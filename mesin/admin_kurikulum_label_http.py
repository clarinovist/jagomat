"""Rute admin ubah label awam topik: GET `/admin/kurikulum/label?topik=<id>`, POST `/admin/kurikulum/label`
(simpan) dan POST `/admin/kurikulum/label/kembalikan` (kembali ke bawaan kode).

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal. Aturan
mengikuti `admin_kurikulum_cp_http`:

- Aksi = pola uang admin (`h._token_final`: CSRF + tinjauan terikat aksi dan sesi + sandi ulang, sesi berkuki),
  same-origin (guard global POST di `web`). Topik target dan revisi HANYA dari tinjauan bertanda tangan; field
  form hanya `label` (persis, lewat `wajib_field`; kembalikan = tanpa field). `kurikulum_override.ubah_label`
  menegakkan optimistic concurrency dan keunikan label.
- Label yang sama persis dengan nama resmi yang dipetakan `topik_awam.dari_nama_lama` ditolak: teks tersimpannya
  akan terbaca sebagai nama lama dan ikut berubah bersama label topik lain.
- Perubahan langsung berlaku untuk hasil cek berikutnya (keputusan pemilik 20 Nov 2026, opsi a): tanpa draf,
  tercatat di audit, bisa dikembalikan. Hasil cek yang sudah dinilai tidak berubah.
- DB kurikulum rusak = GET tetap tampil dengan bawaan kode; POST = 503 jujur tanpa path dan tanpa efek.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import admin_http as h
import admin_kurikulum_label_pages as ui
import admin_kurikulum_pages as peta_ui
import admin_pesanan_aksi as aksi
import admin_security
import admin_store
import kurikulum_katalog as kat
import kurikulum_override as override
import topik_awam

KUNCI_QUERY = frozenset({"topik", "hasil"})
HASIL_TERSIMPAN = "tersimpan"
HASIL_DIKEMBALIKAN = "dikembalikan"


def _topik_dari_teks(teks) -> str:
    """`topik_id` persis dari topik berlabel bawaan; selain itu ValueError."""
    if type(teks) is not str or teks not in kat.label_awam():
        raise ValueError("topik tidak dikenal")
    return teks


def _query_halaman(penangan) -> Tuple[str, Optional[str]]:
    """(topik_id, kode hasil) dari query; kunci/nilai di luar daftar atau `topik` hilang = ValueError (404)."""
    query = h._query(penangan, diizinkan=KUNCI_QUERY)
    hasil = query.get("hasil")
    if "hasil" in query and hasil not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    return _topik_dari_teks(query.get("topik")), hasil


def _tinjauan(akun, sesi, nama_aksi: str, topik_id: str, revisi: int) -> str:
    return admin_security.buat_tinjauan(akun, sesi, nama_aksi, {
        "target_id": topik_id, "target_revisi": revisi})


def _tokens(penangan, principal, topik_id: str, revisi: int) -> Optional[Dict[str, Tuple[str, str]]]:
    """{aksi: (csrf, tinjauan)} untuk sesi berkuki; None (baca-saja) untuk sesi tanpa kuki."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {nama: (csrf, _tinjauan(akun, sesi, nama, topik_id, revisi))
            for nama in (ui.AKSI_UBAH_LABEL, ui.AKSI_KEMBALIKAN_LABEL)}


def _isi_halaman(penangan, principal, topik_id: str, hasil: Optional[str]) -> str:
    item = next(i for i in override.daftar_label() if i.topik_id == topik_id)
    tokens = _tokens(penangan, principal, topik_id, item.revisi)
    return ui.halaman_edit(
        item, nama_resmi=peta_ui._nama_topik(topik_id),
        riwayat=override.riwayat_label(topik_id), hasil=hasil,
        token_ubah=None if tokens is None else tokens[ui.AKSI_UBAH_LABEL],
        token_kembalikan=None if tokens is None else tokens[ui.AKSI_KEMBALIKAN_LABEL])


def tangani_get(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        topik_id, hasil = _query_halaman(penangan)
        isi = _isi_halaman(penangan, principal, topik_id, hasil)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_TANPA_SESI)
        return True
    except ValueError:
        h._tidak_ada(penangan)
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", isi, penangan=penangan, judul=ui.JUDUL, subjudul=ui.SUBJUDUL))
    return True


def _perintah(tinjauan) -> Tuple[str, int]:
    """(topik_id, revisi) dari tinjauan bertanda tangan; bentuk tak sah = ValueError."""
    meta = tinjauan["data"]
    topik_id = _topik_dari_teks(meta.get("target_id"))
    revisi = meta.get("target_revisi")
    if type(revisi) is not int or revisi < 0:
        raise ValueError("revisi kurikulum tidak sah")
    return topik_id, revisi


def _actor(principal) -> str:
    actor = principal.id_akun
    if type(actor) is not str or not actor.strip() or len(actor) > override.MAKS_PELAKU:
        raise ValueError("identitas pelaku tidak sah")
    return actor


def _label_dari_form(data: dict) -> str:
    """Label dari field `label`; ditolak bila sama persis dengan nama resmi yang dipetakan `dari_nama_lama`."""
    label = data["label"]
    if topik_awam.bentrok_nama_resmi(label.strip()):
        raise ValueError("label sama dengan nama resmi topik")
    return label


def _panggil_store(fungsi, *args, **kwargs) -> None:
    """Jalankan fungsi store; galat dipetakan ke galat umum `jalankan_aman` (tanpa isi galat)."""
    try:
        fungsi(*args, **kwargs)
    except override.KonflikRevisi:
        raise admin_store.KonflikOperasi("revisi kurikulum berubah") from None
    except override.GalatKurikulum:
        raise admin_store.StoreBelumSiap("db kurikulum tidak siap") from None


def _selesai(penangan, topik_id: str, hasil: str) -> None:
    h._redirect(penangan, "%s?%s" % (ui.RUTE, urlencode({"topik": topik_id, "hasil": hasil})))


def _simpan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH_LABEL)
    aksi.wajib_field(data, ui.FIELD_UBAH)
    topik_id, revisi = _perintah(tinjauan)
    label = _label_dari_form(data)
    _panggil_store(override.ubah_label, topik_id, label, actor_id=_actor(principal), revisi_diharapkan=revisi)
    _selesai(penangan, topik_id, HASIL_TERSIMPAN)


def _kembalikan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_KEMBALIKAN_LABEL)
    aksi.wajib_field(data, frozenset())
    topik_id, revisi = _perintah(tinjauan)
    _panggil_store(override.kembalikan_label, topik_id, actor_id=_actor(principal), revisi_diharapkan=revisi)
    _selesai(penangan, topik_id, HASIL_DIKEMBALIKAN)


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
