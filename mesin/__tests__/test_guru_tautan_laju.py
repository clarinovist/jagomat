"""Pembatas laju tautan guru di memori proses: jendela dan batas parameter, plafon sendiri, thread-safe (data sintetis)."""

import threading

import pytest

import guru_tautan_laju as L
import laju_masuk

JENDELA = 3600
BATAS = 5
NAMA = "uji-guru"
IP = "10.0.0.1"
T0 = 1000000.0
TIMEOUT_THREAD_DETIK = 60
JUMLAH_THREAD = 8
GAGAL_PER_THREAD = 50


@pytest.fixture(autouse=True)
def laju_bersih():
    L._reset()
    yield
    L._reset()


def _gagal(jumlah, *, nama=NAMA, kunci=IP, sekarang=T0):
    for _ in range(jumlah):
        L.catat_gagal(nama, kunci, jendela=JENDELA, sekarang=sekarang)


def _diblokir(*, nama=NAMA, kunci=IP, sekarang=T0, batas=BATAS, jendela=JENDELA):
    return L.diblokir(nama, kunci, jendela=jendela, batas=batas, sekarang=sekarang)


# --- batas dan jendela ------------------------------------------------------------------

def test_gagal_sebelum_batas_belum_diblokir():
    _gagal(BATAS - 1)
    assert _diblokir() is False


def test_gagal_tepat_pada_batas_diblokir():
    _gagal(BATAS)
    assert _diblokir() is True


def test_gagal_lama_keluar_dari_jendela_tepat_pada_batas_waktu():
    _gagal(BATAS)
    assert _diblokir(sekarang=T0 + JENDELA - 1) is True
    assert _diblokir(sekarang=T0 + JENDELA) is False


def test_gagal_baru_tetap_dihitung_saat_gagal_lama_keluar():
    # Arrange: empat gagal di T0, satu gagal di T0 + 3000 detik
    _gagal(BATAS - 1)
    _gagal(1, sekarang=T0 + 3000)

    # Act / Assert: pada T0 + 3000 kelimanya masih dalam jendela
    assert _diblokir(sekarang=T0 + 3000) is True
    # pada T0 + 3600 gagal T0 keluar, tinggal satu gagal sehingga belum diblokir
    assert _diblokir(sekarang=T0 + JENDELA) is False


def test_batas_dan_jendela_dipakai_dari_parameter_bukan_konstanta_modul():
    _gagal(2)
    assert _diblokir(batas=2) is True
    assert _diblokir(batas=3) is False


def test_jendela_atau_batas_tidak_sah_ditolak():
    with pytest.raises(ValueError):
        L.catat_gagal(NAMA, IP, jendela=0, sekarang=T0)
    with pytest.raises(ValueError):
        _diblokir(batas=0)
    with pytest.raises(ValueError):
        _diblokir(jendela=-1)


def test_sekarang_tanpa_nilai_memakai_waktu_nyata():
    _gagal(BATAS, sekarang=None)
    assert L.diblokir(NAMA, IP, jendela=JENDELA, batas=BATAS) is True


# --- kunci ------------------------------------------------------------------------------

def test_nama_tidak_peka_huruf_besar_dan_spasi_tepi():
    _gagal(BATAS, nama="  Uji-Guru ")
    assert _diblokir(nama="uji-guru") is True
    assert _diblokir(nama="UJI-GURU") is True


def test_kunci_ip_berbeda_terpisah():
    _gagal(BATAS, kunci="10.0.0.1")
    assert _diblokir(kunci="10.0.0.2") is False


def test_nama_berbeda_terpisah():
    _gagal(BATAS, nama="guru-a")
    assert _diblokir(nama="guru-b") is False


def test_nama_atau_kunci_bukan_teks_ditolak():
    with pytest.raises(ValueError):
        L.catat_gagal(None, IP, jendela=JENDELA, sekarang=T0)
    with pytest.raises(ValueError):
        _diblokir(kunci=12)


# --- plafon kunci -----------------------------------------------------------------------

def test_plafon_kunci_membuang_kunci_dengan_gagal_terakhir_paling_tua(monkeypatch):
    # Arrange
    monkeypatch.setattr(L, "BATAS_KUNCI", 2)
    _gagal(2, nama="a", kunci="ip1", sekarang=T0)
    _gagal(1, nama="b", kunci="ip2", sekarang=T0 + 10)

    # Act: kunci ketiga melewati plafon, kunci "a" paling tua dibuang
    _gagal(1, nama="c", kunci="ip3", sekarang=T0 + 20)

    # Assert
    assert _diblokir(nama="a", kunci="ip1", batas=2, sekarang=T0 + 20) is False
    _gagal(1, nama="c", kunci="ip3", sekarang=T0 + 21)
    assert _diblokir(nama="c", kunci="ip3", batas=2, sekarang=T0 + 21) is True


def test_plafon_kunci_bawaan_adalah_4096():
    assert L.BATAS_KUNCI == 4096


def test_banjir_kunci_tidak_menyentuh_riwayat_laju_masuk(monkeypatch):
    # Arrange
    riwayat_awal = {("login-anak", "10.1.1.1"): [T0]}
    salinan_awal = {kunci: list(waktu) for kunci, waktu in riwayat_awal.items()}
    monkeypatch.setattr(laju_masuk, "_RIWAYAT", riwayat_awal)
    monkeypatch.setattr(L, "BATAS_KUNCI", 50)

    # Act
    for indeks in range(200):
        L.catat_gagal("guru-" + str(indeks), "10.2.2.2", jendela=JENDELA, sekarang=T0)

    # Assert
    assert laju_masuk._RIWAYAT == salinan_awal
    assert len(L._RIWAYAT) <= 50


# --- thread -----------------------------------------------------------------------------

def test_beberapa_thread_mencatat_tanpa_kehilangan_hitungan():
    # Arrange
    galat = []

    def pekerja():
        try:
            for _ in range(GAGAL_PER_THREAD):
                L.catat_gagal(NAMA, IP, jendela=JENDELA, sekarang=T0)
        except Exception as err:
            galat.append(err)

    threads = [threading.Thread(target=pekerja) for _ in range(JUMLAH_THREAD)]

    # Act
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=TIMEOUT_THREAD_DETIK)

    # Assert
    total = JUMLAH_THREAD * GAGAL_PER_THREAD
    assert not any(thread.is_alive() for thread in threads)
    assert galat == []
    assert _diblokir(batas=total) is True
    assert _diblokir(batas=total + 1) is False


def test_reset_mengosongkan_seluruh_riwayat():
    _gagal(BATAS)
    L._reset()
    assert _diblokir() is False
