"""Fasad domain pesanan Paket Coba Rp49.000 (QRIS, sekali bayar) + gerbang pembayaran.

Domain murni di koneksi DB admin-control: tanpa HTTP, tanpa jaringan, tanpa env
(kecuali lewat `baca_gerbang`), tanpa tabel `langganan_*`. Pecahan:
`pesanan_dasar` (konstanta/galat/transaksi), `pesanan_order`, `pesanan_status`,
`pesanan_provider`, `pesanan_jendela` (jendela bayar/QR, buka ulang), `pesanan_admin`; skema di `schema_pesanan`.
Jalur transfer rekening (verifikasi manual): `pesanan_transfer` + `pesanan_transfer_baca`, skema `schema_transfer`.
"""
from __future__ import annotations

from pesanan_admin import catat_refund, catat_yatim, daftar_admin  # noqa: F401
from pesanan_dasar import (  # noqa: F401
    CHANNEL, KEDALUWARSA_JAM, KUOTA_ORDER, MATA_UANG, PREFIX_ORDER,
    PROVIDER, RUPIAH_PAKET, STATUS_BELUM_BAYAR, STATUS_DIREFUND, STATUS_KEDALUWARSA,
    STATUS_DITOLAK, STATUS_MENUNGGU_VERIFIKASI,
    STATUS_PERLU_DIPERIKSA, STATUS_SUDAH_DIBAYAR, STATUS_TURUNAN, PesananButuhKontak,
    PesananDataTidakSah, PesananError, PesananKonflik, PesananKuotaHabis,
    PesananTidakDitemukan, buka,
)
from pesanan_jendela import (  # noqa: F401
    MAKS_JENDELA, PesananBatasJendela, buka_jendela_ulang, jendela_terbaru,
)
from pesanan_order import buat_order, periksa_prasyarat_cek  # noqa: F401
from pesanan_provider import catat_petunjuk, terapkan_hasil_provider  # noqa: F401
from pesanan_status import ambil_order, status_order  # noqa: F401

TAHAP_GERBANG = ("checkout", "penegakan")


def gerbang_pembayaran(funnel_aktif, sakelar_efektif, tahap) -> bool:
    """True HANYA bila ketiga syarat terpenuhi; selain itu (termasuk non-bool/None) False.

    `funnel_aktif` dan `sakelar_efektif` harus bool True persis; `tahap` harus
    'checkout' atau 'penegakan'. `FUNNEL_AKTIF` saja tidak pernah cukup.
    """
    return (funnel_aktif is True and sakelar_efektif is True
            and type(tahap) is str and tahap in TAHAP_GERBANG)


def _baca_funnel():
    import funnel_flag
    return funnel_flag.funnel_aktif()


def _baca_sakelar(path_admin, kesiapan):
    """`sakelar_efektif` menghasilkan Sakelar; yang relevan: `buat_pembayaran is True`."""
    if kesiapan is None:
        return False
    import subscription_produksi
    return subscription_produksi.sakelar_efektif(path_admin, kesiapan).buat_pembayaran is True


def _baca_tahap(path_admin):
    import admin_launch_service
    import admin_store
    with admin_store.buka_baca(path_admin) as kon:
        return admin_launch_service.konfigurasi_pembayaran(kon)["tahap"]


def baca_gerbang(path_admin, kesiapan=None, *, funnel=None, sakelar=None, tahap=None) -> bool:
    """Gerbang pembayaran dari sumber existing; fail-closed pada galat apa pun.

    `kesiapan` adalah dict readiness dari runtime pembayaran yang SUDAH tervalidasi
    (secret/recovery/callback); None (runtime tak terpasang) -> False. Tiga
    pembaca bisa disuntik (tanpa argumen -> `funnel_flag.funnel_aktif()`,
    `subscription_produksi.sakelar_efektif(path_admin, kesiapan).buat_pembayaran`,
    dan `pembayaran_konfigurasi.tahap`). Fungsi existing dipanggil lewat atribut
    modul saat runtime sehingga mudah di-monkeypatch.
    """
    try:
        return gerbang_pembayaran(
            funnel() if funnel is not None else _baca_funnel(),
            sakelar() if sakelar is not None else _baca_sakelar(path_admin, kesiapan),
            tahap() if tahap is not None else _baca_tahap(path_admin))
    except Exception:
        return False
