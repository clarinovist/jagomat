"""CSS tab Beranda: kartu tugas utama, peta tahap satu baris judul, sesi lain, banner Perkembangan."""
import design_tokens as T
from child_badge_style import css_badge_review

_R = ".bungkus-st.profil-workspace-st.beranda-profil-st"
_DESKTOP = f"min-width: calc({T.ANAK_BATAS_HP} + .0625rem)"

BADGE = css_badge_review(f"{_R} .beranda-sesi-st")

GAYA_BERANDA = f"""
{_R} .kartu-rencana-st {{
  gap: 1.25rem; border: 1px solid {T.ANAK_BORDER}; border-radius: 20px; background: {T.LATAR_KARTU}; box-shadow: none;
}}
{_R} .kartu-rencana-st > form[action="/pendamping/inline/buka"] {{ display: contents; }}
{_R} .kartu-rencana-st > .batas-rencana-st {{ margin: 0; }}
{_R} .beranda-kepala-kartu-st {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: {T.SP_2}; }}
{_R} .label-rencana-st {{
  margin: 0; font-size: .8125rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: {T.ANAK_AKSEN};
}}
{_R} #judul-rencana-belajar {{ font-size: 1.75rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.2; color: {T.ANAK_TEKS}; }}
{_R} :is(.beranda-meta-st, .identitas-sesi-rencana-st) {{ font-size: .9375rem; color: {T.ANAK_TEKS_BANTUAN}; }}
{_R} .beranda-caranya-st {{ padding: 1.25rem {T.SP_5}; border-radius: 14px; background: {T.ANAK_ABU_HANGAT}; }}
{_R} .beranda-caranya-st p {{ margin: 6px 0 0; font-size: 1.0625rem; color: {T.ANAK_TEKS}; }}
{_R} .beranda-aksi-st .rencana-cta-utama-st {{
  min-height: 3rem; padding: .875rem 1.75rem; border-radius: 12px; background: {T.ANAK_AKSEN};
  border-color: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}; font-size: 1.0625rem; font-weight: 700;
}}
{_R} .beranda-aksi-st .rencana-cta-utama-st:hover {{ background: {T.ANAK_AKSEN_HOVER}; border-color: {T.ANAK_AKSEN_HOVER}; }}
{_R} .petunjuk-sesudah-cta-st {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_BANTUAN}; }}
{_R} .beranda-posisi-kepala-st {{
  display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: {T.SP_2}; margin: 0 0 {T.SP_4};
}}
{_R} .beranda-posisi-kepala-st h2 {{ margin: 0; font-size: 1.125rem; font-weight: 800; color: {T.ANAK_TEKS}; }}
{_R} .beranda-posisi-kepala-st p {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_BANTUAN}; }}
{_R} .beranda-posisi-st .tahap-rencana-st::before {{ background: {T.ANAK_STATUS_BELUM}; }}
{_R} .beranda-posisi-st .tahap-rencana-st.aktif::before {{ background: {T.ANAK_AKSEN}; }}
{_R} .beranda-posisi-st .tahap-rencana-st.aktif {{ color: {T.ANAK_AKSEN}; font-weight: 800; }}
{_R} .beranda-posisi-st .alur-rencana-jelas-st {{ margin: 0; padding: 0; border: 0; }}
{_R} .beranda-posisi-st .alur-rencana-jelas-st > summary {{ font-size: .9375rem; font-weight: 600; color: {T.ANAK_AKSEN}; }}
{_R} .profil-taches-st > h2.st {{ margin: 0 0 {T.SP_3}; font-size: 1.125rem; font-weight: 800; color: {T.ANAK_TEKS}; }}
{_R} .beranda-sesi-st {{
  padding: {T.SP_4} 1.25rem; background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px;
}}
{_R} .beranda-sesi-isi-st {{ display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 2px {T.SP_2}; }}
{_R} .beranda-sesi-isi-st > h3 {{ grid-column: 1; margin: 0; font-size: 1rem; font-weight: 700; color: {T.ANAK_TEKS}; }}
{_R} .beranda-sesi-isi-st > .badge-direview {{ grid-column: 2; grid-row: 1; justify-self: start; }}
{_R} .beranda-sesi-isi-st > p {{ grid-column: 1 / -1; margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_BANTUAN}; }}
{_R} .beranda-sesi-isi-st > .beranda-sesi-peringatan-st {{ font-weight: 600; color: {T.ANAK_PERHATIAN_TEKS}; }}
{BADGE}
{_R} .beranda-tinjau-st {{
  min-height: {T.TARGET_SENTUH}; padding: 0 1.25rem; border: 2px solid {T.ANAK_AKSEN}; border-radius: {T.RADIUS_SEDANG};
  color: {T.ANAK_AKSEN}; font-weight: 700;
}}
{_R} .beranda-perkembangan-st.anak-banner-st {{ margin-top: {T.SP_5}; padding: {T.SP_4} 1.25rem; background: {T.ANAK_AKSEN_LATAR}; color: {T.ANAK_TEKS}; }}
@media ({_DESKTOP}) {{
  {_R} .kartu-rencana-st {{ padding: {T.SP_6}; }}
}}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_R} .kartu-rencana-st {{ padding: 1.25rem; }}
}}
"""
