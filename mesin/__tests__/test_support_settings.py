"""Kontrak konfigurasi dukungan privat, migrasi opt-in, dan audit."""
from dataclasses import replace
import sqlite3

import pytest

import admin_store
import auth
import support_settings as dukungan


NOMOR = "082137111988"


def _akun(tmp_path):
    path = tmp_path / "sandi.json"
    auth.tambah_akun("Admin-Dukungan", "sandi-admin-dukungan-123", "admin", path)
    auth.tambah_akun("Guru-Dukungan", "sandi-guru-dukungan-123", "guru", path)
    return path, auth.autentikasi("Admin-Dukungan", "sandi-admin-dukungan-123", path), auth.autentikasi("Guru-Dukungan", "sandi-guru-dukungan-123", path)


def _snapshot(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


@pytest.mark.parametrize("versi", [7, 8, 9])
def test_migrasi_opt_in_idempoten_preservasi_dan_tidak_bump_admin(tmp_path, versi):
    path = tmp_path / ("admin-%d.db" % versi)
    admin_store.siapkan(path, sekarang=1, paket_v2=versi >= 8)
    if versi == 9:
        admin_store.migrasikan_kuota_pendamping(path)
    with sqlite3.connect(path) as kon:
        kon.execute("INSERT INTO langganan_kampanye VALUES('kampanye-dukungan',1,4838401,100)")
    awal = _snapshot(path)

    dukungan.migrasikan(path, sekarang=10)
    pertama = _snapshot(path)
    dukungan.migrasikan(path, sekarang=11)

    assert _snapshot(path) == pertama
    assert all(baris in pertama for baris in awal if not baris.startswith("PRAGMA user_version"))
    with sqlite3.connect(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert kon.execute("SELECT COUNT(*) FROM dukungan_audit").fetchone()[0] == 0
    cfg = dukungan.baca(path)
    assert cfg is not None
    assert (cfg.whatsapp_digits, cfg.jam_layanan_kode) == (NOMOR, "weekday_0900_1700_wib")
    assert (cfg.sla_respons_hari, cfg.sla_status_hari, cfg.revisi) == (1, 3, 1)


def test_reader_missing_parsial_dan_nilai_rusak_fail_closed_tanpa_tulis(tmp_path):
    hilang = tmp_path / "hilang.db"
    assert dukungan.baca(hilang) is None
    assert not hilang.exists()

    future = tmp_path / "future.db"
    admin_store.siapkan(future, sekarang=1)
    dukungan.migrasikan(future, sekarang=2)
    with sqlite3.connect(future) as kon:
        kon.execute("DROP TRIGGER dukungan_schema_tolak_update")
        kon.execute("PRAGMA ignore_check_constraints=ON")
        kon.execute("UPDATE dukungan_schema SET versi=2")
    assert dukungan.baca(future) is None

    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    awal = path.read_bytes()
    assert dukungan.baca(path) is None
    assert path.read_bytes() == awal

    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE dukungan_konfigurasi(id INTEGER PRIMARY KEY)")
    rusak = path.read_bytes()
    assert dukungan.baca(path) is None
    assert path.read_bytes() == rusak

    path2 = tmp_path / "nilai-rusak.db"
    admin_store.siapkan(path2, sekarang=1)
    dukungan.migrasikan(path2, sekarang=2)
    with sqlite3.connect(path2) as kon:
        kon.execute("PRAGMA ignore_check_constraints=ON")
        kon.execute("UPDATE dukungan_konfigurasi SET whatsapp_digits='08xx-xxxx-xxxx'")
    assert dukungan.baca(path2) is None


@pytest.mark.parametrize("nilai", [
    "", "08xx-xxxx-xxxx", "0800000000", "0812345678", "08123456789",
    "081234567890", "089876543210", "0811111111",
    "+6282137111988", "6282137111988", "https://wa.me/6282137111988",
    "０８２１３７１１１９８８", "0821\n37111988", "0821/3711/1988", "07123456789",
    "081234567", "0812345678901234",
])
def test_nomor_invalid_dan_placeholder_ditolak(nilai):
    with pytest.raises(ValueError):
        dukungan.normalisasi_nomor(nilai)


@pytest.mark.parametrize("nilai", ["082137111988", "0821 3711 1988", "0821-3711-1988"])
def test_nomor_indonesia_dinormalisasi_dan_url_dibangun_kode(nilai):
    assert dukungan.normalisasi_nomor(nilai) == NOMOR
    publik = dukungan.proyeksi_publik(dukungan.KonfigurasiDukungan(
        NOMOR, "weekday_0900_1700_wib", 1, 3, 1, 10, "sistem_migrasi",
    ))
    assert publik.whatsapp_label == "0821 3711 1988"
    assert publik.whatsapp_url == "https://wa.me/6282137111988"
    assert "?" not in publik.whatsapp_url
    assert "akun" not in publik.whatsapp_url.lower()
    assert "anak" not in publik.whatsapp_url.lower()


@pytest.mark.parametrize("sla_respons,sla_status", [(0, 3), (31, 3), (1, 0), (1, 31), (True, 3)])
def test_sla_di_luar_batas_ditolak(sla_respons, sla_status):
    with pytest.raises(ValueError):
        dukungan.konfigurasi(
            NOMOR, "weekday_0900_1700_wib", sla_respons, sla_status,
            revisi=1, diperbarui=1, actor_id="sistem_uji",
        )


def test_jam_layanan_di_luar_allowlist_ditolak():
    with pytest.raises(ValueError):
        dukungan.konfigurasi(
            NOMOR, "setiap_hari_bebas", 1, 3,
            revisi=1, diperbarui=1, actor_id="sistem_uji",
        )


def test_update_atomik_replay_stale_collision_audit_tanpa_nomor(tmp_path):
    path = tmp_path / "admin.db"
    path_auth, principal, _guru = _akun(tmp_path)
    admin_store.siapkan(path, sekarang=1)
    dukungan.migrasikan(path, sekarang=2)
    awal = dukungan.baca(path)
    assert awal is not None
    args = dict(
        operasi="op_" + "a" * 32,
        revisi=awal.revisi,
        sidik_awal=dukungan.sidik_konfigurasi(awal),
        whatsapp="0821-3711-1988",
        jam_layanan="weekday_0900_1700_wib",
        sla_respons=2,
        sla_status=4,
        sekarang=20,
    )
    hasil = dukungan.ubah(path, path_auth, principal, **args)
    assert (hasil.revisi, hasil.sla_respons_hari, hasil.sla_status_hari) == (2, 2, 4)
    assert dukungan.ubah(path, path_auth, principal, **args) == hasil
    with admin_store.buka_baca(path) as kon:
        audit = dict(kon.execute("SELECT * FROM dukungan_audit").fetchone())
        assert kon.execute("SELECT COUNT(*) FROM dukungan_audit").fetchone()[0] == 1
        assert NOMOR not in " ".join(str(v) for v in audit.values())
    with sqlite3.connect(path) as kon:
        for sql in (
            "UPDATE dukungan_audit SET dibuat=99",
            "DELETE FROM dukungan_audit",
            "INSERT OR REPLACE INTO dukungan_audit SELECT * FROM dukungan_audit LIMIT 1",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sql)
    with pytest.raises(admin_store.KonflikOperasi):
        dukungan.ubah(path, path_auth, principal, **{**args, "sla_status": 5})
    with pytest.raises(admin_store.KonflikOperasi):
        dukungan.ubah(path, path_auth, principal, **{**args, "operasi": "op_" + "b" * 32})


def test_stale_revision_dan_operation_collision_tanpa_perubahan(tmp_path):
    path = tmp_path / "admin.db"
    path_auth, principal, _guru = _akun(tmp_path)
    admin_store.siapkan(path, sekarang=1)
    dukungan.migrasikan(path, sekarang=2)
    awal = dukungan.baca(path)
    assert awal is not None
    salah = "0" * 64
    if salah == dukungan.sidik_konfigurasi(awal):
        salah = "1" * 64
    args = dict(
        operasi="op_" + "d" * 32, revisi=awal.revisi,
        sidik_awal=salah, whatsapp=NOMOR,
        jam_layanan="weekday_0900_1700_wib", sla_respons=2, sla_status=3,
        sekarang=20,
    )
    with pytest.raises(admin_store.KonflikOperasi):
        dukungan.ubah(path, path_auth, principal, **args)
    assert dukungan.baca(path) == awal
    with pytest.raises(admin_store.KonflikOperasi):
        dukungan.ubah(path, path_auth, principal, **{
            **args, "operasi": "op_" + "f" * 32, "revisi": awal.revisi + 1,
            "sidik_awal": dukungan.sidik_konfigurasi(awal),
        })
    assert dukungan.baca(path) == awal
    with admin_store.buka_baca(path) as kon:
        assert not kon.execute("SELECT 1 FROM dukungan_audit").fetchone()

    sukses = {**args, "operasi": "op_" + "e" * 32,
              "sidik_awal": dukungan.sidik_konfigurasi(awal)}
    dukungan.ubah(path, path_auth, principal, **sukses)
    hasil = dukungan.baca(path)
    with pytest.raises(admin_store.KonflikOperasi):
        dukungan.ubah(path, path_auth, principal, **{**sukses, "sla_status": 6})
    assert dukungan.baca(path) == hasil
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM dukungan_audit").fetchone()[0] == 1


def test_update_principal_hidup_dan_rollback_failpoint(tmp_path):
    path = tmp_path / "admin.db"
    path_auth, principal, guru = _akun(tmp_path)
    admin_store.siapkan(path, sekarang=1)
    dukungan.migrasikan(path, sekarang=2)
    awal = dukungan.baca(path)
    assert awal is not None
    args = dict(
        operasi="op_" + "c" * 32, revisi=awal.revisi,
        sidik_awal=dukungan.sidik_konfigurasi(awal), whatsapp=NOMOR,
        jam_layanan="weekday_0900_1700_wib", sla_respons=2, sla_status=3,
        sekarang=20,
    )
    snapshot = path.read_bytes()
    for p in (guru, replace(principal, revisi_auth=principal.revisi_auth + 1), replace(principal, peran="guru")):
        with pytest.raises(LookupError):
            dukungan.ubah(path, path_auth, p, **args)
        assert path.read_bytes() == snapshot
    with pytest.raises(RuntimeError, match="failpoint"):
        dukungan.ubah(path, path_auth, principal, **args, failpoint="setelah_update")
    assert dukungan.baca(path) == awal
    with admin_store.buka_baca(path) as kon:
        assert not kon.execute("SELECT 1 FROM dukungan_audit").fetchone()
