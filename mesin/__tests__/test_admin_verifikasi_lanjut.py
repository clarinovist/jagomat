"""Alur lanjut verifikasi transfer lewat HTTP: setelah keputusan ke transfer berikutnya, banner, dan halaman ringkas.

Server loopback + provider PALSU, data sintetis. Efek dibuktikan dari ledger. Guard keamanan form (CSRF, tinjauan,
sandi) tetap diuji di test_admin_transfer_verifikasi.py; di sini hanya jalur pengalihan dan markup baru.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_transfer_menunggu  # noqa: E402
from admin_transfer_kit import (  # noqa: E402
    HALAMAN, SETUJUI, TAK_ADA, TOLAK, VERIFIKASI, form_detail, id_bukti_terakhir, kirim_putusan, login_admin,
    minta_admin, order_menunggu, stempel_putusan, tabel, teks_halaman,
)
from pesanan_transfer_http_kit import (  # noqa: E402,F401
    AKUN_B, JPEG, jam, keluarga, kirim_bukti, ledger, server, siap_tagihan, tertutup, transfer,
)
from cek_http_kit import SANDI_ADMIN  # noqa: E402

DAFTAR_HABIS = "/admin/pesanan?status=menunggu&halaman=1&hasil="
DAFTAR_LAMA = "/admin/pesanan?halaman=1&hasil="


@pytest.fixture()
def admin(transfer):
    return login_admin(transfer)


@pytest.fixture()
def dua_order(transfer, jam):
    """(lama, baru): akun A mengunggah dulu, akun B satu jam kemudian."""
    lama = order_menunggu(transfer)
    jam.maju_jam(1)
    siap_tagihan(transfer, AKUN_B)
    assert kirim_bukti(transfer, JPEG, AKUN_B)[0] == 303
    with ledger() as kon:
        baru = kon.execute("SELECT order_id FROM pesanan_order WHERE order_id != ?", (lama,)).fetchone()[0]
    return lama, baru


def _lokasi(tajuk) -> str:
    return tajuk["Location"]


# --- A4: lanjut ke transfer berikutnya -----------------------------------------------------

def test_setujui_dengan_dua_menunggu_lanjut_ke_detail_yang_tertua(transfer, admin, dua_order):
    lama, baru = dua_order
    kode, isi, tajuk = kirim_putusan(transfer, admin, SETUJUI, baru)
    assert (kode, isi) == (303, "")
    assert _lokasi(tajuk) == "%s?order=%s&hasil=verifikasi_setuju" % (VERIFIKASI, lama)
    assert [r["order_id"] for r in tabel("transfer_lunas")] == [baru]       # hanya yang diputuskan


def test_tolak_dengan_dua_menunggu_lanjut_ke_detail_lain_dengan_hasil_tolak(transfer, admin, dua_order):
    lama, baru = dua_order
    kode, _i, tajuk = kirim_putusan(transfer, admin, TOLAK, lama)
    assert kode == 303
    assert _lokasi(tajuk) == "%s?order=%s&hasil=verifikasi_tolak" % (VERIFIKASI, baru)


def test_keputusan_terakhir_ke_daftar_menunggu_kosong_dengan_pesan_hasil(transfer, admin, dua_order):
    lama, baru = dua_order
    assert kirim_putusan(transfer, admin, SETUJUI, baru)[0] == 303
    kode, _i, tajuk = kirim_putusan(transfer, admin, SETUJUI, lama)
    assert (kode, _lokasi(tajuk)) == (303, DAFTAR_HABIS + "verifikasi_setuju")
    kode, isi, _t = minta_admin(transfer, _lokasi(tajuk), admin)
    assert kode == 200
    teks = teks_halaman(isi)
    assert "Transfer disetujui. Pesanan ini sekarang tercatat lunas." in teks
    assert "Tidak ada transfer yang menunggu verifikasi" in teks
    assert 'role="status"' in isi


def test_tolak_terakhir_ke_daftar_menunggu_dengan_pesan_tolak(transfer, admin):
    order_id = order_menunggu(transfer)
    kode, _i, tajuk = kirim_putusan(transfer, admin, TOLAK, order_id)
    assert (kode, _lokasi(tajuk)) == (303, DAFTAR_HABIS + "verifikasi_tolak")
    assert "Bukti ditolak beserta alasannya" in teks_halaman(minta_admin(transfer, _lokasi(tajuk), admin)[1])


def test_galat_baca_saat_mencari_berikutnya_kembali_ke_daftar_lama_keputusan_tetap_tersimpan(
        transfer, admin, dua_order, monkeypatch):
    lama, baru = dua_order

    def gagal(*_a, **_k):
        raise sqlite3.OperationalError("disk")

    monkeypatch.setattr(admin_transfer_menunggu, "berikutnya", gagal)
    kode, _i, tajuk = kirim_putusan(transfer, admin, SETUJUI, baru)
    assert (kode, _lokasi(tajuk)) == (303, DAFTAR_LAMA + "verifikasi_setuju")
    assert [r["order_id"] for r in tabel("transfer_lunas")] == [baru]
    assert minta_admin(transfer, _lokasi(tajuk), admin)[0] == 200


def test_tolak_tanpa_alasan_tetap_galat_tanpa_efek_dan_tanpa_pengalihan_berikutnya(transfer, admin, dua_order):
    lama, baru = dua_order
    sebelum = stempel_putusan()
    for ganti, hapus in (({"alasan": "   "}, ()), (None, ("alasan",))):
        kode, _i, tajuk = kirim_putusan(transfer, admin, TOLAK, baru, ganti=ganti, hapus=hapus)
        assert kode == 400 and "Location" not in tajuk
    assert stempel_putusan() == sebelum


def test_setujui_order_yang_sama_dua_kali_tetap_409_tanpa_pengalihan(transfer, admin, dua_order):
    lama, baru = dua_order
    assert kirim_putusan(transfer, admin, SETUJUI, baru)[0] == 303
    kode, _i, tajuk = kirim_putusan(transfer, admin, SETUJUI, baru)
    assert kode == 409 and "Location" not in tajuk


# --- detail GET dengan hasil ---------------------------------------------------------------

@pytest.mark.parametrize("hasil,kalimat", [
    ("verifikasi_setuju", "Transfer sebelumnya disetujui. Ini transfer berikutnya."),
    ("verifikasi_tolak", "Transfer sebelumnya ditolak. Ini transfer berikutnya."),
])
def test_detail_dengan_hasil_sah_menampilkan_banner_status(transfer, admin, hasil, kalimat):
    order_id = order_menunggu(transfer)
    kode, isi, _t = minta_admin(transfer, "%s?order=%s&hasil=%s" % (VERIFIKASI, order_id, hasil), admin)
    assert kode == 200
    assert kalimat in teks_halaman(isi)
    assert re.search(r'<p class="admin-kartu admin-catatan" role="status"[^>]*>%s</p>' % re.escape(kalimat), isi)
    assert isi.index(kalimat) < isi.index("Verifikasi transfer</h2>")        # banner di atas ringkasan


def test_detail_tanpa_hasil_tidak_menampilkan_banner(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order_id), admin)[1]
    assert "transfer berikutnya" not in isi


@pytest.mark.parametrize("hasil", ["asal", "", "periksa_ok", "refund_dicatat", "verifikasi_setuju&hasil=verifikasi_tolak"])
def test_detail_dengan_hasil_asal_404_identik(transfer, admin, hasil):
    order_id = order_menunggu(transfer)
    acuan = minta_admin(transfer, TAK_ADA, admin)
    kode, isi, _t = minta_admin(transfer, "%s?order=%s&hasil=%s" % (VERIFIKASI, order_id, hasil), admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_detail_hasil_tanpa_order_404(transfer, admin):
    assert minta_admin(transfer, "%s?hasil=verifikasi_setuju" % VERIFIKASI, admin)[0] == 404


# --- A5: markup ringkas -----------------------------------------------------------------

def _keputusan(isi: str) -> str:
    return isi[isi.index("<h2>Keputusan</h2>"):]


def test_form_tolak_di_dalam_details_dan_hanya_satu_kolom_sandi_di_luar(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order_id), admin)[1]
    kartu = _keputusan(isi)
    details = re.search(r'<details class="admin-form-tolak"><summary>Tolak bukti…</summary>(.*?)</details>', kartu, re.S)
    assert details and '<details class="admin-form-tolak" open' not in kartu
    assert 'action="%s"' % TOLAK in details.group(1) and 'name="alasan"' in details.group(1)
    luar = kartu.replace(details.group(0), "")
    assert luar.count('type="password"') == 1 and 'action="%s"' % SETUJUI in luar
    assert 'action="%s"' % TOLAK not in luar and 'name="alasan"' not in luar


def test_dua_form_tetap_terpisah_dengan_token_tinjauan_berbeda_dan_atribut_keamanan(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order_id), admin)[1]
    forms = form_detail(isi)
    assert set(forms) == {SETUJUI, TOLAK}
    assert forms[SETUJUI]["tinjauan"] != forms[TOLAK]["tinjauan"] and forms[SETUJUI]["csrf"] == forms[TOLAK]["csrf"]
    kartu = _keputusan(isi)
    assert kartu.count("<form ") == 2 and kartu.count("data-konfirmasi=") == 2
    assert kartu.count('type="password"') == 2 and kartu.count(" required") == 3   # 2 sandi + alasan
    assert kartu.count('name="csrf"') == 2 and kartu.count('name="tinjauan"') == 2


def test_form_tolak_dari_details_bekerja_ujung_ke_ujung_dan_lanjut(transfer, admin, dua_order):
    lama, baru = dua_order
    isi = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, baru), admin)[1]
    data = {**form_detail(isi)[TOLAK], "alasan": "Nominal kurang", "reauth": SANDI_ADMIN}
    kode, _i, tajuk = minta_admin(transfer, TOLAK, admin, data)
    assert (kode, _lokasi(tajuk)) == (303, "%s?order=%s&hasil=verifikasi_tolak" % (VERIFIKASI, lama))


def test_tiga_digit_terakhir_nominal_disorot_dan_teks_tetap_utuh(transfer, admin):
    order_id = order_menunggu(transfer)
    with ledger() as kon:
        nominal = kon.execute("SELECT nominal_transfer FROM transfer_tagihan WHERE order_id=?", (order_id,)).fetchone()[0]
    isi = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order_id), admin)[1]
    kode = "%03d" % (nominal - 49000)
    assert '<strong>Rp49.<mark class="admin-digit-unik">%s</mark></strong>' % kode in isi
    utuh = re.sub(r"<[^>]+>", "", isi[isi.index("Nominal yang harus masuk"):])
    assert utuh.startswith("Nominal yang harus masuk: Rp49.%s" % kode)      # tanpa jeda sisipan


def test_halaman_baca_saja_tanpa_form_tidak_punya_details_tolak(transfer):
    from admin_transfer_kit import minta_mentah
    from cek_http_kit import AKUN_ADMIN
    order_id = order_menunggu(transfer)
    isi = minta_mentah(transfer, "%s?order=%s" % (VERIFIKASI, order_id), AKUN_ADMIN)[1]
    assert '<details class="admin-form-tolak"' not in isi and 'type="password"' not in isi
