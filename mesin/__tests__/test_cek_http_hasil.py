"""Rute cek gratis (Fase 2b) bagian hasil, tautan anak, sisi anak, dan redirect pasca-daftar.

Server HTTP sungguhan, data sintetis. Selesai = sesi ditutup lewat jalur database yang ada
(`cek_gratis_kit`), bukan lewat mock. Yang dibuktikan: hasil gratis tidak memuat data bagian
berbayar (diuji pada teks HTML), tautan hanya tampil di respons POST, anak tidak melihat skor.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import cek_http  # noqa: E402
import cek_pages  # noqa: E402
import funnel_style  # noqa: E402
import topics  # noqa: E402
import topik_awam  # noqa: E402
from cek_gratis_skor import KATEGORI  # noqa: E402
from cek_http_kit import (  # noqa: E402
    AKUN_A, AKUN_B, HASIL, MULAI, NAMA_A, POLA_TOKEN, TAUTAN, ambil_token, id_akun, jumlah,
    keluarga, minta_mentah, mulai_cek, selesaikan, server, tambah_anak, teks_tampak, token_form,
)

KATA_TERLARANG = ("diagnosis lengkap", "pasti akurat", "nilai pasti naik", "Rp200.000", "Rp151.000")
NAMA_TOPIK = tuple(topik_awam.nama(t) for t in ("berhitung-sekolah", "pengukuran", "geometri-datar"))
KATA_SKOR_ANAK = ("Skor keseluruhan", "dari 100", "Gambaran awal", "Kategori")


def _hasil_selesai(keluarga, **jawaban):
    sesi = mulai_cek(keluarga)
    selesaikan(keluarga, sesi, **jawaban)
    kode, isi, _t = minta_mentah(keluarga, HASIL, AKUN_A)
    assert kode == 200
    return isi


def _kerangka(isi: str) -> str:
    cocok = re.search(r'<section class="funnel-kunci-st" id="kerangka-terkunci".*?</section>', isi, re.S)
    assert cocok, "kerangka terkunci tidak ada"
    return cocok.group(0)


# --- hasil: belum selesai ---------------------------------------------------

def test_belum_selesai_html_tanpa_angka_skor_atau_ringkasan(keluarga):
    mulai_cek(keluarga)
    kode, isi, tajuk = minta_mentah(keluarga, HASIL, AKUN_A)
    teks = teks_tampak(isi)
    assert kode == 200 and "no-store" in tajuk.get("Cache-Control", "")
    assert "belum menyelesaikan" in teks and NAMA_A in teks
    assert not re.search(r"\d", teks)
    assert not any(k in teks for k in KATA_SKOR_ANAK + KATEGORI + NAMA_TOPIK)
    badan = isi.rsplit("</style>", 1)[1]
    assert "funnel-skor" not in badan and "kerangka-terkunci" not in badan
    assert cek_pages.COPY_TOMBOL_TAUTAN in isi and f'action="{TAUTAN}"' in isi


def test_get_hasil_tanpa_cek_dialihkan_ke_mulai(keluarga):
    kode, isi, tajuk = minta_mentah(keluarga, HASIL, AKUN_A)
    assert (kode, isi, tajuk["Location"]) == (303, "", MULAI)


def test_skor_tidak_disimpan_sebelum_sesi_selesai(keluarga):
    mulai_cek(keluarga)
    minta_mentah(keluarga, HASIL, AKUN_A)
    with keluarga.buka() as kon:
        assert tuple(kon.execute("SELECT skor, kategori, ringkasan FROM cek_gratis").fetchone()) == (None,) * 3


# --- hasil: selesai ---------------------------------------------------------

def test_selesai_memuat_skor_kategori_ringkasan_label_dan_batas(keluarga):
    isi = _hasil_selesai(keluarga, benar_per_topik={"berhitung-sekolah": 5, "pengukuran": 0, "geometri-datar": 5})
    teks = teks_tampak(isi)
    assert "10 dari 100" not in teks  # skor 10/15 = 67
    assert "67 dari 100" in teks and "Cukup baik" in teks
    assert cek_pages.COPY_LABEL_GAMBARAN in isi
    assert "Sudah kuat" in teks and "Perlu diperkuat" in teks
    assert topik_awam.nama("berhitung-sekolah") in teks and topik_awam.nama("pengukuran") in teks
    for batas in cek_pages.COPY_BATAS_HASIL:
        assert batas in isi
    assert 'href="/paket-coba"' in isi
    with keluarga.buka() as kon:
        assert kon.execute("SELECT skor FROM cek_gratis").fetchone()[0] == 67


def test_selesai_tanpa_angka_per_materi_kunci_jawaban_atau_peringkat(keluarga):
    isi = _hasil_selesai(keluarga, benar_per_topik={"berhitung-sekolah": 5, "pengukuran": 1, "geometri-datar": 3})
    teks = teks_tampak(isi)
    # urutan render: cincin skor (60 dari 100), kelas anak, lalu "9 dari 15 soal benar"; tanpa angka per materi
    assert re.findall(r"\d+", teks) == ["60", "100", "4", "9", "15"]
    assert "%" not in teks
    assert "9 dari 15 soal benar" in teks
    for kata in ("peringkat", "ranking", "Peringkat", "jawaban benar", "Rp"):
        assert kata not in teks
    assert not re.search(r"\bkunci\b", teks)
    # Semua kunci/jawaban soal berupa angka atau teks pendek; tidak ada digit lain di teks (di atas).
    assert not any(k in isi.lower() for k in KATA_TERLARANG)


def test_ringkasan_lama_tersimpan_tampil_dengan_nama_baru(keluarga):
    """Baris lama menyimpan nama resmi; halaman hasil wajib menampilkan nama awam."""
    _hasil_selesai(keluarga, benar_per_topik={"berhitung-sekolah": 5, "pengukuran": 0, "geometri-datar": 5})
    lama = {
        "kuat": [topics.ambil("berhitung-sekolah").nama],
        "perlu": [topics.ambil("geometri-datar").nama],
    }
    with keluarga.buka() as kon:
        kon.execute("UPDATE cek_gratis SET ringkasan = ?", (json.dumps(lama),))

    teks = teks_tampak(minta_mentah(keluarga, HASIL, AKUN_A)[1])
    assert topik_awam.nama("berhitung-sekolah") in teks
    assert topik_awam.nama("geometri-datar") in teks
    assert topics.ambil("berhitung-sekolah").nama not in teks
    assert topics.ambil("geometri-datar").nama not in teks


def test_selesai_tanpa_butir_ringkasan_pesan_netral(keluarga):
    isi = _hasil_selesai(keluarga, benar_per_topik={"berhitung-sekolah": 3, "pengukuran": 3, "geometri-datar": 3})
    assert cek_pages.COPY_RINGKASAN_KOSONG in isi


def test_kerangka_terkunci_identik_untuk_hasil_berbeda_dan_tanpa_data(server):
    kerangka = []
    for akun, pemilik, nama, per_topik in (
        (AKUN_A, "guru", "Anak Sintetis Alfa", {"berhitung-sekolah": 5, "pengukuran": 5, "geometri-datar": 5}),
        (AKUN_B, "guru-b", "Anak Sintetis Beta", {"berhitung-sekolah": 0, "pengukuran": 0, "geometri-datar": 1}),
    ):
        tambah_anak(server, nama, pemilik, 4)
        sesi = mulai_cek(server, akun)
        selesaikan(server, sesi, benar_per_topik=per_topik)
        kerangka.append(_kerangka(minta_mentah(server, HASIL, akun)[1]))
    assert kerangka[0] == kerangka[1]
    teks = teks_tampak("</style>" + kerangka[0])
    assert not re.search(r"\d", teks)
    assert not any(k in teks for k in NAMA_TOPIK + KATEGORI + ("Anak Sintetis",))


def test_hasil_selesai_mengalihkan_tombol_tautan_hilang(keluarga):
    isi = _hasil_selesai(keluarga, semua_benar=15)
    assert f'action="{TAUTAN}"' not in isi and "100" in teks_tampak(isi)


# --- tautan anak ------------------------------------------------------------

def _buat_tautan(keluarga, akun=AKUN_A, token=None):
    token = token or ambil_token(keluarga, akun, HASIL)
    return minta_mentah(keluarga, TAUTAN, akun, {"token": token})


def test_tautan_hanya_di_respons_post_dengan_qr_dan_tanpa_cache(keluarga):
    mulai_cek(keluarga)
    kode, isi, tajuk = _buat_tautan(keluarga)
    assert kode == 200 and "no-store" in tajuk["Cache-Control"] and tajuk["Referrer-Policy"] == "no-referrer"
    tautan = re.search(r'id="tautan-sesi" type="text" readonly value="([^"]+)"', isi).group(1)
    assert re.fullmatch(r"https?://[^/]+/mulai/[A-Za-z0-9_-]{43}", tautan)
    assert "<svg" in isi and "Location" not in tajuk
    token_anak = tautan.rsplit("/", 1)[1]
    for jalur in (HASIL, MULAI):
        assert token_anak not in minta_mentah(keluarga, jalur, AKUN_A)[1]
    assert "/mulai/" not in minta_mentah(keluarga, HASIL, AKUN_A)[1]


def test_tautan_ulang_mencabut_yang_lama_dan_satu_baris(keluarga):
    mulai_cek(keluarga)
    pertama = re.search(r"/mulai/([A-Za-z0-9_-]{43})", _buat_tautan(keluarga)[1]).group(1)
    kedua = re.search(r"/mulai/([A-Za-z0-9_-]{43})", _buat_tautan(keluarga)[1]).group(1)
    assert pertama != kedua and jumlah(keluarga, "tautan_sesi") == 1
    assert minta_mentah(keluarga, f"/mulai/{pertama}")[0] == 404
    assert minta_mentah(keluarga, f"/mulai/{kedua}")[0] == 200


def test_tautan_tanpa_cek_dialihkan_ke_mulai_tanpa_efek(keluarga):
    kode, _i, tajuk = minta_mentah(keluarga, TAUTAN, AKUN_A, {"token": token_form(AKUN_A, cek_http.AKSI_TAUTAN)})
    assert (kode, tajuk["Location"]) == (303, MULAI) and jumlah(keluarga, "tautan_sesi") == 0


def test_tautan_sesudah_selesai_dialihkan_ke_hasil_tanpa_tautan_baru(keluarga):
    sesi = mulai_cek(keluarga)
    token = ambil_token(keluarga, AKUN_A, HASIL)
    selesaikan(keluarga, sesi, semua_benar=15)
    kode, isi, tajuk = minta_mentah(keluarga, TAUTAN, AKUN_A, {"token": token})
    assert (kode, tajuk["Location"], isi) == (303, HASIL, "")
    assert jumlah(keluarga, "tautan_sesi") == 0


def test_tautan_akun_lain_tidak_menyentuh_cek_orang(keluarga):
    mulai_cek(keluarga)
    kode, _i, tajuk = minta_mentah(keluarga, TAUTAN, AKUN_B, {"token": token_form(AKUN_B, cek_http.AKSI_TAUTAN)})
    assert (kode, tajuk["Location"]) == (303, MULAI) and jumlah(keluarga, "tautan_sesi") == 0


@pytest.mark.parametrize("ekstra,kode_harap", [({"id_akun": "x"}, 400), ({"setuju": "1"}, 400), ({"sesi_id": "1"}, 400)])
def test_tautan_whitelist_form_tepat_token(keluarga, ekstra, kode_harap):
    mulai_cek(keluarga)
    data = {"token": token_form(AKUN_A, cek_http.AKSI_TAUTAN), **ekstra}
    assert minta_mentah(keluarga, TAUTAN, AKUN_A, data)[0] == kode_harap
    assert jumlah(keluarga, "tautan_sesi") == 0


@pytest.mark.parametrize("token", ["", "1.abc", "bukan"])
def test_tautan_token_salah_ditolak(keluarga, token):
    mulai_cek(keluarga)
    assert minta_mentah(keluarga, TAUTAN, AKUN_A, {"token": token})[0] == 403
    assert jumlah(keluarga, "tautan_sesi") == 0


def test_tautan_token_mulai_tidak_berlaku_untuk_tautan(keluarga):
    mulai_cek(keluarga)
    kode = minta_mentah(keluarga, TAUTAN, AKUN_A, {"token": token_form(AKUN_A, cek_http.AKSI_MULAI)})[0]
    assert kode == 403 and jumlah(keluarga, "tautan_sesi") == 0


# --- sisi anak --------------------------------------------------------------

def test_halaman_anak_lewat_tautan_tidak_menampilkan_skor_atau_kategori(keluarga):
    mulai_cek(keluarga)
    token = re.search(r"/mulai/([A-Za-z0-9_-]{43})", _buat_tautan(keluarga)[1]).group(1)
    kode, isi, _t = minta_mentah(keluarga, f"/mulai/{token}")
    assert kode == 200
    assert not any(k in isi for k in KATA_SKOR_ANAK + KATEGORI)


def test_murid_tidak_melihat_skor_atau_kategori_cek(keluarga):
    sesi = mulai_cek(keluarga)
    selesaikan(keluarga, sesi, semua_benar=15)
    minta_mentah(keluarga, HASIL, AKUN_A)  # skor tersimpan
    auth.tambah_akun("anak-alfa", "sandi-anak-alfa-123", "murid", siswa_id=keluarga.anak_a)
    for jalur in ("/murid", f"/murid/sesi/{sesi}"):
        kode, isi, _t = minta_mentah(keluarga, jalur, ("anak-alfa", "sandi-anak-alfa-123"))
        assert kode in (200, 303, 404), (jalur, kode)
        assert not any(k in isi for k in KATA_SKOR_ANAK + KATEGORI), jalur
    teks = teks_tampak(minta_mentah(keluarga, "/murid", ("anak-alfa", "sandi-anak-alfa-123"))[1])
    assert "100" not in teks.replace("100%", "")


def test_pengiriman_dari_hp_anak_tidak_menampilkan_skor_atau_kategori(keluarga):
    sesi = mulai_cek(keluarga)
    token = re.search(r"/mulai/([A-Za-z0-9_-]{43})", _buat_tautan(keluarga)[1]).group(1)
    # Protokol anak lama ditolak di sesi cek (whitelist ketat) dan tidak menyelesaikan sesi.
    lama = {"aksi": "selesai", "revisi_pekerjaan": "0", "flow_kosong": "1"}
    assert minta_mentah(keluarga, f"/mulai/{token}", data=lama)[0] == 400
    # Protokol anak cek: kumpulkan dari peta dengan revisi pekerjaan terkini.
    import student_submissions
    with keluarga.buka() as kon:
        revisi = student_submissions.revisi(kon, sesi)
    data = {"aksi": "kumpul", "revisi_pekerjaan": str(revisi)}
    kode, isi, _t = minta_mentah(keluarga, f"/mulai/{token}", data=data)
    assert kode == 200 and "Hore" in isi
    assert not any(k in teks_tampak(isi) for k in KATA_SKOR_ANAK + KATEGORI)


# --- markup & copy ----------------------------------------------------------

def test_markup_tanpa_hex_script_style_inline_dan_kelas_funnel_terdefinisi(keluarga):
    sesi = mulai_cek(keluarga)
    halaman = [minta_mentah(keluarga, HASIL, AKUN_A)[1], _buat_tautan(keluarga)[1]]
    selesaikan(keluarga, sesi, semua_benar=15)
    halaman.append(minta_mentah(keluarga, HASIL, AKUN_A)[1])
    for isi in halaman:
        badan = isi.rsplit("</style>", 1)[1]
        utama = badan.split("<main", 1)[1]  # topbar bersama bukan milik halaman cek
        assert "<script" not in badan and ' style="' not in utama
        tanpa_svg = re.sub(r"<svg.*?</svg>", "", utama, flags=re.S)  # QR memakai token warna bersama
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r'href="#[\w-]+"', "", tanpa_svg))
        for kelas in set(re.findall(r"funnel-[a-z-]+-st", badan)):
            assert f".{kelas}" in funnel_style.GAYA_FUNNEL, kelas


def test_css_cek_memakai_token_dan_tanpa_important():
    sumber = Path(funnel_style.__file__).read_text()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
    assert "!important" not in funnel_style.GAYA_FUNNEL
    for kelas in (".funnel-skor-st", ".funnel-skor-angka-st", ".funnel-kunci-st"):
        assert kelas in funnel_style.GAYA_FUNNEL


def test_copy_draf_bertanda_dan_tanpa_kata_terlarang():
    sumber = Path(cek_pages.__file__).read_text()
    assert sumber.count("# DRAF: teks final menunggu persetujuan Pemilik") >= 10
    semua = " ".join(str(v) for v in vars(cek_pages).values() if isinstance(v, (str, tuple)))
    assert not any(k in semua.lower() for k in KATA_TERLARANG)
    assert not re.search(r"Rp\s?\d", semua)


# --- redirect pasca-daftar --------------------------------------------------

def _daftar(server, jalur_cek: bool, **tambah):
    _k, isi, _t = server.minta("/daftar?jalur=cek" if jalur_cek else "/daftar")
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = dict(nama="ortu-funnel", sandi="sandi-form-sintetis", setuju="1", token_form=token,
                nama_anak="Profil Sintetis", kelas_sekolah="4", **tambah)
    if jalur_cek:
        data.update(jalur="cek", wa="0812-3456-7890")
    return minta_mentah(server, "/daftar", data=data)


@pytest.fixture()
def server_daftar(server):
    import admin_registration
    import database
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    admin_registration.migrasikan_profil_registrasi(database.BAWAAN)
    return server


def test_daftar_jalur_cek_diarahkan_ke_mulai_dan_alur_penuh_dengan_cookie(server_daftar):
    kode, _i, tajuk = _daftar(server_daftar, True)
    assert (kode, tajuk["Location"]) == (303, MULAI)
    cookie = tajuk["Set-Cookie"].split(";")[0]
    _k, isi, _t = server_daftar.minta(MULAI, cookie=cookie)
    assert "Profil Sintetis" in isi and 'name="setuju"' in isi
    token = POLA_TOKEN.search(isi).group(1)
    kode, isi, tajuk = minta_mentah(server_daftar, MULAI, data={"token": token, "setuju": "1", "cara": "hp_anak"},
                                    headers={"Cookie": cookie})
    assert kode == 200 and "<svg" in isi and "Location" not in tajuk
    assert jumlah(server_daftar, "cek_gratis") == 1


def test_daftar_jalur_biasa_tujuan_tidak_berubah(server_daftar):
    kode, _i, tajuk = _daftar(server_daftar, False)
    assert kode == 303 and tajuk["Location"].startswith("/anak/") and "cek-kemampuan" not in tajuk["Location"]


def test_daftar_jalur_cek_tetap_lewat_gerbang_persetujuan(server_daftar, monkeypatch):
    import policy_http
    monkeypatch.setattr(policy_http, "perlu", lambda p: True)
    kode, _i, tajuk = _daftar(server_daftar, True)
    assert (kode, tajuk["Location"]) == (303, "/persetujuan")
