"""Autentikasi halaman guru.

Wajib aktif begitu aplikasi ini bisa dijangkau dari luar mesin sendiri:
halamannya memuat jawaban dan diagnosis anak, dan tanpa palang ini siapa
pun yang tahu alamatnya bisa membacanya.

Bentuknya HTTP Basic. Cukup untuk satu pengguna di balik HTTPS, tidak
menambah dependensi, dan tidak perlu tabel sesi. Yang TIDAK boleh:
menjalankannya tanpa HTTPS, karena Basic mengirim sandi sebagai teks
ter-base64 yang bisa dibaca siapa saja di jaringan.

Sandi disimpan sebagai hash PBKDF2 di berkas, bukan di kode dan bukan
sebagai teks biasa. Dibandingkan dengan compare_digest supaya lama
pembandingan tidak membocorkan berapa karakter yang sudah cocok.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from json_storage import (
    GalatPenyimpananJSON,
    TIDAK_ADA,
    baca_json_ketat,
    transaksi_json,
    tulis_json_atomik,
)

BERKAS_SANDI = Path(
    os.environ.get("OSN_BERKAS_SANDI", Path(__file__).resolve().parent / "sandi.json")
)

# PBKDF2-HMAC-SHA256, bukan scrypt.
#
# scrypt lebih tahan serangan perangkat keras, TAPI hashlib.scrypt hanya ada
# kalau Python dibangun dengan OpenSSL yang mendukungnya — ada di VPS
# (Python 3.12) dan TIDAK ADA di Mac ini (Python 3.9.6 bawaan sistem).
# Memakainya berarti sandi yang disetel di satu mesin tidak bisa diverifikasi
# di mesin lain, dan kegagalannya baru muncul saat login, bukan saat menyetel.
#
# pbkdf2_hmac tersedia di keduanya. 600.000 iterasi mengikuti anjuran OWASP
# 2023 untuk SHA-256, dan diukur ~0,2 detik di mesin ini — tidak terasa saat
# login, tapi mahal bila dicoba jutaan kali.
#
# OSN_PBKDF2_ITERASI hanya untuk test (__tests__/conftest.py menyetelnya
# rendah): jumlah iterasi ikut tersimpan di berkas sandi dan diverifikasi
# dengan angka yang sama, jadi logika yang diuji tidak berubah.
_ITERASI = int(os.environ.get("OSN_PBKDF2_ITERASI", "600000"))

# Garam/kunci umpan untuk jalur akun-tak-dikenal agar waktu tetap.
# Nilai konstan ini membuat PBKDF2 tetap dijalankan walau nama tidak ada.
_UMPAN_GARAM = bytes.fromhex("aa" * 16)
_UMPAN_KUNCI = bytes.fromhex("bb" * 32)
_AWAL_ID_AKUN = "akun_"
_PANJANG_HEX_ID_AKUN = 32
PERAN = ("admin", "guru", "murid")


@dataclass(frozen=True)
class PrincipalAkun:
    """Snapshot akun kanonik setelah credential diverifikasi."""

    pengguna: str
    peran: str
    id_akun: str
    revisi_auth: int


def id_akun_sah(nilai) -> bool:
    """True hanya untuk ID acak non-bermakna dengan bentuk kanonik."""
    if type(nilai) is not str or not nilai.startswith(_AWAL_ID_AKUN):
        return False
    ekor = nilai[len(_AWAL_ID_AKUN):]
    return len(ekor) == _PANJANG_HEX_ID_AKUN and all(
        karakter in "0123456789abcdef" for karakter in ekor
    )


def _buat_id_akun() -> str:
    return _AWAL_ID_AKUN + secrets.token_hex(_PANJANG_HEX_ID_AKUN // 2)


def _tulis_akun_atomik(data: dict, path: Path) -> None:
    """Tulis JSON privat; aman dipanggil di dalam transaksi yang sama."""
    tulis_json_atomik(data, path, indent=2)


def revisi_auth(akun: dict) -> int:
    """Revisi efektif akun; akun legacy tanpa field bernilai nol."""
    nilai = akun.get("revisi_auth", 0)
    if type(nilai) is not int or nilai < 0:
        raise ValueError("revisi_auth akun tidak sah")
    return nilai


def _validasi_daftar_akun(akun: list[dict], *, bentuk_multi: bool) -> None:
    nama_terlihat = set()
    id_terlihat = set()
    for item in akun:
        if not isinstance(item, dict):
            raise ValueError("berkas akun tidak sah")
        pengguna = item.get("pengguna")
        if type(pengguna) is not str or not pengguna.strip():
            raise ValueError("berkas akun tidak sah")
        nama = pengguna.strip().casefold()
        if nama in nama_terlihat:
            raise ValueError("nama akun duplikat")
        nama_terlihat.add(nama)
        peran = item.get("peran", "guru")
        if peran not in PERAN or (bentuk_multi and "peran" not in item):
            raise ValueError("peran akun tidak sah")
        revisi_auth(item)
        id_akun = item.get("id_akun")
        if id_akun is not None:
            if not id_akun_sah(id_akun):
                raise ValueError("id_akun tidak sah")
            if id_akun in id_terlihat:
                raise ValueError("id_akun duplikat")
            id_terlihat.add(id_akun)


def _data_akun_valid(data) -> bool:
    if not isinstance(data, dict):
        return False
    try:
        if "akun" in data:
            isi = data["akun"]
            if not isinstance(isi, list):
                return False
            akun = [dict(item) if isinstance(item, dict) else item for item in isi]
            _validasi_daftar_akun(akun, bentuk_multi=True)
        elif isinstance(data.get("pengguna"), str):
            _validasi_daftar_akun([dict(data)], bentuk_multi=False)
        else:
            return False
    except ValueError:
        return False
    return True


def _baca_akun_untuk_tulis(path: Path) -> tuple[dict | None, list[dict], bool]:
    """Baca state writer ketat; ``null`` bukan berkas yang belum ada."""
    try:
        mentah = baca_json_ketat(path, bawaan=TIDAK_ADA)
    except GalatPenyimpananJSON as galat:
        raise ValueError("berkas akun tidak sah") from galat
    if mentah is TIDAK_ADA:
        return None, [], False
    if not isinstance(mentah, dict):
        raise ValueError("berkas akun tidak sah")
    if "akun" in mentah:
        isi = mentah["akun"]
        if not isinstance(isi, list):
            raise ValueError("berkas akun tidak sah")
        akun = [dict(item) if isinstance(item, dict) else item for item in isi]
        _validasi_daftar_akun(akun, bentuk_multi=True)
        return mentah, akun, True
    if isinstance(mentah.get("pengguna"), str):
        akun = [dict(mentah)]
        _validasi_daftar_akun(akun, bentuk_multi=False)
        return mentah, akun, False
    raise ValueError("berkas akun tidak sah")


def _bungkus_akun(mentah: dict | None, akun: list[dict]) -> dict:
    """Pertahankan envelope; konversi legacy memberi peran eksplisit.

    ``operasi_admin`` selalu metadata envelope, termasuk jika ditambahkan pada
    bentuk legacy oleh adapter recovery sebelum akun kedua dibuat.
    """
    bentuk_multi = bool(mentah and "akun" in mentah)
    hasil = dict(mentah) if bentuk_multi else {}
    if bentuk_multi:
        hasil["akun"] = akun
    else:
        if mentah and "operasi_admin" in mentah:
            hasil["operasi_admin"] = mentah["operasi_admin"]
        hasil["akun"] = []
        for item in akun:
            salinan = dict(item)
            salinan.pop("operasi_admin", None)
            salinan["peran"] = salinan.get("peran", "guru")
            hasil["akun"].append(salinan)
    return hasil


def buat_hash(sandi: str) -> dict:
    garam = secrets.token_bytes(16)
    kunci = hashlib.pbkdf2_hmac("sha256", sandi.encode(), garam, _ITERASI, dklen=32)
    return {
        "garam": binascii.hexlify(garam).decode(),
        "kunci": binascii.hexlify(kunci).decode(),
        "iterasi": _ITERASI,
    }


def simpan_sandi(sandi: str, pengguna: str = "guru", path: Path | None = None) -> Path:
    """Setel/ganti sandi satu akun tanpa menghapus akun lain.

    PERNAH SALAH (25 Agustus 2026, tertangkap sebelum dipakai anak): versi
    pertama selalu menulis ulang berkas jadi bentuk lama satu-akun, jadi
    begitu guru mengganti sandinya lewat halaman akun, SELURUH akun murid
    lenyap. Anak tiba-tiba tidak bisa masuk, dan tidak ada pesan galat di
    mana pun — berkasnya memang tertulis "berhasil".

    Sekarang: kalau berkas sudah memuat banyak akun, hanya baris akun yang
    bersangkutan yang diperbarui; sisanya dibiarkan apa adanya.
    """
    p = path or BERKAS_SANDI
    hash_baru = buat_hash(sandi)
    with transaksi_json(p) as tujuan:
        mentah, akun, bentuk_multi = _baca_akun_untuk_tulis(tujuan)

        # Berkas belum ada / masih bentuk lama satu-akun untuk pengguna yang sama:
        # pertahankan bentuk lama supaya format tidak berubah tanpa alasan.
        if mentah is None:
            _tulis_akun_atomik(
                {
                    "pengguna": pengguna,
                    "id_akun": _buat_id_akun(),
                    "revisi_auth": 1,
                    **hash_baru,
                },
                tujuan,
            )
            return p
        if not bentuk_multi and len(akun) == 1 and akun[0]["pengguna"] == pengguna:
            satu = dict(akun[0])
            satu.update(hash_baru)
            satu.setdefault("id_akun", _buat_id_akun())
            satu["revisi_auth"] = revisi_auth(satu) + 1
            # Pertahankan bentuk lama satu-akun dan semantik peran implisitnya.
            satu.pop("peran", None)
            _tulis_akun_atomik(satu, tujuan)
            return p

        ketemu = False
        for a in akun:
            if a["pengguna"].strip().lower() == pengguna.strip().lower():
                a.update(hash_baru)
                a.setdefault("peran", "guru")
                a.setdefault("id_akun", _buat_id_akun())
                a["revisi_auth"] = revisi_auth(a) + 1
                ketemu = True
        if not ketemu:
            id_akun = _buat_id_akun()
            while any(a.get("id_akun") == id_akun for a in akun):
                id_akun = _buat_id_akun()
            akun.append({
                "pengguna": pengguna,
                "peran": "guru",
                "id_akun": id_akun,
                "revisi_auth": 1,
                **hash_baru,
            })

        _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
        return p


def muat_sandi(path: Path | None = None) -> dict | None:
    p = path or BERKAS_SANDI
    try:
        data = baca_json_ketat(p, bawaan=TIDAK_ADA)
    except GalatPenyimpananJSON:
        return None
    if data is TIDAK_ADA or not _data_akun_valid(data):
        return None
    return data


def periksa(pengguna: str, sandi: str, data: dict | None = None) -> bool:
    """Bandingkan dengan waktu tetap.

    Nama pengguna ikut dibandingkan dengan compare_digest, bukan '==', supaya
    tidak ada jalur yang lebih cepat gagal untuk nama yang salah.

    PERNAH SALAH (25 Agustus 2026): saat berkas sudah bentuk multi-akun
    ({"akun": [...]}), fungsi ini membaca d["pengguna"] yang tidak ada di
    situ dan melempar KeyError. Akibatnya begitu satu akun murid dibuat,
    GURU TIDAK BISA MENGGANTI SANDINYA SAMA SEKALI — halaman akun langsung
    500. Tidak tertangkap test mana pun karena tidak ada yang menguji urutan
    "tambah murid, lalu guru ganti sandi".
    """
    if data is None:
        mentah = muat_sandi()
        if not mentah:
            return False
        # Bentuk multi-akun: cari akun yang namanya cocok, lalu periksa
        # akun itu saja. Bentuk lama satu-akun dipakai apa adanya.
        if "akun" in mentah:
            d = None
            for a in _normalisasi(mentah):
                if a["pengguna"].strip().lower() == pengguna.strip().lower():
                    d = a
                    break
            if d is None:
                # waktu-tetap: jalankan PBKDF2 umpan supaya durasi serupa
                _ = hashlib.pbkdf2_hmac("sha256", sandi.encode(), _UMPAN_GARAM, _ITERASI, dklen=32)
                hmac.compare_digest(_, _UMPAN_KUNCI)
                return False
        else:
            d = mentah
    else:
        d = data

    if (
        not d or type(d.get("pengguna")) is not str
        or d.get("peran", "guru") not in PERAN
    ):
        return False
    try:
        revisi_auth(d)
        _validasi_hash_akun(d)
    except ValueError:
        return False

    nama_cocok = hmac.compare_digest(pengguna.encode(), d["pengguna"].encode())

    try:
        garam = binascii.unhexlify(d["garam"])
        harap = binascii.unhexlify(d["kunci"])
        coba = hashlib.pbkdf2_hmac(
            "sha256",
            sandi.encode(),
            garam,
            int(d.get("iterasi", _ITERASI)),
            dklen=len(harap),
        )
    except (binascii.Error, KeyError, OverflowError, TypeError, ValueError):
        return False
    if len(garam) < 1 or len(harap) < 1:
        return False

    sandi_cocok = hmac.compare_digest(coba, harap)
    return nama_cocok and sandi_cocok


def dari_header(header: str | None) -> tuple[str, str] | None:
    """Uraikan header Authorization: Basic <base64>."""
    if not header or not header.startswith("Basic "):
        return None
    try:
        mentah = base64.b64decode(header[6:]).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in mentah:
        return None
    pengguna, _, sandi = mentah.partition(":")
    return pengguna, sandi


def wajib_sandi() -> bool:
    """Apakah palang ini aktif.

    Aktif kalau berkas sandi ada. Dengan begitu pemakaian di localhost tetap
    tanpa hambatan, sementara deploy WAJIB membuat berkas sandinya — dan
    kalau lupa, ada palang kedua di serve.py yang menolak berjalan terbuka
    ke jaringan tanpa sandi.
    """
    return BERKAS_SANDI.exists()


# ── Peran & multi-akun (Fase 4) ──────────────────────────────────────────
#
# Bentuk berkas lama (satu guru) tetap sah:
#   {"pengguna": "guru", "garam": ..., "kunci": ..., "iterasi": ...}
#
# Bentuk baru (multi-akun):
#   {"akun": [{"pengguna": "guru", "peran": "guru", ...hash...},
#             {"pengguna": "feby",  "peran": "murid", ...hash...,
#              "siswa_id": 7}]}
#
# Tiga peran (multi-keluarga):
#   admin = pengelola produk, melihat semua keluarga;
#   guru  = orang tua, hanya melihat siswa ber-`pemilik` namanya;
#   murid = anak, terikat ke satu siswa lewat `siswa_id` (multi-keluarga
#           memutus kaitan nama-akun == nama-siswa: nama tampilan boleh
#           dobel antar keluarga, nama login tetap unik global).
#
# Migrasi satu-arah terjadi saat muat: bentuk lama dibaca sebagai satu akun
# ber-peran "guru". Tidak pernah ditulis balik otomatis — penulisan hanya
# lewat simpan_akun() yang selalu menulis bentuk baru.


def _normalisasi(data: dict | None) -> list[dict]:
    """Bentuk lama atau baru -> daftar akun seragam."""
    if not data:
        return []
    if "akun" in data:
        return list(data["akun"])
    # bentuk lama: satu akun tanpa kunci peran
    return [{**data, "peran": "guru"}]


def muat_akun(path: Path | None = None) -> list[dict]:
    return _normalisasi(muat_sandi(path))


def _validasi_hash_akun(akun: dict) -> None:
    """Pastikan hash dapat dibaca sebelum akun dipakai sebagai principal."""
    try:
        garam_teks = akun["garam"]
        kunci_teks = akun["kunci"]
        if type(garam_teks) is not str or type(kunci_teks) is not str:
            raise ValueError("hash akun tidak sah")
        garam = binascii.unhexlify(garam_teks)
        kunci = binascii.unhexlify(kunci_teks)
        iterasi = akun.get("iterasi", _ITERASI)
    except (KeyError, TypeError, ValueError, binascii.Error) as galat:
        raise ValueError("hash akun tidak sah") from galat
    if (
        len(garam) < 1 or len(kunci) < 1 or type(iterasi) is not int
        or iterasi < 1
    ):
        raise ValueError("hash akun tidak sah")


def pastikan_metadata_auth(path: Path | None = None) -> bool:
    """Migrasikan ID dan revisi akun legacy secara atomik/idempoten."""
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        if mentah is None:
            return False

        terlihat = {
            item["id_akun"] for item in akun if item.get("id_akun") is not None
        }
        berubah = False
        for item in akun:
            _validasi_hash_akun(item)
            nilai = item.get("id_akun")
            if nilai is None:
                nilai = _buat_id_akun()
                while nilai in terlihat:
                    nilai = _buat_id_akun()
                item["id_akun"] = nilai
                terlihat.add(nilai)
                berubah = True
            if "revisi_auth" not in item:
                item["revisi_auth"] = 0
                berubah = True
        if not berubah:
            return False

        hasil = _bungkus_akun(mentah, akun) if bentuk_multi else akun[0]
        _tulis_akun_atomik(hasil, tujuan)
        return True


def pastikan_id_akun(path: Path | None = None) -> bool:
    """Alias kompatibilitas untuk migrasi metadata autentikasi."""
    return pastikan_metadata_auth(path)


def cari_akun(pengguna: str, path: Path | None = None) -> dict | None:
    """Akun dengan nama pengguna itu. Pencarian case-insensitive supaya
    'Feby' dan 'feby' adalah orang yang sama — anak tidak paham bedanya,
    dan kegagalan login yang tidak bisa dijelaskan membuat mereka menyerah."""
    p = pengguna.strip().lower()
    for a in muat_akun(path):
        if a["pengguna"].strip().lower() == p:
            return a
    return None


def periksa_peran(
    pengguna: str, sandi_diberikan: str, peran: str, path: Path | None = None
) -> bool:
    """Login + cocokkan peran sekaligus tanpa mempercayai input role."""
    principal = autentikasi(pengguna, sandi_diberikan, path)
    return principal is not None and principal.peran == peran


def autentikasi(
    pengguna: str, sandi_diberikan: str, path: Path | None = None
) -> PrincipalAkun | None:
    """Verifikasi credential dan ambil snapshot canonical tanpa menulis state."""
    try:
        data = baca_json_ketat(path or BERKAS_SANDI, bawaan=TIDAK_ADA)
        if data is TIDAK_ADA or not _data_akun_valid(data):
            akun = []
        else:
            akun = _normalisasi(data)
    except GalatPenyimpananJSON:
        akun = []
    kandidat = next(
        (
            item for item in akun
            if item["pengguna"].strip().casefold()
            == pengguna.strip().casefold()
        ),
        None,
    )
    if kandidat is None:
        _ = hashlib.pbkdf2_hmac(
            "sha256", sandi_diberikan.encode(), _UMPAN_GARAM,
            _ITERASI, dklen=32,
        )
        hmac.compare_digest(_, _UMPAN_KUNCI)
        return None
    try:
        _validasi_hash_akun(kandidat)
    except ValueError:
        return None
    if not periksa(kandidat["pengguna"], sandi_diberikan, data=kandidat):
        return None
    id_akun = kandidat.get("id_akun")
    if not id_akun_sah(id_akun):
        return None
    return PrincipalAkun(
        pengguna=kandidat["pengguna"],
        peran=kandidat.get("peran", "guru"),
        id_akun=id_akun,
        revisi_auth=revisi_auth(kandidat),
    )


def peran_dari(
    pengguna: str, sandi_diberikan: str, path: Path | None = None
) -> str | None:
    """Peran akun yang kredensialnya benar, atau None."""
    principal = autentikasi(pengguna, sandi_diberikan, path)
    return principal.peran if principal else None


def tambah_akun_dan_principal(
    pengguna: str,
    sandi_baru: str,
    peran: str,
    path: Path | None = None,
    siswa_id: int | None = None,
) -> PrincipalAkun:
    """Tambah akun dan kembalikan snapshot persis yang baru di-commit."""
    if peran not in PERAN:
        raise ValueError(f"peran tidak dikenal: {peran}")
    hash_baru = buat_hash(sandi_baru)
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        for a in akun:
            if a["pengguna"].strip().lower() == pengguna.strip().lower():
                raise ValueError(f"nama pengguna sudah dipakai: {pengguna}")
        id_akun = _buat_id_akun()
        while any(a.get("id_akun") == id_akun for a in akun):
            id_akun = _buat_id_akun()
        baru: dict = {
            "pengguna": pengguna,
            "peran": peran,
            "id_akun": id_akun,
            "revisi_auth": 1,
            **hash_baru,
        }
        if siswa_id is not None:
            baru["siswa_id"] = int(siswa_id)
        akun.append(baru)
        _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
        return PrincipalAkun(pengguna, peran, id_akun, 1)


def tambah_akun(
    pengguna: str,
    sandi_baru: str,
    peran: str,
    path: Path | None = None,
    siswa_id: int | None = None,
) -> Path:
    """Tambah akun; pertahankan return path untuk caller lama."""
    tambah_akun_dan_principal(pengguna, sandi_baru, peran, path, siswa_id)
    return path or BERKAS_SANDI


def pastikan_admin(path: Path | None = None) -> str | None:
    """Pastikan ada tepat satu penjaga tertinggi, kembalikan namanya.

    Kalau sudah ada akun ber-peran "admin", tidak ada yang diubah. Kalau
    belum, akun GURU PERTAMA dipromosikan — ini bootstrap deterministik
    untuk pemasangan lama: pemilik produk tak perlu mengubah berkas sandi
    lewat tangan. Berkas hanya berisi murid: kembalikan None, jangan
    menebak. Tanpa berkas sandi (mode lokal) pun None — palang memang
    belum aktif.
    """
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        for a in akun:
            if a.get("peran", "guru") == "admin":
                return a["pengguna"]
        for a in akun:
            if a.get("peran", "guru") == "guru":
                a["peran"] = "admin"
                a["revisi_auth"] = revisi_auth(a) + 1
                _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
                return a["pengguna"]
        return None


def naikkan_revisi_auth(id_akun: str, path: Path | None = None) -> int | None:
    """Cabut semua sesi akun dengan menaikkan revisi tanpa mengganti ID."""
    if not id_akun_sah(id_akun):
        raise ValueError("id_akun tidak sah")
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        target = next((item for item in akun if item.get("id_akun") == id_akun), None)
        if target is None:
            return None
        target["revisi_auth"] = revisi_auth(target) + 1
        _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
        return target["revisi_auth"]


def hapus_akun(pengguna: str, path: Path | None = None) -> bool:
    """Hapus satu akun murid. Mengembalikan True kalau ada yang terhapus.

    Akun GURU tidak bisa dihapus dari sini: menghapus satu-satunya akun guru
    membuat berkas sandi kosong, dan `wajib_sandi()` menilai berkas yang ada
    sebagai "palang aktif" — hasilnya aplikasi menolak semua orang tanpa ada
    cara masuk lagi kecuali lewat SSH.

    Menghapus akun murid TIDAK menghapus data anaknya: jawaban dan diagnosis
    terikat ke tabel `siswa`, bukan ke akun. Anak yang akunnya dihapus tetap
    punya riwayat lengkap, dan akunnya bisa dibuat ulang kapan saja.
    """
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        sisa = [
            a
            for a in akun
            if not (
                a["pengguna"].strip().lower() == pengguna.strip().lower()
                and a.get("peran", "guru") == "murid"
            )
        ]
        if len(sisa) == len(akun):
            return False
        _tulis_akun_atomik(_bungkus_akun(mentah, sisa), tujuan)
        return True


def hapus_akun_guru(pengguna: str, path: Path | None = None) -> bool:
    """Hapus satu akun orang tua (peran guru). Hanya dipanggil panel admin.

    Akun ADMIN tidak bisa dihapus dari sini: sandi pengelola milik deploy,
    dan menghapusnya dari panel berarti satu sesi bocor bisa mengunci
    pengelola lain. Data anak ber-pemilik nama ini TIDAK ikut terhapus —
    baris siswa & sesi tetap, supaya akun pengganti bisa mengambil alih.

    Mengembalikan True kalau ada yang terhapus.
    """
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        sisa = [
            a
            for a in akun
            if not (
                a["pengguna"].strip().lower() == pengguna.strip().lower()
                and a.get("peran", "guru") == "guru"
            )
        ]
        if len(sisa) == len(akun):
            return False
        _tulis_akun_atomik(_bungkus_akun(mentah, sisa), tujuan)
        return True


def setel_sandi_murid(
    pengguna: str, sandi_baru: str, path: Path | None = None
) -> bool:
    """Setel ulang sandi seorang murid (anak lupa sandinya).

    Guru tidak perlu tahu sandi lama anak — itu justru yang membuat fitur ini
    dipakai, bukan diakali dengan menghapus lalu membuat ulang akun (yang
    membuat guru mengira riwayat anak ikut hilang).
    """
    hash_baru = buat_hash(sandi_baru)
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        ubah = False
        for a in akun:
            if (
                a["pengguna"].strip().lower() == pengguna.strip().lower()
                and a.get("peran", "guru") == "murid"
            ):
                a.update(hash_baru)
                a["revisi_auth"] = revisi_auth(a) + 1
                ubah = True
        if not ubah:
            return False
        _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
        return True


def setel_sandi_guru(
    pengguna: str, sandi_baru: str, path: Path | None = None
) -> bool:
    """Setel ulang sandi akun orang tua/guru yang lupa sandinya.

    Admin yang membuatkan akun orang tua harus bisa menyetel ulang sandinya
    tanpa menghapus akun — menghapus lalu membuat ulang memutus tautan
    akun ke siswa-siswanya dan mengubah "pemilik" data keluarga. Hanya
    peran "guru" yang disetel di sini: sandi admin adalah milik deploy
    (disetel saat pemasangan), bukan ranah panel — kalau panel bisa
    menggantinya, satu sesi admin yang bocor berarti sandi penjaga
    tertinggi ikut bisa ditukar.

    Adapter kompatibilitas: False bila tidak ada akun guru yang cocok.
    Panel admin aktif memakai layanan bertoken/audit di admin_service.
    """
    hash_baru = buat_hash(sandi_baru)
    p = path or BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _bentuk_multi = _baca_akun_untuk_tulis(tujuan)
        ubah = False
        for a in akun:
            if (
                a["pengguna"].strip().lower() == pengguna.strip().lower()
                and a.get("peran", "guru") == "guru"
            ):
                a.update(hash_baru)
                a["revisi_auth"] = revisi_auth(a) + 1
                ubah = True
        if not ubah:
            return False
        _tulis_akun_atomik(_bungkus_akun(mentah, akun), tujuan)
        return True
