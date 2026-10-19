"""Label dan format presentasi admin; tidak menafsirkan ulang status domain."""
from datetime import datetime, timedelta, timezone
import html

WIB = timezone(timedelta(hours=7))
BULAN = ('Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des')
BULAN_PENUH = ('Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember')
HARI = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu')
LABEL_STATUS = {
    'account_missing_id': 'ID akun belum tersedia', 'no_students': 'Belum memiliki siswa',
    'student_without_login': 'Belum punya login', 'duplicate_explicit_login': 'Lebih dari satu login menunjuk siswa',
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


def hari_ini(sekarang=None):
    dt = sekarang or datetime.now(WIB)
    return '%s, %d %s %d' % (HARI[dt.weekday()], dt.day, BULAN_PENUH[dt.month-1], dt.year)


def referensi(nilai):
    teks = str(nilai or '—')
    pendek = teks if len(teks) <= 20 else teks[:8] + '…' + teks[-6:]
    return '<code class="admin-id" title="%s">%s</code>' % (html.escape(teks, quote=True), html.escape(pendek))
