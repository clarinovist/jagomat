"""Pekerja rekonsiliasi terjadwal: batch bounded, lease file, idempoten.

Tanpa route HTTP dan tanpa dispatch saat startup; entry kanonis
`mesin/rekonsiliasi_langganan.py` (ikut image) dengan pembungkus dev di
`scripts/rekonsiliasi_langganan.py`. Hanya invoice yang sudah punya intent yang
diproses — pekerja tidak pernah membuat invoice, enrollment, atau pembayaran baru.
Panggilan provider selalu di luar lock DB/auth, dan sebelum receipt/grant snapshot
invoice + owner profil + revisi akun diperiksa ulang. Unknown (timeout/404/5xx)
dicatat `belum_terverifikasi` dan dijadwalkan ulang secara bounded, bukan dianggap
gagal; refund/pembayaran terlambat tetap `perlu_diperiksa` — kebijakan D8 (26 Sep
2026) = tanpa grant otomatis, koreksi manual admin.
"""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import sqlite3

import admin_registration
import admin_store
import auth
import midtrans_contract as midtrans
import subscription as d
import subscription_store as store

BATAS_BAWAAN = 5
BATAS_MAKS = 20
JEDA_BAWAAN = 300
HORIZON_BAWAAN = 7 * 86400
_PERCOBAAN_MAKS = 200


@contextmanager
def lease(path):
    """Lease antar proses; yield False bila lease sedang dipegang proses lain."""
    fd = os.open(os.fspath(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            os.ftruncate(fd, 0)
            os.write(fd, b"pid=%d\n" % os.getpid())
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def kandidat(path_admin, *, sekarang, batas=BATAS_BAWAAN, jeda=JEDA_BAWAAN,
             horizon=HORIZON_BAWAAN):
    """Invoice ber-intent tanpa receipt; cooldown `jeda` dan cutoff `horizon` dijaga."""
    if type(batas) is not int or not 1 <= batas <= BATAS_MAKS:
        raise ValueError("batas batch tidak sah")
    d.waktu(sekarang)
    hasil = []
    with admin_store.buka_baca(path_admin) as kon:
        baris = kon.execute(
            "SELECT i.invoice_id, i.akun_id, i.kedaluwarsa FROM langganan_invoice AS i "
            "WHERE EXISTS (SELECT 1 FROM langganan_rekonsiliasi AS r "
            "              WHERE r.invoice_id = i.invoice_id AND substr(r.operasi_id, 1, 7) = 'create_') "
            "  AND NOT EXISTS (SELECT 1 FROM langganan_receipt AS c "
            "                  WHERE c.invoice_id = i.invoice_id) "
            "ORDER BY i.dibuat DESC, i.invoice_id DESC LIMIT ?", (_PERCOBAAN_MAKS,)).fetchall()
        for invoice_id, akun_id, kedaluwarsa in baris:
            if len(hasil) >= batas:
                break
            if kedaluwarsa < sekarang - horizon:
                continue
            terakhir = kon.execute(
                "SELECT MAX(diamati) FROM langganan_rekonsiliasi "
                "WHERE invoice_id = ? AND substr(operasi_id, 1, 4) = 'qry_'",
                (invoice_id,)).fetchone()[0]
            if terakhir is not None and terakhir > sekarang - jeda:
                continue
            hasil.append((invoice_id, akun_id))
    return hasil


def jalankan(path_admin, path_auth, path_db, *, config, transport, sekarang,
             sakelar=d.SAKELAR, batas=BATAS_BAWAAN, jeda=JEDA_BAWAAN,
             horizon=HORIZON_BAWAAN):
    """Satu putaran bounded; kembalikan ringkasan agregat tanpa identitas anak."""
    sakelar.wajib("rekonsiliasi")
    d.waktu(sekarang)
    ringkas = {"kandidat": 0, "lunas": 0, "menunggu": 0, "perlu_diperiksa": 0, "dilewati": 0}
    for invoice_id, akun_id in kandidat(path_admin, sekarang=sekarang, batas=batas,
                                       jeda=jeda, horizon=horizon):
        ringkas["kandidat"] += 1
        try:
            hasil = _satu(path_admin, path_auth, path_db, invoice_id, akun_id,
                          config=config, transport=transport, sekarang=sekarang, sakelar=sakelar)
        except (store.KonflikLangganan, LookupError, ValueError, d.FiturNonaktif):
            hasil = "dilewati"
        ringkas[hasil] += 1
    return ringkas


def _satu(path_admin, path_auth, path_db, invoice_id, akun_id, *, config, transport,
          sekarang, sakelar):
    inv, sidik = _snapshot(path_admin, path_auth, path_db, invoice_id, akun_id)
    if inv is None or sidik is None:
        return "dilewati"
    # Penanda percobaan durable sebelum jaringan: cooldown dan bukti upaya, bukan grant.
    store.catat_pengamatan(path_admin, akun_id, invoice_id, operasi_id=_operasi_percobaan(invoice_id, sekarang),
                           status="belum_terverifikasi", sekarang=sekarang, sakelar=sakelar)
    hasil = midtrans.periksa_status(config, inv, akun_id=akun_id, transport=transport, sakelar=sakelar)
    inv_baru, sidik_baru = _snapshot(path_admin, path_auth, path_db, invoice_id, akun_id)
    if inv_baru is None or sidik_baru is None or sidik_baru != sidik:
        # Owner/revisi/snapshot berubah selama jaringan: tanpa receipt/grant.
        return "dilewati"
    if hasil.bukti is not None:
        # Hasil ledger yang menentukan: settlement terlambat/receipt sudah ada tetap
        # perlu_diperiksa — kebijakan D8 (keputusan 26 Sep 2026) = tanpa grant
        # otomatis; koreksi (grant manual/refund) dilakukan admin lewat panel.
        ledger = store.terapkan_pembayaran(path_admin, akun_id, hasil.bukti, sekarang=sekarang,
                                           sakelar=sakelar)
        if ledger == "grant":
            _catat(path_admin, akun_id, invoice_id, "settlement", sekarang, sakelar)
            return "lunas"
        _catat(path_admin, akun_id, invoice_id, "perlu_diperiksa", sekarang, sakelar)
        return "perlu_diperiksa"
    if hasil.status == "perlu_diperiksa":
        _catat(path_admin, akun_id, invoice_id, "perlu_diperiksa", sekarang, sakelar)
        return "perlu_diperiksa"
    _catat(path_admin, akun_id, invoice_id, "belum_terverifikasi", sekarang, sakelar)
    return "menunggu"


def _catat(path_admin, akun_id, invoice_id, status, sekarang, sakelar):
    store.catat_pengamatan(path_admin, akun_id, invoice_id,
                           operasi_id=_operasi_amati(invoice_id, sekarang, status),
                           status=status, sekarang=sekarang, sakelar=sakelar)


def _operasi_percobaan(invoice_id, sekarang):
    bahan = "qry:" + invoice_id + ":" + str(sekarang)
    return "qry_" + hashlib.sha256(bahan.encode()).hexdigest()[:32]


def _operasi_amati(invoice_id, sekarang, status):
    bahan = invoice_id + ":" + str(sekarang) + ":" + status
    return "amati_" + hashlib.sha256(bahan.encode()).hexdigest()[:32]


def _snapshot(path_admin, path_auth, path_db, invoice_id, akun_id):
    """(invoice, sidik) untuk dibandingkan sebelum/sesudah jaringan; None = tidak layak."""
    try:
        inv = store.baca_invoice(path_admin, akun_id, invoice_id)
        akun = next((a for a in auth.muat_akun(path_auth) if a.get("id_akun") == akun_id), None)
        if akun is None or akun.get("peran") != "guru":
            return inv, None
        profil = tuple(json.loads(inv["profil_json"]))
        sidik_profil = []
        with admin_registration.kunci_database_pemilik(path_db) as kon:
            for profil_id in profil:
                baris = kon.execute("SELECT pemilik FROM siswa WHERE id=?", (profil_id,)).fetchone()
                if baris is None or baris[0] != akun.get("pengguna"):
                    return inv, None
                sidik_profil.append((profil_id, baris[0]))
        sidik = (auth.revisi_auth(akun), tuple(sidik_profil), inv["rupiah"], inv["merchant"],
                 inv["status"], inv["kedaluwarsa"])
        return inv, sidik
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError, ValueError, LookupError,
            TypeError, AttributeError):
        return None, None
