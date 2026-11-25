"""Render halaman Paket Belajar 1 Bulan untuk murid/orang tua: pilih paket dan tagihan (murni render, tanpa DB/HTTP/store).

Aturan isi:

- Semua angka dari kontrak (`PaketBelajar`, `Rincian`, `TagihanKelas`); tidak ada harga tulis tangan. Nominal
  transfer hanya dari tagihan (nominal + kode unik), tidak pernah dari form.
- Token form disuntik pemanggil lewat `token_untuk(aksi)` (pola Latihan Harian); tanpa JS baru, tanpa gambar baru.
- Halaman uang = tenang: tanpa maskot di tagihan; status selalu berupa teks (lencana), bukan hanya warna.
- Lokasi kelas offline belum ditetapkan, jadi kartu hanya menulis bahwa lokasi diumumkan setelah pendaftaran.
- Tidak ada klaim hasil belajar, id order, atau kontak. Semua nilai dinamis di-escape.
"""
from __future__ import annotations

import html
from typing import Callable, Optional, Sequence

import harian_langganan_dasar as h
import harian_langganan_style
import kelas_masa as km
import paket_belajar_katalog as k
import pesanan_murid_pages
import playful_components as C
from format_tanggal import tanggal_pendek
from pesanan_transfer_pages import COPY_ATURAN, COPY_LABEL_BERKAS, rupiah, waktu_wib
from playful_style import GAYA_CERIA

RUTE = "/murid/paket"
RUTE_BUAT = RUTE + "/buat"
RUTE_BUKTI = RUTE + "/bukti"
AKSI_BUAT = "kelas_buat:"
AKSI_BUKTI = "kelas_bukti"
ID_JUDUL = "judul-paket"
COPY_JUDUL = "Paket belajar 1 bulan"
COPY_PENGANTAR = ("Pilih paket, lalu transfer ke rekening kami dan unggah bukti transfernya. "
                  "Tim akan memeriksa bukti Anda.")
COPY_SAPA = "Pilih yang cocok ya, Ayah/Bunda!"
COPY_TOMBOL_DAFTAR = "Daftar paket ini"
COPY_TOMBOL_UNGGAH = "Unggah bukti"
COPY_TOMBOL_UNGGAH_ULANG = "Unggah ulang bukti"
COPY_LOKASI = "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar."
COPY_ADA_TAGIHAN = "Selesaikan tagihan yang sedang berjalan dulu sebelum mendaftar paket lain."
COPY_JUDUL_STATUS = "Status paket"
COPY_JUDUL_TAGIHAN = "Bayar lewat transfer"
COPY_REKENING_KOSONG = "Rekening tujuan belum tersedia. Hubungi tim sebelum mentransfer."
COPY_TULIS_TRANSFER = "Transfer persis ya. Tiga angka terakhir = kode unik."
COPY_LABEL_NOMINAL = "Total yang harus Anda transfer:"
COPY_MENUNGGU = "Bukti sudah kami terima. Tim sedang memeriksanya; paket aktif setelah bukti disetujui."
COPY_AKTIF_ISI = "Penjadwalan pertemuan diatur tim setelah pembayaran disetujui."
COPY_JUDUL_JADWAL = "Jadwal pertemuan"
COPY_DIBATALKAN = "Dibatalkan"
COPY_KEDALUWARSA = "Waktu pembayaran tagihan ini sudah habis. Silakan daftar lagi dari halaman pilih paket."
COPY_KEMBALI = "Kembali ke pilih paket"
_ACCEPT_BUKTI = "image/jpeg,image/png,application/pdf"
_LABEL_MODE = {k.MODE_ONLINE: "Belajar online", k.MODE_OFFLINE: "Tatap muka (offline)"}
_STATUS = {k.STATUS_BELUM_BAYAR: ("kuning", "Menunggu pembayaran"),
           k.STATUS_MENUNGGU: ("kuning", "Menunggu verifikasi"),
           k.STATUS_DITOLAK: ("koral", "Ditolak"),
           k.STATUS_KEDALUWARSA: ("koral", "Kedaluwarsa")}
_BOLEH_UNGGAH = (k.STATUS_BELUM_BAYAR, k.STATUS_DITOLAK)

TokenUntuk = Callable[[str], str]


def _e(teks: object) -> str:
    return html.escape(str(teks), quote=True)


def _p(teks: str, kelas: str = "") -> str:
    atribut = f' class="{kelas}"' if kelas else ""
    return f"<p{atribut}>{_e(teks)}</p>"


def _kartu(isi: str) -> str:
    return f'<section class="lg-kartu">{isi}</section>'


def _tombol(teks: str) -> str:
    return f'<button type="submit" class="ceria-tombol">{_e(teks)}</button>'


def _tanggal(baku: str) -> str:
    return tanggal_pendek(h.tanggal_wib(baku))


def _label_status(tagihan: k.TagihanKelas) -> tuple:
    """(nada, teks lencana). Aktif memuat tanggal berakhir; selain itu dari tabel tetap."""
    if tagihan.status == k.STATUS_AKTIF:
        sampai = f" sampai {_tanggal(tagihan.berakhir)}" if tagihan.berakhir else ""
        return "hijau", "Aktif" + sampai
    return _STATUS.get(tagihan.status, ("kuning", tagihan.status))


def _kartu_status(tagihan: k.TagihanKelas) -> str:
    nada, teks = _label_status(tagihan)
    isi = _p(COPY_AKTIF_ISI) if tagihan.status == k.STATUS_AKTIF else ""
    if tagihan.status == k.STATUS_MENUNGGU:
        isi = _p(COPY_MENUNGGU)
    return C.kartu_status(nada, teks, COPY_JUDUL_STATUS, isi, level=2)


# --- pilih paket ------------------------------------------------------------------------------

def _ringkas_isi(paket: k.PaketBelajar) -> str:
    baris = [f"{paket.pertemuan} pertemuan x {paket.menit} menit", _LABEL_MODE.get(paket.mode, paket.mode)]
    if paket.kuota:
        baris.append(f"Kelas kecil, maksimal {paket.kuota} anak")
    if paket.kode == k.KODE_MINI:
        baris.append(COPY_LOKASI)
    return "".join(_p(b, "lg-ket") for b in baris)


def _rincian_khusus(rincian: k.Rincian) -> str:
    if rincian.potongan_deposit:
        baris = f"Sudah dipotong deposit Peta {rupiah(rincian.potongan_deposit)}"
    else:
        return ""
    return _p(baris, "lg-hemat") + _p(f"Yang Anda bayar bulan ini: {rupiah(rincian.nominal)}", "lg-ket")


def _form_daftar(paket: k.PaketBelajar, token_untuk: TokenUntuk) -> str:
    return (f'<form method="post" action="{RUTE_BUAT}">'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_BUAT + paket.kode))}">'
            f'<input type="hidden" name="kode" value="{_e(paket.kode)}">'
            f'{_tombol(COPY_TOMBOL_DAFTAR)}</form>')


def _kartu_paket(kartu: k.KartuPaket, token_untuk: TokenUntuk) -> str:
    paket = kartu.paket
    aksi = _p(COPY_ADA_TAGIHAN, "lg-kecil") if kartu.ada_tagihan_terbuka else _form_daftar(paket, token_untuk)
    return (f'<section class="lg-paket"><div class="lg-paket-kepala"><div class="lg-paket-nama">'
            f'<h3>{_e(paket.nama)}</h3>{_ringkas_isi(paket)}</div>'
            f'<p class="lg-harga">{_e(rupiah(paket.harga))}</p></div>'
            f'{_rincian_khusus(kartu.rincian)}{aksi}</section>')


def _baris_pertemuan(sesi: dict) -> str:
    """'Pertemuan N · <waktu WIB>' (+ ' · Dibatalkan'); status selalu teks, bukan hanya warna."""
    teks = f"Pertemuan {int(sesi['ke'])} · {waktu_wib(sesi['mulai'])}"
    if sesi["dibatalkan"]:
        teks += f" · {COPY_DIBATALKAN}"
    return _p(teks, "lg-ket")


def _kartu_jadwal(jadwal: Optional[dict]) -> str:
    """Kartu 'Jadwal pertemuan': lokasi lalu pertemuan berurut. Hanya lokasi dan waktu; tanpa guru atau id apa pun."""
    if jadwal is None:
        return ""
    sesi = "".join(_baris_pertemuan(x) for x in jadwal["sesi"])
    return _kartu(f"<h2>{_e(COPY_JUDUL_JADWAL)}</h2>{_baris('Lokasi', jadwal['lokasi'])}{sesi}")


def halaman_pilih_paket(kartu: Sequence[k.KartuPaket], tagihan: Optional[k.TagihanKelas],
                        token_untuk: TokenUntuk, galat: str = "", kabar: str = "",
                        jadwal: Optional[dict] = None) -> bytes:
    """Halaman /murid/paket: status tagihan terakhir (bila ada) + kartu paket dengan rincian khusus pembeli.

    `jadwal` (bacaan `jadwal_store.jadwal_untuk_murid`) menambah kartu jadwal pertemuan; None = tanpa kartu.
    """
    pesan = (_kartu(_p(galat)) if galat else "") + (_kartu(_p(kabar)) if kabar else "") + _kartu_jadwal(jadwal)
    status = _kartu_status(tagihan) if tagihan is not None else ""
    sapa = C.maskot_bicara("menunjuk", COPY_SAPA)
    judul = f'<div class="lg-pilih-judul"><h2>Pilih paket</h2>{_p(COPY_PENGANTAR)}</div>'
    daftar = "".join(_kartu_paket(x, token_untuk) for x in kartu)
    return _bungkus(pesan + status + sapa + judul + daftar)


# --- tagihan ----------------------------------------------------------------------------------

def _baris(label: str, nilai: str) -> str:
    return f"<p>{_e(label)}: <strong>{_e(nilai)}</strong></p>"


def _baris_rincian(tagihan: k.TagihanKelas) -> str:
    r = tagihan.rincian
    baris = [_baris("Harga paket", rupiah(r.harga_dasar))]
    if r.potongan_deposit:
        baris.append(_baris("Potongan deposit Peta", "-" + rupiah(r.potongan_deposit)))
    baris.append(_baris("Kode unik", str(tagihan.kode_unik)))
    return f'<div class="lg-rincian">{"".join(baris)}</div>'


def _tentang_paket(paket: k.PaketBelajar) -> str:
    baris = [f"Paket: {paket.nama}", _LABEL_MODE.get(paket.mode, paket.mode),
             f"{paket.pertemuan} pertemuan x {paket.menit} menit"]
    if paket.kode == k.KODE_MINI:
        baris.append(COPY_LOKASI)
    return "".join(_p(b, "lg-kecil") for b in baris)


def _rekening(rekening: str) -> str:
    if not rekening.strip():
        return _p(COPY_REKENING_KOSONG, "lg-kecil")
    baris = "".join(f"<p>{_e(b)}</p>" for b in rekening.splitlines() if b.strip())
    return f'<div class="lg-rincian">{baris}</div>'


def _form_unggah(token: str, ulang: bool) -> str:
    return (f'<form method="post" action="{RUTE_BUKTI}" enctype="multipart/form-data">'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<label class="lg-berkas">{_e(COPY_LABEL_BERKAS)}'
            f'<input type="file" name="berkas" accept="{_ACCEPT_BUKTI}" required></label>'
            f'{_tombol(COPY_TOMBOL_UNGGAH_ULANG if ulang else COPY_TOMBOL_UNGGAH)}</form>')


def _isi_uang(tagihan: k.TagihanKelas, rekening: str, token_untuk: TokenUntuk) -> str:
    if tagihan.status in (k.STATUS_AKTIF, k.STATUS_KEDALUWARSA):
        return _p(COPY_KEDALUWARSA) if tagihan.status == k.STATUS_KEDALUWARSA else ""
    isi = (f'<p class="lg-kecil">{_e(COPY_LABEL_NOMINAL)}</p>'
           f'<p class="lg-nominal"><strong>{_e(rupiah(tagihan.total))}</strong></p>'
           f'<p class="lg-tulis">{_e(COPY_TULIS_TRANSFER)}</p><hr class="lg-pemisah">'
           f'{_rekening(rekening)}'
           f'{_baris("Batas waktu", waktu_wib(tagihan.kedaluwarsa)) if tagihan.kedaluwarsa else ""}')
    if tagihan.status in _BOLEH_UNGGAH:
        isi += _p(COPY_ATURAN, "lg-kecil") + _form_unggah(token_untuk(AKSI_BUKTI), tagihan.status == k.STATUS_DITOLAK)
    return isi


def halaman_tagihan(tagihan: k.TagihanKelas, paket: k.PaketBelajar, rekening: str,
                    token_untuk: TokenUntuk, galat: str = "") -> bytes:
    """Halaman tagihan: rincian nominal, total transfer + kode unik, jendela bayar, status, form unggah bila perlu.

    `rekening` = teks polos (satu baris per bagian); selalu di-escape, bukan HTML.
    """
    pesan = _kartu(_p(galat)) if galat else ""
    rincian = _kartu(f"<h2>{_e(paket.nama)}</h2>{_tentang_paket(paket)}{_baris_rincian(tagihan)}")
    uang = (f'<section class="lg-kartu lg-kertas"><h2>{_e(COPY_JUDUL_TAGIHAN)}</h2>'
            f'{_isi_uang(tagihan, rekening, token_untuk)}</section>')
    kembali = f'<p class="lg-kembali"><a href="{RUTE}">{_e(COPY_KEMBALI)}</a></p>'
    return _bungkus(pesan + _kartu_status(tagihan) + rincian + uang + kembali)


COPY_LABEL_KARTU_ORTU = "Paket belajar"
COPY_JUDUL_KARTU_ORTU = "Belajar bersama Guru"
COPY_TOMBOL_KARTU_ORTU = "Lihat paket belajar"
COPY_TAUTAN_MASUK = "Belajar bersama Guru: lihat paket belajar"


def tautan_masuk() -> str:
    """Satu tautan kecil ke `/murid/paket` untuk halaman langganan (pemanggil hanya memakainya bila sakelar aktif)."""
    return f'<p class="lg-kembali"><a href="{RUTE}">{_e(COPY_TAUTAN_MASUK)}</a></p>'


def kartu_orang_tua() -> str:
    """Kartu kecil halaman orang tua yang menuju `/murid/paket`; nama paket dan jumlah pertemuan dari katalog, tanpa klaim hasil."""
    nama = " atau ".join(p.nama for p in k.DAFTAR_PAKET)
    isi = _p(f"Pilih {nama}, {k.PERTEMUAN_PER_BULAN} pertemuan sebulan. Daftar lewat transfer, tim kami yang memeriksa.")
    return C.kartu_navy(_e(COPY_JUDUL_KARTU_ORTU), isi, RUTE, COPY_TOMBOL_KARTU_ORTU, label=COPY_LABEL_KARTU_ORTU,
                        id_="ortu-paket", level=2)


def _baris_banner(masa: km.MasaPaket, nama_anak: str) -> str:
    """Satu baris banner untuk paket yang segera berakhir atau sudah habis; semua nilai dinamis di-escape."""
    anak = _e(nama_anak or "anak")
    paket = _e(masa.nama)
    tautan = f'<a href="{RUTE}">Perpanjang</a>'
    if masa.status == km.STATUS_SEGERA:
        teks = f"Paket {paket} {anak} berakhir {masa.sisa_hari} hari lagi. {tautan}"
        lencana = "Segera berakhir"
    else:
        teks = f"Paket {paket} {anak} sudah berakhir. {tautan} untuk mendapat jadwal baru."
        lencana = "Sudah berakhir"
    return f'{C.lencana(lencana, "koral")} {teks}'


def banner_orang_tua(masa: Sequence[km.MasaPaket], nama_anak: str) -> str:
    """Banner perpanjang paket belajar: satu elemen `ortu-paket-banner`, satu baris per paket segera/habis; '' bila tak ada.

    Paket aktif (sisa di atas batas pengingat) tidak tampil. Pemanggil hanya memanggil bila sakelar PAKET_BELAJAR aktif.
    """
    baris = [_baris_banner(m, nama_anak) for m in masa
             if m.status in (km.STATUS_SEGERA, km.STATUS_HABIS)]
    if not baris:
        return ""
    return ('<p class="ortu-banner-st" id="ortu-paket-banner" role="status">' + "<br>".join(baris) + "</p>")


def kalimat_aktif(nama_paket: str, berakhir: str) -> str:
    """Satu kalimat status paket aktif (untuk `kabar` halaman pilih); `berakhir` = UTC naif baku."""
    return f"Paket {nama_paket} aktif sampai {_tanggal(berakhir)}."


def halaman_info(judul: str, teks: str) -> bytes:
    """Pesan tetap tanpa form (galat/penutupan), dengan tautan kembali ke halaman pilih paket."""
    isi = _kartu(f"<h2>{_e(judul)}</h2>{_p(teks)}") + f'<p class="lg-kembali"><a href="{RUTE}">{_e(COPY_KEMBALI)}</a></p>'
    return _bungkus(isi)


def _bungkus(isi: str) -> bytes:
    badan = f'<div class="lg-isi"><h1 id="{ID_JUDUL}">{_e(COPY_JUDUL)}</h1>{isi}</div>'
    css = GAYA_CERIA + harian_langganan_style.GAYA_LANGGANAN_HARIAN
    return pesanan_murid_pages.halaman_murid(COPY_JUDUL, ID_JUDUL, badan, "/murid", "Beranda", css_tambahan=css)
