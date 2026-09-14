"""Retry harus terikat chat asal dan tidak menghasilkan histori hantu."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_client
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
import auth
from test_assistant_runtime import ProviderPalsu, _consent, _token_guru, server

AKUN = "akun_" + "a" * 32


@pytest.fixture()
def privat(tmp_path):
    path = tmp_path / "privat.db"
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum", sekarang=100,
        )
    return path


def _kirim(kon, chat_id, provider, teks="Pertanyaan pertama.", request_id="req_retry_asal"):
    return assistant_service.kirim_pesan(
        kon, AKUN, chat_id, teks, request_id=request_id,
        panggil_provider=provider, sekarang=101,
    )


@pytest.mark.parametrize("tujuan", ["chat_lain", "asing", "hilang", "dihapus", "pesan_lain"])
def test_retry_tidak_mengembalikan_jawaban_chat_lain(privat, tujuan):
    with assistant_schema.buka(privat) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        provider = ProviderPalsu()
        _kirim(kon, chat.id, provider)
        chat_id = chat.id
        teks = "Pertanyaan pertama."
        if tujuan in ("chat_lain", "asing"):
            pemilik = AKUN if tujuan == "chat_lain" else "akun_" + "b" * 32
            chat_id = assistant_store.buat_chat(kon, pemilik, "aktif", sekarang=102).id
        elif tujuan == "hilang":
            chat_id = "chat_" + "f" * 32
        elif tujuan == "dihapus":
            versi = assistant_store.ambil_chat(kon, AKUN, chat.id).versi
            assistant_store.hapus_chat(
                kon, AKUN, chat.id, versi_diharapkan=versi, sekarang=102, retensi_detik=30,
            )
        else:
            teks = "Pertanyaan berbeda."
        kon.commit()
        sebelum = kon.total_changes
        with pytest.raises(assistant_service.GalatPendamping):
            _kirim(kon, chat_id, provider, teks=teks)
        assert kon.total_changes == sebelum
        assert len(provider.panggilan) == 1
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 2


@pytest.mark.parametrize("bagian", ["jawaban", "sumber", "operasi"])
def test_retry_jawaban_terikat_request_dan_chat_yang_sama(privat, bagian):
    with assistant_schema.buka(privat) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        provider = ProviderPalsu()
        _kirim(kon, chat.id, provider)
        lain = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=102)
        # Fault injection sintetis: korelasi request di DB rusak, jangan replay.
        if bagian == "operasi":
            kon.execute(
                "UPDATE operasi SET chat_id = ? WHERE request_id = ?",
                (lain.id, "req_retry_asal"),
            )
        else:
            request_id = "req_retry_asal" + (":jawaban" if bagian == "jawaban" else "")
            kon.execute(
                "UPDATE pesan SET chat_id = ? WHERE request_id = ?",
                (lain.id, request_id),
            )
        kon.commit()
        sebelum = kon.total_changes
        with pytest.raises(assistant_service.GalatPendamping):
            _kirim(kon, chat.id, provider)
        assert kon.total_changes == sebelum
        assert len(provider.panggilan) == 1


def test_retry_identik_tidak_menggandakan_pesan(privat):
    with assistant_schema.buka(privat) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        provider = ProviderPalsu()
        pertama = _kirim(kon, chat.id, provider)
        sebelum = kon.total_changes
        assert _kirim(kon, chat.id, provider) == pertama
        assert kon.total_changes == sebelum
        assert len(provider.panggilan) == 1
        assert len(assistant_store.daftar_pesan(kon, AKUN, chat.id)) == 2


def test_retry_provider_gagal_perlu_request_baru(privat):
    with assistant_schema.buka(privat) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        provider = ProviderPalsu(galat=assistant_client.GalatProvider("gagal sintetis"))
        with pytest.raises(assistant_service.GalatPendamping):
            _kirim(kon, chat.id, provider)
        provider.galat = None
        sebelum = kon.total_changes
        with pytest.raises(assistant_service.GalatPendamping):
            _kirim(kon, chat.id, provider)
        assert len(provider.panggilan) == 1
        assert kon.total_changes == sebelum
        _kirim(kon, chat.id, provider, request_id="req_retry_baru")
        assert len(provider.panggilan) == 2


def _chat_awal(kon, provider, mode="aktif", request_id="req_awal_identik"):
    return assistant_service.mulai_chat_dan_kirim(
        kon, AKUN, mode, "Pertanyaan pertama.", request_id=request_id,
        panggil_provider=provider, sekarang=101,
    )


def test_service_retry_chat_awal_tidak_membuat_histori_hantu(privat):
    with assistant_schema.buka(privat) as kon:
        provider = ProviderPalsu()
        pertama = _chat_awal(kon, provider)
        kedua = _chat_awal(kon, provider)
        assert pertama.id == kedua.id
        assert len(provider.panggilan) == 1
        assert len(assistant_store.daftar_chat(kon, AKUN)) == 1
        assert len(assistant_store.daftar_pesan(kon, AKUN, pertama.id)) == 2
        sebelum = kon.total_changes
        with pytest.raises(assistant_service.GalatPendamping):
            _chat_awal(kon, provider, mode="tanpa_memori")
        assert kon.total_changes == sebelum


@pytest.mark.parametrize("awal", [False, True])
def test_retry_paralel_pending_satu_provider_satu_chat(privat, awal):
    masuk = threading.Event()
    lanjut = threading.Event()
    provider = ProviderPalsu()
    with assistant_schema.buka(privat) as kon:
        chat_id = None if awal else assistant_store.buat_chat(
            kon, AKUN, "aktif", sekarang=100
        ).id

    def lambat(pesan):
        masuk.set()
        assert lanjut.wait(5), "worker kedua tidak menyelesaikan pemeriksaan pending"
        return provider(pesan)

    def panggil(pemanggil):
        with assistant_schema.buka(privat) as kon:
            if awal:
                return _chat_awal(kon, pemanggil)
            return _kirim(kon, chat_id, pemanggil)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pertama = pool.submit(panggil, lambat)
        try:
            assert masuk.wait(5)
            kedua = pool.submit(panggil, provider)
            with pytest.raises(assistant_service.GalatPendamping):
                kedua.result(timeout=5)
        finally:
            lanjut.set()
        pertama.result(timeout=5)
    assert len(provider.panggilan) == 1
    with assistant_schema.buka(privat) as kon:
        assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 2
        assert kon.execute("SELECT COUNT(*) FROM operasi").fetchone()[0] == 1


def test_reservasi_dikunci_sebelum_pemeriksaan_operasi(privat, monkeypatch):
    with assistant_schema.buka(privat) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        kon.commit()
        asli = assistant_store.mulai_operasi

        def periksa(*args, **kwargs):
            assert kon.in_transaction
            with sqlite3.connect(privat, timeout=0) as lain:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    lain.execute("UPDATE operasi SET status = status WHERE 0")
            return asli(*args, **kwargs)

        monkeypatch.setattr(assistant_store, "mulai_operasi", periksa)

        def jawab(pesan):
            assert not kon.in_transaction
            with sqlite3.connect(privat, timeout=0) as lain:
                lain.execute("UPDATE operasi SET status = status WHERE 0")
            return ProviderPalsu()(pesan)

        _kirim(kon, chat.id, jawab)


@pytest.mark.parametrize("perubahan", ["dihapus", "pesan", "lanjutan", "consent"])
def test_chat_awal_retry_tidak_mengubah_identitas(privat, perubahan):
    with assistant_schema.buka(privat) as kon:
        provider = ProviderPalsu()
        chat = _chat_awal(kon, provider)
        teks = "Pertanyaan pertama."
        request_id = "req_awal_identik"
        if perubahan == "dihapus":
            assistant_store.hapus_chat(
                kon, AKUN, chat.id, versi_diharapkan=chat.versi,
                sekarang=102, retensi_detik=30,
            )
        elif perubahan == "pesan":
            teks = "Pertanyaan berbeda."
        elif perubahan == "lanjutan":
            request_id = "req_pesan_lanjutan"
            _kirim(kon, chat.id, provider, request_id=request_id)
        else:
            izin = kon.execute("SELECT * FROM persetujuan").fetchone()
            assistant_store.cabut_persetujuan(
                kon, AKUN, izin["id"], versi_diharapkan=izin["versi"], sekarang=102,
            )
        kon.commit()
        sebelum = tuple(kon.iterdump())
        panggilan = len(provider.panggilan)
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.mulai_chat_dan_kirim(
                kon, AKUN, "aktif", teks, request_id=request_id,
                panggil_provider=provider, sekarang=103,
            )
        assert tuple(kon.iterdump()) == sebelum
        assert len(provider.panggilan) == panggilan
        assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 1


def test_chat_awal_gagal_retry_tidak_menambah_chat(privat):
    with assistant_schema.buka(privat) as kon:
        provider = ProviderPalsu(galat=assistant_client.GalatProvider("gagal sintetis"))
        for _ in range(2):
            with pytest.raises(assistant_service.GalatPendamping):
                _chat_awal(kon, provider)
        assert len(provider.panggilan) == 1
        assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
        assert kon.execute("SELECT status FROM operasi").fetchone()[0] == "gagal"


def test_chat_awal_tanpa_consent_rollback_chat(privat):
    with assistant_schema.buka(privat) as kon:
        kon.execute("DELETE FROM persetujuan")
        kon.commit()
        provider = ProviderPalsu()
        with pytest.raises(assistant_service.GalatPendamping):
            _chat_awal(kon, provider)
        assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM operasi").fetchone()[0] == 0
        assert provider.panggilan == []


def _snapshot_privat():
    # siapkan() HTTP menjalankan PRAGMA user_version; header SQLite bisa berubah
    # tanpa mutasi resource. Bandingkan SELURUH schema/isi, bukan header fisik.
    with assistant_schema.buka() as kon:
        return tuple(kon.iterdump())


def _post(server, token, jalur, data):
    return server.minta(jalur, cookie=token, data=data, headers={
        "Origin": server.alamat, "Sec-Fetch-Site": "same-origin",
    })


def test_http_retry_chat_umum_lama_tidak_membuat_histori_hantu(server):
    token = _token_guru(server)
    _consent(server, token)
    data = {"mode": "aktif", "pesan_awal": "Pertanyaan pertama.", "request_id": "req_awal_http_identik"}
    sebelum = _snapshot_privat()
    pertama = _post(server, token, "/pendamping/chat-baru", data)
    kedua = _post(server, token, "/pendamping/chat-baru", data)
    assert pertama[0] == kedua[0] == 410
    assert pertama[1] == kedua[1]
    assert _snapshot_privat() == sebelum
    assert server.provider.panggilan == []


def test_http_request_chat_umum_lama_tidak_boleh_dipindah(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        chat_a = assistant_store.buat_chat(kon, akun, "aktif", sekarang=1)
        chat_b = assistant_store.buat_chat(kon, akun, "aktif", sekarang=2)
        kon.commit()
    sebelum = _snapshot_privat()
    for chat in (chat_a, chat_b):
        hasil = _post(server, token, f"/pendamping/chat/{chat.id}/pesan", {
            "pesan": "Pertanyaan pertama.", "request_id": "req_awal_http_identik",
        })
        assert hasil[0] == 410
    assert _snapshot_privat() == sebelum
    assert server.provider.panggilan == []
