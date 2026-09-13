"""Memori lintas chat harus eksplisit, terbatas, dan dikendalikan orang tua."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_policy  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import auth  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402
from test_assistant_runtime import ProviderPalsu, _consent, _token_guru  # noqa: E402

AKUN = "akun_" + "a" * 32


@pytest.fixture()
def kon(tmp_path):
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as koneksi:
        yield koneksi


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    palsu = ProviderPalsu(respons={
        "jawaban": "Baik, saya akan menjawab lebih ringkas.",
        "draft_memori": {
            "lingkup": "preferensi_orang_tua",
            "isi": "Jelaskan secara ringkas dengan satu contoh konkret.",
        },
        "usulan_latihan": None,
        "butuh_klarifikasi": False,
    })
    monkeypatch.setattr(assistant_service, "panggil_provider_default", palsu)
    s = ServerUji(tmp_path, monkeypatch)
    s.provider = palsu
    yield s
    s.berhenti()


def test_policy_draft_hanya_preferensi_orang_tua():
    draft = assistant_policy.validasi_draft_memori({
        "lingkup": "preferensi_orang_tua",
        "isi": "Jelaskan secara ringkas dan gunakan satu contoh konkret.",
    })
    assert draft.lingkup == "preferensi_orang_tua"
    for rusak in (
        {"lingkup": "profil_anak", "isi": "Simpan ini."},
        {"lingkup": "preferensi_orang_tua", "isi": "Anak saya malas."},
        {"lingkup": "preferensi_orang_tua", "isi": "Hubungi orang@example.test"},
        {"lingkup": "preferensi_orang_tua", "isi": "<b>Jawab singkat</b>"},
    ):
        with pytest.raises(ValueError):
            assistant_policy.validasi_draft_memori(rusak)


def test_draft_tidak_aktif_sebelum_konfirmasi(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id="deepseek", kategori="chat_umum", sekarang=100,
    )
    assistant_store.atur_penggunaan_memori(
        kon, AKUN, True, versi_diharapkan=0, sekarang=100
    )
    chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
    provider = ProviderPalsu(respons={
        "jawaban": "Baik.",
        "draft_memori": {
            "lingkup": "preferensi_orang_tua",
            "isi": "Gunakan kalimat pendek.",
        },
        "usulan_latihan": None,
        "butuh_klarifikasi": False,
    })
    assistant_service.kirim_pesan(
        kon, AKUN, chat.id, "Tolong jawab lebih pendek.",
        request_id="req_draft_memori", panggil_provider=provider, sekarang=101,
    )
    daftar = assistant_store.daftar_memori(kon, AKUN)
    assert len(daftar) == 1
    assert not daftar[0].dikonfirmasi
    assert assistant_store.memori_untuk_chat(kon, AKUN, chat.id) == ()


def test_memori_nonaktif_tidak_dibaca_di_service(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id="deepseek", kategori="chat_umum", sekarang=100,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
    assistant_store.tambah_memori(
        kon, AKUN, "Gunakan contoh konkret.", sumber_chat_id=chat.id,
        dikonfirmasi=True, sekarang=100,
    )
    provider = ProviderPalsu(respons={
        "jawaban": "Baik.", "draft_memori": None,
        "usulan_latihan": None, "butuh_klarifikasi": False,
    })
    assistant_service.kirim_pesan(
        kon, AKUN, chat.id, "Halo.", request_id="req_off_memory_read",
        panggil_provider=provider, sekarang=101,
    )
    muatan = json.loads(provider.panggilan[0][1]["content"])
    assert muatan["memori"] == []


def test_memori_nonaktif_tidak_menyimpan_draft(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id="deepseek", kategori="chat_umum", sekarang=100,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
    provider = ProviderPalsu(respons={
        "jawaban": "Baik.",
        "draft_memori": {
            "lingkup": "preferensi_orang_tua", "isi": "Jawab singkat."
        },
        "usulan_latihan": None,
        "butuh_klarifikasi": False,
    })
    with pytest.raises(assistant_service.GalatPendamping, match="nonaktif"):
        assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Jawab singkat.", request_id="req_off_memory",
            panggil_provider=provider, sekarang=101,
        )
    assert assistant_store.daftar_memori(kon, AKUN) == ()
    assert assistant_store.daftar_pesan(kon, AKUN, chat.id) == ()
    assert kon.execute(
        "SELECT status FROM operasi WHERE request_id = 'req_off_memory'"
    ).fetchone()[0] == "gagal"


def test_chat_tanpa_memori_tidak_membaca_memori_di_service(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id="deepseek", kategori="chat_umum", sekarang=100,
    )
    sumber = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
    assistant_store.tambah_memori(
        kon, AKUN, "Gunakan contoh konkret.", sumber_chat_id=sumber.id,
        dikonfirmasi=True, sekarang=100,
    )
    assistant_store.atur_penggunaan_memori(
        kon, AKUN, True,
        versi_diharapkan=assistant_store.versi_memori(kon, AKUN), sekarang=100,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=100)
    provider = ProviderPalsu(respons={
        "jawaban": "Baik.", "draft_memori": None,
        "usulan_latihan": None, "butuh_klarifikasi": False,
    })
    assistant_service.kirim_pesan(
        kon, AKUN, chat.id, "Halo.", request_id="req_no_memory_read",
        panggil_provider=provider, sekarang=101,
    )
    muatan = json.loads(provider.panggilan[0][1]["content"])
    assert muatan["memori"] == []


def test_chat_tanpa_memori_tidak_menyimpan_draft(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id="deepseek", kategori="chat_umum", sekarang=100,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=100)
    provider = ProviderPalsu(respons={
        "jawaban": "Baik.",
        "draft_memori": {
            "lingkup": "preferensi_orang_tua", "isi": "Jawab singkat."
        },
        "usulan_latihan": None,
        "butuh_klarifikasi": False,
    })
    with pytest.raises(assistant_service.GalatPendamping, match="memori nonaktif"):
        assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Jawab singkat.", request_id="req_no_memory",
            panggil_provider=provider, sekarang=101,
        )
    assert assistant_store.daftar_memori(kon, AKUN) == ()
    assert assistant_store.daftar_pesan(kon, AKUN, chat.id) == ()
    assert kon.execute(
        "SELECT status FROM operasi WHERE request_id = 'req_no_memory'"
    ).fetchone()[0] == "gagal"


def test_http_pengaturan_memori_standalone_dialihkan_tanpa_mutasi(server):
    token = _token_guru(server)
    _consent(server, token)
    with assistant_schema.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta("/pendamping/memori", cookie=token)
    assert kode == 200
    assert "Akun &amp; pengaturan" in isi
    assert "Simpan preferensi ini?" not in isi
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum

def test_hapus_semua_memori_hanya_milik_akun_dan_versi_tepat(kon):
    chat_a = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
    akun_b = "akun_" + "b" * 32
    chat_b = assistant_store.buat_chat(kon, akun_b, "aktif", sekarang=100)
    assistant_store.tambah_memori(
        kon, AKUN, "Jawab singkat.", sumber_chat_id=chat_a.id,
        dikonfirmasi=True, sekarang=101,
    )
    assistant_store.tambah_memori(
        kon, akun_b, "Gunakan contoh.", sumber_chat_id=chat_b.id,
        dikonfirmasi=True, sekarang=101,
    )
    versi = assistant_store.versi_memori(kon, AKUN)
    with pytest.raises(ValueError, match="versi memori berubah"):
        assistant_store.hapus_semua_memori(
            kon, AKUN, versi_diharapkan=versi + 1, sekarang=102
        )
    assert assistant_store.hapus_semua_memori(
        kon, AKUN, versi_diharapkan=versi, sekarang=102
    ) == 1
    assert assistant_store.daftar_memori(kon, AKUN) == ()
    assert len(assistant_store.daftar_memori(kon, akun_b)) == 1


def test_http_memori_akun_lain_tidak_bisa_diubah(server):
    token_a = _token_guru(server)
    _consent(server, token_a)
    with assistant_schema.buka() as kon:
        akun_a = auth.cari_akun("guru")["id_akun"]
        chat = assistant_store.buat_chat(kon, akun_a, "aktif", sekarang=100)
        memori = assistant_store.tambah_memori(
            kon, akun_a, "Jawab singkat.", sumber_chat_id=chat.id,
            dikonfirmasi=False, sekarang=101,
        )

    auth.tambah_akun("ortu-b", "sandi-ortu-b-123", "guru")
    akun_b = auth.cari_akun("ortu-b")
    token_b = sessions.buat(
        "ortu-b", "guru", id_akun=akun_b["id_akun"],
        revisi_auth=akun_b["revisi_auth"],
    )
    _consent(server, token_b)
    kode, _, _ = server.minta(
        f"/pendamping/memori/{memori.id}/konfirmasi", cookie=token_b,
        data={"versi": str(memori.versi), "kembali": ""},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 404
    with assistant_schema.buka() as kon:
        tetap = assistant_store.daftar_memori(kon, akun_a)[0]
        assert not tetap.dikonfirmasi
