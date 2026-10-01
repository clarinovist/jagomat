"""Router HTTP: Penangan(BaseHTTPRequestHandler) + palang peran/kepemilikan.

Stdlib saja, tanpa framework. Alasan tanpa framework: satu-satunya pengguna
adalah guru di jaringan rumah/VPS sendiri, kuerinya sedikit, dan tiap
dependensi tambahan adalah satu hal lagi yang bisa gagal saat deploy.

Halaman-halamannya tinggal di modul sendiri (dipecah 31 Aug 2026):
    teacher_pages.py   dashboard, sesi, konfirmasi hapus, lembar
    reports.py         laporan per anak + diagnosa
    account_pages.py   akun guru & admin
Aturan lama tetap: modul ini tidak boleh mengimpor students di atas file.
Permukaan murid didelegasikan ke student_http dengan impor terlambat.
"""

from __future__ import annotations

import html
import json
import os
import random
import socket
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

import attachments as lampiran_mod
import auth
import brand
import database
import sessions
import design_tokens as T
from assistant_navigation import tujuan_lanjut
from account_pages import (
    PETA_SECTION_AKUN,
    halaman_akun,
    proses_akun,
)
from generator import LEVEL_BAWAAN
from reports import halaman_laporan
from support_pages import halaman_pesan as _halaman
from teacher_pages import (
    _soal_dari_baris,
    _nama_template,
    buat_sesi_seed_baru,
    halaman_konfirmasi_hapus,
    halaman_anak,
    halaman_lembar,
    halaman_sesi_cetak,
    halaman_sesi_stitch,
    halaman_utama_stitch,
    simpan_sesi,
)
from templates import LEVEL
from topics import TOPIK_BAWAAN, daftar_topik

class Penangan(BaseHTTPRequestHandler):
    def finish(self) -> None:
        """Akhiri respons sebelum menguras sisa input secara terbatas.

        POST dapat ditolak sebelum body tiba: menutup socket langsung dapat
        mengirim RST Linux dan memotong respons 401 yang sebenarnya sudah benar.
        FIN sisi tulis memberi klien respons utuh, lalu sisa input dibuang,
        bukan diproses. Jangan percaya Content-Length atau menunggu tanpa batas.
        """
        try:
            super().finish()
        finally:
            try:
                self.connection.shutdown(socket.SHUT_WR)
                tenggat = time.monotonic() + 0.2
                sisa = 64 * 1024
                while sisa > 0:
                    waktu = tenggat - time.monotonic()
                    if waktu <= 0:
                        break
                    self.connection.settimeout(waktu)
                    bagian = self.connection.recv(min(sisa, 8192))
                    if not bagian:
                        break
                    sisa -= len(bagian)
            except OSError:
                # Klien putus/timeout tetap berakhir di cleanup SocketServer.
                pass

    def _kirim(self, isi: bytes, kode: int = 200) -> None:
        import assistant_browser
        if assistant_browser.memiliki_panel(isi) or assistant_browser.memiliki_bagikan(isi):
            return self._kirim_privat(isi, kode)
        if assistant_browser.memiliki_pilihan_isi(isi):
            isi, _izin_skrip = assistant_browser.lengkapi_respons(isi)
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)

    def _kirim_privat(self, isi: bytes, kode: int = 200) -> None:
        """Respons privat; hanya skrip chat berhash boleh mengakses origin sendiri."""
        import assistant_browser
        isi, izin_skrip = assistant_browser.lengkapi_respons(isi)
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
            + izin_skrip + "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(isi)

    def _kirim_json(self, data: dict, kode: int = 200) -> None:
        """Kirim JSON privat untuk aksi halaman yang tidak bernavigasi."""
        isi = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(kode)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(isi)

    def _kirim_tautan(self, isi: bytes, kode: int = 200) -> None:
        """Respons tautan bearer: jangan simpan, indeks, atau bocorkan URL."""
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(isi)

    def end_headers(self) -> None:
        """Satu titik penanda "respons sudah keluar".

        Ditaruh di sini, bukan di tiap rute: ada 17 tempat yang menutup
        header sendiri (redirect 303, berkas lampiran, halaman cetak), dan
        menandai satu per satu pasti terlewat saat rute baru ditambahkan.
        Dipakai `_galat_500` untuk tahu kapan ia harus diam.
        """
        self._sudah_menjawab = True
        super().end_headers()

    def _galat_500(self) -> None:
        """Respons 500 yang UTUH untuk exception tak terduga.

        Tanpa ini, exception di handler membuat BaseHTTPRequestHandler
        memutus koneksi tanpa menulis apa pun — dan Caddy di depannya
        menerjemahkannya jadi **502 Bad Gateway**: halaman kosong, tanpa
        penjelasan, dan menyesatkan saat diinvestigasi (502 berarti
        "aplikasi mati", padahal aplikasinya hidup dan cuma satu rute yang
        salah). Insiden 3 Sep 2026: KeyError di sesi remedial.

        Traceback TIDAK ikut ke layar — jalur galat sering memegang nama
        anak dan detail internal. Yang teknis dicetak ke log server, satu-
        satunya tempat yang aman untuk itu.
        """
        import traceback

        traceback.print_exc()
        if getattr(self, "_sudah_menjawab", False):
            # Respons sudah keluar: menulis yang kedua merusak yang valid.
            return
        isi = _halaman(
            "Ada yang bermasalah",
            "<h1>Ada yang bermasalah</h1>"
            "<p>Permintaan ini gagal diproses. Kesalahannya ada di sisi "
            "aplikasi, bukan pada yang kamu isi.</p>"
            "<p>Silakan coba lagi. Kalau masih gagal, catat halaman apa "
            "yang kamu buka waktu ini terjadi.</p>"
            '<p><a href="/">Kembali ke halaman depan</a></p>',
        )
        try:
            self._kirim(isi, 500)
        except Exception:  # socket sudah putus — tidak ada lagi yang bisa
            traceback.print_exc()  # dilakukan selain mencatatnya

    def handle_one_request(self) -> None:
        """Reset penanda respons tiap permintaan (koneksi bisa keep-alive)."""
        self._sudah_menjawab = False
        super().handle_one_request()

    def _ambil_token(self) -> str | None:
        import http.cookies

        raw = self.headers.get("Cookie", "") or ""
        try:
            c = http.cookies.SimpleCookie(raw)
            m = c.get("osn_sesi")
            return m.value if m else None
        except Exception:
            return None

    def _set_cookie(self, token: str | None) -> str:
        import http.cookies

        if token is None:
            return "osn_sesi=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
        c = http.cookies.SimpleCookie()
        c["osn_sesi"] = token
        c["osn_sesi"]["path"] = "/"
        c["osn_sesi"]["httponly"] = True
        c["osn_sesi"]["samesite"] = "Lax"
        if self._di_https():
            c["osn_sesi"]["secure"] = True
        c["osn_sesi"]["max-age"] = str(sessions.TTL_DETIK)
        return c.output(header="").strip()

    def _di_https(self) -> bool:
        """Benar bila permintaan ini memang lewat HTTPS.

        Diputus dari petunjuk yang benar-benar menandai HTTPS —
        X-Forwarded-Proto dari proxy (Caddy di VPS) atau env OSN_HTTPS=1 —
        bukan dari nama host. Dulu Secure dipasang untuk semua host
        non-localhost: di mode LAN (serve.py --jaringan, host 192.168.x.x
        lewat HTTP biasa) peramban anak diam-diam membuang kuki Secure itu,
        sehingga setiap muat-ulang tiba tanpa identitas dan halaman murid
        jadi polos sampai masuk ulang (bug lapangan 1 Sep 2026).
        """
        if os.environ.get("OSN_HTTPS") == "1":
            return True
        return (self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https"

    def _kredensial(self):
        return auth.dari_header(self.headers.get("Authorization"))

    def _principal(self):
        """Principal cookie atau Basic yang telah divalidasi dan dikanonkan."""
        if not auth.wajib_sandi():
            return None
        principal = sessions.ambil_principal(self._ambil_token())
        if principal is not None:
            return principal
        kred = self._kredensial()
        return sessions.principal_basic(*kred) if kred else None

    def _sesi_atau_basic(self, peran_wajib: str | None = None):
        """Adapter tuple untuk rute murid dari principal bersama."""
        principal = self._principal()
        if principal is None or (
            peran_wajib is not None and principal.peran != peran_wajib
        ):
            return None
        return principal.pengguna, principal.peran

    def _identitas(self) -> tuple[str, str] | None:
        """(pengguna kanonik, peran), atau identitas guru mode lokal."""
        if not auth.wajib_sandi():
            return ("guru", "guru")
        principal = self._principal()
        if principal is None:
            return None
        return principal.pengguna, principal.peran

    def _peran_saya(self) -> str | None:
        ident = self._identitas()
        return ident[1] if ident else None

    def _lolos_sandi(self) -> bool:
        """Palang pengelola (guru/admin). Dilewati kalau berkas sandi tidak ada."""
        if self._peran_saya() in ("guru", "admin"):
            return True

        pesan = _halaman(
            "Perlu masuk",
            '<h1>Perlu masuk</h1><p><a href="/masuk">Masuk</a> untuk melanjutkan.</p>',
        )
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(pesan)))
        self.end_headers()
        self.wfile.write(pesan)
        return False

    def _bisa_lihat_sesi(self, kon, sesi_id: int) -> bool:
        """Kepemilikan sesi: guru hanya sesi milik keluarganya, admin semua.

        Tolakan rute memakai 404, bukan 403 — keberadaan id orang lain
        bukan informasi yang boleh bocor.
        """
        ident = self._identitas()
        if not ident:
            return False
        if ident[1] == "admin":
            return True
        return database.sesi_milik(kon, sesi_id, ident[0])

    def _bisa_lihat_siswa(self, kon, siswa_id: int) -> bool:
        ident = self._identitas()
        if not ident:
            return False
        if ident[1] == "admin":
            return True
        return database.siswa_milik(kon, siswa_id, ident[0])

    def _bisa_lihat_lampiran(self, kon, lampiran_id: int) -> bool:
        lamp = database.ambil_lampiran(kon, lampiran_id)
        if not lamp:
            return False
        return self._bisa_lihat_sesi(kon, int(lamp["sesi_id"]))

    def _proses_foto_terjaga(self, sesi_id, **kwargs):
        """Provider tanpa koneksi belajar route; service memegang fencing final."""
        import sqlite3
        try:
            return lampiran_mod.proses_foto_terjaga(
                database.BAWAAN, sesi_id, principal=self._principal(),
                periksa_principal=self._principal, **kwargs)
        except LookupError:
            return None, 'not_found'
        except (ValueError, RuntimeError, OSError, sqlite3.Error):
            return None, lampiran_mod.PESAN_FOTO_TERTAHAN

    def _kirim_aset(self, nama: str) -> None:
        """Berkas brand statis dari allow-list brand.ASET.

        Nama diperiksa lewat dict, bukan digabung ke path — traversal `../`
        mustahil secara konstruksi. Nama tak dikenal dijawab 404 dengan body
        yang sama seperti halaman lain, jadi rute ini bukan oracle untuk
        menebak isi filesystem.
        """
        got = brand.berkas(nama)
        if got is None:
            return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
        isi, mime = got
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(isi)))
        # Berkasnya tidak pernah berubah tanpa berganti nama.
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(isi)

    def do_GET(self) -> None:  # noqa: N802
        """Pembungkus jaring pengaman — rutenya di _rute_get."""
        try:
            self._rute_get()
        except Exception:
            self._galat_500()

    def do_POST(self) -> None:  # noqa: N802
        """Pembungkus jaring pengaman — rutenya di _rute_post."""
        try:
            self._rute_post()
        except Exception:
            self._galat_500()

    def _rute_get(self) -> None:
        jalur = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        # Runtime pembayaran produksi (fail-closed) dicoba sekali per server sebelum
        # permukaan pembayaran mana pun; tanpa secret sah, seluruh sakelar tetap OFF.
        import subscription_produksi
        subscription_produksi.pastikan_terpasang(self.server)
        import subscription_callback
        if subscription_callback.tangani_get(self, jalur):
            return
        import subscription_produksi_http
        if subscription_produksi_http.tangani_get(self, jalur):
            return
        import subscription_http
        if subscription_http.tangani_get(self, jalur):
            return
        import admin_http
        import ai_http
        import assistant_http

        if admin_http.tangani_get(self, jalur):
            return
        if jalur == "/akun" and admin_http.tangani_akun_admin(self):
            return
        if ai_http.tangani_get(self, jalur):
            return
        if jalur == "/admin" or jalur.startswith("/admin/"):
            return admin_http.tidak_ada(self)
        if assistant_http.tangani_get(self, jalur):
            return
        import share_http
        if share_http.tangani_tautan_get(self, jalur):
            return
        import public_http
        if public_http.tangani_get(self, jalur):
            return
        import auth_http
        if auth_http.tangani_get(self, jalur):
            return
        import registration_http
        if registration_http.tangani_get(self, jalur):
            return
        import teacher_http
        if teacher_http.tangani_beranda_get(
            self, jalur, self.path, halaman_utama=halaman_utama_stitch
        ):
            return
        if jalur == "/aset" or jalur.startswith("/aset/"):
            # Publik & sengaja sempit: hanya berkas brand statis dari
            # allow-list brand.ASET. Favicon dibutuhkan browser sebelum
            # login, jadi rute ini WAJIB berada sebelum palang guru.
            # Tidak menyentuh basis data.
            # Jalur sudah di-rstrip("/"), jadi "/aset/" tiba sebagai "/aset"
            # dengan nama kosong — tetap 404 lewat allow-list.
            return self._kirim_aset(jalur[len("/aset/"):] if len(jalur) > 5 else "")
        if jalur == "/murid" or jalur.startswith("/murid/"):
            import student_http
            student_http.tangani_get(self, jalur, self.path)
            return
        if not self._lolos_sandi():
            return
        import attachment_http
        if attachment_http.tangani_get(self, jalur):
            return
        import session_http
        if session_http.tangani_hapus_get(
            self, jalur, halaman_konfirmasi=halaman_konfirmasi_hapus
        ):
            return
        if session_http.tangani_get(
            self,
            jalur,
            self.path,
            halaman_cetak=halaman_sesi_cetak,
            halaman_sesi=halaman_sesi_stitch,
        ):
            return
        if session_http.tangani_lembar_get(
            self, jalur, halaman_lembar=halaman_lembar
        ):
            return
        import account_http
        if account_http.tangani_get(
            self, jalur, self.path, halaman=halaman_akun
        ):
            return
        try:
            with database.buka() as kon:
                if jalur.startswith("/anak/") and jalur.count("/") >= 2:
                    # History satu anak (feedback Filia 1 Sep 2026 no. 6):
                    # kartu nama di dashboard menaut ke sini. Palang sama
                    # ketatnya dengan /laporan/<id>.
                    bagian = jalur.split("/")
                    try:
                        anak_id = int(bagian[2])
                    except (ValueError, IndexError):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    if not self._bisa_lihat_siswa(kon, anak_id):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    siswa_baris = kon.execute(
                        "SELECT * FROM siswa WHERE id = ?", (anak_id,)
                    ).fetchone()
                    if not siswa_baris:
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    ident = self._identitas()
                    target_inline = None
                    fragmen_inline = ""
                    try:
                        pasangan = urllib.parse.parse_qsl(
                            urllib.parse.urlsplit(self.path).query,
                            keep_blank_values=True, errors="strict",
                        )
                        if any(kunci == "bantuan" for kunci, _nilai in pasangan):
                            import assistant_inline
                            target_inline = assistant_inline.parse_query_host(
                                "anak", anak_id, pasangan,
                            )
                            principal = sessions.ambil_principal_pendamping(
                                self._ambil_token()
                            )
                            fragmen_inline = assistant_http.fragmen_inline(
                                principal, target_inline,
                                dalam_form=target_inline.posisi == "latihan",
                            )
                    except (ValueError, LookupError):
                        return self._kirim_privat(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    qs = urllib.parse.parse_qs(
                        urllib.parse.urlparse(self.path).query
                    ) if self.path and not target_inline else {}
                    try:
                        sorot = int(qs.get("sorot", ["0"])[0]) or None
                    except (TypeError, ValueError):
                        sorot = None
                    pesan = (qs.get("pesan", [""])[0] or "")[:200]
                    query_profil = urllib.parse.urlsplit(self.path).query if not target_inline else ""
                    try:
                        import profile_history
                        profile_history.parse_filter(query_profil)
                    except (ValueError, UnicodeError):
                        return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
                    hasil = halaman_anak(
                        kon, siswa_baris,
                        peran=ident[1] if ident else "guru",
                        pengguna=ident[0] if ident else "",
                        sorot=sorot,
                        pesan=pesan,
                        bantuan_rencana=(fragmen_inline if target_inline and target_inline.posisi == "rencana" else ""),
                        bantuan_latihan=(fragmen_inline if target_inline and target_inline.posisi == "latihan" else ""),
                        query=query_profil,
                    )
                    return self._kirim_privat(hasil) if target_inline else self._kirim(hasil)
                if jalur.startswith("/laporan/"):
                    siswa_id = int(jalur.split("/")[2])
                    if not self._bisa_lihat_siswa(kon, siswa_id):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    ident = self._identitas()
                    return self._kirim(
                        halaman_laporan(
                            kon, siswa_id,
                            pengguna=ident[0] if ident else "",
                            peran=ident[1] if ident else "guru",
                            query=urllib.parse.urlsplit(self.path).query,
                        )
                    )
        except (ValueError, IndexError):
            pass
        self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)

    def _halaman_masuk_stitch(self, galat: str = "", *, lanjut: str = "") -> bytes:
        """Form masuk editorial dengan dekorasi buku latihan di desktop.

        Di ponsel fokus tetap pada form. Logo menaut beranda, pesan galat
        terkait secara semantik ke form. Handler autentikasi tidak berubah.
        """
        from style_stitch import gaya_stitch
        from teacher_style import SKRIP_MATA_SANDI

        lanjut = tujuan_lanjut(lanjut)
        isian_lanjut = (
            f'<input type="hidden" name="lanjut" value="{html.escape(lanjut)}">'
            if lanjut else ""
        )
        kabar = (
            '<div class="masuk-galat-st" id="galat-masuk" role="alert" aria-atomic="true">'
            '<b>Periksa kembali</b>'
            f'<p>{html.escape(galat)}</p></div>' if galat else ""
        )
        deskripsi_galat = ' aria-describedby="galat-masuk"' if galat else ""
        body = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul("Masuk"))}</title>
{brand.tag_kepala()}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">
<style>{gaya_stitch()}</style></head>
<body class="st">
<main class="masuk-badan-st" aria-labelledby="judul-masuk">
  <div class="masuk-kepala-st">
    <a class="masuk-brand-st" href="/" aria-label="{html.escape(T.NAMA_PRODUK)} — kembali ke beranda">
      {brand.mark("topbar", kelas="ik-owl")}
      <span class="nama-brand">{html.escape(T.NAMA_PRODUK)}</span>
      <span class="masuk-beranda-st" aria-hidden="true">/ beranda</span>
    </a>
  </div>
  <div class="masuk-panel-st">
    <div class="masuk-catatan-st" aria-hidden="true">
      <p class="masuk-alis-st">LEMBAR BARU, SEMANGAT BARU</p>
      <p class="masuk-pesan-st">Mulai lagi,<br><span>dengan caramu.</span></p>
      <div class="masuk-buku-st">
        <span class="masuk-coret-st">✳</span>
        <img class="masuk-maskot-st" src="/aset/maskot-menyapa-v3-240.png"
             width="240" height="240" alt="">
        <span class="masuk-catatan-kecil-st">Satu langkah dulu.</span>
      </div>
    </div>
    <section class="masuk-kartu-st" aria-labelledby="judul-masuk">
      <div class="masuk-sapaan-st">
        <p class="masuk-alis-st">AKUN BELAJARMU</p>
        <h1 class="masuk-judul-st" id="judul-masuk">Selamat datang kembali</h1>
        <p class="masuk-sub-st">{html.escape(T.TAGLINE)}</p>
      </div>
      {kabar}
      <form class="masuk-form-st" method="post" action="/masuk"{deskripsi_galat}>
        {isian_lanjut}
        <div class="masuk-field-st">
          <label for="nama">Nama pengguna</label>
          <input type="text" id="nama" name="nama" autocomplete="username"
                 aria-describedby="petunjuk-nama" required>
          <p class="masuk-petunjuk-st" id="petunjuk-nama">Gunakan nama pengguna saat mendaftar,
          atau akun dari orang tua atau guru.</p>
        </div>
        <div class="masuk-field-st">
          <label for="sandi">Kata sandi</label>
          <input type="password" id="sandi" name="sandi" autocomplete="current-password" required>
        </div>
        <button class="masuk-tombol-st" type="submit">
          Masuk <span aria-hidden="true">→</span>
        </button>
      </form>
      <p class="masuk-link-st"><a href="/lupa-sandi">Lupa sandi?</a></p>
    </section>
  </div>
</main>
<script>{SKRIP_MATA_SANDI}</script>
</body></html>"""
        return body.encode()

    def _handle_masuk(self, data: dict) -> None:
        """Façade kompatibel untuk login yang kini dimiliki ``auth_http``."""
        import auth_http
        auth_http.proses_masuk(self, data)

    def _rute_post(self) -> None:
        jalur = urllib.parse.urlparse(self.path).path.rstrip("/")
        import subscription_produksi
        subscription_produksi.pastikan_terpasang(self.server)
        import subscription_callback
        if subscription_callback.tangani_post(self, jalur):
            return
        import subscription_produksi_http
        if subscription_produksi_http.tangani_post(self, jalur):
            return
        import subscription_http
        if subscription_http.tangani_post(self, jalur):
            return
        import admin_http
        import ai_http
        import assistant_http

        if admin_http.tangani_post(self, jalur):
            return
        if ai_http.tangani_post(self, jalur):
            return
        if jalur == "/admin" or jalur.startswith("/admin/"):
            return admin_http.tidak_ada(self)
        import product_analytics_http as analitik
        if analitik.tangani_post(self, jalur):
            return
        if assistant_http.tangani_inline_post(self, jalur):
            return
        if assistant_http.tangani_post(self, jalur):
            return
        import share_http
        if share_http.tangani_tautan_post(self, jalur):
            return
        import student_http
        if student_http.tangani_post(self, jalur):
            return
        import auth_http
        if auth_http.tangani_post(self, jalur):
            return
        import registration_http
        if registration_http.tangani_post(self, jalur):
            return
        if not self._lolos_sandi():
            return

        if share_http.tangani_guru_post(self, jalur):
            return

        import account_http
        if account_http.tangani_post(
            self,
            jalur,
            proses=proses_akun,
            halaman=halaman_akun,
            peta_section=PETA_SECTION_AKUN,
        ):
            return

        import session_http
        if session_http.tangani_latihan_serupa(
            self, jalur, acak_seed=random.randint
        ):
            return

        if (
            jalur.startswith("/siklus/")
            or (jalur.startswith("/sesi/")
                and jalur.endswith(("/konfirmasi", "/tinjauan", "/batalkan")))
        ):
            import learning_cycle_http

            return learning_cycle_http.tangani(self, jalur, _halaman)

        if session_http.tangani_cerita_post(
            self,
            jalur,
            soal_dari_baris=_soal_dari_baris,
            halaman_sesi=halaman_sesi_stitch,
        ):
            return

        if session_http.tangani_pembuatan_gabungan(
            self,
            jalur,
            daftar_topik=daftar_topik,
            acak_seed=random.randint,
        ):
            return

        if session_http.tangani_pembuatan_remedial(
            self,
            jalur,
            level_bawaan=LEVEL_BAWAAN,
            nama_template=_nama_template,
        ):
            return

        if session_http.tangani_pembuatan_biasa(
            self,
            jalur,
            buat_sesi=buat_sesi_seed_baru,
            topik_bawaan=TOPIK_BAWAAN,
            daftar_topik=daftar_topik,
        ):
            return

        import attachment_http
        if attachment_http.tangani_post(self, jalur):
            return

        if session_http.tangani_hapus_post(
            self,
            jalur,
            halaman_konfirmasi=halaman_konfirmasi_hapus,
            bersihkan_berkas=lampiran_mod.bersihkan_berkas,
        ):
            return

        if session_http.tangani_review_post(
            self,
            jalur,
            simpan_review=simpan_sesi,
            halaman_sesi=halaman_sesi_stitch,
        ):
            return
        return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)

    def log_message(self, *a) -> None:  # senyapkan log akses
        pass
