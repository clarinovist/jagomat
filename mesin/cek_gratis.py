"""Cek kemampuan gratis per anak (funnel Fase 2): mulai, nilai, baca hasil, hapus.

Satu cek = satu sesi biasa (`tujuan='bebas'`, pilihan ganda, 15 soal, tanpa timer)
plus satu baris `cek_gratis` (UNIQUE per anak). Cek tidak mengubah `siswa.tingkat`
dan tidak menulis bukti siklus belajar. Hasil gratis hanya skor, kategori, dan
ringkasan nama topik; kunci, jawaban, dan data per soal tidak pernah keluar dari
modul ini. Sapuan retensi ada di `cek_gratis_sapu.py`.

Semua fungsi bekerja di koneksi pemanggil dan tidak commit sendiri (SAVEPOINT
lokal menjaga atomik; tanpa transaksi pemanggil, RELEASE menyimpannya). Waktu
disuntik (string ISO). Pesan galat tidak memuat nama anak, jawaban, atau skor.

Dua cek bisa dimiliki satu `id_akun` bila akun itu punya dua anak: `baca_hasil`
mengembalikan cek terbaru akun itu.
"""
from __future__ import annotations

import json
import random
import sqlite3

import choice_store
import database
import question_context
import topics
from cek_gratis_skor import (
    JUMLAH_SOAL, TOPIK_DASAR, TOPIK_GABUNGAN, VERSI_NOTICE, hitung_skor,
    kategori_dari_skor, level_untuk_kelas, periksa_id_akun, ringkas, waktu_baku,
    waktu_teks,
)

_SEED_MAKS = 9_999_999
_SAVEPOINT_MULAI = "cek_gratis_mulai"
_RINGKASAN_KOSONG = {"kuat": [], "perlu": []}


class CekTidakDitemukan(LookupError):
    """Anak bukan milik pemanggil (atau cek bukan miliknya); pesan sengaja tetap."""


class CekBelumTersedia(ValueError):
    """Cek belum tersedia untuk kelas anak ini; tidak ada yang ditulis."""


class CekPersetujuanDiperlukan(ValueError):
    """Persetujuan data belum diberikan secara eksplisit; tidak ada yang ditulis."""


def _baris_siswa(kon, siswa_id):
    return kon.execute(
        "SELECT id, id_akun, sesi_id FROM cek_gratis WHERE siswa_id = ?", (siswa_id,)
    ).fetchone()


def _hasil_mulai(baris, id_akun, *, baru: bool) -> dict:
    if baris["id_akun"] != id_akun:
        raise CekTidakDitemukan("Cek tidak ditemukan.")
    return {"sesi_id": baris["sesi_id"], "baru": baru}


def _kelas_siswa(kon, siswa_id):
    baris = kon.execute(
        "SELECT kelas_sekolah FROM profil_belajar WHERE siswa_id = ?", (siswa_id,)
    ).fetchone()
    return None if baris is None else baris["kelas_sekolah"]


def _periksa_tersedia(level: str, kelas: int) -> None:
    """Palang sebelum menulis apa pun: kelas 1-2 butuh materi dasar aktif."""
    if kelas <= 2:
        if not question_context.materi_dasar_aktif():
            raise CekBelumTersedia("Cek belum tersedia untuk kelas ini.")
        return
    try:
        question_context.validasi_pilihan(list(TOPIK_GABUNGAN), level)
    except ValueError:
        raise CekBelumTersedia("Cek belum tersedia untuk kelas ini.") from None


def _buat_sesi(kon, siswa_id: int, kelas: int, level: str, seed: int) -> int:
    choice_store.validasi_format("pilihan_ganda")
    if kelas <= 2:
        return database.buat_sesi(
            kon, siswa_id, seed, topik=TOPIK_DASAR, level=level, mode="drill",
            jumlah_soal=JUMLAH_SOAL, format_jawaban="pilihan_ganda",
        )
    return database.buat_sesi_gabungan(
        kon, siswa_id, seed=seed, topik_ids=list(TOPIK_GABUNGAN), level=level,
        mode="drill", jumlah_soal=JUMLAH_SOAL, format_jawaban="pilihan_ganda",
    )


def _periksa_sesi_baru(kon, sesi_id: int, level: str) -> None:
    """Post-kondisi: komposisi PG utuh; bila tidak, gagal (savepoint membatalkan)."""
    sesi = kon.execute(
        "SELECT level, tujuan, jenis, format_jawaban FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    jumlah = kon.execute(
        "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()[0]
    if (sesi is None or tuple(sesi) != (level, "bebas", "biasa", "pilihan_ganda")
            or jumlah != JUMLAH_SOAL):
        raise ValueError("Cek gagal disusun; coba lagi nanti.")


def _simpan_baris(kon, id_akun, siswa_id, sesi_id, waktu: str) -> None:
    kon.execute(
        """INSERT INTO cek_gratis(siswa_id, id_akun, sesi_id, setuju_pada,
                                  versi_notice, dibuat, jumlah_soal)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (siswa_id, id_akun, sesi_id, waktu, VERSI_NOTICE, waktu, JUMLAH_SOAL),
    )


def _susun_cek(kon, id_akun, siswa_id, kelas, level, seed, waktu) -> dict:
    kon.execute("SAVEPOINT " + _SAVEPOINT_MULAI)
    try:
        sesi_id = _buat_sesi(kon, siswa_id, kelas, level, seed)
        _periksa_sesi_baru(kon, sesi_id, level)
        _simpan_baris(kon, id_akun, siswa_id, sesi_id, waktu)
    except sqlite3.IntegrityError:
        kon.execute("ROLLBACK TO " + _SAVEPOINT_MULAI)
        kon.execute("RELEASE " + _SAVEPOINT_MULAI)
        ada = _baris_siswa(kon, siswa_id)
        if ada is None:
            raise
        return _hasil_mulai(ada, id_akun, baru=False)
    except Exception:
        kon.execute("ROLLBACK TO " + _SAVEPOINT_MULAI)
        kon.execute("RELEASE " + _SAVEPOINT_MULAI)
        raise
    kon.execute("RELEASE " + _SAVEPOINT_MULAI)
    return {"sesi_id": sesi_id, "baru": True}


def mulai(kon, id_akun, siswa_id, pemilik, setuju, sekarang, *, seed=None) -> dict:
    """Mulai cek gratis untuk satu anak; idempoten per anak.

    Urutan guard: `setuju is True` (tolak tanpa menulis), id_akun, kepemilikan
    anak (`CekTidakDitemukan` tanpa efek, sebelum apa pun soal keberadaan cek),
    baru cek yang sudah ada. Bila anak sudah punya cek, baris itu dikembalikan
    (`baru=False`) dan TIDAK ada sesi kedua. Kelas dibaca dari `profil_belajar`;
    kelas kosong/di luar 1-6 -> ValueError, kelas 1-2 tanpa materi dasar aktif ->
    `CekBelumTersedia`. Sesi dan baris cek dibuat dalam satu SAVEPOINT: gagal
    berarti tidak ada keduanya. Mengembalikan `{"sesi_id", "baru"}`.
    """
    if setuju is not True:
        raise CekPersetujuanDiperlukan("Persetujuan data diperlukan untuk memulai cek.")
    periksa_id_akun(id_akun)
    waktu = waktu_teks(sekarang)
    if type(siswa_id) is not int or type(pemilik) is not str or not pemilik:
        raise CekTidakDitemukan("Cek tidak ditemukan.")
    if not database.siswa_milik(kon, siswa_id, pemilik):
        raise CekTidakDitemukan("Cek tidak ditemukan.")
    ada = _baris_siswa(kon, siswa_id)
    if ada is not None:
        return _hasil_mulai(ada, id_akun, baru=False)
    kelas = _kelas_siswa(kon, siswa_id)
    level = level_untuk_kelas(kelas)
    _periksa_tersedia(level, kelas)
    seed_efektif = random.randint(1, _SEED_MAKS) if seed is None else seed
    return _susun_cek(kon, id_akun, siswa_id, kelas, level, seed_efektif, waktu)


def _peta_template_ke_topik() -> dict:
    """template_id -> topik_id hanya untuk topik yang dipakai cek (bukan seluruh PAKET)."""
    peta = {}
    for topik_id in TOPIK_GABUNGAN + (TOPIK_DASAR,):
        for template_id in topics.ambil(topik_id).templates:
            peta[template_id] = topik_id
    return peta


def _hitung_dari_sesi(kon, sesi_id: int, jumlah: int):
    """(benar, per_topik) dari jawaban sesi; tak dijawab atau benar NULL = salah."""
    from reports import diagnosa_murid

    diagnosa_murid(kon, sesi_id)
    baris = database.isi_sesi(kon, sesi_id)
    if len(baris) != jumlah:
        raise ValueError("Isi cek tidak lengkap.")
    peta = _peta_template_ke_topik()
    per_topik = {}
    benar_total = 0
    for b in baris:
        benar = 1 if b["benar"] else 0
        benar_total += benar
        topik_id = peta.get(b["template_id"])
        if topik_id is not None:
            sebelumnya = per_topik.get(topik_id, (0, 0))
            per_topik[topik_id] = (sebelumnya[0] + benar, sebelumnya[1] + 1)
    return benar_total, [(t, v[0], v[1]) for t, v in sorted(per_topik.items())]


_SQL_SIAP = """SELECT c.id, c.sesi_id, c.jumlah_soal, s.selesai
    FROM cek_gratis c JOIN sesi s ON s.id = c.sesi_id
    WHERE c.id_akun = ? AND c.skor IS NULL
      AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL
    ORDER BY c.id"""


def selesaikan_jika_siap(kon, id_akun, sekarang) -> bool:
    """Simpan skor/kategori/ringkasan untuk cek akun ini yang sesinya sudah selesai.

    Hanya sesi `selesai` (dan tidak dibatalkan) yang dinilai; sesi belum selesai
    tidak menghasilkan skor. Penilaian PG dipastikan lewat `reports.diagnosa_murid`
    (jalur yang sama dengan sisi guru). `selesai_pada` memakai waktu selesai sesi
    (bukan waktu penilaian) supaya retensi 30 hari dihitung dari anak selesai;
    `sekarang` hanya divalidasi. Idempoten: cek yang sudah punya skor dilewati.
    True bila ada skor baru tersimpan.
    """
    periksa_id_akun(id_akun)
    waktu_baku(sekarang)
    tersimpan = False
    for baris in kon.execute(_SQL_SIAP, (id_akun,)).fetchall():
        benar, per_topik = _hitung_dari_sesi(kon, baris["sesi_id"], baris["jumlah_soal"])
        skor = hitung_skor(benar, baris["jumlah_soal"])
        kon.execute(
            """UPDATE cek_gratis
               SET selesai_pada = ?, skor = ?, kategori = ?, ringkasan = ?
               WHERE id = ? AND skor IS NULL""",
            (waktu_teks(baris["selesai"]), skor, kategori_dari_skor(skor),
             json.dumps(ringkas(per_topik), ensure_ascii=False, sort_keys=True), baris["id"]),
        )
        tersimpan = True
    return tersimpan


def _urai_ringkasan(teks) -> dict:
    try:
        data = json.loads(teks)
    except (TypeError, ValueError):
        raise ValueError("Ringkasan cek tidak sah.") from None
    if (not isinstance(data, dict) or set(data) != {"kuat", "perlu"}
            or not all(isinstance(data[k], list) and all(type(i) is str for i in data[k])
                       for k in data)):
        raise ValueError("Ringkasan cek tidak sah.")
    return {"kuat": list(data["kuat"]), "perlu": list(data["perlu"])}


def _hasil_tanpa_skor(status: str, jumlah_soal: int) -> dict:
    return {"status": status, "skor": None, "kategori": None,
            "ringkasan": dict(_RINGKASAN_KOSONG), "jumlah_soal": jumlah_soal}


def _hasil_dari_baris(baris) -> dict:
    """Baris `cek_gratis` (atau None) menjadi dict hasil bertipe tetap."""
    if baris is None:
        return _hasil_tanpa_skor("belum_mulai", JUMLAH_SOAL)
    if baris["skor"] is None:
        return _hasil_tanpa_skor("belum_selesai", baris["jumlah_soal"])
    return {"status": "selesai", "skor": baris["skor"], "kategori": baris["kategori"],
            "ringkasan": _urai_ringkasan(baris["ringkasan"]),
            "jumlah_soal": baris["jumlah_soal"]}


def baca_hasil(kon, id_akun) -> dict:
    """Hasil cek terbaru MILIK akun ini (kunci `id_akun`, bukan id baris dari klien).

    Selalu dict dengan kunci tetap `status`, `skor`, `kategori`, `ringkasan`,
    `jumlah_soal`. Status `belum_mulai`/`belum_selesai` tidak memuat skor. Tidak
    pernah memuat kunci, jawaban, atau data per soal. Hanya membaca (tidak
    menilai); panggil `selesaikan_jika_siap` dulu bila perlu.
    """
    periksa_id_akun(id_akun)
    baris = kon.execute(
        """SELECT skor, kategori, ringkasan, jumlah_soal FROM cek_gratis
           WHERE id_akun = ? ORDER BY id DESC LIMIT 1""",
        (id_akun,),
    ).fetchone()
    return _hasil_dari_baris(baris)


def hasil_siswa(kon, id_akun, siswa_id) -> dict:
    """Hasil cek anak TERTENTU milik akun ini; kontrak sama dengan `baca_hasil`.

    Kunci baris = `id_akun` DAN `siswa_id` (keduanya dari sisi server): cek anak
    lain, atau cek akun lain untuk anak yang sama, tidak pernah terbaca. Dipakai
    jalur uang, yang tidak boleh memakai "cek terbaru akun" (anak yang salah).
    `siswa_id` bukan int positif -> `belum_mulai`. Hanya membaca.
    """
    periksa_id_akun(id_akun)
    if type(siswa_id) is not int or siswa_id < 1:
        return _hasil_tanpa_skor("belum_mulai", JUMLAH_SOAL)
    baris = kon.execute(
        """SELECT skor, kategori, ringkasan, jumlah_soal FROM cek_gratis
           WHERE id_akun = ? AND siswa_id = ?""",
        (id_akun, siswa_id),
    ).fetchone()
    return _hasil_dari_baris(baris)


def hapus_cek_keluarga(kon, id_akun, siswa_ids) -> int:
    """Hapus baris cek milik akun ini dan/atau anak-anak keluarga itu (hook hapus keluarga).

    Hanya baris cek; sesi dihapus oleh penghapusan keluarga sendiri. Mengembalikan
    jumlah baris terhapus. Di transaksi pemanggil, tanpa commit.
    """
    periksa_id_akun(id_akun)
    if not all(type(i) is int for i in siswa_ids):
        raise ValueError("siswa_ids harus bilangan bulat")
    jumlah = kon.execute("DELETE FROM cek_gratis WHERE id_akun = ?", (id_akun,)).rowcount
    for siswa_id in siswa_ids:
        jumlah += kon.execute("DELETE FROM cek_gratis WHERE siswa_id = ?", (siswa_id,)).rowcount
    return jumlah


from cek_gratis_sapu import sapu_cek_gratis  # noqa: E402,F401  (re-ekspor)
