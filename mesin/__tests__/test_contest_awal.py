"""Halaman awal Latihan Lomba, kartu beranda, dan potongan bersama (hitung mundur, target): render murni."""
import dataclasses
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_anak as A  # noqa: E402
import contest_awal as W  # noqa: E402
import contest_home as H  # noqa: E402
import contest_komponen as KP  # noqa: E402
import contest_paket as PK  # noqa: E402
import contest_results as R  # noqa: E402
import contest_store as K  # noqa: E402

SEKARANG = 1_795_000_000       # 18 Nov 2026, 18.06 WIB


def _sesi_selesai(sesi_id, nilai, mulai, lama=330):
    return R.RingkasSesi(sesi_id=sesi_id, mulai_epoch=mulai, selesai_epoch=mulai + lama, status="dikumpul", nilai=nilai,
                         jumlah_soal=10, waktu_terpakai_detik=lama, per_topik=())


def _ringkas(**ubah):
    dasar = dict(paket=PK.PAKET_AKTIF, berjalan=None, sisa_detik=0, terisi=frozenset(), nomor_lanjut=1, riwayat=(),
                 nilai_terbaik=None, nilai_terakhir=None, selesai_hari_ini=0,
                 hitung_mundur="Lomba tinggal 24 hari lagi", sekarang=SEKARANG)
    return A.RingkasAnak(**{**dasar, **ubah})


def _berjalan(id_=9):
    return K.SesiRingkas(id=id_, siswa_id=1, status="berjalan", mulai_epoch=SEKARANG - 100, batas_epoch=SEKARANG + 800,
                         selesai_epoch=None)


def _awal(**ubah):
    return W.halaman_awal(_ringkas(**ubah)).decode()


def _badan(isi):
    return re.sub(r"<style>.*?</style>", "", isi, flags=re.S)


# --- halaman awal: kepala dan aturan ---------------------------------------------------------------------

def test_awal_memuat_tautan_beranda_maskot_judul_paket_dan_dua_tombol_mode():
    isi = _badan(_awal())

    assert '<a class="tautan-beranda" href="/murid">' in isi and "Beranda</a>" in isi
    assert re.search(r'<img src="/aset/maskot-menunjuk-v3-96\.png" alt="" class="maskot-kartu"', isi)
    assert '<h1 class="judul">Mode Lomba</h1>' in isi
    assert '>Latihan (10 soal · 15 menit)</button>' in isi
    assert '>Simulasi Lomba (35 soal · 60 menit)</button>' in isi
    assert "Simulasi Lomba mirip lomba sungguhan: 30 pilihan ganda + 5 isian." in isi


def test_tombol_mode_mengikuti_durasi_paket_anak_bukan_angka_tetap():
    paket = dataclasses.replace(PK.PAKET_AKTIF, durasi_detik=1200, durasi_simulasi_detik=45 * 60, nama_pendek="Uji")

    isi = _badan(W.halaman_awal(_ringkas(paket=paket)).decode())

    assert ">Latihan (10 soal · 20 menit)</button>" in isi and ">Mode Lomba</h1>" in isi
    assert ">Simulasi Lomba (35 soal · 45 menit)</button>" in isi


def test_catatan_waktu_tetap_berjalan_dan_jawaban_tersimpan():
    isi = _awal()

    assert "Waktu terus berjalan walaupun kamu keluar dari halaman ini. Jawabanmu tetap tersimpan." in isi


def test_nama_acara_paket_tidak_tampil_ke_anak():
    paket = dataclasses.replace(PK.PAKET_AKTIF, nama_pendek="Nama Acara Uji", nama="Nama Acara Uji Lengkap")

    isi = W.halaman_awal(_ringkas(paket=paket)).decode()

    assert "Nama Acara Uji" not in isi and '<h1 class="judul">Mode Lomba</h1>' in isi


# --- Mulai / Lanjutkan -----------------------------------------------------------------------------------

def test_tanpa_sesi_berjalan_menawarkan_dua_mode_lewat_form_post():
    isi = _awal()

    assert isi.count('action="/murid/lomba/mulai"') == 2 and "Lanjutkan" not in isi
    assert '<input type="hidden" name="mode" value="latihan">' in isi
    assert '<input type="hidden" name="mode" value="simulasi">' in isi


def test_sesi_berjalan_menawarkan_lanjutkan_ke_soal_kosong_pertama_dengan_sisa_waktu_dan_terisi():
    isi = _awal(berjalan=_berjalan(9), sisa_detik=754, terisi=frozenset({1, 2, 4}), nomor_lanjut=3)

    assert 'href="/murid/lomba/sesi/9?no=3">Lanjutkan</a>' in isi
    assert "12:34" in isi and "3 dari 10 soal terisi" in isi
    assert 'action="/murid/lomba/mulai"' not in isi


def test_lanjutkan_ke_soal_satu_bila_semua_terisi():
    isi = _awal(berjalan=_berjalan(9), sisa_detik=100, terisi=frozenset(range(1, 11)), nomor_lanjut=1)

    assert 'href="/murid/lomba/sesi/9?no=1">Lanjutkan</a>' in isi and "10 dari 10 soal terisi" in isi


# --- hitung mundur dan target ------------------------------------------------------------------------------

def test_awal_menampilkan_hitung_mundur_dan_target_hari_ini_dengan_bar():
    isi = _awal(selesai_hari_ini=1)

    assert '<p class="hitung-mundur">Lomba tinggal 24 hari lagi</p>' in isi
    assert "Latihan hari ini: 1 dari 2" in isi and 'style="width:50%"' in isi
    assert 'role="progressbar"' in isi and 'aria-valuenow="1"' in isi and 'aria-valuemax="2"' in isi
    assert "Target hari ini tercapai!" not in isi


def test_target_tercapai_menampilkan_ucapan_dan_bar_penuh():
    isi = _awal(selesai_hari_ini=2)

    assert "Target hari ini tercapai!" in isi and 'style="width:100%"' in isi


def test_target_melebihi_batas_tetap_tercapai_dengan_bar_tidak_lebih_dari_penuh():
    isi = _awal(selesai_hari_ini=5)

    assert "Latihan hari ini: 5 dari 2" in isi and 'style="width:100%"' in isi and 'aria-valuenow="2"' in isi


def test_target_nol_tidak_tampil_sama_sekali():
    paket = dataclasses.replace(PK.PAKET_AKTIF, target_harian=0)

    isi = _badan(W.halaman_awal(_ringkas(paket=paket)).decode())

    assert "Latihan hari ini" not in isi and "bar-target" not in isi and "Target hari ini" not in isi


def test_hitung_mundur_kosong_tidak_menampilkan_baris_hitung_mundur():
    isi = _badan(_awal(hitung_mundur=""))

    assert "hitung-mundur" not in isi and "Latihan hari ini: 0 dari 2" in isi


def test_tanpa_hitung_mundur_dan_tanpa_target_kartu_kemajuan_tidak_ada():
    paket = dataclasses.replace(PK.PAKET_AKTIF, target_harian=0)

    isi = _badan(W.halaman_awal(_ringkas(paket=paket, hitung_mundur="")).decode())

    assert "Kemajuanmu" not in isi


@pytest.mark.parametrize("selesai,target,persen", [(0, 2, 0), (1, 2, 50), (2, 2, 100), (3, 2, 100), (1, 3, 33), (0, 0, 0), (-1, 2, 0)])
def test_persen_bar_target(selesai, target, persen):
    assert KP.persen_target(selesai, target) == persen


# --- nilai terbaik dan riwayat -------------------------------------------------------------------------------

def test_nilai_terbaik_tampil_bila_ada_dan_tersembunyi_bila_tidak():
    assert "Nilai terbaikmu" not in _awal()
    isi = _badan(_awal(nilai_terbaik=8))

    assert "Nilai terbaikmu" in isi and "<strong>8/10</strong>" in isi


def test_riwayat_memakai_label_tanggal_relatif_dan_tautan_hasil():
    hari_ini = SEKARANG - 5 * 3600                                  # 13.06 WIB hari ini (18 Nov)
    kemarin = SEKARANG - 24 * 3600 - 5 * 3600
    lama = SEKARANG - 5 * 24 * 3600
    isi = _awal(riwayat=(_sesi_selesai(12, 8, hari_ini), _sesi_selesai(11, 6, kemarin), _sesi_selesai(10, 3, lama)))

    tautan = re.findall(r'<a class="tautan-latihan" href="(/murid/lomba/hasil/\d+)"><span>([^<]+) <span class="label-mode">Latihan</span></span><strong>([^<]+)</strong>', isi)
    assert tautan == [("/murid/lomba/hasil/12", "Hari ini, 13.06", "8/10"), ("/murid/lomba/hasil/11", "Kemarin, 13.06", "6/10"),
                      ("/murid/lomba/hasil/10", "Jumat, 13 Nov", "3/10")]


def test_riwayat_kosong_tidak_menampilkan_bagian_latihan_terakhir():
    assert "Latihan terakhir" not in _awal()


def test_riwayat_dipotong_lima():
    riwayat = tuple(_sesi_selesai(100 + i, 5, SEKARANG - 1000 - i) for i in range(8))

    isi = _awal(riwayat=riwayat)

    assert isi.count('href="/murid/lomba/hasil/') == 5


def test_awal_tanpa_skrip_dan_tanpa_penangan_kejadian():
    isi = _awal(berjalan=_berjalan(), sisa_detik=700, riwayat=(_sesi_selesai(1, 5, SEKARANG - 100),))

    assert "<script" not in isi and not re.search(r"\son[a-z]+\s*=", isi, re.I)


# --- kartu beranda ---------------------------------------------------------------------------------------------

def test_kartu_kecil_tanpa_sesi_berjalan_menawarkan_mulai_latihan_dan_nilai_terakhir():
    kartu = H.kartu_beranda(_ringkas(nilai_terakhir=7))

    assert '<section class="lomba-beranda"' in kartu and ">Mode Lomba</h2>" in kartu
    assert '<a class="lb-tombol" href="/murid/lomba">Mulai latihan</a>' in kartu and "Nilai terakhir: 7/10" in kartu
    assert "Latihan Lomba" not in kartu and "Lanjutkan" not in kartu and "maskot" not in kartu


def test_kartu_tanpa_nilai_terakhir_tidak_menyebutnya():
    assert "Nilai terakhir" not in H.kartu_beranda(_ringkas())


def test_kartu_dengan_sesi_berjalan_menampilkan_status_sisa_terisi_dan_lanjutkan():
    kartu = H.kartu_beranda(_ringkas(berjalan=_berjalan(9), sisa_detik=754, terisi=frozenset({1, 2}), nomor_lanjut=3))

    assert "Latihanmu masih berjalan" in kartu and "Sisa waktu 12:34" in kartu and "2 dari 10 soal terisi" in kartu
    assert '<a class="lb-tombol" href="/murid/lomba/sesi/9?no=3">Lanjutkan</a>' in kartu and "Mulai latihan" not in kartu


def test_kartu_memuat_hitung_mundur_dan_target_hari_ini():
    kartu = H.kartu_beranda(_ringkas(selesai_hari_ini=2))

    assert "Lomba tinggal 24 hari lagi" in kartu
    assert "Latihan hari ini: 2 dari 2" in kartu and "Target hari ini tercapai!" in kartu


def test_kartu_besar_memuat_maskot_dan_catatan_belum_ada_latihan_guru():
    kartu = H.kartu_beranda(_ringkas(), besar=True)

    assert '<section class="lomba-beranda besar"' in kartu and "/aset/maskot-menunjuk-v3-96.png" in kartu
    assert "Belum ada latihan dari gurumu." in kartu
    assert "Belum ada latihan dari gurumu." not in H.kartu_beranda(_ringkas(), besar=False)


def test_kartu_beranda_tanpa_skrip_dan_tanpa_nama_acara():
    paket = dataclasses.replace(PK.PAKET_AKTIF, nama_pendek="Nama Acara Uji")

    kartu = H.kartu_beranda(_ringkas(paket=paket))

    assert "<script" not in kartu and "Nama Acara Uji" not in kartu and ">Mode Lomba</h2>" in kartu


# --- audit area anak Fase 2 (#13): satu kotak catatan, kartu beranda selaras kartu lain ----------------

def test_awal_catatan_waktu_dan_simulasi_teks_kecil_tanpa_kotak_kuning_saat_idle():
    isi = _badan(_awal())

    assert f'<p class="catatan-kecil">{W.CATATAN_WAKTU}</p>' in isi
    assert 'class="catatan-kecil">Simulasi Lomba mirip' in isi
    assert 'class="catatan"' not in isi


def test_awal_sesi_berjalan_hanya_satu_kotak_catatan():
    isi = _badan(_awal(berjalan=_berjalan(), sisa_detik=700, terisi=frozenset({1})))

    assert isi.count('class="catatan"') == 1 and "masih berjalan" in isi
    assert f'<p class="catatan-kecil">{W.CATATAN_WAKTU}</p>' in isi


def test_kartu_beranda_punya_ikon_eyebrow_dan_judul_seperti_kartu_lain():
    kartu = H.kartu_beranda(_ringkas())

    assert '<span class="murid-ikon-topik-st"><svg class="murid-ikon-st"' in kartu
    assert f'<span class="murid-tahap-st">{H.EYEBROW}</span><h2 id="judul-lomba">Mode Lomba</h2>' in kartu
    assert 'class="target-teks">Latihan hari ini: 0 dari' in kartu
