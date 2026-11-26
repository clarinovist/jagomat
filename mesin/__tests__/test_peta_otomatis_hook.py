"""Pemicu penerbitan otomatis Peta (`peta_otomatis`): titik lunas (transfer, QRIS) dan halaman orang tua.

Tes memeriksa KEADAAN database (baris laporan, catatan purna, penilaian cek), bukan hanya kode status. Data sintetis di
DB sementara. Mutasi pemicu ada di `test_peta_otomatis_hook_mutation.py`.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import cek_gratis  # noqa: E402
import database  # noqa: E402
import orang_tua_data as data  # noqa: E402
import peta_laporan_store as toko  # noqa: E402
import peta_otomatis as otomatis  # noqa: E402
import pesanan  # noqa: E402
import pesanan_dasar as d  # noqa: E402
import pesanan_kit  # noqa: E402
import pesanan_transfer as tf  # noqa: E402
from admin_transfer_kit import SETUJUI, kirim_putusan, login_admin, order_menunggu, tabel  # noqa: E402
from cek_gratis_kit import ID_A, ID_B, SEKARANG, jawab, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402
from pesanan_http_kit import (  # noqa: E402,F401
    AKUN_A, PERIKSA, bayar, data_status, jam, keluarga, kirim, pesan, satu_order, server, settlement, siap_pesan,
    tertutup,
)
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from purna_http_kit import bayar_purna, transfer_purna  # noqa: E402,F401
from purna_kit import WAKTU_SETUJU  # noqa: E402
from test_peta_otomatis import (  # noqa: E402,F401
    BENAR_CAMPURAN, CATATAN_GURU, PEMILIK, PEMILIK_LAIN, SELESAI_SESI, SETELAH, _anak_dengan_cek, _baris_laporan,
    _draf_guru, _jumlah, _order_belum_bayar, _order_lunas_qris, _purna_terbit, _terbit_guru, ledger,
)
from transfer_kit import ADMIN, unggah  # noqa: E402

NAMA_SINTETIS = "Anak Sintetis Uji Hook"
POLA_HASIL = re.compile(r"hasil=([a-z_]+)")
ALASAN_TOLAK = "Nominal tidak sesuai"
PENGGANTI_GALAT = "galat sintetis pemicu"


@pytest.fixture()
def belajar(tmp_path, monkeypatch):
    """Path DB belajar sintetis; dijadikan BAWAAN supaya `database.buka()` tanpa argumen memakainya."""
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    return jalur


def _hasil(tajuk) -> str:
    cocok = POLA_HASIL.search(tajuk["Location"])
    assert cocok, tajuk["Location"]
    return cocok.group(1)


def _pemicu_meledak(monkeypatch) -> list:
    """Ganti pemicu dengan galat sintetis; mengembalikan daftar pemanggilannya."""
    panggilan = []

    def meledak(*args, **kwargs):
        panggilan.append(args)
        raise RuntimeError(PENGGANTI_GALAT)

    monkeypatch.setattr(otomatis, "_terbitkan_setelah_lunas", meledak)
    return panggilan


def _catat_pemicu(monkeypatch) -> list:
    """Bungkus pemicu Peta yang dipanggil kumpulkan: mencatat tiap pemanggilan lalu meneruskan ke pemicu asli."""
    panggilan = []
    asli = otomatis.pastikan_untuk_siswa

    def catat(*args, **kwargs):
        panggilan.append(args)
        return asli(*args, **kwargs)

    monkeypatch.setattr(otomatis, "pastikan_untuk_siswa", catat)
    return panggilan


def _hitung_laporan(jalur) -> int:
    with database.buka(jalur) as kon:
        return _jumlah(kon, "peta_laporan")


def _baris_mentah(kon, siswa_id) -> list:
    return [tuple(r) for r in kon.execute("SELECT * FROM peta_laporan WHERE siswa_id = ?", (siswa_id,))]


def _kumpulkan(jalur, siswa_id, akun=ID_A, sekarang=SETELAH):
    with database.buka(jalur) as kon:
        return data.kumpulkan(kon, akun, siswa_id, sekarang)


def _pesanan_qris(server):
    """Order QRIS sintetis yang sudah dibuat provider palsu: (baris order, transaksi)."""
    siap_pesan(server)
    pesan(server)
    order = satu_order()
    return order, server.provider.transaksi[order["order_id"]]


def _receipt(ledger_path, order_id) -> list:
    with pesanan.buka(ledger_path) as kon:
        return [tuple(r) for r in kon.execute("SELECT hasil FROM pesanan_receipt WHERE order_id = ?", (order_id,))]


def _anak_selesai_belum_dinilai(kon):
    """Anak dengan sesi selesai tetapi skor belum tersimpan: penilaian terjadi saat halaman dibuka."""
    anak = tambah_anak(kon, NAMA_SINTETIS, PEMILIK, 4)
    sesi = mulai_cek(kon, ID_A, anak, PEMILIK)
    jawab(kon, sesi, BENAR_CAMPURAN)
    tandai_selesai(kon, sesi, SELESAI_SESI)
    cek_id = kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]
    kon.commit()
    return anak, cek_id


# --- titik lunas: persetujuan transfer oleh admin -----------------------------------------------

def test_transfer_disetujui_menerbitkan_laporan_oleh_sistem_dan_purna(transfer_purna):
    # Arrange
    server = transfer_purna
    admin = login_admin(server)
    order_id = order_menunggu(server)
    # Act
    kode, _isi, tajuk = kirim_putusan(server, admin, SETUJUI, order_id)
    # Assert
    assert kode == 303 and _hasil(tajuk) == "verifikasi_setuju"
    (order,) = tabel("pesanan_order")
    with database.buka(server.db) as kon:
        laporan = _baris_laporan(kon, order["siswa_id"])
    assert laporan["diterbitkan_oleh"] == "sistem"
    assert laporan["catatan"] == otomatis.CATATAN_SISTEM
    assert [(oid, oleh) for oid, _terbit, oleh in _purna_terbit(admin_store.BAWAAN)] == [(order_id, "sistem")]


def test_pemicu_transfer_gagal_tidak_menggagalkan_persetujuan(transfer_purna, monkeypatch):
    # Arrange
    panggilan = _pemicu_meledak(monkeypatch)
    server = transfer_purna
    admin = login_admin(server)
    order_id = order_menunggu(server)
    # Act
    kode, _isi, tajuk = kirim_putusan(server, admin, SETUJUI, order_id)
    # Assert
    assert kode == 303 and _hasil(tajuk) == "verifikasi_setuju"
    assert [r["order_id"] for r in tabel("transfer_lunas")] == [order_id]
    assert panggilan, "pemicu harus dipanggil dari persetujuan"


# --- titik lunas: status QRIS (periksa) -------------------------------------------------------

def test_status_qris_lunas_menerbitkan_laporan_oleh_sistem(bayar_purna):
    order, trx = _pesanan_qris(bayar_purna)
    bayar_purna.provider.status_data = lambda oid: settlement(oid, trx)
    assert kirim(bayar_purna, PERIKSA, AKUN_A)[0] == 303
    with database.buka(bayar_purna.db) as kon:
        laporan = _baris_laporan(kon, order["siswa_id"])
    assert laporan["diterbitkan_oleh"] == "sistem"
    assert [(oid, oleh) for oid, _terbit, oleh in _purna_terbit(admin_store.BAWAAN)] == [(order["order_id"], "sistem")]


@pytest.mark.parametrize("ganti", [
    {"transaction_status": "pending"},
    {"transaction_status": "expire", "status_code": "407"},
])
def test_status_qris_belum_lunas_tidak_menerbitkan_laporan(bayar_purna, ganti):
    _order, trx = _pesanan_qris(bayar_purna)
    bayar_purna.provider.status_data = lambda oid: data_status(oid, trx, **ganti)
    assert kirim(bayar_purna, PERIKSA, AKUN_A)[0] == 303
    assert _hitung_laporan(bayar_purna.db) == 0
    assert _purna_terbit(admin_store.BAWAAN) == []


def test_pemicu_qris_gagal_tidak_menggagalkan_pembayaran(bayar_purna, monkeypatch):
    # Arrange
    panggilan = _pemicu_meledak(monkeypatch)
    order, trx = _pesanan_qris(bayar_purna)
    bayar_purna.provider.status_data = lambda oid: settlement(oid, trx)
    # Act
    assert kirim(bayar_purna, PERIKSA, AKUN_A)[0] == 303
    # Assert
    assert _receipt(admin_store.BAWAAN, order["order_id"]) == [("lunas",)]
    assert panggilan, "pemicu harus dipanggil dari status QRIS lunas"


# --- halaman orang tua: kumpulkan -------------------------------------------------------------

def test_kumpulkan_order_lunas_menerbitkan_laporan_sekali_dan_idempoten(ledger, belajar):
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
    order_id = _order_lunas_qris(anak, cek_id)
    hasil = _kumpulkan(belajar, anak)
    assert hasil.status_pesanan == d.STATUS_SUDAH_DIBAYAR
    assert hasil.peta["oleh_sistem"] is True
    assert hasil.peta["catatan"] == otomatis.CATATAN_SISTEM
    assert hasil.purna is not None and hasil.purna.terbit is not None  # purna sudah mencerminkan laporan baru
    assert _hitung_laporan(belajar) == 1
    assert [(oid, oleh) for oid, _terbit, oleh in _purna_terbit(ledger)] == [(order_id, "sistem")]
    kedua = _kumpulkan(belajar, anak)
    assert kedua.peta["oleh_sistem"] is True
    assert _hitung_laporan(belajar) == 1
    assert len(_purna_terbit(ledger)) == 1


def test_kumpulkan_akun_atau_anak_lain_tanpa_efek(ledger, belajar, monkeypatch):
    panggilan = _catat_pemicu(monkeypatch)
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
        anak_lain = tambah_anak(kon, "Anak Sintetis Lain", PEMILIK, 4)
    _order_lunas_qris(anak, cek_id)
    hasil_akun_lain = _kumpulkan(belajar, anak, akun=ID_B)
    hasil_anak_lain = _kumpulkan(belajar, anak_lain, akun=ID_A)
    assert panggilan == [], "pemicu tidak boleh dipanggil untuk akun atau anak yang bukan milik sesi"
    assert hasil_akun_lain.peta is None and hasil_anak_lain.peta is None
    assert _hitung_laporan(belajar) == 0
    assert _purna_terbit(ledger) == []
    with database.buka(belajar) as kon:
        assert _baris_mentah(kon, anak) == [] and _baris_mentah(kon, anak_lain) == []


def _order_ditahan(anak, cek_id):
    """Nominal provider tidak cocok: receipt perlu_diperiksa, status bukan sudah_dibayar."""
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_kit.buat(kon, 1, akun=ID_A, siswa=anak, cek_id=cek_id)
        pesanan_kit.terapkan(kon, order, 1, gross_amount="48000.00")
    return order["order_id"]


def _order_direfund(anak, cek_id):
    order_id = _order_lunas_qris(anak, cek_id)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan.catat_refund(kon, order_id, pesanan_kit.operasi(3), "admin_a", "kebijakan", SEKARANG)
    return order_id


def _order_ditolak(anak, cek_id):
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = pesanan_kit.buat(kon, 1, akun=ID_A, siswa=anak, cek_id=cek_id)
        tf.buat_tagihan_transfer(kon, order["order_id"], ID_A, SEKARANG)
        unggah(kon, order, 1, akun=ID_A)
        tf.tolak(kon, order["order_id"], ADMIN, ALASAN_TOLAK, WAKTU_SETUJU)
    return order["order_id"]


PEMBUAT_BELUM_LUNAS = {
    "belum_bayar": (_order_belum_bayar, d.STATUS_BELUM_BAYAR),
    "direfund": (_order_direfund, d.STATUS_DIREFUND),
    "ditolak": (_order_ditolak, d.STATUS_DITOLAK),
    "ditahan": (_order_ditahan, d.STATUS_PERLU_DIPERIKSA),
}


@pytest.mark.parametrize("jenis", sorted(PEMBUAT_BELUM_LUNAS))
def test_order_belum_lunas_tidak_menerbitkan_laporan(ledger, belajar, monkeypatch, jenis):
    # Arrange
    panggilan = _catat_pemicu(monkeypatch)
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
    pembuat, status_diharapkan = PEMBUAT_BELUM_LUNAS[jenis]
    pembuat(anak, cek_id)
    # Act
    hasil = _kumpulkan(belajar, anak)
    # Assert: status turunan memang belum lunas, dan kumpulkan tidak memanggil pemicu sama sekali
    assert data.status_pesanan(ID_A, anak, SETELAH) == status_diharapkan
    assert panggilan == []
    assert hasil.peta is None
    assert _hitung_laporan(belajar) == 0
    assert _purna_terbit(ledger) == []


def test_penilaian_cek_menggantung_tetap_tersimpan_setelah_kumpulkan(ledger, belajar):
    # Arrange: sesi selesai tetapi belum dinilai; penilaian dilakukan oleh kumpulkan
    with database.buka(belajar) as kon:
        anak, _cek_id = _anak_selesai_belum_dinilai(kon)
        assert cek_gratis.hasil_siswa(kon, ID_A, anak)["status"] == "belum_selesai"
    _order_lunas_qris(anak, _cek_id)
    # Act: buang transaksi pemanggil sesudah kumpulkan; penilaian yang sudah dipastikan tidak boleh ikut hilang
    with database.buka(belajar) as kon:
        data.kumpulkan(kon, ID_A, anak, SETELAH)
        kon.rollback()
    # Assert
    with database.buka(belajar) as kon:
        hasil = cek_gratis.hasil_siswa(kon, ID_A, anak)
        assert hasil["status"] != "belum_selesai" and hasil["skor"] is not None
        assert _baris_laporan(kon, anak)["diterbitkan_oleh"] == "sistem"


def test_draf_guru_yang_sudah_ada_tidak_disentuh(ledger, belajar):
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
    _order_lunas_qris(anak, cek_id)
    with database.buka(belajar) as kon:
        _draf_guru(kon, anak, cek_id)
        awal = _baris_mentah(kon, anak)
    assert awal, "premis: draf Guru harus ada"
    hasil = _kumpulkan(belajar, anak)
    with database.buka(belajar) as kon:
        assert _baris_mentah(kon, anak) == awal
    assert hasil.peta is None
    assert _purna_terbit(ledger) == []


def test_laporan_guru_terbit_tetap_dan_penanda_sistem_salah(ledger, belajar):
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
    _order_lunas_qris(anak, cek_id)
    with database.buka(belajar) as kon:
        _terbit_guru(kon, anak, cek_id)
        sebelum = toko.terbit_terakhir(kon, anak)
    hasil = _kumpulkan(belajar, anak)
    assert hasil.peta["oleh_sistem"] is False
    assert {k: v for k, v in hasil.peta.items() if k != "oleh_sistem"} == sebelum
    assert hasil.peta["catatan"] == CATATAN_GURU
    assert _purna_terbit(ledger) == []


def test_ledger_tak_terbaca_tidak_menggagalkan_kumpulkan(ledger, belajar, monkeypatch):
    with database.buka(belajar) as kon:
        anak, cek_id = _anak_dengan_cek(kon)
    _order_lunas_qris(anak, cek_id)

    def tak_terbaca(*_args, **_kwargs):
        raise sqlite3.OperationalError("ledger tidak terbaca (sintetis)")

    monkeypatch.setattr(otomatis, "baca_izin", tak_terbaca)
    hasil = _kumpulkan(belajar, anak)
    assert isinstance(hasil, data.DataOrangTua)
    assert hasil.status_pesanan == d.STATUS_SUDAH_DIBAYAR
    assert hasil.peta is None
    assert _hitung_laporan(belajar) == 0

