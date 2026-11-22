"""Hasil rinci dan progress Latihan Lomba: kunci hanya dibaca setelah sesi selesai; ringkasan per anak."""
import json

import pytest

import contest_core as C
import contest_results as R
import contest_store as T
import database

SEKARANG = 1_800_000_000
TOPIK = C.TOPIK


@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "hasil.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Satu", pemilik="guru")


@pytest.fixture
def anak_lain(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Dua", pemilik="guru")


def _baris(kon, sesi_id):
    return kon.execute("SELECT * FROM lomba_soal WHERE sesi_id=? ORDER BY nomor", (sesi_id,)).fetchall()


def _jawaban_benar(baris):
    if baris["jenis"] == "isian":
        return baris["kunci"]
    return C.HURUF[json.loads(baris["pilihan_json"]).index(baris["kunci"])]


def _jawaban_salah(baris):
    if baris["jenis"] == "isian":
        return str(int(baris["kunci"]) + 1)
    return next(h for h in C.HURUF if h != _jawaban_benar(baris))


def _sesi(kon, siswa_id, urut, benar_sampai, jawab_sampai=10, selesai_setelah=300):
    """Satu sesi selesai: soal <= benar_sampai benar, soal sampai jawab_sampai salah, sisanya kosong."""
    mulai = SEKARANG + urut * 5000
    sesi = T.mulai_atau_lanjut(kon, siswa_id, mulai, seed=urut)
    for baris in _baris(kon, sesi.id):
        nomor = baris["nomor"]
        if nomor > jawab_sampai:
            continue
        jawaban = _jawaban_benar(baris) if nomor <= benar_sampai else _jawaban_salah(baris)
        T.simpan_jawaban(kon, siswa_id, sesi.id, nomor, jawaban, mulai + 10)
    T.kumpulkan(kon, siswa_id, sesi.id, mulai + selesai_setelah)
    return sesi.id


def _benar_menurut_uji(baris, jawaban):
    """Penilaian versi uji (mandiri dari kode): bandingkan nilai pilihan atau angka dengan kunci."""
    if jawaban is None:
        return False
    if baris["jenis"] == "isian":
        return int(jawaban) == int(baris["kunci"])
    return json.loads(baris["pilihan_json"])["ABCD".index(jawaban)] == baris["kunci"]


# --- hasil rinci -------------------------------------------------------------------------

def test_hasil_rinci_sesi_yang_masih_berjalan_ditolak(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=1)
    with pytest.raises(T.SesiBerjalan):
        R.hasil_rinci(kon, anak, sesi.id, SEKARANG + 5)


def test_hasil_rinci_memuat_sepuluh_butir_berurutan_dengan_nilai_sama_seperti_ringkas(kon, anak):
    sesi_id = _sesi(kon, anak, 1, benar_sampai=4)
    rinci = R.hasil_rinci(kon, anak, sesi_id, SEKARANG + 99999)
    ringkas = T.hasil_ringkas(kon, anak, sesi_id, SEKARANG + 99999)
    assert [b.nomor for b in rinci.butir] == list(range(1, 11))
    assert (rinci.nilai, rinci.jumlah_soal, rinci.waktu_terpakai_detik) == (4, 10, ringkas.waktu_terpakai_detik)
    assert rinci.sesi.status == "dikumpul" and sum(b.benar for b in rinci.butir) == 4


def test_setiap_butir_memuat_jawaban_anak_kunci_huruf_kunci_dan_pembahasan(kon, anak):
    sesi_id = _sesi(kon, anak, 2, benar_sampai=5)
    rinci = R.hasil_rinci(kon, anak, sesi_id, SEKARANG + 99999)
    for butir, baris in zip(rinci.butir, _baris(kon, sesi_id)):
        assert butir.kunci == baris["kunci"] and butir.jenis == baris["jenis"]
        assert butir.benar is _benar_menurut_uji(baris, butir.jawaban)
        assert butir.pembahasan == tuple(json.loads(baris["pembahasan_json"])) and butir.pembahasan
        if baris["jenis"] == "pg":
            assert butir.kunci_huruf == _jawaban_benar(baris)
            assert butir.pilihan == tuple(json.loads(baris["pilihan_json"]))
            if butir.jawaban:
                assert butir.jawaban_teks == butir.pilihan["ABCD".index(butir.jawaban)]
        else:
            assert butir.kunci_huruf is None and butir.pilihan == ()
            assert butir.jawaban_teks == butir.jawaban


def test_jawaban_salah_pg_membawa_label_kesalahan_pengecoh_yang_dipilih(kon, anak):
    sesi_id = _sesi(kon, anak, 3, benar_sampai=0)
    rinci = R.hasil_rinci(kon, anak, sesi_id, SEKARANG + 99999)
    for butir, baris in zip(rinci.butir, _baris(kon, sesi_id)):
        if baris["jenis"] == "pg":
            label = {p["nilai"]: p["kesalahan"] for p in json.loads(baris["pengecoh_json"])}
            assert butir.kesalahan == label[butir.jawaban_teks] and butir.kesalahan
        else:
            assert butir.kesalahan is None


def test_soal_kosong_dan_soal_benar_tidak_punya_label_kesalahan(kon, anak):
    sesi_id = _sesi(kon, anak, 4, benar_sampai=3, jawab_sampai=3)
    rinci = R.hasil_rinci(kon, anak, sesi_id, SEKARANG + 99999)
    assert all(b.kesalahan is None for b in rinci.butir)
    assert all(b.jawaban is None and not b.benar for b in rinci.butir[3:])
    assert all(b.benar for b in rinci.butir[:3])


def test_nilai_per_topik_menjumlah_ke_total_dan_cocok_dengan_hitungan_uji(kon, anak):
    sesi_id = _sesi(kon, anak, 5, benar_sampai=6)
    rinci = R.hasil_rinci(kon, anak, sesi_id, SEKARANG + 99999)
    harapan = {}
    for baris, butir in zip(_baris(kon, sesi_id), rinci.butir):
        benar, total = harapan.get(baris["topik"], (0, 0))
        harapan[baris["topik"]] = (benar + int(butir.benar), total + 1)
    assert {n.topik: (n.benar, n.total) for n in rinci.per_topik} == harapan
    assert sum(n.total for n in rinci.per_topik) == 10 and sum(n.benar for n in rinci.per_topik) == 6
    assert [n.topik for n in rinci.per_topik] == [t for t in TOPIK if t in harapan]


def test_hasil_rinci_sesi_milik_anak_lain_ditolak(kon, anak, anak_lain):
    sesi_id = _sesi(kon, anak, 6, benar_sampai=2)
    with pytest.raises(T.SesiTidakDitemukan):
        R.hasil_rinci(kon, anak_lain, sesi_id, SEKARANG + 99999)


def test_sesi_yang_waktunya_habis_menjadi_hasil_rinci_dengan_jawaban_sebelum_batas(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7)
    baris = _baris(kon, sesi.id)[0]
    T.simpan_jawaban(kon, anak, sesi.id, 1, _jawaban_benar(baris), SEKARANG + 100)
    rinci = R.hasil_rinci(kon, anak, sesi.id, SEKARANG + 5000)
    assert rinci.sesi.status == "waktu_habis" and rinci.nilai == 1


# --- riwayat dan progress -----------------------------------------------------------------

def test_riwayat_urut_dari_yang_terlama_dan_hanya_sesi_selesai(kon, anak):
    a = _sesi(kon, anak, 1, benar_sampai=2)
    b = _sesi(kon, anak, 2, benar_sampai=7)
    T.mulai_atau_lanjut(kon, anak, SEKARANG + 3 * 5000, seed=3)           # sesi ketiga masih berjalan
    riwayat = R.riwayat_sesi(kon, anak, SEKARANG + 3 * 5000 + 10)
    assert [s.sesi_id for s in riwayat] == [a, b]
    assert [s.nilai for s in riwayat] == [2, 7]
    assert all(s.jumlah_soal == 10 and sum(n.total for n in s.per_topik) == 10 for s in riwayat)


def test_riwayat_menutup_sesi_berjalan_yang_waktunya_sudah_lewat(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=1)
    riwayat = R.riwayat_sesi(kon, anak, SEKARANG + 901)
    assert [s.sesi_id for s in riwayat] == [sesi.id] and riwayat[0].status == "waktu_habis"
    assert riwayat[0].waktu_terpakai_detik == 900


def test_riwayat_hanya_milik_anak_itu(kon, anak, anak_lain):
    _sesi(kon, anak, 1, benar_sampai=2)
    _sesi(kon, anak_lain, 2, benar_sampai=9)
    assert [s.nilai for s in R.riwayat_sesi(kon, anak, SEKARANG + 99999)] == [2]
    assert [s.nilai for s in R.riwayat_sesi(kon, anak_lain, SEKARANG + 99999)] == [9]


def test_progres_tanpa_sesi_kosong(kon, anak):
    p = R.progres(kon, anak, SEKARANG)
    assert (p.jumlah, p.terbaik, p.rata_rata, p.terakhir, p.selisih_tren) == (0, None, None, None, None)
    assert p.sesi == () and p.per_topik_total == ()


def test_progres_menghitung_terbaik_rata_rata_terakhir_dan_total_per_topik(kon, anak):
    for urut, benar in enumerate([2, 5, 3, 8], start=1):
        _sesi(kon, anak, urut, benar_sampai=benar)
    p = R.progres(kon, anak, SEKARANG + 99999)
    assert (p.jumlah, p.terbaik, p.terakhir) == (4, 8, 8)
    assert p.rata_rata == 4.5
    assert sum(n.total for n in p.per_topik_total) == 40 and sum(n.benar for n in p.per_topik_total) == 18


@pytest.mark.parametrize("nilai,harapan", [
    ([2, 4], None),                       # kurang dari 4 sesi: belum ada tren
    ([2, 4, 5], None),
    ([2, 3, 4, 8], 2.0),                  # 3 terakhir (5.0) - 3 pertama (3.0); mulai dihitung pada 4 sesi
    ([8, 7, 6, 4, 3, 2], -4.0),           # 3 terakhir 3.0 - 3 pertama 7.0
])
def test_selisih_tren_membandingkan_tiga_sesi_terakhir_dengan_tiga_pertama(kon, anak, nilai, harapan):
    for urut, benar in enumerate(nilai, start=1):
        _sesi(kon, anak, urut, benar_sampai=benar)
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert p.selisih_tren == (None if harapan is None else pytest.approx(harapan))


# --- jenis soal yang paling sering salah ----------------------------------------------------

def test_jenis_sering_salah_mengurutkan_dari_salah_terbanyak_dan_membatasi_jumlah(kon, anak):
    for urut in (1, 2, 3):
        _sesi(kon, anak, urut, benar_sampai=0)                          # semua salah
    hasil = R.jenis_sering_salah(kon, anak, SEKARANG + 99999, batas=5)
    assert 1 <= len(hasil) <= 5
    assert [j.salah for j in hasil] == sorted((j.salah for j in hasil), reverse=True)
    assert all(j.salah == j.total for j in hasil)                       # tak ada yang benar
    assert all(j.salah >= 1 and j.label and "_" not in j.label for j in hasil)


def test_jenis_sering_salah_mengabaikan_jenis_yang_selalu_benar(kon, anak):
    for urut in (1, 2):
        _sesi(kon, anak, urut, benar_sampai=10)
    assert R.jenis_sering_salah(kon, anak, SEKARANG + 99999) == ()


def test_jenis_sering_salah_hanya_menghitung_soal_anak_itu(kon, anak, anak_lain):
    _sesi(kon, anak_lain, 1, benar_sampai=0)
    assert R.jenis_sering_salah(kon, anak, SEKARANG + 99999) == ()




# --- sesi dikumpulkan asal (asal_kumpul) ------------------------------------------------------

def _riwayat(kon, anak):
    return R.riwayat_sesi(kon, anak, SEKARANG + 999999)


@pytest.mark.parametrize("detik,diharap", [(119, True), (120, False), (13, True), (300, False)])
def test_batas_waktu_sesi_di_bawah_120_detik_asal_kumpul(kon, anak, detik, diharap):
    _sesi(kon, anak, 1, benar_sampai=5, selesai_setelah=detik)
    sesi = _riwayat(kon, anak)[0]
    assert (sesi.waktu_terpakai_detik, sesi.terisi, sesi.asal_kumpul) == (detik, 10, diharap)


@pytest.mark.parametrize("terisi,diharap", [(2, True), (3, False), (0, True), (10, False)])
def test_batas_terisi_kurang_dari_tiga_soal_asal_kumpul(kon, anak, terisi, diharap):
    _sesi(kon, anak, 1, benar_sampai=5, jawab_sampai=terisi, selesai_setelah=300)
    sesi = _riwayat(kon, anak)[0]
    assert (sesi.terisi, sesi.asal_kumpul) == (terisi, diharap)


def test_riwayat_tetap_memuat_semua_sesi_selesai_termasuk_asal_kumpul_berurutan(kon, anak):
    ids = [_sesi(kon, anak, 1, 5), _sesi(kon, anak, 2, 10, selesai_setelah=13), _sesi(kon, anak, 3, 4)]
    riwayat = _riwayat(kon, anak)
    assert [s.sesi_id for s in riwayat] == ids
    assert [s.asal_kumpul for s in riwayat] == [False, True, False]


def test_nilai_ringkas_sesi_asal_kumpul_tetap_apa_adanya(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=7, selesai_setelah=13)
    sesi = _riwayat(kon, anak)[0]
    assert sesi.nilai == 7 and sesi.jumlah_soal == 10


def test_progres_campuran_agregat_hanya_dari_sesi_sah_tetapi_jumlah_dan_terakhir_semua(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=4)
    _sesi(kon, anak, 2, benar_sampai=6)
    _sesi(kon, anak, 3, benar_sampai=10, selesai_setelah=119)     # asal kumpul, nilai tertinggi
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert (p.jumlah, p.jumlah_asal_kumpul) == (3, 1)
    assert p.terbaik == 6 and p.rata_rata == 5.0
    assert p.terakhir == 10                                       # nilai sesi terakhir, semua sesi
    assert sum(n.total for n in p.per_topik_total) == 20          # hanya dua sesi sah
    assert sum(n.benar for n in p.per_topik_total) == 10


def test_progres_sesi_asal_kumpul_karena_terisi_sedikit_juga_dikecualikan(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=6)
    _sesi(kon, anak, 2, benar_sampai=2, jawab_sampai=2)           # terisi 2 -> asal kumpul
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert (p.jumlah, p.jumlah_asal_kumpul, p.terbaik, p.rata_rata) == (2, 1, 6, 6.0)


def test_progres_semua_sesi_asal_kumpul_tanpa_terbaik_rata_tren_dan_topik(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=9, selesai_setelah=10)
    _sesi(kon, anak, 2, benar_sampai=3, selesai_setelah=50)
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert (p.jumlah, p.jumlah_asal_kumpul) == (2, 2)
    assert (p.terbaik, p.rata_rata, p.rata_awal, p.rata_akhir, p.selisih_tren) == (None, None, None, None, None)
    assert p.terakhir == 3 and p.per_topik_total == ()


def test_progres_hanya_sesi_asal_kumpul_dengan_banyak_sesi_tetap_tanpa_tren(kon, anak):
    for urut in range(1, 6):
        _sesi(kon, anak, urut, benar_sampai=urut, selesai_setelah=30)
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert p.jumlah == 5 and p.rata_awal is None and p.rata_akhir is None


def test_tren_rata_tiga_sesi_sah_pertama_dan_terakhir_mengabaikan_sesi_cepat(kon, anak):
    for urut, benar in enumerate([2, 4, 6, 8, 10], start=1):
        _sesi(kon, anak, urut, benar_sampai=benar)
    _sesi(kon, anak, 6, benar_sampai=0, selesai_setelah=5)        # cepat, nilai 0: tak boleh menurunkan rata-rata
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert p.rata_awal == pytest.approx(4.0) and p.rata_akhir == pytest.approx(8.0)
    assert p.selisih_tren == pytest.approx(4.0)


def test_tren_none_bila_sesi_sah_kurang_dari_empat_walau_total_sesi_cukup(kon, anak):
    for urut, benar in enumerate([2, 4, 6], start=1):
        _sesi(kon, anak, urut, benar_sampai=benar)
    _sesi(kon, anak, 4, benar_sampai=10, selesai_setelah=5)
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert p.jumlah == 4 and p.rata_awal is None and p.rata_akhir is None and p.selisih_tren is None


def test_tren_muncul_tepat_pada_empat_sesi_sah(kon, anak):
    for urut, benar in enumerate([2, 3, 4, 8], start=1):
        _sesi(kon, anak, urut, benar_sampai=benar)
    p = R.progres(kon, anak, SEKARANG + 999999)
    assert p.rata_awal == pytest.approx(3.0) and p.rata_akhir == pytest.approx(5.0)


def test_jenis_sering_salah_tidak_menghitung_sesi_asal_kumpul(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=10)
    _sesi(kon, anak, 2, benar_sampai=0, selesai_setelah=13)       # semua salah tetapi asal kumpul
    assert R.jenis_sering_salah(kon, anak, SEKARANG + 999999) == ()


def test_jenis_sering_salah_tetap_menghitung_sesi_sah_di_samping_yang_asal_kumpul(kon, anak):
    _sesi(kon, anak, 1, benar_sampai=0)
    _sesi(kon, anak, 2, benar_sampai=0, selesai_setelah=13)
    hasil = R.jenis_sering_salah(kon, anak, SEKARANG + 999999)
    assert hasil and all(j.total == 1 and j.salah == 1 for j in hasil)    # hanya sesi pertama


# --- label jenis untuk Guru --------------------------------------------------------------------

def _semua_id_template():
    import contest_templates  # noqa: F401  (mendaftarkan semua modul template)
    return [t.id for t in C.semua()]


def test_setiap_template_terdaftar_punya_label_jenis_unik_tidak_kosong_dan_pendek():
    ids = _semua_id_template()
    labels = [R.label_jenis(i) for i in ids]
    assert len(ids) >= 30                                         # registry terisi penuh, bukan kosong
    assert all(i in R.LABEL_JENIS for i in ids)
    assert all(label.strip() and len(label) <= 60 for label in labels)
    assert len(set(labels)) == len(labels)
    assert all("_" not in label for label in labels)


def test_tabel_label_jenis_tidak_memuat_id_yang_tak_terdaftar():
    assert set(R.LABEL_JENIS) <= set(_semua_id_template())


@pytest.mark.parametrize("id_template,label", [
    ("bgn_persegi_kisi", "Menghitung persegi di papan kotak"),
    ("bil_pola_berulang", "Pola berulang"),
    ("ops_ayam_kambing", "Kaki ayam dan kambing (jumlah kepala dan kaki)"),
    ("ops_umur", "Selisih umur"),
])
def test_label_jenis_memakai_tabel_label_ramah_guru(id_template, label):
    assert R.label_jenis(id_template) == label


@pytest.mark.parametrize("id_template,label", [
    ("bil_pola_tak_dikenal", "pola tak dikenal"),
    ("ops_inggris_baru_sekali", "inggris baru sekali"),
])
def test_label_jenis_id_tak_dikenal_jatuh_ke_perilaku_lama(id_template, label):
    assert R.label_jenis(id_template) == label
