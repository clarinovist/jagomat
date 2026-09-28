"""Writer kuota runtime Pendamping: urutan provider, simpan, dan rekonsiliasi."""
import pytest

import assistant_client
import assistant_entitlement_runtime as runtime
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store

AKUN = "akun_" + "a" * 32
RESPONS = {
    "jawaban": "Jawaban sintetis.", "draft_memori": None,
    "usulan_latihan": None, "butuh_klarifikasi": False,
}


def _chat(path):
    assistant_schema.siapkan(path)
    kon = assistant_schema.buka(path)
    assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id=assistant_policy.PROVIDER_ID, kategori="chat_umum", sekarang=1,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=1)
    kon.commit()
    return kon, chat


def test_runtime_off_reservasi_finalisasi_tanpa_io(monkeypatch):
    monkeypatch.delenv("PENDAMPING_ENTITLEMENT_AKTIF", raising=False)
    assert runtime.reservasi(
        AKUN, fitur="balasan_pendamping", identitas="req_sintetis", sekarang=1,
    ) is None
    runtime.finalisasi(None, sekarang=2)
    runtime.tandai_unknown(None, sekarang=2)


def test_service_reserve_sebelum_provider_dan_finalize_setelah_simpan(monkeypatch, tmp_path):
    urutan = []
    ikatan = object()
    kon, chat = _chat(tmp_path / "pendamping.db")
    monkeypatch.setattr(assistant_service, "pastikan_entitlement_outbound", lambda *_a, **_k: None)
    monkeypatch.setattr(
        assistant_service.entitlement, "reservasi",
        lambda *_a, **_k: (
            urutan.append("reserve"),
            kon.in_transaction is False or (_ for _ in ()).throw(
                AssertionError("reserve tidak boleh ditahan transaksi chat")
            ),
            ikatan,
        )[-1],
    )
    def finalisasi(target, **_kwargs):
        assert target is ikatan
        assert kon.execute("SELECT status FROM operasi").fetchone()[0] == "selesai"
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 2
        urutan.append("finalize")
    monkeypatch.setattr(assistant_service.entitlement, "finalisasi", finalisasi)
    monkeypatch.setattr(
        assistant_service.entitlement, "tandai_unknown",
        lambda *_a, **_k: urutan.append("unknown"),
    )
    try:
        hasil = assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Pesan sintetis.", request_id="req_sintetis01",
            panggil_provider=lambda *_: urutan.append("provider") or RESPONS,
            sekarang=2,
        )
    finally:
        kon.close()
    assert hasil == RESPONS["jawaban"]
    assert urutan == ["reserve", "provider", "finalize"]


def test_provider_unknown_dan_respons_invalid_dilepas(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant_service, "pastikan_entitlement_outbound", lambda *_a, **_k: None)
    for nama, provider, hasil in (
        ("unknown", lambda *_: (_ for _ in ()).throw(
            assistant_client.GalatProvider("sintetis", kategori="provider_timeout")
        ), "unknown"),
        ("invalid", lambda *_: {**RESPONS, "asing": True}, "released"),
    ):
        kon, chat = _chat(tmp_path / (nama + ".db"))
        urutan = []
        monkeypatch.setattr(assistant_service.entitlement, "reservasi", lambda *_a, **_k: object())
        monkeypatch.setattr(assistant_service.entitlement, "tandai_unknown", lambda *_a, **_k: urutan.append("unknown"))
        monkeypatch.setattr(assistant_service.entitlement, "lepaskan", lambda *_a, **_k: urutan.append("released"))
        try:
            with pytest.raises(assistant_service.GalatPendamping):
                assistant_service.kirim_pesan(
                    kon, AKUN, chat.id, "Pesan sintetis.",
                    request_id="req_" + nama + "01", panggil_provider=provider,
                    sekarang=2,
                )
        finally:
            kon.close()
        assert urutan == [hasil]


def test_gagal_setelah_reserve_sebelum_provider_melepaskan(monkeypatch, tmp_path):
    kon, chat = _chat(tmp_path / "revalidasi.db")
    monkeypatch.setattr(assistant_service, "pastikan_entitlement_outbound", lambda *_a, **_k: None)
    monkeypatch.setattr(assistant_service.entitlement, "reservasi", lambda *_a, **_k: "ikat")
    dilepas = []
    monkeypatch.setattr(assistant_service.entitlement, "lepaskan", lambda *_a, **_k: dilepas.append(1))
    monkeypatch.setattr(
        assistant_service.assistant_store, "mulai_operasi",
        lambda *_a, **_k: (_ for _ in ()).throw(
            assistant_service.GalatPendamping("State berubah.")
        ),
    )
    provider = []
    try:
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Pesan sintetis.", request_id="req_revalidasi01",
                panggil_provider=lambda *_: provider.append(1), sekarang=2,
            )
    finally:
        kon.close()
    assert dilepas == [1] and provider == []


def test_runtime_operasi_id_tidak_menyimpan_teks_request():
    oid = runtime.operasi_id(
        AKUN, "balasan_pendamping", "req_teks_yang_tidak_boleh_tersimpan",
    )
    assert oid.startswith("kuota_") and len(oid) == 38
    assert "teks" not in oid and "req_" not in oid
