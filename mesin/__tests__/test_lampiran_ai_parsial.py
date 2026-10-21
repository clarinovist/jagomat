"""Bug lapangan 2 Sep 2026 — foto lembar diupload, AI "tidak menganalisa".

Tiga sebab nyata yang ditemukan dari data produksi (sesi 50 soal, foto
memuat 3 soal) dan dikunci di sini:

  1. balasan model memakai kunci bahasa Inggris (number/answer/work)
     -> parse gagal -> hasil dibuang;
  2. balasan terpotong batas token di soal ke-11 -> JSON tak sah -> dibuang;
  3. verifikasi menuntut nomor 1..N LENGKAP -> bacaan sebagian dibuang.

Plus perilaku baru: pesan menyebut "X dari N", dan tombol "Coba baca
ulang" mengulang ekstraksi tanpa unggah ulang.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import attachments  # noqa: E402
import database  # noqa: E402
import llm  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


# ── 1. Alias kunci bahasa Inggris ─────────────────────────────────────


def test_parse_menerima_kunci_inggris():
    """number/answer/work = nomor/jawaban/caraku.

    Balasan nyata dari model vision DeepSeek memakai kunci Inggris
    meski prompt berbahasa Indonesia — dulu seluruh bacaan dibuang.
    """
    konten = json.dumps(
        {"soal": [
            {"number": 1, "answer": "38", "work": "115 : 3 = 38 sisa 1"},
            {"number": 2, "answer": "30", "work": "120 : 4 = 30"},
        ]}
    )
    hasil = llm.parse_ekstraksi(konten)
    assert hasil == [
        {"nomor": 1, "jawaban": "38", "caraku": "115 : 3 = 38 sisa 1"},
        {"nomor": 2, "jawaban": "30", "caraku": "120 : 4 = 30"},
    ]


def test_parse_kunci_indonesia_tetap_utama():
    """Alias tidak boleh menggeser kunci Indonesia."""
    konten = json.dumps(
        {"soal": [{"nomor": 1, "jawaban": "7", "caraku": "coret"}]}
    )
    assert llm.parse_ekstraksi(konten) == [
        {"nomor": 1, "jawaban": "7", "caraku": "coret"}
    ]


# ── 2. JSON terpotong batas token ─────────────────────────────────────


def test_parse_menyelamatkan_json_terpotong():
    """Balasan putus di tengah objek: objek utuh sebelumnya tetap dipakai."""
    terpotong = (
        '{"soal": [\n'
        '  {"nomor": 1, "jawaban": "38", "caraku": "115 : 3"},\n'
        '  {"nomor": 2, "jawaban": "30", "caraku": "120 : 4"},\n'
        '  {"nomor": 3, "jawaban": "560", "caraku": "70 x 8 = 5'
    )
    hasil = llm.parse_ekstraksi(terpotong)
    assert hasil is not None
    assert [h["nomor"] for h in hasil] == [1, 2]
    assert hasil[0]["jawaban"] == "38"


def test_parse_terpotong_tanpa_objek_utuh_tetap_none():
    """Tidak ada satu pun butir utuh -> None (jangan mengarang)."""
    assert llm.parse_ekstraksi('{"soal": [{"nomor": 1, "jawa') is None


# ── 3. Verifikasi menerima bacaan sebagian ────────────────────────────


def test_verifikasi_terima_sebagian():
    hasil = [{"nomor": 3, "jawaban": "560", "caraku": ""}]
    assert llm.verifikasi_ekstraksi(hasil, 50) is True


def test_verifikasi_tolak_kosong_dan_luar_rentang():
    assert llm.verifikasi_ekstraksi([], 10) is False
    assert llm.verifikasi_ekstraksi(
        [{"nomor": 99, "jawaban": "x", "caraku": ""}], 10
    ) is False


def test_saring_membuang_nomor_asing_dan_duplikat():
    hasil = [
        {"nomor": 99, "jawaban": "x", "caraku": ""},
        {"nomor": 2, "jawaban": "9", "caraku": ""},
        {"nomor": 2, "jawaban": "lain", "caraku": ""},
    ]
    assert llm.saring_ekstraksi(hasil, 3) == [
        {"nomor": 2, "jawaban": "9", "caraku": ""}
    ]


# ── 4. Pesan menyebut "X dari N" ──────────────────────────────────────


def _sesi_uji(kon, nama="AnakFoto"):
    sid = database.tambah_siswa(kon, nama, pemilik="guru")
    return database.buat_sesi(kon, sid, seed=7)


def test_pesan_menyebut_jumlah_terbaca_dari_total(db, monkeypatch):
    """Bacaan sebagian bukan kegagalan — guru harus lihat angkanya.

    Keluhan lapangan: "ai tidak langsung menganalisa". Pesan lama hanya
    menyebut jumlah butir yang dikembalikan model (bisa 50 padahal semua
    kosong), jadi guru tak tahu apa pun terbaca.
    """
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [
            {"nomor": 1, "jawaban": "38", "caraku": "115 : 3"},
            {"nomor": 2, "jawaban": "", "caraku": ""},
        ],
    )
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon)
        total = len(database.isi_sesi(kon, sesi_id))
        hasil_json, pesan = attachments._ekstraksi_untuk(kon, sesi_id, b"foto")
    assert f"1 dari {total} soal" in pesan
    assert json.loads(hasil_json)["soal"][0]["jawaban"] == "38"


def test_pesan_khusus_kalau_semua_kosong(db, monkeypatch):
    """Foto salah (mis. screenshot) -> semua kosong: katakan apa adanya."""
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [{"nomor": 1, "jawaban": "", "caraku": ""}],
    )
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakKosong")
        _, pesan = attachments._ekstraksi_untuk(kon, sesi_id, b"foto")
    assert "tidak menemukan jawaban terisi" in pesan


def test_pesan_gagal_menyarankan_baca_ulang(db, monkeypatch):
    # AI dikonfigurasi tetapi gagal baca; tanpa kunci berlaku mode isi manual
    # (lihat test_lampiran_isi_manual).
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "kunci-sintetis", "model": ""})
    monkeypatch.setattr(llm, "ekstrak_lembar", lambda konteks, b64: None)
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakGagal")
        hasil_json, pesan = attachments._ekstraksi_untuk(kon, sesi_id, b"foto")
    assert hasil_json == ""
    assert "Coba baca ulang" in pesan


# ── 5. Baca ulang tanpa unggah ulang ──────────────────────────────────


def test_baca_ulang_menimpa_hasil_tanpa_unggah_ulang(db, monkeypatch, tmp_path):
    """Bacaan pertama gagal, tekan baca ulang -> hasil_json terisi.

    Foto sudah di cakram; guru tak perlu memotret lagi.
    """
    akar = tmp_path / "lampiran-uji"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakUlang")
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")

        monkeypatch.setattr(
            llm, "ekstrak_lembar",
            lambda konteks, b64: [
                {"nomor": 1, "jawaban": "38", "caraku": "115 : 3"}
            ],
        )
        pesan = attachments.baca_ulang(kon, lid)
        lamp = database.ambil_lampiran(kon, lid)
    assert "1 dari" in pesan
    assert json.loads(lamp["hasil_json"])["soal"][0]["jawaban"] == "38"


def test_baca_ulang_tidak_mengubah_status_diterapkan(db, monkeypatch, tmp_path):
    """Jejak penerapan tidak boleh hilang karena baca ulang."""
    akar = tmp_path / "lampiran-uji2"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakStatus")
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg")
        database.tandai_lampiran(kon, lid, "diterapkan")
        monkeypatch.setattr(llm, "ekstrak_lembar", lambda k, b: None)
        attachments.baca_ulang(kon, lid)
        lamp = database.ambil_lampiran(kon, lid)
    assert lamp["status"] == "diterapkan"


def test_baca_ulang_berkas_hilang_pesan_jujur(db, monkeypatch, tmp_path):
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(tmp_path / "kosong"))
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakHilang")
        lid = database.simpan_lampiran(kon, sesi_id, "tidak-ada.jpg")
        pesan = attachments.baca_ulang(kon, lid)
    assert "tidak ditemukan" in pesan.lower()


def test_halaman_konfirmasi_punya_tombol_baca_ulang(db):
    with database.buka(db) as kon:
        sesi_id = _sesi_uji(kon, "AnakTombol")
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")
        html = attachments.halaman_konfirmasi(kon, lid).decode()
    assert f'action="/lampiran/{lid}/baca-ulang"' in html
    assert "Coba baca ulang dengan AI" in html
    # Form baca ulang TERPISAH dari form terapkan (form bersarang tak sah)
    assert html.index("baca-ulang") < html.index("/terapkan")


# ── 6. Rute HTTP /lampiran/<id>/baca-ulang ────────────────────────────


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def test_http_baca_ulang_memperbarui_usulan(server, monkeypatch, tmp_path):
    akar = tmp_path / "lampiran-http"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [
            {"nomor": 1, "jawaban": "38", "caraku": "115 : 3"}
        ],
    )
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakHttp", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")
    kode, isi, _ = server.minta(
        f"/lampiran/{lid}/baca-ulang",
        auth=("guru", SANDI_GURU),
        data={},
    )
    assert kode == 200
    assert "1 dari" in isi
    assert 'value="38"' in isi          # usulan baru tampil di form


def test_http_baca_ulang_tidak_menulis_jawaban(server, monkeypatch, tmp_path):
    """Baca ulang HANYA menyegarkan usulan — jawaban anak tidak tersentuh."""
    akar = tmp_path / "lampiran-http2"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    monkeypatch.setattr(
        llm, "ekstrak_lembar",
        lambda konteks, b64: [{"nomor": 1, "jawaban": "999", "caraku": "x"}],
    )
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakAman", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg")
    server.minta(
        f"/lampiran/{lid}/baca-ulang", auth=("guru", SANDI_GURU), data={}
    )
    with server.buka() as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        lamp = database.ambil_lampiran(kon, lid)
    assert baris["jawaban"] in (None, "")
    assert baris["jawaban_id"] is None
    assert lamp["status"] == "baru"


def test_http_baca_ulang_lampiran_orang_lain_404(server, monkeypatch, tmp_path):
    """Palang kepemilikan sama ketat dengan rute lampiran lain."""
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(tmp_path / "l3"))
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakOrangLain", pemilik="guru2")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg")
    kode, _, _ = server.minta(
        f"/lampiran/{lid}/baca-ulang", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 404

