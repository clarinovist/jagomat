"""Primitive recourse keluarga: preview, guard, isolasi, dan bundle hasil."""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading

import pytest

import admin_backup
import admin_contracts as c
import admin_store
import admin_students
import ai_store
import assistant_schema
import assistant_store
import auth
import database
import family_deletion as hapus
import sessions


ADMIN = "akun_" + "a" * 32
TARGET = "akun_" + "b" * 32
LAIN = "akun_" + "c" * 32
TOKEN = "T" * 48


def _akun(pengguna, peran, identitas, sandi, revisi=1):
    return {"pengguna": pengguna, "peran": peran, "id_akun": identitas,
            "revisi_auth": revisi, **auth.buat_hash(sandi)}


@pytest.fixture()
def penyimpanan(tmp_path):
    live = tmp_path / "live"
    live.mkdir()
    paths = {
        "belajar": live / "latihan.db", "auth": live / "sandi.json",
        "admin": live / "admin-control.db", "ai": live / "ai-control.db",
        "pendamping": live / "pendamping.db", "sesi": live / "sesi.json",
    }
    database.siapkan(paths["belajar"])
    admin_students.siapkan(paths["belajar"])
    admin_store.siapkan(paths["admin"], sekarang=1)
    ai_store.siapkan(paths["ai"], sekarang=1)
    assistant_schema.siapkan(paths["pendamping"])
    paths["auth"].write_text(json.dumps({"akun": [
        _akun("admin-sintetis", "admin", ADMIN, "sandi-admin-sintetis", 2),
        _akun("keluarga-target", "guru", TARGET, "sandi-target-sintetis"),
        _akun("keluarga-lain", "guru", LAIN, "sandi-lain-sintetis"),
    ]}), encoding="utf-8")
    for path in paths.values():
        if path.exists():
            path.chmod(0o600)
    with database.buka(paths["belajar"]) as kon:
        target = database.tambah_siswa(kon, "Anak Target", "P3", pemilik="keluarga-target")
        lain = database.tambah_siswa(kon, "Anak Lain", "P3", pemilik="keluarga-lain")
        sesi_target = database.buat_sesi(kon, target, seed=31, jumlah_soal=1)
        database.buat_sesi(kon, target, seed=33, jumlah_soal=1)
        sesi_lain = database.buat_sesi(kon, lain, seed=32, jumlah_soal=1)
        baris = database.isi_sesi(kon, sesi_target)[0]
        jid = database.simpan_jawaban(kon, baris["sesi_soal_id"], jawaban=baris["kunci"], cara="cara sintetis")
        database.simpan_diagnosis(kon, jid, True, None, None, None, "")
        database.tandai_selesai(kon, sesi_target)
        database.konfirmasi_hasil(kon, sesi_target, "keluarga-target")
    principal_target = auth.autentikasi("keluarga-target", "sandi-target-sintetis", paths["auth"])
    sessions.buat_dari_principal(principal_target, path=paths["sesi"], path_akun=paths["auth"])
    with assistant_schema.buka(paths["pendamping"]) as kon:
        assistant_store.buat_chat(kon, TARGET, "aktif", sekarang=10)
    bundle = tmp_path / "backup"
    bundle.mkdir(mode=0o700)
    for jenis, nama in admin_backup.BERKAS_WAJIB.items():
        shutil.copy2(paths[jenis], bundle / nama)
        (bundle / nama).chmod(0o600)
    admin_backup.buat_manifest(bundle, bundle_id="backup-recourse-001", cutoff=20)
    return paths, bundle, tmp_path / "hasil", target, lain, sesi_target, sesi_lain


def _perintah(inv, *, verifikasi=True, sidik=None, operasi="operasi_hapus_keluarga_001"):
    return c.PerintahHapusKeluarga(
        operasi, ADMIN, 2, "family_data_delete", TARGET, 1, "guru",
        sidik or inv.sidik, "backup-recourse-001", verifikasi, TOKEN,
    )


def _jalankan(data, perintah):
    paths, bundle, hasil, *_ = data
    return hapus.jalankan(
        paths["belajar"], paths["auth"], paths["admin"], paths["ai"],
        paths["pendamping"], bundle=bundle, bundle_hasil=hasil,
        perintah=perintah, sekarang=30, path_sesi=paths["sesi"],
    )


def test_preview_agregat_dan_matriks_tanpa_isi_keluarga(penyimpanan):
    paths, _bundle, _hasil, *_ = penyimpanan
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id=TARGET)
    assert (inv.jumlah_profil, inv.jumlah_sesi, inv.jumlah_sesi_berbukti) == (1, 2, 1)
    assert inv.jumlah_chat == 1 and len(inv.sidik) == 64
    teks = repr(inv)
    assert "Anak Target" not in teks and "cara sintetis" not in teks
    assert ("bukti belajar serta arsip pengiriman append-only", "anonimkan") in inv.matriks


def test_verifikasi_independen_dan_backup_exact_wajib(penyimpanan):
    paths, bundle, hasil, *_ = penyimpanan
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id=TARGET)
    with pytest.raises(c.KontrakTidakSah, match="verifikasi independen"):
        _perintah(inv, verifikasi=False)
    # Defense in depth pada service tetap diuji, bukan hanya constructor typed.
    palsu = _perintah(inv)
    object.__setattr__(palsu, "verifikasi_independen", False)
    with pytest.raises(hapus.PenghapusanDitolak, match="verifikasi independen"):
        _jalankan(penyimpanan, palsu)
    with pytest.raises(hapus.PenghapusanDitolak, match="inventaris berubah"):
        _jalankan(penyimpanan, _perintah(inv, sidik="f" * 64))
    assert not hasil.exists()
    assert auth.cari_akun("keluarga-target", paths["auth"]) is not None


def test_bundle_hasil_memutus_data_aktif_menjaga_arsip_dan_isolasi(penyimpanan):
    paths, _bundle, hasil, target_sid, lain_sid, sesi_target, sesi_lain = penyimpanan
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id=TARGET)
    sebelum_live = {k: p.read_bytes() for k, p in paths.items()}
    selesai = _jalankan(penyimpanan, _perintah(inv))
    replay = _jalankan(penyimpanan, _perintah(inv))
    assert selesai.status == "succeeded" and selesai.baru_dieksekusi
    assert replay.status == "succeeded" and not replay.baru_dieksekusi
    assert {k: p.read_bytes() for k, p in paths.items()} == sebelum_live
    assert selesai.sesi_dicabut == 1 and len(sessions.muat(paths["sesi"])) == 1

    bundle_hasil = hasil / "bundle"
    auth_hasil = bundle_hasil / "sandi.json"
    assert auth.cari_akun("keluarga-target", auth_hasil) is None
    tombstone = next(a for a in auth.muat_akun(auth_hasil) if a["id_akun"] == TARGET)
    assert tombstone["dinonaktifkan"] is True
    assert auth.autentikasi(tombstone["pengguna"], "sandi-target-sintetis", auth_hasil) is None
    assert auth.cari_akun("keluarga-lain", auth_hasil) is not None
    assert "keluarga-target" not in auth_hasil.read_text(encoding="utf-8")
    with database.buka(bundle_hasil / "latihan.db") as kon:
        target = kon.execute("SELECT nama,pemilik FROM siswa WHERE id=?", (target_sid,)).fetchone()
        lain = kon.execute("SELECT nama,pemilik FROM siswa WHERE id=?", (lain_sid,)).fetchone()
        assert target["nama"].startswith("Dihapus-") and target["pemilik"].startswith("keluarga_dihapus_")
        assert tuple(lain) == ("Anak Lain", "keluarga-lain")
        assert kon.execute("SELECT 1 FROM sesi WHERE id=?", (sesi_target,)).fetchone()
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (target_sid,)).fetchone()[0] == 1
        assert kon.execute("SELECT 1 FROM sesi WHERE id=?", (sesi_lain,)).fetchone()
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id=?", (sesi_target,)).fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM snapshot_outcome so JOIN konfirmasi_hasil kh ON kh.id=so.konfirmasi_id WHERE kh.sesi_id=?", (sesi_target,)).fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=?", (sesi_target,)).fetchone()[0] == 0
        assert kon.execute("PRAGMA foreign_key_check").fetchone() is None
    with assistant_schema.buka(bundle_hasil / "pendamping.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM chat WHERE account_id=?", (TARGET,)).fetchone()[0] == 0
    receipt_path = hasil / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert admin_backup.validasi_bundle(bundle_hasil).bundle_id == receipt["bundle_hasil_id"]
    assert hapus.cabut_sesi_setelah_cutover(
        paths["sesi"], target_id=TARGET, receipt_path=receipt_path) == 1
    assert sessions.muat(paths["sesi"]) == {}
    assert receipt["inventaris_sidik"] == inv.sidik
    assert "keluarga-target" not in json.dumps(receipt)


def test_dua_eksekutor_operation_id_sama_hanya_satu_baru(penyimpanan):
    paths, _bundle, _hasil, *_ = penyimpanan
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id=TARGET)
    perintah = _perintah(inv)
    hasil = []
    galat = []
    def kerja():
        try:
            hasil.append(_jalankan(penyimpanan, perintah))
        except Exception as exc:  # pragma: no cover - dilaporkan assert
            galat.append(exc)
    threads = [threading.Thread(target=kerja) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert not galat
    assert len(hasil) == 2
    assert sorted(x.baru_dieksekusi for x in hasil) == [False, True]


def test_state_berubah_setelah_preview_ditolak_tanpa_bundle(penyimpanan):
    paths, _bundle, hasil, *_ = penyimpanan
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id=TARGET)
    auth.naikkan_revisi_auth(TARGET, paths["auth"])
    with pytest.raises(hapus.PenghapusanDitolak, match="inventaris berubah"):
        _jalankan(penyimpanan, _perintah(inv))
    assert not hasil.exists()
