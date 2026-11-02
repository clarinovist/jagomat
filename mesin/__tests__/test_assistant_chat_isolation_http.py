"""Isolasi chat privat antar akun: lihat, kirim, hapus, dan cabut izin.

Akun B tidak boleh membaca atau mengubah resource chat akun A. Penolakan
harus identik dengan resource yang tidak ada (404 pada jalur aktif, 410 pada
adapter form lama), bukan 403, sehingga tidak menjadi oracle keberadaan chat:
tanpa baris ditulis, tanpa chat terhapus, dan tanpa memanggil provider.
Cabut izin milik B juga tidak boleh menyentuh izin/chat milik A.

Fixture sintetis; tidak memakai data anak nyata.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_context
import assistant_schema
import assistant_service
import assistant_store
import auth
import database
import sessions
from http_test_kit import ServerUji
from test_assistant_runtime import ProviderPalsu, _consent, _token_guru

AKUN_B = "ortu-b-isolasi"
CHAT_ID_HILANG = "chat_" + "f" * 32
CHAT_HILANG = "/pendamping/chat/" + CHAT_ID_HILANG
PESAN_A = "Isi privat sintetis akun A."
PESAN_B = "Pesan sintetis akun B."


def _origin(server):
    return {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}


def _dump(server):
    with assistant_schema.buka() as kon:
        pendamping = tuple(kon.iterdump())
    with server.buka() as kon:
        data = tuple(kon.iterdump())
    return pendamping, data


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    palsu = ProviderPalsu()
    monkeypatch.setattr(assistant_service, "panggil_provider_default", palsu)
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        s.anak = database.tambah_siswa(kon, "Anak Privat", "P3", pemilik="guru")
        s.anak_b = database.tambah_siswa(kon, "Anak B", "P3", pemilik=AKUN_B)
        s.versi_anak = assistant_context.versi_resource(
            kon, "anak", str(s.anak), pemilik="guru"
        )
    auth.tambah_akun(AKUN_B, "sandi-ortu-b-isolasi-123", "guru")
    akun_a = auth.cari_akun("guru")
    akun_b = auth.cari_akun(AKUN_B)
    s.akun_a = akun_a["id_akun"]
    s.akun_b = akun_b["id_akun"]
    s.token_a = _token_guru(s)
    s.token_b = sessions.buat(
        AKUN_B, "guru", id_akun=s.akun_b, revisi_auth=akun_b["revisi_auth"]
    )
    for token in (s.token_a, s.token_b):
        # Server uji mengikuti redirect; 200 berarti halaman tujuan berhasil.
        kode, _, _ = _consent(s, token)
        assert kode == 200
    with assistant_schema.buka() as kon:
        izin = assistant_store.beri_persetujuan_konteks(
            kon, s.akun_a, jenis="anak", resource_id=str(s.anak),
            resource_version=s.versi_anak, kategori="ringkasan_netral",
            sekarang=100,
        )
        s.chat = assistant_store.buat_chat(
            kon, s.akun_a, "aktif", sekarang=101,
            context_kind="anak", context_id=str(s.anak),
            context_version=izin.versi,
            context_resource_version=s.versi_anak,
            context_category="ringkasan_netral",
        )
        assistant_store.tambah_pesan(
            kon, s.akun_a, s.chat.id, "pengguna", PESAN_A,
            request_id="req_pemilik_awal", sekarang=102,
        )
        kon.commit()
    s.provider = palsu
    yield s
    s.berhenti()


def test_akun_lain_tidak_bisa_melihat_chat(server):
    # Sanity: chat memang ada dan bisa dibuka pemiliknya.
    assert server.minta(
        f"/pendamping/chat/{server.chat.id}", cookie=server.token_a
    )[0] == 200

    sebelum = _dump(server)
    asing = server.minta(
        f"/pendamping/chat/{server.chat.id}", cookie=server.token_b
    )
    hilang = server.minta(CHAT_HILANG, cookie=server.token_b)
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert PESAN_A not in asing[1]
    assert _dump(server) == sebelum
    assert server.provider.panggilan == []


def test_akun_lain_ditolak_sama_lewat_form_lama(server):
    # Adapter form percakapan lama sudah ditutup: chat asing dan chat tidak
    # ada sama-sama dijawab 410 dengan body identik, bukan 403, sehingga tidak
    # menjadi oracle keberadaan chat. Isi privat tidak pernah dirender.
    sebelum = _dump(server)
    data = {"pesan": PESAN_B, "request_id": "req_asing_form_lama_1"}
    asing = server.minta(
        f"/pendamping/chat/{server.chat.id}/pesan", cookie=server.token_b,
        data=data, headers=_origin(server),
    )
    hilang = server.minta(
        CHAT_HILANG + "/pesan", cookie=server.token_b,
        data=data, headers=_origin(server),
    )
    assert asing[0] == hilang[0] == 410
    assert asing[1] == hilang[1]
    assert PESAN_A not in asing[1]
    assert _dump(server) == sebelum
    assert server.provider.panggilan == []
    with assistant_schema.buka() as kon:
        assert kon.execute(
            "SELECT 1 FROM pesan WHERE teks = ?", (PESAN_B,)
        ).fetchone() is None


def test_akun_lain_tidak_bisa_mengirim_lewat_inline(server):
    # B memakai host anak miliknya sendiri, lalu mencoba menunjuk chat A.
    sebagai = {
        "inline_host": "anak", "inline_host_id": str(server.anak_b),
        "inline_posisi": "latihan", "chat": server.chat.id,
        "request_id": "req_asing_inline_1", "pesan": PESAN_B,
    }
    hilang_data = dict(sebagai, chat=CHAT_ID_HILANG)
    sebelum = _dump(server)
    asing = server.minta(
        "/pendamping/inline/pesan", cookie=server.token_b,
        data=sebagai, headers=_origin(server),
    )
    hilang = server.minta(
        "/pendamping/inline/pesan", cookie=server.token_b,
        data=hilang_data, headers=_origin(server),
    )
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert PESAN_A not in asing[1]
    assert _dump(server) == sebelum
    assert server.provider.panggilan == []
    with assistant_schema.buka() as kon:
        assert kon.execute(
            "SELECT 1 FROM pesan WHERE teks = ?", (PESAN_B,)
        ).fetchone() is None


def test_akun_lain_tidak_bisa_menghapus_chat(server):
    path = f"/pendamping/kelola/chat/{server.chat.id}/hapus"
    hilang_path = "/pendamping/kelola/chat/chat_" + "f" * 32 + "/hapus"
    sebelum = _dump(server)
    for post in (False, True):
        tambahan = (
            {"data": {"versi": "1", "konfirmasi": "1"}, "headers": _origin(server)}
            if post else {}
        )
        asing = server.minta(path, cookie=server.token_b, **tambahan)
        hilang = server.minta(hilang_path, cookie=server.token_b, **tambahan)
        assert asing[0] == hilang[0] == 404
        assert asing[1] == hilang[1]
    assert _dump(server) == sebelum
    with assistant_schema.buka() as kon:
        assert assistant_store.ambil_chat(kon, server.akun_a, server.chat.id) is not None
        baris = kon.execute(
            "SELECT dihapus FROM chat WHERE id = ?", (server.chat.id,)
        ).fetchone()
        assert baris["dihapus"] is None
    assert server.provider.panggilan == []


def test_cabut_izin_akun_b_tidak_menyentuh_akun_a(server):
    kode, isi, _ = server.minta("/pendamping/kelola/cabut", cookie=server.token_b)
    assert kode == 200
    versi_b = re.search(r'name="versi" value="([0-9]+)"', isi).group(1)
    kode, _, _ = server.minta(
        "/pendamping/kelola/cabut", cookie=server.token_b,
        data={"versi": versi_b, "konfirmasi": "1"}, headers=_origin(server),
    )
    assert kode == 200
    with assistant_schema.buka() as kon:
        assert kon.execute(
            "SELECT 1 FROM persetujuan WHERE account_id = ? AND dicabut IS NULL",
            (server.akun_b,),
        ).fetchone() is None
        assert kon.execute(
            "SELECT 1 FROM persetujuan WHERE account_id = ? AND dicabut IS NULL",
            (server.akun_a,),
        ).fetchone() is not None
        assert assistant_store.persetujuan_konteks_aktif(
            kon, server.akun_a, jenis="anak", resource_id=str(server.anak),
            resource_version=server.versi_anak, kategori="ringkasan_netral",
            versi=server.chat.context_version,
        )
        assert assistant_store.ambil_chat(kon, server.akun_a, server.chat.id) is not None
    assert server.minta(
        f"/pendamping/chat/{server.chat.id}", cookie=server.token_a
    )[0] == 200
