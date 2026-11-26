"""Unggah bukti memilih tagihan lewat KODE PAKET saat dua tagihan terbuka berdampingan (domain; data sintetis).

Tagihan diturunkan dari (akun, anak, paket) di dalam transaksi tulis (`kelas_store.catat_bukti`). Akun lain, anak lain, paket
tanpa tagihan terbuka, dan tagihan yang tidak terbuka menghasilkan KelasKonflik yang identik tanpa tulis. Kode asing ditolak
sebelum menyentuh DB.
"""
import pytest

import kelas_dasar as k
import kelas_kit as kk
import kelas_store as store
import pesanan_dasar as d
from tagihan_kit import db_tagihan, kon_tagihan  # noqa: F401

AKUN = kk.AKUN_A
AKUN_LAIN = kk.AKUN_B
MINI, PRIVATE = "mini", "private"
PESAN_TANPA_TAGIHAN = "anak tidak punya tagihan paket yang menerima bukti"


def _unggah(kon, kode, *, akun=AKUN, siswa=1, n=1, sekarang=kk.SESUDAH_UPLOAD):
    return store.catat_bukti(kon, akun, siswa, kode, kk.MIME, kk.UKURAN, kk.sha(n), kk.berkas(n), sekarang)


def _bukti(kon):
    return [tuple(r) for r in kon.execute("SELECT order_id FROM kelas_bukti ORDER BY id")]


def _galat(fungsi):
    try:
        fungsi()
    except Exception as galat:  # noqa: BLE001 - tes ini membandingkan jenis dan pesan galat apa adanya
        return type(galat), str(galat)
    raise AssertionError("tidak melempar galat")


def _sql_dijalankan(kon, fungsi):
    jejak = []
    kon.set_trace_callback(jejak.append)
    try:
        fungsi()
    except d.PesananError:
        pass
    finally:
        kon.set_trace_callback(None)
    return jejak


# --- pemilihan tagihan berdasarkan kode paket -----------------------------------------------------

def test_bukti_untuk_mini_masuk_ke_tagihan_mini_bukan_private(kon_tagihan):
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    mini = kk.tagih(kon_tagihan, 1, MINI)          # tagihan terbaru: bukti TIDAK boleh jatuh ke sini
    hasil = _unggah(kon_tagihan, MINI)
    assert hasil["baru"] is True and hasil["status"] == k.STATUS_MENUNGGU
    assert _bukti(kon_tagihan) == [(mini.order_id,)]
    assert private.order_id not in {r[0] for r in _bukti(kon_tagihan)}


def test_bukti_untuk_private_masuk_ke_tagihan_private_walau_mini_terbaru(kon_tagihan):
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    kk.tagih(kon_tagihan, 1, MINI)
    _unggah(kon_tagihan, PRIVATE)
    assert _bukti(kon_tagihan) == [(private.order_id,)]


def test_tagihan_lain_tetap_belum_bayar_setelah_bukti_paket_lain(kon_tagihan):
    kk.tagih(kon_tagihan, 1, PRIVATE)
    mini = kk.tagih(kon_tagihan, 1, MINI)
    _unggah(kon_tagihan, MINI)
    kon_tagihan.commit()
    sisa = store.tagihan_terbuka(kon_tagihan, AKUN, 1, PRIVATE, kk.SESUDAH_UPLOAD)
    assert sisa is not None and sisa.status == k.STATUS_BELUM_BAYAR
    assert store.tagihan_terbuka(kon_tagihan, AKUN, 1, MINI, kk.SESUDAH_UPLOAD).status == k.STATUS_MENUNGGU
    assert mini.order_id != sisa.order_id


def test_berkas_kembar_menunggu_pada_paket_yang_sama_mengembalikan_bukti_yang_ada(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    pertama = _unggah(kon_tagihan, MINI)
    kedua = _unggah(kon_tagihan, MINI)
    assert kedua == {"bukti_id": pertama["bukti_id"], "status": k.STATUS_MENUNGGU, "baru": False}
    assert len(_bukti(kon_tagihan)) == 1


# --- kode tanpa tagihan terbuka dan kepemilikan ---------------------------------------------------

def test_kode_tanpa_tagihan_terbuka_konflik_tanpa_tulis(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    sebelum = kon_tagihan.total_changes
    assert _galat(lambda: _unggah(kon_tagihan, PRIVATE)) == (k.KelasKonflik, PESAN_TANPA_TAGIHAN)
    assert kon_tagihan.total_changes == sebelum and _bukti(kon_tagihan) == []


def test_akun_lain_identik_dengan_tanpa_tagihan_tanpa_tulis(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    sebelum = kon_tagihan.total_changes
    milik_lain = _galat(lambda: _unggah(kon_tagihan, MINI, akun=AKUN_LAIN))
    tanpa_tagihan = _galat(lambda: _unggah(kon_tagihan, PRIVATE))
    assert milik_lain == tanpa_tagihan == (k.KelasKonflik, PESAN_TANPA_TAGIHAN)
    assert kon_tagihan.total_changes == sebelum and _bukti(kon_tagihan) == []


def test_anak_lain_pada_akun_sama_identik_dengan_tanpa_tagihan(kon_tagihan):
    kk.tagih(kon_tagihan, 2, MINI)
    sebelum = kon_tagihan.total_changes
    anak_lain = _galat(lambda: _unggah(kon_tagihan, MINI, siswa=1))
    assert anak_lain == (k.KelasKonflik, PESAN_TANPA_TAGIHAN)
    assert kon_tagihan.total_changes == sebelum and _bukti(kon_tagihan) == []


def test_tagihan_lunas_menolak_bukti_tanpa_tulis(kon_tagihan):
    kk.lunas(kon_tagihan, 1, MINI)
    sebelum = kon_tagihan.total_changes
    assert _galat(lambda: _unggah(kon_tagihan, MINI, n=2))[0] is k.KelasKonflik
    assert kon_tagihan.total_changes == sebelum


def test_tagihan_dibatalkan_menolak_bukti(kon_tagihan):
    import kelas_batal
    kk.tagih(kon_tagihan, 1, PRIVATE)
    kelas_batal.batalkan_tagihan(kon_tagihan, AKUN, 1, PRIVATE, kk.KINI)
    kon_tagihan.commit()
    assert _galat(lambda: _unggah(kon_tagihan, PRIVATE))[0] is k.KelasKonflik
    assert _bukti(kon_tagihan) == []


def test_tagihan_kedaluwarsa_menolak_bukti_di_luar_jendela(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    assert _galat(lambda: _unggah(kon_tagihan, MINI, sekarang=kk.SESUDAH_JENDELA))[0] is k.KelasKonflik
    assert _bukti(kon_tagihan) == []


# --- validasi sebelum DB --------------------------------------------------------------------------

@pytest.mark.parametrize("kode", ["gratis", "", "MINI", "../mini", 123, None])
def test_kode_asing_ditolak_sebelum_menyentuh_db(kon_tagihan, kode):
    kk.tagih(kon_tagihan, 1, MINI)
    jejak = _sql_dijalankan(kon_tagihan, lambda: _unggah(kon_tagihan, kode))
    assert jejak == []
    assert _galat(lambda: _unggah(kon_tagihan, kode))[0] is d.PesananDataTidakSah
    assert _bukti(kon_tagihan) == []


@pytest.mark.parametrize("ganti", [dict(mime="text/html"), dict(ukuran=0), dict(sha256="xyz")])
def test_metadata_bukti_tidak_sah_ditolak_sebelum_db_dengan_kode_eksplisit(kon_tagihan, ganti):
    kk.tagih(kon_tagihan, 1, MINI)
    argumen = dict(mime=kk.MIME, ukuran=kk.UKURAN, sha256=kk.sha(1), nama_tersimpan=kk.berkas(1))
    argumen.update(ganti)
    jejak = _sql_dijalankan(kon_tagihan, lambda: store.catat_bukti(
        kon_tagihan, AKUN, 1, MINI, argumen["mime"], argumen["ukuran"], argumen["sha256"],
        argumen["nama_tersimpan"], kk.SESUDAH_UPLOAD))
    assert jejak == []
    assert _bukti(kon_tagihan) == []
