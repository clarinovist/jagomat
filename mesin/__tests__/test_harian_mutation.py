"""Mutation guard Latihan Harian (F4) pada salinan source terisolasi.

Tiap kasus mematikan satu guard di salinan (satu atau beberapa penggantian), memastikan tes terkait MERAH karena
perilaku (bukan import/fixture rusak), lalu memulihkan dan memastikan HIJAU. Workspace asli tidak disentuh.
"""
import pytest

from harian_mutasi_kit import uji_mutasi

BERKAS_TES = ("test_harian_http.py", "test_harian_latihan_store.py", "http_test_kit.py", "conftest.py")
TES_HTTP = "test_harian_http.py"
TES_STORE = "test_harian_latihan_store.py"

# (nama, berkas, [(lama, baru), ...], berkas tes, ekspresi -k)
KASUS = (
    ("kunci_bocor_ke_get_soal", "harian_latihan_store.py", [
        ("    if jawaban is None:\n        return soal, None\n", ""),
        ("UmpanBalik(jawaban[\"pilihan\"], bool(jawaban[\"benar\"]), kunci[\"kunci_indeks\"], kunci[\"pembahasan\"])",
         "UmpanBalik(jawaban[\"pilihan\"] if jawaban else 0, bool(jawaban[\"benar\"]) if jawaban else False, "
         "kunci[\"kunci_indeks\"], kunci[\"pembahasan\"])"),
    ], TES_HTTP, "test_soal_belum_dijawab_tanpa_pembahasan_kunci_dan_markup_pilihan_seragam"),
    ("kunci_bocor_di_penyajian_store", "harian_latihan_store.py", [
        ("\"SELECT penyajian_json, opsi_json FROM harian_soal WHERE sesi_id = ? AND nomor = ?\"",
         "\"SELECT penyajian_json, opsi_json, kunci_indeks, pembahasan FROM harian_soal WHERE sesi_id = ? AND nomor = ?\""),
    ], TES_STORE, "test_muat_soal_belum_dijawab_tanpa_kunci_dan_tanpa_membaca_kolom_rahasia"),
    ("izinkan_jawab_ulang", "harian_latihan_store.py", [
        ("    if nomor <= sesi.terjawab:\n        return HasilJawab(False, None, False)\n", ""),
        ("\"INSERT INTO harian_jawaban (sesi_id, nomor, pilihan, benar, dijawab_epoch) VALUES (?, ?, ?, ?, ?)\"",
         "\"INSERT OR REPLACE INTO harian_jawaban (sesi_id, nomor, pilihan, benar, dijawab_epoch) VALUES (?, ?, ?, ?, ?)\""),
    ], TES_HTTP, "test_jawab_kedua_soal_sama_tidak_mengubah_apa_pun"),
    ("izinkan_jawab_ulang_store", "harian_latihan_store.py", [
        ("    if nomor <= sesi.terjawab:\n        return HasilJawab(False, None, False)\n", ""),
        ("\"INSERT INTO harian_jawaban (sesi_id, nomor, pilihan, benar, dijawab_epoch) VALUES (?, ?, ?, ?, ?)\"",
         "\"INSERT OR REPLACE INTO harian_jawaban (sesi_id, nomor, pilihan, benar, dijawab_epoch) VALUES (?, ?, ?, ?, ?)\""),
    ], TES_STORE, "test_jawab_kedua_untuk_soal_yang_sama_ditolak_tanpa_efek"),
    ("batas_gratis_dimatikan", "harian_latihan_store.py", [
        ("(not akses.tanpa_batas) and terpakai >= akses_harian.BATAS_GRATIS_PER_HARI", "False"),
    ], TES_HTTP, "test_batas_gratis_satu_sesi_dimulai_per_hari_wib_dengan_halaman_ramah"),
    ("batas_gratis_dimatikan_store", "harian_latihan_store.py", [
        ("(not akses.tanpa_batas) and terpakai >= akses_harian.BATAS_GRATIS_PER_HARI", "False"),
    ], TES_STORE, "test_batas_gratis_satu_sesi_dimulai_per_hari_wib"),
    ("batas_gratis_bukan_per_anak", "harian_latihan_store.py", [
        ("WHERE s.siswa_id = ? AND ((s.mulai_epoch", "WHERE ((s.mulai_epoch"),
        ("(siswa_id, awal, akhir, awal, akhir)", "(awal, akhir, awal, akhir)"),
    ], TES_STORE, "test_batas_gratis_per_anak_bukan_per_akun_atau_global or test_jawaban_sesi_anak_lain_tidak_memakai_jatah_anak_ini"),
    ("jatah_hanya_sesi_dimulai_hari_ini", "harian_latihan_store.py", [
        ("\"OR EXISTS (SELECT 1 FROM harian_jawaban j WHERE j.sesi_id = s.id AND j.dijawab_epoch >= ? \"\n        \"AND j.dijawab_epoch < ?))\", (siswa_id, awal, akhir, awal, akhir)",
         "\")\", (siswa_id, awal, akhir)"),
    ], TES_STORE, "test_sesi_menggantung_diselesaikan_di_hari_baru_memakai_jatah_hari_baru or test_menjawab_satu_soal_sesi_lama_di_hari_baru_sudah_menghitung_jatah_hari_itu"),
    ("jatah_mengabaikan_sesi_dimulai_tanpa_jawaban", "harian_latihan_store.py", [
        ("((s.mulai_epoch >= ? AND s.mulai_epoch < ?) \"\n        \"OR EXISTS", "(0 \"\n        \"OR EXISTS"),
        ("(siswa_id, awal, akhir, awal, akhir)", "(siswa_id, awal, awal, akhir)"),
    ], TES_STORE, "test_sesi_yang_baru_dimulai_tanpa_jawaban_sudah_menghitung_jatah"),
    ("jatah_jawaban_batas_atas_inklusif", "harian_latihan_store.py", [
        ("AND j.dijawab_epoch < ?))", "AND j.dijawab_epoch <= ?))"),
    ], TES_STORE, "test_jawaban_tepat_tengah_malam_wib_milik_hari_baru_bukan_hari_lama"),
    ("jatah_jawaban_batas_bawah_eksklusif", "harian_latihan_store.py", [
        ("j.dijawab_epoch >= ? \"", "j.dijawab_epoch > ? \""),
    ], TES_STORE, "test_batas_hari_jawaban_tepat_tengah_malam_wib"),
    ("hari_utc_bukan_wib", "harian_waktu.py", [
        ("OFFSET_WIB_DETIK = 7 * 3600", "OFFSET_WIB_DETIK = 0"),
    ], TES_STORE, "test_batas_gratis_memakai_hari_kalender_wib_bukan_utc"),
    ("siswa_dari_query", "harian_http.py", [
        ("            return _belum_terhubung(penangan, pengguna)\n        nama, id_mentah = rute",
         "            return _belum_terhubung(penangan, pengguna)\n"
         "        _q = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query).get('siswa')\n"
         "        siswa_id = int(_q[0]) if _q else siswa_id\n        nama, id_mentah = rute"),
        ("            sesi, _baru = hs.mulai(kon, siswa_id, isian[\"tingkat\"], _sekarang())",
         "            _q = urllib.parse.parse_qs(urllib.parse.urlparse(penangan.path).query).get('siswa')\n"
         "            siswa_id = int(_q[0]) if _q else siswa_id\n"
         "            sesi, _baru = hs.mulai(kon, siswa_id, isian[\"tingkat\"], _sekarang())"),
    ], TES_HTTP, "test_id_siswa_dari_query_atau_form_diabaikan_atau_ditolak_anak_lain_tidak_tersentuh"),
    ("gerbang_sakelar_get", "harian_http.py", [
        ("    rute = _kenali(jalur, \"GET\")\n    if rute is None or not akses_harian.aktif():", "    rute = _kenali(jalur, \"GET\")\n    if rute is None:"),
    ], TES_HTTP, "test_sakelar_mati_get_identik_dengan_jalur_murid_tak_dikenal"),
    ("gerbang_sakelar_post", "harian_http.py", [
        ("    rute = _kenali(jalur, \"POST\")\n    if rute is None or not akses_harian.aktif():", "    rute = _kenali(jalur, \"POST\")\n    if rute is None:"),
    ], TES_HTTP, "test_sakelar_mati_post_identik_dengan_jalur_tak_dikenal_dan_tanpa_efek"),
    ("gerbang_sakelar_kartu", "harian_http.py", [
        ("    if not akses_harian.aktif():\n        return \"\"\n    sekarang = _sekarang()", "    sekarang = _sekarang()"),
    ], TES_HTTP, "test_sakelar_mati_beranda_murid_tanpa_kartu"),
    ("gerbang_sakelar_ringkasan_ortu", "harian_http.py", [
        ("    if not akses_harian.aktif():\n        return None\n    return hs.ringkasan_harian", "    return hs.ringkasan_harian"),
    ], TES_HTTP, "test_halaman_orang_tua_menampilkan_ringkasan_hanya_bila_sakelar_hidup"),
    ("kepemilikan_sesi_dilepas", "harian_latihan_store.py", [
        ("WHERE s.id = ? AND s.siswa_id = ?\", (sesi_id, siswa_id))", "WHERE s.id = ?\", (sesi_id,))"),
    ], TES_HTTP, "test_anak_lain_tidak_bisa_membaca_menjawab_atau_melihat_hasil_dan_tanpa_efek"),
    ("soal_melompat_diizinkan", "harian_latihan_store.py", [
        ("or nomor > sesi.terjawab + 1:", ":"),
    ], TES_HTTP, "test_nomor_soal_belum_gilirannya_atau_tak_sah_404_identik or test_jawab_soal_yang_belum_gilirannya_404_tanpa_efek"),
    ("satu_sesi_berjalan_tak_ditegakkan", "harian_latihan_store.py", [
        ("    if berjalan is not None:\n        return berjalan, False\n", ""),
    ], TES_STORE, "test_mulai_lagi_saat_berjalan_melanjutkan_tanpa_menghitung_dan_tanpa_menulis"),
    ("jawaban_kesepuluh_tidak_menutup_sesi", "harian_latihan_store.py", [
        ("    selesai = nomor == sesi.jumlah_soal\n", "    selesai = False\n"),
    ], TES_STORE, "test_jawaban_kesepuluh_menutup_sesi_dan_ringkasan_menghitung_benar"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_guard_harian_merah_lalu_pulih(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, BERKAS_TES)
