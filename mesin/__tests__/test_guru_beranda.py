"""Beranda guru selaras mockup Ruang guru: chip berhitungan, tombol aksi, ringkasan."""
import re
import pytest

import database
import guru_beranda_pages as G
import teacher_home_priority as P
from http_test_kit import ServerUji, SANDI_GURU
from test_teacher_home_priority import _sesi_terpandu, _kirim


@pytest.fixture
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            menunggu = database.tambah_siswa(kon, "Aaa Menunggu", "P3", pemilik="guru")
            database.tambah_siswa(kon, "Bbb Baru", "P3", pemilik="guru")
            tindakan = database.tambah_siswa(kon, "Ccc Terkirim", "P3", pemilik="guru")
            _sesi_terpandu(kon, menunggu, 901)
            _kirim(kon, _sesi_terpandu(kon, tindakan, 902))
        yield uji
    finally:
        uji.berhenti()


def _beranda(uji, jalur="/guru"):
    kode, isi, _ = uji.minta(jalur, auth=("guru", SANDI_GURU))
    assert kode == 200
    return isi


def _chip(isi):
    """{label: (jumlah, href, aktif)} dari baris chip langkah."""
    nav = re.search(r'<nav class="guru-chip-baris-st"[^>]*>(.*?)</nav>', isi, re.S).group(1)
    return {
        label: (int(jumlah), href.replace("&amp;", "&"), bool(aktif))
        for href, aktif, label, jumlah in re.findall(
            r'<a class="guru-chip-st" href="([^"]+)"( aria-current="true")?>([^<]+?) <strong>(\d+)</strong></a>',
            nav)
    }


def test_chip_menghitung_kelompok_dan_menandai_yang_aktif(server):
    chip = _chip(_beranda(server))
    assert chip == {
        "Semua": (3, "/guru", True),
        "Perlu tindakan Anda": (1, "/guru?kelompok=perlu-tindakan", False),
        "Siap dilanjutkan": (1, "/guru?kelompok=siap", False),
        "Menunggu": (1, "/guru?kelompok=menunggu", False),
    }


def test_hitungan_chip_tidak_berubah_oleh_filter_atau_pencarian(server):
    semua = {k: v[0] for k, v in _chip(_beranda(server)).items()}
    disaring = _beranda(server, "/guru?kelompok=siap&cari=Bbb")
    assert {k: v[0] for k, v in _chip(disaring).items()} == semua
    assert "1 dari 3 siswa ditampilkan." in disaring


def test_hitungan_chip_hanya_anak_milik_guru_ini(server):
    sebelum = {k: v[0] for k, v in _chip(_beranda(server)).items()}
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, "Rahasia Asing", "P3", pemilik="guru-lain")
        _kirim(kon, _sesi_terpandu(kon, asing, 903))
    isi = _beranda(server)
    assert {k: v[0] for k, v in _chip(isi).items()} == sebelum
    assert "Rahasia Asing" not in isi and "dari 3 siswa" in isi


def test_chip_mempertahankan_pencarian_dan_menandai_pilihan(server):
    isi = _beranda(server, "/guru?kelompok=siap&cari=Bbb")
    chip = _chip(isi)
    assert chip["Siap dilanjutkan"] == (1, "/guru?kelompok=siap&cari=Bbb", True)
    assert chip["Semua"][1] == "/guru?cari=Bbb"
    assert [v[2] for v in chip.values()].count(True) == 1


def test_pencarian_hanya_untuk_daftar_panjang_atau_saat_aktif(server):
    assert 'id="guru-filter"' not in _beranda(server)
    assert 'id="guru-filter"' in _beranda(server, "/guru?cari=Bbb")
    with server.buka() as kon:
        for i in range(G.AMBANG_PENCARIAN - 2):
            database.tambah_siswa(kon, f"Tambahan {i}", "P3", pemilik="guru")
    assert 'id="guru-filter"' in _beranda(server)


def test_form_pencarian_membawa_kelompok_aktif(server):
    isi = _beranda(server, "/guru?kelompok=siap&cari=Bbb")
    assert '<input type="hidden" name="kelompok" value="siap">' in isi


def test_satu_tautan_per_kartu_dengan_nama_yang_menyebut_anak(server):
    isi = _beranda(server)
    kartu = re.findall(r'<article class="guru-kartu-st[^"]*">(.*?)</article>', isi, re.S)
    assert len(kartu) == 3
    for k in kartu:
        assert k.count("<a ") == 1
        nama = re.search(r'class="guru-nama-st">([^<]+)<', k).group(1)
        assert re.search(r'aria-label="[^"]+: ' + re.escape(nama) + '"', k)
    assert "Buka profil" not in isi


def test_label_tombol_mengikuti_langkah_dan_hanya_perlu_tindakan_yang_utama(server):
    isi = _beranda(server)
    kartu = {
        re.search(r'class="guru-nama-st">([^<]+)<', k).group(1): k
        for k in re.findall(r'<article class="guru-kartu-st[^"]*">(.*?)</article>', isi, re.S)
    }
    assert "Tinjau hasil" in kartu["Ccc Terkirim"]
    assert "guru-cta-utama-st" in kartu["Ccc Terkirim"]
    assert "Siapkan latihan" in kartu["Bbb Baru"]
    assert "guru-cta-utama-st" not in kartu["Bbb Baru"]
    assert "guru-cta-utama-st" not in kartu["Aaa Menunggu"]


@pytest.mark.parametrize("tindakan,label,harapan", [
    ("konfirmasi_hasil", "Periksa dan konfirmasi hasil", G._CTA["konfirmasi_hasil"]),
    ("lanjutkan_sesi", "Lanjutkan latihan", G._CTA["lanjutkan_sesi"]),
    ("pemetaan", "Lanjutkan latihan awal", G._CTA["pemetaan"]),
    ("pemetaan", "Siapkan latihan awal", G._CTA["pilih_variasi"]),
    ("eskalasi", "Perlu tinjauan lanjutan", G.CTA_BAWAAN),
    ("tunggu_evaluasi", "Tunggu cek beberapa hari lagi", G.CTA_BAWAAN),
    (None, G.prioritas.LABEL_TIDAK_TERBACA, G.CTA_TIDAK_TERBACA),
])
def test_label_tombol_untuk_setiap_jenis_langkah(tindakan, label, harapan):
    langkah = P.LangkahAnak(1, "A", tindakan, P.kelompok_untuk(tindakan), label)
    assert G._cta(langkah) == harapan


def test_ringkasan_satu_kalimat_dari_hitungan_kelompok(server):
    assert "1 anak perlu tindakan Anda. 1 anak siap dilanjutkan." in _beranda(server)


@pytest.mark.parametrize("jumlah,total,kalimat", [
    ({P.PERLU_TINDAKAN: 2, P.SIAP: 0, P.MENUNGGU: 1}, 3, "2 anak perlu tindakan Anda."),
    ({P.PERLU_TINDAKAN: 0, P.SIAP: 1, P.MENUNGGU: 0}, 1, "1 anak siap dilanjutkan."),
    ({P.PERLU_TINDAKAN: 0, P.SIAP: 0, P.MENUNGGU: 2}, 2,
     "Semua anak sedang menunggu langkah berikutnya."),
    ({P.PERLU_TINDAKAN: 0, P.SIAP: 0, P.MENUNGGU: 0}, 0, "Temani prosesnya, bukan hanya hasilnya."),
])
def test_ringkasan_tidak_mengklaim_lebih_dari_hitungan(jumlah, total, kalimat):
    assert G._ringkasan(jumlah, total) == kalimat


def test_kartu_tidak_dikelompokkan_dengan_judul_tetapi_tetap_berurutan(server):
    isi = _beranda(server)
    assert "guru-kelompok-st" not in isi
    assert re.findall(r'class="guru-nama-st">([^<]+)<', isi) == [
        "Ccc Terkirim", "Bbb Baru", "Aaa Menunggu"]
    assert re.findall(r'<span class="guru-pil-st[^"]*">([^<]+)</span>', isi) == [
        "Perlu tindakan Anda", "Siap dilanjutkan", "Menunggu"]
    # Nama anak h3 langsung di bawah h2 daftar (tanpa h3 judul grup).
    assert isi.count("<h3") == 3 and isi.count("<h2") == 1


def test_warna_avatar_deterministik_per_id_anak(server):
    with server.buka() as kon:
        ids = [r[0] for r in kon.execute("SELECT id FROM siswa WHERE pemilik='guru'")]
    isi = _beranda(server)
    for i in ids:
        assert f'guru-avatar-{i % G.JUMLAH_WARNA_AVATAR}" aria-hidden="true">' in isi
    assert _beranda(server) == isi
