"""Renderer murni halaman admin Paket Belajar: antrean bukti menunggu dan detail verifikasi (tanpa I/O).

Mengikuti `harian_langganan_admin_pages`: mengembalikan fragmen HTML (str) yang dibungkus `admin_http._halaman_admin`
oleh pemanggil. Tanpa id anak di antrean/detail, nama anak, kontak, nama berkas, atau sha256; bukti hanya referensi (`BuktiView`,
id = bilangan ledger `kelas_bukti`, sama dengan `kelas_putusan.bukti_meta`).
Nominal disorot persis (tiga digit terakhir = kode unik). Form Setujui (tanpa alasan) dan Tolak (alasan wajib) hanya
untuk status menunggu dan sesi berkuki; token tinjauan terikat ke order dan bukti yang dilihat dibuat pemanggil
(`forms = {'setujui': (csrf, tinjauan), 'tolak': (csrf, tinjauan)}`). Semua nilai dinamis di-escape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from admin_komponen import e
import admin_verifikasi_pages as vp
import paket_belajar_katalog as k
from pesanan_transfer_pages import rupiah
from schema_transfer import BATAS_ALASAN

RUTE = "/admin/kelas"
RUTE_VERIFIKASI = RUTE + "/verifikasi"
RUTE_BUKTI = RUTE + "/bukti"
RUTE_SETUJUI = RUTE + "/setujui"
RUTE_TOLAK = RUTE + "/tolak"
RUTE_KELUARGA = RUTE + "/keluarga"
SECTION = "kelas_belajar"
JUDUL = "Paket Belajar 1 Bulan"
SUBJUDUL = "Periksa bukti transfer paket Private/Mini Class terhadap nominal persis, lalu setujui atau tolak."
AKSI_SETUJUI = "setujui_kelas"
AKSI_TOLAK = "tolak_kelas"
AKSI_KELUARGA = "tautkan_keluarga_kelas"
COPY_ANTREAN_KOSONG = "Tidak ada bukti paket belajar yang menunggu verifikasi."
COPY_KONFIRMASI_SETUJUI = "Setujui transfer ini? Paket langsung aktif dan keputusan tidak dapat dibatalkan."
COPY_KONFIRMASI_TOLAK = ("Tolak bukti ini? Orang tua akan melihat bahwa bukti ditolak dan dapat mengunggah ulang "
                         "selama waktu pembayaran terbuka.")
COPY_CATATAN_NOMINAL = ("Cocokkan nominal di mutasi rekening dengan angka di atas sampai tiga digit terakhir. Hanya "
                        "bukti yang Anda lihat di halaman ini yang akan diputuskan; bila ada bukti baru, buka ulang.")
COPY_GALAT_KONFLIK = ("Bukti ini tidak sedang menunggu verifikasi, sudah diputuskan, atau ada bukti baru sejak Anda "
                      "membuka halaman verifikasi. Buka ulang halaman verifikasi; tidak ada yang diubah.")
COPY_GALAT_ALASAN = ("Alasan penolakan wajib diisi (1 sampai %d karakter, tanpa karakter kontrol). "
                     "Tidak ada yang diubah." % BATAS_ALASAN)
COPY_JUDUL_KELUARGA ="Tautkan keluarga (diskon anak kedua)"
COPY_CATATAN_KELUARGA = ("Tautkan dua anak yang satu keluarga. Anak ke-2 dan seterusnya tanpa deposit Peta sendiri "
                         "mendapat diskon pada paket belajar. Pembeli tidak dapat memilih ini sendiri.")
COPY_KONFIRMASI_KELUARGA = "Tautkan kedua anak sebagai satu keluarga? Tautan tidak dapat dilepas dari halaman ini."
COPY_STATUS = {k.STATUS_AKTIF: "Disetujui", k.STATUS_MENUNGGU: "Menunggu verifikasi",
               k.STATUS_DITOLAK: "Ditolak (menunggu unggah ulang)", k.STATUS_KEDALUWARSA: "Kedaluwarsa",
               k.STATUS_BELUM_BAYAR: "Menunggu pembayaran"}
MAKS_ANGKA_ID_BUKTI = 18
_ID_BUKTI = re.compile(r"[0-9]{1,%d}" % MAKS_ANGKA_ID_BUKTI)
_LABEL_MIME = {"image/jpeg": "JPEG", "image/png": "PNG", "application/pdf": "PDF"}

Token = Tuple[str, str]


@dataclass(frozen=True)
class BuktiView:
    """Referensi satu bukti: id ledger (bilangan bulat dalam teks), waktu UTC naif, ukuran byte, mime.

    Tanpa isi berkas dan tanpa nama berkas tersimpan.
    """
    id: str
    waktu: str
    ukuran: int
    mime: str


def _banner(pesan: str) -> str:
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(pesan) if pesan else ""


def _nama_paket(kode: str) -> str:
    try:
        return k.ambil(kode).nama
    except ValueError:
        return kode


def _baris_antrean(item: k.ItemAntrean) -> str:
    tautan = '<a class="admin-tautan" href="%s?order=%s">Periksa bukti</a>' % (RUTE_VERIFIKASI, e(item.order_id))
    sel = (e(_nama_paket(item.kode_paket)), vp.nominal_sorot(item.total), vp._waktu(item.bukti_terakhir), tautan)
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % s for s in sel)


def halaman_antrean(daftar: Sequence[k.ItemAntrean], pesan: str = "") -> str:
    """Daftar bukti menunggu verifikasi (urutan dari pemanggil)."""
    baris = "".join(_baris_antrean(i) for i in daftar)
    return _banner(pesan) + vp._tabel("Menunggu verifikasi", ("Paket", "Nominal", "Bukti terakhir", "Aksi"), baris,
                                      COPY_ANTREAN_KOSONG)


def _form_setujui(token: Token) -> str:
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s%s'
            '<button class="admin-tombol" type="submit">Setujui transfer</button></form>'
            % (RUTE_SETUJUI, e(COPY_KONFIRMASI_SETUJUI), vp._hidden(*token), vp._SANDI))


def _form_tolak(token: Token) -> str:
    return ('<details class="admin-form-tolak"><summary>%s</summary>'
            '<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Alasan penolakan<input type="text" name="alasan" required maxlength="%d" autocomplete="off">'
            '</label>%s<button class="admin-tombol admin-bahaya" type="submit">Tolak bukti</button></form></details>'
            % (e(vp.COPY_RINGKAS_TOLAK), RUTE_TOLAK, e(COPY_KONFIRMASI_TOLAK), vp._hidden(*token), BATAS_ALASAN,
               vp._SANDI))


def _pratinjau(bukti: BuktiView) -> str:
    if not _ID_BUKTI.fullmatch(bukti.id):
        return "—"
    alamat = "%s?id=%s" % (RUTE_BUKTI, bukti.id)
    gambar = ('<img src="%s" alt="Bukti transfer" class="admin-bukti-gambar">' % alamat
              if bukti.mime.startswith("image/") else "")
    return gambar + ('<p><a class="admin-tautan" href="%s" target="_blank" rel="noopener noreferrer">Buka</a> '
                     '<a class="admin-tautan" href="%s&amp;unduh=1">Unduh</a></p>' % (alamat, alamat))


def _baris_bukti(nomor: int, bukti: BuktiView) -> str:
    ukuran = max(1, -(-bukti.ukuran // vp.BYTE_PER_KB))
    sel = (nomor, vp._waktu(bukti.waktu), e(_LABEL_MIME.get(bukti.mime, bukti.mime)), "%d KB" % ukuran,
           _pratinjau(bukti))
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % s for s in sel)


def _rincian(tagihan: k.TagihanKelas) -> str:
    r = tagihan.rincian
    baris = ["<p>Harga paket: <strong>%s</strong></p>" % e(rupiah(r.harga_dasar))]
    if r.potongan_deposit:
        baris.append("<p>Potongan deposit Peta: <strong>-%s</strong></p>" % e(rupiah(r.potongan_deposit)))
    if r.potongan_diskon:
        baris.append("<p>Diskon anak kedua: <strong>-%s</strong></p>" % e(rupiah(r.potongan_diskon)))
    return "".join(baris)


def _ringkasan(item: k.ItemAntrean, tagihan: k.TagihanKelas) -> str:
    badge = '<span class="admin-badge">%s</span>' % e(COPY_STATUS.get(tagihan.status, tagihan.status))
    return ('<section class="admin-kartu"><h2>%s</h2><p>Paket %s · %s</p>%s'
            '<p>Nominal yang harus masuk: <strong>%s</strong></p><p class="admin-meta">%s</p>'
            '<p><a class="admin-tautan" href="%s">Kembali ke daftar menunggu verifikasi</a></p></section>'
            % (e(JUDUL), e(_nama_paket(item.kode_paket)), badge, _rincian(tagihan), vp.nominal_sorot(tagihan.total),
               e(COPY_CATATAN_NOMINAL), RUTE))


def halaman_detail(item: k.ItemAntrean, tagihan: k.TagihanKelas, bukti: Sequence[BuktiView],
                   forms: Optional[Mapping[str, Token]] = None, *, baca_saja: bool = False) -> str:
    """Detail verifikasi. Form hanya bila `forms` ada dan tagihan menunggu; `baca_saja` memberi catatan tanpa sesi."""
    sesi = '<p class="admin-meta">%s</p>' % e(vp.COPY_TANPA_SESI) if baca_saja else ""
    baris = "".join(_baris_bukti(n, b) for n, b in enumerate(bukti, 1))
    keputusan = ""
    if forms and tagihan.status == k.STATUS_MENUNGGU:
        keputusan = ('<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Keputusan</h2>%s%s</section>'
                     % (_form_setujui(forms["setujui"]), _form_tolak(forms["tolak"])))
    tabel = vp._tabel("Bukti transfer", ("No.", "Diunggah", "Jenis", "Ukuran", "Pratinjau"), baris,
                      vp.COPY_TIDAK_ADA_BUKTI)
    return _ringkasan(item, tagihan) + sesi + tabel + keputusan


def form_keluarga(csrf: str, tinjauan: str) -> str:
    """Form kecil admin: tautkan dua anak (id siswa angka) sebagai satu keluarga untuk diskon anak kedua."""
    return ('<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>%s</h2><p class="admin-meta">%s</p>'
            '<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Id siswa pertama<input type="number" name="siswa_a" required min="1" inputmode="numeric" '
            'autocomplete="off"></label>'
            '<label>Id siswa kedua<input type="number" name="siswa_b" required min="1" inputmode="numeric" '
            'autocomplete="off"></label>%s<button class="admin-tombol" type="submit">Tautkan keluarga</button>'
            '</form></section>'
            % (e(COPY_JUDUL_KELUARGA), e(COPY_CATATAN_KELUARGA), RUTE_KELUARGA, e(COPY_KONFIRMASI_KELUARGA),
               vp._hidden(csrf, tinjauan), vp._SANDI))
