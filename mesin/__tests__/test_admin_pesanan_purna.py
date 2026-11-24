"""Aksi admin purna lewat HTTP: catat voucher dipakai dan catat laporan terbit dari Detail order (V3).

Order lunas di jalur QRIS DAN transfer rekening (fixture `lunas`); provider dan data sintetis. Efek (atau ketiadaannya)
dibuktikan dari tabel purna dan kedua tabel refund, bukan hanya kode status. Tes negatif di sini menjadi sasaran
mutation di `test_admin_pesanan_purna_mutation.py`.
"""
from __future__ import annotations

import html
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_detail_pages as dui  # noqa: E402
import admin_pesanan_http as ap  # noqa: E402
import schema_purna  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402
    HALAMAN, ORDER_ASING, REFUND, TAK_ADA, TERBIT, VOUCHER, RUTE_PURNA, AKSI_RUTE, alamat_detail, form_order,
    hasil_dari, id_admin, kirim_aksi, kirim_dari_detail, login_admin, markup, minta_admin, order_bayar,
    order_lunas, token_langsung,
)
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, minta_mentah  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_http_kit import ProviderPalsu, WAKTU_AWAL, bayar, jam, keadaan_ledger, keluarga, ledger, server, tertutup  # noqa: E402,F401
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from purna_http_kit import (  # noqa: E402,F401
    bayar_purna, kosong, lunas, lunas_transfer, pilih_uang_kembali, potret_efek, transfer_purna,
)

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
JAM_LEWAT_BATAS = 24 * 5 + 1       # janji 48 jam + toleransi 72 jam + 1 jam
JAM_LEWAT_VOUCHER = 24 * 90 + 1    # masa berlaku voucher 90 hari + 1 jam
BARIS = re.compile(r"<tr><td>.*?</tr>", re.S)
SEL = re.compile(r"<td>(.*?)</td>", re.S)


def _detail(server, cookie, order_id, hasil=""):
    kode, isi, _t = minta_admin(server, alamat_detail(order_id, hasil), cookie)
    assert kode == 200
    return isi


def _sel_laporan(isi: str) -> str:
    (baris,) = BARIS.findall(isi)
    return html.unescape(SEL.findall(baris)[5])


def _rute_dan_isian(jalur):
    return {VOUCHER: {"catatan_kode": "kelas"}, TERBIT: {}}[jalur]


# --- voucher: sukses, replay, konflik ----------------------------------------------------

def test_voucher_dari_detail_dicatat_oleh_admin_sesi_lalu_refund_tertutup_dan_form_hilang(lunas):
    server, admin, oid = lunas
    isi = _detail(server, admin, oid)
    assert set(form_order(isi)) == {VOUCHER, TERBIT, REFUND}
    kode, badan, tajuk = kirim_dari_detail(server, admin, VOUCHER, oid)
    assert (kode, badan, hasil_dari(tajuk, oid)) == (303, "", "voucher_dicatat")
    (baris,) = potret_efek()["purna_voucher_pakai"]
    # operasi_id, order_id, dicatat_oleh, catatan_kode, dibuat
    assert baris[0].startswith("vch_") and baris[1:4] == (oid, id_admin(), "kelas")
    sesudah = _detail(server, admin, oid, "voucher_dicatat")
    assert "Voucher tercatat sudah dipakai" in sesudah and "Sudah dipakai" in sesudah
    assert set(form_order(sesudah)) == {TERBIT}
    assert dui.COPY_REFUND_VOUCHER_DIPAKAI in sesudah and dui.COPY_RINGKAS_REFUND not in sesudah


def test_voucher_replay_token_sama_idempoten_satu_baris(lunas):
    server, admin, oid = lunas
    data = {**token_langsung(admin, ap.AKSI_VOUCHER, oid), "catatan_kode": "lainnya"}
    assert hasil_dari(minta_admin(server, VOUCHER, admin, data)[2], oid) == "voucher_dicatat"
    kode, _i, tajuk = minta_admin(server, VOUCHER, admin, data)
    assert (kode, hasil_dari(tajuk, oid)) == (303, "voucher_sudah_ada")
    assert len(potret_efek()["purna_voucher_pakai"]) == 1


def test_voucher_kedua_kali_dari_token_baru_catatan_sama_sudah_ada(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    kode, _i, tajuk = kirim_aksi(server, admin, VOUCHER, oid)
    assert (kode, hasil_dari(tajuk, oid)) == (303, "voucher_sudah_ada")
    assert len(potret_efek()["purna_voucher_pakai"]) == 1


def test_voucher_kedua_kali_catatan_beda_409_catatan_pertama_tetap(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    kode, isi, _t = kirim_aksi(server, admin, VOUCHER, oid, ganti={"catatan_kode": "lainnya"})
    assert kode == 409 and "Traceback" not in isi
    (baris,) = potret_efek()["purna_voucher_pakai"]
    assert baris[3] == "kelas"


def test_voucher_sesudah_terbit_masih_boleh_dan_terbit_sesudah_voucher_replay_saja(lunas):
    server, admin, oid = lunas
    assert hasil_dari(kirim_aksi(server, admin, TERBIT, oid)[2], oid) == "terbit_dicatat"
    assert hasil_dari(kirim_aksi(server, admin, VOUCHER, oid)[2], oid) == "voucher_dicatat"
    assert hasil_dari(kirim_aksi(server, admin, TERBIT, oid)[2], oid) == "terbit_sudah_ada"


def test_voucher_order_belum_lunas_409_tanpa_efek(bayar_purna):
    admin = login_admin(bayar_purna)
    order, _trx = order_bayar(bayar_purna)
    sebelum = potret_efek()
    kode, isi, _t = kirim_aksi(bayar_purna, admin, VOUCHER, order["order_id"])
    assert kode == 409 and "Traceback" not in isi
    assert "tidak bisa dilakukan pada keadaan pesanan sekarang" in isi    # pesan konflik umum, bukan khusus refund
    assert "catatan refund yang berbeda" not in isi
    assert potret_efek() == sebelum and kosong(sebelum)


def test_voucher_order_direfund_409_tanpa_catatan_pemakaian(lunas):
    server, admin, oid = lunas
    assert hasil_dari(kirim_aksi(server, admin, REFUND, oid)[2], oid) == "refund_dicatat"
    sebelum = potret_efek()
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 409
    assert potret_efek() == sebelum and sebelum["purna_voucher_pakai"] == []


def test_voucher_kedaluwarsa_409_tanpa_efek_dan_form_hilang(lunas, jam):
    server, admin, oid = lunas
    jam.maju_jam(JAM_LEWAT_VOUCHER)
    isi = _detail(server, admin, oid)
    assert VOUCHER not in form_order(isi) and "Kedaluwarsa" in isi and TERBIT in form_order(isi)
    sebelum = potret_efek()
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 409
    assert potret_efek() == sebelum


def test_voucher_keluarga_minta_uang_kembali_409_tanpa_efek(lunas, jam):
    server, admin, oid = lunas
    jam.maju_jam(JAM_LEWAT_BATAS)
    pilih_uang_kembali(oid, jam())
    sebelum = potret_efek()
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 409
    assert potret_efek() == sebelum and sebelum["purna_voucher_pakai"] == []


# --- terbit: sukses, replay, konflik ---------------------------------------------------------

def test_terbit_dari_detail_mencatat_jam_server_oleh_admin_sesi_lalu_form_hilang(lunas, jam):
    server, admin, oid = lunas
    jam.maju_jam(5)
    kode, badan, tajuk = kirim_dari_detail(server, admin, TERBIT, oid)
    assert (kode, badan, hasil_dari(tajuk, oid)) == (303, "", "terbit_dicatat")
    (baris,) = potret_efek()["purna_laporan_terbit"]
    assert baris[:3] == (oid, jam(), id_admin())  # waktu terbit = jam pencatatan server (bukan dari form)
    sesudah = _detail(server, admin, oid, "terbit_dicatat")
    assert "Laporan tercatat sudah terbit" in sesudah and "Sudah terbit" in sesudah
    assert set(form_order(sesudah)) == {VOUCHER, REFUND}


def test_terbit_replay_dari_token_baru_sudah_ada_waktu_pertama_tetap(lunas, jam):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, TERBIT, oid)[0] == 303
    pertama = potret_efek()["purna_laporan_terbit"]
    jam.maju_jam(3)
    kode, _i, tajuk = kirim_aksi(server, admin, TERBIT, oid)
    assert (kode, hasil_dari(tajuk, oid)) == (303, "terbit_sudah_ada")
    assert potret_efek()["purna_laporan_terbit"] == pertama


def test_terbit_order_belum_lunas_409_tanpa_efek(bayar_purna):
    admin = login_admin(bayar_purna)
    order, _trx = order_bayar(bayar_purna)
    kode, isi, _t = kirim_aksi(bayar_purna, admin, TERBIT, order["order_id"])
    assert kode == 409 and "Traceback" not in isi
    assert kosong(potret_efek())


def test_terbit_order_direfund_409_tanpa_efek(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    sebelum = potret_efek()
    assert kirim_aksi(server, admin, TERBIT, oid)[0] == 409
    assert potret_efek() == sebelum and sebelum["purna_laporan_terbit"] == []


def test_terbit_dan_voucher_tidak_menulis_ledger_pembayaran(lunas):
    server, admin, oid = lunas
    sebelum = keadaan_ledger()
    assert kirim_aksi(server, admin, TERBIT, oid)[0] == 303 and kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    assert keadaan_ledger() == sebelum


# --- refund sesudah voucher dipakai: ditolak domain, bukan hanya disembunyikan ------------------

def test_refund_post_sesudah_voucher_dipakai_409_dan_tidak_ada_baris_refund_di_kedua_tabel(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    sebelum = potret_efek()
    kode, isi, _t = kirim_aksi(server, admin, REFUND, oid)
    assert kode == 409 and "Traceback" not in isi
    sesudah = potret_efek()
    assert sesudah == sebelum and sesudah["pesanan_refund"] == [] and sesudah["transfer_refund"] == []


def test_refund_post_dengan_form_lama_sesudah_voucher_dipakai_tetap_409(lunas):
    server, admin, oid = lunas
    form = form_order(_detail(server, admin, oid))[REFUND]      # dibuka sebelum voucher dipakai
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    data = {**form, "reauth": SANDI_ADMIN, "catatan_kode": "kebijakan"}
    assert minta_admin(server, REFUND, admin, data)[0] == 409
    assert potret_efek()["pesanan_refund"] == [] and potret_efek()["transfer_refund"] == []


# --- isian tidak sah: 400 ------------------------------------------------------------------

@pytest.mark.parametrize("ganti,hapus,ekstra", [
    ({"catatan_kode": "sembarang"}, (), None),
    ({"catatan_kode": ""}, (), None),
    ({"catatan_kode": "kebijakan"}, (), None),      # enum refund bukan enum pemakaian voucher
    ({"catatan_kode": "' OR 1=1 --"}, (), None),
    (None, ("catatan_kode",), None),
    (None, (), {"akun_id": "akun_x"}),
    (None, (), {"order_id": ORDER_ASING}),
    (None, (), {"dibuat": "2026-01-01T00:00:00"}),
])
def test_voucher_isian_tak_sah_400_tanpa_efek(lunas, ganti, hapus, ekstra):
    server, admin, oid = lunas
    sebelum = potret_efek()
    kode, _i, _t = kirim_aksi(server, admin, VOUCHER, oid, ganti=ganti, hapus=hapus, ekstra=ekstra)
    assert kode == 400
    assert potret_efek() == sebelum


@pytest.mark.parametrize("ekstra", [
    {"catatan_kode": "kelas"}, {"terbit": "2026-11-18T10:00:00"}, {"order_id": ORDER_ASING}, {"akun_id": "akun_x"},
])
def test_terbit_field_asing_400_tanpa_efek(lunas, ekstra):
    server, admin, oid = lunas
    sebelum = potret_efek()
    kode, _i, _t = kirim_aksi(server, admin, TERBIT, oid, ekstra=ekstra)
    assert kode == 400
    assert potret_efek() == sebelum


def test_voucher_dan_terbit_order_id_hanya_dari_tinjauan_bukan_form(lunas):
    server, admin, oid = lunas
    form = form_order(_detail(server, admin, oid))
    data = {**form[VOUCHER], "reauth": SANDI_ADMIN, "catatan_kode": "kelas", "order_id": ORDER_ASING}
    assert minta_admin(server, VOUCHER, admin, data)[0] == 400
    data.pop("order_id")
    assert hasil_dari(minta_admin(server, VOUCHER, admin, data)[2], oid) == "voucher_dicatat"


# --- guard form: CSRF, sandi ulang, tinjauan lintas aksi, sesi ----------------------------------

@pytest.mark.parametrize("jalur", RUTE_PURNA)
@pytest.mark.parametrize("ganti,hapus", [
    ({"csrf": "rusak"}, ()), (None, ("csrf",)),
    ({"reauth": "sandi-salah"}, ()), ({"reauth": ""}, ()), (None, ("reauth",)),
    (None, ("tinjauan",)), ({"tinjauan": "bukan.token"}, ()),
])
def test_guard_form_ditolak_403_tanpa_efek(lunas, jalur, ganti, hapus):
    server, admin, oid = lunas
    kode, isi, _t = kirim_dari_detail(server, admin, jalur, oid, ganti=ganti, hapus=hapus)
    assert kode == 403 and "Traceback" not in isi
    assert kosong(potret_efek())


@pytest.mark.parametrize("jalur,aksi_asing", [
    (VOUCHER, ap.AKSI_REFUND), (VOUCHER, ap.AKSI_TERBIT), (VOUCHER, ap.AKSI_PERIKSA),
    (TERBIT, ap.AKSI_REFUND), (TERBIT, ap.AKSI_VOUCHER), (TERBIT, ap.AKSI_PERIKSA),
])
def test_tinjauan_aksi_lain_ditolak_lintas_rute_purna(lunas, jalur, aksi_asing):
    server, admin, oid = lunas
    data = {**token_langsung(admin, aksi_asing, oid), **_rute_dan_isian(jalur)}
    assert minta_admin(server, jalur, admin, data)[0] == 403
    assert kosong(potret_efek())


@pytest.mark.parametrize("jalur_asing", [REFUND, "/admin/pesanan/periksa"])
def test_tinjauan_purna_ditolak_di_rute_refund_dan_periksa(lunas, jalur_asing):
    server, admin, oid = lunas
    for aksi in (ap.AKSI_VOUCHER, ap.AKSI_TERBIT):
        data = {**token_langsung(admin, aksi, oid), "catatan_kode": "kebijakan"}
        assert minta_admin(server, jalur_asing, admin, data)[0] == 403
    assert kosong(potret_efek())


@pytest.mark.parametrize("jalur", RUTE_PURNA)
def test_tinjauan_dari_sesi_lain_ditolak(lunas, jalur):
    server, admin, oid = lunas
    data = {**token_langsung("sesi-lain-sintetis", AKSI_RUTE[jalur], oid), **_rute_dan_isian(jalur)}
    assert minta_admin(server, jalur, admin, data)[0] == 403
    assert kosong(potret_efek())


@pytest.mark.parametrize("jalur", RUTE_PURNA)
def test_basic_auth_tanpa_kuki_403_tanpa_efek(lunas, jalur):
    server, admin, oid = lunas
    data = {**token_langsung(admin, AKSI_RUTE[jalur], oid), **_rute_dan_isian(jalur)}
    assert minta_mentah(server, jalur, AKUN_ADMIN, data)[0] == 403
    assert kosong(potret_efek())


# --- akses non-admin dan order tak ada ----------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_byte_identik_rute_tak_dikenal_tanpa_efek(lunas, akun, monkeypatch):
    server, admin, oid = lunas
    sebelum = potret_efek()
    dibaca = []

    def gagal(*_a, **_k):
        dibaca.append(1)
        raise sqlite3.OperationalError("tidak boleh dibaca")

    with monkeypatch.context() as ctx:
        ctx.setattr(ap.pesanan, "buka", gagal)
        acuan = minta_mentah(server, TAK_ADA, akun, {"x": "1"})
        assert acuan[0] == 404
        for jalur in RUTE_PURNA:
            data = {**token_langsung(admin, AKSI_RUTE[jalur], oid), **_rute_dan_isian(jalur)}
            assert minta_mentah(server, jalur, akun, data)[:2] == acuan[:2]
            assert minta_mentah(server, jalur, akun, {})[:2] == acuan[:2]
    assert dibaca == [] and potret_efek() == sebelum


@pytest.mark.parametrize("jalur", RUTE_PURNA)
def test_order_tak_ada_404_identik_tanpa_efek(lunas, jalur):
    server, admin, _oid = lunas
    sebelum = potret_efek()
    acuan = minta_admin(server, TAK_ADA, admin, {"x": "1"})
    kode, isi, _t = kirim_aksi(server, admin, jalur, ORDER_ASING)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert potret_efek() == sebelum


# --- skema purna belum terpasang ----------------------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_PURNA)
def test_purna_belum_terpasang_post_409_tanpa_traceback_dan_tanpa_efek(bayar, jalur):
    admin = login_admin(bayar)
    order, _trx = order_lunas(bayar, admin)
    sebelum = keadaan_ledger()
    kode, isi, _t = kirim_aksi(bayar, admin, jalur, order["order_id"])
    assert kode == 409 and "Traceback" not in isi and "sqlite" not in isi.lower()
    assert keadaan_ledger() == sebelum


def test_purna_belum_terpasang_detail_tampil_satu_baris_tanpa_form(bayar):
    admin = login_admin(bayar)
    order, _trx = order_lunas(bayar, admin)
    isi = _detail(bayar, admin, order["order_id"])
    assert dui.COPY_JUDUL_PURNA in isi and dui.COPY_PURNA_BELUM in isi
    assert set(form_order(isi)) == {REFUND}
    assert "Kode voucher" not in isi


# --- tampilan Detail order ----------------------------------------------------------------------

def test_kartu_purna_order_lunas_memuat_kode_status_dan_tanggal_di_antara_ringkasan_dan_perjalanan(lunas):
    server, admin, oid = lunas
    isi = _detail(server, admin, oid)
    kode = "JGV-" + oid[len("ord_"):][:12].upper()
    assert kode in isi and "Aktif" in isi and "Belum terbit" in isi and "Belum memilih" not in isi
    assert "20 Nov 2026, 17.00 WIB" in isi or "20 Nov 2026, 19.00 WIB" in isi   # janji: transfer lunas 12.00 UTC
    assert "16 Feb 2027" in isi
    assert isi.index("<h2>Order ") < isi.index(dui.COPY_JUDUL_PURNA) < isi.index("Perjalanan order")


def test_form_voucher_dan_terbit_membawa_data_konfirmasi_konsekuensi_persis(lunas):
    server, admin, oid = lunas
    isi = _detail(server, admin, oid)
    voucher = re.search(r'<form method="post" action="/admin/pesanan/voucher" data-konfirmasi="([^"]+)">(.*?)</form>', isi, re.S)
    terbit = re.search(r'<form method="post" action="/admin/pesanan/terbit" data-konfirmasi="([^"]+)">(.*?)</form>', isi, re.S)
    assert html.unescape(voucher.group(1)) == "Voucher ditandai sudah dipakai dan order ini tidak bisa direfund lagi. Tidak bisa dibatalkan."
    assert html.unescape(terbit.group(1)) == "Laporan ditandai sudah terbit sekarang (jam pencatatan). Tidak bisa dibatalkan."
    opsi = re.findall(r'<option value="([^"]+)"', voucher.group(2))
    assert opsi == list(schema_purna.CATATAN_PAKAI) == list(dui.URUTAN_ALASAN_VOUCHER)
    assert set(form_order(isi)[TERBIT]) == {"csrf", "tinjauan"}       # terbit: tanpa field isian
    assert 'name="reauth"' in markup(isi)


def test_form_purna_tersembunyi_untuk_order_belum_lunas(bayar_purna):
    admin = login_admin(bayar_purna)
    order, _trx = order_bayar(bayar_purna)
    isi = _detail(bayar_purna, admin, order["order_id"])
    assert dui.COPY_JUDUL_PURNA in isi and "Belum aktif" in isi
    assert VOUCHER not in form_order(isi) and TERBIT not in form_order(isi)


def test_form_terbit_tersembunyi_sesudah_terbit_dan_sesudah_refund(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, TERBIT, oid)[0] == 303
    assert TERBIT not in form_order(_detail(server, admin, oid))
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    assert form_order(_detail(server, admin, oid)) == {}            # direfund: voucher batal, terbit sudah ada


def test_form_voucher_dan_terbit_tersembunyi_sesudah_refund_tanpa_terbit(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    isi = _detail(server, admin, oid)
    assert VOUCHER not in form_order(isi) and TERBIT not in form_order(isi) and "Dibatalkan" in isi


def test_form_refund_tersembunyi_sesudah_voucher_dipakai_dengan_catatan_pengganti(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    isi = _detail(server, admin, oid)
    assert REFUND not in form_order(isi) and 'action="/admin/pesanan/refund"' not in isi
    assert "Voucher sudah dipakai; refund tidak tersedia." in isi


def test_peringatan_minta_uang_kembali_dekat_form_refund_dan_status_terlambat(lunas, jam):
    server, admin, oid = lunas
    jam.maju_jam(JAM_LEWAT_BATAS)
    isi = _detail(server, admin, oid)
    assert "Terlambat sejak" in isi and "Keluarga meminta uang kembali" not in isi
    pilih_uang_kembali(oid, jam())
    isi = _detail(server, admin, oid)
    assert "Keluarga meminta uang kembali (laporan terlambat)" in isi and "Minta uang kembali" in isi
    assert isi.index("Keluarga meminta uang kembali") < isi.index(dui.COPY_RINGKAS_REFUND)
    assert REFUND in form_order(isi) and VOUCHER not in form_order(isi)
    assert kirim_dari_detail(server, admin, REFUND, oid, ganti={"catatan_kode": "kebijakan"})[0] == 303
    assert "Keluarga meminta uang kembali" not in _detail(server, admin, oid)


def test_sesi_basic_baca_saja_kartu_purna_tampil_tanpa_form(lunas):
    server, _admin, oid = lunas
    kode, isi, _t = minta_mentah(server, alamat_detail(oid), AKUN_ADMIN)
    assert kode == 200 and dui.COPY_JUDUL_PURNA in isi and "Aktif" in isi
    assert form_order(isi) == {} and 'name="reauth"' not in markup(isi)


def test_kartu_purna_tanpa_pii_dan_tanpa_akun_penuh(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, VOUCHER, oid)[0] == 303
    isi = _detail(server, admin, oid)
    with ledger() as kon:
        akun_penuh = kon.execute("SELECT akun_id FROM pesanan_order WHERE order_id=?", (oid,)).fetchone()[0]
        operasi = kon.execute("SELECT operasi_id FROM purna_voucher_pakai").fetchone()[0]
    assert akun_penuh not in isi and operasi not in isi and id_admin() not in isi


# --- kolom Laporan pada daftar ------------------------------------------------------------------

def test_daftar_kolom_laporan_semua_keadaan(lunas, jam):
    server, admin, oid = lunas
    daftar = lambda: minta_admin(server, HALAMAN, admin)[1]  # noqa: E731
    assert "<th scope=\"col\">Laporan</th>" in daftar()
    assert re.fullmatch(r"Janji 20 Nov 2026, \d\d\.00 WIB", _sel_laporan(daftar()))
    jam.maju_jam(JAM_LEWAT_BATAS)
    assert _sel_laporan(daftar()) == "Terlambat"
    pilih_uang_kembali(oid, jam())
    assert _sel_laporan(daftar()) == "Minta uang kembali"
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    assert _sel_laporan(daftar()) == "—"                              # direfund tanpa terbit: tidak ada janji lagi


def test_daftar_kolom_laporan_terbit_mengalahkan_janji(lunas):
    server, admin, oid = lunas
    assert kirim_aksi(server, admin, TERBIT, oid)[0] == 303
    assert _sel_laporan(minta_admin(server, HALAMAN, admin)[1]) == "Terbit"


def test_daftar_kolom_laporan_belum_lunas_strip_dan_tanpa_tombol_aksi_baru(bayar_purna):
    admin = login_admin(bayar_purna)
    order_bayar(bayar_purna)
    isi = minta_admin(bayar_purna, HALAMAN, admin)[1]
    assert _sel_laporan(isi) == "—"
    assert form_order(isi) == {} and 'action="/admin/pesanan/' not in isi
    assert 'href="/admin/pesanan/voucher' not in isi and 'href="/admin/pesanan/terbit' not in isi


def test_daftar_purna_belum_terpasang_tetap_tampil_dengan_strip(bayar):
    admin = login_admin(bayar)
    order_lunas(bayar, admin)
    kode, isi, _t = minta_admin(bayar, HALAMAN, admin)
    assert kode == 200 and _sel_laporan(isi) == "—"
