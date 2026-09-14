"""Kontrak typed dan registry sempit untuk operasi admin.

Tidak ada nama pengguna, sandi, hash autentikasi, token sesi, atau payload bebas
di model durable. Token tinjauan opaque hanya dipakai sebagai input sidik SHA-256
dan tidak disimpan atau ditampilkan oleh dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Optional


AKSI_RESET_SANDI = "account_password_reset"
AKSI_CABUT_SESI = "account_session_revoke"
AKSI_HAPUS_LOGIN = "account_login_delete"
AKSI_HAPUS_LOGIN_SAGA = "student_login_delete_step"
AKSI_BUAT_GURU = "account_teacher_create"
AKSI_BUAT_LOGIN_MURID = "student_login_create"
AKSI_UBAH_LEVEL = "student_level_update"
AKSI_HAPUS_SISWA = "student_delete"
AKSI_UBAH_PENDAFTARAN = "registration_config_update"
AKSI_AKUN_EXISTING = frozenset((
    AKSI_RESET_SANDI, AKSI_CABUT_SESI, AKSI_HAPUS_LOGIN,
    AKSI_HAPUS_LOGIN_SAGA,
))
AKSI_PEMBUATAN = frozenset((AKSI_BUAT_GURU, AKSI_BUAT_LOGIN_MURID))
AKSI_AKUN = AKSI_AKUN_EXISTING | AKSI_PEMBUATAN
AKSI_AUDIT = AKSI_AKUN | frozenset((
    AKSI_UBAH_LEVEL, AKSI_HAPUS_SISWA, AKSI_UBAH_PENDAFTARAN,
))
PERAN_TARGET = frozenset(("guru", "murid"))
JENIS_TARGET = {
    AKSI_RESET_SANDI: "account",
    AKSI_CABUT_SESI: "account",
    AKSI_HAPUS_LOGIN: "account",
    AKSI_HAPUS_LOGIN_SAGA: "account",
    AKSI_BUAT_GURU: "account_candidate",
    AKSI_BUAT_LOGIN_MURID: "account_candidate",
    AKSI_UBAH_LEVEL: "student",
    AKSI_HAPUS_SISWA: "student",
    AKSI_UBAH_PENDAFTARAN: "registration_config",
}
STATUS_OPERASI = frozenset((
    "reserved",
    "succeeded",
    "failed_before_commit",
    "conflict",
    "uncertain",
    "cancelled",
))
STATUS_TERMINAL = frozenset((
    "succeeded", "failed_before_commit", "conflict", "cancelled",
))
HASIL_KODE = frozenset((
    "password_reset",
    "sessions_revoked",
    "login_deleted",
    "teacher_created",
    "student_login_created",
    "student_level_updated",
    "student_deleted",
    "config_updated",
    "target_changed",
    "input_rejected",
    "domain_not_committed",
    "domain_uncertain",
))
HASIL_PER_AKSI = {
    AKSI_RESET_SANDI: "password_reset",
    AKSI_CABUT_SESI: "sessions_revoked",
    AKSI_HAPUS_LOGIN: "login_deleted",
    AKSI_HAPUS_LOGIN_SAGA: "login_deleted",
    AKSI_BUAT_GURU: "teacher_created",
    AKSI_BUAT_LOGIN_MURID: "student_login_created",
    AKSI_UBAH_LEVEL: "student_level_updated",
    AKSI_HAPUS_SISWA: "student_deleted",
    AKSI_UBAH_PENDAFTARAN: "config_updated",
}
FIELD_AUDIT = frozenset((
    "auth_revision", "registration_open", "registration_message", "student_level",
))
PESAN_PENDAFTARAN = frozenset(("closed_standard", "closed_maintenance"))

_ID_UMUM = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{7,95}$")
_TOKEN_TINJAUAN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class KontrakTidakSah(ValueError):
    """Input di luar registry kontrak ditolak sebelum menyentuh storage."""


def validasi_id(nilai, label: str) -> str:
    if type(nilai) is not str or _ID_UMUM.fullmatch(nilai) is None:
        raise KontrakTidakSah("%s tidak sah" % label)
    return nilai


def validasi_revisi(nilai, label: str) -> int:
    if type(nilai) is not int or nilai < 0:
        raise KontrakTidakSah("%s harus integer nonnegatif" % label)
    return nilai


def validasi_sidik(nilai) -> str:
    if type(nilai) is not str or _HEX_64.fullmatch(nilai) is None:
        raise KontrakTidakSah("sidik perintah tidak sah")
    return nilai


@dataclass(frozen=True)
class PerintahAkun:
    operasi_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    target_id: str
    target_revisi: int
    target_peran: str
    token_tinjauan: str = field(repr=False)

    def __post_init__(self):
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_id(self.target_id, "target_id")
        validasi_revisi(self.actor_revisi, "actor_revisi")
        validasi_revisi(self.target_revisi, "target_revisi")
        if self.aksi not in AKSI_AKUN_EXISTING:
            raise KontrakTidakSah("aksi akun existing tidak diizinkan")
        if self.target_peran not in PERAN_TARGET:
            raise KontrakTidakSah("peran target tidak diizinkan")
        if (
            type(self.token_tinjauan) is not str
            or _TOKEN_TINJAUAN.fullmatch(self.token_tinjauan) is None
        ):
            raise KontrakTidakSah("token tinjauan tidak sah")
        if self.actor_id == self.target_id:
            raise KontrakTidakSah("actor tidak boleh menjadi target")


@dataclass(frozen=True)
class PerintahPembuatanAkun:
    operasi_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    target_id: str
    target_peran: str
    alias: str = field(repr=False)
    token_tinjauan: str = field(repr=False)
    siswa_id: Optional[int] = None
    target_revisi: int = 0

    def __post_init__(self):
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_id(self.target_id, "target_id")
        validasi_revisi(self.actor_revisi, "actor_revisi")
        if self.target_revisi != 0:
            raise KontrakTidakSah("revisi calon akun harus 0")
        if self.aksi not in AKSI_PEMBUATAN:
            raise KontrakTidakSah("aksi pembuatan tidak diizinkan")
        if self.target_peran not in PERAN_TARGET:
            raise KontrakTidakSah("peran calon tidak diizinkan")
        if self.aksi == AKSI_BUAT_GURU:
            if self.target_peran != "guru" or self.siswa_id is not None:
                raise KontrakTidakSah("pembuatan guru tidak menerima siswa")
        elif self.target_peran != "murid" or type(self.siswa_id) is not int or self.siswa_id <= 0:
            raise KontrakTidakSah("pembuatan login murid memerlukan siswa")
        if type(self.alias) is not str:
            raise KontrakTidakSah("alias calon tidak sah")
        if (
            type(self.token_tinjauan) is not str
            or _TOKEN_TINJAUAN.fullmatch(self.token_tinjauan) is None
        ):
            raise KontrakTidakSah("token tinjauan tidak sah")


@dataclass(frozen=True)
class PerintahSiswa:
    operasi_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    siswa_id: int
    expected_level: str
    level_baru: str
    token_tinjauan: str = field(repr=False)

    @property
    def target_id(self) -> str:
        return "student_%d" % self.siswa_id

    @property
    def target_peran(self):
        return None

    @property
    def target_revisi(self) -> int:
        return 0

    def __post_init__(self):
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_revisi(self.actor_revisi, "actor_revisi")
        if self.aksi != AKSI_UBAH_LEVEL:
            raise KontrakTidakSah("aksi siswa tidak diizinkan")
        if type(self.siswa_id) is not int or self.siswa_id <= 0:
            raise KontrakTidakSah("siswa_id tidak sah")
        if self.expected_level not in ("P3", "P4", "P5", "P6"):
            raise KontrakTidakSah("level awal tidak sah")
        if self.level_baru not in ("P3", "P4", "P5", "P6"):
            raise KontrakTidakSah("level baru tidak sah")
        if (
            type(self.token_tinjauan) is not str
            or _TOKEN_TINJAUAN.fullmatch(self.token_tinjauan) is None
        ):
            raise KontrakTidakSah("token tinjauan tidak sah")


@dataclass(frozen=True)
class PerintahHapusSiswa:
    operasi_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    siswa_id: int
    expected_level: str = "P3"
    login_id: Optional[str] = None
    login_revisi: Optional[int] = None
    token_tinjauan: str = field(default="", repr=False)

    @property
    def target_id(self) -> str:
        return "student_%d" % self.siswa_id

    @property
    def target_peran(self):
        return None

    @property
    def target_revisi(self) -> int:
        return 0

    def __post_init__(self):
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_revisi(self.actor_revisi, "actor_revisi")
        if self.aksi != AKSI_HAPUS_SISWA:
            raise KontrakTidakSah("aksi hapus siswa tidak sah")
        if type(self.siswa_id) is not int or self.siswa_id <= 0:
            raise KontrakTidakSah("siswa_id tidak sah")
        if self.expected_level not in ("P3", "P4", "P5", "P6"):
            raise KontrakTidakSah("level awal tidak sah")
        if (self.login_id is None) != (self.login_revisi is None):
            raise KontrakTidakSah("ID/revisi login harus berpasangan")
        if self.login_id is not None:
            validasi_id(self.login_id, "login_id")
            validasi_revisi(self.login_revisi, "login_revisi")
        if (
            type(self.token_tinjauan) is not str
            or _TOKEN_TINJAUAN.fullmatch(self.token_tinjauan) is None
        ):
            raise KontrakTidakSah("token tinjauan tidak sah")


@dataclass(frozen=True)
class ReceiptAkun:
    versi: int
    operasi_id: str
    actor_id: str
    aksi: str
    target_id: str
    target_peran: str
    revisi_awal: int
    revisi_hasil: int
    hasil_kode: str
    dibuat: int
    sidik_perintah: str

    def __post_init__(self):
        if self.versi != 1:
            raise KontrakTidakSah("versi receipt tidak didukung")
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_id(self.target_id, "target_id")
        validasi_revisi(self.revisi_awal, "revisi_awal")
        validasi_revisi(self.revisi_hasil, "revisi_hasil")
        if self.aksi not in AKSI_AKUN_EXISTING:
            raise KontrakTidakSah("aksi receipt existing tidak diizinkan")
        if self.target_peran not in PERAN_TARGET:
            raise KontrakTidakSah("peran receipt tidak diizinkan")
        if self.hasil_kode != HASIL_PER_AKSI[self.aksi]:
            raise KontrakTidakSah("hasil receipt tidak cocok dengan aksi")
        if self.revisi_hasil != self.revisi_awal + 1:
            raise KontrakTidakSah("revisi hasil receipt tidak berurutan")
        if type(self.dibuat) is not int or self.dibuat < 0:
            raise KontrakTidakSah("waktu receipt tidak sah")
        validasi_sidik(self.sidik_perintah)


@dataclass(frozen=True)
class ReceiptPembuatan:
    versi: int
    operasi_id: str
    actor_id: str
    aksi: str
    target_id: str
    target_peran: str
    revisi_awal: int
    revisi_hasil: int
    hasil_kode: str
    dibuat: int
    sidik_perintah: str
    hasil_id: str

    def __post_init__(self):
        if self.versi != 1:
            raise KontrakTidakSah("versi receipt tidak didukung")
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_id(self.target_id, "target_id")
        validasi_id(self.hasil_id, "hasil_id")
        if self.aksi not in AKSI_PEMBUATAN:
            raise KontrakTidakSah("aksi receipt pembuatan tidak diizinkan")
        if self.target_peran not in PERAN_TARGET:
            raise KontrakTidakSah("peran receipt tidak diizinkan")
        if self.hasil_kode != HASIL_PER_AKSI[self.aksi]:
            raise KontrakTidakSah("hasil receipt tidak cocok dengan aksi")
        if self.revisi_awal != 0 or self.revisi_hasil != 1:
            raise KontrakTidakSah("revisi receipt pembuatan tidak sah")
        if type(self.dibuat) is not int or self.dibuat < 0:
            raise KontrakTidakSah("waktu receipt tidak sah")
        validasi_sidik(self.sidik_perintah)


@dataclass(frozen=True)
class ReceiptSiswa:
    versi: int
    operasi_id: str
    actor_id: str
    aksi: str
    target_id: str
    target_peran: Optional[str]
    revisi_awal: int
    revisi_hasil: int
    hasil_kode: str
    dibuat: int
    sidik_perintah: str
    perubahan: tuple

    def __post_init__(self):
        if self.versi != 1 or self.aksi not in (AKSI_UBAH_LEVEL, AKSI_HAPUS_SISWA):
            raise KontrakTidakSah("receipt siswa tidak sah")
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.actor_id, "actor_id")
        validasi_id(self.target_id, "target_id")
        if self.target_peran is not None:
            raise KontrakTidakSah("receipt siswa tidak memiliki peran akun")
        if self.revisi_awal != 0 or self.revisi_hasil != 0:
            raise KontrakTidakSah("revisi receipt siswa tidak sah")
        if self.hasil_kode != HASIL_PER_AKSI[self.aksi]:
            raise KontrakTidakSah("hasil receipt siswa tidak sah")
        if type(self.dibuat) is not int or self.dibuat < 0:
            raise KontrakTidakSah("waktu receipt siswa tidak sah")
        validasi_sidik(self.sidik_perintah)
        if type(self.perubahan) is not tuple:
            raise KontrakTidakSah("perubahan receipt siswa harus tuple")


@dataclass(frozen=True)
class HasilOperasi:
    operasi_id: str
    aksi: str
    target_id: str
    target_peran: Optional[str]
    status: str
    hasil_kode: Optional[str]
    revisi_hasil: Optional[int]
    credential_status: str
    hasil_id: Optional[str] = None

    def __post_init__(self):
        validasi_id(self.operasi_id, "operasi_id")
        validasi_id(self.target_id, "target_id")
        if self.aksi not in AKSI_AUDIT:
            raise KontrakTidakSah("aksi hasil tidak diizinkan")
        if JENIS_TARGET[self.aksi] == "account":
            if self.target_peran not in PERAN_TARGET:
                raise KontrakTidakSah("peran target hasil tidak sah")
        elif JENIS_TARGET[self.aksi] == "account_candidate":
            if self.target_peran not in PERAN_TARGET:
                raise KontrakTidakSah("peran hasil pembuatan tidak sah")
        elif self.target_peran is not None:
            raise KontrakTidakSah("target ini tidak memiliki peran akun")
        if self.status not in STATUS_OPERASI:
            raise KontrakTidakSah("status hasil tidak diizinkan")
        if self.hasil_kode is not None and self.hasil_kode not in HASIL_KODE:
            raise KontrakTidakSah("kode hasil tidak diizinkan")
        if self.revisi_hasil is not None:
            validasi_revisi(self.revisi_hasil, "revisi_hasil")
        if self.credential_status not in ("not_applicable", "unconfirmed"):
            raise KontrakTidakSah("status credential tidak diizinkan")


@dataclass(frozen=True)
class HasilLayanan:
    hasil: HasilOperasi
    baru_dieksekusi: bool
    credential_sekali: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.baru_dieksekusi) is not bool:
            raise KontrakTidakSah("penanda eksekusi harus boolean")
        if self.credential_sekali is not None and not self.baru_dieksekusi:
            raise KontrakTidakSah("credential hanya boleh pada eksekusi baru")


def sidik_perintah(perintah) -> str:
    """Digest identitas nonsecret + token preview; sandi bukan input."""
    isi = {
        "aksi": perintah.aksi,
        "actor_id": perintah.actor_id,
        "actor_revisi": perintah.actor_revisi,
        "operasi_id": perintah.operasi_id,
        "target_id": perintah.target_id,
        "target_peran": perintah.target_peran,
        "target_revisi": perintah.target_revisi,
        "token_tinjauan": perintah.token_tinjauan,
    }
    if isinstance(perintah, PerintahPembuatanAkun):
        isi["alias"] = perintah.alias
        isi["siswa_id"] = perintah.siswa_id
    elif isinstance(perintah, PerintahSiswa):
        isi["expected_level"] = perintah.expected_level
        isi["level_baru"] = perintah.level_baru
    elif isinstance(perintah, PerintahHapusSiswa):
        isi["expected_level"] = perintah.expected_level
        isi["login_id"] = perintah.login_id
        isi["login_revisi"] = perintah.login_revisi
    mentah = json.dumps(
        isi, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(mentah).hexdigest()


def receipt_ke_dict(receipt) -> dict:
    """Serialisasi allow-list; receipt B lama tetap byte-shape kompatibel."""
    hasil = {
        "versi": receipt.versi,
        "operasi_id": receipt.operasi_id,
        "actor_id": receipt.actor_id,
        "aksi": receipt.aksi,
        "target_id": receipt.target_id,
        "target_peran": receipt.target_peran,
        "revisi_awal": receipt.revisi_awal,
        "revisi_hasil": receipt.revisi_hasil,
        "hasil_kode": receipt.hasil_kode,
        "dibuat": receipt.dibuat,
        "sidik_perintah": receipt.sidik_perintah,
    }
    if isinstance(receipt, ReceiptPembuatan):
        hasil["hasil_id"] = receipt.hasil_id
    return hasil


def receipt_dari_dict(data) -> ReceiptAkun:
    wajib = {
        "versi", "operasi_id", "actor_id", "aksi", "target_id",
        "target_peran", "revisi_awal", "revisi_hasil", "hasil_kode",
        "dibuat", "sidik_perintah",
    }
    if not isinstance(data, dict) or set(data) not in (wajib, wajib | {"hasil_id"}):
        raise KontrakTidakSah("struktur receipt tidak sah")
    if "hasil_id" in data:
        return ReceiptPembuatan(**data)
    return ReceiptAkun(**data)


def receipt_cocok(receipt, perintah) -> bool:
    revisi_awal = getattr(perintah, "target_revisi", 0)
    revisi_cocok = (
        receipt.revisi_awal == revisi_awal
        if not isinstance(perintah, PerintahSiswa)
        else receipt.revisi_awal == 0 and receipt.revisi_hasil == 0
    )
    if isinstance(perintah, PerintahHapusSiswa):
        revisi_cocok = receipt.revisi_awal == 0 and receipt.revisi_hasil == 0
    return bool(
        receipt.operasi_id == perintah.operasi_id
        and receipt.actor_id == perintah.actor_id
        and receipt.aksi == perintah.aksi
        and receipt.target_id == perintah.target_id
        and receipt.target_peran == perintah.target_peran
        and revisi_cocok
        and receipt.sidik_perintah == sidik_perintah(perintah)
    )
