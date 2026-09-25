"""Reader dan quote checkout terjaga, tanpa konfigurasi jaringan atau hook akun."""

import json

import admin_store
import subscription as d
import subscription_service as layanan
import subscription_store as store


def ringkasan(path_admin, path_auth, path_db, principal, *, sakelar=d.SAKELAR):
    """GET tidak enrollment; snapshot ledger dibaca setelah principal hidup."""
    sakelar.wajib("fondasi")
    with layanan._keluarga(path_db, path_auth, principal) as (kon, akun, _):
        snapshot = store.baca(path_admin, akun["id_akun"])
        profil = tuple((r[0], r[1]) for r in kon.execute(
            "SELECT id,nama FROM siswa WHERE pemilik=? ORDER BY id", (akun["pengguna"],)))
        with admin_store.buka_baca(path_admin) as billing:
            terbaru = billing.execute(
                "SELECT invoice_id FROM langganan_invoice WHERE akun_id=? ORDER BY urutan DESC LIMIT 1",
                (akun["id_akun"],)).fetchone()
        invoice = (layanan._invoice_terjaga(path_admin, kon, akun, terbaru[0])
                   if terbaru else None)
        return snapshot, profil, invoice


def baca_tagihan(path_admin, path_auth, path_db, principal, invoice_id, *, sakelar=d.SAKELAR):
    sakelar.wajib("fondasi")
    with layanan._keluarga(path_db, path_auth, principal) as (kon, akun, _):
        inv = layanan._invoice_terjaga(path_admin, kon, akun, invoice_id)
        with admin_store.buka_baca(path_admin) as billing:
            inv["create_dicoba"] = bool(billing.execute(
                "SELECT 1 FROM langganan_rekonsiliasi WHERE operasi_id=? AND invoice_id=?",
                ("create_" + invoice_id[4:], invoice_id)).fetchone())
        return inv


def siapkan_tagihan(path_admin, path_auth, path_db, principal, profil, *, invoice_id,
                     operasi_id, merchant, sekarang, kedaluwarsa, sakelar=d.SAKELAR):
    """Cakupan+quote berserial di fencing keluarga; retry kembali invoice existing.

    Quote/cakupan masing-masing durable; crash di antaranya dipulihkan operasi sama.
    Invoice periode lain belum lunas tidak ditimpa oleh tombol/tab yang berbeda.
    """
    sakelar.wajib("fondasi")
    sakelar.wajib("buat_pembayaran")
    profil = d.profil_kanonis(profil)
    if not 1 <= len(profil) <= 3:
        raise ValueError("pilih satu sampai tiga profil")
    d.identitas(invoice_id, "invoice")
    d.identitas(operasi_id, "operasi")
    with layanan._keluarga(path_db, path_auth, principal) as (kon, akun, _):
        resolve = layanan._pemilik(kon, akun)
        if any(resolve(p) != akun["id_akun"] for p in profil):
            raise LookupError("resource tidak ditemukan")
        with admin_store.buka_baca(path_admin) as billing:
            # Retry token lama sesudah lunas tidak boleh membuat periode berikutnya.
            lama = billing.execute("SELECT invoice_id FROM langganan_invoice WHERE invoice_id=? AND akun_id=?",
                                   (invoice_id, akun["id_akun"])).fetchone()
            urutan = len(store._grants(billing, akun["id_akun"])) + 1
            berjalan = billing.execute("SELECT invoice_id FROM langganan_invoice WHERE akun_id=? AND urutan=?",
                                       (akun["id_akun"], urutan)).fetchone()
            revisi = billing.execute("SELECT MAX(revisi) FROM langganan_cakupan WHERE akun_id=? AND urutan=?",
                                    (akun["id_akun"], urutan)).fetchone()[0] or 0
            operasi = billing.execute("SELECT revisi FROM langganan_cakupan WHERE operasi_id=? AND akun_id=?",
                                      (operasi_id, akun["id_akun"])).fetchone()
        if lama or berjalan:
            inv = layanan._invoice_terjaga(path_admin, kon, akun, (lama or berjalan)[0])
            if tuple(json.loads(inv["profil_json"])) != profil or inv["merchant"] != merchant:
                raise store.KonflikLangganan("tagihan berbeda sudah dibekukan")
            return inv
        store.atur_cakupan(path_admin, akun["id_akun"], profil, operasi_id=operasi_id,
                          revisi=operasi[0] - 1 if operasi else revisi, sekarang=sekarang,
                          pemilik_profil=resolve, sakelar=sakelar)
        return store.buat_invoice(path_admin, akun["id_akun"], invoice_id=invoice_id,
                                  idempotency_key=operasi_id, provider="midtrans", channel="qris",
                                  merchant=merchant, sekarang=sekarang, kedaluwarsa=kedaluwarsa,
                                  sakelar=sakelar)
