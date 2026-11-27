"""Rute guru tugas untuk anak tertaut: `/guru/tugas` dan `/guru/tugas/<order_id>` (Fase 3c, WP3).

Gerbang rilis (`guru_tugas_aturan.GURU_TUGAS_AKTIF`), kepemilikan lewat tautan (404 identik), validasi form, token,
duplikat, batas tugas aktif, atomisitas pembuatan sesi dan catat tugas, serta isi halaman (skor hanya bila selesai).
Server HTTP sungguhan (`cek_http_kit.server`), data sepenuhnya sintetis: dua guru, anak buatan milik koordinator
sintetis, akun murid buatan untuk nama login. Tiga berkas (jadwal, latihan.db, tugas) hidup di tmp_path.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import admin_store
import auth
import database
import form_token
import guru_jadwal_pages as halaman_jadwal
import guru_tautan_anak as tautan_anak
import guru_tugas_aturan as gta
import guru_tugas_dasar as gtd
import guru_tugas_http as gth
import jadwal_store as js
import kelas_kit
import learning_cycle_http
import schema_jadwal
import schema_tagihan_catatan
import sessions
import teacher_pages
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah, server, tambah_anak  # noqa: F401
from guru_tautan_kit import hapus_keluarga_sintetis
from harian_kit import jam  # noqa: F401
from kelas_http_kit import pasang_skema

ADMIN_JADWAL = "admin_sintetis"
LOKASI_MEET = "https://meet.google.com/abc-defg-hij"
KOORDINATOR = "koordinator_sintetis"
SANDI_ANAK = "sandi-anak-sintetis-123"
SANDI_GURU_KOSONG = "sandi-guru-kosong-panjang-123"
KELUARGA_HAPUS = "keluarga-hapus"
SANDI_KELUARGA_HAPUS = "sandi-keluarga-hapus-123"
TIDAK_ADA = "/guru/tidak-ada"
RUTE = "/guru/tugas"
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
KINI_AWAL = "2026-11-23T03:00:00"          # 23 Nov 2026 pukul 10.00 WIB
KINI_LAMPAU = "2026-11-20T12:00:00"        # sebelum semua sesi contoh
KINI_AKSES_LEWAT = "2026-12-22T00:00:00"   # akses paket contoh sudah berakhir (20 Des)
TENGGAT_TANGGAL = "2026-11-25"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
POLA_HREF_ORDER = re.compile(r'href="/guru/tugas/kor_[0-9a-f]{32}"')
KATA_RAHASIA = ("kunci", "malrule", "diagnosis", "pembahasan")


# --- fixture dan data sintetis ----------------------------------------------------------------

@pytest.fixture()
def berkas_tugas(tmp_path, monkeypatch):
    """guru-tugas.db sementara; belum ada sampai tulis pertama (kontrak `guru_tugas_dasar`)."""
    berkas = tmp_path / "guru-tugas.db"
    monkeypatch.setenv(gtd.ENV_DB, str(berkas))
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    return berkas


@pytest.fixture()
def tugas(server, jam, berkas_tugas, monkeypatch):
    """Gerbang MENYALA, dua guru dengan anak tertaut (lihat `_isi_contoh`)."""
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)
    jam.nilai = KINI_AWAL
    monkeypatch.setattr(gta, "GURU_TUGAS_AKTIF", True)
    monkeypatch.setattr(learning_cycle_http, "_riwayat", {})
    return _isi_contoh(server)


def _akun_anak(pengguna: str, siswa_id: int) -> str:
    return auth.tambah_akun_dan_principal(pengguna, SANDI_ANAK, "murid", siswa_id=siswa_id).id_akun


def _tempatkan_mini(kon, kelompok_id, siswa, akun, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n, akun=akun)
    js.tempatkan(kon, ADMIN_JADWAL, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, guru, siswa, akun, n, tanggal="2026-11-25", jam_wib="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n, akun=akun)
    js.tempatkan(kon, ADMIN_JADWAL, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam_wib,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _isi_contoh(server):
    """Guru A: Mini Alfa (anak Alfa) dan Private (anak Beta). Guru B: Mini Beta (Gamma) dan Private (Delta).

    Semua anak dimiliki koordinator sintetis, bukan guru mana pun: gerbang `_bisa_lihat_siswa` tetap menolak guru.
    """
    siswa = {nama: tambah_anak(server, "Anak Sintetis " + nama.capitalize(), KOORDINATOR, None)
             for nama in ("alfa", "beta", "gamma", "delta")}
    akun = {nama: _akun_anak("anak-" + nama, sid) for nama, sid in siswa.items()}
    guru_a, guru_b = id_akun(AKUN_A), id_akun(AKUN_B)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid_a = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Alfa", lokasi=LOKASI_MEET, guru_id=guru_a, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kid_b = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Beta", lokasi=LOKASI_MEET, guru_id=guru_b, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        contoh = {
            "ord_alfa": _tempatkan_mini(kon, kid_a, siswa["alfa"], akun["alfa"], n=1),
            "ord_beta": _tempatkan_privat(kon, guru_a, siswa["beta"], akun["beta"], n=2),
            "ord_gamma": _tempatkan_mini(kon, kid_b, siswa["gamma"], akun["gamma"], n=3),
            "ord_delta": _tempatkan_privat(kon, guru_b, siswa["delta"], akun["delta"], n=4,
                                           tanggal="2026-11-26", jam_wib="10:00"),
        }
        kon.commit()
    return {**contoh, **siswa, "akun": akun, "kid_a": kid_a}


# --- util ---------------------------------------------------------------------------------------

def _jalur(order_id) -> str:
    return f"{RUTE}/{order_id}"


def _hash(path):
    """Hash isi berkas, atau None bila berkas belum ada (tanpa membuatnya)."""
    berkas = Path(path)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _keadaan(berkas_tugas):
    """Hash ketiga berkas: jadwal admin, latihan.db, dan guru-tugas.db."""
    return (_hash(admin_store.BAWAAN), _hash(database.BAWAAN), _hash(berkas_tugas))


def _baca(sql: str, parameter=()):
    kon = sqlite3.connect(Path(database.BAWAAN).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return kon.execute(sql, parameter).fetchall()
    finally:
        kon.close()


def _sesi_anak(siswa_id) -> list:
    return [baris[0] for baris in _baca("SELECT id FROM sesi WHERE siswa_id=? ORDER BY id", (siswa_id,))]


def _tandai_selesai(sesi_id: int) -> None:
    kon = sqlite3.connect(str(database.BAWAAN))
    try:
        kon.execute("UPDATE sesi SET selesai=? WHERE id=?", ("2026-11-23T04:00:00", sesi_id))
        kon.commit()
    finally:
        kon.close()


def _geser(kini: str, detik: int) -> str:
    return (datetime.strptime(kini, FORMAT_WAKTU) + timedelta(seconds=detik)).strftime(FORMAT_WAKTU)


TOPIK_P3 = "geometri-datar"          # punya soal untuk P3 (tingkat anak sintetis)
TOPIK_BUKAN_P3 = "aritmatika-lanjut"  # hanya P5 dan P6


def _topik() -> str:
    assert TOPIK_P3 in [id_topik for id_topik, _label in gta.daftar_topik_tugas()]
    return TOPIK_P3


def _principal(akun):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal


def _lokasi(tajuk: dict):
    for nama, nilai in tajuk.items():
        if nama.lower() == "location":
            return nilai
    return None


def _minta_anak(server, order_id, akun=AKUN_A):
    return server.minta(_jalur(order_id), auth=akun)


def _token_form(server, order_id, akun=AKUN_A) -> str:
    kode, isi, _ = _minta_anak(server, order_id, akun)
    assert kode == 200, kode
    return POLA_TOKEN.search(isi).group(1)


def _form(server, order_id, *, topik=None, tenggat="", akun=AKUN_A, **ekstra) -> dict:
    """Isian seperti peramban: token dari halaman anak milik akun itu, topik, dan tenggat (boleh kosong)."""
    data = {"token": _token_form(server, order_id, akun), "topik": _topik() if topik is None else topik,
            "tenggat": tenggat}
    return {**data, **ekstra}


def _kirim(server, order_id, data, akun=AKUN_A):
    return minta_mentah(server, _jalur(order_id), akun, data)


def _buat_tugas(server, tugas, order_id, siswa_id, *, topik=None, tenggat=""):
    kode, _, _ = _kirim(server, order_id, _form(server, order_id, topik=topik, tenggat=tenggat))
    assert kode == 303, kode
    return _sesi_anak(siswa_id)[-1]


def _sesi_langsung(siswa_id: int) -> int:
    """Sesi latihan biasa tanpa lewat HTTP, untuk menyiapkan tugas yang sudah ada."""
    with database.buka() as kon:
        return teacher_pages.buat_sesi_seed_baru(kon, siswa_id, topik=_topik())


def _lepas_penempatan(order_id: str) -> None:
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        versi = kon.execute("SELECT dibuat FROM jadwal_penempatan WHERE order_id=?", (order_id,)).fetchone()[0]
        js.lepas_penempatan(kon, ADMIN_JADWAL, order_id, versi=versi, sekarang=KINI_LAMPAU)
        kon.commit()


def _keadaan_lengkap(berkas_tugas):
    """Hash keempat berkas: jadwal admin, latihan.db, guru-tugas.db, dan berkas akun (auth)."""
    return _keadaan(berkas_tugas) + (_hash(auth.BERKAS_SANDI),)


def _jumlah_anak_daftar(isi: str) -> int:
    return len(POLA_HREF_ORDER.findall(isi))


def _anak_keluarga_hapus(server, tugas) -> dict:
    """Anak milik keluarga yang nanti dihapus lewat `family_deletion`: akun keluarga (guru), akun murid, dan
    order Mini guru A. Order-nya tidak ikut tersentuh penghapusan (kelas_order tidak disentuh), jadi `anak_tertaut`
    masih mengembalikan siswa_id; hanya `anak_masih_ada` yang menolaknya."""
    auth.tambah_akun(KELUARGA_HAPUS, SANDI_KELUARGA_HAPUS, "guru")
    siswa = tambah_anak(server, "Anak Sintetis Hapus", KELUARGA_HAPUS, None)
    akun = _akun_anak("anak-hapus", siswa)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = _tempatkan_mini(kon, tugas["kid_a"], siswa, akun, n=5)
        kon.commit()
    return {"siswa": siswa, "akun": akun, "order": order}


def _tagihan_belum_lunas(siswa_id: int, akun: str) -> str:
    """Order Mini yang belum dibayar, ditempatkan lewat SQL (melewati domain) supaya hanya status lunas yang beda."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        tagihan = kelas_kit.tagih(kon, siswa_id, "mini", akun=akun)
        kid = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Lunas", lokasi=LOKASI_MEET, guru_id=id_akun(AKUN_A),
                               kuota=5, tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                    "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                    (tagihan.order_id, kid, kelas_kit.KINI, kelas_kit.KINI, ADMIN_JADWAL, ADMIN_JADWAL))
        kon.commit()
    return tagihan.order_id


# --- gerbang rilis ------------------------------------------------------------------------------

@pytest.mark.parametrize("jalur_sufiks", ["", "/kor_" + "0" * 32])
def test_gerbang_mati_get_404_identik_rute_tak_dikenal(server, tugas, monkeypatch, jalur_sufiks):
    monkeypatch.setattr(gta, "GURU_TUGAS_AKTIF", False)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = server.minta(RUTE + jalur_sufiks, auth=AKUN_A)

    assert (kode, isi) == (acuan[0], acuan[1])


def test_gerbang_mati_anak_tertaut_pun_404_identik(server, tugas, monkeypatch):
    monkeypatch.setattr(gta, "GURU_TUGAS_AKTIF", False)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi = _minta_anak(server, tugas["ord_alfa"])[:2]

    assert (kode, isi) == (acuan[0], acuan[1])


def test_gerbang_mati_post_404_identik_tanpa_efek_samping(server, tugas, berkas_tugas, monkeypatch):
    monkeypatch.setattr(gta, "GURU_TUGAS_AKTIF", False)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    sebelum = _keadaan(berkas_tugas)

    kode, isi, _ = _kirim(server, tugas["ord_alfa"], {"token": "x", "topik": _topik(), "tenggat": ""})

    assert (kode, isi) == (acuan[0], acuan[1])
    assert _keadaan(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []


def test_admin_mendapat_404_dan_murid_401_pada_rute_tugas(server, tugas):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_ADMIN)

    kode_admin, isi_admin, _ = server.minta(RUTE, auth=AKUN_ADMIN)
    kode_murid, _isi, _ = server.minta(_jalur(tugas["ord_alfa"]), auth=AKUN_MURID)

    assert (kode_admin, isi_admin) == (acuan[0], acuan[1])
    assert kode_murid == 401


@pytest.mark.parametrize("sufiks", ["kor_xyz", "kor_" + "G" * 32, "kor_" + "0" * 31, "klp_" + "0" * 32, "x/y"])
def test_id_cacat_atau_tak_ada_404_identik(server, tugas, sufiks):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = server.minta(f"{RUTE}/{sufiks}", auth=AKUN_A)

    assert (kode, isi) == (acuan[0], acuan[1])


# --- kepemilikan: hanya anak tertaut ke guru sesi ----------------------------------------------

def test_guru_b_tidak_melihat_anak_guru_a_404_identik(server, tugas):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)

    kode, isi, _ = _minta_anak(server, tugas["ord_alfa"], akun=AKUN_B)

    assert (kode, isi) == (acuan[0], acuan[1])


def test_guru_b_tidak_bisa_menulis_anak_guru_a_tanpa_efek_samping(server, tugas, berkas_tugas):
    token_b = _token_form(server, tugas["ord_gamma"], akun=AKUN_B)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    sebelum = _keadaan(berkas_tugas)

    kode, isi, _ = _kirim(server, tugas["ord_alfa"],
                          {"token": token_b, "topik": _topik(), "tenggat": ""}, akun=AKUN_B)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert _keadaan(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []


def test_siswa_id_di_form_diabaikan(server, tugas):
    data = _form(server, tugas["ord_alfa"], siswa_id=str(tugas["gamma"]))

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], data)

    assert kode == 303
    assert _sesi_anak(tugas["gamma"]) == []
    assert len(_sesi_anak(tugas["alfa"])) == 1


@pytest.mark.parametrize("nama", ["alfa", "beta"])
def test_sukses_satu_sesi_dan_satu_tugas_untuk_mini_dan_privat(server, tugas, berkas_tugas, nama):
    order, siswa = tugas["ord_" + nama], tugas[nama]
    topik = _topik()

    kode, _isi, tajuk = _kirim(server, order, _form(server, order, topik=topik, tenggat=TENGGAT_TANGGAL))

    assert kode == 303
    assert _lokasi(tajuk) == _jalur(order)
    sesi = _sesi_anak(siswa)
    assert len(sesi) == 1
    tugas_siswa = gtd.daftar_siswa(siswa)
    assert len(tugas_siswa) == 1
    assert tugas_siswa[0]["sesi_id"] == sesi[0]
    assert tugas_siswa[0]["guru_akun"] == id_akun(AKUN_A)
    assert (tugas_siswa[0]["topik"], tugas_siswa[0]["tenggat"]) == (topik, TENGGAT_TANGGAL)
    assert tugas_siswa[0]["dibuat"] == KINI_AWAL


def test_sukses_tidak_mengubah_pemilik_anak_dan_gerbang_lama(server, tugas):
    _buat_tugas(server, tugas, tugas["ord_alfa"], tugas["alfa"])

    pemilik = _baca("SELECT pemilik FROM siswa WHERE id=?", (tugas["alfa"],))[0][0]
    kon = sqlite3.connect(str(database.BAWAAN))
    try:
        milik_guru = database.siswa_milik(kon, tugas["alfa"], "guru")
    finally:
        kon.close()
    kode_sesi_baru, _isi, _ = minta_mentah(server, f"/sesi-baru/{tugas['alfa']}", AKUN_A, {"topik": _topik()})

    assert pemilik == KOORDINATOR
    assert milik_guru is False
    assert kode_sesi_baru == 404
    assert len(_sesi_anak(tugas["alfa"])) == 1


def test_sesi_buatan_guru_tercatat_untuk_siswa_yang_benar(server, tugas):
    sesi = _buat_tugas(server, tugas, tugas["ord_beta"], tugas["beta"])

    siswa_sesi = _baca("SELECT siswa_id FROM sesi WHERE id=?", (sesi,))[0][0]
    assert siswa_sesi == tugas["beta"]
    assert _sesi_anak(tugas["gamma"]) == []


# --- order tidak tertaut: 404 tanpa tulis -------------------------------------------------------

def test_order_dilepas_404_tanpa_tulis(server, tugas, berkas_tugas):
    _lepas_penempatan(tugas["ord_alfa"])
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    sebelum = _keadaan(berkas_tugas)

    kode_get, isi_get, _ = _minta_anak(server, tugas["ord_alfa"])
    kode_post, isi_post, _ = _kirim(server, tugas["ord_alfa"], {"token": "x", "topik": _topik(), "tenggat": ""})

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert _keadaan(berkas_tugas) == sebelum


def test_akses_berakhir_404_dan_tidak_bisa_diberi_tugas_baru(server, tugas, jam, berkas_tugas):
    assert _minta_anak(server, tugas["ord_alfa"])[0] == 200
    jam.nilai = KINI_AKSES_LEWAT
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    sebelum = _keadaan(berkas_tugas)

    kode_get, isi_get, _ = _minta_anak(server, tugas["ord_alfa"])
    kode_post, isi_post, _ = _kirim(server, tugas["ord_alfa"], {"token": "x", "topik": _topik(), "tenggat": ""})

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert _keadaan(berkas_tugas) == sebelum


def test_order_belum_lunas_404(server, tugas):
    epsilon = tambah_anak(server, "Anak Sintetis Epsilon", KOORDINATOR, None)
    order = _tagihan_belum_lunas(epsilon, _akun_anak("anak-epsilon", epsilon))
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = _minta_anak(server, order)

    assert (kode, isi) == (acuan[0], acuan[1])


# --- validasi form ------------------------------------------------------------------------------

@pytest.mark.parametrize("topik", ["tidak-ada", "campuran", "", TOPIK_BUKAN_P3])
def test_topik_di_luar_daftar_atau_tingkat_anak_400_tanpa_tulis(server, tugas, berkas_tugas, topik):
    sebelum = _keadaan(berkas_tugas)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], topik=topik))

    assert kode == 400
    assert _keadaan(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []


@pytest.mark.parametrize("tenggat", ["2026-11-22", "23-11-2026", "2027-02-01", "2026-02-30", "2026/11/25"])
def test_tenggat_lampau_format_salah_atau_terlalu_jauh_400_tanpa_tulis(server, tugas, berkas_tugas, tenggat):
    sebelum = _keadaan(berkas_tugas)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat=tenggat))

    assert kode == 400
    assert _keadaan(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []


def test_tenggat_hari_ini_dan_tenggat_kosong_diterima(server, tugas):
    kode_hari_ini, _i, _t = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat="2026-11-23"))
    kode_kosong, _i, _t = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat=""))

    assert (kode_hari_ini, kode_kosong) == (303, 303)


def test_tanggal_tenggat_mengikuti_hari_wib(server, tugas, jam):
    assert gth.hari_ini_wib("2026-11-23T16:59:59") == date(2026, 11, 23)
    assert gth.hari_ini_wib("2026-11-23T17:00:00") == date(2026, 11, 24)
    jam.nilai = "2026-11-23T17:30:00"   # 00.30 WIB 24 Nov: tenggat 23 Nov sudah lampau

    kode, _isi, _t = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat="2026-11-23"))

    assert kode == 400


@pytest.mark.parametrize("jenis", ["salah", "aksi_lain", "domain_lain"])
def test_token_tak_sah_403_tanpa_tulis(server, tugas, berkas_tugas, jenis):
    principal = _principal(AKUN_A)
    token = {
        "salah": "x",
        "aksi_lain": form_token.buat_token(principal, None, domain=gth.DOMAIN_TOKEN_TUGAS,
                                           aksi=f"tugas:{tugas['ord_beta']}"),
        "domain_lain": form_token.buat_token(principal, None, domain=b"guru-pertemuan-form-v1:",
                                             aksi=f"tugas:{tugas['ord_alfa']}"),
    }[jenis]
    sebelum = _keadaan(berkas_tugas)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], {"token": token, "topik": _topik(), "tenggat": ""})

    assert kode == 403
    assert _keadaan(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []


# --- duplikat, batas, dan laju ------------------------------------------------------------------

def test_duplikat_dalam_60_detik_409_tanpa_sesi_kedua(server, tugas):
    data = _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL)
    assert _kirim(server, tugas["ord_alfa"], data)[0] == 303

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], data)

    assert kode == 409
    assert len(_sesi_anak(tugas["alfa"])) == 1
    assert len(gtd.daftar_siswa(tugas["alfa"])) == 1


def test_setelah_61_detik_tugas_serupa_boleh_dibuat(server, tugas, jam):
    data = _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL)
    _kirim(server, tugas["ord_alfa"], data)
    jam.nilai = _geser(KINI_AWAL, gta.JENDELA_DUPLIKAT_DETIK + 1)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], data)

    assert kode == 303
    assert len(_sesi_anak(tugas["alfa"])) == 2


def test_batas_tugas_aktif_409_pada_tugas_keenam(server, tugas, jam):
    for indeks in range(gta.BATAS_TUGAS_AKTIF):
        jam.nilai = _geser(KINI_AWAL, indeks * 120)
        assert _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL))[0] == 303
    jam.nilai = _geser(KINI_AWAL, gta.BATAS_TUGAS_AKTIF * 120)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL))

    assert kode == 409
    assert len(_sesi_anak(tugas["alfa"])) == gta.BATAS_TUGAS_AKTIF


def test_tugas_yang_sudah_selesai_tidak_dihitung_sebagai_aktif(server, tugas, jam):
    sesi_tugas = []
    for indeks in range(gta.BATAS_TUGAS_AKTIF):
        jam.nilai = _geser(KINI_AWAL, indeks * 120)
        sesi_tugas.append(_buat_tugas(server, tugas, tugas["ord_alfa"], tugas["alfa"], tenggat=TENGGAT_TANGGAL))
    _tandai_selesai(sesi_tugas[0])
    jam.nilai = _geser(KINI_AWAL, gta.BATAS_TUGAS_AKTIF * 120)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL))

    assert kode == 303


def test_laju_429_sebelum_isian_diproses(server, tugas, monkeypatch):
    monkeypatch.setattr(learning_cycle_http, "_BATAS_PER_MENIT", 2)
    data = _form(server, tugas["ord_alfa"], tenggat=TENGGAT_TANGGAL)
    _kirim(server, tugas["ord_alfa"], data)
    _kirim(server, tugas["ord_alfa"], data)

    kode, isi, _ = _kirim(server, tugas["ord_alfa"], data)

    assert kode == 429
    assert "Terlalu banyak permintaan" in isi


# --- pembuatan sesi dan catat: atomik ----------------------------------------------------------

def _sesi_aktif(siswa_id) -> list:
    return [baris[0] for baris in _baca("SELECT id FROM sesi WHERE siswa_id=? AND dibatalkan IS NULL", (siswa_id,))]


def test_gagal_catat_membatalkan_sesi_dan_tidak_menyisakan_tugas(server, tugas, berkas_tugas, monkeypatch):
    """`buat_sesi` sudah commit sendiri, jadi sesinya dibatalkan (ada, tidak aktif), bukan di-rollback."""
    def _gagal(*_args, **_kwargs):
        raise gtd.GalatTugas("Tugas guru tidak bisa ditulis.")
    monkeypatch.setattr(gtd, "catat", _gagal)

    kode, isi, _ = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"]))

    assert kode == 500
    assert "Tugas belum bisa dibuat" in isi
    assert "tidak bisa ditulis" not in isi   # tanpa detail galat internal
    assert _sesi_aktif(tugas["alfa"]) == []
    sesi = _sesi_anak(tugas["alfa"])
    assert len(sesi) == 1
    assert _baca("SELECT COUNT(*) FROM kejadian_belajar WHERE sesi_id=? AND jenis='sesi_dibatalkan'",
                 (sesi[0],))[0][0] == 1
    assert gtd.daftar_siswa(tugas["alfa"]) == []


# --- halaman daftar anak dan halaman anak ------------------------------------------------------

def test_daftar_menampilkan_nama_login_dan_tanpa_id_mentah(server, tugas):
    kode, isi, _ = server.minta(RUTE, auth=AKUN_A)

    assert kode == 200
    assert "anak-alfa" in isi and "anak-beta" in isi
    assert "anak-gamma" not in isi and "anak-delta" not in isi
    sisa = POLA_HREF_ORDER.sub("", isi)
    assert "kor_" not in sisa and "siswa_id" not in isi and "akun_" not in isi
    assert len(POLA_HREF_ORDER.findall(isi)) == 2


def test_daftar_kosong_bila_guru_tanpa_anak_tertaut(server, tugas, guru_kosong):
    kode, isi, _ = server.minta(RUTE, auth=guru_kosong)

    assert kode == 200
    assert POLA_HREF_ORDER.search(isi) is None


@pytest.fixture()
def guru_kosong(server):
    """Guru sintetis tanpa order apa pun: daftar anaknya harus kosong, bukan galat."""
    auth.tambah_akun("guru-kosong", SANDI_GURU_KOSONG, "guru")
    return ("guru-kosong", SANDI_GURU_KOSONG)


def test_halaman_anak_memuat_form_topik_dan_tenggat(server, tugas):
    kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])

    assert kode == 200
    assert 'name="topik"' in isi and 'name="tenggat"' in isi and 'type="date"' in isi
    assert 'name="token"' in isi and "Beri tugas" in isi
    assert f'value="{TOPIK_P3}"' in isi
    assert f'value="{TOPIK_BUKAN_P3}"' not in isi   # topik di luar tingkat anak tidak ditawarkan
    assert "siswa_id" not in isi and "akun_" not in isi


def test_topik_tak_terbaca_halaman_tanpa_form_dan_tanpa_detail(server, tugas, monkeypatch):
    monkeypatch.setenv("OSN_MATERI_DASAR", "2")

    kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])

    assert kode == 200
    assert 'name="topik"' not in isi and "Beri tugas" not in isi
    assert f'action="{RUTE}/{tugas["ord_alfa"]}"' not in isi
    assert "OSN_MATERI_DASAR" not in isi


def test_topik_tak_terbaca_saat_kirim_503_tanpa_tulis(server, tugas, berkas_tugas, monkeypatch):
    token = _token_form(server, tugas["ord_alfa"])
    monkeypatch.setenv("OSN_MATERI_DASAR", "2")
    sebelum = _keadaan(berkas_tugas)

    kode, _isi, _ = _kirim(server, tugas["ord_alfa"], {"token": token, "topik": "tidak-ada", "tenggat": ""})

    assert kode == 503
    assert _keadaan(berkas_tugas) == sebelum


def test_daftar_tugas_menampilkan_skor_hanya_bila_selesai(server, tugas, jam):
    selesai = _buat_tugas(server, tugas, tugas["ord_alfa"], tugas["alfa"], tenggat=TENGGAT_TANGGAL)
    jam.nilai = _geser(KINI_AWAL, 120)
    _buat_tugas(server, tugas, tugas["ord_alfa"], tugas["alfa"], tenggat=TENGGAT_TANGGAL)
    _tandai_selesai(selesai)
    total = _baca("SELECT COUNT(*) FROM sesi_soal WHERE sesi_id=?", (selesai,))[0][0]

    kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])

    assert kode == 200
    assert isi.count("Benar ") == 1
    assert f"Benar 0 dari {total}" in isi
    assert "Selesai" in isi and "Belum dikerjakan" in isi


def test_halaman_tugas_tanpa_kunci_malrule_atau_diagnosis(server, tugas):
    _buat_tugas(server, tugas, tugas["ord_alfa"], tugas["alfa"], tenggat=TENGGAT_TANGGAL)

    _kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])
    badan = isi[isi.index("<main"):isi.index("</main>")].lower()   # CSS kerangka bersama tidak dihitung

    for kata in KATA_RAHASIA:
        assert kata not in badan


def test_tenggat_lewat_diberi_label_dan_yatim_tidak_tampil(server, tugas):
    sesi = _sesi_langsung(tugas["alfa"])
    gtd.catat(sesi, tugas["alfa"], id_akun(AKUN_A), _topik(), "2026-11-20", KINI_AWAL)
    gtd.catat(999_999, tugas["alfa"], id_akun(AKUN_A), _topik(), "2026-12-01", KINI_AWAL)

    _kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])

    assert "Lewat tenggat" in isi
    assert "20 November 2026" in isi
    assert "1 Desember 2026" not in isi


def test_daftar_tugas_paling_banyak_dua_puluh_terbaru(server, tugas):
    for _ in range(21):
        gtd.catat(_sesi_langsung(tugas["alfa"]), tugas["alfa"], id_akun(AKUN_A), _topik(), None, KINI_AWAL)

    _kode, isi, _ = _minta_anak(server, tugas["ord_alfa"])

    assert isi.count('class="tugas-baris-st"') == 20


# --- tautan di halaman jadwal guru (satu, hanya bila gerbang menyala) --------------------------

def test_jadwal_tanpa_flag_identik_dan_tanpa_tautan_tugas():
    ident = (AKUN_A[0], "guru")

    polos = halaman_jadwal.halaman_jadwal(ident, [])

    assert polos == halaman_jadwal.halaman_jadwal(ident, [], (), tugas_aktif=False)
    assert b"/guru/tugas" not in polos


def test_jadwal_dengan_flag_satu_tautan_tugas():
    ident = (AKUN_A[0], "guru")

    isi = halaman_jadwal.halaman_jadwal(ident, [], tugas_aktif=True)

    assert isi.count(b'href="/guru/tugas"') == 1


# --- anak yang keluarganya sudah dihapus (invarian F 3b): anak_masih_ada gagal tertutup -----------

def test_anak_terhapus_get_dan_post_404_identik_tanpa_efek_samping(server, tugas, berkas_tugas):
    anak = _anak_keluarga_hapus(server, tugas)
    token = _token_form(server, anak["order"])   # token dibuat saat anak masih ada
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    hapus_keluarga_sintetis(KELUARGA_HAPUS)
    sebelum = _keadaan_lengkap(berkas_tugas)

    kode_get, isi_get, _ = _minta_anak(server, anak["order"])
    kode_post, isi_post, _ = _kirim(server, anak["order"], {"token": token, "topik": _topik(), "tenggat": ""})

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert _keadaan_lengkap(berkas_tugas) == sebelum
    assert _sesi_anak(anak["siswa"]) == []


def test_daftar_tidak_memuat_anak_terhapus_dan_anak_lain_tetap(server, tugas):
    _anak_keluarga_hapus(server, tugas)
    _kode, isi_sebelum, _ = server.minta(RUTE, auth=AKUN_A)
    assert "anak-hapus" in isi_sebelum and _jumlah_anak_daftar(isi_sebelum) == 3

    hapus_keluarga_sintetis(KELUARGA_HAPUS)
    kode, isi, _ = server.minta(RUTE, auth=AKUN_A)

    assert kode == 200
    assert "anak-hapus" not in isi
    assert _jumlah_anak_daftar(isi) == 2
    assert "anak-alfa" in isi and "anak-beta" in isi


def test_anak_yang_tidak_dihapus_tetap_normal_setelah_keluarga_lain_dihapus(server, tugas):
    _anak_keluarga_hapus(server, tugas)
    hapus_keluarga_sintetis(KELUARGA_HAPUS)

    assert _minta_anak(server, tugas["ord_alfa"])[0] == 200
    kode, _isi, _tajuk = _kirim(server, tugas["ord_alfa"], _form(server, tugas["ord_alfa"]))

    assert kode == 303
    assert len(_sesi_anak(tugas["alfa"])) == 1


def test_galat_baca_kepastian_anak_404_fail_closed(server, tugas, berkas_tugas, monkeypatch):
    monkeypatch.setattr(tautan_anak, "status_anak", lambda *_a, **_k: tautan_anak.ANAK_TIDAK_DIKETAHUI)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    sebelum = _keadaan_lengkap(berkas_tugas)

    kode_get, isi_get, _ = _minta_anak(server, tugas["ord_alfa"])
    kode_post, isi_post, _ = _kirim(server, tugas["ord_alfa"], {"token": "x", "topik": _topik(), "tenggat": ""})
    _kode, isi_daftar, _ = server.minta(RUTE, auth=AKUN_A)

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert _jumlah_anak_daftar(isi_daftar) == 0
    assert _keadaan_lengkap(berkas_tugas) == sebelum


def test_kepemilikan_tetap_404_walau_kepastian_anak_selalu_ya(server, tugas, berkas_tugas, monkeypatch):
    """Guard kepemilikan (tertaut) diuji sendiri: anak_masih_ada dibuat selalu True, guru B tetap 404 tanpa tulis."""
    monkeypatch.setattr(tautan_anak, "anak_masih_ada", lambda *_a, **_k: True)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    sebelum = _keadaan_lengkap(berkas_tugas)

    kode_get, isi_get, _ = _minta_anak(server, tugas["ord_alfa"], akun=AKUN_B)
    kode_post, isi_post, _ = _kirim(server, tugas["ord_alfa"],
                                    {"token": "x", "topik": _topik(), "tenggat": ""}, akun=AKUN_B)

    assert (kode_get, isi_get) == (acuan[0], acuan[1])
    assert (kode_post, isi_post) == (acuan[0], acuan[1])
    assert _keadaan_lengkap(berkas_tugas) == sebelum
    assert _sesi_anak(tugas["alfa"]) == []
