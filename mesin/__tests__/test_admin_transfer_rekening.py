"""Halaman admin pengaturan rekening transfer: form, optimistic concurrency, mask, audit, guard.

Data SINTETIS (nomor rekening contoh fiktif). Nomor lengkap tidak boleh tampil di halaman, audit, atau galat.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import pesanan_rekening  # noqa: E402
from admin_transfer_kit import (  # noqa: E402
    AKSI_REKENING, HALAMAN, LINTAS_SITUS, REKENING, TAK_ADA, id_admin, isian_rekening, kirim_rekening,
    login_admin, minta_admin, teks_halaman, token_rekening,
)
from cek_http_kit import AKUN_ADMIN  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    ATAS_NAMA, BANK, NOMOR, STATUS, AKUN_A, bayar, jam, keluarga, minta_mentah, server, siap_order,
    tertutup, transfer,
)
from pesanan_transfer_http_kit import pasang_runtime, atur_tahap  # noqa: E402

NOMOR_BARU = "9876543210"
POLA_HASIL = re.compile(r"/admin/pesanan/rekening\?hasil=([a-z_]+)")


@pytest.fixture()
def admin(transfer):
    return login_admin(transfer)


@pytest.fixture()
def kosong(bayar):
    """Skema rekening terpasang tetapi belum diisi (bukan fixture `transfer` yang sudah mengisi)."""
    pesanan_rekening.migrasikan(admin_store.BAWAAN, sekarang=10)
    return bayar


def _snapshot():
    cfg = pesanan_rekening.baca(admin_store.BAWAAN)
    return (0, pesanan_rekening.SIDIK_KOSONG) if cfg is None else (cfg.revisi, pesanan_rekening.sidik_konfigurasi(cfg))


def _stempel():
    return _baca_tabel("rekening_konfigurasi"), _baca_tabel("rekening_audit")


def _baca_tabel(nama):
    import sqlite3
    with sqlite3.connect(admin_store.BAWAAN) as kon:
        kon.row_factory = sqlite3.Row
        return [dict(r) for r in kon.execute("SELECT * FROM %s ORDER BY 1" % nama)]


def _hasil(tajuk) -> str:
    cocok = POLA_HASIL.fullmatch(tajuk["Location"])
    assert cocok, tajuk["Location"]
    return cocok.group(1)


# --- tampilan ---------------------------------------------------------------------

def test_halaman_terisi_menampilkan_nomor_ter_mask_dan_form_dengan_token(transfer, admin):
    kode, isi, tajuk = minta_admin(transfer, REKENING, admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    assert NOMOR not in isi and re.search(r"\*{6}7890", isi)
    assert BANK in isi and ATAS_NAMA in isi
    for nama in ("nama_bank", "nomor_rekening", "atas_nama", "csrf", "tinjauan", "reauth"):
        assert 'name="%s"' % nama in isi
    assert 'autocomplete="off"' in isi.split('name="nomor_rekening"')[1].split(">")[0]
    assert 'inputmode="numeric"' in isi


def test_halaman_belum_diisi_menjelaskan_transfer_tetap_tertutup(kosong):
    kode, isi, _t = minta_admin(kosong, REKENING, login_admin(kosong))
    assert kode == 200 and "belum diisi" in isi.lower() and "tetap tertutup" in isi
    assert 'name="nomor_rekening"' in isi


def test_halaman_skema_belum_dipasang_memberi_petunjuk_migrasi_tanpa_form(bayar):
    kode, isi, _t = minta_admin(bayar, REKENING, login_admin(bayar))
    assert kode == 503 and "pesanan_transfer_migrasi" in isi
    assert 'name="nomor_rekening"' not in isi


def test_halaman_basic_auth_baca_saja_tanpa_form(transfer):
    kode, isi, _t = minta_mentah(transfer, REKENING, AKUN_ADMIN)
    assert kode == 200 and 'name="nomor_rekening"' not in isi and NOMOR not in isi


def test_halaman_menunjukkan_status_sakelar_transfer(transfer, admin, monkeypatch):
    assert "Sakelar transfer: aktif" in teks_halaman(minta_admin(transfer, REKENING, admin)[1])
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    assert "Sakelar transfer: mati" in teks_halaman(minta_admin(transfer, REKENING, admin)[1])


@pytest.mark.parametrize("query", ["?hasil=sembarang", "?x=1", "?hasil=tersimpan&hasil=tersimpan"])
def test_query_tak_sah_404_identik(transfer, admin, query):
    acuan = minta_admin(transfer, TAK_ADA, admin)
    kode, isi, _t = minta_admin(transfer, REKENING + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_umpan_balik_tersimpan_hanya_dari_kode_dikenal(transfer, admin):
    isi = minta_admin(transfer, REKENING + "?hasil=tersimpan", admin)[1]
    assert 'role="status"' in isi


# --- simpan --------------------------------------------------------------------------

def test_isi_pertama_menyimpan_membuka_gerbang_dan_audit_tanpa_nomor(kosong, monkeypatch):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    cookie = login_admin(kosong)
    revisi, sidik = _snapshot()
    kode, isi, tajuk = kirim_rekening(kosong, cookie, revisi, sidik)
    assert (kode, isi, _hasil(tajuk)) == (303, "", "tersimpan")
    cfg = pesanan_rekening.baca(admin_store.BAWAAN)
    assert (cfg.nama_bank, cfg.nomor_rekening, cfg.atas_nama, cfg.revisi) == (
        "Bank Contoh Baru", NOMOR_BARU, "PT Contoh Dua", 1)
    assert cfg.actor_id == id_admin()
    (audit,) = _baca_tabel("rekening_audit")
    assert audit["actor_id"] == id_admin() and NOMOR_BARU not in repr(audit)
    assert audit["sidik_lama"] == pesanan_rekening.SIDIK_KOSONG and len(audit["sidik_baru"]) == 64


def test_pengisian_pertama_membuka_kartu_transfer_untuk_guru(bayar, monkeypatch):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    pesanan_rekening.migrasikan(admin_store.BAWAAN, sekarang=10)
    from pesanan_transfer_http_kit import schema_transfer
    schema_transfer.migrasikan(admin_store.BAWAAN)
    siap_order(bayar)                              # order dibuat saat gerbang Midtrans masih terbuka
    atur_tahap("nonaktif")
    assert "Bayar lewat transfer" not in minta_mentah(bayar, STATUS, AKUN_A)[1]   # rekening kosong: tertutup
    cookie = login_admin(bayar)
    assert kirim_rekening(bayar, cookie, *_snapshot())[0] == 303
    guru = minta_mentah(bayar, STATUS, AKUN_A)[1]
    assert "Bayar lewat transfer" in guru


def test_ubah_dengan_snapshot_sah_menaikkan_revisi_dan_memakai_sidik_baru(transfer, admin):
    awal = _snapshot()
    assert kirim_rekening(transfer, admin, *awal)[0] == 303
    cfg = pesanan_rekening.baca(admin_store.BAWAAN)
    assert cfg.revisi == awal[0] + 1 and cfg.nomor_rekening == NOMOR_BARU
    assert _snapshot()[1] != awal[1]


def test_konflik_revisi_form_lama_ditolak_409_ramah_tanpa_menimpa(transfer, admin):
    lama = _snapshot()
    assert kirim_rekening(transfer, admin, *lama, ganti={"nomor_rekening": "5555555551"})[0] == 303
    sebelum = _stempel()
    kode, isi, _t = kirim_rekening(transfer, admin, *lama, ganti={"nomor_rekening": NOMOR_BARU})
    assert kode == 409 and "Buka ulang" in isi and "Traceback" not in isi
    assert NOMOR_BARU not in isi and "5555555551" not in isi
    assert _stempel() == sebelum
    assert pesanan_rekening.baca(admin_store.BAWAAN).nomor_rekening == "5555555551"


def test_konflik_sidik_beda_dengan_revisi_sama_ditolak_409(transfer, admin):
    revisi, _sidik = _snapshot()
    sebelum = _stempel()
    kode, _i, _t = kirim_rekening(transfer, admin, revisi, "a" * 64)
    assert kode == 409 and _stempel() == sebelum


def test_replay_form_identik_idempoten_tanpa_audit_ganda(transfer, admin):
    revisi, sidik = _snapshot()
    data = {**token_rekening(admin, revisi, sidik), **isian_rekening()}
    header = {"Cookie": "osn_sesi=" + admin}
    assert minta_mentah(transfer, REKENING, None, data, header)[0] == 303
    sebelum = _stempel()
    assert minta_mentah(transfer, REKENING, None, data, header)[0] == 303
    assert _stempel() == sebelum and len(_baca_tabel("rekening_audit")) == 1


@pytest.mark.parametrize("ganti", [
    {"nomor_rekening": "12ab"}, {"nomor_rekening": "1234"}, {"nomor_rekening": "5555555555"},
    {"nomor_rekening": "1234 5678 90"}, {"nomor_rekening": "1" * 21}, {"nomor_rekening": ""},
    {"nama_bank": ""}, {"nama_bank": "Bank  Ganda"}, {"nama_bank": " Bank"}, {"nama_bank": "B" * 41},
    {"nama_bank": "<script>"}, {"atas_nama": "x"}, {"atas_nama": "A" * 61}, {"atas_nama": "Nama\nBaru"},
])
def test_isian_tak_sah_400_tanpa_efek_dan_nomor_tak_dipantulkan(transfer, admin, ganti):
    sebelum = _stempel()
    kode, isi, _t = kirim_rekening(transfer, admin, *_snapshot(), ganti=ganti)
    assert kode == 400 and "Traceback" not in isi
    nomor = ganti.get("nomor_rekening", NOMOR_BARU)
    assert not nomor or nomor not in isi
    assert _stempel() == sebelum


@pytest.mark.parametrize("hapus,ekstra", [(("nama_bank",), None), (("nomor_rekening",), None),
                                          (("atas_nama",), None), ((), {"revisi": "9"}), ((), {"sidik": "x"}),
                                          ((), {"admin_id": "palsu"})])
def test_field_kurang_atau_asing_400_tanpa_efek(transfer, admin, hapus, ekstra):
    sebelum = _stempel()
    assert kirim_rekening(transfer, admin, *_snapshot(), hapus=hapus, ekstra=ekstra)[0] == 400
    assert _stempel() == sebelum


def test_revisi_dan_sidik_hanya_dari_tinjauan_bertanda_tangan(transfer, admin):
    """Field `revisi`/`sidik` di form tidak pernah dipercaya (400), hanya yang ada di tinjauan."""
    revisi, sidik = _snapshot()
    sebelum = _stempel()
    assert kirim_rekening(transfer, admin, revisi + 5, sidik)[0] == 409
    assert kirim_rekening(transfer, admin, revisi, sidik, ekstra={"revisi": str(revisi + 5)})[0] == 400
    assert _stempel() == sebelum


# --- guard ---------------------------------------------------------------------------

def test_csrf_salah_403_tanpa_efek(transfer, admin):
    sebelum = _stempel()
    assert kirim_rekening(transfer, admin, *_snapshot(), ganti={"csrf": "rusak"})[0] == 403
    assert kirim_rekening(transfer, admin, *_snapshot(), hapus=("csrf",))[0] == 403
    assert _stempel() == sebelum


def test_sandi_ulang_salah_atau_hilang_403_tanpa_efek(transfer, admin):
    sebelum = _stempel()
    assert kirim_rekening(transfer, admin, *_snapshot(), ganti={"reauth": "salah-sandi"})[0] == 403
    assert kirim_rekening(transfer, admin, *_snapshot(), hapus=("reauth",))[0] == 403
    assert _stempel() == sebelum


def test_tinjauan_aksi_lain_atau_sesi_lain_ditolak(transfer, admin):
    from admin_transfer_kit import AKSI_SETUJUI, token_putusan
    sebelum = _stempel()
    data = {**token_putusan(admin, AKSI_SETUJUI, "ord_" + "0" * 32, 1), **isian_rekening()}
    assert minta_admin(transfer, REKENING, admin, data)[0] == 403
    asing = {**token_rekening("sesi-lain-sintetis", *_snapshot()), **isian_rekening()}
    assert minta_admin(transfer, REKENING, admin, asing)[0] == 403
    assert minta_mentah(transfer, REKENING, AKUN_ADMIN, {**token_rekening(admin, *_snapshot()), **isian_rekening()})[0] == 403
    assert _stempel() == sebelum


def test_permintaan_lintas_situs_403_tanpa_efek(transfer, admin):
    sebelum = _stempel()
    assert kirim_rekening(transfer, admin, *_snapshot(), headers=LINTAS_SITUS)[0] == 403
    assert _stempel() == sebelum


def test_skema_belum_dipasang_503_tanpa_efek(bayar):
    cookie = login_admin(bayar)
    kode, isi, _t = kirim_rekening(bayar, cookie, 0, pesanan_rekening.SIDIK_KOSONG)
    assert kode == 503 and "pesanan_transfer_migrasi" in isi
