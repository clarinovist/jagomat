"""Orkestrasi langganan terisolasi; tidak didispatch web/startup/scheduler.

Urutan fencing DB belajar→auth→ledger, sama dengan operasi profil existing.
Transport selalu di luar lock. Tidak menulis auth/bukti belajar, tidak memulai trial
saat login, tidak membaca credential provider dari env, dan tidak punya HTTP route.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import re

import admin_accounts
import admin_registration
import admin_store
import auth
from json_storage import transaksi_json
import midtrans_contract as midtrans
import subscription as d
import subscription_store as store


@dataclass(frozen=True)
class HasilPembayaran:
    status: str
    hasil_ledger: str = ""


class SinkronBelumSelesai(RuntimeError):
    """Receipt sumber tetap durable; retry exact sumber, bukan buat akun baru."""


def _principal(daftar, principal):
    if not isinstance(principal, auth.PrincipalAkun):
        raise LookupError("resource tidak ditemukan")
    akun = next((a for a in daftar if a.get("id_akun") == principal.id_akun), None)
    if (akun is None or principal.peran != "guru" or akun.get("peran") != "guru"
            or auth.revisi_auth(akun) != principal.revisi_auth
            or akun["pengguna"] != principal.pengguna):
        raise LookupError("resource tidak ditemukan")
    return akun


def _receipt(mentah, sumber_id, akun_id, *, cutoff, sekarang):
    """Baca receipt sukses actual, bukan DTO bebas berisi timestamp dari form."""
    daftar = mentah.get("operasi_registrasi", {})
    if type(daftar) is not dict:
        raise ValueError("receipt registrasi tidak sah")
    for key, r in daftar.items():
        if (type(r) is not dict or set(r) != admin_registration._RECEIPT_PUBLIC_FIELDS
                or r.get("operasi_id") != key or type(r.get("versi")) is not int or r["versi"] != 1
                or r.get("hasil_kode") != "teacher_created" or type(r.get("revisi_hasil")) is not int or r["revisi_hasil"] != 1
                or not auth.id_akun_sah(r.get("hasil_id"))
                or type(r.get("dibuat")) is not int or not 0 <= r["dibuat"] <= sekarang
                or type(r.get("target_id")) is not str or re.fullmatch(r"candidate_[0-9a-f]{32}", r["target_id"]) is None
                or type(r.get("sidik_perintah")) is not str or re.fullmatch(r"[0-9a-f]{64}", r["sidik_perintah"]) is None):
            raise ValueError("receipt registrasi tidak sah")
        d.identitas(key, "operasi")
    r = daftar.get(sumber_id)
    if r is None or r["hasil_id"] != akun_id or r["dibuat"] < cutoff:
        raise LookupError("resource tidak ditemukan")
    if sum(item["hasil_id"] == r["hasil_id"] for item in daftar.values()) != 1:
        raise ValueError("receipt akun ambigu")
    return r, daftar


@contextmanager
def _keluarga(path_db, path_auth, principal):
    # Fencing read, rollback tanpa perubahan belajar. Bukan reader GET publik.
    with admin_registration.kunci_database_pemilik(path_db) as kon:
        with transaksi_json(path_auth) as tujuan:
            mentah, daftar, _ = admin_accounts._baca_state_terkunci(tujuan)
            akun = _principal(daftar, principal)
            yield kon, akun, mentah


def _pemilik(kon, akun):
    def resolve(profil_id):
        row = kon.execute("SELECT pemilik FROM siswa WHERE id=?", (profil_id,)).fetchone()
        return akun["id_akun"] if row and row[0] == akun["pengguna"] else None
    return resolve


def sinkron_pendaftaran(path_admin, path_auth, path_db, principal, *, sumber_id,
                        cutoff, sekarang, sakelar=d.SAKELAR):
    """Rekonsiliasi exact receipt setelah commit; cutoff aktivasi wajib eksplisit."""
    sakelar.wajib("fondasi")
    d.waktu(cutoff)
    d.waktu(sekarang)
    d.identitas(sumber_id, "operasi")
    with _keluarga(path_db, path_auth, principal) as (_, akun, mentah):
        receipt, semua = _receipt(mentah, sumber_id, akun["id_akun"], cutoff=cutoff, sekarang=sekarang)
        with admin_store.buka_baca(path_admin) as kon:
            kampanye = kon.execute("SELECT mulai,akhir FROM langganan_kampanye").fetchone()
        peringkat = None
        if kampanye and kampanye[0] <= receipt["dibuat"] < kampanye[1]:
            urutan = sorted((r["dibuat"], key) for key, r in semua.items()
                            if kampanye[0] <= r["dibuat"] < kampanye[1])
            peringkat = urutan.index((receipt["dibuat"], sumber_id)) + 1
        return store.enroll(path_admin, akun["id_akun"], sumber_id=sumber_id,
                            asal="publik", mulai=receipt["dibuat"], peran="guru",
                            urutan_publik=peringkat, sakelar=sakelar)


def atur_cakupan(path_admin, path_auth, path_db, principal, profil, *, operasi_id,
                 revisi, sekarang, sakelar=d.SAKELAR):
    sakelar.wajib("fondasi")
    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):
        return store.atur_cakupan(path_admin, akun["id_akun"], profil, operasi_id=operasi_id,
                                 revisi=revisi, sekarang=sekarang, pemilik_profil=_pemilik(kon, akun), sakelar=sakelar)


def buat_invoice(path_admin, path_auth, path_db, principal, *, invoice_id, idempotency_key,
                 merchant, sekarang, kedaluwarsa, sakelar=d.SAKELAR):
    sakelar.wajib("buat_pembayaran")
    sakelar.wajib("fondasi")
    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):
        # Sebelum commit quote, cakupan terbaru dicek kembali di fencing yang sama.
        with admin_store.buka_baca(path_admin) as billing:
            snapshot = store._grants(billing, akun["id_akun"])
            cakupan = billing.execute("SELECT profil_json FROM langganan_cakupan WHERE akun_id=? AND urutan<=? ORDER BY urutan DESC,revisi DESC LIMIT 1",
                                      (akun["id_akun"], len(snapshot)+1)).fetchone()
        if cakupan is None:
            raise LookupError("resource tidak ditemukan")
        resolve = _pemilik(kon, akun)
        if any(resolve(p) != akun["id_akun"] for p in json.loads(cakupan[0])):
            raise LookupError("resource tidak ditemukan")
        return store.buat_invoice(path_admin, akun["id_akun"], invoice_id=invoice_id,
                                 idempotency_key=idempotency_key, provider="midtrans", channel="qris",
                                 merchant=merchant, sekarang=sekarang, kedaluwarsa=kedaluwarsa, sakelar=sakelar)


def _invoice_terjaga(path_admin, kon, akun, invoice_id):
    inv = store.baca_invoice(path_admin, akun["id_akun"], invoice_id)
    resolve = _pemilik(kon, akun)
    if any(resolve(p) != akun["id_akun"] for p in json.loads(inv["profil_json"])):
        raise LookupError("resource tidak ditemukan")
    return inv


def _catat(path_admin, path_auth, path_db, principal, inv, hasil, sekarang, sakelar, failpoint, cek_sesi):
    # Recheck setelah jaringan: reset, delete/recreate alias, perubahan owner tidak
    # boleh menerapkan grant memakai snapshot principal sebelum transport.
    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):
        _invoice_terjaga(path_admin, kon, akun, inv["invoice_id"])
        if cek_sesi is not None:
            cek_sesi()
        ledger = ""
        if hasil.bukti is not None:
            ledger = store.terapkan_pembayaran(path_admin, akun["id_akun"], hasil.bukti,
                                               sekarang=sekarang, sakelar=sakelar, failpoint=failpoint)
        status = "settlement" if hasil.bukti is not None else ("perlu_diperiksa" if hasil.status == "perlu_diperiksa" else "belum_terverifikasi")
        # Identitas pengamatan bounded/deterministik; payload mentah tidak disimpan.
        bahan = inv["invoice_id"] + ":" + str(sekarang) + ":" + status
        operasi = "amati_" + hashlib.sha256(bahan.encode()).hexdigest()[:32]
        store.catat_pengamatan(path_admin, akun["id_akun"], inv["invoice_id"], operasi_id=operasi,
                              status=status, sekarang=sekarang, sakelar=sakelar)
        # Pending tidak pernah menurunkan receipt yang sudah committed.
        akhir = store.baca_invoice(path_admin, akun["id_akun"], inv["invoice_id"])
        return HasilPembayaran(akhir["status"], ledger)


def periksa_pembayaran(path_admin, path_auth, path_db, principal, invoice_id, *, config,
                       transport, sekarang, sakelar=d.SAKELAR, failpoint=None, cek_sesi=None):
    sakelar.wajib("rekonsiliasi")
    d.waktu(sekarang)
    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):
        inv = _invoice_terjaga(path_admin, kon, akun, invoice_id)
        if inv["merchant"] != config.merchant or sekarang < inv["dibuat"]:
            raise ValueError("merchant/clock berbeda")
    hasil = midtrans.periksa_status(config, inv, akun_id=principal.id_akun, transport=transport, sakelar=sakelar)
    return _catat(path_admin, path_auth, path_db, principal, inv, hasil, sekarang, sakelar, failpoint, cek_sesi)


def mulai_pembayaran(path_admin, path_auth, path_db, principal, invoice_id, *, config,
                     transport, sekarang, sakelar=d.SAKELAR, failpoint=None, cek_sesi=None):
    sakelar.wajib("buat_pembayaran")
    sakelar.wajib("rekonsiliasi")
    d.waktu(sekarang)
    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):
        inv = _invoice_terjaga(path_admin, kon, akun, invoice_id)
        if inv["merchant"] != config.merchant:
            raise ValueError("merchant berbeda")
        baru = store.reservasi_create(path_admin, akun["id_akun"], invoice_id, sekarang=sekarang, sakelar=sakelar)
    if failpoint == "setelah_intent":
        raise SinkronBelumSelesai("intent committed; periksa order yang sama")
    if baru:
        # Create hanya satu kali; hasil create tidak boleh menjadi bukti bayar.
        midtrans.buat_pembayaran(config, inv, akun_id=principal.id_akun, transport=transport, sakelar=sakelar)
    return periksa_pembayaran(path_admin, path_auth, path_db, principal, invoice_id,
                             config=config, transport=transport, sekarang=sekarang, sakelar=sakelar, failpoint=failpoint, cek_sesi=cek_sesi)
