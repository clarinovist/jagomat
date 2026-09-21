"""Satu pembacaan pilot tidak boleh memakai dua tanggal saat tengah malam."""
from datetime import date, timedelta

import pytest

import domain_clock
import learning_cycle as lc
import skill_pilot_service
import skill_pilot_ui
from test_skill_pilot_evidence import paket, LANGSUNG, KISI, HARI
from test_skill_pilot_http import server, test_http_pilih_buat_cetak_tinjau_konfirmasi as isi_pilot


def jam_bergeser(monkeypatch, hari):
    panggilan = []

    def sekarang():
        panggilan.append(1)
        return hari + timedelta(days=len(panggilan) - 1)

    monkeypatch.setattr(domain_clock, 'hari_wib', sekarang)
    return panggilan


def test_penguasaan_semua_konteks_pakai_satu_tanggal(monkeypatch):
    bukti = paket(((LANGSUNG, True, False), (KISI, True, False)))
    # Tepat sebelum umur bukti28hari; panggilan berikutnya akan mencabut status.
    hari = HARI + timedelta(days=25)
    harapan = lc.penguasaan_pilot(bukti, 1, (LANGSUNG, KISI), hari)
    assert all(h.hasil.status == 'terbukti' for h in harapan)
    panggilan = jam_bergeser(monkeypatch, hari)
    assert lc.penguasaan_pilot(bukti, 1, (LANGSUNG, KISI)) == harapan
    assert len(panggilan) == 1
    panggilan.clear()
    assert lc.penguasaan_pilot(bukti, 1, (LANGSUNG, KISI), hari) == harapan
    assert panggilan == []


@pytest.mark.parametrize('permukaan', ['keadaan', 'kartu', 'laporan'])
def test_operasi_pilot_memotret_hari_sekali_tanpa_mutasi(server, monkeypatch, permukaan):
    isi_pilot(server)
    srv, siswa = server
    with srv.buka() as kon:
        hari = date.fromisoformat(kon.execute('SELECT tanggal FROM sesi').fetchone()[0])
        awal = tuple(kon.iterdump())
        panggilan = jam_bergeser(monkeypatch, hari)
        if permukaan == 'keadaan':
            harapan = skill_pilot_service.keadaan(kon, siswa, hari)
            assert panggilan == []
            assert skill_pilot_service.keadaan(kon, siswa) == harapan
        elif permukaan == 'kartu':
            harapan = skill_pilot_ui.kartu(kon, siswa, hari=hari)
            assert panggilan == []
            assert skill_pilot_ui.kartu(kon, siswa) == harapan
        else:
            assert 'Masih dipelajari' in skill_pilot_ui.laporan(kon, siswa)
        assert len(panggilan) == 1
        assert tuple(kon.iterdump()) == awal
