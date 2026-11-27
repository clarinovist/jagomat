"""Paket Belajar 1 Bulan dari akun anak lewat HTTP nyata: sakelar, palang, isolasi, tagihan, bukti, status, deposit.

Efek (atau ketiadaannya) dibuktikan dari DB admin sintetis dan folder berkas, bukan hanya kode status.
"""
from __future__ import annotations

import re
import sqlite3
import time

import pytest

import admin_store as _admin_store
import database
import kelas_dasar
import kelas_murid_http
import kelas_putusan
import kelas_store
import paket_belajar_gate
import pesanan
import pesanan_dasar
import pesanan_http
import sessions
from pesanan_kit import buat as buat_peta, terapkan as terapkan_peta
from bukti_kit import JPEG, PDF, PNG, TEKS_PALSU
from kelas_http_kit import (AWAL, BUAT, BUKTI, KOSONG, M, TABEL, ADMIN, baca_admin, berkas_kelas, bukti_terakhir,  # noqa: F401
                            buat, buat_dan_unggah, buat_murid, halaman, hitung, jam, kidup, kirim, kmati,
                            minta_mentah, order_terakhir, peta_lunas_untuk, semua_berkas, server, tagihan_halaman, token,
                            unggah)


@pytest.fixture()
def dua(kidup):
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def tak_dikenal(server, akun=None, data=None):
    return minta_mentah(server, "/murid/tidak-ada-rute", akun, data)[:2]


def teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def setujui(murid_order, waktu=AWAL):
    with kelas_store.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, murid_order, ADMIN, waktu, bukti_dilihat=bukti_terakhir(murid_order))


# --- sakelar, sesi, peran ----------------------------------------------------------------

def test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal(kmati):
    assert not paket_belajar_gate.aktif()
    murid = buat_murid(kmati, "murid-a", "Anak Alfa")
    harap_get = tak_dikenal(kmati, murid.akun)
    for jalur in (M, BUAT, BUKTI):
        assert minta_mentah(kmati, jalur, murid.akun)[:2] == harap_get, jalur
    harap_post = tak_dikenal(kmati, murid.akun, {"x": "1"})
    for jalur in (BUAT, BUKTI):
        assert minta_mentah(kmati, jalur, murid.akun, {"token": "x", "kode": "mini"})[:2] == harap_post, jalur
    assert hitung() == KOSONG


def test_anonim_get_303_ke_masuk_dan_post_401_tanpa_efek(dua):
    kode, _isi, tajuk = minta_mentah(dua, M)
    assert (kode, tajuk.get("Location")) == (303, "/masuk")
    assert minta_mentah(dua, BUAT, None, {"token": "x", "kode": "mini"})[0] == 401
    assert hitung() == KOSONG


def test_guru_tidak_dilayani_modul_murid(dua):
    kode, isi, _ = minta_mentah(dua, M, ("guru", "sandi-guru-panjang-123"))
    assert "Paket belajar 1 bulan" not in isi
    assert hitung() == KOSONG


def test_akun_murid_tanpa_siswa_tertaut_jatuh_ke_jalur_asing(kidup):
    murid = buat_murid(kidup, "murid-yatim", "x", tertaut=False)
    assert minta_mentah(kidup, M, murid.akun)[:2] == tak_dikenal(kidup, murid.akun)
    assert buat(kidup, murid)[:2] == tak_dikenal(kidup, murid.akun, {"x": "1"})
    assert hitung() == KOSONG


def test_lintas_situs_post_ditolak_sebelum_efek(dua):
    kode, _, _ = minta_mentah(dua, BUAT, dua.a.akun, {"token": token(dua.a.akun, "kelas_buat:mini"), "kode": "mini"},
                              {"Sec-Fetch-Site": "cross-site"})
    assert kode in (403, 400)
    assert hitung() == KOSONG


# --- halaman ------------------------------------------------------------------------------

def test_halaman_dua_kartu_harga_dari_katalog_tanpa_rekening(dua):
    isi = halaman(dua, dua.a)
    t = teks(isi)
    assert "Private" in t and "Mini Class" in t and "Rp640.000" in t and "Rp300.000" in t
    assert isi.count('action="/murid/paket/buat"') == 2
    assert "Zoom atau Google Meet" in t and "Lokasi diumumkan" not in t
    assert "Bank Contoh" not in t  # rekening baru tampil bersama tagihan


def test_kueri_siswa_diabaikan_get_dan_post(dua):
    buat_dan_unggah(dua, dua.b)
    kode, isi, _ = minta_mentah(dua, M + "?siswa_id=%d&order=x" % dua.b.siswa_id, dua.a.akun)
    assert kode == 200 and "Daftar paket ini" in isi and "Menunggu verifikasi" not in isi
    data = {"token": token(dua.a.akun, "kelas_buat:private"), "kode": "private"}
    assert minta_mentah(dua, BUAT + "?siswa_id=%d" % dua.b.siswa_id, dua.a.akun, data)[0] == 303
    assert {r["siswa_id"] for r in baca_admin("SELECT siswa_id FROM kelas_order WHERE paket='private'")} \
        == {dua.a.siswa_id}


def test_rekening_kosong_halaman_jujur_dan_post_404_tanpa_efek(kmati, monkeypatch):
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    murid = buat_murid(kmati, "murid-a", "Anak Alfa")
    isi = halaman(kmati, murid)
    assert "belum dibuka" in teks(isi) and "/murid/paket/buat" not in isi
    assert buat(kmati, murid)[0] == 404
    assert unggah(kmati, murid)[0] == 404
    assert hitung() == KOSONG and semua_berkas(kmati) == []


def test_kelas_belum_dipasang_503_bukan_500(dua):
    kon = sqlite3.connect(_admin_store.BAWAAN)
    for tabel in reversed(TABEL):
        kon.execute("DROP TABLE %s" % tabel)
    kon.commit()
    kon.close()
    kode, isi, _ = minta_mentah(dua, M, dua.a.akun)
    assert kode == 503 and "Traceback" not in isi


# --- buat tagihan -------------------------------------------------------------------------

def test_buat_tagihan_nominal_dari_server_dan_halaman_tagihan(dua):
    kode, _, tajuk = buat(dua, dua.a, "mini")
    assert (kode, tajuk["Location"]) == (303, M)
    o = order_terakhir()
    assert (o["siswa_id"], o["paket"], o["nominal"]) == (dua.a.siswa_id, "mini", 300_000)
    assert o["total_transfer"] == 300_000 + o["kode_unik"] and 1 <= o["kode_unik"] <= 999
    isi = tagihan_halaman(dua, dua.a, "mini")[1]
    t = teks(isi)
    assert "Bank Contoh" in t and "1234 5678 90" in t and "PT Contoh Sintetis" in t
    assert "Unggah bukti" in t and "Daftar paket ini" not in t and "Batas waktu" in t
    assert "Rp300.%03d" % o["kode_unik"] in t


def test_buat_dan_halaman_gagal_tertutup_bila_nominal_peta_tak_sesuai(dua, monkeypatch):
    """K4 fail-closed: order Peta lunas Rp59.000 bukan nilai CHECK. Buat = 503 aman tanpa tagihan; halaman paket = 503."""
    monkeypatch.setattr(pesanan_dasar, "RUPIAH_PAKET", 59_000)
    with pesanan.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        order = buat_peta(kon, 1, akun=dua.a.id_akun, siswa=dua.a.siswa_id)
        terapkan_peta(kon, order, 1, transaction_id="trx-sintetis-0001", gross_amount="59000.00")
    sebelum = hitung(dua)
    kode, isi, _ = buat(dua, dua.a, "mini")
    assert kode == 503 and kelas_murid_http.COPY_DEPOSIT_TIDAK_SAH in isi
    assert hitung(dua) == sebelum and sebelum["kelas_order"] == 0
    assert minta_mentah(dua, M, dua.a.akun)[0] == 503


def test_private_dengan_deposit_peta_dipotong_49_ribu(dua):
    peta = peta_lunas_untuk(dua.a)
    assert "Sudah dipotong deposit Peta Rp49.000" in teks(halaman(dua, dua.a))
    assert buat(dua, dua.a, "private")[0] == 303
    o = order_terakhir()
    assert (o["nominal"], o["potongan_deposit"], o["potongan_diskon"], o["deposit_order_id"]) \
        == (591_000, 49_000, 0, peta)
    assert o["total_transfer"] == 591_000 + o["kode_unik"]


def test_tautan_keluarga_lama_tidak_menurunkan_harga_anak_kedua_lewat_http(dua):
    """Regression (25 Nov 2026): tautan keluarga lama di DB tidak lagi memberi diskon anak kedua."""
    keluarga = kelas_dasar.id_keluarga_baru()
    with kelas_store.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        kon.executemany("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) VALUES(?,?,?,?)",
                        [(keluarga, dua.a.siswa_id, ADMIN, AWAL), (keluarga, dua.b.siswa_id, ADMIN, AWAL)])
    setujui(buat_dan_unggah(dua, dua.a, "mini"))     # anak pertama: harga normal, akses mulai lebih dulu
    assert buat(dua, dua.b, "mini")[0] == 303
    nominal = {r["siswa_id"]: (r["nominal"], r["potongan_diskon"]) for r in baca_admin(
        "SELECT o.siswa_id,t.nominal,t.potongan_diskon FROM kelas_order o JOIN kelas_tagihan t ON t.order_id=o.id")}
    assert nominal[dua.a.siswa_id] == (300_000, 0) and nominal[dua.b.siswa_id] == (300_000, 0)


def test_nominal_tidak_bisa_dari_form(dua):
    for ekstra in ({"nominal": "1000"}, {"total": "1"}, {"siswa_id": str(dua.b.siswa_id)}, {"akun_id": "x"},
                   {"anak_kedua": "1"}, {"keluarga": "kel_x"}):
        assert buat(dua, dua.a, ekstra=ekstra)[0] == 400, ekstra
    assert buat(dua, dua.a, ekstra={"kode": "1000"})[0] == 400
    assert hitung() == KOSONG


@pytest.mark.parametrize("kode", ["gratis", "", "MINI", "mini2", "Private", "../mini"])
def test_kode_tak_dikenal_400_tanpa_efek(dua, kode):
    assert buat(dua, dua.a, kode, tok=token(dua.a.akun, "kelas_buat:mini"))[0] == 400
    assert hitung() == KOSONG


def test_token_salah_atau_untuk_kode_lain_atau_akun_lain_ditolak(dua):
    assert buat(dua, dua.a, "mini", tok="1.salah")[0] == 403
    assert buat(dua, dua.a, "mini", tok=token(dua.a.akun, "kelas_buat:private"))[0] == 403
    assert buat(dua, dua.a, "private", tok=token(dua.a.akun, "kelas_buat:mini"))[0] == 403
    assert buat(dua, dua.a, "mini", tok=token(dua.a.akun, "kelas_bukti"))[0] == 403
    assert buat(dua, dua.a, "mini", tok=token(dua.a.akun, "harian_buat:bulanan"))[0] == 403
    assert buat(dua, dua.a, "mini", tok=token(dua.b.akun, "kelas_buat:mini"))[0] == 403
    assert buat(dua, dua.a, hapus=("token",))[0] == 400
    assert hitung() == KOSONG


def test_token_kedaluwarsa_ditolak(dua):
    principal = sessions.principal_basic(*dua.a.akun)
    lewat = int(time.time()) - 5
    tok = "%d.%s" % (lewat, pesanan_http._mac(principal, None, "kelas_buat:mini", lewat))
    assert buat(dua, dua.a, "mini", tok=tok)[0] == 403
    assert hitung() == KOSONG


def test_idempoten_per_paket_dan_paket_lain_boleh_terbuka_bersamaan(dua):
    assert buat(dua, dua.a, "mini")[0] == 303
    total = order_terakhir()["total_transfer"]
    assert buat(dua, dua.a, "mini")[0] == 303
    assert hitung()["kelas_order"] == 1 and order_terakhir()["total_transfer"] == total
    assert buat(dua, dua.a, "private")[0] == 303
    assert hitung()["kelas_order"] == 2


def test_isolasi_murid_a_b_tagihan_status_dan_bukti(dua):
    buat_dan_unggah(dua, dua.a)
    awal = hitung()
    tb = teks(halaman(dua, dua.b))
    assert "Daftar paket ini" in tb and "Unggah bukti" not in tb and "Bank Contoh" not in tb
    assert unggah(dua, dua.b)[0] == 409
    assert hitung() == awal
    assert buat(dua, dua.b, "mini")[0] == 303
    assert len({r["kode_unik"] for r in baca_admin("SELECT kode_unik FROM kelas_tagihan")}) == 2


def test_anak_dengan_order_akun_lain_diperlakukan_tidak_ada(dua):
    """Siswa yang sudah punya order atas nama akun LAIN: 404 murid tanpa efek (tidak membocorkan keberadaan)."""
    with kelas_store.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_store.buat_tagihan(kon, "akun_" + "9" * 32, dua.a.siswa_id, "mini", AWAL)
    awal = hitung()
    assert minta_mentah(dua, M, dua.a.akun)[0] == 404
    assert buat(dua, dua.a, "mini")[0] == 404
    assert unggah(dua, dua.a)[0] == 409
    assert hitung() == awal and semua_berkas(dua) == []


# --- unggah bukti -------------------------------------------------------------------------

def test_laju_unggah_dibatasi_429_tanpa_efek(dua):
    buat(dua, dua.a)
    kode = [unggah(dua, dua.a, TEKS_PALSU)[0] for _ in range(8)]
    assert kode.count(415) == 6 and kode[6:] == [429, 429]
    assert hitung()["kelas_bukti"] == 0


def test_unggah_catat_bukti_di_subfolder_kelas_dan_status_menunggu(dua):
    buat(dua, dua.a)
    kode, _, tajuk = unggah(dua, dua.a, JPEG, nama_berkas="rahasia-klien.jpg")
    assert (kode, tajuk["Location"]) == (303, M)
    assert hitung()["kelas_bukti"] == 1
    assert len(berkas_kelas(dua)) == 1 and len(semua_berkas(dua)) == 1
    assert semua_berkas(dua)[0].startswith("kelas/")
    t = teks(tagihan_halaman(dua, dua.a, "mini")[1])
    assert "Bukti sudah kami terima" in t and "Menunggu verifikasi" in t and "rahasia-klien" not in t


@pytest.mark.parametrize("isi,kode", [(b"", 400), (TEKS_PALSU, 415),
                                      (b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10), 413)])
def test_unggah_berkas_tidak_sah_ditolak_tanpa_efek(dua, isi, kode):
    buat(dua, dua.a)
    awal = hitung()
    assert unggah(dua, dua.a, isi)[0] == kode
    assert hitung() == awal and semua_berkas(dua) == []


def test_unggah_tipe_diputuskan_dari_isi_bukan_nama_atau_tipe_klien(dua):
    buat(dua, dua.a)
    assert unggah(dua, dua.a, TEKS_PALSU, nama_berkas="x.jpg", tipe="image/jpeg")[0] == 415
    assert unggah(dua, dua.a, PDF, nama_berkas="x.txt", tipe="text/plain")[0] == 303
    assert baca_admin("SELECT mime FROM kelas_bukti")[0]["mime"] == "application/pdf"


def test_unggah_tanpa_tagihan_atau_token_salah_tanpa_efek(dua):
    assert unggah(dua, dua.a)[0] == 409
    buat(dua, dua.a)
    assert unggah(dua, dua.a, tok="1.salah")[0] == 403
    assert unggah(dua, dua.a, tok=token(dua.a.akun, "kelas_buat:mini"))[0] == 403
    assert unggah(dua, dua.a, tok=token(dua.a.akun, "harian_bukti"))[0] == 403
    assert hitung()["kelas_bukti"] == 0 and semua_berkas(dua) == []


def test_unggah_berkas_sama_tidak_ganda_dan_batas_lima(dua, monkeypatch):
    buat(dua, dua.a)
    assert unggah(dua, dua.a, JPEG)[0] == 303
    assert unggah(dua, dua.a, JPEG)[0] == 303
    assert hitung()["kelas_bukti"] == 1 and len(berkas_kelas(dua)) == 1
    for i in range(4):
        assert unggah(dua, dua.a, JPEG + bytes([i + 1]))[0] == 303
    assert hitung()["kelas_bukti"] == 5
    monkeypatch.setattr(pesanan_http, "_laju", {})
    assert unggah(dua, dua.a, JPEG + b"zz")[0] == 409
    assert hitung()["kelas_bukti"] == 5 and len(berkas_kelas(dua)) == 5


def test_berkas_yang_sudah_dipakai_murid_lain_ditolak_dan_berkas_dibuang(dua):
    buat(dua, dua.a)
    buat(dua, dua.b)
    assert unggah(dua, dua.a, JPEG)[0] == 303
    awal = hitung()
    assert unggah(dua, dua.b, JPEG)[0] == 409
    assert hitung() == awal and len(berkas_kelas(dua)) == 1


def test_unggah_setelah_jendela_habis_ditolak(dua, jam):
    buat(dua, dua.a)
    jam.maju_jam(25)
    assert unggah(dua, dua.a)[0] == 409
    assert hitung()["kelas_bukti"] == 0 and semua_berkas(dua) == []


def test_multipart_bentuk_aneh_ditolak(dua):
    from bukti_kit import bagian, multipart
    from kelas_http_kit import minta_multipart
    buat(dua, dua.a)
    tok = token(dua.a.akun, "kelas_bukti:mini")
    ekstra = multipart([bagian("token", tok.encode()), bagian("berkas", JPEG, nama_berkas="a.jpg"),
                        bagian("order_id", b"kor_" + b"0" * 32)])
    assert minta_multipart(dua, BUKTI + "?kode=mini", dua.a.akun, ekstra)[0] == 400
    assert hitung()["kelas_bukti"] == 0 and semua_berkas(dua) == []


def test_gagal_catat_menghapus_berkas(dua, monkeypatch):
    import kelas_murid_http
    buat(dua, dua.a)

    def gagal(*_a, **_k):
        raise OSError("disk penuh")

    monkeypatch.setattr(kelas_murid_http.store, "catat_bukti", gagal)
    assert unggah(dua, dua.a)[0] == 503
    assert semua_berkas(dua) == [] and hitung()["kelas_bukti"] == 0


# --- status -------------------------------------------------------------------------------

def test_ditolak_boleh_unggah_ulang(dua):
    buat_dan_unggah(dua, dua.a)
    oid = order_terakhir()["id"]
    with kelas_store.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.tolak(kon, oid, ADMIN, "Nominal kurang tiga digit", AWAL, bukti_dilihat=bukti_terakhir(oid))
    t = teks(tagihan_halaman(dua, dua.a, "mini")[1])
    assert "Ditolak" in t and "Unggah ulang bukti" in t
    assert unggah(dua, dua.a, PNG)[0] == 303
    assert "Bukti sudah kami terima" in teks(tagihan_halaman(dua, dua.a, "mini")[1])


def test_setuju_halaman_aktif_sampai_tanggal_dan_boleh_perpanjang(dua):
    oid = buat_dan_unggah(dua, dua.a)
    setujui(oid)
    t = teks(halaman(dua, dua.a))
    assert "aktif sampai 23 Des 2026" in t and "Daftar paket ini" in t
    assert baca_admin("SELECT COUNT(*) AS n FROM kelas_akses")[0]["n"] == 1


def test_kedaluwarsa_tanpa_bukti_boleh_tagihan_baru(dua, jam):
    buat(dua, dua.a)
    jam.maju_jam(25)
    assert "Daftar paket ini" in teks(halaman(dua, dua.a))
    assert buat(dua, dua.a)[0] == 303 and hitung()["kelas_order"] == 2


# --- privasi dan escape ----------------------------------------------------------------------

def test_tidak_ada_nama_anak_atau_kontak_di_halaman_murid(dua):
    import kontak_akun
    with database.buka(dua.db) as kon:
        kon.execute("BEGIN IMMEDIATE")
        kontak_akun.simpan(kon, dua.a.id_akun, "6281234567890", "2026-11-18T09:00:00")
        kon.commit()
    buat_dan_unggah(dua, dua.a)
    isi = halaman(dua, dua.a)
    for rahasia in ("81234567890", "wa.me", "Anak Alfa", "Anak Beta", str(dua.a.id_akun)):
        assert rahasia not in isi, rahasia


def test_rekening_di_escape_dan_nilai_berbahaya_ditutup_di_sumber(dua):
    kon = sqlite3.connect(_admin_store.BAWAAN)
    kon.execute("UPDATE rekening_konfigurasi SET nama_bank=?", ("Bank & Mitra",))
    kon.commit()
    buat(dua, dua.a)
    isi = tagihan_halaman(dua, dua.a, "mini")[1]
    assert "Bank &amp; Mitra" in isi and "Bank & Mitra" not in isi
    kon.execute("UPDATE rekening_konfigurasi SET nama_bank=?", ("<script>alert(1)</script>",))
    kon.commit()
    kon.close()
    kode, isi, _ = minta_mentah(dua, M, dua.a.akun)
    assert "<script>alert(1)" not in isi and "belum dibuka" in teks(isi)   # validasi sumber: rekening dianggap tak ada


# --- tautan masuk (hanya bila sakelar PAKET_BELAJAR aktif) --------------------------------------------

def test_tautan_langganan_dan_kartu_orang_tua_ikut_sakelar(dua, monkeypatch):
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    langganan = minta_mentah(dua, "/murid/langganan", dua.a.akun)[1]
    ortu = minta_mentah(dua, "/murid/orang-tua", dua.a.akun)[1]
    assert langganan.count('href="/murid/paket"') == 1 and "Belajar bersama Guru" in teks(langganan)
    assert 'id="ortu-paket"' in ortu and ortu.count('href="/murid/paket"') == 1
    monkeypatch.delenv("PAKET_BELAJAR")
    assert 'href="/murid/paket"' not in minta_mentah(dua, "/murid/langganan", dua.a.akun)[1]
    assert 'id="ortu-paket"' not in minta_mentah(dua, "/murid/orang-tua", dua.a.akun)[1]
