"""Latihan Harian: skema harian_*, mulai/lanjut, batas gratis WIB, jawab sekali, proyeksi aman, bukan bukti siklus."""
import itertools
import re
import sqlite3
from pathlib import Path

import pytest

import akses_harian
import database
import harian_latihan_store as hs
import harian_waktu

T0 = 1_800_000_000  # 2027-01-15 08:00:00 UTC = 15:00 WIB
SEBELUM_TENGAH_MALAM_WIB = harian_waktu.awal_hari_wib(T0) + 86400 - 1
TEPAT_TENGAH_MALAM_WIB = harian_waktu.awal_hari_wib(T0) + 86400
AKAR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def lingkungan(monkeypatch, tmp_path):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    benih = itertools.count(100)
    monkeypatch.setattr(hs, "_seed_baru", lambda: next(benih))


@pytest.fixture
def jalur(tmp_path):
    p = tmp_path / "belajar.db"
    database.siapkan(p)
    return p


@pytest.fixture
def kon(jalur):
    with database.buka(jalur) as k:
        yield k


def _anak(kon, nama="Anak Uji", pemilik="guru-uji"):
    anak = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', ?)", (nama, pemilik)).lastrowid
    kon.commit()
    return anak


def _mulai(kon, siswa, tingkat="t3", sekarang=T0):
    kon.execute("BEGIN IMMEDIATE")
    try:
        return hs.mulai(kon, siswa, tingkat, sekarang)
    finally:
        kon.commit()


def _jawab(kon, siswa, sesi, nomor, huruf="A", sekarang=T0):
    kon.execute("BEGIN IMMEDIATE")
    try:
        return hs.jawab(kon, siswa, sesi, nomor, huruf, sekarang)
    finally:
        kon.commit()


def _kunci_huruf(kon, sesi, nomor):
    return "ABCD"[kon.execute("SELECT kunci_indeks FROM harian_soal WHERE sesi_id=? AND nomor=?", (sesi, nomor)).fetchone()[0]]


def _selesaikan(kon, siswa, sesi, sekarang=T0, benar=True):
    for n in range(1, 11):
        kunci = _kunci_huruf(kon, sesi, n)
        huruf = kunci if benar else next(h for h in "ABCD" if h != kunci)
        _jawab(kon, siswa, sesi, n, huruf, sekarang)


def _tabel(kon, nama):
    return [tuple(b) for b in kon.execute("SELECT * FROM %s ORDER BY 1, 2" % nama)]


# --- skema -------------------------------------------------------------------------------------

def test_skema_harian_idempoten_dan_tiga_tabel(jalur):
    database.siapkan(jalur)
    database.siapkan(jalur)

    with database.buka(jalur) as kon:
        nama = {b[0] for b in kon.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'harian_%'")}
    assert nama == {"harian_sesi", "harian_soal", "harian_jawaban"}


def test_skema_tidak_memakai_prefix_milik_lain():
    sumber = (AKAR / "schema_harian_latihan.py").read_text()
    tabel = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sumber)
    assert tabel and all(t.startswith("harian_") for t in tabel)


def test_skema_tidak_ber_fk_ke_tabel_sesi_guru_atau_siklus(kon):
    for tabel in ("harian_sesi", "harian_soal", "harian_jawaban"):
        tujuan = {b["table"] for b in kon.execute("PRAGMA foreign_key_list(%s)" % tabel)}
        assert tujuan <= {"siswa", "harian_sesi", "harian_soal"}, (tabel, tujuan)


def test_skema_satu_sesi_berjalan_per_anak(kon):
    anak = _anak(kon)
    kon.execute("INSERT INTO harian_sesi(siswa_id,tingkat,seed,jumlah_soal,mulai_epoch,status) VALUES (?,'t1',1,10,5,'berjalan')", (anak,))

    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_sesi(siswa_id,tingkat,seed,jumlah_soal,mulai_epoch,status) VALUES (?,'t2',2,10,6,'berjalan')", (anak,))


def test_skema_ikut_terhapus_bersama_siswa(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    _jawab(kon, anak, sesi.id, 1)

    kon.execute("DELETE FROM siswa WHERE id=?", (anak,))

    for tabel in ("harian_sesi", "harian_soal", "harian_jawaban"):
        assert kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0] == 0


# --- mulai / lanjut ----------------------------------------------------------------------------

def test_mulai_membuat_sesi_sepuluh_soal_dengan_seed_tersimpan(kon):
    anak = _anak(kon)

    sesi, baru = _mulai(kon, anak, "t3")

    assert baru and sesi.berjalan and sesi.tingkat == "t3" and sesi.jumlah_soal == 10 and sesi.terjawab == 0
    seed = kon.execute("SELECT seed FROM harian_sesi WHERE id=?", (sesi.id,)).fetchone()[0]
    assert seed == 100  # dari _seed_baru (secrets pada produksi)
    assert kon.execute("SELECT COUNT(*) FROM harian_soal WHERE sesi_id=?", (sesi.id,)).fetchone()[0] == 10


def test_soal_tersimpan_sama_dengan_rakitan_dari_seed(kon):
    import harian_rakit
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t4")

    rakitan = harian_rakit.rakit_sesi("t4", 100)

    baris = kon.execute("SELECT nomor, tanda_tangan, kunci_indeks FROM harian_soal WHERE sesi_id=? ORDER BY nomor", (sesi.id,)).fetchall()
    assert [(b["nomor"], b["tanda_tangan"], b["kunci_indeks"]) for b in baris] == [
        (r.nomor, r.soal.tanda_tangan, r.soal.kunci_indeks) for r in rakitan]


def test_mulai_lagi_saat_berjalan_melanjutkan_tanpa_menghitung_dan_tanpa_menulis(kon):
    anak = _anak(kon)
    pertama, _ = _mulai(kon, anak, "t3")
    sebelum = [_tabel(kon, t) for t in ("harian_sesi", "harian_soal")]

    kedua, baru = _mulai(kon, anak, "t5")  # tingkat lain diabaikan: sesi berjalan dilanjutkan

    assert not baru and kedua.id == pertama.id and kedua.tingkat == "t3"
    assert [_tabel(kon, t) for t in ("harian_sesi", "harian_soal")] == sebelum


def test_mulai_tingkat_tak_sah_ditolak_tanpa_efek(kon):
    anak = _anak(kon)

    for buruk in ("t7", "", None, "T1", 3):
        kon.execute("BEGIN IMMEDIATE")
        with pytest.raises(hs.TingkatTidakSah):
            hs.mulai(kon, anak, buruk, T0)
        kon.rollback()
    assert kon.execute("SELECT COUNT(*) FROM harian_sesi").fetchone()[0] == 0


def test_mulai_wajib_di_dalam_transaksi(kon):
    anak = _anak(kon)

    with pytest.raises(RuntimeError):
        hs.mulai(kon, anak, "t1", T0)


# --- batas gratis ------------------------------------------------------------------------------

def test_batas_gratis_satu_sesi_dimulai_per_hari_wib(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t3", T0)
    _selesaikan(kon, anak, sesi.id, T0)

    kon.execute("BEGIN IMMEDIATE")
    with pytest.raises(hs.BatasGratisHabis):
        hs.mulai(kon, anak, "t3", T0 + 3600)
    kon.rollback()

    assert kon.execute("SELECT COUNT(*) FROM harian_sesi").fetchone()[0] == 1


def test_batas_gratis_memakai_hari_kalender_wib_bukan_utc(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t3", T0)
    _selesaikan(kon, anak, sesi.id, T0)

    kon.execute("BEGIN IMMEDIATE")
    with pytest.raises(hs.BatasGratisHabis):  # 23:59:59 WIB hari yang sama
        hs.mulai(kon, anak, "t3", SEBELUM_TENGAH_MALAM_WIB)
    kon.rollback()
    lagi, baru = _mulai(kon, anak, "t3", TEPAT_TENGAH_MALAM_WIB)  # 00:00:00 WIB hari berikutnya

    assert baru and lagi.id != sesi.id


def test_sesi_berjalan_boleh_dilanjutkan_walau_jatah_habis(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t3", T0)

    lagi, baru = _mulai(kon, anak, "t3", T0 + 60)

    assert not baru and lagi.id == sesi.id
    _jawab(kon, anak, sesi.id, 1, "A", T0 + 61)  # menyelesaikan sesi berjalan tetap boleh


def test_tanpa_batas_untuk_akses_langganan_atau_les(kon, monkeypatch):
    anak = _anak(kon)
    monkeypatch.setattr(akses_harian, "akses", lambda k, s, kini: akses_harian.Akses(True, "les", None))
    for i in range(3):
        sesi, baru = _mulai(kon, anak, "t3", T0 + i)
        assert baru
        _selesaikan(kon, anak, sesi.id, T0 + i)


def test_batas_gratis_per_anak_bukan_per_akun_atau_global(kon):
    a, b = _anak(kon, "Anak A"), _anak(kon, "Anak B")
    sesi_a, _ = _mulai(kon, a, "t3")
    _selesaikan(kon, a, sesi_a.id)

    sesi_b, baru = _mulai(kon, b, "t3")

    assert baru and sesi_b.id != sesi_a.id


def test_akses_menerima_kini_utc_baku_dari_waktu_suntikan(kon, monkeypatch):
    anak = _anak(kon)
    dilihat = []
    asli = akses_harian.akses
    monkeypatch.setattr(akses_harian, "akses", lambda k, s, kini: (dilihat.append((s, kini)), asli(k, s, kini))[1])

    _mulai(kon, anak, "t3", T0)

    assert dilihat == [(anak, "2027-01-15T08:00:00")]


def test_kuota_melaporkan_terpakai_dan_habis(kon):
    anak = _anak(kon)
    assert hs.kuota(kon, anak, T0).habis is False
    sesi, _ = _mulai(kon, anak, "t3", T0)
    _selesaikan(kon, anak, sesi.id, T0)

    kuota = hs.kuota(kon, anak, T0 + 10)

    assert kuota.habis and kuota.terpakai == 1 and kuota.akses.sumber == "gratis"
    assert hs.kuota(kon, anak, TEPAT_TENGAH_MALAM_WIB).habis is False


# --- proyeksi aman dan giliran soal ------------------------------------------------------------

def test_muat_soal_belum_dijawab_tanpa_kunci_dan_tanpa_membaca_kolom_rahasia(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    pernyataan = []
    kon.set_trace_callback(pernyataan.append)

    soal, umpan = hs.muat_soal(kon, anak, sesi.id, 1)

    kon.set_trace_callback(None)
    assert umpan is None and len(soal.opsi) == 4 and soal.nomor == 1 and soal.jumlah == 10
    assert not any(f in s.lower() for s in pernyataan for f in ("kunci_indeks", "pembahasan"))
    assert not hasattr(soal, "kunci_indeks") and not hasattr(soal, "pembahasan")


def test_umpan_balik_hanya_setelah_dijawab_dan_memuat_kunci_dan_pembahasan(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    kunci = _kunci_huruf(kon, sesi.id, 1)
    salah = next(h for h in "ABCD" if h != kunci)

    hasil = _jawab(kon, anak, sesi.id, 1, salah)
    soal, umpan = hs.muat_soal(kon, anak, sesi.id, 1)

    assert hasil.diterima and hasil.benar is False
    assert umpan.benar is False and "ABCD"[umpan.pilihan] == salah and "ABCD"[umpan.kunci_indeks] == kunci
    assert umpan.pembahasan.strip()


def test_soal_berikutnya_tidak_bisa_dibuka_atau_dijawab_sebelum_gilirannya(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)

    for nomor in (2, 10, 0, 11, -1, "1", None):
        with pytest.raises(hs.HarianTidakDitemukan):
            hs.muat_soal(kon, anak, sesi.id, nomor)
    kon.execute("BEGIN IMMEDIATE")
    with pytest.raises(hs.HarianTidakDitemukan):
        hs.jawab(kon, anak, sesi.id, 2, "A", T0)
    kon.rollback()
    assert kon.execute("SELECT COUNT(*) FROM harian_jawaban").fetchone()[0] == 0
    _jawab(kon, anak, sesi.id, 1)
    assert hs.muat_soal(kon, anak, sesi.id, 2)[1] is None  # gilirannya tiba


def test_sesi_anak_lain_tidak_terlihat_dan_tidak_bisa_dijawab(kon):
    a, b = _anak(kon, "Anak A"), _anak(kon, "Anak B")
    sesi, _ = _mulai(kon, a)
    sebelum = _tabel(kon, "harian_jawaban")

    with pytest.raises(hs.HarianTidakDitemukan):
        hs.ambil_sesi(kon, b, sesi.id)
    with pytest.raises(hs.HarianTidakDitemukan):
        hs.muat_soal(kon, b, sesi.id, 1)
    with pytest.raises(hs.HarianTidakDitemukan):
        hs.ringkasan_sesi(kon, b, sesi.id)
    kon.execute("BEGIN IMMEDIATE")
    with pytest.raises(hs.HarianTidakDitemukan):
        hs.jawab(kon, b, sesi.id, 1, "A", T0)
    kon.rollback()
    with pytest.raises(hs.HarianTidakDitemukan):
        hs.ambil_sesi(kon, a, 9999)
    assert _tabel(kon, "harian_jawaban") == sebelum == []


# --- jawab sekali ------------------------------------------------------------------------------

def test_jawab_kedua_untuk_soal_yang_sama_ditolak_tanpa_efek(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    kunci = _kunci_huruf(kon, sesi.id, 1)
    salah = next(h for h in "ABCD" if h != kunci)
    _jawab(kon, anak, sesi.id, 1, salah, T0)
    sebelum = _tabel(kon, "harian_jawaban")

    kedua = _jawab(kon, anak, sesi.id, 1, kunci, T0 + 5)

    assert kedua.diterima is False
    assert _tabel(kon, "harian_jawaban") == sebelum
    assert sebelum[0][3] == 0  # tetap salah


def test_jawab_pilihan_tak_sah_ditolak(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)

    for buruk in ("E", "a", "", None, "AB", 1):
        kon.execute("BEGIN IMMEDIATE")
        with pytest.raises(hs.PilihanTidakSah):
            hs.jawab(kon, anak, sesi.id, 1, buruk, T0)
        kon.rollback()
    assert kon.execute("SELECT COUNT(*) FROM harian_jawaban").fetchone()[0] == 0


def test_jawaban_kesepuluh_menutup_sesi_dan_ringkasan_menghitung_benar(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    assert hs.ringkasan_sesi(kon, anak, sesi.id) is None  # masih berjalan

    for n in range(1, 11):
        kunci = _kunci_huruf(kon, sesi.id, n)
        huruf = kunci if n <= 7 else next(h for h in "ABCD" if h != kunci)
        hasil = _jawab(kon, anak, sesi.id, n, huruf, T0 + n)

    assert hasil.selesai
    tutup = hs.ambil_sesi(kon, anak, sesi.id)
    assert tutup.status == "selesai" and tutup.selesai_epoch == T0 + 10 and tutup.terjawab == 10
    assert hs.ringkasan_sesi(kon, anak, sesi.id) == hs.RingkasanSesi("t3", 10, 7)
    assert hs.sesi_berjalan(kon, anak) is None


def test_jawab_setelah_sesi_selesai_ditolak_tanpa_efek(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak)
    _selesaikan(kon, anak, sesi.id)
    sebelum = _tabel(kon, "harian_jawaban")

    assert _jawab(kon, anak, sesi.id, 10, "A").diterima is False
    assert _tabel(kon, "harian_jawaban") == sebelum


# --- hari latihan dan ringkasan ----------------------------------------------------------------

def test_hari_latihan_dan_ringkasan_tujuh_hari(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t2", T0 - 2 * 86400)
    for n in range(1, 6):
        _jawab(kon, anak, sesi.id, n, _kunci_huruf(kon, sesi.id, n) if n <= 3 else "ABCD"["ABCD".index(_kunci_huruf(kon, sesi.id, n)) - 1], T0 - 2 * 86400)

    ringkas = hs.ringkasan_harian(kon, anak, T0)

    assert ringkas.tingkat_terakhir == "t2" and ringkas.soal_dikerjakan == 5 and ringkas.soal_benar == 3
    assert ringkas.persen_benar == 60 and ringkas.jumlah_hari == 1
    assert [t for t, ada in ringkas.hari if ada] == [harian_waktu.tanggal_wib(T0 - 2 * 86400)]
    assert len(ringkas.hari) == 7 and ringkas.hari[-1][0] == harian_waktu.tanggal_wib(T0)


def test_ringkasan_harian_kosong_dan_tidak_membaca_anak_lain(kon):
    a, b = _anak(kon, "Anak A"), _anak(kon, "Anak B")
    sesi, _ = _mulai(kon, a, "t2")
    _jawab(kon, a, sesi.id, 1)

    ringkas = hs.ringkasan_harian(kon, b, T0)

    assert ringkas.soal_dikerjakan == 0 and ringkas.persen_benar is None and ringkas.tingkat_terakhir is None
    assert ringkas.jumlah_hari == 0


def test_ringkasan_hanya_tujuh_hari_terakhir(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t2", T0 - 8 * 86400)
    _jawab(kon, anak, sesi.id, 1, "A", T0 - 8 * 86400)

    assert hs.ringkasan_harian(kon, anak, T0).soal_dikerjakan == 0


def test_hari_latihan_pekan_menandai_hari_yang_ada_jawaban(kon):
    anak = _anak(kon)
    sesi, _ = _mulai(kon, anak, "t2", T0)
    _jawab(kon, anak, sesi.id, 1, "A", T0)

    pekan = hs.hari_latihan(kon, anak, harian_waktu.pekan_wib(T0), T0)

    assert len(pekan) == 7 and [t for t, ada in pekan if ada] == [harian_waktu.tanggal_wib(T0)]


# --- bukan bukti siklus ------------------------------------------------------------------------

def test_sesi_penuh_tidak_mengubah_satu_pun_tabel_non_harian(kon):
    anak = _anak(kon)
    kon.commit()
    daftar = [b[0] for b in kon.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'harian_%' AND name NOT LIKE 'sqlite_%'")]
    sebelum = {t: [tuple(r) for r in kon.execute("SELECT * FROM %s" % t)] for t in daftar}

    sesi, _ = _mulai(kon, anak, "t5")
    _selesaikan(kon, anak, sesi.id)
    hs.muat_soal(kon, anak, sesi.id, 1)
    hs.ringkasan_sesi(kon, anak, sesi.id)
    hs.ringkasan_harian(kon, anak, T0)

    assert {t: [tuple(r) for r in kon.execute("SELECT * FROM %s" % t)] for t in daftar} == sebelum
    assert "soal" in daftar and "sesi" in daftar and "diagnosis" in daftar


def test_modul_harian_tidak_menyebut_learning_cycle_atau_tabel_bukti():
    for nama in ("harian_latihan_store.py", "harian_http.py", "harian_pages.py", "harian_rakit.py", "harian_pg.py"):
        jalur = AKAR / nama
        if not jalur.exists():
            continue
        teks = jalur.read_text()
        assert "import learning_cycle" not in teks and "from learning_cycle" not in teks, nama
        assert not re.search(r"(INSERT INTO|UPDATE|DELETE FROM)\s+(sesi|sesi_soal|jawaban|diagnosis|soal)\b", teks), nama
