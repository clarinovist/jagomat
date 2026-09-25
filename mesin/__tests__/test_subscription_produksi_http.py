"""Surface checkout produksi lewat HTTP loopback; seluruh state sintetis.

Runtime produksi diinjeksi ke server uji seperti pemasangan sesungguhnya; transport
palsu (tanpa socket), akun/enrollment/ledger sintetis, tanpa kredensial nyata.
"""

from dataclasses import replace
import re
from types import SimpleNamespace
import time

import pytest

import admin_store
import admin_subscription
import auth
import database
import sessions
import subscription as d
import subscription_produksi_http as h
import subscription_store as store
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_midtrans_contract import CFG
from test_subscription_http import FormParser, Provider

CFGP = replace(CFG, lingkungan="production")
ON = d.Sakelar(True, True, True, False)
AKTIF = {"provider_produksi": True, "callback": True, "recovery": True, "kebijakan": True}


def atur_tahap(tahap):
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap=?", (tahap,))


def jumlah_grant():
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0]


@pytest.fixture
def uji(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setattr(h, "_LAJU", {})
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "Profil Satu", "P3", pemilik="guru")
        sid2 = database.tambah_siswa(kon, "Profil Dua", "P4", pemilik="guru")
        asing = database.tambah_siswa(kon, "Profil Asing", "P5", pemilik="guru-lain")
    p = auth.autentikasi("guru", SANDI_GURU, auth.BERKAS_SANDI)
    cookie = sessions.buat_dari_principal(p)
    p_murid = auth.autentikasi("feby", SANDI_MURID, auth.BERKAS_SANDI)
    cookie_murid = sessions.buat_dari_principal(p_murid)
    auth.tambah_akun("guru-lain", SANDI_GURU, "guru", path=auth.BERKAS_SANDI)
    p_lain = auth.autentikasi("guru-lain", SANDI_GURU, auth.BERKAS_SANDI)
    cookie_lain = sessions.buat_dari_principal(p_lain)
    kini = int(time.time())
    store.enroll(admin_store.BAWAAN, p.id_akun, sumber_id="enroll_sintetis_1", asal="publik",
                 mulai=kini, peran="guru", sakelar=ON)
    provider = Provider()
    server.server.pembayaran_runtime = admin_subscription.RuntimePembayaran(
        CFGP, provider, d.Sakelar(True, True, True, False), dict(AKTIF))
    atur_tahap("checkout")
    k = SimpleNamespace(server=server, p=p, cookie=cookie, cookie_murid=cookie_murid,
                        cookie_lain=cookie_lain, sid=sid, sid2=sid2, asing=asing,
                        provider=provider)
    try:
        yield k
    finally:
        server.berhenti()


def minta(k, url="/langganan", cookie="guru", **kw):
    if cookie == "guru":
        kw.setdefault("cookie", k.cookie)
    elif cookie == "murid":
        kw.setdefault("cookie", k.cookie_murid)
    elif cookie == "lain":
        kw.setdefault("cookie", k.cookie_lain)
    elif cookie:
        kw.setdefault("cookie", cookie)
    if "data" in kw:
        kw.setdefault("headers", {"Origin": k.server.alamat})
    return k.server.minta(url, **kw)


def pesan(isi):
    m = re.search(r'role="alert">([^<]*)', isi or "")
    return m.group(1) if m else (isi or "")[:120]


def siapkan(k, profil=None):
    kode, isi, _ = minta(k)
    assert kode == 200, (kode, pesan(isi))
    form = FormParser(isi).forms["/langganan/siapkan"]
    kode, isi, _ = minta(k, "/langganan/siapkan", data=dict(form, profil=str(profil or k.sid)))
    assert kode == 200, (kode, pesan(isi))
    inv = re.search(r"/langganan/(inv_[0-9a-f]{32})", isi).group(1)
    return inv, isi


def buat(k, inv):
    _, isi, _ = minta(k, "/langganan/" + inv)
    aksi = next(a for a in FormParser(isi).forms if a.endswith("/buat"))
    kode, isi, _ = minta(k, aksi, data=FormParser(isi).forms[aksi])
    assert kode == 200, (kode, pesan(isi))
    return isi


def periksa(k, inv, isi):
    aksi = "/langganan/" + inv + "/periksa"
    kode, isi, _ = minta(k, aksi, data=FormParser(isi).forms[aksi])
    assert kode == 200, (kode, pesan(isi))
    return isi


def test_404_identik_anon_murid_invoice_asing_dan_tidak_ada(uji):
    k = uji
    kode, anon, _ = minta(k, "/langganan", cookie=False)
    assert kode == 404
    kode, murid, _ = minta(k, "/langganan", cookie="murid")
    assert kode == 404 and murid == anon
    kosong = "inv_" + "0" * 32
    kode, tidak_ada, _ = minta(k, "/langganan/" + kosong)
    assert kode == 404 and tidak_ada == anon
    inv, _ = siapkan(k)
    kode, asing, _ = minta(k, "/langganan/" + inv, cookie="lain")
    assert kode == 404 and asing == anon
    kode, anon_qr, _ = minta(k, "/langganan/" + inv + "/qr", cookie=False)
    assert kode == 404 and anon_qr == anon


def test_ringkasan_guru_memuat_teks_kebijakan_dan_profil_sendiri(uji):
    k = uji
    kode, isi, headers = minta(k)
    assert kode == 200
    assert "Profil Satu" in isi and "Profil Asing" not in isi
    assert "Midtrans (QRIS)" in isi
    assert "kunci-sintetis" not in isi
    assert "termasuk pajak bila berlaku" in isi
    assert 'action="/langganan/siapkan"' in isi
    assert k.provider.panggilan == []
    assert "no-store" in headers.get("Cache-Control", "")
    assert "img-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "<script" not in isi.lower()


def test_alur_lengkap_siapkan_buat_qr_periksa_lunas_sekali(uji):
    k = uji
    inv, isi = siapkan(k)
    assert "Rp35.000" in isi
    assert "termasuk pajak bila berlaku" in isi
    isi = buat(k, inv)
    assert "Menunggu pembayaran QRIS" in isi
    assert 'src="/langganan/' + inv + '/qr"' in isi
    kode, data, headers = minta(k, "/langganan/" + inv + "/qr", biner=True)
    assert kode == 200 and data == b"PNG-SINTETIS"
    assert headers.get("Content-Type") == "image/png"
    assert k.provider.url_gambar and k.provider.url_gambar[0].endswith("/qr-code")
    k.provider.status = "settlement"
    isi = periksa(k, inv, isi)
    assert "Pembayaran diterima" in isi
    assert "bukan faktur pajak" in isi and "Merchant: M_SINTETIS" in isi
    assert jumlah_grant() == 1
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_receipt").fetchone()[0] == 1
    tok = h._token(k.cookie, k.p, "periksa", inv)
    kode, _, _ = minta(k, "/langganan/" + inv + "/periksa", data={"token": tok})
    assert kode == 200
    assert jumlah_grant() == 1
    assert sum(1 for r in k.provider.panggilan if r.metode == "POST") == 1


def test_gating_tahap_nonaktif_dan_rekonsiliasi(uji):
    k = uji
    atur_tahap("nonaktif")
    kode, isi, _ = minta(k)
    assert kode == 200 and "Belum aktif" in isi and "Profil Satu" not in isi
    kode, isi, _ = minta(k, "/langganan/siapkan", data={"token": "x", "profil": str(k.sid)})
    assert kode == 409 and "Belum aktif" in isi
    atur_tahap("rekonsiliasi")
    kode, isi, _ = minta(k)
    assert kode == 200 and "Pembayaran belum dibuka" in isi
    assert "/langganan/siapkan" not in isi
    kode, _, _ = minta(k, "/langganan/siapkan",
                       data={"token": h._token(k.cookie, k.p, "siapkan"), "profil": str(k.sid)})
    assert kode == 409


def test_turun_tahap_menyembunyikan_buat_dan_mematikan_qr(uji):
    k = uji
    inv, isi = siapkan(k)
    isi = buat(k, inv)
    atur_tahap("rekonsiliasi")
    kode, isi, _ = minta(k, "/langganan/" + inv)
    assert kode == 200
    assert "/buat" not in isi
    assert ("/langganan/" + inv + "/periksa") in isi
    assert jumlah_grant() == 0


def test_qr_hanya_saat_pending(uji):
    k = uji
    inv, _ = siapkan(k)
    kode, _, _ = minta(k, "/langganan/" + inv + "/qr")
    assert kode == 404
    buat(k, inv)
    kode, _, _ = minta(k, "/langganan/" + inv + "/qr", biner=True)
    assert kode == 200
    k.provider.status = "settlement"
    kode, _, _ = minta(k, "/langganan/" + inv + "/qr")
    assert kode == 404


def test_token_wajib_terikat_sesi_aksi_dan_invoice(uji):
    k = uji
    kode, _, _ = minta(k, "/langganan/siapkan", data={"profil": str(k.sid)})
    assert kode == 400
    kode, _, _ = minta(k, "/langganan/siapkan", data={"token": "x" * 64, "profil": str(k.sid)})
    assert kode == 403
    kode, _, _ = minta(k, "/langganan/siapkan",
                       data={"token": h._token("sesi-palsu", k.p, "siapkan"), "profil": str(k.sid)})
    assert kode == 403
    inv, _ = siapkan(k)
    kode, _, _ = minta(k, "/langganan/" + inv + "/periksa",
                       data={"token": h._token(k.cookie, k.p, "siapkan")})
    assert kode == 403
    kode, _, _ = minta(k, "/langganan/siapkan", data={"token": h._token(k.cookie, k.p, "siapkan"),
                                                     "profil": str(k.sid)},
                       headers={"Origin": "https://jahat.example"})
    assert kode == 403


def test_profil_asing_dan_tanpa_enrollment_tidak_bocor(uji):
    k = uji
    _, anon, _ = minta(k, "/langganan", cookie=False)
    tok = h._token(k.cookie, k.p, "siapkan")
    kode, isi, _ = minta(k, "/langganan/siapkan", data={"token": tok, "profil": str(k.asing)})
    assert kode == 404 and isi == anon
    kode, isi, _ = minta(k, "/langganan/siapkan",
                        data={"token": tok, "profil": str(k.sid), "tambahan": "x"})
    assert kode == 400


def test_tanpa_runtime_produksi_rute_tidak_dilayani(uji):
    k = uji
    del k.server.server.pembayaran_runtime
    kode, _, _ = minta(k)
    assert kode == 404
    assert h.ada(SimpleNamespace(server=k.server.server)) is False


def test_tautan_akun_muncul_hanya_saat_runtime_terpasang(uji):
    k = uji
    kode, isi, _ = minta(k, "/akun")
    assert kode == 200 and ">Langganan</a>" in isi
    del k.server.server.pembayaran_runtime
    kode, isi, _ = minta(k, "/akun")
    assert kode == 200 and 'href="/langganan"' not in isi


def test_gambar_menolak_url_di_luar_allowlist(uji):
    import midtrans_contract as midtrans
    k = uji
    penangan = SimpleNamespace(server=k.server.server)
    dengan = h._runtime(penangan)
    assert dengan is not None
    for url in ("https://jahat.example/v2/qris/trx/qr-code",
                "https://api.midtrans.com/evil",
                "https://api.midtrans.com/v2/qris/trx/qr-code?x=1"):
        with pytest.raises(midtrans.KontrakTidakSah):
            h._gambar(dengan, url)
    assert k.provider.url_gambar == []


def test_batas_laju_per_akun(uji):
    k = uji
    for _ in range(h.BATAS_LAJU):
        kode, _, _ = minta(k)
        assert kode == 200
    kode, isi, _ = minta(k)
    assert kode == 429 and "Terlalu banyak" in isi
