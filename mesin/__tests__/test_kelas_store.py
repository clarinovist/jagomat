"""kelas_store: kartu paket, tagihan (nominal dari server), bukti, bacaan, antrean, kepemilikan. Data sintetis."""
import pytest

import admin_store
import kelas_dasar as k
import kelas_store
import paket_belajar_katalog as katalog
import pesanan
import pesanan_dasar as d
import purna
from kelas_kit import (ADMIN, AKUN_A, AKUN_B, KINI, MIME, SESUDAH_DEPOSIT, SESUDAH_JENDELA, SESUDAH_UPLOAD, UKURAN,
                       baris, berkas, db_kelas, kon_kelas, lunas, menunggu, peta_lunas, sha, tagih, unggah)  # noqa: F401
import pesanan_kit
import transfer_kit


def kartu(kon, siswa=1, akun=AKUN_A, sekarang=KINI):
    return {c.paket.kode: c for c in kelas_store.kartu_paket(kon, akun, siswa, sekarang)}


def _tautan_langsung(kon, a, b):
    """Tautan keluarga LAMA (tabel masih ada di skema, modul penulisnya sudah dihapus) ditulis langsung ke DB."""
    keluarga = k.id_keluarga_baru()
    kon.executemany("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) VALUES(?,?,?,?)",
                    [(keluarga, a, ADMIN, KINI), (keluarga, b, ADMIN, KINI)])
    kon.commit()                                   # jangan biarkan transaksi implisit terbuka untuk d.tulis berikutnya


# --- pemasangan -----------------------------------------------------------------------------------

def test_buka_ditolak_bila_kelas_belum_dipasang(tmp_path):
    from purna_kit import siapkan_db_purna
    path = siapkan_db_purna(tmp_path)
    with pytest.raises(admin_store.StoreBelumSiap):
        with kelas_store.buka(path):
            pass


def test_buka_memberi_koneksi_untuk_baca_dan_tulis(db_kelas):
    with kelas_store.buka(db_kelas, tulis_data=True) as kon:
        assert tagih(kon).kode_paket == "mini"
    with kelas_store.buka(db_kelas) as kon:
        assert kelas_store.antrean(kon) == []


# --- nominal dari server ---------------------------------------------------------------------------

def test_tagihan_tanpa_deposit_memakai_harga_katalog(kon_kelas):
    mini, private = tagih(kon_kelas, 1, "mini"), tagih(kon_kelas, 2, "private")
    for tagihan, harga in ((mini, 300_000), (private, 640_000)):
        assert (tagihan.rincian.harga_dasar, tagihan.rincian.potongan_deposit, tagihan.rincian.potongan_diskon,
                tagihan.rincian.nominal) == (harga, 0, 0, harga)
        assert tagihan.total == harga + tagihan.kode_unik
        assert 1 <= tagihan.kode_unik <= 999
        assert tagihan.status == "belum_bayar" and tagihan.jumlah_bukti == 0 and tagihan.berakhir is None


def test_tagihan_dengan_deposit_aktif_dipotong_sekali_untuk_semua_paket(kon_kelas):
    peta_lunas(kon_kelas, 1)
    peta_lunas(kon_kelas, 2)
    mini, private = tagih(kon_kelas, 1, "mini"), tagih(kon_kelas, 2, "private")
    assert (mini.rincian.nominal, mini.rincian.potongan_deposit) == (251_000, 49_000)
    assert (private.rincian.nominal, private.rincian.potongan_deposit) == (591_000, 49_000)
    deposit = {r[0]: r[1] for r in kon_kelas.execute("SELECT order_id, deposit_order_id FROM kelas_tagihan")}
    assert set(deposit.values()) == {pesanan_kit.ord_id(1), pesanan_kit.ord_id(2)}


def test_deposit_hanya_dari_order_peta_milik_akun_yang_sama(kon_kelas):
    peta_lunas(kon_kelas, 1, AKUN_B)             # Peta anak 1 dibayar akun B; pembeli kelas adalah akun A
    tagihan = tagih(kon_kelas, 1, "mini", akun=AKUN_A)
    assert tagihan.rincian.potongan_deposit == 0 and tagihan.rincian.nominal == 300_000
    assert kon_kelas.execute("SELECT deposit_order_id FROM kelas_tagihan").fetchone()[0] is None


@pytest.mark.parametrize("sekarang", [SESUDAH_DEPOSIT])
def test_deposit_kedaluwarsa_tidak_dipotongkan(kon_kelas, sekarang):
    peta_lunas(kon_kelas, 1)
    tagihan = tagih(kon_kelas, 1, "mini", sekarang=sekarang)
    assert tagihan.rincian.potongan_deposit == 0 and tagihan.rincian.nominal == 300_000


def test_deposit_direfund_atau_sudah_dipakai_tidak_dipotongkan(kon_kelas):
    refund = peta_lunas(kon_kelas, 1)
    pesanan.catat_refund(kon_kelas, refund, pesanan_kit.operasi(1), ADMIN, "kebijakan", KINI)
    dipakai = peta_lunas(kon_kelas, 2)
    purna.catat_pakai(kon_kelas, dipakai, pesanan_kit.operasi(2), ADMIN, "lainnya", KINI)
    assert tagih(kon_kelas, 1).rincian.potongan_deposit == 0
    assert tagih(kon_kelas, 2).rincian.potongan_deposit == 0


def test_deposit_peta_belum_lunas_tidak_dipotongkan(kon_kelas):
    pesanan_kit.buat(kon_kelas, 1)
    assert tagih(kon_kelas, 1).rincian.potongan_deposit == 0


def test_tautan_keluarga_lama_tidak_menurunkan_harga_anak_kedua(kon_kelas):
    """Regression (25 Nov 2026): diskon anak kedua dihapus. Tautan lama di DB tidak lagi mengubah nominal."""
    lunas(kon_kelas, 1, "mini", 1)                   # anak 1 mulai lebih dulu: dulu anak 2 kena diskon 20%
    _tautan_langsung(kon_kelas, 1, 2)
    assert (tagih(kon_kelas, 2, "mini").rincian.potongan_diskon, tagih(kon_kelas, 2, "mini").rincian.nominal) == (
        0, 300_000)
    assert tagih(kon_kelas, 2, "private").rincian.nominal == 640_000


def test_tautan_keluarga_lama_dengan_deposit_tetap_normal_minus_deposit(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    _tautan_langsung(kon_kelas, 1, 2)
    peta_lunas(kon_kelas, 2)
    tagihan = tagih(kon_kelas, 2, "mini")
    assert (tagihan.rincian.potongan_deposit, tagihan.rincian.potongan_diskon, tagihan.rincian.nominal) == (
        49_000, 0, 251_000)


def test_deposit_tidak_dipegang_dua_tagihan_terbuka_sekaligus(kon_kelas):
    peta_lunas(kon_kelas, 1)
    mini, private = tagih(kon_kelas, 1, "mini"), tagih(kon_kelas, 1, "private")
    assert mini.rincian.potongan_deposit == 49_000
    assert (private.rincian.potongan_deposit, private.rincian.nominal) == (0, 640_000)


def test_deposit_dilepas_setelah_tagihan_pemegang_kedaluwarsa(kon_kelas):
    peta_lunas(kon_kelas, 1)
    tagih(kon_kelas, 1, "mini")
    private = tagih(kon_kelas, 1, "private", sekarang=SESUDAH_JENDELA)
    assert (private.rincian.potongan_deposit, private.rincian.nominal) == (49_000, 591_000)


# --- kartu ------------------------------------------------------------------------------------------

def test_kartu_memuat_semua_paket_katalog_dengan_rincian_dan_penanda_tagihan(kon_kelas):
    peta_lunas(kon_kelas, 1)
    sebelum = kartu(kon_kelas)
    assert set(sebelum) == {p.kode for p in katalog.DAFTAR_PAKET}
    assert [c.ada_tagihan_terbuka for c in sebelum.values()] == [False, False]
    assert (sebelum["mini"].rincian.nominal, sebelum["private"].rincian.nominal) == (251_000, 591_000)
    tagih(kon_kelas, 1, "mini")
    sesudah = kartu(kon_kelas)
    assert (sesudah["mini"].ada_tagihan_terbuka, sesudah["private"].ada_tagihan_terbuka) == (True, False)
    assert sesudah["mini"].rincian.nominal == 251_000                   # rincian tersimpan di tagihan itu
    assert sesudah["private"].rincian.nominal == 640_000                # deposit sudah dipegang tagihan mini


def test_kartu_tidak_menulis_apa_pun(kon_kelas):
    peta_lunas(kon_kelas, 1)
    kartu(kon_kelas)
    assert baris(kon_kelas, "kelas_order") == [] and not kon_kelas.in_transaction


def test_kartu_dan_tagihan_anak_milik_akun_lain_berperilaku_tidak_ada(kon_kelas):
    tagih(kon_kelas, 1, "mini", akun=AKUN_A)
    sebelum = baris(kon_kelas, "kelas_order")
    with pytest.raises(d.PesananTidakDitemukan):
        kelas_store.kartu_paket(kon_kelas, AKUN_B, 1, KINI)
    with pytest.raises(d.PesananTidakDitemukan):
        tagih(kon_kelas, 1, "private", akun=AKUN_B)
    assert baris(kon_kelas, "kelas_order") == sebelum


# --- buat_tagihan: idempotensi, validasi, kode unik ---------------------------------------------------

def test_tagihan_terbuka_dikembalikan_apa_adanya_tanpa_menulis_lagi(kon_kelas):
    pertama = tagih(kon_kelas, 1, "mini")
    kedua = tagih(kon_kelas, 1, "mini", sekarang=SESUDAH_UPLOAD)
    assert kedua == pertama
    assert len(baris(kon_kelas, "kelas_order")) == len(baris(kon_kelas, "kelas_tagihan")) == 1


def test_paket_lain_dan_anak_lain_mendapat_tagihan_sendiri_dengan_kode_berbeda_di_nominal_sama(kon_kelas):
    a, b = tagih(kon_kelas, 1, "mini"), tagih(kon_kelas, 2, "mini")
    assert a.rincian.nominal == b.rincian.nominal == 300_000
    assert a.total != b.total and a.kode_unik != b.kode_unik
    assert tagih(kon_kelas, 1, "private").order_id != a.order_id


def test_tagihan_baru_sesudah_yang_lama_kedaluwarsa(kon_kelas):
    lama = tagih(kon_kelas, 1, "mini")
    baru = tagih(kon_kelas, 1, "mini", sekarang=SESUDAH_JENDELA)
    assert baru.order_id != lama.order_id and baru.status == "belum_bayar"
    assert baru.kode_unik == lama.kode_unik == 1                         # kode lama sudah dilepas


@pytest.mark.parametrize("paket", ["vip", "", None, 3, "MINI", "mini ", ["mini"]])
def test_paket_asing_ditolak_tanpa_menyentuh_db(kon_kelas, paket):
    with pytest.raises(d.PesananDataTidakSah):
        kelas_store.buat_tagihan(kon_kelas, AKUN_A, 1, paket, KINI)
    assert baris(kon_kelas, "kelas_order") == []


@pytest.mark.parametrize("akun,siswa", [("akun_x", 1), (None, 1), (AKUN_A, 0), (AKUN_A, "1"), (AKUN_A, True),
                                        (AKUN_A, None)])
def test_identitas_tidak_sah_ditolak(kon_kelas, akun, siswa):
    with pytest.raises(d.PesananDataTidakSah):
        kelas_store.buat_tagihan(kon_kelas, akun, siswa, "mini", KINI)
    assert baris(kon_kelas, "kelas_order") == []


def test_kode_unik_acak_server_dalam_rentang_dan_nominal_tidak_pernah_dari_pemanggil(kon_kelas):
    totals = set()
    for siswa in range(1, 31):
        tagihan = kelas_store.buat_tagihan(kon_kelas, AKUN_A, siswa, "private", KINI)
        assert 640_000 < tagihan.total <= 640_999 and tagihan.total == 640_000 + tagihan.kode_unik
        totals.add(tagihan.total)
    assert len(totals) == 30                                              # tidak ada nominal kembar yang dipegang


def test_kode_unik_habis_menolak_tanpa_menulis(kon_kelas, monkeypatch):
    monkeypatch.setattr(k, "KODE_MAKS", 2)
    tagih(kon_kelas, 1)
    tagih(kon_kelas, 2)
    with pytest.raises(k.KodeUnikHabis):
        tagih(kon_kelas, 3)
    assert len(baris(kon_kelas, "kelas_order")) == 2


@pytest.mark.parametrize("kode", [0, 1000, "5", None, 5.0])
def test_kode_unik_suntikan_tak_bebas_ditolak(kon_kelas, kode):
    with pytest.raises(d.PesananDataTidakSah):
        kelas_store.buat_tagihan(kon_kelas, AKUN_A, 1, "mini", KINI, acak=lambda bebas: kode)
    assert baris(kon_kelas, "kelas_order") == []


def test_tagihan_tidak_pernah_nol_atau_negatif_dan_rentang_tidak_tumpang_tindih_produk_lain(kon_kelas):
    peta_lunas(kon_kelas, 1)
    semua = []
    for siswa, paket in ((1, "mini"), (2, "private"), (3, "mini")):
        semua.append(tagih(kon_kelas, siswa, paket))
    assert all(t.rincian.nominal > 0 and t.total > t.rincian.nominal for t in semua)
    assert all(not (49_000 < t.total <= 49_999) and not (39_000 < t.total <= 39_999)
               and not (349_000 < t.total <= 349_999) for t in semua)


# --- bacaan: tagihan_dari, tagihan_terbuka, berakhir_aktif -------------------------------------------

def test_tagihan_dari_dan_terbuka_mengembalikan_tagihan_yang_sama(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    assert kelas_store.tagihan_dari(kon_kelas, AKUN_A, tagihan.order_id, KINI) == tagihan
    assert kelas_store.tagihan_terbuka(kon_kelas, AKUN_A, 1, "mini", KINI) == tagihan
    assert kelas_store.tagihan_terbuka(kon_kelas, AKUN_A, 1, "private", KINI) is None
    assert kelas_store.tagihan_terbuka(kon_kelas, AKUN_B, 1, "mini", KINI) is None


def test_tagihan_dari_order_orang_lain_tak_ada_dan_id_salah_tak_terbedakan_dan_tanpa_efek(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    sebelum = {t: baris(kon_kelas, t) for t in ("kelas_order", "kelas_tagihan", "kelas_bukti")}
    galat = []
    for akun, oid in ((AKUN_B, tagihan.order_id), (AKUN_A, k.PREFIX_ORDER + "0" * 32), (AKUN_A, "kor_xyz"),
                      (AKUN_A, None), ("akun_xyz", tagihan.order_id), (None, tagihan.order_id)):
        with pytest.raises(d.PesananTidakDitemukan) as info:
            kelas_store.tagihan_dari(kon_kelas, akun, oid, KINI)
        galat.append((type(info.value), str(info.value)))
    assert len(set(galat)) == 1
    assert {t: baris(kon_kelas, t) for t in sebelum} == sebelum


def test_status_turunan_tagihan_dan_urutannya(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    status = lambda kini: kelas_store.tagihan_dari(kon_kelas, AKUN_A, tagihan.order_id, kini).status  # noqa: E731
    assert status(KINI) == "belum_bayar"
    assert status(SESUDAH_JENDELA) == "kedaluwarsa"
    unggah(kon_kelas, 1, "mini", 1)
    assert status(KINI) == "menunggu" and status(SESUDAH_JENDELA) == "menunggu"   # menunggu tidak kedaluwarsa


def test_berakhir_aktif_milik_akun_dan_paket_yang_tepat(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_A, 1, "mini", SESUDAH_UPLOAD) == "2026-12-20T09:30:00"
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_A, 1, "private", SESUDAH_UPLOAD) is None
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_B, 1, "mini", SESUDAH_UPLOAD) is None
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_A, 1, "mini", "2026-12-20T09:30:00") is None
    assert kelas_store.berakhir_aktif(kon_kelas, AKUN_A, 1, "mini", "2026-11-20T09:29:59") is None


# --- bukti --------------------------------------------------------------------------------------------

def test_bukti_pertama_membuat_status_menunggu_dan_replay_sha_sama_tidak_menggandakan(kon_kelas):
    tagih(kon_kelas, 1, "mini")
    pertama = unggah(kon_kelas, 1, "mini", 1)
    assert pertama["baru"] is True and pertama["status"] == "menunggu"
    ulang = kelas_store.catat_bukti(kon_kelas, AKUN_A, 1, "mini", MIME, UKURAN, sha(1), berkas(9), SESUDAH_UPLOAD)
    assert ulang == {"bukti_id": pertama["bukti_id"], "status": "menunggu", "baru": False}
    assert len(baris(kon_kelas, "kelas_bukti")) == 1


def test_bukti_tanpa_tagihan_terbuka_atau_milik_akun_lain_konflik_identik_tanpa_efek(kon_kelas):
    tagih(kon_kelas, 1, "mini", akun=AKUN_A)
    galat = []
    for akun, siswa, paket in ((AKUN_B, 1, "mini"), (AKUN_A, 2, "mini"), (AKUN_A, 1, "private")):
        with pytest.raises(k.KelasKonflik) as info:
            kelas_store.catat_bukti(kon_kelas, akun, siswa, paket, MIME, UKURAN, sha(1), berkas(1), SESUDAH_UPLOAD)
        galat.append(str(info.value))
    assert len(set(galat)) == 1 and baris(kon_kelas, "kelas_bukti") == []


def test_bukti_di_luar_jendela_bayar_ditolak(kon_kelas):
    tagih(kon_kelas, 1, "mini")
    with pytest.raises(k.KelasKonflik):
        unggah(kon_kelas, 1, "mini", 1, sekarang=SESUDAH_JENDELA)
    assert baris(kon_kelas, "kelas_bukti") == []


def test_bukti_maksimal_lima_per_order(kon_kelas):
    tagih(kon_kelas, 1, "mini")
    for n in range(1, 6):
        unggah(kon_kelas, 1, "mini", n)
    with pytest.raises(k.BatasBukti):
        unggah(kon_kelas, 1, "mini", 6)
    assert len(baris(kon_kelas, "kelas_bukti")) == 5


def test_berkas_bukti_tidak_dipakai_ulang_di_order_lain_maupun_di_bukti_peta(kon_kelas):
    tagih(kon_kelas, 1, "mini")
    tagih(kon_kelas, 2, "mini")
    unggah(kon_kelas, 1, "mini", 1)
    with pytest.raises(k.KelasKonflik):
        unggah(kon_kelas, 2, "mini", 1)                                   # sha sama dengan bukti order lain
    transfer_kit.unggah(kon_kelas, transfer_kit.tagihan(kon_kelas, 7)[0], 7)
    with pytest.raises(k.KelasKonflik):
        kelas_store.catat_bukti(kon_kelas, AKUN_A, 2, "mini", MIME, UKURAN, transfer_kit.sha(7), berkas(2),
                                SESUDAH_UPLOAD)
    assert len(baris(kon_kelas, "kelas_bukti")) == 1


@pytest.mark.parametrize("ganti", [dict(mime="text/html"), dict(ukuran=0), dict(ukuran=10 ** 9),
                                   dict(sha256="xyz"), dict(nama_tersimpan="../x")])
def test_metadata_bukti_tidak_sah_ditolak_sebelum_db(kon_kelas, ganti):
    tagih(kon_kelas, 1, "mini")
    argumen = dict(mime=MIME, ukuran=UKURAN, sha256=sha(1), nama_tersimpan=berkas(1))
    argumen.update(ganti)
    with pytest.raises(d.PesananDataTidakSah):
        kelas_store.catat_bukti(kon_kelas, AKUN_A, 1, "mini", argumen["mime"], argumen["ukuran"],
                                argumen["sha256"], argumen["nama_tersimpan"], SESUDAH_UPLOAD)
    assert baris(kon_kelas, "kelas_bukti") == []


def test_bukti_tidak_diterima_setelah_lunas_dan_bukti_lama_tidak_bisa_diganti(kon_kelas):
    lunas(kon_kelas, 1, "mini", 1)
    with pytest.raises(k.KelasKonflik):
        unggah(kon_kelas, 1, "mini", 2)
    assert len(baris(kon_kelas, "kelas_bukti")) == 1
    with pytest.raises(Exception):
        kon_kelas.execute("UPDATE kelas_bukti SET sha256=?", (sha(5),))
    with pytest.raises(Exception):
        kon_kelas.execute("DELETE FROM kelas_bukti")


def test_antrean_urut_bukti_terlama_dan_hanya_yang_menunggu(kon_kelas):
    tagih(kon_kelas, 3, "mini")                                         # tanpa bukti: tidak masuk
    menunggu(kon_kelas, 1, "private", 1, sekarang="2026-11-20T08:00:00", unggah_pada="2026-11-20T08:30:00")
    menunggu(kon_kelas, 2, "mini", 2, sekarang=KINI)
    lunas(kon_kelas, 4, "mini", 4)                                       # sudah diputuskan: tidak masuk
    antre = kelas_store.antrean(kon_kelas)
    assert [(i.siswa_id, i.kode_paket) for i in antre] == [(1, "private"), (2, "mini")]
    assert all(isinstance(i, katalog.ItemAntrean) and i.total > 0 and i.bukti_terakhir for i in antre)
    assert antre[0].bukti_terakhir <= antre[1].bukti_terakhir


# --- satu tagihan terbuka per anak lintas paket (opsi untuk jalur HTTP, atomik di transaksi yang sama) ----------

def test_opsi_tolak_paket_lain_terbuka_menolak_paket_kedua_dan_idempoten_untuk_paket_sama(kon_kelas):
    pertama = tagih(kon_kelas, 1, "mini")
    with pytest.raises(k.KelasKonflik):
        kelas_store.buat_tagihan(kon_kelas, AKUN_A, 1, "private", KINI, acak=lambda bebas: bebas[0],
                                 tolak_paket_lain_terbuka=True)
    assert kelas_store.tagihan_terbuka(kon_kelas, AKUN_A, 1, "private", KINI) is None
    ulang = kelas_store.buat_tagihan(kon_kelas, AKUN_A, 1, "mini", KINI, acak=lambda bebas: bebas[0],
                                     tolak_paket_lain_terbuka=True)
    assert ulang.order_id == pertama.order_id


def test_tanpa_opsi_paket_lain_tetap_boleh_terbuka_bersamaan(kon_kelas):
    tagih(kon_kelas, 1, "mini")
    assert tagih(kon_kelas, 1, "private").kode_paket == "private"
