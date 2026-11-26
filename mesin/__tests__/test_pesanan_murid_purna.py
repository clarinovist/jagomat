"""Kartu "Deposit dan laporan" di permukaan pembeli (murid) lewat HTTP nyata; tidak ada pilihan terlambat/uang kembali.

Order lunas di jalur QRIS DAN transfer rekening (fixture `lunas_murid`); provider dan data sintetis. Efek (atau
ketiadaannya) dibuktikan dari tabel purna + kedua tabel refund, bukan hanya kode status. Tes negatif di sini menjadi
sasaran mutation di `test_pesanan_murid_purna_mutation.py`.
"""
from __future__ import annotations

import re

import pytest

import pesanan_dasar
import pesanan_http
import pesanan_voucher_pages as hv
import purna
from admin_pesanan_kit import login_admin
from admin_transfer_kit import SETUJUI, kirim_putusan
from bukti_kit import JPEG, bukti
from pesanan_http_kit import (  # noqa: F401
    KOSONG, WA_SINTETIS, bayar, jam, keluarga, kirim, ledger, minta_mentah, principal_basic_untuk, server, settlement,
    teks_tampak, tertutup, token,
)
from pesanan_murid_kit import M, NAMA_ANAK_A, NAMA_ANAK_B, buat_murid, sakelar_hidup  # noqa: F401
from pesanan_transfer_http_kit import minta_multipart, transfer  # noqa: F401
from pesanan_transfer_pages import rupiah, waktu_wib
from peta_otomatis_kit import tanpa_terbit_otomatis  # noqa: F401  (autouse: laporan belum terbit di berkas ini)
from purna_http_kit import bayar_purna, potret_efek, transfer_purna  # noqa: F401
from purna_http_kit import jadikan_ditahan as jadikan_ditahan_kit

PILIH = M + "/pilih"          # rute lama (pilihan terlambat) yang sudah dihapus
JAM_LEWAT_BATAS = 48 + 1           # janji 48 jam + 1 jam
KATA_TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "pembahasan", "jawaban benar", "tel:", "wa.me")
KARTU = re.compile(r'<div class="kartu-st" id="kartu-voucher">(.*?)</div>', re.S)


class Siap:
    """Server + murid pembeli + order lunas."""

    def __init__(self, server, murid, order_id):
        self.server, self.murid, self.order_id = server, murid, order_id


def _pesan_dan_tagihan(server, murid):
    assert kirim(server, M + "/pesan", murid.akun, aksi="pesan")[0] == 303
    with ledger() as kon:
        return kon.execute("SELECT order_id FROM pesanan_order ORDER BY rowid DESC LIMIT 1").fetchone()[0]


def _lunas_qris(server, murid):
    order_id = _pesan_dan_tagihan(server, murid)
    trx = server.provider.transaksi[order_id]
    server.provider.status_data = lambda oid: settlement(oid, trx)
    assert minta_mentah(server, M, murid.akun)[0] == 200       # GET status menerapkan hasil provider
    return order_id


def _lunas_transfer(server, murid):
    order_id = _pesan_dan_tagihan(server, murid)
    assert kirim(server, M + "/tagihan", murid.akun, aksi="tagihan")[0] == 303
    tok = token(murid.akun, "bukti")
    assert minta_multipart(server, M + "/bukti", murid.akun, bukti(tok, JPEG))[0] == 303
    admin = login_admin(server)
    assert kirim_putusan(server, admin, SETUJUI, order_id)[0] == 303
    return order_id


def _siapkan(server, jalur, nama="murid-a", nama_anak=NAMA_ANAK_A):
    murid = buat_murid(server, nama, nama_anak)
    pembuat = _lunas_qris if jalur == "qris" else _lunas_transfer
    return Siap(server, murid, pembuat(server, murid))


@pytest.fixture(params=["qris", "transfer"])
def lunas_murid(request, sakelar_hidup):
    """Order lunas milik murid di jalur QRIS lalu transfer rekening; skema purna terpasang."""
    server = request.getfixturevalue("bayar_purna" if request.param == "qris" else "transfer_purna")
    return _siapkan(server, request.param)


@pytest.fixture()
def transfer_lunas_tanpa_purna(transfer, sakelar_hidup):
    """Order transfer lunas, tetapi skema purna BELUM dimigrasikan (transfer sudah)."""
    return _siapkan(transfer, "transfer")


def refund_mentah(siap, jam, kon=None):
    """Catatan refund langsung ke ledger yang menjadi jalur order (receipt QRIS: pesanan_refund; selain itu transfer)."""
    if kon is None:
        with ledger() as baru:
            return refund_mentah(siap, jam, baru)
    tabel = ("pesanan_refund" if kon.execute("SELECT 1 FROM pesanan_receipt WHERE order_id=?",
                                             (siap.order_id,)).fetchone() else "transfer_refund")
    kon.execute("BEGIN IMMEDIATE")
    kon.execute("INSERT INTO %s(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) VALUES(?,?,?,?,?)" % tabel,
                ("rfd_sintetis_0001", siap.order_id, "admin_sintetis", "kebijakan", jam()))
    kon.commit()


def halaman(siap, akun=None):
    kode, isi, _ = minta_mentah(siap.server, M, siap.murid.akun if akun is None else akun)
    assert kode == 200
    return isi


def kartu(isi):
    cocok = KARTU.search(isi)
    return None if cocok is None else cocok.group(1)


def keadaan(siap):
    with ledger() as kon:
        return purna.keadaan(kon, siap.order_id, pesanan_http.alur.waktu_sekarang())


def terlambat(siap, jam):
    jam.maju_jam(JAM_LEWAT_BATAS)
    assert keadaan(siap).terlambat


def jadikan_ditahan(siap, jam):
    jadikan_ditahan_kit(siap.server, siap.order_id, jam)


# --- kartu: tampil dan isi ---------------------------------------------------------------------

def test_kartu_tampil_untuk_order_lunas_dengan_deposit_tenggat_dan_janji_tanpa_tombol(lunas_murid):
    siap = lunas_murid
    k = keadaan(siap)
    isi = kartu(halaman(siap))
    assert isi is not None
    tampak = teks_tampak(isi)
    assert "Potongan dan laporan" in tampak
    assert "Potongan " + rupiah(pesanan_dasar.RUPIAH_PAKET) in tampak
    assert "Memotong tagihan bulan pertama kelas bersama Guru bila Anda mendaftar." in tampak
    assert "otomatis" not in tampak.lower()
    assert "Berlaku hingga " + waktu_wib(k.berlaku_hingga) in tampak
    assert "Laporan langsung terbit setelah pembayaran terverifikasi." in tampak and "paling lambat" not in tampak
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_AKTIF] in tampak
    assert "<form" not in isi and "<button" not in isi and "<input" not in isi


def test_kode_voucher_internal_tidak_tampil_ke_pembeli_tetapi_ada_di_domain(lunas_murid):
    siap = lunas_murid
    k = keadaan(siap)
    assert k.kode.startswith("JGV-")
    isi = halaman(siap)
    assert k.kode not in isi and "JGV-" not in isi and "Kode voucher" not in isi and PILIH not in isi


def test_kalimat_status_deposit_awam_mengikuti_keadaan(lunas_murid, jam):
    siap = lunas_murid
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_AKTIF] in teks_tampak(kartu(halaman(siap)))
    with ledger() as kon:
        purna.catat_pakai(kon, siap.order_id, "vch_sintetis_0001", "admin_sintetis", "kelas", jam())
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_DIPAKAI] in teks_tampak(kartu(halaman(siap)))


def test_kalimat_status_deposit_kedaluwarsa(lunas_murid, jam):
    jam.maju_jam(24 * 90 + 1)
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_KEDALUWARSA] in teks_tampak(kartu(halaman(lunas_murid)))


def test_kartu_tidak_tampil_sebelum_lunas(sakelar_hidup, bayar_purna):
    murid = buat_murid(bayar_purna, "murid-a", NAMA_ANAK_A)
    assert kirim(bayar_purna, M + "/pesan", murid.akun, aksi="pesan")[0] == 303
    kode, isi, _ = minta_mentah(bayar_purna, M, murid.akun)
    assert kode == 200 and "Menunggu pembayaran" in teks_tampak(isi)         # halaman lama tetap tampil utuh
    assert "kartu-voucher" not in isi and "Potongan dan laporan" not in isi


def test_kartu_tidak_tampil_untuk_order_direfund(lunas_murid, jam):
    siap = lunas_murid
    assert kartu(halaman(siap)) is not None
    refund_mentah(siap, jam)
    isi = halaman(siap)
    assert "kartu-voucher" not in isi


def test_kartu_tidak_tampil_bila_skema_purna_belum_dipasang(transfer_lunas_tanpa_purna, jam):
    siap = transfer_lunas_tanpa_purna
    jam.maju_jam(JAM_LEWAT_BATAS)
    isi = halaman(siap)
    assert "Pembayaran diterima" in teks_tampak(isi)             # perilaku lama tetap
    assert "kartu-voucher" not in isi and "Potongan dan laporan" not in isi


def test_kartu_tidak_tampil_untuk_order_perlu_diperiksa_ditahan(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    jadikan_ditahan(siap, jam)
    k = keadaan(siap)
    assert (k.lunas, k.ditahan, k.voucher) == (True, True, purna.VOUCHER_DITAHAN)
    assert "kartu-voucher" not in halaman(siap)              # kartu pembeli hanya untuk sudah_dibayar


def test_kartu_terlambat_tanpa_tombol_dengan_kalimat_maaf_lalu_terbit_menurut_keadaan(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    isi = kartu(halaman(siap))
    assert "Laporan belum terbit. Hubungi tim lewat WhatsApp; kami bantu sampai laporan Anda terbit." in teks_tampak(isi)
    assert "WhatsApp" in teks_tampak(isi)
    assert "<form" not in isi and "<button" not in isi and PILIH not in halaman(siap)
    with ledger() as kon:
        purna.catat_terbit(kon, siap.order_id, "admin_sintetis", jam())
    hal_terbit = halaman(siap)
    isi = kartu(hal_terbit)
    assert "Laporan sudah terbit" in teks_tampak(isi) and "<form" not in isi
    assert "sudah lewat janji" not in teks_tampak(isi)
    assert "Perkiraan terbit menyusul" not in teks_tampak(hal_terbit)


def test_kartu_tidak_menyebut_uang_kembali_pilihan_atau_voucher(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    tampak = teks_tampak(kartu(halaman(siap))).lower()
    for kata in ("uang kembali", "pilihan", "yakin", "tetap menunggu", "voucher"):
        assert kata not in tampak, kata


# --- rute pilihan lama sudah dihapus ----------------------------------------------------------------

def test_murid_post_rute_pilih_404_identik_dengan_rute_tak_dikenal_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    tok = token(siap.murid.akun, "pilih")
    data = {"token": tok, "pilihan": "uang_kembali", "yakin": "1"}
    harap = minta_mentah(siap.server, M + "/tidak-ada-rute", siap.murid.akun, data)[:2]
    assert harap[0] in (401, 404)                       # jawaban penangan murid untuk rute tak dikenal
    assert minta_mentah(siap.server, PILIH, siap.murid.akun, data)[:2] == harap
    harap_get = minta_mentah(siap.server, M + "/tidak-ada-rute", siap.murid.akun)[:2]
    assert harap_get[0] == 404
    assert minta_mentah(siap.server, PILIH, siap.murid.akun)[:2] == harap_get       # GET pun identik
    assert potret_efek() == sebelum


def test_anonim_post_rute_pilih_401_seperti_rute_tak_dikenal_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    data = {"token": "x", "pilihan": "menunggu"}
    harap = minta_mentah(siap.server, M + "/tidak-ada-rute", None, data)[:2]
    assert harap[0] == 401
    assert minta_mentah(siap.server, PILIH, None, data)[:2] == harap
    assert potret_efek() == sebelum


def test_guru_lama_rute_pilih_identik_rute_tak_dikenal_tanpa_kartu(bayar_purna, sakelar_hidup, jam):
    from admin_pesanan_kit import order_lunas
    from pesanan_http_kit import AKUN_A
    admin = login_admin(bayar_purna)
    order_lunas(bayar_purna, admin)
    jam.maju_jam(JAM_LEWAT_BATAS)
    kode, isi, _ = minta_mentah(bayar_purna, "/pesanan", AKUN_A)
    assert kode == 200 and "Pembayaran diterima" in teks_tampak(isi)
    assert PILIH not in isi and 'name="pilihan"' not in isi and "kartu-voucher" not in isi
    harap = minta_mentah(bayar_purna, "/pesanan/tidak-ada-rute", AKUN_A, {"x": "1"})[:2]
    sebelum = potret_efek()
    tok = token(AKUN_A, "pilih")
    assert minta_mentah(bayar_purna, "/pesanan/pilih", AKUN_A, {"token": tok, "pilihan": "menunggu"})[:2] == harap
    assert potret_efek() == sebelum and sebelum["purna_voucher_pakai"] == [] and sebelum["purna_laporan_terbit"] == []


# --- kepemilikan kartu dan palang murid ----------------------------------------------------------

def test_murid_lain_tanpa_order_tidak_melihat_kartu_atau_identitas_order_milik_lain(lunas_murid):
    siap = lunas_murid
    b = buat_murid(siap.server, "murid-b", NAMA_ANAK_B)            # belum punya order
    kode, isi, _ = minta_mentah(siap.server, M, b.akun)
    assert kode == 200 and "kartu-voucher" not in isi and "Potongan dan laporan" not in isi
    assert siap.order_id not in isi and keadaan(siap).kode not in isi and NAMA_ANAK_A not in isi


def test_kartu_murid_b_memakai_order_miliknya_bukan_order_milik_lain(sakelar_hidup, bayar_purna, jam):
    a = _siapkan(bayar_purna, "qris", "murid-a", NAMA_ANAK_A)
    jam.maju_jam(5)
    b = _siapkan(bayar_purna, "qris", "murid-b", NAMA_ANAK_B)
    ka, kb = keadaan(a), keadaan(b)
    assert ka.berlaku_hingga != kb.berlaku_hingga
    tampak_a, tampak_b = teks_tampak(kartu(halaman(a))), teks_tampak(kartu(halaman(b)))
    assert waktu_wib(ka.berlaku_hingga) in tampak_a and waktu_wib(kb.berlaku_hingga) not in tampak_a
    assert waktu_wib(kb.berlaku_hingga) in tampak_b and waktu_wib(ka.berlaku_hingga) not in tampak_b


def test_halaman_murid_tanpa_kata_terlarang_kontak_atau_id_internal(lunas_murid, jam):
    siap = lunas_murid
    halamannya = [halaman(siap)]
    terlambat(siap, jam)
    halamannya.append(halaman(siap))
    halamannya.append(minta_mentah(siap.server, "/murid/orang-tua", siap.murid.akun)[1])
    for isi in halamannya:
        assert WA_SINTETIS not in isi and "0812" not in isi and "+62" not in isi
        tampak = teks_tampak(isi).lower()
        for kata in KATA_TERLARANG:
            assert kata not in tampak, kata
        assert siap.order_id not in isi and "vch_" not in isi and "operasi" not in tampak


def test_halaman_orang_tua_memuat_satu_baris_janji_tanpa_tombol_dan_beranda_tetap_satu_tautan(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    isi = minta_mentah(siap.server, "/murid/orang-tua", siap.murid.akun)[1]
    # Order terlambat: baris janji diganti kalimat maaf (tidak ada janji "langsung terbit" yang bertentangan).
    assert "Laporan belum terbit. Hubungi tim lewat WhatsApp" in teks_tampak(isi)
    assert "Laporan langsung terbit setelah pembayaran terverifikasi." not in teks_tampak(isi)
    assert "paling lambat" not in teks_tampak(isi)
    assert PILIH not in isi and "<button" not in isi.split('id="ortu-pesanan"')[1].split("</section>")[0]
    beranda = minta_mentah(siap.server, "/murid", siap.murid.akun)[1]
    assert beranda.count('href="/murid/orang-tua"') == 1


def test_halaman_orang_tua_tanpa_baris_janji_bila_purna_belum_dipasang(transfer_lunas_tanpa_purna):
    isi = minta_mentah(transfer_lunas_tanpa_purna.server, "/murid/orang-tua", transfer_lunas_tanpa_purna.murid.akun)[1]
    assert "dijanjikan terbit" not in teks_tampak(isi)
