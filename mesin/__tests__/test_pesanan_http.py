"""Rute pesanan (Fase 3c-3) bagian guard: gerbang, peran, kepemilikan, token, form, laju.

Server HTTP loopback, runtime + provider PALSU, data sintetis di tmp_path. Alur uang
(create/QR/status/ulang) ada di test_pesanan_http_alur.py. Yang dibuktikan di sini:
tiap penolakan tidak punya efek samping (ledger kosong, provider tidak dipanggil).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_http  # noqa: E402
import funnel_pages  # noqa: E402
import kontak_http  # noqa: E402
import pesanan_http  # noqa: E402
import pesanan_pages  # noqa: E402
from pesanan_http_kit import (  # noqa: E402
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, BUAT, KOSONG, NAMA_A, PERIKSA, PESAN, QR, SIAP,
    STATUS, ULANG, atur_tahap, bayar, jam, keadaan_ledger,
    keluarga, kirim, minta_mentah, pasang_runtime, pesan, server, siap_pesan, tertutup, token,
)

POST_RUTE = (PESAN, PERIKSA, ULANG, BUAT)


def _acuan(server, *, post):
    kode, isi, _t = (minta_mentah(server, "/rute-tidak-ada", AKUN_A, {"x": "1"}) if post
                     else minta_mentah(server, "/rute-tidak-ada", AKUN_A))
    assert kode == 404
    return kode, isi


def _tanpa_efek(server):
    assert keadaan_ledger() == KOSONG
    assert server.provider.panggilan == []


# --- gerbang pembayaran (tiga syarat) --------------------------------------

def test_funnel_saja_tidak_membuka_pembayaran_get_halaman_jujur(tertutup):
    siap_pesan(tertutup)
    kode, isi, tajuk = minta_mentah(tertutup, STATUS, AKUN_A)
    assert kode == 200 and "no-store" in tajuk.get("Cache-Control", "")
    assert pesanan_pages.COPY_TUTUP in isi.replace("&#x27;", "'")
    assert "<form" not in isi.split("</header>", 1)[1] and NAMA_A not in isi
    assert minta_mentah(tertutup, QR, AKUN_A)[:2] == _acuan(tertutup, post=False)
    _tanpa_efek(tertutup)


@pytest.mark.parametrize("jalur", POST_RUTE)
def test_funnel_saja_post_diperlakukan_rute_tak_dikenal_tanpa_efek(tertutup, jalur):
    siap_pesan(tertutup)
    tok = token(AKUN_A, pesanan_http.AKSI_RUTE[jalur])
    acuan = _acuan(tertutup, post=True)
    kode, isi, _t = minta_mentah(tertutup, jalur, AKUN_A, {"token": tok})
    assert (kode, isi) == acuan
    _tanpa_efek(tertutup)


def _buka_dengan(server, *, funnel="1", runtime=True, tahap="checkout", kesiapan=None, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", funnel)
    atur_tahap(tahap)
    if runtime:
        pasang_runtime(server, server.provider, kesiapan=kesiapan)


@pytest.mark.parametrize("ganti", [
    {"funnel": "0"}, {"funnel": ""}, {"runtime": False}, {"tahap": "nonaktif"},
    {"tahap": "rekonsiliasi"}, {"kesiapan": {**SIAP, "callback": False}},
    {"kesiapan": {**SIAP, "recovery": False}}, {"kesiapan": {**SIAP, "provider_produksi": False}},
])
def test_salah_satu_syarat_gerbang_hilang_semua_tertutup_fail_closed(tertutup, monkeypatch, ganti):
    siap_pesan(tertutup)
    _buka_dengan(tertutup, monkeypatch=monkeypatch, **ganti)
    kode, isi, _t = minta_mentah(tertutup, STATUS, AKUN_A)
    assert kode == 200 and pesanan_pages.COPY_TUTUP in isi  # GET tetap halaman jujur, bukan galat
    acuan = _acuan(tertutup, post=True)
    for jalur in POST_RUTE:
        tok = token(AKUN_A, pesanan_http.AKSI_RUTE[jalur])
        kode, isi, _t = minta_mentah(tertutup, jalur, AKUN_A, {"token": tok})
        assert (kode, isi) == acuan, jalur
    assert minta_mentah(tertutup, QR, AKUN_A)[0] == 404
    _tanpa_efek(tertutup)


def test_ketiga_syarat_terpenuhi_gerbang_terbuka(bayar):
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    assert keadaan_ledger()["pesanan_order"] == 1


def test_runtime_sandbox_atau_transport_bukan_callable_menutup_gerbang(tertutup, monkeypatch):
    import midtrans_contract as m
    from pesanan_http_kit import MERCHANT
    siap_pesan(tertutup)
    atur_tahap("checkout")
    pasang_runtime(tertutup, tertutup.provider)
    asli = tertutup.server.pembayaran_runtime
    for rusak in (type(asli)(m.Konfigurasi("sandbox", "SB-Mid-server-sintetis-0001", MERCHANT),
                              asli.transport, asli.sakelar, asli.kesiapan),
                  type(asli)(asli.config, "bukan-callable", asli.sakelar, asli.kesiapan)):
        tertutup.server.pembayaran_runtime = rusak
        assert pesan(tertutup)[:2] == _acuan(tertutup, post=True)
    _tanpa_efek(tertutup)


def test_get_paket_coba_pesan_terbuka_303_ke_status_dan_paket_coba_publik_tidak_tertukar(bayar):
    # gerbang terbuka: GET /paket-coba/pesan = PRG 303 ke /pesanan (tombol kembali), tanpa efek
    kode, isi, tajuk = minta_mentah(bayar, PESAN, AKUN_A)
    assert (kode, isi, tajuk["Location"]) == (303, "", STATUS)
    _tanpa_efek(bayar)
    kode, isi, _t = minta_mentah(bayar, "/paket-coba")  # publik exact, anonim
    assert kode == 200 and funnel_pages.COPY_HARGA in isi
    assert PESAN not in isi and "<form" not in isi.split("</header>", 1)[-1]
    kode, _isi, _t = minta_mentah(bayar, "/paket-coba/lain", AKUN_A)
    assert kode == 404


# --- peran, kepemilikan -----------------------------------------------------

@pytest.mark.parametrize("jalur", [STATUS, QR])
def test_admin_get_404_identik_rute_tak_dikenal(bayar, jalur):
    siap_pesan(bayar)
    acuan = minta_mentah(bayar, "/rute-tidak-ada", AKUN_ADMIN)
    assert minta_mentah(bayar, jalur, AKUN_ADMIN)[:2] == acuan[:2] and acuan[0] == 404


@pytest.mark.parametrize("jalur", POST_RUTE)
def test_admin_post_404_identik_rute_tak_dikenal_tanpa_efek(bayar, jalur):
    siap_pesan(bayar)
    acuan = minta_mentah(bayar, "/rute-tidak-ada", AKUN_ADMIN, {"x": "1"})
    kode, isi, _t = minta_mentah(bayar, jalur, AKUN_ADMIN, {"token": "1.abc"})
    assert (kode, isi) == acuan[:2] and kode == 404
    _tanpa_efek(bayar)


@pytest.mark.parametrize("jalur", [STATUS, QR])
def test_anonim_dan_murid_ditahan_palang_sandi_get(bayar, jalur):
    assert minta_mentah(bayar, jalur)[0] == 401
    assert minta_mentah(bayar, jalur, AKUN_MURID)[0] == 401


@pytest.mark.parametrize("jalur", POST_RUTE)
def test_anonim_dan_murid_ditahan_palang_sandi_post(bayar, jalur):
    assert minta_mentah(bayar, jalur, None, {"token": "x"})[0] == 401
    assert minta_mentah(bayar, jalur, AKUN_MURID, {"token": "x"})[0] == 401
    _tanpa_efek(bayar)


def test_dua_akun_terpisah_tidak_saling_lihat_order(bayar):
    siap_pesan(bayar, AKUN_A)
    siap_pesan(bayar, AKUN_B)
    assert pesan(bayar, AKUN_A)[0] == 303 and pesan(bayar, AKUN_B)[0] == 303
    assert keadaan_ledger()["pesanan_order"] == 2
    kode_a, isi_a, _t = minta_mentah(bayar, STATUS, AKUN_A)
    kode_b, isi_b, _t = minta_mentah(bayar, STATUS, AKUN_B)
    assert kode_a == kode_b == 200
    assert NAMA_A in isi_a and "Anak Sintetis Beta" not in isi_a
    assert "Anak Sintetis Beta" in isi_b and NAMA_A not in isi_b
    assert minta_mentah(bayar, QR, AKUN_A)[0] == 200


def test_akun_lain_tanpa_cek_tidak_dapat_order_dan_tanpa_efek(bayar):
    siap_pesan(bayar, AKUN_A)
    kode, isi, _t = pesan(bayar, AKUN_B)  # AKUN_B: anak ada, cek belum mulai
    assert kode == 409 and pesanan_pages.COPY_CEK_BELUM_SELESAI in isi
    assert keadaan_ledger() == KOSONG and bayar.provider.panggilan == []


def test_id_akun_dari_form_ditolak_dan_tidak_dipakai(bayar):
    siap_pesan(bayar, AKUN_A)
    siap_pesan(bayar, AKUN_B)
    from cek_http_kit import id_akun
    kode, _isi, _t = pesan(bayar, AKUN_A, ekstra={"id_akun": id_akun(AKUN_B)})
    assert kode == 400
    _tanpa_efek(bayar)


# --- token form ---------------------------------------------------------------

def _jaga(server, jalur, kode_harap, **kw):
    kode, isi, _t = kirim(server, jalur, AKUN_A, **kw)
    assert kode == kode_harap
    _tanpa_efek(server)
    return isi


@pytest.mark.parametrize("jalur", POST_RUTE)
@pytest.mark.parametrize("tok", ["", "1.deadbeef", "x" * 300, "bukan-token"])
def test_token_salah_ditolak_tanpa_efek(bayar, jalur, tok):
    siap_pesan(bayar)
    _jaga(bayar, jalur, 403, tok=tok)


@pytest.mark.parametrize("jalur", POST_RUTE)
def test_token_aksi_lain_tidak_berlaku_lintas_aksi(bayar, jalur):
    siap_pesan(bayar)
    for aksi in ("pesan", "periksa", "ulang", "buat", "cek-mulai", "cek-tautan"):
        if aksi == pesanan_http.AKSI_RUTE[jalur]:
            continue
        tok = (token(AKUN_A, aksi) if aksi in pesanan_http.AKSI_RUTE.values()
               else cek_http.buat_token(_principal(AKUN_A), None, aksi))
        _jaga(bayar, jalur, 403, tok=tok)


def _principal(akun):
    import sessions
    return sessions.principal_basic(*akun)


def test_token_kontak_tidak_berlaku(bayar):
    siap_pesan(bayar)
    tok_kontak = kontak_http.buat_token(_principal(AKUN_A), None)
    for jalur in POST_RUTE:
        _jaga(bayar, jalur, 403, tok=tok_kontak)


def test_token_milik_akun_lain_ditolak(bayar):
    siap_pesan(bayar)
    _jaga(bayar, PESAN, 403, tok=token(AKUN_B, "pesan"))


def test_token_kedaluwarsa_ditolak(bayar, monkeypatch):
    siap_pesan(bayar)
    tok = token(AKUN_A, "pesan")
    asli = time.time
    monkeypatch.setattr(pesanan_http.time, "time", lambda: asli() + pesanan_http.UMUR_TOKEN_DETIK + 5)
    _jaga(bayar, PESAN, 403, tok=tok)


def test_token_terikat_sesi(bayar):
    siap_pesan(bayar)
    _jaga(bayar, PESAN, 403, tok=token(AKUN_A, "pesan", sesi="sesi-lain"))


# --- whitelist form -----------------------------------------------------------

@pytest.mark.parametrize("field", ["rupiah", "nominal", "harga", "id_akun", "order_id",
                                   "siswa_id", "nama", "status", "transaction_status", "x"])
@pytest.mark.parametrize("jalur", POST_RUTE)
def test_field_asing_ditolak_400_tanpa_efek(bayar, jalur, field):
    siap_pesan(bayar)
    _jaga(bayar, jalur, 400, ekstra={field: "1"})


@pytest.mark.parametrize("jalur", POST_RUTE)
def test_token_hilang_atau_ganda_ditolak_400(bayar, jalur):
    siap_pesan(bayar)
    _jaga(bayar, jalur, 400, hapus=("token",), ekstra={"lain": "1"})
    tok = token(AKUN_A, pesanan_http.AKSI_RUTE[jalur])
    kode, _isi, _t = minta_mentah(bayar, jalur, AKUN_A, {"token": [tok, tok]})
    assert kode == 400
    _tanpa_efek(bayar)


# --- pembatas laju -------------------------------------------------------------

def test_laju_per_akun_lewat_batas_429_tanpa_efek(bayar, monkeypatch):
    siap_pesan(bayar)
    monkeypatch.setattr(pesanan_http, "BATAS_AKUN", 2)
    for _ in range(2):
        assert kirim(bayar, PERIKSA, AKUN_A)[0] == 303
    awal = (keadaan_ledger(), len(bayar.provider.panggilan))
    kode, isi, _t = pesan(bayar)
    assert kode == 429 and "Terlalu banyak" in isi
    assert (keadaan_ledger(), len(bayar.provider.panggilan)) == awal


def test_laju_per_ip_berlaku_lintas_akun(bayar, monkeypatch):
    siap_pesan(bayar, AKUN_A)
    siap_pesan(bayar, AKUN_B)
    monkeypatch.setattr(pesanan_http, "BATAS_IP", 2)
    assert kirim(bayar, PERIKSA, AKUN_A)[0] == 303
    assert kirim(bayar, PERIKSA, AKUN_B)[0] == 303
    assert pesan(bayar, AKUN_B)[0] == 429
    assert pesan(bayar, AKUN_A)[0] == 429
    assert keadaan_ledger() == KOSONG


def test_laju_get_status_tidak_memblokir_halaman_hanya_pemeriksaan_provider(bayar, monkeypatch):
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    monkeypatch.setattr(pesanan_http, "BATAS_AKUN", 1)
    pesanan_http._laju.clear()
    assert minta_mentah(bayar, STATUS, AKUN_A)[0] == 200
    panggilan = len(bayar.provider.panggilan)
    kode, isi, _t = minta_mentah(bayar, STATUS, AKUN_A)
    assert kode == 200 and len(bayar.provider.panggilan) == panggilan
    assert pesanan_pages.COPY_BELUM_TERPERIKSA in isi
