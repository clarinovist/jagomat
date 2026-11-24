"""Admin jadwal lewat HTTP nyata: kelompok, penempatan, kuota, sesi, dan palang akses."""
from __future__ import annotations

import http.cookies

import pytest

import admin_http
import admin_security
import admin_store
import auth
import jadwal_dasar as jd
import kelas_kit
import pesanan
import schema_jadwal
from admin_pesanan_kit import login_admin, minta_admin
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, minta_mentah
from kelas_http_kit import jam, kidup, kmati, server  # noqa: F401

DAFTAR = "/admin/kelas"
KELOMPOK = "/admin/kelas/kelompok"
PENEMPATAN = "/admin/kelas/penempatan"
LEPAS = "/admin/kelas/penempatan/lepas"
PERTEMUAN = "/admin/kelas/pertemuan"
BATAL = "/admin/kelas/pertemuan/batal"
DETAIL = "/admin/kelas/verifikasi"
TAK_ADA = "/admin/tidak-ada"


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    return kidup


@pytest.fixture()
def admin(siap):
    return login_admin(siap)


def _token(cookie, aksi, isi):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie),
            "tinjauan": admin_security.buat_tinjauan(akun, cookie, aksi, isi)}


def _guru() -> str:
    return auth.cari_akun("guru-b")["id_akun"]


def _buat_kelompok(server, cookie, *, kuota=5, nama="Mini A") -> str:
    data = _token(cookie, "jadwal_kelompok_buat", {"section": "kelas_belajar"})
    data.update({"nama": nama, "lokasi": "Ruang 1", "guru_id": _guru(), "kuota": str(kuota),
                 "tanggal": "2026-11-28", "jam": "09:00"})
    kode, _, tajuk = minta_admin(server, KELOMPOK, cookie, data)
    assert kode == 303, kode
    return tajuk["Location"].split("id=")[1]


def _aktif(paket="mini", siswa=1, n=1) -> str:
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return kelas_kit.lunas(kon, siswa, paket, n=n).order_id


def _tempat_mini(server, cookie, order_id, kid):
    data = _token(cookie, "jadwal_tempatkan", {"order_id": order_id})
    data["kelompok_id"] = kid
    return minta_admin(server, PENEMPATAN, cookie, data)


def _baris(sql, args=()):
    from kelas_http_kit import baca_admin
    return baca_admin(sql, args)


def test_non_admin_404_identik_untuk_semua_rute_jadwal(siap):
    for jalur in (KELOMPOK + "?id=" + jd.id_kelompok_baru(), PENEMPATAN, LEPAS, PERTEMUAN, BATAL):
        acuan = minta_mentah(siap, TAK_ADA, None, {} if jalur != KELOMPOK else None)[:2]
        uji = minta_mentah(siap, jalur, None, {} if jalur != KELOMPOK else None)[:2]
        assert uji == acuan


def test_daftar_menampilkan_kelompok_form_dan_guru(siap, admin):
    kid = _buat_kelompok(siap, admin, kuota=3)
    kode, isi, _ = minta_admin(siap, DAFTAR, admin)
    assert kode == 200
    assert "Buat kelompok Mini Class" in isi and "Mini A" in isi
    assert "guru-b" in isi and "0/3" in isi
    assert kid in isi


def test_buat_kelompok_lewat_http_menulis_delapan_sesi(siap, admin):
    kid = _buat_kelompok(siap, admin)
    assert len(_baris("SELECT * FROM jadwal_kelompok WHERE id=?", (kid,))) == 1
    assert _baris("SELECT * FROM jadwal_pertemuan WHERE kelompok_id=?", (kid,))[0]["mulai"] == "2026-11-28T02:00:00"
    assert len(_baris("SELECT * FROM jadwal_pertemuan WHERE kelompok_id=?", (kid,))) == 8
    kode, isi, _ = minta_admin(siap, "%s?id=%s" % (KELOMPOK, kid), admin)
    assert kode == 200 and "Delapan pertemuan" in isi and isi.count('action="/admin/kelas/pertemuan"') == 8


def test_buat_kelompok_isian_asing_dan_csrf_salah_ditolak_tanpa_tulis(siap, admin):
    data = _token(admin, "jadwal_kelompok_buat", {"section": "kelas_belajar"})
    data.update({"nama": "Mini", "lokasi": "Ruang", "guru_id": _guru(), "kuota": "5",
                 "tanggal": "2026-11-28", "jam": "09:00", "order_id": "kor_" + "0" * 32})
    assert minta_admin(siap, KELOMPOK, admin, data)[0] == 400
    data.pop("order_id")
    data["csrf"] = "salah"
    assert minta_admin(siap, KELOMPOK, admin, data)[0] == 403
    assert _baris("SELECT COUNT(*) AS n FROM jadwal_kelompok")[0]["n"] == 0


def test_tempatkan_mini_sampai_penuh_lewat_http(siap, admin):
    kid = _buat_kelompok(siap, admin, kuota=2)
    satu, dua, tiga = _aktif("mini", 1, 1), _aktif("mini", 2, 2), _aktif("mini", 3, 3)
    assert _tempat_mini(siap, admin, satu, kid)[0] == 303
    assert _tempat_mini(siap, admin, dua, kid)[0] == 303
    assert _tempat_mini(siap, admin, tiga, kid)[0] == 409
    assert _baris("SELECT COUNT(*) AS n FROM jadwal_penempatan WHERE kelompok_id=?", (kid,))[0]["n"] == 2
    kode, isi, _ = minta_admin(siap, "%s?order=%s" % (DETAIL, satu), admin)
    assert kode == 200 and "Kelompok" in isi and "Lepas penempatan" in isi


def test_hanya_order_aktif_yang_tampil_form_penempatan(siap, admin):
    _buat_kelompok(siap, admin)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = kelas_kit.tagih(kon, 1).order_id
    kode, isi, _ = minta_admin(siap, "%s?order=%s" % (DETAIL, order), admin)
    assert kode == 200 and "Jadwal bisa dibuat setelah bukti transfer disetujui" in isi
    assert "Tempatkan ke kelompok" not in isi


def test_private_lewat_http_sesi_bisa_diubah_dan_dibatalkan(siap, admin):
    order = _aktif("private")
    data = _token(admin, "jadwal_tempatkan", {"order_id": order})
    data.update({"guru_id": _guru(), "tanggal": "2026-12-01", "jam": "16:30"})
    assert minta_admin(siap, PENEMPATAN, admin, data)[0] == 303
    sesi = _baris("SELECT * FROM jadwal_pertemuan WHERE order_id=? ORDER BY ke", (order,))
    assert len(sesi) == 8 and sesi[0]["mulai"] == "2026-12-01T09:30:00"
    pid = sesi[0]["id"]
    ubah = _token(admin, "jadwal_pertemuan_ubah", {"order_id": order})
    ubah.update({"pertemuan_id": str(pid), "tanggal": "2026-12-02", "jam": "17:00"})
    assert minta_admin(siap, PERTEMUAN, admin, ubah)[0] == 303
    assert _baris("SELECT mulai FROM jadwal_pertemuan WHERE id=?", (pid,))[0]["mulai"] == "2026-12-02T10:00:00"
    batal = _token(admin, "jadwal_pertemuan_batal", {"order_id": order})
    batal.update({"pertemuan_id": str(pid), "batal": "1"})
    assert minta_admin(siap, BATAL, admin, batal)[0] == 303
    assert _baris("SELECT dibatalkan FROM jadwal_pertemuan WHERE id=?", (pid,))[0]["dibatalkan"] == 1


def test_sesi_order_lain_tidak_bisa_diubah_dari_tinjauan_ini(siap, admin):
    order = _aktif("private")
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        lain = kelas_kit.lunas(kon, 2, "private", n=2)
        js = __import__("jadwal_store")
        js.tempatkan(kon, "admin_sintetis", lain.order_id, guru_id=_guru(), tanggal="2026-12-01",
                     jam="16:30", sekarang=kelas_kit.SESUDAH_UPLOAD)
    sesi_lain = _baris("SELECT id FROM jadwal_pertemuan WHERE order_id=? ORDER BY ke", (lain.order_id,))[0]["id"]
    ubah = _token(admin, "jadwal_pertemuan_ubah", {"order_id": order})
    ubah.update({"pertemuan_id": str(sesi_lain), "tanggal": "2026-12-02", "jam": "17:00"})
    assert minta_admin(siap, PERTEMUAN, admin, ubah)[0] == 404
    assert _baris("SELECT mulai FROM jadwal_pertemuan WHERE id=?", (sesi_lain,))[0]["mulai"] == "2026-12-01T09:30:00"


def test_lepas_membebaskan_kuota_dan_menghapus_sesi_private(siap, admin):
    kid = _buat_kelompok(siap, admin, kuota=1)
    mini = _aktif("mini")
    assert _tempat_mini(siap, admin, mini, kid)[0] == 303
    data = _token(admin, "jadwal_lepas", {"order_id": mini})
    assert minta_admin(siap, LEPAS, admin, data)[0] == 303
    assert _baris("SELECT COUNT(*) AS n FROM jadwal_penempatan WHERE order_id=?", (mini,))[0]["n"] == 0
    lain = _aktif("mini", 2, 2)
    assert _tempat_mini(siap, admin, lain, kid)[0] == 303
    privat = _aktif("private", 3, 3)
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        __import__("jadwal_store").tempatkan(kon, "admin_sintetis", privat, guru_id=_guru(),
                                             tanggal="2026-12-01", jam="16:30",
                                             sekarang=kelas_kit.SESUDAH_UPLOAD)
    lepas = _token(admin, "jadwal_lepas", {"order_id": privat})
    assert minta_admin(siap, LEPAS, admin, lepas)[0] == 303
    assert _baris("SELECT COUNT(*) AS n FROM jadwal_pertemuan WHERE order_id=?", (privat,))[0]["n"] == 0


def test_kuota_tidak_boleh_turun_di_bawah_anggota_lewat_http(siap, admin):
    kid = _buat_kelompok(siap, admin, kuota=2)
    for n in (1, 2):
        assert _tempat_mini(siap, admin, _aktif("mini", n, n), kid)[0] == 303
    data = _token(admin, "jadwal_kelompok_ubah", {"kelompok_id": kid})
    data.update({"nama": "Mini A", "lokasi": "Ruang 1", "guru_id": _guru(), "kuota": "1"})
    assert minta_admin(siap, KELOMPOK + "/ubah", admin, data)[0] == 409
    assert _baris("SELECT kuota FROM jadwal_kelompok WHERE id=?", (kid,))[0]["kuota"] == 2


def test_sakelar_paket_mati_admin_jadwal_tetap_terbuka(siap, admin, monkeypatch):
    monkeypatch.delenv("PAKET_BELAJAR", raising=False)
    _buat_kelompok(siap, admin)
    kode, isi, _ = minta_admin(siap, DAFTAR, admin)
    assert kode == 200 and "Buat kelompok Mini Class" in isi
