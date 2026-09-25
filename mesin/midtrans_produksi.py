"""Transport HTTPS produksi eksplisit; hanya host produksi, tanpa fallback.

Sengaja mencerminkan `midtrans_sandbox` (paritas kebijakan: canonical request,
TLS terverifikasi, tanpa redirect/retry, bounded read, deadline) dengan host dan
lingkungan dikunci ke produksi. Konfigurasi diinjeksi dan wajib `production`;
tidak ada env/key default. Modul ini bukan ledger: caller wajib menyimpan hint
durable sebelum efek finansial dan memverifikasi binding lewat kontrak.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import http.client
import re
import ssl
import time

import midtrans_contract as m

HOST = "api.midtrans.com"


@dataclass(frozen=True, repr=False)
class _Respons:
    status: int
    url: str
    headers: dict
    data: bytes = field(repr=False)

    def read(self, batas):
        if type(batas) is not int or not 1 <= batas <= m.BATAS_RESPONS + 1:
            raise m.KontrakTidakSah("batas baca produksi tidak sah")
        return self.data[:batas]


class TransportProduksi:
    """Transport produksi eksplisit; import/inisialisasi tidak membuka jaringan."""

    def __init__(self, config):
        if type(config) is not m.Konfigurasi or config.lingkungan != "production":
            raise m.KontrakTidakSah("hanya konfigurasi produksi yang diizinkan")
        self._config = config

    def _validasi(self, req, timeout, allow_redirects):
        if (type(req) is not m.Permintaan or type(timeout) is not int
                or not 1 <= timeout <= 15 or allow_redirects is not False):
            raise m.KontrakTidakSah("permintaan produksi tidak sah")
        if req.metode == "POST" and req.url == "https://" + HOST + "/v2/charge":
            data = m._json(req.body)
            detail = data["transaction_details"]
            kanonis = m.request_create(self._config, detail["order_id"],
                                      detail["gross_amount"], req.headers["Idempotency-Key"])
            # Kesetaraan byte menolak field kontak, JSON ambigu, header tambahan,
            # dan kredensial yang tidak berasal konfigurasi produksi yang dipilih.
        elif req.metode == "GET" and type(req.url) is str:
            cocok = re.fullmatch(r"https://api\.midtrans\.com/v2/(inv_[0-9a-f]{32})/status", req.url)
            if cocok is None:
                raise m.KontrakTidakSah("tujuan produksi tidak sah")
            kanonis = m.request_status(self._config, cocok.group(1))
        else:
            raise m.KontrakTidakSah("operasi produksi tidak sah")
        if req != kanonis:
            raise m.KontrakTidakSah("payload produksi tidak minimal")
        return req.url[len("https://" + HOST):]

    def __call__(self, req, *, timeout=10, allow_redirects=False):
        return self._kirim(req, timeout=timeout, allow_redirects=allow_redirects)

    def gambar(self, url):
        """Ambil PNG produksi tanpa mengirim key; URL harus berasal status terjaga."""
        req = m.Permintaan("GET", url, {"Accept": "image/png"})
        with self._kirim(req, timeout=10, allow_redirects=False, gambar=True) as respons:
            data = respons.data
        if (not data.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") or len(data) < 33
                or not 1 <= int.from_bytes(data[16:20], "big") <= 2048
                or not 1 <= int.from_bytes(data[20:24], "big") <= 2048
                or data[24] not in (1, 2, 4, 8, 16)
                or data[25] not in (0, 2, 3, 4, 6)
                or data[26:29] != b"\x00\x00\x00"):
            raise m.KontrakTidakSah("gambar QR produksi tidak sah")
        return data

    @contextmanager
    def _kirim(self, req, *, timeout, allow_redirects, gambar=False):
        koneksi = None
        batas = 256_000 if gambar else m.BATAS_RESPONS
        try:
            if gambar:
                if (not m.url_qr_sah(req.url, "production")
                        or not req.url.startswith("https://" + HOST + "/v2/qris/")):
                    raise m.KontrakTidakSah("tujuan QR produksi tidak sah")
                path = req.url[len("https://" + HOST):]
            else:
                path = self._validasi(req, timeout, allow_redirects)
            konteks = ssl.create_default_context()
            koneksi = http.client.HTTPSConnection(HOST, timeout=timeout, context=konteks)
            tenggat = time.monotonic() + timeout
            koneksi.connect()
            soket = koneksi.sock

            def sisa_waktu():
                sisa = tenggat - time.monotonic()
                if sisa <= 0:
                    raise TimeoutError
                soket.settimeout(sisa)

            sisa_waktu()
            koneksi.request(req.metode, path, body=req.body, headers=req.headers)
            sisa_waktu()
            with koneksi.getresponse() as respons:
                # Redirect/error tidak diikuti dan tidak perlu dibaca payloadnya.
                if respons.status != 200:
                    raise m.KontrakTidakSah("status HTTP produksi belum terverifikasi")
                headers = {"Content-Type": respons.getheader("Content-Type", ""),
                           "Content-Length": respons.getheader("Content-Length")}
                if headers["Content-Type"].split(";", 1)[0].strip().lower() != ("image/png" if gambar else "application/json"):
                    raise m.KontrakTidakSah("tipe respons produksi tidak sah")
                panjang = headers["Content-Length"]
                if panjang is not None and (not re.fullmatch(r"[0-9]{1,9}", panjang)
                                             or int(panjang) > batas):
                    raise m.KontrakTidakSah("respons produksi terlalu besar")
                data = bytearray()
                while len(data) <= batas:
                    sisa_waktu()
                    potongan = respons.read1(min(8192, batas + 1 - len(data)))
                    if not potongan:
                        break
                    data.extend(potongan)
                if len(data) > batas:
                    raise m.KontrakTidakSah("respons produksi terlalu besar")
                if panjang is not None and len(data) != int(panjang):
                    raise m.KontrakTidakSah("respons produksi terpotong")
                hasil = _Respons(respons.status, req.url, headers, bytes(data))
        except Exception:
            raise m.KontrakTidakSah("respons produksi belum terverifikasi") from None
        finally:
            if koneksi is not None:
                try:
                    koneksi.close()
                except Exception:
                    raise m.KontrakTidakSah("penutupan koneksi produksi gagal") from None
        yield hasil
