"""Bandingkan nama, metode, endpoint dan validasi form dengan baseline sebelum redesain."""
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_admin_http_c import server, _login, _minta, SANDI_ADMIN


class KontrakForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self._forms = []
        self._luar = []
        self.kini = None

    @property
    def forms(self):
        """Kontrol di luar <form> yang memakai atribut ``form`` ikut form target."""
        hasil = []
        for form_id, form in self._forms:
            fields = form['fields'] + [row for target, row in self._luar if form_id and target == form_id]
            fields.sort(key=lambda x: x['name'])
            hasil.append(dict(form, fields=fields))
        return hasil

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            assert self.kini is None, 'form bersarang'
            self._id = a.get('id')
            self.kini = {'action': a.get('action'), 'method': a.get('method', 'get'), 'fields': []}
        elif tag in ('input', 'select', 'textarea', 'button') and a.get('name') and (self.kini is not None or a.get('form')):
            tipe = a.get('type', 'text' if tag == 'input' else 'select-one' if tag == 'select' else 'textarea' if tag == 'textarea' else 'submit')
            row = dict(name=a['name'], type=tipe, required='required' in a, disabled='disabled' in a)
            if tag == 'input':
                row.update({k:a.get(k,'') for k in ('min','max','step')})
            if a.get('form') and self.kini is None:
                self._luar.append((a['form'], row))
            else:
                self.kini['fields'].append(row)

    def handle_endtag(self, tag):
        if tag == 'form':
            assert self.kini is not None
            self._forms.append((self._id, self.kini))
            self.kini = None


def _kanonis(forms):
    return sorted((json.dumps(f,sort_keys=True) for f in forms))


@pytest.mark.parametrize('nama', ['ringkasan','keluarga','siswa','pendaftaran','langganan','kpi','operasional','ai','riwayat','riset','perhatian'])
def test_kontrak_form_http_sama_dengan_sebelum_redesain(server, nama):
    baseline = json.loads(Path(__file__).with_name('admin_form_contract.json').read_text())
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    jalur = '/admin/'+nama if nama in ('ai','riset') else '/admin?section='+nama
    code, body, _ = _minta(server, jalur, cookie=token)
    assert code == 200
    parser = KontrakForm(); parser.feed(body)
    assert parser.kini is None
    # Pemilih tema adalah kontrak baru yang sengaja dibagikan seluruh shell admin;
    # baseline ini tetap menjaga form domain lama tidak berubah.
    form_tema = [form for form in parser.forms if form['action'] == '/admin/tema']
    assert len(form_tema) == 1
    assert {field['name'] for field in form_tema[0]['fields']} == {'tema', 'token_tema'}
    form_domain = [form for form in parser.forms if form['action'] != '/admin/tema']
    assert _kanonis(form_domain) == _kanonis(baseline[nama])
