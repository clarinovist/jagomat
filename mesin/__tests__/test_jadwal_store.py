"""Domain jadwal Paket Belajar pada DB sintetis: kelompok, 8 pertemuan WIB, kuota, penempatan, dan sesi."""
import pytest

import jadwal_dasar as jd
import jadwal_store as js
import kelas_kit
import schema_jadwal

GURU = "akun_" + "9" * 32
TANGGAL = "2026-11-21"
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


def test_buat_kelompok_membuat_delapan_pertemuan_dua_kali_seminggu_wib(kon):
    kid = _kelompok(kon)
    detail = js.detail_kelompok(kon, kid)
    assert len(detail["sesi"]) == 8
    assert detail["sesi"][0]["mulai"] == "2026-11-21T02:00:00"   # 09.00 WIB
    assert all(s["menit"] == 60 for s in detail["sesi"])
    assert [s["ke"] for s in detail["sesi"]] == list(range(1, 9))
    assert detail["sesi"][1]["mulai"] == "2026-11-24T02:00:00"   # +3 hari
    assert detail["sesi"][2]["mulai"] == "2026-11-28T02:00:00"   # +7 hari
    assert detail["sesi"][7]["mulai"] == "2026-12-15T02:00:00"   # +24 hari: selesai dalam satu bulan
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
    js.tempatkan(kon, "admin_sintetis", tagihan.order_id, guru_id=guru, tanggal="2026-11-23",
                 jam="16:30", sekarang=kelas_kit.SESUDAH_UPLOAD)
    ringkas = js.ringkas_order(kon, tagihan.order_id)
    assert ringkas["kelompok_id"] is None and ringkas["guru_id"] == guru
    assert ringkas["lokasi"] == schema_jadwal.LOKASI_PRIVATE
    assert len(ringkas["sesi"]) == 8 and ringkas["sesi"][0]["mulai"] == "2026-11-23T09:30:00"
    assert ringkas["sesi"][1]["mulai"] == "2026-11-26T09:30:00"
    js.lepas_penempatan(kon, "admin_sintetis", tagihan.order_id, versi=ringkas["dibuat"],
                        sekarang=kelas_kit.SESUDAH_UPLOAD)
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
    js.tempatkan(kon, "admin_sintetis", tagihan.order_id, guru_id=GURU, tanggal="2026-11-23", jam="16:30",
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    sesi = js.ringkas_order(kon, tagihan.order_id)["sesi"][0]
    js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-11-24", jam="17:00",
                      sekarang=kelas_kit.SESUDAH_UPLOAD)
    berubah = js.pertemuan_dari(kon, sesi["id"])
    assert berubah["mulai"] == "2026-11-24T10:00:00" and berubah["ke"] == 1
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


# --- batas akses, kelompok selesai, duplikat, dan "berikut" -----------------------------------
# Akses `lunas` pada SESUDAH_UPLOAD berakhir 2026-12-20T09:30:00 UTC (= 20 Des 16.30 WIB).
AKSES_AKHIR = "2026-12-20T09:30:00"
SETELAH_SELESAI = "2026-12-16T00:00:00"   # semua pertemuan kelompok TANGGAL sudah lewat, akses masih aktif


def _jumlah(kon, tabel, **kolom):
    sql = "SELECT COUNT(*) FROM %s" % tabel
    if kolom:
        sql += " WHERE " + " AND ".join("%s=?" % k for k in kolom)
    return kon.execute(sql, tuple(kolom.values())).fetchone()[0]


def _privat(kon, tanggal, jam, siswa=1, n=1):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    return tagihan.order_id, lambda: js.tempatkan(
        kon, "admin_sintetis", tagihan.order_id, guru_id=GURU, tanggal=tanggal, jam=jam,
        sekarang=kelas_kit.SESUDAH_UPLOAD)


def test_akses_order_sesuai_asumsi_tes(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    assert kon.execute("SELECT berakhir FROM kelas_akses WHERE order_id=?",
                       (tagihan.order_id,)).fetchone()[0] == AKSES_AKHIR


def test_private_pertemuan_terakhir_melewati_akses_ditolak_tanpa_tulis(kon):
    order_id, tempatkan = _privat(kon, "2026-11-26", "16:31")     # ke-8 = 20 Des 16.31 WIB, 1 menit lewat
    with pytest.raises(jd.JadwalTidakSah, match="masa akses"):
        tempatkan()
    assert _jumlah(kon, "jadwal_penempatan", order_id=order_id) == 0
    assert _jumlah(kon, "jadwal_pertemuan", order_id=order_id) == 0


def test_private_pertemuan_terakhir_tepat_di_batas_akses_diterima(kon):
    order_id, tempatkan = _privat(kon, "2026-11-26", "16:30")     # ke-8 = persis akhir akses
    tempatkan()
    sesi = js.ringkas_order(kon, order_id)["sesi"]
    assert sesi[-1]["mulai"] == AKSES_AKHIR


def test_mini_kelompok_selesai_ditolak_tanpa_penempatan(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalKonflik, match="selesai"):
        js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid, sekarang=SETELAH_SELESAI)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_mini_kelompok_semua_pertemuan_dibatalkan_dianggap_selesai(kon):
    kid = _kelompok(kon)
    for sesi in js.detail_kelompok(kon, kid)["sesi"]:
        js.batalkan_pertemuan(kon, "admin_sintetis", sesi["id"], batal=True, sekarang=kelas_kit.KINI)
    mini = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalKonflik, match="selesai"):
        js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_mini_kelompok_masih_punya_pertemuan_mendatang_boleh_dimasuki(kon):
    kid = _kelompok(kon)                                           # baru ke-1 yang mulai (21 Nov); ke-8 = 15 Des
    mini = kelas_kit.lunas(kon, 1, "mini")
    js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid, sekarang="2026-11-21T03:00:00")
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


def test_mini_pertemuan_aktif_terakhir_melewati_akses_ditolak(kon):
    kid = js.buat_kelompok(kon, "admin_sintetis", nama="Mini Z", lokasi="Ruang 1", guru_id=GURU, kuota=5,
                           tanggal="2026-11-26", jam="16:31", sekarang=kelas_kit.KINI)   # ke-8 lewat 1 menit
    mini = kelas_kit.lunas(kon, 1, "mini")
    with pytest.raises(jd.JadwalTidakSah, match="masa akses"):
        js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 0
    terakhir = js.detail_kelompok(kon, kid)["sesi"][-1]            # yang dibatalkan tidak dihitung
    js.batalkan_pertemuan(kon, "admin_sintetis", terakhir["id"], batal=True, sekarang=kelas_kit.KINI)
    js.tempatkan(kon, "admin_sintetis", mini.order_id, kelompok_id=kid, sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.detail_kelompok(kon, kid)["terisi"] == 1


def test_ubah_pertemuan_private_tidak_boleh_melewati_akses(kon):
    order_id, tempatkan = _privat(kon, "2026-11-23", "16:30")
    tempatkan()
    sesi = js.ringkas_order(kon, order_id)["sesi"][7]
    asal = sesi["mulai"]
    with pytest.raises(jd.JadwalTidakSah, match="masa akses"):
        js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-12-20", jam="16:31",
                          sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["mulai"] == asal
    js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-12-20", jam="16:30",
                      sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["mulai"] == AKSES_AKHIR


def test_ubah_pertemuan_kelompok_dibatasi_akses_anggota_terpendek(kon):
    kid = _kelompok(kon)
    pendek = kelas_kit.lunas(kon, 1, "mini")                                   # akses sampai AKSES_AKHIR
    panjang = kelas_kit.lunas(kon, 2, "mini", n=2, putus="2026-11-20T23:00:00")  # akses lebih lama
    for tagihan in (pendek, panjang):
        js.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=kid,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
    sesi = js.detail_kelompok(kon, kid)["sesi"][7]
    asal = sesi["mulai"]
    with pytest.raises(jd.JadwalTidakSah, match="masa akses"):
        js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-12-20", jam="16:31",
                          sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["mulai"] == asal
    js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2026-12-20", jam="16:30",
                      sekarang=kelas_kit.SESUDAH_UPLOAD)


def test_ubah_pertemuan_kelompok_tanpa_anggota_tanpa_batas_akses(kon):
    kid = _kelompok(kon)
    sesi = js.detail_kelompok(kon, kid)["sesi"][7]
    js.ubah_pertemuan(kon, "admin_sintetis", sesi["id"], tanggal="2027-01-15", jam="09:00",
                      sekarang=kelas_kit.SESUDAH_UPLOAD)
    assert js.pertemuan_dari(kon, sesi["id"])["mulai"] == "2027-01-15T02:00:00"


def test_buat_kelompok_kembar_ditolak_dan_klik_ganda_tidak_menulis(kon):
    _kelompok(kon)
    with pytest.raises(jd.JadwalKonflik):
        js.buat_kelompok(kon, "admin_sintetis", nama="  mini a ", lokasi="Ruang 9", guru_id=GURU, kuota=3,
                         tanggal=TANGGAL, jam=JAM, sekarang=kelas_kit.KINI)
    assert _jumlah(kon, "jadwal_kelompok") == 1
    assert _jumlah(kon, "jadwal_pertemuan") == 8


def test_buat_kelompok_nama_sama_beda_waktu_atau_waktu_sama_beda_nama_boleh(kon):
    _kelompok(kon)
    js.buat_kelompok(kon, "admin_sintetis", nama="Mini A", lokasi="Ruang 1", guru_id=GURU, kuota=5,
                     tanggal=TANGGAL, jam="10:00", sekarang=kelas_kit.KINI)
    js.buat_kelompok(kon, "admin_sintetis", nama="Mini B", lokasi="Ruang 1", guru_id=GURU, kuota=5,
                     tanggal=TANGGAL, jam=JAM, sekarang=kelas_kit.KINI)
    assert _jumlah(kon, "jadwal_kelompok") == 3


def test_daftar_kelompok_berikut_adalah_pertemuan_aktif_mendatang(kon):
    kid = _kelompok(kon)                                  # ke-1..8 = 21, 24, 28 Nov; 1, 5, 8, 12, 15 Des 09.00
    sesi = js.detail_kelompok(kon, kid)["sesi"]
    awal = js.daftar_kelompok(kon, kelas_kit.KINI)[0]
    assert awal["berikut"] == "2026-11-21T02:00:00"
    sesudah_dua = js.daftar_kelompok(kon, "2026-11-25T00:00:00")[0]["berikut"]
    assert sesudah_dua == "2026-11-28T02:00:00"           # yang sudah lewat tidak dihitung
    js.batalkan_pertemuan(kon, "admin_sintetis", sesi[2]["id"], batal=True, sekarang=kelas_kit.KINI)
    assert js.daftar_kelompok(kon, "2026-11-25T00:00:00")[0]["berikut"] == "2026-12-01T02:00:00"
    assert js.daftar_kelompok(kon, SETELAH_SELESAI)[0]["berikut"] is None
