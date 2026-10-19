"""Perilaku accordion dan lewati: tidak menilai, menulis, atau merusak isian."""
import json
import shutil
import subprocess

import pytest

from review_browser import SKRIP_TINJAUAN


def test_browser_menjaga_isian_dan_konfirmasi_lewati(tmp_path):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node tidak tersedia; pemeriksaan browser nyata tetap wajib.')
    skenario = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
let focused = null, accept = false, confirms = [], events = [], hashListener;
function element(extra={}) {
  return Object.assign({hidden:false, disabled:false, textContent:'', attrs:{}, handlers:{},
    addEventListener(k,f){this.handlers[k]=f;},
    setAttribute(k,v){this.attrs[k]=v;}, getAttribute(k){return this.attrs[k];},
    focus(){focused=this;}, contains(t){return t===this;}, dispatchEvent(e){events.push(e.type);}},extra);
}
const cards = [0,1,2].map((n)=>{
  const button=element(), body=element(), notes=element(), marker=element({hidden:true});
  const checkbox=element({checked:false, value:'1'}), skip=element({dataset:{konfirmasi:'Bukan bukti pemahaman.'},hidden:true});
  const native=element({querySelector:()=>checkbox}), status=element();
  const refs={'[data-buka-kartu]':button,'[data-isi-kartu]':body,
    '[data-catatan-tambahan]':notes,'[data-penanda-catatan]':marker,
    '[data-lewati-native]':native,'[data-lewati-tombol]':skip,'[data-status-lewati]':status};
  return {id:'tinjau-soal-'+(n+1),dataset:{prioritas:n===1?'2':'1'},
    querySelector:q=>refs[q], scrollIntoView(){}, refs, checkbox};
});
const form={querySelectorAll:()=>cards};
const context={document:{querySelectorAll:()=>[form],addEventListener(){}},
 location:{hash:''},history:{pushState(){}},Event:function(type){this.type=type;},
 window:{confirm(message){confirms.push(message);return accept;},addEventListener(k,f){hashListener=f;}}};
vm.runInNewContext(SOURCE, context);
assert.equal(cards.filter(c=>!c.refs['[data-isi-kartu]'].hidden).length,1);
assert.equal(cards[1].refs['[data-isi-kartu]'].hidden,false);
assert(cards.every(c=>!c.refs['[data-buka-kartu]'].disabled));
const a=cards[0], b=cards[1];
a.refs['[data-buka-kartu]'].handlers.click();
assert.equal(a.refs['[data-buka-kartu]'].getAttribute('aria-expanded'),'true');
assert.equal(b.refs['[data-isi-kartu]'].hidden,true);
a.refs['[data-catatan-tambahan]'].handlers.input();
assert.equal(a.refs['[data-penanda-catatan]'].hidden,false);
assert(a.refs['[data-penanda-catatan]'].textContent.includes('belum disimpan'));
a.refs['[data-lewati-tombol]'].handlers.click();
assert.equal(a.checkbox.checked,false);assert.equal(events.length,0);
accept=true;a.refs['[data-lewati-tombol]'].handlers.click();
assert.equal(a.checkbox.checked,true);assert.deepEqual(events,['change']);
assert.equal(confirms[0],'Bukan bukti pemahaman.');
assert(a.refs['[data-status-lewati]'].textContent.includes('belum disimpan'));
a.refs['[data-lewati-tombol]'].handlers.click();assert.equal(a.checkbox.checked,false);
context.location.hash='#tinjau-soal-3';hashListener();
assert.equal(cards[2].refs['[data-isi-kartu]'].hidden,false);
assert.equal(focused,cards[2].refs['[data-buka-kartu]']);
assert.equal(cards.filter(c=>!c.refs['[data-isi-kartu]'].hidden).length,1);
context.location.hash='#%invalid';hashListener();
assert.equal(cards[2].refs['[data-isi-kartu]'].hidden,false);
'''
    path = tmp_path / 'review.cjs'

    def jalankan(sumber):
        path.write_text('const SOURCE=' + json.dumps(sumber) + ';\n' + skenario)
        return subprocess.run([node, str(path)], capture_output=True, text=True, timeout=15)

    sehat = jalankan(SKRIP_TINJAUAN)
    assert sehat.returncode == 0, sehat.stderr
    # Hilangnya konfirmasi harus gagal pada checkbox/event, bukan setup/import.
    mutasi = SKRIP_TINJAUAN.replace('if (!window.confirm(pesan)) return;', '')
    assert mutasi != SKRIP_TINJAUAN
    merah = jalankan(mutasi)
    assert merah.returncode == 1 and 'AssertionError' in merah.stderr
    assert 'true !== false' in merah.stderr
