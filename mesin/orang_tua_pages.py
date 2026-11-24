"""Render halaman orang tua di akun murid: form PIN tirai dan isi baca-saja.

Murni render (tanpa DB, tanpa token). Pakai ulang blok hasil cek (`cek_pages`), renderer laporan Guru
(`parent_report_page.isi_laporan`), dan teks status pesanan (`pesanan_pages.COPY_STATUS`). Tanpa JS baru:
satu-satunya skrip adalah `SKRIP_MATA_SANDI` yang sudah disetujui (toggle mata untuk PIN).

DILARANG di halaman ini: kunci jawaban, malrule, kode diagnosis, pembahasan soal, dan kontak orang tua
(nomor WhatsApp tidak pernah dirender; hanya kalimat bahwa perubahan lewat tim). Cek: skor dan kategori boleh.
"""
from __future__ import annotations

import html

import brand
import cek_gratis_skor
import cek_pages
import harian_langganan_pages
import harian_pages
import playful_components as C
import parent_report_page
import pesanan_pages
import pesanan_voucher_pages
import peta_laporan_ortu_pages
from funnel_style import GAYA_FUNNEL
from murid_shell import PANAH_KEMBALI, aksi_topbar, bungkus_murid, kepala_murid, topbar_murid
from orang_tua_style import GAYA_ORTU, RUTE
from parent_report_page import GAYA_LO
from playful_style import GAYA_CERIA
from style_stitch import gaya_stitch
from teacher_style import SKRIP_MATA_SANDI

RUTE_PIN = RUTE + "/pin"
RUTE_ATUR = RUTE_PIN + "/atur"
RUTE_HAPUS = RUTE_PIN + "/hapus"

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
COPY_LAPORAN_JUDUL = "Laporan dari Guru"
COPY_LAPORAN_KOSONG = "Belum ada laporan dari Guru."
COPY_PESANAN_JUDUL = "Peta Kemampuan"
COPY_PESANAN_TAWARAN = "Laporan lengkap dikerjakan guru dari hasil cek ini. " + __import__("funnel_pages").COPY_HARGA
COPY_PESANAN_LANJUT = "Lanjutkan pembayaran atau lihat statusnya di halaman pembayaran."
COPY_PESANAN_TERBIT = "Pembayaran diterima. Laporan Peta Kemampuan sudah tersedia di halaman ini."
COPY_PESANAN_LIHAT_DEPOSIT = "Lihat deposit & rincian pesanan"
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


def _blok_cek(hasil: dict, nama_anak: str) -> str:
    if hasil["status"] == "belum_mulai":
        isi = f'<p>{_e(COPY_CEK_BELUM)}</p>'
    elif hasil["status"] != "selesai":
        isi = f'<p>{_e(COPY_CEK_BELUM_SELESAI)}</p>'
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


def _blok_pesanan(status, cek_selesai: bool, purna=None) -> str:
    """Status Peta Kemampuan (lencana teks) + satu pintu ke halaman pembayaran/pesanan akun anak (F2c).

    `purna` (`KeadaanPurna` atau None): bila ada, SATU baris janji terbit / status laporan serta tautan
    ke `/murid/pesanan` untuk melihat kartu deposit & rincian pesanan (tanpa tombol form).

    Kalimat instruksi bayar (mis. "Pindai kode QRIS") tidak diulang di sini: jalur aktif (transfer/QRIS) hanya
    dijelaskan di halaman pembayaran. Tanpa cek selesai dan tanpa pesanan, kartu tidak tampil.
    """
    if status in pesanan_pages.COPY_STATUS:
        judul, kalimat = pesanan_pages.COPY_STATUS[status]
        sudah = status == pesanan_pages.STATUS_SUDAH_DIBAYAR
        teks = (COPY_PESANAN_TERBIT if sudah and purna is not None and purna.terbit is not None
                else kalimat if sudah else COPY_PESANAN_LANJUT)
        isi = C.lencana(judul, "hijau" if sudah else "kuning") + f'<p>{_e(teks)}</p>'
        tombol = "" if sudah else _tautan_bayar("Buka halaman pembayaran")
        if sudah and purna is not None:
            isi += f'<p>{_e(pesanan_voucher_pages.teks_janji(purna))}</p>'
            tombol = _tautan_bayar(COPY_PESANAN_LIHAT_DEPOSIT)
    elif cek_selesai:
        isi = f'<p>{_e(COPY_PESANAN_TAWARAN)}</p>'
        tombol = _tautan_bayar("Lanjut ke pembayaran")
    else:
        return ""
    return (f'<section class="ortu-kartu-st ortu-pesanan-st" id="ortu-pesanan"><h2>{_e(COPY_PESANAN_JUDUL)}</h2>'
            f'{isi}{tombol}</section>')


def _tautan_bayar(teks: str) -> str:
    import pesanan_permukaan
    return (f'<a class="ortu-tombol-st ortu-tombol-pinggir-st" '
            f'href="{_e(pesanan_permukaan.RUTE_MURID.status)}">{_e(teks)}</a>')


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


def halaman_isi(data, ada_pin: bool, kabar: str = "", galat: str = "") -> bytes:
    """Isi halaman (tirai terbuka atau anak tanpa PIN); `data` = `orang_tua_data.DataOrangTua`.

    Urutan: banner perpanjang, hero ringkasan, hasil cek, Peta lengkap (bila terbit dan lunas), Latihan Harian, langganan, laporan Guru, Peta, PIN (lipat).
    """
    pin_terbuka = bool(KABAR.get(kabar) or galat)
    badan = (
        '<div class="funnel-alur-st">' + _pesan(kabar, galat)
        + harian_langganan_pages.banner_orang_tua(data.langganan, data.nama_anak)
        + _hero_ringkasan(data.nama_anak, data.harian)
        + _blok_cek(data.hasil_cek, data.nama_anak) + peta_laporan_ortu_pages.blok_peta(data.peta)
        + _blok_harian(data.harian)
        + harian_langganan_pages.kartu_orang_tua(data.langganan) + _blok_laporan(data.laporan)
        + _blok_pesanan(data.status_pesanan, data.hasil_cek.get("status") == "selesai", data.purna)
        + _blok_pin(ada_pin, pin_terbuka) + _kaki() + "</div>"
    )
    return _dokumen(badan, ceria=True)
