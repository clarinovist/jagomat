"""Saga hapus siswa kosong: login→siswa, recovery, race, dan replay."""

import json
import sqlite3
import threading

import pytest

import admin_accounts
import admin_contracts as c
import admin_service
import admin_store
import admin_students
import auth
import database


ACTOR = "akun_" + "a" * 32
OWNER = "akun_" + "b" * 32
TOKEN = "D" * 48


@pytest.fixture()
def storage(tmp_path):
    admin = tmp_path / "admin.db"
    akun = tmp_path / "auth.json"
    db = tmp_path / "belajar.db"
    admin_store.siapkan(admin, sekarang=1)
    database.siapkan(db)
    admin_students.siapkan(db)
    akun.write_text(json.dumps({"akun": [
        {"pengguna": "pengelola", "peran": "admin", "id_akun": ACTOR,
         "revisi_auth": 2, **auth.buat_hash("admin-sintetis")},
        {"pengguna": "keluarga-a", "peran": "guru", "id_akun": OWNER,
         "revisi_auth": 1, **auth.buat_hash("guru-sintetis")},
    ], "operasi_admin": {}}), encoding="utf-8")
    return admin, akun, db


def _buat_siswa_login(storage, *, nama="Siswa Kosong", login=True):
    _admin, akun, db = storage
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, nama, "P3", pemilik="keluarga-a")
    login_id = None
    if login:
        auth.tambah_akun(nama.lower().replace(" ", "-"), "murid-sintetis", "murid", akun, siswa_id=siswa_id)
        item = auth.cari_akun(nama.lower().replace(" ", "-"), akun)
        login_id = item["id_akun"]
    return siswa_id, login_id


def _perintah(siswa_id, login_id, nomor=1, nama="Siswa Kosong"):
    del nama  # kompatibilitas helper test; nama tidak masuk command/durable.
    return c.PerintahHapusSiswa(
        "operasi_delete_%04d" % nomor,
        ACTOR,
        2,
        c.AKSI_HAPUS_SISWA,
        siswa_id,
        "P3",
        login_id,
        1 if login_id else None,
        TOKEN,
    )


def _ada_siswa(db, siswa_id):
    with database.buka(db) as kon:
        return kon.execute("SELECT 1 FROM siswa WHERE id=?", (siswa_id,)).fetchone() is not None


def test_tinjau_hapus_siswa_hanya_snapshot_id_dan_menolak_legacy(storage):
    _admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Nama Tidak Durable")

    snapshot = admin_students.tinjau_hapus_siswa(db, akun, siswa_id)

    assert snapshot == admin_students.SnapshotHapusSiswa(
        siswa_id, "P3", login_id, 1
    )
    assert "Nama Tidak Durable" not in repr(snapshot)
    raw = json.loads(akun.read_text(encoding="utf-8"))
    raw["akun"].append({
        "pengguna": "Nama Tidak Durable",
        "peran": "murid",
        "id_akun": "akun_" + "e" * 32,
        "revisi_auth": 1,
        **auth.buat_hash("legacy-sintetis"),
    })
    akun.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(admin_accounts.KonflikAkun, match="ambigu"):
        admin_students.tinjau_hapus_siswa(db, akun, siswa_id)


def test_hapus_siswa_dengan_login_sukses_dan_replay(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage)
    perintah = _perintah(siswa_id, login_id)

    hasil = admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=10)
    replay = admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=11)

    assert hasil.hasil.status == "succeeded" and hasil.baru_dieksekusi is True
    assert replay.hasil == hasil.hasil and replay.baru_dieksekusi is False
    assert not _ada_siswa(db, siswa_id)
    assert all(a.get("id_akun") != login_id for a in auth.muat_akun(akun))
    with sqlite3.connect(str(db)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin_siswa WHERE operasi_id=?", (perintah.operasi_id,)).fetchone()[0] == 1
    raw = json.loads(akun.read_text(encoding="utf-8"))
    assert any(r["hasil_kode"] == "login_deleted" for r in raw["operasi_admin"].values())


def test_replay_sukses_setelah_siswa_hilang_tetap_revalidasi_actor(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Replay Actor")
    perintah = _perintah(siswa_id, login_id, 12, "Replay Actor")
    hasil = admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=12)
    assert hasil.hasil.status == "succeeded" and not _ada_siswa(db, siswa_id)

    data = json.loads(akun.read_text(encoding="utf-8"))
    actor = next(item for item in data["akun"] if item["id_akun"] == ACTOR)
    actor["revisi_auth"] = 3
    akun.write_text(json.dumps(data), encoding="utf-8")
    sebelum_admin = admin.read_bytes()
    sebelum_auth = akun.read_bytes()

    with pytest.raises(admin_service.OperasiTidakDapatDilanjutkan):
        admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=13)
    assert admin.read_bytes() == sebelum_admin
    assert akun.read_bytes() == sebelum_auth
    assert not _ada_siswa(db, siswa_id)


def test_hapus_siswa_tanpa_login_sukses(storage):
    admin, akun, db = storage
    siswa_id, _ = _buat_siswa_login(storage, nama="Tanpa Login", login=False)
    hasil = admin_service.hapus_siswa(
        admin, akun, db, _perintah(siswa_id, None, 2, "Tanpa Login"), sekarang=20
    )
    assert hasil.hasil.status == "succeeded"
    assert not _ada_siswa(db, siswa_id)


def test_history_protected_ditolak_effect_zero(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Ada Riwayat")
    with database.buka(db) as kon:
        database.buat_sesi(kon, siswa_id, seed=1)
    sebelum = akun.read_bytes()

    hasil = admin_service.hapus_siswa(
        admin, akun, db, _perintah(siswa_id, login_id, 3, "Ada Riwayat"), sekarang=30
    )
    assert hasil.hasil.status == "conflict"
    assert akun.read_bytes() == sebelum
    assert _ada_siswa(db, siswa_id)


def test_crash_setelah_login_delete_lanjut_hanya_delete_siswa(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Crash Login")
    perintah = _perintah(siswa_id, login_id, 4, "Crash Login")

    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.hapus_siswa(
            admin, akun, db, perintah, sekarang=40,
            failpoint="setelah_login_delete",
        )
    assert _ada_siswa(db, siswa_id)
    assert all(a.get("id_akun") != login_id for a in auth.muat_akun(akun))

    pulih = admin_service.rekonsiliasi_hapus_siswa(
        admin, akun, db, perintah, sekarang=41
    )
    assert pulih.hasil.status == "succeeded"
    assert not _ada_siswa(db, siswa_id)
    assert pulih.credential_sekali is None


def test_crash_setelah_student_delete_before_commit_sama_dengan_login_deleted(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Crash DB")
    perintah = _perintah(siswa_id, login_id, 5, "Crash DB")

    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.hapus_siswa(
            admin, akun, db, perintah, sekarang=50,
            failpoint="setelah_student_delete_sebelum_commit",
        )
    assert _ada_siswa(db, siswa_id)
    assert all(a.get("id_akun") != login_id for a in auth.muat_akun(akun))
    pulih = admin_service.rekonsiliasi_hapus_siswa(
        admin, akun, db, perintah, sekarang=51
    )
    assert pulih.hasil.status == "succeeded"
    assert not _ada_siswa(db, siswa_id)


def test_crash_setelah_domain_commit_finalize_tanpa_delete_ulang(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Crash Final")
    perintah = _perintah(siswa_id, login_id, 6, "Crash Final")

    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.hapus_siswa(
            admin, akun, db, perintah, sekarang=60,
            failpoint="setelah_domain_commit",
        )
    assert not _ada_siswa(db, siswa_id)
    pulih = admin_service.rekonsiliasi_hapus_siswa(
        admin, akun, db, perintah, sekarang=61
    )
    assert pulih.hasil.status == "succeeded"


def test_history_muncul_setelah_login_delete_membuat_uncertain_tanpa_hapus(storage, monkeypatch):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Race History")
    perintah = _perintah(siswa_id, login_id, 7, "Race History")
    asli = admin_students._referensi_siswa_ada
    hitung = {"n": 0}

    def berubah(kon, sid):
        hitung["n"] += 1
        if hitung["n"] == 2:
            return True
        return asli(kon, sid)

    monkeypatch.setattr(admin_students, "_referensi_siswa_ada", berubah)
    hasil = admin_service.hapus_siswa(
        admin, akun, db, perintah, sekarang=70
    )
    assert hasil.hasil.status == "uncertain"
    assert _ada_siswa(db, siswa_id)
    assert all(a.get("id_akun") != login_id for a in auth.muat_akun(akun))
    # Simulasikan history/provenance yang benar-benar muncul setelah langkah
    # login; recovery wajib tetap menahan delete, bukan hanya mengandalkan mock.
    monkeypatch.setattr(admin_students, "_referensi_siswa_ada", asli)
    with database.buka(db) as kon:
        database.buat_sesi(kon, siswa_id, seed=9)
    replay = admin_service.rekonsiliasi_hapus_siswa(
        admin, akun, db, perintah, sekarang=71
    )
    assert replay.hasil.status == "uncertain"
    assert _ada_siswa(db, siswa_id)


def test_concurrent_sesi_baru_diblokir_db_lock(storage, monkeypatch):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Race Sesi")
    perintah = _perintah(siswa_id, login_id, 8, "Race Sesi")
    masuk = threading.Event(); lanjut = threading.Event()
    asli = admin_accounts.langkah_login_hapus_siswa
    from contextlib import contextmanager

    @contextmanager
    def lambat(*args, **kwargs):
        with asli(*args, **kwargs) as hasil:
            masuk.set(); lanjut.wait(5)
            yield hasil

    monkeypatch.setattr(admin_accounts, "langkah_login_hapus_siswa", lambat)
    hasil = []
    thread = threading.Thread(target=lambda: hasil.append(
        admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=80)
    ))
    thread.start(); assert masuk.wait(5)
    galat = []

    def buat_sesi():
        kon = sqlite3.connect(str(db), timeout=0.05)
        try:
            kon.execute("PRAGMA busy_timeout=50")
            kon.execute("INSERT INTO sesi(siswa_id,seed) VALUES(?,1)", (siswa_id,))
            kon.commit()
        except sqlite3.OperationalError as exc:
            galat.append(str(exc))
        finally:
            kon.close()

    pesaing = threading.Thread(target=buat_sesi); pesaing.start(); pesaing.join(2)
    assert galat and "locked" in galat[0]
    lanjut.set(); thread.join(5)
    assert hasil[0].hasil.status == "succeeded"
    assert not _ada_siswa(db, siswa_id)


def test_no_login_concurrent_create_menunggu_auth_hingga_db_commit(storage, monkeypatch):
    admin, akun, db = storage
    siswa_id, _ = _buat_siswa_login(storage, nama="Tanpa Login Race", login=False)
    perintah = _perintah(siswa_id, None, 11, "Tanpa Login Race")
    masuk = threading.Event(); lanjut = threading.Event(); galat = []
    asli = admin_accounts.langkah_login_hapus_siswa
    from contextlib import contextmanager

    @contextmanager
    def tahan(*args, **kwargs):
        with asli(*args, **kwargs) as hasil:
            masuk.set(); lanjut.wait(5)
            yield hasil

    monkeypatch.setattr(admin_accounts, "langkah_login_hapus_siswa", tahan)
    hasil = []
    penghapus = threading.Thread(target=lambda: hasil.append(
        admin_service.hapus_siswa(admin, akun, db, perintah, sekarang=89)
    ))
    penghapus.start(); assert masuk.wait(5)

    def create_login():
        try:
            auth.tambah_akun(
                "login-terlambat", "murid-terlambat", "murid", akun,
                siswa_id=siswa_id,
            )
        except Exception as exc:  # pragma: no cover
            galat.append(exc)

    pembuat = threading.Thread(target=create_login); pembuat.start()
    # Lock auth harus masih held sampai DB commit; create belum boleh selesai.
    pembuat.join(0.1)
    assert pembuat.is_alive()
    lanjut.set(); penghapus.join(5); pembuat.join(5)
    assert hasil[0].hasil.status == "succeeded"
    assert not _ada_siswa(db, siswa_id)
    # Caller auth mentah dapat membuat orphan setelah commit; ini membuktikan
    # lock mencegah penyisipan di critical section, sementara integration wajib
    # memakai service one-to-one agar revalidate siswa setelah menunggu.
    assert auth.cari_akun("login-terlambat", akun) is not None


def test_login_generation_revision_legacy_mismatch_effect_zero(storage):
    admin, akun, db = storage
    siswa_id, login_id = _buat_siswa_login(storage, nama="Mismatch")
    sebelum = akun.read_bytes()
    for nomor, lid, rev in ((9, "akun_" + "f" * 32, 1), (10, login_id, 99)):
        hasil = admin_service.hapus_siswa(
            admin, akun, db, _perintah(siswa_id, lid, nomor, "Mismatch")
            if rev == 1 else c.PerintahHapusSiswa(
                "operasi_delete_%04d" % nomor, ACTOR, 2, c.AKSI_HAPUS_SISWA,
                siswa_id, "P3", lid, rev, TOKEN,
            ),
            sekarang=90 + nomor,
        )
        assert hasil.hasil.status in ("conflict", "uncertain")
        assert _ada_siswa(db, siswa_id)
    assert akun.read_bytes() == sebelum
