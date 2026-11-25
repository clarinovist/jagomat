"""Jatah pendaftaran guru mandiri: per IP dan global, terpisah dari pembatas login (butir QA #5, 25 Nov 2026; data sintetis)."""
import threading

import pytest

import jatah_pendaftaran as J
import laju_masuk


@pytest.fixture(autouse=True)
def _bersih():
    J._reset()
    laju_masuk._reset()
    yield
    J._reset()
    laju_masuk._reset()


def test_per_ip_lima_lalu_habis_dan_pulih_setelah_jendela():
    assert [J.ambil("1.1.1.1", sekarang=100.0) for _ in range(J.BATAS_PER_IP + 1)] == [True] * J.BATAS_PER_IP + [False]
    assert J.ambil("2.2.2.2", sekarang=100.0) is True                       # IP lain tidak terpengaruh
    assert J.ambil("1.1.1.1", sekarang=100.0 + J.JENDELA_DETIK - 1) is False
    assert J.ambil("1.1.1.1", sekarang=100.0 + J.JENDELA_DETIK + 1) is True


def test_ipv6_dalam_satu_blok_64_berbagi_jatah_dan_ipv4_mapped_sama_dengan_ipv4():
    for n in range(J.BATAS_PER_IP):
        assert J.ambil("2001:db8:1:2:%x::1" % n, sekarang=5.0) is True       # alamat berbeda, blok /64 sama
    assert J.ambil("2001:db8:1:2:ffff::9", sekarang=5.0) is False
    assert J.ambil("2001:db8:1:3::1", sekarang=5.0) is True                   # blok /64 lain
    for _ in range(J.BATAS_PER_IP):
        assert J.ambil("::ffff:198.51.100.7", sekarang=6.0) is True
    assert J.ambil("198.51.100.7", sekarang=6.0) is False


def test_batas_global_menahan_banyak_ip_berbeda():
    hasil = [J.ambil("10.0.%d.%d" % (n // 250, n % 250), sekarang=50.0) for n in range(J.BATAS_GLOBAL + 20)]
    assert sum(hasil) == J.BATAS_GLOBAL and hasil[:J.BATAS_GLOBAL] == [True] * J.BATAS_GLOBAL


def test_membanjiri_kunci_laju_login_tidak_membuka_jatah():
    for _ in range(J.BATAS_PER_IP):
        assert J.ambil("3.3.3.3", sekarang=10.0) is True
    for n in range(laju_masuk.BATAS_KUNCI + 500):                           # banjir /masuk dengan nama acak
        laju_masuk.catat_gagal("acak-%d" % n, "9.9.9.9", 10.0)
    assert J.ambil("3.3.3.3", sekarang=11.0) is False


def test_memori_dibatasi_oleh_plafon_kunci(monkeypatch):
    monkeypatch.setattr(J, "BATAS_KUNCI", 50)
    monkeypatch.setattr(J, "BATAS_GLOBAL", 10**6)
    for n in range(200):
        J.ambil("ip-%d" % n, sekarang=float(n) / 100)
    assert J._jumlah_kunci() <= 50


def test_atomik_di_bawah_permintaan_paralel():
    hasil, gerbang = [], threading.Barrier(40)

    def coba():
        gerbang.wait()
        hasil.append(J.ambil("203.0.113.9"))

    pekerja = [threading.Thread(target=coba) for _ in range(40)]
    for t in pekerja:
        t.start()
    for t in pekerja:
        t.join()
    assert sum(hasil) == J.BATAS_PER_IP and len(hasil) == 40
