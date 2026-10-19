"""Warna badge status review yang sama di Riwayat dan Beranda (satu sumber, nada chip bersama)."""
import design_tokens as T

_NADA = (
    (".perlu", T.ANAK_PERHATIAN_LATAR, T.ANAK_PERHATIAN_TEKS),
    (":is(.draf, .proses)", T.ANAK_INFO_LATAR, T.ANAK_INFO_TEKS),
    (".sudah", T.ANAK_BAIK_LATAR, T.ANAK_BAIK_TEKS),
    (":is(.belum, .batal)", T.ANAK_NETRAL_LATAR, T.ANAK_NETRAL_TEKS),
)


def css_badge_review(lingkup):
    """Aturan badge-direview di dalam `lingkup` (selektor CSS pembungkus)."""
    dasar = (
        f"{lingkup} .badge-direview {{\n"
        f"  width: fit-content; max-width: 100%; margin: 0; padding: {T.SP_1} {T.SP_3}; border-radius: {T.RADIUS_PIL};\n"
        f"  font-size: .8125rem; font-weight: 700; line-height: 1.4; white-space: nowrap;\n"
        f"  background: {T.ANAK_NETRAL_LATAR}; color: {T.ANAK_NETRAL_TEKS};\n}}\n"
    )
    nada = "".join(
        f"{lingkup} .badge-direview{kelas} {{ background: {latar}; color: {teks}; }}\n"
        for kelas, latar, teks in _NADA
    )
    return dasar + nada
