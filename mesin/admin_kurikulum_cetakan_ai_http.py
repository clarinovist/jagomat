"""POST admin draf AI cetakan soal (C3): `/admin/kurikulum/cetakan/draf-ai`.

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal. Guard sama
persis dengan `admin_kurikulum_cetakan_http._buat` (pola uang admin): CSRF + tinjauan terikat aksi dan sesi +
sandi ulang lewat `aksi.terima_form`, field form PERSIS kosong (`wajib_field`), dan target (kelas, bab) HANYA dari
tinjauan bertanda tangan (`target_id` "kelas/bab", revisi 0), tidak pernah dari form.

Urutan setelah guard: kunci API ada -> `cetakan_ai_store.reservasi` (kuota harian, atomik; penuh = 429, DB kuota
bermasalah = 503, keduanya TANPA memanggil AI) -> satu panggilan `cetakan_ai.minta_kandidat` -> tiap kandidat:
kelas/bab DIPAKSA dari tinjauan (nilai AI ditimpa), `cetakan_pola.validasi` + `uji_kelayakan`, lolos = simpan
sebagai draf `sumber="ai"` (tak pernah aktif otomatis), gagal = alasan dicatat -> `selesaikan` -> PRG ke halaman
cetakan bab itu dengan `?permintaan=<id>`. Kegagalan AI juga PRG ke ringkasan yang sama (status gagal).

Sengaja TIDAK lewat `ai_service`/`ai_store`: sakelar "Hentikan" di /admin/ai tidak mematikan draf cetakan, dan
panggilan ini tidak tercatat di ledger itu (lihat docstring `cetakan_ai`).
"""
from __future__ import annotations

import logging
from typing import List, Sequence

import admin_http as h
import admin_kurikulum_cetakan_ai_pages as ui_ai
import admin_kurikulum_cetakan_http as http_cetakan
import admin_kurikulum_cetakan_pages as ui
import admin_pesanan_aksi as aksi
import admin_store
import cetakan_ai
import cetakan_ai_store as kuota
import cetakan_pola as pola
import cetakan_store as store
import kurikulum_kelas as kk

MAKS_FIELD_DRAF_AI = 3  # csrf + tinjauan + reauth; tanpa isian lain
SUMBER_AI = "ai"
COPY_GALAT_CETAKAN_DB = "Database cetakan tidak dapat ditulis."
COPY_GALAT_TAK_TERDUGA = "Galat tak terduga saat memproses jawaban AI."

_log = logging.getLogger(__name__)


def _simpan_kandidat(mentah, kelas: int, bab: kk.Bab, actor: str) -> store.ItemCetakan:
    """Satu kandidat AI menjadi draf, atau ValueError beralasan. Kelas/bab selalu dari tinjauan."""
    if not isinstance(mentah, dict):
        raise ValueError("kandidat bukan objek cetakan.")
    isi = {**mentah, "kelas": kelas, "bab": bab.nomor}
    hasil = pola.uji_kelayakan(pola.validasi(isi))
    if not hasil.lolos:
        raise ValueError("uji kelayakan gagal: " + "; ".join(hasil.alasan))
    return store.buat_draf(isi, sumber=SUMBER_AI, actor_id=actor)


def _tutup(id_permintaan: int, status: str, draf: Sequence[int], ditolak: Sequence[str]) -> None:
    """Catat hasil permintaan. Gagal mencatat tidak boleh menggugurkan draf yang sudah tersimpan."""
    try:
        kuota.selesaikan(id_permintaan, status, len(draf), draf=draf, ditolak=ditolak)
    except (kuota.GalatKuota, ValueError):
        _log.warning("Hasil permintaan draf AI id=%d tak tercatat.", id_permintaan)


def _olah_kandidat(kandidat: Sequence[object], kelas: int, bab: kk.Bab, actor: str, draf: List[int],
                   ditolak: List[str]) -> None:
    for no, mentah in enumerate(kandidat, start=1):
        try:
            draf.append(_simpan_kandidat(mentah, kelas, bab, actor).id)
        except ValueError as galat:
            ditolak.append("Cetakan %d: %s" % (no, galat))


def _jalankan_permintaan(id_permintaan: int, kelas: int, bab: kk.Bab, actor: str) -> None:
    """Panggil AI, simpan kandidat lolos, tutup permintaan. DB cetakan rusak = 503 setelah dicatat gagal."""
    try:
        kandidat = cetakan_ai.minta_kandidat(kelas, bab)
    except cetakan_ai.GalatAI as galat:
        _tutup(id_permintaan, kuota.STATUS_GAGAL, (), (str(galat),))
        return
    except Exception:
        _tutup(id_permintaan, kuota.STATUS_GAGAL, (), (COPY_GALAT_TAK_TERDUGA,))
        raise
    draf: List[int] = []
    ditolak: List[str] = []
    try:
        _olah_kandidat(kandidat, kelas, bab, actor, draf, ditolak)
    except store.GalatCetakan:
        _tutup(id_permintaan, kuota.STATUS_GAGAL, draf, ditolak + [COPY_GALAT_CETAKAN_DB])
        raise admin_store.StoreBelumSiap("db cetakan tidak siap") from None
    except Exception:
        _tutup(id_permintaan, kuota.STATUS_GAGAL, draf, ditolak + [COPY_GALAT_TAK_TERDUGA])
        raise
    _tutup(id_permintaan, kuota.STATUS_SELESAI, draf, ditolak)


def _reservasi(penangan, kelas: int, bab: kk.Bab, actor: str):
    """id permintaan, atau None setelah menjawab 429/503 (tanpa memanggil AI)."""
    try:
        return kuota.reservasi(kelas, bab.nomor, actor)
    except kuota.KuotaHabis:
        h._galat(penangan, 429, ui_ai.COPY_KUOTA_HABIS_POST)
    except kuota.GalatKuota:
        h._galat(penangan, 503, ui_ai.COPY_KUOTA_TIDAK_SIAP)
    return None


def _draf_ai(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui_ai.AKSI_DRAF_AI, maksimum_field=MAKS_FIELD_DRAF_AI)
    aksi.wajib_field(data, frozenset())
    if not cetakan_ai.aktif():
        h._galat(penangan, 503, ui_ai.COPY_AI_TIDAK_AKTIF)
        return
    kelas, bab = http_cetakan._bab_dari_tinjauan(tinjauan)
    actor = http_cetakan._actor(principal)
    id_permintaan = _reservasi(penangan, kelas, bab, actor)
    if id_permintaan is None:
        return
    _jalankan_permintaan(id_permintaan, kelas, bab, actor)
    h._redirect(penangan, ui_ai.url_daftar_hasil(kelas, bab.nomor, id_permintaan))


def tangani_post(penangan, jalur) -> bool:
    if jalur != ui_ai.RUTE_DRAF_AI:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(penangan, lambda: _draf_ai(penangan, principal), copy_konflik=ui.COPY_GALAT_KONFLIK,
                       copy_isian=ui.COPY_GALAT_ISIAN, copy_layanan=ui.COPY_TIDAK_SIAP)
    return True
