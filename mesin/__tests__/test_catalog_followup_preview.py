"""Ekspor review draf menjaga lingkungan, identitas isi dan artefak sebelumnya."""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'catalog_followup_preview.py'


def test_preview_draf_tidak_mengesahkan_dan_tidak_menimpa(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('catalog_followup_preview', SCRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', 'rusak')
    monkeypatch.delenv('OSN_PENILAIAN_REVISI', raising=False)
    output = tmp_path / 'review'
    manifest = modul.ekspor(output)
    assert os.environ['OSN_KATALOG_LANJUTAN'] == 'rusak'
    assert 'OSN_PENILAIAN_REVISI' not in os.environ
    assert manifest['jumlah'] == 34
    assert manifest['reviewer'] is None and manifest['disahkan'] is False
    payload = (output / 'contoh.json').read_bytes()
    assert sha256(payload).hexdigest() == manifest['content_sha256']
    for row in json.loads(payload):
        assert 'revisi_penilaian' not in row['lama']['parameter']
        assert row['draf']['parameter']['revisi_penilaian'] == 2
        assert row['lama']['kunci'] == row['draf']['kunci']
    with pytest.raises(FileExistsError):
        modul.ekspor(output)
    assert (output / 'contoh.json').read_bytes() == payload
