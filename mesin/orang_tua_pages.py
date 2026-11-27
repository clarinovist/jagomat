"""Render halaman orang tua di akun murid: form PIN tirai dan isi baca-saja.

Murni render (tanpa DB, tanpa token). Pakai ulang blok hasil cek (`cek_pages`), renderer laporan Guru
(`parent_report_page.isi_laporan`), dan teks status pesanan (`pesanan_pages.COPY_STATUS`). Tanpa JS baru:
satu-satunya skrip adalah `SKRIP_MATA_SANDI` yang sudah disetujui (toggle mata untuk PIN).

DILARANG di halaman ini: kunci jawaban, malrule, kode diagnosis, pembahasan soal, dan kontak orang tua
(nomor WhatsApp tidak pernah dirender; hanya kalimat bahwa perubahan lewat tim). Cek: skor dan kategori boleh.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta

import brand
import cek_gratis_skor
import cek_pages
import format_tanggal
import guru_pertemuan_aturan as aturan
import guru_tugas_aturan
import harian_langganan_pages
import harian_pages
import kelas_pages
import paket_belajar_katalog as katalog
import playful_components as C
import parent_report_page
import pesanan_dasar
import pesanan_pages
import pesanan_transfer_pages
import pesanan_voucher_pages
import peta_laporan_ortu_pages
from funnel_style import GAYA_FUNNEL
from murid_shell import PANAH_KEMBALI, aksi_topbar, bungkus_murid, kepala_murid, topbar_murid
from orang_tua_style import GAYA_ORTU, RUTE
from parent_report_page import GAYA_LO
from playful_style import GAYA_CERIA
from purna import VOUCHER_AKTIF
from style_stitch import gaya_stitch
from teacher_style import SKRIP_MATA_SANDI

RUTE_PIN = RUTE + "/pin"
RUTE_ATUR = RUTE_PIN + "/atur"
RUTE_HAPUS = RUTE_PIN + "/hapus"
RUTE_PAKET = kelas_pages.RUTE
RUTE_LANGGANAN = harian_langganan_pages.RUTE

COPY_JUDUL = "Halaman Ayah/Bunda"
COPY_ALIS = "UNTUK AYAH/BUNDA"
COPY_SAPAAN = "Halo, Ayah/Bunda"
COPY_RINGKASAN_ANAK = "Ringkasan belajar %s"
COPY_RINGKASAN_UMUM = "Ringkasan belajar anak"
COPY_KALIMAT = (
    "Halaman ini untuk Ayah/Bunda. Nomor WhatsApp untuk tagihan hanya bisa diubah lewat tim Jagomat."
)
COPY_CEK_JUDUL = "Hasil cek kemampuan"
COPY_CEK_BELUM = "Cek kemampuan belum dikerjakan."
COPY_CEK_BELUM_SELESAI = "Cek kemampuan belum selesai dikerjakan."
COPY_CEK_LANJUT = "Lanjutkan cek"
RUTE_BERANDA_ANAK = "/murid#judul-cek-murid"  # kartu cek ada di beranda; tombolnya POST, jadi tautan mengarah ke kartu
COPY_LAPORAN_JUDUL = "Laporan dari Guru"
COPY_LAPORAN_KOSONG = "Belum ada laporan dari Guru."
COPY_PESANAN_JUDUL = "Peta Kemampuan"
COPY_PESANAN_LANGKAH = "Langkah berikutnya"
COPY_PESANAN_HARGA_SUB = "Bukan langganan. Tidak ada tagihan bulan depan."
# Harfiah dari funnel_pages.COPY_PEMBATALAN_BUTIR (kalimat pertama); jangan diringkas.
COPY_PESANAN_TIDAK_KEMBALI = (
    "Laporan langsung terbit setelah pembayaran terverifikasi, jadi pembayaran tidak dapat dikembalikan."
)
COPY_PESANAN_BAYAR = "Buka Peta Kemampuan · %s"
COPY_PESANAN_LIHAT_STATUS = "Lihat status pembayaran"
COPY_PESANAN_LUNAS_TERBIT = "Lunas · laporan terbit"
COPY_BUKA_LAPORAN = "Buka laporan lengkap"
COPY_LIHAT_KELAS = "Lihat kelas"
COPY_LANGGANAN = "Langganan"
COPY_POTONGAN = "Potongan deposit Peta %s untuk tagihan bulan pertama"
COPY_DAFTAR_KELAS = "Daftar kelas"
OPSI_KELAS = ((katalog.KODE_PRIVATE, "Private"), (katalog.KODE_MINI, "Mini Class"))
# Status yang tidak meminta pembeli membayar lagi: kalimat dari `COPY_STATUS` dipakai apa adanya (butir QA #1).
STATUS_PESANAN_TANPA_TINDAKAN = frozenset((
    pesanan_pages.STATUS_MENUNGGU_VERIFIKASI, pesanan_pages.STATUS_PERLU_DIPERIKSA, pesanan_pages.STATUS_DIREFUND,
))
# Belum lunas dan masih menunggu tindakan pembeli: kartu gelap "Buka Peta Kemampuan" dengan lencana statusnya.
STATUS_PESANAN_BUTUH_BAYAR = frozenset((
    pesanan_pages.STATUS_BELUM_BAYAR, pesanan_pages.STATUS_KEDALUWARSA, pesanan_pages.STATUS_DITOLAK,
))
# Kalimat status ikut tampil di kartu gelap; kalimat "belum bayar" memuat instruksi QRIS dan tidak ikut.
STATUS_PESANAN_KALIMAT_KARTU = frozenset((pesanan_pages.STATUS_KEDALUWARSA, pesanan_pages.STATUS_DITOLAK))
COPY_PESANAN_TERBIT = "Pembayaran diterima. Laporan Peta Kemampuan sudah tersedia di halaman ini."
COPY_PESANAN_DISIAPKAN = "Pembayaran diterima. Laporan sedang disiapkan."
COPY_PESANAN_LIHAT_DEPOSIT = "Lihat potongan & rincian pesanan"
COPY_KEHADIRAN_JUDUL = "Kehadiran dan jurnal"
COPY_TUGAS_JUDUL = "Tugas dari Guru"
COPY_TENGGAT = "Tenggat %s"
COPY_LEWAT_TENGGAT = "Lewat tenggat"
COPY_BELUM_DIKERJAKAN = "Belum dikerjakan"
COPY_SELESAI = "Selesai · %d dari %d benar"
COPY_TOPIK = "Topik: %s"
COPY_BELUM_DICATAT = "Belum dicatat"
STATUS_HADIR_TAMPIL = {"hadir": "Hadir", "izin": "Izin", "tidak_hadir": "Tidak hadir"}
HARI_SINGKAT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
PEMISAH_WAKTU = " · "
COPY_PIN_MASUK_JUDUL = "Masukkan PIN"
COPY_PIN_MASUK_TEKS = "Halaman ini ditutup dengan PIN. Masukkan 4 angka PIN Ayah/Bunda untuk membukanya."
COPY_PIN_SALAH = "PIN belum cocok. Coba lagi."
COPY_PIN_DIBLOKIR = "Coba lagi beberapa menit lagi."
COPY_PIN_PERLU_BUKA = "Masukkan PIN dulu, ya."
COPY_PIN_TIDAK_SAH = "PIN harus 4 angka, dan isian ulangnya harus sama."
COPY_KONFIRMASI_WAJIB = "Centang konfirmasi dulu untuk menghapus PIN."
COPY_PIN_KARTU = "PIN halaman Ayah/Bunda"
COPY_PIN_STATUS_ADA = "Sudah dipasang"
COPY_PIN_STATUS_TIDAK_ADA = "Belum dipasang"
COPY_PIN_ADA = "PIN sudah dipasang. Halaman ini tertutup sampai PIN dimasukkan."
COPY_PIN_TIDAK_ADA = "Belum ada PIN. Siapa pun yang memegang akun anak bisa membuka halaman ini."
COPY_PIN_CATATAN = "PIN ini penutup halaman, bukan pengaman data."
COPY_KONFIRMASI_HAPUS = "Saya yakin ingin menghapus PIN. Setelah itu halaman ini terbuka tanpa PIN."
KABAR = {
    "pin-dipasang": "PIN sudah disimpan.",
    "pin-dihapus": "PIN sudah dihapus.",
}

_ATRIBUT_PIN = ' inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off" required'


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _field_pin(id_, label, nama) -> str:
    return (
        '<div class="masuk-field-st">'
        f'<label for="{id_}">{_e(label)}</label>'
        f'<input type="password" id="{id_}" name="{nama}"{_ATRIBUT_PIN}></div>'
    )


def _tombol(teks) -> str:
    return f'<button type="submit" class="ortu-tombol-st">{_e(teks)}</button>'


def _pesan(kabar: str, galat: str) -> str:
    teks = KABAR.get(kabar, "")
    kabar_html = f'<p class="ortu-kabar-st" role="status">{_e(teks)}</p>' if teks else ""
    galat_html = f'<p class="ortu-galat-st" role="alert">{_e(galat)}</p>' if galat else ""
    return kabar_html + galat_html


def _kepala() -> str:
    return (
        '<header class="ortu-kepala-st">'
        f'<p class="editorial-alis-st">{_e(COPY_ALIS)}</p><h1 id="judul-ortu">{_e(COPY_JUDUL)}</h1>'
        f'<p>{_e(COPY_KALIMAT)}</p></header>'
    )


def _dokumen(badan: str, ceria: bool = False) -> bytes:
    css = gaya_stitch() + GAYA_FUNNEL + GAYA_LO + GAYA_ORTU + (GAYA_CERIA if ceria else "")
    topbar = topbar_murid(aksi_topbar("/murid", "Kembali", PANAH_KEMBALI))
    return (
        '<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f'<title>{_e(brand.judul(COPY_JUDUL))}</title>{brand.tag_kepala()}{kepala_murid(css)}</head>'
        f'<body class="st">{bungkus_murid(topbar + "<main id=utama class=murid-kanvas-st>" + badan + "</main>")}'
        f'<script>{SKRIP_MATA_SANDI}</script></body></html>'
    ).encode("utf-8")


def halaman_pin(galat: str = "") -> bytes:
    """Form PIN saja (tirai tertutup): tanpa satu pun data anak."""
    form = (
        f'<form method="post" action="{RUTE_PIN}">{_field_pin("pin", "PIN Ayah/Bunda", "pin")}'
        f'{_tombol("Buka halaman")}</form>'
    )
    maskot = brand.maskot("gembok", 96, kelas="ortu-pin-maskot-st")
    badan = (
        '<div class="funnel-alur-st">' + _kepala() + _pesan("", galat)
        + f'<section class="ortu-kartu-st" id="ortu-pin-masuk">{maskot}<h2>{_e(COPY_PIN_MASUK_JUDUL)}</h2>'
        f'<p>{_e(COPY_PIN_MASUK_TEKS)}</p>{form}</section></div>'
    )
    return _dokumen(badan)


def _tautan_lanjut_cek() -> str:
    return (f'<a class="ortu-tombol-st ortu-tombol-pinggir-st" href="{RUTE_BERANDA_ANAK}">'
            f'{_e(COPY_CEK_LANJUT)}</a>')


def _blok_cek(hasil: dict, nama_anak: str) -> str:
    if hasil["status"] == "belum_mulai":
        isi = f'<p>{_e(COPY_CEK_BELUM)}</p>' + _tautan_lanjut_cek()
    elif hasil["status"] != "selesai":
        isi = f'<p>{_e(COPY_CEK_BELUM_SELESAI)}</p>' + _tautan_lanjut_cek()
    else:
        isi = (
            cek_pages._blok_kepala_hasil(hasil, nama_anak, None)
            + '<section class="funnel-ringkasan-st" aria-labelledby="judul-ringkasan">'
            '<h3 class="funnel-sub-judul-st" id="judul-ringkasan">Ringkasan awal</h3>'
            f'{cek_pages._blok_ringkasan(hasil["ringkasan"])}</section>'
        )
    return (f'<section class="ortu-kartu-st ortu-hasil-st" id="ortu-hasil-cek"><h2>{_e(COPY_CEK_JUDUL)}</h2>'
            f'{isi}</section>')


def _kartu_laporan_kosong() -> str:
    """Kartu sabar: satu kalimat. Satu-satunya tempat di halaman ini yang membawa maskot."""
    maskot = brand.maskot("membaca", C.UKURAN_MASKOT_BICARA, kelas="ceria-maskot")
    return (f'<section class="ortu-kartu-st ortu-kosong-st" id="ortu-laporan">{maskot}'
            f'<h2>{_e(COPY_LAPORAN_JUDUL)}</h2><p>{_e(COPY_LAPORAN_KOSONG)}</p></section>')


def _blok_laporan(laporan) -> str:
    if laporan is None:
        return _kartu_laporan_kosong()
    isi = parent_report_page.isi_laporan(
        nama=laporan["nama"], isi=laporan["isi"], catatan=laporan["catatan"], guru=laporan["guru"],
        periode=laporan["periode"], diterbitkan=laporan["diterbitkan"], judul_tag="h3",
        tanpa_batas_berlaku=True,
    )
    return f'<section class="ortu-kartu-st" id="ortu-laporan"><h2>{_e(COPY_LAPORAN_JUDUL)}</h2>{isi}</section>'


def _sudah_terbit(laporan_terbit: bool, purna) -> bool:
    return laporan_terbit or (purna is not None and purna.terbit is not None)


def _teks_lunas(terbit: bool) -> str:
    """Kalimat lunas: laporan sudah tersedia, atau sedang disiapkan (tanpa kata Guru)."""
    return COPY_PESANAN_TERBIT if terbit else COPY_PESANAN_DISIAPKAN


def _kalimat_potongan(nominal_bayar, purna) -> str:
    """Potongan hanya bila nominal lunas terbaca DAN voucher masih aktif; selain itu tanpa kalimat (tidak menebak)."""
    if nominal_bayar is None or purna is None or purna.voucher != VOUCHER_AKTIF:
        return ""
    return f'<p>{_e(COPY_POTONGAN % pesanan_transfer_pages.rupiah(nominal_bayar))}</p>'


def _opsi_kelas(nama: str, harga_rupiah) -> str:
    """Pilihan kelas sebagai tautan ke /murid/paket; tanpa angka bila harga tidak terbaca (galat baca)."""
    angka = (f'<span>{_e(pesanan_transfer_pages.rupiah(harga_rupiah))} <small>per bulan</small></span>'
             if harga_rupiah is not None else "")
    return f'<a class="ortu-opsi-kelas-st" href="{RUTE_PAKET}"><b>{_e(nama)}</b>{angka}</a>'


def _blok_kelas(nominal_bayar, purna, harga_kelas: dict) -> str:
    opsi = "".join(_opsi_kelas(nama, harga_kelas.get(kode)) for kode, nama in OPSI_KELAS)
    return (f'<div class="ortu-kelas-st">{_kalimat_potongan(nominal_bayar, purna)}{opsi}'
            f'<a class="ortu-tombol-st" href="{RUTE_PAKET}">{_e(COPY_DAFTAR_KELAS)}</a></div>')


def _kartu_lunas(purna, laporan_terbit: bool, tautan_paket: bool, harga_kelas: dict, nominal_bayar) -> str:
    """Setelah lunas (A2): chip, tautan ke blok laporan di halaman ini, dan pilihan kelas bila tautan paket aktif."""
    terbit = _sudah_terbit(laporan_terbit, purna)
    lencana = COPY_PESANAN_LUNAS_TERBIT if terbit else pesanan_pages.COPY_STATUS[pesanan_pages.STATUS_SUDAH_DIBAYAR][0]
    isi = C.lencana(lencana, "hijau") + f'<p>{_e(_teks_lunas(terbit))}</p>'
    if purna is not None:
        isi += f'<p>{_e(pesanan_voucher_pages.teks_janji(purna))}</p>' + _tautan_bayar(COPY_PESANAN_LIHAT_DEPOSIT)
    if laporan_terbit:
        isi += (f'<a class="ortu-tombol-st ortu-tombol-pinggir-st" href="#{peta_laporan_ortu_pages.ID_BLOK}">'
                f'{_e(COPY_BUKA_LAPORAN)}</a>')
    if tautan_paket:
        isi += _blok_kelas(nominal_bayar, purna, harga_kelas)
    return (f'<section class="ortu-kartu-st ortu-pesanan-st" id="ortu-pesanan"><h2>{_e(COPY_PESANAN_JUDUL)}</h2>'
            f'{isi}</section>')


def _blok_laporan_lama(laporan, status_pesanan) -> str:
    """Laporan Guru jalur lama. Kartu kosong tidak tampil bagi pesanan lunas (laporan Peta tanpa Guru)."""
    if laporan is None and status_pesanan == pesanan_pages.STATUS_SUDAH_DIBAYAR:
        return ""
    return _blok_laporan(laporan)


def _tautan_sekunder(tautan_paket: bool, tautan_langganan: bool) -> str:
    """Tautan kecil di kartu gelap: Lihat kelas (bila tautan paket aktif) dan Langganan (bila Latihan Harian aktif)."""
    tautan = []
    if tautan_paket:
        tautan.append(f'<a class="ortu-tautan-kecil-st" href="{RUTE_PAKET}">{_e(COPY_LIHAT_KELAS)}</a>')
    if tautan_langganan:
        tautan.append(f'<a class="ortu-tautan-kecil-st" href="{RUTE_LANGGANAN}">{_e(COPY_LANGGANAN)}</a>')
    return f'<div class="ortu-tautan-baris-pesanan-st">{"".join(tautan)}</div>' if tautan else ""


def _kartu_sebelum_bayar(status, tautan_paket: bool, tautan_langganan: bool) -> str:
    """Sebelum bayar (Usulan A): kartu gelap, harga sekali bayar, SATU tombol ke pesanan, tautan kecil bila aktif.

    `status` None untuk pembeli tanpa pesanan; untuk pesanan belum bayar, kedaluwarsa, atau ditolak, lencana
    statusnya ikut tampil, dan kalimat status ikut tampil untuk kedaluwarsa dan ditolak.
    """
    lencana = C.lencana(pesanan_pages.COPY_STATUS[status][0], "kuning") if status else ""
    kalimat = f'<p>{_e(pesanan_pages.COPY_STATUS[status][1])}</p>' if status in STATUS_PESANAN_KALIMAT_KARTU else ""
    harga = pesanan_transfer_pages.rupiah(pesanan_dasar.RUPIAH_PAKET)
    return (f'<section class="ceria-ortu ortu-pesanan-st" id="ortu-pesanan">{lencana}{kalimat}'
            f'<p class="ceria-alis">{_e(COPY_PESANAN_LANGKAH)}</p>'
            f'<h2 class="ceria-judul">{_e(COPY_PESANAN_JUDUL)}</h2>'
            f'<p class="ortu-harga-st"><b>{_e(harga)}</b> sekali bayar</p>'
            f'<p>{_e(COPY_PESANAN_HARGA_SUB)}</p>'
            f'<a class="ceria-tombol" href="{_e(_href_pesanan())}">{_e(COPY_PESANAN_BAYAR % harga)}</a>'
            f'<p class="ortu-tidak-kembali-st">{_e(COPY_PESANAN_TIDAK_KEMBALI)}</p>'
            f'{_tautan_sekunder(tautan_paket, tautan_langganan)}</section>')


def _kartu_status_tanpa_bayar(status: str) -> str:
    """Status yang tidak meminta pembeli membayar lagi (QA #1): lencana kuning, kalimat status, satu tautan status."""
    judul, kalimat = pesanan_pages.COPY_STATUS[status]
    return (f'<section class="ortu-kartu-st ortu-pesanan-st" id="ortu-pesanan"><h2>{_e(COPY_PESANAN_JUDUL)}</h2>'
            f'{C.lencana(judul, "kuning")}<p>{_e(kalimat)}</p>{_tautan_bayar(COPY_PESANAN_LIHAT_STATUS)}</section>')


def _blok_pesanan(status, cek_selesai: bool, purna=None, laporan_terbit: bool = False, *,
                  tautan_paket: bool = False, tautan_langganan: bool = False, harga_kelas=None,
                  nominal_bayar=None) -> str:
    """Kartu Peta Kemampuan di halaman orang tua (F1): sebelum bayar (gelap), setelah lunas (A2), atau status.

    `laporan_terbit`: True bila laporan Peta anak sudah terbit (`data.peta` ada); jangkar "Buka laporan lengkap" ikut.
    `purna` (`KeadaanPurna` atau None): janji terbit dan tautan rincian deposit bila ada.
    `tautan_paket` / `tautan_langganan`: tautan ke /murid/paket dan /murid/langganan hanya bila sakelarnya aktif.
    `harga_kelas` dan `nominal_bayar`: lihat `_kartu_lunas`; None berarti tanpa angka dan tanpa kalimat potongan.

    Tanpa pesanan dan cek belum selesai, kartu tidak tampil. Pesanan menunggu pemeriksaan tidak ditawari bayar lagi.
    """
    if status == pesanan_pages.STATUS_SUDAH_DIBAYAR:
        return _kartu_lunas(purna, laporan_terbit, tautan_paket, harga_kelas or {}, nominal_bayar)
    if status in STATUS_PESANAN_TANPA_TINDAKAN:
        return _kartu_status_tanpa_bayar(status)
    if status in STATUS_PESANAN_BUTUH_BAYAR:
        return _kartu_sebelum_bayar(status, tautan_paket, tautan_langganan)
    if cek_selesai:
        return _kartu_sebelum_bayar(None, tautan_paket, tautan_langganan)
    return ""


def _href_pesanan() -> str:
    import pesanan_permukaan
    return pesanan_permukaan.RUTE_MURID.status


def _tautan_bayar(teks: str) -> str:
    return f'<a class="ortu-tombol-st ortu-tombol-pinggir-st" href="{_e(_href_pesanan())}">{_e(teks)}</a>'


def _waktu_ramah(mulai_utc: str) -> str:
    """Waktu baku UTC jadwal sebagai 'Sen, 30 Nov 2026 · 15.00' (WIB)."""
    waktu = datetime.strptime(mulai_utc, aturan.FORMAT_WAKTU) + timedelta(hours=pesanan_transfer_pages.WIB_JAM)
    return f"{HARI_SINGKAT[waktu.weekday()]}, {format_tanggal.tanggal_pendek(waktu.date())}{PEMISAH_WAKTU}{waktu:%H.%M}"


def _baris_kehadiran(item: dict) -> str:
    status = STATUS_HADIR_TAMPIL.get(item.get("hadir"), COPY_BELUM_DICATAT)
    topik = f"<p>{_e(COPY_TOPIK % item['topik'])}</p>" if item.get("topik") else ""
    return f"<li><b>{_e(_waktu_ramah(item['mulai']))}</b><p>{_e(status)}</p>{topik}</li>"


def _blok_kehadiran(riwayat: list) -> str:
    if not riwayat:
        return ""
    baris = "".join(_baris_kehadiran(item) for item in riwayat)
    return (f'<section class="ortu-kartu-st" id="ortu-kehadiran"><h2>{_e(COPY_KEHADIRAN_JUDUL)}</h2>'
            f'<ul>{baris}</ul></section>')


def _baris_tugas(item: dict) -> str:
    tenggat = (f"<p>{_e(COPY_TENGGAT % format_tanggal.tanggal_dari_teks(item['tenggat']))}</p>"
               if item.get("tenggat") else "")
    if item["selesai"]:
        status, lewat = COPY_SELESAI % (item["benar"], item["total"]), ""
    else:
        status = COPY_BELUM_DIKERJAKAN
        lewat = (f"<p>{_e(COPY_LEWAT_TENGGAT)}</p>"
                 if item["status_tenggat"] == guru_tugas_aturan.TENGGAT_LEWAT else "")
    return f"<li><b>{_e(item['topik'])}</b>{tenggat}{lewat}<p>{_e(status)}</p></li>"


def _blok_tugas(tugas: list) -> str:
    if not tugas:
        return ""
    baris = "".join(_baris_tugas(item) for item in tugas)
    return (f'<section class="ortu-kartu-st" id="ortu-tugas"><h2>{_e(COPY_TUGAS_JUDUL)}</h2>'
            f'<ul>{baris}</ul></section>')


def _blok_guru(guru) -> str:
    """Kehadiran/jurnal dan tugas dari Guru (`orang_tua_guru.kumpulkan_guru`). Kosong bila `guru` None atau kedua daftar kosong."""
    if not guru:
        return ""
    return _blok_kehadiran(guru.get("kehadiran") or []) + _blok_tugas(guru.get("tugas") or [])


def _blok_harian(ringkas) -> str:
    """Kartu ringkasan Latihan Harian (F4); kosong bila sakelar mati (`ringkas` None)."""
    if ringkas is None:
        return ""
    import harian_pages
    return harian_pages.blok_orang_tua(ringkas)


def _form_atur(ada_pin: bool) -> str:
    return (
        f'<form method="post" action="{RUTE_ATUR}">'
        + _field_pin("pin-baru", "PIN baru (4 angka)", "pin") + _field_pin("pin-ulang", "Ulangi PIN", "pin_ulang")
        + _tombol("Ganti PIN" if ada_pin else "Pasang PIN") + "</form>"
    )


def _form_hapus() -> str:
    return (
        f'<form method="post" action="{RUTE_HAPUS}">'
        '<label class="ortu-konfirmasi-st"><input type="checkbox" name="konfirmasi" value="1" required>'
        f'<span>{_e(COPY_KONFIRMASI_HAPUS)}</span></label>{_tombol("Hapus PIN")}</form>'
    )


def _blok_pin(ada_pin: bool, terbuka: bool = False) -> str:
    """PIN dilipat dalam `<details>` native; `terbuka` membuka lipatan (umpan balik PIN terlihat). Form tak berubah."""
    status = COPY_PIN_ADA if ada_pin else COPY_PIN_TIDAK_ADA
    lencana = C.lencana(COPY_PIN_STATUS_ADA if ada_pin else COPY_PIN_STATUS_TIDAK_ADA, "hijau" if ada_pin else "kuning")
    forms = _form_atur(ada_pin) + (_form_hapus() if ada_pin else "")
    buka = " open" if terbuka else ""
    return (f'<details class="ortu-pin-st" id="ortu-pin"{buka}><summary><span>{_e(COPY_PIN_KARTU)}</span>{lencana}</summary>'
            f'<div class="ortu-pin-isi-st"><p>{_e(status)}</p>{forms}</div></details>')


def _tiga_angka(ringkas) -> str:
    """Hari latihan (dari 7), soal dikerjakan, persen tepat; semuanya dari `RingkasanHarian`, tanpa angka lain."""
    butir = ((f"{ringkas.jumlah_hari}/{len(C.HARI_PEKAN)}", "hari latihan"),
             (str(ringkas.soal_dikerjakan), "soal dikerjakan"), (harian_pages.teks_persen_tepat(ringkas), "tepat"))
    isi = "".join(f"<li><b>{_e(angka)}</b>{_e(nama)}</li>" for angka, nama in butir)
    return f'<ul class="ortu-tiga-st">{isi}</ul>'


def _hero_ringkasan(nama_anak: str, harian) -> str:
    """Hero teal "Halo, Ayah/Bunda" + nama anak; tiga angka hanya saat Latihan Harian aktif (`harian` bukan None)."""
    ringkasan = COPY_RINGKASAN_ANAK % nama_anak if nama_anak else COPY_RINGKASAN_UMUM
    isi = (f'<p class="ceria-alis-hero">{_e(COPY_ALIS)}</p>'
           f'<h1 id="judul-ortu" class="ortu-judul-hero-st">{_e(COPY_SAPAAN)}</h1><p>{_e(ringkasan)}</p>')
    return C.hero(isi + (_tiga_angka(harian) if harian is not None else ""))


def _kaki() -> str:
    return (f'<p class="ortu-kaki-st">{_e(COPY_PIN_CATATAN)}</p><p class="ortu-kaki-st">{_e(COPY_KALIMAT)}</p>')


def halaman_isi(data, ada_pin: bool, kabar: str = "", galat: str = "", *, tautan_paket: bool = False,
                masa_paket=(), tagihan_paket=(), kartu_kode: str = "", guru=None, harga_kelas=None) -> bytes:
    """Isi halaman (tirai terbuka atau anak tanpa PIN); `data` = `orang_tua_data.DataOrangTua`.

    Urutan: banner perpanjang Latihan Harian, banner tagihan Latihan Harian belum dibayar, banner paket belajar
    (hanya bila `tautan_paket`, isi `masa_paket`), hero ringkasan, hasil cek, pesanan Peta, Peta lengkap (bila terbit dan lunas), Latihan Harian, langganan, kartu paket belajar (hanya bila `tautan_paket`), kartu kode anak untuk guru (`kartu_kode`, kosong bila tidak tampil), laporan Guru, kehadiran dan jurnal serta tugas dari Guru (`guru`, kosong bila tidak tampil), PIN (lipat).
    """
    pin_terbuka = bool(KABAR.get(kabar) or galat)
    banner_paket = (kelas_pages.banner_tagihan(tagihan_paket, data.nama_anak)
                    + kelas_pages.banner_orang_tua(masa_paket, data.nama_anak)) if tautan_paket else ""
    badan = (
        '<div class="funnel-alur-st">' + _pesan(kabar, galat)
        + harian_langganan_pages.banner_orang_tua(data.langganan, data.nama_anak)
        + harian_langganan_pages.banner_tagihan(data.langganan)
        + banner_paket
        + _hero_ringkasan(data.nama_anak, data.harian)
        + _blok_cek(data.hasil_cek, data.nama_anak)
        + _blok_pesanan(data.status_pesanan, data.hasil_cek.get("status") == "selesai", data.purna,
                        data.peta is not None, tautan_paket=tautan_paket,
                        tautan_langganan=data.langganan is not None, harga_kelas=harga_kelas,
                        nominal_bayar=data.nominal_bayar)
        + peta_laporan_ortu_pages.blok_peta(data.peta)
        + _blok_harian(data.harian)
        + harian_langganan_pages.kartu_orang_tua(data.langganan) + (kelas_pages.kartu_orang_tua() if tautan_paket else "")
        + kartu_kode + _blok_laporan_lama(data.laporan, data.status_pesanan)
        + _blok_guru(guru) + _blok_pin(ada_pin, pin_terbuka) + _kaki() + "</div>"
    )
    return _dokumen(badan, ceria=True)
