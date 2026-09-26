"""Gaya scoped untuk kandidat pusat kendali admin readonly."""

import design_tokens as T


GAYA_ADMIN = f"""
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body.admin-readonly {{
  margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_UTAMA};
  font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR};
  line-height: {T.LINE_HEIGHT};
}}
.admin-bungkus {{
  width: 100%; margin: 0; min-height: 100vh;
}}
.admin-lompat {{
  position: absolute; left: {T.SP_2}; top: -10rem; z-index: 10;
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH};
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL};
}}
.admin-lompat:focus {{ top: {T.SP_2}; }}
.admin-topbar {{
  display: flex; justify-content: space-between; align-items: center;
  gap: {T.SP_3}; min-height: {T.SP_8}; padding: {T.SP_2} 0;
  border-bottom: 1px solid {T.BORDER_HALUS};
}}
.admin-konteks {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: 0; font-size: .75rem; color: {T.TEKS_VARIAN}; }}
.admin-konteks strong {{ color: {T.TEKS_JUDUL}; }}
.admin-brand {{ display: flex; align-items: center; gap: {T.SP_3}; color: {T.TEKS_PUTIH};
  padding: {T.SP_2} {T.SP_2} {T.SP_6}; text-decoration: none; }}
.admin-brand strong {{ display: block; font: 800 1.1rem {T.FONT_HEADLINE}; }}
.admin-brand small {{ display: block; margin-top: {T.SP_1}; font-size: .75rem; color: {T.BORDER_VARIAN}; }}
.admin-brand-mark {{ display: grid; place-items: center; width: 2.5rem; height: 2.5rem;
  flex-shrink: 0; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_KARTU}; font: 800 1.25rem {T.FONT_HEADLINE}; }}
.admin-topbar .menu-pengguna {{ position: relative; min-width: 0; }}
.admin-topbar .menu-pengguna summary {{ cursor: pointer; overflow-wrap: anywhere; padding: {T.SP_2};
  min-height: {T.TARGET_SENTUH}; border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL}; font-size: .85rem; }}
.admin-topbar .menu-pengguna summary .admin-badge {{ margin: 0; }}
.admin-topbar .menu-isi {{ position: absolute; right: 0; z-index: 20;
  min-width: 12rem; padding: {T.SP_3}; background: {T.LATAR_KARTU_MURID};
  border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL}; }}
.admin-topbar .menu-isi a {{ display: block; padding: {T.SP_2}; color: {T.AKSEN_TEAL_TUA}; }}
.admin-topbar .menu-isi button {{ width: 100%; min-height: {T.TARGET_SENTUH}; margin-top: {T.SP_2}; }}
.admin-identitas {{ margin: auto 0 0; padding: {T.SP_4} {T.SP_2} 0; color: {T.TEKS_PUTIH};
  border-top: 1px solid {T.TEKS_VARIAN}; font-size: .8rem; overflow-wrap: anywhere; }}
.admin-identitas strong, .admin-identitas span {{ display: block; }}
.admin-identitas span {{ color: {T.BORDER_VARIAN}; font-size: .75rem; margin-top: {T.SP_1}; }}
.admin-layout {{ display: grid; grid-template-columns: 14.5rem minmax(0, 1fr); min-height: 100vh; }}
.admin-sidebar {{ position: sticky; top: 0; height: 100vh; overflow-y: auto; display: flex; flex-direction: column;
  padding: {T.SP_4} {T.SP_3}; background: {T.TEKS_JUDUL}; gap: {T.SP_4}; }}
.admin-utama {{ min-width: 0; width: 100%; max-width: 90rem; margin: 0 auto; padding: 0 {T.SP_6} {T.SP_6}; }}
.admin-kepala {{ margin: {T.SP_6} 0; }}
.admin-utama h1, .admin-utama h2, .admin-utama h3 {{ font-family: {T.FONT_HEADLINE}; line-height: 1.3; }}
.admin-alis {{
  margin: 0; color: {T.AKSEN_TEAL_TUA}; font-size: .75rem;
  font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
}}
.admin-kepala h1 {{ margin: {T.SP_1} 0; color: {T.TEKS_JUDUL}; font-size: clamp(1.55rem, 3vw, 2.2rem); }}
.admin-sub {{ margin: 0; color: {T.TEKS_VARIAN}; overflow-wrap: anywhere; }}
.admin-nav {{ display: grid; gap: {T.SP_4}; }}
.admin-nav-grup {{ display: grid; gap: {T.SP_1}; }}
.admin-nav-label {{
  margin: 0 0 {T.SP_1}; padding: 0 {T.SP_3}; color: {T.BORDER_VARIAN};
  font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
}}
.admin-nav a {{
  min-height: {T.TARGET_SENTUH}; display: flex; align-items: center;
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL};
  color: {T.LATAR_KARTU_SEKUNDER}; text-decoration: none; font-weight: 650; font-size: .85rem;
}}
.admin-nav a:hover {{ background: {T.TEKS_VARIAN}; color: {T.TEKS_PUTIH}; }}
.admin-nav a[aria-current="page"] {{
  color: {T.TEKS_PUTIH}; background: {T.AKSEN_TEAL_TUA};
}}
.admin-nav-mobile {{ display: none; }}
.admin-nav-mobile > summary {{
  min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; cursor: pointer;
  border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
  background: {T.LATAR_KARTU_MURID};
}}
.admin-nav-mobile > summary span {{ color: {T.TEKS_VARIAN}; margin-right: {T.SP_2}; }}
.admin-nav-mobile > nav {{
  margin-top: {T.SP_2}; padding: {T.SP_3}; background: {T.TEKS_JUDUL};
  border-radius: {T.RADIUS_KECIL}; display: grid; gap: {T.SP_4};
}}
.admin-nav-mobile nav a {{ min-height: {T.TARGET_SENTUH}; display: flex; align-items: center;
  padding: {T.SP_2} {T.SP_3}; color: {T.TEKS_PUTIH}; text-decoration: none; border-radius: {T.RADIUS_KECIL}; }}
.admin-nav-mobile nav a:hover, .admin-nav-mobile nav a[aria-current="page"] {{ background: {T.AKSEN_TEAL_TUA}; }}
.admin-grid-kpi {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr)); gap:{T.SP_3}; margin:{T.SP_4} 0; }}
.admin-grid-kpi > * {{ min-width:0; }}
.admin-kpi-carte header {{ display:flex; justify-content:space-between; align-items:start; gap:{T.SP_2}; }}
.admin-kpi-carte header h2 {{ font-size:1.12rem; margin:0; }}
.admin-kpi-carte .admin-info {{ flex-shrink:0; }}
.admin-kpi-carte .admin-info[open] {{ flex-shrink:1; }}
.admin-kpi-carte p {{ margin:{T.SP_2} 0; }}
.admin-kpi-biaya {{ grid-column:1 / -1; }}
.admin-filtre-periode {{ display:flex; flex-wrap:wrap; align-items:end; gap:{T.SP_3}; }}
.admin-filtre-periode label {{ display:grid; gap:{T.SP_1}; }}
.admin-filtre-periode input {{ min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; font:inherit; }}
.admin-angka {{ font-size:1.75rem; color:{T.TEKS_JUDUL}; }}
.admin-info {{ display:inline-block; vertical-align:middle; font-size:1rem; font-weight:normal; }}
.admin-info summary {{ cursor:pointer; min-width:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; display:flex; align-items:center; justify-content:center; }}
.admin-info p {{ max-width:22rem; font-size:.88rem; overflow-wrap:anywhere; }}
.admin-kartu > summary {{ cursor:pointer; min-height:{T.TARGET_SENTUH}; font-weight:700; }}
.admin-grid-stat {{
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0; margin-bottom: {T.SP_4}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU_BESAR}; background: {T.LATAR_KARTU_MURID};
}}
.admin-komando {{ display: grid; grid-template-columns: minmax(0, 2.1fr) minmax(17rem, 1fr); gap: {T.SP_4}; }}
.admin-komando > *, .admin-pendukung > *, .admin-antrean > * {{ min-width: 0; }}
.admin-kartu.admin-prioritas {{ padding: 0; background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; border-color: {T.TEKS_JUDUL}; }}
.admin-prioritas-kepala {{ display: flex; justify-content: space-between; align-items: start;
  gap: {T.SP_4}; padding: {T.SP_5}; border-bottom: 1px solid {T.TEKS_VARIAN}; }}
.admin-prioritas .admin-alis {{ color: {T.BORDER_VARIAN}; }}
.admin-kartu.admin-prioritas h2 {{ margin: {T.SP_1} 0 0; color: {T.TEKS_PUTIH}; font-size: 1.35rem; }}
.admin-total-temuan {{ margin: 0; color: {T.BORDER_VARIAN}; font-size: .75rem; text-align: right; }}
.admin-total-temuan strong {{ display: block; font: 800 1.75rem {T.FONT_HEADLINE}; color: {T.AKSEN_MURID_AMBER}; }}
.admin-antrean {{ list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr)); padding: 0; margin: 0; }}
.admin-antrean-item {{ padding: {T.SP_4}; display: flex; flex-direction: column; border-right: 1px solid {T.TEKS_VARIAN}; }}
.admin-antrean-item:last-child {{ border-right: 0; }}
.admin-antrean-urutan {{ display: flex; align-items: center; justify-content: space-between; gap: {T.SP_2}; }}
.admin-antrean-urutan span {{ color: {T.BORDER_VARIAN}; font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
.admin-antrean-urutan strong {{ color: {T.AKSEN_MURID_AMBER}; font: 800 1.5rem {T.FONT_HEADLINE}; }}
.admin-prioritas .admin-antrean-item h3 {{ color: {T.TEKS_PUTIH}; font-size: 1rem; margin: {T.SP_4} 0 {T.SP_2}; }}
.admin-antrean-item p {{ color: {T.LATAR_KARTU_SEKUNDER}; font-size: .8rem; margin: 0 0 {T.SP_2}; }}
.admin-antrean-rincian {{ margin: 0 0 {T.SP_3}; padding-left: {T.SP_4}; color: {T.BORDER_VARIAN}; font-size: .75rem; }}
.admin-antrean-item p.admin-antrean-rincian {{ color: {T.BORDER_VARIAN}; }}
.admin-antrean-cta {{ display: inline-flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH};
  margin-top: auto; font-size: .8rem; font-weight: 800; color: {T.TEKS_PUTIH}; text-underline-offset: .2em; }}
.admin-antrean-cta:hover {{ color: {T.AKSEN_MURID_AMBER}; }}
.admin-antrean-rincian a {{ color: {T.TEKS_PUTIH}; display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.admin-antrean-catatan, .admin-antrean-kosong {{ margin: 0; padding: {T.SP_4} {T.SP_5}; color: {T.BORDER_VARIAN}; font-size: .75rem; }}
.admin-antrean-catatan {{ border-top: 1px solid {T.TEKS_VARIAN}; }}
.admin-layanan {{ display: flex; flex-direction: column; }}
.admin-layanan h2 {{ font-size: 1.1rem; }}
.admin-layanan dl {{ margin: 0; }}
.admin-layanan dl > div {{ display: flex; justify-content: space-between; align-items: baseline; gap: {T.SP_3}; padding: {T.SP_3} 0; border-bottom: 1px solid {T.BORDER_HALUS}; }}
.admin-layanan dt {{ color: {T.TEKS_VARIAN}; font-size: .8rem; }}
.admin-layanan dd {{ margin: 0; text-align: right; font-weight: 700; font-size: .8rem; }}
.admin-layanan .admin-meta {{ font-size: .75rem; }}
.admin-layanan-cta {{ color: {T.AKSEN_TEAL_TUA}; display: flex; justify-content: space-between; align-items: center;
  min-height: {T.TARGET_SENTUH}; font-size: .85rem; font-weight: 800; margin-top: auto; text-decoration: none; }}
.admin-pendukung {{ display: grid; grid-template-columns: minmax(0, 2fr) minmax(18rem, 1fr); gap: {T.SP_4}; align-items: start; }}
.admin-kartu.admin-aktivitas {{ padding: 0; }}
.admin-aktivitas header {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: {T.SP_2}; padding: {T.SP_4} {T.SP_5}; }}
.admin-aktivitas h2 {{ margin: 0; font-size: 1.1rem; }}
.admin-aktivitas > ul {{ list-style: none; margin: 0; padding: 0; }}
.admin-aktivitas li {{ display: flex; align-items: start; gap: {T.SP_3}; padding: {T.SP_3} {T.SP_5}; border-top: 1px solid {T.BORDER_HALUS}; }}
.admin-aktivitas li > div {{ min-width: 0; }}
.admin-aktivitas-ikon {{ display: grid; place-items: center; flex-shrink: 0; width: {T.SP_6}; height: {T.SP_6}; background: {T.LATAR_KARTU_SEKUNDER}; color: {T.TEKS_JUDUL}; border-radius: {T.RADIUS_KECIL}; font-size: .75rem; font-weight: 800; }}
.admin-aktivitas a {{ color: {T.AKSEN_TEAL_TUA}; text-underline-offset: .2em; }}
.admin-aktivitas a.admin-aktivitas-judul {{ color: {T.TEKS_JUDUL}; font-size: .9rem; font-weight: 750; }}
.admin-aktivitas p {{ margin: {T.SP_1} 0 0; font-size: .8rem; color: {T.TEKS_VARIAN}; }}
.admin-cepat h2 {{ font-size: 1.1rem; margin-bottom: {T.SP_1}; }}
.admin-cepat nav {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: {T.SP_2}; }}
.admin-cepat nav a {{ display: flex; flex-direction: column; justify-content: center; min-height: {T.TINGGI_CTA};
  padding: {T.SP_3}; border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_SEDANG}; text-decoration: none; color: {T.TEKS_JUDUL}; }}
.admin-cepat nav a:hover {{ border-color: {T.AKSEN_TEAL_TUA}; background: {T.LATAR_KARTU_SEKUNDER}; }}
.admin-cepat nav strong {{ font-size: .8rem; }}
.admin-cepat nav span {{ font-size: .75rem; color: {T.TEKS_VARIAN}; margin-top: {T.SP_1}; }}
.admin-login-detail ul {{ list-style: none; padding: 0; }}
.admin-login-detail li {{ padding: {T.SP_3} 0; border-top: 1px solid {T.BORDER_HALUS}; }}
.admin-login-detail li strong, .admin-login-detail li span {{ display: block; }}
.admin-login-detail li span {{ font-size: .85rem; color: {T.TEKS_VARIAN}; }}
.admin-definisi {{ padding: {T.SP_3} {T.SP_4}; }}
.admin-definisi > summary {{ color: {T.TEKS_JUDUL}; }}
.admin-kartu, .admin-stat {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_4};
}}
.admin-kartu {{ margin-bottom: {T.SP_4}; }}
.admin-kartu h2, .admin-kartu h3 {{ color: {T.TEKS_JUDUL}; margin-top: 0; }}
.admin-grid-stat .admin-stat {{ min-width: 0; border: 0; border-right: 1px solid {T.BORDER_HALUS}; border-radius: 0; background: transparent; }}
.admin-grid-stat .admin-stat:last-child {{ border-right: 0; }}
.admin-stat h2 {{ margin: 0 0 {T.SP_1}; color: {T.TEKS_VARIAN}; font: 700 .75rem {T.FONT_BODY}; }}
.admin-stat > div {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: {T.SP_2}; }}
.admin-stat strong {{ color: {T.TEKS_JUDUL}; font: 800 1.5rem {T.FONT_HEADLINE}; }}
.admin-stat span {{ color: {T.TEKS_VARIAN}; font-size: .75rem; }}
.admin-utama main {{ overflow-wrap: anywhere; }}
.admin-samping .admin-catatan {{ font-size: .85rem; }}
.admin-catatan {{
  background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN};
}}
.admin-galat {{
  background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; color: {T.TEKS_GALAT};
}}
.admin-form-cari {{
  display: grid; grid-template-columns: minmax(12rem, 1fr) repeat(2, minmax(9rem, auto)) auto;
  gap: {T.SP_3}; align-items: end;
}}
.admin-form-cari.admin-form-siswa {{ grid-template-columns: minmax(12rem, 1fr) repeat(3, minmax(8rem, auto)) auto; }}
.admin-form-cari label {{ min-width: 0; display: grid; gap: {T.SP_1}; color: {T.TEKS_VARIAN}; font-size: .88rem; }}
.admin-form-cari input, .admin-form-cari select {{
  width: 100%; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  color: {T.TEKS_UTAMA}; background: {T.LATAR_KARTU_MURID};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  font: inherit;
}}
.admin-tombol, .admin-tautan {{
  min-height: {T.TARGET_SENTUH}; display: inline-flex; align-items: center;
  justify-content: center; padding: {T.SP_2} {T.SP_4};
  border-radius: {T.RADIUS_KECIL}; border: 1px solid {T.BORDER_INTERAKTIF};
  font: inherit; font-weight: 700; text-decoration: none; cursor: pointer;
}}
.admin-tombol {{ color: {T.TEKS_PUTIH}; background: {T.AKSEN_TEAL_TUA}; }}
.admin-tombol:not(.admin-bahaya):hover {{ background: {T.AKSEN_TEAL_HOVER}; border-color: {T.AKSEN_TEAL_HOVER}; }}
.admin-tautan {{ color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU_SEKUNDER}; }}
.admin-bahaya {{ color: {T.TEKS_GALAT}; border-color: {T.BORDER_GALAT}; background: {T.LATAR_GALAT}; }}
.admin-form-tindakan form + form {{ margin-top: {T.SP_5}; padding-top: {T.SP_4}; border-top: 1px solid {T.BORDER_HALUS}; }}
.admin-form-tindakan label {{ display: grid; gap: {T.SP_1}; margin: {T.SP_3} 0; }}
.admin-form-tindakan input:not([type=checkbox]), .admin-form-tindakan select, .admin-kartu > form input:not([type=checkbox]), .admin-kartu > form select {{ width: 100%; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL}; font: inherit; }}
.admin-kartu label {{ display: block; margin: {T.SP_3} 0; overflow-wrap: anywhere; }}
.admin-kartu fieldset {{ min-width: 0; margin: {T.SP_3} 0; border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL}; }}
.admin-kartu fieldset label {{ min-height: {T.TARGET_SENTUH}; }}
.admin-kartu input[type=checkbox] {{ width: 1.2rem; height: 1.2rem; vertical-align: middle; margin-right: {T.SP_2}; }}
.admin-kartu form + form {{ margin-top: {T.SP_4}; }}
.admin-kartu button:not(.tombol-mata) {{ min-height: {T.TARGET_SENTUH}; margin: {T.SP_1} {T.SP_1} {T.SP_1} 0; font: inherit; cursor: pointer; }}
.kolom-sandi {{ position: relative; display: block; min-width: 0; }}
.kolom-sandi > input {{ width: 100%; padding-right: 3rem !important; }}
.tombol-mata {{
  position: absolute; top: 50%; right: .3rem; transform: translateY(-50%);
  width: 2.75rem; height: 2.75rem; display: inline-flex; align-items: center;
  justify-content: center; padding: 0; border: none; background: none;
  color: {T.TEKS_SUBTLE}; cursor: pointer; border-radius: {T.RADIUS_KECIL};
}}
.tombol-mata:hover {{ color: {T.TEKS_UTAMA}; }}
.tombol-mata svg {{ display: block; }}
.admin-tabel-wrap {{ overflow-x: auto; max-width: 100%; }}
.admin-tabel {{ width: 100%; border-collapse: collapse; min-width: 42rem; }}
.admin-tabel th, .admin-tabel td {{
  padding: {T.SP_3}; border-bottom: 1px solid {T.BORDER_HALUS};
  text-align: left; vertical-align: top;
}}
.admin-tabel th {{ color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU_SEKUNDER}; }}
.admin-tabel td[data-angka] {{ text-align: right; font-variant-numeric: tabular-nums; }}
.admin-tabel a {{ color: {T.AKSEN_TEAL_TUA}; }}
.admin-meta {{ color: {T.TEKS_VARIAN}; font-size: .85rem; }}
.admin-badge {{
  display: inline-flex; align-items: center; min-height: 1.8rem;
  margin: 0 {T.SP_1} {T.SP_1} 0; padding: {T.SP_1} {T.SP_2};
  border-radius: {T.RADIUS_PIL}; background: {T.LATAR_SEKUNDER_NETRAL};
  color: {T.TEKS_VARIAN}; font-size: .78rem; font-weight: 700;
}}
.admin-badge.perhatian {{ background: {T.LATAR_CATATAN}; color: {T.BADGE_ADMIN_TEKS}; }}
.admin-badge.batal {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; }}
.admin-daftar-status {{ margin: 0; padding-left: {T.SP_5}; }}
.admin-kosong {{ color: {T.TEKS_VARIAN}; text-align: center; padding: {T.SP_6}; }}
.admin-pager {{
  display: flex; flex-wrap: wrap; justify-content: space-between;
  align-items: center; gap: {T.SP_2}; margin-top: {T.SP_4};
}}
.admin-pager form {{ margin: 0; }}
.admin-pager button {{
  min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  border: 1px solid {T.BORDER_INTERAKTIF}; border-radius: {T.RADIUS_KECIL};
  background: {T.LATAR_KARTU_SEKUNDER}; color: {T.TEKS_JUDUL}; font: inherit;
}}
.admin-rincian {{ display: grid; grid-template-columns: 11rem 1fr; gap: {T.SP_2} {T.SP_4}; }}
.admin-rincian dt {{ color: {T.TEKS_VARIAN}; font-weight: 700; }}
.admin-rincian dd {{ margin: 0; overflow-wrap: anywhere; }}
.admin-aksi-baca {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.admin-footer {{ margin-top: {T.SP_6}; color: {T.TEKS_VARIAN}; font-size: .82rem; }}
:focus-visible {{ outline: 3px solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.admin-sidebar :focus-visible, .admin-prioritas :focus-visible {{ outline-color: {T.AKSEN_MURID_AMBER}; }}
@media (max-width: 75rem) {{
  .admin-form-cari, .admin-form-cari.admin-form-siswa {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .admin-form-cari > :first-child {{ grid-column: 1 / -1; }}
  .admin-komando, .admin-pendukung {{ grid-template-columns: minmax(0, 1fr); }}
  .admin-layanan dl {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: {T.SP_5}; }}
}}
@media (max-width: 56rem) {{
  .admin-layout {{ display: block; }}
  .admin-sidebar {{ display: none; }}
  .admin-konteks {{ display: none; }}
  .admin-nav-mobile {{ display: block; position: relative; min-width: 0; }}
  .admin-nav-mobile > nav {{ position: absolute; left: 0; z-index: 10; width: min(28rem, calc(100vw - {T.SP_6})); grid-template-columns: 1fr 1fr; }}
  .admin-topbar {{ align-items: start; }}
  .admin-topbar .menu-pengguna {{ max-width: 50%; }}
  .admin-grid-stat .admin-stat:nth-child(2) {{ border-right: 0; }}
  .admin-grid-stat .admin-stat:nth-child(-n+2) {{ border-bottom: 1px solid {T.BORDER_HALUS}; }}
  .admin-grid-stat {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .admin-form-cari, .admin-form-cari.admin-form-siswa {{ grid-template-columns: 1fr 1fr; }}
  .admin-form-cari > :first-child {{ grid-column: 1 / -1; }}
}}
@media (max-width: 32rem) {{
  .admin-utama {{ padding: 0 {T.SP_4} {T.SP_5}; }}
  .admin-kepala {{ margin: {T.SP_5} 0; }}
  .admin-kepala h1 {{ font-size: 1.6rem; }}
  .admin-sub {{ font-size: .9rem; }}
  .admin-nav-mobile > nav {{ grid-template-columns: 1fr; }}
  .admin-antrean {{ grid-template-columns: minmax(0, 1fr); }}
  .admin-antrean-item {{ border-right: 0; border-bottom: 1px solid {T.TEKS_VARIAN}; }}
  .admin-antrean-item:last-child {{ border-bottom: 0; }}
  .admin-prioritas-kepala {{ padding: {T.SP_4}; gap: {T.SP_2}; }}
  .admin-prioritas-kepala > div {{ min-width: 0; }}
  .admin-kartu.admin-prioritas h2 {{ font-size: 1.2rem; }}
  .admin-total-temuan {{ flex: 0 0 5rem; font-size: .7rem; }}
  .admin-antrean-item p, .admin-antrean-rincian, .admin-antrean-item p.admin-antrean-rincian {{ font-size: .875rem; }}
  .admin-antrean-item .admin-antrean-rincian {{ margin-bottom: {T.SP_1}; }}
  .admin-antrean-catatan, .admin-antrean-kosong {{ padding: {T.SP_4}; }}
  .admin-layanan dl {{ grid-template-columns: 1fr; }}
  .admin-aktivitas header, .admin-aktivitas li {{ padding-left: {T.SP_4}; padding-right: {T.SP_4}; }}
  .admin-nav-mobile > summary {{ display: flex; flex-wrap: wrap; gap: {T.SP_1} {T.SP_2}; }}
  .admin-topbar .menu-pengguna .admin-badge {{ display: none; }}
  .admin-topbar .menu-isi {{ min-width: 10rem; max-width: calc(100vw - {T.SP_6}); }}
  .admin-form-cari, .admin-form-cari.admin-form-siswa {{ grid-template-columns: 1fr; }}
  .admin-form-cari > :first-child {{ grid-column: auto; }}
  .admin-rincian {{ grid-template-columns: 1fr; gap: 0; }}
  .admin-rincian dd {{ margin-bottom: {T.SP_3}; }}
}}
@media print {{ .admin-sidebar, .admin-nav-mobile, .admin-form-cari, .admin-pager {{ display: none; }} .admin-layout {{ display: block; }} }}
"""
