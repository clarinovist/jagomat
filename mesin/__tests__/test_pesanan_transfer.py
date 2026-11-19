"""Logika inti transfer rekening: tagihan unik, bukti, keputusan admin, retensi bukti."""
import sqlite3

import pytest

import pesanan
import pesanan_transfer as tf
from pesanan_kit import (AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, buat, hitung, operasi,
                         ord_id, terapkan)
from transfer_kit import (ADMIN, ADMIN_B, MIME, SESUDAH_UPLOAD, UKURAN, berkas, menunggu, sha,
                          siapkan_db_transfer, tagihan, unggah)

SEMUA_TABEL = ("transfer_tagihan", "transfer_bukti", "transfer_bukti_hapus",
               "transfer_verifikasi", "transfer_lunas", "transfer_refund")


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


def status(kon, order, akun=AKUN_A, sekarang=SESUDAH_UPLOAD):
    return pesanan.status_order(kon, order["order_id"], akun, sekarang)["status"]


def isi(kon):
    return {t: hitung(kon, t) for t in SEMUA_TABEL}


def terendah(kandidat):
    return min(kandidat)


# --- tagihan ----------------------------------------------------------------

def test_tagihan_nominal_adalah_rupiah_paket_ditambah_kode_unik(kon):
    order, tag = tagihan(kon, 1)
    assert 1 <= tag["kode_unik"] <= 999
    assert tag["nominal_transfer"] == pesanan.RUPIAH_PAKET + tag["kode_unik"]
    assert tag["baru"] is True and tag["urutan"] == 1
    assert order["rupiah"] == 49000       # order.rupiah tidak pernah berubah
    assert status(kon, order, sekarang=SEKARANG) == "belum_bayar"


def test_tagihan_idempoten_per_order_dan_jendela(kon):
    order, pertama = tagihan(kon, 1)
    ulang = tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SEKARANG)
    assert ulang["baru"] is False
    assert {k: ulang[k] for k in ("kode_unik", "nominal_transfer", "urutan")} == \
        {k: pertama[k] for k in ("kode_unik", "nominal_transfer", "urutan")}
    assert hitung(kon, "transfer_tagihan") == 1


def test_tagihan_order_milik_akun_lain_atau_id_rusak_identik_tanpa_tulis(kon):
    order = buat(kon, 1)
    sebelum = isi(kon)
    galat = []
    for oid, akun in ((order["order_id"], AKUN_B), (ord_id(99), AKUN_A), ("rusak", AKUN_A),
                      (order["order_id"], "rusak")):
        with pytest.raises(pesanan.PesananTidakDitemukan) as info:
            tf.buat_tagihan_transfer(kon, oid, akun, SEKARANG)
        galat.append(str(info.value))
    assert len(set(galat)) == 1
    assert isi(kon) == sebelum


def test_nominal_unik_antar_order_yang_masih_menunggu(kon):
    nominal = set()
    for n in range(1, 8):
        _, tag = tagihan(kon, n, acak=terendah)
        nominal.add(tag["nominal_transfer"])
    assert len(nominal) == 7
    assert nominal == {49000 + k for k in range(1, 8)}


def test_kode_unik_habis_gagal_jelas_tanpa_tulis(kon, monkeypatch):
    monkeypatch.setattr(tf, "KODE_MAKS", 2)
    tagihan(kon, 1, acak=terendah)
    tagihan(kon, 2, acak=terendah)
    order = buat(kon, 3)
    sebelum = isi(kon)
    with pytest.raises(tf.PesananKodeUnikHabis):
        tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SEKARANG, acak=terendah)
    assert isi(kon) == sebelum
    assert issubclass(tf.PesananKodeUnikHabis, pesanan.PesananKonflik)


def test_pengacak_yang_memilih_kode_tidak_bebas_ditolak(kon):
    tagihan(kon, 1, acak=terendah)
    order = buat(kon, 2)
    with pytest.raises(pesanan.PesananDataTidakSah):
        tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SEKARANG, acak=lambda _: 1)
    assert hitung(kon, "transfer_tagihan") == 1


def test_pengacak_bawaan_memakai_secrets_dan_menghasilkan_kode_sah(kon):
    kode = {tagihan(kon, n)[1]["kode_unik"] for n in range(1, 6)}
    assert len(kode) == 5 and all(1 <= k <= 999 for k in kode)


def test_tagihan_order_kedaluwarsa_tanpa_bukti_ditolak(kon):
    order = buat(kon, 1)
    with pytest.raises(pesanan.PesananKonflik):
        tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SESUDAH_KEDALUWARSA)
    assert hitung(kon, "transfer_tagihan") == 0


def test_nominal_dilepas_setelah_kedaluwarsa_tanpa_bukti(kon):
    _, lama = tagihan(kon, 1, acak=terendah)
    _, baru = tagihan(kon, 2, sekarang=SESUDAH_KEDALUWARSA, acak=terendah)
    assert baru["kode_unik"] == lama["kode_unik"]


def test_nominal_tetap_dipegang_selama_menunggu_verifikasi_walau_lewat_jendela(kon):
    order, lama = tagihan(kon, 1, acak=terendah)
    unggah(kon, order, 1)
    _, baru = tagihan(kon, 2, sekarang=SESUDAH_KEDALUWARSA, acak=terendah)
    assert baru["kode_unik"] != lama["kode_unik"]


def test_jendela_dibuka_ulang_mendapat_tagihan_baru_tanpa_tabrakan(kon):
    order1, lama = tagihan(kon, 1, acak=terendah)
    _, order2_tag = tagihan(kon, 2, sekarang=SESUDAH_KEDALUWARSA, acak=terendah)
    assert order2_tag["kode_unik"] == lama["kode_unik"]          # kode order 1 sudah dilepas
    pesanan.buka_jendela_ulang(kon, order1["order_id"], AKUN_A, SESUDAH_KEDALUWARSA, operasi(1))
    baru = tf.buat_tagihan_transfer(kon, order1["order_id"], AKUN_A, SESUDAH_KEDALUWARSA,
                                    acak=terendah)
    assert baru["urutan"] == 2 and baru["baru"] is True
    assert baru["nominal_transfer"] != order2_tag["nominal_transfer"]


def test_tagihan_ditolak_bila_order_sudah_lunas_midtrans(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    with pytest.raises(pesanan.PesananKonflik):
        tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SEKARANG)
    assert hitung(kon, "transfer_tagihan") == 0


def test_ambil_tagihan_hanya_untuk_pemilik_dan_none_bila_belum_ada(kon):
    order = buat(kon, 1)
    assert tf.ambil_tagihan(kon, order["order_id"], AKUN_A) is None
    _, tag = tagihan(kon, 2)
    baca = tf.ambil_tagihan(kon, tag["order_id"], AKUN_A)
    assert baca["nominal_transfer"] == tag["nominal_transfer"]
    with pytest.raises(pesanan.PesananTidakDitemukan):
        tf.ambil_tagihan(kon, tag["order_id"], AKUN_B)


# --- bukti ------------------------------------------------------------------

def test_catat_bukti_membuat_status_menunggu_verifikasi(kon):
    order, _ = tagihan(kon, 1)
    hasil = unggah(kon, order, 1)
    assert hasil["status"] == "menunggu_verifikasi" and hasil["baru"] is True
    baris = kon.execute("SELECT * FROM transfer_bukti WHERE id=?", (hasil["bukti_id"],)).fetchone()
    assert (baris["berkas"], baris["mime"], baris["ukuran"], baris["sha256"],
            baris["diunggah_oleh"]) == (berkas(1), MIME, UKURAN, sha(1), AKUN_A)


@pytest.mark.parametrize("ganti", [
    dict(mime="image/gif"), dict(mime=None), dict(ukuran=0), dict(ukuran=5 * 1024 * 1024 + 1),
    dict(ukuran=True), dict(ukuran="10"), dict(sha256="xyz"), dict(sha256="AB" * 32),
    dict(nama_tersimpan="foto-asli.jpg"), dict(nama_tersimpan="ab" * 15),
])
def test_catat_bukti_input_tidak_sah_ditolak_tanpa_tulis(kon, ganti):
    order, _ = tagihan(kon, 1)
    sebelum = isi(kon)
    with pytest.raises(pesanan.PesananDataTidakSah):
        unggah(kon, order, 1, **ganti)
    assert isi(kon) == sebelum


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "application/pdf"])
def test_catat_bukti_menerima_jpeg_png_pdf(kon, mime):
    order, _ = tagihan(kon, 1)
    assert unggah(kon, order, 1, mime=mime)["baru"] is True


def test_catat_bukti_tanpa_tagihan_atau_akun_lain_ditolak(kon):
    order = buat(kon, 1)
    sebelum = isi(kon)
    with pytest.raises(pesanan.PesananKonflik):
        unggah(kon, order, 1)
    with pytest.raises(pesanan.PesananTidakDitemukan):
        unggah(kon, order, 1, akun=AKUN_B)
    assert isi(kon) == sebelum


def test_catat_bukti_milik_akun_lain_tidak_ada_efek_samping(kon):
    order, _ = tagihan(kon, 1)
    sebelum = isi(kon)
    with pytest.raises(pesanan.PesananTidakDitemukan):
        unggah(kon, order, 1, akun=AKUN_B)
    assert isi(kon) == sebelum


def test_catat_bukti_dibatasi_lima_per_order(kon):
    order, _ = tagihan(kon, 1)
    for n in range(1, tf.MAKS_BUKTI + 1):
        unggah(kon, order, n)
    sebelum = isi(kon)
    with pytest.raises(tf.PesananBatasBukti):
        unggah(kon, order, 6)
    assert isi(kon) == sebelum
    assert issubclass(tf.PesananBatasBukti, pesanan.PesananKonflik)


def test_unggah_ulang_berkas_yang_sama_saat_menunggu_idempoten(kon):
    order, _ = tagihan(kon, 1)
    pertama = unggah(kon, order, 1)
    ulang = unggah(kon, order, 2, sha256=sha(1))
    assert ulang["baru"] is False and ulang["bukti_id"] == pertama["bukti_id"]
    assert hitung(kon, "transfer_bukti") == 1


def test_bukti_hanya_diterima_selama_jendela_bayar_terbuka(kon):
    order, _ = tagihan(kon, 1)
    with pytest.raises(pesanan.PesananKonflik):
        unggah(kon, order, 1, sekarang=SESUDAH_KEDALUWARSA)
    unggah(kon, order, 2)                              # masih terbuka
    with pytest.raises(pesanan.PesananKonflik):        # sudah menunggu, tetapi jendela habis
        unggah(kon, order, 3, sekarang=SESUDAH_KEDALUWARSA)
    assert hitung(kon, "transfer_bukti") == 1


def test_bukti_ditolak_bila_order_sudah_lunas_transfer(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        unggah(kon, order, 2)


# --- keputusan admin ----------------------------------------------------------

def test_setujui_membuat_lunas_dan_status_sudah_dibayar(kon):
    order, tag = menunggu(kon, 1)
    hasil = tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert hasil["status"] == "sudah_dibayar" and hasil["verifikasi_id"] >= 1
    lunas = kon.execute("SELECT * FROM transfer_lunas").fetchone()
    assert (lunas["order_id"], lunas["rupiah"], lunas["verifikasi_id"]) == \
        (order["order_id"], 49000, hasil["verifikasi_id"])
    putusan = kon.execute("SELECT * FROM transfer_verifikasi").fetchone()
    assert (putusan["keputusan"], putusan["admin_id"], putusan["alasan"]) == ("setuju", ADMIN, None)
    assert status(kon, order) == "sudah_dibayar"
    assert tag["nominal_transfer"] > 49000


def test_setujui_dua_kali_ditolak_tanpa_tulis(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    sebelum = isi(kon)
    with pytest.raises(pesanan.PesananKonflik):
        tf.setujui(kon, order["order_id"], ADMIN_B, SESUDAH_UPLOAD)
    assert isi(kon) == sebelum


def test_setujui_tanpa_bukti_atau_tanpa_tagihan_ditolak(kon):
    order, _ = tagihan(kon, 1)
    polos = buat(kon, 2)
    sebelum = isi(kon)
    for target in (order, polos):
        with pytest.raises(pesanan.PesananKonflik):
            tf.setujui(kon, target["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert isi(kon) == sebelum


def test_setujui_order_tak_dikenal_atau_admin_tak_sah(kon):
    order, _ = menunggu(kon, 1)
    with pytest.raises(pesanan.PesananTidakDitemukan):
        tf.setujui(kon, ord_id(404), ADMIN, SESUDAH_UPLOAD)
    for admin in ("", "spasi dalam", None, "x" * 65):
        with pytest.raises(pesanan.PesananDataTidakSah):
            tf.setujui(kon, order["order_id"], admin, SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_verifikasi") == 0


@pytest.mark.parametrize("alasan", [None, "", "   ", "bukti\x00buram", "baris\nbaru", "x" * 201, 5])
def test_tolak_wajib_alasan_sah_tanpa_tulis(kon, alasan):
    order, _ = menunggu(kon, 1)
    with pytest.raises(pesanan.PesananDataTidakSah):
        tf.tolak(kon, order["order_id"], ADMIN, alasan, SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_verifikasi") == 0
    assert status(kon, order) == "menunggu_verifikasi"


def test_tolak_membuat_status_ditolak_dan_memungkinkan_unggah_ulang(kon):
    order, _ = menunggu(kon, 1)
    hasil = tf.tolak(kon, order["order_id"], ADMIN, "  nominal tidak sesuai  ", SESUDAH_UPLOAD)
    assert hasil["status"] == "ditolak"
    assert kon.execute("SELECT alasan FROM transfer_verifikasi").fetchone()[0] == "nominal tidak sesuai"
    assert unggah(kon, order, 2)["status"] == "menunggu_verifikasi"
    assert tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)["status"] == "sudah_dibayar"


def test_tolak_dua_kali_tanpa_bukti_baru_ditolak(kon):
    order, _ = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        tf.tolak(kon, order["order_id"], ADMIN, "buram lagi", SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_verifikasi") == 1


def test_tolak_setelah_setuju_ditolak(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        tf.tolak(kon, order["order_id"], ADMIN, "terlambat", SESUDAH_UPLOAD)


def test_menunggu_verifikasi_tidak_kedaluwarsa_dan_setujui_tetap_sah_sesudah_jendela(kon):
    order, _ = menunggu(kon, 1)
    assert status(kon, order, sekarang=SESUDAH_KEDALUWARSA) == "menunggu_verifikasi"
    hasil = tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_KEDALUWARSA)
    assert hasil["status"] == "sudah_dibayar"


def test_ditolak_mengikuti_kedaluwarsa_dan_jendela_baru_membuat_belum_bayar(kon):
    order, _ = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    assert status(kon, order, sekarang=SESUDAH_UPLOAD) == "ditolak"
    assert status(kon, order, sekarang=SESUDAH_KEDALUWARSA) == "kedaluwarsa"
    pesanan.buka_jendela_ulang(kon, order["order_id"], AKUN_A, SESUDAH_KEDALUWARSA, operasi(1))
    assert status(kon, order, sekarang=SESUDAH_KEDALUWARSA) == "belum_bayar"


def test_setujui_ditolak_bila_order_sudah_lunas_midtrans(kon):
    order, _ = menunggu(kon, 1)
    terapkan(kon, order, 1)
    with pytest.raises(pesanan.PesananKonflik):
        tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_lunas") == 0


def test_bukti_menunggu_hanya_bukti_sesudah_keputusan_terakhir(kon):
    order, _ = menunggu(kon, 1)
    assert [b["berkas"] for b in tf.bukti_menunggu(kon, order["order_id"])] == [berkas(1)]
    tf.tolak(kon, order["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    assert tf.bukti_menunggu(kon, order["order_id"]) == ()
    unggah(kon, order, 2)
    assert [b["berkas"] for b in tf.bukti_menunggu(kon, order["order_id"])] == [berkas(2)]


# --- retensi bukti ------------------------------------------------------------

TIGA_PULUH_HARI = "2026-12-18T12:00:00"     # tepat 30 hari sesudah SESUDAH_UPLOAD
SEHARI_KURANG = "2026-12-18T11:59:59"


def test_bukti_belum_diputuskan_tidak_pernah_kedaluwarsa(kon):
    menunggu(kon, 1)
    assert tf.bukti_kedaluwarsa(kon, "2030-01-01T00:00:00") == ()


def test_bukti_kedaluwarsa_30_hari_sesudah_verifikasi(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert tf.bukti_kedaluwarsa(kon, SEHARI_KURANG) == ()
    hasil = tf.bukti_kedaluwarsa(kon, TIGA_PULUH_HARI)
    assert [(b["order_id"], b["berkas"]) for b in hasil] == [(order["order_id"], berkas(1))]
    assert tf.bukti_kedaluwarsa(kon, SEHARI_KURANG, hari=29)[0]["berkas"] == berkas(1)


@pytest.mark.parametrize("hari", [0, -1, True, "30", 1.5, None])
def test_bukti_kedaluwarsa_menolak_hari_tidak_sah(kon, hari):
    with pytest.raises(pesanan.PesananDataTidakSah):
        tf.bukti_kedaluwarsa(kon, TIGA_PULUH_HARI, hari=hari)


def test_bukti_yang_ditolak_juga_kedaluwarsa_dan_bukti_baru_belum(kon):
    order, _ = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    unggah(kon, order, 2, sekarang="2026-11-18T13:00:00")    # masih di jendela bayar; belum diputuskan
    assert [b["berkas"] for b in tf.bukti_kedaluwarsa(kon, TIGA_PULUH_HARI)] == [berkas(1)]


def test_tandai_dihapus_menulis_penanda_dan_idempoten(kon):
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    hasil = tf.tandai_dihapus(kon, 1, TIGA_PULUH_HARI)
    assert hasil == {"bukti_id": 1, "berkas": berkas(1), "baru": True}
    assert tf.tandai_dihapus(kon, 1, TIGA_PULUH_HARI)["baru"] is False
    assert hitung(kon, "transfer_bukti_hapus") == 1
    assert tf.bukti_kedaluwarsa(kon, TIGA_PULUH_HARI) == ()
    assert hitung(kon, "transfer_bukti") == 1       # metadata bukti tidak dihapus/diubah


def test_tandai_dihapus_menolak_bukti_belum_kedaluwarsa_belum_diputuskan_atau_tak_dikenal(kon):
    order, _ = menunggu(kon, 1)
    with pytest.raises(pesanan.PesananKonflik):
        tf.tandai_dihapus(kon, 1, TIGA_PULUH_HARI)           # belum diputuskan
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        tf.tandai_dihapus(kon, 1, SEHARI_KURANG)             # belum 30 hari
    with pytest.raises(pesanan.PesananTidakDitemukan):
        tf.tandai_dihapus(kon, 99, TIGA_PULUH_HARI)
    for buruk in (0, -1, True, "1"):
        with pytest.raises(pesanan.PesananDataTidakSah):
            tf.tandai_dihapus(kon, buruk, TIGA_PULUH_HARI)
    assert hitung(kon, "transfer_bukti_hapus") == 0


def test_buka_menolak_koneksi_baca_untuk_tulis_dan_tanpa_transfer(tmp_path):
    import admin_store
    from pesanan_kit import siapkan_db
    with pytest.raises(admin_store.StoreBelumSiap):
        with tf.buka(siapkan_db(tmp_path)):
            pass
    with tf.buka(siapkan_db_transfer(tmp_path / "lain")) as baca:
        with pytest.raises(sqlite3.OperationalError):
            baca.execute("INSERT INTO transfer_refund VALUES('a','b','c','d','e')")
