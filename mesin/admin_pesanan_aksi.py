"""Pembantu bersama aksi POST admin transfer (keputusan verifikasi, pengaturan rekening).

Satu tempat untuk pola yang sama dengan aksi pesanan admin lain: baca form bertanda asal sama lalu
`h._token_final` (CSRF + tinjauan terikat aksi dan sesi + sandi ulang, wajib sesi berkuki), dan peta galat
ke pesan tetap (tanpa `str(galat)`, tanpa nomor rekening atau data isian di respons).
"""
from __future__ import annotations

import re
import sqlite3

import admin_http as h
import admin_pesanan_pages as ui
import admin_security
import admin_store
import pesanan

_KONFLIK = (pesanan.PesananKonflik, admin_store.KonflikOperasi)
_ISIAN = (pesanan.PesananDataTidakSah, ValueError, KeyError, TypeError)
_LAYANAN = (pesanan.PesananError, admin_store.StoreBelumSiap, sqlite3.Error, OSError)
MAKS_FIELD = 8
_POLA_ORDER = re.compile(r"ord_[0-9a-f]{32}")


def terima_form(penangan, principal, aksi: str, *, maksimum_field: int = MAKS_FIELD):
    """(tinjauan, data) bila form sah; selain itu PermissionError/ValueError (dipetakan `jalankan_aman`).

    `data` sudah tanpa csrf/tinjauan/reauth, jadi hanya berisi isian aksi itu sendiri. `maksimum_field`
    (termasuk csrf, tinjauan, reauth) hanya dinaikkan eksplisit oleh aksi yang memang berisian banyak.
    """
    data = admin_security.baca_form(penangan, maksimum_field=maksimum_field)
    _akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)
    return tinjauan, data


def wajib_field(data: dict, harap: frozenset) -> None:
    """Isian harus persis `harap`: kurang atau asing (misalnya admin_id, order_id) = ValueError."""
    if set(data) != harap:
        raise ValueError("isian tidak sah")


def periksa_order(order_id) -> str:
    """`order_id` harus persis `ord_` + 32 hex huruf kecil; selain itu ValueError."""
    if type(order_id) is not str or _POLA_ORDER.fullmatch(order_id) is None:
        raise ValueError("order tidak sah")
    return order_id


def order_dari_tinjauan(tinjauan) -> str:
    """`order_id` hanya dari tinjauan bertanda tangan (`target_id`), tidak pernah dari field form."""
    return periksa_order(tinjauan["data"].get("target_id"))


def jalankan_aman(penangan, aksi, *, copy_konflik: str, copy_isian: str = ui.COPY_GALAT_ISIAN,
                  copy_layanan: str = ui.COPY_GALAT_LAYANAN) -> None:
    """Jalankan `aksi()`; galat dipetakan ke respons tetap. Urutan: izin, tak ada, isian, konflik, layanan."""
    try:
        aksi()
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_GALAT_FORM)
    except (LookupError, pesanan.PesananTidakDitemukan):
        h._tidak_ada(penangan)
    except _ISIAN:
        h._galat(penangan, 400, copy_isian)
    except _KONFLIK:
        h._galat(penangan, 409, copy_konflik)
    except _LAYANAN:
        h._galat(penangan, 503, copy_layanan)
