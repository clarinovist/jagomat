"""Mutasi terisolasi pada guard kandidat sempit yang dipanggil regresi."""
import pytest

import assistant_http
import assistant_inline_http
import assistant_client
import assistant_policy
import assistant_view
from test_assistant_manage_mutation import pasang
from test_assistant_narrow import test_field_retired_ditolak_bukan_dibuang as cek_field
from test_assistant_narrow_http import (
    server, test_reuse_tidak_menghidupkan_chat_tidak_sah as cek_reuse,
    test_draft_lama_tidak_dikonfirmasi_atau_diubah_tapi_bisa_dihapus as cek_draft,
)


def test_mutasi_key_ganda_terdeteksi(monkeypatch):
    from test_assistant_narrow import test_client_menolak_json_key_ganda as cek_client
    pasang(monkeypatch, assistant_client, '_objek_unik', 'if kunci in hasil:', 'if False:')
    with pytest.raises(pytest.fail.Exception, match='DID NOT RAISE'):
        cek_client(monkeypatch)


def test_mutasi_field_extra_ditolak(monkeypatch):
    pasang(monkeypatch, assistant_policy, 'validasi_respons',
        'set(data) != {', 'not set(data) >= {')
    with pytest.raises(pytest.fail.Exception, match='DID NOT RAISE'):
        cek_field({'draft_memori': None, 'usulan_latihan': None})


@pytest.mark.parametrize('perubahan', ['konteks', 'policy', 'provider'])
def test_mutasi_hak_baca_lookup_terdeteksi(server, monkeypatch, perubahan):
    pasang(monkeypatch, assistant_view, 'chat_terbaru_sah',
        'if not hak_baca_chat(kon_priv, account_id, chat, pemilik=pemilik):', 'if False:')
    # Guard reader berikutnya tetap memblokir; uji lookup secara langsung agar
    # mutasi tidak lolos hanya karena lapisan kedua menutupi celah selector.
    from test_assistant_narrow_http import siapkan
    import assistant_context
    import assistant_schema
    import assistant_store
    token, akun, target, chat, izin, grant = siapkan(server)
    with server.buka() as kon:
        konteks = assistant_context.ambil(kon, target.jenis_resource, target.resource_id, pemilik='guru')
    with assistant_schema.buka() as kon:
        if perubahan == 'konteks':
            kon.execute('UPDATE persetujuan_konteks SET dicabut=103 WHERE id=?', (grant.id,))
        elif perubahan == 'policy':
            kon.execute("UPDATE persetujuan SET policy_version='usang' WHERE id=?", (izin.id,))
        else:
            kon.execute('UPDATE persetujuan SET dicabut=103 WHERE id=?', (izin.id,))
        # Assertion invariant harus merah saat guard dinonaktifkan.
        with pytest.raises(AssertionError):
            assert assistant_view.chat_terbaru_sah(kon, akun, konteks, pemilik='guru') is None


def test_mutasi_fingerprint_lookup_terdeteksi(server, monkeypatch):
    pasang(monkeypatch, assistant_view, 'chat_terbaru_sah',
        'AND c.context_resource_version = ?', 'AND ? IS NOT NULL')
    # Hak baca juga mengikat fingerprint grant; mutasi diperiksa dengan dua
    # snapshot yang sama-sama sah sebagai histori, satu sudah usang.
    from test_assistant_narrow_http import siapkan
    from dataclasses import replace
    import assistant_context
    import assistant_schema
    token, akun, target, chat, _, _ = siapkan(server)
    with server.buka() as kon:
        konteks = assistant_context.ambil(kon, target.jenis_resource, target.resource_id, pemilik='guru')
    with assistant_schema.buka() as kon:
        with pytest.raises(AssertionError):
            assert assistant_view.chat_terbaru_sah(kon, akun, replace(konteks, versi='baru'), pemilik='guru') is None


def test_mutasi_endpoint_konfirmasi_retired_terdeteksi(server, monkeypatch):
    pasang(monkeypatch, assistant_inline_http, 'tangani_inline_post',
        'if aksi in ("konfirmasi-memori", "ubah-memori"):', 'if False:')
    monkeypatch.setattr(assistant_http, 'tangani_inline_post', assistant_inline_http.tangani_inline_post)
    with pytest.raises(AssertionError):
        cek_draft(server)
