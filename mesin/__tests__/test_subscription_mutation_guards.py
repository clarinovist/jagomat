"""Lapisan UNIQUE tetap melindungi periode meski jalur REPLACE tidak digunakan."""
import sqlite3

import pytest
from test_subscription_store import ledger, invoice, bukti, AKUN, ON, T0
import subscription_store as s


def test_unique_receipt_sumber_sql():
    import subscription_schema
    kon = sqlite3.connect(':memory:')
    try:
        # Isolasi indeks dari FK/trigger agar mutasi diuji oleh INSERT duplikat,
        # bukan gagal karena FK fixture saat bootstrap. Tidak ada file pengguna.
        kon.executescript(subscription_schema.DDL)
        kon.execute('DROP TRIGGER langganan_receipt_tolak_replace')
        kon.execute("INSERT INTO langganan_receipt VALUES('fake','trx','inv',?,15000,1,'grant')", (AKUN,))
        with pytest.raises(sqlite3.IntegrityError, match='UNIQUE constraint failed: langganan_receipt.provider, langganan_receipt.transaksi_id'):
            kon.execute('INSERT INTO langganan_receipt SELECT * FROM langganan_receipt')
    finally:
        kon.close()


def test_unique_grant_periode_sql(ledger):
    inv = invoice(ledger)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    kedua = invoice(ledger, 2, T0+2)
    with sqlite3.connect(ledger) as kon:
        kon.execute("PRAGMA foreign_keys=ON")
        # Isolasi lapisan UNIQUE dari trigger REPLACE, pada DB temp sintetis saja.
        kon.execute("DROP TRIGGER langganan_grant_tolak_replace")
        kon.execute("INSERT INTO langganan_receipt VALUES(?,?,?,?,?,?,?)",
                    ("midtrans", "trx_kedua", kedua["invoice_id"], AKUN, kedua["rupiah"], T0+3, "grant"))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed: langganan_grant.akun_id, langganan_grant.urutan"):
            kon.execute("INSERT INTO langganan_grant SELECT ?,akun_id,urutan,provider,?,mulai,akhir,jangkar,profil_json,promo FROM langganan_grant",
                        (kedua["invoice_id"], "trx_kedua"))
        kon.rollback()
