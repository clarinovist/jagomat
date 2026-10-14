"""SQLite privat untuk wawancara riset konsumen yang dianonimkan."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Callable, Optional, Sequence

import research_instrument as instrumen
import research_schema as schema


BAWAAN = Path(os.environ.get("RISET_BERKAS_DB", "/data/riset-konsumen.db"))
SUMBER = frozenset(("meta_ads", "referensi", "komunitas", "internal", "lainnya"))
STATUS_JAWABAN = frozenset(("dijawab", "tidak_dibahas", "tidak_tahu", "menolak"))
STATUS_KLARIFIKASI = frozenset(("tidak_perlu", "sudah", "ambigu"))
RETENSI_HARI = 90
BATAS_PER_HALAMAN = 25


class StoreRisetBelumSiap(RuntimeError):
    """Database riset hilang, rusak, atau belum dimigrasikan."""


class KonflikRiset(RuntimeError):
    """Snapshot berubah atau operation ID dipakai untuk perintah berbeda."""


@dataclass(frozen=True)
class HalamanWawancara:
    item: tuple
    total: int
    halaman: int
    per_halaman: int


def _tujuan(path=None) -> Path:
    return Path(path) if path is not None else BAWAAN


def _uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + "?mode=" + mode


def _koneksi(path: Path, mode: str) -> sqlite3.Connection:
    try:
        kon = sqlite3.connect(_uri(path, mode), uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise StoreRisetBelumSiap("database riset tidak tersedia") from galat
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    kon.execute("PRAGMA busy_timeout=5000")
    return kon


def _validasi(kon: sqlite3.Connection) -> None:
    try:
        schema.validasi(kon)
        daftar = kon.execute(
            "SELECT kode_versi,snapshot_json,sidik FROM instrumen_riset"
        ).fetchall()
        if not daftar:
            raise ValueError("instrumen riset kosong")
        for baris in daftar:
            data = instrumen.muat_json(baris["snapshot_json"])
            if data["kode"] != baris["kode_versi"] or instrumen.sidik(data) != baris["sidik"]:
                raise ValueError("snapshot instrumen tidak cocok")
    except (ValueError, sqlite3.Error):
        raise StoreRisetBelumSiap("struktur database riset tidak lengkap") from None


@contextmanager
def buka_baca(path=None):
    """Buka read-only tanpa membuat atau memperbaiki file."""
    kon = _koneksi(_tujuan(path), "ro")
    try:
        kon.execute("PRAGMA query_only=ON")
        _validasi(kon)
        yield kon
    finally:
        kon.close()


@contextmanager
def _transaksi(path=None):
    kon = _koneksi(_tujuan(path), "rw")
    try:
        _validasi(kon)
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def siapkan(path=None, *, sekarang: Optional[int] = None) -> None:
    """Bootstrap/replay eksplisit v1; tidak pernah dipanggil oleh GET."""
    tujuan = _tujuan(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    kon = sqlite3.connect(str(tujuan), timeout=5.0)
    try:
        kon.row_factory = sqlite3.Row
        kon.execute("PRAGMA foreign_keys=ON")
        kon.execute("BEGIN IMMEDIATE")
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi == 0:
            schema.jalankan_ddl(kon, schema.DDL)
            kon.execute(
                "INSERT INTO studi_riset VALUES(?,?,?,?,?,NULL)",
                (instrumen.SLUG_STUDI_AKTIF, "Validasi masalah B2C orang tua/wali kelas 3–6",
                 "Pengalaman orang tua/wali mendampingi matematika dalam kejadian nyata.",
                 "aktif", kini),
            )
            snapshot = instrumen.snapshot()
            kon.execute(
                "INSERT INTO instrumen_riset(studi_slug,kode_versi,snapshot_json,sidik,diterbitkan) "
                "VALUES(?,?,?,?,?)",
                (instrumen.SLUG_STUDI_AKTIF, instrumen.KODE_VERSI_AKTIF,
                 instrumen.json_kanonis(snapshot), instrumen.sidik(snapshot), kini),
            )
            kon.execute("PRAGMA user_version=%d" % schema.VERSI_SKEMA)
        elif versi != schema.VERSI_SKEMA:
            raise StoreRisetBelumSiap("versi database riset tidak didukung")
        _validasi(kon)
        if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise StoreRisetBelumSiap("integritas database riset gagal")
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass


def _operasi_id(nilai: str) -> str:
    if not isinstance(nilai, str) or re.fullmatch(r"op_[0-9a-f]{32}", nilai) is None:
        raise ValueError("operation ID tidak sah")
    return nilai


def _wawancara_id(nilai: str) -> str:
    if not isinstance(nilai, str) or re.fullmatch(r"waw_[0-9a-f]{32}", nilai) is None:
        raise ValueError("ID wawancara tidak sah")
    return nilai


def _actor(nilai: str) -> str:
    if not isinstance(nilai, str) or not 8 <= len(nilai) <= 80:
        raise ValueError("actor riset tidak sah")
    return nilai


def _kode_responden(nilai: str) -> str:
    nilai = nilai.strip().upper() if isinstance(nilai, str) else ""
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,31}", nilai):
        raise ValueError("kode responden tidak sah")
    return nilai


def _instrument_dari_baris(kon, baris) -> dict:
    instrumen_baris = kon.execute(
        "SELECT * FROM instrumen_riset WHERE id=?", (baris["instrumen_id"],)
    ).fetchone()
    if instrumen_baris is None:
        raise StoreRisetBelumSiap("instrumen wawancara hilang")
    return instrumen.muat_json(instrumen_baris["snapshot_json"])


def _sidik_perintah(aksi, target_id, payload) -> str:
    bahan = json.dumps(
        {"aksi": aksi, "target": target_id, "payload": payload},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(bahan).hexdigest()


def _replay(kon, operasi_id, actor_id, aksi, target_id, sidik):
    ada = kon.execute(
        "SELECT actor_id,aksi,target_id,sidik_perintah FROM audit_riset WHERE operasi_id=?",
        (operasi_id,),
    ).fetchone()
    if ada is None:
        return False
    if (ada["actor_id"], ada["aksi"], ada["target_id"], ada["sidik_perintah"]) == (
        actor_id, aksi, target_id, sidik,
    ):
        return True
    raise KonflikRiset("operation ID telah dipakai")


def _audit(kon, operasi_id, actor_id, aksi, target_id, sidik, sekarang):
    if _replay(kon, operasi_id, actor_id, aksi, target_id, sidik):
        return False
    kon.execute(
        "INSERT INTO audit_riset VALUES(?,?,?,?,?,?,?)",
        (operasi_id, actor_id, aksi, target_id, sidik, "sukses", sekarang),
    )
    return True


def buat_wawancara(path, *, actor_id: str, operasi_id: str, kode_responden: str,
                    sumber: str, consent_rekaman: bool, diwawancarai: int,
                    sekarang: Optional[int] = None) -> str:
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    kode_responden = _kode_responden(kode_responden)
    if sumber not in SUMBER or type(consent_rekaman) is not bool:
        raise ValueError("metadata wawancara tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    if type(diwawancarai) is not int or diwawancarai < 0 or diwawancarai > kini + 86400:
        raise ValueError("waktu wawancara tidak sah")
    identitas = "waw_" + secrets.token_hex(16)
    sidik = _sidik_perintah("buat", "buat", {
        "kode_responden": kode_responden, "sumber": sumber,
        "consent_rekaman": consent_rekaman, "diwawancarai": diwawancarai,
    })
    with _transaksi(path) as kon:
        replay = kon.execute(
            "SELECT target_id,actor_id,aksi,sidik_perintah FROM audit_riset WHERE operasi_id=?",
            (operasi_id,),
        ).fetchone()
        if replay is not None:
            if (replay["actor_id"], replay["aksi"], replay["sidik_perintah"]) == (
                actor_id, "buat", sidik,
            ):
                return str(replay["target_id"])
            raise KonflikRiset("operation ID telah dipakai")
        aktif = kon.execute(
            "SELECT id FROM instrumen_riset WHERE kode_versi=? AND studi_slug=?",
            (instrumen.KODE_VERSI_AKTIF, instrumen.SLUG_STUDI_AKTIF),
        ).fetchone()
        if aktif is None:
            raise StoreRisetBelumSiap("instrumen aktif tidak tersedia")
        retensi = kini + RETENSI_HARI * 86400
        kon.execute(
            "INSERT INTO wawancara_riset VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (identitas, instrumen.SLUG_STUDI_AKTIF, aktif["id"], kode_responden,
             actor_id, sumber, 1, int(consent_rekaman), "draf", 1,
             diwawancarai, kini, kini, None, retensi),
        )
        _audit(kon, operasi_id, actor_id, "buat", identitas, sidik, kini)
    return identitas


def daftar_wawancara(path=None, *, status: str = "", halaman: int = 1) -> HalamanWawancara:
    if status not in ("", "draf", "final", "perlu_redaksi", "ditarik"):
        raise ValueError("status filter tidak sah")
    if type(halaman) is not int or halaman < 1:
        raise ValueError("halaman tidak sah")
    syarat = " WHERE status=?" if status else ""
    argumen = (status,) if status else ()
    with buka_baca(path) as kon:
        total = int(kon.execute("SELECT COUNT(*) FROM wawancara_riset" + syarat, argumen).fetchone()[0])
        baris = kon.execute(
            "SELECT w.*,i.kode_versi,(SELECT COUNT(*) FROM jawaban_riset j WHERE j.wawancara_id=w.id) AS terisi "
            "FROM wawancara_riset w JOIN instrumen_riset i ON i.id=w.instrumen_id" + syarat +
            " ORDER BY w.diperbarui DESC,w.id DESC LIMIT ? OFFSET ?",
            (*argumen, BATAS_PER_HALAMAN, (halaman - 1) * BATAS_PER_HALAMAN),
        ).fetchall()
        item = tuple(dict(b) for b in baris)
    return HalamanWawancara(item, total, halaman, BATAS_PER_HALAMAN)


def ringkasan(path=None, *, sekarang: Optional[int] = None) -> dict:
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with buka_baca(path) as kon:
        status = {baris["status"]: int(baris["n"]) for baris in kon.execute(
            "SELECT status,COUNT(*) AS n FROM wawancara_riset GROUP BY status"
        )}
        mendekati = int(kon.execute(
            "SELECT COUNT(*) FROM wawancara_riset WHERE status!='ditarik' AND retensi_hingga BETWEEN ? AND ?",
            (kini, kini + 7 * 86400),
        ).fetchone()[0])
    return {**{k: status.get(k, 0) for k in ("draf", "final", "perlu_redaksi", "ditarik")},
            "mendekati_retensi": mendekati}


def detail_wawancara(path, identitas: str) -> Optional[dict]:
    identitas = _wawancara_id(identitas)
    with buka_baca(path) as kon:
        baris = kon.execute(
            "SELECT w.*,i.kode_versi,i.snapshot_json FROM wawancara_riset w "
            "JOIN instrumen_riset i ON i.id=w.instrumen_id WHERE w.id=?", (identitas,)
        ).fetchone()
        if baris is None:
            return None
        data_instrumen = instrumen.muat_json(baris["snapshot_json"])
        jawaban = {}
        for jaw in kon.execute(
            "SELECT * FROM jawaban_riset WHERE wawancara_id=? ORDER BY pertanyaan_kode", (identitas,)
        ):
            item = dict(jaw)
            item["kode_tambahan"] = tuple(r[0] for r in kon.execute(
                "SELECT kode FROM kode_tambahan_riset WHERE wawancara_id=? AND pertanyaan_kode=? ORDER BY kode",
                (identitas, jaw["pertanyaan_kode"]),
            ))
            jawaban[jaw["pertanyaan_kode"]] = item
        hasil = dict(baris)
        hasil["instrumen"] = data_instrumen
        hasil["jawaban"] = jawaban
        hasil.pop("snapshot_json", None)
        return hasil


def simpan_jawaban(path, *, actor_id: str, operasi_id: str, wawancara_id: str,
                    pertanyaan_kode: str, revisi_wawancara: int, revisi_jawaban: int,
                    status_jawaban: str, jawaban_responden: str,
                    kutipan_responden: str, kutipan_terpilih: bool,
                    catatan_interviewer: str, kode_utama: Optional[str],
                    kode_tambahan: Sequence[str], status_klarifikasi: str,
                    sekarang: Optional[int] = None) -> None:
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    wawancara_id = _wawancara_id(wawancara_id)
    if type(revisi_wawancara) is not int or revisi_wawancara < 1 or type(revisi_jawaban) is not int or revisi_jawaban < 0:
        raise ValueError("revisi tidak sah")
    if status_jawaban not in STATUS_JAWABAN or status_klarifikasi not in STATUS_KLARIFIKASI:
        raise ValueError("status jawaban tidak sah")
    if any(type(x) is not str for x in (jawaban_responden, kutipan_responden, catatan_interviewer)):
        raise ValueError("teks jawaban tidak sah")
    jawaban_responden = jawaban_responden.strip()
    kutipan_responden = kutipan_responden.strip()
    catatan_interviewer = catatan_interviewer.strip()
    if len(jawaban_responden) > 6000 or len(kutipan_responden) > 2000 or len(catatan_interviewer) > 4000:
        raise ValueError("teks jawaban terlalu panjang")
    if type(kutipan_terpilih) is not bool or type(kode_tambahan) not in (tuple, list):
        raise ValueError("metadata jawaban tidak sah")
    if status_jawaban != "dijawab":
        if any((jawaban_responden, kutipan_responden, kode_utama, kode_tambahan, kutipan_terpilih)):
            raise ValueError("jawaban nonnarasi tidak boleh membawa bukti")
    elif not any((jawaban_responden, kutipan_responden, catatan_interviewer, kode_utama, kode_tambahan)):
        raise ValueError("jawaban kosong")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    tambahan = tuple(dict.fromkeys(kode_tambahan))
    sidik = _sidik_perintah("ubah_jawaban", wawancara_id, {
        "pertanyaan": pertanyaan_kode, "revisi_wawancara": revisi_wawancara,
        "revisi_jawaban": revisi_jawaban, "status": status_jawaban,
        "jawaban": jawaban_responden, "kutipan": kutipan_responden,
        "kutipan_terpilih": kutipan_terpilih, "catatan": catatan_interviewer,
        "kode_utama": kode_utama, "kode_tambahan": tambahan,
        "klarifikasi": status_klarifikasi,
    })
    with _transaksi(path) as kon:
        if _replay(kon, operasi_id, actor_id, "ubah_jawaban", wawancara_id, sidik):
            return
        wawancara = kon.execute("SELECT * FROM wawancara_riset WHERE id=?", (wawancara_id,)).fetchone()
        if wawancara is None:
            raise LookupError("wawancara tidak tersedia")
        if wawancara["status"] not in ("draf", "perlu_redaksi") or wawancara["actor_id"] != actor_id:
            raise PermissionError("wawancara tidak dapat diubah")
        if int(wawancara["revisi"]) != revisi_wawancara:
            raise KonflikRiset("wawancara telah berubah")
        data_instrumen = _instrument_dari_baris(kon, wawancara)
        item = instrumen.pertanyaan(data_instrumen, pertanyaan_kode)
        diizinkan = instrumen.kode_diizinkan(item)
        if (kode_utama is not None and kode_utama not in diizinkan
                or any(kode not in diizinkan for kode in tambahan)
                or kode_utama in tambahan):
            raise ValueError("kode jawaban tidak sah")
        lama = kon.execute(
            "SELECT revisi FROM jawaban_riset WHERE wawancara_id=? AND pertanyaan_kode=?",
            (wawancara_id, pertanyaan_kode),
        ).fetchone()
        if (0 if lama is None else int(lama["revisi"])) != revisi_jawaban:
            raise KonflikRiset("jawaban telah berubah")
        revisi_baru = revisi_jawaban + 1
        if lama is None:
            kon.execute(
                "INSERT INTO jawaban_riset VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (wawancara_id, pertanyaan_kode, status_jawaban, jawaban_responden,
                 kutipan_responden, int(kutipan_terpilih), catatan_interviewer,
                 kode_utama, status_klarifikasi, revisi_baru, kini),
            )
        else:
            kon.execute(
                "UPDATE jawaban_riset SET status_jawaban=?,jawaban_responden=?,kutipan_responden=?,"
                "kutipan_terpilih=?,catatan_interviewer=?,kode_utama=?,status_klarifikasi=?,"
                "revisi=?,diperbarui=? WHERE wawancara_id=? AND pertanyaan_kode=? AND revisi=?",
                (status_jawaban, jawaban_responden, kutipan_responden, int(kutipan_terpilih),
                 catatan_interviewer, kode_utama, status_klarifikasi, revisi_baru, kini,
                 wawancara_id, pertanyaan_kode, revisi_jawaban),
            )
        kon.execute(
            "DELETE FROM kode_tambahan_riset WHERE wawancara_id=? AND pertanyaan_kode=?",
            (wawancara_id, pertanyaan_kode),
        )
        kon.executemany(
            "INSERT INTO kode_tambahan_riset VALUES(?,?,?)",
            ((wawancara_id, pertanyaan_kode, kode) for kode in tambahan),
        )
        diubah = kon.execute(
            "UPDATE wawancara_riset SET revisi=revisi+1,diperbarui=? WHERE id=? AND revisi=?",
            (kini, wawancara_id, revisi_wawancara),
        ).rowcount
        if diubah != 1:
            raise KonflikRiset("wawancara telah berubah")
        _audit(kon, operasi_id, actor_id, "ubah_jawaban", wawancara_id, sidik, kini)


def finalisasi(path, *, actor_id: str, operasi_id: str, wawancara_id: str,
               revisi: int, sekarang: Optional[int] = None) -> None:
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    wawancara_id = _wawancara_id(wawancara_id)
    if type(revisi) is not int or revisi < 1:
        raise ValueError("revisi tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = _sidik_perintah("finalisasi", wawancara_id, {"revisi": revisi})
    with _transaksi(path) as kon:
        if _replay(kon, operasi_id, actor_id, "finalisasi", wawancara_id, sidik):
            return
        wawancara = kon.execute("SELECT * FROM wawancara_riset WHERE id=?", (wawancara_id,)).fetchone()
        if wawancara is None:
            raise LookupError("wawancara tidak tersedia")
        if wawancara["actor_id"] != actor_id or wawancara["status"] not in ("draf", "perlu_redaksi"):
            raise PermissionError("wawancara tidak dapat difinalkan")
        if int(wawancara["revisi"]) != revisi:
            raise KonflikRiset("wawancara telah berubah")
        data_instrumen = _instrument_dari_baris(kon, wawancara)
        wajib = {item["kode"] for item in data_instrumen["pertanyaan"]}
        aktual = {r[0] for r in kon.execute("SELECT pertanyaan_kode FROM jawaban_riset WHERE wawancara_id=?", (wawancara_id,))}
        if aktual != wajib:
            raise ValueError("semua pertanyaan perlu diberi status sebelum finalisasi")
        kon.execute(
            "UPDATE wawancara_riset SET status='final',revisi=revisi+1,diperbarui=?,difinalkan=? "
            "WHERE id=? AND revisi=?",
            (kini, kini, wawancara_id, revisi),
        )
        _audit(kon, operasi_id, actor_id, "finalisasi", wawancara_id, sidik, kini)


def buka_koreksi(path, *, actor_id: str, operasi_id: str, wawancara_id: str,
                  revisi: int, sekarang: Optional[int] = None) -> None:
    _ubah_status(path, actor_id=actor_id, operasi_id=operasi_id, wawancara_id=wawancara_id,
                 revisi=revisi, asal=("final",), tujuan="draf", aksi="buka_koreksi",
                 difinalkan=None, sekarang=sekarang)


def tandai_redaksi(path, *, actor_id: str, operasi_id: str, wawancara_id: str,
                    revisi: int, sekarang: Optional[int] = None) -> None:
    _ubah_status(path, actor_id=actor_id, operasi_id=operasi_id, wawancara_id=wawancara_id,
                 revisi=revisi, asal=("draf", "final"), tujuan="perlu_redaksi",
                 aksi="tandai_redaksi", difinalkan=None, sekarang=sekarang)


def _ubah_status(path, *, actor_id, operasi_id, wawancara_id, revisi, asal, tujuan,
                 aksi, difinalkan, sekarang=None):
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    wawancara_id = _wawancara_id(wawancara_id)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = _sidik_perintah(aksi, wawancara_id, {
        "revisi": revisi, "asal": asal, "tujuan": tujuan,
    })
    with _transaksi(path) as kon:
        if _replay(kon, operasi_id, actor_id, aksi, wawancara_id, sidik):
            return
        baris = kon.execute("SELECT actor_id,status,revisi FROM wawancara_riset WHERE id=?", (wawancara_id,)).fetchone()
        if baris is None:
            raise LookupError("wawancara tidak tersedia")
        if baris["actor_id"] != actor_id or baris["status"] not in asal:
            raise PermissionError("status wawancara tidak dapat diubah")
        if int(baris["revisi"]) != revisi:
            raise KonflikRiset("wawancara telah berubah")
        kon.execute(
            "UPDATE wawancara_riset SET status=?,revisi=revisi+1,diperbarui=?,difinalkan=? WHERE id=? AND revisi=?",
            (tujuan, kini, difinalkan, wawancara_id, revisi),
        )
        _audit(kon, operasi_id, actor_id, aksi, wawancara_id, sidik, kini)


def tarik_consent(path, *, actor_id: str, operasi_id: str, wawancara_id: str,
                   revisi: int, sekarang: Optional[int] = None) -> None:
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    wawancara_id = _wawancara_id(wawancara_id)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = _sidik_perintah("tarik_consent", wawancara_id, {"revisi": revisi})
    with _transaksi(path) as kon:
        if _replay(kon, operasi_id, actor_id, "tarik_consent", wawancara_id, sidik):
            return
        baris = kon.execute("SELECT actor_id,status,revisi FROM wawancara_riset WHERE id=?", (wawancara_id,)).fetchone()
        if baris is None:
            raise LookupError("wawancara tidak tersedia")
        if baris["actor_id"] != actor_id or baris["status"] == "ditarik":
            raise PermissionError("consent tidak dapat ditarik")
        if int(baris["revisi"]) != revisi:
            raise KonflikRiset("wawancara telah berubah")
        kon.execute("DELETE FROM jawaban_riset WHERE wawancara_id=?", (wawancara_id,))
        kon.execute(
            "UPDATE wawancara_riset SET status='ditarik',consent_wawancara=1,consent_rekaman=0,"
            "revisi=revisi+1,diperbarui=?,difinalkan=NULL,retensi_hingga=? WHERE id=? AND revisi=?",
            (kini, kini + 86400, wawancara_id, revisi),
        )
        _audit(kon, operasi_id, actor_id, "tarik_consent", wawancara_id, sidik, kini)


def catat_ekspor(path, *, actor_id: str, operasi_id: str, target_id: str,
                  sekarang: Optional[int] = None) -> None:
    actor_id = _actor(actor_id)
    operasi_id = _operasi_id(operasi_id)
    if target_id != "ekspor_semua":
        target_id = _wawancara_id(target_id)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = _sidik_perintah("ekspor", target_id, {})
    with _transaksi(path) as kon:
        if _replay(kon, operasi_id, actor_id, "ekspor", target_id, sidik):
            return
        if target_id == "ekspor_semua":
            if kon.execute("SELECT 1 FROM wawancara_riset WHERE status='final' LIMIT 1").fetchone() is None:
                raise LookupError("wawancara final tidak tersedia")
        elif kon.execute("SELECT 1 FROM wawancara_riset WHERE id=? AND status='final'", (target_id,)).fetchone() is None:
            raise LookupError("wawancara final tidak tersedia")
        _audit(kon, operasi_id, actor_id, "ekspor", target_id, sidik, kini)


def hapus_retensi(path, *, actor_id: str, batas: int = 50,
                   sekarang: Optional[int] = None,
                   buat_operasi: Optional[Callable[[], str]] = None) -> int:
    actor_id = _actor(actor_id)
    if type(batas) is not int or not 1 <= batas <= 100:
        raise ValueError("batas retensi tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    pembuat = buat_operasi or (lambda: "op_" + secrets.token_hex(16))
    with _transaksi(path) as kon:
        target = [r["id"] for r in kon.execute(
            "SELECT id FROM wawancara_riset WHERE status!='ditarik' AND retensi_hingga<=? ORDER BY retensi_hingga,id LIMIT ?",
            (kini, batas),
        )]
        for identitas in target:
            kon.execute("DELETE FROM jawaban_riset WHERE wawancara_id=?", (identitas,))
            kon.execute(
                "UPDATE wawancara_riset SET status='ditarik',consent_rekaman=0,revisi=revisi+1,"
                "diperbarui=?,difinalkan=NULL WHERE id=?", (kini, identitas)
            )
            operasi_id = _operasi_id(pembuat())
            sidik = _sidik_perintah("hapus_retensi", identitas, {"retensi_hingga": kini})
            _audit(kon, operasi_id, actor_id, "hapus_retensi", identitas, sidik, kini)
        return len(target)


def wawancara_final(path=None) -> tuple:
    with buka_baca(path) as kon:
        baris = kon.execute(
            "SELECT w.*,i.kode_versi,i.snapshot_json FROM wawancara_riset w "
            "JOIN instrumen_riset i ON i.id=w.instrumen_id WHERE w.status='final' "
            "ORDER BY w.diwawancarai,w.id"
        ).fetchall()
        hasil = []
        for waw in baris:
            data_instrumen = instrumen.muat_json(waw["snapshot_json"])
            labels = instrumen.label_kode(data_instrumen)
            jawaban = {}
            for jaw in kon.execute("SELECT * FROM jawaban_riset WHERE wawancara_id=? ORDER BY pertanyaan_kode", (waw["id"],)):
                item = dict(jaw)
                tambahan = [r[0] for r in kon.execute(
                    "SELECT kode FROM kode_tambahan_riset WHERE wawancara_id=? AND pertanyaan_kode=? ORDER BY kode",
                    (waw["id"], jaw["pertanyaan_kode"]),
                )]
                item["kode_label"] = tuple(labels[k] for k in ([jaw["kode_utama"]] if jaw["kode_utama"] else []) + tambahan)
                jawaban[jaw["pertanyaan_kode"]] = item
            item_waw = dict(waw)
            item_waw.pop("snapshot_json", None)
            item_waw["jawaban"] = jawaban
            hasil.append(item_waw)
        return tuple(hasil)
