"""Ledger langganan di admin-control.db, tanpa hook HTTP/auth atau jaringan.

Caller masa depan wajib memberi ID akun/profil hasil otorisasi, bukan input form.
Sakelar diinjeksi eksplisit untuk pengujian. Tidak ada pembacaan env/akun, bootstrap
terselubung, atau transaksi lintas DB. D8 belum diputuskan: kasus terlambat/lebih
hanya disimpan untuk pemeriksaan, tanpa refund/revoke atau grant tambahan.
"""

from dataclasses import dataclass
import json
import re
import sqlite3
from typing import Tuple

import admin_store
import subscription as d


class KonflikLangganan(ValueError):
    """Identitas/revisi/snapshot tidak cocok; transaksi dibatalkan."""


@dataclass(frozen=True)
class Snapshot:
    enrollment: d.Enrollment
    grants: Tuple[d.Grant, ...]


def _kode(nilai):
    if type(nilai) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", nilai) is None:
        raise ValueError("referensi billing tidak sah")
    return nilai


def _enrollment(kon, akun_id):
    d.identitas(akun_id, "akun")
    row = kon.execute("SELECT * FROM langganan_enrollment WHERE akun_id=?", (akun_id,)).fetchone()
    if row is None:
        raise LookupError("langganan tidak ditemukan")
    return d.Enrollment(row["akun_id"], row["mulai"], bool(row["peserta_promo"]), row["versi"])


def _grants(kon, akun_id):
    return tuple(d.Grant(r["akun_id"], r["invoice_id"], r["urutan"],
                         d.Periode(r["mulai"], r["akhir"], r["jangkar"]),
                         tuple(json.loads(r["profil_json"])), bool(r["promo"]))
                 for r in kon.execute("SELECT * FROM langganan_grant WHERE akun_id=? ORDER BY urutan", (akun_id,)))


def validasi_ledger(kon, *, akun_id=None):
    """Periksa linkage snapshot/receipt/grant setelah restore, tanpa menulis data."""
    args = () if akun_id is None else (akun_id,)
    where = "" if akun_id is None else " WHERE akun_id=?"
    for row in kon.execute("SELECT akun_id FROM langganan_enrollment" + where, args):
        akun = row[0]
        enrollment = _enrollment(kon, akun)
        grants = _grants(kon, akun)
        if d.akses(enrollment, grants, sekarang=enrollment.mulai).status == "belum_terverifikasi":
            raise KonflikLangganan("urutan ledger tidak sah")
        for inv in kon.execute("SELECT * FROM langganan_invoice WHERE akun_id=?", (akun,)):
            cakupan = kon.execute("SELECT * FROM langganan_cakupan WHERE operasi_id=?", (inv["cakupan_id"],)).fetchone()
            profil = tuple(json.loads(inv["profil_json"]))
            if (cakupan is None or cakupan["akun_id"] != akun or cakupan["urutan"] > inv["urutan"]
                    or cakupan["profil_json"] != inv["profil_json"] or d.profil_kanonis(profil) != profil
                    or inv["versi"] != enrollment.versi
                    or bool(inv["promo"]) != (enrollment.peserta_promo and inv["urutan"] <= 3)
                    or inv["rupiah"] != d.harga(len(profil), peserta_promo=enrollment.peserta_promo, periode_dibayar=inv["urutan"]-1)):
                raise KonflikLangganan("snapshot invoice tidak sah")
        for r in kon.execute("SELECT * FROM langganan_receipt WHERE akun_id=?", (akun,)):
            inv = _invoice(kon, akun, r["invoice_id"])
            grant = kon.execute("SELECT * FROM langganan_grant WHERE provider=? AND transaksi_id=?", (r["provider"],r["transaksi_id"])).fetchone()
            if (r["rupiah"] != inv["rupiah"] or r["provider"] != inv["provider"]
                    or (r["hasil"] == "grant") != (grant is not None)):
                raise KonflikLangganan("receipt ledger tidak sah")
        for g in kon.execute("SELECT * FROM langganan_grant WHERE akun_id=?", (akun,)):
            inv = _invoice(kon, akun, g["invoice_id"])
            r = kon.execute("SELECT * FROM langganan_receipt WHERE provider=? AND transaksi_id=?", (g["provider"],g["transaksi_id"])).fetchone()
            if (r is None or r["akun_id"] != akun or r["invoice_id"] != g["invoice_id"] or r["hasil"] != "grant"
                    or g["urutan"] != inv["urutan"] or g["profil_json"] != inv["profil_json"] or g["promo"] != inv["promo"]
                    or g["akhir"] != d.bulan_berikutnya(g["mulai"], g["jangkar"])):
                raise KonflikLangganan("grant ledger tidak sah")


def baca(path, akun_id):
    """Missing/schema lama gagal jujur; tidak membuat DB/tabel/enrollment."""
    with admin_store.buka_baca(path) as kon:
        kon.execute("BEGIN")  # Snapshot konsisten lintas query reader.
        enrollment = _enrollment(kon, akun_id)
        validasi_ledger(kon, akun_id=akun_id)
        return Snapshot(enrollment, _grants(kon, akun_id))


def _invoice(kon, akun_id, invoice_id):
    d.identitas(akun_id, "akun")
    d.identitas(invoice_id, "invoice")
    row = kon.execute("SELECT * FROM langganan_invoice WHERE invoice_id=? AND akun_id=?",
                      (invoice_id, akun_id)).fetchone()
    if row is None:
        raise LookupError("invoice tidak ditemukan")
    return dict(row)


def baca_invoice(path, akun_id, invoice_id):
    with admin_store.buka_baca(path) as kon:
        kon.execute("BEGIN")
        hasil = _invoice(kon, akun_id, invoice_id)
        validasi_ledger(kon, akun_id=akun_id)
        lunas = kon.execute("SELECT 1 FROM langganan_receipt WHERE invoice_id=?", (invoice_id,)).fetchone()
        hasil["status"] = "lunas" if lunas else "belum_terverifikasi"
        hasil["perlu_diperiksa"] = bool(kon.execute(
            "SELECT 1 FROM langganan_receipt WHERE invoice_id=? AND hasil='perlu_diperiksa'", (invoice_id,)).fetchone())
        return hasil


def buat_kampanye(path, kampanye_id, *, mulai, sakelar=d.SAKELAR):
    sakelar.wajib("fondasi")
    _kode(kampanye_id)
    d.waktu(mulai)
    akhir = d.waktu(mulai + d.DURASI_KAMPANYE)
    with admin_store._transaksi(path) as kon:
        lama = kon.execute("SELECT * FROM langganan_kampanye").fetchall()
        if lama:
            if len(lama) != 1 or tuple(lama[0]) != (kampanye_id, mulai, akhir, 100):
                raise KonflikLangganan("kampanye telah dibekukan")
            return
        kon.execute("INSERT INTO langganan_kampanye VALUES(?,?,?,100)", (kampanye_id, mulai, akhir))


def enroll(path, akun_id, *, sumber_id, asal, mulai, peran, internal=False,
           promo_lama=False, sakelar=d.SAKELAR):
    """Terima metadata keberhasilan publik/transisi eksplisit; belum ada adapter live."""
    sakelar.wajib("fondasi")
    d.identitas(akun_id, "akun")
    d.identitas(sumber_id, "operasi")
    d.waktu(mulai)
    d.waktu(mulai + d.DURASI_TRIAL)
    if (peran != "guru" or internal is not False or asal not in ("publik", "transisi")
            or type(promo_lama) is not bool or (asal == "publik" and promo_lama)):
        raise ValueError("akun tidak eligible enrollment")
    with admin_store._transaksi(path) as kon:
        lama = kon.execute("SELECT * FROM langganan_enrollment WHERE akun_id=?", (akun_id,)).fetchone()
        if lama:
            if (lama["sumber_id"], lama["asal"], lama["mulai"]) != (sumber_id, asal, mulai):
                raise KonflikLangganan("enrollment telah dibekukan")
            if asal == "transisi" and bool(lama["peserta_promo"]) != promo_lama:
                raise KonflikLangganan("eligibility telah dibekukan")
            return _enrollment(kon, akun_id)
        kampanye = kon.execute("SELECT * FROM langganan_kampanye WHERE mulai<=? AND ?<akhir", (mulai, mulai)).fetchone()
        promo, kampanye_id = promo_lama, None
        if asal == "publik" and kampanye:
            kampanye_id = kampanye["kampanye_id"]
            jumlah = kon.execute("SELECT COUNT(*) FROM langganan_enrollment WHERE asal='publik' AND peserta_promo=1 AND kampanye_id=?", (kampanye_id,)).fetchone()[0]
            promo = jumlah < kampanye["kuota"]
        try:
            kon.execute("INSERT INTO langganan_enrollment VALUES(?,?,?,?,?,?,?)",
                        (akun_id, sumber_id, asal, mulai, int(promo), kampanye_id, d.VERSI_ATURAN))
        except sqlite3.IntegrityError:
            raise KonflikLangganan("sumber enrollment telah dipakai") from None
        return _enrollment(kon, akun_id)


def atur_cakupan(path, akun_id, profil, *, operasi_id, revisi, sekarang,
                 pemilik_profil=None, sakelar=d.SAKELAR):
    """Resolver terjaga diinjeksi; belum ada adapter DB belajar/lintas-store live."""
    sakelar.wajib("fondasi")
    d.identitas(operasi_id, "operasi")
    profil = d.profil_kanonis(profil)
    if not callable(pemilik_profil) or any(pemilik_profil(p) != akun_id for p in profil):
        raise LookupError("profil tidak ditemukan")
    d.bilangan(revisi)
    d.waktu(sekarang)
    serial = json.dumps(profil, separators=(",", ":"))
    with admin_store._transaksi(path) as kon:
        enrollment = _enrollment(kon, akun_id)
        if sekarang < enrollment.mulai:
            raise ValueError("clock mendahului enrollment")
        lama = kon.execute("SELECT * FROM langganan_cakupan WHERE operasi_id=?", (operasi_id,)).fetchone()
        if lama:
            if (lama["akun_id"], lama["profil_json"], lama["revisi"]) != (akun_id, serial, revisi + 1):
                raise KonflikLangganan("retry cakupan berbeda")
            return lama["urutan"]
        # Pembayaran di muka/quote aktif: jangan memilih efek tanggal diam-diam.
        urutan = len(_grants(kon, akun_id)) + 1
        if kon.execute("SELECT 1 FROM langganan_invoice WHERE akun_id=? AND urutan=?", (akun_id, urutan)).fetchone():
            raise KonflikLangganan("periode sudah dibekukan; rekonsiliasi quote diperlukan")
        terakhir = kon.execute("SELECT MAX(revisi) FROM langganan_cakupan WHERE akun_id=? AND urutan=?", (akun_id, urutan)).fetchone()[0] or 0
        if revisi != terakhir:
            raise KonflikLangganan("revisi cakupan stale")
        kon.execute("INSERT INTO langganan_cakupan VALUES(?,?,?,?,?,?)",
                    (operasi_id, akun_id, urutan, revisi + 1, serial, sekarang))
        return urutan


def buat_invoice(path, akun_id, *, invoice_id, idempotency_key, provider, channel,
                 merchant, sekarang, kedaluwarsa, sakelar=d.SAKELAR):
    """Snapshot internal sintetis; bukan checkout pajak final atau create provider."""
    sakelar.wajib("buat_pembayaran")
    sakelar.wajib("fondasi")
    d.identitas(invoice_id, "invoice")
    d.identitas(idempotency_key, "operasi")
    for nilai in (provider, channel, merchant):
        _kode(nilai)
    d.waktu(sekarang)
    d.waktu(kedaluwarsa)
    if kedaluwarsa <= sekarang:
        raise ValueError("deadline invoice tidak sah")
    with admin_store._transaksi(path) as kon:
        enrollment = _enrollment(kon, akun_id)
        if sekarang < enrollment.mulai:
            raise ValueError("clock mendahului enrollment")
        lama = kon.execute("SELECT * FROM langganan_invoice WHERE invoice_id=?", (invoice_id,)).fetchone()
        if lama:
            if (lama["akun_id"], lama["idempotency_key"], lama["provider"], lama["channel"], lama["merchant"], lama["kedaluwarsa"]) != (akun_id, idempotency_key, provider, channel, merchant, kedaluwarsa):
                raise KonflikLangganan("snapshot invoice berbeda")
            return dict(lama)
        validasi_ledger(kon, akun_id=akun_id)
        dibayar = len(_grants(kon, akun_id))
        cakupan = kon.execute("SELECT * FROM langganan_cakupan WHERE akun_id=? AND urutan<=? ORDER BY urutan DESC,revisi DESC LIMIT 1", (akun_id, dibayar + 1)).fetchone()
        if cakupan is None:
            raise ValueError("cakupan belum dipilih")
        jumlah = len(json.loads(cakupan["profil_json"]))
        rupiah = d.harga(jumlah, peserta_promo=enrollment.peserta_promo, periode_dibayar=dibayar)
        try:
            kon.execute("INSERT INTO langganan_invoice VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
                        (invoice_id, akun_id, dibayar + 1, enrollment.versi, cakupan["operasi_id"],
                         cakupan["profil_json"], int(enrollment.peserta_promo and dibayar < 3),
                         rupiah, "IDR", provider, channel, merchant, idempotency_key,
                         sekarang, kedaluwarsa, "belum_ditetapkan"))
        except sqlite3.IntegrityError:
            raise KonflikLangganan("invoice periode atau key sudah ada") from None
        return _invoice(kon, akun_id, invoice_id)


def catat_pengamatan(path, akun_id, invoice_id, *, operasi_id, status, sekarang,
                     rujukan=None, sakelar=d.SAKELAR):
    sakelar.wajib("rekonsiliasi")
    d.identitas(operasi_id, "operasi")
    d.waktu(sekarang)
    if status not in ("belum_terverifikasi", "perlu_diperiksa", "settlement"):
        raise ValueError("status rekonsiliasi tidak sah")
    with admin_store._transaksi(path) as kon:
        _invoice(kon, akun_id, invoice_id)
        if rujukan is not None:
            sumber = kon.execute("SELECT invoice_id FROM langganan_rekonsiliasi WHERE operasi_id=?", (rujukan,)).fetchone()
            if sumber is None or sumber[0] != invoice_id:
                raise KonflikLangganan("rujukan rekonsiliasi berbeda")
        lama = kon.execute("SELECT * FROM langganan_rekonsiliasi WHERE operasi_id=?", (operasi_id,)).fetchone()
        if lama:
            if (lama["invoice_id"], lama["status"], lama["rujukan"]) != (invoice_id, status, rujukan):
                raise KonflikLangganan("pengamatan berbeda")
            return
        kon.execute("INSERT INTO langganan_rekonsiliasi VALUES(?,?,?,?,?)",
                    (operasi_id, invoice_id, status, sekarang, rujukan))


def terapkan_pembayaran(path, akun_id, bukti, *, sekarang, sakelar=d.SAKELAR, failpoint=None):
    """Receipt/grant/promo satu transaksi; callback mentah tidak diterima di sini."""
    sakelar.wajib("rekonsiliasi")
    d.waktu(sekarang)
    _kode(bukti.transaksi_id)
    with admin_store._transaksi(path) as kon:
        invoice = _invoice(kon, akun_id, bukti.invoice_id)
        if not d.pembayaran_cocok(bukti, invoice, akun_id):
            raise KonflikLangganan("bukti pembayaran tidak cocok")
        if sekarang < invoice["dibuat"]:
            raise ValueError("clock mendahului invoice")
        validasi_ledger(kon, akun_id=akun_id)
        lama = kon.execute("SELECT * FROM langganan_receipt WHERE provider=? AND transaksi_id=?",
                           (bukti.provider, bukti.transaksi_id)).fetchone()
        if lama is not None:
            if (lama["invoice_id"], lama["akun_id"], lama["rupiah"]) != (bukti.invoice_id, akun_id, bukti.rupiah):
                raise KonflikLangganan("sumber pembayaran telah dipakai")
            return lama["hasil"]
        enrollment = _enrollment(kon, akun_id)
        grants = _grants(kon, akun_id)
        sudah = kon.execute("SELECT 1 FROM langganan_grant WHERE invoice_id=?", (bukti.invoice_id,)).fetchone()
        hasil = "perlu_diperiksa" if sudah or sekarang >= invoice["kedaluwarsa"] else "grant"
        kon.execute("INSERT INTO langganan_receipt VALUES(?,?,?,?,?,?,?)",
                    (bukti.provider, bukti.transaksi_id, bukti.invoice_id, akun_id, bukti.rupiah, sekarang, hasil))
        if failpoint == "setelah_receipt":
            raise RuntimeError("crash sintetis setelah receipt")
        if hasil == "grant":
            if invoice["urutan"] != len(grants) + 1:
                raise KonflikLangganan("urutan periode tidak cocok")
            periode = d.periode_baru(sekarang=sekarang, enrollment=enrollment,
                                     sebelumnya=grants[-1].periode if grants else None)
            kon.execute("INSERT INTO langganan_grant VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (bukti.invoice_id, akun_id, invoice["urutan"], bukti.provider, bukti.transaksi_id,
                         periode.mulai, periode.akhir, periode.jangkar, invoice["profil_json"], invoice["promo"]))
        return hasil
