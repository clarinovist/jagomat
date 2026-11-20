"""Rute admin cetakan soal berpola (C2, manual): GET daftar/baru/periksa dan POST baru/ubah/setujui/nonaktifkan/aktifkan.

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal. Aturan
mengikuti `admin_kurikulum_cp_http` (pola `admin_sakelar_http`):

- Aksi = pola uang admin (`h._token_final`: CSRF + tinjauan terikat aksi dan sesi + sandi ulang, sesi berkuki),
  same-origin (guard global POST di `web`). Sandi ulang wajib di SEMUA aksi (semua admin boleh menyetujui).
- Target HANYA dari tinjauan bertanda tangan: buat = (kelas, bab) dalam `target_id` "kelas/bab"; aksi lain =
  (id, revisi). Field form hanya isian cetakan (persis, lewat `wajib_field`; kelas/bab/id tidak pernah dibaca
  dari form). `MAKS_FIELD_CETAKAN` eksplisit lewat `terima_form(maksimum_field=)`; `MAKS_FIELD` global tidak diubah.
- Sumber selalu "manual"; `actor_id` dari principal.
- Sukses = PRG ke halaman periksa dengan `hasil` dari daftar putih. Isi tak sah atau Setujui/Aktifkan gagal uji
  kelayakan = halaman dirender ulang 400 (nilai ketikan dipertahankan dan di-escape, pesan galat tampil, token
  baru, sandi selalu kosong), tanpa tulis DB. KonflikRevisi = 409; DB cetakan tak siap/rusak = 503.
- Baris yang tak terbaca saat POST (DB rusak, atau hilang) dijawab 503 karena id berasal dari tinjauan yang
  hanya diterbitkan untuk cetakan yang ada.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

import admin_http as h
import admin_kurikulum_cetakan_ai_pages as ui_ai
import admin_kurikulum_cetakan_form as form
import admin_kurikulum_cetakan_pages as ui
import admin_kurikulum_merdeka_http as peta_http
import admin_pesanan_aksi as aksi
import admin_security
import admin_store
import cetakan_ai
import cetakan_ai_store as kuota_ai
import cetakan_pola as pola
import cetakan_store as store
import kurikulum_kelas as kk
import kurikulum_kelas_hitung as hitung

KUNCI_QUERY_BAB = frozenset({"kelas", "bab"})
KUNCI_QUERY_DAFTAR = KUNCI_QUERY_BAB | {"permintaan"}  # permintaan = ringkasan draf AI (C3) setelah PRG
KUNCI_QUERY_PERIKSA = frozenset({"id", "hasil"})
MAKS_FIELD_CETAKAN = len(form.FIELD_ISI) + 3  # isian + csrf + tinjauan + reauth
SUMBER_MANUAL = "manual"
REVISI_BUAT = 0
HASIL_DIBUAT, HASIL_TERSIMPAN = "dibuat", "tersimpan"
HASIL_DISETUJUI, HASIL_DINONAKTIFKAN, HASIL_DIAKTIFKAN = "disetujui", "dinonaktifkan", "diaktifkan"
Token = Tuple[str, str]


def _bab_dari_query(query: Dict[str, str]) -> Tuple[int, kk.Bab]:
    """(kelas, bab) tervalidasi ketat dari query; apa pun yang tak sah atau tak ada = ValueError (404)."""
    kelas, nomor = peta_http._angka_ketat(query.get("kelas")), peta_http._angka_ketat(query.get("bab"))
    ditemukan = hitung.cari_bab(kelas, nomor)
    if ditemukan is None:
        raise ValueError("bab tidak ada")
    return kelas, ditemukan[1]


def _id_dari_query(query: Dict[str, str]) -> int:
    id_cetakan = peta_http._angka_ketat(query.get("id"))
    if id_cetakan < 1:
        raise ValueError("id tidak sah")
    return id_cetakan


def _item_atau_404(id_cetakan: int) -> store.ItemCetakan:
    item = store.ambil(id_cetakan)
    if item is None:
        raise ValueError("cetakan tidak ada")
    return item


def _item_wajib(id_cetakan: int) -> store.ItemCetakan:
    """Item untuk POST; tak terbaca = 503 (id dari tinjauan, jadi DB-lah yang bermasalah)."""
    item = store.ambil(id_cetakan)
    if item is None:
        raise admin_store.StoreBelumSiap("cetakan tidak terbaca")
    return item


# --- token -------------------------------------------------------------------

def _tinjauan(akun, sesi, nama_aksi: str, target_id, revisi: int) -> str:
    return admin_security.buat_tinjauan(akun, sesi, nama_aksi, {"target_id": target_id, "target_revisi": revisi})


def _sesi_berkuki(penangan, principal):
    """(akun, sesi, csrf) untuk sesi berkuki; None untuk sesi tanpa kuki (baca-saja)."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    return akun, sesi, h._csrf(akun, sesi)


def _token_bab(penangan, principal, nama_aksi: str, kelas: int, bab: int) -> Optional[Token]:
    """(csrf, tinjauan) untuk aksi yang menarget satu bab (target_id "kelas/bab", revisi 0)."""
    sesi = _sesi_berkuki(penangan, principal)
    if sesi is None:
        return None
    akun, token_sesi, csrf = sesi
    return csrf, _tinjauan(akun, token_sesi, nama_aksi, "%d/%d" % (kelas, bab), REVISI_BUAT)


def _token_buat(penangan, principal, kelas: int, bab: int) -> Optional[Token]:
    return _token_bab(penangan, principal, ui.AKSI_BUAT, kelas, bab)


def _tokens_item(penangan, principal, item: store.ItemCetakan, revisi: int) -> Optional[Dict[str, Token]]:
    """{aksi: (csrf, tinjauan)} terikat (id, revisi); `revisi` = revisi yang diajukan, bukan hasil baca ulang."""
    sesi = _sesi_berkuki(penangan, principal)
    if sesi is None:
        return None
    akun, token_sesi, csrf = sesi
    return {nama: (csrf, _tinjauan(akun, token_sesi, nama, item.id, revisi))
            for nama in (ui.AKSI_UBAH, ui.AKSI_SETUJUI, ui.AKSI_NONAKTIFKAN, ui.AKSI_AKTIFKAN)}


# --- GET ---------------------------------------------------------------------

def _ringkasan_ai(query: Dict[str, str], kelas: int, bab: kk.Bab, items) -> str:
    """Ringkasan permintaan draf AI bila `?permintaan=` ada dan cocok dengan bab halaman; selain itu kosong."""
    if "permintaan" not in query:
        return ""
    id_permintaan = peta_http._angka_ketat(query["permintaan"])
    if id_permintaan < 1:
        raise ValueError("permintaan tidak sah")
    permintaan = kuota_ai.ambil(id_permintaan)
    if permintaan is None or (permintaan.kelas, permintaan.bab) != (kelas, bab.nomor):
        return ""
    return ui_ai.ringkasan(permintaan, items)


def _bagian_ai(penangan, principal, kelas: int, bab: kk.Bab) -> str:
    """Kartu tombol draf AI: hanya bila kunci ada DAN kuota terbaca dan tersisa (fail-closed)."""
    kunci_ada = cetakan_ai.aktif()
    sisa = kuota_ai.sisa_hari_ini() if kunci_ada else None
    token = _token_bab(penangan, principal, ui_ai.AKSI_DRAF_AI, kelas, bab.nomor) if sisa else None
    return ui_ai.bagian_ai(token, sisa, kunci_ada)


def _isi_daftar(penangan, principal):
    query = h._query(penangan, diizinkan=KUNCI_QUERY_DAFTAR)
    kelas, bab = _bab_dari_query(query)
    items = store.daftar(kelas=kelas, bab=bab.nomor)
    isi = ui.halaman_daftar(kelas, bab, items, atas=_ringkasan_ai(query, kelas, bab, items),
                            ai=_bagian_ai(penangan, principal, kelas, bab))
    return isi, ui.JUDUL_DAFTAR, ui.SUBJUDUL_DAFTAR


def _isi_baru(penangan, principal):
    kelas, bab = _bab_dari_query(h._query(penangan, diizinkan=KUNCI_QUERY_BAB))
    isi = ui.halaman_baru(kelas, bab, _token_buat(penangan, principal, kelas, bab.nomor))
    return isi, ui.JUDUL_BARU, ui.SUBJUDUL_DAFTAR


def _isi_periksa(penangan, principal, item: store.ItemCetakan, revisi: int, *, hasil=None, galat=None, nilai=None):
    return ui.halaman_periksa(
        item, contoh=pola.contoh(item.cetakan), kelayakan=pola.uji_kelayakan(item.cetakan),
        riwayat=store.riwayat(item.id), tokens=_tokens_item(penangan, principal, item, revisi),
        hasil=hasil, galat=galat, nilai=nilai)


def _isi_periksa_get(penangan, principal):
    query = h._query(penangan, diizinkan=KUNCI_QUERY_PERIKSA)
    hasil = query.get("hasil")
    if "hasil" in query and hasil not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    item = _item_atau_404(_id_dari_query(query))
    return _isi_periksa(penangan, principal, item, item.revisi, hasil=hasil), ui.JUDUL_PERIKSA, ui.SUBJUDUL_PERIKSA


_GET = {ui.RUTE: _isi_daftar, ui.RUTE_BARU: _isi_baru, ui.RUTE_PERIKSA: _isi_periksa_get}


def tangani_get(penangan, jalur) -> bool:
    isi_halaman = _GET.get(jalur)
    if isi_halaman is None:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        isi, judul, subjudul = isi_halaman(penangan, principal)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_TANPA_SESI)
        return True
    except ValueError:
        h._tidak_ada(penangan)
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", isi, penangan=penangan, judul=judul, subjudul=subjudul))
    return True


# --- POST: bantu -------------------------------------------------------------

def _actor(principal) -> str:
    actor = principal.id_akun
    if type(actor) is not str or not actor.strip() or len(actor) > store.MAKS_PELAKU:
        raise ValueError("identitas pelaku tidak sah")
    return actor


def _id_dari_tinjauan(tinjauan) -> Tuple[int, int]:
    """(id, revisi) dari tinjauan bertanda tangan; bentuk tak sah = ValueError."""
    meta = tinjauan["data"]
    id_cetakan, revisi = meta.get("target_id"), meta.get("target_revisi")
    if type(id_cetakan) is not int or id_cetakan < 1 or type(revisi) is not int or revisi < 1:
        raise ValueError("target cetakan tidak sah")
    return id_cetakan, revisi


def _bab_dari_tinjauan(tinjauan) -> Tuple[int, kk.Bab]:
    """(kelas, bab) dari `target_id` "kelas/bab" bertanda tangan (revisi harus 0); selain itu ValueError."""
    meta = tinjauan["data"]
    teks = meta.get("target_id")
    kelas, pemisah, nomor = teks.partition("/") if type(teks) is str else ("", "", "")
    if not pemisah or meta.get("target_revisi") != REVISI_BUAT:
        raise ValueError("target bab tidak sah")
    return _bab_dari_query({"kelas": kelas, "bab": nomor})


def _panggil_store(fungsi, *args, **kwargs):
    """Jalankan fungsi store; KonflikRevisi dan GalatCetakan dipetakan ke galat umum `jalankan_aman`."""
    try:
        return fungsi(*args, **kwargs)
    except store.KonflikRevisi:
        raise admin_store.KonflikOperasi("revisi cetakan berubah") from None
    except store.GalatCetakan:
        raise admin_store.StoreBelumSiap("db cetakan tidak siap") from None


def _selesai(penangan, id_cetakan: int, hasil: str) -> None:
    h._redirect(penangan, ui.url_periksa(id_cetakan, hasil))


def _tampilkan(penangan, principal, isi: str, judul: str, subjudul: str) -> None:
    """Halaman 400 (isi tak sah): dirender ulang, tanpa PRG dan tanpa tulis DB."""
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", isi, penangan=penangan, judul=judul, subjudul=subjudul), 400)


def _tampilkan_baru(penangan, principal, kelas: int, bab: kk.Bab, nilai: dict, galat: str) -> None:
    isi = ui.halaman_baru(kelas, bab, _token_buat(penangan, principal, kelas, bab.nomor), nilai, galat)
    _tampilkan(penangan, principal, isi, ui.JUDUL_BARU, ui.SUBJUDUL_DAFTAR)


def _tampilkan_periksa(penangan, principal, item: store.ItemCetakan, revisi: int, galat: str,
                       nilai: Optional[dict] = None) -> None:
    isi = _isi_periksa(penangan, principal, item, revisi, galat=galat, nilai=nilai)
    _tampilkan(penangan, principal, isi, ui.JUDUL_PERIKSA, ui.SUBJUDUL_PERIKSA)


# --- POST: aksi --------------------------------------------------------------

def _buat(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_BUAT, maksimum_field=MAKS_FIELD_CETAKAN)
    aksi.wajib_field(data, ui.FIELD_BUAT)
    kelas, bab = _bab_dari_tinjauan(tinjauan)
    actor = _actor(principal)
    try:
        isi = form.ke_isi(data, kelas, bab.nomor)
        item = _panggil_store(store.buat_draf, isi, sumber=SUMBER_MANUAL, actor_id=actor)
    except ValueError as galat:
        _tampilkan_baru(penangan, principal, kelas, bab, data, str(galat))
        return
    _selesai(penangan, item.id, HASIL_DIBUAT)


def _ubah(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH, maksimum_field=MAKS_FIELD_CETAKAN)
    aksi.wajib_field(data, ui.FIELD_UBAH)
    id_cetakan, revisi = _id_dari_tinjauan(tinjauan)
    actor = _actor(principal)
    item = _item_wajib(id_cetakan)
    try:
        isi = form.ke_isi(data, item.kelas, item.bab)
        _panggil_store(store.ubah_draf, id_cetakan, isi, actor_id=actor, revisi_diharapkan=revisi)
    except ValueError as galat:
        _tampilkan_periksa(penangan, principal, item, revisi, str(galat), data)
        return
    _selesai(penangan, id_cetakan, HASIL_TERSIMPAN)


def _pindah(penangan, principal, nama_aksi: str, fungsi: Callable, hasil: str) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, nama_aksi)
    aksi.wajib_field(data, frozenset())
    id_cetakan, revisi = _id_dari_tinjauan(tinjauan)
    actor = _actor(principal)
    item = _item_wajib(id_cetakan)
    try:
        _panggil_store(fungsi, id_cetakan, actor_id=actor, revisi_diharapkan=revisi)
    except ValueError as galat:
        _tampilkan_periksa(penangan, principal, item, revisi, str(galat))
        return
    _selesai(penangan, id_cetakan, hasil)


def _setujui(penangan, principal) -> None:
    _pindah(penangan, principal, ui.AKSI_SETUJUI, store.setujui, HASIL_DISETUJUI)


def _nonaktifkan(penangan, principal) -> None:
    _pindah(penangan, principal, ui.AKSI_NONAKTIFKAN, store.nonaktifkan, HASIL_DINONAKTIFKAN)


def _aktifkan(penangan, principal) -> None:
    _pindah(penangan, principal, ui.AKSI_AKTIFKAN, store.aktifkan_kembali, HASIL_DIAKTIFKAN)


_AKSI_POST = {
    ui.RUTE_BARU: _buat, ui.RUTE_UBAH: _ubah, ui.RUTE_SETUJUI: _setujui,
    ui.RUTE_NONAKTIFKAN: _nonaktifkan, ui.RUTE_AKTIFKAN: _aktifkan,
}


def tangani_post(penangan, jalur) -> bool:
    jalankan = _AKSI_POST.get(jalur)
    if jalankan is None:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(penangan, lambda: jalankan(penangan, principal), copy_konflik=ui.COPY_GALAT_KONFLIK,
                       copy_isian=ui.COPY_GALAT_ISIAN, copy_layanan=ui.COPY_TIDAK_SIAP)
    return True
