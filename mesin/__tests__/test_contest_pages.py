"""Halaman anak Latihan Lomba (unit): escape, urutan DOM form, timer, skrip, dan tanpa hex literal."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_browser as B  # noqa: E402
import design_tokens as T  # noqa: E402
import contest_pages as P  # noqa: E402
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


def _html(soal=None, terjawab=frozenset(), sisa=600, galat=False, isi_galat=""):
    return P.halaman_soal(SESI_ID, soal or _soal(), terjawab, sisa, galat, isi_galat).decode()


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


def test_isian_tidak_punya_tombol_simpan_terlihat_hanya_yang_tersembunyi_untuk_enter():
    isi = _html(_isian(jawaban="7"))

    assert isi.count('value="simpan"') == 1 and 'value="simpan" class="sr-saja"' in isi
    assert 'class="tombol">Simpan<' not in isi and 'class="tombol sekunder">Simpan<' not in isi


def test_galat_mempertahankan_ketikan_anak_dan_meng_escape_nilainya():
    isi = _html(_isian(jawaban="9"), galat=True, isi_galat='5,"<9')

    assert 'name="jawaban" value="5,&quot;&lt;9"' in isi and 'name="jawaban" value="9"' not in isi
    assert P.PESAN_GALAT_ANGKA in isi


def test_ketikan_galat_diabaikan_bila_tidak_galat_dan_jawaban_tersimpan_tetap_tampil():
    assert 'name="jawaban" value="9"' in _html(_isian(jawaban="9"), galat=False, isi_galat="abc")
    assert 'name="jawaban" value="9"' in _html(_isian(jawaban="9"), galat=True, isi_galat="")


def test_pesan_galat_memberi_contoh_dan_tanpa_istilah_teknis():
    assert P.PESAN_GALAT_ANGKA == "Tulis angkanya saja, tanpa huruf atau tanda baca. Contoh: 120"


def test_alamat_sesi_galat_membawa_ketikan_dipotong_enam_karakter_dan_di_url_encode():
    assert P.alamat_sesi(5, 3) == "/murid/lomba/sesi/5?no=3"
    assert P.alamat_sesi(5, 3, galat=True) == "/murid/lomba/sesi/5?no=3&galat=angka"
    assert P.alamat_sesi(5, 3, galat=True, isi="5,94") == "/murid/lomba/sesi/5?no=3&galat=angka&isi=5%2C94"
    assert P.alamat_sesi(5, 3, galat=True, isi="1234567890").endswith("&isi=123456")
    assert "isi=" not in P.alamat_sesi(5, 3, isi="abc")


def test_pesan_galat_angka_hanya_untuk_soal_isian():
    assert P.PESAN_GALAT_ANGKA in _html(_isian(), galat=True)
    assert P.PESAN_GALAT_ANGKA not in _html(_isian(), galat=False)
    assert P.PESAN_GALAT_ANGKA not in _html(_soal(), galat=True)


def test_pilihan_tersimpan_ditandai_dipilih_dan_lainnya_tidak():
    isi = _html(_soal(jawaban="B"))

    assert isi.count("pilih dipilih") == 1
    assert re.search(r'class="pilih dipilih" aria-pressed="true"><span class="huruf">B<', isi)


def test_hanya_pilihan_terpilih_berlabel_tersimpan():
    assert _html(_soal(jawaban="B")).count('<span class="tersimpan">') == 1
    assert '<span class="tersimpan">' not in _html(_soal(jawaban=None))


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


def test_tombol_maju_utama_dan_mundur_sekunder_dengan_nomor_tujuan_menyesuaikan_ujung():
    awal = _html(_soal(nomor=1))
    akhir = _html(_soal(nomor=10))
    tengah = _html(_soal(nomor=5))

    assert "\u2190 Soal" not in awal and "Soal 2 \u2192" in awal
    assert "Soal 11" not in akhir and "\u2190 Soal 9" in akhir
    assert 'value="4" class="tombol sekunder">\u2190 Soal 4<' in tengah
    assert 'value="6" class="tombol">Soal 6 \u2192<' in tengah
    assert "Sebelumnya" not in tengah and "Berikutnya" not in tengah


def test_tombol_maju_soal_isian_berlabel_simpan_ke_soal_berikutnya_dan_pindah_tetap_menyimpan():
    isi = _html(_isian(nomor=4, jawaban="12"))

    assert 'name="pindah" value="5" class="tombol">Simpan, ke soal 5 \u2192<' in isi
    assert 'name="pindah" value="3" class="tombol sekunder">\u2190 Soal 3<' in isi
    assert "Simpan, ke soal" not in _html(_soal(nomor=4))


def test_selesai_adalah_tombol_kirim_bergaya_tautan_di_dalam_form_agar_isian_terketik_ikut_tersimpan():
    isi = _html()
    form_akhir = isi.index("</form>")

    assert 'name="aksi" value="selesai" class="tautan-selesai">Selesai &amp; kumpulkan<' in isi[:form_akhir]
    assert 'value="selesai" class="tombol' not in isi
    assert 'href="/murid/lomba/sesi/42/selesai"' not in isi


def test_strip_nomor_tanpa_titik_atau_garis_putus_dan_nomor_terisi_berkelas_sudah():
    from contest_style import GAYA_LOMBA

    nomor = GAYA_LOMBA[GAYA_LOMBA.index("/* ===== strip nomor"):GAYA_LOMBA.index("/* ===== pilihan jawaban")]
    assert "dashed" not in nomor and "::after" not in nomor
    assert re.search(r"\.nomor\.sudah \{ background: " + re.escape(T.ANAK_AKSEN) + "; color: " + re.escape(T.TEKS_PUTIH), nomor)
    assert re.search(r"\.nomor\.aktif \{ box-shadow: [^;]*" + re.escape(T.TEKS_JUDUL), nomor)


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


def _semua_halaman():
    return {
        "soal-pg": P.halaman_soal(SESI_ID, _soal(), frozenset({1}), 600),
        "soal-isian": P.halaman_soal(SESI_ID, _isian(), frozenset(), 100, True, "5,9"),
        "selesai": P.halaman_selesai(SESI_ID, [3, 4], 200),
        "selesai-penuh": P.halaman_selesai(SESI_ID, [], 200),
        "gagal": P.halaman_gagal_siapkan(),
    }


@pytest.mark.parametrize("nama", ["soal-pg", "soal-isian", "selesai", "selesai-penuh"])
def test_skrip_di_halaman_berwaktu_polos_tanpa_atribut(nama):
    isi = _semua_halaman()[nama].decode()

    pembuka = re.findall(r"<script\b[^>]*>", isi)
    assert pembuka == ["<script>"]
    assert SKRIP_TIMER_DIBUNGKUS in isi


@pytest.mark.parametrize("nama", ["gagal"])
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


# --- konfirmasi kumpul ----------------------------------------------------------------

def _selesai(kosong, sisa=200):
    return P.halaman_selesai(SESI_ID, kosong, sisa).decode()


def test_konfirmasi_dengan_kosong_menyebut_jumlah_sisa_menit_dan_dua_aksi():
    isi = _selesai([2, 5, 9], sisa=420)

    assert "Masih ada 3 soal kosong" in isi and "Waktumu masih 7 menit. Coba isi dulu, ya." in isi
    assert 'href="/murid/lomba/sesi/42?no=2">Kerjakan soal 2</a>' in isi and 'class="tombol besar"' in isi
    assert 'action="/murid/lomba/sesi/42/kumpul"' in isi
    assert 'class="tombol sekunder">Kumpulkan sekarang</button>' in isi
    assert "Kumpulkan</button>" not in isi.replace("Kumpulkan sekarang</button>", "")


def test_konfirmasi_strip_memuat_sepuluh_nomor_kosong_berupa_tautan_terisi_bukan_tautan():
    isi = _selesai([2, 5])

    assert len(re.findall(r'class="nomor ', isi)) == 10
    assert isi.count('<a class="nomor belum"') == 2 and isi.count('<span class="nomor sudah">') == 8
    assert 'href="/murid/lomba/sesi/42?no=2"' in isi and 'href="/murid/lomba/sesi/42?no=5"' in isi
    assert 'href="/murid/lomba/sesi/42?no=1"' not in isi


@pytest.mark.parametrize("sisa,teks", [(900, "15 menit"), (119, "1 menit"), (60, "1 menit"), (59, "kurang dari 1 menit"),
                                       (0, "kurang dari 1 menit"), (-5, "kurang dari 1 menit")])
def test_sisa_waktu_dibulatkan_ke_bawah_dengan_minimal_kurang_dari_semenit(sisa, teks):
    assert P.teks_sisa_waktu(sisa) == f"Waktumu masih {teks}"


def test_konfirmasi_kerjakan_soal_menunjuk_kosong_pertama_bukan_urutan_masukan():
    isi = _selesai([7, 3, 9])

    assert "Kerjakan soal 3</a>" in isi and 'class="tombol besar" href="/murid/lomba/sesi/42?no=3"' in isi


def test_konfirmasi_semua_terisi_merayakan_dengan_kumpulkan_utama_dan_periksa_lagi():
    isi = _selesai([])

    assert "Semua soal sudah kamu jawab!" in isi and "maskot-merayakan" in isi
    assert 'action="/murid/lomba/sesi/42/kumpul"' in isi and 'class="tombol besar">Kumpulkan</button>' in isi
    assert 'href="/murid/lomba/sesi/42?no=1">Periksa lagi</a>' in isi
    assert "Masih ada" not in isi and "Kumpulkan sekarang" not in isi and isi.count('<span class="nomor sudah">') == 10


# --- tanpa hex literal ----------------------------------------------------------------

@pytest.mark.parametrize("berkas", ["contest_style.py", "contest_pages.py", "contest_browser.py", "contest_format.py",
                                    "contest_chart_svg.py", "contest_results_pages.py", "contest_guru_pages.py",
                                    "contest_guru_http.py", "contest_awal.py", "contest_home.py",
                                    "contest_komponen.py", "contest_anak.py", "contest_paket.py"])
def test_tanpa_warna_literal_di_berkas_halaman(berkas):
    sumber = (MESIN / berkas).read_text(encoding="utf-8")

    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|%23[0-9a-fA-F]{3,8}\b", sumber)
