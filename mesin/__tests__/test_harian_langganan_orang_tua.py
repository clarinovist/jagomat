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
    assert html.count('href="/murid/langganan"') == 1 and ">Lihat paket<" in html
    assert 'id="ortu-langganan-banner"' not in html


def test_aktif_lebih_dari_tiga_hari_kartu_tanpa_banner(kon):
    s = anak(kon)
    langganan(kon, s)
    html = isi(kon, s, "2026-12-20T02:59:59")
    assert "Tanpa batas sampai 23 Des 2026" in html and ">Perpanjang<" in html
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
    assert 'id="ortu-langganan-banner"' not in html and "Tanpa batas sampai 23 Jan 2027" in html


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


# --- F3: kartu enam keadaan (murni render, tanpa DB) ----------------------------------------------

import re
from types import MappingProxyType

import harian_langganan_dasar as dasar
import harian_langganan_ringkas as ringkas

BERAKHIR = "2026-12-23T03:00:00"


def _r(sumber="gratis", berakhir=None, sisa=0, tagihan=None, alasan=None):
    return ringkas.Ringkasan(sumber, berakhir, sisa, tagihan, alasan)


def _kartu(r):
    html = halaman.kartu_orang_tua(r)
    assert html.count('id="ortu-langganan"') == 1 and html.startswith("<section")
    return html


KEADAAN = {
    "belum": (_r(), "Belum berlangganan", "Lihat paket"),
    "menunggu": (_r(tagihan=dasar.STATUS_MENUNGGU), "Menunggu pemeriksaan", "Lihat status"),
    "aktif": (_r("langganan", BERAKHIR, 20), "Aktif", "Perpanjang"),
    "segera": (_r("langganan", BERAKHIR, 2), "Berakhir 2 hari lagi", "Perpanjang"),
    "ditolak": (_r(tagihan=dasar.STATUS_DITOLAK, alasan="Nominal kurang"), "Bukti perlu diperbaiki", "Unggah ulang bukti"),
    "les": (_r("les"), "Dari les", None),
    "belum_bayar": (_r(tagihan=dasar.STATUS_BELUM_BAYAR), "Menunggu pembayaran", "Lanjutkan pembayaran"),
}


@pytest.mark.parametrize("nama", sorted(KEADAAN))
def test_setiap_keadaan_berpenanda_teks_dan_paling_banyak_satu_tautan_langganan(nama):
    r, penanda, tombol = KEADAAN[nama]
    html = _kartu(r)
    teks = re.sub(r"<[^>]+>", " ", html)
    # status bukan hanya warna: penanda teks (lencana atau label kartu navy) selalu ada
    assert penanda in teks, nama
    assert html.count('href="/murid/langganan"') == (0 if tombol is None else 1)
    assert html.count("<a ") == (0 if tombol is None else 1)
    if tombol:
        assert ">%s<" % tombol in html
    assert "<script" not in html and html.count("<img") == 0


def test_nada_kartu_per_keadaan_tidak_tercampur():
    nada = {n: re.search(r'class="(ceria-(?:status ceria-status-\w+|ortu))"', _kartu(KEADAAN[n][0])).group(1) for n in KEADAAN}
    assert nada["belum"] == "ceria-ortu"
    assert nada["menunggu"] == nada["belum_bayar"] == "ceria-status ceria-status-kuning"
    assert nada["aktif"] == nada["les"] == "ceria-status ceria-status-hijau"
    assert nada["segera"] == nada["ditolak"] == "ceria-status ceria-status-koral"


def test_kartu_belum_berlangganan_harga_dari_paket(monkeypatch):
    assert "mulai Rp39.000/bulan" in re.sub(r"<[^>]+>", "", _kartu(_r()))
    baru = dasar.Paket("bulanan", "Bulanan", 45000, 1)
    monkeypatch.setattr(dasar, "PAKET", MappingProxyType({"bulanan": baru, "tahunan": dasar.Paket("tahunan", "Tahunan", 400000, 12)}))
    assert "mulai Rp45.000/bulan" in re.sub(r"<[^>]+>", "", _kartu(_r()))


def test_alasan_penolakan_di_kartu_di_escape():
    html = _kartu(_r(tagihan=dasar.STATUS_DITOLAK, alasan="<b>X</b> & Y"))
    assert "&lt;b&gt;X&lt;/b&gt; &amp; Y" in html and "<b>X</b>" not in html


def test_tagihan_ditolak_tanpa_alasan_tidak_mengarang_alasan():
    html = _kartu(_r(tagihan=dasar.STATUS_DITOLAK))
    assert "Alasan dari tim" not in html and "Bukti terakhir belum sesuai" in html


def test_menunggu_dan_aktif_masih_menyebut_tanggal_berakhir():
    html = _kartu(_r("langganan", BERAKHIR, 20, dasar.STATUS_MENUNGGU))
    assert "Latihan Harian tanpa batas aktif sampai 23 Des 2026." in html


def test_ringkasan_membawa_alasan_tolak_hanya_saat_ditolak(kon):
    s = anak(kon)
    t = store.buat_tagihan(kon, s, "bulanan", T0)
    b = store.catat_bukti(kon, s, "image/png", 10, "%064x" % 1, "%032x" % 1, T0)
    assert ringkas.ringkasan(kon, s, T0).alasan_tolak is None
    putusan.tolak(kon, t["order_id"], "admin_sintetis", "Nominal kurang tiga digit", T0, bukti_dilihat=b["bukti_id"])
    r = ringkas.ringkasan(kon, s, T0)
    assert (r.status_tagihan, r.alasan_tolak) == (dasar.STATUS_DITOLAK, "Nominal kurang tiga digit")
    assert "Nominal kurang tiga digit" in halaman.kartu_orang_tua(r)
