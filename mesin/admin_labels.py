"""Label dan format presentasi admin; tidak menafsirkan ulang status domain."""
from datetime import datetime, timedelta, timezone
import html
import re

WIB = timezone(timedelta(hours=7))
BULAN = ('Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des')
BULAN_PENUH = ('Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember')
HARI = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu')
LABEL_STATUS = {
    'account_missing_id': 'ID akun belum tersedia', 'no_students': 'Belum memiliki siswa',
    'student_without_login': 'Belum ada login tertaut', 'duplicate_explicit_login': 'Lebih dari satu login menunjuk siswa',
    'owner_without_account': 'Pemilik tanpa akun', 'owner_empty': 'Pemilik siswa kosong',
    'owner_admin': 'Dimiliki akun pengelola', 'orphan_login': 'Login menunjuk siswa yang tidak ada',
    'legacy_orphan_login': 'Login lama tidak punya kandidat siswa',
    'legacy_login_unverified': 'Login lama belum terverifikasi',
    'legacy_same_name_ambiguous': 'Nama lama cocok ke beberapa siswa',
    'perlu_diperiksa': 'Perlu diperiksa', 'succeeded': 'Berhasil', 'ok': 'Berhasil',
    'uncertain': 'Belum pasti', 'reserved': 'Menunggu hasil', 'pending': 'Belum diproses',
    'failed_before_commit': 'Gagal sebelum tersimpan', 'conflict': 'Konflik',
    'cancelled': 'Dibatalkan', 'ready': 'Siap', 'running': 'Sedang diproses',
    'partial': 'Sebagian selesai', 'stopped': 'Dihentikan', 'attention': 'Perlu pemeriksaan',
    'completed': 'Selesai', 'tak_pasti': 'Belum pasti', 'selesai': 'Selesai',
    'gagal': 'Gagal', 'tertunda': 'Tertunda', 'transisi': 'Transisi', 'publik': 'Pendaftaran publik',
    'nonaktif': 'Nonaktif', 'rekonsiliasi': 'Rekonsiliasi', 'checkout': 'Checkout',
    'penegakan': 'Penegakan', 'admin': 'Pengelola', 'pembayaran': 'Pembayaran', 'layanan': 'Layanan',
}


def label_status(nilai):
    return LABEL_STATUS.get(nilai, str(nilai).replace('_', ' ').capitalize())


def waktu(nilai):
    """String tanpa zona dari proyeksi existing adalah WIB, bukan UTC."""
    if nilai in (None, ''):
        return None
    try:
        if isinstance(nilai, (int, float)):
            return datetime.fromtimestamp(nilai, WIB)
        dt = datetime.fromisoformat(str(nilai).replace('Z', '+00:00'))
        return dt.replace(tzinfo=WIB) if dt.tzinfo is None else dt.astimezone(WIB)
    except (ValueError, TypeError, OverflowError):
        return None


def tanggal(nilai):
    dt = waktu(nilai)
    return '%d %s %d, %s WIB' % (dt.day, BULAN[dt.month-1], dt.year, dt.strftime('%H.%M')) if dt else '—'


HARI_PER_MINGGU = 7
HARI_PER_BULAN = 30
HARI_PER_TAHUN = 365


def _selisih_hari(dt, sekarang):
    acuan = (sekarang or datetime.now(WIB)).astimezone(WIB)
    return (acuan.date() - dt.date()).days


def relatif(nilai, sekarang=None, *, kosong='Belum pernah'):
    """Selisih hari kalender WIB sebagai teks awam: "Hari ini", "2 hari lalu", "3 minggu lalu"."""
    dt = waktu(nilai)
    if dt is None:
        return kosong
    selisih = _selisih_hari(dt, sekarang)
    if selisih <= 0:
        return 'Hari ini'
    if selisih == 1:
        return 'Kemarin'
    if selisih < HARI_PER_MINGGU:
        return '%d hari lalu' % selisih
    if selisih < HARI_PER_BULAN:
        return '%d minggu lalu' % (selisih // HARI_PER_MINGGU)
    if selisih < HARI_PER_TAHUN:
        return '%d bulan lalu' % (selisih // HARI_PER_BULAN)
    return '%d tahun lalu' % (selisih // HARI_PER_TAHUN)


def judul_hari(nilai, sekarang=None):
    """Judul kelompok per hari: "Hari ini", "Kemarin", atau tanggal WIB ("20 Nov 2026")."""
    dt = waktu(nilai)
    if dt is None:
        return 'Waktu tidak tercatat'
    selisih = _selisih_hari(dt, sekarang)
    if selisih == 0:
        return 'Hari ini'
    if selisih == 1:
        return 'Kemarin'
    return '%d %s %d' % (dt.day, BULAN[dt.month - 1], dt.year)


def hari_ini(sekarang=None):
    dt = sekarang or datetime.now(WIB)
    return '%s, %d %s %d' % (HARI[dt.weekday()], dt.day, BULAN_PENUH[dt.month-1], dt.year)


def referensi(nilai):
    teks = str(nilai or '—')
    return '<code class="admin-id" title="%s">%s</code>' % (html.escape(teks, quote=True), html.escape(teks))


PANJANG_REFERENSI_PENDEK = 8  # awal id sesudah awalan; cukup untuk dicocokkan mata di daftar
_AWALAN_ID = re.compile(r"^[a-z]{2,5}_")


def referensi_pendek(nilai):
    """Label ringkas id ledger untuk DAFTAR: `#xxxxxxxx`, id penuh hanya di `title` dan halaman Detail.

    Satu sel daftar tidak perlu 40 karakter heksadesimal (mis. `ord_` + 32 heks): cukup penanda unik yang bisa
    dicocokkan mata, sedangkan id penuh tetap bisa disalin di halaman Detail lewat :func:`referensi`. Hanya awalan
    huruf kecil (mis. `ord_`, `akun_`) yang dibuang; id tanpa awalan dipendekkan apa adanya.
    """
    teks = str(nilai or '')
    if not teks:
        return '—'
    awalan = _AWALAN_ID.match(teks)
    pendek = '#' + teks[awalan.end():][:PANJANG_REFERENSI_PENDEK] if awalan else '#' + teks[:PANJANG_REFERENSI_PENDEK]
    return '<code class="admin-id" title="%s">%s</code>' % (html.escape(teks, quote=True), html.escape(pendek))
