"""Renderer murni halaman admin detail verifikasi transfer rekening (tanpa I/O, tanpa JS baru).

Isi: nominal yang harus masuk (49.000 + kode unik, persis), daftar bukti dengan pratinjau lewat rute
admin-saja (`/admin/pesanan/bukti?id=`), riwayat keputusan, dan dua form (Setujui, Tolak) hanya bila
status `menunggu_verifikasi` dan sesi berkuki (form Tolak dilipat dalam `<details>`; token tinjauan tetap per aksi). Tidak menampilkan nama berkas tersimpan, nama berkas klien,
sha256, kontak, atau nama anak. Semua nilai dinamis di-escape; waktu ledger (UTC naif) ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple

import admin_labels as L
from admin_komponen import e
from admin_pesanan_pages import COPY_STATUS, RUTE, KELAS_BADGE
from pesanan_transfer_pages import rupiah
from schema_transfer import BATAS_ALASAN

RUTE_VERIFIKASI = RUTE + "/verifikasi"
RUTE_BUKTI = RUTE + "/bukti"
RUTE_SETUJUI = RUTE + "/setujui"
RUTE_TOLAK = RUTE + "/tolak"
JUDUL = "Verifikasi transfer"
SUBJUDUL = "Periksa bukti transfer terhadap nominal persis, lalu setujui atau tolak. Tanpa kontak dan nama anak."
AKSI_SETUJUI = "setujui_transfer"
AKSI_TOLAK = "tolak_transfer"
STATUS_MENUNGGU = "menunggu_verifikasi"
BYTE_PER_KB = 1024
_EKSTENSI = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
_LABEL_MIME = {"image/jpeg": "JPEG", "image/png": "PNG", "application/pdf": "PDF"}
_LABEL_KEADAAN = {"menunggu": "Menunggu keputusan", "diputuskan": "Sudah diputuskan",
                  "dihapus": "Dihapus (retensi 30 hari)"}
_LABEL_KEPUTUSAN = {"setuju": "Disetujui", "tolak": "Ditolak"}

COPY_KONFIRMASI_SETUJUI = (
    "Setujui transfer ini? Pesanan menjadi lunas dan keputusan tidak dapat dibatalkan; hanya catatan refund "
    "yang dapat ditambahkan sesudahnya."
)
COPY_KONFIRMASI_TOLAK = (
    "Tolak bukti ini? Guru akan melihat alasannya dan dapat mengunggah ulang selama waktu pembayaran terbuka."
)
COPY_CATATAN_NOMINAL = (
    "Cocokkan nominal di mutasi rekening dengan angka di atas sampai tiga digit terakhir. Hanya bukti yang "
    "Anda lihat di halaman ini yang akan diputuskan; bila guru mengunggah bukti baru, buka ulang halaman ini."
)
COPY_LANJUT = {
    "verifikasi_setuju": "Transfer sebelumnya disetujui. Ini transfer berikutnya.",
    "verifikasi_tolak": "Transfer sebelumnya ditolak. Ini transfer berikutnya.",
}
COPY_RINGKAS_TOLAK = "Tolak bukti…"
JUMLAH_DIGIT_UNIK = 3
COPY_BUKTI_DIHAPUS = "Berkas sudah dihapus sesuai retensi."
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk menyetujui atau menolak."
COPY_TIDAK_ADA_BUKTI = "Belum ada bukti."
COPY_TIDAK_ADA_KEPUTUSAN = "Belum ada keputusan."
COPY_BUKTI_TIDAK_TERSEDIA = "Berkas bukti tidak tersedia (sudah dihapus sesuai retensi atau tidak ditemukan)."
COPY_GALAT_KONFLIK = (
    "Pesanan ini tidak sedang menunggu verifikasi, sudah diputuskan, atau ada bukti baru sejak Anda membuka "
    "halaman verifikasi. Buka ulang halaman verifikasi; tidak ada yang diubah."
)
COPY_GALAT_ALASAN = (
    "Alasan penolakan wajib diisi (1 sampai %d karakter, tanpa karakter kontrol). Tidak ada yang diubah."
    % BATAS_ALASAN
)
COPY_BERKAS_RUSAK = "Berkas bukti tidak bisa ditampilkan. Tidak ada yang diubah; periksa penyimpanan bukti."


def nama_unduhan(mime: str) -> str:
    """Nama berkas generik untuk Content-Disposition (tidak pernah nama dari klien)."""
    return "bukti-transfer" + _EKSTENSI[mime]


def _waktu(nilai: str) -> str:
    return e(L.tanggal(nilai + "Z"))


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


_SANDI = ('<label>Sandi admin saat ini<input type="password" name="reauth" required '
          'autocomplete="current-password"></label>')


def _form_setujui(token: Tuple[str, str]) -> str:
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s%s'
            '<button class="admin-tombol" type="submit">Setujui transfer</button></form>'
            % (RUTE_SETUJUI, e(COPY_KONFIRMASI_SETUJUI), _hidden(*token), _SANDI))


def _form_tolak(token: Tuple[str, str]) -> str:
    """Form Tolak dilipat; normalnya hanya satu kolom sandi (form Setujui) yang terlihat."""
    return ('<details class="admin-form-tolak"><summary>%s</summary>'
            '<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Alasan penolakan<input type="text" name="alasan" required maxlength="%d" '
            'autocomplete="off"></label>%s'
            '<button class="admin-tombol admin-bahaya" type="submit">Tolak bukti</button></form></details>'
            % (e(COPY_RINGKAS_TOLAK), RUTE_TOLAK, e(COPY_KONFIRMASI_TOLAK), _hidden(*token), BATAS_ALASAN, _SANDI))


def _nominal_sorot(nominal: int) -> str:
    """`Rp49.007` dengan tiga digit terakhir (kode unik) disorot; teks tetap terbaca utuh tanpa jeda."""
    teks = rupiah(nominal)
    awal, kode = teks[:-JUMLAH_DIGIT_UNIK], teks[-JUMLAH_DIGIT_UNIK:]
    return '%s<mark class="admin-digit-unik">%s</mark>' % (e(awal), e(kode))


def _pratinjau(bukti: Mapping) -> str:
    alamat = "%s?id=%d" % (RUTE_BUKTI, bukti["id"])
    if bukti["keadaan"] == "dihapus":
        return e(COPY_BUKTI_DIHAPUS)
    gambar = ('<img src="%s" alt="Bukti transfer nomor %d" class="admin-bukti-gambar">' % (alamat, bukti["id"])
              if bukti["mime"].startswith("image/") else "")
    return gambar + ('<p><a class="admin-tautan" href="%s" target="_blank" rel="noopener noreferrer">Buka</a> '
                     '<a class="admin-tautan" href="%s&amp;unduh=1">Unduh</a></p>' % (alamat, alamat))


def _baris_bukti(bukti: Mapping) -> str:
    ukuran = max(1, -(-bukti["ukuran"] // BYTE_PER_KB))
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % sel for sel in (
        bukti["id"], _waktu(bukti["diunggah"]), e(_LABEL_MIME.get(bukti["mime"], bukti["mime"])),
        "%d KB" % ukuran, e(_LABEL_KEADAAN[bukti["keadaan"]]), _pratinjau(bukti)))


def _tabel(judul: str, kepala: Tuple[str, ...], baris: str, kosong: str) -> str:
    th = "".join('<th scope="col">%s</th>' % k for k in kepala)
    isi = baris or '<tr><td colspan="%d" class="admin-kosong">%s</td></tr>' % (len(kepala), e(kosong))
    return ('<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala"><h2>%s</h2></div>'
            '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="%s"><table class="admin-tabel">'
            '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div></section>' % (e(judul), e(judul), th, isi))


def _riwayat(keputusan) -> str:
    baris = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(_LABEL_KEPUTUSAN.get(k["keputusan"], k["keputusan"])), e(k["alasan"] or "—"), _waktu(k["dibuat"]))
        for k in keputusan)
    return _tabel("Riwayat keputusan", ("Keputusan", "Alasan", "Waktu"), baris, COPY_TIDAK_ADA_KEPUTUSAN)


def _ringkasan(detail: Mapping) -> str:
    status = detail["status"]
    badge = '<span class="admin-badge%s">%s</span>' % (KELAS_BADGE.get(status, ""), e(COPY_STATUS.get(status, status)))
    nominal = _nominal_sorot(detail["nominal"]) if detail["nominal"] else "—"
    return ('<section class="admin-kartu"><h2>%s</h2>'
            '<p>Order %s · Akun <code class="admin-id">%s</code> · %s</p>'
            '<p>Nominal yang harus masuk: <strong>%s</strong></p><p class="admin-meta">%s</p>'
            '<p><a class="admin-tautan" href="%s?status=menunggu">Kembali ke daftar menunggu verifikasi</a></p>'
            '</section>' % (e(JUDUL), L.referensi(detail["order_id"]), e(detail["akun"]), badge, nominal,
                            e(COPY_CATATAN_NOMINAL), RUTE))


def _form_keputusan(detail: Mapping, forms: Optional[Mapping]) -> str:
    if detail["status"] != STATUS_MENUNGGU or not forms:
        return ""
    return ('<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Keputusan</h2>%s%s</section>'
            % (_form_setujui(forms["setujui"]), _form_tolak(forms["tolak"])))


def _banner_lanjut(lanjut: Optional[str]) -> str:
    if lanjut not in COPY_LANJUT:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_LANJUT[lanjut])


def halaman(detail: Mapping, forms: Optional[Mapping], *, baca_saja: bool = False,
            lanjut: Optional[str] = None) -> str:
    """Isi section detail. `forms` = {'setujui': (csrf, tinjauan), 'tolak': (csrf, tinjauan)} atau None.

    `lanjut` = kode hasil keputusan sebelumnya (tampil sebagai banner "transfer berikutnya") atau None.
    """
    sesi = '<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI) if baca_saja else ""
    bukti = "".join(_baris_bukti(b) for b in detail["bukti"])
    return (_banner_lanjut(lanjut) + _ringkasan(detail) + sesi
            + _tabel("Bukti transfer", ("No.", "Diunggah", "Jenis", "Ukuran", "Keadaan", "Pratinjau"), bukti,
                     COPY_TIDAK_ADA_BUKTI)
            + _riwayat(detail["keputusan"]) + _form_keputusan(detail, forms))


def halaman_bukti_tidak_tersedia() -> str:
    """Kartu ramah (status 404) untuk bukti terhapus, hilang, atau id tak dikenal."""
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Bukti tidak tersedia</h2><p>%s</p></section>'
            % e(COPY_BUKTI_TIDAK_TERSEDIA))


def halaman_bukti_rusak() -> str:
    """Kartu jujur (status 503) bila berkas bukti tidak cocok dengan catatan atau tak bisa dibaca aman."""
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Bukti tidak bisa ditampilkan</h2><p>%s</p>'
            '</section>' % e(COPY_BERKAS_RUSAK))
