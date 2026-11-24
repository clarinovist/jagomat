"""Aturan catatan Guru laporan Peta (D1): `periksa_catatan` murni + penegakan di `simpan_catatan` dan `terbitkan`.

Catatan dibaca orang tua DAN anak, jadi tidak boleh jadi jalur kebocoran kontak, tautan, atau istilah internal.
Data sintetis. Menjadi sasaran mutation di `test_peta_laporan_catatan_mutation.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import peta_laporan_store as store  # noqa: E402
from test_peta_laporan_store import CATATAN, GURU, LEBIH_LAMBAT, SEKARANG, _isi  # noqa: E402

ZW = "\N{ZERO WIDTH SPACE}"


def _lebar(teks: str) -> str:
    """Versi fullwidth (NFKC melipatnya kembali ke ASCII)."""
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in teks)


PARAGRAF = ("Ananda sudah lebih teliti saat berhitung dan mulai berani menjelaskan langkahnya sendiri. "
            "Di rumah cukup latihan sepuluh menit setiap hari, fokus pada pengukuran panjang dan berat. ")
LOLOS = (
    "",
    CATATAN,
    "Kunci keberhasilannya latihan rutin; diagnosis awal: perlu penguatan pecahan.",
    "Pembahasan soal kita lakukan di kelas, bukan di rumah.",
    "Nilai 7 dari 10 soal, naik 2 poin; kelas 4, durasi 15 menit.",
    "Biaya Rp 49.000 sudah termasuk; sisa 1234567 tidak dianggap nomor.",
    "1234 567 dan 12 34 56 7 masih 7 digit.",
    "Dicek pada 24-11-2026 dan diulang 08-12-2026.",
    "Nilai 12345678 bukan nomor; sudah memberi jawaban benar pada nomor 3.",
    "1234 5678",
    "Hotel: tempat latihan lomba (bukan tautan).",
    "a\nb\tc\r\nd",
    PARAGRAF * 5,
)
KONTAK = (
    "123456789",
    "1234 56789",
    "Hubungi 0812 3456 7890 ya",
    "0812.3456.7890",
    "0812-3456-7890",
    "+62 812-3456-7890",
    "(0812) 3456 7890",
    "0 8 1 2 3 4 5 6 7",
    "08\n12\n34\n56\n7",
    _lebar("0812345678"),
    "08" + ZW + "12 3456 789",
    "chat wa.me/628123",
    "WA.ME/x",
    "tel:+62812",
    "TEL:021",
    "kontak saya WhatsApp",
    "WHATSAPP",
    "guru@contoh.id",
    "@guru",
    "lihat http://contoh.id",
    "HTTPS://contoh.id",
    "lihat www.contoh.id",
    _lebar("www") + ".contoh.id",
)
ISTILAH = (
    "ada malrule di soal itu",
    "MALRULE",
    "kode_final B",
    "KODE_FINAL",
    "kode_usulan K",
    "kode diagnosis anak",
    "Kode   Diagnosis",
    "minta kunci jawaban",
    "Kunci\nJawaban",
    "m" + ZW + "alrule",
    "kunci" + ZW + " jawaban",
    _lebar("malrule"),
)
KONTROL = ("a\x00b", "a\x01b", "a\x1bb", "a\x7fb", "a\x85b",
           "a\u202ab", "a\u202bb", "a\u202cb", "a\u202db", "a\u202eb", "a\u2066b", "a\u2067b", "a\u2068b", "a\u2069b")
# L1: pemisah digit tambahan, homoglyph Sirilik/Yunani, penanda tambahan, istilah internal dengan pemisah.
KONTAK_L1 = (
    "0812/3456/7890", "0812,3456,7890", "0812_3456_7890", "0812:3456:7890", "0 8 1 2 / 3 4 5 , 6 7",
    "w\u0430.me/628123", "w\u04bbatsapp", "wh\u0430tsapp", "wh\u03b1tsapp", "WA.M\u0415", "buka contoh.c\u043em",
    "t.me/guru", "bit.ly/abc", "Instagram saya", "INSTAGRAM", "ikut telegram", "buka contoh.com", "situs.co.id",
    "belajar.net", "x.org", "kontak.io", "a-b.link", "guru.id", "guru dot com", "kirim ke nama at gmail",
    "nama AT  Gmail dot  COM",
)
ISTILAH_L1 = (
    "kunci_jawaban", "kunci-jawaban", "kode-diagnosis", "mal rule", "mal-rule", "Mal_Rule", "Kode_Final",
    "kode-usulan", "kunci  _ jawaban", "kode__diagnosis", "m\u0430lrule", "kunci jaw\u0430ban",
)
LOLOS_L1 = (
    "Kunci keberhasilannya latihan rutin; diagnosis awal perlu penguatan, pembahasan kita lakukan di kelas 4 pada "
    "24-11-2026 pukul 15.30. Biaya Rp 49.000 dan nilai 80 85 90 sudah dicatat.",
    "Jadwal 24/11/2026 diganti; kita mulai pukul 15:30 di kelas 4.",
    "Aturan normal rule dan formal rule bukan istilah internal; rapat.Mei dibuka dan lihat gmail biasa.",
    "Telepon rumah tidak dipakai; sampai jumpa di kelas, ya.",
    "Ananda lebih rapi menulis di buku; coba soal nomor 3, 5, dan 7 sebelum pertemuan berikutnya.",
)


@pytest.mark.parametrize("catatan", LOLOS)
def test_catatan_wajar_lolos(catatan):
    assert store.periksa_catatan(catatan) is None


def test_teks_normal_panjang_hampir_batas_lolos():
    teks = (PARAGRAF * 30)[:2000]
    assert len(teks) == 2000 and store.periksa_catatan(teks) is None


@pytest.mark.parametrize("catatan", LOLOS_L1)
def test_kalimat_guru_wajar_tidak_salah_tolak_oleh_penyaring_diperluas(catatan):
    assert store.periksa_catatan(catatan) is None


@pytest.mark.parametrize("catatan", KONTAK_L1)
def test_penyaring_diperluas_menolak_pemisah_homoglyph_dan_penanda_tambahan(catatan):
    assert store.periksa_catatan(catatan) == "kontak"


@pytest.mark.parametrize("catatan", ISTILAH_L1)
def test_istilah_internal_dengan_garis_bawah_tanda_hubung_dan_homoglyph_ditolak(catatan):
    assert store.periksa_catatan(catatan) == "istilah_internal"


@pytest.mark.parametrize("catatan", KONTAK)
def test_kontak_ditolak_dengan_kode_kontak(catatan):
    assert store.periksa_catatan(catatan) == "kontak"


@pytest.mark.parametrize("catatan", ISTILAH)
def test_istilah_internal_ditolak_dengan_kode_istilah_internal(catatan):
    assert store.periksa_catatan(catatan) == "istilah_internal"


@pytest.mark.parametrize("catatan", KONTROL)
def test_karakter_kontrol_selain_newline_dan_tab_ditolak(catatan):
    assert store.periksa_catatan(catatan) == "kontrol"


def test_batas_panjang_2000_boleh_2001_ditolak():
    assert store.periksa_catatan("a" * 2000) is None
    assert store.periksa_catatan("a" * 2001) == "panjang"


def test_batas_sembilan_digit_tepat():
    assert store.periksa_catatan("12345678") is None
    assert store.periksa_catatan("123456789") == "kontak"
    assert store.periksa_catatan("24-11-2026") is None
    assert store.periksa_catatan("12345678 abc 1") is None


def test_prioritas_kode_panjang_lalu_kontrol_lalu_kontak_lalu_istilah():
    assert store.periksa_catatan("a" * 2001 + "http") == "panjang"
    assert store.periksa_catatan("\x00 http malrule") == "kontrol"
    assert store.periksa_catatan("http malrule") == "kontak"
    assert store.periksa_catatan("malrule") == "istilah_internal"


def test_selain_teks_melempar_typeerror():
    for nilai in (None, 5, b"x", ["x"]):
        with pytest.raises(TypeError):
            store.periksa_catatan(nilai)


# --- penegakan di store --------------------------------------------------------------------------

@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "catatan.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _draf(kon) -> int:
    anak = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik=GURU)
    store.buat_draf(kon, anak, GURU, _isi(), SEKARANG)
    return anak


@pytest.mark.parametrize("catatan,kode", [
    ("telepon 0812 3456 7890", "kontak"), ("lihat https://contoh.id", "kontak"),
    ("minta kunci jawaban", "istilah_internal"), ("a\x00b", "kontrol"), ("c" * 2001, "panjang"),
])
def test_simpan_catatan_menolak_catatan_tak_sah_tanpa_mengubah_dan_tanpa_membocorkan_isi(kon, catatan, kode):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, CATATAN)
    with pytest.raises(ValueError) as galat:
        store.simpan_catatan(kon, anak, catatan)
    assert kode in str(galat.value) and catatan[:12] not in str(galat.value)
    assert store.ambil(kon, anak)["catatan"] == CATATAN


def test_simpan_catatan_non_teks_ditolak(kon):
    anak = _draf(kon)
    with pytest.raises(ValueError):
        store.simpan_catatan(kon, anak, None)


def test_simpan_catatan_wajar_tetap_tersimpan(kon):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, "Catatan\nbaris dua\tbertab")
    assert store.ambil(kon, anak)["catatan"] == "Catatan\nbaris dua\tbertab"


@pytest.mark.parametrize("lama", ["hubungi 081234567890", "pakai kunci jawaban", "http://x.id", "a\x00b"])
def test_terbitkan_memeriksa_ulang_catatan_lama_dan_tidak_menerbitkan(kon, lama):
    anak = _draf(kon)
    kon.execute("UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?", (lama, anak))
    with pytest.raises(ValueError):
        store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
    laporan = store.ambil(kon, anak)
    assert laporan["diterbitkan"] is None and laporan["catatan"] == lama
    store.simpan_catatan(kon, anak, CATATAN)
    store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
    assert store.ambil(kon, anak)["diterbitkan"] is not None


# --- L2: bentuk efektif catatan untuk terbit ---------------------------------------------------------

@pytest.mark.parametrize("catatan", [
    ZW * 20, "\u00a0" * 20, "\u2003" * 12, " \t\n" * 10, "a" + ZW * 30 + "bcdefghi", "abcdefghi", "...... !!!",
    "a b c d e f g h i", "\u202f".join("abcdefghi"),
])
def test_terbitkan_menolak_catatan_yang_bentuk_efektifnya_kurang_dari_sepuluh_karakter(kon, catatan):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, catatan)          # catatan kosong/pendek tetap boleh disimpan sebagai draf
    with pytest.raises(ValueError) as galat:
        store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
    assert str(galat.value) in ("Catatan terlalu singkat untuk diterbitkan", "catatan wajib diisi sebelum terbit")
    laporan = store.ambil(kon, anak)
    assert laporan["diterbitkan"] is None and laporan["diterbitkan_oleh"] is None and laporan["catatan"] == catatan


@pytest.mark.parametrize("catatan", [
    "abcdefghij", "a b c d e f g h i j", "A1B2C3D4E5", "ab" + ZW + "cdefg\u00a0hij", "Sudah baik.", "!?!?!?!?!?",
])
def test_terbitkan_menerima_catatan_dengan_sepuluh_karakter_efektif_atau_lebih(kon, catatan):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, catatan)
    store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
    assert store.ambil(kon, anak)["diterbitkan"] is not None


def test_pesan_singkat_tetap_dan_berbeda_dari_pesan_kosong(kon):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, ZW * 15)
    with pytest.raises(ValueError, match="^Catatan terlalu singkat untuk diterbitkan$"):
        store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
    assert store.MIN_CATATAN_TERBIT == 10
    store.simpan_catatan(kon, anak, "")
    with pytest.raises(ValueError, match="^catatan wajib diisi sebelum terbit$"):
        store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT)
