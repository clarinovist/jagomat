"""CSS komponen ceria bersama (`GAYA_CERIA`) untuk halaman anak dan Ayah/Bunda gaya landing page.

Namespace `ceria-`. Markup-nya ada di `playful_components`. Semua nilai dari `design_tokens`
(tanpa warna literal). Bukan bagian `gaya_stitch()`: halaman yang memakainya menambahkan
`GAYA_CERIA` sendiri ke `<head>`, jadi byte halaman lain tidak berubah.

Animasi hanya didefinisikan di dalam `prefers-reduced-motion: no-preference`; keadaan diam
(tanpa animasi) selalu lengkap terlihat. Status tidak pernah hanya warna: titik hari memakai
teks tersembunyi, banner umpan balik selalu berteks.
"""
from __future__ import annotations

import design_tokens as T

_UKURAN_TITIK = "1.1rem"
_TINGGI_SEGMEN = "8px"

GAYA_CERIA = f"""
/* Hero teal: simbol matematika samar dan konfeti statis. */
.ceria-hero {{ position: relative; overflow: hidden; display: flex; flex-direction: column; gap: {T.SP_3};
  padding: {T.SP_4} {T.SP_4} {T.SP_5}; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.ceria-hero > * {{ position: relative; z-index: 2; margin: 0; }}
.ceria-hero > .ceria-simbol, .ceria-hero > .ceria-konfeti {{ position: absolute; inset: 0; z-index: 1; pointer-events: none; }}
.ceria-simbol b {{ position: absolute; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_DOODLE}; font-weight: 800; line-height: 1; color: {T.DOODLE_PUTIH}; }}
.ceria-simbol b:nth-child(1) {{ left: 3%; top: 14%; }}
.ceria-simbol b:nth-child(2) {{ right: 4%; top: 18%; }}
.ceria-simbol b:nth-child(3) {{ left: 46%; bottom: 4%; }}
.ceria-simbol b:nth-child(4) {{ right: 9%; bottom: 14%; transform: rotate(10deg); }}
.ceria-konfeti i {{ position: absolute; width: 8px; height: 13px; border-radius: 2px; background: {T.AKSEN_MURID_AMBER}; }}
.ceria-konfeti i:nth-child(1) {{ left: 12%; top: 18%; transform: rotate(25deg); }}
.ceria-konfeti i:nth-child(2) {{ left: 30%; top: 8%; background: {T.AKSEN_MURID_KORAL}; transform: rotate(-30deg); }}
.ceria-konfeti i:nth-child(3) {{ left: 52%; top: 14%; background: {T.TEKS_PUTIH}; transform: rotate(60deg); }}
.ceria-konfeti i:nth-child(4) {{ left: 74%; top: 7%; transform: rotate(-12deg); }}
.ceria-konfeti i:nth-child(5) {{ left: 88%; top: 20%; background: {T.AKSEN_MURID_KORAL}; transform: rotate(40deg); }}
.ceria-konfeti i:nth-child(6) {{ left: 64%; top: 30%; width: 6px; height: 6px; background: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_BULAT}; }}
.ceria-konfeti i:nth-child(7) {{ left: 20%; top: 34%; width: 6px; height: 6px; background: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_BULAT}; }}
.ceria-konfeti i:nth-child(8) {{ left: 92%; top: 44%; transform: rotate(-50deg); }}

/* Maskot + gelembung bicara. */
.ceria-maskot-baris {{ display: flex; align-items: flex-end; gap: {T.SP_2}; }}
.ceria-maskot {{ flex: none; display: block; height: auto; filter: {T.BAYANGAN_MASKOT}; }}
.ceria-gelembung {{ position: relative; margin: 0 0 {T.SP_5}; padding: {T.SP_3} {T.SP_4}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL};
  border-radius: 16px 16px 16px 4px; font-weight: 600; line-height: 1.4; box-shadow: {T.BAYANGAN_TIMBUL_GELAP}; }}
.ceria-gelembung::before {{ content: ""; position: absolute; left: -7px; bottom: 6px; border: 7px solid transparent; border-left: 0; border-right-color: {T.LATAR_KARTU}; }}
.ceria-gelembung b {{ color: {T.AKSEN_KORAL_TUA}; }}

/* Teks di dalam hero (judul, alis, petunjuk): putih di atas teal. */
.ceria-hero :is(h1, h2, h3) {{ color: {T.TEKS_PUTIH}; }}
.ceria-hero .ceria-alis-hero {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; letter-spacing: .09em; color: {T.TEKS_DI_TEAL}; }}
.ceria-hero .ceria-hint-hero {{ display: block; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_DI_TEAL}; }}
.ceria-hero > p {{ color: {T.TEKS_DI_TEAL}; }}

/* Skor besar sesi + deretan titik (terisi = benar). */
.ceria-hero .ceria-skor {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 700; color: {T.TEKS_DI_TEAL}; }}
.ceria-skor b {{ font-size: {T.UKURAN_ANGKA_FUNNEL}; font-weight: 800; line-height: 1; color: {T.TEKS_PUTIH}; }}
.ceria-bintang {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.ceria-bintang i {{ display: block; width: 15px; height: 15px; border-radius: {T.RADIUS_BULAT}; border: 2px solid {T.TEKS_DI_TEAL_REDUP}; }}
.ceria-bintang i.ceria-isi {{ background: {T.AKSEN_MURID_AMBER}; border-color: {T.AKSEN_MURID_AMBER}; }}

/* Stiker miring dan kata kunci bergaris. Sorot hanya untuk latar gelap (navy/teal). */
.ceria-stiker {{ display: inline-block; align-self: flex-start; padding: {T.SP_1} {T.SP_3}; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL};
  font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 800; border-radius: {T.RADIUS_KECIL};
  box-shadow: {T.BAYANGAN_TIMBUL_GELAP}; transform: rotate(-4deg); }}
.ceria-stiker.ceria-miring-kanan {{ transform: rotate(1.2deg); }}
.ceria-sorot {{ color: {T.AKSEN_MURID_AMBER}; text-decoration: underline; text-decoration-color: {T.AKSEN_MURID_KORAL};
  text-decoration-thickness: 3px; text-underline-offset: 3px; }}

/* Kartu navy ajakan untuk orang dewasa pembayar: satu tautan saja. */
.ceria-ortu {{ display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_5}; background: {T.TEKS_JUDUL}; color: {T.TEKS_DI_NAVY};
  border-radius: {T.RADIUS_KARTU_BESAR}; }}
.ceria-ortu > * {{ margin: 0; }}
.ceria-alis {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: {T.AKSEN_MURID_AMBER}; }}
.ceria-ortu .ceria-judul {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; line-height: 1.25; color: {T.TEKS_PUTIH}; }}
.ceria-centang {{ display: flex; flex-direction: column; gap: {T.SP_1}; margin: 0; padding: 0; list-style: none; color: {T.TEKS_DI_NAVY_REDUP}; }}
.ceria-centang li::before {{ content: "\\2713"; margin-right: {T.SP_2}; font-weight: 800; color: {T.AKSEN_MURID_AMBER}; }}
.ceria-tombol {{ display: flex; align-items: center; justify-content: center; min-height: {T.TINGGI_CTA}; padding: 0 {T.SP_5}; text-align: center;
  font-family: {T.FONT_HEADLINE}; font-weight: 800; text-decoration: none; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_PIL}; box-shadow: 0 4px 0 {T.AKSEN_KORAL_TEPI}; }}
.ceria-tombol:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.ceria-ortu :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.AKSEN_MURID_AMBER}; outline-offset: 3px; }}

/* Kartu status lembut (kuning menunggu, hijau aman, koral perlu tindakan) dengan lencana teks. */
.ceria-status {{ display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_2}; padding: {T.SP_4}; border: {T.TEBAL_GARIS} solid;
  border-radius: {T.RADIUS_KARTU_BESAR}; }}
.ceria-status > * {{ margin: 0; }}
.ceria-status .ceria-judul {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; line-height: 1.25; color: inherit; }}
.ceria-status > p {{ line-height: 1.5; }}
.ceria-status .ceria-tombol {{ align-self: stretch; margin-top: {T.SP_1}; }}
.ceria-status-kuning {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; color: {T.ANAK_PERHATIAN_TEKS}; }}
.ceria-status-hijau {{ background: {T.LATAR_TERSIMPAN}; border-color: {T.BORDER_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.ceria-status-koral {{ background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; color: {T.TEKS_GALAT}; }}
.ceria-lencana {{ display: inline-block; white-space: nowrap; padding: 2px {T.SP_3}; background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid; border-radius: {T.RADIUS_PIL};
  font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; }}
.ceria-lencana-kuning {{ color: {T.AKSEN_AMBER_TUA}; border-color: {T.BORDER_CATATAN}; }}
.ceria-lencana-hijau {{ color: {T.TEKS_TERSIMPAN}; border-color: {T.BORDER_TERSIMPAN}; }}
.ceria-lencana-koral {{ color: {T.TEKS_GALAT}; border-color: {T.BORDER_GALAT}; }}
.ceria-status :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}

/* Deretan titik 7 hari: varian di atas teal (bawaan) dan di atas krem. */
.ceria-titik {{ display: flex; gap: {T.SP_2}; margin: 0; padding: 0; list-style: none; }}
.ceria-titik li {{ flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: {T.SP_1};
  font-size: {T.UKURAN_TEKS_META}; font-weight: 600; color: {T.TEKS_DI_TEAL}; }}
.ceria-titik i {{ display: block; width: {_UKURAN_TITIK}; height: {_UKURAN_TITIK}; border-radius: {T.RADIUS_BULAT}; border: 2px solid {T.TEKS_DI_TEAL_REDUP}; }}
.ceria-titik .ceria-isi i {{ background: {T.AKSEN_MURID_AMBER}; border-color: {T.AKSEN_MURID_AMBER}; box-shadow: 0 0 0 3px {T.LATAR_BENING_PUTIH}; }}
.ceria-titik.ceria-krem li {{ color: {T.TEKS_VARIAN}; }}
.ceria-titik.ceria-krem i {{ border-color: {T.ANAK_BORDER_PIL}; }}
.ceria-titik.ceria-krem .ceria-isi i {{ border-color: {T.AKSEN_MURID_AMBER}; box-shadow: none; }}
.ceria-sr {{ position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }}

/* Progres kotak soal: sudah, kini, belum. */
.ceria-progres {{ display: flex; gap: 4px; }}
.ceria-progres span {{ flex: 1; height: {_TINGGI_SEGMEN}; border-radius: {T.RADIUS_PIL}; background: {T.ANAK_NETRAL_LATAR}; }}
.ceria-progres .ceria-sudah {{ background: {T.AKSEN_TEAL_TUA}; }}
.ceria-progres .ceria-kini {{ background: {T.AKSEN_MURID_AMBER}; }}

/* Banner umpan balik: betul hijau, belum tepat hangat (bukan merah). */
.ceria-banner {{ display: flex; align-items: center; gap: {T.SP_3}; padding: {T.SP_3} {T.SP_4}; border-radius: {T.RADIUS_KARTU_BESAR}; border: {T.TEBAL_GARIS} solid; }}
.ceria-banner > div {{ min-width: 0; }}
.ceria-banner .ceria-judul, .ceria-banner p {{ margin: 0; }}
.ceria-banner .ceria-judul {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; color: inherit; }}
.ceria-banner.ceria-betul {{ background: {T.LATAR_TERSIMPAN}; border-color: {T.BORDER_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.ceria-banner.ceria-hampir {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; color: {T.ANAK_PERHATIAN_TEKS}; }}

@media (prefers-reduced-motion: no-preference) {{
  .ceria-maskot, .ceria-gelembung {{ animation: ceria-naik .6s ease-out both; }}
  .ceria-konfeti i {{ animation: ceria-muncul .7s ease-out both; }}
  .ceria-konfeti i:nth-child(2n) {{ animation-delay: .12s; }}
  .ceria-konfeti i:nth-child(3n) {{ animation-delay: .24s; }}
  .ceria-tombol {{ transition: transform .12s ease; }}
  .ceria-tombol:hover {{ transform: translateY(-2px); }}
  @keyframes ceria-naik {{ 0% {{ transform: translateY(10px) scale(.94); }} 60% {{ transform: translateY(-5px) scale(1.02); }} 100% {{ transform: none; }} }}
  @keyframes ceria-muncul {{ 0% {{ opacity: 0; translate: 0 -14px; }} 100% {{ opacity: 1; translate: 0 0; }} }}
}}
"""
