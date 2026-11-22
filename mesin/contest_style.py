"""CSS halaman anak Latihan Lomba; hanya dimuat halaman lomba.

Semua warna, jarak, radius, dan ukuran sentuh dari ``design_tokens`` (tanpa hex). Tombol jawaban
besar untuk jari anak kelas 2 (tinggi >= 3,5rem, huruf >= 1,25rem), bilah atas menempel agar timer
selalu terlihat, dan strip nomor berubah dari satu baris (layar lebar) ke dua baris (HP).
"""
from __future__ import annotations

import design_tokens as T

_TINGGI_JAWABAN = "3.5rem"
_HURUF_JAWABAN = "1.25rem"
_HURUF_SOAL = "1.5rem"
_HURUF_TIMER = "1.5rem"
_LEBAR_NOMOR = "3rem"
_TEBAL_TANDA = "3px"
_TEBAL_CINCIN = "5px"
_LEBAR_MASKOT = "6rem"
_LEBAR_LABEL_HURUF = "2.25rem"

GAYA_LOMBA = f"""
*, *::before, *::after {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; background: {T.LATAR_MURID}; }}
body.lomba {{
  margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_JUDUL};
  font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: {T.LINE_HEIGHT};
}}
.lomba h1, .lomba h2 {{ margin: 0; font-family: {T.FONT_HEADLINE}; line-height: 1.2; }}
.lomba p {{ margin: 0; }}
.lomba :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.sr-saja {{
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}}
/* Lebar kolom dan gutter dari shell murid (.murid-wadah-st); di sini hanya tinggi layar. */
.bingkai {{ min-height: 100vh; min-height: 100dvh; }}

/* ===== topbar murid menempel di soal supaya timer (slot kanan) selalu terlihat ===== */
body.lomba .murid-topbar-st {{
  position: sticky; top: 0; z-index: 10; margin-bottom: {T.SP_3}; padding-top: {T.SP_2};
  background: {T.LATAR_MURID};
}}
.lomba .bilah-nomor {{ margin: 0 0 {T.SP_3}; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.timer {{
  min-width: 5.5rem; padding: {T.SP_1} {T.SP_3}; text-align: center; font-family: {T.FONT_HEADLINE};
  font-size: {_HURUF_TIMER}; font-weight: 800; font-variant-numeric: tabular-nums;
  background: {T.ANAK_AKSEN_LATAR}; color: {T.TEKS_JUDUL};
  border: 2px solid {T.ANAK_AKSEN}; border-radius: {T.RADIUS_PIL};
}}
.timer.merah {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; border-color: {T.BORDER_GALAT}; }}

/* ===== isi ===== */
.isi {{ display: flex; flex-direction: column; gap: {T.SP_5}; padding: {T.SP_4}; }}
.isi > form {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.kartu {{
  display: flex; flex-direction: column; gap: {T.SP_4}; padding: {T.SP_5};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR};
}}
.topik {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.TEKS_VARIAN}; }}
.teks-soal {{ font-size: {T.UKURAN_SOAL}; font-weight: {T.BOBOT_SOAL}; line-height: {T.LINE_HEIGHT_SOAL}; white-space: pre-line; }}
.gambar {{ display: flex; justify-content: center; }}
.gambar svg {{ width: 100%; max-width: {T.LEBAR_VISUAL_SOAL}; height: auto; }}

/* ===== strip nomor: kosong polos, terisi teal penuh, aktif bercincin gelap ===== */
.strip {{ display: grid; grid-template-columns: repeat(10, 1fr); gap: {T.SP_2}; margin: 0; padding: 0; list-style: none; }}
.nomor {{
  display: inline-flex; align-items: center; justify-content: center; width: 100%; min-width: {T.TARGET_SENTUH};
  min-height: {_LEBAR_NOMOR}; padding: 0; font-family: inherit; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800;
  text-decoration: none; cursor: pointer; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL};
  border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_SEDANG};
}}
span.nomor {{ cursor: default; }}
.nomor.sudah {{ background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}; border-color: {T.ANAK_AKSEN}; }}
.nomor.aktif {{ box-shadow: 0 0 0 2px {T.LATAR_MURID}, 0 0 0 {_TEBAL_CINCIN} {T.TEKS_JUDUL}; }}

/* ===== pilihan jawaban ===== */
.pilihan {{ display: grid; grid-template-columns: 1fr; gap: {T.SP_3}; }}
.pilih {{
  display: flex; align-items: center; gap: {T.SP_3}; width: 100%; min-height: {_TINGGI_JAWABAN};
  padding: {T.SP_2} {T.SP_4}; text-align: left; font-family: inherit; font-size: {_HURUF_JAWABAN}; font-weight: 700;
  color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU}; cursor: pointer;
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU};
}}
.pilih:hover {{ border-color: {T.ANAK_AKSEN}; }}
.pilih .huruf {{
  flex: none; display: inline-flex; align-items: center; justify-content: center; width: {_LEBAR_LABEL_HURUF};
  height: {_LEBAR_LABEL_HURUF}; font-family: {T.FONT_HEADLINE}; font-weight: 800;
  background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_BULAT};
}}
.pilih .isi-pilihan {{ flex: 1; min-width: 0; }}
.pilih .isi-pilihan svg {{ display: block; width: 100%; max-width: 9rem; height: auto; max-height: 7rem; }}
.pilih.dipilih {{ background: {T.ANAK_AKSEN_LATAR}; border: {_TEBAL_TANDA} solid {T.ANAK_AKSEN}; }}
.pilih.dipilih .huruf {{ background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}; }}
.pilih .tersimpan {{ flex: none; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.ANAK_BAIK_TEKS}; }}
.pilihan.bergambar .pilih {{ position: relative; }}
.pilihan.bergambar .pilih .tersimpan {{ position: absolute; top: {T.SP_1}; right: {T.SP_2}; }}

/* ===== isian angka ===== */
.isian {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.isian label {{ font-size: {_HURUF_JAWABAN}; font-weight: 700; }}
.isian input {{
  width: 100%; min-height: {_TINGGI_JAWABAN}; padding: 0 {T.SP_4}; font-family: inherit;
  font-size: {_HURUF_SOAL}; font-weight: 700; color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU};
  border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_KARTU};
}}
.bantuan {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
.galat {{
  padding: {T.SP_3}; font-weight: 700; color: {T.TEKS_GALAT};
  background: {T.LATAR_GALAT}; border: {T.TEBAL_GARIS} solid {T.BORDER_GALAT}; border-radius: {T.RADIUS_SEDANG};
}}

/* ===== tombol aksi ===== */
.aksi {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; }}
.aksi .tombol, .aksi > form {{ flex: 1 1 8rem; }}
.aksi > form {{ display: flex; }}
.aksi > form .tombol, .kartu > form .tombol {{ width: 100%; }}
.tombol {{
  display: inline-flex; align-items: center; justify-content: center;
  min-height: {T.TINGGI_CTA}; padding: 0 {T.SP_5}; font-family: inherit; font-size: {_HURUF_JAWABAN}; font-weight: 700;
  text-decoration: none; text-align: center; cursor: pointer;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; border: 0; border-radius: {T.RADIUS_KARTU};
}}
.tombol:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.tombol.sekunder {{ background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border: 2px solid {T.BORDER_KONTROL}; }}
.tombol.sekunder:hover {{ border-color: {T.ANAK_AKSEN}; }}
.tombol.besar {{ width: 100%; min-height: 4.5rem; font-size: {_HURUF_SOAL}; }}

.tautan-selesai {{
  align-self: center; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3}; font-family: inherit; font-size: {T.UKURAN_TEKS_LABEL};
  font-weight: 700; color: {T.ANAK_TEKS_REDUP}; text-decoration: underline; background: none; border: 0; cursor: pointer;
}}
.tautan-selesai:hover {{ color: {T.TEKS_JUDUL}; }}

/* Sesi panjang (Simulasi): grid nomor dilipat di bawah kartu soal dan tombol geser. */
.daftar-nomor {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU}; }}
.daftar-nomor > summary {{
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_4}; font-weight: 700; cursor: pointer; list-style: none;
}}
.daftar-nomor > summary::after {{ content: "\\25BE"; flex: none; }}
.daftar-nomor[open] > summary::after {{ content: "\\25B4"; }}
.daftar-nomor > nav {{ padding: 0 {T.SP_3} {T.SP_3}; }}



/* ===== halaman awal dan hasil: tautan Beranda ada di slot kanan topbar murid ===== */
.maskot-kartu {{ display: block; width: {_LEBAR_MASKOT}; height: auto; }}

/* ===== halaman awal, konfirmasi, hasil ===== */
.judul {{ font-size: {T.UKURAN_JUDUL_STITCH}; font-weight: 800; }}
.angka-besar {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_ANGKA_FUNNEL}; font-weight: 800; }}
.catatan {{
  padding: {T.SP_3} {T.SP_4}; color: {T.ANAK_PERHATIAN_TEKS};
  background: {T.ANAK_PERHATIAN_LATAR}; border: {T.TEBAL_GARIS} solid {T.ANAK_PERHATIAN_BORDER}; border-radius: {T.RADIUS_SEDANG};
}}
.daftar-aturan {{ margin: 0; padding-left: {T.SP_5}; display: flex; flex-direction: column; gap: {T.SP_2}; }}
form {{ margin: 0; }}

@media (max-width: {T.ANAK_BATAS_HP}) {{
  .strip {{ grid-template-columns: repeat(5, 1fr); }}
  .isi {{ padding: {T.SP_3}; }}
  .kartu {{ padding: {T.SP_4}; }}
}}
@media (min-width: {T.ANAK_BATAS_HP}) {{
  .pilihan {{ grid-template-columns: 1fr 1fr; }}
}}
.pilihan.bergambar {{ grid-template-columns: 1fr 1fr; }}
"""


# ===== hasil rinci (anak), riwayat dan detail (guru): dipakai halaman anak dan halaman guru =====
_LEBAR_NOMOR_HASIL = "2.25rem"
_LEBAR_GAMBAR_PILIHAN = "9rem"
_TINGGI_GAMBAR_PILIHAN = "7rem"
_TINGGI_BAR = ".75rem"
_LEBAR_GRAFIK = "34rem"
_LEBAR_LABEL_TOPIK = "11rem"
_TINGGI_BAR_TARGET = "1rem"
_LEBAR_PETA = "3.25rem"

GAYA_HASIL = f"""
.hasil-lomba {{ display: flex; flex-direction: column; gap: {T.SP_5}; color: {T.TEKS_JUDUL}; }}
.hasil-lomba h1, .hasil-lomba h2, .hasil-lomba h3, .hasil-lomba h4, .hasil-lomba p, .hasil-lomba ol, .hasil-lomba ul {{ margin: 0; }}
.hl-sr {{
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}}
.hasil-lomba h2 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.hl-kartu {{
  display: flex; flex-direction: column; gap: {T.SP_4}; padding: {T.SP_5};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR};
}}
.hl-sub {{ color: {T.ANAK_TEKS_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; }}
.hl-semangat {{ font-weight: 600; }}
.hl-catatan {{
  padding: {T.SP_3} {T.SP_4}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_PERHATIAN_TEKS};
  background: {T.ANAK_PERHATIAN_LATAR}; border: {T.TEBAL_GARIS} solid {T.ANAK_PERHATIAN_BORDER}; border-radius: {T.RADIUS_SEDANG};
}}
.hl-kosong {{ padding: {T.SP_4}; color: {T.ANAK_TEKS_REDUP}; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_SEDANG}; }}

/* ringkasan angka */
.hl-ringkas {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: {T.SP_3}; }}
.hl-stat {{ display: flex; flex-direction: column; gap: {T.SP_1}; padding: {T.SP_3} {T.SP_4}; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_SEDANG}; }}
.hl-stat-nilai {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.hl-stat-label {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}

/* bar per topik */
.hl-topik-daftar {{ list-style: none; padding: 0; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.hl-topik-baris {{ display: grid; grid-template-columns: {_LEBAR_LABEL_TOPIK} 1fr auto; align-items: center; gap: {T.SP_3}; }}
.hl-topik-nama {{ font-weight: 700; }}
.hl-topik-angka {{ text-align: right; white-space: nowrap; font-weight: 700; font-variant-numeric: tabular-nums; }}
.hl-bar {{ display: block; width: 100%; height: {_TINGGI_BAR}; border-radius: {T.RADIUS_PIL}; overflow: hidden; }}
.hl-grafik {{ display: block; width: 100%; max-width: {_LEBAR_GRAFIK}; height: auto; }}

/* kartu soal */
.hl-daftar-soal {{ display: flex; flex-direction: column; gap: {T.SP_4}; margin-top: {T.SP_3}; }}
.hl-soal {{
  display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_5};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR};
}}
.hl-judul {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_2}; font-size: 1rem; }}
.hl-nomor {{
  display: inline-flex; align-items: center; justify-content: center; width: {_LEBAR_NOMOR_HASIL}; height: {_LEBAR_NOMOR_HASIL};
  font-family: {T.FONT_HEADLINE}; font-weight: 800; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_BULAT};
}}
.hl-topik {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.TEKS_VARIAN}; }}
.hl-status {{ padding: 0 {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; border-radius: {T.RADIUS_PIL}; border: 2px solid transparent; }}
.hl-status.hl-benar {{ color: {T.ANAK_BAIK_TEKS}; background: {T.ANAK_BAIK_LATAR}; border-color: {T.ANAK_BAIK_TEKS}; }}
.hl-status.hl-salah {{ color: {T.TEKS_GALAT}; background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; }}
.hl-status.hl-kosong-jawab {{ color: {T.ANAK_NETRAL_TEKS}; background: {T.ANAK_NETRAL_LATAR}; border: 2px dashed {T.BORDER_KONTROL}; }}
.hl-teks {{ font-size: 1.25rem; font-weight: 700; line-height: 1.4; white-space: pre-line; }}
.hl-gambar {{ display: flex; justify-content: center; }}
.hl-gambar svg {{ width: 100%; max-width: {T.LEBAR_VISUAL_SOAL}; height: auto; }}
.hl-pilihan {{ list-style: none; padding: 0; display: grid; grid-template-columns: 1fr; gap: {T.SP_2}; }}
.hl-pilih {{
  display: flex; align-items: center; gap: {T.SP_3}; padding: {T.SP_2} {T.SP_3};
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU};
}}
.hl-huruf {{
  flex: none; display: inline-flex; align-items: center; justify-content: center; width: {_LEBAR_NOMOR_HASIL}; height: {_LEBAR_NOMOR_HASIL};
  font-family: {T.FONT_HEADLINE}; font-weight: 800; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_BULAT};
}}
.hl-isi {{ flex: 1; min-width: 0; font-weight: 600; }}
.hl-isi svg {{ display: block; width: 100%; max-width: {_LEBAR_GAMBAR_PILIHAN}; height: auto; max-height: {_TINGGI_GAMBAR_PILIHAN}; }}
.hl-tanda {{ flex: none; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; }}
.hl-pilih.hl-dipilih {{ background: {T.ANAK_AKSEN_LATAR}; border: 3px solid {T.ANAK_AKSEN}; }}
.hl-pilih.hl-kunci {{ background: {T.ANAK_BAIK_LATAR}; border: 2px solid {T.ANAK_BAIK_TEKS}; }}
.hl-pilih.hl-dipilih.hl-kunci {{ border: 3px solid {T.ANAK_BAIK_TEKS}; }}
.hl-jawaban {{ display: flex; flex-direction: column; gap: {T.SP_1}; }}
.hl-jawaban strong {{ font-weight: 800; }}
.hl-bahas-judul {{ font-size: 1rem; font-weight: 800; }}
.hl-bahas {{ padding-left: {T.SP_5}; display: flex; flex-direction: column; gap: {T.SP_1}; }}
.hl-kesalahan {{
  padding: {T.SP_2} {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_PERHATIAN_TEKS};
  background: {T.ANAK_PERHATIAN_LATAR}; border: {T.TEBAL_GARIS} solid {T.ANAK_PERHATIAN_BORDER}; border-radius: {T.RADIUS_SEDANG};
}}

/* tabel riwayat (guru) */
.hl-gulir {{ overflow-x: auto; }}
.hl-tabel {{ width: 100%; border-collapse: collapse; font-size: {T.UKURAN_TEKS_LABEL}; }}
.hl-tabel th {{ white-space: nowrap; }}
.hl-tabel th, .hl-tabel td {{ text-align: left; padding: {T.SP_2}; border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; vertical-align: top; }}
.hl-tabel td.hl-angka {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
.hl-daftar-sering {{ padding-left: {T.SP_5}; display: flex; flex-direction: column; gap: {T.SP_1}; }}
.hl-chip {{
  display: inline-block; max-width: 100%; padding: 0 {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600;
  overflow-wrap: anywhere; color: {T.ANAK_NETRAL_TEKS}; background: {T.ANAK_NETRAL_LATAR}; border-radius: {T.RADIUS_PIL};
}}
.hl-chip-cepat {{ color: {T.ANAK_PERHATIAN_TEKS}; background: {T.ANAK_PERHATIAN_LATAR}; border: {T.TEBAL_GARIS} solid {T.ANAK_PERHATIAN_BORDER}; }}
.hl-riwayat-hp {{ display: none; list-style: none; padding: 0; flex-direction: column; gap: {T.SP_3}; }}
.hl-sesi-hp {{
  display: flex; flex-direction: column; gap: {T.SP_2}; min-width: 0; padding: {T.SP_3} {T.SP_4};
  background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_SEDANG};
}}
.hl-sesi-atas {{ display: flex; align-items: baseline; justify-content: space-between; gap: {T.SP_3}; min-width: 0; }}
.hl-sesi-tanggal {{ min-width: 0; overflow-wrap: anywhere; font-weight: 600; }}
.hl-sesi-nilai {{ flex: none; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.hl-chip-baris {{ list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: {T.SP_2}; min-width: 0; }}
.hl-sesi-lihat {{ display: inline-flex; align-items: center; align-self: flex-start; min-height: {T.TARGET_SENTUH}; font-weight: 700; }}

@media (max-width: {T.ANAK_BATAS_HP}) {{
  .hl-kartu, .hl-soal {{ padding: {T.SP_4}; }}
  .hl-topik-baris {{ grid-template-columns: 1fr auto; }}
  .hl-topik-baris .hl-bar {{ grid-column: 1 / -1; order: 3; }}
  .hl-riwayat-lebar {{ display: none; }}
  .hl-riwayat-hp {{ display: flex; }}
}}
@media (min-width: {T.ANAK_BATAS_HP}) {{
  .hl-pilihan {{ grid-template-columns: 1fr 1fr; }}
}}
"""

GAYA_AWAL = f"""
.kartu-awal {{ align-items: flex-start; }}
.pilih-mode {{ display: flex; flex-direction: column; gap: {T.SP_3}; align-self: stretch; }}
/* Label mode panjang ("Simulasi Lomba (35 soal · 60 menit)"): ukuran tombol biasa supaya satu baris di HP. */
.pilih-mode .tombol.besar {{ min-height: {T.TINGGI_CTA}; padding-inline: {T.SP_3}; font-size: {_HURUF_JAWABAN}; }}
.label-mode {{
  padding: {T.SP_1} {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.TEKS_JUDUL};
  background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_PIL};
}}
.kartu-awal .tombol, .kartu-awal form {{ align-self: stretch; }}
.catatan-kecil {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
.hitung-mundur {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.target {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
.target-teks {{ font-weight: 700; }}
.bar-target {{ height: {_TINGGI_BAR_TARGET}; background: {T.ANAK_NETRAL_LATAR}; border-radius: {T.RADIUS_PIL}; overflow: hidden; }}
.bar-target-isi {{ height: 100%; background: {T.ANAK_AKSEN}; border-radius: {T.RADIUS_PIL}; }}
.target-capai {{ font-weight: 800; color: {T.ANAK_BAIK_TEKS}; }}
.nilai-terbaik {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
.nilai-terbaik-baris {{ display: flex; align-items: baseline; justify-content: space-between; gap: {T.SP_3}; margin: 0; }}
.nilai-terbaik strong {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_JUDUL_STITCH}; font-weight: 800; }}
.latihan-terakhir {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.latihan-terakhir h2 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.latihan-terakhir ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.tautan-latihan {{
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_4}; color: {T.TEKS_JUDUL}; text-decoration: none; font-weight: 600;
  background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU};
}}
.tautan-latihan strong {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.tautan-latihan:hover {{ border-color: {T.ANAK_AKSEN}; }}
"""

# ===== hasil anak: ringkasan, peta nomor, kelompok soal (hanya halaman anak, bukan guru) =====
GAYA_HASIL_ANAK = f"""
.hl-ringkas-anak {{ display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_2}; }}
.hl-ringkas-anak .angka-besar {{ line-height: 1; }}
.hl-banding {{ font-weight: 700; color: {T.ANAK_BAIK_TEKS}; }}
.hl-mode {{ margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.ANAK_TEKS_REDUP}; }}
.peta {{ display: grid; grid-template-columns: repeat(10, 1fr); gap: {T.SP_2}; margin: 0; padding: 0; list-style: none; }}
.peta-nomor {{
  display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: {T.TARGET_SENTUH};
  min-height: {_LEBAR_PETA}; font-weight: 800; text-decoration: none; line-height: 1.2;
  color: {T.TEKS_JUDUL}; border: 2px solid transparent; border-radius: {T.RADIUS_SEDANG};
}}
.peta-nomor.hl-benar {{ color: {T.ANAK_BAIK_TEKS}; background: {T.ANAK_BAIK_LATAR}; border-color: {T.ANAK_BAIK_TEKS}; }}
.peta-nomor.hl-salah {{ color: {T.TEKS_GALAT}; background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; }}
.peta-nomor.hl-kosong-jawab {{ color: {T.ANAK_NETRAL_TEKS}; background: {T.ANAK_NETRAL_LATAR}; border: 2px dashed {T.BORDER_KONTROL}; }}
.hl-kelompok {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.hl-lipat {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.hl-lipat > summary {{
  display: flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_3} {T.SP_4}; font-weight: 800; cursor: pointer;
}}
.hl-lipat > .hl-daftar-soal {{ margin: 0; padding: 0 {T.SP_3} {T.SP_3}; }}
.hl-lipat .hl-soal {{ border: 0; padding: {T.SP_3}; }}
/* "Tidak dijawab" = badge netral polos (tanpa garis putus), sama untuk lencana kartu dan peta nomor. */
.hl-status.hl-kosong-jawab {{ border-color: transparent; }}
.peta-nomor.hl-kosong-jawab {{ border: 2px solid transparent; }}
.hasil-lomba .aksi {{ margin-top: {T.SP_2}; }}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  .peta {{ grid-template-columns: repeat(5, 1fr); }}
}}
"""

# ===== kartu pengaturan Mode Lomba di halaman Guru (/anak/<id>/lomba); tanpa JS =====
GAYA_PENGATURAN = f"""
.hl-pesan-simpan {{
  padding: {T.SP_3} {T.SP_4}; font-weight: 700; color: {T.ANAK_BAIK_TEKS}; background: {T.ANAK_BAIK_LATAR};
  border: {T.TEBAL_GARIS} solid {T.ANAK_BAIK_TEKS}; border-radius: {T.RADIUS_SEDANG};
}}
.hl-galat {{
  padding: {T.SP_3} {T.SP_4}; font-weight: 700; color: {T.TEKS_GALAT}; background: {T.LATAR_GALAT};
  border: {T.TEBAL_GARIS} solid {T.BORDER_GALAT}; border-radius: {T.RADIUS_SEDANG};
}}
.hl-form {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.hl-form fieldset {{ display: flex; flex-direction: column; gap: {T.SP_2}; margin: 0; padding: 0; border: 0; }}
.hl-form legend {{ padding: 0; font-weight: 700; }}
.hl-form label {{ display: flex; align-items: center; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; }}
.hl-form .hl-isian {{ flex-direction: column; align-items: flex-start; gap: {T.SP_2}; font-weight: 700; }}
.hl-form select, .hl-form input[type="number"] {{
  min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3}; font: inherit; color: {T.TEKS_JUDUL};
  background: {T.LATAR_KARTU}; border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_SEDANG};
}}
.hl-form .btn-st {{ align-self: flex-start; }}
.hl-form select {{ min-height: {T.TINGGI_KONTROL}; }}
.hl-lencana-st {{
  display: inline-flex; align-items: center; border-radius: {T.RADIUS_PIL}; padding: {T.SP_1} {T.SP_3};
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; line-height: 1.4;
}}
.hl-lencana-aktif-st {{ background: {T.ANAK_BAIK_LATAR}; color: {T.ANAK_BAIK_TEKS}; }}
.hl-lencana-netral-st {{ background: {T.ANAK_NETRAL_LATAR}; color: {T.ANAK_NETRAL_TEKS}; }}
"""

# ===== kartu Lomba di beranda murid (dimuat HANYA saat sakelar Lomba hidup; beranda lain tidak berubah) =====
GAYA_BERANDA = f"""
.lomba-beranda {{
  display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_3}; margin-top: {T.SP_6}; padding: {T.SP_5};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR};
}}
.lomba-beranda.besar {{ margin-top: 0; }}
.lomba-beranda h2 {{ margin: 0; font: 800 {T.UKURAN_BAGIAN_DEWASA}/1.4 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.lb-kepala {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.lb-kepala > div {{ display: flex; flex-direction: column; min-width: 0; }}
.lomba-beranda.besar h2 {{ font-size: {T.UKURAN_JUDUL_STITCH}; }}
.lomba-beranda p {{ margin: 0; }}
.lomba-beranda .maskot-kartu {{ display: block; width: {_LEBAR_MASKOT}; height: auto; }}
.lb-status {{ font-weight: 800; color: {T.ANAK_PERHATIAN_TEKS}; }}
.lb-meta {{ color: {T.ANAK_TEKS_REDUP}; font-size: {T.UKURAN_TEKS_LABEL}; }}
/* Beranda punya satu tombol utama koral: kartu kecil = tombol sekunder (garis); kartu besar menggantikan hero
   saat anak belum punya sesi dari Guru, jadi tombolnya menjadi yang utama. */
.lb-tombol {{
  display: inline-flex; align-items: center; justify-content: center; align-self: stretch; min-height: {T.TINGGI_CTA};
  padding: 0 {T.SP_5}; font-weight: 700; text-decoration: none; text-align: center;
  background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; border: 2px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU};
}}
.lb-tombol:hover {{ background: {T.LATAR_ELEVASI}; }}
.lomba-beranda.besar .lb-tombol {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; border-color: transparent; }}
.lomba-beranda.besar .lb-tombol:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.lomba-beranda .hitung-mundur {{ font-size: 1rem; }}
.lomba-beranda .target {{ align-self: stretch; }}
.lomba-beranda .target-teks {{ font-size: {T.UKURAN_TEKS_LABEL}; }}
.lomba-beranda .bar-target {{ height: {_TINGGI_BAR_TARGET}; background: {T.ANAK_NETRAL_LATAR}; border-radius: {T.RADIUS_PIL}; overflow: hidden; }}
.lomba-beranda .bar-target-isi {{ height: 100%; background: {T.ANAK_AKSEN}; border-radius: {T.RADIUS_PIL}; }}
.lomba-beranda .target-capai {{ font-weight: 800; color: {T.ANAK_BAIK_TEKS}; }}
.lb-catatan {{ margin-top: {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
"""
