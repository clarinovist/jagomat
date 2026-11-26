"""Aturan catatan Guru lewat HTTP (D1-2): penolakan di form catatan, pemeriksaan ulang saat terbit, petunjuk di halaman.

Data sintetis; fixture dan pembantu sama dengan `test_peta_laporan_guru_http.py`. Menjadi sasaran mutation di
`test_peta_laporan_catatan_mutation.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import peta_laporan_guru_http as pgh  # noqa: E402
import peta_laporan_guru_pages as hal  # noqa: E402
from cek_http_kit import AKUN_A, minta_mentah  # noqa: E402
from pesanan_http_kit import bayar, jam, keluarga, ledger, server, tertutup  # noqa: E402,F401
from pesanan_transfer_http_kit import transfer  # noqa: E402,F401
from peta_otomatis_kit import tanpa_terbit_otomatis  # noqa: E402,F401  (autouse: jalur Guru butuh order lunas tanpa laporan)
from purna_http_kit import bayar_purna, lunas, potret_efek, transfer_purna  # noqa: E402,F401

CATATAN = "Anak sudah lebih teliti saat berhitung; di rumah cukup latihan sepuluh menit."
PESAN_TOLAK = ("Catatan tidak boleh memuat nomor telepon, tautan, alamat email, atau istilah internal seperti "
               "kode diagnosis atau kunci jawaban.")
PESAN_PETUNJUK = "Catatan ini dibaca orang tua dan anak. Jangan tulis nomor telepon, tautan, atau kunci jawaban."
PESAN_TERSIMPAN = ("Catatan yang tersimpan tidak memenuhi aturan (tanpa nomor telepon, tautan, alamat email, atau "
                   "istilah internal). Ubah dan simpan catatan dulu sebelum menerbitkan.")


def _url(server, aksi: str = "") -> str:
    return "/anak/%d/peta%s" % (server.anak_a, aksi)


def _post(server, aksi: str, data=None):
    return minta_mentah(server, _url(server, "/" + aksi), AKUN_A, {} if data is None else data)


def _efek(server) -> tuple:
    with server.buka() as kon:
        baris = [tuple(r) for r in kon.execute("SELECT * FROM peta_laporan ORDER BY id")]
    return baris, potret_efek()


def _draf(server, catatan: str = CATATAN) -> None:
    assert _post(server, "buat")[0] == 303
    if catatan:
        assert _post(server, "catatan", {"catatan": catatan})[0] == 303


def _tulis_catatan_lama(server, catatan: str) -> None:
    """Meniru draf yang dibuat sebelum aturan ada: catatan ditulis langsung ke DB, melewati store."""
    with server.buka() as kon:
        kon.execute("UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?", (catatan, server.anak_a))


@pytest.mark.parametrize("catatan", [
    "Hubungi saya di 0812 3456 7890 ya", "WA 0812-3456-7890", "chat lewat wa.me/62812", "lihat https://contoh.id/x",
    "email guru@contoh.id", "ada malrule di soal tiga", "minta Kunci Jawaban dulu", "kode diagnosis: B2",
    "kode_final K",
])
def test_catatan_berisi_kontak_atau_istilah_internal_ditolak_400_pesan_tepat_tanpa_efek_dan_teks_dipertahankan(
        lunas, catatan):
    server, _admin, _oid = lunas
    _draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": catatan})
    assert kode == 400 and PESAN_TOLAK in isi
    assert ">%s</textarea>" % catatan in isi
    assert _efek(server) == sebelum


def test_catatan_wajar_dengan_kata_awam_tetap_diterima(lunas):
    server, _admin, _oid = lunas
    _draf(server, catatan="")
    teks = "Kunci keberhasilannya latihan rutin. Pembahasan kita lakukan di kelas; diagnosis awal: perlu penguatan."
    assert _post(server, "catatan", {"catatan": teks})[0] == 303
    assert _efek(server)[0][0][3] == teks


def test_pesan_panjang_dan_kontrol_tetap_pesan_lama(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": "b" * 2001})
    assert kode == 400 and pgh.PESAN_CATATAN_PANJANG in isi and PESAN_TOLAK not in isi
    kode, isi, _t = _post(server, "catatan", {"catatan": "ada\x00nul"})
    assert kode == 400 and pgh.PESAN_CATATAN_ISI in isi and PESAN_TOLAK not in isi
    assert _efek(server) == sebelum


def test_pesan_tolak_tidak_menayangkan_ulang_bagian_yang_ditolak_di_pesan(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    isi = _post(server, "catatan", {"catatan": "tel:+628123456789"})[1]
    sebelum_form = isi.split("<textarea", 1)[0]
    assert "628123456789" not in sebelum_form


def test_terbit_memeriksa_ulang_catatan_tersimpan_lama_409_tanpa_efek_lalu_berhasil_setelah_diperbaiki(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    _tulis_catatan_lama(server, "Hubungi 081234567890 untuk kunci jawaban")
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "terbitkan", {"konfirmasi": "1"})
    assert kode == 409 and PESAN_TERSIMPAN in isi
    assert _efek(server) == sebelum and sebelum[0][0][6] is None
    assert _post(server, "catatan", {"catatan": CATATAN})[0] == 303
    assert _post(server, "terbitkan", {"konfirmasi": "1"})[0] == 303
    assert _efek(server)[0][0][6] is not None


def test_terbit_catatan_kosong_tetap_pesan_kosong_bukan_pesan_tersimpan(lunas):
    server, _admin, _oid = lunas
    _draf(server, catatan="")
    kode, isi, _t = _post(server, "terbitkan", {"konfirmasi": "1"})
    assert kode == 409 and pgh.PESAN_CATATAN_KOSONG in isi and PESAN_TERSIMPAN not in isi


def test_petunjuk_siapa_pembaca_catatan_tampil_di_bawah_kolom_catatan(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    isi = minta_mentah(server, _url(server), AKUN_A)[1]
    form = isi.split('name="catatan"', 1)[1].split("</form>", 1)[0]
    assert PESAN_PETUNJUK in form and "<script" not in form
    assert hal.PETUNJUK_CATATAN == PESAN_PETUNJUK


PESAN_SINGKAT = "Catatan terlalu singkat untuk diterbitkan"


@pytest.mark.parametrize("catatan", ["\u200b" * 20, "\u00a0".join("abcdefg"), "pendek", "abcdefghi", "a b c d e f g h i"])
def test_terbit_catatan_tak_terlihat_atau_terlalu_pendek_409_pesan_singkat_tanpa_efek(lunas, catatan):
    server, _admin, _oid = lunas
    _draf(server, catatan="")
    assert _post(server, "catatan", {"catatan": catatan})[0] == 303      # draf boleh menyimpan catatan pendek
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "terbitkan", {"konfirmasi": "1"})
    assert kode == 409 and PESAN_SINGKAT in isi and pgh.PESAN_CATATAN_KOSONG not in isi
    assert PESAN_SINGKAT == pgh.PESAN_CATATAN_SINGKAT
    assert _efek(server) == sebelum and sebelum[0][0][6] is None


def test_terbit_catatan_tepat_sepuluh_karakter_efektif_berhasil(lunas):
    server, _admin, _oid = lunas
    _draf(server, catatan="a b c d e\u200b f g h i j")
    assert _post(server, "terbitkan", {"konfirmasi": "1"})[0] == 303
    assert _efek(server)[0][0][6] is not None


@pytest.mark.parametrize("catatan", ["ada\u202eterbalik", "ada\u2066isolasi", "ada\u2069"])
def test_catatan_berisi_penanda_arah_teks_ditolak_400_pesan_karakter_tanpa_efek(lunas, catatan):
    server, _admin, _oid = lunas
    _draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": catatan})
    assert kode == 400 and pgh.PESAN_CATATAN_ISI in isi and PESAN_TOLAK not in isi
    assert _efek(server) == sebelum


@pytest.mark.parametrize("huruf", [chr(0x1F600), chr(0xE9), chr(0x4E2D)], ids=["emoji", "beraksen", "cjk"])
def test_catatan_2000_karakter_non_ascii_tidak_ditolak_batas_form(lunas, huruf):
    server, _admin, _oid = lunas
    _draf(server, catatan="")
    catatan = huruf * 2000
    assert _post(server, "catatan", {"catatan": catatan})[0] == 303
    assert _efek(server)[0][0][3] == catatan
    kode, isi, _t = _post(server, "catatan", {"catatan": huruf * 2001})
    assert kode == 400 and pgh.PESAN_CATATAN_PANJANG in isi


def test_tubuh_melebihi_batas_form_catatan_ditolak_pesan_form_tanpa_efek(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", {"catatan": "x" * 30000})
    assert kode == 400 and pgh.PESAN_FORM in isi and _efek(server) == sebelum
    assert pgh.BATAS_FORM_CATATAN >= 2000 * 12


def test_konfirmasi_hapus_draf_menyebut_data_per_materi_tidak_bisa_dibuat_ulang_setelah_30_hari(lunas):
    server, _admin, _oid = lunas
    _draf(server)
    isi = minta_mentah(server, _url(server), AKUN_A)[1]
    form = isi.split("/hapus", 1)[1].split("</form>", 1)[0]
    assert "tidak bisa dikembalikan" in form
    assert "data per materi tidak dapat dibuat ulang bila sudah lewat 30 hari sejak cek" in form
    assert hal.KONFIRMASI_HAPUS in form.replace("&#x27;", "'")


@pytest.mark.parametrize("data", [{"catatan": ["satu", "dua"]}, {"catatan": "a", **{"f%d" % i: "x" for i in range(16)}}],
                         ids=["kunci-ganda", "terlalu-banyak-field"])
def test_form_catatan_salah_bentuk_400_pesan_form_tanpa_efek(lunas, data):
    server, _admin, _oid = lunas
    _draf(server)
    sebelum = _efek(server)
    kode, isi, _t = _post(server, "catatan", data)
    assert kode == 400 and pgh.PESAN_FORM in isi and _efek(server) == sebelum
