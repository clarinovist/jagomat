"""HTTP nyata host Pendamping inline: principal, draft, header, dan side effect."""

from pathlib import Path
import re
import sqlite3
import sys
import urllib.parse
import urllib.request

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


def test_draf_format_latihan_tidak_hilang_pada_buka_dan_tutup(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    data = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': 'latihan',
            'topik': 'campuran', 'jumlah_soal': '15', 'mode': 'diagnostik',
            'hadir_timer_mode': '1', 'durasi_menit': '47', 'timer_auto': '0',
            'format_jawaban': 'pilihan_ganda'}
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    for aksi in ('buka', 'tutup'):
        kode, isi, _ = server.minta('/pendamping/inline/' + aksi, cookie=token,
                                   data=data, headers=_origin(server))
        assert kode == 200
        assert 'value="pilihan_ganda" selected' in isi
        assert 'value="15" selected' in isi
        assert 'value="47"' in isi
        assert f'href="/anak/{anak}?section=latihan" aria-current="page"' in isi
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []


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
    assert kode == 200 and 'formaction="/pendamping/inline/buka"' in biasa
    kode, profil, header = server.minta(
        f"/anak/{anak}?bantuan=rencana", cookie=token
    )
    assert kode == 200
    _privat(header)
    assert 'id="bantuan-rencana"' in profil
    assert "Sebelum memakai bantuan" in profil
    assert 'data-bagikan-url=' not in profil
    assert 'action="/pendamping/inline/tutup"' in profil
    assert "fonts.googleapis.com" not in profil
    assert profil.count("<script>") == 1
    assert f"script-src 'sha256-{__import__('assistant_browser').HASH_CSP}'" in header["Content-Security-Policy"]
    assert "connect-src 'self'" in header["Content-Security-Policy"]
    assert not assistant_schema.BAWAAN.exists()
    assert server.provider.panggilan == []

    kode, sesi_html, header = server.minta(
        f"/sesi/{sesi}?bantuan=soal&nomor=1", cookie=token
    )
    assert kode == 200
    _privat(header)
    assert 'id="bantuan-soal-1"' in sesi_html
    assert "fonts.googleapis.com" not in sesi_html
    assert sesi_html.count("<script>") == 1
    assert f"script-src 'sha256-{__import__('assistant_browser').HASH_CSP}'" in header["Content-Security-Policy"]
    assert "Tutup bantuan untuk membuka aksi pembatalan atau hapus." in sesi_html
    assert 'onsubmit="return confirm(' not in sesi_html


def test_respons_fragmen_buka_dan_tutup_tidak_merender_atau_menulis_host(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"}
    header = {**_origin(server), "X-Pendamping-Panel": "fragment"}
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, respons = server.minta(
        "/pendamping/inline/buka", cookie=token, data=dasar, headers=header,
    )
    assert kode == 200
    assert isi.startswith('<aside class="pendamping-inline pendamping-panel-kanan"')
    assert '<main' not in isi and 'Sebelum memakai bantuan' in isi
    assert respons["Cache-Control"] == "no-store"
    assert "script-src" not in respons["Content-Security-Policy"]
    assert "<script" not in isi
    kode, tutup, _ = server.minta(
        "/pendamping/inline/tutup", cookie=token, data=dasar, headers=header,
    )
    assert kode == 200
    assert 'class="pendamping-inline pendamping-panel-kanan"' in tutup
    assert 'hidden aria-hidden="true"' in tutup
    assert '<main' not in tutup
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []


def test_buka_fragmen_latihan_tidak_menerima_draf_pekerjaan(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    header = {**_origin(server), "X-Pendamping-Panel": "fragment"}
    kode, isi, _ = server.minta(
        "/pendamping/inline/buka", cookie=token,
        data={**dasar, "topik": "campuran", "jumlah_soal": "15", "mode": "drill",
              "hadir_timer_mode": "1", "timer_mode": "sesi", "durasi_menit": "47", "timer_auto": "1"},
        headers=header,
    )
    assert kode == 404
    assert '<option value="campuran"' not in isi
    assert 'durasi_menit' not in isi
    assert server.provider.panggilan == []


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
    assert kode == 200 and normal.count('<script>') == 1
    kode, sesi_assisted, _ = server.minta(f"/sesi/{sesi}?bantuan=soal&nomor=1", cookie=token)
    assert kode == 200 and 'onsubmit="return confirm(' not in sesi_assisted
    ids, draf = _draf(server, sesi)
    kode, sesi_normal, _ = server.minta(
        "/pendamping/inline/tutup", cookie=token,
        data={"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "soal",
              "inline_nomor": "1", **draf}, headers=_origin(server),
    )
    assert kode == 200 and sesi_normal.count('<script>') == 1
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
    assert kode == 200 and "Bantuan mendampingi belajar" in isi
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


@pytest.mark.parametrize('mode', ['aktif', 'tanpa_memori'])
@pytest.mark.parametrize('fragmen', [False, True])
def test_satu_cta_tetap_menolak_tanpa_izin_konteks_dan_tidak_mengubah_data(server, mode, fragmen):
    token = _token_guru(server)
    anak = server.ids_inline[0]
    dasar = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': 'latihan'}
    headers = _origin(server)
    if fragmen:
        headers['X-Pendamping-Panel'] = 'fragment'
    kode, pilih, _ = server.minta('/pendamping/inline/persetujuan', cookie=token,
        data={**dasar, 'kebijakan': assistant_policy.VERSI_KEBIJAKAN, 'setuju': '1'}, headers=headers)
    assert kode == 200
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', pilih).group(1)
    with assistant_schema.buka() as kon:
        sebelum = tuple(kon.iterdump())
    data = {**dasar, 'resource_version': versi, 'kategori': 'ringkasan_netral',
            'mode_chat': mode, 'request_id': 'buka_izin_ux'}
    kode, _, _ = server.minta('/pendamping/inline/mulai', cookie=token, data=data, headers=headers)
    assert kode == 400
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []
    kode, isi, _ = server.minta('/pendamping/inline/mulai', cookie=token,
        data={**data, 'setuju_konteks': '1'}, headers=headers)
    assert kode == 200 and 'Mau dibantu apa?' in isi
    with assistant_schema.buka() as kon:
        chat = kon.execute('SELECT mode_memori, context_kind, context_id FROM chat').fetchone()
        assert tuple(chat) == (mode, 'anak', str(anak))
    assert server.provider.panggilan == []


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


@pytest.mark.parametrize('jenis_draf', ['', 'gabungan', 'remedial'])
def test_usulan_inline_tinjau_konfirmasi_hasil_idempoten_tanpa_bukti(server, monkeypatch, jenis_draf):
    usulan_sah = {"topik_id": "pola-bilangan", "template_ids": ["deret_aritmetika"],
                  "level": "P3", "jumlah_soal": 10}
    provider = ProviderPalsu({"jawaban": "Usulan siap ditinjau.", "draft_memori": None,
                              "usulan_latihan": usulan_sah, "butuh_klarifikasi": False})
    monkeypatch.setattr(assistant_service, "panggil_provider_default", provider)
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    if jenis_draf == 'gabungan':
        dasar.update(inline_form='gabungan', jumlah_soal='15', mode='drill',
                     format_jawaban='pilihan_ganda', profil_parameter='P4')
    elif jenis_draf == 'remedial':
        from test_remedial_ui import _catat
        with server.buka() as kon:
            _catat(kon, anak, 'soal_umur', 'K')
        dasar.update(inline_form='remedial', jumlah_soal='20')
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
    if jenis_draf:
        for halaman in (tinjau, hasil, hasil_retry):
            assert f'value="{dasar["jumlah_soal"]}" selected' in halaman
            assert 'value="soal_umur" checked' not in halaman
        if jenis_draf == 'gabungan':
            assert 'value="pilihan_ganda" selected' in hasil_retry
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


def test_parser_draf_gabungan_dan_remedial_menolak_nilai_asing(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    with server.buka() as kon:
        sebelum = kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0]
        sasaran = database.sasaran_remedial_anak(kon, anak)
    gabungan = {"inline_form": "gabungan", "topik": ["pola-bilangan", "aritmetika-dasar"],
                "jumlah_soal": "15", "mode": "diagnostik", "format_jawaban": "pilihan_ganda",
                "profil_parameter": "P4"}
    import assistant_http
    import assistant_inline
    parsed = assistant_http._pisahkan_draf_inline(
        {k: ([v] if isinstance(v, str) else v) for k, v in {**dasar, **gabungan}.items()},
        assistant_inline.tujuan_anak(anak, "latihan"),
    )
    assert parsed[2].topik == ("pola-bilangan", "aritmetika-dasar")
    assert parsed[0] == {k: [v] for k, v in dasar.items()}
    import pytest
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_gabungan(
            {"topik": ["pola-bilangan", "asing"], "jumlah_soal": ["15"],
             "mode": ["diagnostik"], "format_jawaban": ["pilihan_ganda"],
             "profil_parameter": ["P4"]},
            __import__('topics').daftar_topik(),
        )
    if sasaran:
        template = str(sasaran[0]["template_id"])
        remedial = assistant_inline.parse_draf_remedial(
            {"template_id": [template], "jumlah_soal": ["20"]}, [template]
        )
        assert remedial.template_id == (template,) and remedial.jumlah_soal == "20"
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0] == sebelum
    assert server.provider.panggilan == []


def _post_multi(server, token, aksi, data, *, fragment=False):
    req = urllib.request.Request(
        server.alamat + '/pendamping/inline/' + aksi,
        data=urllib.parse.urlencode(data, doseq=True).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded',
                 'Cookie': f'osn_sesi={token}', **_origin(server),
                 **({'X-Pendamping-Panel': 'fragment'} if fragment else {})},
    )
    try:
        respons = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as galat:
        respons = galat
    with respons:
        return respons.status, respons.read().decode()


@pytest.mark.parametrize('jenis', ['manual', 'gabungan', 'remedial'])
def test_semua_draf_native_melewati_consent_chat_status_history_error_memori(server, jenis):
    from test_remedial_ui import _catat
    token = _token_guru(server)
    anak = server.ids_inline[0]
    with server.buka() as kon:
        _catat(kon, anak, 'soal_umur', 'K')
        sebelum = tuple(kon.iterdump())
    dasar = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': 'latihan'}
    draf = {
        'manual': {'inline_form': 'manual', 'topik': 'campuran', 'jumlah_soal': '15',
                   'mode': 'drill', 'hadir_timer_mode': '1', 'durasi_menit': '49',
                   'timer_auto': '0', 'format_jawaban': 'pilihan_ganda', 'profil_parameter': 'P4'},
        'gabungan': {'inline_form': 'gabungan', 'jumlah_soal': '15', 'mode': 'diagnostik',
                     'format_jawaban': 'pilihan_ganda', 'profil_parameter': 'P4'},
        'remedial': {'inline_form': 'remedial', 'jumlah_soal': '20'},
    }[jenis]
    def kirim(aksi, tambahan=None, kode=200):
        status, isi = _post_multi(server, token, aksi, {**dasar, **draf, **(tambahan or {})})
        assert status == kode, isi[-500:]
        assert f'value="{draf["jumlah_soal"]}" selected' in isi
        if jenis == 'manual':
            assert 'value="49"' in isi
            assert 'name="timer_mode" value="sesi" checked' not in isi
        elif jenis == 'gabungan':
            assert 'id="tab-gabungan"' in isi
            assert 'name="topik" value="pola-bilangan" checked' not in isi
            assert 'value="pilihan_ganda" selected' in isi
        else:
            assert 'name="template_id" value="soal_umur" checked' not in isi
        return isi
    kirim('buka')
    kirim('tutup')
    assert not assistant_schema.BAWAAN.exists()
    pilih = kirim('persetujuan', {'kebijakan': assistant_policy.VERSI_KEBIJAKAN, 'setuju': '1'})
    versi = re.search(r'name="resource_version" value="([^"]+)"', pilih).group(1)
    chat_html = kirim('mulai', {'resource_version': versi, 'kategori': 'ringkasan_netral',
                               'mode_chat': 'aktif', 'request_id': 'buka_draf_sintetis', 'setuju_konteks': '1'})
    chat = re.search(r'name="chat" value="([^"]+)"', chat_html).group(1)
    req = re.search(r'name="request_id" value="(req_[^"]+)"', chat_html).group(1)
    kirim('pesan', {'chat': chat, 'request_id': req, 'pesan': 'Pertanyaan sintetis.'})
    kirim('status', {'chat': chat, 'request_id': req})
    kirim('riwayat', {'chat': chat, 'pilih_chat': chat})
    kirim('pesan', {'chat': chat, 'request_id': 'buruk', 'pesan': 'Pertanyaan sintetis.'}, 400)
    kirim('batal-hapus-memori', {'chat': chat})
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert len(server.provider.panggilan) == 1
    muatan = str(server.provider.panggilan)
    assert 'inline_form' not in muatan and 'durasi_menit' not in muatan


@pytest.mark.parametrize('buruk', [
    {'mode': ['drill', 'diagnostik']}, {'asing': 'rahasia'},
    {'topik': ['pola-bilangan', 'asing']}, {'sumber_sesi_id': '999999'},
])
def test_draf_gabungan_field_asing_ganda_ditolak_tanpa_efek(server, buruk):
    token = _token_guru(server)
    anak = server.ids_inline[0]
    data = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': 'latihan',
            'inline_form': 'gabungan', 'jumlah_soal': '15', 'mode': 'drill',
            'format_jawaban': 'isian', 'profil_parameter': 'P4', **buruk}
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _ = _post_multi(server, token, 'buka', data)
    assert kode == 404
    assert server.provider.panggilan == []
    assert not assistant_schema.BAWAAN.exists()
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_bookmark_sesi_dibatalkan_tetap_memiliki_form_panel_mandiri(server):
    token = _token_guru(server)
    sesi = server.ids_inline[1]
    with server.buka() as kon:
        kon.execute("UPDATE sesi SET dibatalkan='2026-09-27' WHERE id=?", (sesi,))
    kode, isi, _ = server.minta(f'/sesi/{sesi}?bantuan=sesi', cookie=token)
    assert kode == 200
    assert 'action="/pendamping/inline/persetujuan"' in isi
    assert f'form="form-koreksi-{sesi}"' not in isi


def test_remedial_sumber_native_owner_valid_dipulihkan(server):
    from test_remedial_ui import _catat
    token = _token_guru(server)
    anak = server.ids_inline[0]
    with server.buka() as kon:
        sumber = _catat(kon, anak, 'soal_umur', 'K')
        sebelum = tuple(kon.iterdump())
    dasar = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': 'latihan',
             'inline_form': 'remedial', 'jumlah_soal': '20', 'sumber_sesi_id': str(sumber)}
    for aksi in ('buka', 'tutup'):
        kode, isi = _post_multi(server, token, aksi, dasar)
        assert kode == 200
        assert f'name="sumber_sesi_id" value="{sumber}"' in isi
    asing = _post_multi(server, token, 'buka', {**dasar, 'sumber_sesi_id': str(server.ids_inline[3])})
    hilang = _post_multi(server, token, 'buka', {**dasar, 'sumber_sesi_id': '999999'})
    assert asing == hilang and asing[0] == 404
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []


def test_pilih_sumber_nomor_hilang_asing_sama_404_tanpa_store(server):
    token = _token_guru(server)
    _, sesi, _, sesi_asing = server.ids_inline
    hasil = []
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    for sid, nomor in ((sesi, '999'), (sesi_asing, '1'), (999999, '1')):
        hasil.append(_post_multi(server, token, 'pilih-sumber', {
            'inline_host': 'sesi', 'inline_host_id': str(sid),
            'inline_posisi': 'sesi', 'pilih_nomor': nomor,
        }, fragment=True))
    assert all(h == hasil[0] for h in hasil)
    assert hasil[0][0] == 404
    assert not assistant_schema.BAWAAN.exists()
    assert server.provider.panggilan == []
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('tambahan', [{'setuju': ['1', '1']}, {'asing': 'x' * 110001}])
def test_payload_ganda_atau_terlalu_besar_tidak_memberi_consent(server, tambahan):
    token = _token_guru(server)
    kode, _ = _post_multi(server, token, 'persetujuan', {
        'inline_host': 'anak', 'inline_host_id': str(server.ids_inline[0]),
        'inline_posisi': 'latihan', 'kebijakan': assistant_policy.VERSI_KEBIJAKAN,
        'setuju': '1', **tambahan,
    })
    assert kode in (404, 413)
    assert not assistant_schema.BAWAAN.exists()
    assert server.provider.panggilan == []


def test_draf_gabungan_native_dipulihkan_tanpa_membuat_sesi(server):
    token = _token_guru(server)
    anak, _, _, _ = server.ids_inline
    dasar = {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "latihan"}
    gabungan = {"inline_form": "gabungan", "topik": ["pola-bilangan", "aritmetika-dasar"],
                "jumlah_soal": "15", "mode": "diagnostik", "format_jawaban": "pilihan_ganda",
                "profil_parameter": "P4"}
    with server.buka() as kon:
        sebelum = kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0]
    import urllib.request
    req = urllib.request.Request(
        server.alamat + "/pendamping/inline/buka",
        data=urllib.parse.urlencode({**dasar, **gabungan}, doseq=True).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": f"osn_sesi={token}", **_origin(server)},
    )
    with urllib.request.urlopen(req, timeout=10) as respons:
        kode, isi = respons.status, respons.read().decode()
    assert kode == 200
    assert 'value="pola-bilangan" checked' in isi and 'value="aritmetika-dasar" checked' in isi
    assert 'value="15" selected' in isi and 'value="diagnostik" checked' in isi
    assert 'value="pilihan_ganda" selected' in isi
    panel_gabungan = isi.split('id="form-latihan-gabungan-', 1)[1].split('</form>', 1)[0]
    assert panel_gabungan.count('name="profil_parameter"') == 2
    assert 'value="P5"' in panel_gabungan and 'value="P6"' in panel_gabungan
    assert 'value="P4"' not in panel_gabungan
    kartu_isi = panel_gabungan.split('<fieldset class="pilih-isi-latihan"', 1)[1].split('</fieldset>', 1)[0]
    assert 'name="profil_parameter" value="P5" checked' not in kartu_isi
    assert 'name="profil_parameter" value="P6" checked' not in kartu_isi
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id=?", (anak,)).fetchone()[0] == sebelum
    assert server.provider.panggilan == []


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


def test_pilih_soal_dari_satu_entry_panel_tetap_owner_scoped(server):
    token = _token_guru(server)
    _, sesi, _, sesi_asing = server.ids_inline
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "sesi"}
    kode, isi, _ = server.minta(
        "/pendamping/inline/pilih-sumber", cookie=token,
        data={**dasar, "pilih_nomor": "1"}, headers=_origin(server),
    )
    assert kode == 200
    assert 'id="bantuan-soal-1"' in isi and "Soal 1" in isi
    assert server.provider.panggilan == []
    asing = {"inline_host": "sesi", "inline_host_id": str(sesi_asing),
             "inline_posisi": "sesi", "pilih_nomor": "1"}
    hilang = {"inline_host": "sesi", "inline_host_id": "999999",
              "inline_posisi": "sesi", "pilih_nomor": "1"}
    a = server.minta("/pendamping/inline/pilih-sumber", cookie=token, data=asing, headers=_origin(server))
    b = server.minta("/pendamping/inline/pilih-sumber", cookie=token, data=hilang, headers=_origin(server))
    assert a[0] == b[0] == 404 and a[1] == b[1]
    assert server.provider.panggilan == []


def test_host_biasa_membuka_bantuan_via_post_dengan_draf(server):
    token = _token_guru(server)
    _, sesi, _, _ = server.ids_inline
    ids, draf = _draf(server, sesi)
    kode, awal, _ = server.minta(f"/sesi/{sesi}", cookie=token)
    assert kode == 200
    assert f'formaction="/pendamping/inline/buka/sesi/{sesi}/sesi"' in awal
    assert f'form="form-koreksi-{sesi}"' in awal
    assert awal.count('class="pendamping-pemicu"') == 1
    dasar = {"inline_host": "sesi", "inline_host_id": str(sesi), "inline_posisi": "sesi"}
    kode, isi, _ = server.minta(
        f"/pendamping/inline/buka/sesi/{sesi}/sesi", cookie=token, data=draf, headers=_origin(server),
    )
    assert kode == 200
    assert 'id="bantuan-sesi"' in isi
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
    assert isi.count('<script>') == 1 and "fonts.googleapis.com" not in isi


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
