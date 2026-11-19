"""Renderer murni halaman admin "Pesanan Paket Coba" (Fase 3c-4): daftar, aksi periksa/refund.

Jalur transfer rekening: kolom nominal persis dan bukti, tab "Menunggu verifikasi", dan tautan ke detail
verifikasi (`admin_verifikasi_pages`); ringkasan transfer disuntik pemanggil (`pesanan_admin_transfer`).

Tanpa I/O, tanpa JS baru (konfirmasi lewat `data-konfirmasi` yang sudah dihash CSP oleh bingkai admin),
tanpa warna sendiri (kelas komponen admin yang ada). Data hanya proyeksi minimal dari
`pesanan_admin.daftar_admin`: tanpa kontak, nama anak, siswa_id, cek_id, merchant, atau payload.
Semua nilai dinamis di-escape; waktu ledger (UTC naif) ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple
from urllib.parse import urlencode

import admin_labels as L
from admin_daftar_pages import kartu_tabel
from admin_komponen import e
from pesanan_transfer_pages import rupiah
from schema_pesanan import CATATAN_REFUND

RUTE = "/admin/pesanan"
RUTE_PERIKSA = RUTE + "/periksa"
RUTE_REFUND = RUTE + "/refund"
RUTE_VERIFIKASI = RUTE + "/verifikasi"
RUTE_REKENING = RUTE + "/rekening"
SARING_MENUNGGU = "menunggu"
JUDUL = "Pesanan Paket Coba"
SUBJUDUL = "Daftar order, periksa status ke penyedia pembayaran, dan catatan refund manual. Tanpa kontak dan nama anak."
PER_HALAMAN = 25
AKSI_PERIKSA = "periksa"
AKSI_REFUND = "refund"
_STATUS_PERIKSA = ("belum_bayar", "kedaluwarsa")
_STATUS_REFUND = ("sudah_dibayar", "perlu_diperiksa")
KELAS_BADGE = {"sudah_dibayar": " bien", "perlu_diperiksa": " perhatian", "menunggu_verifikasi": " perhatian"}
_KOLOM = ("Order", "Akun", "Dibuat", "Kedaluwarsa", "Nominal transfer", "Bukti", "Status", "Alasan", "Tindakan")

COPY_STATUS = {
    "belum_bayar": "Menunggu pembayaran",
    "sudah_dibayar": "Dibayar",
    "perlu_diperiksa": "Perlu diperiksa",
    "kedaluwarsa": "Kedaluwarsa",
    "direfund": "Direfund (dicatat)",
    "menunggu_verifikasi": "Menunggu verifikasi",
    "ditolak": "Ditolak (menunggu unggah ulang)",
}
COPY_TAB = (("Semua", None), ("Menunggu verifikasi", SARING_MENUNGGU))
COPY_KOSONG_MENUNGGU = "Tidak ada transfer yang menunggu verifikasi."
COPY_PERIKSA_BUKTI = "Periksa bukti"
COPY_LIHAT_BUKTI = "Lihat bukti"
COPY_TAUTAN_REKENING = "Pengaturan rekening transfer"
COPY_CATATAN = {
    "permintaan_pembeli": "Permintaan pembeli",
    "kesalahan_sistem": "Kesalahan sistem",
    "kebijakan": "Sesuai kebijakan",
    "lainnya": "Lainnya",
}
COPY_HASIL = {
    "periksa_ok": "Pemeriksaan selesai. Status pesanan sudah mengikuti jawaban penyedia pembayaran.",
    "periksa_dilewati": "Tidak ada yang perlu diperiksa untuk pesanan ini (sudah lunas, atau belum ada transaksi).",
    "periksa_gagal": "Penyedia pembayaran belum bisa dihubungi atau jawabannya tidak bisa dipakai. Tidak ada yang berubah; coba lagi nanti.",
    "gerbang_tertutup": "Gerbang pembayaran sedang tertutup, jadi pemeriksaan tidak dijalankan. Tidak ada yang berubah.",
    "refund_dicatat": "Catatan refund tersimpan. Ini hanya catatan; dana dikembalikan lewat jalur manual di luar aplikasi.",
    "refund_sudah_ada": "Catatan refund yang sama sudah tersimpan sebelumnya. Tidak ada yang berubah.",
    "verifikasi_setuju": "Transfer disetujui. Pesanan ini sekarang tercatat lunas.",
    "verifikasi_tolak": ("Bukti ditolak beserta alasannya. Guru dapat mengunggah ulang selama waktu "
                         "pembayaran masih terbuka."),
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_GERBANG_BUKA = "Gerbang pembayaran: terbuka. Tombol Periksa tersedia untuk order yang belum lunas."
COPY_GERBANG_TUTUP = (
    "Gerbang pembayaran tertutup. Daftar tetap bisa dibaca dan refund tetap bisa dicatat, "
    "tetapi pemeriksaan ke penyedia pembayaran tidak tersedia."
)
COPY_KOSONG = "Belum ada pesanan."
COPY_KONFIRMASI_REFUND = (
    "Catat refund untuk pesanan ini? Aplikasi tidak mengembalikan dana; catatan ini ber-audit "
    "dan tidak dapat dibatalkan."
)
COPY_CATATAN_KAKI = (
    "Refund hanya dicatat di sini: tidak ada panggilan refund ke penyedia pembayaran. "
    "Satu order hanya bisa punya satu catatan refund."
)
COPY_TIDAK_SIAP = "Data pesanan belum siap di server ini. Tidak ada yang diubah; periksa pemasangan skema pesanan."
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk memeriksa atau mencatat refund."

COPY_GALAT_FORM = "Form atau autentikasi ulang tidak sah. Buka ulang daftar pesanan, lalu coba lagi."
COPY_GALAT_ISIAN = "Isian pesanan tidak sah. Tidak ada yang diubah."
COPY_GALAT_KONFLIK = (
    "Pesanan ini belum punya pembayaran tercatat, atau sudah punya catatan refund yang berbeda. "
    "Tidak ada yang diubah."
)
COPY_GALAT_LAYANAN = "Layanan pesanan belum bisa menyelesaikan tindakan ini. Tidak ada yang diubah; coba lagi nanti."


def aksi_tersedia(item: Mapping, gerbang_terbuka: bool) -> Tuple[str, ...]:
    """Aksi yang boleh ditampilkan untuk satu order (server tetap menegakkan sendiri)."""
    status = item["status"]
    aksi = []
    if gerbang_terbuka and status in _STATUS_PERIKSA:
        aksi.append(AKSI_PERIKSA)
    if status in _STATUS_REFUND:
        aksi.append(AKSI_REFUND)
    return tuple(aksi)


def _waktu(nilai: str) -> str:
    return e(L.tanggal(nilai + "Z"))


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


_SANDI = ('<label>Sandi admin saat ini<input type="password" name="reauth" required '
          'autocomplete="current-password"></label>')


def _form_periksa(token: Tuple[str, str]) -> str:
    return ('<form method="post" action="%s">%s%s<button class="admin-tombol admin-tombol-sekunder" '
            'type="submit">Periksa status</button></form>' % (RUTE_PERIKSA, _hidden(*token), _SANDI))


def _form_refund(token: Tuple[str, str]) -> str:
    opsi = "".join('<option value="%s">%s</option>' % (e(k), e(COPY_CATATAN[k])) for k in CATATAN_REFUND)
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Alasan<select name="catatan_kode" required>%s</select></label>%s'
            '<button class="admin-tombol admin-bahaya" type="submit">Catat refund</button></form>'
            % (RUTE_REFUND, e(COPY_KONFIRMASI_REFUND), _hidden(*token), opsi, _SANDI))


def _tautan_bukti(item: Mapping, transfer: Mapping) -> str:
    if not transfer.get(item["order_id"], {}).get("jumlah_bukti"):
        return ""
    label = COPY_PERIKSA_BUKTI if item["status"] == "menunggu_verifikasi" else COPY_LIHAT_BUKTI
    return '<a class="admin-tautan" href="%s?order=%s">%s</a>' % (RUTE_VERIFIKASI, e(item["order_id"]), e(label))


def _tindakan(item: Mapping, gerbang_terbuka: bool, forms: Mapping, transfer: Mapping) -> str:
    token = forms.get(item["order_id"], {})
    isi = _tautan_bukti(item, transfer)
    for aksi in aksi_tersedia(item, gerbang_terbuka):
        if aksi in token:
            isi += (_form_periksa if aksi == AKSI_PERIKSA else _form_refund)(token[aksi])
    return isi or "—"


def _sel_nominal(ringkas: Mapping) -> str:
    return e(rupiah(ringkas["nominal"])) if ringkas.get("nominal") else "—"


def _sel_bukti(ringkas: Mapping) -> str:
    jumlah = ringkas.get("jumlah_bukti", 0)
    return "%d · %s" % (jumlah, _waktu(ringkas["diunggah"])) if jumlah else "—"


def _baris(item: Mapping, gerbang_terbuka: bool, forms: Mapping, transfer: Mapping) -> str:
    status = item["status"]
    ringkas = transfer.get(item["order_id"], {})
    badge = '<span class="admin-badge%s">%s</span>' % (KELAS_BADGE.get(status, ""), e(COPY_STATUS.get(status, status)))
    return ("<tr>" + "".join("<td>%s</td>" % sel for sel in (
        L.referensi(item["order_id"]), e(item["akun"]), _waktu(item["dibuat"]), _waktu(item["kedaluwarsa"]),
        _sel_nominal(ringkas), _sel_bukti(ringkas), badge, e(item["alasan_kode"] or "—"),
        _tindakan(item, gerbang_terbuka, forms, transfer))) + "</tr>")


def _alamat(halaman: int, saring: Optional[str]) -> str:
    return "%s?%s" % (RUTE, urlencode({k: v for k, v in (("status", saring), ("halaman", halaman)) if v}))


def _pager(halaman: int, total: int, saring: Optional[str]) -> str:
    jumlah = max(1, -(-total // PER_HALAMAN))
    kontrol = ""
    for nomor, label in ((halaman - 1, "Sebelumnya"), (halaman + 1, "Berikutnya")):
        if 1 <= nomor <= jumlah:
            kontrol += '<a class="admin-tautan" href="%s">%s</a>' % (e(_alamat(nomor, saring)), label)
    return ('<div class="admin-pager"><span>Halaman %d dari %d · %d order</span>'
            '<div class="admin-aksi-baca">%s</div></div>' % (halaman, jumlah, total, kontrol))


def _tautan_rekening() -> str:
    return '<p class="admin-meta"><a class="admin-tautan" href="%s">%s</a></p>' % (
        RUTE_REKENING, e(COPY_TAUTAN_REKENING))


def _tab(saring: Optional[str]) -> str:
    tautan = "".join(
        '<a class="admin-tautan" href="%s"%s>%s</a>' % (
            RUTE if nilai is None else "%s?status=%s" % (RUTE, nilai),
            ' aria-current="page"' if nilai == saring else "", e(label))
        for label, nilai in COPY_TAB)
    return '<nav class="admin-aksi-baca" aria-label="Saring status">%s</nav>' % tautan


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _catatan_gerbang(gerbang_terbuka: bool) -> str:
    return '<p class="admin-meta">%s</p>' % e(COPY_GERBANG_BUKA if gerbang_terbuka else COPY_GERBANG_TUTUP)


def halaman(daftar: Mapping, *, halaman: int, gerbang_terbuka: bool, forms: Mapping,
            hasil: Optional[str], baca_saja: bool = False, transfer: Optional[Mapping] = None,
            saring: Optional[str] = None) -> str:
    """Isi section pesanan. `forms` = {order_id: {aksi: (csrf, tinjauan)}}; kosong = tanpa tombol.

    `transfer` = {order_id: {nominal, jumlah_bukti, diunggah}} dari `pesanan_admin_transfer.ringkasan`;
    `saring` = `SARING_MENUNGGU` untuk tab verifikasi atau None.
    """
    ringkas = transfer or {}
    kosong = COPY_KOSONG_MENUNGGU if saring == SARING_MENUNGGU else COPY_KOSONG
    baris = "".join(_baris(i, gerbang_terbuka, forms, ringkas) for i in daftar["items"]) or (
        '<tr><td colspan="%d" class="admin-kosong">%s</td></tr>' % (len(_KOLOM), e(kosong)))
    kepala = tuple('<th scope="col">%s</th>' % x for x in _KOLOM)
    sesi = '<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI) if baca_saja else ""
    return (_umpan_balik(hasil) + _catatan_gerbang(gerbang_terbuka) + sesi + _tautan_rekening() + _tab(saring)
            + kartu_tabel("Pesanan", kepala, baris, _pager(halaman, daftar["total"], saring),
                          keterangan="%d tercatat · Halaman %d" % (daftar["total"], halaman))
            + '<p class="admin-meta">%s</p>' % e(COPY_CATATAN_KAKI))


def halaman_tidak_siap() -> str:
    """Kartu jujur bila skema pesanan belum dipasang atau DB belum bisa dibaca."""
    return '<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>' % e(COPY_TIDAK_SIAP)
