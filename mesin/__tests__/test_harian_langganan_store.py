"""Domain langganan Latihan Harian (F5): tagihan, bukti, keputusan admin, masa aktif, DB append-only (data sintetis)."""
import sqlite3

import pytest

import akses_harian
import database
import harian_langganan_akses as akses
import harian_langganan_dasar as h
import harian_langganan_putusan as putusan
import harian_langganan_store as store
import pesanan_dasar as d
import schema_harian_langganan as sk

T0 = "2026-11-23T03:00:00"
ADMIN = "admin_sintetis"
BERKAS = "a" * 32
SHA = "b" * 64


@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


def anak(kon, nama="Anak Uji"):
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', 'guru')", (nama,)).lastrowid
    kon.commit()
    return siswa


_nomor = [0]


def bukti(kon, siswa, waktu=T0, sha=None, berkas=None):
    _nomor[0] += 1
    return store.catat_bukti(kon, siswa, "image/png", 100, sha or "%064x" % _nomor[0], berkas or "%032x" % _nomor[0],
                             waktu)


def pesan(kon, siswa, paket="bulanan", waktu=T0, **kw):
    return store.buat_tagihan(kon, siswa, paket, waktu, **kw)


def setuju(kon, order_id, waktu, dilihat):
    return putusan.setujui(kon, order_id, ADMIN, waktu, bukti_dilihat=dilihat)


def langganan_aktif(kon, siswa, waktu):
    """Satu siklus: tagihan, bukti, setuju pada `waktu`."""
    t = pesan(kon, siswa, waktu=waktu)
    b = bukti(kon, siswa, waktu=waktu)
    setuju(kon, t["order_id"], waktu, b["bukti_id"])
    return t


# --- skema ---------------------------------------------------------------------------

def test_skema_idempoten_dua_kali_siapkan(tmp_path):
    jalur = tmp_path / "x.db"
    database.siapkan(jalur)
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        nama = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE name GLOB 'harian_*'")}
    assert set(sk.TABEL) <= nama


def test_rentang_nominal_tidak_beririsan_dengan_paket_coba_dan_antar_paket():
    rentang = [(p.rupiah + h.KODE_MIN, p.rupiah + h.KODE_MAKS) for p in h.PAKET.values()]
    rentang.append((h.RUPIAH_PAKET_COBA + h.KODE_MIN, h.RUPIAH_PAKET_COBA + h.KODE_MAKS))
    rentang.sort()
    for (_, akhir), (awal, _) in zip(rentang, rentang[1:]):
        assert akhir < awal


def test_harga_paket_konstanta_server():
    assert h.PAKET["bulanan"].rupiah == 39000 and h.PAKET["bulanan"].bulan == 1
    assert h.PAKET["tahunan"].rupiah == 349000 and h.PAKET["tahunan"].bulan == 12


# --- tagihan -------------------------------------------------------------------------

def test_tagihan_nominal_dari_paket_dan_kode_unik(kon):
    t = pesan(kon, anak(kon), "tahunan", acak=lambda bebas: bebas[6])
    assert (t["kode_unik"], t["nominal_transfer"], t["baru"]) == (7, 349007, True)
    assert t["kedaluwarsa"] == "2026-11-24T03:00:00"


@pytest.mark.parametrize("paket", ["gratis", "", None, 39000, "BULANAN"])
def test_paket_asing_ditolak_tanpa_efek(kon, paket):
    with pytest.raises(d.PesananDataTidakSah):
        pesan(kon, anak(kon), paket)
    assert kon.execute("SELECT COUNT(*) FROM harian_order").fetchone()[0] == 0


def test_anak_tak_ada_404_tanpa_efek(kon):
    with pytest.raises(d.PesananTidakDitemukan):
        pesan(kon, 9999)
    assert kon.execute("SELECT COUNT(*) FROM harian_order").fetchone()[0] == 0


def test_satu_tagihan_terbuka_per_anak_idempoten_paket_sama(kon):
    s = anak(kon)
    a = pesan(kon, s)
    b = pesan(kon, s)
    assert (b["baru"], b["order_id"], b["nominal_transfer"]) == (False, a["order_id"], a["nominal_transfer"])
    assert kon.execute("SELECT COUNT(*) FROM harian_order").fetchone()[0] == 1


def test_paket_lain_saat_tagihan_terbuka_konflik_tanpa_tulis(kon):
    s = anak(kon)
    pesan(kon, s, "bulanan")
    with pytest.raises(h.LanggananKonflik):
        pesan(kon, s, "tahunan")
    assert kon.execute("SELECT COUNT(*) FROM harian_order").fetchone()[0] == 1


def test_db_menolak_order_kedua_terbuka_walau_lewat_sql_langsung(kon):
    s = anak(kon)
    pesan(kon, s)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_order(id,siswa_id,paket,rupiah,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?)",
                    (h.id_order_baru(), s, "bulanan", 39000, T0, "2026-11-24T03:00:00"))


def test_kedaluwarsa_tanpa_bukti_boleh_tagihan_baru(kon):
    s = anak(kon)
    lama = pesan(kon, s)
    baru = pesan(kon, s, waktu="2026-11-24T03:00:00")
    assert baru["baru"] and baru["order_id"] != lama["order_id"]


def test_anak_lain_tidak_terpengaruh(kon):
    a, b = anak(kon), anak(kon, "Anak Dua")
    ta, tb = pesan(kon, a), pesan(kon, b)
    assert ta["order_id"] != tb["order_id"]
    assert store.tampilan_terbuka(kon, a, T0).order_id == ta["order_id"]


def test_kode_unik_tidak_bertabrakan_dengan_tagihan_dipegang(kon):
    pilihan = []
    for i in range(3):
        t = pesan(kon, anak(kon, "A%d" % i), acak=lambda bebas: bebas[0])
        pilihan.append(t["kode_unik"])
    assert pilihan == [1, 2, 3]


def test_kode_unik_ditahan_30_hari_setelah_lunas_lalu_bebas(kon):
    langganan_aktif(kon, anak(kon), T0)
    nominal = kon.execute("SELECT nominal_transfer FROM harian_tagihan").fetchone()[0]
    assert nominal in store._nominal_dipegang(kon, "2026-12-22T03:00:00")
    assert nominal not in store._nominal_dipegang(kon, "2026-12-24T03:00:00")


def test_tagihan_baru_tidak_memakai_kode_order_lunas_yang_masih_ditahan(kon):
    langganan_aktif(kon, anak(kon), T0)
    kode_lunas = kon.execute("SELECT kode_unik FROM harian_tagihan").fetchone()[0]
    baru = pesan(kon, anak(kon, "Lain"), waktu="2026-12-01T03:00:00", acak=lambda bebas: bebas[0])
    assert baru["kode_unik"] != kode_lunas


def test_kode_unik_habis(kon, monkeypatch):
    monkeypatch.setattr(store, "_nominal_dipegang", lambda k, n: {39000 + i for i in range(1, 1000)})
    with pytest.raises(h.KodeUnikHabis):
        pesan(kon, anak(kon))


def test_kode_acak_di_luar_bebas_ditolak(kon):
    with pytest.raises(d.PesananDataTidakSah):
        pesan(kon, anak(kon), acak=lambda bebas: 5000)


# --- bukti ---------------------------------------------------------------------------

def test_bukti_tanpa_tagihan_konflik(kon):
    with pytest.raises(h.LanggananKonflik):
        bukti(kon, anak(kon))


def test_bukti_masuk_status_menunggu_dan_sha_sama_tidak_ganda(kon):
    s = anak(kon)
    pesan(kon, s)
    a = bukti(kon, s, sha=SHA, berkas=BERKAS)
    b = bukti(kon, s, sha=SHA, berkas="c" * 32)
    assert a["baru"] and not b["baru"] and a["bukti_id"] == b["bukti_id"]
    assert store.tampilan_terbuka(kon, s, T0).status == "menunggu_verifikasi"


@pytest.mark.parametrize("mime,ukuran,sha,berkas", [
    ("text/html", 10, SHA, BERKAS), ("image/png", 0, SHA, BERKAS),
    ("image/png", 5 * 1024 * 1024 + 1, SHA, BERKAS), ("image/png", 10, "xyz", BERKAS),
    ("image/png", 10, SHA, "../etc/passwd"), ("image/png", True, SHA, BERKAS)])
def test_metadata_bukti_tidak_sah_ditolak_tanpa_efek(kon, mime, ukuran, sha, berkas):
    s = anak(kon)
    pesan(kon, s)
    with pytest.raises(d.PesananDataTidakSah):
        store.catat_bukti(kon, s, mime, ukuran, sha, berkas, T0)
    assert kon.execute("SELECT COUNT(*) FROM harian_bukti").fetchone()[0] == 0


def test_bukti_batas_lima(kon):
    s = anak(kon)
    pesan(kon, s)
    for _ in range(5):
        bukti(kon, s)
    with pytest.raises(h.BatasBukti):
        bukti(kon, s)


def test_bukti_setelah_jendela_ditolak(kon):
    s = anak(kon)
    pesan(kon, s)
    with pytest.raises(h.LanggananKonflik):
        bukti(kon, s, waktu="2026-11-24T03:00:00")


# --- keputusan admin ----------------------------------------------------------------

def test_setujui_tulis_verifikasi_dan_akses_satu_transaksi(kon):
    s = anak(kon)
    t = pesan(kon, s)
    b = bukti(kon, s)
    hasil = setuju(kon, t["order_id"], "2026-11-23T05:00:00", b["bukti_id"])
    assert hasil["status"] == "aktif"
    baris = kon.execute("SELECT mulai,berakhir,siswa_id FROM harian_akses").fetchone()
    assert tuple(baris) == ("2026-11-23T05:00:00", "2026-12-23T05:00:00", s)


def test_tahunan_dua_belas_bulan_dan_jepit_akhir_bulan(kon):
    s = anak(kon)
    t = pesan(kon, s, "tahunan", waktu="2026-01-30T03:00:00")
    b = bukti(kon, s, waktu="2026-01-30T03:00:00")
    setuju(kon, t["order_id"], "2026-01-30T03:00:00", b["bukti_id"])
    assert kon.execute("SELECT berakhir FROM harian_akses").fetchone()[0] == "2027-01-30T03:00:00"
    assert h.tambah_bulan_wib("2026-01-30T03:00:00", 1) == "2026-02-28T03:00:00"
    assert h.tambah_bulan_wib("2026-01-31T03:00:00", 1) == "2026-02-28T03:00:00"
    assert h.tambah_bulan_wib("2027-12-31T03:00:00", 2) == "2028-02-29T03:00:00"


def test_perpanjangan_menyambung_dari_akhir_akses_aktif(kon):
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    pertama = kon.execute("SELECT berakhir FROM harian_akses").fetchone()[0]
    langganan_aktif(kon, s, "2026-11-25T03:00:00")
    baris = kon.execute("SELECT mulai,berakhir FROM harian_akses ORDER BY id").fetchall()
    assert baris[1]["mulai"] == pertama == baris[0]["berakhir"]
    assert baris[1]["berakhir"] == h.tambah_bulan_wib(pertama, 1)


def test_setelah_berakhir_mulai_dari_sekarang_bukan_dari_masa_lalu(kon):
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    langganan_aktif(kon, s, "2027-03-01T03:00:00")
    kedua = kon.execute("SELECT mulai FROM harian_akses ORDER BY id DESC").fetchone()[0]
    assert kedua == "2027-03-01T03:00:00"


def test_setujui_dengan_bukti_basi_ditolak_tanpa_efek(kon):
    s = anak(kon)
    t = pesan(kon, s)
    lama = bukti(kon, s)
    bukti(kon, s)
    with pytest.raises(h.LanggananKonflik):
        setuju(kon, t["order_id"], T0, lama["bukti_id"])
    assert kon.execute("SELECT COUNT(*) FROM harian_verifikasi").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM harian_akses").fetchone()[0] == 0


def test_setujui_dua_kali_dan_tanpa_bukti_konflik(kon):
    s = anak(kon)
    t = pesan(kon, s)
    with pytest.raises(h.LanggananKonflik):
        setuju(kon, t["order_id"], T0, 1)
    b = bukti(kon, s)
    setuju(kon, t["order_id"], T0, b["bukti_id"])
    with pytest.raises(h.LanggananKonflik):
        setuju(kon, t["order_id"], T0, b["bukti_id"])
    assert kon.execute("SELECT COUNT(*) FROM harian_akses").fetchone()[0] == 1


def test_setujui_order_tak_dikenal_404(kon):
    with pytest.raises(d.PesananTidakDitemukan):
        setuju(kon, "hor_" + "0" * 32, T0, 1)


def test_tolak_alasan_tampil_dan_boleh_unggah_ulang(kon):
    s = anak(kon)
    t = pesan(kon, s)
    b = bukti(kon, s)
    putusan.tolak(kon, t["order_id"], ADMIN, "  Nominal kurang  ", T0, bukti_dilihat=b["bukti_id"])
    tampil = store.tampilan_terbuka(kon, s, T0)
    assert (tampil.status, tampil.alasan_tolak, tampil.boleh_unggah) == ("ditolak", "Nominal kurang", True)
    assert kon.execute("SELECT COUNT(*) FROM harian_akses").fetchone()[0] == 0
    b2 = bukti(kon, s)
    assert store.tampilan_terbuka(kon, s, T0).status == "menunggu_verifikasi"
    setuju(kon, t["order_id"], T0, b2["bukti_id"])


@pytest.mark.parametrize("alasan", ["", "   ", None, "x" * 201, "a\x00b", 5])
def test_tolak_alasan_tidak_sah_tanpa_efek(kon, alasan):
    s = anak(kon)
    t = pesan(kon, s)
    b = bukti(kon, s)
    with pytest.raises(d.PesananDataTidakSah):
        putusan.tolak(kon, t["order_id"], ADMIN, alasan, T0, bukti_dilihat=b["bukti_id"])
    assert kon.execute("SELECT COUNT(*) FROM harian_verifikasi").fetchone()[0] == 0


def test_menunggu_tidak_kedaluwarsa_admin_boleh_putuskan_sesudah_jendela(kon):
    s = anak(kon)
    t = pesan(kon, s)
    b = bukti(kon, s)
    setuju(kon, t["order_id"], "2026-11-30T03:00:00", b["bukti_id"])
    assert kon.execute("SELECT mulai FROM harian_akses").fetchone()[0] == "2026-11-30T03:00:00"


def test_antrean_terlama_dulu_dan_detail(kon):
    a, b_ = anak(kon), anak(kon, "Dua")
    ta = pesan(kon, a)
    tb = pesan(kon, b_)
    bukti(kon, b_, waktu="2026-11-23T04:00:00")
    ba = bukti(kon, a, waktu="2026-11-23T05:00:00")
    antre = putusan.antrean(kon, T0)
    assert [x["order_id"] for x in antre] == [tb["order_id"], ta["order_id"]]
    rinci = putusan.detail(kon, ta["order_id"], "2026-11-23T05:00:00")
    assert (rinci["status"], rinci["bukti_terakhir_id"], rinci["nominal"]) == (
        "menunggu_verifikasi", ba["bukti_id"], ta["nominal_transfer"])
    assert putusan.detail(kon, "hor_" + "1" * 32, T0) is None
    setuju(kon, ta["order_id"], T0, ba["bukti_id"])
    assert [x["order_id"] for x in putusan.antrean(kon, T0)] == [tb["order_id"]]


# --- DB append-only dan akses tanpa verifikasi ---------------------------------------------

def test_akses_tanpa_verifikasi_ditolak_db(kon):
    s = anak(kon)
    t = pesan(kon, s)
    b = bukti(kon, s)
    kon.execute("INSERT INTO harian_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
                "VALUES(?,'tolak',?,'x',?,?)", (t["order_id"], ADMIN, b["bukti_id"], T0))
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) VALUES(?,?,1,?,?,?)",
                    (t["order_id"], s, T0, "2026-12-23T03:00:00", T0))
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) VALUES(?,?,99,?,?,?)",
                    (t["order_id"], s, T0, "2026-12-23T03:00:00", T0))


@pytest.mark.parametrize("sql", [
    "UPDATE harian_order SET paket='tahunan'", "DELETE FROM harian_order", "UPDATE harian_tagihan SET kode_unik=1",
    "DELETE FROM harian_bukti", "UPDATE harian_verifikasi SET alasan='z'", "DELETE FROM harian_akses",
    "UPDATE harian_akses SET berakhir='2099-01-01T00:00:00'"])
def test_ledger_tidak_bisa_diubah_atau_dihapus(kon, sql):
    langganan_aktif(kon, anak(kon), T0)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(sql)


def test_nominal_dan_paket_dikunci_db(kon):
    s = anak(kon)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_order(id,siswa_id,paket,rupiah,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?)",
                    (h.id_order_baru(), s, "bulanan", 1000, T0, "2026-11-24T03:00:00"))
    kon.rollback()
    t = pesan(kon, s)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT OR REPLACE INTO harian_tagihan(order_id,kode_unik,nominal_transfer,dibuat) VALUES(?,?,?,?)",
                    (t["order_id"], 5, 39005, T0))


def test_siswa_ber_order_ditahan_penghapusan_admin(kon):
    import admin_students
    s = anak(kon)
    assert admin_students._referensi_siswa_ada(kon, s) is False
    pesan(kon, s)
    assert admin_students._referensi_siswa_ada(kon, s) is True


def test_siswa_dengan_order_tidak_bisa_dihapus(kon):
    s = anak(kon)
    pesan(kon, s)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("DELETE FROM siswa WHERE id=?", (s,))


# --- akses / kait ----------------------------------------------------------------------

def test_akses_langganan_aktif_lalu_kembali_gratis_setelah_berakhir(kon):
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    berakhir = "2026-12-23T03:00:00"
    sebelum = akses_harian.akses(kon, s, "2026-12-23T02:59:59")
    assert (sebelum.tanpa_batas, sebelum.sumber, sebelum.berakhir) == (True, "langganan", berakhir)
    sesudah = akses_harian.akses(kon, s, berakhir)
    assert (sesudah.tanpa_batas, sesudah.sumber) == (False, "gratis")


def test_akses_tanpa_langganan_atau_langganan_belum_disetujui_gratis(kon):
    s = anak(kon)
    pesan(kon, s)
    bukti(kon, s)
    assert akses_harian.akses(kon, s, T0).sumber == "gratis"


def test_akses_langganan_anak_lain_tidak_berlaku(kon):
    a, b = anak(kon), anak(kon, "Dua")
    langganan_aktif(kon, a, T0)
    assert akses_harian.akses(kon, b, T0).sumber == "gratis"


def test_akses_rantai_perpanjangan_melaporkan_akhir_terjauh(kon):
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    langganan_aktif(kon, s, "2026-11-25T03:00:00")
    assert akses.berakhir_aktif(kon, s, "2026-11-26T00:00:00") == "2027-01-23T03:00:00"


@pytest.mark.parametrize("kini", ["2026-11-23T10:00:00", "2026-11-23T10:00:00+07:00", "2026-11-23T10:00:00Z".replace("Z", "+00:00")])
def test_kini_format_iso_dinormalkan(kon, kini):
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    assert akses.berakhir_aktif(kon, s, kini) is not None


def test_kini_tanggal_datetime_dan_epoch(kon):
    import datetime
    s = anak(kon)
    langganan_aktif(kon, s, T0)
    assert akses.berakhir_aktif(kon, s, "2026-11-23") is None  # tengah malam UTC sebelum mulai 03:00
    assert akses.berakhir_aktif(kon, s, "2026-11-24") is not None
    assert akses.berakhir_aktif(kon, s, datetime.date(2026, 11, 24)) is not None
    assert akses.berakhir_aktif(kon, s, datetime.datetime(2026, 11, 24, 9, tzinfo=datetime.timezone.utc)) is not None
    assert akses.berakhir_aktif(kon, s, 1795500000) is not None


def test_tabel_absen_tidak_error(kon):
    for tabel in ("harian_akses", ):
        for pemicu in [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'harian_%'")]:
            kon.execute("DROP TRIGGER %s" % pemicu)
    kon.execute("DROP TABLE harian_akses")
    assert akses.berakhir_aktif(kon, 1, T0) is None
    assert akses_harian.akses(kon, anak(kon), T0).sumber == "gratis"


def test_sisa_hari_dibulatkan_ke_atas():
    assert h.sisa_hari("2026-11-26T03:00:00", "2026-11-23T03:00:00") == 3
    assert h.sisa_hari("2026-11-26T03:00:01", "2026-11-23T03:00:00") == 4
    assert h.sisa_hari("2026-11-23T03:30:00", "2026-11-23T03:00:00") == 1
    assert h.sisa_hari("2026-11-23T03:00:00", "2026-11-23T03:00:00") == 0
