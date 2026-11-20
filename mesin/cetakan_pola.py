"""Cetakan soal berpola: data JSON (bukan kode) yang membangkitkan soal teks + angka.

Cetakan = teks dengan placeholder `{a}`, rentang variabel, syarat, dan rumus `kunci`. AI atau
admin hanya menulis DATA; mesin ini yang memvalidasi dan menghitung. Invariant (plan
`2026-11-20-cetakan-ai.md` §6): kunci SELALU dihitung mesin dari rumus tervalidasi; tidak ada
`eval`/`exec`/`compile`/`str.format` atas isi cetakan.

Evaluator ekspresi (kunci dan syarat) = validator AST BERTIPE + evaluator rekursif sendiri:
- Posisi aritmetika (akar `kunci`, operan BinOp/UnaryOp/Compare) hanya menerima BinOp
  (+ - * // %), UnaryOp (-), Constant int 0..1.000.000 (bukan bool), dan Name variabel terdaftar.
- Posisi boolean (akar tiap `syarat`, nilai BoolOp) hanya menerima Compare (Lt/LtE/Gt/GtE/Eq/
  NotEq, boleh berantai) dan BoolOp (and/or). Compare/BoolOp tidak boleh di `kunci`, dan
  ekspresi aritmetika tanpa perbandingan tidak boleh jadi syarat.
- Panjang ekspresi <= 120 karakter (dicek SEBELUM parse); jumlah node ekspresi <= 40. Node
  dihitung = instance `ast.expr` (BinOp, UnaryOp, Constant, Name, Compare, BoolOp); simbol
  operator/konteks (`Add`, `Load`, ...) tidak dihitung.
Semua selain itu (Call, Attribute, Subscript, Pow, `/`, Lambda, string, float, f-string, ...)
ditolak `ValueError` saat validasi.

Saat evaluasi, sampel yang tak sah (pembagi 0, operan negatif pada `//`/`%`, `//` tak habis,
nilai antara > 10^12) memakai
`_SampelTakSah` privat dan diundi ulang; struktur rusak selalu `ValueError` saat validasi.

Murni stdlib + `kurikulum_kelas` (data beku); tanpa I/O; tidak boleh diimpor modul inti soal.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import functools
import hashlib
import json
import random
import re
from typing import Dict, FrozenSet, List, Optional, Tuple
import unicodedata

import kurikulum_kelas

MAKS_JUDUL = 80
MAKS_TEKS = 300
MAKS_PEMBAHASAN = 300
MAKS_VARIABEL = 4
MAKS_SYARAT = 5
MAKS_EKSPRESI = 120
MAKS_NODE = 40
BATAS_KONSTANTA = 1_000_000
BATAS_ANTARA = 10 ** 12
MAKS_PERCOBAAN = 200
JUMLAH_SAMPEL = 200
MIN_UNIK = 30
BANYAK_CONTOH = 10
# Salinan `topic_school_basics._NAMA_ANAK` (nama sintetis); disalin agar modul ini tidak
# menarik modul inti soal. Tes menjaga keduanya tetap sama.
NAMA_SINTETIS = ("Rafi", "Nadia", "Bimo", "Sinta")

_KUNCI_DIIZINKAN = frozenset(
    {"kelas", "bab", "judul", "teks", "variabel", "nama", "syarat", "kunci", "pembahasan"})
_KUNCI_WAJIB = frozenset({"kelas", "bab", "judul", "teks", "variabel", "kunci"})
_NAMA_VARIABEL = re.compile(r"^[a-z]$")
_PLACEHOLDER = re.compile(r"\{([a-z]+)\}")
_OP_ARITMETIKA = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
_OP_BANDING = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)

Variabel = Tuple[Tuple[str, int, int], ...]


class _SampelTakSah(Exception):
    """Sampel parameter tak sah (pembagi 0, tak habis dibagi, nilai antara terlalu besar)."""


class KunciNegatif(ValueError):
    """Sampel lolos syarat tetapi kuncinya negatif: cetakan butuh syarat tambahan."""


@dataclass(frozen=True)
class Cetakan:
    """Cetakan tervalidasi dan dinormalkan; `variabel` terurut menurut nama."""

    kelas: int
    bab: int
    judul: str
    teks: str
    variabel: Variabel
    nama: bool
    syarat: Tuple[str, ...]
    kunci: str
    pembahasan: str


@dataclass(frozen=True)
class SoalCetakan:
    """Satu soal hasil bangkitan. `parameter` jangan diubah pemakai (tidak ikut hash)."""

    teks: str
    kunci: str
    pembahasan: str
    parameter: Dict[str, int] = field(hash=False)
    tanda_tangan: str


@dataclass(frozen=True)
class HasilKelayakan:
    lolos: bool
    alasan: Tuple[str, ...]
    jumlah_unik: int
    contoh: Tuple[SoalCetakan, ...]


# --- validasi ekspresi -------------------------------------------------------

def _galat(bidang: str, pesan: str) -> ValueError:
    return ValueError(f"Bidang '{bidang}': {pesan}")


def _periksa_aritmetika(node, nama_var: FrozenSet[str], bidang: str) -> None:
    if isinstance(node, ast.Constant):
        nilai = node.value
        if type(nilai) is not int or not 0 <= nilai <= BATAS_KONSTANTA:
            raise _galat(bidang, f"konstanta harus bilangan bulat 0..{BATAS_KONSTANTA}.")
    elif isinstance(node, ast.Name):
        if node.id not in nama_var:
            raise _galat(bidang, f"variabel '{node.id}' tidak terdaftar.")
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.USub):
            raise _galat(bidang, "hanya tanda minus yang boleh sebagai operator satu operan.")
        _periksa_aritmetika(node.operand, nama_var, bidang)
    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, _OP_ARITMETIKA):
            raise _galat(bidang, "operator hanya + - * // % yang diizinkan.")
        _periksa_aritmetika(node.left, nama_var, bidang)
        _periksa_aritmetika(node.right, nama_var, bidang)
    else:
        raise _galat(bidang, f"unsur {type(node).__name__} tidak diizinkan di rumus aritmetika.")


def _periksa_boolean(node, nama_var: FrozenSet[str], bidang: str) -> None:
    if isinstance(node, ast.Compare):
        if not all(isinstance(op, _OP_BANDING) for op in node.ops):
            raise _galat(bidang, "pembanding hanya < <= > >= == != yang diizinkan.")
        for operan in [node.left, *node.comparators]:
            _periksa_aritmetika(operan, nama_var, bidang)
    elif isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise _galat(bidang, "operator logika hanya and/or.")
        for nilai in node.values:
            _periksa_boolean(nilai, nama_var, bidang)
    else:
        raise _galat(bidang, "syarat harus berupa perbandingan (boleh digabung and/or).")


def _urai_ekspresi(teks, bidang: str):
    """Parse ekspresi dengan batas panjang dan node; ValueError berbahasa Indonesia."""
    if not isinstance(teks, str):
        raise _galat(bidang, "harus berupa teks ekspresi.")
    teks = teks.strip()
    if not teks:
        raise _galat(bidang, "tidak boleh kosong.")
    if len(teks) > MAKS_EKSPRESI:
        raise _galat(bidang, f"maksimal {MAKS_EKSPRESI} karakter.")
    try:
        pohon = ast.parse(teks, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as err:
        raise _galat(bidang, "bukan ekspresi yang sah.") from err
    if sum(isinstance(node, ast.expr) for node in ast.walk(pohon)) > MAKS_NODE:
        raise _galat(bidang, f"terlalu rumit (maksimal {MAKS_NODE} node).")
    return pohon.body


@functools.lru_cache(maxsize=512)
def _ekspresi_tervalidasi(teks: str, nama_var: FrozenSet[str], jenis: str):
    """Pohon ekspresi yang sudah lolos validasi bertipe; jenis 'kunci' atau 'syarat'."""
    akar = _urai_ekspresi(teks, jenis)
    if jenis == "kunci":
        _periksa_aritmetika(akar, nama_var, jenis)
    else:
        _periksa_boolean(akar, nama_var, jenis)
    return akar


def _normalkan_ekspresi(teks, nama_var: FrozenSet[str], jenis: str) -> str:
    if not isinstance(teks, str):
        raise _galat(jenis, "harus berupa teks ekspresi.")
    bersih = teks.strip()
    _ekspresi_tervalidasi(bersih, nama_var, jenis)
    return bersih


# --- evaluasi ----------------------------------------------------------------

def _periksa_besar(nilai: int) -> int:
    if abs(nilai) > BATAS_ANTARA:
        raise _SampelTakSah("nilai antara terlalu besar")
    return nilai


def _hitung_binop(op, kiri: int, kanan: int) -> int:
    if isinstance(op, ast.Add):
        return kiri + kanan
    if isinstance(op, ast.Sub):
        return kiri - kanan
    if isinstance(op, ast.Mult):
        return kiri * kanan
    if kanan == 0:
        raise _SampelTakSah("pembagi nol")
    if kiri < 0 or kanan < 0:
        # Pembagian/sisa bilangan negatif (dibulatkan ke bawah) bukan materi SD dan membingungkan.
        raise _SampelTakSah("operan negatif pada // atau %")
    if isinstance(op, ast.FloorDiv):
        if kiri % kanan != 0:
            raise _SampelTakSah("pembagian tak habis")
        return kiri // kanan
    return kiri % kanan


def _hitung(node, nilai: Dict[str, int]):
    """Evaluasi rekursif atas node yang SUDAH divalidasi. Tidak memakai eval/compile."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return nilai[node.id]
    if isinstance(node, ast.UnaryOp):
        return _periksa_besar(-_hitung(node.operand, nilai))
    if isinstance(node, ast.BinOp):
        return _periksa_besar(_hitung_binop(
            node.op, _hitung(node.left, nilai), _hitung(node.right, nilai)))
    if isinstance(node, ast.BoolOp):
        hasil = [_hitung(sub, nilai) for sub in node.values]
        return all(hasil) if isinstance(node.op, ast.And) else any(hasil)
    if isinstance(node, ast.Compare):
        return _hitung_compare(node, nilai)
    raise ValueError("Node ekspresi tak dikenal.")  # tak tercapai bila sudah divalidasi


def _hitung_compare(node, nilai: Dict[str, int]) -> bool:
    kiri = _hitung(node.left, nilai)
    for op, sisi in zip(node.ops, node.comparators):
        kanan = _hitung(sisi, nilai)
        if isinstance(op, ast.Lt):
            lolos = kiri < kanan
        elif isinstance(op, ast.LtE):
            lolos = kiri <= kanan
        elif isinstance(op, ast.Gt):
            lolos = kiri > kanan
        elif isinstance(op, ast.GtE):
            lolos = kiri >= kanan
        elif isinstance(op, ast.Eq):
            lolos = kiri == kanan
        else:
            lolos = kiri != kanan
        if not lolos:
            return False
        kiri = kanan
    return True


# --- validasi cetakan --------------------------------------------------------

def _periksa_int(nilai, bidang: str, kecil: int, besar: int) -> int:
    if type(nilai) is not int or not kecil <= nilai <= besar:
        raise _galat(bidang, f"harus bilangan bulat {kecil}..{besar}.")
    return nilai


def _normalkan_teks(nilai, bidang: str, kecil: int, besar: int) -> str:
    if not isinstance(nilai, str):
        raise _galat(bidang, "harus berupa teks.")
    bersih = nilai.strip()
    if not kecil <= len(bersih) <= besar:
        raise _galat(bidang, f"harus {kecil}-{besar} karakter." if kecil else f"maksimal {besar} karakter.")
    if "<" in bersih or ">" in bersih:
        raise _galat(bidang, "tidak boleh memuat tanda < atau >.")
    if any(unicodedata.category(huruf).startswith("C") for huruf in bersih):
        raise _galat(bidang, "tidak boleh memuat karakter kontrol.")
    return bersih


def _normalkan_variabel(nilai) -> Variabel:
    if not isinstance(nilai, dict) or not 1 <= len(nilai) <= MAKS_VARIABEL:
        raise _galat("variabel", f"harus objek berisi 1-{MAKS_VARIABEL} variabel.")
    hasil = []
    for nama, rentang in nilai.items():
        if not isinstance(nama, str) or not _NAMA_VARIABEL.match(nama):
            raise _galat("variabel", f"nama variabel {nama!r} harus satu huruf kecil a-z.")
        if (not isinstance(rentang, (list, tuple)) or len(rentang) != 2
                or any(type(x) is not int for x in rentang)):
            raise _galat("variabel", f"rentang '{nama}' harus [min, max] bilangan bulat.")
        kecil, besar = rentang
        if not 0 <= kecil <= besar <= BATAS_KONSTANTA:
            raise _galat("variabel", f"rentang '{nama}' harus 0 <= min <= max <= {BATAS_KONSTANTA}.")
        hasil.append((nama, kecil, besar))
    return tuple(sorted(hasil))


def _periksa_placeholder(teks: str, bidang: str, boleh: FrozenSet[str]) -> FrozenSet[str]:
    """Hanya `{nama}` terdaftar; kembalikan nama yang dipakai. Kurung kurawal lain ditolak."""
    dipakai = set()
    for cocok in _PLACEHOLDER.finditer(teks):
        if cocok.group(1) not in boleh:
            raise _galat(bidang, f"placeholder {{{cocok.group(1)}}} tidak terdaftar.")
        dipakai.add(cocok.group(1))
    if "{" in _PLACEHOLDER.sub("", teks) or "}" in _PLACEHOLDER.sub("", teks):
        raise _galat(bidang, "kurung kurawal hanya boleh untuk placeholder seperti {a}.")
    return frozenset(dipakai)


def _normalkan_syarat(nilai, nama_var: FrozenSet[str]) -> Tuple[str, ...]:
    if not isinstance(nilai, (list, tuple)) or len(nilai) > MAKS_SYARAT:
        raise _galat("syarat", f"harus daftar berisi 0-{MAKS_SYARAT} ekspresi.")
    return tuple(_normalkan_ekspresi(teks, nama_var, "syarat") for teks in nilai)


def _periksa_bab(kelas: int, bab: int) -> None:
    for data in kurikulum_kelas.KELAS:
        if data.kelas == kelas and any(b.nomor == bab for b in data.bab):
            return
    raise _galat("bab", f"bab {bab} tidak ada di kelas {kelas}.")


def _periksa_kunci_objek(isi) -> None:
    if not isinstance(isi, dict):
        raise ValueError("Cetakan harus berupa objek JSON.")
    asing = sorted(str(k) for k in isi if k not in _KUNCI_DIIZINKAN)
    if asing:
        raise ValueError(f"Bidang tidak dikenal: {', '.join(asing)}.")
    kurang = sorted(_KUNCI_WAJIB - set(isi))
    if kurang:
        raise ValueError(f"Bidang wajib belum diisi: {', '.join(kurang)}.")


def validasi(isi) -> Cetakan:
    """Validasi dict (dari JSON) menjadi `Cetakan` ternormalkan; ValueError menyebut bidangnya."""
    _periksa_kunci_objek(isi)
    kelas = _periksa_int(isi["kelas"], "kelas", 1, 6)
    bab = _periksa_int(isi["bab"], "bab", 1, 1_000)
    _periksa_bab(kelas, bab)
    judul = _normalkan_teks(isi["judul"], "judul", 1, MAKS_JUDUL)
    teks = _normalkan_teks(isi["teks"], "teks", 1, MAKS_TEKS)
    variabel = _normalkan_variabel(isi["variabel"])
    nama = isi.get("nama", False)
    if type(nama) is not bool:
        raise _galat("nama", "harus true atau false.")
    nama_var = frozenset(v[0] for v in variabel)
    pembahasan = _normalkan_teks(isi.get("pembahasan", ""), "pembahasan", 0, MAKS_PEMBAHASAN)
    _periksa_semua_placeholder(teks, pembahasan, nama_var, nama)
    syarat = _normalkan_syarat(isi.get("syarat", []), nama_var)
    kunci = _normalkan_ekspresi(isi["kunci"], nama_var, "kunci")
    return Cetakan(kelas, bab, judul, teks, variabel, nama, syarat, kunci, pembahasan)


def _periksa_semua_placeholder(teks: str, pembahasan: str, nama_var: FrozenSet[str], nama: bool) -> None:
    boleh_teks = nama_var | ({"nama"} if nama else set())
    dipakai = _periksa_placeholder(teks, "teks", frozenset(boleh_teks))
    _periksa_placeholder(pembahasan, "pembahasan", frozenset(boleh_teks | {"kunci"}))
    tak_tampil = sorted(nama_var - dipakai)
    if tak_tampil:
        # Variabel tak tampil di teks membuat dua soal sama persis punya kunci berbeda.
        raise _galat("teks", f"variabel {', '.join(tak_tampil)} harus muncul sebagai placeholder.")


def ke_dict(cetakan: Cetakan) -> dict:
    """Bentuk dict kanonis (kebalikan `validasi`): `validasi(ke_dict(c)) == c`."""
    return {
        "kelas": cetakan.kelas, "bab": cetakan.bab, "judul": cetakan.judul, "teks": cetakan.teks,
        "variabel": {nama: [kecil, besar] for nama, kecil, besar in cetakan.variabel},
        "nama": cetakan.nama, "syarat": list(cetakan.syarat), "kunci": cetakan.kunci,
        "pembahasan": cetakan.pembahasan,
    }


def ke_json(cetakan: Cetakan) -> str:
    return json.dumps(ke_dict(cetakan), ensure_ascii=False, sort_keys=True)


def dari_json(teks) -> Cetakan:
    """Urai JSON lalu validasi; ValueError bila bukan JSON sah atau isinya tak lolos."""
    if not isinstance(teks, str):
        raise ValueError("Cetakan JSON harus berupa teks.")
    try:
        isi = json.loads(teks)
    except (ValueError, RecursionError) as err:
        raise ValueError("Cetakan bukan JSON yang sah.") from err
    return validasi(isi)


# --- bangkitan soal ----------------------------------------------------------

def ribuan(n: int) -> str:
    """Titik ribuan gaya Indonesia (salinan kecil `school_numbers_common.ribuan`)."""
    return f"{n:,}".replace(",", ".")


def _isi_placeholder(teks: str, nilai: Dict[str, str]) -> str:
    """Satu kali ganti `{nama}` dari kamus; nama tak dikenal dibiarkan (terdeteksi uji kelayakan)."""
    return _PLACEHOLDER.sub(lambda m: nilai.get(m.group(1), m.group(0)), teks)


def _tanda_tangan(cetakan: Cetakan, parameter: Dict[str, int]) -> str:
    """Hash (kelas, bab, teks pola, parameter terurut); `nama` sengaja tidak ikut."""
    muatan = json.dumps(
        [cetakan.kelas, cetakan.bab, cetakan.teks, sorted(parameter.items())],
        ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(muatan.encode("utf-8")).hexdigest()


def _coba_sampel(cetakan: Cetakan, rng: random.Random) -> Optional[Tuple[Dict[str, int], int]]:
    """Satu undian; None bila syarat gagal atau sampel tak sah, KunciNegatif bila kunci < 0."""
    nama_var = frozenset(v[0] for v in cetakan.variabel)
    parameter = {nama: rng.randint(kecil, besar) for nama, kecil, besar in cetakan.variabel}
    try:
        for syarat in cetakan.syarat:
            if not _hitung(_ekspresi_tervalidasi(syarat, nama_var, "syarat"), parameter):
                return None
        kunci = _hitung(_ekspresi_tervalidasi(cetakan.kunci, nama_var, "kunci"), parameter)
    except _SampelTakSah:
        return None
    if kunci < 0:
        raise KunciNegatif("Kunci negatif: tambahkan syarat agar hasil tidak kurang dari 0.")
    return parameter, kunci


def buat_soal(cetakan: Cetakan, seed: int) -> SoalCetakan:
    """Soal deterministik dari (cetakan, seed). ValueError("syarat terlalu ketat") bila 200 undian gagal."""
    if type(seed) is not int:
        raise ValueError("Seed harus bilangan bulat.")
    rng = random.Random(f"cetakan:{seed}")
    for _ in range(MAKS_PERCOBAAN):
        sampel = _coba_sampel(cetakan, rng)
        if sampel is not None:
            return _rakit_soal(cetakan, rng, *sampel)
    raise ValueError("syarat terlalu ketat")


def _rakit_soal(cetakan: Cetakan, rng: random.Random, parameter: Dict[str, int], kunci: int) -> SoalCetakan:
    isian = {nama: ribuan(nilai) for nama, nilai in parameter.items()}
    if cetakan.nama:
        isian["nama"] = rng.choice(NAMA_SINTETIS)
    teks = _isi_placeholder(cetakan.teks, isian)
    pembahasan = _isi_placeholder(cetakan.pembahasan, {**isian, "kunci": ribuan(kunci)})
    return SoalCetakan(teks, str(kunci), pembahasan, dict(sorted(parameter.items())),
                       _tanda_tangan(cetakan, parameter))


def _kumpulkan(cetakan: Cetakan, seeds) -> Tuple[List[SoalCetakan], List[str]]:
    """Soal per seed yang berhasil, plus alasan gagal (satu per jenis, tanpa duplikat)."""
    soal, alasan = [], []
    for seed in seeds:
        try:
            soal.append(buat_soal(cetakan, seed))
        except KunciNegatif:
            alasan.append("ada kunci negatif")
        except ValueError as err:
            alasan.append(str(err))
    return soal, alasan


def contoh(cetakan: Cetakan, n: int = BANYAK_CONTOH, seed_awal: int = 1) -> Tuple[SoalCetakan, ...]:
    """Hingga `n` soal contoh dari seed berurutan; seed yang gagal dilewati (maks 20n percobaan)."""
    if type(n) is not int or n < 1:
        raise ValueError("Banyak contoh harus bilangan bulat positif.")
    hasil: List[SoalCetakan] = []
    for seed in range(seed_awal, seed_awal + 20 * n):
        if len(hasil) >= n:
            break
        soal, _ = _kumpulkan(cetakan, (seed,))
        hasil.extend(soal)
    return tuple(hasil)


def uji_kelayakan(cetakan: Cetakan) -> HasilKelayakan:
    """200 seed deterministik (1..200). Gagal bila < 30 tanda tangan unik, ada kunci negatif,
    atau teks hasil masih memuat `{`/`}`."""
    soal, gagal = _kumpulkan(cetakan, range(1, JUMLAH_SAMPEL + 1))
    alasan: List[str] = []
    if "ada kunci negatif" in gagal:
        alasan.append("ada kunci negatif; tambahkan syarat agar kunci tidak kurang dari 0")
    if any(("{" in s.teks or "}" in s.teks or "{" in s.pembahasan or "}" in s.pembahasan) for s in soal):
        alasan.append("teks hasil masih memuat placeholder sisa")
    unik = len({s.tanda_tangan for s in soal})
    if unik < MIN_UNIK:
        alasan.append(f"hanya {unik} soal unik dari {JUMLAH_SAMPEL} seed (minimal {MIN_UNIK})")
    return HasilKelayakan(not alasan, tuple(alasan), unik, tuple(soal[:BANYAK_CONTOH]))
