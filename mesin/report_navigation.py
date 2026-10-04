"""Navigasi URL laporan; hanya menyaring tampilan, bukan bukti atau rekomendasi."""
import html
from urllib.parse import parse_qs, urlencode


def parameter_laporan(query):
    """Parameter tunggal saja; nilai ganda memakai bawaan, bukan urutan URL."""
    return {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()
            if len(v) == 1}


def tautan_tab(siswa_id, bagian='ringkasan', **opsi):
    """URL mentah tab Perkembangan; satu base /anak agar terasa satu halaman."""
    data = {}
    if bagian not in ('', None, 'ringkasan'):
        data['bagian'] = bagian
    data.update({k: v for k, v in opsi.items() if v not in ('', None)})
    data = {'section': 'perkembangan', **data}
    return f'/anak/{siswa_id}?' + urlencode(data)


def tujuan_alias_lama(siswa_id, query):
    """Tujuan kanonis deep link lama; dipanggil hanya setelah ownership guard."""
    data = parse_qs(query, keep_blank_values=True)
    if any(len(nilai) != 1 for nilai in data.values()):
        return None
    nilai = {k: v[0] for k, v in data.items()}
    section = nilai.get('section', '')
    tampilan = nilai.get('tampilan', '')

    def tujuan(bagian, **opsi):
        return tautan_tab(siswa_id, bagian, **opsi)

    if section == 'riwayat':
        if tampilan in ('', 'sesi'):
            return f'/anak/{siswa_id}?section=riwayat'
        if tampilan == 'mingguan':
            return tujuan('ringkasan', rincian='tren')
        if tampilan == 'catatan':
            return tujuan('penguasaan', rincian='catatan')
    if section == 'penguasaan':
        umum = {
            k: nilai.get(k, '') for k in ('materi', 'status', 'halaman')
        }
        if tampilan == 'konteks':
            return tujuan('penguasaan', rincian='konteks', **umum)
        if tampilan == 'kriteria':
            return tujuan('penguasaan', rincian='kriteria', **umum)
        if tampilan == 'pilot':
            return tujuan('perjalanan', rincian='pilot')
        if tampilan == 'perjalanan':
            return tujuan('perjalanan', halaman=nilai.get('halaman', ''))
    return None


def url_laporan(siswa_id, section='ringkasan', **opsi):
    """URL atribut HTML; canonical tab /anak agar satu base dengan profil."""
    return html.escape(tautan_tab(siswa_id, section, **opsi), quote=True)


def pilihan(label, opsi, aktif, tautan):
    """Tautan native; aria-current, border dan bobot menandai pilihan aktif."""
    return (f'<nav class="laporan-pilihan" aria-label="{html.escape(label)}">' + ''.join(
        f'<a href="{tautan(kode)}"' + (' aria-current="true"' if kode == aktif else '')
        + '>' + html.escape(nama) + '</a>' for kode, nama in opsi) + '</nav>')


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
