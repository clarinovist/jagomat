"""Palang MANUAL-SAJA (pedagogis-kritis): bilangan-sekolah tidak boleh bocor ke siklus.

Topik P3–P5 yang mengikuti pola biasa otomatis masuk Campuran, siklus terpandu,
pemetaan, dan Pendamping. Soal bilangan besar belum punya grup mastery, kartu
intervensi, dan playbook, jadi `Topik.hanya_manual=True` menutup SEMUA jalur
itu, baik sakelar mati maupun hidup. Guru tetap bisa memilihnya di Latihan
manual dan lembar cetak; pembaca histori tetap mengenal ID.

Mutation (wajib): tiap situs diuji MERAH saat atribut dimatikan lewat jalur
yang dipanggil tes (entri PAKET diganti `replace(hanya_manual=False)` dan
Campuran dibangun ulang), lalu hijau setelah monkeypatch memulihkan.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import assistant_actions
import assistant_catalog
import database
import generator
import learning_cycle_service
import learning_cycle_ui
import learning_sessions
import mastery_catalog
import question_context
import question_variants_ui
import topics
from baseline_bilangan_sekolah import SIDIK_BASELINE, sidik
from templates import LEVEL, LEVEL_TINGKAT

TOPIK = "bilangan-sekolah"
TID = "nilai_tempat_besar"
SEMUA = (TID, "urutkan_bilangan", "tambah_kurang_bersusun", "kali_bagi_sekolah",
         "kalimat_matematika")  # Tahap A + B: semua jenis topik ini manual-saja
NAMA_TOPIK = "Bilangan Sekolah"


@pytest.fixture(autouse=True)
def sakelar_hidup(monkeypatch):
    """Kasus terkuat: sakelar HIDUP, topik terbuka, palang manual-saja yang menahan."""
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)


def _bangun_ulang_campuran(monkeypatch):
    """Campuran dibangun sekali dan di-cache; mutasi harus membangunnya ulang."""
    monkeypatch.delitem(topics.PAKET, "campuran")
    topics._daftarkan_campuran()
    return topics.PAKET["campuran"]


@pytest.fixture
def campuran_baru(monkeypatch):
    return _bangun_ulang_campuran(monkeypatch)


@pytest.fixture
def mutasi(monkeypatch):
    """Matikan atribut manual-saja lewat jalur nyata registri lalu bangun ulang Campuran."""
    asli = topics.ambil(TOPIK)
    monkeypatch.setitem(topics.PAKET, TOPIK, replace(asli, hanya_manual=False))
    _bangun_ulang_campuran(monkeypatch)


# ── pemeriksaan per situs (dipakai langsung dan di mutation) ─────────────

def situs_campuran():
    campuran = topics.ambil("campuran")
    assert not set(SEMUA) & set(campuran.templates), "Campuran memuat template manual-saja"
    for level in LEVEL:
        assert not set(SEMUA) & set(campuran.komposisi.get(level, ())), ("komposisi Campuran bocor", level)
        assert not set(SEMUA) & set(campuran.komposisi_untuk(level)), ("writer Campuran bocor", level)


def situs_siklus_lintas_topik():
    for level in LEVEL_TINGKAT:
        assert not set(SEMUA) & set(learning_sessions._template_lintas_topik(level, 400)), (
            "pemetaan/probe/pembanding siklus bocor", level)


def situs_ubah_fokus_ui():
    for level in LEVEL_TINGKAT:
        html_ubah = learning_cycle_ui._override(
            SimpleNamespace(tindakan="intervensi", putaran=SimpleNamespace(level=level)), 7)
        assert not any(f'value="{tid}"' in html_ubah for tid in SEMUA), (
            "pilihan ubah fokus bocor", level)


def situs_pemilih_pemetaan():
    """Kartu pemetaan hanya menghitung materi dan pola, jadi dibandingkan utuh dengan baseline."""
    html_pilih = question_variants_ui.pemilih_pemetaan("uji")
    assert TOPIK not in html_pilih and NAMA_TOPIK not in html_pilih, "pemilih pemetaan bocor"
    assert sidik(html_pilih) == SIDIK_BASELINE["pemilih_pemetaan_html"], "cakupan pemetaan bocor"


def situs_pendamping():
    katalog = assistant_catalog.buat_katalog(untuk_penawaran=True)
    assert not set(SEMUA) & {t.id for t in katalog.template}, "Pendamping menawarkan template"
    assert TOPIK not in {t.id for t in katalog.topik}, "Pendamping menawarkan topik"
    for tid in SEMUA:
        try:
            assistant_actions.validasi_usulan({
                "topik_id": TOPIK, "template_ids": [tid], "level": "P4", "jumlah_soal": 10})
        except assistant_actions.GalatTindakan:
            continue
        raise AssertionError("Pendamping menawarkan usulan manual-saja yang seharusnya ditolak")


def situs_katalog_mastery():
    """Grup audit ada di KELOMPOK (dibutuhkan skrip audit), tetapi target siklus tetap tertutup."""
    assert TOPIK in mastery_catalog.KELOMPOK, "grup audit bilangan-sekolah wajib ada"
    for level in LEVEL:
        for target in mastery_catalog.katalog_target(level):
            assert not set(SEMUA) & set(target.pola) and target.topik_id != TOPIK, ("mastery bocor", level)


def situs_fokus_rencana():
    for tid in SEMUA:
        rencana = SimpleNamespace(kandidat=((tid, "K", None),), putaran=None, tindakan="intervensi")
        try:
            learning_sessions._fokus_rencana(rencana)
        except ValueError as galat:
            assert "latihan manual" in str(galat), galat
            continue
        raise AssertionError("fokus siklus dengan template manual-saja seharusnya ditolak")


def situs_override_service(tmp_path):
    lokasi = tmp_path / "manual-saja-sintetis.db"
    database.siapkan(lokasi)
    with database.buka(lokasi) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", tingkat="P4", pemilik="guru")
        for tid in SEMUA:
            try:
                learning_cycle_service._ubah_fokus(kon, siswa, (tid, "K", None))
            except ValueError as galat:
                assert "latihan manual" in str(galat), galat
                continue
            raise AssertionError("override fokus ke template manual-saja seharusnya ditolak")


SITUS_TANPA_BERKAS = {
    "campuran": situs_campuran,
    "lintas_topik_siklus": situs_siklus_lintas_topik,
    "ubah_fokus_ui": situs_ubah_fokus_ui,
    "pemilih_pemetaan": situs_pemilih_pemetaan,
    "pendamping": situs_pendamping,
    "katalog_mastery": situs_katalog_mastery,
    "fokus_rencana": situs_fokus_rencana,
}


# ── kondisi sehat: tidak ada kebocoran ───────────────────────────────────

@pytest.mark.parametrize("nama", sorted(SITUS_TANPA_BERKAS))
def test_tidak_bocor_pada_situs(nama, campuran_baru):
    SITUS_TANPA_BERKAS[nama]()


def test_tidak_bocor_override_service(tmp_path):
    situs_override_service(tmp_path)


def test_hanya_topik_ini_yang_manual_saja_dan_atribut_default_salah():
    punya = {t for t in topics.daftar_topik() if topics.ambil(t).hanya_manual}
    assert punya == {TOPIK}
    assert topics.daftar_topik_siklus() == [
        t for t in topics.daftar_topik() if t not in ("campuran", TOPIK)]
    assert all(topics.template_hanya_manual(tid) is True for tid in SEMUA)
    assert topics.template_hanya_manual("tambah_dasar") is False
    assert topics.template_hanya_manual("tidak_ada") is False


def test_tidak_bocor_dengan_sakelar_mati_juga(monkeypatch, campuran_baru):
    monkeypatch.delenv("OSN_BILANGAN_SEKOLAH", raising=False)
    for nama, periksa in SITUS_TANPA_BERKAS.items():
        periksa()


# ── jalur guru tetap terbuka (butir c) ───────────────────────────────────

def test_guru_tetap_bisa_memilih_di_latihan_manual_dan_cetak():
    assert TOPIK in question_context.daftar_topik_latihan()
    question_context.pastikan_materi_dibuka([TOPIK])
    question_context.validasi_pilihan([TOPIK], "P4")
    assert question_context.profil_otomatis([TOPIK], "P6") == "P5"
    lembar = generator.buat_lembar(9, level="P4", topik=TOPIK)
    assert {s.template_id for s in lembar.soal} == set(SEMUA)
    paket = topics.gabungan([TOPIK, "pola-bilangan"])
    assert set(SEMUA) <= set(paket.templates) and set(SEMUA) <= set(paket.komposisi["P4"])
    # Pemilih isi Latihan manual (kartu variasi) mengenal topik ini.
    assert NAMA_TOPIK in question_variants_ui.pemilih_isi([TOPIK], "manual")


def test_pembaca_histori_dan_inventaris_tetap_mengenal():
    assert topics.dari_sesi(TOPIK).id == TOPIK
    for tid in SEMUA:
        assert topics.pemilik_template(tid) == TOPIK
        assert topics.paket_untuk_template([tid]).id == TOPIK
        assert tid in topics.registri()
        question_context.konteks_warisan(tid, "P4")
    konteks = {(k.template_id, k.profil_parameter) for k in question_context.daftar_konteks()}
    assert {(tid, lv) for tid in SEMUA for lv in ("P3", "P4", "P5")} <= konteks


def test_topik_manual_saja_tetap_menyaring_remedial_dasar_tidak_berubah():
    # Topik lain tidak terdampak atribut baru.
    for t in topics.daftar_topik():
        if t not in ("campuran", TOPIK):
            assert topics.ambil(t).hanya_manual is False, t


# ── mutation: atribut dimatikan -> setiap situs merah ────────────────────

# Pesan asersi tiap situs: merah harus karena KEBOCORAN, bukan galat lain.
PESAN_BOCOR = {
    "campuran": "Campuran memuat|Campuran bocor",
    "lintas_topik_siklus": "siklus bocor",
    "ubah_fokus_ui": "ubah fokus bocor",
    "pemilih_pemetaan": "pemetaan bocor",
    "pendamping": "Pendamping menawarkan",
    "katalog_mastery": "mastery bocor",
    "fokus_rencana": "seharusnya ditolak",
}


def test_pesan_bocor_lengkap():
    assert set(PESAN_BOCOR) == set(SITUS_TANPA_BERKAS)


@pytest.mark.parametrize("nama", sorted(SITUS_TANPA_BERKAS))
def test_mutation_atribut_dimatikan_membocorkan_situs(nama, mutasi):
    with pytest.raises(AssertionError, match=PESAN_BOCOR[nama]):
        SITUS_TANPA_BERKAS[nama]()


def test_mutation_atribut_dimatikan_membocorkan_override_service(mutasi, tmp_path):
    with pytest.raises(AssertionError, match="putaran aktif tidak ditemukan"):
        situs_override_service(tmp_path)


def test_mutation_dipulihkan_hijau_lagi(monkeypatch, tmp_path):
    asli = topics.ambil(TOPIK)
    with monkeypatch.context() as m:
        m.setitem(topics.PAKET, TOPIK, replace(asli, hanya_manual=False))
        m.delitem(topics.PAKET, "campuran")
        topics._daftarkan_campuran()
        with pytest.raises(AssertionError, match="Campuran"):
            situs_campuran()
    # keluar dari konteks: entri asli dan Campuran asli kembali
    assert topics.ambil(TOPIK) is asli
    for periksa in SITUS_TANPA_BERKAS.values():
        periksa()
    situs_override_service(tmp_path)
