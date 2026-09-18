"""Regresi bukti tinjauan dan transaksi dua DB; seluruh data sintetis."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
import sqlite3
import threading
from pathlib import Path
import html
import re
import urllib.parse
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_actions
import assistant_context
import assistant_policy
import assistant_schema
import assistant_store
import database
import auth
from test_assistant_actions import (
    USULAN_SAH, _buat_usulan_http, _origin, server,
)


@pytest.fixture()
def kasus(tmp_path, monkeypatch):
    data = tmp_path / "belajar.db"
    privat = tmp_path / "pendamping.db"
    database.siapkan(data)
    assistant_schema.siapkan(privat)
    monkeypatch.setattr(database, "BAWAAN", data)
    monkeypatch.setattr(assistant_schema, "BAWAAN", privat)
    akun = "akun_" + "a" * 32
    with database.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
        sumber = database.buat_sesi_dari_urutan(
            kon, anak, 7, ("deret_aritmetika",), level="P3"
        )
        versi = assistant_context.versi_resource(
            kon, "sesi", str(sumber), pemilik="guru"
        )
    with assistant_schema.buka() as kon:
        assistant_store.beri_persetujuan(
            kon, akun, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum",
            sekarang=100,
        )
        izin = assistant_store.beri_persetujuan_konteks(
            kon, akun, jenis="sesi", resource_id=str(sumber),
            resource_version=versi, kategori="ringkasan_netral", sekarang=100,
        )
        chat = assistant_store.buat_chat(
            kon, akun, "aktif", sekarang=100, context_kind="sesi",
            context_id=str(sumber), context_version=izin.versi,
            context_resource_version=versi, context_category=izin.kategori,
        )
        operasi = assistant_store.mulai_operasi(
            kon, akun, chat.id, "req_sintetis_usulan", consent_version=1,
            memory_version=0, context_version=izin.versi, sekarang=100,
        )
        kon.execute("UPDATE operasi SET status = 'selesai', selesai = 100")
        import json
        sah = assistant_actions.validasi_usulan(USULAN_SAH)
        usulan = assistant_store.simpan_usulan(
            kon, akun, chat.id, operasi.request_id,
            payload_json=json.dumps(sah.ke_dict()),
            hash_usulan=assistant_actions.hash_usulan(sah),
            chat_version=chat.versi, consent_version=1,
            context_version=izin.versi, context_resource_version=versi,
            sekarang=100,
        )
    return {"akun": akun, "anak": anak, "sumber": sumber, "usulan": usulan,
            "chat": chat, "privat": privat, "data": data}


def _tinjau(kasus):
    with assistant_schema.buka() as kon:
        return assistant_actions.tinjau_usulan(
            kon, kasus["akun"], "guru", kasus["usulan"].id, sekarang=101
        )


def _konfirmasi(kasus, token, **ubah):
    parameter = {
        "versi": kasus["usulan"].versi,
        "hash_diharapkan": kasus["usulan"].hash_usulan,
        "request_id": token,
        "sekarang": 102,
    }
    parameter.update(ubah)
    with assistant_schema.buka() as kon:
        return assistant_actions.konfirmasi_dan_buat_sesi(
            kon, kasus["akun"], "guru", kasus["usulan"].id, **parameter
        )


def _jumlah_sesi():
    with database.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]


def test_post_tanpa_review_server_ditolak(server):
    token, _, usulan_id = _buat_usulan_http(server)
    with assistant_schema.buka() as kon:
        usulan = assistant_store.ambil_usulan(
            kon, auth.cari_akun("guru")["id_akun"], usulan_id
        )
    sebelum = _jumlah_sesi()
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi", cookie=token,
        data={"versi": str(usulan.versi), "hash": usulan.hash_usulan,
              "request_id": "aksi_" + "f" * 32}, headers=_origin(server),
    )
    assert kode == 409
    assert _jumlah_sesi() == sebelum


def test_retry_wajib_validasi_owner_sumber_dan_hasil(kasus):
    token = _tinjau(kasus)
    _konfirmasi(kasus, token)
    with database.buka() as kon:
        kon.execute("UPDATE siswa SET pemilik = 'guru-lain' WHERE id = ?",
                    (kasus["anak"],))
    sebelum = _jumlah_sesi()
    with pytest.raises(LookupError):
        _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum


def test_crash_setelah_generator_tidak_meninggalkan_sesi_tanpa_kunci(kasus, monkeypatch):
    token = _tinjau(kasus)
    asli = database.buat_sesi_dari_urutan

    def gagal_setelah_simpan(*args, **kwargs):
        asli(*args, **kwargs)
        raise RuntimeError("crash sintetis setelah generator")

    sebelum = _jumlah_sesi()
    with database.buka() as kon:
        snapshot = tuple(kon.iterdump())
    with monkeypatch.context() as m:
        m.setattr(database, "buat_sesi_dari_urutan", gagal_setelah_simpan)
        with pytest.raises(RuntimeError, match="crash sintetis"):
            _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum
    with database.buka() as kon:
        assert tuple(kon.iterdump()) == snapshot
    _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum + 1


@pytest.mark.parametrize("hapus", [False, True], ids=["batal", "hapus"])
def test_crash_lalu_hasil_batal_hapus_tidak_dibuat_ulang(kasus, monkeypatch, hapus):
    token = _tinjau(kasus)

    def gagal_simpan_hasil(*args, **kwargs):
        raise RuntimeError("crash sintetis setelah commit utama")

    sebelum = _jumlah_sesi()
    with monkeypatch.context() as m:
        m.setattr(assistant_store, "selesaikan_usulan", gagal_simpan_hasil)
        with pytest.raises(RuntimeError, match="crash sintetis"):
            _konfirmasi(kasus, token)
    with database.buka() as kon:
        sesi_id = kon.execute("SELECT MAX(id) FROM sesi").fetchone()[0]
        assert sesi_id != kasus["sumber"]
        if hapus:
            assert database.hapus_sesi(kon, sesi_id)
        else:
            database.batalkan_sesi(kon, sesi_id)
    jumlah = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kasus, token)
    assert _jumlah_sesi() == jumlah == sebelum + (not hapus)


def _ambil_hasil(kasus):
    with assistant_schema.buka() as kon:
        return assistant_actions.ambil_hasil_usulan(
            kon, kasus["akun"], "guru", kasus["usulan"].id
        )


def test_tinjau_hanya_metadata_hashed_dan_token_lama_tidak_berlaku(kasus):
    with database.buka() as kon:
        sebelum = tuple(kon.iterdump())
    with assistant_schema.buka() as kon:
        privat_sebelum = tuple(kon.iterdump())
    lama = _tinjau(kasus)
    baru = _tinjau(kasus)
    assert lama != baru
    with database.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    with assistant_schema.buka() as kon:
        baris = kon.execute("SELECT * FROM tinjauan_usulan").fetchall()
        assert len(baris) == 1
        assert baris[0]["token_hash"] == hashlib.sha256(baru.encode()).hexdigest()
        dump = tuple(kon.iterdump())
        assert baru not in "\n".join(dump)
        assert tuple(b for b in dump if not b.startswith('INSERT INTO "tinjauan_usulan"')) == privat_sebelum
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kasus, lama)
    _konfirmasi(kasus, baru)


@pytest.mark.parametrize("waktu", [100, 1901, 3000])
def test_review_di_luar_masa_berlaku_ditolak(kasus, waktu):
    token = _tinjau(kasus)
    sebelum = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan, match="kedaluwarsa"):
        _konfirmasi(kasus, token, sekarang=waktu)
    assert _jumlah_sesi() == sebelum


@pytest.mark.parametrize("kolom,nilai", [
    ("payload_json", json.dumps({**USULAN_SAH, "jumlah_soal": 15})),
    ("hash_usulan", "f" * 64), ("versi", 2), ("chat_version", 2),
    ("context_version", 2), ("context_resource_version", "f" * 64),
    ("consent_version", 2),
])
def test_snapshot_review_berubah_tidak_dapat_disahkan_form(kasus, kolom, nilai):
    token = _tinjau(kasus)
    with assistant_schema.buka() as kon:
        kon.execute(f"UPDATE usulan_latihan SET {kolom} = ? WHERE id = ?",
                    (nilai, kasus["usulan"].id))
        catatan = assistant_store.ambil_usulan(kon, kasus["akun"], kasus["usulan"].id)
    sebelum = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kasus, token, versi=catatan.versi,
                    hash_diharapkan=catatan.hash_usulan)
    assert _jumlah_sesi() == sebelum


@pytest.mark.parametrize("perubahan", ["consent", "konteks", "chat", "hapus_chat"])
@pytest.mark.parametrize("sudah", [False, True], ids=["baru", "retry"])
def test_izin_diperiksa_sebelum_eksekusi_dan_retry(kasus, perubahan, sudah):
    token = _tinjau(kasus)
    if sudah:
        _konfirmasi(kasus, token)
    with assistant_schema.buka() as kon:
        if perubahan == "consent":
            kon.execute("UPDATE persetujuan SET dicabut = 103, versi = versi + 1")
        elif perubahan == "konteks":
            kon.execute("UPDATE persetujuan_konteks SET dicabut = 103, versi = versi + 1")
        elif perubahan == "chat":
            kon.execute("UPDATE chat SET versi = versi + 1")
        else:
            assistant_store.hapus_chat(
                kon, kasus["akun"], kasus["chat"].id,
                versi_diharapkan=kasus["chat"].versi, sekarang=103, retensi_detik=0,
            )
    galat = LookupError if perubahan == "hapus_chat" else assistant_actions.GalatTindakan
    sebelum = _jumlah_sesi()
    with pytest.raises(galat):
        _konfirmasi(kasus, token)
    with pytest.raises(galat):
        _ambil_hasil(kasus)
    assert _jumlah_sesi() == sebelum


@pytest.mark.parametrize("perubahan", ["selesai", "batal"])
def test_sumber_usang_tidak_disahkan_refresh_review(kasus, perubahan):
    token = _tinjau(kasus)
    with database.buka() as kon:
        kolom = "selesai" if perubahan == "selesai" else "dibatalkan"
        kon.execute(f"UPDATE sesi SET {kolom} = '2026-09-11' WHERE id = ?",
                    (kasus["sumber"],))
    sebelum = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kasus, token)
    with pytest.raises(assistant_actions.GalatTindakan):
        _tinjau(kasus)
    assert _jumlah_sesi() == sebelum


def test_token_tidak_dapat_dipakai_usulan_lain(kasus):
    token = _tinjau(kasus)
    with assistant_schema.buka() as kon:
        kon.execute("""INSERT INTO operasi SELECT 'req_lain', chat_id, account_id,
            status, chat_version, consent_version, memory_version, context_version,
            dibuat, selesai FROM operasi LIMIT 1""")
        asal = kasus["usulan"]
        lain = assistant_store.simpan_usulan(
            kon, kasus["akun"], kasus["chat"].id, "req_lain",
            payload_json=asal.payload_json, hash_usulan=asal.hash_usulan,
            chat_version=asal.chat_version, consent_version=asal.consent_version,
            context_version=asal.context_version,
            context_resource_version=asal.context_resource_version, sekarang=100,
        )
    kedua = {**kasus, "usulan": lain}
    token_kedua = _tinjau(kedua)
    sebelum = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kedua, token)
    assert _jumlah_sesi() == sebelum
    _konfirmasi(kedua, token_kedua)


@pytest.mark.parametrize("pemilik_lain", ["guru", "guru-lain"])
def test_owner_hasil_diperiksa_terpisah_dari_sumber(kasus, pemilik_lain):
    token = _tinjau(kasus)
    hasil = _konfirmasi(kasus, token)
    with database.buka() as kon:
        anak_lain = database.tambah_siswa(kon, "Anak Lain", "P3", pemilik=pemilik_lain)
        kon.execute("UPDATE sesi SET siswa_id = ? WHERE id = ?", (anak_lain, hasil))
    sebelum = _jumlah_sesi()
    with pytest.raises(LookupError):
        _konfirmasi(kasus, token)
    with pytest.raises(LookupError):
        _ambil_hasil(kasus)
    assert _jumlah_sesi() == sebelum


def test_payload_valid_berubah_tetap_memerlukan_review_baru(kasus):
    token = _tinjau(kasus)
    with assistant_schema.buka() as kon:
        kon.execute("UPDATE usulan_latihan SET payload_json = payload_json || ' '")
    sebelum = _jumlah_sesi()
    with pytest.raises(assistant_actions.GalatTindakan, match="Tinjauan"):
        _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum


def test_lookup_hasil_menolak_ikatan_payload_berubah(kasus):
    token = _tinjau(kasus)
    _konfirmasi(kasus, token)
    with assistant_schema.buka() as kon:
        # Payload tetap valid dan hash kanonis sama; snapshot teks berubah.
        kon.execute("UPDATE usulan_latihan SET payload_json = payload_json || ' '")
    with pytest.raises(assistant_actions.GalatTindakan):
        _ambil_hasil(kasus)


def test_crash_commit_utama_dipulihkan_dengan_token_yang_sama(kasus, monkeypatch):
    token = _tinjau(kasus)
    sebelum = _jumlah_sesi()
    with monkeypatch.context() as m:
        m.setattr(assistant_store, "selesaikan_usulan", lambda *a, **k: False)
        with pytest.raises(assistant_actions.GalatTindakan, match="disimpan"):
            _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum + 1
    hasil = _ambil_hasil(kasus)
    assert hasil is not None
    assert _konfirmasi(kasus, token, sekarang=9000) == hasil
    assert _jumlah_sesi() == sebelum + 1
    with assistant_schema.buka() as kon:
        assert assistant_store.ambil_usulan(kon, kasus["akun"], kasus["usulan"].id).sesi_id == hasil


@pytest.mark.parametrize("privat_terpisah", [False, True], ids=["satu-db-privat", "salinan-db-privat"])
def test_race_koneksi_terpisah_maksimum_satu_sesi(kasus, privat_terpisah):
    token = _tinjau(kasus)
    path_kedua = kasus["privat"]
    if privat_terpisah:
        path_kedua = kasus["privat"].with_name("pendamping-kedua.db")
        shutil.copy2(kasus["privat"], path_kedua)
    mulai = threading.Barrier(2)

    def jalankan(path):
        with assistant_schema.buka(path) as kon:
            mulai.wait(timeout=5)
            return assistant_actions.konfirmasi_dan_buat_sesi(
                kon, kasus["akun"], "guru", kasus["usulan"].id,
                versi=kasus["usulan"].versi, hash_diharapkan=kasus["usulan"].hash_usulan,
                request_id=token, sekarang=102,
            )

    sebelum = _jumlah_sesi()
    with ThreadPoolExecutor(max_workers=2) as pool:
        pekerjaan = [pool.submit(jalankan, p) for p in (kasus["privat"], path_kedua)]
        hasil = [p.result(timeout=10) for p in pekerjaan]
    assert hasil[0] == hasil[1]
    assert _jumlah_sesi() == sebelum + 1
    with database.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM eksekusi_pendamping").fetchone()[0] == 1


def test_dua_snapshot_privat_token_berbeda_tidak_mengklaim_hasil_pemenang(kasus):
    token = _tinjau(kasus)
    salinan = kasus["privat"].with_name("snapshot-privat.db")
    shutil.copy2(kasus["privat"], salinan)
    with assistant_schema.buka(salinan) as kon:
        token_lain = assistant_actions.tinjau_usulan(
            kon, kasus["akun"], "guru", kasus["usulan"].id, sekarang=101
        )
    hasil = _konfirmasi(kasus, token)
    sebelum = _jumlah_sesi()
    with assistant_schema.buka(salinan) as kon:
        with pytest.raises(assistant_actions.GalatTindakan, match="eksekusi tersimpan"):
            assistant_actions.konfirmasi_dan_buat_sesi(
                kon, kasus["akun"], "guru", kasus["usulan"].id,
                versi=kasus["usulan"].versi, hash_diharapkan=kasus["usulan"].hash_usulan,
                request_id=token_lain, sekarang=102,
            )
    assert _jumlah_sesi() == sebelum
    assert _konfirmasi(kasus, token) == hasil


@pytest.mark.parametrize("sudah", [False, True], ids=["baru", "retry"])
def test_sumber_hilang_404_tanpa_eksekusi(kasus, sudah):
    token = _tinjau(kasus)
    if sudah:
        _konfirmasi(kasus, token)
    with database.buka() as kon:
        assert database.hapus_sesi(kon, kasus["sumber"])
    sebelum = _jumlah_sesi()
    with pytest.raises(LookupError):
        _konfirmasi(kasus, token)
    with pytest.raises(LookupError):
        _ambil_hasil(kasus)
    assert _jumlah_sesi() == sebelum


@pytest.mark.parametrize("status", ["aktif", "batal", "hapus"])
def test_hasil_legacy_tetap_diperiksa_dan_tidak_digenerasi_ulang(kasus, status):
    token = _tinjau(kasus)
    hasil = _konfirmasi(kasus, token)
    with database.buka() as kon:
        kon.execute("DELETE FROM eksekusi_pendamping")
        if status == "batal":
            database.batalkan_sesi(kon, hasil)
        elif status == "hapus":
            assert database.hapus_sesi(kon, hasil)
    with assistant_schema.buka() as kon:
        kon.execute("DELETE FROM tinjauan_usulan")
    sebelum = _jumlah_sesi()
    if status == "aktif":
        assert _ambil_hasil(kasus) == hasil
    else:
        with pytest.raises(assistant_actions.GalatTindakan):
            _ambil_hasil(kasus)
    with pytest.raises(assistant_actions.GalatTindakan):
        _konfirmasi(kasus, token)
    assert _jumlah_sesi() == sebelum


def test_gagal_insert_ledger_me_rollback_sesi_kunci_dan_bank_soal(kasus):
    token = _tinjau(kasus)
    with database.buka() as kon:
        kon.execute("""CREATE TRIGGER gagal_ledger BEFORE INSERT ON eksekusi_pendamping
            BEGIN SELECT RAISE(ABORT, 'gagal ledger sintetis'); END""")
        snapshot = tuple(kon.iterdump())
    with pytest.raises(sqlite3.IntegrityError, match="gagal ledger sintetis"):
        _konfirmasi(kasus, token)
    with database.buka() as kon:
        assert tuple(kon.iterdump()) == snapshot
        kon.execute("DROP TRIGGER gagal_ledger")
    assert _ambil_hasil(kasus) is None
    assert _konfirmasi(kasus, token) is not None


def test_transaksi_pemanggil_tidak_di_commit_diam_diam(kasus):
    with assistant_schema.buka() as kon:
        kon.execute("UPDATE chat SET diperbarui = 999")
        with pytest.raises(assistant_actions.GalatTindakan, match="transaksi"):
            assistant_actions.tinjau_usulan(
                kon, kasus["akun"], "guru", kasus["usulan"].id, sekarang=101
            )
        assert kon.in_transaction
        kon.rollback()
        assert kon.execute("SELECT diperbarui FROM chat").fetchone()[0] == 100


def test_migrasi_additive_dua_kali_dan_purge_mempertahankan_ledger(kasus):
    # Simulasikan skema privat versi 3 dan utama sebelum ledger, tetap berisi data.
    with assistant_schema.buka() as kon:
        kon.execute("DROP TABLE tinjauan_usulan")
        kon.execute("DELETE FROM migrasi_pendamping WHERE versi > 3")
        kon.execute("PRAGMA user_version = 3")
    with database.buka() as kon:
        kon.execute("DROP TABLE eksekusi_pendamping")
        sebelum = tuple(kon.iterdump())
    for _ in range(2):
        assistant_schema.siapkan(kasus["privat"])
        database.siapkan(kasus["data"])
    with database.buka() as kon:
        assert all(b in tuple(kon.iterdump()) for b in sebelum)
    token = _tinjau(kasus)
    _konfirmasi(kasus, token)
    with assistant_schema.buka() as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 4
        assert kon.execute("SELECT COUNT(*) FROM migrasi_pendamping").fetchone()[0] == 4
        assert assistant_store.hapus_chat(
            kon, kasus["akun"], kasus["chat"].id,
            versi_diharapkan=kasus["chat"].versi, sekarang=103, retensi_detik=0,
        )
        assistant_store.purge(kon, sekarang=104)
        assert kon.execute("SELECT COUNT(*) FROM tinjauan_usulan").fetchone()[0] == 0
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with database.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM eksekusi_pendamping").fetchone()[0] == 1
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(LookupError):
        _konfirmasi(kasus, token)


def test_sesi_manual_tidak_menulis_bukti_atau_mengubah_rekomendasi(kasus):
    import learning_cycle

    def snapshot():
        with database.buka() as kon:
            hitung = tuple(kon.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                           for t in ("kejadian_belajar", "bukti_fokus", "putaran_fokus",
                                     "konfirmasi_hasil", "snapshot_outcome"))
            rencana = learning_cycle.rencana_berikutnya(
                database.muat_bukti_siklus(kon, kasus["anak"]), kasus["anak"]
            )
            return hitung, rencana

    sebelum = snapshot()
    hasil = _konfirmasi(kasus, _tinjau(kasus))
    assert snapshot() == sebelum
    with database.buka() as kon:
        sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (hasil,)).fetchone()
        assert sesi["tujuan"] == "bebas"
        assert all(sesi[k] is None for k in (
            "putaran_id", "bagian_checkpoint", "dikonfirmasi_guru", "kunci_idempotensi"
        ))


def _form_review(server, cookie, usulan_id):
    kode, isi, _ = server.minta(f"/pendamping/usulan/{usulan_id}", cookie=cookie)
    assert kode == 200
    cocok = re.search(
        r'name="data_aksi" value="([^"]+)"[^>]+formaction="/pendamping/inline/konfirmasi-usulan"',
        isi,
    )
    if cocok:
        data = dict(urllib.parse.parse_qsl(html.unescape(cocok.group(1))))
        return {
            "versi": data["versi_usulan"], "hash": data["hash_usulan"],
            "request_id": data["request_id"],
        }
    nama_baru = {
        "versi": "versi_usulan", "hash": "hash_usulan",
        "request_id": "request_id",
    }
    return {
        lama: re.search(
            r'name="' + baru + r'" value="([^"]+)"', isi
        ).group(1)
        for lama, baru in nama_baru.items()
    }


def test_http_get_hasil_tetap_tersedia_setelah_snapshot_anak_usang(server):
    cookie, _, usulan_id = _buat_usulan_http(server)
    form = _form_review(server, cookie, usulan_id)
    sebelum = _jumlah_sesi()
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi", cookie=cookie,
        data=form, headers=_origin(server),
    )
    assert kode == 200
    kode, isi, _ = server.minta(f"/pendamping/usulan/{usulan_id}", cookie=cookie)
    assert kode == 200
    assert 'Latihan bebas #' in isi and 'sudah dibuat.' in isi
    assert 'Buka latihan</a>' in isi
    assert _jumlah_sesi() == sebelum + 1


@pytest.mark.parametrize("hapus", [False, True], ids=["batal", "hapus"])
def test_http_hasil_terminal_tidak_dibuat_ulang(server, hapus):
    cookie, _, usulan_id = _buat_usulan_http(server)
    form = _form_review(server, cookie, usulan_id)
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi", cookie=cookie,
        data=form, headers=_origin(server),
    )
    assert kode == 200
    with database.buka() as kon:
        hasil = kon.execute("SELECT MAX(id) FROM sesi").fetchone()[0]
        if hapus:
            assert database.hapus_sesi(kon, hasil)
        else:
            database.batalkan_sesi(kon, hasil)
    sebelum = _jumlah_sesi()
    assert server.minta(f"/pendamping/usulan/{usulan_id}", cookie=cookie)[0] in (404, 409)
    assert server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi", cookie=cookie,
        data=form, headers=_origin(server),
    )[0] == 409
    assert _jumlah_sesi() == sebelum


def test_http_retry_owner_asing_404_identik_dengan_hilang(server):
    cookie, _, usulan_id = _buat_usulan_http(server)
    form = _form_review(server, cookie, usulan_id)
    assert server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi", cookie=cookie,
        data=form, headers=_origin(server),
    )[0] == 200
    with database.buka() as kon:
        kon.execute("UPDATE siswa SET pemilik = 'guru-lain' WHERE id = ?", (server.anak,))
    sebelum = _jumlah_sesi()
    for post in (False, True):
        suffix = "/konfirmasi" if post else ""
        parameter = {"data": form, "headers": _origin(server)} if post else {}
        asing = server.minta(f"/pendamping/usulan/{usulan_id}{suffix}", cookie=cookie, **parameter)
        hilang = server.minta("/pendamping/usulan/usulan_" + "f" * 32 + suffix,
                             cookie=cookie, **parameter)
        assert asing[0] == hilang[0] == 404
        assert asing[1] == hilang[1]
    assert _jumlah_sesi() == sebelum
