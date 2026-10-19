"""CSS tab Perkembangan > Per materi: dua panel (daftar materi, kartu target) dan satu disclosure bukti."""
import design_tokens as T

_R = ".bungkus-st.profil-workspace-st"
_DUA_KOLOM = "min-width: 46.0625rem"  # di bawah ini panel menumpuk (aturan peta lama)

GAYA_MATERI = f"""
{_R} .peta-materi-st .peta-ringkas {{ margin: 0 0 {T.SP_4}; }}
{_R} .peta-materi-st .peta-pemilih > h3 {{ margin: 0 0 {T.SP_3}; font-size: 1.25rem; font-weight: 800; color: {T.ANAK_TEKS}; }}
{_R} .peta-materi-st .peta-pilihan {{
  display: flex; flex-direction: column; gap: {T.SP_2}; padding: {T.SP_4} 1.125rem;
  background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px; color: {T.ANAK_TEKS};
}}
{_R} .peta-materi-st .peta-pilihan[aria-current="true"],
{_R} .peta-materi-st .peta-pilihan[data-preview="true"] {{
  background: {T.ANAK_AKSEN_LATAR}; border: 2px solid {T.ANAK_AKSEN}; padding: calc({T.SP_4} - 1px) calc(1.125rem - 1px);
}}
{_R} .peta-materi-st .peta-pilihan-kepala-st {{ display: flex; justify-content: space-between; align-items: baseline; gap: {T.SP_2}; }}
{_R} .peta-materi-st .peta-pilihan b {{ font-size: 1rem; font-weight: 700; color: {T.ANAK_TEKS}; }}
{_R} .peta-materi-st .peta-pilihan small {{ margin: 0; font-size: .8125rem; color: {T.ANAK_TEKS_BANTUAN}; }}
{_R} .peta-materi-st .peta-pilihan .peta-grafik {{ height: .5rem; margin: 0; background: {T.ANAK_STATUS_BELUM}; }}
{_R} .peta-materi-st .peta-grafik rect {{ stroke: none; }}
{_R} .peta-materi-st .peta-detail {{
  display: flex; flex-direction: column; gap: {T.SP_4}; padding: 1.75rem; background: {T.LATAR_KARTU};
  border: 1px solid {T.ANAK_BORDER}; border-radius: 20px; box-shadow: none;
}}
{_R} .peta-materi-st .peta-detail h2 {{ margin: 0; font-size: 1.375rem; font-weight: 800; color: {T.ANAK_TEKS}; }}
{_R} .peta-materi-st .peta-detail > p {{ margin: 0; font-size: .9375rem; color: {T.ANAK_TEKS_REDUP}; }}
{_R} .peta-materi-st .peta-detail .peta-target {{ display: flex; flex-direction: column; }}
{_R} .peta-materi-st .peta-detail .peta-target > li {{ padding: 0; border-top: 1px solid {T.ANAK_BORDER}; }}
{_R} .peta-materi-st .rincian-target-st {{ padding: 0; }}
{_R} .peta-materi-st .rincian-target-st > summary {{
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3};
  min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} 0; list-style: none;
}}
{_R} .peta-materi-st .rincian-target-st > summary::-webkit-details-marker {{ display: none; }}
{_R} .peta-materi-st .rincian-target-st > summary::before {{ content: "\\25B8"; flex: none; color: {T.ANAK_AKSEN}; }}
{_R} .peta-materi-st .rincian-target-st[open] > summary::before {{ transform: rotate(90deg); }}
{_R} .peta-materi-st .rincian-target-st > summary > b {{ flex: 1; margin: 0; font-weight: 600; color: {T.ANAK_TEKS}; }}
{_R} .peta-materi-st .rincian-target-st > :not(summary) {{ margin-left: {T.SP_5}; }}
{_R} .peta-materi-st .bukti-konteks-st {{ padding-top: {T.SP_2}; border-top: 1px solid {T.ANAK_BORDER}; }}
{_R} .peta-materi-st .bukti-konteks-st h3 {{ margin: {T.SP_3} 0 {T.SP_1}; font-size: 1rem; font-weight: 700; color: {T.ANAK_TEKS}; }}
@media ({_DUA_KOLOM}) {{
  {_R} .peta-materi-st .peta-panel {{ grid-template-columns: minmax(16rem, 21.25rem) minmax(0, 1fr); gap: {T.SP_5}; }}
}}
"""
