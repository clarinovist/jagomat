"""Panel admin pesanan (Fase 3c-4) lewat HTTP: daftar, periksa, catat refund, akses.

Provider PALSU dan data sintetis. Efek (atau ketiadaannya) dibuktikan dari ledger dan hitungan
panggilan provider, bukan hanya kode status. Guard sengaja diuji lewat jalur HTTP yang sama
dengan mutation di test_admin_pesanan_mutation.py.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pages  # noqa: E402
import admin_pesanan_http as ap  # noqa: E402
import pesanan  # noqa: E402
import pesanan_kit  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402
    HALAMAN, ORDER_ASING, PERIKSA, REFUND, RUTE_AKSI, TAK_ADA, baris_refund, hasil_dari,
    id_admin, jumlah_panggilan, kirim_aksi, kirim_dari_detail, login_admin, markup, minta_admin,
    order_bayar, order_lunas, token_langsung,
)
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, id_akun, minta_mentah  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_http_kit import (  # noqa: E402
    AKUN_A, KOSONG, MERCHANT, NAMA_A, WA_SINTETIS, ProviderPalsu, Respons, atur_tahap, bayar,
    jam, keadaan_ledger, keluarga, ledger, pasang_runtime, satu_order, server, tertutup,
)

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)


@pytest.fixture()
def admin(bayar):
    return login_admin(bayar)


def _stempel(server):
    """Potret efek: seluruh tabel ledger + jumlah panggilan provider."""
    return keadaan_ledger(), jumlah_panggilan(server), baris_refund()


# --- daftar --------------------------------------------------------------------

def test_daftar_kosong_200_privat_dan_nav_terdaftar(bayar, admin):
    kode, isi, tajuk = minta_admin(bayar, HALAMAN, admin)
    assert kode == 200
    assert tajuk["Cache-Control"] == "no-store"
    assert "Pesanan Paket Coba" in isi and 'href="/admin/pesanan"' in isi
    assert "Belum ada pesanan" in isi


def test_daftar_memuat_kolom_minimal_tanpa_pii(bayar, admin):
    order, trx = order_bayar(bayar)
    kode, isi, _t = minta_admin(bayar, HALAMAN, admin)
    assert kode == 200
    assert order["order_id"] in isi
    assert order["akun_id"][:13] in isi and order["akun_id"] not in isi
    assert "Menunggu pembayaran" in isi
    for terlarang in (NAMA_A, WA_SINTETIS, MERCHANT, trx, order["idempotency_key"], "49000"):
        assert terlarang not in isi


def test_daftar_waktu_wib_bukan_utc_mentah(bayar, admin):
    order_bayar(bayar)
    isi = minta_admin(bayar, HALAMAN, admin)[1]
    assert "18 Nov 2026, 17.00 WIB" in isi  # dibuat 10.00 UTC (kolom kedaluwarsa pindah ke Detail order)
    assert "19 Nov 2026, 17.00 WIB" not in isi


def test_daftar_paginasi_25_per_halaman_terbaru_dulu(bayar, admin):
    awal = datetime(2026, 1, 1)
    with ledger() as kon:
        for n in range(1, 31):  # jarak 2 hari: order lama sudah kedaluwarsa, kuota 20 tidak kena
            pesanan_kit.buat(kon, n, sekarang=(awal + timedelta(days=2 * n)).strftime("%Y-%m-%dT%H:%M:%S"))
    h1 = minta_admin(bayar, HALAMAN, admin)[1]
    h2 = minta_admin(bayar, HALAMAN + "?halaman=2", admin)[1]
    assert h1.count("<tr><td>") == 25 and h2.count("<tr><td>") == 5
    assert pesanan_kit.ord_id(30) in h1 and pesanan_kit.ord_id(30) not in h2
    assert pesanan_kit.ord_id(1) in h2
    assert "halaman=2" in h1 and "halaman=1" in h2


@pytest.mark.parametrize("query", ["?halaman=0", "?halaman=abc", "?hasil=sembarang", "?x=1", "?halaman=1&halaman=2"])
def test_daftar_query_tak_sah_404_identik(bayar, admin, query):
    acuan = minta_admin(bayar, TAK_ADA, admin)
    kode, isi, _t = minta_admin(bayar, HALAMAN + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_daftar_gerbang_tertutup_tetap_tampil_tanpa_tombol_periksa(bayar, admin):
    order, _trx = order_bayar(bayar)
    atur_tahap("rekonsiliasi")
    kode, isi, _t = minta_admin(bayar, HALAMAN, admin)
    assert kode == 200 and order["order_id"] in isi
    assert "Gerbang pembayaran tertutup" in isi
    assert PERIKSA not in isi and 'type="password"' not in markup(isi)


def test_daftar_tanpa_runtime_tetap_tampil(tertutup):
    tertutup.server.pembayaran_runtime = None
    kode, isi, _t = minta_admin(tertutup, HALAMAN, login_admin(tertutup))
    assert kode == 200 and "Gerbang pembayaran tertutup" in isi


def test_daftar_skema_pesanan_belum_dipasang_kartu_jujur_503(keluarga):
    kode, isi, _t = minta_admin(keluarga, HALAMAN, login_admin(keluarga))
    assert kode == 503 and "belum siap" in isi.lower()
    assert "Traceback" not in isi and "sqlite" not in isi.lower()


# --- periksa -------------------------------------------------------------------

def test_periksa_gerbang_terbuka_menerapkan_status_provider_ke_ledger(bayar, admin):
    order, trx = order_bayar(bayar)
    from pesanan_http_kit import settlement
    bayar.provider.status_data = lambda oid: settlement(oid, trx)
    sebelum = bayar.provider.jumlah_status
    kode, isi, tajuk = kirim_dari_detail(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, isi, hasil_dari(tajuk)) == (303, "", "periksa_ok")
    assert bayar.provider.jumlah_status == sebelum + 1
    with ledger() as kon:
        assert kon.execute("SELECT COUNT(*) FROM pesanan_receipt").fetchone()[0] == 1
    assert "Dibayar" in minta_admin(bayar, HALAMAN, admin)[1]


def test_periksa_akun_id_dari_ledger_form_dengan_akun_id_ditolak(bayar, admin):
    order, _trx = order_bayar(bayar)
    sebelum = _stempel(bayar)
    for akun in (id_akun(AKUN_ADMIN), order["akun_id"]):
        kode, _i, _t = kirim_aksi(bayar, admin, PERIKSA, order["order_id"], ekstra={"akun_id": akun})
        assert kode == 400
    assert _stempel(bayar) == sebelum


def test_periksa_order_milik_akun_lain_dari_admin_tetap_diperiksa_lewat_pemilik_ledger(bayar, admin):
    order, _trx = order_bayar(bayar)
    assert order["akun_id"] != id_admin()
    kode, _i, tajuk = kirim_aksi(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "periksa_ok")


@pytest.mark.parametrize("cara", ["tanpa_runtime", "tahap_rekonsiliasi", "funnel_mati"])
def test_periksa_gerbang_tertutup_jujur_tanpa_panggilan_provider_dan_tanpa_efek(bayar, admin, monkeypatch, cara):
    order, _trx = order_bayar(bayar)
    if cara == "tanpa_runtime":
        bayar.server.pembayaran_runtime = None
    elif cara == "tahap_rekonsiliasi":
        atur_tahap("rekonsiliasi")
    else:
        monkeypatch.setenv("FUNNEL_AKTIF", "0")
    sebelum = _stempel(bayar)
    kode, _i, tajuk = kirim_aksi(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "gerbang_tertutup")
    assert _stempel(bayar) == sebelum


def test_periksa_order_lunas_dilewati_tanpa_panggilan(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    kode, _i, tajuk = kirim_aksi(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "periksa_dilewati")
    assert _stempel(bayar) == sebelum


def test_periksa_provider_gagal_jujur_dan_ledger_tak_berubah(bayar, admin):
    order, _trx = order_bayar(bayar)
    bayar.provider.status_data = lambda oid: Respons({}, kode=500)
    sebelum = keadaan_ledger()
    kode, _i, tajuk = kirim_aksi(bayar, admin, PERIKSA, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "periksa_gagal")
    assert keadaan_ledger() == sebelum


def test_periksa_order_tak_ada_404_tanpa_panggilan(bayar, admin):
    order_bayar(bayar)
    sebelum = _stempel(bayar)
    acuan = minta_admin(bayar, TAK_ADA, admin, {"x": "1"})
    kode, isi, _t = kirim_aksi(bayar, admin, PERIKSA, ORDER_ASING)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert _stempel(bayar) == sebelum


# --- refund --------------------------------------------------------------------

def test_refund_sukses_dicatat_oleh_admin_sesi_tanpa_panggilan_provider(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    panggilan = jumlah_panggilan(bayar)
    kode, isi, tajuk = kirim_dari_detail(bayar, admin, REFUND, order["order_id"])
    assert (kode, isi, hasil_dari(tajuk)) == (303, "", "refund_dicatat")
    (baris,) = baris_refund()
    assert (baris["order_id"], baris["dicatat_oleh"], baris["catatan_kode"]) == (
        order["order_id"], id_admin(), "permintaan_pembeli")
    assert baris["operasi_id"].startswith("rfd_")
    assert jumlah_panggilan(bayar) == panggilan
    assert "Direfund" in minta_admin(bayar, HALAMAN, admin)[1]


def test_refund_idempoten_replay_form_sama(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "kebijakan"}
    assert hasil_dari(minta_admin(bayar, REFUND, admin, data)[2]) == "refund_dicatat"
    kode, _i, tajuk = minta_admin(bayar, REFUND, admin, data)
    assert (kode, hasil_dari(tajuk)) == (303, "refund_sudah_ada")
    assert len(baris_refund()) == 1


def test_refund_ulang_dari_form_baru_dengan_catatan_sama_idempoten(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    assert kirim_aksi(bayar, admin, REFUND, order["order_id"])[0] == 303
    kode, _i, tajuk = kirim_aksi(bayar, admin, REFUND, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "refund_sudah_ada")
    assert len(baris_refund()) == 1


def test_refund_kedua_dengan_catatan_beda_konflik_409_catatan_pertama_tetap(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    assert kirim_aksi(bayar, admin, REFUND, order["order_id"])[0] == 303
    kode, isi, _t = kirim_aksi(bayar, admin, REFUND, order["order_id"], ganti={"catatan_kode": "lainnya"})
    assert kode == 409 and "Traceback" not in isi
    (baris,) = baris_refund()
    assert baris["catatan_kode"] == "permintaan_pembeli"


def test_refund_order_tanpa_receipt_konflik_409_tanpa_catatan(bayar, admin):
    order, _trx = order_bayar(bayar)
    sebelum = _stempel(bayar)
    kode, isi, _t = kirim_aksi(bayar, admin, REFUND, order["order_id"])
    assert kode == 409 and "receipt" not in isi.lower()
    assert _stempel(bayar) == sebelum


@pytest.mark.parametrize("ganti,hapus,ekstra", [
    ({"catatan_kode": "sembarang"}, (), None),
    ({"catatan_kode": ""}, (), None),
    ({"catatan_kode": "' OR 1=1 --"}, (), None),
    (None, ("catatan_kode",), None),
    (None, (), {"nominal": "1"}),
    (None, (), {"akun_id": "akun_x"}),
])
def test_refund_isian_tak_sah_400_tanpa_efek(bayar, admin, ganti, hapus, ekstra):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    kode, _i, _t = kirim_aksi(bayar, admin, REFUND, order["order_id"], ganti=ganti, hapus=hapus, ekstra=ekstra)
    assert kode == 400
    assert _stempel(bayar) == sebelum


def test_refund_tidak_dibatasi_gerbang_pembayaran(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    atur_tahap("nonaktif")
    kode, _i, tajuk = kirim_aksi(bayar, admin, REFUND, order["order_id"])
    assert (kode, hasil_dari(tajuk)) == (303, "refund_dicatat")


def test_refund_order_tak_ada_404(bayar, admin):
    order_lunas(bayar, admin)
    acuan = minta_admin(bayar, TAK_ADA, admin, {"x": "1"})
    kode, isi, _t = kirim_aksi(bayar, admin, REFUND, ORDER_ASING)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert baris_refund() == []


# --- guard form (CSRF, tinjauan, reauth, sesi) -----------------------------------

@pytest.mark.parametrize("jalur", RUTE_AKSI)
def test_csrf_salah_403_tanpa_efek(bayar, admin, jalur):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    assert kirim_aksi(bayar, admin, jalur, order["order_id"], ganti={"csrf": "rusak"})[0] == 403
    assert kirim_aksi(bayar, admin, jalur, order["order_id"], hapus=("csrf",))[0] == 403
    assert _stempel(bayar) == sebelum


@pytest.mark.parametrize("jalur", RUTE_AKSI)
def test_sandi_ulang_salah_403_tanpa_efek(bayar, admin, jalur):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    assert kirim_aksi(bayar, admin, jalur, order["order_id"], ganti={"reauth": "salah-sandi"})[0] == 403
    assert _stempel(bayar) == sebelum


def test_tinjauan_aksi_lain_tidak_berlaku_lintas_rute(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    periksa = token_langsung(admin, ap.AKSI_PERIKSA, order["order_id"])
    kode, _i, _t = minta_admin(bayar, REFUND, admin, {**periksa, "catatan_kode": "lainnya"})
    assert kode == 403
    refund = token_langsung(admin, ap.AKSI_REFUND, order["order_id"])
    assert minta_admin(bayar, PERIKSA, admin, refund)[0] == 403
    assert _stempel(bayar) == sebelum


def test_tinjauan_dari_sesi_lain_ditolak(bayar, admin):
    order, _trx = order_lunas(bayar, admin)
    data = token_langsung("sesi-lain-sintetis", ap.AKSI_REFUND, order["order_id"])
    kode, _i, _t = minta_admin(bayar, REFUND, admin, {**data, "catatan_kode": "lainnya"})
    assert kode == 403 and baris_refund() == []


@pytest.mark.parametrize("jalur", RUTE_AKSI)
def test_basic_auth_tanpa_kuki_403_tanpa_efek(bayar, admin, jalur):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)
    data = token_langsung(admin, ap.AKSI_REFUND, order["order_id"])
    kode, _i, _t = minta_mentah(bayar, jalur, AKUN_ADMIN, {**data, "catatan_kode": "lainnya"})
    assert kode == 403
    assert _stempel(bayar) == sebelum


# --- akses non-admin -------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_byte_identik_rute_tak_dikenal_tanpa_efek(bayar, admin, akun, monkeypatch):
    order, _trx = order_lunas(bayar, admin)
    sebelum = _stempel(bayar)

    dibaca = []

    def gagal(*_a, **_k):
        dibaca.append(1)  # dicatat, bukan pytest.fail: galat di ulir server bukan asersi
        raise sqlite3.OperationalError("tidak boleh dibaca")

    with monkeypatch.context() as ctx:
        ctx.setattr(ap.pesanan, "buka", gagal)
        acuan_get = minta_mentah(bayar, TAK_ADA, akun)
        acuan_post = minta_mentah(bayar, TAK_ADA, akun, {"x": "1"})
        assert acuan_get[0] == acuan_post[0] == 404
        assert minta_mentah(bayar, HALAMAN, akun)[:2] == acuan_get[:2]
        for jalur in RUTE_AKSI:
            data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "lainnya"}
            assert minta_mentah(bayar, jalur, akun, data)[:2] == acuan_post[:2]
            assert minta_mentah(bayar, jalur, akun, {})[:2] == acuan_post[:2]
    assert dibaca == []
    assert _stempel(bayar) == sebelum


def test_section_pesanan_terdaftar_di_nav_grup_penjualan():
    assert ("pesanan", "Pesanan & transfer", "/admin/pesanan") in admin_pages.SECTION
    grup = dict(admin_pages.GRUP_SECTION)
    assert grup["Penjualan"][0] == "pesanan"
    assert "pesanan" in admin_pages.SECTION_LOKAL
