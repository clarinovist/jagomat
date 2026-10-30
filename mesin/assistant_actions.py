"""Validasi usulan dan eksekusi latihan manual Pendamping.

Model hanya boleh mengusulkan nilai dari katalog aktif. Modul ini memvalidasi
ulang seluruh nilai dan membuat sesi ``bebas`` secara idempoten setelah
konfirmasi orang tua; ia tidak menulis bukti atau kejadian siklus belajar.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import re
import secrets
from typing import Optional

import assistant_catalog
import assistant_policy
import assistant_store
import database
import topics


JUMLAH_SOAL_SAH = (10, 15, 20, 25, 30)
MASA_TINJAU_DETIK = 30 * 60


@dataclass(frozen=True)
class UsulanLatihan:
    topik_id: str
    template_ids: tuple[str, ...]
    level: str
    jumlah_soal: int

    def ke_dict(self) -> dict:
        return {
            "topik_id": self.topik_id,
            "template_ids": list(self.template_ids),
            "level": self.level,
            "jumlah_soal": self.jumlah_soal,
        }


class GalatTindakan(ValueError):
    """Usulan atau konfirmasi tidak lagi aman untuk dijalankan."""


def validasi_usulan(data, *, untuk_penawaran: bool = True) -> UsulanLatihan:
    """Validasi katalog; pembaca histori boleh memakai registri tanpa izin membuat."""
    if type(data) is not dict or set(data) != {
        "topik_id", "template_ids", "level", "jumlah_soal"
    }:
        raise GalatTindakan("Usulan latihan tidak sesuai kontrak.")
    if (
        type(data["topik_id"]) is not str
        or type(data["level"]) is not str
        or type(data["jumlah_soal"]) is not int
        or type(data["template_ids"]) is not list
        or not data["template_ids"]
        or len(data["template_ids"]) > 8
        or any(type(item) is not str for item in data["template_ids"])
        or len(set(data["template_ids"])) != len(data["template_ids"])
    ):
        raise GalatTindakan("Parameter usulan latihan tidak sah.")
    if data["jumlah_soal"] not in JUMLAH_SOAL_SAH:
        raise GalatTindakan("Jumlah soal usulan tidak tersedia.")

    katalog = assistant_catalog.buat_katalog(untuk_penawaran=untuk_penawaran)
    topik = {item.id: item for item in katalog.topik}.get(data["topik_id"])
    template = {item.id: item for item in katalog.template}
    if topik is None or data["level"] not in topik.level:
        raise GalatTindakan("Topik atau level usulan tidak tersedia.")
    for template_id in data["template_ids"]:
        item = template.get(template_id)
        if (
            item is None
            or item.topik_id != topik.id
            or data["level"] not in item.level
        ):
            raise GalatTindakan("Template usulan tidak tersedia untuk pilihan ini.")
    return UsulanLatihan(
        topik_id=topik.id,
        template_ids=tuple(data["template_ids"]),
        level=data["level"],
        jumlah_soal=data["jumlah_soal"],
    )


def hash_usulan(usulan: UsulanLatihan) -> str:
    mentah = json.dumps(
        usulan.ke_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(mentah.encode("utf-8")).hexdigest()


def _siswa_dari_konteks(kon, chat, *, pemilik: str) -> Optional[int]:
    """Petakan konteks yang sudah diotorisasi ke satu anak tanpa fallback."""
    try:
        if chat.context_kind == "anak":
            siswa_id = int(chat.context_id)
        elif chat.context_kind in ("sesi", "soal"):
            sesi_id = int(chat.context_id.split(":", 1)[0])
            baris = kon.execute(
                """SELECT s.siswa_id FROM sesi s JOIN siswa w ON w.id = s.siswa_id
                   WHERE s.id = ? AND w.pemilik = ?""",
                (sesi_id, pemilik),
            ).fetchone()
            return int(baris["siswa_id"]) if baris is not None else None
        else:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return siswa_id if database.siswa_milik(kon, siswa_id, pemilik) else None


def _urutan(usulan: UsulanLatihan) -> tuple[str, ...]:
    dasar = usulan.template_ids
    return tuple(dasar[indeks % len(dasar)] for indeks in range(usulan.jumlah_soal))


def _sidik(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


def _ikatan(catatan, chat, pemilik: str) -> str:
    """Ikatan snapshot tinjauan, bukan nilai status hasil yang dapat berubah."""
    return _sidik(json.dumps({
        "account_id": catatan.account_id, "pemilik": pemilik,
        "usulan_id": catatan.id, "payload": catatan.payload_json,
        "hash": catatan.hash_usulan, "versi": catatan.versi,
        "sumber": catatan.sumber_request_id, "chat_id": chat.id,
        "chat_version": catatan.chat_version,
        "consent_version": catatan.consent_version,
        "context_version": catatan.context_version,
        "context_resource_version": catatan.context_resource_version,
        "context_kind": chat.context_kind, "context_id": chat.context_id,
    }, sort_keys=True, separators=(",", ":")))


def _kunci(catatan) -> str:
    # Jangan sertakan hash payload: perubahan isi tidak boleh membuka eksekusi
    # kedua untuk identitas usulan yang sama.
    return _sidik("pendamping-eksekusi-v1|" + catatan.account_id + "|" + catatan.id)


def _kunci_lama(catatan) -> str:
    return _sidik("pendamping-bebas-v1|" + catatan.account_id + "|" + catatan.id
                  + "|" + catatan.hash_usulan)


@contextmanager
def _transaksi_tindakan(kon):
    """Miliki transaksi privat; jangan commit WIP pemanggil diam-diam.

    Urutan lock selalu Pendamping lalu DB belajar. Tidak ada network. BEGIN
    IMMEDIATE sebelum read menserialkan konfirmasi, tinjauan, dan pencabutan.
    """
    if kon.in_transaction:
        raise GalatTindakan("Selesaikan transaksi sebelum meninjau usulan.")
    with kon:
        kon.execute("BEGIN IMMEDIATE")
        yield


def _catatan_dan_chat(kon, account_id: str, usulan_id: str):
    catatan = assistant_store.ambil_usulan(kon, account_id, usulan_id)
    chat = None if catatan is None else assistant_store.ambil_chat(
        kon, account_id, catatan.chat_id
    )
    if catatan is None or chat is None:
        raise LookupError("usulan tidak ditemukan")
    return catatan, chat


def _periksa_izin(kon, catatan, chat) -> None:
    if not assistant_store.persetujuan_aktif(
        kon, catatan.account_id, kategori="chat_umum",
        provider_id=assistant_policy.PROVIDER_ID,
    ) or assistant_store.versi_persetujuan(kon, catatan.account_id) != catatan.consent_version:
        raise GalatTindakan("Persetujuan berubah. Tinjau ulang usulan.")
    if (
        chat.versi != catatan.chat_version
        or chat.context_kind is None
        or chat.context_version != catatan.context_version
        or chat.context_resource_version != catatan.context_resource_version
        or not assistant_store.persetujuan_konteks_aktif(
            kon, catatan.account_id, jenis=chat.context_kind,
            resource_id=chat.context_id,
            resource_version=chat.context_resource_version,
            versi=chat.context_version,
        )
    ):
        raise GalatTindakan("Konteks berubah. Tinjau ulang usulan.")


def _pemilik_sumber(kon_data, chat, pemilik: str) -> int:
    siswa_id = _siswa_dari_konteks(kon_data, chat, pemilik=pemilik)
    if siswa_id is None:
        raise LookupError("usulan tidak ditemukan")
    if chat.context_kind == "soal":
        try:
            sesi_id, nomor = map(int, chat.context_id.split(":", 1))
        except (TypeError, ValueError, OverflowError):
            raise LookupError("usulan tidak ditemukan") from None
        if kon_data.execute(
            "SELECT 1 FROM sesi_soal WHERE sesi_id = ? AND nomor = ?",
            (sesi_id, nomor),
        ).fetchone() is None:
            raise LookupError("usulan tidak ditemukan")
    return siswa_id


def _periksa_kebaruan(kon_data, chat, pemilik: str) -> None:
    import assistant_context

    if chat.context_kind in ("sesi", "soal"):
        sesi_id = int(chat.context_id.split(":", 1)[0])
        sesi = kon_data.execute(
            "SELECT dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
        if sesi is None or sesi["dibatalkan"] is not None:
            raise GalatTindakan("Konteks berubah. Tinjau ulang usulan.")
    if assistant_context.versi_resource(
        kon_data, chat.context_kind, chat.context_id, pemilik=pemilik
    ) != chat.context_resource_version:
        raise GalatTindakan("Konteks berubah. Tinjau ulang usulan.")


def _usulan_tersimpan(catatan, *, untuk_penawaran: bool = True) -> UsulanLatihan:
    try:
        usulan = validasi_usulan(json.loads(catatan.payload_json), untuk_penawaran=untuk_penawaran)
    except (ValueError, TypeError):
        raise GalatTindakan("Isi usulan tidak lagi tersedia. Tinjau ulang.") from None
    if hash_usulan(usulan) != catatan.hash_usulan:
        raise GalatTindakan("Isi usulan tidak cocok dengan hash tinjauan.")
    return usulan


def _hasil_tersimpan(kon_data, catatan, siswa_id: int, pemilik: str):
    """Lookup hasil hanya setelah sumber diotorisasi; batal/hilang terminal."""
    ledger = kon_data.execute(
        "SELECT * FROM eksekusi_pendamping WHERE kunci = ?", (_kunci(catatan),)
    ).fetchone()
    sesi_id = catatan.sesi_id if ledger is None else int(ledger["sesi_id"])
    if ledger is not None and catatan.sesi_id not in (None, sesi_id):
        raise GalatTindakan("Hasil konfirmasi tidak cocok.")
    if sesi_id is None:
        # Kompatibilitas hasil versi lama yang commit sebelum DB privat.
        lama = kon_data.execute(
            "SELECT id FROM sesi WHERE kunci_pendamping = ? ORDER BY id",
            (_kunci_lama(catatan),),
        ).fetchall()
        if len(lama) > 1:
            raise GalatTindakan("Hasil lama perlu diperiksa; tidak membuat ulang.")
        if not lama:
            return None, ledger
        sesi_id = int(lama[0]["id"])
    sesi = kon_data.execute(
        """SELECT s.siswa_id, s.dibatalkan, s.kunci_pendamping
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id
           WHERE s.id = ? AND w.pemilik = ?""", (sesi_id, pemilik),
    ).fetchone()
    if sesi is None:
        # Jangan ungkap apakah ID yang tersimpan telah berpindah pemilik.
        if kon_data.execute("SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)).fetchone():
            raise LookupError("usulan tidak ditemukan")
        raise GalatTindakan("Latihan hasil sudah tidak tersedia; tidak dibuat ulang.")
    if sesi["siswa_id"] != siswa_id:
        raise LookupError("usulan tidak ditemukan")
    if sesi["dibatalkan"] is not None:
        raise GalatTindakan("Latihan hasil dibatalkan; tidak dibuat ulang.")
    if sesi["kunci_pendamping"] != _kunci_lama(catatan):
        raise GalatTindakan("Hasil konfirmasi tidak cocok.")
    return sesi_id, ledger


def ambil_hasil_usulan(kon, account_id: str, pemilik: str, usulan_id: str) -> Optional[int]:
    """Baca hasil berizin tanpa menulis atau menuntut snapshot sumber segar.

    HTTP GET wajib memakai ini sebelum mencoba menerbitkan tinjauan baru.
    Hasil yang membuat ringkasan anak usang tetap bisa ditemukan, tetapi
    pencabutan consent, penghapusan chat, dan perpindahan owner tetap menolak.
    """
    catatan, chat = _catatan_dan_chat(kon, account_id, usulan_id)
    with database.buka() as kon_data:
        siswa_id = _pemilik_sumber(kon_data, chat, pemilik)
        _periksa_izin(kon, catatan, chat)
        sesi_id, ledger = _hasil_tersimpan(kon_data, catatan, siswa_id, pemilik)
        if ledger is not None:
            _usulan_tersimpan(catatan, untuk_penawaran=False)
            if ledger["ikatan_hash"] != _ikatan(catatan, chat, pemilik):
                raise GalatTindakan("Hasil konfirmasi tidak cocok dengan tinjauan.")
        return sesi_id


def tinjau_usulan(kon, account_id: str, pemilik: str, usulan_id: str, *, sekarang: int) -> str:
    """Catat tinjauan tervalidasi dan kembalikan token form, bukan eksekusi.

    Tinjauan baru mengganti token lama (multi-tab lama mendapat konflik).
    Mengubah payload/konteks tidak dapat disahkan hanya dengan refresh GET.
    """
    with _transaksi_tindakan(kon):
        catatan, chat = _catatan_dan_chat(kon, account_id, usulan_id)
        with database.buka() as kon_data:
            siswa_id = _pemilik_sumber(kon_data, chat, pemilik)
            _periksa_izin(kon, catatan, chat)
            _usulan_tersimpan(catatan)
            sesi_id, _ = _hasil_tersimpan(kon_data, catatan, siswa_id, pemilik)
            if sesi_id is not None:
                raise GalatTindakan("Latihan sudah dibuat. Buka hasil yang tersimpan.")
            _periksa_kebaruan(kon_data, chat, pemilik)
        token = "aksi_" + secrets.token_hex(16)
        kon.execute(
            """INSERT INTO tinjauan_usulan
                   (usulan_id, token_hash, ikatan_hash, dibuat, kedaluarsa)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(usulan_id) DO UPDATE SET token_hash = excluded.token_hash,
                   ikatan_hash = excluded.ikatan_hash, dibuat = excluded.dibuat,
                   kedaluarsa = excluded.kedaluarsa""",
            (usulan_id, _sidik(token), _ikatan(catatan, chat, pemilik),
             sekarang, sekarang + MASA_TINJAU_DETIK),
        )
        return token


def konfirmasi_dan_buat_sesi(
    kon_pendamping, account_id: str, pemilik: str, usulan_id: str, *,
    versi: int, hash_diharapkan: str, request_id: str, sekarang: int,
) -> int:
    """Revalidasi tinjauan server lalu buat maksimum satu sesi manual/bebas.

    Commit belajar (sesi + ledger) mendahului commit hasil privat. Bila proses
    mati di antaranya, retry menemukan ledger tanpa meregenerasi. Semua write
    generator terbungkus transaksi luar, termasuk RELEASE SAVEPOINT internal.
    """
    with _transaksi_tindakan(kon_pendamping):
        catatan, chat = _catatan_dan_chat(kon_pendamping, account_id, usulan_id)
        with database.buka() as kon_data:
            kon_data.execute("BEGIN IMMEDIATE")
            siswa_id = _pemilik_sumber(kon_data, chat, pemilik)
            _periksa_izin(kon_pendamping, catatan, chat)
            if (
                type(versi) is not int or catatan.versi != versi
                or catatan.hash_usulan != hash_diharapkan
                or type(request_id) is not str
                or not re.fullmatch(r"aksi_[0-9a-f]{32}", request_id)
                or catatan.request_id_konfirmasi not in (None, request_id)
            ):
                raise GalatTindakan("Usulan berubah. Tinjau ulang sebelum mengonfirmasi.")
            ikatan = _ikatan(catatan, chat, pemilik)
            tinjauan = kon_pendamping.execute(
                "SELECT * FROM tinjauan_usulan WHERE usulan_id = ?", (usulan_id,)
            ).fetchone()
            if (
                tinjauan is None or tinjauan["token_hash"] != _sidik(request_id)
                or tinjauan["ikatan_hash"] != ikatan
            ):
                raise GalatTindakan("Tinjauan tidak sah. Tinjau ulang usulan.")
            usulan = _usulan_tersimpan(catatan, untuk_penawaran=False)
            sesi_id, ledger = _hasil_tersimpan(kon_data, catatan, siswa_id, pemilik)
            if ledger is not None and (
                ledger["token_hash"] != _sidik(request_id) or ledger["ikatan_hash"] != ikatan
            ):
                raise GalatTindakan("Konfirmasi tidak cocok dengan eksekusi tersimpan.")
            if sesi_id is None:
                # Retry hasil lama boleh dibaca; sesi baru wajib lolos sakelar kini.
                _usulan_tersimpan(catatan)
                if not tinjauan["dibuat"] <= sekarang < tinjauan["kedaluarsa"]:
                    raise GalatTindakan("Tinjauan kedaluwarsa. Tinjau ulang usulan.")
                _periksa_kebaruan(kon_data, chat, pemilik)
                kunci_lama = _kunci_lama(catatan)
                sesi_id = database.buat_sesi_dari_urutan(
                    kon_data, siswa_id, int(kunci_lama[:15], 16), _urutan(usulan),
                    topik=topics.ambil(usulan.topik_id), level=usulan.level,
                    mode="diagnostik", jenis="biasa",
                )
                hasil = kon_data.execute(
                    """UPDATE sesi SET kunci_pendamping = ?
                       WHERE id = ? AND tujuan = 'bebas' AND putaran_id IS NULL
                         AND bagian_checkpoint IS NULL AND dikonfirmasi_guru IS NULL
                         AND kunci_idempotensi IS NULL""", (kunci_lama, sesi_id),
                )
                if hasil.rowcount != 1:
                    raise GalatTindakan("Sesi manual tidak dapat dikunci dengan aman.")
            if ledger is None:
                kon_data.execute(
                    """INSERT INTO eksekusi_pendamping
                           (kunci, sesi_id, token_hash, ikatan_hash) VALUES (?, ?, ?, ?)""",
                    (_kunci(catatan), sesi_id, _sidik(request_id), ikatan),
                )
        if not assistant_store.selesaikan_usulan(
            kon_pendamping, account_id, usulan_id, versi_diharapkan=versi,
            hash_diharapkan=hash_diharapkan, request_id=request_id,
            sesi_id=sesi_id, sekarang=sekarang,
        ):
            raise GalatTindakan("Hasil konfirmasi tidak dapat disimpan.")
        return sesi_id
