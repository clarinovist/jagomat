"""Halaman admin /admin/sakelar: lima sakelar fitur, optimistic concurrency, prasyarat transfer, guard.

Data SINTETIS. DB sakelar diarahkan ke tmp_path; nama, target, dan revisi hanya dari tinjauan bertanda tangan.
"""
from __future__ import annotations

import html
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_sakelar_http  # noqa: E402
import admin_security  # noqa: E402
import admin_store  # noqa: E402
import auth  # noqa: E402
import feature_switch as fs  # noqa: E402
import pesanan_rekening  # noqa: E402
import sakelar_registry  # noqa: E402
from admin_transfer_kit import (  # noqa: E402
    LINTAS_SITUS, TAK_ADA, id_admin, login_admin, minta_admin, token_rekening,
)
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    isi_rekening, jam, keluarga, minta_mentah, server, tertutup,
)

SAKELAR = "/admin/sakelar"
AKSI = "ubah_sakelar"
FUNNEL, TRANSFER = "FUNNEL_AKTIF", "PESANAN_TRANSFER_AKTIF"
CETAK, KALIMAT = "OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT"
POLA_FORM = re.compile(r'<form[^>]*action="/admin/sakelar"[^>]*>(.*?)</form>', re.S)
POLA_HIDDEN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)"')
AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)


@pytest.fixture(autouse=True)
def _db_sakelar_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_BERKAS_DB, str(tmp_path / "sakelar.db"))
    for nama in fs.NAMA_SAKELAR:
        monkeypatch.delenv(nama, raising=False)
    fs.bersihkan_cache()
    yield
    fs.bersihkan_cache()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


def _badan(isi: str) -> str:
    """Isi halaman tanpa blok CSS bingkai (yang memuat kata seperti name="reauth" dan disabled)."""
    return isi.rsplit("</style>", 1)[-1]


def _db() -> Path:
    return Path(fs._path_db(None))


def _stempel():
    """(baris sakelar, audit) mentah; kosong bila berkas belum ada."""
    if not _db().exists():
        return [], []
    with sqlite3.connect(_db()) as kon:
        kon.row_factory = sqlite3.Row
        return ([dict(r) for r in kon.execute("SELECT * FROM sakelar ORDER BY nama")],
                [dict(r) for r in kon.execute("SELECT * FROM audit_sakelar ORDER BY id")])


def _token(cookie, nama, aktif, revisi=1, aksi=AKSI):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": nama, "aktif": int(aktif), "target_revisi": revisi})}


def _kirim(server, cookie, nama, aktif, revisi=1, *, ganti=None, hapus=(), ekstra=None, headers=None, aksi=AKSI):
    data = {**_token(cookie, nama, aktif, revisi, aksi), **(ekstra or {}), **(ganti or {})}
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, SAKELAR, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def _funnel(monkeypatch, nyala: bool):
    if nyala:
        monkeypatch.setenv(FUNNEL, "1")
    else:
        monkeypatch.delenv(FUNNEL, raising=False)


def _rekening(terisi: bool):
    pesanan_rekening.migrasikan(admin_store.BAWAAN, sekarang=10)
    if terisi:
        isi_rekening(admin_store.BAWAAN)


def _kondisi(nama):
    return next(s for s in fs.daftar(seed=sakelar_registry.seed_env()) if s.nama == nama)


# --- akses ----------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_menyentuh_db_sakelar(tertutup, admin, akun, monkeypatch):
    def gagal(*_a, **_k):
        raise AssertionError("DB sakelar tidak boleh disentuh")

    acuan_get = minta_mentah(tertutup, TAK_ADA, akun)
    acuan_post = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    assert acuan_get[0] == acuan_post[0] == 404
    with monkeypatch.context() as ctx:
        ctx.setattr(admin_sakelar_http.feature_switch, "daftar", gagal)
        ctx.setattr(admin_sakelar_http.feature_switch, "ubah", gagal)
        assert minta_mentah(tertutup, SAKELAR, akun)[:2] == acuan_get[:2]
        assert minta_mentah(tertutup, SAKELAR, akun, {})[:2] == acuan_post[:2]
        assert minta_mentah(tertutup, SAKELAR, akun, _token(admin, FUNNEL, True))[:2] == acuan_post[:2]
    assert _stempel() == ([], [])


# --- tampilan -------------------------------------------------------------------------

def test_halaman_admin_memuat_semua_sakelar_dengan_form_dan_tanpa_rahasia(tertutup, admin, tmp_path):
    kode, isi, tajuk = minta_admin(tertutup, SAKELAR, admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    for nama in fs.NAMA_SAKELAR:
        assert html.escape(sakelar_registry.info(nama).label) in isi
    for nama_field in ("csrf", "tinjauan", "reauth"):
        assert 'name="%s"' % nama_field in isi
    assert len(POLA_FORM.findall(isi)) == 9 - 1  # transfer terkunci: funnel mati
    assert "nilai bawaan server, belum pernah diubah di sini" in isi
    assert SANDI_ADMIN not in isi and str(tmp_path) not in isi and "sakelar.db" not in isi
    assert 'href="/admin/sakelar" aria-current="page"' in isi


def test_halaman_basic_auth_baca_saja_tanpa_form(tertutup):
    kode, isi, _t = minta_mentah(tertutup, SAKELAR, AKUN_ADMIN)
    assert kode == 200 and 'name="reauth"' not in _badan(isi) and 'name="tinjauan"' not in _badan(isi)
    assert "baca-saja" in isi.lower()
    for nama in fs.NAMA_SAKELAR:
        assert html.escape(sakelar_registry.info(nama).label) in isi


@pytest.mark.parametrize("query", ["?hasil=sembarang", "?x=1", "?hasil=tersimpan&hasil=tersimpan",
                                   "?dukungan=sembarang", "?dukungan=", "?dukungan=tersimpan&dukungan=tersimpan"])
def test_query_tak_sah_404_identik(tertutup, admin, query):
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, SAKELAR + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_umpan_balik_tersimpan_hanya_dari_kode_dikenal(tertutup, admin):
    assert 'role="status"' in minta_admin(tertutup, SAKELAR + "?hasil=tersimpan", admin)[1]


def test_baris_transfer_menampilkan_prasyarat_dan_tombol_nonaktif_saat_belum_terpenuhi(tertutup, admin):
    isi = minta_admin(tertutup, SAKELAR, admin)[1]
    baris = isi.split('id="s-pesanan_transfer_aktif"', 1)[1].split("</section>", 1)[0]
    assert html.escape(sakelar_registry.info(TRANSFER).label) in baris
    assert "cek kemampuan" in baris.lower() and "rekening" in baris.lower()
    assert 'href="/admin/pesanan/rekening"' in baris  # prasyarat rekening menautkan halaman rekening
    assert "disabled" in baris and 'name="tinjauan"' not in baris


def test_baris_transfer_dapat_dinyalakan_saat_prasyarat_terpenuhi(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    _rekening(True)
    isi = minta_admin(tertutup, SAKELAR, admin)[1]
    assert len(POLA_FORM.findall(isi)) == 9 and "disabled" not in _badan(isi)


# --- ubah -----------------------------------------------------------------------------

def test_nyalakan_sah_redirect_tersimpan_db_menang_dan_audit_satu_baris(tertutup, admin):
    kode, isi, tajuk = _kirim(tertutup, admin, CETAK, True)
    assert (kode, isi, tajuk["Location"]) == (303, "", SAKELAR + "?hasil=tersimpan")
    kondisi = _kondisi(CETAK)
    assert (kondisi.aktif, kondisi.sumber, kondisi.revisi) == (True, "db", 2)
    baris, audit = _stempel()
    assert len(baris) == 9 and len(audit) == 1
    assert (audit[0]["nama"], audit[0]["lama"], audit[0]["baru"]) == (CETAK, 0, 1)
    assert audit[0]["actor_id"] == id_admin()


def test_form_dari_halaman_dapat_dikirim_apa_adanya(tertutup, admin):
    isi = minta_admin(tertutup, SAKELAR, admin)[1]
    form = next(f for f in POLA_FORM.findall(isi) if "Nyalakan" in f)
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(form)}
    assert set(data) == {"csrf", "tinjauan"}
    kode, _i, tajuk = minta_admin(tertutup, SAKELAR, admin, {**data, "reauth": SANDI_ADMIN})
    assert kode == 303 and tajuk["Location"].endswith("hasil=tersimpan")
    assert any(s.sumber == "db" and s.aktif for s in fs.daftar(seed=sakelar_registry.seed_env()))


def test_kirim_ulang_form_sama_konflik_ramah_tanpa_ubah_ulang(tertutup, admin):
    assert _kirim(tertutup, admin, CETAK, True)[0] == 303
    sebelum = _stempel()
    kode, isi, _t = _kirim(tertutup, admin, CETAK, True)
    assert kode == 409 and "Buka ulang" in isi and "Traceback" not in isi
    assert _stempel() == sebelum


def test_revisi_basi_konflik_409_tanpa_menimpa(tertutup, admin):
    assert _kirim(tertutup, admin, CETAK, True)[0] == 303
    assert _kirim(tertutup, admin, CETAK, False, revisi=2)[0] == 303
    sebelum = _stempel()
    assert _kirim(tertutup, admin, CETAK, True, revisi=2)[0] == 409
    assert _stempel() == sebelum


def test_mematikan_selalu_berhasil_walau_funnel_mati_dan_rekening_kosong(tertutup, admin, monkeypatch):
    monkeypatch.setenv(TRANSFER, "1")
    assert _kondisi(TRANSFER).aktif is True
    assert _kirim(tertutup, admin, TRANSFER, False)[0] == 303
    assert _kondisi(TRANSFER).aktif is False and _kondisi(TRANSFER).sumber == "db"


def test_mematikan_funnel_boleh_walau_transfer_menyala(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    monkeypatch.setenv(TRANSFER, "1")
    assert _kirim(tertutup, admin, FUNNEL, False)[0] == 303
    assert _kondisi(FUNNEL).aktif is False


# --- prasyarat transfer (ditegakkan di server saat POST) --------------------------------

def test_nyalakan_transfer_ditolak_saat_funnel_mati(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, False)
    _rekening(True)
    kode, isi, _t = _kirim(tertutup, admin, TRANSFER, True)
    assert kode == 409 and "cek kemampuan" in isi.lower() and "Traceback" not in isi
    assert _stempel() == ([], [])


def test_nyalakan_transfer_ditolak_saat_rekening_kosong(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    _rekening(False)
    kode, isi, _t = _kirim(tertutup, admin, TRANSFER, True)
    assert kode == 409 and "rekening" in isi.lower()
    assert _stempel() == ([], [])


def test_nyalakan_transfer_ditolak_saat_rekening_tak_terbaca(tertutup, admin, monkeypatch):
    """Skema rekening belum dipasang = galat baca = tolak, bukan 500."""
    _funnel(monkeypatch, True)
    kode, isi, _t = _kirim(tertutup, admin, TRANSFER, True)
    assert kode == 409 and "rekening" in isi.lower()
    assert _stempel() == ([], [])


def test_nyalakan_transfer_berhasil_saat_funnel_dan_rekening_terpenuhi(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    _rekening(True)
    assert _kirim(tertutup, admin, TRANSFER, True)[0] == 303
    assert _kondisi(TRANSFER).aktif is True and _kondisi(TRANSFER).sumber == "db"


def test_sakelar_lain_dinyalakan_tanpa_prasyarat(tertutup, admin):
    for nama in (FUNNEL, CETAK, KALIMAT):
        revisi = _kondisi(nama).revisi or 1
        assert _kirim(tertutup, admin, nama, True, revisi)[0] == 303
        assert _kondisi(nama).aktif is True


# --- guard ----------------------------------------------------------------------------

@pytest.mark.parametrize("kasus", ["tanpa_csrf", "csrf_salah", "tinjauan_palsu", "tanpa_tinjauan",
                                   "reauth_salah", "tanpa_reauth"])
def test_token_cacat_403_tanpa_mengubah_db(tertutup, admin, kasus):
    ganti, hapus = {
        "tanpa_csrf": ({}, ("csrf",)), "csrf_salah": ({"csrf": "rusak"}, ()),
        "tinjauan_palsu": ({"tinjauan": "palsu.palsu"}, ()), "tanpa_tinjauan": ({}, ("tinjauan",)),
        "reauth_salah": ({"reauth": "salah-sandi"}, ()), "tanpa_reauth": ({}, ("reauth",)),
    }[kasus]
    assert _kirim(tertutup, admin, CETAK, True, ganti=ganti, hapus=hapus)[0] == 403
    assert _stempel() == ([], [])


def test_tinjauan_aksi_lain_atau_sesi_lain_ditolak(tertutup, admin):
    assert _kirim(tertutup, admin, CETAK, True, aksi="ubah_rekening")[0] == 403
    data = {**token_rekening(admin, 0, "a" * 64)}
    assert minta_admin(tertutup, SAKELAR, admin, data)[0] == 403
    asing = _token("sesi-lain-sintetis", CETAK, True)
    assert minta_admin(tertutup, SAKELAR, admin, asing)[0] == 403
    assert minta_mentah(tertutup, SAKELAR, AKUN_ADMIN, _token(admin, CETAK, True))[0] == 403
    assert _stempel() == ([], [])


def test_permintaan_lintas_situs_403_tanpa_efek(tertutup, admin):
    assert _kirim(tertutup, admin, CETAK, True, headers=LINTAS_SITUS)[0] == 403
    assert _stempel() == ([], [])


@pytest.mark.parametrize("ekstra", [{"nama": KALIMAT}, {"aktif": "1"}, {"revisi": "9"},
                                    {"nama": KALIMAT, "aktif": "0", "revisi": "1"}])
def test_nama_target_revisi_tak_bisa_diganti_lewat_field_form(tertutup, admin, ekstra):
    kode, _i, _t = _kirim(tertutup, admin, CETAK, True, ekstra=ekstra)
    assert kode == 400
    assert _stempel() == ([], [])


@pytest.mark.parametrize("nama,aktif,revisi", [("PENDAMPING_AKTIF", 1, 1), (CETAK, 2, 1), (CETAK, 1, -1)])
def test_isi_tinjauan_tak_sah_400_bukan_500(tertutup, admin, nama, aktif, revisi):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    data = {"csrf": admin_http._csrf(akun, admin), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, admin, AKSI, {"target_id": nama, "aktif": aktif, "target_revisi": revisi})}
    assert minta_admin(tertutup, SAKELAR, admin, data)[0] == 400
    assert _stempel() == ([], [])


# --- DB sakelar rusak -----------------------------------------------------------------

def _rusakkan(isi=b"bukan sqlite"):
    _db().write_bytes(isi)


def test_db_rusak_halaman_503_jujur_tanpa_path_dan_tanpa_form(tertutup, admin, tmp_path):
    _rusakkan()
    kode, isi, _t = minta_admin(tertutup, SAKELAR, admin)
    assert kode == 503 and 'action="/admin/sakelar"' not in isi  # tanpa form sakelar
    assert str(tmp_path) not in isi and "sakelar.db" not in isi and "Traceback" not in isi
    # Halaman Pengaturan layanan lain tetap tampil: galat sakelar tidak membuang kesiapan/rekening.
    assert "Database sakelar tidak dapat dibaca" in isi
    assert 'id="kesiapan"' in isi and 'id="rekening"' in isi


def test_db_rusak_post_503_tanpa_path_dan_tanpa_efek(tertutup, admin, tmp_path):
    _rusakkan()
    kode, isi, _t = _kirim(tertutup, admin, CETAK, True)
    assert kode == 503 and str(tmp_path) not in isi and "sakelar.db" not in isi
    assert _db().read_bytes() == b"bukan sqlite"


def test_skema_db_tak_dikenal_503(tertutup, admin):
    with sqlite3.connect(_db()) as kon:
        kon.execute("PRAGMA user_version = 99")
    assert minta_admin(tertutup, SAKELAR, admin)[0] == 503


# --- rombak tampilan Pengaturan layanan (23 Nov 2026): ringkasan, checklist, tindakan terlipat --------------

def ui_id(nama: str) -> str:
    return "s-" + nama.lower()


def _utama(isi: str) -> str:
    return isi.split('<main id="konten-admin"', 1)[1].split("</main>", 1)[0]


def _kartu(isi: str, sid: str) -> str:
    return isi.split('id="%s"' % sid, 1)[1].split("</section>", 1)[0]


def _langkah(isi: str):
    return re.findall(r'<li class="admin-langkah-item (\S+)">', _kartu(isi, "buka-transfer"))


def test_ringkasan_aktif_menampilkan_status_semua_layanan_di_atas(tertutup, admin):
    kode, isi, _t = minta_admin(tertutup, SAKELAR, admin)
    utama = _utama(isi)
    ringkasan = _kartu(utama, "ringkasan")
    assert kode == 200 and utama.index('id="ringkasan"') < utama.index('id="penjualan"')
    for nama in fs.NAMA_SAKELAR:
        assert html.escape(sakelar_registry.info(nama).label) in ringkasan
    assert "Pembayaran QRIS (Midtrans)" in ringkasan and "Pendaftaran mandiri" in ringkasan
    assert 'admin-badge admin-status-besar">Tutup<' in ringkasan  # QRIS tahap nonaktif

    def badge(nama):
        baris = ringkasan.split('href="#%s"' % ui_id(nama), 1)[1].split("</li>", 1)[0]
        return re.sub(r"<[^>]+>", "", baris.split("</a>", 1)[1])

    awal = {s.nama: badge(s.nama) for s in fs.daftar(seed=sakelar_registry.seed_env())}
    assert all(awal[s.nama] == ("Aktif" if s.aktif else "Mati")
               for s in fs.daftar(seed=sakelar_registry.seed_env()))
    # Nyalakan satu fitur: ringkasan ikut berubah.
    assert awal[CETAK] == "Mati"
    assert _kirim(tertutup, admin, CETAK, True)[0] == 303
    ringkasan = _kartu(_utama(minta_admin(tertutup, SAKELAR, admin)[1]), "ringkasan")
    assert badge(CETAK) == "Aktif"


def test_kelompok_dan_urutan_kartu_di_halaman(tertutup, admin):
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    penjualan = utama.split('id="penjualan"', 1)[1].split('id="belajar"', 1)[0]
    belajar = utama.split('id="belajar"', 1)[1].split('id="pendaftaran"', 1)[0]
    urutan = [penjualan.index(t) for t in ('id="s-funnel_aktif"', 'id="pembayaran"', 'id="s-pesanan_transfer_aktif"',
                                           'id="buka-transfer"', 'id="rekening"')]
    assert urutan == sorted(urutan)
    for nama in ("OSN_LOMBA", "OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT"):
        assert 'id="s-%s"' % nama.lower() in belajar
    assert "Kesehatan sistem" in utama and utama.index('id="kesehatan"') > utama.index('id="pendaftaran"')


def test_checklist_transfer_skema_rekening_belum_dipasang(tertutup, admin):
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    assert _langkah(utama) == ["belum", "selesai", "belum"]
    assert "belum dipasang operator" in _kartu(utama, "buka-transfer")


def test_checklist_transfer_rekening_kosong_lalu_terisi(tertutup, admin, monkeypatch):
    _rekening(False)
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    assert _langkah(utama) == ["belum", "selesai", "belum"]
    assert 'href="/admin/pesanan/rekening">Isi di halaman rekening</a>' in _kartu(utama, "buka-transfer")
    isi_rekening(admin_store.BAWAAN)
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    assert _langkah(utama) == ["selesai", "selesai", "belum"]


def test_checklist_transfer_selesai_semua_setelah_transfer_dinyalakan(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    _rekening(True)
    assert _kirim(tertutup, admin, TRANSFER, True)[0] == 303
    assert _langkah(_utama(minta_admin(tertutup, SAKELAR, admin)[1])) == ["selesai", "selesai", "selesai"]


def test_checklist_qris_terbuka_belum_selesai_walau_transfer_menyala(tertutup, admin, monkeypatch):
    _funnel(monkeypatch, True)
    _rekening(True)
    monkeypatch.setattr(admin_sakelar_http.launch.billing, "kesiapan_penangan", lambda _p: {})
    assert _kirim(tertutup, admin, TRANSFER, True)[0] == 303
    ringkas_asli = admin_sakelar_http.launch.admin_operations.ringkasan

    def ringkas_checkout(*a, **kw):
        hasil = ringkas_asli(*a, **kw)
        return {**hasil, "pembayaran_config": {"tahap": "checkout", "revisi": 5}}

    monkeypatch.setattr(admin_sakelar_http.launch.admin_operations, "ringkasan", ringkas_checkout)
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    assert _langkah(utama) == ["selesai", "belum", "selesai"]
    assert 'admin-badge admin-status-besar bien">Buka<' in _kartu(utama, "pembayaran")


def test_sandi_tiap_form_hanya_di_dalam_details_terlipat(tertutup, admin):
    isi = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    sisa = re.sub(r'<details class="admin-aksi-ubah">.*?</details>', "", isi, flags=re.S)
    assert 'name="reauth"' not in sisa and 'type="password"' not in sisa
    assert isi.count('name="reauth"') >= 5  # empat sakelar bisa dinyalakan + QRIS + pendaftaran + dukungan
    assert '<details class="admin-aksi-ubah" open' not in isi


def test_mematikan_fitur_aktif_memakai_konfirmasi_dengan_akibat_dan_form_tetap_sama(tertutup, admin):
    assert _kirim(tertutup, admin, CETAK, True)[0] == 303
    isi = minta_admin(tertutup, SAKELAR, admin)[1]
    kartu = _kartu(isi, "s-osn_cetak_ringkas")
    info = sakelar_registry.info(CETAK)
    form = re.search(r"<form[^>]*>", kartu).group(0)
    assert html.unescape(re.search(r'data-konfirmasi="([^"]*)"', form).group(1)) == \
        "Matikan %s? %s" % (info.label, info.akibat_mati)
    assert 'class="admin-tombol admin-bahaya" type="submit">Matikan</button>' in kartu
    assert "data-konfirmasi" not in _kartu(isi, "s-osn_bank_kalimat")  # fitur mati: tanpa konfirmasi
    # Skrip konfirmasi yang sudah ada dimuat; tidak ada skrip baru pada halaman ini.
    assert "form[data-konfirmasi" in isi and isi.count("<script") == 1
    # Form dari halaman tetap bisa dikirim apa adanya (nama field tidak berubah).
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(kartu)}
    assert set(data) == {"csrf", "tinjauan"}
    kode, _i, tajuk = minta_admin(tertutup, SAKELAR, admin, {**data, "reauth": SANDI_ADMIN})
    assert kode == 303 and _kondisi(CETAK).aktif is False


def test_tidak_ada_baris_ai_dan_jargon_lama_di_halaman(tertutup, admin):
    utama = _utama(minta_admin(tertutup, SAKELAR, admin)[1])
    for teks in ("AI: tidak dipakai", 'id="ai"', 'href="/admin/ai"', "Sakelar pembayaran", "Env (belum diatur",
                 "Key/provider produksi", "Recovery exact-pair", "Kebijakan D8/D9", "Prasyarat tepercaya",
                 "migrator opt-in", "runtime produksi", "Perubahan pertama menyimpan nilai env"):
        assert teks not in utama, teks


def test_baca_saja_tanpa_cookie_tidak_punya_form_tombol_atau_konfirmasi(tertutup):
    kode, isi, _t = minta_mentah(tertutup, SAKELAR, AKUN_ADMIN)
    utama = _utama(isi)
    assert kode == 200 and "Tampilan baca-saja" in utama
    for terlarang in ("<form", "<button", "data-konfirmasi", 'name="reauth"', 'name="tinjauan"'):
        assert terlarang not in utama, terlarang
    assert 'id="ringkasan"' in utama and 'id="buka-transfer"' in utama  # status tetap terbaca
