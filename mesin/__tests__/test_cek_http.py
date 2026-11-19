"""Rute cek gratis (Fase 2b) bagian guard: sakelar, persetujuan, token, peran, kepemilikan, laju.

Server HTTP sungguhan, semua data sintetis di tmp_path. Hasil/tautan/sisi anak ada di
test_cek_http_hasil.py. Yang dibuktikan di sini: tiap penolakan tidak punya efek samping.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_http  # noqa: E402
import cek_pages  # noqa: E402
import cek_pages_mulai  # noqa: E402
import policy_http  # noqa: E402
from cek_http_kit import (  # noqa: E402
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, HASIL, MULAI, NAMA_A, NAMA_B, POLA_TOKEN, TAUTAN,
    ambil_token, id_akun, jumlah, keadaan, keluarga, kirim_mulai, minta_mentah, mulai_cek,
    selesaikan, server, tambah_anak, token_form,
)

KOSONG = (0, 0, 0, 0)
SATU_CEK_SATU_TAUTAN = (1, 1, 15, 1)  # cek, sesi, soal sesi, tautan anak


# --- sakelar ---------------------------------------------------------------

@pytest.mark.parametrize("jalur", [MULAI, HASIL])
def test_sakelar_mati_get_halaman_belum_dibuka_tanpa_form_dan_tanpa_efek(keluarga, monkeypatch, jalur):
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    kode, isi, _t = minta_mentah(keluarga, jalur, AKUN_A)
    assert kode == 200 and "belum dibuka" in isi.lower()
    assert "<form" not in isi and NAMA_A not in isi
    assert keadaan(keluarga) == KOSONG


@pytest.mark.parametrize("jalur", [MULAI, TAUTAN])
def test_sakelar_mati_post_diperlakukan_rute_tak_dikenal_tanpa_efek(keluarga, monkeypatch, jalur):
    token = ambil_token(keluarga, AKUN_A)  # sah sewaktu sakelar hidup
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    acuan = minta_mentah(keluarga, "/rute-tidak-ada", AKUN_A, {"x": "1"})
    kode, isi, _t = minta_mentah(keluarga, jalur, AKUN_A, {"token": token, "setuju": "1"})
    assert (kode, isi) == (acuan[0], acuan[1]) and kode == 404
    assert "belum dibuka" not in isi.lower()
    assert keadaan(keluarga) == KOSONG


@pytest.mark.parametrize("nilai", ["", "0", "true", "2"])
def test_nilai_sakelar_selain_satu_tetap_mati(keluarga, monkeypatch, nilai):
    monkeypatch.setenv("FUNNEL_AKTIF", nilai)
    assert "belum dibuka" in minta_mentah(keluarga, MULAI, AKUN_A)[1].lower()


# --- halaman mulai ---------------------------------------------------------

def test_get_mulai_notice_centang_token_dan_nama_anak(keluarga):
    kode, isi, tajuk = minta_mentah(keluarga, MULAI, AKUN_A)
    assert kode == 200 and "no-store" in tajuk.get("Cache-Control", "")
    for butir in cek_pages.COPY_NOTICE:
        assert butir.replace("&", "&amp;") in isi
    assert 'name="setuju"' in isi and 'type="checkbox"' in isi and " required" in isi
    assert f'action="{MULAI}"' in isi and POLA_TOKEN.search(isi)
    assert NAMA_A in isi and NAMA_B not in isi
    assert "<script" not in isi.split("<body", 1)[1]


def test_get_mulai_pilih_anak_id_terkecil_bila_lebih_dari_satu(keluarga):
    tambah_anak(keluarga, "Anak Sintetis Gamma", "guru", 3)
    assert NAMA_A in minta_mentah(keluarga, MULAI, AKUN_A)[1]


def test_get_mulai_tanpa_anak_pesan_jujur_tanpa_form(keluarga):
    import auth
    auth.tambah_akun("guru-c", "sandi-guru-c-panjang-1", "guru")
    kode, isi, _t = minta_mentah(keluarga, MULAI, ("guru-c", "sandi-guru-c-panjang-1"))
    assert kode == 200 and cek_pages.COPY_TANPA_ANAK in isi and "<form" not in isi


def test_get_mulai_sesudah_selesai_dialihkan_ke_hasil(keluarga):
    selesaikan(keluarga, mulai_cek(keluarga), semua_benar=15)
    kode, isi, tajuk = minta_mentah(keluarga, MULAI, AKUN_A)
    assert (kode, tajuk["Location"], isi) == (303, HASIL, "")


def test_get_mulai_cek_berjalan_tidak_lagi_dialihkan_tetapi_menawarkan_lanjut(keluarga):
    mulai_cek(keluarga)
    kode, isi, _t = minta_mentah(keluarga, MULAI, AKUN_A)
    assert kode == 200 and NAMA_A in isi and f'action="{TAUTAN}"' in isi
    assert f'action="{MULAI}"' not in isi


# --- POST mulai: persetujuan -----------------------------------------------

def test_post_sah_hp_ini_membuat_satu_cek_dan_satu_sesi_lalu_303_ke_tautan_anak_tanpa_data_di_url(keluarga):
    kode, isi, tajuk = kirim_mulai(keluarga, AKUN_A, cara="hp_ini")
    assert (kode, isi) == (303, "")
    assert re.fullmatch(r"/mulai/[A-Za-z0-9_-]{43}\?di=hp-ini", tajuk["Location"])
    assert NAMA_A not in str(tajuk) and "Sintetis" not in tajuk["Location"]
    assert "no-store" in tajuk["Cache-Control"] and tajuk["Referrer-Policy"] == "no-referrer"
    assert keadaan(keluarga) == SATU_CEK_SATU_TAUTAN
    with keluarga.buka() as kon:
        baris = kon.execute("SELECT id_akun, siswa_id, setuju_pada FROM cek_gratis").fetchone()
    assert baris["id_akun"] == id_akun(AKUN_A) and baris["siswa_id"] == keluarga.anak_a
    assert baris["setuju_pada"]


def test_post_sah_hp_anak_membuat_satu_cek_dan_menampilkan_qr_sekali(keluarga):
    kode, isi, tajuk = kirim_mulai(keluarga, AKUN_A, cara="hp_anak")
    assert kode == 200 and "<svg" in isi and "Location" not in tajuk
    assert "no-store" in tajuk["Cache-Control"] and tajuk["Referrer-Policy"] == "no-referrer"
    assert re.search(r"https?://[^/]+/mulai/[A-Za-z0-9_-]{43}", isi)
    assert keadaan(keluarga) == SATU_CEK_SATU_TAUTAN
    with keluarga.buka() as kon:
        baris = kon.execute("SELECT id_akun, siswa_id, setuju_pada FROM cek_gratis").fetchone()
    with keluarga.buka() as kon:
        baris = kon.execute("SELECT id_akun, siswa_id, setuju_pada FROM cek_gratis").fetchone()
    assert baris["id_akun"] == id_akun(AKUN_A) and baris["siswa_id"] == keluarga.anak_a
    assert baris["setuju_pada"]


@pytest.mark.parametrize("cara", [None, "", "hp-ini", "HP_INI", "hp_ini ", "tablet"])
def test_cara_kosong_atau_asing_ditolak_400_tanpa_efek_dan_tanpa_memakan_laju(keluarga, cara):
    kode, isi, _t = kirim_mulai(keluarga, AKUN_A, cara=cara)
    assert kode == 400 and cek_pages_mulai.COPY_CARA_WAJIB in isi
    assert keadaan(keluarga) == KOSONG
    for _ in range(cek_http.BATAS_PERMULAAN_PER_HARI):  # laju utuh: sepuluh permulaan sah masih lolos
        assert kirim_mulai(keluarga, AKUN_A)[0] == 200


@pytest.mark.parametrize("setuju", [None, "", "0", "on", "true", "2"])
def test_tanpa_setuju_satu_tidak_ada_sesi_dan_baris(keluarga, setuju):
    kode, isi, _t = kirim_mulai(keluarga, AKUN_A, setuju=setuju)
    assert kode == 400 and cek_pages.COPY_WAJIB_CENTANG in isi
    assert keadaan(keluarga) == KOSONG


def test_halaman_wajib_centang_membawa_token_segar_yang_bisa_dipakai(keluarga):
    _k, isi, _t = kirim_mulai(keluarga, AKUN_A, setuju=None)
    token = POLA_TOKEN.search(isi).group(1)
    assert kirim_mulai(keluarga, AKUN_A, token=token)[0] == 200


def test_post_ganda_tidak_membuat_sesi_kedua(keluarga):
    assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    awal = keadaan(keluarga)
    assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    assert keadaan(keluarga) == awal == SATU_CEK_SATU_TAUTAN


# --- POST mulai: token & whitelist -----------------------------------------

def _jaga(keluarga, kode_harap, **kw):
    kode, isi, _t = kirim_mulai(keluarga, AKUN_A, **kw)
    assert kode == kode_harap
    assert keadaan(keluarga) == KOSONG
    return isi


@pytest.mark.parametrize("token", ["", "1.deadbeef", "x" * 300, "bukan-token"])
def test_token_salah_ditolak_tanpa_efek(keluarga, token):
    _jaga(keluarga, 403, token=token)


def test_token_kedaluwarsa_ditolak(keluarga, monkeypatch):
    token = ambil_token(keluarga, AKUN_A)
    asli = time.time
    monkeypatch.setattr(cek_http.time, "time", lambda: asli() + cek_http.UMUR_TOKEN_DETIK + 5)
    _jaga(keluarga, 403, token=token)


def test_token_akun_lain_tidak_berlaku(keluarga):
    _jaga(keluarga, 403, token=ambil_token(keluarga, AKUN_B))


def test_token_aksi_lain_dan_token_kontak_tidak_berlaku(keluarga):
    _k, isi, _t = minta_mentah(keluarga, "/akun/kontak", AKUN_A)
    token_kontak = POLA_TOKEN.search(isi).group(1)
    _jaga(keluarga, 403, token=token_kontak)
    _jaga(keluarga, 403, token=token_form(AKUN_A, cek_http.AKSI_TAUTAN))


@pytest.mark.parametrize("nama", ["id_akun", "siswa_id", "pemilik", "pengguna", "sesi_id"])
def test_field_asing_ditolak_tanpa_efek(keluarga, nama):
    _jaga(keluarga, 400, ekstra={nama: id_akun(AKUN_B)})


def test_id_akun_form_tidak_mengalihkan_cek_ke_akun_lain(keluarga):
    kode, _i, _t = kirim_mulai(keluarga, AKUN_A, ekstra={"id_akun": id_akun(AKUN_B)})
    assert kode == 400 and keadaan(keluarga) == KOSONG
    kode, _i, tajuk = minta_mentah(keluarga, HASIL, AKUN_B)
    assert (kode, tajuk["Location"]) == (303, MULAI)  # B tetap belum_mulai
    assert NAMA_A not in minta_mentah(keluarga, MULAI, AKUN_B)[1]


def test_token_hilang_dan_setuju_ganda_ditolak(keluarga):
    assert minta_mentah(keluarga, MULAI, AKUN_A, {"setuju": "1"})[0] == 400
    token = ambil_token(keluarga, AKUN_A)
    assert minta_mentah(keluarga, MULAI, AKUN_A, {"token": token, "setuju": ["1", "1"]})[0] == 400
    assert minta_mentah(keluarga, MULAI, AKUN_A, {})[0] == 400
    assert keadaan(keluarga) == KOSONG


def test_post_lintas_situs_ditolak_dispatcher(keluarga):
    kode, _i, _t = minta_mentah(
        keluarga, MULAI, AKUN_A, {"token": ambil_token(keluarga, AKUN_A), "setuju": "1"},
        headers={"Sec-Fetch-Site": "cross-site"})
    assert kode == 403 and keadaan(keluarga) == KOSONG


# --- peran -----------------------------------------------------------------

def test_anonim_dan_murid_ditolak_palang_sandi_tanpa_efek(keluarga):
    for akun in (None, AKUN_MURID):
        for jalur in (MULAI, HASIL):
            kode, isi, _t = minta_mentah(keluarga, jalur, akun)
            assert kode == 401 and "perlu masuk" in isi.lower() and NAMA_A not in isi
        for jalur in (MULAI, TAUTAN):
            assert minta_mentah(keluarga, jalur, akun, {"token": "x", "setuju": "1"})[0] == 401
    assert keadaan(keluarga) == KOSONG


@pytest.mark.parametrize("hidup", ["1", "0"])
def test_admin_404_identik_rute_tak_dikenal_get_dan_post(keluarga, monkeypatch, hidup):
    monkeypatch.setenv("FUNNEL_AKTIF", hidup)
    acuan_get = minta_mentah(keluarga, "/rute-tidak-ada", AKUN_ADMIN)
    acuan_post = minta_mentah(keluarga, "/rute-tidak-ada", AKUN_ADMIN, {"token": "x"})
    for jalur in (MULAI, HASIL):
        assert minta_mentah(keluarga, jalur, AKUN_ADMIN)[:2] == acuan_get[:2]
    for jalur in (MULAI, TAUTAN):
        assert minta_mentah(keluarga, jalur, AKUN_ADMIN, {"token": "x", "setuju": "1"})[:2] == acuan_post[:2]
    assert acuan_get[0] == acuan_post[0] == 404 and acuan_get[1] != acuan_post[1]
    assert keadaan(keluarga) == KOSONG


def test_admin_tidak_bisa_memakai_token_guru(keluarga):
    kode, isi, _t = minta_mentah(
        keluarga, MULAI, AKUN_ADMIN, {"token": ambil_token(keluarga, AKUN_A), "setuju": "1"})
    assert kode == 404 and keadaan(keluarga) == KOSONG


# --- persetujuan (policy) ---------------------------------------------------

def test_gerbang_persetujuan_mengarahkan_tanpa_efek(keluarga, monkeypatch):
    token = ambil_token(keluarga, AKUN_A)
    monkeypatch.setattr(policy_http, "perlu", lambda p: True)
    kode, isi, tajuk = minta_mentah(keluarga, MULAI, AKUN_A, {"token": token, "setuju": "1"})
    assert (kode, isi, tajuk["Location"]) == (303, "", "/persetujuan")
    assert keadaan(keluarga) == KOSONG


# --- kepemilikan -----------------------------------------------------------

def test_dua_akun_cek_milik_sendiri_dan_tanpa_kebocoran(keluarga):
    assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    with keluarga.buka() as kon:
        cek_a = tuple(kon.execute("SELECT * FROM cek_gratis").fetchone())
    isi_b = minta_mentah(keluarga, HASIL, AKUN_B)
    assert (isi_b[0], isi_b[2]["Location"]) == (303, MULAI)
    kode, isi, _t = minta_mentah(keluarga, MULAI, AKUN_B)
    assert kode == 200 and NAMA_B in isi and NAMA_A not in isi
    assert minta_mentah(keluarga, TAUTAN, AKUN_B, {"token": token_form(AKUN_B, cek_http.AKSI_TAUTAN)})[0] == 303
    assert keadaan(keluarga) == SATU_CEK_SATU_TAUTAN
    assert kirim_mulai(keluarga, AKUN_B)[0] == 200
    with keluarga.buka() as kon:
        assert tuple(kon.execute("SELECT * FROM cek_gratis WHERE id_akun = ?",
                                 (id_akun(AKUN_A),)).fetchone()) == cek_a
        assert kon.execute("SELECT COUNT(*) FROM cek_gratis").fetchone()[0] == 2
    assert NAMA_A not in minta_mentah(keluarga, HASIL, AKUN_B)[1]


# --- pembatas laju ----------------------------------------------------------

def test_permulaan_ke_sebelas_dari_ip_sama_ditolak_tanpa_efek(keluarga):
    for _ in range(cek_http.BATAS_PERMULAAN_PER_HARI):
        assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    awal = keadaan(keluarga)
    kode, isi, _t = kirim_mulai(keluarga, AKUN_B)
    assert kode == 429 and "Terlalu banyak" in isi
    assert keadaan(keluarga) == awal == SATU_CEK_SATU_TAUTAN


def test_di_bawah_batas_akun_lain_tetap_bisa(keluarga):
    assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    assert kirim_mulai(keluarga, AKUN_B)[0] == 200
    assert keadaan(keluarga)[0] == 2


def test_jendela_laju_geser_lewat_sehari(keluarga, monkeypatch):
    for _ in range(cek_http.BATAS_PERMULAAN_PER_HARI):
        kirim_mulai(keluarga, AKUN_A)
    asli = time.monotonic
    monkeypatch.setattr(cek_http.time, "monotonic",
                        lambda: asli() + cek_http.JENDELA_LAJU_DETIK + 1)
    assert kirim_mulai(keluarga, AKUN_B)[0] == 200


# --- kelas ------------------------------------------------------------------

def test_kelas_1_tanpa_materi_dasar_pesan_jujur_tanpa_baris(server):
    tambah_anak(server, NAMA_A, "guru", 1)
    kode, isi, _t = kirim_mulai(server, AKUN_A)
    assert kode == 409 and cek_pages.COPY_BELUM_TERSEDIA in isi
    assert keadaan(server) == KOSONG and NAMA_A not in isi


def test_kelas_belum_diisi_pesan_jujur_tanpa_baris(server):
    tambah_anak(server, NAMA_A, "guru", None)
    kode, isi, _t = kirim_mulai(server, AKUN_A)
    assert kode == 409 and cek_pages.COPY_BELUM_TERSEDIA in isi
    assert keadaan(server) == KOSONG


def test_pesan_galat_tidak_memuat_nama_atau_isi_eksepsi(server):
    tambah_anak(server, NAMA_A, "guru", None)
    _k, isi, _t = kirim_mulai(server, AKUN_A)
    assert "belum diisi; isi kelas" not in isi and NAMA_A not in isi


def test_akun_tanpa_anak_post_pesan_jujur_tanpa_baris(server):
    token = token_form(AKUN_A, cek_http.AKSI_MULAI)
    kode, isi, _t = minta_mentah(server, MULAI, AKUN_A, {"token": token, "setuju": "1", "cara": "hp_anak"})
    assert kode == 409 and cek_pages.COPY_TANPA_ANAK in isi and keadaan(server) == KOSONG


# --- jejak ------------------------------------------------------------------

def test_nama_anak_tidak_ada_di_url_log_stdout_stderr(keluarga, capfd, caplog):
    caplog.set_level(logging.DEBUG)
    _k, _i, tajuk = kirim_mulai(keluarga, AKUN_A)
    kirim_mulai(keluarga, AKUN_A, setuju="0")
    minta_mentah(keluarga, HASIL, AKUN_A)
    keluar = capfd.readouterr()
    gabung = keluar.out + keluar.err + caplog.text + str(tajuk)
    assert NAMA_A not in gabung and "Sintetis" not in gabung
