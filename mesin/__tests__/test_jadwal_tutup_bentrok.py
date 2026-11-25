"""Pendaftaran kelompok ditutup, peringatan bentrok guru (hanya baca), dan versi lepas pada DB sintetis.

Kelompok `_kelompok` mulai 21 Nov 09.00 WIB; ke-1..8 = 21, 24, 28 Nov; 1, 5, 8, 12, 15 Des (02.00 UTC, 60 menit).
Private mulai 24 Nov 09.00 WIB: 24, 27 Nov; 1, 4, 8, 11, 15, 18 Des. Jadi yang jam-nya sama: mini ke-2/4/6/8 dengan
private ke-1/3/5/7.
"""
import pytest

import jadwal_dasar as jd
import jadwal_store as js
import kelas_kit
import schema_jadwal

GURU = "akun_" + "9" * 32
GURU2 = "akun_" + "8" * 32
ADMIN = "admin_sintetis"
SATU_MULAI = "2026-11-21T03:00:00"      # ke-1 sudah mulai, ke-2 belum
TEPAT_KE_DUA = "2026-11-24T02:00:00"    # tepat saat ke-2 mulai (belum dihitung: mulai < sekarang)
DUA_MULAI = "2026-11-24T03:00:00"       # ke-1 dan ke-2 sudah mulai
TIGA_MULAI = "2026-11-28T03:00:00"      # ke-1, ke-2, ke-3 sudah mulai


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _kelompok(kon, *, guru=GURU, nama="Mini A"):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=guru, kuota=5,
                            tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)


def _tempatkan_mini(kon, kid, sekarang, siswa=1):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=siswa)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kid, sekarang=sekarang)
    return tagihan.order_id


def _privat(kon, jam="09:00", guru=GURU, siswa=2):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=siswa)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal="2026-11-24", jam=jam,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _jumlah(kon, tabel):
    return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def _ke_bentrok(sesi):
    return [s["ke"] for s in sesi if s["bentrok"]]


# --- pendaftaran ditutup setelah dua pertemuan mulai -------------------------------------------

def test_mini_masih_boleh_masuk_saat_baru_satu_pertemuan_mulai(kon):
    kid = _kelompok(kon)
    _tempatkan_mini(kon, kid, SATU_MULAI)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


def test_mini_ditolak_setelah_dua_pertemuan_mulai_tanpa_efek_tulis(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalKonflik, match="ditutup"):
        js.tempatkan(kon, ADMIN, mini.order_id, kelompok_id=kid, sekarang=DUA_MULAI)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0
    assert _jumlah(kon, "jadwal_penempatan") == 0


def test_tepat_saat_pertemuan_kedua_mulai_belum_dihitung(kon):
    kid = _kelompok(kon)
    _tempatkan_mini(kon, kid, TEPAT_KE_DUA)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


def test_pertemuan_dibatalkan_tidak_dihitung_untuk_penutupan(kon):
    kid = _kelompok(kon)
    ke1 = js.detail_kelompok(kon, kid)["sesi"][0]
    js.batalkan_pertemuan(kon, ADMIN, ke1["id"], batal=True, sekarang=kelas_kit.KINI)
    _tempatkan_mini(kon, kid, DUA_MULAI)                     # hanya ke-2 yang aktif dan sudah mulai
    assert js.detail_kelompok(kon, kid)["terisi"] == 1
    mini_dua = kelas_kit.lunas(kon, 2, "mini", n=2)
    with pytest.raises(jd.JadwalKonflik, match="ditutup"):   # ke-2 dan ke-3 aktif dan sudah mulai
        js.tempatkan(kon, ADMIN, mini_dua.order_id, kelompok_id=kid, sekarang=TIGA_MULAI)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


def test_daftar_kelompok_menandai_terbuka_sesuai_penutupan_dan_selesai(kon):
    _kelompok(kon)
    assert js.daftar_kelompok(kon, kelas_kit.KINI)[0]["terbuka"] is True
    assert js.daftar_kelompok(kon, SATU_MULAI)[0]["terbuka"] is True
    assert js.daftar_kelompok(kon, TEPAT_KE_DUA)[0]["terbuka"] is True
    tutup = js.daftar_kelompok(kon, DUA_MULAI)[0]
    assert tutup["terbuka"] is False and tutup["berikut"] is not None
    selesai = js.daftar_kelompok(kon, "2026-12-16T00:00:00")[0]
    assert selesai["terbuka"] is False and selesai["berikut"] is None


# --- peringatan bentrok guru (hanya baca) ------------------------------------------------------

def test_private_dan_mini_guru_sama_overlap_ditandai_dua_arah(kon):
    kid = _kelompok(kon)
    privat = _privat(kon)
    assert _ke_bentrok(js.ringkas_order(kon, privat)["sesi"]) == [1, 3, 5, 7]
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == [2, 4, 6, 8]
    assert js.daftar_kelompok(kon, kelas_kit.KINI)[0]["bentrok"] == 4


def test_overlap_sebagian_juga_ditandai(kon):
    kid = _kelompok(kon)
    privat = _privat(kon, jam="09:30")
    assert _ke_bentrok(js.ringkas_order(kon, privat)["sesi"]) == [1, 3, 5, 7]
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == [2, 4, 6, 8]


def test_guru_beda_tidak_bentrok(kon):
    kid = _kelompok(kon)
    privat = _privat(kon, guru=GURU2)
    assert _ke_bentrok(js.ringkas_order(kon, privat)["sesi"]) == []
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == []
    assert js.daftar_kelompok(kon, kelas_kit.KINI)[0]["bentrok"] == 0


def test_sesi_dibatalkan_tidak_bentrok(kon):
    kid = _kelompok(kon)
    privat = _privat(kon)
    ke2 = js.detail_kelompok(kon, kid)["sesi"][1]
    js.batalkan_pertemuan(kon, ADMIN, ke2["id"], batal=True, sekarang=kelas_kit.KINI)
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == [4, 6, 8]
    assert _ke_bentrok(js.ringkas_order(kon, privat)["sesi"]) == [3, 5, 7]
    assert js.daftar_kelompok(kon, kelas_kit.KINI)[0]["bentrok"] == 3


def test_penempatan_private_dipensiunkan_tidak_dihitung(kon):
    kid = _kelompok(kon)
    privat = _privat(kon)
    kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (privat,))   # seperti pensiun perpanjangan
    assert _jumlah(kon, "jadwal_pertemuan") == 16                              # sesi lama tetap riwayat
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == []
    assert js.daftar_kelompok(kon, kelas_kit.KINI)[0]["bentrok"] == 0


@pytest.mark.parametrize("jam", ["10:00", "08:00"], ids=["mulai-saat-lain-selesai", "selesai-saat-lain-mulai"])
def test_bersentuhan_tepat_bukan_bentrok(kon, jam):
    kid = _kelompok(kon)
    privat = _privat(kon, jam=jam)
    assert _ke_bentrok(js.ringkas_order(kon, privat)["sesi"]) == []
    assert _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"]) == []


def test_rantai_beririsan_menandai_semuanya_dan_sesi_bercelah_tidak(kon):
    # A 09.00-10.00, B 09.30-10.30, C 10.15-11.15 (A dan C tidak beririsan), D 11.15-12.15 (menyentuh C), E 13.00.
    orders = {jam: _privat(kon, jam=jam, siswa=n) for n, jam in enumerate(["09:00", "09:30", "10:15", "11:15", "13:00"],
                                                                        start=2)}
    ke_satu = {jam: js.ringkas_order(kon, oid)["sesi"][0]["bentrok"] for jam, oid in orders.items()}
    assert ke_satu == {"09:00": True, "09:30": True, "10:15": True, "11:15": False, "13:00": False}


def test_menyimpan_jadwal_bentrok_tetap_berhasil_dan_hanya_ditandai(kon):
    kid = _kelompok(kon)
    privat = _privat(kon, jam="09:00")                  # private ke-2 = 27 Nov 09.00 WIB
    ke3 = js.detail_kelompok(kon, kid)["sesi"][2]       # mini ke-3 semula 28 Nov
    js.ubah_pertemuan(kon, ADMIN, ke3["id"], tanggal="2026-11-27", jam="09:00", sekarang=kelas_kit.KINI)
    assert js.pertemuan_dari(kon, ke3["id"])["mulai"] == "2026-11-27T02:00:00"
    assert 3 in _ke_bentrok(js.detail_kelompok(kon, kid)["sesi"])
    assert 2 in _ke_bentrok(js.ringkas_order(kon, privat)["sesi"])


# --- lepas: versi penempatan -------------------------------------------------------------------

def test_lepas_dengan_versi_basi_ditolak_tanpa_efek_dan_versi_baru_berhasil(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    js.tempatkan(kon, ADMIN, mini.order_id, kelompok_id=kid, sekarang=kelas_kit.SESUDAH_UPLOAD)
    lama = js.ringkas_order(kon, mini.order_id)["dibuat"]
    js.lepas_penempatan(kon, ADMIN, mini.order_id, versi=lama, sekarang=kelas_kit.SESUDAH_UPLOAD)
    js.tempatkan(kon, ADMIN, mini.order_id, kelompok_id=kid, sekarang="2026-11-20T10:00:00")
    baru = js.ringkas_order(kon, mini.order_id)["dibuat"]
    assert baru != lama
    with pytest.raises(jd.JadwalKonflik, match="sudah berubah"):
        js.lepas_penempatan(kon, ADMIN, mini.order_id, versi=lama, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1
    js.lepas_penempatan(kon, ADMIN, mini.order_id, versi=baru, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_lepas_private_versi_basi_tidak_menghapus_sesi(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=GURU, tanggal="2026-11-24", jam="09:00",
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    lama = js.ringkas_order(kon, tagihan.order_id)["dibuat"]
    js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=lama, sekarang=kelas_kit.SESUDAH_UPLOAD)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=GURU2, tanggal="2026-11-25", jam="09:00",
                 sekarang="2026-11-20T10:00:00")
    with pytest.raises(jd.JadwalKonflik, match="sudah berubah"):
        js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=lama, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert _jumlah(kon, "jadwal_penempatan") == 1 and _jumlah(kon, "jadwal_pertemuan") == 8


def test_lepas_wajib_membawa_versi_sebagai_keyword(kon):
    kid = _kelompok(kon)
    mini = _tempatkan_mini(kon, kid, kelas_kit.SESUDAH_UPLOAD)
    with pytest.raises(TypeError):
        js.lepas_penempatan(kon, ADMIN, mini, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


@pytest.mark.parametrize("versi", [None, "", 12, "2026-11-20T09:30:01"], ids=["none", "kosong", "angka", "lain"])
def test_versi_kosong_atau_bukan_milik_penempatan_ditolak(kon, versi):
    kid = _kelompok(kon)
    mini = _tempatkan_mini(kon, kid, kelas_kit.SESUDAH_UPLOAD)
    with pytest.raises(jd.JadwalKonflik):
        js.lepas_penempatan(kon, ADMIN, mini, versi=versi, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1
