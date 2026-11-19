"""Konstanta dan fungsi murni cek kemampuan gratis: skor, kategori, ringkasan awal.

Tanpa akses basis data dan tanpa LLM. Skor dihitung di sini, bukan lewat
`parent_report_snapshot`: daftar putih "tanpa skor/persentase" untuk laporan
orang tua tetap utuh (pengecualian bercakupan sempit, plan funnel Fase 2 §2.2).

Ringkasan hanya memuat NAMA topik (tanpa angka per topik): hasil gratis tidak
boleh membocorkan rincian bagian berbayar (plan §2.11).
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction

from auth import id_akun_sah

FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
JUMLAH_SOAL = 15
TOPIK_GABUNGAN = ("pola-bilangan", "statistika", "geometri-datar")
TOPIK_DASAR = "bilangan-dasar"
VERSI_NOTICE = "v1"
RETENSI_SELESAI_HARI = 30
RETENSI_BELUM_SELESAI_HARI = 7

AMBANG_SANGAT_BAIK = 85
AMBANG_CUKUP_BAIK = 65
AMBANG_PERLU_PENGUATAN = 40
KATEGORI = ("Sangat baik", "Cukup baik", "Perlu penguatan", "Perlu pendampingan")

MIN_SOAL_PER_TOPIK = 3
AMBANG_KUAT = Fraction(8, 10)
AMBANG_PERLU = Fraction(1, 2)
MAKS_BUTIR_RINGKASAN = 2


def _bilangan_bulat(nilai) -> bool:
    return type(nilai) is int


def hitung_skor(jawaban_benar: int, jumlah: int) -> int:
    """Persentase benar, dibulatkan setengah ke atas (bukan pembulatan bankir)."""
    if not (_bilangan_bulat(jawaban_benar) and _bilangan_bulat(jumlah)):
        raise ValueError("jumlah benar dan jumlah soal harus bilangan bulat")
    if jumlah < 1 or not 0 <= jawaban_benar <= jumlah:
        raise ValueError("jumlah benar harus 0..jumlah soal dan jumlah soal minimal 1")
    return (jawaban_benar * 200 + jumlah) // (2 * jumlah)


def jumlah_benar(skor: int, jumlah: int):
    """Kebalikan `hitung_skor`: jumlah benar yang menghasilkan `skor`, atau None.

    Dipakai halaman hasil orang tua ("X dari N soal benar") tanpa membaca data
    per soal. None bila tidak ada jumlah benar yang cocok atau tidak tunggal
    (jumlah soal sangat besar), sehingga halaman cukup menghilangkan barisnya.
    """
    if not (_bilangan_bulat(skor) and _bilangan_bulat(jumlah)) or jumlah < 1:
        return None
    cocok = [b for b in range(jumlah + 1) if hitung_skor(b, jumlah) == skor]
    return cocok[0] if len(cocok) == 1 else None


def kategori_dari_skor(skor: int) -> str:
    """Empat label kategori; batas bawah tiap label termasuk labelnya."""
    if not _bilangan_bulat(skor) or not 0 <= skor <= 100:
        raise ValueError("skor harus bilangan bulat 0..100")
    if skor >= AMBANG_SANGAT_BAIK:
        return KATEGORI[0]
    if skor >= AMBANG_CUKUP_BAIK:
        return KATEGORI[1]
    if skor >= AMBANG_PERLU_PENGUATAN:
        return KATEGORI[2]
    return KATEGORI[3]


def _periksa_per_topik(per_topik) -> tuple:
    hasil = []
    for butir in per_topik:
        try:
            topik_id, benar, total = butir
        except (TypeError, ValueError):
            raise ValueError("butir per topik harus (topik_id, benar, total)") from None
        if type(topik_id) is not str or not topik_id:
            raise ValueError("topik_id harus string tidak kosong")
        if not (_bilangan_bulat(benar) and _bilangan_bulat(total)) or total < 1 or not 0 <= benar <= total:
            raise ValueError("benar dan total per topik tidak sah")
        hasil.append((topik_id, Fraction(benar, total), total))
    return tuple(hasil)


def _nama_topik(topik_id: str) -> str:
    import topics

    try:
        return topics.ambil(topik_id).nama
    except KeyError:
        raise ValueError("topik tidak dikenal") from None


def ringkas(per_topik) -> dict:
    """Ringkasan awal terstruktur dari daftar `(topik_id, benar, total)`.

    Hanya topik dengan minimal `MIN_SOAL_PER_TOPIK` soal. Rasio >= `AMBANG_KUAT`
    masuk `kuat`; rasio <= `AMBANG_PERLU` masuk `perlu`; keduanya maksimal
    `MAKS_BUTIR_RINGKASAN` butir, urut rasio lalu id topik (deterministik).
    Mengembalikan dict baru `{"kuat": [nama], "perlu": [nama]}`.
    """
    layak = [b for b in _periksa_per_topik(per_topik) if b[2] >= MIN_SOAL_PER_TOPIK]
    kuat = sorted((b for b in layak if b[1] >= AMBANG_KUAT), key=lambda b: (-b[1], b[0]))
    perlu = sorted((b for b in layak if b[1] <= AMBANG_PERLU), key=lambda b: (b[1], b[0]))
    return {
        "kuat": [_nama_topik(b[0]) for b in kuat[:MAKS_BUTIR_RINGKASAN]],
        "perlu": [_nama_topik(b[0]) for b in perlu[:MAKS_BUTIR_RINGKASAN]],
    }


def level_untuk_kelas(kelas) -> str:
    """Kelas sekolah 1..6 menjadi level soal `P{kelas}`; selain itu ValueError."""
    if kelas is None:
        raise ValueError("Kelas anak belum diisi; isi kelas dulu sebelum memulai cek.")
    if not _bilangan_bulat(kelas) or not 1 <= kelas <= 6:
        raise ValueError("Cek gratis hanya tersedia untuk kelas 1 sampai 6.")
    return "P%d" % kelas


def periksa_id_akun(id_akun) -> None:
    if not id_akun_sah(id_akun):
        raise ValueError("id_akun tidak sah")


def waktu_baku(waktu) -> datetime:
    """Waktu ISO (string) menjadi datetime naif UTC; selain itu ValueError."""
    if type(waktu) is not str:
        raise ValueError("waktu harus string ISO")
    try:
        hasil = datetime.fromisoformat(waktu)
    except ValueError:
        raise ValueError("waktu bukan format ISO") from None
    if hasil.tzinfo is not None:
        hasil = hasil.astimezone(timezone.utc).replace(tzinfo=None)
    return hasil


def waktu_teks(waktu) -> str:
    """Waktu ISO menjadi teks baku `FORMAT_WAKTU` (urutan teks = urutan waktu)."""
    return waktu_baku(waktu).strftime(FORMAT_WAKTU)


BATAS_KUAT_PERSEN = 80
LABEL_KUAT = "Kuat"
LABEL_PERLU_DIPERKUAT = "Perlu diperkuat"
LABEL_BELUM_CUKUP = "Belum cukup soal"


def label_materi(benar: int, total: int) -> str:
    """Label per materi untuk laporan Peta Kemampuan (Keputusan 19, poin 13).

    Kurang dari `MIN_SOAL_PER_TOPIK` soal: "Belum cukup soal". Selain itu
    persen yang DITAMPILKAN (`hitung_skor`, setengah ke atas) >= `BATAS_KUAT_PERSEN`
    -> "Kuat", di bawahnya "Perlu diperkuat". Memakai persen tampilan agar label
    tidak bertentangan dengan angka di layar (mis. 35/44 tampil 80% dan Kuat).
    """
    persen = hitung_skor(benar, total)
    if total < MIN_SOAL_PER_TOPIK:
        return LABEL_BELUM_CUKUP
    return LABEL_KUAT if persen >= BATAS_KUAT_PERSEN else LABEL_PERLU_DIPERKUAT
