"""Retensi bukti 30 hari: sapu idempoten, urutan aman, sisa .tmp-*, dan CLI operator.

Data dan berkas sintetis di tmp_path; tidak menyentuh folder bukti atau DB nyata.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import pesanan_retensi as pr
import pesanan_transfer as tf
from bukti_kit import JPEG
from transfer_kit import ADMIN, SESUDAH_UPLOAD, berkas, menunggu, siapkan_db_transfer

FORMAT = "%Y-%m-%dT%H:%M:%S"
SESUDAH_30_HARI = "2026-12-18T12:00:00"
SEBELUM_30_HARI = "2026-12-17T12:00:00"


@pytest.fixture
def db(tmp_path):
    return siapkan_db_transfer(tmp_path)


@pytest.fixture
def kon(db):
    with tf.buka(db, tulis_data=True) as sambungan:
        yield sambungan


@pytest.fixture
def folder(tmp_path):
    jalur = tmp_path / "folder-bukti"
    jalur.mkdir()
    return jalur


def _putuskan(kon, folder, n=1, *, setuju=True, tulis_berkas=True):
    order, _ = menunggu(kon, n)
    if setuju:
        tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    else:
        tf.tolak(kon, order["order_id"], ADMIN, "Tidak sesuai", SESUDAH_UPLOAD)
    if tulis_berkas:
        (folder / berkas(n)).write_bytes(JPEG)
    return order


def _tertanda(kon):
    return kon.execute("SELECT COUNT(*) FROM transfer_bukti_hapus").fetchone()[0]


def _lama(folder, nama, sekarang=SESUDAH_30_HARI, selisih_detik=7200):
    """Buat berkas sementara yang berumur `selisih_detik` terhadap `sekarang`."""
    jalur = folder / nama
    jalur.write_bytes(b"sisa")
    epoch = datetime.strptime(sekarang, FORMAT).replace(tzinfo=timezone.utc).timestamp() - selisih_detik
    os.utime(jalur, (epoch, epoch))
    return jalur


# --- bukti ---------------------------------------------------------------------

def test_sapu_menghapus_berkas_lalu_menandai_bukti_yang_sudah_30_hari(kon, folder):
    _putuskan(kon, folder, 1)
    hasil = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (hasil.berkas_dihapus, hasil.ditandai, hasil.gagal) == (1, 1, 0)
    assert not (folder / berkas(1)).exists()
    assert _tertanda(kon) == 1 and tf.bukti_kedaluwarsa(kon, SESUDAH_30_HARI) == ()


def test_sapu_sebelum_30_hari_tidak_menyentuh_apa_pun(kon, folder):
    _putuskan(kon, folder, 1)
    hasil = pr.sapu(kon, folder, SEBELUM_30_HARI)
    assert (hasil.berkas_dihapus, hasil.ditandai) == (0, 0)
    assert (folder / berkas(1)).exists() and _tertanda(kon) == 0


def test_sapu_tidak_pernah_menghapus_bukti_yang_belum_diputuskan(kon, folder):
    order, _ = menunggu(kon, 1)
    (folder / berkas(1)).write_bytes(JPEG)
    hasil = pr.sapu(kon, folder, "2030-01-01T00:00:00")
    assert (hasil.berkas_dihapus, hasil.ditandai) == (0, 0)
    assert (folder / berkas(1)).exists()


def test_sapu_bukti_yang_ditolak_juga_dihapus(kon, folder):
    _putuskan(kon, folder, 1, setuju=False)
    assert pr.sapu(kon, folder, SESUDAH_30_HARI).ditandai == 1


def test_sapu_idempoten_dijalankan_berulang_tanpa_galat(kon, folder):
    _putuskan(kon, folder, 1)
    pr.sapu(kon, folder, SESUDAH_30_HARI)
    ulang = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (ulang.berkas_dihapus, ulang.ditandai, ulang.gagal, ulang.sementara_dibersihkan) == (0, 0, 0, 0)
    assert _tertanda(kon) == 1


def test_berkas_hilang_duluan_tidak_membuat_macet_dan_tetap_ditandai(kon, folder):
    _putuskan(kon, folder, 1, tulis_berkas=False)
    _putuskan(kon, folder, 2)
    hasil = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (hasil.ditandai, hasil.berkas_dihapus, hasil.berkas_sudah_hilang, hasil.gagal) == (2, 1, 1, 0)
    assert _tertanda(kon) == 2


def test_urutan_aman_berkas_dihapus_sebelum_bukti_ditandai(kon, folder, monkeypatch):
    _putuskan(kon, folder, 1)
    urutan = []
    asli_hapus, asli_tandai = pr.bukti_berkas.hapus_berkas, pr.pesanan_transfer.tandai_dihapus
    monkeypatch.setattr(pr.bukti_berkas, "hapus_berkas",
                        lambda *a, **k: (urutan.append("hapus"), asli_hapus(*a, **k))[1])
    monkeypatch.setattr(pr.pesanan_transfer, "tandai_dihapus",
                        lambda *a, **k: (urutan.append("tandai"), asli_tandai(*a, **k))[1])
    pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert urutan == ["hapus", "tandai"]


def test_tandai_gagal_setelah_berkas_terhapus_dilanjutkan_pada_sapu_berikutnya(kon, folder, monkeypatch):
    _putuskan(kon, folder, 1)
    asli = pr.pesanan_transfer.tandai_dihapus

    def gagal(*_a, **_k):
        raise sqlite3.OperationalError("database terkunci")

    monkeypatch.setattr(pr.pesanan_transfer, "tandai_dihapus", gagal)
    pertama = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (pertama.berkas_dihapus, pertama.ditandai, pertama.gagal) == (1, 0, 1)
    monkeypatch.setattr(pr.pesanan_transfer, "tandai_dihapus", asli)
    kedua = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (kedua.ditandai, kedua.berkas_sudah_hilang, kedua.gagal) == (1, 1, 0)


def test_gagal_hapus_berkas_tidak_menandai_dan_tidak_menghentikan_yang_lain(kon, folder, monkeypatch):
    _putuskan(kon, folder, 1)
    _putuskan(kon, folder, 2)
    asli = pr.bukti_berkas.hapus_berkas

    def selektif(nama, folder_=None):
        if nama == berkas(1):
            raise PermissionError("izin ditolak")
        return asli(nama, folder_)

    monkeypatch.setattr(pr.bukti_berkas, "hapus_berkas", selektif)
    hasil = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (hasil.ditandai, hasil.berkas_dihapus, hasil.gagal) == (1, 1, 1)
    assert (folder / berkas(1)).exists() and _tertanda(kon) == 1
    assert [b["berkas"] for b in tf.bukti_kedaluwarsa(kon, SESUDAH_30_HARI)] == [berkas(1)]


def test_nama_berkas_tersimpan_rusak_dihitung_gagal_bukan_macet(kon, folder, monkeypatch):
    _putuskan(kon, folder, 1)
    monkeypatch.setattr(pr.pesanan_transfer, "bukti_kedaluwarsa", lambda *_a, **_k: (
        {"bukti_id": 1, "order_id": "ord_" + "0" * 32, "berkas": "../luar"},))
    hasil = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert (hasil.gagal, hasil.ditandai) == (1, 0)


def test_folder_tidak_ada_dengan_bukti_kedaluwarsa_tidak_menandai_apa_pun(kon, folder, tmp_path):
    _putuskan(kon, folder, 1)
    salah = tmp_path / "folder-salah-tidak-ada"
    hasil = pr.sapu(kon, salah, SESUDAH_30_HARI)
    assert (hasil.gagal, hasil.ditandai, hasil.berkas_sudah_hilang, hasil.berkas_dihapus) == (1, 0, 0, 0)
    assert _tertanda(kon) == 0 and (folder / berkas(1)).exists() and not salah.exists()
    assert pr.sapu(kon, folder, SESUDAH_30_HARI).ditandai == 1            # folder benar: selesai normal


def test_hari_lebih_pendek_diteruskan_ke_penandaan(kon, folder):
    _putuskan(kon, folder, 1)
    hasil = pr.sapu(kon, folder, SEBELUM_30_HARI, hari=29)
    assert (hasil.ditandai, hasil.berkas_dihapus, hasil.gagal) == (1, 1, 0)
    assert _tertanda(kon) == 1


# --- sisa sementara ------------------------------------------------------------

def test_sisa_sementara_lama_dibuang_yang_baru_dan_bukan_sementara_tidak(kon, folder):
    lama = _lama(folder, ".tmp-" + "a" * 32)
    baru = _lama(folder, ".tmp-" + "b" * 32, selisih_detik=60)
    biasa = _lama(folder, "c" * 32)
    hasil = pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert hasil.sementara_dibersihkan == 1
    assert not lama.exists() and baru.exists() and biasa.exists()


def test_ambang_sementara_tepat_satu_jam(kon, folder):
    tepat = _lama(folder, ".tmp-" + "a" * 32, selisih_detik=pr.UMUR_SEMENTARA_DETIK)
    kurang = _lama(folder, ".tmp-" + "b" * 32, selisih_detik=pr.UMUR_SEMENTARA_DETIK - 1)
    pr.sapu(kon, folder, SESUDAH_30_HARI)
    assert not tepat.exists() and kurang.exists()


def test_sisa_sementara_bukan_berkas_biasa_tidak_disentuh(kon, folder, tmp_path):
    luar = tmp_path / "luar.txt"
    luar.write_bytes(b"rahasia")
    tautan = folder / (".tmp-" + "d" * 32)
    os.symlink(luar, tautan)
    direktori = folder / (".tmp-" + "e" * 32)
    direktori.mkdir()
    hasil = pr.sapu(kon, folder, "2099-01-01T00:00:00")
    assert hasil.sementara_dibersihkan == 0
    assert luar.read_bytes() == b"rahasia" and os.path.islink(tautan) and direktori.is_dir()


def test_folder_tidak_ada_nol_tanpa_galat_dan_tidak_dibuat(kon, tmp_path):
    ada_nanti = tmp_path / "belum-ada"
    hasil = pr.sapu(kon, ada_nanti, SESUDAH_30_HARI)
    assert (hasil.sementara_dibersihkan, hasil.gagal) == (0, 0) and not ada_nanti.exists()


# --- CLI -----------------------------------------------------------------------

def test_cli_menyapu_dan_mencetak_ringkasan_tanpa_nama_berkas(db, folder, capsys):
    with tf.buka(db, tulis_data=True) as kon:
        _putuskan(kon, folder, 1)
        _lama(folder, ".tmp-" + "f" * 32)
    kode = pr.main(["--database", str(db), "--folder", str(folder)], sekarang=SESUDAH_30_HARI)
    keluar = capsys.readouterr().out
    assert kode == 0 and "1 bukti ditandai" in keluar and "1 sisa sementara" in keluar
    assert berkas(1) not in keluar
    assert not (folder / berkas(1)).exists()


def test_cli_folder_bawaan_di_samping_db(db, capsys):
    bawaan = db.parent / "bukti-transfer"
    bawaan.mkdir()
    with tf.buka(db, tulis_data=True) as kon:
        _putuskan(kon, bawaan, 1)
    assert pr.main(["--database", str(db)], sekarang=SESUDAH_30_HARI) == 0
    assert not (bawaan / berkas(1)).exists()


def test_cli_folder_dari_env_bila_tidak_ada_opsi(db, folder, monkeypatch):
    monkeypatch.setenv("OSN_DIREKTORI_BUKTI", str(folder))
    with tf.buka(db, tulis_data=True) as kon:
        _putuskan(kon, folder, 1)
    assert pr.main(["--database", str(db)], sekarang=SESUDAH_30_HARI) == 0
    assert not (folder / berkas(1)).exists()


def test_cli_folder_salah_dengan_bukti_kedaluwarsa_keluar_1_dan_ledger_utuh(db, folder, tmp_path, capsys):
    with tf.buka(db, tulis_data=True) as kon:
        _putuskan(kon, folder, 1)
    kode = pr.main(["--database", str(db), "--folder", str(tmp_path / "salah")], sekarang=SESUDAH_30_HARI)
    keluar = capsys.readouterr()
    assert kode == pr.EXIT_SEBAGIAN and "1 gagal" in keluar.out and "OSN_DIREKTORI_BUKTI" in keluar.err
    with tf.buka(db) as kon:
        assert _tertanda(kon) == 0
    assert (folder / berkas(1)).exists()


def test_cli_db_tidak_ada_atau_tanpa_transfer_gagal_ramah_tanpa_efek(tmp_path, capsys):
    assert pr.main(["--database", str(tmp_path / "tidak-ada.db")], sekarang=SESUDAH_30_HARI) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert not (tmp_path / "tidak-ada.db").exists()


def test_cli_mewajibkan_database(capsys):
    with pytest.raises(SystemExit) as galat:
        pr.main([], sekarang=SESUDAH_30_HARI)
    assert galat.value.code == 2


def test_sapu_memakai_jam_suntikan_bukan_jam_dinding_untuk_ambang(kon, folder):
    baru_menurut_jam_suntikan = _lama(folder, ".tmp-" + "a" * 32, sekarang="2020-01-01T00:00:00",
                                      selisih_detik=60)
    pr.sapu(kon, folder, "2020-01-01T00:00:00")
    assert baru_menurut_jam_suntikan.exists()      # jam dinding menganggapnya berumur bertahun-tahun
