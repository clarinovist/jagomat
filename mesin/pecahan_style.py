"""CSS pecahan bertumpuk; hanya dimuat permukaan layar yang merendernya.

Bank cetak tidak memuat pecahan bertumpuk agar tetap identik dengan baseline
recovery pada uji pasangan rilis; cetak tetap memakai teks "5/6".
"""

GAYA_PECAHAN = """
.pecahan {
  display: inline-flex; flex-direction: column; vertical-align: middle;
  text-align: center; line-height: 1.05; white-space: nowrap;
  margin: 0 .12em; font-size: .92em;
}
.pecahan-angka { display: block; padding: 0 .18em; }
.pecahan-angka:first-child { border-bottom: 1px solid currentColor; }
@media print { .pecahan { break-inside: avoid; } }
"""
