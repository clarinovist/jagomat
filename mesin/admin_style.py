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
.admin-brand {{ display: flex; gap: 12px; align-items: center; padding: 0 4px 20px; line-height: normal; color: {T.ADMIN_TEKS}; text-decoration: none; }}
.admin-brand strong {{ display: block; font-size: 16px; }}
.admin-brand small {{ display: block; color: {T.ADMIN_REDUP}; font-size: 13px; }}
.admin-brand-mark {{ display: grid; place-items: center; width: 40px; height: 40px; flex: none; border-radius: 12px; background: {T.ADMIN_AKSEN}; color: {T.ADMIN_PERMUKAAN}; font-weight: 700; font-size: 18px; }}
.admin-nav-daftar, .admin-nav-pilihan, .admin-nav-anak {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }}
.admin-nav-daftar {{ gap: 18px; }}
.admin-nav-label {{ margin: 0; padding: 0 12px 6px; line-height: normal; color: {T.ADMIN_REDUP}; font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }}
.admin-menu a {{ display: flex; align-items: center; gap: 12px; min-height: 44px; padding: 8px 12px; border-radius: {T.ADMIN_RADIUS_KONTROL}; color: {T.ADMIN_TEKS}; text-decoration: none; font-size: {T.ADMIN_UKURAN_ISI}; font-weight: 500; }}
.admin-menu a svg {{ flex: none; color: {T.ADMIN_REDUP}; }}
.admin-menu a[aria-current="page"] svg {{ color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-nav-label-menu {{ flex: 1; min-width: 0; }}
.admin-nav-badge {{ background: {T.ADMIN_AKSEN_PERHATIAN}; color: {T.ADMIN_PERMUKAAN}; font-size: 12px; font-weight: 700; line-height: 1.25; border-radius: 999px; padding: 2px 8px; }}
.admin-nav-titik {{ width: 8px; height: 8px; border-radius: 50%; background: {T.ADMIN_AKSEN_PERHATIAN}; flex: none; }}
.admin-sr {{ position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
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
.admin-nav-mobile > summary {{ display: flex; align-items: center; gap: 8px; }}
.admin-nav-mobile > summary span:not(.admin-nav-badge):not(.admin-sr) {{ color: {T.ADMIN_REDUP}; }}
.admin-nav-mobile > summary .admin-nav-badge {{ margin-left: auto; }}
.admin-nav-mobile > nav {{ position: absolute; left: 0; z-index: 10; width: min(28rem, calc(100vw - 32px)); margin-top: 8px; padding: 20px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; background: {T.ADMIN_PERMUKAAN}; max-height: calc(100vh - 8rem); max-height: calc(100dvh - 8rem); overflow-y: auto; overscroll-behavior: contain; }}
.admin-kepala {{ margin-bottom: 28px; }}
.admin-utama h1, .admin-utama h2, .admin-utama h3 {{ font-family: {T.FONT_HEADLINE}; line-height: 1.3; color: {T.ADMIN_TEKS}; }}
.admin-kepala h1 {{ margin: 0 0 4px; line-height: 1.2; font-size: {T.ADMIN_UKURAN_JUDUL}; font-weight: 700; letter-spacing: -.01em; }}
.admin-sub {{ margin: 0; color: {T.ADMIN_REDUP}; font-size: 15px; }}
.admin-utama main {{ min-width: 0; overflow-wrap: anywhere; }}
.admin-kartu, .admin-stat {{ background: {T.ADMIN_PERMUKAAN}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.ADMIN_RADIUS}; padding: 24px; min-width: 0; }}
.admin-kartu {{ margin-bottom: 24px; }}
.admin-kartu h2 {{ font-size: 18px; margin: 0 0 16px; }}
.admin-kartu h3 {{ font-size: 15px; margin: 0 0 12px; }}
.admin-meta, .admin-sub, .sub {{ color: {T.ADMIN_REDUP}; }}
.admin-meta, .admin-footer, .admin-kartu small {{ font-size: 13px; }}
.admin-footer {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid {T.ADMIN_BORDER}; color: {T.ADMIN_REDUP}; }}
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
.admin-kartu.admin-status-baris {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; padding: 20px 24px; }}
.admin-status-baris h2 {{ display: inline-flex; align-items: center; gap: 10px; margin: 0; font-size: 20px; }}
.admin-titik-status {{ width: 12px; height: 12px; flex: none; border-radius: 50%; background: {T.ADMIN_BAIK_TITIK}; }}
.admin-titik-status.admin-titik-netral {{ background: {T.ADMIN_NETRAL_TITIK}; }}
.admin-dua-kolom.admin-kolom-2-1 {{ grid-template-columns: minmax(0,2fr) minmax(0,1fr); }}
.admin-form-bagian {{ display: flex; flex-direction: column; gap: 20px; }}
.admin-form-bagian label {{ margin: 0; }}
.admin-kartu label.admin-cek:has(input[type=checkbox]) {{ display: flex; align-items: flex-start; gap: 12px; min-height: 44px; padding: 0; background: none; }}
.admin-cek input[type=checkbox] {{ margin: 2px 0 0; flex: none; }}
.admin-cek > span {{ display: flex; flex-direction: column; gap: 2px; }}
.admin-bagian {{ display: flex; flex-direction: column; gap: 12px; padding-top: 20px; border-top: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-sempit {{ max-width: 20rem; }}
.admin-pratinjau {{ padding: 20px; border: 1px dashed {T.ADMIN_BORDER_KUAT}; border-radius: 12px; background: {T.ADMIN_HOVER}; font-size: 16px; }}
.admin-bar-atas {{ display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: flex-end; gap: 12px; margin-bottom: 4px; }}
.admin-bar-atas > form {{ flex: 1 1 24rem; max-width: 40rem; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.admin-bar-atas > form > label.admin-cari {{ display: block; flex: 1 1 14rem; margin: 0; }}
.admin-cari input {{ display: block; width: 100%; min-height: 44px; padding: 10px 14px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: 12px; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-bar-atas details {{ flex: 1 1 100%; }}
.admin-bar-atas details > div {{ display: flex; flex-wrap: wrap; gap: 16px; padding: 4px 0 8px; }}
.admin-bar-atas details label {{ flex: 1 1 160px; margin: 0; font-size: 14px; }}
.admin-bar-atas details select {{ display: block; width: 100%; min-height: 44px; margin-top: 6px; padding: 10px 12px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: 10px; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-bar-atas + .admin-grid-stat {{ margin-top: 16px; }}
.admin-kpi-hero {{ display: flex; flex-direction: column; gap: 20px; }}
.admin-kpi-hero-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; }}
.admin-kpi-hero-kepala h2 {{ margin: 0; }}
.admin-kpi-hero-kepala .admin-meta {{ margin-left: auto; font-size: 14px; }}
.admin-kpi-hero-angka {{ display: flex; flex-wrap: wrap; align-items: flex-end; gap: 20px 40px; }}
.admin-kpi-hero-angka > div {{ display: flex; flex-direction: column; gap: 2px; }}
.admin-kpi-hero-angka strong {{ font-size: 20px; }}
.admin-kpi-hero-angka .admin-angka {{ font-size: {T.ADMIN_UKURAN_KPI}; line-height: 1.1; }}
.admin-kpi-hero .admin-bilah {{ margin: 0; background: {T.ADMIN_NAV_HOVER}; }}
.admin-bilah-skala {{ display: flex; justify-content: space-between; margin-top: -12px; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-kartu.admin-kosong-kartu {{ display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 40px 24px; text-align: center; }}
.admin-kosong-kartu h2, .admin-kosong-kartu p {{ margin: 0; }}
.admin-kosong-kartu p {{ max-width: 34rem; color: {T.ADMIN_REDUP}; line-height: 1.6; }}
.admin-tab-baris {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }}
.admin-tab {{ display: inline-flex; align-items: center; min-height: 44px; padding: 10px 16px; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: 999px; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; font-weight: 600; text-decoration: none; }}
.admin-tab:hover {{ background: {T.ADMIN_NAV_HOVER}; text-decoration: none; }}
.admin-tab.admin-tab-aktif {{ background: {T.ADMIN_AKSEN_LATAR}; border-color: {T.ADMIN_AKSEN_BORDER}; color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-kartu.admin-filter-riwayat {{ padding: 20px 24px; margin-bottom: 16px; }}
.admin-kartu.admin-filter-riwayat > label {{ margin: 0; flex: 1 1 11rem; }}
.admin-kartu.admin-filter-riwayat > label:first-of-type {{ flex-basis: 11rem; }}
.admin-kartu.admin-cepat-aksi {{ padding: 0 24px; margin-bottom: 24px; }}
.admin-daftar-status {{ list-style: none; margin: 0; padding: 0; }}
.admin-baris-status {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; padding: 16px 24px; border-bottom: 1px solid {T.ADMIN_PEMISAH}; font-weight: 600; }}
.admin-baris-status.perhatian {{ background: {T.ADMIN_BANNER_LATAR}; color: {T.ADMIN_BANNER_TEKS}; }}
.admin-kaki-garis {{ padding-top: 16px; border-top: 1px solid {T.ADMIN_BORDER}; }}
.admin-kaki-garis p {{ margin: 0 0 6px; }}
.admin-seksi-kepala p {{ margin: 0; }}
.admin-seksi-kepala {{ margin-bottom: 16px; }}
.admin-tahap {{ display: flex; flex-direction: column; gap: 4px; }}
.admin-tahap-aktif .admin-meta {{ color: {T.ADMIN_AKSEN_TEKS}; font-weight: 600; }}
.admin-tahap-hint {{ font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-prasyarat {{ margin: 16px 0; padding: 16px 20px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; }}
.admin-prasyarat h3 {{ margin: 0 0 10px; }}
.admin-prasyarat ul {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit,minmax(15rem,1fr)); gap: 8px 24px; }}
.admin-prasyarat-item {{ display: flex; align-items: center; gap: 10px; }}
.admin-prasyarat-item::before {{ content: ''; width: 10px; height: 10px; flex: none; border-radius: 50%; background: {T.ADMIN_BAIK_TITIK}; }}
.admin-prasyarat-item.perhatian::before {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-prasyarat-item.perhatian strong {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-ai-grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(12.5rem,1fr)); gap: 12px; margin-bottom: 16px; }}
.admin-ai-tile {{ display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 14px 16px; border: 1px solid {T.ADMIN_BORDER}; border-radius: 12px; }}
.admin-ai-tile strong {{ font-size: 24px; }}
form[action="/admin/layanan/dukungan"] {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(15rem,1fr)); gap: 4px 16px; align-items: start; }}
form[action="/admin/layanan/dukungan"] > p, form[action="/admin/layanan/dukungan"] > label:has(input[type=checkbox]), form[action="/admin/layanan/dukungan"] > button {{ grid-column: 1 / -1; }}
form[action="/admin/layanan/dukungan"] > label[for="dukungan-wa"] {{ grid-column: 1 / -1; max-width: 28rem; }}
form[action="/admin/layanan/dukungan"] > button, form[action="/admin/layanan/pembayaran"] > button {{ justify-self: start; }}
form[action="/admin/layanan/dukungan"] > label[for="dukungan-reauth"], form[action="/admin/layanan/pembayaran"] > label:not(:has(input[type=checkbox])):not(:has(select)) {{ max-width: 20rem; }}
form[action="/admin/layanan/pembayaran"] > label:has(select) {{ max-width: 22rem; }}
form[action="/admin/layanan/pembayaran"], form[action="/admin/layanan/dukungan"] {{ padding-top: 16px; border-top: 1px solid {T.ADMIN_PEMISAH}; margin-top: 16px; }}
.admin-cnt {{ font-size: 12px; font-weight: 700; line-height: 1.25; background: {T.ADMIN_NAV_HOVER}; color: {T.ADMIN_NETRAL_TEKS}; border-radius: 999px; padding: 2px 8px; }}
.admin-chip[aria-current="true"] .admin-cnt {{ background: {T.ADMIN_PERMUKAAN}; }}
.admin-kartu.admin-kartu-tabel {{ padding: 0; overflow: hidden; }}
.admin-kartu-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; padding: 18px 24px; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-kartu-kepala h2 {{ margin: 0; }}
.admin-kartu-catatan {{ margin: 0; padding: 12px 24px; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-kartu-kaki {{ padding: 0 24px 20px; }}
.admin-kartu-kaki .admin-meta {{ margin: 16px 0 0; }}
.admin-kartu-tabel .admin-tabel th, .admin-kartu-tabel .admin-tabel td {{ vertical-align: middle; }}
.admin-sel-nama {{ display: flex; align-items: center; gap: 12px; font-weight: 600; }}
.admin-avatar {{ display: inline-flex; align-items: center; justify-content: center; flex: none; width: 36px; height: 36px; border-radius: 50%; background: {T.ADMIN_NAV_HOVER}; color: {T.ADMIN_NETRAL_TEKS}; font-weight: 700; font-size: 14px; }}
.admin-redup {{ color: {T.ADMIN_REDUP}; }}
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
.admin-ai-status {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 16px; margin: 0 0 16px; }}
.admin-ai-status dt {{ font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-ai-status dd {{ margin: 6px 0 0; font-size: 17px; }}
.admin-ai-pagu {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(14rem,1fr)); gap: 16px; }}
.admin-ai-pagu label {{ margin: 0; }}
.admin-ai-grup {{ margin: 0 0 20px; }}
.admin-kartu fieldset.admin-henti {{ background: {T.ADMIN_PERMUKAAN}; border-color: {T.ADMIN_BAHAYA_BORDER}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-henti legend {{ color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-kartu .admin-henti label:has(input[type=checkbox]) {{ background: {T.ADMIN_BAHAYA_LATAR}; }}
.admin-ai-tabel .admin-tabel td[data-angka], .admin-ai-tabel .admin-tabel code {{ white-space: nowrap; }}
.admin-ai-tabel .admin-badge {{ border-radius: 12px; }}
.admin-ai-simpan {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; }}
.admin-ai-simpan > label {{ flex: 0 1 320px; margin: 0; }}
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
.admin-ringkasan {{ display: flex; flex-direction: column; gap: 28px; line-height: normal; }}
.admin-ringkasan > .admin-kartu {{ margin-bottom: 0; }}
.admin-kartu.admin-prioritas {{ padding: 0; background: {T.ADMIN_PERMUKAAN}; overflow: hidden; }}
.admin-prioritas-kepala, .admin-seksi-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; }}
.admin-prioritas-kepala {{ padding: 20px 24px; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-kartu.admin-prioritas h2 {{ margin: 0; font-size: 18px; }}
.admin-seksi-kepala h2 {{ margin: 0; font-size: 18px; }}
.admin-prioritas-ket {{ margin: 0; font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-alis {{ margin: 0 0 4px; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-antrean {{ list-style: none; margin: 0; padding: 0; }}
.admin-antrean-item {{ display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 18px 24px; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-antrean-item:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-urgensi {{ flex: 0 0 96px; display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: {T.ADMIN_REDUP}; }}
.admin-urgensi-mendesak {{ color: {T.ADMIN_URGEN_TEKS}; }}
.admin-urgensi-penting {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-titik {{ width: 8px; height: 8px; flex: none; border-radius: 50%; background: {T.ADMIN_NETRAL_TITIK}; }}
.admin-urgensi-mendesak .admin-titik {{ background: {T.ADMIN_URGEN_TITIK}; }}
.admin-urgensi-penting .admin-titik {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-antrean-isi {{ flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 4px; }}
.admin-prioritas .admin-antrean-item h3 {{ margin: 0; font-size: 15px; font-weight: 600; }}
.admin-antrean-isi p {{ margin: 0; font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-ref {{ font-family: ui-monospace, Menlo, monospace; font-size: 13px; background: {T.ADMIN_NETRAL_LATAR}; border-radius: 6px; padding: 2px 6px; }}
.admin-umur {{ flex: 0 0 84px; font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-umur-mendesak {{ color: {T.ADMIN_URGEN_TEKS}; font-weight: 600; }}
.admin-antrean-sisa {{ padding: 16px 24px; font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-antrean-catatan, .admin-antrean-kosong {{ margin: 0; padding: 16px 24px; font-size: 13px; color: {T.ADMIN_REDUP}; }}
.admin-layanan {{ display: flex; flex-direction: column; gap: 14px; }}
.admin-layanan dl {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 16px; margin: 0; }}
.admin-layanan-kartu {{ min-width: 0; display: flex; flex-direction: column; gap: 8px; padding: 18px 20px; background: {T.ADMIN_PERMUKAAN}; border: 1px solid {T.ADMIN_BORDER}; border-radius: 14px; }}
.admin-layanan dt {{ color: {T.ADMIN_REDUP}; font-size: 14px; }}
.admin-layanan dd {{ margin: 0; display: inline-flex; align-items: center; gap: 8px; font-size: 17px; font-weight: 700; }}
.admin-layanan dd .admin-titik {{ width: 10px; height: 10px; }}
.admin-layanan-baik .admin-titik {{ background: {T.ADMIN_BAIK_TITIK}; }}
.admin-layanan-perhatian {{ background: {T.ADMIN_BANNER_LATAR}; border-color: {T.ADMIN_BANNER_BORDER}; }}
.admin-layanan-perhatian dt {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-layanan-perhatian dd {{ color: {T.ADMIN_BANNER_TEKS}; }}
.admin-layanan-perhatian .admin-titik {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-layanan-cta {{ display: inline-flex; min-height: 44px; align-items: center; font-weight: 600; align-self: flex-start; }}
.admin-pendukung {{ display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }}
.admin-pendukung > .admin-kartu {{ margin-bottom: 0; }}
.admin-dua-kolom {{ display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 24px; align-items: start; }}
.admin-angka-kartu {{ flex: 1 1 370px; display: flex; flex-direction: column; gap: 16px; }}
.admin-angka-kartu h2 {{ margin: 0; }}
.admin-angka-kartu p {{ margin: 0; line-height: 1.5; }}
.admin-angka-daftar {{ margin: 0; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px 16px; }}
.admin-angka-daftar dt {{ font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-angka-daftar dd {{ margin: 2px 0 0; font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }}
.admin-kartu.admin-aktivitas {{ flex: 2 1 402px; padding: 0; overflow: hidden; }}
.admin-aktivitas .admin-seksi-kepala {{ padding: 20px 24px; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-aktivitas li {{ padding: 16px 24px; }}
.admin-aktivitas li + li {{ border-top: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-aktivitas-baris {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; }}
.admin-aktivitas-baris:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-aktivitas a {{ display: inline-flex; align-items: center; min-height: 44px; text-decoration: none; }}
.admin-aktivitas-judul-baris {{ display: flex; flex-wrap: wrap; align-items: center; column-gap: 6px; }}
.admin-aktivitas a:hover {{ text-decoration: underline; }}
.admin-aktivitas-isi {{ flex: 1 1 220px; min-width: 0; display: flex; flex-direction: column; gap: 2px; font-size: 15px; }}
.admin-aktivitas-isi .admin-meta {{ font-size: 14px; }}
.admin-aktivitas-waktu {{ font-size: 14px; color: {T.ADMIN_REDUP}; }}
.admin-pil {{ font-size: 13px; font-weight: 600; background: {T.ADMIN_NETRAL_LATAR}; color: {T.ADMIN_NETRAL_TEKS}; border-radius: 999px; padding: 3px 10px; }}
.admin-pil-batal {{ background: {T.ADMIN_BAHAYA_LATAR}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-aktivitas ul, .admin-login-detail ul {{ list-style: none; padding: 0; margin: 0; }}
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
.admin-kepala-aksi {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px; }}
.admin-kepala-aksi > div:first-child {{ flex: 1 1 22rem; min-width: 0; }}
.admin-aksi-header {{ flex: 0 1 auto; max-width: 100%; }}
.admin-aksi-header .riset-aksi-atas {{ margin: 0; justify-content: flex-end; }}
.riset-stat .admin-stat > div {{ flex-direction: column; align-items: flex-start; gap: 2px; }}
.riset-mulai form {{ display: flex; flex-direction: column; gap: 16px; }}
.riset-mulai label {{ margin: 0; font-weight: 600; }}
.riset-mulai .admin-catatan {{ margin: 0 0 16px; padding: 14px 16px; font-size: 14px; line-height: 1.5; }}
.admin-kartu fieldset.riset-persetujuan {{ display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; border: 0; }}
.riset-persetujuan legend {{ padding: 0 0 8px; font-size: 14px; }}
.admin-kartu .riset-persetujuan label:has(input[type=checkbox]) {{ display: flex; align-items: flex-start; gap: 8px; min-height: 0; padding: 0; background: none; font-weight: 400; }}
.admin-kartu .riset-persetujuan input[type=checkbox] {{ flex: none; margin: 1px 0 0; }}
.riset-kepala-filter {{ align-items: flex-end; }}
.riset-filter {{ display: flex; flex-wrap: nowrap; align-items: flex-end; gap: 10px; }}
.admin-form-cari.riset-filter > label {{ flex: 0 1 180px; margin: 0; font-weight: 600; }}
.riset-filter .admin-tombol {{ flex: none; }}
.riset-kosong {{ display: flex; flex-direction: column; align-items: center; gap: 8px; margin: 0; padding: 56px 24px; text-align: center; }}
.riset-kosong span {{ max-width: 380px; color: {T.ADMIN_REDUP}; font-size: 14.5px; line-height: 1.6; }}
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
  .admin-grid-stat {{ grid-template-columns: repeat(2,minmax(0,1fr)); }}
  .admin-dua-kolom, .admin-dua-kolom.admin-kolom-2-1 {{ grid-template-columns: 1fr; }}
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
  .admin-kartu.admin-kartu-tabel {{ padding: 0; }}
  .riset-filter {{ flex-wrap: wrap; }}
  .admin-kartu-kepala, .admin-kartu-catatan {{ padding-left: 20px; padding-right: 20px; }}
  .admin-kartu-kaki {{ padding: 0 20px 20px; }}
  .admin-bar-atas > form, .admin-bar-atas .admin-tombol {{ flex-basis: 100%; max-width: none; }}
  .admin-rincian dd {{ margin-bottom: 12px; }}
  .admin-antrean-item, .admin-prioritas-kepala, .admin-aktivitas .admin-seksi-kepala, .admin-aktivitas li {{ padding-left: 20px; padding-right: 20px; }}
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
