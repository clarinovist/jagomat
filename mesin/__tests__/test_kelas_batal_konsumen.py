"""Konsumen status tagihan DIBATALKAN: setiap pembaca yang menghitung tagihan terbuka, antrean, putusan, atau tampilan admin.

Satu kasus per konsumen. Data sintetis (akun, anak, waktu buatan). Tagihan batal tidak boleh diingatkan, dihitung belum bayar,
masuk antrean verifikasi, menerima putusan, atau tampak sebagai aktif. Tampilan admin memberi label, bukan status mentah.
"""
from datetime import datetime, timedelta

import admin_pembayaran_pages as P
import admin_pembayaran_semua as S
import jadwal_dasar as jd
import jadwal_store as js
import kelas_admin_pages as KAP
import kelas_batal
import kelas_dasar as k
import kelas_kit as kk
import kelas_masa as km
import kelas_putusan as kp
import kelas_status as ks
import kelas_store
import kelas_tunggakan as kt
import pesanan
from tagihan_kit import db_tagihan, kon_tagihan  # noqa: F401

AKUN = kk.AKUN_A
AKUN_LAIN = kk.AKUN_B
MINI, PRIVATE = "mini", "private"
LABEL_DIBATALKAN = "Dibatalkan oleh orang tua"
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"


def batal(kon, kode, sekarang=kk.KINI, akun=AKUN):
    return kelas_batal.batalkan_tagihan(kon, akun, 1, kode, sekarang)


def _galat(fungsi):
    try:
        fungsi()
    except Exception as galat:  # noqa: BLE001 - tes ini membandingkan jenis galat apa adanya
        return type(galat), str(galat)
    raise AssertionError("tidak melempar galat")


def _berakhir_akses(kon):
    return kon.execute("SELECT MAX(a.berakhir) FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
                       "WHERE o.akun_id=? AND a.siswa_id=?", (AKUN, 1)).fetchone()[0]


def _lewat(waktu, hari):
    return (datetime.strptime(waktu, FORMAT_WAKTU) + timedelta(days=hari)).strftime(FORMAT_WAKTU)


# --- status turunan ------------------------------------------------------------------------------

def test_status_dibatalkan_hanya_selama_jendela_lalu_kedaluwarsa(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    order = ks.baris_order(kon_tagihan, tagihan.order_id)
    fakta = ks.fakta_order(kon_tagihan, tagihan.order_id)
    assert ks.status_dari(order, fakta, kk.KINI) == k.STATUS_DIBATALKAN
    assert ks.status_dari(order, fakta, kk.SESUDAH_JENDELA) == k.STATUS_KEDALUWARSA
    assert k.STATUS_DIBATALKAN not in k.STATUS_TERBUKA


def test_order_dibatalkan_hanya_untuk_akun_dan_anak_pemilik(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert ks.order_dibatalkan(kon_tagihan, AKUN, 1, MINI, kk.KINI)[0]["id"] == tagihan.order_id
    assert ks.order_dibatalkan(kon_tagihan, AKUN_LAIN, 1, MINI, kk.KINI) is None
    assert ks.order_dibatalkan(kon_tagihan, AKUN, 2, MINI, kk.KINI) is None
    assert ks.order_dibatalkan(kon_tagihan, AKUN, 1, MINI, kk.SESUDAH_JENDELA) is None


# --- konsumen: pengingat, antrean, tunggakan, putusan, jadwal, tampilan admin ---------------------

def test_pengingat_belum_dibayar_mengabaikan_tagihan_batal_dan_menampilkan_yang_terbuka(kon_tagihan):
    mini = kk.tagih(kon_tagihan, 1, MINI)
    private = kk.tagih(kon_tagihan, 1, PRIVATE)          # terbaru: dibatalkan, jadi tidak boleh diingatkan
    batal(kon_tagihan, PRIVATE)
    kon_tagihan.commit()
    pengingat = km.tagihan_belum_dibayar(kon_tagihan, AKUN, 1, kk.KINI)
    assert [(p.kode_paket, p.status) for p in pengingat] == [(MINI, k.STATUS_BELUM_BAYAR)]
    assert mini.order_id != private.order_id


def test_pengingat_kosong_bila_satu_satunya_tagihan_dibatalkan(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert km.tagihan_belum_dibayar(kon_tagihan, AKUN, 1, kk.KINI) == ()


def test_antrean_verifikasi_tidak_memuat_tagihan_batal(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert kelas_store.antrean(kon_tagihan) == []


def test_tunggakan_tetap_tampil_saat_tagihan_baru_dibatalkan(kon_tagihan):
    kk.lunas(kon_tagihan, 1, MINI)
    sekarang = _lewat(_berakhir_akses(kon_tagihan), 35)
    tagihan = kk.tagih(kon_tagihan, 1, MINI, sekarang=sekarang)
    kon_tagihan.commit()
    assert kt.daftar_tunggakan(kon_tagihan, sekarang) == ()          # tagihan terbuka menahan tunggakan (perilaku lama)
    batal(kon_tagihan, MINI, sekarang)
    kon_tagihan.commit()
    assert [t.kode_paket for t in kt.daftar_tunggakan(kon_tagihan, sekarang)] == [MINI]


def test_putusan_admin_menolak_tagihan_dibatalkan_tanpa_verifikasi(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert _galat(lambda: kp.setujui(kon_tagihan, tagihan.order_id, kk.ADMIN, kk.SESUDAH_UPLOAD,
                                     bukti_dilihat=1))[0] is k.KelasKonflik
    assert _galat(lambda: kp.tolak(kon_tagihan, tagihan.order_id, kk.ADMIN, "bukti tidak sesuai",
                                   kk.SESUDAH_UPLOAD, bukti_dilihat=1))[0] is k.KelasKonflik
    assert kon_tagihan.execute("SELECT COUNT(*) FROM kelas_verifikasi").fetchone()[0] == 0


def test_penempatan_jadwal_menolak_tagihan_dibatalkan_sebagai_belum_aktif(kon_tagihan):
    """`_order_aktif` adalah gerbang penempatan jadwal (`tempatkan`): tagihan batal bukan paket aktif."""
    tagihan = kk.tagih(kon_tagihan, 1, MINI)
    batal(kon_tagihan, MINI)
    kon_tagihan.commit()
    assert _galat(lambda: js._order_aktif(kon_tagihan, tagihan.order_id, kk.KINI))[0] is jd.JadwalKonflik


def test_semua_pembayaran_menghitung_tagihan_batal_di_kelompok_ditolak_bukan_belum_bayar(db_tagihan):
    with pesanan.buka(db_tagihan, tulis_data=True) as kon:
        tagihan = kk.tagih(kon, 1, MINI)
        batal(kon, MINI)
        kon.commit()
    baris = S._kelas(db_tagihan, kk.KINI)
    dibatalkan = [b for b in baris if b.order_id == tagihan.order_id]
    assert [b.status for b in dibatalkan] == [S.S_DIBATALKAN]
    assert S.hitung(baris)["belum_bayar"] == 0
    assert dibatalkan[0] in S.saring(baris, "ditolak")
    assert dibatalkan[0] not in S.saring(baris, "belum_bayar")
    assert sum(S.hitung(baris)[kelompok] for kelompok in S.KELOMPOK) == S.hitung(baris)["semua"]


def test_label_tampilan_admin_untuk_tagihan_dibatalkan():
    assert P.COPY_STATUS[S.S_DIBATALKAN] == LABEL_DIBATALKAN
    assert KAP.COPY_STATUS[k.STATUS_DIBATALKAN] == LABEL_DIBATALKAN
