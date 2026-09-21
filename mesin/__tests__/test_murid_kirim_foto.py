"""Poin 1 & 4 feedback Filia — ANAK mengunggah foto cara pengerjaannya.

Sebelum ini upload foto hanya ada di akun pengelola/orang tua, jadi anak
yang mengerjakan lembar CETAK tidak punya tempat memasukkan jawabannya
sama sekali ("belum ada tempat untuk upload cara pengerjaan soal, oleh
anak" / "apabila soal latihan di print, bagaimana cara upload jawabannya").

Kontrak yang dikunci di sini:
  - blok kirim foto tampil di halaman kerja anak;
  - POST /murid/foto/<sesi> wajib akun murid DAN sesi milik anak itu;
  - yang tersimpan cuma lampiran 'baru' -- jawaban TIDAK langsung masuk
    laporan, guru tetap yang menerapkan;
  - palang murid tetap utuh: tidak ada kunci/malrule/diagnosis yang
    tersentuh mau pun terender di jalur ini.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import attachments  # noqa: E402
import database  # noqa: E402
import llm  # noqa: E402
import student_pages  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def kirim_foto(server, sesi_id, auth, isi=JPEG, nama="lembar.jpg",
               mime="image/jpeg", field="foto"):
    """POST multipart ke /murid/foto/<sesi> lewat socket nyata."""
    import urllib.error
    import urllib.request

    boundary = "----UjiFotoMurid"
    tubuh = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; '
        f'filename="{nama}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + isi + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        server.alamat + f"/murid/foto/{sesi_id}", data=tubuh, method="POST"
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


# ── 1. Blok kirim foto di halaman kerja anak ──────────────────────────


def test_halaman_kerja_punya_blok_kirim_foto(db):
    """Anak yang mengerjakan di kertas harus melihat jalan masuknya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Bilal", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    assert f'action="/murid/foto/{sesi_id}"' in html
    assert 'name="foto"' in html
    assert "Kirim foto caraku" in html
    assert 'enctype="multipart/form-data"' in html


def test_blok_foto_tidak_membocorkan_kunci(db):
    """Palang murid: halaman kerja tetap bersih dari kunci/diagnosis.

    Assertion menyasar marker BADAN, bukan seluruh dokumen: CSS bersama
    memuat kata "diagnosa"/"Caraku" di komentar dan nama kelas, jadi
    `"diagnosa" not in html` adalah false-positive yang sudah pernah
    menipu tiga kali di repo ini.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "BilalPalang", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    # Buang blok <style> — sisanya adalah badan yang dilihat anak.
    badan = html.split("</style>")[-1]
    rendah = badan.lower()
    assert "malrule" not in rendah
    assert "kode_final" not in rendah
    assert "pembahasan" not in rendah
    assert "langkah:" not in rendah
    assert 'class="kunci"' not in rendah
    # Catatan: JANGAN assert nilai kunci absen dari badan. Kunci sering
    # berupa angka pendek ("3") yang sah muncul sebagai nomor soal atau
    # di dalam kalimat soal itu sendiri — false-positive. Kebocoran nilai
    # dijaga di lapisan datanya (students.soal_murid + test_students.py),
    # bukan dengan mencocokkan string di halaman.


def test_kabar_foto_tampil_setelah_kirim(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "BilalKabar", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        html = student_pages.halaman_kerja_baru(
            kon, sid, sesi_id, kabar_foto="Foto caramu sudah terkirim."
        ).decode()
    assert "Foto caramu sudah terkirim." in html
    assert "kerja-foto-kabar-st" in html


def _sesi_untuk_feby(server) -> int:
    """Guru membuat sesi untuk akun murid uji 'feby' -> sesi_id.

    Sesi WAJIB dibuat lewat rute guru: siswa dan akun murid dihubungkan
    lewat nama (COLLATE NOCASE), dan tanpa itu siswa_dari_akun -> None
    sehingga rute murid menjawab 401/404.
    """
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")
    server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "profil_parameter": "P3"},
    )
    with server.buka() as kon:
        return int(kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"])


# ── 2. Alur HTTP nyata ────────────────────────────────────────────────


def test_http_anak_kirim_foto_tersimpan(server, monkeypatch):
    """Anak kirim foto -> lampiran 'baru' tersimpan, ekstraksi dipanggil."""
    tertangkap = []
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: (
            tertangkap.append(konteks) or [
                {"nomor": 1, "jawaban": "38", "caraku": "115 : 3"}
            ]
        ),
    )
    sesi_id = _sesi_untuk_feby(server)
    kode, isi = kirim_foto(server, sesi_id, ("feby", SANDI_MURID))
    assert kode == 200                       # urllib mengikuti 303
    assert "Foto caramu sudah terkirim" in isi
    assert len(tertangkap) == 1              # AI benar dipanggil
    with server.buka() as kon:
        lampiran = database.daftar_lampiran(kon, sesi_id)
    assert len(lampiran) == 1
    assert lampiran[0]["status"] == "baru"   # guru yang menerapkan


def test_http_guru_tidak_bisa_pakai_rute_murid(server):
    """Rute /murid/* hanya untuk akun berperan murid — guru punya rutenya
    sendiri (/lampiran/<sesi>). Palang tulis tidak boleh melemah."""
    sesi_id = _sesi_untuk_feby(server)
    kode, _ = kirim_foto(server, sesi_id, ("guru", SANDI_GURU))
    assert kode == 401
    with server.buka() as kon:
        assert database.daftar_lampiran(kon, sesi_id) == []


def test_http_anak_tidak_bisa_kirim_ke_sesi_anak_lain(server):
    """Sesi milik anak lain -> 404 (bukan 403: keberadaan id tak boleh bocor).

    PENTING: feby harus punya sesi SENDIRI dulu supaya siswa_dari_akun
    mengembalikan id yang sah. Tanpa itu 404 datang dari cabang "akun
    belum terhubung" dan test ini lolos bahkan kalau cek kepemilikan
    sesi dihapus (terbukti lewat mutation test).
    """
    _sesi_untuk_feby(server)            # feby terhubung ke barisan siswa
    with server.buka() as kon:
        lain = database.tambah_siswa(kon, "AnakLain", pemilik="guru")
        sesi_lain = database.buat_sesi(kon, lain, seed=7)
    kode, _ = kirim_foto(server, sesi_lain, ("feby", SANDI_MURID))
    assert kode == 404
    with server.buka() as kon:
        assert database.daftar_lampiran(kon, sesi_lain) == []


def test_http_bukan_gambar_ditolak_dengan_alasan(server):
    """Bukan gambar -> tidak tersimpan, dan anak diberi tahu alasannya."""
    sesi_id = _sesi_untuk_feby(server)
    kode, isi = kirim_foto(
        server, sesi_id, ("feby", SANDI_MURID),
        isi=b"MZ\x90\x00bukan gambar", nama="virus.exe",
        mime="application/x-msdownload",
    )
    assert kode == 200                     # 303 -> halaman kerja
    assert "bukan foto" in isi
    with server.buka() as kon:
        assert database.daftar_lampiran(kon, sesi_id) == []


def test_http_pesan_ke_anak_tidak_menyebut_jumlah_terbaca(server, monkeypatch):
    """Anak TIDAK diberi angka "X dari N".

    Angka itu informasi untuk guru yang mengoreksi. Ditampilkan ke anak, ia
    mudah ditafsirkan "cuma 1 yang benar" padahal belum dinilai sama sekali.
    """
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [{"nomor": 1, "jawaban": "38", "caraku": "x"}],
    )
    sesi_id = _sesi_untuk_feby(server)
    _kode, isi = kirim_foto(server, sesi_id, ("feby", SANDI_MURID))
    assert "Foto caramu sudah terkirim" in isi
    assert "soal —" not in isi          # frasa pesan guru tidak bocor
    assert "periksa dan koreksi" not in isi


def test_upload_anak_muncul_sebagai_usulan_di_halaman_guru(server, monkeypatch):
    """Rantai penuh: anak kirim foto -> guru buka konfirmasi -> usulan AI ada.

    Inilah inti poin 1 & 4: anak yang mengerjakan di kertas cukup memfoto,
    dan pekerjaannya tetap sampai ke alur diagnosis guru.
    """
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [{"nomor": 1, "jawaban": "38", "caraku": "115 : 3"}],
    )
    sesi_id = _sesi_untuk_feby(server)
    kirim_foto(server, sesi_id, ("feby", SANDI_MURID))
    with server.buka() as kon:
        lid = database.daftar_lampiran(kon, sesi_id)[0]["id"]
    kode, isi, _ = server.minta(f"/lampiran/{lid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert 'value="38"' in isi           # usulan AI terisi untuk guru
    assert 'value="115 : 3"' in isi
    assert "Terapkan" in isi             # guru yang memutuskan
