"""Bulk R: sesi hidup, metadata durable, recovery, dan privasi draft."""

import json
import sqlite3
import threading

import pytest

import admin_bulk
import admin_contracts as c
import admin_service
import admin_store
import auth
import database
import sessions


ACTOR = "akun_" + "a" * 32


@pytest.fixture()
def storage(tmp_path):
    admin = tmp_path / "admin.db"
    akun = tmp_path / "auth.json"
    db = tmp_path / "belajar.db"
    transient = tmp_path / "bulk-transient.db"
    sesi = tmp_path / "sesi.json"
    admin_store.siapkan(admin, sekarang=1)
    admin_bulk.siapkan_transient(transient)
    database.siapkan(db)
    akun.write_text(json.dumps({"akun": [{
        "pengguna": "pengelola", "peran": "admin", "id_akun": ACTOR,
        "revisi_auth": 2, **auth.buat_hash("admin-sintetis"),
    }]}), encoding="utf-8")
    token = sessions.buat(
        "pengelola", "admin", path=sesi, sekarang=0,
        id_akun=ACTOR, revisi_auth=2,
    )
    return admin, akun, db, transient, sesi, token


def _target(i, alias=None, *, revisi=0, peran="guru"):
    hex_id = "%032x" % i
    return admin_bulk.TargetBulk(
        "item_%04d" % i,
        "operasi_bulk_%04d" % i,
        "candidate_" + hex_id if alias is not None else "akun_" + hex_id,
        revisi,
        peran,
        alias,
    )


def _identitas(storage, *, token=None):
    admin, akun, _db, transient, sesi, token_asli = storage
    return dict(
        path_admin=admin, path_transient=transient, path_auth=akun,
        path_sesi=sesi, token_sesi=token_asli if token is None else token,
        actor_id=ACTOR, actor_revisi=2,
    )


def _buat(storage, *, batch_id, aksi=c.AKSI_BUAT_GURU,
          peran="guru", target, sekarang=10):
    return admin_bulk.buat_batch(
        **_identitas(storage), batch_id=batch_id, aksi=aksi,
        target_peran=peran, target=target, sekarang=sekarang,
    )


def _proses(storage, *, batch_id, kelompok_id, sekarang=20, maksimum=10):
    admin, akun, db, transient, sesi, token = storage
    return admin_bulk.proses_kelompok(
        admin, akun, db, path_transient=transient, path_sesi=sesi,
        token_sesi=token, batch_id=batch_id, actor_id=ACTOR,
        actor_revisi=2, kelompok_id=kelompok_id,
        sekarang=sekarang, maksimum=maksimum,
    )


def _baca(storage, batch_id, *, sekarang=20, token=None):
    return admin_bulk.baca_batch(
        **_identitas(storage, token=token), batch_id=batch_id,
        sekarang=sekarang,
    )


def _logout_reset_atau_demosi(perubahan, akun, sesi, token):
    if perubahan == "logout":
        sessions.hapus(token, sesi)
        return
    data = json.loads(akun.read_text(encoding="utf-8"))
    actor = next(x for x in data["akun"] if x["id_akun"] == ACTOR)
    if perubahan == "reset":
        actor["revisi_auth"] += 1
    else:
        actor["peran"] = "guru"
    akun.write_text(json.dumps(data), encoding="utf-8")


def test_csv_satu_kolom_utf8_bom_dan_batas():
    assert admin_bulk.parse_csv_alias(
        b"\xef\xbb\xbfpengguna\r\nalias-satu\r\nalias.dua\r\n"
    ) == ("alias-satu", "alias.dua")
    invalid = (
        b"", b"nama\nx\n", b"pengguna,peran\nx,guru\n",
        b"pengguna\na@b.invalid\n", b"pengguna\n=FORMULA\n",
        b"pengguna\nSama\nsama\n", b"pengguna\n\xff\n",
        b"pengguna\na\x00b\n", b"pengguna\n" + b"x\n" * 101,
        b"x" * (64 * 1024 + 1),
    )
    for data in invalid:
        with pytest.raises(admin_bulk.BulkTidakSah):
            admin_bulk.parse_csv_alias(data)


def test_migrasi_transient_v1_ke_v2_mempertahankan_batch(tmp_path):
    transient = tmp_path / "bulk-v1.db"
    ddl_v1 = admin_bulk._DDL_TRANSIENT.replace(
        "    preflight_selesai INTEGER NOT NULL DEFAULT 0 CHECK(preflight_selesai IN (0,1)),\n",
        "",
    ).replace(
        "    status TEXT NOT NULL CHECK(status IN (\n        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'\n    )),\n    hasil_id TEXT,\n    credential_status TEXT NOT NULL DEFAULT 'not_applicable'\n        CHECK(credential_status IN ('not_applicable','unconfirmed','confirmed')),\n",
        "    status TEXT NOT NULL CHECK(status IN ('pending','succeeded','conflict','uncertain','cancelled')),\n",
    ).split("CREATE TABLE IF NOT EXISTS kelompok_bulk", 1)[0]
    with sqlite3.connect(str(transient)) as kon:
        kon.executescript(ddl_v1)
        kon.execute(
            "INSERT INTO draft_bulk VALUES(?,?,?,?,?,?,?,'partial',?,?)",
            ("batch_migrasi_v1", ACTOR, 2, "f" * 64,
             c.AKSI_BUAT_GURU, "guru", 999, 1, 2),
        )
        kon.execute(
            "INSERT INTO item_bulk VALUES(?,?,?,?,?,?,?,'succeeded')",
            ("batch_migrasi_v1", "item_migrasi", 0, "operasi_migrasi",
             "candidate_" + "d" * 32, 0, "alias-migrasi"),
        )
        kon.execute("PRAGMA user_version=1")
    admin_bulk.siapkan_transient(transient)
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 2
        assert kon.execute("SELECT status FROM item_bulk").fetchone()[0] == "succeeded"
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None


def test_buat_batch_guard_session_dan_durable_tanpa_alias(storage):
    admin, akun, _db, transient, sesi, token = storage
    target = (_target(1, "alias-rahasia"),)
    _buat(storage, batch_id="batch_create", target=target)
    snapshot = _baca(storage, "batch_create")
    assert snapshot.draft_tersedia and snapshot.boleh_proses
    assert snapshot.item[0].alias_valid == "alias-rahasia"
    with sqlite3.connect(str(admin)) as kon:
        dump = "\n".join(kon.iterdump())
        assert "alias-rahasia" not in dump and token not in dump
        assert kon.execute("SELECT jumlah_total FROM batch_admin").fetchone()[0] == 1
    with pytest.raises(PermissionError):
        admin_bulk.buat_batch(
            admin, transient, path_auth=akun, path_sesi=sesi,
            token_sesi="X" * 48, batch_id="batch_invalid_session",
            actor_id=ACTOR, actor_revisi=2, aksi=c.AKSI_BUAT_GURU,
            target_peran="guru", target=target, sekarang=10,
        )


def test_kelompok_replay_stabil_dan_credential_hanya_fresh(storage):
    _admin, akun, _db, _transient, _sesi, _token = storage
    target = tuple(_target(i, "bulk-%02d" % i) for i in range(1, 13))
    _buat(storage, batch_id="batch_stabil", target=target)
    pertama = _proses(
        storage, batch_id="batch_stabil", kelompok_id="kelompok_stabil"
    )
    replay = _proses(
        storage, batch_id="batch_stabil", kelompok_id="kelompok_stabil",
        sekarang=21,
    )
    assert len(pertama) == len(replay) == 10
    assert [item.item_id for item in pertama] == [item.item_id for item in replay]
    assert all(item.credential_sekali for item in pertama)
    assert all(item.credential_sekali is None for item in replay)
    assert len(auth.muat_akun(akun)) == 11
    assert [item.status for item in _baca(storage, "batch_stabil").item].count("pending") == 2


def test_running_recovery_hanya_item_terikat(storage):
    admin, _akun, _db, transient, _sesi, token = storage
    target = tuple(_target(i, "resume-%02d" % i) for i in range(20, 32))
    _buat(storage, batch_id="batch_resume", target=target)
    admin_store.mulai_kelompok_durable(
        admin, batch_id="batch_resume", kelompok_id="kelompok_resume",
        item_ids=tuple(item.item_id for item in target[:10]), sekarang=12,
    )
    with sqlite3.connect(str(transient)) as kon:
        kon.execute(
            "INSERT INTO kelompok_bulk VALUES(?,?,'running',12,12)",
            ("kelompok_resume", "batch_resume"),
        )
        kon.executemany(
            "INSERT INTO kelompok_bulk_item VALUES(?,?,?,?)",
            [("kelompok_resume", "batch_resume", item.item_id, nomor)
             for nomor, item in enumerate(target[:10])],
        )
        kon.execute(
            "UPDATE draft_bulk SET status='running' WHERE batch_id='batch_resume'"
        )
    hasil = _proses(
        storage, batch_id="batch_resume", kelompok_id="kelompok_resume",
        sekarang=13,
    )
    assert [item.item_id for item in hasil] == [item.item_id for item in target[:10]]
    assert all(item.credential_sekali for item in hasil)
    replay = _proses(
        storage, batch_id="batch_resume", kelompok_id="kelompok_resume",
        sekarang=14,
    )
    assert all(item.credential_sekali is None for item in replay)
    assert _baca(storage, "batch_resume", sekarang=14).kelompok_aktif_id is None
    with pytest.raises(admin_store.KonflikOperasi):
        admin_store.mulai_kelompok_durable(
            admin, batch_id="batch_resume", kelompok_id="kelompok_resume",
            item_ids=tuple(item.item_id for item in target[10:]), sekarang=15,
        )
    assert token


@pytest.mark.parametrize("perubahan", ("logout", "reset", "demotion"))
def test_session_hilang_setelah_item_pertama_hentikan_dan_tidak_bocor_credential(
    storage, monkeypatch, perubahan,
):
    admin, akun, _db, _transient, sesi, token = storage
    target = (_target(40, "sesi-satu"), _target(41, "sesi-dua"))
    _buat(storage, batch_id="batch_session_stop", target=target)
    asli = admin_service.buat_akun
    panggilan = {"n": 0}

    def hapus_sesi_setelah_item(*args, **kwargs):
        hasil = asli(*args, **kwargs)
        panggilan["n"] += 1
        if panggilan["n"] == 1:
            _logout_reset_atau_demosi(perubahan, akun, sesi, token)
        return hasil

    monkeypatch.setattr(admin_service, "buat_akun", hapus_sesi_setelah_item)
    with pytest.raises(PermissionError):
        _proses(
            storage, batch_id="batch_session_stop",
            kelompok_id="kelompok_session_stop", sekarang=20,
        )
    assert panggilan["n"] == 1
    assert auth.cari_akun("sesi-satu", akun) is not None
    assert auth.cari_akun("sesi-dua", akun) is None
    durable = admin_store.baca_batch_durable(admin, "batch_session_stop")
    assert durable.batch.status == "stopped"
    assert [item.status for item in durable.item] == ["succeeded", "cancelled"]


def test_expiry_diperiksa_ulang_sebelum_setiap_item(storage, monkeypatch):
    admin, akun, db, transient, sesi, token = storage
    target = (_target(48, "expiry-item-satu"), _target(49, "expiry-item-dua"))
    _buat(storage, batch_id="batch_expiry_item", target=target, sekarang=10)
    clock = {"nilai": 100.0}
    monkeypatch.setattr(admin_bulk.time, "time", lambda: clock["nilai"])
    asli = admin_service.buat_akun
    panggilan = {"n": 0}

    def lewat_ttl_setelah_item(*args, **kwargs):
        hasil = asli(*args, **kwargs)
        panggilan["n"] += 1
        clock["nilai"] = sessions.TTL_DETIK + 1.0
        return hasil

    monkeypatch.setattr(admin_service, "buat_akun", lewat_ttl_setelah_item)
    with pytest.raises(PermissionError):
        admin_bulk.proses_kelompok(
            admin, akun, db, path_transient=transient, path_sesi=sesi,
            token_sesi=token, batch_id="batch_expiry_item", actor_id=ACTOR,
            actor_revisi=2, kelompok_id="kelompok_expiry_item",
        )
    assert panggilan["n"] == 1
    assert auth.cari_akun("expiry-item-satu", akun) is not None
    assert auth.cari_akun("expiry-item-dua", akun) is None
    assert [x.status for x in admin_store.baca_batch_durable(
        admin, "batch_expiry_item"
    ).item] == ["succeeded", "cancelled"]


def test_expiry_diperiksa_setelah_menunggu_lock(storage, monkeypatch):
    admin, akun, db, transient, sesi, token = storage
    _buat(
        storage, batch_id="batch_expiry", target=(_target(50, "expiry-satu"),),
        sekarang=10,
    )
    waktu = iter((100.0, sessions.TTL_DETIK + 1.0))
    monkeypatch.setattr(admin_bulk.time, "time", lambda: next(waktu))
    with pytest.raises(PermissionError):
        admin_bulk.proses_kelompok(
            admin, akun, db, path_transient=transient, path_sesi=sesi,
            token_sesi=token, batch_id="batch_expiry", actor_id=ACTOR,
            actor_revisi=2, kelompok_id="kelompok_expiry",
        )
    assert auth.cari_akun("expiry-satu", akun) is None


def test_sesi_baru_tidak_mewarisi_batch_sesi_lama(storage):
    _admin, akun, _db, _transient, sesi, token = storage
    _buat(
        storage, batch_id="batch_sesi_lama",
        target=(_target(58, "sesi-lama"),),
    )
    sessions.hapus(token, sesi)
    token_baru = sessions.buat(
        "pengelola", "admin", path=sesi, sekarang=20,
        id_akun=ACTOR, revisi_auth=2,
    )
    with pytest.raises(LookupError):
        _baca(storage, "batch_sesi_lama", sekarang=21, token=token_baru)
    assert auth.cari_akun("pengelola", akun) is not None


def test_fallback_durable_setelah_draft_hilang_dan_confirmed_tetap(storage):
    admin, _akun, _db, transient, _sesi, _token = storage
    target = (_target(60, "fallback-satu"),)
    _buat(storage, batch_id="batch_fallback", target=target)
    hasil = _proses(
        storage, batch_id="batch_fallback", kelompok_id="kelompok_fallback"
    )
    admin_bulk.konfirmasi_penyerahan(
        **_identitas(storage), batch_id="batch_fallback",
        item_ids=(target[0].item_id,), operasi_id="operasi_serah_fallback",
        sekarang=21,
    )
    transient.unlink()
    snapshot = _baca(storage, "batch_fallback", sekarang=22)
    assert not snapshot.draft_tersedia and not snapshot.boleh_proses
    assert snapshot.item[0].alias_valid is None
    assert snapshot.item[0].hasil_id == hasil[0].hasil_id
    assert snapshot.item[0].credential_status == "confirmed"
    assert snapshot.item[0].operasi_id == target[0].operasi_id


def test_pending_create_tanpa_draft_attention_tidak_boleh_proses(storage):
    _admin, _akun, _db, transient, _sesi, _token = storage
    _buat(
        storage, batch_id="batch_pending_lost",
        target=(_target(70, "pending-rahasia"),),
    )
    transient.unlink()
    snapshot = _baca(storage, "batch_pending_lost")
    assert snapshot.status == "attention"
    assert not snapshot.draft_tersedia and not snapshot.boleh_proses
    assert snapshot.item[0].alias_valid is None
    with pytest.raises(admin_bulk.BulkTidakSah, match="draft"):
        _proses(
            storage, batch_id="batch_pending_lost",
            kelompok_id="kelompok_pending_lost",
        )


def test_crash_create_setelah_durable_retry_merekonsiliasi_draft(storage, monkeypatch):
    admin, _akun, _db, transient, _sesi, _token = storage
    target = (_target(75, "crash-create"),)
    asli = admin_bulk._upsert_transient_batch
    panggilan = {"n": 0}

    def crash_sekali(*args, **kwargs):
        panggilan["n"] += 1
        if panggilan["n"] == 1:
            raise RuntimeError("crash sintetis setelah durable")
        return asli(*args, **kwargs)

    monkeypatch.setattr(admin_bulk, "_upsert_transient_batch", crash_sekali)
    with pytest.raises(RuntimeError, match="crash sintetis"):
        _buat(storage, batch_id="batch_crash_create", target=target)
    durable = admin_store.baca_batch_durable(admin, "batch_crash_create")
    assert durable.batch.status == "ready" and durable.item[0].status == "pending"
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT COUNT(*) FROM draft_bulk WHERE batch_id='batch_crash_create'"
        ).fetchone()[0] == 0
    _buat(storage, batch_id="batch_crash_create", target=target)
    assert _baca(storage, "batch_crash_create").boleh_proses
    with sqlite3.connect(str(admin)) as kon:
        assert kon.execute(
            "SELECT COUNT(*) FROM batch_admin WHERE batch_id='batch_crash_create'"
        ).fetchone()[0] == 1


def test_crash_item_setelah_durable_retry_tidak_mengulang_operasi(storage, monkeypatch):
    admin, akun, _db, transient, _sesi, _token = storage
    target = (_target(76, "crash-item"),)
    _buat(storage, batch_id="batch_crash_item", target=target)
    asli_transaksi = admin_bulk._transaksi
    crash = {"aktif": False}

    from contextlib import contextmanager

    @contextmanager
    def crash_transient(path):
        if crash["aktif"]:
            crash["aktif"] = False
            raise RuntimeError("crash sintetis item transient")
        with asli_transaksi(path) as kon:
            yield kon

    asli_catat = admin_store.catat_item_batch_durable

    def aktifkan_crash(*args, **kwargs):
        setelah = kwargs["setelah"]

        def setelah_durable():
            crash["aktif"] = True
            setelah()

        kwargs["setelah"] = setelah_durable
        return asli_catat(*args, **kwargs)

    monkeypatch.setattr(admin_bulk, "_transaksi", crash_transient)
    monkeypatch.setattr(admin_store, "catat_item_batch_durable", aktifkan_crash)
    with pytest.raises(RuntimeError, match="crash sintetis item"):
        _proses(
            storage, batch_id="batch_crash_item",
            kelompok_id="kelompok_crash_item",
        )
    assert auth.cari_akun("crash-item", akun) is not None
    assert admin_store.baca_batch_durable(
        admin, "batch_crash_item"
    ).item[0].status == "succeeded"
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT status FROM item_bulk WHERE batch_id='batch_crash_item'"
        ).fetchone()[0] == "pending"
    replay = _proses(
        storage, batch_id="batch_crash_item",
        kelompok_id="kelompok_crash_item", sekarang=21,
    )
    assert len(replay) == 1 and replay[0].credential_sekali is None
    assert len([x for x in auth.muat_akun(akun) if x["pengguna"] == "crash-item"]) == 1


def test_stop_dan_handover_guard_actor_session_sebelum_commit(storage, monkeypatch):
    admin, akun, _db, transient, sesi, token = storage
    target = (_target(80, "guard-stop"),)
    _buat(storage, batch_id="batch_guard_stop", target=target)
    asli_stop = admin_store.hentikan_batch_durable_dengan_guard

    def reset_sebelum_stop(*args, **kwargs):
        auth.naikkan_revisi_auth(ACTOR, akun)
        return asli_stop(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "hentikan_batch_durable_dengan_guard", reset_sebelum_stop
    )
    sebelum_transient = transient.read_bytes()
    sebelum_durable = admin.read_bytes()
    with pytest.raises(PermissionError):
        admin_bulk.hentikan(
            admin, transient, path_auth=akun, path_sesi=sesi,
            token_sesi=token, batch_id="batch_guard_stop",
            actor_id=ACTOR, actor_revisi=2, sekarang=20,
        )
    assert transient.read_bytes() == sebelum_transient
    assert admin.read_bytes() == sebelum_durable


@pytest.mark.parametrize("perubahan", ("logout", "reset", "demotion"))
def test_kelompok_guard_session_sebelum_commit_matrix(storage, monkeypatch, perubahan):
    admin, akun, _db, transient, sesi, token = storage
    target = (_target(83, "guard-group"),)
    _buat(storage, batch_id="batch_guard_group", target=target)
    asli = admin_store.mulai_kelompok_durable_dengan_guard

    def cabut_sebelum_commit(*args, **kwargs):
        _logout_reset_atau_demosi(perubahan, akun, sesi, token)
        return asli(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "mulai_kelompok_durable_dengan_guard", cabut_sebelum_commit
    )
    sebelum_transient = transient.read_bytes()
    sebelum_durable = admin.read_bytes()
    with pytest.raises(PermissionError):
        _proses(
            storage, batch_id="batch_guard_group",
            kelompok_id="kelompok_guard_group", sekarang=20,
        )
    assert transient.read_bytes() == sebelum_transient
    assert admin.read_bytes() == sebelum_durable


@pytest.mark.parametrize("perubahan", ("logout", "reset", "demotion"))
def test_stop_guard_session_sebelum_commit_matrix(storage, monkeypatch, perubahan):
    admin, akun, _db, transient, sesi, token = storage
    target = (_target(84, "guard-stop-matrix"),)
    _buat(storage, batch_id="batch_guard_stop_matrix", target=target)
    asli = admin_store.hentikan_batch_durable_dengan_guard

    def cabut_sebelum_commit(*args, **kwargs):
        _logout_reset_atau_demosi(perubahan, akun, sesi, token)
        return asli(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "hentikan_batch_durable_dengan_guard", cabut_sebelum_commit
    )
    sebelum_transient = transient.read_bytes()
    sebelum_durable = admin.read_bytes()
    with pytest.raises(PermissionError):
        admin_bulk.hentikan(
            **_identitas(storage), batch_id="batch_guard_stop_matrix",
            sekarang=20,
        )
    assert transient.read_bytes() == sebelum_transient
    assert admin.read_bytes() == sebelum_durable


@pytest.mark.parametrize("perubahan", ("logout", "reset", "demotion"))
def test_handover_guard_session_sebelum_commit(storage, monkeypatch, perubahan):
    admin, akun, _db, transient, sesi, token = storage
    target = (_target(85, "guard-handover"),)
    _buat(storage, batch_id="batch_guard_handover", target=target)
    _proses(
        storage, batch_id="batch_guard_handover",
        kelompok_id="kelompok_guard_handover",
    )
    asli = admin_store.konfirmasi_penyerahan_durable_dengan_guard

    def cabut_sebelum_commit(*args, **kwargs):
        _logout_reset_atau_demosi(perubahan, akun, sesi, token)
        return asli(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "konfirmasi_penyerahan_durable_dengan_guard",
        cabut_sebelum_commit,
    )
    sebelum_transient = transient.read_bytes()
    sebelum_durable = admin.read_bytes()
    with pytest.raises(PermissionError):
        admin_bulk.konfirmasi_penyerahan(
            **_identitas(storage), batch_id="batch_guard_handover",
            item_ids=(target[0].item_id,), operasi_id="operasi_serah_guard",
            sekarang=21,
        )
    assert transient.read_bytes() == sebelum_transient
    assert admin.read_bytes() == sebelum_durable


def test_crash_stop_setelah_durable_retry_merekonsiliasi_transient(storage, monkeypatch):
    admin, _akun, _db, transient, _sesi, _token = storage
    target = (_target(86, "crash-stop"),)
    _buat(storage, batch_id="batch_crash_stop", target=target)
    asli = admin_store.hentikan_batch_durable_dengan_guard
    panggilan = {"n": 0}

    def crash_setelah_durable(*args, **kwargs):
        setelah = kwargs["setelah"]

        def callback():
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                raise RuntimeError("crash sintetis stop")
            setelah()

        kwargs["setelah"] = callback
        return asli(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "hentikan_batch_durable_dengan_guard", crash_setelah_durable
    )
    with pytest.raises(RuntimeError, match="crash sintetis stop"):
        admin_bulk.hentikan(
            **_identitas(storage), batch_id="batch_crash_stop", sekarang=20
        )
    assert admin_store.baca_batch_durable(
        admin, "batch_crash_stop"
    ).batch.status == "stopped"
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT status FROM draft_bulk WHERE batch_id='batch_crash_stop'"
        ).fetchone()[0] == "ready"
    admin_bulk.hentikan(
        **_identitas(storage), batch_id="batch_crash_stop", sekarang=21
    )
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT status FROM draft_bulk WHERE batch_id='batch_crash_stop'"
        ).fetchone()[0] == "stopped"


def test_crash_handover_setelah_durable_retry_merekonsiliasi_transient(storage, monkeypatch):
    admin, _akun, _db, transient, _sesi, _token = storage
    target = (_target(87, "crash-handover"),)
    _buat(storage, batch_id="batch_crash_handover", target=target)
    _proses(
        storage, batch_id="batch_crash_handover",
        kelompok_id="kelompok_crash_handover",
    )
    asli = admin_store.konfirmasi_penyerahan_durable_dengan_guard
    panggilan = {"n": 0}

    def crash_setelah_durable(*args, **kwargs):
        setelah = kwargs["setelah"]

        def callback():
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                raise RuntimeError("crash sintetis handover")
            setelah()

        kwargs["setelah"] = callback
        return asli(*args, **kwargs)

    monkeypatch.setattr(
        admin_store, "konfirmasi_penyerahan_durable_dengan_guard",
        crash_setelah_durable,
    )
    kwargs = dict(
        **_identitas(storage), batch_id="batch_crash_handover",
        item_ids=(target[0].item_id,), operasi_id="operasi_crash_handover",
        sekarang=21,
    )
    with pytest.raises(RuntimeError, match="crash sintetis handover"):
        admin_bulk.konfirmasi_penyerahan(**kwargs)
    assert admin_store.baca_batch_durable(
        admin, "batch_crash_handover"
    ).item[0].credential_status == "confirmed"
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT credential_status FROM item_bulk WHERE batch_id='batch_crash_handover'"
        ).fetchone()[0] == "unconfirmed"
    admin_bulk.konfirmasi_penyerahan(**dict(kwargs, sekarang=22))
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute(
            "SELECT credential_status FROM item_bulk WHERE batch_id='batch_crash_handover'"
        ).fetchone()[0] == "confirmed"


def test_handover_receipt_durable_idempoten_dan_tanpa_alias(storage):
    admin, _akun, _db, _transient, _sesi, _token = storage
    target = (_target(90, "serah-rahasia"),)
    _buat(storage, batch_id="batch_handover", target=target)
    _proses(storage, batch_id="batch_handover", kelompok_id="kelompok_handover")
    kwargs = dict(
        **_identitas(storage), batch_id="batch_handover",
        item_ids=(target[0].item_id,), operasi_id="operasi_serah_0001",
        sekarang=21,
    )
    admin_bulk.konfirmasi_penyerahan(**kwargs)
    admin_bulk.konfirmasi_penyerahan(**kwargs)
    detail = admin_store.baca_batch_durable(admin, "batch_handover")
    assert detail.item[0].credential_status == "confirmed"
    assert len(detail.penyerahan) == 1
    with sqlite3.connect(str(admin)) as kon:
        dump = "\n".join(kon.iterdump())
    assert "serah-rahasia" not in dump
    assert _identitas(storage)["token_sesi"] not in dump


def test_reader_audit_batch_paginated_dan_detail_tanpa_alias(storage):
    admin, _akun, _db, _transient, _sesi, _token = storage
    for nomor in range(3):
        _buat(
            storage, batch_id="batch_audit_%02d" % nomor,
            target=(_target(100 + nomor, "audit-%02d" % nomor),),
            sekarang=30 + nomor,
        )
    halaman = admin_store.daftar_batch_durable(
        admin, actor_id=ACTOR, halaman=1, per_halaman=2
    )
    assert halaman.total == 3 and len(halaman.item) == 2
    assert halaman.jumlah_halaman == 2
    detail = admin_store.baca_batch_durable(admin, "batch_audit_00")
    assert detail.item[0].operasi_id == "operasi_bulk_0100"
    assert not hasattr(detail.batch, "session_hash")
    assert "audit-00" not in repr(detail)
    with pytest.raises(admin_store.DataAuditTidakSah):
        admin_store.daftar_batch_durable(admin, status="asing")


def test_all_pending_preflight_create_dan_existing(storage):
    admin, akun, db, _transient, _sesi, _token = storage
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Owner Lama", "P3", pemilik="alias-belakang")
    create = tuple(_target(120 + i, "valid-%02d" % i) for i in range(10)) + (
        _target(130, "alias-belakang"),
    )
    _buat(storage, batch_id="batch_preflight_create", target=create)
    with pytest.raises(admin_bulk.BulkTidakSah):
        _proses(
            storage, batch_id="batch_preflight_create",
            kelompok_id="kelompok_preflight_create",
        )
    assert admin_store.baca_operasi(admin, create[0].operasi_id) is None

    existing = []
    for nomor in range(12):
        auth.tambah_akun(
            "guru-%02d" % nomor, "sandi-lama-%02d" % nomor, "guru", akun
        )
        item = auth.cari_akun("guru-%02d" % nomor, akun)
        existing.append(admin_bulk.TargetBulk(
            "item_existing_%02d" % nomor,
            "operasi_existing_%02d" % nomor,
            item["id_akun"], item["revisi_auth"], "guru",
        ))
    terakhir = existing[-1]
    existing[-1] = admin_bulk.TargetBulk(
        terakhir.item_id, terakhir.operasi_id, terakhir.target_id, 99, "guru"
    )
    _buat(
        storage, batch_id="batch_preflight_existing",
        aksi=c.AKSI_CABUT_SESI, target=tuple(existing),
    )
    with pytest.raises(admin_bulk.BulkTidakSah):
        _proses(
            storage, batch_id="batch_preflight_existing",
            kelompok_id="kelompok_preflight_existing",
        )
    assert admin_store.baca_operasi(admin, existing[0].operasi_id) is None


def test_purge_transient_tidak_menghapus_metadata_durable(storage):
    admin, _akun, _db, transient, _sesi, _token = storage
    _buat(
        storage, batch_id="batch_purge",
        target=(_target(150, "purge-rahasia"),), sekarang=1,
    )
    assert admin_bulk.purge_draft(transient, sekarang=901) == 1
    assert admin_store.baca_batch_durable(admin, "batch_purge") is not None
    snapshot = _baca(storage, "batch_purge", sekarang=901)
    assert snapshot.status == "attention" and not snapshot.boleh_proses


def test_bulk_durable_backup_tidak_memuat_alias(storage, tmp_path):
    admin, _akun, _db, transient, _sesi, _token = storage
    _buat(
        storage, batch_id="batch_backup",
        target=(_target(160, "alias-transient-rahasia"),),
    )
    cadangan = tmp_path / "admin-backup.db"
    with sqlite3.connect(str(admin)) as sumber, sqlite3.connect(str(cadangan)) as tujuan:
        sumber.backup(tujuan)
    with sqlite3.connect(str(cadangan)) as kon:
        tabel = {row[0] for row in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "batch_admin" in tabel and "draft_bulk" not in tabel
    assert b"alias-transient-rahasia" not in cadangan.read_bytes()
    assert b"alias-transient-rahasia" in transient.read_bytes()


def test_baca_operasional_menolak_logout_reset_demosi_dan_expiry(storage):
    _admin, akun, _db, _transient, sesi, token = storage
    target = (_target(165, "read-guard"),)
    for perubahan in ("logout", "reset", "demotion"):
        # Fixture dipulihkan manual per subcase agar batch/token selalu identik.
        data = json.loads(akun.read_text(encoding="utf-8"))
        actor = next(x for x in data["akun"] if x["id_akun"] == ACTOR)
        actor["peran"] = "admin"
        actor["revisi_auth"] = 2
        akun.write_text(json.dumps(data), encoding="utf-8")
        if token not in sessions.muat(sesi):
            raw = sessions.muat(sesi)
            raw[token] = {
                "pengguna": "pengelola", "peran": "admin",
                "id_akun": ACTOR, "revisi_auth": 2,
                "kedaluarsa": sessions.TTL_DETIK,
            }
            sessions._tulis(raw, sesi)
        if perubahan == "logout" and not _baca_or_create_batch_marker(storage):
            _buat(storage, batch_id="batch_read_guard", target=target)
        elif perubahan != "logout" and admin_store.baca_batch_durable(
            _admin, "batch_read_guard"
        ) is None:
            _buat(storage, batch_id="batch_read_guard", target=target)
        _logout_reset_atau_demosi(perubahan, akun, sesi, token)
        with pytest.raises(PermissionError):
            _baca(storage, "batch_read_guard", sekarang=20)
    # Restore exact principal untuk kasus expiry terpisah.
    data = json.loads(akun.read_text(encoding="utf-8"))
    actor = next(x for x in data["akun"] if x["id_akun"] == ACTOR)
    actor["peran"] = "admin"; actor["revisi_auth"] = 2
    akun.write_text(json.dumps(data), encoding="utf-8")
    raw = sessions.muat(sesi)
    raw[token] = {
        "pengguna": "pengelola", "peran": "admin", "id_akun": ACTOR,
        "revisi_auth": 2, "kedaluarsa": sessions.TTL_DETIK,
    }
    sessions._tulis(raw, sesi)
    with pytest.raises(PermissionError):
        _baca(storage, "batch_read_guard", sekarang=sessions.TTL_DETIK + 1)


def _baca_or_create_batch_marker(storage):
    return admin_store.baca_batch_durable(storage[0], "batch_read_guard") is not None


def test_handover_menolak_pending_duplikat_revoke_dan_session_lain(storage):
    admin, akun, db, _transient, sesi, token = storage
    target = (_target(170, "handover-negatif"),)
    _buat(storage, batch_id="batch_handover_negatif", target=target)
    dasar = dict(
        **_identitas(storage), batch_id="batch_handover_negatif",
        operasi_id="operasi_serah_negatif", sekarang=20,
    )
    with pytest.raises(admin_bulk.BulkTidakSah):
        admin_bulk.konfirmasi_penyerahan(
            item_ids=(target[0].item_id,), **dasar
        )
    with pytest.raises(admin_bulk.BulkTidakSah):
        admin_bulk.konfirmasi_penyerahan(
            item_ids=(target[0].item_id, target[0].item_id), **dasar
        )
    with pytest.raises(PermissionError):
        admin_bulk.konfirmasi_penyerahan(
            item_ids=(target[0].item_id,),
            **dict(dasar, token_sesi="X" * 48),
        )

    auth.tambah_akun("guru-revoke", "sandi-revoke", "guru", akun)
    akun_target = auth.cari_akun("guru-revoke", akun)
    revoke = admin_bulk.TargetBulk(
        "item_revoke", "operasi_revoke", akun_target["id_akun"],
        akun_target["revisi_auth"], "guru",
    )
    _buat(
        storage, batch_id="batch_revoke", aksi=c.AKSI_CABUT_SESI,
        target=(revoke,),
    )
    _proses(storage, batch_id="batch_revoke", kelompok_id="kelompok_revoke")
    with pytest.raises(admin_bulk.BulkTidakSah):
        admin_bulk.konfirmasi_penyerahan(
            **_identitas(storage), batch_id="batch_revoke",
            item_ids=(revoke.item_id,), operasi_id="operasi_serah_revoke",
            sekarang=21,
        )


def test_reader_missing_tidak_membuat_transient(storage, tmp_path):
    admin, akun, _db, _transient, sesi, token = storage
    missing = tmp_path / "missing.db"
    with pytest.raises(LookupError):
        admin_bulk.baca_batch(
            admin, missing, path_auth=akun, path_sesi=sesi, token_sesi=token,
            batch_id="batch_missing", actor_id=ACTOR, actor_revisi=2,
            sekarang=20,
        )
    assert not missing.exists()
