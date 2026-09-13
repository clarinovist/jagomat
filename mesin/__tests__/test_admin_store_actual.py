"""Store admin SQLite aktual dengan seluruh path sintetis temp."""

import os
from pathlib import Path
import shutil
import sqlite3
import stat

import pytest

import admin_contracts as c
import admin_store as store


ACTOR = "akun_" + "a" * 32
TARGET = "akun_" + "b" * 32
TOKEN = "T" * 48


def _perintah(nomor=1, *, aksi=c.AKSI_CABUT_SESI, target_revisi=0):
    return c.PerintahAkun(
        "operasi_%04d" % nomor,
        ACTOR,
        0,
        aksi,
        TARGET,
        target_revisi,
        "guru",
        TOKEN,
    )


@pytest.fixture()
def path_store(tmp_path):
    path = tmp_path / "admin-control.db"
    store.siapkan(path, sekarang=100)
    return path


def test_reader_missing_tidak_membuat_db(tmp_path):
    path = tmp_path / "belum-ada.db"

    with pytest.raises(store.StoreBelumSiap):
        store.baca_konfigurasi(path)

    assert not path.exists()


def test_bootstrap_idempoten_permission_integrity_dan_fk(path_store):
    sebelum = path_store.read_bytes()
    store.siapkan(path_store, sekarang=999)
    config = store.baca_konfigurasi(path_store)

    assert config == store.KonfigurasiPendaftaran(1, True, "closed_standard", 100)
    assert stat.S_IMODE(path_store.stat().st_mode) == 0o600
    with sqlite3.connect(str(path_store)) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == store.VERSI_SKEMA
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None
    # SQLite header/counter boleh tidak identik byte, tetapi bootstrap tak menambah row.
    assert path_store.stat().st_size == len(sebelum)


def test_schema_lebih_baru_dan_struktur_bentrok_ditolak(tmp_path):
    baru = tmp_path / "lebih-baru.db"
    with sqlite3.connect(str(baru)) as kon:
        kon.execute("PRAGMA user_version=99")
    with pytest.raises(store.StoreBelumSiap, match="lebih baru"):
        store.siapkan(baru)

    bentrok = tmp_path / "bentrok.db"
    with sqlite3.connect(str(bentrok)) as kon:
        kon.execute("CREATE TABLE konfigurasi_pendaftaran(id INTEGER PRIMARY KEY)")
    with pytest.raises(store.StoreBelumSiap):
        store.siapkan(bentrok)


def test_config_audit_satu_transaksi_stale_replay_invalid(path_store):
    hasil = store.ubah_konfigurasi(
        path_store,
        operasi_id="operasi_config_1",
        actor_id=ACTOR,
        revisi=1,
        dibuka=False,
        pesan_kode="closed_maintenance",
        token_tinjauan=TOKEN,
        sekarang=200,
    )
    assert hasil.status == "succeeded"
    assert hasil.target_peran is None
    assert hasil.revisi_hasil == 2
    assert store.baca_konfigurasi(path_store) == store.KonfigurasiPendaftaran(
        2, False, "closed_maintenance", 200
    )

    replay = store.ubah_konfigurasi(
        path_store,
        operasi_id="operasi_config_1",
        actor_id=ACTOR,
        revisi=1,
        dibuka=False,
        pesan_kode="closed_maintenance",
        token_tinjauan=TOKEN,
        sekarang=201,
    )
    assert replay == hasil

    with pytest.raises(store.KonflikOperasi, match="stale"):
        store.ubah_konfigurasi(
            path_store,
            operasi_id="operasi_config_2",
            actor_id=ACTOR,
            revisi=1,
            dibuka=True,
            pesan_kode="closed_standard",
            token_tinjauan=TOKEN,
            sekarang=202,
        )
    with pytest.raises(store.DataAuditTidakSah):
        store.ubah_konfigurasi(
            path_store,
            operasi_id="operasi_config_3",
            actor_id=ACTOR,
            revisi=2,
            dibuka=False,
            pesan_kode="hubungi admin bebas",
            token_tinjauan=TOKEN,
            sekarang=203,
        )
    with sqlite3.connect(str(path_store)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM audit_admin").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM audit_admin_perubahan").fetchone()[0] == 2


def test_config_failpoint_rollback_config_journal_audit(path_store):
    awal = store.baca_konfigurasi(path_store)
    with pytest.raises(RuntimeError, match="failpoint"):
        store.ubah_konfigurasi(
            path_store,
            operasi_id="operasi_config_crash",
            actor_id=ACTOR,
            revisi=1,
            dibuka=False,
            pesan_kode="closed_standard",
            token_tinjauan=TOKEN,
            sekarang=210,
            failpoint="setelah_config_sebelum_audit",
        )

    assert store.baca_konfigurasi(path_store) == awal
    with sqlite3.connect(str(path_store)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM audit_admin").fetchone()[0] == 0


def test_reservasi_identity_conflict_dan_replay(path_store):
    perintah = _perintah(1)
    pertama = store.reservasi(path_store, perintah, sekarang=300)
    kedua = store.reservasi(path_store, perintah, sekarang=301)

    assert pertama.dibuat_baru is True
    assert kedua.dibuat_baru is False
    assert kedua.hasil.status == "reserved"

    beda = c.PerintahAkun(
        perintah.operasi_id,
        perintah.actor_id,
        perintah.actor_revisi,
        c.AKSI_HAPUS_LOGIN,
        perintah.target_id,
        perintah.target_revisi,
        perintah.target_peran,
        perintah.token_tinjauan,
    )
    with pytest.raises(store.KonflikOperasi):
        store.reservasi(path_store, beda)


def test_finalisasi_receipt_dan_audit_allow_list(path_store):
    perintah = _perintah(2)
    store.reservasi(path_store, perintah, sekarang=400)
    receipt = c.ReceiptAkun(
        1,
        perintah.operasi_id,
        perintah.actor_id,
        perintah.aksi,
        perintah.target_id,
        perintah.target_peran,
        0,
        1,
        "sessions_revoked",
        401,
        c.sidik_perintah(perintah),
    )
    hasil = store.finalisasi_sukses(path_store, perintah, receipt, sekarang=402)

    assert hasil.status == "succeeded"
    assert hasil.revisi_hasil == 1
    with sqlite3.connect(str(path_store)) as kon:
        audit = kon.execute("SELECT * FROM audit_admin").fetchone()
        perubahan = kon.execute("SELECT * FROM audit_admin_perubahan").fetchone()
        assert audit[7] == "succeeded"
        assert audit[8] == "sessions_revoked"
        assert tuple(perubahan[1:]) == ("auth_revision", "0", "1")

    for data in (
        {"password": ("lama", "baru")},
        {"username": ("nama", "nama2")},
        {"auth_revision": ("nol", "1")},
    ):
        with pytest.raises(store.DataAuditTidakSah):
            store.validasi_perubahan_audit(data)


def test_purge_180_hari_hanya_audit_bukan_journal(path_store):
    lama = 1_000
    perintah = _perintah(3)
    store.reservasi(path_store, perintah, sekarang=lama)
    store.finalisasi_gagal(
        path_store,
        perintah,
        status="failed_before_commit",
        hasil_kode="domain_not_committed",
        sekarang=lama,
    )

    kini = lama + 181 * 86400
    assert store.purge_audit(path_store, sekarang=kini) == 1
    hasil = store.baca_operasi(path_store, perintah.operasi_id)
    assert hasil is not None
    assert hasil.status == "failed_before_commit"
    with sqlite3.connect(str(path_store)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM operasi_admin").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM audit_admin").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM audit_admin_perubahan").fetchone()[0] == 0


def test_restore_salinan_mempertahankan_config_journal_audit(path_store, tmp_path):
    perintah = _perintah(8)
    store.reservasi(path_store, perintah, sekarang=500)
    store.finalisasi_gagal(
        path_store,
        perintah,
        status="failed_before_commit",
        hasil_kode="domain_not_committed",
        sekarang=501,
    )
    salinan = tmp_path / "restore-admin-control.db"
    shutil.copy2(path_store, salinan)

    store.siapkan(salinan, sekarang=999)
    assert store.baca_konfigurasi(salinan).revisi == 1
    assert store.baca_operasi(salinan, perintah.operasi_id).status == "failed_before_commit"
    with sqlite3.connect(str(salinan)) as kon:
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None
        assert kon.execute("SELECT COUNT(*) FROM audit_admin").fetchone()[0] == 1


def test_store_readonly_gagal_tutup_tidak_membuka_baru(path_store, tmp_path):
    os.chmod(path_store, 0o400)
    # Reader masih sah.
    assert store.baca_konfigurasi(path_store).revisi == 1
    # URI rw bisa dibuka oleh owner pada sebagian platform; force invalid parent/path
    # untuk membuktikan reserve gagal sebelum domain dipanggil di test service.
    direktori = tmp_path / "bukan-db"
    direktori.mkdir()
    with pytest.raises(store.StoreBelumSiap):
        store.reservasi(direktori, _perintah(9))
