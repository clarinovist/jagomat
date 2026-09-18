"""Router HTTP: Penangan(BaseHTTPRequestHandler) + palang peran/kepemilikan.

Stdlib saja, tanpa framework. Alasan tanpa framework: satu-satunya pengguna
adalah guru di jaringan rumah/VPS sendiri, kuerinya sedikit, dan tiap
dependensi tambahan adalah satu hal lagi yang bisa gagal saat deploy.

Halaman-halamannya tinggal di modul sendiri (dipecah 31 Aug 2026):
    teacher_pages.py   dashboard, sesi, konfirmasi hapus, lembar
    reports.py         laporan per anak + diagnosa
    account_pages.py   akun guru & admin
Aturan lama tetap: modul ini tidak boleh mengimpor students di atas file —
impor terlambat di dalam handler (lihat _rute_murid_get).
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
import share_links
import sessions
import design_tokens as T
from assistant_navigation import tujuan_lanjut
from account_pages import (
    PETA_SECTION_AKUN,
    halaman_akun,
    proses_akun,
)
from generator import LEVEL_BAWAAN
from reports import diagnosa_murid, halaman_laporan
from support_pages import halaman_pesan as _halaman
from teacher_pages import (
    halaman_bagikan_sesi,
    _soal_dari_baris,
    _topik_untuk_level,
    _nama_template,
    buat_sesi_seed_baru,
    halaman_konfirmasi_hapus,
    halaman_anak,
    halaman_lembar,
    halaman_sesi_cetak,
    halaman_sesi_lampiran,
    halaman_sesi_stitch,
    halaman_utama_stitch,
    simpan_sesi,
)
from templates import LEVEL, label_kelas
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
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)

    def _kirim_privat(self, isi: bytes, kode: int = 200) -> None:
        """Respons privat; hanya skrip chat berhash boleh mengakses origin sendiri."""
        import assistant_browser
        isi, izin_chat = assistant_browser.lengkapi_respons(isi)
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
            + izin_chat + "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
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

    def _kirim_berkas_lampiran(self, kon, lampiran_id: int) -> None:
        """Kirim isi berkas foto lampiran (hanya guru, hanya milik sesi)."""
        lamp = database.ambil_lampiran(kon, lampiran_id)
        if not lamp or not self._bisa_lihat_sesi(kon, int(lamp["sesi_id"])):
            return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
        berkas = (
            lampiran_mod.direktori_lampiran()
            / str(lamp["sesi_id"])
            / lamp["nama_berkas"]
        )
        try:
            isi = berkas.read_bytes()
        except OSError:
            return self._kirim(_halaman("404", "<h1>Berkas hilang</h1>"), 404)
        self.send_response(200)
        self.send_header("Content-Type", lamp["mime"])
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        self.wfile.write(isi)

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

    def _rute_tautan_get(self, token: str) -> None:
        """Buka tepat satu lembar dari capability bearer tanpa membuat login."""
        import student_pages

        tidak_ada = _halaman("404", "<h1>Halaman tidak ada</h1>")
        with database.buka() as kon:
            akses = share_links.ambil(kon, token)
            if not akses:
                return self._kirim_tautan(tidak_ada, 404)
            isi = student_pages.halaman_kerja_baru(
                kon,
                int(akses["siswa_id"]),
                int(akses["sesi_id"]),
                jalur_aksi=f"/mulai/{token}",
                akses_tautan=True,
            )
        if isi is None:
            return self._kirim_tautan(tidak_ada, 404)
        return self._kirim_tautan(isi)

    def _rute_tautan_post(self, token: str) -> None:
        """Simpan jawaban hanya ke sesi yang ditunjuk token aktif."""
        import students

        tidak_ada = _halaman("404", "<h1>Halaman tidak ada</h1>")
        panjang = int(self.headers.get("Content-Length", 0) or 0)
        if panjang > 1_000_000:
            # Jalur bearer tanpa login paling rawan dikirimi body raksasa —
            # tolak sebelum membaca, jangan memakan memori per koneksi.
            return self._kirim_tautan(_halaman(
                "Terlalu besar",
                "<h1>Isian terlalu besar</h1><p>Coba muat ulang halaman.</p>",
            ), 413)
        mentah = self.rfile.read(panjang).decode("utf-8")
        pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
        if any(len(v) != 1 for v in pasangan.values()):
            return self._kirim_tautan(_halaman("Isian tidak sah", "<h1>Isian ganda tidak diizinkan</h1>"), 400)
        data = {k: v[0] for k, v in pasangan.items()}
        with database.buka() as kon:
            # Kunci tulis mencegah pencabutan menang/kalah di antara validasi
            # dan penyimpanan jawaban pada dua permintaan yang bersamaan.
            kon.execute("BEGIN IMMEDIATE")
            akses = share_links.ambil(kon, token)
            if not akses:
                return self._kirim_tautan(tidak_ada, 404)
            siswa_id = int(akses["siswa_id"])
            sesi_id = int(akses["sesi_id"])
            if data.get("aksi") == "mulai":
                database.tandai_mulai(kon, sesi_id)
                kon.commit()
                # Respons capability tetap memakai semua header anti-bocor.
                return self._kirim_tautan(
                    json.dumps({"mulai": True}).encode("utf-8")
                )
            import student_submissions as kiriman
            aksi = data.get("aksi", "simpan")
            if aksi not in ("simpan", "selesai", "kirim_latihan", "kembali"):
                aksi = "simpan"
            try:
                kiriman.validasi_versi(kon, sesi_id, data)
                if aksi in ("kirim_latihan", "kembali"):
                    kiriman.simpan_refleksi(kon, sesi_id, data)
                    hasil = 0
                else:
                    hasil = students.simpan_jawaban_murid(kon, siswa_id, sesi_id, data)
            except ValueError as galat:
                kon.rollback()
                return self._kirim_tautan(_halaman("Belum tersimpan", f"<h1>Belum tersimpan</h1><p>{html.escape(str(galat))}</p>"), getattr(galat, "status", 400))
            if hasil is None:
                return self._kirim_tautan(tidak_ada, 404)
            info_sesi = students.sesi_murid(kon, siswa_id, sesi_id)
            if aksi == "selesai" and kiriman.perlu_refleksi(kon, info_sesi, data):
                from submission_pages import halaman_refleksi
                isi = halaman_refleksi(kon, siswa_id, sesi_id, f"/mulai/{token}")
                kon.commit()
                return self._kirim_tautan(isi)
            if hasil:
                database.tandai_mulai(kon, sesi_id)
            selesai = aksi in ("selesai", "kirim_latihan")
            if selesai:
                kiriman.arsipkan(kon, sesi_id, "tautan")
                diagnosa_murid(kon, sesi_id)
                database.tandai_mulai(kon, sesi_id)
                database.tandai_selesai(kon, sesi_id)
                # Commit sebelum respons — alasan sama dengan rute bagikan:
                # GET /mulai/<token> berikutnya harus melihat selesai.
                isi = _halaman(
                    "Jawaban tersimpan",
                    "<h1>Hebat, selesai!</h1>"
                    "<p>Semua jawabanmu sudah masuk. Gurumu akan memeriksanya.</p>",
                )
            else:
                import student_pages

                isi = student_pages.halaman_kerja_baru(
                    kon, siswa_id, sesi_id, hasil,
                    jalur_aksi=f"/mulai/{token}", akses_tautan=True,
                )
                if isi is None:
                    return self._kirim_tautan(tidak_ada, 404)
            # Jawaban (dan stamp mulai/selesai) ter-commit sebelum respons:
            # refresh anak tepat setelah simpan membaca DB yang sudah final.
            kon.commit()
        return self._kirim_tautan(isi)

    def _rute_get(self) -> None:
        jalur = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
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
        if jalur.startswith("/mulai/"):
            token = jalur[len("/mulai/"):]
            return self._rute_tautan_get(token)
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

                return self._kirim(halaman_landing())
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
                return self._kirim(halaman_utama_stitch(
                    kon, pesan=pesan, pemilik=ident[0], peran=ident[1], sorot=sorot,
                ))
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
            return self._kirim(halaman_daftar(
                pendaftaran_dibuka=status.dibuka,
                token_form=token_form,
            ))
        if jalur == "/kebijakan-privasi":
            # Publik: tujuan checkbox persetujuan di /daftar & form anak,
            # dan footer landing. Statis, tanpa membaca basis data.
            from landing import halaman_kebijakan

            return self._kirim(halaman_kebijakan())
        if jalur == "/lupa-sandi":
            # Publik, dari tautan di /masuk. Aplikasi sengaja tidak
            # menyimpan email, jadi ini halaman panduan ("mintalah sandi
            # baru ke X"), bukan reset mandiri — mengarang alur email
            # berarti mengarang kanal yang tidak ada.
            from landing import halaman_lupa_sandi

            return self._kirim(halaman_lupa_sandi())
        if jalur == "/aset" or jalur.startswith("/aset/"):
            # Publik & sengaja sempit: hanya berkas brand statis dari
            # allow-list brand.ASET. Favicon dibutuhkan browser sebelum
            # login, jadi rute ini WAJIB berada sebelum palang guru.
            # Tidak menyentuh basis data.
            # Jalur sudah di-rstrip("/"), jadi "/aset/" tiba sebagai "/aset"
            # dengan nama kosong — tetap 404 lewat allow-list.
            return self._kirim_aset(jalur[len("/aset/"):] if len(jalur) > 5 else "")
        if jalur == "/murid" or jalur.startswith("/murid/"):
            try:
                with database.buka() as kon:
                    return self._rute_murid_get(kon, jalur, self.path)
            except (ValueError, IndexError):
                pass
            self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
            return
        if not self._lolos_sandi():
            return
        try:
            with database.buka() as kon:
                if jalur.startswith("/lampiran/berkas/"):
                    return self._kirim_berkas_lampiran(
                        kon, int(jalur.rsplit("/", 1)[1])
                    )
                if jalur.startswith("/lampiran/"):
                    lampiran_id = int(jalur.split("/")[2])
                    if not self._bisa_lihat_lampiran(kon, lampiran_id):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    isi = lampiran_mod.halaman_konfirmasi(kon, lampiran_id)
                    if isi:
                        return self._kirim(isi)
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
                if jalur.startswith("/sesi/") and jalur.endswith("/cetak"):
                    try:
                        sesi_id = int(jalur.split("/")[2])
                    except (ValueError, IndexError):
                        return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
                    if not self._bisa_lihat_sesi(kon, sesi_id):
                        return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
                    ident = self._identitas()
                    isi = halaman_sesi_cetak(
                        kon, sesi_id,
                        peran=ident[1] if ident else "guru",
                        pengguna=ident[0] if ident else "",
                    )
                    if isi is None:
                        return self._kirim(_halaman("404", "<h1>Sesi tidak ada</h1>"), 404)
                    return self._kirim(isi)
                if jalur.startswith("/sesi/") and jalur.endswith("/lampiran"):
                    try:
                        sesi_id = int(jalur.split("/")[2])
                    except (ValueError, IndexError):
                        return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
                    if not self._bisa_lihat_sesi(kon, sesi_id):
                        return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
                    ident = self._identitas()
                    isi = halaman_sesi_lampiran(
                        kon, sesi_id,
                        peran=ident[1] if ident else "guru",
                        pengguna=ident[0] if ident else "",
                    )
                    if isi is None:
                        return self._kirim(_halaman("404", "<h1>Sesi tidak ada</h1>"), 404)
                    return self._kirim(isi)
                if jalur.startswith("/sesi/"):
                    sesi_id = int(jalur.split("/")[2])
                    if not self._bisa_lihat_sesi(kon, sesi_id):
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
                                "sesi", sesi_id, pasangan,
                            )
                            principal = sessions.ambil_principal_pendamping(
                                self._ambil_token()
                            )
                            status_inline = kon.execute(
                                "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)
                            ).fetchone()
                            fragmen_inline = assistant_http.fragmen_inline(
                                principal, target_inline,
                                dalam_form=bool(
                                    status_inline and status_inline["selesai"]
                                    and target_inline.posisi == "soal"
                                ),
                            )
                    except (ValueError, LookupError):
                        return self._kirim_privat(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    # Validasi bantuan selesai sebelum stamp direview.
                    # Guru membuka sesi yang SUDAH DIKIRIM = momen review.
                    # Pratinjau sebelum pengumpulan tidak pernah menandai review.
                    if ident and ident[1] == "guru":
                        siap = kon.execute(
                            """SELECT 1 FROM sesi
                               WHERE id = ? AND direview IS NULL
                                 AND selesai IS NOT NULL""",
                            (sesi_id,),
                        ).fetchone()
                        if siap:
                            kon.execute(
                                "UPDATE sesi SET direview = "
                                "datetime('now', '+7 hours') WHERE id = ?",
                                (sesi_id,),
                            )
                            kon.commit()
                    # Redirect simpan memakai pesan tetap. Query bebas/ganda
                    # tidak boleh menjadi isi banner atau mengklaim konfirmasi.
                    pesan_tinjauan = (
                        'Tinjauan tersimpan. Konfirmasi hasil tetap merupakan langkah terpisah.'
                        if [nilai for kunci, nilai in pasangan if kunci == 'pesan'] == ['Tinjauan tersimpan']
                        else ''
                    )
                    hasil = halaman_sesi_stitch(
                        kon, sesi_id, pesan=pesan_tinjauan,
                        peran=ident[1] if ident else "guru",
                        pengguna=ident[0] if ident else "",
                        bantuan=fragmen_inline,
                        bantuan_nomor=(target_inline.nomor if target_inline else None),
                    )
                    return self._kirim_privat(hasil) if target_inline else self._kirim(hasil)
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
                    hasil = halaman_akun(
                        kon,
                        pengguna=ident[0] if ident else None,
                        peran=ident[1] if ident else "guru",
                        section=section,
                        arsip_pendamping=arsip,
                        privat=bool(arsip),
                    )
                    return assistant_http._kirim_host_privat(self, hasil) if arsip else self._kirim(hasil)
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
                        return self._kirim(isi)
        except (ValueError, IndexError):
            pass
        self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)

    def _rute_murid_get(self, kon, jalur: str, jalur_penuh: str = "") -> None:
        """Rute /murid — hanya akun berperan murid.

        Guru sengaja TIDAK bisa membuka halaman murid: halamannya memuat
        form jawaban atas nama anak, dan guru mengerjakan lewat rutenya
        sendiri. GET tanpa identitas murid (kuki hilang, kedaluwarsa, atau
        ditimpa akun lain di perangkat bersama) -> 303 ke /masuk dengan
        pesan yang jelas — anak dibawa ke pintu yang benar, bukan halaman
        401 polos yang terlihat seperti situs rusak saat muat-ulang. POST
        kirim jawaban tetap 401 di do_POST supaya palang tulis tidak
        melemah.
        """
        import student_pages
        import students

        kredensial = self._sesi_atau_basic(peran_wajib="murid")
        if not kredensial:
            qs = urllib.parse.urlencode({
                "galat": "Sesi kamu sudah habis atau akun lain masuk di "
                         "perangkat ini. Masuk lagi dengan nama & sandimu, ya.",
            })
            self.send_response(303)
            self.send_header("Location", f"/masuk?{qs}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        siswa_id = students.siswa_dari_akun(kon, kredensial[0])
        if siswa_id is None:
            nama = html.escape(kredensial[0])
            return self._kirim(
                _halaman(
                    "Belum terhubung",
                    f"<h1>Halo, {nama}</h1>"
                    "<p>Akunmu belum dihubungkan ke daftar siswa. "
                    "Minta gurumu menyiapkannya.</p>",
                )
            )
        if jalur == "/murid":
            # ?selesai=<id> dari pengalihan setelah semua soal terkirim:
            # hanya memicu banner perayaan di daftar, tidak menyentuh data.
            sesi_selesai = None
            if jalur_penuh:
                q = urllib.parse.parse_qs(
                    urllib.parse.urlparse(jalur_penuh).query
                )
                try:
                    sesi_selesai = int(q.get("selesai", ["0"])[0]) or None
                except (ValueError, TypeError):
                    sesi_selesai = None
            return self._kirim(
                student_pages.halaman_daftar_sesi_baru(
                    kon, siswa_id, kredensial[0], sesi_selesai
                )
            )
        bagian = jalur.split("/")
        # /murid/hasil/<id> — hasil + pembahasan, hanya sesi yang SUDAH
        # direview guru. Gerbangnya di students.hasil_murid (None = belum
        # direview / bukan miliknya) dan dijawab 404: anak tidak boleh bisa
        # membedakan "belum dinilai" dari "sesi orang lain" lewat kode HTTP.
        if len(bagian) >= 4 and bagian[2] == "hasil":
            try:
                sesi_id_hasil = int(bagian[3])
            except ValueError:
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            isi = student_pages.halaman_hasil_murid(
                kon, siswa_id, sesi_id_hasil
            )
            if isi is None:
                return self._kirim(
                    _halaman(
                        "Belum ada hasil",
                        "<h1>Belum ada hasil</h1><p>Sesi ini belum selesai "
                        "diperiksa gurumu. Coba lagi nanti, ya.</p>"
                        '<p><a href="/murid">Kembali ke daftar sesi</a></p>',
                    ),
                    404,
                )
            return self._kirim(isi)
        # /murid/kerjakan/<id>
        if len(bagian) >= 3 and bagian[2] == "kerjakan":
            # Jumlah tersimpan datang dari pengalihan setelah POST. Nilainya
            # dari URL, jadi tidak dipercaya: dibatasi ke bilangan bulat wajar
            # dan hanya dipakai untuk kalimat konfirmasi, tidak menyentuh data.
            tersimpan = 0
            if jalur_penuh:
                q = urllib.parse.parse_qs(
                    urllib.parse.urlparse(jalur_penuh).query
                )
                try:
                    tersimpan = max(0, min(99, int(q.get("tersimpan", ["0"])[0])))
                except (ValueError, TypeError):
                    tersimpan = 0
            sesi_id_kerja = int(bagian[3])
            # Kabar hasil kirim foto (?foto=ok / ?foto=<alasan gagal>).
            # Sama seperti `tersimpan`: datang dari URL, jadi tidak
            # dipercaya — hanya dipakai sebagai kalimat, dan dipangkas.
            kabar_foto = ""
            if jalur_penuh:
                q_foto = urllib.parse.parse_qs(
                    urllib.parse.urlparse(jalur_penuh).query
                )
                kabar_foto = (q_foto.get("foto", [""])[0] or "")[:200]
            # Waktu pengerjaan mulai dihitung dari saat lembar DIBUKA, bukan
            # dari simpan pertama: anak yang mengisi semuanya lalu sekali
            # simpan tidak boleh tercatat berdurasi 0 detik. Idempoten —
            # buka ulang tidak menggeser waktu yang sudah tercatat. Commit
            # sendiri sebelum respons: stamp mandiri, dan commit konteks
            # buka() baru terjadi setelah respons pergi (lihat /sesi/).
            if students.sesi_murid(kon, siswa_id, sesi_id_kerja):
                database.tandai_mulai(kon, sesi_id_kerja)
                kon.commit()
            isi = student_pages.halaman_kerja_baru(
                kon, siswa_id, sesi_id_kerja, tersimpan,
                kabar_foto=kabar_foto,
            )
            if isi is None:
                return self._kirim(
                    _halaman("404", "<h1>Sesi tidak ada</h1>"), 404
                )
            return self._kirim(isi)
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
        import admin_http
        import ai_http
        import assistant_http

        if admin_http.tangani_post(self, jalur):
            return
        if ai_http.tangani_post(self, jalur):
            return
        if jalur == "/admin" or jalur.startswith("/admin/"):
            return admin_http.tidak_ada(self)
        if assistant_http.tangani_inline_post(self, jalur):
            return
        if assistant_http.tangani_post(self, jalur):
            return
        if jalur.startswith("/mulai/"):
            token = jalur[len("/mulai/"):]
            return self._rute_tautan_post(token)

        if jalur.startswith("/murid/kerjakan/"):
            import students

            kredensial = self._sesi_atau_basic(peran_wajib="murid")
            if not kredensial:
                return self._kirim(
                    _halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401
                )
            panjang = int(self.headers.get("Content-Length", 0))
            if panjang < 0 or panjang > 1_000_000:
                return self._kirim(_halaman('Isian terlalu besar', '<h1>Isian terlalu besar</h1>'), 413)
            mentah = self.rfile.read(panjang).decode("utf-8")
            pasangan = urllib.parse.parse_qs(mentah, keep_blank_values=True)
            if any(len(v) != 1 for v in pasangan.values()):
                return self._kirim(_halaman("Isian tidak sah", "<h1>Isian ganda tidak diizinkan</h1>"), 400)
            data = {k: v[0] for k, v in pasangan.items()}
            sesi_id = int(jalur.split("/")[3])
            aksi = data.get("aksi", "simpan")
            if aksi not in ("simpan", "selesai", "kirim_latihan", "kembali"):
                aksi = "simpan"
            with database.buka() as kon:
                # Kunci pemeriksaan+penyimpanan agar POST simpan dan final
                # yang bersamaan tidak melewati gerbang selesai.
                kon.execute("BEGIN IMMEDIATE")
                siswa_id = students.siswa_dari_akun(kon, kredensial[0])
                info_sesi = (
                    students.sesi_murid(kon, siswa_id, sesi_id)
                    if siswa_id is not None
                    else None
                )
                if not info_sesi or info_sesi.get("dibatalkan"):
                    return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
                if info_sesi.get("selesai"):
                    return self._kirim(
                        _halaman(
                            "Sudah dikirim",
                            "<h1>Jawaban sudah dikirim</h1>"
                            "<p>Sesi ini tidak dapat diubah lagi.</p>",
                        ),
                        409,
                    )
                import student_submissions as kiriman
                try:
                    kiriman.validasi_versi(kon, sesi_id, data)
                    if aksi in ("kirim_latihan", "kembali"):
                        kiriman.simpan_refleksi(kon, sesi_id, data)
                        hasil = 0
                    else:
                        hasil = students.simpan_jawaban_murid(kon, siswa_id, sesi_id, data)
                except ValueError as galat:
                    kon.rollback()
                    return self._kirim(_halaman("Belum tersimpan", f"<h1>Belum tersimpan</h1><p>{html.escape(str(galat))}</p>"), getattr(galat, "status", 400))
                if aksi == "selesai" and kiriman.perlu_refleksi(kon, info_sesi, data):
                    from submission_pages import halaman_refleksi
                    isi = halaman_refleksi(kon, siswa_id, sesi_id, f"/murid/kerjakan/{sesi_id}")
                    kon.commit()
                    return self._kirim_privat(isi)
                # Diagnosis otomatis: jawaban baru dari HP langsung dinilai
                # mesin (usulan). Keputusan manual guru tidak pernah
                # ditimpa — lihat web.diagnosa_murid. Guru membuka halaman
                # sesi dan membaca hasil, bukan menekan tombol dulu.
                selesai = aksi in ("selesai", "kirim_latihan")
                if hasil:
                    # Waktu mulai sudah dicatat saat lembar dibuka. POST tetap
                    # idempoten untuk klien lama yang langsung mengirim tanpa GET.
                    database.tandai_mulai(kon, sesi_id)
                # Diagnosis baru menjadi data laporan saat anak mengumpulkan.
                # Draft boleh berubah atau dikosongkan tanpa meninggalkan nilai
                # sementara di dashboard orang tua.
                if selesai:
                    kiriman.arsipkan(kon, sesi_id, "akun")
                    diagnosa_murid(kon, sesi_id)
                    database.tandai_mulai(kon, sesi_id)
                    database.tandai_selesai(kon, sesi_id)
            if hasil is None:
                return self._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
            if selesai:
                # Langsung kembali ke daftar sesi — banner ?selesai= sudah
                # mengonfirmasi. Halaman perayaan terpisah berarti satu
                # klik ekstra plus pilihan "Keluar" yang membingungkan;
                # tombol Keluar memang sudah ada di daftar sesi.
                self.send_response(303)
                self.send_header("Location", f"/murid?selesai={sesi_id}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            # Balik ke lembar kerja yang sama lewat 303 + parameter jumlah,
            # bukan menampilkan halaman langsung: pengalihan mencegah
            # pengiriman ganda kalau anak menekan muat-ulang.
            self.send_response(303)
            self.send_header(
                "Location", f"/murid/kerjakan/{sesi_id}?tersimpan={hasil}"
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # pendaftaran mandiri + login + logout — terbuka, tanpa palang
        if jalur == "/daftar":
            import admin_registration
            import admin_store
            from admin_accounts import DomainAkunTidakSah
            from admin_contracts import KontrakTidakSah
            from landing import halaman_daftar

            try:
                import admin_http
                import admin_security
                data = admin_security.baca_form(self)
                if set(data) - {"nama", "sandi", "setuju", "token_form"} or not {
                    "nama", "sandi"
                } <= set(data):
                    raise ValueError("Isian pendaftaran tidak sah.")
                nama = data["nama"].strip()
                sandi = data["sandi"]
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
                akun_baru = admin_registration.daftar_publik(
                    admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN,
                    operasi_id=tinjauan["op"], alias=nama,
                    sandi=sandi,
                    token_form=admin_http.token_domain(data["token_form"]),
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
            except admin_store.StoreBelumSiap:
                return self._kirim(
                    halaman_daftar(
                        "Pendaftaran sementara belum tersedia. Akun yang sudah ada tetap bisa masuk.",
                        galat=True, pendaftaran_dibuka=False, belum_tersedia=True,
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
            except (ValueError, KontrakTidakSah, DomainAkunTidakSah) as galat:
                teks_galat = str(galat)
                aman = teks_galat
                status = 200
                if "alias tidak tersedia" in teks_galat:
                    aman = "Nama sudah dipakai. Pakai nama lain, atau masuk bila memang akunmu."
                elif aman not in (
                    "Nama wajib diisi.", "Kata sandi minimal 8 karakter.",
                    "Centang persetujuan Kebijakan Privasi dulu, ya.",
                ):
                    aman = "Isian pendaftaran belum dapat digunakan."
                    status = 400
                return self._kirim(
                    halaman_daftar(
                        aman, galat=True,
                        nama=locals().get("nama", ""),
                        token_form=admin_http.buat_token_pendaftaran(),
                    ),
                    status,
                )
            self.send_response(303)
            self.send_header("Location", "/guru")
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

        if jalur.startswith("/murid/foto/"):
            # Anak mengirim FOTO lembar yang dikerjakan di kertas (poin 1 & 4
            # feedback Filia). Palang sama ketat dengan POST jawaban: wajib
            # akun berperan murid, dan sesi wajib milik anak itu sendiri.
            # Yang tersimpan hanya lampiran berstatus 'baru' — guru tetap
            # yang menerapkan, jadi tidak ada jalur anak menulis laporan.
            import students

            kredensial = self._sesi_atau_basic(peran_wajib="murid")
            if not kredensial:
                return self._kirim(
                    _halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401
                )
            try:
                sesi_id = int(jalur.split("/")[3])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)

            content_type = self.headers.get("Content-Type", "")
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            if panjang > lampiran_mod.BATAS_UKURAN * 2:
                return self._kirim(
                    _halaman("Terlalu besar", "<h1>Fotonya terlalu besar</h1>"),
                    400,
                )
            tubuh = self.rfile.read(panjang)
            with database.buka() as kon:
                siswa_id = students.siswa_dari_akun(kon, kredensial[0])
                if siswa_id is None or not students.sesi_murid(
                    kon, siswa_id, sesi_id
                ):
                    # Satu body 404 yang sama untuk "tidak ada" dan "bukan
                    # milikmu" — beda body jadi oracle eksistensi.
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                _lid, pesan = lampiran_mod.proses_upload_murid(
                    kon, sesi_id, content_type, tubuh
                )
            # PRG: refresh tidak mengunggah dua kali. Pesan (sukses ATAU
            # alasan gagal) dibawa di query dan ditampilkan di blok foto —
            # anak harus tahu fotonya masuk atau tidak.
            qs = urllib.parse.urlencode({"foto": pesan})
            self.send_response(303)
            self.send_header("Location", f"/murid/kerjakan/{sesi_id}?{qs}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if not self._lolos_sandi():
            return

        if (
            jalur.startswith("/sesi/")
            and (jalur.endswith("/bagikan") or jalur.endswith("/cabut-tautan"))
        ):
            try:
                sesi_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
            ident = self._identitas()
            with database.buka() as kon:
                if not ident or not self._bisa_lihat_sesi(kon, sesi_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                info = kon.execute(
                    """SELECT s.siswa_id, w.nama FROM sesi s
                       JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
                    (sesi_id,),
                ).fetchone()
                if not info:
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                if jalur.endswith("/bagikan"):
                    # Kunci status sampai token tersimpan: pembatalan/submit
                    # bersamaan tidak boleh menyelinap setelah pemeriksaan.
                    kon.execute("BEGIN IMMEDIATE")
                    status = kon.execute(
                        "SELECT selesai, dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
                    ).fetchone()
                    if status is None:
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    if status["dibatalkan"] is not None:
                        return self._kirim_tautan(_halaman(
                            "Sesi dibatalkan",
                            "<h1>Sesi dibatalkan</h1>"
                            "<p>Tautan sesi tidak dapat dibuat. Riwayat tetap tersimpan; "
                            "kembali ke profil anak untuk melihat rencana berikutnya.</p>",
                        ), 409)
                    if status["selesai"]:
                        # Tautan baru langsung mati karena gerbang ambil
                        # mensyaratkan selesai IS NULL — menolak dengan
                        # penjelasan lebih jujur daripada menyerahkan link
                        # yang tak pernah bisa dipakai.
                        return self._kirim_tautan(_halaman(
                            "Sesi sudah selesai",
                            f"<h1>Sesi #{sesi_id} sudah selesai dikerjakan</h1>"
                            "<p>Tautan berbagi hanya untuk sesi yang belum "
                            "selesai. Anak bisa melihat hasilnya lewat "
                            "akun latihannya setelah kamu review.</p>",
                        ), 400)
                    token = share_links.buat(kon, sesi_id)
                    # Commit SEBELUM respons: bila commit menunggu keluar
                    # dari with buka(), respons sudah pergi lebih dulu dan
                    # guru yang menekan tautannya seketika membaca DB tanpa
                    # baris token — 404 untuk link yang baru saja dibagikan.
                    kon.commit()
                    tautan = f"{brand.URL_SITUS}/mulai/{token}"
                    if self.headers.get("X-Requested-With") == "fetch":
                        return self._kirim_json({"tautan": tautan})
                    # Fallback tanpa JavaScript: respons sederhana tetap
                    # memungkinkan tautan dipilih dan disalin manual.
                    isi = halaman_bagikan_sesi(
                        sesi_id, info["siswa_id"], tautan, ident[0], ident[1],
                    )
                    return self._kirim_tautan(isi)
                share_links.cabut(kon, sesi_id)
                qs = urllib.parse.urlencode({
                    "pesan": f"Tautan sesi dicabut — sesi #{sesi_id} tidak bisa lagi dibuka dari link lama.",
                    "sorot": sesi_id,
                })
                tujuan = f"/anak/{info['siswa_id']}?{qs}"
            self.send_response(303)
            self.send_header("Location", tujuan)
            self.send_header("Content-Length", "0")
            self.end_headers()
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
                data = {
                    k: v[0]
                    for k, v in urllib.parse.parse_qs(
                        mentah, keep_blank_values=True
                    ).items()
                }
            with database.buka() as kon:
                pesan, galat = proses_akun(kon, data, pengguna, peran)
                section = data.get("section") or PETA_SECTION_AKUN.get(
                    data.get("aksi", ""), "akun"
                )
                return self._kirim(
                    halaman_akun(
                        kon, pesan, galat,
                        pengguna=pengguna, peran=peran, section=section,
                    )
                )

        if jalur.startswith("/sesi/") and jalur.endswith("/latihan-serupa"):
            bagian = jalur.split("/")
            if len(bagian) != 4 or bagian[1] != "sesi" or bagian[3] != "latihan-serupa":
                return self._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
            try:
                sesi_id = int(bagian[2])
                if not 0 < sesi_id <= 9_223_372_036_854_775_807:
                    raise ValueError("ID sesi di luar rentang")
            except ValueError:
                return self._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
            # Jangan menahan lock writer saat menunggu body dari jaringan.
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            data = urllib.parse.parse_qs(
                self.rfile.read(panjang).decode("utf-8"),
                keep_blank_values=True,
            )
            ident = self._identitas()
            with database.buka() as kon:
                # Kepemilikan dan syarat sumber tetap terkunci sampai sesi tersimpan.
                kon.execute("BEGIN IMMEDIATE")
                ada = kon.execute(
                    "SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)
                ).fetchone()
                if not ident or ada is None or not self._bisa_lihat_sesi(kon, sesi_id):
                    kon.rollback()
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                if set(data) != {"sesi_soal_id"} or len(data["sesi_soal_id"]) != 1:
                    kon.rollback()
                    return self._kirim(
                        _halaman(
                            "Permintaan belum dapat diproses",
                            "<h1>Permintaan belum dapat diproses</h1>"
                            "<p>Referensi soal tidak dikenal.</p>",
                        ),
                        400,
                    )
                try:
                    sesi_soal_id = int(data["sesi_soal_id"][0])
                    if not 0 < sesi_soal_id <= 9_223_372_036_854_775_807:
                        raise ValueError("ID butir di luar rentang")
                except ValueError:
                    sesi_soal_id = -1
                import similar_practice

                try:
                    sesi_baru = similar_practice.buat_dari_hasil_t(
                        kon,
                        sesi_id,
                        sesi_soal_id,
                        seed=random.randint(1, 9_999_999),
                    )
                except (ValueError, RuntimeError):
                    kon.rollback()
                    return self._kirim(
                        _halaman(
                            "Latihan belum dapat dibuat",
                            "<h1>Latihan belum dapat dibuat</h1>"
                            "<p>Hasil ini tidak lagi memenuhi syarat atau variasi "
                            "soalnya belum cukup. Muat ulang hasil lalu coba lagi.</p>",
                        ),
                        409,
                    )
            self.send_response(303)
            self.send_header("Location", f"/sesi/{sesi_baru}?pesan=" + urllib.parse.quote(
                "5 soal serupa dibuat. Latihan manual ini tidak mengubah progres rencana terpandu."
            ))
            self.send_header("Content-Length", "0")
            self.end_headers()
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

        if jalur.startswith("/sesi-gabungan/"):
            # Latihan lintas BEBERAPA topik pilihan guru (poin 4 tahap 2).
            try:
                siswa_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            data = urllib.parse.parse_qs(
                self.rfile.read(panjang).decode("utf-8"),
                keep_blank_values=True,
            )
            # Checkbox bernama sama -> parse_qs mengembalikan LIST.
            dipilih = [t.strip() for t in data.get("topik", []) if t.strip()]
            sah = set(daftar_topik())
            asing = [t for t in dipilih if t not in sah]
            if asing:
                # Pilihan asing = salah ketik/manipulasi: ditolak jelas,
                # bukan dilewati diam-diam (kontrak sama dengan /sesi-baru).
                return self._kirim(
                    _halaman(
                        "Topik tidak dikenal",
                        "<h1>Topik tidak dikenal</h1><p>"
                        + ", ".join(html.escape(t) for t in asing)
                        + " tidak terdaftar.</p>",
                    ),
                    400,
                )
            try:
                jumlah = int((data.get("jumlah_soal") or ["10"])[0] or 10)
            except ValueError:
                jumlah = 10
            if not 1 <= jumlah <= 50:
                jumlah = 10

            if len(dipilih) < 2:
                qs = urllib.parse.urlencode({
                    "pesan": "Pilih minimal DUA topik untuk latihan gabungan. "
                             "Kalau hanya satu, pakai form buat sesi biasa.",
                })
                self.send_response(303)
                self.send_header("Location", f"/anak/{siswa_id}?{qs}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            with database.buka() as kon:
                if not self._bisa_lihat_siswa(kon, siswa_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                baris = kon.execute(
                    "SELECT nama, tingkat FROM siswa WHERE id = ?", (siswa_id,)
                ).fetchone()
                nama_siswa = baris["nama"] if baris else ""
                # Gabungan baru default cepat; pilihan diagnostik tetap eksplisit.
                # Jangan memilih nilai pertama ketika form mengirim mode ganda.
                mode_dikirim = data.get("mode", ["drill"])
                if len(mode_dikirim) != 1 or mode_dikirim[0] not in ("drill", "diagnostik"):
                    return self._kirim(
                        _halaman(
                            "Mode tidak dikenal",
                            "<h1>Mode tidak dikenal</h1>"
                            "<p>Pilih satu mode: Latihan Cepat atau Diagnostik.</p>",
                        ), 400,
                    )
                try:
                    from choice_pages import format_dari_form
                    sesi_id = database.buat_sesi_gabungan(
                        kon, siswa_id, seed=random.randint(1, 9_999_999), topik_ids=dipilih,
                        level=(baris['tingkat'] if baris else LEVEL_BAWAAN),
                        mode=mode_dikirim[0], jumlah_soal=jumlah,
                        format_jawaban=format_dari_form(data),
                    )
                except ValueError as galat:
                    return self._kirim(_halaman('Latihan belum dibuat', '<p>' + html.escape(str(galat)) + '</p>'), 400)
            qs = urllib.parse.urlencode({
                "pesan": f"Latihan gabungan untuk {nama_siswa} dibuat — "
                         f"sesi #{sesi_id}, {jumlah} soal dari "
                         f"{len(dipilih)} topik.",
                "sorot": sesi_id,
            })
            self.send_response(303)
            self.send_header("Location", f"/anak/{siswa_id}?{qs}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if jalur.startswith("/sesi-remedial/"):
            # Latihan ulang (poin a feedback Filia): sesi berisi HANYA
            # konsep yang pernah dijawab salah anak ini, dengan soal baru.
            try:
                siswa_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            data = urllib.parse.parse_qs(
                self.rfile.read(panjang).decode("utf-8"),
                keep_blank_values=True,
            )
            jumlah_valid = True
            try:
                jumlah = int((data.get("jumlah_soal") or ["10"])[0] or 10)
            except ValueError:
                jumlah = 0
                jumlah_valid = False
            if not 1 <= jumlah <= 50:
                jumlah_valid = False

            template_ids = [nilai for nilai in data.get("template_id", []) if nilai]
            sumber_mentah = (data.get("sumber_sesi_id") or [""])[0]
            try:
                sumber_sesi_id = int(sumber_mentah) if sumber_mentah else None
            except ValueError:
                sumber_sesi_id = -1

            sesi_id = None
            nama_siswa = None
            pesan_gagal = ""
            with database.buka() as kon:
                if not self._bisa_lihat_siswa(kon, siswa_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                baris = kon.execute(
                    "SELECT nama, tingkat FROM siswa WHERE id = ?", (siswa_id,)
                ).fetchone()
                nama_siswa = baris["nama"] if baris else ""
                if (
                    sumber_sesi_id is not None
                    and not database.sasaran_remedial_sesi(
                        kon, siswa_id, sumber_sesi_id
                    )
                ):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                if not jumlah_valid:
                    pesan_gagal = "Jumlah soal harus antara 1 dan 50."
                else:
                    try:
                        sesi_id = database.buat_sesi_remedial(
                            kon, siswa_id,
                            level=(baris["tingkat"] if baris else LEVEL_BAWAAN),
                            jumlah_soal=jumlah,
                            template_ids=template_ids,
                            sumber_sesi_id=sumber_sesi_id,
                        )
                    except ValueError as galat:
                        detail = str(galat)
                        if "bukan kandidat" in detail:
                            pesan_gagal = "Pilihan itu bukan pilihan remedial yang tersedia."
                        elif "kosong" in detail:
                            pesan_gagal = "Pilih setidaknya satu tipe soal untuk remedial."
                        elif "maksimal 3" in detail:
                            pesan_gagal = "Pilih maksimal 3 tipe soal untuk satu remedial."
                        elif "sumber" in detail:
                            pesan_gagal = "Sesi sumber remedial tidak tersedia."
                        elif "jumlah_soal" in detail:
                            pesan_gagal = "Jumlah soal harus antara 1 dan 50."
                        else:
                            pesan_gagal = "Remedial belum dapat dibuat. Periksa pilihannya."
            if pesan_gagal:
                qs = urllib.parse.urlencode({"pesan": pesan_gagal})
            elif sesi_id is None:
                # Tidak ada kesalahan tercatat: katakan apa adanya, jangan
                # membuat sesi acak lalu menyebutnya latihan ulang.
                qs = urllib.parse.urlencode({
                    "pesan": "Belum ada kesalahan tercatat untuk dilatih "
                             "ulang — buat sesi biasa dulu, ya.",
                })
            else:
                fokus = " & ".join(
                    _nama_template(template_id) for template_id in template_ids
                )
                qs = urllib.parse.urlencode({
                    "pesan": f"Remedial {fokus} dibuat — {jumlah} soal baru "
                             f"untuk {nama_siswa} (sesi #{sesi_id}).",
                    "sorot": sesi_id,
                })
            self.send_response(303)
            self.send_header("Location", f"/anak/{siswa_id}?{qs}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if jalur.startswith("/sesi-baru/"):
            try:
                siswa_id = int(jalur.split("/")[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            data = urllib.parse.parse_qs(
                self.rfile.read(panjang).decode("utf-8"),
                keep_blank_values=True,
            )
            pilihan_topik = (data.get("topik") or [TOPIK_BAWAAN])[0].strip()
            if pilihan_topik not in daftar_topik():
                # Topik asing = salah ketik pemanggil: ditolak jelas, BUKAN
                # jatuh diam-diam ke pola bilangan. Pesan menyebut daftar
                # yang sah supaya guru/pemanggil langsung tahu pilihannya.
                pesan = (
                    f"<h1>Topik tidak dikenal</h1>"
                    f"<p><code>{html.escape(pilihan_topik)}</code> tidak "
                    f"terdaftar. Yang tersedia: "
                    f"{', '.join(html.escape(t) for t in daftar_topik())}.</p>"
                )
                return self._kirim(_halaman("Topik tidak dikenal", pesan), 400)
            sesi_id = None
            nama_siswa = None
            with database.buka() as kon:
                if not self._bisa_lihat_siswa(kon, siswa_id):
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                siswa = kon.execute(
                    "SELECT nama, tingkat FROM siswa WHERE id = ?", (siswa_id,)
                ).fetchone()
                if not siswa:
                    return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)
                level = siswa["tingkat"] if siswa["tingkat"] in LEVEL else LEVEL_BAWAAN
                nama_siswa = siswa["nama"]
                if pilihan_topik not in _topik_untuk_level(level):
                    pesan = (
                        f"<h1>Topik belum tersedia untuk kelas ini</h1>"
                        f"<p><code>{html.escape(pilihan_topik)}</code> tidak tersedia "
                        f"untuk {html.escape(label_kelas(siswa['tingkat']))}.</p>"
                    )
                    return self._kirim(_halaman("Topik belum tersedia", pesan), 400)
                pilihan_mode = (data.get("mode") or ["diagnostik"])[0].strip()
                if pilihan_mode not in ("diagnostik", "drill"):
                    pesan = (
                        f"<h1>Mode tidak dikenal</h1>"
                        f"<p><code>{html.escape(pilihan_mode)}</code> tidak terdaftar. "
                        f"Yang tersedia: diagnostik (Diagnosa), drill (Latihan Cepat).</p>"
                    )
                    return self._kirim(_halaman("Mode tidak dikenal", pesan), 400)
                timer_mode, durasi_menit, timer_auto = "tanpa", 15, 0
                if pilihan_mode == "drill":
                    timer_mode = (data.get("timer_mode") or ["tanpa"])[0].strip()
                    if timer_mode not in ("tanpa", "sesi", "soal"):
                        pesan = (
                            f"<h1>Timer tidak dikenal</h1>"
                            f"<p><code>{html.escape(timer_mode)}</code> tidak terdaftar. "
                            f"Yang tersedia: tanpa (tanpa timer), sesi (per sesi, tampil jalan), "
                            f"soal (per soal, internal).</p>"
                        )
                        return self._kirim(_halaman("Timer tidak dikenal", pesan), 400)
                    if timer_mode in ("sesi", "soal"):
                        nilai_durasi = (data.get("durasi_menit") or [""])[0].strip()
                        try:
                            durasi_diajukan = int(nilai_durasi)
                        except ValueError:
                            durasi_diajukan = 0
                        if not 1 <= durasi_diajukan <= 180:
                            pesan = (
                                "<h1>Durasi tidak wajar</h1>"
                                f"<p>Durasi Latihan Cepat harus angka 1–180 menit "
                                f"(terima: {html.escape(nilai_durasi or '(kosong)')}).</p>"
                            )
                            return self._kirim(_halaman("Durasi tidak wajar", pesan), 400)
                        durasi_menit = durasi_diajukan
                        timer_auto = 1 if (data.get("timer_auto") or ["0"])[0] == "1" else 0
                nilai_jumlah = (data.get("jumlah_soal") or [""])[0].strip()
                jumlah_soal = int(nilai_jumlah) if nilai_jumlah.isdigit() and 1 <= int(nilai_jumlah) <= 50 else None
                try:
                    from choice_pages import format_dari_form
                    sesi_id = buat_sesi_seed_baru(
                        kon, siswa_id, level=level, topik=pilihan_topik,
                        mode=pilihan_mode, timer_mode=timer_mode,
                        durasi_menit=durasi_menit, timer_auto=timer_auto,
                        jumlah_soal=jumlah_soal, format_jawaban=format_dari_form(data),
                    )
                except ValueError as galat:
                    return self._kirim(_halaman('Latihan belum dibuat', '<p>' + html.escape(str(galat)) + '</p>'), 400)
            # Sesi baru = history anak (feedback Filia 1 Sep 2026 no. 6):
            # PRG kini ke /anak/<id> tempat strip buat sesi & daftar sesi
            # berada. Banner + sorotan menunjukkan sesi yang baru; PRG tetap
            # dijaga: refresh tidak membuat sesi ganda.
            pesan_sukses = f"Sesi baru untuk {nama_siswa} berhasil dibuat — sesi #{sesi_id} siap dikerjakan."
            qs = urllib.parse.urlencode({"pesan": pesan_sukses, "sorot": sesi_id})
            self.send_response(303)
            self.send_header("Location", f"/anak/{siswa_id}?{qs}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if jalur.startswith("/lampiran/"):
            bagian = jalur.split("/")
            try:
                angka = int(bagian[2])
            except (ValueError, IndexError):
                return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)

            if len(bagian) >= 4 and bagian[3] == "baca-ulang":
                # Ulangi ekstraksi AI atas foto yang sudah ada — tidak
                # menyentuh jawaban sama sekali, hanya hasil_json usulan.
                with database.buka() as kon:
                    if not self._bisa_lihat_lampiran(kon, angka):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    pesan = lampiran_mod.baca_ulang(kon, angka)
                    isi = lampiran_mod.halaman_konfirmasi(kon, angka, pesan)
                    if isi is None:
                        return self._kirim(
                            _halaman("404", "<h1>Lampiran hilang</h1>"), 404
                        )
                    return self._kirim(isi)

            if len(bagian) >= 4 and bagian[3] == "terapkan":
                # Konfirmasi guru: tulis jawaban hasil koreksi ke jalur resmi.
                panjang = int(self.headers.get("Content-Length", 0) or 0)
                mentah = self.rfile.read(panjang).decode("utf-8")
                data = {
                    k: v[0]
                    for k, v in urllib.parse.parse_qs(
                        mentah, keep_blank_values=True
                    ).items()
                }
                with database.buka() as kon:
                    if not self._bisa_lihat_lampiran(kon, angka):
                        return self._kirim(
                            _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                        )
                    jumlah, pesan = lampiran_mod.terapkan(kon, angka, data)
                    isi = lampiran_mod.halaman_konfirmasi(kon, angka, pesan)
                    if isi is None:
                        return self._kirim(
                            _halaman("404", "<h1>Lampiran hilang</h1>"), 404
                        )
                    return self._kirim(isi)

            # Upload foto (multipart) -> ekstraksi -> halaman konfirmasi.
            content_type = self.headers.get("Content-Type", "")
            panjang = int(self.headers.get("Content-Length", 0) or 0)
            if panjang > lampiran_mod.BATAS_UKURAN * 2:
                return self._kirim(
                    _halaman("Terlalu besar", "<h1>Upload terlalu besar</h1>"), 400
                )
            tubuh = self.rfile.read(panjang)
            with database.buka() as kon:
                if not kon.execute(
                    "SELECT 1 FROM sesi WHERE id = ?", (angka,)
                ).fetchone() or not self._bisa_lihat_sesi(kon, angka):
                    # Satu body 404 yang sama untuk "tidak ada" maupun
                    # "bukan milikmu" — beda body jadi oracle eksistensi.
                    return self._kirim(
                        _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                    )
                lid, pesan = lampiran_mod.proses_upload(
                    kon, angka, content_type, tubuh
                )
            if lid is None:
                # Gagal validasi (bukan gambar, terlalu besar, kosong):
                # 400 dengan pesan jelas — bukan 200 menyamarkan kegagalan.
                return self._kirim(
                    _halaman("Upload ditolak", f"<h1>Upload ditolak</h1><p>{html.escape(pesan)}</p>"),
                    400,
                )
            self.send_response(303)
            self.send_header("Location", f"/lampiran/{lid}")
            self.send_header("Content-Length", "0")
            self.end_headers()
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

        if not jalur.startswith("/sesi/"):
            return self._kirim(_halaman("404", "<h1>Tidak ada</h1>"), 404)

        panjang = int(self.headers.get("Content-Length", 0))
        mentah = self.rfile.read(panjang).decode("utf-8")
        data = {
            k: v[0]
            for k, v in urllib.parse.parse_qs(mentah, keep_blank_values=True).items()
        }
        # Metadata presence hanya untuk pemulihan draf pada aksi Pendamping.
        # Handler simpan/konfirmasi resmi tidak boleh meneruskannya ke domain.
        data = {
            k: v for k, v in data.items()
            if k != "hadir_sertakan_pemetaan"
            and not k.startswith(("hadir_dilewati_", "hadir_belum_"))
        }

        sesi_id = int(jalur.split("/")[2])
        with database.buka() as kon:
            kon.execute('BEGIN IMMEDIATE')
            if not self._bisa_lihat_sesi(kon, sesi_id):
                return self._kirim(
                    _halaman("404", "<h1>Halaman tidak ada</h1>"), 404
                )
            status = kon.execute(
                "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)
            ).fetchone()
            if not status or not status["selesai"]:
                return self._kirim(
                    _halaman(
                        "Belum dikirim",
                        "<h1>Koreksi belum tersedia</h1>"
                        "<p>Anak belum menekan Selesai &amp; kirim.</p>",
                    ),
                    409,
                )
            ident = self._identitas()
            try:
                pesan = simpan_sesi(kon, sesi_id, data, guru=ident[0])
            except ValueError as galat:
                kon.rollback()
                return self._kirim(_halaman('Tinjauan belum tersimpan', '<h1>Tinjauan belum tersimpan</h1><p>' + html.escape(str(galat)) + '</p>'), 400)
            kon.commit()  # Respons sukses harus melihat invalidasi yang sudah tersimpan.
            ident = self._identitas()
            self._kirim(
                halaman_sesi_stitch(
                    kon, sesi_id, pesan,
                    peran=ident[1] if ident else "guru",
                    pengguna=ident[0] if ident else "",
                )
            )

    def log_message(self, *a) -> None:  # senyapkan log akses
        pass
