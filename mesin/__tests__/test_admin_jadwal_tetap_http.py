"""Tes HTTP koreksi admin atas jadwal tetap guru (3d, WP3): `/admin/jadwal/tetap` dan detail per guru.

Data sintetis: dua akun guru uji (AKUN_A, AKUN_B) dan pengelola uji. DB jadwal tetap di `tmp_path`. Gerbang dinyalakan
lewat monkeypatch pada `guru_jadwal_tetap_aturan` kecuali tes gerbang mati.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

import auth
import form_token
import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as tetap
import admin_jadwal_tetap_http as jt
import admin_jurnal_koreksi_http as kh
from admin_pesanan_kit import id_admin, login_admin, minta_admin
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah, server  # noqa: F401
from harian_kit import jam  # noqa: F401
import sessions

JALUR = "/admin/jadwal/tetap"
TAK_ADA = "/admin/tidak-ada"
WAKTU_KINI = "2026-11-27T05:00:00"
DIBUAT = "2026-11-20T03:00:00"
BLOK_SENIN = "1@480-600"  # Senin 08.00-10.00 WIB
BLOK_SELASA = "2@600-720"
BLOK_RABU = "3@900-1020"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
POLA_FORM = re.compile(r'<form method="post" action="([^"]+)"[^>]*>(.*?)</form>', re.S)
POLA_HIDDEN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)">')
POLA_SELECT = re.compile(r'<select name="(h[1-7][ab]_[ms])"[^>]*>(.*?)</select>', re.S)
POLA_OPSI = re.compile(r'<option value="([^"]*)"( selected)?')
POLA_MENTAH = re.compile(r"kor_|klp_|siswa_id|order_id")
TEKS_TERSIMPAN = "Jadwal tetap tersimpan."
TEKS_BELUM_ADA = "Belum ada"
TEKS_MENUNGGU = "Usulan menunggu"
TEKS_KONFLIK = "Usulan sudah berubah, muat ulang halaman"
TEKS_TANPA_JAM = "Tanpa jam tetap"
DOMAIN_JURNAL = kh.DOMAIN_TOKEN


# --- fixture ------------------------------------------------------------------------------------

@pytest.fixture()
def berkas_tetap(tmp_path, monkeypatch):
    """DB jadwal tetap sementara; belum ada sampai tulis pertama."""
    berkas = tmp_path / "guru-jadwal-tetap.db"
    monkeypatch.setenv(tetap.ENV_DB, str(berkas))
    return berkas


@pytest.fixture()
def gerbang_menyala(monkeypatch):
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", True)


@pytest.fixture()
def waktu(jam):
    jam.nilai = WAKTU_KINI
    return jam


@pytest.fixture()
def sesi_admin(server, berkas_tetap, waktu):
    """Cookie pengelola tanpa gerbang: dipakai tes gerbang mati."""
    return login_admin(server)


@pytest.fixture()
def cookie(sesi_admin, gerbang_menyala):
    """Cookie pengelola dengan gerbang menyala."""
    return sesi_admin


# --- util ---------------------------------------------------------------------------------------

def _guru_a() -> str:
    return id_akun(AKUN_A)


def _guru_b() -> str:
    return id_akun(AKUN_B)


def _jalur_guru(guru: str) -> str:
    return f"{JALUR}/{guru}"


def _hash(path):
    """Hash isi berkas, atau None bila berkas belum ada (tanpa membuatnya)."""
    berkas = Path(path)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _keadaan(berkas_tetap: Path):
    return _hash(berkas_tetap)


def _principal_cookie(cookie_sesi):
    principal = sessions.ambil_principal(cookie_sesi, path=sessions.BERKAS_SESI, path_akun=auth.BERKAS_SANDI)
    assert principal is not None
    return principal


def _token(cookie_sesi, aksi: str) -> str:
    """Token sah untuk pengelola sesi `cookie_sesi` dan aksi itu, dibuat dari modul token."""
    return form_token.buat_token(_principal_cookie(cookie_sesi), cookie_sesi, domain=jt.DOMAIN_TOKEN, aksi=aksi)


def _aksi_tetapkan(guru: str) -> str:
    return f"tetapkan:{guru}"


def _aksi_putus(usulan_id: int, putusan: str) -> str:
    return f"putus:{usulan_id}:{putusan}"


def _usul(guru: str, blok: str) -> int:
    """Usulan guru lewat API dasar (bukan HTTP guru). Mengembalikan id usulan baru."""
    tetap.usul(guru_akun=guru, blok=blok, dibuat=DIBUAT)
    return tetap.menunggu(guru)["usulan_id"]


def _halaman(server, jalur: str, cookie_sesi: str) -> str:
    kode, isi, _ = minta_admin(server, jalur, cookie_sesi)
    assert kode == 200, kode
    return isi


def _form_putus(isi: str, usulan_id: int, putusan: str) -> dict:
    """Isian tersembunyi form Setujui/Tolak untuk usulan dan putusan itu, seperti peramban mengirimnya."""
    for _aksi, badan in POLA_FORM.findall(isi):
        tersembunyi = dict(POLA_HIDDEN.findall(badan))
        if tersembunyi.get("aksi") == "putus" and tersembunyi.get("usulan_id") == str(usulan_id) \
                and tersembunyi.get("putusan") == putusan:
            return tersembunyi
    raise AssertionError(f"form putus {usulan_id}/{putusan} tidak ditemukan")


def _isi_tetapkan(isi: str) -> dict:
    """Isian form Tetapkan langsung seperti peramban: token, aksi, dan 28 select (opsi terpilih, atau opsi pertama)."""
    for _aksi, badan in POLA_FORM.findall(isi):
        tersembunyi = dict(POLA_HIDDEN.findall(badan))
        if tersembunyi.get("aksi") != "tetapkan":
            continue
        data = dict(tersembunyi)
        for nama, opsi in POLA_SELECT.findall(badan):
            pilihan = POLA_OPSI.findall(opsi)
            terpilih = [nilai for nilai, pilih in pilihan if pilih] or [pilihan[0][0]]
            data[nama] = terpilih[0]
        return data
    raise AssertionError("form tetapkan tidak ditemukan")


def _kirim_tetapkan(server, cookie_sesi: str, guru: str, blok_isi: dict, token: str = None):
    """POST tetapkan dengan 28 field blok; `blok_isi` menimpa nilai default kosong."""
    data = {"token": token if token is not None else _token(cookie_sesi, _aksi_tetapkan(guru)),
            "aksi": "tetapkan"}
    data.update({nama: "" for nama in aturan.KUNCI_FORM})
    data.update(blok_isi)
    return minta_admin(server, _jalur_guru(guru), cookie_sesi, data)


def _kirim_putus(server, cookie_sesi: str, guru: str, usulan_id: int, putusan: str, token: str = None):
    data = {"token": token if token is not None else _token(cookie_sesi, _aksi_putus(usulan_id, putusan)),
            "aksi": "putus", "usulan_id": str(usulan_id), "putusan": putusan}
    return minta_admin(server, _jalur_guru(guru), cookie_sesi, data)


def _blok_form(blok_teks: str) -> dict:
    """Isian 28 field untuk blok teks kanonik (mis. "1@480-600;3@900-1020")."""
    isi = {}
    dihitung = {}
    for potongan in blok_teks.split(";"):
        hari, rentang = potongan.split("@")
        mulai, selesai = rentang.split("-")
        slot = "a" if dihitung.get(hari, 0) == 0 else "b"
        dihitung[hari] = dihitung.get(hari, 0) + 1
        isi[f"h{hari}{slot}_m"] = mulai
        isi[f"h{hari}{slot}_s"] = selesai
    return isi


# --- akses: 404 identik dan tanpa efek samping --------------------------------------------------

AKUN_NON_ADMIN = [
    pytest.param(None, id="anonim"),
    pytest.param(AKUN_A, id="guru_pemilik"),
    pytest.param(AKUN_B, id="guru_lain"),
    pytest.param(AKUN_MURID, id="murid"),
]


@pytest.mark.parametrize("akun", AKUN_NON_ADMIN)
def test_get_non_admin_404_identik_dengan_rute_tak_dikenal(server, berkas_tetap, gerbang_menyala, akun):
    acuan = minta_mentah(server, TAK_ADA, akun)
    for jalur in (JALUR, _jalur_guru(_guru_a())):
        kode, isi, _ = minta_mentah(server, jalur, akun)
        assert (kode, isi) == acuan[:2], jalur
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("akun", AKUN_NON_ADMIN)
def test_post_non_admin_404_identik_dan_tanpa_tulis(server, berkas_tetap, gerbang_menyala, akun):
    data = {"token": "x", "aksi": "tetapkan"}
    acuan = minta_mentah(server, TAK_ADA, akun, data)

    kode, isi, _ = minta_mentah(server, _jalur_guru(_guru_a()), akun, data)

    assert (kode, isi) == acuan[:2]
    assert not berkas_tetap.exists()


def test_mode_lokal_tanpa_principal_404_identik(server, berkas_tetap, gerbang_menyala, monkeypatch):
    acuan = minta_mentah(server, TAK_ADA)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)

    kode, isi, _ = minta_mentah(server, JALUR)

    assert (kode, isi) == acuan[:2]


def test_mode_lokal_post_404_identik_tanpa_tulis(server, berkas_tetap, gerbang_menyala, monkeypatch):
    data = {"token": "x", "aksi": "tetapkan"}
    acuan = minta_mentah(server, TAK_ADA, None, data)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)

    kode, isi, _ = minta_mentah(server, _jalur_guru(_guru_a()), None, data)

    assert (kode, isi) == acuan[:2]
    assert not berkas_tetap.exists()


def test_gerbang_mati_404_identik_untuk_admin_dan_tanpa_berkas(server, sesi_admin, berkas_tetap):
    acuan = minta_admin(server, TAK_ADA, sesi_admin)[:2]
    data = {"token": _token(sesi_admin, _aksi_tetapkan(_guru_a())), "aksi": "tetapkan"}

    for jalur in (JALUR, _jalur_guru(_guru_a())):
        assert minta_admin(server, jalur, sesi_admin)[:2] == acuan, jalur
    assert minta_admin(server, _jalur_guru(_guru_a()), sesi_admin, data)[:2] == acuan
    assert not berkas_tetap.exists()


def test_admin_basic_get_hanya_baca_tanpa_token(server, cookie, berkas_tetap):
    kode, isi, _ = minta_mentah(server, _jalur_guru(_guru_a()), AKUN_ADMIN)

    assert kode == 200
    assert POLA_TOKEN.search(isi) is None


def test_admin_basic_post_403_walau_token_sah_tanpa_tulis(server, berkas_tetap, gerbang_menyala, waktu):
    token = form_token.buat_token(_principal_basic(), None, domain=jt.DOMAIN_TOKEN,
                                  aksi=_aksi_tetapkan(_guru_a()))
    data = {"token": token, "aksi": "tetapkan"}
    data.update({nama: "" for nama in aturan.KUNCI_FORM})
    data.update(_blok_form(BLOK_SENIN))

    kode, _isi, _ = minta_mentah(server, _jalur_guru(_guru_a()), AKUN_ADMIN, data)

    assert kode == 403
    assert not berkas_tetap.exists()


def _principal_basic():
    principal = sessions.principal_basic(*AKUN_ADMIN)
    assert principal is not None
    return principal


@pytest.mark.parametrize("variasi", ["kosong", "domain_lain", "aksi_lain", "target_lain", "putus_untuk_tetapkan"])
def test_token_salah_403_tanpa_tulis(server, cookie, berkas_tetap, variasi):
    token = {
        "kosong": "x",
        "domain_lain": form_token.buat_token(_principal_cookie(cookie), cookie, domain=DOMAIN_JURNAL,
                                             aksi=_aksi_tetapkan(_guru_a())),
        "aksi_lain": _token(cookie, _aksi_tetapkan(_guru_a()) + "x"),
        "target_lain": _token(cookie, _aksi_tetapkan(_guru_b())),
        "putus_untuk_tetapkan": _token(cookie, _aksi_putus(1, "setuju")),
    }[variasi]
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_SENIN), token=token)

    assert kode == 403
    assert _keadaan(berkas_tetap) == sebelum


@pytest.mark.parametrize("sufiks", ["ABC", "0" * 31, "0" * 33, "g" * 32, "sintetis"])
def test_guru_pola_cacat_404_identik(server, cookie, berkas_tetap, sufiks):
    acuan = minta_admin(server, TAK_ADA, cookie)[:2]
    jalur = f"{JALUR}/akun_{sufiks}"

    assert minta_admin(server, jalur, cookie)[:2] == acuan
    assert minta_admin(server, jalur, cookie, {"token": "x", "aksi": "tetapkan"})[:2] == acuan
    assert not berkas_tetap.exists()


def test_guru_tidak_di_peta_404_identik_termasuk_admin_dan_tanpa_tulis(server, cookie, berkas_tetap):
    acuan = minta_admin(server, TAK_ADA, cookie)[:2]
    bukan_guru = [id_admin(), "akun_" + "0" * 32]
    for guru in bukan_guru:
        token = _token(cookie, _aksi_tetapkan(guru))
        assert minta_admin(server, _jalur_guru(guru), cookie)[:2] == acuan, guru
        assert _kirim_tetapkan(server, cookie, guru, _blok_form(BLOK_SENIN), token=token)[:2] == acuan
    assert not berkas_tetap.exists()


# Garis miring akhir tidak dibahas di sini: router (`web.py`) memotongnya untuk semua rute, jadi `/tetap/` = daftar.
@pytest.mark.parametrize("jalur", [f"{JALUR}/{'a' * 32}/x", f"{JALUR}/{'a' * 32}/"])
def test_jalur_lain_di_bawah_prefix_404_identik(server, cookie, berkas_tetap, jalur):
    acuan = minta_admin(server, TAK_ADA, cookie)[:2]

    assert minta_admin(server, jalur, cookie)[:2] == acuan


def test_list_dengan_query_404_identik(server, cookie, berkas_tetap):
    acuan = minta_admin(server, TAK_ADA, cookie)[:2]

    assert minta_admin(server, JALUR + "?x=1", cookie)[:2] == acuan


def test_pesan_selain_tersimpan_404_identik(server, cookie, berkas_tetap):
    acuan = minta_admin(server, TAK_ADA, cookie)[:2]

    assert minta_admin(server, _jalur_guru(_guru_a()) + "?pesan=lain", cookie)[:2] == acuan


# --- GET: daftar dan detail -----------------------------------------------------------------------

def test_get_tidak_membuat_berkas_dan_daftar_menampilkan_nama_guru(server, cookie, berkas_tetap):
    isi = _halaman(server, JALUR, cookie)

    assert not berkas_tetap.exists()
    assert "guru-b" in isi and "guru" in isi
    assert TEKS_BELUM_ADA in isi


def test_daftar_menandai_usulan_menunggu_dan_jadwal_aktif(server, cookie, berkas_tetap):
    """Guru A hanya punya usulan menunggu (tampil Belum ada); guru B punya jadwal aktif dan usulan menunggu."""
    _usul(_guru_a(), BLOK_SENIN)
    tetap.tetapkan_admin(guru_akun=_guru_b(), blok=BLOK_RABU, admin_akun=id_admin(), dibuat=DIBUAT)
    _usul(_guru_b(), BLOK_SELASA)

    isi = _halaman(server, JALUR, cookie)

    assert isi.count(TEKS_MENUNGGU) == 2
    assert TEKS_BELUM_ADA in isi
    assert "Rabu 15.00" in isi


def test_detail_menampilkan_aktif_usulan_menunggu_dan_riwayat(server, cookie, berkas_tetap):
    tetap.tetapkan_admin(guru_akun=_guru_a(), blok=BLOK_SENIN, admin_akun=id_admin(), dibuat=DIBUAT)
    usulan = _usul(_guru_a(), BLOK_RABU)

    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)

    assert "Senin 08.00" in isi
    assert f'name="usulan_id" value="{usulan}"' in isi
    assert "Setujui" in isi and "Tolak" in isi
    assert "Usulan guru" in isi
    assert "Ketetapan admin" in isi


def test_detail_aktif_kosong_berbeda_dari_belum_ada(server, cookie, berkas_tetap):
    tetap.tetapkan_admin(guru_akun=_guru_a(), blok="", admin_akun=id_admin(), dibuat=DIBUAT)

    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)

    assert TEKS_TANPA_JAM in isi
    assert TEKS_BELUM_ADA not in isi


def test_detail_tanpa_jadwal_tampil_belum_ada(server, cookie, berkas_tetap):
    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)

    assert TEKS_BELUM_ADA in isi


def test_detail_tanpa_id_anak_order_kontak_atau_kor_klp(server, cookie, berkas_tetap):
    _usul(_guru_a(), BLOK_SENIN)
    tetap.tetapkan_admin(guru_akun=_guru_a(), blok=BLOK_RABU, admin_akun=id_admin(), dibuat=DIBUAT)

    for jalur in (JALUR, _jalur_guru(_guru_a())):
        isi = _halaman(server, jalur, cookie)
        assert POLA_MENTAH.search(isi) is None, jalur
        assert id_admin() not in isi, jalur


def test_pesan_tersimpan_menampilkan_kabar(server, cookie, berkas_tetap):
    isi = _halaman(server, _jalur_guru(_guru_a()) + "?pesan=tersimpan", cookie)

    assert TEKS_TERSIMPAN in isi


def test_form_tetapkan_memuat_28_select_dan_pra_pilih_dari_aktif(server, cookie, berkas_tetap):
    tetap.tetapkan_admin(guru_akun=_guru_a(), blok="1@480-600;3@900-1020", admin_akun=id_admin(), dibuat=DIBUAT)

    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)
    data = _isi_tetapkan(isi)

    assert {nama for nama in data if nama.startswith("h")} == set(aturan.KUNCI_FORM)
    assert data["h1a_m"] == "480" and data["h1a_s"] == "600"
    assert data["h3a_m"] == "900" and data["h3a_s"] == "1020"
    assert data["h2a_m"] == "" and data["h1b_m"] == ""


def test_get_riwayat_hanya_berisi_label_bukan_id_admin(server, cookie, berkas_tetap):
    tetap.tetapkan_admin(guru_akun=_guru_a(), blok=BLOK_SENIN, admin_akun=id_admin(), dibuat=DIBUAT)

    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)

    assert "Ketetapan admin" in isi
    assert id_admin() not in isi


def test_get_galat_baca_menjadi_503(server, cookie, berkas_tetap, monkeypatch):
    def gagal(*_args, **_kwargs):
        raise tetap.GalatTetap(tetap.KIND_UMUM, "tidak bisa dibaca")

    monkeypatch.setattr(tetap, "aktif", gagal)

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie)

    assert kode == 503


# --- POST: tetapkan -------------------------------------------------------------------------------

def test_tetapkan_menulis_usulan_admin_dan_membuatnya_aktif(server, cookie, berkas_tetap):
    kode, _isi, tajuk = _kirim_tetapkan(server, cookie, _guru_a(), _blok_form("1@480-600;3@900-1020"))

    assert kode == 303
    assert tajuk["Location"] == _jalur_guru(_guru_a()) + "?pesan=tersimpan"
    aktif = tetap.aktif(_guru_a())
    assert aktif["blok"] == "1@480-600;3@900-1020"
    assert aktif["asal"] == "admin"
    assert aktif["oleh"] == id_admin()
    riwayat = tetap.riwayat(_guru_a())
    assert riwayat[0]["putusan"] == "setuju"
    assert riwayat[0]["diputus_oleh"] == id_admin()


def test_tetapkan_menggantikan_usulan_menunggu(server, cookie, berkas_tetap):
    _usul(_guru_a(), BLOK_SENIN)

    _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_RABU))

    assert tetap.menunggu(_guru_a()) is None
    assert tetap.aktif(_guru_a())["blok"] == BLOK_RABU


def test_tetapkan_identik_dengan_aktif_303_tanpa_tulis(server, cookie, berkas_tetap):
    _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_SENIN))
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, tajuk = _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_SENIN))

    assert kode == 303
    assert tajuk["Location"].endswith("?pesan=tersimpan")
    assert _keadaan(berkas_tetap) == sebelum


def test_tetapkan_nol_blok_mengosongkan_jadwal_aktif(server, cookie, berkas_tetap):
    _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_SENIN))

    kode, _isi, _ = _kirim_tetapkan(server, cookie, _guru_a(), {})

    assert kode == 303
    assert tetap.aktif(_guru_a())["blok"] == ""


def test_e2e_token_dan_isian_dari_halaman_membuat_jadwal_aktif(server, cookie, berkas_tetap):
    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)
    data = _isi_tetapkan(isi)
    data["h2a_m"], data["h2a_s"] = "600", "720"

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 303
    assert tetap.aktif(_guru_a())["blok"] == BLOK_SELASA


@pytest.mark.parametrize("dibuang", [["h1a_s"], []], ids=["tukar_satu_blok", "melebihi_batas_field"])
def test_tetapkan_field_berlebih_400_tanpa_tulis(server, cookie, berkas_tetap, dibuang):
    """`tukar_satu_blok` (30 field, di bawah batas parser) menguji cek himpunan field; `melebihi_batas_field` (31)
    ditolak lebih dulu oleh batas parser. Keduanya 400 tanpa tulis, dan `oleh` dari form tidak pernah dipakai."""
    token = _token(cookie, _aksi_tetapkan(_guru_a()))
    data = {"token": token, "aksi": "tetapkan", "oleh": "akun_" + "1" * 32}
    data.update({nama: "" for nama in aturan.KUNCI_FORM if nama not in dibuang})
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 400
    assert _keadaan(berkas_tetap) == sebelum


def test_tetapkan_field_kurang_400_tanpa_tulis(server, cookie, berkas_tetap):
    token = _token(cookie, _aksi_tetapkan(_guru_a()))
    data = {"token": token, "aksi": "tetapkan"}
    data.update({nama: "" for nama in aturan.KUNCI_FORM if nama != "h1a_s"})

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 400
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("isi_blok", [
    {"h1a_m": "485", "h1a_s": "600"},  # bukan kelipatan 30
    {"h1a_m": "480"},  # hanya jam mulai
    {"h1a_m": "480", "h1a_s": "510"},  # kurang dari 60 menit
    {"h1a_m": "480", "h1a_s": "600", "h1b_m": "540", "h1b_s": "660"},  # beririsan
    {"h1a_m": "x", "h1a_s": "600"},  # bukan angka
    {"h1a_m": "900", "h1a_s": "800"},  # selesai sebelum mulai
])
def test_tetapkan_blok_tidak_sah_400_tanpa_tulis(server, cookie, berkas_tetap, isi_blok):
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = _kirim_tetapkan(server, cookie, _guru_a(), isi_blok)

    assert kode == 400
    assert _keadaan(berkas_tetap) == sebelum


def test_tetapkan_hanya_menulis_guru_sasaran_dan_oleh_dari_sesi(server, cookie, berkas_tetap):
    _kirim_tetapkan(server, cookie, _guru_b(), _blok_form(BLOK_RABU))

    assert tetap.aktif(_guru_b())["oleh"] == id_admin()
    assert tetap.aktif(_guru_a()) is None


def test_galat_umum_tetapkan_503(server, cookie, berkas_tetap, monkeypatch):
    def gagal(**_kwargs):
        raise tetap.GalatTetap(tetap.KIND_UMUM, "tidak bisa ditulis")

    monkeypatch.setattr(tetap, "tetapkan_admin", gagal)

    kode, _isi, _ = _kirim_tetapkan(server, cookie, _guru_a(), _blok_form(BLOK_SENIN))

    assert kode == 503
    assert not berkas_tetap.exists()


# --- POST: putus ----------------------------------------------------------------------------------

def test_putus_setuju_menjadikan_usulan_guru_aktif(server, cookie, berkas_tetap):
    usulan = _usul(_guru_a(), BLOK_SENIN)
    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)
    data = _form_putus(isi, usulan, "setuju")

    kode, _isi, tajuk = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 303
    assert tajuk["Location"].endswith("?pesan=tersimpan")
    assert tetap.aktif(_guru_a())["blok"] == BLOK_SENIN
    assert tetap.aktif(_guru_a())["asal"] == "guru"
    assert tetap.riwayat(_guru_a())[0]["diputus_oleh"] == id_admin()


def test_putus_tolak_tidak_mengaktifkan_dan_tercatat_ditolak(server, cookie, berkas_tetap):
    usulan = _usul(_guru_a(), BLOK_SENIN)

    kode, _isi, _ = _kirim_putus(server, cookie, _guru_a(), usulan, "tolak")

    assert kode == 303
    assert tetap.aktif(_guru_a()) is None
    assert tetap.menunggu(_guru_a()) is None
    assert tetap.ditolak_terakhir(_guru_a())["usulan_id"] == usulan


def test_putus_usulan_basi_409_tanpa_tulis(server, cookie, berkas_tetap):
    usulan_lama = _usul(_guru_a(), BLOK_SENIN)
    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)
    data = _form_putus(isi, usulan_lama, "setuju")
    _usul(_guru_a(), BLOK_SELASA)
    sebelum = _keadaan(berkas_tetap)

    kode, isi_galat, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 409
    assert TEKS_KONFLIK in isi_galat
    assert _keadaan(berkas_tetap) == sebelum
    assert tetap.aktif(_guru_a()) is None
    assert tetap.menunggu(_guru_a())["blok"] == BLOK_SELASA


def test_putus_usulan_guru_lain_409_tanpa_tulis(server, cookie, berkas_tetap):
    usulan_b = _usul(_guru_b(), BLOK_RABU)
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = _kirim_putus(server, cookie, _guru_a(), usulan_b, "setuju")

    assert kode == 409
    assert _keadaan(berkas_tetap) == sebelum
    assert tetap.aktif(_guru_b()) is None


def test_putus_token_guru_a_dikirim_ke_guru_b_409_tanpa_tulis(server, cookie, berkas_tetap):
    usulan_a = _usul(_guru_a(), BLOK_SENIN)
    token = _token(cookie, _aksi_putus(usulan_a, "setuju"))
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = _kirim_putus(server, cookie, _guru_b(), usulan_a, "setuju", token=token)

    assert kode == 409
    assert _keadaan(berkas_tetap) == sebelum
    assert tetap.aktif(_guru_a()) is None


def test_putus_usulan_tak_ada_409_tanpa_tulis(server, cookie, berkas_tetap):
    kode, _isi, _ = _kirim_putus(server, cookie, _guru_a(), 999, "setuju")

    assert kode == 409
    assert not berkas_tetap.exists()


@pytest.mark.parametrize("usulan_id, putusan", [("abc", "setuju"), ("0", "setuju"), ("1", "lain")])
def test_putus_format_salah_dengan_token_sah_400(server, cookie, berkas_tetap, usulan_id, putusan):
    """Token dibuat dari nilai mentah form, jadi token cocok dan validasi format berjalan sesudahnya."""
    token = _token(cookie, f"putus:{usulan_id}:{putusan}")
    data = {"token": token, "aksi": "putus", "usulan_id": usulan_id, "putusan": putusan}

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 400
    assert not berkas_tetap.exists()


def test_putus_field_berlebih_400_tanpa_tulis(server, cookie, berkas_tetap):
    usulan = _usul(_guru_a(), BLOK_SENIN)
    token = _token(cookie, _aksi_putus(usulan, "setuju"))
    data = {"token": token, "aksi": "putus", "usulan_id": str(usulan), "putusan": "setuju", "oleh": "x"}
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 400
    assert _keadaan(berkas_tetap) == sebelum


def test_putus_tanpa_usulan_id_403_karena_token_tak_cocok(server, cookie, berkas_tetap):
    usulan = _usul(_guru_a(), BLOK_SENIN)
    token = _token(cookie, _aksi_putus(usulan, "setuju"))
    data = {"token": token, "aksi": "putus", "putusan": "setuju"}

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 403


def test_galat_konflik_dari_dasar_putus_409(server, cookie, berkas_tetap, monkeypatch):
    usulan = _usul(_guru_a(), BLOK_SENIN)

    def konflik(**_kwargs):
        raise tetap.GalatTetap(tetap.KIND_KONFLIK, "tidak lagi menunggu")

    monkeypatch.setattr(tetap, "putus", konflik)

    kode, _isi, _ = _kirim_putus(server, cookie, _guru_a(), usulan, "setuju")

    assert kode == 409


def test_galat_umum_dasar_putus_503_tanpa_tulis(server, cookie, berkas_tetap, monkeypatch):
    usulan = _usul(_guru_a(), BLOK_SENIN)
    sebelum = _keadaan(berkas_tetap)

    def gagal(**_kwargs):
        raise tetap.GalatTetap(tetap.KIND_UMUM, "tidak bisa ditulis")

    monkeypatch.setattr(tetap, "putus", gagal)

    kode, _isi, _ = _kirim_putus(server, cookie, _guru_a(), usulan, "setuju")

    assert kode == 503
    assert _keadaan(berkas_tetap) == sebelum


def test_putus_basi_setelah_halaman_dirender_tidak_mengubah_db(server, cookie, berkas_tetap):
    """Urutan: admin melihat U1, guru mengirim U2, admin menyetujui U1 = 409 dan hash DB sama."""
    usulan_1 = _usul(_guru_a(), BLOK_SENIN)
    isi = _halaman(server, _jalur_guru(_guru_a()), cookie)
    data = _form_putus(isi, usulan_1, "setuju")
    _usul(_guru_a(), BLOK_SELASA)
    sebelum = _keadaan(berkas_tetap)

    kode, _isi, _ = minta_admin(server, _jalur_guru(_guru_a()), cookie, data)

    assert kode == 409
    assert _keadaan(berkas_tetap) == sebelum
