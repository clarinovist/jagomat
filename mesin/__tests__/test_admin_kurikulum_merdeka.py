"""Halaman admin `/admin/kurikulum` (tabel Kurikulum Merdeka) dan `/admin/kurikulum/buat` (Buat soal). Data sintetis."""
from __future__ import annotations

from dataclasses import replace
import re
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurikulum_kelas as kk  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)

RUTE = "/admin/kurikulum"
RUTE_DETAIL = "/admin/kurikulum/cp-detail"
RUTE_BUAT = "/admin/kurikulum/buat"
RUTE_EDIT_CP = "/admin/kurikulum/cp?grup=aritmatika-lanjut%2Fkonversi"
DIR_RENDER = Path(tempfile.gettempdir()) / "jagomat-render"
POLA_SEL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
POLA_DIPAKAI = re.compile(r"Dipakai: ([^<]*)")


def _dipakai(sel) -> str:
    """Nilai "Dipakai" dari sel Jumlah soal (indeks 3)."""
    return POLA_DIPAKAI.search(sel[3]).group(1)
BATAS_RENDER_DETIK = 2.0


@pytest.fixture(autouse=True)
def _sakelar_mati(monkeypatch):
    """Hasil tak bergantung env mesin: sakelar jenis baru mati kecuali tes yang menyalakannya."""
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "0")
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "0")
    monkeypatch.delenv("OSN_MATEMATIKA_AWAL", raising=False)  # bawaan 1 (menyala)


@pytest.fixture
def bab_tanpa_pelatih(monkeypatch):
    """K1 B4 tanpa pelatih. Data nyata tak lagi punya bab "belum" (21 Nov 2026), jadi kontrak
    tampilan bab tanpa jenis soal diuji dengan data yang disimulasikan, bukan dengan bab nyata."""
    kelas = tuple(
        replace(k, bab=tuple(replace(b, pelatih=()) if (k.kelas, b.nomor) == (1, 4) else b
                             for b in k.bab))
        for k in kk.KELAS)
    monkeypatch.setattr(kk, "KELAS", kelas)


def _admin(server):
    return _login(server, "Admin-C", SANDI_ADMIN)


def _baris(isi: str, kelas: int, bab: int) -> list:
    """Sel-sel baris tabel untuk (kelas, bab)."""
    kartu = isi[isi.index('id="kelas-%d"' % kelas):]
    kartu = kartu[:kartu.index("</section>")]
    for baris in kartu.split("<tr>")[1:]:
        sel = POLA_SEL.findall(baris)
        if sel and sel[0] == str(bab):
            return sel
    raise AssertionError((kelas, bab))


def _jumlah_soal_db(server) -> int:
    with server.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM soal").fetchone()[0]


def _sisip_soal(server, template_id: str, level: str, banyak: int) -> None:
    with server.buka() as kon:
        for i in range(banyak):
            kon.execute(
                "INSERT INTO soal (tanda_tangan, template_id, parameter, kunci, level) VALUES (?, ?, '{}', '1', ?)",
                ("sintetis|%s|%s|%d" % (level, template_id, i), template_id, level))


# --- akses ---------------------------------------------------------------------------------

@pytest.mark.parametrize("jalur", [RUTE, RUTE_DETAIL, RUTE_BUAT + "?kelas=3&bab=1"])
def test_anonim_dan_guru_404_identik_tanpa_isi(server, jalur):
    acuan = _minta(server, "/admin/tidak-ada")[:2]
    anonim = _minta(server, jalur)[:2]
    guru = _minta(server, jalur, auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    assert anonim == guru == acuan and acuan[0] == 404


@pytest.mark.parametrize("jalur", [RUTE, RUTE_DETAIL, RUTE_BUAT + "?kelas=3&bab=1"])
def test_admin_200_tanpa_skrip_dan_privat(server, jalur):
    kode, isi, header = _minta(server, jalur, cookie=_admin(server))
    assert kode == 200 and "<script" not in isi and header["Cache-Control"] == "no-store"


# --- tabel ---------------------------------------------------------------------------------

def test_tabel_memuat_enam_kelas_empat_puluh_bab_dan_kolom_lengkap(server):
    isi = _minta(server, RUTE, cookie=_admin(server))[1]
    assert len(re.findall(r'<h2 id="kelas-\d">Kelas \d</h2>', isi)) == 6
    assert len(re.findall(r"<tr><td>\d+</td>", isi)) == 40
    for kolom in ("No", "Materi dan sub-materi", "Soal Jagomat", "Jumlah soal", "Status"):
        assert isi.count('<th scope="col">%s</th>' % kolom) == 6
    assert kk.SUMBER_BAB in isi and "Total 40 bab" in isi
    assert "Pengayaan di luar buku" in isi and '<div class="admin-tabel-wrap"' in isi


def test_status_dihitung_dari_level_kelas(server):
    isi = _minta(server, RUTE, cookie=_admin(server))[1]
    assert "<strong>Perlu disempurnakan</strong>" in _baris(isi, 1, 4)[4]  # kenali_bentuk (sebagian)
    assert "Belum ada soal" not in isi  # tak ada bab "belum" di data nyata
    assert "<strong>Sudah ada soal</strong>" in _baris(isi, 1, 2)[4]
    # K1 B6 naik ke "ada" lewat tambah_kurang_20; K1 B7 naik lewat satuan tak baku bergambar (adegan_awal).
    assert "<strong>Sudah ada soal</strong>" in _baris(isi, 1, 6)[4]
    assert "<strong>Sudah ada soal</strong>" in _baris(isi, 1, 7)[4]


def test_status_belum_ada_soal_untuk_bab_tanpa_pelatih(server, bab_tanpa_pelatih):
    sel = _baris(_minta(server, RUTE, cookie=_admin(server))[1], 1, 4)
    assert "<strong>Belum ada soal</strong>" in sel[4] and "Buat soal" not in sel[4]


def test_pelatih_yang_belum_ada_di_kelas_itu_diberi_catatan(server):
    # K2 B4: pelatih lama (pola-bilangan/siklus) baru ada di kelas 3+, pelatih baru (pola_posisi) ada di
    # kelas 2 dan menaikkan bab ke "Sudah ada soal" (keputusan pemilik 21 Nov 2026); catatan kelas lain tetap tampil.
    sel = _baris(_minta(server, RUTE, cookie=_admin(server))[1], 2, 4)
    assert "baru ada di kelas 3, 4, 5, 6" in sel[2] and "Matematika Awal" in sel[2]
    assert "Sudah ada soal" in sel[4] and "Perlu disempurnakan" not in sel[4] and "Belum ada soal" not in sel[4]


def test_aksi_buat_soal_hanya_bila_ada_jenis_yang_bisa_dibuat(server, bab_tanpa_pelatih, monkeypatch):
    monkeypatch.setenv("OSN_MATEMATIKA_AWAL", "0")  # K1 bab 1: jenis lama dan baru sama-sama tertutup
    isi = _minta(server, RUTE, cookie=_admin(server))[1]
    assert 'href="/admin/kurikulum/buat?kelas=3&amp;bab=1"' in _baris(isi, 3, 1)[4]
    assert "Buat soal" not in _baris(isi, 1, 4)[4]
    # K1 bab 1 hanya punya jenis yang sakelarnya mati: tidak ada tautan, variasi jujur 0 + catatan.
    sel = _baris(isi, 1, 1)
    assert "Buat soal" not in sel[4] and "belum dinyalakan" in sel[3]


def test_bab_k1_b1_bisa_dibuat_lewat_jenis_baru_walau_pelatih_lama_tertutup(server):
    # Sakelar matematika-awal bawaan 1: bilang_benda_awal terbuka walau bilangan-dasar masih tertutup.
    sel = _baris(_minta(server, RUTE, cookie=_admin(server))[1], 1, 1)
    assert "Buat soal" in sel[4] and "<strong>Sudah ada soal</strong>" in sel[4]


def test_sakelar_menyala_membuka_variasi_dan_tautan(server, monkeypatch):
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    sel = _baris(_minta(server, RUTE, cookie=_admin(server))[1], 1, 1)
    assert "Buat soal" in sel[4] and "belum dinyalakan" not in sel[3]


def test_sudah_dipakai_menghitung_template_dan_level_yang_tepat(server):
    admin = _admin(server)
    awal = int(_dipakai(_baris(_minta(server, RUTE, cookie=admin)[1], 1, 2)))
    awal_k2 = int(_dipakai(_baris(_minta(server, RUTE, cookie=admin)[1], 2, 2)))
    _sisip_soal(server, "tambah_dasar", "P1", 3)
    _sisip_soal(server, "tambah_dasar", "P2", 2)
    isi = _minta(server, RUTE, cookie=admin)[1]
    assert int(_dipakai(_baris(isi, 1, 2))) == awal + 3  # level P2 tidak ikut
    assert int(_dipakai(_baris(isi, 2, 2))) == awal_k2 + 2  # level P1 tidak ikut


def test_db_rusak_sudah_dipakai_strip_dan_halaman_tetap_200(server):
    admin = _admin(server)
    server.db.write_bytes(b"bukan sqlite sama sekali")
    kode, isi, _t = _minta(server, RUTE, cookie=admin)
    assert kode == 200 and _dipakai(_baris(isi, 1, 2)) == "–"
    assert "belum bisa dibaca" in isi
    assert str(server.db) not in isi


def test_waktu_render_di_bawah_batas(server):
    admin = _admin(server)
    _minta(server, RUTE, cookie=admin)  # pemanasan cache variasi
    mulai = time.perf_counter()
    assert _minta(server, RUTE, cookie=admin)[0] == 200
    assert time.perf_counter() - mulai < BATAS_RENDER_DETIK


def test_query_apa_pun_di_tabel_404(server):
    assert _minta(server, RUTE + "?x=1", cookie=_admin(server))[0] == 404


# --- tab dan Detail CP ----------------------------------------------------------------------

def _tab_aktif(isi: str) -> list:
    return re.findall(r'<a class="admin-tab" href="[^"]*" aria-current="page">([^<]+)</a>', isi)


def test_tab_aktif_benar_di_semua_halaman(server):
    admin = _admin(server)
    for jalur, nama in ((RUTE, "Kurikulum Merdeka"), (RUTE_DETAIL, "Detail CP"),
                        (RUTE_BUAT + "?kelas=3&bab=1", "Kurikulum Merdeka"),
                        ("/admin/cek-topik", "Topik cek"), (RUTE_EDIT_CP, "Detail CP")):
        isi = _minta(server, jalur, cookie=admin)[1]
        assert _tab_aktif(isi) == [nama], jalur
        assert isi.count('class="admin-tab"') == 3


def test_detail_cp_memuat_isi_lama_dan_tautan_ubah(server):
    isi = _minta(server, RUTE_DETAIL, cookie=_admin(server))[1]
    assert "disahkan pemilik" in isi and "Celah cakupan SD" in isi
    assert 'href="/admin/kurikulum/cp?grup=' in isi and ">Ubah</a>" in isi
    assert "Butir CP per fase" in isi


def test_halaman_edit_cp_kembali_ke_detail_cp(server):
    isi = _minta(server, RUTE_EDIT_CP, cookie=_admin(server))[1]
    assert 'href="/admin/kurikulum/cp-detail">&larr; Kembali ke Detail CP</a>' in isi


# --- Buat soal -----------------------------------------------------------------------------

def _item(isi: str) -> list:
    daftar = isi[isi.index('<ol class="kur-soal-daftar">'):]
    return re.findall(r"<li><p class=\"admin-meta\">Soal (\d+) · ([^<]*)</p>", daftar)


def test_buat_soal_sah_menampilkan_jumlah_soal_kunci_dan_seed(server):
    kode, isi, _t = _minta(server, RUTE_BUAT + "?kelas=3&bab=1&jumlah=10&seed=7", cookie=_admin(server))
    assert kode == 200
    assert len(_item(isi)) == 10 and isi.count("Kunci jawaban:") == 10
    assert "Seed: 7" in isi and "seed=7" in isi
    assert "Buat ulang dengan soal lain" in isi and "Soal ini belum tersimpan" in isi
    assert '<select name="jumlah">' in isi and 'name="seed" value="7"' in isi


def test_buat_soal_tanpa_seed_mengundi_dan_menampilkannya(server):
    isi = _minta(server, RUTE_BUAT + "?kelas=3&bab=1", cookie=_admin(server))[1]
    seed = int(re.search(r"Seed: (\d+)", isi).group(1))
    assert 1 <= seed <= 2 ** 31 and len(_item(isi)) == 10


def test_buat_soal_seed_sama_sama_dan_beda_seed_beda(server):
    admin = _admin(server)

    def teks(seed):
        isi = _minta(server, RUTE_BUAT + "?kelas=5&bab=1&jumlah=10&seed=%d" % seed, cookie=admin)[1]
        return isi[isi.index('<ol class="kur-soal-daftar">'):]

    assert teks(11) == teks(11) and teks(11) != teks(12)


@pytest.mark.parametrize("jumlah", [5, 10, 20, 30])
def test_buat_soal_jumlah_yang_diizinkan(server, jumlah):
    isi = _minta(server, RUTE_BUAT + "?kelas=5&bab=1&jumlah=%d&seed=3" % jumlah, cookie=_admin(server))[1]
    assert len(_item(isi)) == jumlah


@pytest.mark.parametrize("query", [
    "kelas=7&bab=1", "kelas=0&bab=1", "kelas=3&bab=99", "kelas=3&bab=0", "kelas=3", "bab=1", "",
    "kelas=3&bab=1&jumlah=15", "kelas=3&bab=1&jumlah=", "kelas=3&bab=1&seed=abc", "kelas=3&bab=1&seed=0",
    "kelas=3&bab=1&seed=2147483649", "kelas=3&bab=1&seed=-5", "kelas=3&bab=1&seed=1.5",
    "kelas=3&bab=1&x=1", "kelas=3&kelas=3&bab=1", "kelas=03&bab=1", "kelas=%EF%BC%93&bab=1",
    "kelas=3&bab=1&seed=" + "9" * 40,
])
def test_buat_soal_query_tak_sah_404(server, query):
    kode, isi, _t = _minta(server, RUTE_BUAT + "?" + query, cookie=_admin(server))
    assert kode == 404 and "Kunci jawaban" not in isi


def test_buat_soal_seed_batas_atas_sah(server):
    assert _minta(server, RUTE_BUAT + "?kelas=3&bab=1&seed=2147483648", cookie=_admin(server))[0] == 200


def test_bab_tanpa_pelatih_pesan_jujur(server, bab_tanpa_pelatih):
    kode, isi, _t = _minta(server, RUTE_BUAT + "?kelas=1&bab=4", cookie=_admin(server))
    assert kode == 200 and "Bab ini belum punya jenis soal di kelas 1." in isi and "Kunci jawaban" not in isi


def test_bab_dengan_jenis_belum_dinyalakan_pesan_jujur(server, monkeypatch):
    monkeypatch.setenv("OSN_MATEMATIKA_AWAL", "0")
    isi = _minta(server, RUTE_BUAT + "?kelas=1&bab=1", cookie=_admin(server))[1]
    assert "belum dinyalakan" in isi and "Kunci jawaban" not in isi


def test_sakelar_menyala_bab_dasar_bisa_dibuat(server, monkeypatch):
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    isi = _minta(server, RUTE_BUAT + "?kelas=1&bab=1&seed=4", cookie=_admin(server))[1]
    assert len(_item(isi)) == 10


def test_jumlah_terbesar_tercapai_bila_variasi_cukup(server, monkeypatch):
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    isi = _minta(server, RUTE_BUAT + "?kelas=1&bab=5&jumlah=30&seed=4", cookie=_admin(server))[1]
    assert len(_item(isi)) == 30  # nilai_tempat 20 + bandingkan 218: cukup
    isi = _minta(server, RUTE_BUAT + "?kelas=4&bab=3&jumlah=30&seed=4", cookie=_admin(server))[1]
    assert len(_item(isi)) == 30


def test_buat_soal_tidak_menulis_db(server):
    admin = _admin(server)
    sebelum = _jumlah_soal_db(server)
    for seed in (1, 2, 3):
        assert _minta(server, RUTE_BUAT + "?kelas=5&bab=1&jumlah=30&seed=%d" % seed, cookie=admin)[0] == 200
    assert _minta(server, RUTE, cookie=admin)[0] == 200
    assert _jumlah_soal_db(server) == sebelum


def test_simpan_render_sintetis(server):
    admin = _admin(server)
    DIR_RENDER.mkdir(parents=True, exist_ok=True)
    for nama, jalur in (("kurikulum-merdeka.html", RUTE),
                        ("kurikulum-buat.html", RUTE_BUAT + "?kelas=3&bab=1&jumlah=10&seed=2026"),
                        ("kurikulum-cp-detail.html", RUTE_DETAIL)):
        (DIR_RENDER / nama).write_text(_minta(server, jalur, cookie=admin)[1], "utf-8")
