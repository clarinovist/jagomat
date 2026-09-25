"""Runtime pembayaran produksi: hanya dibuat dari konfigurasi server tepercaya.

Tidak membaca env, DB, atau input HTTP. Secret dan artefak recovery dibaca dari
mount privat dengan validasi ketat; tanpa fallback antar lingkungan. Readiness
dihitung dari runtime/artefak (bukan checkbox Admin): `provider_produksi` dari
secret+transport, `callback` dari permukaan callback di image, `recovery` dari
artefak pair deployer, dan `kebijakan` tetap false selama D8/D9 belum diputuskan.
"""

import importlib.util
import json
import re

import admin_subscription
import midtrans_produksi
import midtrans_secret
import subscription as d

BERKAS_RAHASIA_BAWAAN = "/run/secrets/midtrans/produksi-rahasia"
BERKAS_RECOVERY_BAWAAN = "/run/secrets/midtrans/recovery-pair.json"
BATAS_ARTEFAK = 1024
# D8 (refund/late/over) dan D9 (pajak/retensi) belum diputuskan pengguna; nilai ini
# bukan toggle Admin dan tidak boleh diturunkan dari konfigurasi apa pun.
KEBIJAKAN_D8_D9 = False


def _tanpa_duplikat(pasangan):
    hasil = {}
    for nama, nilai in pasangan:
        if nama in hasil:
            raise ValueError("field artefak duplikat")
        hasil[nama] = nilai
    return hasil


def baca_recovery(path=None):
    """Artefak pair recovery dari deployer; absent/rusak berarti belum siap."""
    try:
        data = json.loads(midtrans_secret.baca_privat(BERKAS_RECOVERY_BAWAAN if path is None else path,
                                                      batas=BATAS_ARTEFAK),
                          object_pairs_hook=_tanpa_duplikat)
    except (midtrans_secret.RahasiaTidakSah, ValueError, TypeError):
        return False
    return (type(data) is dict
            and set(data) == {"versi", "revisi", "digest", "kontrak",
                              "pasangan_terverifikasi", "kompatibel", "mode"}
            and data["versi"] == 1
            and _teks(data["revisi"], r"[0-9a-f]{40}")
            and _teks(data["digest"], r"sha256:[0-9a-f]{64}")
            and _teks(data["kontrak"], r"[0-9a-f]{64}")
            and data["pasangan_terverifikasi"] is True and data["kompatibel"] is True
            and data["mode"] in ("migrasi", "rutin"))


def _teks(nilai, pola):
    return type(nilai) is str and re.fullmatch(pola, nilai) is not None


def permukaan_callback():
    """Permukaan callback tersedia di image ini (fakta artifact, bukan deklarasi)."""
    try:
        return importlib.util.find_spec("subscription_callback") is not None
    except (ImportError, ValueError):
        return False


def kesiapan_produksi(*, path_recovery=None):
    """Readiness lengkap; hanya dipanggil setelah konfigurasi produksi tervalidasi."""
    return {"provider_produksi": True, "callback": permukaan_callback(),
            "recovery": baca_recovery(path_recovery), "kebijakan": KEBIJAKAN_D8_D9}


def konfigurasi_tepercaya(path=None):
    """Konfigurasi produksi dari berkas server tepercaya; raise bila rusak."""
    return midtrans_secret.konfigurasi(BERKAS_RAHASIA_BAWAAN if path is None else path)


def konfigurasi_dan_transport(*, path_rahasia=None):
    """Konfigurasi + transport produksi dari berkas tepercaya; raise bila rusak."""
    config = konfigurasi_tepercaya(path_rahasia)
    return config, midtrans_produksi.TransportProduksi(config)


def runtime(*, path_rahasia=None, path_recovery=None):
    """Fail-closed: None bila konfigurasi tepercaya tidak tersedia. Tanpa fallback."""
    try:
        config, transport = konfigurasi_dan_transport(path_rahasia=path_rahasia)
    except (Exception, KeyboardInterrupt):
        return None
    return admin_subscription.RuntimePembayaran(
        config, transport, d.SAKELAR, kesiapan_produksi(path_recovery=path_recovery))


def sakelar_efektif(path_admin, kesiapan):
    """Tangga efektif yang sama dengan permukaan Admin: prasyarat readiness wajib."""
    tersimpan = admin_subscription.sakelar_runtime(path_admin)
    rekonsiliasi = tersimpan.rekonsiliasi and kesiapan["provider_produksi"]
    checkout = (tersimpan.buat_pembayaran and rekonsiliasi
                and kesiapan["callback"] and kesiapan["recovery"])
    return d.Sakelar(fondasi=rekonsiliasi, buat_pembayaran=checkout,
                     rekonsiliasi=rekonsiliasi,
                     penegakan=tersimpan.penegakan and checkout and kesiapan["kebijakan"])


def pasang(server, *, path_rahasia=None, path_recovery=None):
    """Pasang runtime ke server tepercaya; False bila belum siap (fail-closed)."""
    if getattr(server, "pembayaran_runtime", None) is not None:
        raise RuntimeError("runtime pembayaran sudah terpasang")
    hasil = runtime(path_rahasia=path_rahasia, path_recovery=path_recovery)
    if hasil is None:
        return False
    server.pembayaran_runtime = hasil
    return True
