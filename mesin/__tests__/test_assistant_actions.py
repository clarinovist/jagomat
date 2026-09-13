"""Usulan latihan Pendamping: allow-list, tinjau, konfirmasi, dan idempotensi."""

from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_actions  # noqa: E402
import assistant_policy  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402
from test_assistant_runtime import ProviderPalsu, _consent, _token_guru  # noqa: E402


USULAN_SAH = {
    "topik_id": "pola-bilangan",
    "template_ids": ["deret_aritmetika"],
    "level": "P3",
    "jumlah_soal": 10,
}


def _origin(server):
    return {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}


def _field_tinjau(isi):
    cocok = re.search(
        r'name="data_aksi" value="([^"]+)"[^>]+formaction="/pendamping/inline/konfirmasi-usulan"',
        isi,
    )
    if cocok:
        return dict(urllib.parse.parse_qsl(html.unescape(cocok.group(1))))
    return {
        nama: re.search(r'name="' + nama + r'" value="([^"]+)"', isi).group(1)
        for nama in ("usulan", "versi_usulan", "hash_usulan", "request_id")
    }


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    provider = ProviderPalsu({
        "jawaban": "Saya sudah menyiapkan usulan untuk ditinjau.",
        "draft_memori": None,
        "usulan_latihan": USULAN_SAH,
        "butuh_klarifikasi": False,
    })
    monkeypatch.setattr(assistant_service, "panggil_provider_default", provider)
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        s.anak = database.tambah_siswa(
            kon, "Anak Usulan", "P3", pemilik="guru"
        )
    s.provider = provider
    yield s
    s.berhenti()


def _buat_usulan_http(server):
    token = _token_guru(server)
    _consent(server, token)
    _, pilih, _ = server.minta(
        f"/pendamping/konteks/anak/{server.anak}", cookie=token
    )
    versi = re.search(
        r'name="resource_version" value="([0-9a-f]+)"', pilih
    ).group(1)
    _, chat_html, _ = server.minta(
        "/pendamping/konteks/pilih",
        cookie=token,
        data={
            "jenis": "anak",
            "resource_id": str(server.anak),
            "resource_version": versi,
            "kategori": "ringkasan_netral",
            "mode": "aktif",
        },
        headers=_origin(server),
    )
    chat_id = re.search(
        r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html
    ).group(1)
    request_id = re.search(
        r'name="request_id" value="([^"]+)"', chat_html
    ).group(1)
    kode, hasil, _ = server.minta(
        f"/pendamping/chat/{chat_id}/pesan",
        cookie=token,
        data={"pesan": "Tolong usulkan latihan.", "request_id": request_id},
        headers=_origin(server),
    )
    assert kode == 200
    usulan_id = re.search(
        r'(usulan_[0-9a-f]{32})', hasil
    ).group(1)
    return token, chat_id, usulan_id


def test_validator_hanya_menerima_katalog_aktual_dan_field_allow_list():
    hasil = assistant_actions.validasi_usulan(USULAN_SAH)
    assert hasil.topik_id == "pola-bilangan"
    assert hasil.template_ids == ("deret_aritmetika",)

    rusak = (
        {**USULAN_SAH, "owner": "guru"},
        {**USULAN_SAH, "topik_id": "kurikulum-baru"},
        {**USULAN_SAH, "level": "kelas-3"},
        {**USULAN_SAH, "jumlah_soal": 50},
        {**USULAN_SAH, "template_ids": ["template_buatan_ai"]},
        {**USULAN_SAH, "topik_id": "statistika"},
    )
    for data in rusak:
        with pytest.raises(assistant_actions.GalatTindakan):
            assistant_actions.validasi_usulan(data)


def test_chat_umum_tidak_boleh_menyimpan_usulan(tmp_path):
    account_id = "akun_" + "a" * 32
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    provider = ProviderPalsu({
        "jawaban": "Ada usulan.",
        "draft_memori": None,
        "usulan_latihan": USULAN_SAH,
        "butuh_klarifikasi": False,
    })
    with assistant_schema.buka(path) as kon:
        assistant_store.beri_persetujuan(
            kon, account_id,
            policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id=assistant_policy.PROVIDER_ID,
            kategori="chat_umum", sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, account_id, "aktif", sekarang=100)
        with pytest.raises(
            assistant_service.GalatPendamping, match="Pilih konteks"
        ):
            assistant_service.kirim_pesan(
                kon, account_id, chat.id, "Buat latihan.",
                request_id="req_usulan_umum", panggil_provider=provider,
                sekarang=101,
            )
        assert assistant_store.daftar_pesan(kon, account_id, chat.id) == ()
        assert kon.execute("SELECT COUNT(*) FROM usulan_latihan").fetchone()[0] == 0


def test_http_tinjau_lalu_konfirmasi_membuat_satu_sesi_bebas(server):
    token, chat_id, usulan_id = _buat_usulan_http(server)
    with server.buka() as kon:
        sebelum_sesi = kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]
        sebelum_kejadian = kon.execute(
            "SELECT COUNT(*) FROM kejadian_belajar"
        ).fetchone()[0]
        sebelum_bukti = kon.execute(
            "SELECT COUNT(*) FROM bukti_fokus"
        ).fetchone()[0]

    kode, tinjau, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}", cookie=token
    )
    assert kode == 200
    assert "Tinjau usulan latihan" in tinjau
    assert "Pola Bilangan" in tinjau
    assert "P3" in tinjau
    assert "10 soal" in tinjau
    assert "Belum ada sesi. Tinjau lalu konfirmasi" not in tinjau
    field = _field_tinjau(tinjau)
    versi = field["versi_usulan"]
    sidik = field["hash_usulan"]
    request_id = field["request_id"]

    kode, hasil, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={"versi": versi, "hash": sidik, "request_id": request_id},
        headers=_origin(server),
    )
    assert kode == 200
    assert "Sesi #" in hasil
    with server.buka() as kon:
        baris = kon.execute(
            """SELECT s.*, COUNT(ss.id) AS jumlah
               FROM sesi s JOIN sesi_soal ss ON ss.sesi_id = s.id
               GROUP BY s.id ORDER BY s.id DESC LIMIT 1"""
        ).fetchone()
        assert baris["tujuan"] == "bebas"
        assert baris["putaran_id"] is None
        assert baris["dikonfirmasi_guru"] is None
        assert baris["jumlah"] == 10
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum_sesi + 1
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar").fetchone()[0] == sebelum_kejadian
        assert kon.execute("SELECT COUNT(*) FROM bukti_fokus").fetchone()[0] == sebelum_bukti
        sesi_id = int(baris["id"])

    # Retry dengan token konfirmasi yang sama mengembalikan sesi yang sama.
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={"versi": versi, "hash": sidik, "request_id": request_id},
        headers=_origin(server),
    )
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum_sesi + 1
        assert kon.execute(
            "SELECT tujuan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()[0] == "bebas"

    # Double-submit dengan token aksi berbeda tidak membuka eksekusi kedua.
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={
            "versi": versi,
            "hash": sidik,
            "request_id": "aksi_" + "b" * 32,
        },
        headers=_origin(server),
    )
    assert kode == 409
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum_sesi + 1
    with assistant_schema.buka() as kon:
        usulan = assistant_store.ambil_usulan(
            kon, auth.cari_akun("guru")["id_akun"], usulan_id
        )
        assert usulan.sesi_id == sesi_id
        assert usulan.status == "selesai"
        assert assistant_store.ambil_chat(
            kon, auth.cari_akun("guru")["id_akun"], chat_id
        ) is not None


def test_perubahan_chat_setelah_tinjau_meminta_tinjau_ulang(server):
    token, chat_id, usulan_id = _buat_usulan_http(server)
    _, tinjau, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}", cookie=token
    )
    field = _field_tinjau(tinjau)
    versi = field["versi_usulan"]
    sidik = field["hash_usulan"]
    request_id = field["request_id"]
    with assistant_schema.buka() as kon:
        akun = auth.cari_akun("guru")["id_akun"]
        assistant_store.tambah_pesan(
            kon, akun, chat_id, "pengguna", "Parameter baru.",
            request_id="req_perubahan_tinjau", sekarang=200,
        )
    with server.buka() as kon:
        sebelum = kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]
    kode, isi, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={"versi": versi, "hash": sidik, "request_id": request_id},
        headers=_origin(server),
    )
    assert kode == 409
    assert "Tinjau ulang" in isi or "tinjau ulang" in isi
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum


def test_hash_atau_owner_asing_gagal_tanpa_sesi(server):
    token, _, usulan_id = _buat_usulan_http(server)
    _, tinjau, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}", cookie=token
    )
    field = _field_tinjau(tinjau)
    versi = field["versi_usulan"]
    request_id = field["request_id"]
    with server.buka() as kon:
        sebelum = kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={"versi": versi, "hash": "f" * 64, "request_id": request_id},
        headers=_origin(server),
    )
    assert kode == 409
    kode, _, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}/konfirmasi",
        cookie=token,
        data={
            "versi": str(int(versi) + 1),
            "hash": field["hash_usulan"],
            "request_id": request_id,
        },
        headers=_origin(server),
    )
    assert kode == 409

    auth.tambah_akun("ortu-b", "sandi-ortu-b-123", "guru")
    akun_b = auth.cari_akun("ortu-b")
    token_b = sessions.buat(
        "ortu-b", "guru", id_akun=akun_b["id_akun"],
        revisi_auth=akun_b["revisi_auth"],
    )
    _consent(server, token_b)
    kode_asing, isi_asing, _ = server.minta(
        f"/pendamping/usulan/{usulan_id}", cookie=token_b
    )
    kode_hilang, isi_hilang, _ = server.minta(
        "/pendamping/usulan/usulan_ffffffffffffffffffffffffffffffff",
        cookie=token_b,
    )
    assert kode_asing == kode_hilang == 404
    assert isi_asing == isi_hilang
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum
