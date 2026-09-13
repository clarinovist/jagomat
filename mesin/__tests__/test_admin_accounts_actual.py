"""Adapter receipt terhadap auth JSON aktual dari kandidat writer A."""

from dataclasses import fields
import json
from pathlib import Path

import pytest

import admin_accounts as accounts
import admin_contracts as c
import auth


ACTOR_ID = "akun_" + "a" * 32
GURU_ID = "akun_" + "b" * 32
MURID_ID = "akun_" + "c" * 32
ADMIN_LAIN_ID = "akun_" + "d" * 32
TOKEN = "P" * 48


def _akun(pengguna, peran, id_akun, sandi, **tambahan):
    return {
        "pengguna": pengguna,
        "peran": peran,
        "id_akun": id_akun,
        **tambahan,
        **auth.buat_hash(sandi),
    }


@pytest.fixture()
def auth_path(tmp_path):
    path = tmp_path / "sandi-sintetis.json"
    data = {
        "versi_envelope": 7,
        "metadata_tetap": {"nilai": True},
        "operasi_admin": {},
        "akun": [
            _akun("admin-sintetis", "admin", ACTOR_ID, "admin-lama", revisi_auth=2),
            _akun("guru-sintetis", "guru", GURU_ID, "guru-lama", revisi_auth=0, field_tetap="ya"),
            _akun("murid-sintetis", "murid", MURID_ID, "murid-lama", siswa_id=17),
            _akun("admin-lain", "admin", ADMIN_LAIN_ID, "admin-lain", revisi_auth=1),
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _perintah(
    nomor=1,
    *,
    aksi=c.AKSI_RESET_SANDI,
    target_id=GURU_ID,
    target_revisi=0,
    target_peran="guru",
    actor_id=ACTOR_ID,
    actor_revisi=2,
    token=TOKEN,
):
    return c.PerintahAkun(
        "operasi_%04d" % nomor,
        actor_id,
        actor_revisi,
        aksi,
        target_id,
        target_revisi,
        target_peran,
        token,
    )


def _mentah(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_replay_reset_tidak_menghitung_hash_baru(auth_path, monkeypatch):
    perintah = _perintah(0)
    accounts.jalankan(
        auth_path, perintah, sandi_baru="guru-baru-pertama", sekarang=90
    )

    def hash_tidak_boleh_dipanggil(_sandi):
        raise AssertionError("replay tidak boleh menghitung hash baru")

    monkeypatch.setattr(auth, "buat_hash", hash_tidak_boleh_dipanggil)
    replay = accounts.jalankan(
        auth_path, perintah, sandi_baru="plaintext-replay", sekarang=91
    )
    assert replay.operasi_id == perintah.operasi_id


def test_reset_guru_actual_hash_id_revisi_receipt_dan_replay(auth_path):
    perintah = _perintah(1)
    receipt = accounts.jalankan(
        auth_path, perintah, sandi_baru="guru-baru-sintetis", sekarang=100
    )
    pertama = auth_path.read_bytes()
    replay = accounts.jalankan(
        auth_path, perintah, sandi_baru="plaintext-berbeda-tidak-dipakai", sekarang=101
    )

    assert replay == receipt
    assert auth_path.read_bytes() == pertama
    target = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == GURU_ID)
    assert target["revisi_auth"] == 1
    assert target["id_akun"] == GURU_ID
    assert target["field_tetap"] == "ya"
    assert auth.periksa("guru-sintetis", "guru-baru-sintetis", target)
    assert not auth.periksa("guru-sintetis", "guru-lama", target)
    raw = _mentah(auth_path)
    assert raw["versi_envelope"] == 7
    assert raw["metadata_tetap"] == {"nilai": True}
    assert list(raw["operasi_admin"]) == [perintah.operasi_id]
    receipt_raw = raw["operasi_admin"][perintah.operasi_id]
    assert set(receipt_raw) == {
        "versi", "operasi_id", "actor_id", "aksi", "target_id",
        "target_peran", "revisi_awal", "revisi_hasil", "hasil_kode",
        "dibuat", "sidik_perintah",
    }
    serialized = json.dumps(receipt_raw)
    for rahasia in (
        "guru-baru-sintetis", "guru-lama", target["garam"], target["kunci"],
        "guru-sintetis", TOKEN,
    ):
        assert rahasia not in serialized


def test_reset_murid_dan_revoke_actual_increment_revisi(auth_path):
    reset = _perintah(
        2, target_id=MURID_ID, target_peran="murid", aksi=c.AKSI_RESET_SANDI
    )
    accounts.jalankan(
        auth_path, reset, sandi_baru="murid-baru", sekarang=110
    )
    murid = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == MURID_ID)
    assert murid["revisi_auth"] == 1
    assert murid["siswa_id"] == 17
    assert auth.periksa("murid-sintetis", "murid-baru", murid)

    hash_sebelum = (murid["garam"], murid["kunci"], murid["iterasi"])
    revoke = _perintah(
        3,
        aksi=c.AKSI_CABUT_SESI,
        target_id=MURID_ID,
        target_revisi=1,
        target_peran="murid",
    )
    accounts.jalankan(auth_path, revoke, sekarang=111)
    murid = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == MURID_ID)
    assert murid["revisi_auth"] == 2
    assert (murid["garam"], murid["kunci"], murid["iterasi"]) == hash_sebelum


def test_hapus_login_guru_actual_receipt_tombstone_dan_replay(auth_path):
    perintah = _perintah(4, aksi=c.AKSI_HAPUS_LOGIN)
    receipt = accounts.jalankan(auth_path, perintah, sekarang=120)

    assert receipt.hasil_kode == "login_deleted"
    assert receipt.revisi_hasil == 1
    assert auth.cari_akun("guru-sintetis", auth_path) is None
    assert accounts.baca_receipt(auth_path, perintah) == receipt
    assert accounts.jalankan(auth_path, perintah, sekarang=121) == receipt
    assert len(auth.muat_akun(auth_path)) == 3


def test_legacy_missing_revisi_nol_bool_string_negatif_ditolak(auth_path):
    data = _mentah(auth_path)
    guru = next(item for item in data["akun"] if item["id_akun"] == GURU_ID)
    guru.pop("revisi_auth")
    auth_path.write_text(json.dumps(data), encoding="utf-8")
    receipt = accounts.jalankan(
        auth_path, _perintah(5), sandi_baru="guru-baru-legacy", sekarang=130
    )
    assert (receipt.revisi_awal, receipt.revisi_hasil) == (0, 1)

    for nomor, nilai in enumerate((True, "0", -1), start=6):
        path = auth_path.parent / ("invalid-%d.json" % nomor)
        rusak = _mentah(auth_path)
        target = next(item for item in rusak["akun"] if item["id_akun"] == MURID_ID)
        target["revisi_auth"] = nilai
        path.write_text(json.dumps(rusak), encoding="utf-8")
        sebelum = path.read_bytes()
        with pytest.raises(accounts.DomainAkunTidakSah):
            accounts.jalankan(
                path,
                _perintah(
                    nomor,
                    aksi=c.AKSI_CABUT_SESI,
                    target_id=MURID_ID,
                    target_revisi=0,
                    target_peran="murid",
                ),
                sekarang=131,
            )
        assert path.read_bytes() == sebelum


@pytest.mark.parametrize(
    "ubah,galat",
    [
        ({"actor_id": "akun_" + "e" * 32}, "actor tidak tersedia"),
        ({"actor_revisi": 99}, "revisi actor berubah"),
        ({"actor_id": GURU_ID, "actor_revisi": 0, "target_id": MURID_ID, "target_peran": "murid"}, "actor bukan admin"),
        ({"target_id": "akun_" + "f" * 32}, "target tidak tersedia"),
        ({"target_revisi": 99}, "revisi target berubah"),
        ({"target_peran": "murid"}, "peran target berubah"),
        ({"target_id": ADMIN_LAIN_ID, "target_revisi": 1}, "akun admin tidak boleh"),
    ],
)
def test_actor_target_stale_admin_wrongrole_effect_zero(auth_path, ubah, galat):
    dasar = {
        "nomor": 20,
        "aksi": c.AKSI_CABUT_SESI,
        "target_id": GURU_ID,
        "target_revisi": 0,
        "target_peran": "guru",
        "actor_id": ACTOR_ID,
        "actor_revisi": 2,
    }
    dasar.update(ubah)
    nomor = dasar.pop("nomor")
    perintah = _perintah(nomor, **dasar)
    sebelum = auth_path.read_bytes()

    with pytest.raises(accounts.KonflikAkun, match=galat):
        accounts.jalankan(auth_path, perintah, sekarang=140)

    assert auth_path.read_bytes() == sebelum


def test_null_malformed_duplicate_id_receipt_corrupt_fail_closed(tmp_path, auth_path):
    kasus = {
        "null.json": "null",
        "malformed.json": '{"akun":[rusak]}',
    }
    for nama, isi in kasus.items():
        path = tmp_path / nama
        path.write_text(isi, encoding="utf-8")
        sebelum = path.read_bytes()
        with pytest.raises(accounts.DomainAkunTidakSah):
            accounts.jalankan(
                path, _perintah(30), sandi_baru="sandi-baru-sintetis", sekarang=150
            )
        assert path.read_bytes() == sebelum

    data = _mentah(auth_path)
    data["akun"][1]["id_akun"] = ACTOR_ID
    duplikat = tmp_path / "duplikat.json"
    duplikat.write_text(json.dumps(data), encoding="utf-8")
    sebelum = duplikat.read_bytes()
    with pytest.raises(accounts.DomainAkunTidakSah):
        accounts.jalankan(
            duplikat, _perintah(31), sandi_baru="sandi-baru-sintetis", sekarang=151
        )
    assert duplikat.read_bytes() == sebelum

    data = _mentah(auth_path)
    data["operasi_admin"] = {"operasi_rusak": {"payload": "bebas"}}
    rusak_receipt = tmp_path / "receipt-rusak.json"
    rusak_receipt.write_text(json.dumps(data), encoding="utf-8")
    sebelum = rusak_receipt.read_bytes()
    with pytest.raises(accounts.DomainAkunTidakSah):
        accounts.jalankan(
            rusak_receipt, _perintah(32), sandi_baru="sandi-baru-sintetis", sekarang=152
        )
    assert rusak_receipt.read_bytes() == sebelum


def test_race_target_berubah_saat_hash_dihitung_ditolak(auth_path, monkeypatch):
    perintah = _perintah(38)
    asli = auth.buat_hash

    def hash_dan_ubah_target(sandi):
        data = _mentah(auth_path)
        target = next(item for item in data["akun"] if item["id_akun"] == GURU_ID)
        target["revisi_auth"] = 1
        auth_path.write_text(json.dumps(data), encoding="utf-8")
        return asli(sandi)

    monkeypatch.setattr(auth, "buat_hash", hash_dan_ubah_target)
    with pytest.raises(accounts.KonflikAkun, match="revisi target berubah"):
        accounts.jalankan(
            auth_path, perintah, sandi_baru="guru-baru-race", sekarang=158
        )
    assert accounts.baca_receipt(auth_path, perintah) is None
    target = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == GURU_ID)
    assert target["revisi_auth"] == 1
    assert auth.periksa("guru-sintetis", "guru-lama", target)


def test_writer_existing_mempertahankan_envelope_operasi_admin(auth_path):
    perintah = _perintah(39, aksi=c.AKSI_CABUT_SESI)
    receipt = accounts.jalankan(auth_path, perintah, sekarang=159)

    auth.tambah_akun(
        "guru-tambahan", "password-tambahan", "guru", path=auth_path
    )
    auth.setel_sandi_murid("murid-sintetis", "murid-baru-lagi", auth_path)
    auth.hapus_akun_guru("guru-tambahan", auth_path)

    assert accounts.baca_receipt(auth_path, perintah) == receipt
    raw = _mentah(auth_path)
    assert raw["metadata_tetap"] == {"nilai": True}
    assert list(raw["operasi_admin"]) == [perintah.operasi_id]


def test_failpoint_sebelum_dan_setelah_replace_actual(auth_path):
    sebelum = auth_path.read_bytes()
    perintah_awal = _perintah(40, aksi=c.AKSI_CABUT_SESI)
    with pytest.raises(accounts.BelumCommit):
        accounts.jalankan(
            auth_path, perintah_awal, sekarang=160, failpoint="sebelum_replace"
        )
    assert auth_path.read_bytes() == sebelum
    assert accounts.baca_receipt(auth_path, perintah_awal) is None

    perintah_commit = _perintah(41, aksi=c.AKSI_CABUT_SESI)
    with pytest.raises(accounts.CrashSetelahReplace):
        accounts.jalankan(
            auth_path, perintah_commit, sekarang=161, failpoint="setelah_replace"
        )
    receipt = accounts.baca_receipt(auth_path, perintah_commit)
    assert receipt is not None
    target = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == GURU_ID)
    assert target["revisi_auth"] == 1
    assert accounts.jalankan(auth_path, perintah_commit, sekarang=162) == receipt
    target2 = next(item for item in auth.muat_akun(auth_path) if item["id_akun"] == GURU_ID)
    assert target2["revisi_auth"] == 1


def test_replay_receipt_tetap_revalidasi_actor_admin(auth_path):
    perintah = _perintah(49)
    accounts.jalankan(
        auth_path, perintah, sandi_baru="guru-baru-actor-check", sekarang=180
    )
    data = _mentah(auth_path)
    actor = next(item for item in data["akun"] if item["id_akun"] == ACTOR_ID)
    actor["peran"] = "guru"
    auth_path.write_text(json.dumps(data), encoding="utf-8")
    sebelum = auth_path.read_bytes()

    with pytest.raises(accounts.KonflikAkun, match="actor bukan admin"):
        accounts.jalankan(
            auth_path, perintah, sandi_baru="tidak-digunakan-lagi", sekarang=181
        )
    assert auth_path.read_bytes() == sebelum


def test_perintah_repr_sidik_tidak_muat_sandi_token_atau_nama():
    perintah = _perintah(50)
    assert {item.name for item in fields(c.ReceiptAkun)} == {
        "versi", "operasi_id", "actor_id", "aksi", "target_id",
        "target_peran", "revisi_awal", "revisi_hasil", "hasil_kode",
        "dibuat", "sidik_perintah",
    }
    teks = repr(perintah)
    assert TOKEN not in teks
    assert "guru-sintetis" not in teks
    sidik = c.sidik_perintah(perintah)
    assert len(sidik) == 64
    assert TOKEN not in sidik
    assert "sandi" not in sidik
