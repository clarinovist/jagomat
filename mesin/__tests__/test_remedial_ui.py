"""Alur UI remedial terarah dari profil anak dan hasil satu sesi."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import teacher_pages  # noqa: E402
import topics  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "uji.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _catat(kon, siswa_id, template_id, kode="K", *, direview=True):
    paket = topics.paket_untuk_template([template_id])
    level = next(iter(paket.komposisi))
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=20_000 + kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0],
        urutan=(template_id,),
        topik=paket,
        level=level,
    )
    butir = database.isi_sesi(kon, sesi_id)[0]
    jawaban_id = database.simpan_jawaban(
        kon, butir["sesi_soal_id"], jawaban="999999", cara="hitung"
    )
    database.simpan_diagnosis(
        kon,
        jawaban_id,
        benar=False,
        kode_usulan=kode,
        kode_final=kode,
        alasan="Belum memahami hubungan umur" if kode == "K" else "Perlu lebih teliti",
    )
    database.tandai_selesai(kon, sesi_id)
    if direview:
        kon.execute(
            "UPDATE sesi SET direview = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )
    return sesi_id


def test_profil_menjelaskan_dan_memilih_fokus_remedial(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Fokus", pemilik="guru")
        _catat(kon, siswa_id, "soal_umur", "K")
        _catat(kon, siswa_id, "soal_uang", "H")
        kon.execute(
            "UPDATE sesi SET tanggal = '2099-12-31' WHERE siswa_id = ?",
            (siswa_id,),
        )
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
        halaman = teacher_pages.halaman_anak(
            kon, siswa, query="section=latihan"
        ).decode()

    assert "Latihan terarah" in halaman
    assert "Pilihan yang dicentang adalah rekomendasi berdasarkan hasil terbaru" in halaman
    panel = halaman.split('<section class="remedial-st">', 1)[1].split("</section>", 1)[0]
    assert "Soal tentang umur" in panel
    assert "Salah konsep · 1 kali" in panel
    assert "Salah hitung · 1 kali" in panel
    assert 'name="template_id" value="soal_umur" checked' in panel
    assert 'name="template_id" value="soal_uang" checked' not in panel
    assert "Logika &amp; Penalaran" not in panel
    assert "Belum memahami hubungan umur" not in panel
    assert "Perlu lebih teliti" not in panel
    assert "sesi #" not in panel
    assert "2099-12-31" not in panel
    assert "soal_umur" not in halaman.replace('value="soal_umur"', "")


def test_hasil_sesi_hanya_menawarkan_kesalahan_sesi_itu(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Sesi", pemilik="guru")
        sumber = _catat(kon, siswa_id, "soal_umur", "K")
        _catat(kon, siswa_id, "soal_uang", "H")
        halaman = teacher_pages.halaman_sesi_stitch(kon, sumber).decode()

    assert "Perbaiki kesalahan dari sesi ini" in halaman
    assert "Soal tentang umur" in halaman
    assert "Soal uang" not in halaman
    assert f'name="sumber_sesi_id" value="{sumber}"' in halaman


def test_hasil_belum_selesai_tidak_menampilkan_form_remedial(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Belum", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    assert "Perbaiki kesalahan dari sesi ini" not in halaman


def test_post_fokus_satu_template_membuat_sepuluh_soal(server):
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak HTTP", pemilik="guru")
        _catat(kon, siswa_id, "soal_umur", "K")

    kode, isi, _ = server.minta(
        f"/sesi-remedial/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"template_id": "soal_umur", "jumlah_soal": "10"},
    )

    assert kode == 200
    assert "Remedial Soal tentang umur dibuat" in isi
    with server.buka() as kon:
        sesi_id = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC", (siswa_id,)
        ).fetchone()["id"]
        isi_sesi = database.isi_sesi(kon, sesi_id)
    assert [b["template_id"] for b in isi_sesi] == ["soal_umur"] * 10


def test_riwayat_guru_dan_murid_menandai_sesi_remedial(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Riwayat", pemilik="guru")
        _catat(kon, siswa_id, "soal_umur", "K")
        remedial_id = database.buat_sesi_remedial(
            kon,
            siswa_id,
            template_ids=["soal_umur"],
            seed=123,
            jumlah_soal=10,
        )
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
        guru = teacher_pages.halaman_anak(
            kon, siswa, query="section=riwayat"
        ).decode()
        import student_pages
        murid = student_pages.halaman_daftar_sesi_baru(
            kon, siswa_id, "Anak Riwayat"
        ).decode()

    assert f"Sesi #{remedial_id}" in guru
    assert "Remedial" in guru
    assert "Latihan bebas · Remedial" in guru
    assert "Logika &amp; Penalaran" in guru
    assert "Latihan terarah" in murid
    assert "Remedial" not in murid
    assert "Fokus Soal tentang umur" not in murid


def test_post_sumber_dari_anak_lain_404_dan_tidak_membuat_sesi(server):
    with server.buka() as kon:
        anak_a = database.tambah_siswa(kon, "Anak Sumber A", pemilik="guru")
        anak_b = database.tambah_siswa(kon, "Anak Sumber B", pemilik="guru")
        sumber_a = _catat(kon, anak_a, "soal_umur", "K")
        _catat(kon, anak_b, "soal_umur", "K")
        sebelum = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (anak_b,)
        ).fetchone()[0]

    kode, isi, _ = server.minta(
        f"/sesi-remedial/{anak_b}",
        auth=("guru", SANDI_GURU),
        data={
            "template_id": "soal_umur",
            "jumlah_soal": "10",
            "sumber_sesi_id": str(sumber_a),
        },
    )

    assert kode == 404
    assert "Halaman tidak ada" in isi
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (anak_b,)
        ).fetchone()[0]
    assert sesudah == sebelum


def test_post_jumlah_di_luar_batas_tidak_membuat_sesi(server):
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Batas", pemilik="guru")
        _catat(kon, siswa_id, "soal_umur", "K")
        sebelum = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchone()[0]

    kode, isi, _ = server.minta(
        f"/sesi-remedial/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"template_id": "soal_umur", "jumlah_soal": "999"},
    )

    assert kode == 200
    assert "Jumlah soal harus antara 1 dan 50" in isi
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchone()[0]
    assert sesudah == sebelum


def test_post_template_di_luar_kandidat_tidak_membuat_sesi(server):
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Tamper", pemilik="guru")
        _catat(kon, siswa_id, "soal_umur", "K")
        sebelum = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchone()[0]

    kode, isi, _ = server.minta(
        f"/sesi-remedial/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"template_id": "soal_uang", "jumlah_soal": "10"},
    )

    assert kode == 200
    assert "bukan pilihan remedial yang tersedia" in isi
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchone()[0]
    assert sesudah == sebelum
