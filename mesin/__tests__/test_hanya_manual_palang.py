"""Palang MANUAL-SAJA (pedagogis-kritis): bilangan-sekolah tidak boleh bocor ke siklus.

Topik P3–P5 yang mengikuti pola biasa otomatis masuk Campuran, siklus terpandu,
pemetaan, dan Pendamping. Soal bilangan besar belum punya grup mastery, kartu
intervensi, dan playbook, jadi `Topik.hanya_manual=True` menutup SEMUA jalur
itu, baik sakelar mati maupun hidup. Guru tetap bisa memilihnya di Latihan
manual dan lembar cetak; pembaca histori tetap mengenal ID.

Mutation (wajib): tiap situs diuji MERAH saat atribut dimatikan lewat jalur
yang dipanggil tes (entri PAKET diganti `replace(hanya_manual=False)` dan
Campuran dibangun ulang), lalu hijau setelah monkeypatch memulihkan.

Topik manual-saja kedua, `matematika-awal` (P1/P2, 21 Nov 2026), diuji dengan situs
yang sama (parametrisasi per topik). Sebagian situs hanya melihat P3–P6 (Campuran,
pemilih pemetaan, katalog mastery, siklus lintas topik), jadi untuk topik P1/P2 ia
HAMPA saat ini dan tidak dihitung sebagai bukti gigitan; situs yang menggigit pada
level mana pun ada di `SITUS_MENGGIGIT_P1_P2`. Begitu jenis P3+ ditambahkan, situs
hampa itu mulai menggigit tanpa perubahan tes.
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

TOPIK_AWAL = "matematika-awal"
SEMUA_AWAL = ("kenali_bentuk",)  # tambahkan tiap jenis baru topik ini di sini
NAMA_AWAL = "Matematika Awal"
# topik -> (template milik topik, nama tampil, level uji usulan Pendamping, level warisan)
DATA_TOPIK = {
    TOPIK: (SEMUA, NAMA_TOPIK, "P4", ("P3", "P4", "P5")),
    TOPIK_AWAL: (SEMUA_AWAL, NAMA_AWAL, "P2", ("P1", "P2")),
}
SEMUA_TOPIK_MANUAL = tuple(DATA_TOPIK)
# Topik yang grup auditnya WAJIB ada di `mastery_catalog.KELOMPOK`. `matematika-awal` belum:
# KELOMPOK dibaca dari `kurikulum_katalog.KATALOG` (integrasi tahap 4, di luar tahap 2);
# tambahkan topik itu ke himpunan ini begitu entrinya masuk KATALOG.
GRUP_AUDIT_WAJIB = frozenset({TOPIK, TOPIK_AWAL})
# Gabungan template manual-saja dari semua topik: tak satu pun boleh bocor ke jalur otomatis.
SEMUA_GABUNGAN = SEMUA + SEMUA_AWAL


@pytest.fixture(autouse=True)
def sakelar_hidup(monkeypatch):
    """Kasus terkuat: sakelar HIDUP, topik terbuka, palang manual-saja yang menahan.

    OSN_MATERI_DASAR=1 juga dipasang: topik P1/P2 selain digerbang sakelarnya
    disembunyikan gerbang dasar bila 0, dan itu bukan palang yang diuji di sini.
    """
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    monkeypatch.setenv("OSN_MATEMATIKA_AWAL", "1")
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")


def _bangun_ulang_campuran(monkeypatch):
    """Campuran dibangun sekali dan di-cache; mutasi harus membangunnya ulang."""
    monkeypatch.delitem(topics.PAKET, "campuran")
    topics._daftarkan_campuran()
    return topics.PAKET["campuran"]


@pytest.fixture
def campuran_baru(monkeypatch):
    return _bangun_ulang_campuran(monkeypatch)


@pytest.fixture(params=SEMUA_TOPIK_MANUAL)
def topik(request):
    """Tiap tes situs berjalan untuk setiap topik manual-saja."""
    return request.param


@pytest.fixture
def mutasi(monkeypatch, topik):
    """Matikan atribut manual-saja lewat jalur nyata registri lalu bangun ulang Campuran."""
    asli = topics.ambil(topik)
    monkeypatch.setitem(topics.PAKET, topik, replace(asli, hanya_manual=False))
    _bangun_ulang_campuran(monkeypatch)


def _semua(topik):
    return DATA_TOPIK[topik][0]


def _nama(topik):
    return DATA_TOPIK[topik][1]


# ── pemeriksaan per situs (dipakai langsung dan di mutation) ─────────────

def situs_campuran(topik):
    semua = _semua(topik)
    campuran = topics.ambil("campuran")
    assert not set(semua) & set(campuran.templates), "Campuran memuat template manual-saja"
    for level in LEVEL:
        assert not set(semua) & set(campuran.komposisi.get(level, ())), ("komposisi Campuran bocor", level)
        assert not set(semua) & set(campuran.komposisi_untuk(level)), ("writer Campuran bocor", level)


def situs_siklus_lintas_topik(topik):
    for level in LEVEL_TINGKAT:
        assert not set(_semua(topik)) & set(learning_sessions._template_lintas_topik(level, 400)), (
            "pemetaan/probe/pembanding siklus bocor", level)


def situs_ubah_fokus_ui(topik):
    for level in LEVEL_TINGKAT:
        html_ubah = learning_cycle_ui._override(
            SimpleNamespace(tindakan="intervensi", putaran=SimpleNamespace(level=level)), 7)
        assert not any(f'value="{tid}"' in html_ubah for tid in _semua(topik)), (
            "pilihan ubah fokus bocor", level)


def situs_pemilih_pemetaan(topik):
    """Kartu pemetaan hanya menghitung materi dan pola, jadi dibandingkan utuh dengan baseline."""
    html_pilih = question_variants_ui.pemilih_pemetaan("uji")
    assert topik not in html_pilih and _nama(topik) not in html_pilih, "pemilih pemetaan bocor"
    assert sidik(html_pilih) == SIDIK_BASELINE["pemilih_pemetaan_html"], "cakupan pemetaan bocor"


def situs_pendamping(topik):
    semua, level = _semua(topik), DATA_TOPIK[topik][2]
    katalog = assistant_catalog.buat_katalog(untuk_penawaran=True)
    assert not set(semua) & {t.id for t in katalog.template}, "Pendamping menawarkan template"
    assert topik not in {t.id for t in katalog.topik}, "Pendamping menawarkan topik"
    for tid in semua:
        try:
            assistant_actions.validasi_usulan({
                "topik_id": topik, "template_ids": [tid], "level": level, "jumlah_soal": 10})
        except assistant_actions.GalatTindakan:
            continue
        raise AssertionError("Pendamping menawarkan usulan manual-saja yang seharusnya ditolak")


def situs_katalog_mastery(topik):
    """Grup audit ada di KELOMPOK (dibutuhkan skrip audit), tetapi target siklus tetap tertutup."""
    if topik in GRUP_AUDIT_WAJIB:
        assert topik in mastery_catalog.KELOMPOK, f"grup audit {topik} wajib ada"
    if topik in mastery_catalog.KELOMPOK:  # KELOMPOK datang dari kurikulum_katalog.KATALOG
        grup = {pola for _, _, pola_grup in mastery_catalog.KELOMPOK[topik] for pola in pola_grup}
        assert set(_semua(topik)) <= grup, "grup audit tidak mencakup semua jenis topik"
    for level in LEVEL:
        for target in mastery_catalog.katalog_target(level):
            assert not set(_semua(topik)) & set(target.pola) and target.topik_id != topik, (
                "mastery bocor", level)


def situs_fokus_rencana(topik):
    for tid in _semua(topik):
        rencana = SimpleNamespace(kandidat=((tid, "K", None),), putaran=None, tindakan="intervensi")
        try:
            learning_sessions._fokus_rencana(rencana)
        except ValueError as galat:
            assert "latihan manual" in str(galat), galat
            continue
        raise AssertionError("fokus siklus dengan template manual-saja seharusnya ditolak")


def situs_override_service(tmp_path, topik):
    lokasi = tmp_path / "manual-saja-sintetis.db"
    database.siapkan(lokasi)
    with database.buka(lokasi) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", tingkat="P4", pemilik="guru")
        for tid in _semua(topik):
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
# Situs yang menggigit untuk topik yang hanya punya level P1/P2 (di luar LEVEL_TINGKAT).
SITUS_MENGGIGIT_P1_P2 = frozenset({"fokus_rencana", "pendamping"})


# ── kondisi sehat: tidak ada kebocoran ───────────────────────────────────

@pytest.mark.parametrize("nama", sorted(SITUS_TANPA_BERKAS))
def test_tidak_bocor_pada_situs(nama, topik, campuran_baru):
    SITUS_TANPA_BERKAS[nama](topik)


def test_tidak_bocor_override_service(tmp_path, topik):
    situs_override_service(tmp_path, topik)


def test_hanya_topik_ini_yang_manual_saja_dan_atribut_default_salah():
    punya = {t for t in topics.daftar_topik() if topics.ambil(t).hanya_manual}
    assert punya == set(SEMUA_TOPIK_MANUAL)
    assert topics.daftar_topik_siklus() == [
        t for t in topics.daftar_topik() if t not in ("campuran", *SEMUA_TOPIK_MANUAL)]
    assert all(topics.template_hanya_manual(tid) is True for tid in SEMUA_GABUNGAN)
    assert set(topics.ambil(TOPIK).templates) == set(SEMUA)
    assert set(topics.ambil(TOPIK_AWAL).templates) == set(SEMUA_AWAL)
    assert topics.template_hanya_manual("tambah_dasar") is False
    assert topics.template_hanya_manual("tidak_ada") is False


def test_tidak_bocor_dengan_sakelar_mati_juga(monkeypatch, topik, campuran_baru):
    monkeypatch.delenv("OSN_BILANGAN_SEKOLAH", raising=False)
    monkeypatch.setenv("OSN_MATEMATIKA_AWAL", "0")
    for nama, periksa in SITUS_TANPA_BERKAS.items():
        periksa(topik)


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


def test_guru_tetap_bisa_memilih_matematika_awal_di_latihan_manual_dan_cetak():
    assert TOPIK_AWAL in question_context.daftar_topik_latihan()
    question_context.pastikan_materi_dibuka([TOPIK_AWAL])
    question_context.validasi_pilihan([TOPIK_AWAL], "P2")
    assert question_context.profil_otomatis([TOPIK_AWAL], "P6") == "P2"
    assert question_context.profil_otomatis([TOPIK_AWAL], "P3") == "P2"
    for level in ("P1", "P2"):
        lembar = generator.buat_lembar(9, level=level, topik=TOPIK_AWAL)
        assert {s.template_id for s in lembar.soal} == set(SEMUA_AWAL)
    paket = topics.gabungan([TOPIK_AWAL, "bilangan-dasar"])
    assert set(SEMUA_AWAL) <= set(paket.templates) and set(SEMUA_AWAL) <= set(paket.komposisi["P1"])
    assert NAMA_AWAL in question_variants_ui.pemilih_isi([TOPIK_AWAL], "manual")


@pytest.mark.parametrize("topik_manual", SEMUA_TOPIK_MANUAL)
def test_pembaca_histori_dan_inventaris_tetap_mengenal(topik_manual):
    semua, _, _, level_warisan = DATA_TOPIK[topik_manual]
    assert topics.dari_sesi(topik_manual).id == topik_manual
    for tid in semua:
        assert topics.pemilik_template(tid) == topik_manual
        assert topics.paket_untuk_template([tid]).id == topik_manual
        assert tid in topics.registri()
        question_context.konteks_warisan(tid, level_warisan[0])
    konteks = {(k.template_id, k.profil_parameter) for k in question_context.daftar_konteks()}
    assert {(tid, lv) for tid in semua for lv in level_warisan} <= konteks


def test_topik_manual_saja_tetap_menyaring_remedial_dasar_tidak_berubah():
    # Topik lain tidak terdampak atribut baru.
    for t in topics.daftar_topik():
        if t not in ("campuran", *SEMUA_TOPIK_MANUAL):
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
    assert SITUS_MENGGIGIT_P1_P2 <= set(SITUS_TANPA_BERKAS)


def _menggigit(nama, topik):
    """Bagi topik P3+ semua situs menggigit; topik P1/P2 hanya yang bukan hampa."""
    return topik != TOPIK_AWAL or nama in SITUS_MENGGIGIT_P1_P2


@pytest.mark.parametrize("nama", sorted(SITUS_TANPA_BERKAS))
def test_mutation_atribut_dimatikan_membocorkan_situs(nama, topik, mutasi):
    if not _menggigit(nama, topik):
        # Situs hampa untuk topik ini: hanya buktikan ia tidak menolak diam-diam secara salah.
        SITUS_TANPA_BERKAS[nama](topik)
        pytest.skip("situs hanya memeriksa P3-P6; hampa untuk topik P1/P2 (lihat docstring)")
    with pytest.raises(AssertionError, match=PESAN_BOCOR[nama]):
        SITUS_TANPA_BERKAS[nama](topik)


def test_mutation_atribut_dimatikan_membocorkan_override_service(mutasi, topik, tmp_path):
    with pytest.raises(AssertionError, match="putaran aktif tidak ditemukan"):
        situs_override_service(tmp_path, topik)


@pytest.mark.parametrize("topik_manual", SEMUA_TOPIK_MANUAL)
def test_mutation_dipulihkan_hijau_lagi(monkeypatch, tmp_path, topik_manual):
    asli = topics.ambil(topik_manual)
    with monkeypatch.context() as m:
        m.setitem(topics.PAKET, topik_manual, replace(asli, hanya_manual=False))
        m.delitem(topics.PAKET, "campuran")
        topics._daftarkan_campuran()
        with pytest.raises(AssertionError, match="seharusnya ditolak"):
            situs_fokus_rencana(topik_manual)
        if topik_manual == TOPIK:  # topik P3+: Campuran juga ikut bocor
            with pytest.raises(AssertionError, match="Campuran"):
                situs_campuran(topik_manual)
    # keluar dari konteks: entri asli dan Campuran asli kembali
    assert topics.ambil(topik_manual) is asli
    for periksa in SITUS_TANPA_BERKAS.values():
        periksa(topik_manual)
    situs_override_service(tmp_path, topik_manual)
