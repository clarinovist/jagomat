"""Cache sidik jari domain dan jalur unik_per_lembar: ekuivalen dengan versi lama.

Invariant yang dijaga: seed -> lembar harus identik dengan enumerasi penuh tanpa
cache (versi HEAD), dan konsumsi RNG harus sama, karena seed disimpan di DB dan
lembar dirakit ulang. `_referensi_unik_per_lembar` adalah salinan
`_soal_unik_per_lembar` dari HEAD. `generator._soal_layak` dipinjam dari produksi
karena tidak berubah terhadap HEAD (git diff tidak menyentuh fungsi itu).

Semua data sintetis; registri topik global tidak diubah.
"""

from __future__ import annotations

import random
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generator  # noqa: E402
import kurikulum_kelas_hitung as hitung  # noqa: E402
import topics  # noqa: E402
from generator_domain import bersihkan_cache_domain, domain_sidik  # noqa: E402
from templates import Malrule, Soal  # noqa: E402
from topics import Topik  # noqa: E402

BATAS_UNDI_REFERENSI = 40  # konstanta `_BATAS_UNDI_UNIK` di HEAD
SEED_UJI = (1, 42)
TEMPLATE_SINTETIS = "domain_sintetis"
LEVEL_SINTETIS = "P3"
DOMAIN_SINTETIS = ({"a": 1}, {"a": 2}, {"a": 3}, {"a": 4})
BATAS_SLOT_UJI = 60  # batas panjang urutan stres pada topik sungguhan (jaga durasi)
UKURAN_DOMAIN_KECIL = 60  # domain kecil: undian duplikat sering terjadi, fallback nyata terpicu


@pytest.fixture(autouse=True)
def cache_domain_bersih():
    """Setiap test mulai dan selesai dengan cache domain kosong."""
    bersihkan_cache_domain()
    yield
    bersihkan_cache_domain()


# ── Referensi: salinan HEAD tanpa cache ─────────────────────────────────


def _referensi_unik_per_lembar(paket, urutan, rng, level, batas=BATAS_UNDI_REFERENSI):
    """Salinan `_soal_unik_per_lembar` dari HEAD: enumerasi penuh, tanpa cache."""
    if paket.domain_parameter is None:
        raise ValueError("topik unik_per_lembar memerlukan enumerator domain")
    domain_per_template = {}
    dipakai_per_template = {}
    hasil = []
    for tid in urutan:
        if tid not in domain_per_template:
            parameter = paket.domain_parameter(tid, level)
            if not parameter:
                raise ValueError(f"{tid}: domain parameter kosong")
            calon = (replace(paket.templates[tid](**p), level=level) for p in parameter)
            domain = {s.tanda_tangan: s for s in calon if s.malrule}
            if not domain:
                raise RuntimeError(f"{tid}: domain tanpa malrule yang sah")
            domain_per_template[tid] = domain
            dipakai_per_template[tid] = set()
        domain = domain_per_template[tid]
        dipakai = dipakai_per_template[tid]
        habis = len(dipakai) == len(domain)
        for _ in range(batas):
            soal = generator._soal_layak(paket, tid, rng, level)
            if soal.tanda_tangan not in domain:
                raise ValueError(f"{tid}: sampler keluar domain")
            if habis or soal.tanda_tangan not in dipakai:
                break
        else:
            sisa = tuple(s for tanda, s in domain.items() if tanda not in dipakai)
            soal = rng.choice(sisa)
        dipakai.add(soal.tanda_tangan)
        hasil.append(soal)
    return tuple(hasil)


def _urutan_seperti_buat_lembar(paket, level, seed):
    """Urutan dan RNG persis seperti `buat_lembar`: komposisi diacak dengan seed itu."""
    rng = random.Random(seed)
    urutan = generator._acak_urutan(paket.komposisi[level], rng)
    return urutan, rng


def _rakit(fungsi, paket, level, seed):
    """Jalankan `fungsi` pada urutan realistis; kembalikan hasil dan state RNG sesudahnya."""
    urutan, rng = _urutan_seperti_buat_lembar(paket, level, seed)
    hasil = fungsi(paket, urutan, rng, level)
    return hasil, rng.getstate()


# ── Paket sintetis kecil (tidak didaftarkan) ────────────────────────────


def _templat_sintetis(**parameter):
    """Soal sintetis: tanda ditentukan parameter; ada malrule kecuali `malrule` False."""
    malrule = (Malrule(id="salah", jawaban="0", kode="K1", alasan="uji"),) if parameter.get("malrule", True) else ()
    return Soal(template_id=TEMPLATE_SINTETIS, parameter=dict(parameter), teks="uji", kunci="1", malrule=malrule)


def _templat_kelas_saja(**parameter):
    """Varian `varian` dibuang dari parameter: dua parameter berbeda, tanda sama."""
    malrule = (Malrule(id="salah", jawaban="0", kode="K1", alasan="uji"),) if parameter["malrule"] else ()
    return Soal(template_id=TEMPLATE_SINTETIS, parameter={"kelas": parameter["kelas"]},
                teks="uji", kunci="1", malrule=malrule)


class _SamplerTetap:
    """Sampler yang selalu mengembalikan parameter sama: undian pasti terus duplikat."""

    def __init__(self, parameter):
        self._parameter = parameter
        self.jumlah_panggilan = 0

    def __call__(self, template_id, rng, level):
        self.jumlah_panggilan += 1
        return dict(self._parameter)


def _topik_sintetis(domain, sampler, templat=_templat_sintetis):
    """Paket unik_per_lembar kecil; sengaja TIDAK didaftarkan ke registri global."""
    return Topik(
        id="uji-domain-sintetis",
        nama="Uji Domain Sintetis",
        judul_lembar="Uji",
        judul_penilaian="Uji",
        templates={TEMPLATE_SINTETIS: templat},
        komposisi={LEVEL_SINTETIS: (TEMPLATE_SINTETIS,)},
        parameter_untuk=sampler,
        unik_per_lembar=True,
        domain_parameter=lambda template_id, level: tuple(dict(p) for p in domain),
    )


# ── 1. Ekuivalen dengan referensi pada topik unik sungguhan ─────────────

_TOPIK_UNIK = [tid for tid in topics.daftar_topik() if topics.ambil(tid).unik_per_lembar]
_KASUS_EKUIVALEN = [
    (tid, level, seed)
    for tid in _TOPIK_UNIK
    for level in sorted(topics.ambil(tid).komposisi)
    for seed in SEED_UJI
]


def test_daftar_topik_unik_per_lembar_memuat_bilangan_dasar_dan_matematika_awal():
    # Arrange / Act: daftar diambil dari registri saat modul dimuat
    # Assert: tanpa dua topik ini parametrisasi di bawah kosong diam-diam
    assert {"bilangan-dasar", "matematika-awal"} <= set(_TOPIK_UNIK)


@pytest.mark.parametrize("topik_id, level, seed", _KASUS_EKUIVALEN,
                         ids=[f"{t}-{lv}-seed{s}" for t, lv, s in _KASUS_EKUIVALEN])
def test_lembar_dan_state_rng_sama_dengan_referensi_tanpa_cache(topik_id, level, seed):
    # Arrange
    paket = topics.ambil(topik_id)
    hasil_referensi, state_referensi = _rakit(_referensi_unik_per_lembar, paket, level, seed)

    # Act
    hasil_cache_dingin, state_dingin = _rakit(generator._soal_unik_per_lembar, paket, level, seed)
    hasil_cache_hangat, state_hangat = _rakit(generator._soal_unik_per_lembar, paket, level, seed)

    # Assert: cache dingin dan hangat sama-sama identik dengan referensi
    for hasil, state in ((hasil_cache_dingin, state_dingin), (hasil_cache_hangat, state_hangat)):
        assert hasil == hasil_referensi
        assert [s.penyajian for s in hasil] == [s.penyajian for s in hasil_referensi]
        assert state == state_referensi


@pytest.mark.parametrize("topik_id", _TOPIK_UNIK)
def test_satu_template_melewati_domain_di_topik_sungguhan_sama_dengan_referensi(topik_id):
    # Arrange: urutan komposisi asli jarang kembar, jadi satu template diulang melewati
    # ukuran domainnya (ditambah sedikit, dibatasi) agar undian ulang, habis, dan fallback
    # nyata terjadi pada domain asli (bukan hanya pada paket sintetis).
    paket = topics.ambil(topik_id)
    level = sorted(paket.komposisi)[0]
    tid = paket.komposisi[level][0]
    jumlah_slot = min(len(paket.domain_parameter(tid, level)) + 3, BATAS_SLOT_UJI)
    urutan = (tid,) * jumlah_slot
    rng_baru = random.Random(SEED_UJI[1])
    rng_referensi = random.Random(SEED_UJI[1])

    # Act
    hasil_baru = generator._soal_unik_per_lembar(paket, urutan, rng_baru, level)
    hasil_referensi = _referensi_unik_per_lembar(paket, urutan, rng_referensi, level)

    # Assert
    assert hasil_baru == hasil_referensi
    assert rng_baru.getstate() == rng_referensi.getstate()


class _RngHitung(random.Random):
    """Random biasa yang menghitung pemanggilan `choice` (= jalur cadangan terpakai)."""

    def __init__(self, seed):
        super().__init__(seed)
        self.dipanggil = 0

    def choice(self, seq):
        self.dipanggil += 1
        return super().choice(seq)


def _template_domain_kecil():
    """(paket, level, template_id, ukuran) domain nyata kecil pertama: fallback gampang terpicu."""
    for topik_id in _TOPIK_UNIK:
        paket = topics.ambil(topik_id)
        for level in sorted(paket.komposisi):
            for tid in sorted(set(paket.komposisi[level])):
                ukuran = len(paket.domain_parameter(tid, level))
                if 5 <= ukuran <= UKURAN_DOMAIN_KECIL:
                    return paket, level, tid, ukuran
    raise AssertionError("tak ada template domain kecil di topik unik")


def test_jalur_cadangan_pada_domain_nyata_dengan_batas_undi_kecil_sama_dengan_referensi(monkeypatch):
    # Arrange: batas undian 1 dan 3 membuat fallback sering terjadi pada domain nyata yang kecil;
    # pada batas 40 fallback nyaris tak pernah terpicu sehingga tak terjaga oleh tes lain.
    dibandingkan = 0
    total_fallback = 0

    # Act + Assert per kombinasi
    for topik_id in _TOPIK_UNIK:
        paket = topics.ambil(topik_id)
        for level in sorted(paket.komposisi):
            for tid in sorted(set(paket.komposisi[level])):
                ukuran = len(paket.domain_parameter(tid, level))
                if ukuran > UKURAN_DOMAIN_KECIL:
                    continue
                urutan = (tid,) * min(ukuran + 3, BATAS_SLOT_UJI)
                for batas in (1, 3):
                    monkeypatch.setattr(generator, "_BATAS_UNDI_UNIK", batas)
                    rng_baru = _RngHitung(5)
                    rng_referensi = random.Random(5)
                    hasil_baru = generator._soal_unik_per_lembar(paket, urutan, rng_baru, level)
                    hasil_referensi = _referensi_unik_per_lembar(paket, urutan, rng_referensi, level, batas)
                    assert hasil_baru == hasil_referensi, (topik_id, level, tid, batas)
                    assert rng_baru.getstate() == rng_referensi.getstate(), (topik_id, level, tid, batas)
                    dibandingkan += 1
                    total_fallback += rng_baru.dipanggil

    # Assert agregat: jalur cadangan benar-benar terpakai, bukan lulus kosong
    assert dibandingkan >= 10
    assert total_fallback >= 10


# ── 2. Jalur cadangan (fallback setelah 40 undian duplikat) ─────────────


def test_jalur_cadangan_dipakai_saat_sampler_terus_mengulang_dan_hasil_sama_referensi():
    # Arrange: tiga slot template sama; sampler selalu {"a": 1} sehingga slot kedua dan ketiga
    # tidak pernah lolos undian dan harus jatuh ke fallback rng.choice(sisa).
    urutan = (TEMPLATE_SINTETIS,) * 3
    sampler_baru = _SamplerTetap({"a": 1})
    sampler_referensi = _SamplerTetap({"a": 1})
    paket_baru = _topik_sintetis(DOMAIN_SINTETIS, sampler_baru)
    paket_referensi = _topik_sintetis(DOMAIN_SINTETIS, sampler_referensi)
    rng_baru = random.Random(7)
    rng_referensi = random.Random(7)

    # Act
    hasil_baru = generator._soal_unik_per_lembar(paket_baru, urutan, rng_baru, LEVEL_SINTETIS)
    hasil_referensi = _referensi_unik_per_lembar(paket_referensi, urutan, rng_referensi, LEVEL_SINTETIS)

    # Assert
    assert sampler_baru.jumlah_panggilan > BATAS_UNDI_REFERENSI
    assert hasil_baru == hasil_referensi
    assert rng_baru.getstate() == rng_referensi.getstate()
    assert len({s.tanda_tangan for s in hasil_baru}) == len(urutan)


def _templat_teks_dari_nilai(**parameter):
    """Teks memuat repr nilai: 1 dan "1" punya sidik jari sama (f-string) tapi render beda."""
    malrule = (Malrule(id="salah", jawaban="0", kode="K1", alasan="uji"),)
    return Soal(template_id=TEMPLATE_SINTETIS, parameter=dict(parameter),
                teks=repr(parameter["a"]), kunci="1", malrule=malrule)


def test_jalur_cadangan_dengan_sidik_kembar_memakai_parameter_terakhir_seperti_dict_lama():
    # Arrange: {"a": 1} dan {"a": "1"} berbagi sidik jari "a=1"; sampler selalu {"a": 2}, jadi slot
    # kedua jatuh ke fallback dan satu-satunya sisa adalah sidik kembar itu. Dict lama menyimpan
    # Soal dari parameter TERAKHIR ({"a": "1"}); indeks yang salah akan merender {"a": 1}.
    domain = ({"a": 1}, {"a": "1"}, {"a": 2})
    urutan = (TEMPLATE_SINTETIS,) * 2
    paket_baru = _topik_sintetis(domain, _SamplerTetap({"a": 2}), _templat_teks_dari_nilai)
    paket_referensi = _topik_sintetis(domain, _SamplerTetap({"a": 2}), _templat_teks_dari_nilai)
    rng_baru = random.Random(11)
    rng_referensi = random.Random(11)

    # Act
    hasil_baru = generator._soal_unik_per_lembar(paket_baru, urutan, rng_baru, LEVEL_SINTETIS)
    hasil_referensi = _referensi_unik_per_lembar(paket_referensi, urutan, rng_referensi, LEVEL_SINTETIS)

    # Assert
    assert hasil_baru == hasil_referensi
    assert hasil_baru[1].parameter == {"a": "1"}
    assert hasil_baru[1].teks == "'1'"
    assert rng_baru.getstate() == rng_referensi.getstate()


def test_domain_habis_menerima_soal_berulang_tanpa_undian_tambahan():
    # Arrange: hanya {"a": 1} yang bermalrule (satu tanda), tetapi jumlah parameter mentah dua.
    # Slot kedua memakai tanda yang sama, domain sudah habis: harus diterima tanpa fallback.
    domain = ({"a": 1}, {"a": 2, "malrule": False})
    urutan = (TEMPLATE_SINTETIS,) * 2
    sampler_baru = _SamplerTetap({"a": 1})
    sampler_referensi = _SamplerTetap({"a": 1})
    paket_baru = _topik_sintetis(domain, sampler_baru)
    paket_referensi = _topik_sintetis(domain, sampler_referensi)
    rng_baru = random.Random(3)
    rng_referensi = random.Random(3)

    # Act
    hasil_baru = generator._soal_unik_per_lembar(paket_baru, urutan, rng_baru, LEVEL_SINTETIS)
    hasil_referensi = _referensi_unik_per_lembar(paket_referensi, urutan, rng_referensi, LEVEL_SINTETIS)

    # Assert
    assert len(hasil_baru) == 2
    assert sampler_baru.jumlah_panggilan == 2
    assert hasil_baru == hasil_referensi
    assert rng_baru.getstate() == rng_referensi.getstate()


# ── 3. Cache dipakai: sekali hitung per argumen ─────────────────────────


def _enumerator_pencatat(panggilan):
    def enumerator(template_id, level):
        panggilan.append((template_id, level))
        return ({"a": 1}, {"a": 2})
    return enumerator


def test_domain_sidik_dengan_argumen_sama_memanggil_enumerator_sekali_dan_objek_sama():
    # Arrange
    panggilan = []
    enumerator = _enumerator_pencatat(panggilan)

    # Act
    pertama = domain_sidik(_templat_sintetis, enumerator, TEMPLATE_SINTETIS, LEVEL_SINTETIS)
    kedua = domain_sidik(_templat_sintetis, enumerator, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert kedua is pertama
    assert len(panggilan) == 1


def _templat_lain(**parameter):
    return _templat_sintetis(**parameter)


@pytest.mark.parametrize("argumen_beda", [
    {"level": "P4"},
    {"template_id": "tid_lain"},
    {"templat": _templat_lain},
], ids=["level", "template_id", "fungsi_template"])
def test_argumen_berbeda_membuat_entri_cache_baru(argumen_beda):
    # Arrange
    panggilan = []
    dasar = {
        "templat": _templat_sintetis,
        "enumerator": _enumerator_pencatat(panggilan),
        "template_id": TEMPLATE_SINTETIS,
        "level": LEVEL_SINTETIS,
    }

    # Act
    pertama = domain_sidik(**dasar)
    kedua = domain_sidik(**{**dasar, **argumen_beda})

    # Assert
    assert kedua is not pertama
    assert len(panggilan) == 2


def test_enumerator_berbeda_membuat_entri_cache_baru():
    # Arrange: paket gabungan bisa berbagi fungsi template dengan topik lain; enumerator-nya beda
    panggilan = []

    # Act
    pertama = domain_sidik(_templat_sintetis, _enumerator_pencatat(panggilan), TEMPLATE_SINTETIS, LEVEL_SINTETIS)
    kedua = domain_sidik(_templat_sintetis, _enumerator_pencatat(panggilan), TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert kedua is not pertama
    assert len(panggilan) == 2


def test_galat_enumerator_tidak_di_cache_dan_panggilan_berikutnya_mencoba_lagi():
    # Arrange
    panggilan = []

    def enumerator_gagal_sekali(template_id, level):
        panggilan.append(level)
        if len(panggilan) == 1:
            raise RuntimeError("enumerator belum siap")
        return ({"a": 1},)

    # Act
    with pytest.raises(RuntimeError, match="belum siap"):
        domain_sidik(_templat_sintetis, enumerator_gagal_sekali, TEMPLATE_SINTETIS, LEVEL_SINTETIS)
    hasil = domain_sidik(_templat_sintetis, enumerator_gagal_sekali, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert len(panggilan) == 2
    assert hasil.jumlah_parameter == 1


# ── 4. Semantik duplikat sidik jari ──────────────────────────────────────


def _enumerator_dengan_duplikat(template_id, level):
    """Indeks 0 dan 2 sama-sama kelas=1; indeks 3 tanpa malrule; indeks 1 dan 4 unik."""
    return (
        {"kelas": 1, "varian": "a", "malrule": True},
        {"kelas": 3, "varian": "a", "malrule": True},
        {"kelas": 1, "varian": "b", "malrule": True},
        {"kelas": 9, "varian": "a", "malrule": False},
        {"kelas": 2, "varian": "c", "malrule": True},
    )


def test_sidik_duplikat_memakai_posisi_pertama_dan_indeks_parameter_terakhir():
    # Arrange
    def tanda_kelas(kelas):
        return f"{LEVEL_SINTETIS}|{TEMPLATE_SINTETIS}(kelas={kelas})"

    # Act
    domain = domain_sidik(_templat_kelas_saja, _enumerator_dengan_duplikat, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert domain.tanda == (tanda_kelas(1), tanda_kelas(3), tanda_kelas(2))
    assert domain.indeks == (2, 1, 4)
    assert domain.jumlah_parameter == 5
    assert domain.himpunan == frozenset(domain.tanda)


def test_indeks_sidik_menunjuk_parameter_yang_menghasilkan_tanda_itu():
    # Arrange
    parameter = _enumerator_dengan_duplikat(TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Act
    domain = domain_sidik(_templat_kelas_saja, _enumerator_dengan_duplikat, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    for tanda, indeks in zip(domain.tanda, domain.indeks):
        assert _templat_kelas_saja(**parameter[indeks]).tanda_tangan == tanda


# ── 5. Galat generator tetap sama ────────────────────────────────────────


def test_domain_kosong_melempar_galat_domain_parameter_kosong():
    # Arrange
    paket = _topik_sintetis((), _SamplerTetap({"a": 1}))

    # Act / Assert
    with pytest.raises(ValueError, match="domain parameter kosong"):
        generator._soal_unik_per_lembar(paket, (TEMPLATE_SINTETIS,), random.Random(1), LEVEL_SINTETIS)


def test_semua_soal_tanpa_malrule_melempar_galat_domain_tanpa_malrule():
    # Arrange
    paket = _topik_sintetis(({"a": 1, "malrule": False},), _SamplerTetap({"a": 1, "malrule": False}))

    # Act / Assert
    with pytest.raises(RuntimeError, match="domain tanpa malrule yang sah"):
        generator._soal_unik_per_lembar(paket, (TEMPLATE_SINTETIS,), random.Random(1), LEVEL_SINTETIS)


def test_sampler_keluar_domain_melempar_galat():
    # Arrange: domain hanya {"a": 1}, sampler mengembalikan {"a": 7} yang tidak ada di domain
    paket = _topik_sintetis(({"a": 1},), _SamplerTetap({"a": 7}))

    # Act / Assert
    with pytest.raises(ValueError, match="sampler keluar domain"):
        generator._soal_unik_per_lembar(paket, (TEMPLATE_SINTETIS,), random.Random(1), LEVEL_SINTETIS)


# ── 6. Tidak ada efek samping antar lembar ──────────────────────────────


def test_mutasi_parameter_lembar_pertama_tidak_mengubah_lembar_kedua_dengan_seed_sama(monkeypatch):
    # Arrange: batas undian 1 + template domain kecil + slot lebih banyak dari domain memaksa
    # jalur cadangan dipakai; cache yang menyimpan objek Soal akan membocorkan mutasi ke lembar kedua.
    monkeypatch.setattr(generator, "_BATAS_UNDI_UNIK", 1)
    paket, level, tid, ukuran = _template_domain_kecil()
    urutan = (tid,) * min(ukuran + 3, BATAS_SLOT_UJI)
    rng_pertama = _RngHitung(SEED_UJI[1])
    lembar_pertama = generator._soal_unik_per_lembar(paket, urutan, rng_pertama, level)
    sebelum_mutasi = tuple(replace(s, parameter=dict(s.parameter)) for s in lembar_pertama)
    assert rng_pertama.dipanggil > 0, "jalur cadangan harus terpakai agar tes bermakna"

    # Act: rusak seluruh dict parameter lembar pertama, lalu rakit lembar kedua dengan seed sama
    for soal in lembar_pertama:
        for kunci in soal.parameter:
            soal.parameter[kunci] = "DIMUTASI"
    lembar_kedua = generator._soal_unik_per_lembar(paket, urutan, random.Random(SEED_UJI[1]), level)

    # Assert
    assert lembar_kedua == sebelum_mutasi


# ── 7. Hitungan variasi per kelas (kurikulum_kelas_hitung) ──────────────


def test_variasi_domain_menghitung_tanda_bermalrule_unik():
    # Arrange: {"a": 1} muncul dua kali (tanda sama); {"a": 3} tanpa malrule
    paket = types.SimpleNamespace(
        templates={TEMPLATE_SINTETIS: _templat_sintetis},
        domain_parameter=lambda template_id, level: ({"a": 1}, {"a": 2}, {"a": 1}, {"a": 3, "malrule": False}),
    )

    # Act
    hasil = hitung._variasi_domain(paket, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert hasil == (2, hitung.JENIS_TEPAT, "")


@pytest.mark.parametrize("domain", [(), ({"a": 1, "malrule": False},)],
                         ids=["domain kosong", "semua tanpa malrule"])
def test_variasi_domain_kosong_kembali_nol_tepat_tanpa_melempar(domain):
    # Arrange
    paket = types.SimpleNamespace(
        templates={TEMPLATE_SINTETIS: _templat_sintetis},
        domain_parameter=lambda template_id, level: domain,
    )

    # Act
    hasil = hitung._variasi_domain(paket, TEMPLATE_SINTETIS, LEVEL_SINTETIS)

    # Assert
    assert hasil == (0, hitung.JENIS_TEPAT, "")
