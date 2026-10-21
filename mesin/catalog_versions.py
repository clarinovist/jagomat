"""Versi konten katalog: writer opt-in, reader parameter historis tetap murni."""
import os
from dataclasses import replace
from functools import wraps


# Jembatan reader dahulu. Aktivasi writer memerlukan review konten dan pair exact.
VERSI_KATALOG_BAWAAN = 1
TEMPLATE_DIPERBAIKI = frozenset({"soal_umur", "perbandingan_senilai",
    "perbandingan_berbalik", "kerja_bersama", "lingkaran_keliling_luas", "juring", "paritas",
    "rata_rata_gabungan", "median_modus", "diagram_batang_garis", "tabel_turus", "piktogram",
    "jangkauan_data", "jumlah_selisih", "fpb_dua_bilangan", "volume_prisma_tabung",
    "unsur_bangun", "perbandingan_volume", "skala_peta", "jam_menit_detik",
    "jaring_jaring", "benar_salah_pengandaian", "jumlah_deret", "luas_kotak_satuan",
    "satuan_konversi", "korek_api"})


def versi_writer():
    """Konfigurasi hanya untuk soal baru, tidak untuk rekonstruksi bank lama."""
    nilai = os.environ.get("OSN_KATALOG_VERSI", str(VERSI_KATALOG_BAWAAN)).strip()
    if nilai not in {"1", "2"}:
        raise ValueError("OSN_KATALOG_VERSI hanya menerima 1 atau 2")
    return int(nilai)


def soal_berversi(perbaiki):
    """Tanpa marker, jalankan fungsi historis persis; jangan baca flag writer."""
    def bungkus(lama):
        @wraps(lama)
        def panggil(*args, versi_katalog=1, **kwargs):
            if type(versi_katalog) is not int or versi_katalog not in (1, 2):
                raise ValueError("versi katalog tidak didukung")
            if versi_katalog == 1:
                return lama(*args, **kwargs)
            soal = perbaiki(*args, **kwargs)
            return replace(soal, parameter={**soal.parameter, "versi_katalog": 2})
        return panggil
    return bungkus


def koreksi_soal(perbaiki):
    """Pertahankan konstruksi teks lama, koreksi hasil hanya untuk konten baru."""
    def bungkus(lama):
        @wraps(lama)
        def baru(*args, **kwargs):
            return perbaiki(lama(*args, **kwargs))
        return soal_berversi(baru)(lama)
    return bungkus


def parameter_visual(template_id, parameter, didukung):
    """Marker konten tervalidasi bukan field geometri publik; field lain tetap ketat."""
    if "versi_katalog" not in parameter:
        return parameter
    if (type(parameter["versi_katalog"]) is not int or parameter["versi_katalog"] != 2
            or template_id not in didukung):
        raise ValueError("versi katalog visual tidak didukung")
    return {k: v for k, v in parameter.items() if k != "versi_katalog"}


def parameter_baru(lama):
    """Tambahkan identitas konten hanya pada template yang sudah diperbaiki."""
    @wraps(lama)
    def parameter(template_id, rng, level):
        versi = versi_writer()
        hasil = lama(template_id, rng, level)
        if versi == 2 and template_id in TEMPLATE_DIPERBAIKI:
            if template_id in {"jaring_jaring", "perbandingan_volume", "skala_peta", "jam_menit_detik"}:
                if hasil.get("versi") != 2:
                    raise ValueError("katalog baru memerlukan writer matematika versi 2")
            if (template_id == "volume_prisma_tabung" and hasil.get("varian", "").startswith("tabung")
                    and hasil.get("versi") != 2):
                raise ValueError("katalog tabung memerlukan writer matematika versi 2")
            return {**hasil, "versi_katalog": 2}
        return hasil
    return parameter
