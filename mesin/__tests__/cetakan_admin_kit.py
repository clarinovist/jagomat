"""Pembantu tes admin cetakan soal berpola (C2): form sah, token, kirim POST, stempel DB, parser form halaman.

Semua data SINTETIS. DB cetakan diarahkan ke tmp_path oleh fixture tiap berkas tes (CETAKAN_BERKAS_DB).
"""
from __future__ import annotations

import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_kurikulum_cetakan_pages as ui  # noqa: E402
import admin_security  # noqa: E402
import auth  # noqa: E402
import cetakan_store as store  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, minta_mentah  # noqa: E402

BAB_ADA = (3, 1)  # kelas 3 bab 1: sudah ada soal kode
BAB_BELUM = (2, 3)  # kelas 2 bab 3: belum ada soal kode
TAK_ADA = "/admin/tidak-ada"
JUDUL = "Penjumlahan dua angka cerita"
TEKS = "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?"
AKSI_RUTE = {
    ui.AKSI_BUAT: ui.RUTE_BARU, ui.AKSI_UBAH: ui.RUTE_UBAH, ui.AKSI_SETUJUI: ui.RUTE_SETUJUI,
    ui.AKSI_NONAKTIFKAN: ui.RUTE_NONAKTIFKAN, ui.AKSI_AKTIFKAN: ui.RUTE_AKTIFKAN,
}


def isi_sah(**ganti) -> dict:
    """Isian form sah (25 - 3 = 22 field)."""
    data = {
        "judul": JUDUL, "teks": TEKS, "pembahasan": "{a} + {b} = {kunci}", "kunci": "a + b", "nama": "ya",
        "var_1_nama": "a", "var_1_min": "10", "var_1_max": "50",
        "var_2_nama": "b", "var_2_min": "1", "var_2_max": "40",
        "var_3_nama": "", "var_3_min": "", "var_3_max": "", "var_4_nama": "", "var_4_min": "", "var_4_max": "",
        "syarat_1": "a + b <= 99", "syarat_2": "", "syarat_3": "", "syarat_4": "", "syarat_5": "",
    }
    data.update(ganti)
    return data


def isi_tak_layak(**ganti) -> dict:
    """Sah secara bentuk tetapi hanya 25 kombinasi (< 30 unik): lolos simpan draf, gagal uji kelayakan."""
    return isi_sah(var_1_min="1", var_1_max="5", var_2_min="1", var_2_max="5", syarat_1="", **ganti)


def token(cookie: str, aksi: str, target_id, revisi: int, *, csrf_cookie=None, reauth=SANDI_ADMIN) -> dict:
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, csrf_cookie or cookie), "reauth": reauth,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": target_id, "target_revisi": revisi})}


def kirim(server, cookie, aksi, target_id, revisi, isi=None, *, ganti=None, hapus=(), ekstra=None, headers=None,
          jalur=None, token_aksi=None):
    """POST aksi dengan token langsung (tanpa lewat halaman). `ganti`/`hapus` mengubah field setelah dirakit."""
    data = {**token(cookie, token_aksi or aksi, target_id, revisi), **(isi if isi is not None else {}),
            **(ekstra or {}), **(ganti or {})}
    for nama in hapus:
        data.pop(nama, None)
    return minta_mentah(server, jalur or AKSI_RUTE[aksi], None, data,
                        {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def kirim_buat(server, cookie, isi=None, bab=BAB_ADA, **kw):
    return kirim(server, cookie, ui.AKSI_BUAT, "%d/%d" % bab, 0, isi_sah() if isi is None else isi, **kw)


def kirim_ubah(server, cookie, id_cetakan, revisi, isi=None, **kw):
    return kirim(server, cookie, ui.AKSI_UBAH, id_cetakan, revisi, isi_sah() if isi is None else isi, **kw)


def kirim_pindah(server, cookie, aksi, id_cetakan, revisi, **kw):
    return kirim(server, cookie, aksi, id_cetakan, revisi, {}, **kw)


def daftar_halaman(server, cookie, jalur):
    return minta_mentah(server, jalur, None, None, {"Cookie": "osn_sesi=" + cookie})


def stempel(path) -> tuple:
    """(baris cetakan, baris audit) apa adanya dari berkas DB; ((), ()) bila berkas belum ada."""
    if not Path(path).exists():
        return (), ()
    with sqlite3.connect(path) as kon:
        return (tuple(kon.execute("SELECT * FROM cetakan ORDER BY id").fetchall()),
                tuple(kon.execute("SELECT * FROM audit_cetakan ORDER BY id").fetchall()))


def segar(id_cetakan: int):
    store.bersihkan_cache()
    return store.ambil(id_cetakan)


def buat_langsung(isi=None, *, bab=BAB_ADA, sumber="manual", **ganti):
    """Cetakan draf lewat store (bukan HTTP), untuk menyiapkan keadaan."""
    data = isi if isi is not None else {
        "kelas": bab[0], "bab": bab[1], "judul": ganti.get("judul", JUDUL), "teks": ganti.get("teks", TEKS),
        "variabel": {"a": [10, 50], "b": [1, 40]}, "nama": True, "syarat": ["a + b <= 99"], "kunci": "a + b",
        "pembahasan": "{a} + {b} = {kunci}"}
    return store.buat_draf(data, sumber=sumber, actor_id="admin-sintetis")


def aktifkan_langsung(item):
    """draf -> aktif lewat store."""
    return store.setujui(item.id, actor_id="admin-sintetis", revisi_diharapkan=item.revisi)


class _ParserForm(HTMLParser):
    """Field form seperti peramban mengirimnya: hidden/text apa adanya, textarea isinya, select opsi terpilih."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formulir = []
        self._kini = None
        self._area = None
        self._pilih = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._kini = {"action": a.get("action"), "field": {}}
            self.formulir.append(self._kini)
        elif self._kini is None:
            return
        elif tag == "input" and a.get("name"):
            self._kini["field"][a["name"]] = a.get("value", "")
        elif tag == "textarea":
            self._area = a.get("name")
            self._kini["field"][self._area] = ""
        elif tag == "select":
            self._pilih = a.get("name")
            self._kini["field"][self._pilih] = None
        elif tag == "option" and self._pilih and ("selected" in a or self._kini["field"][self._pilih] is None):
            if "selected" in a or self._kini["field"][self._pilih] is None:
                self._kini["field"][self._pilih] = a.get("value", "")

    def handle_data(self, data):
        if self._area:
            self._kini["field"][self._area] += data

    def handle_endtag(self, tag):
        if tag == "form":
            self._kini = None
        elif tag == "textarea":
            self._area = None
        elif tag == "select":
            self._pilih = None


def formulir(isi_halaman: str, action: str) -> dict:
    """Field form (sebagai dikirim peramban) untuk `action`; AssertionError bila tak ada."""
    parser = _ParserForm()
    parser.feed(isi_halaman.rsplit("</style>", 1)[-1])
    for f in parser.formulir:
        if f["action"] == action:
            return dict(f["field"])
    raise AssertionError("form %s tidak ada" % action)


def semua_action(isi_halaman: str) -> list:
    parser = _ParserForm()
    parser.feed(isi_halaman.rsplit("</style>", 1)[-1])
    return [f["action"] for f in parser.formulir if f["action"].startswith(ui.RUTE)]
