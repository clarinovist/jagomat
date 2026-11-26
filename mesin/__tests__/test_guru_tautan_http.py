"""Tambah anak dengan kode lewat HTTP (`POST /guru/kelas/<klp_id>/tautan`): jalur sukses, kepemilikan 404 identik,
bagian detail kelas, dan privasi nama login. Kegagalan kode dan laju ada di `test_guru_tautan_http_oracle.py`.

Positive control dulu: kode sah harus berhasil, supaya setiap tes kegagalan membuktikan sesuatu.
"""
from __future__ import annotations

import admin_store
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_masuk as masuk
import jadwal_store as js
import kelas_kit
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, server, tambah_anak  # noqa: F401
from guru_tautan_kit import (
    JALUR_TAUTAN,
    KINI,
    KODE,
    LOGIN_ANAK,
    baris_tabel,
    buat_kode_anak,
    keadaan_tautan,
    siapkan_db_tautan,
    siapkan_kelompok_dan_order,
    tambah_murid,
)
from cek_http_kit import ambil_token, minta_mentah
from harian_kit import jam  # noqa: F401

KELOMPOK_TIDAK_ADA = "klp_" + "0" * 32
NAMA_PEMESAN = "Anak Sintetis Alfa"


def _ajukan(server, kelompok_id: str, kode: str, *, akun=AKUN_A, token=None):
    """POST tambah anak. Token diambil dari halaman detail bila tidak diberikan."""
    tok = ambil_token(server, akun, f"/guru/kelas/{kelompok_id}") if token is None else token
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), akun, data={"kode": kode, "token": tok})


def _detail(server, kelompok_id: str, akun=AKUN_A):
    return minta_mentah(server, f"/guru/kelas/{kelompok_id}", akun)


def test_positive_control_kode_sah_membuat_permintaan_menunggu(server, jam, tmp_path, monkeypatch):
    # Arrange
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    with js.buka(admin_store.BAWAAN) as kon:
        assert masuk.anak_bisa_masuk(kon, kondisi.murid_id, kondisi.siswa_id, kondisi.kelompok_id, KINI) is True

    # Act
    kode, isi, headers = _ajukan(server, kondisi.kelompok_id, KODE)

    # Assert
    assert kode == 200
    assert LOGIN_ANAK in isi and "Status: menunggu persetujuan orang tua" in isi
    assert "Location" not in headers
    assert headers.get("Cache-Control") == "no-store"
    assert KODE not in isi and "ABCD-2345" not in isi
    assert baris_tabel(db, "permintaan") == 1
    assert baris_tabel(db, "percobaan_gagal") == 0


def test_permintaan_kedua_untuk_anak_yang_sama_ditolak_generik(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    _ajukan(server, kondisi.kelompok_id, KODE)

    kode, isi, _ = _ajukan(server, kondisi.kelompok_id, KODE)

    assert kode == 400
    assert LOGIN_ANAK not in isi
    assert baris_tabel(db, "permintaan") == 1
    assert baris_tabel(db, "percobaan_gagal") == 1


def test_halaman_detail_pemilik_memuat_form_tanpa_kode(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)

    kode, isi, _ = _detail(server, kondisi.kelompok_id)

    assert kode == 200
    assert f'action="/guru/kelas/{kondisi.kelompok_id}/tautan"' in isi
    assert 'name="kode"' in isi and 'name="token"' in isi
    assert KODE not in isi


def test_permintaan_menunggu_tampil_tanpa_nama_login_dan_tanpa_id(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    _ajukan(server, kondisi.kelompok_id, KODE)

    kode, isi, _ = _detail(server, kondisi.kelompok_id)

    assert kode == 200
    assert "Menunggu persetujuan orang tua" in isi
    assert LOGIN_ANAK not in isi.split('aria-label="Permintaan kode anak"')[1]
    assert kondisi.murid_id not in isi
    assert f"/guru/kelas/{kondisi.kelompok_id}/tautan" in isi


def test_setuju_menampilkan_nama_login_tanpa_id_mentah(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    _ajukan(server, kondisi.kelompok_id, KODE)
    permintaan = dasar.daftar_untuk_guru(kondisi.guru_id, KINI, path=db)[0]
    dasar.putusan(permintaan_id=permintaan["id"], akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id,
                  hasil=aturan.HASIL_SETUJU, oleh=kondisi.murid_id, pada=KINI, path=db)

    kode, isi, _ = _detail(server, kondisi.kelompok_id)

    assert kode == 200
    daftar = isi.split('aria-label="Permintaan kode anak"')[1]
    assert LOGIN_ANAK in daftar and "Disetujui orang tua" in daftar
    assert kondisi.murid_id not in isi


def test_guru_lain_mendapat_404_identik_untuk_kelompok_orang(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    sebelum = keadaan_tautan(db)

    jawaban = [
        _ajukan_tanpa_token(server, kondisi.kelompok_id, KODE, akun=AKUN_B),
        _ajukan_tanpa_token(server, kondisi.kelompok_id, KODE, akun=AKUN_ADMIN),
        _ajukan_tanpa_token(server, KELOMPOK_TIDAK_ADA, KODE, akun=AKUN_A),
        _ajukan_tanpa_token(server, "bukan-id", KODE, akun=AKUN_A),
    ]

    assert {(kode, isi) for kode, isi, _ in jawaban} == {(404, jawaban[0][1])}
    assert keadaan_tautan(db) == sebelum


def _ajukan_tanpa_token(server, kelompok_id: str, kode: str, *, akun):
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), akun,
                        data={"kode": kode, "token": "tidak-dipakai"})


def test_guru_b_tidak_melihat_permintaan_guru_a(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    _ajukan(server, kondisi.kelompok_id, KODE)

    kode, isi, _ = _detail(server, kondisi.kelompok_id, akun=AKUN_B)

    assert kode == 404
    assert LOGIN_ANAK not in isi and "Permintaan" not in isi


def test_kelompok_penuh_menampilkan_pesan_tanpa_form(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server, kuota=1)
    lain = tambah_anak(server, "Anak Sintetis Lain", AKUN_A[0], None)
    murid_lain = tambah_murid(login="anak-lain", siswa_id=lain)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        tagihan_lain = kelas_kit.lunas(kon, lain, "mini", n=2, akun=murid_lain["id_akun"], sekarang=KINI)
        js.tempatkan(kon, "admin_sintetis", tagihan_lain.order_id, kelompok_id=kondisi.kelompok_id,
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
        kon.commit()

    kode, isi, _ = _detail(server, kondisi.kelompok_id)

    assert kode == 200
    assert masuk.PESAN_PENUH in isi
    assert 'name="kode"' not in isi


def test_kelompok_tertutup_menolak_pengajuan_dengan_pesan_spesifik(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    jam.maju_jam(14 * 24)  # dua pertemuan (24 Nov dan 1 Des) sudah mulai: pendaftaran ditutup
    sebelum = keadaan_tautan(db)

    kode, isi, _ = _ajukan(server, kondisi.kelompok_id, KODE, token=ambil_token_tanpa_form(server, kondisi))

    assert kode == 409
    assert js.PESAN_DITUTUP in isi
    assert keadaan_tautan(db) == sebelum


def ambil_token_tanpa_form(server, kondisi) -> str:
    """Kelompok tertutup tidak merender form, jadi token diambil dengan membangun ulang dari modul (uji ini
    hanya membuktikan jawaban 409, bukan token)."""
    from guru_tautan_http import _buat_token
    from sessions import principal_basic

    return _buat_token(principal_basic(*AKUN_A), None, kondisi.kelompok_id)
