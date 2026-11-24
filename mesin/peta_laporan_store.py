"""Penyimpanan laporan Peta Kemampuan untuk orang tua (D1-1): semua SQL tabel `peta_laporan` ada di sini.

Satu laporan per anak. Siklus: draf (`buat_draf`) -> catatan Guru (`simpan_catatan`) -> terbit (`terbitkan`); draf
boleh dihapus (`hapus_draf`), laporan terbit tidak. Isi snapshot dibangun server (`peta_laporan_snapshot`) dan
DIPERIKSA ulang tiap ditulis dan tiap dibaca, jadi baris dengan isi di luar allowlist tidak pernah sampai ke
pemanggil. Semua fungsi memakai koneksi DB belajar milik pemanggil dan TIDAK commit sendiri (transaksi pemanggil).
Waktu disuntik (`sekarang` = epoch detik, bukan bool) dan disimpan seperti `parent_report_store` (WIB).
Pemeriksaan kepemilikan anak oleh Guru adalah tugas pemanggil; kunci `siswa_id` selalu dari sisi server.
"""
from __future__ import annotations

import json
import re
import unicodedata

from peta_laporan_snapshot import periksa_isi

BATAS_CATATAN = 2000
BATAS_GURU = 64
MIN_CATATAN_TERBIT = 10   # karakter efektif (huruf/angka/tanda baca) agar catatan boleh diterbitkan
PESAN_CATATAN_SINGKAT = "Catatan terlalu singkat untuk diterbitkan"
_SPASI = " \t\n\r"
_KONTROL_BOLEH = "\n\t\r"
# Penanda arah teks (bidi override/isolate): Cf, jadi tak terlihat, tetapi bisa membalik tampilan catatan.
_BIDI_KONTROL = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_KATEGORI_EFEKTIF = ("L", "N", "P")
# Catatan Guru dibaca orang tua DAN anak (sesi murid): bukan jalur untuk kontak, tautan, atau istilah internal.
# CATATAN: penyaring kontak/istilah di bawah adalah PENGINGAT untuk Guru, bukan batas keamanan: teks yang disusun
# sengaja (ejaan lain, huruf mirip yang belum terdaftar, dst.) tetap bisa lolos.
CATATAN_PANJANG = "panjang"
CATATAN_KONTROL = "kontrol"
CATATAN_KONTAK = "kontak"
CATATAN_ISTILAH_INTERNAL = "istilah_internal"
_MIN_DIGIT_KONTAK = 9   # nomor telepon >= 9 digit; tanggal dd-mm-yyyy (8 digit) dan nilai pendek tidak ikut tertolak
_POLA_DIGIT_KONTAK = re.compile(r"\d(?:[\s.\-\u2010-\u2015()/,_:]*\d){%d}" % (_MIN_DIGIT_KONTAK - 1))
_POLA_TEL = re.compile(r"(?<![a-z0-9])tel:")
_PENANDA_KONTAK = ("wa.me", "whatsapp", "@", "http", "www.", "bit.ly", "instagram", "telegram")
_POLA_PENANDA_KONTAK = re.compile(
    r"[a-z0-9-]+\.(?:com|co\.id|id|net|org|me|io|link)\b"                    # nama domain umum (termasuk t.me)
    r"|\b(?:dot com|at gmail)\b")                                            # ejaan kata-kata (spasi sudah dirapatkan)
# Istilah dibandingkan sesudah [_-\s]+ dilipat jadi satu spasi ("kunci_jawaban", "kode-diagnosis", "mal rule").
_POLA_ISTILAH_INTERNAL = re.compile(
    r"malrule|kode final|kode usulan|kode diagnosis|kunci jawaban|(?<![a-z])mal rule")
# Huruf Sirilik/Yunani yang paling sering dipakai meniru huruf Latin (a e o p c x y i h j s, dst.).
_HOMOGLYPH = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0445": "x", "\u0443": "y",
    "\u0456": "i", "\u04bb": "h", "\u0458": "j", "\u0455": "s",
    "\u03b1": "a", "\u03b5": "e", "\u03bf": "o", "\u03c1": "p", "\u03b9": "i", "\u03c7": "x",
})
_KOLOM = "id, siswa_id, isi, catatan, guru, dibuat, diterbitkan, diterbitkan_oleh"


def _epoch(sekarang) -> int:
    if type(sekarang) is not int:
        raise ValueError("sekarang harus epoch detik bilangan bulat")
    return sekarang


def _guru(guru) -> str:
    if type(guru) is not str or not 1 <= len(guru) <= BATAS_GURU:
        raise ValueError("akun guru tidak sah")
    return guru


def _baris_ke_dict(baris) -> dict:
    kunci = ("id", "siswa_id", "isi", "catatan", "guru", "dibuat", "diterbitkan", "diterbitkan_oleh")
    laporan = {k: baris[i] for i, k in enumerate(kunci)}
    try:
        laporan["isi"] = periksa_isi(json.loads(laporan["isi"]))
    except json.JSONDecodeError:
        raise ValueError("isi laporan peta rusak") from None
    return laporan


def buat_draf(kon, siswa_id: int, guru: str, isi: dict, sekarang) -> int:
    """Draf baru untuk anak ini; draf/laporan kedua untuk anak yang sama = ValueError."""
    isi_bersih = periksa_isi(isi)
    akun = _guru(guru)
    waktu = _epoch(sekarang)
    if kon.execute("SELECT 1 FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone() is not None:
        raise ValueError("anak ini sudah punya laporan peta")
    cur = kon.execute(
        """INSERT INTO peta_laporan (siswa_id, isi, guru, dibuat)
           VALUES (?, ?, ?, datetime(?, 'unixepoch', '+7 hours'))""",
        (siswa_id, json.dumps(isi_bersih, ensure_ascii=False, sort_keys=True), akun, waktu),
    )
    return cur.lastrowid


def ambil(kon, siswa_id: int):
    """Laporan anak ini (draf atau terbit) dengan isi tervalidasi ulang, atau None. Isi tak sah = ValueError."""
    baris = kon.execute(
        "SELECT %s FROM peta_laporan WHERE siswa_id = ?" % _KOLOM, (siswa_id,),
    ).fetchone()
    return None if baris is None else _baris_ke_dict(baris)


def _normal(catatan: str) -> str:
    """Bentuk pembanding: NFKC, tanpa karakter format (lebar nol, bidi, soft hyphen), huruf kecil, homoglyph dilipat."""
    tanpa_format = "".join(c for c in catatan if unicodedata.category(c) != "Cf")
    return unicodedata.normalize("NFKC", tanpa_format).casefold().translate(_HOMOGLYPH)


def _kode_isi(catatan: str):
    """Kode galat untuk isi catatan (kontak/istilah internal) atau None; catatan sudah lolos panjang dan kontrol."""
    bentuk = _normal(catatan)
    rapat = " ".join(bentuk.split())
    if (_POLA_DIGIT_KONTAK.search(bentuk) or _POLA_TEL.search(bentuk) or any(p in bentuk for p in _PENANDA_KONTAK)
            or _POLA_PENANDA_KONTAK.search(rapat)):
        return CATATAN_KONTAK
    if _POLA_ISTILAH_INTERNAL.search(re.sub(r"[_\-\s]+", " ", bentuk)):
        return CATATAN_ISTILAH_INTERNAL
    return None


def periksa_catatan(catatan: str):
    """Murni: None bila catatan Guru sah; selain itu KODE galat tetap (panjang, kontrol, kontak, istilah_internal).

    Satu sumber kebenaran untuk simpan, terbit, dan halaman Guru. Kode tidak memuat bagian catatan yang ditolak.
    """
    if type(catatan) is not str:
        raise TypeError("catatan harus str")
    if len(catatan) > BATAS_CATATAN:
        return CATATAN_PANJANG
    if any(c in _BIDI_KONTROL or (unicodedata.category(c) == "Cc" and c not in _KONTROL_BOLEH) for c in catatan):
        return CATATAN_KONTROL
    return _kode_isi(catatan)


def simpan_catatan(kon, siswa_id: int, catatan: str) -> None:
    """Ganti catatan Guru pada DRAF; catatan tak sah (periksa_catatan), laporan terbit, atau tak ada = ValueError."""
    if type(catatan) is not str:
        raise ValueError("catatan harus teks")
    kode = periksa_catatan(catatan)
    if kode is not None:
        raise ValueError("catatan tidak sah: %s" % kode)
    cur = kon.execute(
        "UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ? AND diterbitkan IS NULL",
        (catatan, siswa_id),
    )
    if cur.rowcount != 1:
        raise ValueError("laporan bukan draf milik anak ini")


def catatan_cukup_untuk_terbit(catatan: str) -> bool:
    """Murni: bentuk efektif catatan memuat >= MIN_CATATAN_TERBIT karakter huruf/angka/tanda baca (kategori L, N, P).

    Karakter format (Cf: U+200B dst.), spasi Unicode (U+00A0, U+2003, dst.), dan kontrol tidak dihitung, jadi karakter
    tak terlihat tidak membuat catatan dianggap terisi."""
    efektif = sum(unicodedata.category(c)[0] in _KATEGORI_EFEKTIF for c in catatan)
    return efektif >= MIN_CATATAN_TERBIT


def terbitkan(kon, siswa_id: int, guru: str, sekarang) -> str:
    """Terbitkan draf yang catatannya cukup (catatan_cukup_untuk_terbit); mengembalikan waktu terbit. Terbit kedua = ValueError.

    Draf boleh menyimpan catatan kosong/pendek (`simpan_catatan`); aturan panjang efektif hanya berlaku saat terbit.
    """
    akun = _guru(guru)
    waktu = _epoch(sekarang)
    laporan = ambil(kon, siswa_id)
    if laporan is None or laporan["diterbitkan"] is not None:
        raise ValueError("laporan bukan draf milik anak ini")
    if not laporan["catatan"].strip(_SPASI):
        raise ValueError("catatan wajib diisi sebelum terbit")
    if periksa_catatan(laporan["catatan"]) is not None:
        raise ValueError("catatan tersimpan tidak sah; ubah dulu sebelum terbit")
    if not catatan_cukup_untuk_terbit(laporan["catatan"]):
        raise ValueError(PESAN_CATATAN_SINGKAT)
    cur = kon.execute(
        """UPDATE peta_laporan SET diterbitkan = datetime(?, 'unixepoch', '+7 hours'), diterbitkan_oleh = ?
           WHERE siswa_id = ? AND diterbitkan IS NULL""",
        (waktu, akun, siswa_id),
    )
    if cur.rowcount != 1:
        raise ValueError("laporan bukan draf milik anak ini")
    return kon.execute("SELECT diterbitkan FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone()[0]


def hapus_draf(kon, siswa_id: int) -> bool:
    """Hapus DRAF anak ini; True bila terhapus, False bila tidak ada. Laporan terbit = ValueError (tidak dihapus)."""
    laporan = ambil(kon, siswa_id)
    if laporan is None:
        return False
    if laporan["diterbitkan"] is not None:
        raise ValueError("laporan terbit tidak dihapus")
    return kon.execute(
        "DELETE FROM peta_laporan WHERE siswa_id = ? AND diterbitkan IS NULL", (siswa_id,),
    ).rowcount == 1


def terbit_terakhir(kon, siswa_id: int):
    """Laporan TERBIT untuk halaman orang tua: isi tervalidasi, catatan, waktu terbit; None bila draf/tidak ada.

    Tidak memuat akun Guru (pembuat maupun penerbit); kolom itu tidak dibaca sama sekali.
    """
    baris = kon.execute(
        "SELECT isi, catatan, diterbitkan FROM peta_laporan WHERE siswa_id = ? AND diterbitkan IS NOT NULL",
        (siswa_id,),
    ).fetchone()
    if baris is None:
        return None
    try:
        isi = periksa_isi(json.loads(baris[0]))
    except json.JSONDecodeError:
        raise ValueError("isi laporan peta rusak") from None
    return {"isi": isi, "catatan": baris[1], "diterbitkan": baris[2]}
