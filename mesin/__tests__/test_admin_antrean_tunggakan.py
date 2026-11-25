"""Antrean "Perlu ditangani" untuk tunggakan paket kelas: tingkat, hitungan, urutan, batas, dan galat baca.

Data sintetis. Bagian lain antrean dibuat kosong (operasi dan backup dipalsukan) supaya asersi hanya menyentuh
tunggakan. Tes nyata memakai ledger kelas sementara, bukan stub.
"""
from datetime import datetime, timedelta, timezone

import pytest

import admin_antrean as A
import admin_antrean_bayar as B
import admin_antrean_pages as AP
import admin_operations
import admin_queries as Q
import admin_store
import kelas_admin_pages
import kelas_kit as kk
import kelas_tunggakan as kt
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

SEKARANG = 1_760_000_000.0  # 2025-10-09; sintetis
KONTEKS_KOSONG = Q.KonteksAdmin((), (), ())
FORMAT = "%Y-%m-%dT%H:%M:%S"
KALIMAT_TINDAK_LANJUT = ("Hubungi orang tua: ajak ikut kelas lagi atau tanyakan umpan balik.")


def _tg(siswa_id, hari, paket="mini", nama="Mini Class"):
    return kt.Tunggakan(siswa_id, paket, nama, "2026-10-01T09:30:00", hari)


def _epoch(baku):
    return datetime.strptime(baku, FORMAT).replace(tzinfo=timezone.utc).timestamp()


def _kumpulkan(path):
    return A.kumpulkan(KONTEKS_KOSONG, path, sekarang=SEKARANG)


def _pakai_tunggakan(monkeypatch, daftar):
    monkeypatch.setattr(B, "kelas_tunggakan", lambda path, sekarang_iso: tuple(daftar))


@pytest.fixture
def tanpa_operasi(monkeypatch):
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))


@pytest.fixture
def satu_operasi_layanan(monkeypatch):
    baris = ({"sumber": "layanan", "ref": "op1", "akun": "x", "status": "uncertain", "waktu": SEKARANG},)
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: (baris, 1))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))


# --- item dan tingkat ----------------------------------------------------------------------------

def test_tingkat_tinjau_untuk_30_59_dan_penting_untuk_60_ke_atas(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(1, 75), _tg(2, 60), _tg(3, 59), _tg(4, 30)])
    hasil = _kumpulkan(tmp_path / "belum-ada.db")
    assert [(i.judul, i.tingkat) for i in hasil.item] == [
        ("Paket Mini Class anak #1 belum diperpanjang", "penting"),
        ("Paket Mini Class anak #2 belum diperpanjang", "penting"),
        ("Paket Mini Class anak #3 belum diperpanjang", "tinjau"),
        ("Paket Mini Class anak #4 belum diperpanjang", "tinjau"),
    ]


def test_item_tunggakan_membawa_jalur_admin_kelas_dan_kalimat_tindak_lanjut(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(7, 45, "private", "Private")])
    (item,) = _kumpulkan(tmp_path / "belum-ada.db").item
    assert item.judul == "Paket Private anak #7 belum diperpanjang"
    assert item.deskripsi == "berakhir 45 hari lalu. " + KALIMAT_TINDAK_LANJUT
    assert item.jalur == kelas_admin_pages.RUTE and item.cta == "Tinjau paket"
    assert item.umur_hari == 45 and item.ref == ""


def test_item_tunggakan_tidak_menampilkan_nama_anak_atau_kontak(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(9, 80)])
    html = AP.render_antrean(_kumpulkan(tmp_path / "belum-ada.db"))
    assert "anak #9" in html and "@" not in html


# --- hitungan dan sinyal -------------------------------------------------------------------------

def test_hitungan_tinjau_tidak_dihitung_penting_dihitung(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(1, 75), _tg(2, 45), _tg(3, 40)])
    hasil = _kumpulkan(tmp_path / "belum-ada.db")
    assert hasil.total == 3 and hasil.mendesak == 0
    assert hasil.perlu_keputusan == 1
    assert AP.sinyal_dari(hasil).total == 1
    assert hasil.transfer_menunggu == 0 and hasil.kelas_menunggu == 0


def test_tinjau_tunggakan_tampil_di_dalam_lipatan_tinjauan_ringan(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(3, 40)])
    html = AP.render_antrean(_kumpulkan(tmp_path / "belum-ada.db"))
    awal = html.index('<details class="admin-antrean-tinjau">')
    assert "Tinjauan ringan (1)" in html[awal:html.index("</details>")]


# --- urutan dan batas ----------------------------------------------------------------------------

def test_mendesak_tetap_di_depan_dan_tidak_tergeser_tunggakan_saat_batas_terlampaui(
        monkeypatch, satu_operasi_layanan, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(n, 70) for n in range(1, 61)])
    hasil = _kumpulkan(tmp_path / "belum-ada.db")
    assert hasil.item[0].tingkat == "mendesak" and hasil.item[0].judul.startswith("Operasi layanan")
    assert all(i.tingkat == "penting" for i in hasil.item[1:])
    assert len(hasil.item) == AP.BATAS_BARIS == 50
    assert hasil.total == 61 and hasil.mendesak == 1 and hasil.perlu_keputusan == 61
    assert "dan 11 lainnya" in AP.render_antrean(hasil)


def test_penting_tunggakan_di_depan_tinjau_walau_urutan_masukan_campur(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [_tg(1, 31), _tg(2, 90), _tg(3, 35), _tg(4, 61)])
    hasil = _kumpulkan(tmp_path / "belum-ada.db")
    assert [i.tingkat for i in hasil.item] == ["penting", "penting", "tinjau", "tinjau"]
    assert [i.judul for i in hasil.item[:2]] == [
        "Paket Mini Class anak #2 belum diperpanjang", "Paket Mini Class anak #4 belum diperpanjang"]


def test_tanpa_tunggakan_antrean_kosong_seperti_sebelumnya(monkeypatch, tanpa_operasi, tmp_path):
    _pakai_tunggakan(monkeypatch, [])
    hasil = _kumpulkan(tmp_path / "belum-ada.db")
    assert hasil.item == () and hasil.total == 0 and hasil.perlu_keputusan == 0


# --- galat baca dan ledger nyata -----------------------------------------------------------------

def test_kelas_belum_dipasang_atau_tak_terbaca_berarti_kosong(tmp_path):
    iso = "2026-11-25T00:00:00"
    kosong = tmp_path / "admin-kosong.db"
    admin_store.siapkan(kosong, sekarang=1)  # skema admin ada, namespace kelas belum
    rusak = tmp_path / "bukan-db.db"
    rusak.write_bytes(b"bukan sqlite")
    for path in (kosong, rusak, tmp_path / "tidak-ada.db"):
        assert B.kelas_tunggakan(path, iso) == ()


def test_ledger_kelas_nyata_menghasilkan_item_tinjau_setelah_45_hari(db_kelas, kon_kelas, tanpa_operasi):
    kk.lunas(kon_kelas, 1, "mini", 1)
    berakhir = kon_kelas.execute("SELECT MAX(berakhir) FROM kelas_akses").fetchone()[0]
    sekarang = datetime.strptime(berakhir, FORMAT) + timedelta(days=45)
    hasil = A.kumpulkan(KONTEKS_KOSONG, db_kelas, sekarang=sekarang.replace(tzinfo=timezone.utc).timestamp())
    (item,) = hasil.item
    assert item.judul == "Paket Mini Class anak #1 belum diperpanjang"
    assert item.tingkat == "tinjau" and item.umur_hari == 45
    assert hasil.kelas_menunggu == 0 and hasil.total == 1 and hasil.perlu_keputusan == 0
