"""Sambungan empat pembaca ke feature_switch (F2): DB menang, env hanya fallback.

Perilaku live tidak berubah: tanpa berkas DB/baris, hasil identik dengan parsing
env lama, termasuk ValueError nilai asing untuk cetak ringkas dan bank kalimat.
Baris DB (admin) menang atas env; DB rusak fail-closed tanpa memakai env.
Semua DB uji berada di tmp_path lewat SAKELAR_BERKAS_DB.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import choice_pages  # noqa: E402
import feature_switch as fs  # noqa: E402
import funnel_flag  # noqa: E402
import pesanan_transfer_gerbang as gerbang  # noqa: E402
import story_frames  # noqa: E402

# Nama env lama sekaligus nama sakelar DB; satu pasangan per pembaca publik.
PEMBACA = (
    pytest.param("FUNNEL_AKTIF", funnel_flag.funnel_aktif, id="funnel"),
    pytest.param("PESANAN_TRANSFER_AKTIF", gerbang.transfer_aktif, id="transfer"),
    pytest.param("OSN_CETAK_RINGKAS", choice_pages.cetak_ringkas_aktif, id="cetak-ringkas"),
    pytest.param("OSN_BANK_KALIMAT", story_frames.aktif, id="bank-kalimat"),
)
# Dua pembaca yang menolak nilai env asing dengan ValueError.
VALIDATOR = PEMBACA[2:]

SEED = {nama: False for nama in fs.NAMA_SAKELAR}


@pytest.fixture(autouse=True)
def _db_sakelar_terisolasi(tmp_path, monkeypatch):
    """Arahkan DB sakelar ke tmp_path (berkas belum ada), hapus keempat env
    sakelar, dan kosongkan cache sebelum serta sesudah tiap tes."""
    monkeypatch.setenv(fs.ENV_BERKAS_DB, str(tmp_path / "sakelar.db"))
    for nama in fs.NAMA_SAKELAR:
        monkeypatch.delenv(nama, raising=False)
    fs.bersihkan_cache()
    yield
    fs.bersihkan_cache()


def _isi_db(nama, nilai):
    """Seed DB baru lalu set baris `nama` ke `nilai`.

    Pada DB baru seed meninggalkan revisi 1, jadi revisi_diharapkan untuk
    panggilan pertama adalah 1 (mengikuti pola test_feature_switch.py).
    """
    return fs.ubah(nama, nilai, actor_id="tes", revisi_diharapkan=1, seed=SEED)


# --- a. tanpa DB: parsing env lama tetap berlaku -----------------------------

@pytest.mark.parametrize("nilai_env,harapan", [("1", True), (None, False)],
                         ids=["env-satu", "tanpa-env"])
@pytest.mark.parametrize("nama,pembaca", PEMBACA)
def test_tanpa_db_mengikuti_env_lama(nama, pembaca, monkeypatch, nilai_env, harapan):
    # Arrange: berkas DB belum ada; env lama satu-satunya sumber.
    if nilai_env is None:
        monkeypatch.delenv(nama, raising=False)
    else:
        monkeypatch.setenv(nama, nilai_env)

    # Act + Assert: jalur tanpa DB identik dengan perilaku sebelum refactor.
    assert pembaca() is harapan


# --- b. baris DB aktif: hidup tanpa env -------------------------------------

@pytest.mark.parametrize("nama,pembaca", PEMBACA)
def test_db_baris_aktif_hidup_tanpa_env(nama, pembaca):
    # Arrange: hanya baris `nama` yang aktif; env tak diset oleh fixture.
    _isi_db(nama, True)

    # Act + Assert: baris DB (admin) menang; pembaca terhubung ke nama yang tepat.
    assert pembaca() is True


# --- c. baris DB mati: menang atas env "1" -----------------------------------

@pytest.mark.parametrize("nama,pembaca", PEMBACA)
def test_db_baris_mati_menang_atas_env_satu(nama, pembaca, monkeypatch):
    # Arrange: baris DB aktif=0, env lama mencoba menghidupkan.
    _isi_db(nama, False)
    monkeypatch.setenv(nama, "1")

    # Act + Assert: DB menang atas env.
    assert pembaca() is False


# --- d. DB rusak: fail-closed, env tidak dipakai -----------------------------

@pytest.mark.parametrize("nama,pembaca", PEMBACA)
def test_db_sampah_fail_closed_tanpa_env(nama, pembaca, monkeypatch):
    # Arrange: berkas DB berisi byte sampah; env "1" tidak boleh dipakai.
    Path(os.environ[fs.ENV_BERKAS_DB]).write_bytes(os.urandom(512))
    monkeypatch.setenv(nama, "1")

    # Act + Assert: gagal membaca berarti fitur mati, bukan kembali ke env.
    assert pembaca() is False


# --- e/f. khusus cetak ringkas & bank kalimat: ValueError hanya jalur env ----

@pytest.mark.parametrize("nama,pembaca", VALIDATOR)
def test_tanpa_db_env_tak_sah_valueerror(nama, pembaca, monkeypatch):
    # Arrange: tanpa DB, env lama bernilai tak sah.
    monkeypatch.setenv(nama, "true")

    # Act + Assert: ValueError perilaku lama tetap merambat.
    with pytest.raises(ValueError, match=nama):
        pembaca()


@pytest.mark.parametrize("nilai_db,harapan", [(True, True), (False, False)],
                         ids=["db-nyala", "db-mati"])
@pytest.mark.parametrize("nama,pembaca", VALIDATOR)
def test_db_ada_env_tak_sah_hasil_dari_db(nama, pembaca, monkeypatch, nilai_db, harapan):
    # Arrange: baris DB ada; env lama tetap bernilai tak sah.
    _isi_db(nama, nilai_db)
    monkeypatch.setenv(nama, "true")

    # Act + Assert: DB menang, tidak ada ValueError, hasil dari baris.
    assert pembaca() is harapan


# --- gerbang transfer: DB mematikan transfer, rekening tak dibaca ------------

def test_rekening_bila_terbuka_tutup_saat_db_mematikan_transfer(monkeypatch):
    # Arrange: DB mematikan transfer (funnel tetap hidup lewat seed), env lama
    # "1" mencoba membuka, dan baca_publik akan gagal-tes bila terpanggil.
    fs.ubah("PESANAN_TRANSFER_AKTIF", False, actor_id="tes",
            revisi_diharapkan=1, seed=dict(SEED, FUNNEL_AKTIF=True))
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    monkeypatch.setattr(gerbang.pesanan_rekening, "baca_publik",
                        lambda path=None: pytest.fail("rekening dibaca padahal transfer mati"))

    # Act + Assert: gerbang fail-closed tanpa menyentuh rekening.
    assert gerbang.rekening_bila_terbuka(object()) is None
