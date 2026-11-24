"""Blok "Peta Kemampuan lengkap" di halaman orang tua lewat HTTP nyata (D1-3): syarat tampil, tirai PIN, urutan, tanpa JS baru.

Memakai fixture `dunia` dan pembantu dari `test_orang_tua_http` (data sepenuhnya sintetis di tmp_path). Tes ini menjadi
sasaran mutation di `test_peta_laporan_ortu_mutation.py`.
"""
import base64
import hashlib
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pesanan_admin
import pesanan_dasar
import peta_laporan_store as store
import teacher_style
from pesanan_kit import buat as buat_order, operasi, terapkan as terapkan_bayar
from test_orang_tua_http import (  # noqa: F401  (dunia = fixture bersama)
    KATA_TERLARANG_ORTU, PIN_A, RUTE, SANDI_A, SANDI_B, NAMA_A, NAMA_B,
    _buat_order, _buka_tirai, _login, _pasang_pin, _req, _seed_cek, _siapkan_pesanan, _tanpa_gaya, dunia,
)
import admin_store

GURU = "guru-rahasia-sintetis"
CATATAN_A = "Catatan sintetis untuk anak A: makin lancar berhitung."
CATATAN_B = "CATATAN KHUSUS ANAK B"
ISI = {
    "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
    "jumlah_soal": 15, "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                                      {"materi": "Pengukuran", "benar": 2, "total": 7}],
    "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": [],
}
ISI_B = {**ISI, "skor": 33, "per_materi": [{"materi": "Geometri Anak B", "benar": 1, "total": 9}],
         "kuat": [], "perlu_dilatih": ["Geometri Anak B"]}
BLOK = re.compile(r'<section[^>]*id="ortu-peta".*?</section>', re.S)


def _peta(dunia, siswa, catatan=CATATAN_A, *, terbit=True, isi=ISI):
    with dunia.server.buka() as kon:
        store.buat_draf(kon, siswa, GURU, isi, 1_795_000_000)
        store.simpan_catatan(kon, siswa, catatan)
        if terbit:
            store.terbitkan(kon, siswa, GURU, 1_795_000_060)


def _lunas(dunia, siswa=None, akun=None, n=1):
    _siapkan_pesanan(dunia)
    _buat_order(dunia, dunia.a if siswa is None else siswa,
                dunia.akun_a.id_akun if akun is None else akun, n=n, bayar=True)


def _lunas_kedua(dunia):
    """Order lunas anak B (transaksi provider berbeda dari order anak A)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with pesanan_dasar.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = buat_order(kon, 2, akun=dunia.akun_b.id_akun, siswa=dunia.b, sekarang=now)
        terapkan_bayar(kon, order, 2, sekarang=now, transaction_id="trx-sintetis-0002")


def _halaman(dunia, nama="raka-m", sandi=SANDI_A):
    kode, isi, header = _req(dunia.server, RUTE, cookie=_login(dunia.server, nama, sandi))
    assert kode == 200
    return isi, header


def test_terbit_dan_lunas_menampilkan_blok_lengkap(dunia):
    _lunas(dunia)
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    blok = BLOK.search(isi).group(0)
    assert "Peta Kemampuan lengkap" in blok and "Ditinjau Guru Jagomat" in blok and CATATAN_A in blok
    assert len(re.findall(r"<meter\b", blok)) == 2 and "Catatan dari Guru" in blok
    assert 'max="7"' in blok and 'value="2"' in blok


def test_urutan_blok_setelah_hasil_cek_dan_sebelum_laporan_dan_pesanan(dunia):
    _lunas(dunia)
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], ["Pengukuran"])
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    posisi = [isi.index(f'id="{x}"') for x in ("ortu-hasil-cek", "ortu-peta", "ortu-laporan", "ortu-pesanan")]
    assert posisi == sorted(posisi) and isi.count('id="ortu-peta"') == 1


def test_draf_tidak_tampil_walau_lunas(dunia):
    _lunas(dunia)
    _peta(dunia, dunia.a, terbit=False)
    isi, _ = _halaman(dunia)
    assert 'id="ortu-peta"' not in isi and CATATAN_A not in isi


def test_terbit_tetapi_belum_bayar_tidak_tampil(dunia):
    _siapkan_pesanan(dunia)
    _buat_order(dunia, dunia.a, dunia.akun_a.id_akun, bayar=False)
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    assert 'id="ortu-peta"' not in isi and CATATAN_A not in isi


def test_terbit_tanpa_order_atau_penyimpanan_pesanan_belum_siap_tidak_tampil(dunia):
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    assert 'id="ortu-peta"' not in isi and CATATAN_A not in isi


def test_terbit_tetapi_direfund_tidak_tampil(dunia):
    _lunas(dunia)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with pesanan_dasar.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order_id = kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]
        hasil = pesanan_admin.catat_refund(kon, order_id, operasi(90), "admin-sintetis", "lainnya", now)
    assert hasil["status"] == pesanan_dasar.STATUS_DIREFUND
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    assert 'id="ortu-peta"' not in isi and CATATAN_A not in isi


def test_order_milik_akun_lain_tidak_membuka_peta(dunia):
    _lunas(dunia, akun=dunia.akun_b.id_akun)
    _peta(dunia, dunia.a)
    isi, _ = _halaman(dunia)
    assert 'id="ortu-peta"' not in isi


def test_anak_keluarga_lain_tidak_pernah_muncul(dunia):
    _lunas(dunia)
    _lunas_kedua(dunia)
    _peta(dunia, dunia.a)
    _peta(dunia, dunia.b, CATATAN_B, isi=ISI_B)
    isi_a, _ = _halaman(dunia)
    isi_b, _ = _halaman(dunia, "dina-m", SANDI_B)
    assert CATATAN_A in isi_a and "Pengukuran" in isi_a
    for bocor in (CATATAN_B, "Geometri Anak B", NAMA_B, 'value="1"'):
        assert bocor not in isi_a, bocor
    assert CATATAN_B in isi_b and "Geometri Anak B" in isi_b
    for bocor in (CATATAN_A, "Pengukuran", NAMA_A):
        assert bocor not in isi_b, bocor


def test_tirai_pin_tertutup_menyembunyikan_blok_dan_terbuka_atau_tanpa_pin_sama(dunia):
    _lunas(dunia)
    _peta(dunia, dunia.a)
    tanpa_pin = BLOK.search(_halaman(dunia)[0]).group(0)
    _pasang_pin(dunia, dunia.a, PIN_A)
    tertutup = _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))[1]
    assert 'id="ortu-peta"' not in tertutup and CATATAN_A not in tertutup and 'id="ortu-pin-masuk"' in tertutup
    terbuka = _req(dunia.server, RUTE, cookie=_buka_tirai(dunia))[1]
    assert BLOK.search(terbuka).group(0) == tanpa_pin


def test_tirai_tertutup_tidak_membaca_peta(dunia, monkeypatch):
    _lunas(dunia)
    _peta(dunia, dunia.a)
    _pasang_pin(dunia, dunia.a, PIN_A)

    def terlarang(*a, **k):
        raise AssertionError("peta dibaca saat tirai tertutup")
    monkeypatch.setattr(store, "terbit_terakhir", terlarang)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))
    assert kode == 200 and CATATAN_A not in isi


def test_tanpa_skrip_baru_dan_hash_csp_tidak_berubah(dunia):
    _lunas(dunia)
    sebelum = _halaman(dunia)[1]["Content-Security-Policy"]
    _peta(dunia, dunia.a)
    isi, header = _halaman(dunia)
    assert re.findall(r"<script[^>]*>(.*?)</script>", isi, flags=re.S) == [teacher_style.SKRIP_MATA_SANDI]
    assert "<script" not in BLOK.search(isi).group(0).lower()
    hash_skrip = base64.b64encode(hashlib.sha256(teacher_style.SKRIP_MATA_SANDI.encode()).digest()).decode()
    assert header["Content-Security-Policy"] == sebelum and "'sha256-" + hash_skrip + "'" in sebelum
    assert "style=" not in BLOK.search(isi).group(0)


def test_tanpa_kata_terlarang_nama_guru_dan_kontak_pada_halaman_dengan_peta(dunia):
    _lunas(dunia)
    _seed_cek(dunia, dunia.a, dunia.akun_a.id_akun, 72, "Cukup baik", ["Pecahan"], ["Pengukuran"])
    _peta(dunia, dunia.a)
    badan = _tanpa_gaya(_halaman(dunia)[0]).lower()
    assert 'id="ortu-peta"' in badan
    for kata in KATA_TERLARANG_ORTU + ("peringkat", "persentil", GURU):
        assert kata not in badan, kata


def test_catatan_html_dan_skrip_tampil_ter_escape_di_halaman(dunia):
    _lunas(dunia)
    _peta(dunia, dunia.a, '<script>alert(1)</script><b onclick="x">tebal</b>')
    isi, _ = _halaman(dunia)
    assert "<script>alert(1)" not in isi and '<b onclick' not in isi
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in BLOK.search(isi).group(0)
    assert len(re.findall(r"<script", isi)) == 1


def test_isi_rusak_menyembunyikan_blok_tanpa_500_dan_log_tanpa_data(dunia, caplog):
    _lunas(dunia)
    _peta(dunia, dunia.a)
    with dunia.server.buka() as kon:
        kon.execute("DROP TRIGGER peta_laporan_terbit_tetap")
        kon.execute("DROP TRIGGER peta_laporan_isi_tetap")
        kon.execute("UPDATE peta_laporan SET isi = '{rusak' WHERE siswa_id = ?", (dunia.a,))
    with caplog.at_level(logging.WARNING):
        kode, isi, _ = _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))
    assert kode == 200 and 'id="ortu-peta"' not in isi and 'id="ortu-hasil-cek"' in isi
    assert CATATAN_A not in caplog.text


def test_tabel_peta_hilang_halaman_tetap_200_tanpa_blok(dunia):
    _lunas(dunia)
    with dunia.server.buka() as kon:
        kon.execute("DROP TABLE peta_laporan")
    kode, isi, _ = _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))
    assert kode == 200 and 'id="ortu-peta"' not in isi
