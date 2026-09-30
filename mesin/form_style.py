"""Gaya kontrol form bersama yang harus konsisten di semua permukaan."""

import design_tokens as T


GAYA_SELECT = f"""
/* Chevron select digambar dengan CSS agar posisi konsisten antarbrowser.
   Kontrol tetap <select> native; hanya indikator visual bawaannya diganti. */
select:not([multiple]):not([size]) {{
  -webkit-appearance: none !important;
  appearance: none !important;
  padding-inline-end: {T.SP_7} !important;
  background-image:
    linear-gradient(45deg, transparent 50%, {T.TEKS_VARIAN} 50%),
    linear-gradient(135deg, {T.TEKS_VARIAN} 50%, transparent 50%) !important;
  background-position:
    right {T.SP_5} center,
    right {T.SP_4} center !important;
  background-size: {T.SP_2} {T.SP_2}, {T.SP_2} {T.SP_2} !important;
  background-repeat: no-repeat !important;
}}

/* Mode kontras paksa perlu indikator native karena background image dapat
   dihilangkan sistem operasi. */
@media (forced-colors: active) {{
  select:not([multiple]):not([size]) {{
    -webkit-appearance: menulist !important;
    appearance: auto !important;
    padding-inline-end: {T.SP_3} !important;
    background-image: none !important;
  }}
}}
"""
