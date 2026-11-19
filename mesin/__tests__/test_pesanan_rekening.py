"""Pengaturan rekening tujuan transfer: opt-in, tanpa seed, revisi optimistik, audit, fail-closed."""
from dataclasses import replace
import sqlite3

import pytest

import admin_store
import auth
import pesanan_rekening as rekening

BANK = "Bank Contoh"
NOMOR = "1234567890"
NAMA = "PT Contoh Sintetis"


def _akun(tmp_path):
    path = tmp_path / "sandi.json"
    auth.tambah_akun("Admin-Rekening", "sandi-admin-rekening-123", "admin", path)
    auth.tambah_akun("Guru-Rekening", "sandi-guru-rekening-123", "guru", path)
    return (path, auth.autentikasi("Admin-Rekening", "sandi-admin-rekening-123", path),
            auth.autentikasi("Guru-Rekening", "sandi-guru-rekening-123", path))


def _snapshot(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def _siap(tmp_path, versi=7):
    path = tmp_path / ("admin-%d.db" % versi)
    admin_store.siapkan(path, sekarang=1, paket_v2=versi >= 8)
    if versi == 9:
        admin_store.migrasikan_kuota_pendamping(path)
    rekening.migrasikan(path, sekarang=10)
    return path


def _args(**ganti):
    dasar = dict(operasi="op_" + "a" * 32, revisi=0, sidik_awal=rekening.SIDIK_KOSONG,
                 nama_bank=BANK, nomor_rekening=NOMOR, atas_nama=NAMA, sekarang=20)
    dasar.update(ganti)
    return dasar


@pytest.mark.parametrize("versi", [7, 8, 9])
def test_migrasi_opt_in_idempoten_tanpa_seed_dan_tanpa_bump(tmp_path, versi):
    path = tmp_path / ("admin-%d.db" % versi)
    admin_store.siapkan(path, sekarang=1, paket_v2=versi >= 8)
    if versi == 9:
        admin_store.migrasikan_kuota_pendamping(path)
    awal = _snapshot(path)
    rekening.migrasikan(path, sekarang=10)
    pertama = _snapshot(path)
    rekening.migrasikan(path, sekarang=11)
    assert _snapshot(path) == pertama
    assert all(b in pertama for b in awal if not b.startswith("PRAGMA user_version"))
    with sqlite3.connect(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert kon.execute("SELECT COUNT(*) FROM rekening_konfigurasi").fetchone()[0] == 0
        assert kon.execute("SELECT versi,dipasang FROM rekening_schema").fetchall() == [(1, 10)]
    assert rekening.baca(path) is None          # tidak ada rekening bawaan: admin wajib mengisi
    assert rekening.baca_publik(path) is None


def test_reader_hilang_absent_parsial_dan_nilai_rusak_fail_closed_tanpa_tulis(tmp_path):
    hilang = tmp_path / "hilang.db"
    assert rekening.baca(hilang) is None and not hilang.exists()
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    awal = path.read_bytes()
    assert rekening.baca(path) is None and path.read_bytes() == awal
    with admin_store.buka_baca(path) as kon:
        assert rekening.validasi_schema(kon) is False

    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE rekening_konfigurasi(id INTEGER PRIMARY KEY)")
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass
    assert rekening.baca(path) is None

    rusak = _siap(tmp_path / "rusak")
    path_auth, principal, _ = _akun(tmp_path / "rusak")
    rekening.ubah(rusak, path_auth, principal, **_args())
    with sqlite3.connect(rusak) as kon:
        kon.execute("PRAGMA ignore_check_constraints=ON")
        kon.execute("UPDATE rekening_konfigurasi SET nomor_rekening='12ab'")
    assert rekening.baca(rusak) is None


def test_trigger_hilang_membuat_store_ditolak(tmp_path):
    path = _siap(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TRIGGER rekening_audit_tolak_update")
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass
    with sqlite3.connect(path) as kon:
        with pytest.raises(ValueError):
            rekening.validasi_schema(kon)


def test_ubah_pertama_kali_revisi_nol_menjadi_satu_lalu_baca_dan_publik(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, _ = _akun(tmp_path)
    hasil = rekening.ubah(path, path_auth, principal, **_args(nomor_rekening="1234567890"))
    assert (hasil.nama_bank, hasil.nomor_rekening, hasil.atas_nama, hasil.revisi) == \
        (BANK, "1234567890", NAMA, 1)
    assert rekening.baca(path) == hasil
    publik = rekening.baca_publik(path)
    assert (publik.nama_bank, publik.nomor_rekening, publik.nomor_label, publik.atas_nama) == \
        (BANK, "1234567890", "1234 5678 90", NAMA)
    with admin_store.buka_baca(path) as kon:
        audit = dict(kon.execute("SELECT * FROM rekening_audit").fetchone())
    assert (audit["revisi_awal"], audit["revisi_hasil"], audit["actor_id"]) == (0, 1, principal.id_akun)
    assert "1234567890" not in " ".join(str(v) for v in audit.values())


def test_ubah_kedua_replay_stale_dan_collision(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, _ = _akun(tmp_path)
    pertama = rekening.ubah(path, path_auth, principal, **_args())
    kedua_args = _args(operasi="op_" + "b" * 32, revisi=1,
                       sidik_awal=rekening.sidik_konfigurasi(pertama), nomor_rekening="98765432100")
    kedua = rekening.ubah(path, path_auth, principal, **kedua_args)
    assert kedua.revisi == 2 and kedua.nomor_rekening == "98765432100"
    assert rekening.ubah(path, path_auth, principal, **kedua_args) == kedua      # replay
    with pytest.raises(admin_store.KonflikOperasi):
        rekening.ubah(path, path_auth, principal, **{**kedua_args, "atas_nama": "Orang Lain"})
    with pytest.raises(admin_store.KonflikOperasi):                              # revisi basi
        rekening.ubah(path, path_auth, principal, **_args(operasi="op_" + "c" * 32))
    with pytest.raises(admin_store.KonflikOperasi):                              # sidik basi
        rekening.ubah(path, path_auth, principal, **_args(
            operasi="op_" + "d" * 32, revisi=2, sidik_awal=rekening.sidik_konfigurasi(pertama)))
    assert rekening.baca(path) == kedua
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM rekening_audit").fetchone()[0] == 2


def test_penulisan_pertama_dua_kali_dengan_operasi_beda_ditolak(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, _ = _akun(tmp_path)
    rekening.ubah(path, path_auth, principal, **_args())
    with pytest.raises(admin_store.KonflikOperasi):
        rekening.ubah(path, path_auth, principal, **_args(operasi="op_" + "e" * 32))
    assert rekening.baca(path).revisi == 1


def test_audit_append_only_dan_konfigurasi_tak_boleh_dihapus(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, _ = _akun(tmp_path)
    rekening.ubah(path, path_auth, principal, **_args())
    with sqlite3.connect(path) as kon:
        for sql in ("UPDATE rekening_audit SET dibuat=99", "DELETE FROM rekening_audit",
                    "INSERT OR REPLACE INTO rekening_audit SELECT * FROM rekening_audit",
                    "DELETE FROM rekening_konfigurasi", "UPDATE rekening_schema SET versi=1",
                    "DELETE FROM rekening_schema"):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sql)


def test_principal_tidak_sah_dan_rollback_failpoint(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, guru = _akun(tmp_path)
    snapshot = path.read_bytes()
    for p in (guru, replace(principal, revisi_auth=principal.revisi_auth + 1),
              replace(principal, peran="guru")):
        with pytest.raises(LookupError):
            rekening.ubah(path, path_auth, p, **_args())
        assert path.read_bytes() == snapshot
    with pytest.raises(RuntimeError, match="failpoint"):
        rekening.ubah(path, path_auth, principal, **_args(), failpoint="setelah_update")
    assert rekening.baca(path) is None
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM rekening_audit").fetchone()[0] == 0


def test_ubah_tanpa_migrasi_ditolak(tmp_path):
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    path_auth, principal, _ = _akun(tmp_path)
    with pytest.raises(admin_store.StoreBelumSiap):
        rekening.ubah(path, path_auth, principal, **_args())


@pytest.mark.parametrize("nilai", [
    "", "Bank\x00", "Bank\nBaru", " Bank", "Bank ", "B", "B" * 41, "Bank  Ganda", "<b>Bank</b>",
    'Bank "X"', "Bank​X", None, 7,
])
def test_nama_bank_tidak_sah_ditolak(nilai):
    with pytest.raises(ValueError):
        rekening.normalisasi_nama_bank(nilai)


@pytest.mark.parametrize("nilai", [
    "", "Nama\x00", "Nama\tTab", " Nama", "Nama ", "N", "N" * 61, "<script>", "Nama‮X", None,
])
def test_atas_nama_tidak_sah_ditolak(nilai):
    with pytest.raises(ValueError):
        rekening.normalisasi_atas_nama(nilai)


@pytest.mark.parametrize("nilai", [
    "", "1234", "1" * 21, "12 345 678", "1234-5678", "12345abc", "１２３４５６７８", "+6281234567",
    "00000000", "1111111111", "1234567890\n", None, 1234567890,
])
def test_nomor_rekening_hanya_digit_lima_sampai_dua_puluh(nilai):
    with pytest.raises(ValueError):
        rekening.normalisasi_nomor_rekening(nilai)


@pytest.mark.parametrize("bank,nama", [
    ("BCA", "Budi Santoso"), ("Bank Mandiri", "PT Jagomat Édukasi"), ("BNI Syariah", "CV Maju-Jaya (Cabang 2)"),
    ("Bank Jago", "O'Brien & Rekan"),
])
def test_nama_wajar_diterima(bank, nama):
    assert rekening.normalisasi_nama_bank(bank) == bank
    assert rekening.normalisasi_atas_nama(nama) == nama
    for digit in ("12345", "9" * 19 + "8", "1234567890123"):
        assert rekening.normalisasi_nomor_rekening(digit) == digit


def test_ubah_menolak_input_tidak_sah_tanpa_tulis(tmp_path):
    path = _siap(tmp_path)
    path_auth, principal, _ = _akun(tmp_path)
    snapshot = path.read_bytes()
    for ganti in (dict(nama_bank="B"), dict(nomor_rekening="12ab"), dict(atas_nama="<x>"),
                  dict(sekarang=-1), dict(sidik_awal="xyz"), dict(revisi=-1), dict(operasi="!")):
        with pytest.raises(ValueError):
            rekening.ubah(path, path_auth, principal, **_args(**ganti))
        assert path.read_bytes() == snapshot


def test_proyeksi_publik_validasi_ulang_objek_buatan_caller():
    cfg = rekening.KonfigurasiRekening(BANK, NOMOR, NAMA, 1, 10, "sistem_uji")
    assert rekening.proyeksi_publik(None) is None
    assert rekening.proyeksi_publik(cfg).nomor_label == "1234 5678 90"
    with pytest.raises(ValueError):
        rekening.proyeksi_publik(replace(cfg, nomor_rekening="abc"))
