"""Komponen panel privat; token scoped, tanpa aset jaringan atau JavaScript."""
import design_tokens as T
from form_style import GAYA_SELECT

GAYA_ADMIN = f"""
{GAYA_SELECT}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body.admin-readonly {{ margin: 0; background: {T.ADMIN_LATAR}; color: {T.ADMIN_TEKS}; font-family: {T.FONT_BODY}; font-size: {T.ADMIN_UKURAN_ISI}; line-height: 1.6; }}
a {{ color: {T.ADMIN_AKSEN}; text-underline-offset: .2em; }}
a:hover {{ text-decoration: underline; }}
button, input, select, textarea {{ font: inherit; }}
button, summary {{ cursor: pointer; }}
:focus-visible {{ outline: 3px solid {T.ADMIN_AKSEN}; outline-offset: 3px; }}
.admin-lompat {{ position: absolute; left: 16px; top: -10rem; z-index: 30; padding: 12px 16px; background: {T.ADMIN_AKSEN_TEKS}; color: {T.ADMIN_PERMUKAAN}; border-radius: 10px; }}
.admin-lompat:focus {{ top: 16px; }}
.admin-bungkus {{ width: 100%; min-height: 100vh; }}
.admin-layout {{ display: grid; grid-template-columns: {T.ADMIN_SIDEBAR} minmax(0,1fr); min-height: 100vh; }}
.admin-sidebar {{ position: sticky; top: 0; height: 100vh; overflow-y: auto; padding: 20px 16px; background: {T.ADMIN_PERMUKAAN}; border-right: 1px solid {T.ADMIN_BORDER}; }}
.admin-brand {{ display: flex; gap: 12px; align-items: center; padding: 0 4px 24px; color: {T.ADMIN_TEKS}; text-decoration: none; }}
.admin-brand strong {{ display: block; font-size: 16px; }}
.admin-brand small {{ display: block; color: {T.ADMIN_REDUP}; font-size: 13px; }}
.admin-brand-mark {{ display: grid; place-items: center; width: 40px; height: 40px; flex: none; border-radius: 12px; background: {T.ADMIN_AKSEN}; color: {T.ADMIN_PERMUKAAN}; font-weight: 700; font-size: 18px; }}
.admin-nav-daftar, .admin-nav-pilihan, .admin-nav-anak {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }}
.admin-nav-daftar {{ gap: 18px; }}
.admin-nav-label {{ margin: 0; padding: 0 12px 6px; color: {T.ADMIN_REDUP}; font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }}
.admin-menu a {{ display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 12px; border-radius: {T.ADMIN_RADIUS_KONTROL}; color: {T.ADMIN_TEKS}; text-decoration: none; font-weight: 500; }}
.admin-menu a:hover {{ background: {T.ADMIN_NAV_HOVER}; }}
.admin-menu a[aria-current="page"] {{ color: {T.ADMIN_AKSEN_TEKS}; background: {T.ADMIN_AKSEN_LATAR}; font-weight: 600; }}
.admin-utama {{ min-width: 0; width: 100%; max-width: 100rem; margin: 0 auto; padding: 28px 40px 48px; }}
.admin-topbar {{ display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-bottom: 16px; }}
.menu-pengguna {{ position: relative; min-width: 0; }}
.menu-pengguna summary {{ min-height: 44px; padding: 8px 12px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 10px; overflow-wrap: anywhere; }}
.menu-pengguna .menu-isi {{ position: absolute; right: 0; z-index: 20; width: 190px; padding: 12px; border: 1px solid {T.ADMIN_BORDER}; background: {T.ADMIN_PERMUKAAN}; border-radius: 12px; }}
.menu-isi a, .menu-isi button {{ display: flex; align-items: center; min-height: 44px; padding: 8px 12px; width: 100%; }}
.menu-isi button {{ border: 1px solid {T.ADMIN_BORDER_KUAT}; background: {T.ADMIN_PERMUKAAN}; border-radius: 10px; }}
.admin-nav-mobile {{ display: none; }}
.admin-nav-mobile > summary {{ min-height: 44px; padding: 8px 12px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: 10px; background: {T.ADMIN_PERMUKAAN}; }}
.admin-nav-mobile > summary span {{ color: {T.ADMIN_REDUP}; margin-right: 8px; }}
.admin-nav-mobile > nav {{ position: absolute; left: 0; z-index: 10; width: min(28rem, calc(100vw - 32px)); margin-top: 8px; padding: 20px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; background: {T.ADMIN_PERMUKAAN}; max-height: calc(100vh - 8rem); max-height: calc(100dvh - 8rem); overflow-y: auto; overscroll-behavior: contain; }}
.admin-kepala {{ margin-bottom: 28px; }}
.admin-utama h1, .admin-utama h2, .admin-utama h3 {{ font-family: {T.FONT_HEADLINE}; line-height: 1.3; color: {T.ADMIN_TEKS}; }}
.admin-kepala h1 {{ margin: 0 0 6px; font-size: {T.ADMIN_UKURAN_JUDUL}; font-weight: 700; letter-spacing: -.01em; }}
.admin-sub {{ margin: 0; color: {T.ADMIN_REDUP}; }}
.admin-utama main {{ min-width: 0; overflow-wrap: anywhere; }}
.admin-kartu, .admin-stat {{ background: {T.ADMIN_PERMUKAAN}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.ADMIN_RADIUS}; padding: 24px; min-width: 0; }}
.admin-kartu {{ margin-bottom: 24px; }}
.admin-kartu h2 {{ font-size: 18px; margin: 0 0 16px; }}
.admin-kartu h3 {{ font-size: 15px; margin: 0 0 12px; }}
.admin-meta, .admin-sub, .sub {{ color: {T.ADMIN_REDUP}; }}
.admin-meta, .admin-footer, .admin-kartu small {{ font-size: 13px; }}
.admin-footer {{ margin-top: 28px; color: {T.ADMIN_REDUP}; }}
.admin-catatan, .admin-banner {{ background: {T.ADMIN_BANNER_LATAR}; border-color: {T.ADMIN_BANNER_BORDER}; color: {T.ADMIN_BANNER_TEKS}; }}
.admin-galat, .pesan.galat {{ background: {T.ADMIN_BAHAYA_LATAR}; border: 1px solid {T.ADMIN_BAHAYA_BORDER}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.pesan {{ padding: 16px 20px; border: 1px solid {T.ADMIN_AKSEN_BORDER}; background: {T.ADMIN_AKSEN_LATAR}; border-radius: 12px; margin-bottom: 24px; }}
.admin-tombol, .admin-tautan, .admin-chip, .admin-antrean-cta, .admin-pager button {{ min-height: 44px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 16px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.ADMIN_RADIUS_KONTROL}; text-decoration: none; font-size: 14px; font-weight: 600; cursor: pointer; }}
.admin-tombol {{ background: {T.ADMIN_AKSEN}; border-color: {T.ADMIN_AKSEN}; color: {T.ADMIN_PERMUKAAN}; }}
.admin-tombol:hover {{ background: {T.ADMIN_AKSEN_TEKS}; color: {T.ADMIN_PERMUKAAN}; text-decoration: none; }}
.admin-tautan, .admin-tombol-sekunder, .admin-antrean-cta, .admin-pager button {{ background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-tautan:hover, .admin-chip:hover, .admin-antrean-cta:hover {{ background: {T.ADMIN_NAV_HOVER}; text-decoration: none; }}
.admin-bahaya {{ background: {T.ADMIN_BAHAYA_TOMBOL}; border-color: {T.ADMIN_BAHAYA_TOMBOL}; color: {T.ADMIN_PERMUKAAN}; }}
.admin-tautan.admin-bahaya:hover, .admin-tombol.admin-bahaya:hover {{ background: {T.ADMIN_BAHAYA_TEKS}; border-color: {T.ADMIN_BAHAYA_TEKS}; color: {T.ADMIN_PERMUKAAN}; }}
.admin-chip-baris, .admin-aksi-baca, .riset-aksi-atas {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }}
.admin-chip {{ border-radius: 999px; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-chip[aria-current="true"] {{ background: {T.ADMIN_AKSEN_LATAR}; border-color: {T.ADMIN_AKSEN_BORDER}; color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; margin: 2px 4px 2px 0; border-radius: 999px; font-size: 13px; font-weight: 600; color: {T.ADMIN_NETRAL_TEKS}; background: {T.ADMIN_NETRAL_LATAR}; }}
.admin-badge::before {{ content: '•'; }}
.admin-badge.perhatian {{ color: {T.ADMIN_PERHATIAN_TEKS}; background: {T.ADMIN_PERHATIAN_LATAR}; }}
.admin-badge.batal {{ color: {T.ADMIN_BAHAYA_TEKS}; background: {T.ADMIN_BAHAYA_LATAR}; }}
.admin-badge.bien {{ color: {T.ADMIN_BAIK_TEKS}; background: {T.ADMIN_BAIK_LATAR}; }}
.admin-form-cari, .admin-filtre-periode {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: end; }}
.admin-form-cari > label {{ flex: 1 1 160px; }}
.admin-form-cari > label:first-of-type {{ flex-basis: 260px; }}
.admin-kartu label, .admin-filtre-periode label {{ display: block; margin: 12px 0; font-size: 14px; }}
.admin-kartu input:not([type=hidden]):not([type=checkbox]):not([type=radio]), .admin-kartu select, .admin-kartu textarea, .admin-filtre-periode input {{ display: block; width: 100%; min-height: 44px; margin-top: 6px; padding: 10px 12px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: 10px; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-kartu textarea {{ resize: vertical; min-height: 7rem; }}
.admin-kartu fieldset {{ min-width: 0; margin: 16px 0; padding: 16px 20px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; }}
.admin-kartu legend {{ padding: 0 8px; font-weight: 600; }}
.admin-kartu fieldset.admin-galat {{ border-color: {T.ADMIN_BAHAYA_BORDER}; }}
::placeholder {{ color: {T.ADMIN_REDUP}; opacity: 1; }}
.admin-kartu input[type=checkbox], .admin-kartu input[type=radio] {{ width: 20px; height: 20px; vertical-align: middle; margin-right: 8px; accent-color: {T.ADMIN_AKSEN}; }}
.admin-kartu label:has(input[type=checkbox]), .admin-kartu label:has(input[type=radio]) {{ min-height: 44px; padding: 10px 12px; background: {T.ADMIN_BANNER_LATAR}; border-radius: 10px; }}
.admin-kartu button:not(.tombol-mata) {{ min-height: 44px; }}
.admin-kartu form + form, .admin-form-tindakan form + form {{ margin-top: 24px; }}
.admin-form-cari details {{ flex: 1 1 100%; }}
.admin-form-cari details > div {{ display: flex; flex-wrap: wrap; gap: 16px; }}
.admin-form-cari details label {{ flex: 1 1 160px; }}
summary {{ min-height: 44px; padding: 10px 0; font-weight: 600; }}
.kolom-sandi {{ display: block; position: relative; min-width: 0; }}
.kolom-sandi > input {{ padding-right: 52px !important; }}
.tombol-mata {{ position: absolute; right: 3px; top: 50%; transform: translateY(-50%); width: 44px; height: 44px; padding: 0; display: grid; place-items: center; border: 0; border-radius: 10px; background: transparent; color: {T.ADMIN_REDUP}; }}
.admin-tabel-wrap {{ overflow-x: auto; max-width: 100%; }}
.admin-tabel {{ width: 100%; border-collapse: collapse; min-width: 42rem; }}
.admin-tabel th, .admin-tabel td {{ overflow-wrap: normal; word-break: normal; padding: 14px 16px; border-bottom: 1px solid {T.ADMIN_PEMISAH}; text-align: left; vertical-align: top; }}
.admin-tabel th {{ font-size: 13px; font-weight: 600; color: {T.ADMIN_REDUP}; background: {T.ADMIN_LATAR}; white-space: nowrap; }}
.admin-tabel tbody tr:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-tabel td[data-angka], .admin-tabel th[data-angka] {{ text-align: right; font-variant-numeric: tabular-nums; }}
.admin-tabel td:last-child a {{ display: inline-flex; min-height: 44px; align-items: center; }}
.admin-kosong {{ color: {T.ADMIN_REDUP}; padding: 24px; text-align: center; }}
.admin-pager {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; margin-top: 20px; }}
.admin-pager form {{ margin: 0; }}
.admin-rincian {{ display: grid; grid-template-columns: 11rem minmax(0,1fr); gap: 8px 16px; }}
.admin-rincian dt {{ font-weight: 600; color: {T.ADMIN_REDUP}; }}
.admin-rincian dd {{ margin: 0; overflow-wrap: anywhere; }}
.admin-grid-stat {{ display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 16px; margin-bottom: 24px; }}
.admin-stat h2 {{ font-size: 14px; font-weight: 500; margin: 0 0 8px; color: {T.ADMIN_REDUP}; }}
.admin-stat > div {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }}
.admin-stat strong {{ font-size: 28px; line-height: 1.2; font-variant-numeric: tabular-nums; }}
.admin-stat span {{ font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-komando {{ display: grid; gap: 0; }}
.admin-kartu.admin-prioritas {{ padding: 0; background: {T.ADMIN_PERMUKAAN}; }}
.admin-prioritas-kepala {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 24px; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-kartu.admin-prioritas h2 {{ margin: 0; font-size: 18px; }}
.admin-alis {{ margin: 0 0 4px; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-total-temuan {{ margin: 0; font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-total-temuan strong {{ font-size: {T.ADMIN_UKURAN_TOTAL}; color: {T.ADMIN_TEKS}; }}
.admin-antrean {{ list-style: none; margin: 0; padding: 0; }}
.admin-antrean-item {{ display: grid; grid-template-columns: 130px minmax(0,1fr) auto; gap: 8px 20px; padding: 20px 24px; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-antrean-urutan {{ grid-row: 1 / 5; font-size: 13px; color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-antrean-urutan strong {{ display: block; font-size: 20px; }}
.admin-prioritas .admin-antrean-item h3 {{ grid-column: 2; margin: 0; font-size: 15px; }}
.admin-antrean-item p, .admin-antrean-rincian {{ grid-column: 2; margin: 0; color: {T.ADMIN_REDUP}; font-size: 14px; }}
.admin-antrean-rincian {{ padding-left: 18px; }}
.admin-antrean-cta {{ grid-column: 3; grid-row: 1 / 5; align-self: center; }}
.admin-antrean-rincian a {{ display: inline-flex; min-height: 44px; align-items: center; }}
.admin-antrean-catatan, .admin-antrean-kosong {{ margin: 0; padding: 16px 24px; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-layanan dl {{ display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 16px; margin: 0; }}
.admin-layanan dl > div {{ padding: 16px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; min-width: 0; }}
.admin-layanan dt {{ color: {T.ADMIN_REDUP}; font-size: 14px; }}
.admin-layanan dd {{ margin: 8px 0 0; font-weight: 600; }}
.admin-layanan-cta {{ display: inline-flex; min-height: 44px; align-items: center; font-weight: 600; }}
.admin-pendukung, .admin-dua-kolom {{ display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 24px; align-items: start; }}
.admin-pendukung .admin-grid-stat {{ grid-template-columns: repeat(2,minmax(0,1fr)); }}
.admin-aktivitas header {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; }}
.admin-aktivitas ul, .admin-login-detail ul {{ list-style: none; padding: 0; margin: 0; }}
.admin-aktivitas li, .admin-login-detail li {{ padding: 14px 0; border-top: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-aktivitas p {{ margin: 4px 0; }}
.admin-aktivitas-judul {{ font-size: 15px; font-weight: 600; }}
.admin-aktivitas-ikon {{ display: none; }}
.admin-cepat nav {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.admin-cepat a {{ display: grid; gap: 6px; padding: 12px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 10px; }}
.admin-login-detail span {{ display: block; color: {T.ADMIN_REDUP}; }}
.admin-grid-kpi {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,250px),1fr)); gap: 24px; margin-top: 24px; }}
.admin-kpi-carte header {{ display: flex; justify-content: space-between; gap: 8px; align-items: start; }}
.admin-kpi-carte header h2 {{ margin-bottom: 8px; }}
.admin-info {{ display: inline-block; font-size: 14px; font-weight: normal; }}
.admin-info summary {{ min-width: 44px; display: grid; place-items: center; }}
.admin-info p {{ max-width: 22rem; }}
.admin-angka {{ font-size: {T.ADMIN_UKURAN_KPI}; font-variant-numeric: tabular-nums; }}
.admin-kpi-biaya {{ grid-column: 1 / -1; }}
.admin-bilah {{ height: 12px; margin: 16px 0; border-radius: 999px; background: {T.ADMIN_NETRAL_LATAR}; position: relative; }}
.admin-bilah span {{ display: block; height: 100%; border-radius: inherit; background: {T.ADMIN_AKSEN}; }}
.admin-bilah i {{ position: absolute; top: -3px; height: 18px; width: 2px; background: {T.ADMIN_TEKS}; }}
.admin-stepper {{ display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 12px; padding: 0; list-style: none; }}
.admin-stepper li {{ padding: 12px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; }}
.admin-stepper [aria-current="step"] {{ border: 2px solid {T.ADMIN_AKSEN}; background: {T.ADMIN_AKSEN_LATAR}; font-weight: 600; }}
.admin-id {{ overflow-wrap: anywhere; user-select: all; }}
.riset-grid-form {{ display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 16px; }}
.admin-dua-kolom .riset-grid-form {{ grid-template-columns: 1fr; }}
.riset-aksi-atas form {{ margin: 0; }}
.riset-prompt {{ max-width: 50rem; font-size: 18px; font-weight: 600; }}
.riset-kode-baris {{ display: grid; grid-template-columns: 8rem 9rem minmax(0,1fr); gap: 8px; align-items: center; }}
.riset-tombol, .riset-aksi-form {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-top: 16px; }}
.riset-aksi-form form {{ flex: 1 1 15rem; }}
.riset-daftar-pertanyaan, .riset-daftar-sesi {{ list-style: none; margin: 0; padding: 0; }}
.riset-daftar-pertanyaan li, .riset-sesi {{ padding: 14px; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.riset-daftar-pertanyaan li, .riset-daftar-pertanyaan li > div, .riset-sesi-kepala {{ display: flex; justify-content: space-between; align-items: start; gap: 12px; }}
.riset-sesi {{ display: block; text-decoration: none; }}
.riset-sesi-meta {{ display: block; color: {T.ADMIN_REDUP}; font-size: 13px; }}
.riset-nomor {{ min-width: 28px; font-weight: 600; }}
.riset-matriks {{ min-width: 80rem; }}
.riset-matriks q {{ display: block; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.riset-grid-ringkas {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,16rem),1fr)); gap: 16px; }}
.sensor-tabel {{ min-width: 50rem; }}
@media (max-width: 70rem) {{
  .admin-utama {{ padding-left: 24px; padding-right: 24px; }}
  .admin-layanan dl, .admin-grid-stat {{ grid-template-columns: repeat(2,minmax(0,1fr)); }}
  .admin-pendukung, .admin-dua-kolom {{ grid-template-columns: 1fr; }}
  .admin-antrean-item {{ grid-template-columns: 100px minmax(0,1fr); }}
  .admin-antrean-cta {{ grid-column: 2; grid-row: auto; justify-self: start; }}
}}
@media (max-width: 51.25rem) {{
  .admin-layout {{ display: block; }}
  .admin-sidebar {{ display: none; }}
  .admin-topbar {{ justify-content: space-between; align-items: start; }}
  .admin-nav-mobile {{ display: block; position: relative; min-width: 0; }}
  .menu-pengguna {{ max-width: 45%; }}
  .menu-pengguna .admin-badge {{ display: none; }}
  .admin-nav-mobile .admin-nav-daftar {{ grid-template-columns: 1fr 1fr; }}
  .admin-nav-utama {{ grid-column: 1 / -1; }}
}}
@media (max-width: 32rem) {{
  .admin-utama {{ padding: 16px; }}
  .admin-kartu {{ padding: 20px; }}
  .admin-kepala {{ margin: 20px 0; }}
  .admin-nav-mobile > summary {{ display: flex; flex-wrap: wrap; }}
  .admin-nav-mobile .admin-nav-daftar, .admin-rincian, .riset-grid-form {{ grid-template-columns: 1fr; }}
  .admin-rincian dd {{ margin-bottom: 12px; }}
  .admin-layanan dl {{ grid-template-columns: 1fr; }}
  .admin-antrean-item {{ display: flex; flex-direction: column; padding: 20px; }}
  .admin-antrean-urutan {{ display: flex; gap: 12px; align-items: center; }}
  .admin-antrean-cta {{ align-self: start; }}
  .admin-grid-stat {{ gap: 12px; }}
  .admin-stat {{ padding: 16px; }}
  .admin-stepper {{ grid-template-columns: 1fr 1fr; }}
  .riset-kode-baris {{ grid-template-columns: 1fr 1fr; }}
  .riset-kode-baris span {{ grid-column: 1 / -1; }}
  .riset-aksi-atas {{ display: grid; }}
  .riset-aksi-atas .admin-tautan {{ width: 100%; }}
}}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto; animation: none; transition: none; }} }}
@media print {{ .admin-sidebar, .admin-topbar, .admin-form-cari, .admin-pager {{ display: none; }} .admin-layout {{ display: block; }} }}
"""
