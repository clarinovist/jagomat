"""Render admin jadwal: penanda bentrok guru berupa TEKS, kolom Peringatan, dan kelompok ditutup tidak bisa dipilih."""
import jadwal_admin_pages as ui

GURU = {"akun_" + "9" * 32: "guru-satu"}
TOKEN = {"csrf": "c", "tinjauan": "t"}
TOKENS = {"tempatkan": TOKEN, "lepas": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
TEKS_SESI = "Bentrok dengan jadwal guru lain"
TEKS_PERINGATAN = ("Guru ini punya pertemuan lain di jam yang sama; periksa dan geser bila perlu. "
                   "Penyimpanan tidak diblokir.")


def _kelompok(nama="Mini A", **tambahan):
    dasar = {"id": "klp_" + "a" * 32, "nama": nama, "lokasi": "Ruang 1", "guru_id": "akun_" + "9" * 32,
             "kuota": 5, "terisi": 1, "berikut": "2026-11-28T02:00:00"}
    return {**dasar, **tambahan}


def _sesi(bentrok=None):
    kunci = {} if bentrok is None else {"bentrok": bentrok}
    return {"id": 1, "ke": 1, "mulai": "2026-12-01T09:30:00", "menit": 60, "dibatalkan": 0, **kunci}


def _detail(sesi):
    return {"kelompok": {"id": "klp_" + "a" * 32, "paket": "mini", "nama": "Mini A", "lokasi": "Ruang 1",
                         "guru_id": "akun_" + "9" * 32, "kuota": 5},
            "anggota": [], "sesi": sesi, "terisi": 0}


def _privat(sesi):
    ringkas = {"kelompok_id": None, "guru_id": "akun_" + "9" * 32, "lokasi": "Online", "sesi": sesi}
    return ui.blok_penempatan({"paket": "private"}, ringkas, [], GURU, True, TOKENS)


def test_daftar_kolom_peringatan_menyebut_jumlah_pertemuan_bentrok_dengan_teks():
    isi = ui.blok_daftar([_kelompok(bentrok=3)], GURU, TOKEN)
    assert "Peringatan" in isi and "Bentrok jadwal guru: 3 pertemuan" in isi


def test_daftar_tanpa_bentrok_atau_tanpa_kunci_menampilkan_strip():
    for kelompok in (_kelompok(bentrok=0), _kelompok()):
        isi = ui.blok_daftar([kelompok], GURU, TOKEN)
        assert "Peringatan" in isi and "<td>—</td>" in isi and "Bentrok jadwal guru" not in isi


def test_halaman_kelompok_menandai_sesi_bentrok_dengan_teks_dan_satu_baris_peringatan():
    tokens = {"ubah": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
    sesi = [{**_sesi(True), "id": 1, "ke": 1}, {**_sesi(False), "id": 2, "ke": 2}]
    isi = ui.halaman_kelompok(_detail(sesi), GURU, tokens)
    assert isi.count(TEKS_SESI) == 1 and isi.count(TEKS_PERINGATAN) == 1


def test_halaman_kelompok_tanpa_bentrok_tidak_memuat_penanda():
    tokens = {"ubah": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
    for sesi in ([_sesi(False)], [_sesi()]):
        isi = ui.halaman_kelompok(_detail(sesi), GURU, tokens)
        assert TEKS_SESI not in isi and TEKS_PERINGATAN not in isi


def test_detail_order_private_menandai_sesi_bentrok_dan_tanpa_bentrok_bersih():
    isi = _privat([_sesi(True)])
    assert isi.count(TEKS_SESI) == 1 and isi.count(TEKS_PERINGATAN) == 1
    bersih = _privat([_sesi(False)])
    assert TEKS_SESI not in bersih and TEKS_PERINGATAN not in bersih


def test_dropdown_menyembunyikan_kelompok_ditutup_dan_pesan_menyebut_ditutup():
    ditutup = _kelompok(nama="Sudah Ditutup", terbuka=False)
    terbuka = _kelompok(nama="Masih Terbuka", terbuka=True)
    isi = ui.blok_penempatan({"paket": "mini"}, None, [ditutup, terbuka], GURU, True, TOKENS)
    assert "Masih Terbuka" in isi and "Sudah Ditutup" not in isi
    semua = ui.blok_penempatan({"paket": "mini"}, None, [ditutup], GURU, True, TOKENS)
    assert ui.COPY_KUOTA_PENUH in semua and "Tempatkan ke kelompok" not in semua
    for kata in ("penuh", "selesai", "ditutup"):
        assert kata in ui.COPY_KUOTA_PENUH


def test_kelompok_tanpa_kunci_terbuka_tetap_bisa_dipilih_untuk_pemanggil_lama():
    isi = ui.blok_penempatan({"paket": "mini"}, None, [_kelompok(nama="Kunci Lama")], GURU, True, TOKENS)
    assert "Kunci Lama" in isi
