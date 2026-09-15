"""Proyeksi UI Pendamping yang hanya membaca metadata milik principal.

Nama sumber hanya untuk renderer: jangan gabungkan hasil modul ini dengan
``KonteksPendamping.muatan``. Hak baca snapshot bukan izin mengirim pesan;
caller tetap wajib memeriksa peran, kebaruan, dan consent pada jalur kirim.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Optional

import assistant_actions
import assistant_policy
import assistant_store
import database
import rumus
import topics
from template_labels import nama_tipe_soal


_WIB = timezone(timedelta(hours=7))
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
_ID_SUMBER = re.compile(r"[1-9][0-9]{0,18}\Z")
_MAKS_ID = 2 ** 63 - 1


def label_chat(chat: assistant_store.Chat) -> str:
    """Identitas tetap dari waktu dibuat WIB dan ID penuh, bukan cuplikan pesan."""
    waktu = datetime.fromtimestamp(chat.dibuat, tz=_WIB)
    return (
        f"Chat {waktu.day:02d} {_BULAN[waktu.month - 1]} {waktu.year} · "
        f"{waktu:%H:%M} WIB · {chat.id}"
    )


def _angka_sumber(nilai: str) -> Optional[int]:
    if not _ID_SUMBER.fullmatch(nilai):
        return None
    angka = int(nilai)
    return angka if angka <= _MAKS_ID else None


def sumber_tampilan(kon_data, jenis: str, resource_id: str, *, pemilik: str
                    ) -> Optional[dict]:
    """Nama/level/link lokal dari satu query owner-scoped, tanpa isi belajar.

    Nilai hasil berupa teks, bukan HTML; renderer wajib escape. Route sesi belum
    memiliki parameter ``lihat``. Tautan soal sesi terkirim memakai anchor input;
    pratinjau tanpa anchor per-soal menuju sesi, bukan tautan anchor yang mati.
    """
    if type(pemilik) is not str or not pemilik or type(resource_id) is not str:
        return None
    if jenis not in ("anak", "sesi", "soal"):
        return None
    bagian = resource_id.split(":")
    if len(bagian) != (2 if jenis == "soal" else 1):
        return None
    angka = tuple(_angka_sumber(item) for item in bagian)
    if any(item is None for item in angka):
        return None
    identitas = angka[0]
    if jenis == "anak":
        baris = kon_data.execute(
            "SELECT nama, tingkat AS level FROM siswa WHERE id = ? AND pemilik = ?",
            (identitas, pemilik),
        ).fetchone()
        label, url = "Ringkasan anak", f"/anak/{identitas}"
    elif jenis == "sesi":
        baris = kon_data.execute(
            """SELECT w.nama, s.level FROM sesi s JOIN siswa w ON w.id = s.siswa_id
               WHERE s.id = ? AND w.pemilik = ?""",
            (identitas, pemilik),
        ).fetchone()
        label, url = f"Sesi #{identitas}", f"/sesi/{identitas}"
    else:
        nomor = angka[1]
        baris = kon_data.execute(
            """SELECT w.nama, s.level, s.selesai, ss.id AS sesi_soal_id
               FROM sesi_soal ss JOIN sesi s ON s.id = ss.sesi_id
               JOIN siswa w ON w.id = s.siswa_id
               WHERE ss.sesi_id = ? AND ss.nomor = ? AND w.pemilik = ?""",
            (identitas, nomor, pemilik),
        ).fetchone()
        label = f"Soal {nomor} · Sesi #{identitas}"
        url = f"/sesi/{identitas}"
        if baris is not None and baris["selesai"]:
            url += f"#jwb-{baris['sesi_soal_id']}"
    if baris is None:
        return None
    return {
        "label": label, "nama": baris["nama"], "level": baris["level"],
        "url": url, "jenis": jenis,
        "kategori": "soal_resmi" if jenis == "soal" else "ringkasan_netral",
    }


def status_memori(kon_priv, account_id: str, chat=None) -> str:
    """Mode chat mendahului preferensi; tidak membaca isi atau menghitung draft."""
    assistant_store._wajib_account_id(account_id)
    if chat is not None:
        if chat.account_id != account_id or chat.dihapus is not None:
            raise ValueError("Percakapan tidak tersedia.")
        if chat.mode_memori == "tanpa_memori":
            return "Chat tanpa memori"
        if chat.mode_memori != "aktif":
            raise ValueError("Mode memori tidak sah.")
    if not assistant_store.penggunaan_memori_aktif(kon_priv, account_id):
        return "Memori nonaktif"
    jumlah = kon_priv.execute(
        """SELECT COUNT(*) FROM memori
           WHERE account_id = ? AND dikonfirmasi = 1 AND dihapus IS NULL
             AND lingkup = 'preferensi_orang_tua'""",
        (account_id,),
    ).fetchone()[0]
    if not jumlah:
        return "Memori aktif · belum ada catatan"
    return f"Memori aktif · {jumlah} catatan"


def riwayat(kon_priv, account_id: str, *, halaman: int = 1, batas: int = 20,
            jenis_resource: Optional[str] = None, resource_id: Optional[str] = None,
            ) -> tuple[tuple[assistant_store.Chat, ...], bool]:
    """Satu halaman metadata saja, opsional exact-resource, tanpa transkrip."""
    assistant_store._wajib_account_id(account_id)
    if type(batas) is not int or not 1 <= batas <= 20:
        raise ValueError("Batas riwayat tidak sah.")
    if type(halaman) is not int or halaman < 1 or (halaman - 1) * batas > 10000:
        raise ValueError("Halaman riwayat tidak sah.")
    scoped = jenis_resource is not None or resource_id is not None
    if scoped and (
        jenis_resource not in ("anak", "sesi", "soal")
        or type(resource_id) is not str
        or not resource_id
    ):
        raise ValueError("Scope riwayat tidak sah.")
    syarat = " AND context_kind = ? AND context_id = ?" if scoped else ""
    parameter = ((account_id, jenis_resource, resource_id, batas + 1,
                  (halaman - 1) * batas) if scoped else
                 (account_id, batas + 1, (halaman - 1) * batas))
    baris = kon_priv.execute(
        """SELECT * FROM chat WHERE account_id = ? AND dihapus IS NULL""" + syarat +
        " ORDER BY diperbarui DESC, id DESC LIMIT ? OFFSET ?",
        parameter,
    ).fetchall()
    return (
        tuple(assistant_store._chat_dari_baris(item) for item in baris[:batas]),
        len(baris) > batas and halaman * batas <= 10000,
    )


def riwayat_umum(kon_priv, account_id: str, *, halaman: int = 1,
                  batas: int = 20) -> tuple[tuple[assistant_store.Chat, ...], bool]:
    """Metadata chat umum lama saja; tidak memuat transkrip atau chat konteks."""
    assistant_store._wajib_account_id(account_id)
    if type(batas) is not int or not 1 <= batas <= 20:
        raise ValueError("Batas arsip tidak sah.")
    if type(halaman) is not int or halaman < 1 or (halaman - 1) * batas > 10000:
        raise ValueError("Halaman arsip tidak sah.")
    baris = kon_priv.execute(
        """SELECT * FROM chat
           WHERE account_id = ? AND dihapus IS NULL AND context_kind IS NULL
             AND context_id IS NULL AND context_version IS NULL
             AND context_resource_version IS NULL
           ORDER BY diperbarui DESC, id DESC LIMIT ? OFFSET ?""",
        (account_id, batas + 1, (halaman - 1) * batas),
    ).fetchall()
    return (
        tuple(assistant_store._chat_dari_baris(item) for item in baris[:batas]),
        len(baris) > batas and halaman * batas <= 10000,
    )


def _objek_unik(pasangan):
    hasil = {}
    for kunci, nilai in pasangan:
        if kunci in hasil:
            raise ValueError("Isi usulan tidak sah.")
        hasil[kunci] = nilai
    return hasil


def ringkasan_usulan(payload_json: str) -> dict:
    """Label resmi dan jumlah per materi sesuai distribusi eksekusi, tanpa soal."""
    if type(payload_json) is not str or len(payload_json) > 8000:
        raise ValueError("Isi usulan tidak sah.")
    try:
        data = json.loads(payload_json, object_pairs_hook=_objek_unik)
        usulan = assistant_actions.validasi_usulan(data)
    except (ValueError, RecursionError):
        raise ValueError("Isi usulan tidak sah.") from None
    dasar, sisa = divmod(usulan.jumlah_soal, len(usulan.template_ids))
    materi = []
    for indeks, template_id in enumerate(usulan.template_ids):
        kartu = rumus.kartu_untuk(template_id)
        if kartu is None:
            raise ValueError("Materi usulan belum tersedia.")
        materi.append((nama_tipe_soal(template_id), dasar + (indeks < sisa), template_id))
    return {
        "topik": topics.ambil(usulan.topik_id).nama,
        "level": usulan.level, "jumlah": usulan.jumlah_soal,
        "materi": tuple(materi),
    }


def hak_baca_chat(kon_priv, account_id: str, chat, *, pemilik: str) -> bool:
    """Periksa izin baca snapshot tersimpan, bukan izin kirim atau kebaruan.

    Refetch mencegah objek lama menghidupkan chat dihapus. Grant yang diperiksa
    adalah grant TERBARU resource chat ini, bukan versi global semua sumber.
    Caller harus memakai pasangan id_akun/pengguna dari principal terverifikasi.
    """
    assistant_store._wajib_account_id(account_id)
    if (type(pemilik) is not str or not pemilik or chat is None
            or chat.account_id != account_id):
        return False
    kini = assistant_store.ambil_chat(kon_priv, account_id, chat.id)
    if kini is None:
        return False
    izin = kon_priv.execute(
        """SELECT provider_id, policy_version, dicabut FROM persetujuan
           WHERE account_id = ? AND kategori = 'chat_umum'
           ORDER BY versi DESC, rowid DESC LIMIT 1""",
        (account_id,),
    ).fetchone()
    if (izin is None or izin["dicabut"] is not None
            or izin["provider_id"] != assistant_policy.PROVIDER_ID
            or izin["policy_version"] != assistant_policy.VERSI_KEBIJAKAN):
        return False
    if kini.context_kind is None:
        return all(item is None for item in (
            kini.context_id, kini.context_version, kini.context_resource_version
        ))
    if (kini.context_kind not in ("anak", "sesi", "soal")
            or not kini.context_id or not kini.context_resource_version
            or type(kini.context_version) is not int or kini.context_version < 1):
        return False
    kategori = "soal_resmi" if kini.context_kind == "soal" else "ringkasan_netral"
    if not assistant_store.persetujuan_konteks_aktif(
        kon_priv, account_id, jenis=kini.context_kind, resource_id=kini.context_id,
        resource_version=kini.context_resource_version, kategori=kategori,
        versi=kini.context_version,
    ):
        return False
    with database.buka() as kon_data:
        return sumber_tampilan(
            kon_data, kini.context_kind, kini.context_id, pemilik=pemilik
        ) is not None
