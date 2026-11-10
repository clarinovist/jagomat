"""Versi kebijakan persetujuan Pendamping: izin versi lama tidak lagi berlaku."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_http  # noqa: E402
import assistant_policy  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import assistant_view  # noqa: E402
import auth  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402


AKUN = "akun_" + "a" * 32
VERSI_LAMA = "pendamping-privasi-v1"
VERSI_BARU = "pendamping-privasi-v2"
ORIGIN_SAMA = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def privat(tmp_path):
    path = tmp_path / "pendamping-sintetis.db"
    assistant_schema.siapkan(path)
    kon = assistant_schema.buka(path)
    yield kon
    kon.close()


def _beri_izin(kon, versi, sekarang):
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=versi,
        provider_id=assistant_policy.PROVIDER_ID,
        kategori="chat_umum", sekarang=sekarang,
    )
    kon.commit()


def test_versi_kebijakan_saat_ini_adalah_v2():
    assert assistant_policy.VERSI_KEBIJAKAN == VERSI_BARU


def test_izin_versi_lama_tidak_dianggap_aktif(privat):
    _beri_izin(privat, VERSI_LAMA, 1)

    assert assistant_http._consent(privat, AKUN) is False


def test_izin_versi_baru_dianggap_aktif(privat):
    _beri_izin(privat, VERSI_BARU, 1)

    assert assistant_http._consent(privat, AKUN) is True


def test_izin_ulang_v2_menggantikan_izin_v1(privat):
    _beri_izin(privat, VERSI_LAMA, 1)
    _beri_izin(privat, VERSI_BARU, 2)

    assert assistant_http._consent(privat, AKUN) is True


def test_chat_lama_tidak_bisa_dibaca_dengan_izin_versi_lama(privat):
    chat = assistant_store.buat_chat(privat, AKUN, "tanpa_memori", sekarang=1)
    privat.commit()
    _beri_izin(privat, VERSI_LAMA, 2)
    assert assistant_view.hak_baca_chat(privat, AKUN, chat, pemilik="ortu-sintetis") is False

    _beri_izin(privat, VERSI_BARU, 3)
    assert assistant_view.hak_baca_chat(privat, AKUN, chat, pemilik="ortu-sintetis") is True


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    monkeypatch.setattr(
        assistant_service, "panggil_provider_default",
        lambda *_: pytest.fail("Provider nyata tidak boleh dipanggil"),
    )
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _akun_guru():
    return auth.cari_akun("guru")


def _token_guru():
    akun = _akun_guru()
    return sessions.buat(
        akun["pengguna"], "guru", id_akun=akun["id_akun"],
        revisi_auth=akun["revisi_auth"],
    )


def _kirim_persetujuan(server, token, versi):
    return server.minta(
        "/pendamping/persetujuan", cookie=token,
        data={"setuju": "1", "kebijakan": versi},
        headers={"Origin": server.alamat, **ORIGIN_SAMA},
    )


def test_http_pengguna_izin_v1_diminta_persetujuan_ulang_dan_tersimpan_v2(server):
    token = _token_guru()
    id_akun = _akun_guru()["id_akun"]
    assistant_schema.siapkan(assistant_schema.BAWAAN)
    with assistant_schema.buka() as kon:
        assistant_store.beri_persetujuan(
            kon, id_akun, policy_version=VERSI_LAMA,
            provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum", sekarang=1,
        )
        kon.commit()

    kode, isi, _ = server.minta("/pendamping/tidak-dikenal", cookie=token)
    assert kode == 200
    assert 'action="/pendamping/persetujuan"' in isi
    assert f'value="{VERSI_BARU}"' in isi

    kode_lama, _, _ = _kirim_persetujuan(server, token, VERSI_LAMA)
    assert kode_lama == 400

    kode_baru, _, _ = _kirim_persetujuan(server, token, VERSI_BARU)
    assert kode_baru == 200  # klien uji mengikuti redirect ke /pendamping
    with assistant_schema.buka() as kon:
        terbaru = kon.execute(
            "SELECT policy_version FROM persetujuan WHERE account_id=? "
            "AND kategori='chat_umum' ORDER BY versi DESC, rowid DESC LIMIT 1",
            (id_akun,),
        ).fetchone()
    assert terbaru["policy_version"] == VERSI_BARU

    kode_setelah, isi_setelah, _ = server.minta("/pendamping/tidak-dikenal", cookie=token)
    assert kode_setelah == 404
    assert 'action="/pendamping/persetujuan"' not in isi_setelah
