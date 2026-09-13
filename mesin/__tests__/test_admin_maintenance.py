"""Pemeliharaan admin bounded tanpa menyentuh receipt durable."""

import json
import sqlite3

import admin_bulk
import admin_maintenance
import admin_store
import auth
import sessions
from admin_contracts import AKSI_BUAT_GURU


ACTOR = "akun_" + "a" * 32


def test_jalankan_purge_bounded_dan_idempoten(tmp_path):
    admin = tmp_path / "admin.db"
    transient = tmp_path / "transient.db"
    akun = tmp_path / "auth.json"
    sesi = tmp_path / "sesi.json"
    admin_store.siapkan(admin, sekarang=1)
    admin_bulk.siapkan_transient(transient)
    akun.write_text(json.dumps({"akun": [{
        "pengguna": "pengelola", "peran": "admin", "id_akun": ACTOR,
        "revisi_auth": 1, **auth.buat_hash("admin-sintetis"),
    }]}), encoding="utf-8")
    token = sessions.buat(
        "pengelola", "admin", path=sesi, sekarang=0,
        id_akun=ACTOR, revisi_auth=1,
    )
    for nomor in range(3):
        target = (admin_bulk.TargetBulk(
            "item_maint_%02d" % nomor, "operasi_maint_%02d" % nomor,
            "candidate_%032x" % nomor, 0, "guru", "alias-%02d" % nomor,
        ),)
        admin_bulk.buat_batch(
            admin, transient, path_auth=akun, path_sesi=sesi,
            token_sesi=token, batch_id="batch_maint_%02d" % nomor,
            actor_id=ACTOR, actor_revisi=1, aksi=AKSI_BUAT_GURU,
            target_peran="guru", target=target, sekarang=1,
        )
    with admin_store._transaksi(admin) as kon:
        kon.execute(
            """INSERT INTO operasi_admin(
                operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
                hasil_id,credential_status,dibuat,diperbarui)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("operasi_audit_lama", ACTOR, "account_teacher_create",
             "account_candidate", "candidate_" + "f" * 32, "guru", 0,
             "e" * 64, "conflict", "target_changed", None, None,
             "not_applicable", 1, 1),
        )
        kon.execute(
            """INSERT INTO audit_admin(
                operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                status,hasil_kode,dibuat) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("operasi_audit_lama", ACTOR, "account_teacher_create",
             "account_candidate", "candidate_" + "f" * 32, "guru",
             "conflict", "target_changed", 1),
        )

    kini = 181 * 86400 + 2
    satu = admin_maintenance.jalankan(
        admin, transient, sekarang=kini, batas_audit=1, batas_batch=2
    )
    dua = admin_maintenance.jalankan(
        admin, transient, sekarang=kini, batas_audit=1, batas_batch=2
    )
    tiga = admin_maintenance.jalankan(
        admin, transient, sekarang=kini, batas_audit=1, batas_batch=2
    )
    assert satu.audit_dihapus == 1 and satu.draft_dihapus == 2
    assert dua.audit_dihapus == 0 and dua.draft_dihapus == 1
    assert tiga.audit_dihapus == 0 and tiga.draft_dihapus == 0
    assert admin_store.baca_operasi(admin, "operasi_audit_lama") is not None
    for nomor in range(3):
        assert admin_store.baca_batch_durable(
            admin, "batch_maint_%02d" % nomor
        ) is not None
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM draft_bulk").fetchone()[0] == 0
