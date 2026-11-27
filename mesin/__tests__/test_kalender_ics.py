"""Simpan ke kalender: format iCalendar (RFC 5545), UID stabil, tanpa PII, dan rute GET `/murid/paket/kalender.ics` (data sintetis).

Format diuji langsung pada `kalender_ics`; rute diuji lewat server loopback (`kelas_http_kit`): hanya pemilik jadwal yang
mendapat berkas, selain itu 404 identik dengan rute tak ada.
"""
import re

import pytest

import admin_store
import jadwal_store as js
import kalender_ics
import kelas_putusan
import kelas_store
import schema_jadwal
from bukti_kit import JPEG
from kelas_http_kit import (ADMIN, AWAL, M, bukti_terakhir, buat_dan_unggah, buat_murid, jam,  # noqa: F401
                            kidup, kirim, kmati, minta_mentah, server, token)

KAL = M + "/kalender.ics"
GURU = "akun_" + "9" * 32
LOKASI = "https://meet.google.com/rahasia-kelas-xyz"
KUNCI = "kor_" + "ab" * 16
SEKARANG = "2026-11-25T03:00:00"
JADWAL = {"lokasi": LOKASI, "sesi": [
    {"ke": 1, "mulai": "2026-11-26T02:00:00", "menit": 60, "dibatalkan": False},
    {"ke": 2, "mulai": "2026-11-28T02:00:00", "menit": 60, "dibatalkan": True},
]}


def _baris(isi: bytes) -> list:
    return isi.decode("utf-8").split("\r\n")


# --- format (pure) -----------------------------------------------------------------------------

def test_escape_teks_mengikuti_rfc_backslash_lebih_dulu_lalu_separator_dan_baris_baru():
    assert kalender_ics.escape_teks("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    assert kalender_ics.escape_teks("baris\r\nbaru") == "baris\\nbaru"


def test_lipat_maks_75_oktet_dan_tidak_memotong_karakter_multibyte():
    baris = "ä" * 100
    potongan = kalender_ics.lipat(baris)
    assert all(len(p.encode("utf-8")) <= 75 for p in potongan)
    assert all(p.startswith(" ") for p in potongan[1:]) and not potongan[0].startswith(" ")
    assert "".join([potongan[0]] + [p[1:] for p in potongan[1:]]) == baris


def test_berkas_memakai_crlf_tanpa_lf_telanjang_dan_diakhiri_crlf():
    isi = kalender_ics.bangun(KUNCI, JADWAL, SEKARANG)
    assert isi.endswith(b"\r\n") and isi.count(b"\n") == isi.count(b"\r\n")
    baris = _baris(isi)
    assert baris[0] == "BEGIN:VCALENDAR" and baris[-2] == "END:VCALENDAR" and baris[-1] == ""
    assert all(len(b.encode("utf-8")) <= 75 for b in baris)
    assert "VERSION:2.0" in baris and "CALSCALE:GREGORIAN" in baris


def test_vevent_per_pertemuan_dengan_waktu_utc_dan_status_dibatalkan():
    baris = _baris(kalender_ics.bangun(KUNCI, JADWAL, SEKARANG))
    assert baris.count("BEGIN:VEVENT") == baris.count("END:VEVENT") == 2
    assert "DTSTART:20261126T020000Z" in baris and "DTEND:20261126T030000Z" in baris
    assert "SUMMARY:Kelas Jagomat - pertemuan 1" in baris and "STATUS:CONFIRMED" in baris
    assert "SUMMARY:Kelas Jagomat - pertemuan 2" in baris and "STATUS:CANCELLED" in baris


def test_uid_stabil_saat_unduhan_diulang_dan_tidak_memuat_kunci_mentah():
    pertama = [b for b in _baris(kalender_ics.bangun(KUNCI, JADWAL, SEKARANG)) if b.startswith("UID:")]
    kedua = [b for b in _baris(kalender_ics.bangun(KUNCI, JADWAL, "2026-11-27T09:00:00")) if b.startswith("UID:")]
    assert pertama == kedua and len(set(pertama)) == 2
    assert all(re.fullmatch(r"UID:[0-9a-f]{32}@jagomat\.id", b) for b in pertama)
    assert all(KUNCI not in b for b in pertama)


def test_uid_beda_untuk_order_berbeda_meski_nomor_pertemuan_sama():
    satu = [b for b in _baris(kalender_ics.bangun(KUNCI, JADWAL, SEKARANG)) if b.startswith("UID:")]
    lain = [b for b in _baris(kalender_ics.bangun("kor_" + "cd" * 16, JADWAL, SEKARANG)) if b.startswith("UID:")]
    assert not set(satu) & set(lain)


def test_berkas_tanpa_nama_guru_kontak_atau_lokasi():
    teks = kalender_ics.bangun(KUNCI, JADWAL, SEKARANG).decode("utf-8")
    assert LOKASI not in teks and GURU not in teks and "@" not in teks.replace("@jagomat.id", "")
    assert "LOCATION" not in teks and "ORGANIZER" not in teks and "ATTENDEE" not in teks


def test_jadwal_tanpa_sesi_menghasilkan_kalender_kosong_yang_valid():
    baris = _baris(kalender_ics.bangun(KUNCI, {"lokasi": "Online", "sesi": []}, SEKARANG))
    assert baris[0] == "BEGIN:VCALENDAR" and "BEGIN:VEVENT" not in baris and baris[-2] == "END:VCALENDAR"


# --- rute (server loopback) -------------------------------------------------------------------

@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def _aktifkan(server, murid):
    order_id = buat_dan_unggah(server, murid, "mini", JPEG)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _tempatkan(server, murid):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid = js.buat_kelompok(kon, ADMIN, nama="Mini A", lokasi=LOKASI, guru_id=GURU, kuota=5,
                               tanggal="2026-11-24", jam="09:00", sekarang=AWAL)
    data = {"token": token(murid.akun, "jadwal_pilih:" + kid), "kelompok": kid}
    assert kirim(server, M + "/jadwal", murid, data)[0] == 303
    return kid


def test_pemilik_jadwal_mendapat_berkas_ics_sebagai_lampiran(siap):
    _aktifkan(siap, siap.a)
    _tempatkan(siap, siap.a)
    kode, isi, header = minta_mentah(siap, KAL, siap.a.akun)
    assert kode == 200
    assert header["Content-Type"] == "text/calendar; charset=utf-8"
    assert header["Content-Disposition"].startswith("attachment;")
    assert header["Cache-Control"] == "no-store" and header["X-Content-Type-Options"] == "nosniff"
    assert "BEGIN:VCALENDAR\r\nVERSION:2.0" in isi and "DTSTART:20261124T020000Z" in isi
    assert "SUMMARY:Kelas Jagomat - pertemuan 1" in isi
    assert all(x not in isi for x in ("Anak Alfa", GURU, LOKASI, "murid-a", siap.a.id_akun, "kor_"))


def test_murid_tanpa_jadwal_mendapat_404_identik_dengan_tagihan_tak_ada(siap):
    _aktifkan(siap, siap.a)
    _tempatkan(siap, siap.a)
    kode_b, isi_b, _ = minta_mentah(siap, KAL, siap.b.akun)
    kode_ref, isi_ref, _ = minta_mentah(siap, M + "/tagihan?kode=mini", siap.b.akun)
    assert kode_b == kode_ref == 404 and isi_b == isi_ref


def test_tanpa_sesi_tidak_membocorkan_berkas_dan_sama_dengan_rute_paket(siap):
    _aktifkan(siap, siap.a)
    _tempatkan(siap, siap.a)
    kode_kal, isi_kal, _ = minta_mentah(siap, KAL)
    kode_paket, isi_paket, _ = minta_mentah(siap, M)
    assert "BEGIN:VCALENDAR" not in isi_kal and kode_kal == kode_paket
    assert isi_kal == isi_paket


def test_halaman_paket_memuat_tautan_simpan_ke_kalender_hanya_bila_ada_jadwal(siap):
    _aktifkan(siap, siap.a)
    _tempatkan(siap, siap.a)
    assert 'href="/murid/paket/kalender.ics"' in minta_mentah(siap, M, siap.a.akun)[1]
    assert "Simpan ke kalender" not in minta_mentah(siap, M, siap.b.akun)[1]


def test_sakelar_mati_rute_kalender_menjawab_seperti_rute_murid_asing(siap, monkeypatch):
    _aktifkan(siap, siap.a)
    _tempatkan(siap, siap.a)
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    kode_kal, isi_kal, _ = minta_mentah(siap, KAL, siap.a.akun)
    kode_asing, isi_asing, _ = minta_mentah(siap, M + "/tidak-ada", siap.a.akun)
    assert "BEGIN:VCALENDAR" not in isi_kal and (kode_kal, isi_kal) == (kode_asing, isi_asing)
