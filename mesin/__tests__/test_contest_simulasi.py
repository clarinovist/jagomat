"""Simulasi Lomba 35 soal: perakit (sebaran, isian, ulang jenis, kunci), pelonggaran larangan, dan store per mode.

Latihan 10 soal wajib identik dengan perakit sebelum Simulasi ada: sidik 40 seed di bawah dihitung dari kode
HEAD 7b299cc (sebelum perubahan) dan dari kode baru, keduanya sama.
"""
import hashlib
import time
from collections import Counter

import pytest

import contest_core as C
import contest_paket as PK
import contest_session as S
import contest_store as T
import contest_templates
import database

KATALOG = contest_templates.katalog()
SEKARANG = 1_800_000_000
JUMLAH_SEED_SIMULASI = 150
SIDIK_LATIHAN_40_SEED = "db8f210bbd737183a28714999e2c6c4f217f90d4136e7a90be625bcb154240dc"
BATAS_DETIK_PER_SESI = 2.0


def _keluarga(template_id):
    template = next(t for t in KATALOG if t.id == template_id)
    return template.keluarga or template.id


@pytest.fixture(scope="module")
def simulasi_banyak():
    return [S.rakit_sesi(seed, KATALOG, frozenset(), mode=PK.MODE_SIMULASI) for seed in range(JUMLAH_SEED_SIMULASI)]


# --- Latihan tidak berubah ------------------------------------------------------------------------------

def test_latihan_identik_dengan_perakit_sebelum_simulasi_ada():
    sidik = hashlib.sha256()
    for seed in range(40):
        for b in S.rakit_sesi(seed, KATALOG, frozenset()).butir:
            sidik.update(repr((b.nomor, C.tanda_tangan(b.soal), b.pilihan, b.posisi_kunci)).encode())
    assert sidik.hexdigest() == SIDIK_LATIHAN_40_SEED


def test_mode_tidak_dikenal_ditolak():
    with pytest.raises(ValueError):
        S.rakit_sesi(1, KATALOG, frozenset(), mode="ujian")


# --- bentuk simulasi ------------------------------------------------------------------------------------

def test_simulasi_35_soal_30_pg_5_isian_dengan_sebaran_pdf(simulasi_banyak):
    for sesi in simulasi_banyak:
        assert [b.nomor for b in sesi.butir] == list(range(1, 36))
        jenis = Counter(b.soal.jenis for b in sesi.butir)
        assert jenis == {C.JENIS_PG: 30, C.JENIS_ISIAN: 5}
        assert Counter(b.soal.topik for b in sesi.butir) == S.SEBARAN_SIMULASI


def test_isian_tersebar_minimal_tiga_topik_maksimal_dua_per_topik(simulasi_banyak):
    for sesi in simulasi_banyak:
        topik = Counter(b.soal.topik for b in sesi.butir if b.soal.jenis == C.JENIS_ISIAN)
        assert len(topik) >= 3 and max(topik.values()) <= 2


def test_jenis_soal_paling_banyak_dua_kali_dan_tanpa_soal_kembar(simulasi_banyak):
    ada_ulang = False
    for sesi in simulasi_banyak:
        keluarga = Counter(_keluarga(b.soal.template_id) for b in sesi.butir)
        assert max(keluarga.values()) <= S.MAKS_PAKAI_JENIS_SIMULASI
        ada_ulang = ada_ulang or max(keluarga.values()) == 2
        tanda = [C.tanda_tangan(b.soal) for b in sesi.butir]
        assert len(set(tanda)) == len(tanda)
    assert ada_ulang      # U3: pengulangan jenis memang terjadi (dengan angka berbeda)


def test_kunci_seimbang_7_atau_8_per_huruf_dan_isian_tanpa_posisi(simulasi_banyak):
    for sesi in simulasi_banyak:
        posisi = Counter(b.posisi_kunci for b in sesi.butir if b.soal.jenis == C.JENIS_PG)
        assert sorted(posisi.values()) == [7, 7, 8, 8]
        assert all(b.posisi_kunci == -1 and b.pilihan == () for b in sesi.butir if b.soal.jenis == C.JENIS_ISIAN)
        for b in sesi.butir:
            if b.soal.jenis == C.JENIS_PG:
                assert C.jawaban_benar(b.soal.kunci, b.pilihan[b.posisi_kunci], C.JENIS_PG)


def test_urut_mudah_ke_sulit_tingkat_dalam_batas_dan_inggris_maksimal_dua(simulasi_banyak):
    for sesi in simulasi_banyak:
        tingkat = [b.soal.tingkat for b in sesi.butir]
        assert tingkat == sorted(tingkat)
        hitung = Counter(tingkat)
        for level, (minimal, maksimal) in S.BATAS_PER_TINGKAT_SIMULASI.items():
            assert minimal <= hitung[level] <= maksimal
        assert sum(1 for b in sesi.butir if b.soal.inggris) <= S.MAKS_INGGRIS_SIMULASI


def test_simulasi_deterministik_per_seed_dan_berbeda_antarseed():
    satu = S.rakit_sesi(11, KATALOG, frozenset(), mode=PK.MODE_SIMULASI)
    assert satu == S.rakit_sesi(11, KATALOG, frozenset(), mode=PK.MODE_SIMULASI)
    assert satu != S.rakit_sesi(12, KATALOG, frozenset(), mode=PK.MODE_SIMULASI)


def test_simulasi_menghormati_tanda_tangan_terlarang():
    pertama = S.rakit_sesi(3, KATALOG, frozenset(), mode=PK.MODE_SIMULASI)
    terlarang = frozenset(C.tanda_tangan(b.soal) for b in pertama.butir)
    kedua = S.rakit_sesi(3, KATALOG, terlarang, mode=PK.MODE_SIMULASI)
    assert not terlarang & {C.tanda_tangan(b.soal) for b in kedua.butir}


# --- pelonggaran larangan dari sesi tertua --------------------------------------------------------------

def test_pelonggaran_melepas_larangan_sesi_tertua_lebih_dulu(monkeypatch):
    dicoba = []

    def palsu(seed, pool, terlarang, template_dihindari=frozenset(), mode=PK.MODE_LATIHAN):
        dicoba.append(terlarang)
        if "tertua" in terlarang:
            raise S.GagalMerakitSesi("habis")
        return "sesi"

    monkeypatch.setattr(S, "rakit_sesi", palsu)
    hasil = S.rakit_dengan_pelonggaran(1, KATALOG, [frozenset({"baru"}), frozenset({"tengah"}), frozenset({"tertua"})])

    assert hasil == "sesi"
    assert dicoba == [frozenset({"baru", "tengah", "tertua"}), frozenset({"baru", "tengah"})]


def test_pelonggaran_sampai_tanpa_larangan_lalu_gagal_bila_tetap_tidak_bisa(monkeypatch):
    dicoba = []

    def selalu_gagal(seed, pool, terlarang, template_dihindari=frozenset(), mode=PK.MODE_LATIHAN):
        dicoba.append(terlarang)
        raise S.GagalMerakitSesi("habis")

    monkeypatch.setattr(S, "rakit_sesi", selalu_gagal)
    with pytest.raises(S.GagalMerakitSesi):
        S.rakit_dengan_pelonggaran(1, KATALOG, [frozenset({"a"}), frozenset({"b"})])
    assert dicoba == [frozenset({"a", "b"}), frozenset({"a"}), frozenset()]


def test_tanpa_kegagalan_pelonggaran_sama_dengan_rakit_sesi_biasa():
    larangan = [frozenset({"x|1"}), frozenset({"y|2"})]
    assert (S.rakit_dengan_pelonggaran(5, KATALOG, larangan)
            == S.rakit_sesi(5, KATALOG, frozenset({"x|1", "y|2"})))


# --- store per mode -------------------------------------------------------------------------------------

@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "lomba.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Simulasi", pemilik="guru")


def test_mulai_simulasi_menyimpan_mode_35_soal_dan_batas_60_menit(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7, mode=T.SIMULASI)

    assert (sesi.mode, sesi.jumlah_soal, sesi.batas_epoch - sesi.mulai_epoch) == ("simulasi", 35, 3600)
    assert T.ambil_sesi(kon, anak, sesi.id, SEKARANG) == sesi
    assert kon.execute("SELECT MAX(nomor) FROM lomba_soal WHERE sesi_id = ?", (sesi.id,)).fetchone()[0] == 35
    assert T.soal_untuk_anak(kon, anak, sesi.id, 35).nomor == 35


def test_latihan_bawaan_tetap_10_soal_15_menit(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7)

    assert (sesi.mode, sesi.jumlah_soal, sesi.batas_epoch - sesi.mulai_epoch) == ("latihan", 10, 900)
    with pytest.raises(T.SesiTidakDitemukan):
        T.soal_untuk_anak(kon, anak, sesi.id, 11)


def test_durasi_khusus_disalin_ke_batas_sesi(kon, anak):
    sesi = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7, mode=T.SIMULASI, durasi_detik=45 * 60)
    assert sesi.batas_epoch == SEKARANG + 45 * 60


@pytest.mark.parametrize("ubah", [{"mode": "ujian"}, {"durasi_detik": 0}, {"durasi_detik": 180 * 60 + 1},
                                  {"durasi_detik": True}, {"durasi_detik": 60.0}])
def test_mode_atau_durasi_tidak_sah_ditolak_tanpa_membuat_sesi(kon, anak, ubah):
    with pytest.raises(ValueError):
        T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7, **ubah)
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 0


def test_sesi_berjalan_mode_lain_dilanjutkan_bukan_dibuat_baru(kon, anak):
    latihan = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=7)
    lanjut = T.mulai_atau_lanjut(kon, anak, SEKARANG + 10, seed=8, mode=T.SIMULASI)
    assert lanjut.id == latihan.id and lanjut.mode == "latihan"


def test_rotasi_latihan_hanya_membaca_sesi_latihan(kon, anak, monkeypatch):
    latihan = T.mulai_atau_lanjut(kon, anak, SEKARANG, seed=1)
    T.kumpulkan(kon, anak, latihan.id, SEKARANG + 300)
    simulasi = T.mulai_atau_lanjut(kon, anak, SEKARANG + 1000, seed=2, mode=T.SIMULASI)
    T.kumpulkan(kon, anak, simulasi.id, SEKARANG + 2000)

    larangan, dihindari = T._riwayat(kon, anak)

    template_latihan = {r[0] for r in kon.execute("SELECT template_id FROM lomba_soal WHERE sesi_id = ?", (latihan.id,))}
    assert dihindari == template_latihan
    assert len(larangan) == 2 and len(larangan[0]) == 35 and len(larangan[1]) == 10   # terbaru dulu


def test_empat_puluh_sesi_beruntun_campuran_tidak_pernah_gagal(kon, anak):
    """Risiko bank 38 jenis: larangan 5 sesi terakhir (hingga 175 soal) tidak boleh membuat sesi gagal dirakit."""
    pola = [T.LATIHAN, T.LATIHAN, T.SIMULASI, T.SIMULASI, T.SIMULASI, T.LATIHAN, T.SIMULASI]
    sekarang = SEKARANG
    terlama = 0.0
    riwayat = []
    for urut in range(40):
        mode = pola[urut % len(pola)]
        mulai = time.perf_counter()
        sesi = T.mulai_atau_lanjut(kon, anak, sekarang, seed=1000 + urut, mode=mode)
        terlama = max(terlama, time.perf_counter() - mulai)
        assert sesi.mode == mode and sesi.jumlah_soal == (35 if mode == T.SIMULASI else 10)
        tanda = {r[0] for r in kon.execute("SELECT tanda_tangan FROM lomba_soal WHERE sesi_id = ?", (sesi.id,))}
        assert not tanda & frozenset().union(*riwayat[-S.RIWAYAT_SESI:])    # larangan tidak perlu dilonggarkan
        riwayat.append(tanda)
        T.kumpulkan(kon, anak, sesi.id, sekarang + 600)
        sekarang += 4000
    assert terlama < BATAS_DETIK_PER_SESI


# --- asal kumpul per mode -------------------------------------------------------------------------------

@pytest.mark.parametrize("waktu,terisi,durasi,harapan", [
    (599, 35, 3600, True), (600, 12, 3600, False), (3000, 11, 3600, True), (3600, 35, 3600, False),
    (300, 20, 300, False),       # Guru mengatur 5 menit dan waktunya habis: bukan "cepat"
    (299, 20, 300, True),
    (600, 12, None, False), (599, 12, None, True),
])
def test_asal_kumpul_simulasi_kurang_12_terisi_atau_kurang_10_menit(waktu, terisi, durasi, harapan):
    assert PK.asal_kumpul(waktu, terisi, PK.MODE_SIMULASI, durasi) is harapan


def test_asal_kumpul_latihan_tidak_berubah():
    assert PK.asal_kumpul(119, 10) and PK.asal_kumpul(500, 2) and not PK.asal_kumpul(120, 3)
    assert PK.asal_kumpul(119, 10, PK.MODE_LATIHAN, 900) and not PK.asal_kumpul(120, 3, PK.MODE_LATIHAN, 900)
