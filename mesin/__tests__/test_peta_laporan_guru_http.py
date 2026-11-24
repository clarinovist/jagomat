"""Halaman Guru laporan Peta Kemampuan lewat HTTP (D1-2): kepemilikan, gerbang order lunas, siklus draf-catatan-terbit,
sinkron `purna.catat_terbit`, kartu di halaman anak, dan guard form. Data sintetis; order lunas di jalur QRIS DAN transfer
(fixture `lunas`). Tes di sini menjadi sasaran mutation di `test_peta_laporan_guru_mutation.py`.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import cek_gratis_sapu  # noqa: E402
import cek_ringkasan_admin  # noqa: E402
import peta_laporan_guru_http as pgh  # noqa: E402
import peta_laporan_snapshot  # noqa: E402
import peta_laporan_store  # noqa: E402
import pesanan  # noqa: E402
import pesanan_admin_order as po  # noqa: E402
from admin_pesanan_kit import REFUND, kirim_aksi, login_admin, order_bayar  # noqa: E402
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah  # noqa: E402
from pesanan_http_kit import WA_SINTETIS, bayar, jam, keluarga, ledger, server, tertutup  # noqa: E402,F401
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from purna_http_kit import bayar_purna, jadikan_ditahan, lunas, potret_efek, transfer_purna  # noqa: E402,F401

CATATAN = "Anak sudah lebih teliti saat berhitung; di rumah cukup latihan sepuluh menit."
TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "pembahasan", "jawaban benar", "tel:", "wa.me")
SAPUAN_LEWAT_RETENSI = "2026-12-20T00:00:00"
POLA_GAYA_SKRIP = re.compile(r"<(style|script)\b.*?</\1>", re.S)


def _url(server, aksi: str = "") -> str:
    return "/anak/%d/peta%s" % (server.anak_a, aksi)


def _get(server, akun=AKUN_A, aksi: str = ""):
    return minta_mentah(server, _url(server, aksi), akun)


def _post(server, aksi: str, data=None, akun=AKUN_A):
    return minta_mentah(server, _url(server, "/" + aksi), akun, {} if data is None else data)


def _laporan_baris(server) -> list:
    with server.buka() as kon:
        return [tuple(r) for r in kon.execute("SELECT * FROM peta_laporan ORDER BY id")]


def _efek(server) -> tuple:
    return _laporan_baris(server), potret_efek()


def _teks(isi: str) -> str:
    badan = POLA_GAYA_SKRIP.sub(" ", isi)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", badan))


def _siapkan_draf(server, catatan: str = CATATAN) -> None:
    assert _post(server, "buat")[0] == 303
    if catatan:
        assert _post(server, "catatan", {"catatan": catatan})[0] == 303


def _terbitkan(server, **kw):
    return _post(server, "terbitkan", {"konfirmasi": "1"}, **kw)


def _siswa_order() -> dict:
    with ledger() as kon:
        baris = kon.execute("SELECT * FROM pesanan_order").fetchone()
        return dict(baris)


# --- lookup order per anak (pesanan_admin_order) -----------------------------------------------------

def test_order_peta_untuk_siswa_lima_kunci_dari_ledger_dan_status_turunan(lunas, jam):
    server, _admin, oid = lunas
    baris = _siswa_order()
    with ledger() as kon:
        hasil = po.order_peta_untuk_siswa(kon, baris["siswa_id"], jam())
    assert set(hasil) == set(po.KUNCI_ORDER_PETA) == {"order_id", "siswa_id", "cek_id", "akun_id", "status"}
    assert hasil == {"order_id": oid, "siswa_id": baris["siswa_id"], "cek_id": baris["cek_id"],
                     "akun_id": baris["akun_id"], "status": "sudah_dibayar"}


@pytest.mark.parametrize("siswa_id", [0, -1, 999999, True, "1", None, 1.0])
def test_order_peta_untuk_siswa_none_bila_tak_ada_atau_id_tak_sah(lunas, jam, siswa_id):
    with ledger() as kon:
        assert po.order_peta_untuk_siswa(kon, siswa_id, jam()) is None


def test_order_peta_untuk_siswa_status_belum_bayar(bayar_purna, jam):
    order, _trx = order_bayar(bayar_purna)
    with ledger() as kon:
        assert po.order_peta_untuk_siswa(kon, order["siswa_id"], jam())["status"] == "belum_bayar"


# --- kepemilikan dan keberadaan order ------------------------------------------------------------

def test_guru_pemilik_melihat_halaman_awal_dengan_ringkasan_per_materi_dan_tombol_buat(lunas):
    server, _admin, oid = lunas
    kode, isi, kepala = _get(server)
    teks = _teks(isi)
    assert kode == 200 and kepala["Cache-Control"] == "no-store"
    assert "Buat draf laporan" in teks and "Janji laporan terbit" in teks
    assert "Skor 67 dari 100" in teks and "Data per materi dihapus otomatis dalam 29 hari" in teks
    assert len(re.findall(r'<th scope="row">', isi)) == 3 and "<meter" in isi
    assert f'action="{_url(server, "/buat")}"' in isi and "<script" not in isi.split("<main", 1)[1]


def test_bukan_pemilik_404_byte_identik_dengan_anak_tak_ada_dan_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    sebelum = _efek(server)
    acuan = minta_mentah(server, "/anak/99999/peta", AKUN_B)
    assert acuan[0] == 404
    assert _get(server, AKUN_B)[:2] == acuan[:2]
    for aksi in ("buat", "catatan", "terbitkan", "hapus"):
        assert _post(server, aksi, {"catatan": "x", "konfirmasi": "1"}, AKUN_B)[:2] == acuan[:2], aksi
    assert _efek(server) == sebelum


def test_anak_tanpa_order_404_identik_dan_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    sebelum = _efek(server)
    acuan = minta_mentah(server, "/anak/99999/peta", AKUN_B)
    for aksi in ("", "/buat", "/catatan", "/terbitkan", "/hapus"):
        jalur = "/anak/%d/peta%s" % (server.anak_b, aksi)
        kode, isi, _t = minta_mentah(server, jalur, AKUN_B, None if not aksi else {"konfirmasi": "1"})
        assert (kode, isi) == acuan[:2], aksi
    assert _efek(server) == sebelum


def test_get_dengan_sufiks_aksi_404_dan_rute_lain_tak_ditangkap(lunas):
    server, _admin, _oid = lunas
    acuan = minta_mentah(server, "/anak/99999/peta", AKUN_B)
    assert _get(server, AKUN_A, "/buat")[:2] == acuan[:2]
    assert _post(server, "")[:2] == acuan[:2]


# --- order ada tetapi belum lunas / ditahan / direfund --------------------------------------------

def _tanpa_form_dan_data(isi: str) -> None:
    assert "<form" not in POLA_GAYA_SKRIP.sub("", isi).split("<main", 1)[-1]
    teks = _teks(isi)
    assert "Skor" not in teks and "Materi" not in teks and "Buat draf" not in teks


def test_order_belum_lunas_halaman_info_tanpa_form_dan_post_409_tanpa_efek(bayar_purna, monkeypatch):
    order_bayar(bayar_purna)
    dibaca = []
    monkeypatch.setattr(cek_ringkasan_admin, "ringkasan_untuk_order", lambda *a, **k: dibaca.append(a))
    sebelum = _efek(bayar_purna)
    kode, isi, _t = _get(bayar_purna)
    assert kode == 200 and "belum selesai" in _teks(isi)
    _tanpa_form_dan_data(isi)
    for aksi in ("buat", "catatan", "terbitkan", "hapus"):
        assert _post(bayar_purna, aksi, {"catatan": "x", "konfirmasi": "1"})[0] == 409, aksi
    assert dibaca == [] and _efek(bayar_purna) == sebelum


def test_order_ditahan_halaman_info_dan_post_409_tanpa_efek(lunas, jam):
    server, _admin, oid = lunas
    jadikan_ditahan(server, oid, jam)
    sebelum = _efek(server)
    kode, isi, _t = _get(server)
    assert kode == 200 and "sedang diperiksa" in _teks(isi)
    _tanpa_form_dan_data(isi)
    assert _post(server, "buat")[0] == 409 and _efek(server) == sebelum


def test_order_direfund_halaman_info_dan_post_409_walau_draf_sudah_ada(lunas):
    server, admin, oid = lunas
    _siapkan_draf(server)
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    sebelum = _efek(server)
    kode, isi, _t = _get(server)
    assert kode == 200 and "sudah dikembalikan" in _teks(isi)
    _tanpa_form_dan_data(isi)
    assert CATATAN not in isi
    for aksi in ("catatan", "terbitkan", "hapus"):
        assert _post(server, aksi, {"catatan": "x", "konfirmasi": "1"})[0] == 409, aksi
    assert _efek(server) == sebelum


# --- siklus: buat draf, catatan, terbitkan -----------------------------------------------------------

def test_siklus_penuh_buat_catatan_terbit_dan_purna_tercatat_oleh_guru(lunas, jam):
    server, _admin, oid = lunas
    kode, _i, tajuk = _post(server, "buat")
    assert kode == 303 and tajuk["Location"] == _url(server)
    (baris,) = _laporan_baris(server)
    assert baris[4] == "guru" and baris[6] is None            # guru pembuat, belum terbit
    kode, isi, _t = _get(server)
    assert kode == 200 and 'name="catatan"' in isi and 'maxlength="2000"' in isi and "Ditinjau Guru Jagomat" in isi
    assert "teks ini dibaca orang tua" in _teks(isi) and CATATAN not in isi
    assert _post(server, "catatan", {"catatan": CATATAN})[0] == 303
    assert CATATAN in _get(server)[1]
    jam.maju_jam(5)
    kode, _i, tajuk = _terbitkan(server)
    assert kode == 303 and tajuk["Location"] == _url(server)
    with server.buka() as kon:
        laporan = peta_laporan_store.ambil(kon, server.anak_a)
    assert laporan["diterbitkan"] is not None and laporan["diterbitkan_oleh"] == "guru" and laporan["catatan"] == CATATAN
    (terbit,) = potret_efek()["purna_laporan_terbit"]
    assert terbit[:3] == (oid, jam(), "guru")                  # waktu terbit = waktu laporan terbit, pelaku = Guru sesi
    kode, isi, _t = _get(server)
    teks = _teks(isi)
    assert kode == 200 and "<form" not in isi.split("<main", 1)[-1] and "sudah terbit dan tidak bisa diubah" in teks
    assert CATATAN in isi and "Laporan terbit:" in teks


def test_isi_draf_dibangun_server_sama_dengan_snapshot_pembaca_allowlist(lunas, jam):
    server, _admin, _oid = lunas
    order = _siswa_order()
    _siapkan_draf(server)
    with server.buka() as kon:
        laporan = peta_laporan_store.ambil(kon, server.anak_a)
        cek = cek_ringkasan_admin.ringkasan_untuk_order(kon, order["siswa_id"], order["cek_id"], order["akun_id"], jam())
    assert laporan["isi"] == peta_laporan_snapshot.bangun(cek)


@pytest.mark.parametrize("ekstra", [{"isi": "{}"}, {"per_materi": "[]"}, {"skor": "100"}, {"cek_id": "1"}, {"akun_id": "akun_x"}])
def test_buat_dengan_field_apa_pun_400_isi_tidak_pernah_dari_form(lunas, ekstra):
    server, _admin, _oid = lunas
    sebelum = _efek(server)
    assert _post(server, "buat", ekstra)[0] == 400
    assert _efek(server) == sebelum


def test_draf_kedua_409_dan_tidak_menambah_baris(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "buat")
    assert kode == 409 and "Traceback" not in isi and "ValueError" not in isi
    assert _efek(server) == sebelum


def test_bahan_dihapus_retensi_tidak_bisa_buat_draf_dan_tanpa_tombol(lunas):
    server, _admin, _oid = lunas
    with server.buka() as kon:
        assert cek_gratis_sapu.sapu_cek_gratis(kon, SAPUAN_LEWAT_RETENSI, frozenset({id_akun(AKUN_A)}))["bahan_dihapus"] == 1
    kode, isi, _t = _get(server)
    assert kode == 200 and "Data per materi sudah dihapus (retensi 30 hari); laporan tidak bisa dibuat." in _teks(isi)
    assert "Buat draf laporan" not in isi
    sebelum = _efek(server)
    assert _post(server, "buat")[0] == 409 and _efek(server) == sebelum


def test_draf_tetap_terbaca_sesudah_bahan_dihapus_karena_snapshot_dibekukan(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    with server.buka() as kon:
        cek_gratis_sapu.sapu_cek_gratis(kon, SAPUAN_LEWAT_RETENSI, frozenset({id_akun(AKUN_A)}))
    kode, isi, _t = _get(server)
    assert kode == 200 and "Skor 67 dari 100" in _teks(isi) and _terbitkan(server)[0] == 303


def test_terbit_tanpa_centang_ditolak_400_tanpa_efek_lalu_dengan_centang_berhasil(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    for data in ({"konfirmasi": ""}, {"konfirmasi": "0"}, {"konfirmasi": "on"}):
        kode, isi, _t = _post(server, "terbitkan", data)
        assert kode == 400 and "Centang kotak konfirmasi" in isi, data
    assert _efek(server) == sebelum
    assert _post(server, "terbitkan", {})[0] == 400 and _efek(server) == sebelum
    assert _terbitkan(server)[0] == 303 and _laporan_baris(server)[0][6] is not None


def test_form_terbit_memuat_kotak_centang_konfirmasi_server_tanpa_js(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    isi = _get(server)[1]
    form = isi.split('action="%s"' % _url(server, "/terbitkan"), 1)[1].split("</form>", 1)[0]
    assert 'type="checkbox" name="konfirmasi" value="1"' in form
    assert "Setelah terbit, laporan tidak bisa diubah dan langsung terlihat oleh orang tua" in form
    assert "onclick" not in isi and "confirm(" not in isi


def test_terbit_tanpa_catatan_409_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server, catatan="")
    sebelum = _efek(server)
    kode, isi, _t = _terbitkan(server)
    assert kode == 409 and "Isi catatan" in isi and _efek(server) == sebelum


def test_hapus_draf_butuh_centang_lalu_boleh_buat_ulang(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    assert _post(server, "hapus", {})[0] == 400 and _post(server, "hapus", {"konfirmasi": "0"})[0] == 400
    assert _efek(server) == sebelum
    assert _post(server, "hapus", {"konfirmasi": "1"})[0] == 303 and _laporan_baris(server) == []
    assert _post(server, "buat")[0] == 303 and len(_laporan_baris(server)) == 1


def test_hapus_tanpa_draf_409(lunas):
    server, _admin, _oid = lunas
    assert _post(server, "hapus", {"konfirmasi": "1"})[0] == 409


def test_laporan_terbit_tidak_bisa_diubah_dihapus_atau_diterbitkan_lagi(lunas, jam):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    assert _terbitkan(server)[0] == 303
    sebelum = _efek(server)
    jam.maju_jam(2)
    for aksi, data in (("catatan", {"catatan": "ubah"}), ("hapus", {"konfirmasi": "1"}),
                       ("terbitkan", {"konfirmasi": "1"}), ("buat", {})):
        assert _post(server, aksi, data)[0] == 409, aksi
    assert _efek(server) == sebelum


# --- guard form --------------------------------------------------------------------------------

@pytest.mark.parametrize("aksi,data", [
    ("catatan", {}), ("catatan", {"catatan": "x", "isi": "{}"}), ("catatan", {"catatan": "x", "konfirmasi": "1"}),
    ("terbitkan", {"konfirmasi": "1", "catatan": "x"}), ("terbitkan", {"konfirmasi": "1", "order_id": "ord_x"}),
    ("hapus", {"konfirmasi": "1", "isi": "{}"}), ("hapus", {"catatan": "x"}),
])
def test_form_asing_atau_kurang_400_tanpa_efek(lunas, aksi, data):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    assert _post(server, aksi, data)[0] == 400
    assert _efek(server) == sebelum


def test_catatan_2000_karakter_boleh_2001_ditolak_400_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server, catatan="")
    assert _post(server, "catatan", {"catatan": "a" * 2000})[0] == 303
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": "b" * 2001})
    assert kode == 400 and "terlalu panjang" in isi and _efek(server) == sebelum


def test_catatan_berisi_karakter_kontrol_ditolak_400(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server, catatan="")
    sebelum = _efek(server)
    assert _post(server, "catatan", {"catatan": "ada\x00nul"})[0] == 400
    assert _post(server, "catatan", {"catatan": "ok\nbaris dua\tbertab"})[0] == 303
    assert _efek(server) != sebelum


def test_tubuh_melebihi_batas_form_rute_ditolak_400_pesan_form_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": "x" * (pgh.BATAS_FORM_CATATAN + 1)})
    assert kode == 400 and pgh.PESAN_FORM in isi
    assert _efek(server) == sebelum


def test_catatan_dan_nama_anak_di_escape_di_halaman(lunas):
    server, _admin, _oid = lunas
    with server.buka() as kon:
        kon.execute("UPDATE siswa SET nama = ? WHERE id = ?", ("<b>Anak</b>", server.anak_a))
    _siapkan_draf(server, catatan="<script>alert(1)</script>")
    isi = _get(server)[1]
    assert "<script>alert(1)</script>" not in isi and "&lt;script&gt;alert(1)&lt;/script&gt;" in isi
    assert "<b>Anak</b>" not in isi and "&lt;b&gt;Anak&lt;/b&gt;" in isi


# --- peran ------------------------------------------------------------------------------------

def test_admin_hanya_melihat_post_403_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _get(server, AKUN_ADMIN)
    assert kode == 200 and "Admin hanya dapat melihat" in _teks(isi) and "<textarea" not in isi
    assert "<form" not in POLA_GAYA_SKRIP.sub("", isi).split("<main", 1)[-1]
    for aksi in ("buat", "catatan", "terbitkan", "hapus"):
        assert _post(server, aksi, {"catatan": "x", "konfirmasi": "1"}, AKUN_ADMIN)[0] == 403, aksi
    assert _efek(server) == sebelum


def test_anonim_dan_murid_ditolak_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    sebelum = _efek(server)
    for akun in (None, AKUN_MURID):
        assert _get(server, akun)[0] in (401, 403, 404)
        for aksi in ("buat", "catatan", "terbitkan", "hapus"):
            assert _post(server, aksi, {"catatan": "x", "konfirmasi": "1"}, akun)[0] in (401, 403, 404), aksi
    assert _efek(server) == sebelum


def test_post_lintas_situs_ditolak_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    sebelum = _efek(server)
    kode, _i, _t = minta_mentah(server, _url(server, "/buat"), AKUN_A, {}, {
        "Sec-Fetch-Site": "cross-site", "Origin": "https://jahat.example"})
    assert kode in (400, 403) and _efek(server) == sebelum


# --- tanpa kata terlarang / tanpa data pembayar -------------------------------------------------------

def _semua_keadaan(server):
    """Halaman Peta pada tiga keadaan: belum ada draf, draf, terbit."""
    yield _get(server)[1]
    _siapkan_draf(server)
    yield _get(server)[1]
    assert _terbitkan(server)[0] == 303
    yield _get(server)[1]


def test_halaman_tanpa_kata_terlarang_dan_tanpa_data_pembayar(lunas):
    server, _admin, oid = lunas
    akun = _siswa_order()["akun_id"]
    for isi in _semua_keadaan(server):
        # Petunjuk untuk Guru ("jangan tulis ... kunci jawaban") memang menyebut istilahnya; yang dijaga: tidak ada kebocoran lain.
        konten = isi.split("<main", 1)[1].replace(pgh.hal.PETUNJUK_CATATAN, "")
        teks = _teks(konten).lower()
        assert [k for k in TERLARANG if k in teks] == []
        assert [k for k in TERLARANG if k in POLA_GAYA_SKRIP.sub("", konten).lower()] == []
        for rahasia in (oid, akun, id_akun(AKUN_A), WA_SINTETIS):
            assert rahasia not in isi


# --- kartu di halaman anak ------------------------------------------------------------------------

def _anak(server, akun=AKUN_A, bagian="perkembangan", anak=None):
    return minta_mentah(server, "/anak/%d?section=%s" % (anak or server.anak_a, bagian), akun)


def test_kartu_muncul_hanya_di_tab_perkembangan_untuk_order_lunas_satu_tautan(lunas):
    server, _admin, _oid = lunas
    kode, isi, _t = _anak(server)
    assert kode == 200 and isi.count('href="/anak/%d/peta"' % server.anak_a) == 1 and "Janji laporan terbit" in _teks(isi)
    for bagian in ("rencana", "latihan", "riwayat"):
        assert "/peta" not in _anak(server, bagian=bagian)[1], bagian
    _siapkan_draf(server)
    assert "Draf laporan siap dilengkapi" in _teks(_anak(server)[1])
    assert _terbitkan(server)[0] == 303
    assert "Laporan sudah terbit" in _teks(_anak(server)[1])


def test_kartu_tidak_ada_tanpa_order_atau_belum_lunas(bayar_purna):
    kode, isi, _t = _anak(bayar_purna)
    assert kode == 200 and "/peta" not in isi                 # belum ada order
    order_bayar(bayar_purna)
    kode, isi, _t = _anak(bayar_purna)
    assert kode == 200 and "/peta" not in isi                 # order belum lunas


def test_kartu_tidak_ada_untuk_order_ditahan_dan_direfund(lunas, jam):
    server, admin, oid = lunas
    jadikan_ditahan(server, oid, jam)
    assert "/peta" not in _anak(server)[1]
    assert kirim_aksi(server, admin, REFUND, oid)[0] == 303
    assert "/peta" not in _anak(server)[1]


@pytest.mark.parametrize("galat", [admin_store.StoreBelumSiap("x"), sqlite3.OperationalError("x"), OSError("x"),
                                   pesanan.PesananError("x")])
def test_kartu_toleran_galat_ledger_halaman_anak_tetap_200_tanpa_kartu(lunas, monkeypatch, galat):
    server, _admin, _oid = lunas

    def gagal(*_a, **_k):
        raise galat

    monkeypatch.setattr(pgh, "_buka_admin", gagal)
    kode, isi, _t = _anak(server)
    assert kode == 200 and "/peta" not in isi and "Traceback" not in isi


def test_kartu_galat_apa_pun_dari_ledger_halaman_anak_tetap_200_tanpa_kartu_dan_log_hanya_tipe(
        lunas, monkeypatch, caplog):
    server, _admin, _oid = lunas

    def gagal(*_a, **_k):
        raise KeyError("RAHASIA-SINTETIS-123")

    monkeypatch.setattr(po, "order_peta_untuk_siswa", gagal)
    with caplog.at_level("WARNING", logger=pgh.__name__):
        kode, isi, _t = _anak(server)
    assert kode == 200 and "/peta" not in isi and "Traceback" not in isi
    assert "KeyError" in caplog.text and "RAHASIA-SINTETIS-123" not in caplog.text


def test_kartu_galat_apa_pun_dari_toko_laporan_halaman_anak_tetap_200_tanpa_kartu(lunas, monkeypatch):
    server, _admin, _oid = lunas

    def gagal(*_a, **_k):
        raise KeyError("x")

    monkeypatch.setattr(peta_laporan_store, "ambil", gagal)
    kode, isi, _t = _anak(server)
    assert kode == 200 and "/peta" not in isi


def test_kartu_tidak_menulis_purna_walau_laporan_terbit_belum_tercatat(lunas, monkeypatch):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    asli = pgh._buka_admin
    monkeypatch.setattr(pgh, "_buka_admin", lambda tulis=False: (_ for _ in ()).throw(sqlite3.OperationalError("x"))
                        if tulis else asli(tulis))
    assert _terbitkan(server)[0] == 303
    monkeypatch.setattr(pgh, "_buka_admin", asli)
    _anak(server)
    assert potret_efek()["purna_laporan_terbit"] == []


# --- ledger admin tak terbaca -------------------------------------------------------------------

@pytest.mark.parametrize("galat", [admin_store.StoreBelumSiap("rahasia-sintetis"), sqlite3.OperationalError("rahasia-sintetis"),
                                   OSError("rahasia-sintetis"), pesanan.PesananError("rahasia-sintetis")])
def test_ledger_tak_terbaca_halaman_belum_bisa_dibuka_503_tanpa_efek(lunas, monkeypatch, caplog, galat):
    server, _admin, _oid = lunas
    sebelum = _efek(server)

    def gagal(*_a, **_k):
        raise galat

    monkeypatch.setattr(pgh, "_buka_admin", gagal)
    with caplog.at_level("DEBUG"):
        kode, isi, _t = _get(server)
        assert kode == 503 and "belum bisa dibuka" in isi and "rahasia-sintetis" not in isi and "Traceback" not in isi
        for aksi in ("buat", "catatan", "terbitkan", "hapus"):
            kode, isi, _t = _post(server, aksi, {"catatan": "x", "konfirmasi": "1"})
            assert kode == 503 and "rahasia-sintetis" not in isi, aksi
    assert type(galat).__name__ in caplog.text and "rahasia-sintetis" not in caplog.text
    assert _efek(server) == sebelum


# --- sinkron purna: gagal tidak membatalkan laporan, lalu diulang ------------------------------------

def _gagalkan_tulis_purna(monkeypatch):
    asli = pgh._buka_admin

    def selektif(tulis=False):
        if tulis:
            raise sqlite3.OperationalError("rahasia-sintetis")
        return asli(tulis)

    monkeypatch.setattr(pgh, "_buka_admin", selektif)
    return asli


def test_pencatatan_purna_gagal_laporan_tetap_terbit_303_dan_log_hanya_tipe(lunas, monkeypatch, caplog):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    _gagalkan_tulis_purna(monkeypatch)
    with caplog.at_level("DEBUG"):
        kode, isi, _t = _terbitkan(server)
    assert kode == 303 and "rahasia-sintetis" not in isi
    assert _laporan_baris(server)[0][6] is not None and potret_efek()["purna_laporan_terbit"] == []
    assert "OperationalError" in caplog.text and "rahasia-sintetis" not in caplog.text and "Traceback" not in caplog.text


def test_pencatatan_purna_konflik_dari_domain_tidak_membatalkan_laporan(lunas, monkeypatch):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    monkeypatch.setattr(pgh.purna, "catat_terbit", lambda *a, **k: (_ for _ in ()).throw(pesanan.PesananKonflik("x")))
    assert _terbitkan(server)[0] == 303 and _laporan_baris(server)[0][6] is not None
    assert potret_efek()["purna_laporan_terbit"] == []


def test_pengulangan_saat_guru_membuka_halaman_dengan_waktu_terbit_laporan(lunas, monkeypatch, jam):
    server, _admin, oid = lunas
    _siapkan_draf(server)
    jam.maju_jam(1)
    asli = _gagalkan_tulis_purna(monkeypatch)
    waktu_terbit = jam()
    assert _terbitkan(server)[0] == 303 and potret_efek()["purna_laporan_terbit"] == []
    monkeypatch.setattr(pgh, "_buka_admin", asli)
    jam.maju_jam(7)
    kode, isi, _t = _get(server)
    assert kode == 200
    (terbit,) = potret_efek()["purna_laporan_terbit"]
    assert terbit[:3] == (oid, waktu_terbit, "guru")           # bukan jam pengulangan
    assert "Laporan terbit:" in _teks(isi)
    _get(server)
    assert len(potret_efek()["purna_laporan_terbit"]) == 1     # idempoten


def test_admin_membuka_halaman_tidak_mengulang_pencatatan_purna(lunas, monkeypatch):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    asli = _gagalkan_tulis_purna(monkeypatch)
    assert _terbitkan(server)[0] == 303
    monkeypatch.setattr(pgh, "_buka_admin", asli)
    assert _get(server, AKUN_ADMIN)[0] == 200
    assert potret_efek()["purna_laporan_terbit"] == []


def test_pelaku_purna_memakai_akun_guru_sesi_bukan_admin(lunas):
    server, _admin, _oid = lunas
    _siapkan_draf(server)
    assert _terbitkan(server)[0] == 303
    assert potret_efek()["purna_laporan_terbit"][0][2] == "guru"
