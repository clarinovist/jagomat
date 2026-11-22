"""Header ringkas khusus halaman anak, tanpa membaca data persisten."""
import html

import design_tokens as T


def nama_akun(pengguna):
    """Format tampilan saja; nama login dan kepemilikan tidak berubah."""
    nama = pengguna.strip()
    if '-' in nama and nama == nama.lower():
        return ' '.join(nama.split('-')).title()
    return nama or 'Menu akun'


def identitas(siswa, *, kelas_sekolah=None, id_judul='judul-profil', kembali=None):
    """Nama dan kelas sebagai sibling, tanpa badge status atau foto tersimpan."""
    from learning_profile import label_kelas_sekolah
    nama = str(siswa['nama'])
    kelas = (
        f'<span class="anak-meta-st">{html.escape(label_kelas_sekolah(kelas_sekolah))}</span>'
        if kelas_sekolah is not None else ''
    )
    tautan = (
        f'<a class="profil-kembali-st" href="{html.escape(kembali, quote=True)}">'
        '<svg aria-hidden="true" focusable="false" width="14" height="14" '
        'viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 3 4.5 7l4 4"/></svg>'
        'Semua anak</a>' if kembali else ''
    )
    return (
        '<header class="kepala-anak-st editorial-kepala-st">'
        '<div class="profil-identitas-st">'
        f'<span class="anak-avatar-st" aria-hidden="true">{html.escape(nama.strip()[:1].upper())}</span>'
        f'<h1 class="st" id="{html.escape(id_judul, quote=True)}">{html.escape(nama)}</h1>'
        f'{kelas}{tautan}</div></header>'
    )


def tombol_pendamping(target, *, status_akses, form_id=''):
    """Pindahkan pemicu existing; form latihan dan draf native tetap terhubung."""
    from assistant_components import hubungkan_form, tombol_buka
    tombol = tombol_buka(target, dalam_form=bool(form_id), label='Tanya', status_akses=status_akses)
    # Label keadaan akses tetap terbaca (tombol_buka menambahkan "Tanya" ke nama aksesibel).
    if form_id:
        tombol = hubungkan_form(tombol, form_id)
    return tombol


# Hanya identitas anak dan tab profil; topbar & pemicu Tanya milik shell bersama (shell_guru_style).
_H = '.bungkus-st.pendamping-editorial-st.profil-workspace-st.anak-header-st'
GAYA_HEADER_ANAK = f"""
{_H} {{ overflow: visible; }}
{_H} > main {{ min-width: 0; overflow: visible; timeline-scope: --anak-identitas; }}
{_H}:has(> .pendamping-panel-kanan:not([hidden])) {{ row-gap: 0; }}
{_H} .kepala-anak-st {{ margin: 0; padding: 0; border: 0; view-timeline: --anak-identitas block; }}
{_H} .profil-identitas-st {{
  display: flex; flex-wrap: nowrap; align-items: center; justify-content: flex-start;
  gap: {T.SP_3}; min-height: 56px; font-family: {T.FONT_BODY};
}}
{_H} .anak-avatar-st {{
  display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 40px; height: 40px; border-radius: {T.RADIUS_BULAT};
  background: {T.ANAK_HEADER_AVATAR_LATAR}; color: {T.ANAK_HEADER_AVATAR_TEKS};
  font: 700 18px/1 {T.FONT_BODY};
}}
{_H} .kepala-anak-st h1 {{
  margin: 0; min-width: 0; font: 700 24px/1.2 {T.FONT_BODY};
  letter-spacing: normal; color: {T.TEKS_JUDUL}; overflow-wrap: anywhere;
}}
{_H} .anak-meta-st {{ font: 400 14px/1.4 {T.FONT_BODY}; color: {T.ANAK_HEADER_META}; white-space: nowrap; }}
{_H} .profil-kembali-st {{
  display: inline-flex; align-items: center; flex: none; margin-left: auto;
  min-height: {T.TARGET_SENTUH}; gap: {T.SP_1};
  font: 600 14px/1.4 {T.FONT_BODY}; color: {T.AKSEN_TEAL_TUA}; white-space: nowrap;
}}
{_H} .profil-kembali-st svg {{ flex: none; }}
{_H} .profil-tabs-st {{
  display: flex; flex-wrap: nowrap; gap: {T.SP_5}; margin: 0 0 {T.SP_5}; padding: 0;
  border: 0; border-bottom: 1px solid {T.ANAK_BORDER}; background: {T.LATAR_MURID};
  overflow-x: auto; position: sticky; top: 0; z-index: 40;
}}
@supports (animation-timeline: --anak-identitas) {{
  @keyframes anak-tab-menempel {{ from {{ box-shadow: none; }} to {{ box-shadow: {T.ANAK_HEADER_BAYANGAN}; }} }}
  {_H} .profil-tabs-st {{
    animation: anak-tab-menempel linear both; animation-timeline: --anak-identitas;
    animation-range: exit 99% exit 100%;
  }}
}}
{_H} .profil-tabs-st a {{
  flex: none; height: {T.TINGGI_KONTROL}; min-height: {T.TINGGI_KONTROL}; padding: 0;
  font: 600 {T.UKURAN_BADAN_LAYAR}/1.4 {T.FONT_BODY}; color: {T.TEKS_VARIAN};
  border-bottom: 3px solid transparent;
}}
{_H} .profil-tabs-st a[aria-current="page"] {{
  font-weight: 700; color: {T.AKSEN_TEAL_TUA}; border-bottom-color: {T.AKSEN_TEAL_TUA};
}}
{_H} :is(.kepala-anak-st, .profil-tabs-st) :is(a, button, summary):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: -3px; border-radius: 4px;
}}
@media (max-width: 36rem) {{
  {_H} .profil-identitas-st {{ gap: 10px; }}
  {_H} .profil-kembali-st {{ padding-left: {T.SP_2}; }}
  {_H} .profil-tabs-st {{
    margin-inline: -1rem; padding-inline: {T.SP_4}; margin-bottom: 20px; gap: 0;
    scroll-padding-inline: {T.SP_4};
  }}
  {_H} .profil-tabs-st a {{ padding-inline: {T.SP_1}; font-size: {T.UKURAN_TEKS_LABEL}; }}
}}
@media (max-width: 24rem) {{
  /* Nama dan kelas bertumpuk pada kolom yang sama; semua teks tetap terbaca. */
  {_H} .profil-identitas-st {{
    display: grid; grid-template-columns: 40px minmax(0, 1fr) auto;
    column-gap: {T.SP_2}; row-gap: 2px; padding-block: {T.SP_1};
  }}
  {_H} .anak-avatar-st {{ grid-column: 1; grid-row: 1 / 3; }}
  {_H} .kepala-anak-st h1 {{ grid-column: 2; grid-row: 1 / 3; align-self: center; }}
  {_H} .profil-identitas-st:has(.anak-meta-st) h1 {{ grid-row: 1; align-self: end; font-size: 20px; }}
  {_H} .anak-meta-st {{ grid-column: 2; grid-row: 2; align-self: start; }}
  {_H} .profil-kembali-st {{ grid-column: 3; grid-row: 1 / 3; padding-left: 0; }}
}}
@media print {{
  {_H} > .st-topbar, {_H} .profil-tabs-st, {_H} .profil-kembali-st {{ display: none; }}
  {_H} {{ padding-bottom: 0; }}
}}
"""
