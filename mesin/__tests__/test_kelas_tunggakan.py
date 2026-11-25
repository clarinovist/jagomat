"""Tunggakan paket kelas: anak yang paket bulanannya habis dan belum diperpanjang (data sintetis, baca-saja).

Aturan yang dikunci: jendela hari 30..120 sejak akses terakhir berakhir (dibulatkan ke bawah), order terbuka dari
akun mana pun menahan tunggakan, akses yang lebih baru menutupnya, satu item per (anak, paket), dan urutan
deterministik. Tabel kelas kosong berarti tidak ada tunggakan.
"""
from datetime import datetime, timedelta

import pytest

import kelas_kit as kk
import kelas_putusan
import kelas_tunggakan as kt
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

FORMAT = "%Y-%m-%dT%H:%M:%S"


def _lewat(waktu, *, hari=0, detik=0):
    return (datetime.strptime(waktu, FORMAT) + timedelta(days=hari, seconds=detik)).strftime(FORMAT)


def _berakhir(kon, siswa=1, paket="mini"):
    baris = kon.execute("SELECT MAX(a.berakhir) FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
                        "WHERE a.siswa_id=? AND o.paket=?", (siswa, paket)).fetchone()
    return baris[0]


def _lunas_berakhir(kon, siswa=1, paket="mini", n=1, *, sekarang=kk.KINI, putus=kk.SESUDAH_UPLOAD):
    kk.lunas(kon, siswa, paket, n, sekarang=sekarang, putus=putus)
    return _berakhir(kon, siswa, paket)


def _hari(daftar):
    return [t.hari_lewat for t in daftar]


# --- batas hari ----------------------------------------------------------------------------------

def test_tabel_kelas_kosong_tanpa_tunggakan(kon_kelas):
    assert kt.daftar_tunggakan(kon_kelas, kk.KINI) == ()


@pytest.mark.parametrize("hari,termasuk", [(29, False), (30, True), (59, True), (60, True), (120, True),
                                           (121, False)])
def test_batas_hari_tunggakan_30_sampai_120(kon_kelas, hari, termasuk):
    berakhir = _lunas_berakhir(kon_kelas)
    daftar = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=hari))
    assert _hari(daftar) == ([hari] if termasuk else [])


def test_hari_lewat_dibulatkan_ke_bawah(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas)
    tepat_sebelum_30 = _lewat(berakhir, hari=30, detik=-1)
    sebelum_hari_30 = kt.daftar_tunggakan(kon_kelas, tepat_sebelum_30)
    setelah_30_penuh = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=30, detik=86399))
    assert sebelum_hari_30 == ()
    assert _hari(setelah_30_penuh) == [30]


def test_tunggakan_membawa_nama_paket_siswa_dan_berakhir(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas, 7, "private")
    (item,) = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=45))
    assert item == kt.Tunggakan(7, "private", "Private", berakhir, 45)


# --- order terbuka dan perpanjangan ---------------------------------------------------------------

def test_belum_bayar_menahan_tunggakan_sampai_order_kedaluwarsa(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas)
    sekarang = _lewat(berakhir, hari=35)
    kk.tagih(kon_kelas, 1, "mini", sekarang=sekarang)
    assert kt.daftar_tunggakan(kon_kelas, _lewat(sekarang, detik=3600)) == ()
    assert _hari(kt.daftar_tunggakan(kon_kelas, _lewat(sekarang, hari=2))) == [37]


def test_bukti_menunggu_verifikasi_menahan_tunggakan(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas)
    sekarang = _lewat(berakhir, hari=35)
    kk.menunggu(kon_kelas, 1, "mini", 2, sekarang=sekarang, unggah_pada=_lewat(sekarang, detik=600))
    assert kt.daftar_tunggakan(kon_kelas, _lewat(sekarang, hari=2)) == ()


def test_bukti_ditolak_yang_masih_terbuka_menahan_tunggakan(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas)
    sekarang = _lewat(berakhir, hari=35)
    tagihan, bukti = kk.menunggu(kon_kelas, 1, "mini", 2, sekarang=sekarang, unggah_pada=_lewat(sekarang, detik=600))
    kelas_putusan.tolak(kon_kelas, tagihan.order_id, kk.ADMIN, "Nominal tidak cocok",
                        _lewat(sekarang, detik=1200), bukti_dilihat=bukti)
    assert kt.daftar_tunggakan(kon_kelas, _lewat(sekarang, detik=3600)) == ()
    assert _hari(kt.daftar_tunggakan(kon_kelas, _lewat(sekarang, hari=2))) == [37]


def test_perpanjangan_menyambung_menutup_tunggakan_akses_lama(kon_kelas):
    berakhir1 = _lunas_berakhir(kon_kelas)
    sekarang = _lewat(berakhir1, hari=-5)
    kk.lunas(kon_kelas, 1, "mini", 2, sekarang=sekarang, putus=_lewat(sekarang, detik=600))
    berakhir2 = _berakhir(kon_kelas)
    assert berakhir2 > berakhir1
    # Akses lama sudah 40 hari lewat, tetapi akses terakhir (berakhir2) belum; tidak boleh muncul.
    assert kt.daftar_tunggakan(kon_kelas, _lewat(berakhir1, hari=40)) == ()
    # Hari dihitung dari akses terakhir, bukan dari akses lama.
    assert _hari(kt.daftar_tunggakan(kon_kelas, _lewat(berakhir2, hari=35))) == [35]


# --- satu item per (anak, paket) dan urutan --------------------------------------------------------

def test_dua_paket_pada_anak_sama_masing_masing_satu_item(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas, 1, "mini")
    _lunas_berakhir(kon_kelas, 1, "private", n=2)
    daftar = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=40))
    assert [(t.siswa_id, t.kode_paket, t.hari_lewat) for t in daftar] == [(1, "mini", 40), (1, "private", 40)]


def test_pindah_paket_tidak_menandai_paket_lama(kon_kelas):
    berakhir_private = _lunas_berakhir(kon_kelas, 1, "private")
    berakhir_mini = _lunas_berakhir(kon_kelas, 1, "mini", n=2, putus=_lewat(kk.SESUDAH_UPLOAD, hari=3))
    assert berakhir_mini > berakhir_private
    daftar = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir_private, hari=40))
    assert [(t.kode_paket, t.hari_lewat) for t in daftar] == [("mini", 37)]


def test_urut_hari_lalu_turun_lalu_anak_lalu_paket(kon_kelas):
    berakhir = _lunas_berakhir(kon_kelas, 1, "mini")
    _lunas_berakhir(kon_kelas, 1, "private", n=2)
    berakhir_anak2 = _lunas_berakhir(kon_kelas, 2, "mini", n=3, putus=_lewat(kk.SESUDAH_UPLOAD, hari=2))
    daftar = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=40))
    assert berakhir_anak2 == _lewat(berakhir, hari=2)
    assert [(t.siswa_id, t.kode_paket, t.hari_lewat) for t in daftar] == [
        (1, "mini", 40), (1, "private", 40), (2, "mini", 38)]


def test_hari_sama_diurutkan_anak_lalu_paket(kon_kelas):
    _lunas_berakhir(kon_kelas, 2, "mini", n=1)
    berakhir = _lunas_berakhir(kon_kelas, 1, "private", n=2)
    _lunas_berakhir(kon_kelas, 1, "mini", n=3)
    daftar = kt.daftar_tunggakan(kon_kelas, _lewat(berakhir, hari=40))
    assert [(t.siswa_id, t.kode_paket) for t in daftar] == [(1, "mini"), (1, "private"), (2, "mini")]
