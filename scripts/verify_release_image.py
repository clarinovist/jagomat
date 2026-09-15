#!/usr/bin/env python3
"""Verifikasi image GHCR yang sudah ditarik CI; tidak membangun/memasang image.

Probe stdlib dikirim lewat stdin, bukan bind mount source host. Semua fixture
sintetis berada di tmpfs, dan keluaran subprocess tidak pernah diteruskan ke log.
CLI yang sama dipakai untuk candidate maupun recovery dengan revisi masing-masing.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess

REPOSITORI = "ghcr.io/clarinovist/osn-mesin-latihan"
REVISION_RECOVERY_LEGACY = "bc9c973b50eb1fb04edd37df62f71ba0123f29c6"
KONTRAK_CANDIDATE = "candidate-inline-v1"
KONTRAK_RECOVERY_LEGACY = "recovery-standalone-v1"


def kontrak_untuk_revision(revision: str) -> str:
    """Pilih kontrak HTTP berdasarkan revision image yang sudah diverifikasi."""
    return (
        KONTRAK_RECOVERY_LEGACY
        if revision == REVISION_RECOVERY_LEGACY else KONTRAK_CANDIDATE
    )


def ringkasan_untuk_revision(revision: str) -> dict:
    return {
        "ok": True, "kontrak": 1, "skema": 4, "skenario_migrasi": 2,
        "skenario_tindakan": 7, "http_checks": 7, "provider_calls": 0,
        "http_contract": kontrak_untuk_revision(revision),
        "pengiriman_checks": 0 if revision in {
            REVISION_RECOVERY_LEGACY, "33e241c18024190f41ebca1986e35af26c0397fd",
        } else 6,
    }


# Kompatibilitas import test: revision sintetis biasa memakai kontrak candidate.
RINGKASAN = ringkasan_untuk_revision("b" * 40)

# Sengaja mandiri: tidak mengimpor test/helper host yang tidak ada dalam image.
SUMBER_PROBE = r'''
from __future__ import annotations
import contextlib
import http.client
import importlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
from http.server import ThreadingHTTPServer


def pastikan(kondisi, kode):
    if not kondisi:
        raise RuntimeError(kode)


def snapshot(buka):
    with buka() as kon:
        return tuple(kon.iterdump())


def baris_lama(buka):
    with buka() as kon:
        tabel = [b[0] for b in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if b[0] != 'migrasi_pendamping']
        return {t: tuple(tuple(b) for b in kon.execute(
            'SELECT * FROM "' + t.replace('"', '""') + '" ORDER BY rowid')) for t in tabel}


def sehat(buka):
    with buka() as kon:
        pastikan(kon.execute('PRAGMA foreign_keys').fetchone()[0] == 1, 'fk_nonaktif')
        pastikan(not kon.execute('PRAGMA foreign_key_check').fetchall(), 'fk_rusak')
        pastikan([b[0] for b in kon.execute('PRAGMA integrity_check')] == ['ok'], 'integritas')


def fixture(akar, database, skema, tindakan, konteks, kebijakan, simpan):
    akar.mkdir()
    database.BAWAAN = akar / 'belajar.db'
    skema.BAWAAN = akar / 'pendamping.db'
    database.siapkan(database.BAWAAN)
    skema.siapkan(skema.BAWAAN)
    akun = 'akun_' + 'a' * 32
    with database.buka() as kon:
        anak = database.tambah_siswa(kon, 'Anak Sintetis', 'P3', pemilik='guru')
        # Snapshot benar-benar berisi bukti, bukan hanya membandingkan tabel kosong.
        putaran = database.buat_putaran_fokus(kon, anak, 'P3')
        bukti = database.buat_sesi_dari_urutan(kon, anak, 6, ('deret_aritmetika',), level='P3')
        kon.execute("UPDATE sesi SET tujuan='pemetaan', putaran_id=?, selesai='2026-09-01 09:00:00' WHERE id=?", (putaran, bukti))
        butir = database.isi_sesi(kon, bukti)[0]['sesi_soal_id']
        database.konfirmasi_hasil(kon, bukti, guru='guru', dilewati={butir})
        sumber = database.buat_sesi_dari_urutan(kon, anak, 7, ('deret_aritmetika',), level='P3')
        versi = konteks.versi_resource(kon, 'sesi', str(sumber), pemilik='guru')
    with contextlib.closing(skema.buka()) as kon, kon:
        simpan.beri_persetujuan(kon, akun, policy_version=kebijakan.VERSI_KEBIJAKAN,
            provider_id=kebijakan.PROVIDER_ID, kategori='chat_umum', sekarang=100)
        izin = simpan.beri_persetujuan_konteks(kon, akun, jenis='sesi', resource_id=str(sumber),
            resource_version=versi, kategori='ringkasan_netral', sekarang=100)
        chat = simpan.buat_chat(kon, akun, 'aktif', sekarang=100, context_kind='sesi',
            context_id=str(sumber), context_version=izin.versi,
            context_resource_version=versi, context_category=izin.kategori)
        operasi = simpan.mulai_operasi(kon, akun, chat.id, 'req_sintetis_usulan',
            consent_version=1, memory_version=0, context_version=izin.versi, sekarang=100)
        kon.execute("UPDATE operasi SET status='selesai', selesai=100")
        mentah = {'topik_id': 'pola-bilangan', 'template_ids': ['deret_aritmetika'],
                  'level': 'P3', 'jumlah_soal': 10}
        sah = tindakan.validasi_usulan(mentah)
        usulan = simpan.simpan_usulan(kon, akun, chat.id, operasi.request_id,
            payload_json=json.dumps(sah.ke_dict()), hash_usulan=tindakan.hash_usulan(sah),
            chat_version=chat.versi, consent_version=1, context_version=izin.versi,
            context_resource_version=versi, sekarang=100)
    return akun, anak, usulan


def uji_migrasi(database, skema, privat):
    # Dua kondisi: v3 lengkap dan migrasi parsial (review sudah ada, marker belum).
    for parsial in (False, True):
        with privat() as kon:
            if not parsial:
                kon.execute('DROP TABLE tinjauan_usulan')
            kon.execute('DELETE FROM migrasi_pendamping WHERE versi > 3')
            kon.execute('PRAGMA user_version = 3')
        with database.buka() as kon:
            kon.execute('DROP TABLE eksekusi_pendamping')
        lama_data, lama_privat = baris_lama(database.buka), baris_lama(privat)
        for _ in range(2):
            database.siapkan(database.BAWAAN)
            skema.siapkan(skema.BAWAAN)
            with privat() as kon:
                pastikan(kon.execute('PRAGMA user_version').fetchone()[0] == 4, 'skema_bukan_v4')
                pastikan([b[0] for b in kon.execute('SELECT versi FROM migrasi_pendamping ORDER BY versi')] == [1, 2, 3, 4], 'marker_migrasi')
                pastikan(kon.execute('SELECT COUNT(*) FROM tinjauan_usulan').fetchone()[0] == 0, 'review_awal')
            with database.buka() as kon:
                pastikan(kon.execute('SELECT COUNT(*) FROM eksekusi_pendamping').fetchone()[0] == 0, 'ledger_awal')
            for buka, lama in ((database.buka, lama_data), (privat, lama_privat)):
                baru = baris_lama(buka)
                pastikan(all(baru.get(t) == isi for t, isi in lama.items()), 'baris_migrasi_berubah')
                sehat(buka)
        pertama = snapshot(database.buka), snapshot(privat)
        database.siapkan(database.BAWAAN)
        skema.siapkan(skema.BAWAAN)
        pastikan((snapshot(database.buka), snapshot(privat)) == pertama, 'migrasi_tidak_idempoten')


def uji_tindakan(akar, jenis, modul):
    database, skema, tindakan, konteks, kebijakan, simpan, siklus = modul
    akun, anak, usulan = fixture(akar, database, skema, tindakan, konteks, kebijakan, simpan)

    @contextlib.contextmanager
    def privat():
        with contextlib.closing(skema.buka()) as kon, kon:
            yield kon

    if jenis == 'retry':
        uji_migrasi(database, skema, privat)

    def siklus_snapshot():
        with database.buka() as kon:
            tabel = ('kejadian_belajar', 'bukti_fokus', 'putaran_fokus', 'konfirmasi_hasil', 'snapshot_outcome')
            isi = tuple(tuple(tuple(b) for b in kon.execute('SELECT * FROM ' + t + ' ORDER BY rowid')) for t in tabel)
            pastikan(bool(isi[-1]) and bool(isi[-2]), 'bukti_fixture_kosong')
            return isi, siklus.rencana_berikutnya(database.muat_bukti_siklus(kon, anak), anak)

    def jumlah():
        with database.buka() as kon:
            return kon.execute('SELECT COUNT(*) FROM sesi').fetchone()[0]

    def hasil():
        with privat() as kon:
            return tindakan.ambil_hasil_usulan(kon, akun, 'guru', usulan.id)

    def konfirmasi(token, waktu=102):
        with privat() as kon:
            return tindakan.konfirmasi_dan_buat_sesi(kon, akun, 'guru', usulan.id,
                versi=usulan.versi, hash_diharapkan=usulan.hash_usulan,
                request_id=token, sekarang=waktu)

    def ditolak(panggil, galat):
        sebelum = snapshot(database.buka), snapshot(privat)
        try:
            panggil()
        except galat:
            pass
        else:
            raise RuntimeError('guard_tidak_menolak')
        pastikan((snapshot(database.buka), snapshot(privat)) == sebelum, 'penolakan_menulis')

    awal_siklus = siklus_snapshot()
    awal = jumlah()
    # Lookup/GET bukan jalur eksekusi; token yang tidak ditinjau juga ditolak.
    pastikan(hasil() is None and jumlah() == awal, 'lookup_mengeksekusi')
    ditolak(lambda: konfirmasi('aksi_' + 'f' * 32), tindakan.GalatTindakan)
    sebelum = snapshot(database.buka)
    with privat() as kon:
        token = tindakan.tinjau_usulan(kon, akun, 'guru', usulan.id, sekarang=101)
    pastikan(snapshot(database.buka) == sebelum, 'review_mengeksekusi')

    if jenis in ('retry', 'batal', 'hapus'):
        asli = simpan.selesaikan_usulan
        simpan.selesaikan_usulan = lambda *a, **k: False
        try:
            try:
                konfirmasi(token)
            except tindakan.GalatTindakan:
                pass
            else:
                raise RuntimeError('crash_tidak_terjadi')
        finally:
            simpan.selesaikan_usulan = asli
        pastikan(jumlah() == awal + 1, 'crash_bukan_setelah_commit')
        with privat() as kon:
            catatan = simpan.ambil_usulan(kon, akun, usulan.id)
            pastikan(catatan.status == 'menunggu' and catatan.sesi_id is None, 'crash_privat_commit')
        sesi_id = hasil()
        pastikan(sesi_id is not None, 'ledger_tidak_ditemukan')
    elif jenis in ('pemilik_baru', 'izin_baru'):
        sesi_id = None
    else:
        sesi_id = konfirmasi(token)

    if sesi_id is not None:
        with database.buka() as kon:
            ledger = kon.execute('SELECT sesi_id FROM eksekusi_pendamping').fetchall()
            pastikan([b[0] for b in ledger] == [sesi_id], 'ledger_ganda')
            sesi = kon.execute('SELECT * FROM sesi WHERE id=?', (sesi_id,)).fetchone()
            pastikan(sesi['tujuan'] == 'bebas' and all(sesi[k] is None for k in
                ('putaran_id', 'bagian_checkpoint', 'dikonfirmasi_guru', 'kunci_idempotensi')), 'sesi_bukan_manual')
            pastikan(kon.execute('SELECT COUNT(*) FROM sesi_soal WHERE sesi_id=?', (sesi_id,)).fetchone()[0] == 10, 'jumlah_soal')

    pastikan(siklus_snapshot() == awal_siklus, 'siklus_berubah')
    if jenis == 'retry':
        pastikan(konfirmasi(token, 9000) == sesi_id, 'retry_id_berubah')
        pastikan(konfirmasi(token, 9001) == sesi_id, 'retry_kedua_berubah')
        pastikan(jumlah() == awal + 1, 'sesi_ganda')
        with privat() as kon:
            catatan = simpan.ambil_usulan(kon, akun, usulan.id)
            pastikan(catatan.status == 'selesai' and catatan.sesi_id == sesi_id, 'retry_privat')
        with database.buka() as kon:
            pastikan(kon.execute('SELECT COUNT(*) FROM eksekusi_pendamping').fetchone()[0] == 1, 'retry_ledger_ganda')
    else:
        if jenis in ('batal', 'hapus'):
            with database.buka() as kon:
                if jenis == 'hapus':
                    pastikan(database.hapus_sesi(kon, sesi_id), 'hapus_fixture')
                else:
                    database.batalkan_sesi(kon, sesi_id)
            # Pembatalan eksplisit sendiri menambah satu kejadian, tetapi
            # snapshot/konfirmasi/putaran/rekomendasi sebelumnya tetap immutable.
            setelah = siklus_snapshot()
            pastikan(setelah[0][1:] == awal_siklus[0][1:] and setelah[1] == awal_siklus[1], 'bukti_terminal_berubah')
            lama = awal_siklus[0][0]
            pastikan(setelah[0][0][:len(lama)] == lama and
                len(setelah[0][0]) == len(lama) + (jenis == 'batal'), 'kejadian_terminal_berubah')
            awal_siklus = setelah
            galat = tindakan.GalatTindakan
        elif jenis in ('pemilik', 'pemilik_baru'):
            with database.buka() as kon:
                kon.execute("UPDATE siswa SET pemilik='guru-lain' WHERE id=?", (anak,))
            galat = LookupError
        else:
            with privat() as kon:
                kon.execute('UPDATE persetujuan SET dicabut=103, versi=versi+1')
            galat = tindakan.GalatTindakan
        for _ in range(2):
            ditolak(lambda: konfirmasi(token), galat)
            ditolak(hasil, galat)
        if jenis in ('pemilik', 'pemilik_baru'):
            with database.buka() as kon:
                kon.execute("UPDATE siswa SET pemilik='guru' WHERE id=?", (anak,))
    pastikan(siklus_snapshot() == awal_siklus, 'siklus_berubah')
    sehat(database.buka)
    sehat(privat)


def uji_http(akar, database, skema, kontrak_http):
    import auth
    import sessions
    import web
    import brand
    akar.mkdir()
    database.BAWAAN = akar / 'belajar.db'
    skema.BAWAAN = akar / 'pendamping.db'
    auth.BERKAS_SANDI = akar / 'sandi.json'
    sessions.BERKAS_SESI = akar / 'sesi.json'
    database.siapkan(database.BAWAAN)
    skema.siapkan(skema.BAWAAN)
    auth.simpan_sandi('sandi-sintetis-probe-123', 'guru', path=auth.BERKAS_SANDI)
    auth.pastikan_id_akun(path=auth.BERKAS_SANDI)
    akun = auth.cari_akun('guru')
    # Recovery pinned lama belum mengenal revisi; candidate wajib memakai
    # penerbitan principal yang memeriksa snapshot autentikasi mutakhir.
    if hasattr(sessions, 'buat_dari_principal'):
        principal = auth.autentikasi('guru', 'sandi-sintetis-probe-123')
        pastikan(principal is not None, 'principal_probe_tidak_sah')
        token = sessions.buat_dari_principal(principal)
    else:
        token = sessions.buat('guru', 'guru', id_akun=akun['id_akun'])
    with database.buka() as kon:
        anak = database.tambah_siswa(kon, 'Anak HTTP Sintetis', 'P3', pemilik='guru')
    # Semua aset yang diumumkan image wajib terkemas; tidak mengunci markup UI.
    for nama in brand.ASET:
        pastikan((brand.FOLDER_ASET / nama).is_file(), 'aset_hilang')
    galat_server = []
    class Server(ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            galat_server.append(True)  # Tidak pernah log traceback/request.
    server = Server(('127.0.0.1', 0), web.Penangan)
    ulir = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
    ulir.start()
    try:
        status_pendamping = 200 if kontrak_http == 'recovery-standalone-v1' else 303
        for jalur, cookie, status in (
            ('/', False, 200), ('/akun', False, 401), ('/murid/', False, 303),
            ('/pendamping', False, 401), ('/pendamping', True, status_pendamping),
            ('/aset/favicon.svg', False, 200),
        ):
            koneksi = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            try:
                koneksi.request('GET', jalur, headers={'Cookie': 'osn_sesi=' + token} if cookie else {})
                respons = koneksi.getresponse()
                tubuh = respons.read()
                pastikan(respons.status == status, 'http_status')
                if jalur == '/murid/':
                    lokasi = respons.getheader('Location') or ''
                    pastikan(lokasi == '/masuk' or lokasi.startswith('/masuk?'), 'http_redirect')
                if jalur == '/pendamping' and cookie:
                    if kontrak_http == 'candidate-inline-v1':
                        pastikan(respons.getheader('Location') == '/guru', 'http_redirect_candidate')
                        pastikan(not tubuh, 'http_redirect_body_candidate')
                    else:
                        pastikan(respons.getheader('Location') is None, 'http_redirect_recovery')
                if cookie:
                    pastikan(respons.getheader('Cache-Control') == 'no-store', 'http_cache')
                    if respons.status == 200:
                        pastikan(respons.getheader('Referrer-Policy') == 'no-referrer', 'http_referrer')
                        pastikan(respons.getheader('X-Frame-Options') == 'DENY', 'http_frame')
                        pastikan('noindex' in (respons.getheader('X-Robots-Tag') or ''), 'http_robot')
                        pastikan("default-src 'none'" in (respons.getheader('Content-Security-Policy') or ''), 'http_csp')
                        pastikan('text/html' in (respons.getheader('Content-Type') or '') and bool(tubuh), 'http_render')
                        if jalur == '/pendamping':
                            pastikan(b'id="judul-pendamping">Sebelum mulai</h1>' in tubuh,
                                     'http_render_recovery')
                if jalur == '/aset/favicon.svg':
                    pastikan(bool(tubuh) and 'image/svg+xml' in (respons.getheader('Content-Type') or ''), 'http_aset')
            finally:
                koneksi.close()
        if kontrak_http == 'candidate-inline-v1':
            jalur = '/anak/' + str(anak) + '?bantuan=rencana'
            koneksi = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            try:
                koneksi.request('GET', jalur, headers={'Cookie': 'osn_sesi=' + token})
                respons = koneksi.getresponse()
                tubuh = respons.read()
                pastikan(respons.status == 200, 'http_inline_status_candidate')
                pastikan(b'id="bantuan-rencana"' in tubuh, 'http_inline_render_candidate')
                pastikan(respons.getheader('Cache-Control') == 'no-store', 'http_inline_cache_candidate')
                pastikan(respons.getheader('Referrer-Policy') == 'no-referrer', 'http_inline_referrer_candidate')
                pastikan(respons.getheader('X-Frame-Options') == 'DENY', 'http_inline_frame_candidate')
                pastikan('noindex' in (respons.getheader('X-Robots-Tag') or ''), 'http_inline_robot_candidate')
                pastikan("default-src 'none'" in (respons.getheader('Content-Security-Policy') or ''), 'http_inline_csp_candidate')
            finally:
                koneksi.close()
    finally:
        server.shutdown()
        server.server_close()
        ulir.join(timeout=10)
    pastikan(not ulir.is_alive() and not galat_server, 'http_server')


def uji_pengiriman(akar, database):
    """Migrasi additive dan provenance diuji pada data sintetis, bukan keluarga."""
    import student_submissions
    import review_store
    akar.mkdir()
    database.BAWAAN = akar / 'belajar.db'
    database.siapkan(database.BAWAAN)
    with database.buka() as kon:
        siswa = database.tambah_siswa(kon, 'Anak Probe Pengiriman', 'P3', pemilik='guru')
        sesi = database.buat_sesi_dari_urutan(kon, siswa, 73, ('deret_aritmetika',), level='P3')
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        # Turunkan fixture menjadi schema pra-pengiriman, tanpa mengubah tabel lama.
        tabel_baru = ('tinjauan_outcome', 'tinjauan_guru', 'pengiriman_butir',
                      'pengiriman_sesi', 'refleksi_jawaban', 'versi_pekerjaan')
        triggers = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                    if r[0].startswith(('pengiriman_', 'tinjauan_outcome_', 'jawaban_versi_', 'refleksi_jawaban_versi_'))]
        for nama in triggers:
            kon.execute('DROP TRIGGER "' + nama + '"')
        for nama in tabel_baru:
            kon.execute('DROP TABLE ' + nama)
    lama = baris_lama(database.buka)
    for _ in range(2):
        database.siapkan(database.BAWAAN)
        baru = baris_lama(database.buka)
        pastikan(all(baru.get(t) == isi for t, isi in lama.items()), 'pengiriman_migrasi_preservasi')
        sehat(database.buka)
    awal = snapshot(database.buka)
    database.siapkan(database.BAWAAN)
    pastikan(snapshot(database.buka) == awal, 'pengiriman_migrasi_idempoten')
    with database.buka() as kon:
        student_submissions.arsipkan(kon, sesi, 'akun')
        database.tandai_selesai(kon, sesi)
        arsip = tuple(kon.execute('SELECT * FROM pengiriman_butir WHERE sesi_id=?', (sesi,)).fetchone())
        pastikan(kon.execute('SELECT jawaban FROM pengiriman_butir WHERE sesi_id=?', (sesi,)).fetchone()[0] == '', 'pengiriman_kosong')
        for sql in (
            "UPDATE pengiriman_butir SET jawaban='123' WHERE sesi_id=?",
            'DELETE FROM pengiriman_butir WHERE sesi_id=?',
        ):
            try:
                kon.execute(sql, (sesi,))
            except sqlite3.IntegrityError:
                pass
            else:
                raise RuntimeError('pengiriman_immutable')
        review_store.simpan(kon, sesi, {f'catatan_tinjauan_{sid}': 'Anak mendapat contoh awal.',
            f'provenance_{sid}': 'setelah_bantuan', f'jawaban_bantuan_{sid}': '123'}, 'guru')
        pastikan(kon.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0] == 0, 'tinjauan_bukan_bukti')
        jid = database.simpan_jawaban(kon, sid, '123', 'Setelah mendapat contoh')
        for benar, kode in ((True, None), (False, 'K'), (False, 'H')):
            if not benar:
                database.simpan_jawaban(kon, sid, '', '')
            database.simpan_diagnosis(kon, jid, benar, None, kode, manual=True)
            try:
                database.konfirmasi_hasil(kon, sesi, guru='guru')
            except ValueError:
                pass
            else:
                raise RuntimeError('bantuan_menjadi_bukti')
        pastikan(tuple(kon.execute('SELECT * FROM pengiriman_butir WHERE sesi_id=?', (sesi,)).fetchone()) == arsip, 'pengiriman_berubah')
        identitas = database.konfirmasi_hasil(kon, sesi, guru='guru', dilewati={sid})
        pastikan(kon.execute('SELECT COUNT(*) FROM tinjauan_outcome WHERE konfirmasi_id=?', (identitas,)).fetchone()[0] == 1, 'tinjauan_provenance_hilang')
    sehat(database.buka)


def jalankan_probe(akar):
    # Tetapkan path SEBELUM impor; tidak pernah membuka konfigurasi/DB bawaan host.
    os.environ.update({
        'OSN_BERKAS_DB': str(akar / 'awal.db'),
        'PENDAMPING_BERKAS_DB': str(akar / 'awal-privat.db'),
        'OSN_BERKAS_SANDI': str(akar / 'awal-sandi.json'),
        'OSN_BERKAS_SESI': str(akar / 'awal-sesi.json'),
        'OSN_FOLDER_LEMBAR': str(akar / 'lembar'),
        'OSN_PBKDF2_ITERASI': '1000', 'OSN_HTTPS': '0',
        'PENDAMPING_AKTIF': '1', 'DEEPSEEK_API_KEY': 'kunci-sintetis-probe',
        'DEEPSEEK_BASE_URL': 'https://provider.invalid', 'DEEPSEEK_MODEL': 'deepseek-flash',
    })
    revision = os.environ.get('OSN_RELEASE_REVISION', '')
    if revision == 'bc9c973b50eb1fb04edd37df62f71ba0123f29c6':
        kontrak_http = 'recovery-standalone-v1'
    else:
        kontrak_http = 'candidate-inline-v1'
    # Defense in depth untuk eksekusi test tanpa Docker: hanya socket loopback,
    # tanpa DNS eksternal; provider default juga selalu gagal jika terpanggil.
    asli_connect = socket.socket.connect
    asli_connect_ex = socket.socket.connect_ex
    asli_resolve = socket.getaddrinfo
    panggilan = []
    def alamat_sah(alamat):
        pastikan(isinstance(alamat, tuple) and alamat[0] == '127.0.0.1', 'network_dilarang')
    def connect(soket, alamat):
        alamat_sah(alamat)
        return asli_connect(soket, alamat)
    def connect_ex(soket, alamat):
        alamat_sah(alamat)
        return asli_connect_ex(soket, alamat)
    def resolve(host, port, *a, **k):
        pastikan(host == '127.0.0.1', 'dns_dilarang')
        return asli_resolve(host, port, *a, **k)
    def provider(*a, **k):
        panggilan.append(True)
        raise RuntimeError('provider_dilarang')
    socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = connect, connect_ex, resolve
    try:
        nama = ('database', 'assistant_schema', 'assistant_actions', 'assistant_context',
                'assistant_policy', 'assistant_store', 'learning_cycle')
        modul = tuple(importlib.import_module(n) for n in nama)
        layanan = importlib.import_module('assistant_service')
        klien = importlib.import_module('assistant_client')
        layanan.panggil_provider_default = provider
        klien.kirim = provider
        for jenis in ('retry', 'batal', 'hapus', 'pemilik', 'izin', 'pemilik_baru', 'izin_baru'):
            uji_tindakan(akar / jenis, jenis, modul)
        uji_http(akar / 'http', modul[0], modul[1], kontrak_http)
        pengiriman_checks = 0
        if revision not in ('bc9c973b50eb1fb04edd37df62f71ba0123f29c6',
                            '33e241c18024190f41ebca1986e35af26c0397fd'):
            uji_pengiriman(akar / 'pengiriman', modul[0])
            pengiriman_checks = 6
        pastikan(not panggilan, 'provider_terpanggil')
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = asli_connect, asli_connect_ex, asli_resolve
    return {'ok': True, 'kontrak': 1, 'skema': 4, 'skenario_migrasi': 2,
            'skenario_tindakan': 7, 'http_checks': 7, 'provider_calls': 0,
            'http_contract': kontrak_http, 'pengiriman_checks': pengiriman_checks}


def main():
    try:
        with tempfile.TemporaryDirectory(prefix='osn-release-') as sementara:
            with open(os.devnull, 'w') as sunyi, contextlib.redirect_stdout(sunyi), contextlib.redirect_stderr(sunyi):
                ringkasan = jalankan_probe(Path(sementara))
    except Exception:
        print(json.dumps({'ok': False, 'kode': 'probe_gagal'}))
        return 1
    print(json.dumps(ringkasan, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''


class GalatVerifikasi(Exception):
    """Kode konstan saja; tidak memuat output Docker/data aplikasi."""


def validasi_rujukan(image: str, revision: str) -> None:
    if not re.fullmatch(re.escape(REPOSITORI) + r"@sha256:[0-9a-f]{64}", image):
        raise GalatVerifikasi("image_tidak_immutable")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise GalatVerifikasi("revision_tidak_penuh")


def periksa_inspect(teks: str, image: str, revision: str) -> None:
    try:
        data = json.loads(teks)
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError
        item = data[0]
        if not isinstance(item['RepoDigests'], list):
            raise ValueError
        if (item['Config']['Labels']['org.opencontainers.image.revision'] != revision
                or image not in item['RepoDigests']
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', item['Id'])):
            raise ValueError
        # VOLUME tambahan dari image juga tidak boleh membuat mount tak terduga.
        if set(item['Config'].get('Volumes') or {}) - {'/data'}:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise GalatVerifikasi("identitas_image_tidak_cocok") from None


def perintah_probe(image: str, nama: str, revision: str) -> list[str]:
    return [
        'docker', 'run', '--rm', '--interactive', '--pull', 'never', '--name', nama,
        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--user', '10001:10001',
        '--tmpfs', '/data:rw,uid=10001,gid=10001', '--tmpfs', '/tmp',
        '--env', 'TMPDIR=/data', '--env', 'OSN_RELEASE_REVISION=' + revision,
        '--no-healthcheck', '--workdir', '/app',
        '--entrypoint', 'python', image, '-B', '-',
    ]


def jalankan(argv: list[str], *, masukan=None, batas=30):
    return subprocess.run(argv, input=masukan, text=True, capture_output=True,
                          timeout=batas, check=False, shell=False)


def verifikasi(image: str, revision: str) -> dict:
    validasi_rujukan(image, revision)
    inspeksi = jalankan(['docker', 'image', 'inspect', image])
    if inspeksi.returncode:
        raise GalatVerifikasi('inspect_gagal')
    periksa_inspect(inspeksi.stdout, image, revision)
    nama = 'osn-release-probe-' + secrets.token_hex(12)
    try:
        hasil = jalankan(perintah_probe(image, nama, revision), masukan=SUMBER_PROBE, batas=180)
        if hasil.returncode:
            raise GalatVerifikasi('probe_gagal')
    except (Exception, KeyboardInterrupt):
        # Timeout pada client Docker belum tentu menghentikan container.
        # Bersihkan HANYA nama acak milik pemanggilan ini, tanpa log stderr.
        try:
            jalankan(['docker', 'container', 'rm', '--force', nama])
        except Exception:
            pass
        raise
    try:
        ringkasan = json.loads(hasil.stdout)
        diharapkan = ringkasan_untuk_revision(revision)
        if ringkasan != diharapkan or any(type(ringkasan[k]) is not type(v) for k, v in diharapkan.items()):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise GalatVerifikasi('ringkasan_tidak_sah') from None
    return {'ok': True, 'image': image, 'revision': revision, 'probe': diharapkan.copy()}


class ParserAman(argparse.ArgumentParser):
    def error(self, message):
        raise GalatVerifikasi('argumen_tidak_sah')


def main(argv=None) -> int:
    parser = ParserAman(description=__doc__, allow_abbrev=False)
    parser.add_argument('--image', required=True)
    parser.add_argument('--revision', required=True)
    try:
        argumen = parser.parse_args(argv)
        ringkasan = verifikasi(argumen.image, argumen.revision)
    except GalatVerifikasi as galat:
        print(json.dumps({'ok': False, 'kode': str(galat)}))
        return 1
    except (Exception, KeyboardInterrupt):
        print(json.dumps({'ok': False, 'kode': 'verifikasi_gagal'}))
        return 1
    print(json.dumps(ringkasan, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
