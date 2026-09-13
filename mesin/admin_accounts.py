"""Adapter operasi admin terhadap auth JSON aktual.

Mutasi akun dan receipt ``operasi_admin`` ditulis dalam satu atomic replace di
bawah ``json_storage.transaksi_json`` yang sama. Modul ini tidak mengubah policy
HTTP/sesi dan tidak membuat akun baru.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import time
from pathlib import Path
import re
from typing import Mapping, Optional

import auth
from admin_contracts import (
    AKSI_BUAT_GURU,
    AKSI_BUAT_LOGIN_MURID,
    AKSI_CABUT_SESI,
    AKSI_HAPUS_LOGIN,
    AKSI_HAPUS_LOGIN_SAGA,
    AKSI_RESET_SANDI,
    HASIL_PER_AKSI,
    KontrakTidakSah,
    PerintahAkun,
    PerintahHapusSiswa,
    PerintahPembuatanAkun,
    ReceiptAkun,
    ReceiptPembuatan,
    receipt_cocok,
    receipt_dari_dict,
    receipt_ke_dict,
    sidik_perintah,
)
from json_storage import transaksi_json


class KonflikAkun(RuntimeError):
    """Actor/target/peran/revisi berubah atau receipt tidak cocok."""


class DomainAkunTidakSah(RuntimeError):
    """Auth JSON tidak dapat dibaca atau metadata receipt/revisi rusak."""


class BelumCommit(RuntimeError):
    """Failpoint atau kegagalan yang diketahui terjadi sebelum replace."""


class CrashSetelahReplace(RuntimeError):
    """Failpoint test: replace selesai tetapi caller belum menerima receipt."""


class CommitDomainTakPasti(RuntimeError):
    """Writer I/O gagal; replace mungkin sudah terjadi dan wajib direkonsiliasi."""


_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,39}$")


def validasi_alias(alias) -> str:
    """Alias bounded yang bukan kontak, formula, control, atau path."""
    if type(alias) is not str:
        raise KontrakTidakSah("alias tidak sah")
    hasil = alias.strip()
    if hasil != alias or _ALIAS.fullmatch(hasil) is None:
        raise KontrakTidakSah("alias tidak sah")
    if "@" in hasil or hasil[0] in "=+-@" or ".." in hasil:
        raise KontrakTidakSah("alias tidak sah")
    return hasil


def _revisi_auth(akun: dict) -> int:
    nilai = akun.get("revisi_auth", 0)
    if type(nilai) is not int or nilai < 0:
        raise DomainAkunTidakSah("revisi_auth akun tidak sah")
    return nilai


def _baca_state_terkunci(path: Path):
    """Bedakan file hilang dari JSON literal null; keduanya tak boleh ditimpa."""
    ada = path.exists()
    try:
        mentah, akun, bentuk_multi = auth._baca_akun_untuk_tulis(path)
    except (ValueError, OSError) as galat:
        raise DomainAkunTidakSah("berkas akun tidak sah") from galat
    if mentah is None:
        if ada:
            raise DomainAkunTidakSah("berkas akun null tidak sah")
        raise DomainAkunTidakSah("berkas akun belum tersedia")
    # Seluruh record diperiksa supaya ID/revisi ambigu tidak dipilih diam-diam.
    id_terlihat = set()
    for item in akun:
        if not isinstance(item, dict):
            raise DomainAkunTidakSah("record akun tidak sah")
        id_akun = item.get("id_akun")
        if not auth.id_akun_sah(id_akun) or id_akun in id_terlihat:
            raise DomainAkunTidakSah("id akun hilang/cacat/duplikat")
        id_terlihat.add(id_akun)
        peran = item.get("peran", "guru")
        if peran not in auth.PERAN:
            raise DomainAkunTidakSah("peran akun tidak sah")
        _revisi_auth(item)
    return mentah, akun, bentuk_multi


def _receipt_semua(mentah: dict) -> dict:
    nilai = mentah.get("operasi_admin", {})
    if not isinstance(nilai, dict):
        raise DomainAkunTidakSah("operasi_admin bukan mapping")
    hasil = {}
    try:
        for operasi_id, data in nilai.items():
            if type(operasi_id) is not str or not isinstance(data, dict):
                raise KontrakTidakSah("receipt tidak sah")
            receipt = receipt_dari_dict(data)
            if receipt.operasi_id != operasi_id:
                raise KontrakTidakSah("key receipt tidak cocok")
            hasil[operasi_id] = receipt
    except KontrakTidakSah as galat:
        raise DomainAkunTidakSah("receipt akun tidak sah") from galat
    return hasil


def _cari_id(akun: list, id_akun: str):
    cocok = [item for item in akun if item.get("id_akun") == id_akun]
    if len(cocok) > 1:
        raise DomainAkunTidakSah("id akun ambigu")
    return None if not cocok else cocok[0]


def _validasi_actor(akun: list, perintah: PerintahAkun):
    actor = _cari_id(akun, perintah.actor_id)
    if actor is None:
        raise KonflikAkun("actor tidak tersedia")
    if actor.get("peran", "guru") != "admin":
        raise KonflikAkun("actor bukan admin")
    if _revisi_auth(actor) != perintah.actor_revisi:
        raise KonflikAkun("revisi actor berubah")
    return actor


def _validasi_target(akun: list, perintah: PerintahAkun):
    target = _cari_id(akun, perintah.target_id)
    if target is None:
        raise KonflikAkun("target tidak tersedia")
    peran = target.get("peran", "guru")
    if peran == "admin":
        raise KonflikAkun("akun admin tidak boleh menjadi target")
    if peran != perintah.target_peran:
        raise KonflikAkun("peran target berubah")
    if _revisi_auth(target) != perintah.target_revisi:
        raise KonflikAkun("revisi target berubah")
    return target


def ringkasan_login_siswa(path_auth, *, siswa_id: int, siswa_nama: str):
    """Snapshot aman untuk membangun PerintahHapusSiswa di halaman tinjauan."""
    if type(siswa_id) is not int or siswa_id <= 0:
        raise KontrakTidakSah("siswa_id tidak sah")
    path = Path(path_auth)
    with transaksi_json(path) as tujuan:
        _mentah, akun, _multi = _baca_state_terkunci(tujuan)
        explicit = [
            item for item in akun
            if item.get("peran") == "murid" and item.get("siswa_id") == siswa_id
        ]
        legacy = [
            item for item in akun
            if item.get("peran") == "murid" and item.get("siswa_id") is None
            and item["pengguna"].strip().casefold() == siswa_nama.casefold()
        ]
        if legacy or len(explicit) > 1:
            raise KonflikAkun("login siswa ambigu")
        if not explicit:
            return None
        item = explicit[0]
        return item["id_akun"], _revisi_auth(item)


def _baca_receipt_terkunci(
    mentah: dict,
    perintah,
) -> Optional[ReceiptAkun]:
    receipt = _receipt_semua(mentah).get(perintah.operasi_id)
    if receipt is None:
        return None
    if not receipt_cocok(receipt, perintah):
        raise KonflikAkun("operation ID memiliki receipt berbeda")
    return receipt


@contextmanager
def kunci_actor(path_auth, perintah):
    """Tahan lock auth setelah actor admin mutakhir tervalidasi."""
    path = Path(path_auth)
    with transaksi_json(path) as tujuan:
        _mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        yield


def validasi_actor(path_auth, perintah) -> None:
    """Validasi principal admin mutakhir tanpa membaca/mempercayai receipt."""
    with kunci_actor(path_auth, perintah):
        return None


def baca_receipt(
    path_auth, perintah: PerintahAkun
) -> Optional[ReceiptAkun]:
    """Baca receipt setelah memvalidasi actor terbaru; corruption gagal tertutup."""
    path = Path(path_auth)
    with transaksi_json(path) as tujuan:
        mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        return _baca_receipt_terkunci(mentah, perintah)


def validasi_input(perintah: PerintahAkun, sandi_baru: Optional[str]) -> None:
    """Validasi request-local sebelum journal dibuat; tidak menghitung hash."""
    if perintah.aksi == AKSI_RESET_SANDI:
        minimum = 12 if perintah.target_peran == "guru" else 8
        if type(sandi_baru) is not str or len(sandi_baru) < minimum:
            raise KontrakTidakSah("sandi baru tidak memenuhi batas")
    elif sandi_baru is not None:
        raise KontrakTidakSah("aksi ini tidak menerima sandi")


@contextmanager
def langkah_login_hapus_siswa(
    path_auth,
    perintah,
    *,
    siswa_nama: str,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
):
    """Hapus login lalu tahan lock auth sampai commit DB caller selesai."""
    path = Path(path_auth)
    with transaksi_json(path) as tujuan:
        mentah, akun, _multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        explicit = [
            item for item in akun
            if item.get("peran") == "murid" and item.get("siswa_id") == perintah.siswa_id
        ]
        legacy = [
            item for item in akun
            if item.get("peran") == "murid" and item.get("siswa_id") is None
            and item["pengguna"].strip().casefold() == siswa_nama.casefold()
        ]
        if legacy:
            raise KonflikAkun("login warisan harus ditinjau manual")
        if perintah.login_id is None:
            if explicit:
                raise KonflikAkun("login siswa berubah")
            yield None
            return
        derived = perintah_login_delete(perintah)
        if len(explicit) != 1:
            receipt = _baca_receipt_terkunci(mentah, derived)
            if receipt is None:
                raise KonflikAkun("login siswa tidak tersedia")
            yield receipt
            return
        target = explicit[0]
        if target.get("id_akun") != perintah.login_id:
            raise KonflikAkun("generation login berubah")
        if _revisi_auth(target) != perintah.login_revisi:
            raise KonflikAkun("revisi login berubah")
        receipt_lama = _baca_receipt_terkunci(mentah, derived)
        if receipt_lama is not None:
            yield receipt_lama
            return
        akun = [item for item in akun if item.get("id_akun") != perintah.login_id]
        receipt = ReceiptAkun(
            1, derived.operasi_id, derived.actor_id, derived.aksi,
            derived.target_id, derived.target_peran, derived.target_revisi,
            derived.target_revisi + 1, HASIL_PER_AKSI[derived.aksi],
            int(time.time()) if sekarang is None else int(sekarang),
            sidik_perintah(derived),
        )
        receipt_map = dict(mentah.get("operasi_admin", {}))
        receipt_map[derived.operasi_id] = receipt_ke_dict(receipt)
        hasil = auth._bungkus_akun(mentah, akun)
        hasil["operasi_admin"] = receipt_map
        if failpoint == "sebelum_login_delete":
            raise BelumCommit("failpoint sebelum login delete")
        auth._tulis_akun_atomik(hasil, tujuan)
        if failpoint == "setelah_login_delete":
            raise CrashSetelahReplace("failpoint setelah login delete")
        yield receipt


def baca_receipt_login_siswa_saga(
    path_auth, perintah: PerintahHapusSiswa
) -> Optional[ReceiptAkun]:
    """Baca receipt langkah login dengan validasi actor mutakhir."""
    if perintah.login_id is None:
        return None
    return baca_receipt(path_auth, perintah_login_delete(perintah))


def perintah_login_delete(perintah: PerintahHapusSiswa) -> PerintahAkun:
    from admin_contracts import AKSI_HAPUS_LOGIN_SAGA, PerintahAkun
    if perintah.login_id is None:
        raise KontrakTidakSah("command tidak memiliki login")
    operasi_login = "operasi_" + hashlib.sha256(
        (perintah.operasi_id + ":login").encode("ascii")
    ).hexdigest()[:32]
    return PerintahAkun(
        operasi_login,
        perintah.actor_id,
        perintah.actor_revisi,
        AKSI_HAPUS_LOGIN_SAGA,
        perintah.login_id,
        perintah.login_revisi,
        "murid",
        perintah.token_tinjauan,
    )


def jalankan(
    path_auth,
    perintah: PerintahAkun,
    *,
    sandi_baru: Optional[str] = None,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> ReceiptAkun:
    """Mutasi target + receipt satu replace; replay tidak mengulang mutasi.

    Hash sandi dihitung sebelum lock agar login lain tidak tertahan oleh PBKDF2.
    Precondition actor/target selalu dibaca ulang setelah lock didapat.
    """
    validasi_input(perintah, sandi_baru)
    path = Path(path_auth)
    kini = int(time.time()) if sekarang is None else int(sekarang)

    # Preflight terkunci membuat replay selesai tanpa menghitung PBKDF2 lagi.
    # Target tetap divalidasi ulang pada transaksi commit setelah hash dibuat.
    with transaksi_json(path) as tujuan:
        mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        receipt_lama = _baca_receipt_terkunci(mentah, perintah)
        if receipt_lama is not None:
            return receipt_lama
        _validasi_target(akun, perintah)

    if perintah.aksi == AKSI_RESET_SANDI:
        hash_baru = auth.buat_hash(sandi_baru)
    else:
        hash_baru = None

    with transaksi_json(path) as tujuan:
        mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        receipt_lama = _baca_receipt_terkunci(mentah, perintah)
        if receipt_lama is not None:
            return receipt_lama
        target = _validasi_target(akun, perintah)
        revisi_hasil = perintah.target_revisi + 1

        if perintah.aksi == AKSI_RESET_SANDI:
            target.update(hash_baru)
            target["revisi_auth"] = revisi_hasil
        elif perintah.aksi == AKSI_CABUT_SESI:
            target["revisi_auth"] = revisi_hasil
        elif perintah.aksi == AKSI_HAPUS_LOGIN:
            akun = [item for item in akun if item.get("id_akun") != perintah.target_id]
        else:  # pragma: no cover - dataclass sudah menolak
            raise KontrakTidakSah("aksi akun tidak dikenal")

        receipt = ReceiptAkun(
            1,
            perintah.operasi_id,
            perintah.actor_id,
            perintah.aksi,
            perintah.target_id,
            perintah.target_peran,
            perintah.target_revisi,
            revisi_hasil,
            HASIL_PER_AKSI[perintah.aksi],
            kini,
            sidik_perintah(perintah),
        )
        receipt_map = dict(mentah.get("operasi_admin", {}))
        receipt_map[perintah.operasi_id] = receipt_ke_dict(receipt)
        hasil = auth._bungkus_akun(mentah, akun)
        hasil["operasi_admin"] = receipt_map

        if failpoint == "sebelum_replace":
            raise BelumCommit("failpoint sebelum replace")
        try:
            auth._tulis_akun_atomik(hasil, tujuan)
        except OSError as galat:
            # Replace/fsync mungkin sudah terjadi. Jangan mengaku sukses dari
            # state yang kebetulan terbaca pada proses ini; reconcile terpisah.
            raise CommitDomainTakPasti("commit domain perlu rekonsiliasi") from galat
        if failpoint == "setelah_replace":
            raise CrashSetelahReplace("failpoint setelah replace")
        return receipt


def validasi_pembuatan_input(
    perintah: PerintahPembuatanAkun,
    sandi_baru: str,
) -> str:
    alias = validasi_alias(perintah.alias)
    minimum = 12 if perintah.target_peran == "guru" else 8
    if type(sandi_baru) is not str or len(sandi_baru) < minimum:
        raise KontrakTidakSah("sandi akun baru tidak memenuhi batas")
    return alias


def validasi_guard_create(
    perintah: PerintahPembuatanAkun,
    guard: Mapping[str, object],
) -> None:
    """Validasi fakta DB typed; fakta auth dihitung ulang di lock auth."""
    if not isinstance(guard, Mapping):
        raise KontrakTidakSah("guard pembuatan bukan mapping")
    if perintah.aksi == AKSI_BUAT_GURU:
        if set(guard) != {"owner_lama_ada"} or type(guard["owner_lama_ada"]) is not bool:
            raise KontrakTidakSah("guard guru tidak lengkap")
        if guard["owner_lama_ada"]:
            raise KonflikAkun("alias masih terikat pemilik lama")
        return
    wajib = {"siswa_ada", "owner_pengguna", "siswa_nama", "jumlah_nama"}
    if set(guard) != wajib:
        raise KontrakTidakSah("guard murid tidak lengkap")
    if type(guard["siswa_ada"]) is not bool or type(guard["jumlah_nama"]) is not int:
        raise KontrakTidakSah("guard murid tidak sah")
    if not guard["siswa_ada"]:
        raise KonflikAkun("siswa tidak tersedia")
    if (
        type(guard["owner_pengguna"]) is not str
        or not guard["owner_pengguna"]
        or type(guard["siswa_nama"]) is not str
        or not guard["siswa_nama"]
        or guard["jumlah_nama"] < 1
    ):
        raise KonflikAkun("siswa atau pemilik tidak valid")


def buat_akun(
    path_auth,
    perintah: PerintahPembuatanAkun,
    *,
    sandi_baru: str,
    guard: Mapping[str, object],
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
) -> ReceiptPembuatan:
    """Buat guru/login murid + receipt dalam satu replace auth.

    Guard DB diberikan service setelah dibaca ulang tepat sebelum commit. Adapter
    tetap mengulang uniqueness alias dan siswa_id di dalam lock auth.
    """
    alias = validasi_pembuatan_input(perintah, sandi_baru)
    validasi_guard_create(perintah, guard)
    path = Path(path_auth)
    kini = int(time.time()) if sekarang is None else int(sekarang)

    with transaksi_json(path) as tujuan:
        mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        receipt_lama = _baca_receipt_terkunci(mentah, perintah)
        if receipt_lama is not None:
            return receipt_lama
        if any(item["pengguna"].strip().casefold() == alias.casefold() for item in akun):
            raise KonflikAkun("alias akun sudah dipakai")
        if perintah.aksi == AKSI_BUAT_LOGIN_MURID:
            owner = [
                item for item in akun
                if item["pengguna"].strip().casefold()
                == guard["owner_pengguna"].casefold()
                and item.get("peran", "guru") in ("guru", "admin")
            ]
            if len(owner) != 1:
                raise KonflikAkun("pemilik siswa tidak valid")
            if any(
                item.get("peran") == "murid"
                and item.get("siswa_id") == perintah.siswa_id
                for item in akun
            ):
                raise KonflikAkun("siswa sudah memiliki login")
            legacy = [
                item for item in akun
                if item.get("peran") == "murid"
                and item.get("siswa_id") is None
                and item["pengguna"].strip().casefold()
                == guard["siswa_nama"].casefold()
            ]
            if legacy:
                raise KonflikAkun("siswa memiliki login warisan belum terverifikasi")

    hash_baru = auth.buat_hash(sandi_baru)
    with transaksi_json(path) as tujuan:
        mentah, akun, _bentuk_multi = _baca_state_terkunci(tujuan)
        _validasi_actor(akun, perintah)
        receipt_lama = _baca_receipt_terkunci(mentah, perintah)
        if receipt_lama is not None:
            return receipt_lama
        if any(item["pengguna"].strip().casefold() == alias.casefold() for item in akun):
            raise KonflikAkun("alias akun sudah dipakai")
        if perintah.aksi == AKSI_BUAT_LOGIN_MURID:
            owner = [
                item for item in akun
                if item["pengguna"].strip().casefold()
                == guard["owner_pengguna"].casefold()
                and item.get("peran", "guru") in ("guru", "admin")
            ]
            if len(owner) != 1:
                raise KonflikAkun("pemilik siswa tidak valid")
            if any(
                item.get("peran") == "murid"
                and item.get("siswa_id") == perintah.siswa_id
                for item in akun
            ):
                raise KonflikAkun("siswa sudah memiliki login")
            legacy = [
                item for item in akun
                if item.get("peran") == "murid"
                and item.get("siswa_id") is None
                and item["pengguna"].strip().casefold()
                == guard["siswa_nama"].casefold()
            ]
            if legacy:
                raise KonflikAkun("siswa memiliki login warisan belum terverifikasi")
        id_baru = (
            "akun_" + perintah.target_id[len("candidate_"):]
            if perintah.target_id.startswith("candidate_")
            and len(perintah.target_id) == len("candidate_") + 32
            and all(c in "0123456789abcdef" for c in perintah.target_id[len("candidate_"):])
            else auth._buat_id_akun()
        )
        if any(item.get("id_akun") == id_baru for item in akun):
            raise KonflikAkun("ID hasil pembuatan sudah dipakai")
        baru = {
            "pengguna": alias,
            "peran": perintah.target_peran,
            "id_akun": id_baru,
            "revisi_auth": 1,
            **hash_baru,
        }
        if perintah.aksi == AKSI_BUAT_LOGIN_MURID:
            baru["siswa_id"] = perintah.siswa_id
        akun.append(baru)
        receipt = ReceiptPembuatan(
            1,
            perintah.operasi_id,
            perintah.actor_id,
            perintah.aksi,
            perintah.target_id,
            perintah.target_peran,
            0,
            1,
            HASIL_PER_AKSI[perintah.aksi],
            kini,
            sidik_perintah(perintah),
            id_baru,
        )
        receipt_map = dict(mentah.get("operasi_admin", {}))
        receipt_map[perintah.operasi_id] = receipt_ke_dict(receipt)
        hasil = auth._bungkus_akun(mentah, akun)
        hasil["operasi_admin"] = receipt_map
        if failpoint == "sebelum_replace":
            raise BelumCommit("failpoint sebelum replace")
        try:
            auth._tulis_akun_atomik(hasil, tujuan)
        except OSError as galat:
            raise CommitDomainTakPasti("commit create perlu rekonsiliasi") from galat
        if failpoint == "setelah_replace":
            raise CrashSetelahReplace("failpoint setelah replace")
        return receipt
