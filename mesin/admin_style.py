"""Panel privat memakai fondasi Jagomat bersama; tema scoped, tanpa aset eksternal."""
import design_tokens as T
from form_style import GAYA_SELECT

GAYA_ADMIN = f"""
{GAYA_SELECT}
:root {{
  color-scheme: light;
  --admin-latar: {T.ADMIN_LATAR_CERAH};
  --admin-permukaan: {T.ADMIN_PERMUKAAN_CERAH};
  --admin-border: {T.ADMIN_BORDER_CERAH};
  --admin-border-kuat: {T.ADMIN_BORDER_KUAT_CERAH};
  --admin-pemisah: {T.ADMIN_PEMISAH_CERAH};
  --admin-teks: {T.ADMIN_TEKS_CERAH};
  --admin-redup: {T.ADMIN_REDUP_CERAH};
  --admin-chevron-select: {T.TEKS_VARIAN};
  --admin-aksen: {T.ADMIN_AKSEN_CERAH};
  --admin-aksen-teks: {T.ADMIN_AKSEN_TEKS_CERAH};
  --admin-aksen-latar: {T.ADMIN_AKSEN_LATAR_CERAH};
  --admin-aksen-border: {T.ADMIN_AKSEN_BORDER_CERAH};
  --admin-baik-latar: {T.ADMIN_BAIK_LATAR_CERAH};
  --admin-baik-teks: {T.ADMIN_BAIK_TEKS_CERAH};
  --admin-perhatian-latar: {T.ADMIN_PERHATIAN_LATAR_CERAH};
  --admin-perhatian-teks: {T.ADMIN_PERHATIAN_TEKS_CERAH};
  --admin-banner-latar: {T.ADMIN_BANNER_LATAR_CERAH};
  --admin-banner-border: {T.ADMIN_BANNER_BORDER_CERAH};
  --admin-banner-teks: {T.ADMIN_BANNER_TEKS_CERAH};
  --admin-bahaya-latar: {T.ADMIN_BAHAYA_LATAR_CERAH};
  --admin-bahaya-border: {T.ADMIN_BAHAYA_BORDER_CERAH};
  --admin-bahaya-teks: {T.ADMIN_BAHAYA_TEKS_CERAH};
  --admin-bahaya-tombol: {T.ADMIN_BAHAYA_TOMBOL_CERAH};
  --admin-netral-latar: {T.ADMIN_NETRAL_LATAR_CERAH};
  --admin-netral-teks: {T.ADMIN_NETRAL_TEKS_CERAH};
  --admin-hover: {T.ADMIN_HOVER_CERAH};
  --admin-nav-hover: {T.ADMIN_NAV_HOVER_CERAH};
  --admin-urgen-titik: {T.ADMIN_URGEN_TITIK_CERAH};
  --admin-urgen-teks: {T.ADMIN_URGEN_TEKS_CERAH};
  --admin-aksen-perhatian: {T.ADMIN_AKSEN_PERHATIAN_CERAH};
  --admin-baik-titik: {T.ADMIN_BAIK_TITIK_CERAH};
  --admin-netral-titik: {T.ADMIN_NETRAL_TITIK_CERAH};
}}
@media screen and (prefers-color-scheme: dark) {{
  :root {{
    color-scheme: dark;
    --admin-latar: {T.ADMIN_LATAR_GELAP};
    --admin-permukaan: {T.ADMIN_PERMUKAAN_GELAP};
    --admin-border: {T.ADMIN_BORDER_GELAP};
    --admin-border-kuat: {T.ADMIN_BORDER_KUAT_GELAP};
    --admin-pemisah: {T.ADMIN_PEMISAH_GELAP};
    --admin-teks: {T.ADMIN_TEKS_GELAP};
    --admin-redup: {T.ADMIN_REDUP_GELAP};
    --admin-chevron-select: {T.ADMIN_REDUP_GELAP};
    --admin-aksen: {T.ADMIN_AKSEN_GELAP};
    --admin-aksen-teks: {T.ADMIN_AKSEN_TEKS_GELAP};
    --admin-aksen-latar: {T.ADMIN_AKSEN_LATAR_GELAP};
    --admin-aksen-border: {T.ADMIN_AKSEN_BORDER_GELAP};
    --admin-baik-latar: {T.ADMIN_BAIK_LATAR_GELAP};
    --admin-baik-teks: {T.ADMIN_BAIK_TEKS_GELAP};
    --admin-perhatian-latar: {T.ADMIN_PERHATIAN_LATAR_GELAP};
    --admin-perhatian-teks: {T.ADMIN_PERHATIAN_TEKS_GELAP};
    --admin-banner-latar: {T.ADMIN_BANNER_LATAR_GELAP};
    --admin-banner-border: {T.ADMIN_BANNER_BORDER_GELAP};
    --admin-banner-teks: {T.ADMIN_BANNER_TEKS_GELAP};
    --admin-bahaya-latar: {T.ADMIN_BAHAYA_LATAR_GELAP};
    --admin-bahaya-border: {T.ADMIN_BAHAYA_BORDER_GELAP};
    --admin-bahaya-teks: {T.ADMIN_BAHAYA_TEKS_GELAP};
    --admin-bahaya-tombol: {T.ADMIN_BAHAYA_TOMBOL_GELAP};
    --admin-netral-latar: {T.ADMIN_NETRAL_LATAR_GELAP};
    --admin-netral-teks: {T.ADMIN_NETRAL_TEKS_GELAP};
    --admin-hover: {T.ADMIN_HOVER_GELAP};
    --admin-nav-hover: {T.ADMIN_NAV_HOVER_GELAP};
    --admin-urgen-titik: {T.ADMIN_URGEN_TITIK_GELAP};
    --admin-urgen-teks: {T.ADMIN_URGEN_TEKS_GELAP};
    --admin-aksen-perhatian: {T.ADMIN_AKSEN_PERHATIAN_GELAP};
    --admin-baik-titik: {T.ADMIN_BAIK_TITIK_GELAP};
    --admin-netral-titik: {T.ADMIN_NETRAL_TITIK_GELAP};
  }}
}}
body.admin-readonly[data-tema="terang"] {{
  color-scheme: light;
  --admin-latar: {T.ADMIN_LATAR_CERAH};
  --admin-permukaan: {T.ADMIN_PERMUKAAN_CERAH};
  --admin-border: {T.ADMIN_BORDER_CERAH};
  --admin-border-kuat: {T.ADMIN_BORDER_KUAT_CERAH};
  --admin-pemisah: {T.ADMIN_PEMISAH_CERAH};
  --admin-teks: {T.ADMIN_TEKS_CERAH};
  --admin-redup: {T.ADMIN_REDUP_CERAH};
  --admin-chevron-select: {T.TEKS_VARIAN};
  --admin-aksen: {T.ADMIN_AKSEN_CERAH};
  --admin-aksen-teks: {T.ADMIN_AKSEN_TEKS_CERAH};
  --admin-aksen-latar: {T.ADMIN_AKSEN_LATAR_CERAH};
  --admin-aksen-border: {T.ADMIN_AKSEN_BORDER_CERAH};
  --admin-baik-latar: {T.ADMIN_BAIK_LATAR_CERAH};
  --admin-baik-teks: {T.ADMIN_BAIK_TEKS_CERAH};
  --admin-perhatian-latar: {T.ADMIN_PERHATIAN_LATAR_CERAH};
  --admin-perhatian-teks: {T.ADMIN_PERHATIAN_TEKS_CERAH};
  --admin-banner-latar: {T.ADMIN_BANNER_LATAR_CERAH};
  --admin-banner-border: {T.ADMIN_BANNER_BORDER_CERAH};
  --admin-banner-teks: {T.ADMIN_BANNER_TEKS_CERAH};
  --admin-bahaya-latar: {T.ADMIN_BAHAYA_LATAR_CERAH};
  --admin-bahaya-border: {T.ADMIN_BAHAYA_BORDER_CERAH};
  --admin-bahaya-teks: {T.ADMIN_BAHAYA_TEKS_CERAH};
  --admin-bahaya-tombol: {T.ADMIN_BAHAYA_TOMBOL_CERAH};
  --admin-netral-latar: {T.ADMIN_NETRAL_LATAR_CERAH};
  --admin-netral-teks: {T.ADMIN_NETRAL_TEKS_CERAH};
  --admin-hover: {T.ADMIN_HOVER_CERAH};
  --admin-nav-hover: {T.ADMIN_NAV_HOVER_CERAH};
  --admin-urgen-titik: {T.ADMIN_URGEN_TITIK_CERAH};
  --admin-urgen-teks: {T.ADMIN_URGEN_TEKS_CERAH};
  --admin-aksen-perhatian: {T.ADMIN_AKSEN_PERHATIAN_CERAH};
  --admin-baik-titik: {T.ADMIN_BAIK_TITIK_CERAH};
  --admin-netral-titik: {T.ADMIN_NETRAL_TITIK_CERAH};
}}
body.admin-readonly[data-tema="gelap"] {{
  color-scheme: dark;
  --admin-latar: {T.ADMIN_LATAR_GELAP};
  --admin-permukaan: {T.ADMIN_PERMUKAAN_GELAP};
  --admin-border: {T.ADMIN_BORDER_GELAP};
  --admin-border-kuat: {T.ADMIN_BORDER_KUAT_GELAP};
  --admin-pemisah: {T.ADMIN_PEMISAH_GELAP};
  --admin-teks: {T.ADMIN_TEKS_GELAP};
  --admin-redup: {T.ADMIN_REDUP_GELAP};
  --admin-chevron-select: {T.ADMIN_REDUP_GELAP};
  --admin-aksen: {T.ADMIN_AKSEN_GELAP};
  --admin-aksen-teks: {T.ADMIN_AKSEN_TEKS_GELAP};
  --admin-aksen-latar: {T.ADMIN_AKSEN_LATAR_GELAP};
  --admin-aksen-border: {T.ADMIN_AKSEN_BORDER_GELAP};
  --admin-baik-latar: {T.ADMIN_BAIK_LATAR_GELAP};
  --admin-baik-teks: {T.ADMIN_BAIK_TEKS_GELAP};
  --admin-perhatian-latar: {T.ADMIN_PERHATIAN_LATAR_GELAP};
  --admin-perhatian-teks: {T.ADMIN_PERHATIAN_TEKS_GELAP};
  --admin-banner-latar: {T.ADMIN_BANNER_LATAR_GELAP};
  --admin-banner-border: {T.ADMIN_BANNER_BORDER_GELAP};
  --admin-banner-teks: {T.ADMIN_BANNER_TEKS_GELAP};
  --admin-bahaya-latar: {T.ADMIN_BAHAYA_LATAR_GELAP};
  --admin-bahaya-border: {T.ADMIN_BAHAYA_BORDER_GELAP};
  --admin-bahaya-teks: {T.ADMIN_BAHAYA_TEKS_GELAP};
  --admin-bahaya-tombol: {T.ADMIN_BAHAYA_TOMBOL_GELAP};
  --admin-netral-latar: {T.ADMIN_NETRAL_LATAR_GELAP};
  --admin-netral-teks: {T.ADMIN_NETRAL_TEKS_GELAP};
  --admin-hover: {T.ADMIN_HOVER_GELAP};
  --admin-nav-hover: {T.ADMIN_NAV_HOVER_GELAP};
  --admin-urgen-titik: {T.ADMIN_URGEN_TITIK_GELAP};
  --admin-urgen-teks: {T.ADMIN_URGEN_TEKS_GELAP};
  --admin-aksen-perhatian: {T.ADMIN_AKSEN_PERHATIAN_GELAP};
  --admin-baik-titik: {T.ADMIN_BAIK_TITIK_GELAP};
  --admin-netral-titik: {T.ADMIN_NETRAL_TITIK_GELAP};
}}
select:not([multiple]):not([size]) {{
  background-image:
    linear-gradient(45deg, transparent 50%, var(--admin-chevron-select) 50%),
    linear-gradient(135deg, var(--admin-chevron-select) 50%, transparent 50%) !important;
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body.admin-readonly {{ margin: 0; background: {T.ADMIN_LATAR}; color: {T.ADMIN_TEKS}; font-family: {T.FONT_LAYAR}; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: {T.LINE_HEIGHT}; }}
a {{ color: {T.ADMIN_AKSEN}; text-underline-offset: .2em; }}
a:hover {{ text-decoration: underline; }}
button, input, select, textarea {{ font: inherit; }}
input, select, textarea {{ font-size: {T.UKURAN_BADAN_LAYAR}; }}
button, summary {{ cursor: pointer; }}
:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.ADMIN_AKSEN}; outline-offset: 2px; }}
.admin-lompat {{ position: absolute; left: 16px; top: -10rem; z-index: 30; padding: {T.SP_3} {T.SP_4}; background: {T.ADMIN_AKSEN_TEKS}; color: {T.ADMIN_PERMUKAAN}; border-radius: {T.RADIUS_SEDANG}; }}
.admin-lompat:focus {{ top: 16px; }}
.admin-bungkus {{ width: 100%; min-height: 100vh; }}
.admin-layout {{ display: grid; grid-template-columns: {T.ADMIN_SIDEBAR} minmax(0,1fr); min-height: 100vh; }}
.admin-sidebar {{ position: sticky; top: 0; height: 100vh; overflow-y: auto; padding: {T.SP_5} {T.SP_4}; background: {T.ADMIN_PERMUKAAN}; border-right: 1px solid {T.ADMIN_BORDER}; }}
.admin-brand {{ display: flex; gap: {T.SP_3}; align-items: center; padding: 0 {T.SP_1} {T.SP_5}; line-height: normal; color: {T.ADMIN_AKSEN}; text-decoration: none; }}
.admin-brand strong {{ display: block; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.admin-brand small {{ display: block; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-brand-mobile {{ display: none; }}
.admin-nav-daftar, .admin-nav-pilihan, .admin-nav-anak {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }}
.admin-nav-daftar {{ gap: {T.SP_4}; }}
.admin-nav-label {{ margin: 0; padding: 0 {T.SP_3} {T.SP_2}; line-height: normal; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }}
.admin-menu a {{ display: flex; align-items: center; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_SEDANG}; color: {T.ADMIN_TEKS}; text-decoration: none; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 500; }}
.admin-menu a svg {{ flex: none; color: {T.ADMIN_REDUP}; }}
.admin-menu a[aria-current="page"] svg {{ color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-nav-label-menu {{ flex: 1; min-width: 0; }}
.admin-nav-badge {{ background: {T.ADMIN_AKSEN_PERHATIAN}; color: {T.ADMIN_PERMUKAAN}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; line-height: 1.25; border-radius: {T.RADIUS_PIL}; padding: 2px {T.SP_2}; }}
.admin-nav-titik {{ width: 8px; height: 8px; border-radius: {T.RADIUS_BULAT}; background: {T.ADMIN_AKSEN_PERHATIAN}; flex: none; }}
.admin-sr {{ position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
.admin-menu a:hover {{ background: {T.ADMIN_NAV_HOVER}; }}
.admin-menu a[aria-current="page"] {{ color: {T.ADMIN_AKSEN_TEKS}; background: {T.ADMIN_AKSEN_LATAR}; font-weight: 600; }}
.admin-utama {{ min-width: 0; width: 100%; max-width: 100rem; margin: 0 auto; padding: {T.SP_5} {T.SP_6} {T.SP_7}; }}
.admin-topbar {{ display: flex; justify-content: flex-end; align-items: center; gap: {T.SP_3}; margin-bottom: {T.SP_4}; }}
.menu-pengguna {{ position: relative; min-width: 0; }}
.menu-pengguna summary {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_SEDANG}; overflow-wrap: anywhere; }}
.menu-pengguna .menu-isi {{ position: absolute; right: 0; z-index: 20; width: min(260px, calc(100vw - 32px)); padding: {T.SP_3}; border: 1px solid {T.ADMIN_BORDER}; background: {T.ADMIN_PERMUKAAN}; border-radius: {T.RADIUS_KARTU}; }}
.menu-isi a, .menu-isi > form:not(.admin-tema) button {{ display: flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; width: 100%; text-align: left; }}
.menu-isi > form:not(.admin-tema) button {{ border: 1px solid {T.ADMIN_BORDER_KUAT}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; border-radius: {T.RADIUS_SEDANG}; }}
.admin-tema {{ padding: {T.SP_1} 0 {T.SP_3}; margin-bottom: {T.SP_2}; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-tema > span {{ display: block; margin: 0 0 {T.SP_2}; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; }}
.admin-tema-pilihan {{ display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: {T.SP_1}; }}
.menu-isi .admin-tema-pilihan button {{ min-height: {T.TARGET_SENTUH}; width: 100%; padding: {T.SP_2} {T.SP_1}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_KECIL}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; }}
.menu-isi .admin-tema-pilihan button:hover {{ background: {T.ADMIN_NAV_HOVER}; }}
.menu-isi .admin-tema-pilihan button[aria-pressed="true"] {{ border: 2px solid {T.ADMIN_AKSEN}; background: {T.ADMIN_AKSEN_LATAR}; color: {T.ADMIN_AKSEN_TEKS}; font-weight: 700; }}
.menu-isi .admin-tema-pilihan button[aria-pressed="true"]::before {{ content: '✓'; margin-right: 3px; }}
.admin-nav-mobile {{ display: none; }}
.admin-nav-mobile > summary {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_SEDANG}; background: {T.ADMIN_PERMUKAAN}; }}
.admin-nav-mobile > summary {{ display: flex; align-items: center; gap: {T.SP_2}; }}
.admin-nav-mobile > summary span:not(.admin-nav-badge):not(.admin-sr) {{ color: {T.ADMIN_REDUP}; }}
.admin-nav-mobile > summary .admin-nav-badge {{ margin-left: auto; }}
.admin-nav-mobile > nav {{ position: absolute; left: 0; z-index: 10; width: min(28rem, calc(100vw - 32px)); margin-top: {T.SP_2}; padding: {T.SP_5}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; background: {T.ADMIN_PERMUKAAN}; max-height: calc(100vh - 8rem); max-height: calc(100dvh - 8rem); overflow-y: auto; overscroll-behavior: contain; }}
.admin-kepala {{ margin-bottom: {T.SP_5}; }}
.admin-utama h1, .admin-utama h2, .admin-utama h3 {{ font-family: {T.FONT_LAYAR}; line-height: 1.3; color: {T.ADMIN_TEKS}; }}
.admin-kepala h1 {{ margin: 0 0 {T.SP_1}; line-height: 1.2; font-size: {T.UKURAN_JUDUL_DEWASA}; font-weight: 700; letter-spacing: -.01em; }}
.admin-sub {{ margin: 0; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.admin-utama main {{ min-width: 0; overflow-wrap: anywhere; }}
.admin-kartu, .admin-stat {{ background: {T.ADMIN_PERMUKAAN}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; min-width: 0; }}
.admin-kartu {{ margin-bottom: {T.SP_5}; }}
.admin-kartu h2 {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; margin: 0 0 {T.SP_4}; }}
.admin-kartu h3 {{ font-size: {T.UKURAN_BADAN_LAYAR}; margin: 0 0 {T.SP_3}; }}
.admin-meta, .admin-sub, .sub {{ color: {T.ADMIN_REDUP}; }}
.admin-meta, .admin-footer, .admin-kartu small {{ font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-footer {{ margin-top: {T.SP_5}; padding-top: {T.SP_4}; border-top: 1px solid {T.ADMIN_BORDER}; color: {T.ADMIN_REDUP}; }}
.admin-catatan, .admin-banner {{ background: {T.ADMIN_BANNER_LATAR}; border-color: {T.ADMIN_BANNER_BORDER}; color: {T.ADMIN_BANNER_TEKS}; }}
.admin-galat, .pesan.galat {{ background: {T.ADMIN_BAHAYA_LATAR}; border: 1px solid {T.ADMIN_BAHAYA_BORDER}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.pesan {{ padding: {T.SP_4} {T.SP_5}; border: 1px solid {T.ADMIN_AKSEN_BORDER}; background: {T.ADMIN_AKSEN_LATAR}; border-radius: {T.RADIUS_KARTU}; margin-bottom: {T.SP_5}; }}
.admin-tombol, .admin-tautan, .admin-chip, .admin-antrean-cta, .admin-pager button {{ min-height: {T.TINGGI_KONTROL}; display: inline-flex; align-items: center; justify-content: center; gap: {T.SP_2}; padding: {T.SP_3} {T.SP_4}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_SEDANG}; text-decoration: none; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; cursor: pointer; }}
.admin-tombol {{ background: {T.ADMIN_AKSEN}; border-color: {T.ADMIN_AKSEN}; color: {T.ADMIN_PERMUKAAN}; }}
.admin-tombol:hover {{ background: {T.ADMIN_AKSEN_TEKS}; color: {T.ADMIN_PERMUKAAN}; text-decoration: none; }}
.admin-tautan, .admin-tombol-sekunder, .admin-antrean-cta, .admin-pager button {{ background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-tombol-sekunder:hover, .admin-tautan:hover, .admin-chip:hover, .admin-antrean-cta:hover {{ background: {T.ADMIN_NAV_HOVER}; color: {T.ADMIN_TEKS}; text-decoration: none; }}
.admin-bahaya {{ background: {T.ADMIN_BAHAYA_TOMBOL}; border-color: {T.ADMIN_BAHAYA_TOMBOL}; color: {T.ADMIN_PERMUKAAN}; }}
.admin-tautan.admin-bahaya:hover, .admin-tombol.admin-bahaya:hover {{ background: {T.ADMIN_BAHAYA_TEKS}; border-color: {T.ADMIN_BAHAYA_TEKS}; color: {T.ADMIN_PERMUKAAN}; }}
button:disabled, button:disabled:hover {{ background: {T.ADMIN_NETRAL_LATAR}; border-color: {T.ADMIN_BORDER}; color: {T.ADMIN_REDUP}; cursor: not-allowed; }}
.admin-kartu input[readonly]:not([type=hidden]):not([type=checkbox]):not([type=radio]), .admin-kartu textarea[readonly] {{ background: {T.ADMIN_NETRAL_LATAR}; }}
.admin-kartu input:disabled:not([type=hidden]):not([type=checkbox]):not([type=radio]), .admin-kartu select:disabled, .admin-kartu textarea:disabled {{ background-color: {T.ADMIN_NETRAL_LATAR}; color: {T.ADMIN_REDUP}; cursor: not-allowed; }}
.admin-zona-bahaya {{ padding: {T.SP_4}; border: 1px solid {T.ADMIN_BAHAYA_BORDER}; border-radius: {T.RADIUS_SEDANG}; background: {T.ADMIN_BAHAYA_LATAR}; }}
.admin-zona-bahaya label {{ color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-chip-baris, .admin-aksi-baca, .riset-aksi-atas {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: {T.SP_4} 0; }}
.admin-chip {{ border-radius: {T.RADIUS_PIL}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-chip[aria-current="true"] {{ background: {T.ADMIN_AKSEN_LATAR}; border-color: {T.ADMIN_AKSEN_BORDER}; color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-kartu.admin-status-baris {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_3} {T.SP_5}; padding: {T.SP_5} {T.SP_5}; }}
.admin-status-baris h2 {{ display: inline-flex; align-items: center; gap: {T.SP_3}; margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.admin-titik-status {{ width: 12px; height: 12px; flex: none; border-radius: {T.RADIUS_BULAT}; background: {T.ADMIN_BAIK_TITIK}; }}
.admin-titik-status.admin-titik-netral {{ background: {T.ADMIN_NETRAL_TITIK}; }}
.admin-dua-kolom.admin-kolom-2-1 {{ grid-template-columns: minmax(0,2fr) minmax(0,1fr); }}
.admin-form-bagian {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
.admin-form-bagian label {{ margin: 0; }}
.admin-kartu label.admin-cek:has(input[type=checkbox]) {{ display: flex; align-items: flex-start; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; padding: 0; background: none; }}
.admin-cek input[type=checkbox] {{ margin: 2px 0 0; flex: none; }}
.admin-cek > span {{ display: flex; flex-direction: column; gap: 2px; }}
.admin-bagian {{ display: flex; flex-direction: column; gap: {T.SP_3}; padding-top: {T.SP_5}; border-top: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-sempit {{ max-width: 20rem; }}
.admin-form-pendek {{ max-width: {T.LEBAR_KONTEN}; }}
.admin-pratinjau {{ padding: {T.SP_5}; border: 1px dashed {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_KARTU}; background: {T.ADMIN_HOVER}; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.admin-kepala-aksi .admin-form-cari {{ flex: 0 1 360px; min-width: 240px; flex-wrap: nowrap; gap: {T.SP_3}; align-items: center; }}
.admin-kepala-aksi .admin-form-cari > label.admin-cari {{ display: block; flex: 1 1 auto; min-width: 0; margin: 0; }}
.admin-kepala-aksi > .admin-grup-cari {{ flex: 0 1 auto; flex-wrap: nowrap; max-width: 100%; }}
.admin-grup-cari .admin-tombol {{ white-space: nowrap; }}
.admin-grup-cari {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; align-items: center; }}
.admin-cari input {{ display: block; width: 100%; min-height: {T.TINGGI_KONTROL}; padding: {T.SP_2} {T.SP_4}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_SEDANG}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-filter-lanjutan {{ margin: 0 0 {T.SP_4}; }}
.admin-filter-lanjutan > div {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 240px)); gap: {T.SP_4}; align-items: end; padding: {T.SP_1} 0 {T.SP_2}; }}
.admin-filter-lanjutan label {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-filter-lanjutan button {{ min-height: {T.TINGGI_KONTROL}; }}
.admin-filter-lanjutan select {{ display: block; width: 100%; min-height: {T.TINGGI_KONTROL}; margin-top: {T.SP_2}; padding: {T.SP_2} {T.SP_3}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_SEDANG}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-kpi-hero {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
.admin-kpi-hero-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: {T.SP_2}; }}
.admin-kpi-hero-kepala h2 {{ margin: 0; }}
.admin-kpi-hero-kepala .admin-meta {{ margin-left: auto; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-kpi-hero-angka {{ display: flex; flex-wrap: wrap; align-items: flex-end; gap: {T.SP_5} {T.SP_6}; }}
.admin-kpi-hero-angka > div {{ display: flex; flex-direction: column; gap: 2px; }}
.admin-kpi-hero-angka strong {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.admin-kpi-hero-angka .admin-angka {{ font-size: {T.UKURAN_ANGKA_DEWASA}; line-height: 1.1; }}
.admin-kpi-hero .admin-bilah {{ margin: 0; background: {T.ADMIN_NAV_HOVER}; }}
.admin-bilah-skala {{ display: flex; justify-content: space-between; margin-top: -12px; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-kartu.admin-kosong-kartu {{ display: flex; flex-direction: column; align-items: center; gap: {T.SP_2}; padding: {T.SP_6} {T.SP_5}; text-align: center; }}
.admin-kosong-kartu h2, .admin-kosong-kartu p {{ margin: 0; }}
.admin-kosong-kartu p {{ max-width: 34rem; color: {T.ADMIN_REDUP}; line-height: 1.6; }}
.admin-tab-baris {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; margin-bottom: {T.SP_4}; }}
.admin-tab {{ display: inline-flex; align-items: center; min-height: {T.TINGGI_KONTROL}; padding: {T.SP_3} {T.SP_4}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_PIL}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; font-weight: 600; text-decoration: none; }}
.admin-tab:hover {{ background: {T.ADMIN_NAV_HOVER}; text-decoration: none; }}
.admin-tab.admin-tab-aktif {{ background: {T.ADMIN_AKSEN_LATAR}; border-color: {T.ADMIN_AKSEN_BORDER}; color: {T.ADMIN_AKSEN_TEKS}; }}
.admin-kartu.admin-filter-riwayat {{ padding: {T.SP_5} {T.SP_5}; margin-bottom: {T.SP_4}; }}
.admin-kartu.admin-filter-riwayat > label {{ margin: 0; flex: 1 1 11rem; }}
.admin-kartu.admin-filter-riwayat > label:first-of-type {{ flex-basis: 11rem; }}
.admin-kartu.admin-cepat-aksi {{ padding: 0 {T.SP_5}; margin-bottom: {T.SP_5}; }}
.admin-daftar-status {{ list-style: none; margin: 0; padding: 0; }}
.admin-baris-status {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: {T.SP_2} {T.SP_4}; padding: {T.SP_4} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_PEMISAH}; font-weight: 600; }}
.admin-baris-status.perhatian {{ background: {T.ADMIN_BANNER_LATAR}; color: {T.ADMIN_BANNER_TEKS}; }}
.admin-kaki-garis {{ padding-top: {T.SP_4}; border-top: 1px solid {T.ADMIN_BORDER}; }}
.admin-kaki-garis p {{ margin: 0 0 {T.SP_2}; }}
.admin-seksi-kepala p {{ margin: 0; }}
.admin-seksi-kepala {{ margin-bottom: {T.SP_4}; }}
.admin-tahap {{ display: flex; flex-direction: column; gap: {T.SP_1}; }}
.admin-tahap-aktif .admin-meta {{ color: {T.ADMIN_AKSEN_TEKS}; font-weight: 600; }}
.admin-tahap-hint {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-prasyarat {{ margin: {T.SP_4} 0; padding: {T.SP_4} {T.SP_5}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.admin-prasyarat h3 {{ margin: 0 0 {T.SP_3}; }}
.admin-prasyarat ul {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,15rem),1fr)); gap: {T.SP_2} {T.SP_5}; }}
.admin-prasyarat-item {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.admin-prasyarat-item::before {{ content: ''; width: 10px; height: 10px; flex: none; border-radius: {T.RADIUS_BULAT}; background: {T.ADMIN_BAIK_TITIK}; }}
.admin-prasyarat-item.perhatian::before {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-prasyarat-item.perhatian strong {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-ai-grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,12.5rem),1fr)); gap: {T.SP_3}; margin-bottom: {T.SP_4}; }}
.admin-ai-tile {{ display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_2}; padding: {T.SP_4} {T.SP_4}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.admin-ai-tile strong {{ font-size: {T.UKURAN_ANGKA_DEWASA}; }}
form[action="/admin/layanan/dukungan"] {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,15rem),1fr)); gap: {T.SP_1} {T.SP_4}; align-items: start; }}
form[action="/admin/layanan/dukungan"] > p, form[action="/admin/layanan/dukungan"] > label:has(input[type=checkbox]), form[action="/admin/layanan/dukungan"] > button {{ grid-column: 1 / -1; }}
form[action="/admin/layanan/dukungan"] > label[for="dukungan-wa"] {{ grid-column: 1 / -1; max-width: 28rem; }}
form[action="/admin/layanan/dukungan"] > button, form[action="/admin/layanan/pembayaran"] > button {{ justify-self: start; }}
form[action="/admin/layanan/dukungan"] > label[for="dukungan-reauth"], form[action="/admin/layanan/pembayaran"] > label:not(:has(input[type=checkbox])):not(:has(select)) {{ max-width: 20rem; }}
form[action="/admin/layanan/pembayaran"] > label:has(select) {{ max-width: 22rem; }}
form[action="/admin/layanan/pembayaran"], form[action="/admin/layanan/dukungan"] {{ padding-top: {T.SP_4}; border-top: 1px solid {T.ADMIN_PEMISAH}; margin-top: {T.SP_4}; }}
.admin-cnt {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; line-height: 1.25; background: {T.ADMIN_NAV_HOVER}; color: {T.ADMIN_NETRAL_TEKS}; border-radius: {T.RADIUS_PIL}; padding: 2px {T.SP_2}; }}
.admin-chip[aria-current="true"] .admin-cnt {{ background: {T.ADMIN_PERMUKAAN}; }}
.admin-kartu.admin-kartu-tabel {{ padding: 0; overflow: hidden; }}
.admin-kartu-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: {T.SP_2}; padding: {T.SP_4} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-kartu-kepala h2 {{ margin: 0; }}
.admin-kartu-catatan {{ margin: 0; padding: {T.SP_3} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-kartu-kaki {{ padding: 0 {T.SP_5} {T.SP_5}; }}
.admin-kartu-kaki .admin-meta {{ margin: {T.SP_4} 0 0; }}
.admin-kartu-tabel .admin-tabel th, .admin-kartu-tabel .admin-tabel td {{ vertical-align: middle; }}
.admin-sel-nama {{ display: flex; align-items: center; gap: {T.SP_3}; font-weight: 600; }}
.admin-avatar {{ display: inline-flex; align-items: center; justify-content: center; flex: none; width: 36px; height: 36px; border-radius: {T.RADIUS_BULAT}; background: {T.ADMIN_NAV_HOVER}; color: {T.ADMIN_NETRAL_TEKS}; font-weight: 700; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-redup {{ color: {T.ADMIN_REDUP}; }}
.admin-badge {{ display: inline-flex; align-items: center; gap: {T.SP_2}; padding: 3px {T.SP_3}; margin: 2px {T.SP_1} 2px 0; border-radius: {T.RADIUS_PIL}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ADMIN_NETRAL_TEKS}; background: {T.ADMIN_NETRAL_LATAR}; }}
.admin-badge::before {{ content: '•'; }}
.admin-badge.perhatian {{ color: {T.ADMIN_PERHATIAN_TEKS}; background: {T.ADMIN_PERHATIAN_LATAR}; }}
.admin-badge.batal {{ color: {T.ADMIN_BAHAYA_TEKS}; background: {T.ADMIN_BAHAYA_LATAR}; }}
.admin-badge.bien {{ color: {T.ADMIN_BAIK_TEKS}; background: {T.ADMIN_BAIK_LATAR}; }}
.admin-form-cari, .admin-filtre-periode {{ display: flex; flex-wrap: wrap; gap: {T.SP_4}; align-items: end; }}
.admin-form-cari > label {{ flex: 1 1 160px; }}
.admin-form-cari > label:first-of-type {{ flex-basis: 260px; }}
.admin-kartu label, .admin-filtre-periode label {{ display: block; margin: {T.SP_3} 0; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-kartu input:not([type=hidden]):not([type=checkbox]):not([type=radio]), .admin-kartu select, .admin-kartu textarea, .admin-filtre-periode input {{ display: block; width: 100%; min-height: {T.TINGGI_KONTROL}; margin-top: {T.SP_2}; padding: {T.SP_2} {T.SP_3}; border: 1px solid {T.ADMIN_BORDER_KUAT}; border-radius: {T.RADIUS_SEDANG}; background: {T.ADMIN_PERMUKAAN}; color: {T.ADMIN_TEKS}; }}
.admin-kartu textarea {{ resize: vertical; min-height: 7rem; }}
.admin-kartu fieldset {{ min-width: 0; margin: {T.SP_4} 0; padding: {T.SP_4} {T.SP_5}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.admin-kartu legend {{ padding: 0 {T.SP_2}; font-weight: 600; }}
.admin-kartu fieldset.admin-galat {{ border-color: {T.ADMIN_BAHAYA_BORDER}; }}
.admin-ai-status {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: {T.SP_4}; margin: 0 0 {T.SP_4}; }}
.admin-ai-status dt {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-ai-status dd {{ margin: {T.SP_2} 0 0; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.admin-ai-pagu {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,14rem),1fr)); gap: {T.SP_4}; }}
.admin-ai-pagu label {{ margin: 0; }}
.admin-ai-grup {{ margin: 0 0 {T.SP_5}; }}
.admin-kartu fieldset.admin-henti {{ background: {T.ADMIN_PERMUKAAN}; border-color: {T.ADMIN_BAHAYA_BORDER}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-henti legend {{ color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-kartu .admin-henti label:has(input[type=checkbox]) {{ background: {T.ADMIN_BAHAYA_LATAR}; }}
.admin-ai-tabel .admin-tabel td[data-angka], .admin-ai-tabel .admin-tabel code {{ white-space: nowrap; }}
.admin-ai-tabel .admin-badge {{ border-radius: {T.RADIUS_KARTU}; }}
.admin-ai-simpan {{ display: flex; flex-wrap: wrap; gap: {T.SP_4}; align-items: flex-end; }}
.admin-ai-simpan > label {{ flex: 0 1 320px; margin: 0; }}
::placeholder {{ color: {T.ADMIN_REDUP}; opacity: 1; }}
.admin-kartu input[type=checkbox], .admin-kartu input[type=radio] {{ width: 20px; height: 20px; vertical-align: middle; margin-right: {T.SP_2}; accent-color: {T.ADMIN_AKSEN}; }}
.admin-kartu label:has(input[type=checkbox]), .admin-kartu label:has(input[type=radio]) {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_3} {T.SP_3}; background: {T.ADMIN_NETRAL_LATAR}; border-radius: {T.RADIUS_SEDANG}; }}
.admin-kartu button:not(.tombol-mata) {{ min-height: {T.TINGGI_KONTROL}; }}
.admin-kartu form + form, .admin-form-tindakan form + form {{ margin-top: {T.SP_5}; }}
summary {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_3} 0; font-weight: 600; }}
.kolom-sandi {{ display: block; position: relative; min-width: 0; }}
.kolom-sandi > input {{ padding-right: 52px !important; }}
.tombol-mata {{ position: absolute; right: 3px; top: 50%; transform: translateY(-50%); width: {T.TARGET_SENTUH}; height: {T.TARGET_SENTUH}; padding: 0; display: grid; place-items: center; border: 0; border-radius: {T.RADIUS_SEDANG}; background: transparent; color: {T.ADMIN_REDUP}; }}
.admin-tabel-wrap {{ overflow-x: auto; max-width: 100%; }}
.admin-tabel-wrap:focus-visible {{ outline-offset: -3px; }}
.admin-tabel a:focus-visible {{ outline-offset: -3px; }}
.admin-tabel {{ width: 100%; border-collapse: collapse; min-width: 42rem; }}
.admin-tabel th, .admin-tabel td {{ overflow-wrap: normal; word-break: normal; padding: {T.SP_4} {T.SP_4}; border-bottom: 1px solid {T.ADMIN_PEMISAH}; text-align: left; vertical-align: top; }}
.admin-tabel th {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ADMIN_REDUP}; background: {T.ADMIN_LATAR}; white-space: nowrap; }}
.admin-tabel tbody tr:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-tabel td[data-angka], .admin-tabel th[data-angka] {{ text-align: right; font-variant-numeric: tabular-nums; }}
.admin-tabel a {{ display: inline-flex; min-height: {T.TARGET_SENTUH}; min-width: {T.TARGET_SENTUH}; align-items: center; }}
.admin-kosong {{ color: {T.ADMIN_REDUP}; padding: {T.SP_5}; text-align: center; }}
.admin-pager {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: {T.SP_3}; margin-top: {T.SP_5}; }}
.admin-pager form {{ margin: 0; }}
.admin-rincian {{ display: grid; grid-template-columns: 11rem minmax(0,1fr); gap: {T.SP_2} {T.SP_4}; }}
.admin-rincian dt {{ font-weight: 600; color: {T.ADMIN_REDUP}; }}
.admin-rincian dd {{ margin: 0; overflow-wrap: anywhere; }}
.admin-grid-stat {{ display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: {T.SP_4}; margin-bottom: {T.SP_5}; }}
.admin-stat h2 {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 500; margin: 0 0 {T.SP_2}; color: {T.ADMIN_REDUP}; }}
.admin-stat > div {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: {T.SP_2}; }}
.admin-stat strong {{ font-size: {T.UKURAN_ANGKA_DEWASA}; line-height: 1.2; font-variant-numeric: tabular-nums; }}
.admin-stat span {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-ringkasan {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
.admin-ringkasan > .admin-kartu {{ margin-bottom: 0; }}
.admin-kartu.admin-prioritas {{ padding: 0; background: {T.ADMIN_PERMUKAAN}; overflow: hidden; }}
.admin-prioritas-kepala, .admin-seksi-kepala {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: {T.SP_2}; }}
.admin-prioritas-kepala {{ padding: {T.SP_5} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-kartu.admin-prioritas h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.admin-seksi-kepala h2 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.admin-prioritas-ket {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-alis {{ margin: 0 0 {T.SP_1}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-antrean {{ list-style: none; margin: 0; padding: 0; }}
.admin-antrean-item {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_4}; padding: {T.SP_4} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-antrean-item:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-urgensi {{ flex: 0 0 96px; display: inline-flex; align-items: center; gap: {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ADMIN_REDUP}; }}
.admin-urgensi-mendesak {{ color: {T.ADMIN_URGEN_TEKS}; }}
.admin-urgensi-penting {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-titik {{ width: 8px; height: 8px; flex: none; border-radius: {T.RADIUS_BULAT}; background: {T.ADMIN_NETRAL_TITIK}; }}
.admin-urgensi-mendesak .admin-titik {{ background: {T.ADMIN_URGEN_TITIK}; }}
.admin-urgensi-penting .admin-titik {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-antrean-isi {{ flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: {T.SP_1}; }}
.admin-prioritas .admin-antrean-item h3 {{ margin: 0; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 600; }}
.admin-antrean-isi p {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-ref {{ font-family: ui-monospace, Menlo, monospace; font-size: {T.UKURAN_TEKS_LABEL}; background: {T.ADMIN_NETRAL_LATAR}; border-radius: {T.RADIUS_KECIL}; padding: 2px {T.SP_2}; }}
.admin-umur {{ flex: 0 0 84px; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-umur-mendesak {{ color: {T.ADMIN_URGEN_TEKS}; font-weight: 600; }}
.admin-antrean-sisa {{ padding: {T.SP_4} {T.SP_5}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-antrean-catatan, .admin-antrean-kosong {{ margin: 0; padding: {T.SP_4} {T.SP_5}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-layanan {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.admin-layanan dl {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: {T.SP_4}; margin: 0; }}
.admin-layanan-kartu {{ min-width: 0; display: flex; flex-direction: column; gap: {T.SP_2}; padding: {T.SP_4} {T.SP_5}; background: {T.ADMIN_PERMUKAAN}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.admin-layanan dt {{ color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-layanan dd {{ margin: 0; display: inline-flex; align-items: center; gap: {T.SP_2}; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 700; }}
.admin-layanan dd .admin-titik {{ width: 10px; height: 10px; }}
.admin-layanan-baik .admin-titik {{ background: {T.ADMIN_BAIK_TITIK}; }}
.admin-layanan-perhatian {{ background: {T.ADMIN_BANNER_LATAR}; border-color: {T.ADMIN_BANNER_BORDER}; }}
.admin-layanan-perhatian dt {{ color: {T.ADMIN_PERHATIAN_TEKS}; }}
.admin-layanan-perhatian dd {{ color: {T.ADMIN_BANNER_TEKS}; }}
.admin-layanan-perhatian .admin-titik {{ background: {T.ADMIN_AKSEN_PERHATIAN}; }}
.admin-layanan-cta {{ display: inline-flex; min-height: {T.TARGET_SENTUH}; align-items: center; font-weight: 600; align-self: flex-start; }}
.admin-pendukung {{ display: flex; flex-wrap: wrap; gap: {T.SP_5}; align-items: flex-start; }}
.admin-pendukung > .admin-kartu {{ margin-bottom: 0; }}
.admin-dua-kolom {{ display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: {T.SP_5}; align-items: start; }}
.admin-angka-kartu {{ flex: 1 1 370px; display: flex; flex-direction: column; gap: {T.SP_4}; }}
.admin-angka-kartu h2 {{ margin: 0; }}
.admin-angka-kartu p {{ margin: 0; line-height: 1.5; }}
.admin-angka-daftar {{ margin: 0; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: {T.SP_4} {T.SP_4}; }}
.admin-angka-daftar dt {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-angka-daftar dd {{ margin: 2px 0 0; font-size: {T.UKURAN_ANGKA_DEWASA}; font-weight: 700; font-variant-numeric: tabular-nums; }}
.admin-kartu.admin-aktivitas {{ flex: 2 1 402px; padding: 0; overflow: hidden; }}
.admin-aktivitas .admin-seksi-kepala {{ padding: {T.SP_5} {T.SP_5}; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.admin-aktivitas li {{ padding: {T.SP_4} {T.SP_5}; }}
.admin-aktivitas li + li {{ border-top: 1px solid {T.ADMIN_PEMISAH}; }}
.admin-aktivitas-baris {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_2} {T.SP_4}; }}
.admin-aktivitas-baris:hover {{ background: {T.ADMIN_HOVER}; }}
.admin-aktivitas a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; min-width: {T.TARGET_SENTUH}; text-decoration: none; }}
.admin-aktivitas-judul-baris {{ display: flex; flex-wrap: wrap; align-items: center; column-gap: {T.SP_2}; }}
.admin-aktivitas a:hover {{ text-decoration: underline; }}
.admin-aktivitas-isi {{ flex: 1 1 220px; min-width: 0; display: flex; flex-direction: column; gap: 2px; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.admin-aktivitas-isi .admin-meta {{ font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-aktivitas-waktu {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.admin-pil {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; background: {T.ADMIN_NETRAL_LATAR}; color: {T.ADMIN_NETRAL_TEKS}; border-radius: {T.RADIUS_PIL}; padding: 3px {T.SP_3}; }}
.admin-pil-batal {{ background: {T.ADMIN_BAHAYA_LATAR}; color: {T.ADMIN_BAHAYA_TEKS}; }}
.admin-aktivitas ul, .admin-login-detail ul {{ list-style: none; padding: 0; margin: 0; }}
.admin-aktivitas-judul {{ font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 600; }}
.admin-aktivitas-ikon {{ display: none; }}
.admin-cepat nav {{ display: grid; grid-template-columns: 1fr 1fr; gap: {T.SP_3}; }}
.admin-cepat a {{ display: grid; gap: {T.SP_2}; padding: {T.SP_3}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_SEDANG}; }}
.admin-login-detail span {{ display: block; color: {T.ADMIN_REDUP}; }}
.admin-grid-kpi {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,250px),1fr)); gap: {T.SP_5}; margin-top: {T.SP_5}; }}
.admin-kpi-carte header {{ display: flex; justify-content: space-between; gap: {T.SP_2}; align-items: start; }}
.admin-kpi-carte header h2 {{ margin-bottom: {T.SP_2}; }}
.admin-info {{ display: inline-block; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: normal; }}
.admin-info summary {{ min-width: {T.TARGET_SENTUH}; display: grid; place-items: center; }}
.admin-info p {{ max-width: 22rem; }}
.admin-angka {{ font-size: {T.UKURAN_ANGKA_DEWASA}; font-variant-numeric: tabular-nums; }}
.admin-kpi-biaya {{ grid-column: 1 / -1; }}
.admin-bilah {{ height: 12px; margin: {T.SP_4} 0; border-radius: {T.RADIUS_PIL}; background: {T.ADMIN_NETRAL_LATAR}; position: relative; }}
.admin-bilah span {{ display: block; height: 100%; border-radius: inherit; background: {T.ADMIN_AKSEN}; }}
.admin-bilah i {{ position: absolute; top: -3px; height: 18px; width: 2px; background: {T.ADMIN_TEKS}; }}
.admin-stepper {{ display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: {T.SP_3}; padding: 0; list-style: none; }}
.admin-stepper li {{ padding: {T.SP_3}; border: 1px solid {T.ADMIN_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.admin-stepper [aria-current="step"] {{ border: 2px solid {T.ADMIN_AKSEN}; background: {T.ADMIN_AKSEN_LATAR}; font-weight: 600; }}
.admin-id {{ overflow-wrap: anywhere; user-select: all; }}
.riset-grid-form {{ display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: {T.SP_4}; }}
.admin-dua-kolom .riset-grid-form {{ grid-template-columns: 1fr; }}
.riset-aksi-atas form {{ margin: 0; }}
.admin-kepala-aksi {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: {T.SP_4}; }}
.admin-kepala-aksi > div:first-child {{ flex: 1 1 22rem; min-width: 0; }}
.admin-aksi-header {{ flex: 0 1 auto; max-width: 100%; }}
.admin-aksi-header .riset-aksi-atas {{ margin: 0; justify-content: flex-end; }}
.riset-stat .admin-stat > div {{ flex-direction: column; align-items: flex-start; gap: 2px; }}
.riset-mulai form {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.riset-mulai label {{ margin: 0; font-weight: 600; }}
.riset-mulai .admin-catatan {{ margin: 0 0 {T.SP_4}; padding: {T.SP_4} {T.SP_4}; font-size: {T.UKURAN_TEKS_LABEL}; line-height: 1.5; }}
.admin-kartu fieldset.riset-persetujuan {{ display: flex; flex-direction: column; gap: {T.SP_3}; margin: 0; padding: 0; border: 0; }}
.riset-persetujuan legend {{ padding: 0 0 {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.admin-kartu .riset-persetujuan label:has(input[type=checkbox]) {{ display: flex; align-items: flex-start; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} 0; background: none; font-weight: 400; }}
.admin-kartu .riset-persetujuan input[type=checkbox] {{ flex: none; margin: 1px 0 0; }}
.riset-kepala-filter {{ align-items: flex-end; }}
.riset-filter {{ display: flex; flex-wrap: nowrap; align-items: flex-end; gap: {T.SP_3}; }}
.admin-form-cari.riset-filter > label {{ flex: 0 1 180px; margin: 0; font-weight: 600; }}
.riset-filter .admin-tombol {{ flex: none; }}
.riset-kosong {{ display: flex; flex-direction: column; align-items: center; gap: {T.SP_2}; margin: 0; padding: {T.SP_7} {T.SP_5}; text-align: center; }}
.riset-kosong span {{ max-width: 380px; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: 1.6; }}
.riset-prompt {{ max-width: 50rem; font-size: {T.UKURAN_BAGIAN_DEWASA}; font-weight: 600; }}
.riset-kode-baris {{ display: grid; grid-template-columns: 8rem 9rem minmax(0,1fr); gap: {T.SP_2}; align-items: center; }}
.riset-tombol, .riset-aksi-form {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; align-items: end; margin-top: {T.SP_4}; }}
.riset-aksi-form form {{ flex: 1 1 15rem; }}
.riset-daftar-pertanyaan, .riset-daftar-sesi {{ list-style: none; margin: 0; padding: 0; }}
.riset-daftar-pertanyaan li, .riset-sesi {{ padding: {T.SP_4}; border-bottom: 1px solid {T.ADMIN_BORDER}; }}
.riset-daftar-pertanyaan li, .riset-daftar-pertanyaan li > div, .riset-sesi-kepala {{ display: flex; justify-content: space-between; align-items: start; gap: {T.SP_3}; }}
.riset-daftar-pertanyaan > li {{ flex-wrap: wrap; }}
.riset-daftar-pertanyaan > li > div {{ flex: 1 1 12rem; min-width: 0; }}
.riset-daftar-pertanyaan > li > a {{ flex: none; }}
.riset-daftar-pertanyaan p {{ margin: {T.SP_2} 0; }}
.riset-daftar-pertanyaan > li > div > div {{ flex: 1; min-width: 0; }}
.riset-daftar-sesi + .admin-pager {{ padding: 0 {T.SP_5} {T.SP_5}; }}
.riset-sesi {{ display: block; text-decoration: none; }}
.riset-sesi-meta {{ display: block; color: {T.ADMIN_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.riset-nomor {{ min-width: 28px; font-weight: 600; }}
.riset-matriks {{ min-width: 80rem; }}
.riset-matriks q {{ display: block; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ADMIN_REDUP}; }}
.riset-grid-ringkas {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,16rem),1fr)); gap: {T.SP_4}; }}
.sensor-tabel {{ min-width: 50rem; }}
@media (max-width: 70rem) {{
  .admin-utama {{ padding-left: {T.SP_5}; padding-right: {T.SP_5}; }}
  .admin-grid-stat {{ grid-template-columns: repeat(2,minmax(0,1fr)); }}
  .admin-dua-kolom, .admin-dua-kolom.admin-kolom-2-1 {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 51.25rem) {{
  .admin-layout {{ display: block; }}
  .admin-sidebar {{ display: none; }}
  .admin-brand-mobile {{ display: flex; grid-column: 1; grid-row: 1; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; padding: 0; }}
  .admin-topbar {{ display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); align-items: start; }}
  .admin-nav-mobile {{ display: block; grid-column: 1 / -1; grid-row: 2; position: relative; min-width: 0; max-width: 100%; }}
  .menu-pengguna {{ grid-column: 2; grid-row: 1; max-width: 100%; margin-left: auto; }}
  .menu-pengguna > summary {{ max-width: 100%; }}
  .admin-nav-mobile > summary {{ flex-wrap: wrap; }}
  .menu-pengguna .admin-badge {{ display: none; }}
  .admin-nav-mobile .admin-nav-daftar {{ grid-template-columns: 1fr 1fr; }}
  .admin-nav-utama {{ grid-column: 1 / -1; }}
}}
@media (max-width: 32rem) {{
  .admin-utama {{ padding: {T.SP_4}; }}
  .admin-kartu {{ padding: {T.SP_5}; }}
  .admin-kepala {{ margin: {T.SP_5} 0; }}
  .admin-nav-mobile > summary {{ display: flex; flex-wrap: wrap; }}
  .admin-nav-mobile .admin-nav-daftar, .admin-rincian, .riset-grid-form {{ grid-template-columns: 1fr; }}
  .admin-kartu.admin-kartu-tabel {{ padding: 0; }}
  .riset-filter {{ flex-wrap: wrap; }}
  .admin-kartu-kepala, .admin-kartu-catatan {{ padding-left: {T.SP_5}; padding-right: {T.SP_5}; }}
  .admin-kartu-kaki {{ padding: 0 {T.SP_5} {T.SP_5}; }}
  .admin-kepala-aksi .admin-form-cari, .admin-kepala-aksi > .admin-grup-cari {{ flex-basis: 100%; }}
  .admin-kepala-aksi > .admin-grup-cari {{ flex-wrap: wrap; }}
  .admin-rincian dd {{ margin-bottom: {T.SP_3}; }}
  .admin-antrean-item, .admin-prioritas-kepala, .admin-aktivitas .admin-seksi-kepala, .admin-aktivitas li {{ padding-left: {T.SP_5}; padding-right: {T.SP_5}; }}
  .admin-grid-stat {{ gap: {T.SP_3}; }}
  .admin-stat {{ padding: {T.SP_4}; }}
  .admin-stepper {{ grid-template-columns: 1fr 1fr; }}
  .riset-kode-baris {{ grid-template-columns: 1fr 1fr; }}
  .riset-kode-baris span {{ grid-column: 1 / -1; }}
  .riset-aksi-atas {{ display: grid; }}
  .riset-aksi-atas .admin-tautan {{ width: 100%; }}
}}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto; animation: none; transition: none; }} }}
@media (forced-colors: active) {{ select:not([multiple]):not([size]) {{ background-image: none !important; }} }}
@media print {{
  body.admin-readonly[data-tema] {{
    color-scheme: light;
    --admin-latar: {T.ADMIN_LATAR_CERAH};
    --admin-permukaan: {T.ADMIN_PERMUKAAN_CERAH};
    --admin-border: {T.ADMIN_BORDER_CERAH};
    --admin-border-kuat: {T.ADMIN_BORDER_KUAT_CERAH};
    --admin-pemisah: {T.ADMIN_PEMISAH_CERAH};
    --admin-teks: {T.ADMIN_TEKS_CERAH};
    --admin-redup: {T.ADMIN_REDUP_CERAH};
    --admin-chevron-select: {T.TEKS_VARIAN};
    --admin-aksen: {T.ADMIN_AKSEN_CERAH};
    --admin-aksen-teks: {T.ADMIN_AKSEN_TEKS_CERAH};
    --admin-aksen-latar: {T.ADMIN_AKSEN_LATAR_CERAH};
    --admin-aksen-border: {T.ADMIN_AKSEN_BORDER_CERAH};
    --admin-baik-latar: {T.ADMIN_BAIK_LATAR_CERAH};
    --admin-baik-teks: {T.ADMIN_BAIK_TEKS_CERAH};
    --admin-perhatian-latar: {T.ADMIN_PERHATIAN_LATAR_CERAH};
    --admin-perhatian-teks: {T.ADMIN_PERHATIAN_TEKS_CERAH};
    --admin-banner-latar: {T.ADMIN_BANNER_LATAR_CERAH};
    --admin-banner-border: {T.ADMIN_BANNER_BORDER_CERAH};
    --admin-banner-teks: {T.ADMIN_BANNER_TEKS_CERAH};
    --admin-bahaya-latar: {T.ADMIN_BAHAYA_LATAR_CERAH};
    --admin-bahaya-border: {T.ADMIN_BAHAYA_BORDER_CERAH};
    --admin-bahaya-teks: {T.ADMIN_BAHAYA_TEKS_CERAH};
    --admin-bahaya-tombol: {T.ADMIN_BAHAYA_TOMBOL_CERAH};
    --admin-netral-latar: {T.ADMIN_NETRAL_LATAR_CERAH};
    --admin-netral-teks: {T.ADMIN_NETRAL_TEKS_CERAH};
    --admin-hover: {T.ADMIN_HOVER_CERAH};
    --admin-nav-hover: {T.ADMIN_NAV_HOVER_CERAH};
    --admin-urgen-titik: {T.ADMIN_URGEN_TITIK_CERAH};
    --admin-urgen-teks: {T.ADMIN_URGEN_TEKS_CERAH};
    --admin-aksen-perhatian: {T.ADMIN_AKSEN_PERHATIAN_CERAH};
    --admin-baik-titik: {T.ADMIN_BAIK_TITIK_CERAH};
    --admin-netral-titik: {T.ADMIN_NETRAL_TITIK_CERAH};
  }}
  .admin-sidebar, .admin-topbar, .admin-form-cari, .admin-pager {{ display: none; }}
  .admin-layout {{ display: block; }}
}}
"""
