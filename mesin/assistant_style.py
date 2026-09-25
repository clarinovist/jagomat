"""Gaya Pendamping: aliran dokumen ringan, token lokal, tanpa skrip/font jaringan."""

import design_tokens as T

GAYA_PENDAMPING = f"""
.pendamping-halaman, .pendamping-halaman *, .pendamping-halaman *::before, .pendamping-halaman *::after {{ box-sizing:border-box; }}
html {{ color-scheme:light; scroll-padding-block:{T.SP_5}; }}
.pendamping-halaman {{ margin:0; min-height:100vh; min-height:100svh; background:{T.LATAR_MURID}; color:{T.TEKS_UTAMA}; font:1rem/1.6 {T.FONT_LAYAR}; overflow-wrap:anywhere; }}
.pendamping-halaman img, .pendamping-halaman svg {{ max-width:100%; vertical-align:middle; }}
.pendamping-halaman a {{ color:{T.AKSEN_TEAL_TUA}; text-underline-offset:.22em; }}
.pendamping-halaman a:hover {{ text-decoration-thickness:.13em; }}
.pendamping-halaman button, .pendamping-halaman input, .pendamping-halaman textarea {{ font:inherit; max-width:100%; }}
.pendamping-halaman button, .pendamping-halaman summary {{ cursor:pointer; }}
.pendamping-halaman a, .pendamping-halaman button, .pendamping-halaman summary, .pendamping-halaman textarea {{ touch-action:manipulation; }}
.pendamping-halaman :focus-visible {{ outline:3px solid {T.AKSEN_TEAL_TUA}; outline-offset:4px; }}
.pendamping-bungkus:focus {{ outline-offset:-3px; }}
.pendamping-halaman :target {{ scroll-margin-block:{T.SP_5}; }}
.pendamping-sr {{ position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:clip; clip-path:inset(50%); white-space:nowrap; border:0; }}
.pendamping-lewati {{ position:absolute; inset-block-start:{T.SP_3}; inset-inline-start:{T.SP_4}; transform:translateY(-200%); min-height:{T.TARGET_SENTUH}; padding:{T.SP_3} {T.SP_4}; background:{T.LATAR_KARTU}; border:1px solid {T.AKSEN_TEAL_TUA}; border-radius:{T.RADIUS_KECIL}; z-index:1; }}
.pendamping-lewati:focus {{ transform:none; }}
.pendamping-halaman h1, .pendamping-halaman h2 {{ color:{T.TEKS_JUDUL}; line-height:1.3; text-wrap:pretty; }}
.pendamping-halaman h1 {{ margin:0 0 {T.SP_3}; font-size:clamp(1.6rem, 2.5vw, 1.875rem); letter-spacing:-.035em; font-weight:650; }}
.pendamping-halaman h2 {{ margin:0 0 {T.SP_2}; font-size:1.125rem; font-weight:650; }}
.pendamping-halaman p {{ margin:0 0 {T.SP_4}; }}
.pendamping-halaman strong {{ font-weight:650; }}
.pendamping-halaman small, .pendamping-catatan {{ color:{T.TEKS_VARIAN}; }}
.pendamping-halaman small {{ font-size:.8125rem; }}
.pendamping-catatan {{ font-size:.875rem; }}
.pendamping-halaman ul {{ padding-inline-start:{T.SP_5}; margin:{T.SP_3} 0 {T.SP_5}; }}
.pendamping-halaman li + li {{ margin-block-start:{T.SP_2}; }}
.pendamping-halaman blockquote {{ margin:{T.SP_4} 0; line-height:1.65; }}
.pendamping-halaman code {{ font-size:.875em; white-space:normal; overflow-wrap:anywhere; }}

/* Header tunggal, disclosure native mendorong isi; bukan sidebar/overlay. */
.pendamping-kepala {{ width:min(100%, 72rem); margin-inline:auto; padding:{T.SP_4} {T.SP_6}; }}
.pendamping-baris-kepala {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:{T.SP_3} {T.SP_5}; min-height:{T.TARGET_SENTUH}; }}
.pendamping-merek {{ display:flex; flex-wrap:wrap; align-items:center; gap:{T.SP_2}; min-width:0; min-height:{T.TARGET_SENTUH}; color:{T.AKSEN_TEAL_TUA}; text-decoration:none; }}
.pendamping-merek img {{ width:{T.LOGO_TOPBAR}; height:{T.LOGO_TOPBAR}; flex:0 0 auto; }}
.pendamping-merek strong {{ font-size:1.375rem; font-weight:750; letter-spacing:-.04em; }}
.pendamping-merek span {{ margin-inline-start:{T.SP_2}; padding-inline-start:{T.SP_4}; border-inline-start:1px solid {T.BORDER_VARIAN}; color:{T.TEKS_VARIAN}; font-size:.875rem; }}
.pendamping-navigasi {{ display:flex; flex-wrap:wrap; align-items:flex-start; justify-content:flex-end; gap:{T.SP_1} {T.SP_2}; min-width:0; }}
.pendamping-navigasi > a, .pendamping-navigasi summary {{ display:inline-flex; align-items:center; justify-content:center; gap:{T.SP_2}; min-width:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} {T.SP_3}; border-radius:{T.RADIUS_SEDANG}; color:{T.TEKS_UTAMA}; font-size:.875rem; text-decoration:none; }}
.pendamping-navigasi a:hover, .pendamping-navigasi summary:hover {{ background:{T.LATAR_KARTU}; }}
.pendamping-navigasi > details {{ margin:0; min-width:0; }}
.pendamping-navigasi > details[open] {{ flex-basis:100%; }}
.pendamping-baris-kepala:has(.pendamping-navigasi details[open]) {{ align-items:flex-start; }}
.pendamping-baris-kepala:has(.pendamping-navigasi details[open]) > .pendamping-navigasi {{ flex-basis:100%; justify-content:flex-start; }}
.pendamping-navigasi summary {{ list-style:none; }}
.pendamping-navigasi summary::-webkit-details-marker {{ display:none; }}
.pendamping-navigasi summary::after {{ content:""; width:.375rem; height:.375rem; border-inline-end:1px solid {T.TEKS_VARIAN}; border-block-end:1px solid {T.TEKS_VARIAN}; transform:rotate(45deg); margin-block-start:-.2rem; }}
.pendamping-navigasi details[open] > summary::after {{ transform:rotate(225deg); margin-block-start:.2rem; }}
.pendamping-riwayat > .pendamping-rincian, .pendamping-menu > nav {{ max-width:{T.LEBAR_KONTEN}; }}
.pendamping-menu > nav {{ display:flex; flex-wrap:wrap; gap:{T.SP_1} {T.SP_3}; }}

/* Kolom baca; awal hanya satu composer dengan ruang kosong yang tenang. */
.pendamping-bungkus {{ width:min({T.LEBAR_KONTEN}, calc(100% - 3rem)); min-width:0; margin-inline:auto; padding-block:2.5rem 3.5rem; }}
.pendamping-bungkus.pendamping-awal {{ display:flex; flex-direction:column; justify-content:center; min-height:min(62vh, 38rem); min-height:min(62svh, 38rem); padding-block:{T.SP_6} 5rem; }}
.pendamping-awal > .pendamping-status {{ align-self:flex-start; }}
.pendamping-awal > .pendamping-form + .pendamping-catatan {{ margin-block-start:{T.SP_3}; }}
.pendamping-bungkus.pendamping-chat {{ padding-block-start:{T.SP_6}; }}
.pendamping-form {{ width:100%; min-width:0; margin:0; }}
.pendamping-label {{ display:block; margin-block-end:{T.SP_2}; color:{T.TEKS_VARIAN}; font-size:.875rem; font-weight:550; }}
.pendamping-composer-kotak {{ display:flex; align-items:flex-end; gap:{T.SP_3}; padding:.875rem; padding-inline-start:1.25rem; background:{T.LATAR_KARTU}; border:1px solid {T.TEKS_VARIAN}; border-radius:1.75rem; min-width:0; }}
.pendamping-composer-kotak:focus-within {{ border-color:{T.AKSEN_TEAL_TUA}; }}
.pendamping-input {{ display:block; width:100%; min-width:0; resize:vertical; background:{T.LATAR_KARTU}; color:{T.TEKS_UTAMA}; border:1px solid {T.TEKS_VARIAN}; border-radius:{T.RADIUS_SEDANG}; padding:{T.SP_3} {T.SP_4}; font-size:1rem; line-height:1.5; }}
.pendamping-composer-kotak textarea {{ min-height:3.5rem; height:3.5rem; padding:{T.SP_1} 0; border:0; border-radius:{T.SP_1}; }}
.pendamping-input::placeholder {{ color:{T.TEKS_VARIAN}; opacity:1; }}
.pendamping-composer-kotak .pendamping-kirim {{ display:inline-flex; flex:0 0 {T.TARGET_SENTUH}; align-items:center; justify-content:center; width:{T.TARGET_SENTUH}; height:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; border-radius:{T.RADIUS_BULAT}; }}
.pendamping-composer-meta {{ margin:.625rem {T.SP_1} 0 !important; color:{T.TEKS_VARIAN}; font-size:.8125rem; line-height:1.6; }}
.pendamping-chat > .pendamping-form {{ margin-block-start:clamp(2rem, 7vh, 4.5rem); }}

/* Bubble hanya untuk orang tua; jawaban asisten terbuka. */
.pendamping-pesan {{ min-width:0; margin-block:0 {T.SP_6}; }}
.pendamping-pesan .pendamping-peran {{ margin-block-end:.625rem; color:{T.TEKS_VARIAN}; font-size:.8125rem; font-weight:600; }}
.pendamping-teks {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
.pendamping-pesan > :last-child {{ margin-block-end:0; }}
.pendamping-pesan.pengguna {{ width:fit-content; max-width:84%; margin-inline-start:auto; padding:{T.SP_4} 1.25rem; border-radius:1.5rem 1.5rem .375rem 1.5rem; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.pendamping-pesan.asisten {{ padding-block:{T.SP_1} {T.SP_2}; background:none; border:0; }}
.pendamping-pesan.asisten .pendamping-peran {{ color:{T.AKSEN_TEAL_TUA}; }}
.pendamping-pesan.asisten p {{ line-height:1.75; }}

.pendamping-panel {{ min-width:0; margin-block:{T.SP_5}; padding:{T.SP_5}; border:1px solid {T.BORDER_VARIAN}; border-radius:{T.SP_4}; background:{T.LATAR_KARTU}; }}
.pendamping-panel > :last-child {{ margin-block-end:0; }}
.pendamping-memori > .pendamping-teks {{ font-size:1.125rem; line-height:1.65; }}
.pendamping-usulan > h2 {{ font-size:1.25rem; }}
.pendamping-status {{ display:inline-flex; align-items:center; max-width:100%; margin:0 0 .875rem; padding:{T.SP_1} .625rem; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.TEKS_VARIAN}; font-size:.8125rem; }}
.pendamping-hasil .pendamping-status {{ background:{T.LATAR_TERSIMPAN}; color:{T.TEKS_TERSIMPAN}; }}
.pendamping-info, .pendamping-galat {{ margin-block:{T.SP_4}; padding:.875rem {T.SP_4}; border-inline-start:3px solid {T.AKSEN_TEAL_TUA}; border-radius:0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0; background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.TEKS_UTAMA}; font-size:.9375rem; }}
.pendamping-galat {{ border-color:{T.TEKS_GALAT}; background:{T.LATAR_GALAT}; color:{T.TEKS_GALAT}; }}
.pendamping-info a {{ color:{T.TEKS_JUDUL}; }}
.pendamping-galat a {{ color:{T.TEKS_GALAT}; }}
.pendamping-halaman dl {{ display:grid; grid-template-columns:minmax(6rem, 1fr) minmax(0, 2fr); gap:.625rem {T.SP_4}; margin:1.25rem 0; }}
.pendamping-halaman dt {{ min-width:0; color:{T.TEKS_VARIAN}; font-size:.875rem; }}
.pendamping-halaman dd {{ min-width:0; margin:0; }}
.pendamping-editor {{ min-height:8rem; margin-block:{T.SP_2} {T.SP_3}; line-height:1.65; }}
.pendamping-halaman [aria-invalid="true"] {{ border-color:{T.TEKS_GALAT}; }}
.pendamping-cek {{ display:flex; align-items:flex-start; gap:{T.SP_3}; min-height:{T.TARGET_SENTUH}; padding-block:{T.SP_3}; font-size:.9375rem; }}
.pendamping-cek input {{ flex:0 0 auto; width:1.25rem; height:1.25rem; margin:.125rem 0 0; accent-color:{T.AKSEN_TEAL_TUA}; }}
.pendamping-tombol, .pendamping-tautan {{ display:inline-flex; align-items:center; justify-content:center; gap:{T.SP_2}; min-width:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; max-width:100%; padding:.625rem .875rem; border-radius:{T.RADIUS_SEDANG}; font-size:.875rem; line-height:1.45; text-align:center; white-space:normal; overflow-wrap:anywhere; }}
.pendamping-tombol {{ border:1px solid {T.AKSEN_TEAL_TUA}; background:{T.AKSEN_TEAL_TUA}; color:{T.TEKS_PUTIH}; text-decoration:none; font-weight:550; cursor:pointer; }}
.pendamping-tombol:not(.pendamping-sekunder):not(.pendamping-bahaya):hover {{ background:{T.AKSEN_TEAL_HOVER}; border-color:{T.AKSEN_TEAL_HOVER}; }}
.pendamping-halaman a.pendamping-tombol {{ color:{T.TEKS_PUTIH}; }}
.pendamping-tombol.pendamping-sekunder, .pendamping-halaman a.pendamping-tombol.pendamping-sekunder {{ border-color:{T.TEKS_VARIAN}; background:{T.LATAR_KARTU}; color:{T.TEKS_UTAMA}; }}
.pendamping-tombol.pendamping-bahaya, .pendamping-halaman a.pendamping-tombol.pendamping-bahaya {{ border-color:{T.TEKS_GALAT}; background:{T.LATAR_KARTU}; color:{T.TEKS_GALAT}; }}
.pendamping-tautan.pendamping-bahaya {{ color:{T.TEKS_GALAT}; }}
.pendamping-aksi {{ display:flex; flex-wrap:wrap; align-items:center; gap:{T.SP_2} {T.SP_3}; margin-block:{T.SP_4} 0; }}
.pendamping-aksi > * {{ min-width:0; max-width:100%; }}
.pendamping-sumber {{ margin-block:{T.SP_3}; color:{T.TEKS_VARIAN}; font-size:.875rem; }}
.pendamping-sumber p {{ margin-block-end:{T.SP_1}; }}
.pendamping-sumber .pendamping-tautan {{ padding-inline:0; }}
.pendamping-halaman details {{ min-width:0; margin-block:{T.SP_2}; }}
.pendamping-halaman summary {{ min-height:{T.TARGET_SENTUH}; padding:.625rem {T.SP_1}; color:{T.TEKS_VARIAN}; font-size:.875rem; line-height:1.65; list-style-position:inside; }}
.pendamping-halaman summary::marker {{ color:{T.AKSEN_TEAL_TUA}; }}
.pendamping-halaman summary:hover, .pendamping-halaman details[open] > summary {{ color:{T.AKSEN_TEAL_TUA}; }}
.pendamping-rincian {{ padding:{T.SP_2} {T.SP_1} {T.SP_3}; min-width:0; font-size:.875rem; }}
.pendamping-daftar-riwayat {{ display:grid; grid-template-columns:minmax(0, 1fr); gap:0; min-width:0; margin-block:{T.SP_2} {T.SP_4}; }}
.pendamping-daftar-riwayat > a {{ display:flex; flex-direction:column; justify-content:center; align-items:flex-start; gap:.2rem; min-width:0; min-height:{T.TARGET_SENTUH}; padding:.875rem {T.SP_4}; border-block-end:1px solid {T.BORDER_VARIAN}; color:{T.TEKS_UTAMA}; text-decoration:none; }}
.pendamping-daftar-riwayat > a > strong {{ font-size:.9375rem; font-weight:550; font-variant-numeric:tabular-nums; }}
.pendamping-daftar-riwayat > a:hover {{ background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.pendamping-daftar-riwayat > a[aria-current="page"] {{ border-inline-start:3px solid {T.AKSEN_TEAL_TUA}; padding-inline-start:calc(1rem - 3px); background:{T.LATAR_KARTU}; }}
.pendamping-daftar-riwayat > a[aria-current="page"] > strong {{ color:{T.AKSEN_TEAL_TUA}; font-weight:650; }}

@media (max-width:48rem) {{
 .pendamping-kepala {{ padding:.875rem {T.SP_5}; }}
 .pendamping-merek span {{ display:none; }}
}}
@media (max-width:30rem) {{
 .pendamping-kepala {{ padding:{T.SP_3} {T.SP_4}; }}
 .pendamping-baris-kepala {{ gap:.375rem {T.SP_3}; }}
 .pendamping-merek {{ gap:.375rem; }}
 .pendamping-merek strong {{ font-size:1.25rem; }}
 .pendamping-navigasi {{ gap:0 .125rem; }}
 .pendamping-navigasi > a, .pendamping-navigasi summary {{ gap:{T.SP_1}; padding-inline:.375rem; font-size:.8125rem; }}
 .pendamping-bungkus {{ width:calc(100% - 2rem); padding-block:{T.SP_5} 2.5rem; }}
 .pendamping-bungkus.pendamping-awal {{ padding-block:{T.SP_6} 3.5rem; }}
 .pendamping-bungkus.pendamping-chat {{ padding-block-start:{T.SP_5}; }}
 .pendamping-composer-kotak {{ gap:{T.SP_2}; padding:{T.SP_3}; padding-inline-start:{T.SP_4}; border-radius:{T.SP_5}; }}
 .pendamping-pesan {{ margin-block-end:1.75rem; }}
 .pendamping-pesan.pengguna {{ max-width:92%; padding:.875rem {T.SP_4}; }}
 .pendamping-panel {{ padding:1.125rem; margin-block:1.25rem; }}
 .pendamping-halaman dl {{ grid-template-columns:minmax(0, 1fr); gap:{T.SP_1}; }}
 .pendamping-halaman dd + dt {{ margin-block-start:.625rem; }}
}}
@media (max-width:23rem) {{
 .pendamping-baris-kepala {{ align-items:flex-start; }}
 .pendamping-navigasi {{ width:100%; justify-content:flex-start; }}
}}
@media (forced-colors:active) {{
 .pendamping-pesan.pengguna {{ border:1px solid; }}
}}
"""
