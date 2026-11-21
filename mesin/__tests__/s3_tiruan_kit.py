"""Server S3 tiruan lokal (thread, 127.0.0.1) untuk tes backup off-site.

Verifikator SigV4 di sini sengaja ditulis TERPISAH dari `scripts/r2_s3.py`
(kanonisasi dihitung ulang dari path/query/header mentah yang diterima), supaya
bug di sisi klien tidak tertutup oleh kode yang sama. Hanya data sintetis.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import http.server
import re
import threading
import time
from urllib.parse import unquote

AKSES_UJI = "AKIAUJITIRUAN0001"
RAHASIA_UJI = "rahasia-uji-tiruan/ABCDEFGHIJKLMNOPQRSTUVWXYZ+0123"
BUCKET_UJI = "bucket-uji"
TOLERANSI_JAM = 900


def _pct(teks: str) -> str:
    keluar = []
    for bita in teks.encode("utf-8"):
        huruf = chr(bita)
        aman = bita < 128 and (huruf.isalnum() or huruf in "-_.~")
        keluar.append(huruf if aman else "%%%02X" % bita)
    return "".join(keluar)


def _query_kanon(mentah: str) -> str:
    pasangan = []
    for potong in filter(None, mentah.split("&")):
        k, _, v = potong.partition("=")
        pasangan.append((_pct(unquote(k)), _pct(unquote(v))))
    return "&".join(f"{k}={v}" for k, v in sorted(pasangan))


def _kunci_tanda(rahasia: str, tanggal: str, region: str) -> bytes:
    kunci = ("AWS4" + rahasia).encode()
    for bagian in (tanggal, region, "s3", "aws4_request"):
        kunci = hmac.new(kunci, bagian.encode(), hashlib.sha256).digest()
    return kunci


class S3Tiruan:
    def __init__(self, bucket=BUCKET_UJI, akses=AKSES_UJI, rahasia=RAHASIA_UJI, jam=time.time):
        self.bucket, self.akses, self.rahasia, self.jam = bucket, akses, rahasia, jam
        self.objek = {}  # kunci -> (bytes, epoch)
        self.payload_diterima = []
        self.permintaan = []  # (metode, kunci)
        self.gagal = {}  # (metode, kunci) -> status; selalu gagal
        self.ukuran_halaman = 1000
        self.kunci_diverifikasi = 0
        self._kunci_db = threading.Lock()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.tiruan = self
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._server.shutdown()
        self._server.server_close()

    def taruh(self, kunci: str, data: bytes, diubah: float | None = None) -> None:
        self.objek[kunci] = (data, self.jam() if diubah is None else diubah)

    def kunci_ada(self) -> list:
        return sorted(self.objek)

    # -- verifikasi tanda tangan (implementasi independen) --
    def _tanda_sah(self, h, badan: bytes) -> bool:
        cocok = re.fullmatch(
            r"AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/s3/aws4_request, "
            r"SignedHeaders=([a-z0-9;\-]+), Signature=([0-9a-f]{64})",
            h.headers.get("Authorization", ""))
        if not cocok:
            return False
        akses, tanggal, region, daftar, tanda = cocok.groups()
        stempel = h.headers.get("x-amz-date", "")
        if akses != self.akses or not stempel.startswith(tanggal):
            return False
        waktu = dt.datetime.strptime(stempel, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        if abs(waktu.timestamp() - self.jam()) > TOLERANSI_JAM:
            return False
        if h.headers.get("x-amz-content-sha256") != hashlib.sha256(badan).hexdigest():
            return False
        path, _, kueri = h.path.partition("?")
        nama = daftar.split(";")
        if not {"host", "x-amz-date", "x-amz-content-sha256"} <= set(nama):
            return False
        blok = "".join(f"{n}:{' '.join(h.headers[n].split())}\n" for n in nama)
        kanon = "\n".join((h.command, path, _query_kanon(kueri), blok, daftar,
                           h.headers["x-amz-content-sha256"]))
        sts = "\n".join(("AWS4-HMAC-SHA256", stempel, f"{tanggal}/{region}/s3/aws4_request",
                         hashlib.sha256(kanon.encode()).hexdigest()))
        harap = hmac.new(_kunci_tanda(self.rahasia, tanggal, region), sts.encode(),
                         hashlib.sha256).hexdigest()
        return hmac.compare_digest(harap, tanda)


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def induk(self):
        return self.server.tiruan

    def log_message(self, *_):
        pass

    def _balas(self, status, isi=b"", jenis="application/xml"):
        self.send_response(status)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Content-Type", jenis)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(isi)

    def _galat(self, status, kode):
        # Seperti S3 sungguhan: badan galat meng-echo access key.
        self._balas(status, (f"<Error><Code>{kode}</Code>"
                             f"<AWSAccessKeyId>{self.induk.akses}</AWSAccessKeyId></Error>").encode())

    def _tangani(self):
        panjang = int(self.headers.get("Content-Length") or 0)
        badan = self.rfile.read(panjang) if panjang else b""
        path = self.path.partition("?")[0]
        awal = f"/{self.induk.bucket}"
        kunci = unquote(path[len(awal) + 1:]) if path.startswith(awal) else ""
        with self.induk._kunci_db:
            self.induk.permintaan.append((self.command, kunci))
            if self.command == "PUT":
                self.induk.payload_diterima.append(badan)
            if not self.induk._tanda_sah(self, badan):
                return self._galat(403, "SignatureDoesNotMatch")
            self.induk.kunci_diverifikasi += 1
            status = self.induk.gagal.get((self.command, kunci))
            if status:
                return self._galat(status, "InternalError")
            self._layani(kunci, badan)

    def _layani(self, kunci, badan):
        if self.command == "PUT":
            self.induk.objek[kunci] = (badan, self.induk.jam())
            return self._balas(200)
        if self.command == "DELETE":
            self.induk.objek.pop(kunci, None)
            return self._balas(204)
        if kunci:
            if kunci not in self.induk.objek:
                return self._galat(404, "NoSuchKey")
            return self._balas(200, self.induk.objek[kunci][0], "application/octet-stream")
        self._daftar()

    def _daftar(self):
        kueri = dict(p.partition("=")[::2] for p in self.path.partition("?")[2].split("&") if p)
        kueri = {unquote(k): unquote(v) for k, v in kueri.items()}
        prefiks = kueri.get("prefix", "")
        semua = sorted(k for k in self.induk.objek if k.startswith(prefiks))
        token = kueri.get("continuation-token", "")
        mulai = int(token.rsplit("=", 2)[0].split("/")[-1]) if token else 0
        halaman = min(int(kueri.get("max-keys", 1000)), self.induk.ukuran_halaman)
        potong = semua[mulai:mulai + halaman]
        lagi = mulai + halaman < len(semua)
        isi = ['<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">',
               f"<IsTruncated>{'true' if lagi else 'false'}</IsTruncated>"]
        if lagi:
            isi.append(f"<NextContinuationToken>tok+/{mulai + halaman}==</NextContinuationToken>")
        for k in potong:
            data, epoch = self.induk.objek[k]
            waktu = dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            isi.append(f"<Contents><Key>{k}</Key><LastModified>{waktu}</LastModified>"
                       f"<Size>{len(data)}</Size></Contents>")
        isi.append("</ListBucketResult>")
        self._balas(200, "".join(isi).encode())

    do_PUT = do_GET = do_DELETE = _tangani
