"""Guard browser latihan dieksekusi, bukan hanya dicari sebagai teks."""
import json
import shutil
import subprocess

import pytest
import practice_browser


def test_mode_dan_minimal_dua_topik_melalui_event_browser(tmp_path):
    node=shutil.which('node')
    if not node:
        pytest.skip('Node tidak tersedia; gate browser wajib sebelum rilis.')
    skenario = r'''
const vm=require('node:vm');
const assert=require('node:assert/strict');
let n=0;
const panels=['manual','gabungan','remedial'].map(mode=>({
 dataset:{modeLatihan:mode,url:'/sesi-'+mode+'/1',formId:'form-'+mode},
 disabled:mode!=='manual',hidden:mode!=='manual',querySelectorAll:()=>Array(n).fill({})
}));
const button={disabled:false}, identity={value:'manual'};
const form={id:'form-manual',action:'/sesi-manual/1',
 querySelector:q=>q==='[data-buat-latihan]'?button:q==='input[name="inline_form"]'?identity:
  q.includes(':not(')?panels.find(p=>!p.disabled):panels.find(p=>q.includes('"'+p.dataset.modeLatihan+'"')),
 querySelectorAll:()=>panels,addEventListener(){}};
const radios=panels.map(p=>({value:p.dataset.modeLatihan,checked:false,addEventListener(name,fn){this.change=fn;}}));
const external={form:'form-manual',getAttribute(){return this.form;},setAttribute(k,v){this.form=v;}};
const document={querySelector:()=>form,querySelectorAll:q=>q==='[form]'?[external]:radios};
vm.runInNewContext(SOURCE,{document});
assert.equal(button.disabled,false);
function choose(index,count){n=count;radios[index].checked=true;radios[index].change();}
choose(1,0);assert.equal(button.disabled,true);
choose(1,1);assert.equal(button.disabled,true);
choose(1,2);assert.equal(button.disabled,false);
assert.equal(form.action,'/sesi-gabungan/1');assert.equal(identity.value,'gabungan');
assert.equal(external.form,'form-gabungan');
assert.equal(panels[0].disabled,true);assert.equal(panels[1].hidden,false);
choose(2,0);assert.equal(button.disabled,true);
choose(2,4);assert.equal(button.disabled,true);
choose(2,3);assert.equal(button.disabled,false);
'''
    path=tmp_path/'test.cjs'
    def jalankan(source):
        path.write_text('const SOURCE='+json.dumps(source)+';\n'+skenario)
        return subprocess.run([node,str(path)],capture_output=True,text=True,timeout=15)
    sehat=jalankan(practice_browser.SKRIP_LATIHAN)
    assert sehat.returncode==0,sehat.stderr
    rusak=jalankan(practice_browser.SKRIP_LATIHAN.replace('jumlah < 2','jumlah < 1'))
    assert rusak.returncode==1 and 'AssertionError' in rusak.stderr
    assert 'false !== true' in rusak.stderr
