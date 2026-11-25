"""Antrean dan penanda admin untuk bukti transfer Latihan Harian dan Paket Belajar (data sintetis, read-only).

Latar: bukti Rp39.000 Latihan Harian sudah masuk ledger tetapi tidak terlihat di Pesanan (hanya Peta), tanpa lencana.
Tes memakai ledger nyata di DB sementara, bukan stub, supaya pembaca dan penyambungannya terbukti.
"""
from datetime import datetime, timezone

import pytest

import admin_antrean as A
import admin_antrean_bayar as B
import admin_antrean_pages as AP
import admin_operations
import admin_pages
import admin_pesanan_pages as pesanan_ui
import database
import harian_langganan_putusan as hp
import harian_langganan_store as hs
import kelas_putusan
import kelas_kit as kk
from kelas_kit import db_kelas, kon_kelas  # noqa: F401
import admin_queries as Q

T0 = "2026-11-23T03:00:00"
T_UNGGAH = "2026-11-23T03:10:00"
ADMIN = "admin_sintetis"
SEKARANG = datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp()
KONTEKS_KOSONG = Q.KonteksAdmin((), (), ())


@pytest.fixture
def belajar(tmp_path, monkeypatch):
    """DB belajar sintetis yang dipakai `database.buka()` tanpa argumen (bukan DB asli)."""
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    with database.buka(jalur) as kon:
        yield kon


@pytest.fixture(autouse=True)
def tanpa_operasi(monkeypatch):
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))


def _anak(kon, nama="Anak Uji"):
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', 'guru')", (nama,)).lastrowid
    kon.commit()
    return siswa


def _harian_menunggu(kon, nomor=1, waktu=T0, unggah=T_UNGGAH, nama="Anak Uji"):
    siswa = _anak(kon, nama)
    tagihan = hs.buat_tagihan(kon, siswa, "bulanan", waktu)
    bukti = hs.catat_bukti(kon, siswa, "image/png", 100, "%064x" % nomor, "%032x" % nomor, unggah)
    return tagihan, bukti["bukti_id"]


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def _kumpulkan(path_admin):
    return A.kumpulkan(KONTEKS_KOSONG, path_admin, sekarang=SEKARANG)


# --- pembaca -----------------------------------------------------------------------------------

def test_harian_bukti_menunggu_terbaca_dan_hilang_setelah_diputuskan(belajar):
    tagihan, bukti_id = _harian_menunggu(belajar)
    ada = B.harian_menunggu(T_UNGGAH)
    assert [(t.order_id, t.nominal, t.diunggah) for t in ada] == [
        (tagihan["order_id"], tagihan["nominal_transfer"], T_UNGGAH)]
    hp.setujui(belajar, tagihan["order_id"], ADMIN, T_UNGGAH, bukti_dilihat=bukti_id)
    assert B.harian_menunggu(T_UNGGAH) == ()


def test_harian_tagihan_tanpa_bukti_belum_menunggu_verifikasi(belajar):
    hs.buat_tagihan(belajar, _anak(belajar), "bulanan", T0)
    assert B.harian_menunggu(T_UNGGAH) == ()


def test_harian_terlama_dulu_dan_tanpa_nama_anak(belajar):
    baru, _ = _harian_menunggu(belajar, 2, "2026-11-23T05:00:00", "2026-11-23T05:10:00", "Nama Rahasia B")
    lama, _ = _harian_menunggu(belajar, 1, T0, T_UNGGAH, "Nama Rahasia A")
    ada = B.harian_menunggu(T_UNGGAH)
    assert [t.order_id for t in ada] == [lama["order_id"], baru["order_id"]]
    assert "Rahasia" not in repr(ada)


def test_kelas_bukti_menunggu_terbaca_dan_hilang_setelah_diputuskan(db_kelas, kon_kelas):
    tagihan, bukti_id = kk.menunggu(kon_kelas)
    ada = B.kelas_menunggu(db_kelas)
    assert len(ada) == 1 and ada[0].order_id == tagihan.order_id
    assert ada[0].nominal == tagihan.total and ada[0].diunggah == kk.SESUDAH_UPLOAD
    kk.setuju(kon_kelas, tagihan, bukti_id)
    assert B.kelas_menunggu(db_kelas) == ()


def test_ledger_belum_dipasang_atau_tak_terbaca_berarti_kosong(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BAWAAN", tmp_path / "kosong-belajar.db")
    assert B.harian_menunggu(T_UNGGAH) == ()
    assert B.kelas_menunggu(tmp_path / "tidak-ada.db") == ()
    (tmp_path / "bukan-db.db").write_bytes(b"bukan sqlite")
    assert B.kelas_menunggu(tmp_path / "bukan-db.db") == ()


# --- antrean "Perlu ditangani" dan penanda sidebar ---------------------------------------------

def test_antrean_memuat_harian_dan_kelas_sebagai_mendesak_dengan_tautan_halaman_acc(belajar, db_kelas, kon_kelas):
    harian, _ = _harian_menunggu(belajar)
    kelas, _ = kk.menunggu(kon_kelas)
    antrean = _kumpulkan(db_kelas)
    assert (antrean.harian_menunggu, antrean.kelas_menunggu, antrean.transfer_menunggu) == (1, 1, 0)
    assert antrean.mendesak == 2 and antrean.perlu_keputusan == 2 and antrean.total == 2
    judul = {i.judul: i for i in antrean.item}
    item_harian = judul["Langganan Latihan Harian: transfer menunggu verifikasi"]
    item_kelas = judul["Paket Belajar: transfer menunggu verifikasi"]
    assert item_harian.jalur == "/admin/langganan/verifikasi?order=" + harian["order_id"]
    assert item_kelas.jalur == "/admin/kelas/verifikasi?order=" + kelas.order_id
    assert {item_harian.tingkat, item_kelas.tingkat} == {"mendesak"}
    assert "Rp" in item_harian.deskripsi and "Anak Uji" not in item_harian.deskripsi


def test_antrean_tanpa_bukti_menunggu_tidak_menambah_hitungan(belajar, db_kelas):
    antrean = _kumpulkan(db_kelas)
    assert (antrean.harian_menunggu, antrean.kelas_menunggu, antrean.mendesak, antrean.total) == (0, 0, 0, 0)


def test_sinyal_nav_membawa_hitungan_ketiga_jalur(belajar, db_kelas, kon_kelas):
    _harian_menunggu(belajar)
    kk.menunggu(kon_kelas)
    sinyal = AP.sinyal_dari(_kumpulkan(db_kelas))
    assert (sinyal.harian_menunggu, sinyal.kelas_menunggu, sinyal.transfer_menunggu) == (1, 1, 0)
    assert sinyal.total == 2


def test_badge_menu_langganan_harian_dan_paket_belajar_masing_masing(belajar):
    sinyal = AP.SinyalNav(total=3, mendesak=3, transfer_menunggu=1, harian_menunggu=2, kelas_menunggu=0)
    harian = admin_pages._badge_nav(sinyal, "langganan_harian")
    assert 'class="admin-nav-badge">2<' in harian and " transfer menunggu verifikasi" in harian
    assert admin_pages._badge_nav(sinyal, "kelas_belajar") == ""
    assert 'class="admin-nav-badge">1<' in admin_pages._badge_nav(sinyal, "pesanan")
    kelas = admin_pages._badge_nav(AP.SinyalNav(total=1, kelas_menunggu=1), "kelas_belajar")
    assert 'class="admin-nav-badge">1<' in kelas
    assert admin_pages._badge_nav(None, "langganan_harian") == ""
    nav = admin_pages._nav("ringkasan", sinyal)
    assert nav.count("transfer menunggu verifikasi") == 2  # pesanan + langganan harian; kelas 0


# --- halaman Pesanan menunjuk ke jalur lain ----------------------------------------------------

def test_halaman_pesanan_menautkan_langganan_harian_dan_paket_belajar():
    isi = pesanan_ui.halaman({"items": [], "total": 0}, halaman=1, gerbang_terbuka=True, hasil=None)
    assert 'href="/admin/langganan"' in isi and 'href="/admin/kelas"' in isi
    assert "hanya pesanan Peta Kemampuan" in isi


# --- pembayaran belum dibayar (butir QA #8, 25 Nov 2026) ----------------------------------------
# Order yang dibuat tetapi belum ada bukti transfer tidak boleh tampil sebagai "mendesak" (belum ada yang
# diperiksa), tetapi admin perlu melihat bahwa ada pembeli yang menggantung. Satu butir tinjau, terpisah dari
# hitungan menunggu verifikasi, tanpa nama atau kontak.

TAUTAN_BELUM_BAYAR = "/admin/pembayaran?status=belum_bayar"
KINI_BELUM_BAYAR = "2026-11-23T20:00:00"  # 4 jam sebelum SEKARANG: jendela 24 jam masih terbuka


def _item_belum_bayar(antrean):
    return [i for i in antrean.item if i.jalur == TAUTAN_BELUM_BAYAR]


def test_belum_bayar_dua_jalur_jadi_satu_butir_tinjau_tanpa_mengubah_hitungan_mendesak(belajar, db_kelas, kon_kelas):
    hs.buat_tagihan(belajar, _anak(belajar, "Nama Rahasia"), "bulanan", T0)
    kk.tagih(kon_kelas, sekarang=KINI_BELUM_BAYAR)
    antrean = _kumpulkan(db_kelas)
    (item,) = _item_belum_bayar(antrean)
    assert item.tingkat == "tinjau" and item.judul.startswith("2 pembayaran belum dibayar")
    assert "Rahasia" not in item.judul + item.deskripsi
    assert (antrean.mendesak, antrean.perlu_keputusan) == (0, 0)
    assert (antrean.transfer_menunggu, antrean.harian_menunggu, antrean.kelas_menunggu) == (0, 0, 0)
    assert antrean.total == 1
    assert AP.sinyal_dari(antrean).total == 0


def test_belum_bayar_kedaluwarsa_dan_sudah_ada_bukti_tidak_dihitung(belajar, db_kelas, kon_kelas):
    kk.tagih(kon_kelas, sekarang=kk.KINI)  # jendela 24 jam sudah lewat pada SEKARANG
    _harian_menunggu(belajar)  # sudah ada bukti: urusan antrean transfer, bukan belum bayar
    antrean = _kumpulkan(db_kelas)
    assert _item_belum_bayar(antrean) == []
    assert antrean.harian_menunggu == 1


def test_belum_bayar_nol_tidak_menambah_butir(belajar, db_kelas):
    antrean = _kumpulkan(db_kelas)
    assert _item_belum_bayar(antrean) == [] and antrean.total == 0


def test_pembaca_belum_bayar_ledger_tak_terbaca_berarti_nol(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BAWAAN", tmp_path / "kosong-belajar.db")
    assert B.belum_bayar(tmp_path / "tidak-ada.db", "2026-11-24T00:00:00") == 0


# --- paket aktif belum ditempatkan (butir QA #4, notifikasi admin; 25 Nov 2026) ---------------------------------
# Pembeli sudah bayar dan disetujui, tetapi jadwal belum ada: admin perlu menindaklanjuti (menempatkan atau menghubungi).

JALUR_PERLU_DITEMPATKAN = "/admin/kelas"
GURU_UJI = "akun_" + "9" * 32


def _item_perlu_ditempatkan(antrean):
    return [i for i in antrean.item if "belum ditempatkan" in i.judul]


def test_paket_aktif_belum_ditempatkan_jadi_butir_penting_dengan_tautan_ke_admin_kelas(db_kelas, kon_kelas):
    import schema_jadwal
    schema_jadwal.migrasikan(db_kelas)
    kk.lunas(kon_kelas, siswa=7, n=1)
    kk.lunas(kon_kelas, siswa=8, n=2)
    antrean = _kumpulkan(db_kelas)
    (item,) = _item_perlu_ditempatkan(antrean)
    assert item.judul.startswith("2 paket aktif belum ditempatkan") and item.tingkat == "penting"
    assert item.jalur == JALUR_PERLU_DITEMPATKAN
    assert antrean.mendesak == 0 and antrean.perlu_keputusan == 1 and antrean.total == 1
    assert AP.sinyal_dari(antrean).total == 1


def test_paket_yang_sudah_ditempatkan_tidak_dihitung(db_kelas, kon_kelas):
    import jadwal_store as js
    import schema_jadwal
    schema_jadwal.migrasikan(db_kelas)
    tagihan = kk.lunas(kon_kelas, siswa=7)
    with js.buka(db_kelas, tulis_data=True) as kon:
        kelompok = js.buat_kelompok(kon, ADMIN, nama="Mini A", lokasi="https://meet.google.com/abc-defg-hij",
                                    guru_id=GURU_UJI, kuota=5, tanggal="2026-11-26", jam="09:00", sekarang=kk.KINI)
        js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok, sekarang=kk.SESUDAH_UPLOAD)
    assert _item_perlu_ditempatkan(_kumpulkan(db_kelas)) == []


def test_tanpa_tabel_jadwal_penempatan_tidak_diketahui_tidak_dihitung(db_kelas, kon_kelas):
    kk.lunas(kon_kelas, siswa=7)
    assert _item_perlu_ditempatkan(_kumpulkan(db_kelas)) == []
    assert B.belum_ditempatkan(db_kelas, "2026-11-24T00:00:00") == 0


def test_pembaca_belum_ditempatkan_ledger_tak_terbaca_berarti_nol(tmp_path):
    assert B.belum_ditempatkan(tmp_path / "tidak-ada.db", "2026-11-24T00:00:00") == 0
