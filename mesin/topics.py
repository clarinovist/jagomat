"""Kontrak paket topik + registry — dimensi yang hilang dari mesin.

Sebelum Fase A, mesin mengandaikan satu topik: komposisi lembar, profil
angka, judul bagian, dan renderer semuanya mengandaikan pola bilangan.
Fase A memasukkan dimensi itu sebagai PAKET: satu topik membawa seluruh
kontennya sendiri, dan menambah topik baru tidak menyentuh paket lain.

Isi satu paket (dataclass Topik):

  templates       template_id -> fungsi parameter -> Soal
  komposisi       level -> urutan template_id untuk satu lembar
  profil          level -> batas angka per parameter
  judul_bagian    huruf bagian -> judul yang tampil di lembar
  catatan_bagian  huruf bagian -> catatan khusus di bawah judul
  render_badan    soal -> HTML/SVG khusus, atau None untuk renderer teks

Konvensi penting yang diwarisi dari kode lama:

  - Level TAK DIKENAL tidak boleh meledak. `siswa.tingkat` adalah kolom
    teks bebas yang sudah terisi di basis data produksi; satu nilai aneh
    jatuh ke level bawaan (P3), bukan exception. Topik berbeda: salah
    ketik id topik adalah bug pemanggil, jadi dicari dengan jelas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from templates import LEVEL, LEVEL_BAWAAN, LEVEL_TINGKAT, Soal

TOPIK_BAWAAN = "pola-bilangan"


@dataclass(frozen=True)
class Topik:
    """Seluruh konten satu topik — lihat docstring modul."""

    id: str
    nama: str
    judul_lembar: str
    judul_penilaian: str
    templates: dict[str, Callable[..., Soal]]
    komposisi: dict[str, tuple[str, ...]]
    profil: dict[str, dict[str, Any]] = field(default_factory=dict)
    judul_bagian: dict[str, str] = field(default_factory=dict)
    catatan_bagian: dict[str, str] = field(default_factory=dict)
    render_badan: Callable[[Soal], str | None] | None = None
    # template_id + rng + level -> parameter; satu-satunya pemilik aturan
    # batas angka supaya seed yang sama selalu menghasilkan soal yang sama.
    parameter_untuk: Callable[..., dict[str, Any]] | None = None
    # Inventaris historis tetap di komposisi. Override ini hanya untuk writer
    # default; reader konteks/laporan tidak boleh menyusut saat recovery.
    komposisi_writer: dict[str, tuple[str, ...]] | None = None

    def komposisi_untuk(self, level: str) -> tuple[str, ...]:
        """Urutan template untuk satu lembar di level itu.

        Level tak dikenal jatuh ke level bawaan (P3) — kontrak lama
        `susun_lembar`, dipertahankan demi data produksi. Paket yang memang
        mulai di level lebih tinggi (mis. aritmetika P5/P6) jatuh ke level
        pertama yang mereka dukung, bukan mencoba mengakses P3 yang tidak
        mereka miliki.
        """
        sumber = self.komposisi if self.komposisi_writer is None else self.komposisi_writer
        bawaan = sumber.get(LEVEL_BAWAAN, next(iter(sumber.values())))
        return sumber.get(level, bawaan)

    def profil_untuk(self, level: str) -> dict[str, Any]:
        """Batas angka untuk level itu; tak dikenal jatuh ke P3 —
        kontrak lama `generator.profil`, dengan alasan yang sama. Paket yang
        mulai di level lebih tinggi jatuh ke profil pertama yang tersedia."""
        bawaan = self.profil.get(LEVEL_BAWAAN, next(iter(self.profil.values())))
        return dict(self.profil.get(level, bawaan))

    def susun_lembar(self, level: str) -> tuple[str, ...]:
        return self.komposisi_untuk(level)


# ── Registry ────────────────────────────────────────────────────────────
#
# PAKET sengaja TIDAK diisi saat modul ini diimpor. Modul paket mengimpor
# templates.py, dan templates.py mengekspor simbol kompatibilitas yang
# mengimpor topik — daftar isi yang lengkap saat impor akan membentuk
# lingkaran yang hasilnya bergantung urutan impor. Jadi paket dimuat
# MALAS: panggilan fungsi di bawah yang memuatnya, dan setelah itu
# registry terisi penuh apa pun urutan impor pertama.

PAKET: dict[str, Topik] = {}
_SUDAH_DIMUAT = False
_SEDANG_MEMUAT = False


def daftarkan(topik: Topik) -> None:
    if topik.id in PAKET:
        raise ValueError(f"topik duplikat: {topik.id}")
    PAKET[topik.id] = topik


def _pastikan_dimuat() -> None:
    global _SUDAH_DIMUAT, _SEDANG_MEMUAT
    if _SUDAH_DIMUAT or _SEDANG_MEMUAT:
        return
    _SEDANG_MEMUAT = True
    import topic_number_patterns  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_basic_arithmetic  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_plane_geometry  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_combinatorics  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_number_theory  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_advanced_arithmetic  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_solid_geometry  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_statistics  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_logic  # noqa: F401  (mendaftarkan diri saat impor)
    import topic_measurement  # noqa: F401  (mendaftarkan diri saat impor)

    if not PAKET:
        raise RuntimeError("paket topik dimuat tapi tidak mendaftarkan diri")
    _daftarkan_campuran()
    _SUDAH_DIMUAT = True
    _SEDANG_MEMUAT = False


def _daftarkan_campuran() -> None:
    if "campuran" in PAKET:
        return
    gabungan_templates = {}
    pemilik_param = {}
    for t in list(PAKET.values()):
        for tid, fn in t.templates.items():
            gabungan_templates[tid] = fn
        if t.parameter_untuk:
            for tid in t.templates:
                pemilik_param[tid] = t.parameter_untuk

    def parameter_campuran(template_id: str, rng, level: str):
        if template_id in pemilik_param:
            return pemilik_param[template_id](template_id, rng, level)
        raise KeyError(f"template {template_id} tidak punya pemilik parameter")

    komposisi_campuran = {}
    writer_campuran = {}
    # Campuran simulasi ujian tetap P3–P6; P1/P2 dipilih per materi manual.
    for lvl in LEVEL_TINGKAT:
        topik_level = [t for t in PAKET.values() if lvl in t.komposisi and t.id != "campuran"]
        urutan_gabungan = []
        max_len = max((len(t.komposisi[lvl]) for t in topik_level), default=0)
        for idx in range(max_len):
            for t in topik_level:
                comp = t.komposisi[lvl]
                if idx < len(comp):
                    urutan_gabungan.append(comp[idx])
        komposisi_campuran[lvl] = tuple(urutan_gabungan)
        writers = [t.komposisi_untuk(lvl) for t in topik_level]
        writer_campuran[lvl] = tuple(comp[i] for i in range(max(map(len, writers), default=0))
                                     for comp in writers if i < len(comp))

    topik_campuran = Topik(
        id="campuran",
        nama="✨ Campuran Semua Topik (Simulasi Ujian)",
        judul_lembar="Simulasi Ujian — Campuran Semua Topik",
        judul_penilaian="Penilaian — Simulasi Ujian",
        templates=gabungan_templates,
        komposisi=komposisi_campuran,
        komposisi_writer=writer_campuran,
        profil={"P3": {}, "P4": {}, "P5": {}, "P6": {}},
        render_badan=_render_gabungan(
            [t for t in PAKET.values() if t.id != "campuran"]
        ),
        parameter_untuk=parameter_campuran,
    )
    PAKET["campuran"] = topik_campuran


def paket_bawaan() -> Topik:
    _pastikan_dimuat()
    return PAKET[TOPIK_BAWAAN]


def ambil(topik_id: str) -> Topik:
    """Ambil paket berdasar id. Topik tak dikenal = bug pemanggil:
    dilempar, bukan disamarkan (beda dengan level, lihat docstring modul)."""
    _pastikan_dimuat()
    try:
        return PAKET[topik_id]
    except KeyError:
        raise KeyError(
            f"topik tidak dikenal: {topik_id!r}. "
            f"Yang terdaftar: {daftar_topik()}"
        ) from None


def gabungan(topik_ids) -> Topik:
    """Paket sintetis dari BEBERAPA topik pilihan (poin 4 tahap 2).

    Berbeda dari "campuran" yang selalu memakai SEMUA topik: di sini guru
    memilih sebagian, misalnya "geometri datar + pengukuran" untuk anak
    yang lemah di dua itu saja.

    Sengaja TIDAK mendaftarkan apa pun ke PAKET: paket ini ad-hoc per
    permintaan. Kalau didaftarkan, dropdown topik akan penuh paket
    sekali-pakai dan dua permintaan berbeda bisa saling menimpa.

    Satu topik (setelah duplikat dibuang) mengembalikan paket aslinya —
    tidak ada gunanya membungkus ulang. Topik tak dikenal dilempar lewat
    `ambil()`, bukan dilewati diam-diam: pilihan yang salah harus terlihat.
    """
    _pastikan_dimuat()
    urut: list[str] = []
    for tid in topik_ids:
        if tid not in urut:
            urut.append(tid)
    if not urut:
        raise ValueError("pilih minimal satu topik")
    paket_terpilih = [ambil(t) for t in urut]  # tak dikenal -> KeyError
    if len(paket_terpilih) == 1:
        return paket_terpilih[0]

    templates: dict[str, Any] = {}
    pemilik_param: dict[str, Any] = {}
    for t in paket_terpilih:
        templates.update(t.templates)
        if t.parameter_untuk:
            for tid in t.templates:
                pemilik_param[tid] = t.parameter_untuk

    def parameter_gabungan(template_id: str, rng, level: str):
        if template_id in pemilik_param:
            return pemilik_param[template_id](template_id, rng, level)
        raise KeyError(f"template {template_id} tidak punya pemilik parameter")

    # Interleave antar-topik (pola yang sama dengan campuran): ambil
    # template ke-i dari tiap topik bergantian, supaya satu topik tidak
    # memborong bagian awal lembar.
    komposisi: dict[str, tuple[str, ...]] = {}
    writer: dict[str, tuple[str, ...]] = {}
    for lvl in LEVEL:
        punya = [t for t in paket_terpilih if lvl in t.komposisi]
        if not punya:
            continue
        panjang = max(len(t.komposisi[lvl]) for t in punya)
        deret: list[str] = []
        for i in range(panjang):
            for t in punya:
                comp = t.komposisi[lvl]
                if i < len(comp):
                    deret.append(comp[i])
        komposisi[lvl] = tuple(deret)
        writers = [t.komposisi_untuk(lvl) for t in punya]
        writer[lvl] = tuple(comp[i] for i in range(max(map(len, writers), default=0))
                            for comp in writers if i < len(comp))

    nama_pendek = " + ".join(t.nama for t in paket_terpilih)
    return Topik(
        id="gabungan:" + ",".join(urut),
        nama=nama_pendek,
        judul_lembar="Latihan Gabungan — " + nama_pendek,
        judul_penilaian="Penilaian — " + nama_pendek,
        templates=templates,
        komposisi=komposisi,
        komposisi_writer=writer,
        profil={lvl: {} for lvl in komposisi},
        render_badan=_render_gabungan(paket_terpilih),
        parameter_untuk=parameter_gabungan,
    )


def _render_gabungan(paket_terpilih):
    """Dispatch render_badan ke topik PEMILIK tiap template.

    Paket sintetis (campuran & gabungan) merangkai templates dari beberapa
    topik tapi dulu lahir dengan `render_badan=None`, sehingga soal yang
    punya bentuk visual khusus (SVG korek api, susunan titik, kotak isian
    deret) turun jadi teks polos begitu masuk sesi campuran/gabungan —
    termasuk sesi remedial. Anak jadi melihat soal berbeda untuk template
    yang sama, tergantung sesi itu lahir dari jalur mana.

    Renderer dipetakan per template_id, bukan dirantai berurutan: renderer
    hanya boleh menyentuh templatenya sendiri, dan pemetaan membuat itu
    berlaku otomatis tanpa bergantung pada urutan paket.
    """
    peta = {}
    for t in paket_terpilih:
        if t.render_badan is None:
            continue
        for tid in t.templates:
            peta.setdefault(tid, t.render_badan)
    if not peta:
        return None

    def render_badan_gabungan(soal):
        fungsi = peta.get(soal.template_id)
        return fungsi(soal) if fungsi else None

    return render_badan_gabungan


def pemilik_template(template_id: str) -> str | None:
    """Id topik yang MEMILIKI template ini, atau None kalau tak dikenal.

    Paket sintetis ("campuran", "gabungan:...") sengaja dilewati: yang
    dicari pemilik aslinya, supaya pemanggil bisa membangun paket yang
    memuat template itu beserta `parameter_untuk` dan `render_badan`-nya.
    """
    _pastikan_dimuat()
    for t in PAKET.values():
        if t.id == "campuran":
            continue
        if template_id in t.templates:
            return t.id
    return None


def paket_untuk_template(template_ids) -> Topik:
    """Paket terkecil yang memuat SEMUA template ini (remedial lintas topik).

    Sasaran remedial datang dari riwayat anak, jadi bisa mencakup beberapa
    topik sekaligus — paket bawaan tidak memuatnya dan generator melempar
    KeyError (akar 502 produksi 3 Sep 2026). Di sini topik pemiliknya
    dikumpulkan lalu dirangkai lewat `gabungan()`, sehingga paket hasilnya
    membawa `parameter_untuk` DAN `render_badan` pemilik aslinya.

    Template tak dikenal (mis. sisa template yang sudah dihapus dari kode)
    DILEWATI, bukan dilempar: riwayat anak tidak boleh membuat fitur mati.
    Kalau tak satu pun dikenal, jatuh ke paket bawaan.
    """
    _pastikan_dimuat()
    urut: list[str] = []
    for tid in template_ids:
        pemilik = pemilik_template(tid)
        if pemilik is not None and pemilik not in urut:
            urut.append(pemilik)
    if not urut:
        return PAKET[TOPIK_BAWAAN]
    return gabungan(urut)


def daftar_topik() -> list[str]:
    _pastikan_dimuat()
    return sorted(PAKET)


def dari_sesi(nilai: str | None) -> Topik:
    """Topik untuk satu baris sesi dari basis data.

    Sesi lama menyimpan 'pola bilangan' (dengan spasi — default kolom
    sebelum Fase A) dan nilai aneh tidak boleh membuat lembar gagal:
    keduanya jatuh ke paket bawaan. Kontraknya berbeda dari ambil() yang
    tegas, dengan alasan yang sama dengan level yang fallback.
    """
    _pastikan_dimuat()
    if nilai in PAKET:
        return PAKET[nilai]
    # Sesi gabungan menyimpan "gabungan:a,b" — bangun ulang paketnya supaya
    # halaman lembar/cetak sesi lama tetap menampilkan judul yang benar.
    # Kalau salah satu topiknya sudah tidak ada, jatuh ke bawaan (kontrak
    # fungsi ini: JANGAN pernah membuat halaman sesi lama gagal).
    if isinstance(nilai, str) and nilai.startswith("gabungan:"):
        try:
            return gabungan([t for t in nilai[len("gabungan:"):].split(",") if t])
        except (KeyError, ValueError):
            return PAKET[TOPIK_BAWAAN]
    return PAKET[TOPIK_BAWAAN]


def registri() -> dict[str, Callable[..., Soal]]:
    """Gabungan template semua paket. Pemanggil lama yang masih mengimpor
    REGISTRI dari templates.py mendapat dict ini lewat jalur kompatibilitas."""
    _pastikan_dimuat()
    gabungan: dict[str, Callable[..., Soal]] = {}
    for t in PAKET.values():
        if t.id == "campuran":
            continue
        for tid, fungsi in t.templates.items():
            if tid in gabungan:
                raise ValueError(f"template_id duplikat lintas topik: {tid}")
            gabungan[tid] = fungsi
    return gabungan
