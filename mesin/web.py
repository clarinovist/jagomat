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
        if jalur == "/masuk":
            galat = ""
            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query, keep_blank_values=True
            )
            if q.get("galat"):
                galat = q["galat"][0]
            nilai_lanjut = q.get("lanjut", [])
            lanjut = tujuan_lanjut(nilai_lanjut[0]) if len(nilai_lanjut) == 1 else ""
            # Tujuan hanya petunjuk navigasi, bukan izin membaca resource.
            return self._kirim(self._halaman_masuk_stitch(galat=galat, lanjut=lanjut))
        if jalur in ("/", "/guru", "/ortu"):
            # Orang tua dan guru memakai peran yang sama. Root tetap publik
            # bagi anonim/murid; beranda pendamping punya alamat eksplisit.
            ident = self._identitas()
            if jalur == "/" and (not ident or ident[1] not in ("guru", "admin")):
                from landing import halaman_landing
                import admin_store
                import support_settings

                return self._kirim(halaman_landing(
                    dukungan=support_settings.baca_publik(admin_store.BAWAAN)
                ))
            if not self._lolos_sandi():
                return
            if ident[1] == "admin":
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if jalur != "/guru":
                # Alias lama mempertahankan kabar, bukan tujuan bebas dari URL.
                qs = urllib.parse.urlencode({
                    k: q[k][0] for k in ("pesan", "sorot") if k in q
                })
                self.send_response(303)
                self.send_header("Location", "/guru" + ("?" + qs if qs else ""))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            pesan = (q.get("pesan") or [""])[0][:200]
            try:
                sorot = int((q.get("sorot") or [""])[0])
            except ValueError:
                sorot = None
            with database.buka() as kon:
                isi = halaman_utama_stitch(
                    kon, pesan=pesan, pemilik=ident[0], peran=ident[1], sorot=sorot,
                )
            import product_analytics_http as analitik
            survei = analitik.form_survei(self)
            if survei:
                isi = isi.replace(b'</main>', survei.encode() + b'</main>', 1)
            return self._kirim_privat(isi) if survei else self._kirim(isi)
        if jalur == "/daftar":
            import admin_http
            import admin_registration
            import admin_store
            from landing import halaman_daftar

            try:
                status = admin_registration.status(admin_store.BAWAAN)
                token_form = admin_http.buat_token_pendaftaran() if status.dibuka else ''
            except admin_store.StoreBelumSiap:
                return self._kirim(
                    halaman_daftar(
                        "Pendaftaran sementara belum tersedia. Akun yang sudah ada tetap bisa masuk.",
                        galat=True, pendaftaran_dibuka=False, belum_tersedia=True,
                    ),
                    503,
                )
            import product_analytics_http as analitik
            return self._kirim(halaman_daftar(
                pendaftaran_dibuka=status.dibuka,
                token_form=token_form, analitik=analitik.form_daftar(),
            ))
        if jalur == "/kebijakan-privasi":
            # Publik dan tidak membaca data keluarga. Hanya proyeksi konfigurasi
            # dukungan minimum yang dibaca dari admin-control secara read-only.
            from landing import halaman_kebijakan
            import admin_store
            import support_settings

            return self._kirim(halaman_kebijakan(
                dukungan=support_settings.baca_publik(admin_store.BAWAAN)
            ))
        if jalur == "/lupa-sandi":
            # Publik, dari tautan di /masuk. Aplikasi sengaja tidak
            # menyimpan email, jadi ini halaman panduan ("mintalah sandi
            # baru ke X"), bukan reset mandiri — mengarang alur email
            # berarti mengarang kanal yang tidak ada.
            from landing import halaman_lupa_sandi
            import admin_store
            import support_settings

            return self._kirim(halaman_lupa_sandi(
                dukungan=support_settings.baca_publik(admin_store.BAWAAN)
            ))
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
        if session_http.tangani_get(
            self,
            jalur,
            self.path,
            halaman_cetak=halaman_sesi_cetak,
            halaman_sesi=halaman_sesi_stitch,
        ):
            return
        try:
            with database.buka() as kon:
                if jalur.startswith("/sesi/") and jalur.endswith("/hapus"):
                    sesi_id = int(jalur.split("/")[2])
                    if not self._bisa_lihat_sesi(kon, sesi_id):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    ident = self._identitas()
                    isi = halaman_konfirmasi_hapus(
                        kon, sesi_id,
                        pengguna=ident[0] if ident else "",
                        peran=ident[1] if ident else "guru",
                    )
                    if isi is None:
                        return self._kirim(
                            _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
                        )
                    return self._kirim(isi)
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
                if jalur == "/akun":
                    ident = self._identitas()
                    try:
                        pasangan = urllib.parse.parse_qsl(
                            urllib.parse.urlsplit(self.path).query,
                            keep_blank_values=True, errors="strict",
                        )
                        if len(pasangan) != len({k for k, _v in pasangan}):
                            raise ValueError("parameter ganda")
                        q = dict(pasangan)
                        if set(q) - {"section", "halaman", "chat"}:
                            raise ValueError("parameter asing")
                        section = q.get("section", "akun")
                        arsip = ""
                        if section in ("akun", "arsip-pendamping"):
                            if set(q) - ({"section"} if section == "akun" else {"section", "halaman", "chat"}):
                                raise ValueError("parameter arsip tidak sah")
                            halaman = int(q.get("halaman", "1"))
                            if not 1 <= halaman <= 501:
                                raise ValueError("halaman arsip tidak sah")
                            principal = sessions.ambil_principal_pendamping(
                                self._ambil_token()
                            )
                            daftar_arsip = assistant_http.fragmen_arsip_akun(
                                principal, halaman=halaman,
                                chat_id=q.get("chat", ""),
                            )
                            arsip = daftar_arsip
                        elif set(q) != {"section"}:
                            raise ValueError("parameter tidak sah")
                    except (ValueError, UnicodeError, LookupError):
                        return self._kirim_privat(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    import product_analytics_http as analitik
                    panel_analitik = ''
                    if section == 'akun' and ident[1] == 'guru' and self._ambil_token():
                        try:
                            panel_analitik = analitik.form_akun(self)
                        except (LookupError, RuntimeError, OSError):
                            panel_analitik = '<p>Analitik opsional belum tersedia.</p>'
                    hasil = halaman_akun(
                        kon,
                        pengguna=ident[0] if ident else None,
                        peran=ident[1] if ident else "guru",
                        section=section,
                        arsip_pendamping=arsip,
                        privat=bool(arsip or panel_analitik),
                        analitik=panel_analitik,
                        langganan_sandbox=subscription_http.runtime(self) is not None,
                        langganan_produksi=subscription_produksi_http.ada(self),
                    )
                    return assistant_http._kirim_host_privat(self, hasil) if arsip or panel_analitik else self._kirim(hasil)
                if jalur.startswith("/lembar/"):
                    bagian = jalur.split("/")
                    sesi_id = int(bagian[2])
                    if not self._bisa_lihat_sesi(kon, sesi_id):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    guru = len(bagian) > 3 and bagian[3] == "penilaian"
                    isi = halaman_lembar(kon, sesi_id, guru)
                    if isi:
                        kon.commit()
                        if not guru:
                            import product_analytics_http as analitik
                            ident = self._identitas()
                            return analitik.kirim_dan_catat(self, isi, sesi_id, 'lembar_soal_disajikan',
                                                           pengguna=ident[0], peran=ident[1])
                        return self._kirim(isi)
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
        nama = (data.get("nama") or "").strip()
        pw = data.get("sandi") or ""
        lanjut = tujuan_lanjut(data.get("lanjut", ""))
        ip = self.client_address[0] if self.client_address else "unknown"
        if not nama or not pw:
            return self._kirim(self._halaman_masuk_stitch("Nama dan sandi wajib diisi.", lanjut=lanjut))
        if sessions.sedang_diblokir(nama, ip):
            return self._kirim(self._halaman_masuk_stitch("Terlalu banyak percobaan. Coba lagi 15 menit lagi.", lanjut=lanjut), 429)
        principal = auth.autentikasi(nama, pw)
        if principal is None:
            sessions.catat_gagal(nama, ip)
            return self._kirim(self._halaman_masuk_stitch("Nama atau sandi belum cocok. Coba lagi, atau minta gurumu.", lanjut=lanjut))
        token = sessions.buat_dari_principal(principal)
        if token is None:
            sessions.catat_gagal(nama, ip)
            return self._kirim(
                self._halaman_masuk_stitch(
                    "Akun berubah saat masuk. Coba lagi.", lanjut=lanjut
                ),
                409,
            )
        sessions.catat_berhasil(principal.pengguna, ip)
        peran = principal.peran
        tujuan = "/murid" if peran == "murid" else (
            "/admin" if peran == "admin" else "/guru"
        )
        if peran == "guru" and lanjut:
            tujuan = lanjut
        self.send_response(303)
        self.send_header("Location", tujuan)
        self.send_header("Set-Cookie", self._set_cookie(token))
        self.send_header("Content-Length", "0")
        self.end_headers()

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

        # pendaftaran mandiri + login + logout — terbuka, tanpa palang
        if jalur == "/daftar":
            import admin_registration
            import admin_store
            import subscription_registration
            from admin_accounts import DomainAkunTidakSah
            from admin_contracts import KontrakTidakSah
            from landing import halaman_daftar as render_daftar
            import learning_profile_ui

            nama_anak = ''
            kelas_sekolah = None
            profil_parameter = ''
            def halaman_daftar(*args, **kwargs):
                return render_daftar(*args, nama_anak=nama_anak, kelas_sekolah=kelas_sekolah,
                                     profil_parameter=profil_parameter, **kwargs)

            try:
                import admin_http
                import admin_security
                data = admin_security.baca_form(self)
                if set(data) - {"nama", "sandi", "setuju", "token_form", "analitik", "sumber_analitik",
                                "nama_anak", "kelas_sekolah", "profil_parameter"} or not {
                    "nama", "sandi"
                } <= set(data):
                    raise ValueError("Isian pendaftaran tidak sah.")
                if data.get('analitik', '0') not in ('0', '1'):
                    raise ValueError('persetujuan analitik tidak sah')
                if data.get('sumber_analitik', 'tidak_diketahui') not in analitik.d.SUMBER:
                    raise ValueError('sumber analitik tidak sah')
                nama = data["nama"].strip()
                sandi = data["sandi"]
                nama_anak = data.get('nama_anak', '').strip()
                kelas_sekolah = learning_profile_ui.baca_kelas_form(data.get('kelas_sekolah', ''))
                profil_parameter = data.get('profil_parameter')
                token_baru = admin_http.buat_token_pendaftaran()
                status_daftar = admin_registration.status(admin_store.BAWAAN)
                if not status_daftar.dibuka:
                    raise PermissionError("Pendaftaran ditutup.")
                if not nama:
                    return self._kirim(halaman_daftar(
                        "Nama wajib diisi.", galat=True, nama=nama,
                        token_form=token_baru,
                    ))
                if len(sandi) < 8:
                    return self._kirim(halaman_daftar(
                        "Kata sandi minimal 8 karakter.", galat=True, nama=nama,
                        token_form=token_baru,
                    ))
                if data.get("setuju") != "1":
                    return self._kirim(halaman_daftar(
                        "Centang persetujuan Kebijakan Privasi dulu, ya.",
                        galat=True, nama=nama, token_form=token_baru,
                    ))
                if sessions.sedang_diblokir(nama, self.client_address[0]):
                    return self._kirim(
                        halaman_daftar(
                            "Terlalu banyak percobaan. Coba lagi 15 menit lagi.",
                            galat=True, nama=nama,
                            token_form=data.get("token_form", token_baru),
                        ),
                        429,
                    )
                tinjauan = admin_http.periksa_token_pendaftaran(
                    data.get("token_form", "")
                )
                akun_baru = subscription_registration.daftar_web(
                    admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN,
                    operasi_id=tinjauan["op"], alias=nama,
                    sandi=sandi, nama_anak=nama_anak, kelas_sekolah=kelas_sekolah,
                    profil_parameter=profil_parameter,
                    token_form=admin_http.token_domain(data["token_form"]),
                    sekarang=int(time.time()),
                ).akun
                analitik.setelah_daftar(
                    auth.PrincipalAkun(akun_baru.pengguna, akun_baru.peran,
                                       akun_baru.id_akun, akun_baru.revisi_auth),
                    setuju=data.get('analitik') == '1' and akun_baru.baru,
                    sumber=data.get('sumber_analitik', 'tidak_diketahui'),
                )
                token = sessions.buat_dari_principal(akun_baru)
                if token is None:
                    return self._kirim(
                        halaman_daftar(
                            "Akun berubah saat pendaftaran. Silakan masuk lagi.",
                            galat=True, nama=nama,
                            token_form=admin_http.buat_token_pendaftaran(),
                        ),
                        409,
                    )
            except admin_registration.RegistrasiBelumSelesai:
                # Token exact mempertahankan saga yang mungkin sudah commit profil.
                # Tidak memasukkan operasi/nama anak ke URL atau menerbitkan sesi.
                return self._kirim(halaman_daftar(
                    'Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.',
                    galat=True, nama=locals().get('nama', ''),
                    token_form=locals().get('data', {}).get('token_form', ''),
                ), 503)
            except admin_store.StoreBelumSiap:
                return self._kirim(
                    halaman_daftar(
                        "Pendaftaran sementara belum tersedia. Akun yang sudah ada tetap bisa masuk.",
                        galat=True, pendaftaran_dibuka=False, belum_tersedia=True,
                    ) if 'tinjauan' not in locals() else halaman_daftar(
                        'Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.',
                        galat=True, nama=locals().get('nama', ''),
                        token_form=data.get('token_form', ''),
                    ),
                    503,
                )
            except PermissionError as galat:
                ditutup = "ditutup" in str(galat)
                return self._kirim(
                    halaman_daftar(
                        "Pendaftaran baru sedang ditutup. Akun yang sudah terdaftar tetap bisa masuk."
                        if ditutup else
                        "Form pendaftaran sudah tidak berlaku. Buka ulang halaman pendaftaran.",
                        galat=True, nama=locals().get("nama", ""),
                        pendaftaran_dibuka=not ditutup,
                        token_form=(
                            "" if ditutup else admin_http.buat_token_pendaftaran()
                        ),
                    ),
                    403,
                )
            except OSError:
                return self._kirim(halaman_daftar(
                    'Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama.',
                    galat=True, nama=locals().get('nama', ''),
                    token_form=locals().get('data', {}).get('token_form', ''),
                ), 503)
            except (ValueError, KontrakTidakSah, DomainAkunTidakSah) as galat:
                teks_galat = str(galat)
                aman = teks_galat
                status = 200
                if "alias tidak tersedia" in teks_galat:
                    aman = "Nama sudah dipakai. Pakai nama lain, atau masuk bila memang akunmu."
                elif aman not in (
                    "Nama wajib diisi.", "Kata sandi minimal 8 karakter.",
                    "Centang persetujuan Kebijakan Privasi dulu, ya.",
                    'Nama panggilan anak wajib diisi, maksimal 40 karakter.',
                    'Pilih kelas sekolah 1–6 atau Kelas belum diisi.',
                    'Pilihan variasi soal tidak sah. Muat ulang formulir pendaftaran.',
                ):
                    aman = "Isian pendaftaran belum dapat digunakan."
                    status = 400
                return self._kirim(
                    halaman_daftar(
                        aman, galat=True,
                        nama=locals().get("nama", ""),
                        token_form=locals().get('data', {}).get('token_form') or admin_http.buat_token_pendaftaran(),
                    ),
                    status,
                )
            tujuan_daftar = (
                f"/anak/{akun_baru.siswa_id}?section=rencana"
                if type(akun_baru.siswa_id) is int and akun_baru.siswa_id > 0
                else "/guru"
            )
            self.send_response(303)
            self.send_header("Location", tujuan_daftar)
            self.send_header("Set-Cookie", self._set_cookie(token))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if jalur == "/masuk":
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            mentah = self.rfile.read(panjang).decode("utf-8") if panjang else ""
            bidang = urllib.parse.parse_qs(mentah, keep_blank_values=True)
            data = {k: v[0] for k, v in bidang.items()}
            if len(bidang.get("lanjut", [])) != 1:
                data.pop("lanjut", None)
            return self._handle_masuk(data)
        if jalur == "/keluar":
            tok = self._ambil_token()
            if tok:
                sessions.hapus(tok)
            self.send_response(303)
            self.send_header("Location", "/masuk")
            self.send_header("Set-Cookie", self._set_cookie(None))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if not self._lolos_sandi():
            return

        if share_http.tangani_guru_post(self, jalur):
            return

        if jalur == "/akun":
            ident = self._identitas()
            pengguna = ident[0] if ident else "guru"
            peran = ident[1] if ident else "guru"
            if peran == "admin":
                # Jalur lama hanya untuk sandi sendiri, bukan bypass layanan admin.
                import admin_security
                try:
                    data = admin_security.baca_form(self)
                    if data.get("aksi") != "sandi" or set(data) - {
                        "aksi", "section", "lama", "baru", "ulang"
                    }:
                        return admin_http.arahkan_admin(self)
                except (ValueError, PermissionError):
                    return self._kirim_privat(b"Form tidak sah.", 400)
            else:
                panjang = int(self.headers.get("Content-Length", 0))
                mentah = self.rfile.read(panjang).decode("utf-8")
                pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
                if any(len(v) != 1 for v in pasangan.values()):
                    return self._kirim(_halaman('Form tidak sah', '<p>Field ganda tidak diizinkan. Muat ulang form.</p>'), 400)
                data = {k: v[0] for k, v in pasangan.items()}
            with database.buka() as kon:
                import learning_profile
                if data.get('aksi') == 'kelas_sekolah':
                    try:
                        sid = int(data.get('siswa_id', ''))
                        if not 0 < sid <= 9_223_372_036_854_775_807:
                            raise ValueError('ID tidak sah')
                        learning_profile.baca(kon, sid, pemilik=pengguna)
                    except (ValueError, TypeError):
                        return self._kirim(_halaman('404', '<h1>Halaman tidak ada</h1>'), 404)
                    if set(data) - {'aksi', 'siswa_id', 'kelas_sekolah', 'revisi_profil', 'section'}:
                        return self._kirim(_halaman('Form tidak sah', '<p>Field profil tidak dikenal. Muat ulang form.</p>'), 400)
                if data.get('aksi') == 'tingkat':
                    return self._kirim(_halaman('Form lama', '<p>Muat ulang form kelas sekolah. Profil parameter lama tidak diubah lewat form ini.</p>'), 409)
                if data.get('aksi') in ('anak_baru', 'siswa'):
                    profil_lama = data.get('profil_parameter', '')
                    if ('tingkat' in data or 'level' in data
                            or profil_lama not in ('', 'P3', 'P4', 'P5', 'P6')):
                        return self._kirim(
                            _halaman(
                                'Form lama',
                                '<p>Form pengaturan soal lama tidak cocok. Muat ulang sebelum menambahkan anak.</p>',
                            ),
                            409,
                        )
                try:
                    pesan, galat = proses_akun(kon, data, pengguna, peran)
                except learning_profile.ProfilTidakDitemukan:
                    return self._kirim(_halaman('404', '<h1>Halaman tidak ada</h1>'), 404)
                section = data.get("section") or PETA_SECTION_AKUN.get(
                    data.get("aksi", ""), "akun"
                )
                return self._kirim(
                    halaman_akun(
                        kon, pesan, galat,
                        pengguna=pengguna, peran=peran, section=section,
                    )
                )

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

        if jalur.startswith("/cerita/"):
            import llm

            try:
                sesi_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            with database.buka() as kon:
                if not self._bisa_lihat_sesi(kon, sesi_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                _, _, catatan = llm.bungkus_sesi(kon, sesi_id, _soal_dari_baris)
                ident = self._identitas()
                return self._kirim(
                    halaman_sesi_stitch(
                        kon, sesi_id, catatan,
                        peran=ident[1] if ident else "guru",
                        pengguna=ident[0] if ident else "",
                    )
                )

        import session_http
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

        if jalur.startswith("/sesi/") and jalur.endswith("/hapus"):
            try:
                sesi_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            with database.buka() as kon:
                if not self._bisa_lihat_sesi(kon, sesi_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            data = urllib.parse.parse_qs(
                self.rfile.read(panjang).decode("utf-8"),
                keep_blank_values=True,
            )
            if (data.get("konfirmasi") or [""])[0] != "1":
                # Tanpa konfirmasi = hanya melihat halaman peringatan lagi.
                # Sesi tidak disentuh sama sekali.
                with database.buka() as kon:
                    ident = self._identitas()
                    isi = halaman_konfirmasi_hapus(
                        kon, sesi_id,
                        pengguna=ident[0] if ident else "",
                        peran=ident[1] if ident else "guru",
                    )
                if isi is None:
                    return self._kirim(
                        _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
                    )
                return self._kirim(isi)
            with database.buka() as kon:
                baris_sesi = kon.execute(
                    "SELECT siswa_id FROM sesi WHERE id = ?", (sesi_id,)
                ).fetchone()
                dilindungi = kon.execute(
                    """SELECT 1 FROM konfirmasi_hasil WHERE sesi_id = ?
                       UNION ALL SELECT 1 FROM bukti_fokus WHERE sesi_id = ?
                       UNION ALL SELECT 1 FROM kejadian_belajar WHERE sesi_id = ?""",
                    (sesi_id, sesi_id, sesi_id),
                ).fetchone()
                if dilindungi:
                    return self._kirim(_halaman(
                        "Histori sesi dilindungi",
                        "<h1>Histori sesi dilindungi</h1>"
                        "<p>Gunakan Batalkan sesi agar bukti belajar tetap tersimpan.</p>",
                    ), 409)
                dihapus = database.hapus_sesi(kon, sesi_id)
            if not dihapus:
                return self._kirim(
                    _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
                )
            # Berkas foto tidak diurus DB — dibuang di sini, SETELAH baris
            # DB benar-benar hilang supaya tidak ada foto yatim sebaliknya.
            lampiran_mod.bersihkan_berkas(sesi_id)
            tujuan = urllib.parse.urlencode({"pesan": f"Sesi {sesi_id} dihapus."})
            self.send_response(303)
            # Kembali ke history anak yang punya sesi itu (baris sudah hilang,
            # jadi siswa_id diselamatkan sebelum hapus). Tanpa baris (kasus
            # langka), fallback ke dashboard.
            tujuan_anak = (
                f"/anak/{baris_sesi['siswa_id']}?{tujuan}" if baris_sesi
                else f"/?{tujuan}"
            )
            self.send_header("Location", tujuan_anak)
            self.end_headers()
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
