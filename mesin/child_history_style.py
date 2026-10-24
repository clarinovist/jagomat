"""CSS tab Riwayat halaman anak: baris sesi satu lapis, chip status, filter satu baris."""
import design_tokens as T
from child_badge_style import css_badge_review

_R = ".bungkus-st.profil-workspace-st"
_DESKTOP = "min-width: 48.0625rem"  # di atas BATAS_TABLET; tata letak HP lama tetap berlaku di bawahnya

BADGE = css_badge_review(f"{_R} .riwayat-ringkas-st .riwayat-status-st")

GAYA_RIWAYAT = f"""
{_R} .riwayat-perhatian-st {{
  background: {T.ANAK_PERHATIAN_LATAR}; color: {T.ANAK_PERHATIAN_TEKS}; border-radius: 14px; padding: {T.SP_4} 1.25rem;
}}
{_R} .riwayat-perhatian-st p {{ font-size: 1rem; }}
{_R} .anak-tombol-st {{
  display: inline-flex; align-items: center; justify-content: center; min-height: {T.TARGET_SENTUH};
  padding: 0 1.25rem; border-radius: {T.RADIUS_SEDANG}; background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH};
  font-weight: 700; text-decoration: none; line-height: 1.2;
}}
{_R} .anak-tombol-st:hover {{ background: {T.ANAK_AKSEN_HOVER}; color: {T.TEKS_PUTIH}; text-decoration: none; }}
{_R} .anak-filterbar-st {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_3}; margin-bottom: {T.SP_4}; }}
{_R} .anak-filterbar-st .kepala-riwayat-st {{ flex: 1 1 auto; margin: 0; text-align: left; }}
{_R} .anak-filterbar-st .kepala-riwayat-st h2.st {{ font-size: 1.25rem; font-weight: 800; text-align: left; }}
{_R} .anak-filterbar-st .riwayat-pilbar-st {{ margin: 0; }}
{_R} .anak-filterbar-st .profil-saring-st {{ margin: 0; }}
{_R} .anak-filterbar-st .profil-saring-st > summary {{
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ANAK_AKSEN}; line-height: {T.TARGET_SENTUH};
}}
{_R} .anak-filterbar-st .profil-saring-st[open] {{ flex: 1 1 100%; order: 9; }}
{_R} .riwayat-grup-judul-st {{ color: {T.ANAK_TEKS}; }}
{_R} .riwayat-ringkas-st .riwayat-kartu-kepala-st small {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_BANTUAN}; }}
{BADGE}@media ({_DESKTOP}) {{
  {_R} .riwayat-ringkas-st .riwayat-kartu-st {{
    grid-template-columns: 3.5rem minmax(0, 1fr) auto auto; gap: {T.SP_4}; padding: .75rem 1.25rem;
    border-color: {T.ANAK_BORDER}; border-radius: 14px;
  }}
  {_R} .riwayat-ringkas-st .riwayat-aksi-st {{ grid-area: auto; }}
  {_R} .riwayat-ringkas-st .riwayat-status-st {{ display: flex; justify-content: flex-end; }}
  {_R} .riwayat-ringkas-st .riwayat-tanggal-blok-st {{ justify-content: center; text-align: center; }}
  {_R} .riwayat-ringkas-st .riwayat-tanggal-blok-st span {{ font-size: .8125rem; color: {T.ANAK_TEKS_BANTUAN}; }}
  {_R} .riwayat-ringkas-st .riwayat-kartu-kepala-st strong {{ font-size: 1.0625rem; color: {T.ANAK_TEKS}; }}
}}
@media (max-width: 48rem) {{
  {_R} .riwayat-ringkas-st .riwayat-tanggal-blok-st {{ grid-column: 1; grid-row: 1; }}
  {_R} .riwayat-ringkas-st .riwayat-kartu-kepala-st {{ grid-column: 2; grid-row: 1; }}
  {_R} .riwayat-ringkas-st .riwayat-status-st {{ grid-column: 2; grid-row: 2; }}
  {_R} .riwayat-ringkas-st .riwayat-aksi-st {{ grid-column: 2; grid-row: 3; }}
}}
{_R} .riwayat-ringkas-st .riwayat-buka-st {{
  min-width: 3.5rem; justify-content: center; text-align: center; text-decoration: none;
  color: {T.ANAK_AKSEN}; font-weight: 700;
}}
{_R} .riwayat-ringkas-st .riwayat-tinjau-st {{ border: 2px solid {T.ANAK_AKSEN}; border-radius: {T.RADIUS_SEDANG}; padding: 0 1.25rem; }}
{_R} .riwayat-ringkas-st .riwayat-lihat-st {{ border: 0; text-decoration: none; }}
"""
