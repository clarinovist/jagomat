"""Kalender WIB tetap benar di host UTC dan batas hari tanpa data nyata."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import os
import sqlite3
import time

import pytest

import database
import domain_clock
import learning_cycle as lc
import learning_journey
import report_metrics
import skill_pilot_service
from http_test_kit import ServerUji
from test_skill_pilot_http import test_http_pilih_buat_cetak_tinjau_konfirmasi as alur_pilot
from test_mastery_context import _sesi, _muat, DASAR


@pytest.fixture(params=['UTC', 'Asia/Jakarta'])
def zona_host(request, monkeypatch):
    lama = os.environ.get('TZ')
    monkeypatch.setenv('TZ', request.param)
    time.tzset()
    try:
        yield request.param
    finally:
        if lama is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = lama
        time.tzset()


def bekukan(monkeypatch, instan):
    class Jam(datetime):
        @classmethod
        def now(cls, tz=None):
            return instan.astimezone(tz) if tz else instan.astimezone().replace(tzinfo=None)

    class TanggalHost(date):
        @classmethod
        def today(cls):
            return instan.astimezone().date()

    monkeypatch.setattr(domain_clock, 'datetime', Jam)
    # Jalur lama harus merah deterministik, bukan menunggu jam tertentu di CI.
    monkeypatch.setattr(lc, 'date', TanggalHost)
    monkeypatch.setattr(learning_journey, 'date', TanggalHost)
    return instan.astimezone(timezone(timedelta(hours=7))).date()


@pytest.mark.parametrize('instan,harapan', [
    ('2026-09-21T16:59:59+00:00', '2026-09-21'),
    ('2026-09-21T17:00:00+00:00', '2026-09-22'),
    ('2026-09-30T17:00:00+00:00', '2026-10-01'),
    ('2026-12-31T17:00:00+00:00', '2027-01-01'),
    ('2028-02-28T17:00:00+00:00', '2028-02-29'),
])
def test_hari_wib_tidak_mengikuti_host(zona_host, monkeypatch, instan, harapan):
    bekukan(monkeypatch, datetime.fromisoformat(instan))
    assert domain_clock.hari_wib().isoformat() == harapan
    assert report_metrics.hari_wib().isoformat() == harapan


@pytest.mark.parametrize('jam', [16, 17, 23])
def test_http_bukti_hari_ini_tidak_hilang_di_batas_wib(zona_host, monkeypatch, tmp_path, jam):
    instan = datetime(2026, 9, 21, jam, tzinfo=timezone.utc)
    hari = bekukan(monkeypatch, instan)
    waktu = instan.astimezone(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S')
    sambung_asli = sqlite3.connect

    def sambung(*args, **kwargs):
        kon = sambung_asli(*args, **kwargs)
        kon.create_function('date', 2, lambda *_: hari.isoformat())
        kon.create_function('datetime', 2, lambda *_: waktu)
        return kon

    monkeypatch.setattr(sqlite3, 'connect', sambung)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        # Jalur HTTP yang gagal di CI, assertion status aslinya tidak diganti.
        alur_pilot((server, siswa))
    finally:
        server.berhenti()


def test_bukti_besok_ditolak_hari_eksplisit_dihormati(zona_host, monkeypatch, tmp_path):
    hari = bekukan(monkeypatch, datetime(2026, 9, 21, 23, tzinfo=timezone.utc))
    path = tmp_path / 'sintetis.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        _sesi(kon, siswa, 'P3', 61, hari)
        bukti = _muat(kon, siswa)
    awal = repr(bukti)
    assert lc.penguasaan_konteks(bukti, siswa, (DASAR,))[0].hasil.status == 'dipelajari'
    assert lc.penguasaan_konteks(bukti, siswa, (DASAR,), hari - timedelta(days=1))[0].hasil.status == 'belum_dinilai'
    besok = replace(bukti, sesi=tuple(replace(s, tanggal=hari + timedelta(days=1)) for s in bukti.sesi))
    assert lc.penguasaan_konteks(besok, siswa, (DASAR,))[0].hasil.status == 'belum_dinilai'
    assert repr(bukti) == awal


def test_rekomendasi_dan_perjalanan_tetap_menunggu_hari_berbeda(zona_host, monkeypatch):
    hari = bekukan(monkeypatch, datetime(2026, 9, 21, 23, tzinfo=timezone.utc))
    kemarin = hari - timedelta(days=1)
    sesi = lc.SesiSiklus(1, 1, 'P3', 'pemetaan', kemarin, selesai=str(kemarin),
                        dikonfirmasi=str(kemarin), konfirmasi_id=1, putaran_id=1,
                        outcomes=(lc.OutcomeSiklus('deret_aritmetika', True),))
    bukti = lc.BuktiSiklus(1, 'P3', (sesi,), (lc.PutaranSiklus(1, 1, 'P3', kemarin),))
    assert lc.rencana_berikutnya(bukti, 1).tindakan == 'pemetaan'
    assert lc.rencana_berikutnya(bukti, 1, kemarin).tindakan == 'tunggu_pemetaan'
    assert learning_journey.perjalanan_belajar(bukti, 1) == learning_journey.perjalanan_belajar(bukti, 1, hari)


def test_aksi_pilot_memakai_wib_dan_menerima_hari_eksplisit(monkeypatch, tmp_path):
    hari = bekukan(monkeypatch, datetime(2099, 12, 31, 23, tzinfo=timezone.utc))
    path = tmp_path / 'sintetis.db'
    database.siapkan(path)
    tertangkap = []

    def tangkap(kon, siswa, hari=None):
        tertangkap.append(hari)
        raise RuntimeError('hentikan sebelum mutasi')

    monkeypatch.setattr(skill_pilot_service, 'keadaan', tangkap)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        data = {'aksi': 'mulai', 'revisi': skill_pilot_service.revisi(kon, siswa)}
        awal = tuple(kon.iterdump())
        for opsi in ({}, {'hari': date(2026, 1, 1)}):
            with pytest.raises(RuntimeError, match='hentikan sebelum mutasi'):
                skill_pilot_service.jalankan(kon, siswa, data, **opsi)
        assert tuple(kon.iterdump()) == awal
    assert tertangkap == [hari, date(2026, 1, 1)]
