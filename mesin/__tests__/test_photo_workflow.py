"""Foto opsional, lipatan native, dan CTA guru memakai data sintetis saja."""
from html.parser import HTMLParser
import json
import sqlite3

import pytest

import attachments
import database
import student_pages
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU


class FormFoto(HTMLParser):
    """Baca kontrol sukses form Terapkan; details tertutup bukan disabled."""
    def __init__(self, teks, lampiran):
        super().__init__()
        self.aksi = f'/lampiran/{lampiran}/terapkan'
        self.dalam = False
        self.data = {}
        self.kartu = []
        self.feed(teks)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            assert not self.dalam, 'Form Terapkan tidak boleh bersarang'
            self.dalam = a.get('action') == self.aksi
        if not self.dalam:
            return
        if tag == 'fieldset':
            assert 'disabled' not in a, 'Fieldset tidak boleh menonaktifkan kartu'
        if tag == 'details' and 'soal-lampiran' in a.get('class', '').split():
            self.kartu.append(a)
        if tag == 'input' and a.get('name'):
            if 'disabled' in a or a.get('type') == 'checkbox' and 'checked' not in a:
                return
            self.data[a['name']] = a.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.dalam = False


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'foto-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


def sesi_foto(kon, format_jawaban='isian', jumlah=3):
    siswa = database.tambah_siswa(kon, 'Peserta Foto Sintetis', pemilik='guru')
    sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=jumlah,
                              format_jawaban=format_jawaban)
    return siswa, sesi, database.isi_sesi(kon, sesi)


def lampiran_foto(kon, sesi, hasil):
    return database.simpan_lampiran(kon, sesi, 'sintetis.jpg',
                                    hasil_json=json.dumps(hasil))


@pytest.mark.parametrize('format_jawaban,ada_foto,tampil', [
    ('pilihan_ganda', False, False), ('pilihan_ganda', True, True),
    ('isian', False, True), ('isian', True, True),
])
def test_upload_opsional_di_guru_dan_akun_anak(db, format_jawaban, ada_foto, tampil):
    with database.buka(db) as kon:
        siswa, sesi, _ = sesi_foto(kon, format_jawaban)
        if ada_foto:
            lid = lampiran_foto(kon, sesi, {})
        sebelum = tuple(kon.iterdump())
        guru = teacher_pages.halaman_sesi_lampiran(kon, sesi).decode()
        anak = student_pages.halaman_kerja_baru(kon, siswa, sesi).decode()
        tautan = student_pages.halaman_kerja_baru(
            kon, siswa, sesi, akses_tautan=True, jalur_aksi='/s/contoh',
        ).decode()
        assert ('name="foto"' in guru) == tampil
        assert ('name="foto"' in anak) == tampil
        assert 'name="foto"' not in tautan
        assert tuple(kon.iterdump()) == sebelum
        if ada_foto:
            assert f'href="/lampiran/{lid}"' in guru
            assert attachments.halaman_konfirmasi(kon, lid) is not None


def test_pg_anak_tidak_membaca_kunci_untuk_menyembunyikan_foto(db):
    with database.buka(db) as kon:
        siswa, sesi, _ = sesi_foto(kon, 'pilihan_ganda')
        def jaga(aksi, tabel, kolom, _db, _pemicu):
            if aksi == sqlite3.SQLITE_READ and kolom in {
                'kunci', 'kode_final', 'kode_usulan', 'malrule_id', 'alasan',
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        kon.set_authorizer(jaga)
        assert 'name="foto"' not in student_pages.halaman_kerja_baru(kon, siswa, sesi).decode()


def test_kartu_terlipat_tetap_terkirim_dan_get_tidak_menerapkan(db):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon)
        hasil = {'soal': [dict(nomor=b['nomor'], jawaban=b['kunci'], caraku='Hitung satu-satu')
                          for b in butir]}
        lid = lampiran_foto(kon, sesi, hasil)
        sebelum = tuple(kon.iterdump())
        teks = attachments.halaman_konfirmasi(kon, lid).decode()
        assert tuple(kon.iterdump()) == sebelum, 'GET konfirmasi tidak boleh menerapkan AI'
        form = FormFoto(teks, lid)
        assert len(form.kartu) == len(butir)
        assert all('open' not in k for k in form.kartu)
        assert '0 perlu dicek lebih dulu' in teks
        assert 'Belum diverifikasi manusia' in teks
        assert teks.count('>Terapkan &amp; diagnosis</button>') == 1
        assert '.foto-editorial-st .koreksi-simpan-st { position: static; }' in teks
        for b in butir:
            sid = b['sesi_soal_id']
            assert form.data[f'jwb_{sid}'] == b['kunci']
            assert form.data[f'cara_{sid}'] == 'Hitung satu-satu'
            assert f'name="blm_{sid}"' in teks
        assert attachments.terapkan(kon, lid, form.data)[0] == len(butir)
        assert all(b['jawaban'] == b['kunci'] and b['cara'] == 'Hitung satu-satu'
                   for b in database.isi_sesi(kon, sesi))
        assert database.ambil_lampiran(kon, lid)['status'] == 'diterapkan'
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0


@pytest.mark.parametrize('jawaban,cara,lama,buka', [
    ('12', 'Hitung', '', False), ('12', 'Hitung', '12', False),
    ('', 'Hitung', '', True), ('   ', 'Hitung', '', True),
    ('12', '', '', True), ('12', '  ', '', True),
    ('12', '?', '', True), ('12', 'mungkin 2?', '', True),
    ('?', 'Hitung', '', True), ('12', 'Hitung', '13', True),
])
def test_pengecualian_foto_terbuka(db, jawaban, cara, lama, buka):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon, jumlah=1)
        if lama:
            database.simpan_jawaban(kon, butir[0]['sesi_soal_id'], lama, 'Cara lama')
        lid = lampiran_foto(kon, sesi, {'soal': [dict(nomor=1, jawaban=jawaban, caraku=cara)]})
        teks = attachments.halaman_konfirmasi(kon, lid).decode()
        assert ('open' in FormFoto(teks, lid).kartu[0]) == buka


@pytest.mark.parametrize('hasil', ['', '{', '[]', 'null', '{"soal": []}',
    '{"soal": [null]}', '{"soal": [{"nomor": 1, "jawaban": 12}]}',
    '{"soal": [{"nomor": 1, "jawaban": "12", "caraku": "Hitung"}, null]}'])
def test_bacaan_kosong_atau_rusak_membuka_semua_kartu(db, hasil):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon)
        lid = database.simpan_lampiran(kon, sesi, 'sintetis.jpg', hasil_json=hasil)
        teks = attachments.halaman_konfirmasi(kon, lid).decode()
        form = FormFoto(teks, lid)
        assert len(form.kartu) == len(butir)
        assert all('open' in k for k in form.kartu)
        assert '0 dari 3 soal memiliki bacaan jawaban' in teks


def test_pg_selalu_terbuka_dan_tidak_memakai_jawaban_ai(db):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon, 'pilihan_ganda')
        lid = lampiran_foto(kon, sesi, {'soal': [dict(nomor=b['nomor'], jawaban=b['kunci'], caraku='Hitung')
                                                for b in butir]})
        teks = attachments.halaman_konfirmasi(kon, lid).decode()
        assert all('open' in k for k in FormFoto(teks, lid).kartu)
        assert teks.count('<select ') == len(butir)
        assert '0 dari 3 soal memiliki bacaan jawaban' in teks
        assert 'Pilihan ganda: pilih sesuai foto' in teks


def test_preview_escaped_dan_bacaan_parsial(db):
    with database.buka(db) as kon:
        _, sesi, _ = sesi_foto(kon)
        lid = lampiran_foto(kon, sesi, {'soal': [dict(nomor=1, jawaban='<b>12</b>', caraku='<script>x</script>')]})
        teks = attachments.halaman_konfirmasi(kon, lid).decode()
        ringkas = teks.split('<summary class="foto-ringkas">', 1)[1].split('</summary>', 1)[0]
        assert 'Soal 1' in ringkas and '&lt;b&gt;12&lt;/b&gt;' in ringkas
        assert '&lt;script&gt;x&lt;/script&gt;' in ringkas
        assert '<script>' not in teks
        assert '1 dari 3 soal memiliki bacaan jawaban' in teks
        assert sum('open' in k for k in FormFoto(teks, lid).kartu) == 2


@pytest.mark.parametrize('format_jawaban,ada_foto,peran,tampil', [
    ('isian', False, 'guru', True), ('pilihan_ganda', False, 'guru', False),
    ('pilihan_ganda', True, 'guru', True), ('isian', True, 'admin', False),
])
def test_minta_foto_hanya_kategori_tepat_dan_tujuan_tidak_buntu(db, format_jawaban, ada_foto, peran, tampil):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon, format_jawaban)
        database.tandai_selesai(kon, sesi)
        jid = database.simpan_jawaban(kon, butir[0]['sesi_soal_id'], butir[0]['kunci'], 'Cara asli')
        database.simpan_diagnosis(kon, jid, True, None, None)
        if ada_foto:
            lampiran_foto(kon, sesi, {})
        sebelum = tuple(kon.iterdump())
        teks = teacher_pages.halaman_sesi_stitch(kon, sesi, peran=peran).decode()
        kartu = teks.split('<article class="koreksi-kartu-st')[1:]
        cta = [k.split('</article>')[0] for k in kartu if '>Minta foto cara</a>' in k.split('</article>')[0]]
        assert len(cta) == int(tampil)
        if tampil:
            assert 'kategori-tanyakan_cara' in cta[0]
            assert f'href="/sesi/{sesi}/lampiran"' in cta[0]
            assert 'Simpan draf' in cta[0]
            assert 'name="foto"' in teacher_pages.halaman_sesi_lampiran(kon, sesi).decode()
        assert tuple(kon.iterdump()) == sebelum


def test_sesi_dibatalkan_tanpa_cta_foto_tetap_menampilkan_riwayat(db):
    with database.buka(db) as kon:
        _, sesi, butir = sesi_foto(kon)
        database.tandai_selesai(kon, sesi)
        jid = database.simpan_jawaban(kon, butir[0]['sesi_soal_id'], butir[0]['kunci'], 'Cara asli')
        database.simpan_diagnosis(kon, jid, True, None, None)
        database.batalkan_sesi(kon, sesi)
        sebelum = tuple(kon.iterdump())
        teks = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert '>Minta foto cara</a>' not in teks
        assert 'kategori-tanyakan_cara' in teks
        assert 'Sesi dibatalkan' in teks
        assert tuple(kon.iterdump()) == sebelum


def test_lampiran_asing_404_identik_tanpa_efek_samping(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            _, sesi, _ = sesi_foto(kon)
            asing = database.tambah_siswa(kon, 'Peserta Asing Sintetis', pemilik='keluarga-lain')
            sesi_asing = database.buat_sesi(kon, asing, 8, jumlah_soal=1)
        assert server.minta(f'/sesi/{sesi}/lampiran', auth=('guru', SANDI_GURU))[0] == 200
        with server.buka() as kon:
            sebelum = tuple(kon.iterdump())
        # Waktu respons bukan identitas resource; paksa pergantian detik agar
        # tes tidak kebetulan lulus hanya karena kedua request sangat cepat.
        tanggal = iter(('Sat, 24 Oct 2026 22:31:25 GMT', 'Sat, 24 Oct 2026 22:31:26 GMT'))
        monkeypatch.setattr(server.server.RequestHandlerClass, 'date_time_string', lambda self, timestamp=None: next(tanggal))
        respon = [server.minta(f'/sesi/{sid}/lampiran', auth=('guru', SANDI_GURU))
                  for sid in (sesi_asing, 999999)]
        assert respon[0][2]['Date'] != respon[1][2]['Date']
        assert respon[0][:2] == respon[1][:2]
        assert {k: v for k, v in respon[0][2].items() if k.lower() != 'date'} == {
            k: v for k, v in respon[1][2].items() if k.lower() != 'date'
        }
        assert respon[0][0] == 404
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    finally:
        server.berhenti()
