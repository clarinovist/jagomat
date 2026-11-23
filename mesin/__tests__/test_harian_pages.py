"""Render Latihan Harian: escape, struktur tanpa kebocoran, kartu beranda dan blok orang tua (murni, tanpa DB/HTTP)."""
import re

import harian_latihan_store as hs
import harian_pages as P
import visual_contract

PENYAJIAN = visual_contract.buat_penyajian(
    template_id="tambah_dasar", level="P1", parameter={"a": 1}, teks_soal="Berapa 1 + 1? <b>tebal</b>")
SOAL = hs.SoalAnak(3, 10, PENYAJIAN, ("2", "<script>x</script>", "3/4", "4"))
UMPAN = hs.UmpanBalik(1, False, 0, "Satu tambah satu <i>dua</i>.\nBaris kedua 1/2")


def _teks(isi: bytes) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script)\b.*?</\1>", " ", isi.decode(), flags=re.S))


def test_soal_belum_dijawab_memuat_empat_radio_dan_tanpa_umpan():
    isi = P.halaman_soal(7, "t1", SOAL, None, 2).decode()

    assert isi.count('type="radio"') == 4 and 'name="pilihan"' in isi and 'name="no" value="3"' in isi
    assert "Caranya" not in isi and "Periksa jawabanku" in isi
    assert 'action="/murid/latihan-harian/sesi/7/jawab"' in isi


def test_teks_soal_dan_opsi_di_escape():
    isi = P.halaman_soal(7, "t1", SOAL, None, 2).decode()

    assert "<script>x</script>" not in isi and "&lt;script&gt;x&lt;/script&gt;" in isi
    assert "<b>tebal</b>" not in isi


def test_pecahan_pada_opsi_dirender_bertumpuk():
    assert 'class="pecahan"' in P.halaman_soal(7, "t1", SOAL, None, 2).decode()


def test_umpan_menampilkan_tanda_teks_pembahasan_ter_escape_dan_tautan_lanjut():
    isi = P.halaman_soal(7, "t1", SOAL, UMPAN, 3).decode()

    assert "Belum tepat" in isi and "Caranya" in isi and "Jawaban yang benar" in isi and "Jawabanmu" in isi
    assert "<i>dua</i>" not in isi and "&lt;i&gt;dua&lt;/i&gt;" in isi and "<br>" in isi
    assert 'type="radio"' not in isi and 'href="/murid/latihan-harian/sesi/7?no=4"' in isi


def test_soal_terakhir_tautan_ke_ringkasan():
    terakhir = hs.SoalAnak(10, 10, PENYAJIAN, SOAL.opsi)

    isi = P.halaman_soal(7, "t1", terakhir, hs.UmpanBalik(0, True, 0, "cara"), 10).decode()

    assert 'href="/murid/latihan-harian/sesi/7/ringkasan"' in isi and "Benar! Hebat." in isi


def test_status_benar_salah_selalu_disertai_teks_bukan_warna_saja():
    isi = P.halaman_soal(7, "t1", SOAL, UMPAN, 3).decode()

    assert re.search(r'class="hr-pilih benar".*?Jawaban yang benar', isi, re.S)
    assert re.search(r'class="hr-pilih salah".*?Jawabanmu', isi, re.S)


def test_ringkasan_tanpa_peringkat():
    teks = _teks(P.halaman_ringkasan(hs.RingkasanSesi("t3", 10, 8))).lower()

    assert "8 dari 10" in teks and "peringkat" not in teks and "persentil" not in teks


def _sesi(terjawab=2):
    return hs.SesiRingkas(4, "t2", "berjalan", 10, terjawab, 100, None)


def test_beranda_tiga_keadaan():
    pilih = P.halaman_beranda(None, False, "t4", "t2").decode()
    habis = P.halaman_beranda(None, True, "t4", "t2").decode()
    jalan = P.halaman_beranda(_sesi(), False, "t4", None).decode()

    assert pilih.count('name="tingkat"') == 8 and "Disarankan untukmu" in pilih and "Terakhir kamu pilih" in pilih
    assert P.COPY_HABIS in habis and 'name="tingkat"' not in habis and 'href="/murid/orang-tua"' in habis
    assert "Latihanmu masih berjalan" in jalan and "sesi/4?no=3" in jalan and 'name="tingkat"' not in jalan


def test_kartu_beranda_tujuh_titik_dan_tombol_sesuai_keadaan():
    pekan = tuple(("2027-01-%02d" % (11 + i), i == 4) for i in range(7))

    baru = P.kartu_beranda(None, None, False, pekan)
    jalan = P.kartu_beranda(_sesi(), "t2", False, pekan)
    habis = P.kartu_beranda(None, "t2", True, pekan)

    assert baru.count('class="hr-titik"') == 7 and "Pilih tingkatmu" in baru and "Mulai latihan" in baru
    assert 'class="ada"' in baru and baru.count('class="kosong"') == 6
    assert "Tingkat 2" in jalan and "Lanjutkan" in jalan and "sesi/4?no=3" in jalan
    assert "Lihat latihan" in habis and "Jatah latihan gratis hari ini sudah dipakai" in habis


def test_blok_orang_tua_angka_dan_kosong():
    hari = tuple(("2027-01-%02d" % (9 + i), i in (1, 5)) for i in range(7))
    isi = _teks(P.blok_orang_tua(hs.RingkasanHarian("t5", hari, 12, 9)).encode())

    assert "Tingkat 5" in isi and "2</b> dari 7" in P.blok_orang_tua(hs.RingkasanHarian("t5", hari, 12, 9)) \
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
