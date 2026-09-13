"""Orkestrasi chat umum Pendamping tanpa menahan transaksi saat network."""

from __future__ import annotations

from contextvars import ContextVar
import json
import os
import time

import ai_service
import assistant_actions
import assistant_catalog
import assistant_client
import assistant_policy
import assistant_store


class GalatPendamping(RuntimeError):
    """Kegagalan aman yang boleh diterjemahkan menjadi pesan UI umum."""


_konteks_ai = ContextVar("konteks_ai_pendamping", default=(None, None))


def konfigurasi() -> assistant_client.Konfigurasi:
    return assistant_client.Konfigurasi(
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash").strip(),
    )


def tersedia() -> bool:
    """Konfigurasi chat lengkap dan sah, tanpa melakukan network call."""
    try:
        konfigurasi()
    except ValueError:
        return False
    return True


def panggil_provider_default(pesan):
    account_id, operasi_id = _konteks_ai.get()
    return ai_service.panggil(
        "pendamping", account_id,
        lambda: assistant_client.kirim(konfigurasi(), pesan),
        operasi_id=operasi_id,
    )


def _pesan_provider(
    kon, account_id: str, chat_id: str, teks_baru: str, *, konteks=None
):
    katalog = json.loads(
        assistant_catalog.serialisasi_ringkas(assistant_catalog.buat_katalog())
    )
    memori = [item.isi for item in assistant_store.memori_untuk_chat(
        kon, account_id, chat_id
    )]
    percakapan = [
        {"peran": item.peran, "teks": item.teks}
        for item in assistant_store.daftar_pesan(kon, account_id, chat_id)
    ]
    percakapan.append({"peran": "pengguna", "teks": teks_baru})
    isi = {
        "katalog": katalog,
        "memori": memori,
        "percakapan": percakapan,
    }
    if konteks is not None:
        isi["konteks"] = konteks.muatan
    muatan = json.dumps(isi, ensure_ascii=False, separators=(",", ":"))
    return [
        {"role": "system", "content": assistant_policy.PROMPT_SISTEM},
        {"role": "user", "content": muatan},
    ]


def _kunci_reservasi(kon):
    """Serialkan pemeriksaan request dan reservasi; lepaskan sebelum network."""
    if not kon.in_transaction:
        kon.execute("BEGIN IMMEDIATE")
    else:
        # Pemanggil boleh baru membuat chat dalam transaksi yang sama.
        kon.execute("UPDATE operasi SET status = status WHERE 0")


def _chat_dan_konteks_sah(kon, account_id, chat_id, konteks, validasi_konteks):
    chat = assistant_store.ambil_chat(kon, account_id, chat_id)
    if chat is None:
        raise GalatPendamping("Percakapan tidak tersedia.")
    if chat.context_kind is None:
        if konteks is not None:
            raise GalatPendamping("Konteks tidak cocok dengan percakapan.")
    elif (
        konteks is None
        or konteks.jenis != chat.context_kind
        or konteks.resource_id != chat.context_id
        or konteks.versi != chat.context_resource_version
        or validasi_konteks is None
        or validasi_konteks() != konteks.versi
    ):
        raise GalatPendamping("Konteks belajar berubah. Tinjau sumber lagi.")
    if konteks is not None and not assistant_store.persetujuan_konteks_aktif(
        kon, account_id, jenis=chat.context_kind, resource_id=chat.context_id,
        resource_version=chat.context_resource_version,
        kategori=konteks.kategori, versi=chat.context_version,
    ):
        raise GalatPendamping("Persetujuan konteks berubah. Buka chat baru.")
    return chat


def mulai_chat_dan_kirim(
    kon, account_id: str, mode_memori: str, teks: str, *, request_id: str,
    panggil_provider=None, sekarang: int | None = None,
):
    """Reservasi chat awal dan request atomik; retry tetap ke chat asal."""
    aman = assistant_policy.pastikan_teks_aman(teks)
    if mode_memori not in ("aktif", "tanpa_memori"):
        raise ValueError("Mode memori tidak sah.")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with kon:
        _kunci_reservasi(kon)
        lama = kon.execute(
            "SELECT chat_id, chat_version FROM operasi WHERE request_id = ? AND account_id = ?",
            (request_id, account_id),
        ).fetchone()
        if lama is not None:
            chat = assistant_store.ambil_chat(kon, account_id, lama["chat_id"])
            if (
                chat is None
                or chat.mode_memori != mode_memori
                or chat.context_kind is not None
                or lama["chat_version"] != 1
            ):
                raise GalatPendamping("Permintaan tidak cocok dengan percakapan awal.")
        else:
            chat = assistant_store.buat_chat(
                kon, account_id, mode_memori, sekarang=kini
            )
        kirim_pesan(
            kon, account_id, chat.id, aman, request_id=request_id,
            panggil_provider=panggil_provider, sekarang=kini,
        )
    return assistant_store.ambil_chat(kon, account_id, chat.id)


def kirim_pesan(
    kon,
    account_id: str,
    chat_id: str,
    teks: str,
    *,
    request_id: str,
    panggil_provider=None,
    sekarang: int | None = None,
    konteks=None,
    validasi_konteks=None,
) -> str:
    """Simpan pesan, panggil provider di luar transaksi, lalu revalidasi versi."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    aman = assistant_policy.pastikan_teks_aman(teks)
    with kon:
        _kunci_reservasi(kon)
        if not assistant_store.persetujuan_aktif(
            kon, account_id, kategori="chat_umum", provider_id=assistant_policy.PROVIDER_ID
        ):
            raise GalatPendamping("Persetujuan provider belum diberikan.")
        chat = _chat_dan_konteks_sah(
            kon, account_id, chat_id, konteks, validasi_konteks
        )
        operasi_lama = kon.execute(
            "SELECT chat_id, status FROM operasi WHERE request_id = ? AND account_id = ?",
            (request_id, account_id),
        ).fetchone()
        if operasi_lama:
            if operasi_lama["chat_id"] != chat.id:
                raise GalatPendamping("Permintaan tidak cocok dengan percakapan.")
            sumber = assistant_store.pesan_dari_request(
                kon, account_id, request_id, peran="pengguna"
            )
            jawaban_lama = assistant_store.pesan_dari_request(
                kon, account_id, request_id + ":jawaban", peran="asisten"
            )
            if (
                operasi_lama["status"] == "selesai"
                and sumber is not None and sumber.chat_id == chat.id
                and sumber.teks == aman
                and jawaban_lama is not None and jawaban_lama.chat_id == chat.id
            ):
                return jawaban_lama.teks
            raise GalatPendamping("Permintaan ini sedang atau sudah gagal diproses.")

        consent_version = assistant_store.versi_persetujuan(kon, account_id)
        memory_version = assistant_store.versi_memori(kon, account_id)
        context_version = chat.context_version if konteks is not None else 0
        operasi = assistant_store.mulai_operasi(
            kon, account_id, chat_id, request_id,
            consent_version=consent_version,
            memory_version=memory_version,
            context_version=context_version,
            sekarang=kini,
        )
        pesan = _pesan_provider(
            kon, account_id, chat_id, aman, konteks=konteks
        )

    pemanggil = panggil_provider or panggil_provider_default
    token_ai = _konteks_ai.set((account_id, "pendamping:" + request_id))
    try:
        mentah = pemanggil(pesan)
        respons = assistant_policy.validasi_respons(mentah)
        konteks_masih_sah = (
            konteks is None
            or (
                validasi_konteks is not None
                and validasi_konteks() == konteks.versi
            )
        )
    except (assistant_client.GalatProvider, ai_service.AIUnavailable, ValueError) as galat:
        try:
            with kon:
                assistant_store.gagalkan_operasi(
                    kon, account_id, request_id, sekarang=kini
                )
        except Exception:
            kon.rollback()
        raise GalatPendamping("Pendamping belum bisa menjawab. Coba lagi nanti.") from galat
    finally:
        _konteks_ai.reset(token_ai)

    try:
        with kon:
            _kunci_reservasi(kon)
            if not konteks_masih_sah:
                raise GalatPendamping(
                    "Konteks belajar berubah. Buka chat baru setelah meninjau ulang."
                )
            if konteks is not None and (
                not assistant_store.persetujuan_konteks_aktif(
                    kon,
                    account_id,
                    jenis=konteks.jenis,
                    resource_id=konteks.resource_id,
                    resource_version=konteks.versi,
                    kategori=konteks.kategori,
                    versi=context_version,
                )
            ):
                raise GalatPendamping(
                    "Persetujuan konteks berubah. Buka chat baru."
                )
            if not assistant_store.selesaikan_operasi(
                kon, account_id, request_id,
                chat_version=operasi.chat_version,
                consent_version=consent_version,
                memory_version=memory_version,
                context_version=context_version,
                sekarang=kini,
            ):
                raise GalatPendamping(
                    "Percakapan atau persetujuan berubah. Tinjau lalu kirim lagi."
                )
            assistant_store.tambah_pesan(
                kon, account_id, chat_id, "pengguna", aman,
                request_id=request_id, sekarang=kini,
            )
            assistant_store.tambah_pesan(
                kon, account_id, chat_id, "asisten", respons.jawaban,
                request_id=request_id + ":jawaban", sekarang=kini,
            )
            if respons.usulan_latihan is not None:
                if konteks is None:
                    raise GalatPendamping(
                        "Pilih konteks belajar sebelum meninjau usulan latihan."
                    )
                payload = json.dumps(
                    respons.usulan_latihan.ke_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                assistant_store.simpan_usulan(
                    kon,
                    account_id,
                    chat_id,
                    request_id,
                    payload_json=payload,
                    hash_usulan=assistant_actions.hash_usulan(
                        respons.usulan_latihan
                    ),
                    chat_version=operasi.chat_version + 2,
                    consent_version=consent_version,
                    context_version=context_version,
                    context_resource_version=konteks.versi,
                    sekarang=kini,
                )
            if respons.draft_memori is not None:
                chat = assistant_store.ambil_chat(kon, account_id, chat_id)
                if (
                    chat is None
                    or chat.mode_memori == "tanpa_memori"
                    or not assistant_store.penggunaan_memori_aktif(
                        kon, account_id
                    )
                ):
                    raise GalatPendamping(
                        "Penggunaan memori nonaktif untuk chat ini."
                    )
                assistant_store.tambah_memori(
                    kon,
                    account_id,
                    respons.draft_memori.isi,
                    sumber_chat_id=chat_id,
                    dikonfirmasi=False,
                    sekarang=kini,
                    lingkup=respons.draft_memori.lingkup,
                )
    except GalatPendamping:
        try:
            with kon:
                assistant_store.gagalkan_operasi(
                    kon, account_id, request_id, sekarang=kini
                )
        except Exception:
            kon.rollback()
        raise
    return respons.jawaban
