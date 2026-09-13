"""Parser unggahan admin terbatas, seluruh isi hanya di memori request."""
from email import policy
from email.parser import BytesParser
import re

import admin_security

BATAS_UNGGAH = 64 * 1024


def baca_csv(penangan):
    """Terima satu file CSV dan field form scalar tanpa memakai nama file klien."""
    headers = penangan.headers
    admin_security._asal_sama(headers)
    ukuran = headers.get_all("Content-Length", [])
    if (headers.get("Transfer-Encoding") or len(ukuran) != 1
            or not ukuran[0].isascii() or not ukuran[0].isdigit()
            or not 0 < int(ukuran[0]) <= BATAS_UNGGAH):
        raise ValueError("Ukuran unggahan tidak sah.")
    if len(headers.get_all("Content-Type", [])) != 1:
        raise ValueError("Format unggahan tidak sah.")
    if headers.get_content_type() != "multipart/form-data":
        raise ValueError("Unggah file CSV menggunakan formulir.")
    batas = headers.get_boundary()
    if not batas or not re.fullmatch(r"[A-Za-z0-9'()+_,./:=?-]{1,70}", batas):
        raise ValueError("Batas unggahan tidak sah.")
    raw = penangan.rfile.read(int(ukuran[0]))
    if len(raw) != int(ukuran[0]):
        raise ValueError("Unggahan tidak lengkap.")
    pesan = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + headers["Content-Type"].encode("ascii")
        + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw
    )
    if (not pesan.is_multipart() or pesan.defects
            or pesan.preamble not in (None, "") or pesan.epilogue not in (None, "")):
        raise ValueError("Format unggahan tidak sah.")
    hasil = {}
    for bagian in pesan.iter_parts():
        if (bagian.defects or bagian.is_multipart()
                or bagian.get_content_disposition() != "form-data"
                or len(bagian.get_all("Content-Disposition", [])) != 1
                or bagian.get("Content-Transfer-Encoding")
                or set(k.lower() for k in bagian.keys()) - {"content-disposition", "content-type"}):
            raise ValueError("Bagian unggahan tidak sah.")
        nama = bagian.get_param("name", header="content-disposition")
        if nama not in {"csv", "csrf", "tinjauan", "aksi", "reauth"} or nama in hasil:
            raise ValueError("Field unggahan tidak sah.")
        isi = bagian.get_payload(decode=True)
        if nama == "csv":
            if bagian.get_filename() is None:
                raise ValueError("File CSV wajib.")
            hasil[nama] = isi
        else:
            if bagian.get_filename() is not None or len(isi) > 4096:
                raise ValueError("Field unggahan tidak sah.")
            hasil[nama] = isi.decode("utf-8", "strict")
    if "csv" not in hasil:
        raise ValueError("File CSV wajib.")
    return hasil
