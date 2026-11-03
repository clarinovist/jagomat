"""Gaya penyajian pertanyaan bersama untuk layar dan cetak."""
import design_tokens as T

GAYA_PENYAJIAN = f"""
[data-fingerprint-penyajian] {{ min-width: 0; overflow-wrap: anywhere; }}
/* Pecahan bertumpuk dari mesin/pecahan.py; tetap tanpa JavaScript. */
.pecahan {{
  display: inline-flex; flex-direction: column; vertical-align: middle;
  text-align: center; line-height: 1.05; white-space: nowrap;
  margin: 0 .12em; font-size: .92em;
}}
.pecahan-angka {{ display: block; padding: 0 .18em; }}
.pecahan-angka:first-child {{ border-bottom: 1px solid currentColor; }}
@media print {{ .pecahan {{ break-inside: avoid; }} }}
[data-fingerprint-penyajian] svg {{
  display: block; width: {T.LEBAR_VISUAL_SOAL}; max-width: 100%; height: auto;
  margin: {T.JARAK_VISUAL_SOAL} auto;
}}
@media print {{
  .rumus-kartu-st, .bantuan-visual {{ break-inside: avoid; }}
  .hasil-soal-st {{ break-inside: avoid; }}
}}
"""
