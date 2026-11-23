"""Halaman orang tua (F5): kartu status langganan dan banner 'berakhir N hari lagi' (sakelar LATIHAN_HARIAN, data sintetis)."""
import pytest

import database
import harian_langganan_pages as halaman
import harian_langganan_putusan as putusan
import harian_langganan_store as store
import lembaga_store
import orang_tua_data
import orang_tua_pages
from harian_kit import M, buat, buat_murid, halaman as ambil_halaman, hidup, jam, mati, minta_mentah, server, unggah  # noqa: F401

T0 = "2026-11-23T03:00:00"          # disetujui; berakhir 2026-12-23T03:00:00
AKUN = "akun_" + "a" * 32


@pytest.fixture
def kon(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    with database.buka(jalur) as k:
        yield k


def anak(kon, nama="Anak Sintetis", pemilik="guru"):
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', ?)", (nama, pemilik)).lastrowid
    kon.commit()
    return siswa


def langganan(kon, siswa, waktu=T0):
    n = kon.execute("SELECT COUNT(*) FROM harian_bukti").fetchone()[0] + 1
    t = store.buat_tagihan(kon, siswa, "bulanan", waktu)
    b = store.catat_bukti(kon, siswa, "image/png", 10, "%064x" % n, "%032x" % n, waktu)
    putusan.setujui(kon, t["order_id"], "admin_sintetis", waktu, bukti_dilihat=b["bukti_id"])


def isi(kon, siswa, kini):
    data = orang_tua_data.kumpulkan(kon, AKUN, siswa, kini)
    return orang_tua_pages.halaman_isi(data, False).decode()


def test_tanpa_langganan_kartu_belum_berlangganan_dengan_satu_tombol(kon):
    html = isi(kon, anak(kon), T0)
    assert 'id="ortu-langganan"' in html and "Belum berlangganan" in html
    assert html.count('href="/murid/langganan"') == 1 and ">Berlangganan<" in html
    assert 'id="ortu-langganan-banner"' not in html


def test_aktif_lebih_dari_tiga_hari_kartu_tanpa_banner(kon):
    s = anak(kon)
    langganan(kon, s)
    html = isi(kon, s, "2026-12-20T02:59:59")
    assert "aktif sampai 23 Des 2026" in html and ">Perpanjang<" in html
    assert 'id="ortu-langganan-banner"' not in html


@pytest.mark.parametrize("kini,sisa", [("2026-12-20T03:00:00", 3), ("2026-12-22T03:00:00", 1),
                                       ("2026-12-23T02:00:00", 1)])
def test_banner_saat_sisa_tiga_hari_atau_kurang(kon, kini, sisa):
    s = anak(kon, "Budi")
    langganan(kon, s)
    html = isi(kon, s, kini)
    assert 'id="ortu-langganan-banner"' in html
    assert "Latihan Harian Budi berakhir %d hari lagi." % sisa in html
    assert '<a href="/murid/langganan">Perpanjang</a>' in html


def test_setelah_berakhir_tanpa_banner_dan_kembali_belum_berlangganan(kon):
    s = anak(kon)
    langganan(kon, s)
    html = isi(kon, s, "2026-12-23T03:00:00")
    assert 'id="ortu-langganan-banner"' not in html and "Belum berlangganan" in html


def test_perpanjangan_tersetujui_menghilangkan_banner(kon):
    s = anak(kon)
    langganan(kon, s)
    langganan(kon, s, "2026-12-21T03:00:00")
    html = isi(kon, s, "2026-12-21T04:00:00")
    assert 'id="ortu-langganan-banner"' not in html and "aktif sampai 23 Jan 2027" in html


def test_nama_anak_di_banner_di_escape(kon):
    s = anak(kon, "<b>X</b>")
    langganan(kon, s)
    html = isi(kon, s, "2026-12-21T03:00:00")
    assert "<b>X</b> berakhir" not in html and "&lt;b&gt;X&lt;/b&gt; berakhir" in html


def test_murid_les_tanpa_tombol_dan_tanpa_banner(kon, monkeypatch):
    lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="koordinator-uji")
    kon.execute("INSERT INTO anggota_lembaga (lembaga_id, guru) VALUES (1, 'guru-anggota')")
    kon.commit()
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    s = anak(kon, pemilik="guru-anggota")
    html = isi(kon, s, T0)
    assert "murid les" in html and 'href="/murid/langganan"' not in html


def test_sakelar_mati_tanpa_kartu_dan_banner(kon, monkeypatch):
    s = anak(kon)
    langganan(kon, s)
    monkeypatch.delenv("LATIHAN_HARIAN")
    html = isi(kon, s, "2026-12-21T03:00:00")
    assert "ortu-langganan" not in html
    assert orang_tua_data.kumpulkan(kon, AKUN, s, T0).langganan is None


def test_data_tanpa_langganan_bawaan_none_untuk_pembuat_lama():
    data = orang_tua_data.DataOrangTua("A", {"status": "belum_mulai"}, None, None)
    assert data.langganan is None
    assert halaman.kartu_orang_tua(None) == "" and halaman.banner_orang_tua(None, "A") == ""


def test_halaman_orang_tua_http_memuat_kartu_hanya_saat_sakelar_hidup(hidup, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    murid = buat_murid(hidup, "murid-a", "Anak Alfa")
    kode, html, _ = minta_mentah(hidup, "/murid/orang-tua", murid.akun)
    assert kode == 200 and 'id="ortu-langganan"' in html and "Belum berlangganan" in html
    assert "6281234567890" not in html
    monkeypatch.delenv("LATIHAN_HARIAN")
    assert 'id="ortu-langganan"' not in minta_mentah(hidup, "/murid/orang-tua", murid.akun)[1]
