"""Alur UI Pendamping setelah cutover penuh ke host inline dan arsip akun."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_context
import assistant_policy
import assistant_schema
import assistant_store
import auth
import sessions
from test_assistant_actions import server as server_usulan, _buat_usulan_http, _origin
from test_assistant_runtime import server, _token_guru, _consent


def _post(server, token, path, data):
    return server.minta(path, cookie=token, data=data, headers=_origin(server))


def _snapshot_privat():
    with assistant_schema.buka() as kon:
        return tuple(kon.iterdump())


def test_root_dan_tanpa_memori_kembali_ke_workflow_tanpa_membuat_chat(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    for jalur in ("/pendamping", "/pendamping/tanpa-memori"):
        kode, isi, _ = server.minta(jalur, cookie=token)
        assert kode == 200 and "Ruang pendamping" in isi
        assert 'action="/pendamping/chat-baru"' not in isi
    with assistant_schema.buka() as kon:
        assert assistant_store.daftar_chat(kon, akun) == ()


def test_arsip_paging_45_chat_umum_dan_tidak_ada_composer(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        chats = tuple(
            assistant_store.buat_chat(kon, akun, "aktif", sekarang=100 + i)
            for i in range(45)
        )
        assistant_store.tambah_pesan(
            kon, akun, chats[-1].id, "pengguna", "Pesan arsip sintetis.",
            request_id="req_arsip_45", sekarang=200,
        )
        kon.commit()
    sebelum = _snapshot_privat()
    for nomor, jumlah in ((1, 20), (2, 20), (3, 5)):
        kode, isi, _ = server.minta(
            f"/akun?section=arsip-pendamping&halaman={nomor}", cookie=token,
        )
        assert kode == 200
        assert len(re.findall(r"chat=chat_[0-9a-f]{32}", isi)) == jumlah
        assert "Pesan untuk Pendamping" not in isi
    kode, isi, _ = server.minta(
        f"/akun?section=arsip-pendamping&chat={chats[-1].id}", cookie=token,
    )
    assert kode == 200 and "Pesan arsip sintetis." in isi
    assert _snapshot_privat() == sebelum


def test_post_umum_kosong_dan_berisi_tetap_ditolak_tanpa_chat(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    sebelum = _snapshot_privat()
    for pesan in ("", "Halo."):
        kode, _, _ = _post(server, token, "/pendamping/chat-baru", {
            "mode": "tanpa_memori", "pesan_awal": pesan,
            "request_id": "req_umum_ditutup",
        })
        assert kode == 410
    with assistant_schema.buka() as kon:
        assert assistant_store.daftar_chat(kon, akun) == ()
    assert _snapshot_privat() == sebelum and server.provider.panggilan == []


def test_hasil_stale_tetap_terjangkau_readonly_inline(server_usulan):
    server = server_usulan
    token, chat_id, usulan_id = _buat_usulan_http(server)
    _, tinjau, _ = server.minta(f"/pendamping/usulan/{usulan_id}", cookie=token)
    data = {
        "versi": re.search(r'name="versi_usulan" value="([0-9]+)"', tinjau).group(1),
        "hash": re.search(r'name="hash_usulan" value="([0-9a-f]{64})"', tinjau).group(1),
        "request_id": re.search(r'name="request_id" value="(aksi_[0-9a-f]{32})"', tinjau).group(1),
    }
    assert _post(server, token, f"/pendamping/usulan/{usulan_id}/konfirmasi", data)[0] == 200
    kode, isi, _ = server.minta(f"/pendamping/chat/{chat_id}", cookie=token)
    assert kode == 200 and "hanya dapat dibaca" in isi
    assert "Pesan untuk Pendamping" not in isi
    assert "Usulan latihan bebas" in isi and "Buka latihan #" in isi


def test_konteks_dicabut_tidak_boleh_baca_atau_kirim(server_usulan):
    server = server_usulan
    token, chat_id, _ = _buat_usulan_http(server)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        izin = kon.execute(
            "SELECT id,versi FROM persetujuan_konteks WHERE account_id=?", (akun,)
        ).fetchone()
        assistant_store.cabut_persetujuan_konteks(
            kon, akun, izin["id"], versi_diharapkan=izin["versi"], sekarang=500,
        )
        kon.commit()
    sebelum = len(server.provider.panggilan)
    asing = server.minta(f"/pendamping/chat/{chat_id}", cookie=token)
    hilang = server.minta(
        "/pendamping/chat/chat_" + "f" * 32, cookie=token,
    )
    assert asing[0] == hilang[0] == 404 and asing[1] == hilang[1]
    kode, _, _ = _post(server, token, f"/pendamping/chat/{chat_id}/pesan", {
        "pesan": "Ulangi.", "request_id": "req_dicabut_baru",
    })
    assert kode == 409 and len(server.provider.panggilan) == sebelum


def test_pending_contextual_owner_only_dan_tanpa_retry_provider(server_usulan):
    server = server_usulan
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with server.buka() as kon_data:
        konteks = assistant_context.ambil(
            kon_data, "anak", str(server.anak), pemilik="guru"
        )
    with assistant_schema.buka() as kon:
        izin = assistant_store.beri_persetujuan_konteks(
            kon, akun, jenis="anak", resource_id=str(server.anak),
            resource_version=konteks.versi, kategori=konteks.kategori, sekarang=100,
        )
        chat = assistant_store.buat_chat(
            kon, akun, "aktif", sekarang=100, context_kind="anak",
            context_id=str(server.anak), context_version=izin.versi,
            context_resource_version=konteks.versi,
            context_category=konteks.kategori,
        )
        assistant_store.mulai_operasi(
            kon, akun, chat.id, "req_pending_sintetis",
            consent_version=assistant_store.versi_persetujuan(kon, akun),
            memory_version=0, context_version=izin.versi, sekarang=100,
        )
        kon.commit()
    sebelum = _snapshot_privat()
    kode, isi, _ = server.minta(
        "/pendamping/operasi/req_pending_sintetis", cookie=token,
    )
    assert kode == 200 and "Jangan kirim ulang" in isi
    assert "Pesan untuk Pendamping" not in isi
    assert _snapshot_privat() == sebelum and server.provider.panggilan == []

    auth.tambah_akun("ortu-lain", "sandi-sintetis-lain", "guru")
    lain = auth.cari_akun("ortu-lain")
    token_b = sessions.buat(
        lain["pengguna"], "guru", id_akun=lain["id_akun"],
        revisi_auth=lain["revisi_auth"],
    )
    _consent(server, token_b)
    asing = server.minta(
        "/pendamping/operasi/req_pending_sintetis", cookie=token_b,
    )
    hilang = server.minta(
        "/pendamping/operasi/req_hilang_sintetis", cookie=token_b,
    )
    assert asing[0] == hilang[0] == 404 and asing[1] == hilang[1]


def test_consent_umum_dicabut_tidak_membuka_arsip_atau_chat(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        chat = assistant_store.buat_chat(kon, akun, "aktif", sekarang=100)
        izin = kon.execute(
            "SELECT id,versi FROM persetujuan WHERE account_id=? ORDER BY versi DESC LIMIT 1",
            (akun,),
        ).fetchone()
        assistant_store.cabut_persetujuan(
            kon, akun, izin["id"], versi_diharapkan=izin["versi"], sekarang=500,
        )
        kon.commit()
    kode, isi, _ = server.minta("/akun", cookie=token)
    assert kode == 200 and "Arsip percakapan lama" not in isi
    assert server.minta(f"/pendamping/chat/{chat.id}", cookie=token)[0] == 404
    assert _post(server, token, "/pendamping/chat-baru", {
        "mode": "aktif", "pesan_awal": "Halo.",
        "request_id": "req_consent_dicabut",
    })[0] == 410
    assert server.provider.panggilan == []
