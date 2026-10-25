"""CSS tab Latihan: satu kartu form, tiga mode berupa kartu pilihan, pengaturan lanjutan tanpa garis."""
import design_tokens as T

_R = ".bungkus-st.profil-workspace-st"
_KARTU_CENTANG = f"""
  display: flex; align-items: center; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; padding: .875rem 1.125rem;
  background: {T.ANAK_LATAR_KARTU_HALUS}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px; cursor: pointer;"""

GAYA_LATIHAN = f"""
{_R} .latihan-terpadu-st {{
  display: flex; flex-direction: column; gap: {T.SP_5}; padding: {T.SP_6};
  border: 1px solid {T.ANAK_BORDER}; border-radius: 20px;
}}
{_R} .latihan-terpadu-st > h2.st {{ margin: 0; font-size: 1.625rem; font-weight: 800; letter-spacing: -.02em; color: {T.ANAK_TEKS}; }}
{_R} .latihan-terpadu-st form {{ display: flex; flex-direction: column; gap: {T.SP_5}; margin: 0; }}
{_R} .latihan-terpadu-st fieldset {{ margin: 0; }}
{_R} .latihan-terpadu-st fieldset[data-mode-latihan] > legend {{
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip-path: inset(50%);
}}
{_R} .latihan-pemilih-st legend {{ margin-bottom: 10px; padding: 0; font-size: .9375rem; font-weight: 700; color: {T.ANAK_TEKS}; }}
{_R} .latihan-mode-st label {{
  gap: {T.SP_3}; padding: {T.SP_4} 1.125rem; background: {T.LATAR_KARTU};
  border: 1px solid {T.ANAK_BORDER_PIL}; border-radius: 14px;
}}
{_R} .latihan-mode-st label:has(:checked) {{
  padding: calc({T.SP_4} - 1px) calc(1.125rem - 1px); background: {T.ANAK_AKSEN_LATAR}; border: 2px solid {T.ANAK_AKSEN};
}}
{_R} .latihan-mode-st b {{ font-size: 1rem; color: {T.ANAK_TEKS}; }}
{_R} .latihan-terpadu-st small {{ color: {T.ANAK_TEKS_REDUP}; }}
{_R} .latihan-terpadu-st input:is([type=radio], [type=checkbox]) {{ accent-color: {T.ANAK_AKSEN}; }}
{_R} .latihan-field-grid label {{ font-size: .9375rem; font-weight: 700; color: {T.ANAK_TEKS}; }}
{_R} .latihan-terpadu-st :is(label[for="gabungan-jumlah"], label[for="remedial-jumlah"]) {{
  display: block; margin-top: {T.SP_4}; font-size: .9375rem; font-weight: 700; color: {T.ANAK_TEKS};
}}
{_R}.pendamping-editorial-st .latihan-terpadu-st select {{
  min-height: {T.TINGGI_KONTROL}; margin: {T.SP_2} 0 {T.SP_1}; padding: 0 {T.SP_3};
  border: 1px solid {T.BORDER_KONTROL}; border-radius: 12px; color: {T.ANAK_TEKS};
}}
{_R} .latihan-topik-grid {{ grid-template-columns: repeat(auto-fit, minmax(min(100%, 16.25rem), 1fr)); gap: {T.SP_3}; }}
{_R} .latihan-topik-grid label {{{_KARTU_CENTANG}
}}
{_R} .daftar-remedial-st .pilihan-remedial-st {{{_KARTU_CENTANG}
  align-items: center;
}}
{_R} .daftar-remedial-st .pilihan-remedial-st:has(input:checked),
{_R} .latihan-topik-grid label:has(input:checked) {{ background: {T.ANAK_AKSEN_LATAR}; border-color: {T.ANAK_AKSEN}; }}
{_R} .latihan-terpadu-st .atur-latihan-st {{
  margin: {T.SP_3} 0 0; padding: 0; background: transparent; border: 0; border-radius: 0;
}}
{_R} .latihan-terpadu-st .atur-latihan-st summary {{ font-size: .9375rem; font-weight: 600; color: {T.ANAK_AKSEN}; }}
{_R} .latihan-terpadu-st .atur-latihan-st > small {{ display: block; margin: {T.SP_2} 0; }}
{_R} .latihan-aksi-st button {{
  min-height: 3rem; padding: .875rem 1.75rem; border-radius: 12px; background: {T.ANAK_AKSEN};
  color: {T.TEKS_PUTIH}; font-size: 1.0625rem; font-weight: 700;
}}
{_R} .latihan-aksi-st button:hover:not(:disabled) {{ background: {T.ANAK_AKSEN_HOVER}; }}
{_R} .latihan-aksi-st p {{ margin: 0; color: {T.ANAK_TEKS_BANTUAN}; }}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_R} .latihan-terpadu-st {{ padding: {T.SP_4}; }}
}}
"""
