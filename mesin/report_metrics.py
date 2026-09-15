"""Statistik deskriptif latihan; bukan penentu pemahaman atau rekomendasi."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple


@dataclass(frozen=True)
class Hitungan:
    dikerjakan: int = 0
    benar: int = 0
    salah: int = 0
    perlu_ditinjau: int = 0
    belum_dikenalkan: int = 0
    dilewati: int = 0
    terkonfirmasi: int = 0

    @property
    def dinilai(self) -> int:
        return self.benar + self.salah

    @property
    def persen(self) -> Optional[float]:
        return 100 * self.benar / self.dinilai if self.dinilai else None


@dataclass(frozen=True)
class Materi:
    # Tipe, kelas, mode pengerjaan, tujuan sesi, representasi soal.
    kunci: Tuple[str, str, str, str, str]
    kini: Hitungan
    lalu: Hitungan

    @property
    def sebanding(self) -> bool:
        # Ambang keterbacaan tampilan, bukan uji signifikansi/penguasaan.
        return self.kini.dinilai >= 5 and self.lalu.dinilai >= 5


@dataclass(frozen=True)
class StatistikLaporan:
    mulai: date
    akhir: date
    kini: Hitungan
    lalu: Hitungan
    semua: Hitungan
    materi: Tuple[Materi, ...]
    tanpa_tanggal: int = 0

    @property
    def sebanding(self) -> Tuple[Materi, ...]:
        return tuple(m for m in self.materi if m.sebanding)


def hari_wib() -> date:
    """Satu batas hari untuk seluruh statistik laporan."""
    return datetime.now(timezone(timedelta(hours=7))).date()


def _tanggal(nilai) -> Optional[date]:
    try:
        return date.fromisoformat(str(nilai or "")[:10])
    except ValueError:
        return None


def _ada_kerja(baris) -> bool:
    """Pilihan cepat tanpa jawaban/coretan bukan pekerjaan yang teramati."""
    cara = (baris["cara"] or "").strip()
    if cara.startswith("[pilihan] "):
        cara = cara.partition(" — ")[2].strip()
    return bool((baris["jawaban"] or "").strip() or cara)


def _kategori(baris) -> Optional[str]:
    """T/N/kosong/dilewati tidak diam-diam berubah menjadi salah."""
    if baris["snapshot_id"] is not None:
        if baris["dilewati"]:
            return "dilewati"
        benar, kode = baris["benar_sah"], baris["kode_sah"]
    else:
        benar, kode = baris["benar"], baris["kode_final"]
    if kode == "T" or (baris["diagnosis_id"] is None and baris["belum_pernah"]):
        return "belum_dikenalkan"
    if not _ada_kerja(baris):
        return None
    if benar == 1 and kode is None:
        return "benar"
    if benar == 0 and kode in {"B", "K", "H", "E"}:
        return "salah"
    return "perlu_ditinjau"


def _hitung(baris) -> Hitungan:
    angka = defaultdict(int)
    for satu in baris:
        kategori = _kategori(satu)
        if kategori is None:
            continue
        angka[kategori] += 1
        # Aktivitas dan hasil adalah dua ukuran terpisah. Mengubah penilaian
        # H menjadi T/dilewati tidak menghapus pekerjaan yang sudah tercatat.
        if _ada_kerja(satu):
            angka["dikerjakan"] += 1
        if kategori in {"benar", "salah"} and satu["snapshot_id"] is not None:
            angka["terkonfirmasi"] += 1
    return Hitungan(**angka)


def statistik_laporan(kon, siswa_id: int, hari_ini: Optional[date] = None) -> StatistikLaporan:
    """Baca aktivitas unik per butir, termasuk sesi berjalan, tanpa menulis DB.

    Waktu aktivitas ialah pencatatan jawaban pertama, bukan tanggal pembuatan
    lembar. Koreksi mengubah statistik deskriptif tetapi tidak menambah aktivitas.
    Hanya satu konfirmasi aktif di-join; snapshot lama tidak menggandakan butir.
    """
    akhir = hari_ini or hari_wib()
    mulai = akhir - timedelta(days=6)
    mulai_lalu = mulai - timedelta(days=7)
    baris = kon.execute(
        """SELECT ss.id, so.template_id, se.level, se.mode, se.tujuan,
                  COALESCE(ss.mode_representasi, 'teks-v1') AS representasi,
                  j.jawaban, j.cara, j.belum_pernah,
                  COALESCE(j.dicatat, kh.dibuat) AS dicatat,
                  d.id AS diagnosis_id, d.benar, d.kode_final,
                  o.id AS snapshot_id, o.benar AS benar_sah,
                  o.kode_final AS kode_sah, o.dilewati
           FROM sesi se
           JOIN sesi_soal ss ON ss.sesi_id = se.id
           JOIN soal so ON so.id = ss.soal_id
           LEFT JOIN jawaban j ON j.sesi_soal_id = ss.id
           LEFT JOIN diagnosis d ON d.jawaban_id = j.id
           LEFT JOIN konfirmasi_hasil kh ON kh.id = (
               SELECT aktif.id FROM konfirmasi_hasil aktif
               WHERE aktif.sesi_id = se.id
                 AND se.dikonfirmasi_guru IS NOT NULL
                 AND aktif.fingerprint = se.fingerprint_konfirmasi
               ORDER BY aktif.nomor_urut DESC, aktif.id DESC LIMIT 1
           )
           LEFT JOIN snapshot_outcome o
             ON o.konfirmasi_id = kh.id AND o.sesi_soal_id = ss.id
           WHERE se.siswa_id = ? AND se.dibatalkan IS NULL
           ORDER BY ss.id""", (siswa_id,),
    ).fetchall()
    kini, lalu = [], []
    kelompok_kini, kelompok_lalu = defaultdict(list), defaultdict(list)
    tanpa_tanggal = 0
    for satu in baris:
        if _kategori(satu) is None:
            continue
        tanggal = _tanggal(satu["dicatat"])
        if tanggal is None:
            tanpa_tanggal += 1
            continue
        kunci = tuple(str(satu[n]) for n in (
            "template_id", "level", "mode", "tujuan", "representasi"
        ))
        if mulai <= tanggal <= akhir:
            kini.append(satu)
            kelompok_kini[kunci].append(satu)
        elif mulai_lalu <= tanggal < mulai:
            lalu.append(satu)
            kelompok_lalu[kunci].append(satu)
    materi = tuple(
        Materi(kunci, _hitung(kelompok_kini[kunci]), _hitung(kelompok_lalu[kunci]))
        for kunci in sorted(set(kelompok_kini) | set(kelompok_lalu))
    )
    return StatistikLaporan(
        mulai, akhir, _hitung(kini), _hitung(lalu), _hitung(baris), materi, tanpa_tanggal,
    )


def tugas_belum_selesai(kon, siswa_id: int):
    """Daftar tugas sekunder; tidak memilih atau memblokir rekomendasi reducer."""
    return kon.execute(
        """SELECT se.id, se.topik, se.level, se.tujuan, COUNT(ss.id) AS tersedia,
                  SUM(CASE WHEN TRIM(COALESCE(j.jawaban, '')) != ''
                            OR TRIM(COALESCE(j.cara, '')) != '' THEN 1 ELSE 0 END) AS terisi
           FROM sesi se
           JOIN sesi_soal ss ON ss.sesi_id = se.id
           LEFT JOIN jawaban j ON j.sesi_soal_id = ss.id
           WHERE se.siswa_id = ? AND se.selesai IS NULL AND se.dibatalkan IS NULL
           GROUP BY se.id ORDER BY se.id""", (siswa_id,),
    ).fetchall()
