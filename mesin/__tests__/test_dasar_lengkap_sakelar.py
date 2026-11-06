"""Sakelar OSN_DASAR_LENGKAP: pembaca mengenal semua jenis, writer hanya tambah_dasar.

Writer dan keterangan level dipilih SEKALI saat topik terdaftar (impor),
sedangkan palang per template membaca lingkungan tiap panggilan. Karena itu
kasus "sakelar hidup" dijalankan di proses terpisah dengan variabel terpasang
sebelum impor; setenv di tengah test hanya membuka palang tanpa mengubah writer.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import assistant_actions
import assistant_catalog
import basic_numbers_versions as versi
import database
import generator
import question_variants_ui
import similar_practice
import topics
from choice_generation import buat_lembar_pilihan
from http_test_kit import SANDI_GURU, ServerUji

TOPIK = "bilangan-dasar"
NAMA = "OSN_DASAR_LENGKAP"
LAMA = "tambah_dasar"
BARU = ("kurang_dasar", "bilangan_hilang", "nilai_tempat", "bandingkan_bilangan")
LEVEL = ("P1", "P2")
AKAR_MESIN = Path(__file__).resolve().parents[1]
FOLDER_TEST = Path(__file__).resolve().parent


def periksa_hanya_tambah_dasar():
    """Invarian sakelar mati; dipakai langsung dan di proses mutasi."""
    paket = topics.ambil(TOPIK)
    assert paket.komposisi_writer is not None, "writer sakelar mati wajib terpasang"
    for level in LEVEL:
        assert paket.komposisi_untuk(level) == (LAMA,) * 10, level
        for seed in range(30):
            for jumlah in (None, 20):
                lembar = generator.buat_lembar(seed, level=level, topik=TOPIK, jumlah_soal=jumlah)
                assert {s.template_id for s in lembar.soal} == {LAMA}, (level, seed)


@pytest.fixture(autouse=True)
def sakelar_mati(monkeypatch):
    monkeypatch.delenv(NAMA, raising=False)
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")  # topik terbuka; jenis baru tetap tertutup


@pytest.mark.parametrize("nilai,aktif", [(None, False), ("0", False), ("1", True), (" 1 ", True)])
def test_nilai_sakelar(nilai, aktif, monkeypatch):
    if nilai is None:
        monkeypatch.delenv(NAMA, raising=False)
    else:
        monkeypatch.setenv(NAMA, nilai)
    assert versi.dasar_lengkap_aktif() is aktif


@pytest.mark.parametrize("nilai", ["", "true", "2", "-1", "on", "00"])
def test_nilai_sakelar_tidak_sah_ditolak(nilai, monkeypatch):
    monkeypatch.setenv(NAMA, nilai)
    with pytest.raises(ValueError, match=NAMA):
        versi.dasar_lengkap_aktif()


def test_writer_dan_keterangan_mengikuti_sakelar(monkeypatch):
    assert versi.pilih_komposisi_writer() == {lv: (LAMA,) * 10 for lv in LEVEL}
    assert versi.keterangan_level() == {
        "P1": "Hasil penjumlahan sampai 10",
        "P2": "Hasil penjumlahan 11–20, termasuk melewati 10",
    }
    monkeypatch.setenv(NAMA, "1")
    assert versi.pilih_komposisi_writer() is None
    assert all("Campuran" in teks for teks in versi.keterangan_level().values())


def test_mati_pembaca_tetap_mengenal_jenis_baru():
    from rumus import kartu_untuk
    from template_labels import nama_tipe_soal
    from templates import REGISTRI
    from visual_inventory import inventaris_template
    paket = topics.ambil(TOPIK)
    assert paket.komposisi_writer is not None
    for level in LEVEL:
        assert set(paket.komposisi[level]) == {LAMA, *BARU}
    inventaris = {r["template_id"] for r in inventaris_template()}
    for tid in BARU:
        assert tid in REGISTRI and tid in paket.templates and tid in inventaris
        assert kartu_untuk(tid) is not None
        assert nama_tipe_soal(tid) != tid
    assert paket.keterangan_level == versi.KETERANGAN_MATI


def test_mati_lembar_hanya_tambah_dasar():
    periksa_hanya_tambah_dasar()


@pytest.mark.parametrize("level", LEVEL)
def test_mati_lembar_pilihan_ganda_dan_gabungan_hanya_tambah_dasar(level):
    for seed in range(20):
        pg = buat_lembar_pilihan(seed, level=level, topik=TOPIK, jumlah_soal=15)
        assert {s.template_id for s in pg.soal} == {LAMA}
    gabungan = topics.gabungan([TOPIK, "pola-bilangan"])
    assert not set(BARU) & set(gabungan.komposisi_untuk(level) if level in gabungan.komposisi else ())


@pytest.mark.parametrize("tid", BARU)
def test_mati_urutan_eksplisit_ditolak(tid):
    with pytest.raises(ValueError, match="belum dibuka"):
        generator.buat_lembar(0, urutan=(tid,) * 3, level="P1", topik=TOPIK)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "dasar-lengkap-sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


def _template_sesi(kon, sesi):
    return {b[0] for b in kon.execute(
        "SELECT so.template_id FROM sesi_soal ss JOIN soal so ON so.id = ss.soal_id "
        "WHERE ss.sesi_id = ?", (sesi,))}


def _jumlah_baris(kon):
    return tuple(kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
                 for t in ("sesi", "soal", "sesi_soal"))


@pytest.mark.parametrize("level", LEVEL)
def test_mati_sesi_database_hanya_tambah_dasar(db, level):
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    for seed in range(10):
        for format_jawaban in ("isian", "pilihan_ganda"):
            sesi = database.buat_sesi(db, siswa, seed, topik=TOPIK, level=level,
                                      format_jawaban=format_jawaban)
            assert _template_sesi(db, sesi) == {LAMA}
        gabungan = database.buat_sesi_gabungan(db, siswa, seed, [TOPIK, "pola-bilangan"], level=level)
        assert not _template_sesi(db, gabungan) & set(BARU)


@pytest.mark.parametrize("tid", BARU)
def test_mati_urutan_database_ditolak_tanpa_menulis(db, tid):
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    awal = _jumlah_baris(db)
    with pytest.raises(ValueError, match="belum dibuka"):
        database.buat_sesi_dari_urutan(db, siswa, 5, (tid,) * 5, topik=TOPIK, level="P1")
    assert _jumlah_baris(db) == awal


def test_mati_remedial_dari_riwayat_jenis_baru_ditolak(db, monkeypatch):
    """Riwayat jenis baru ada (sakelar pernah hidup); remedial tidak boleh membuatnya lagi."""
    siswa = database.tambah_siswa(db, "Sintetis", tingkat="P3", pemilik="guru")
    monkeypatch.setattr(versi, "dasar_lengkap_aktif", lambda: True)
    sesi = database.buat_sesi_dari_urutan(db, siswa, 3, ("kurang_dasar",), topik=TOPIK, level="P1")
    butir = database.isi_sesi(db, sesi)[0]
    jawaban = database.simpan_jawaban(db, butir["sesi_soal_id"], jawaban="999", cara="hitung")
    database.simpan_diagnosis(db, jawaban, benar=False, kode_usulan="K", kode_final="K", alasan="Sintetis")
    db.execute("UPDATE sesi SET selesai='2026-11-01', direview='2026-11-01' WHERE id=?", (sesi,))
    monkeypatch.undo()
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    awal = _jumlah_baris(db)
    with pytest.raises(ValueError, match="belum dibuka"):
        database.buat_sesi_remedial(db, siswa, seed=4, level="P1", jumlah_soal=10,
                                    template_ids=["kurang_dasar"], sumber_sesi_id=sesi)
    assert _jumlah_baris(db) == awal


@pytest.mark.parametrize("tid", BARU)
def test_mati_latihan_serupa_tidak_membuat_jenis_baru(tid):
    with pytest.raises(similar_practice.LatihanSerupaTidakTersedia):
        similar_practice._pilih_soal_baru(tid, "P1", 7, set())


def test_mati_pendamping_tidak_menawarkan_jenis_baru():
    penawaran = {t.id for t in assistant_catalog.buat_katalog().template}
    assert LAMA in penawaran and not set(BARU) & penawaran
    audit = {t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=False).template}
    assert {LAMA, *BARU} <= audit
    for tid in BARU:
        with pytest.raises(assistant_actions.GalatTindakan):
            assistant_actions.validasi_usulan(
                {"topik_id": TOPIK, "level": "P1", "template_ids": [tid], "jumlah_soal": 10})
    assert assistant_actions.validasi_usulan(
        {"topik_id": TOPIK, "level": "P1", "template_ids": [LAMA], "jumlah_soal": 10})


@pytest.mark.parametrize("level", LEVEL)
def test_mati_pola_soal_di_ui_mengikuti_writer(level):
    assert question_variants_ui._pola_soal(TOPIK, level) == ("Penjumlahan sampai 20",)


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, "Anak Sintetis T3", "P3", pemilik="guru")
    try:
        yield srv
    finally:
        srv.berhenti()


@pytest.mark.parametrize("level", LEVEL)
def test_mati_http_latihan_hanya_tambah_dasar(server, level):
    kode, _, _ = server.minta("/sesi-baru/%d" % server.siswa, auth=("guru", SANDI_GURU),
                              data={"topik": TOPIK, "variasi_dasar": level})
    assert kode == 200
    with server.buka() as kon:
        sesi = kon.execute("SELECT id FROM sesi ORDER BY id DESC").fetchone()[0]
        assert _template_sesi(kon, sesi) == {LAMA}


SKRIP_LEMBAR = """
import json, sys
{tambahan}
import generator, topics
paket = topics.ambil('bilangan-dasar')
hasil = {{
    'tanda': [[s.tanda_tangan for s in generator.buat_lembar(n, level=lv, topik='bilangan-dasar').soal]
              for lv in ('P1', 'P2') for n in range(21)],
    'jenis': {{lv: sorted({{t for n in range(21) for t in
               (s.template_id for s in generator.buat_lembar(n, level=lv, topik='bilangan-dasar').soal)}})
              for lv in ('P1', 'P2')}},
    'writer_none': paket.komposisi_writer is None,
    'keterangan': paket.keterangan_level,
}}
print(json.dumps(hasil, sort_keys=True))
"""


def _jalankan(skrip, **env_tambahan):
    env = {k: v for k, v in os.environ.items() if k != NAMA}
    env.update(env_tambahan)
    return subprocess.run([sys.executable, "-c", skrip], cwd=AKAR_MESIN, env=env,
                          capture_output=True, text=True)


def _lembar(**env):
    hasil = _jalankan(SKRIP_LEMBAR.format(tambahan=""), **env)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_hidup_komposisi_campuran_dan_deterministik_lintas_proses():
    awal = _lembar(**{NAMA: "1", "PYTHONHASHSEED": "0", "OSN_MATERI_DASAR": "1"})
    lain = _lembar(**{NAMA: "1", "PYTHONHASHSEED": "123", "OSN_MATERI_DASAR": "1"})
    assert awal == lain
    assert awal["writer_none"] is True
    assert all("Campuran" in teks for teks in awal["keterangan"].values())
    for level in LEVEL:
        assert awal["jenis"][level] == sorted([LAMA, *BARU])
    # Lembar bawaan 10 soal: dua soal untuk tiap jenis dari lima.
    for tanda in (awal["tanda"][0], awal["tanda"][21]):
        for jenis in (LAMA, *BARU):
            assert sum(t.split("|")[1].startswith(jenis) for t in tanda) == 2, jenis


def test_mati_di_proses_terpisah_sama_dengan_bawaan():
    mati = _lembar(**{NAMA: "0", "PYTHONHASHSEED": "7", "OSN_MATERI_DASAR": "1"})
    assert mati["writer_none"] is False
    assert all(mati["jenis"][lv] == [LAMA] for lv in LEVEL)
    assert mati["keterangan"] == versi.KETERANGAN_MATI


def test_nilai_salah_di_lingkungan_menggagalkan_impor_topik():
    hasil = _jalankan("import topics; topics.ambil('bilangan-dasar')", **{NAMA: "true"})
    assert hasil.returncode != 0 and NAMA in hasil.stderr


SKRIP_MUTASI = """
import sys
sys.path.insert(0, {folder!r})
import basic_numbers_versions
{mutasi}
import topics
from test_dasar_lengkap_sakelar import periksa_hanya_tambah_dasar
periksa_hanya_tambah_dasar()
print('INVARIAN_LOLOS')
"""


def test_mutation_sakelar_dipaksa_hidup_membuat_invarian_merah():
    """Invarian lolos pada kode asli dan gagal bila sakelar dipaksa hidup sebelum impor topik."""
    env = {"OSN_MATERI_DASAR": "1", "OSN_MATEMATIKA_VERSI": "2", "OSN_TEORI_BILANGAN_VERSI": "2",
           "OSN_KATALOG_VERSI": "1"}
    asli = _jalankan(SKRIP_MUTASI.format(folder=str(FOLDER_TEST), mutasi=""), **env)
    assert asli.returncode == 0 and "INVARIAN_LOLOS" in asli.stdout, asli.stderr
    paksa = "basic_numbers_versions.dasar_lengkap_aktif = lambda: True"
    rusak = _jalankan(SKRIP_MUTASI.format(folder=str(FOLDER_TEST), mutasi=paksa), **env)
    assert rusak.returncode != 0 and "AssertionError" in rusak.stderr
    assert "INVARIAN_LOLOS" not in rusak.stdout
