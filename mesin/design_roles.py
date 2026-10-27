"""Peran semantik token per permukaan: peta rujukan desain yang dijaga test.

Setiap pasangan menunjuk aturan CSS nyata (modul, konstanta, selektor, properti)
dan NAMA token di design_tokens, bukan nilainya. Test menukar token di namespace
terisolasi untuk membuktikan token itu benar-benar mencapai aturan tersebut, lalu
menghitung kontras pasangan yang memang tampil bersama. Modul ini tidak dipakai
saat runtime aplikasi; pakai `peta_peran()` untuk memilih token di halaman baru.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Optional, Tuple

import design_tokens as T

MIN_TEKS = 4.5    # teks normal (WCAG 1.4.3)
MIN_GRAFIS = 3.0  # batas kontrol, indikator fokus, teks besar (WCAG 1.4.11)


@dataclass(frozen=True)
class Sisi:
    """Satu warna pada satu aturan CSS, dengan peran semantiknya."""
    peran: str
    token: str
    modul: str
    konstanta: str
    selektor: str
    properti: str
    # Token var(--x) yang dirujuk aturan; nilai `token` dipasang ke --x pada
    # aturan `pemasang` (blok tema admin).
    alias: Optional[str] = None
    pemasang: Optional[str] = None


@dataclass(frozen=True)
class Pasangan:
    depan: Sisi
    belakang: Sisi
    minimum: float


def _sumber(modul, konstanta):
    def sisi(peran, token, selektor, properti, alias=None, pemasang=None):
        return Sisi(peran, token, modul, konstanta, selektor, properti, alias, pemasang)
    return sisi


_stitch = _sumber("style_stitch", "GAYA_STITCH")
_sesi = _sumber("style_stitch", "CSS_SESI")
_anak = _sumber("child_style", "GAYA_ANAK")
_latihan = _sumber("child_latihan_style", "GAYA_LATIHAN")
_profil = _sumber("profile_workspace", "GAYA_PROFIL")
_guru = _sumber("teacher_style", "GAYA_GURU")
_admin = _sumber("admin_style", "GAYA_ADMIN")
_cetak = _sumber("print_style", "GAYA_CETAK")


def _teks(depan, belakang):
    return Pasangan(depan, belakang, MIN_TEKS)


def _grafis(depan, belakang):
    return Pasangan(depan, belakang, MIN_GRAFIS)


def _badge(nama, latar, teks, selektor, sumber=_stitch):
    return _teks(sumber(nama + "_teks", teks, selektor, "color"),
                 sumber(nama + "_latar", latar, selektor, "background"))


_HALAMAN = _stitch("latar_halaman", "LATAR_MURID", "body.st", "background")
_KARTU = _stitch("latar_kartu", "LATAR_KARTU", ".st-kartu", "background")
_TEKS = _stitch("teks_utama", "TEKS_UTAMA", "body.st", "color")
_TEKS_AKSI = _stitch("teks_aksi", "TEKS_PUTIH", ".st-tombol-coral", "color")

_DASAR = (
    _teks(_TEKS, _HALAMAN),
    _teks(_TEKS, _KARTU),
    _teks(_stitch("teks_judul", "TEKS_JUDUL", "h1.st", "color"), _HALAMAN),
    _teks(_stitch("tautan", "AKSEN_TEAL_TUA", ".pesan-editorial-st a", "color"), _HALAMAN),
    _teks(_stitch("tautan", "AKSEN_TEAL_TUA", ".publik-isi-st a", "color"), _HALAMAN),
    _teks(_stitch("tautan", "AKSEN_TEAL_TUA", ".masuk-link-st a", "color"), _HALAMAN),
    _teks(_TEKS_AKSI, _stitch("aksi_utama", "AKSEN_KORAL_TUA", ".st-tombol-coral", "background")),
    _teks(_TEKS_AKSI, _stitch("aksi_utama_hover", "AKSEN_KORAL_HOVER", ".st-tombol-coral:hover", "background")),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".st-input", "border"), _KARTU),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".st-input", "border"), _HALAMAN),
    _grafis(_stitch("fokus", "FOKUS_AKSEN", ".info:focus-visible", "outline"), _HALAMAN),
    _badge("badge_diagnostik", "STATUS_DIAGNOSTIK_BG", "STATUS_DIAGNOSTIK_TEKS", ".st-badge.diagnostik"),
    _badge("badge_latihan", "STATUS_LATIHAN_BG", "STATUS_LATIHAN_TEKS", ".st-badge.latihan"),
    _badge("badge_baru", "AKSEN_KORAL_TUA", "TEKS_INVERS", ".st-badge.baru"),
    _badge("badge_selesai", "LATAR_ELEVASI", "TEKS_VARIAN", ".st-badge.selesai"),
    _badge("badge_review", "LATAR_REVIEW", "TEKS_REVIEW", ".st-badge.review"),
    _badge("peran_pengelola", "BADGE_ADMIN_BG", "BADGE_ADMIN_TEKS", ".badge-peran-admin"),
    _badge("peran_guru", "BADGE_GURU_BG", "BADGE_GURU_TEKS", ".badge-peran-guru"),
    _badge("galat", "LATAR_GALAT", "TEKS_GALAT", ".kerja-timer-st.habis"),
    _badge("sukses", "LATAR_TERSIMPAN", "TEKS_TERSIMPAN", ".tahap-rencana-st.selesai"),
    _badge("tahap_aktif", "AKSEN_TEAL_TUA", "TEKS_PUTIH", ".tahap-rencana-st.aktif"),
)

_KARTU_SESI = _anak("latar_kartu", "LATAR_KARTU", ".anak-kartu-sesi-st", "background")
_BANNER = _anak("latar_banner", "ANAK_AKSEN_LATAR", ".anak-banner-st", "background")
_PIL = ".profil-workspace-st .anak-pil-st"
_PIL_AKTIF = _PIL + '[aria-current="true"]'
_TOMBOL_PROFIL = ".profil-workspace-st :is(.st-tombol-coral, .tombol-coral, .rencana-cta-utama-st)"

_PROFIL = (
    _teks(_anak("teks_utama", "ANAK_TEKS", ".anak-banner-st", "color"), _BANNER),
    _teks(_anak("tautan", "ANAK_AKSEN", ".anak-banner-tautan-st", "color"), _BANNER),
    _teks(_anak("tautan", "ANAK_AKSEN", ".anak-disclosure-st > summary", "color"), _HALAMAN),
    _teks(_anak("teks_bantuan", "ANAK_TEKS_BANTUAN", ".anak-kartu-isi-st small", "color"), _KARTU_SESI),
    _teks(_anak("teks_peringatan", "ANAK_PERHATIAN_TEKS", ".anak-kartu-peringatan-st", "color"), _KARTU_SESI),
    _badge("pil", "LATAR_KARTU", "ANAK_TEKS_REDUP", _PIL, _anak),
    _badge("pil_aktif", "ANAK_AKSEN_LATAR", "ANAK_AKSEN_HOVER", _PIL_AKTIF, _anak),
    _badge("chip_perhatian", "ANAK_PERHATIAN_LATAR", "ANAK_PERHATIAN_TEKS", ".anak-chip-perhatian-st", _anak),
    _badge("chip_baik", "ANAK_BAIK_LATAR", "ANAK_BAIK_TEKS", ".anak-chip-baik-st", _anak),
    _badge("chip_netral", "ANAK_NETRAL_LATAR", "ANAK_NETRAL_TEKS", ".anak-chip-netral-st", _anak),
    _badge("chip_info", "ANAK_INFO_LATAR", "ANAK_INFO_TEKS", ".anak-chip-info-st", _anak),
    _badge("chip_galat", "LATAR_GALAT", "TEKS_GALAT", ".anak-chip-galat-st", _anak),
    _teks(_profil("teks_aksi", "TEKS_PUTIH", _TOMBOL_PROFIL, "color"),
          _profil("aksi_utama", "AKSEN_TEAL_TUA", _TOMBOL_PROFIL, "background")),
    _grafis(_stitch("fokus", "AKSEN_TEAL_TUA", ".guru-beranda-st :is(a, button, summary):focus-visible", "outline"),
            _HALAMAN),
    _grafis(_latihan("batas_kontrol", "BORDER_KONTROL",
                     ".bungkus-st.profil-workspace-st.pendamping-editorial-st .latihan-terpadu-st select",
                     "border"), _KARTU),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".guru-cari-st input[type=search]", "border"), _KARTU),
    _grafis(_profil("batas_kontrol", "BORDER_KONTROL", ".profil-workspace-st .profil-filter-st input", "border"), _KARTU),
)

_MURID = (
    _badge("nomor", "AKSEN_TEAL_TUA", "TEKS_PUTIH", ".kerja-nomor-st"),
    _badge("pilihan_aktif", "AKSEN_TEAL_TUA", "TEKS_PUTIH", ".kerja-pill-st:has(input:checked)"),
    _badge("timer", "AKSEN_TEAL_TUA", "TEKS_INVERS", ".kerja-timer-st"),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".kerja-jawab-st input[type=text]", "border"), _KARTU),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".kerja-cara-st", "border"), _KARTU),
    _grafis(_stitch("batas_kontrol", "BORDER_KONTROL", ".kerja-restate-st", "border"), _KARTU),
    _grafis(_stitch("fokus", "FOKUS_AKSEN", ".kerja-cara-st:focus", "border-color"), _KARTU),
    _grafis(_stitch("bintang", "AKSEN_AMBER_TUA", ".kerja-bintang-st", "color"), _KARTU),
)

_KODE = (("benar", "KODE_BENAR"), ("K", "KODE_SALAH_KONSEP"), ("H", "KODE_SALAH_HITUNG"),
         ("E", "KODE_SALAH_TULIS"), ("N", "KODE_MENEBAK"))
_TINJAUAN = tuple(
    _badge("kode_" + kode, awalan + "_BG", awalan + "_TEKS", ".koreksi-status-st." + kode, _sesi)
    for kode, awalan in _KODE
) + (
    _badge("kode_B", "KODE_SALAH_BACA_BG", "TEKS_JUDUL", ".koreksi-status-st.B", _sesi),
    _badge("kode_T", "KODE_BELUM_LIAT_BG", "TEKS_JUDUL", ".koreksi-status-st.T", _sesi),
    _badge("nomor", "AKSEN_TEAL_TUA", "TEKS_PUTIH", ".koreksi-nomor-st", _sesi),
    _teks(_sesi("tautan", "AKSEN_TEAL_TUA", ".sesi-jejak-st a", "color"), _HALAMAN),
) + tuple(
    _badge("kode_lama_" + kode, awalan + "_BG", awalan + "_TEKS", ".kode." + kode, _guru)
    for kode, awalan in _KODE + (("B", "KODE_SALAH_BACA"), ("T", "KODE_BELUM_LIAT"))
) + (
    _teks(_guru("teks_kunci", "KODE_SALAH_BACA_TEKS", ".kunci", "color"),
          _guru("latar_halaman", "LATAR_MURID", "body", "background")),
    _grafis(_guru("batas_kontrol", "BORDER_KONTROL", "input[type=text]", "border"),
            _guru("latar_halaman", "LATAR_MURID", "body", "background")),
)


def _permukaan_admin(tema):
    pemasang = 'body.admin-readonly[data-tema="%s"]' % ("terang" if tema == "CERAH" else "gelap")

    def sisi(peran, nama, selektor, properti):
        return _admin(peran, f"ADMIN_{nama}_{tema}", selektor, properti,
                      alias=f"ADMIN_{nama}", pemasang=pemasang)
    halaman = sisi("latar_halaman", "LATAR", "body.admin-readonly", "background")
    kartu = sisi("latar_kartu", "PERMUKAAN", ".admin-kartu", "background")
    teks_aksi = sisi("teks_aksi", "PERMUKAAN", ".admin-tombol", "color")
    batas = sisi("batas_kontrol", "BORDER_KUAT", ".admin-cari input", "border")
    sekunder = sisi("latar_kartu", "PERMUKAAN", ".admin-tombol-sekunder", "background")
    pil_aktif = '.admin-chip[aria-current="true"]'
    latar_pil_aktif = sisi("latar_aksen", "AKSEN_LATAR", pil_aktif, "background")
    komponen = (
        _teks(sisi("aksi_sekunder", "AKSEN", ".admin-tombol-sekunder", "color"), sekunder),
        _grafis(sisi("batas_aksi_sekunder", "AKSEN", ".admin-tombol-sekunder", "border-color"), sekunder),
        _teks(sisi("aksi_sekunder_hover", "AKSEN_TEKS", ".admin-tombol-sekunder:hover", "color"),
              sisi("latar_aksen", "AKSEN_LATAR", ".admin-tombol-sekunder:hover", "background")),
        _teks(sisi("pil_teks", "REDUP", ".admin-chip", "color"),
              sisi("latar_kartu", "PERMUKAAN", ".admin-chip", "background")),
        _teks(sisi("pil_aktif_teks", "AKSEN_TEKS", pil_aktif, "color"), latar_pil_aktif),
        _grafis(sisi("pil_aktif_batas", "AKSEN", pil_aktif, "border"), latar_pil_aktif),
        _teks(sisi("tab_teks", "REDUP", ".admin-tab", "color"), halaman),
        _teks(sisi("tab_aktif", "AKSEN", '.admin-tab[aria-current="page"]', "color"), halaman),
        _teks(sisi("jejak", "AKSEN", ".admin-jejak a", "color"), halaman),
    )
    return komponen + (
        _teks(sisi("teks_utama", "TEKS", "body.admin-readonly", "color"), halaman),
        _teks(sisi("teks_redup", "REDUP", ".admin-brand small", "color"),
              sisi("latar_kartu", "PERMUKAAN", ".admin-sidebar", "background")),
        _teks(teks_aksi, sisi("aksi_utama", "AKSEN", ".admin-tombol", "background")),
        _teks(teks_aksi, sisi("aksi_utama_hover", "AKSEN_TEKS", ".admin-tombol:hover", "background")),
        _grafis(batas, kartu),
        _grafis(batas, halaman),
        _grafis(sisi("fokus", "AKSEN", ":focus-visible", "outline"), halaman),
        _teks(sisi("brand", "AKSEN", ".admin-brand", "color"), kartu),
    ) + tuple(
        _teks(sisi("badge_" + nama + "_teks", awalan + "_TEKS", selektor, "color"),
              sisi("badge_" + nama + "_latar", awalan + "_LATAR", selektor, "background"))
        for nama, awalan, selektor in (
            ("netral", "NETRAL", ".admin-badge"),
            ("baik", "BAIK", ".admin-badge.bien"),
            ("perhatian", "PERHATIAN", ".admin-badge.perhatian"),
            ("batal", "BAHAYA", ".admin-badge.batal"),
        )
    )


_CETAK = (
    _teks(_cetak("teks_utama", "CETAK_TINTA", "body", "color"),
          _cetak("latar_petunjuk", "CETAK_LATAR_PETUNJUK", ".petunjuk", "background")),
)

PERMUKAAN = MappingProxyType({
    "dasar": _DASAR,
    "profil": _PROFIL,
    "murid": _MURID,
    "tinjauan": _TINJAUAN,
    "admin_cerah": _permukaan_admin("CERAH"),
    "admin_gelap": _permukaan_admin("GELAP"),
    "cetak": _CETAK,
})

# Pasangan yang diketahui gagal kontras dan sengaja ditunda, dengan alasannya.
# Kunci: (permukaan, peran depan, peran belakang). Test menuntut daftar ini sama
# persis dengan kegagalan nyata, jadi perbaikan wajib menghapus entrinya.
PENGECUALIAN = MappingProxyType({})


# Aturan yang sah memakai aksen terang (AKSEN_MURID_*/STATUS_*) sebagai warna teks
# atau latar teks putih. Kunci: (modul, konstanta, daftar selektor). Test memindai
# semua CSS dan menuntut temuan sama persis dengan daftar ini.
AKSEN_TERANG_DIIZINKAN = MappingProxyType({
    ("competitive_research", "GAYA_RISET", ".riset-keputusan .riset-alis"): "amber di atas latar navy TEKS_JUDUL",
    ("competitive_research", "GAYA_RISET", ".riset-keputusan strong"): "amber di atas latar navy TEKS_JUDUL",
    ("style_stitch", "GAYA_STITCH", ".landing-cara-st .landing-nomor-st"): "amber di atas latar navy TEKS_JUDUL",
    ("style_stitch", "GAYA_STITCH", ".landing-cara-st li::before"): "amber di atas latar navy TEKS_JUDUL",
    ("style_stitch", "GAYA_STITCH", ".kerja-jawab-st .head-jawab .material-symbols-outlined"): "ikon dekoratif, makna di teks",
    ("style_stitch", "GAYA_STITCH", ".kerja-foto-kepala-st .material-symbols-outlined"): "ikon dekoratif, makna di teks",
    ("style_stitch", "GAYA_STITCH", ".hasil-langkah-st .material-symbols-outlined"): "ikon dekoratif, makna di teks",
    ("style_stitch", "GAYA_STITCH", ".rumus-kepala-st .material-symbols-outlined"): "ikon dekoratif, makna di teks",
    ("style_stitch", "CSS_SESI", ".status-sesi-st .material-symbols-outlined, .status-sesi-st .ikon-status-sesi-st"):
        "ikon status dekoratif, status berteks",
    ("teacher_style", "GAYA_GURU", ".ikon-kartu"): "glyph ikon putih di teal terang: grafis 3,1:1",
    ("screen_style", "GAYA_LAYAR", ".nomor"): "lembar dibekukan gate rilis; tertimpa .lembar-editorial .nomor",
    ("screen_style", "GAYA_LAYAR", ".bintang"): "lembar dibekukan gate rilis",
})


def _kanal(hex_warna: str) -> Tuple[float, float, float]:
    h = hex_warna.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"warna harus #rgb/#rrggbb: {hex_warna!r}")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminansi(hex_warna: str) -> float:
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
               for c in _kanal(hex_warna))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rasio_kontras(a: str, b: str) -> float:
    """Rasio kontras WCAG 2.x berdasarkan luminansi relatif sRGB."""
    terang, gelap = sorted((_luminansi(a), _luminansi(b)), reverse=True)
    return (terang + 0.05) / (gelap + 0.05)


def nilai(sisi: Sisi, ns=T) -> str:
    return getattr(ns, sisi.token)


def peta_peran(permukaan: str) -> Dict[str, str]:
    """Peran → nama token untuk satu permukaan; peran ganda harus satu token."""
    peta: Dict[str, str] = {}
    for p in PERMUKAAN[permukaan]:
        for s in (p.depan, p.belakang):
            if peta.setdefault(s.peran, s.token) != s.token:
                raise ValueError(f"{permukaan}.{s.peran}: {peta[s.peran]} vs {s.token}")
    return peta


def kegagalan(ns=T) -> Dict[Tuple[str, str, str], float]:
    """Pasangan di bawah minimum → rasio terukurnya."""
    gagal = {}
    for nama, daftar in PERMUKAAN.items():
        for p in daftar:
            r = rasio_kontras(nilai(p.depan, ns), nilai(p.belakang, ns))
            if r < p.minimum:
                gagal[(nama, p.depan.peran, p.belakang.peran)] = r
    return gagal
