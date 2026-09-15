"""Pintasan tinjauan guru; tidak menyimpan data atau menentukan penilaian."""


def render_antrean(daftar, *, draf=False):
    """Render nomor kartu yang diproyeksikan host, seluruh kartu tetap tersedia."""
    if not daftar:
        return ''
    if any(type(sid) is not int or type(nomor) is not int or sid < 1 or nomor < 1
           for sid, nomor in daftar):
        raise ValueError('Identitas kartu tinjauan tidak sah.')
    tautan = ''.join(
        f'<li><a href="#tinjau-soal-{sid}">Soal {nomor}</a></li>'
        for sid, nomor in daftar
    )
    catatan = (
        'Antrean mengikuti isian yang sedang ditampilkan; perubahan belum disimpan.'
        if draf else 'Pintasan ke pekerjaan yang masih perlu keputusan atau pemeriksaan sumber.'
    )
    return (
        '<nav class="antrean-tinjauan-st" aria-labelledby="judul-antrean-tinjauan">'
        f'<h2 id="judul-antrean-tinjauan">{len(daftar)} soal perlu ditinjau</h2>'
        f'<p>{catatan} Semua soal tetap ada di bawah.</p>'
        f'<ul>{tautan}</ul>'
        '<p class="koreksi-catatan-st">Pintasan ini bukan pengesahan hasil. '
        'Simpan tinjauan untuk melanjutkan nanti.</p></nav>'
    )
