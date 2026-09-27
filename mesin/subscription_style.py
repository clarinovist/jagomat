"""CSS checkout bersama; tidak memuat logika atau konfigurasi pembayaran."""

import design_tokens as T

GAYA_LANGGANAN = f"""
.langganan-panel {{max-width:{T.LEBAR_KONTEN};margin:0 auto}}
.langganan-panel .kartu {{padding:{T.SP_5};margin:{T.SP_4} 0;background:{T.LATAR_KARTU};border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS};border-radius:{T.RADIUS_KARTU_BESAR}}}
.langganan-panel .peringatan {{padding:{T.SP_4};border-left:4px solid {T.AKSEN_MURID_AMBER};background:{T.LATAR_CATATAN};color:{T.TEKS_UTAMA}}}
.langganan-panel label {{display:flex;gap:.75rem;align-items:center;min-height:{T.TARGET_SENTUH}}}
.langganan-panel input[type=checkbox] {{width:1.25rem;height:1.25rem;flex-shrink:0}}
.langganan-panel button,.langganan-panel .tombol {{min-height:{T.TARGET_SENTUH};display:inline-flex;align-items:center;justify-content:center;padding:{T.SP_3} {T.SP_4};border-radius:{T.RADIUS_KECIL}}}
.langganan-panel .qr {{display:block;width:280px;max-width:100%;height:auto;margin:{T.SP_4} auto}}
.langganan-panel .nominal {{font-size:{T.UKURAN_ANGKA_DEWASA};font-weight:800;color:{T.TEKS_JUDUL}}}
.langganan-panel fieldset {{border:0;padding:0;margin:{T.SP_4} 0}}
.langganan-panel :focus-visible {{outline:3px solid {T.TEKS_JUDUL};outline-offset:3px}}
.langganan-panel p,.langganan-panel a {{overflow-wrap:anywhere}}
@media(max-width:480px) {{.langganan-panel .kartu {{padding:{T.SP_4}}} .langganan-panel button {{width:100%}}}}
"""
