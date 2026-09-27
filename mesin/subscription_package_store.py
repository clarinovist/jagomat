"""Ledger v2 di admin-control.db admin8; tidak mengaktifkan HTTP atau kampanye.

Seluruh writer berserial BEGIN IMMEDIATE melalui admin_store. Caller service
wajib memegang fencing principal/pemilik. Tidak membaca data belajar atau provider.
"""
from dataclasses import dataclass
import json

import admin_store
import subscription as d
import subscription_packages as p
import subscription_package_schema as schema
import subscription_store as lama


Konflik = lama.KonflikLangganan


def _wajib(kon):
    if not schema.tersedia(kon):
        raise admin_store.StoreBelumSiap("paket v2 belum dimigrasikan")


def _akun(kon, akun_id):
    _wajib(kon)
    d.identitas(akun_id, "akun")
    r = kon.execute("SELECT * FROM paket_akun WHERE akun_id=?", (akun_id,)).fetchone()
    if r is None:
        raise LookupError("langganan tidak ditemukan")
    return dict(r)


def memiliki_invoice(kon, invoice_id):
    return schema.tersedia(kon) and kon.execute(
        "SELECT 1 FROM paket_invoice WHERE invoice_id=?", (invoice_id,)).fetchone() is not None


def _invoice(kon, akun_id, invoice_id):
    _akun(kon, akun_id)
    d.identitas(invoice_id, "invoice")
    r = kon.execute("SELECT * FROM paket_invoice WHERE invoice_id=? AND akun_id=?",
                    (invoice_id, akun_id)).fetchone()
    if r is None:
        raise LookupError("invoice tidak ditemukan")
    return dict(r)


def _grants(kon, akun_id):
    return tuple(dict(r) for r in kon.execute(
        "SELECT g.*,i.paket,i.penagihan,i.profil_json,i.promo,i.balasan,i.foto "
        "FROM paket_grant g JOIN paket_invoice i ON i.invoice_id=g.invoice_id "
        "WHERE g.akun_id=? ORDER BY g.urutan", (akun_id,)))


def _batas_lama(kon, akun_id):
    e = lama._enrollment(kon, akun_id)
    gs = lama._grants(kon, akun_id)
    return max(e.akhir_trial, gs[-1].periode.akhir if gs else 0)


def _periode(kon, akun_id, invoice, sekarang, grants):
    batas = grants[-1]["akhir"] if grants else _batas_lama(kon, akun_id)
    mulai = max(sekarang, batas)
    bulan = p.jumlah_bulan(invoice["penagihan"])
    if grants and sekarang <= batas:
        terakhir = grants[-1]
        jangkar = terakhir["jangkar_mulai"]
        indeks = terakhir["indeks_bulan"] + p.jumlah_bulan(terakhir["penagihan"])
    else:
        jangkar, indeks = mulai, 0
    akhir = p.batas_bulan(jangkar, indeks + bulan)
    return mulai, akhir, jangkar, indeks


def validasi_ledger(kon, *, akun_id=None):
    """Snapshot, urutan, kepemilikan dan linkage lintas versi; tidak menulis DB."""
    _wajib(kon)
    for tabel in schema.TABEL:
        if kon.execute('PRAGMA foreign_key_check("' + tabel + '")').fetchone():
            raise Konflik("foreign key paket tidak sah")
    if akun_id is not None:
        d.identitas(akun_id, "akun")
    args = () if akun_id is None else (akun_id,)
    where = "" if akun_id is None else " WHERE akun_id=?"
    for row in kon.execute("SELECT * FROM paket_akun" + where, args):
        akun = dict(row)
        ident = akun["akun_id"]
        lama._enrollment(kon, ident)
        p.ambil_paket("jago", versi=akun["versi"])
        d.waktu(akun["mulai"])
        d.identitas(akun["operasi_id"], "operasi")
        if akun["kampanye"] is not None:
            lama._kode(akun["kampanye"])
        if kon.execute("SELECT 1 FROM langganan_invoice i WHERE i.akun_id=? "
                       "AND NOT EXISTS(SELECT 1 FROM langganan_grant g WHERE g.invoice_id=i.invoice_id)", (ident,)).fetchone():
            raise Konflik("tagihan lama belum selesai")
        invoices = tuple(dict(r) for r in kon.execute(
            "SELECT * FROM paket_invoice WHERE akun_id=? ORDER BY urutan", (ident,)))
        grants = _grants(kon, ident)
        if len(invoices) not in (len(grants), len(grants)+1):
            raise Konflik("urutan invoice paket tidak sah")
        for urutan, inv in enumerate(invoices, 1):
            profil = tuple(json.loads(inv["profil_json"]))
            harga = p.penawaran(inv["paket"], inv["penagihan"], len(profil),
                                peserta_promo=bool(akun["peserta_promo"]), periode_dibayar=urutan-1,
                                versi=inv["versi"])
            kuota = p.ambil_paket(inv["paket"]).kuota
            if (inv["urutan"] != urutan or not profil or d.profil_kanonis(profil) != profil
                    or len(profil) > 3 or inv["dibuat"] < akun["mulai"]
                    or inv["penagihan"] != invoices[0]["penagihan"]
                    or (inv["rupiah"], inv["normal"], bool(inv["promo"])) != (harga.rupiah, harga.normal, harga.promo)
                    or (inv["balasan"], inv["foto"]) != (kuota.balasan, kuota.foto)):
                raise Konflik("snapshot invoice paket tidak sah")
            d.identitas(inv["invoice_id"], "invoice")
            d.identitas(inv["idempotency_key"], "operasi")
            d.waktu(inv["dibuat"]); d.waktu(inv["kedaluwarsa"])
            for nilai in (inv["provider"], inv["merchant"]):
                lama._kode(nilai)
            if kon.execute("SELECT 1 FROM langganan_invoice WHERE invoice_id=? OR idempotency_key=?",
                           (inv["invoice_id"], inv["idempotency_key"])).fetchone():
                raise Konflik("identitas invoice lintas versi ganda")
        for r in kon.execute("SELECT * FROM paket_receipt WHERE akun_id=?", (ident,)):
            inv = _invoice(kon, ident, r["invoice_id"])
            g = kon.execute("SELECT * FROM paket_grant WHERE provider=? AND transaksi_id=?",
                            (r["provider"], r["transaksi_id"])).fetchone()
            d.waktu(r["diterima"])
            lama._kode(r["transaksi_id"])
            if (r["diterima"] < inv["dibuat"]
                    or (r["hasil"] == "grant" and r["diterima"] >= inv["kedaluwarsa"])
                    or r["provider"] != inv["provider"] or r["rupiah"] != inv["rupiah"]
                    or (r["hasil"] == "grant") != (g is not None)
                    or (g is not None and (g["invoice_id"], g["akun_id"]) != (inv["invoice_id"], ident))
                    or kon.execute("SELECT 1 FROM langganan_receipt WHERE provider=? AND transaksi_id=?",
                                   (r["provider"], r["transaksi_id"])).fetchone()):
                raise Konflik("receipt paket tidak sah")
        for i, g in enumerate(grants, 1):
            inv = _invoice(kon, ident, g["invoice_id"])
            r = kon.execute("SELECT * FROM paket_receipt WHERE provider=? AND transaksi_id=?",
                            (g["provider"], g["transaksi_id"])).fetchone()
            if (r is None or r["hasil"] != "grant" or r["invoice_id"] != g["invoice_id"]
                    or r["akun_id"] != ident or inv["urutan"] != i or g["urutan"] != i):
                raise Konflik("link grant paket tidak sah")
            tanggal = _periode(kon, ident, inv, r["diterima"], grants[:i-1])
            if tuple(g[k] for k in ("mulai", "akhir", "jangkar_mulai", "indeks_bulan")) != tanggal:
                raise Konflik("periode grant paket tidak sah")
        for r in kon.execute("SELECT r.* FROM paket_rekonsiliasi r JOIN paket_invoice i "
                             "ON i.invoice_id=r.invoice_id WHERE i.akun_id=?", (ident,)):
            inv = _invoice(kon, ident, r["invoice_id"])
            d.waktu(r["diamati"])
            if r["diamati"] < inv["dibuat"]:
                raise Konflik("clock pengamatan paket tidak sah")
            if r["rujukan"] is not None:
                sumber = kon.execute("SELECT invoice_id FROM paket_rekonsiliasi WHERE operasi_id=?",
                                      (r["rujukan"],)).fetchone()
                if sumber is None or sumber[0] != r["invoice_id"]:
                    raise Konflik("rujukan pengamatan paket berbeda")


def adopsi(path, akun_id, *, operasi_id, sekarang, peserta_promo=False, kampanye=None, sakelar=d.SAKELAR):
    """Metadata transisi eksplisit, tidak membuat/mengulang enrollment atau trial."""
    sakelar.wajib("fondasi")
    d.identitas(operasi_id, "operasi"); d.waktu(sekarang)
    if type(peserta_promo) is not bool or peserta_promo != (kampanye is not None):
        raise ValueError("metadata promo tidak sah")
    if kampanye is not None:
        lama._kode(kampanye)
    with admin_store._transaksi(path) as kon:
        _wajib(kon)
        e = lama._enrollment(kon, akun_id)
        if sekarang < e.mulai:
            raise ValueError("clock mendahului enrollment")
        lama.validasi_ledger(kon, akun_id=akun_id)
        ada = kon.execute("SELECT * FROM paket_akun WHERE akun_id=?", (akun_id,)).fetchone()
        if ada:
            if (ada["operasi_id"], bool(ada["peserta_promo"]), ada["kampanye"]) != (operasi_id, peserta_promo, kampanye):
                raise Konflik("transisi paket berbeda")
            return dict(ada)
        if kon.execute("SELECT 1 FROM langganan_invoice i WHERE i.akun_id=? AND NOT EXISTS "
                       "(SELECT 1 FROM langganan_grant g WHERE g.invoice_id=i.invoice_id)", (akun_id,)).fetchone():
            raise Konflik("tagihan lama belum selesai")
        kon.execute("INSERT INTO paket_akun VALUES(?,?,?,?,?,?)",
                    (akun_id, operasi_id, p.VERSI, sekarang, int(peserta_promo), kampanye))
        return _akun(kon, akun_id)


def buat_invoice(path, akun_id, profil, *, kode, penagihan, invoice_id, idempotency_key,
                 provider, merchant, sekarang, kedaluwarsa, pemilik_profil, sakelar=d.SAKELAR):
    sakelar.wajib("fondasi"); sakelar.wajib("buat_pembayaran")
    profil = d.profil_kanonis(profil)
    if not 1 <= len(profil) <= 3:
        raise ValueError("pilih satu sampai tiga profil")
    if not callable(pemilik_profil) or any(pemilik_profil(i) != akun_id for i in profil):
        raise LookupError("profil tidak ditemukan")
    d.identitas(invoice_id, "invoice"); d.identitas(idempotency_key, "operasi")
    d.waktu(sekarang); d.waktu(kedaluwarsa)
    p.ambil_paket(kode); p.jumlah_bulan(penagihan)
    lama._kode(provider); lama._kode(merchant)
    if kedaluwarsa <= sekarang:
        raise ValueError("deadline invoice tidak sah")
    serial = json.dumps(profil, separators=(",", ":"))
    with admin_store._transaksi(path) as kon:
        akun = _akun(kon, akun_id)
        lama.validasi_ledger(kon, akun_id=akun_id)
        if sekarang < akun["mulai"]:
            raise ValueError("clock mendahului transisi")
        ada = kon.execute("SELECT * FROM paket_invoice WHERE invoice_id=?", (invoice_id,)).fetchone()
        if ada:
            if tuple(ada[k] for k in ("akun_id", "paket", "penagihan", "profil_json", "idempotency_key", "provider", "merchant", "kedaluwarsa")) != (akun_id, kode, penagihan, serial, idempotency_key, provider, merchant, kedaluwarsa):
                raise Konflik("snapshot invoice paket berbeda")
            return dict(ada)
        if kon.execute("SELECT 1 FROM langganan_invoice WHERE invoice_id=? OR idempotency_key=?",
                       (invoice_id, idempotency_key)).fetchone():
            raise Konflik("identitas invoice lintas versi ganda")
        terakhir = kon.execute("SELECT penagihan FROM paket_invoice WHERE akun_id=? LIMIT 1", (akun_id,)).fetchone()
        if terakhir and terakhir[0] != penagihan:
            raise Konflik("perubahan periode belum tersedia")
        dibayar = len(_grants(kon, akun_id))
        if kon.execute("SELECT 1 FROM paket_invoice WHERE akun_id=? AND urutan=?", (akun_id, dibayar+1)).fetchone():
            raise Konflik("tagihan periode sudah dibekukan")
        h = p.penawaran(kode, penagihan, len(profil), peserta_promo=bool(akun["peserta_promo"]), periode_dibayar=dibayar)
        kuota = p.ambil_paket(kode).kuota
        kon.execute("INSERT INTO paket_invoice VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (invoice_id, akun_id, dibayar+1, h.versi, kode, penagihan, serial, int(h.promo),
                     h.rupiah, h.normal, kuota.balasan, kuota.foto, "IDR", provider, "qris", merchant,
                     idempotency_key, sekarang, kedaluwarsa, "termasuk_bila_berlaku"))
        return _invoice(kon, akun_id, invoice_id)


def terapkan(kon, akun_id, bukti, *, sekarang, failpoint=None):
    """Dipanggil dispatcher v1 di transaksi/guard yang sama; grant tepat sekali."""
    inv = _invoice(kon, akun_id, bukti.invoice_id)
    if not d.pembayaran_cocok(bukti, inv, akun_id):
        raise Konflik("bukti pembayaran tidak cocok")
    if sekarang < inv["dibuat"]:
        raise ValueError("clock mendahului invoice")
    lama.validasi_ledger(kon, akun_id=akun_id)
    if kon.execute("SELECT 1 FROM langganan_receipt WHERE provider=? AND transaksi_id=?",
                   (bukti.provider, bukti.transaksi_id)).fetchone():
        raise Konflik("sumber pembayaran lintas versi telah dipakai")
    ada = kon.execute("SELECT * FROM paket_receipt WHERE provider=? AND transaksi_id=?",
                      (bukti.provider, bukti.transaksi_id)).fetchone()
    if ada:
        if (ada["invoice_id"], ada["akun_id"], ada["rupiah"]) != (bukti.invoice_id, akun_id, bukti.rupiah):
            raise Konflik("sumber pembayaran telah dipakai")
        return ada["hasil"]
    grants = _grants(kon, akun_id)
    sudah = any(g["invoice_id"] == inv["invoice_id"] for g in grants)
    hasil = "perlu_diperiksa" if sudah or sekarang >= inv["kedaluwarsa"] else "grant"
    kon.execute("INSERT INTO paket_receipt VALUES(?,?,?,?,?,?,?)",
                (bukti.provider, bukti.transaksi_id, inv["invoice_id"], akun_id, bukti.rupiah, sekarang, hasil))
    if failpoint == "setelah_receipt":
        raise RuntimeError("crash sintetis setelah receipt")
    if hasil == "grant":
        if inv["urutan"] != len(grants)+1:
            raise Konflik("urutan periode tidak cocok")
        tanggal = _periode(kon, akun_id, inv, sekarang, grants)
        kon.execute("INSERT INTO paket_grant VALUES(?,?,?,?,?,?,?,?,?)",
                    (inv["invoice_id"], akun_id, inv["urutan"], bukti.provider, bukti.transaksi_id, *tanggal))
    return hasil


@dataclass(frozen=True)
class Snapshot:
    akun: dict
    grants: tuple


def baca(path, akun_id):
    with admin_store.buka_baca(path) as kon:
        kon.execute("BEGIN")
        akun = _akun(kon, akun_id)
        lama.validasi_ledger(kon, akun_id=akun_id)
        return Snapshot(akun, _grants(kon, akun_id))
