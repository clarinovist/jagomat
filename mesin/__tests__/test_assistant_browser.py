"""Kontrak progressive enhancement chat; seluruh state/provider sintetis."""

import base64
import hashlib
import re
import json
import shutil
import subprocess

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


@pytest.mark.parametrize('jenis', ['anak', 'sesi'])
def test_host_awal_memuat_skrip_dan_header_privat(server, jenis):
    token = _token_guru(server)
    identitas = server.ids_inline[0 if jenis == 'anak' else 1]
    kode, isi, header = server.minta(f'/{jenis}/{identitas}', cookie=token)
    assert kode == 200
    assert 'class="pendamping-pemicu"' in isi
    assert '<script>' + assistant_browser.SKRIP_CHAT + '</script>' in isi
    assert "'sha256-%s'" % assistant_browser.HASH_CSP in header['Content-Security-Policy']
    if jenis == 'anak':
        assert '<script>' + assistant_browser.SKRIP_PILIHAN_ISI + '</script>' in isi
        assert "'sha256-%s'" % assistant_browser.HASH_PILIHAN_ISI in header['Content-Security-Policy']
    else:
        assert assistant_browser.SKRIP_PILIHAN_ISI not in isi
    assert header['Cache-Control'] == 'no-store'
    assert header['Referrer-Policy'] == 'no-referrer'
    assert header['X-Frame-Options'] == 'DENY'
    assert header['X-Robots-Tag'] == 'noindex, nofollow'
    assert 'fonts.googleapis.com' not in isi
    assert 'onsubmit=' not in isi
    assert server.provider.panggilan == []


def test_izin_skrip_hanya_hash_persis_pada_chat():
    biasa = b'<body><p>Tanpa chat</p></body>'
    assert assistant_browser.lengkapi_respons(biasa) == (biasa, "")
    latihan, izin_latihan = assistant_browser.lengkapi_respons(
        b'<body><select data-pilihan-isi-otomatis><option>Topik</option></select></body>'
    )
    skrip_latihan = re.search(rb'<script>(.*?)</script>', latihan, re.S).group(1)
    digest_latihan = base64.b64encode(hashlib.sha256(skrip_latihan).digest()).decode()
    assert izin_latihan == f"script-src 'sha256-{digest_latihan}'; "
    assert b"requestSubmit" in skrip_latihan and b"fetch(" not in skrip_latihan
    isi, izin = assistant_browser.lengkapi_respons(b'<body><aside data-pendamping-chat="chat_sintetis"></aside></body>')
    skrip = re.search(rb'<script>(.*?)</script>', isi, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(skrip).digest()).decode()
    assert izin == f"script-src 'sha256-{digest}'; connect-src 'self'; "
    assert "unsafe-inline" not in izin and "script-src 'self'" not in izin
    gabungan, izin_gabungan = assistant_browser.lengkapi_respons(
        b'<body><aside data-pendamping-chat="chat_sintetis"></aside>'
        b'<select data-pilihan-isi-otomatis></select></body>'
    )
    assert gabungan.count(b'<script>') == 2
    assert "sha256-" + assistant_browser.HASH_CSP in izin_gabungan
    assert "sha256-" + assistant_browser.HASH_PILIHAN_ISI in izin_gabungan
    assert "connect-src 'self'" in izin_gabungan


@pytest.mark.parametrize("soal", [False, True])
def test_chat_native_dan_fetch_memakai_guard_dan_request_yang_sama(server, soal):
    token, data, isi, header = mulai(server, soal=soal)
    assert isi.count('<script>') == 1
    assert f'data-pendamping-chat="{data["chat"]}"' in isi
    assert "'sha256-%s'" % assistant_browser.HASH_CSP in header['Content-Security-Policy']
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


def test_fragmen_buka_asing_dan_hilang_sama_404_tanpa_provider(server):
    token = _token_guru(server)
    _anak, _sesi, asing, _sesi_asing = server.ids_inline
    header = {**_origin(server), "X-Pendamping-Panel": "fragment"}
    hasil = []
    for identitas in (asing, 999999):
        hasil.append(server.minta(
            "/pendamping/inline/buka", cookie=token,
            data={"inline_host": "anak", "inline_host_id": str(identitas), "inline_posisi": "rencana"},
            headers=header,
        ))
    assert hasil[0][0] == hasil[1][0] == 404
    assert hasil[0][1] == hasil[1][1]
    assert "pendamping-panel-kanan" not in hasil[0][1]
    assert server.provider.panggilan == []


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
    assert f'data-pendamping-request="{data["request_id"]}"' in isi
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


def test_halaman_murid_tidak_memperoleh_enhancement_panel(server):
    import auth
    import sessions
    akun = auth.cari_akun('feby')
    token = sessions.buat('feby', 'murid', id_akun=akun['id_akun'], revisi_auth=akun['revisi_auth'])
    kode, isi, _ = server.minta('/murid/', cookie=token)
    assert kode == 200
    assert not assistant_browser.memiliki_panel(isi.encode())
    assert assistant_browser.SKRIP_CHAT not in isi
    assert 'data-pendamping-host=' not in isi
    assert 'class="pendamping-pemicu"' not in isi


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


def _jalankan_js(skenario):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node tidak tersedia; regression JS harus dijalankan lewat browser sebelum rilis.')
    skrip = assistant_browser.SKRIP_CHAT.rsplit('})();', 1)[0] + (
        'globalThis.uji = {cocokPanel, payload, jalurSah, lengkapiFallback, '
        'pembuka: function(form) { pembuka={form:form,bungkus:{dataset:{}}}; }};})();'
    )
    awal = '''const vm = require('node:vm'); const assert = require('node:assert/strict');
const SubmitEvent = function () {}; SubmitEvent.prototype.submitter = null;
const dunia = {window: {fetch(){}, FormData: function(){}, DOMParser: function(){},
 AbortController, URLSearchParams, SubmitEvent}, SubmitEvent, URLSearchParams,
 document: {addEventListener(){}, querySelector(){return null;}, createElement(){return {dataset:{}};}}, console};
vm.createContext(dunia);
'''
    hasil = subprocess.run([node, '-e', awal + 'vm.runInContext(' + json.dumps(skrip) +
                            ', dunia); const uji=dunia.uji;\n' + skenario],
                           capture_output=True, text=True, timeout=15)
    assert hasil.returncode == 0, hasil.stderr


def test_js_binding_host_resource_chat_request_melalui_guard_runtime():
    _jalankan_js('''
const harap = {host:'sesi', id:'42', posisi:'sesi', resource:'sesi', resourceId:'42', chat:''};
function panel(b) { return {classList:{contains:n=>n==='pendamping-panel-kanan'},
 dataset:{pendampingHost:b.host, pendampingHostId:b.id, pendampingPosisi:b.posisi,
 pendampingResource:b.resource, pendampingResourceId:b.resourceId, pendampingChat:b.chat || '',
 pendampingRequest:b.request}}; }
const kosong = new URLSearchParams();
assert.equal(uji.cocokPanel(harap,panel(harap),'buka',kosong),true);
for (const ubah of [{host:'anak'},{id:'99'},{resource:'soal'},{resourceId:'42:2'},{posisi:'soal'}]) {
 assert.equal(uji.cocokPanel(harap,panel({...harap,...ubah}),'buka',kosong),false,'respons asing ditolak');
}
const soal={...harap,posisi:'soal',resource:'soal',resourceId:'42:2'};
const pilih=new URLSearchParams({pilih_nomor:'2'});
assert.equal(uji.cocokPanel(harap,panel(soal),'pilih-sumber',pilih),true);
assert.equal(uji.cocokPanel(harap,panel({...soal,resourceId:'42:1'}),'pilih-sumber',pilih),false);
const chat={...soal,chat:'chat_'+ 'a'.repeat(32)}, lain='chat_'+ 'b'.repeat(32);
assert.equal(uji.cocokPanel(chat,panel({...chat,chat:lain}),'riwayat',new URLSearchParams({pilih_chat:lain})),true);
assert.equal(uji.cocokPanel(chat,panel({...chat,chat:lain,resourceId:'42:1'}),'riwayat',new URLSearchParams({pilih_chat:lain})),false);
for (const aksi of ['pesan','status']) {
 const data=new URLSearchParams({request_id:'req_sintetis'});
 assert.equal(uji.cocokPanel(chat,panel({...chat,request:'req_sintetis'}),aksi,data),true);
 assert.equal(uji.cocokPanel(chat,panel({...chat,chat:lain,request:'req_sintetis'}),aksi,data),false);
 assert.equal(uji.cocokPanel(chat,panel({...chat,request:'req_lain'}),aksi,data),false);
}
''')


def test_js_payload_hanya_wrapper_atau_panel_tidak_draf_pekerjaan():
    _jalankan_js('''
const form={};
const input=(name,value,type='hidden',checked=true)=>({form,name,value,type,checked,disabled:false});
const field=[input('inline_host','anak'),input('inline_host_id','7'),input('inline_posisi','latihan'),
 input('inline_form','manual'),input('durasi_menit','49'),input('jwb_11','DRAF-RAHASIA'),
 input('pesan','Pertanyaan sintetis','textarea'),input('chat','chat_sintetis'),input('request_id','req_sintetis')];
const dataset={pendampingHost:'anak',pendampingHostId:'7',pendampingPosisi:'latihan',pendampingResource:'anak',pendampingResourceId:'7'};
const batas={dataset,querySelectorAll:()=>field};
const tombol={name:'',value:''};
assert.equal(uji.payload(form,tombol,batas,'buka').toString(),'inline_host=anak&inline_host_id=7&inline_posisi=latihan');
const kirim=uji.payload(form,tombol,batas,'pesan');
assert.equal(kirim.has('jwb_11'),false,'draf pekerjaan tidak dikirim');
assert.equal(kirim.has('inline_form'),false);
assert.equal(kirim.get('pesan'),'Pertanyaan sintetis');
const mulai={dataset,querySelectorAll:()=>[input('mode_chat','tanpa_memori','select'),input('setuju_konteks','1','checkbox',true)]};
const dataMulai=uji.payload(form,tombol,mulai,'mulai');
assert.deepEqual(dataMulai.getAll('mode_chat'),['tanpa_memori']);
assert.equal(dataMulai.get('setuju_konteks'),'1');
assert.equal(uji.payload(form,{name:'pilih_chat',value:'chat_lain'},batas,'riwayat').get('pilih_chat'),'chat_lain');
const cek={dataset,querySelectorAll:()=>[input('setuju','1','checkbox',false)]};
assert.equal(uji.payload(form,tombol,cek,'persetujuan').has('setuju'),false);
''')


def test_js_fallback_native_membawa_draf_hanya_ke_form_panel():
    _jalankan_js('''
const elements=[{name:'inline_form',value:'remedial'},{name:'jumlah_soal',value:'20'},
 {name:'versi_pilihan_isi',value:'1'},{name:'topik_dibandingkan',value:'pola-bilangan'},
 {name:'template_id',value:'pola_a',type:'checkbox',checked:false},
 {name:'jwb_11',value:'DRAF SINTETIS'},{name:'asing',value:'JANGAN SALIN'}];
uji.pembuka({elements});
const tambahan=[];
const form={querySelectorAll:()=>[],appendChild:e=>tambahan.push(e)};
uji.lengkapiFallback(form);
assert.equal(tambahan.map(e=>e.name).join(','),'inline_form,jumlah_soal,versi_pilihan_isi,topik_dibandingkan,jwb_11');
assert.equal(tambahan[4].value,'DRAF SINTETIS');
assert.equal(elements.length,7,'form pekerjaan tidak diubah');
''')


def test_js_allowlist_exact_same_origin_semua_aksi():
    _jalankan_js('''
for (const aksi of ['buka','persetujuan','mulai','pilih-sumber','riwayat','pesan','status']) {
 assert.equal(uji.jalurSah('/pendamping/inline/'+aksi),aksi);
 for (const url of ['https://asing.test/pendamping/inline/'+aksi,
  '//asing.test/pendamping/inline/'+aksi,'/asing/pendamping/inline/'+aksi,
  '/pendamping/inline/'+aksi+'?x=1','/pendamping/inline/'+aksi+'#x']) {
   assert.equal(uji.jalurSah(url),'');
 }
}
assert.equal(uji.jalurSah('/pendamping/inline/buka/sesi/42/sesi'),'buka');
assert.equal(uji.jalurSah('/pendamping/inline/buka/sesi/42/soal/1'),'buka');
for (const url of ['/sesi-baru/1','/pendamping/inline/konfirmasi-usulan','/pendamping/inline/buka/sesi/01/sesi'])
 assert.equal(uji.jalurSah(url),'');
''')


def test_js_pilihan_isi_hanya_mengirim_form_native_dan_menyisakan_fallback():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node tidak tersedia; regression JS harus dijalankan lewat browser sebelum rilis.')
    skenario = '''const vm=require('node:vm');const assert=require('node:assert/strict');
let listener=null, dikirim=0;
const tombol={hidden:false};
const form={requestSubmit(t){assert.equal(t,tombol);dikirim++;}};
const select={form,addEventListener(n,f){assert.equal(n,'change');listener=f;}};
const document={querySelectorAll(q){return q==='[data-pilihan-isi-otomatis]'?[select]:[];}};
const dunia={document};vm.createContext(dunia);vm.runInContext(SKRIP,dunia);
assert.equal(tombol.hidden,false,'skrip tidak boleh menyembunyikan fallback tanpa target');
form.querySelector=q=>{assert.equal(q,'button[data-pilihan-isi-fallback]');return tombol;};
vm.runInContext(SKRIP,dunia);assert.equal(tombol.hidden,true);listener();assert.equal(dikirim,1);'''
    hasil = subprocess.run([node, '-e', 'const SKRIP=' + json.dumps(assistant_browser.SKRIP_PILIHAN_ISI) + ';' + skenario],
                           capture_output=True, text=True, timeout=15)
    assert hasil.returncode == 0, hasil.stderr
    for terlarang in ('fetch(', 'FormData', 'localStorage', 'sessionStorage', 'document.cookie', 'innerHTML', 'eval('):
        assert terlarang not in assistant_browser.SKRIP_PILIHAN_ISI


def test_skrip_tidak_memperluas_pengiriman_atau_penyimpanan_browser():
    skrip = assistant_browser.SKRIP_CHAT
    assert 'fetch(p.jalur' in skrip
    assert 'jalurSah(p.jalur) !== p.aksi' in skrip
    assert "redirect: 'error'" in skrip
    assert "credentials: 'same-origin', cache: 'no-store'" in skrip
    assert 'panel.replaceWith(baru)' in skrip
    assert 'document.body.replaceWith' not in skrip
    assert "var aksiPanel" in skrip
    assert "X-Pendamping-Panel" in skrip
    assert "batas.querySelectorAll('input, select, textarea')" in skrip
    assert 'new FormData(form)' not in skrip
    assert "localStorage" not in skrip and "sessionStorage" not in skrip
    assert 'b.chat !== chat' in skrip
    assert 'p.generasi === generasi' in skrip
    assert 'if (!pembuka) return;' in skrip
    for terlarang in ('localStorage', 'sessionStorage', 'document.cookie', 'sendBeacon', 'innerHTML', 'eval('):
        assert terlarang not in skrip
