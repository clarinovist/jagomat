"""Poin b feedback Filia — anak melihat PEMBAHASAN setelah sesi direview.

Pertanyaan Filia: "setelah mengetahui hasil anak, next nya apa yang harus
kita lakukan?" Jawaban tahap pertama: anak harus tahu LETAK salahnya,
bukan cuma benar/salah. Pembahasan langkah per soal sudah ada di sisi
guru (Soal.pembahasan) — di sini dibuka untuk anak, dengan pagar:

  1. HANYA sesi yang sudah DIREVIEW guru. Sebelum direview, membuka
     pembahasan = membocorkan kunci sebelum dinilai.
  2. Anak melihat pembahasan + benar/salah + jawabannya sendiri. Anak
     TIDAK melihat kode diagnosis (K/H/E/N/B), malrule, atau alasan —
     itu bahasa kerja guru, dan menampilkannya ke anak mengubah alat
     bantu belajar jadi label "kamu tipe salah K".
  3. Sesi milik anak lain tetap 404.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import student_pages  # noqa: E402
import students  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


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


def _sesi_dikerjakan(kon, nama="AnakHasil", direview=True):
    """Sesi yang sudah diisi anak dan (opsional) sudah direview guru."""
    sid = database.tambah_siswa(kon, nama, pemilik="guru")
    sesi_id = database.buat_sesi(kon, sid, seed=7, jumlah_soal=3)
    baris = database.isi_sesi(kon, sesi_id)
    # soal 1 dijawab BENAR, soal 2 dijawab salah, soal 3 dibiarkan kosong
    database.simpan_jawaban(kon, baris[0]["sesi_soal_id"],
                            jawaban=baris[0]["kunci"], cara="aku hitung")
    database.simpan_jawaban(kon, baris[1]["sesi_soal_id"],
                            jawaban="999", cara="aku tebak")
    import reports
    reports.diagnosa_murid(kon, sesi_id)
    database.tandai_selesai(kon, sesi_id)
    if direview:
        kon.execute(
            "UPDATE sesi SET direview = datetime('now') WHERE id = ?",
            (sesi_id,),
        )
    return sid, sesi_id


# ── 1. Data layer: students.hasil_murid ───────────────────────────────


def test_hasil_murid_hanya_setelah_direview(db):
    """Sebelum guru mereview, pembahasan TIDAK boleh keluar."""
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakBelumReview", direview=False)
        assert students.hasil_murid(kon, sid, sesi_id) is None


def test_hasil_murid_setelah_direview_berisi_pembahasan(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon)
        hasil = students.hasil_murid(kon, sid, sesi_id)
    assert hasil is not None
    assert hasil["jumlah"] == 3
    assert hasil["benar"] == 1
    butir = hasil["soal"]
    assert len(butir) == 3
    assert butir[0]["benar"] is True
    assert butir[1]["benar"] is False
    assert butir[0]["jawabanku"]           # jawaban anak sendiri dikembalikan
    assert all("pembahasan" in b for b in butir)


def test_hasil_murid_tidak_membawa_kode_diagnosis(db):
    """Anak tidak menerima kode K/H/E/N/B maupun malrule/alasan.

    Itu bahasa kerja guru. Dibawa ke anak, alat bantu belajar berubah
    jadi label ("kamu tipe salah K") — dan bocornya lewat data, bukan
    lewat halaman, jadi dijaga di sini.
    """
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakTanpaKode")
        hasil = students.hasil_murid(kon, sid, sesi_id)
    for b in hasil["soal"]:
        assert "kode" not in b
        assert "kode_final" not in b
        assert "malrule_id" not in b
        assert "alasan" not in b


def test_hasil_murid_sesi_anak_lain_none(db):
    with database.buka(db) as kon:
        _sid_a, sesi_a = _sesi_dikerjakan(kon, "AnakA")
        sid_b = database.tambah_siswa(kon, "AnakB", pemilik="guru")
        assert students.hasil_murid(kon, sid_b, sesi_a) is None


# ── 2. Halaman hasil ──────────────────────────────────────────────────


def test_halaman_hasil_menampilkan_pembahasan(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakHalaman")
        html = student_pages.halaman_hasil_murid(kon, sid, sesi_id).decode()
    assert "Caranya:" in html               # blok pembahasan terender
    assert "Jawabanmu:" in html             # jawaban anak sendiri
    assert "Benar" in html and "Belum tepat" in html


def test_halaman_hasil_none_kalau_belum_direview(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakBelum2", direview=False)
        assert student_pages.halaman_hasil_murid(kon, sid, sesi_id) is None


def test_halaman_hasil_tidak_menampilkan_kode_diagnosis(db):
    """Anak tidak melihat K/H/E/N/B, malrule, atau alasan guru."""
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakTanpaKode2")
        html = student_pages.halaman_hasil_murid(kon, sid, sesi_id).decode()
    badan = html.split("</style>")[-1]
    rendah = badan.lower()
    assert "malrule" not in rendah
    assert "kode_final" not in rendah
    assert "miskonsepsi" not in rendah
    assert "diagnosis" not in rendah


def test_kartu_sesi_direview_menuju_halaman_hasil(db):
    """Setelah direview, kartu di /murid membuka hasil — bukan lembar lagi."""
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakKartu")
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakKartu").decode()
    assert f'href="/murid/hasil/{sesi_id}"' in html


def test_sesi_terkirim_belum_direview_hanya_status_menunggu(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dikerjakan(kon, "AnakKartu2", direview=False)
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakKartu2").decode()
    assert "Menunggu diperiksa" in html
    assert f'href="/murid/kerjakan/{sesi_id}"' not in html
    assert f'href="/murid/hasil/{sesi_id}"' not in html


# ── 3. Pembahasan harus berbahasa ANAK ────────────────────────────────


def test_tidak_ada_pembahasan_berbahasa_guru():
    """Pembahasan kini dibaca ANAK — jangan menyebut istilah kerja guru.

    Bug nyata yang ditemukan saat membangun halaman hasil: 79 template
    memakai kalimat "Perhatikan malrule di halaman koreksi." Itu aman
    selama pembahasan hanya dilihat guru, dan langsung bocor begitu
    halaman anak dibuka. Guard ini menjaga supaya template baru tidak
    mengulanginya.
    """
    import random

    import topics
    from templates import LEVEL, REGISTRI

    terlarang = ("malrule", "halaman koreksi", "kode_final", "miskonsepsi")
    pelanggar = []
    for topik_id in topics.daftar_topik():
        if topik_id == "campuran":       # delegasi ke topik pemilik
            continue
        paket = topics.ambil(topik_id)
        for level in LEVEL:
            urutan = paket.komposisi.get(level)
            if not urutan:
                continue
            for template_id in sorted(set(urutan)):
                rng = random.Random(abs(hash((topik_id, template_id))) % 99991)
                param = (
                    paket.parameter_untuk(template_id, rng, level)
                    if paket.parameter_untuk else {}
                )
                if not param:
                    continue
                soal = REGISTRI[template_id](**param)
                teks = (getattr(soal, "pembahasan", "") or "").lower()
                for kata in terlarang:
                    if kata in teks:
                        pelanggar.append((topik_id, template_id, kata))
    assert not pelanggar, f"pembahasan berbahasa guru: {pelanggar[:5]}"


# ── 4. Rute HTTP /murid/hasil/<id> ────────────────────────────────────


def _sesi_feby_direview(server, direview=True):
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")
    server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "profil_parameter": "P3"},
    )
    with server.buka() as kon:
        sesi_id = int(kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"])
        baris = database.isi_sesi(kon, sesi_id)
        database.simpan_jawaban(kon, baris[0]["sesi_soal_id"],
                                jawaban=baris[0]["kunci"], cara="aku hitung")
        import reports
        reports.diagnosa_murid(kon, sesi_id)
        database.tandai_selesai(kon, sesi_id)
        if direview:
            kon.execute(
                "UPDATE sesi SET direview = datetime('now') WHERE id = ?",
                (sesi_id,),
            )
    return sesi_id


def test_http_anak_buka_hasil_setelah_direview(server):
    sesi_id = _sesi_feby_direview(server)
    kode, isi, _ = server.minta(
        f"/murid/hasil/{sesi_id}", auth=("feby", SANDI_MURID)
    )
    assert kode == 200
    assert "Caranya:" in isi
    assert "Jawabanmu:" in isi


def test_http_hasil_belum_direview_404_dengan_penjelasan(server):
    """Belum dinilai -> 404, tapi kalimatnya ramah anak (bukan halaman rusak)."""
    sesi_id = _sesi_feby_direview(server, direview=False)
    kode, isi, _ = server.minta(
        f"/murid/hasil/{sesi_id}", auth=("feby", SANDI_MURID)
    )
    assert kode == 404
    assert "belum selesai diperiksa" in isi.lower()


def test_http_hasil_anonim_tidak_terbuka(server):
    """Tanpa identitas murid: dialihkan ke /masuk (urllib mengikuti 303)."""
    kode, isi, _ = server.minta("/murid/hasil/1")
    assert kode in (200, 401)
    if kode == 200:
        assert "Masuk" in isi          # halaman login, bukan hasil
    assert "Caranya:" not in isi


def test_http_guru_tidak_bisa_buka_halaman_hasil_anak(server):
    """Rute /murid/* tetap khusus akun murid — guru punya /sesi/<id>."""
    sesi_id = _sesi_feby_direview(server)
    kode, isi, _ = server.minta(
        f"/murid/hasil/{sesi_id}", auth=("guru", SANDI_GURU)
    )
    assert "Caranya:" not in isi       # guru tidak memakai permukaan anak
    assert "Jawabanmu:" not in isi
