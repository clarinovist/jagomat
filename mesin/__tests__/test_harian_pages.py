"""Render Latihan Harian: escape, struktur tanpa kebocoran, kartu beranda dan blok orang tua (murni, tanpa DB/HTTP)."""
import re

import pytest

import harian_langganan_dasar as paket_dasar
import harian_latihan_store as hs
import harian_pages as P
import visual_contract

PENYAJIAN = visual_contract.buat_penyajian(
    template_id="tambah_dasar", level="P1", parameter={"a": 1}, teks_soal="Berapa 1 + 1? <b>tebal</b>")
SOAL = hs.SoalAnak(3, 10, PENYAJIAN, ("2", "<script>x</script>", "3/4", "4"))
UMPAN = hs.UmpanBalik(1, False, 0, "Satu tambah satu <i>dua</i>.\nBaris kedua 1/2")


def _teks(isi: bytes) -> str:
    mentah = re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script)\b.*?</\1>", " ", isi.decode(), flags=re.S))
    return " ".join(mentah.split())


def _badan(isi) -> str:
    """HTML tanpa blok <style> (nama kelas di CSS tidak ikut terhitung)."""
    teks = isi.decode() if isinstance(isi, bytes) else isi
    return re.sub(r"<style\b.*?</style>", "", teks, flags=re.S)


def _jumlah_tautan_ortu(isi) -> int:
    return _badan(isi).count('href="/murid/orang-tua"')


def _jumlah_maskot(isi) -> int:
    return _badan(isi).count('class="ceria-maskot"')


def test_soal_belum_dijawab_memuat_empat_radio_dan_tanpa_umpan():
    isi = _badan(P.halaman_soal(7, "t1", SOAL, None, 2))

    assert isi.count('type="radio"') == 4 and 'name="pilihan"' in isi and 'name="no" value="3"' in isi
    assert "Cara mengerjakannya" not in isi and "Periksa jawabanku" in isi and "ceria-banner" not in isi
    assert "Jawaban benar" not in isi and "Jawabanmu" not in isi and _jumlah_maskot(isi) == 0
    assert 'action="/murid/latihan-harian/sesi/7/jawab"' in isi


def test_teks_soal_dan_opsi_di_escape():
    isi = P.halaman_soal(7, "t1", SOAL, None, 2).decode()

    assert "<script>x</script>" not in isi and "&lt;script&gt;x&lt;/script&gt;" in isi
    assert "<b>tebal</b>" not in isi


def test_pecahan_pada_opsi_dirender_bertumpuk():
    assert 'class="pecahan"' in P.halaman_soal(7, "t1", SOAL, None, 2).decode()


def test_umpan_menampilkan_tanda_teks_pembahasan_ter_escape_dan_tautan_lanjut():
    isi = P.halaman_soal(7, "t1", SOAL, UMPAN, 3).decode()

    assert "Belum tepat" in isi and "Cara mengerjakannya" in isi and "Jawaban benar" in isi and "Jawabanmu" in isi
    assert "<i>dua</i>" not in isi and "&lt;i&gt;dua&lt;/i&gt;" in isi and "<br>" in isi
    assert 'type="radio"' not in isi and 'href="/murid/latihan-harian/sesi/7?no=4"' in isi


def test_soal_terakhir_tautan_ke_ringkasan():
    terakhir = hs.SoalAnak(10, 10, PENYAJIAN, SOAL.opsi)

    isi = P.halaman_soal(7, "t1", terakhir, hs.UmpanBalik(0, True, 0, "cara"), 10).decode()

    assert 'href="/murid/latihan-harian/sesi/7/ringkasan"' in isi and "Betul!" in isi


def test_status_benar_salah_selalu_disertai_teks_bukan_warna_saja():
    isi = _badan(P.halaman_soal(7, "t1", SOAL, UMPAN, 3))

    assert re.search(r'class="hr-pilih benar".*?Jawaban benar', isi, re.S)
    assert re.search(r'class="hr-pilih salah".*?Jawabanmu', isi, re.S)


def test_ringkasan_tanpa_peringkat():
    teks = _teks(P.halaman_ringkasan(hs.RingkasanSesi("t3", 10, 8))).lower()

    assert "8 dari 10 benar" in teks and "peringkat" not in teks and "persentil" not in teks
    assert "sesi ini selesai" in teks and "sesi selesai" in teks and "hari ini" not in teks and "dibanding" not in teks


def test_ringkasan_hero_satu_maskot_skor_besar_dan_sepuluh_titik():
    isi = _badan(P.halaman_ringkasan(hs.RingkasanSesi("t3", 10, 8)))

    assert 'class="ceria-hero"' in isi and 'class="ceria-konfeti"' in isi and _jumlah_maskot(isi) == 1
    assert '<p class="ceria-skor"><b>8</b> dari 10 benar</p>' in isi
    bintang = re.search(r'<div class="ceria-bintang"[^>]*>(.*?)</div>', isi, re.S).group(1)
    assert bintang.count("<i ") == 10 and bintang.count('<i class="ceria-isi"></i>') == 8
    assert bintang.count('<i class=""></i>') == 2
    assert "Latihan lagi" in isi and "<h1" in isi and "<script" not in isi


def test_ringkasan_ajakan_ortu_hanya_bila_diminta_dan_satu_tautan():
    ringkas = hs.RingkasanSesi("t3", 10, 8)

    tanpa = _badan(P.halaman_ringkasan(ringkas))
    dengan = _badan(P.halaman_ringkasan(ringkas, tampil_ajakan_ortu=True))

    assert _jumlah_tautan_ortu(tanpa) == 0 and "ceria-ortu" not in tanpa
    assert _jumlah_tautan_ortu(dengan) == 1 and "ceria-ortu" in dengan
    assert _jumlah_maskot(dengan) == 1


def _sesi(terjawab=2):
    return hs.SesiRingkas(4, "t2", "berjalan", 10, terjawab, 100, None)


def test_beranda_tiga_keadaan():
    pilih = P.halaman_beranda(None, False, "t4", "t2").decode()
    habis = P.halaman_beranda(None, True, "t4", "t2").decode()
    jalan = P.halaman_beranda(_sesi(), False, "t4", None).decode()

    assert pilih.count('name="tingkat"') == 8 and 'class="hr-saran">Saran<' in pilih and "Terakhir<" in pilih
    assert P.COPY_HABIS in habis and 'name="tingkat"' not in habis and _jumlah_tautan_ortu(habis) == 1
    assert "Latihanmu masih berjalan" in jalan and "sesi/4?no=3" in jalan and 'name="tingkat"' not in jalan


def test_pilih_kelas_maskot_menyebut_kelas_saran_dan_satu_maskot():
    pilih = _badan(P.halaman_beranda(None, False, "t4", "t2"))

    assert _jumlah_maskot(pilih) == 1 and "maskot-semangat-v4-96.png" in pilih
    assert "Mulai dari <b>Kelas 4</b> ya, sesuai kelasmu." in pilih
    assert "Boleh pilih kelas lain untuk mengulang atau menantang diri." in pilih
    assert pilih.count('class="ceria-stiker ceria-miring-kanan">Pengayaan<') == 2
    assert pilih.count("hr-tingkat saran") == 1 and "Tingkat" not in _teks(pilih.encode())


@pytest.mark.parametrize("saran", [None, "t9", "osn-lanjut_tak_ada"])
def test_pilih_kelas_tanpa_saran_memakai_kalimat_netral(saran):
    pilih = _badan(P.halaman_beranda(None, False, saran, None))

    assert "Pilih kelasmu ya." in pilih and "Mulai dari" not in pilih and "hr-tingkat saran" not in pilih
    assert _jumlah_maskot(pilih) == 1


def test_pilih_kelas_tombol_tetap_form_post_per_kelas():
    pilih = _badan(P.halaman_beranda(None, False, "t4", None))

    assert pilih.count('<form method="post" action="/murid/latihan-harian/mulai">') == 8
    assert 'name="tingkat" value="t4"' in pilih and 'name="tingkat" value="osn-pemula"' in pilih


def test_jatah_habis_banner_hangat_dan_satu_kartu_ajakan_ortu():
    habis = _badan(P.halaman_beranda(None, True, None, None))

    assert "Hebat, latihan hari ini selesai!" in habis and "Besok kamu bisa latihan lagi." in habis
    assert P.COPY_HABIS in _teks(habis.encode())
    assert _jumlah_tautan_ortu(habis) == 1 and _jumlah_maskot(habis) == 1 and "Untuk Ayah/Bunda · lihat paket" in habis


def test_ajakan_harga_dihitung_dari_paket_bukan_hardcode(monkeypatch):
    paket = paket_dasar.PAKET[paket_dasar.PAKET_BULANAN]
    baru = paket_dasar.Paket(paket.kode, paket.nama, 41000, 1)
    monkeypatch.setattr(P.paket_dasar, "PAKET", {paket.kode: baru})

    habis = _badan(P.halaman_beranda(None, True, None, None))

    assert "Rp41.000/bulan" in habis and "mulai" not in habis and "Rp39.000" not in habis


def test_teks_persen_tepat_strip_bila_belum_ada_soal_dan_persen_bila_ada():
    kosong = hs.RingkasanHarian(None, (), 0, 0)
    ada = hs.RingkasanHarian("t5", (), 12, 9)

    assert P.teks_persen_tepat(kosong) == "-"
    assert P.teks_persen_tepat(ada) == "75%"


def test_ajakan_harga_bawaan_sesuai_paket_bulanan():
    paket = paket_dasar.PAKET[paket_dasar.PAKET_BULANAN]

    assert P.teks_harga_ortu() == "Rp%s/bulan" % format(paket.rupiah // paket.bulan, ",").replace(",", ".")


def test_jatah_habis_tanpa_halaman_ortu_menyembunyikan_ajakan():
    habis = _badan(P.halaman_beranda(None, True, None, None, ada_ortu=False))

    assert P.COPY_HABIS in habis and _jumlah_tautan_ortu(habis) == 0 and "ceria-ortu" not in habis
    assert _jumlah_maskot(habis) == 1 and "maskot-istirahat-v4-96.png" in habis


@pytest.mark.parametrize("benar,beruntun,pose,kata", [
    (True, 1, "merayakan-v3", "Hebat!"), (True, 2, "merayakan-v3", "Hebat!"),
    (True, 3, "terkejut-v4", "Sudah 3 betul berturut-turut!"), (True, 5, "terkejut-v4", "Sudah 5 betul berturut-turut!"),
    (False, 1, "memeriksa-v4", "Yuk lihat caranya."), (False, 2, "menyemangati-v4", "Terus semangat"),
])
def test_pose_umpan_balik_mengikuti_jawaban_beruntun(benar, beruntun, pose, kata):
    umpan = hs.UmpanBalik(1, benar, 1 if benar else 0, "cara")
    html = _badan(P.halaman_soal(7, "t1", SOAL, umpan, 3, beruntun))
    assert "maskot-%s-96.png" % pose in html and kata in html and _jumlah_maskot(html) == 1


@pytest.mark.parametrize("benar,pose,konfeti", [(10, "merayakan-v3", True), (4, "merayakan-v3", True),
                                                (3, "sedih-v4", False), (0, "sedih-v4", False)])
def test_ringkasan_pose_sedih_hangat_tanpa_konfeti_hanya_untuk_skor_rendah(benar, pose, konfeti):
    html = _badan(P.halaman_ringkasan(hs.RingkasanSesi("t3", 10, benar)))

    assert "maskot-%s-96.png" % pose in html and _jumlah_maskot(html) == 1
    assert ('class="ceria-konfeti"' in html) is konfeti
    assert ("Kamu sudah mencoba" in html) is (not konfeti)


def test_umpan_betul_hijau_dan_belum_tepat_hangat_berlabel_teks():
    betul = _badan(P.halaman_soal(7, "t1", SOAL, hs.UmpanBalik(1, True, 1, "cara"), 3))
    belum = _badan(P.halaman_soal(7, "t1", SOAL, hs.UmpanBalik(1, False, 0, "cara"), 3))

    assert "ceria-betul" in betul and "Betul!" in betul and "Jawabanmu B tepat. Hebat!" in betul
    assert "ceria-hampir" in belum and "Belum tepat, tidak apa-apa." in belum and "Yuk lihat caranya." in belum
    assert "ceria-hampir" not in betul and "ceria-betul" not in belum
    assert _jumlah_maskot(betul) == 1 and _jumlah_maskot(belum) == 1
    assert "maskot-merayakan-v3-96.png" in betul and "maskot-memeriksa-v4-96.png" in belum
    assert "Jawabanmu, benar" in betul and "Jawabanmu" in belum and "Jawaban benar" in belum
    assert "Cara mengerjakannya" in belum and _jumlah_tautan_ortu(belum) == 0


def test_layar_soal_info_kelas_progres_dan_tombol_periksa():
    isi = _badan(P.halaman_soal(7, "t4", SOAL, None, 2))

    assert "Kelas 4 · Soal 3 dari 10" in isi and "hr-progres" not in isi
    assert 'aria-label="2 dari 10 soal sudah dijawab"' in isi
    assert '<span class="ceria-kini"></span>' in isi and isi.count('class="ceria-sudah"') == 2
    assert "Tingkat" not in _teks(isi.encode()) and "Periksa jawabanku" in isi


def test_kartu_beranda_tujuh_titik_dan_tombol_sesuai_keadaan():
    pekan = tuple(("2027-01-%02d" % (11 + i), i == 4) for i in range(7))

    baru = P.kartu_beranda(None, None, False, pekan)
    jalan = P.kartu_beranda(_sesi(), "t2", False, pekan)
    habis = P.kartu_beranda(None, "t2", True, pekan)

    assert baru.count("<li class=\"ceria-") == 7 and "Pilih kelasmu" in baru and "Mulai latihan" in baru
    assert baru.count('class="ceria-isi"') == 1 and baru.count('class="ceria-kosong"') == 6
    assert "ceria-titik ceria-krem" in baru and 'class="hr-tombol"' in baru
    assert "Kelas 2" in jalan and "Lanjutkan" in jalan and "sesi/4?no=3" in jalan
    assert "Lihat latihan" in habis and "Jatah latihan gratis hari ini sudah dipakai" in habis
    for kartu in (baru, jalan, habis):
        assert _jumlah_tautan_ortu(kartu) == 0 and _jumlah_maskot(kartu) == 0 and "<script" not in kartu


def test_blok_orang_tua_angka_dan_kosong():
    hari = tuple(("2027-01-%02d" % (9 + i), i in (1, 5)) for i in range(7))
    isi = _teks(P.blok_orang_tua(hs.RingkasanHarian("t5", hari, 12, 9)).encode())

    assert "Kelas 5" in isi and "2</b> dari 7" in P.blok_orang_tua(hs.RingkasanHarian("t5", hari, 12, 9)) \
        and "12" in isi and "75%" in isi
    kosong = _teks(P.blok_orang_tua(hs.RingkasanHarian(None, hari, 0, 0)).encode())
    assert "Belum ada Latihan Harian" in kosong and "%" not in kosong


def test_blok_orang_tua_tidak_memuat_kata_terlarang_halaman_orang_tua():
    hari = tuple(("2027-01-%02d" % (9 + i), False) for i in range(7))

    teks = _teks(P.blok_orang_tua(hs.RingkasanHarian("t5", hari, 3, 2)).encode()).lower()

    for kata in ("kunci", "malrule", "diagnos", "pembahasan", "jawaban benar", "tel:", "wa.me"):
        assert kata not in teks


def test_tidak_ada_warna_hex_di_modul_harian():
    from pathlib import Path
    akar = Path(__file__).resolve().parent.parent
    for nama in ("harian_style.py", "harian_pages.py", "harian_http.py"):
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", (akar / nama).read_text()), nama
