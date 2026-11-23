"""Admin langganan Latihan Harian (F5) lewat HTTP nyata: antrean, detail, pratinjau, setujui/tolak, keamanan aksi.

Efek (atau ketiadaannya) dibuktikan dari DB belajar sintetis, bukan hanya status HTTP. Pola keamanan sama dengan
verifikasi transfer: sesi berkuki, CSRF, tinjauan bertanda tangan (order + bukti terakhir), sandi admin ulang.
"""
from __future__ import annotations

import html

import pytest

import admin_http
import admin_security
import akses_harian
import auth
from admin_pesanan_kit import login_admin, minta_admin
from bukti_kit import JPEG, PNG
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN
from harian_kit import (AWAL, KOSONG, buat, buat_murid, hidup, hitung, jam, mati, minta_mentah, semua_berkas,  # noqa: F401
                        server, unggah)

DAFTAR = "/admin/langganan"
DETAIL = DAFTAR + "/verifikasi"
BUKTI = DAFTAR + "/bukti"
SETUJUI = DAFTAR + "/setujui"
TOLAK = DAFTAR + "/tolak"
TAK_ADA = "/admin/tidak-ada"
AKSI = {SETUJUI: "setujui_langganan", TOLAK: "tolak_langganan"}
ORDER_ASING = "hor_" + "0" * 32


@pytest.fixture()
def admin(hidup):
    return login_admin(hidup)


@pytest.fixture()
def menunggu(hidup):
    """Satu murid dengan tagihan bulanan dan satu bukti menunggu; mengembalikan (murid, order_id)."""
    hidup.murid = buat_murid(hidup, "murid-a", "Anak Alfa")
    assert buat(hidup, hidup.murid)[0] == 303
    assert unggah(hidup, hidup.murid, JPEG)[0] == 303
    return hidup.murid, order_id(hidup)


def order_id(server) -> str:
    with server.buka() as kon:
        return kon.execute("SELECT id FROM harian_order ORDER BY dibuat DESC,id DESC").fetchone()[0]


def bukti_terakhir(server, oid) -> int:
    with server.buka() as kon:
        return kon.execute("SELECT MAX(id) FROM harian_bukti WHERE order_id=?", (oid,)).fetchone()[0]


def token(cookie, aksi, oid, bukti_id, *, sandi=SANDI_ADMIN):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": sandi,
            "tinjauan": admin_security.buat_tinjauan(akun, cookie, aksi, {"target_id": oid, "target_revisi": bukti_id})}


def putus(server, cookie, jalur, oid, *, bukti_id=None, ekstra=None, ganti=None, hapus=(), headers=None,
          alasan="Nominal tidak sesuai", aksi=None):
    data = token(cookie, aksi or AKSI[jalur], oid, bukti_terakhir(server, oid) if bukti_id is None else bukti_id)
    if jalur == TOLAK:
        data["alasan"] = alasan
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def keadaan(server):
    with server.buka() as kon:
        return (tuple(tuple(r) for r in kon.execute("SELECT * FROM harian_verifikasi")),
                tuple(tuple(r) for r in kon.execute("SELECT * FROM harian_akses")))


# --- sakelar dan palang ----------------------------------------------------------------------

def _matikan_sakelar(monkeypatch):
    monkeypatch.delenv("LATIHAN_HARIAN")


def test_sakelar_mati_antrean_detail_dan_pratinjau_admin_tetap_terbuka(hidup, menunggu, admin, monkeypatch):
    _, oid = menunggu
    _matikan_sakelar(monkeypatch)
    assert not akses_harian.aktif()
    kode, isi, _ = minta_admin(hidup, DAFTAR, admin)
    assert kode == 200 and oid in isi
    kode, isi, _ = minta_admin(hidup, "%s?order=%s" % (DETAIL, oid), admin)
    assert kode == 200 and 'action="%s"' % SETUJUI in isi
    kode, _, tajuk = minta_admin(hidup, "%s?id=%d" % (BUKTI, bukti_terakhir(hidup, oid)), admin)
    assert kode == 200 and tajuk["Content-Type"] == "image/jpeg"


def test_sakelar_mati_admin_tetap_bisa_setujui_bukti_yang_sudah_masuk(hidup, menunggu, admin, monkeypatch):
    murid, oid = menunggu
    _matikan_sakelar(monkeypatch)
    kode, _, tajuk = putus(hidup, admin, SETUJUI, oid)
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=verifikasi_setuju")
    with hidup.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM harian_akses WHERE siswa_id=?", (murid.siswa_id,)).fetchone()[0] == 1


def test_sakelar_mati_admin_tetap_bisa_tolak_bukti_yang_sudah_masuk(hidup, menunggu, admin, monkeypatch):
    _, oid = menunggu
    _matikan_sakelar(monkeypatch)
    kode, _, tajuk = putus(hidup, admin, TOLAK, oid)
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=verifikasi_tolak")
    with hidup.buka() as kon:
        assert kon.execute("SELECT keputusan FROM harian_verifikasi").fetchall()[0][0] == "tolak"


@pytest.mark.parametrize("jalur", [DAFTAR, DETAIL + "?order=" + ORDER_ASING, BUKTI + "?id=1"])
def test_sakelar_mati_non_admin_tetap_404_identik_rute_tak_dikenal(mati, jalur):
    acuan = minta_mentah(mati, TAK_ADA, None)[:2]
    assert minta_mentah(mati, jalur, None)[:2] == acuan
    assert minta_mentah(mati, jalur, ("guru", "sandi-guru-panjang-123"))[:2] == acuan
    assert minta_mentah(mati, jalur, ("feby", "sandi-feby-12345"))[:2] == acuan
    for aksi in (SETUJUI, TOLAK):
        assert minta_mentah(mati, aksi, None, {"x": "1"})[:2] == minta_mentah(mati, TAK_ADA, None, {"x": "1"})[:2]


def test_menu_admin_memuat_butir_langganan_harian(hidup):
    cookie = login_admin(hidup)
    kode, isi, _ = minta_admin(hidup, DAFTAR, cookie)
    assert kode == 200 and 'href="/admin/langganan"' in isi and 'aria-current="page"' in isi


@pytest.mark.parametrize("jalur", [DAFTAR, DETAIL + "?order=" + ORDER_ASING, BUKTI + "?id=1"])
def test_anonim_guru_dan_murid_404_identik_tanpa_menyentuh_data(hidup, jalur):
    acuan = minta_mentah(hidup, TAK_ADA, None)[:2]
    assert minta_mentah(hidup, jalur, None)[:2] == acuan
    assert minta_mentah(hidup, jalur, ("guru", "sandi-guru-panjang-123"))[:2] == acuan
    assert minta_mentah(hidup, jalur, ("feby", "sandi-feby-12345"))[:2] == acuan


# --- antrean, detail, pratinjau --------------------------------------------------------------------

def test_antrean_memuat_paket_nominal_persis_dan_tautan_tanpa_nama_anak(hidup, menunggu, admin):
    _, oid = menunggu
    isi = minta_admin(hidup, DAFTAR, admin)[1]
    assert "Bulanan" in isi and 'href="%s?order=%s"' % (DETAIL, oid) in isi
    with hidup.buka() as kon:
        nominal = kon.execute("SELECT nominal_transfer FROM harian_tagihan").fetchone()[0]
    assert 'Rp39.<mark class="admin-digit-unik">%03d</mark>' % (nominal - 39000) in isi
    assert "Anak Alfa" not in isi and "murid-a" not in isi


def test_antrean_kosong_pesan_jujur(hidup, admin):
    assert "Tidak ada bukti langganan yang menunggu" in minta_admin(hidup, DAFTAR, admin)[1]


def test_antrean_terlama_dulu(hidup, admin, jam):
    a = buat_murid(hidup, "murid-a", "Anak A")
    b = buat_murid(hidup, "murid-b", "Anak B")
    buat(hidup, a)
    buat(hidup, b)
    jam.maju_jam(1)
    unggah(hidup, b, JPEG)
    jam.maju_jam(1)
    unggah(hidup, a, PNG)
    with hidup.buka() as kon:
        urut = [r[0] for r in kon.execute("SELECT o.siswa_id FROM harian_order o ORDER BY o.siswa_id")]
    isi = minta_admin(hidup, DAFTAR, admin)[1]
    with hidup.buka() as kon:
        oid_b = kon.execute("SELECT id FROM harian_order WHERE siswa_id=?", (b.siswa_id,)).fetchone()[0]
        oid_a = kon.execute("SELECT id FROM harian_order WHERE siswa_id=?", (a.siswa_id,)).fetchone()[0]
    assert isi.index(oid_b) < isi.index(oid_a) and urut


def test_detail_dua_form_dengan_token_dan_pratinjau(hidup, menunggu, admin):
    _, oid = menunggu
    kode, isi, _ = minta_admin(hidup, "%s?order=%s" % (DETAIL, oid), admin)
    assert kode == 200
    assert 'action="%s"' % SETUJUI in isi and 'action="%s"' % TOLAK in isi
    assert isi.count('name="reauth"') >= 2 and 'name="tinjauan"' in isi and 'name="csrf"' in isi
    assert "%s?id=%d" % (BUKTI, bukti_terakhir(hidup, oid)) in isi
    assert "Menunggu verifikasi" in isi


@pytest.mark.parametrize("query", ["", "?order=x", "?order=" + ORDER_ASING, "?order=ord_" + "0" * 32,
                                   "?order=" + "hor_" + "A" * 32, "?x=1"])
def test_detail_tidak_sah_atau_tak_dikenal_404_identik(hidup, admin, query):
    acuan = minta_admin(hidup, TAK_ADA, admin)
    kode, isi, _ = minta_admin(hidup, DETAIL + query, admin)
    assert (kode, isi) == acuan[:2]


def test_pratinjau_bukti_tipe_header_dan_isi(hidup, menunggu, admin):
    _, oid = menunggu
    kode, isi, tajuk = minta_admin(hidup, "%s?id=%d" % (BUKTI, bukti_terakhir(hidup, oid)), admin)
    assert kode == 200 and tajuk["Content-Type"] == "image/jpeg"
    assert tajuk["X-Content-Type-Options"] == "nosniff" and "sandbox" in tajuk["Content-Security-Policy"]
    assert 'filename="bukti-transfer.jpg"' in tajuk["Content-Disposition"]


@pytest.mark.parametrize("query", ["?id=99999", "?id=0", "?id=abc", "?id=1&x=2", ""])
def test_pratinjau_tak_dikenal_atau_tak_sah(hidup, admin, query):
    kode, _, _ = minta_admin(hidup, BUKTI + query, admin)
    assert kode == 404


# --- keputusan ----------------------------------------------------------------------------------

def test_setujui_tulis_verifikasi_dan_akses_tanggal_benar(hidup, menunggu, admin, jam):
    murid, oid = menunggu
    jam.maju_jam(2)
    kode, _, tajuk = putus(hidup, admin, SETUJUI, oid)
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=verifikasi_setuju")
    with hidup.buka() as kon:
        baris = kon.execute("SELECT mulai,berakhir,siswa_id FROM harian_akses").fetchone()
        assert tuple(baris) == ("2026-11-23T05:00:00", "2026-12-23T05:00:00", murid.siswa_id)
        akses = akses_harian.akses(kon, murid.siswa_id, "2026-11-23T06:00:00")
        assert (akses.sumber, akses.tanpa_batas) == ("langganan", True)
        assert akses_harian.akses(kon, murid.siswa_id, "2026-12-23T05:00:00").sumber == "gratis"
    assert "disetujui" in minta_admin(hidup, DAFTAR + "?hasil=verifikasi_setuju", admin)[1]


def test_setujui_dua_kali_konflik_tanpa_efek_baru(hidup, menunggu, admin):
    _, oid = menunggu
    assert putus(hidup, admin, SETUJUI, oid)[0] == 303
    awal = keadaan(hidup)
    assert putus(hidup, admin, SETUJUI, oid)[0] == 409
    assert keadaan(hidup) == awal


def test_perpanjangan_menyambung_lewat_admin(hidup, menunggu, admin, jam):
    murid, oid = menunggu
    putus(hidup, admin, SETUJUI, oid)
    jam.maju_jam(24 * 5)
    assert buat(hidup, murid, "tahunan")[0] == 303
    assert unggah(hidup, murid, PNG)[0] == 303
    oid2 = order_id(hidup)
    assert putus(hidup, admin, SETUJUI, oid2)[0] == 303
    with hidup.buka() as kon:
        baris = kon.execute("SELECT mulai,berakhir FROM harian_akses ORDER BY id").fetchall()
    assert baris[1]["mulai"] == baris[0]["berakhir"] == "2026-12-23T03:00:00"
    assert baris[1]["berakhir"] == "2027-12-23T03:00:00"


def test_tolak_alasan_tampil_ke_murid_dan_bisa_unggah_ulang(hidup, menunggu, admin):
    murid, oid = menunggu
    kode, _, tajuk = putus(hidup, admin, TOLAK, oid, alasan="Nominal kurang tiga digit")
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=verifikasi_tolak")
    assert keadaan(hidup)[1] == ()
    isi = minta_mentah(hidup, "/murid/langganan", murid.akun)[1]
    assert "Nominal kurang tiga digit" in isi and "Unggah ulang bukti" in isi
    assert unggah(hidup, murid, PNG)[0] == 303
    assert putus(hidup, admin, SETUJUI, oid)[0] == 303


@pytest.mark.parametrize("alasan", ["", "   ", "x" * 201])
def test_tolak_alasan_tidak_sah_tanpa_efek(hidup, menunggu, admin, alasan):
    awal = keadaan(hidup)
    assert putus(hidup, admin, TOLAK, menunggu[1], alasan=alasan)[0] == 400
    assert keadaan(hidup) == awal


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_tanpa_sandi_csrf_atau_tinjauan_ditolak_tanpa_efek(hidup, menunggu, admin, jalur):
    _, oid = menunggu
    awal = keadaan(hidup)
    assert putus(hidup, admin, jalur, oid, hapus=("reauth",))[0] == 403
    assert putus(hidup, admin, jalur, oid, ganti={"reauth": "sandi-salah"})[0] == 403
    assert putus(hidup, admin, jalur, oid, hapus=("csrf",))[0] == 403
    assert putus(hidup, admin, jalur, oid, ganti={"csrf": "x"})[0] == 403
    assert putus(hidup, admin, jalur, oid, hapus=("tinjauan",))[0] == 403
    assert putus(hidup, admin, jalur, oid, ganti={"tinjauan": "x.y"})[0] == 403
    assert keadaan(hidup) == awal


def test_tinjauan_aksi_lain_tidak_berlaku(hidup, menunggu, admin):
    _, oid = menunggu
    awal = keadaan(hidup)
    assert putus(hidup, admin, SETUJUI, oid, aksi=AKSI[TOLAK])[0] == 403
    assert putus(hidup, admin, TOLAK, oid, aksi=AKSI[SETUJUI])[0] == 403
    assert putus(hidup, admin, SETUJUI, oid, aksi="setujui_transfer")[0] == 403
    assert keadaan(hidup) == awal


def test_tinjauan_basi_bukti_baru_ditolak_409_tanpa_efek(hidup, menunggu, admin):
    murid, oid = menunggu
    lama = bukti_terakhir(hidup, oid)
    assert unggah(hidup, murid, PNG)[0] == 303
    awal = keadaan(hidup)
    assert putus(hidup, admin, SETUJUI, oid, bukti_id=lama)[0] == 409
    assert keadaan(hidup) == awal
    assert putus(hidup, admin, SETUJUI, oid)[0] == 303


def test_target_tidak_dari_field_form(hidup, menunggu, admin):
    _, oid = menunggu
    awal = keadaan(hidup)
    for ekstra in ({"order_id": ORDER_ASING}, {"admin_id": "lain"}, {"nominal": "1"}, {"paket": "tahunan"}):
        assert putus(hidup, admin, SETUJUI, oid, ekstra=ekstra)[0] == 400
    assert putus(hidup, admin, TOLAK, oid, ekstra={"order_id": ORDER_ASING})[0] == 400
    assert keadaan(hidup) == awal


def test_order_asing_dalam_tinjauan_404_tanpa_efek(hidup, menunggu, admin):
    awal = keadaan(hidup)
    assert putus(hidup, admin, SETUJUI, ORDER_ASING, bukti_id=1)[0] == 404
    assert keadaan(hidup) == awal


def test_basic_tanpa_sesi_berkuki_ditolak(hidup, menunggu):
    _, oid = menunggu
    akun = auth.cari_akun(AKUN_ADMIN[0])
    awal = keadaan(hidup)
    kode, _, _ = minta_mentah(hidup, SETUJUI, AKUN_ADMIN, {"csrf": "x", "reauth": SANDI_ADMIN, "tinjauan": "x.y"})
    assert kode in (403, 404) and akun is not None
    assert keadaan(hidup) == awal


def test_lintas_situs_ditolak(hidup, menunggu, admin):
    awal = keadaan(hidup)
    kode, _, _ = putus(hidup, admin, SETUJUI, menunggu[1], headers={"Sec-Fetch-Site": "cross-site"})
    assert kode in (400, 403)
    assert keadaan(hidup) == awal


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_post_non_admin_tanpa_efek(hidup, menunggu, jalur):
    _, oid = menunggu
    awal = keadaan(hidup)
    for akun in (None, ("guru", "sandi-guru-panjang-123"), ("feby", "sandi-feby-12345")):
        kode, _, _ = minta_mentah(hidup, jalur, akun, {"csrf": "x", "reauth": "x", "tinjauan": "x.y"})
        assert kode in (401, 403, 404)
    assert keadaan(hidup) == awal
