"""Halaman orang tua di akun murid (F3) lewat HTTP nyata: gerbang sakelar, isolasi anak, PIN tirai, isi.

Data sepenuhnya sintetis di tmp_path. Sakelar dinyalakan lewat env (fallback; DB sakelar tidak ada).
Login memakai POST /masuk (cookie), kecuali tes Basic yang memang menguji jalur tanpa cookie.
"""
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import admin_store
import auth
import database
import kontak_akun
import parent_report_store
import pesanan
import pesanan_pages
import pesanan_dasar
import pin_orang_tua_store as pin_store
import schema_pesanan
import teacher_style
import tirai_orang_tua as tirai
from http_test_kit import ServerUji, _basic
from pesanan_kit import buat as buat_order, terapkan as terapkan_bayar

RUTE = "/murid/orang-tua"
SANDI_A = "sandi-raka-sintetis"
SANDI_B = "sandi-dina-sintetis"
PIN_A = "4821"
PIN_B = "1357"
WA_MENTAH = "0812-3456-7890"
WA_NORMAL = "6281234567890"
NAMA_A = "Raka Sintetis"
NAMA_B = "Dina Sintetis"
UNTUK_AYAH_BUNDA = "Untuk Ayah/Bunda"
KALIMAT_ORTU = "Halaman ini untuk Ayah/Bunda. Nomor WhatsApp untuk tagihan hanya bisa diubah lewat tim Jagomat."
# Daftar khusus halaman orang tua (terpisah dari KATA_TERLARANG halaman anak cek).
KATA_TERLARANG_ORTU = (
    "kunci", "malrule", "diagnos", "kode_final", "kode_usulan", "pembahasan", "jawaban benar", "tel:", "wa.me",
)


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _req(server, jalur, *, data=None, cookie=None, basic=None, headers=None, method=None):
    isi = None if data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi, method=method or ("POST" if isi is not None else "GET"))
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        req.add_header("Cookie", "osn_sesi=" + cookie)
    if basic:
        req.add_header("Authorization", _basic(*basic))
    for nama, nilai in (headers or {}).items():
        req.add_header(nama, nilai)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)


def _login(server, nama, sandi):
    kode, _, header = _req(server, "/masuk", data={"nama": nama, "sandi": sandi})
    assert kode == 303, kode
    return header["Set-Cookie"].split(";")[0].split("=", 1)[1]


def _tanpa_gaya(isi):
    return re.sub(r"<(style|script)\b.*?</\1>", "", isi, flags=re.S)


class Dunia:
    pass


@pytest.fixture
def dunia(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    tirai._reset()
    d = Dunia()
    d.server, d.monkeypatch = server, monkeypatch
    with server.buka() as kon:
        d.a = database.tambah_siswa(kon, NAMA_A, "P4", pemilik="koordinator-sintetis")
        d.b = database.tambah_siswa(kon, NAMA_B, "P3", pemilik="koordinator-sintetis")
    d.akun_a = auth.tambah_akun_dan_principal("raka-m", SANDI_A, "murid", siswa_id=d.a)
    d.akun_b = auth.tambah_akun_dan_principal("dina-m", SANDI_B, "murid", siswa_id=d.b)
    yield d
    tirai._reset()
    server.berhenti()


def _pasang_pin(dunia, siswa, pin):
    with dunia.server.buka() as kon:
        pin_store.simpan(kon, siswa, pin, 1_800_000_000)


def _hash_pin(dunia, siswa):
    with dunia.server.buka() as kon:
        baris = kon.execute("SELECT garam, kunci, iterasi, diperbarui FROM pin_orang_tua WHERE siswa_id = ?", (siswa,)).fetchone()
    return None if baris is None else tuple(baris)


def _seed_cek(dunia, siswa, id_akun, skor, kategori, kuat, perlu):
    ring = json.dumps({"kuat": kuat, "perlu": perlu})
    with dunia.server.buka() as kon:
        kon.execute(
            """INSERT INTO cek_gratis(siswa_id, id_akun, setuju_pada, versi_notice, dibuat, selesai_pada, skor,
                                      kategori, ringkasan, jumlah_soal)
               VALUES (?, ?, 't', 'v1', 't', 't', ?, ?, ?, 15)""", (siswa, id_akun, skor, kategori, ring))


def _seed_laporan(dunia, siswa, catatan, *, terbit=True, tanggal=1_790_000_000):
    isi = {"topik": ["Pecahan senilai"], "langkah": "Latih satu soal sehari."}
    with dunia.server.buka() as kon:
        lap = parent_report_store.buat_draf(kon, siswa, "2026-11-01", "2026-11-15", isi)
        parent_report_store.simpan_catatan(kon, siswa, lap, catatan)
        if terbit:
            parent_report_store.terbitkan(kon, siswa, lap, "Bu Guru Sintetis", sekarang=tanggal)
    return lap


def _buka_tirai(dunia, nama="raka-m", sandi=SANDI_A, pin=PIN_A):
    token = _login(dunia.server, nama, sandi)
    kode, _, _ = _req(dunia.server, RUTE + "/pin", data={"pin": pin}, cookie=token)
    assert kode == 303
    return token


# --- gerbang sakelar ---------------------------------------------------------

def test_sakelar_mati_get_identik_rute_murid_tak_dikenal(dunia):
    dunia.monkeypatch.delenv("DAFTAR_AKUN_ANAK")
    token = _login(dunia.server, "raka-m", SANDI_A)
    hasil = _req(dunia.server, RUTE, cookie=token)
    asing = _req(dunia.server, "/murid/tidak-ada", cookie=token)
    assert hasil[0] == 404 and hasil[:2] == asing[:2]
    anon, anon_asing = _req(dunia.server, RUTE), _req(dunia.server, "/murid/tidak-ada")
    assert anon[0] == 303 and anon[0] == anon_asing[0] and anon[2]["Location"] == anon_asing[2]["Location"]


@pytest.mark.parametrize("rute", [RUTE + "/pin", RUTE + "/pin/atur", RUTE + "/pin/hapus"])
def test_sakelar_mati_post_identik_rute_tak_dikenal_dan_tanpa_efek(dunia, rute):
    _pasang_pin(dunia, dunia.a, PIN_A)
    sebelum = _hash_pin(dunia, dunia.a)
    dunia.monkeypatch.delenv("DAFTAR_AKUN_ANAK")
    token = _login(dunia.server, "raka-m", SANDI_A)
    data = {"pin": "9999", "pin_ulang": "9999", "konfirmasi": "1"}
    hasil = _req(dunia.server, rute, data=data, cookie=token)
    asing = _req(dunia.server, "/murid/tidak-ada", data=data, cookie=token)
    assert hasil[:2] == asing[:2]
    assert _hash_pin(dunia, dunia.a) == sebelum
    anon, anon_asing = _req(dunia.server, rute, data=data), _req(dunia.server, "/murid/tidak-ada", data=data)
    assert anon[:2] == anon_asing[:2]


def test_tombol_beranda_hanya_saat_sakelar_hidup(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, "/murid", cookie=token)
    assert kode == 200 and UNTUK_AYAH_BUNDA in isi and f'href="{RUTE}"' in isi
    assert isi.count(f'href="{RUTE}"') == 1
    dunia.monkeypatch.delenv("DAFTAR_AKUN_ANAK")
    kode, isi, _ = _req(dunia.server, "/murid", cookie=token)
    assert kode == 200 and UNTUK_AYAH_BUNDA not in isi and RUTE not in isi


def test_tanpa_sesi_get_diarahkan_ke_masuk_dan_post_ditolak(dunia):
    kode, _, header = _req(dunia.server, RUTE)
    assert kode == 303 and header["Location"] == "/masuk"
    for rute in (RUTE + "/pin", RUTE + "/pin/atur", RUTE + "/pin/hapus"):
        kode, isi, _ = _req(dunia.server, rute, data={"pin": PIN_A})
        assert kode == 401 and NAMA_A not in isi


# --- isolasi anak ------------------------------------------------------------

def test_siswa_hanya_dari_sesi_parameter_palsu_diabaikan(dunia):
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], ["Pengukuran"])
    _seed_cek(dunia, dunia.b, dunia.akun_b.id_akun, 33, "Perlu pendampingan", ["Geometri"], ["Bilangan"])
    _seed_laporan(dunia, dunia.b, "CATATAN KHUSUS DINA")
    token = _login(dunia.server, "raka-m", SANDI_A)
    dasar = _req(dunia.server, RUTE, cookie=token)
    assert dasar[0] == 200 and NAMA_A in dasar[1]
    for kueri in (f"?siswa_id={dunia.b}", f"?id={dunia.b}&id_akun={dunia.akun_b.id_akun}", "?siswa=" + urllib.parse.quote(NAMA_B)):
        palsu = _req(dunia.server, RUTE + kueri, cookie=token)
        assert palsu[:2] == dasar[:2]
    for bocor in (NAMA_B, "CATATAN KHUSUS DINA", ">33<"):
        assert bocor not in dasar[1]


def test_siswa_dari_form_diabaikan_pada_aksi_pin(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    _pasang_pin(dunia, dunia.b, PIN_B)
    sebelum_b = _hash_pin(dunia, dunia.b)
    token = _buka_tirai(dunia)
    kode, _, _ = _req(dunia.server, RUTE + "/pin/hapus", data={"konfirmasi": "1", "siswa_id": str(dunia.b)}, cookie=token)
    assert kode == 303
    assert _hash_pin(dunia, dunia.a) is None and _hash_pin(dunia, dunia.b) == sebelum_b
    kode, _, _ = _req(dunia.server, RUTE + "/pin/atur", data={"pin": "2222", "pin_ulang": "2222", "siswa_id": str(dunia.b)}, cookie=token)
    assert kode == 303
    assert _hash_pin(dunia, dunia.b) == sebelum_b and _hash_pin(dunia, dunia.a) is not None


# --- PIN tirai ---------------------------------------------------------------

def test_tanpa_pin_langsung_isi(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, header = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="ortu-hasil-cek"' in isi and 'id="ortu-pin"' in isi
    assert 'id="ortu-pin-masuk"' not in isi
    assert KALIMAT_ORTU in isi and header["Cache-Control"] == "no-store"


def test_dengan_pin_form_dulu_tanpa_isi(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], [])
    _seed_laporan(dunia, dunia.a, "CATATAN RAHASIA TIRAI")
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="ortu-pin-masuk"' in isi and 'name="pin"' in isi
    for isi_tertutup in ('id="ortu-hasil-cek"', "CATATAN RAHASIA TIRAI", "Cukup baik", 'id="ortu-laporan"'):
        assert isi_tertutup not in isi


def test_get_tertutup_tidak_membaca_isi(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    import orang_tua_data

    def terlarang(*a, **k):
        raise AssertionError("isi dibaca saat tirai tertutup")
    dunia.monkeypatch.setattr(orang_tua_data, "kumpulkan", terlarang)
    token = _login(dunia.server, "raka-m", SANDI_A)
    assert _req(dunia.server, RUTE, cookie=token)[0] == 200


def test_pin_benar_membuka_dan_salah_tetap_tertutup(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE + "/pin", data={"pin": "0000"}, cookie=token)
    assert kode == 200 and "PIN belum cocok" in isi and PIN_A not in isi
    assert 'id="ortu-pin-masuk"' in _req(dunia.server, RUTE, cookie=token)[1]
    kode, _, header = _req(dunia.server, RUTE + "/pin", data={"pin": PIN_A}, cookie=token)
    assert kode == 303 and header["Location"] == RUTE
    assert 'id="ortu-hasil-cek"' in _req(dunia.server, RUTE, cookie=token)[1]


def test_pin_salah_pesan_generik_sama_untuk_bentuk_apa_pun(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    token = _login(dunia.server, "raka-m", SANDI_A)
    badan = {_req(dunia.server, RUTE + "/pin", data=d, cookie=token)[1] for d in ({"pin": "0000"}, {"pin": "abc"}, {})}
    assert len(badan) == 1


def test_tirai_kedaluwarsa_tiga_puluh_menit_dengan_waktu_disuntik(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    jam = {"t": 1_800_000_000.0}
    dunia.monkeypatch.setattr(tirai, "_jam", lambda: jam["t"])
    token = _buka_tirai(dunia)
    jam["t"] += tirai.UMUR_TIRAI_DETIK - 1
    assert 'id="ortu-hasil-cek"' in _req(dunia.server, RUTE, cookie=token)[1]
    jam["t"] += 1
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert 'id="ortu-pin-masuk"' in isi and 'id="ortu-hasil-cek"' not in isi


def test_blokir_setelah_batas_laju_tanpa_menjalankan_pbkdf2(dunia):
    import laju_masuk
    _pasang_pin(dunia, dunia.a, PIN_A)
    token = _login(dunia.server, "raka-m", SANDI_A)
    for _ in range(laju_masuk.BATAS_GAGAL):
        assert _req(dunia.server, RUTE + "/pin", data={"pin": "0000"}, cookie=token)[0] == 200
    panggilan = []
    asli = pin_store.periksa_pin
    dunia.monkeypatch.setattr(pin_store, "periksa_pin", lambda *a, **k: panggilan.append(1) or asli(*a, **k))
    kode, isi, _ = _req(dunia.server, RUTE + "/pin", data={"pin": PIN_A}, cookie=token)
    assert kode == 429 and "Coba lagi beberapa menit lagi." in isi and panggilan == []
    assert 'id="ortu-pin-masuk"' in _req(dunia.server, RUTE, cookie=token)[1]


def test_laju_per_anak_anak_lain_tidak_ikut_terblokir(dunia):
    import laju_masuk
    _pasang_pin(dunia, dunia.a, PIN_A)
    _pasang_pin(dunia, dunia.b, PIN_B)
    token_a = _login(dunia.server, "raka-m", SANDI_A)
    for _ in range(laju_masuk.BATAS_GAGAL):
        _req(dunia.server, RUTE + "/pin", data={"pin": "0000"}, cookie=token_a)
    token_b = _login(dunia.server, "dina-m", SANDI_B)
    assert _req(dunia.server, RUTE + "/pin", data={"pin": PIN_B}, cookie=token_b)[0] == 303


def test_basic_auth_dengan_pin_benar_tidak_pernah_membuka_tirai(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    kredensial = ("raka-m", SANDI_A)
    _req(dunia.server, RUTE + "/pin", data={"pin": PIN_A}, basic=kredensial)
    isi = _req(dunia.server, RUTE, basic=kredensial)[1]
    assert 'id="ortu-pin-masuk"' in isi and 'id="ortu-hasil-cek"' not in isi
    assert tirai._TERBUKA == {}


def test_tirai_terikat_sesi_dan_hilang_saat_keluar(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    token1 = _buka_tirai(dunia)
    token2 = _login(dunia.server, "raka-m", SANDI_A)
    assert 'id="ortu-hasil-cek"' in _req(dunia.server, RUTE, cookie=token1)[1]
    assert 'id="ortu-pin-masuk"' in _req(dunia.server, RUTE, cookie=token2)[1]
    assert _req(dunia.server, "/keluar", data={}, cookie=token1)[0] == 303
    assert tirai._TERBUKA == {}
    token3 = _login(dunia.server, "raka-m", SANDI_A)
    assert 'id="ortu-pin-masuk"' in _req(dunia.server, RUTE, cookie=token3)[1]


# --- atur / hapus PIN --------------------------------------------------------

def test_pasang_pin_tanpa_pin_membuka_tirai_dan_menyimpan_hash(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, _, header = _req(dunia.server, RUTE + "/pin/atur", data={"pin": "2468", "pin_ulang": "2468"}, cookie=token)
    assert kode == 303 and header["Location"].startswith(RUTE)
    assert "2468" not in json.dumps(_hash_pin(dunia, dunia.a))
    with dunia.server.buka() as kon:
        assert pin_store.periksa_pin(kon, dunia.a, "2468") is True
    assert 'id="ortu-hasil-cek"' in _req(dunia.server, RUTE, cookie=token)[1]


@pytest.mark.parametrize("data", [
    {"pin": "246", "pin_ulang": "246"}, {"pin": "abcd", "pin_ulang": "abcd"},
    {"pin": "2468", "pin_ulang": "2469"}, {"pin": "24680", "pin_ulang": "24680"}, {},
])
def test_pasang_pin_tidak_sah_ditolak_tanpa_efek(dunia, data):
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE + "/pin/atur", data=data, cookie=token)
    assert kode == 400 and "PIN harus 4 angka" in isi
    assert _hash_pin(dunia, dunia.a) is None


def test_ganti_pin_saat_tertutup_ditolak_tanpa_efek_saat_terbuka_berhasil(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    sebelum = _hash_pin(dunia, dunia.a)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE + "/pin/atur", data={"pin": "2468", "pin_ulang": "2468"}, cookie=token)
    assert kode == 403 and 'id="ortu-pin-masuk"' in isi
    assert _hash_pin(dunia, dunia.a) == sebelum
    token = _buka_tirai(dunia)
    kode, _, _ = _req(dunia.server, RUTE + "/pin/atur", data={"pin": "2468", "pin_ulang": "2468"}, cookie=token)
    assert kode == 303
    with dunia.server.buka() as kon:
        assert pin_store.periksa_pin(kon, dunia.a, "2468") and not pin_store.periksa_pin(kon, dunia.a, PIN_A)


def test_hapus_pin_butuh_tirai_terbuka_dan_konfirmasi(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    sebelum = _hash_pin(dunia, dunia.a)
    token = _login(dunia.server, "raka-m", SANDI_A)
    assert _req(dunia.server, RUTE + "/pin/hapus", data={"konfirmasi": "1"}, cookie=token)[0] == 403
    assert _hash_pin(dunia, dunia.a) == sebelum
    token = _buka_tirai(dunia)
    kode, isi, _ = _req(dunia.server, RUTE + "/pin/hapus", data={}, cookie=token)
    assert kode == 400 and "konfirmasi" in isi.lower() and _hash_pin(dunia, dunia.a) == sebelum
    kode, _, _ = _req(dunia.server, RUTE + "/pin/hapus", data={"konfirmasi": "1"}, cookie=token)
    assert kode == 303 and _hash_pin(dunia, dunia.a) is None
    assert 'id="ortu-hasil-cek"' in _req(dunia.server, RUTE, cookie=token)[1]


def test_hapus_tanpa_pin_tidak_berefek(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    assert _req(dunia.server, RUTE + "/pin/hapus", data={"konfirmasi": "1"}, cookie=token)[0] == 303
    assert _hash_pin(dunia, dunia.a) is None


@pytest.mark.parametrize("rute,data", [
    (RUTE + "/pin", {"pin": PIN_A}),
    (RUTE + "/pin/atur", {"pin": "2468", "pin_ulang": "2468"}),
    (RUTE + "/pin/hapus", {"konfirmasi": "1"}),
])
def test_csrf_lintas_situs_ditolak_tanpa_efek(dunia, rute, data):
    _pasang_pin(dunia, dunia.a, PIN_A)
    sebelum = _hash_pin(dunia, dunia.a)
    token = _buka_tirai(dunia)
    for tajuk in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://jahat.example"}):
        kode, _, _ = _req(dunia.server, rute, data=data, cookie=token, headers=tajuk)
        assert kode == 403
        assert _hash_pin(dunia, dunia.a) == sebelum


# --- isi halaman -------------------------------------------------------------

def test_hasil_cek_tampil_dengan_ringkasan_topik(dunia):
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], ["Pengukuran"])
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert ">72<" in isi and "Cukup baik" in isi and "Sudah kuat" in isi and "Perlu diperkuat" in isi


def test_belum_ada_cek_kalimat_netral(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "Cek kemampuan belum dikerjakan." in isi and 'class="funnel-cincin' not in isi


def test_cek_belum_selesai_tanpa_skor(dunia):
    with dunia.server.buka() as kon:
        kon.execute("""INSERT INTO cek_gratis(siswa_id, id_akun, setuju_pada, versi_notice, dibuat)
                       VALUES (?, ?, 't', 'v1', 't')""", (dunia.a, dunia.akun_a.id_akun))
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "belum selesai" in isi.lower() and 'class="funnel-cincin' not in isi and "dari 100" not in isi


def test_cek_milik_akun_lain_tidak_tampil(dunia):
    _seed_cek(dunia, dunia.a, dunia.akun_b.id_akun, 91, "Sangat baik", ["Pecahan"], [])
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "Sangat baik" not in isi and "Cek kemampuan belum dikerjakan." in isi


def test_cek_anak_lain_di_akun_yang_sama_tidak_dipakai(dunia):
    _seed_cek(dunia, dunia.b, dunia.akun_a.id_akun, 91, "Sangat baik", ["Pecahan"], [])
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "Sangat baik" not in isi and "Cek kemampuan belum dikerjakan." in isi


def test_laporan_terbit_terbaru_tampil_bukan_draf_atau_yang_lama(dunia):
    _seed_laporan(dunia, dunia.a, "CATATAN LAMA", tanggal=1_790_000_000)
    _seed_laporan(dunia, dunia.a, "CATATAN BARU", tanggal=1_790_100_000)
    _seed_laporan(dunia, dunia.a, "CATATAN DRAF", terbit=False)
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "CATATAN BARU" in isi and "Bu Guru Sintetis" in isi
    assert "CATATAN LAMA" not in isi and "CATATAN DRAF" not in isi
    assert "Pratinjau" not in isi and "Berlaku sampai" not in isi and "Diterbitkan" in isi


def test_tanpa_laporan_kalimat_netral(dunia):
    _seed_laporan(dunia, dunia.a, "HANYA DRAF", terbit=False)
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert "Belum ada laporan dari Guru." in isi and "HANYA DRAF" not in isi


def _siapkan_pesanan(dunia):
    schema_pesanan.migrasikan(admin_store.BAWAAN)


def _buat_order(dunia, siswa, akun, n=1, bayar=False):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with pesanan_dasar.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = buat_order(kon, n, akun=akun, siswa=siswa, sekarang=now)
        if bayar:
            terapkan_bayar(kon, order, n, sekarang=now)


def test_status_pesanan_tampil_dengan_teks_copy_status(dunia):
    _siapkan_pesanan(dunia)
    _buat_order(dunia, dunia.a, dunia.akun_a.id_akun, bayar=True)
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    judul, kalimat = pesanan_pages.COPY_STATUS[pesanan_dasar.STATUS_SUDAH_DIBAYAR]
    assert 'id="ortu-pesanan"' in isi and judul in isi and kalimat in isi
    assert 'action="/pesanan' not in isi and "/pesanan/" not in isi


def test_status_belum_bayar_tanpa_tombol_bayar(dunia):
    _siapkan_pesanan(dunia)
    _buat_order(dunia, dunia.a, dunia.akun_a.id_akun)
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    judul, _ = pesanan_pages.COPY_STATUS[pesanan_dasar.STATUS_BELUM_BAYAR]
    assert judul in isi and "/pesanan/qr" not in isi and "<img src=\"/pesanan" not in isi


def test_tanpa_order_atau_order_akun_lain_kartu_tidak_tampil(dunia):
    _siapkan_pesanan(dunia)
    token = _login(dunia.server, "raka-m", SANDI_A)
    assert 'id="ortu-pesanan"' not in _req(dunia.server, RUTE, cookie=token)[1]
    _buat_order(dunia, dunia.a, auth.id_akun_baru() if hasattr(auth, "id_akun_baru") else "akun_" + "c3" * 16, bayar=True)
    assert 'id="ortu-pesanan"' not in _req(dunia.server, RUTE, cookie=token)[1]


def test_penyimpanan_pesanan_belum_siap_menyembunyikan_kartu_bukan_500(dunia):
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="ortu-pesanan"' not in isi


def test_kontak_wa_tidak_pernah_dirender_dan_kalimat_ortu_ada(dunia):
    with dunia.server.buka() as kon:
        kontak_akun.simpan(kon, dunia.akun_a.id_akun, WA_NORMAL, "2026-11-23T10:00:00")
    _pasang_pin(dunia, dunia.a, PIN_A)
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], [])
    token = _buka_tirai(dunia)
    for isi in (_req(dunia.server, RUTE, cookie=token)[1], _req(dunia.server, "/murid", cookie=token)[1]):
        for angka in (WA_MENTAH, WA_NORMAL, "081234567890", "1234567890"):
            assert angka not in isi
    assert KALIMAT_ORTU in _req(dunia.server, RUTE, cookie=token)[1]


def test_tanpa_kata_terlarang_halaman_orang_tua(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], ["Pengukuran"])
    _seed_laporan(dunia, dunia.a, "Catatan sintetis")
    token = _buka_tirai(dunia)
    for isi in (_req(dunia.server, RUTE, cookie=token)[1],
                _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))[1]):
        badan = _tanpa_gaya(isi).lower()
        for kata in KATA_TERLARANG_ORTU:
            assert kata not in badan, kata


def test_hanya_skrip_mata_sandi_dan_csp_mengizinkan_hash_nya(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, header = _req(dunia.server, RUTE, cookie=token)
    skrip = re.findall(r"<script>(.*?)</script>", isi, flags=re.S)
    assert skrip == [teacher_style.SKRIP_MATA_SANDI]
    import base64
    hash_skrip = base64.b64encode(hashlib.sha256(teacher_style.SKRIP_MATA_SANDI.encode()).digest()).decode()
    assert "'sha256-" + hash_skrip + "'" in header["Content-Security-Policy"]
    assert 'type="password"' in isi and 'inputmode="numeric"' in isi


def test_murid_tanpa_siswa_terhubung_tidak_membuka_halaman(dunia):
    auth.tambah_akun_dan_principal("yatim-m", "sandi-yatim-sintetis", "murid")
    token = _login(dunia.server, "yatim-m", "sandi-yatim-sintetis")
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert "Belum terhubung" in isi and "ortu-" not in isi
