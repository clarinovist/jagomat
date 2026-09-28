"""Konteks anak/sesi Pendamping harus minimum, eksplisit, dan tetap dimiliki."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_context  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_policy  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import database  # noqa: E402
import question_views  # noqa: E402

from test_assistant_runtime import ProviderPalsu  # noqa: E402

AKUN = "akun_" + "a" * 32


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "latihan.db"
    database.siapkan(path)
    return path


@pytest.fixture()
def privat(tmp_path):
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    return path


def test_migrasi_v1_ke_v2_idempoten_dan_menjaga_chat(tmp_path):
    path = tmp_path / "pendamping-v1.db"
    with sqlite3.connect(path) as koneksi:
        koneksi.executescript("""
        CREATE TABLE chat (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
            mode_memori TEXT NOT NULL, context_kind TEXT, context_id TEXT,
            context_version INTEGER, versi INTEGER NOT NULL DEFAULT 1,
            dibuat INTEGER NOT NULL, diperbarui INTEGER NOT NULL,
            dihapus INTEGER, purge_setelah INTEGER
        );
        CREATE TABLE migrasi_pendamping (
            versi INTEGER PRIMARY KEY, diterapkan TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO migrasi_pendamping(versi) VALUES (1);
        INSERT INTO chat(id, account_id, mode_memori, dibuat, diperbarui)
        VALUES ('chat_lama', 'akun_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'aktif', 1, 1);
        PRAGMA user_version = 1;
        """)
    assistant_schema.siapkan(path)
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as koneksi:
        assert koneksi.execute("PRAGMA user_version").fetchone()[0] == 4
        assert koneksi.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 1
        assert "context_resource_version" in {
            baris["name"] for baris in koneksi.execute("PRAGMA table_info(chat)")
        }
        assert koneksi.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []


def test_konteks_soal_minimum_dari_snapshot_yang_sama(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="ortu")
        sesi = database.buat_sesi(kon, siswa, seed=42)
        sumber = database.isi_sesi(kon, sesi)[0]
        hasil = assistant_context.konteks_soal(kon, sesi, 1, pemilik="ortu")
        penyajian = question_views.penyajian_dari_baris(sumber)
        soal = question_views.soal_dari_baris(sumber)

    assert hasil.resource_id == f"{sesi}:1"
    assert hasil.versi == penyajian.fingerprint_penyajian
    assert hasil.muatan["teks_soal"] == penyajian.teks_soal
    assert hasil.muatan["kunci"] == soal.kunci
    assert hasil.muatan["pembahasan"] == soal.pembahasan
    assert set(hasil.muatan) == {
        "jenis", "nomor", "template_id", "level", "teks_soal",
        "descriptor", "kunci", "pembahasan", "fingerprint_penyajian",
    }
    mentah = json.dumps(hasil.muatan)
    for terlarang in ("Anak Sintetis", "jawaban_anak", "diagnosis", "malrule", "catatan"):
        assert terlarang not in mentah


def test_konteks_soal_asing_dan_hilang_identik(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak A", pemilik="ortu-a")
        sesi = database.buat_sesi(kon, siswa, seed=42)
        assert assistant_context.konteks_soal(kon, sesi, 1, pemilik="ortu-b") is None
        assert assistant_context.konteks_soal(kon, 999999, 1, pemilik="ortu-b") is None
        assert assistant_context.konteks_sesi(kon, sesi, pemilik="ortu-b") is None
        assert assistant_context.konteks_sesi(kon, 999999, pemilik="ortu-b") is None


def test_snapshot_rusak_tidak_fallback_ke_soal_baru(db, monkeypatch):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak A", pemilik="ortu")
        sesi = database.buat_sesi(kon, siswa, seed=42)
        kon.execute(
            "UPDATE sesi_soal SET penyajian_json = '{rusak' WHERE sesi_id = ? AND nomor = 1",
            (sesi,),
        )
        monkeypatch.setitem(
            question_views.REGISTRI,
            "deret_aritmetika",
            lambda **_: pytest.fail("snapshot rusak tidak boleh regenerate"),
        )
        with pytest.raises(ValueError, match="snapshot"):
            assistant_context.konteks_soal(kon, sesi, 1, pemilik="ortu")


def test_ringkasan_anak_netral_tanpa_nama_atau_kode(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Nama Tidak Boleh Keluar", "P4", pemilik="ortu")
        hasil = assistant_context.konteks_anak(kon, siswa, pemilik="ortu")
    assert hasil.resource_id == str(siswa)
    assert set(hasil.muatan) == {"jenis", "level", "tahap", "tersedia_pada"}
    mentah = json.dumps(hasil.muatan)
    assert "Nama Tidak Boleh Keluar" not in mentah
    assert not any(kode in hasil.muatan["tahap"] for kode in ("K", "B", "H", "E", "N", "T"))


def test_ikat_konteks_hanya_ke_chat_baru_dan_consent_resource(privat):
    with assistant_schema.buka(privat) as kon:
        consent = assistant_store.beri_persetujuan_konteks(
            kon, AKUN, jenis="soal", resource_id="7:1", resource_version="abc",
            kategori="soal_resmi", sekarang=100,
        )
        chat = assistant_store.buat_chat(
            kon, AKUN, "aktif", sekarang=101,
            context_kind="soal", context_id="7:1", context_version=consent.versi,
            context_resource_version="abc", context_category="soal_resmi",
        )
        assert chat.context_kind == "soal"
        assert chat.context_id == "7:1"
        assert assistant_store.persetujuan_konteks_aktif(
            kon, AKUN, jenis="soal", resource_id="7:1",
            resource_version="abc", kategori="soal_resmi",
        )
        with pytest.raises(ValueError, match="konteks"):
            assistant_store.ubah_konteks_chat(
                kon, AKUN, chat.id, context_kind="anak", context_id="8"
            )


def test_kategori_consent_harus_cocok_jenis_context(privat):
    with assistant_schema.buka(privat) as kon:
        consent = assistant_store.beri_persetujuan_konteks(
            kon, AKUN, jenis="anak", resource_id="1", resource_version="v1",
            kategori="ringkasan_netral", sekarang=100,
        )
        with pytest.raises(ValueError, match="persetujuan konteks"):
            assistant_store.buat_chat(
                kon, AKUN, "aktif", sekarang=101,
                context_kind="anak", context_id="1",
                context_version=consent.versi,
                context_resource_version="v1", context_category="soal_resmi",
            )


def test_cabut_context_membuat_izin_tidak_aktif(privat):
    with assistant_schema.buka(privat) as kon:
        consent = assistant_store.beri_persetujuan_konteks(
            kon, AKUN, jenis="anak", resource_id="1", resource_version="v1",
            kategori="ringkasan_netral", sekarang=100,
        )
        assert assistant_store.cabut_persetujuan_konteks(
            kon, AKUN, consent.id, versi_diharapkan=consent.versi,
            sekarang=101,
        )
        assert not assistant_store.persetujuan_konteks_aktif(
            kon, AKUN, jenis="anak", resource_id="1",
            resource_version="v1", kategori="ringkasan_netral",
        )
        with pytest.raises(ValueError, match="persetujuan konteks"):
            assistant_store.buat_chat(
                kon, AKUN, "aktif", sekarang=102,
                context_kind="anak", context_id="1",
                context_version=consent.versi,
                context_resource_version="v1",
                context_category="ringkasan_netral",
            )


def test_context_asing_tidak_bisa_diikat(privat):
    with assistant_schema.buka(privat) as kon:
        assistant_store.beri_persetujuan_konteks(
            kon, AKUN, jenis="anak", resource_id="1", resource_version="v1",
            kategori="ringkasan_netral", sekarang=100,
        )
        with pytest.raises(ValueError, match="persetujuan konteks"):
            assistant_store.buat_chat(
                kon, "akun_" + "b" * 32, "aktif", sekarang=101,
                context_kind="anak", context_id="1", context_version=1,
                context_resource_version="v1",
                context_category="ringkasan_netral",
            )


def _chat_konteks(kon, resource_id="1"):
    konteks = assistant_context.KonteksPendamping(
        jenis="anak", resource_id=resource_id, versi="v1",
        kategori="ringkasan_netral", muatan={"jenis": "ringkasan_anak", "level": "P3"},
    )
    izin = assistant_store.beri_persetujuan_konteks(
        kon, AKUN, jenis=konteks.jenis, resource_id=konteks.resource_id,
        resource_version=konteks.versi, kategori=konteks.kategori, sekarang=100,
    )
    chat = assistant_store.buat_chat(
        kon, AKUN, "aktif", sekarang=100,
        context_kind=konteks.jenis, context_id=konteks.resource_id,
        context_version=izin.versi, context_resource_version=konteks.versi,
        context_category=konteks.kategori,
    )
    return chat, konteks, izin


def _izin_provider(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum", sekarang=100,
    )


@pytest.mark.parametrize("saat_network", [False, True])
def test_service_dua_konteks_sah_menyimpan_versi_chat_sendiri(privat, saat_network):
    with assistant_schema.buka(privat) as kon:
        _izin_provider(kon)
        pertama = _chat_konteks(kon, "1")
        kedua = []
        if not saat_network:
            kedua.append(_chat_konteks(kon, "2"))
        kon.commit()
        provider = ProviderPalsu(respons={
            "jawaban": "Mari tinjau latihan ini.", "draft_memori": None,
            "usulan_latihan": {"topik_id": "pola-bilangan",
                               "template_ids": ["deret_aritmetika"],
                               "level": "P3", "jumlah_soal": 10},
            "butuh_klarifikasi": False,
        })

        def jawab(pesan):
            assert not kon.in_transaction
            if saat_network and not kedua:
                with assistant_schema.buka(privat) as lain:
                    kedua.append(_chat_konteks(lain, "2"))
            return provider(pesan)

        chat, konteks, _ = pertama
        assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Buat usulan latihan pertama.",
            request_id="req_konteks_pertama", panggil_provider=jawab,
            konteks=konteks, validasi_konteks=lambda: konteks.versi, sekarang=101,
        )
        chat_b, konteks_b, _ = kedua[0]
        assistant_service.kirim_pesan(
            kon, AKUN, chat_b.id, "Buat usulan latihan kedua.",
            request_id="req_konteks_kedua", panggil_provider=jawab,
            konteks=konteks_b, validasi_konteks=lambda: konteks_b.versi, sekarang=102,
        )
        assert len(provider.panggilan) == 2
        for item, sumber, izin in (pertama, kedua[0]):
            usulan, = assistant_store.daftar_usulan_chat(kon, AKUN, item.id)
            assert usulan.context_version == item.context_version == izin.versi
            assert usulan.context_resource_version == sumber.versi
            operasi = kon.execute(
                "SELECT * FROM operasi WHERE request_id = ?",
                (usulan.sumber_request_id,),
            ).fetchone()
            assert operasi["context_version"] == izin.versi
            assert operasi["chat_id"] == item.id
            assert operasi["status"] == "selesai"
            assert len(assistant_store.daftar_pesan(kon, AKUN, item.id)) == 2


@pytest.mark.parametrize("rusak", ["tanpa", "lain", "jenis", "versi", "kategori", "izin", "validator"])
def test_service_konteks_harus_terikat_chat_sebelum_network(privat, rusak):
    with assistant_schema.buka(privat) as kon:
        _izin_provider(kon)
        chat, konteks, izin = _chat_konteks(kon)
        validator = lambda: konteks.versi
        if rusak == "tanpa":
            konteks = None
        elif rusak == "lain":
            _, konteks, _ = _chat_konteks(kon, "2")
        elif rusak == "jenis":
            konteks = replace(konteks, jenis="sesi")
        elif rusak == "versi":
            konteks = replace(konteks, versi="v2")
        elif rusak == "kategori":
            konteks = replace(konteks, kategori="soal_resmi")
        elif rusak == "izin":
            assistant_store.cabut_persetujuan_konteks(
                kon, AKUN, izin.id, versi_diharapkan=izin.versi, sekarang=101,
            )
        else:
            validator = None
        kon.commit()
        sebelum = kon.total_changes
        provider = ProviderPalsu()
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Jelaskan sumber ini.", request_id="req_sumber_salah",
                konteks=konteks, validasi_konteks=validator,
                panggil_provider=provider, sekarang=102,
            )
        assert provider.panggilan == []
        assert kon.total_changes == sebelum
        assert kon.execute("SELECT COUNT(*) FROM operasi").fetchone()[0] == 0


@pytest.mark.parametrize("perubahan", ["cabut", "ganti", "resource", "kategori"])
def test_service_konteks_sendiri_berubah_saat_network_ditolak(privat, perubahan):
    with assistant_schema.buka(privat) as kon:
        _izin_provider(kon)
        chat, konteks, izin = _chat_konteks(kon)
        _chat_konteks(kon, "2")  # Versi global lebih tinggi: jangan bergantung MAX.
        kon.commit()
        versi = [konteks.versi]

        def ubah(_pesan):
            assert not kon.in_transaction
            with assistant_schema.buka(privat) as lain:
                if perubahan == "cabut":
                    assistant_store.cabut_persetujuan_konteks(
                        lain, AKUN, izin.id, versi_diharapkan=izin.versi, sekarang=102,
                    )
                elif perubahan in ("ganti", "kategori"):
                    assistant_store.beri_persetujuan_konteks(
                        lain, AKUN, jenis=konteks.jenis, resource_id=konteks.resource_id,
                        resource_version=konteks.versi,
                        kategori="soal_resmi" if perubahan == "kategori" else konteks.kategori,
                        sekarang=102,
                    )
                else:
                    versi[0] = "v2"
            return ProviderPalsu().respons

        with pytest.raises(assistant_service.GalatPendamping, match="berubah"):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Jelaskan sumber ini.", request_id="req_sumber_berubah",
                konteks=konteks, validasi_konteks=lambda: versi[0],
                panggil_provider=ubah, sekarang=101,
            )
        assert assistant_store.daftar_pesan(kon, AKUN, chat.id) == ()
        assert assistant_store.daftar_usulan_chat(kon, AKUN, chat.id) == ()
        assert kon.execute("SELECT status FROM operasi").fetchone()[0] == "gagal"


@pytest.mark.parametrize("perubahan", ["cabut", "ganti", "resource", "lain", "tanpa"])
def test_retry_konteks_usang_tidak_replay(privat, perubahan):
    with assistant_schema.buka(privat) as kon:
        _izin_provider(kon)
        chat, konteks, izin = _chat_konteks(kon)
        provider = ProviderPalsu()
        versi = [konteks.versi]

        def kirim():
            return assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Jelaskan sumber ini.", request_id="req_retry_konteks",
                konteks=konteks, validasi_konteks=lambda: versi[0],
                panggil_provider=provider, sekarang=101,
            )

        hasil = kirim()
        assert kirim() == hasil
        if perubahan == "cabut":
            assistant_store.cabut_persetujuan_konteks(
                kon, AKUN, izin.id, versi_diharapkan=izin.versi, sekarang=102,
            )
        elif perubahan == "ganti":
            _chat_konteks(kon)
        elif perubahan == "resource":
            versi[0] = "v2"
        elif perubahan == "lain":
            _, konteks, _ = _chat_konteks(kon, "2")
        else:
            konteks = None
        kon.commit()
        sebelum = kon.total_changes
        with pytest.raises(assistant_service.GalatPendamping):
            kirim()
        assert kon.total_changes == sebelum
        assert len(provider.panggilan) == 1
        assert len(assistant_store.daftar_pesan(kon, AKUN, chat.id)) == 2


def test_validasi_consent_dan_finalisasi_memegang_lock_yang_sama(privat, monkeypatch):
    with assistant_schema.buka(privat) as kon:
        _izin_provider(kon)
        chat, konteks, _ = _chat_konteks(kon)
        kon.commit()
        asli = assistant_store.persetujuan_konteks_aktif
        cek = []

        def periksa(*args, **kwargs):
            assert kon.in_transaction, "validasi consent harus atomik dengan reservasi/finalisasi"
            with sqlite3.connect(privat, timeout=0) as lain:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    lain.execute("UPDATE persetujuan_konteks SET dicabut = 102")
            cek.append(True)
            return asli(*args, **kwargs)

        monkeypatch.setattr(assistant_store, "persetujuan_konteks_aktif", periksa)
        assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Jelaskan sumber ini.", request_id="req_lock_konteks",
            konteks=konteks, validasi_konteks=lambda: konteks.versi,
            panggil_provider=ProviderPalsu(), sekarang=101,
        )
        # Pre-admission, revalidasi sesudah reserve lintas DB, dan finalisasi.
        assert len(cek) == 3
