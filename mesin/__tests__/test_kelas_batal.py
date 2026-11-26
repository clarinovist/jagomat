"""Batal dan pulih tagihan Paket Belajar (domain): tagihan dipilih lewat KODE PAKET, dua tagihan berdampingan, dan pemulihan.

Data sintetis, tingkat domain (tanpa HTTP). Skenario deposit Peta memakai waktu dari `kelas_kit`.
"""
import pytest

import kelas_batal as B
import kelas_dasar as k
import kelas_kit as kk
import kelas_rincian
import kelas_status as ks
import kelas_store
import pesanan_dasar as d
from kelas_kit import db_kelas, kon_kelas  # noqa: F401
from tagihan_kit import db_tagihan, jumlah_catatan, kon_tagihan, semua_catatan  # noqa: F401

AKUN = kk.AKUN_A
AKUN_LAIN = kk.AKUN_B
MINI, PRIVATE = "mini", "private"
PESAN_TIDAK_DITEMUKAN = "pesanan tidak ditemukan"


def batal(kon, kode, *, akun=AKUN, siswa=1, sekarang=kk.KINI):
    return B.batalkan_tagihan(kon, akun, siswa, kode, sekarang)


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


def _order_mini(kon, akun=AKUN, siswa=1):
    return [r[0] for r in kon.execute("SELECT id FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY rowid",
                                      (akun, siswa, MINI))]


# --- batal sukses dan kepemilikan ------------------------------------------------------------

def test_batalkan_tagihan_belum_bayar_menulis_satu_catatan_batal(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    hasil = batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert hasil == {"order_id": tagihan.order_id, "status": k.STATUS_DIBATALKAN}
    assert [r[1:3] for r in semua_catatan(kon_tagihan)] == [(tagihan.order_id, "batal")]
    assert kelas_store.tagihan_terbuka(kon_tagihan, AKUN, 1, MINI, kk.KINI) is None
    assert kelas_store.tagihan_dari(kon_tagihan, AKUN, tagihan.order_id, kk.KINI).status == k.STATUS_DIBATALKAN


def test_paket_tanpa_tagihan_terbuka_identik_dengan_milik_akun_lain_tanpa_catatan(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    sebelum = kon_tagihan.total_changes
    milik_lain = _galat(lambda: batal(kon_tagihan, MINI, akun=AKUN_LAIN))
    tanpa_tagihan = _galat(lambda: batal(kon_tagihan, PRIVATE))
    assert milik_lain == tanpa_tagihan == (d.PesananTidakDitemukan, PESAN_TIDAK_DITEMUKAN)
    assert kon_tagihan.total_changes == sebelum and jumlah_catatan(kon_tagihan) == 0


def test_anak_lain_pada_akun_sama_identik_dengan_tanpa_tagihan(kon_tagihan):
    kk.tagih(kon_tagihan, 2, MINI)
    sebelum = kon_tagihan.total_changes
    anak_lain = _galat(lambda: batal(kon_tagihan, MINI, siswa=1))
    assert anak_lain == (d.PesananTidakDitemukan, PESAN_TIDAK_DITEMUKAN)
    assert kon_tagihan.total_changes == sebelum and jumlah_catatan(kon_tagihan) == 0


def test_dua_akun_memakai_kode_paket_sama_hanya_tagihan_pemiliknya_yang_dibatalkan(kon_tagihan):
    milik_a = kk.tagih(kon_tagihan, 1, MINI)
    milik_b = kk.tagih(kon_tagihan, 2, MINI, akun=AKUN_LAIN)
    sebelum = kon_tagihan.total_changes
    assert _galat(lambda: batal(kon_tagihan, MINI, akun=AKUN_LAIN, siswa=1))[0] is d.PesananTidakDitemukan
    assert kon_tagihan.total_changes == sebelum and jumlah_catatan(kon_tagihan) == 0
    batal(kon_tagihan, MINI, akun=AKUN_LAIN, siswa=2)
    kon_tagihan.commit()
    assert [r[1:3] for r in semua_catatan(kon_tagihan)] == [(milik_b.order_id, "batal")]
    assert kelas_store.tagihan_terbuka(kon_tagihan, AKUN, 1, MINI, kk.KINI).order_id == milik_a.order_id


def test_kode_paket_asing_ditolak_sebelum_menyentuh_db(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    for kode in ("gratis", "", "MINI", "../mini", 123, None):
        jejak = _sql_dijalankan(kon_tagihan, lambda: batal(kon_tagihan, kode))
        assert jejak == [], "tidak boleh ada SQL untuk kode %r" % (kode,)
        assert _galat(lambda: batal(kon_tagihan, kode))[0] is d.PesananDataTidakSah
    assert jumlah_catatan(kon_tagihan) == 0


# --- penolakan keadaan -----------------------------------------------------------------------

def test_bukti_sudah_ada_menolak_batal_tanpa_catatan(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    kk.unggah(kon_tagihan, 1, MINI)
    sebelum = kon_tagihan.total_changes
    assert _galat(lambda: batal(kon_tagihan, MINI))[0] is k.KelasKonflik
    assert kon_tagihan.total_changes == sebelum and jumlah_catatan(kon_tagihan) == 0


def test_sudah_lunas_menolak_batal_tanpa_catatan(kon_tagihan):
    kk.lunas(kon_tagihan, 1, MINI)
    assert _galat(lambda: batal(kon_tagihan, MINI))[0] is d.PesananTidakDitemukan
    assert jumlah_catatan(kon_tagihan) == 0


def test_batal_ganda_menolak_dan_tidak_menambah_catatan(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    assert _galat(lambda: batal(kon_tagihan, MINI))[0] is d.PesananTidakDitemukan
    assert jumlah_catatan(kon_tagihan) == 1


def test_sesudah_jendela_bayar_tagihan_kedaluwarsa_tidak_terbuka_dan_tanpa_catatan(kon_tagihan):
    kk.tagih(kon_tagihan, 1, MINI)
    assert _galat(lambda: batal(kon_tagihan, MINI, sekarang=kk.SESUDAH_JENDELA))[0] is d.PesananTidakDitemukan
    assert jumlah_catatan(kon_tagihan) == 0


def test_tabel_belum_dipasang_menolak_tanpa_tulis(kon_kelas):
    kk.tagih(kon_kelas, 1, MINI)
    sebelum = kon_kelas.total_changes
    assert _galat(lambda: batal(kon_kelas, MINI))[0] is k.KelasKonflik
    assert kon_kelas.total_changes == sebelum


# --- dua tagihan berdampingan dan pemulihan --------------------------------------------------

def test_dua_tagihan_paket_berbeda_terbuka_berdampingan_dan_batal_satu_tidak_mengganggu_yang_lain(kon_tagihan):
    mini = kk.tagih(kon_tagihan, 1, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    assert {s[0]["id"] for s in ks.order_terbuka_siswa(kon_tagihan, AKUN, 1, kk.KINI)} == {mini.order_id,
                                                                                         private.order_id}
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert kelas_store.tagihan_terbuka(kon_tagihan, AKUN, 1, PRIVATE, kk.KINI).order_id == private.order_id
    assert kelas_store.tagihan_terbuka(kon_tagihan, AKUN, 1, MINI, kk.KINI) is None


def test_pulih_lewat_buat_tagihan_mengembalikan_tagihan_yang_sama_tanpa_order_baru(kon_tagihan):
    mini = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    pulih = kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_UPLOAD)
    assert pulih.order_id == mini.order_id and pulih.status == k.STATUS_BELUM_BAYAR
    assert pulih.total == mini.total and pulih.kode_unik == mini.kode_unik
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal", "pulih"]
    assert _order_mini(kon_tagihan) == [mini.order_id]


def test_pulih_tetap_boleh_saat_paket_lain_masih_terbuka(kon_tagihan):
    mini = kk.tagih(kon_tagihan, 1, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    pulih = kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_UPLOAD)
    assert pulih.order_id == mini.order_id
    assert kelas_store.tagihan_terbuka(kon_tagihan, AKUN, 1, PRIVATE, kk.SESUDAH_UPLOAD).order_id == private.order_id
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal", "pulih"]


def test_pulih_setelah_jendela_lewat_membuat_tagihan_baru(kon_tagihan):
    mini = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    baru = kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_JENDELA)
    assert baru.order_id != mini.order_id and baru.status == k.STATUS_BELUM_BAYAR
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal"]
    assert len(_order_mini(kon_tagihan)) == 2


# --- deposit Peta pada pemulihan --------------------------------------------------------------

def test_deposit_tagihan_batal_dipulihkan_utuh_bila_deposit_masih_tersedia(kon_tagihan):
    kk.peta_lunas(kon_tagihan, 1)
    mini = kk.tagih(kon_tagihan, 1, MINI)
    assert mini.rincian.potongan_deposit == 49_000
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    pulih = kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_UPLOAD)
    assert pulih.order_id == mini.order_id and pulih.rincian.potongan_deposit == 49_000
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal", "pulih"]


def test_deposit_sudah_dipakai_tagihan_lain_dan_lunas_menolak_pulih_tanpa_tulis(kon_tagihan):
    """RED kasus Peta: Mini(deposit) batal -> Private mengambil deposit lalu lunas (voucher terpakai) -> Mini tak boleh pulih."""
    kk.peta_lunas(kon_tagihan, 1)
    mini = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    assert private.rincian.potongan_deposit == 49_000
    bukti = kk.unggah(kon_tagihan, 1, PRIVATE)["bukti_id"]
    kk.setuju(kon_tagihan, private, bukti, sekarang=kk.SESUDAH_UPLOAD)
    assert kelas_rincian.deposit_aktif(kon_tagihan, AKUN, 1, kk.SESUDAH_UPLOAD) is None   # premis: voucher terpakai
    kon_tagihan.commit()
    sebelum = kon_tagihan.total_changes
    galat = _galat(lambda: kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_UPLOAD))
    assert galat[0] is k.KelasKonflik and galat[1].startswith("deposit"), galat
    assert kon_tagihan.total_changes == sebelum
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal"]
    assert _order_mini(kon_tagihan) == [mini.order_id]


def test_deposit_masih_dipegang_tagihan_terbuka_lain_menolak_pulih(kon_tagihan):
    kk.peta_lunas(kon_tagihan, 1)
    kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    assert private.rincian.potongan_deposit == 49_000
    kon_tagihan.commit()
    galat = _galat(lambda: kk.tagih(kon_tagihan, 1, MINI, sekarang=kk.SESUDAH_UPLOAD))
    assert galat[0] is k.KelasKonflik and galat[1].startswith("deposit"), galat
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal"]


def test_deposit_tidak_dipotongkan_dua_kali_pada_tagihan_berdampingan(kon_tagihan):
    kk.peta_lunas(kon_tagihan, 1)
    mini = kk.tagih(kon_tagihan, 1, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)
    assert (mini.rincian.potongan_deposit, private.rincian.potongan_deposit) == (49_000, 0)
    assert private.rincian.nominal == 640_000
    assert (mini.total, private.total) == (mini.rincian.nominal + mini.kode_unik, 640_000 + private.kode_unik)


def test_nominal_tagihan_batal_tetap_ditahan_selama_jendela(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert tagihan.total in ks.nominal_dipegang(kon_tagihan, kk.KINI)
    assert tagihan.total not in ks.nominal_dipegang(kon_tagihan, kk.SESUDAH_JENDELA)
