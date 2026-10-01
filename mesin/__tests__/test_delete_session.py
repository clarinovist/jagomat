"""Uji hapus sesi — Task perbaikan halaman guru.

Hapus sesi harus menghilangkan SEMUA jejaknya: baris sesi, sesi_soal,
jawaban, diagnosis, dan lampiran (semuanya lewat ON DELETE CASCADE di
skema), PLUS berkas foto lampiran di cakram yang tidak diurus basis data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import attachments  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
from diagnosis import diagnosa  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(tmp_path / "lampiran"))
    return p


def _sesi_dengan_hasil(kon) -> int:
    """Sesi 12 soal; dua soal pertama punya jawaban + diagnosis + foto."""
    sid = database.tambah_siswa(kon, "Uji", pemilik="guru")
    sesi_id = database.buat_sesi(kon, sid, seed=42)
    for baris in database.isi_sesi(kon, sesi_id)[:2]:
        jid = database.simpan_jawaban(
            kon, baris["sesi_soal_id"], jawaban="7", cara="aku hitung"
        )
        u = diagnosa(
            baris["kunci"], "7", "aku hitung", "", False,
            database.malrule_soal(kon, baris["soal_id"]), False,
        )
        database.simpan_diagnosis(
            kon, jid, u.benar, u.kode, u.kode, u.malrule_id, u.alasan
        )
    nama = attachments.simpan_berkas(sesi_id, "foto-lembar.png", b"\x89PNG palsu")
    database.simpan_lampiran(kon, sesi_id, nama, "image/png")
    return sesi_id


def test_hapus_sesi_kosong_menghilangkan_sesi_dan_soalnya(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Kosong")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        assert database.hapus_sesi(kon, sesi_id) is True
        sisa_sesi = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0]
        sisa_soal = kon.execute(
            "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()[0]
    assert sisa_sesi == 0
    assert sisa_soal == 0


def test_hapus_sesi_menghilangkan_jawaban_diagnosis_lampiran_dan_berkasnya(db):
    with database.buka(db) as kon:
        sesi_id = _sesi_dengan_hasil(kon)
        folder = attachments.direktori_lampiran() / str(sesi_id)
        assert folder.is_dir(), "prasyarat: foto sudah tersimpan di cakram"

        assert database.hapus_sesi(kon, sesi_id) is True

        n_jawaban = kon.execute(
            """SELECT COUNT(*) FROM jawaban j
               JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
        n_diagnosis = kon.execute(
            """SELECT COUNT(*) FROM diagnosis d
               JOIN jawaban j ON j.id = d.jawaban_id
               JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
        n_lampiran = kon.execute(
            "SELECT COUNT(*) FROM lampiran WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()[0]
    assert n_jawaban == 0
    assert n_diagnosis == 0
    assert n_lampiran == 0

    attachments.bersihkan_berkas(sesi_id)
    assert not folder.exists(), "berkas foto lampiran harus ikut terhapus"


def test_hapus_sesi_tak_dikenal_mengembalikan_false_tanpa_meledak(db):
    with database.buka(db) as kon:
        assert database.hapus_sesi(kon, 99999) is False


def test_bersihkan_berkas_pada_folder_tidak_ada_tidak_meledak(db):
    # Idempoten: dipanggil dua kali (atau saat sesi tanpa foto) tetap aman.
    attachments.bersihkan_berkas(424242)
    attachments.bersihkan_berkas(424242)


# ── Rute web + halaman konfirmasi ────────────────────────────────────


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("OSN_DIREKTORI_LAMPIRAN", raising=False)
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _sesi_dengan_hasil_http(server) -> int:
    """Versi _sesi_dengan_hasil lewat DB server uji."""
    with server.buka() as kon:
        return _sesi_dengan_hasil(kon)


def test_konfirmasi_hapus_menampilkan_angka_nyata(db):
    """Peringatan menyebut jumlah jawaban/diagnosis/foto yang SESUNGGUHNYA
    hilang — bukan kata-kata generik yang membuat hapus terasa ringan."""
    with database.buka(db) as kon:
        sesi_id = _sesi_dengan_hasil(kon)
        isi = teacher_pages.halaman_konfirmasi_hapus(kon, sesi_id).decode()
    assert "2 jawaban" in isi
    assert "2 diagnosis" in isi
    assert "1 foto" in isi
    assert f'action="/sesi/{sesi_id}/hapus"' in isi
    assert 'name="konfirmasi" value="1"' in isi
    assert "tidak bisa dibatalkan" in isi


def test_konfirmasi_hapus_sesi_tak_dikenal_mengembalikan_none(db):
    with database.buka(db) as kon:
        assert teacher_pages.halaman_konfirmasi_hapus(kon, 99999) is None


def test_halaman_sesi_memuat_tombol_hapus(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tombol")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    assert f'action="/sesi/{sesi_id}/hapus"' in isi


def test_halaman_utama_menampilkan_pesan_hapus(db):
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Pesan")
        isi = teacher_pages.halaman_utama_stitch(kon, pesan="Sesi 3 dihapus.").decode()
    assert "Sesi 3 dihapus." in isi


def test_http_get_hapus_butuh_guru(server):
    sesi_id = _sesi_dengan_hasil_http(server)
    kode, _, _ = server.minta(f"/sesi/{sesi_id}/hapus")
    assert kode == 401


def test_http_hapus_mempertahankan_lookup_fasad(server, monkeypatch):
    sesi_id = _sesi_dengan_hasil_http(server)
    asli_halaman = web.halaman_konfirmasi_hapus
    asli_bersihkan = attachments.bersihkan_berkas
    panggilan = []

    def halaman_terpantau(kon, target_id, **kwargs):
        panggilan.append(("halaman", target_id))
        return asli_halaman(kon, target_id, **kwargs)

    def bersihkan_terpantau(target_id):
        panggilan.append(("bersihkan", target_id))
        return asli_bersihkan(target_id)

    monkeypatch.setattr(web, "halaman_konfirmasi_hapus", halaman_terpantau)
    monkeypatch.setattr(web.lampiran_mod, "bersihkan_berkas", bersihkan_terpantau)
    assert server.minta(
        f"/sesi/{sesi_id}/hapus", auth=("guru", SANDI_GURU)
    )[0] == 200
    assert server.minta(
        f"/sesi/{sesi_id}/hapus",
        auth=("guru", SANDI_GURU),
        data={"konfirmasi": "1"},
    )[0] == 200
    assert panggilan == [("halaman", sesi_id), ("bersihkan", sesi_id)]


def test_http_get_hapus_menampilkan_konfirmasi(server):
    sesi_id = _sesi_dengan_hasil_http(server)
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}/hapus", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert "tidak bisa dibatalkan" in isi


def test_http_post_tanpa_konfirmasi_tidak_menghapus(server):
    sesi_id = _sesi_dengan_hasil_http(server)
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}/hapus", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 200
    assert "tidak bisa dibatalkan" in isi  # kembali ke halaman konfirmasi
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0]
    assert n == 1, "POST tanpa konfirmasi=1 TIDAK boleh menghapus"


def test_http_post_konfirmasi_menghapus_foto_dan_menampilkan_pesan(server):
    sesi_id = _sesi_dengan_hasil_http(server)
    folder = attachments.direktori_lampiran() / str(sesi_id)
    assert folder.is_dir()
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}/hapus", auth=("guru", SANDI_GURU),
        data={"konfirmasi": "1"},
    )
    # urllib mengikuti 303 ke /?pesan=... — halaman akhirnya memuat pesan.
    assert kode == 200
    assert f"Sesi {sesi_id} dihapus." in isi
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0]
    assert n == 0
    assert not folder.exists(), "berkas foto lampiran harus ikut terhapus"
