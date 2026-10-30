"""Draf bantuan tetap lokal dan tidak kehilangan pilihan materi dasar."""
import pytest
import assistant_inline
import assistant_inline_http
from test_assistant_inline_http import server, _origin
from test_assistant_runtime import _token_guru


def data_draf():
    return {'inline_form': 'manual', 'topik': 'bilangan-dasar', 'jumlah_soal': '15',
            'mode': 'diagnostik', 'hadir_timer_mode': '1', 'durasi_menit': '47',
            'timer_auto': '0', 'variasi_dasar': 'P1'}


def test_draf_baru_terpisah_dari_muatan_pendamping(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    data = {k: [v] for k, v in data_draf().items()}
    data['aksi'] = ['buka']
    target = assistant_inline.tujuan_anak(7, 'latihan')
    muatan, draf, gabungan, remedial = assistant_inline_http._pisahkan_draf_inline(data, target)
    assert muatan == {'aksi': ['buka']}
    assert draf.variasi_dasar == 'P1'
    assert gabungan is remedial is None


@pytest.mark.parametrize('nilai', [['P3'], ['P1', 'P2']])
def test_draf_variasi_tidak_sah_ditolak(nilai):
    data = {k: [v] for k, v in data_draf().items() if k != 'inline_form'}
    data['variasi_dasar'] = nilai
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_latihan(data, ['bilangan-dasar'])


def test_draf_p1_native_buka_tutup_tanpa_provider_atau_sesi(server, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    token = _token_guru(server)
    anak = server.ids_inline[0]
    data = dict(data_draf(), inline_host='anak', inline_host_id=str(anak), inline_posisi='latihan')
    with server.buka() as kon:
        awal = tuple(kon.iterdump())
    for aksi in ('buka', 'tutup'):
        kode, isi, _ = server.minta('/pendamping/inline/' + aksi, cookie=token,
                                   data=data, headers=_origin(server))
        assert kode == 200
        assert 'name="variasi_dasar" value="P1" checked' in isi
        assert 'value="bilangan-dasar" selected' in isi
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == awal
    assert server.provider.panggilan == []
