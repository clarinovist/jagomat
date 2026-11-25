"""Orang tua memilih kelompok Mini sendiri (butir QA #4, 25 Nov 2026; data sintetis).

Mini saja: kelompok, kuota, dan masa akses sudah punya aturan tempatkan admin; Private butuh guru, tanggal, dan jam sehingga tetap
ditentukan admin. Pilihan hanya untuk order Mini aktif yang BELUM ditempatkan dan sekali saja; mengubahnya tetap lewat admin.
"""
import pytest

import jadwal_dasar as jd
import jadwal_pilih as jp
import jadwal_store as js
import kelas_dasar as dasar
import kelas_kit
import pesanan_dasar as d
import schema_jadwal
from pesanan_kit import AKUN_A, AKUN_B

ADMIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
LOKASI = "https://meet.google.com/abc-defg-hij"
KINI = "2026-11-25T03:00:00"        # akses lunas kelas_kit: 20 Nov 09.30 sampai 20 Des 09.30 (UTC naif)


@pytest.fixture()
def kon(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    with js.buka(path, tulis_data=True) as koneksi:
        yield koneksi


def kelompok(kon, nama="Mini A", kuota=5, tanggal="2026-11-26", dibuat=kelas_kit.KINI):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=LOKASI, guru_id=GURU, kuota=kuota, tanggal=tanggal,
                            jam="09:00", sekarang=dibuat)

TANGGAL_LAMPAU = dict(tanggal="2026-11-20", dibuat="2026-11-10T00:00:00")    # dua pertemuan pertama sudah mulai pada KINI


def jumlah_penempatan(kon) -> int:
    return kon.execute("SELECT COUNT(*) FROM jadwal_penempatan").fetchone()[0]


def test_pilihan_memuat_nama_waktu_dan_sisa_tanpa_guru_atau_lokasi(kon):
    kelas_kit.lunas(kon, siswa=7)
    kid = kelompok(kon)
    (pilihan,) = jp.pilihan_untuk(kon, AKUN_A, 7, KINI)
    assert (pilihan.kelompok_id, pilihan.nama, pilihan.sisa) == (kid, "Mini A", 5)
    assert pilihan.mulai == "2026-11-26T02:00:00"           # 09.00 WIB
    assert not hasattr(pilihan, "guru_id") and not hasattr(pilihan, "lokasi")


def test_sisa_kuota_berkurang_dan_kelompok_penuh_tidak_ditawarkan(kon):
    kelas_kit.lunas(kon, siswa=7, n=1)
    kelas_kit.lunas(kon, siswa=8, n=2)
    kid = kelompok(kon, kuota=1)
    jp.pilih_kelompok(kon, AKUN_A, 8, kid, KINI)
    assert jp.pilihan_untuk(kon, AKUN_A, 7, KINI) == ()


def test_kelompok_ditutup_atau_selesai_atau_lewat_akses_tidak_ditawarkan(kon):
    kelas_kit.lunas(kon, siswa=7)
    kelompok(kon, nama="Sudah berjalan", **TANGGAL_LAMPAU)
    kelompok(kon, nama="Lewat akses", tanggal="2026-12-10")         # pertemuan terakhir jatuh setelah akses berakhir
    assert jp.pilihan_untuk(kon, AKUN_A, 7, KINI) == ()


@pytest.mark.parametrize("keadaan", ["tanpa_order", "menunggu", "private", "akun_lain", "sudah_ditempatkan"])
def test_tanpa_order_mini_aktif_yang_belum_ditempatkan_tidak_ada_pilihan(kon, keadaan):
    kid = kelompok(kon)
    if keadaan == "menunggu":
        kelas_kit.menunggu(kon, siswa=7)
    elif keadaan == "private":
        kelas_kit.lunas(kon, siswa=7, paket="private")
    elif keadaan == "akun_lain":
        kelas_kit.lunas(kon, siswa=7)
    elif keadaan == "sudah_ditempatkan":
        tagihan = kelas_kit.lunas(kon, siswa=7)
        js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kid, sekarang=KINI)
    akun = AKUN_B if keadaan == "akun_lain" else AKUN_A
    if keadaan == "akun_lain":
        with pytest.raises(d.PesananTidakDitemukan):
            jp.pilihan_untuk(kon, akun, 7, KINI)
        return
    assert jp.pilihan_untuk(kon, akun, 7, KINI) == ()


def test_pilih_menempatkan_order_dan_jadwal_terbaca_orang_tua(kon):
    tagihan = kelas_kit.lunas(kon, siswa=7)
    kid = kelompok(kon)
    jp.pilih_kelompok(kon, AKUN_A, 7, kid, KINI)
    baris = kon.execute("SELECT order_id,kelompok_id,guru_id,dibuat_oleh FROM jadwal_penempatan").fetchall()
    assert [tuple(b) for b in baris] == [(tagihan.order_id, kid, None, AKUN_A)]
    jadwal = js.jadwal_terbaru_murid(kon, AKUN_A, 7, KINI)
    assert jadwal is not None and len(jadwal["sesi"]) == jd.PERTEMUAN
    assert jp.pilihan_untuk(kon, AKUN_A, 7, KINI) == ()               # sekali saja


def test_pilih_ulang_setelah_ditempatkan_ditolak_dan_penempatan_tetap(kon):
    kelas_kit.lunas(kon, siswa=7)
    pertama, kedua = kelompok(kon, "Mini A"), kelompok(kon, "Mini B")
    jp.pilih_kelompok(kon, AKUN_A, 7, pertama, KINI)
    with pytest.raises(d.PesananKonflik):
        jp.pilih_kelompok(kon, AKUN_A, 7, kedua, KINI)
    assert [b["kelompok_id"] for b in kon.execute("SELECT kelompok_id FROM jadwal_penempatan")] == [pertama]


def test_pilih_tidak_menimpa_penempatan_admin(kon):
    tagihan = kelas_kit.lunas(kon, siswa=7)
    milik_admin, lain = kelompok(kon, "Admin"), kelompok(kon, "Lain")
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=milik_admin, sekarang=KINI)
    with pytest.raises(d.PesananKonflik):
        jp.pilih_kelompok(kon, AKUN_A, 7, lain, KINI)
    assert [b["kelompok_id"] for b in kon.execute("SELECT kelompok_id FROM jadwal_penempatan")] == [milik_admin]


def test_pilih_kelompok_penuh_ditolak_tanpa_tulis(kon):
    kelas_kit.lunas(kon, siswa=7, n=1)
    kelas_kit.lunas(kon, siswa=8, n=2)
    kid = kelompok(kon, kuota=1)
    jp.pilih_kelompok(kon, AKUN_A, 8, kid, KINI)
    with pytest.raises(js.jd.JadwalPenuh):
        jp.pilih_kelompok(kon, AKUN_A, 7, kid, KINI)
    assert jumlah_penempatan(kon) == 1


@pytest.mark.parametrize("kelompok_id,galat", [
    ("klp_" + "0" * 32, jd.JadwalTidakDitemukan),
    ("bukan-id", jd.JadwalTidakSah),
    (None, jd.JadwalTidakSah),
])
def test_pilih_kelompok_tak_dikenal_atau_tak_sah_ditolak(kon, kelompok_id, galat):
    kelas_kit.lunas(kon, siswa=7)
    with pytest.raises(galat):
        jp.pilih_kelompok(kon, AKUN_A, 7, kelompok_id, KINI)
    assert jumlah_penempatan(kon) == 0


def test_pilih_anak_milik_akun_lain_tidak_ditemukan(kon):
    kelas_kit.lunas(kon, siswa=7)
    kid = kelompok(kon)
    with pytest.raises(d.PesananTidakDitemukan):
        jp.pilih_kelompok(kon, AKUN_B, 7, kid, KINI)
    assert jumlah_penempatan(kon) == 0


def test_pilih_tanpa_order_mini_aktif_konflik(kon):
    kelas_kit.lunas(kon, siswa=7, paket="private")
    kid = kelompok(kon)
    with pytest.raises(dasar.KelasKonflik):
        jp.pilih_kelompok(kon, AKUN_A, 7, kid, KINI)
    assert jumlah_penempatan(kon) == 0


def test_pilih_kelompok_yang_ditutup_ditolak(kon):
    kelas_kit.lunas(kon, siswa=7)
    kid = kelompok(kon, **TANGGAL_LAMPAU)
    with pytest.raises(d.PesananKonflik):
        jp.pilih_kelompok(kon, AKUN_A, 7, kid, KINI)
    assert jumlah_penempatan(kon) == 0
