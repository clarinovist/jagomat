"""Ledger sintetis: transaksi, schema, restart, race, privasi dan sakelar."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3

import pytest
import admin_store
import subscription as d
import subscription_schema as sk
import subscription_store as s
from test_subscription import AKUN, INVOICE, ts

ON = d.Sakelar(True, True, True, False)
T0 = ts(2027, 1, 1)


def dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def daftar(path, akun=AKUN, sumber="daftar_0001", mulai=T0, **kw):
    return s.enroll(path, akun, sumber_id=sumber, asal="publik", mulai=mulai,
                    peran="guru", sakelar=ON, **kw)


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=T0)
    s.buat_kampanye(path, "promo_v1", mulai=T0, sakelar=ON)
    daftar(path)
    s.atur_cakupan(path, AKUN, (1,), operasi_id="cakupan_001", revisi=0, sekarang=T0, pemilik_profil=lambda _: AKUN, sakelar=ON)
    return path


def invoice(path, nomor=1, sekarang=T0, akun=AKUN):
    return s.buat_invoice(path, akun, invoice_id="inv_" + ("%032x" % nomor),
                         idempotency_key="idem_%032x" % nomor, provider="midtrans", channel="qris",
                         merchant="M_SINTETIS", sekarang=sekarang, kedaluwarsa=sekarang+86400, sakelar=ON)


def bukti(inv, transaksi="trx_sintetis"):
    return d.Pembayaran("midtrans", transaksi, inv["invoice_id"], inv["akun_id"], inv["rupiah"],
                         "IDR", "qris", "M_SINTETIS", "settlement", True)


def test_migrasi_admin5_ke6_additive_idempoten_dan_reader(tmp_path):
    path = tmp_path / "admin-control.db"
    with pytest.raises(admin_store.StoreBelumSiap):
        s.baca(path, AKUN)
    assert not path.exists()
    with sqlite3.connect(path) as kon:
        admin_store._jalankan_ddl(kon, admin_store._DDL)
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,9,0,'closed_standard',1)")
        kon.execute("PRAGMA user_version=5")
    lama = dump(path)
    with pytest.raises(admin_store.StoreBelumSiap):
        s.baca(path, AKUN)
    assert dump(path) == lama
    admin_store.siapkan(path, sekarang=4)
    setelah = dump(path)
    admin_store.siapkan(path, sekarang=9)
    assert dump(path) == setelah
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 7
        assert tuple(kon.execute("SELECT * FROM konfigurasi_pendaftaran").fetchone()) == (1,9,0,"closed_standard",1)
        for t in sk.TABEL[1:]:
            assert kon.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] == 0
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_migrator_dan_enrollment_serentak_tidak_ganda(tmp_path):
    path = tmp_path / 'admin-control.db'
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: admin_store.siapkan(path, sekarang=T0), range(8)))
    s.buat_kampanye(path, 'promo_v1', mulai=T0, sakelar=ON)
    with ThreadPoolExecutor(max_workers=4) as pool:
        hasil = list(pool.map(lambda _: daftar(path), range(8)))
    assert all(e == hasil[0] for e in hasil)
    with admin_store.buka_baca(path) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0] == 7
        assert kon.execute('SELECT COUNT(*) FROM langganan_enrollment').fetchone()[0] == 1


def test_schema_trigger_hilang_ditolak_tanpa_repair(ledger):
    with sqlite3.connect(ledger) as kon:
        kon.execute("DROP TRIGGER langganan_grant_tolak_update")
    sebelum = dump(ledger)
    with pytest.raises(admin_store.StoreBelumSiap):
        s.baca(ledger, AKUN)
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_store.siapkan(ledger)
    assert dump(ledger) == sebelum


def test_default_off_semua_writer_tidak_menyentuh_store(tmp_path):
    path = tmp_path / "tidak-ada.db"
    panggilan = [
        lambda: s.buat_kampanye(path, "promo", mulai=T0),
        lambda: s.enroll(path, AKUN, sumber_id="daftar_0001", asal="publik", mulai=T0, peran="guru"),
        lambda: s.atur_cakupan(path, AKUN, (1,), operasi_id="cakupan_001", revisi=0, sekarang=T0),
        lambda: s.buat_invoice(path, AKUN, invoice_id=INVOICE, idempotency_key="idem_0001", provider="midtrans", channel="qris", merchant="M", sekarang=T0, kedaluwarsa=T0+1),
        lambda: s.catat_pengamatan(path, AKUN, INVOICE, operasi_id="amati_0001", status="belum_terverifikasi", sekarang=T0),
        lambda: s.terapkan_pembayaran(path, AKUN, None, sekarang=T0),
    ]
    for panggil in panggilan:
        with pytest.raises(d.FiturNonaktif):
            panggil()
    assert not path.exists()


def test_enrollment_replay_kuota100_jendela_dan_internal(ledger):
    awal = s.baca(ledger, AKUN)
    assert daftar(ledger) == awal.enrollment
    for i in range(2, 103):
        e = daftar(ledger, "akun_%032x" % i, "daftar_%04d" % i)
        assert e.peserta_promo is (i <= 100)
    luar = daftar(ledger, "akun_" + "f" * 32, "daftar_luar", T0 + d.DURASI_KAMPANYE)
    assert not luar.peserta_promo
    transisi = s.enroll(ledger, "akun_" + "e" * 32, sumber_id="transisi_001", asal="transisi", mulai=T0,
                         peran="guru", promo_lama=True, sakelar=ON)
    assert transisi.peserta_promo
    for kw in ({"peran": "admin"}, {"peran": "guru", "internal": True}, {"peran": "guru", "asal": "admin"}):
        args = dict(sumber_id="internal_001", asal="publik", mulai=T0, peran="guru", sakelar=ON)
        args.update(kw)
        with pytest.raises(ValueError):
            s.enroll(ledger, "akun_" + "d" * 32, **args)
    with pytest.raises(s.KonflikLangganan):
        daftar(ledger, mulai=T0+1)
    assert s.baca(ledger, AKUN) == awal


def test_receipt_grant_replay_concurrency_restart(ledger):
    inv = invoice(ledger)
    b = bukti(inv)
    with ThreadPoolExecutor(max_workers=4) as pool:
        hasil = list(pool.map(lambda _: s.terapkan_pembayaran(ledger, AKUN, b, sekarang=T0+1, sakelar=ON), range(8)))
    assert hasil == ["grant"] * 8
    sebelum = dump(ledger)
    assert s.terapkan_pembayaran(ledger, AKUN, b, sekarang=T0+999999, sakelar=ON) == "grant"
    assert dump(ledger) == sebelum
    snap = s.baca(ledger, AKUN)
    assert len(snap.grants) == 1 and snap.grants[0].urutan == 1
    with admin_store.buka_baca(ledger) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_receipt").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0] == 1
    assert s.baca_invoice(ledger, AKUN, inv["invoice_id"])["status"] == "lunas"


def test_invoice_retry_dan_semantik_serentak(ledger):
    with ThreadPoolExecutor(max_workers=3) as pool:
        hasil = list(pool.map(lambda _: invoice(ledger), range(6)))
    assert all(h == hasil[0] for h in hasil)
    with pytest.raises(s.KonflikLangganan):
        invoice(ledger, 2)
    with admin_store.buka_baca(ledger) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_invoice").fetchone()[0] == 1


@pytest.mark.parametrize("ubah", [
    {"status": "pending"}, {"terverifikasi": False}, {"rupiah": 15001}, {"rupiah": 15000.0},
    {"akun_id": "akun_" + "d" * 32}, {"currency": "USD"}, {"channel": "gopay"},
    {"merchant": "asing"}, {"provider": "asing"},
])
def test_binding_bukti_tidak_cocok_tanpa_efek(ledger, ubah):
    b = replace(bukti(invoice(ledger)), **ubah)
    sebelum = dump(ledger)
    with pytest.raises(s.KonflikLangganan):
        s.terapkan_pembayaran(ledger, AKUN, b, sekarang=T0+1, sakelar=ON)
    assert dump(ledger) == sebelum


def test_owner_asing_dan_sumber_receipt_lintas_invoice(ledger):
    inv = invoice(ledger)
    sebelum = dump(ledger)
    with pytest.raises(LookupError, match="invoice tidak ditemukan"):
        s.terapkan_pembayaran(ledger, "akun_" + "d" * 32, bukti(inv), sekarang=T0+1, sakelar=ON)
    assert dump(ledger) == sebelum
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    berikut = invoice(ledger, 2, T0+2)
    sebelum = dump(ledger)
    with pytest.raises(s.KonflikLangganan, match="sumber"):
        s.terapkan_pembayaran(ledger, AKUN, bukti(berikut), sekarang=T0+3, sakelar=ON)
    assert dump(ledger) == sebelum


def test_atomic_receipt_grant_crash_rollback(ledger):
    inv = invoice(ledger)
    sebelum = dump(ledger)
    with pytest.raises(RuntimeError, match="crash sintetis"):
        s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON, failpoint="setelah_receipt")
    assert dump(ledger) == sebelum
    assert s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON) == "grant"


def test_pending_setelah_settlement_dan_uang_tambahan_tidak_double_grant(ledger):
    inv = invoice(ledger)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    snap = s.baca(ledger, AKUN)
    s.catat_pengamatan(ledger, AKUN, inv["invoice_id"], operasi_id="amati_0001", status="belum_terverifikasi", sekarang=T0+2, sakelar=ON)
    assert s.baca(ledger, AKUN) == snap
    assert s.baca_invoice(ledger, AKUN, inv["invoice_id"])["status"] == "lunas"
    assert s.terapkan_pembayaran(ledger, AKUN, bukti(inv, "trx_kedua"), sekarang=T0+2, sakelar=ON) == "perlu_diperiksa"
    assert s.baca(ledger, AKUN) == snap
    with admin_store.buka_baca(ledger) as kon:
        assert kon.execute("SELECT COUNT(*) FROM langganan_receipt").fetchone()[0] == 2


def test_settlement_terlambat_tidak_memilih_d8(ledger):
    inv = invoice(ledger)
    assert s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+86400, sakelar=ON) == "perlu_diperiksa"
    assert not s.baca(ledger, AKUN).grants
    assert s.baca_invoice(ledger, AKUN, inv["invoice_id"])["perlu_diperiksa"]


def test_cakupan_berikutnya_snapshot_dan_tiga_promo(ledger):
    inv = invoice(ledger)
    with pytest.raises(s.KonflikLangganan):
        s.atur_cakupan(ledger, AKUN, (2,), operasi_id="cakupan_quote", revisi=1, sekarang=T0+1, pemilik_profil=lambda _: AKUN, sakelar=ON)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    s.atur_cakupan(ledger, AKUN, (1,2), operasi_id="cakupan_002", revisi=0, sekarang=T0+2, pemilik_profil=lambda _: AKUN, sakelar=ON)
    assert s.baca(ledger, AKUN).grants[0].profil == (1,)
    assert s.baca_invoice(ledger, AKUN, inv["invoice_id"])["profil_json"] == "[1]"
    for nomor in range(2, 5):
        sekarang = s.baca(ledger, AKUN).grants[-1].periode.akhir + 86400
        inv2 = invoice(ledger, nomor, sekarang)
        assert inv2["rupiah"] == (20000 if nomor <= 3 else 45000)
        s.terapkan_pembayaran(ledger, AKUN, bukti(inv2, "trx_%d" % nomor), sekarang=sekarang+1, sakelar=ON)
    s.atur_cakupan(ledger, AKUN, (), operasi_id="cakupan_nol", revisi=0, sekarang=sekarang+2, pemilik_profil=lambda _: AKUN, sakelar=ON)
    with pytest.raises(ValueError):
        invoice(ledger, 5, sekarang+3)


def test_ledger_immutable_semua_jalur_sql(ledger):
    inv = invoice(ledger)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    for tabel in sk.TABEL:
        with sqlite3.connect(ledger) as kon:
            if not kon.execute("SELECT 1 FROM " + tabel).fetchone():
                continue
            for sql in ("DELETE FROM " + tabel, "INSERT OR REPLACE INTO %s SELECT * FROM %s" % (tabel,tabel)):
                with pytest.raises(sqlite3.IntegrityError):
                    kon.execute(sql)
    with sqlite3.connect(ledger) as kon:
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("UPDATE langganan_receipt SET rupiah=1")


def test_auth_belajar_tidak_berubah_dan_login_consent_bukan_input(ledger, tmp_path):
    import database
    import auth
    belajar, akun = tmp_path / "belajar.db", tmp_path / "sandi.json"
    database.siapkan(belajar)
    auth.tambah_akun("keluarga-sintetis", "sandi-sintetis-123", "guru", akun)
    sebelum = (belajar.read_bytes(), akun.read_bytes())
    inv = invoice(ledger)
    s.terapkan_pembayaran(ledger, AKUN, bukti(inv), sekarang=T0+1, sakelar=ON)
    assert (belajar.read_bytes(), akun.read_bytes()) == sebelum
    snap = s.baca(ledger, AKUN)
    assert auth.setel_sandi_guru("keluarga-sintetis", "sandi-baru-sintetis-123", akun)
    assert auth.autentikasi("keluarga-sintetis", "sandi-baru-sintetis-123", akun)
    assert daftar(ledger) == snap.enrollment
    assert s.baca(ledger, AKUN) == snap
