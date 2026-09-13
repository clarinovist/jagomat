"""Integritas writer JSON akun/sesi lintas thread dan proses."""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import json_storage  # noqa: E402
import sessions  # noqa: E402

_ID_SESI_UJI = "akun_" + "e" * 32
_REVISI_SESI_UJI = 1


def _buat_sesi(pengguna, peran, *, path, sekarang=None):
    return sessions.buat(
        pengguna, peran, path=path, sekarang=sekarang,
        id_akun=_ID_SESI_UJI, revisi_auth=_REVISI_SESI_UJI,
    )


def _perlambat_writer(modul, nama, monkeypatch, jeda=0.02):
    """Perlebar kontensi setelah read tanpa barrier di dalam critical section."""
    asli = getattr(modul, nama)

    def lambat(*args, **kwargs):
        time.sleep(jeda)
        return asli(*args, **kwargs)

    monkeypatch.setattr(modul, nama, lambat)


def _jalankan_bersamaan(*fungsi):
    mulai = threading.Barrier(len(fungsi) + 1, timeout=5)
    galat = []

    def bungkus(fn):
        try:
            mulai.wait()
            fn()
        except Exception as exc:  # pragma: no cover - dilaporkan assertion
            galat.append(exc)

    ulir = [threading.Thread(target=bungkus, args=(fn,)) for fn in fungsi]
    for item in ulir:
        item.start()
    mulai.wait()
    for item in ulir:
        item.join(timeout=10)
    assert not any(item.is_alive() for item in ulir), "writer buntu"
    assert galat == []


def _proses_tambah_akun(path_teks, awalan, jumlah, mulai):
    """Target spawn: pakai writer aktual dengan kontensi write terjadwal."""
    import auth as auth_anak

    asli = auth_anak._tulis_akun_atomik

    def lambat(*args, **kwargs):
        time.sleep(0.02)
        return asli(*args, **kwargs)

    auth_anak._tulis_akun_atomik = lambat
    mulai.wait(10)
    for nomor in range(jumlah):
        auth_anak.tambah_akun(
            f"{awalan}-{nomor}", "sandi-proses-sintetis", "guru",
            path=Path(path_teks),
        )


def _proses_buat_sesi(path_teks, awalan, jumlah, mulai):
    """Target spawn sesi; tidak mengirim token lewat IPC/log."""
    import sessions as sesi_anak

    asli = sesi_anak._tulis

    def lambat(*args, **kwargs):
        time.sleep(0.02)
        return asli(*args, **kwargs)

    sesi_anak._tulis = lambat
    mulai.wait(10)
    for nomor in range(jumlah):
        sesi_anak.buat(
            f"{awalan}-{nomor}", "guru", path=Path(path_teks),
            id_akun=_ID_SESI_UJI, revisi_auth=_REVISI_SESI_UJI,
        )


def _proses_mutasi_akun(path_teks, aksi, mulai):
    import auth as auth_anak

    asli = auth_anak._tulis_akun_atomik

    def lambat(*args, **kwargs):
        time.sleep(0.04)
        return asli(*args, **kwargs)

    auth_anak._tulis_akun_atomik = lambat
    mulai.wait(10)
    path = Path(path_teks)
    if aksi == "reset":
        assert auth_anak.setel_sandi_guru("target", "sandi-target-baru", path)
    elif aksi == "hapus":
        assert auth_anak.hapus_akun_guru("target", path)
    else:
        auth_anak.tambah_akun("tambahan", "sandi-tambahan", "guru", path=path)


def _proses_mutasi_sesi(path_teks, aksi, token_lama, mulai):
    import sessions as sesi_anak

    asli = sesi_anak._tulis

    def lambat(*args, **kwargs):
        time.sleep(0.04)
        return asli(*args, **kwargs)

    sesi_anak._tulis = lambat
    mulai.wait(10)
    path = Path(path_teks)
    if aksi == "hapus":
        assert sesi_anak.hapus(token_lama, path=path)
    elif aksi == "bersihkan":
        assert sesi_anak.bersihkan(path=path) >= 1
    else:
        sesi_anak.buat(
            "baru", "guru", path=path,
            id_akun=_ID_SESI_UJI, revisi_auth=_REVISI_SESI_UJI,
        )


def _jalankan_proses(target, path, jumlah_proses=3, per_proses=4):
    konteks = multiprocessing.get_context("spawn")
    mulai = konteks.Event()
    proses = [
        konteks.Process(
            target=target,
            args=(str(path), f"proses-{nomor}", per_proses, mulai),
        )
        for nomor in range(jumlah_proses)
    ]
    for item in proses:
        item.start()
    mulai.set()
    for item in proses:
        item.join(20)
    assert [item.exitcode for item in proses] == [0] * jumlah_proses
    return jumlah_proses * per_proses


def _jalankan_dua_proses(target, path, aksi_a, aksi_b, *tambahan):
    konteks = multiprocessing.get_context("spawn")
    mulai = konteks.Event()
    proses = [
        konteks.Process(
            target=target, args=(str(path), aksi, *tambahan, mulai)
        )
        for aksi in (aksi_a, aksi_b)
    ]
    for item in proses:
        item.start()
    mulai.set()
    for item in proses:
        item.join(20)
    assert [item.exitcode for item in proses] == [0, 0]


def test_sidecar_runtime_tercakup_gitignore():
    akar = Path(__file__).resolve().parents[2]
    pola = (akar / ".gitignore").read_text(encoding="utf-8")
    assert ".*.json.lock" in pola


def test_lock_reentrant_dan_alias_path_sama(tmp_path):
    path = tmp_path / "sub" / ".." / "state.json"
    with json_storage.transaksi_json(path) as luar:
        with json_storage.transaksi_json(tmp_path / "state.json") as dalam:
            assert luar == dalam == (tmp_path / "state.json").resolve()
    lock = json_storage.jalur_lock(path)
    assert lock.exists()
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


def test_lock_alias_symlink_memakai_sidecar_kanonik_yang_sama(tmp_path):
    nyata = tmp_path / "nyata"
    nyata.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(nyata, target_is_directory=True)
    langsung = nyata / "state.json"
    lewat_alias = alias / "state.json"

    assert json_storage.jalur_lock(langsung) == json_storage.jalur_lock(lewat_alias)
    with json_storage.transaksi_json(lewat_alias) as tujuan:
        assert tujuan == langsung.resolve()


def test_noop_writer_auth_tidak_membuat_data(tmp_path):
    path = tmp_path / "belum-ada.json"

    assert auth.pastikan_id_akun(path) is False
    assert auth.pastikan_admin(path) is None
    assert not path.exists()
    assert stat.S_IMODE(json_storage.jalur_lock(path).stat().st_mode) == 0o600


def test_akun_create_create_thread_tidak_lost_update(tmp_path, monkeypatch):
    path = tmp_path / "akun.json"
    auth.tambah_akun("awal", "sandi-awal-sintetis", "guru", path=path)
    _perlambat_writer(auth, "_tulis_akun_atomik", monkeypatch)
    nama = [f"akun-thread-{nomor}" for nomor in range(10)]

    _jalankan_bersamaan(*(
        lambda nilai=nilai: auth.tambah_akun(
            nilai, "sandi-thread-sintetis", "guru", path=path
        )
        for nilai in nama
    ))

    tersimpan = {item["pengguna"] for item in auth.muat_akun(path)}
    assert {"awal", *nama} <= tersimpan


def test_akun_create_nama_sama_thread_hanya_satu_berhasil(tmp_path, monkeypatch):
    path = tmp_path / "akun.json"
    _perlambat_writer(auth, "_tulis_akun_atomik", monkeypatch)
    mulai = threading.Barrier(3, timeout=5)
    hasil = []

    def tambah():
        mulai.wait()
        try:
            auth.tambah_akun("sama", "sandi-sama", "guru", path=path)
            hasil.append("berhasil")
        except ValueError as galat:
            hasil.append(str(galat))

    ulir = [threading.Thread(target=tambah) for _ in range(2)]
    for item in ulir:
        item.start()
    mulai.wait()
    for item in ulir:
        item.join(timeout=10)

    assert sorted(hasil) == ["berhasil", "nama pengguna sudah dipakai: sama"]
    assert [item["pengguna"] for item in auth.muat_akun(path)] == ["sama"]


def test_id_akun_collision_dibangkitkan_ulang_di_dalam_lock(tmp_path, monkeypatch):
    path = tmp_path / "akun.json"
    id_lama = "akun_" + "a" * 32
    id_baru = "akun_" + "b" * 32
    path.write_text(json.dumps({"akun": [{
        "pengguna": "lama", "peran": "guru", "id_akun": id_lama,
        **auth.buat_hash("sandi-lama"),
    }]}), encoding="utf-8")
    urutan = iter((id_lama, id_baru))
    monkeypatch.setattr(auth, "_buat_id_akun", lambda: next(urutan))

    auth.tambah_akun("baru", "sandi-baru", "guru", path=path)

    assert auth.cari_akun("baru", path)["id_akun"] == id_baru


def test_akun_reset_create_thread_mempertahankan_keduanya(tmp_path, monkeypatch):
    path = tmp_path / "akun.json"
    auth.tambah_akun("target", "sandi-target-lama", "guru", path=path)
    _perlambat_writer(auth, "_tulis_akun_atomik", monkeypatch)

    _jalankan_bersamaan(
        lambda: auth.setel_sandi_guru("target", "sandi-target-baru", path),
        lambda: auth.tambah_akun("tambahan", "sandi-tambahan", "guru", path),
    )

    assert auth.periksa_peran("target", "sandi-target-baru", "guru", path)
    assert auth.cari_akun("tambahan", path) is not None


def test_akun_delete_create_thread_mempertahankan_keduanya(tmp_path, monkeypatch):
    path = tmp_path / "akun.json"
    auth.tambah_akun("target", "sandi-target-lama", "murid", path=path)
    _perlambat_writer(auth, "_tulis_akun_atomik", monkeypatch)

    _jalankan_bersamaan(
        lambda: auth.hapus_akun("target", path),
        lambda: auth.tambah_akun("tambahan", "sandi-tambahan", "guru", path),
    )

    assert auth.cari_akun("target", path) is None
    assert auth.cari_akun("tambahan", path) is not None


def test_akun_create_create_lintas_proses_tidak_lost_update(tmp_path):
    path = tmp_path / "akun-proses.json"
    auth.tambah_akun("awal", "sandi-awal-sintetis", "guru", path=path)
    jumlah = _jalankan_proses(_proses_tambah_akun, path)

    akun = auth.muat_akun(path)
    assert len(akun) == jumlah + 1
    assert len({item["pengguna"] for item in akun}) == jumlah + 1


def test_akun_reset_create_lintas_proses_mempertahankan_keduanya(tmp_path):
    path = tmp_path / "akun-proses.json"
    auth.tambah_akun("target", "sandi-target-lama", "guru", path=path)

    _jalankan_dua_proses(_proses_mutasi_akun, path, "reset", "buat")

    assert auth.periksa_peran("target", "sandi-target-baru", "guru", path)
    assert auth.cari_akun("tambahan", path) is not None


def test_akun_delete_create_lintas_proses_mempertahankan_keduanya(tmp_path):
    path = tmp_path / "akun-proses.json"
    auth.tambah_akun("target", "sandi-target-lama", "guru", path=path)

    _jalankan_dua_proses(_proses_mutasi_akun, path, "hapus", "buat")

    assert auth.cari_akun("target", path) is None
    assert auth.cari_akun("tambahan", path) is not None


def test_sesi_create_create_thread_tidak_lost_update(tmp_path, monkeypatch):
    path = tmp_path / "sesi.json"
    _perlambat_writer(sessions, "_tulis", monkeypatch)
    token = []
    token_lock = threading.Lock()

    def buat(nomor):
        hasil = _buat_sesi(f"akun-{nomor}", "guru", path=path)
        with token_lock:
            token.append(hasil)

    _jalankan_bersamaan(*(lambda nomor=nomor: buat(nomor) for nomor in range(12)))

    tersimpan = sessions.muat(path)
    assert len(token) == 12
    assert all(nilai in tersimpan for nilai in token)


def test_token_collision_dibangkitkan_ulang_di_dalam_lock(tmp_path, monkeypatch):
    path = tmp_path / "sesi.json"
    path.write_text(json.dumps({
        "token-sama": {
            "pengguna": "lama", "peran": "guru", "kedaluarsa": time.time() + 1000,
        }
    }), encoding="utf-8")
    urutan = iter(("token-sama", "token-baru"))
    monkeypatch.setattr(sessions.secrets, "token_urlsafe", lambda _n: next(urutan))

    token = _buat_sesi("baru", "guru", path=path)

    assert token == "token-baru"
    assert set(sessions.muat(path)) == {"token-sama", "token-baru"}


def test_sesi_delete_create_thread_mempertahankan_keduanya(tmp_path, monkeypatch):
    path = tmp_path / "sesi.json"
    lama = _buat_sesi("lama", "guru", path=path)
    _perlambat_writer(sessions, "_tulis", monkeypatch)
    baru = []

    _jalankan_bersamaan(
        lambda: sessions.hapus(lama, path=path),
        lambda: baru.append(_buat_sesi("baru", "guru", path=path)),
    )

    tersimpan = sessions.muat(path)
    assert lama not in tersimpan
    assert len(baru) == 1 and baru[0] in tersimpan


def test_sesi_cleanup_create_thread_mempertahankan_token_baru(tmp_path, monkeypatch):
    path = tmp_path / "sesi.json"
    lama = _buat_sesi("lama", "guru", path=path, sekarang=0)
    _perlambat_writer(sessions, "_tulis", monkeypatch)
    baru = []

    _jalankan_bersamaan(
        lambda: sessions.bersihkan(path=path),
        lambda: baru.append(_buat_sesi("baru", "guru", path=path)),
    )

    tersimpan = sessions.muat(path)
    assert lama not in tersimpan
    assert len(baru) == 1 and baru[0] in tersimpan


def test_sesi_create_create_lintas_proses_tidak_lost_update(tmp_path):
    path = tmp_path / "sesi-proses.json"
    jumlah = _jalankan_proses(_proses_buat_sesi, path)

    data = sessions.muat(path)
    assert len(data) == jumlah
    assert len({entri["pengguna"] for entri in data.values()}) == jumlah


def test_sesi_delete_create_lintas_proses_mempertahankan_keduanya(tmp_path):
    path = tmp_path / "sesi-proses.json"
    token_lama = _buat_sesi("lama", "guru", path=path)

    _jalankan_dua_proses(
        _proses_mutasi_sesi, path, "hapus", "buat", token_lama
    )

    data = sessions.muat(path)
    assert token_lama not in data
    assert {entri["pengguna"] for entri in data.values()} == {"baru"}


def test_sesi_cleanup_create_lintas_proses_mempertahankan_token_baru(tmp_path):
    path = tmp_path / "sesi-proses.json"
    token_lama = _buat_sesi("lama", "guru", path=path, sekarang=0)

    _jalankan_dua_proses(
        _proses_mutasi_sesi, path, "bersihkan", "buat", token_lama
    )

    data = sessions.muat(path)
    assert token_lama not in data
    assert {entri["pengguna"] for entri in data.values()} == {"baru"}


def test_sesi_create_mempertahankan_field_entri_existing(tmp_path):
    path = tmp_path / "sesi.json"
    existing = {
        "token-existing": {
            "pengguna": "lama",
            "peran": "guru",
            "kedaluarsa": time.time() + 1000,
            "id_akun": "akun_" + "a" * 32,
            "revisi_auth": 1,
            "metadata": {"tetap": True},
        }
    }
    path.write_text(json.dumps(existing), encoding="utf-8")

    token_baru = _buat_sesi("baru", "guru", path=path)
    hasil = json.loads(path.read_text(encoding="utf-8"))

    assert hasil["token-existing"] == existing["token-existing"]
    assert token_baru in hasil


def test_semua_writer_auth_menolak_json_rusak_tanpa_overwrite(tmp_path):
    operasi = (
        lambda path: auth.simpan_sandi("sandi-baru", "guru", path),
        lambda path: auth.pastikan_id_akun(path),
        lambda path: auth.tambah_akun("baru", "sandi-baru", "guru", path),
        lambda path: auth.pastikan_admin(path),
        lambda path: auth.hapus_akun("murid", path),
        lambda path: auth.hapus_akun_guru("guru", path),
        lambda path: auth.setel_sandi_murid("murid", "sandi-baru", path),
        lambda path: auth.setel_sandi_guru("guru", "sandi-baru", path),
    )
    for nomor, mutasi in enumerate(operasi):
        path = tmp_path / f"akun-rusak-{nomor}.json"
        sebelum = b'{"akun":[rusak]}'
        path.write_bytes(sebelum)
        with pytest.raises(ValueError, match="berkas akun tidak sah"):
            mutasi(path)
        assert path.read_bytes() == sebelum


def test_semua_writer_sesi_menolak_json_rusak_tanpa_overwrite(tmp_path):
    operasi = (
        lambda path: _buat_sesi("baru", "guru", path=path),
        lambda path: sessions.hapus("token", path=path),
        lambda path: sessions.bersihkan(path=path),
    )
    for nomor, mutasi in enumerate(operasi):
        path = tmp_path / f"sesi-rusak-{nomor}.json"
        sebelum = b'{"token":rusak}'
        path.write_bytes(sebelum)
        with pytest.raises(ValueError, match="berkas sesi tidak sah"):
            mutasi(path)
        assert path.read_bytes() == sebelum
        assert sessions.muat(path) == {}, "reader sesi harus tetap fail-closed"


@pytest.mark.parametrize(
    "isi_akun,isi_sesi",
    [
        ("null", "null"),
        ("[]", "[]"),
        ('{"akun":[{"peran":"guru"}]}', '{"token":[]}'),
        ('{"asing":true}', '{"token":{"pengguna":"u"}}'),
        (
            '{"akun":[],"akun":[]}',
            '{"token":{"pengguna":"u","peran":"guru","kedaluarsa":1},'
            '"token":{"pengguna":"u","peran":"guru","kedaluarsa":2}}',
        ),
    ],
)
def test_writer_menolak_schema_json_salah(tmp_path, isi_akun, isi_sesi):
    akun = tmp_path / "akun.json"
    sesi = tmp_path / "sesi.json"
    akun.write_text(isi_akun, encoding="utf-8")
    sesi.write_text(isi_sesi, encoding="utf-8")

    with pytest.raises(ValueError, match="berkas akun tidak sah"):
        auth.tambah_akun("baru", "sandi-baru", "guru", akun)
    with pytest.raises(ValueError, match="berkas sesi tidak sah"):
        _buat_sesi("baru", "guru", path=sesi)
    assert akun.read_text(encoding="utf-8") == isi_akun
    assert sesi.read_text(encoding="utf-8") == isi_sesi
    assert auth.muat_sandi(akun) is None
    assert sessions.muat(sesi) == {}


def test_metadata_envelope_dan_field_akun_dipertahankan_semua_mutasi(tmp_path):
    path = tmp_path / "akun.json"
    data = {
        "versi_envelope": 7,
        "catatan_envelope": {"tetap": True},
        "akun": [
            {
                "pengguna": "guru-a",
                "peran": "guru",
                "id_akun": "akun_" + "a" * 32,
                "field_tambahan": {"tetap": 1},
                **auth.buat_hash("sandi-guru-a"),
            },
            {
                "pengguna": "murid-a",
                "peran": "murid",
                "id_akun": "akun_" + "b" * 32,
                "siswa_id": 17,
                "field_murid": "tetap",
                **auth.buat_hash("sandi-murid-a"),
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    auth.simpan_sandi("sandi-guru-baru", "guru-a", path)
    auth.setel_sandi_murid("murid-a", "sandi-murid-baru", path)
    auth.tambah_akun("tambahan", "sandi-tambahan", "guru", path)
    hasil = json.loads(path.read_text(encoding="utf-8"))

    assert hasil["versi_envelope"] == 7
    assert hasil["catatan_envelope"] == {"tetap": True}
    guru = next(item for item in hasil["akun"] if item["pengguna"] == "guru-a")
    murid = next(item for item in hasil["akun"] if item["pengguna"] == "murid-a")
    assert guru["id_akun"] == "akun_" + "a" * 32
    assert guru["field_tambahan"] == {"tetap": 1}
    assert murid["id_akun"] == "akun_" + "b" * 32
    assert murid["siswa_id"] == 17 and murid["field_murid"] == "tetap"

    assert auth.hapus_akun("murid-a", path)
    assert auth.hapus_akun_guru("guru-a", path)
    akhir = json.loads(path.read_text(encoding="utf-8"))
    assert akhir["versi_envelope"] == 7
    assert akhir["catatan_envelope"] == {"tetap": True}


def test_pastikan_admin_mempertahankan_metadata_envelope(tmp_path):
    path = tmp_path / "akun.json"
    path.write_text(json.dumps({
        "versi_envelope": 9,
        "metadata": {"tetap": True},
        "akun": [{
            "pengguna": "guru", "peran": "guru",
            "id_akun": "akun_" + "d" * 32,
            "field_akun": "tetap",
            **auth.buat_hash("sandi-guru"),
        }],
    }), encoding="utf-8")

    assert auth.pastikan_admin(path) == "guru"
    hasil = json.loads(path.read_text(encoding="utf-8"))
    assert hasil["versi_envelope"] == 9
    assert hasil["metadata"] == {"tetap": True}
    assert hasil["akun"][0]["field_akun"] == "tetap"
    assert hasil["akun"][0]["peran"] == "admin"


def test_simpan_sandi_legacy_mempertahankan_format_dan_metadata(tmp_path):
    path = tmp_path / "legacy.json"
    data = {
        "pengguna": "guru",
        "id_akun": "akun_" + "c" * 32,
        "metadata": {"tetap": "ya"},
        **auth.buat_hash("sandi-lama"),
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    assert auth.simpan_sandi("sandi-baru", "guru", path) == path
    hasil = json.loads(path.read_text(encoding="utf-8"))
    assert "akun" not in hasil and "peran" not in hasil
    assert hasil["pengguna"] == "guru"
    assert hasil["revisi_auth"] == 1
    assert hasil["id_akun"] == "akun_" + "c" * 32
    assert hasil["metadata"] == {"tetap": "ya"}
    assert auth.periksa("guru", "sandi-baru", hasil)


def test_sidecar_symlink_ditolak_tanpa_menyentuh_target(tmp_path):
    path = tmp_path / "state.json"
    tujuan_symlink = tmp_path / "bukan-lock.txt"
    tujuan_symlink.write_text("tetap", encoding="utf-8")
    json_storage.jalur_lock(path).symlink_to(tujuan_symlink)

    with pytest.raises((OSError, json_storage.GalatPenyimpananJSON)):
        json_storage.tulis_json_atomik({"baru": True}, path)

    assert not path.exists()
    assert tujuan_symlink.read_text(encoding="utf-8") == "tetap"


def test_gagal_replace_meninggalkan_target_dan_membersihkan_temp(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    sebelum = b'{"tetap":true}'
    path.write_bytes(sebelum)

    def gagal_replace(*_args):
        raise OSError("gagal sintetis replace")

    monkeypatch.setattr(json_storage.os, "replace", gagal_replace)
    with pytest.raises(OSError, match="gagal sintetis replace"):
        json_storage.tulis_json_atomik({"baru": True}, path)

    assert path.read_bytes() == sebelum
    assert list(tmp_path.glob(".state.json-*")) == []


def test_gagal_replace_writer_auth_dan_sesi_menjaga_state_lama(tmp_path, monkeypatch):
    akun = tmp_path / "akun.json"
    sesi = tmp_path / "sesi.json"
    auth.tambah_akun("lama", "sandi-lama", "guru", path=akun)
    token = _buat_sesi("lama", "guru", path=sesi)
    akun_sebelum = akun.read_bytes()
    sesi_sebelum = sesi.read_bytes()

    def gagal_replace(*_args):
        raise OSError("gagal sintetis replace")

    monkeypatch.setattr(json_storage.os, "replace", gagal_replace)
    with pytest.raises(OSError, match="gagal sintetis replace"):
        auth.tambah_akun("baru", "sandi-baru", "guru", path=akun)
    with pytest.raises(OSError, match="gagal sintetis replace"):
        sessions.hapus(token, path=sesi)

    assert akun.read_bytes() == akun_sebelum
    assert sesi.read_bytes() == sesi_sebelum
    assert list(tmp_path.glob(".akun.json-*")) == []
    assert list(tmp_path.glob(".sesi.json-*")) == []


def test_gagal_serialisasi_meninggalkan_target_dan_membersihkan_temp(tmp_path):
    path = tmp_path / "state.json"
    sebelum = b'{"tetap":true}'
    path.write_bytes(sebelum)

    with pytest.raises((TypeError, ValueError)):
        json_storage.tulis_json_atomik({"tidak_json": object()}, path)

    assert path.read_bytes() == sebelum
    assert list(tmp_path.glob(".state.json-*")) == []


def test_atomic_write_fsync_dan_permission_privat(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    dipanggil = []
    asli = json_storage.os.fsync

    def catat(fd):
        dipanggil.append(fd)
        return asli(fd)

    monkeypatch.setattr(json_storage.os, "fsync", catat)
    json_storage.tulis_json_atomik({"aman": True}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"aman": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(json_storage.jalur_lock(path).stat().st_mode) == 0o600
    assert len(dipanggil) >= 2, "file dan direktori harus disinkronkan"
