"""Cek kemampuan di sesi anak (F2b) lewat HTTP nyata: gerbang, persetujuan, isolasi anak, idempoten, hasil.

Anak dibuat lewat /daftar mode anak (F2a). Data sintetis di tmp_path; sakelar lewat env (fallback).
"""
import re

import pytest

import cek_gratis
import cek_gratis_kit as kit_cek
import cek_gratis_skor
import database
from cek_murid_kit import (  # noqa: F401  (server/gerbang_hidup adalah fixture)
    JUMLAH_SOAL, KATA_TERLARANG_KARTU, POLA_REVISI, TABEL_CEK, Anak, gerbang_hidup, jumlah_baris, kirim, murid_guru,
    server,
)

ACTION_KARTU = 'action="/murid/cek/mulai"'
KATA_HORE_TERLARANG = (
    "kunci", "malrule", "diagnos", "skor", "kategori", "benar", "salah", "kelemahan",
    "gurumu akan memeriksa", "kode_final", "persentil", "peringkat",
)


def _jalur_asing_identik(server, cookie, jalur):
    """POST ke jalur murid tak dikenal sebagai pembanding byte-identik (bukan 404 literal: lewat palang guru)."""
    return kirim(server, jalur, {}, cookie=cookie)


# --- gerbang -----------------------------------------------------------------

def test_sakelar_anak_mati_kartu_tidak_tampil_dan_post_identik_dengan_jalur_asing(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", str(server.lembaga_id))
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    anak = Anak(server, "raka-gerbang")
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "0")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, isi, _ = anak.get("/murid")
    assert kode == 200 and ACTION_KARTU not in isi and "Cek kemampuan" not in isi
    kode, isi, _ = anak.post()
    pembanding = _jalur_asing_identik(server, anak.cookie, "/murid/cek/tidak-ada")
    assert (kode, isi) == pembanding[:2]
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


def test_funnel_mati_kartu_tidak_tampil_dan_post_identik_dengan_jalur_asing(server, gerbang_hidup, monkeypatch):
    anak = Anak(server, "raka-funnel")
    monkeypatch.delenv("FUNNEL_AKTIF")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, isi, _ = anak.get("/murid")
    assert kode == 200 and ACTION_KARTU not in isi
    kode, isi, _ = anak.post()
    assert (kode, isi) == _jalur_asing_identik(server, anak.cookie, "/murid/cek/tidak-ada")[:2]
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


def test_anonim_dan_bukan_murid_ditolak_tanpa_menulis(server, gerbang_hidup):
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, isi, _ = kirim(server, "/murid/cek/mulai", {})
    assert kode == 401 and "Perlu masuk" in isi
    guru = ("guru", "sandi-guru-panjang-123")
    kode, isi, _ = server.minta("/murid/cek/mulai", auth=guru, data={})
    asing = server.minta("/murid/cek/tidak-ada", auth=guru, data={})
    assert (kode, isi) == asing[:2]  # guru: jatuh ke rantai lama, identik jalur asing
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


# --- kartu di beranda ----------------------------------------------------------

def test_kartu_tampil_untuk_anak_hasil_daftar_belum_mulai(server, gerbang_hidup):
    anak = Anak(server, "raka-kartu")
    kode, isi, _ = anak.get("/murid")
    assert kode == 200 and ACTION_KARTU in isi and "Mulai cek kemampuan" in isi
    kartu = isi[isi.index("<!--cek-murid-->"):isi.index("<!--/cek-murid-->")].lower()
    for kata in KATA_TERLARANG_KARTU:
        assert kata not in kartu, kata
    assert "<script" not in kartu and "href=" not in kartu


def test_kartu_tidak_tampil_untuk_murid_buatan_guru_tanpa_persetujuan(server, gerbang_hidup):
    cookie, _, _ = murid_guru(server, "murid-guru-1")
    kode, isi, _ = kirim(server, "/murid", cookie=cookie)
    assert kode == 200 and ACTION_KARTU not in isi and "Cek kemampuan" not in isi


# --- mulai -------------------------------------------------------------------------

def test_mulai_membuat_cek_untuk_akun_murid_dan_mengalihkan_ke_tautan_anak(server, gerbang_hidup):
    anak = Anak(server, "raka-mulai")
    kode, isi, header = anak.post()
    assert kode == 303 and isi == ""
    lokasi = header["Location"]
    assert re.fullmatch(r"/mulai/[A-Za-z0-9_-]{43}", lokasi)
    assert header["Cache-Control"] == "no-store" and header["Referrer-Policy"] == "no-referrer"
    assert "Set-Cookie" not in header
    baris = anak.baris_cek()
    assert baris["id_akun"] == anak.id_akun and baris["siswa_id"] == anak.siswa_id
    assert baris["versi_notice"] == cek_gratis_skor.VERSI_NOTICE and baris["skor"] is None
    with server.buka() as kon:
        sesi = kon.execute("SELECT siswa_id, tujuan, format_jawaban FROM sesi WHERE id = ?", (baris["sesi_id"],)).fetchone()
        assert tuple(sesi) == (anak.siswa_id, "bebas", "pilihan_ganda")
        assert kon.execute("SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (baris["sesi_id"],)).fetchone()[0] == JUMLAH_SOAL
    assert anak.get("/murid")[0] == 200  # sesi login anak tidak dihapus
    kode, halaman, _ = kirim(server, lokasi)
    assert kode == 200 and "Hore, " not in halaman and "soal" in halaman.lower()


def test_mulai_idempoten_satu_cek_satu_sesi_dan_kartu_menjadi_lanjutkan(server, gerbang_hidup):
    anak = Anak(server, "raka-idem")
    assert anak.post()[0] == 303
    awal = jumlah_baris(server, "cek_gratis", "sesi", "sesi_soal")
    kode, _, header = anak.post()
    assert kode == 303 and header["Location"].startswith("/mulai/")
    assert jumlah_baris(server, "cek_gratis", "sesi", "sesi_soal") == awal
    _, isi, _ = anak.get("/murid")
    assert "Lanjutkan cek kemampuan" in isi and "Mulai cek kemampuan" not in isi


def test_cek_anak_tidak_muncul_sebagai_latihan_biasa_di_beranda(server, gerbang_hidup):
    anak = Anak(server, "raka-daftar")
    anak.post()
    sesi_id = anak.baris_cek()["sesi_id"]
    _, isi, _ = anak.get("/murid")
    assert "/murid/kerjakan/%d" % sesi_id not in isi
    assert "Menunggu diperiksa" not in isi and "Latihan untukmu" not in isi


def test_tanpa_persetujuan_ditolak_404_tanpa_menulis(server, gerbang_hidup):
    cookie, siswa_id, _ = murid_guru(server, "murid-guru-2")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, isi, _ = kirim(server, "/murid/cek/mulai", {}, cookie=cookie)
    assert kode == 404 and "Halaman tidak ada" in isi
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


def test_versi_notice_persetujuan_beda_ditolak_tanpa_menulis(server, gerbang_hidup):
    anak = Anak(server, "raka-versi")
    with server.buka() as kon:
        kon.execute("UPDATE persetujuan_daftar_anak SET versi_notice = 'v-lain' WHERE siswa_id = ?", (anak.siswa_id,))
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, _, _ = anak.post()
    assert kode == 404 and jumlah_baris(server, *TABEL_CEK) == sebelum
    assert ACTION_KARTU not in anak.get("/murid")[1]


def test_kelas_belum_tersedia_pesan_tetap_tanpa_menulis(server, gerbang_hidup):
    anak = Anak(server, "raka-kelas1", kelas="1")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, isi, _ = anak.post()
    assert kode == 409 and "belum bisa dimulai" in isi.lower() and "Cek belum tersedia" not in isi
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


# --- isolasi antar anak ---------------------------------------------------------------

def test_id_dari_query_atau_form_diabaikan_atau_ditolak_anak_lain_tidak_tersentuh(server, gerbang_hidup):
    a, b = Anak(server, "anak-a"), Anak(server, "anak-b")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    for data in ({"siswa": str(b.siswa_id)}, {"siswa_id": str(b.siswa_id), "id_akun": b.id_akun}):
        kode, _, _ = a.post(data=data)
        assert kode == 400
    assert jumlah_baris(server, *TABEL_CEK) == sebelum
    kode, _, header = a.post("/murid/cek/mulai?siswa=%d&siswa_id=%d&id_akun=%s" % (b.siswa_id, b.siswa_id, b.id_akun))
    assert kode == 303
    assert a.baris_cek()["id_akun"] == a.id_akun
    assert b.baris_cek() is None
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (b.siswa_id,)).fetchone()[0] == 0
        assert kon.execute("""SELECT COUNT(*) FROM tautan_sesi t JOIN sesi s ON s.id = t.sesi_id
                              WHERE s.siswa_id = ?""", (b.siswa_id,)).fetchone()[0] == 0


def test_cek_anak_lain_tidak_terbaca_dan_tidak_muncul_di_beranda(server, gerbang_hidup):
    a, b = Anak(server, "anak-c"), Anak(server, "anak-d")
    b.post()
    sesi_b = b.baris_cek()["sesi_id"]
    with server.buka() as kon:
        assert cek_gratis.hasil_siswa(kon, a.id_akun, b.siswa_id)["status"] == "belum_mulai"
        assert cek_gratis.hasil_siswa(kon, b.id_akun, a.siswa_id)["status"] == "belum_mulai"
    _, isi, _ = a.get("/murid")
    assert str(sesi_b) not in re.sub(r"\d{6,}", "", isi) or "/murid/kerjakan/%d" % sesi_b not in isi
    assert "Mulai cek kemampuan" in isi and "Lanjutkan cek kemampuan" not in isi


def test_cek_milik_akun_lain_untuk_anak_sama_tidak_diambil_alih(server, gerbang_hidup):
    """Anak yang cek-nya sudah dibuat id_akun lain (alur guru lama): jalur murid 404, tidak menulis, kartu hilang."""
    anak = Anak(server, "raka-warisan")
    with server.buka() as kon:
        kit_cek.mulai_cek(kon, kit_cek.ID_B, anak.siswa_id, "koordinator-jagomat")
    sebelum = jumlah_baris(server, *TABEL_CEK)
    assert anak.post()[0] == 404
    assert jumlah_baris(server, *TABEL_CEK) == sebelum
    assert ACTION_KARTU not in anak.get("/murid")[1]


# --- selesai ----------------------------------------------------------------------------

def _kumpulkan_lewat_tautan(server, anak, lokasi, benar=7):
    baris = anak.baris_cek()
    with server.buka() as kon:
        kit_cek.jawab(kon, baris["sesi_id"], semua_benar=benar)
    _, peta, _ = kirim(server, lokasi + "?peta=1")
    revisi = POLA_REVISI.search(peta).group(1)
    return kirim(server, lokasi, {"aksi": "kumpul", "revisi_pekerjaan": revisi})


def test_selesai_hore_tanpa_skor_hasil_siswa_berisi_skor_dan_kartu_hilang(server, gerbang_hidup):
    anak = Anak(server, "raka-selesai")
    _, _, header = anak.post()
    kode, hore, _ = _kumpulkan_lewat_tautan(server, anak, header["Location"])
    assert kode == 200 and "Hore" in hore
    from cek_anak_kit import buang_soal_dan_gaya
    polos = buang_soal_dan_gaya(hore).lower()
    for kata in KATA_HORE_TERLARANG:
        assert kata not in polos, kata
    with server.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        assert cek_gratis.selesaikan_jika_siap(kon, anak.id_akun, kit_cek.SEKARANG) is True
        hasil = cek_gratis.hasil_siswa(kon, anak.id_akun, anak.siswa_id)
    assert hasil["status"] == "selesai" and hasil["skor"] == cek_gratis_skor.hitung_skor(7, JUMLAH_SOAL)
    _, isi, _ = anak.get("/murid")
    assert ACTION_KARTU not in isi and "Cek kemampuan" not in isi
    assert "Menunggu diperiksa" not in isi


def test_mulai_setelah_selesai_kembali_ke_beranda_tanpa_cek_kedua(server, gerbang_hidup):
    anak = Anak(server, "raka-ulang")
    _, _, header = anak.post()
    _kumpulkan_lewat_tautan(server, anak, header["Location"])
    assert ACTION_KARTU not in anak.get("/murid")[1]  # kartu hilang begitu sesi dikumpulkan, sebelum dinilai
    sebelum = jumlah_baris(server, *TABEL_CEK)
    kode, _, tajuk = anak.post()
    assert kode == 303 and tajuk["Location"] == "/murid"
    assert jumlah_baris(server, *TABEL_CEK) == sebelum


def test_alur_guru_lama_tidak_berubah_saat_sakelar_anak_hidup(server, gerbang_hidup):
    """Anak milik guru dengan cek buatan id_akun guru: token lama tetap membuka layar cek anak."""
    import share_links
    with server.buka() as kon:
        siswa_id = kit_cek.tambah_anak(kon, "Anak Guru Lama", "guru", 4)
        sesi_id = kit_cek.mulai_cek(kon, kit_cek.ID_A, siswa_id, "guru", seed=3)
        token = share_links.buat(kon, sesi_id)
    kode, isi, _ = kirim(server, "/mulai/" + token)
    assert kode == 200 and "Anak Guru Lama" in isi
