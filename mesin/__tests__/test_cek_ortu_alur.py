"""Alur Cek Kemampuan sisi orang tua (funnel Fase 3): daftar, login lanjut, siap mulai, serah HP, hasil.

Server HTTP sungguhan, data sintetis di tmp_path. Sesi login nyata (cookie) dipakai untuk
bukti logout `hp_ini`: autentikasi Basic tidak punya sesi server untuk dihapus.
"""
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import choice_store  # noqa: E402
import cek_http  # noqa: E402
import cek_pages  # noqa: E402
import cek_pages_mulai  # noqa: E402
import daftar_cek_pages  # noqa: E402
import database  # noqa: E402
import funnel_style  # noqa: E402
import funnel_style_alur  # noqa: E402
from cek_gratis_kit import jawab  # noqa: E402
from cek_http_kit import (  # noqa: E402
    AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, HASIL, MULAI, NAMA_A, POLA_TOKEN, TAUTAN, ambil_token,
    jumlah, keadaan, keluarga, kirim_mulai, minta_mentah, mulai_cek, selesaikan, server,
    tambah_anak, token_form,
)

LANJUT_CEK = ("/cek-kemampuan/mulai", "/cek-kemampuan/hasil")
POLA_TAUTAN_ANAK = r"/mulai/([A-Za-z0-9_-]{43})\?di=hp-ini"
POLA_HIDDEN_LANJUT = re.compile(r'<input type="hidden" name="lanjut" value="([^"]*)">')


def _masuk(server, akun, lanjut=None):
    data = {"nama": akun[0], "sandi": akun[1]}
    if lanjut is not None:
        data["lanjut"] = lanjut
    return minta_mentah(server, "/masuk", data=data)


def _cookie_login(server, akun) -> str:
    kode, _i, tajuk = _masuk(server, akun)
    assert kode == 303
    return tajuk["Set-Cookie"].split(";")[0]


def _dengan_cookie(server, jalur, cookie, data=None):
    return minta_mentah(server, jalur, data=data, headers={"Cookie": cookie})


# --- login: lanjut allow-list ------------------------------------------------

@pytest.mark.parametrize("tujuan", LANJUT_CEK)
def test_lanjut_cek_persis_dibawa_form_dan_diikuti_guru(server, tujuan):
    _k, isi, _t = minta_mentah(server, "/masuk?lanjut=" + tujuan)
    assert POLA_HIDDEN_LANJUT.search(isi).group(1) == tujuan
    kode, _i, tajuk = _masuk(server, AKUN_A, tujuan)
    assert (kode, tajuk["Location"]) == (303, tujuan)


@pytest.mark.parametrize("varian", [
    "/cek-kemampuan/hasil/../guru", "/cek-kemampuan/hasil/", "/cek-kemampuan/hasilx",
    "/cek-kemampuan/hasil?x=1", "/cek-kemampuan/hasil#a", "/cek-kemampuan/hasil ",
    "/cek-kemampuan/mulai/..", "/cek-kemampuan", "/cek-kemampuan/tautan", "/CEK-KEMAMPUAN/HASIL",
    "//evil.example", "//cek-kemampuan/hasil", "https://evil.example/cek-kemampuan/hasil",
    "/guru", "/admin", "",
])
def test_lanjut_varian_ditolak_di_form_dan_login_tetap_ke_beranda(server, varian):
    _k, isi, _t = minta_mentah(server, "/masuk?" + urllib.parse.urlencode({"lanjut": varian}))
    assert POLA_HIDDEN_LANJUT.search(isi) is None
    kode, _i, tajuk = _masuk(server, AKUN_A, varian)
    assert (kode, tajuk["Location"]) == (303, "/guru")


def test_lanjut_ganda_diabaikan_di_get_dan_post(server):
    _k, isi, _t = minta_mentah(server, "/masuk?lanjut=/cek-kemampuan/hasil&lanjut=/cek-kemampuan/mulai")
    assert POLA_HIDDEN_LANJUT.search(isi) is None
    kode, _i, tajuk = _masuk(server, AKUN_A, list(LANJUT_CEK))
    assert (kode, tajuk["Location"]) == (303, "/guru")


@pytest.mark.parametrize("akun,harap", [(AKUN_MURID, "/murid"), (AKUN_ADMIN, "/admin")])
def test_lanjut_cek_tidak_diikuti_murid_dan_admin(server, akun, harap):
    for tujuan in LANJUT_CEK:
        kode, _i, tajuk = _masuk(server, akun, tujuan)
        assert (kode, tajuk["Location"]) == (303, harap)


def test_lanjut_cek_tidak_berlaku_saat_sakelar_mati(server, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF")
    _k, isi, _t = minta_mentah(server, "/masuk?lanjut=/cek-kemampuan/hasil")
    assert POLA_HIDDEN_LANJUT.search(isi) is None
    kode, _i, tajuk = _masuk(server, AKUN_A, "/cek-kemampuan/hasil")
    assert (kode, tajuk["Location"]) == (303, "/guru")


def test_judul_serah_ke_orang_tua_hanya_untuk_lanjut_ke_hasil(server):
    _k, hasil, _t = minta_mentah(server, "/masuk?lanjut=/cek-kemampuan/hasil")
    _k, mulai, _t = minta_mentah(server, "/masuk?lanjut=/cek-kemampuan/mulai")
    _k, biasa, _t = minta_mentah(server, "/masuk")
    for kata in ("Serahkan ke Ayah/Bunda", "Masukkan sandi untuk melihat hasil"):
        assert kata in hasil and kata not in mulai and kata not in biasa
    assert 'name="nama"' in hasil and 'name="sandi"' in hasil and 'type="password"' in hasil


# --- serah HP: hp_ini menghapus sesi server ------------------------------------

def _siap_kirim(server, cookie):
    _k, isi, _t = _dengan_cookie(server, MULAI, cookie)
    return POLA_TOKEN.search(isi).group(1)


def test_hp_ini_menghapus_sesi_server_dan_cookie_lama_tidak_lagi_membuka_guru(keluarga):
    cookie = _cookie_login(keluarga, AKUN_A)
    assert _dengan_cookie(keluarga, "/guru", cookie)[0] == 200
    token = _siap_kirim(keluarga, cookie)
    kode, isi, tajuk = _dengan_cookie(keluarga, MULAI, cookie,
                                      {"token": token, "setuju": "1", "cara": "hp_ini"})
    assert (kode, isi) == (303, "")
    assert "Max-Age=0" in tajuk["Set-Cookie"] and tajuk["Set-Cookie"].startswith("osn_sesi=;")
    # Cookie lama (dipakai ulang oleh penyerang atau tab lain) tidak lagi mengesahkan apa pun.
    anonim = minta_mentah(keluarga, "/guru")
    ulang = _dengan_cookie(keluarga, "/guru", cookie)
    assert ulang[0] == anonim[0] != 200 and ulang[2].get("Location") == anonim[2].get("Location")
    assert _dengan_cookie(keluarga, MULAI, cookie)[0] in (401, 303)
    # Tautan anak terbit dan valid, dengan penanda `di`.
    token_anak = re.fullmatch(POLA_TAUTAN_ANAK, tajuk["Location"]).group(1)
    assert minta_mentah(keluarga, f"/mulai/{token_anak}")[0] == 200
    assert keadaan(keluarga) == (1, 1, 15, 1)


def test_hp_ini_tidak_mengeluarkan_akun_lain(keluarga):
    cookie_a, cookie_b = _cookie_login(keluarga, AKUN_A), _cookie_login(keluarga, AKUN_B)
    token = _siap_kirim(keluarga, cookie_a)
    assert _dengan_cookie(keluarga, MULAI, cookie_a, {"token": token, "setuju": "1", "cara": "hp_ini"})[0] == 303
    assert _dengan_cookie(keluarga, "/guru", cookie_b)[0] == 200


def test_hp_anak_tetap_masuk_dan_menampilkan_qr(keluarga):
    cookie = _cookie_login(keluarga, AKUN_A)
    token = _siap_kirim(keluarga, cookie)
    kode, isi, tajuk = _dengan_cookie(keluarga, MULAI, cookie,
                                      {"token": token, "setuju": "1", "cara": "hp_anak"})
    assert kode == 200 and "<svg" in isi and "Set-Cookie" not in tajuk
    assert _dengan_cookie(keluarga, "/guru", cookie)[0] == 200


def test_hp_ini_tidak_keluar_bila_tautan_tidak_terbit_karena_cek_sudah_selesai(keluarga):
    cookie = _cookie_login(keluarga, AKUN_A)
    token = _siap_kirim(keluarga, cookie)
    selesaikan(keluarga, mulai_cek(keluarga), semua_benar=15)
    kode, _i, tajuk = _dengan_cookie(keluarga, MULAI, cookie,
                                     {"token": token, "setuju": "1", "cara": "hp_ini"})
    assert (kode, tajuk["Location"]) == (303, HASIL) and "Set-Cookie" not in tajuk
    assert _dengan_cookie(keluarga, "/guru", cookie)[0] == 200
    assert jumlah(keluarga, "tautan_sesi") == 0


# --- lanjutkan cek yang berjalan lewat /tautan --------------------------------

def test_lanjut_lewat_tautan_tidak_memakan_laju_mulai(keluarga):
    for _ in range(cek_http.BATAS_PERMULAAN_PER_HARI):
        assert kirim_mulai(keluarga, AKUN_A)[0] == 200
    assert kirim_mulai(keluarga, AKUN_A)[0] == 429
    tautan = {"token": token_form(AKUN_A, cek_http.AKSI_TAUTAN)}
    kode, isi, _t = minta_mentah(keluarga, TAUTAN, AKUN_A, {**tautan, "cara": "hp_anak"})
    assert kode == 200 and "<svg" in isi
    kode, _i, tajuk = minta_mentah(keluarga, TAUTAN, AKUN_A, {**tautan, "cara": "hp_ini"})
    assert kode == 303 and re.fullmatch(POLA_TAUTAN_ANAK, tajuk["Location"])
    assert jumlah(keluarga, "cek_gratis") == 1


@pytest.mark.parametrize("cara", ["", "tablet", "HP_INI"])
def test_tautan_cara_asing_ditolak_tanpa_efek(keluarga, cara):
    mulai_cek(keluarga)
    data = {"token": token_form(AKUN_A, cek_http.AKSI_TAUTAN), "cara": cara}
    assert minta_mentah(keluarga, TAUTAN, AKUN_A, data)[0] == 400
    assert jumlah(keluarga, "tautan_sesi") == 0


def test_tautan_hp_ini_menghapus_sesi_server(keluarga):
    mulai_cek(keluarga)
    cookie = _cookie_login(keluarga, AKUN_A)
    token = re.search(r'name="token" value="([^"]+)"', _dengan_cookie(keluarga, MULAI, cookie)[1]).group(1)
    kode, _i, _t = _dengan_cookie(keluarga, TAUTAN, cookie, {"token": token, "cara": "hp_ini"})
    assert kode == 303
    assert _dengan_cookie(keluarga, "/guru", cookie)[0] != 200


# --- halaman siap mulai --------------------------------------------------------

def _baca_mulai(server, akun=AKUN_A):
    kode, isi, tajuk = minta_mentah(server, MULAI, akun)
    assert kode == 200 and "no-store" in tajuk["Cache-Control"]
    return isi


def test_belum_mulai_menampilkan_kartu_info_tips_centang_lipatan_dan_dua_tombol(keluarga):
    isi = _baca_mulai(keluarga)
    assert f"{NAMA_A} · kelas 4" in isi and "Belum mulai" in isi
    for butir in ("15 soal", "±25 menit", "Boleh jeda", "Gratis"):
        assert butir in isi
    assert isi.count('class="funnel-tips-st"') == 1 and isi.count("<li><span class=\"funnel-ubin-st") == 3
    assert "<details" in isi and "30 hari" in isi and "7 hari" not in isi
    assert cek_pages.COPY_SETUJU in isi and 'name="setuju"' in isi
    assert isi.count('<form') == 1 and f'action="{MULAI}"' in isi
    assert re.findall(r'<button type="submit" name="cara" value="(\w+)"', isi) == ["hp_ini", "hp_anak"]
    assert cek_pages_mulai.COPY_HP_INI in isi and cek_pages_mulai.COPY_HP_ANAK in isi
    assert "<progress" not in isi


@pytest.mark.parametrize("benar,salah_terisi,harap", [(0, 0, 0), (6, 0, 6), (3, 2, 5), (15, 0, 15)])
def test_status_berjalan_menghitung_soal_terjawab_tanpa_benar_salah(keluarga, benar, salah_terisi, harap):
    sesi = mulai_cek(keluarga)
    with keluarga.buka() as kon:
        jawab(kon, sesi, semua_benar=benar)
        baris = database.isi_sesi(kon, sesi)
        pilihan = choice_store.daftar_pilihan(kon, sesi)
        for b in baris[benar:benar + salah_terisi]:
            salah = next(o.nilai for o in pilihan[b["sesi_soal_id"]].opsi if o.nilai != b["kunci"])
            database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban=salah)
    isi = _baca_mulai(keluarga)
    teks = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.split("</style>", 1)[1]))
    if harap == 0:
        assert "Belum mulai" in teks and "<progress" not in isi
    else:
        assert f"Sedang berjalan · {harap} dari 15 soal" in teks
        assert f'max="15" value="{harap}"' in isi
    assert f'action="{TAUTAN}"' in isi and f'action="{MULAI}"' not in isi and 'name="setuju"' not in isi
    assert re.findall(r'<button type="submit" name="cara" value="(\w+)"', isi) == ["hp_ini", "hp_anak"]
    for kata in ("benar", "salah", "skor", "Skor"):
        assert kata not in teks.replace("pilihan ganda", "")


def test_status_berjalan_tidak_membocorkan_kunci_atau_skor(keluarga):
    sesi = mulai_cek(keluarga)
    with keluarga.buka() as kon:
        jawab(kon, sesi, semua_benar=7)
        kunci = [b["kunci"] for b in database.isi_sesi(kon, sesi)][:7]
    isi = _baca_mulai(keluarga)
    assert "7 dari 15" in isi and not any(f'value="{k}"' in isi for k in kunci if len(k) > 3)
    assert "Kategori" not in isi and "dari 100" not in isi


def test_selesai_diarahkan_ke_hasil_dan_bukan_berjalan_15_dari_15(keluarga):
    selesaikan(keluarga, mulai_cek(keluarga), semua_benar=15)
    kode, isi, tajuk = minta_mentah(keluarga, MULAI, AKUN_A)
    assert (kode, isi, tajuk["Location"]) == (303, "", HASIL)


def test_get_siap_mulai_tidak_menilai_cek_yang_sudah_dikumpulkan(keluarga):
    """GET hanya membaca: penilaian terjadi di halaman hasil, bukan di siap mulai."""
    selesaikan(keluarga, mulai_cek(keluarga), semua_benar=15)
    kode, _isi, tajuk = minta_mentah(keluarga, MULAI, AKUN_A)
    assert (kode, tajuk["Location"]) == (303, HASIL)
    with keluarga.buka() as kon:
        assert kon.execute("SELECT skor FROM cek_gratis").fetchone()[0] is None
    assert minta_mentah(keluarga, HASIL, AKUN_A)[0] == 200
    with keluarga.buka() as kon:
        assert kon.execute("SELECT skor FROM cek_gratis").fetchone()[0] is not None


def test_akun_tanpa_kelas_pesan_jujur_dan_tautan_isi_kelas_bukan_tombol_buntu(server):
    tambah_anak(server, NAMA_A, "guru", None)
    isi = _baca_mulai(server)
    assert cek_pages_mulai.COPY_TANPA_KELAS in isi and "Kelas anak belum diisi" in isi
    assert f'href="{cek_pages_mulai.RUTE_KELAS}"' in isi
    assert "<form" not in isi and 'name="cara"' not in isi and 'name="setuju"' not in isi
    kode, halaman, _t = minta_mentah(server, cek_pages_mulai.RUTE_KELAS, AKUN_A)
    assert kode == 200 and "kelas_sekolah" in halaman  # rute tujuan memang memuat form kelas
    assert keadaan(server) == (0, 0, 0, 0)


def test_halaman_siap_mulai_milik_akun_sendiri(keluarga):
    mulai_cek(keluarga)
    assert NAMA_A in _baca_mulai(keluarga) and "Beta" not in _baca_mulai(keluarga)
    assert "Alfa" not in _baca_mulai(keluarga, AKUN_B)


# --- hasil ----------------------------------------------------------------------

def _hasil(kuat, perlu, status="selesai"):
    return {"status": status, "skor": 60, "kategori": "Cukup baik", "jumlah_soal": 15,
            "ringkasan": {"kuat": list(kuat), "perlu": list(perlu)}}


def test_ringkasan_maksimal_dua_butir_per_bagian_di_halaman():
    isi = cek_pages.halaman_hasil(("guru", "guru"), _hasil(["K1", "K2", "K3", "K4"], ["P1", "P2", "P3"]),
                                  "Anak Sintetis", "123.tok", kelas=4).decode()
    assert "K1" in isi and "K2" in isi and "K3" not in isi and "K4" not in isi
    assert "P1" in isi and "P2" in isi and "P3" not in isi


def test_hasil_selesai_memuat_x_dari_15_benar_cincin_dan_pil(keluarga):
    sesi = mulai_cek(keluarga)
    selesaikan(keluarga, sesi, semua_benar=9)
    kode, isi, _t = minta_mentah(keluarga, HASIL, AKUN_A)
    assert kode == 200 and "9 dari 15 soal benar" in isi
    assert 'stroke-dasharray="60 100"' in isi and cek_pages.COPY_LABEL_GAMBARAN in isi
    assert f"Hasil {NAMA_A} · kelas 4" in isi


@pytest.mark.parametrize("benar", [0, 1, 7, 14, 15])
def test_jumlah_benar_kebalikan_skor_untuk_semua_nilai(benar):
    from cek_gratis_skor import hitung_skor, jumlah_benar
    assert jumlah_benar(hitung_skor(benar, 15), 15) == benar


def test_jumlah_benar_none_untuk_masukan_tidak_sah():
    from cek_gratis_skor import jumlah_benar
    assert jumlah_benar(101, 15) is None and jumlah_benar("60", 15) is None and jumlah_benar(60, 0) is None


def test_belum_selesai_tanpa_skor_dengan_tautan_ke_halaman_siap_mulai(keluarga):
    sesi = mulai_cek(keluarga)
    with keluarga.buka() as kon:
        jawab(kon, sesi, semua_benar=5)
    _k, isi, _t = minta_mentah(keluarga, HASIL, AKUN_A)
    badan = isi.split("</style>", 1)[1]
    assert f'href="{MULAI}"' in badan and "funnel-cincin" not in badan and "dari 15" not in badan
    assert "stroke-dasharray" not in badan and "Cukup" not in badan


# --- daftar jalur cek -----------------------------------------------------------

@pytest.fixture()
def server_daftar(server):
    import admin_registration
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    admin_registration.migrasikan_profil_registrasi(database.BAWAAN)
    return server


def _daftar(server, *, jalur_cek, kelas="4", **tambah):
    _k, isi, _t = server.minta("/daftar?jalur=cek" if jalur_cek else "/daftar")
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = dict(nama="ortu-funnel", sandi="sandi-form-sintetis", setuju="1", token_form=token,
                nama_anak="Profil Sintetis", **tambah)
    if kelas is not None:
        data["kelas_sekolah"] = kelas
    if jalur_cek:
        data.update(jalur="cek", wa="0812-3456-7890")
    return minta_mentah(server, "/daftar", data=data)


def _tanpa_efek(server):
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0] == 0
    assert auth.cari_akun("ortu-funnel") is None


@pytest.mark.parametrize("kelas", ["", None])
def test_jalur_cek_menolak_kelas_kosong_dan_mengisi_ulang_form(server_daftar, kelas):
    kode, isi, tajuk = _daftar(server_daftar, jalur_cek=True, kelas=kelas)
    assert kode == 200 and "Set-Cookie" not in tajuk
    assert daftar_cek_pages.COPY_KELAS_WAJIB in isi
    assert 'value="Profil Sintetis"' in isi and 'value="0812-3456-7890"' in isi
    assert 'name="kelas_sekolah"' in isi and " checked" not in isi
    _tanpa_efek(server_daftar)


def test_jalur_cek_menolak_kelas_di_luar_1_sampai_6(server_daftar):
    kode, _i, tajuk = _daftar(server_daftar, jalur_cek=True, kelas="9")
    assert kode != 303 and "Set-Cookie" not in tajuk
    _tanpa_efek(server_daftar)


def test_jalur_cek_dengan_kelas_sah_membuat_akun_dan_ke_siap_mulai(server_daftar):
    kode, _i, tajuk = _daftar(server_daftar, jalur_cek=True, kelas="3")
    assert (kode, tajuk["Location"]) == (303, MULAI)
    with server_daftar.buka() as kon:
        assert kon.execute("SELECT kelas_sekolah FROM profil_belajar").fetchone()[0] == 3


def test_jalur_biasa_tetap_boleh_tanpa_kelas(server_daftar):
    kode, _i, tajuk = _daftar(server_daftar, jalur_cek=False, kelas="")
    assert kode == 303 and tajuk["Location"].startswith("/anak/")
    with server_daftar.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0] == 1


def test_form_daftar_cek_satu_form_enam_radio_wajib_tab_dan_isi_ulang(server):
    _k, isi, _t = server.minta("/daftar?jalur=cek")
    assert isi.count("<form") == 1 and isi.count('action="/daftar"') == 1
    assert re.findall(r'<input type="radio" name="kelas_sekolah" value="(\d)" required', isi) == list("123456")
    assert 'href="/masuk?lanjut=/cek-kemampuan/mulai"' in isi and 'aria-current="page"' in isi
    assert 'name="jalur" value="cek"' in isi and 'name="nama_anak"' in isi and 'name="wa"' in isi
    assert isi.split("</style>", 1)[1].count("funnel-sapa-maskot-st") == 1 and 'alt=""' in isi
    assert "<select" not in isi.split("</style>", 1)[1]


def test_form_daftar_cek_menandai_kelas_terpilih():
    isi = daftar_cek_pages.isi_daftar_cek(kelas_sekolah=5)
    assert isi.count(" checked") == 1 and 'value="5" required checked' in isi


# --- markup & CSS ----------------------------------------------------------------

def test_halaman_orang_tua_tanpa_js_baru_hex_dan_gaya_inline_serta_kelas_terdefinisi(keluarga):
    sesi = mulai_cek(keluarga)
    halaman = [_baca_mulai(keluarga)]
    with keluarga.buka() as kon:
        jawab(kon, sesi, semua_benar=4)
    halaman.append(_baca_mulai(keluarga))
    selesaikan(keluarga, sesi, semua_benar=9)
    halaman.append(minta_mentah(keluarga, HASIL, AKUN_A)[1])
    for isi in halaman:
        badan = isi.split("</style>", 1)[1]
        utama = badan.split("<main", 1)[1]
        assert "<script" not in badan and ' style="' not in utama
        tanpa_svg = re.sub(r"<svg.*?</svg>", "", utama, flags=re.S)
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r'href="#[\w-]+"', "", tanpa_svg))
        for kelas in set(re.findall(r"funnel-[a-z-]+-st", badan)):
            assert f".{kelas}" in funnel_style.GAYA_FUNNEL, kelas


def test_markup_daftar_cek_dan_serah_login_memakai_kelas_terdefinisi(server):
    _k, daftar, _t = server.minta("/daftar?jalur=cek")
    _k, serah, _t = minta_mentah(server, "/masuk?lanjut=/cek-kemampuan/hasil")
    for isi in (daftar, serah):
        for kelas in set(re.findall(r"funnel-[a-z-]+-st", isi.split("</style>", 1)[1])):
            assert f".{kelas}" in funnel_style.GAYA_FUNNEL, kelas


def test_css_alur_memakai_token_tanpa_hex_important_dan_teks_minimal_14px():
    sumber = Path(funnel_style_alur.__file__).read_text()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
    assert "!important" not in funnel_style_alur.GAYA_ALUR
    import design_tokens as T
    ukuran = re.findall(r"font(?:-size\s*:\s*|\s*:\s*(?:\d{3}\s+)?)(\d*\.?\d+)(rem|px)\b", funnel_style_alur.GAYA_ALUR)
    px = [float(a) * (16 if s == "rem" else 1) for a, s in ukuran]
    assert px and min(px) >= 14.0, sorted(set(px))
    assert T.TARGET_SENTUH == "44px"
