"""Generator lembar latihan — mesin umum, isi ditentukan paket topik.

Seed menentukan parameter, parameter menentukan soal. Sejak Fase A (registry
topik) generator TIDAK tahu apa-apa tentang pola bilangan: template, batas
angka, dan komposisi lembar datang dari paket topik (topics.py).

Kontrak determinisme yang diuji di __tests__/test_generator.py dan
__tests__/test_identitas_refactor.py:
  - seed sama + topik sama -> lembar identik (bisa dicetak ulang persis)
  - seed beda -> parameter beda (bank soal benar-benar tumbuh)
  - tiap malrule menghasilkan jawaban != kunci (kalau sama, malrule itu bug)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from templates import LEVEL, LEVEL_BAWAAN, Soal
from topics import TOPIK_BAWAAN, Topik, ambil


_BATAS_UNDI_UNIK = 40


def profil(level: str) -> dict:
    """Batas angka untuk satu level — milik paket topik sejak Fase A.

    Kontrak lama dipertahankan: level tak dikenal jatuh ke P3 (bukan
    exception), karena `siswa.tingkat` adalah kolom teks bebas yang sudah
    terisi di basis data produksi. Yang salah levelnya lebih baik daripada
    yang tidak ada lembarnya.
    """
    return paket_bawaan().profil_untuk(level)


def paket_bawaan() -> Topik:
    from topics import paket_bawaan as _paket_bawaan

    return _paket_bawaan()


@dataclass(frozen=True)
class Lembar:
    seed: int
    soal: tuple[Soal, ...]
    level: str = LEVEL_BAWAAN

    @property
    def tanda_tangan(self) -> str:
        return "|".join(s.tanda_tangan for s in self.soal)


def _level_efektif(paket: Topik, level: str) -> str:
    """Validasi level resmi, atau normalkan teks lama ke level paket pertama."""
    if level in LEVEL and level not in paket.komposisi:
        raise ValueError(
            f"topik {paket.id!r} tidak tersedia untuk level {level!r}; "
            f"level yang didukung: {sorted(paket.komposisi)}"
        )
    return level if level in paket.komposisi else next(iter(paket.komposisi))


def _acak_urutan(
    urutan: tuple[str, ...], rng: random.Random
) -> tuple[str, ...]:
    """Acak pemetaan posisi->template per lembar utk topik multi-template.

    Feedback Filia (1 Sep 2026): komposisi terkunci menaruh template
    BERULANG di posisi TETAP (mis. P3 statistika: modus di posisi ganjil,
    diagram batang di genap), jadi antar-seed posisi yang sama bermodel
    (template+varian) identik — cuma angkanya beda. Di sini urutan template
    diacak ulang per lembar supaya posisi yang sama tidak lagi selalu
    memakai template yang sama.

    HANYA memakai `rng` (deterministik per seed) — TIDAK hash() (trap
    PYTHONHASHSEED, lihat SKILL.md pitfall #14): seed yang sama harus
    melahirkan lembar yang identik antar-proses. Karena shuffle menjaga
    multiset, dan komposisi tiap level sudah berbobot paling banyak
    ceil(n/3) per template (kecuali kasus yang secara matematis mustahil,
    mis. P3 statistika yang cuma 2 template), batas ini otomatis terbawa.

    Komposisi yang semua template-nya berbeda (mis. pola-bilangan: 12
    template beda) DIBIARKAN — di sana urutan punya makna pedagogis
    (bagian A..F naik, tiap template sekali).
    """
    if len(set(urutan)) == len(urutan):
        return urutan
    lst = list(urutan)
    rng.shuffle(lst)
    return tuple(lst)


def buat_lembar(
    seed: int,
    urutan: tuple[str, ...] | None = None,
    level: str = LEVEL_BAWAAN,
    topik: str | Topik = TOPIK_BAWAAN,
    jumlah_soal: int | None = None,
) -> Lembar:
    """Bangun satu lembar penuh dari seed. Deterministik.

    `topik` boleh berupa id (str) ATAU objek Topik yang sudah dibangun —
    yang kedua dipakai paket gabungan ad-hoc (topics.gabungan) yang
    sengaja tidak terdaftar di registri global.
    """
    paket = topik if isinstance(topik, Topik) else ambil(topik)
    level_efektif = _level_efektif(paket, level)
    rng = random.Random(seed)
    if urutan is None:
        urutan = paket.komposisi_untuk(level_efektif)
    if jumlah_soal is not None and jumlah_soal > 0:
        base = list(urutan)
        while len(base) < jumlah_soal:
            base.extend(urutan)
        urutan = tuple(base[:jumlah_soal])
    urutan = _acak_urutan(urutan, rng)
    if paket.unik_per_lembar:
        soal = _soal_unik_per_lembar(paket, urutan, rng, level_efektif)
    else:
        # Jalur historis persis: tanpa enumerasi atau undian tambahan.
        soal = tuple(_soal_layak(paket, t, rng, level_efektif) for t in urutan)
    return Lembar(seed=seed, soal=soal, level=level_efektif)


def _soal_unik_per_lembar(paket, urutan, rng, level):
    """Undi ulang slot kembar; ulang boleh hanya setelah domain sah habis.

    Domain lokal per template, tanpa mengubah parameter atau state paket.
    Batas retry bukan bukti domain habis: jika RNG terus memilih duplikat,
    pilih sisa enumerator dalam urutan stabil memakai RNG yang sama.
    """
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
        for _ in range(_BATAS_UNDI_UNIK):
            soal = _soal_layak(paket, tid, rng, level)
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


def _soal_layak(
    paket: Topik,
    template_id: str,
    rng: random.Random,
    level: str = LEVEL_BAWAAN,
    batas: int = 40,
) -> Soal:
    """Ambil parameter sampai dapat soal yang benar-benar bisa mendiagnosis.

    Beberapa kombinasi parameter menghasilkan soal yang sah tapi tumpul:
    seluruh malrule-nya bertabrakan dengan kunci atau satu sama lain, lalu
    dibuang oleh `saring_malrule`. Sisanya soal tanpa satu pun jalur
    diagnosis — anak tetap harus mengerjakannya, tapi jawaban salahnya tidak
    memberi tahu apa-apa. Itu beban menulis tanpa imbalan informasi.

    Contoh nyata: siklus huruf 'CBC' dengan posisi kelipatan 3. Kunci 'C',
    dan "ambil unsur terakhir siklus" juga 'C' — satu-satunya malrule
    terbuang, soal jadi kosong.

    Karena rng dipakai berurutan, penolakan tetap deterministik: seed yang
    sama menghasilkan lembar yang sama.
    """
    if paket.parameter_untuk is None:
        raise RuntimeError(
            f"topik {paket.id!r} tidak mendefinisikan parameter_untuk — "
            "paket tidak bisa menghasilkan soal"
        )
    for _ in range(batas):
        soal = paket.templates[template_id](
            **paket.parameter_untuk(template_id, rng, level)
        )
        if soal.malrule:
            # Level ditempelkan di sini, bukan di dalam template: definisi
            # soal tidak perlu tahu untuk siapa ia dipakai. Pemisahan yang
            # sama dengan alasan generator.py terpisah dari templates.py.
            return replace(soal, level=level)
    raise RuntimeError(
        f"{template_id}: {batas} percobaan tanpa satu pun malrule bertahan — "
        "periksa definisi malrule template ini"
    )


def buat_soal(
    template_id: str,
    seed: int,
    level: str = LEVEL_BAWAAN,
    topik: str = TOPIK_BAWAAN,
) -> Soal:
    """Satu soal saja — untuk menambal bank soal per tipe."""
    paket = ambil(topik)
    return _soal_layak(
        paket, template_id, random.Random(seed), _level_efektif(paket, level)
    )
