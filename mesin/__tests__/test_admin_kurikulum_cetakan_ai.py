"""Draf AI cetakan di `/admin/kurikulum/cetakan/draf-ai` (C3): tombol, kuota, muatan, validasi mesin, guard POST.

Data SINTETIS, kunci API sintetis, urlopen palsu (tanpa jaringan nyata). DB cetakan dan DB kuota di tmp_path.
"""
from __future__ import annotations

import logging
import re
import socket
import sqlite3
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_kurikulum_cetakan_ai_http as http_ai  # noqa: E402
import admin_kurikulum_cetakan_ai_pages as ui_ai  # noqa: E402
import admin_kurikulum_cetakan_pages as ui  # noqa: E402
import ai_policy  # noqa: E402
import ai_service  # noqa: E402
import ai_store  # noqa: E402
import cetakan_ai  # noqa: E402
import cetakan_ai_store as kuota  # noqa: E402
import cetakan_store as store  # noqa: E402
import kurikulum_kelas as kk  # noqa: E402
import kurikulum_kelas_hitung as hitung  # noqa: E402
from admin_transfer_kit import LINTAS_SITUS, id_admin, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from cetakan_admin_kit import BAB_ADA, BAB_BELUM, TAK_ADA, buat_langsung, formulir, isi_tak_layak, kirim, semua_action  # noqa: E402,F401
from cetakan_ai_kit import (  # noqa: E402
    KUNCI_SINTETIS, badan_chat, isi_balasan, kandidat_sah, kandidat_tak_layak, pasang_api, siapkan_env,
)
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import jam, keluarga, minta_mentah, server, tertutup  # noqa: E402,F401

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
POLA_PERMINTAAN = re.compile(r"/admin/kurikulum/cetakan\?kelas=(\d+)&bab=(\d+)&permintaan=(\d+)$")
SAMPAH = b"bukan sqlite sama sekali"


@pytest.fixture(autouse=True)
def _lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_BERKAS_DB, str(tmp_path / "cetakan.db"))
    monkeypatch.setenv(kuota.ENV_BERKAS_DB, str(tmp_path / "cetakan_ai.db"))
    siapkan_env(monkeypatch)
    store.bersihkan_cache()
    yield
    store.bersihkan_cache()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


@pytest.fixture()
def api(monkeypatch):
    """urlopen palsu yang menjawab dua kandidat sah."""
    return pasang_api(monkeypatch, respons=isi_balasan([kandidat_sah(), kandidat_sah(judul="Penjumlahan kedua")]))


def _db_kuota() -> Path:
    return kuota._path_db(None)


def _alamat_daftar(bab=BAB_ADA, tambah="") -> str:
    return "%s?kelas=%d&bab=%d%s" % (ui.RUTE, *bab, tambah)


def _badan(isi: str) -> str:
    return isi.rsplit("</style>", 1)[-1]


def _kirim_ai(server, cookie, bab="3/1", revisi=0, **kw):
    return kirim(server, cookie, ui_ai.AKSI_DRAF_AI, bab, revisi, {}, jalur=ui_ai.RUTE_DRAF_AI, **kw)


def _id_permintaan(tajuk) -> int:
    return int(POLA_PERMINTAAN.search(tajuk["Location"]).group(3))


def _semua_draf():
    return store.daftar()


def _stempel_kuota():
    if not _db_kuota().exists():
        return ()
    with sqlite3.connect(_db_kuota()) as kon:
        return tuple(kon.execute("SELECT * FROM permintaan ORDER BY id").fetchall())


def _stempel_cetakan():
    path = store._path_db(None)
    if not path.exists():
        return ()
    with sqlite3.connect(path) as kon:
        return tuple(kon.execute("SELECT * FROM cetakan ORDER BY id").fetchall())


def _isi_pengaturan_ai(**ganti):
    with ai_store.buka(ai_service.path_store()) as kon:
        utama, _ = ai_store.konfigurasi(kon)
    nilai = {"dihentikan": 0, "request_akun_harian": 20, "uji_harian": 3, "uji_cooldown_detik": 600}
    for fitur in ai_policy.FITUR:
        nilai["aktif_%s" % fitur] = 1
    for fitur, (harian, bulanan) in ai_policy.DEFAULT_LIMIT.items():
        nilai["harian_%s" % fitur] = harian
        nilai["bulanan_%s" % fitur] = bulanan
    nilai.update(ganti)
    ai_store.ubah(ai_service.path_store(), nilai, "admin", revisi=utama["revisi"])


# --- tombol ----------------------------------------------------------------------------------

def test_tombol_tampil_dengan_kunci_dan_kuota_serta_isi_form_persis(tertutup, admin):
    kode, isi, tajuk = minta_admin(tertutup, _alamat_daftar(), admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store" and "<script" not in _badan(isi)
    assert ui_ai.TOMBOL_DRAF_AI in isi and "Sisa kuota hari ini: 20 dari 20." in isi
    field = formulir(isi, ui_ai.RUTE_DRAF_AI)
    assert set(field) == {"csrf", "tinjauan", "reauth"} and field["reauth"] == ""
    assert KUNCI_SINTETIS not in isi and SANDI_ADMIN not in isi and not _db_kuota().exists()


@pytest.mark.parametrize("bab", [BAB_ADA, BAB_BELUM])
def test_tombol_tampil_di_halaman_bab_mana_pun_yang_valid(tertutup, admin, bab):
    assert ui_ai.RUTE_DRAF_AI in minta_admin(tertutup, _alamat_daftar(bab), admin)[1]


@pytest.mark.parametrize("kunci", ["", "   "])
def test_tanpa_kunci_tombol_tak_tampil_dan_tabel_tanpa_tautan(tertutup, admin, monkeypatch, kunci, bab_sebagian_simulasi):
    siapkan_env(monkeypatch, kunci=kunci)
    isi = minta_admin(tertutup, _alamat_daftar(), admin)[1]
    assert ui_ai.RUTE_DRAF_AI not in isi and ui_ai.TOMBOL_DRAF_AI not in isi and "Sisa kuota" not in isi
    assert "kuota" not in _badan(isi).lower()
    assert ui_ai.LABEL_TAUTAN_TABEL not in minta_admin(tertutup, "/admin/kurikulum", admin)[1]


def test_tanpa_kunci_post_ditolak_503_tanpa_urlopen_reservasi_dan_cetakan(tertutup, admin, monkeypatch, api):
    siapkan_env(monkeypatch, kunci="")
    kode, isi, _t = _kirim_ai(tertutup, admin)
    assert kode == 503 and ui_ai.COPY_AI_TIDAK_AKTIF in isi
    assert api.panggilan == [] and not _db_kuota().exists() and _semua_draf() == ()


def test_kuota_habis_tombol_hilang_dengan_catatan_dan_tabel_tanpa_tautan(tertutup, admin, bab_sebagian_simulasi):
    for _ in range(kuota.BATAS_HARIAN):
        kuota.reservasi(3, 1, "akun-sintetis")
    isi = minta_admin(tertutup, _alamat_daftar(), admin)[1]
    assert ui_ai.RUTE_DRAF_AI not in isi and ui_ai.COPY_KUOTA_HABIS in isi and "Sisa kuota hari ini" not in isi
    assert ui_ai.LABEL_TAUTAN_TABEL not in minta_admin(tertutup, "/admin/kurikulum", admin)[1]


def test_sesi_tanpa_kuki_baca_saja_tanpa_form_draf_ai(tertutup):
    kode, isi, _t = minta_mentah(tertutup, _alamat_daftar(), AKUN_ADMIN)
    assert kode == 200 and ui_ai.RUTE_DRAF_AI not in isi and ui_ai.TOMBOL_DRAF_AI not in isi


def test_sisa_kuota_berkurang_setelah_permintaan_dan_tampil_19(tertutup, admin, api):
    assert _kirim_ai(tertutup, admin)[0] == 303
    assert "Sisa kuota hari ini: 19 dari 20." in minta_admin(tertutup, _alamat_daftar(), admin)[1]


# --- alur sukses -----------------------------------------------------------------------------

def test_alur_lengkap_lewat_form_halaman_prg_ringkasan_dan_draf_ai(tertutup, admin, api):
    form = formulir(minta_admin(tertutup, _alamat_daftar(), admin)[1], ui_ai.RUTE_DRAF_AI)
    form["reauth"] = SANDI_ADMIN
    kode, _isi, tajuk = minta_admin(tertutup, ui_ai.RUTE_DRAF_AI, admin, form)
    assert kode == 303 and POLA_PERMINTAAN.search(tajuk["Location"]).groups() == ("3", "1", "1")
    assert tajuk["Location"] == ui_ai.url_daftar_hasil(3, 1, 1) and len(api.panggilan) == 1
    draf = _semua_draf()
    assert len(draf) == 2 and {d.cetakan.judul for d in draf} == {kandidat_sah()["judul"], "Penjumlahan kedua"}
    assert all(d.sumber == "ai" and d.status == "draf" and (d.kelas, d.bab) == BAB_ADA and d.revisi == 1 for d in draf)
    riwayat = store.riwayat(draf[0].id)
    assert [(r.aksi, r.actor_id) for r in riwayat] == [("buat", id_admin())]
    kode, halaman, _t = minta_admin(tertutup, tajuk["Location"], admin)
    assert kode == 200 and "AI membuat 2 draf:" in halaman and "Sisa kuota hari ini: 19 dari 20." in halaman
    for d in draf:
        assert 'href="%s"' % ui.url_periksa(d.id).replace("&", "&amp;") in halaman
        assert d.cetakan.judul in halaman and "Draf AI" in minta_admin(tertutup, ui.url_periksa(d.id), admin)[1]


def test_permintaan_tercatat_di_db_kuota_dengan_hasil(tertutup, admin, api):
    _kirim_ai(tertutup, admin)
    p = kuota.ambil(1)
    assert (p.status, p.jumlah_draf, p.kelas, p.bab, p.actor_id, p.ditolak) == ("selesai", 2, 3, 1, id_admin(), ())
    assert p.draf == tuple(d.id for d in _semua_draf())


def test_draf_ai_tak_pernah_aktif_otomatis_dan_tak_masuk_tabel_buat_soal(tertutup, admin, api):
    _kirim_ai(tertutup, admin)
    assert store.aktif_untuk_bab(*BAB_ADA) == () and {d.status for d in _semua_draf()} == {"draf"}


# --- muatan privat ---------------------------------------------------------------------------

def test_muatan_terkirim_persis_muatan_bab_dan_tanpa_data_akun_atau_anak(tertutup, admin, api):
    assert _kirim_ai(tertutup, admin)[0] == 303
    req, timeout = api.panggilan[0]
    badan = api.badan()
    bab = hitung.cari_bab(*BAB_ADA)[1]
    assert badan["messages"] == cetakan_ai.muatan(BAB_ADA[0], bab)
    assert set(badan) == {"model", "messages", "temperature", "max_tokens", "response_format", "thinking"} and timeout == 30
    assert badan["thinking"] == {"type": "disabled"}
    mentah = req.data.decode("utf-8").lower()
    penting = [id_admin().lower(), AKUN_ADMIN[0].lower(), SANDI_ADMIN.lower(), "osn_sesi", "csrf", "tinjauan",
               "reauth", "cookie", "akun_", "sesi", KUNCI_SINTETIS]
    assert not [kata for kata in penting if kata in mentah]
    assert req.get_header("Authorization") == "Bearer " + KUNCI_SINTETIS and req.full_url.startswith(
        "https://api.deepseek.com/")
    assert "Cookie" not in dict(req.header_items()) and not req.has_header("Cookie")


def test_kunci_tak_muncul_di_html_atau_log_pada_sukses_dan_galat(tertutup, admin, monkeypatch, caplog):
    with caplog.at_level(logging.DEBUG):
        api = pasang_api(monkeypatch, galat=urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions", 401, "Unauthorized", {}, None))
        kode, isi, tajuk = _kirim_ai(tertutup, admin)
        halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert kode == 303 and len(api.panggilan) == 1
    for teks in (isi, halaman, caplog.text, str(tajuk)):
        assert KUNCI_SINTETIS not in teks and "Bearer" not in teks and "api.deepseek.com" not in teks


# --- validasi mesin atas kandidat ------------------------------------------------------------

def test_kelas_dan_bab_dipaksa_dari_tinjauan_bukan_dari_ai(tertutup, admin, monkeypatch):
    pasang_api(monkeypatch, respons=isi_balasan([kandidat_sah(kelas=6, bab=1), kandidat_sah(kelas=1, bab=1, judul="B")]))
    assert _kirim_ai(tertutup, admin, bab="%d/%d" % BAB_BELUM)[0] == 303
    assert {(d.kelas, d.bab) for d in _semua_draf()} == {BAB_BELUM} and len(_semua_draf()) == 2


def test_kandidat_tanpa_kelas_bab_tetap_sah_karena_diisi_dari_tinjauan(tertutup, admin, monkeypatch):
    kandidat = kandidat_sah()
    del kandidat["kelas"], kandidat["bab"]
    pasang_api(monkeypatch, respons=isi_balasan([kandidat]))
    assert _kirim_ai(tertutup, admin)[0] == 303 and [(d.kelas, d.bab) for d in _semua_draf()] == [BAB_ADA]


BERBAHAYA = [
    kandidat_sah(kunci="__import__('os').system('id')"),
    kandidat_sah(kunci="a ** 999999"),
    kandidat_sah(kunci="a + b", syarat=["a.__class__ == 1"]),
    kandidat_sah(kunci="(lambda: 1)()"),
    kandidat_sah(judul="<script>alert(1)</script>"),
    kandidat_sah(teks="{nama} <img src=x onerror=alert(1)> {a} {b}"),
]


def test_kandidat_berbahaya_ditolak_dan_alasan_tampil_ter_escape(tertutup, admin, monkeypatch):
    for urutan in range(0, len(BERBAHAYA), 3):
        pasang_api(monkeypatch, respons=isi_balasan(BERBAHAYA[urutan:urutan + 3]))
        kode, _i, tajuk = _kirim_ai(tertutup, admin)
        halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
        assert kode == 303 and "Ditolak mesin:" in halaman and COPY_KOSONG in halaman
        assert "<script>alert" not in _badan(halaman) and "<img src=x" not in halaman and "onerror=alert" not in _badan(halaman)
    assert _semua_draf() == ()


COPY_KOSONG = ui_ai.COPY_KOSONG


def test_satu_sah_dua_buruk_hanya_yang_sah_tersimpan_dan_penolakan_bernomor(tertutup, admin, monkeypatch):
    pasang_api(monkeypatch, respons=isi_balasan([BERBAHAYA[0], kandidat_sah(judul="Yang sah"), BERBAHAYA[1]]))
    tajuk = _kirim_ai(tertutup, admin)[2]
    assert [d.cetakan.judul for d in _semua_draf()] == ["Yang sah"]
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "AI membuat 1 draf:" in halaman and "Cetakan 1:" in halaman and "Cetakan 3:" in halaman
    assert kuota.ambil(1).ditolak[0].startswith("Cetakan 1:") and len(kuota.ambil(1).ditolak) == 2


def test_kandidat_tak_layak_ditolak_dengan_alasan_kelayakan(tertutup, admin, monkeypatch):
    pasang_api(monkeypatch, respons=isi_balasan([kandidat_tak_layak()]))
    tajuk = _kirim_ai(tertutup, admin)[2]
    assert _semua_draf() == ()
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "uji kelayakan gagal" in halaman and "25 soal unik" in halaman


@pytest.mark.parametrize("aneh", ["teks saja", 5, None, [1], {"judul": 1}, {"variabel": []}, {"kunci": 5},
                                  kandidat_sah(variabel={"a": "x"}), kandidat_sah(nama="ya"),
                                  kandidat_sah(syarat="a < 1"), kandidat_sah(judul=["x"]),
                                  kandidat_sah(kunci=5), kandidat_sah(kunci=None), kandidat_sah(kunci=["a"]),
                                  kandidat_sah(syarat=[5]), kandidat_sah(syarat=[{}]), kandidat_sah(syarat=None),
                                  kandidat_sah(pembahasan=5), kandidat_sah(pembahasan=None), kandidat_sah(teks=None),
                                  kandidat_sah(teks=5), kandidat_sah(judul=5), kandidat_sah(variabel=None),
                                  kandidat_sah(variabel={"a": None}), kandidat_sah(variabel={"a": [1.5, 2]}),
                                  kandidat_sah(variabel={"a": [[1], 2]}), kandidat_sah(nama=[])])
def test_kandidat_berbentuk_aneh_tidak_membuat_500_dan_tidak_tersimpan(tertutup, admin, monkeypatch, aneh):
    pasang_api(monkeypatch, respons=isi_balasan([aneh]))
    kode, _i, tajuk = _kirim_ai(tertutup, admin)
    assert kode == 303 and _semua_draf() == () and kuota.ambil(_id_permintaan(tajuk)).status == "selesai"


def test_kandidat_lebih_dari_tiga_hanya_tiga_diproses(tertutup, admin, monkeypatch):
    pasang_api(monkeypatch, respons=isi_balasan([kandidat_sah(judul="J%d" % i) for i in range(6)]))
    assert _kirim_ai(tertutup, admin)[0] == 303 and len(_semua_draf()) == 3


# --- kegagalan AI ----------------------------------------------------------------------------

GAGAL = {
    "http-500": dict(galat=urllib.error.HTTPError("https://x.invalid", 500, "e", {}, None)),
    "urlerror": dict(galat=urllib.error.URLError("ditolak")),
    "timeout": dict(galat=socket.timeout("lama")),
    "bukan-json": dict(respons=badan_chat("bukan json")),
    "terlalu-besar": dict(respons=b"x" * 9000),
    "tanpa-cetakan": dict(respons=badan_chat("{}")),
}


@pytest.mark.parametrize("nama", sorted(GAGAL))
def test_kegagalan_ai_prg_ke_ringkasan_gagal_slot_terpakai_tanpa_draf(tertutup, admin, monkeypatch, nama):
    pasang_api(monkeypatch, **GAGAL[nama])
    kode, _i, tajuk = _kirim_ai(tertutup, admin)
    assert kode == 303 and POLA_PERMINTAAN.search(tajuk["Location"]) and _semua_draf() == ()
    p = kuota.ambil(1)
    assert p.status == "gagal" and p.jumlah_draf == 0 and len(p.ditolak) == 1
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "AI belum berhasil membuat draf kali ini" in halaman and "Slot kuota tetap terpakai" in halaman
    assert "Sisa kuota hari ini: 19 dari 20." in halaman and KUNCI_SINTETIS not in halaman


def test_kegagalan_tak_terduga_dicatat_gagal_lalu_diteruskan(tertutup, admin, monkeypatch):
    def meledak(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(cetakan_ai, "minta_kandidat", meledak)
    kode = _kirim_ai(tertutup, admin)[0]
    assert kode >= 500 and kuota.ambil(1).status == "gagal"


def test_db_cetakan_rusak_saat_simpan_503_dan_permintaan_dicatat_gagal(tertutup, admin, api):
    store._path_db(None).write_bytes(SAMPAH)
    store.bersihkan_cache()
    kode, isi, _t = _kirim_ai(tertutup, admin)
    assert kode == 503 and str(Path(store._path_db(None)).parent) not in isi
    p = kuota.ambil(1)
    assert p.status == "gagal" and "Database cetakan tidak dapat ditulis." in p.ditolak
    assert store._path_db(None).read_bytes() == SAMPAH


# --- kuota -----------------------------------------------------------------------------------

def test_kuota_dua_puluh_permintaan_lolos_dan_ke_21_ditolak_429_tanpa_urlopen(tertutup, admin, api):
    for _ in range(kuota.BATAS_HARIAN):
        assert _kirim_ai(tertutup, admin)[0] == 303
    assert len(api.panggilan) == 20
    kode, isi, _t = _kirim_ai(tertutup, admin)
    assert kode == 429 and ui_ai.COPY_KUOTA_HABIS_POST in isi
    assert len(api.panggilan) == 20 and len(_stempel_kuota()) == 20
    assert ui_ai.RUTE_DRAF_AI not in minta_admin(tertutup, _alamat_daftar(), admin)[1]


def test_slot_terpakai_walau_ai_gagal_dan_kuota_habis_oleh_kegagalan(tertutup, admin, monkeypatch):
    api = pasang_api(monkeypatch, galat=urllib.error.URLError("mati"))
    for _ in range(kuota.BATAS_HARIAN):
        assert _kirim_ai(tertutup, admin)[0] == 303
    assert _kirim_ai(tertutup, admin)[0] == 429 and len(api.panggilan) == 20


def test_kuota_global_dipakai_bersama_walau_bab_berbeda(tertutup, admin, api):
    for _ in range(kuota.BATAS_HARIAN):
        kuota.reservasi(2, 3, "akun-lain")
    assert _kirim_ai(tertutup, admin)[0] == 429 and api.panggilan == []


@pytest.mark.parametrize("rusak", ["sampah", "versi", "asing"])
def test_db_kuota_rusak_fail_closed_tombol_hilang_post_503_tanpa_urlopen(tertutup, admin, api, rusak, bab_sebagian_simulasi):
    if rusak == "sampah":
        _db_kuota().write_bytes(SAMPAH)
    else:
        with sqlite3.connect(_db_kuota()) as kon:
            kon.execute("PRAGMA user_version = %d" % (99 if rusak == "versi" else 0))
            if rusak == "asing":
                kon.execute("CREATE TABLE bukan_milik_kita(x INTEGER)")
    sebelum = _db_kuota().read_bytes()
    halaman = minta_admin(tertutup, _alamat_daftar(), admin)
    assert halaman[0] == 200 and ui_ai.RUTE_DRAF_AI not in halaman[1] and ui_ai.LABEL_TAUTAN_TABEL not in (
        minta_admin(tertutup, "/admin/kurikulum", admin)[1])
    kode, isi, _t = _kirim_ai(tertutup, admin)
    assert kode == 503 and ui_ai.COPY_KUOTA_TIDAK_SIAP in isi and str(_db_kuota().parent) not in isi
    assert api.panggilan == [] and _db_kuota().read_bytes() == sebelum and _semua_draf() == ()


# --- independen dari /admin/ai ---------------------------------------------------------------

def _dump_ai() -> bytes:
    with sqlite3.connect(ai_service.path_store()) as kon:
        return "\n".join(kon.iterdump()).encode()


def test_tombol_dan_post_tetap_hidup_saat_ai_lama_dihentikan_dan_semua_fitur_mati(tertutup, admin, api, monkeypatch,
                                                                                    bab_sebagian_simulasi):
    _isi_pengaturan_ai(dihentikan=1, **{"aktif_%s" % f: 0 for f in ai_policy.FITUR},
                       **{"harian_%s" % f: 0 for f in ("global", *ai_policy.FITUR)})
    monkeypatch.setenv("AI_NONAKTIF", "1")
    assert ai_service.status_fitur("cerita")[0] is False  # AI lama benar-benar mati
    sebelum = _dump_ai()
    halaman = minta_admin(tertutup, _alamat_daftar(), admin)[1]
    assert ui_ai.TOMBOL_DRAF_AI in halaman and ui_ai.LABEL_TAUTAN_TABEL in minta_admin(tertutup, "/admin/kurikulum", admin)[1]
    assert _kirim_ai(tertutup, admin)[0] == 303 and len(api.panggilan) == 1 and len(_semua_draf()) == 2
    assert _dump_ai() == sebelum  # ledger /admin/ai tak disentuh (tak tercatat di sana)


def test_pagu_ai_lama_habis_tak_membatasi_draf_cetakan(tertutup, admin, api):
    _isi_pengaturan_ai(request_akun_harian=0, uji_harian=0)
    assert _kirim_ai(tertutup, admin)[0] == 303 and len(api.panggilan) == 1


# --- guard POST ------------------------------------------------------------------------------

@pytest.mark.parametrize("kasus", ["tanpa_csrf", "csrf_salah", "tinjauan_palsu", "tanpa_tinjauan",
                                   "reauth_salah", "tanpa_reauth", "reauth_kosong"])
def test_token_cacat_403_tanpa_reservasi_urlopen_atau_cetakan(tertutup, admin, api, kasus):
    ganti, hapus = {
        "tanpa_csrf": ({}, ("csrf",)), "csrf_salah": ({"csrf": "rusak"}, ()),
        "tinjauan_palsu": ({"tinjauan": "palsu.palsu"}, ()), "tanpa_tinjauan": ({}, ("tinjauan",)),
        "reauth_salah": ({"reauth": "salah-sandi"}, ()), "tanpa_reauth": ({}, ("reauth",)),
        "reauth_kosong": ({"reauth": ""}, ()),
    }[kasus]
    assert _kirim_ai(tertutup, admin, ganti=ganti, hapus=hapus)[0] == 403
    assert api.panggilan == [] and not _db_kuota().exists() and _stempel_cetakan() == ()


def test_tinjauan_aksi_lain_lintas_situs_dan_sesi_lain_ditolak(tertutup, admin, api):
    for percobaan in (dict(token_aksi=ui.AKSI_BUAT), dict(token_aksi="ubah_sakelar"), dict(headers=LINTAS_SITUS)):
        assert _kirim_ai(tertutup, admin, **percobaan)[0] == 403
    from cetakan_admin_kit import token
    asing = token("sesi-lain-sintetis", ui_ai.AKSI_DRAF_AI, "3/1", 0)
    assert minta_admin(tertutup, ui_ai.RUTE_DRAF_AI, admin, asing)[0] == 403
    assert api.panggilan == [] and not _db_kuota().exists()


@pytest.mark.parametrize("ekstra", [{"kelas": "6", "bab": "1"}, {"id": "1"}, {"target_id": "6/1"}, {"x": "1"}])
def test_field_asing_ditolak_400_dan_target_di_form_diabaikan(tertutup, admin, api, ekstra):
    assert _kirim_ai(tertutup, admin, ekstra=ekstra)[0] == 400
    assert api.panggilan == [] and not _db_kuota().exists() and _semua_draf() == ()


def test_batas_field_tiga_ditolak_sebelum_token_diperiksa(tertutup, admin, api):
    assert http_ai.MAKS_FIELD_DRAF_AI == 3
    assert _kirim_ai(tertutup, admin, ganti={"csrf": "rusak"})[0] == 403
    assert _kirim_ai(tertutup, admin, ganti={"csrf": "rusak"}, ekstra={"tambahan": "x"})[0] == 400
    assert api.panggilan == [] and not _db_kuota().exists()


@pytest.mark.parametrize("target,revisi", [("9/1", 0), ("3/99", 0), ("3", 0), ("abc/def", 0), ("3/1/2", 0),
                                           ("03/1", 0), ("3/1", 1), ("3/1", 5), ("-3/1", 0)])
def test_target_tinjauan_tak_sah_400_tanpa_reservasi(tertutup, admin, api, target, revisi):
    assert _kirim_ai(tertutup, admin, bab=target, revisi=revisi)[0] == 400
    assert api.panggilan == [] and not _db_kuota().exists()


@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_reservasi_atau_urlopen(tertutup, admin, api, akun):
    acuan = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    from cetakan_admin_kit import token
    for data in ({}, token(admin, ui_ai.AKSI_DRAF_AI, "3/1", 0)):
        assert minta_mentah(tertutup, ui_ai.RUTE_DRAF_AI, akun, data)[:2] == acuan[:2]
    assert acuan[0] == 404 and api.panggilan == [] and not _db_kuota().exists() and _stempel_cetakan() == ()


def test_get_ke_rute_post_draf_ai_404(tertutup, admin):
    assert minta_admin(tertutup, ui_ai.RUTE_DRAF_AI, admin)[:2] == minta_admin(tertutup, TAK_ADA, admin)[:2]


# --- PRG dan ringkasan -----------------------------------------------------------------------

def test_sukses_redirect_303_ke_halaman_bab_dengan_permintaan(tertutup, admin, api):
    kode, isi, tajuk = _kirim_ai(tertutup, admin, bab="%d/%d" % BAB_BELUM)
    assert kode == 303 and isi == "" and tajuk["Location"] == "/admin/kurikulum/cetakan?kelas=2&bab=3&permintaan=1"
    assert tajuk["Cache-Control"] == "no-store"


def test_ringkasan_hanya_tampil_bila_kelas_bab_permintaan_cocok(tertutup, admin, api):
    tajuk = _kirim_ai(tertutup, admin)[2]
    assert "AI membuat 2 draf:" in minta_admin(tertutup, tajuk["Location"], admin)[1]
    lain = _alamat_daftar(BAB_BELUM, "&permintaan=1")
    kode, isi, _t = minta_admin(tertutup, lain, admin)
    assert kode == 200 and "AI membuat" not in isi and "Ditolak mesin" not in isi
    kode, isi, _t = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=777"), admin)
    assert kode == 200 and "AI membuat" not in isi


@pytest.mark.parametrize("nilai", ["0", "01", "abc", "-1", "", "1.5", "%EF%BC%91", "1&permintaan=1"])
def test_parameter_permintaan_tak_sah_404_identik(tertutup, admin, nilai):
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=" + nilai), admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_alasan_penolakan_dari_db_ter_escape_di_halaman(tertutup, admin):
    id_p = kuota.reservasi(3, 1, id_admin())
    kuota.selesaikan(id_p, "selesai", 0, ditolak=["<script>alert(1)</script>", "\"><img src=x onerror=1>"])
    halaman = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=%d" % id_p), admin)[1]
    assert "<script>alert(1)" not in _badan(halaman) and "<img src=x" not in halaman
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in halaman


def test_alasan_gagal_dari_db_ter_escape_di_halaman(tertutup, admin):
    id_p = kuota.reservasi(3, 1, id_admin())
    kuota.selesaikan(id_p, "gagal", 0, ditolak=["<script>alert(2)</script>"])
    halaman = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=%d" % id_p), admin)[1]
    assert "<script>alert(2)" not in _badan(halaman) and "&lt;script&gt;alert(2)&lt;/script&gt;" in halaman


def test_permintaan_berjalan_ditampilkan_belum_selesai_dan_status_gagal_dengan_alasan(tertutup, admin):
    berjalan = kuota.reservasi(3, 1, id_admin())
    assert ui_ai.COPY_BELUM_SELESAI in minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=%d" % berjalan), admin)[1]
    gagal = kuota.reservasi(3, 1, id_admin())
    kuota.selesaikan(gagal, "gagal", 0, ditolak=["Layanan AI menolak permintaan (kode 500)."])
    halaman = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=%d" % gagal), admin)[1]
    assert "kode 500" in halaman and "AI belum berhasil" in halaman


def test_tautan_draf_hanya_untuk_draf_yang_ada_di_bab_itu(tertutup, admin):
    ada = buat_langsung(sumber="ai")
    id_p = kuota.reservasi(3, 1, id_admin())
    kuota.selesaikan(id_p, "selesai", 2, draf=[ada.id, 999])
    halaman = minta_admin(tertutup, _alamat_daftar(BAB_ADA, "&permintaan=%d" % id_p), admin)[1]
    assert halaman.count("/admin/kurikulum/cetakan/periksa?id=") >= 1
    assert "id=999" not in halaman and 'href="%s"' % ui.url_periksa(ada.id) in halaman


# --- tabel Kurikulum Merdeka -----------------------------------------------------------------

BAB_DULU_SEBAGIAN = {(1, 4), (2, 3), (2, 6), (5, 6), (5, 8), (6, 1), (6, 3)}


@pytest.fixture
def bab_sebagian_simulasi(monkeypatch):
    """Data nyata kini 40 bab "ada" (22 Nov 2026), jadi tautan draf AI di bab "sebagian" diuji dengan keadaan
    yang disimulasikan: tujuh bab terakhir hanya dengan pelatih lamanya yang berkecocokan "sebagian"."""
    from dataclasses import replace
    kelas = tuple(
        replace(k, bab=tuple(
            replace(b, pelatih=tuple(p for p in b.pelatih if p[2] != "ada")) if (k.kelas, b.nomor) in BAB_DULU_SEBAGIAN
            else b for b in k.bab))
        for k in kk.KELAS)
    monkeypatch.setattr(kk, "KELAS", kelas)

def _bab_belum_atau_sebagian() -> int:
    return sum(1 for k in kk.KELAS for b in hitung.ringkasan_kelas(k, None)
               if b.status in (hitung.STATUS_BELUM, hitung.STATUS_SEBAGIAN))


def test_tabel_menautkan_draf_ai_hanya_di_bab_belum_atau_sebagian(tertutup, admin, bab_sebagian_simulasi):
    isi = minta_admin(tertutup, "/admin/kurikulum", admin)[1]
    jumlah = _bab_belum_atau_sebagian()
    assert 0 < jumlah < sum(len(k.bab) for k in kk.KELAS)
    assert isi.count(">%s</a>" % ui_ai.LABEL_TAUTAN_TABEL) == jumlah
    assert isi.count(">Kelola cetakan</a>") == sum(len(k.bab) for k in kk.KELAS)  # tautan lama tetap
    assert 'href="/admin/kurikulum/cetakan?kelas=2&amp;bab=3">%s</a>' % ui_ai.LABEL_TAUTAN_TABEL in isi


def test_tabel_memanggil_db_kuota_sekali_per_render(tertutup, admin, monkeypatch):
    panggilan = []
    asli = kuota.sisa_hari_ini

    def hitung_panggilan(*a, **k):
        panggilan.append(1)
        return asli(*a, **k)

    monkeypatch.setattr(kuota, "sisa_hari_ini", hitung_panggilan)
    assert minta_admin(tertutup, "/admin/kurikulum", admin)[0] == 200
    assert len(panggilan) == 1


def test_tabel_tanpa_kunci_tak_menyentuh_db_kuota(tertutup, admin, monkeypatch):
    siapkan_env(monkeypatch, kunci="")

    def gagal(*_a, **_k):
        raise AssertionError("DB kuota tak boleh dibaca tanpa kunci")

    monkeypatch.setattr(kuota, "sisa_hari_ini", gagal)
    assert minta_admin(tertutup, "/admin/kurikulum", admin)[0] == 200
    assert minta_admin(tertutup, _alamat_daftar(), admin)[0] == 200
