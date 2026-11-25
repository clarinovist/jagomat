"""Renderer murni halaman admin "Semua pembayaran": satu daftar read-only untuk tiga jalur pembayaran.

Tanpa I/O, tanpa form, tanpa JS. Hanya order, nominal, waktu, status, dan tautan ke halaman ACC; tanpa nama anak,
kontak, atau akun. Semua nilai dinamis di-escape; waktu ledger (UTC naif) ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

import admin_labels as L
import admin_pembayaran_semua as S
from admin_daftar_pages import kartu_tabel
from admin_komponen import e
from pesanan_transfer_pages import rupiah

RUTE = "/admin/pembayaran"
JUDUL = "Semua pembayaran"
SUBJUDUL = "Peta Kemampuan, Latihan Harian, dan Paket Belajar dalam satu daftar. Baca-saja; ACC lewat halaman masing-masing."
_KOLOM = ("Jenis", "Order", "Nominal", "Dibuat", "Status", "Aksi")

COPY_JENIS = {S.JENIS_PETA: "Peta Kemampuan", S.JENIS_HARIAN: "Latihan Harian", S.JENIS_KELAS: "Paket Belajar"}
COPY_STATUS = {
    S.S_BELUM_BAYAR: "Menunggu pembayaran",
    S.S_MENUNGGU: "Menunggu verifikasi",
    S.S_LUNAS: "Dibayar",
    S.S_DITOLAK: "Ditolak (menunggu unggah ulang)",
    S.S_KEDALUWARSA: "Kedaluwarsa",
    S.S_PERLU_DIPERIKSA: "Perlu diperiksa",
    S.S_DIREFUND: "Direfund (dicatat)",
}
KELAS_BADGE = {S.S_LUNAS: " bien", S.S_PERLU_DIPERIKSA: " perhatian", S.S_MENUNGGU: " perhatian"}
COPY_SARING = (
    ("Menunggu verifikasi", "menunggu"),
    ("Belum bayar", "belum_bayar"),
    ("Dibayar", "dibayar"),
    ("Ditolak / kedaluwarsa", "ditolak"),
    ("Semua", None),
)
KODE_SARING = frozenset(nilai for _label, nilai in COPY_SARING if nilai is not None)
COPY_KOSONG = {
    "menunggu": "Tidak ada transfer yang menunggu verifikasi.",
    "belum_bayar": "Tidak ada tagihan yang menunggu pembayaran.",
    "dibayar": "Belum ada pembayaran yang lunas.",
    "ditolak": "Tidak ada order yang ditolak atau kedaluwarsa.",
}
COPY_KOSONG_SEMUA = "Belum ada order pembayaran."
COPY_PERIKSA_BUKTI = "Periksa bukti"
COPY_DETAIL = "Detail"
COPY_GAGAL = "Belum bisa membaca: %s. Daftar di bawah belum lengkap; buka halaman jenis itu langsung."
COPY_TIDAK_SIAP = "Data pembayaran belum bisa dibaca di server ini. Tidak ada yang diubah."
COPY_CATATAN = ("Menampilkan %d order terbaru per jenis. Tagihan tanpa bukti ikut tampil; bukti yang menunggu "
                "diputuskan di halaman jenisnya.")


def _chip(label: str, nilai: Optional[str], saring: Optional[str], hitungan: Mapping) -> str:
    jumlah = hitungan.get("semua" if nilai is None else nilai)
    cnt = "" if jumlah is None else '<span class="admin-cnt">%d</span>' % jumlah
    return '<a class="admin-chip"%s href="%s">%s%s</a>' % (
        ' aria-current="true"' if nilai == saring else "",
        RUTE if nilai is None else "%s?status=%s" % (RUTE, nilai), e(label), cnt)


def _chips(saring: Optional[str], hitungan: Mapping) -> str:
    return '<nav class="admin-chip-baris" aria-label="Saring status">%s</nav>' % "".join(
        _chip(label, nilai, saring, hitungan) for label, nilai in COPY_SARING)


def _baris(item: S.BarisBayar) -> str:
    status = '<span class="admin-badge%s">%s</span>' % (
        KELAS_BADGE.get(item.status, ""), e(COPY_STATUS.get(item.status, item.status)))
    nominal = rupiah(item.nominal) if item.nominal else "—"
    cta = COPY_PERIKSA_BUKTI if item.status == S.S_MENUNGGU else COPY_DETAIL
    sel = (e(COPY_JENIS.get(item.jenis, item.jenis)), '<code class="admin-ref">%s</code>' % e(item.order_id),
           e(nominal), e(L.tanggal(item.dibuat + "Z")), status,
           '<a class="admin-tautan" href="%s">%s</a>' % (e(item.jalur), e(cta)))
    return "<tr>" + "".join("<td>%s</td>" % s for s in sel) + "</tr>"


def _peringatan_gagal(gagal: Sequence[str]) -> str:
    if not gagal:
        return ""
    jenis = ", ".join(COPY_JENIS.get(j, j) for j in gagal)
    return '<p class="admin-kartu admin-catatan" role="alert">%s</p>' % e(COPY_GAGAL % jenis)


def halaman(baris: Sequence[S.BarisBayar], *, saring: Optional[str], hitungan: Mapping,
            gagal: Sequence[str] = ()) -> str:
    """Isi section: peringatan jenis tak terbaca, chip saringan, tabel. `baris` sudah disaring pemanggil."""
    kosong = COPY_KOSONG.get(saring, COPY_KOSONG_SEMUA)
    isi = "".join(_baris(b) for b in baris) or (
        '<tr><td colspan="%d" class="admin-kosong">%s</td></tr>' % (len(_KOLOM), e(kosong)))
    kepala = tuple('<th scope="col">%s</th>' % x for x in _KOLOM)
    return (_peringatan_gagal(gagal) + _chips(saring, hitungan)
            + kartu_tabel("Pembayaran", kepala, isi, "", keterangan="%d tampil" % len(baris),
                          catatan='<p class="admin-meta">%s</p>' % e(COPY_CATATAN % S.BATAS_PER_JENIS)))


def halaman_tidak_siap() -> str:
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>'
            % e(COPY_TIDAK_SIAP))
