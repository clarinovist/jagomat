"""Label awam topik yang bisa diubah admin (3d): pembaca saat request, hasil lama tetap, fallback ke bawaan.

Data SINTETIS. DB kurikulum diarahkan ke tmp_path lewat `KURIKULUM_BERKAS_DB`; tidak ada data anak nyata.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_anak_komponen  # noqa: E402
import cek_gratis  # noqa: E402
import cek_pages  # noqa: E402
import database  # noqa: E402
import kurikulum_override as ko  # noqa: E402
import topics  # noqa: E402
import topik_awam  # noqa: E402
from cek_gratis_kit import ID_A, ID_B, SEKARANG, jawab, mulai_cek, tambah_anak, tandai_selesai  # noqa: E402

PENGUKURAN = "pengukuran"          # label bawaan = nama resmi ("Pengukuran")
ARITMETIKA = "aritmetika-dasar"    # label bawaan "Aritmetika dasar", nama resmi "Aritmetika Dasar"
GEOMETRI = "geometri-datar"
LABEL_BARU = "Hitung dasar"


@pytest.fixture(autouse=True)
def _db_kurikulum_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(ko.ENV_BERKAS_DB, str(tmp_path / "kurikulum.db"))
    ko.bersihkan_cache()
    yield
    ko.bersihkan_cache()


@pytest.fixture(autouse=True)
def materi_dasar_mati(monkeypatch):
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "cek.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _ubah(topik_id=ARITMETIKA, label=LABEL_BARU, revisi=0):
    return ko.ubah_label(topik_id, label, actor_id="admin-sintetis", revisi_diharapkan=revisi)


def _nilai(kon, id_akun):
    anak = tambah_anak(kon, "Anak Sintetis", "guru-" + id_akun[-2:], 5)
    sesi_id = mulai_cek(kon, id_akun, anak, "guru-" + id_akun[-2:])
    jawab(kon, sesi_id, {ARITMETIKA: 5, "aritmatika-lanjut": 3, GEOMETRI: 1})
    tandai_selesai(kon, sesi_id)
    assert cek_gratis.selesaikan_jika_siap(kon, id_akun, SEKARANG) is True
    return cek_gratis.baca_hasil(kon, id_akun)["ringkasan"]


# --- topik_awam.nama ---------------------------------------------------------------------------

def test_nama_memakai_bawaan_tanpa_berkas_dan_tidak_membuat_berkas(tmp_path):
    assert topik_awam.nama(ARITMETIKA) == topik_awam.NAMA_AWAM[ARITMETIKA]
    assert not (tmp_path / "kurikulum.db").exists()


def test_nama_mengikuti_override_langsung_dan_kembali_saat_dikembalikan():
    _ubah()
    assert topik_awam.nama(ARITMETIKA) == LABEL_BARU
    ko.kembalikan_label(ARITMETIKA, actor_id="admin-sintetis", revisi_diharapkan=1)
    assert topik_awam.nama(ARITMETIKA) == topik_awam.NAMA_AWAM[ARITMETIKA]


def test_nama_awam_konstanta_tetap_bawaan_kode_walau_override():
    _ubah()
    assert topik_awam.NAMA_AWAM[ARITMETIKA] == "Aritmetika dasar"


def test_nama_topik_tanpa_label_tetap_keyerror():
    with pytest.raises(KeyError):
        topik_awam.nama("kombinatorik")
    with pytest.raises(KeyError):
        topik_awam.nama("topik-tak-dikenal")


def test_db_rusak_label_bawaan_tanpa_galat(tmp_path):
    (tmp_path / "kurikulum.db").write_bytes(b"bukan sqlite sama sekali")
    ko.bersihkan_cache()
    assert topik_awam.nama(ARITMETIKA) == topik_awam.NAMA_AWAM[ARITMETIKA]
    assert topik_awam.dari_nama_lama("Aritmetika Dasar") == topik_awam.NAMA_AWAM[ARITMETIKA]


# --- dari_nama_lama ----------------------------------------------------------------------------

def test_dari_nama_lama_nama_resmi_menjadi_label_efektif():
    resmi = topics.ambil(ARITMETIKA).nama
    assert resmi != topik_awam.NAMA_AWAM[ARITMETIKA]
    assert topik_awam.dari_nama_lama(resmi) == topik_awam.NAMA_AWAM[ARITMETIKA]
    _ubah()
    assert topik_awam.dari_nama_lama(resmi) == LABEL_BARU


def test_dari_nama_lama_label_tersimpan_dan_tak_dikenal_tetap_utuh():
    _ubah()
    assert topik_awam.dari_nama_lama("Aritmetika dasar") == "Aritmetika dasar"  # label bawaan lama
    assert topik_awam.dari_nama_lama(LABEL_BARU) == LABEL_BARU
    assert topik_awam.dari_nama_lama("Topik Warisan") == "Topik Warisan"


def test_nama_resmi_yang_sama_dengan_label_bawaan_tidak_ikut_berubah():
    """"Pengukuran" = nama resmi sekaligus label bawaan: teks tersimpannya harus tetap utuh."""
    assert topics.ambil(PENGUKURAN).nama == topik_awam.NAMA_AWAM[PENGUKURAN]
    _ubah(PENGUKURAN, "Ukur-ukur")
    assert topik_awam.dari_nama_lama("Pengukuran") == "Pengukuran"
    assert topik_awam.nama(PENGUKURAN) == "Ukur-ukur"


def test_bentrok_nama_resmi_hanya_untuk_nama_yang_dipetakan():
    assert topik_awam.bentrok_nama_resmi(topics.ambil(ARITMETIKA).nama) is True
    assert topik_awam.bentrok_nama_resmi(LABEL_BARU) is False
    assert topik_awam.bentrok_nama_resmi("Pengukuran") is False  # sama dengan label bawaan: tidak dipetakan


# --- hasil cek: lama tetap, baru memakai label baru -------------------------------------------

def test_hasil_lama_tetap_dan_hasil_baru_memakai_label_override(kon):
    lama = _nilai(kon, ID_A)
    assert lama == {"kuat": [topik_awam.NAMA_AWAM[ARITMETIKA]], "perlu": [topik_awam.NAMA_AWAM[GEOMETRI]]}

    _ubah()

    assert cek_gratis.baca_hasil(kon, ID_A)["ringkasan"] == lama  # tersimpan sebagai teks, tidak dihitung ulang
    halaman_lama = cek_pages._blok_ringkasan(cek_gratis.baca_hasil(kon, ID_A)["ringkasan"])
    assert topik_awam.NAMA_AWAM[ARITMETIKA] in halaman_lama and LABEL_BARU not in halaman_lama

    baru = _nilai(kon, ID_B)
    assert baru == {"kuat": [LABEL_BARU], "perlu": [topik_awam.NAMA_AWAM[GEOMETRI]]}
    assert LABEL_BARU in cek_pages._blok_ringkasan(baru)


def test_ringkasan_lama_berisi_nama_resmi_ditampilkan_dengan_label_efektif():
    ringkasan = {"kuat": [topics.ambil(ARITMETIKA).nama], "perlu": []}
    _ubah()
    assert LABEL_BARU in cek_pages._blok_ringkasan(ringkasan)


# --- layar anak --------------------------------------------------------------------------------

def test_layar_anak_memakai_label_baru_tanpa_restart_proses():
    template_id = next(iter(topics.ambil(ARITMETIKA).templates))
    assert ">Aritmetika dasar</span>" in cek_anak_komponen.label_topik(template_id)
    _ubah()
    label = cek_anak_komponen.label_topik(template_id)
    assert ">" + LABEL_BARU + "</span>" in label and "<svg" in label
    ko.kembalikan_label(ARITMETIKA, actor_id="admin-sintetis", revisi_diharapkan=1)
    assert ">Aritmetika dasar</span>" in cek_anak_komponen.label_topik(template_id)


def test_layar_anak_hanya_menampilkan_label_dan_warna_tetap_konstanta():
    _ubah(label="Hitung <b>& dasar")
    template_id = next(iter(topics.ambil(ARITMETIKA).templates))
    label = cek_anak_komponen.label_topik(template_id)
    assert "&lt;b&gt;&amp; dasar" in label and "<b>" not in label  # di-escape
    assert 'class="ubin amber"' in label  # warna tidak ikut override
    assert cek_anak_komponen.WARNA_TOPIK[ARITMETIKA] == "amber"


def test_layar_anak_db_rusak_memakai_label_bawaan(tmp_path):
    (tmp_path / "kurikulum.db").write_bytes(b"bukan sqlite sama sekali")
    ko.bersihkan_cache()
    template_id = next(iter(topics.ambil(ARITMETIKA).templates))
    assert ">Aritmetika dasar</span>" in cek_anak_komponen.label_topik(template_id)


def test_modul_anak_tidak_mengimpor_modul_skor():
    sumber = Path(cek_anak_komponen.__file__).read_text(encoding="utf-8")
    assert "import cek_gratis_skor" not in sumber and "from cek_gratis_skor" not in sumber
