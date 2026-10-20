"""Kompatibilitas source/probe soal, tanpa Docker lokal atau data keluarga."""
from pathlib import Path
import os
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / "scripts"))
import release_question_pair as pair


def _jalankan(tmp_path, sumber, injeksi=""):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(AKAR / "mesin"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    # Simulasi default B/C pada satu checkout; probe image sendiri TIDAK
    # menginjeksi default dan wajib membaca default dari masing-masing image.
    versi = 1 if sumber == pair.SUMBER_BACA else 2
    injeksi = f"import number_theory_versions as v\nv.VERSI_TEORI_BILANGAN_BAWAAN={versi}\n" + injeksi
    return subprocess.run([sys.executable, "-B", "-"],
        input=injeksi + sumber.replace("/data/", str(tmp_path) + "/"),
        env=env, capture_output=True, text=True, timeout=30)


def test_soal_cbc_source(tmp_path):
    for sumber, marker in ((pair.SUMBER_TULIS, "OSN_QUESTION_WRITER_OK"),
                           (pair.SUMBER_BACA, "OSN_QUESTION_RECOVERY_OK"),
                           (pair.SUMBER_KEMBALI, "OSN_QUESTION_RETURN_OK")):
        hasil = _jalankan(tmp_path, sumber)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


@pytest.mark.parametrize("rusak", ("id", "cetak", "konteks"))
def test_mutation_reader_soal(tmp_path, rusak):
    tulis = _jalankan(tmp_path, pair.SUMBER_TULIS)
    assert tulis.returncode == 0, tulis.stderr
    if rusak == "id":
        injeksi = "from templates import REGISTRI\nREGISTRI.pop('banyak_prima')\n"
        pesan = "reader_tidak_mengenal_jenis"
    elif rusak == "konteks":
        injeksi = "import context_store\ncontext_store._id_konteks=lambda *a: None\n"
        pesan = "konteks butir tidak cocok sumber"
    else:
        injeksi = '''import teacher_print_pages,inspect,textwrap
sumber=textwrap.dedent(inspect.getsource(teacher_print_pages.halaman_lembar))
lama="        if untuk_guru:\\n            hasil = replace("
assert sumber.count(lama)==1
exec('from __future__ import annotations\\n'+sumber.replace(lama,"        if False:\\n            hasil = replace("),teacher_print_pages.__dict__)
'''
        pesan = "cetak_bank_berubah"
    hasil = _jalankan(tmp_path, pair.SUMBER_BACA, injeksi)
    assert hasil.returncode == 1 and pesan in hasil.stderr
    pulih = _jalankan(tmp_path, pair.SUMBER_BACA)
    assert pulih.returncode == 0, pulih.stderr


@pytest.mark.parametrize("nilai", ("", "0", "3", "dua"))
def test_writer_teori_bilangan_invalid_gagal(nilai, monkeypatch):
    from number_theory_versions import versi_writer
    monkeypatch.setenv("OSN_TEORI_BILANGAN_VERSI", nilai)
    with pytest.raises(ValueError):
        versi_writer()


@pytest.mark.parametrize("versi,jumlah", (("1", 3), ("2", 7)))
def test_writer_proses_baru_mengikuti_versi_tanpa_menghapus_reader(versi, jumlah):
    skrip = '''import topics
from generator import buat_lembar
from templates import REGISTRI
paket=topics.ambil('teori-bilangan')
assert len(set(paket.komposisi['P4']))==7
assert len(set(paket.komposisi_untuk('P4')))==JUMLAH
from question_context import konteks_warisan
from mastery_catalog import katalog_target
assert konteks_warisan('banyak_prima','P4').id=='warisan-v1:banyak_prima:P4'
assert any('banyak_prima' in t.pola for t in katalog_target('P4'))
for gab in (topics.ambil('campuran'),topics.gabungan(('teori-bilangan','statistika'))):
    ada='banyak_prima' in gab.komposisi_untuk('P4')
    assert ada==(JUMLAH==7)
assert len({s.template_id for s in buat_lembar(42,level='P4',topik='teori-bilangan').soal})==JUMLAH
assert REGISTRI['banyak_prima'](a=10,b=20).kunci=='4'
print('writer_reader_ok')
'''.replace('JUMLAH', str(jumlah))
    hasil = subprocess.run([sys.executable, '-B', '-'], input=skrip,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(AKAR / "mesin"),
             "PYTHONDONTWRITEBYTECODE": "1", "OSN_TEORI_BILANGAN_VERSI": versi},
        capture_output=True, text=True, timeout=15)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout.strip() == 'writer_reader_ok'


def test_writer_lama_tidak_membatasi_reader(monkeypatch):
    from number_theory_versions import pilih_komposisi, LAMA
    from templates import REGISTRI
    monkeypatch.setenv("OSN_TEORI_BILANGAN_VERSI", "1")
    assert pilih_komposisi({"P4": ("banyak_prima",)})["P4"] == LAMA["P4"]
    assert REGISTRI["banyak_prima"](a=10, b=20).kunci == "4"
    monkeypatch.setenv("OSN_TEORI_BILANGAN_VERSI", "2")
    assert pilih_komposisi({"P4": ("banyak_prima",)}) is None
