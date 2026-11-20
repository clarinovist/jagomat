"""Cache badge sidebar admin: TTL (jam diinjeksi), invalidasi POST admin, galat tidak di-cache, thread."""
import threading

import pytest

import admin_http
import admin_sinyal_cache as C
import admin_antrean_pages as AP


class _Jam:
    def __init__(self):
        self.sekarang = 100.0

    def __call__(self):
        return self.sekarang


def _penghitung(nilai):
    panggilan = []

    def hitung():
        panggilan.append(1)
        return nilai if not callable(nilai) else nilai()
    return hitung, panggilan


def test_nilai_dipakai_ulang_selama_ttl_lalu_dihitung_ulang():
    jam = _Jam()
    hitung, panggilan = _penghitung(AP.SinyalNav(total=3))
    assert C.ambil(hitung, jam=jam).total == 3
    jam.sekarang += C.TTL_DETIK - 0.1
    assert C.ambil(hitung, jam=jam).total == 3
    assert len(panggilan) == 1
    jam.sekarang += 0.2  # melewati TTL
    C.ambil(hitung, jam=jam)
    assert len(panggilan) == 2


def test_galat_none_tidak_disimpan_dan_dicoba_lagi():
    jam = _Jam()
    hasil = iter([None, AP.SinyalNav(total=1)])
    panggilan = []

    def hitung():
        panggilan.append(1)
        return next(hasil)
    assert C.ambil(hitung, jam=jam) is None
    assert C.ambil(hitung, jam=jam).total == 1  # tanpa menunggu TTL
    assert len(panggilan) == 2


def test_kosongkan_memaksa_hitung_ulang():
    jam = _Jam()
    hitung, panggilan = _penghitung(AP.SinyalNav(total=1))
    C.ambil(hitung, jam=jam)
    C.kosongkan()
    C.ambil(hitung, jam=jam)
    assert len(panggilan) == 2


def test_hasil_yang_dihitung_sebelum_kosongkan_tidak_tersimpan_sesudahnya():
    jam = _Jam()
    lama = AP.SinyalNav(total=1)

    def hitung_lalu_admin_bertindak():
        C.kosongkan()  # POST admin masuk saat hitungan berjalan
        return lama
    assert C.ambil(hitung_lalu_admin_bertindak, jam=jam) is lama
    baru, panggilan = _penghitung(AP.SinyalNav(total=2))
    assert C.ambil(baru, jam=jam).total == 2 and len(panggilan) == 1


def test_simpan_dengan_generasi_basi_ditolak_dan_none_diabaikan():
    jam = _Jam()
    awal = C.generasi()
    C.kosongkan()
    C.simpan(AP.SinyalNav(total=9), awal, jam=jam)
    C.simpan(None, C.generasi(), jam=jam)
    hitung, panggilan = _penghitung(AP.SinyalNav(total=1))
    assert C.ambil(hitung, jam=jam).total == 1 and len(panggilan) == 1


def test_ringkasan_mengisi_cache_dengan_angka_segarnya():
    jam = _Jam()
    C.simpan(AP.SinyalNav(total=5), C.generasi(), jam=jam)
    hitung, panggilan = _penghitung(AP.SinyalNav(total=99))
    assert C.ambil(hitung, jam=jam).total == 5 and panggilan == []


def test_thread_bersamaan_tidak_merusak_cache():
    hitung, panggilan = _penghitung(AP.SinyalNav(total=4))
    hasil = []

    def kerja():
        for _ in range(200):
            hasil.append(C.ambil(hitung).total)
            C.kosongkan() if len(hasil) % 50 == 0 else None
    utas = [threading.Thread(target=kerja) for _ in range(8)]
    for t in utas:
        t.start()
    for t in utas:
        t.join()
    assert set(hasil) == {4} and len(hasil) == 1600


def test_sinyal_nav_admin_http_memakai_cache(monkeypatch):
    hitung, panggilan = _penghitung(AP.SinyalNav(total=2))
    monkeypatch.setattr(admin_http, "_hitung_sinyal_nav", hitung)
    assert admin_http.sinyal_nav().total == 2 and admin_http.sinyal_nav().total == 2
    assert len(panggilan) == 1


@pytest.mark.parametrize("jalur,ditangani,harap_kosong", [
    ("/admin/akun", True, True),
    ("/admin/akun", False, True),   # dikosongkan di awal untuk jalur /admin
    ("/murid", False, False),
])
def test_tangani_post_mengosongkan_cache(monkeypatch, jalur, ditangani, harap_kosong):
    jam = _Jam()
    C.simpan(AP.SinyalNav(total=1), C.generasi(), jam=jam)
    monkeypatch.setattr(admin_http, "_tangani_post_admin", lambda p, j: ditangani)
    assert admin_http.tangani_post(object(), jalur) is ditangani
    hitung, panggilan = _penghitung(AP.SinyalNav(total=7))
    C.ambil(hitung, jam=jam)
    assert (len(panggilan) == 1) is harap_kosong


def test_tangani_post_mengosongkan_cache_walau_penangan_galat(monkeypatch):
    jam = _Jam()
    C.simpan(AP.SinyalNav(total=1), C.generasi(), jam=jam)

    def galat(p, j):
        raise RuntimeError("x")
    monkeypatch.setattr(admin_http, "_tangani_post_admin", galat)
    with pytest.raises(RuntimeError):
        admin_http.tangani_post(object(), "/murid")  # jalur non-admin tetap dikosongkan saat galat
    hitung, panggilan = _penghitung(AP.SinyalNav(total=7))
    C.ambil(hitung, jam=jam)
    assert len(panggilan) == 1
