"""HTTP nyata host Pendamping inline: principal, draft, header, dan side effect."""

from pathlib import Path
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
import auth
import database
import sessions
from http_test_kit import ServerUji
from test_assistant_runtime import ProviderPalsu, _token_guru


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
        anak = database.tambah_siswa(kon, "Anak Inline", "P3", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, seed=42, jumlah_soal=2)
        asing = database.tambah_siswa(kon, "Asing", "P3", pemilik="ortu-b")
        sesi_asing = database.buat_sesi(kon, asing, seed=43, jumlah_soal=2)
        database.tandai_selesai(kon, sesi)
    s.ids_inline = (anak, sesi, asing, sesi_asing)
    s.provider = palsu
    yield s
    s.berhenti()


def _origin(server):
    return {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}


def _privat(header):
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert header["X-Robots-Tag"] == "noindex, nofollow"
    assert header["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in header["Content-Security-Policy"]


def _draf(server, sesi):
    with server.buka() as kon:
        ids = [b["sesi_soal_id"] for b in database.isi_sesi(kon, sesi)]
    data = {"hadir_sertakan_pemetaan": "1"}
    nilai = (("", "K", "Baris satu\nbaris dua", "ragu", False, True),
             ("42", "benar", "Cara kedua", "bisa_menjelaskan", True, False))
    for sid, (jwb, kode, cara, paham, lewati, belum) in zip(ids, nilai):
        data.update({f"jwb_{sid}": jwb, f"kode_{sid}": kode, f"cara_{sid}": cara,
                     f"cek_pemahaman_{sid}": paham, f"hadir_dilewati_{sid}": "1",
                     f"hadir_belum_{sid}": "1"})
        if lewati: data[f"dilewati_{sid}"] = "1"
        if belum: data[f"belum_{sid}"] = "1"
    return ids, data


def test_query_host_existing_tetap_diterima_dan_query_bantuan_tetap_strict(server):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    kode, isi, _ = server.minta(f"/anak/{anak}?pesan=Berhasil&sorot={sesi}", cookie=token)
    assert kode == 200 and "Berhasil" in isi
    assert server.minta(f"/anak/{anak}?bantuan=rencana&asing=1", cookie=token)[0] == 404


def test_get_host_inline_privat_tanpa_provider_write_atau_resource_eksternal(server):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    kode, biasa, _ = server.minta(f"/anak/{anak}", cookie=token)
    assert kode == 200 and '<form method="post" action="/pendamping/inline/buka">' in biasa
    kode, profil, header = server.minta(
        f"/anak/{anak}?bantuan=rencana", cookie=token
    )
    assert kode == 200
    _privat(header)
    assert 'id="bantuan-rencana"' in profil
    assert "Sebelum memakai bantuan" in profil
    assert 'data-bagikan-url=' not in profil
    assert 'action="/pendamping/inline/tutup"' in profil
    assert "fonts.googleapis.com" not in profil and "<script" not in profil
    assert not assistant_schema.BAWAAN.exists()
    assert server.provider.panggilan == []

    kode, sesi_html, header = server.minta(
        f"/sesi/{sesi}?bantuan=soal&nomor=1", cookie=token
    )
    assert kode == 200
    _privat(header)
    assert 'id="bantuan-soal-1"' in sesi_html
    assert "fonts.googleapis.com" not in sesi_html and "<script" not in sesi_html
    assert "Tutup bantuan untuk membuka aksi pembatalan atau hapus." in sesi_html
    assert 'onsubmit="return confirm(' not in sesi_html


def test_tutup_bantuan_memulihkan_kontrol_tautan_dan_konfirmasi_destruktif(server):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    kode, assisted, _ = server.minta(f"/anak/{anak}?bantuan=rencana", cookie=token)
    assert kode == 200 and 'data-bagikan-url=' not in assisted
    kode, normal, _ = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"},
        headers=_origin(server),
    )
    assert kode == 200 and "<script" not in normal
    kode, sesi_assisted, _ = server.minta(f"/sesi/{sesi}?bantuan=soal&nomor=1", cookie=token)
    assert kode == 200 and 'onsubmit="return confirm(' not in sesi_assisted
    ids, draf = _draf(server, sesi)
    kode, sesi_normal, _ = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal",
              "inline_nomor": "1", **draf}, headers=_origin(server),
    )
    assert kode == 200 and "<script" not in sesi_normal
    assert "fonts.googleapis.com" not in sesi_normal
    assert 'action="/sesi/' in sesi_normal and '/hapus"' in sesi_normal
    assert "Baris satu\nbaris dua" in sesi_normal


def test_origin_null_hanya_diterima_bila_fetch_same_origin(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    data = {"inline_host": "anak", "inline_host_id": str(anak),
            "inline_posisi": "rencana"}
    kode, isi, _ = server.minta(
        "/pendamping/inline/buka", cookie=token, data=data,
        headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and "Sebelum memakai bantuan" in isi
    for headers in (
        {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
        {"Origin": "https://asing.test", "Sec-Fetch-Site": "same-origin"},
        {"Sec-Fetch-Site": "none"},
    ):
        kode, _, _ = server.minta(
            "/pendamping/inline/buka", cookie=token, data=data, headers=headers,
        )
        assert kode == 403


def test_resource_asing_hilang_404_identik_tanpa_stamp_direview(server):
    token = _token_guru(server)
    _, _, _, sesi_asing = server.ids_inline
    with server.buka() as kon:
        sebelum = kon.execute("SELECT direview FROM sesi WHERE id=?", (sesi_asing,)).fetchone()[0]
    a = server.minta(f"/sesi/{sesi_asing}?bantuan=soal&nomor=1", cookie=token)
    b = server.minta("/sesi/999999?bantuan=soal&nomor=1", cookie=token)
    assert a[0] == b[0] == 404
    assert a[1] == b[1]
    with server.buka() as kon:
        assert kon.execute("SELECT direview FROM sesi WHERE id=?", (sesi_asing,)).fetchone()[0] == sebelum
    assert server.provider.panggilan == []


def test_consent_mulai_dan_kirim_inline_tetap_di_host(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    kode, isi, header = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"},
        headers=_origin(server),
    )
    assert kode == 200 and "Pilih sumber bantuan" in isi
    _privat(header)
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', isi).group(1)
    with assistant_schema.buka() as kon:
        jumlah_izin = kon.execute("SELECT COUNT(*) FROM persetujuan").fetchone()[0]
    kode, chat, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, "resource_version": versi, "kategori": "ringkasan_netral",
              "mode_chat": "aktif", "request_id": "buka_sintetis123", "setuju_konteks": "1"},
        headers=_origin(server),
    )
    assert kode == 200 and "Bantuan terkait" in chat
    chat_id = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat).group(1)
    with assistant_schema.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM persetujuan").fetchone()[0] == jumlah_izin
    kode, chat_ulang, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, "resource_version": versi, "kategori": "ringkasan_netral",
              "mode_chat": "aktif", "request_id": "buka_sintetis123", "setuju_konteks": "1"},
        headers=_origin(server),
    )
    assert kode == 200
    assert re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_ulang).group(1) == chat_id
    with assistant_schema.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 1
    request_id = re.search(r'name="request_id" value="(req_[^"]+)"', chat).group(1)
    kode, hasil, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token,
        data={**dasar, "chat": chat_id, "request_id": request_id, "pesan": "Bantu rencana ini."},
        headers=_origin(server),
    )
    assert kode == 200
    assert "Mari kita bahas" in hasil
    assert "/pendamping/chat/" not in hasil
    assert len(server.provider.panggilan) == 1


def test_mode_tanpa_memori_inline_immutable_dan_riwayat_tetap_ada(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    _, pilih, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', pilih).group(1)
    kode, chat_html, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, "resource_version": versi, "kategori": "ringkasan_netral",
              "mode_chat": "tanpa_memori", "request_id": "buka_tanpa_123", "setuju_konteks": "1"},
        headers=_origin(server),
    )
    assert kode == 200 and "Chat tanpa memori" in chat_html
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html).group(1)
    req = re.search(r'name="request_id" value="(req_[^"]+)"', chat_html).group(1)
    kode, hasil, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token,
        data={**dasar, "chat": chat, "request_id": req, "pesan": "Tetap simpan riwayat."},
        headers=_origin(server),
    )
    assert kode == 200 and "Tetap simpan riwayat." in hasil
    with assistant_schema.buka() as kon:
        assert assistant_store.ambil_chat(kon, auth.cari_akun("guru")["id_akun"], chat).mode_memori == "tanpa_memori"
        assert assistant_store.daftar_pesan(kon, auth.cari_akun("guru")["id_akun"], chat)


def test_draft_memori_konfirmasi_ubah_hapus_semua_inline(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    with server.buka() as kon_data:
        import assistant_context
        konteks = assistant_context.ambil(kon_data, "anak", str(anak), pemilik="guru")
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        grant = assistant_store.beri_persetujuan_konteks(
            kon, akun, jenis="anak", resource_id=str(anak), resource_version=konteks.versi,
            kategori=konteks.kategori, sekarang=1,
        )
        chat = assistant_store.buat_chat(
            kon, akun, "aktif", sekarang=1, context_kind="anak", context_id=str(anak),
            context_version=grant.versi, context_resource_version=konteks.versi,
            context_category=konteks.kategori,
        )
        draft = assistant_store.tambah_memori(
            kon, akun, "Jawab singkat.", sumber_chat_id=chat.id,
            dikonfirmasi=False, sekarang=2,
        )
        kon.commit()
    identitas = {**dasar, "chat": chat.id}
    kode, isi, _ = server.minta(
        "/pendamping/inline/konfirmasi-memori", cookie=token,
        data={**identitas, "memori": draft.id, "versi_item": str(draft.versi)}, headers=_origin(server),
    )
    assert kode == 200 and "Jawab singkat." in isi
    with assistant_schema.buka() as kon:
        item = next(m for m in assistant_store.daftar_memori(kon, akun) if m.id == draft.id)
        assert item.dikonfirmasi
    kode, isi, _ = server.minta(
        "/pendamping/inline/ubah-memori", cookie=token,
        data={**identitas, "memori": item.id, "versi_item": str(item.versi),
              "isi_memori": "Jawab singkat dengan satu analogi."}, headers=_origin(server),
    )
    assert kode == 200 and "Jawab singkat dengan satu analogi." in isi
    with assistant_schema.buka() as kon:
        item = next(m for m in assistant_store.daftar_memori(kon, akun) if m.id == item.id)
    kode, tinjau, _ = server.minta(
        "/pendamping/inline/tinjau-hapus-memori", cookie=token,
        data={**identitas, "memori": item.id, "versi_item": str(item.versi)},
        headers=_origin(server),
    )
    assert kode == 200 and "Tinjau penghapusan memori" in tinjau
    assert "Jawab singkat dengan satu analogi." in tinjau
    assert "Chat sumber tetap ada" in tinjau and "maksimal 30 hari" in tinjau
    assert 'name="persetujuan_hapus" value="1"' in tinjau
    with assistant_schema.buka() as kon:
        assert len(assistant_store.daftar_memori(kon, akun)) == 1
    kode, batal, _ = server.minta(
        "/pendamping/inline/batal-hapus-memori", cookie=token,
        data=identitas, headers=_origin(server),
    )
    assert kode == 200 and "Jawab singkat dengan satu analogi." in batal
    kode, tanpa_izin, _ = server.minta(
        "/pendamping/inline/hapus-memori", cookie=token,
        data={**identitas, "memori": item.id, "versi_item": str(item.versi)},
        headers=_origin(server),
    )
    assert kode == 400 and "Centang konfirmasi sebelum menghapus" in tanpa_izin
    assert "Tinjau penghapusan memori" in tanpa_izin
    with assistant_schema.buka() as kon:
        assert len(assistant_store.daftar_memori(kon, akun)) == 1
    kode, isi, _ = server.minta(
        "/pendamping/inline/hapus-memori", cookie=token,
        data={**identitas, "memori": item.id, "versi_item": str(item.versi),
              "persetujuan_hapus": "1"}, headers=_origin(server),
    )
    assert kode == 200 and "Jawab singkat dengan satu analogi." not in isi
    with assistant_schema.buka() as kon:
        assert assistant_store.daftar_memori(kon, akun) == ()


def test_history_exact_resource_pagination_inline(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    with server.buka() as kon_data:
        import assistant_context
        konteks = assistant_context.ambil(kon_data, "anak", str(anak), pemilik="guru")
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        grant = assistant_store.beri_persetujuan_konteks(
            kon, akun, jenis="anak", resource_id=str(anak), resource_version=konteks.versi,
            kategori=konteks.kategori, sekarang=1,
        )
        chats = tuple(assistant_store.buat_chat(
            kon, akun, "aktif", sekarang=i, context_kind="anak", context_id=str(anak),
            context_version=grant.versi, context_resource_version=konteks.versi,
            context_category=konteks.kategori,
        ) for i in range(1, 23))
        kon.commit()
    aktif = chats[-1]
    kode, halaman_1, _ = server.minta(
        f"/anak/{anak}?bantuan=rencana&chat={aktif.id}", cookie=token,
    )
    assert kode == 200 and "Berikutnya" in halaman_1 and "Halaman 1" in halaman_1
    kode, halaman_2, _ = server.minta(
        "/pendamping/inline/riwayat", cookie=token,
        data={**dasar, "chat": aktif.id, "halaman": "2"}, headers=_origin(server),
    )
    assert kode == 200 and "Sebelumnya" in halaman_2 and "Halaman 2" in halaman_2
    assert len(re.findall(r"Chat [0-9]{2} [A-Z][a-z]{2} 1970", halaman_2)) == 2


def test_usulan_inline_tinjau_konfirmasi_hasil_idempoten_tanpa_bukti(server, monkeypatch):
    usulan_sah = {"topik_id": "pola-bilangan", "template_ids": ["deret_aritmetika"],
                  "level": "P3", "jumlah_soal": 10}
    provider = ProviderPalsu({"jawaban": "Usulan siap ditinjau.", "draft_memori": None,
                              "usulan_latihan": usulan_sah, "butuh_klarifikasi": False})
    monkeypatch.setattr(assistant_service, "panggil_provider_default", provider)
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    _, pilih, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', pilih).group(1)
    _, chat_html, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, "resource_version": versi, "kategori": "ringkasan_netral",
              "mode_chat": "aktif", "request_id": "buka_usulan_123", "setuju_konteks": "1"}, headers=_origin(server),
    )
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html).group(1)
    req = re.search(r'name="request_id" value="(req_[^"]+)"', chat_html).group(1)
    _, jawaban, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token,
        data={**dasar, "chat": chat, "request_id": req, "pesan": "Tolong usulkan latihan."}, headers=_origin(server),
    )
    usulan = re.search(r'name="data_aksi" value="usulan=(usulan_[0-9a-f]{32})"', jawaban).group(1)
    with server.buka() as kon:
        sebelum_sesi = kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]
        sebelum_bukti = kon.execute("SELECT COUNT(*) FROM bukti_fokus").fetchone()[0]
    kode, tinjau, _ = server.minta(
        "/pendamping/inline/tinjau", cookie=token,
        data={**dasar, "chat": chat, "usulan": usulan}, headers=_origin(server),
    )
    assert kode == 200 and "Tinjau usulan latihan" in tinjau
    import html
    import urllib.parse
    muatan_konfirmasi = re.search(
        r'name="data_aksi" value="([^"]+)"[^>]+formaction="/pendamping/inline/konfirmasi-usulan"',
        tinjau,
    ).group(1)
    data_konfirmasi = {
        **dasar, "chat": chat,
        **dict(urllib.parse.parse_qsl(html.unescape(muatan_konfirmasi))),
    }
    kode, hasil, _ = server.minta(
        "/pendamping/inline/konfirmasi-usulan", cookie=token,
        data=data_konfirmasi, headers=_origin(server),
    )
    assert kode == 200 and "Latihan siap" in hasil and "Buka latihan" in hasil
    kode, hasil_retry, _ = server.minta(
        "/pendamping/inline/konfirmasi-usulan", cookie=token,
        data=data_konfirmasi, headers=_origin(server),
    )
    assert kode == 200 and "Latihan siap" in hasil_retry
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == sebelum_sesi + 1
        assert kon.execute("SELECT COUNT(*) FROM bukti_fokus").fetchone()[0] == sebelum_bukti
        sesi_baru = kon.execute("SELECT tujuan,putaran_id FROM sesi ORDER BY id DESC LIMIT 1").fetchone()
        assert tuple(sesi_baru) == ("bebas", None)


def test_edit_memori_dalam_form_koreksi_hanya_mengambil_field_target(server):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    dasar_anak = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar_anak, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    with server.buka() as kon_data:
        import assistant_context
        konteks = assistant_context.ambil(kon_data, "soal", f"{sesi}:1", pemilik="guru")
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        grant = assistant_store.beri_persetujuan_konteks(
            kon, akun, jenis="soal", resource_id=f"{sesi}:1", resource_version=konteks.versi,
            kategori=konteks.kategori, sekarang=1,
        )
        chat = assistant_store.buat_chat(
            kon, akun, "aktif", sekarang=1, context_kind="soal", context_id=f"{sesi}:1",
            context_version=grant.versi, context_resource_version=konteks.versi,
            context_category=konteks.kategori,
        )
        memori = assistant_store.tambah_memori(
            kon, akun, "Jawab singkat.", sumber_chat_id=chat.id, dikonfirmasi=True, sekarang=2,
        )
        kon.commit()
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal",
             "inline_nomor": "1", "chat": chat.id}
    payload = {**dasar, **draf,
               "isi_memori_" + memori.id: "Jawab singkat dengan satu analogi.",
               "data_aksi": f"memori={memori.id}&versi_item={memori.versi}&isi_field=isi_memori_{memori.id}"}
    kode, isi, _ = server.minta(
        "/pendamping/inline/ubah-memori", cookie=token, data=payload, headers=_origin(server),
    )
    assert kode == 200 and "Jawab singkat dengan satu analogi." in isi
    assert "Baris satu\nbaris dua" in isi
    with server.buka() as kon:
        assert kon.execute("SELECT jawaban FROM jawaban WHERE sesi_soal_id=?", (ids[0],)).fetchone() is None


def test_draf_form_latihan_profil_melintasi_consent_tanpa_membuat_sesi(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    draf = {"topik": "campuran", "jumlah_soal": "15", "mode": "drill",
            "hadir_timer_mode": "1", "timer_mode": "sesi", "durasi_menit": "47", "timer_auto": "1"}
    with server.buka() as kon:
        sebelum = kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0]
    kode, isi, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, **draf, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"},
        headers=_origin(server),
    )
    assert kode == 200
    assert '<option value="campuran" selected>' in isi
    assert '<option value="15" selected>' in isi
    assert 'name="mode" value="drill" checked' in isi
    assert 'name="timer_mode" value="sesi" checked' in isi
    assert 'name="durasi_menit" value="47"' in isi
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0] == sebelum


def test_host_biasa_membuka_bantuan_via_post_dengan_draf(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    kode, awal, _ = server.minta(f"/sesi/{sesi}", cookie=token)
    assert kode == 200
    assert f'formaction="/pendamping/inline/buka/sesi/{sesi}/soal/1"' in awal
    assert f'form="form-koreksi-{sesi}"' in awal
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal", "inline_nomor": "1"}
    kode, isi, _ = server.minta(
        f"/pendamping/inline/buka/sesi/{sesi}/soal/1", cookie=token, data=draf, headers=_origin(server),
    )
    assert kode == 200
    assert 'id="bantuan-soal-1"' in isi
    assert "Baris satu\nbaris dua" in isi
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi


def test_tutup_bantuan_memulihkan_host_native_dan_draf(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal", "inline_nomor": "1"}
    kode, isi, header = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={**dasar, **draf}, headers=_origin(server),
    )
    assert kode == 200
    assert "Bantuan terkait" not in isi and "Sebelum memakai bantuan" not in isi
    assert "Baris satu\nbaris dua" in isi
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi
    _privat(header)
    assert "script-src 'unsafe-inline'" not in header["Content-Security-Policy"]
    assert "<script" not in isi and "fonts.googleapis.com" not in isi


def test_tutup_draf_koreksi_blank_checkbox_caraku_pemahaman_dan_galat_privat(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi),
             "inline_posisi": "soal", "inline_nomor": "1"}
    kode, isi, header = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={**dasar, **draf}, headers=_origin(server),
    )
    assert kode == 200
    _privat(header)
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi
    assert "Baris satu\nbaris dua" in isi
    from test_teacher_corrections import FormKoreksi
    pulih = FormKoreksi(isi, sesi).data
    assert pulih[f'cek_pemahaman_{ids[0]}'] == 'ragu'
    assert pulih[f'belum_{ids[0]}'] == '1'
    assert f'dilewati_{ids[0]}' not in pulih
    kode, galat, header = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={**dasar, **draf, f"kode_{ids[0]}": "asing"}, headers=_origin(server),
    )
    assert kode == 404
    _privat(header)
    assert "Baris satu\nbaris dua" not in galat
    with server.buka() as kon:
        assert kon.execute(
            "SELECT jawaban FROM jawaban WHERE sesi_soal_id=?", (ids[0],)
        ).fetchone() is None


def test_draf_koreksi_request_local_melintasi_consent_tanpa_autosave(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    with server.buka() as kon:
        sebelum = tuple(tuple(r) for r in kon.execute(
            "SELECT jawaban, cara FROM jawaban WHERE sesi_soal_id IN (?,?) ORDER BY sesi_soal_id", ids
        ).fetchall())
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi),
             "inline_posisi": "soal", "inline_nomor": "1"}
    kode, isi, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, **draf, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"},
        headers=_origin(server),
    )
    assert kode == 200
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi
    assert "Baris satu\nbaris dua" in isi
    from test_teacher_corrections import FormKoreksi
    pulih = FormKoreksi(isi, sesi).data
    assert pulih[f'belum_{ids[0]}'] == '1'
    assert f'dilewati_{ids[0]}' not in pulih
    with server.buka() as kon:
        sesudah = tuple(tuple(r) for r in kon.execute(
            "SELECT jawaban, cara FROM jawaban WHERE sesi_soal_id IN (?,?) ORDER BY sesi_soal_id", ids
        ).fetchall())
    assert sesudah == sebelum
    assert server.provider.panggilan == []


def test_draf_koreksi_riwayat_post_mempertahankan_form_dan_tidak_nested(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal", "inline_nomor": "1"}
    _, consent, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, **draf, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', consent).group(1)
    _, chat_html, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, **draf, "resource_version": versi, "kategori": "soal_resmi", "mode_chat": "aktif",
              "request_id": "buka_history_123", "setuju_konteks": "1"}, headers=_origin(server),
    )
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html).group(1)
    kode, isi, _ = server.minta(
        "/pendamping/inline/riwayat", cookie=token,
        data={**dasar, **draf, "chat": chat, "pilih_chat": chat}, headers=_origin(server),
    )
    assert kode == 200
    assert isi.count(f'<form id="form-koreksi-{sesi}" method="post" action="/sesi/{sesi}">') == 1
    assert "Baris satu\nbaris dua" in isi
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi


def test_provider_gagal_merender_host_dengan_draf_tetap_dan_tanpa_autosave(server, monkeypatch):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal", "inline_nomor": "1"}
    # Consent, konteks, dan chat lewat jalur inline yang sama.
    _, consent, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, **draf, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', consent).group(1)
    _, chat_html, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, **draf, "resource_version": versi, "kategori": "soal_resmi", "mode_chat": "aktif",
              "request_id": "buka_gagal_123", "setuju_konteks": "1"}, headers=_origin(server),
    )
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html).group(1)
    monkeypatch.setattr(
        assistant_service, "panggil_provider_default",
        lambda _pesan: (_ for _ in ()).throw(ValueError("provider sintetis gagal")),
    )
    kode, isi, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token,
        data={**dasar, **draf, "chat": chat, "request_id": "req_gagal_sintetis", "pesan": "Tolong bantu."},
        headers=_origin(server),
    )
    assert kode == 409
    assert "Pendamping belum bisa menjawab" in isi
    assert "Baris satu\nbaris dua" in isi
    assert f'name="jwb_{ids[0]}"\n               value=""' in isi
    with server.buka() as kon:
        assert kon.execute("SELECT jawaban FROM jawaban WHERE sesi_soal_id=?", (ids[0],)).fetchone() is None


def test_consent_dicabut_menyembunyikan_transkrip_inline(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    _, pilih, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={**dasar, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', pilih).group(1)
    _, chat_html, _ = server.minta(
        "/pendamping/inline/mulai", cookie=token,
        data={**dasar, "resource_version": versi, "kategori": "ringkasan_netral", "mode_chat": "aktif",
              "request_id": "buka_revoke_123", "setuju_konteks": "1"}, headers=_origin(server),
    )
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', chat_html).group(1)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        izin = kon.execute("SELECT id,versi FROM persetujuan WHERE account_id=? ORDER BY versi DESC LIMIT 1", (akun,)).fetchone()
        assistant_store.cabut_persetujuan(kon, akun, izin["id"], versi_diharapkan=izin["versi"], sekarang=99)
        kon.commit()
    kode, isi, _ = server.minta(f"/anak/{anak}?bantuan=rencana&chat={chat}", cookie=token)
    assert kode == 200
    assert "Sebelum memakai bantuan" in isi
    assert "Bantuan terkait" not in isi
    assert "Pesan untuk Pendamping" not in isi


def test_chat_resource_lain_ditolak_identik_dan_draf_tidak_dipantulkan(server):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    # Siapkan consent umum secara sintetis lewat endpoint existing.
    server.minta(
        "/pendamping/inline/persetujuan", cookie=token,
        data={"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana",
              "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"}, headers=_origin(server),
    )
    with server.buka() as kon_data:
        import assistant_context
        konteks = assistant_context.ambil(kon_data, "anak", str(anak), pemilik="guru")
    with assistant_schema.buka() as kon:
        grant = assistant_store.beri_persetujuan_konteks(
            kon, auth.cari_akun("guru")["id_akun"], jenis="anak", resource_id=str(anak),
            resource_version=konteks.versi, kategori=konteks.kategori, sekarang=1,
        )
        chat = assistant_store.buat_chat(
            kon, auth.cari_akun("guru")["id_akun"], "aktif", sekarang=1,
            context_kind="anak", context_id=str(anak), context_version=grant.versi,
            context_resource_version=konteks.versi, context_category=konteks.kategori,
        )
        kon.commit()
    ids, draf = _draf(server, sesi)
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal", "inline_nomor": "1"}
    data = {**dasar, **draf, "chat": chat.id, "request_id": "req_sintetis_asing", "pesan": "rahasia-draf"}
    asing = server.minta("/pendamping/inline/pesan", cookie=token, data=data, headers=_origin(server))
    hilang = server.minta("/pendamping/inline/pesan", cookie=token,
                          data={**data, "chat": "chat_" + "f" * 32}, headers=_origin(server))
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert "rahasia-draf" not in asing[1]
    assert server.provider.panggilan == []
