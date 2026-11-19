"""CSS permukaan anak sesi Cek Kemampuan gratis; hanya dimuat halaman cek anak.

Semua warna, ukuran huruf, jarak, dan radius dari ``design_tokens`` (tanpa hex).
Teks tak kurang dari ``UKURAN_TEKS_LABEL`` (14px), target sentuh minimal
``TARGET_SENTUH`` (44px). Tampilan meniru prototipe yang disetujui pemilik
(layar s4-s8); nama kelas tidak dipakai halaman lain.

Aturan `kerja-teks-st`/`kerja-tanya-st` dan GAYA_PENYAJIAN/GAYA_PECAHAN ada di
sini karena renderer soal bersama memakai kelas itu; GAYA_STITCH utuh tidak
dimuat supaya halaman tetap ringan dan tidak bertabrakan.
"""
from __future__ import annotations

import design_tokens as T
from pecahan_style import GAYA_PECAHAN
from presentation_style import GAYA_PENYAJIAN

# Tint ilustratif dari token yang ada (koral memakai latar galat yang kemerahan
# muda; ini hanya warna latar ubin, bukan penanda salah).
_TINT_TEAL = T.ANAK_AKSEN_LATAR
_TINT_KORAL = T.LATAR_GALAT
_TINT_AMBER = T.LATAR_REVIEW
_TINT_NAVY = T.ANAK_INFO_LATAR
_TINT_MINT = T.ANAK_HEADER_AVATAR_LATAR

GAYA_CEK_ANAK = f"""
{GAYA_PENYAJIAN}
{GAYA_PECAHAN}
*, *::before, *::after {{ box-sizing: border-box; }}
[hidden] {{ display: none !important; }}
html {{ -webkit-text-size-adjust: 100%; background: {T.LATAR_MURID}; }}
body.cek-anak {{
  margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_JUDUL};
  font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: {T.LINE_HEIGHT};
}}
.cek-anak h1, .cek-anak h2, .cek-anak h3 {{
  margin: 0; line-height: 1.2; letter-spacing: -.01em; font-family: {T.FONT_HEADLINE};
}}
.cek-anak p {{ margin: 0; }}
.cek-anak :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.bingkai {{
  max-width: {T.BATAS_HP}; margin: 0 auto; min-height: 100vh; min-height: 100dvh;
  display: flex; flex-direction: column; background: {T.LATAR_MURID};
}}
@media (min-width: {T.BATAS_HP}) {{
  .bingkai {{ border-inline: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; }}
}}
.sr-saja {{
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}}
.bantuan {{ font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.eyebrow {{
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: {T.AKSEN_TEAL_TUA};
}}

/* ===== tombol ===== */
.cta, .sekunder {{
  display: flex; align-items: center; justify-content: center; gap: {T.SP_2}; width: 100%;
  text-decoration: none; text-align: center; cursor: pointer; font-family: inherit; font-weight: 700;
}}
.cta {{
  min-height: {T.TINGGI_CTA}; padding: 0 {T.SP_4}; border: 0; border-radius: {T.RADIUS_KARTU};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font-size: {T.UKURAN_BADAN_LAYAR};
  box-shadow: 0 4px 0 {T.AKSEN_TEAL_HOVER};
  transition: transform {T.DURASI_CEPAT}, box-shadow {T.DURASI_CEPAT};
}}
.cta:hover {{ background: {T.AKSEN_TEAL_HOVER}; }}
.cta:active {{ transform: translateY(3px); box-shadow: 0 1px 0 {T.AKSEN_TEAL_HOVER}; }}
.cta.koral {{ background: {T.AKSEN_KORAL_TUA}; box-shadow: 0 4px 0 {T.AKSEN_KORAL_HOVER}; }}
.cta.amber {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; box-shadow: 0 4px 0 {T.AKSEN_AMBER_TUA}; }}
.cta.putih {{ background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; box-shadow: 0 4px 0 {T.ANAK_BORDER_PIL}; }}
.sekunder {{
  min-height: {T.TARGET_SENTUH}; border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_KARTU};
  background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; font-size: {T.UKURAN_BADAN_LAYAR};
}}
.sekunder:hover {{ border-color: {T.AKSEN_TEAL_TUA}; color: {T.AKSEN_TEAL_TUA}; }}

/* ===== kepala teal + jejak ===== */
.kepala-anak {{
  position: relative; z-index: 2; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH};
  padding: {T.SP_5} {T.SP_4} {T.SP_4};
}}
.doodle {{
  position: absolute; inset: 0; overflow: hidden; pointer-events: none; color: {T.TEKS_PUTIH};
  opacity: .13; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_ANGKA_FUNNEL_HP};
}}
.doodle span {{ position: absolute; line-height: 1; }}
.kepala-anak .baris {{ position: relative; display: flex; align-items: center; gap: {T.SP_2}; }}
.kepala-anak .judul-kecil {{ font-weight: 700; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.kepala-anak h1 {{ position: relative; font-size: {T.UKURAN_ANGKA_DEWASA}; font-weight: 800; margin-top: {T.SP_2}; }}
.rehat {{ position: relative; margin-left: auto; }}
.rehat summary {{
  list-style: none; display: inline-flex; align-items: center; gap: {T.SP_2}; cursor: pointer;
  min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3}; border-radius: {T.RADIUS_PIL};
  background: {T.AKSEN_TEAL_HOVER}; color: {T.TEKS_PUTIH}; font-weight: 700; font-size: {T.UKURAN_TEKS_LABEL};
}}
.rehat summary::-webkit-details-marker {{ display: none; }}
.rehat-panel {{
  position: absolute; right: 0; top: calc(100% + {T.SP_2}); z-index: 5;
  width: min(19rem, calc(100vw - 2rem)); display: flex; flex-direction: column; gap: {T.SP_3};
  padding: {T.SP_4}; border: 2px solid {T.TEKS_JUDUL}; border-radius: {T.RADIUS_KARTU_BESAR};
  background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; box-shadow: {T.BAYANGAN_MENU};
}}
.rehat-panel h2 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.jejak {{ position: relative; margin-top: {T.SP_3}; }}
.jejak ol {{ list-style: none; margin: 0; padding: 0; display: flex; justify-content: space-between; align-items: center; position: relative; }}
.jejak ol::before {{
  content: ""; position: absolute; left: {T.SP_2}; right: {T.SP_2}; top: 50%; height: 3px;
  background: {T.AKSEN_MURID_UTAMA}; opacity: .5; transform: translateY(-50%);
}}
.jejak li {{
  position: relative; width: 18px; height: 18px; border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_TEAL_TUA};
  border: 2px solid {T.ANAK_AKSEN_LATAR}; display: flex; align-items: center; justify-content: center;
}}
.jejak li.isi {{ background: {T.AKSEN_MURID_AMBER}; border-color: {T.AKSEN_MURID_AMBER}; }}
.jejak li.isi::after {{ content: "★"; font-size: {T.UKURAN_TEKS_META}; color: {T.TEKS_JUDUL}; line-height: 1; }}
.jejak li.lewat {{ border-style: dashed; border-color: {T.TEKS_PUTIH}; background: transparent; }}
.jejak li.kini {{
  width: 24px; height: 24px; background: {T.TEKS_PUTIH}; border-color: {T.TEKS_PUTIH};
  box-shadow: 0 0 0 4px {T.AKSEN_MURID_AMBER}; animation: denyut 1.6s ease-in-out infinite;
}}
@keyframes denyut {{ 50% {{ box-shadow: 0 0 0 7px {T.AKSEN_MURID_AMBER}; }} }}
.jejak .teks {{ display: flex; justify-content: space-between; margin-top: {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.ANAK_AKSEN_LATAR}; }}
.jejak .teks b {{ color: {T.TEKS_PUTIH}; }}

/* ===== isi soal ===== */
.isi-anak {{ padding: {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_3}; flex: 1; }}
.isi-anak form {{ display: flex; flex-direction: column; gap: {T.SP_3}; flex: 1; margin: 0; }}
.label-materi {{ display: inline-flex; align-items: center; gap: {T.SP_2}; font-weight: 700; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; }}
.ubin {{
  width: var(--u, 30px); height: var(--u, 30px); border-radius: {T.RADIUS_KARTU}; display: inline-flex;
  align-items: center; justify-content: center; flex: none; transform: rotate(-4deg);
  box-shadow: 0 3px 0 {T.ANAK_BORDER};
}}
.ubin.teal {{ background: {_TINT_TEAL}; color: {T.AKSEN_TEAL_TUA}; }}
.ubin.koral {{ background: {_TINT_KORAL}; color: {T.AKSEN_KORAL_TUA}; }}
.ubin.amber {{ background: {_TINT_AMBER}; color: {T.AKSEN_AMBER_TUA}; }}
.ubin.navy {{ background: {_TINT_NAVY}; color: {T.TEKS_JUDUL}; }}
.kertas {{
  position: relative; border-radius: {T.RADIUS_KARTU_BESAR}; border: 2px solid {T.TEKS_JUDUL};
  padding: {T.SP_4}; background-color: {T.LATAR_KARTU}; box-shadow: 0 5px 0 {T.TEKS_JUDUL};
  background-image: linear-gradient({_TINT_MINT} 1px, transparent 1px), linear-gradient(90deg, {_TINT_MINT} 1px, transparent 1px);
  background-size: 18px 18px;
}}
.kerja-teks-st, .kerja-tanya-st {{ display: block; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 600; line-height: 1.45; overflow-wrap: anywhere; }}
.kerja-teks-st + .kerja-teks-st, .kerja-teks-st + .kerja-tanya-st {{ margin-top: {T.SP_2}; }}
.kerja-tanya-st {{ font-weight: 700; }}
.kertas [data-fingerprint-penyajian] svg {{ background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KARTU}; }}
.opsi {{ border: 0; margin: 0; padding: 0; min-width: 0; display: grid; grid-template-columns: 1fr 1fr; gap: {T.SP_3}; }}
.opsi-satu {{ position: relative; display: block; }}
/* legend ikut dihitung nth-child, jadi pakai nth-of-type (hanya label) */
.opsi-satu:nth-of-type(odd):last-of-type {{ grid-column: 1 / -1; }}
.opsi-satu input {{ position: absolute; opacity: 0; width: 100%; height: 100%; inset: 0; margin: 0; cursor: pointer; }}
.opsi-satu .kotak {{
  display: flex; align-items: center; gap: {T.SP_2}; min-height: 68px; padding: {T.SP_2} {T.SP_3};
  border: 2px solid {T.ANAK_BORDER}; border-radius: 18px; background: {T.LATAR_KARTU};
  box-shadow: 0 4px 0 {T.ANAK_BORDER}; font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: {T.UKURAN_BAGIAN_STITCH}; overflow-wrap: anywhere;
  transition: transform {T.DURASI_CEPAT}, box-shadow {T.DURASI_CEPAT};
}}
.opsi-satu .huruf {{
  width: 30px; height: 30px; border-radius: {T.RADIUS_SEDANG}; display: inline-flex; align-items: center;
  justify-content: center; flex: none; font-size: {T.UKURAN_TEKS_LABEL}; background: var(--k); color: {T.TEKS_JUDUL};
}}
.opsi-satu:nth-of-type(1) {{ --k: {_TINT_TEAL}; }}
.opsi-satu:nth-of-type(2) {{ --k: {_TINT_KORAL}; }}
.opsi-satu:nth-of-type(3) {{ --k: {_TINT_AMBER}; }}
.opsi-satu:nth-of-type(4) {{ --k: {_TINT_NAVY}; }}
.opsi-satu:nth-of-type(5) {{ --k: {_TINT_MINT}; }}
.opsi-satu:hover .kotak {{ border-color: {T.TEKS_JUDUL}; }}
.opsi-satu input:checked + .kotak {{ border-color: {T.TEKS_JUDUL}; border-width: 3px; background: var(--k); box-shadow: 0 4px 0 {T.TEKS_JUDUL}; }}
.opsi-satu input:checked + .kotak .huruf {{ background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; }}
.opsi-satu input:focus-visible + .kotak {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}
.opsi.panjang .kotak {{ font-family: {T.FONT_BODY}; font-weight: 700; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.aksi-soal {{ display: grid; grid-template-columns: auto 1fr; gap: {T.SP_2}; margin-top: auto; }}
.aksi-soal .sekunder {{ width: auto; padding: 0 {T.SP_4}; }}
.alat-kecil {{ display: flex; align-items: center; justify-content: space-between; gap: {T.SP_2}; }}
.teman {{ display: flex; align-items: center; gap: {T.SP_2}; min-width: 0; }}
.teman img {{ width: 52px; height: 52px; flex: none; }}
.gel {{
  background: {T.LATAR_KARTU}; border: 2px solid {T.TEKS_JUDUL}; border-radius: 14px;
  padding: {T.SP_1} {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; max-width: 12rem;
}}
.btn-coret {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3};
  border-radius: {T.RADIUS_PIL}; border: 2px dashed {T.AKSEN_TEAL_TUA}; background: {T.LATAR_KARTU};
  color: {T.AKSEN_TEAL_TUA}; font-family: inherit; font-weight: 700; font-size: {T.UKURAN_TEKS_LABEL}; cursor: pointer; flex: none;
}}
.papan {{ position: relative; border: 2px dashed {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KARTU_BESAR}; background: {T.ANAK_LATAR_KARTU_HALUS}; }}
.papan canvas {{ display: block; width: 100%; height: 160px; touch-action: none; cursor: crosshair; }}
.papan .hapus {{
  position: absolute; right: {T.SP_2}; top: {T.SP_2}; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3};
  border-radius: {T.RADIUS_PIL}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; background: {T.LATAR_KARTU};
  font-family: inherit; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; cursor: pointer;
}}
.papan .ket {{ position: absolute; left: {T.SP_3}; top: {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; pointer-events: none; }}
.bawaan {{ position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }}
.kabar {{
  align-self: flex-start; display: inline-flex; align-items: center; gap: {T.SP_2}; padding: {T.SP_1} {T.SP_4};
  border-radius: {T.RADIUS_PIL}; background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; font-weight: 700;
  font-size: {T.UKURAN_TEKS_LABEL}; animation: kabar-pudar 4s ease forwards;
}}
.kabar .bintang {{ color: {T.AKSEN_MURID_AMBER}; }}
.kabar.netral {{ background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; animation: none; }}
@keyframes kabar-pudar {{ 0%, 75% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}

/* ===== layar penuh (sapaan, jeda, keluar, hore) ===== */
.tengah {{ position: relative; display: flex; flex-direction: column; align-items: center; text-align: center; gap: {T.SP_3}; }}
.layar-cerah {{
  position: relative; overflow: hidden; flex: 1; display: flex; flex-direction: column; justify-content: center;
  padding: {T.SP_7} {T.SP_4} {T.SP_5}; gap: {T.SP_4};
}}
.layar-cerah form {{ width: 100%; margin: 0; }}
.layar-cerah.teal {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.layar-cerah.teal .bantuan {{ color: {T.ANAK_AKSEN_LATAR}; }}
.layar-cerah h1 {{ font-size: {T.UKURAN_JUDUL_STITCH}; font-weight: 800; }}
.layar-cerah .besar {{ font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 600; }}
.maskot-besar {{ width: 190px; height: 190px; }}
.maskot-sedang {{ width: 140px; height: 140px; }}
.cara {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: {T.SP_2}; width: 100%; }}
.cara div {{
  background: {T.AKSEN_TEAL_HOVER}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_3} {T.SP_2};
  display: flex; flex-direction: column; align-items: center; gap: {T.SP_2};
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; line-height: 1.3;
}}
.cara div:nth-child(1) {{ transform: rotate(-2deg); }}
.cara div:nth-child(2) {{ transform: rotate(2deg); }}
.cara b {{
  width: 34px; height: 34px; border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL};
  display: flex; align-items: center; justify-content: center; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BADAN_LAYAR};
}}
.regang {{ display: flex; gap: {T.SP_2}; justify-content: center; }}
.regang span {{
  width: 64px; height: 52px; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_KARTU}; border: 2px solid {T.TEKS_JUDUL};
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-family: {T.FONT_HEADLINE};
  font-size: {T.UKURAN_TEKS_LABEL}; animation: goyang 2.4s ease-in-out infinite;
}}
.regang span:nth-child(2) {{ animation-delay: .3s; }}
.regang span:nth-child(3) {{ animation-delay: .6s; }}
@keyframes goyang {{ 0%, 100% {{ transform: rotate(-6deg); }} 50% {{ transform: rotate(6deg) translateY(-4px); }} }}
.hitung-napas {{
  position: relative; width: 6rem; height: 3rem; font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: {T.UKURAN_ANGKA_FUNNEL}; color: {T.AKSEN_TEAL_TUA}; line-height: 1;
}}
.hitung-napas span {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; opacity: 0; }}
.hitung-napas .n {{ animation: angka 1s linear; animation-delay: calc(var(--i) * 1s); }}
.hitung-napas .siap {{ animation: angka-akhir .3s linear 5s forwards; font-size: {T.UKURAN_ANGKA_DEWASA}; }}
@keyframes angka {{ 0%, 99% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
@keyframes angka-akhir {{ to {{ opacity: 1; }} }}

/* ===== peta soal ===== */
.sapa {{ display: flex; align-items: flex-end; gap: {T.SP_2}; }}
.sapa img {{ width: 84px; height: 84px; flex: none; }}
.gelembung {{
  position: relative; background: {T.LATAR_KARTU}; border: 2px solid {T.TEKS_JUDUL}; border-radius: 18px;
  padding: {T.SP_3} {T.SP_4}; font-weight: 600; font-size: {T.UKURAN_BADAN_LAYAR};
  box-shadow: 0 4px 0 {T.ANAK_BORDER}; margin-bottom: {T.SP_4};
}}
.gelembung::before {{ content: ""; position: absolute; left: -12px; bottom: 14px; border: 10px solid transparent; border-right-color: {T.TEKS_JUDUL}; border-left: 0; }}
.gelembung::after {{ content: ""; position: absolute; left: -8px; bottom: 16px; border: 8px solid transparent; border-right-color: {T.LATAR_KARTU}; border-left: 0; }}
.peta-soal {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: {T.SP_2}; list-style: none; margin: 0; padding: 0; }}
.peta-soal a {{
  aspect-ratio: 1; min-height: {T.TARGET_SENTUH}; border-radius: {T.RADIUS_KARTU_BESAR}; border: 2px solid {T.TEKS_JUDUL};
  background: {T.AKSEN_MURID_AMBER}; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_BAGIAN_STITCH};
  display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1;
  gap: {T.SP_1}; text-decoration: none; color: {T.TEKS_JUDUL}; box-shadow: 0 3px 0 {T.TEKS_JUDUL};
}}
.peta-soal a small {{ font-size: {T.UKURAN_TEKS_LABEL}; font-family: {T.FONT_BODY}; font-weight: 700; }}
.peta-soal a.kosong {{ background: {T.LATAR_KARTU}; border-style: dashed; box-shadow: none; }}
.peta-soal li:nth-child(odd) a {{ transform: rotate(-3deg); }}
.peta-soal li:nth-child(even) a {{ transform: rotate(2deg); }}
.legenda {{ display: flex; gap: {T.SP_3}; flex-wrap: wrap; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.kumpul {{ margin-top: auto; }}
.kumpul summary {{
  list-style: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
  min-height: {T.TINGGI_CTA}; border-radius: {T.RADIUS_KARTU}; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  font-weight: 700; font-size: {T.UKURAN_BADAN_LAYAR}; box-shadow: 0 4px 0 {T.AKSEN_KORAL_HOVER};
}}
.kumpul summary::-webkit-details-marker {{ display: none; }}
.kumpul[open] summary {{ background: {T.AKSEN_KORAL_HOVER}; }}
.kumpul-panel {{
  display: flex; flex-direction: column; gap: {T.SP_3}; margin-top: {T.SP_3}; padding: {T.SP_4};
  border: 2px solid {T.TEKS_JUDUL}; border-radius: {T.RADIUS_KARTU_BESAR}; background: {T.LATAR_KARTU};
}}
.kumpul-panel h2 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.kumpul-panel form {{ margin: 0; }}

/* ===== Hore ===== */
.konfeti {{ position: absolute; inset: 0; pointer-events: none; overflow: hidden; }}
.konfeti i {{ position: absolute; top: -16px; width: 9px; height: 14px; border-radius: 2px; animation: jatuh 2.4s ease-in forwards; }}
@keyframes jatuh {{ to {{ transform: translateY(105vh) rotate(540deg); }} }}
.stiker {{ width: 190px; height: 190px; margin: 0 auto; }}
.stiker svg {{ width: 190px; height: 190px; overflow: visible; animation: putar-masuk .8s cubic-bezier(.2, 1.4, .4, 1) both; }}
@keyframes putar-masuk {{ from {{ transform: scale(.3) rotate(-30deg); opacity: 0; }} to {{ transform: scale(1) rotate(-6deg); opacity: 1; }} }}
.angka-usaha {{ display: flex; gap: {T.SP_2}; justify-content: center; flex-wrap: wrap; }}
.angka-usaha span {{ background: {T.AKSEN_TEAL_HOVER}; border-radius: {T.RADIUS_PIL}; padding: {T.SP_2} {T.SP_4}; font-weight: 700; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.serah {{
  width: 100%; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border: 2px solid {T.TEKS_JUDUL};
  border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_4}; font-weight: 700; box-shadow: 0 5px 0 {T.TEKS_JUDUL};
}}
.kotak-galat {{ border: 2px solid {T.TEKS_GALAT}; background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_3}; font-weight: 600; }}
.layar-cerah.krem {{ background: {T.LATAR_MURID}; }}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
  .konfeti {{ display: none; }}
  .hitung-napas .n {{ display: none; }}
  .hitung-napas .siap {{ opacity: 1; }}
  .stiker svg {{ transform: rotate(-6deg); }}
}}
"""
