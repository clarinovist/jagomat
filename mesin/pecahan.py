"""Tampilan pecahan sederhana sebagai pecahan bertumpuk, tanpa JavaScript.

Konten tetap menyimpan teks polos ("5/6"). Fungsi di sini hanya mengubah
tampilan: token bilangan bulat pendek yang dipisah satu garis miring menjadi
dua baris dengan garis pecahan. Bukan parser matematika:

- hanya angka/angka (1–3 digit tiap sisi);
- "km/jam", tanggal "2026/11", dan rantai "1/2/3" dibiarkan apa adanya;
- label pembaca layar "5 per 6" supaya angka tidak dibaca sebagai tanggal.

Pemanggil wajib sudah memastikan teks berasal dari konten tervalidasi; fungsi
ini tetap meng-escape HTML sendiri agar aman dipakai pada teks bebas.
"""

from __future__ import annotations

import html
import re

# Batas kiri/kanan menolak huruf, angka, titik, dan garis miring lain supaya
# satuan (km/jam), versi (v1/2), tanggal (2026/11), dan rantai (1/2/3) tidak
# ikut berubah. Tanda hubung/kurung/operator tetap dianggap batas.
_POLA = re.compile(r"(?<![\w/.])(\d{1,3})/(\d{1,3})(?![\w/]|\.\d)")


def _token(pembilang: str, penyebut: str) -> str:
    return (
        f'<span class="pecahan" role="math" aria-label="{pembilang} per {penyebut}">'
        f'<span class="pecahan-angka" aria-hidden="true">{pembilang}</span>'
        f'<span class="pecahan-angka" aria-hidden="true">{penyebut}</span></span>'
    )


def render(teks: str) -> str:
    """Escape teks lalu ubah pecahan angka/angka menjadi markup bertumpuk."""
    aman = html.escape(teks)
    return _POLA.sub(lambda cocok: _token(cocok.group(1), cocok.group(2)), aman)
