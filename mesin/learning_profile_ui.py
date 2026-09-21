"""Form native metadata sekolah, terpisah dari konfigurasi latihan."""
import html

from learning_profile import label_kelas_sekolah


KETERANGAN_KELAS = (
    'Kelas sekolah hanya informasi profil; tidak menentukan kemampuan, '
    'mengubah soal lama, atau memulai ulang rencana belajar.'
)


def baca_kelas_form(nilai):
    """Terima hanya pilihan kelas formulir; kosong berarti belum dikonfirmasi."""
    if nilai == '':
        return None
    if type(nilai) is not str or nilai not in ('1', '2', '3', '4', '5', '6'):
        raise ValueError('Pilih kelas sekolah 1–6 atau Kelas belum diisi.')
    return int(nilai)


def baca_revisi_form(nilai):
    """Revisi wajib kanonis; jangan menganggap field hilang sebagai revisi nol."""
    if (type(nilai) is not str or not nilai or len(nilai) > 18
            or not nilai.isascii() or not nilai.isdecimal()
            or str(int(nilai)) != nilai):
        raise ValueError('Revisi profil tidak sah. Muat ulang sebelum menyimpan.')
    return int(nilai)


def opsi_kelas(kelas_sekolah=None):
    """Pilihan nullable, tidak pernah memilih kelas dari profil parameter."""
    label_kelas_sekolah(kelas_sekolah)
    return ''.join(
        '<option value="%s"%s>%s</option>' % (
            '' if kelas is None else kelas,
            ' selected' if kelas == kelas_sekolah else '',
            label_kelas_sekolah(kelas),
        ) for kelas in (None, 1, 2, 3, 4, 5, 6)
    )


def form_kelas(profil, nama):
    """Satu entry point edit kelas di akun; revisi berasal dari snapshot baca."""
    identitas = 'kelas-sekolah-%d' % profil.siswa_id
    return (
        '<form method="post" action="/akun" class="form-kelas-sekolah">'
        '<input type="hidden" name="aksi" value="kelas_sekolah">'
        '<input type="hidden" name="siswa_id" value="%d">'
        '<input type="hidden" name="revisi_profil" value="%d">'
        '<label for="%s">Kelas sekolah %s</label>'
        '<select id="%s" name="kelas_sekolah" aria-describedby="keterangan-kelas">%s</select>'
        '<button type="submit" class="tombol-kecil">Simpan kelas sekolah</button>'
        '</form>'
    ) % (profil.siswa_id, profil.revisi, identitas, html.escape(nama), identitas,
         opsi_kelas(profil.kelas_sekolah))
