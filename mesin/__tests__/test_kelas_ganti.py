"""Ganti paket saat tagihan belum dibayar (butir QA #3, 25 Nov 2026; data sintetis, tingkat domain).

Ledger immutable: ganti = tagihan baru untuk paket lain, tagihan lama dibiarkan terbuka sampai kedaluwarsa (halaman
pembeli memakai yang terbaru; lihat test_kelas_ganti_http). Invarian: paling banyak dua tagihan terbuka per anak dan
hanya lewat ganti, nominal dari katalog di server, deposit Peta pindah, tanpa bukti di tagihan lama, atomik.
"""
import pytest

import harga
import kelas_dasar as k
import kelas_ganti as G
import kelas_kit as kk
import kelas_status as ks
import paket_belajar_katalog as katalog
import pesanan_dasar as d
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

AKUN = kk.AKUN_A
SESUDAH = "2026-11-20T10:00:00"   # satu jam setelah kk.KINI: jendela 24 jam tagihan awal masih terbuka


def _terbuka(kon, siswa=1, kini=SESUDAH):
    """(paket, status) terbaru dulu."""
    return [(o["paket"], status) for o, _f, status in ks.order_terbuka_siswa(kon, AKUN, siswa, kini)]


def _jumlah_order(kon):
    return kon.execute("SELECT COUNT(*) FROM kelas_order").fetchone()[0]


def _ganti(kon, paket, siswa=1, sekarang=SESUDAH, akun=AKUN):
    return G.ganti_paket(kon, akun, siswa, paket, sekarang, acak=kk.pilih_pertama)


def test_ganti_menulis_tagihan_baru_dan_yang_terbaru_didahulukan(kon_kelas):
    lama = kk.tagih(kon_kelas, paket="mini")
    baru = _ganti(kon_kelas, "private")
    assert (baru.kode_paket, baru.status) == ("private", k.STATUS_BELUM_BAYAR) and baru.order_id != lama.order_id
    assert _terbuka(kon_kelas) == [("private", k.STATUS_BELUM_BAYAR), ("mini", k.STATUS_BELUM_BAYAR)]
    assert _jumlah_order(kon_kelas) == 2


def test_tagihan_terbaru_menang_juga_saat_waktu_buat_sama(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    baru = _ganti(kon_kelas, "private", sekarang=kk.KINI)   # waktu buat identik: urutan sisip yang menentukan
    (pertama, *_), = [[o["id"] for o, _f, _s in ks.order_terbuka_siswa(kon_kelas, AKUN, 1, kk.KINI)]]
    assert pertama == baru.order_id


def test_nominal_baru_dari_katalog_server_dan_kode_unik_beda(kon_kelas):
    lama = kk.tagih(kon_kelas, paket="mini")
    baru = _ganti(kon_kelas, "private")
    harapan = katalog.hitung_rincian("private", deposit_aktif=False, harga_paket=harga.harga_aktif(kon_kelas, "private"))
    assert baru.rincian.nominal == harapan.nominal and baru.total == harapan.nominal + baru.kode_unik
    assert baru.total != lama.total


def test_deposit_peta_ikut_ke_tagihan_baru(kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    lama = kk.tagih(kon_kelas, paket="mini", sekarang=kk.SEKARANG)
    assert lama.rincian.potongan_deposit == katalog.RUPIAH_DEPOSIT
    baru = _ganti(kon_kelas, "private", sekarang=kk.SEKARANG)
    assert baru.rincian.potongan_deposit == katalog.RUPIAH_DEPOSIT


def test_paket_sama_ditolak_tanpa_tulis(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "mini")
    assert _jumlah_order(kon_kelas) == 1


def test_sudah_ada_bukti_ditolak_tanpa_tulis(kon_kelas):
    kk.menunggu(kon_kelas, paket="mini")
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "private", sekarang=kk.SESUDAH_UPLOAD)
    assert _jumlah_order(kon_kelas) == 1


def test_tanpa_tagihan_atau_sudah_kedaluwarsa_ditolak(kon_kelas):
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "private")
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "private", sekarang=kk.SESUDAH_JENDELA)
    assert _jumlah_order(kon_kelas) == 1


def test_akun_lain_dan_paket_asing_ditolak(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(d.PesananTidakDitemukan):
        _ganti(kon_kelas, "private", akun=kk.AKUN_B)
    with pytest.raises(d.PesananDataTidakSah):
        _ganti(kon_kelas, "paket-asing")
    assert _jumlah_order(kon_kelas) == 1


def test_ganti_kedua_dan_kembali_ke_paket_semula_ditolak_sampai_tagihan_lama_habis(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    _ganti(kon_kelas, "private")
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "mini")        # sudah ada dua tagihan terbuka
    with pytest.raises(k.KelasKonflik):
        _ganti(kon_kelas, "private")
    assert _jumlah_order(kon_kelas) == 2
    # Setelah tagihan lama habis, hanya tagihan terbaru yang terbuka dan boleh diganti lagi.
    lewat_lama = "2026-11-21T09:30:00"   # lama (KINI+24j) habis; baru (SESUDAH+24j) masih terbuka
    assert _terbuka(kon_kelas, kini=lewat_lama) == [("private", k.STATUS_BELUM_BAYAR)]
    assert _ganti(kon_kelas, "mini", sekarang=lewat_lama).kode_paket == "mini"
