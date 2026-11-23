"""Langganan Latihan Harian dari akun anak (F5) lewat HTTP nyata: sakelar, palang, isolasi, tagihan, bukti, status.

Efek (atau ketiadaannya) dibuktikan dari DB dan folder berkas, bukan hanya kode status. Data sintetis di tmp_path.
"""
from __future__ import annotations

import re

import pytest

import akses_harian
import database
import harian_langganan_putusan as putusan
import harian_langganan_store as store
from bukti_kit import JPEG, PDF, PNG, TEKS_PALSU
from harian_kit import (AWAL, BUAT, BUKTI, KOSONG, M, SANDI, TABEL, berkas_harian, buat, buat_murid, halaman, hidup,  # noqa: F401
                        hitung, jam, kirim, mati, minta_mentah, satu_order, semua_berkas, server, token, unggah)

ADMIN = "admin_sintetis"


@pytest.fixture()
def dua(hidup):
    hidup.a = buat_murid(hidup, "murid-a", "Anak Alfa")
    hidup.b = buat_murid(hidup, "murid-b", "Anak Beta")
    return hidup


def tak_dikenal(server, akun=None, data=None):
    return minta_mentah(server, "/murid/tidak-ada-rute", akun, data)[:2]


def teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def putuskan_setuju(server, murid, waktu=AWAL):
    with server.buka() as kon:
        order = satu_order_id(kon)
        bukti_id = kon.execute("SELECT MAX(id) FROM harian_bukti").fetchone()[0]
        putusan.setujui(kon, order, ADMIN, waktu, bukti_dilihat=bukti_id)


def satu_order_id(kon):
    return kon.execute("SELECT id FROM harian_order ORDER BY dibuat DESC,id DESC").fetchone()[0]


# --- sakelar, sesi, peran ----------------------------------------------------------------

def test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal(mati):
    murid = buat_murid(mati, "murid-a", "Anak Alfa")
    harap_get = tak_dikenal(mati, murid.akun)
    for jalur in (M, BUAT, BUKTI):
        assert minta_mentah(mati, jalur, murid.akun)[:2] == harap_get, jalur
    harap_post = tak_dikenal(mati, murid.akun, {"x": "1"})
    for jalur in (BUAT, BUKTI):
        assert minta_mentah(mati, jalur, murid.akun, {"token": "x", "paket": "bulanan"})[:2] == harap_post, jalur
    assert hitung(mati) == KOSONG


def test_anonim_get_303_ke_masuk_dan_post_401_tanpa_efek(dua):
    kode, _isi, tajuk = minta_mentah(dua, M)
    assert (kode, tajuk.get("Location")) == (303, "/masuk")
    assert minta_mentah(dua, BUAT, None, {"token": "x", "paket": "bulanan"})[0] == 401
    assert hitung(dua) == KOSONG


def test_guru_tidak_dilayani_modul_murid(dua):
    kode, isi, _ = minta_mentah(dua, M, ("guru", "sandi-guru-panjang-123"))
    assert "Langganan Latihan Harian" not in isi
    assert hitung(dua) == KOSONG


def test_akun_murid_tanpa_siswa_tertaut_jatuh_ke_jalur_asing(hidup):
    murid = buat_murid(hidup, "murid-yatim", "x", tertaut=False)
    assert minta_mentah(hidup, M, murid.akun)[:2] == tak_dikenal(hidup, murid.akun)
    assert buat(hidup, murid)[:2] == tak_dikenal(hidup, murid.akun, {"x": "1"})
    assert hitung(hidup) == KOSONG


def test_lintas_situs_post_ditolak_sebelum_efek(dua):
    kode, _, _ = minta_mentah(dua, BUAT, dua.a.akun, {"token": token(dua.a.akun, "harian_buat:bulanan"),
                                                       "paket": "bulanan"}, {"Sec-Fetch-Site": "cross-site"})
    assert kode in (403, 400)
    assert hitung(dua) == KOSONG


# --- halaman ------------------------------------------------------------------------------

def test_halaman_status_gratis_dan_dua_paket_dengan_harga_server(dua):
    isi = halaman(dua, dua.a)
    t = teks(isi)
    assert "Belum berlangganan" in t and "Rp39.000" in t and "Rp349.000" in t
    assert isi.count('action="/murid/langganan/buat"') == 2
    assert "Pilih Bulanan" in t and "Pilih Tahunan" in t
    assert "Bank Contoh" not in t  # rekening baru tampil bersama tagihan


def test_kueri_siswa_diabaikan_get_dan_post(dua):
    buat(dua, dua.b)
    unggah(dua, dua.b)
    putuskan_setuju(dua, dua.b)
    kode, isi, _ = minta_mentah(dua, M + "?siswa_id=%d&order=x" % dua.b.siswa_id, dua.a.akun)
    assert kode == 200 and "Belum berlangganan" in isi and "aktif sampai" not in isi
    data = {"token": token(dua.a.akun, "harian_buat:tahunan"), "paket": "tahunan"}
    assert minta_mentah(dua, BUAT + "?siswa_id=%d" % dua.b.siswa_id, dua.a.akun, data)[0] == 303
    with dua.buka() as kon:
        assert [r[0] for r in kon.execute("SELECT siswa_id FROM harian_order WHERE paket='tahunan'")] == [dua.a.siswa_id]


@pytest.fixture()
def tanpa_rekening(mati, monkeypatch):
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    return mati


def test_rekening_kosong_halaman_jujur_dan_post_404_tanpa_efek(tanpa_rekening):
    murid = buat_murid(tanpa_rekening, "murid-a", "Anak Alfa")
    isi = halaman(tanpa_rekening, murid)
    assert "belum dibuka" in teks(isi) and "/murid/langganan/buat" not in isi
    assert buat(tanpa_rekening, murid)[:2][0] == 404
    assert unggah(tanpa_rekening, murid)[0] == 404
    assert hitung(tanpa_rekening) == KOSONG and semua_berkas(tanpa_rekening) == []


# --- buat tagihan -------------------------------------------------------------------------

def test_buat_tagihan_nominal_dari_server_dan_halaman_tagihan(dua):
    kode, _, tajuk = buat(dua, dua.a, "bulanan")
    assert (kode, tajuk["Location"]) == (303, M)
    order = satu_order(dua)
    assert (order["siswa_id"], order["paket"], order["rupiah"]) == (dua.a.siswa_id, "bulanan", 39000)
    assert order["nominal_transfer"] == 39000 + order["kode_unik"] and 1 <= order["kode_unik"] <= 999
    t = teks(halaman(dua, dua.a))
    assert "Rp39.%03d" % order["kode_unik"] in t.replace("Rp39.0", "Rp39.0")
    assert "Bank Contoh" in t and "1234 5678 90" in t and "PT Contoh Sintetis" in t
    assert "Unggah bukti" in t and "Pilih Bulanan" not in t
    assert "Batas waktu" in t and "24 November 2026 pukul 10.00 WIB" in t


def test_tahunan_nominal_349_ribu_plus_kode(dua):
    assert buat(dua, dua.a, "tahunan")[0] == 303
    order = satu_order(dua)
    assert order["rupiah"] == 349000 and 349000 < order["nominal_transfer"] < 350000


def test_nominal_tidak_bisa_dari_form(dua):
    kode, *_ = buat(dua, dua.a, ekstra={"nominal": "1000", "rupiah": "1"})
    assert kode == 400 and hitung(dua) == KOSONG
    kode, *_ = buat(dua, dua.a, ekstra={"siswa_id": str(dua.b.siswa_id)})
    assert kode == 400 and hitung(dua) == KOSONG
    kode, *_ = buat(dua, dua.a, ekstra={"paket": "1000"})
    assert kode == 400 and hitung(dua) == KOSONG


@pytest.mark.parametrize("paket", ["gratis", "", "BULANAN", "bulanan2"])
def test_paket_asing_400_tanpa_efek(dua, paket):
    assert buat(dua, dua.a, paket, tok=token(dua.a.akun, "harian_buat:bulanan"))[0] == 400
    assert hitung(dua) == KOSONG


def test_token_salah_atau_untuk_paket_lain_atau_akun_lain_ditolak(dua):
    assert buat(dua, dua.a, "bulanan", tok="1.salah")[0] == 403
    assert buat(dua, dua.a, "bulanan", tok=token(dua.a.akun, "harian_buat:tahunan"))[0] == 403
    assert buat(dua, dua.a, "bulanan", tok=token(dua.a.akun, "harian_bukti"))[0] == 403
    assert buat(dua, dua.a, "bulanan", tok=token(dua.b.akun, "harian_buat:bulanan"))[0] == 403
    assert buat(dua, dua.a, hapus=("token",))[0] == 400
    assert hitung(dua) == KOSONG


def test_satu_tagihan_per_anak_idempoten_dan_paket_lain_konflik(dua):
    assert buat(dua, dua.a, "bulanan")[0] == 303
    nominal = satu_order(dua)["nominal_transfer"]
    assert buat(dua, dua.a, "bulanan")[0] == 303
    assert hitung(dua)["harian_order"] == 1 and satu_order(dua)["nominal_transfer"] == nominal
    kode, isi, _ = buat(dua, dua.a, "tahunan")
    assert kode == 409 and hitung(dua)["harian_order"] == 1


def test_isolasi_murid_a_b_tagihan_status_dan_bukti(dua):
    buat(dua, dua.a, "bulanan")
    assert unggah(dua, dua.a)[0] == 303
    awal = hitung(dua)
    tb = teks(halaman(dua, dua.b))
    assert "Pilih Bulanan" in tb and "Unggah bukti" not in tb and "Bank Contoh" not in tb
    kode, isi, _ = unggah(dua, dua.b)
    assert kode == 409
    assert hitung(dua) == awal
    with dua.buka() as kon:
        assert {r[0] for r in kon.execute("SELECT DISTINCT siswa_id FROM harian_order")} == {dua.a.siswa_id}
    assert buat(dua, dua.b, "bulanan")[0] == 303
    kodes = {r[0] for r in database_baca(dua, "SELECT kode_unik FROM harian_tagihan")}
    assert len(kodes) == 2


def database_baca(server, sql):
    with server.buka() as kon:
        return kon.execute(sql).fetchall()


# --- unggah bukti ---------------------------------------------------------------------------

def test_laju_unggah_dibatasi_429_tanpa_efek(dua):
    buat(dua, dua.a)
    kode = [unggah(dua, dua.a, TEKS_PALSU)[0] for _ in range(8)]
    assert kode.count(415) == 6 and kode[6:] == [429, 429]
    assert hitung(dua)["harian_bukti"] == 0


def test_unggah_catat_bukti_di_subfolder_khusus_dan_status_menunggu(dua):
    buat(dua, dua.a)
    kode, _, tajuk = unggah(dua, dua.a, JPEG, nama_berkas="rahasia-klien.jpg")
    assert (kode, tajuk["Location"]) == (303, M)
    assert hitung(dua)["harian_bukti"] == 1
    assert len(berkas_harian(dua)) == 1 and len(semua_berkas(dua)) == 1
    assert semua_berkas(dua)[0].startswith("harian/")
    t = teks(halaman(dua, dua.a))
    assert "Bukti sudah kami terima" in t and "rahasia-klien" not in t
    assert "Unggah bukti" in t  # tetap boleh unggah bukti lebih baru (admin melihat yang terbaru)


@pytest.mark.parametrize("isi,kode", [(b"", 400), (TEKS_PALSU, 415), (b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10), 413)])
def test_unggah_berkas_tidak_sah_ditolak_tanpa_efek(dua, isi, kode):
    buat(dua, dua.a)
    awal = hitung(dua)
    assert unggah(dua, dua.a, isi)[0] == kode
    assert hitung(dua) == awal and semua_berkas(dua) == []


def test_unggah_tipe_diputuskan_dari_isi_bukan_nama_atau_tipe_klien(dua):
    buat(dua, dua.a)
    assert unggah(dua, dua.a, TEKS_PALSU, nama_berkas="x.jpg", tipe="image/jpeg")[0] == 415
    assert unggah(dua, dua.a, PDF, nama_berkas="x.txt", tipe="text/plain")[0] == 303
    with dua.buka() as kon:
        assert kon.execute("SELECT mime FROM harian_bukti").fetchone()[0] == "application/pdf"


def test_unggah_tanpa_tagihan_atau_token_salah_tanpa_efek(dua):
    assert unggah(dua, dua.a)[0] == 409
    buat(dua, dua.a)
    assert unggah(dua, dua.a, tok="1.salah")[0] == 403
    assert unggah(dua, dua.a, tok=token(dua.a.akun, "harian_buat:bulanan"))[0] == 403
    assert hitung(dua)["harian_bukti"] == 0 and semua_berkas(dua) == []


def test_unggah_berkas_sama_tidak_ganda_dan_batas_lima(dua, monkeypatch):
    buat(dua, dua.a)
    assert unggah(dua, dua.a, JPEG)[0] == 303
    assert unggah(dua, dua.a, JPEG)[0] == 303
    assert hitung(dua)["harian_bukti"] == 1 and len(berkas_harian(dua)) == 1
    for i in range(4):
        assert unggah(dua, dua.a, JPEG + bytes([i + 1]))[0] == 303
    assert hitung(dua)["harian_bukti"] == 5
    import pesanan_http
    monkeypatch.setattr(pesanan_http, "_laju", {})
    assert unggah(dua, dua.a, JPEG + b"zz")[0] == 409
    assert hitung(dua)["harian_bukti"] == 5 and len(berkas_harian(dua)) == 5


def test_unggah_setelah_jendela_habis_ditolak(dua, jam):
    buat(dua, dua.a)
    jam.maju_jam(25)
    assert unggah(dua, dua.a)[0] == 409
    assert hitung(dua)["harian_bukti"] == 0 and semua_berkas(dua) == []


def test_multipart_bentuk_aneh_ditolak(dua):
    from bukti_kit import bagian, multipart
    from harian_kit import minta_multipart
    buat(dua, dua.a)
    tok = token(dua.a.akun, "harian_bukti")
    ekstra = multipart([bagian("token", tok.encode()), bagian("berkas", JPEG, nama_berkas="a.jpg"),
                        bagian("order_id", b"hor_" + b"0" * 32)])
    assert minta_multipart(dua, BUKTI, dua.a.akun, ekstra)[0] == 400
    assert hitung(dua)["harian_bukti"] == 0


# --- status: tolak, setuju, kedaluwarsa --------------------------------------------------------

def test_ditolak_alasan_tampil_dan_bisa_unggah_ulang(dua):
    buat(dua, dua.a)
    unggah(dua, dua.a)
    with dua.buka() as kon:
        putusan.tolak(kon, satu_order_id(kon), ADMIN, "Nominal kurang tiga digit", AWAL, bukti_dilihat=1)
    t = teks(halaman(dua, dua.a))
    assert "Nominal kurang tiga digit" in t and "Unggah ulang bukti" in t
    assert unggah(dua, dua.a, PNG)[0] == 303
    assert "Bukti sudah kami terima" in teks(halaman(dua, dua.a))


def test_setuju_halaman_aktif_sampai_tanggal_dan_akses_langganan(dua):
    buat(dua, dua.a)
    unggah(dua, dua.a)
    putuskan_setuju(dua, dua.a)
    t = teks(halaman(dua, dua.a))
    assert "aktif sampai 23 Des 2026" in t and "Perpanjang Bulanan" in t
    with dua.buka() as kon:
        akses = akses_harian.akses(kon, dua.a.siswa_id, AWAL)
        assert (akses.sumber, akses.tanpa_batas) == ("langganan", True)
        assert akses_harian.akses(kon, dua.b.siswa_id, AWAL).sumber == "gratis"


def test_kedaluwarsa_tanpa_bukti_boleh_tagihan_baru(dua, jam):
    buat(dua, dua.a)
    jam.maju_jam(25)
    assert "Pilih Bulanan" in teks(halaman(dua, dua.a))
    assert buat(dua, dua.a)[0] == 303 and hitung(dua)["harian_order"] == 2


def test_nomor_wa_tidak_pernah_dirender(dua):
    import kontak_akun
    with dua.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        kontak_akun.simpan(kon, dua.a.id_akun, "6281234567890", "2026-11-18T09:00:00")
        kon.commit()
    buat(dua, dua.a)
    isi = halaman(dua, dua.a)
    assert "81234567890" not in isi and "wa.me" not in isi


def test_retensi_paket_coba_tidak_menyentuh_subfolder_harian(dua):
    """Sapuan yatim Paket Coba membuang berkas 32-hex tak dirujuk di folder bukti, bukan isi subfolder harian."""
    import os
    import admin_store
    import pesanan_retensi
    import pesanan_transfer
    import schema_pesanan
    import schema_transfer
    buat(dua, dua.a)
    unggah(dua, dua.a)
    lama = dua.folder / "harian" / berkas_harian(dua)[0]
    os.utime(lama, (1, 1))
    yatim = dua.folder / ("f" * 32)
    yatim.write_bytes(b"x")
    os.utime(yatim, (1, 1))
    schema_pesanan.migrasikan(admin_store.BAWAAN)
    schema_transfer.migrasikan(admin_store.BAWAAN)
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan_retensi.sapu(kon, dua.folder, "2026-12-30T00:00:00")
    assert not yatim.exists()
    assert lama.exists()
