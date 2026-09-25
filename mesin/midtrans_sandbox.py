"""Adapter HTTPS opt-in untuk QRIS sandbox; tidak dihubungkan ke aplikasi.

Konfigurasi diinjeksi, tanpa env/key default, proxy, redirect atau retry otomatis.
Hanya request minimal dari midtrans_contract diterima sebelum jaringan dibuka.
Transport ini bukan ledger: caller wajib menyimpan intent sebelum create, lalu
query order sama saat hasil tidak pasti. Tidak boleh digunakan untuk produksi.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import http.client
import re
import ssl
import time

import midtrans_contract as m

HOST = "api.sandbox.midtrans.com"


@dataclass(frozen=True, repr=False)
class _Respons:
    status: int
    url: str
    headers: dict
    data: bytes = field(repr=False)

    def read(self, batas):
        if type(batas) is not int or not 1 <= batas <= m.BATAS_RESPONS + 1:
            raise m.KontrakTidakSah("batas baca sandbox tidak sah")
        return self.data[:batas]


class TransportSandbox:
    """Transport sandbox eksplisit; import/inisialisasi tidak membuka jaringan."""

    def __init__(self, config):
        if type(config) is not m.Konfigurasi or config.lingkungan != "sandbox":
            raise m.KontrakTidakSah("hanya konfigurasi sandbox yang diizinkan")
        self._config = config

    def _validasi(self, req, timeout, allow_redirects):
        if (type(req) is not m.Permintaan or type(timeout) is not int
                or not 1 <= timeout <= 15 or allow_redirects is not False):
            raise m.KontrakTidakSah("permintaan sandbox tidak sah")
        if req.metode == "POST" and req.url == "https://" + HOST + "/v2/charge":
            data = m._json(req.body)
            detail = data["transaction_details"]
            kanonis = m.request_create(self._config, detail["order_id"],
                                      detail["gross_amount"], req.headers["Idempotency-Key"])
            # Kesetaraan byte menolak field kontak, JSON ambigu, header tambahan,
            # dan kredensial yang tidak berasal konfigurasi sandbox yang dipilih.
        elif req.metode == "GET" and type(req.url) is str:
            cocok = re.fullmatch(r"https://api\.sandbox\.midtrans\.com/v2/(inv_[0-9a-f]{32})/status", req.url)
            if cocok is None:
                raise m.KontrakTidakSah("tujuan sandbox tidak sah")
            kanonis = m.request_status(self._config, cocok.group(1))
        else:
            raise m.KontrakTidakSah("operasi sandbox tidak sah")
        if req != kanonis:
            raise m.KontrakTidakSah("payload sandbox tidak minimal")
        return req.url[len("https://" + HOST):]

    @contextmanager
    def __call__(self, req, *, timeout=10, allow_redirects=False):
        koneksi = None
        try:
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
                    raise m.KontrakTidakSah("status HTTP sandbox belum terverifikasi")
                headers = {"Content-Type": respons.getheader("Content-Type", ""),
                           "Content-Length": respons.getheader("Content-Length")}
                if headers["Content-Type"].split(";", 1)[0].strip().lower() != "application/json":
                    raise m.KontrakTidakSah("tipe respons sandbox tidak sah")
                panjang = headers["Content-Length"]
                if panjang is not None and (not re.fullmatch(r"[0-9]{1,9}", panjang)
                                             or int(panjang) > m.BATAS_RESPONS):
                    raise m.KontrakTidakSah("respons sandbox terlalu besar")
                data = bytearray()
                while len(data) <= m.BATAS_RESPONS:
                    sisa_waktu()
                    potongan = respons.read1(min(8192, m.BATAS_RESPONS + 1 - len(data)))
                    if not potongan:
                        break
                    data.extend(potongan)
                if len(data) > m.BATAS_RESPONS:
                    raise m.KontrakTidakSah("respons sandbox terlalu besar")
                if panjang is not None and len(data) != int(panjang):
                    raise m.KontrakTidakSah("respons sandbox terpotong")
                hasil = _Respons(respons.status, req.url, headers, bytes(data))
        except Exception:
            raise m.KontrakTidakSah("respons sandbox belum terverifikasi") from None
        finally:
            if koneksi is not None:
                try:
                    koneksi.close()
                except Exception:
                    raise m.KontrakTidakSah("penutupan koneksi sandbox gagal") from None
        yield hasil
