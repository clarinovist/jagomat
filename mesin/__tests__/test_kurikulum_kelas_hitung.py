"""Hitungan per kelas (`kurikulum_kelas_hitung`) dan pembuat contoh soal (`kurikulum_buat_soal`). Tanpa DB/HTTP."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurikulum_buat_soal as buat  # noqa: E402
import kurikulum_kelas as kk  # noqa: E402
import kurikulum_kelas_hitung as hitung  # noqa: E402


@pytest.fixture(autouse=True)
def _sakelar_mati(monkeypatch):
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "0")
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "0")
    monkeypatch.delenv("OSN_MATEMATIKA_AWAL", raising=False)  # bawaan 1 (menyala)


def _bab(kelas: int, nomor: int) -> kk.Bab:
    return hitung.cari_bab(kelas, nomor)[1]


def _ringkas(kelas: int, nomor: int) -> hitung.RingkasanBab:
    return hitung.ringkasan_bab(_bab(kelas, nomor), kelas, {})


# Bab sintetis: data nyata tidak lagi punya bab "belum" sejak topik matematika-awal mengisi 11 bab
# (21 Nov 2026), jadi kasus "belum" diuji dengan bab buatan, bukan dengan bab kurikulum yang bisa terisi.
BAB_TANPA_PELATIH = kk.Bab(1, "Uji tanpa pelatih", ("x",), ())
BAB_GRUP_KELAS_LAIN = kk.Bab(2, "Uji grup kelas lain", ("x",), (("pola-bilangan", "siklus", "sebagian"),))


def test_status_mengikuti_level_kelas_bukan_data_mentah():
    assert hitung.ringkasan_bab(BAB_TANPA_PELATIH, 1, {}).status == hitung.STATUS_BELUM
    assert _ringkas(1, 2).status == hitung.STATUS_ADA
    assert _ringkas(1, 6).status == hitung.STATUS_ADA  # naik lewat tambah_kurang_20
    assert _ringkas(1, 7).status == hitung.STATUS_ADA  # naik lewat ukur_satuan_tak_baku bergambar (adegan_awal)
    assert _ringkas(1, 4).status == hitung.STATUS_SEBAGIAN  # kenali_bentuk belum bergambar
    # Bab menunjuk grup yang baru ada di kelas 3+: tidak dihitung tersedia di kelas 2.
    r = hitung.ringkasan_bab(BAB_GRUP_KELAS_LAIN, 2, {})
    assert r.status == hitung.STATUS_BELUM and not r.pelatih[0].tersedia and r.pelatih[0].kelas_lain[0] == 3
    # Bab nyata yang dulu "belum": grup matematika-awal tersedia di levelnya sendiri. K2 B4 "ada" lewat
    # pola_posisi (soal teks menutup sub-materi; keputusan pemilik 21 Nov 2026) walau pelatih lama
    # pola-bilangan/siklus tetap tak tersedia di kelas 2; K2 B6 tetap sebagian (waktu_berat_awal "sebagian").
    r24 = _ringkas(2, 4)
    assert r24.status == hitung.STATUS_ADA
    assert [p.tersedia for p in r24.pelatih] == [False, True]
    assert _ringkas(2, 6).status == hitung.STATUS_SEBAGIAN
    assert _ringkas(1, 4).status == hitung.STATUS_SEBAGIAN


def test_tidak_ada_bab_belum_ada_soal_di_data_nyata():
    status = [hitung.ringkasan_bab(b, k.kelas, {}).status for k in kk.KELAS for b in k.bab]
    assert hitung.STATUS_BELUM not in status


def test_jenis_soal_adalah_template_unik_di_level_kelas():
    assert _ringkas(1, 2).jenis == 2 and hitung.ringkasan_bab(BAB_TANPA_PELATIH, 1, {}).jenis == 0
    assert _ringkas(1, 4).jenis == 1  # kenali_bentuk
    ref = _ringkas(5, 6).template
    assert len(ref) == len(set(ref))


def test_variasi_domain_tepat_dan_palang_rilis_dibaca_tiap_panggilan(monkeypatch):
    mati = _ringkas(1, 2).variasi
    assert (mati.total, mati.jenis, mati.tertutup) == (45, hitung.JENIS_TEPAT, ("bilangan_hilang",))
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    nyala = _ringkas(1, 2).variasi
    assert (nyala.total, nyala.tertutup) == (45 + 180, ())  # cache murni tidak menyimpan keadaan palang


def test_variasi_sampel_banyak_bila_semua_unik_dan_perkiraan_bila_tidak():
    assert _ringkas(5, 1).variasi.jenis == hitung.JENIS_BANYAK
    kira = hitung.variasi_bab((("pola-bilangan", "titik_segitiga"),), "P4")
    assert kira.jenis == hitung.JENIS_PERKIRAAN and 0 < kira.total < hitung.JUMLAH_SAMPEL


def test_template_tanpa_enumerator_jatuh_ke_sampel_bukan_galat(monkeypatch):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    v = hitung.variasi_bab((("bilangan-sekolah", "nilai_tempat_besar"),), "P3")
    assert v.galat == () and v.total > 0


def test_ringkasan_pemakaian_menjumlah_template_dan_level_yang_tepat():
    pemakaian = {("tambah_dasar", "P1"): 3, ("bilangan_hilang", "P1"): 4, ("tambah_dasar", "P2"): 9}
    assert hitung.ringkasan_bab(_bab(1, 2), 1, pemakaian).terpakai == 7
    assert hitung.ringkasan_bab(_bab(1, 2), 1, None).terpakai is None


def test_grup_pengayaan_tidak_memuat_grup_yang_dipakai_bab():
    terpakai = kk.grup_terpakai()
    jumlah = sum(len(n) for _t, n in hitung.grup_pengayaan())
    total = sum(len(e.grup) for e in hitung.kat.KATALOG)
    assert jumlah == total - len(terpakai)


# --- pembuat soal --------------------------------------------------------------------------

def test_buat_soal_level_template_dan_tanda_tangan_sah():
    bab = _bab(5, 1)
    hasil = buat.buat_soal_bab(5, bab, 20, 5)
    boleh = {tid for _t, tid in hitung.ringkasan_bab(bab, 5, {}).template if hitung.template_dibuka(tid)}
    assert len(hasil.item) == 20
    assert {i.soal.template_id for i in hasil.item} == boleh  # dibagi bergiliran antar template
    assert all(i.soal.level == "P5" for i in hasil.item)
    tanda = [i.soal.tanda_tangan for i in hasil.item]
    assert len(tanda) == len(set(tanda))
    assert [i.nomor for i in hasil.item] == list(range(1, 21))


def test_buat_soal_deterministik_per_seed():
    def sidik(seed):
        return [i.soal.tanda_tangan for i in buat.buat_soal_bab(4, _bab(4, 3), 10, seed).item]

    assert sidik(8) == sidik(8) and sidik(8) != sidik(9)


def test_buat_soal_domain_kecil_berhenti_tanpa_kembar():
    bab = kk.Bab(1, "Uji", ("x",), (("pola-bilangan", "titik", "ada"),))
    hasil = buat.buat_soal_bab(4, bab, 30, 1)
    tanda = [i.soal.tanda_tangan for i in hasil.item]
    assert 0 < len(tanda) < 30 and len(tanda) == len(set(tanda))


def test_buat_soal_domain_enumerasi_tanpa_ulang_sampai_habis(monkeypatch):
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    bab = kk.Bab(1, "Uji", ("x",), (("bilangan-dasar", "nilai_tempat", "ada"),))
    hasil = buat.buat_soal_bab(1, bab, 30, 3)  # domain nilai_tempat P1 = 20
    assert len(hasil.item) == 20 and len({i.soal.tanda_tangan for i in hasil.item}) == 20


def test_buat_soal_template_tertutup_dikeluarkan_dan_dilaporkan():
    hasil = buat.buat_soal_bab(1, _bab(1, 2), 10, 2)
    assert {i.soal.template_id for i in hasil.item} == {"tambah_dasar"}
    assert hasil.template_tertutup == ("bilangan_hilang",)
    # Bab sintetis dengan satu pelatih yang tertutup: tidak bisa dibuat walau ada pelatih.
    bab_tertutup = kk.Bab(1, "Uji tertutup", ("x",), (("bilangan-dasar", "membandingkan", "sebagian"),))
    tertutup_semua = buat.buat_soal_bab(1, bab_tertutup, 10, 2)
    assert not tertutup_semua.bisa_dibuat and tertutup_semua.ada_pelatih
    # K1 B1 kini punya jenis matematika-awal yang terbuka (sakelar bawaan 1): bisa dibuat, jenis lama dikeluarkan.
    k1b1 = buat.buat_soal_bab(1, _bab(1, 1), 10, 2)
    assert k1b1.bisa_dibuat and {i.soal.template_id for i in k1b1.item} == {"bilang_benda_awal"}


def test_buat_soal_bab_tanpa_pelatih():
    hasil = buat.buat_soal_bab(1, BAB_TANPA_PELATIH, 10, 2)
    assert not hasil.bisa_dibuat and not hasil.ada_pelatih
