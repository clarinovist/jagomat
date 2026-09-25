"""Gaya scoped untuk kandidat pusat kendali admin readonly."""

import design_tokens as T


GAYA_ADMIN = f"""
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body.admin-readonly {{
  margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_UTAMA};
  font-family: {T.FONT_LAYAR}; font-size: {T.UKURAN_BADAN_LAYAR};
  line-height: {T.LINE_HEIGHT};
}}
.admin-bungkus {{
  width: min({T.LEBAR_LANDING}, calc(100% - {T.SP_6}));
  margin: 0 auto; padding: {T.SP_4} 0 {T.SP_6};
}}
.admin-lompat {{
  position: absolute; left: {T.SP_2}; top: -10rem; z-index: 10;
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH};
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL};
}}
.admin-lompat:focus {{ top: {T.SP_2}; }}
.admin-topbar {{
  display: flex; justify-content: space-between; align-items: center;
  gap: {T.SP_3}; padding: {T.SP_2} 0 {T.SP_3};
  border-bottom: 1px solid {T.BORDER_HALUS};
}}
.admin-brand {{ color: {T.WARNA_WORDMARK}; font-weight: 800; text-decoration: none; }}
.admin-topbar .menu-pengguna {{ position: relative; min-width: 0; }}
.admin-topbar .menu-pengguna summary {{ cursor: pointer; overflow-wrap: anywhere; padding: {T.SP_2}; }}
.admin-topbar .menu-isi {{ position: absolute; right: 0; z-index: 20;
  min-width: 12rem; padding: {T.SP_3}; background: {T.LATAR_KARTU_MURID};
  border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL}; }}
.admin-topbar .menu-isi a {{ display: block; padding: {T.SP_2}; color: {T.AKSEN_TEAL_TUA}; }}
.admin-topbar .menu-isi button {{ width: 100%; min-height: {T.TARGET_SENTUH}; margin-top: {T.SP_2}; }}
.admin-identitas {{ color: {T.TEKS_VARIAN}; font-size: .88rem; overflow-wrap: anywhere; }}
.admin-kepala {{ margin: {T.SP_5} 0; }}
.admin-alis {{
  margin: 0; color: {T.AKSEN_TEAL_TUA}; font-size: .75rem;
  font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
}}
.admin-kepala h1 {{ margin: {T.SP_1} 0; color: {T.TEKS_JUDUL}; font-size: clamp(1.55rem, 3vw, 2.2rem); }}
.admin-sub {{ margin: 0; color: {T.TEKS_VARIAN}; }}
.admin-nav {{
  display: flex; gap: {T.SP_2}; overflow-x: auto; padding: 0 0 {T.SP_3};
  margin-bottom: {T.SP_5}; border-bottom: 1px solid {T.BORDER_HALUS};
}}
.admin-nav a {{
  flex: 0 0 auto; min-height: {T.TARGET_SENTUH}; display: inline-flex;
  align-items: center; padding: 0 {T.SP_3}; border-radius: {T.RADIUS_PIL};
  color: {T.TEKS_VARIAN}; text-decoration: none; font-weight: 650;
}}
.admin-nav a[aria-current="page"] {{
  color: {T.TEKS_PUTIH}; background: {T.AKSEN_TEAL_TUA};
}}
@media (max-width: 48rem) {{
  .admin-nav {{ flex-wrap:wrap; overflow:visible; gap:{T.SP_1}; }}
  .admin-nav a {{ padding:0 {T.SP_2}; font-size:.88rem; }}
}}
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
  gap: {T.SP_3}; margin-bottom: {T.SP_5};
}}
.admin-kartu, .admin-stat {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_4};
}}
.admin-kartu {{ margin-bottom: {T.SP_4}; }}
.admin-kartu h2, .admin-kartu h3 {{ color: {T.TEKS_JUDUL}; margin-top: 0; }}
.admin-stat strong {{ display: block; color: {T.TEKS_JUDUL}; font-size: 1.75rem; }}
.admin-stat span {{ color: {T.TEKS_VARIAN}; font-size: .88rem; }}
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
.admin-form-cari label {{ display: grid; gap: {T.SP_1}; color: {T.TEKS_VARIAN}; font-size: .88rem; }}
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
@media (max-width: 56rem) {{
  .admin-grid-stat {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .admin-form-cari, .admin-form-cari.admin-form-siswa {{ grid-template-columns: 1fr 1fr; }}
  .admin-form-cari > :first-child {{ grid-column: 1 / -1; }}
}}
@media (max-width: 32rem) {{
  .admin-bungkus {{ width: min(100% - {T.SP_4}, {T.LEBAR_LANDING}); }}
  .admin-topbar {{ align-items: flex-start; flex-direction: column; }}
  .admin-topbar .menu-pengguna {{ width: 100%; }}
  .admin-topbar .menu-isi {{ position: static; min-width: 0; width: 100%; }}
  .admin-grid-stat, .admin-form-cari, .admin-form-cari.admin-form-siswa {{ grid-template-columns: 1fr; }}
  .admin-form-cari > :first-child {{ grid-column: auto; }}
  .admin-rincian {{ grid-template-columns: 1fr; gap: 0; }}
  .admin-rincian dd {{ margin-bottom: {T.SP_3}; }}
}}
@media print {{ .admin-nav, .admin-form-cari, .admin-pager {{ display: none; }} }}
"""
