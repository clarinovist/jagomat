"""Halaman admin "Semua pembayaran": pembaca tiga ledger, renderer, dan rute HTTP (data sintetis, baca-saja)."""
from __future__ import annotations

import sqlite3

import pytest

import admin_pages
import admin_pembayaran_pages as ui
import admin_pembayaran_semua as S
import admin_security
import auth
import database
import harian_langganan_putusan as hp
import harian_langganan_store as hs
import kelas_kit as kk
from admin_pesanan_kit import login_admin, minta_admin
from bukti_kit import JPEG
from cek_http_kit import AKUN_A, AKUN_MURID
from harian_kit import SANDI as SANDI_HARIAN
from harian_kit import buat, buat_murid, hidup, jam, mati, minta_mentah, server, unggah  # noqa: F401
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

T0 = "2026-11-23T03:00:00"
T_UNGGAH = "2026-11-23T03:10:00"
KINI_PETA = "2026-11-18T11:00:00"  # sesudah order Peta sintetis (18 Nov 10.00), sebelum kedaluwarsa
ADMIN = "admin_sintetis"


@pytest.fixture
def belajar(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "tidak-ada-sandi.json")  # jangan pernah sandi.json asli
    with database.buka(jalur) as kon:
        yield kon


def _anak(kon, nama="Anak Uji"):
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', 'guru')", (nama,)).lastrowid
    kon.commit()
    return siswa


def _status(baris, order_id):
    return next(b.status for b in baris if b.order_id == order_id)


# --- pembaca -----------------------------------------------------------------------------------

def test_harian_tagihan_tanpa_bukti_tetap_tampil_lalu_menunggu_lalu_lunas(belajar, db_kelas):
    siswa = _anak(belajar, "Nama Rahasia")
    tagihan = hs.buat_tagihan(belajar, siswa, "bulanan", T0)
    oid = tagihan["order_id"]
    baris, gagal = S.baca(db_kelas, T_UNGGAH)
    harian = [b for b in baris if b.jenis == S.JENIS_HARIAN]
    assert [(b.order_id, b.status, b.nominal) for b in harian] == [(oid, S.S_BELUM_BAYAR, tagihan["nominal_transfer"])]
    assert "Rahasia" not in repr(baris)
    bukti = hs.catat_bukti(belajar, siswa, "image/png", 100, "%064x" % 1, "%032x" % 1, T_UNGGAH)
    assert _status(S.baca(db_kelas, T_UNGGAH)[0], oid) == S.S_MENUNGGU
    hp.setujui(belajar, oid, ADMIN, T_UNGGAH, bukti_dilihat=bukti["bukti_id"])
    assert _status(S.baca(db_kelas, T_UNGGAH)[0], oid) == S.S_LUNAS


def test_harian_kedaluwarsa_dan_ditolak_memakai_status_halaman_acc(belajar, db_kelas):
    a, b = _anak(belajar, "A"), _anak(belajar, "B")
    lama = hs.buat_tagihan(belajar, a, "bulanan", T0)["order_id"]
    tolak = hs.buat_tagihan(belajar, b, "bulanan", T0)["order_id"]
    bukti = hs.catat_bukti(belajar, b, "image/png", 100, "%064x" % 2, "%032x" % 2, T_UNGGAH)
    hp.tolak(belajar, tolak, ADMIN, "Nominal tidak sesuai", T_UNGGAH, bukti_dilihat=bukti["bukti_id"])
    baris, _ = S.baca(db_kelas, "2026-11-23T04:00:00")
    assert (_status(baris, lama), _status(baris, tolak)) == (S.S_BELUM_BAYAR, S.S_DITOLAK)
    assert _status(S.baca(db_kelas, "2026-11-25T00:00:00")[0], lama) == S.S_KEDALUWARSA


def test_kelas_menunggu_lalu_lunas(belajar, db_kelas, kon_kelas):
    tagihan, bukti_id = kk.menunggu(kon_kelas)
    baris, gagal = S.baca(db_kelas, kk.SESUDAH_UPLOAD)
    kelas = [b for b in baris if b.jenis == S.JENIS_KELAS]
    assert [(b.order_id, b.status, b.nominal) for b in kelas] == [(tagihan.order_id, S.S_MENUNGGU, tagihan.total)]
    kk.setuju(kon_kelas, tagihan, bukti_id)
    assert _status(S.baca(db_kelas, kk.SESUDAH_UPLOAD)[0], tagihan.order_id) == S.S_LUNAS


def test_peta_belum_bayar_dan_lunas_terbaca_dengan_nominal_dasar(belajar, db_kelas, kon_kelas):
    baru = kk.buat(kon_kelas, 7)["order_id"]
    lunas = kk.peta_lunas(kon_kelas, 8)
    baris, _ = S.baca(db_kelas, KINI_PETA)
    peta = {b.order_id: b for b in baris if b.jenis == S.JENIS_PETA}
    assert peta[baru].status == S.S_BELUM_BAYAR and peta[lunas].status == S.S_LUNAS
    assert peta[baru].nominal == 49000
    assert peta[lunas].jalur == "/admin/pesanan/order?id=" + lunas


def test_jenis_tak_terbaca_dilaporkan_bukan_diam_diam_kosong(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BAWAAN", tmp_path / "kosong.db")
    baris, gagal = S.baca(tmp_path / "tidak-ada.db", T_UNGGAH)
    assert baris == () and set(gagal) == {S.JENIS_PETA, S.JENIS_HARIAN, S.JENIS_KELAS}


def test_urutan_terbaru_dulu_dan_saring_serta_hitung(belajar, db_kelas, kon_kelas):
    hs.buat_tagihan(belajar, _anak(belajar), "bulanan", T0)
    kk.menunggu(kon_kelas)
    baris, _ = S.baca(db_kelas, kk.SESUDAH_UPLOAD)
    assert [b.dibuat for b in baris] == sorted((b.dibuat for b in baris), reverse=True)
    jumlah = S.hitung(baris)
    assert jumlah["semua"] == len(baris) and jumlah["menunggu"] == 1 and jumlah["belum_bayar"] == 1
    assert sum(jumlah[k] for k in S.KELOMPOK) == jumlah["semua"]  # tiap status tepat satu kelompok
    assert {b.status for b in S.saring(baris, "menunggu")} == {S.S_MENUNGGU}
    with pytest.raises(ValueError):
        S.saring(baris, "bukan-kelompok")


def test_tautan_menunggu_ke_halaman_verifikasi_jenisnya():
    kelas = S.BarisBayar(S.JENIS_KELAS, "kel_1", 1, S.S_MENUNGGU, T0)
    harian = S.BarisBayar(S.JENIS_HARIAN, "hor_1", 1, S.S_BELUM_BAYAR, T0)
    peta = S.BarisBayar(S.JENIS_PETA, "ord_1", 1, S.S_MENUNGGU, T0)
    assert kelas.jalur == "/admin/kelas/verifikasi?order=kel_1"
    assert harian.jalur == "/admin/langganan/verifikasi?order=hor_1"
    assert peta.jalur == "/admin/pesanan/verifikasi?order=ord_1"


# --- nama anak dan akun (keputusan Pemilik 26 Nov 2026) ---------------------------------------

SANDI_UJI = "sandi-sintetis-rahasia-456"


def _berkas_auth(tmp_path, akun):
    """Berkas auth sintetis; `akun` = [(pengguna, siswa_id)] akun murid (siswa_id None = akun lama tanpa siswa)."""
    berkas = tmp_path / "sandi.json"
    auth.simpan_sandi(SANDI_UJI, "guru", path=berkas)
    for pengguna, siswa in akun:
        auth.tambah_akun(pengguna, SANDI_UJI, "murid", path=berkas, siswa_id=siswa)
    return berkas


def test_lengkapi_nama_anak_dan_akun_tiga_jalur_untuk_admin(tmp_path, belajar, db_kelas, kon_kelas):
    siswa = _anak(belajar, "Anak Tiga")
    berkas = _berkas_auth(tmp_path, [("murid-tiga", siswa)])
    hs.buat_tagihan(belajar, siswa, "bulanan", T0)
    kk.peta_lunas(kon_kelas, siswa)
    kk.menunggu(kon_kelas, siswa=siswa)
    baris, _ = S.baca(db_kelas, T_UNGGAH)
    hasil = S.lengkapi_anak_akun(baris, berkas)
    assert {b.jenis: (b.nama_anak, b.akun) for b in hasil} == {
        S.JENIS_HARIAN: ("Anak Tiga", "murid-tiga"),
        S.JENIS_PETA: ("Anak Tiga", "murid-tiga"),
        S.JENIS_KELAS: ("Anak Tiga", "murid-tiga"),
    }


def test_akun_ambigu_akun_lama_dan_siswa_tanpa_akun_tampil_strip(tmp_path, belajar):
    dua = _anak(belajar, "Anak Dua")
    sepi = _anak(belajar, "Anak Sepi")
    lama = _anak(belajar, "Anak Lama")  # satu akun bertaut, tetapi ada akun lama (tanpa siswa_id) bernama sama
    berkas = _berkas_auth(tmp_path, [("murid-dua-a", dua), ("murid-dua-b", dua),
                                     ("murid-lama", lama), ("anak lama", None)])
    baris = (S.BarisBayar(S.JENIS_KELAS, "kel_1", 1, S.S_LUNAS, T0, siswa_id=dua),
             S.BarisBayar(S.JENIS_HARIAN, "hor_1", 1, S.S_LUNAS, T0, siswa_id=sepi),
             S.BarisBayar(S.JENIS_PETA, "ord_1", 1, S.S_LUNAS, T0, siswa_id=lama),
             S.BarisBayar(S.JENIS_PETA, "ord_2", 1, S.S_LUNAS, T0))
    hasil = S.lengkapi_anak_akun(baris, berkas)
    assert [(b.nama_anak, b.akun) for b in hasil] == [
        ("Anak Dua", None), ("Anak Sepi", None), ("Anak Lama", None), (None, None)]


def test_galat_baca_auth_dan_db_membuat_strip_tanpa_menggagalkan_halaman(tmp_path, belajar, monkeypatch):
    siswa = _anak(belajar, "Anak Galat")
    berkas = _berkas_auth(tmp_path, [("murid-galat", siswa)])
    baris = (S.BarisBayar(S.JENIS_HARIAN, "hor_1", 1, S.S_LUNAS, T0, siswa_id=siswa),)
    bukan_berkas = tmp_path / "bukan-berkas"  # direktori: baca auth gagal dengan galat OS
    bukan_berkas.mkdir()
    hasil = S.lengkapi_anak_akun(baris, bukan_berkas)
    assert (hasil[0].nama_anak, hasil[0].akun) == ("Anak Galat", None)

    def db_rusak(*_args, **_kwargs):
        raise sqlite3.OperationalError("no such table: siswa")

    monkeypatch.setattr(S.database, "buka", db_rusak)
    hasil = S.lengkapi_anak_akun(baris, berkas)
    isi = ui.halaman(hasil, saring=None, hitungan=S.hitung(hasil))
    assert (hasil[0].nama_anak, hasil[0].akun) == (None, None)
    assert "<td>-</td><td>-</td>" in isi and str(tmp_path) not in isi


def test_galat_berjalur_di_pesan_tidak_bocor_ke_halaman(tmp_path, belajar, monkeypatch):
    siswa = _anak(belajar, "Anak Jalur")
    berkas = _berkas_auth(tmp_path, [("murid-jalur", siswa)])
    baris = (S.BarisBayar(S.JENIS_HARIAN, "hor_1", 1, S.S_LUNAS, T0, siswa_id=siswa),)

    def auth_rusak(*_args, **_kwargs):
        raise OSError(13, "ditolak", "/sintetis/rahasia/sandi.json")

    def db_rusak(*_args, **_kwargs):
        raise sqlite3.OperationalError("unable to open database file /sintetis/rahasia/belajar.db")

    monkeypatch.setattr(S.auth, "muat_akun", auth_rusak)
    monkeypatch.setattr(S.database, "buka", db_rusak)
    hasil = S.lengkapi_anak_akun(baris, berkas)
    isi = ui.halaman(hasil, saring=None, hitungan=S.hitung(hasil))
    assert len(hasil) == 1 and (hasil[0].nama_anak, hasil[0].akun) == (None, None)
    assert "<td>-</td><td>-</td>" in isi
    assert "/sintetis/rahasia" not in isi and "/sintetis/rahasia" not in repr(hasil)


def test_hasil_lengkapi_tidak_memuat_sandi_atau_hash(tmp_path, belajar):
    siswa = _anak(belajar, "Anak Rahasia")
    berkas = _berkas_auth(tmp_path, [("murid-rahasia", siswa)])
    baris = (S.BarisBayar(S.JENIS_HARIAN, "hor_1", 1, S.S_LUNAS, T0, siswa_id=siswa),)
    keluaran = repr(S.lengkapi_anak_akun(baris, berkas))
    assert SANDI_UJI not in keluaran
    akun = next(a for a in auth.muat_akun(berkas) if a["pengguna"] == "murid-rahasia")
    for nilai in akun.values():
        if isinstance(nilai, str) and len(nilai) >= 8 and nilai != "murid-rahasia":
            assert nilai not in keluaran


# --- renderer ----------------------------------------------------------------------------------

def test_render_escape_status_asing_dan_cta_menurut_status():
    item = [S.BarisBayar(S.JENIS_HARIAN, "hor_<b>x</b>", 39798, "aneh<script>", T0),
            S.BarisBayar(S.JENIS_KELAS, "kel_1", 250007, S.S_MENUNGGU, T0)]
    isi = ui.halaman(item, saring=None, hitungan=S.hitung(item))
    assert "<b>x</b>" not in isi and "<script>" not in isi
    assert "Rp39.798" in isi and "Periksa bukti" in isi and ">Detail<" in isi
    assert "Latihan Harian" in isi and "Paket Belajar" in isi


def test_render_kosong_peringatan_gagal_dan_chip_aktif():
    isi = ui.halaman((), saring="menunggu", hitungan=S.hitung(()), gagal=(S.JENIS_HARIAN,))
    assert "Tidak ada transfer yang menunggu verifikasi." in isi
    assert 'role="alert"' in isi and "Latihan Harian" in isi and 'aria-current="true"' in isi


def test_render_nama_anak_dan_akun_di_escape_dan_strip_bila_kosong():
    item = [S.BarisBayar(S.JENIS_HARIAN, "hor_1", 39798, S.S_LUNAS, T0,
                         nama_anak="<img src=x onerror=1>", akun="murid-x"),
            S.BarisBayar(S.JENIS_PETA, "ord_1", 49000, S.S_LUNAS, T0)]
    isi = ui.halaman(item, saring=None, hitungan=S.hitung(item))
    assert "<img src=x" not in isi and "&lt;img src=x onerror=1&gt;" in isi
    assert "<td>murid-x</td>" in isi and "<td>-</td><td>-</td>" in isi
    assert ">Anak<" in isi and ">Akun<" in isi


def test_semua_pembayaran_anak_menu_pesanan_tanpa_menambah_butir_menu():
    assert ("pembayaran", "Semua pembayaran", "/admin/pembayaran") in admin_pages.SECTION
    assert "pembayaran" not in [sid for _g, daftar in admin_pages.GRUP_SECTION for sid in daftar]
    nav = admin_pages._nav("pembayaran")
    awal = nav.index('href="/admin/pesanan"')
    assert nav[awal:].startswith('href="/admin/pesanan" aria-current="page"')


def test_halaman_pesanan_menautkan_semua_pembayaran():
    import admin_pesanan_pages as pesanan_ui
    isi = pesanan_ui.halaman({"items": [], "total": 0}, halaman=1, gerbang_terbuka=True, hasil=None)
    assert 'href="/admin/pembayaran"' in isi


# --- HTTP --------------------------------------------------------------------------------------

def test_http_admin_melihat_tagihan_tanpa_bukti_dan_bukti_menunggu(hidup):
    admin = login_admin(hidup)
    murid = buat_murid(hidup, "murid-a", "Anak Alfa")
    assert buat(hidup, murid)[0] == 303
    kode, isi, _ = minta_admin(hidup, "/admin/pembayaran", admin)
    assert kode == 200 and "Menunggu pembayaran" in isi and "Anak Alfa" in isi and "murid-a" in isi
    assert unggah(hidup, murid, JPEG)[0] == 303
    isi = minta_admin(hidup, "/admin/pembayaran?status=menunggu", admin)[1]
    assert "Menunggu verifikasi" in isi and "Periksa bukti" in isi and "/admin/langganan/verifikasi?order=" in isi
    assert "Menunggu pembayaran" not in isi
    assert "murid-a" in isi and "Anak Alfa" in isi


def test_http_nama_anak_di_escape_dan_sandi_serta_hash_tidak_bocor(hidup):
    admin = login_admin(hidup)
    murid = buat_murid(hidup, "murid-esc", "<b>Anak Esc</b>")
    assert buat(hidup, murid)[0] == 303
    isi = minta_admin(hidup, "/admin/pembayaran", admin)[1]
    assert "&lt;b&gt;Anak Esc&lt;/b&gt;" in isi and "<b>Anak Esc</b>" not in isi
    assert SANDI_HARIAN not in isi
    akun = next(a for a in auth.muat_akun() if a["pengguna"] == "murid-esc")
    for nilai in akun.values():
        if isinstance(nilai, str) and len(nilai) >= 8 and nilai != "murid-esc":
            assert nilai not in isi


@pytest.mark.parametrize("query", ["?status=bukan", "?status=menunggu&x=1", "?status=menunggu&status=lunas"])
def test_http_query_tak_sah_404_identik_dengan_rute_tak_dikenal(hidup, query):
    admin = login_admin(hidup)
    kode, isi, _ = minta_admin(hidup, "/admin/pembayaran" + query, admin)
    tak_ada = minta_admin(hidup, "/admin/tidak-ada", admin)
    assert (kode, isi) == (tak_ada[0], tak_ada[1]) and kode == 404


def test_http_non_admin_dan_anonim_404_tanpa_menyentuh_ledger(hidup):
    murid = buat_murid(hidup, "murid-a", "Anak Alfa")
    assert buat(hidup, murid)[0] == 303
    for akun in (None, AKUN_A, AKUN_MURID):
        kode, isi, _ = minta_mentah(hidup, "/admin/pembayaran", akun)
        tak_ada = minta_mentah(hidup, "/admin/tidak-ada", akun)
        assert (kode, isi) == (tak_ada[0], tak_ada[1]) and kode in (401, 403, 404)
        assert "hor_" not in isi and "Anak Alfa" not in isi


def test_http_non_admin_dan_murid_pemilik_tidak_melihat_nama_atau_akun(hidup):
    murid = buat_murid(hidup, "murid-bukan", "Anak Bukan")
    assert buat(hidup, murid)[0] == 303
    for akun in (None, AKUN_A, AKUN_MURID, murid.akun):
        kode, isi, _ = minta_mentah(hidup, "/admin/pembayaran", akun)
        tak_ada = minta_mentah(hidup, "/admin/tidak-ada", akun)
        assert (kode, isi) == (tak_ada[0], tak_ada[1]) and kode in (401, 403, 404)
        assert "Anak Bukan" not in isi and "murid-bukan" not in isi


def test_http_hanya_get_tanpa_aksi_tulis(hidup):
    admin = login_admin(hidup)
    kode, _, _ = minta_admin(hidup, "/admin/pembayaran", admin, {"x": "1"})
    assert kode in (404, 405)
