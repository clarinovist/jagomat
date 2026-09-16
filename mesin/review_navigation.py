"""Proyeksi pekerjaan tinjauan guru; bukan penilaian atau syarat bukti."""


def tindakan_tinjauan(*, benar, kode, pilihan, pemahaman, dilewati,
                      masalah=False, sumber_perlu_diperiksa=False,
                      terkonfirmasi=False):
    """Bedakan hasil jawaban dari pekerjaan guru memakai nilai efektif host."""
    if masalah:
        return 'Periksa isian yang ditandai'
    if dilewati:
        return ''
    if sumber_perlu_diperiksa:
        return 'Periksa sumber jawaban'
    if kode == 'T' and not pilihan:
        return 'Pastikan kebutuhan pengenalan'
    if not benar and not kode:
        return 'Tentukan penilaian'
    if (benar or kode == 'N') and not pemahaman:
        return 'Periksa cara anak'
    if not (pilihan or pemahaman or terkonfirmasi):
        return 'Periksa langkah anak'
    return ''


def render_progres(jumlah, tercatat, *, draf=False):
    """Progres pengisian saat render, tidak menyatakan hasil sudah disahkan."""
    catatan = (
        'Mengikuti isian yang ditampilkan; perubahan belum disimpan.' if draf else
        'Diperbarui setelah disimpan. Tinjauan tercatat bukan berarti materi sudah dikuasai.'
    )
    return (
        '<section class="koreksi-progres-st" aria-labelledby="judul-progres-tinjauan">'
        '<p class="editorial-alis-st">Progres tinjauan</p>'
        f'<h2 id="judul-progres-tinjauan">{tercatat} dari {jumlah} tinjauan tercatat</h2>'
        f'<progress max="{max(jumlah, 1)}" value="{tercatat}" '
        'aria-labelledby="judul-progres-tinjauan"></progress>'
        f'<p class="koreksi-catatan-st">{catatan}</p></section>'
    )


def render_antrean(daftar, *, draf=False):
    """Render pintasan ke kartu prioritas; kartu tertutup tetap bisa dibuka."""
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
        if draf else 'Dengarkan cara anak, lalu catat hasil tinjauan.'
    )
    return (
        '<nav class="antrean-tinjauan-st" aria-labelledby="judul-antrean-tinjauan">'
        f'<h2 id="judul-antrean-tinjauan">{len(daftar)} soal perlu ditinjau</h2>'
        f'<p>{catatan}</p><ul>{tautan}</ul></nav>'
    )
