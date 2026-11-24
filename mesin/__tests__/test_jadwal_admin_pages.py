"""Render admin jadwal: teks kunci, form, escape, dan tidak ada sandi ulang."""
from datetime import datetime, timedelta

import jadwal_admin_pages as ui

GURU = {"akun_" + "9" * 32: "guru-satu"}
TOKEN = {"csrf": "c", "tinjauan": "t"}


def _kelompok(nama="Mini A", kuota=5, terisi=1, berikut="2026-11-28T02:00:00"):
    return {"id": "klp_" + "a" * 32, "nama": nama, "lokasi": "Ruang 1",
            "guru_id": "akun_" + "9" * 32, "kuota": kuota, "terisi": terisi, "berikut": berikut}


def test_blok_daftar_memuat_kelompok_form_dan_escape():
    isi = ui.blok_daftar([_kelompok(nama="<b>Mini</b>")], GURU, TOKEN)
    assert "&lt;b&gt;Mini&lt;/b&gt;" in isi and "<b>Mini</b>" not in isi
    assert "1/5" in isi and "guru-satu" in isi
    assert 'name="nama"' in isi and 'name="jumlah"' not in isi
    assert 'name="kuota"' in isi and 'name="tanggal"' in isi and 'name="jam"' in isi
    assert "Buat kelompok + 8 pertemuan" in isi
    assert 'name="reauth"' not in isi


def test_blok_daftar_tanpa_guru_tidak_menampilkan_form():
    isi = ui.blok_daftar([], {}, TOKEN)
    assert ui.COPY_TANPA_GURU in isi and "Buat kelompok" not in isi


def test_halaman_kelompok_memuat_anggota_dan_delapan_sesi_dengan_aksi():
    awal = datetime(2026, 11, 28, 2)
    sesi = [{"id": i, "ke": i, "menit": 60, "dibatalkan": 0,
             "mulai": (awal + timedelta(days=i - 1)).strftime("%Y-%m-%dT%H:%M:%S")} for i in range(1, 9)]
    detail = {"kelompok": {"id": "klp_" + "a" * 32, "paket": "mini", "nama": "Mini A",
                           "lokasi": "Ruang 1", "guru_id": "akun_" + "9" * 32, "kuota": 5},
              "anggota": [{"order_id": "kor_" + "b" * 32, "siswa_id": 12, "paket": "mini",
                           "berakhir": "2026-12-20T10:00:00"}],
              "sesi": sesi, "terisi": 1}
    tokens = {"ubah": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
    isi = ui.halaman_kelompok(detail, GURU, tokens)
    assert "Mini A" in isi and "Ruang 1" in isi and "guru-satu" in isi
    assert isi.count('action="/admin/kelas/pertemuan"') == 8
    assert isi.count('action="/admin/kelas/pertemuan/batal"') == 8
    assert "kor_" + "b" * 32 in isi
    assert "Ubah kelompok" in isi and "Lepas" not in isi
    assert 'name="reauth"' not in isi


def test_penempatan_mini_hanya_kelompok_dengan_sisa_dan_hormati_status():
    tokens = {"tempatkan": TOKEN, "lepas": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
    penuh = _kelompok(nama="Penuh", kuota=2, terisi=2)
    sisa = _kelompok(nama="Sisa", kuota=5, terisi=1)
    isi = ui.blok_penempatan({"paket": "mini"}, None, [penuh, sisa], GURU, True, tokens)
    assert "Sisa" in isi and "Penuh" not in isi and "sisa 4 anak" in isi
    assert "Tempatkan ke kelompok" in isi
    assert ui.COPY_KUOTA_PENUH in ui.blok_penempatan({"paket": "mini"}, None, [penuh], GURU, True, tokens)
    assert ui.COPY_BELUM_AKTIF in ui.blok_penempatan({"paket": "mini"}, None, [sisa], GURU, False, tokens)


def test_penempatan_private_dan_ringkasan_sesi():
    tokens = {"tempatkan": TOKEN, "lepas": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
    isi = ui.blok_penempatan({"paket": "private"}, None, [], GURU, True, tokens)
    assert "Buat 8 pertemuan Private" in isi and 'name="tanggal"' in isi
    sesi = [{"id": 1, "ke": 1, "mulai": "2026-12-01T09:30:00", "menit": 60, "dibatalkan": 0}]
    ringkas = {"kelompok_id": None, "guru_id": "akun_" + "9" * 32, "lokasi": "Online", "sesi": sesi}
    isi = ui.blok_penempatan({"paket": "private"}, ringkas, [], GURU, True, tokens)
    assert "Private · Online" in isi and "Lepas penempatan" in isi
    assert 'action="/admin/kelas/pertemuan"' in isi


def test_penempatan_kelompok_read_only_dengan_tautan():
    tokens = {"lepas": TOKEN}
    sesi = [{"id": 1, "ke": 1, "mulai": "2026-11-28T02:00:00", "menit": 60, "dibatalkan": 0}]
    ringkas = {"kelompok_id": "klp_" + "a" * 32, "kelompok_nama": "Mini A", "kelompok_lokasi": "Ruang 1",
               "kelompok_guru": "akun_" + "9" * 32, "sesi": sesi}
    isi = ui.blok_penempatan({"paket": "mini"}, ringkas, [], GURU, True, tokens)
    assert 'href="/admin/kelas/kelompok?id=klp_' in isi
    assert 'action="/admin/kelas/pertemuan"' not in isi
    assert "Lepas penempatan" in isi
