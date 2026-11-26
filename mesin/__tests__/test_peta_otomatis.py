"""Penerbitan otomatis laporan Peta Kemampuan setelah lunas, tanpa Guru (data sintetis di basis sementara).

Tes memeriksa KEADAAN database (baris laporan, catatan purna, ledger), bukan hanya nilai kembalian. Tiap guard punya
tes berdiri sendiri: fungsi murni `izin_bila_sah` atau ledger yang dipalsukan lewat `po`, supaya mutasi satu guard
tidak tertutup guard lain. Sasaran mutation: `test_peta_otomatis_mutation.py`.
"""
from __future__ import annotations

import calendar
import contextlib
import logging
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import cek_gratis  # noqa: E402
import cek_gratis_sapu  # noqa: E402
import cek_ringkasan_admin  # noqa: E402
import database  # noqa: E402
import peta_laporan_snapshot as snapshot  # noqa: E402
import peta_laporan_store as toko  # noqa: E402
import peta_otomatis as otomatis  # noqa: E402
import pesanan  # noqa: E402
import pesanan_admin_order as po  # noqa: E402
import pesanan_dasar as d  # noqa: E402
import pesanan_kit  # noqa: E402
import pesanan_transfer as tf  # noqa: E402
import purna  # noqa: E402
from cek_gratis_kit import ID_A, ID_B, SEKARANG, jawab, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402
from purna_kit import WAKTU_SETUJU, refund_mentah, siapkan_db_purna  # noqa: E402
from transfer_kit import ADMIN, siapkan_db_transfer, unggah  # noqa: E402

PEMILIK, PEMILIK_LAIN = "guru-a", "guru-b"
NAMA_ANAK, NAMA_PENGGANJAL = "Anak Sintetis Otomatis", "Anak Pengganjal"
BENAR_CAMPURAN = {"berhitung-sekolah": 5, "pengukuran": 2, "geometri-datar": 0}  # 7 dari 15 = skor 47
SELESAI_SESI = "2026-11-18 09:00:00"
SETELAH = "2026-11-18T13:00:00"        # sesudah lunas QRIS (10:00) dan transfer disetujui (12:00)
SETELAH_NANTI = "2026-11-18T15:00:00"
EPOCH_SETELAH = calendar.timegm((2026, 11, 18, 13, 0, 0))
TERBIT_UTC = "2026-11-18T13:00:00"     # waktu terbit laporan dalam UTC (= SETELAH)
TERBIT_WIB = "2026-11-18 20:00:00"     # waktu terbit laporan tersimpan (WIB)
AKHIR_RETENSI = "2026-12-18T09:00:01"  # selesai + 30 hari, lewat sapuan
KEDALUWARSA = "2026-11-19T10:00:01"
ORDER_ID = pesanan_kit.ord_id(1)
CATATAN_GURU = "Catatan Guru sintetis untuk uji: latih pengukuran tiga kali seminggu."
JALUR_LUNAS = ("qris", "transfer")


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    """Ledger admin sintetis dengan namespace pesanan, transfer, dan purna; dijadikan BAWAAN."""
    jalur = siapkan_db_purna(tmp_path)
    monkeypatch.setattr(admin_store, "BAWAAN", jalur)
    return jalur


@pytest.fixture()
def ledger_tanpa_purna(tmp_path, monkeypatch):
    jalur = siapkan_db_transfer(tmp_path)
    monkeypatch.setattr(admin_store, "BAWAAN", jalur)
    return jalur


@pytest.fixture()
def belajar(tmp_path, monkeypatch):
    """DB belajar sintetis; dijadikan BAWAAN supaya database.buka() tanpa argumen memakai berkas ini."""
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    with database.buka(jalur) as kon:
        yield kon


def _jalur_belajar(kon):
    return kon.execute("PRAGMA database_list").fetchone()[2]


def _anak_dengan_cek(kon, *, selesai=True):
    """Anak berid 2 dengan cek berid 1 (id beda supaya kunci yang tertukar terlihat). Cek dinilai bila `selesai`."""
    tambah_anak(kon, NAMA_PENGGANJAL, PEMILIK, 4)
    anak = tambah_anak(kon, NAMA_ANAK, PEMILIK, 4)
    sesi = mulai_cek(kon, ID_A, anak, PEMILIK)
    jawab(kon, sesi, BENAR_CAMPURAN)
    if selesai:
        tandai_selesai(kon, sesi, SELESAI_SESI)
        assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
    cek_id = kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]
    kon.commit()
    assert anak != cek_id
    return anak, cek_id


def _order_lunas_qris(anak, cek_id, n=1):
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_kit.buat(kon, n, akun=ID_A, siswa=anak, cek_id=cek_id)
        pesanan_kit.terapkan(kon, order, n)
    return order["order_id"]


def _order_lunas_transfer(anak, cek_id, n=1):
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_kit.buat(kon, n, akun=ID_A, siswa=anak, cek_id=cek_id)
        tf.buat_tagihan_transfer(kon, order["order_id"], ID_A, SEKARANG)
        unggah(kon, order, n, akun=ID_A)
        tf.setujui(kon, order["order_id"], ADMIN, WAKTU_SETUJU)
    return order["order_id"]


_BUAT_LUNAS = {"qris": _order_lunas_qris, "transfer": _order_lunas_transfer}


def _lunas(kon, jalur="qris"):
    """Anak + cek + order lunas (jalur QRIS atau transfer) -> (anak, cek_id, order_id)."""
    anak, cek_id = _anak_dengan_cek(kon)
    return anak, cek_id, _BUAT_LUNAS[jalur](anak, cek_id)


def _order_belum_bayar(anak, cek_id):
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return pesanan_kit.buat(kon, 1, akun=ID_A, siswa=anak, cek_id=cek_id)["order_id"]


def _draf_guru(kon, anak, cek_id, catatan=""):
    isi = snapshot.bangun(cek_ringkasan_admin.ringkasan_untuk_order(kon, anak, cek_id, ID_A, SETELAH))
    toko.buat_draf(kon, anak, PEMILIK, isi, EPOCH_SETELAH)
    if catatan:
        toko.simpan_catatan(kon, anak, catatan)
    kon.commit()


def _terbit_guru(kon, anak, cek_id, oleh=PEMILIK_LAIN, catatan=CATATAN_GURU):
    _draf_guru(kon, anak, cek_id, catatan)
    toko.terbitkan(kon, anak, oleh, EPOCH_SETELAH)
    kon.commit()


def _jumlah(kon, tabel):
    return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def _baris_laporan(kon, anak):
    return kon.execute(
        "SELECT guru, diterbitkan, diterbitkan_oleh, catatan FROM peta_laporan WHERE siswa_id = ?", (anak,),
    ).fetchone()


def _purna_terbit(ledger_path):
    with pesanan.buka(ledger_path) as kon:
        return [tuple(r) for r in kon.execute(
            "SELECT order_id, terbit, dicatat_oleh FROM purna_laporan_terbit ORDER BY order_id")]


# --- konstanta dan catatan sistem --------------------------------------------------------------

def test_catatan_sistem_lolos_aturan_penyimpanan_dan_terbit():
    assert toko.periksa_catatan(otomatis.CATATAN_SISTEM) is None
    assert toko.catatan_cukup_untuk_terbit(otomatis.CATATAN_SISTEM) is True


@pytest.mark.parametrize("potongan", ["guru", "http", "www", "@", "wa.me", "kode diagnosis", "malrule"])
def test_catatan_sistem_bebas_nama_guru_kontak_dan_istilah_internal(potongan):
    assert potongan not in otomatis.CATATAN_SISTEM.lower()


def test_pelaku_sistem_sah_menurut_aturan_pelaku_pesanan():
    assert otomatis.PELAKU_SISTEM == "sistem"
    d.periksa_pelaku(otomatis.PELAKU_SISTEM)


# --- izin_bila_sah (murni): satu guard per kasus ---------------------------------------------

ORDER_LUNAS = {"order_id": ORDER_ID, "siswa_id": 2, "cek_id": 1, "akun_id": ID_A,
               "status": d.STATUS_SUDAH_DIBAYAR}
PURNA_LUNAS = {"terpasang": True, "lunas": True, "direfund": False, "ditahan": False, "terbit": None}


def _ubah(dasar, **ganti):
    return {**dasar, **ganti}


def test_izin_bila_sah_mengembalikan_lima_kunci_dari_order():
    izin = otomatis.izin_bila_sah(ORDER_LUNAS, PURNA_LUNAS, ID_A)
    assert izin == {"order_id": ORDER_ID, "siswa_id": 2, "cek_id": 1, "akun_id": ID_A, "terbit": None}


def test_izin_bila_sah_tanpa_id_akun_tidak_memeriksa_akun():
    assert otomatis.izin_bila_sah(ORDER_LUNAS, PURNA_LUNAS) is not None


def test_izin_bila_sah_meneruskan_waktu_terbit_dari_purna():
    izin = otomatis.izin_bila_sah(ORDER_LUNAS, _ubah(PURNA_LUNAS, terbit=TERBIT_UTC), ID_A)
    assert izin["terbit"] == TERBIT_UTC


@pytest.mark.parametrize("order, purna, id_akun", [
    pytest.param(_ubah(ORDER_LUNAS, akun_id=ID_B), PURNA_LUNAS, ID_A, id="akun-tidak-cocok"),
    pytest.param(_ubah(ORDER_LUNAS, status=d.STATUS_BELUM_BAYAR), PURNA_LUNAS, ID_A, id="status-belum-bayar"),
    pytest.param(_ubah(ORDER_LUNAS, status=d.STATUS_PERLU_DIPERIKSA), PURNA_LUNAS, ID_A,
                 id="status-perlu-diperiksa-purna-bersih"),
    pytest.param(_ubah(ORDER_LUNAS, status=d.STATUS_DIREFUND), PURNA_LUNAS, ID_A,
                 id="status-direfund-purna-bersih"),
    pytest.param(_ubah(ORDER_LUNAS, status=d.STATUS_KEDALUWARSA), PURNA_LUNAS, ID_A, id="status-kedaluwarsa"),
    pytest.param(ORDER_LUNAS, _ubah(PURNA_LUNAS, direfund=True), ID_A, id="purna-direfund-status-lunas"),
    pytest.param(ORDER_LUNAS, _ubah(PURNA_LUNAS, ditahan=True), ID_A, id="purna-ditahan-status-lunas"),
    pytest.param(ORDER_LUNAS, _ubah(PURNA_LUNAS, terpasang=False), ID_A, id="purna-tak-terpasang-lunas"),
    pytest.param(ORDER_LUNAS, _ubah(PURNA_LUNAS, lunas=False), ID_A, id="purna-belum-lunas"),
])
def test_izin_bila_sah_menolak_bila_satu_guard_gagal(order, purna, id_akun):
    assert otomatis.izin_bila_sah(order, purna, id_akun) is None


# --- baca_izin: ledger admin read-only -------------------------------------------------------

def test_baca_izin_order_lunas_qris_mengembalikan_kunci_dari_ledger(belajar, ledger):
    anak, cek_id, order_id = _lunas(belajar, "qris")
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    assert izin == {"order_id": order_id, "siswa_id": anak, "cek_id": cek_id, "akun_id": ID_A, "terbit": None}


def test_baca_izin_order_lunas_transfer_disetujui(belajar, ledger):
    anak, cek_id, order_id = _lunas(belajar, "transfer")
    assert otomatis.baca_izin(anak, SETELAH, ID_A)["order_id"] == order_id


def test_baca_izin_menutup_ledger_sebelum_kembali(ledger, monkeypatch):
    _order_lunas_qris(2, 1)
    buka_asli = pesanan.buka
    terbuka = []

    @contextlib.contextmanager
    def catat(path, *, tulis_data=False):
        with buka_asli(path, tulis_data=tulis_data) as kon:
            terbuka.append(kon)
            yield kon

    monkeypatch.setattr(pesanan, "buka", catat)
    assert otomatis.baca_izin(2, SETELAH, ID_A) is not None
    with pytest.raises(sqlite3.ProgrammingError):
        terbuka[0].execute("SELECT 1")


@pytest.mark.parametrize("siswa_id", [0, True, "2", 99], ids=["nol", "bool", "teks", "tanpa-order"])
def test_baca_izin_none_bila_siswa_tak_sah_atau_tanpa_order(ledger, siswa_id):
    _order_lunas_qris(2, 1)
    assert otomatis.baca_izin(siswa_id, SETELAH, ID_A) is None


def test_baca_izin_none_bila_waktu_tak_sah(ledger):
    _order_lunas_qris(2, 1)
    assert otomatis.baca_izin(2, "bukan-waktu", ID_A) is None


def test_baca_izin_none_bila_order_belum_bayar(ledger):
    _order_belum_bayar(2, 1)
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None


def test_baca_izin_none_bila_sudah_kedaluwarsa_sebelum_lunas(ledger):
    _order_belum_bayar(2, 1)
    assert otomatis.baca_izin(2, KEDALUWARSA, ID_A) is None


def test_baca_izin_none_bila_akun_lain(ledger):
    _order_lunas_qris(2, 1)
    assert otomatis.baca_izin(2, SETELAH, ID_B) is None


def test_baca_izin_none_bila_direfund(ledger):
    order_id = _order_lunas_qris(2, 1)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        refund_mentah(kon, order_id)
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None


def test_baca_izin_none_bila_ditahan_karena_refund_penyedia(ledger):
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_kit.buat(kon, 1, akun=ID_A, siswa=2, cek_id=1)
        pesanan_kit.terapkan(kon, order, 1)
        pesanan_kit.terapkan(kon, order, 2, transaction_status="refund", transaction_id="trx-sintetis-tahan")
        status = po.order_peta_untuk_siswa(kon, 2, SETELAH)["status"]
    assert status == d.STATUS_PERLU_DIPERIKSA
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None


def test_baca_izin_none_walau_status_sudah_dibayar_bila_purna_menahan(ledger, monkeypatch):
    _order_lunas_qris(2, 1)
    asli = po.purna_ringkas
    monkeypatch.setattr(po, "purna_ringkas", lambda kon, oid, sekarang: _ubah(asli(kon, oid, sekarang), ditahan=True))
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None


def test_baca_izin_none_bila_purna_belum_terpasang(ledger_tanpa_purna):
    _order_lunas_qris(2, 1)
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None


def test_baca_izin_none_bila_ledger_tak_ada_dan_tidak_membuat_berkas(tmp_path, monkeypatch):
    jalur = tmp_path / "tidak-ada.db"
    monkeypatch.setattr(admin_store, "BAWAAN", jalur)
    assert otomatis.baca_izin(2, SETELAH, ID_A) is None
    assert not jalur.exists()


# --- terbitkan_bila_siap: DB belajar --------------------------------------------------------

def test_terbit_sah_menulis_laporan_sistem_dalam_satu_baris(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.TERBIT
    guru, diterbitkan, oleh, catatan = _baris_laporan(belajar, anak)
    assert (guru, diterbitkan, oleh, catatan) == ("sistem", TERBIT_WIB, "sistem", otomatis.CATATAN_SISTEM)
    laporan = toko.ambil(belajar, anak)
    assert (laporan["isi"]["skor"], laporan["isi"]["jumlah_soal"], laporan["isi"]["kelas"]) == (47, 15, 4)


def test_terbit_memakai_cek_dari_order_bukan_id_anak(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    assert izin["cek_id"] == cek_id != anak
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.TERBIT


def test_terbit_kedua_hasil_sudah_ada_tanpa_baris_baru(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    otomatis.terbitkan_bila_siap(belajar, izin, SETELAH)
    awal = _baris_laporan(belajar, anak)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH_NANTI) == otomatis.SUDAH_ADA
    assert _jumlah(belajar, "peta_laporan") == 1
    assert _baris_laporan(belajar, anak) == awal


def test_draf_guru_belum_terbit_tidak_disentuh(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    _draf_guru(belajar, anak, cek_id)
    awal = _baris_laporan(belajar, anak)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.SUDAH_ADA
    assert _baris_laporan(belajar, anak) == awal
    assert _baris_laporan(belajar, anak)[:3] == (PEMILIK, None, None)


def test_draf_guru_dengan_bahan_dihapus_tetap_sudah_ada_tanpa_buat_draf(belajar, ledger, monkeypatch):
    anak, cek_id, _order = _lunas(belajar)
    _draf_guru(belajar, anak, cek_id)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    cek_gratis_sapu.sapu_cek_gratis(belajar, AKHIR_RETENSI, frozenset({ID_A}))
    belajar.commit()
    monkeypatch.setattr(toko, "buat_draf", lambda *a, **k: pytest.fail("buat_draf tidak boleh dipanggil"))
    assert otomatis.terbitkan_bila_siap(belajar, izin, AKHIR_RETENSI) == otomatis.SUDAH_ADA
    assert _baris_laporan(belajar, anak)[:3] == (PEMILIK, None, None)


def test_bahan_dihapus_tanpa_draf_tidak_menulis_apa_pun(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    cek_gratis_sapu.sapu_cek_gratis(belajar, AKHIR_RETENSI, frozenset({ID_A}))
    belajar.commit()
    izin = otomatis.baca_izin(anak, AKHIR_RETENSI, ID_A)
    assert otomatis.terbitkan_bila_siap(belajar, izin, AKHIR_RETENSI) == otomatis.BAHAN_BELUM
    assert _jumlah(belajar, "peta_laporan") == 0


def test_cek_belum_selesai_dinilai_tidak_terbit(belajar, ledger):
    anak, cek_id = _anak_dengan_cek(belajar, selesai=False)
    _order_lunas_qris(anak, cek_id)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    assert izin is not None
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.BAHAN_BELUM
    assert _baris_laporan(belajar, anak) is None


def test_izin_kosong_tidak_menulis_dan_menolak(belajar, ledger):
    assert otomatis.terbitkan_bila_siap(belajar, None, SETELAH) == otomatis.TIDAK_LAYAK
    assert _jumlah(belajar, "peta_laporan") == 0


@pytest.mark.parametrize("langkah", ["buat_draf", "simpan_catatan", "terbitkan"])
@pytest.mark.parametrize("galat", [ValueError("gagal sintetis"), sqlite3.OperationalError("terkunci sintetis")],
                         ids=["valueerror", "sqlite-error"])
def test_galat_di_tengah_transaksi_batal_seluruhnya_tanpa_draf_yatim(belajar, ledger, monkeypatch, langkah, galat):
    anak, _cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)

    def gagal(*_args, **_kwargs):
        raise galat

    monkeypatch.setattr(toko, langkah, gagal)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.GAGAL
    assert _jumlah(belajar, "peta_laporan") == 0
    assert belajar.in_transaction is False


def test_commit_gagal_setelah_tulis_tetap_batal_tanpa_draf_yatim(belajar, ledger, monkeypatch):
    """`d.tulis` tidak rollback bila commit sendiri gagal; pembatalan di `_hasil_setelah_batal` yang menutupnya."""
    anak, _cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)

    @contextlib.contextmanager
    def tulis_commit_gagal(kon):
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        raise sqlite3.OperationalError("commit sintetis gagal")

    monkeypatch.setattr(d, "tulis", tulis_commit_gagal)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.GAGAL
    assert _jumlah(belajar, "peta_laporan") == 0
    assert belajar.in_transaction is False


def test_koneksi_dalam_transaksi_ditolak_tanpa_menulis_dan_tanpa_rollback(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    belajar.execute("BEGIN IMMEDIATE")
    belajar.execute("UPDATE siswa SET nama = ? WHERE id = ?", ("Nama Sementara", anak))
    assert belajar.in_transaction is True
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.GAGAL
    assert belajar.in_transaction is True
    assert belajar.execute("SELECT nama FROM siswa WHERE id = ?", (anak,)).fetchone()[0] == "Nama Sementara"
    assert _jumlah(belajar, "peta_laporan") == 0
    belajar.commit()
    assert belajar.execute("SELECT nama FROM siswa WHERE id = ?", (anak,)).fetchone()[0] == "Nama Sementara"


def test_penerbit_lain_di_sela_pemeriksaan_hasilkan_sudah_ada(belajar, ledger, monkeypatch):
    anak, cek_id, _order = _lunas(belajar)
    izin = otomatis.baca_izin(anak, SETELAH, ID_A)
    jalur = _jalur_belajar(belajar)
    asli = cek_ringkasan_admin.ringkasan_untuk_order

    def sisipkan_draf_penerbit_lain(kon, siswa_id, cek, akun, sekarang):
        hasil = asli(kon, siswa_id, cek, akun, sekarang)
        with database.buka(jalur) as lain:
            toko.buat_draf(lain, siswa_id, PEMILIK_LAIN, snapshot.bangun(hasil), EPOCH_SETELAH)
        return hasil

    monkeypatch.setattr(cek_ringkasan_admin, "ringkasan_untuk_order", sisipkan_draf_penerbit_lain)
    assert otomatis.terbitkan_bila_siap(belajar, izin, SETELAH) == otomatis.SUDAH_ADA
    assert _baris_laporan(belajar, anak)[:3] == (PEMILIK_LAIN, None, None)


# --- catat_purna_sistem ------------------------------------------------------------------

def test_catat_purna_sistem_mencatat_waktu_terbit_utc_dan_pelaku_sistem(belajar, ledger):
    _lunas(belajar)
    assert otomatis.catat_purna_sistem(ORDER_ID, TERBIT_WIB) is True
    assert _purna_terbit(ledger) == [(ORDER_ID, TERBIT_UTC, "sistem")]


def test_catat_purna_sistem_idempoten(belajar, ledger):
    _lunas(belajar)
    otomatis.catat_purna_sistem(ORDER_ID, TERBIT_WIB)
    assert otomatis.catat_purna_sistem(ORDER_ID, TERBIT_WIB) is True
    assert len(_purna_terbit(ledger)) == 1


def test_catat_purna_sistem_false_tanpa_melempar_bila_gagal(belajar, ledger, monkeypatch, caplog):
    _lunas(belajar)

    def gagal(*_args, **_kwargs):
        raise RuntimeError("rahasia-sintetis")

    monkeypatch.setattr(purna, "catat_terbit", gagal)
    with caplog.at_level(logging.WARNING):
        assert otomatis.catat_purna_sistem(ORDER_ID, TERBIT_WIB) is False
    assert "RuntimeError" in caplog.text
    assert "rahasia-sintetis" not in caplog.text and ORDER_ID not in caplog.text
    assert _purna_terbit(ledger) == []


def test_catat_purna_sistem_false_bila_purna_belum_terpasang(belajar, ledger_tanpa_purna):
    _order_lunas_qris(2, 1)
    assert otomatis.catat_purna_sistem(ORDER_ID, TERBIT_WIB) is False


# --- pastikan_untuk_siswa (halaman orang tua) -------------------------------------------

@pytest.mark.parametrize("jalur", JALUR_LUNAS)
def test_pastikan_menerbitkan_laporan_dan_mencatat_purna(belajar, ledger, jalur):
    anak, _cek_id, order_id = _lunas(belajar, jalur)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH) == otomatis.TERBIT
    assert _baris_laporan(belajar, anak)[2] == "sistem"
    assert _purna_terbit(ledger) == [(order_id, TERBIT_UTC, "sistem")]


def test_pastikan_dua_kali_satu_laporan_dan_satu_catatan_purna(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH)
    awal = _baris_laporan(belajar, anak)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH_NANTI) == otomatis.SUDAH_ADA
    assert _jumlah(belajar, "peta_laporan") == 1
    assert len(_purna_terbit(ledger)) == 1
    assert _baris_laporan(belajar, anak) == awal


def test_pastikan_gagal_purna_laporan_tetap_terbit_lalu_sinkron_pada_panggilan_berikut(belajar, ledger, monkeypatch):
    anak, _cek_id, order_id = _lunas(belajar)
    asli = purna.catat_terbit
    panggilan = []

    def gagal_sekali(kon, oid, pelaku, waktu):
        panggilan.append(waktu)
        if len(panggilan) == 1:
            raise sqlite3.OperationalError("terkunci sintetis")
        return asli(kon, oid, pelaku, waktu)

    monkeypatch.setattr(purna, "catat_terbit", gagal_sekali)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH) == otomatis.TERBIT
    assert _jumlah(belajar, "peta_laporan") == 1
    assert _purna_terbit(ledger) == []
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH_NANTI) == otomatis.SUDAH_ADA
    assert _purna_terbit(ledger) == [(order_id, TERBIT_UTC, "sistem")]


def test_pastikan_laporan_guru_terbit_tidak_diubah_dan_tanpa_catatan_purna(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    _terbit_guru(belajar, anak, cek_id)
    awal = _baris_laporan(belajar, anak)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH) == otomatis.SUDAH_ADA
    assert _baris_laporan(belajar, anak) == awal
    assert _purna_terbit(ledger) == []


def _order_direfund(anak, cek_id):
    order_id = _order_lunas_qris(anak, cek_id)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        refund_mentah(kon, order_id)


def _order_ditahan(anak, cek_id):
    """Order lunas QRIS lalu observasi refund penyedia: status perlu_diperiksa, voucher ditahan."""
    order_id = _order_lunas_qris(anak, cek_id)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan_kit.terapkan(kon, {"order_id": order_id}, 2, transaction_status="refund",
                             transaction_id="trx-sintetis-tahan")


@pytest.mark.parametrize("siapkan, sekarang", [
    pytest.param(_order_belum_bayar, SETELAH, id="belum-bayar"),
    pytest.param(_order_belum_bayar, KEDALUWARSA, id="kedaluwarsa"),
    pytest.param(_order_direfund, SETELAH, id="direfund"),
    pytest.param(_order_ditahan, SETELAH, id="ditahan"),
])
def test_pastikan_keadaan_belum_layak_tanpa_efek(belajar, ledger, siapkan, sekarang):
    anak, cek_id = _anak_dengan_cek(belajar)
    siapkan(anak, cek_id)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, sekarang) == otomatis.TIDAK_LAYAK
    assert _jumlah(belajar, "peta_laporan") == 0
    assert _purna_terbit(ledger) == []


def test_pastikan_akun_lain_tidak_layak_tanpa_efek(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_B, anak, SETELAH) == otomatis.TIDAK_LAYAK
    assert _jumlah(belajar, "peta_laporan") == 0
    assert _purna_terbit(ledger) == []


def test_pastikan_purna_belum_terpasang_tidak_layak_tanpa_efek(belajar, ledger_tanpa_purna):
    anak, _cek_id = _anak_dengan_cek(belajar)
    _order_lunas_qris(anak, _cek_id)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH) == otomatis.TIDAK_LAYAK
    assert _jumlah(belajar, "peta_laporan") == 0


def test_pastikan_tidak_melempar_galat_tak_terduga(belajar, ledger, monkeypatch):
    anak, _cek_id, _order = _lunas(belajar)

    def meledak(*_args, **_kwargs):
        raise RuntimeError("rusak sintetis")

    monkeypatch.setattr(otomatis, "terbitkan_bila_siap", meledak)
    assert otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH) == otomatis.GAGAL


# --- setelah_lunas (pemicu pembayaran) ---------------------------------------------------

@pytest.mark.parametrize("jalur", JALUR_LUNAS)
def test_setelah_lunas_menerbitkan_dan_mencatat_purna(belajar, ledger, jalur):
    anak, _cek_id, order_id = _lunas(belajar, jalur)
    assert otomatis.setelah_lunas(order_id, SETELAH) is None
    assert _baris_laporan(belajar, anak)[2] == "sistem"
    assert _purna_terbit(ledger) == [(order_id, TERBIT_UTC, "sistem")]


def _gagal_sintetis(*_args, **_kwargs):
    raise RuntimeError("rusak sintetis")


@pytest.mark.parametrize("rusak", ["kunci_cek", "ledger", "belajar", "purna"])
def test_setelah_lunas_tidak_pernah_melempar(belajar, ledger, tmp_path, monkeypatch, rusak):
    anak, _cek_id, order_id = _lunas(belajar)
    if rusak == "kunci_cek":
        monkeypatch.setattr(po, "kunci_cek", _gagal_sintetis)
    elif rusak == "ledger":
        monkeypatch.setattr(admin_store, "BAWAAN", tmp_path / "tidak-ada.db")
    elif rusak == "belajar":
        monkeypatch.setattr(database, "BAWAAN", tmp_path)
    else:
        monkeypatch.setattr(purna, "catat_terbit", _gagal_sintetis)
    assert otomatis.setelah_lunas(order_id, SETELAH) is None
    if rusak == "purna":
        assert _baris_laporan(belajar, anak)[2] == "sistem"
    else:
        assert _jumlah(belajar, "peta_laporan") == 0


def test_setelah_lunas_order_tak_dikenal_tanpa_efek(belajar, ledger):
    assert otomatis.setelah_lunas(pesanan_kit.ord_id(99), SETELAH) is None
    assert _jumlah(belajar, "peta_laporan") == 0


# --- oleh_sistem -------------------------------------------------------------------------

def test_oleh_sistem_benar_untuk_laporan_yang_diterbitkan_sistem(belajar, ledger):
    anak, _cek_id, _order = _lunas(belajar)
    otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH)
    assert otomatis.oleh_sistem(belajar, anak) is True


def test_oleh_sistem_salah_untuk_laporan_guru_walau_catatannya_sama(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    _terbit_guru(belajar, anak, cek_id, catatan=otomatis.CATATAN_SISTEM)
    assert otomatis.oleh_sistem(belajar, anak) is False


def test_oleh_sistem_salah_untuk_draf_guru_dan_tanpa_laporan(belajar, ledger):
    anak, cek_id, _order = _lunas(belajar)
    assert otomatis.oleh_sistem(belajar, anak) is False
    _draf_guru(belajar, anak, cek_id)
    assert otomatis.oleh_sistem(belajar, anak) is False


def test_oleh_sistem_salah_bila_baca_laporan_gagal(belajar, ledger, monkeypatch):
    anak, _cek_id, _order = _lunas(belajar)
    otomatis.pastikan_untuk_siswa(belajar, ID_A, anak, SETELAH)

    def rusak(*_args, **_kwargs):
        raise ValueError("isi rusak sintetis")

    monkeypatch.setattr(toko, "ambil", rusak)
    assert otomatis.oleh_sistem(belajar, anak) is False
