"""Regresi Pendamping: fakta aplikasi minimum, versi dan empat tab native."""
import json
import re

import assistant_components
import assistant_http
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
import auth
import profile_history

import pytest

import assistant_context
import assistant_inline
import database
from test_assistant_inline_http import server, _token_guru, _origin


def test_ringkasan_memilih_antrean_otoritatif_dan_tidak_mengirim_identitas(server):
    anak, sesi, asing, sesi_asing = server.ids_inline
    with server.buka() as kon:
        konteks = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        assert konteks.muatan['tinjauan']['sesi'] == [
            {'alias': 'Sesi A', 'jumlah_soal': 2, 'status': 'perlu_ditinjau'}]
        assert konteks.tautan_sesi == (('Sesi A', sesi),)
        assert konteks.muatan['posisi']['total'] == 6
        assert set(konteks.muatan) == {'jenis', 'level', 'tahap', 'tersedia_pada', 'posisi', 'target', 'tinjauan'}
        assert set(konteks.muatan['target']) == {'total', 'dipelajari', 'terbukti', 'perlu_cek', 'belum_dinilai'}
        assert set(konteks.muatan['tinjauan']) == {'urutan', 'sesi'}
        assert assistant_context.konteks_anak(kon, asing, pemilik='guru') is None
    mentah = json.dumps(konteks.muatan)
    for terlarang in ('Anak Inline', 'Asing', 'siswa_id', 'sesi_id', 'jawaban', 'diagnosis', 'catatan', 'pemilik'):
        assert terlarang not in mentah


def test_versi_berubah_saat_sesi_dikirim_dan_dibatalkan(server):
    anak = server.ids_inline[0]
    with server.buka() as kon:
        sesi = database.buat_sesi(kon, anak, seed=47, jumlah_soal=2)
        awal = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        database.tandai_selesai(kon, sesi)
        terkirim = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        assert terkirim.versi != awal.versi
        kon.execute("UPDATE sesi SET dibatalkan='2026-10-20 00:00:00' WHERE id=?", (sesi,))
        batal = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        assert batal.versi != terkirim.versi
        assert assistant_context.versi_ringkasan_anak(kon, anak, pemilik='guru') == batal.versi


@pytest.mark.parametrize('tab', ['rencana', 'latihan', 'riwayat', 'perkembangan'])
def test_panel_native_menjaga_tab_asal(server, tab):
    token = _token_guru(server)
    anak = server.ids_inline[0]
    target = assistant_inline.tujuan_anak(anak, tab)
    kode, isi, _ = server.minta(target.jalur, cookie=token)
    assert kode == 200
    assert f'href="/anak/{anak}?bantuan={tab}#bantuan-{tab}" aria-current="page"' in isi
    assert f'name="inline_posisi" value="{tab}"' in isi
    kode, tutup, _ = server.minta('/pendamping/inline/tutup', cookie=token,
        data={'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': tab},
        headers=_origin(server))
    assert kode == 200
    assert f'href="/anak/{anak}?section={tab}" aria-current="page"' in tutup


def _mulai(server, tab='rencana'):
    token = _token_guru(server)
    anak = server.ids_inline[0]
    dasar = {'inline_host': 'anak', 'inline_host_id': str(anak), 'inline_posisi': tab}
    kode, isi, _ = server.minta('/pendamping/inline/persetujuan', cookie=token,
        data={**dasar, 'kebijakan': assistant_policy.VERSI_KEBIJAKAN, 'setuju': '1'}, headers=_origin(server))
    assert kode == 200
    versi = re.search(r'name="resource_version" value="([0-9a-f]+)"', isi).group(1)
    kode, isi, _ = server.minta('/pendamping/inline/mulai', cookie=token,
        data={**dasar, 'resource_version': versi, 'kategori': 'ringkasan_netral',
              'mode_chat': 'aktif', 'request_id': 'buka_regresi_pendamping', 'setuju_konteks': '1'}, headers=_origin(server))
    assert kode == 200
    chat = re.search(r'name="chat" value="(chat_[0-9a-f]{32})"', isi).group(1)
    return token, dasar, chat, isi


@pytest.mark.parametrize('tab', ['rencana', 'latihan', 'riwayat', 'perkembangan'])
def test_payload_provider_sama_di_empat_tab_dan_alias_hanya_lokal(server, tab):
    token, dasar, chat, isi = _mulai(server, tab)
    request = re.search(r'name="request_id" value="(req_[^"]+)"', isi).group(1)
    kode, hasil, _ = server.minta('/pendamping/inline/pesan', cookie=token,
        data={**dasar, 'chat': chat, 'request_id': request, 'pesan': 'Sesi mana ditinjau dulu?'}, headers=_origin(server))
    assert kode == 200
    payload = json.loads(server.provider.panggilan[0][-1]['content'])['konteks']
    with server.buka() as kon:
        assert payload == assistant_context.konteks_anak(kon, server.ids_inline[0], pemilik='guru').muatan
    assert 'tautan_sesi' not in payload and 'sesi_id' not in json.dumps(payload)
    assert f'Sesi A · sesi #{server.ids_inline[1]}' in hasil
    assert 'Dijawab AI, bisa keliru' in hasil
    assert 'role="log"' in hasil
    assert f'name="inline_posisi" value="{tab}"' in hasil


def test_antrean_memakai_konfirmasi_aktif_terlama_batas_tiga(server):
    anak, sesi = server.ids_inline[:2]
    with server.buka() as kon:
        kon.execute("UPDATE sesi SET tanggal='2026-01-01',dikonfirmasi_guru='2026-01-02' WHERE id=?", (sesi,))
        ids = [sesi]
        for i in range(5):
            baru = database.buat_sesi(kon, anak, seed=70+i, jumlah_soal=1)
            kon.execute('UPDATE sesi SET tanggal=? WHERE id=?', (f'2026-01-0{2+i}', baru))
            database.tandai_selesai(kon, baru)
            ids.append(baru)
        butir = database.isi_sesi(kon, ids[1])[0]['sesi_soal_id']
        database.konfirmasi_hasil(kon, ids[1], guru='guru', dilewati={butir})
        database.batalkan_sesi(kon, ids[2], 'Sintetis')
        kon.execute('UPDATE sesi SET selesai=NULL WHERE id=?', (ids[3],))
        assert [r['id'] for r in profile_history.metadata_tinjauan(kon, anak)] == [ids[0], ids[4], ids[5]]
        kon.execute("UPDATE sesi SET fingerprint_konfirmasi='usang' WHERE id=?", (ids[1],))
        assert [r['id'] for r in profile_history.metadata_tinjauan(kon, anak)] == [ids[0], ids[1], ids[4]]


def test_binding_alias_berubah_meski_payload_sama(server):
    anak, sesi = server.ids_inline[:2]
    with server.buka() as kon:
        berikut = database.buat_sesi(kon, anak, seed=60, jumlah_soal=2)
        kon.execute("UPDATE sesi SET tanggal='2026-01-01' WHERE id=?", (sesi,))
        awal = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        kon.execute('UPDATE sesi SET selesai=NULL WHERE id=?', (sesi,))
        database.tandai_selesai(kon, berikut)
        akhir = assistant_context.konteks_anak(kon, anak, pemilik='guru')
        assert awal.muatan == akhir.muatan
        assert awal.versi != akhir.versi


def test_izin_v1_tidak_mengirim_v2_dan_histori_tidak_memetakan_alias_baru(server):
    token, dasar, cid, _ = _mulai(server)
    akun = auth.cari_akun('guru')['id_akun']
    anak = server.ids_inline[0]
    with server.buka() as kon:
        lama = assistant_context._versi_bukti_anak(kon, anak, pemilik='guru')
    with assistant_schema.buka() as kon:
        grant = assistant_store.beri_persetujuan_konteks(kon, akun, jenis='anak', resource_id=str(anak),
            resource_version=lama, kategori='ringkasan_netral', sekarang=100)
        chat = assistant_store.buat_chat(kon, akun, 'aktif', sekarang=101, context_kind='anak',
            context_id=str(anak), context_version=grant.versi, context_resource_version=lama, context_category='ringkasan_netral')
    kode, isi, _ = server.minta(assistant_inline.tujuan_anak(anak, chat_id=chat.id).jalur, cookie=token)
    assert kode == 200 and 'hanya baca' in isi
    assert not re.search(r'<textarea[^>]*name="pesan"', isi)
    assert 'Sesi A · sesi #' not in isi
    assert 'Tinjau izin ringkasan terbaru' in isi
    kode, _, _ = server.minta('/pendamping/inline/pesan', cookie=token,
        data={**dasar, 'chat': chat.id, 'request_id': 'req_v1_ditolak', 'pesan': 'Tinjau sesi.'}, headers=_origin(server))
    assert kode in (404, 409) and server.provider.panggilan == []


def test_konteks_berubah_saat_provider_tidak_menyimpan_jawaban(server, monkeypatch):
    token, dasar, chat, isi = _mulai(server)
    anak, sesi = server.ids_inline[:2]
    def provider(pesan):
        with server.buka() as kon:
            kon.execute("UPDATE sesi SET dibatalkan='2026-10-20' WHERE id=?", (sesi,))
        return server.provider(pesan)
    monkeypatch.setattr(assistant_service, 'panggil_provider_default', provider)
    kode, _, _ = server.minta('/pendamping/inline/pesan', cookie=token,
        data={**dasar, 'chat': chat, 'request_id': 'req_berubah_di_network', 'pesan': 'Tinjau sesi.'}, headers=_origin(server))
    assert kode == 409
    with assistant_schema.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM pesan WHERE chat_id=?', (chat,)).fetchone()[0] == 0


def test_tautan_bukan_dari_teks_model_dan_stale_tanpa_alias():
    from types import SimpleNamespace
    chat = SimpleNamespace(id='chat_' + 'a'*32, mode_memori='aktif')
    pesan = SimpleNamespace(peran='asisten', teks='Sesi Z https://asing.invalid/sesi/99', request_id='req_sintetis')
    konteks = assistant_context.KonteksPendamping('anak', '7', 'v2', 'ringkasan_netral', {}, (('Sesi A', 8),))
    panel = assistant_components.panel_chat(assistant_inline.tujuan_anak(7), chat, (pesan,), (),
        sumber={}, konteks=konteks, hanya_baca=True)
    assert 'href="https://asing' not in panel
    assert 'href="/sesi/8"' not in panel
