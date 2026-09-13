"""Koordinasi SQLite admin + receipt auth JSON aktual, termasuk concurrency."""

import json
import multiprocessing
from pathlib import Path
import threading
import time

import pytest

import admin_accounts
import admin_contracts as c
import admin_service as service
import admin_store
import auth


ACTOR_ID = "akun_" + "a" * 32
TARGET_ID = "akun_" + "b" * 32
ADMIN_LAIN_ID = "akun_" + "c" * 32
TOKEN = "R" * 48
PASSWORD_LAMA = "password-lama-sintetis"
PASSWORD_BARU = "password-baru-sintetis"


def _akun(pengguna, peran, id_akun, sandi, revisi_auth):
    return {
        "pengguna": pengguna,
        "peran": peran,
        "id_akun": id_akun,
        "revisi_auth": revisi_auth,
        **auth.buat_hash(sandi),
    }


def _buat_auth(path):
    path.write_text(json.dumps({
        "metadata": {"tetap": True},
        "operasi_admin": {},
        "akun": [
            _akun("admin-sintetis", "admin", ACTOR_ID, "admin-lama", 3),
            _akun("guru-sintetis", "guru", TARGET_ID, PASSWORD_LAMA, 0),
            _akun("admin-lain", "admin", ADMIN_LAIN_ID, "admin-lain", 1),
        ],
    }), encoding="utf-8")


def _perintah(nomor=1, *, token=TOKEN, target_id=TARGET_ID, target_revisi=0, target_peran="guru"):
    return c.PerintahAkun(
        "operasi_%04d" % nomor,
        ACTOR_ID,
        3,
        c.AKSI_RESET_SANDI,
        target_id,
        target_revisi,
        target_peran,
        token,
    )


@pytest.fixture()
def storage(tmp_path):
    admin = tmp_path / "admin-control.db"
    akun = tmp_path / "sandi-sintetis.json"
    admin_store.siapkan(admin, sekarang=1)
    _buat_auth(akun)
    return admin, akun


def _jumlah_mutasi(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    target = next(item for item in data["akun"] if item["id_akun"] == TARGET_ID)
    return target["revisi_auth"], len(data["operasi_admin"]), target


def _proses_service(path_admin, path_auth, mulai, hasil):
    """Target spawn: jangan kirim plaintext hasil melalui queue."""
    import admin_contracts as kontrak
    import admin_service as layanan

    perintah = kontrak.PerintahAkun(
        "operasi_proses_0001",
        ACTOR_ID,
        3,
        kontrak.AKSI_RESET_SANDI,
        TARGET_ID,
        0,
        "guru",
        TOKEN,
    )
    mulai.wait(10)
    try:
        nilai = layanan.jalankan(
            Path(path_admin),
            Path(path_auth),
            perintah,
            sandi_baru=PASSWORD_BARU,
            sekarang=500,
        )
        hasil.put((nilai.hasil.status, nilai.baru_dieksekusi, nilai.credential_sekali is not None))
    except Exception as galat:  # pragma: no cover - dilaporkan parent
        hasil.put(("ERROR", galat.__class__.__name__, str(galat)))


def test_service_reset_fresh_replay_metadata_only(storage):
    admin, akun = storage
    perintah = _perintah(1)

    fresh = service.jalankan(
        admin,
        akun,
        perintah,
        sandi_baru=PASSWORD_BARU,
        sekarang=100,
    )
    replay = service.jalankan(
        admin,
        akun,
        perintah,
        sandi_baru="password-berbeda-tidak-dipakai",
        sekarang=101,
    )

    assert fresh.hasil.status == "succeeded"
    assert fresh.baru_dieksekusi is True
    assert fresh.credential_sekali == PASSWORD_BARU
    assert replay.hasil == fresh.hasil
    assert replay.baru_dieksekusi is False
    assert replay.credential_sekali is None
    revisi, receipt_count, target = _jumlah_mutasi(akun)
    assert (revisi, receipt_count) == (1, 1)
    assert auth.periksa("guru-sintetis", PASSWORD_BARU, target)
    assert not auth.periksa("guru-sintetis", PASSWORD_LAMA, target)
    assert admin_store.baca_operasi(admin, perintah.operasi_id).status == "succeeded"


def test_input_invalid_ditolak_sebelum_journal(storage):
    admin, akun = storage
    perintah = _perintah(17)
    sebelum = akun.read_bytes()

    with pytest.raises(c.KontrakTidakSah):
        service.jalankan(
            admin, akun, perintah, sandi_baru="pendek", sekarang=110
        )

    assert admin_store.baca_operasi(admin, perintah.operasi_id) is None
    assert akun.read_bytes() == sebelum


def test_store_reserve_gagal_auth_byte_identik(tmp_path):
    akun = tmp_path / "sandi.json"
    _buat_auth(akun)
    sebelum = akun.read_bytes()
    path_admin_tidak_ada = tmp_path / "tidak-ada" / "admin-control.db"

    with pytest.raises(admin_store.StoreBelumSiap):
        service.jalankan(
            path_admin_tidak_ada,
            akun,
            _perintah(2),
            sandi_baru=PASSWORD_BARU,
        )

    assert akun.read_bytes() == sebelum
    assert not path_admin_tidak_ada.exists()


def test_replay_reserved_actor_stale_menjadi_conflict_bukan_failed(storage):
    admin, akun = storage
    perintah = _perintah(19)
    admin_store.reservasi(admin, perintah, sekarang=115)
    data = json.loads(akun.read_text(encoding="utf-8"))
    actor = next(item for item in data["akun"] if item["id_akun"] == ACTOR_ID)
    actor["revisi_auth"] = 4
    akun.write_text(json.dumps(data), encoding="utf-8")
    sebelum = akun.read_bytes()

    hasil = service.rekonsiliasi(admin, akun, perintah, sekarang=116)
    assert hasil.hasil.status == "conflict"
    assert hasil.hasil.hasil_kode == "target_changed"
    assert akun.read_bytes() == sebelum


def test_actor_invalid_ditolak_sebelum_journal(storage):
    admin, akun = storage
    sebelum = akun.read_bytes()
    # Actor adalah akun guru; target berupa ID asing valid agar command typed
    # lolos, lalu principal mutakhir menolak sebelum admission SQLite.
    perintah = c.PerintahAkun(
        "operasi_actor_invalid",
        TARGET_ID,
        0,
        c.AKSI_RESET_SANDI,
        "akun_" + "d" * 32,
        0,
        "guru",
        TOKEN,
    )

    with pytest.raises(
        service.OperasiTidakDapatDilanjutkan, match="tidak dapat diverifikasi"
    ):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=117
        )
    assert admin_store.baca_operasi(admin, perintah.operasi_id) is None
    assert akun.read_bytes() == sebelum


def test_target_stale_conflict_diaudit_dan_effect_zero(storage):
    admin, akun = storage
    sebelum = akun.read_bytes()
    hasil = service.jalankan(
        admin,
        akun,
        _perintah(3, target_revisi=99),
        sandi_baru=PASSWORD_BARU,
        sekarang=120,
    )

    assert hasil.hasil.status == "conflict"
    assert hasil.hasil.hasil_kode == "target_changed"
    assert hasil.credential_sekali is None
    assert akun.read_bytes() == sebelum


def test_target_admin_ditolak_effect_zero(storage):
    admin, akun = storage
    sebelum = akun.read_bytes()
    hasil = service.jalankan(
        admin,
        akun,
        _perintah(4, target_id=ADMIN_LAIN_ID, target_revisi=1),
        sandi_baru=PASSWORD_BARU,
        sekarang=121,
    )

    assert hasil.hasil.status == "conflict"
    assert akun.read_bytes() == sebelum


def test_failpoint_sebelum_replace_terminal_tidak_auto_retry(storage):
    admin, akun = storage
    perintah = _perintah(5)
    sebelum = akun.read_bytes()

    hasil = service.jalankan(
        admin,
        akun,
        perintah,
        sandi_baru=PASSWORD_BARU,
        sekarang=130,
        failpoint="sebelum_replace",
    )
    assert hasil.hasil.status == "failed_before_commit"
    assert akun.read_bytes() == sebelum
    with pytest.raises(service.OperasiTidakDapatDilanjutkan):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=131
        )
    assert akun.read_bytes() == sebelum


def test_crash_setelah_replace_sebelum_finalize_reconcile_receipt(storage):
    admin, akun = storage
    perintah = _perintah(6)

    with pytest.raises(service.CrashSebelumFinalisasi):
        service.jalankan(
            admin,
            akun,
            perintah,
            sandi_baru=PASSWORD_BARU,
            sekarang=140,
            failpoint="setelah_replace",
        )

    assert admin_store.baca_operasi(admin, perintah.operasi_id).status == "reserved"
    revisi, receipt_count, _target = _jumlah_mutasi(akun)
    assert (revisi, receipt_count) == (1, 1)
    pulih = service.rekonsiliasi(admin, akun, perintah, sekarang=141)
    assert pulih.hasil.status == "succeeded"
    assert pulih.baru_dieksekusi is False
    assert pulih.credential_sekali is None
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_crash_sebelum_finalize_dan_response_lost_tidak_keluarkan_sandi(storage):
    admin, akun = storage
    pertama = _perintah(7)
    with pytest.raises(service.CrashSebelumFinalisasi):
        service.jalankan(
            admin, akun, pertama, sandi_baru=PASSWORD_BARU,
            sekarang=150, failpoint="sebelum_finalize",
        )
    pulih = service.rekonsiliasi(admin, akun, pertama, sekarang=151)
    assert pulih.hasil.status == "succeeded"
    assert pulih.credential_sekali is None

    # Target kini revisi 1; operasi reset baru dapat commit lalu respons hilang.
    kedua = _perintah(8, target_revisi=1, token="S" * 48)
    with pytest.raises(service.CrashSetelahFinalisasi):
        service.jalankan(
            admin, akun, kedua, sandi_baru="password-kedua-sintetis",
            sekarang=152, failpoint="setelah_finalize",
        )
    replay = service.jalankan(
        admin, akun, kedua, sandi_baru="jangan-dipakai-lagi", sekarang=153
    )
    assert replay.hasil.status == "succeeded"
    assert replay.baru_dieksekusi is False
    assert replay.credential_sekali is None
    assert _jumlah_mutasi(akun)[:2] == (2, 2)


def test_error_setelah_replace_dari_writer_ditandai_uncertain_meski_receipt_terbaca(storage, monkeypatch):
    admin, akun = storage
    perintah = _perintah(21)
    asli = auth._tulis_akun_atomik

    def tulis_lalu_gagal(data, path):
        asli(data, path)
        raise OSError("fsync direktori gagal sintetis")

    monkeypatch.setattr(auth, "_tulis_akun_atomik", tulis_lalu_gagal)
    with pytest.raises(service.OperasiTidakDapatDilanjutkan, match="tak pasti"):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=155
        )
    hasil = admin_store.baca_operasi(admin, perintah.operasi_id)
    assert hasil.status == "uncertain"
    assert hasil.credential_status == "unconfirmed"
    assert _jumlah_mutasi(akun)[:2] == (1, 1)

    monkeypatch.setattr(auth, "_tulis_akun_atomik", asli)
    pulih = service.rekonsiliasi(admin, akun, perintah, sekarang=156)
    assert pulih.hasil.status == "succeeded"
    assert pulih.credential_sekali is None
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_reserved_tanpa_receipt_reconcile_failed_dan_tidak_reexec(storage):
    admin, akun = storage
    perintah = _perintah(9)
    admin_store.reservasi(admin, perintah, sekarang=160)
    sebelum = akun.read_bytes()

    pulih = service.rekonsiliasi(admin, akun, perintah, sekarang=161)
    assert pulih.hasil.status == "failed_before_commit"
    assert akun.read_bytes() == sebelum
    with pytest.raises(service.OperasiTidakDapatDilanjutkan):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=162
        )
    assert akun.read_bytes() == sebelum


def test_auth_corrupt_membuat_uncertain_dan_tidak_auto_retry(storage):
    admin, akun = storage
    perintah = _perintah(10)
    akun.write_text("null", encoding="utf-8")
    sebelum = akun.read_bytes()

    with pytest.raises(service.OperasiTidakDapatDilanjutkan):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=170
        )
    hasil = admin_store.baca_operasi(admin, perintah.operasi_id)
    assert hasil.status == "uncertain"
    assert hasil.hasil_kode == "domain_uncertain"
    assert hasil.credential_status == "unconfirmed"
    assert akun.read_bytes() == sebelum


def test_uncertain_bisa_reconcile_setelah_domain_receipt_pulih(storage):
    admin, akun = storage
    perintah = _perintah(14)
    with pytest.raises(service.CrashSebelumFinalisasi):
        service.jalankan(
            admin,
            akun,
            perintah,
            sandi_baru=PASSWORD_BARU,
            sekarang=171,
            failpoint="setelah_replace",
        )
    committed = akun.read_bytes()
    akun.write_text("null", encoding="utf-8")
    pertama = service.rekonsiliasi(admin, akun, perintah, sekarang=172)
    assert pertama.hasil.status == "uncertain"

    akun.write_bytes(committed)
    pulih = service.rekonsiliasi(admin, akun, perintah, sekarang=173)
    assert pulih.hasil.status == "succeeded"
    assert pulih.baru_dieksekusi is False
    assert pulih.credential_sekali is None
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_uncertain_tanpa_receipt_setelah_domain_pulih_jadi_gagal_bukan_reexec(storage):
    admin, akun = storage
    perintah = _perintah(15)
    semula = akun.read_bytes()
    admin_store.reservasi(admin, perintah, sekarang=174)
    akun.write_text("null", encoding="utf-8")
    assert service.rekonsiliasi(
        admin, akun, perintah, sekarang=175
    ).hasil.status == "uncertain"

    akun.write_bytes(semula)
    pulih = service.rekonsiliasi(admin, akun, perintah, sekarang=176)
    assert pulih.hasil.status == "failed_before_commit"
    assert akun.read_bytes() == semula


def test_same_operation_thread_hanya_satu_mutasi_dan_satu_credential(storage):
    admin, akun = storage
    perintah = _perintah(11)
    mulai = threading.Barrier(3, timeout=5)
    hasil = []
    galat = []

    def pekerja():
        try:
            mulai.wait()
            nilai = service.jalankan(
                admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=180
            )
            hasil.append((nilai.baru_dieksekusi, nilai.credential_sekali is not None))
        except Exception as exc:  # pragma: no cover - assertion melaporkan
            galat.append(exc)

    thread = [threading.Thread(target=pekerja) for _ in range(2)]
    for item in thread:
        item.start()
    mulai.wait()
    for item in thread:
        item.join(timeout=10)
    assert not any(item.is_alive() for item in thread)
    assert galat == []
    assert sorted(hasil) == [(False, False), (True, True)]
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_same_operation_lintas_proses_hanya_satu_mutasi(storage):
    admin, akun = storage
    konteks = multiprocessing.get_context("spawn")
    mulai = konteks.Event()
    hasil = konteks.Queue()
    proses = [
        konteks.Process(
            target=_proses_service,
            args=(str(admin), str(akun), mulai, hasil),
        )
        for _ in range(2)
    ]
    for item in proses:
        item.start()
    mulai.set()
    for item in proses:
        item.join(20)
    assert [item.exitcode for item in proses] == [0, 0]
    nilai = sorted(hasil.get(timeout=3) for _ in proses)
    assert nilai == [
        ("succeeded", False, False),
        ("succeeded", True, True),
    ]
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_replay_sukses_actor_stale_ditolak_tanpa_mutasi(storage):
    admin, akun = storage
    perintah = _perintah(16)
    service.jalankan(
        admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=590
    )
    data = json.loads(akun.read_text(encoding="utf-8"))
    actor = next(item for item in data["akun"] if item["id_akun"] == ACTOR_ID)
    actor["revisi_auth"] = 4
    akun.write_text(json.dumps(data), encoding="utf-8")
    sebelum = akun.read_bytes()

    with pytest.raises(
        service.OperasiTidakDapatDilanjutkan, match="tidak dapat diverifikasi"
    ):
        service.jalankan(
            admin, akun, perintah, sandi_baru="jangan-dipakai", sekarang=591
        )
    assert akun.read_bytes() == sebelum
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_journal_sukses_tanpa_receipt_ditolak_bukan_replay_palsu(storage):
    admin, akun = storage
    perintah = _perintah(12)
    service.jalankan(
        admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=600
    )
    data = json.loads(akun.read_text(encoding="utf-8"))
    data["operasi_admin"].pop(perintah.operasi_id)
    akun.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(
        service.OperasiTidakDapatDilanjutkan, match="tanpa receipt"
    ):
        service.jalankan(
            admin, akun, perintah, sandi_baru="jangan-dipakai", sekarang=601
        )
    assert _jumlah_mutasi(akun)[0] == 1


def test_journal_sukses_receipt_corrupt_ditolak(storage):
    admin, akun = storage
    perintah = _perintah(18)
    service.jalankan(
        admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=602
    )
    data = json.loads(akun.read_text(encoding="utf-8"))
    data["operasi_admin"][perintah.operasi_id]["hasil_kode"] = "payload_bebas"
    akun.write_text(json.dumps(data), encoding="utf-8")
    sebelum = akun.read_bytes()

    with pytest.raises(
        service.OperasiTidakDapatDilanjutkan, match="tidak dapat diverifikasi"
    ):
        service.jalankan(
            admin, akun, perintah, sandi_baru="jangan-dipakai", sekarang=603
        )
    assert akun.read_bytes() == sebelum
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_replay_sukses_tetap_valid_setelah_audit_dipurge(storage):
    admin, akun = storage
    perintah = _perintah(20)
    service.jalankan(
        admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=1_000
    )
    assert admin_store.purge_audit(
        admin, sekarang=1_000 + 181 * 86400
    ) == 1

    replay = service.jalankan(
        admin, akun, perintah, sandi_baru="jangan-dipakai", sekarang=1_100
    )
    assert replay.hasil.status == "succeeded"
    assert replay.baru_dieksekusi is False
    assert replay.credential_sekali is None
    assert _jumlah_mutasi(akun)[:2] == (1, 1)


def test_operation_lock_sidecar_symlink_ditolak_tanpa_reservasi(storage, tmp_path):
    admin, akun = storage
    perintah = _perintah(22)
    tujuan = tmp_path / "bukan-lock.txt"
    tujuan.write_text("tetap", encoding="utf-8")
    service._lock_path(admin, perintah.operasi_id).symlink_to(tujuan)
    sebelum = akun.read_bytes()

    with pytest.raises(service.PenyimpananOperasiTidakSah):
        service.jalankan(
            admin, akun, perintah, sandi_baru=PASSWORD_BARU, sekarang=700
        )
    assert admin_store.baca_operasi(admin, perintah.operasi_id) is None
    assert akun.read_bytes() == sebelum
    assert tujuan.read_text(encoding="utf-8") == "tetap"


def test_operation_lock_private_stable_dan_tidak_bocor_id(storage):
    admin, _akun_path = storage
    perintah = _perintah(13)
    with service.kunci_operasi(admin, perintah.operasi_id):
        lock = service._lock_path(admin, perintah.operasi_id)
        assert lock.exists()
        assert perintah.operasi_id not in lock.name
        assert (lock.stat().st_mode & 0o777) == 0o600
        # Reentrant thread sama tidak deadlock.
        with service.kunci_operasi(admin, perintah.operasi_id):
            assert lock == service._lock_path(admin, perintah.operasi_id)
