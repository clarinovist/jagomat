"""Rute admin ubah pemetaan CP per grup: GET `/admin/kurikulum/cp?grup=<topik>/<kode>`, POST `/admin/kurikulum/cp`
(simpan) dan POST `/admin/kurikulum/cp/kembalikan` (kembali ke bawaan kode).

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal. Aturan
mengikuti `admin_sakelar_http`:

- Aksi = pola uang admin (`h._token_final`: CSRF + tinjauan terikat aksi dan sesi + sandi ulang, sesi berkuki),
  same-origin (guard global POST di `web`). Grup target dan revisi HANYA dari tinjauan bertanda tangan; field form
  hanya `butir_N`/`cocok_N` (persis, lewat `wajib_field`). `kurikulum_override.ubah_cp` menegakkan optimistic
  concurrency, jadi kirim ulang form yang sama setelah sukses berakhir konflik 409, bukan ubah ulang.
- Perubahan langsung berlaku (keputusan pemilik 20 Nov 2026, opsi a): tanpa draf, tercatat di audit, bisa dikembalikan.
- DB kurikulum rusak = GET tetap tampil dengan bawaan kode; POST = 503 jujur tanpa path dan tanpa efek.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import admin_http as h
import admin_kurikulum_cp_pages as ui
import admin_kurikulum_pages as peta_ui
import admin_pesanan_aksi as aksi
import admin_security
import admin_store
import kurikulum_cp as cp
import kurikulum_katalog as kat
import kurikulum_override as override

KUNCI_QUERY = frozenset({"grup", "hasil"})
MAKS_FIELD_CP = 2 * override.MAKS_PASANGAN_CP + 3  # butir_N + cocok_N + csrf + tinjauan + reauth
HASIL_TERSIMPAN = "tersimpan"
HASIL_DIKEMBALIKAN = "dikembalikan"
Kunci = Tuple[str, str]


def _kunci_dari_teks(teks) -> Kunci:
    """`topik/kode` persis dari CP_PER_GRUP; selain itu ValueError."""
    topik_id, pemisah, grup_kode = teks.partition("/") if type(teks) is str else ("", "", "")
    if not pemisah or (topik_id, grup_kode) not in cp.CP_PER_GRUP:
        raise ValueError("grup tidak dikenal")
    return topik_id, grup_kode


def _query_halaman(penangan) -> Tuple[Kunci, Optional[str]]:
    """(kunci grup, kode hasil) dari query; kunci/nilai di luar daftar atau `grup` hilang = ValueError (404)."""
    query = h._query(penangan, diizinkan=KUNCI_QUERY)
    hasil = query.get("hasil")
    if "hasil" in query and hasil not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    return _kunci_dari_teks(query.get("grup")), hasil


def _info_grup(kunci: Kunci) -> Tuple[str, str, Tuple[str, ...]]:
    """(nama topik resmi, nama grup, id template pola) dari katalog."""
    for entri in kat.KATALOG:
        for kode, nama, pola in entri.grup:
            if (entri.topik_id, kode) == kunci:
                return peta_ui._nama_topik(entri.topik_id), nama, tuple(pola)
    raise ValueError("grup tidak ada di katalog")


def _tinjauan(akun, sesi, nama_aksi: str, kunci: Kunci, revisi: int) -> str:
    return admin_security.buat_tinjauan(akun, sesi, nama_aksi, {
        "target_id": "%s/%s" % kunci, "target_revisi": revisi})


def _tokens(penangan, principal, kunci: Kunci, revisi: int) -> Optional[Dict[str, Tuple[str, str]]]:
    """{aksi: (csrf, tinjauan)} untuk sesi berkuki; None (baca-saja) untuk sesi tanpa kuki."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {nama: (csrf, _tinjauan(akun, sesi, nama, kunci, revisi))
            for nama in (ui.AKSI_UBAH_CP, ui.AKSI_KEMBALIKAN_CP)}


def _isi_halaman(penangan, principal, kunci: Kunci, hasil: Optional[str]) -> str:
    item = next(i for i in override.daftar_cp() if (i.topik_id, i.grup_kode) == kunci)
    tokens = _tokens(penangan, principal, kunci, item.revisi)
    nama_topik, nama_grup, pola = _info_grup(kunci)
    return ui.halaman_edit(
        item, nama_topik=nama_topik, nama_grup=nama_grup, pola=pola,
        riwayat=override.riwayat_cp(*kunci), hasil=hasil,
        token_ubah=None if tokens is None else tokens[ui.AKSI_UBAH_CP],
        token_kembalikan=None if tokens is None else tokens[ui.AKSI_KEMBALIKAN_CP])


def tangani_get(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        kunci, hasil = _query_halaman(penangan)
        isi = _isi_halaman(penangan, principal, kunci, hasil)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_TANPA_SESI)
        return True
    except ValueError:
        h._tidak_ada(penangan)
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", isi, penangan=penangan, judul=ui.JUDUL, subjudul=ui.SUBJUDUL))
    return True


def _perintah(tinjauan) -> Tuple[Kunci, int]:
    """(kunci grup, revisi) dari tinjauan bertanda tangan; bentuk tak sah = ValueError."""
    meta = tinjauan["data"]
    kunci = _kunci_dari_teks(meta.get("target_id"))
    revisi = meta.get("target_revisi")
    if type(revisi) is not int or revisi < 0:
        raise ValueError("revisi kurikulum tidak sah")
    return kunci, revisi


def _actor(principal) -> str:
    actor = principal.id_akun
    if type(actor) is not str or not actor.strip() or len(actor) > override.MAKS_PELAKU:
        raise ValueError("identitas pelaku tidak sah")
    return actor


def _isi_dari_form(data: dict) -> Tuple[Tuple[str, str], ...]:
    """Pasangan (butir, kecocokan) dari 12 baris tetap; baris dengan butir kosong dilewati.

    Kecocokan semua baris (juga yang butirnya kosong) harus kosong atau salah satu KECOCOKAN; butir
    tak dikenal atau ganda ditolak store (ValueError)."""
    pasangan = []
    for no in range(1, override.MAKS_PASANGAN_CP + 1):
        butir, cocok = data["butir_%d" % no], data["cocok_%d" % no]
        if cocok and cocok not in cp.KECOCOKAN:
            raise ValueError("kecocokan tidak sah")
        if butir:
            pasangan.append((butir, cocok))
    return tuple(pasangan)


def _panggil_store(fungsi, *args, **kwargs) -> None:
    """Jalankan fungsi store; galat dipetakan ke galat umum `jalankan_aman` (tanpa isi galat)."""
    try:
        fungsi(*args, **kwargs)
    except override.KonflikRevisi:
        raise admin_store.KonflikOperasi("revisi kurikulum berubah") from None
    except override.GalatKurikulum:
        raise admin_store.StoreBelumSiap("db kurikulum tidak siap") from None


def _selesai(penangan, kunci: Kunci, hasil: str) -> None:
    h._redirect(penangan, "%s?%s" % (ui.RUTE, urlencode({"grup": "%s/%s" % kunci, "hasil": hasil})))


def _simpan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH_CP, maksimum_field=MAKS_FIELD_CP)
    aksi.wajib_field(data, ui.FIELD_UBAH)
    kunci, revisi = _perintah(tinjauan)
    isi = _isi_dari_form(data)
    _panggil_store(override.ubah_cp, *kunci, isi, actor_id=_actor(principal), revisi_diharapkan=revisi)
    _selesai(penangan, kunci, HASIL_TERSIMPAN)


def _kembalikan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_KEMBALIKAN_CP)
    aksi.wajib_field(data, frozenset())
    kunci, revisi = _perintah(tinjauan)
    _panggil_store(override.kembalikan_cp, *kunci, actor_id=_actor(principal), revisi_diharapkan=revisi)
    _selesai(penangan, kunci, HASIL_DIKEMBALIKAN)


_AKSI_POST = {ui.RUTE: _simpan, ui.RUTE_KEMBALIKAN: _kembalikan}


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
