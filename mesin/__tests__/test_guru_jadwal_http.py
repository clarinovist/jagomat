"""Jadwal saya dan Kelas saya (guru, baca-saja) lewat HTTP: kepemilikan, 404 identik, tanpa bocor, tanpa efek samping.

Kasus H1-H8 dari plan Fase 1. Data sepenuhnya sintetis: akun guru dan admin dari cek_http_kit, murid feby, dan anak
buatan. Jam dipatok lewat fixture `jam` (AWAL 23 Nov 2026 pukul 10.00 WIB), jadi sesi Mini 21 Nov sudah lewat.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import admin_store
import auth
import database
import guru_jadwal_pages as halaman
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import jadwal_store as js
import kelas_kit
import schema_jadwal
import schema_tagihan_catatan
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, server, tambah_anak  # noqa: F401
from harian_kit import jam  # noqa: F401
from kelas_http_kit import pasang_skema
from pesanan_transfer_pages import waktu_wib

ADMIN = "admin_sintetis"
LOKASI_MEET = "https://meet.google.com/abc-defg-hij"
LOKASI_ZOOM = "https://zoom.us/j/123456789"
TIDAK_ADA = "/guru/tidak-ada"
KELAS_TIDAK_ADA = "/guru/kelas/klp_" + "0" * 32
KELAS_CACAT = "/guru/kelas/bukan-id"
PERLU_MASUK = "perlu masuk"
JUMLAH_PERTEMUAN = 8  # sesi per kelompok (jadwal_pertemuan ke 1..8)
NAMA_KELOMPOK_KOSONG = "Mini Kosong Sintetis"
LABEL_DIBATALKAN = " · " + halaman.COPY_DIBATALKAN
POLA_HREF_KELAS = re.compile(r'href="/guru/kelas/(klp_[0-9a-f]{32})"')
POLA_AKSI_TAUTAN = re.compile(r'action="/guru/kelas/(klp_[0-9a-f]{32})/tautan"')  # form tambah anak (3b-2)
POLA_BARIS_KELAS = re.compile(r'<li><strong>([^<]*)</strong><p class="jadwal-meta-st">([^<]*)</p>')
POLA_SESI_DETAIL = re.compile(r"<li>Pertemuan (\d+) · ([^<]*)")
POLA_BARIS_JADWAL = re.compile(r'<strong>([^<]*)</strong><p class="jadwal-meta-st">Pertemuan (\d+) · ([^<]*)')


def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, guru, siswa, n, tanggal, jam="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _lunas_mini_akses_lewat(kon, siswa, n):
    """Order Mini lunas dengan masa akses sebulan yang berakhir 19 Nov (disetujui 19 Okt, sebelum jam uji 23 Nov)."""
    tagihan, bukti_id = kelas_kit.menunggu(kon, siswa, "mini", n, sekarang="2026-10-19T09:00:00",
                                           unggah_pada="2026-10-19T09:30:00")
    kelas_kit.setuju(kon, tagihan, bukti_id, sekarang="2026-10-19T10:00:00")
    return tagihan.order_id


def _tempatkan_mentah(kon, kelompok_id, order_id):
    """Penempatan langsung lewat SQL: tempatkan() memeriksa pertemuan terhadap masa akses, sedangkan order ini sengaja lewat."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (order_id, kelompok_id, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
    kon.commit()


def _isi_contoh(server):
    """Dua guru: A punya Mini Alfa (anak Alfa) dan Private (anak Beta); B punya Mini Beta dan Private (anak Delta)."""
    anak = {
        "alfa": tambah_anak(server, "Anak Sintetis Alfa", "guru", None),
        "beta": tambah_anak(server, "Anak Sintetis Beta", "guru", None),
        "gamma": tambah_anak(server, "Anak Sintetis Gamma", "guru-b", None),
        "delta": tambah_anak(server, "Anak Sintetis Delta", "guru-b", None),
    }
    guru_a, guru_b = id_akun(AKUN_A), id_akun(AKUN_B)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid_a = js.buat_kelompok(kon, ADMIN, nama="Mini Alfa", lokasi=LOKASI_MEET, guru_id=guru_a, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kid_b = js.buat_kelompok(kon, ADMIN, nama="Mini Beta", lokasi=LOKASI_ZOOM, guru_id=guru_b, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        ord_alfa = _tempatkan_mini(kon, kid_a, anak["alfa"], n=1)
        ord_beta = _tempatkan_privat(kon, guru_a, anak["beta"], n=2, tanggal="2026-11-25")
        _tempatkan_mini(kon, kid_b, anak["gamma"], n=3)
        ord_delta = _tempatkan_privat(kon, guru_b, anak["delta"], n=4, tanggal="2026-11-26", jam="10:00")
        kon.commit()
    return {"kid_a": kid_a, "kid_b": kid_b, "ord_alfa": ord_alfa, "ord_beta": ord_beta, "ord_delta": ord_delta}


@pytest.fixture()
def jadwal(server, jam):
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)
    return _isi_contoh(server)


@pytest.fixture(autouse=True)
def berkas_catatan(tmp_path, monkeypatch):
    """Catatan pertemuan dialihkan ke tmp_path agar tes ini tidak pernah menyentuh /data. Belum dibuat."""
    berkas = tmp_path / "guru-pertemuan-uji.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    return berkas


def _hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- H1: pemilik melihat data sendiri, tanpa id mentah ------------------------------------

def test_guru_pemilik_melihat_jadwal_dan_kelas_sendiri(server, jadwal):
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Mini Alfa" in isi and "Anak Sintetis Beta" in isi
    assert "24 November 2026 pukul 09.00 WIB" in isi
    assert "21 November 2026" not in _bagian_mendatang(isi)
    assert "Mini Beta" not in isi and "Anak Sintetis Gamma" not in isi and "Anak Sintetis Delta" not in isi

    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200
    assert "Mini Alfa" in isi and "Mini Beta" not in isi

    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "Anak Sintetis Alfa" in isi and LOKASI_MEET in isi
    assert "Anak Sintetis Beta" not in isi


def test_halaman_guru_tidak_membocorkan_id_mentah(server, jadwal):
    kelas_diharapkan = {
        "/guru/jadwal": {jadwal["kid_a"]},
        "/guru/kelas": {jadwal["kid_a"]},
        "/guru/kelas/" + jadwal["kid_a"]: set(),
    }
    for jalur, diharapkan in kelas_diharapkan.items():
        kode, isi, _ = server.minta(jalur, auth=AKUN_A)
        assert kode == 200, jalur
        assert "kor_" not in isi and "akun_" not in isi, jalur
        assert "siswa_id" not in isi and "order_id" not in isi, jalur
        hrefs = POLA_HREF_KELAS.findall(isi)
        # id kelompok boleh muncul di href kelas dan di action form tambah anak milik pemilik sendiri (3b-2)
        assert isi.count("klp_") == len(hrefs) + len(POLA_AKSI_TAUTAN.findall(isi)), jalur
        assert set(hrefs) == diharapkan, jalur
        if diharapkan:
            assert hrefs, jalur


# --- H2: guru lain mendapat 404 identik ---------------------------------------------------

def test_detail_kelas_milik_guru_lain_404_identik(server, jadwal):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    assert acuan[0] == 404
    for jalur in ("/guru/kelas/" + jadwal["kid_a"], KELAS_TIDAK_ADA, KELAS_CACAT):
        kode, isi, _ = server.minta(jalur, auth=AKUN_B)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur
        assert "Mini Alfa" not in isi


# --- H3: tanpa efek samping pada DB ---------------------------------------------------------

def test_permintaan_guru_tidak_mengubah_db(server, jadwal):
    admin_db = Path(admin_store.BAWAAN)
    sebelum = (_hash(admin_db), _hash(server.db))
    for jalur, akun in (
        ("/guru/kelas/" + jadwal["kid_a"], AKUN_B),
        ("/guru/kelas/" + jadwal["kid_a"], AKUN_A),
        ("/guru/jadwal", AKUN_A),
        ("/guru/kelas", AKUN_A),
        (KELAS_TIDAK_ADA, AKUN_A),
    ):
        server.minta(jalur, auth=akun)
    assert (_hash(admin_db), _hash(server.db)) == sebelum


# --- H4: parameter URL tidak mengganti pemilik -------------------------------------------

def test_guru_id_di_query_diabaikan(server, jadwal):
    for jalur in ("/guru/kelas", "/guru/jadwal"):
        acuan = server.minta(jalur, auth=AKUN_B)
        kode, isi, _ = server.minta(jalur + "?guru_id=" + id_akun(AKUN_A), auth=AKUN_B)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur
        assert "Mini Alfa" not in isi and "Anak Sintetis Alfa" not in isi and "Anak Sintetis Beta" not in isi


# --- H5: selain guru pemilik -> 404 identik / 401 -----------------------------------------

@pytest.mark.parametrize("sufiks", ["/guru/jadwal", "/guru/kelas", "/guru/kelas/{kid_a}"])
def test_admin_mendapat_404_identik_rute_tak_dikenal(server, jadwal, sufiks):
    jalur = sufiks.format(kid_a=jadwal["kid_a"])
    acuan = server.minta(TIDAK_ADA, auth=AKUN_ADMIN)
    assert acuan[0] == 404
    kode, isi, _ = server.minta(jalur, auth=AKUN_ADMIN)
    assert (kode, isi) == (acuan[0], acuan[1]), jalur
    assert "Mini Alfa" not in isi


def test_murid_dan_anonim_ditolak_palang_sandi(server, jadwal):
    for akun in (AKUN_MURID, None):
        kode, isi, _ = server.minta("/guru/jadwal", auth=akun)
        assert kode == 401, akun
        assert PERLU_MASUK in isi.lower()
        assert "Mini Alfa" not in isi


def test_mode_lokal_tanpa_principal_404_identik_bukan_500(server, jadwal, monkeypatch):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, isi, _ = server.minta(jalur)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur


# --- H6: header respons privat ------------------------------------------------------------

def test_respons_guru_memakai_header_privat(server, jadwal):
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, _isi, tajuk = server.minta(jalur, auth=AKUN_A)
        assert kode == 200, jalur
        assert tajuk.get("Cache-Control") == "no-store", jalur
        assert tajuk.get("Referrer-Policy") == "no-referrer", jalur


# --- H9: anggota dengan masa akses lewat diberi tanda teks, nama tetap tampil ------------------

def test_anggota_akses_habis_diberi_tanda_teks_dan_nama_tetap_tampil(server, jadwal):
    siswa = tambah_anak(server, "Anak Sintetis Epsilon", "guru", None)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = _lunas_mini_akses_lewat(kon, siswa, n=9)
        _tempatkan_mentah(kon, jadwal["kid_a"], order)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "<li>Anak Sintetis Epsilon · Akses habis</li>" in isi
    assert "<li>Anak Sintetis Alfa</li>" in isi
    assert isi.count("Akses habis") == 1
    assert "Terisi 2 dari 5 anak." in isi
    assert "siswa_id" not in isi and "order_id" not in isi and "akun_" not in isi


# --- H7: DB admin belum dipasang atau rusak ------------------------------------------------

def test_db_admin_belum_dipasang_daftar_kosong_dan_detail_404(server):
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and "Belum ada jadwal." in isi
    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200 and "Belum ada kelas" in isi
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    assert server.minta(KELAS_TIDAK_ADA, auth=AKUN_A)[:2] == acuan[:2]


def test_db_admin_rusak_diperlakukan_belum_siap(server):
    Path(admin_store.BAWAAN).write_bytes(b"bukan basis data " * 64)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and "Belum ada jadwal." in isi
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    assert server.minta(KELAS_TIDAK_ADA, auth=AKUN_A)[:2] == acuan[:2]


# --- H8: topbar guru ----------------------------------------------------------------------

def test_topbar_guru_memuat_dua_tautan_baru_dan_admin_tidak(server, jadwal):
    _kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert '<a href="/guru/jadwal" aria-current="page">Jadwal saya</a>' in isi
    assert '<a href="/guru/kelas">Kelas saya</a>' in isi

    _kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert '<a href="/guru/kelas" aria-current="page">Kelas saya</a>' in isi

    _kode, isi, _ = server.minta("/guru", auth=AKUN_A)
    assert '<a href="/guru/jadwal">Jadwal saya</a>' in isi
    assert '<a href="/guru/kelas">Kelas saya</a>' in isi

    kode, isi, _ = server.minta("/admin", auth=AKUN_ADMIN)
    assert kode == 200
    assert "Jadwal saya" not in isi and "Kelas saya" not in isi


def test_latihan_tak_terbaca_nama_anak_memakai_placeholder(server, jadwal, monkeypatch, tmp_path):
    """latihan.db rusak (berkas ada, isinya bukan basis data): nama anak jadi placeholder, halaman tetap 200."""
    rusak = tmp_path / "latihan-rusak.db"
    rusak.write_bytes(b"bukan basis data " * 64)
    monkeypatch.setattr(database, "BAWAAN", rusak)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "<li>Anak</li>" in isi
    assert "Anak Sintetis Alfa" not in isi
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Private: Anak" in isi and "Anak Sintetis Beta" not in isi


# --- J: "Sudah berlangsung" dan tautan catat (Fase 2a-2) ----------------------------------------

RUTE_PERTEMUAN = "/guru/pertemuan/"
PETA_KUNCI_BOCOR = re.compile(r"(klp|kor)_[0-9a-f]{32}:")
POLA_ID_TAUTAN = re.compile(r'href="/guru/pertemuan/([0-9]+)"')
POLA_FORM_TOKEN = re.compile(r'name="token"')
TEKS_CATAT = ">Catat</a>"
TEKS_UBAH = ">Ubah catatan</a>"
LOKASI_RENDER = "https://meet.google.com/abc-defg-hij"
JAM_PRIVAT_SUDAH_MULAI = "2026-11-27T00:00:00"   # privat A (25 Nov) dan B (26 Nov) sudah mulai
JAM_BELUM_ADA_BERLANGSUNG = "2026-11-01T00:00:00"  # semua sesi masih di masa depan


def _bagian_mendatang(isi: str) -> str:
    """Isi dari penanda 'Pertemuan mendatang' ke akhir halaman; bagian 'Sudah berlangsung' tidak ikut."""
    return isi.split('aria-label="Pertemuan mendatang"', 1)[1]


def _sesi_kelompok(kelompok_id, ke):
    with js.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT id, mulai, menit, dibatalkan FROM jadwal_pertemuan WHERE kelompok_id=? AND ke=?",
                           (kelompok_id, ke)).fetchone()


def _sesi_privat(order_id, ke):
    with js.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT id, mulai, menit, dibatalkan FROM jadwal_pertemuan WHERE order_id=? AND ke=?",
                           (order_id, ke)).fetchone()


def _geser(waktu: str, **selisih) -> str:
    return (datetime.strptime(waktu, aturan.FORMAT_WAKTU) + timedelta(**selisih)).strftime(aturan.FORMAT_WAKTU)


def _catat(kunci: str, sesi, order_id: str, berkas) -> None:
    """Catatan sintetis lewat penyimpanan langsung (tanpa form), dengan id akun guru A sebagai pencatat."""
    dasar.catat(kunci=kunci, pertemuan_id=sesi["id"], mulai=sesi["mulai"], topik=aturan.daftar_topik_jurnal()[0],
                hadir={order_id: "hadir"}, oleh=id_akun(AKUN_A), peran="guru", pada="2026-11-27T01:00:00",
                path=berkas)


def _pasang_versi_asing(berkas) -> None:
    with closing(sqlite3.connect(str(berkas))) as kon:
        kon.execute("PRAGMA user_version=7")
        kon.commit()


def _ringkasan_sesi(ke: int, aksi) -> dict:
    return {"ke": ke, "mulai": "2026-11-2%dT02:00:00" % ke, "menit": 60, "dibatalkan": False, "aksi": aksi}


def test_jadwal_tampilkan_sudah_berlangsung_dengan_tautan_catat(server, jadwal):
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Sudah berlangsung" in isi and "Belum dicatat" in isi
    assert "21 November 2026 pukul 09.00 WIB" in isi
    assert f'href="{RUTE_PERTEMUAN}{sesi["id"]}">Catat</a>' in isi


def test_setelah_dicatat_tampil_sudah_dicatat_dan_ubah_catatan(server, jadwal, berkas_catatan):
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    _catat(aturan.kunci_pertemuan(jadwal["kid_a"], 1), sesi, jadwal["ord_alfa"], berkas_catatan)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Sudah dicatat" in isi and "Belum dicatat" not in isi
    assert f'href="{RUTE_PERTEMUAN}{sesi["id"]}">Ubah catatan</a>' in isi


def test_tanpa_berkas_catatan_tetap_catat_dan_tidak_membuat_berkas(server, jadwal, berkas_catatan):
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and TEKS_CATAT in isi
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200 and TEKS_CATAT in isi
    assert not berkas_catatan.exists()


def test_versi_skema_asing_tetap_200_dan_tampil_catat(server, jadwal, berkas_catatan):
    _pasang_versi_asing(berkas_catatan)
    sebelum = _hash(berkas_catatan)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and TEKS_CATAT in isi
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200 and TEKS_CATAT in isi
    assert _hash(berkas_catatan) == sebelum


def test_berkas_catatan_rusak_dianggap_belum_dicatat(server, jadwal, berkas_catatan):
    berkas_catatan.write_bytes(b"bukan basis data " * 64)
    sebelum = _hash(berkas_catatan)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and TEKS_CATAT in isi
    assert _hash(berkas_catatan) == sebelum


def test_guru_b_tidak_melihat_pertemuan_guru_a(server, jadwal):
    sesi_alfa = _sesi_kelompok(jadwal["kid_a"], 1)
    sesi_gamma = _sesi_kelompok(jadwal["kid_b"], 1)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_B)
    assert kode == 200
    assert f'href="{RUTE_PERTEMUAN}{sesi_gamma["id"]}">Catat</a>' in isi
    assert f'href="{RUTE_PERTEMUAN}{sesi_alfa["id"]}"' not in isi
    assert "Mini Alfa" not in isi


def test_tanpa_pertemuan_berlangsung_tidak_memuat_bagian(server, jadwal, jam):
    jam.nilai = JAM_BELUM_ADA_BERLANGSUNG
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Sudah berlangsung" not in isi and "Pertemuan mendatang" in isi
    assert RUTE_PERTEMUAN not in isi


def test_detail_tautan_hanya_sesi_yang_boleh_dicatat(server, jadwal):
    sesi1 = _sesi_kelompok(jadwal["kid_a"], 1)
    sesi2 = _sesi_kelompok(jadwal["kid_a"], 2)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert POLA_ID_TAUTAN.findall(isi) == [str(sesi1["id"])]
    assert isi.count("Belum dicatat") == 1
    assert f'href="{RUTE_PERTEMUAN}{sesi2["id"]}"' not in isi


def test_detail_setelah_dicatat_tampil_ubah_catatan(server, jadwal, berkas_catatan):
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    _catat(aturan.kunci_pertemuan(jadwal["kid_a"], 1), sesi, jadwal["ord_alfa"], berkas_catatan)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert isi.count("Sudah dicatat") == 1 and TEKS_UBAH in isi


def _ubah_admin(sql: str, parameter) -> None:
    """UPDATE langsung pada DB admin sintetis (menggeser jadwal atau penempatan seperti tindakan admin)."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kon.execute(sql, parameter)
        kon.commit()


def test_jadwal_pertemuan_digeser_sesudah_dicatat_tampil_belum_dicatat(server, jadwal, berkas_catatan):
    """Catatan menempel pada (kunci, mulai): slot yang digeser admin tidak mewarisi 'Sudah dicatat'."""
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    _catat(aturan.kunci_pertemuan(jadwal["kid_a"], 1), sesi, jadwal["ord_alfa"], berkas_catatan)
    _ubah_admin("UPDATE jadwal_pertemuan SET mulai=? WHERE id=?", (_geser(sesi["mulai"], hours=1), sesi["id"]))

    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)

    assert kode == 200
    assert f'href="{RUTE_PERTEMUAN}{sesi["id"]}">Catat</a>' in isi
    assert "Sudah dicatat" not in isi and TEKS_UBAH not in isi


def test_detail_pertemuan_digeser_sesudah_dicatat_tampil_belum_dicatat(server, jadwal, berkas_catatan):
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    _catat(aturan.kunci_pertemuan(jadwal["kid_a"], 1), sesi, jadwal["ord_alfa"], berkas_catatan)
    _ubah_admin("UPDATE jadwal_pertemuan SET mulai=? WHERE id=?", (_geser(sesi["mulai"], hours=1), sesi["id"]))

    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)

    assert kode == 200
    assert POLA_ID_TAUTAN.findall(isi) == [str(sesi["id"])]
    assert "Sudah dicatat" not in isi and TEKS_UBAH not in isi and "Belum dicatat" in isi


def test_sesi_tanpa_anggota_pada_saat_itu_tidak_diberi_tautan_di_detail_dan_jadwal(server, jadwal):
    """Anggota yang penempatannya dibuat sesudah sesi mulai tidak ada di sesi itu (R4): tidak ada yang bisa dicatat."""
    sesi = _sesi_kelompok(jadwal["kid_a"], 1)
    sesudah_mulai = _geser(sesi["mulai"], days=1)
    # Penempatan tidak bisa di-UPDATE (trigger): sama seperti admin, lepas lalu tempatkan ulang pada waktu yang lebih baru.
    _ubah_admin("DELETE FROM jadwal_penempatan WHERE order_id=?", (jadwal["ord_alfa"],))
    _ubah_admin("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (jadwal["ord_alfa"], jadwal["kid_a"], sesudah_mulai, sesudah_mulai, ADMIN, ADMIN))

    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert POLA_ID_TAUTAN.findall(isi) == []

    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert f'href="{RUTE_PERTEMUAN}{sesi["id"]}"' not in isi


def test_detail_sesi_dibatalkan_tanpa_tautan(server, jadwal):
    sesi1 = _sesi_kelompok(jadwal["kid_a"], 1)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.batalkan_pertemuan(kon, ADMIN, sesi1["id"], batal=True, sekarang=kelas_kit.KINI)
        kon.commit()
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert str(sesi1["id"]) not in POLA_ID_TAUTAN.findall(isi)


def test_detail_sesi_terkunci_tanpa_tautan(server, jadwal, jam):
    sesi1 = _sesi_kelompok(jadwal["kid_a"], 1)
    sesi2 = _sesi_kelompok(jadwal["kid_a"], 2)
    jam.nilai = _geser(aturan.selesai(sesi1["mulai"], sesi1["menit"]), days=aturan.JENDELA_KOREKSI.days)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    ids = POLA_ID_TAUTAN.findall(isi)
    assert str(sesi1["id"]) not in ids and str(sesi2["id"]) in ids


def test_privat_tercatat_tampil_sudah_dicatat(server, jadwal, berkas_catatan, jam):
    jam.nilai = JAM_PRIVAT_SUDAH_MULAI
    privat = _sesi_privat(jadwal["ord_beta"], 1)
    _catat(aturan.kunci_pertemuan(jadwal["ord_beta"], 1), privat, jadwal["ord_beta"], berkas_catatan)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Private: Anak Sintetis Beta" in isi
    assert f'href="{RUTE_PERTEMUAN}{privat["id"]}">Ubah catatan</a>' in isi


def test_privasi_tidak_membocorkan_kunci_setelah_privat_mulai(server, jadwal, jam):
    jam.nilai = JAM_PRIVAT_SUDAH_MULAI
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, isi, _ = server.minta(jalur, auth=AKUN_A)
        assert kode == 200, jalur
        assert PETA_KUNCI_BOCOR.search(isi) is None, jalur
        assert "kor_" not in isi and "akun_" not in isi, jalur
        assert "siswa_id" not in isi and "order_id" not in isi, jalur
    _kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    hrefs = POLA_HREF_KELAS.findall(isi)
    assert isi.count("klp_") == len(hrefs)
    assert set(hrefs) == {jadwal["kid_a"]}  # hanya kelompok milik guru A, bukan sekadar jumlah yang cocok


def test_setiap_tautan_catat_membuka_form_milik_guru(server, jadwal, jam):
    jam.nilai = JAM_PRIVAT_SUDAH_MULAI
    _kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    ids = POLA_ID_TAUTAN.findall(isi)
    assert str(_sesi_kelompok(jadwal["kid_a"], 1)["id"]) in ids
    assert str(_sesi_privat(jadwal["ord_beta"], 1)["id"]) in ids
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    for id_teks in ids:
        kode, isi_form, _ = server.minta(RUTE_PERTEMUAN + id_teks, auth=AKUN_A)
        assert kode == 200 and POLA_FORM_TOKEN.search(isi_form), id_teks
        assert server.minta(RUTE_PERTEMUAN + id_teks, auth=AKUN_B)[:2] == acuan[:2], id_teks


def test_render_tanpa_berlangsung_sama_dengan_bawaan():
    ident = ("akun_" + "a" * 32, "guru")
    pertemuan = [{"judul": "Mini Class: Sintetis", "ke": 1, "mulai": "2026-11-21T02:00:00",
                  "dibatalkan": False, "kelas_id": "klp_" + "0" * 32}]
    isi = halaman.halaman_jadwal(ident, pertemuan)
    assert isi == halaman.halaman_jadwal(ident, pertemuan, ())
    assert b"Sudah berlangsung" not in isi


def test_render_berlangsung_teks_status_dan_tautan_tanpa_id_mentah():
    ident = ("akun_" + "a" * 32, "guru")
    berlangsung = [
        {"judul": "Private: Anak Sintetis", "ke": 2, "mulai": "2026-11-23T09:30:00", "tercatat": False,
         "id_pertemuan": 77},
        {"judul": "Mini Class: Sintetis", "ke": 1, "mulai": "2026-11-21T02:00:00", "tercatat": True,
         "id_pertemuan": 78},
    ]
    isi = halaman.halaman_jadwal(ident, [], berlangsung).decode("utf-8")
    assert "Sudah berlangsung" in isi
    assert "Catat atau ubah kehadiran dan jurnal. Bisa diubah sampai 7 hari setelah pertemuan selesai." in isi
    assert 'href="/guru/pertemuan/77">Catat</a>' in isi
    assert 'href="/guru/pertemuan/78">Ubah catatan</a>' in isi
    assert "Belum dicatat" in isi and "Sudah dicatat" in isi
    assert not re.search(r"kor_|klp_[0-9a-f]|siswa_id|order_id", isi)


def test_render_detail_sesi_tanpa_aksi_tanpa_tautan():
    ident = ("akun_" + "a" * 32, "guru")
    kelas = {"nama": "Kelompok Sintetis", "lokasi": LOKASI_RENDER, "kuota": 5, "terisi": 1,
             "anggota": [{"nama": "Anak Sintetis", "akses_habis": False}],
             "sesi": [_ringkasan_sesi(1, None), _ringkasan_sesi(2, {"id_pertemuan": 91, "tercatat": True})]}
    isi = halaman.halaman_detail(ident, kelas).decode("utf-8")
    assert isi.count(RUTE_PERTEMUAN) == 1
    assert 'href="/guru/pertemuan/91">Ubah catatan</a>' in isi
    assert "Sudah dicatat" in isi and "Belum dicatat" not in isi


# --- T1, T2, T5 (celah tes Fase 1): pertemuan berikut, label Dibatalkan, dan latihan.db baca-saja ----

def _batalkan_admin(pertemuan_id: int) -> None:
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.batalkan_pertemuan(kon, ADMIN, pertemuan_id, batal=True, sekarang=kelas_kit.KINI)
        kon.commit()


def _buat_kelompok_tanpa_mendatang() -> str:
    """Kelompok Mini milik guru A dengan semua pertemuannya dibatalkan: tidak ada pertemuan berikut."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid = js.buat_kelompok(kon, ADMIN, nama=NAMA_KELOMPOK_KOSONG, lokasi=LOKASI_MEET,
                               guru_id=id_akun(AKUN_A), kuota=5, tanggal="2026-11-21", jam="09:00",
                               sekarang=kelas_kit.KINI)
        for sesi in js.detail_kelompok(kon, kid)["sesi"]:
            js.batalkan_pertemuan(kon, ADMIN, sesi["id"], batal=True, sekarang=kelas_kit.KINI)
        kon.commit()
    return kid


def _meta_kelas(isi: str) -> dict:
    """Teks meta tiap kelompok di `/guru/kelas`, dikunci nama kelompok (satu baris per kelompok)."""
    return dict(POLA_BARIS_KELAS.findall(isi))


# T1: pertemuan berikut di `/guru/kelas` (daftar_kelas) memakai pertemuan aktif paling awal, atau copy kosong.

def test_kelas_saya_memuat_pertemuan_berikut_yang_aktif_paling_awal(server, jadwal):
    ke2 = _sesi_kelompok(jadwal["kid_a"], 2)
    ke3 = _sesi_kelompok(jadwal["kid_a"], 3)
    _batalkan_admin(ke2["id"])
    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200
    assert f"Pertemuan berikut: {waktu_wib(ke3['mulai'])}" in _meta_kelas(isi)["Mini Alfa"]


def test_kelas_saya_tanpa_pertemuan_mendatang_memuat_copy_kosong(server, jadwal):
    _buat_kelompok_tanpa_mendatang()
    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200
    meta = _meta_kelas(isi)
    assert halaman.COPY_TIDAK_ADA_BERIKUT in meta[NAMA_KELOMPOK_KOSONG]
    assert "Pertemuan berikut" not in meta[NAMA_KELOMPOK_KOSONG]
    assert "Pertemuan berikut" in meta["Mini Alfa"]


# T2: label "Dibatalkan" hanya pada pertemuan yang dibatalkan, di detail kelas dan di Jadwal saya.

def test_detail_kelas_beri_label_dibatalkan_hanya_pada_sesi_yang_batal(server, jadwal):
    _batalkan_admin(_sesi_kelompok(jadwal["kid_a"], 2)["id"])
    _batalkan_admin(_sesi_kelompok(jadwal["kid_a"], 5)["id"])
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    baris = POLA_SESI_DETAIL.findall(isi)
    assert len(baris) == JUMLAH_PERTEMUAN
    assert {int(ke) for ke, teks in baris if LABEL_DIBATALKAN in teks} == {2, 5}
    assert isi.count(LABEL_DIBATALKAN) == 2


def test_jadwal_saya_beri_label_dibatalkan_untuk_mini_dan_privat_yang_batal(server, jadwal):
    _batalkan_admin(_sesi_kelompok(jadwal["kid_a"], 2)["id"])
    _batalkan_admin(_sesi_privat(jadwal["ord_beta"], 3)["id"])
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    mendatang = _bagian_mendatang(isi)
    batal = {(judul, int(ke)) for judul, ke, sisa in POLA_BARIS_JADWAL.findall(mendatang) if LABEL_DIBATALKAN in sisa}
    assert batal == {("Mini Class: Mini Alfa", 2), ("Private: Anak Sintetis Beta", 3)}
    assert mendatang.count(LABEL_DIBATALKAN) == 2


# T5: latihan.db dibuka mode ro. Berkas yang belum ada tidak boleh terbuat; nama anak jadi placeholder.

def test_latihan_belum_ada_tidak_dibuat_dan_nama_anak_jadi_placeholder(server, jadwal, monkeypatch, tmp_path):
    hilang = tmp_path / "latihan-tidak-ada.db"
    monkeypatch.setattr(database, "BAWAAN", hilang)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Private: Anak" in isi and "Anak Sintetis Beta" not in isi
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "<li>Anak</li>" in isi and "Anak Sintetis Alfa" not in isi
    assert not list(tmp_path.glob("latihan-tidak-ada.db*"))
