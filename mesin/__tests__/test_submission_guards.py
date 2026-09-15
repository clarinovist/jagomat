"""Palang pengiriman/refleksi: timer, kapabilitas, payload dan versi."""
import concurrent.futures
import re

import pytest

import database
import share_links
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        s.siswa = database.tambah_siswa(kon, 'feby', pemilik='guru')
        s.sesi = database.buat_sesi(kon, s.siswa, 7, jumlah_soal=2)
        s.sid = database.isi_sesi(kon, s.sesi)[0]['sesi_soal_id']
    yield s
    s.berhenti()


def kirim(s, data, jalur=None):
    return s.minta(jalur or f'/murid/kerjakan/{s.sesi}', data=data,
                   auth=None if jalur else ('feby', SANDI_MURID))


@pytest.mark.parametrize('mode,auto,mulai,langsung', [
    ('drill', 1, "datetime('now','+7 hours','-20 minutes')", True),
    ('drill', 0, "datetime('now','+7 hours','-20 minutes')", False),
    ('drill', 1, "datetime('now','+7 hours')", False),
    ('diagnostik', 1, "datetime('now','+7 hours','-20 minutes')", False),
])
def test_timer_hanya_bypass_jika_konfigurasi_dan_waktu_server_sah(server, mode, auto, mulai, langsung):
    s = server
    with s.buka() as kon:
        kon.execute(f"UPDATE sesi SET mode=?,timer_mode='sesi',timer_auto=?,durasi_menit=10,mulai={mulai} WHERE id=?", (mode, auto, s.sesi))
    status, _, _ = kirim(s, {'aksi':'selesai', 'flow_kosong':'1', 'revisi_pekerjaan':'0'})
    assert status == 200
    with s.buka() as kon:
        assert bool(kon.execute('SELECT selesai FROM sesi').fetchone()[0]) == langsung
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_sesi').fetchone()[0] == int(langsung)


def test_alasan_dan_payload_asing_tidak_mengubah_data(server):
    s = server
    with s.buka() as kon:
        asing = database.tambah_siswa(kon, 'Peserta Asing', pemilik='guru2')
        sesi = database.buat_sesi(kon, asing, 8, jumlah_soal=1)
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        awal = tuple(kon.iterdump())
    for data in (
        {'aksi':'kirim_latihan', f'alasan_kosong_{sid}':'maksud_soal'},
        {'aksi':'kirim_latihan', f'alasan_kosong_{s.sid}':'K'},
        {'aksi':'kirim_latihan', f'jwb_{s.sid}':'123'},
        {'aksi':'selesai', f'jwb_{sid}':'123'},
        [('aksi','selesai'), ('aksi','kirim_latihan')],
    ):
        assert kirim(s, data)[0] == 400
        with s.buka() as kon:
            assert tuple(kon.iterdump()) == awal
    hasil = [kirim(s, {'aksi':'kirim_latihan'}, jalur=f'/murid/kerjakan/{n}') for n in (sesi,999999)]
    # jalur parameter di helper tidak memasang auth; keduanya sama-sama ditolak login.
    assert hasil[0][0] == hasil[1][0] == 401
    hasil = [s.minta(f'/murid/kerjakan/{n}', auth=('feby', SANDI_MURID), data={'aksi':'kirim_latihan'}) for n in (sesi,999999)]
    assert hasil[0][0] == hasil[1][0] == 404 and hasil[0][1] == hasil[1][1]


def test_tautan_dicabut_setelah_refleksi_tidak_bisa_finalisasi(server):
    s = server
    with s.buka() as kon:
        token = share_links.buat(kon, s.sesi)
    status, _, _ = kirim(s, {'aksi':'selesai', 'flow_kosong':'1'}, f'/mulai/{token}')
    assert status == 200
    with s.buka() as kon:
        share_links.cabut(kon, s.sesi)
    assert kirim(s, {'aksi':'kirim_latihan'}, f'/mulai/{token}')[0] == 404
    with s.buka() as kon:
        assert kon.execute('SELECT selesai FROM sesi').fetchone()[0] is None


def test_foto_tidak_memalsukan_jawaban_dan_tidak_memanggil_ai(server, monkeypatch):
    import attachments
    s = server
    def dilarang(*args, **kwargs):
        pytest.fail('Pengiriman tidak boleh memanggil ekstraksi AI')
    monkeypatch.setattr(attachments, 'baca_ulang', dilarang)
    with s.buka() as kon:
        lid = database.simpan_lampiran(kon, s.sesi, 'sintetis.jpg')
    status, html, _ = kirim(s, {'aksi':'selesai','flow_kosong':'1'})
    assert status == 200 and 'jawaban mungkin ada di foto' in html
    assert kirim(s, {'aksi':'kirim_latihan'})[0] == 200
    with s.buka() as kon:
        assert kon.execute('SELECT lampiran_json FROM pengiriman_sesi').fetchone()[0] == f'[{lid}]'
        assert all(b[0] == '' for b in kon.execute('SELECT jawaban FROM pengiriman_butir'))


@pytest.mark.parametrize('alasan', ['', 'maksud_soal', 'langkah_awal', 'belum_sempat', 'belum_bisa_menjelaskan'])
def test_semua_alasan_tetap_terpisah_dan_tidak_jadi_diagnosis(server, alasan):
    s=server
    assert kirim(s,{'aksi':'selesai','flow_kosong':'1'})[0]==200
    assert kirim(s,{'aksi':'kirim_latihan',f'alasan_kosong_{s.sid}':alasan})[0]==200
    with s.buka() as kon:
        b=kon.execute('SELECT jawaban,cara,alasan FROM pengiriman_butir WHERE sesi_soal_id=?',(s.sid,)).fetchone()
        assert tuple(b)==('','',alasan)
        assert kon.execute('SELECT count(*) FROM diagnosis').fetchone()[0]==0


def test_semua_jawaban_terisi_flow_baru_langsung_finalisasi(server):
    s=server
    with s.buka() as kon:
        data={f'jwb_{b["sesi_soal_id"]}': b['kunci'] for b in database.isi_sesi(kon,s.sesi)}
    data.update({'aksi':'selesai','flow_kosong':'1','revisi_pekerjaan':'0'})
    status,html,_=kirim(s,data)
    assert status==200 and 'Latihan belum dikirim' not in html
    with s.buka() as kon:
        assert kon.execute('SELECT selesai FROM sesi').fetchone()[0]
        assert kon.execute('SELECT count(*) FROM pengiriman_butir').fetchone()[0]==2


def test_halaman_refleksi_akun_memakai_header_privat(server):
    status,_,h=kirim(server,{'aksi':'selesai','flow_kosong':'1'})
    assert status==200
    assert h['Cache-Control']=='no-store' and h['Referrer-Policy']=='no-referrer'
    assert h['X-Robots-Tag']=='noindex, nofollow'
    assert "form-action 'self'" in h['Content-Security-Policy']
    assert "default-src 'none'" in h['Content-Security-Policy']


def test_double_submit_akun_hanya_satu_arsip(server):
    s = server
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        hasil = list(pool.map(lambda _: kirim(s, {'aksi':'kirim_latihan'})[0], (1,2)))
    assert sorted(hasil) == [200,409]
    with s.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_sesi').fetchone()[0] == 1
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_butir').fetchone()[0] == 2
