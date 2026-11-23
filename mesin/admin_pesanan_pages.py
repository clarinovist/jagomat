"""Renderer murni halaman admin "Pesanan & transfer" (Fase C): daftar order tanpa form tindakan.

Tabel hanya menampilkan ringkasan dan satu tautan per baris ("Periksa bukti" ke detail verifikasi untuk transfer
yang menunggu, selain itu "Detail" ke `/admin/pesanan/order`). Tindakan berisiko (periksa status, catat refund)
ada di halaman Detail order (`admin_pesanan_detail_pages`), bukan di tabel: tidak ada kolom sandi per baris.

Tanpa I/O, tanpa JS baru, tanpa warna sendiri (kelas komponen admin yang ada). Data hanya proyeksi minimal dari
`pesanan_admin.daftar_tersaring`: tanpa kontak, nama anak, siswa_id, cek_id, merchant, atau payload.
Semua nilai dinamis di-escape; waktu ledger (UTC naif) ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple
from urllib.parse import urlencode

import admin_labels as L
import pesanan_dasar as d
from admin_daftar_pages import kartu_tabel
from admin_komponen import e
from pesanan_transfer_pages import rupiah

RUTE = "/admin/pesanan"
RUTE_PERIKSA = RUTE + "/periksa"
RUTE_REFUND = RUTE + "/refund"
RUTE_VERIFIKASI = RUTE + "/verifikasi"
RUTE_REKENING = RUTE + "/rekening"
RUTE_ORDER = RUTE + "/order"
RUTE_PENGATURAN_REKENING = "/admin/sakelar#rekening"
SARING_MENUNGGU = "menunggu"
JUDUL = "Pesanan & transfer"
SUBJUDUL = "Daftar order. Periksa bukti transfer atau buka detail order; tanpa kontak dan nama anak."
PER_HALAMAN = 25
AKSI_PERIKSA = "periksa"
AKSI_REFUND = "refund"
STATUS_PERIKSA = ("belum_bayar", "kedaluwarsa")
STATUS_REFUND = d.STATUS_BISA_REFUND  # satu sumber dengan penegakan server (`pesanan_refund_aturan`)
KELAS_BADGE = {"sudah_dibayar": " bien", "perlu_diperiksa": " perhatian", "menunggu_verifikasi": " perhatian"}
_KOLOM = ("Order", "Akun", "Nominal", "Dibayar / diunggah", "Status", "Aksi")

COPY_STATUS = {
    "belum_bayar": "Menunggu pembayaran",
    "sudah_dibayar": "Dibayar",
    "perlu_diperiksa": "Perlu diperiksa",
    "kedaluwarsa": "Kedaluwarsa",
    "direfund": "Direfund (dicatat)",
    "menunggu_verifikasi": "Menunggu verifikasi",
    "ditolak": "Ditolak (menunggu unggah ulang)",
}
# Chip saringan: (label, nilai `?status=`); nilai = kunci `pesanan_admin.KELOMPOK_STATUS`, None = semua.
COPY_SARING = (
    ("Menunggu verifikasi", SARING_MENUNGGU),
    ("Belum bayar", "belum_bayar"),
    ("Dibayar", "dibayar"),
    ("Ditolak / kedaluwarsa", "ditolak"),
    ("Semua", None),
)
KODE_SARING = frozenset(nilai for _label, nilai in COPY_SARING if nilai is not None)
KUNCI_SEMUA = "semua"
COPY_KOSONG_SARING = {
    SARING_MENUNGGU: "Tidak ada transfer yang menunggu verifikasi.",
    "belum_bayar": "Tidak ada pesanan yang menunggu pembayaran.",
    "dibayar": "Belum ada pesanan yang dibayar.",
    "ditolak": "Tidak ada pesanan yang ditolak atau kedaluwarsa.",
}
COPY_KOSONG_MENUNGGU = COPY_KOSONG_SARING[SARING_MENUNGGU]
COPY_PERIKSA_BUKTI = "Periksa bukti"
COPY_DUA_JALUR = "Dibayar lewat dua jalur — cek refund"
COPY_MENUNGGU_LAMA = "Menunggu > 72 jam"
COPY_DETAIL = "Detail"
# Alasan receipt penyedia (`alasan_kode`) dalam bahasa awam; kode tak dikenal jatuh ke "Lainnya".
COPY_ALASAN = {
    "ok": "Pembayaran sesuai",
    "nominal": "Nominal tidak sesuai",
    "merchant": "Penjual tidak sesuai",
    "mata_uang": "Mata uang tidak sesuai",
    "kanal": "Cara bayar tidak sesuai",
    "refund": "Ada pengembalian dana di penyedia",
    "lainnya": "Lainnya",
}
COPY_ALASAN_LAIN = COPY_ALASAN["lainnya"]
COPY_HASIL = {
    "periksa_ok": "Pemeriksaan selesai. Status pesanan sudah mengikuti jawaban penyedia pembayaran.",
    "periksa_dilewati": "Tidak ada yang perlu diperiksa untuk pesanan ini (sudah lunas, atau belum ada transaksi).",
    "periksa_gagal": "Penyedia pembayaran belum bisa dihubungi atau jawabannya tidak bisa dipakai. Tidak ada yang berubah; coba lagi nanti.",
    "gerbang_tertutup": "Pembayaran sedang ditutup, jadi pemeriksaan tidak dijalankan. Tidak ada yang berubah.",
    "refund_dicatat": "Catatan refund tersimpan. Ini hanya catatan; dana dikembalikan lewat jalur manual di luar aplikasi.",
    "refund_sudah_ada": "Catatan refund yang sama sudah tersimpan sebelumnya. Tidak ada yang berubah.",
    "verifikasi_setuju": "Transfer disetujui. Pesanan ini sekarang tercatat lunas.",
    "verifikasi_tolak": ("Bukti ditolak beserta alasannya. Guru dapat mengunggah ulang selama waktu "
                         "pembayaran masih terbuka."),
}
KODE_HASIL = frozenset(COPY_HASIL)
# Hasil yang boleh tampil di halaman Detail order (hasil aksi periksa/refund; keputusan verifikasi tidak).
KODE_HASIL_DETAIL = frozenset(k for k in COPY_HASIL if not k.startswith("verifikasi_"))
COPY_GERBANG_BUKA = "Pembayaran dibuka"
COPY_GERBANG_TUTUP = "Pembayaran ditutup (pemeriksaan ke penyedia tidak tersedia)"
COPY_REKENING_TERISI = "Rekening transfer terisi"
COPY_REKENING_KOSONG = "Rekening transfer belum diisi"
COPY_ATUR_LAYANAN = "Atur di Pengaturan layanan"
COPY_KOSONG = "Belum ada pesanan."
COPY_TIDAK_SIAP = "Data pesanan belum siap di server ini. Tidak ada yang diubah; periksa pemasangan skema pesanan."
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk memeriksa atau mencatat refund."

COPY_GALAT_FORM = "Form atau autentikasi ulang tidak sah. Buka ulang halaman tadi, lalu coba lagi."
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
    if gerbang_terbuka and status in STATUS_PERIKSA:
        aksi.append(AKSI_PERIKSA)
    if status in STATUS_REFUND:
        aksi.append(AKSI_REFUND)
    return tuple(aksi)


def _waktu(nilai: str) -> str:
    return e(L.tanggal(nilai + "Z"))


def _sel_nominal(ringkas: Mapping) -> str:
    return e(rupiah(ringkas["nominal"])) if ringkas.get("nominal") else "—"


def _sel_bukti(ringkas: Mapping) -> str:
    return _waktu(ringkas["diunggah"]) if ringkas.get("jumlah_bukti") else "—"


def _sel_order(item: Mapping) -> str:
    return "%s<br><span class=\"admin-meta\">%s</span>" % (L.referensi(item["order_id"]), _waktu(item["dibuat"]))


def _sel_status(item: Mapping) -> str:
    status = item["status"]
    badge = '<span class="admin-badge%s">%s</span>' % (KELAS_BADGE.get(status, ""), e(COPY_STATUS.get(status, status)))
    kode = item["alasan_kode"]
    if kode:
        badge += '<br><span class="admin-meta">%s</span>' % e(COPY_ALASAN.get(kode, COPY_ALASAN_LAIN))
    return badge + _penanda(item)


def _penanda(item: Mapping) -> str:
    """Penanda admin (dua jalur bayar, menunggu lama); item buatan tangan tanpa kunci ini = tanpa penanda."""
    teks = [t for kunci, t in (("dua_jalur", COPY_DUA_JALUR), ("menunggu_lama", COPY_MENUNGGU_LAMA)) if item.get(kunci)]
    return "".join('<br><span class="admin-badge perhatian">%s</span>' % e(t) for t in teks)


def _sel_aksi(item: Mapping) -> str:
    """Satu tautan per baris: periksa bukti (transfer menunggu) atau detail order."""
    if item["status"] == "menunggu_verifikasi":
        return '<a class="admin-tombol" href="%s?order=%s">%s</a>' % (
            RUTE_VERIFIKASI, e(item["order_id"]), e(COPY_PERIKSA_BUKTI))
    return '<a class="admin-tautan" href="%s?id=%s">%s</a>' % (RUTE_ORDER, e(item["order_id"]), e(COPY_DETAIL))


def _baris(item: Mapping, transfer: Mapping) -> str:
    ringkas = transfer.get(item["order_id"], {})
    return ("<tr>" + "".join("<td>%s</td>" % sel for sel in (
        _sel_order(item), e(item["akun"]), _sel_nominal(ringkas), _sel_bukti(ringkas),
        _sel_status(item), _sel_aksi(item))) + "</tr>")


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


def _chip(label: str, nilai: Optional[str], saring: Optional[str], hitungan: Mapping) -> str:
    jumlah = hitungan.get(KUNCI_SEMUA if nilai is None else nilai)
    cnt = "" if jumlah is None else '<span class="admin-cnt">%d</span>' % jumlah
    return '<a class="admin-chip"%s href="%s">%s%s</a>' % (
        ' aria-current="true"' if nilai == saring else "",
        RUTE if nilai is None else "%s?status=%s" % (RUTE, nilai), e(label), cnt)


def _chips(saring: Optional[str], hitungan: Mapping) -> str:
    return '<nav class="admin-chip-baris" aria-label="Saring status">%s</nav>' % "".join(
        _chip(label, nilai, saring, hitungan) for label, nilai in COPY_SARING)


def _strip_layanan(gerbang_terbuka: bool, rekening_terisi: Optional[bool]) -> str:
    """Satu baris ringkas: status pembayaran dibuka/ditutup, rekening transfer, dan tautan ke Pengaturan layanan."""
    bagian = [COPY_GERBANG_BUKA if gerbang_terbuka else COPY_GERBANG_TUTUP]
    if rekening_terisi is not None:
        bagian.append(COPY_REKENING_TERISI if rekening_terisi else COPY_REKENING_KOSONG)
    return '<p class="admin-meta">%s · <a class="admin-tautan" href="%s">%s</a></p>' % (
        e(" · ".join(bagian)), RUTE_PENGATURAN_REKENING, e(COPY_ATUR_LAYANAN))


def umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def halaman(daftar: Mapping, *, halaman: int, gerbang_terbuka: bool, hasil: Optional[str],
            transfer: Optional[Mapping] = None, saring: Optional[str] = None,
            hitungan: Optional[Mapping] = None, rekening_terisi: Optional[bool] = None) -> str:
    """Isi section pesanan: tanpa form (tindakan ada di Detail order).

    `transfer` = {order_id: {nominal, jumlah_bukti, diunggah}} dari `pesanan_admin_transfer.ringkasan`;
    `saring` = kunci `KODE_SARING` atau None (semua); `hitungan` = {kelompok|semua: n} atau None (tanpa angka);
    `rekening_terisi` = True/False/None (None = tidak ditampilkan).
    """
    ringkas = transfer or {}
    kosong = COPY_KOSONG_SARING.get(saring, COPY_KOSONG)
    baris = "".join(_baris(i, ringkas) for i in daftar["items"]) or (
        '<tr><td colspan="%d" class="admin-kosong">%s</td></tr>' % (len(_KOLOM), e(kosong)))
    kepala = tuple('<th scope="col">%s</th>' % x for x in _KOLOM)
    return (umpan_balik(hasil) + _strip_layanan(gerbang_terbuka, rekening_terisi) + _chips(saring, hitungan or {})
            + kartu_tabel("Pesanan", kepala, baris, _pager(halaman, daftar["total"], saring),
                          keterangan="%d tercatat · Halaman %d" % (daftar["total"], halaman)))


def halaman_tidak_siap() -> str:
    """Kartu jujur bila skema pesanan belum dipasang atau DB belum bisa dibaca."""
    return '<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>' % e(COPY_TIDAK_SIAP)
