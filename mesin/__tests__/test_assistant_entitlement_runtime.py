"""Integrasi runtime/UI entitlement Pendamping tanpa provider atau data keluarga nyata."""
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import admin_store
import assistant_components
import assistant_entitlement_runtime as runtime
import assistant_http
import assistant_inline
import assistant_service
import subscription as d
import subscription_package_schema
import subscription_package_store
import subscription_packages
import subscription_store
from test_assistant_inline_http import server

AKUN = "akun_" + "a" * 32
ON = d.Sakelar(True, True, True, True)


def _admin8(path, *, mulai=1):
    admin_store.siapkan(path, sekarang=mulai)
    subscription_store.enroll(
        path, AKUN, sumber_id="enroll_sintetis", asal="transisi", mulai=mulai,
        peran="guru", sakelar=ON,
    )
    admin_store.siapkan(path, paket_v2=True, sekarang=mulai)
    subscription_package_store.adopsi(
        path, AKUN, operasi_id="adopsi_sintetis", sekarang=mulai,
        peserta_promo=False, sakelar=ON,
    )


def test_sakelar_default_off_tidak_membuat_db_dan_mempertahankan_runtime_lama(tmp_path, monkeypatch):
    path = tmp_path / "belum-ada.db"
    monkeypatch.setattr(admin_store, "BAWAAN", path)
    monkeypatch.delenv("PENDAMPING_ENTITLEMENT_AKTIF", raising=False)
    assert runtime.status(AKUN, sekarang=10).enforcement_aktif is False
    assert runtime.boleh_outbound(AKUN, sekarang=10) is True
    assert not path.exists()


def test_enforcement_on_storage_absen_fail_closed_tanpa_membuat_db(tmp_path, monkeypatch):
    path = tmp_path / "absen.db"
    monkeypatch.setattr(admin_store, "BAWAAN", path)
    monkeypatch.setenv("PENDAMPING_ENTITLEMENT_AKTIF", "1")
    state = runtime.status(AKUN, sekarang=10)
    assert state.status == "storage_tidak_terverifikasi"
    assert runtime.boleh_outbound(AKUN, sekarang=10) is False
    assert not path.exists()


def test_jago_terkunci_dan_panel_tidak_memuat_context():
    state = runtime.StatusRuntime(
        "jago_tanpa_ai", paket="jago", enforcement_aktif=True,
    )
    panel = assistant_components.panel_akses(
        assistant_inline.tujuan_anak(7, "latihan"), state, dalam_form=False,
    )
    assert "Pendamping tersedia di Jago Pro" in panel
    assert "Latihan dan rencana belajar tetap dapat digunakan" in panel
    assert "Lihat paket" in panel
    assert "data-pendamping-resource-id" not in panel
    assert "inline_host_id" not in panel


def test_pemicu_akses_memiliki_label_dan_lencana_bukan_disabled():
    state = runtime.StatusRuntime(
        "jago_tanpa_ai", paket="jago", enforcement_aktif=True,
    )
    markup = assistant_components.tombol_buka(
        assistant_inline.tujuan_anak(7), dalam_form=True, status_akses=state,
    )
    assert 'aria-label="Pendamping — tersedia di Jago Pro"' in markup
    assert 'class="pendamping-lencana-akses"' in markup
    assert "disabled" not in markup


def test_kirim_ditolak_tidak_meninggalkan_operasi(monkeypatch, tmp_path):
    import assistant_schema
    import assistant_store
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version="pendamping-privasi-v1",
            provider_id="deepseek", kategori="chat_umum", sekarang=1,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=1)
        kon.commit()
        monkeypatch.setenv("PENDAMPING_ENTITLEMENT_AKTIF", "1")
        monkeypatch.setattr(runtime, "boleh_outbound", lambda *_a, **_k: False)
        provider = []
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Pesan sintetis.", request_id="req_entitlement01",
                panggil_provider=lambda *_: provider.append(1), sekarang=2,
            )
        assert kon.execute("SELECT COUNT(*) FROM operasi").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
        assert provider == []


def test_service_menahan_provider_saat_entitlement_tidak_sah(monkeypatch):
    monkeypatch.setenv("PENDAMPING_ENTITLEMENT_AKTIF", "1")
    monkeypatch.setattr(runtime, "boleh_outbound", lambda *_a, **_k: False)
    dipanggil = []
    with pytest.raises(assistant_service.GalatPendamping, match="paket atau kuota"):
        assistant_service.pastikan_entitlement_outbound(
            AKUN, sekarang=10, sebelum_provider=lambda: dipanggil.append(1)
        )
    assert dipanggil == []


def test_fragment_buka_terkunci_owner_sah_tanpa_membaca_konteks(server, monkeypatch):
    monkeypatch.setenv("PENDAMPING_ENTITLEMENT_AKTIF", "1")
    monkeypatch.setattr(
        runtime, "status",
        lambda *_a, **_k: runtime.StatusRuntime(
            "jago_tanpa_ai", paket="jago", enforcement_aktif=True,
        ),
    )
    def dilarang(*_a, **_k):
        raise AssertionError("konteks tidak boleh dibaca pada panel paket")
    monkeypatch.setattr(assistant_http.assistant_context, "ambil", dilarang)
    from test_assistant_inline_http import _origin
    from test_assistant_runtime import _token_guru
    token = _token_guru(server)
    anak = server.ids_inline[0]
    kode, isi, _ = server.minta(
        "/pendamping/inline/buka", cookie=token,
        data={"inline_host": "anak", "inline_host_id": str(anak),
              "inline_posisi": "rencana"},
        headers={**_origin(server), "X-Pendamping-Panel": "fragment"},
    )
    assert kode == 200 and "Pendamping tersedia di Jago Pro" in isi
    assert server.provider.panggilan == []
    assert "data-pendamping-resource-id" not in isi


def test_state_kuota_ui_tidak_mengarang_tanggal():
    state = SimpleNamespace(
        status="kuota_habis", paket="jago_pro", limit=50, digunakan=50,
        direservasi=0, tersisa=0, isi_ulang=None, enforcement_aktif=True,
    )
    panel = assistant_components.panel_akses(
        assistant_inline.tujuan_anak(7, "rencana"), state,
    )
    assert "50 dari 50 balasan sudah digunakan" in panel
    assert "Kuota berikutnya" not in panel
    assert "composer" not in panel
