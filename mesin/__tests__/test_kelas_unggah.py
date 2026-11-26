"""Catat bukti ke tagihan terbuka per (akun, anak, paket) lewat `kelas_store.catat_bukti` (butir QA #3; data sintetis, domain).

Tagihan dipilih dari kode paket di dalam transaksi tulis. Akun lain, anak lain, dan paket tanpa tagihan terbuka identik
(KelasKonflik tanpa tulis). Kasus dua tagihan berdampingan ada di `test_kelas_unggah_order.py`.
"""
import pytest

import kelas_dasar as k
import kelas_kit as kk
import kelas_store as store
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

AKUN = kk.AKUN_A
SESUDAH = "2026-11-20T10:00:00"


def _catat(kon, n=1, siswa=1, akun=AKUN, paket="mini", sekarang=SESUDAH):
    return store.catat_bukti(kon, akun, siswa, paket, kk.MIME, kk.UKURAN, kk.sha(n), kk.berkas(n), sekarang)


def _bukti(kon):
    return [(b["order_id"],) for b in kon.execute("SELECT order_id FROM kelas_bukti ORDER BY id")]


def test_bukti_masuk_ke_tagihan_terbuka_dan_status_menunggu(kon_kelas):
    tagihan = kk.tagih(kon_kelas, paket="mini")
    hasil = _catat(kon_kelas)
    assert hasil["baru"] is True and hasil["status"] == k.STATUS_MENUNGGU
    assert _bukti(kon_kelas) == [(tagihan.order_id,)]


def test_tanpa_tagihan_terbuka_atau_milik_akun_lain_konflik_tanpa_tulis(kon_kelas):
    with pytest.raises(k.KelasKonflik):
        _catat(kon_kelas)
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(k.KelasKonflik):
        _catat(kon_kelas, akun=kk.AKUN_B)
    assert _bukti(kon_kelas) == []


def test_jendela_bayar_habis_konflik(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(k.KelasKonflik):
        _catat(kon_kelas, sekarang=kk.SESUDAH_JENDELA)


def test_berkas_sama_menunggu_mengembalikan_bukti_yang_ada(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    pertama = _catat(kon_kelas)
    kedua = _catat(kon_kelas)
    assert kedua["baru"] is False and kedua["bukti_id"] == pertama["bukti_id"] and len(_bukti(kon_kelas)) == 1


def test_berkas_yang_sudah_dipakai_tagihan_lain_ditolak(kon_kelas):
    kk.tagih(kon_kelas, siswa=1, paket="mini")
    kk.tagih(kon_kelas, siswa=2, paket="mini", akun=kk.AKUN_B)
    _catat(kon_kelas, n=1, siswa=1)
    with pytest.raises(k.KelasKonflik):
        _catat(kon_kelas, n=1, siswa=2, akun=kk.AKUN_B)
    assert len(_bukti(kon_kelas)) == 1


def test_batas_bukti_tercapai_melempar_batas_bukti(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    for n in range(1, k.MAKS_BUKTI + 1):
        _catat(kon_kelas, n=n)
    with pytest.raises(k.BatasBukti):
        _catat(kon_kelas, n=k.MAKS_BUKTI + 1)
    assert len(_bukti(kon_kelas)) == k.MAKS_BUKTI


def test_metadata_tidak_sah_ditolak_sebelum_db(kon_kelas):
    kk.tagih(kon_kelas, paket="mini")
    with pytest.raises(Exception):
        store.catat_bukti(kon_kelas, AKUN, 1, "mini", "text/html", kk.UKURAN, kk.sha(1), kk.berkas(1), SESUDAH)
    assert _bukti(kon_kelas) == []
