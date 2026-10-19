"""CSS bersama halaman anak: satu kontainer dan komponen yang dipakai ulang antar tab."""
import design_tokens as T
from child_history_style import GAYA_RIWAYAT
from child_latihan_style import GAYA_LATIHAN
from child_materi_style import GAYA_MATERI
from child_ringkasan_style import GAYA_RINGKASAN

# Spesifisitas empat kelas agar menang atas aturan lebar lama per tab
# (beranda 60rem, laporan 60rem/75rem, profil 75rem) tanpa menambal satu per satu.
_KONTAINER = ".bungkus-st.pendamping-editorial-st.profil-editorial-st.profil-workspace-st"

GAYA_ANAK = f"""
{_KONTAINER} {{
  width: 100%; max-width: calc({T.ANAK_LEBAR} + 2 * {T.ANAK_GUTTER}); margin-inline: auto;
  padding-inline: {T.ANAK_GUTTER}; box-sizing: border-box;
}}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_KONTAINER} {{ padding-inline: {T.SP_4}; }}
}}
.anak-chip-st {{
  display: inline-flex; align-items: center; gap: {T.SP_1}; width: fit-content; flex: none;
  border-radius: {T.RADIUS_PIL}; padding: {T.SP_1} {T.SP_3}; font-size: .8125rem; font-weight: 700;
  line-height: 1.4; white-space: nowrap;
}}
.anak-chip-perhatian-st {{ background: {T.ANAK_PERHATIAN_LATAR}; color: {T.ANAK_PERHATIAN_TEKS}; }}
.anak-chip-baik-st {{ background: {T.ANAK_BAIK_LATAR}; color: {T.ANAK_BAIK_TEKS}; }}
.anak-chip-netral-st {{ background: {T.ANAK_NETRAL_LATAR}; color: {T.ANAK_NETRAL_TEKS}; }}
.anak-chip-info-st {{ background: {T.ANAK_INFO_LATAR}; color: {T.ANAK_INFO_TEKS}; }}
.anak-chip-galat-st {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; }}
.anak-pil-st {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_4};
  border-radius: {T.RADIUS_PIL}; border: 1px solid {T.ANAK_BORDER_PIL}; background: {T.LATAR_KARTU};
  color: {T.ANAK_TEKS_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; text-decoration: none;
}}
.anak-pil-st[aria-current="true"] {{
  border: 2px solid {T.ANAK_AKSEN}; background: {T.ANAK_AKSEN_LATAR}; color: {T.ANAK_AKSEN_HOVER}; font-weight: 700;
}}
.anak-pil-st:hover {{ border-color: {T.ANAK_AKSEN}; }}
.anak-disclosure-st {{ font-size: .9375rem; }}
.anak-disclosure-st > summary {{
  display: list-item; min-height: {T.TARGET_SENTUH}; cursor: pointer; font-weight: 600; color: {T.ANAK_AKSEN};
}}
.anak-disclosure-st > :not(summary) {{ margin: {T.SP_2} 0 0; color: {T.ANAK_TEKS_REDUP}; }}
.anak-banner-st {{
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: {T.SP_2};
  padding: {T.SP_4} 1.25rem; border-radius: 14px; background: {T.ANAK_AKSEN_LATAR};
  color: {T.ANAK_TEKS}; text-decoration: none; font-size: .9375rem;
}}
.anak-banner-st:hover {{ text-decoration: none; }}
.anak-banner-tautan-st {{ font-weight: 700; color: {T.ANAK_AKSEN}; }}
.anak-kartu-sesi-st {{
  display: flex; align-items: center; flex-wrap: wrap; gap: {T.SP_4}; padding: {T.SP_4} 1.25rem;
  background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px;
}}
.anak-kartu-sesi-st > .anak-kartu-tanggal-st {{ width: 3.5rem; text-align: center; line-height: 1.1; }}
.anak-kartu-sesi-st > .anak-kartu-isi-st {{ flex: 1 1 16rem; min-width: 0; display: flex; flex-direction: column; gap: 2px; }}
.anak-kartu-isi-st small {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_BANTUAN}; }}
.anak-kartu-peringatan-st {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ANAK_PERHATIAN_TEKS}; }}
"""

GAYA_ANAK += GAYA_RIWAYAT + GAYA_MATERI + GAYA_RINGKASAN + GAYA_LATIHAN
