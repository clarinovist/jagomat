"""Halaman anak Latihan Lomba (unit): escape, urutan DOM form, timer, skrip, dan tanpa hex literal."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_browser as B  # noqa: E402
import contest_pages as P  # noqa: E402
import contest_results as R  # noqa: E402
import contest_store as K  # noqa: E402

MESIN = Path(__file__).resolve().parent.parent
SESI_ID = 42
SVG_SOAL = '<svg id="gambar-uji" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'
SVG_PILIHAN = '<svg id="pilihan-uji" viewBox="0 0 10 10"><rect width="9" height="9"/></svg>'
KATA_TERLARANG = ("kunci", "pembahasan")
SKRIP_TIMER_DIBUNGKUS = f"<script>{B.SKRIP_TIMER}</script>"


def _soal(**ubah):
    dasar = dict(nomor=3, jenis="pg", topik="bilangan", teks="Berapa 2 + 3?", svg="",
                 pilihan=("4", "5", "6", "7"), gambar_pilihan=("", "", "", ""), jawaban=None)
    return K.SoalAnak(**{**dasar, **ubah})


def _isian(**ubah):
    return _soal(jenis="isian", pilihan=(), gambar_pilihan=(), **ubah)


def _html(soal=None, terjawab=frozenset(), sisa=600, galat=False):
    return P.halaman_soal(SESI_ID, soal or _soal(), terjawab, sisa, galat).decode()


def _kontrol_pertama_di_form(isi):
    awal = isi.index("<form")
    return re.search(r"<(button|input|select|textarea)\b[^>]*>", isi[awal:]).group(0)


# --- escape dan markup tepercaya -----------------------------------------------------

def test_teks_soal_dan_pilihan_di_escape():
    soal = _soal(teks='<b onclick="x">Tia & "Budi"</b>', pilihan=("<i>1</i>", "2", "3", "4"))

    isi = _html(soal)

    assert "&lt;b onclick=&quot;x&quot;&gt;Tia &amp; &quot;Budi&quot;&lt;/b&gt;" in isi
    assert '<b onclick' not in isi and "<i>1</i>" not in isi and "&lt;i&gt;1&lt;/i&gt;" in isi


def test_nilai_isian_tersimpan_di_escape_dalam_atribut():
    isi = _html(_isian(jawaban='"><script>x</script>'))

    assert 'value="&quot;&gt;&lt;script&gt;x&lt;/script&gt;"' in isi


def test_svg_soal_disisipkan_sekali_apa_adanya():
    isi = _html(_soal(svg=SVG_SOAL))

    assert isi.count(SVG_SOAL) == 1


def test_gambar_pilihan_menggantikan_teks_pilihan():
    soal = _soal(pilihan=("teks-a", "teks-b", "teks-c", "teks-d"),
                 gambar_pilihan=(SVG_PILIHAN, SVG_PILIHAN, SVG_PILIHAN, SVG_PILIHAN))

    isi = _html(soal)

    assert isi.count(SVG_PILIHAN) == 4 and "teks-a" not in isi and 'class="pilihan bergambar"' in isi


def test_label_topik_tampil_tetapi_bukan_tingkat_atau_templat():
    isi = _html(_soal(topik="operasi"))
    badan = re.sub(r"<style>.*?</style>", "", isi, flags=re.S)

    assert "Operasi Hitung" in badan and "tingkat" not in badan and "template" not in badan


# --- urutan DOM: Enter/Go menyimpan di soal yang sama ---------------------------------

@pytest.mark.parametrize("soal", [_soal(), _isian(jawaban="12")], ids=["pg", "isian"])
def test_tombol_kirim_bawaan_tersembunyi_visual_adalah_kontrol_pertama_di_form(soal):
    isi = _html(soal)

    pembuka = '<button type="submit" name="aksi" value="simpan" class="sr-saja">'
    bawaan = pembuka + "Simpan</button>"
    assert _kontrol_pertama_di_form(isi) == pembuka
    assert isi.index(bawaan) < isi.index('name="pindah"')
    assert "display:none" not in isi.replace(" ", "")


def test_hanya_satu_form_dan_nomor_soal_tersembunyi_satu_kali():
    isi = _html()

    assert isi.count("<form") == 1 and isi.count('name="no"') == 1
    assert 'action="/murid/lomba/sesi/42/jawab"' in isi


def test_isian_memakai_teks_numerik_bukan_type_number():
    isi = _html(_isian(jawaban="7"))

    assert 'type="text"' in isi and 'inputmode="numeric"' in isi and 'pattern="[0-9]*"' in isi
    assert 'maxlength="6"' in isi and 'autocomplete="off"' in isi and 'value="7"' in isi
    assert 'type="number"' not in isi
    assert 'name="aksi" value="simpan" class="tombol"' in isi


def test_pesan_galat_angka_hanya_untuk_soal_isian():
    assert P.PESAN_GALAT_ANGKA in _html(_isian(), galat=True)
    assert P.PESAN_GALAT_ANGKA not in _html(_isian(), galat=False)
    assert P.PESAN_GALAT_ANGKA not in _html(_soal(), galat=True)


def test_pilihan_tersimpan_ditandai_dipilih_dan_lainnya_tidak():
    isi = _html(_soal(jawaban="B"))

    assert isi.count("pilih dipilih") == 1
    assert re.search(r'class="pilih dipilih" aria-pressed="true"><span class="huruf">B<', isi)


def test_empat_tombol_pilihan_punya_markup_sama_selain_nilai():
    isi = _html(_soal())

    tombol = re.findall(r'<button type="submit" name="jawaban" value="([A-D])" class="pilih" aria-pressed="false">'
                        r'<span class="huruf">\1</span>', isi)
    assert tombol == ["A", "B", "C", "D"]


# --- strip nomor ----------------------------------------------------------------------

def test_strip_nomor_membedakan_belum_dijawab_dan_sudah_dijawab():
    isi = _html(_soal(nomor=3), terjawab=frozenset({1, 2, 5}))

    assert len(re.findall(r'class="nomor ', isi)) == 10
    assert isi.count("belum dijawab") == 7 and isi.count("sudah dijawab") == 3
    assert isi.count('class="nomor sudah"') == 3 and isi.count('class="nomor belum') == 7


def test_strip_nomor_menandai_satu_soal_aktif():
    isi = _html(_soal(nomor=4), terjawab=frozenset())

    assert isi.count("aria-current") == 1
    assert re.search(r'value="4" class="nomor belum aktif" aria-current="step"', isi)


def test_tombol_sebelumnya_dan_berikutnya_menyesuaikan_ujung():
    awal = _html(_soal(nomor=1))
    akhir = _html(_soal(nomor=10))
    tengah = _html(_soal(nomor=5))

    assert "Sebelumnya" not in awal and "Berikutnya" in awal
    assert "Berikutnya" not in akhir and "Sebelumnya" in akhir
    assert 'value="4" class="tombol sekunder"' in tengah and 'value="6" class="tombol"' in tengah


def test_selesai_adalah_tombol_kirim_di_dalam_form_agar_isian_terketik_ikut_tersimpan():
    isi = _html()
    form_akhir = isi.index("</form>")

    assert 'name="aksi" value="selesai"' in isi[:form_akhir]
    assert 'href="/murid/lomba/sesi/42/selesai"' not in isi


# --- timer ----------------------------------------------------------------------------

def test_timer_memuat_sisa_tujuan_hasil_dan_teks_awal():
    isi = _html(sisa=605)

    assert '<div class="timer" id="timer" data-sisa="605" data-hasil="/murid/lomba/hasil/42">10:05</div>' in isi
    assert "Soal 3 dari 10" in isi


@pytest.mark.parametrize("sisa,merah", [(181, False), (180, True), (179, True), (1, True), (900, False)])
def test_kelas_merah_hanya_saat_sisa_180_detik_atau_kurang(sisa, merah):
    isi = _html(sisa=sisa)

    assert ('class="timer merah"' in isi) is merah
    assert ('class="timer"' in isi) is (not merah)


def test_mmss_membulatkan_ke_nol_dan_menata_dua_digit():
    assert P.mmss(900) == "15:00" and P.mmss(65) == "01:05" and P.mmss(0) == "00:00" and P.mmss(-3) == "00:00"


# --- skrip ----------------------------------------------------------------------------

@pytest.mark.parametrize("terlarang", ["fetch", "XMLHttpRequest", "eval", "innerHTML", "localStorage", "</script>"])
def test_skrip_timer_tidak_memuat_api_terlarang(terlarang):
    assert terlarang not in B.SKRIP_TIMER


@pytest.mark.parametrize("wajib", ["performance.now", "pageshow", "persisted", "visibilitychange", "textContent",
                                   "location.replace", "data-sisa", "data-hasil", "try", "catch"])
def test_skrip_timer_memuat_bagian_yang_dibutuhkan(wajib):
    assert wajib in B.SKRIP_TIMER


def _ringkas_sesi(nilai, mulai, sesi_id=5):
    return R.RingkasSesi(sesi_id=sesi_id, mulai_epoch=mulai, selesai_epoch=mulai + 330, status="dikumpul", nilai=nilai,
                         jumlah_soal=10, waktu_terpakai_detik=330, per_topik=())


def _semua_halaman():
    sesi = K.SesiRingkas(id=SESI_ID, siswa_id=1, status="berjalan", mulai_epoch=0, batas_epoch=900, selesai_epoch=None)
    return {
        "soal-pg": P.halaman_soal(SESI_ID, _soal(), frozenset({1}), 600),
        "soal-isian": P.halaman_soal(SESI_ID, _isian(), frozenset(), 100, True),
        "awal-baru": P.halaman_awal(None),
        "awal-lanjut": P.halaman_awal(sesi, 300),
        "selesai": P.halaman_selesai(SESI_ID, 3, 200),
        "awal-riwayat": P.halaman_awal(None, 0, (_ringkas_sesi(7, 1_800_000_000),)),
        "gagal": P.halaman_gagal_siapkan(),
    }


@pytest.mark.parametrize("nama", ["soal-pg", "soal-isian", "selesai"])
def test_skrip_di_halaman_berwaktu_polos_tanpa_atribut(nama):
    isi = _semua_halaman()[nama].decode()

    pembuka = re.findall(r"<script\b[^>]*>", isi)
    assert pembuka == ["<script>"]
    assert SKRIP_TIMER_DIBUNGKUS in isi


@pytest.mark.parametrize("nama", ["awal-baru", "awal-lanjut", "awal-riwayat", "gagal"])
def test_halaman_tanpa_timer_tidak_memuat_skrip(nama):
    assert b"<script" not in _semua_halaman()[nama]


@pytest.mark.parametrize("nama", sorted(_semua_halaman()))
def test_tidak_ada_atribut_penangan_kejadian_atau_api_jaringan(nama):
    isi = _semua_halaman()[nama].decode()

    assert not re.search(r"\son[a-z]+\s*=", isi, re.I)
    assert "fetch(" not in isi and "XMLHttpRequest" not in isi


@pytest.mark.parametrize("nama", ["soal-pg", "soal-isian"])
def test_halaman_soal_tidak_memuat_kata_kunci_atau_pembahasan(nama):
    isi = _semua_halaman()[nama].decode().lower()

    assert not any(kata in isi for kata in KATA_TERLARANG)


# --- halaman lain ---------------------------------------------------------------------

def test_halaman_selesai_menyebut_jumlah_belum_dijawab():
    isi = P.halaman_selesai(SESI_ID, 7, 200).decode()

    assert "Masih ada <strong>7</strong> soal belum dijawab" in isi
    assert 'action="/murid/lomba/sesi/42/kumpul"' in isi and "Ya, kumpulkan" in isi
    assert 'href="/murid/lomba/sesi/42?no=1"' in isi and "Kembali ke soal" in isi


def test_halaman_selesai_semua_terjawab():
    isi = P.halaman_selesai(SESI_ID, 0, 200).decode()

    assert "Semua soal sudah dijawab" in isi and "Masih ada" not in isi


def test_halaman_awal_baru_menawarkan_mulai_dan_lanjut_menampilkan_sisa():
    baru = P.halaman_awal(None).decode()
    sesi = K.SesiRingkas(id=9, siswa_id=1, status="berjalan", mulai_epoch=0, batas_epoch=900, selesai_epoch=None)
    lanjut = P.halaman_awal(sesi, 754).decode()

    assert 'action="/murid/lomba/mulai"' in baru and "Mulai" in baru and "Lanjutkan" not in baru
    assert 'href="/murid/lomba/sesi/9?no=1"' in lanjut and "12:34" in lanjut and 'action="/murid/lomba/mulai"' not in lanjut
    assert "10 soal" in baru and "15 menit" in baru


# --- tanpa hex literal ----------------------------------------------------------------

@pytest.mark.parametrize("berkas", ["contest_style.py", "contest_pages.py", "contest_browser.py", "contest_format.py",
                                    "contest_chart_svg.py", "contest_results_pages.py", "contest_guru_pages.py",
                                    "contest_guru_http.py"])
def test_tanpa_warna_literal_di_berkas_halaman(berkas):
    sumber = (MESIN / berkas).read_text(encoding="utf-8")

    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|%23[0-9a-fA-F]{3,8}\b", sumber)


# --- Latihan terakhir di halaman awal ------------------------------------------------------

def test_halaman_awal_tanpa_riwayat_tidak_memuat_bagian_latihan_terakhir_dan_sama_dengan_default():
    assert P.halaman_awal(None, 0, ()) == P.halaman_awal(None)
    assert "Latihan terakhir" not in P.halaman_awal(None).decode()


def test_latihan_terakhir_menampilkan_tanggal_wib_nilai_dan_tautan_hasil_sesuai_urutan_masuk():
    riwayat = (_ringkas_sesi(8, 1_800_000_000, sesi_id=12), _ringkas_sesi(3, 1_799_900_000, sesi_id=9))

    isi = P.halaman_awal(None, 0, riwayat).decode()

    assert "Latihan terakhir" in isi
    assert isi.index('href="/murid/lomba/hasil/12"') < isi.index('href="/murid/lomba/hasil/9"')
    assert "<span>15 Jan 2027, 15:00</span><strong>8/10</strong>" in isi
    assert "<strong>3/10</strong>" in isi


def test_latihan_terakhir_dipotong_di_lima_sesi():
    riwayat = tuple(_ringkas_sesi(5, 1_800_000_000 - i, sesi_id=100 + i) for i in range(8))

    isi = P.halaman_awal(None, 0, riwayat).decode()

    assert isi.count('href="/murid/lomba/hasil/') == 5 and 'hasil/104"' in isi and 'hasil/105"' not in isi


def test_tautan_beranda_murid_menunjuk_ke_halaman_awal_lomba_tanpa_skrip():
    isi = P.tautan_beranda_murid()

    assert 'href="/murid/lomba"' in isi and "Latihan Lomba" in isi and "<script" not in isi
    assert not re.search(r"\son[a-z]+\s*=", isi, re.I)
