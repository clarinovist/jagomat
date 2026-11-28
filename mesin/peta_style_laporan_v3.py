"""CSS laporan Peta versi 3 (F6): layar HP dulu, lalu lebar desktop lewat container query, dan cetak A4 dua lembar.

Semua nilai warna, jarak, dan huruf datang dari `design_tokens` (`T.*`); tidak ada hex atau rgba di sini. Aturan
melebar untuk desktop memakai `@container` pada `.ortu-peta-v3-isi-st`, bukan lebar viewport. Tidak ada animasi baru.
Kartu lain di halaman orang tua disembunyikan saat cetak lewat `:has()`, seperti laporan versi 2.
"""
from __future__ import annotations

import design_tokens as T

KONTEINER_V3 = "ortu-peta-v3"
LEBAR_SEMPIT_V3 = "40rem"
LEBAR_SEDANG_V3 = "52rem"
LEBAR_LAYAR_LEBAR = "72rem"

GAYA_PETA_V3 = f"""
.ortu-peta-v3-st {{ color: {T.TEKS_JUDUL}; font-family: {T.FONT_BODY}; }}
.ortu-peta-v3-isi-st {{ container: {KONTEINER_V3} / inline-size; display: flex; flex-direction: column; gap: {T.SP_5}; }}
.ortu-peta-v3-isi-st > * {{ min-width: 0; }}
.ortu-peta-v3-st h2, .ortu-peta-v3-st h3 {{ margin: 0; font-family: {T.FONT_HEADLINE}; line-height: 1.2; text-wrap: balance; }}
.ortu-peta-v3-st p {{ margin: 0; }}
.ortu-peta-v3-st ul, .ortu-peta-v3-st ol {{ margin: 0; padding: 0; }}
.ortu-peta-v3-st :is(button, a, summary):focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.ortu-peta-v3-kepala-st {{ display: grid; grid-template-columns: auto 1fr auto; gap: {T.SP_3} {T.SP_5}; align-items: center; }}
.ortu-peta-v3-merek-st {{ display: flex; align-items: center; gap: {T.SP_2}; font: 800 1.15rem/1.2 {T.FONT_HEADLINE}; color: {T.AKSEN_TEAL_TUA}; }}
.ortu-peta-v3-merek-st img {{ width: {T.LOGO_BADGE}; height: {T.LOGO_BADGE}; flex: none; }}
.ortu-peta-v3-merek-st small {{ display: block; font: 600 .72rem/1.3 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-judul-st {{ text-align: center; }}
.ortu-peta-v3-judul-st h2 {{ font-size: clamp(1.45rem, 3.4cqi, 2.1rem); font-weight: 800; letter-spacing: -.02em; }}
.ortu-peta-v3-judul-st p {{ font-size: .92rem; color: {T.TEKS_VARIAN}; margin-top: 2px; }}
.ortu-peta-v3-cetak-baris-st {{ display: flex; justify-content: flex-end; }}
.ortu-peta-v3-cetak-st {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_4}; border: 0; border-radius: {T.RADIUS_PIL};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE}; cursor: pointer; }}
.ortu-peta-v3-kartu-st {{ background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR};
  padding: {T.SP_5}; }}
.ortu-peta-v3-kartu-st > h3 {{ font-size: 1.2rem; font-weight: 800; color: {T.TEKS_JUDUL}; margin-bottom: {T.SP_3}; }}
.ortu-peta-v3-atas-st {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: {T.SP_4}; align-items: stretch; }}
.ortu-peta-v3-atas-st > * {{ min-width: 0; }}
.ortu-peta-v3-hero-st {{ display: grid; grid-template-columns: 96px 1fr; gap: {T.SP_4}; align-items: center; padding: {T.SP_5};
  border: 1px solid {T.LAPORAN_V3_HERO_TEPI}; border-radius: {T.RADIUS_KARTU_BESAR};
  background: linear-gradient(135deg, {T.LAPORAN_V3_HERO_ATAS}, {T.LAPORAN_V3_HERO_BAWAH} 70%); }}
.ortu-peta-v3-maskot-st {{ width: 96px; height: auto; }}
.ortu-peta-v3-gelembung-st {{ display: table; margin-bottom: {T.SP_2}; background: {T.ANAK_PERHATIAN_LATAR}; color: {T.AKSEN_AMBER_TUA};
  font: 700 .82rem/1.3 {T.FONT_HEADLINE}; padding: 6px {T.SP_3}; border-radius: {T.RADIUS_KARTU}; }}
.ortu-peta-v3-kategori-st {{ display: inline; font: 800 clamp(1.5rem, 3.6cqi, 2.2rem)/1.1 {T.FONT_HEADLINE}; letter-spacing: -.02em;
  background: linear-gradient(transparent 55%, {T.ANAK_PERHATIAN_BORDER} 55%); padding: 0 4px; }}
.ortu-peta-v3-hero-st p:not(.ortu-peta-v3-kategori-st) {{ font-size: .95rem; color: {T.TEKS_VARIAN}; max-width: 40ch; margin-top: {T.SP_2}; }}
.ortu-peta-v3-skor-kartu-st {{ display: flex; align-items: center; }}
.ortu-peta-v3-skor-st {{ display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: {T.SP_5}; align-items: center; width: 100%; }}
.ortu-peta-v3-skor-st > * {{ min-width: 0; }}
.ortu-peta-v3-skor-kartu-st h3 {{ font-size: 1.05rem; font-weight: 800; margin-bottom: 6px; }}
.ortu-peta-v3-cincin-st {{ position: relative; width: 150px; height: 150px; }}
.ortu-peta-v3-cincin-st svg {{ width: 100%; height: 100%; transform: rotate(-90deg); }}
.ortu-peta-v3-cincin-jalur-st {{ stroke: {T.ANAK_NETRAL_LATAR}; }}
.ortu-peta-v3-cincin-isi-st {{ stroke: {T.AKSEN_MURID_UTAMA}; }}
.ortu-peta-v3-cincin-angka-st {{ position: absolute; inset: 0; display: grid; place-content: center; text-align: center; line-height: 1; }}
.ortu-peta-v3-cincin-angka-st b {{ font: 800 2.8rem {T.FONT_HEADLINE}; letter-spacing: -.03em; }}
.ortu-peta-v3-cincin-angka-st small {{ font: 700 1rem {T.FONT_HEADLINE}; color: {T.TEKS_VARIAN}; margin-top: 4px; }}
.ortu-peta-v3-legenda-st {{ list-style: none; }}
.ortu-peta-v3-legenda-st li {{ display: grid; grid-template-columns: 14px 1fr auto; gap: {T.SP_2}; align-items: center;
  padding: {T.SP_2} 0; border-bottom: 1px solid {T.ANAK_BORDER}; font-size: .92rem; }}
.ortu-peta-v3-legenda-st li:last-child {{ border-bottom: 0; }}
.ortu-peta-v3-legenda-st b {{ font-family: {T.FONT_HEADLINE}; }}
.ortu-peta-v3-titik-st {{ width: 14px; height: 14px; border-radius: {T.RADIUS_BULAT}; }}
.ortu-peta-v3-titik-dikuasai-st {{ background: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-titik-perlu-st {{ background: {T.AKSEN_MURID_AMBER}; }}
.ortu-peta-v3-titik-belum-st {{ background: {T.AKSEN_MURID_KORAL}; }}
.ortu-peta-v3-ket-st {{ font-size: .8rem; color: {T.TEKS_VARIAN}; margin-top: 6px; }}
.ortu-peta-v3-peta-st {{ position: relative; overflow: hidden; padding: {T.SP_5} {T.SP_5} 52px; border: 1px solid {T.LAPORAN_V3_TEPI_PETA};
  border-radius: {T.RADIUS_KARTU_BESAR}; background: radial-gradient(120% 70% at 50% 120%, {T.LAPORAN_V3_RUMPUT} 0 40%, transparent 41%),
  linear-gradient(180deg, {T.LAPORAN_V3_LANGIT_ATAS} 0%, {T.LAPORAN_V3_LANGIT_BAWAH} 100%); }}
.ortu-peta-v3-peta-st > h3 {{ display: inline-block; background: {T.LAPORAN_V3_PAPAN}; color: {T.LAPORAN_V3_PAPAN_TEKS};
  font: 800 1rem {T.FONT_HEADLINE}; padding: {T.SP_2} {T.SP_4}; border-radius: {T.RADIUS_SEDANG};
  box-shadow: 0 4px 0 {T.LAPORAN_V3_PAPAN_TEPI}; transform: rotate(-2deg); margin-bottom: {T.SP_3}; }}
.ortu-peta-v3-urut-teks-st {{ font-size: .85rem; color: {T.TEKS_VARIAN}; margin-bottom: {T.SP_4}; }}
.ortu-peta-v3-jalur-st {{ position: relative; display: flex; flex-wrap: wrap; gap: {T.SP_3}; list-style: none; align-items: stretch; }}
.ortu-peta-v3-jalur-st::before {{ content: ""; position: absolute; left: 4%; right: 4%; top: 50%; border-top: 4px dashed {T.LAPORAN_V3_JALUR}; z-index: 0; }}
.ortu-peta-v3-pulau-st {{ position: relative; z-index: 1; flex: 1 1 120px; min-width: 0; display: flex; flex-direction: column;
  align-items: center; gap: 6px; text-align: center; background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KARTU_BESAR};
  padding: {T.SP_3} {T.SP_2}; border: 2px solid transparent;
  box-shadow: 0 8px 0 -2px {T.LAPORAN_V3_PULAU_BAYANG}, {T.LAPORAN_BAYANGAN_TIMBUL}; }}
.ortu-peta-v3-pulau-st:nth-child(even) {{ transform: translateY(22px); }}
.ortu-peta-v3-urut-st {{ position: absolute; top: -10px; left: -6px; width: 26px; height: 26px; border-radius: {T.RADIUS_BULAT};
  display: grid; place-items: center; font: 800 .78rem {T.FONT_HEADLINE}; background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH};
  border: 2px solid {T.TEKS_PUTIH}; }}
.ortu-peta-v3-ikon-st {{ width: 52px; height: 52px; border-radius: 16px; display: grid; place-items: center;
  background: {T.ANAK_LATAR_KARTU_HALUS}; border: 1px solid {T.ANAK_BORDER}; flex: none; }}
.ortu-peta-v3-ikon-st svg {{ width: 34px; height: 34px; }}
.ortu-peta-v3-teks-st {{ display: flex; flex-direction: column; align-items: center; gap: 4px; }}
.ortu-peta-v3-teks-st b {{ font: 800 .92rem/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-nilai-st {{ font: 800 .82rem {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-label-st {{ font: 700 .74rem {T.FONT_HEADLINE}; padding: 2px 10px; border-radius: {T.RADIUS_PIL}; }}
.ortu-peta-v3-pulau-st.ortu-peta-v3-dikuasai-st {{ border-color: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-pulau-st.ortu-peta-v3-perlu-st {{ border-color: {T.AKSEN_MURID_AMBER}; }}
.ortu-peta-v3-pulau-st.ortu-peta-v3-belum-st {{ border-color: {T.AKSEN_MURID_KORAL}; }}
.ortu-peta-v3-dikuasai-st .ortu-peta-v3-ikon-st {{ color: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-perlu-st .ortu-peta-v3-ikon-st {{ color: {T.AKSEN_AMBER_TUA}; }}
.ortu-peta-v3-belum-st .ortu-peta-v3-ikon-st {{ color: {T.AKSEN_KORAL_TUA}; }}
.ortu-peta-v3-dikuasai-st .ortu-peta-v3-label-st {{ background: {T.ANAK_BAIK_LATAR}; color: {T.TEKS_TERSIMPAN}; }}
.ortu-peta-v3-perlu-st .ortu-peta-v3-label-st {{ background: {T.ANAK_PERHATIAN_LATAR}; color: {T.AKSEN_AMBER_TUA}; }}
.ortu-peta-v3-belum-st .ortu-peta-v3-label-st {{ background: {T.LAPORAN_V3_KORAL_MUDA}; color: {T.TEKS_GALAT}; }}
.ortu-peta-v3-ujung-st {{ background: transparent; box-shadow: none; border: 0; justify-content: center; }}
.ortu-peta-v3-bawah-st {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: {T.SP_4}; align-items: start; }}
.ortu-peta-v3-ujung-st .ortu-peta-v3-teks-st span {{ font-size: .75rem; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-kolom-st {{ display: flex; flex-direction: column; gap: {T.SP_4}; min-width: 0; }}
.ortu-peta-v3-detail-st {{ list-style: none; display: grid; gap: {T.SP_3}; }}
.ortu-peta-v3-baris-st {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; align-items: center;
  gap: 4px {T.SP_3}; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.ortu-peta-v3-nama-st {{ display: flex; flex-direction: column; gap: 2px; min-width: 0; }}
.ortu-peta-v3-nama-st b {{ font: 800 .95rem/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-meter-st {{ width: 100%; height: 10px; }}
.ortu-peta-v3-angka-st {{ font: 800 .9rem {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; font-variant-numeric: tabular-nums;
  white-space: nowrap; }}
.ortu-peta-v3-temuan-st {{ list-style: none; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.ortu-peta-v3-temuan-st li {{ display: grid; grid-template-columns: 26px 1fr; gap: 10px; font-size: .92rem; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-temuan-st b {{ color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-tanda-st {{ width: 24px; height: 24px; border-radius: {T.RADIUS_BULAT}; display: grid; place-items: center;
  color: {T.TEKS_PUTIH}; font: 800 .8rem {T.FONT_HEADLINE}; }}
.ortu-peta-v3-tanda-dikuasai-st {{ background: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-tanda-perlu-st {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-tanda-belum-st {{ background: {T.AKSEN_KORAL_TUA}; }}
.ortu-peta-v3-urutan-st {{ list-style: none; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.ortu-peta-v3-langkah-st {{ display: grid; grid-template-columns: 36px 1fr; gap: {T.SP_3}; align-items: center; padding: 10px 12px;
  border-radius: {T.RADIUS_KARTU}; font: 800 .95rem {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-no-langkah-st {{ width: 36px; height: 36px; border-radius: {T.RADIUS_BULAT}; display: grid; place-items: center;
  font: 800 1rem {T.FONT_HEADLINE}; }}
.ortu-peta-v3-belum-st.ortu-peta-v3-langkah-st {{ background: {T.LAPORAN_V3_KORAL_MUDA}; }}
.ortu-peta-v3-belum-st .ortu-peta-v3-no-langkah-st {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}
.ortu-peta-v3-perlu-st.ortu-peta-v3-langkah-st {{ background: {T.ANAK_PERHATIAN_LATAR}; }}
.ortu-peta-v3-perlu-st .ortu-peta-v3-no-langkah-st {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; }}
.ortu-peta-v3-dikuasai-st.ortu-peta-v3-langkah-st {{ background: {T.ANAK_BAIK_LATAR}; }}
.ortu-peta-v3-dikuasai-st .ortu-peta-v3-no-langkah-st {{ background: {T.LAPORAN_V3_HIJAU}; color: {T.TEKS_PUTIH}; }}
.ortu-peta-v3-sub-st {{ font-size: .86rem; color: {T.TEKS_VARIAN}; margin: -4px 0 {T.SP_3}; }}
.ortu-peta-v3-perilaku-st {{ list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: {T.SP_3}; }}
.ortu-peta-v3-perilaku-item-st {{ background: {T.ANAK_LATAR_KARTU_HALUS}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px;
  padding: {T.SP_3}; display: flex; flex-direction: column; gap: 6px; }}
.ortu-peta-v3-atas-p-st {{ display: flex; align-items: center; gap: {T.SP_2}; }}
.ortu-peta-v3-atas-p-st b {{ font: 800 .9rem/1.2 {T.FONT_HEADLINE}; }}
.ortu-peta-v3-ik-st {{ width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; flex: none;
  background: {T.LATAR_KARTU}; border: 1px solid {T.ANAK_BORDER}; color: {T.AKSEN_TEAL_TUA}; }}
.ortu-peta-v3-status-st {{ align-self: flex-start; font: 700 .74rem {T.FONT_HEADLINE}; padding: 2px 10px; border-radius: {T.RADIUS_PIL}; }}
.ortu-peta-v3-baik-st {{ background: {T.ANAK_BAIK_LATAR}; color: {T.TEKS_TERSIMPAN}; }}
.ortu-peta-v3-perhatian-st {{ background: {T.ANAK_PERHATIAN_LATAR}; color: {T.AKSEN_AMBER_TUA}; }}
.ortu-peta-v3-perilaku-item-st p {{ font-size: .8rem; color: {T.TEKS_VARIAN}; line-height: 1.4; }}
.ortu-peta-v3-halaman2-st {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
.ortu-peta-v3-ubin-st {{ list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: {T.SP_2}; margin-bottom: {T.SP_3}; }}
.ortu-peta-v3-ubin-st li {{ background: {T.ANAK_LATAR_KARTU_HALUS}; border: 1px solid {T.ANAK_BORDER}; border-radius: 14px; padding: {T.SP_2} {T.SP_3}; }}
.ortu-peta-v3-ubin-st b {{ display: block; font: 800 1.35rem/1.1 {T.FONT_HEADLINE}; font-variant-numeric: tabular-nums; }}
.ortu-peta-v3-ubin-st span {{ display: block; margin-top: 2px; font-size: .78rem; line-height: 1.3; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-waktu-st {{ display: block; width: 100%; height: 150px; margin-top: {T.SP_4}; border-bottom: 2px solid {T.ANAK_BORDER}; overflow: visible; }}
.ortu-peta-v3-batang-benar-st {{ fill: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-batang-salah-st {{ fill: {T.LAPORAN_V3_BATANG_SALAH}; }}
.ortu-peta-v3-batang-cepat-st {{ fill: {T.LAPORAN_V3_BATANG_CEPAT}; }}
.ortu-peta-v3-batang-abu-st {{ fill: {T.LAPORAN_V3_BATANG_ABU}; }}
.ortu-peta-v3-rata-st {{ fill: none; stroke: {T.LAPORAN_V3_RATA}; stroke-width: 2; }}
.ortu-peta-v3-no-st {{ display: flex; padding-top: 4px; font: 700 .7rem {T.FONT_HEADLINE}; color: {T.TEKS_VARIAN}; text-align: center; }}
.ortu-peta-v3-no-st span {{ flex: 1 1 0; min-width: 0; }}
.ortu-peta-v3-leg-st {{ display: flex; flex-wrap: wrap; gap: 6px {T.SP_4}; margin-top: {T.SP_3}; list-style: none;
  font-size: {T.UKURAN_TEKS_CATATAN}; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-leg-st li {{ display: inline-flex; align-items: center; gap: 6px; }}
.ortu-peta-v3-swatch-st {{ display: inline-block; width: 14px; height: 14px; border-radius: {T.RADIUS_KECIL}; }}
.ortu-peta-v3-swatch-benar-st {{ background: {T.LAPORAN_V3_HIJAU}; }}
.ortu-peta-v3-swatch-salah-st {{ background: {T.LAPORAN_V3_BATANG_SALAH}; }}
.ortu-peta-v3-swatch-cepat-st {{ background: {T.LAPORAN_V3_BATANG_CEPAT}; }}
.ortu-peta-v3-swatch-abu-st {{ background: {T.LAPORAN_V3_BATANG_ABU}; }}
.ortu-peta-v3-swatch-rata-st {{ height: 0; width: 18px; border-top: 2px dashed {T.LAPORAN_V3_RATA}; border-radius: 0; }}
.ortu-peta-v3-sr-st {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }}
.ortu-peta-v3-sorot-st {{ margin-top: {T.SP_3}; background: {T.ANAK_PERHATIAN_LATAR}; border-radius: 14px; padding: {T.SP_3};
  font-size: .88rem; color: {T.AKSEN_AMBER_TUA}; }}
.ortu-peta-v3-dua-st {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: {T.SP_4}; align-items: start; }}
.ortu-peta-v3-dua-st > * {{ min-width: 0; }}
.ortu-peta-v3-saran-st {{ list-style: none; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.ortu-peta-v3-saran-st li {{ padding: {T.SP_3}; border-radius: 14px; background: {T.ANAK_AKSEN_LATAR}; color: {T.TEKS_VARIAN};
  font-size: .86rem; }}
.ortu-peta-v3-rekom-kartu-st {{ border: 2px solid {T.AKSEN_TEAL_TUA}; }}
.ortu-peta-v3-rekom-kartu-st p {{ font-size: .92rem; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-catatan-st {{ font-size: .8rem; color: {T.TEKS_VARIAN}; }}
.ortu-peta-v3-penutup-st {{ position: relative; overflow: hidden; padding: {T.SP_5} {T.SP_5};
  background: linear-gradient(120deg, {T.AKSEN_TEAL_TUA} 0%, {T.LAPORAN_V3_PENUTUP_BAWAH} 100%);
  color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.ortu-peta-v3-penutup-st blockquote {{ margin: 0; }}
.ortu-peta-v3-penutup-st p {{ font: 800 clamp(1.1rem, 2.2cqi, 1.45rem)/1.35 {T.FONT_HEADLINE}; letter-spacing: -.01em; }}
.ortu-peta-v3-penutup-st p span {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; border-radius: {T.RADIUS_KECIL}; padding: 0 {T.SP_1}; }}
.ortu-peta-v3-penutup-st footer {{ margin-top: {T.SP_2}; font-size: .85rem; color: {T.LAPORAN_V3_PENUTUP_TEKS}; }}
@container {KONTEINER_V3} (max-width: {LEBAR_SEDANG_V3}) {{
  .ortu-peta-v3-perilaku-st, .ortu-peta-v3-ubin-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ortu-peta-v3-dua-st, .ortu-peta-v3-bawah-st {{ grid-template-columns: minmax(0, 1fr); }}
  .ortu-peta-v3-atas-st {{ grid-template-columns: minmax(0, 1fr); }}
}}
@container {KONTEINER_V3} (max-width: {LEBAR_SEMPIT_V3}) {{
  .ortu-peta-v3-kepala-st {{ grid-template-columns: 1fr auto; }}
  .ortu-peta-v3-judul-st {{ grid-column: 1 / -1; grid-row: 2; text-align: left; }}
  .ortu-peta-v3-skor-st {{ grid-template-columns: 1fr; justify-items: center; }}
  .ortu-peta-v3-skor-st .ortu-peta-v3-skor-teks-st {{ width: 100%; }}
  .ortu-peta-v3-jalur-st {{ flex-direction: column; }}
  .ortu-peta-v3-jalur-st::before {{ left: 50%; right: auto; top: 20px; bottom: 20px; border-top: 0; border-left: 4px dashed {T.LAPORAN_V3_JALUR}; }}
  .ortu-peta-v3-pulau-st {{ flex: none; width: 62%; flex-direction: row; text-align: left; padding: 10px 12px; }}
  .ortu-peta-v3-pulau-st:nth-child(even) {{ transform: none; align-self: flex-end; }}
  .ortu-peta-v3-pulau-st .ortu-peta-v3-teks-st {{ align-items: flex-start; }}
  .ortu-peta-v3-ujung-st {{ width: auto; align-self: center; }}
  .ortu-peta-v3-hero-st {{ grid-template-columns: 72px 1fr; }}
  .ortu-peta-v3-maskot-st {{ width: 72px; }}
  .ortu-peta-v3-ubin-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ortu-peta-v3-perilaku-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ortu-peta-v3-dua-st {{ grid-template-columns: minmax(0, 1fr); }}
}}
.funnel-alur-st:has(> .ortu-peta-v3-st) {{ max-width: {LEBAR_LAYAR_LEBAR}; }}
@page {{ size: A4 portrait; margin: 14mm; }}
@media print {{
  .funnel-alur-st:has(> .ortu-peta-v3-st) {{ max-width: none; }}
  .funnel-alur-st:has(> .ortu-peta-v3-st) > :not(.ortu-peta-v3-st) {{ display: none; }}
  .ortu-peta-v3-st {{ margin: 0; border: 0; box-shadow: none; background: {T.LATAR_KARTU}; }}
  .ortu-peta-v3-st, .ortu-peta-v3-st * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .ortu-peta-v3-isi-st {{ gap: {T.SP_3}; font-size: {T.UKURAN_BADAN_CETAK}; }}
  .ortu-peta-v3-kartu-st {{ padding: {T.SP_3} {T.SP_4}; }}
  .ortu-peta-v3-cetak-baris-st {{ display: none; }}
  .ortu-peta-v3-kartu-st, .ortu-peta-v3-pulau-st, .ortu-peta-v3-hero-st, .ortu-peta-v3-penutup-st,
  .ortu-peta-v3-perilaku-item-st, .ortu-peta-v3-baris-st, .ortu-peta-v3-langkah-st, .ortu-peta-v3-kolom-st > *,
  .ortu-peta-v3-ubin-st li {{ break-inside: avoid; page-break-inside: avoid; }}
  .ortu-peta-v3-halaman2-st {{ break-before: page; page-break-before: always; }}
}}
"""
