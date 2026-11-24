"""Domain jadwal Paket Belajar pada DB sintetis: kelompok, 8 pertemuan WIB, kuota, penempatan, dan sesi."""
import pytest

import jadwal_dasar as jd
import jadwal_store as js
import kelas_kit
import schema_jadwal

GURU = "akun_" + "9" * 32
TANGGAL = "2026-11-28"
JAM = "09:00"


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _kelompok(kon, *, kuota=5):
    return js.buat_kelompok(kon, "admin_sintetis", nama="Mini A", lokasi="Ruang 1", guru_id=GURU,
                            kuota=kuota, tanggal=TANGGAL, jam=JAM, sekarang=kelas_kit.KINI)


def test_buat_kelompok_membuat_delapan_pertemuan_mingguan_wib(kon):
    kid = _kelompok(kon)
    detail = js.detail_kelompok(kon, kid)
    assert len(detail["sesi"]) == 8
    assert detail["sesi"][0]["mulai"] == "2026-11-28T02:00:00"   # 09.00 WIB
    assert all(s["menit"] == 60 for s in detail["sesi"])
    assert [s["ke"] for s in detail["sesi"]] == list(range(1, 9))
    assert detail["sesi"][1]["mulai"] == "2026-12-05T02:00:00"   # +7 hari
    assert detail["terisi"] == 0


def test_tanggal_mulai_lampau_ditolak(kon):
    with pytest.raises(jd.JadwalTidakSah):
        js.buat_kelompok(kon, "admin_sintetis", nama="Mini", lokasi="Ruang", guru_id=GURU, kuota=5,
                         tanggal="2026-11-19", jam=JAM, sekarang=kelas_kit.KINI)


def test_tempatkan_mini_sampai_kuota_penuh(kon):
    kid = _kelompok(kon, kuota=2)
    for n in (1, 2):
        tagihan = kelas_kit.lunas(kon, n, "mini", n=n)
        js.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=kid, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 2
    ketiga = kelas_kit.lunas(kon, 3, "mini", n=3)
    with pytest.raises(jd.JadwalPenuh):
        js.tempatkan(kon, "admin_sintetis", ketiga.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 2


def test_hanya_order_aktif_yang_bisa_ditempatkan(kon):
    kid = _kelompok(kon)
    tagihan = kelas_kit.tagih(kon, 1)
    with pytest.raises(jd.JadwalKonflik):
        js.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_private_membuat_delapan_sesi_dan_lepas_menghapus(kon):
    guru = "akun_" + "7" * 32
    tagihan = kelas_kit.lunas(kon, 1, "private")
    js.tempatkan(kon, "admin_sintetis", tagihan.order_id, guru_id=guru, tanggal="2026-12-01",
                 jam="16:30", sekarang=kelas_kit.SESUDAH_UPLOAD)
    ringkas = js.ringkas_order(kon, tagihan.order_id)
    assert ringkas["kelompok_id"] is None and ringkas["guru_id"] == guru
    assert ringkas["lokasi"] == schema_jadwal.LOKASI_PRIVATE
    assert len(ringkas["sesi"]) == 8 and ringkas["sesi"][0]["mulai"] == "2026-12-01T09:30:00"
    js.lepas_penempatan(kon, "admin_sintetis", tagihan.order_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.ringkas_order(kon, tagihan.order_id) is None
    assert kon.execute("SELECT COUNT(*) FROM jadwal_pertemuan WHERE order_id=?",
                       (tagihan.order_id,)).fetchone()[0] == 0


def test_paket_dan_jenis_penempatan_harus_cocok(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalTidakSah):
        js.tempatkan(kon, "admin_sintetis", mini.order_id, guru_id=GURU, tanggal=TANGGAL, jam=JAM,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    privat = kelas_kit.lunas(kon, 2, "private", n=2)
    with pytest.raises(jd.JadwalTidakSah):
        js.tempatkan(kon, "admin_sintetis", privat.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)


def test_anak_tidak_bisa_punya_dua_penempatan(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid, sekarang=kelas_kit.SESUDAH_UPLOAD)
    privat = kelas_kit.lunas(kon, 1, "private", n=2)
    with pytest.raises(jd.JadwalKonflik):
        js.tempatkan(kon, "admin_sintetis", privat.order_id, guru_id=GURU, tanggal=TANGGAL, jam=JAM,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)


def test_kuota_tidak_boleh_di_bawah_anggota_dan_ubah_lain_tetap_boleh(kon):
    kid = _kelompok(kon, kuota=2)
    for n in (1, 2):
        tagihan = kelas_kit.lunas(kon, n, "mini", n=n)
        js.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    with pytest.raises(jd.JadwalKonflik):
        js.ubah_kelompok(kon, "admin_sintetis", kid, nama="Mini B", lokasi="Ruang 2", guru_id=GURU,
                         kuota=1, sekarang=kelas_kit.SESUDAH_UPLOAD)
    js.ubah_kelompok(kon, "admin_sintetis", kid, nama="Mini B", lokasi="Ruang 2", guru_id=GURU,
                     kuota=2, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["kelompok"]["nama"] == "Mini B"


def test_ubah_dan_batalkan_pertemuan_tanpa_mengubah_identitas(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    js.tempatkan(kon, "admin_sintetis", tagihan.order_id, guru_id=GURU, tanggal="2026-12-01", jam="16:30",
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    sesi = js.ringkas_order(kon, tagihan.order_id)["sesi"][0]
    js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-12-02", jam="17:00",
                      sekarang=kelas_kit.SESUDAH_UPLOAD)
    berubah = js.pertemuan_dari(kon, sesi["id"])
    assert berubah["mulai"] == "2026-12-02T10:00:00" and berubah["ke"] == 1
    js.batalkan_pertemuan(kon, "admin_sintetis", sesi["id"], batal=True, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["dibatalkan"] == 1
    js.batalkan_pertemuan(kon, "admin_sintetis", sesi["id"], batal=False, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["dibatalkan"] == 0


def test_guru_dan_kelompok_tidak_sah_ditolak(kon):
    with pytest.raises(jd.JadwalTidakSah):
        js.buat_kelompok(kon, "admin_sintetis", nama="Mini", lokasi="Ruang", guru_id="bukan-guru", kuota=5,
                         tanggal=TANGGAL, jam=JAM, sekarang=kelas_kit.KINI)
    tagihan = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalTidakDitemukan):
        js.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=jd.id_kelompok_baru(),
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
