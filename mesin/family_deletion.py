"""Primitive domain penghapusan seluruh keluarga yang fail-closed.

Primitive tidak merangkai ``hapus_akun_guru``. Eksekusi hanya mengubah salinan
bundle coherent yang sudah divalidasi; hasilnya adalah bundle kandidat privat
untuk cutover terkontrol. Bukti belajar, receipt, journal, dan ledger immutable
tetap byte-value utuh. Identitas aktif diputus lewat pseudonim operasi.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Tuple

import admin_accounts
import admin_backup
import admin_contracts as c
import admin_registration
import admin_service
import admin_store
import ai_store
import assistant_schema
import auth
import database


MATRIS_RETENSI = (
    ("akun login, sesi login, profil aktif, lampiran, chat, memori, persetujuan", "hapus"),
    ("jawaban/diagnosis aktif dan mapping analitik opsional", "hapus"),
    ("bukti belajar serta arsip pengiriman append-only", "anonimkan"),
    ("receipt/journal operasi dan ledger layanan/finansial immutable", "pertahankan"),
    ("konfigurasi global dan agregat tanpa mapping keluarga", "pertahankan"),
)


class PenghapusanDitolak(RuntimeError):
    """Precondition penghapusan belum aman atau state berubah."""


@dataclass(frozen=True)
class InventarisKeluarga:
    target_id: str
    target_revisi: int
    jumlah_profil: int
    jumlah_sesi: int
    jumlah_sesi_berbukti: int
    jumlah_lampiran: int
    jumlah_chat: int
    jumlah_ledger_layanan: int
    jumlah_analitik: int
    sidik: str
    matriks: Tuple[Tuple[str, str], ...] = MATRIS_RETENSI


@dataclass(frozen=True)
class HasilPenghapusan:
    operasi_id: str
    status: str
    bundle_hasil: str
    pseudonim: str
    inventaris_sidik: str
    backup_id: str
    baru_dieksekusi: bool
    sesi_dicabut: int = 0


def _tabel(kon, nama: str) -> bool:
    return kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nama,)
    ).fetchone() is not None


def _hitung(kon, sql: str, arg=()) -> int:
    return int(kon.execute(sql, arg).fetchone()[0])


def _target(path_auth, target_id: str):
    cocok = [a for a in auth.muat_akun(Path(path_auth)) if a.get("id_akun") == target_id]
    if len(cocok) != 1 or cocok[0].get("peran", "guru") != "guru":
        raise PenghapusanDitolak("keluarga tidak tersedia")
    return cocok[0]


def _sidik(nilai) -> str:
    return hashlib.sha256(json.dumps(
        nilai, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()


def _jumlah_admin(kon, target_id: str) -> tuple[int, int]:
    ledger = 0
    for tabel in (
        "langganan_enrollment", "langganan_cakupan", "langganan_invoice",
        "langganan_receipt", "langganan_grant", "paket_akun", "paket_invoice",
        "paket_receipt", "paket_grant", "kuota_pendamping_jendela",
        "kuota_pendamping_operasi", "penutupan_tagihan",
    ):
        if _tabel(kon, tabel):
            ledger += _hitung(
                kon, 'SELECT COUNT(*) FROM "%s" WHERE akun_id=?' % tabel,
                (target_id,),
            )
    analitik = (
        _hitung(kon, "SELECT COUNT(*) FROM kpi_peserta WHERE akun_id=?", (target_id,))
        if _tabel(kon, "kpi_peserta") else 0
    )
    return ledger, analitik


def preview(path_belajar, path_auth, path_admin, path_ai, path_pendamping,
            *, target_id: str) -> InventarisKeluarga:
    """Inventaris agregat lintas empat DB + auth, tanpa menyalin isi keluarga."""
    target = _target(path_auth, target_id)
    pemilik = target["pengguna"]
    uri = Path(path_belajar).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as kon:
        profil = _hitung(kon, "SELECT COUNT(*) FROM siswa WHERE pemilik=?", (pemilik,))
        sesi = _hitung(kon, "SELECT COUNT(*) FROM sesi s JOIN siswa w ON w.id=s.siswa_id WHERE w.pemilik=?", (pemilik,))
        berbukti = _hitung(kon, "SELECT COUNT(DISTINCT kh.sesi_id) FROM konfirmasi_hasil kh JOIN sesi s ON s.id=kh.sesi_id JOIN siswa w ON w.id=s.siswa_id WHERE w.pemilik=?", (pemilik,))
        lampiran = _hitung(kon, "SELECT COUNT(*) FROM lampiran l JOIN sesi s ON s.id=l.sesi_id JOIN siswa w ON w.id=s.siswa_id WHERE w.pemilik=?", (pemilik,))
    with assistant_schema.buka(path_pendamping) as kon:
        chat = _hitung(kon, "SELECT COUNT(*) FROM chat WHERE account_id=?", (target_id,))
    with admin_store.buka_baca(path_admin) as kon:
        ledger_admin, analitik = _jumlah_admin(kon, target_id)
    with ai_store.buka(path_ai) as kon:
        ledger_ai = _hitung(kon, "SELECT COUNT(*) FROM ledger WHERE bucket_akun=?", (pemilik,))
    nilai = (target_id, auth.revisi_auth(target), profil, sesi, berbukti,
             lampiran, chat, ledger_admin + ledger_ai, analitik)
    return InventarisKeluarga(*nilai, _sidik(nilai))


def _pseudonim(perintah: c.PerintahHapusKeluarga) -> str:
    return "keluarga_dihapus_" + hashlib.sha256(
        (perintah.operasi_id + ":" + perintah.target_id).encode("ascii")
    ).hexdigest()[:24]


def _copy_live(paths, tujuan: Path) -> dict:
    """Salin state live setelah backup exact lolos; caller produksi wajib write-hold."""
    nama = admin_backup.BERKAS_WAJIB
    sumber = {
        "belajar": Path(paths["belajar"]), "auth": Path(paths["auth"]),
        "admin": Path(paths["admin"]), "ai": Path(paths["ai"]),
        "pendamping": Path(paths["pendamping"]),
    }
    hasil = {}
    for jenis, asal in sumber.items():
        dst = tujuan / nama[jenis]
        if jenis == "auth":
            dst.write_bytes(asal.read_bytes())
        else:
            src = sqlite3.connect(asal.resolve().as_uri() + "?mode=ro", uri=True)
            out = sqlite3.connect(str(dst))
            try:
                src.backup(out)
            finally:
                out.close(); src.close()
            for akhiran in ("-wal", "-shm"):
                samping = dst.with_name(dst.name + akhiran)
                if samping.exists():
                    samping.unlink()
        dst.chmod(0o600)
        hasil[jenis] = dst
    return hasil


def _arsip_belajar(kon, siswa_ids) -> set[int]:
    if not siswa_ids:
        return set()
    q = ",".join("?" for _ in siswa_ids)
    hasil = {
        int(r[0]) for r in kon.execute(
            "SELECT DISTINCT kh.sesi_id FROM konfirmasi_hasil kh JOIN sesi s ON s.id=kh.sesi_id WHERE s.siswa_id IN (%s)" % q,
            siswa_ids,
        )
    }
    hasil.update(int(r[0]) for r in kon.execute(
        "SELECT DISTINCT sesi_id FROM kejadian_belajar WHERE siswa_id IN (%s) AND sesi_id IS NOT NULL" % q,
        siswa_ids,
    ))
    hasil.update(int(r[0]) for r in kon.execute(
        "SELECT DISTINCT bf.sesi_id FROM bukti_fokus bf JOIN sesi s ON s.id=bf.sesi_id WHERE s.siswa_id IN (%s)" % q,
        siswa_ids,
    ))
    return hasil


def _ubah_belajar(path, pemilik: str, target_id: str, pseudonim: str):
    with database.buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        siswa_ids = tuple(int(r[0]) for r in kon.execute(
            "SELECT id FROM siswa WHERE pemilik=?", (pemilik,)))
        terlindungi = _arsip_belajar(kon, siswa_ids)
        sesi_ids = tuple(int(r[0]) for r in kon.execute(
            "SELECT id FROM sesi WHERE siswa_id IN (%s)" % (
                ",".join("?" for _ in siswa_ids) or "NULL"), siswa_ids))
        for sesi_id in sesi_ids:
            if sesi_id not in terlindungi:
                database.hapus_sesi(kon, sesi_id)
        if siswa_ids:
            q = ",".join("?" for _ in siswa_ids)
            # Data aktif pada sesi terlindungi dibersihkan; snapshot/arsip tetap.
            kon.execute("DELETE FROM diagnosis WHERE jawaban_id IN (SELECT j.id FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id JOIN sesi s ON s.id=ss.sesi_id WHERE s.siswa_id IN (%s))" % q, siswa_ids)
            kon.execute("DELETE FROM jawaban WHERE sesi_soal_id IN (SELECT ss.id FROM sesi_soal ss JOIN sesi s ON s.id=ss.sesi_id WHERE s.siswa_id IN (%s))" % q, siswa_ids)
            kon.execute("DELETE FROM lampiran WHERE sesi_id IN (SELECT id FROM sesi WHERE siswa_id IN (%s))" % q, siswa_ids)
            if _tabel(kon, "operasi_foto_baca"):
                # Receipt foto durable tidak dihapus; identity link-nya diputus.
                kon.execute("UPDATE operasi_foto_baca SET akun_id=? WHERE akun_id=?",
                            (pseudonim, target_id))
            # Tinjauan aktif boleh dianonimkan. Konfirmasi/snapshot append-only
            # tidak diubah; identitas guru historis tetap bagian ledger bukti.
            kon.execute("UPDATE tinjauan_guru SET guru=? WHERE sesi_soal_id IN (SELECT ss.id FROM sesi_soal ss JOIN sesi s ON s.id=ss.sesi_id WHERE s.siswa_id IN (%s))" % q, (pseudonim, *siswa_ids))
            for urutan, siswa_id in enumerate(siswa_ids, 1):
                kon.execute("UPDATE siswa SET nama=?,pemilik=? WHERE id=?",
                            ("Dihapus-%d" % urutan, pseudonim, siswa_id))
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise PenghapusanDitolak("integritas basis belajar gagal")
        return siswa_ids


def _ubah_pendamping(path, target_id: str):
    with assistant_schema.buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        chats = tuple(r[0] for r in kon.execute(
            "SELECT id FROM chat WHERE account_id=?", (target_id,)))
        for chat_id in chats:
            kon.execute("DELETE FROM tinjauan_usulan WHERE usulan_id IN (SELECT id FROM usulan_latihan WHERE chat_id=?)", (chat_id,))
            kon.execute("DELETE FROM usulan_latihan WHERE chat_id=?", (chat_id,))
            kon.execute("DELETE FROM operasi WHERE chat_id=?", (chat_id,))
            kon.execute("UPDATE memori SET sumber_chat_id=NULL WHERE sumber_chat_id=?", (chat_id,))
            kon.execute("DELETE FROM pesan WHERE chat_id=?", (chat_id,))
            kon.execute("DELETE FROM chat WHERE id=?", (chat_id,))
        for tabel in ("memori", "preferensi_memori", "persetujuan_konteks", "persetujuan"):
            kon.execute('DELETE FROM "%s" WHERE account_id=?' % tabel, (target_id,))
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise PenghapusanDitolak("integritas Pendamping gagal")


def _ubah_ai(path, pemilik: str, pseudonim: str):
    with ai_store.buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        kon.execute("UPDATE ledger SET bucket_akun=? WHERE bucket_akun=?", (pseudonim, pemilik))


def _ubah_admin(path, target_id: str):
    # Ledger/journal immutable dipertahankan utuh. Hanya mapping analitik opsional
    # yang memang berkontrak hard-delete dihapus beserta detail cascade.
    with admin_store._transaksi(path) as kon:
        if _tabel(kon, "kpi_peserta"):
            kon.execute("DELETE FROM kpi_peserta WHERE akun_id=?", (target_id,))


def _ubah_auth(path, perintah: c.PerintahHapusKeluarga, pseudonim: str, siswa_ids):
    from json_storage import transaksi_json
    with transaksi_json(Path(path)) as tujuan:
        mentah, akun, _ = auth._baca_akun_untuk_tulis(tujuan)
        target = next((a for a in akun if a.get("id_akun") == perintah.target_id), None)
        if (target is None or target.get("peran", "guru") != "guru"
                or auth.revisi_auth(target) != perintah.target_revisi):
            raise PenghapusanDitolak("akun target berubah")
        # ID kanonis dipertahankan untuk ledger/receipt, tetapi credential
        # dibuang, nama login dipseudonimkan, revisi naik, dan autentikasi
        # menolak tombstone ``dinonaktifkan``.
        target["pengguna"] = pseudonim
        target.update(auth.buat_hash(hashlib.sha256(pseudonim.encode()).hexdigest()))
        target["revisi_auth"] = perintah.target_revisi + 1
        target["dinonaktifkan"] = True
        akun = [a for a in akun if not (
            a.get("peran") == "murid" and a.get("siswa_id") in set(siswa_ids))]
        hasil = auth._bungkus_akun(mentah, akun)
        for item in hasil.get("registrasi_profil", {}).values():
            if isinstance(item, dict) and item.get("akun_id") == perintah.target_id:
                item["alias_sidik"] = admin_registration._sidik_registrasi(
                    pseudonim.casefold())
                item["kredensial"] = auth.buat_hash(
                    hashlib.sha256((pseudonim + ":intent").encode()).hexdigest())
        auth._tulis_akun_atomik(hasil, tujuan)


def _hitung_sesi(path_sesi, target_id: str) -> int:
    if path_sesi is None:
        return 0
    import sessions
    return sum(item.get("id_akun") == target_id
               for item in sessions.muat(Path(path_sesi)).values())


def cabut_sesi_setelah_cutover(path_sesi, *, target_id: str,
                                receipt_path) -> int:
    """Cabut cookie hanya setelah operator memasang bundle hasil tervalidasi."""
    from json_storage import transaksi_json, tulis_json_atomik
    from sessions import _muat_untuk_tulis
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("status") != "succeeded" or receipt.get("target_sidik") != hashlib.sha256(target_id.encode("ascii")).hexdigest():
        raise PenghapusanDitolak("receipt cutover tidak cocok")
    with transaksi_json(Path(path_sesi)) as tujuan:
        data = _muat_untuk_tulis(tujuan)
        sisa = {token: item for token, item in data.items()
                if item.get("id_akun") != target_id}
        jumlah = len(data) - len(sisa)
        if jumlah:
            tulis_json_atomik(sisa, tujuan)
        return jumlah


def _receipt_path(hasil_root: Path) -> Path:
    return hasil_root / "receipt.json"


def _baca_receipt(bundle_hasil: Path):
    path = _receipt_path(bundle_hasil)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def jalankan(path_belajar, path_auth, path_admin, path_ai, path_pendamping,
             *, bundle, bundle_hasil, perintah: c.PerintahHapusKeluarga,
             sekarang: int, path_sesi=None) -> HasilPenghapusan:
    """Buat bundle hasil privat; sumber aktif tidak pernah ditulis primitive."""
    if not isinstance(perintah, c.PerintahHapusKeluarga):
        raise PenghapusanDitolak("perintah penghapusan keluarga wajib")
    if perintah.verifikasi_independen is not True:
        raise PenghapusanDitolak("verifikasi independen wajib")
    admin_accounts.validasi_actor(path_auth, perintah)
    ringkasan = admin_backup.validasi_bundle(bundle, bundle_id=perintah.backup_id)
    if ringkasan.perlu_rekonsiliasi:
        raise PenghapusanDitolak("backup memiliki operasi yang perlu direkonsiliasi")
    awal = preview(path_belajar, path_auth, path_admin, path_ai, path_pendamping,
                   target_id=perintah.target_id)
    if awal.target_revisi != perintah.target_revisi or awal.sidik != perintah.inventaris_sidik:
        raise PenghapusanDitolak("inventaris berubah; buat preview baru")
    hasil_dir = Path(bundle_hasil)
    lama = _baca_receipt(hasil_dir) if hasil_dir.exists() else None
    target_sidik = hashlib.sha256(perintah.target_id.encode("ascii")).hexdigest()
    if lama is not None:
        cocok = (
            lama.get("operasi_id") == perintah.operasi_id
            and lama.get("target_sidik") == target_sidik
            and lama.get("inventaris_sidik") == perintah.inventaris_sidik
            and lama.get("backup_id") == perintah.backup_id
        )
        if not cocok:
            raise PenghapusanDitolak("operation ID dipakai untuk permintaan berbeda")
        return HasilPenghapusan(perintah.operasi_id, lama["status"],
                                str(hasil_dir / "bundle"), lama["pseudonim"],
                                lama["inventaris_sidik"], lama["backup_id"],
                                False, lama.get("sesi_dicabut", 0))
    if hasil_dir.exists():
        raise PenghapusanDitolak("tujuan bundle hasil tidak kosong")
    pseudonim = _pseudonim(perintah)
    hasil_dir.parent.mkdir(parents=True, exist_ok=True)
    with admin_service.kunci_operasi(path_admin, perintah.operasi_id):
        # Periksa lagi setelah lock: retry yang tadi belum melihat hasil tidak
        # boleh membuat staging kedua atau menganggap direktori sukses sebagai konflik.
        lama = _baca_receipt(hasil_dir) if hasil_dir.exists() else None
        if lama is not None:
            if (lama.get("operasi_id") != perintah.operasi_id
                    or lama.get("target_sidik") != target_sidik
                    or lama.get("inventaris_sidik") != perintah.inventaris_sidik
                    or lama.get("backup_id") != perintah.backup_id):
                raise PenghapusanDitolak("operation ID dipakai untuk permintaan berbeda")
            return HasilPenghapusan(
                perintah.operasi_id, lama["status"], str(hasil_dir / "bundle"),
                lama["pseudonim"], lama["inventaris_sidik"], lama["backup_id"],
                False, lama.get("sesi_dicabut", 0),
            )
        if hasil_dir.exists():
            raise PenghapusanDitolak("tujuan bundle hasil tidak kosong")
        with tempfile.TemporaryDirectory(prefix="jagomat-family-delete-", dir=str(hasil_dir.parent)) as tmp:
            tmp_path = Path(tmp)
            staging = tmp_path / "hasil"
            bundle_baru = staging / "bundle"
            bundle_baru.mkdir(parents=True, mode=0o700)
            paths = _copy_live({
                "belajar": path_belajar, "auth": path_auth,
                "admin": path_admin, "ai": path_ai,
                "pendamping": path_pendamping,
            }, bundle_baru)
            target = _target(paths["auth"], perintah.target_id)
            siswa_ids = _ubah_belajar(
                paths["belajar"], target["pengguna"], perintah.target_id, pseudonim)
            _ubah_pendamping(paths["pendamping"], perintah.target_id)
            _ubah_ai(paths["ai"], target["pengguna"], pseudonim)
            _ubah_admin(paths["admin"], perintah.target_id)
            _ubah_auth(paths["auth"], perintah, pseudonim, siswa_ids)
            for path in paths.values():
                for akhiran in ("-wal", "-shm"):
                    samping = path.with_name(path.name + akhiran)
                    if samping.exists():
                        samping.unlink()
                lock = path.with_name("." + path.name + ".lock")
                if lock.exists():
                    lock.unlink()
            # Bundle sumber tetap pemulihan; hasil adalah kandidat baru yang
            # harus divalidasi/integrity-check sebelum cutover oleh operator.
            output_bundle_id = "hapus-" + perintah.operasi_id
            admin_backup.buat_manifest(
                bundle_baru, bundle_id=output_bundle_id, cutoff=sekarang)
            admin_backup.validasi_bundle(bundle_baru, bundle_id=output_bundle_id)
            sesi_dicabut = _hitung_sesi(path_sesi, perintah.target_id)
            receipt = {
                "versi": 1, "operasi_id": perintah.operasi_id,
                "actor_id": perintah.actor_id, "target_sidik": target_sidik,
                "inventaris_sidik": perintah.inventaris_sidik,
                "backup_id": perintah.backup_id, "pseudonim": pseudonim,
                "status": "succeeded", "dibuat": sekarang,
                "bundle_hasil_id": output_bundle_id,
                "sesi_dicabut": sesi_dicabut,
                "matriks": list(MATRIS_RETENSI),
            }
            _receipt_path(staging).write_text(
                json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            _receipt_path(staging).chmod(0o600)
            os.replace(str(staging), str(hasil_dir))
    return HasilPenghapusan(perintah.operasi_id, "succeeded",
                            str(hasil_dir / "bundle"), pseudonim,
                            perintah.inventaris_sidik, perintah.backup_id,
                            True, sesi_dicabut)
