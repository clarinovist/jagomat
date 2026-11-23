"""Jendela bayar/QR per order: #1 saat order dibuat, buka ulang terjaga, kuota, append-only."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

import midtrans_contract
import pesanan
import pesanan_dasar
import pesanan_jendela
from pesanan_kit import (AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, buat, hitung, operasi,
                         ord_id, siapkan_db, snapshot_langganan, terapkan)

PESAN_TOLAK = "jendela pembayaran tidak dapat dibuka ulang"
SEPERTIGA_HARI = "2026-11-18T18:00:00"   # masih di dalam jendela #1 (kedaluwarsa 19 Nov 10:00)
JENDELA_BARU = "2026-11-21T00:00:00"      # sesudah kedaluwarsa jendela #2 (20 Nov 10:00:01)


@pytest.fixture
def db(tmp_path):
    return siapkan_db(tmp_path)


@pytest.fixture
def kon(db):
    with pesanan.buka(db, tulis_data=True) as k:
        yield k


def buka_ulang(kon, order, n=50, *, akun=AKUN_A, sekarang=SESUDAH_KEDALUWARSA, **ganti):
    return pesanan.buka_jendela_ulang(kon, order["order_id"], akun, sekarang, operasi(n), **ganti)


def jendela(kon):
    return [tuple(r) for r in kon.execute(
        "SELECT order_id,urutan,idempotency_key,operasi_id,dibuat,kedaluwarsa FROM pesanan_jendela "
        "ORDER BY order_id,urutan")]


def amati_mati(kon, order, n, status, sekarang):
    return terapkan(kon, order, n, sekarang=sekarang, transaction_status=status, status_code="407")


def status(kon, order, sekarang):
    return pesanan.status_order(kon, order["order_id"], AKUN_A, sekarang)["status"]


def dump(path):
    with sqlite3.connect(path) as k:
        return tuple(k.iterdump())


# --- jendela #1 --------------------------------------------------------------------------------

def test_jendela_pertama_dibuat_bersama_order_dengan_kunci_order(kon):
    order = buat(kon, 1)
    assert jendela(kon) == [(order["order_id"], 1, order["idempotency_key"], None, SEKARANG,
                             order["kedaluwarsa"])]
    terbaru = pesanan.jendela_terbaru(kon, order["order_id"])
    assert terbaru == {"urutan": 1, "idempotency_key": order["idempotency_key"],
                       "dibuat": SEKARANG, "kedaluwarsa": order["kedaluwarsa"]}


def test_order_idempoten_tidak_menambah_jendela_dan_kontrak_order_lama_utuh(kon):
    order = buat(kon, 1)
    buat(kon, 1, order_id=ord_id(777))
    assert hitung(kon, "pesanan_jendela") == 1
    assert set(order) == {"order_id", "akun_id", "siswa_id", "cek_id", "rupiah", "currency",
                          "provider", "channel", "merchant", "idempotency_key", "dibuat",
                          "kedaluwarsa", "baru"}


def test_order_ditolak_tidak_meninggalkan_jendela(kon):
    with pytest.raises(pesanan.PesananButuhKontak):
        buat(kon, 1, punya_kontak=False)
    assert hitung(kon, "pesanan_jendela") == 0


def test_jendela_terbaru_order_tak_dikenal_atau_format_salah(kon):
    for nilai in (ord_id(5), "bukan-id"):
        with pytest.raises(pesanan.PesananTidakDitemukan):
            pesanan.jendela_terbaru(kon, nilai)


def test_kelas_mati_sama_dengan_kontrak_midtrans():
    assert pesanan_jendela.KELAS_MATI == midtrans_contract.KELAS_MATI


# --- status turunan memakai jendela terbaru --------------------------------------------------

def test_kedaluwarsa_lokal_menjadi_status_kedaluwarsa_tanpa_receipt(kon):
    order = buat(kon, 1)
    assert status(kon, order, SEKARANG) == "belum_bayar"
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "kedaluwarsa"


def test_status_memakai_jendela_terbaru_bukan_yang_pertama(kon):
    order = buat(kon, 1)
    baru = buka_ulang(kon, order)
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "belum_bayar"
    assert pesanan.status_order(kon, order["order_id"], AKUN_A,
                                SESUDAH_KEDALUWARSA)["kedaluwarsa"] == baru["kedaluwarsa"]
    assert status(kon, order, baru["kedaluwarsa"]) == "kedaluwarsa"


def test_daftar_admin_memakai_jendela_terbaru_dan_tetap_minimal(kon):
    order = buat(kon, 1)
    baru = buka_ulang(kon, order)
    item = pesanan.daftar_admin(kon, halaman=1, per_halaman=5,
                                sekarang=SESUDAH_KEDALUWARSA)["items"][0]
    assert item["status"] == "belum_bayar" and item["kedaluwarsa"] == baru["kedaluwarsa"]
    assert set(item) == {"order_id", "akun", "dibuat", "kedaluwarsa", "alasan_kode", "status", "dua_jalur", "menunggu_lama"}


def test_receipt_lunas_tetap_lunas_walau_jendela_lewat(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1, sekarang=SESUDAH_KEDALUWARSA)
    assert status(kon, order, JENDELA_BARU) == "sudah_dibayar"


# --- buka ulang: sukses ------------------------------------------------------------------------

def test_buka_ulang_sukses_setelah_kedaluwarsa_order_id_tetap_sama(kon):
    order = buat(kon, 1)
    hasil = buka_ulang(kon, order)
    assert hasil["baru"] is True and hasil["order_id"] == order["order_id"]
    assert hasil["urutan"] == 2 and hasil["dibuat"] == SESUDAH_KEDALUWARSA
    assert hasil["kedaluwarsa"] == "2026-11-20T10:00:01"
    assert hasil["idempotency_key"] == pesanan_jendela.kunci_ulang(order["order_id"], 2)
    assert hasil["idempotency_key"] != order["idempotency_key"]
    assert 8 <= len(hasil["idempotency_key"]) <= 46
    assert pesanan.jendela_terbaru(kon, order["order_id"]) == {
        k: hasil[k] for k in ("urutan", "idempotency_key", "dibuat", "kedaluwarsa")}
    assert hitung(kon, "pesanan_order") == 1 and hitung(kon, "pesanan_jendela") == 2
    assert pesanan.ambil_order(kon, order["order_id"], AKUN_A)["kedaluwarsa"] == order["kedaluwarsa"]
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "belum_bayar"


def test_kunci_baru_dari_pemanggil_dipakai_dan_divalidasi(kon):
    order = buat(kon, 1)
    assert buka_ulang(kon, order, idem_baru="kunci-baru-0001")["idempotency_key"] == "kunci-baru-0001"
    kedua = buat(kon, 2)
    for buruk in ("pendek", "kunci dengan spasi!!", "k" * 47, 12345):
        with pytest.raises(pesanan.PesananDataTidakSah):
            buka_ulang(kon, kedua, 60, idem_baru=buruk, sekarang=SESUDAH_KEDALUWARSA)
    with pytest.raises(pesanan.PesananKonflik):   # bentrok dengan kunci jendela lain
        buka_ulang(kon, kedua, 61, idem_baru="kunci-baru-0001", sekarang=JENDELA_BARU)
    assert hitung(kon, "pesanan_jendela") == 3


def test_kunci_ulang_deterministik_per_order_dan_urutan():
    assert pesanan_jendela.kunci_ulang(ord_id(1), 2) == pesanan_jendela.kunci_ulang(ord_id(1), 2)
    assert pesanan_jendela.kunci_ulang(ord_id(1), 2) != pesanan_jendela.kunci_ulang(ord_id(1), 3)
    assert pesanan_jendela.kunci_ulang(ord_id(1), 2) != pesanan_jendela.kunci_ulang(ord_id(2), 2)


# --- buka ulang: ditolak -----------------------------------------------------------------------

def _tolak_tanpa_efek(kon, db, order, **kw):
    sebelum = dump(db)
    with pytest.raises(pesanan.PesananKonflik, match=PESAN_TOLAK):
        buka_ulang(kon, order, **kw)
    assert dump(db) == sebelum


def test_ditolak_saat_jendela_masih_berlaku_dan_provider_belum_menyatakan_mati(kon, db):
    order = buat(kon, 1)
    _tolak_tanpa_efek(kon, db, order, sekarang=SEPERTIGA_HARI)
    terapkan(kon, order, 2, sekarang=SEPERTIGA_HARI, transaction_status="pending", status_code="201")
    _tolak_tanpa_efek(kon, db, order, sekarang=SEPERTIGA_HARI)


@pytest.mark.parametrize("mati", ["expire", "cancel", "deny"])
def test_diizinkan_setelah_pengamatan_status_mati_walau_belum_24_jam(kon, mati):
    order = buat(kon, 1)
    amati_mati(kon, order, 2, mati, "2026-11-18T12:00:00")
    hasil = buka_ulang(kon, order, sekarang="2026-11-18T13:00:00")
    assert hasil["urutan"] == 2 and hasil["baru"] is True
    assert hasil["kedaluwarsa"] == "2026-11-19T13:00:00"


def test_status_selain_kelas_mati_tidak_membuka(kon, db):
    order = buat(kon, 1)
    for n, nilai in enumerate(("pending", "authorize", "tidak aman!"), start=2):
        terapkan(kon, order, n, sekarang="2026-11-18T12:00:00", transaction_status=nilai,
                 status_code="201")
    _tolak_tanpa_efek(kon, db, order, sekarang="2026-11-18T13:00:00")


def test_petunjuk_callback_tidak_pernah_membuka_jendela(kon, db):
    order = buat(kon, 1)
    for n, nilai in enumerate(("expire", "cancel", "deny"), start=2):
        pesanan.catat_petunjuk(kon, order["order_id"],
                               {"transaction_status": nilai, "status_code": "407"},
                               "2026-11-18T12:00:00", operasi(n))
    _tolak_tanpa_efek(kon, db, order, sekarang="2026-11-18T13:00:00")


def test_pengamatan_mati_pada_detik_yang_sama_atau_sebelum_jendela_baru_tidak_membuka_lagi(kon, db):
    order = buat(kon, 1)
    amati_mati(kon, order, 2, "expire", "2026-11-18T12:00:00")
    amati_mati(kon, order, 3, "expire", "2026-11-18T13:00:00")
    buka_ulang(kon, order, sekarang="2026-11-18T13:00:00")
    _tolak_tanpa_efek(kon, db, order, n=51, sekarang="2026-11-18T14:00:00")
    amati_mati(kon, order, 4, "expire", "2026-11-18T15:00:00")
    assert buka_ulang(kon, order, 52, sekarang="2026-11-18T15:30:00")["urutan"] == 3


@pytest.mark.parametrize("ubah", ["lunas", "perlu_diperiksa", "direfund"])
def test_ditolak_bila_ada_receipt_walau_jendela_lewat_atau_provider_mati(kon, db, ubah):
    order = buat(kon, 1)
    if ubah == "perlu_diperiksa":
        terapkan(kon, order, 1, gross_amount="48000")
    else:
        terapkan(kon, order, 1)
    if ubah == "direfund":
        pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    amati_mati(kon, order, 3, "expire", "2026-11-18T12:00:00")
    _tolak_tanpa_efek(kon, db, order, sekarang=SESUDAH_KEDALUWARSA)
    assert hitung(kon, "pesanan_jendela") == 1


def test_akun_lain_dan_id_tak_sah_404_identik_tanpa_efek(kon, db):
    order = buat(kon, 1)
    sebelum = dump(db)
    pesan = set()
    for ident, akun in ((order["order_id"], AKUN_B), (ord_id(999), AKUN_A), ("bukan-id", AKUN_A),
                        (order["order_id"], "bukan-akun")):
        with pytest.raises(pesanan.PesananTidakDitemukan) as galat:
            pesanan.buka_jendela_ulang(kon, ident, akun, SESUDAH_KEDALUWARSA, operasi(50))
        pesan.add(str(galat.value))
    assert pesan == {"pesanan tidak ditemukan"}
    assert dump(db) == sebelum


def test_masukan_tidak_sah_ditolak_tanpa_tulis(kon, db):
    order = buat(kon, 1)
    sebelum = dump(db)
    for ganti in (dict(operasi_id="pendek"), dict(sekarang="kemarin"), dict(sekarang=17)):
        argumen = dict(order_id=order["order_id"], akun_id=AKUN_A, sekarang=SESUDAH_KEDALUWARSA,
                       operasi_id=operasi(50))
        argumen.update(ganti)
        with pytest.raises(pesanan.PesananDataTidakSah):
            pesanan.buka_jendela_ulang(kon, **argumen)
    assert dump(db) == sebelum


# --- idempotensi per operasi_id ---------------------------------------------------------------

def test_replay_operasi_identik_mengembalikan_jendela_yang_sama(kon):
    order = buat(kon, 1)
    pertama = buka_ulang(kon, order, 50)
    sama = buka_ulang(kon, order, 50)
    assert {**pertama, "baru": False} == sama
    sesudah_lewat = buka_ulang(kon, order, 50, sekarang="2026-11-30T00:00:00")
    assert sesudah_lewat == sama   # tetap jendela yang sama walau jendela itu kini juga kedaluwarsa
    assert hitung(kon, "pesanan_jendela") == 2


def test_operasi_sama_isi_berbeda_adalah_konflik(kon):
    satu, dua = buat(kon, 1), buat(kon, 2)
    buka_ulang(kon, satu, 50, idem_baru="kunci-baru-0001")
    with pytest.raises(pesanan.PesananKonflik):
        buka_ulang(kon, satu, 50, idem_baru="kunci-baru-0002")
    with pytest.raises(pesanan.PesananKonflik):
        buka_ulang(kon, dua, 50)
    assert hitung(kon, "pesanan_jendela") == 3


def test_replay_oleh_akun_lain_tetap_404(kon):
    order = buat(kon, 1)
    buka_ulang(kon, order, 50)
    with pytest.raises(pesanan.PesananTidakDitemukan):
        buka_ulang(kon, order, 50, akun=AKUN_B)


# --- batas jumlah jendela ----------------------------------------------------------------------

def test_jumlah_jendela_dibatasi_per_order(kon, db):
    order = buat(kon, 1)
    waktu = SESUDAH_KEDALUWARSA
    for n in range(2, pesanan.MAKS_JENDELA + 1):
        assert buka_ulang(kon, order, 50 + n, sekarang=waktu)["urutan"] == n
        waktu = pesanan_dasar.tambah_jam(waktu, 25)
    sebelum = dump(db)
    with pytest.raises(pesanan.PesananBatasJendela) as galat:
        buka_ulang(kon, order, 99, sekarang=waktu)
    assert isinstance(galat.value, pesanan.PesananKonflik)
    assert dump(db) == sebelum and hitung(kon, "pesanan_jendela") == pesanan.MAKS_JENDELA
    assert status(kon, order, waktu) == "kedaluwarsa"


# --- kuota -------------------------------------------------------------------------------------

def test_order_kedaluwarsa_melepas_slot_dan_buka_ulang_memakainya_lagi(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 1)
    satu = buat(kon, 1)
    assert pesanan_jendela.jumlah_aktif(kon, SEKARANG) == 1
    assert pesanan_jendela.jumlah_aktif(kon, SESUDAH_KEDALUWARSA) == 0
    buat(kon, 2, sekarang=SESUDAH_KEDALUWARSA)          # slot satu terlepas
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 3, sekarang=SESUDAH_KEDALUWARSA)
    assert satu["order_id"]


def test_buka_ulang_saat_kuota_penuh_ditolak_tanpa_menulis(kon, db, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu = buat(kon, 1)
    buat(kon, 2, sekarang="2026-11-18T12:00:00")
    buat(kon, 3, sekarang=SESUDAH_KEDALUWARSA)          # satu kedaluwarsa, dua aktif: penuh
    sebelum = dump(db)
    with pytest.raises(pesanan.PesananKuotaHabis):
        buka_ulang(kon, satu)
    assert dump(db) == sebelum and hitung(kon, "pesanan_jendela") == 3


def test_buka_ulang_berhasil_bila_ada_slot_dan_lalu_dihitung(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu = buat(kon, 1)
    buat(kon, 2, sekarang="2026-11-18T12:00:00")
    buka_ulang(kon, satu)
    assert pesanan_jendela.jumlah_aktif(kon, SESUDAH_KEDALUWARSA) == 2
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 3, sekarang=SESUDAH_KEDALUWARSA)


def test_order_ber_receipt_tetap_memakai_slot_walau_jendela_lewat(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu, dua = buat(kon, 1), buat(kon, 2)
    terapkan(kon, satu, 1, transaction_id="trx-1")
    terapkan(kon, dua, 2, transaction_id="trx-2", gross_amount="48000")
    assert pesanan_jendela.jumlah_aktif(kon, JENDELA_BARU) == 2
    with pytest.raises(pesanan.PesananKuotaHabis):
        buat(kon, 3, sekarang=JENDELA_BARU)


def test_order_sendiri_tidak_dihitung_ganda_saat_dibuka_ulang_karena_sinyal_mati(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu = buat(kon, 1)
    buat(kon, 2)
    amati_mati(kon, satu, 3, "expire", "2026-11-18T12:00:00")
    assert buka_ulang(kon, satu, sekarang="2026-11-18T13:00:00")["urutan"] == 2


def test_dua_order_berebut_slot_terakhir_berurutan_deterministik(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 1)
    satu = buat(kon, 1)
    dua = buat(kon, 2, sekarang=SESUDAH_KEDALUWARSA)
    waktu = "2026-11-21T00:00:00"   # kedua order tanpa receipt dan kedaluwarsa
    assert pesanan_jendela.jumlah_aktif(kon, waktu) == 0
    assert buka_ulang(kon, satu, 50, sekarang=waktu)["urutan"] == 2
    with pytest.raises(pesanan.PesananKuotaHabis):
        buka_ulang(kon, dua, 51, sekarang=waktu)
    assert hitung(kon, "pesanan_jendela") == 3


def test_balapan_koneksi_pada_slot_terakhir_tidak_melampaui_kuota(db, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 1)
    waktu = "2026-11-21T00:00:00"
    with pesanan.buka(db, tulis_data=True) as k:
        satu = buat(k, 1)
        dua = buat(k, 2, sekarang=SESUDAH_KEDALUWARSA)

    def coba(order):
        with pesanan.buka(db, tulis_data=True) as k:
            try:
                buka_ulang(k, order, 70 + order["siswa_id"], sekarang=waktu)
                return "ok"
            except pesanan.PesananKuotaHabis:
                return "habis"
            except sqlite3.OperationalError:
                return "terkunci"

    with ThreadPoolExecutor(max_workers=2) as pool:
        hasil = list(pool.map(coba, (satu, dua)))
    with pesanan.buka(db) as k:
        assert hitung(k, "pesanan_jendela") == 2 + hasil.count("ok")
        assert pesanan_jendela.jumlah_aktif(k, waktu) == hasil.count("ok") <= 1
    assert hasil.count("ok") >= 1


# --- append-only dan skema ---------------------------------------------------------------------

@pytest.mark.parametrize("sql", ["UPDATE pesanan_jendela SET kedaluwarsa='2031-01-01T00:00:00'",
                                 "UPDATE pesanan_jendela SET idempotency_key='kunci-lain-01'",
                                 "DELETE FROM pesanan_jendela"])
def test_jendela_tolak_update_dan_delete(kon, sql):
    order = buat(kon, 1)
    buka_ulang(kon, order)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        kon.execute(sql)
    kon.rollback()
    assert hitung(kon, "pesanan_jendela") == 2


def test_urutan_jendela_wajib_berurutan_dan_kunci_unik_di_tingkat_db(kon):
    order = buat(kon, 1)
    sisip = ("INSERT INTO pesanan_jendela(order_id,urutan,idempotency_key,operasi_id,dibuat,"
             "kedaluwarsa) VALUES(?,?,?,?,?,?)")
    dasar = (order["order_id"],)
    akhir = ("2026-11-18T10:00:00", "2026-11-19T10:00:00")
    for buruk in ((3, "kunci-baru-0003", operasi(1)), (1, "kunci-baru-0004", None),
                  (2, order["idempotency_key"], operasi(2)), (0, "kunci-baru-0005", operasi(3)),
                  (2, "kunci-baru-0006", None), (2, "pendek", operasi(4)),
                  (2, "kunci-baru-0007", "pendek")):
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(sisip, dasar + buruk[:2] + (buruk[2],) + akhir)
    kon.execute(sisip, dasar + (2, "kunci-baru-0008", operasi(5)) + akhir)
    with pytest.raises(sqlite3.IntegrityError):   # operasi_id ganda
        kon.execute(sisip, dasar + (3, "kunci-baru-0009", operasi(5)) + akhir)
    with pytest.raises(sqlite3.IntegrityError):   # kedaluwarsa tidak melebihi dibuat
        kon.execute(sisip, dasar + (3, "kunci-baru-0010", operasi(6)) + (akhir[0], akhir[0]))
    kon.rollback()
    assert hitung(kon, "pesanan_jendela") == 1


def test_jendela_wajib_menunjuk_order_yang_ada(kon):
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO pesanan_jendela VALUES(?,1,'kunci-baru-0001',NULL,?,?)",
                    (ord_id(404), SEKARANG, "2026-11-19T10:00:00"))
    kon.rollback()


def test_insert_or_replace_jendela_ditolak(kon):
    order = buat(kon, 1)
    buka_ulang(kon, order)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT OR REPLACE INTO pesanan_jendela SELECT * FROM pesanan_jendela")
    kon.rollback()
    assert hitung(kon, "pesanan_jendela") == 2


# --- isolasi dari langganan, atomisitas -------------------------------------------------------

def test_tidak_ada_baris_langganan_dari_jalur_jendela(kon):
    sebelum = snapshot_langganan(kon)
    order = buat(kon, 1)
    buka_ulang(kon, order)
    assert snapshot_langganan(kon) == sebelum


def test_buka_ulang_memakai_begin_immediate_sebelum_membaca_dan_commit_sesudah_tulis(kon):
    order = buat(kon, 1)
    pernyataan = []
    kon.set_trace_callback(pernyataan.append)
    try:
        buka_ulang(kon, order)
    finally:
        kon.set_trace_callback(None)
    sql = [p.strip() for p in pernyataan]
    awal = next(i for i, p in enumerate(sql) if p.startswith("BEGIN IMMEDIATE"))
    baca = next(i for i, p in enumerate(sql) if "pesanan_" in p and p.startswith("SELECT"))
    tulis = [i for i, p in enumerate(sql) if p.startswith("INSERT")]
    assert awal < baca and tulis and sql.index("COMMIT") > max(tulis)
