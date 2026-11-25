"""Halaman Ayah/Bunda gaya ceria (F3): urutan blok, hero, hasil cek, Latihan Harian, PIN dilipat (murni render)."""
import re

import pytest

import harian_langganan_ringkas as ringkas
import harian_latihan_store as hs
import kelas_masa as km
import orang_tua_data
import orang_tua_pages as P
import pesanan_pages
from teacher_style import SKRIP_MATA_SANDI

HARI = tuple(("2027-01-%02d" % (9 + i), i in (1, 5)) for i in range(7))  # 9 Jan 2027 = Sabtu
CEK = {"status": "selesai", "skor": 60, "kategori": "Perlu penguatan",
       "ringkasan": {"kuat": ["Penjumlahan"], "perlu": []}, "jumlah_soal": 15}
LAPORAN = {"nama": "Anak", "isi": {"topik": ["Pecahan"], "langkah": "Latih."}, "catatan": "Catatan sintetis",
           "guru": "Bu Guru", "periode": ("2026-11-01", "2026-11-15"), "diterbitkan": "2026-11-20 10:00:00"}
LANGGANAN_SEGERA = ringkas.Ringkasan("langganan", "2026-12-23T03:00:00", 2, None)


def _data(nama="Anak Sintetis", hasil=None, laporan=None, pesanan=None, langganan=None, harian=None):
    return orang_tua_data.DataOrangTua(nama, CEK if hasil is None else hasil, laporan, pesanan, langganan, harian)


def _isi(data, ada_pin=False, kabar="", galat="") -> str:
    return P.halaman_isi(data, ada_pin, kabar, galat).decode()


def _badan(html: str) -> str:
    return html.split("</head>", 1)[1]


def _dari_seksi(html: str, id_: str) -> str:
    """Isi mulai dari tag `<section` pembuka kartu ber-id `id_` (kelas ada sebelum id) sampai akhir dokumen."""
    return html[html.rfind("<section", 0, html.index('id="%s"' % id_)):]


def _penuh() -> str:
    harian = hs.RingkasanHarian("t5", HARI, 12, 9)
    data = _data(laporan=LAPORAN, pesanan=pesanan_pages.STATUS_BELUM_BAYAR, langganan=LANGGANAN_SEGERA, harian=harian)
    return _badan(_isi(data, ada_pin=True))


def test_urutan_blok_halaman():
    html = _penuh()
    penanda = ['id="ortu-langganan-banner"', 'class="ceria-hero"', 'id="ortu-hasil-cek"', 'id="ortu-pesanan"',
               'id="ortu-harian"', 'id="ortu-langganan"', 'id="ortu-laporan"', 'id="ortu-pin"']
    posisi = [html.index(p) for p in penanda]
    assert posisi == sorted(posisi) and len(set(posisi)) == len(penanda)


def test_pesan_umpan_balik_pin_di_atas_semua_blok():
    html = _badan(_isi(_data(), ada_pin=True, kabar="pin-dipasang"))
    assert html.index("PIN sudah disimpan.") < html.index('class="ceria-hero"')


def test_hero_tiga_angka_hanya_saat_latihan_harian_aktif():
    tanpa = _badan(_isi(_data(harian=None)))
    assert "ortu-tiga-st" not in tanpa and "hari latihan" not in tanpa
    dengan = _badan(_isi(_data(harian=hs.RingkasanHarian("t5", HARI, 12, 9))))
    assert "<b>2/7</b>hari latihan" in dengan and "<b>12</b>soal dikerjakan" in dengan and "<b>75%</b>tepat" in dengan


def test_hero_persen_tepat_strip_bila_belum_ada_soal():
    html = _badan(_isi(_data(harian=hs.RingkasanHarian(None, HARI, 0, 0))))
    assert "<b>-</b>tepat" in html and "<b>0</b>soal dikerjakan" in html


def test_hero_menyebut_nama_anak_ter_escape_dan_tanpa_nama_kalimat_umum():
    assert "Ringkasan belajar &lt;b&gt;X&lt;/b&gt;" in _isi(_data(nama="<b>X</b>"))
    assert "Ringkasan belajar anak<" in _isi(_data(nama=""))
    html = _badan(_isi(_data()))
    assert html.count("<h1") == 1 and 'id="judul-ortu"' in html and "Halo, Ayah/Bunda" in html


def test_hero_tidak_mengarang_kelas_anak():
    html = _badan(_isi(_data(harian=hs.RingkasanHarian("t5", HARI, 12, 9))))
    hero = html[html.index('class="ceria-hero"'):html.index('id="ortu-hasil-cek"')]
    assert "Kelas" not in hero


# --- hasil cek ---------------------------------------------------------------------------------

def test_hasil_cek_selesai_memuat_donat_dan_teks_lama_tanpa_batang_karangan():
    html = _badan(_isi(_data()))
    kartu = _dari_seksi(html, "ortu-hasil-cek")[:3000]
    assert "funnel-cincin-svg-st" in kartu and "<svg" in kartu and 'stroke-dasharray="60 100"' in kartu
    assert "Gambaran awal" in kartu and "9 dari 15 soal benar" in kartu and "Perlu penguatan" in kartu
    assert "ortu-hasil-st" in kartu
    for karangan in ("batang", "progress", "<meter", "role=\"progressbar\""):
        assert karangan not in html


@pytest.mark.parametrize("status,kalimat", [("belum_mulai", "Cek kemampuan belum dikerjakan."),
                                            ("belum_selesai", "Cek kemampuan belum selesai dikerjakan.")])
def test_hasil_cek_belum_selesai_tanpa_donat(status, kalimat):
    html = _badan(_isi(_data(hasil={"status": status, "skor": None, "kategori": None, "ringkasan": {}, "jumlah_soal": 15})))
    assert kalimat in html and "funnel-cincin" not in html


# --- Latihan Harian ----------------------------------------------------------------------------

def test_latihan_harian_memakai_titik_hari_krem_dan_gaya_lama_hilang():
    html = _badan(_isi(_data(harian=hs.RingkasanHarian("t5", HARI, 12, 9))))
    kartu = html[html.index('id="ortu-harian"'):]
    assert "ceria-titik ceria-krem" in kartu and "Terakhir berlatih: <b>Kelas 5</b>" in kartu
    assert kartu.count('class="ceria-isi"') == 2 and kartu.count('class="ceria-kosong"') == 5
    assert "hr-hari" not in html and "hr-titik" not in html and "<style" not in html


def test_latihan_harian_mati_tanpa_kartu():
    assert 'id="ortu-harian"' not in _isi(_data(harian=None))


# --- laporan Guru dan pesanan ------------------------------------------------------------------

def test_laporan_kosong_kartu_sabar_dengan_satu_kalimat_dan_satu_maskot():
    html = _badan(_isi(_data(laporan=None)))
    kartu = _dari_seksi(html, "ortu-laporan")
    assert "Belum ada laporan dari Guru." in kartu and "ortu-kosong-st" in kartu
    assert html.count('class="ceria-maskot"') == 1


def test_laporan_terisi_tanpa_maskot_dan_halaman_penuh_paling_banyak_satu_maskot():
    assert _penuh().count('class="ceria-maskot"') == 0


def test_pesanan_status_lencana_dan_satu_tombol():
    html = _badan(_isi(_data(pesanan=pesanan_pages.STATUS_BELUM_BAYAR)))
    kartu = html[html.index('id="ortu-pesanan"'):]
    kartu = kartu[:kartu.index("</section>")]
    assert "ceria-lencana-kuning" in kartu and "Menunggu pembayaran" in kartu
    assert kartu.count("<a ") == 1 and "Lanjutkan pembayaran atau lihat statusnya" in kartu


def test_pesanan_sudah_dibayar_tanpa_tombol():
    kartu = _badan(_isi(_data(pesanan=pesanan_pages.STATUS_SUDAH_DIBAYAR)))
    kartu = kartu[kartu.index('id="ortu-pesanan"'):kartu.index("</section>", kartu.index('id="ortu-pesanan"'))]
    assert "ceria-lencana-hijau" in kartu and "<a " not in kartu


# --- PIN dalam <details> -----------------------------------------------------------------------

def _pin(html: str) -> str:
    awal = html.index('<details class="ortu-pin-st"')
    return html[awal:html.index("</details>", awal) + len("</details>")]


@pytest.mark.parametrize("ada_pin,status", [(True, "Sudah dipasang"), (False, "Belum dipasang")])
def test_pin_dalam_details_tertutup_dengan_status_teks(ada_pin, status):
    kartu = _pin(_badan(_isi(_data(), ada_pin=ada_pin)))
    assert kartu.startswith('<details class="ortu-pin-st" id="ortu-pin"><summary>') and " open" not in kartu[:60]
    assert "PIN halaman Ayah/Bunda" in kartu and status in kartu.split("</summary>")[0]


def test_pin_form_atur_dan_hapus_di_dalam_details_tak_berubah():
    kartu = _pin(_badan(_isi(_data(), ada_pin=True)))
    assert 'action="/murid/orang-tua/pin/atur"' in kartu and 'action="/murid/orang-tua/pin/hapus"' in kartu
    assert 'name="pin"' in kartu and 'name="pin_ulang"' in kartu and 'name="konfirmasi" value="1" required' in kartu
    assert ">Ganti PIN<" in kartu and ">Hapus PIN<" in kartu and "PIN sudah dipasang. Halaman ini tertutup" in kartu
    sebelum = _pin(_badan(_isi(_data(), ada_pin=False)))
    assert ">Pasang PIN<" in sebelum and "pin/hapus" not in sebelum and "Belum ada PIN" in sebelum


@pytest.mark.parametrize("kabar,galat", [("pin-dipasang", ""), ("pin-dihapus", ""), ("", P.COPY_PIN_TIDAK_SAH),
                                         ("", P.COPY_KONFIRMASI_WAJIB)])
def test_pin_terbuka_otomatis_saat_ada_pesan_pin(kabar, galat):
    kartu = _pin(_badan(_isi(_data(), ada_pin=True, kabar=kabar, galat=galat)))
    assert kartu.startswith('<details class="ortu-pin-st" id="ortu-pin" open>')


def test_kode_kabar_tak_dikenal_tidak_membuka_pin():
    assert " open" not in _pin(_badan(_isi(_data(), ada_pin=True, kabar="acak")))[:60]


def test_catatan_jujur_pin_dan_kalimat_tim_tetap_ada():
    html = _badan(_isi(_data()))
    assert P.COPY_PIN_CATATAN in html and P.COPY_KALIMAT in html and "PIN ini penutup halaman, bukan pengaman data." in html


# --- skrip, kebocoran, tirai ------------------------------------------------------------------

def test_hanya_skrip_mata_sandi_dan_tanpa_skrip_baru():
    html = _isi(_data(laporan=LAPORAN, langganan=LANGGANAN_SEGERA, harian=hs.RingkasanHarian("t5", HARI, 12, 9)),
                ada_pin=True)
    skrip = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S)
    assert skrip == [SKRIP_MATA_SANDI] and html.count("<script") == 1


def test_halaman_tirai_pin_tidak_ikut_gaya_ceria_dan_tanpa_data_anak():
    penuh = _isi(_data(nama="Anak Sintetis", laporan=LAPORAN), ada_pin=True)
    html = P.halaman_pin(P.COPY_PIN_TIDAK_SAH).decode()
    assert "Anak Sintetis" in penuh and "Catatan sintetis" in penuh  # kontrol positif: halaman penuh memuat data
    assert "ceria-hero" not in html and 'id="ortu-pin-masuk"' in html
    assert "Anak Sintetis" not in html and "Catatan sintetis" not in html and "Bu Guru" not in html


def test_halaman_pin_memakai_satu_maskot_gembok_tanpa_gaya_ceria():
    html = P.halaman_pin().decode()
    assert html.count("maskot-gembok-v4-96.png") == 1 and html.count("/aset/maskot-") == 1
    assert 'class="ortu-pin-maskot-st"' in html and 'class="ceria-maskot"' not in html


def test_tanpa_kontak_diagnosis_atau_kunci_di_isi_halaman():
    teks = _penuh().lower()
    for terlarang in ("wa.me", "tel:", "mailto:", "malrule", "diagnos", "kode_final", "kunci jawaban", "pembahasan"):
        assert terlarang not in teks, terlarang
    assert "6281" not in teks


def test_css_ceria_dimuat_di_isi_halaman_dan_modul_tanpa_hex():
    from pathlib import Path
    assert ".ceria-hero" in _isi(_data()) and ".ceria-hero" not in P.halaman_pin().decode()
    for nama in ("orang_tua_style.py", "orang_tua_pages.py", "harian_langganan_style.py", "harian_langganan_pages.py"):
        sumber = (Path(P.__file__).parent / nama).read_text()
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber.replace("&#", "")), nama


# --- kartu Paket Belajar (hanya bila pemanggil menyalakan; sakelar PAKET_BELAJAR) -------------------

def _isi_paket(data, tautan):
    return _badan(P.halaman_isi(data, False, "", "", tautan_paket=tautan).decode())


def test_kartu_paket_belajar_hanya_saat_diminta_dan_byte_sama_bila_mati():
    harian = hs.RingkasanHarian("t5", HARI, 12, 9)
    data = _data(laporan=LAPORAN, langganan=LANGGANAN_SEGERA, harian=harian)
    assert _isi_paket(data, False) == _badan(_isi(data)) and 'id="ortu-paket"' not in _isi_paket(data, False)
    assert 'id="ortu-paket"' in _isi_paket(data, True)


def test_kartu_paket_belajar_setelah_langganan_sebelum_laporan_guru():
    harian = hs.RingkasanHarian("t5", HARI, 12, 9)
    html = _isi_paket(_data(laporan=LAPORAN, langganan=LANGGANAN_SEGERA, harian=harian), True)
    posisi = [html.index(p) for p in ('id="ortu-harian"', 'id="ortu-langganan"', 'id="ortu-paket"', 'id="ortu-laporan"')]
    assert posisi == sorted(posisi)
    kartu = html[html.index('id="ortu-paket"'):]
    kartu = kartu[:kartu.index("</section>")]
    assert 'href="/murid/paket"' in kartu and "Belajar bersama Guru" in kartu
    for klaim in ("nilai naik", "pasti", "dijamin", "Rp"):
        assert klaim not in kartu


# --- banner perpanjang paket belajar (hanya bila `tautan_paket`; isi dari `masa_paket`) ---------------

def _isi_masa(data, tautan, masa):
    return _badan(P.halaman_isi(data, False, "", "", tautan_paket=tautan, masa_paket=masa).decode())


def test_banner_paket_hanya_saat_tautan_dan_setelah_banner_langganan():
    data = _data(langganan=LANGGANAN_SEGERA)
    masa = (km.MasaPaket("mini", "Mini Class", "2026-12-20T09:30:00", 2, km.STATUS_SEGERA),)
    mati = _isi_masa(data, False, masa)
    assert mati == _badan(_isi(data)) and 'id="ortu-paket-banner"' not in mati
    html = _isi_masa(data, True, masa)
    posisi = [html.index(p) for p in ('id="ortu-langganan-banner"', 'id="ortu-paket-banner"', 'id="judul-ortu"')]
    assert posisi == sorted(posisi)


def test_banner_paket_tanpa_masa_tidak_menambah_banner():
    data = _data(langganan=LANGGANAN_SEGERA)
    assert 'id="ortu-paket-banner"' not in _isi_masa(data, True, ())
