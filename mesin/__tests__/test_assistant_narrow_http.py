"""Reuse exact-resource dan retirement melalui HTTP, bukan hanya renderer."""
import re

import pytest

import assistant_context
import assistant_inline
import assistant_policy
import assistant_schema
import assistant_store
import auth
from test_assistant_inline_http import server, _token_guru, _origin


def siapkan(server, *, nomor=None):
    token = _token_guru(server)
    anak, sesi = server.ids_inline[:2]
    target = assistant_inline.tujuan_sesi(sesi, nomor=nomor) if nomor else assistant_inline.tujuan_anak(anak)
    akun = auth.cari_akun('guru')['id_akun']
    with server.buka() as kon:
        konteks = assistant_context.ambil(kon, target.jenis_resource, target.resource_id, pemilik='guru')
    assistant_schema.siapkan()
    with assistant_schema.buka() as kon:
        izin = assistant_store.beri_persetujuan(kon, akun, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id='deepseek', kategori='chat_umum', sekarang=100)
        grant = assistant_store.beri_persetujuan_konteks(kon, akun, jenis=konteks.jenis,
            resource_id=konteks.resource_id, resource_version=konteks.versi, kategori=konteks.kategori, sekarang=101)
        chat = assistant_store.buat_chat(kon, akun, 'aktif', sekarang=102,
            context_kind=konteks.jenis, context_id=konteks.resource_id, context_version=grant.versi,
            context_resource_version=konteks.versi, context_category=konteks.kategori)
    return token, akun, target, chat, izin, grant


def test_open_reuse_tanpa_write_consent_atau_provider(server):
    token, akun, target, chat, _, _ = siapkan(server, nomor=1)
    with assistant_schema.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(target.jalur, cookie=token)
    assert kode == 200 and f'data-pendamping-chat="{chat.id}"' in isi
    assert 'id="pesan-inline"' in isi and 'name="setuju_konteks"' not in isi
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []
    # Soal kedua bukan resource sama, walau sesi/pemilik sama.
    kode, isi, _ = server.minta(assistant_inline.tujuan_sesi(target.host_id, nomor=2).jalur, cookie=token)
    assert kode == 200 and 'name="setuju_konteks"' in isi
    assert f'data-pendamping-chat="{chat.id}"' not in isi


@pytest.mark.parametrize('perubahan', ['hapus', 'konteks', 'fingerprint', 'policy', 'provider', 'reconsent'])
def test_reuse_tidak_menghidupkan_chat_tidak_sah(server, perubahan):
    token, akun, target, chat, izin, grant = siapkan(server)
    with assistant_schema.buka() as kon:
        if perubahan == 'hapus':
            assistant_store.hapus_chat(kon, akun, chat.id, versi_diharapkan=chat.versi, sekarang=103, retensi_detik=0)
        elif perubahan == 'konteks':
            assistant_store.cabut_persetujuan_konteks(kon, akun, grant.id, versi_diharapkan=grant.versi, sekarang=103)
        elif perubahan == 'fingerprint':
            kon.execute("UPDATE chat SET context_resource_version='usang' WHERE id=?", (chat.id,))
        elif perubahan == 'policy':
            assistant_store.beri_persetujuan(kon, akun, policy_version='policy-usang', provider_id='deepseek', kategori='chat_umum', sekarang=103)
        elif perubahan == 'provider':
            assistant_store.cabut_persetujuan(kon, akun, izin.id, versi_diharapkan=izin.versi, sekarang=103)
        else:
            assistant_store.cabut_persetujuan_konteks(kon, akun, grant.id, versi_diharapkan=grant.versi, sekarang=103)
            assistant_store.beri_persetujuan_konteks(kon, akun, jenis=grant.jenis,
                resource_id=grant.resource_id, resource_version=grant.resource_version, kategori=grant.kategori, sekarang=104)
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(target.jalur, cookie=token)
    assert kode == 200 and f'data-pendamping-chat="{chat.id}"' not in isi
    assert 'id="pesan-inline"' not in isi
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []


def test_picker_http_reuse_diterima_guard_browser_exact_resource(server):
    import json
    from html.parser import HTMLParser
    from test_assistant_browser import _jalankan_js
    token, akun, target, chat, _, _ = siapkan(server, nomor=1)
    with assistant_schema.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta('/pendamping/inline/pilih-sumber', cookie=token,
        data={'inline_host': 'sesi', 'inline_host_id': str(target.host_id),
              'inline_posisi': 'sesi', 'pilih_nomor': '1'},
        headers={**_origin(server), 'X-Pendamping-Panel': 'fragment'})
    assert kode == 200
    class Panel(HTMLParser):
        atribut = None
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == 'aside' and 'pendamping-panel-kanan' in a.get('class', ''):
                self.atribut = a
    parser = Panel()
    parser.feed(isi)
    a = parser.atribut
    assert a['data-pendamping-chat'] == chat.id
    dataset = {''.join([k.split('-')[1]] + [v.title() for v in k.split('-')[2:]]): v
               for k, v in a.items() if k.startswith('data-')}
    harap = {'host': 'sesi', 'id': str(target.host_id), 'posisi': 'sesi',
             'resource': 'sesi', 'resourceId': str(target.host_id), 'chat': ''}
    _jalankan_js('const harap=' + json.dumps(harap) + '; const dataset=' + json.dumps(dataset) + ''';
const panel={classList:{contains:n=>n==='pendamping-panel-kanan'},dataset};
assert.equal(uji.cocokPanel(harap,panel,'pilih-sumber',new URLSearchParams({pilih_nomor:'1'})),true);
''')
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert server.provider.panggilan == []


def test_lookup_exact_owner_jenis_resource_dan_grant(server):
    from dataclasses import replace
    import assistant_view
    token, akun, target, chat, _, grant = siapkan(server, nomor=1)
    with server.buka() as kon:
        konteks = assistant_context.ambil(kon, target.jenis_resource, target.resource_id, pemilik='guru')
    with assistant_schema.buka() as kon:
        assert assistant_view.chat_terbaru_sah(kon, 'akun_' + 'f' * 32, konteks, pemilik='guru') is None
        assert assistant_view.chat_terbaru_sah(kon, akun, konteks, pemilik='orang-lain') is None
        for beda in (replace(konteks, resource_id=f'{target.host_id}:2'), replace(konteks, jenis='sesi')):
            assert assistant_view.chat_terbaru_sah(kon, akun, beda, pemilik='guru') is None
        # Grant baru dengan snapshot sama tetap tidak mengesahkan chat grant lama.
        assistant_store.beri_persetujuan_konteks(kon, akun, jenis=grant.jenis,
            resource_id=grant.resource_id, resource_version=grant.resource_version, kategori=grant.kategori, sekarang=104)
        assert assistant_view.chat_terbaru_sah(kon, akun, konteks, pemilik='guru') is None


def test_reuse_histori_tetap_tersedia_saat_kuota_habis(server, monkeypatch):
    import assistant_entitlement_runtime as entitlement
    token, akun, target, chat, _, _ = siapkan(server)
    monkeypatch.setattr(entitlement, 'status', lambda *_a, **_k: entitlement.StatusRuntime(
        'kuota_habis', paket='jago_pro', enforcement_aktif=True))
    kode, isi, _ = server.minta(target.jalur, cookie=token)
    assert kode == 200 and f'data-pendamping-chat="{chat.id}"' in isi
    assert 'Riwayat tetap dapat dibaca' in isi and 'id="pesan-inline"' not in isi
    assert server.provider.panggilan == []


def test_draft_lama_tidak_dikonfirmasi_atau_diubah_tapi_bisa_dihapus(server):
    token, akun, target, chat, _, _ = siapkan(server)
    with assistant_schema.buka() as kon:
        item = assistant_store.tambah_memori(kon, akun, 'Gunakan kalimat pendek.',
            sumber_chat_id=chat.id, dikonfirmasi=False, sekarang=103)
        sebelum = tuple(kon.iterdump())
    dasar = {'inline_host': 'anak', 'inline_host_id': str(target.host_id), 'inline_posisi': 'rencana',
             'chat': chat.id, 'memori': item.id, 'versi_item': str(item.versi)}
    for aksi in ('konfirmasi-memori', 'ubah-memori'):
        kode, isi, _ = server.minta('/pendamping/inline/' + aksi, cookie=token, data=dasar, headers=_origin(server))
        assert kode == 410 and 'dihentikan' in isi
        with assistant_schema.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    kode, _, _ = server.minta('/pendamping/inline/hapus-memori', cookie=token,
        data={**dasar, 'persetujuan_hapus': '1'}, headers=_origin(server))
    assert kode == 200
    with assistant_schema.buka() as kon:
        assert not assistant_store.daftar_memori(kon, akun)
    assert server.provider.panggilan == []
