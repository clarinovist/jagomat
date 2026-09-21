"""Domain Gelombang C: create, registrasi, siswa, dan audit reader."""

import json
import sqlite3
import threading

import pytest

import admin_accounts
import admin_contracts as c
import admin_registration
import admin_service
import admin_store
import admin_students
import auth
import database
import sessions


ACTOR = "akun_" + "a" * 32
OWNER = "akun_" + "b" * 32
TOKEN = "Z" * 48


def _akun(nama, peran, identitas, sandi, revisi=1, siswa_id=None):
    hasil = {
        "pengguna": nama,
        "peran": peran,
        "id_akun": identitas,
        "revisi_auth": revisi,
        **auth.buat_hash(sandi),
    }
    if siswa_id is not None:
        hasil["siswa_id"] = siswa_id
    return hasil


@pytest.fixture()
def storage(tmp_path):
    admin = tmp_path / "admin-control.db"
    akun = tmp_path / "sandi.json"
    db = tmp_path / "latihan.db"
    sesi = tmp_path / "sesi.json"
    admin_store.siapkan(admin, sekarang=1)
    database.siapkan(db)
    admin_students.siapkan(db)
    akun.write_text(json.dumps({
        "metadata": {"tetap": True},
        "operasi_admin": {},
        "akun": [
            _akun("pengelola", "admin", ACTOR, "admin-sintetis", 2),
            _akun("keluarga-a", "guru", OWNER, "guru-sintetis", 1),
        ],
    }), encoding="utf-8")
    return admin, akun, db, sesi


def _buat_perintah(nomor, alias, *, murid=False, siswa_id=None):
    return c.PerintahPembuatanAkun(
        "operasi_buat_%04d" % nomor,
        ACTOR,
        2,
        c.AKSI_BUAT_LOGIN_MURID if murid else c.AKSI_BUAT_GURU,
        "candidate_%04d" % nomor,
        "murid" if murid else "guru",
        alias,
        TOKEN,
        siswa_id,
    )


def test_schema_v4_migrasi_v1_mempertahankan_journal(tmp_path):
    path = tmp_path / "v1.db"
    ddl_v1 = admin_store._DDL.replace(
        "'account_teacher_create',\n        'student_login_create','student_level_update',",
        "",
    ).replace(
        "'account_candidate','student',", ""
    ).replace(
        "'teacher_created',\n        'student_login_created','student_level_updated',",
        "",
    ).replace("    hasil_id TEXT,\n", "").split("CREATE TABLE IF NOT EXISTS draft_bulk", 1)[0]
    with sqlite3.connect(str(path)) as kon:
        admin_store._jalankan_ddl(kon, ddl_v1)
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,1,1,'closed_standard',1)")
        kon.execute(
            """INSERT INTO operasi_admin(
            operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,revisi_target,
            sidik_perintah,status,credential_status,dibuat,diperbarui)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("operasi_v1_demo", ACTOR, c.AKSI_CABUT_SESI, "account", OWNER,
             "guru", 1, "a" * 64, "reserved", "not_applicable", 2, 2),
        )
        kon.execute("PRAGMA user_version=1")
    admin_store.siapkan(path, sekarang=3)
    assert admin_store.baca_operasi(path, "operasi_v1_demo").status == "reserved"
    with sqlite3.connect(str(path)) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == admin_store.VERSI_SKEMA
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None


def test_schema_v4_migrasi_v2_mempertahankan_seluruh_data_dan_anchor(tmp_path):
    path = tmp_path / "v2.db"
    ddl_v2 = admin_store._DDL.replace(
        "'account_login_delete','student_login_delete_step','account_teacher_create',\n"
        "        'student_login_create','student_level_update','student_delete',",
        "'account_login_delete','account_teacher_create',\n"
        "        'student_login_create','student_level_update',",
    ).replace(
        "CHECK(aksi IN ('student_level_update','student_delete'))",
        "CHECK(aksi='student_level_update')",
    ).replace(
        "CHECK(hasil_kode IN ('student_level_updated','student_deleted'))",
        "CHECK(hasil_kode='student_level_updated')",
    ).replace(
        "'student_login_created','student_level_updated','student_deleted','config_updated',",
        "'student_login_created','student_level_updated','config_updated',",
    )
    with sqlite3.connect(str(path)) as kon:
        admin_store._jalankan_ddl(kon, ddl_v2)
        kon.execute(
            "INSERT INTO konfigurasi_pendaftaran VALUES(1,1,1,'closed_standard',1)"
        )
        kon.execute("PRAGMA user_version=2")
    perintah = _buat_perintah(901, "migrasi-v2")
    sidik = c.sidik_perintah(perintah)
    anchor_id = "operasi_anchor_v2"
    with sqlite3.connect(str(path)) as kon:
        kon.execute(
            """INSERT INTO operasi_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
                   hasil_id,credential_status,dibuat,diperbarui)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (perintah.operasi_id, ACTOR, perintah.aksi, "account_candidate",
             perintah.target_id, "guru", 0, sidik, "succeeded",
             "teacher_created", 1, "akun_" + "f" * 32, "unconfirmed", 2, 3),
        )
        audit_id = kon.execute(
            """INSERT INTO audit_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   status,hasil_kode,dibuat) VALUES(?,?,?,?,?,?,?,?,?)""",
            (perintah.operasi_id, ACTOR, perintah.aksi, "account_candidate",
             perintah.target_id, "guru", "succeeded", "teacher_created", 3),
        ).lastrowid
        kon.execute(
            "INSERT INTO audit_admin_perubahan VALUES(?,?,?,?)",
            (audit_id, "auth_revision", "0", "1"),
        )
        kon.execute(
            "INSERT INTO receipt_admin VALUES(?,?,?,?,?,?,?,?)",
            (anchor_id, ACTOR, c.AKSI_UBAH_LEVEL, "student", "student_7",
             "b" * 64, "student_level_updated", 4),
        )
        kon.commit()

    admin_store.siapkan(path, sekarang=5)
    admin_store.siapkan(path, sekarang=6)

    with sqlite3.connect(str(path)) as kon:
        kon.row_factory = sqlite3.Row
        assert kon.execute("PRAGMA user_version").fetchone()[0] == admin_store.VERSI_SKEMA
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None
        journal = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?", (perintah.operasi_id,)
        ).fetchone()
        assert journal["hasil_id"] == "akun_" + "f" * 32
        assert journal["status"] == "succeeded"
        assert kon.execute("SELECT COUNT(*) FROM audit_admin").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM audit_admin_perubahan").fetchone()[0] == 1
        anchor = kon.execute(
            "SELECT * FROM receipt_admin WHERE operasi_id=?", (anchor_id,)
        ).fetchone()
        assert anchor["hasil_kode"] == "student_level_updated"
        sql_operasi = kon.execute(
            "SELECT sql FROM sqlite_master WHERE name='operasi_admin'"
        ).fetchone()[0]
        sql_anchor = kon.execute(
            "SELECT sql FROM sqlite_master WHERE name='receipt_admin'"
        ).fetchone()[0]
        assert "student_delete" in sql_operasi
        assert "student_deleted" in sql_anchor
        assert kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_admin'"
        ).fetchone() is not None


def test_schema_v4_migrasi_v3_menambah_metadata_batch_tanpa_mengubah_lama(tmp_path):
    path = tmp_path / "v3.db"
    ddl_v3 = admin_store._DDL.split(
        "CREATE TABLE IF NOT EXISTS batch_admin", 1
    )[0]
    with sqlite3.connect(str(path)) as kon:
        admin_store._jalankan_ddl(kon, ddl_v3)
        kon.execute(
            "INSERT INTO konfigurasi_pendaftaran VALUES(1,1,1,'closed_standard',1)"
        )
        kon.execute(
            """INSERT INTO operasi_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
                   hasil_id,credential_status,dibuat,diperbarui)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("operasi_v3_preserved", ACTOR, c.AKSI_CABUT_SESI, "account",
             OWNER, "guru", 1, "c" * 64, "succeeded", "sessions_revoked",
             2, None, "not_applicable", 2, 3),
        )
        audit_id = kon.execute(
            """INSERT INTO audit_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   status,hasil_kode,dibuat) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("operasi_v3_preserved", ACTOR, c.AKSI_CABUT_SESI, "account",
             OWNER, "guru", "succeeded", "sessions_revoked", 3),
        ).lastrowid
        kon.execute(
            "INSERT INTO audit_admin_perubahan VALUES(?,?,?,?)",
            (audit_id, "auth_revision", "1", "2"),
        )
        kon.execute("PRAGMA user_version=3")
    sebelum = path.stat().st_size
    admin_store.siapkan(path, sekarang=2)
    admin_store.siapkan(path, sekarang=3)
    with sqlite3.connect(str(path)) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == admin_store.VERSI_SKEMA
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None
        assert kon.execute(
            "SELECT status,hasil_kode FROM operasi_admin WHERE operasi_id=?",
            ("operasi_v3_preserved",),
        ).fetchone() == ("succeeded", "sessions_revoked")
        assert kon.execute(
            "SELECT COUNT(*) FROM audit_admin WHERE operasi_id=?",
            ("operasi_v3_preserved",),
        ).fetchone()[0] == 1
        assert kon.execute(
            "SELECT nilai_lama,nilai_baru FROM audit_admin_perubahan"
        ).fetchone() == ("1", "2")
        for tabel in (
            "batch_admin", "batch_admin_item", "kelompok_admin",
            "kelompok_admin_item", "penyerahan_admin",
            "penyerahan_admin_item",
        ):
            assert kon.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tabel,),
            ).fetchone() is not None
    assert path.stat().st_size >= sebelum


def test_admin_create_guru_actual_owner_guard_replay_dan_secret_minimal(storage):
    admin, akun, db, _sesi = storage
    perintah = _buat_perintah(1, "guru-baru")
    hasil = admin_service.buat_akun(
        admin, akun, db, perintah,
        sandi_baru="sandi-guru-baru-123", sekarang=10,
    )
    replay = admin_service.buat_akun(
        admin, akun, db, perintah,
        sandi_baru="sandi-lain-tidak-dipakai", sekarang=11,
    )

    assert hasil.hasil.status == "succeeded"
    assert hasil.hasil.hasil_id.startswith("akun_")
    assert hasil.credential_sekali == "sandi-guru-baru-123"
    assert replay.hasil == hasil.hasil
    assert replay.credential_sekali is None
    baru = auth.cari_akun("guru-baru", akun)
    assert baru["id_akun"] == hasil.hasil.hasil_id
    assert baru["revisi_auth"] == 1
    raw = akun.read_text(encoding="utf-8")
    with sqlite3.connect(str(admin)) as kon:
        sqlite_dump = "\n".join(kon.iterdump())
    for rahasia in ("guru-baru", "sandi-guru-baru-123", baru["kunci"], baru["garam"], TOKEN):
        assert rahasia not in sqlite_dump
    receipt = json.loads(raw)["operasi_admin"][perintah.operasi_id]
    assert "alias" not in receipt and "password" not in receipt
    assert receipt["hasil_id"] == baru["id_akun"]


def test_admin_create_crash_setelah_replace_reconcile_tidak_duplikat(storage):
    admin, akun, db, _sesi = storage
    perintah = _buat_perintah(31, "guru-crash")
    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.buat_akun(
            admin, akun, db, perintah, sandi_baru="sandi-crash-123",
            sekarang=12, failpoint="setelah_replace",
        )
    assert len([a for a in auth.muat_akun(akun) if a["pengguna"] == "guru-crash"]) == 1
    pulih = admin_service.rekonsiliasi_pembuatan(
        admin, akun, perintah, sekarang=13
    )
    assert pulih.hasil.status == "succeeded"
    assert pulih.credential_sekali is None
    assert len([a for a in auth.muat_akun(akun) if a["pengguna"] == "guru-crash"]) == 1


def test_admin_create_guru_tolak_duplicate_dan_owner_lama(storage):
    admin, akun, db, _sesi = storage
    sebelum = akun.read_bytes()
    duplikat = _buat_perintah(2, "keluarga-a")
    hasil = admin_service.buat_akun(
        admin, akun, db, duplikat, sandi_baru="sandi-duplikat-123", sekarang=20
    )
    assert hasil.hasil.status == "conflict"
    assert akun.read_bytes() == sebelum

    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Anak Lama", "P3", pemilik="mantan-owner")
    owner = _buat_perintah(3, "mantan-owner")
    hasil = admin_service.buat_akun(
        admin, akun, db, owner, sandi_baru="sandi-owner-lama-123", sekarang=21
    )
    assert hasil.hasil.status == "conflict"
    assert auth.cari_akun("mantan-owner", akun) is None


@pytest.mark.parametrize("alias", ["a@b.invalid", "+62000000", "=FORMULA", " dua", "dua ", "a/b"])
def test_alias_contact_formula_path_ditolak_sebelum_journal(storage, alias):
    admin, akun, db, _sesi = storage
    perintah = _buat_perintah(4, alias)
    sebelum = akun.read_bytes()
    with pytest.raises(c.KontrakTidakSah):
        admin_service.buat_akun(
            admin, akun, db, perintah, sandi_baru="sandi-valid-123", sekarang=30
        )
    assert admin_store.baca_operasi(admin, perintah.operasi_id) is None
    assert akun.read_bytes() == sebelum


def test_create_login_murid_explicit_one_to_one_owner_valid(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Baru", "P3", pemilik="keluarga-a")
    perintah = _buat_perintah(5, "anak-baru-login", murid=True, siswa_id=siswa_id)
    hasil = admin_service.buat_akun(
        admin, akun, db, perintah, sandi_baru="murid-123", sekarang=40
    )
    login = auth.cari_akun("anak-baru-login", akun)
    assert hasil.hasil.status == "succeeded"
    assert login["siswa_id"] == siswa_id and login["revisi_auth"] == 1

    kedua = _buat_perintah(6, "anak-login-lain", murid=True, siswa_id=siswa_id)
    hasil2 = admin_service.buat_akun(
        admin, akun, db, kedua, sandi_baru="murid-456", sekarang=41
    )
    assert hasil2.hasil.status == "conflict"
    assert auth.cari_akun("anak-login-lain", akun) is None


def test_create_login_murid_tolak_owner_hilang_dan_legacy_ambigu(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        yatim = database.tambah_siswa(kon, "Yatim", "P3", pemilik="tak-ada")
        satu = database.tambah_siswa(kon, "namasama", "P3", pemilik="keluarga-a")
        database.tambah_siswa(kon, "namasama", "P4", pemilik="tak-ada")
    hasil = admin_service.buat_akun(
        admin, akun, db, _buat_perintah(7, "login-yatim", murid=True, siswa_id=yatim),
        sandi_baru="murid-789", sekarang=50,
    )
    assert hasil.hasil.status == "conflict"

    data = json.loads(akun.read_text(encoding="utf-8"))
    data["akun"].append(_akun("namasama", "murid", "akun_" + "d" * 32, "legacy", 0))
    data["akun"][-1].pop("siswa_id", None)
    akun.write_text(json.dumps(data), encoding="utf-8")
    hasil2 = admin_service.buat_akun(
        admin, akun, db, _buat_perintah(8, "namasama", murid=True, siswa_id=satu),
        sandi_baru="murid-abc", sekarang=51,
    )
    assert hasil2.hasil.status == "conflict"


def test_create_login_murid_tolak_legacy_unik_tanpa_auto_link(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "legacyunik", "P3", pemilik="keluarga-a")
    data = json.loads(akun.read_text(encoding="utf-8"))
    data["akun"].append(_akun("legacyunik", "murid", "akun_" + "e" * 32, "legacy", 0))
    data["akun"][-1].pop("siswa_id", None)
    akun.write_text(json.dumps(data), encoding="utf-8")

    hasil = admin_service.buat_akun(
        admin, akun, db, _buat_perintah(81, "login-baru", murid=True, siswa_id=siswa_id),
        sandi_baru="murid-unique", sekarang=52,
    )
    assert hasil.hasil.status == "conflict"
    assert auth.cari_akun("login-baru", akun) is None


def test_registration_config_dan_bulk_metadata_tidak_deadlock(storage, monkeypatch, tmp_path):
    admin, akun, db, sesi = storage
    transient = tmp_path / "bulk-race.db"
    admin_bulk = __import__("admin_bulk")
    admin_bulk.siapkan_transient(transient)
    token = sessions.buat(
        "pengelola", "admin", path=sesi, sekarang=0,
        id_akun=ACTOR, revisi_auth=2,
    )
    target = (admin_bulk.TargetBulk(
        "item_lock_bulk", "operasi_lock_bulk",
        "candidate_" + "7" * 32, 0, "guru", "lock-bulk",
    ),)
    auth_dipegang = threading.Event()
    lanjut_config = threading.Event()
    admin_db_dipegang = threading.Event()
    galat = []
    hasil = []
    asli_guard = admin_bulk._guard_principal
    asli_buat = admin_store._buat_batch_durable_kon
    urutan_guard = {"n": 0}

    from contextlib import contextmanager

    def guard_tercatat(*args, **kwargs):
        dasar = asli_guard(*args, **kwargs)

        @contextmanager
        def guard():
            with dasar:
                urutan_guard["n"] += 1
                if urutan_guard["n"] == 1:
                    auth_dipegang.set()
                    assert lanjut_config.wait(5)
                yield

        return guard()

    def buat_tercatat(*args, **kwargs):
        admin_db_dipegang.set()
        return asli_buat(*args, **kwargs)

    monkeypatch.setattr(admin_bulk, "_guard_principal", guard_tercatat)
    monkeypatch.setattr(admin_store, "_buat_batch_durable_kon", buat_tercatat)

    def bulk():
        try:
            admin_bulk.buat_batch(
                admin, transient, path_auth=akun, path_sesi=sesi,
                token_sesi=token, batch_id="batch_lock_order",
                actor_id=ACTOR, actor_revisi=2, aksi=c.AKSI_BUAT_GURU,
                target_peran="guru", target=target, sekarang=10,
            )
            hasil.append("bulk")
        except Exception as exc:  # pragma: no cover - assertion parent
            galat.append(exc)

    def config():
        try:
            admin_registration.ubah(
                admin, operasi_id="operasi_config_lock_order",
                actor_id=ACTOR, actor_revisi=2, path_auth=akun, revisi=1,
                dibuka=False, pesan_kode="closed_standard",
                token_tinjauan=TOKEN, sekarang=11,
            )
            hasil.append("config")
        except Exception as exc:  # pragma: no cover - assertion parent
            galat.append(exc)

    thread_bulk = threading.Thread(target=bulk)
    thread_bulk.start()
    assert auth_dipegang.wait(5)
    thread_config = threading.Thread(target=config)
    thread_config.start()
    # Config menunggu auth; bulk belum membuka transaksi admin sebelum guard.
    assert not admin_db_dipegang.wait(0.1)
    lanjut_config.set()
    thread_bulk.join(5); thread_config.join(5)
    assert not thread_bulk.is_alive() and not thread_config.is_alive()
    assert admin_db_dipegang.is_set()
    assert sorted(hasil) == ["bulk", "config"] and galat == []


def test_public_registration_missing_closed_open_snapshot_session_and_retry_stale(storage, tmp_path):
    admin, akun, db, sesi = storage
    missing = tmp_path / "missing-admin.db"
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_registration.status(missing)
    assert not missing.exists()

    admin_registration.ubah(
        admin, operasi_id="operasi_tutup_1", actor_id=ACTOR, revisi=1, path_auth=akun, actor_revisi=2,
        dibuka=False, pesan_kode="closed_standard", token_tinjauan=TOKEN,
        sekarang=60,
    )
    with pytest.raises(PermissionError):
        admin_registration.daftar_publik(
            admin, akun, db, operasi_id="operasi_public_1", alias="publik-satu",
            sandi="publik-123", token_form="F" * 48, sekarang=61,
        )
    assert auth.cari_akun("publik-satu", akun) is None

    admin_registration.ubah(
        admin, operasi_id="operasi_buka_1", actor_id=ACTOR, revisi=2, path_auth=akun, actor_revisi=2,
        dibuka=True, pesan_kode="closed_standard", token_tinjauan="Y" * 48,
        sekarang=62,
    )
    snapshot = admin_registration.daftar_publik(
        admin, akun, db, operasi_id="operasi_public_2", alias="publik-dua",
        sandi="publik-456", token_form="G" * 48, sekarang=63,
    )
    assert snapshot.peran == "guru" and snapshot.revisi_auth == 1
    token_sesi = sessions.buat_dari_principal(
        snapshot, path=sesi, sekarang=64, path_akun=akun
    )
    assert token_sesi is not None

    # Reset sesudah create membuat snapshot lama stale; replay create tidak boleh
    # menghasilkan snapshot mutakhir yang bisa menerbitkan sesi baru.
    perintah_reset = c.PerintahAkun(
        "operasi_reset_public", ACTOR, 2, c.AKSI_RESET_SANDI,
        snapshot.id_akun, 1, "guru", "X" * 48,
    )
    admin_service.jalankan(
        admin, akun, perintah_reset, sandi_baru="publik-reset-789", sekarang=65
    )
    replay = admin_registration.daftar_publik(
        admin, akun, db, operasi_id="operasi_public_2", alias="publik-dua",
        sandi="jangan-dipakai", token_form="G" * 48, sekarang=66,
    )
    assert replay.revisi_auth == 1
    assert sessions.buat_dari_principal(
        replay, path=sesi, sekarang=67, path_akun=akun
    ) is None


def test_admin_create_login_murid_mengunci_db_sampai_auth_commit(storage, monkeypatch):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Lock Anak", "P3", pemilik="keluarga-a")
    perintah = _buat_perintah(82, "lock-anak", murid=True, siswa_id=siswa_id)
    masuk = threading.Event()
    lanjut = threading.Event()
    asli = admin_accounts.buat_akun

    def lambat(*args, **kwargs):
        masuk.set()
        lanjut.wait(5)
        return asli(*args, **kwargs)

    monkeypatch.setattr(admin_accounts, "buat_akun", lambat)
    hasil = []
    galat_db = []

    def buat_login():
        hasil.append(admin_service.buat_akun(
            admin, akun, db, perintah, sandi_baru="murid-lock", sekarang=53
        ))

    def ubah_owner():
        kon = sqlite3.connect(str(db), timeout=0.05)
        try:
            kon.execute("PRAGMA busy_timeout=50")
            kon.execute("UPDATE siswa SET pemilik='berubah' WHERE id=?", (siswa_id,))
            kon.commit()
        except sqlite3.OperationalError as exc:
            galat_db.append(str(exc))
        finally:
            kon.close()

    thread = threading.Thread(target=buat_login)
    thread.start()
    assert masuk.wait(5)
    pesaing = threading.Thread(target=ubah_owner)
    pesaing.start(); pesaing.join(2)
    assert galat_db and "locked" in galat_db[0]
    lanjut.set(); thread.join(5)
    assert len(hasil) == 1 and hasil[0].hasil.status == "succeeded"


def test_public_operation_token_strict_dan_receipt_injection_ditolak(storage):
    admin, akun, db, _sesi = storage
    for operasi, token in (("pendek", "F" * 48), ("operasi_public_strict", "x" * 5000)):
        sebelum = akun.read_bytes()
        with pytest.raises((c.KontrakTidakSah, ValueError)):
            admin_registration.daftar_publik(
                admin, akun, db, operasi_id=operasi, alias="publik-strict",
                sandi="publik-123", token_form=token, sekarang=68,
            )
        assert akun.read_bytes() == sebelum

    data = json.loads(akun.read_text(encoding="utf-8"))
    data["operasi_registrasi"] = {
        "operasi_public_inject": {"sidik_perintah": "x", "payload": "bebas"}
    }
    akun.write_text(json.dumps(data), encoding="utf-8")
    sebelum = akun.read_bytes()
    with pytest.raises(admin_accounts.DomainAkunTidakSah):
        admin_registration.daftar_publik(
            admin, akun, db, operasi_id="operasi_public_inject", alias="publik-inject",
            sandi="publik-123", token_form="Q" * 48, sekarang=69,
        )
    assert akun.read_bytes() == sebelum


def test_public_owner_create_race_guard_tidak_mewariskan_data(storage, monkeypatch):
    admin, akun, db, _sesi = storage
    masuk = threading.Event(); lanjut = threading.Event()
    asli = admin_registration._buat_publik_auth

    def lambat(*args, **kwargs):
        masuk.set(); lanjut.wait(5)
        return asli(*args, **kwargs)

    monkeypatch.setattr(admin_registration, "_buat_publik_auth", lambat)
    hasil = []
    galat = []

    def daftar():
        try:
            hasil.append(admin_registration.daftar_publik(
                admin, akun, db, operasi_id="operasi_owner_race",
                alias="owner-race", sandi="owner-race-123",
                token_form="U" * 48, sekarang=69,
            ))
        except Exception as exc:  # pragma: no cover
            galat.append(exc)

    def tambah_owner():
        try:
            kon = sqlite3.connect(str(db), timeout=0.05)
            kon.execute("PRAGMA busy_timeout=50")
            kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES('Race','P3','owner-race')")
            kon.commit(); kon.close()
        except sqlite3.OperationalError as exc:
            galat.append(exc)

    thread = threading.Thread(target=daftar); thread.start(); assert masuk.wait(5)
    pesaing = threading.Thread(target=tambah_owner); pesaing.start(); pesaing.join(2)
    assert any("locked" in str(exc) for exc in galat)
    lanjut.set(); thread.join(5)
    assert len(hasil) == 1
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa WHERE pemilik='owner-race'").fetchone()[0] == 0


def test_public_close_race_linearizable(storage, monkeypatch):
    admin, akun, db, _sesi = storage
    masuk = threading.Event()
    lanjut = threading.Event()
    asli = admin_registration._buat_publik_auth

    def lambat(*args, **kwargs):
        masuk.set()
        lanjut.wait(5)
        return asli(*args, **kwargs)

    monkeypatch.setattr(admin_registration, "_buat_publik_auth", lambat)
    hasil = []

    def daftar():
        hasil.append(admin_registration.daftar_publik(
            admin, akun, db, operasi_id="operasi_public_race", alias="publik-race",
            sandi="publik-race-123", token_form="H" * 48, sekarang=70,
        ))

    thread = threading.Thread(target=daftar)
    thread.start()
    assert masuk.wait(5)
    selesai_close = threading.Event()

    def tutup():
        admin_registration.ubah(
            admin, operasi_id="operasi_close_race", actor_id=ACTOR, revisi=1, path_auth=akun, actor_revisi=2,
            dibuka=False, pesan_kode="closed_standard", token_tinjauan="I" * 48,
            sekarang=71,
        )
        selesai_close.set()

    closer = threading.Thread(target=tutup)
    closer.start()
    assert not selesai_close.wait(0.05)
    lanjut.set()
    thread.join(5); closer.join(5)
    assert len(hasil) == 1
    assert selesai_close.is_set()
    assert admin_registration.status(admin).dibuka is False
    with pytest.raises(PermissionError):
        admin_registration.daftar_publik(
            admin, akun, db, operasi_id="operasi_public_late", alias="publik-late",
            sandi="publik-late-123", token_form="J" * 48, sekarang=72,
        )


def test_level_stale_dan_failpoint_sebelum_commit_effect_zero(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Level Stale", "P3", pemilik="keluarga-a")
    stale = c.PerintahSiswa(
        "operasi_level_stale", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P4", "P5", TOKEN,
    )
    assert admin_service.ubah_kelas(admin, akun, db, stale, sekarang=78).hasil.status == "conflict"
    with database.buka(db) as kon:
        assert kon.execute("SELECT tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0] == "P3"
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin_siswa WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 0

    gagal = c.PerintahSiswa(
        "operasi_level_fail", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P3", "P4", "W" * 48,
    )
    hasil = admin_service.ubah_kelas(
        admin, akun, db, gagal, sekarang=79, failpoint="sebelum_commit"
    )
    assert hasil.hasil.status == "failed_before_commit"
    with database.buka(db) as kon:
        assert kon.execute("SELECT tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0] == "P3"
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin_siswa WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 0


def test_level_receipt_same_tx_history_same_level_crash_reconcile(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Level Demo", "P3", pemilik="keluarga-a")
    perintah = c.PerintahSiswa(
        "operasi_level_1", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P3", "P4", TOKEN,
    )
    hasil = admin_service.ubah_kelas(admin, akun, db, perintah, sekarang=80)
    assert hasil.hasil.status == "succeeded"
    with database.buka(db) as kon:
        assert kon.execute("SELECT tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0] == "P4"
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=? AND jenis='diganti_level'", (siswa_id,)).fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin_siswa WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 1

    replay = admin_service.ubah_kelas(admin, akun, db, perintah, sekarang=81)
    assert replay.baru_dieksekusi is False
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=? AND jenis='diganti_level'", (siswa_id,)).fetchone()[0] == 1

    sama = c.PerintahSiswa(
        "operasi_level_2", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P4", "P4", "K" * 48,
    )
    assert admin_service.ubah_kelas(admin, akun, db, sama, sekarang=82).hasil.status == "succeeded"
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=?", (siswa_id,)).fetchone()[0] == 1

    crash = c.PerintahSiswa(
        "operasi_level_3", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P4", "P5", "L" * 48,
    )
    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.ubah_kelas(
            admin, akun, db, crash, sekarang=83, failpoint="setelah_commit"
        )
    pulih = admin_service.rekonsiliasi_siswa(admin, akun, db, crash, sekarang=84)
    assert pulih.hasil.status == "succeeded"
    with database.buka(db) as kon:
        assert kon.execute("SELECT tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0] == "P5"
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar WHERE siswa_id=? AND jenis='diganti_level'", (siswa_id,)).fetchone()[0] == 2


def test_lock_order_cross_command_db_lalu_auth_tidak_deadlock(storage, monkeypatch):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "Urutan Lock", "P3", pemilik="keluarga-a"
        )
    perintah = c.PerintahSiswa(
        "operasi_lock_order", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P3", "P4", "D" * 48,
    )
    db_dipegang = threading.Event()
    lanjut_existing = threading.Event()
    selesai_existing = threading.Event()
    actor_lock_level = threading.Event()
    galat = []
    asli_kunci_actor = admin_accounts.kunci_actor

    from contextlib import contextmanager

    @contextmanager
    def catat_kunci_actor(path_auth, command):
        with asli_kunci_actor(path_auth, command):
            actor_lock_level.set()
            yield

    monkeypatch.setattr(admin_accounts, "kunci_actor", catat_kunci_actor)

    def caller_akun_existing():
        try:
            with database.buka(db) as kon:
                kon.execute(
                    "UPDATE siswa SET tingkat=tingkat WHERE id=?", (siswa_id,)
                )
                db_dipegang.set()
                assert lanjut_existing.wait(5)
                auth.tambah_akun(
                    "akun-existing-flow", "sandi-existing-flow", "guru", akun
                )
            selesai_existing.set()
        except Exception as exc:  # pragma: no cover - assertion parent
            galat.append(exc)

    hasil_level = []

    def ubah_level():
        try:
            hasil_level.append(admin_service.ubah_kelas(
                admin, akun, db, perintah, sekarang=89
            ))
        except Exception as exc:  # pragma: no cover - assertion parent
            galat.append(exc)

    existing = threading.Thread(target=caller_akun_existing)
    level = threading.Thread(target=ubah_level)
    existing.start(); assert db_dipegang.wait(5)
    level.start()
    # Saat DB dipegang caller /akun, ubah kelas harus menunggu DB dan belum
    # boleh memegang auth. Kalau urutannya auth->DB, caller akan deadlock.
    assert not actor_lock_level.wait(0.1)
    lanjut_existing.set()
    existing.join(5); level.join(5)

    assert not existing.is_alive() and not level.is_alive()
    assert selesai_existing.is_set() and actor_lock_level.is_set()
    assert galat == []
    assert hasil_level[0].hasil.status == "succeeded"
    assert auth.cari_akun("akun-existing-flow", akun) is not None


def test_anchor_siswa_mencegah_missing_receipt_dianggap_belum_commit(storage):
    admin, akun, db, _sesi = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anchor Demo", "P3", pemilik="keluarga-a")
    perintah = c.PerintahSiswa(
        "operasi_anchor_1", ACTOR, 2, c.AKSI_UBAH_LEVEL,
        siswa_id, "P3", "P4", "O" * 48,
    )
    admin_store.reservasi(admin, perintah, sekarang=90)
    admin_students.siapkan_anchor_admin(admin, perintah, sekarang=90)
    pulih = admin_service.rekonsiliasi_siswa(admin, akun, db, perintah, sekarang=91)
    assert pulih.hasil.status == "uncertain"
    with database.buka(db) as kon:
        assert kon.execute("SELECT tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0] == "P3"


def test_delete_siswa_hanya_guard_tidak_menghapus_history(storage):
    _admin, _akun_path, db, _sesi = storage
    with database.buka(db) as kon:
        kosong = database.tambah_siswa(kon, "Kosong", "P3", pemilik="keluarga-a")
        berisi = database.tambah_siswa(kon, "Berisi", "P3", pemilik="keluarga-a")
        database.buat_sesi(kon, berisi, seed=1)
    assert admin_students.siswa_boleh_dihapus(db, kosong) is True
    assert admin_students.siswa_boleh_dihapus(db, berisi) is False
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa").fetchone()[0] == 2


def test_audit_reader_pending_error_filter_pagination_dan_secrecy(storage):
    admin, akun, db, _sesi = storage
    create = _buat_perintah(20, "audit-alias-rahasia")
    admin_service.buat_akun(
        admin, akun, db, create, sandi_baru="audit-sandi-rahasia", sekarang=100
    )
    pending = c.PerintahAkun(
        "operasi_pending_1", ACTOR, 2, c.AKSI_CABUT_SESI,
        OWNER, 1, "guru", "M" * 48,
    )
    admin_store.reservasi(admin, pending, sekarang=101)
    failed = c.PerintahAkun(
        "operasi_failed_1", ACTOR, 2, c.AKSI_CABUT_SESI,
        OWNER, 1, "guru", "N" * 48,
    )
    admin_store.reservasi(admin, failed, sekarang=102)
    admin_store.finalisasi_gagal(
        admin, failed, status="uncertain", hasil_kode="domain_uncertain", sekarang=103
    )
    halaman = admin_store.daftar_riwayat(admin, per_halaman=2)
    assert halaman.total == 3 and len(halaman.item) == 2 and halaman.jumlah_halaman == 2
    assert {item.status for item in halaman.item} == {"reserved", "uncertain"}
    sukses = admin_store.daftar_riwayat(admin, aksi=c.AKSI_BUAT_GURU, status="succeeded")
    assert sukses.total == 1
    for kwargs in (
        {"aksi": "aksi_bebas"}, {"status": "status_bebas"},
        {"halaman": 0}, {"per_halaman": 101}, {"mulai": 20, "selesai": 10},
    ):
        with pytest.raises(admin_store.DataAuditTidakSah):
            admin_store.daftar_riwayat(admin, **kwargs)
    teks = repr(sukses)
    assert "audit-alias-rahasia" not in teks
    assert "audit-sandi-rahasia" not in teks
    assert TOKEN not in teks


def test_contract_result_create_memuat_hasil_id_tanpa_alias(storage):
    admin, akun, db, _sesi = storage
    perintah = _buat_perintah(30, "shape-demo")
    hasil = admin_service.buat_akun(
        admin, akun, db, perintah, sandi_baru="shape-sandi-123", sekarang=110
    )
    assert hasil.hasil.hasil_id.startswith("akun_")
    assert "shape-demo" not in repr(hasil.hasil)
    assert "shape-sandi-123" not in repr(hasil)
