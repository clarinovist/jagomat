"""Prototipe ledger kuota atomik, belum adapter write aplikasi produksi.

Fungsi berakhiran _kon menerima koneksi DB admin9 yang disiapkan migrator eksternal
DAN pemuat snapshot trusted. Belum ada migrator/path writer/startup admin9: reader,
backup, probe dan recovery existing hanya admin7/8. Jangan memasang DDL atau memakai
writer ini pada data nyata sebelum lifecycle admin9 diintegrasikan dan diuji.

Reservasi berhasil baru adalah satu-satunya izin melanjutkan outbound. Replay
reserved/unknown/completed/released tidak pernah izin outbound kedua. Pemuat sumber
wajib membaca snapshot hak dari koneksi transaksi yang diterima, bukan browser.
Finalisasi sesudah output valid tersimpan; cross-DB crash harus direkonsiliasi lewat
receipt caller, bukan auto-release/auto-finalize dari ledger biaya provider.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import re
import sqlite3

import admin_store
import assistant_entitlement as domain
import assistant_quota_schema as schema
import subscription as lama
import subscription_package_schema as paket_schema
import subscription_package_store as paket_store
import subscription_store as langganan


class KonflikKuota(ValueError):
    """Ikatan atau state operasi berbeda; tidak boleh mengulang jaringan."""


class KuotaDitolak(RuntimeError):
    """Tidak ada hak/kuota terverifikasi pada clock reservasi."""

    def __init__(self, status):
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class IkatanOperasi:
    operasi_id: str
    akun_id: str
    fitur: str
    jendela_id: str
    entitlement_sidik: str


@dataclass(frozen=True)
class Reservasi:
    dibuat_baru: bool
    status: str
    ikatan: IkatanOperasi

    @property
    def boleh_outbound(self):
        return self.dibuat_baru and self.status == "reserved"


def _ikatan(row):
    return IkatanOperasi(*(row[k] for k in (
        "operasi_id", "akun_id", "fitur", "jendela_id", "entitlement_sidik",
    )))


def _validasi_ikatan(ikatan):
    if not isinstance(ikatan, IkatanOperasi):
        raise ValueError("ikatan operasi tidak sah")
    lama.identitas(ikatan.operasi_id, "operasi")
    lama.identitas(ikatan.akun_id, "akun")
    domain.validasi_fitur(ikatan.fitur)
    for nilai in (ikatan.jendela_id, ikatan.entitlement_sidik):
        if type(nilai) is not str or re.fullmatch(r"[0-9a-f]{64}", nilai) is None:
            raise ValueError("sidik kuota tidak sah")


def _pemakaian(kon, akun_id):
    return tuple(domain.Pemakaian(r[0], r[1], r[2], r[3]) for r in kon.execute(
        "SELECT jendela_id,fitur,"
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN status IN ('reserved','unknown') THEN 1 ELSE 0 END) "
        "FROM kuota_pendamping_operasi WHERE akun_id=? GROUP BY jendela_id,fitur",
        (akun_id,),
    ))


def validasi_ledger(kon):
    """Tolak metadata/ikatan/state rusak, bukan menganggap pemakaian nol."""
    schema.validasi(kon)
    if kon.execute('PRAGMA foreign_key_check("kuota_pendamping_operasi")').fetchone():
        raise KonflikKuota("foreign key kuota tidak sah")
    trial_akun = {}
    sumber_akun = {}
    for r in kon.execute("SELECT * FROM kuota_pendamping_jendela"):
        lama.identitas(r["akun_id"], "akun")
        domain.validasi_fitur(r["fitur"])
        for nama in ("entitlement_sidik", "jendela_id"):
            if type(r[nama]) is not str or re.fullmatch(r"[0-9a-f]{64}", r[nama]) is None:
                raise KonflikKuota("sidik jendela tidak sah")
        kunci = (r["akun_id"], r["sumber"], r["sumber_id"])
        if sumber_akun.setdefault(kunci, r["entitlement_sidik"]) != r["entitlement_sidik"]:
            raise KonflikKuota("sumber kuota berubah")
        for nama in ("entitlement_mulai", "entitlement_akhir", "mulai", "akhir"):
            lama.waktu(r[nama])
        if not (r["entitlement_mulai"] <= r["mulai"] < r["akhir"] <= r["entitlement_akhir"]):
            raise KonflikKuota("rentang kuota tidak sah")
        if r["jendela_id"] != domain.sidik((r["entitlement_sidik"], r["mulai"], r["akhir"])):
            raise KonflikKuota("identitas jendela kuota berubah")
        if r["sumber"] == "trial":
            sah = (r["sumber_id"] == "trial" and r["paket"] == "coba_gratis"
                   and r["mulai"] == r["entitlement_mulai"]
                   and r["akhir"] == r["entitlement_akhir"]
                   and r["akhir"] == r["mulai"] + lama.DURASI_TRIAL)
            batas = 10 if r["fitur"] == domain.FITUR[0] else 2
            sidik_trial = domain.sidik((r["akun_id"], "trial", r["mulai"], r["akhir"], 10, 2))
            if (r["entitlement_sidik"] != sidik_trial
                    or trial_akun.setdefault(r["akun_id"], sidik_trial) != sidik_trial):
                raise KonflikKuota("trial akun berubah")
        elif r["sumber"] == "grant_paket":
            lama.identitas(r["sumber_id"], "invoice")
            sah = r["paket"] == "jago_pro"
            batas = 50 if r["fitur"] == domain.FITUR[0] else 5
        else:
            sah, batas = False, -1
        if not sah or r["batas"] != batas:
            raise KonflikKuota("batas/sumber kuota tidak sah")
        jumlah = kon.execute(
            "SELECT COUNT(*) FROM kuota_pendamping_operasi "
            "WHERE akun_id=? AND jendela_id=? AND fitur=? AND status!='released'",
            (r["akun_id"], r["jendela_id"], r["fitur"]),
        ).fetchone()[0]
        if jumlah > batas:
            raise KonflikKuota("pemakaian melebihi kuota")
    for r in kon.execute("SELECT o.*,j.entitlement_sidik AS sidik_jendela,"
                         "j.mulai AS mulai_jendela,j.akhir AS akhir_jendela "
                         "FROM kuota_pendamping_operasi o JOIN kuota_pendamping_jendela j "
                         "ON j.akun_id=o.akun_id AND j.jendela_id=o.jendela_id AND j.fitur=o.fitur"):
        _validasi_ikatan(_ikatan(r))
        lama.waktu(r["dibuat"]); lama.waktu(r["diperbarui"])
        if (r["status"] not in ("reserved", "completed", "released", "unknown")
                or r["diperbarui"] < r["dibuat"]
                or not r["mulai_jendela"] <= r["dibuat"] < r["akhir_jendela"]
                or r["entitlement_sidik"] != r["sidik_jendela"]):
            raise KonflikKuota("operasi kuota tidak sah")


@contextmanager
def _transaksi(kon):
    if kon.in_transaction:
        raise ValueError("reservasi memerlukan transaksi sendiri")
    if kon.execute("PRAGMA user_version").fetchone()[0] != schema.VERSI_SKEMA:
        raise admin_store.StoreBelumSiap("kuota Pendamping belum dimigrasikan")
    if kon.row_factory is not sqlite3.Row:
        raise ValueError("koneksi kuota perlu sqlite3.Row")
    kon.execute("BEGIN IMMEDIATE")
    try:
        validasi_ledger(kon)
        yield
        kon.commit()
    except Exception:
        kon.rollback()
        raise


def _bekukan_jendela(kon, hak):
    # Satu trial/grant tidak boleh memperoleh jendela baru karena snapshot
    # bergeser, termasuk lewat fitur berbeda. Callback trusted tetap difencing.
    sumber = kon.execute(
        "SELECT entitlement_sidik FROM kuota_pendamping_jendela "
        "WHERE akun_id=? AND sumber=? AND sumber_id=? LIMIT 1",
        (hak.akun_id, hak.sumber, hak.sumber_id),
    ).fetchone()
    if sumber is not None and sumber[0] != hak.entitlement_sidik:
        raise KonflikKuota("sumber kuota telah dibekukan")
    nilai = (hak.akun_id, hak.jendela_id, hak.fitur, hak.entitlement_sidik,
             hak.sumber, hak.sumber_id, hak.paket, hak.entitlement_mulai,
             hak.entitlement_akhir, hak.jendela_mulai, hak.jendela_akhir, hak.limit)
    row = kon.execute("SELECT * FROM kuota_pendamping_jendela "
                      "WHERE akun_id=? AND jendela_id=? AND fitur=?", nilai[:3]).fetchone()
    if row is None:
        kon.execute("INSERT INTO kuota_pendamping_jendela VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", nilai)
    elif tuple(row) != nilai:
        raise KonflikKuota("snapshot jendela berbeda")


def reservasi_kon(kon, akun_id, *, operasi_id, fitur, sekarang, muat_snapshot,
                  penegakan=False):
    """Reserve atomik; prototype admin9, callback harus membaca sumber di kon.

    OFF tidak menulis apa pun dan mengembalikan None. Callback dijalankan di bawah
    lock IMMEDIATE sebelum cek kuota, jadi dua tab berbagi unit terakhir akun.
    Tidak menerima siswa/chat/prompt/foto atau angka kuota dari request.
    """
    lama.identitas(akun_id, "akun"); lama.identitas(operasi_id, "operasi")
    domain.validasi_fitur(fitur); lama.waktu(sekarang)
    if type(penegakan) is not bool:
        raise ValueError("sakelar penegakan tidak sah")
    if not penegakan:
        return None
    if not callable(muat_snapshot):
        raise ValueError("pemuat hak terverifikasi wajib")
    with _transaksi(kon):
        snapshot = muat_snapshot(kon, akun_id)
        hak = domain.selesaikan(akun_id, snapshot, fitur=fitur, sekarang=sekarang,
                               pemakaian=_pemakaian(kon, akun_id), penegakan=True)
        row = kon.execute("SELECT * FROM kuota_pendamping_operasi WHERE operasi_id=?",
                          (operasi_id,)).fetchone()
        if row is not None:
            ikatan = _ikatan(row)
            if (ikatan.akun_id, ikatan.fitur) != (akun_id, fitur):
                raise KonflikKuota("operasi terikat akun/fitur lain")
            # Jika jendela telah berganti, replay harus lewat baca_operasi_kon
            # dengan ikatan lama; tidak menafsirkan operationID sebagai request baru.
            if (ikatan.jendela_id, ikatan.entitlement_sidik) != (hak.jendela_id, hak.entitlement_sidik):
                raise KonflikKuota("operasi terikat jendela/hak lain")
            return Reservasi(False, row["status"], ikatan)
        if hak.status not in domain.STATUS_BERHAK:
            raise KuotaDitolak(hak.status)
        _bekukan_jendela(kon, hak)
        ikatan = IkatanOperasi(operasi_id, akun_id, fitur, hak.jendela_id, hak.entitlement_sidik)
        kon.execute("INSERT INTO kuota_pendamping_operasi VALUES(?,?,?,?,?,'reserved',?,?)",
                    (operasi_id, akun_id, hak.jendela_id, fitur, hak.entitlement_sidik, sekarang, sekarang))
        return Reservasi(True, "reserved", ikatan)


def _operasi(kon, ikatan):
    _validasi_ikatan(ikatan)
    row = kon.execute("SELECT * FROM kuota_pendamping_operasi WHERE operasi_id=?",
                      (ikatan.operasi_id,)).fetchone()
    if row is None or _ikatan(row) != ikatan:
        raise KonflikKuota("ikatan operasi berbeda")
    return row


def baca_operasi_kon(kon, ikatan):
    """Replay lama hanya lookup; tidak ada write, expiry, atau provider retry."""
    if kon.execute("PRAGMA user_version").fetchone()[0] != schema.VERSI_SKEMA:
        raise admin_store.StoreBelumSiap("kuota Pendamping belum dimigrasikan")
    validasi_ledger(kon)
    row = _operasi(kon, ikatan)
    return Reservasi(False, row["status"], ikatan)


def _ubah(kon, ikatan, *, sekarang, status, rekonsiliasi=False):
    lama.waktu(sekarang)
    if type(rekonsiliasi) is not bool:
        raise ValueError("penanda rekonsiliasi tidak sah")
    with _transaksi(kon):
        row = _operasi(kon, ikatan)
        if sekarang < row["diperbarui"]:
            raise KonflikKuota("clock operasi mundur")
        if row["status"] == status:
            return Reservasi(False, status, ikatan)
        if row["status"] in ("completed", "released"):
            raise KonflikKuota("operasi terminal tidak dapat diubah")
        if row["status"] == "unknown" and status != "unknown" and not rekonsiliasi:
            raise KonflikKuota("operasi unknown memerlukan bukti rekonsiliasi")
        kon.execute("UPDATE kuota_pendamping_operasi SET status=?,diperbarui=? WHERE operasi_id=?",
                    (status, sekarang, ikatan.operasi_id))
        return Reservasi(False, status, ikatan)


def tandai_unknown_kon(kon, ikatan, *, sekarang):
    """Timeout/crash pasca-outbound menahan unit; tidak ada release otomatis."""
    return _ubah(kon, ikatan, sekarang=sekarang, status="unknown")


def finalisasi_kon(kon, ikatan, *, sekarang, hasil_valid_tersimpan, rekonsiliasi=False):
    """Caller wajib mempunyai receipt output valid+durable, bukan sukses transport."""
    if hasil_valid_tersimpan is not True:
        raise KonflikKuota("hasil belum valid dan tersimpan")
    return _ubah(kon, ikatan, sekarang=sekarang, status="completed", rekonsiliasi=rekonsiliasi)


def lepaskan_kon(kon, ikatan, *, sekarang, tanpa_output_terbukti, rekonsiliasi=False):
    """Hanya kegagalan tanpa output terbukti; unknown perlu rekonsiliasi eksplisit."""
    if tanpa_output_terbukti is not True:
        raise KonflikKuota("ketiadaan output belum terbukti")
    return _ubah(kon, ikatan, sekarang=sekarang, status="released", rekonsiliasi=rekonsiliasi)


def muat_snapshot_admin8(kon, akun_id):
    """Reader admin7/8 existing; bukan pemuat sumber untuk writer prototype9.

    Caller membuka lewat admin_store.buka_baca dan memegang snapshot transaksi.
    Tidak menulis, memigrasikan, atau mengadopsi akun.
    """
    lama.identitas(akun_id, "akun")
    langganan.validasi_ledger(kon, akun_id=akun_id)
    row = kon.execute("SELECT 1 FROM langganan_enrollment WHERE akun_id=?", (akun_id,)).fetchone()
    if row is None:
        return domain.SnapshotHak(akun_id)
    enrollment = langganan._enrollment(kon, akun_id)
    periode_lama = tuple((g.periode.mulai, g.periode.akhir) for g in langganan._grants(kon, akun_id))
    transisi, grants = None, ()
    if paket_schema.tersedia(kon):
        row = kon.execute("SELECT mulai FROM paket_akun WHERE akun_id=?", (akun_id,)).fetchone()
        if row is not None:
            transisi = row[0]
            grants = tuple(domain.GrantHak(
                g["akun_id"], g["invoice_id"], g["paket"], g["penagihan"], g["mulai"],
                g["akhir"], g["jangkar_mulai"], g["indeks_bulan"], g["balasan"], g["foto"],
            ) for g in paket_store._grants(kon, akun_id))
    return domain.SnapshotHak(akun_id, enrollment.mulai, transisi, grants, periode_lama)


def baca_snapshot(path, akun_id):
    """Dry-run hak saja pada admin7/8; tidak berarti pemakaian nol terverifikasi."""
    with admin_store.buka_baca(path) as kon:
        kon.execute("BEGIN")
        return muat_snapshot_admin8(kon, akun_id)


def baca_status(path, akun_id, *, fitur, sekarang, penegakan=False):
    """Reader aplikasi sementara fail-closed: storage kuota belum diintegrasikan.

    Status tanpa hak (Jago/expired/belumtransisi) dapat diproyeksikan dari admin7/8.
    Trial/Pro tidak boleh disajikan sebagai jatah utuh ketika ledger belum tersedia.
    Pure selesaikan + baca_snapshot tetap tersedia untuk simulasi eksplisit.
    """
    try:
        snapshot = baca_snapshot(path, akun_id)
        hak = domain.selesaikan(akun_id, snapshot, fitur=fitur, sekarang=sekarang,
                               penegakan=penegakan)
        if hak.status not in domain.STATUS_BERHAK:
            return hak
    except (OSError, sqlite3.Error, RuntimeError, ValueError, LookupError):
        pass
    return domain.selesaikan(akun_id, domain.SnapshotHak(akun_id, terverifikasi=False),
                            fitur=fitur, sekarang=sekarang, penegakan=penegakan)
