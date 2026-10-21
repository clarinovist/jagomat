"""Inventaris draf sintetis P3; validasi teknis bukan review matematika manusia."""
import teaching_playbook as pb
from generator import buat_soal
from learning_cycle import RencanaBelajar
from learning_sessions import _urutan_rencana
import topics


def test_lima_belas_pola_disetujui_semuanya_draf(monkeypatch):
    # Draf ditujukan writer katalog2. Recovery katalog1 tidak dipaksa menerima ID baru.
    monkeypatch.setenv('OSN_KATALOG_VERSI', '2')
    # Parser strict yang sama: envelope versi salah/kunci ganda -> kosong -> test merah.
    entri = pb._baca()
    disetujui = set(_urutan_rencana(RencanaBelajar('pemetaan', ''), (), 'P3'))
    assert len(entri) == 15
    assert {e['template_id'] for e in entri} == disetujui
    for e in entri:
        assert e['profil'] == 'P3' and e['status'] == 'draf'
        assert all(e[k] is None for k in ('reviewer', 'tanggal_review', 'versi_review', 'sha256_review'))
        assert 'belum direview manusia' in e['batas']
        assert pb.validasi_entri(e) == (), e['template_id']
        fokus = (e['template_id'], e['kode_intervensi'], e['malrule_id'])
        isi = pb.render(fokus, 'P3', peran='guru')
        assert 'data-playbook-draf' in isi
        assert 'DRAF — belum direview manusia; jangan dianggap panduan ajar final' in isi
        assert 'Ulasan:' not in isi
        pasangan = set()
        for seed in range(25):
            soal = buat_soal(e['template_id'], seed, 'P3', topics.pemilik_template(e['template_id']))
            pasangan.update((m.id, m.kode) for m in soal.malrule)
        assert (e['malrule_id'], e['kode_intervensi']) in pasangan
