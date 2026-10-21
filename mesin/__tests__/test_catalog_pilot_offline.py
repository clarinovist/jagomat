"""Pilot A/B/C: draf terikat hash, solver terpisah, tanpa serving/DB."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

AKAR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(AKAR/'scripts'))
import catalog_pilot as p


@pytest.fixture(scope='module')
def paket(tmp_path_factory):
    folder=tmp_path_factory.mktemp('pilot-offline')/'hasil'
    with pytest.MonkeyPatch.context() as patch:
        for k,v in {'OSN_PENILAIAN_REVISI':'0','OSN_KATALOG_VERSI':'2'}.items():patch.setenv(k,v)
        hasil=p.ekspor(folder)
    return folder,hasil


def test_lima_konsep_90_draft_tanpa_klaim_review(paket):
    path,r=paket
    assert r['pair_AC_identik']
    for arm in ('A','B','C'):
        s=r['lengan'][arm]
        assert s['kandidat']==s['lolos_gate_mesin']==30
        assert s['terbit']==s['review_manusia']==0
        assert s['menit_review'] is None
    assert r['lengan']['B']['item_bermalrule']==0
    assert r['lengan']['B']['pg_tersedia']==0
    semua=json.loads((path/'semua-kandidat.json').read_text())
    assert len(semua)==90 and len({i['id'] for i in semua})==90
    for item in semua:
        assert not p.gate(item)
        pub=item['payload']['publik']
        assert set(pub)=={'konsep','level','fakta','teks'}
        assert not {'kunci','malrule','pembahasan'}&set(pub)
    review=json.loads((path/'review-buta.json').read_text())
    assert all('lengan' not in i and 'id' not in i for i in review)


def test_replay_paket_tanpa_generator(paket,monkeypatch):
    import generator
    import templates
    def dilarang(*a,**k):pytest.fail('replay tidak boleh meregenerasi')
    monkeypatch.setattr(generator,'buat_soal',dilarang)
    monkeypatch.setattr(templates,'REGISTRI',{})
    for arm in ('B','C'):
        assert len(p.baca_paket(paket[0]/(arm+'-draft.json')))==30


@pytest.mark.parametrize('mutasi,alasan',(
    ('kunci','kunci'),('malrule','malrule_prosedur'),('bocor','payload_publik'),
    ('review','review_bukan_draft_terikat'),('domain','domain'),('hash','hash_konten'),
))
def test_mutation_gate_item_bukan_fixture_rusak(paket,mutasi,alasan):
    item=deepcopy(p.baca_paket(paket[0]/'A-draft.json')[0])
    if mutasi=='kunci':item['payload']['guru']['kunci']='999'
    elif mutasi=='malrule':item['payload']['guru']['malrule'][0]['jawaban']='999'
    elif mutasi=='bocor':item['payload']['publik']['kunci']='999'
    elif mutasi=='domain':item['payload']['publik']['fakta']['n1']=999
    elif mutasi=='review':item['review']['status']='disetujui'
    if mutasi not in ('hash','review'):
        item['content_sha256']=p.sidik(item['payload'])
        item['review']['content_sha256']=item['content_sha256']
    if mutasi=='hash':item['content_sha256']='0'*64
    assert alasan in p.gate(item)


def test_prosedur_konsep_lain_ditolak(paket):
    item=deepcopy(p.baca_paket(paket[0]/'A-draft.json')[0])
    f=item['payload']['publik']['fakta']
    from fractions import Fraction
    n=Fraction(f['n1'],f['d1'])*Fraction(f['n2'],f['d2'])
    item['payload']['guru']['malrule']=[{'id':'rev1.pecahan.lupa_balik','jawaban':str(n),'kode':'K','alasan':'lupa balik'}]
    item['content_sha256']=p.sidik(item['payload']);item['review']['content_sha256']=item['content_sha256']
    assert p.gate(item), 'ID prosedur cabang lain wajib ditolak'


@pytest.mark.parametrize('field,value',(('id',None),('source_sha',None),('revisi',True),('seed',-1)))
def test_envelope_invalid_ditolak(paket,field,value):
    item=deepcopy(p.baca_paket(paket[0]/'A-draft.json')[0]);item[field]=value
    assert p.gate(item)


def test_duplikat_id_paket_ditolak(paket,tmp_path):
    item=p.baca_paket(paket[0]/'B-draft.json')[0]
    items=[item,item];file=tmp_path/'dup.json'
    source=json.loads((paket[0]/'B-draft.json').read_text())['source_manifest']
    file.write_text(json.dumps({'versi':1,'items':items,'hash':p.sidik(items),'source_manifest':source}))
    with pytest.raises(ValueError,match='identitas'):p.baca_paket(file)


@pytest.mark.parametrize('field',('pembahasan','alasan'))
def test_teks_invalid_menjadi_reject_bukan_exception(paket,field):
    item=deepcopy(p.baca_paket(paket[0]/'A-draft.json')[0])
    if field=='pembahasan':item['payload']['guru']['pembahasan']=None
    else:item['payload']['guru']['malrule'][0]['alasan']=None
    item['content_sha256']=p.sidik(item['payload']);item['review']['content_sha256']=item['content_sha256']
    assert p.gate(item)


def test_ekspor_mencatat_reject_dan_tetap_menghasilkan_laporan(tmp_path,monkeypatch):
    authored=deepcopy(p.ITEM)
    tid=p.KONSEP[0]
    authored[tid]=(tuple((*authored[tid][0][:3],None)),*authored[tid][1:])
    monkeypatch.setattr(p,'ITEM',authored)
    folder=tmp_path/'reject'
    import os
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','0')
    hasil=p.ekspor(folder)
    assert os.environ['OSN_PENILAIAN_REVISI']=='0'
    assert hasil['lengan']['B']['kandidat']==30
    assert hasil['lengan']['B']['gagal_gate']==1
    assert hasil['lengan']['B']['lolos_gate_mesin']==29
    assert (folder/'hasil.json').is_file()
    assert 'Ditolak gate mesin' in (folder/'review.html').read_text()


def test_paket_hash_dan_item_tampered_ditolak(paket,tmp_path):
    data=json.loads((paket[0]/'B-draft.json').read_text())
    data['items'][0]['payload']['guru']['kunci']='123'
    file=tmp_path/'rusak.json';file.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='tidak utuh'):p.baca_paket(file)
    data['hash']=p.sidik(data['items']);file.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='gagal gate'):p.baca_paket(file)
