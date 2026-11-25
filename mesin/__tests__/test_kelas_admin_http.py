"""Admin Paket Belajar lewat HTTP nyata: antrean, detail, pratinjau, setujui/tolak, deposit, keamanan aksi.

Efek (atau ketiadaannya) dibuktikan dari DB admin sintetis, bukan hanya status HTTP. Pola keamanan sama dengan
verifikasi transfer: sesi berkuki, CSRF, tinjauan bertanda tangan (order + bukti terakhir), sandi admin ulang.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import admin_http
import admin_security
import admin_store
import auth
import paket_belajar_gate
import pesanan
import purna
from admin_pesanan_kit import login_admin, minta_admin
from bukti_kit import JPEG, PDF, PNG
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN
from kelas_http_kit import (AWAL, KOSONG, TABEL, baca_admin, berkas_kelas, bukti_terakhir, buat, buat_dan_unggah,  # noqa: F401
                            buat_murid, hitung, jam, kidup, kmati, minta_mentah, order_terakhir, peta_lunas_untuk,
                            semua_berkas, server, unggah)

DAFTAR = "/admin/kelas"
DETAIL = DAFTAR + "/verifikasi"
BUKTI = DAFTAR + "/bukti"
SETUJUI = DAFTAR + "/setujui"
TOLAK = DAFTAR + "/tolak"
KELUARGA = DAFTAR + "/keluarga"
TAK_ADA = "/admin/tidak-ada"
AKSI = {SETUJUI: "setujui_kelas", TOLAK: "tolak_kelas"}
ORDER_ASING = "kor_" + "0" * 32


@pytest.fixture()
def admin(kidup):
    return login_admin(kidup)


@pytest.fixture()
def menunggu(kidup):
    """Satu murid dengan tagihan mini dan satu bukti menunggu; mengembalikan (murid, order_id)."""
    kidup.murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    return kidup.murid, buat_dan_unggah(kidup, kidup.murid, "mini", JPEG)


def token(cookie, aksi, oid, bukti_id, *, sandi=SANDI_ADMIN, isi=None):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    payload = isi if isi is not None else {"target_id": oid, "target_revisi": bukti_id}
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": sandi,
            "tinjauan": admin_security.buat_tinjauan(akun, cookie, aksi, payload)}


def putus(server, cookie, jalur, oid, *, bukti_id=None, ekstra=None, ganti=None, hapus=(), headers=None,
          alasan="Nominal tidak sesuai", aksi=None):
    data = token(cookie, aksi or AKSI[jalur], oid, bukti_terakhir(oid) if bukti_id is None else bukti_id)
    if jalur == TOLAK:
        data["alasan"] = alasan
    data.update(ekstra or {})
    data.update(ganti or {})
    for kunci in hapus:
        data.pop(kunci, None)
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def keadaan():
    return {t: tuple(tuple(r.values()) for r in baca_admin("SELECT * FROM %s" % t)) for t in
            ("kelas_verifikasi", "kelas_akses", "purna_voucher_pakai")}


# --- sakelar dan palang ----------------------------------------------------------------------

def test_sakelar_mati_antrean_detail_pratinjau_dan_putusan_admin_tetap_terbuka(kidup, menunggu, admin, monkeypatch):
    _, oid = menunggu
    monkeypatch.delenv("PAKET_BELAJAR")
    assert not paket_belajar_gate.aktif()
    kode, isi, _ = minta_admin(kidup, DAFTAR, admin)
    assert kode == 200 and oid in isi
    assert minta_admin(kidup, "%s?order=%s" % (DETAIL, oid), admin)[0] == 200
    kode, _, tajuk = minta_admin(kidup, "%s?id=%d" % (BUKTI, bukti_terakhir(oid)), admin)
    assert kode == 200 and tajuk["Content-Type"] == "image/jpeg"
    kode, _, tajuk = putus(kidup, admin, SETUJUI, oid)
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=kelas_setuju")


@pytest.mark.parametrize("jalur", [DAFTAR, DETAIL + "?order=" + ORDER_ASING, BUKTI + "?id=1"])
def test_non_admin_404_identik_rute_tak_dikenal_sakelar_mati_atau_hidup(kmati, kidup, jalur):
    acuan = minta_mentah(kidup, TAK_ADA, None)[:2]
    for akun in (None, ("guru", "sandi-guru-panjang-123"), ("feby", "sandi-feby-12345")):
        assert minta_mentah(kidup, jalur, akun)[:2] == acuan
    for aksi in (SETUJUI, TOLAK, KELUARGA):
        for akun in (None, ("guru", "sandi-guru-panjang-123"), ("feby", "sandi-feby-12345")):
            asing = minta_mentah(kidup, TAK_ADA, akun, {"x": "1"})[:2]
            assert minta_mentah(kidup, aksi, akun, {"x": "1"})[:2] == asing, (aksi, akun)


def test_menu_admin_memuat_butir_paket_belajar(kidup):
    cookie = login_admin(kidup)
    kode, isi, _ = minta_admin(kidup, DAFTAR, cookie)
    assert kode == 200 and 'href="/admin/kelas"' in isi and 'aria-current="page"' in isi and "Paket belajar" in isi


# --- antrean, detail, pratinjau --------------------------------------------------------------------

def test_antrean_memuat_paket_nominal_persis_dan_tautan_tanpa_nama_anak(kidup, menunggu, admin):
    murid, oid = menunggu
    isi = minta_admin(kidup, DAFTAR, admin)[1]
    assert "Mini Class" in isi and 'href="%s?order=%s"' % (DETAIL, oid) in isi
    unik = order_terakhir()["kode_unik"]
    assert 'Rp300.<mark class="admin-digit-unik">%03d</mark>' % unik in isi
    assert "Anak Alfa" not in isi and "murid-a" not in isi and str(murid.id_akun) not in isi


def test_antrean_kosong_pesan_jujur(kidup, admin):
    assert "Tidak ada bukti paket belajar yang menunggu" in minta_admin(kidup, DAFTAR, admin)[1]


def test_antrean_terlama_dulu(kidup, admin, jam):
    a = buat_murid(kidup, "murid-a", "Anak A")
    b = buat_murid(kidup, "murid-b", "Anak B")
    buat(kidup, a)
    buat(kidup, b)
    jam.maju_jam(1)
    unggah(kidup, b, JPEG)
    jam.maju_jam(1)
    unggah(kidup, a, PNG)
    oid = {r["siswa_id"]: r["id"] for r in baca_admin("SELECT id,siswa_id FROM kelas_order")}
    isi = minta_admin(kidup, DAFTAR, admin)[1]
    assert isi.index(oid[b.siswa_id]) < isi.index(oid[a.siswa_id])


def test_detail_dua_form_token_dan_pratinjau_tanpa_form_keluarga(kidup, menunggu, admin):
    _, oid = menunggu
    kode, isi, _ = minta_admin(kidup, "%s?order=%s" % (DETAIL, oid), admin)
    assert kode == 200
    assert 'action="%s"' % SETUJUI in isi and 'action="%s"' % TOLAK in isi
    assert isi.count('name="reauth"') >= 2 and 'name="tinjauan"' in isi and 'name="csrf"' in isi
    assert "%s?id=%d" % (BUKTI, bukti_terakhir(oid)) in isi and "Menunggu verifikasi" in isi
    antrean = minta_admin(kidup, DAFTAR, admin)[1]
    assert KELUARGA not in antrean and 'name="siswa_a"' not in antrean


@pytest.mark.parametrize("query", ["", "?order=x", "?order=" + ORDER_ASING, "?order=ord_" + "0" * 32,
                                   "?order=kor_" + "A" * 32, "?x=1"])
def test_detail_tidak_sah_atau_tak_dikenal_404_identik(kidup, admin, query):
    acuan = minta_admin(kidup, TAK_ADA, admin)
    kode, isi, _ = minta_admin(kidup, DETAIL + query, admin)
    assert (kode, isi) == acuan[:2]


def test_pratinjau_bukti_tipe_header_dan_isi(kidup, menunggu, admin):
    _, oid = menunggu
    kode, isi, tajuk = minta_admin(kidup, "%s?id=%d" % (BUKTI, bukti_terakhir(oid)), admin)
    assert kode == 200 and tajuk["Content-Type"] == "image/jpeg"
    assert tajuk["X-Content-Type-Options"] == "nosniff" and "sandbox" in tajuk["Content-Security-Policy"]
    assert 'filename="bukti-transfer.jpg"' in tajuk["Content-Disposition"]
    kode, _, tajuk = minta_admin(kidup, "%s?id=%d&unduh=1" % (BUKTI, bukti_terakhir(oid)), admin)
    assert kode == 200 and "attachment" in tajuk["Content-Disposition"]


@pytest.mark.parametrize("query", ["?id=99999", "?id=0", "?id=abc", "?id=1&x=2", "", "?id=" + "c" * 32,
                                   "?id=1&unduh=2"])
def test_pratinjau_tak_dikenal_atau_tak_sah(kidup, admin, query):
    kode, _, _ = minta_admin(kidup, BUKTI + query, admin)
    assert kode == 404


def test_pratinjau_berkas_rusak_503_bukan_500(kidup, menunggu, admin):
    for f in (Path(kidup.folder) / "kelas").glob("*"):
        f.write_bytes(b"bukan gambar")
    kode, _, _ = minta_admin(kidup, "%s?id=%d" % (BUKTI, bukti_terakhir(menunggu[1])), admin)
    assert kode == 503


# --- keputusan ----------------------------------------------------------------------------------

def test_setujui_tulis_verifikasi_dan_akses_tanggal_benar(kidup, menunggu, admin, jam):
    murid, oid = menunggu
    jam.maju_jam(2)
    kode, _, tajuk = putus(kidup, admin, SETUJUI, oid)
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=kelas_setuju")
    akses = baca_admin("SELECT mulai,berakhir,siswa_id FROM kelas_akses")
    assert [tuple(a.values()) for a in akses] == [("2026-11-23T05:00:00", "2026-12-23T05:00:00", murid.siswa_id)]
    assert "disetujui" in minta_admin(kidup, DAFTAR + "?hasil=kelas_setuju", admin)[1]


def test_setujui_dua_kali_idempoten_tanpa_efek_baru_dan_tolak_sesudahnya_konflik(kidup, menunggu, admin):
    _, oid = menunggu
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303      # domain idempoten: balasan `baru=False`
    assert keadaan() == awal and len(baca_admin("SELECT * FROM kelas_akses")) == 1
    assert putus(kidup, admin, TOLAK, oid)[0] == 409
    assert keadaan() == awal


def test_tolak_alasan_wajib_lalu_murid_boleh_unggah_ulang(kidup, menunggu, admin):
    murid, oid = menunggu
    kode, _, tajuk = putus(kidup, admin, TOLAK, oid, alasan="Nominal kurang tiga digit")
    assert (kode, tajuk["Location"]) == (303, DAFTAR + "?hasil=kelas_tolak")
    assert keadaan()["kelas_akses"] == ()
    assert baca_admin("SELECT keputusan,alasan FROM kelas_verifikasi") == [
        {"keputusan": "tolak", "alasan": "Nominal kurang tiga digit"}]
    assert unggah(kidup, murid, PNG)[0] == 303
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303


@pytest.mark.parametrize("alasan", ["", "   ", "x" * 201])
def test_tolak_alasan_tidak_sah_tanpa_efek(kidup, menunggu, admin, alasan):
    awal = keadaan()
    assert putus(kidup, admin, TOLAK, menunggu[1], alasan=alasan)[0] == 400
    assert keadaan() == awal


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_tanpa_sandi_csrf_atau_tinjauan_ditolak_tanpa_efek(kidup, menunggu, admin, jalur):
    _, oid = menunggu
    awal = keadaan()
    assert putus(kidup, admin, jalur, oid, hapus=("reauth",))[0] == 403
    assert putus(kidup, admin, jalur, oid, ganti={"reauth": "sandi-salah"})[0] == 403
    assert putus(kidup, admin, jalur, oid, hapus=("csrf",))[0] == 403
    assert putus(kidup, admin, jalur, oid, ganti={"csrf": "x"})[0] == 403
    assert putus(kidup, admin, jalur, oid, hapus=("tinjauan",))[0] == 403
    assert putus(kidup, admin, jalur, oid, ganti={"tinjauan": "x.y"})[0] == 403
    assert keadaan() == awal


def test_tinjauan_aksi_lain_tidak_berlaku(kidup, menunggu, admin):
    _, oid = menunggu
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, oid, aksi=AKSI[TOLAK])[0] == 403
    assert putus(kidup, admin, TOLAK, oid, aksi=AKSI[SETUJUI])[0] == 403
    assert putus(kidup, admin, SETUJUI, oid, aksi="setujui_langganan")[0] == 403
    assert keadaan() == awal


def test_tinjauan_basi_bukti_baru_ditolak_409_tanpa_efek(kidup, menunggu, admin):
    murid, oid = menunggu
    lama = bukti_terakhir(oid)
    assert unggah(kidup, murid, PNG)[0] == 303
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, oid, bukti_id=lama)[0] == 409
    assert putus(kidup, admin, TOLAK, oid, bukti_id=lama)[0] == 409
    assert keadaan() == awal
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303


def test_target_tidak_dari_field_form(kidup, menunggu, admin):
    _, oid = menunggu
    awal = keadaan()
    for ekstra in ({"order_id": ORDER_ASING}, {"admin_id": "lain"}, {"nominal": "1"}, {"paket": "private"},
                   {"bukti_dilihat": "1"}):
        assert putus(kidup, admin, SETUJUI, oid, ekstra=ekstra)[0] == 400, ekstra
    assert putus(kidup, admin, TOLAK, oid, ekstra={"order_id": ORDER_ASING})[0] == 400
    assert keadaan() == awal


def test_order_asing_dalam_tinjauan_404_tanpa_efek(kidup, menunggu, admin):
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, ORDER_ASING, bukti_id=1)[0] == 404
    assert keadaan() == awal


def test_tinjauan_dengan_order_tidak_sah_ditolak(kidup, menunggu, admin):
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, "ord_" + "0" * 32, bukti_id=1)[0] == 400
    assert putus(kidup, admin, SETUJUI, menunggu[1], bukti_id=0)[0] == 400
    assert keadaan() == awal


def test_basic_tanpa_sesi_berkuki_ditolak(kidup, menunggu):
    awal = keadaan()
    kode, _, _ = minta_mentah(kidup, SETUJUI, AKUN_ADMIN, {"csrf": "x", "reauth": SANDI_ADMIN, "tinjauan": "x.y"})
    assert kode in (403, 404)
    assert keadaan() == awal


def test_lintas_situs_ditolak(kidup, menunggu, admin):
    awal = keadaan()
    kode, _, _ = putus(kidup, admin, SETUJUI, menunggu[1], headers={"Sec-Fetch-Site": "cross-site"})
    assert kode in (400, 403)
    assert keadaan() == awal


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_post_non_admin_tanpa_efek(kidup, menunggu, jalur):
    awal = keadaan()
    for akun in (None, ("guru", "sandi-guru-panjang-123"), ("feby", "sandi-feby-12345")):
        kode, _, _ = minta_mentah(kidup, jalur, akun, {"csrf": "x", "reauth": "x", "tinjauan": "x.y"})
        assert kode in (401, 403, 404)
    assert keadaan() == awal


# --- deposit ------------------------------------------------------------------------------------

def test_deposit_dipakai_tepat_sekali_dan_tagihan_dipotong(kidup, admin):
    murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    peta = peta_lunas_untuk(murid)
    oid = buat_dan_unggah(kidup, murid, "private", PDF)
    o = order_terakhir()
    assert (o["nominal"], o["potongan_deposit"]) == (591_000, 49_000)
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303
    pakai = baca_admin("SELECT order_id,catatan_kode FROM purna_voucher_pakai")
    assert pakai == [{"order_id": peta, "catatan_kode": "kelas"}]
    awal = keadaan()
    assert putus(kidup, admin, SETUJUI, oid)[0] == 303      # ulang: tidak menggandakan akses maupun pemakaian deposit
    assert keadaan() == awal and len(baca_admin("SELECT * FROM kelas_akses")) == 1


def test_deposit_tidak_lagi_berlaku_setujui_ditolak_pesan_jelas_tanpa_akses(kidup, admin):
    murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    peta = peta_lunas_untuk(murid)
    oid = buat_dan_unggah(kidup, murid, "mini", JPEG)
    assert order_terakhir()["potongan_deposit"] == 49_000
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:   # deposit dipakai pihak lain
        purna.catat_pakai(kon, peta, "op-manual-0001", "admin_sintetis_x", "kelas", AWAL)
    awal = keadaan()
    kode, isi, _ = putus(kidup, admin, SETUJUI, oid)
    assert kode == 409 and "Deposit pembeli tidak lagi berlaku" in isi and "mendaftar ulang" in isi
    assert keadaan() == awal and baca_admin("SELECT * FROM kelas_akses") == []
    assert putus(kidup, admin, TOLAK, oid, alasan="Deposit tidak berlaku")[0] == 303


# --- tautan keluarga dihapus (25 Nov 2026) ---------------------------------------------------------

def test_rute_keluarga_sudah_dihapus_sama_dengan_rute_tak_dikenal_tanpa_efek(kidup, admin):
    """Regression: POST /keluarga tidak lagi punya handler; hasilnya identik dengan rute admin tak dikenal."""
    a = buat_murid(kidup, "murid-a", "Anak A")
    b = buat_murid(kidup, "murid-b", "Anak B")
    data = token(admin, AKSI[SETUJUI], None, None, isi={"section": "kelas_belajar"})
    data.update({"siswa_a": str(a.siswa_id), "siswa_b": str(b.siswa_id)})
    cookie = {"Cookie": "osn_sesi=" + admin}
    assert minta_mentah(kidup, KELUARGA, None, data, cookie)[:2] == minta_mentah(kidup, TAK_ADA, None, data, cookie)[:2]
    assert hitung()["kelas_keluarga"] == 0


# --- XSS dan privasi -------------------------------------------------------------------------------

def test_detail_admin_tanpa_nama_anak_atau_akun(kidup, menunggu, admin):
    _, oid = menunggu
    isi = minta_admin(kidup, "%s?order=%s" % (DETAIL, oid), admin)[1]
    for rahasia in ("Anak Alfa", "murid-a", "6281"):
        assert rahasia not in isi
