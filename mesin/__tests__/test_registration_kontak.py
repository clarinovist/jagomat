"""Pendaftaran jalur funnel (`jalur=cek`): WhatsApp wajib, tersimpan per akun.

Semua data sintetis di tmp_path; nomor uji rekaan. `/daftar` biasa tidak boleh
berubah: golden markup dan golden `sidik` diturunkan dari kode sebelum K2.
"""
import hashlib
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import pytest

import admin_registration as reg
import admin_store
import auth
import database
import funnel_flag
import kontak_akun
import landing
import product_analytics_http
import registration_contact
from http_test_kit import ServerUji

WA_MASUKAN = "0812-3456-7890"
WA_NORMAL = "6281234567890"
WA_LAIN = "6285551234567"
SIDIK_EMAS = "b0924e77255ebfa466ed710823dcee44a30b859f35446d5697cea2ba54329f7d"
# Diperbarui 23 Nov 2026, perubahan tampilan yang disengaja, bukan perilaku form: golden terakhir hijau di
# deb96ef (22 Nov 16:48). Sejak itu hanya <head> dan <style> halaman_daftar yang berubah: tautan Google Fonts
# diganti @font-face same-origin (3c07916 font merek 22 Nov, 7eaaf9d font lokal/CSP 23 Nov) dan CSS bersama
# bergeser oleh shell guru (6221a6b, e630a8c, 3667919 22 Nov) dan area anak (bcfe8e2 22 Nov). Body <form>
# (field, action, token, CTA, kesepakatan) dan skrip identik; dibuktikan lewat diff markup di luar <style>.
MARKUP_EMAS = {
    "polos": "d37778b3d40b4a26392d3772a8bb08b44382c7aec33decc78536ba23e572d307",
    "lengkap": "e7fd1f743e86681bda361b4b6bc85fb007fd4ccd58654dd8b3c16682bb99ffbd",
    "kesepakatan": "709768b616036408af166ba27b02b814ab2e3c6d2e0b6913b9817e83c31d3b50",
}


def _sha(isi: bytes) -> str:
    return hashlib.sha256(isi).hexdigest()


# --- sakelar ---------------------------------------------------------------

def test_funnel_aktif_default_mati(monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    assert funnel_flag.funnel_aktif() is False


@pytest.mark.parametrize("nilai,hasil", [("1", True), (" 1 ", True), ("0", False),
                                         ("", False), ("true", False), ("2", False)])
def test_funnel_aktif_hanya_satu_yang_hidup(monkeypatch, nilai, hasil):
    monkeypatch.setenv("FUNNEL_AKTIF", nilai)
    assert funnel_flag.funnel_aktif() is hasil


# --- golden: jalur biasa tidak berubah -------------------------------------

def test_golden_markup_form_biasa_identik_byte():
    assert _sha(landing.halaman_daftar()) == MARKUP_EMAS["polos"]
    assert _sha(landing.halaman_daftar(
        "Pesan <uji>", True, "nama&x", token_form="tok-uji-sintetis", analitik="<i>",
        kesepakatan="", nama_anak='Anak "S"', kelas_sekolah=4, profil_parameter="P4",
    )) == MARKUP_EMAS["lengkap"]
    assert _sha(landing.halaman_daftar(
        kesepakatan='<input type="hidden" name="k" value="1">', token_form="t",
    )) == MARKUP_EMAS["kesepakatan"]


@pytest.fixture
def kasus(tmp_path):
    paths = (tmp_path / "admin.db", tmp_path / "auth.json", tmp_path / "belajar.db")
    admin_store.siapkan(paths[0])
    database.siapkan(paths[2])
    reg.migrasikan_profil_registrasi(paths[2])
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin", paths[1])
    kw = dict(operasi_id="registrasi_profil_001", alias="ortu-sintetis", sandi="sandi-sintetis",
              token_form="x" * 64, sekarang=1800000000, nama_anak="Anak Sintetis",
              kelas_sekolah=4, profil_parameter="P4")
    return paths, kw


def _daftar(kasus, **ubah):
    paths, kw = kasus
    return reg.daftar_dengan_profil(*paths, **{**kw, **ubah})


def _kontak(paths):
    with database.buka(paths[2]) as kon:
        return [tuple(b) for b in kon.execute("SELECT id_akun, wa FROM kontak_akun")]


def _jumlah_siswa(paths):
    with database.buka(paths[2]) as kon:
        return kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0]


def _sidik_tersimpan(paths):
    with database.buka(paths[2]) as kon:
        return kon.execute("SELECT sidik_perintah FROM registrasi_profil_anak").fetchone()[0]


def test_golden_sidik_jalur_biasa_identik_dengan_sebelum_k2(kasus):
    _daftar(kasus)
    assert _sidik_tersimpan(kasus[0]) == SIDIK_EMAS
    assert _kontak(kasus[0]) == []


def test_sidik_jalur_cek_berbeda_dari_jalur_biasa(kasus):
    _daftar(kasus, wa=WA_NORMAL)
    assert _sidik_tersimpan(kasus[0]) != SIDIK_EMAS


# --- saga: kontak di transaksi siswa ---------------------------------------

def test_saga_wa_valid_tersimpan_dengan_id_akun_bukan_nama_login(kasus):
    paths, kw = kasus
    akun = _daftar(kasus, wa=WA_NORMAL)
    assert _kontak(paths) == [(akun.id_akun, WA_NORMAL)]
    assert akun.id_akun != kw["alias"]
    with database.buka(paths[2]) as kon:
        assert kontak_akun.ambil(kon, akun.id_akun)["wa"] == WA_NORMAL


def test_saga_replay_wa_sama_idempoten(kasus):
    paths, _ = kasus
    pertama = _daftar(kasus, wa=WA_NORMAL)
    awal = paths[1].read_bytes()
    kedua = _daftar(kasus, wa=WA_NORMAL)
    assert kedua.id_akun == pertama.id_akun and not kedua.baru
    assert paths[1].read_bytes() == awal
    assert _kontak(paths) == [(pertama.id_akun, WA_NORMAL)]
    assert _jumlah_siswa(paths) == 1


def test_saga_replay_wa_beda_ditolak_tanpa_menimpa(kasus):
    paths, _ = kasus
    akun = _daftar(kasus, wa=WA_NORMAL)
    awal = paths[1].read_bytes()
    with pytest.raises(ValueError):
        _daftar(kasus, wa=WA_LAIN)
    assert _kontak(paths) == [(akun.id_akun, WA_NORMAL)]
    assert paths[1].read_bytes() == awal


def test_saga_replay_jalur_biasa_atas_operasi_cek_ditolak(kasus):
    paths, _ = kasus
    _daftar(kasus, wa=WA_NORMAL)
    with pytest.raises(ValueError):
        _daftar(kasus)
    assert len(_kontak(paths)) == 1


@pytest.mark.parametrize("wa", ["", "081234567890", "12345", "+6281234567890", 6281234567890])
def test_saga_wa_tidak_ternormalisasi_ditolak_tanpa_efek(kasus, wa):
    paths, _ = kasus
    with pytest.raises(ValueError) as galat:
        _daftar(kasus, wa=wa)
    assert str(wa) not in str(galat.value) or str(wa) == ""
    assert _jumlah_siswa(paths) == 0 and _kontak(paths) == []
    assert auth.muat_sandi(paths[1]).get("registrasi_profil", {}) == {}


def test_saga_simpan_kontak_gagal_membatalkan_seluruh_transaksi(kasus, monkeypatch):
    paths, kw = kasus

    def rusak(*_a, **_kw):
        raise ValueError("kontak gagal disimpan")

    monkeypatch.setattr(kontak_akun, "simpan", rusak)
    with pytest.raises(ValueError):
        _daftar(kasus, wa=WA_NORMAL)
    assert _jumlah_siswa(paths) == 0 and _kontak(paths) == []
    assert auth.cari_akun(kw["alias"], paths[1]) is None
    assert auth.muat_sandi(paths[1]).get("registrasi_profil", {}) == {}
    with database.buka(paths[2]) as kon:
        assert kon.execute("SELECT COUNT(*) FROM registrasi_profil_anak").fetchone()[0] == 0


@pytest.mark.parametrize("titik", ["sebelum_intent", "setelah_intent", "setelah_db", "setelah_auth"])
def test_saga_crash_lalu_lanjut_kontak_tepat_satu(kasus, titik):
    paths, kw = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        _daftar(kasus, wa=WA_NORMAL, failpoint=titik)
    akun = _daftar(kasus, wa=WA_NORMAL)
    assert _kontak(paths) == [(akun.id_akun, WA_NORMAL)]
    assert _jumlah_siswa(paths) == 1


# --- HTTP ------------------------------------------------------------------

@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    yield s
    s.berhenti()


@pytest.fixture
def funnel_hidup(monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(server, data):
    """POST /daftar tanpa mengikuti 303 -> (kode, isi, header)."""
    req = urllib.request.Request(
        server.alamat + "/daftar", data=urllib.parse.urlencode(data).encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)


def _ambil_form(server, jalur="/daftar?jalur=cek", **tambahan):
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = dict(nama="ortu-funnel", sandi="sandi-form-sintetis", setuju="1", token_form=token,
                nama_anak="Profil Sintetis", kelas_sekolah="4")
    return {**data, **tambahan}


def _tanpa_token(isi: str) -> str:
    return re.sub(r'name="token_form" value="[^"]+"', 'name="token_form" value="-"', isi)


def _keadaan(server):
    with server.buka() as kon:
        siswa = kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0]
        kontak = [tuple(b) for b in kon.execute("SELECT id_akun, wa FROM kontak_akun")]
    intent = auth.muat_sandi(auth.BERKAS_SANDI).get("registrasi_profil", {})
    return siswa, kontak, intent


def _tidak_ada_efek(server, akun_ada=False):
    siswa, kontak, intent = _keadaan(server)
    assert (siswa, kontak, intent) == (0, [], {})
    assert (auth.cari_akun("ortu-funnel") is not None) is akun_ada


def _teks_pesan(isi: str) -> str:
    cocok = re.search(r'id="pesan-daftar"[^>]*>(.*?)</div>', isi, re.S)
    return cocok.group(1) if cocok else ""


def test_get_jalur_cek_saat_sakelar_mati_sama_dengan_form_lama(server, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    _, biasa, _ = server.minta("/daftar")
    _, cek, _ = server.minta("/daftar?jalur=cek")
    assert _tanpa_token(cek) == _tanpa_token(biasa)
    assert 'name="wa"' not in cek and 'name="jalur"' not in cek
    assert "Tidak perlu email atau nomor telepon" in cek


def test_get_jalur_cek_saat_sakelar_hidup_menampilkan_field_wa_dan_copy(server, funnel_hidup):
    _, isi, _ = server.minta("/daftar?jalur=cek")
    assert re.search(r'<input[^>]*type="tel"[^>]*name="wa"[^>]*>', isi)
    campur = re.search(r'<input[^>]*name="wa"[^>]*>', isi).group(0)
    assert 'autocomplete="tel"' in campur and " required" in campur
    assert '<input type="hidden" name="jalur" value="cek">' in isi
    assert registration_contact.COPY_FUNNEL_WA in isi
    assert "Tidak perlu email atau nomor telepon" not in isi


def test_get_tanpa_jalur_saat_sakelar_hidup_tetap_form_lama(server, funnel_hidup):
    _, biasa, _ = server.minta("/daftar")
    assert 'name="wa"' not in biasa and "Tidak perlu email atau nomor telepon" in biasa
    _, aneh, _ = server.minta("/daftar?jalur=lain")
    assert _tanpa_token(aneh) == _tanpa_token(biasa)


def test_post_jalur_cek_saat_sakelar_mati_ditolak_tanpa_menyimpan(server, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    data = _ambil_form(server, jalur="/daftar")
    kode, isi, header = _post(server, {**data, "jalur": "cek", "wa": WA_MASUKAN})
    assert kode == 400 and "Set-Cookie" not in header
    assert WA_MASUKAN not in isi
    _tidak_ada_efek(server)


@pytest.mark.parametrize("hidup", [False, True])
def test_post_biasa_membawa_wa_ditolak_tanpa_menyimpan(server, monkeypatch, hidup):
    monkeypatch.setenv("FUNNEL_AKTIF", "1" if hidup else "0")
    data = _ambil_form(server, jalur="/daftar")
    kode, isi, header = _post(server, {**data, "wa": WA_MASUKAN})
    assert kode == 400 and "Set-Cookie" not in header
    assert WA_MASUKAN not in isi
    _tidak_ada_efek(server)


def test_post_jalur_selain_cek_ditolak(server, funnel_hidup):
    data = _ambil_form(server)
    kode, _, header = _post(server, {**data, "jalur": "lain", "wa": WA_MASUKAN})
    assert kode == 400 and "Set-Cookie" not in header
    _tidak_ada_efek(server)


def test_post_jalur_cek_tanpa_wa_ditolak_tanpa_akun_siswa_kontak(server, funnel_hidup):
    data = _ambil_form(server)
    kode, isi, header = _post(server, {**data, "jalur": "cek"})
    assert kode == 200 and "Set-Cookie" not in header
    assert "nomor WhatsApp" in _teks_pesan(isi)
    assert 'name="wa"' in isi and 'name="jalur" value="cek"' in isi
    _tidak_ada_efek(server)


@pytest.mark.parametrize("wa", ["", "   ", "12345", "abcdefghijk", "0812", "+1234567890123",
                                "08123456789012345678901234567890123"])
def test_post_wa_tidak_valid_ditolak_dan_tidak_diulang_di_galat(server, funnel_hidup, wa):
    data = _ambil_form(server)
    kode, isi, header = _post(server, {**data, "jalur": "cek", "wa": wa})
    assert kode == 200 and "Set-Cookie" not in header
    pesan = _teks_pesan(isi)
    assert "nomor WhatsApp" in pesan
    if wa.strip():
        assert wa.strip() not in pesan
    _tidak_ada_efek(server)


def test_wa_diecho_di_input_dengan_escape_saat_validasi_gagal(server, funnel_hidup):
    data = _ambil_form(server)
    _, isi, _ = _post(server, {**data, "jalur": "cek", "wa": '"><b>x</b>'})
    assert '"><b>x</b>' not in isi
    assert "&quot;&gt;&lt;b&gt;x&lt;/b&gt;" in isi


def test_post_wa_valid_membuat_akun_siswa_dan_kontak_per_id_akun(server, funnel_hidup):
    data = _ambil_form(server)
    kode, _, header = _post(server, {**data, "jalur": "cek", "wa": WA_MASUKAN})
    assert kode == 303 and "Set-Cookie" in header
    akun = auth.cari_akun("ortu-funnel")
    siswa, kontak, _ = _keadaan(server)
    assert siswa == 1
    assert kontak == [(akun["id_akun"], WA_NORMAL)]
    assert all(baris[0] != "ortu-funnel" for baris in kontak)
    with server.buka() as kon:
        assert kontak_akun.ambil(kon, akun["id_akun"])["wa"] == WA_NORMAL


def test_post_replay_sama_idempoten_dan_wa_beda_ditolak(server, funnel_hidup):
    data = {**_ambil_form(server), "jalur": "cek", "wa": WA_MASUKAN}
    assert _post(server, data)[0] == 303
    awal = auth.BERKAS_SANDI.read_bytes()
    assert _post(server, data)[0] == 303
    assert auth.BERKAS_SANDI.read_bytes() == awal
    akun = auth.cari_akun("ortu-funnel")
    assert _keadaan(server)[:2] == (1, [(akun["id_akun"], WA_NORMAL)])
    kode, _, header = _post(server, {**data, "wa": "0855-5123-4567"})
    assert kode == 400 and "Set-Cookie" not in header
    assert _keadaan(server)[:2] == (1, [(akun["id_akun"], WA_NORMAL)])
    assert auth.BERKAS_SANDI.read_bytes() == awal


def test_post_simpan_kontak_gagal_tidak_meninggalkan_akun_separuh(server, funnel_hidup, monkeypatch):
    def rusak(*_a, **_kw):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(kontak_akun, "simpan", rusak)
    data = {**_ambil_form(server), "jalur": "cek", "wa": WA_MASUKAN}
    kode, isi, header = _post(server, data)
    assert kode == 503 and "Set-Cookie" not in header
    assert WA_MASUKAN not in _teks_pesan(isi)
    _tidak_ada_efek(server)


def test_jalur_biasa_tanpa_wa_tetap_berjalan_dan_tanpa_kontak(server, funnel_hidup):
    data = _ambil_form(server, jalur="/daftar")
    kode, _, _ = _post(server, data)
    assert kode == 303
    siswa, kontak, _ = _keadaan(server)
    assert siswa == 1 and kontak == []
    with server.buka() as kon:
        sidik = kon.execute("SELECT sidik_perintah FROM registrasi_profil_anak").fetchone()[0]
    assert re.fullmatch(r"[0-9a-f]{64}", sidik)


# --- nomor tidak bocor -----------------------------------------------------

def test_nomor_tidak_bocor_ke_analitik_log_url_dan_berkas_auth(server, funnel_hidup, monkeypatch, capfd, caplog):
    dicatat = []
    asli = product_analytics_http.setelah_daftar

    def rekam(*args, **kwargs):
        dicatat.append(repr((args, kwargs)))
        return asli(*args, **kwargs)

    monkeypatch.setattr(product_analytics_http, "setelah_daftar", rekam)
    data = {**_ambil_form(server), "jalur": "cek", "wa": WA_MASUKAN, "analitik": "1"}
    kode, isi, header = _post(server, data)
    assert kode == 303
    assert dicatat, "analitik.setelah_daftar tidak terpanggil"
    keluaran = capfd.readouterr()
    sisa = [WA_NORMAL, WA_MASUKAN, WA_MASUKAN.replace("-", "")]
    jejak = [
        ("analitik", "".join(dicatat)),
        ("stdout", keluaran.out), ("stderr", keluaran.err), ("log", caplog.text),
        ("Location", header.get("Location", "")), ("Set-Cookie", header.get("Set-Cookie", "")),
        ("sandi.json", auth.BERKAS_SANDI.read_text()),
        ("admin.db", admin_store.BAWAAN.read_bytes().decode("latin-1")),
        ("isi", isi),
    ]
    for nama, teks in jejak:
        for angka in sisa:
            assert angka not in teks, f"nomor muncul di {nama}"


def test_nomor_hanya_ada_di_tabel_kontak_akun(server, funnel_hidup):
    data = {**_ambil_form(server), "jalur": "cek", "wa": WA_MASUKAN}
    assert _post(server, data)[0] == 303
    with server.buka() as kon:
        ada = [t for (t,) in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")
               if any(WA_NORMAL in str(sel)
                      for baris in kon.execute(f'SELECT * FROM "{t}"') for sel in baris)]
    assert ada == ["kontak_akun"]


def test_llm_tidak_menyentuh_kontak():
    import llm
    with open(llm.__file__, encoding="utf-8") as berkas:
        sumber = berkas.read()
    assert "kontak_akun" not in sumber and "registration_contact" not in sumber
