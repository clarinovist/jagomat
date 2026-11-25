"""Renderer halaman admin Harga (murni: tanpa I/O, tanpa JS). Semua nilai dinamis di-escape.

Form ubah hanya untuk Private dan Mini Class; Peta dan Latihan Harian hanya dibaca. Field form: csrf, tinjauan,
reauth (sandi), kode (harus sama dengan tinjauan), dan harga_baru (teks rupiah). Batas angka dari harga_aturan.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence, Tuple

import admin_harga_baca as baca
import harga
import harga_aturan as a
from admin_komponen import e
from pesanan_transfer_pages import rupiah

RUTE = "/admin/harga"
JUDUL = "Harga Private dan Mini Class"
SUBJUDUL = "Harga aktif, riwayat perubahan, dan Peta serta Latihan Harian yang hanya dibaca."
AKSI_UBAH = "ubah_harga"
FIELD_KODE = "kode"
FIELD_HARGA = "harga_baru"
FIELD_KONFIRMASI = "konfirmasi_selisih"
NILAI_KONFIRMASI = "ya"
HASIL_TERSIMPAN = "tersimpan"
COPY_HASIL = {HASIL_TERSIMPAN: "Harga tersimpan. Harga baru berlaku untuk tagihan BARU."}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_TAGIHAN_BARU = (
    "Harga baru berlaku untuk tagihan BARU. Tagihan yang sudah dibuat tetap pada harga yang tersimpan."
)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah harga."
COPY_BELUM_DIPASANG = "Pengaturan harga belum dipasang di server ini. Tidak ada yang diubah."
COPY_TIDAK_SIAP = (
    "Pengaturan harga belum bisa dibaca di server ini. Tidak ada yang diubah; periksa pemasangan skema harga."
)
COPY_KONFLIK = (
    "Harga sudah diubah sejak halaman ini dibuka. Buka ulang halaman Harga, periksa nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_ISIAN = "Permintaan ubah harga tidak sah. Tidak ada yang diubah."
COPY_LAYANAN = "Layanan harga belum bisa menyelesaikan tindakan ini. Tidak ada yang diubah; coba lagi nanti."
COPY_FORMAT = "Harga harus angka bulat tanpa pemisah ribuan, spasi, tanda, atau desimal. Tidak ada yang diubah."
COPY_SELISIH_BESAR = (
    "Harga baru lebih dari 2 kali lipat atau kurang dari separuh harga aktif. Periksa angkanya (salah ketik nol?). "
    "Bila sudah benar, centang konfirmasi di bawah kolom harga lalu simpan lagi. Tidak ada yang diubah."
)
COPY_KONFIRMASI = "Saya yakin: harga baru memang lebih dari 2 kali lipat atau kurang dari separuh harga aktif."
COPY_HARGA_SAMA = "Harga baru sama dengan harga aktif. Tidak ada yang diubah."
COPY_PETA = "Peta Kemampuan belum bisa diatur; harga Peta hanya dibaca."
COPY_LATIHAN = "Harga Latihan Harian diatur di katalog Latihan Harian, bukan di halaman ini (hanya dibaca)."

Token = Tuple[str, str]


def pola_isian_harga() -> str:
    """Pola HTML dan batas digit dari harga_aturan (dibaca saat dipanggil)."""
    return "[0-9]{1,%d}" % len(str(a.HARGA_MAKS))


def _rentang_teks() -> str:
    return "Rentang harga %s sampai %s, kelipatan %s. Harga dalam rupiah bulat." % (
        rupiah(a.HARGA_MIN), rupiah(a.HARGA_MAKS), rupiah(a.KELIPATAN))


def _hidden(nama: str, nilai: str) -> str:
    return '<input type="hidden" name="%s" value="%s">' % (nama, e(nilai))


def _form(produk: baca.BarisProduk, token: Token) -> str:
    csrf, tinjauan = token
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s%s%s'
        '<label>Harga baru per bulan (rupiah, tanpa titik)<input type="text" name="%s" inputmode="numeric" '
        'pattern="%s" required autocomplete="off"></label>'
        '<label class="admin-meta"><input type="checkbox" name="%s" value="%s"> %s</label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan harga</button></form>'
        % (RUTE, _hidden("csrf", csrf), _hidden("tinjauan", tinjauan), _hidden(FIELD_KODE, produk.kode),
           FIELD_HARGA, e(pola_isian_harga()), FIELD_KONFIRMASI, NILAI_KONFIRMASI, e(COPY_KONFIRMASI)))


def _sumber(produk: baca.BarisProduk) -> str:
    if not produk.diubah:
        return "nilai awal"
    return "diubah admin pada %s" % e(produk.diubah)


def _kartu_produk(produk: baca.BarisProduk, token: Optional[Token]) -> str:
    setelah = ""
    if produk.setelah_deposit is not None:
        setelah = '<p class="admin-meta">Tagihan setelah potongan deposit Peta (info): %s</p>' % (
            rupiah(produk.setelah_deposit))
    form = _form(produk, token) if token else '<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI)
    return (
        '<section class="admin-kartu admin-kartu-fitur" id="h-%s"><div class="admin-fitur-kepala">'
        '<h3>%s</h3></div><p>Harga aktif: <strong>%s</strong> per bulan. <span class="admin-meta">%s</span></p>'
        '%s%s</section>'
        % (e(produk.kode), e(produk.label), rupiah(produk.rupiah), _sumber(produk), setelah, form))


def _kartu_peta(produk: baca.BarisProduk) -> str:
    return (
        '<section class="admin-kartu admin-kartu-fitur" id="h-%s"><div class="admin-fitur-kepala">'
        '<h3>%s</h3><span class="admin-badge">Belum bisa diatur</span></div>'
        '<p>Harga: <strong>%s</strong> (hanya dibaca)</p><p class="admin-meta">%s</p></section>'
        % (e(produk.kode), e(produk.label), rupiah(produk.rupiah), e(COPY_PETA)))


def _kartu_harian(harian: Sequence[baca.BarisHarian]) -> str:
    baris = "".join("<li>%s: <strong>%s</strong></li>" % (e(b.label), rupiah(b.rupiah)) for b in harian)
    return ('<section class="admin-kartu" id="latihan-harian"><h3>Latihan Harian</h3>'
            '<p class="admin-meta">%s</p><ul>%s</ul></section>' % (e(COPY_LATIHAN), baris))


def _baris_riwayat(riwayat: harga.RiwayatHarga) -> str:
    lama = "nilai awal" if riwayat.lama is None else rupiah(riwayat.lama)
    return "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(riwayat.waktu), e(baca.LABEL_PRODUK.get(riwayat.kode, riwayat.kode)), lama,
        rupiah(riwayat.baru), e(riwayat.oleh))


def _riwayat(riwayat: Sequence[harga.RiwayatHarga]) -> str:
    if not riwayat:
        return ('<section class="admin-kartu" id="riwayat"><h3>Riwayat perubahan</h3>'
                '<p class="admin-meta">Belum ada perubahan harga oleh admin.</p></section>')
    baris = "".join(_baris_riwayat(r) for r in riwayat)
    return ('<section class="admin-kartu" id="riwayat"><h3>Riwayat perubahan</h3>'
            '<p class="admin-meta">Terbaru dulu, paling banyak %d baris.</p><div class="admin-tabel-wrap">'
            '<table class="admin-tabel"><thead><tr><th>Waktu (UTC)</th><th>Produk</th><th>Lama</th>'
            '<th>Baru</th><th>Oleh</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (harga.BATAS_RIWAYAT_BAWAAN, baris))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in KODE_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _catatan(tampilan: baca.Tampilan, tokens: Optional[Mapping[str, Token]]) -> str:
    if not tampilan.terpasang:
        return '<p class="admin-kartu admin-catatan" role="note">%s</p>' % e(COPY_BELUM_DIPASANG)
    if tokens is None:
        return '<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI)
    return '<p class="admin-meta">%s</p><p class="admin-meta">%s</p>' % (e(COPY_TAGIHAN_BARU), e(_rentang_teks()))


def _kartu(produk: baca.BarisProduk, tokens: Optional[Mapping[str, Token]]) -> str:
    if not produk.bisa_diubah:
        return _kartu_peta(produk)
    return _kartu_produk(produk, tokens.get(produk.kode) if tokens else None)


def halaman(tampilan: baca.Tampilan, tokens: Optional[Mapping[str, Token]], hasil: Optional[str]) -> str:
    """Isi section halaman Harga (tanpa kerangka admin). `tokens` None = baca-saja tanpa form."""
    kartu = "".join(_kartu(p, tokens if tampilan.terpasang else None) for p in tampilan.produk)
    return "".join((_umpan_balik(hasil), _catatan(tampilan, tokens), kartu,
                    _kartu_harian(tampilan.harian), _riwayat(tampilan.riwayat)))


def _galat_kartu(judul: str, pesan: str) -> str:
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>%s</h2><p>%s</p></section>'
            % (e(judul), e(pesan)))


def galat_isian(pesan: str) -> str:
    return _galat_kartu("Permintaan tidak dapat diproses", pesan)


def galat_belum_dipasang() -> str:
    return _galat_kartu("Harga belum dipasang", COPY_BELUM_DIPASANG)


def galat_skema_rusak() -> str:
    return _galat_kartu("Belum siap", COPY_TIDAK_SIAP)


def galat_layanan() -> str:
    return _galat_kartu("Belum siap", COPY_LAYANAN)


def tautan_pengaturan() -> str:
    return ('<p class="admin-meta">Harga Private dan Mini Class: <a class="admin-tautan-teks" href="%s">'
            'buka halaman harga</a>.</p>' % RUTE)

