"""Renderer murni halaman admin "Detail order" `/admin/pesanan/order?id=` (Fase C): tanpa I/O, tanpa JS baru.

Isi: ringkasan (nominal persis dengan tiga digit unik disorot, cara bayar, waktu WIB), urutan perjalanan order
(hanya langkah yang datanya ada), tautan ke bukti transfer, lalu dua tindakan berisiko dalam `<details>`:
"Periksa status ke penyedia pembayaran" dan "Pengecualian: catat uang kembali". Kedua form tetap memakai token
final admin (csrf + tinjauan terikat aksi dan sesi + sandi ulang) dan hanya muncul untuk sesi berkuki.

Data hanya proyeksi minimal dari `pesanan_admin_order.detail_order`: tanpa kontak, nama anak, siswa_id,
transaksi_id, atau payload. Semua nilai dinamis di-escape; waktu ledger (UTC naif) ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple

import admin_labels as L
import admin_pesanan_pages as ui
import pesanan_admin_order as po
from admin_komponen import e
from admin_verifikasi_pages import nominal_sorot

JUDUL = "Detail order"
SUBJUDUL = "Ringkasan, perjalanan, dan tindakan untuk satu order. Tanpa kontak dan nama anak."
PRODUK = "Peta Kemampuan"
COPY_KEMBALI = "← Pesanan & transfer"
COPY_LIHAT_BUKTI = "Lihat bukti transfer"
COPY_CARA = {po.CARA_TRANSFER: "Transfer rekening", po.CARA_QRIS: "QRIS (penyedia pembayaran)"}
COPY_LANGKAH = {
    po.LANGKAH_DIBUAT: "Order dibuat",
    po.LANGKAH_BUKTI: "Bukti transfer diunggah",
    po.LANGKAH_SETUJU: "Transfer disetujui",
    po.LANGKAH_TOLAK: "Bukti ditolak",
    po.LANGKAH_LUNAS: "Pembayaran dikonfirmasi penyedia",
    po.LANGKAH_PERLU_DIPERIKSA: "Pembayaran perlu diperiksa",
    po.LANGKAH_REFUND: "Uang kembali dicatat",
    po.LANGKAH_KEDALUWARSA: "Waktu bayar habis",
}
COPY_RINGKAS_PERIKSA = "Periksa status ke penyedia pembayaran"
COPY_PERIKSA_JELAS = (
    "Tanyakan status order ini ke penyedia pembayaran; status pesanan mengikuti jawabannya. "
    "Hanya berguna untuk pembayaran QRIS."
)
COPY_PERIKSA_GERBANG = "Pembayaran sedang ditutup, jadi pemeriksaan ke penyedia pembayaran tidak tersedia."
COPY_PERIKSA_TIDAK_PERLU = (
    "Pemeriksaan hanya untuk order yang belum dibayar atau sudah kedaluwarsa. Status order ini tidak perlu diperiksa."
)
COPY_TOMBOL_PERIKSA = "Periksa status"
COPY_RINGKAS_REFUND = "Pengecualian: catat uang kembali"
COPY_KEBIJAKAN_REFUND = (
    "Peta Kemampuan tidak ada uang kembali. Pengecualian: laporan terlambat dan keluarga memilih uang kembali "
    "penuh. Aplikasi hanya mencatat; dana dikembalikan manual lewat rekening."
)
COPY_TOMBOL_REFUND = "Catat uang kembali"
COPY_KONFIRMASI_REFUND = (
    "Catat uang kembali untuk order ini? Aplikasi tidak mengembalikan dana; catatan ini ber-audit "
    "dan tidak dapat dibatalkan."
)
COPY_SATU_CATATAN = "Satu order hanya bisa punya satu catatan uang kembali."
# Enum `catatan_kode` yang diterima server tidak berubah. `kebijakan` dipilih untuk "laporan terlambat"
# (pengecualian Keputusan 18) dan menjadi pilihan pertama (bawaan <select>).
URUTAN_ALASAN_REFUND = ("kebijakan", "kesalahan_sistem", "permintaan_pembeli", "lainnya")
COPY_ALASAN_REFUND = {
    "kebijakan": "Laporan terlambat (pengecualian kebijakan)",
    "kesalahan_sistem": "Kesalahan sistem",
    "permintaan_pembeli": "Permintaan keluarga",
    "lainnya": "Lainnya",
}

_SANDI = ('<label>Sandi admin saat ini<input type="password" name="reauth" required '
          'autocomplete="current-password"></label>')


def _waktu(nilai: str) -> str:
    return e(L.tanggal(nilai + "Z"))


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _form_periksa(token: Tuple[str, str]) -> str:
    return ('<form method="post" action="%s">%s%s<button class="admin-tombol admin-tombol-sekunder" '
            'type="submit">%s</button></form>' % (ui.RUTE_PERIKSA, _hidden(*token), _SANDI, e(COPY_TOMBOL_PERIKSA)))


def _form_refund(token: Tuple[str, str]) -> str:
    opsi = "".join('<option value="%s">%s</option>' % (e(k), e(COPY_ALASAN_REFUND[k])) for k in URUTAN_ALASAN_REFUND)
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Alasan<select name="catatan_kode" required>%s</select></label>%s'
            '<button class="admin-tombol admin-bahaya-garis" type="submit">%s</button></form>'
            % (ui.RUTE_REFUND, e(COPY_KONFIRMASI_REFUND), _hidden(*token), opsi, _SANDI, e(COPY_TOMBOL_REFUND)))


def _baris_rincian(label: str, nilai: str) -> str:
    return "<div><dt>%s</dt><dd>%s</dd></div>" % (e(label), nilai)


def _ringkasan(detail: Mapping) -> str:
    status = detail["status"]
    badge = '<span class="admin-badge%s">%s</span>' % (
        ui.KELAS_BADGE.get(status, ""), e(ui.COPY_STATUS.get(status, status)))
    nominal = nominal_sorot(detail["nominal"]) if detail["nominal"] else "—"
    rincian = "".join((
        _baris_rincian("Produk", e(PRODUK)),
        _baris_rincian("Akun", '<code class="admin-id">%s</code>' % e(detail["akun"])),
        _baris_rincian("Nominal transfer", "<strong>%s</strong>" % nominal),
        _baris_rincian("Dibayar lewat", e(COPY_CARA.get(detail["cara"], COPY_CARA[po.CARA_QRIS]))),
        _baris_rincian("Dibuat", _waktu(detail["dibuat"])),
        _baris_rincian("Batas bayar", _waktu(detail["kedaluwarsa"]))))
    return ('<section class="admin-kartu"><div class="admin-kepala-aksi"><h2>Order %s</h2>%s</div>'
            '<dl class="admin-order-rincian">%s</dl></section>' % (L.referensi(detail["order_id"]), badge, rincian))


def _langkah(langkah: Mapping) -> str:
    label = COPY_LANGKAH.get(langkah["kode"], langkah["kode"])
    banyak = langkah["kode"] == po.LANGKAH_BUKTI and langkah["jumlah"] > 1
    jumlah = " (%d berkas)" % langkah["jumlah"] if banyak else ""
    return '<li><span class="admin-titik"></span><span>%s%s<br><span class="admin-meta">%s</span></span></li>' % (
        e(label), e(jumlah), _waktu(langkah["waktu"]))


def _perjalanan(detail: Mapping) -> str:
    tautan = ""
    if detail["jumlah_bukti"]:
        tautan = '<p><a class="admin-tautan" href="%s?order=%s">%s</a></p>' % (
            ui.RUTE_VERIFIKASI, e(detail["order_id"]), e(COPY_LIHAT_BUKTI))
    return ('<section class="admin-kartu"><h2>Perjalanan order</h2><ol class="admin-perjalanan">%s</ol>%s</section>'
            % ("".join(_langkah(x) for x in detail["langkah"]), tautan))


def _lipat(ringkas: str, isi: str) -> str:
    return ('<details class="admin-kartu admin-lipat"><summary>%s</summary>'
            '<div class="admin-lipat-isi">%s</div></details>' % (e(ringkas), isi))


def _penjelasan_periksa(detail: Mapping, gerbang_terbuka: bool, tersedia: bool) -> str:
    if tersedia:
        return COPY_PERIKSA_JELAS
    if not gerbang_terbuka and detail["status"] in ui.STATUS_PERIKSA:
        return COPY_PERIKSA_GERBANG
    return COPY_PERIKSA_TIDAK_PERLU


def _periksa(detail: Mapping, gerbang_terbuka: bool, forms: Mapping) -> str:
    tersedia = ui.AKSI_PERIKSA in ui.aksi_tersedia(detail, gerbang_terbuka)
    form = _form_periksa(forms[ui.AKSI_PERIKSA]) if tersedia and ui.AKSI_PERIKSA in forms else ""
    teks = _penjelasan_periksa(detail, gerbang_terbuka, tersedia)
    return _lipat(COPY_RINGKAS_PERIKSA, "<p>%s</p>%s" % (e(teks), form))


def _refund(detail: Mapping, gerbang_terbuka: bool, forms: Mapping) -> str:
    """Hanya untuk order yang boleh dicatat uang kembalinya; selain itu kosong (tidak ada pintu samping)."""
    if ui.AKSI_REFUND not in ui.aksi_tersedia(detail, gerbang_terbuka):
        return ""
    form = _form_refund(forms[ui.AKSI_REFUND]) if ui.AKSI_REFUND in forms else ""
    isi = '<p>%s</p>%s<p class="admin-meta">%s</p>' % (e(COPY_KEBIJAKAN_REFUND), form, e(COPY_SATU_CATATAN))
    return _lipat(COPY_RINGKAS_REFUND, isi)


def halaman(detail: Mapping, *, gerbang_terbuka: bool, forms: Optional[Mapping] = None,
            hasil: Optional[str] = None, baca_saja: bool = False) -> str:
    """Isi section Detail order. `forms` = {aksi: (csrf, tinjauan)} hanya untuk aksi yang tampil; kosong = tanpa form.

    `hasil` = kode hasil aksi sebelumnya (banner) atau None; `baca_saja` = sesi bukan kuki (tanpa tombol).
    """
    token = forms or {}
    sesi = '<p class="admin-meta">%s</p>' % e(ui.COPY_TANPA_SESI) if baca_saja else ""
    kembali = '<p><a class="admin-tautan" href="%s">%s</a></p>' % (ui.RUTE, e(COPY_KEMBALI))
    umpan = ui.umpan_balik(hasil if hasil in ui.KODE_HASIL_DETAIL else None)
    return (kembali + umpan + sesi + _ringkasan(detail) + _perjalanan(detail)
            + _periksa(detail, gerbang_terbuka, token) + _refund(detail, gerbang_terbuka, token))
