"""Navigasi URL laporan; hanya menyaring tampilan, bukan bukti atau rekomendasi."""
import html
from urllib.parse import parse_qs, urlencode


def parameter_laporan(query):
    """Parameter tunggal saja; nilai ganda memakai bawaan, bukan urutan URL."""
    return {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()
            if len(v) == 1}


def url_laporan(siswa_id, section='ringkasan', **opsi):
    """URL atribut HTML dengan encoding nilai dan escaping pemisah."""
    data = {'section': section}
    data.update({k: v for k, v in opsi.items() if v not in ('', None)})
    return html.escape(f'/laporan/{siswa_id}?' + urlencode(data), quote=True)


def pilihan(label, opsi, aktif, tautan):
    """Tombol navigasi berupa tautan native, dengan penanda selain warna."""
    return (f'<nav class="laporan-pilihan" aria-label="{html.escape(label)}">' + ''.join(
        f'<a href="{tautan(kode)}"' + (' aria-current="true"' if kode == aktif else '')
        + '>' + ('<span aria-hidden="true">✓ </span>' if kode == aktif else '')
        + html.escape(nama) + '</a>' for kode, nama in opsi) + '</nav>')


def halaman_daftar(daftar, halaman, ukuran):
    """Potong presentasi secara deterministik; nilai di luar batas dijepit."""
    jumlah = max(1, (len(daftar) + ukuran - 1) // ukuran)
    try:
        nomor = min(jumlah, max(1, int(halaman)))
    except (ValueError, TypeError):
        nomor = 1
    return daftar[(nomor - 1) * ukuran:nomor * ukuran], nomor, jumlah


def navigasi_halaman(nomor, jumlah, tautan):
    if jumlah <= 1:
        return ''
    sebelum = f'<a href="{tautan(nomor - 1)}">← Sebelumnya</a>' if nomor > 1 else ''
    sesudah = f'<a href="{tautan(nomor + 1)}">Berikutnya →</a>' if nomor < jumlah else ''
    return ('<nav class="laporan-paginasi" aria-label="Halaman daftar">'
            f'{sebelum}<span>Halaman {nomor} dari {jumlah}</span>{sesudah}</nav>')
