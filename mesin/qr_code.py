"""Kode QR server-side (stdlib murni) untuk tautan sesi anak.

Hanya yang dibutuhkan tautan: mode byte, koreksi galat M, versi 1–10 (≤ 213 byte),
keluaran SVG tanpa JavaScript. Mengikuti ISO/IEC 18004 (alur sama dengan
implementasi rujukan Project Nayuki). Diuji bit per bit terhadap libqrencode
(golden di ``__tests__/test_qr_code.py``) dan didekode kamera/BarcodeDetector.

Bukan pembangkit umum: input terlalu panjang → ValueError, pemanggil wajib tetap
menampilkan tautan teks sebagai cadangan.
"""
from __future__ import annotations

from html import escape

# Per versi 1..10, koreksi galat M (ISO/IEC 18004 tabel 9).
_ECC_PER_BLOK = (10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
_JUMLAH_BLOK = (1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
_TOTAL_CODEWORD = (26, 44, 70, 100, 134, 172, 196, 242, 292, 346)
_POSISI_ALIGNMENT = (
    (), (6, 18), (6, 22), (6, 26), (6, 30), (6, 34),
    (6, 22, 38), (6, 24, 42), (6, 26, 46), (6, 28, 50),
)
_FORMAT_ECC_M = 0  # bit format ECL: L=1, M=0, Q=3, H=2
VERSI_MAKS = 10
ZONA_SENYAP = 4


def _kapasitas_data(versi: int) -> int:
    i = versi - 1
    return _TOTAL_CODEWORD[i] - _ECC_PER_BLOK[i] * _JUMLAH_BLOK[i]


def _bit_hitungan(versi: int) -> int:
    return 8 if versi <= 9 else 16


def _kali_gf(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _pembagi_rs(derajat: int) -> list[int]:
    hasil = [0] * (derajat - 1) + [1]
    akar = 1
    for _ in range(derajat):
        for j in range(derajat):
            hasil[j] = _kali_gf(hasil[j], akar)
            if j + 1 < derajat:
                hasil[j] ^= hasil[j + 1]
        akar = _kali_gf(akar, 0x02)
    return hasil


def _sisa_rs(data: list[int], pembagi: list[int]) -> list[int]:
    hasil = [0] * len(pembagi)
    for b in data:
        faktor = b ^ hasil.pop(0)
        hasil.append(0)
        for i, koef in enumerate(pembagi):
            hasil[i] ^= _kali_gf(koef, faktor)
    return hasil


def _pilih_versi(n_byte: int) -> int:
    for versi in range(1, VERSI_MAKS + 1):
        if 4 + _bit_hitungan(versi) + 8 * n_byte <= _kapasitas_data(versi) * 8:
            return versi
    raise ValueError("Teks terlalu panjang untuk kode QR tautan.")


def _codeword_data(isi: bytes, versi: int) -> list[int]:
    bit: list[int] = []

    def tambah(nilai: int, panjang: int) -> None:
        bit.extend((nilai >> i) & 1 for i in reversed(range(panjang)))

    tambah(0b0100, 4)
    tambah(len(isi), _bit_hitungan(versi))
    for b in isi:
        tambah(b, 8)
    kapasitas = _kapasitas_data(versi) * 8
    tambah(0, min(4, kapasitas - len(bit)))
    tambah(0, -len(bit) % 8)
    hasil = [int("".join(map(str, bit[i:i + 8])), 2) for i in range(0, len(bit), 8)]
    pad = 0xEC
    while len(hasil) < kapasitas // 8:
        hasil.append(pad)
        pad ^= 0xEC ^ 0x11
    return hasil


def _dengan_ecc(data: list[int], versi: int) -> list[int]:
    i = versi - 1
    n_blok, panjang_ecc, total = _JUMLAH_BLOK[i], _ECC_PER_BLOK[i], _TOTAL_CODEWORD[i]
    n_pendek = n_blok - total % n_blok
    panjang_pendek = total // n_blok
    pembagi = _pembagi_rs(panjang_ecc)
    blok: list[list[int]] = []
    k = 0
    for b in range(n_blok):
        panjang = panjang_pendek - panjang_ecc + (0 if b < n_pendek else 1)
        dat = data[k:k + panjang]
        k += panjang
        ecc = _sisa_rs(dat, pembagi)
        if b < n_pendek:
            dat = dat + [0]
        blok.append(dat + ecc)
    hasil = []
    for i in range(len(blok[0])):
        for j, isi in enumerate(blok):
            if i != panjang_pendek - panjang_ecc or j >= n_pendek:
                hasil.append(isi[i])
    return hasil


class _Matriks:
    def __init__(self, versi: int):
        self.versi = versi
        self.ukuran = versi * 4 + 17
        self.modul = [[False] * self.ukuran for _ in range(self.ukuran)]
        self.fungsi = [[False] * self.ukuran for _ in range(self.ukuran)]

    def set_fungsi(self, x: int, y: int, gelap: bool) -> None:
        self.modul[y][x] = gelap
        self.fungsi[y][x] = True

    def pola_fungsi(self) -> None:
        n = self.ukuran
        for i in range(n):
            self.set_fungsi(6, i, i % 2 == 0)
            self.set_fungsi(i, 6, i % 2 == 0)
        for x, y in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < n and 0 <= yy < n:
                        self.set_fungsi(xx, yy, max(abs(dx), abs(dy)) not in (2, 4))
        posisi = _POSISI_ALIGNMENT[self.versi - 1]
        akhir = len(posisi) - 1
        for i, px in enumerate(posisi):
            for j, py in enumerate(posisi):
                if (i, j) in ((0, 0), (0, akhir), (akhir, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_fungsi(px + dx, py + dy, max(abs(dx), abs(dy)) != 1)
        self.bit_format(0)
        self.bit_versi()

    def bit_format(self, mask: int) -> None:
        data = (_FORMAT_ECC_M << 3) | mask
        sisa = data
        for _ in range(10):
            sisa = (sisa << 1) ^ ((sisa >> 9) * 0x537)
        bit = ((data << 10) | sisa) ^ 0x5412
        n = self.ukuran

        def b(i: int) -> bool:
            return (bit >> i) & 1 == 1

        for i in range(6):
            self.set_fungsi(8, i, b(i))
        self.set_fungsi(8, 7, b(6))
        self.set_fungsi(8, 8, b(7))
        self.set_fungsi(7, 8, b(8))
        for i in range(9, 15):
            self.set_fungsi(14 - i, 8, b(i))
        for i in range(8):
            self.set_fungsi(n - 1 - i, 8, b(i))
        for i in range(8, 15):
            self.set_fungsi(8, n - 15 + i, b(i))
        self.set_fungsi(8, n - 8, True)

    def bit_versi(self) -> None:
        if self.versi < 7:
            return
        sisa = self.versi
        for _ in range(12):
            sisa = (sisa << 1) ^ ((sisa >> 11) * 0x1F25)
        bit = (self.versi << 12) | sisa
        for i in range(18):
            gelap = (bit >> i) & 1 == 1
            a, b = self.ukuran - 11 + i % 3, i // 3
            self.set_fungsi(a, b, gelap)
            self.set_fungsi(b, a, gelap)

    def isi_codeword(self, codeword: list[int]) -> None:
        n = self.ukuran
        i = 0
        kanan = n - 1
        while kanan >= 1:
            if kanan == 6:
                kanan = 5
            for vert in range(n):
                for j in range(2):
                    x = kanan - j
                    naik = ((kanan + 1) & 2) == 0
                    y = n - 1 - vert if naik else vert
                    if not self.fungsi[y][x] and i < len(codeword) * 8:
                        self.modul[y][x] = (codeword[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            kanan -= 2

    def terapkan_mask(self, mask: int) -> None:
        for y in range(self.ukuran):
            for x in range(self.ukuran):
                if not self.fungsi[y][x] and _mask(mask, x, y):
                    self.modul[y][x] = not self.modul[y][x]


def _mask(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask == 5:
        return x * y % 2 + x * y % 3 == 0
    if mask == 6:
        return (x * y % 2 + x * y % 3) % 2 == 0
    return ((x + y) % 2 + x * y % 3) % 2 == 0


_POLA_FINDER = ([1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1])


def _penalti(modul: list[list[bool]]) -> int:
    """Skor penalti ISO/IEC 18004 §7.8.3 (N1 runs, N2 blok, N3 pola finder, N4 proporsi)."""
    n = len(modul)
    baris = [[int(v) for v in r] for r in modul]
    kolom = [[baris[y][x] for y in range(n)] for x in range(n)]
    skor = 0
    for garis in baris + kolom:
        run, warna = 1, garis[0]
        for v in garis[1:]:
            if v == warna:
                run += 1
            else:
                skor += run - 2 if run >= 5 else 0
                run, warna = 1, v
        skor += run - 2 if run >= 5 else 0
        for i in range(n - 10):
            if garis[i:i + 11] in _POLA_FINDER:
                skor += 40
    for y in range(n - 1):
        for x in range(n - 1):
            if baris[y][x] == baris[y][x + 1] == baris[y + 1][x] == baris[y + 1][x + 1]:
                skor += 3
    gelap = sum(map(sum, baris))
    total = n * n
    skor += (abs(gelap * 20 - total * 10) + total - 1) // total * 10 - 10
    return skor


def matriks(teks: str, *, mask: int | None = None) -> list[list[bool]]:
    """Matriks modul (True = gelap), tanpa zona senyap. ``mask`` hanya untuk uji."""
    isi = teks.encode("utf-8")
    versi = _pilih_versi(len(isi))
    codeword = _dengan_ecc(_codeword_data(isi, versi), versi)
    terbaik = None
    for m in range(8) if mask is None else (mask,):
        mtx = _Matriks(versi)
        mtx.pola_fungsi()
        mtx.isi_codeword(codeword)
        mtx.terapkan_mask(m)
        mtx.bit_format(m)
        skor = _penalti(mtx.modul) if mask is None else 0
        if terbaik is None or skor < terbaik[0]:
            terbaik = (skor, mtx.modul)
    return terbaik[1]


def svg(teks: str, *, warna_gelap: str, warna_terang: str, label: str) -> str:
    """SVG inline (tanpa JS, tanpa sumber luar). Satu path untuk semua modul gelap."""
    modul = matriks(teks)
    n = len(modul) + 2 * ZONA_SENYAP
    jalur = "".join(
        f"M{x + ZONA_SENYAP} {y + ZONA_SENYAP}h1v1h-1z"
        for y, r in enumerate(modul) for x, gelap in enumerate(r) if gelap
    )
    return (
        f'<svg class="kode-qr" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
        f'role="img" aria-label="{escape(label, quote=True)}" shape-rendering="crispEdges">'
        f'<rect width="{n}" height="{n}" fill="{escape(warna_terang, quote=True)}"/>'
        f'<path d="{jalur}" fill="{escape(warna_gelap, quote=True)}"/></svg>'
    )
