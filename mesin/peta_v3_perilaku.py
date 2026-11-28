"""Kartu "Perilaku belajar" laporan Peta versi 3 (F6): empat kebiasaan dari data soal, bukan dari penilaian anak.

Ketekunan dibaca dari soal dilewati; Fokus sampai akhir dari benar pada soal terakhir; Saat soal sulit dari jawaban
salah yang dijawab terlalu cepat (dan materinya); Memeriksa ulang dari jumlah jawaban yang diganti. Setiap status
ditentukan aturan di `peta_v3_aturan` dan ditulis sebagai teks, jadi tidak hanya warna. Tanpa penilaian karakter.
"""
from __future__ import annotations

import peta_ikon
import peta_laporan_snapshot as snap
import peta_v3_aturan as aturan
from peta_v3_html import e, kartu

COPY_JUDUL = "Perilaku belajar"
COPY_SUB = "Kebiasaan anak saat mengerjakan, dibaca dari rekaman %d soal."
COPY_KETEKUNAN = "Ketekunan"
COPY_KETEKUNAN_SEMUA = "Mencoba semua %d soal, tidak ada yang dilewati."
COPY_KETEKUNAN_LEWAT = "%d soal dilewati."
COPY_FOKUS = "Fokus sampai akhir"
COPY_FOKUS_ISI = "%d dari %d soal terakhir benar."
COPY_SULIT = "Saat soal sulit"
COPY_SULIT_TIDAK = "Tidak ada jawaban salah yang dijawab di bawah %d detik."
COPY_SULIT_ISI = "%d soal salah dijawab di bawah %d detik%s."
COPY_SULIT_SEMUA = ", semuanya di materi yang belum dikuasai"
COPY_SULIT_SEBAGIAN = ", %d di antaranya di materi yang belum dikuasai"
COPY_PERIKSA = "Memeriksa ulang"
COPY_PERIKSA_TIDAK = "Tidak ada jawaban yang diganti."
COPY_PERIKSA_ISI = "Mengubah jawaban %d kali, paling banyak %d kali di satu soal."
IKON = {
    "ketekunan": "bintang",
    "fokus": "panah-atas",
    "sulit": "cari",
    "periksa": "cek",
}
UKURAN_IKON = 18
TEBAL_IKON = "2.4"


def _kartu_perilaku(kunci: str, judul: str, status: tuple, kalimat: str) -> str:
    label, nada = status
    return (f'<li class="ortu-peta-v3-perilaku-item-st">'
            f'<span class="ortu-peta-v3-atas-p-st"><span class="ortu-peta-v3-ik-st">'
            f'{peta_ikon.ikon(IKON[kunci], UKURAN_IKON, TEBAL_IKON)}</span><b>{e(judul)}</b></span>'
            f'<span class="ortu-peta-v3-status-st ortu-peta-v3-{nada}-st">{e(label)}</span>'
            f'<p>{e(kalimat)}</p></li>')


def _kalimat_ketekunan(dilewati: int, jumlah: int) -> str:
    if dilewati == 0:
        return COPY_KETEKUNAN_SEMUA % jumlah
    return COPY_KETEKUNAN_LEWAT % dilewati


def _kalimat_sulit(jumlah_cepat: int, lemah: int, semua_dikenal: bool) -> str:
    if jumlah_cepat == 0:
        return COPY_SULIT_TIDAK % snap.AMBANG_CEPAT_DETIK
    if lemah == jumlah_cepat and semua_dikenal:
        tambahan = COPY_SULIT_SEMUA
    elif lemah > 0:
        tambahan = COPY_SULIT_SEBAGIAN % lemah
    else:
        tambahan = ""
    return COPY_SULIT_ISI % (jumlah_cepat, snap.AMBANG_CEPAT_DETIK, tambahan)


def _kalimat_periksa(total_ganti: int, maks_ganti: int) -> str:
    if total_ganti == 0:
        return COPY_PERIKSA_TIDAK
    return COPY_PERIKSA_ISI % (total_ganti, maks_ganti)


def bagian_perilaku(isi: dict, daftar_berstatus: list) -> str:
    """Kartu empat perilaku dari butir soal versi 3 dan ringkasan jumlah cepat, ganti, dan dilewati."""
    soal = isi["soal"]
    jendela_benar, jendela = aturan.benar_di_akhir(soal)
    lemah, semua_dikenal = aturan.soal_cepat_di_materi_lemah(soal, daftar_berstatus)
    total_ganti = sum(butir["ganti"] for butir in soal)
    maks_ganti = max((butir["ganti"] for butir in soal), default=0)
    item = "".join([
        _kartu_perilaku("ketekunan", COPY_KETEKUNAN, aturan.status_ketekunan(isi["dilewati"]),
                        _kalimat_ketekunan(isi["dilewati"], isi["jumlah_soal"])),
        _kartu_perilaku("fokus", COPY_FOKUS, aturan.status_fokus_akhir(jendela_benar, jendela),
                        COPY_FOKUS_ISI % (jendela_benar, jendela)),
        _kartu_perilaku("sulit", COPY_SULIT, aturan.status_saat_sulit(isi["jumlah_cepat"]),
                        _kalimat_sulit(isi["jumlah_cepat"], lemah, semua_dikenal)),
        _kartu_perilaku("periksa", COPY_PERIKSA, aturan.status_periksa_ulang(total_ganti),
                        _kalimat_periksa(total_ganti, maks_ganti)),
    ])
    return kartu("ortu-peta-v3-h-perilaku", COPY_JUDUL,
                 f'<p class="ortu-peta-v3-sub-st">{e(COPY_SUB % isi["jumlah_soal"])}</p>'
                 f'<ul class="ortu-peta-v3-perilaku-st">{item}</ul>')
