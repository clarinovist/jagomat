"""Proyeksi isi laporan guru -> orang tua dari bukti terkonfirmasi.

Semua yang boleh dilihat orang tua melewati **allowlist** eksplisit di modul
ini: ``versi``, ``topik``, ``tahap`` (nomor + label netral), ``langkah``, dan
``catatan`` (kolom terpisah). Kunci lain yang entah bagaimana masuk ke JSON
tidak pernah dibaca, jadi tidak bisa bocor lewat perubahan renderer.

Batas yang dijaga:

- Topik hanya dari sesi **selesai + terkonfirmasi guru** di dalam periode.
  Sesi yang belum ditinjau tidak muncul (keputusan pemilik).
- Tahap memakai peta enam pita yang sama dengan permukaan guru
  (``learning_cycle_ui.tahap_netral``); tidak ada skor, persentase, kode
  B/K/H/E/T/N, malrule, atau status per fokus.
- Kalimat langkah berikutnya berasal dari tabel pra-tulis bahasa awam, bukan
  ``judul_tindakan``/instruksi intervensi.
- Modul ini tidak menulis bukti/sesi; hanya membaca proyeksi dan dipakai
  service laporan untuk menyusun snapshot.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

VERSI = 1
BATAS_TOPIK = 40
BATAS_PANJANG_TOPIK = 120
BATAS_PANJANG_LANGKAH = 400

# Langkah berikutnya dalam bahasa awam, satu kalimat per tahap 1-6.
# Ditulis tetap (bukan disusun dari istilah internal) agar guru tidak perlu
# menulis ulang dan orang tua tidak pernah melihat kosakata diagnosis.
_LANGKAH = (
    "Dampingi anak mencoba beberapa soal pendek dengan caranya sendiri, "
    "lalu serahkan hasilnya kepada guru untuk diperiksa.",
    "Kerjakan satu contoh bersama, lalu minta anak menjelaskan langkahnya "
    "dengan kata-katanya sendiri.",
    "Biarkan anak mencoba soal sendiri; bantu hanya ketika ia benar-benar "
    "berhenti, tanpa menunjukkan jawabannya.",
    "Beri jeda beberapa hari, lalu minta anak mengerjakan soal serupa tanpa "
    "melihat contoh lama.",
    "Minta anak menjelaskan caranya dari awal sampai akhir, tanpa membuka "
    "catatan atau contoh sebelumnya.",
    "Pilih latihan campuran yang ringan agar materi yang sudah dipelajari "
    "tetap terpakai.",
)
LANGKAH_TANPA_TAHAP = (
    "Tunggu arahan guru sebelum memulai langkah berikutnya."
)


def nama_guru(pengguna: str) -> str:
    """Nama tampilan guru untuk snapshot laporan (login kanonik tetap di sesi).

    Memakai formatter yang sama dengan topbar guru supaya orang tua melihat
    nama yang konsisten; nilai ini dibekukan saat terbit.
    """
    nama = (pengguna or "").strip()
    if not nama:
        return ""
    from child_header import nama_akun

    return nama_akun(nama)


def nama_topik(topik_id: str) -> str:
    """Nama ramah topik; id warisan yang tak dikenal tampil apa adanya."""
    if not isinstance(topik_id, str) or not topik_id:
        return ""
    if topik_id.startswith("gabungan:"):
        jumlah = len([t for t in topik_id.split(":", 1)[1].split(",") if t])
        return f"Gabungan {jumlah} topik"
    from topics import ambil

    try:
        return ambil(topik_id).nama
    except KeyError:
        return topik_id


def topik_periode(
    kon: sqlite3.Connection, siswa_id: int, mulai: date, akhir: date
) -> tuple[str, ...]:
    """Topik dari sesi selesai + terkonfirmasi guru, urut abjad, tanpa duplikat."""
    baris = kon.execute(
        """SELECT DISTINCT s.topik
           FROM sesi s
           WHERE s.siswa_id = ?
             AND s.tanggal BETWEEN ? AND ?
             AND s.selesai IS NOT NULL
             AND s.dikonfirmasi_guru IS NOT NULL
             AND s.dibatalkan IS NULL
           ORDER BY s.topik""",
        (siswa_id, mulai.isoformat(), akhir.isoformat()),
    ).fetchall()
    hasil: list[str] = []
    for item in baris:
        nama = nama_topik(item["topik"])
        if nama and nama not in hasil:
            hasil.append(nama)
    return tuple(hasil)


def tahap_sekarang(kon: sqlite3.Connection, siswa_id: int) -> dict | None:
    """Posisi perjalanan (1-6 + label netral) dari reducer yang sama dengan guru."""
    import database
    import learning_cycle_ui
    import learning_journey

    bukti = database.muat_bukti_siklus(kon, siswa_id)
    perjalanan = learning_journey.perjalanan_belajar(bukti, siswa_id)
    netral = learning_cycle_ui.tahap_netral(perjalanan.rekomendasi, bukti)
    if netral is None:
        return None
    nomor, label = netral
    return {"nomor": nomor, "label": label}


def proyeksi(
    kon: sqlite3.Connection, siswa_id: int, mulai: date, akhir: date
) -> dict:
    """Snapshot presentasi yang dibekukan saat laporan diterbitkan."""
    topik = topik_periode(kon, siswa_id, mulai, akhir)
    tahap = tahap_sekarang(kon, siswa_id)
    langkah = (
        _LANGKAH[tahap["nomor"] - 1] if tahap is not None
        else LANGKAH_TANPA_TAHAP
    )
    return {
        "versi": VERSI,
        "topik": list(topik),
        "tahap": tahap,
        "langkah": langkah,
    }


def serialisasi(isi: dict) -> str:
    """JSON ringkas dan deterministik untuk kolom snapshot."""
    return json.dumps(isi, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def isi_tampil(payload) -> dict:
    """Allowlist baca: kunci di luar daftar tidak pernah dibaca.

    Dipakai renderer (dan rute) sebagai pertahanan terakhir: payload yang
    ditambahi ``skor``/``kunci``/``sesi_ids`` menghasilkan output identik.
    """
    if not isinstance(payload, dict):
        return {"topik": (), "tahap": None, "langkah": ""}
    mentah_topik = payload.get("topik")
    topik: tuple[str, ...] = ()
    if isinstance(mentah_topik, (list, tuple)):
        topik = tuple(
            x[:BATAS_PANJANG_TOPIK] for x in mentah_topik
            if isinstance(x, str) and x
        )[:BATAS_TOPIK]
    tahap = None
    mentah_tahap = payload.get("tahap")
    if isinstance(mentah_tahap, dict):
        nomor = mentah_tahap.get("nomor")
        label = mentah_tahap.get("label")
        if type(nomor) is int and 1 <= nomor <= 6 and isinstance(label, str) and label:
            tahap = {"nomor": nomor, "label": label[:80]}
    langkah = payload.get("langkah")
    if not isinstance(langkah, str):
        langkah = ""
    return {
        "topik": topik,
        "tahap": tahap,
        "langkah": langkah[:BATAS_PANJANG_LANGKAH],
    }


def muat_isi(teks) -> dict:
    """Baca snapshot JSON tanpa mempercayai bentuknya."""
    if not isinstance(teks, str) or not teks:
        return isi_tampil(None)
    try:
        data = json.loads(teks)
    except (TypeError, ValueError):
        return isi_tampil(None)
    return isi_tampil(data)


def kejadian_terakhir(kon: sqlite3.Connection, siswa_id: int) -> int:
    """Watermark bukti saat laporan disusun/diterbitkan."""
    return int(kon.execute(
        "SELECT COALESCE(MAX(id), 0) FROM kejadian_belajar WHERE siswa_id = ?",
        (siswa_id,),
    ).fetchone()[0])


def perubahan_bukti(
    kon: sqlite3.Connection, siswa_id: int, watermark: int
) -> tuple[bool, int]:
    """(ada perubahan, jumlah kejadian baru) sesudah watermark laporan."""
    jumlah = int(kon.execute(
        """SELECT COUNT(*) FROM kejadian_belajar
           WHERE siswa_id = ? AND id > ?""",
        (siswa_id, int(watermark)),
    ).fetchone()[0])
    return jumlah > 0, jumlah


def periode_dari_form(data, hari_ini: date | None = None) -> tuple[date, date]:
    """Preset periode form guru; input tak sah ditolak sebelum tulis."""
    hari = hari_ini or _hari_ini()
    pilihan = data.get("periode", "30") if hasattr(data, "get") else "30"
    if pilihan == "30":
        return hari - timedelta(days=29), hari
    if pilihan == "bulan":
        return hari.replace(day=1), hari
    if pilihan != "custom":
        raise ValueError("periode tidak dikenal")
    try:
        mulai = date.fromisoformat(str(data.get("mulai", "")))
        akhir = date.fromisoformat(str(data.get("sampai", "")))
    except ValueError:
        raise ValueError("tanggal periode tidak sah") from None
    if mulai > akhir:
        raise ValueError("tanggal awal melewati tanggal akhir")
    if (akhir - mulai).days > 366:
        raise ValueError("rentang periode terlalu panjang")
    if akhir > hari:
        raise ValueError("tanggal akhir melewati hari ini")
    return mulai, akhir


def _hari_ini() -> date:
    import domain_clock

    return domain_clock.hari_wib()
