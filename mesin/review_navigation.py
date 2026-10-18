"""Proyeksi pekerjaan tinjauan guru; bukan penilaian atau syarat bukti."""

PERLU_DIPERIKSA = 'perlu_diperiksa'
TANYAKAN_CARA = 'tanyakan_cara'
TINJAUAN_TERCATAT = 'tinjauan_tercatat'
KATEGORI_TINJAUAN = frozenset({
    PERLU_DIPERIKSA, TANYAKAN_CARA, TINJAUAN_TERCATAT,
})

_KODE = {'B', 'K', 'H', 'E', 'T', 'N'}
_PEMAHAMAN = {'bisa_menjelaskan', 'ragu', 'menghafal'}


def klasifikasi_tinjauan(*, benar, kode, pilihan, pemahaman, dilewati,
                         masalah=False, sumber_perlu_diperiksa=False,
                         terkonfirmasi=False, draf=False,
                         tidak_konsisten=False):
    """Kelompokkan pekerjaan UI dari state efektif secara fail-closed.

    Hasil ini tidak mengesahkan outcome. Nilai asing, draf request-local, dan
    error selalu kembali ke kelompok yang perlu diperiksa.
    """
    if any(type(nilai) is not bool for nilai in (
            benar, dilewati, masalah, sumber_perlu_diperiksa,
            terkonfirmasi, draf, tidak_konsisten)):
        return PERLU_DIPERIKSA
    if kode not in (None, '', *_KODE):
        return PERLU_DIPERIKSA
    if pemahaman not in (None, '', *_PEMAHAMAN):
        return PERLU_DIPERIKSA
    if pilihan not in (None, '', 'benar', *_KODE):
        return PERLU_DIPERIKSA
    if draf or masalah or sumber_perlu_diperiksa or tidak_konsisten:
        return PERLU_DIPERIKSA
    if dilewati:
        return TINJAUAN_TERCATAT
    if kode == 'T' and not pilihan:
        return PERLU_DIPERIKSA
    if not benar and not kode:
        return PERLU_DIPERIKSA
    if (benar or kode == 'N') and not pemahaman:
        return TANYAKAN_CARA
    if not (pilihan or pemahaman or terkonfirmasi):
        return PERLU_DIPERIKSA
    return TINJAUAN_TERCATAT


def tindakan_tinjauan(*, benar, kode, pilihan, pemahaman, dilewati,
                      masalah=False, sumber_perlu_diperiksa=False,
                      terkonfirmasi=False, draf=False,
                      tidak_konsisten=False):
    """Label tindakan untuk kategori tertutup; kategori asing fail-closed."""
    kategori = klasifikasi_tinjauan(
        benar=benar, kode=kode, pilihan=pilihan, pemahaman=pemahaman,
        dilewati=dilewati, masalah=masalah,
        sumber_perlu_diperiksa=sumber_perlu_diperiksa,
        terkonfirmasi=terkonfirmasi, draf=draf,
        tidak_konsisten=tidak_konsisten,
    )
    if kategori == TINJAUAN_TERCATAT:
        return ''
    if kategori == TANYAKAN_CARA:
        return 'Periksa cara anak'
    if sumber_perlu_diperiksa:
        return 'Periksa sumber jawaban'
    if masalah or tidak_konsisten or draf:
        return 'Periksa isian yang ditandai'
    if kode == 'T' and not pilihan:
        return 'Pastikan kebutuhan pengenalan'
    if not benar and not kode:
        return 'Tentukan penilaian'
    return 'Periksa langkah anak'


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
