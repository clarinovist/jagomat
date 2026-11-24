"""kelas_putusan: setujui/tolak admin, akses berjendela, deposit dipakai tepat sekali saat lunas. Data sintetis."""
import pytest

import kelas_dasar as k
import kelas_putusan
import kelas_store
import pesanan
import pesanan_dasar as d
import pesanan_kit
import purna
from kelas_kit import (ADMIN, ADMIN_B, AKUN_A, AKUN_B, KINI, SESUDAH_JENDELA, SESUDAH_UPLOAD, baris, berkas,
                       db_kelas, kon_kelas, lunas, menunggu, peta_lunas, setuju, sha, sisip_tagihan, tagih,  # noqa: F401
                       unggah)

PUTUS = SESUDAH_UPLOAD
BERAKHIR_1_BULAN = "2026-12-20T09:30:00"


def operasi_deposit(tagihan):
    return k.operasi_deposit(tagihan.order_id)


def tulisan(kon):
    return {t: baris(kon, t) for t in ("kelas_verifikasi", "kelas_akses", "purna_voucher_pakai")}


# --- setujui: akses ------------------------------------------------------------------------------------

def test_setujui_menulis_verifikasi_dan_akses_satu_bulan_kalender(kon_kelas):
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    hasil = setuju(kon_kelas, tagihan, bukti)
    assert hasil["status"] == "aktif" and hasil["baru"] is True
    verifikasi = baris(kon_kelas, "kelas_verifikasi")
    assert [(v[1], v[2], v[3], v[4], v[5]) for v in verifikasi] == [(tagihan.order_id, "setuju", ADMIN, None, bukti)]
    akses = baris(kon_kelas, "kelas_akses")
    assert [(a[1], a[2], a[4], a[5]) for a in akses] == [(tagihan.order_id, 1, PUTUS, BERAKHIR_1_BULAN)]
    lihat = kelas_store.tagihan_dari(kon_kelas, AKUN_A, tagihan.order_id, PUTUS)
    assert lihat.status == "aktif" and lihat.berakhir == BERAKHIR_1_BULAN and lihat.kedaluwarsa is None
    assert not kon_kelas.in_transaction


def test_setujui_dua_kali_tidak_menggandakan_akses_maupun_deposit(kon_kelas):
    peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    pertama = setuju(kon_kelas, tagihan, bukti)
    sebelum = tulisan(kon_kelas)
    kedua = setuju(kon_kelas, tagihan, bukti, sekarang="2026-11-20T10:00:00", admin=ADMIN_B)
    assert kedua == {"status": "aktif", "verifikasi_id": pertama["verifikasi_id"], "baru": False}
    assert tulisan(kon_kelas) == sebelum
    assert len(sebelum["purna_voucher_pakai"]) == 1


def test_setujui_tanpa_bukti_atau_order_tak_ada_atau_setelah_tolak_tanpa_bukti_baru_ditolak(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    with pytest.raises(k.KelasKonflik):
        kelas_putusan.setujui(kon_kelas, tagihan.order_id, ADMIN, PUTUS, bukti_dilihat=1)
    with pytest.raises(d.PesananTidakDitemukan):
        kelas_putusan.setujui(kon_kelas, k.PREFIX_ORDER + "0" * 32, ADMIN, PUTUS, bukti_dilihat=1)
    bukti = unggah(kon_kelas, 1, "mini", 1)["bukti_id"]
    kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, "buram", PUTUS, bukti_dilihat=bukti)
    with pytest.raises(k.KelasKonflik):
        kelas_putusan.setujui(kon_kelas, tagihan.order_id, ADMIN, PUTUS, bukti_dilihat=bukti)
    assert baris(kon_kelas, "kelas_akses") == []


def test_setujui_atas_bukti_yang_sudah_usang_ditolak_tanpa_tulis(kon_kelas):
    tagihan, lama = menunggu(kon_kelas, 1, "mini", 1)
    unggah(kon_kelas, 1, "mini", 2)                                    # bukti baru sesudah admin melihat bukti 1
    with pytest.raises(k.KelasKonflik):
        setuju(kon_kelas, tagihan, lama)
    assert tulisan(kon_kelas) == {"kelas_verifikasi": [], "kelas_akses": [], "purna_voucher_pakai": []}


@pytest.mark.parametrize("bukti", [0, -1, "1", None, True, 1.0])
def test_bukti_dilihat_wajib_bilangan_sah(kon_kelas, bukti):
    tagihan, _ = menunggu(kon_kelas, 1, "mini", 1)
    with pytest.raises(d.PesananDataTidakSah):
        kelas_putusan.setujui(kon_kelas, tagihan.order_id, ADMIN, PUTUS, bukti_dilihat=bukti)


def test_setujui_wajib_menyebut_bukti_dilihat(kon_kelas):
    tagihan, _ = menunggu(kon_kelas, 1, "mini", 1)
    with pytest.raises(TypeError):
        kelas_putusan.setujui(kon_kelas, tagihan.order_id, ADMIN, PUTUS)


@pytest.mark.parametrize("admin", ["", "a b", None, "x" * 65])
def test_admin_tidak_sah_ditolak(kon_kelas, admin):
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    with pytest.raises(d.PesananDataTidakSah):
        kelas_putusan.setujui(kon_kelas, tagihan.order_id, admin, PUTUS, bukti_dilihat=bukti)


def test_order_menunggu_tetap_bisa_diputuskan_sesudah_jendela_lewat(kon_kelas):
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    assert setuju(kon_kelas, tagihan, bukti, sekarang=SESUDAH_JENDELA)["status"] == "aktif"


# --- masa aktif: rantai per (anak, paket) -------------------------------------------------------------

def test_perpanjangan_menyambung_dari_akhir_akses_dan_hari_jangkar_tidak_bergeser(kon_kelas):
    jan = "2027-01-31T03:00:00"
    lunas(kon_kelas, 1, "mini", 1, sekarang="2027-01-31T02:00:00", putus=jan)
    bulan1 = baris(kon_kelas, "kelas_akses")[0]
    assert (bulan1[4], bulan1[5]) == (jan, "2027-02-28T03:00:00")                      # 31 Jan -> 28 Feb
    lunas(kon_kelas, 1, "mini", 2, sekarang="2027-02-10T02:00:00", putus="2027-02-10T03:00:00")
    bulan2 = baris(kon_kelas, "kelas_akses")[1]
    assert (bulan2[4], bulan2[5]) == ("2027-02-28T03:00:00", "2027-03-31T03:00:00")    # jangkar 31 Jan + 2 bulan
    lunas(kon_kelas, 1, "mini", 3, sekarang="2027-03-10T02:00:00", putus="2027-03-10T03:00:00")
    assert baris(kon_kelas, "kelas_akses")[2][5] == "2027-04-30T03:00:00"


def test_rantai_per_paket_mini_tidak_menunggu_akhir_private(kon_kelas):
    lunas(kon_kelas, 1, "private", 1)
    lunas(kon_kelas, 1, "mini", 2, sekarang="2026-11-21T00:00:00", putus="2026-11-21T00:30:00")
    private, mini = baris(kon_kelas, "kelas_akses")
    assert mini[4] == "2026-11-21T00:30:00" and mini[4] < private[5]


def test_akses_yang_sudah_berakhir_memulai_rantai_baru(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    lunas(kon_kelas, 1, "mini", 2, sekarang="2027-01-05T00:00:00", putus="2027-01-05T00:30:00")
    kedua = baris(kon_kelas, "kelas_akses")[1]
    assert (kedua[4], kedua[5]) == ("2027-01-05T00:30:00", "2027-02-05T00:30:00")


def test_perpanjangan_diputuskan_saat_masih_aktif_memperpanjang_dari_akhir(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    lunas(kon_kelas, 1, "mini", 2, sekarang="2026-12-01T00:00:00", putus="2026-12-01T00:30:00")
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_A, 1, "mini", "2026-12-01T01:00:00") == "2027-01-20T09:30:00"


# --- tolak ------------------------------------------------------------------------------------------------

def test_tolak_butuh_alasan_dan_menulis_verifikasi_tanpa_akses_dan_tanpa_deposit(kon_kelas):
    peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    for alasan in ("", "   ", None, "x" * 201, "a\x00b"):
        with pytest.raises(d.PesananDataTidakSah):
            kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, alasan, PUTUS, bukti_dilihat=bukti)
    assert baris(kon_kelas, "kelas_verifikasi") == []
    hasil = kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, " buram ", PUTUS, bukti_dilihat=bukti)
    assert hasil["status"] == "ditolak" and hasil["baru"] is True
    assert [v[2:5] for v in baris(kon_kelas, "kelas_verifikasi")] == [("tolak", ADMIN, "buram")]
    assert baris(kon_kelas, "kelas_akses") == [] and baris(kon_kelas, "purna_voucher_pakai") == []
    lihat = kelas_store.tagihan_dari(kon_kelas, AKUN_A, tagihan.order_id, PUTUS)
    assert lihat.status == "ditolak" and lihat.kedaluwarsa == tagihan.kedaluwarsa


def test_tolak_lalu_unggah_ulang_lalu_setujui_atas_bukti_baru(kon_kelas):
    tagihan, lama = menunggu(kon_kelas, 1, "mini", 1)
    kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, "buram", PUTUS, bukti_dilihat=lama)
    baru = unggah(kon_kelas, 1, "mini", 2, sekarang="2026-11-20T10:00:00")["bukti_id"]
    assert setuju(kon_kelas, tagihan, baru, sekarang="2026-11-20T11:00:00")["status"] == "aktif"


def test_tolak_pada_order_yang_tidak_menunggu_konflik(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    with pytest.raises(k.KelasKonflik):
        kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, "buram", PUTUS, bukti_dilihat=1)
    done = lunas(kon_kelas, 2, "mini", 2)
    with pytest.raises(k.KelasKonflik):
        kelas_putusan.tolak(kon_kelas, done.order_id, ADMIN, "buram", PUTUS, bukti_dilihat=2)


def test_tolak_dan_kedaluwarsa_melepas_deposit_untuk_tagihan_baru(kon_kelas):
    peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    kelas_putusan.tolak(kon_kelas, tagihan.order_id, ADMIN, "buram", PUTUS, bukti_dilihat=bukti)
    baru = tagih(kon_kelas, 1, "mini", sekarang=SESUDAH_JENDELA)
    assert baru.order_id != tagihan.order_id and baru.rincian.potongan_deposit == 49_000


# --- deposit dipakai saat lunas, tepat sekali ----------------------------------------------------------------

def test_setujui_dengan_deposit_mencatat_pemakaian_di_transaksi_yang_sama(kon_kelas):
    peta = peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    assert (tagihan.rincian.nominal, baris(kon_kelas, "purna_voucher_pakai")) == (201_000, [])
    setuju(kon_kelas, tagihan, bukti, admin=ADMIN_B)
    assert baris(kon_kelas, "purna_voucher_pakai") == [(operasi_deposit(tagihan), peta, ADMIN_B, "kelas", PUTUS)]
    assert purna.keadaan(kon_kelas, peta, PUTUS).voucher == "dipakai"


def test_setujui_tanpa_deposit_tidak_menyentuh_purna(kon_kelas):
    peta_lunas(kon_kelas, 1, AKUN_B)                                   # milik akun lain: tidak dipotongkan
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    setuju(kon_kelas, tagihan, bukti)
    assert baris(kon_kelas, "purna_voucher_pakai") == []
    assert purna.keadaan(kon_kelas, pesanan_kit.ord_id(1), PUTUS).voucher == "aktif"


def test_deposit_kedaluwarsa_di_antara_tagihan_dan_lunas_ditolak_tanpa_tulisan_apa_pun(kon_kelas):
    peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    sebelum = tulisan(kon_kelas)
    with pytest.raises(k.DepositTidakAktif):
        setuju(kon_kelas, tagihan, bukti, sekarang="2027-02-17T00:00:00")        # lewat 90 hari
    assert tulisan(kon_kelas) == sebelum
    assert kelas_store.tagihan_dari(kon_kelas, AKUN_A, tagihan.order_id, "2027-02-17T00:00:00").status == "menunggu"
    assert not kon_kelas.in_transaction


def test_deposit_dipakai_manual_atau_direfund_di_antara_tagihan_dan_lunas_ditolak(kon_kelas):
    manual = peta_lunas(kon_kelas, 1)
    refund = peta_lunas(kon_kelas, 2)
    t1, b1 = menunggu(kon_kelas, 1, "mini", 1)
    t2, b2 = menunggu(kon_kelas, 2, "mini", 2)
    purna.catat_pakai(kon_kelas, manual, pesanan_kit.operasi(1), ADMIN, "lainnya", KINI)
    pesanan.catat_refund(kon_kelas, refund, pesanan_kit.operasi(2), ADMIN, "kebijakan", KINI)
    sebelum = tulisan(kon_kelas)
    for tagihan, bukti in ((t1, b1), (t2, b2)):
        with pytest.raises(k.DepositTidakAktif):
            setuju(kon_kelas, tagihan, bukti)
    assert tulisan(kon_kelas) == sebelum


def test_deposit_hanya_sekali_pakai_tagihan_kedua_yang_memegangnya_ditolak(kon_kelas):
    peta = peta_lunas(kon_kelas, 1)
    t1, b1 = menunggu(kon_kelas, 1, "mini", 1)
    t2 = tagih(kon_kelas, 1, "private")                                  # domain tidak memotongkan deposit dua kali
    assert t2.rincian.potongan_deposit == 0
    b2 = unggah(kon_kelas, 1, "private", 2)["bukti_id"]
    # tagihan kedua yang (secara menyimpang) memuat potongan deposit yang sama: ditolak saat lunas
    kon_kelas.commit()
    kon_kelas.execute("PRAGMA ignore_check_constraints=ON")
    kon_kelas.execute("DROP TRIGGER kelas_tagihan_tolak_update")
    kon_kelas.execute("UPDATE kelas_tagihan SET harga_dasar=640000,potongan_deposit=49000,deposit_order_id=?,"
                      "nominal=591000,total_transfer=591000+kode_unik WHERE order_id=?", (peta, t2.order_id))
    kon_kelas.commit()
    setuju(kon_kelas, t1, b1)
    sebelum = tulisan(kon_kelas)
    with pytest.raises(k.DepositTidakAktif):
        setuju(kon_kelas, t2, b2)
    assert tulisan(kon_kelas) == sebelum
    assert len(sebelum["purna_voucher_pakai"]) == 1


def test_setelah_lunas_deposit_terpakai_dan_tagihan_baru_tidak_memotong_lagi(kon_kelas):
    peta_lunas(kon_kelas, 1)
    lunas(kon_kelas, 1, "mini", 1)
    baru = tagih(kon_kelas, 1, "private", sekarang="2026-11-21T01:00:00")
    assert (baru.rincian.potongan_deposit, baru.rincian.nominal) == (0, 640_000)
    perpanjang = tagih(kon_kelas, 1, "mini", sekarang="2026-11-21T01:00:00")
    assert perpanjang.rincian.potongan_deposit == 0


def _hapus_pelindung_db(kon, trigger):
    """Simulasi DB yang menyimpang: lepas satu trigger lapis-DB supaya guard domain teruji sendirian."""
    kon.commit()
    kon.execute("DROP TRIGGER %s" % trigger)
    kon.commit()


def test_deposit_milik_akun_lain_ditolak_domain_walau_lapis_db_hilang(kon_kelas):
    peta_lunas(kon_kelas, 1, AKUN_B)                                     # Peta anak 1 dibayar akun B
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1, akun=AKUN_A)      # tagihan akun A tanpa deposit
    _hapus_pelindung_db(kon_kelas, "kelas_tagihan_deposit_milik")
    _hapus_pelindung_db(kon_kelas, "kelas_tagihan_tolak_update")
    kon_kelas.execute("UPDATE kelas_tagihan SET potongan_deposit=49000,deposit_order_id=?,nominal=201000,"
                      "total_transfer=201000+kode_unik WHERE order_id=?", (pesanan_kit.ord_id(1), tagihan.order_id))
    kon_kelas.commit()
    sebelum = tulisan(kon_kelas)
    with pytest.raises(k.DepositTidakAktif):
        setuju(kon_kelas, tagihan, bukti)
    assert tulisan(kon_kelas) == sebelum


def test_deposit_anak_lain_ditolak_domain_walau_lapis_db_hilang(kon_kelas):
    peta_lunas(kon_kelas, 2)                                             # Peta anak 2, milik akun A juga
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    _hapus_pelindung_db(kon_kelas, "kelas_tagihan_deposit_milik")
    _hapus_pelindung_db(kon_kelas, "kelas_tagihan_tolak_update")
    kon_kelas.execute("UPDATE kelas_tagihan SET potongan_deposit=49000,deposit_order_id=?,nominal=201000,"
                      "total_transfer=201000+kode_unik WHERE order_id=?", (pesanan_kit.ord_id(2), tagihan.order_id))
    kon_kelas.commit()
    with pytest.raises(k.DepositTidakAktif):
        setuju(kon_kelas, tagihan, bukti)
    assert baris(kon_kelas, "purna_voucher_pakai") == [] and baris(kon_kelas, "kelas_akses") == []


def test_kegagalan_menulis_akses_membatalkan_pemakaian_deposit_dan_verifikasi(kon_kelas, monkeypatch):
    peta = peta_lunas(kon_kelas, 1)
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)

    def gagal(*a, **kw):
        raise RuntimeError("gagal sesudah deposit dipakai")

    monkeypatch.setattr(kelas_putusan, "_tulis_akses", gagal)
    with pytest.raises(RuntimeError):
        setuju(kon_kelas, tagihan, bukti)
    assert tulisan(kon_kelas) == {"kelas_verifikasi": [], "kelas_akses": [], "purna_voucher_pakai": []}
    assert purna.keadaan(kon_kelas, peta, PUTUS).voucher == "aktif" and not kon_kelas.in_transaction


def test_pemakaian_deposit_idempoten_dan_operasi_deterministik_per_order(kon_kelas):
    assert k.operasi_deposit(k.PREFIX_ORDER + "ab" * 16) == "kelas-kor_" + "ab" * 16
    assert len(k.operasi_deposit(k.id_order_baru())) <= 64
    with pytest.raises(d.PesananDataTidakSah):
        k.operasi_deposit("kor_xyz")


# --- hitungan tagihan tersimpan ------------------------------------------------------------------------------

def test_hitungan_tagihan_tidak_konsisten_ditolak_saat_setujui(kon_kelas):
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    kon_kelas.commit()
    kon_kelas.execute("DROP TRIGGER kelas_tagihan_tolak_update")
    kon_kelas.execute("PRAGMA ignore_check_constraints=ON")
    kon_kelas.execute("UPDATE kelas_tagihan SET total_transfer=total_transfer+1 WHERE order_id=?",
                      (tagihan.order_id,))
    kon_kelas.commit()
    kon_kelas.execute("PRAGMA ignore_check_constraints=OFF")
    with pytest.raises(k.TagihanTidakSah):
        setuju(kon_kelas, tagihan, bukti)
    assert baris(kon_kelas, "kelas_akses") == [] and baris(kon_kelas, "kelas_verifikasi") == []


# --- bacaan admin -------------------------------------------------------------------------------------------

def test_detail_dan_bukti_meta_untuk_admin(kon_kelas):
    tagihan, bukti = menunggu(kon_kelas, 1, "mini", 1)
    unggah(kon_kelas, 1, "mini", 2)
    rincian = kelas_putusan.detail(kon_kelas, tagihan.order_id, KINI)
    assert (rincian["status"], rincian["siswa_id"], rincian["kode_paket"], rincian["total"]) == (
        "menunggu", 1, "mini", tagihan.total)
    assert [b["keadaan"] for b in rincian["bukti"]] == ["menunggu", "menunggu"]
    assert rincian["bukti_terakhir_id"] == bukti + 1 and rincian["keputusan"] == ()
    assert kelas_putusan.bukti_meta(kon_kelas, bukti) == {"berkas": berkas(1), "mime": "image/jpeg", "ukuran": 120_000}
    assert kelas_putusan.bukti_meta(kon_kelas, 999) is None
    assert kelas_putusan.detail(kon_kelas, k.PREFIX_ORDER + "0" * 32, KINI) is None
    with pytest.raises(d.PesananDataTidakSah):
        kelas_putusan.detail(kon_kelas, "bukan", KINI)
