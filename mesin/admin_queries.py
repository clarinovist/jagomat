"""Proyeksi baca-saja untuk pusat kendali admin.

Modul ini tidak membuka database atau berkas akun sendiri. Pemanggil wajib
memberikan koneksi SQLite yang sudah dibuka dan satu snapshot akun hasil baca
pada awal request. Field credential diputus di ``snapshot_akun`` dan tidak
pernah menjadi bagian DTO renderer.

Angka sesi di sini adalah catatan administratif, bukan ukuran progres atau
kelulusan. ``waktu_aktivitas`` memakai nilai pertama yang tersedia dari
``selesai``, ``mulai``, ``dibuat``, lalu ``tanggal``. Sesi dibatalkan tetap
terhitung sebagai catatan dan diberi label tersendiri.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Iterable, Mapping, Optional, Sequence, Tuple


BATAS_BAWAAN = 25
BATAS_MAKSIMUM = 100
LEVEL_DIIJINKAN = frozenset(("P3", "P4", "P5", "P6"))
PERAN_DIIJINKAN = frozenset(("admin", "guru", "murid"))
STATUS_SISWA = frozenset((
    "student_without_login",
    "duplicate_explicit_login",
    "owner_without_account",
    "owner_empty",
    "owner_admin",
    "legacy_login_unverified",
    "legacy_same_name_ambiguous",
))
STATUS_KELUARGA = frozenset((
    "account_missing_id",
    "no_students",
    "owner_without_account",
    "owner_empty",
    "owner_admin",
))
STATUS_LOGIN = frozenset((
    "orphan_login",
    "legacy_orphan_login",
    "legacy_login_unverified",
    "legacy_same_name_ambiguous",
))


class InputQueryTidakSah(ValueError):
    """Filter atau snapshot tidak memenuhi kontrak sempit query admin."""


@dataclass(frozen=True)
class AkunPublik:
    """Field akun yang aman untuk proyeksi admin; tidak ada credential."""

    id_akun: Optional[str]
    pengguna: str
    peran: str
    siswa_id: Optional[int]


@dataclass(frozen=True)
class IdentitasSiswa:
    id: int
    nama: str
    tingkat: str
    pemilik: str


@dataclass(frozen=True)
class LoginBermasalah:
    id_akun: Optional[str]
    pengguna: str
    siswa_id: Optional[int]
    status: str
    jumlah_kandidat: int


@dataclass(frozen=True)
class KonteksAdmin:
    """Snapshot immutable yang dibangun sekali untuk satu request."""

    akun: Tuple[AkunPublik, ...]
    siswa: Tuple[IdentitasSiswa, ...]
    login_bermasalah: Tuple[LoginBermasalah, ...]


@dataclass(frozen=True)
class HitungPerhatian:
    kode: str
    jumlah: int


@dataclass(frozen=True)
class AktivitasSesi:
    sesi_id: int
    siswa_id: int
    nama_siswa: str
    pemilik: str
    tingkat: str
    tanggal: str
    waktu_aktivitas: str
    dibatalkan: bool


@dataclass(frozen=True)
class RingkasanAdmin:
    jumlah_keluarga: int
    jumlah_siswa: int
    jumlah_login_murid: int
    jumlah_sesi: int
    sesi_7_hari: int
    sesi_30_hari: int
    sesi_dibatalkan: int
    perhatian: Tuple[HitungPerhatian, ...]
    login_bermasalah: Tuple[LoginBermasalah, ...]
    aktivitas_terbaru: Tuple[AktivitasSesi, ...]


@dataclass(frozen=True)
class KeluargaRingkas:
    id_akun: Optional[str]
    pengguna: str
    kategori: str
    jumlah_siswa: int
    jumlah_sesi: int
    aktivitas_terakhir: Optional[str]
    status: Tuple[str, ...]


@dataclass(frozen=True)
class SiswaRingkas:
    id: int
    nama: str
    tingkat: str
    pemilik: str
    keluarga_id: Optional[str]
    keluarga_kategori: str
    login_id: Optional[str]
    login_pengguna: Optional[str]
    jumlah_sesi: int
    aktivitas_terakhir: Optional[str]
    status: Tuple[str, ...]


@dataclass(frozen=True)
class SesiRingkas:
    id: int
    tanggal: str
    waktu_aktivitas: str
    tingkat: str
    dibatalkan: bool


@dataclass(frozen=True)
class DetailKeluarga:
    keluarga: KeluargaRingkas
    siswa: "HalamanSiswa"


@dataclass(frozen=True)
class DetailSiswa:
    siswa: SiswaRingkas
    sesi_terbaru: Tuple[SesiRingkas, ...]


@dataclass(frozen=True)
class HalamanKeluarga:
    item: Tuple[KeluargaRingkas, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int
    cari: str
    status: str
    memiliki_anak: str


@dataclass(frozen=True)
class HalamanSiswa:
    item: Tuple[SiswaRingkas, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int
    cari: str
    tingkat: str
    status: str
    keluarga_id: str


def _teks_wajib(nilai, label: str, *, maksimum: int = 160) -> str:
    if type(nilai) is not str:
        raise InputQueryTidakSah("%s harus berupa teks" % label)
    hasil = nilai.strip()
    if not hasil or len(hasil) > maksimum or any(ord(c) < 32 for c in hasil):
        raise InputQueryTidakSah("%s tidak sah" % label)
    return hasil


def _id_opsional(nilai) -> Optional[str]:
    if nilai is None:
        return None
    return _teks_wajib(nilai, "id_akun", maksimum=96)


def _siswa_id_opsional(nilai) -> Optional[int]:
    if nilai is None:
        return None
    if type(nilai) is not int or nilai <= 0:
        raise InputQueryTidakSah("siswa_id akun tidak sah")
    return nilai


def snapshot_akun(akun_mentah: Iterable[Mapping[str, object]]) -> Tuple[AkunPublik, ...]:
    """Salin hanya empat field allow-list dari satu hasil ``auth.muat_akun``.

    Mapping asal tidak disimpan. Field seperti garam, kunci, iterasi, token,
    sandi, atau metadata asing otomatis gugur secara konstruksi.
    """
    hasil = []
    id_terlihat = set()
    pengguna_terlihat = set()
    for mentah in akun_mentah:
        if not isinstance(mentah, Mapping):
            raise InputQueryTidakSah("record akun bukan mapping")
        pengguna = _teks_wajib(mentah.get("pengguna"), "pengguna", maksimum=80)
        peran = mentah.get("peran", "guru")
        if peran not in PERAN_DIIJINKAN:
            raise InputQueryTidakSah("peran akun tidak dikenal")
        id_akun = _id_opsional(mentah.get("id_akun"))
        siswa_id = _siswa_id_opsional(mentah.get("siswa_id"))
        if peran != "murid" and siswa_id is not None:
            raise InputQueryTidakSah("hanya akun murid boleh memiliki siswa_id")
        kunci_pengguna = pengguna.casefold()
        if kunci_pengguna in pengguna_terlihat:
            raise InputQueryTidakSah("pengguna akun duplikat")
        pengguna_terlihat.add(kunci_pengguna)
        if id_akun is not None:
            if id_akun in id_terlihat:
                raise InputQueryTidakSah("id_akun duplikat")
            id_terlihat.add(id_akun)
        hasil.append(AkunPublik(id_akun, pengguna, peran, siswa_id))
    return tuple(sorted(
        hasil,
        key=lambda akun: (akun.peran, akun.pengguna.casefold(), akun.id_akun or ""),
    ))


def _nilai(baris, nama: str, posisi: int):
    try:
        return baris[nama]
    except (IndexError, KeyError, TypeError):
        return baris[posisi]


def buat_konteks(kon, akun_mentah: Iterable[Mapping[str, object]]) -> KonteksAdmin:
    """Ambil snapshot akun sekali dan identitas siswa dengan satu SELECT."""
    akun = snapshot_akun(akun_mentah)
    baris_siswa = kon.execute(
        "SELECT id,nama,tingkat,pemilik FROM siswa ORDER BY id"
    ).fetchall()
    siswa = tuple(
        IdentitasSiswa(
            int(_nilai(baris, "id", 0)),
            str(_nilai(baris, "nama", 1)),
            str(_nilai(baris, "tingkat", 2)),
            str(_nilai(baris, "pemilik", 3) or ""),
        )
        for baris in baris_siswa
    )
    siswa_by_id = {item.id: item for item in siswa}
    nama_ke_siswa = {}
    for item in siswa:
        nama_ke_siswa.setdefault(item.nama.casefold(), []).append(item)

    masalah = []
    for item in akun:
        if item.peran != "murid":
            continue
        if item.siswa_id is not None:
            if item.siswa_id not in siswa_by_id:
                masalah.append(LoginBermasalah(
                    item.id_akun, item.pengguna, item.siswa_id,
                    "orphan_login", 0,
                ))
            continue
        kandidat = nama_ke_siswa.get(item.pengguna.casefold(), ())
        if not kandidat:
            status = "legacy_orphan_login"
        elif len(kandidat) == 1:
            status = "legacy_login_unverified"
        else:
            status = "legacy_same_name_ambiguous"
        masalah.append(LoginBermasalah(
            item.id_akun, item.pengguna, None, status, len(kandidat)
        ))
    return KonteksAdmin(
        akun,
        siswa,
        tuple(sorted(
            masalah,
            key=lambda item: (item.status, item.pengguna.casefold(), item.id_akun or ""),
        )),
    )


def _sekarang_wib(nilai: Optional[datetime]) -> datetime:
    zona = timezone(timedelta(hours=7))
    if nilai is None:
        return datetime.now(zona)
    if not isinstance(nilai, datetime):
        raise InputQueryTidakSah("sekarang_wib harus datetime")
    if nilai.tzinfo is None:
        return nilai.replace(tzinfo=zona)
    return nilai.astimezone(zona)


@dataclass(frozen=True)
class _IndeksKonteks:
    akun_by_pengguna: Mapping[str, AkunPublik]
    login_explicit: Mapping[int, Tuple[AkunPublik, ...]]
    login_legacy_per_nama: Mapping[str, Tuple[AkunPublik, ...]]
    jumlah_nama_siswa: Mapping[str, int]


def _buat_indeks(konteks: KonteksAdmin) -> _IndeksKonteks:
    akun_by_pengguna = {akun.pengguna: akun for akun in konteks.akun}
    explicit = {}
    legacy = {}
    for akun in konteks.akun:
        if akun.peran != "murid":
            continue
        if akun.siswa_id is None:
            legacy.setdefault(akun.pengguna.casefold(), []).append(akun)
        else:
            explicit.setdefault(akun.siswa_id, []).append(akun)
    jumlah_nama = {}
    for siswa in konteks.siswa:
        kunci = siswa.nama.casefold()
        jumlah_nama[kunci] = jumlah_nama.get(kunci, 0) + 1
    return _IndeksKonteks(
        akun_by_pengguna,
        {kunci: tuple(nilai) for kunci, nilai in explicit.items()},
        {kunci: tuple(nilai) for kunci, nilai in legacy.items()},
        jumlah_nama,
    )


def _status_siswa(
    identitas: IdentitasSiswa,
    indeks: _IndeksKonteks,
) -> Tuple[Tuple[str, ...], Optional[AkunPublik], Optional[AkunPublik], str]:
    akun_by_pengguna = indeks.akun_by_pengguna
    explicit = indeks.login_explicit.get(identitas.id, ())
    legacy = indeks.login_legacy_per_nama.get(identitas.nama.casefold(), ())
    status = []

    owner = akun_by_pengguna.get(identitas.pemilik)
    if not identitas.pemilik:
        kategori = "pemilik_kosong"
        status.append("owner_empty")
    elif owner is None:
        kategori = "pemilik_tanpa_akun"
        status.append("owner_without_account")
    elif owner.peran == "admin":
        kategori = "pengelola"
        status.append("owner_admin")
    elif owner.peran == "guru":
        kategori = "orang_tua"
    else:
        kategori = "pemilik_tanpa_akun"
        status.append("owner_without_account")

    login = explicit[0] if len(explicit) == 1 else None
    if not explicit:
        status.append("student_without_login")
    elif len(explicit) > 1:
        status.append("duplicate_explicit_login")

    legacy_login = legacy[0] if len(legacy) == 1 else None
    if legacy:
        if indeks.jumlah_nama_siswa.get(identitas.nama.casefold(), 0) > 1 or len(legacy) > 1:
            status.append("legacy_same_name_ambiguous")
        else:
            status.append("legacy_login_unverified")

    return tuple(status), login, legacy_login, kategori


def _siswa_ringkas_dari_baris(baris, indeks: _IndeksKonteks) -> SiswaRingkas:
    identitas = IdentitasSiswa(
        int(_nilai(baris, "id", 0)),
        str(_nilai(baris, "nama", 1)),
        str(_nilai(baris, "tingkat", 2)),
        str(_nilai(baris, "pemilik", 3) or ""),
    )
    status, login, _legacy, kategori = _status_siswa(identitas, indeks)
    owner = indeks.akun_by_pengguna.get(identitas.pemilik)
    return SiswaRingkas(
        identitas.id,
        identitas.nama,
        identitas.tingkat,
        identitas.pemilik,
        None if owner is None else owner.id_akun,
        kategori,
        None if login is None else login.id_akun,
        None if login is None else login.pengguna,
        int(_nilai(baris, "jumlah_sesi", 4) or 0),
        _nilai(baris, "aktivitas_terakhir", 5),
        status,
    )


def _paginasi(halaman, per_halaman) -> Tuple[int, int]:
    if type(halaman) is not int or halaman < 1:
        raise InputQueryTidakSah("halaman harus bilangan positif")
    if type(per_halaman) is not int or not 1 <= per_halaman <= BATAS_MAKSIMUM:
        raise InputQueryTidakSah("per_halaman harus 1..100")
    return halaman, per_halaman


def _jumlah_halaman(total: int, per_halaman: int) -> int:
    return max(1, int(math.ceil(total / per_halaman)))


def _cari(nilai: str) -> str:
    if type(nilai) is not str or len(nilai) > 80 or any(ord(c) < 32 for c in nilai):
        raise InputQueryTidakSah("pencarian tidak sah")
    return nilai.strip()


def _pola_like_literal(nilai: str) -> str:
    """Escape wildcard SQL agar `%`, `_`, dan `\\` dicari sebagai karakter."""
    return "%" + nilai.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def ringkasan_admin(
    kon,
    konteks: KonteksAdmin,
    *,
    sekarang_wib: Optional[datetime] = None,
    batas_aktivitas: int = 10,
) -> RingkasanAdmin:
    """Ringkasan administratif; semua sesi termasuk yang dibatalkan."""
    if type(batas_aktivitas) is not int or not 1 <= batas_aktivitas <= 10:
        raise InputQueryTidakSah("batas aktivitas harus 1..10")
    kini = _sekarang_wib(sekarang_wib)
    teks_kini = kini.strftime("%Y-%m-%d %H:%M:%S")
    agregat = kon.execute(
        """SELECT COUNT(*) AS jumlah,
                  SUM(CASE WHEN datetime(COALESCE(selesai,mulai,dibuat,tanggal))
                                BETWEEN datetime(?,'-7 days') AND datetime(?) THEN 1 ELSE 0 END) AS tujuh,
                  SUM(CASE WHEN datetime(COALESCE(selesai,mulai,dibuat,tanggal))
                                BETWEEN datetime(?,'-30 days') AND datetime(?) THEN 1 ELSE 0 END) AS tiga_puluh,
                  SUM(CASE WHEN dibatalkan IS NOT NULL THEN 1 ELSE 0 END) AS dibatalkan
           FROM sesi""",
        (teks_kini, teks_kini, teks_kini, teks_kini),
    ).fetchone()
    aktivitas = kon.execute(
        """SELECT s.id AS sesi_id,w.id AS siswa_id,w.nama,w.pemilik,s.level,s.tanggal,
                  COALESCE(s.selesai,s.mulai,s.dibuat,s.tanggal) AS waktu_aktivitas,
                  CASE WHEN s.dibatalkan IS NULL THEN 0 ELSE 1 END AS dibatalkan
           FROM sesi s JOIN siswa w ON w.id=s.siswa_id
           ORDER BY waktu_aktivitas DESC,s.id DESC LIMIT ?""",
        (batas_aktivitas,),
    ).fetchall()

    indeks = _buat_indeks(konteks)
    status_semua = []
    for identitas in konteks.siswa:
        status_semua.extend(_status_siswa(identitas, indeks)[0])
    hitung = []
    for kode in (
        "student_without_login",
        "owner_without_account",
        "owner_empty",
        "legacy_same_name_ambiguous",
    ):
        jumlah = status_semua.count(kode)
        if kode == "legacy_same_name_ambiguous":
            jumlah = sum(
                masalah.status == kode for masalah in konteks.login_bermasalah
            )
        if jumlah:
            hitung.append(HitungPerhatian(kode, jumlah))
    orphan = sum(
        masalah.status in ("orphan_login", "legacy_orphan_login")
        for masalah in konteks.login_bermasalah
    )
    if orphan:
        hitung.append(HitungPerhatian("orphan_login", orphan))

    return RingkasanAdmin(
        sum(akun.peran == "guru" for akun in konteks.akun),
        len(konteks.siswa),
        sum(akun.peran == "murid" for akun in konteks.akun),
        int(_nilai(agregat, "jumlah", 0) or 0),
        int(_nilai(agregat, "tujuh", 1) or 0),
        int(_nilai(agregat, "tiga_puluh", 2) or 0),
        int(_nilai(agregat, "dibatalkan", 3) or 0),
        tuple(hitung),
        konteks.login_bermasalah[:BATAS_BAWAAN],
        tuple(
            AktivitasSesi(
                int(_nilai(baris, "sesi_id", 0)),
                int(_nilai(baris, "siswa_id", 1)),
                str(_nilai(baris, "nama", 2)),
                str(_nilai(baris, "pemilik", 3) or ""),
                str(_nilai(baris, "level", 4)),
                str(_nilai(baris, "tanggal", 5)),
                str(_nilai(baris, "waktu_aktivitas", 6)),
                bool(_nilai(baris, "dibatalkan", 7)),
            )
            for baris in aktivitas
        ),
    )


def _keluarga_semua(kon, konteks: KonteksAdmin) -> Tuple[KeluargaRingkas, ...]:
    kelompok = kon.execute(
        """SELECT w.pemilik,COUNT(DISTINCT w.id) AS jumlah_siswa,
                  COUNT(s.id) AS jumlah_sesi,
                  MAX(COALESCE(s.selesai,s.mulai,s.dibuat,s.tanggal)) AS aktivitas_terakhir
           FROM siswa w LEFT JOIN sesi s ON s.siswa_id=w.id
           GROUP BY w.pemilik ORDER BY lower(w.pemilik),w.pemilik"""
    ).fetchall()
    data_kelompok = {
        str(_nilai(baris, "pemilik", 0) or ""): (
            int(_nilai(baris, "jumlah_siswa", 1)),
            int(_nilai(baris, "jumlah_sesi", 2)),
            _nilai(baris, "aktivitas_terakhir", 3),
        )
        for baris in kelompok
    }
    akun_by_pengguna = _buat_indeks(konteks).akun_by_pengguna
    hasil = []
    for akun in konteks.akun:
        if akun.peran == "guru":
            kategori = "orang_tua"
        elif akun.peran == "admin" and akun.pengguna in data_kelompok:
            kategori = "pengelola"
        else:
            continue
        jumlah_siswa, jumlah_sesi, terakhir = data_kelompok.get(
            akun.pengguna, (0, 0, None)
        )
        status = []
        if akun.id_akun is None:
            status.append("account_missing_id")
        if jumlah_siswa == 0:
            status.append("no_students")
        if kategori == "pengelola":
            status.append("owner_admin")
        hasil.append(KeluargaRingkas(
            akun.id_akun,
            akun.pengguna,
            kategori,
            jumlah_siswa,
            jumlah_sesi,
            terakhir,
            tuple(status),
        ))
    for pemilik, (jumlah_siswa, jumlah_sesi, terakhir) in data_kelompok.items():
        pemilik_akun = akun_by_pengguna.get(pemilik)
        if pemilik_akun is not None and pemilik_akun.peran in ("guru", "admin"):
            continue
        if pemilik:
            hasil.append(KeluargaRingkas(
                None, pemilik, "pemilik_tanpa_akun", jumlah_siswa, jumlah_sesi,
                terakhir, ("owner_without_account",),
            ))
        else:
            hasil.append(KeluargaRingkas(
                None, "", "pemilik_kosong", jumlah_siswa, jumlah_sesi,
                terakhir, ("owner_empty",),
            ))
    return tuple(sorted(
        hasil,
        key=lambda item: (
            item.pengguna.casefold(), item.pengguna,
            item.id_akun or "", item.kategori,
        ),
    ))


def daftar_keluarga(
    kon,
    konteks: KonteksAdmin,
    *,
    cari: str = "",
    status: str = "semua",
    memiliki_anak: str = "semua",
    halaman: int = 1,
    per_halaman: int = BATAS_BAWAAN,
) -> HalamanKeluarga:
    """Daftar keluarga. Pencarian alias literal dilakukan pada snapshot."""
    halaman, per_halaman = _paginasi(halaman, per_halaman)
    cari = _cari(cari)
    if status not in ("semua", "perlu_perhatian"):
        raise InputQueryTidakSah("filter status keluarga tidak sah")
    if memiliki_anak not in ("semua", "ya", "tidak"):
        raise InputQueryTidakSah("filter anak tidak sah")
    data = list(_keluarga_semua(kon, konteks))
    if cari:
        needle = cari.casefold()
        data = [item for item in data if needle in item.pengguna.casefold()]
    if status == "perlu_perhatian":
        data = [item for item in data if item.status]
    if memiliki_anak == "ya":
        data = [item for item in data if item.jumlah_siswa > 0]
    elif memiliki_anak == "tidak":
        data = [item for item in data if item.jumlah_siswa == 0]
    total = len(data)
    awal = (halaman - 1) * per_halaman
    return HalamanKeluarga(
        tuple(data[awal:awal + per_halaman]),
        total,
        halaman,
        per_halaman,
        _jumlah_halaman(total, per_halaman),
        cari,
        status,
        memiliki_anak,
    )


def _klausa_siswa(
    konteks: KonteksAdmin,
    *,
    cari: str,
    tingkat: str,
    keluarga_id: str,
):
    klausa = []
    argumen = []
    # Cari sesudah proyeksi agar alias login dapat dicari tanpa daftar IN
    # ribuan ID atau wildcard SQL. Snapshot tidak pernah mengaitkan login warisan.
    if tingkat:
        klausa.append("w.tingkat=?")
        argumen.append(tingkat)
    if keluarga_id:
        akun = next(
            (
                item for item in konteks.akun
                if item.id_akun == keluarga_id and item.peran in ("guru", "admin")
            ),
            None,
        )
        if akun is None:
            raise InputQueryTidakSah("keluarga_id tidak dikenal")
        klausa.append("w.pemilik=?")
        argumen.append(akun.pengguna)
    where = " WHERE " + " AND ".join(klausa) if klausa else ""
    return where, tuple(argumen)


def daftar_siswa(
    kon,
    konteks: KonteksAdmin,
    *,
    cari: str = "",
    tingkat: str = "",
    status: str = "semua",
    keluarga_id: str = "",
    halaman: int = 1,
    per_halaman: int = BATAS_BAWAAN,
) -> HalamanSiswa:
    """Daftar siswa beragregat satu query; status dipaginasi setelah proyeksi."""
    halaman, per_halaman = _paginasi(halaman, per_halaman)
    cari = _cari(cari)
    if tingkat and tingkat not in LEVEL_DIIJINKAN:
        raise InputQueryTidakSah("filter tingkat tidak sah")
    if status != "semua" and status not in STATUS_SISWA:
        raise InputQueryTidakSah("filter status siswa tidak sah")
    keluarga_id = keluarga_id.strip()
    where, argumen = _klausa_siswa(
        konteks, cari=cari, tingkat=tingkat, keluarga_id=keluarga_id
    )
    baris = kon.execute(
        """SELECT w.id,w.nama,w.tingkat,w.pemilik,
                  COUNT(s.id) AS jumlah_sesi,
                  MAX(COALESCE(s.selesai,s.mulai,s.dibuat,s.tanggal)) AS aktivitas_terakhir
           FROM siswa w LEFT JOIN sesi s ON s.siswa_id=w.id"""
        + where
        + " GROUP BY w.id,w.nama,w.tingkat,w.pemilik ORDER BY lower(w.nama),w.nama,w.id",
        argumen,
    ).fetchall()
    indeks = _buat_indeks(konteks)
    data = [_siswa_ringkas_dari_baris(item, indeks) for item in baris]
    if cari:
        dicari = cari.casefold()
        data = [item for item in data if any(
            dicari in nilai.casefold()
            for nilai in (item.nama, item.pemilik, item.login_pengguna or "")
        )]
    if status != "semua":
        data = [item for item in data if status in item.status]
    total = len(data)
    awal = (halaman - 1) * per_halaman
    return HalamanSiswa(
        tuple(data[awal:awal + per_halaman]),
        total,
        halaman,
        per_halaman,
        _jumlah_halaman(total, per_halaman),
        cari,
        tingkat,
        status,
        keluarga_id,
    )


def detail_keluarga(
    kon,
    konteks: KonteksAdmin,
    id_akun: str,
    *,
    halaman: int = 1,
    per_halaman: int = BATAS_BAWAAN,
) -> Optional[DetailKeluarga]:
    """Detail berdasarkan generation ID, bukan username dari URL."""
    id_akun = _teks_wajib(id_akun, "id_akun", maksimum=96)
    keluarga = next(
        (item for item in _keluarga_semua(kon, konteks) if item.id_akun == id_akun),
        None,
    )
    if keluarga is None:
        return None
    siswa = daftar_siswa(
        kon,
        konteks,
        keluarga_id=id_akun,
        halaman=halaman,
        per_halaman=per_halaman,
    )
    return DetailKeluarga(keluarga, siswa)


def detail_siswa(
    kon,
    konteks: KonteksAdmin,
    siswa_id: int,
    *,
    batas_sesi: int = 10,
) -> Optional[DetailSiswa]:
    """Detail administratif siswa; tidak membaca jawaban atau diagnosis."""
    if type(siswa_id) is not int or siswa_id <= 0:
        raise InputQueryTidakSah("siswa_id tidak sah")
    if type(batas_sesi) is not int or not 1 <= batas_sesi <= 25:
        raise InputQueryTidakSah("batas sesi harus 1..25")
    baris = kon.execute(
        """SELECT w.id,w.nama,w.tingkat,w.pemilik,
                  COUNT(s.id) AS jumlah_sesi,
                  MAX(COALESCE(s.selesai,s.mulai,s.dibuat,s.tanggal)) AS aktivitas_terakhir
           FROM siswa w LEFT JOIN sesi s ON s.siswa_id=w.id
           WHERE w.id=? GROUP BY w.id,w.nama,w.tingkat,w.pemilik""",
        (siswa_id,),
    ).fetchone()
    if baris is None:
        return None
    sesi = kon.execute(
        """SELECT id,tanggal,COALESCE(selesai,mulai,dibuat,tanggal) AS waktu_aktivitas,
                  level,CASE WHEN dibatalkan IS NULL THEN 0 ELSE 1 END AS dibatalkan
           FROM sesi WHERE siswa_id=?
           ORDER BY waktu_aktivitas DESC,id DESC LIMIT ?""",
        (siswa_id, batas_sesi),
    ).fetchall()
    indeks = _buat_indeks(konteks)
    return DetailSiswa(
        _siswa_ringkas_dari_baris(baris, indeks),
        tuple(
            SesiRingkas(
                int(_nilai(item, "id", 0)),
                str(_nilai(item, "tanggal", 1)),
                str(_nilai(item, "waktu_aktivitas", 2)),
                str(_nilai(item, "level", 3)),
                bool(_nilai(item, "dibatalkan", 4)),
            )
            for item in sesi
        ),
    )
