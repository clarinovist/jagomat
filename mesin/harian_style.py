"""CSS Latihan Harian: halaman anak (`GAYA_HARIAN`) dan potongan kecil untuk kartu beranda/halaman orang tua (`GAYA_KARTU`).

Semua warna, jarak, radius, dan ukuran dari `design_tokens` (tanpa hex). Tombol dan pilihan besar untuk jari anak
(tinggi >= `T.TARGET_SENTUH`), status benar/salah selalu disertai teks (bukan warna saja).
`GAYA_KARTU` disisipkan sebagai `<style>` di dalam kartu supaya beranda murid dan halaman orang tua tidak perlu
menambah stylesheet (CSP `style-src 'unsafe-inline'` sudah berlaku).
"""
from __future__ import annotations

import design_tokens as T

_TINGGI_PILIHAN = "3.5rem"
_UKURAN_TITIK = "1.1rem"
_LEBAR_NOMOR = "2rem"

GAYA_KARTU = f"""
.hr-hari {{ display: flex; gap: {T.SP_2}; margin: {T.SP_3} 0; padding: 0; list-style: none; }}
.hr-hari li {{ display: flex; flex-direction: column; align-items: center; gap: {T.SP_1}; font-size: {T.UKURAN_TEKS_META}; color: {T.TEKS_VARIAN}; }}
.hr-titik {{ display: block; width: {_UKURAN_TITIK}; height: {_UKURAN_TITIK}; border-radius: {T.RADIUS_BULAT};
  background: {T.ANAK_ABU_HANGAT}; border: 2px solid {T.ANAK_BORDER_PIL}; }}
.hr-hari .ada .hr-titik {{ background: {T.ANAK_AKSEN}; border-color: {T.ANAK_AKSEN}; }}
.hr-sr {{ position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0; }}
.hr-tombol {{ display: inline-flex; align-items: center; justify-content: center; min-height: {T.TINGGI_CTA};
  padding: 0 {T.SP_5}; font: inherit; font-weight: 700; text-decoration: none; text-align: center; cursor: pointer;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; border: 0; border-radius: {T.RADIUS_KARTU}; }}
.hr-tombol:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.hr-tombol.sekunder {{ background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border: 2px solid {T.BORDER_KONTROL}; }}
.hr-tombol.sekunder:hover {{ border-color: {T.ANAK_AKSEN}; }}
"""

GAYA_HARIAN = GAYA_KARTU + f"""
.hr-isi {{ display: flex; flex-direction: column; gap: {T.SP_4}; padding-bottom: {T.SP_6}; }}
.hr-isi h1, .hr-isi h2, .hr-isi h3, .hr-isi p {{ margin: 0; }}
.hr-isi h1 {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_JUDUL_STITCH}; font-weight: 800; line-height: 1.2; }}
.hr-isi h2 {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
.hr-isi :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.hr-kartu {{ display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_5}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.hr-kartu.catatan {{ color: {T.ANAK_PERHATIAN_TEKS}; background: {T.ANAK_PERHATIAN_LATAR}; border-color: {T.ANAK_PERHATIAN_BORDER}; }}
.hr-redup {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
.hr-daftar {{ display: grid; grid-template-columns: 1fr; gap: {T.SP_3}; margin: 0; padding: 0; list-style: none; }}
.hr-daftar form {{ margin: 0; display: flex; }}
.hr-tingkat {{ display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_1}; width: 100%; min-height: {_TINGGI_PILIHAN};
  padding: {T.SP_3} {T.SP_4}; text-align: left; font: inherit; color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU}; cursor: pointer;
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU}; }}
.hr-tingkat:hover {{ border-color: {T.ANAK_AKSEN}; }}
.hr-tingkat b {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.hr-tingkat span {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.ANAK_TEKS_REDUP}; }}
.hr-tingkat .hr-lencana {{ padding: 0 {T.SP_2}; font-weight: 700; color: {T.ANAK_BAIK_TEKS}; background: {T.ANAK_BAIK_LATAR}; border-radius: {T.RADIUS_PIL}; }}
.hr-progres {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: 0; padding: 0; list-style: none; }}
.hr-progres li {{ display: inline-flex; align-items: center; justify-content: center; min-width: {_LEBAR_NOMOR}; height: {_LEBAR_NOMOR};
  font-weight: 800; background: {T.LATAR_KARTU}; border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_SEDANG}; }}
.hr-progres li.sudah {{ background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}; border-color: {T.ANAK_AKSEN}; }}
.hr-progres li.aktif {{ box-shadow: 0 0 0 2px {T.LATAR_MURID}, 0 0 0 4px {T.TEKS_JUDUL}; }}
.hr-soal {{ font-size: {T.UKURAN_SOAL}; font-weight: {T.BOBOT_SOAL}; line-height: {T.LINE_HEIGHT_SOAL}; }}
.hr-pilihan {{ display: grid; grid-template-columns: 1fr; gap: {T.SP_3}; margin: 0; padding: 0; border: 0; min-width: 0; }}
.hr-pilihan legend {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
.hr-pilih {{ display: flex; align-items: center; gap: {T.SP_3}; min-height: {_TINGGI_PILIHAN}; padding: {T.SP_2} {T.SP_4};
  font-size: {T.UKURAN_SOAL}; font-weight: 700; background: {T.LATAR_KARTU}; cursor: pointer;
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU}; }}
.hr-pilih:has(input:checked) {{ background: {T.ANAK_AKSEN_LATAR}; border-color: {T.ANAK_AKSEN}; }}
.hr-pilih:focus-within {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.hr-pilih input {{ flex: none; width: 1.25rem; height: 1.25rem; }}
.hr-huruf {{ flex: none; display: inline-flex; align-items: center; justify-content: center; width: {_LEBAR_NOMOR}; height: {_LEBAR_NOMOR};
  font-family: {T.FONT_HEADLINE}; font-weight: 800; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_BULAT}; }}
.hr-isi-pilihan {{ flex: 1; min-width: 0; overflow-wrap: anywhere; }}
.hr-tanda {{ flex: none; padding: 0 {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; border-radius: {T.RADIUS_PIL}; }}
.hr-pilih.benar {{ background: {T.ANAK_BAIK_LATAR}; border-color: {T.BORDER_TERSIMPAN}; cursor: default; }}
.hr-pilih.benar .hr-tanda {{ color: {T.ANAK_BAIK_TEKS}; }}
.hr-pilih.salah {{ background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; cursor: default; }}
.hr-pilih.salah .hr-tanda {{ color: {T.TEKS_GALAT}; }}
.hr-pilih.diam {{ cursor: default; }}
.hr-umpan {{ display: flex; flex-direction: column; gap: {T.SP_2}; padding: {T.SP_4}; border-radius: {T.RADIUS_KARTU}; }}
.hr-umpan.benar {{ color: {T.ANAK_BAIK_TEKS}; background: {T.ANAK_BAIK_LATAR}; }}
.hr-umpan.salah {{ color: {T.ANAK_PERHATIAN_TEKS}; background: {T.ANAK_PERHATIAN_LATAR}; }}
.hr-umpan h2 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; }}
.hr-cara {{ padding: {T.SP_4}; background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_KARTU}; }}
.hr-cara b {{ display: block; margin-bottom: {T.SP_1}; }}
.hr-aksi {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; }}
.hr-aksi .hr-tombol {{ flex: 1 1 10rem; }}
.hr-angka {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_ANGKA_FUNNEL}; font-weight: 800; }}
.hr-isi svg {{ max-width: 100%; height: auto; }}
@media (min-width: {T.ANAK_BATAS_HP}) {{
  .hr-daftar {{ grid-template-columns: 1fr 1fr; }}
  .hr-pilihan {{ grid-template-columns: 1fr 1fr; }}
}}
"""
