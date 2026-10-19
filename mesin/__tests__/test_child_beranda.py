"""Beranda anak: badge menunggu, teks dilipat, baris hasil sesi, banner Perkembangan, durasi."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import profile_history  # noqa: E402
import profile_home  # noqa: E402
from learning_cycle import BuktiSiklus, RencanaBelajar, SesiSiklus  # noqa: E402

SISWA = {"id": 9, "nama": "Anak"}


def _kartu(tindakan="konfirmasi_hasil", hari_ini=date(2026, 10, 19)):
    bukti = BuktiSiklus(9, "P3", sesi=(SesiSiklus(63, 9, "P3", "evaluasi", date(2026, 9, 22)),))
    rencana = RencanaBelajar(tindakan, "uji", sesi_id=63)
    return profile_home.kartu(rencana, bukti, SISWA, jumlah_soal=15, hari_ini=hari_ini)


def test_badge_menunggu_menghitung_hari_sejak_sesi_yang_dituju():
    assert 'Menunggu 27 hari' in _kartu()
    assert 'anak-chip-perhatian-st' in _kartu().split('beranda-kepala-kartu-st', 1)[1].split('</div>', 1)[0]


def test_badge_menunggu_kosong_bila_baru_hari_ini_atau_bukan_tinjauan():
    assert 'Menunggu' not in _kartu(hari_ini=date(2026, 9, 22))
    assert 'Menunggu' not in _kartu(tindakan="lanjutkan_sesi")


def test_peringatan_konfirmasi_dilipat_di_cara_membaca_progres():
    h = _kartu()
    luar, lipatan = h.split('<details class="rincian-ui-st batas-rencana-st">', 1)
    assert 'Konfirmasi hanya setelah hasil diperiksa.' not in luar
    assert 'Konfirmasi hanya setelah hasil diperiksa.' in lipatan.split('</details>', 1)[0]


def test_kalimat_peta_perjalanan_sejajar_dengan_judul_posisi():
    posisi = profile_home.posisi(RencanaBelajar("pilih_variasi", "uji"), BuktiSiklus(9, "P3"), "Anak")
    kepala = posisi.split('<div class="beranda-posisi-kepala-st">', 1)[1].split('</div>', 1)[0]
    assert 'Posisi Anak: tahap' in kepala and 'Ini peta perjalanan, bukan nilai.' in kepala
    assert posisi.count('Ini peta perjalanan, bukan nilai.') == 1


def _baris(sid, n=10, benar=0, selesai='2026-09-15 10:03:00', mulai='2026-09-15 10:00:00', **lain):
    return {'id': sid, 'topik': 't', 'tanggal': '15 Sep', 'n': n, 'benar': benar, 'selesai': selesai,
            'mulai': mulai, 'badge': '<span class="badge-direview perlu">Perlu ditinjau</span>', **lain}


def _sesi_lain(*baris):
    return profile_home.sesi_lain(baris, judul_topik=lambda t: (t, None), tanggal=lambda t: t,
                                  badge_tinjauan=lambda r: r['badge'])


def test_sesi_lain_memperingatkan_hasil_nol_yang_terlalu_cepat():
    h = _sesi_lain(_baris(55))
    assert 'Hasil 0 dari 10 dalam 3 menit, mungkin belum dikerjakan' in h
    assert 'Perlu ditinjau' in h, 'status tinjauan tetap tampil di kartu sesi lain'


def test_sesi_lain_tanpa_peringatan_bila_waktu_wajar_atau_ada_benar():
    lambat = _baris(55, mulai='2026-09-15 10:00:00', selesai='2026-09-15 10:30:00')
    assert 'mungkin belum dikerjakan' not in _sesi_lain(lambat)
    assert 'mungkin belum dikerjakan' not in _sesi_lain(_baris(56, benar=1))
    assert 'mungkin belum dikerjakan' not in _sesi_lain(_baris(57, mulai=None, selesai=None))


def test_sesi_lain_draf_menampilkan_skor_dan_aksi_lanjutkan():
    draf = _baris(54, n=15, benar=8, badge='<span class="badge-direview draf">Draf tersimpan</span>')
    h = _sesi_lain(draf)
    assert '8 dari 15 benar' in h and 'Draf tersimpan' in h
    assert re.search(r'aria-label="Lanjutkan sesi 54">Lanjutkan</a>', h)


def test_sesi_lain_mempertahankan_urutan_dari_query_terlama_dahulu():
    h = _sesi_lain(_baris(54), _baris(55))
    assert h.index('data-sesi-id="54"') < h.index('data-sesi-id="55"')


def test_banner_perkembangan_beranda_punya_tautan_tebal(tmp_path, monkeypatch):
    path = tmp_path / 'b.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Anak', 'P3', pemilik='guru')
        h = profile_home.tautan_perkembangan(kon, sid)
    assert h.startswith('<a class="beranda-perkembangan-st anak-banner-st"')
    assert 'Lihat perkembangan →' in h and f'/anak/{sid}?section=perkembangan' in h


@pytest.mark.parametrize('mulai,selesai,awal,akhir,hasil', [
    ('2026-09-15 10:00:00', '2026-09-15 10:03:00', None, None, 180),
    (None, None, '2026-09-15 10:00:00', '2026-09-15 10:01:30', 90),
    ('2026-09-15 10:00:00', '2026-09-15 10:00:00', '2026-09-15 10:00:00', '2026-09-15 10:02:00', 120),
    (None, None, None, None, None),
    ('bukan tanggal', 'bukan tanggal', None, None, None),
])
def test_durasi_detik_jatuh_ke_jawaban_tercatat_dan_tidak_mengarang(mulai, selesai, awal, akhir, hasil):
    assert profile_history.durasi_detik(mulai, selesai, awal, akhir) == hasil


def test_css_beranda_menutup_celah_formulir_pendamping_tanpa_menghapusnya():
    from child_beranda_style import GAYA_BERANDA as css
    assert 'form[action="/pendamping/inline/buka"] { display: contents; }' in css
    slot = '<form method="post" action="/pendamping/inline/buka"><button class="pendamping-pemicu">P</button></form>'
    bukti = BuktiSiklus(9, "P3", sesi=(SesiSiklus(63, 9, "P3", "evaluasi", date(2026, 9, 22)),))
    h = profile_home.kartu(RencanaBelajar("konfirmasi_hasil", "uji", sesi_id=63), bukti, SISWA, slot_bantuan=slot)
    assert slot in h, "tombol Pendamping di kartu tetap dirender; hanya kotaknya yang tidak memakan ruang"


def test_css_beranda_tanpa_garis_alur_dan_badge_sesi_memakai_sumber_bersama():
    from child_badge_style import css_badge_review
    from child_beranda_style import GAYA_BERANDA as css
    alur = css.split(".beranda-posisi-st .alur-rencana-jelas-st {", 1)[1].split("}", 1)[0]
    assert "border: 0" in alur and "border-top" not in alur
    assert css_badge_review(".bungkus-st.profil-workspace-st.beranda-profil-st .beranda-sesi-st") in css


def test_banner_bersama_menjaga_tautan_di_kanan_saat_teks_panjang():
    from child_style import GAYA_ANAK as css
    assert ".anak-banner-st > span:first-child { flex: 1 1 18rem; min-width: 0; }" in css
    assert ".anak-banner-tautan-st { flex: none;" in css
