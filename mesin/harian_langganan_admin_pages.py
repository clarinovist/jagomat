"""Renderer murni halaman admin langganan Latihan Harian: antrean bukti menunggu dan detail verifikasi (tanpa I/O).

Tanpa nama anak, kontak, id anak, nama berkas, atau sha256; nominal disorot persis (harga paket + kode unik).
Form Setujui/Tolak hanya untuk status menunggu dan sesi berkuki; sandi admin diminta tiap aksi (token tinjauan terikat
ke order dan bukti terakhir yang dilihat). Memakai ulang potongan renderer verifikasi transfer (tabel, sorot nominal,
kolom sandi) supaya admin melihat bentuk yang sama; semua nilai dinamis di-escape, waktu ledger ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple

from admin_komponen import e
import admin_verifikasi_pages as vp  # tabel, sorot nominal, kolom sandi, label bersama
import harian_langganan_dasar as h
from schema_transfer import BATAS_ALASAN

RUTE = "/admin/langganan"
RUTE_VERIFIKASI = RUTE + "/verifikasi"
RUTE_BUKTI = RUTE + "/bukti"
RUTE_SETUJUI = RUTE + "/setujui"
RUTE_TOLAK = RUTE + "/tolak"
SECTION = "langganan_harian"
JUDUL = "Langganan Latihan Harian"
SUBJUDUL = "Periksa bukti transfer paket Bulanan/Tahunan terhadap nominal persis, lalu setujui atau tolak. Tanpa nama anak dan kontak."
AKSI_SETUJUI = "setujui_langganan"
AKSI_TOLAK = "tolak_langganan"
HASIL_SETUJU = "verifikasi_setuju"
HASIL_TOLAK = "verifikasi_tolak"
COPY_HASIL = {HASIL_SETUJU: "Langganan disetujui dan masa aktif sudah dicatat.",
              HASIL_TOLAK: "Bukti ditolak; orang tua melihat alasannya dan dapat mengunggah ulang."}
COPY_ANTREAN_KOSONG = "Tidak ada bukti langganan yang menunggu verifikasi."
COPY_KONFIRMASI_SETUJUI = (
    "Setujui transfer ini? Langganan langsung aktif dan keputusan tidak dapat dibatalkan.")
COPY_KONFIRMASI_TOLAK = (
    "Tolak bukti ini? Orang tua akan melihat alasannya dan dapat mengunggah ulang selama waktu pembayaran terbuka.")
COPY_CATATAN_NOMINAL = (
    "Cocokkan nominal di mutasi rekening dengan angka di atas sampai tiga digit terakhir. Hanya bukti yang Anda lihat "
    "di halaman ini yang akan diputuskan; bila ada bukti baru, buka ulang halaman ini.")
COPY_GALAT_KONFLIK = (
    "Tagihan ini tidak sedang menunggu verifikasi, sudah diputuskan, atau ada bukti baru sejak Anda membuka halaman "
    "verifikasi. Buka ulang halaman verifikasi; tidak ada yang diubah.")
COPY_GALAT_ALASAN = (
    "Alasan penolakan wajib diisi (1 sampai %d karakter, tanpa karakter kontrol). Tidak ada yang diubah." % BATAS_ALASAN)
COPY_STATUS = {h.STATUS_AKTIF: "Disetujui", h.STATUS_MENUNGGU: "Menunggu verifikasi",
               h.STATUS_DITOLAK: "Ditolak (menunggu unggah ulang)", h.STATUS_KEDALUWARSA: "Kedaluwarsa",
               h.STATUS_BELUM_BAYAR: "Menunggu pembayaran"}

Token = Tuple[str, str]


def _banner(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _baris_antrean(item: Mapping) -> str:
    nama = h.PAKET[item["paket"]].nama
    tautan = '<a class="admin-tautan" href="%s?order=%s">Periksa bukti</a>' % (RUTE_VERIFIKASI, e(item["order_id"]))
    sel = (e(nama), vp.nominal_sorot(item["nominal"]), vp._waktu(item["diunggah"]), tautan)
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % s for s in sel)


def halaman_antrean(antrean, *, hasil: Optional[str] = None) -> str:
    """Daftar bukti menunggu, bukti terakhir paling lama dulu."""
    baris = "".join(_baris_antrean(i) for i in antrean)
    return _banner(hasil) + vp._tabel("Menunggu verifikasi", ("Paket", "Nominal", "Bukti terakhir", "Aksi"), baris,
                                      COPY_ANTREAN_KOSONG)


def _hidden(token: Token) -> str:
    return vp._hidden(*token)


def _form_setujui(token: Token) -> str:
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s%s'
            '<button class="admin-tombol" type="submit">Setujui transfer</button></form>'
            % (RUTE_SETUJUI, e(COPY_KONFIRMASI_SETUJUI), _hidden(token), vp._SANDI))


def _form_tolak(token: Token) -> str:
    return ('<details class="admin-form-tolak"><summary>%s</summary>'
            '<form method="post" action="%s" data-konfirmasi="%s">%s'
            '<label>Alasan penolakan<input type="text" name="alasan" required maxlength="%d" autocomplete="off">'
            '</label>%s<button class="admin-tombol admin-bahaya" type="submit">Tolak bukti</button></form></details>'
            % (e(vp.COPY_RINGKAS_TOLAK), RUTE_TOLAK, e(COPY_KONFIRMASI_TOLAK), _hidden(token), BATAS_ALASAN,
               vp._SANDI))


def _pratinjau(bukti: Mapping) -> str:
    alamat = "%s?id=%d" % (RUTE_BUKTI, bukti["id"])
    gambar = ('<img src="%s" alt="Bukti transfer nomor %d" class="admin-bukti-gambar">' % (alamat, bukti["id"])
              if bukti["mime"].startswith("image/") else "")
    return gambar + ('<p><a class="admin-tautan" href="%s" target="_blank" rel="noopener noreferrer">Buka</a> '
                     '<a class="admin-tautan" href="%s&amp;unduh=1">Unduh</a></p>' % (alamat, alamat))


def _baris_bukti(bukti: Mapping) -> str:
    ukuran = max(1, -(-bukti["ukuran"] // vp.BYTE_PER_KB))
    keadaan = "Menunggu keputusan" if bukti["keadaan"] == "menunggu" else "Sudah diputuskan"
    sel = (bukti["id"], vp._waktu(bukti["diunggah"]), e(vp._LABEL_MIME.get(bukti["mime"], bukti["mime"])),
           "%d KB" % ukuran, e(keadaan), _pratinjau(bukti))
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % s for s in sel)


def _riwayat(keputusan) -> str:
    baris = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(vp._LABEL_KEPUTUSAN.get(k["keputusan"], k["keputusan"])), e(k["alasan"] or "—"), vp._waktu(k["dibuat"]))
        for k in keputusan)
    return vp._tabel("Riwayat keputusan", ("Keputusan", "Alasan", "Waktu"), baris, vp.COPY_TIDAK_ADA_KEPUTUSAN)


def _ringkasan(detail: Mapping) -> str:
    status = detail["status"]
    badge = '<span class="admin-badge">%s</span>' % e(COPY_STATUS.get(status, status))
    return ('<section class="admin-kartu"><h2>%s</h2><p>Paket %s · %s</p>'
            '<p>Nominal yang harus masuk: <strong>%s</strong></p><p class="admin-meta">%s</p>'
            '<p><a class="admin-tautan" href="%s">Kembali ke daftar menunggu verifikasi</a></p></section>'
            % (e(JUDUL), e(detail["paket"]), badge, vp.nominal_sorot(detail["nominal"]), e(COPY_CATATAN_NOMINAL), RUTE))


def halaman_detail(detail: Mapping, forms: Optional[Mapping], *, baca_saja: bool = False) -> str:
    """Isi detail. `forms` = {'setujui': (csrf, tinjauan), 'tolak': (csrf, tinjauan)} atau None."""
    sesi = '<p class="admin-meta">%s</p>' % e(vp.COPY_TANPA_SESI) if baca_saja else ""
    bukti = "".join(_baris_bukti(b) for b in detail["bukti"])
    keputusan = ""
    if forms and detail["status"] == h.STATUS_MENUNGGU:
        keputusan = ('<section class="admin-kartu admin-form-tindakan admin-form-pendek"><h2>Keputusan</h2>%s%s</section>'
                     % (_form_setujui(forms["setujui"]), _form_tolak(forms["tolak"])))
    return (_ringkasan(detail) + sesi
            + vp._tabel("Bukti transfer", ("No.", "Diunggah", "Jenis", "Ukuran", "Keadaan", "Pratinjau"), bukti,
                        vp.COPY_TIDAK_ADA_BUKTI)
            + _riwayat(detail["keputusan"]) + keputusan)
