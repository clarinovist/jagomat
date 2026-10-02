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
from attachment_store import (
    ambil_lampiran,
    daftar_lampiran,
    simpan_lampiran,
    tandai_lampiran,
)
import outcome_presentations
from question_bank_store import simpan_soal, statistik_bank
from report_store import miskonsepsi_berulang, peta_materi_baru, ringkasan
from session_read_store import (
    hapus_sesi, isi_sesi, malrule_soal, tandai_mulai, tandai_selesai,
)
from student_profile_store import daftar_siswa, sesi_milik, siswa_milik, tambah_siswa
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
    import choice_store
    choice_store.daftarkan_validasi(kon)
    try:
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def validasi_operasi_foto(kon) -> None:
    """Reader metadata exact; tidak bootstrap atau memperbaiki schema parsial."""
    from schema import SKEMA_OPERASI_FOTO
    if kon.execute('PRAGMA user_version').fetchone()[0] != 0:
        raise ValueError('versi basis belajar tidak dikenal')
    def struktur(koneksi):
        return tuple(tuple(r) for r in koneksi.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name='operasi_foto_baca' OR name='operasi_foto_lampiran_hapus' ORDER BY type,name"))
    acuan = sqlite3.connect(':memory:')
    try:
        acuan.execute('CREATE TABLE lampiran(id INTEGER PRIMARY KEY,sesi_id INTEGER)')
        acuan.executescript(SKEMA_OPERASI_FOTO)
        if struktur(kon) != struktur(acuan):
            raise ValueError('penyimpanan operasi foto belum terverifikasi')
    finally:
        acuan.close()
    if kon.execute('''SELECT 1 FROM operasi_foto_baca o LEFT JOIN lampiran l ON l.id=o.hasil_id
            WHERE o.hasil_id IS NOT NULL AND (l.id IS NULL OR l.sesi_id!=o.sesi_id)
            LIMIT 1''').fetchone():
        raise ValueError('pointer receipt foto tidak sah')


def migrasikan_operasi_foto(path) -> None:
    """Pasang receipt foto aditif secara eksplisit; startup/GET tidak memanggil.

    File belajar wajib existing; table baru tidak mengubah user_version legacy0.
    Binary recovery wajib memahami receipt sebelum penegakan foto diaktifkan.
    """
    from schema import SKEMA_OPERASI_FOTO
    kon = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True)
    try:
        kon.execute('PRAGMA foreign_keys=ON')
        kon.execute('BEGIN IMMEDIATE')
        if kon.execute('PRAGMA user_version').fetchone()[0] != 0:
            raise ValueError('versi basis belajar tidak dikenal')
        for tabel in ('sesi', 'siswa', 'lampiran'):
            if not kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabel,)).fetchone():
                raise ValueError('basis belajar belum siap')
        ada = kon.execute("SELECT 1 FROM sqlite_master WHERE tbl_name='operasi_foto_baca' OR name='operasi_foto_lampiran_hapus'").fetchone()
        if not ada:
            _jalankan_skema(kon, SKEMA_OPERASI_FOTO)
        validasi_operasi_foto(kon)
        if kon.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('foreign key operasi foto tidak sah')
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


# ── Bank soal dan sesi ──────────────────────────────────────────────────


def _simpan_butir_sesi(
    kon: sqlite3.Connection, sesi_id: int, nomor: int, soal: Soal
) -> int:
    import session_store

    return session_store._simpan_butir_sesi(
        kon, sesi_id, nomor, soal,
        question_views_module=question_views,
        simpan_soal_func=simpan_soal,
        serialisasi=serialisasi_penyajian,
    )


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
    format_jawaban: str = 'isian',
) -> int:
    import session_store

    return session_store.buat_sesi(
        kon, siswa_id, seed, topik, tanggal, level, mode, timer_mode,
        durasi_menit, timer_auto, jumlah_soal, format_jawaban,
        pembuat_lembar=buat_lembar, simpan_butir=_simpan_butir_sesi,
    )


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
    import session_store

    return session_store.buat_sesi_dari_urutan(
        kon, siswa_id, seed, urutan, topik, level, mode, jenis,
        sumber_sesi_id, soal_terpilih=soal_terpilih,
        pembuat_lembar=buat_lembar, simpan_butir=_simpan_butir_sesi,
    )


def buat_sesi_gabungan(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    topik_ids: list[str],
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
) -> int:
    import session_store

    return session_store.buat_sesi_gabungan(
        kon, siswa_id, seed, topik_ids, level, mode, jumlah_soal,
        format_jawaban, pembuat_lembar=buat_lembar,
        simpan_butir=_simpan_butir_sesi, pilih_level=_level_terdekat,
    )


def _baris_sasaran_remedial(
    kon: sqlite3.Connection, siswa_id: int, sesi_id: int | None = None,
) -> list[sqlite3.Row]:
    import session_store

    return session_store._baris_sasaran_remedial(kon, siswa_id, sesi_id)


def _susun_sasaran(baris: list[sqlite3.Row]) -> list[dict[str, Any]]:
    import session_store

    return session_store._susun_sasaran(baris)


def sasaran_remedial_anak(
    kon: sqlite3.Connection, siswa_id: int
) -> list[dict[str, Any]]:
    import session_store

    return session_store.sasaran_remedial_anak(kon, siswa_id)


def sasaran_remedial_sesi(
    kon: sqlite3.Connection, siswa_id: int, sesi_id: int
) -> list[dict[str, Any]]:
    import session_store

    return session_store.sasaran_remedial_sesi(kon, siswa_id, sesi_id)


def sasaran_remedial(
    kon: sqlite3.Connection, siswa_id: int, batas: int = 6
) -> list[str]:
    import session_store

    return session_store.sasaran_remedial(kon, siswa_id, batas)


def _level_terdekat(level: str, tersedia) -> str:
    import session_store

    return session_store._level_terdekat(level, tersedia)


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
    import session_store

    return session_store.buat_sesi_remedial(
        kon, siswa_id, seed, level, topik, jumlah_soal, template_ids,
        sumber_sesi_id, sasaran_anak=sasaran_remedial_anak,
        sasaran_sesi=sasaran_remedial_sesi, pilih_level=_level_terdekat,
        buat_dari_urutan=buat_sesi_dari_urutan, random_module=random,
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
    import answer_store

    return answer_store.simpan_jawaban(
        kon, sesi_soal_id, jawaban, cara, restatement, belum_pernah, detik,
        invalidasi=_invalidasi_konfirmasi_dari_jawaban,
    )


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
    import answer_store

    return answer_store.simpan_diagnosis(
        kon, jawaban_id, benar, kode_usulan, kode_final, malrule_id, alasan,
        manual, catatan, invalidasi=_invalidasi_konfirmasi_dari_jawaban,
    )


def _invalidasi_konfirmasi_dari_jawaban(
    kon: sqlite3.Connection, jawaban_id: int
) -> None:
    import answer_store

    answer_store._invalidasi_konfirmasi_dari_jawaban(kon, jawaban_id)

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
    import learning_evidence_store

    return learning_evidence_store._target_per_butir(kon, sesi_id)


def konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None = None,
    cek_pemahaman: dict[int, str] | None = None,
) -> int:
    import learning_evidence_store

    return learning_evidence_store.konfirmasi_hasil(
        kon, sesi_id, guru, dilewati, cek_pemahaman,
        transaksi=outcome_presentations.transaksi,
        konfirmasi_impl=_konfirmasi_hasil,
    )


def _konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None,
    cek_pemahaman: dict[int, str] | None,
) -> int:
    import learning_evidence_store

    return learning_evidence_store._konfirmasi_hasil(
        kon, sesi_id, guru, dilewati, cek_pemahaman,
        muat_outcome=isi_sesi, target_per_butir=_target_per_butir,
    )


def _tanggal_domain(nilai: str) -> date:
    import learning_evidence_store

    return learning_evidence_store._tanggal_domain(nilai)


def _tanggal_domain_opsional(nilai: Optional[str]) -> Optional[date]:
    import learning_evidence_store

    return learning_evidence_store._tanggal_domain_opsional(nilai)


def _data_kejadian(nilai: str) -> tuple[tuple[str, object], ...]:
    import learning_evidence_store

    return learning_evidence_store._data_kejadian(nilai)


def muat_bukti_siklus(
    kon: sqlite3.Connection, siswa_id: int, *, validasi_pilot=True
):
    import learning_evidence_store

    return learning_evidence_store.muat_bukti_siklus(
        kon, siswa_id, validasi_pilot=validasi_pilot,
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
