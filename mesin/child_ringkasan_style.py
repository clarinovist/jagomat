"""CSS tab Perkembangan > Ringkasan: kartu hero, kartu aktivitas, pil periode, banner ke Beranda."""
import design_tokens as T

_R = ".bungkus-st.profil-workspace-st"
_KARTU = f"""
  background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; border-radius: 20px; box-shadow: none;
  display: flex; flex-direction: column; gap: 1.25rem; margin: 0;"""

GAYA_RINGKASAN = f"""
{_R} #progres.laporan-bagian-st {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
{_R} .peta-materi-st.kartu-st {{{_KARTU} padding: {T.SP_6};
}}
{_R} .peta-materi-st.kartu-st > * {{ margin: 0; }}
{_R} .peta-materi-st.kartu-st .peta-angka {{
  font-size: {T.UKURAN_JUDUL_STITCH}; font-weight: 800; letter-spacing: -.02em; line-height: 1.2; color: {T.ANAK_TEKS};
}}
{_R} .peta-materi-st.kartu-st > p {{ font-size: 1rem; color: {T.ANAK_TEKS_REDUP}; }}
{_R} .peta-materi-st .peta-grafik {{ height: 1rem; margin: 0; }}
{_R} .peta-materi-st .peta-legenda {{
  display: flex; flex-wrap: wrap; gap: {T.SP_2} {T.SP_5}; margin: 0; padding: 0; font-size: .9375rem;
}}
{_R} .peta-materi-st .peta-swatch {{ width: .75rem; height: .75rem; border: 0; border-radius: 3px; }}
{_R} .aktivitas-kartu-st {{{_KARTU} padding: 1.75rem {T.SP_6};
}}
{_R} .aktivitas-kartu-st h2 {{ margin: 0; font-size: 1.25rem; font-weight: 800; color: {T.ANAK_TEKS}; }}
{_R} .aktivitas-kartu-st .laporan-catatan {{ margin: 0; font-size: .9375rem; color: {T.ANAK_TEKS_REDUP}; }}
{_R} .aktivitas-kartu-st .laporan-periode-kontrol {{ display: flex; align-items: center; gap: {T.SP_3}; margin: 0; }}
{_R} .aktivitas-kartu-st .laporan-pilihan {{ margin: 0; }}
{_R} .laporan-pilihan a {{
  min-height: {T.TARGET_SENTUH}; padding: 0 1.125rem; border: 1px solid {T.ANAK_BORDER_PIL};
  border-radius: {T.RADIUS_PIL}; background: {T.LATAR_KARTU}; color: {T.ANAK_TEKS_REDUP};
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600;
}}
{_R} .laporan-pilihan a[aria-current="true"] {{
  padding: 0 calc(1.125rem - 1px); border: 2px solid {T.ANAK_AKSEN}; background: {T.ANAK_AKSEN_LATAR};
  color: {T.ANAK_AKSEN_HOVER}; font-weight: 700;
}}
{_R} .laporan-pilih-tanggal {{ margin-left: auto; }}
{_R} .laporan-pilih-tanggal > summary {{
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ANAK_AKSEN};
}}
{_R} .laporan-pilih-tanggal[open] {{ flex-basis: 100%; }}
{_R} .aktivitas-kartu-st .kartu-stat {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: {T.SP_3};
  margin: 0; padding: 0; background: transparent; border: 0; border-radius: 0;
}}
{_R} .aktivitas-kartu-st .laporan-metrik .stat {{
  padding: {T.SP_4} 1.25rem; background: {T.ANAK_ABU_HANGAT}; border: 0; border-radius: 14px; box-shadow: none;
}}
{_R} .aktivitas-kartu-st .laporan-metrik strong {{ font-size: 2rem; font-weight: 800; line-height: 1.1; color: {T.ANAK_TEKS}; }}
{_R} .aktivitas-kartu-st .laporan-metrik span {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
{_R} .aktivitas-kartu-st .rincian-ui-st {{ margin: 0; }}
{_R} .laporan-ke-beranda.anak-banner-st {{
  display: flex; margin: 0; padding: {T.SP_4} 1.25rem; background: {T.ANAK_AKSEN_LATAR};
  border-radius: 14px; color: {T.ANAK_TEKS};
}}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_R} .peta-materi-st.kartu-st {{ padding: 1.25rem; }}
  {_R} .aktivitas-kartu-st {{ padding: 1.25rem; }}
}}
"""
