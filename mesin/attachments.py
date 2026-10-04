"""Lampiran foto lembar diisi anak (Fase 2) — foto → AI vision → guru konfirmasi.

Alur lengkapnya:

  1. Guru upload foto lembar hasil kerja anak (POST /lampiran/<sesi>).
  2. Berkas disimpan di cakram (direktori lampiran), hasil AI vision
     (llm.ekstrak_lembar) disimpan sebagai JSON berstatus 'baru'.
  3. Guru membuka halaman konfirmasi, melihat foto + usulan AI per soal,
     mengoreksi bila AI salah baca, lalu menekan Terapkan.
  4. Terapkan menulis jawaban lewat database.simpan_jawaban — jalur yang SAMA
     dengan semua alur lain — lalu reports.diagnosa_murid menilainya. Data
     hasil bacaan AI TIDAK PERNAH masuk laporan tanpa lewat guru.

Garis yang tidak boleh dilanggar modul ini:

  - Berkas yang diterima hanya gambar (jpeg/png/webp), berukuran wajar.
  - Nama berkas yang disimpan SELALU dibuat ulang (bukan nama asli dari
    pengirim) — nama asli bisa membawa path traversal.
  - Jawaban AI tidak pernah langsung disimpan; konfirmasi guru wajib.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import html
import json
import os
import re
import shutil
import secrets
import sqlite3
import time
from pathlib import Path

import database
import question_views
import visual_renderer
import brand
import design_tokens as T

# Batas ukuran berkas: foto HP 8MP JPEG biasanya 2–5 MB; 8 MB longgar.
BATAS_UKURAN = 8 * 1024 * 1024
# Cek magic bytes — Content-Type dari klien tidak boleh dipercaya.
MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
}


def _mime_dari_isi(isi: bytes) -> str | None:
    for awalan, mime in MAGIC.items():
        if isi.startswith(awalan):
            return mime
    # webp: RIFF....WEBP
    if isi[:4] == b"RIFF" and isi[8:12] == b"WEBP":
        return "image/webp"
    return None


def direktori_lampiran() -> Path:
    """Akar penyimpanan gambar. Ikut env OSN_DIREKTORI_LAMPIRAN supaya
    bisa diuji; default di samping DB (/data di container)."""
    ling = os.environ.get("OSN_DIREKTORI_LAMPIRAN", "").strip()
    if ling:
        return Path(ling)
    import database  # late: hindari siklus impor saat modul dimuat

    return Path(database.BAWAAN).resolve().parent / "lampiran"


def bersihkan_berkas(sesi_id: int) -> None:
    """Buang folder foto lampiran milik satu sesi.

    DB menghapus baris lampiran lewat ON DELETE CASCADE, tapi berkasnya
    tinggal di cakram — dipanggil bersama database.hapus_sesi saat sesi
    dihapus. Folder yang tidak ada dianggap bukan kesalahan: sesi tanpa
    foto dan pemanggilan kedua sama-sama aman.
    """
    shutil.rmtree(direktori_lampiran() / str(sesi_id), ignore_errors=True)


# ── Parser multipart minimal ──────────────────────────────────────────
#
# http.server tidak punya parser multipart dan menambah dependensi untuk
# SATU form upload tidak sepadan. Yang dibutuhkan sempit: satu berkas
# (field "foto"). Parser ini mengambil bagian pertama yang punya filename
# dan mengembalikan (nama_berkas, mime_klaim, isi_bytes).


def _parsing_multipart(tubuh: bytes, boundary: str) -> tuple[str, str, bytes] | None:
    try:
        bagian = tubuh.split(f"--{boundary}".encode())
    except ValueError:
        return None
    for b in bagian:
        if not b or b in (b"--", b"--\r\n", b"\r\n"):
            continue
        if b.startswith(b"--"):
            continue  # penutup
        # pisahkan header dan isi
        pemisah = b.find(b"\r\n\r\n")
        if pemisah == -1:
            continue
        header_mentah = b[:pemisah].decode("utf-8", "replace")
        isi = b[pemisah + 4 :]
        if isi.endswith(b"\r\n"):
            isi = isi[:-2]
        nama_berkas = None
        mime = ""
        for baris in header_mentah.split("\r\n"):
            if baris.lower().startswith("content-disposition:"):
                m = re.search(r'filename="([^"]*)"', baris)
                if m:
                    nama_berkas = m.group(1)
                m = re.search(r'name="([^"]*)"', baris)
                if m and m.group(1) != "foto":
                    nama_berkas = None  # field lain, lewati
            elif baris.lower().startswith("content-type:"):
                mime = baris.split(":", 1)[1].strip()
        if nama_berkas is not None:
            return nama_berkas, mime, isi
    return None


def simpan_berkas(sesi_id: int, nama_asli: str, isi: bytes) -> str:
    """Tulis isi gambar ke cakram dengan nama yang dibuat sendiri.

    Nama berkas asli tidak pernah dipakai (path traversal). Kembalikan
    nama berkas yang disimpan, relatif terhadap direktori sesinya.
    """
    akhiran = ".jpg"
    if isi[:4] == b"RIFF" and isi[8:12] == b"WEBP":
        akhiran = ".webp"
    elif isi.startswith(b"\x89PNG"):
        akhiran = ".png"
    nama = f"lembar-{sesi_id}-{os.getpid()}-{abs(hash(isi)) % 10**8}{akhiran}"
    direktori = direktori_lampiran() / str(sesi_id)
    direktori.mkdir(parents=True, exist_ok=True)
    (direktori / nama).write_bytes(isi)
    return nama


def proses_upload(
    kon, sesi_id: int, content_type: str, tubuh: bytes
) -> tuple[int | None, str]:
    """Terima upload -> simpan berkas -> ekstraksi AI -> baris lampiran.

    Mengembalikan (lampiran_id | None, pesan). Pesan berisi petunjuk untuk
    halaman berikutnya (sukses atau alasan gagal yang bisa ditindaklanjuti).
    """
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        return None, "Format upload tidak dikenal."
    terurai = _parsing_multipart(tubuh, m.group(1))
    if not terurai:
        return None, "Tidak ada berkas yang terkirim."
    nama_asli, _mime_klaim, isi = terurai
    if not isi:
        return None, "Berkas kosong."
    if len(isi) > BATAS_UKURAN:
        return None, "Foto terlalu besar (maksimal 8 MB)."
    mime = _mime_dari_isi(isi)
    if mime is None:
        return None, "Berkas bukan gambar yang didukung (JPEG/PNG/WebP)."

    daftar = database.isi_sesi(kon, sesi_id)
    if not daftar:
        return None, "Sesi tidak ditemukan atau kosong."

    # Ekstraksi AI — gagal-diam; tetap simpan lampiran tanpa hasil supaya
    # guru bisa coba lagi dari halaman yang sama.
    hasil_json, pesan = _ekstraksi_untuk(kon, sesi_id, isi)

    nama = simpan_berkas(sesi_id, nama_asli, isi)
    lid = database.simpan_lampiran(
        kon, sesi_id, nama, mime=mime, hasil_json=hasil_json
    )
    return lid, pesan


def _ekstraksi_untuk(kon, sesi_id: int, isi: bytes) -> tuple[str, str]:
    """Jalankan ekstraksi AI atas satu foto -> (hasil_json, pesan untuk guru).

    Dipakai dua kali: saat upload pertama dan saat guru menekan "Coba baca
    ulang" di halaman konfirmasi (tanpa upload ulang). Pesan menyebutkan
    JUMLAH soal yang terbaca dari total — bacaan sebagian adalah keadaan
    normal (anak memfoto satu lembar dari sesi panjang), bukan kegagalan,
    jadi guru harus tahu angkanya, bukan cuma "berhasil/gagal".
    """
    import llm

    total = len(database.isi_sesi(kon, sesi_id))
    b64 = base64.b64encode(isi).decode()
    konteks = _teks_konteks(kon, sesi_id)
    pemilik = kon.execute(
        """SELECT w.pemilik FROM sesi se JOIN siswa w ON w.id=se.siswa_id
           WHERE se.id=?""", (sesi_id,),
    ).fetchone()
    with llm.gunakan_bucket_akun(pemilik["pemilik"] if pemilik else None):
        hasil = llm.ekstrak_lembar(konteks, b64)
    if hasil is None:
        return "", (
            "Foto tersimpan, tapi AI tidak bisa membaca lembar dengan yakin. "
            "Coba tekan \"Coba baca ulang\", atau unggah foto yang lebih "
            "terang/tegak, atau isi manual."
        )
    hasil_json = json.dumps({"soal": hasil}, ensure_ascii=False)
    terisi = sum(1 for h in hasil if h.get("jawaban") or h.get("caraku"))
    if terisi == 0:
        return hasil_json, (
            f"AI melihat lembar ini tapi tidak menemukan jawaban terisi "
            f"(0 dari {total} soal). Pastikan yang difoto adalah lembar "
            "jawaban anak, lalu coba baca ulang."
        )
    return hasil_json, (
        f"AI membaca {terisi} dari {total} soal — periksa dan koreksi di "
        "bawah, soal yang tidak terbaca biarkan kosong."
    )


def baca_ulang(kon, lampiran_id: int) -> str:
    """Jalankan ulang ekstraksi AI atas foto yang SUDAH terunggah.

    Guru tidak perlu memotret dan mengunggah lagi hanya karena bacaan
    pertama gagal (jaringan, model sibuk, balasan terpotong). Berkasnya
    sudah ada di cakram; yang diulang hanya panggilan AI dan hasil_json
    ditimpa. Status lampiran TIDAK diubah — 'diterapkan' tetap
    'diterapkan' supaya jejak penerapan tidak hilang.
    """
    lampiran = database.ambil_lampiran(kon, lampiran_id)
    if not lampiran:
        return "Lampiran tidak ditemukan."
    berkas = (
        direktori_lampiran()
        / str(lampiran["sesi_id"])
        / lampiran["nama_berkas"]
    )
    try:
        isi = berkas.read_bytes()
    except OSError:
        return "Berkas foto tidak ditemukan lagi di server."
    hasil_json, pesan = _ekstraksi_untuk(kon, int(lampiran["sesi_id"]), isi)
    kon.execute(
        "UPDATE lampiran SET hasil_json = ? WHERE id = ?",
        (hasil_json, lampiran_id),
    )
    return pesan


def proses_upload_murid(
    kon, sesi_id: int, content_type: str, tubuh: bytes
) -> tuple[int | None, str]:
    """Upload foto oleh ANAK dari halaman kerjanya (poin 1 & 4 Filia).

    Sengaja BUKAN pintu yang sama dengan guru, walau menyimpan ke tabel yang
    sama. Bedanya dua hal, dan keduanya disengaja:

      1. Palang: tidak menyentuh kunci/malrule/diagnosis sama sekali —
         ekstraksi memakai _teks_konteks (teks soal saja).
      2. Pesan balik ke anak TIDAK menyebut berapa yang terbaca AI. Anak
         tidak sedang dinilai saat mengunggah; angka "3 dari 50" adalah
         informasi untuk guru yang mengoreksi, dan menampilkannya ke anak
         mengundang tafsir "cuma 3 yang benar".

    Jawaban TIDAK langsung masuk laporan: statusnya 'baru' dan guru tetap
    yang menekan Terapkan di halaman konfirmasi. Jadi anak boleh salah
    unggah tanpa merusak data.
    """
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        return None, "Format upload tidak dikenal."
    terurai = _parsing_multipart(tubuh, m.group(1))
    if not terurai:
        return None, "Tidak ada foto yang terkirim."
    nama_asli, _mime_klaim, isi = terurai
    if not isi:
        return None, "Berkasnya kosong."
    if len(isi) > BATAS_UKURAN:
        return None, "Fotonya terlalu besar (maksimal 8 MB)."
    mime = _mime_dari_isi(isi)
    if mime is None:
        return None, "Yang dikirim bukan foto (JPEG/PNG/WebP)."
    if not database.isi_sesi(kon, sesi_id):
        return None, "Sesi tidak ditemukan."

    hasil_json, _pesan_guru = _ekstraksi_untuk(kon, sesi_id, isi)
    nama = simpan_berkas(sesi_id, nama_asli, isi)
    lid = database.simpan_lampiran(
        kon, sesi_id, nama, mime=mime, hasil_json=hasil_json
    )
    return lid, (
        "Foto caramu sudah terkirim ke gurumu. Kamu tidak perlu "
        "mengetik ulang — gurumu yang akan memeriksanya."
    )


def _teks_konteks(kon, sesi_id: int) -> list[str]:
    """Teks soal saja (urut nomor) — TANPA kunci, TANPA diagnosis.

    Dipisah dari _soal_konteks karena jalur MURID juga memanggil ekstraksi:
    halaman/aksi murid tidak boleh menyentuh kolom kunci sama sekali
    (palang di test_murid.py meledak kalau tersentuh). AI memang hanya
    butuh kalimat soalnya untuk memetakan jawaban ke nomor yang benar.
    """
    return [
        visual_renderer.ringkasan_pertanyaan(p)
        for p in question_views.penyajian_sesi_aman(kon, sesi_id)
    ]


def _soal_konteks(kon, sesi_id: int) -> list[dict]:
    """Soal sesi untuk konteks AI dan halaman konfirmasi (teks + kunci)."""
    from teacher_pages import _soal_dari_baris  # late import: hindari siklus

    keluar = []
    for b in database.isi_sesi(kon, sesi_id):
        soal = _soal_dari_baris(b)
        keluar.append(
            {
                "nomor": b["nomor"],
                "sesi_soal_id": b["sesi_soal_id"],
                "teks": soal.teks,
                "penyajian": soal.penyajian,
                "kunci": b["kunci"],
                "jawaban_lama": b["jawaban"] or "",
                "cara_lama": b["cara"] or "",
            }
        )
    return keluar


# ── Percobaan foto durable, hanya saat penegakan paket ON ─────────────

PESAN_FOTO_TERTAHAN = 'Foto belum dapat diproses. Minta orang tua memeriksa atau isi jawaban secara manual.'


class KonflikFoto(ValueError):
    """Resource/identitas/percobaan berubah; jangan mengulang provider otomatis."""


def penegakan_foto():
    import assistant_entitlement_runtime as kuota
    return kuota.enforcement_aktif()


def field_operasi_foto():
    """Nonce native request, bukan izin akses; GET tidak menyimpan state."""
    if not penegakan_foto():
        return ''
    return '<input type="hidden" name="operasi_foto" value="foto_' + secrets.token_hex(16) + '">'


def operasi_foto_sah(nilai):
    if type(nilai) is not str or re.fullmatch(r'foto_[0-9a-f]{32}', nilai) is None:
        raise KonflikFoto('identitas percobaan foto tidak sah')
    return nilai


def operasi_multipart(tubuh, content_type):
    """Tepat satu nonce field non-file; tidak memantulkan body upload."""
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        raise KonflikFoto('format percobaan foto tidak sah')
    nilai = []
    for bagian in tubuh.split(('--' + m.group(1)).encode()):
        header, pisah, isi = bagian.partition(b'\r\n\r\n')
        if pisah and re.search(br'name="operasi_foto"(?:;|\r|$)', header) and b'filename=' not in header:
            nilai.append(isi.removesuffix(b'\r\n').decode('ascii', 'strict'))
    if len(nilai) != 1:
        raise KonflikFoto('identitas percobaan foto tidak sah')
    return operasi_foto_sah(nilai[0])


def _sidik_foto(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


@contextmanager
def _foto_transaksi(path):
    """Tidak auto-create; commit selesai sebelum jaringan/finalisasi kuota."""
    import auth
    from json_storage import transaksi_json
    kon = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute('PRAGMA foreign_keys=ON')
        database.validasi_operasi_foto(kon)
        kon.execute('BEGIN IMMEDIATE')
        with transaksi_json(auth.BERKAS_SANDI):
            yield kon
            kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _snapshot_foto(kon, sesi_id, target_id, principal, periksa_principal):
    """Fencing akun generasi+resource; murid tidak membaca kunci/diagnosis."""
    import auth
    import students
    if principal is None or periksa_principal() != principal:
        raise LookupError('foto tidak ditemukan')
    actor = auth.cari_akun(principal.pengguna)
    if (actor is None or actor.get('id_akun') != principal.id_akun
            or auth.revisi_auth(actor) != principal.revisi_auth
            or actor.get('peran', 'guru') != principal.peran):
        raise LookupError('foto tidak ditemukan')
    sesi = kon.execute('SELECT se.id,se.siswa_id,se.dibatalkan,w.pemilik FROM sesi se '
                       'JOIN siswa w ON w.id=se.siswa_id WHERE se.id=?', (sesi_id,)).fetchone()
    if not sesi or sesi['dibatalkan'] is not None:
        raise LookupError('foto tidak ditemukan')
    if principal.peran == 'murid':
        if target_id or students.siswa_dari_akun(kon, principal.pengguna) != sesi['siswa_id']:
            raise LookupError('foto tidak ditemukan')
    elif principal.peran != 'admin' and not (
            principal.peran == 'guru' and database.sesi_milik(kon, sesi_id, principal.pengguna)):
        raise LookupError('foto tidak ditemukan')
    parent = auth.cari_akun(sesi['pemilik'])
    if not parent or parent.get('peran', 'guru') != 'guru' or not auth.id_akun_sah(parent.get('id_akun')):
        raise KonflikFoto('akun pemilik belum terverifikasi')
    konteks = _teks_konteks(kon, sesi_id)
    if not konteks:
        raise LookupError('foto tidak ditemukan')
    lamp = database.ambil_lampiran(kon, target_id) if target_id else None
    if target_id and (not lamp or lamp['sesi_id'] != sesi_id):
        raise LookupError('foto tidak ditemukan')
    fence = _sidik_foto(dict(lamp)) if lamp else _sidik_foto(tuple(sesi))
    return parent, sesi['pemilik'], konteks, fence


def _hapus_file_foto(path):
    """Cleanup best-effort file milik attempt; kegagalan tidak mengubah receipt."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _file_baru_durable(sesi_id, isi, operasi_id):
    """O_EXCL per attempt; crash-file dapat dikaitkan ke receipt tanpa payload."""
    operasi_foto_sah(operasi_id)
    folder = direktori_lampiran() / str(sesi_id)
    folder.mkdir(parents=True, exist_ok=True)
    nama = operasi_id + '.img'
    path = folder / nama
    dibuat = False
    try:
        with path.open('xb') as f:
            dibuat = True
            f.write(isi); f.flush(); os.fsync(f.fileno())
        fd = os.open(str(folder), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        if dibuat:
            _hapus_file_foto(path)
        raise
    return nama


def proses_foto_terjaga(path, sesi_id, *, principal, periksa_principal,
                       content_type='', tubuh=b'', target_id=0, operasi_id=None, sekarang=None):
    """Claim durable→reserve kuota→provider→result+receipt commit→completed.

    OFF ditangani caller legacy; service ini tidak boleh dipakai sebagai bypass.
    Reserved/sent/unknown replay selalu menahan jaringan. Crash setelah receipt
    result dapat direkonsiliasi walau hasil lampiran telah dibaca ulang lagi.
    """
    import assistant_entitlement_runtime as kuota
    import llm
    if not penegakan_foto():
        raise KonflikFoto('jalur foto terjaga belum aktif')
    kini = int(time.time()) if sekarang is None else sekarang
    if type(kini) is not int or kini < 0:
        raise KonflikFoto('clock percobaan foto tidak sah')
    jenis = 'reread' if target_id else 'upload'
    if not target_id:
        m = re.search(r'boundary="?([^";]+)"?', content_type)
        terurai = _parsing_multipart(tubuh, m.group(1)) if m else None
        if not terurai:
            return None, PESAN_FOTO_TERTAHAN
        _nama_asli, _mime_klaim, isi = terurai
        if not isi or len(isi) > BATAS_UKURAN or _mime_dari_isi(isi) is None:
            return None, PESAN_FOTO_TERTAHAN
        operasi_id = operasi_multipart(tubuh, content_type)
    else:
        operasi_foto_sah(operasi_id)
        with _foto_transaksi(path) as kon:
            _snapshot_foto(kon, sesi_id, target_id, principal, periksa_principal)
            lamp = database.ambil_lampiran(kon, target_id)
            nama = lamp['nama_berkas']
            if Path(nama).name != nama:
                raise KonflikFoto('nama berkas foto tidak sah')
            isi = (direktori_lampiran() / str(sesi_id) / nama).read_bytes()
        if not isi or len(isi) > BATAS_UKURAN or _mime_dari_isi(isi) is None:
            return None, PESAN_FOTO_TERTAHAN
    mime = _mime_dari_isi(isi)
    content_hash = hashlib.sha256(isi).hexdigest()
    with _foto_transaksi(path) as kon:
        parent, pemilik, konteks, fence = _snapshot_foto(
            kon, sesi_id, target_id, principal, periksa_principal)
        akun_id = parent['id_akun']
        context_hash = _sidik_foto(konteks)
        binding = _sidik_foto((akun_id, auth_revisi_foto(parent), principal.id_akun,
                              principal.revisi_auth, sesi_id, target_id, jenis, content_hash, context_hash))
        row = kon.execute('SELECT * FROM operasi_foto_baca WHERE operasi_id=?', (operasi_id,)).fetchone()
        if row:
            if row['permintaan_sidik'] != binding:
                raise KonflikFoto('percobaan foto berbeda')
            # Crash proses di sela file fsync dan commit meninggalkan file tanpa
            # row. Lock DB ini membedakannya dari writer yang masih menyimpan;
            # hanya path exact milik attempt upload ini yang boleh dibersihkan.
            if jenis == 'upload':
                orphan = direktori_lampiran() / str(sesi_id) / (operasi_id + '.img')
                try:
                    if (orphan.is_file() and not orphan.is_symlink()
                            and not kon.execute('SELECT 1 FROM lampiran WHERE sesi_id=? AND nama_berkas=?',
                                                (sesi_id, orphan.name)).fetchone()
                            and hashlib.sha256(orphan.read_bytes()).hexdigest() == content_hash):
                        _hapus_file_foto(orphan)
                except OSError:
                    pass  # Cleanup tertunda; bukan alasan menggagalkan replay.
            replay = dict(row)
        else:
            replay = None
            try:
                kon.execute('INSERT INTO operasi_foto_baca VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)',
                            (operasi_id, akun_id, principal.id_akun, sesi_id, target_id, jenis,
                             content_hash, context_hash, binding, fence, 'reserved', kini, kini))
            except sqlite3.IntegrityError:
                raise KonflikFoto('foto masih diproses') from None
    if replay is not None:
        if replay['status'] in ('result', 'no_output', 'deleted_result', 'deleted_no_output'):
            # Receipt ini tidak bergantung pada hasil mutable lampiran berikutnya.
            hasil_id = replay['hasil_id']
            with _foto_transaksi(path) as kon:
                _snapshot_foto(kon, sesi_id, target_id, principal, periksa_principal)
                hasil_row = database.ambil_lampiran(kon, hasil_id) if hasil_id else None
                if hasil_id and (hasil_row is None or hasil_row['sesi_id'] != sesi_id):
                    raise LookupError('foto tidak ditemukan')
            if replay['status'] in ('result', 'deleted_result'):
                kuota.finalisasi_replay(akun_id, fitur='pembacaan_foto', identitas=operasi_id, sekarang=kini)
            else:
                _pulihkan_release_foto(akun_id, operasi_id, kini)
            return hasil_id, 'Foto sudah diproses.' if hasil_id else PESAN_FOTO_TERTAHAN
        return None, PESAN_FOTO_TERTAHAN
    try:
        ikatan = kuota.reservasi(akun_id, fitur='pembacaan_foto', identitas=operasi_id, sekarang=kini)
        if ikatan is None:
            raise kuota.GalatKuotaRuntime('reservasi foto tidak tersedia')
    except kuota.GalatKuotaRuntime:
        with _foto_transaksi(path) as kon:
            kon.execute("UPDATE operasi_foto_baca SET status='no_output',diperbarui=? WHERE operasi_id=? AND status='reserved'", (kini, operasi_id))
        # Adapter dapat gagal sesudah commit admin. Receipt lokal membuktikan
        # tidak ada outbound; lookup exact tidak boleh reservasi/call ulang.
        _pulihkan_release_foto(akun_id, operasi_id, kini)
        return None, PESAN_FOTO_TERTAHAN

    def sebelum_kirim():
        with _foto_transaksi(path) as kon:
            p, _nama, ctx, baru_fence = _snapshot_foto(kon, sesi_id, target_id, principal, periksa_principal)
            if (p['id_akun'] != akun_id or auth_revisi_foto(p) != auth_revisi_foto(parent)
                    or _sidik_foto(ctx) != context_hash or baru_fence != fence):
                raise KonflikFoto('konteks foto berubah')
            if target_id:
                foto_path = direktori_lampiran() / str(sesi_id) / lamp['nama_berkas']
                if hashlib.sha256(foto_path.read_bytes()).hexdigest() != content_hash:
                    raise KonflikFoto('isi foto berubah')
            cur = kon.execute("UPDATE operasi_foto_baca SET status='sent',diperbarui=? WHERE operasi_id=? AND status='reserved'", (kini, operasi_id))
            if cur.rowcount != 1:
                raise KonflikFoto('percobaan foto berubah')

    try:
        with llm.gunakan_bucket_akun(pemilik):
            bacaan = llm.ekstrak_lembar_tercatat(konteks, base64.b64encode(isi).decode(), sebelum_kirim=sebelum_kirim)
    except llm.FotoBelumDikirim:
        _gagal_foto(path, operasi_id, ikatan, kini, unknown=False)
        return None, PESAN_FOTO_TERTAHAN
    except Exception:
        _gagal_foto(path, operasi_id, ikatan, kini, unknown=True)
        raise
    if not isinstance(bacaan, llm.BacaanFoto) or bacaan.status not in ('result', 'no_output', 'unknown'):
        _gagal_foto(path, operasi_id, ikatan, kini, unknown=True)
        raise KonflikFoto('hasil pembacaan tidak sah')
    if bacaan.status == 'unknown':
        _gagal_foto(path, operasi_id, ikatan, kini, unknown=True)
        return None, PESAN_FOTO_TERTAHAN
    nama_baru = None
    try:
        with _foto_transaksi(path) as kon:
            p, _nama, ctx, baru_fence = _snapshot_foto(kon, sesi_id, target_id, principal, periksa_principal)
            if (p['id_akun'] != akun_id or auth_revisi_foto(p) != auth_revisi_foto(parent)
                    or _sidik_foto(ctx) != context_hash or baru_fence != fence):
                raise KonflikFoto('konteks foto berubah')
            row = kon.execute('SELECT status FROM operasi_foto_baca WHERE operasi_id=?', (operasi_id,)).fetchone()
            if row['status'] not in ('reserved', 'sent') or (bacaan.status == 'result' and row['status'] != 'sent'):
                raise KonflikFoto('percobaan foto berubah')
            if target_id:
                foto_path = direktori_lampiran() / str(sesi_id) / lamp['nama_berkas']
                if hashlib.sha256(foto_path.read_bytes()).hexdigest() != content_hash:
                    raise KonflikFoto('isi foto berubah')
            if bacaan.status == 'result':
                sah = llm.parse_ekstraksi(json.dumps({'soal': bacaan.hasil}, ensure_ascii=False))
                if sah is None or not llm.verifikasi_ekstraksi(sah, len(konteks)):
                    raise KonflikFoto('hasil pembacaan tidak sah')
                sah = llm.saring_ekstraksi(sah, len(konteks))
                hasil_json = json.dumps({'soal': sah}, ensure_ascii=False)
            else:
                hasil_json = ''
            if target_id:
                if bacaan.status == 'result':
                    kon.execute('UPDATE lampiran SET hasil_json=? WHERE id=?', (hasil_json, target_id))
                lid = target_id
            else:
                nama_baru = _file_baru_durable(sesi_id, isi, operasi_id)
                lid = database.simpan_lampiran(kon, sesi_id, nama_baru, mime=mime, hasil_json=hasil_json)
            kon.execute('UPDATE operasi_foto_baca SET status=?,hasil_id=?,diperbarui=? WHERE operasi_id=?',
                        (bacaan.status, lid, kini, operasi_id))
        # Commit hasil+receipt sudah selesai; jangan pindahkan ke dalam transaksi.
        if bacaan.status == 'result':
            kuota.finalisasi(ikatan, sekarang=kini)
        else:
            kuota.lepaskan(ikatan, sekarang=kini)
    except Exception:
        with _foto_transaksi(path) as kon:
            row = kon.execute('SELECT status FROM operasi_foto_baca WHERE operasi_id=?', (operasi_id,)).fetchone()
        if row['status'] not in ('result', 'no_output', 'deleted_result', 'deleted_no_output'):
            if nama_baru:
                _hapus_file_foto(direktori_lampiran() / str(sesi_id) / nama_baru)
            _gagal_foto(path, operasi_id, ikatan, kini, unknown=False)
        raise
    return lid, ('Foto caramu sudah terkirim ke gurumu.' if principal.peran == 'murid'
                 else 'Foto tersimpan. Periksa hasil bacaan sebelum menerapkan.')


def auth_revisi_foto(akun):
    import auth
    return auth.revisi_auth(akun)


def _pulihkan_release_foto(akun_id, operasi_id, kini):
    import assistant_entitlement_runtime as kuota
    import assistant_quota_store
    import admin_store
    row = assistant_quota_store.baca_operasi(admin_store.BAWAAN, akun_id,
            kuota.operasi_id(akun_id, 'pembacaan_foto', operasi_id), fitur='pembacaan_foto')
    if row is not None and row.status != 'released':
        kuota.lepaskan(row.ikatan, sekarang=kini)


def _gagal_foto(path, operasi_id, ikatan, kini, *, unknown):
    import assistant_entitlement_runtime as kuota
    with _foto_transaksi(path) as kon:
        row = kon.execute('SELECT status FROM operasi_foto_baca WHERE operasi_id=?', (operasi_id,)).fetchone()
        status = 'unknown' if unknown and row['status'] == 'sent' else 'no_output'
        kon.execute('UPDATE operasi_foto_baca SET status=?,diperbarui=? WHERE operasi_id=?', (status, kini, operasi_id))
    if status == 'unknown':
        kuota.tandai_unknown(ikatan, sekarang=kini)
    else:
        kuota.lepaskan(ikatan, sekarang=kini)


# ── Halaman konfirmasi guru ───────────────────────────────────────────


def terapkan(kon, lampiran_id: int, data: dict) -> tuple[int, str]:
    """Tulis jawaban hasil konfirmasi guru ke jalur simpan yang resmi.

    Form mengirim per soal: jwb_<ssid>, cara_<ssid>, blm_<ssid>.
    Mengembalikan (jumlah_soal, pesan). Setelah menulis, diagnosis dijalankan
    lewat reports.diagnosa_murid (satu jalur untuk semua sumber jawaban).
    """
    lampiran = database.ambil_lampiran(kon, lampiran_id)
    if not lampiran:
        return 0, "Lampiran tidak ditemukan."
    sesi_id = lampiran["sesi_id"]

    from choice_store import daftar_pilihan
    pilihan_pg = daftar_pilihan(kon, sesi_id)
    if pilihan_pg:
        if kon.execute('SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?', (sesi_id,)).fetchone():
            raise ValueError('Latihan sudah dikirim. Koreksi salinan melalui tinjauan dengan sumber koreksi.')
        for sid, p in pilihan_pg.items():
            nilai = (data.get(f'jwb_{sid}') or '').strip()
            if nilai and nilai not in {o.nilai for o in p.opsi}:
                raise ValueError('Pilih jawaban foto sesuai opsi pada lembar.')
    jumlah = 0
    for b in database.isi_sesi(kon, sesi_id):
        ssid = b["sesi_soal_id"]
        jawaban = (data.get(f"jwb_{ssid}") or "").strip()
        cara = (data.get(f"cara_{ssid}") or "").strip()
        belum = f"blm_{ssid}" in data
        if not (jawaban or cara or belum):
            continue
        database.simpan_jawaban(
            kon, ssid,
            jawaban=jawaban, cara=cara,
            restatement="", belum_pernah=belum,
        )
        jumlah += 1
    if jumlah:
        import reports  # late: diagnosa_murid tinggal di reports

        reports.diagnosa_murid(kon, sesi_id)
        database.tandai_lampiran(kon, lampiran_id, "diterapkan")
        # Sesi yang jadi terisi penuh lewat foto dianggap terkirim: kolom
        # selesai menentukan badge daftar murid ("Masih di review", bukan
        # "Baru") dan masuk hitungan durasi guru. Tanpa ini sesi kertas
        # yang selesai tetap tampak belum dikirim selamanya.
        n_soal = kon.execute(
            "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()[0]
        terisi = kon.execute(
            """SELECT COUNT(DISTINCT ss.id) FROM sesi_soal ss
               JOIN jawaban j ON j.sesi_soal_id = ss.id
               WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
        if n_soal and terisi >= n_soal:
            from student_submissions import arsipkan
            arsipkan(kon, sesi_id, 'foto')
            database.tandai_selesai(kon, sesi_id)
    return jumlah, f"{jumlah} soal dari foto masuk dan didiagnosis."


def _blok_jawaban_lama(s: dict) -> str:
    """Anti-dobel (rencana E): jawaban online lama anak tampil agar guru bisa
    membandingkan dengan bacaan AI sebelum menekan Terapkan. Kosong = blok
    tidak muncul sama sekali."""
    if not (s.get("jawaban_lama") or s.get("cara_lama")):
        return ""
    bagian = [f'<div class="jawaban-lama"><b>Jawaban lama:</b> '
              f'{html.escape(s["jawaban_lama"] or "-")}']
    if s.get("cara_lama"):
        bagian.append(f' &middot; caraku: {html.escape(s["cara_lama"])}')
    bagian.append(
        " (Terapkan akan menimpa — koreksi dulu kalau foto lebih akurat)</div>"
    )
    return "".join(bagian)


def halaman_konfirmasi(kon, lampiran_id: int, pesan: str = "") -> bytes | None:
    """Foto + usulan AI per soal + form koreksi + tombol Terapkan."""
    from style_stitch import gaya_stitch, CSS_SESI
    from teacher_pages import _topbar_stitch

    lampiran = database.ambil_lampiran(kon, lampiran_id)
    if not lampiran:
        return None
    sesi_id = lampiran["sesi_id"]
    usulan = {}
    if lampiran["hasil_json"]:
        try:
            for butir in json.loads(lampiran["hasil_json"]).get("soal", []):
                usulan[butir["nomor"]] = butir
        except (ValueError, KeyError, TypeError):
            usulan = {}

    from choice_store import daftar_pilihan
    from choice_pages import select_guru
    pilihan_pg = daftar_pilihan(kon, sesi_id)
    kartu: list[str] = []
    for s in _soal_konteks(kon, sesi_id):
        u = usulan.get(s["nomor"], {})
        jwb_u = html.escape(u.get("jawaban", ""))
        cara_u = html.escape(u.get("caraku", ""))
        pg = pilihan_pg.get(s['sesi_soal_id'])
        input_jawaban = (select_guru(pg, s['jawaban_lama'], f'foto-jwb-{s["sesi_soal_id"]}') if pg else
                         f'<input id="foto-jwb-{s["sesi_soal_id"]}" type="text" name="jwb_{s["sesi_soal_id"]}" value="{jwb_u}">')
        tanda = (
            f'<span class="tanda">{"?" if u.get("caraku") == "?" else ""}</span>'
            if u.get("caraku") == "?"
            else ""
        )
        kartu.append(f"""
<div class="kartu soal-lampiran">
  <div class="kartu-kepala"><span class="nomor">{s['nomor']}</span>
    <span class="tipe">Soal {s['nomor']}</span>
    <span class="kunci">kunci: {html.escape(s['kunci'])}</span>{tanda}</div>
  {visual_renderer.render_pertanyaan(s['penyajian'], gaya='guru', namespace=str(s['nomor']))}
  {_blok_jawaban_lama(s)}
  <div class="baris">
    <div><label for="foto-jwb-{s['sesi_soal_id']}">Jawaban (bacaan AI)</label>
      {input_jawaban}
      {'<small>Pilih sesuai foto; bacaan AI tidak diterapkan otomatis.</small>' if pg else ''}</div>
    <div><label for="foto-cara-{s['sesi_soal_id']}">Caraku (bacaan AI)</label>
      <input id="foto-cara-{s['sesi_soal_id']}" type="text" name="cara_{s['sesi_soal_id']}" value="{cara_u}"></div>
  </div>
  <label class="centang"><input type="checkbox" name="blm_{s['sesi_soal_id']}">
    anak menulis "belum pernah lihat"</label>
</div>""")

    kabar = f'<div class="pesan">{html.escape(pesan)}</div>' if pesan else ""
    catatan_status = (
        "" if lampiran["status"] == "baru"
        else '<div class="pesan">Lampiran ini sudah diterapkan — '
        "menyimpan lagi akan menimpa jawaban yang ada.</div>"
    )
    # Tombol baca ulang: form TERPISAH dari form terapkan (form bersarang
    # tidak sah di HTML, dan menekan "baca ulang" tidak boleh ikut menulis
    # jawaban). Selalu tersedia — bacaan pertama bisa gagal karena apa saja.
    blok_baca_ulang = (
        f'<form method="post" action="/lampiran/{lampiran_id}/baca-ulang" '
        'class="baca-ulang-form">'
        + field_operasi_foto() + '<button type="submit" class="tombol-baca-ulang">'
        "Coba baca ulang dengan AI</button>"
        '<span class="sub">Foto tidak perlu diunggah ulang.</span>'
        "</form>"
    )

    isi = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul("Konfirmasi lembar foto")}</title>
{brand.tag_kepala()}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">
<style>{GAYA_KONFIRMASI}{gaya_stitch()}{CSS_SESI}</style></head>
<body class="st"><div class="bungkus-st pendamping-editorial-st foto-editorial-st">
{_topbar_stitch("", "guru")}
<main class="sesi-badan-st" aria-labelledby="judul-foto">
<div class="jejak"><a href="/sesi/{sesi_id}">&larr; Kembali ke sesi</a></div>
<header class="editorial-kepala-st"><p class="editorial-alis-st">DARI KERTAS KE CATATAN</p>
<h1 class="sesi-judul-st" id="judul-foto">Konfirmasi bacaan AI — Sesi #{sesi_id}</h1>
<p class="sub">Cocokkan bacaan dengan foto sebelum menerapkan. Hasil AI masih perlu diperiksa.</p></header>
{kabar}{catatan_status}
<div class="kartu pratinjau-foto-st"><img class="foto-lembar"
  src="/lampiran/berkas/{lampiran_id}" alt="Foto lembar anak"></div>
{blok_baca_ulang}
<form method="post" action="/lampiran/{lampiran_id}/terapkan">
{''.join(kartu)}
<div class="koreksi-simpan-st"><button type="submit">Terapkan &amp; diagnosis</button></div>
</form>
</main></div></body></html>"""
    return isi.encode()


GAYA_KONFIRMASI = f"""
* {{ box-sizing: border-box; }}
body {{
  font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR};
  line-height: {T.LINE_HEIGHT}; color: {T.TEKS_UTAMA}; margin: 0;
  background: {T.LATAR_MURID};
}}
.bungkus {{ max-width: 900px; margin: 0 auto; padding: {T.SP_4} 0.9rem {T.SP_7}; }}
a {{ color: {T.AKSEN_TEAL_TUA}; }}
h1 {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_JUDUL_DEWASA}; color: {T.TEKS_JUDUL}; }}
.jejak {{ font-size: .88rem; margin: 0 0 .8rem; }}
.jejak a {{ color: {T.TEKS_SUBTLE}; text-decoration: none; }}
.kartu {{
  background: {T.LATAR_KARTU_MURID}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_4} 1.1rem; margin-bottom: {T.SP_4};
}}
.kartu-kepala {{ display: flex; align-items: center; gap: .55rem; margin-bottom: .5rem; flex-wrap: wrap; }}
.nomor {{
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 2.1rem; height: 2.1rem; font-weight: 700; font-size: .95rem;
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_INVERS}; border-radius: {T.RADIUS_BULAT};
}}
.tipe {{ color: {T.TEKS_SUBTLE}; font-size: .88rem; flex: 1; }}
.kunci {{ font-weight: 700; color: {T.KODE_SALAH_BACA_TEKS}; font-size: .88rem; }}
.tanda {{ color: {T.AKSEN_KORAL_TUA}; font-weight: 700; }}
label {{ display: block; font-size: .84rem; color: {T.TEKS_SUBTLE}; margin: .4rem 0 .15rem; }}
input[type=text] {{
  width: 100%; padding: .5rem .6rem; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KECIL}; font-size: 1rem; font-family: inherit;
}}
input[type=text]:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: {T.BAYANGAN_FOKUS_GURU};
}}
.baris {{ display: flex; gap: .8rem; flex-wrap: wrap; }}
.baris > div {{ flex: 1; min-width: 160px; }}
.centang {{ display: flex; align-items: center; gap: .45rem; margin-top: .5rem; font-size: .88rem; }}
.centang input {{ width: auto; }}
.foto-lembar {{
  display: block; max-width: 100%; max-height: 70vh; margin: 0 auto;
  border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
}}
.pesan {{
  background: {T.LATAR_TERSIMPAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN}; border-radius: {T.RADIUS_SEDANG};
  padding: .7rem .9rem; margin-bottom: {T.SP_4}; font-size: .93rem;
}}
.simpan-strip {{
  position: sticky; bottom: 0; padding: .8rem 0 .4rem;
  background: linear-gradient(to top, {T.LATAR_MURID} 70%, transparent);
}}
button {{
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_INVERS}; border: 0;
  border-radius: 9px; padding: .85rem 1.3rem; font-size: 1rem; cursor: pointer; width: 100%;
}}
/* Baca ulang = aksi sekunder: jangan menyaingi tombol Terapkan yang
   penuh-lebar teal, tapi tetap target sentuh 44px di HP. */
.baca-ulang-form {{
  display: flex; align-items: center; gap: .6rem; flex-wrap: wrap;
  margin: 0 0 {T.SP_4};
}}
.baca-ulang-form .sub {{ color: {T.TEKS_SUBTLE}; font-size: .84rem; }}
button.tombol-baca-ulang {{
  width: auto; min-height: {T.TARGET_SENTUH}; padding: .6rem {T.SP_4};
  background: {T.LATAR_KARTU_MURID}; color: {T.AKSEN_TEAL_TUA};
  border: {T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA}; font-size: .95rem;
}}
"""
