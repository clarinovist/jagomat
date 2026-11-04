"""Snapshot isi laporan orang tua: hanya topik, tahap netral, dan satu kalimat langkah.

Allowlist yang sempit disengaja: skor, persentase, kode diagnosis, malrule, ID, level,
kelas sekolah, dan nama pola soal tidak pernah masuk. Kalimat tahap/langkah berasal dari
tabel tetap di sini, bukan dari teks rencana guru (yang membawa sidik kode diagnosis).
Fungsi ini hanya membaca; tidak menulis bukti belajar.
"""
from __future__ import annotations

VERSI = 1

# Harus sama dengan learning_cycle_ui._LABEL_TAHAP (dijaga test).
LABEL_TAHAP = ("Kenali cara anak", "Pelajari", "Latihan", "Cek setelah jeda", "Cek kembali", "Lanjut")
URAIAN = (
    "Guru sedang mengenali cara anak mengerjakan soal.",
    "Anak mempelajari caranya lewat contoh dan arahan guru.",
    "Anak berlatih mengerjakan soal, dengan bantuan yang makin berkurang.",
    "Setelah jeda, guru mengecek apakah caranya masih diingat.",
    "Guru mengecek kembali setelah beberapa minggu.",
    "Anak siap melanjutkan ke materi berikutnya.",
)
LANGKAH = (
    "Anak mengerjakan beberapa soal pendek, lalu guru memeriksa caranya bersama anak.",
    "Bahas satu contoh bersama, lalu anak mencoba dengan bantuan guru.",
    "Coba sendiri beberapa soal pendek di rumah, lalu hasilnya diperiksa guru.",
    "Beri jeda beberapa hari, lalu anak mengerjakan soal pendek tanpa bantuan.",
    "Anak mengerjakan soal pendek lagi; guru melihat apakah caranya tetap terpakai.",
    "Guru memilih materi berikutnya bersama anak.",
)
LANGKAH_TANPA_TAHAP = "Guru akan menentukan langkah berikutnya bersama anak."


def _topik(kon, siswa_id, mulai, akhir):
    """Nama topik dari sesi selesai dan terkonfirmasi dalam periode, urut kemunculan."""
    from reports import _nama_topik

    baris = kon.execute(
        """SELECT s.topik FROM sesi s
           WHERE s.siswa_id = ? AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL
             AND s.tanggal BETWEEN ? AND ?
             AND EXISTS (SELECT 1 FROM konfirmasi_hasil kh WHERE kh.sesi_id = s.id)
           ORDER BY s.tanggal, s.id""",
        (siswa_id, mulai, akhir),
    ).fetchall()
    hasil = []
    for (topik,) in baris:
        nama = _nama_topik(topik)
        if nama not in hasil:
            hasil.append(nama)
    return hasil


def _tahap(kon, siswa_id):
    import database
    import learning_cycle_ui as ui
    from learning_cycle import rencana_berikutnya

    bukti = database.muat_bukti_siklus(kon, siswa_id)
    rencana = rencana_berikutnya(bukti, siswa_id)
    indeks = ui._tahap_tampil(rencana, bukti)
    return None if indeks is None else indeks


def bangun(kon, siswa_id: int, mulai: str, akhir: str) -> dict:
    indeks = _tahap(kon, siswa_id)
    if indeks is None:
        tahap, langkah = None, LANGKAH_TANPA_TAHAP
    else:
        tahap = {"nomor": indeks + 1, "label": LABEL_TAHAP[indeks], "uraian": URAIAN[indeks]}
        langkah = LANGKAH[indeks]
    return {"versi": VERSI, "topik": _topik(kon, siswa_id, mulai, akhir), "tahap": tahap, "langkah": langkah}
