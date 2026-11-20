"""Override peta kurikulum dari admin: DB SQLite terpisah (`kurikulum.db`, skema v1).

Dua hal bisa diubah admin tanpa rilis kode: pemetaan CP per grup katalog
(`kurikulum_cp.CP_PER_GRUP`) dan label awam per topik (`kurikulum_katalog.label_awam`).
Nilai di kode adalah bawaan; baris DB hanya menimpanya. DB baru dibuat saat tulis:
membaca (mode=ro) tidak pernah membuat berkas.

BEDA dari `feature_switch` (sengaja): sakelar fail-closed karena nilai salah bisa
menyalakan fitur; di sini bawaan dari kode adalah nilai yang SAH, jadi kegagalan baca
(berkas tidak ada, bukan sqlite, user_version tak dikenal, tabel hilang, baris rusak)
jatuh ke bawaan dan dicatat lewat `logging` (tanpa isi), bukan memblokir halaman.
Baris tak sah diabaikan satu per satu; baris lain tetap berlaku. Sebaliknya TULIS
ke DB berskema asing ditolak (`GalatKurikulum`) agar tidak menimpa berkas orang lain.

Konkurensi: tulis dalam satu transaksi `BEGIN IMMEDIATE` (cek skema, cek revisi,
ubah, audit). Revisi per kunci naik monoton dan baris tidak pernah dihapus ("kembalikan
ke bawaan" = nilai NULL + revisi naik), sehingga konflik tidak tertipu kasus ABA.
Nilai efektif yang sama dengan sekarang = no-op tanpa revisi/audit. Hasil baca dicache
pendek (TTL_DETIK) per path absolut dan dikosongkan `bersihkan_cache()` setelah tulis.

Hanya mengimpor stdlib + `kurikulum_cp` + `kurikulum_katalog`; tidak boleh diimpor
modul inti soal (`generator` dan penutupan impornya).
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Dict, List, Optional, Tuple
import unicodedata

import kurikulum_cp
import kurikulum_katalog

BERKAS_BAWAAN = "/data/kurikulum.db"
ENV_BERKAS_DB = "KURIKULUM_BERKAS_DB"
VERSI_SKEMA = 1
TTL_DETIK = 5

MAKS_PASANGAN_CP = 12
MAKS_LABEL = 40
MAKS_PELAKU = 100
SUMBER_BAWAAN = "bawaan"
SUMBER_ADMIN = "admin"
TABEL_SKEMA = ("cp_grup", "label_awam", "audit_kurikulum")

_DDL_CP = (
    "CREATE TABLE IF NOT EXISTS cp_grup (\n"
    "    topik_id TEXT NOT NULL,\n"
    "    grup_kode TEXT NOT NULL,\n"
    "    isi_json TEXT,\n"
    "    revisi INTEGER NOT NULL CHECK (revisi >= 1),\n"
    "    diperbarui TEXT NOT NULL,\n"
    "    PRIMARY KEY (topik_id, grup_kode)\n"
    ")"
)
_DDL_LABEL = (
    "CREATE TABLE IF NOT EXISTS label_awam (\n"
    "    topik_id TEXT PRIMARY KEY,\n"
    "    label TEXT,\n"
    "    revisi INTEGER NOT NULL CHECK (revisi >= 1),\n"
    "    diperbarui TEXT NOT NULL\n"
    ")"
)
_DDL_AUDIT = (
    "CREATE TABLE IF NOT EXISTS audit_kurikulum (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    jenis TEXT NOT NULL CHECK (jenis IN ('cp', 'label')),\n"
    "    kunci TEXT NOT NULL,\n"
    "    lama TEXT,\n"
    "    baru TEXT,\n"
    "    revisi INTEGER NOT NULL,\n"
    "    actor_id TEXT NOT NULL,\n"
    "    dibuat TEXT NOT NULL\n"
    ")"
)

_log = logging.getLogger(__name__)
# Jam disuntik lewat variabel modul agar tes bisa memalsukan TTL cache.
_jam = time.monotonic
_kunci_cache = threading.Lock()
_cache = {}

IsiCP = Tuple[Tuple[str, str], ...]
KunciCP = Tuple[str, str]


class KonflikRevisi(Exception):
    """revisi_diharapkan tidak cocok dengan revisi baris sekarang."""


class GalatKurikulum(Exception):
    """DB kurikulum tak dapat ditulis atau skemanya tak dikenali; jangan ditelan admin."""


@dataclass(frozen=True)
class ItemCP:
    """Pemetaan CP satu grup: nilai efektif, bawaan, sumber, dan revisi barisnya."""

    topik_id: str
    grup_kode: str
    efektif: IsiCP
    bawaan: IsiCP
    sumber: str
    revisi: int
    diperbarui: Optional[str]


@dataclass(frozen=True)
class ItemLabel:
    """Label awam satu topik: nilai efektif, bawaan, sumber, dan revisi barisnya."""

    topik_id: str
    efektif: str
    bawaan: str
    sumber: str
    revisi: int
    diperbarui: Optional[str]


@dataclass(frozen=True)
class _Keadaan:
    cp: Tuple[ItemCP, ...]
    label: Tuple[ItemLabel, ...]


def bersihkan_cache() -> None:
    """Kosongkan cache hasil baca; dipanggil setelah tulis berhasil."""
    with _kunci_cache:
        _cache.clear()


def _path_db(path):
    """Tujuan DB: parameter, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- bawaan dari kode -------------------------------------------------------

def _cp_bawaan() -> Dict[KunciCP, IsiCP]:
    return {kunci: tuple(isi) for kunci, isi in kurikulum_cp.CP_PER_GRUP.items()}


def _label_bawaan() -> Dict[str, str]:
    return dict(kurikulum_katalog.label_awam())


# --- validasi ---------------------------------------------------------------

def _periksa_pelaku(actor_id) -> None:
    if (not isinstance(actor_id, str) or not actor_id.strip()
            or len(actor_id) > MAKS_PELAKU):
        raise ValueError("Identitas pelaku ubah kurikulum tidak sah.")


def _periksa_revisi(revisi_diharapkan) -> None:
    if (not isinstance(revisi_diharapkan, int) or isinstance(revisi_diharapkan, bool)
            or revisi_diharapkan < 0):
        raise ValueError("Revisi yang diharapkan harus bilangan bulat tak negatif.")


def _periksa_kunci_cp(topik_id, grup_kode) -> KunciCP:
    kunci = (topik_id, grup_kode)
    if kunci not in kurikulum_cp.CP_PER_GRUP:
        raise ValueError(f"Grup katalog tidak dikenal: {topik_id!r}/{grup_kode!r}.")
    return kunci


def _periksa_topik_berlabel(topik_id) -> None:
    if topik_id not in _label_bawaan():
        raise ValueError(f"Topik tidak punya label awam bawaan: {topik_id!r}.")


def _urutan_capaian() -> Dict[str, int]:
    return {butir.id: no for no, butir in enumerate(kurikulum_cp.CAPAIAN)}


def _normalkan_isi_cp(isi) -> IsiCP:
    """Validasi isi CP, hasilnya urut sesuai `CAPAIAN`; ValueError berbahasa Indonesia."""
    if not isinstance(isi, (tuple, list)):
        raise ValueError("Isi CP harus berupa daftar pasangan (capaian, kecocokan).")
    if len(isi) > MAKS_PASANGAN_CP:
        raise ValueError(f"Isi CP maksimal {MAKS_PASANGAN_CP} butir.")
    urutan = _urutan_capaian()
    terlihat = set()
    for pasangan in isi:
        if (not isinstance(pasangan, (tuple, list)) or len(pasangan) != 2
                or not all(isinstance(bagian, str) for bagian in pasangan)):
            raise ValueError("Tiap butir CP harus pasangan (capaian, kecocokan) berupa teks.")
        capaian_id, kecocokan = pasangan
        if capaian_id not in urutan:
            raise ValueError(f"Butir capaian tidak dikenal: {capaian_id!r}.")
        if kecocokan not in kurikulum_cp.KECOCOKAN:
            raise ValueError(f"Tingkat kecocokan tidak dikenal: {kecocokan!r}.")
        if capaian_id in terlihat:
            raise ValueError(f"Butir capaian ganda: {capaian_id!r}.")
        terlihat.add(capaian_id)
    return tuple(sorted(((c, k) for c, k in isi), key=lambda p: urutan[p[0]]))


def _cp_ke_json(isi: IsiCP) -> str:
    return json.dumps([list(pasangan) for pasangan in isi], ensure_ascii=False)


def _cp_dari_json(teks) -> IsiCP:
    """Urai isi_json DB; ValueError bila bukan JSON sah atau isinya tak lolos validasi."""
    if not isinstance(teks, str):
        raise ValueError("isi_json bukan teks.")
    try:
        isi = json.loads(teks)
    except ValueError as err:
        raise ValueError("isi_json bukan JSON sah.") from err
    return _normalkan_isi_cp(isi)


def _normalkan_format_label(label) -> str:
    """Validasi bentuk label (tanpa cek unik): str, strip, 1-40 karakter, tanpa kontrol."""
    if not isinstance(label, str):
        raise ValueError("Label awam harus berupa teks.")
    bersih = label.strip()
    if not 1 <= len(bersih) <= MAKS_LABEL:
        raise ValueError(f"Label awam harus 1-{MAKS_LABEL} karakter.")
    if any(unicodedata.category(huruf).startswith("C") for huruf in bersih):
        raise ValueError("Label awam tidak boleh memuat karakter kontrol.")
    return bersih


def _kunci_unik(label: str) -> str:
    return unicodedata.normalize("NFKC", label).casefold()


def _periksa_label_unik(topik_id: str, label: str, efektif: Dict[str, str]) -> None:
    unik = _kunci_unik(label)
    for lain, nilai in efektif.items():
        if lain != topik_id and _kunci_unik(nilai) == unik:
            raise ValueError("Label awam sudah dipakai topik lain.")


# --- penyusunan keadaan dari baris DB (murni) --------------------------------

def _item_cp(kunci: KunciCP, bawaan: IsiCP, baris) -> ItemCP:
    topik_id, grup_kode = kunci
    if baris is None:
        return ItemCP(topik_id, grup_kode, bawaan, bawaan, SUMBER_BAWAAN, 0, None)
    isi_json, revisi, diperbarui = baris
    efektif = bawaan
    if isi_json is not None:
        try:
            efektif = _cp_dari_json(isi_json)
        except ValueError:
            _log.warning("Override CP %s/%s tidak sah, memakai bawaan.", topik_id, grup_kode)
            efektif = bawaan
    sumber = SUMBER_BAWAAN if efektif == bawaan else SUMBER_ADMIN
    return ItemCP(topik_id, grup_kode, efektif, bawaan, sumber, revisi, diperbarui)


def _label_valid_per_topik(baris_label, bawaan) -> Dict[str, str]:
    """Override label yang lolos validasi bentuk, per topik berlabel bawaan."""
    valid = {}
    for topik_id, (label, _, _) in baris_label.items():
        if topik_id not in bawaan:
            _log.warning("Baris label untuk topik tak dikenal %s diabaikan.", topik_id)
            continue
        if label is None:
            continue
        try:
            valid[topik_id] = _normalkan_format_label(label)
        except ValueError:
            _log.warning("Override label topik %s tidak sah, memakai bawaan.", topik_id)
    return valid


def _label_efektif_tanpa_duplikat(bawaan: Dict[str, str], valid: Dict[str, str]) -> Dict[str, str]:
    """Efektif = bawaan + override; override yang bentrok (casefold) dibuang sampai unik."""
    sisa = dict(valid)
    while True:
        efektif = {topik: sisa.get(topik, nilai) for topik, nilai in bawaan.items()}
        per_unik: Dict[str, List[str]] = {}
        for topik, nilai in efektif.items():
            per_unik.setdefault(_kunci_unik(nilai), []).append(topik)
        bentrok = {t for grup in per_unik.values() if len(grup) > 1 for t in grup if t in sisa}
        if not bentrok:
            return efektif
        for topik in sorted(bentrok):
            _log.warning("Override label topik %s bentrok dengan topik lain, memakai bawaan.", topik)
            del sisa[topik]


def _susun_keadaan(baris_cp, baris_label) -> _Keadaan:
    cp_bawaan = _cp_bawaan()
    for kunci in baris_cp:
        if kunci not in cp_bawaan:
            _log.warning("Baris CP untuk grup tak dikenal %s/%s diabaikan.", *kunci)
    item_cp = tuple(_item_cp(k, isi, baris_cp.get(k)) for k, isi in cp_bawaan.items())
    bawaan = _label_bawaan()
    efektif = _label_efektif_tanpa_duplikat(bawaan, _label_valid_per_topik(baris_label, bawaan))
    item_label = []
    for topik_id, nilai_bawaan in bawaan.items():
        baris = baris_label.get(topik_id)
        revisi, diperbarui = (0, None) if baris is None else (baris[1], baris[2])
        sumber = SUMBER_BAWAAN if efektif[topik_id] == nilai_bawaan else SUMBER_ADMIN
        item_label.append(ItemLabel(
            topik_id, efektif[topik_id], nilai_bawaan, sumber, revisi, diperbarui))
    return _Keadaan(item_cp, tuple(item_label))


def _keadaan_bawaan() -> _Keadaan:
    return _susun_keadaan({}, {})


def _ke_revisi(nilai) -> Optional[int]:
    if isinstance(nilai, int) and not isinstance(nilai, bool) and nilai >= 1:
        return nilai
    return None


def _muat_baris(kon):
    """Baca semua baris override dari koneksi; baris dengan revisi tak sah dilewati."""
    baris_cp, baris_label = {}, {}
    for b in kon.execute("SELECT topik_id, grup_kode, isi_json, revisi, diperbarui FROM cp_grup"):
        revisi = _ke_revisi(b["revisi"])
        if revisi is None:
            _log.warning("Baris CP %s/%s berrevisi tak sah diabaikan.", b["topik_id"], b["grup_kode"])
            continue
        baris_cp[(b["topik_id"], b["grup_kode"])] = (b["isi_json"], revisi, b["diperbarui"])
    for b in kon.execute("SELECT topik_id, label, revisi, diperbarui FROM label_awam"):
        revisi = _ke_revisi(b["revisi"])
        if revisi is None:
            _log.warning("Baris label %s berrevisi tak sah diabaikan.", b["topik_id"])
            continue
        baris_label[b["topik_id"]] = (b["label"], revisi, b["diperbarui"])
    return baris_cp, baris_label


# --- baca -------------------------------------------------------------------

def _baca_db(tujuan: Path) -> _Keadaan:
    with closing(sqlite3.connect(f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
        kon.row_factory = sqlite3.Row
        if kon.execute("PRAGMA user_version").fetchone()[0] != VERSI_SKEMA:
            raise GalatKurikulum("Skema DB kurikulum tidak dikenali.")
        return _susun_keadaan(*_muat_baris(kon))


def _muat(path) -> _Keadaan:
    """Keadaan efektif; kegagalan apa pun jatuh ke bawaan (lihat docstring modul)."""
    tujuan = _path_db(path)
    kunci = os.path.abspath(str(tujuan))
    with _kunci_cache:
        entri = _cache.get(kunci)
    if entri is not None and _jam() - entri[1] < TTL_DETIK:
        return entri[0]
    try:
        if not tujuan.exists():
            return _keadaan_bawaan()
        keadaan = _baca_db(tujuan)
    except (sqlite3.Error, GalatKurikulum, OSError) as err:
        _log.warning("DB kurikulum tak terbaca (%s), memakai bawaan.", type(err).__name__)
        keadaan = _keadaan_bawaan()
    with _kunci_cache:
        _cache[kunci] = (keadaan, _jam())
    return keadaan


def daftar_cp(*, path=None) -> Tuple[ItemCP, ...]:
    """Satu ItemCP per grup katalog, urut bawaan."""
    return _muat(path).cp


def daftar_label(*, path=None) -> Tuple[ItemLabel, ...]:
    """Satu ItemLabel per topik berlabel bawaan, urut bawaan."""
    return _muat(path).label


def cp_efektif(*, path=None) -> Dict[KunciCP, IsiCP]:
    """Peta (topik_id, grup_kode) -> butir CP efektif; salinan baru tiap panggilan."""
    return {(i.topik_id, i.grup_kode): i.efektif for i in daftar_cp(path=path)}


def label_efektif(*, path=None) -> Dict[str, str]:
    """Peta topik_id -> label awam efektif; salinan baru tiap panggilan."""
    return {i.topik_id: i.efektif for i in daftar_label(path=path)}


# --- tulis ------------------------------------------------------------------

def _buat_skema(kon) -> None:
    for ddl in (_DDL_CP, _DDL_LABEL, _DDL_AUDIT):
        kon.execute(ddl)


def _periksa_skema_tulis(kon) -> None:
    """Dalam transaksi: terima DB kosong (v0 tanpa tabel) atau v1; selain itu tolak."""
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi not in (0, VERSI_SKEMA):
        raise GalatKurikulum("Skema DB kurikulum tidak dikenali.")
    if versi == 0:
        if kon.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
            raise GalatKurikulum("DB kurikulum bukan milik aplikasi ini.")
    _buat_skema(kon)
    if versi == 0:
        kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _buat_berkas_privat(tujuan: Path) -> None:
    descriptor = os.open(str(tujuan), os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)


def _jalankan_tulis(path, aksi):
    """Satu transaksi BEGIN IMMEDIATE: cek skema, jalankan aksi(kon), commit, bersihkan cache."""
    tujuan = _path_db(path)
    try:
        if not tujuan.exists():
            _buat_berkas_privat(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=5.0)) as kon, kon:
            kon.row_factory = sqlite3.Row
            kon.execute("BEGIN IMMEDIATE")
            _periksa_skema_tulis(kon)
            hasil = aksi(kon)
    except (sqlite3.Error, OSError) as err:
        raise GalatKurikulum("DB kurikulum tidak dapat diubah.") from err
    bersihkan_cache()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass
    return hasil


def _konflik(deskripsi: str, diharapkan: int, kini: int) -> KonflikRevisi:
    return KonflikRevisi(
        f"Revisi {deskripsi} berubah: diharapkan {diharapkan}, sekarang {kini}.")


def _revisi_baris(kon, sql: str, parameter, deskripsi: str, revisi_diharapkan: int) -> int:
    """Revisi baris sekarang (0 bila belum ada); KonflikRevisi bila beda dari harapan."""
    baris = kon.execute(sql, parameter).fetchone()
    if baris is None:
        revisi_kini = 0
    else:
        revisi_kini = _ke_revisi(baris["revisi"])
        if revisi_kini is None:
            raise GalatKurikulum("Baris kurikulum rusak: revisi tidak terbaca.")
    if revisi_kini != revisi_diharapkan:
        raise _konflik(deskripsi, revisi_diharapkan, revisi_kini)
    return revisi_kini


def _catat_audit(kon, jenis, kunci, lama, baru, revisi, actor_id, dibuat) -> None:
    kon.execute(
        "INSERT INTO audit_kurikulum(jenis, kunci, lama, baru, revisi, actor_id, dibuat)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (jenis, kunci, lama, baru, revisi, actor_id, dibuat),
    )


def _tulis_cp(kunci: KunciCP, baru: Optional[IsiCP], actor_id, revisi_diharapkan, path) -> ItemCP:
    """baru None = kembali ke bawaan. Isi yang sama dengan bawaan disimpan sebagai NULL."""
    topik_id, grup_kode = kunci
    if not _path_db(path).exists():
        # Berkas belum ada: keadaan pasti bawaan. Tolak/no-op tanpa membuat berkas.
        if revisi_diharapkan != 0:
            raise _konflik(f"CP {topik_id}/{grup_kode}", revisi_diharapkan, 0)
        sekarang = next(i for i in _keadaan_bawaan().cp if (i.topik_id, i.grup_kode) == kunci)
        if baru is None or baru == sekarang.efektif:
            return sekarang

    def aksi(kon):
        revisi_kini = _revisi_baris(
            kon, "SELECT revisi FROM cp_grup WHERE topik_id = ? AND grup_kode = ?",
            kunci, f"CP {topik_id}/{grup_kode}", revisi_diharapkan)
        sekarang = next(i for i in _susun_keadaan(*_muat_baris(kon)).cp
                        if (i.topik_id, i.grup_kode) == kunci)
        target = sekarang.bawaan if baru is None else baru
        if target == sekarang.efektif:
            return sekarang
        revisi_baru, kini = revisi_kini + 1, _utc_iso()
        tersimpan = None if target == sekarang.bawaan else _cp_ke_json(target)
        if revisi_kini == 0:
            kon.execute("INSERT INTO cp_grup(topik_id, grup_kode, isi_json, revisi, diperbarui)"
                        " VALUES (?, ?, ?, ?, ?)", (topik_id, grup_kode, tersimpan, revisi_baru, kini))
        else:
            kon.execute("UPDATE cp_grup SET isi_json = ?, revisi = ?, diperbarui = ?"
                        " WHERE topik_id = ? AND grup_kode = ?",
                        (tersimpan, revisi_baru, kini, topik_id, grup_kode))
        _catat_audit(kon, "cp", f"{topik_id}/{grup_kode}", _cp_ke_json(sekarang.efektif),
                     _cp_ke_json(target), revisi_baru, actor_id, kini)
        sumber = SUMBER_BAWAAN if tersimpan is None else SUMBER_ADMIN
        return ItemCP(topik_id, grup_kode, target, sekarang.bawaan, sumber, revisi_baru, kini)

    return _jalankan_tulis(path, aksi)


def _tulis_label(topik_id: str, baru: Optional[str], actor_id, revisi_diharapkan, path) -> ItemLabel:
    """baru None = kembali ke bawaan. Keunikan dicek di dalam transaksi, terhadap keadaan saat itu."""
    if not _path_db(path).exists():
        # Berkas belum ada: keadaan pasti bawaan. Tolak/no-op tanpa membuat berkas.
        if revisi_diharapkan != 0:
            raise _konflik(f"label {topik_id}", revisi_diharapkan, 0)
        sekarang = next(i for i in _keadaan_bawaan().label if i.topik_id == topik_id)
        _periksa_label_unik(topik_id, sekarang.bawaan if baru is None else baru, _label_bawaan())
        if baru is None or baru == sekarang.efektif:
            return sekarang

    def aksi(kon):
        revisi_kini = _revisi_baris(
            kon, "SELECT revisi FROM label_awam WHERE topik_id = ?",
            (topik_id,), f"label {topik_id}", revisi_diharapkan)
        keadaan = _susun_keadaan(*_muat_baris(kon))
        sekarang = next(i for i in keadaan.label if i.topik_id == topik_id)
        target = sekarang.bawaan if baru is None else baru
        _periksa_label_unik(topik_id, target, {i.topik_id: i.efektif for i in keadaan.label})
        if target == sekarang.efektif:
            return sekarang
        revisi_baru, kini = revisi_kini + 1, _utc_iso()
        tersimpan = None if target == sekarang.bawaan else target
        if revisi_kini == 0:
            kon.execute("INSERT INTO label_awam(topik_id, label, revisi, diperbarui)"
                        " VALUES (?, ?, ?, ?)", (topik_id, tersimpan, revisi_baru, kini))
        else:
            kon.execute("UPDATE label_awam SET label = ?, revisi = ?, diperbarui = ?"
                        " WHERE topik_id = ?", (tersimpan, revisi_baru, kini, topik_id))
        _catat_audit(kon, "label", topik_id, json.dumps(sekarang.efektif, ensure_ascii=False),
                     json.dumps(target, ensure_ascii=False), revisi_baru, actor_id, kini)
        sumber = SUMBER_BAWAAN if tersimpan is None else SUMBER_ADMIN
        return ItemLabel(topik_id, target, sekarang.bawaan, sumber, revisi_baru, kini)

    return _jalankan_tulis(path, aksi)


def ubah_cp(topik_id, grup_kode, isi, *, actor_id, revisi_diharapkan, path=None) -> ItemCP:
    """Ganti pemetaan CP satu grup (tuple kosong = di luar CP). Mengembalikan ItemCP baru.

    ValueError untuk masukan tak sah (sebelum menyentuh DB); KonflikRevisi bila revisi
    berubah; GalatKurikulum bila DB berskema asing. Nilai efektif sama = no-op.
    """
    kunci = _periksa_kunci_cp(topik_id, grup_kode)
    baru = _normalkan_isi_cp(isi)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)
    return _tulis_cp(kunci, baru, actor_id, revisi_diharapkan, path)


def kembalikan_cp(topik_id, grup_kode, *, actor_id, revisi_diharapkan, path=None) -> ItemCP:
    """Kembalikan pemetaan CP satu grup ke bawaan kode (revisi tetap naik, tercatat di audit)."""
    kunci = _periksa_kunci_cp(topik_id, grup_kode)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)
    return _tulis_cp(kunci, None, actor_id, revisi_diharapkan, path)


def ubah_label(topik_id, label, *, actor_id, revisi_diharapkan, path=None) -> ItemLabel:
    """Ganti label awam satu topik; unik (casefold) terhadap label efektif topik lain."""
    _periksa_topik_berlabel(topik_id)
    baru = _normalkan_format_label(label)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)
    return _tulis_label(topik_id, baru, actor_id, revisi_diharapkan, path)


def kembalikan_label(topik_id, *, actor_id, revisi_diharapkan, path=None) -> ItemLabel:
    """Kembalikan label awam ke bawaan kode; ValueError bila bentrok dengan label topik lain."""
    _periksa_topik_berlabel(topik_id)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)
    return _tulis_label(topik_id, None, actor_id, revisi_diharapkan, path)
