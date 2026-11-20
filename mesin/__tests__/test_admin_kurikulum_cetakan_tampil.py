"""Cetakan aktif di tabel Kurikulum Merdeka dan Buat soal, escape stored-XSS, invarian draf/nonaktif, DB rusak (C2).

Data SINTETIS. Hanya `aktif_untuk_bab` yang dibaca di luar halaman cetakan admin; draf dan nonaktif tidak pernah tampil.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_kurikulum_buat_pages as buat_ui  # noqa: E402
import admin_kurikulum_cetakan_pages as ui  # noqa: E402
import cetakan_pola as pola  # noqa: E402
import cetakan_store as store  # noqa: E402
import kurikulum_buat_soal as buat  # noqa: E402
import kurikulum_kelas_hitung as hitung  # noqa: E402
from admin_transfer_kit import login_admin, minta_admin  # noqa: E402
from cetakan_admin_kit import (  # noqa: E402
    BAB_ADA, BAB_BELUM, JUDUL, aktifkan_langsung, buat_langsung, isi_sah, kirim_buat, kirim_pindah,
)
from pesanan_transfer_http_kit import jam, keluarga, server, tertutup  # noqa: E402,F401

RUTE_TABEL = "/admin/kurikulum"
RUTE_BUAT = "/admin/kurikulum/buat"
POLA_SEL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
JUDUL_PENANDA = "Penanda cetakan unik zzq"
PAYLOAD = 'Ani & "Budi" \'Cici\''
PAYLOAD_TER_ESCAPE = ("Ani &amp; &quot;Budi&quot; &#x27;Cici&#x27;",)


@pytest.fixture(autouse=True)
def _lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_BERKAS_DB, str(tmp_path / "cetakan.db"))
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "0")
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "0")
    store.bersihkan_cache()
    yield
    store.bersihkan_cache()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


def _baris(isi: str, kelas: int, bab: int) -> list:
    kartu = isi[isi.index('id="kelas-%d"' % kelas):]
    kartu = kartu[:kartu.index("</section>")]
    for baris in kartu.split("<tr>")[1:]:
        sel = POLA_SEL.findall(baris)
        if sel and sel[0] == str(bab):
            return sel
    raise AssertionError((kelas, bab))


def _tabel(server, cookie, kelas, bab) -> list:
    kode, isi, _t = minta_admin(server, RUTE_TABEL, cookie)
    assert kode == 200
    return _baris(isi, kelas, bab)


def _buat_soal(server, cookie, bab=BAB_BELUM, jumlah=10, seed=7):
    return minta_admin(server, "%s?kelas=%d&bab=%d&jumlah=%d&seed=%d" % (RUTE_BUAT, *bab, jumlah, seed), cookie)


def _aktif(judul=JUDUL_PENANDA, bab=BAB_BELUM, **kw):
    return aktifkan_langsung(buat_langsung(bab=bab, judul=judul, **kw))


# --- tabel ----------------------------------------------------------------------------------

def test_tabel_tanpa_cetakan_tidak_berubah_dan_semua_bab_punya_tautan_kelola(tertutup, admin):
    isi = minta_admin(tertutup, RUTE_TABEL, admin)[1]
    assert "Cetakan:" not in isi.split('<section class="admin-kartu admin-kartu-tabel"', 1)[1]
    assert len(re.findall(r'href="%s\?kelas=\d&amp;bab=\d"' % ui.RUTE, isi)) == 40  # 40 bab
    sel = _baris(isi, *BAB_BELUM)
    assert "Belum ada soal" in sel[4] and "Jenis: 0" in sel[3] and "Buat soal" not in sel[4]
    assert 'href="%s?kelas=2&amp;bab=3"' % ui.RUTE in sel[4]


def test_cetakan_aktif_menjadikan_bab_belum_menjadi_sebagian_dengan_jenis_variasi_dan_tautan(tertutup, admin):
    _aktif()
    sel = _tabel(tertutup, admin, *BAB_BELUM)
    assert "Perlu disempurnakan" in sel[4] and "Belum ada soal" not in sel[4]
    assert "Cetakan: %s" % JUDUL_PENANDA in sel[2]
    assert "Jenis: 1" in sel[3] and "Variasi: banyak" in sel[3] and "Dipakai: 0" in sel[3]
    assert "Buat soal" in sel[4] and "Kelola cetakan" in sel[4]


def test_bab_yang_sudah_ada_soal_kode_tetap_ada_dan_jenis_bertambah(tertutup, admin):
    sebelum = _tabel(tertutup, admin, *BAB_ADA)
    jenis_awal = int(re.search(r"Jenis: (\d+)", sebelum[3]).group(1))
    _aktif(bab=BAB_ADA)
    sel = _tabel(tertutup, admin, *BAB_ADA)
    assert "Sudah ada soal" in sel[4] and "Cetakan: %s" % JUDUL_PENANDA in sel[2]
    assert int(re.search(r"Jenis: (\d+)", sel[3]).group(1)) == jenis_awal + 1 and "Variasi: banyak" in sel[3]
    assert "Dipakai: " + re.search(r"Dipakai: ([^<]*)", sebelum[3]).group(1) in sel[3]  # kolom Dipakai tak berubah


def test_variasi_cetakan_tidak_menjalankan_uji_kelayakan_atau_sampel_saat_render(tertutup, admin, monkeypatch):
    _aktif()

    def gagal(*_a, **_k):
        raise AssertionError("tabel tidak boleh menjalankan cetakan")

    for nama in ("uji_kelayakan", "buat_soal", "contoh"):
        monkeypatch.setattr(pola, nama, gagal)
    sel = _tabel(tertutup, admin, *BAB_BELUM)
    assert "Variasi: banyak" in sel[3]


def test_draf_dan_nonaktif_tidak_pernah_tampil_di_tabel_dan_buat_soal(tertutup, admin):
    buat_langsung(bab=BAB_BELUM, judul="Judul draf rahasia aaa")
    item = aktifkan_langsung(buat_langsung(bab=BAB_BELUM, judul="Judul nonaktif bbb"))
    store.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=item.revisi)
    isi = minta_admin(tertutup, RUTE_TABEL, admin)[1]
    assert "Judul draf rahasia aaa" not in isi and "Judul nonaktif bbb" not in isi
    sel = _baris(isi, *BAB_BELUM)
    assert "Belum ada soal" in sel[4] and "Jenis: 0" in sel[3]
    kode, halaman, _t = _buat_soal(tertutup, admin)
    assert kode == 200 and "Judul draf rahasia aaa" not in halaman and "Judul nonaktif bbb" not in halaman
    assert "belum punya jenis soal" in halaman and 'class="kur-soal"' not in halaman.rsplit("</style>", 1)[-1]


def test_nonaktifkan_lewat_http_langsung_menghilang_dari_tabel_dan_buat_soal(tertutup, admin):
    item = _aktif()
    assert JUDUL_PENANDA in _tabel(tertutup, admin, *BAB_BELUM)[2] and JUDUL_PENANDA in _buat_soal(tertutup, admin)[1]
    assert kirim_pindah(tertutup, admin, ui.AKSI_NONAKTIFKAN, item.id, item.revisi)[0] == 303
    assert JUDUL_PENANDA not in _tabel(tertutup, admin, *BAB_BELUM)[2]
    assert JUDUL_PENANDA not in _buat_soal(tertutup, admin)[1]
    hidup = kirim_pindah(tertutup, admin, ui.AKSI_AKTIFKAN, item.id, item.revisi + 1)
    assert hidup[0] == 303 and JUDUL_PENANDA in _tabel(tertutup, admin, *BAB_BELUM)[2]


def test_status_dan_variasi_hitung_unit_tanpa_http():
    kelas, bab = hitung.cari_bab(*BAB_BELUM)
    assert hitung.ringkasan_bab(bab, kelas.kelas, {}).status == hitung.STATUS_BELUM
    _aktif()
    ringkas = hitung.ringkasan_bab(bab, kelas.kelas, {})
    assert ringkas.status == hitung.STATUS_SEBAGIAN and ringkas.jenis == 1 and len(ringkas.cetakan) == 1
    assert ringkas.variasi.jenis == hitung.JENIS_BANYAK and ringkas.variasi.total == 0


# --- Buat soal ------------------------------------------------------------------------------

def test_buat_soal_bab_tanpa_soal_kode_tetapi_punya_cetakan_aktif_menghasilkan_soal_berlabel(tertutup, admin):
    _aktif()
    kode, isi, _t = _buat_soal(tertutup, admin, jumlah=10)
    assert kode == 200 and len(re.findall(r"Soal \d+ · Cetakan: %s" % JUDUL_PENANDA, isi)) == 10
    for teks, kunci in re.findall(r'<div class="kur-soal"><p>(.*?)</p></div><p class="kur-kunci"><strong>Kunci jawaban:'
                                  r'</strong> (\d+)</p>', isi):
        a, b = map(int, re.search(r"punya (\d+) kelereng\. Ia diberi (\d+) kelereng", teks).groups())
        assert int(kunci) == a + b  # kunci dihitung mesin
    assert "belum punya jenis soal" not in isi and "Hanya" not in isi  # tidak kekurangan soal


def test_buat_soal_campuran_kode_dan_cetakan_bergiliran_dan_deterministik(tertutup, admin):
    _aktif(bab=BAB_ADA)
    isi = _buat_soal(tertutup, admin, bab=BAB_ADA, jumlah=10)[1]
    label = re.findall(r'<p class="admin-meta">Soal \d+ · ([^<]*)</p>', isi)
    assert len(label) == 10 and "Cetakan: %s" % JUDUL_PENANDA in label
    assert any(not x.startswith("Cetakan:") for x in label)  # soal kode tetap ikut
    assert label[0] != label[1] or len(set(label)) > 1  # bergiliran, bukan blok
    ulang = _buat_soal(tertutup, admin, bab=BAB_ADA, jumlah=10)[1]  # seed sama, hasil sama (token tema beda)
    daftar = lambda h: re.search(r'<ol class="kur-soal-daftar">.*?</ol>', h, re.S).group(0)  # noqa: E731
    assert daftar(ulang) == daftar(isi)


def test_buat_soal_cetakan_langsung_deterministik_dan_unik():
    kelas, bab = hitung.cari_bab(*BAB_BELUM)
    _aktif()
    satu = buat.buat_soal_bab(kelas.kelas, bab, 20, seed=11)
    dua = buat.buat_soal_bab(kelas.kelas, bab, 20, seed=11)
    lain = buat.buat_soal_bab(kelas.kelas, bab, 20, seed=12)
    assert satu == dua and satu != lain
    tanda = [i.soal.tanda_tangan for i in satu.item]
    assert len(tanda) == 20 == len(set(tanda)) and satu.ada_pelatih and satu.bisa_dibuat
    assert all(isinstance(i, buat.ItemSoalCetakan) and i.judul == JUDUL_PENANDA for i in satu.item)


def test_buat_soal_melewati_seed_gagal_tanpa_500(tertutup, admin):
    """Syarat yang sering gagal dan kunci yang bisa negatif: seed gagal dilewati, halaman tetap 200."""
    item = buat_langsung({
        "kelas": BAB_BELUM[0], "bab": BAB_BELUM[1], "judul": "Pengurangan berisiko negatif",
        "teks": "{a} dikurangi {b} berapa?", "variabel": {"a": [1, 400], "b": [1, 400]}, "nama": False,
        "syarat": ["a % 7 == 0"], "kunci": "a - b"})
    assert pola.uji_kelayakan(item.cetakan).lolos is False  # ada kunci negatif: tak boleh disetujui
    store.bersihkan_cache()
    # Paksa aktif lewat SQL (keadaan buruk): Buat soal tetap tidak boleh 500.
    import sqlite3
    with sqlite3.connect(store._path_db(None)) as kon:
        kon.execute("UPDATE cetakan SET status = 'aktif' WHERE id = ?", (item.id,))
    store.bersihkan_cache()
    kode, isi, _t = _buat_soal(tertutup, admin)
    assert kode == 200 and "Pengurangan berisiko negatif" in isi
    kunci = [int(k) for k in re.findall(r"Kunci jawaban:</strong> (\d+)</p>", isi)]
    assert kunci and all(k >= 0 for k in kunci)


def test_buat_soal_tetap_get_dan_tidak_menulis_db_cetakan(tertutup, admin):
    _aktif()
    sebelum = store._path_db(None).read_bytes()
    _buat_soal(tertutup, admin)
    assert store._path_db(None).read_bytes() == sebelum


# --- DB rusak -------------------------------------------------------------------------------

@pytest.mark.parametrize("isi_berkas", [b"bukan sqlite sama sekali", b""], ids=["rusak", "kosong"])
def test_db_cetakan_rusak_tabel_dan_buat_soal_tetap_200_dengan_soal_kode_saja(tertutup, admin, isi_berkas):
    store._path_db(None).write_bytes(isi_berkas)
    store.bersihkan_cache()
    kode, isi, _t = minta_admin(tertutup, RUTE_TABEL, admin)
    assert kode == 200 and "Cetakan:" not in isi.split('<section class="admin-kartu admin-kartu-tabel"', 1)[1]
    sel = _baris(isi, *BAB_ADA)
    assert "Sudah ada soal" in sel[4]
    kode, isi, _t = _buat_soal(tertutup, admin, bab=BAB_ADA)
    assert kode == 200 and "Soal 1 ·" in isi and "Cetakan:" not in isi
    assert minta_admin(tertutup, "/admin/kurikulum/cp-detail", admin)[0] == 200


def test_db_cetakan_tidak_ada_tabel_tetap_jalan(tertutup, admin):
    assert not store._path_db(None).exists()
    assert minta_admin(tertutup, RUTE_TABEL, admin)[0] == 200
    assert _buat_soal(tertutup, admin, bab=BAB_ADA)[0] == 200


# --- escape (stored-XSS) --------------------------------------------------------------------

def _cetakan_berbahaya():
    return buat_langsung({
        "kelas": BAB_BELUM[0], "bab": BAB_BELUM[1], "judul": "Judul " + PAYLOAD,
        "teks": "Teks " + PAYLOAD + " {a} dan {b}?", "variabel": {"a": [1, 40], "b": [1, 40]}, "nama": False,
        "syarat": [], "kunci": "a + b", "pembahasan": "Bahas " + PAYLOAD + " = {kunci}"})


def test_karakter_html_di_isi_cetakan_ter_escape_di_semua_permukaan(tertutup, admin):
    item = aktifkan_langsung(_cetakan_berbahaya())
    halaman = {
        "daftar": minta_admin(tertutup, "%s?kelas=2&bab=3" % ui.RUTE, admin)[1],
        "periksa": minta_admin(tertutup, "%s?id=%d" % (ui.RUTE_PERIKSA, item.id), admin)[1],
        "tabel": minta_admin(tertutup, RUTE_TABEL, admin)[1],
        "buat": _buat_soal(tertutup, admin)[1],
    }
    for nama, isi in halaman.items():
        badan = isi.rsplit("</style>", 1)[-1]
        assert PAYLOAD_TER_ESCAPE[0] in badan, nama
        assert 'Ani & "Budi"' not in badan and "Ani & " not in badan, nama
    assert "Bahas " + PAYLOAD_TER_ESCAPE[0] in halaman["periksa"]  # pembahasan contoh dan pola


@pytest.mark.parametrize("payload", ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>', "</textarea><b>x"])
def test_markup_di_isian_ditolak_validasi_dan_ter_escape_saat_dipantulkan(tertutup, admin, payload):
    kode, halaman, _t = kirim_buat(tertutup, admin, isi_sah(judul=payload, teks="{nama} {a} {b} " + payload))
    badan = halaman.rsplit("</style>", 1)[-1]
    assert kode == 400 and payload not in badan and not store._path_db(None).exists()
    assert "&lt;" in badan or "&quot;" in badan


def test_renderer_langsung_meng_escape_item_yang_berisi_markup():
    """Validasi menolak `<`/`>`, jadi item dirakit tangan: renderer harus tetap aman (lapis kedua)."""
    c = pola.Cetakan(
        3, 1, '<script>j()</script>', '"><img onerror=t()> {a}', (("a", 1, 9),), False,
        ('a < "<i>"',), 'a', '<svg onload=p()> {kunci}')
    item = store.ItemCetakan(1, 3, 1, "aktif", "ai", c, 1, "2026-11-20<b>", "2026-11-20<b>")
    soal = pola.SoalCetakan('<script>s()</script> "x"', "7", '<u onclick=p()>', {"a": 7}, "t")
    hasil = pola.HasilKelayakan(False, ("<alasan>",), 3, (soal,))
    riwayat = (store.RiwayatCetakan(1, "buat", "<waktu>", "<pelaku>", None, "<json>"),
               store.RiwayatCetakan(2, "setujui", "<waktu>", "<pelaku>", "<lama>", "<baru>"))
    _k, bab = hitung.cari_bab(3, 1)
    kumpulan = [
        ui.halaman_periksa(item, contoh=(soal,), kelayakan=hasil, riwayat=riwayat, tokens=None, galat="<galat>"),
        ui.halaman_daftar(3, bab, (item,)),
        ui.halaman_baru(3, bab, ("c<", "t<"), {n: "<x>\"'&" for n in ui.form.FIELD_ISI}, "<galat>"),
        buat_ui.halaman(3, bab, buat.HasilBuat((buat.ItemSoalCetakan(1, soal, "<script>j</script>"),), 5, (), True), 5, 1),
        ui.baris_soal(soal),
    ]
    for isi in kumpulan:
        for mentah in ("<script>", "<img", "<svg", "<u onclick", "<b>", "<i>", "<alasan>", "<waktu>", "<pelaku>",
                       "<galat>", "<lama>", "<baru>", "<x>", "<json>"):
            assert mentah not in isi, mentah
    assert "&lt;script&gt;" in kumpulan[0] and "&lt;galat&gt;" in kumpulan[0]


def test_tampil_angka_ribuan_hanya_untuk_angka():
    assert ui._tampil_angka("1234567") == "1.234.567" and ui._tampil_angka("42") == "42"
    assert ui._tampil_angka("<x>") == "<x>"  # bukan angka: apa adanya (di-escape oleh pemanggil)
