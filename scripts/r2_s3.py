"""Klien S3 minimal untuk Cloudflare R2 (AWS Signature V4), stdlib saja.

Operasi: PutObject (streaming dari berkas), GetObject (streaming ke berkas),
ListObjectsV2 (paginasi) dan DeleteObject. Path-style
`<endpoint>/<bucket>/<kunci>`, region `auto`, service `s3`. Payload selalu
ditandatangani dengan sha256 sebenarnya (`UNSIGNED-PAYLOAD` tidak dipakai).

Keamanan: pesan galat hanya memuat operasi, status HTTP, dan kode galat S3
yang sudah disanitasi. Header, URL penuh, dan isi respons tidak pernah masuk
pesan, jadi kredensial yang di-echo server tidak bocor ke log. Endpoint
non-loopback wajib https.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import http.client
from pathlib import Path
import re
import time
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

REGION = "auto"
SERVICE = "s3"
ALGORITMA = "AWS4-HMAC-SHA256"
HASH_KOSONG = hashlib.sha256(b"").hexdigest()
HOST_LOOPBACK = frozenset(("127.0.0.1", "localhost", "::1"))
PERCOBAAN = 3
JEDA_ULANG_DETIK = (1.0, 2.0)
TIMEOUT_DETIK = 120
BATAS_XML = 16 * 1024 * 1024
BATAS_HALAMAN = 1000
BLOK = 1024 * 1024
_POLA_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")
_POLA_KODE = re.compile(r"^[A-Za-z0-9]{1,64}$")


class GalatS3(Exception):
    """Galat operasi S3; pesan sudah bersih dari rahasia."""


class ObjekS3(NamedTuple):
    kunci: str
    ukuran: int
    diubah: float  # epoch UTC dari LastModified


def sha256_berkas(path) -> str:
    sidik = hashlib.sha256()
    with open(path, "rb") as sumber:
        for blok in iter(lambda: sumber.read(BLOK), b""):
            sidik.update(blok)
    return sidik.hexdigest()


def _hmac(kunci: bytes, pesan: str) -> bytes:
    return hmac.new(kunci, pesan.encode("utf-8"), hashlib.sha256).digest()


def _enkode(teks: str) -> str:
    return quote(teks, safe="-_.~")


def _query_kanonik(query: Iterable[Tuple[str, str]]) -> str:
    pasangan = sorted((_enkode(k), _enkode(v)) for k, v in query)
    return "&".join(f"{k}={v}" for k, v in pasangan)


def _header_kanonik(headers: Dict[str, str]) -> Tuple[str, str]:
    item = sorted((k.lower(), re.sub(r"\s+", " ", v.strip())) for k, v in headers.items())
    isi = "".join(f"{k}:{v}\n" for k, v in item)
    return isi, ";".join(k for k, _ in item)


def tandatangani(metode, path, query, headers, hash_payload, akses, rahasia, region, service) -> str:
    """Hitung nilai header Authorization SigV4.

    `path` sudah ter-URI-encode (S3: sekali, tanpa normalisasi). `headers`
    wajib memuat `host` dan `x-amz-date`; semua header yang diberikan ikut
    ditandatangani.
    """
    tanggal_waktu = {k.lower(): v for k, v in headers.items()}["x-amz-date"]
    tanggal = tanggal_waktu[:8]
    isi_header, daftar_header = _header_kanonik(headers)
    kanonik = "\n".join((metode, path, _query_kanonik(query), isi_header,
                         daftar_header, hash_payload))
    lingkup = f"{tanggal}/{region}/{service}/aws4_request"
    untuk_ditandatangani = "\n".join((
        ALGORITMA, tanggal_waktu, lingkup,
        hashlib.sha256(kanonik.encode("utf-8")).hexdigest()))
    kunci = _hmac(("AWS4" + rahasia).encode("utf-8"), tanggal)
    for bagian in (region, service, "aws4_request"):
        kunci = _hmac(kunci, bagian)
    tanda = hmac.new(kunci, untuk_ditandatangani.encode("utf-8"), hashlib.sha256).hexdigest()
    return (f"{ALGORITMA} Credential={akses}/{lingkup}, "
            f"SignedHeaders={daftar_header}, Signature={tanda}")


def _tanpa_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kode_galat(isi: bytes) -> str:
    try:
        for simpul in ET.fromstring(isi).iter():
            if _tanpa_ns(simpul.tag) == "Code" and _POLA_KODE.match(simpul.text or ""):
                return simpul.text
    except ET.ParseError:
        pass
    return "-"


def _epoch(teks: str) -> float:
    waktu = dt.datetime.strptime(teks[:19], "%Y-%m-%dT%H:%M:%S")
    return waktu.replace(tzinfo=dt.timezone.utc).timestamp()


def _urai_halaman(isi: bytes):
    objek: List[ObjekS3] = []
    terpotong, token = False, None
    for simpul in ET.fromstring(isi):
        nama = _tanpa_ns(simpul.tag)
        if nama == "IsTruncated":
            terpotong = (simpul.text or "").strip().lower() == "true"
        elif nama == "NextContinuationToken":
            token = simpul.text
        elif nama == "Contents":
            kolom = {_tanpa_ns(c.tag): (c.text or "") for c in simpul}
            objek.append(ObjekS3(kolom["Key"], int(kolom["Size"]), _epoch(kolom["LastModified"])))
    return objek, (token if terpotong else None)


class KlienR2:
    def __init__(self, endpoint, bucket, akses, rahasia, *, region=REGION,
                 jam=time.time, tidur=time.sleep):
        bagian = urlsplit(endpoint)
        host = bagian.hostname or ""
        if bagian.scheme not in ("http", "https") or not host or bagian.path not in ("", "/"):
            raise ValueError("endpoint tidak sah")
        if bagian.scheme == "http" and host not in HOST_LOOPBACK:
            raise ValueError("endpoint non-loopback wajib https")
        if not _POLA_BUCKET.match(bucket):
            raise ValueError("nama bucket tidak sah")
        self._https = bagian.scheme == "https"
        self._host, self._port = host, bagian.port
        self._bucket, self._akses, self._rahasia = bucket, akses, rahasia
        self._region, self._jam, self._tidur = region, jam, tidur

    def _header_host(self) -> str:
        return self._host if self._port is None else f"{self._host}:{self._port}"

    def _sambungan(self):
        kelas = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        return kelas(self._host, self._port, timeout=TIMEOUT_DETIK)

    def _siapkan(self, metode, kunci, query, hash_payload, ukuran):
        path = "/" + quote(self._bucket + ("/" + kunci if kunci else ""), safe="/-_.~")
        waktu = dt.datetime.fromtimestamp(self._jam(), dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        header = {"host": self._header_host(), "x-amz-content-sha256": hash_payload,
                  "x-amz-date": waktu}
        header["Authorization"] = tandatangani(metode, path, query, header, hash_payload,
                                         self._akses, self._rahasia, self._region, SERVICE)
        header["Content-Length"] = str(ukuran)
        kueri = _query_kanonik(query)
        return path + ("?" + kueri if kueri else ""), header

    def _sekali(self, metode, kunci, query, berkas, hash_payload, simpan_ke):
        ukuran = 0 if berkas is None else berkas.stat().st_size
        target, header = self._siapkan(metode, kunci, query, hash_payload, ukuran)
        koneksi = self._sambungan()
        try:
            if berkas is None:
                koneksi.request(metode, target, headers=header)
            else:
                with berkas.open("rb") as badan:
                    koneksi.request(metode, target, body=badan, headers=header)
            resp = koneksi.getresponse()
            if resp.status >= 300 or simpan_ke is None:
                return resp.status, resp.read(BATAS_XML)
            with open(simpan_ke, "wb") as keluar:
                for blok in iter(lambda: resp.read(BLOK), b""):
                    keluar.write(blok)
            return resp.status, b""
        finally:
            koneksi.close()

    def _kirim(self, operasi, metode, kunci="", query=(), berkas=None, simpan_ke=None):
        hash_payload = HASH_KOSONG if berkas is None else sha256_berkas(berkas)
        for percobaan in range(PERCOBAAN):
            try:
                status, isi = self._sekali(metode, kunci, query, berkas, hash_payload, simpan_ke)
            except (OSError, http.client.HTTPException):
                status, isi = 599, b""
            if status < 300:
                return isi
            if status < 500 or percobaan == PERCOBAAN - 1:
                kode = "-" if status == 599 else _kode_galat(isi)
                raise GalatS3(f"{operasi} gagal: HTTP {status} {kode}")
            self._tidur(JEDA_ULANG_DETIK[min(percobaan, len(JEDA_ULANG_DETIK) - 1)])
        raise GalatS3(f"{operasi} gagal")  # tidak tercapai

    def put_objek(self, kunci: str, berkas) -> None:
        self._kirim("PutObject", "PUT", kunci, berkas=Path(berkas))

    def ambil_objek(self, kunci: str, simpan_ke) -> None:
        self._kirim("GetObject", "GET", kunci, simpan_ke=simpan_ke)

    def hapus_objek(self, kunci: str) -> None:
        self._kirim("DeleteObject", "DELETE", kunci)

    def daftar_objek(self, prefiks: str, *, maks: Optional[int] = None) -> List[ObjekS3]:
        hasil: List[ObjekS3] = []
        token = None
        for _ in range(BATAS_HALAMAN):
            query = [("list-type", "2"), ("prefix", prefiks)]
            if maks is not None:
                query.append(("max-keys", str(maks)))
            if token:
                query.append(("continuation-token", token))
            try:
                objek, token = _urai_halaman(self._kirim("ListObjectsV2", "GET", "", query))
            except (ET.ParseError, KeyError, ValueError) as galat:
                raise GalatS3("ListObjectsV2 gagal: respons tidak terbaca") from galat
            hasil.extend(objek)
            if token is None:
                return hasil
        raise GalatS3("ListObjectsV2 gagal: terlalu banyak halaman")

