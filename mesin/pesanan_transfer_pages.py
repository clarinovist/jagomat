"""Blok halaman dan teks jalur transfer rekening Paket Coba (renderer murni, HTML native).

Tidak membuka DB, tidak membuat token (pemanggil menyuntik `token_untuk`), tidak membaca
berkas. Aturan isi:

- Nominal hanya dari tagihan ledger (`TampilanTransfer.nominal` = 49.000 + kode unik) dan
  disorot harus persis. Tidak ada nominal dari form/URL.
- Rekening hanya setelah tagihan dibuat, bersama nominal dan batas waktu (WIB).
- Alasan penolakan admin ditampilkan ter-escape; tidak ada janji akses laporan.
- Pesan galat tetap, tanpa jalur berkas, id, atau `str(galat)`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from cek_pages import _a, _e
from pesanan_dasar import STATUS_BELUM_BAYAR, STATUS_DITOLAK, STATUS_MENUNGGU_VERIFIKASI
from schema_transfer import BATAS_UKURAN_BUKTI, MAKS_BUKTI

RUTE_TAGIHAN = "/pesanan/tagihan"
RUTE_BUKTI = "/pesanan/bukti"
RUTE_ULANG = "/pesanan/tagihan/ulang"
RUTE_POST = frozenset({RUTE_TAGIHAN, RUTE_BUKTI, RUTE_ULANG})
AKSI_TAGIHAN = "tagihan"
AKSI_BUKTI = "bukti"
AKSI_ULANG = "ulang_transfer"
WIB_JAM = 7
BYTE_PER_MB = 1024 * 1024
BATAS_MB = BATAS_UKURAN_BUKTI // BYTE_PER_MB
_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
          "Oktober", "November", "Desember")
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_ACCEPT_BUKTI = "image/jpeg,image/png,application/pdf"
_STATUS_BLOK = (STATUS_BELUM_BAYAR, STATUS_DITOLAK, STATUS_MENUNGGU_VERIFIKASI)

COPY_JUDUL = "Bayar lewat transfer"
COPY_PENGANTAR = (
    "Transfer ke rekening kami, lalu unggah bukti transfernya. Tekan tombol di bawah untuk "
    "melihat rekening dan nominal yang harus Anda transfer."
)
COPY_TOMBOL_TAGIHAN = "Buat tagihan transfer"
COPY_TOMBOL_UNGGAH = "Unggah bukti"
COPY_TOMBOL_UNGGAH_ULANG = "Unggah ulang bukti"
COPY_LABEL_BERKAS = "Bukti transfer (JPEG, PNG, atau PDF, maksimal %d MB)" % BATAS_MB
COPY_ATURAN = (
    "Transfer dan unggah bukti sebelum batas waktu di atas. Lewat batas itu, tagihan tidak "
    "bisa menerima bukti baru. Bukti yang sudah masuk tetap diperiksa tim."
)
COPY_DITOLAK = "Bukti terakhir belum sesuai. Alasan dari tim:"
COPY_MENUNGGU = "Bukti sudah kami terima. Tim akan memeriksanya; status berubah setelah bukti disetujui."
COPY_BATAS_TERCAPAI = (
    "Batas %d bukti sudah tercapai. Hubungi tim lewat WhatsApp bila masih perlu bantuan." % MAKS_BUKTI
)
COPY_JUDUL_QRIS = "Pilihan kedua: QRIS"
COPY_PETUNJUK_QRIS = "Pindai kode QRIS dengan aplikasi pembayaran Anda."
COPY_STATUS_PILIH = (
    "Pilih cara bayar di bawah. Status berubah setelah pembayaran terverifikasi, bukan saat "
    "Anda menekan tombol."
)
# Teks galat unggah/tagihan (halaman info, tanpa data internal)
COPY_TIPE_TIDAK_DIDUKUNG = "Jenis berkas tidak didukung. Unggah foto JPEG, PNG, atau berkas PDF."
COPY_BERKAS_KOSONG = "Berkas kosong. Pilih berkas bukti transfer, lalu coba lagi."
COPY_BERKAS_BESAR = "Berkas terlalu besar. Ukuran maksimal %d MB." % BATAS_MB
COPY_BERKAS_TAK_TERBACA = "Berkas tidak terbaca. Muat ulang halaman, pilih satu berkas, lalu coba lagi."
COPY_BELUM_ADA_TAGIHAN = "Buat tagihan transfer dulu, lalu unggah bukti transfernya."
COPY_JENDELA_TUTUP = "Waktu pembayaran sudah habis, jadi bukti tidak bisa diterima lagi."
COPY_TIDAK_TERIMA = "Pesanan ini sedang tidak menerima bukti transfer."
COPY_KODE_HABIS = (
    "Tagihan transfer belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim lewat WhatsApp."
)
COPY_TAGIHAN_TIDAK_BISA = "Tagihan transfer tidak bisa dibuat untuk pesanan ini."
COPY_JUDUL_ULANG = "Buka waktu pembayaran baru"
COPY_PENGANTAR_ULANG = (
    "Waktu pembayaran sebelumnya sudah habis dan belum ada bukti transfer yang masuk. Anda bisa membuka "
    "waktu pembayaran baru. Tagihan dan nominal transfer yang baru akan dibuat, jadi jangan memakai "
    "nominal sebelumnya."
)
COPY_TOMBOL_ULANG = "Buka waktu pembayaran baru"
COPY_ULANG_TIDAK_BISA = "Waktu pembayaran baru tidak bisa dibuka untuk pesanan ini."


def rupiah(nilai: int) -> str:
    """Format `Rp49.321` (titik ribuan)."""
    return "Rp" + format(nilai, ",").replace(",", ".")


def waktu_wib(waktu_utc: str) -> str:
    """Waktu ledger (UTC naif) sebagai '19 November 2026 pukul 17.00 WIB'."""
    waktu = datetime.strptime(waktu_utc, _FORMAT_WAKTU) + timedelta(hours=WIB_JAM)
    return "%d %s %d pukul %s WIB" % (waktu.day, _BULAN[waktu.month - 1], waktu.year,
                                      waktu.strftime("%H.%M"))


def _kartu(isi: str) -> str:
    return f'<div class="kartu-st">{isi}</div>'


def _catatan(teks: str) -> str:
    return f'<p class="funnel-catatan-st">{_e(teks)}</p>'


def _tombol(teks: str) -> str:
    return f'<p class="akun-aksi-sandi"><button type="submit" class="tombol-utama-akun">{_e(teks)}</button></p>'


def _form_tagihan(token: str) -> str:
    return (f'<form method="post" action="{RUTE_TAGIHAN}">'
            f'<input type="hidden" name="token" value="{_a(token)}">{_tombol(COPY_TOMBOL_TAGIHAN)}</form>')


def _form_ulang(token: str) -> str:
    return (f'<form method="post" action="{RUTE_ULANG}">'
            f'<input type="hidden" name="token" value="{_a(token)}">{_tombol(COPY_TOMBOL_ULANG)}</form>')


def _form_unggah(token: str, ulang: bool) -> str:
    return (
        f'<form method="post" action="{RUTE_BUKTI}" enctype="multipart/form-data">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        f'<p><label>{_e(COPY_LABEL_BERKAS)}<br>'
        f'<input type="file" name="berkas" accept="{_ACCEPT_BUKTI}" required></label></p>'
        f'{_tombol(COPY_TOMBOL_UNGGAH_ULANG if ulang else COPY_TOMBOL_UNGGAH)}</form>')


def _rincian(tampilan, rekening) -> str:
    nominal = rupiah(tampilan.nominal)
    return (
        f"<p>Bank: <strong>{_e(rekening.nama_bank)}</strong></p>"
        f"<p>Nomor rekening: <strong>{_e(rekening.nomor_label)}</strong></p>"
        f"<p>Atas nama: <strong>{_e(rekening.atas_nama)}</strong></p>"
        f'<p class="funnel-catatan-st">Nominal yang harus Anda transfer: <strong>{_e(nominal)}</strong>. '
        "Nominal harus persis sama sampai tiga digit terakhir; jangan dibulatkan.</p>"
        f"<p>Batas waktu: <strong>{_e(waktu_wib(tampilan.kedaluwarsa))}</strong></p>"
    )


def _aksi_unggah(tampilan, token_untuk) -> str:
    if tampilan.boleh_unggah:
        return _form_unggah(token_untuk(AKSI_BUKTI), tampilan.status == STATUS_DITOLAK)
    if tampilan.jumlah_bukti >= MAKS_BUKTI:
        return _catatan(COPY_BATAS_TERCAPAI)
    return ""


def _isi_dengan_tagihan(tampilan, rekening, token_untuk) -> str:
    isi = f"<h2>{_e(COPY_JUDUL)}</h2>"
    if tampilan.status == STATUS_DITOLAK and tampilan.alasan_tolak:
        isi += f'<p class="funnel-catatan-st">{_e(COPY_DITOLAK)} <strong>{_e(tampilan.alasan_tolak)}</strong></p>'
    if tampilan.status == STATUS_MENUNGGU_VERIFIKASI:
        isi += _catatan(COPY_MENUNGGU)
    isi += _rincian(tampilan, rekening)
    if tampilan.status != STATUS_MENUNGGU_VERIFIKASI:
        isi += _catatan(COPY_ATURAN)
    return isi + _aksi_unggah(tampilan, token_untuk)


def blok_transfer(tampilan, rekening, token_untuk) -> str:
    """Kartu 'Bayar lewat transfer' sesuai status; '' bila status tidak relevan (lunas, dst.).

    Status kedaluwarsa: kartu 'Buka waktu pembayaran baru' hanya bila `tampilan.boleh_ulang`.

    `token_untuk(aksi)` membuat token form (hanya dipanggil bila form ditampilkan).
    """
    if tampilan.boleh_tagihan:
        return _kartu(f"<h2>{_e(COPY_JUDUL)}</h2><p>{_e(COPY_PENGANTAR)}</p>"
                      + _form_tagihan(token_untuk(AKSI_TAGIHAN)))
    if tampilan.nominal is not None and tampilan.status in _STATUS_BLOK:
        return _kartu(_isi_dengan_tagihan(tampilan, rekening, token_untuk))
    if tampilan.boleh_ulang:
        return _kartu(f"<h2>{_e(COPY_JUDUL_ULANG)}</h2><p>{_e(COPY_PENGANTAR_ULANG)}</p>"
                      + _form_ulang(token_untuk(AKSI_ULANG)))
    return ""
