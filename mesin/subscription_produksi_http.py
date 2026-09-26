"""Surface checkout produksi guru di /langganan — server produksi, fail-closed.

Rute: GET /langganan, GET /langganan/<inv>[/qr], POST /langganan/siapkan,
POST /langganan/<inv>/{buat,periksa}. Tanpa runtime produksi terpasang modul ini
tidak melayani apa pun (fallback permukaan sandbox/404), dan tanpa sakelar fondasi
hanya halaman status "belum aktif" yang dirender — tidak ada pembacaan ledger.

Finansial: create/query provider hanya lewat service terjaga; efek finansial tetap
query server-to-server terautentikasi. QR diambil server-side via transport
produksi (allow-list kontrak) lalu disajikan same-origin; URL/harga tidak pernah
dari input browser. 404 identik untuk non-pemilik; log tidak memuat identitas.
"""

from contextlib import contextmanager
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

import admin_security
import admin_store
import admin_subscription
import auth
import database
import midtrans_contract as midtrans
import subscription as d
import subscription_checkout as checkout
import subscription_produksi_pages as halaman
import subscription_service as layanan
import subscription_store as store

POLA = re.compile(r"/langganan/(inv_[0-9a-f]{32})(?:/(buat|periksa|ulang|qr))?\Z")
LINGKAR = ("127.0.0.1", "localhost", "::1")
BATAS_LAJU = 30
_JENDELA_LAJU = 60
_LAJU = {}
_LAJU_KUNCI = threading.Lock()
# Kunci token form per proses; permintaan menyusul saat restart tinggal ditolak
# (TTL 900 s) lalu halaman dimuat ulang — tidak dipakai untuk apa pun yang durable.
_KUNCI = secrets.token_bytes(32)


def ada(penangan):
    """True bila runtime produksi terpasang di server ini (dipakai tautan akun)."""
    return _runtime(penangan) is not None


def _runtime(penangan):
    runtime = admin_subscription.runtime_penangan(penangan)
    if runtime is None or getattr(runtime.config, "lingkungan", None) != "production":
        return None
    if not callable(runtime.transport):
        return None
    return runtime


def _paths():
    return (admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN)


def _principal(penangan):
    p = penangan._principal()
    if p is None or p.peran != "guru" or getattr(p, "metode", None) != "cookie":
        raise LookupError("resource tidak ditemukan")
    return auth.PrincipalAkun(p.pengguna, p.peran, p.id_akun, p.revisi_auth)


def _recheck(penangan, principal):
    if _principal(penangan) != principal:
        raise LookupError("resource tidak ditemukan")


def _token(sesi, principal, aksi, invoice="", *, op=None):
    kini = int(time.time())
    isi = {"aksi": aksi, "invoice": invoice, "op": op or secrets.token_hex(16), "exp": kini + 900}
    tubuh = json.dumps(isi, sort_keys=True, separators=(",", ":")).encode().hex()
    ikat = ":".join((sesi or "", principal.id_akun, str(principal.revisi_auth), tubuh))
    return tubuh + "." + hmac.new(_KUNCI, ikat.encode(), hashlib.sha256).hexdigest()


def _periksa_token(sesi, principal, token, aksi, invoice=""):
    try:
        if type(token) is not str or len(token) > 1024:
            raise ValueError()
        tubuh, signature = token.split(".")
        ikat = ":".join((sesi or "", principal.id_akun, str(principal.revisi_auth), tubuh))
        harap = hmac.new(_KUNCI, ikat.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, harap):
            raise ValueError()
        data = json.loads(bytes.fromhex(tubuh))
        kini = int(time.time())
        if (set(data) != {"aksi", "invoice", "op", "exp"} or data["aksi"] != aksi
                or data["invoice"] != invoice or type(data["exp"]) is not int
                or not kini < data["exp"] <= kini + 900
                or type(data["op"]) is not str
                or re.fullmatch(r"[0-9a-f]{32}", data["op"]) is None):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise PermissionError("form tidak sah") from None


def _limiti(principal):
    kini = time.monotonic()
    with _LAJU_KUNCI:
        daftar = [t for t in _LAJU.get(principal.id_akun, ()) if kini - t < _JENDELA_LAJU]
        if len(daftar) >= BATAS_LAJU:
            raise PermissionError("batas laju")
        daftar.append(kini)
        _LAJU[principal.id_akun] = daftar
        if len(_LAJU) > 1000:
            for kunci in [k for k, v in _LAJU.items() if not v]:
                del _LAJU[kunci]


def _kirim(penangan, isi, kode=200, *, png=False, lokasi=None):
    penangan.send_response(kode)
    for k, v in admin_security.header_privat().items():
        penangan.send_header(k, v)
    penangan.send_header("X-Content-Type-Options", "nosniff")
    penangan.send_header("Content-Type", "image/png" if png else "text/html; charset=utf-8")
    if lokasi:
        penangan.send_header("Location", lokasi)
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.end_headers()
    penangan.wfile.write(isi)


def _tidak_ada(penangan):
    # Identik untuk anon/guru asing/invoice asing — tanpa identitas atau status.
    _kirim(penangan, halaman.galat(None, "Halaman tidak ada"), 404)


def _transport(penangan, runtime, principal):
    @contextmanager
    def kirim(req, **kw):
        _recheck(penangan, principal)
        with runtime.transport(req, **kw) as respons:
            yield respons
        _recheck(penangan, principal)
    return kirim


def _status(penangan, runtime, principal, inv):
    hasil = midtrans.Hasil()
    if inv["create_dicoba"] and inv["status"] != "lunas" and runtime.sakelar.rekonsiliasi:
        hasil = midtrans.periksa_status(runtime.config, inv, akun_id=principal.id_akun,
                                        transport=_transport(penangan, runtime, principal),
                                        sakelar=runtime.sakelar)
        _recheck(penangan, principal)
    return hasil


def _penerimaan(path_admin, invoice_id):
    """(diterima, akhir periode) receipt grant; None bila belum ada. Tanpa isi sensitif."""
    try:
        with admin_store.buka_baca(path_admin) as kon:
            kon.execute("BEGIN")
            terima = kon.execute(
                "SELECT diterima FROM langganan_receipt WHERE invoice_id=? AND hasil='grant'",
                (invoice_id,)).fetchone()
            grant = kon.execute("SELECT akhir FROM langganan_grant WHERE invoice_id=?",
                                (invoice_id,)).fetchone()
        if terima is None:
            return None, None
        return int(terima[0]), (int(grant[0]) if grant else None)
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError, LookupError, TypeError, ValueError):
        return None, None


def _gambar(runtime, url):
    """Ambil PNG QR via transport produksi; URL wajib lolos allow-list kontrak."""
    if (not midtrans.url_qr_sah(url, "production")
            or not url.startswith(runtime.config.base_url + "/v2/qris/")):
        raise midtrans.KontrakTidakSah("tujuan QR produksi tidak sah")
    fungsi = getattr(runtime.transport, "gambar", None)
    if not callable(fungsi):
        raise midtrans.KontrakTidakSah("gambar QR produksi tidak tersedia")
    return fungsi(url)


def _tangani(penangan, jalur, *, post):
    if jalur != "/langganan" and not jalur.startswith("/langganan/"):
        return False
    runtime = _runtime(penangan)
    if runtime is None:
        return False
    pengguna = None
    try:
        p = _principal(penangan)
        pengguna = p.pengguna
        cocok = POLA.fullmatch(jalur)
        if urlsplit(penangan.path).query or (jalur not in ("/langganan", "/langganan/siapkan") and not cocok):
            raise LookupError()
        if jalur == "/langganan/siapkan" and not post:
            raise LookupError()
        if not runtime.sakelar.fondasi:
            if not post and jalur == "/langganan":
                _kirim(penangan, halaman.belum_aktif(pengguna))
                return True
            raise d.FiturNonaktif("fitur langganan nonaktif")
        _limiti(p)
        kini = int(time.time())
        sesi = penangan._ambil_token()
        if post:
            if not penangan._di_https():
                try:
                    host = urlsplit("//" + str(penangan.headers.get("Host", ""))).hostname
                except ValueError:
                    host = None
                if host not in LINGKAR:
                    raise PermissionError("transport tidak aman")
            if jalur == "/langganan/siapkan":
                aksi, invoice = "siapkan", ""
            elif cocok and cocok.group(2) in ("buat", "periksa", "ulang"):
                invoice, aksi = cocok.groups()
                checkout.baca_tagihan(*_paths(), p, invoice, sakelar=runtime.sakelar)
            else:
                raise LookupError()
            data = admin_security.baca_form(penangan, berulang=("profil",), maksimum_field=34)
            if set(data) != ({"token", "profil"} if aksi == "siapkan" else {"token"}):
                raise ValueError()
            token = _periksa_token(sesi, p, data["token"], aksi, invoice)
            profil = None
            if aksi == "siapkan":
                if any(re.fullmatch(r"[1-9][0-9]{0,18}", n) is None for n in data["profil"]):
                    raise ValueError()
                profil = tuple(int(n) for n in data["profil"])
                if not 1 <= len(profil) <= 3:
                    raise ValueError()
                d.profil_kanonis(profil)
            if aksi == "siapkan":
                inv = checkout.siapkan_tagihan(
                    *_paths(), p, profil, invoice_id="inv_" + token["op"],
                    operasi_id="op_" + token["op"], merchant=runtime.config.merchant,
                    sekarang=kini, kedaluwarsa=kini + 86400, sakelar=runtime.sakelar)
                invoice = inv["invoice_id"]
            else:
                if aksi == "buat":
                    fungsi = layanan.mulai_pembayaran
                elif aksi == "periksa":
                    fungsi = layanan.periksa_pembayaran
                else:
                    fungsi = layanan.buat_ulang_qr
                fungsi(*_paths(), p, invoice, config=runtime.config,
                       transport=_transport(penangan, runtime, p), sekarang=kini,
                       sakelar=runtime.sakelar, cek_sesi=lambda: _recheck(penangan, p))
            _recheck(penangan, p)
            _kirim(penangan, b"", 303, lokasi="/langganan/" + invoice)
        elif jalur == "/langganan":
            _, profil, inv = checkout.ringkasan(*_paths(), p, sakelar=runtime.sakelar)
            aktif = runtime.sakelar.buat_pembayaran
            token = _token(sesi, p, "siapkan") if aktif else ""
            _kirim(penangan, halaman.ringkasan(pengguna, profil, inv, token,
                                                merchant=runtime.config.merchant, aktif=aktif))
        elif cocok and cocok.group(2) in (None, "qr"):
            invoice, aksi = cocok.groups()
            inv = checkout.baca_tagihan(*_paths(), p, invoice, sakelar=runtime.sakelar)
            hasil = _status(penangan, runtime, p, inv)
            if aksi == "qr":
                if (hasil.status != "pending" or not hasil.qr or inv["perlu_diperiksa"]
                        or inv["status"] == "lunas"):
                    raise LookupError()
                data = _gambar(runtime, hasil.qr)
                _recheck(penangan, p)
                checkout.baca_tagihan(*_paths(), p, invoice, sakelar=runtime.sakelar)
                _kirim(penangan, data, png=True)
            else:
                sekarang = int(time.time())
                lunas = inv["status"] == "lunas"
                boleh_buat = (runtime.sakelar.buat_pembayaran and not inv["create_dicoba"]
                              and not lunas and sekarang < inv["kedaluwarsa"])
                boleh_periksa = runtime.sakelar.rekonsiliasi and inv["create_dicoba"] and not lunas
                boleh_ulang = (runtime.sakelar.buat_pembayaran and inv["create_dicoba"]
                               and not lunas and not inv["perlu_diperiksa"]
                               and sekarang < inv["kedaluwarsa"] and hasil.status != "pending")
                if boleh_ulang:
                    # Satu aksi satu entry point: kode mati → tawarkan buat ulang saja.
                    boleh_periksa = False
                status = ("perlu_diperiksa" if inv["perlu_diperiksa"] else
                          ("lunas" if lunas else
                           ("pending" if hasil.status == "pending" else hasil.status)))
                token = _token(sesi, p, "buat" if boleh_buat else ("ulang" if boleh_ulang else "periksa"), invoice)
                diterima = periode = None
                if lunas:
                    diterima, periode = _penerimaan(_paths()[0], invoice)
                _kirim(penangan, halaman.tagihan(
                    pengguna, inv, token=token, status=status, merchant=runtime.config.merchant,
                    boleh_buat=boleh_buat, boleh_periksa=boleh_periksa, boleh_ulang=boleh_ulang,
                    qr_tersedia=(hasil.status == "pending" and bool(hasil.qr)
                                 and not inv["perlu_diperiksa"] and not lunas
                                 and sekarang < inv["kedaluwarsa"]),
                    qr_kedaluwarsa=(not lunas and sekarang >= inv["kedaluwarsa"]),
                    periode=periode, diterima=diterima))
        else:
            raise LookupError()
    except LookupError:
        _tidak_ada(penangan)
    except d.FiturNonaktif:
        _kirim(penangan, halaman.belum_aktif(pengguna), 409)
    except PermissionError as galat:
        pesan = ("Terlalu banyak permintaan. Coba lagi sebentar." if str(galat) == "batas laju"
                 else "Form tidak sah atau kedaluwarsa. Buka ulang halaman.")
        _kirim(penangan, halaman.galat(pengguna, pesan),
               429 if str(galat) == "batas laju" else 403)
    except store.KonflikLangganan:
        _kirim(penangan, halaman.galat(
            pengguna, "Tagihan berubah atau sudah dibekukan. Buka tagihan yang ada."), 409)
    except midtrans.KontrakTidakSah:
        _kirim(penangan, halaman.galat(
            pengguna, "QR/pembayaran sementara belum terverifikasi. Periksa tagihan yang sama nanti."), 503)
    except (ValueError, TypeError):
        _kirim(penangan, halaman.galat(pengguna, "Isian tidak sah. Muat ulang dan coba lagi."), 400)
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError, RuntimeError):
        _kirim(penangan, halaman.galat(
            pengguna, "Pembayaran sementara belum terverifikasi. Periksa tagihan yang sama nanti."), 503)
    return True


def tangani_get(penangan, jalur):
    return _tangani(penangan, jalur, post=False)


def tangani_post(penangan, jalur):
    return _tangani(penangan, jalur, post=True)
