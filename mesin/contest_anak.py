"""Ringkasan Latihan Lomba untuk sisi anak: sesi berjalan, riwayat, nilai terbaik, target harian, banding.

Menggabungkan `contest_store` (sesi berjalan, jawaban terisi) dan `contest_results.riwayat_sesi` (nilai sesi
selesai) menjadi data siap tampil untuk halaman awal, hasil, dan kartu beranda. Semua dibatasi ke satu
`siswa_id`. Sesi "asal kumpul" (`contest_paket.asal_kumpul`) tetap tampil di riwayat, tetapi tidak ikut nilai
terbaik, nilai terakhir, banding "naik/turun", maupun hitungan target harian.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import AbstractSet, FrozenSet, Optional, Sequence, Tuple

import contest_assignment_store as AS
import contest_paket as PK
import contest_results as R
import contest_store as K

BATAS_RIWAYAT_TAMPIL = 5


@dataclass(frozen=True)
class RingkasAnak:
    paket: PK.PaketLomba
    berjalan: Optional[K.SesiRingkas]
    sisa_detik: int
    terisi: FrozenSet[int]               # nomor terisi pada sesi berjalan (kosong bila tak ada sesi)
    nomor_lanjut: int                    # soal kosong pertama (atau 1 bila semua terisi / tanpa sesi)
    riwayat: Tuple[R.RingkasSesi, ...]   # sesi selesai terbaru dulu, termasuk asal kumpul
    nilai_terbaik: Optional[int]
    nilai_terakhir: Optional[int]
    selesai_hari_ini: int
    hitung_mundur: str
    sekarang: int


def nomor_kosong_pertama(terisi: AbstractSet[int]) -> int:
    """Soal kosong dengan nomor terkecil; 1 bila semua terisi."""
    return next((n for n in range(K.NOMOR_PERTAMA, K.NOMOR_TERAKHIR + 1) if n not in terisi), K.NOMOR_PERTAMA)


def nomor_kosong_berikutnya(terisi: AbstractSet[int], nomor: int) -> Optional[int]:
    """Soal kosong berikutnya setelah `nomor` secara siklis (n+1..akhir lalu awal..n-1); None bila tak ada."""
    total = K.NOMOR_TERAKHIR
    for langkah in range(1, total):
        calon = (nomor - 1 + langkah) % total + 1
        if calon not in terisi:
            return calon
    return None


def _saring_sah(kon, siswa_id: int, semua: Sequence[R.RingkasSesi]) -> Tuple[R.RingkasSesi, ...]:
    """Sesi sah (bukan asal kumpul); penanda dihitung `contest_results` dengan aturan `contest_paket`."""
    return tuple(s for s in semua if not s.asal_kumpul)


def sesi_sah(kon, siswa_id: int, sekarang: int) -> Tuple[R.RingkasSesi, ...]:
    """Sesi selesai yang bukan asal kumpul, dari yang terlama."""
    return _saring_sah(kon, siswa_id, R.riwayat_sesi(kon, siswa_id, sekarang))


def _selesai_hari_ini(sah: Sequence[R.RingkasSesi], sekarang: int) -> int:
    awal = PK.awal_hari_wib(sekarang)
    return sum(1 for s in sah if s.mulai_epoch >= awal)


def paket_untuk_anak(kon, siswa_id: int, paket: PK.PaketLomba) -> PK.PaketLomba:
    """Paket dengan target harian dan hitung mundur dari penugasan Guru bila diisi (None = ikut paket).

    Salinan baru lewat `dataclasses.replace` (paket tidak dimutasi); tanpa nilai khusus mengembalikan `paket` itu.
    """
    penugasan = AS.ambil(kon, siswa_id)
    if penugasan is None:
        return paket
    ubah = {}
    if penugasan.target_harian is not None:
        ubah["target_harian"] = penugasan.target_harian
    if penugasan.tampil_hitung_mundur is not None:
        ubah["tampil_hitung_mundur"] = penugasan.tampil_hitung_mundur
    return dataclasses.replace(paket, **ubah) if ubah else paket


def muat_ringkas(kon, siswa_id: int, sekarang: int, paket: PK.PaketLomba = PK.PAKET_AKTIF) -> RingkasAnak:
    """Data awal anak; menutup sesi yang batasnya lewat (lewat `sesi_berjalan`) sebelum membaca riwayat."""
    paket = paket_untuk_anak(kon, siswa_id, paket)
    berjalan = K.sesi_berjalan(kon, siswa_id, sekarang)
    terisi = K.nomor_terjawab(kon, siswa_id, berjalan.id) if berjalan else frozenset()
    semua = R.riwayat_sesi(kon, siswa_id, sekarang)
    sah = _saring_sah(kon, siswa_id, semua)
    return RingkasAnak(
        paket=paket, berjalan=berjalan, sisa_detik=berjalan.sisa_detik(sekarang) if berjalan else 0,
        terisi=terisi, nomor_lanjut=nomor_kosong_pertama(terisi),
        riwayat=tuple(reversed(semua[-BATAS_RIWAYAT_TAMPIL:])),
        nilai_terbaik=max((s.nilai for s in sah), default=None),
        nilai_terakhir=sah[-1].nilai if sah else None,
        selesai_hari_ini=_selesai_hari_ini(sah, sekarang),
        hitung_mundur=PK.teks_hitung_mundur(paket, sekarang), sekarang=sekarang)


def nilai_sebelumnya(kon, siswa_id: int, sesi_id: int, sekarang: int) -> Optional[int]:
    """Nilai sesi sah SEBELUMNYA untuk dibandingkan; None bila sesi ini asal kumpul atau tak ada pendahulu."""
    sah = sesi_sah(kon, siswa_id, sekarang)
    if not any(s.sesi_id == sesi_id for s in sah):
        return None
    sebelum = [s for s in sah if s.sesi_id < sesi_id]
    return sebelum[-1].nilai if sebelum else None


def kalimat_banding(nilai: int, sebelumnya: Optional[int]) -> str:
    """"Naik 2 dari latihan sebelumnya" dst.; kosong bila tak ada pembanding."""
    if sebelumnya is None:
        return ""
    selisih = nilai - sebelumnya
    if selisih > 0:
        return f"Naik {selisih} dari latihan sebelumnya"
    if selisih < 0:
        return f"Turun {-selisih} dari latihan sebelumnya"
    return "Sama dengan latihan sebelumnya"

