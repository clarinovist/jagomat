"""Kontrak progressive enhancement chat; seluruh state/provider sintetis."""

import base64
import hashlib
import re

import pytest

import assistant_browser
import assistant_schema
import assistant_service
from test_assistant_inline_http import server, _origin, _draf
from test_assistant_runtime import _token_guru
import assistant_policy


def mulai(server, *, soal=False):
    token = _token_guru(server)
    anak, sesi, _, _ = server.ids_inline
    data = ({"inline_host": "sesi", "inline_host_id": str(sesi),
             "inline_posisi": "soal", "inline_nomor": "1", **_draf(server, sesi)[1]}
            if soal else {"inline_host": "anak", "inline_host_id": str(anak), "inline_posisi": "rencana"})
    _, pilih, _ = server.minta(
        "/pendamping/inline/persetujuan", cookie=token, headers=_origin(server),
        data={**data, "kebijakan": assistant_policy.VERSI_KEBIJAKAN, "setuju": "1"},
    )
    versi = re.search(r'name="resource_version" value="([^"]+)"', pilih).group(1)
    kode, isi, header = server.minta(
        "/pendamping/inline/mulai", cookie=token, headers=_origin(server),
        data={**data, "resource_version": versi, "kategori": "soal_resmi" if soal else "ringkasan_netral",
              "mode_chat": "aktif", "request_id": "buka_browser_sintetis", "setuju_konteks": "1"},
    )
    assert kode == 200
    data["chat"] = re.search(r'name="chat" value="([^"]+)"', isi).group(1)
    data["request_id"] = re.search(r'name="request_id" value="(req_[^"]+)"', isi).group(1)
    return token, data, isi, header


def test_izin_skrip_hanya_hash_persis_pada_chat():
    biasa = b'<body><p>Tanpa chat</p></body>'
    assert assistant_browser.lengkapi_respons(biasa) == (biasa, "")
    isi, izin = assistant_browser.lengkapi_respons(b'<body><aside data-pendamping-chat="chat_sintetis"></aside></body>')
    skrip = re.search(rb'<script>(.*?)</script>', isi, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(skrip).digest()).decode()
    assert izin == f"script-src 'sha256-{digest}'; connect-src 'self'; "
    assert "unsafe-inline" not in izin and "script-src 'self'" not in izin


@pytest.mark.parametrize("soal", [False, True])
def test_chat_native_dan_fetch_memakai_guard_dan_request_yang_sama(server, soal):
    token, data, isi, header = mulai(server, soal=soal)
    assert isi.count('<script>') == 1
    assert f'data-pendamping-chat="{data["chat"]}"' in isi
    assert f"script-src 'sha256-{assistant_browser.HASH_CSP}'" in header['Content-Security-Policy']
    assert "connect-src 'self'" in header['Content-Security-Policy']
    assert "script-src 'unsafe-inline'" not in header['Content-Security-Policy']
    assert header['Cache-Control'] == 'no-store'
    muatan = {**data, "pesan": "Bantu jelaskan sumber ini."}
    for _ in range(2):
        kode, hasil, header = server.minta(
            '/pendamping/inline/pesan', cookie=token, data=muatan, headers=_origin(server))
        assert kode == 200
        assert f'data-request-id="{data["request_id"]}:jawaban"' in hasil
        assert "Mari kita bahas" in hasil
        if soal:
            assert "Baris satu\nbaris dua" in hasil
    assert len(server.provider.panggilan) == 1
    assert "Baris satu" not in str(server.provider.panggilan)
    with server.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM jawaban').fetchone()[0] == 0


def test_fetch_asing_sama_404_dan_tidak_memanggil_provider(server):
    token, data, _, _ = mulai(server)
    hasil = []
    for identitas in (server.ids_inline[2], 999999):
        hasil.append(server.minta('/pendamping/inline/pesan', cookie=token,
            data={**data, "inline_host_id": str(identitas), "pesan": "Teks sintetis."}, headers=_origin(server)))
    assert hasil[0][:2] == hasil[1][:2]
    assert hasil[0][0] == 404
    assert '<script>' not in hasil[0][1]
    assert server.provider.panggilan == []
    with assistant_schema.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM operasi').fetchone()[0] == 0


def test_fetch_status_hanya_baca_request_terikat_chat(server):
    token, data, _, _ = mulai(server)
    server.minta('/pendamping/inline/pesan', cookie=token,
                 data={**data, 'pesan': 'Bantu jelaskan.'}, headers=_origin(server))
    kode, isi, _ = server.minta('/pendamping/inline/status', cookie=token,
                               data=data, headers=_origin(server))
    assert kode == 200
    assert f'data-request-id="{data["request_id"]}:jawaban"' in isi
    assert len(server.provider.panggilan) == 1
    kode, _, _ = server.minta('/pendamping/inline/status', cookie=token,
                              data={**data, 'request_id': 'req_tidak_ada'}, headers=_origin(server))
    assert kode == 404


def test_provider_gagal_tanpa_marker_selesai_dan_request_baru(server, monkeypatch):
    token, data, _, _ = mulai(server)
    def gagal(_pesan):
        raise ValueError('Galat sintetis')
    monkeypatch.setattr(assistant_service, 'panggil_provider_default', gagal)
    kode, isi, _ = server.minta('/pendamping/inline/pesan', cookie=token,
        data={**data, 'pesan': 'Bantu jelaskan.'}, headers=_origin(server))
    assert kode == 409
    assert 'Pendamping belum bisa menjawab' in isi
    assert f'data-request-id="{data["request_id"]}:jawaban"' not in isi
    assert re.search(r'name="request_id" value="(req_[^"]+)"', isi).group(1) != data['request_id']


def test_marker_chat_dan_request_tidak_bisa_menyisipkan_atribut():
    from test_assistant_inline_pages import Chat, Pesan
    import assistant_components
    import assistant_inline
    chat = Chat('chat_" onload="jahat')
    pesan = Pesan('asisten', '<script>jahat()</script>')
    pesan.request_id = 'req_" onload="jahat'
    isi = assistant_components.panel_chat(assistant_inline.tujuan_anak(1), chat, (pesan,), (), sumber={})
    assert 'data-pendamping-chat="chat_&quot; onload=&quot;jahat"' in isi
    assert 'data-request-id="req_&quot; onload=&quot;jahat"' in isi
    assert '<script>' not in isi


def test_kontrol_pemulihan_tersembunyi_tidak_ditampilkan_css():
    import style_stitch
    assert '.pendamping-inline button[hidden] { display: none; }' in style_stitch.GAYA_STITCH


def test_skrip_tidak_memperluas_pengiriman_atau_penyimpanan_browser():
    skrip = assistant_browser.SKRIP_CHAT
    assert "fetch('/pendamping/inline/' + permintaan.aksi" in skrip
    assert "redirect: 'error'" in skrip
    assert "credentials: 'same-origin', cache: 'no-store'" in skrip
    assert 'panel.replaceWith(baru)' in skrip
    assert 'document.body.replaceWith' not in skrip
    assert "baru.dataset.pendampingChat === panel.dataset.pendampingChat" in skrip
    for terlarang in ('localStorage', 'sessionStorage', 'document.cookie', 'sendBeacon', 'innerHTML', 'eval('):
        assert terlarang not in skrip
