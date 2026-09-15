"""Akses basis data — simpan bank soal, sesi, jawaban, diagnosis.

Sengaja sqlite3 polos tanpa ORM: skemanya kecil, kuerinya sedikit, dan
ketergantungan tambahan hanya menambah hal yang bisa rusak saat deploy.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Optional

from generator import LEVEL_BAWAAN, buat_lembar
import outcome_presentations
import question_views
from schema import MIGRASI, SKEMA, VIEW_USANG
from templates import Soal
from topics import TOPIK_BAWAAN
from visual_contract import serialisasi_penyajian

# Lokasi basis data bisa disetel lewat lingkungan, seperti berkas sandi.
#
# Diperlukan karena di dalam container /app dimiliki root dan hanya bisa
# dibaca: basis data harus tinggal di volume (/data) agar bisa ditulis DAN
# selamat saat container diganti. Tanpa ini container gagal start dengan
# "unable to open database file" — kegagalan yang hanya muncul saat deploy,
# tidak pernah saat dijalankan lokal.
BAWAAN = Path(
    os.environ.get("OSN_BERKAS_DB", Path(__file__).resolve().parent / "latihan.db")
)


@contextmanager
def buka(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Koneksi dengan foreign key aktif dan transaksi otomatis.

    Default dibaca DI BADAN fungsi, bukan sebagai nilai argumen bawaan:
    nilai argumen terikat saat definisi, sehingga test yang mengganti
    BAWAAN lewat monkeypatch tidak akan berpengaruh pada pemanggilan
    buka() tanpa argumen dari kode halaman.
    """
    if path is None:
        path = BAWAAN
    kon = sqlite3.connect(str(path))
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys = ON")
    outcome_presentations.daftarkan_validasi(kon)
    try:
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _segarkan_trigger_snapshot(kon: sqlite3.Connection) -> None:
    """Ganti hanya trigger Fase 1 lama; startup ulang tetap idempoten."""
    nama = "sesi_soal_snapshot_tolak_update_terkunci"
    baris = kon.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        (nama,),
    ).fetchone()
    if baris is None:
        return
    sql = " ".join(baris[0].split())
    palang = ("sesi_id, soal_id, nomor", "se.dibatalkan IS NOT NULL", "lain.sesi_id IN", "kh.sesi_id IN", "bf.sesi_id IN")
    if not all(marker in sql for marker in palang):
        kon.execute(f"DROP TRIGGER {nama}")


def _jalankan_skema(kon: sqlite3.Connection, skrip: str) -> None:
    """Jalankan SQL utuh tanpa implicit COMMIT dari executescript."""
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip() and not all(
        b.strip().startswith("--") or not b.strip() for b in bagian.splitlines()
    ):
        raise sqlite3.OperationalError("skrip skema tidak lengkap")


def siapkan(path: Path | str = BAWAAN) -> None:
    """Buat/segarkan skema. Aman dijalankan berulang.

    Urutannya penting: view usang dibuang DULU, lalu kolom baru ditambahkan,
    baru SKEMA dijalankan untuk membangun ulang view dengan definisi terkini.
    Kalau view dibangun sebelum kolomnya ada, SQLite menerimanya (view tidak
    divalidasi saat dibuat) lalu gagal saat pertama kali dibaca — kegagalan
    yang muncul di halaman laporan, jauh dari penyebabnya.
    """
    with buka(path) as kon:
        kon.execute("PRAGMA foreign_keys = OFF")
        kon.execute("BEGIN IMMEDIATE")
        for nama in VIEW_USANG:
            kon.execute(f"DROP VIEW IF EXISTS {nama}")
        migrasi(kon)
        rebuild_siswa_unik(kon)
        _segarkan_trigger_snapshot(kon)
        _jalankan_skema(kon, SKEMA)
        # Migrasi bentuk parameter (A4): pola string per-template → list
        # JSON murni. Idempoten dan terverifikasi per baris (kunci lama
        # wajib cocok) — jalannya di setiap siapkan() aman dan murah.
        import migrate_params

        migrate_params.jalankan(kon)
        outcome_presentations.lengkapi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("migrasi meninggalkan foreign key tidak valid")


def migrasi(kon: sqlite3.Connection) -> list[str]:
    """Tambahkan kolom yang belum ada. Mengembalikan yang benar-benar dijalankan.

    SQLite tidak punya "ADD COLUMN IF NOT EXISTS", jadi kolomnya diperiksa
    lewat PRAGMA table_info. Tabel yang belum ada dilewati — SKEMA akan
    membuatnya lengkap sesaat kemudian.
    """
    dijalankan: list[str] = []
    for tabel, kolom, pernyataan in MIGRASI:
        ada_tabel = kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabel,)
        ).fetchone()
        if not ada_tabel:
            continue
        kolom_ada = {
            r["name"] for r in kon.execute(f"PRAGMA table_info({tabel})").fetchall()
        }
        if kolom in kolom_ada:
            continue
        kon.execute(pernyataan)
        dijalankan.append(f"{tabel}.{kolom}")
    return dijalankan


def rebuild_siswa_unik(kon: sqlite3.Connection) -> bool:
    """Ganti UNIQUE(nama) global jadi UNIQUE(nama, pemilik) lewat rebuild tabel.

    Kendala tabel tidak bisa di-ALTER di SQLite — satu-satunya jalan adalah
    buat tabel baru, salin, drop, rename. Deteksinya lewat indeks unik yang
    menyusun satu kolom `nama` saja (tabel lama memilikinya sebagai
    sqlite_autoindex; tabel baru mengunci (nama, pemilik) sekaligus), jadi
    aman dijalankan berulang.

    foreign_keys dimatikan sementara: DROP tabel induk dilarang selama
    penjaga hidup. Seluruh langkahnya satu transaksi eksplisit — kalau
    foreign_key_check menemukan sisa, semuanya digulung balik, bukan
    dibiarkan setengah jadi.
    """
    ada = kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'siswa'"
    ).fetchone()
    if not ada:
        return False

    unik_nama_saja = False
    for idx in kon.execute("PRAGMA index_list(siswa)").fetchall():
        if not idx["unique"]:
            continue
        kolom = [
            r["name"]
            for r in kon.execute(f"PRAGMA index_info({idx['name']})").fetchall()
        ]
        if kolom == ["nama"]:
            unik_nama_saja = True
    if not unik_nama_saja:
        return False

    mandiri = not kon.in_transaction
    if mandiri:
        kon.execute("PRAGMA foreign_keys = OFF")
        kon.execute("BEGIN IMMEDIATE")
    elif kon.execute("PRAGMA foreign_keys").fetchone()[0]:
        raise sqlite3.IntegrityError("rebuild membutuhkan transaksi migrasi dengan FK nonaktif")
    try:
        _jalankan_skema(kon,
            """
            CREATE TABLE siswa_baru (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nama        TEXT    NOT NULL,
                tingkat     TEXT    NOT NULL DEFAULT 'P3',
                pemilik     TEXT    NOT NULL DEFAULT '',
                dibuat      TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
                UNIQUE (nama, pemilik)
            );
            INSERT INTO siswa_baru (id, nama, tingkat, pemilik, dibuat)
                SELECT id, nama, tingkat, pemilik, dibuat FROM siswa;
            DROP TABLE siswa;
            ALTER TABLE siswa_baru RENAME TO siswa;
            """
        )
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("rebuild siswa meninggalkan FK rusak")
        if mandiri:
            kon.commit()
    except Exception:
        if mandiri:
            kon.rollback()
        raise
    finally:
        if mandiri:
            kon.execute("PRAGMA foreign_keys = ON")
    return True


# ── Siswa ───────────────────────────────────────────────────────────────


def tambah_siswa(
    kon: sqlite3.Connection, nama: str, tingkat: str = "P3", pemilik: str = ""
) -> int:
    """Tambahkan anak milik satu keluarga (pemilik = username akun gurunya).

    Nama unik PER KELUARGA, bukan global: dua keluarga boleh sama-sama
    punya 'Bima'. Duplikat dalam satu keluarga mengembalikan baris yang
    sudah ada (INSERT OR IGNORE) — perilaku idempoten lama dipertahankan.
    """
    kon.execute(
        "INSERT OR IGNORE INTO siswa (nama, tingkat, pemilik) VALUES (?, ?, ?)",
        (nama, tingkat, pemilik),
    )
    baris = kon.execute(
        "SELECT id FROM siswa WHERE nama = ? AND pemilik = ?", (nama, pemilik)
    ).fetchone()
    return int(baris["id"])


def daftar_siswa(
    kon: sqlite3.Connection, pemilik: str | None = None
) -> list[sqlite3.Row]:
    """Daftar anak. `pemilik=None` = tanpa filter (admin dan panggilan
    lama); string = hanya keluarga itu, urut nama."""
    if pemilik is None:
        return kon.execute("SELECT * FROM siswa ORDER BY nama").fetchall()
    return kon.execute(
        "SELECT * FROM siswa WHERE pemilik = ? ORDER BY nama", (pemilik,)
    ).fetchall()


def siswa_milik(kon: sqlite3.Connection, siswa_id: int, pemilik: str) -> bool:
    """True bila siswa ini milik keluarga `pemilik` tersebut.

    Penjaga tunggal untuk seluruh rute guru; pengecualian admin diperiksa
    di lapisan web (peran), bukan di sini.
    """
    baris = kon.execute(
        "SELECT 1 FROM siswa WHERE id = ? AND pemilik = ?", (siswa_id, pemilik)
    ).fetchone()
    return baris is not None


def sesi_milik(kon: sqlite3.Connection, sesi_id: int, pemilik: str) -> bool:
    """True bila sesi ini milik siswa yang ber-pemilik tersebut."""
    baris = kon.execute(
        """SELECT 1
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id
           WHERE s.id = ? AND w.pemilik = ?""",
        (sesi_id, pemilik),
    ).fetchone()
    return baris is not None


# ── Bank soal ───────────────────────────────────────────────────────────


def simpan_soal(kon: sqlite3.Connection, soal: Soal) -> int:
    """Masukkan soal ke bank. Idempoten lewat tanda_tangan.

    Mengembalikan id soal — yang lama kalau sudah pernah ada, sehingga
    generate berulang tidak menggandakan bank.
    """
    ada = kon.execute(
        "SELECT id FROM soal WHERE tanda_tangan = ?", (soal.tanda_tangan,)
    ).fetchone()
    if ada:
        return int(ada["id"])

    cur = kon.execute(
        """INSERT INTO soal (tanda_tangan, template_id, parameter, kunci,
                             bagian, tantangan, level)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            soal.tanda_tangan,
            soal.template_id,
            json.dumps(soal.parameter, ensure_ascii=False, sort_keys=True),
            soal.kunci,
            soal.bagian,
            int(soal.tantangan),
            soal.level,
        ),
    )
    soal_id = int(cur.lastrowid)

    for m in soal.malrule:
        kon.execute(
            """INSERT OR IGNORE INTO malrule (soal_id, malrule_id, jawaban, kode, alasan)
               VALUES (?, ?, ?, ?, ?)""",
            (soal_id, m.id, m.jawaban, m.kode, m.alasan),
        )
    return soal_id


def statistik_bank(kon: sqlite3.Connection) -> list[sqlite3.Row]:
    return kon.execute(
        """SELECT template_id, COUNT(*) AS jumlah
           FROM soal GROUP BY template_id ORDER BY jumlah DESC"""
    ).fetchall()


def _simpan_butir_sesi(
    kon: sqlite3.Connection, sesi_id: int, nomor: int, soal: Soal
) -> int:
    """Simpan relasi soal beserta 12 kolom snapshot penyajiannya."""
    penyajian = question_views.penyajian_dari_soal(soal)
    soal_id = simpan_soal(kon, soal)
    cur = kon.execute(
        """INSERT INTO sesi_soal (
               sesi_id, soal_id, nomor,
               teks_soal, bagian_soal, tantangan_soal, minta_restatement,
               penyajian_json, penyajian_versi, renderer_versi, asal_teks,
               status_visual, mode_representasi, fingerprint_matematis,
               fingerprint_penyajian
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sesi_id,
            soal_id,
            nomor,
            penyajian.teks_soal,
            penyajian.bagian_soal,
            int(penyajian.tantangan_soal),
            int(penyajian.minta_restatement),
            serialisasi_penyajian(penyajian),
            penyajian.penyajian_versi,
            penyajian.renderer_versi,
            penyajian.asal_teks,
            penyajian.status_visual,
            penyajian.mode_representasi,
            penyajian.fingerprint_matematis,
            penyajian.fingerprint_penyajian,
        ),
    )
    return int(cur.lastrowid)


# ── Sesi ────────────────────────────────────────────────────────────────


def buat_sesi(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    topik: str = TOPIK_BAWAAN,
    tanggal: str | None = None,
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    timer_mode: str = "tanpa",
    durasi_menit: int = 15,
    timer_auto: int = 0,
    jumlah_soal: int | None = None,
) -> int:
    """Bangkitkan lembar dari seed, simpan soalnya ke bank, rangkai jadi sesi."""
    MODE_SAH = ("diagnostik", "drill")
    TIMER_SAH = ("tanpa", "sesi", "soal")
    if mode not in MODE_SAH:
        raise ValueError(f"mode tidak dikenal: {mode!r} (sah: {', '.join(MODE_SAH)})")
    if timer_mode not in TIMER_SAH:
        raise ValueError(
            f"timer_mode tidak dikenal: {timer_mode!r} (sah: {', '.join(TIMER_SAH)})"
        )
    if mode == "diagnostik":
        timer_mode, durasi_menit, timer_auto = "tanpa", 15, 0
    if not isinstance(durasi_menit, int) or not 1 <= durasi_menit <= 180:
        raise ValueError(f"durasi_menit tidak wajar: {durasi_menit!r}")

    lembar = buat_lembar(seed, level=level, topik=topik, jumlah_soal=jumlah_soal)
    # Level yang DICATAT adalah level yang benar-benar dipakai generator,
    # bukan yang diminta. `siswa.tingkat` teks bebas, dan `_level_efektif`
    # menormalkan nilai tak dikenal ke level paket — menyimpan yang mentah
    # membuat kolom ini berbohong: halaman murid menampilkan "level kelas 4"
    # untuk lembar yang isinya P3, dan laporan guru ikut salah label.
    # Level yang sah tidak tersentuh: untuk itu lembar.level == level.
    level = lembar.level

    kon.execute("SAVEPOINT buat_sesi_snapshot")
    try:
        if tanggal:
            cur = kon.execute(
                """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                     timer_mode, durasi_menit, timer_auto, tanggal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (siswa_id, seed, topik, level, mode,
                 timer_mode, durasi_menit, timer_auto, tanggal),
            )
        else:
            cur = kon.execute(
                """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                     timer_mode, durasi_menit, timer_auto)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (siswa_id, seed, topik, level, mode,
                 timer_mode, durasi_menit, timer_auto),
            )
        sesi_id = int(cur.lastrowid)

        for nomor, soal in enumerate(lembar.soal, start=1):
            _simpan_butir_sesi(kon, sesi_id, nomor, soal)
        kon.execute("RELEASE SAVEPOINT buat_sesi_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_snapshot")
        raise


def buat_sesi_dari_urutan(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    urutan: tuple[str, ...],
    topik: str | Any = TOPIK_BAWAAN,
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    jenis: str = "biasa",
    sumber_sesi_id: int | None = None,
    *,
    soal_terpilih: tuple[Soal, ...] | None = None,
) -> int:
    """Sesi dengan komposisi soal DITENTUKAN pemanggil, bukan dari paket.

    Dipakai remedial: template diambil dari kesalahan anak, bukan dari
    komposisi bawaan level. Sengaja fungsi terpisah, bukan parameter
    tambahan di buat_sesi — pemanggil biasa tidak boleh bisa menyetel
    komposisi tanpa sadar, dan alur normalnya tetap satu jalur.

    `topik` boleh objek Topik (paket ad-hoc lintas topik): yang tersimpan
    ke kolom `sesi.topik` adalah id-nya, supaya `topics.dari_sesi` bisa
    merekonstruksi paket yang sama saat lembar dicetak ulang.
    """
    if jenis not in ("biasa", "remedial"):
        raise ValueError(f"jenis sesi tidak dikenal: {jenis!r}")
    if jenis == "biasa" and sumber_sesi_id is not None:
        raise ValueError("sesi biasa tidak boleh memiliki sumber remedial")
    if soal_terpilih is None:
        lembar = buat_lembar(seed, urutan=urutan, level=level, topik=topik)
    else:
        from collections import Counter
        from generator import Lembar

        if (Counter(s.template_id for s in soal_terpilih) != Counter(urutan)
                or any(s.level != level for s in soal_terpilih)):
            raise ValueError("soal terpilih tidak cocok dengan komposisi atau level")
        lembar = Lembar(seed, soal_terpilih, level)
    topik_id = getattr(topik, "id", topik)
    kon.execute("SAVEPOINT buat_sesi_urutan_snapshot")
    try:
        cur = kon.execute(
            """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                 timer_mode, durasi_menit, timer_auto,
                                 jenis, sumber_sesi_id)
               VALUES (?, ?, ?, ?, ?, 'tanpa', 15, 0, ?, ?)""",
            (siswa_id, seed, topik_id, lembar.level, mode, jenis, sumber_sesi_id),
        )
        sesi_id = int(cur.lastrowid)
        for nomor, soal in enumerate(lembar.soal, start=1):
            _simpan_butir_sesi(kon, sesi_id, nomor, soal)
        kon.execute("RELEASE SAVEPOINT buat_sesi_urutan_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_urutan_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_urutan_snapshot")
        raise


def buat_sesi_gabungan(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    topik_ids: list[str],
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    jumlah_soal: int | None = None,
) -> int:
    """Sesi lintas BEBERAPA topik pilihan guru (poin 4 tahap 2).

    Kolom `sesi.topik` menyimpan id gabungan ("gabungan:a,b") sehingga
    sesi lama tetap bisa dibaca: `topics.dari_sesi` mengurainya kembali.
    Soalnya sendiri sudah tersimpan baris-per-baris di tabel soal, jadi
    replay tidak bergantung pada paket ad-hoc ini. Default diagnostik dijaga
    untuk pemanggil internal lama; form gabungan mengirim mode secara eksplisit.
    """
    if mode not in ("diagnostik", "drill"):
        raise ValueError(f"mode tidak dikenal: {mode!r}")

    from topics import gabungan

    paket = gabungan(topik_ids)
    # Level datang dari `siswa.tingkat` (teks bebas), bukan dari pilihan
    # guru — dan tidak semua topik punya semua level (logika melompati P4,
    # kombinatorik mulai P5). Anak P4 yang memilih dua topik tanpa P4 dulu
    # membuat generator melempar ValueError dan handler mati. Level yang
    # bukan pilihan pengguna dinormalkan, bukan ditolak.
    if level not in paket.komposisi:
        level = _level_terdekat(level, paket.komposisi)
    lembar = buat_lembar(
        seed, level=level, topik=paket, jumlah_soal=jumlah_soal
    )
    kon.execute("SAVEPOINT buat_sesi_gabungan_snapshot")
    try:
        cur = kon.execute(
            """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                 timer_mode, durasi_menit, timer_auto)
               VALUES (?, ?, ?, ?, ?, 'tanpa', 15, 0)""",
            (siswa_id, seed, paket.id, lembar.level, mode),
        )
        sesi_id = int(cur.lastrowid)
        for nomor, soal in enumerate(lembar.soal, start=1):
            _simpan_butir_sesi(kon, sesi_id, nomor, soal)
        kon.execute("RELEASE SAVEPOINT buat_sesi_gabungan_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_gabungan_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_gabungan_snapshot")
        raise


def _baris_sasaran_remedial(
    kon: sqlite3.Connection,
    siswa_id: int,
    sesi_id: int | None = None,
) -> list[sqlite3.Row]:
    """Bukti diagnosis sah, terbaru lebih dulu per template."""
    syarat_sesi = " AND se.id = ?" if sesi_id is not None else ""
    parameter: tuple[int, ...] = (
        (siswa_id, sesi_id) if sesi_id is not None else (siswa_id,)
    )
    return kon.execute(
        """SELECT s.template_id,
                  se.id AS sesi_id,
                  se.tanggal,
                  ss.nomor,
                  d.benar,
                  IFNULL(d.kode_final, d.kode_usulan) AS kode,
                  d.alasan
           FROM diagnosis d
           JOIN jawaban j    ON j.id = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id = ss.soal_id
           WHERE se.siswa_id = ?
             AND se.selesai IS NOT NULL
             AND se.direview IS NOT NULL"""
        + syarat_sesi
        + " ORDER BY se.tanggal DESC, se.id DESC, ss.nomor DESC",
        parameter,
    ).fetchall()


def _susun_sasaran(baris: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Ringkas bukti per template; hanya kesalahan terbaru non-T yang aktif."""
    from topics import pemilik_template

    jumlah_salah: dict[str, int] = {}
    for bukti in baris:
        kode = bukti["kode"]
        if not bukti["benar"] and kode != "T":
            template_id = bukti["template_id"]
            jumlah_salah[template_id] = jumlah_salah.get(template_id, 0) + 1

    terbaru: dict[str, sqlite3.Row] = {}
    for bukti in baris:
        terbaru.setdefault(bukti["template_id"], bukti)

    hasil: list[dict[str, Any]] = []
    for template_id, bukti in terbaru.items():
        kode = bukti["kode"]
        if bukti["benar"] or kode == "T":
            continue
        hasil.append(
            {
                "template_id": template_id,
                "topik": pemilik_template(template_id),
                "kode": kode,
                "alasan": bukti["alasan"],
                "kali_salah": jumlah_salah[template_id],
                "sesi_terakhir": int(bukti["sesi_id"]),
                "tanggal_terakhir": bukti["tanggal"],
                "direkomendasikan": kode == "K",
            }
        )
    return hasil


def sasaran_remedial_anak(
    kon: sqlite3.Connection, siswa_id: int
) -> list[dict[str, Any]]:
    """Kandidat remedial aktif dari seluruh hasil yang sudah direview guru."""
    return _susun_sasaran(_baris_sasaran_remedial(kon, siswa_id))


def sasaran_remedial_sesi(
    kon: sqlite3.Connection, siswa_id: int, sesi_id: int
) -> list[dict[str, Any]]:
    """Kandidat remedial dari satu sesi sah milik anak tersebut."""
    sumber = kon.execute(
        """SELECT 1 FROM sesi
           WHERE id = ? AND siswa_id = ?
             AND selesai IS NOT NULL AND direview IS NOT NULL""",
        (sesi_id, siswa_id),
    ).fetchone()
    if sumber is None:
        return []
    return _susun_sasaran(_baris_sasaran_remedial(kon, siswa_id, sesi_id))


def sasaran_remedial(
    kon: sqlite3.Connection, siswa_id: int, batas: int = 6
) -> list[str]:
    """Template yang perlu DILATIH ULANG oleh anak ini (poin a Filia).

    Sumbernya data nyata, bukan tebakan: template yang jawabannya pernah
    salah (diagnosis.benar = 0) untuk anak ini. Diurut dari yang paling
    sering salah, lalu yang paling baru — supaya sesi remedial menyerang
    yang paling membebani lebih dulu.

    Yang TIDAK dihitung:
      - soal yang belum dijawab (tidak ada bukti anak tidak bisa);
      - kode 'T' (belum pernah diajarkan) — itu peta urutan belajar, dan
        melatih ulang materi yang belum diajarkan bukan remedial, itu
        menjatuhkan anak dua kali;
      - template yang SELALU benar.

    `batas` menjaga sesi remedial tetap masuk akal (bawaan 6 konsep).
    Kembalian [] berarti tidak ada dasar untuk remedial — pemanggil WAJIB
    menghormati itu dan tidak mengarang latihan.
    """
    baris = kon.execute(
        """SELECT s.template_id            AS template_id,
                  COUNT(*)                 AS kali_salah,
                  MAX(se.tanggal)          AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ?
             AND se.selesai IS NOT NULL
             AND d.benar = 0
             AND IFNULL(d.kode_final, IFNULL(d.kode_usulan, '')) <> 'T'
           GROUP BY s.template_id
           ORDER BY kali_salah DESC, terakhir DESC""",
        (siswa_id,),
    ).fetchall()
    return [b["template_id"] for b in baris[:batas]]


def _level_terdekat(level: str, tersedia) -> str:
    """Level didukung yang PALING DEKAT dengan level anak.

    Dipakai remedial: paket sasaran bisa saja tidak punya level anak
    (logika melompati P4). Memilih yang terdekat — bukan yang pertama —
    menjaga soal tetap sepadan: anak P4 dapat P3, bukan P6.
    Seri (mis. P4 antara P3 dan P5) diputus ke bawah: lebih baik sedikit
    terlalu mudah daripada terlalu sulit untuk latihan ulang.
    """
    from templates import LEVEL

    urut = [lv for lv in LEVEL if lv in tersedia]
    if not urut:
        return level
    if level not in LEVEL:
        return urut[0]
    posisi = LEVEL.index(level)
    return min(urut, key=lambda lv: (abs(LEVEL.index(lv) - posisi),
                                     LEVEL.index(lv)))


def buat_sesi_remedial(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int | None = None,
    level: str = LEVEL_BAWAAN,
    topik: str | None = None,
    jumlah_soal: int = 10,
    template_ids: list[str] | None = None,
    sumber_sesi_id: int | None = None,
) -> int | None:
    """Sesi latihan ulang berisi HANYA konsep yang pernah dijawab salah.

    Kunci desainnya: template-nya sama, SOALNYA BARU. Seed berbeda berarti
    angka/objeknya berganti — yang dilatih konsepnya, bukan hafalan jawaban
    lembar lama. Ini juga yang membuat perbandingan "sudah membaik atau
    belum" bermakna.

    `seed=None` berarti pilih seed yang BELUM pernah dipakai anak ini
    (pola sama dengan buat_sesi_seed_baru) — pemanggil web tidak perlu
    mengurus keacakan sendiri. Seed eksplisit dipakai test determinisme.

    `topik=None` (bawaan) berarti paket DITURUNKAN dari sasaran lewat
    `topics.paket_untuk_template`. Ini bukan kenyamanan, ini koreksi bug:
    sasaran remedial datang dari seluruh riwayat anak, jadi template-nya
    bisa milik topik mana pun. Versi lama memaksa paket bawaan
    (pola-bilangan) dan melempar KeyError untuk anak yang salah di topik
    lain — 502 di produksi, 3 Sep 2026.

    None kalau tidak ada sasaran (anak belum punya kesalahan tercatat) —
    lebih jujur daripada membuat sesi acak dan menyebutnya remedial.
    """
    if not isinstance(jumlah_soal, int) or not 1 <= jumlah_soal <= 50:
        raise ValueError("jumlah_soal harus antara 1 dan 50")

    if sumber_sesi_id is None:
        kandidat = sasaran_remedial_anak(kon, siswa_id)
        kandidat_ids = [b["template_id"] for b in kandidat]
    else:
        sumber = kon.execute(
            """SELECT 1 FROM sesi
               WHERE id = ? AND siswa_id = ?
                 AND selesai IS NOT NULL AND direview IS NOT NULL""",
            (sumber_sesi_id, siswa_id),
        ).fetchone()
        if sumber is None:
            raise ValueError("sumber sesi remedial tidak sah")
        kandidat_ids = [
            b["template_id"]
            for b in sasaran_remedial_sesi(kon, siswa_id, sumber_sesi_id)
        ]

    if template_ids is None:
        sasaran = kandidat_ids[:6]
    else:
        if not template_ids:
            raise ValueError("pilihan template kosong")
        if len(template_ids) != len(set(template_ids)):
            raise ValueError("pilihan template duplikat")
        if len(template_ids) > 3:
            raise ValueError("pilihan template maksimal 3")
        if jumlah_soal < len(template_ids):
            raise ValueError("jumlah soal harus memuat setiap fokus")
        bukan_kandidat = set(template_ids) - set(kandidat_ids)
        if bukan_kandidat:
            raise ValueError("template bukan kandidat remedial")
        sasaran = list(template_ids)

    if not sasaran:
        return None
    if topik is None:
        from topics import paket_untuk_template

        paket = paket_untuk_template(sasaran)
    else:
        paket = topik
    # `siswa.tingkat` adalah teks bebas dan paket sasaran belum tentu
    # mendukung level itu (mis. anak P4 yang salah di topik logika = P3/P5/P6).
    # Guru memilih topik lewat dropdown yang sudah difilter per level, jadi
    # ValueError generator masih benar DI SANA; di sini levelnya bukan
    # pilihan siapa pun, jadi dinormalkan ke level terdekat yang didukung
    # daripada mematikan fitur untuk anak yang levelnya "salah".
    komposisi = getattr(paket, "komposisi", None)
    if komposisi and level not in komposisi:
        level = _level_terdekat(level, komposisi)
    if seed is None:
        dipakai = {
            r["seed"]
            for r in kon.execute(
                "SELECT seed FROM sesi WHERE siswa_id = ?", (siswa_id,)
            ).fetchall()
        }
        for _ in range(500):
            calon = random.randint(1, 9_999_999)
            if calon not in dipakai:
                seed = calon
                break
        else:
            raise RuntimeError("gagal menemukan seed baru")
    # Ulangi sasaran round-robin sampai memenuhi jumlah_soal: tiap konsep
    # dapat porsi seimbang, dan urutannya tetap diacak per lembar oleh
    # generator (_acak_urutan) supaya posisi soal tidak menghafal.
    urutan: list[str] = []
    while len(urutan) < jumlah_soal:
        urutan.extend(sasaran)
    return buat_sesi_dari_urutan(
        kon, siswa_id, seed,
        urutan=tuple(urutan[:jumlah_soal]),
        level=level, topik=paket,
        jenis="remedial", sumber_sesi_id=sumber_sesi_id,
    )


def tandai_pengenalan_selesai(
    kon: sqlite3.Connection,
    siswa_id: int,
    putaran_id: int,
    fokus,
    pendekatan_id: str,
) -> None:
    from learning_sessions import tandai_pengenalan_selesai as tandai

    tandai(kon, siswa_id, putaran_id, fokus, pendekatan_id)


def buat_sesi_dari_rencana(
    kon: sqlite3.Connection,
    siswa_id: int,
    rencana,
    *,
    putaran_id: int,
    seed: int,
    occurrence: int = 1,
) -> int:
    """Delegasikan orkestrasi sesi tanpa mencampur aturan ke akses DB dasar."""
    from learning_sessions import buat_sesi_dari_rencana as buat

    return buat(
        kon,
        siswa_id,
        rencana,
        putaran_id=putaran_id,
        seed=seed,
        occurrence=occurrence,
    )


def isi_sesi(kon: sqlite3.Connection, sesi_id: int) -> list[sqlite3.Row]:
    """Soal satu sesi beserta jawaban & diagnosisnya, urut nomor."""
    return kon.execute(
        """SELECT ss.id AS sesi_soal_id, ss.nomor,
                  ss.teks_soal, ss.bagian_soal, ss.tantangan_soal,
                  ss.minta_restatement, ss.penyajian_json,
                  ss.penyajian_versi, ss.renderer_versi, ss.asal_teks,
                  ss.status_visual, ss.mode_representasi,
                  ss.fingerprint_matematis, ss.fingerprint_penyajian,
                  s.id AS soal_id, s.template_id, s.parameter, s.kunci,
                  s.bagian, s.tantangan, s.level, s.cerita,
                  j.id AS jawaban_id, j.restatement, j.cara, j.jawaban,
                  j.belum_pernah, j.detik,
                  d.benar, d.kode_usulan, d.kode_final, d.malrule_id,
                  d.alasan, d.manual, d.catatan
           FROM sesi_soal ss
           JOIN soal s        ON s.id = ss.soal_id
           LEFT JOIN jawaban j   ON j.sesi_soal_id = ss.id
           LEFT JOIN diagnosis d ON d.jawaban_id = j.id
           WHERE ss.sesi_id = ?
           ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()


def hapus_sesi(kon: sqlite3.Connection, sesi_id: int) -> bool:
    """Hapus satu sesi beserta seluruh jejaknya di basis data.

    sesi_soal, jawaban, diagnosis, dan lampiran mengikuti lewat
    ON DELETE CASCADE — sudah diatur skema. Berkas foto lampiran di
    cakram TIDAK diurus sini: pemanggil (web) membersihkannya lewat
    attachments.bersihkan_berkas.

    Mengembalikan False bila sesi tidak ada, tanpa melempar — pemanggil
    cukup menampilkan pesan, bukan menangani pengecualian.
    """
    cur = kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))
    return cur.rowcount > 0


def tandai_mulai(kon: sqlite3.Connection, sesi_id: int) -> None:
    """Catat waktu mulai pengerjaan (alur murid) — sekali saja.

    Idempoten: POST berulang dari HP tidak boleh menggeser mulai, kalau
    tidak, durasi pengerjaan jadi bohong. Sesi tak dikenal: no-op, bukan
    pengecualian — pemanggilnya adalah handler HTTP yang sibuk menyimpan.
    """
    kon.execute(
        """UPDATE sesi SET mulai = datetime('now', '+7 hours')
           WHERE id = ? AND mulai IS NULL""",
        (sesi_id,),
    )


def tandai_selesai(kon: sqlite3.Connection, sesi_id: int) -> None:
    """Catat waktu selesai — dipanggil saat semua soal terisi.

    Dijaga WHERE selesai IS NULL: anak yang menekan simpan lagi setelah
    halaman selesai tidak boleh menggeser angka durasinya.
    """
    kon.execute(
        """UPDATE sesi SET selesai = datetime('now', '+7 hours')
           WHERE id = ? AND selesai IS NULL""",
        (sesi_id,),
    )


def malrule_soal(kon: sqlite3.Connection, soal_id: int) -> list[sqlite3.Row]:
    return kon.execute(
        "SELECT malrule_id, jawaban, kode, alasan FROM malrule WHERE soal_id = ?",
        (soal_id,),
    ).fetchall()


# ── Jawaban & diagnosis ─────────────────────────────────────────────────


def simpan_jawaban(
    kon: sqlite3.Connection,
    sesi_soal_id: int,
    jawaban: str = "",
    cara: str = "",
    restatement: str = "",
    belum_pernah: bool = False,
    detik: int | None = None,
) -> int:
    """Simpan/perbarui jawaban satu soal. Idempoten per sesi_soal."""
    kon.execute(
        """INSERT INTO jawaban (sesi_soal_id, restatement, cara, jawaban,
                                belum_pernah, detik)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(sesi_soal_id) DO UPDATE SET
               restatement  = excluded.restatement,
               cara         = excluded.cara,
               jawaban      = excluded.jawaban,
               belum_pernah = excluded.belum_pernah,
               detik        = excluded.detik""",
        (sesi_soal_id, restatement, cara, jawaban, int(belum_pernah), detik),
    )
    baris = kon.execute(
        "SELECT id FROM jawaban WHERE sesi_soal_id = ?", (sesi_soal_id,)
    ).fetchone()
    # Simpan_jawaban juga dapat mengubah outcome setelah konfirmasi. Jalur ini
    # memakai helper invalidasi yang sama dengan koreksi diagnosis.
    _invalidasi_konfirmasi_dari_jawaban(kon, int(baris["id"]))
    return int(baris["id"])


def simpan_diagnosis(
    kon: sqlite3.Connection,
    jawaban_id: int,
    benar: bool,
    kode_usulan: str | None,
    kode_final: str | None,
    malrule_id: str | None = None,
    alasan: str = "",
    manual: bool = False,
    catatan: str = "",
) -> int:
    kon.execute(
        """INSERT INTO diagnosis (jawaban_id, benar, kode_usulan, kode_final,
                                  malrule_id, alasan, manual, catatan)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(jawaban_id) DO UPDATE SET
               benar       = excluded.benar,
               kode_usulan = excluded.kode_usulan,
               kode_final  = excluded.kode_final,
               malrule_id  = excluded.malrule_id,
               alasan      = excluded.alasan,
               manual      = excluded.manual,
               catatan     = excluded.catatan""",
        (
            jawaban_id,
            int(benar),
            kode_usulan,
            kode_final,
            malrule_id,
            alasan,
            int(manual),
            catatan,
        ),
    )
    _invalidasi_konfirmasi_dari_jawaban(kon, jawaban_id)
    baris = kon.execute(
        "SELECT id FROM diagnosis WHERE jawaban_id = ?", (jawaban_id,)
    ).fetchone()
    return int(baris["id"])


def _invalidasi_konfirmasi_dari_jawaban(
    kon: sqlite3.Connection, jawaban_id: int
) -> None:
    """Batalkan cache bukti aktif setelah diagnosis ditulis ulang.

    Snapshot lama tetap immutable. Event hanya lahir bila sesi sebelumnya
    memang punya konfirmasi aktif, sehingga penulisan diagnosis awal tidak
    menciptakan invalidasi palsu.
    """
    sesi = kon.execute(
        """SELECT se.id, se.siswa_id, se.putaran_id, se.dikonfirmasi_guru,
                  kh.id AS konfirmasi_id
           FROM jawaban j
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se ON se.id = ss.sesi_id
           LEFT JOIN konfirmasi_hasil kh
             ON kh.id = (
                 SELECT aktif.id
                 FROM konfirmasi_hasil aktif
                 WHERE aktif.sesi_id = se.id
                   AND aktif.fingerprint = se.fingerprint_konfirmasi
                 ORDER BY aktif.nomor_urut DESC, aktif.id DESC
                 LIMIT 1
             )
           WHERE j.id = ?""",
        (jawaban_id,),
    ).fetchone()
    if sesi is None or sesi["dikonfirmasi_guru"] is None:
        return
    kon.execute(
        """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data)
           VALUES (?, ?, ?, ?, 'konfirmasi_dibatalkan', ?)""",
        (
            sesi["siswa_id"],
            sesi["putaran_id"],
            sesi["id"],
            sesi["konfirmasi_id"],
            json.dumps({"alasan": "diagnosis_diubah"}, sort_keys=True),
        ),
    )
    kon.execute(
        """UPDATE sesi
           SET dikonfirmasi_guru = NULL, fingerprint_konfirmasi = NULL
           WHERE id = ?""",
        (sesi["id"],),
    )


def _validasi_sesi_putaran(
    kon: sqlite3.Connection, putaran: Any, sesi_ids: list[int]
) -> list[int]:
    """Deduplikasi dan validasi seluruh sesi sebelum satu pun ditautkan."""
    unik = list(dict.fromkeys(sesi_ids))
    for sesi_id in unik:
        sesi = kon.execute(
            "SELECT siswa_id, level, putaran_id FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
        if sesi is None or sesi["siswa_id"] != putaran["siswa_id"]:
            raise ValueError("sesi bukan milik siswa putaran")
        if sesi["level"] != putaran["level"]:
            raise ValueError("level sesi berbeda dari putaran")
        if sesi["putaran_id"] not in (None, putaran["id"]):
            raise ValueError("sesi sudah terikat ke putaran lain")
    return unik


def buat_putaran_fokus(
    kon: sqlite3.Connection,
    siswa_id: int,
    level: str,
    sesi_ids: list[int] | None = None,
) -> int:
    sesi_ids = list(dict.fromkeys(sesi_ids or []))
    calon = {"id": None, "siswa_id": siswa_id, "level": level}
    _validasi_sesi_putaran(kon, calon, sesi_ids)
    cur = kon.execute(
        "INSERT INTO putaran_fokus (siswa_id, level) VALUES (?, ?)",
        (siswa_id, level),
    )
    putaran_id = int(cur.lastrowid)
    if sesi_ids:
        kon.executemany(
            "UPDATE sesi SET putaran_id = ? WHERE id = ?",
            [(putaran_id, sesi_id) for sesi_id in sesi_ids],
        )
    return putaran_id


def tautkan_sesi_putaran(
    kon: sqlite3.Connection, putaran_id: int, sesi_ids: list[int]
) -> None:
    putaran = kon.execute(
        "SELECT id, siswa_id, level FROM putaran_fokus WHERE id = ?", (putaran_id,)
    ).fetchone()
    if putaran is None:
        raise ValueError("putaran tidak dikenal")
    unik = _validasi_sesi_putaran(kon, putaran, sesi_ids)
    kon.executemany(
        "UPDATE sesi SET putaran_id = ? WHERE id = ?",
        [(putaran_id, sesi_id) for sesi_id in unik],
    )


def tambah_anggota_fokus(
    kon: sqlite3.Connection,
    putaran_id: int,
    template_id: str,
    kode_intervensi: str,
    malrule_id: str | None,
    sumber_sesi_ids: list[int],
    *,
    izinkan_provenance_historis: bool = False,
) -> int:
    """Tambahkan satu dari maksimal dua kunci fokus beserta provenance sesi."""
    jumlah = kon.execute(
        "SELECT COUNT(*) FROM anggota_fokus WHERE putaran_id = ?", (putaran_id,)
    ).fetchone()[0]
    duplikat = kon.execute(
        """SELECT 1 FROM anggota_fokus
           WHERE putaran_id = ? AND template_id = ? AND kode_intervensi = ?
             AND malrule_id_kanonis = ?""",
        (putaran_id, template_id, kode_intervensi, malrule_id or ""),
    ).fetchone()
    if duplikat is not None:
        raise sqlite3.IntegrityError("kunci fokus kanonis sudah ada")
    if jumlah >= 2:
        raise ValueError("satu putaran maksimal dua fokus")
    putaran = kon.execute(
        "SELECT siswa_id, level FROM putaran_fokus WHERE id = ?", (putaran_id,)
    ).fetchone()
    if putaran is None:
        raise ValueError("putaran tidak dikenal")
    if not sumber_sesi_ids:
        raise ValueError("fokus harus memiliki provenance sesi")
    for sesi_id in sumber_sesi_ids:
        if izinkan_provenance_historis:
            milik = kon.execute(
                """SELECT 1 FROM sesi
                   WHERE id = ? AND siswa_id = ? AND level = ?""",
                (sesi_id, putaran["siswa_id"], putaran["level"]),
            ).fetchone()
        else:
            milik = kon.execute(
                """SELECT 1 FROM sesi
                   WHERE id = ? AND siswa_id = ? AND putaran_id = ?""",
                (sesi_id, putaran["siswa_id"], putaran_id),
            ).fetchone()
        if milik is None:
            raise ValueError("sesi provenance bukan milik siswa dan putaran")

    cur = kon.execute(
        """INSERT INTO anggota_fokus
               (putaran_id, slot, template_id, kode_intervensi, malrule_id_kanonis)
           VALUES (?, ?, ?, ?, ?)""",
        (putaran_id, jumlah + 1, template_id, kode_intervensi, malrule_id or ""),
    )
    anggota_id = int(cur.lastrowid)
    for sesi_id in dict.fromkeys(sumber_sesi_ids):
        kon.execute(
            "INSERT INTO bukti_fokus (anggota_fokus_id, sesi_id) VALUES (?, ?)",
            (anggota_id, sesi_id),
        )
    return anggota_id


def _target_per_butir(
    kon: sqlite3.Connection, sesi_id: int
) -> dict[int, tuple[str, str, Optional[str]]]:
    event = kon.execute(
        """SELECT data FROM kejadian_belajar
           WHERE sesi_id = ? AND jenis = 'sesi_dibuat'
           ORDER BY id DESC LIMIT 1""",
        (sesi_id,),
    ).fetchone()
    if event is None:
        return {}
    data = json.loads(event["data"] or "{}")
    target = data.get("target_per_nomor", {}) if isinstance(data, dict) else {}
    hasil = {}
    for nomor, mentah in target.items():
        if not isinstance(mentah, list) or len(mentah) != 3:
            continue
        hasil[int(nomor)] = (mentah[0], mentah[1], mentah[2])
    return hasil


def konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None = None,
    cek_pemahaman: dict[int, str] | None = None,
) -> int:
    """Sahkan snapshot dan provenance atomik, tanpa meng-commit pemanggil."""
    with outcome_presentations.transaksi(kon):
        return _konfirmasi_hasil(kon, sesi_id, guru, dilewati, cek_pemahaman)


def _konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None,
    cek_pemahaman: dict[int, str] | None,
) -> int:
    """Sahkan outcome lengkap menjadi snapshot immutable dan event audit."""
    dilewati = dilewati or set()
    cek_pemahaman = cek_pemahaman or {}
    sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    if sesi is None:
        raise ValueError("sesi tidak dikenal")
    if sesi["dibatalkan"] is not None:
        raise ValueError("sesi dibatalkan")
    if sesi["selesai"] is None:
        raise ValueError("sesi belum selesai")

    outcome = isi_sesi(kon, sesi_id)
    jumlah_butir = kon.execute(
        "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()[0]
    if len(outcome) != jumlah_butir:
        raise ValueError("hubungan snapshot penyajian sesi tidak lengkap")
    if not outcome:
        raise ValueError("sesi tidak memiliki butir")
    id_butir = {int(b["sesi_soal_id"]) for b in outcome}
    if not dilewati <= id_butir or not set(cek_pemahaman) <= id_butir:
        raise ValueError("referensi butir tidak dikenal")
    pemahaman_sah = {"bisa_menjelaskan", "ragu", "menghafal"}
    if any(nilai not in pemahaman_sah for nilai in cek_pemahaman.values()):
        raise ValueError("cek pemahaman tidak dikenal")
    for butir in outcome:
        butir_id = int(butir["sesi_soal_id"])
        if butir_id in dilewati:
            continue
        if butir["jawaban_id"] is None or butir["benar"] is None:
            raise ValueError("outcome belum lengkap")
        if not bool(butir["benar"]) and butir["kode_final"] is None:
            raise ValueError("outcome belum lengkap")
        if bool(butir["benar"]) and (
            butir["kode_final"] is not None or butir["malrule_id"] is not None
        ):
            raise ValueError("outcome belum lengkap")

    import review_store
    tinjauan = review_store.validasi_bukti(kon, sesi_id, outcome, dilewati)
    target_per_butir = _target_per_butir(kon, sesi_id)
    kanonis = []
    for butir in outcome:
        butir_id = int(butir["sesi_soal_id"])
        lewat = butir_id in dilewati
        target_fokus = target_per_butir.get(int(butir["nomor"]))
        kanonis.append(
            {
                "nomor": int(butir["nomor"]),
                "template_id": butir["template_id"],
                "jawaban": "" if lewat else (butir["jawaban"] or ""),
                "benar": None if lewat else int(butir["benar"]),
                "kode_final": None if lewat else butir["kode_final"],
                "malrule_id": None if lewat else butir["malrule_id"],
                "dilewati": int(lewat),
                "level_efektif": sesi["level"],
                "cek_pemahaman": cek_pemahaman.get(butir_id),
                "target_template_id": None if target_fokus is None else target_fokus[0],
                "target_kode_intervensi": None if target_fokus is None else target_fokus[1],
                "target_malrule_id": None if target_fokus is None else target_fokus[2],
            }
        )
    isi_fingerprint = {"outcome": kanonis, "tinjauan": tinjauan} if tinjauan else kanonis
    serial = json.dumps(isi_fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serial.encode("utf-8")).hexdigest()
    aktif = kon.execute(
        """SELECT kh.id
           FROM konfirmasi_hasil kh
           JOIN sesi se ON se.id = kh.sesi_id
           WHERE kh.sesi_id = ?
             AND kh.fingerprint = ?
             AND se.dikonfirmasi_guru IS NOT NULL
             AND se.fingerprint_konfirmasi = kh.fingerprint
           ORDER BY kh.nomor_urut DESC, kh.id DESC
           LIMIT 1""",
        (sesi_id, fingerprint),
    ).fetchone()
    if aktif is not None:
        outcome_presentations.lengkapi(kon, int(aktif["id"]))
        return int(aktif["id"])
    nomor_urut = int(
        kon.execute(
            """SELECT COALESCE(MAX(nomor_urut), 0) + 1
               FROM konfirmasi_hasil WHERE sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
    )
    cur = kon.execute(
        """INSERT INTO konfirmasi_hasil
               (sesi_id, nomor_urut, guru, fingerprint)
           VALUES (?, ?, ?, ?)""",
        (sesi_id, nomor_urut, guru, fingerprint),
    )
    konfirmasi_id = int(cur.lastrowid)
    if tinjauan:
        kon.execute("INSERT INTO tinjauan_outcome VALUES (?,?)",
                    (konfirmasi_id, json.dumps(tinjauan, ensure_ascii=False, sort_keys=True)))
    for butir, salinan in zip(outcome, kanonis):
        kon.execute(
            """INSERT INTO snapshot_outcome
                   (konfirmasi_id, sesi_soal_id, nomor, template_id, jawaban,
                    benar, kode_final, malrule_id, dilewati, level_efektif,
                    cek_pemahaman, target_template_id, target_kode_intervensi,
                    target_malrule_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                konfirmasi_id,
                butir["sesi_soal_id"],
                salinan["nomor"],
                salinan["template_id"],
                salinan["jawaban"],
                salinan["benar"],
                salinan["kode_final"],
                salinan["malrule_id"],
                salinan["dilewati"],
                salinan["level_efektif"],
                salinan["cek_pemahaman"],
                salinan["target_template_id"],
                salinan["target_kode_intervensi"],
                salinan["target_malrule_id"],
            ),
        )
    outcome_presentations.lengkapi(kon, konfirmasi_id)
    kon.execute(
        """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data)
           VALUES (?, ?, ?, ?, 'hasil_dikonfirmasi', ?)""",
        (
            sesi["siswa_id"],
            sesi["putaran_id"],
            sesi_id,
            konfirmasi_id,
            json.dumps({"nomor_urut": nomor_urut}, sort_keys=True),
        ),
    )
    kon.execute(
        """UPDATE sesi
           SET dikonfirmasi_guru = datetime('now', '+7 hours'),
               fingerprint_konfirmasi = ?
           WHERE id = ?""",
        (fingerprint, sesi_id),
    )
    return konfirmasi_id


# ── Loader immutable siklus belajar ─────────────────────────────────────


def _tanggal_domain(nilai: str) -> date:
    """Ambil tanggal dari nilai SQLite date/datetime."""
    return date.fromisoformat(nilai[:10])


def _tanggal_domain_opsional(nilai: Optional[str]) -> Optional[date]:
    if nilai is None:
        return None
    return _tanggal_domain(nilai)


def _data_kejadian(nilai: str) -> tuple[tuple[str, object], ...]:
    data = json.loads(nilai or "{}")
    if not isinstance(data, dict):
        return ()

    def bekukan(objek):
        if isinstance(objek, list):
            return tuple(bekukan(item) for item in objek)
        if isinstance(objek, dict):
            return tuple(sorted((kunci, bekukan(isi)) for kunci, isi in objek.items()))
        return objek

    return tuple(sorted((kunci, bekukan(isi)) for kunci, isi in data.items()))


def muat_bukti_siklus(kon: sqlite3.Connection, siswa_id: int):
    """Muat snapshot aktif dan histori append-only sebagai input reducer murni."""
    from learning_cycle import (
        BuktiSiklus,
        KejadianSiklus,
        OutcomeSiklus,
        PutaranSiklus,
        SesiSiklus,
    )

    siswa = kon.execute(
        "SELECT id, tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None:
        raise ValueError("siswa tidak dikenal")

    fokus_per_putaran: dict[int, list[tuple[str, str, Optional[str]]]] = {}
    for baris in kon.execute(
        """SELECT putaran_id, slot, template_id, kode_intervensi,
                  malrule_id_kanonis
           FROM anggota_fokus
           WHERE putaran_id IN (SELECT id FROM putaran_fokus WHERE siswa_id = ?)
           ORDER BY putaran_id, slot""",
        (siswa_id,),
    ).fetchall():
        fokus_per_putaran.setdefault(int(baris["putaran_id"]), []).append(
            (
                baris["template_id"],
                baris["kode_intervensi"],
                baris["malrule_id_kanonis"] or None,
            )
        )

    putaran = tuple(
        PutaranSiklus(
            int(baris["id"]),
            siswa_id,
            baris["level"],
            _tanggal_domain(baris["dibuka"]),
            tuple(fokus_per_putaran.get(int(baris["id"]), ())),
        )
        for baris in kon.execute(
            """SELECT id, level, dibuka FROM putaran_fokus
               WHERE siswa_id = ? ORDER BY id""",
            (siswa_id,),
        ).fetchall()
    )

    kejadian = tuple(
        KejadianSiklus(
            int(baris["id"]),
            baris["jenis"],
            _tanggal_domain(baris["dibuat"]),
            baris["putaran_id"],
            baris["sesi_id"],
            baris["konfirmasi_id"],
            _data_kejadian(baris["data"]),
        )
        for baris in kon.execute(
            """SELECT id, jenis, dibuat, putaran_id, sesi_id, konfirmasi_id, data
               FROM kejadian_belajar WHERE siswa_id = ? ORDER BY id""",
            (siswa_id,),
        ).fetchall()
    )
    metadata_sesi = {
        event.sesi_id: event
        for event in kejadian
        if event.jenis == "sesi_dibuat" and event.sesi_id is not None
    }

    sesi_hasil = []
    sesi_baris = kon.execute(
        """SELECT id, level, tujuan, tanggal, dibuat, selesai, direview,
                  dikonfirmasi_guru, putaran_id, bagian_checkpoint, dibatalkan,
                  fingerprint_konfirmasi
           FROM sesi WHERE siswa_id = ? ORDER BY tanggal, id""",
        (siswa_id,),
    ).fetchall()
    for baris in sesi_baris:
        outcome = ()
        aktif = None
        metadata = metadata_sesi.get(int(baris["id"]))
        target_fokus = ()
        occurrence = None
        if metadata is not None:
            fokus_mentah = metadata.nilai("fokus", ())
            if isinstance(fokus_mentah, tuple):
                target_fokus = tuple(tuple(kunci) for kunci in fokus_mentah)
            occurrence_mentah = metadata.nilai("occurrence")
            if isinstance(occurrence_mentah, int):
                occurrence = occurrence_mentah
        if baris["dikonfirmasi_guru"] is not None:
            aktif = kon.execute(
                """SELECT id FROM konfirmasi_hasil
                   WHERE sesi_id = ? AND fingerprint = ?
                   ORDER BY nomor_urut DESC, id DESC LIMIT 1""",
                (baris["id"], baris["fingerprint_konfirmasi"]),
            ).fetchone()
            if aktif is not None:
                outcome = tuple(
                    OutcomeSiklus(
                        item["template_id"],
                        None if item["benar"] is None else bool(item["benar"]),
                        item["kode_final"],
                        item["malrule_id"],
                        bool(item["dilewati"]),
                        item["cek_pemahaman"],
                        (
                            None
                            if item["target_template_id"] is None
                            else (
                                item["target_template_id"],
                                item["target_kode_intervensi"],
                                item["target_malrule_id"],
                            )
                        ),
                        mode_representasi=item["mode_representasi"],
                        fingerprint_penyajian=item["fingerprint_penyajian"],
                    )
                    for item in outcome_presentations.muat(kon, int(aktif["id"]))
                )
        sesi_hasil.append(
            SesiSiklus(
                int(baris["id"]),
                siswa_id,
                baris["level"],
                baris["tujuan"],
                _tanggal_domain(baris["tanggal"]),
                baris["dibuat"],
                baris["selesai"],
                baris["direview"],
                baris["dikonfirmasi_guru"],
                baris["putaran_id"],
                baris["bagian_checkpoint"],
                baris["dibatalkan"],
                outcome,
                target_fokus,
                occurrence,
                None if aktif is None else int(aktif["id"]),
                _tanggal_domain_opsional(baris["selesai"]),
                _tanggal_domain_opsional(baris["dikonfirmasi_guru"]),
            )
        )
    import interventions
    from learning_cycle import _putaran_dengan_override

    putaran_efektif = tuple(
        _putaran_dengan_override(item, kejadian) for item in putaran
    )
    pendekatan_tersedia = tuple(
        (
            kunci,
            tuple(
                materi.pendekatan_id
                for materi in interventions.pilihan_untuk_fokus(kunci)
                if materi.tersedia
            ),
        )
        for satu_putaran in putaran_efektif
        if satu_putaran is not None
        for kunci in satu_putaran.fokus
    )
    return BuktiSiklus(
        siswa_id,
        siswa["tingkat"],
        tuple(sesi_hasil),
        putaran,
        kejadian,
        pendekatan_tersedia,
    )


def batalkan_sesi(
    kon: sqlite3.Connection, sesi_id: int, alasan: str = ""
) -> None:
    sesi = kon.execute(
        "SELECT siswa_id, putaran_id FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    if sesi is None:
        raise ValueError("sesi tidak dikenal")
    kon.execute(
        """UPDATE sesi SET dibatalkan = COALESCE(
               dibatalkan, datetime('now', '+7 hours')) WHERE id = ?""",
        (sesi_id,),
    )
    kon.execute(
        """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, jenis, data)
           VALUES (?, ?, ?, 'sesi_dibatalkan', ?)""",
        (
            sesi["siswa_id"],
            sesi["putaran_id"],
            sesi_id,
            json.dumps({"alasan": alasan}, ensure_ascii=False, sort_keys=True),
        ),
    )


def ganti_level(
    kon: sqlite3.Connection, siswa_id: int, level_baru: str
) -> None:
    siswa = kon.execute(
        "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None:
        raise ValueError("siswa tidak dikenal")
    level_lama = siswa["tingkat"]
    if level_lama == level_baru:
        return
    kon.execute("UPDATE siswa SET tingkat = ? WHERE id = ?", (level_baru, siswa_id))
    putaran = kon.execute(
        """SELECT id FROM putaran_fokus
           WHERE siswa_id = ? AND level = ?
           ORDER BY id DESC LIMIT 1""",
        (siswa_id, level_lama),
    ).fetchone()
    kon.execute(
        """INSERT INTO kejadian_belajar (siswa_id, putaran_id, jenis, data)
           VALUES (?, ?, 'diganti_level', ?)""",
        (
            siswa_id,
            None if putaran is None else putaran["id"],
            json.dumps(
                {"level_lama": level_lama, "level_baru": level_baru},
                ensure_ascii=False,
                sort_keys=True,
            ),
        ),
    )


# ── Laporan ─────────────────────────────────────────────────────────────


def ringkasan(kon: sqlite3.Connection, siswa_id: int | None = None) -> list[sqlite3.Row]:
    if siswa_id is None:
        return kon.execute(
            """SELECT r.* FROM ringkasan_sesi r
               JOIN sesi s ON s.id = r.sesi_id
               WHERE s.selesai IS NOT NULL
               ORDER BY r.tanggal DESC, r.sesi_id DESC"""
        ).fetchall()
    return kon.execute(
        """SELECT r.* FROM ringkasan_sesi r
           JOIN sesi s ON s.id = r.sesi_id
           WHERE r.siswa_id = ? AND s.selesai IS NOT NULL
           ORDER BY r.tanggal DESC, r.sesi_id DESC""",
        (siswa_id,),
    ).fetchall()


def miskonsepsi_berulang(
    kon: sqlite3.Connection, siswa_id: int, minimal: int = 1
) -> list[sqlite3.Row]:
    """Miskonsepsi dihitung per malrule_id, bukan per nomor soal.

    Aturan dari lembar penilaian: satu miskonsepsi yang muncul di tiga soal
    tetap satu miskonsepsi. Yang penting bukan berapa soal yang salah, tapi
    berapa gagasan keliru yang masih hidup — dan mana yang bertahan lintas
    sesi meski angkanya sudah diganti.
    """
    return kon.execute(
        """SELECT d.malrule_id,
                  s.template_id,
                  se.topik                   AS topik,
                  MAX(d.alasan)              AS alasan,
                  COUNT(*)                   AS kemunculan,
                  COUNT(DISTINCT se.id)      AS jumlah_sesi,
                  MIN(se.tanggal)            AS pertama,
                  MAX(se.tanggal)            AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ?
             AND se.selesai IS NOT NULL
             AND d.kode_final = 'K'
             AND d.malrule_id IS NOT NULL
           GROUP BY d.malrule_id, s.template_id, se.topik
           HAVING COUNT(*) >= ?
           ORDER BY jumlah_sesi DESC, kemunculan DESC""",
        (siswa_id, minimal),
    ).fetchall()


def peta_materi_baru(kon: sqlite3.Connection, siswa_id: int) -> list[sqlite3.Row]:
    """Tipe soal yang ditandai T — belum pernah diajarkan, bukan kegagalan."""
    return kon.execute(
        """SELECT s.template_id, se.topik AS topik,
                  COUNT(*) AS kali, MAX(se.tanggal) AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ? AND se.selesai IS NOT NULL
             AND d.kode_final = 'T'
           GROUP BY s.template_id, se.topik
           ORDER BY kali DESC""",
        (siswa_id,),
    ).fetchall()


# ── Lampiran foto lembar (Fase 2) ──────────────────────────────────────


def simpan_lampiran(
    kon: sqlite3.Connection,
    sesi_id: int,
    nama_berkas: str,
    mime: str = "image/jpeg",
    hasil_json: str = "",
) -> int:
    """Simpan catatan lampiran. Berkasnya sendiri disimpan di cakram oleh
    pemanggil (web) — tabel ini hanya metadata + hasil ekstraksi AI mentah."""
    cur = kon.execute(
        """INSERT INTO lampiran (sesi_id, nama_berkas, mime, hasil_json)
           VALUES (?, ?, ?, ?)""",
        (sesi_id, nama_berkas, mime, hasil_json),
    )
    return int(cur.lastrowid)


def daftar_lampiran(kon: sqlite3.Connection, sesi_id: int) -> list[sqlite3.Row]:
    return kon.execute(
        "SELECT * FROM lampiran WHERE sesi_id = ? ORDER BY id DESC", (sesi_id,)
    ).fetchall()


def ambil_lampiran(kon: sqlite3.Connection, lampiran_id: int) -> sqlite3.Row | None:
    return kon.execute(
        "SELECT * FROM lampiran WHERE id = ?", (lampiran_id,)
    ).fetchone()


def tandai_lampiran(
    kon: sqlite3.Connection, lampiran_id: int, status: str
) -> None:
    """Ubah status lampiran: 'baru' -> 'diterapkan' (atau sebaliknya)."""
    kon.execute(
        "UPDATE lampiran SET status = ? WHERE id = ?", (status, lampiran_id)
    )
