"""Render halaman Paket Belajar 1 Bulan untuk murid/orang tua: pilih paket dan tagihan (murni render, tanpa DB/HTTP/store).

Aturan isi:

- Semua angka dari kontrak (`PaketBelajar`, `Rincian`, `TagihanKelas`); tidak ada harga tulis tangan. Nominal
  transfer hanya dari tagihan (nominal + kode unik), tidak pernah dari form.
- Token form disuntik pemanggil lewat `token_untuk(aksi)` (pola Latihan Harian); tanpa JS baru, tanpa gambar baru.
- Halaman uang = tenang: tanpa maskot di tagihan; status selalu berupa teks (lencana), bukan hanya warna.
- Mini Class online tanpa lokasi fisik (keputusan Pemilik 25 Nov 2026): kolom lokasi kelompok berupa tautan Zoom
  atau Google Meet. Kartu jadwal menampilkannya sebagai tautan hanya bila lolos validasi ulang; selain itu teks biasa.
- Tidak ada klaim hasil belajar, id order, atau kontak. Semua nilai dinamis di-escape.
- Daftar paket SELALU tampil. Di atasnya satu kartu per tagihan terbuka (tautan per KODE paket, bukan id order). Hapus tagihan
  (konfirmasi GET + POST) hanya untuk tagihan belum bayar tanpa bukti dan bila tabel catatan tagihan sudah dipasang.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING, Callable, Mapping, Optional, Sequence

import harian_langganan_dasar as h
import harian_langganan_style
import jadwal_tautan as jt
import kelas_dasar as dasar
import kelas_masa as km
import paket_belajar_katalog as k
import pesanan_murid_pages
import playful_components as C
from format_tanggal import tanggal_pendek
from pesanan_transfer_pages import COPY_ATURAN, COPY_LABEL_BERKAS, rupiah, waktu_wib
from playful_style import GAYA_CERIA

if TYPE_CHECKING:  # hanya untuk anotasi: tidak menarik DB/domain saat modul render dimuat
    from jadwal_tunggu_mini import StatusTunggu

RUTE = "/murid/paket"
RUTE_BUAT = RUTE + "/buat"
RUTE_BUKTI = RUTE + "/bukti"
RUTE_TAGIHAN = RUTE + "/tagihan"
RUTE_HAPUS = RUTE + "/hapus"
RUTE_JADWAL = RUTE + "/jadwal"
RUTE_TUNGGU = RUTE + "/tunggu"
RUTE_TUNGGU_KELUAR = RUTE + "/tunggu/keluar"
RUTE_KALENDER = RUTE + "/kalender.ics"
AKSI_JADWAL = "jadwal_pilih:"
AKSI_TUNGGU = "jadwal_tunggu_masuk:"
AKSI_TUNGGU_KELUAR = "jadwal_tunggu_keluar"
AKSI_BUAT = "kelas_buat:"
AKSI_HAPUS = "kelas_hapus:"
AKSI_BUKTI = "kelas_bukti:"
ID_JUDUL = "judul-paket"
COPY_JUDUL = "Paket belajar 1 bulan"
COPY_PENGANTAR = ("Pilih paket, lalu transfer ke rekening kami dan unggah bukti transfernya. "
                  "Tim akan memeriksa bukti Anda.")
COPY_SAPA = "Pilih yang cocok ya, Ayah/Bunda!"
COPY_TOMBOL_DAFTAR = "Daftar paket ini"
COPY_TOMBOL_UNGGAH = "Unggah bukti"
COPY_TOMBOL_UNGGAH_ULANG = "Unggah ulang bukti"
COPY_LOKASI = "Kelas berlangsung online lewat Zoom atau Google Meet. Tautan dikirim setelah Anda daftar."
COPY_ADA_TAGIHAN = "Tagihan paket ini ada di atas."
COPY_JUDUL_STATUS = "Status paket"
COPY_JUDUL_TAGIHAN = "Bayar lewat transfer"
COPY_REKENING_KOSONG = "Rekening tujuan belum tersedia. Hubungi tim sebelum mentransfer."
COPY_TULIS_TRANSFER = "Transfer persis ya. Tiga angka terakhir = kode unik."
COPY_LABEL_NOMINAL = "Total yang harus Anda transfer:"
COPY_MENUNGGU = "Bukti sudah kami terima. Tim sedang memeriksanya; paket aktif setelah bukti disetujui."
COPY_AKTIF_ISI = "Penjadwalan pertemuan diatur tim setelah pembayaran disetujui."
COPY_JUDUL_JADWAL = "Jadwal pertemuan"
COPY_JUDUL_PILIH_JADWAL = "Pilih jadwal kelas"
COPY_PENGANTAR_PILIH_JADWAL = ("Pembayaran sudah disetujui. Pilih kelompok belajar untuk anak. Pilihan hanya bisa sekali; "
                               "bila perlu pindah, hubungi tim.")
COPY_TOMBOL_PILIH_JADWAL = "Pilih kelompok ini"
COPY_PENUH = "penuh"
COPY_SEMUA_PENUH = "Semua kelompok sedang penuh."
COPY_TOMBOL_TUNGGU = "Masuk daftar tunggu"
COPY_TOMBOL_TUNGGU_KELUAR = "Keluar dari daftar tunggu"
COPY_TUNGGU_SAYA = "Anda di daftar tunggu kelompok %s. Urutan %d."
COPY_TUNGGU_PINDAH = "Anak hanya bisa di satu daftar tunggu. Masuk daftar lain menggantikan daftar ini."
COPY_SIMPAN_KALENDER = "Simpan ke kalender"
COPY_BAYAR_DALAM = "Bayar dalam %d jam sejak tagihan dibuat."
COPY_TAUTAN_KELAS = "Tautan kelas"
COPY_DIBATALKAN = "Dibatalkan"
COPY_KEDALUWARSA = "Waktu pembayaran tagihan ini sudah habis. Silakan daftar lagi dari halaman pilih paket."
COPY_KEMBALI = "Kembali ke pilih paket"
COPY_TAUTAN_TAGIHAN = "Lanjutkan pembayaran"
COPY_TAUTAN_HAPUS = "Hapus tagihan"
COPY_TOMBOL_HAPUS = "Ya, hapus tagihan"
COPY_BATAL = "Batal"
COPY_JUDUL_HAPUS = "Hapus tagihan"
COPY_AKIBAT_HAPUS = ("Jangan transfer ke tagihan ini setelah dihapus. Bila Anda sudah terlanjur mentransfer, hubungi tim "
                     "lewat WhatsApp dulu sebelum menghapus.")
COPY_PULIH = "Memilih lagi memulihkan tagihan yang tadi dihapus (sisa waktu bayar: %s)."
COPY_DIBATALKAN_ISI = "Tagihan ini sudah dihapus. Pilih paket lagi bila masih ingin mendaftar."
COPY_TOTAL_TRANSFER = "Total transfer:"
_ACCEPT_BUKTI = "image/jpeg,image/png,application/pdf"
_LABEL_MODE = {k.MODE_ONLINE: "Belajar online", k.MODE_OFFLINE: "Tatap muka (offline)"}
_STATUS = {k.STATUS_BELUM_BAYAR: ("kuning", "Menunggu pembayaran"),
           k.STATUS_MENUNGGU: ("kuning", "Menunggu verifikasi"),
           k.STATUS_DITOLAK: ("koral", "Ditolak"),
           k.STATUS_KEDALUWARSA: ("koral", "Kedaluwarsa"),
           k.STATUS_DIBATALKAN: ("koral", COPY_DIBATALKAN)}
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


def _aksi_paket(kartu: k.KartuPaket, token_untuk: TokenUntuk, dibatalkan_sampai: Optional[str]) -> str:
    """Tombol Daftar, atau penanda 'ada di atas' bila paket sudah punya tagihan terbuka; catatan pulih bila dibatalkan."""
    if kartu.ada_tagihan_terbuka:
        return _p(COPY_ADA_TAGIHAN, "lg-kecil")
    pulih = _p(COPY_PULIH % waktu_wib(dibatalkan_sampai), "lg-kecil") if dibatalkan_sampai else ""
    return pulih + _form_daftar(kartu.paket, token_untuk)


def _kartu_paket(kartu: k.KartuPaket, token_untuk: TokenUntuk, dibatalkan_sampai: Optional[str] = None) -> str:
    paket = kartu.paket
    aksi = _aksi_paket(kartu, token_untuk, dibatalkan_sampai)
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


def _baris_tautan(tautan: str) -> str:
    """Tautan Zoom/Meet yang sudah lolos validasi: buka di tab baru; href dan teks sama-sama di-escape."""
    return (f'<p>{_e(COPY_TAUTAN_KELAS)}: <strong><a href="{_e(tautan)}" target="_blank" '
            f'rel="noopener noreferrer nofollow">{_e(tautan)}</a></strong></p>')


def _baris_lokasi(lokasi: str) -> str:
    """Lokasi Mini sebagai tautan bila lolos validasi ulang (DB tidak dipercaya); selain itu teks biasa."""
    if not jt.tautan_meeting_sah(lokasi):
        return _baris("Lokasi", lokasi)
    return _baris_tautan(lokasi.strip())


def _tautan_kalender() -> str:
    """Tautan unduh berkas .ics (tanpa JS); hanya tampil bersama kartu jadwal yang sudah terpasang."""
    return f'<p><a href="{RUTE_KALENDER}">{_e(COPY_SIMPAN_KALENDER)}</a></p>'


def _kartu_jadwal(jadwal: Optional[dict]) -> str:
    """Kartu 'Jadwal pertemuan': lokasi (atau tautan kelas), pertemuan berurut, lalu tautan kalender. Tanpa guru atau id."""
    if jadwal is None:
        return ""
    sesi = "".join(_baris_pertemuan(x) for x in jadwal["sesi"])
    return _kartu(f"<h2>{_e(COPY_JUDUL_JADWAL)}</h2>{_baris_lokasi(jadwal['lokasi'])}{sesi}{_tautan_kalender()}")


def _baris_tunggu(pilihan, token_untuk: TokenUntuk, tunggu: Optional["StatusTunggu"]) -> str:
    """Daftar tunggu di bawah satu kelompok: status anak bila menunggu di sini, atau tombol masuk bila kelompok penuh.

    `tunggu` None = daftar tunggu tidak bisa dibaca: tanpa tombol apa pun (kartu pilih tetap utuh).
    """
    if tunggu is None:
        return ""
    saya = tunggu.saya
    if saya is not None and saya.kelompok_id == pilihan.kelompok_id:
        return (_p(COPY_TUNGGU_SAYA % (pilihan.nama, saya.urutan))
                + f'<form method="post" action="{RUTE_TUNGGU_KELUAR}">'
                f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_TUNGGU_KELUAR))}">'
                f'{_tombol(COPY_TOMBOL_TUNGGU_KELUAR)}</form>')
    if not pilihan.penuh:
        return ""
    return (f'<form method="post" action="{RUTE_TUNGGU}">'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_TUNGGU + pilihan.kelompok_id))}">'
            f'<input type="hidden" name="kelompok" value="{_e(pilihan.kelompok_id)}">'
            f'{_tombol(COPY_TOMBOL_TUNGGU)}</form>')


def _form_pilih_jadwal(pilihan, token_untuk: TokenUntuk, tunggu: Optional["StatusTunggu"] = None) -> str:
    """Satu kelompok: nama, pertemuan pertama (WIB), sisa kursi, dan tombol pilih. Kelompok penuh tanpa form pilih.

    `tunggu` menambah baris daftar tunggu (lihat `_baris_tunggu`). Tanpa guru atau lokasi.
    """
    ringkas = f"{pilihan.nama} · mulai {waktu_wib(pilihan.mulai)}"
    if pilihan.penuh:
        return _p(f"{ringkas} · {COPY_PENUH}", "lg-ket") + _baris_tunggu(pilihan, token_untuk, tunggu)
    ringkas += f" · sisa {int(pilihan.sisa)} kursi"
    return (f'<form method="post" action="{RUTE_JADWAL}">{_p(ringkas, "lg-ket")}'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_JADWAL + pilihan.kelompok_id))}">'
            f'<input type="hidden" name="kelompok" value="{_e(pilihan.kelompok_id)}">'
            f'{_tombol(COPY_TOMBOL_PILIH_JADWAL)}</form>' + _baris_tunggu(pilihan, token_untuk, tunggu))


def _kartu_pilih_jadwal(pilihan: Sequence, token_untuk: TokenUntuk, html_tambahan: str = "",
                        tunggu: Optional["StatusTunggu"] = None) -> str:
    """Kartu 'Pilih jadwal kelas' untuk Mini aktif yang belum ditempatkan (butir QA #4); kosong = tanpa kartu.

    Bila semua kelompok penuh, kartu tetap tampil dengan kabar penuh. `tunggu` (F2c) menambah tombol daftar tunggu per
    kelompok penuh; None = tanpa tombol. `html_tambahan` = titik sambung tanpa tombol.
    """
    if not pilihan:
        return ""
    daftar = "".join(_form_pilih_jadwal(x, token_untuk, tunggu) for x in pilihan)
    kabar = _p(COPY_SEMUA_PENUH, "lg-kecil") if all(x.penuh for x in pilihan) else ""
    pindah = _p(COPY_TUNGGU_PINDAH, "lg-kecil") if tunggu is not None and tunggu.saya is not None else ""
    return _kartu(f"<h2>{_e(COPY_JUDUL_PILIH_JADWAL)}</h2>{_p(COPY_PENGANTAR_PILIH_JADWAL, 'lg-kecil')}"
                  f"{daftar}{kabar}{pindah}{html_tambahan}")


def _boleh_hapus_tagihan(tagihan: k.TagihanKelas, boleh_hapus: bool) -> bool:
    return boleh_hapus and tagihan.status == k.STATUS_BELUM_BAYAR and not tagihan.jumlah_bukti


def _kartu_tagihan(tagihan: k.TagihanKelas, boleh_hapus: bool) -> str:
    """Kartu satu tagihan terbuka di atas daftar: paket, total transfer, status (teks), batas waktu, dan tautan per kode."""
    nada, teks = _label_status(tagihan)
    kode = _e(tagihan.kode_paket)
    tautan = f'<a href="{RUTE_TAGIHAN}?kode={kode}">{_e(COPY_TAUTAN_TAGIHAN)}</a>'
    if _boleh_hapus_tagihan(tagihan, boleh_hapus):
        tautan += f' · <a href="{RUTE_HAPUS}?kode={kode}">{_e(COPY_TAUTAN_HAPUS)}</a>'
    batas = _baris("Batas waktu", waktu_wib(tagihan.kedaluwarsa)) if tagihan.kedaluwarsa else ""
    return _kartu(f'<h2>{_e(k.ambil(tagihan.kode_paket).nama)}</h2>{C.lencana(teks, nada)}'
                  f'<p class="lg-kecil">{_e(COPY_TOTAL_TRANSFER)}</p>'
                  f'<p class="lg-nominal"><strong>{_e(rupiah(tagihan.total))}</strong></p>{batas}<p>{tautan}</p>')


def halaman_pilih_paket(kartu: Sequence[k.KartuPaket], tagihan_terbuka: Sequence[k.TagihanKelas],
                        token_untuk: TokenUntuk, galat: str = "", kabar: str = "",
                        jadwal: Optional[dict] = None, pilihan_jadwal: Sequence = (), privat: str = "", *,
                        dibatalkan: Optional[Mapping[str, str]] = None, boleh_hapus: bool = False,
                        tunggu: Optional["StatusTunggu"] = None) -> bytes:
    """Halaman /murid/paket: SELALU daftar paket; di atasnya satu kartu per tagihan terbuka.

    `tagihan_terbuka` = tagihan belum bayar, menunggu, atau ditolak milik anak (`kelas_store.tagihan_terbuka_semua`).
    `dibatalkan` = {kode paket: batas waktu WIB} untuk paket yang tagihannya baru dihapus (catatan pulih, tombol tetap ada).
    `boleh_hapus` = tautan hapus boleh tampil (tabel catatan terpasang dan tirai tidak menahan).
    `jadwal` (bacaan `jadwal_store.jadwal_untuk_murid`) menambah kartu jadwal pertemuan; None = tanpa kartu.
    `pilihan_jadwal` (`jadwal_pilih.pilihan_untuk`) menambah kartu pilih kelompok; kosong = tanpa kartu.
    `tunggu` (`jadwal_tunggu_mini.status_tunggu`) menambah tombol daftar tunggu di kartu pilih; None = tanpa tombol.
    `privat` (kartu Jadwal Private dari `kelas_private_pages`) menambah kartu di bawahnya; "" = tanpa kartu.
    """
    pesan = ((_kartu(_p(galat)) if galat else "") + (_kartu(_p(kabar)) if kabar else "") + _kartu_jadwal(jadwal)
             + _kartu_pilih_jadwal(pilihan_jadwal, token_untuk, tunggu=tunggu) + privat)
    kartu_tagihan = "".join(_kartu_tagihan(t, boleh_hapus) for t in tagihan_terbuka)
    sapa = C.maskot_bicara("menunjuk", COPY_SAPA)
    judul = f'<div class="lg-pilih-judul"><h2>Pilih paket</h2>{_p(COPY_PENGANTAR)}</div>'
    tanda = dibatalkan or {}
    daftar = "".join(_kartu_paket(x, token_untuk, tanda.get(x.paket.kode)) for x in kartu)
    return _bungkus(pesan + kartu_tagihan + sapa + judul + daftar)


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


def _form_unggah(token: str, ulang: bool, kode_paket: str) -> str:
    return (f'<form method="post" action="{RUTE_BUKTI}?kode={_e(kode_paket)}" enctype="multipart/form-data">'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<label class="lg-berkas">{_e(COPY_LABEL_BERKAS)}'
            f'<input type="file" name="berkas" accept="{_ACCEPT_BUKTI}" required></label>'
            f'{_tombol(COPY_TOMBOL_UNGGAH_ULANG if ulang else COPY_TOMBOL_UNGGAH)}</form>')


def _isi_uang_selesai(status: str) -> str:
    """Isi uang untuk tagihan yang tidak lagi dibayar: kedaluwarsa atau dibatalkan (teks); aktif tanpa isi."""
    if status == k.STATUS_KEDALUWARSA:
        return _p(COPY_KEDALUWARSA)
    if status == k.STATUS_DIBATALKAN:
        return _p(COPY_DIBATALKAN_ISI, "lg-kecil")
    return ""


def _baris_batas(tagihan: k.TagihanKelas) -> str:
    """Batas bayar: waktu berakhir (WIB) dan jendela bayar dari pembuatan tagihan; kosong bila tagihan tak berbatas."""
    if not tagihan.kedaluwarsa:
        return ""
    return _baris("Batas waktu", waktu_wib(tagihan.kedaluwarsa)) + _p(COPY_BAYAR_DALAM % dasar.KEDALUWARSA_JAM, "lg-kecil")


def _isi_uang(tagihan: k.TagihanKelas, rekening: str, token_untuk: TokenUntuk) -> str:
    if tagihan.status in (k.STATUS_AKTIF, k.STATUS_KEDALUWARSA, k.STATUS_DIBATALKAN):
        return _isi_uang_selesai(tagihan.status)
    isi = (f'<p class="lg-kecil">{_e(COPY_LABEL_NOMINAL)}</p>'
           f'<p class="lg-nominal"><strong>{_e(rupiah(tagihan.total))}</strong></p>'
           f'<p class="lg-tulis">{_e(COPY_TULIS_TRANSFER)}</p><hr class="lg-pemisah">'
           f'{_rekening(rekening)}{_baris_batas(tagihan)}')
    if tagihan.status in _BOLEH_UNGGAH:
        isi += _p(COPY_ATURAN, "lg-kecil") + _form_unggah(token_untuk(AKSI_BUKTI + tagihan.kode_paket),
                                                          tagihan.status == k.STATUS_DITOLAK, tagihan.kode_paket)
    return isi


def halaman_konfirmasi_hapus(tagihan: k.TagihanKelas, paket: k.PaketBelajar, token_untuk: TokenUntuk) -> bytes:
    """Konfirmasi hapus tagihan belum bayar tanpa bukti: nama paket, total, akibat uang, tombol POST, dan batal kembali."""
    formulir = (f'<form method="post" action="{RUTE_HAPUS}">'
                f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_HAPUS + paket.kode))}">'
                f'<input type="hidden" name="kode" value="{_e(paket.kode)}">'
                f'{_tombol(COPY_TOMBOL_HAPUS)}</form>')
    kembali = f'<p class="lg-kembali"><a href="{RUTE_TAGIHAN}?kode={_e(paket.kode)}">{_e(COPY_BATAL)}</a></p>'
    isi = _kartu(f"<h2>{_e(COPY_JUDUL_HAPUS)} {_e(paket.nama)}?</h2>"
                 f"{_p(COPY_TOTAL_TRANSFER + ' ' + rupiah(tagihan.total))}{_p(COPY_AKIBAT_HAPUS, 'lg-kecil')}{formulir}")
    return _bungkus(isi + kembali)


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


def _baris_tagihan(tagihan: km.TagihanBelumBayar, nama_anak: str) -> str:
    anak = _e(nama_anak or "anak")
    paket = _e(tagihan.nama)
    tautan = f'<a href="{RUTE_TAGIHAN}?kode={_e(tagihan.kode_paket)}">{_e(COPY_TAUTAN_TAGIHAN)}</a>'
    if tagihan.status == k.STATUS_DITOLAK:
        return f'{C.lencana("Bukti belum sesuai", "koral")} Tagihan {paket} {anak} belum dibayar: bukti ditolak. {tautan}'
    return f'{C.lencana("Belum dibayar", "kuning")} Tagihan {paket} {anak} belum dibayar. {tautan}'


def banner_tagihan(tagihan: Sequence[km.TagihanBelumBayar], nama_anak: str) -> str:
    """Banner pengingat tagihan paket belajar yang menggantung: satu elemen `ortu-tagihan-banner`; '' bila tak ada.

    Menaut ke halaman pilih paket, yang menampilkan tagihan berjalan dan rekening. Pemanggil hanya memanggil bila
    sakelar PAKET_BELAJAR aktif.
    """
    if not tagihan:
        return ""
    baris = "<br>".join(_baris_tagihan(t, nama_anak) for t in tagihan)
    return f'<p class="ortu-banner-st" id="ortu-tagihan-banner" role="status">{baris}</p>'


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
    return pesanan_murid_pages.halaman_murid(
        COPY_JUDUL, ID_JUDUL, badan, pesanan_murid_pages.TUJUAN_ORANG_TUA, pesanan_murid_pages.LABEL_ORANG_TUA,
        css_tambahan=css)
