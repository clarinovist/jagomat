"""Kontrak inti Latihan Lomba: validasi soal, pilihan, pembuatan, dan pendaftaran template."""
import random

import pytest

import contest_core as C

SVG_SAH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" '
    'aria-label="Gambar benda"><rect x="0" y="0" width="5" height="5"/></svg>'
)


def _pg(**ubah):
    dasar = dict(
        template_id="ops_uji_pg", topik="operasi", jenis=C.JENIS_PG, tingkat=1,
        teks="Berapa hasilnya?", svg="", kunci="8",
        pengecoh=(C.Pengecoh("7", "salah hitung"), C.Pengecoh("9", "lupa kurang"),
                  C.Pengecoh("10", "salah tambah")),
        pembahasan=("9 + 6 = 15", "15 - 7 = 8"),
        parameter=C.kanonik({"a": 9}), nilai=8,
    )
    dasar.update(ubah)
    return C.SoalLomba(**dasar)


def _isian(**ubah):
    dasar = dict(
        template_id="bil_uji_isian", topik="bilangan", jenis=C.JENIS_ISIAN, tingkat=2,
        teks="Ada berapa?", svg="", kunci="5", pengecoh=(),
        pembahasan=("Hitung satu per satu.",), parameter=C.kanonik({"k": 5}), nilai=5,
    )
    dasar.update(ubah)
    return C.SoalLomba(**dasar)


# --- validasi_soal: soal sah lolos -------------------------------------------------

def test_soal_pg_dan_isian_yang_sah_lolos_validasi():
    C.validasi_soal(_pg())
    C.validasi_soal(_isian())


def test_pg_kunci_non_angka_seperti_jam_atau_hari_boleh_tanpa_nilai():
    C.validasi_soal(_pg(kunci="08.30", nilai=None, pengecoh=(
        C.Pengecoh("09.30", "jarum tertukar"), C.Pengecoh("06.40", "baca menit"),
        C.Pengecoh("08.00", "abaikan menit"))))


# --- validasi_soal: tiap guard punya kasus negatif ---------------------------------

@pytest.mark.parametrize("ubah", [
    dict(topik="ipa"),
    dict(jenis="uraian"),
    dict(tingkat=0),
    dict(tingkat=4),
    dict(teks="   "),
    dict(teks="Hitung <b>ini</b>"),
    dict(pembahasan=()),
    dict(pembahasan=("",)),
    dict(kunci=""),
    dict(nilai=0),
    dict(nilai=C.BATAS_NILAI + 1),
    dict(parameter="{bukan json"),
    dict(parameter='{"b": 1, "a": 2}'),
])
def test_pg_yang_melanggar_aturan_ditolak(ubah):
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(**ubah))


def test_pg_wajib_tiga_pengecoh():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(pengecoh=(C.Pengecoh("7", "x"), C.Pengecoh("9", "y"))))


def test_pg_pengecoh_sama_dengan_kunci_ditolak():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(pengecoh=(C.Pengecoh("8", "x"), C.Pengecoh("9", "y"),
                                      C.Pengecoh("10", "z"))))


def test_pg_pengecoh_kembar_setelah_normalisasi_ditolak():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(kunci="Rabu", nilai=None, pengecoh=(
            C.Pengecoh("Selasa", "x"), C.Pengecoh(" selasa ", "y"), C.Pengecoh("Kamis", "z"))))


def test_pg_pengecoh_tanpa_label_kesalahan_ditolak():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(pengecoh=(C.Pengecoh("7", ""), C.Pengecoh("9", "y"),
                                      C.Pengecoh("10", "z"))))


@pytest.mark.parametrize("ubah", [
    dict(kunci="0", nilai=0),
    dict(kunci="-3", nilai=-3),
    dict(kunci="3,5", nilai=None),
    dict(kunci="5", nilai=None),
    dict(kunci="5", nilai=6),
    dict(pengecoh=(C.Pengecoh("1", "x"),)),
])
def test_isian_yang_melanggar_aturan_ditolak(ubah):
    with pytest.raises(ValueError):
        C.validasi_soal(_isian(**ubah))


# --- validasi_svg ------------------------------------------------------------------

def test_svg_sah_lolos():
    C.validasi_svg(SVG_SAH)


@pytest.mark.parametrize("svg", [
    "<div></div>",
    SVG_SAH.replace('role="img" ', ""),
    SVG_SAH.replace('aria-label="Gambar benda"', ""),
    SVG_SAH.replace("Gambar benda", "Ada 15 benda"),
    SVG_SAH.replace("<rect", "<script>x()</script><rect"),
    SVG_SAH.replace("<rect", "<foreignObject><p>x</p></foreignObject><rect"),
    SVG_SAH.replace("<rect", '<rect onclick="x()"'),
    SVG_SAH.replace("<rect", '<image href="https://contoh.id/a.png"/><rect'),
    SVG_SAH.replace("<rect", "<title>delapan</title><rect"),
    SVG_SAH.replace("<rect", "<desc>jawabannya</desc><rect"),
    SVG_SAH.replace("</svg>", "<!-- x " + "a" * C.MAKS_UKURAN_SVG + " --></svg>"),
])
def test_svg_berbahaya_atau_membocorkan_jawaban_ditolak(svg):
    with pytest.raises(ValueError):
        C.validasi_svg(svg)


def test_validasi_soal_ikut_memeriksa_svg():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(svg="<svg></svg>"))


# --- kanonik dan tanda tangan ------------------------------------------------------

def test_kanonik_urutan_kunci_tidak_memengaruhi_hasil():
    assert C.kanonik({"b": 1, "a": [2, 3]}) == C.kanonik({"a": [2, 3], "b": 1})


def test_kanonik_menolak_nilai_yang_tidak_bisa_diserialkan():
    with pytest.raises(ValueError):
        C.kanonik({"a": float("nan")})
    with pytest.raises(ValueError):
        C.kanonik({"a": {1, 2}})


def test_tanda_tangan_membedakan_template_dan_parameter():
    a = C.tanda_tangan(_pg(parameter=C.kanonik({"a": 1})))
    b = C.tanda_tangan(_pg(parameter=C.kanonik({"a": 2})))
    c = C.tanda_tangan(_pg(template_id="lain", parameter=C.kanonik({"a": 1})))
    assert len({a, b, c}) == 3


# --- pilihan dan jawaban -----------------------------------------------------------

@pytest.mark.parametrize("posisi", range(4))
def test_susun_pilihan_menaruh_kunci_di_posisi_yang_diminta(posisi):
    soal = _pg()
    pilihan = C.susun_pilihan(soal, posisi, random.Random(1))
    assert len(pilihan) == 4 and len(set(pilihan)) == 4
    assert pilihan[posisi] == soal.kunci
    assert set(pilihan) == {"8", "7", "9", "10"}


def test_susun_pilihan_deterministik_untuk_seed_sama():
    soal = _pg()
    assert (C.susun_pilihan(soal, 2, random.Random(7))
            == C.susun_pilihan(soal, 2, random.Random(7)))


def test_susun_pilihan_menolak_isian_dan_posisi_di_luar_rentang():
    with pytest.raises(ValueError):
        C.susun_pilihan(_isian(), 0, random.Random(1))
    for buruk in (-1, 4):
        with pytest.raises(ValueError):
            C.susun_pilihan(_pg(), buruk, random.Random(1))


@pytest.mark.parametrize("jumlah", [0, 1, 4, 7, 8, 13])
def test_posisi_seimbang_selisih_hitungan_paling_banyak_satu(jumlah):
    posisi = C.posisi_seimbang(jumlah, random.Random(3))
    assert len(posisi) == jumlah
    hitung = [posisi.count(i) for i in range(4)]
    assert max(hitung) - min(hitung) <= 1


def test_posisi_seimbang_delapan_soal_masing_masing_dua():
    posisi = C.posisi_seimbang(8, random.Random(9))
    assert [posisi.count(i) for i in range(4)] == [2, 2, 2, 2]


def test_jawaban_benar_pg_membandingkan_teks_ternormalisasi():
    assert C.jawaban_benar("Rp9.500", " rp9.500 ", C.JENIS_PG)
    assert not C.jawaban_benar("Rp9.500", "Rp10.500", C.JENIS_PG)


def test_jawaban_benar_isian_membandingkan_bilangan():
    assert C.jawaban_benar("24", "24", C.JENIS_ISIAN)
    assert C.jawaban_benar("24", " 024 ", C.JENIS_ISIAN)
    assert not C.jawaban_benar("24", "25", C.JENIS_ISIAN)
    assert not C.jawaban_benar("24", "dua puluh empat", C.JENIS_ISIAN)
    assert not C.jawaban_benar("24", "", C.JENIS_ISIAN)
    assert not C.jawaban_benar("24", "24.0", C.JENIS_ISIAN)


# --- template: pendaftaran dan pembuatan -------------------------------------------

def _template(**ubah):
    def sampler(rng):
        return {"a": rng.randint(1, 5)}

    def bangun(parameter):
        return _pg(parameter=C.kanonik(parameter))

    def verifikator(parameter):
        return "8"

    dasar = dict(id="ops_uji_pg", topik="operasi", jenis=C.JENIS_PG, tingkat=1,
                 sampler=sampler, bangun=bangun, verifikator=verifikator)
    dasar.update(ubah)
    return C.Template(**dasar)


@pytest.fixture
def registri_kosong(monkeypatch):
    monkeypatch.setattr(C, "REGISTRY", {})


def test_daftarkan_lalu_ambil_dan_semua(registri_kosong):
    template = C.daftarkan(_template())
    assert C.ambil("ops_uji_pg") is template
    assert C.semua() == (template,)


def test_daftarkan_menolak_id_ganda(registri_kosong):
    C.daftarkan(_template())
    with pytest.raises(ValueError):
        C.daftarkan(_template())


@pytest.mark.parametrize("ubah", [
    dict(id="Besar"), dict(id="a"), dict(id="pakai-strip"),
    dict(topik="ipa"), dict(jenis="uraian"), dict(tingkat=9),
])
def test_daftarkan_menolak_metadata_tidak_sah(registri_kosong, ubah):
    with pytest.raises(ValueError):
        C.daftarkan(_template(**ubah))


def test_buat_soal_deterministik_untuk_seed_sama():
    template = _template()
    assert C.buat_soal(template, random.Random(5)) == C.buat_soal(template, random.Random(5))


def test_buat_soal_mengulang_parameter_saat_tidak_sah():
    panggilan = {"n": 0}

    def sampler(rng):
        panggilan["n"] += 1
        if panggilan["n"] < 3:
            raise C.ParameterTidakSah("pengecoh kurang")
        return {"a": 1}

    soal = C.buat_soal(_template(sampler=sampler), random.Random(1))
    assert panggilan["n"] == 3 and soal.template_id == "ops_uji_pg"


def test_buat_soal_gagal_setelah_batas_percobaan():
    def sampler(rng):
        raise C.ParameterTidakSah("selalu gagal")

    with pytest.raises(C.GagalMembuatSoal):
        C.buat_soal(_template(sampler=sampler), random.Random(1), maks_percobaan=5)


def test_buat_soal_tidak_menyembunyikan_soal_cacat_lewat_pengulangan():
    def bangun(parameter):
        return _pg(kunci="", parameter=C.kanonik(parameter))

    with pytest.raises(ValueError):
        C.buat_soal(_template(bangun=bangun), random.Random(1))


def test_buat_soal_menolak_soal_yang_tidak_cocok_dengan_template():
    def bangun(parameter):
        return _pg(template_id="lain", parameter=C.kanonik(parameter))

    with pytest.raises(ValueError):
        C.buat_soal(_template(bangun=bangun), random.Random(1))


def test_buat_soal_menolak_parameter_soal_yang_bukan_hasil_sampler():
    def bangun(parameter):
        return _pg(parameter=C.kanonik({"a": 999}))

    with pytest.raises(ValueError):
        C.buat_soal(_template(bangun=bangun), random.Random(1))


# --- pilihan bergambar, pengecoh angka, dan awalan id --------------------------------

def _svg(label):
    return SVG_SAH.replace("Gambar benda", label)


def _pg_gambar(**ubah):
    dasar = dict(
        kunci="lingkaran", nilai=None, kunci_svg=_svg("Bentuk bulat"),
        pengecoh=(C.Pengecoh("persegi", "x", _svg("Bentuk kotak")),
                  C.Pengecoh("segitiga", "y", _svg("Bentuk runcing")),
                  C.Pengecoh("belah ketupat", "z", _svg("Bentuk miring"))),
    )
    dasar.update(ubah)
    return _pg(**dasar)


def test_pg_dengan_pilihan_gambar_lolos_validasi():
    C.validasi_soal(_pg_gambar())


def test_pilihan_gambar_sebagian_ditolak():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg_gambar(kunci_svg=""))
    with pytest.raises(ValueError):
        C.validasi_soal(_pg_gambar(pengecoh=(
            C.Pengecoh("persegi", "x", _svg("Bentuk kotak")),
            C.Pengecoh("segitiga", "y", ""),
            C.Pengecoh("belah ketupat", "z", _svg("Bentuk miring")))))


def test_svg_pilihan_berbahaya_ditolak():
    jahat = _svg("Bentuk bulat").replace("<rect", "<script>x()</script><rect")
    with pytest.raises(ValueError):
        C.validasi_soal(_pg_gambar(kunci_svg=jahat))


def test_svg_pilihan_kembar_ditolak():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg_gambar(kunci_svg=_svg("Bentuk kotak")))


def test_isian_tidak_boleh_punya_gambar_pilihan():
    with pytest.raises(ValueError):
        C.validasi_soal(_isian(kunci_svg=_svg("Bentuk bulat")))


@pytest.mark.parametrize("posisi", range(4))
def test_gambar_pilihan_mengikuti_urutan_pilihan_yang_diacak(posisi):
    soal = _pg_gambar()
    pilihan = C.susun_pilihan(soal, posisi, random.Random(4))
    gambar = C.gambar_pilihan(soal, pilihan)
    assert gambar[posisi] == soal.kunci_svg
    peta = {p.nilai: p.svg for p in soal.pengecoh}
    peta[soal.kunci] = soal.kunci_svg
    assert gambar == tuple(peta[nilai] for nilai in pilihan)


def test_gambar_pilihan_untuk_pilihan_teks_semuanya_kosong():
    soal = _pg()
    assert C.gambar_pilihan(soal, C.susun_pilihan(soal, 1, random.Random(1))) == ("",) * 4


def test_gambar_pilihan_menolak_pilihan_yang_bukan_milik_soal():
    with pytest.raises(ValueError):
        C.gambar_pilihan(_pg(), ("8", "7", "9", "99"))


@pytest.mark.parametrize("buruk", ["0", "-2", "3,5", "abc", "07", str(C.BATAS_NILAI + 1)])
def test_pengecoh_angka_wajib_bilangan_bulat_positif_wajar(buruk):
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(pengecoh=(C.Pengecoh("7", "x"), C.Pengecoh("9", "y"),
                                      C.Pengecoh(buruk, "z"))))


def test_pg_berkunci_angka_wajib_membawa_nilai():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(kunci="8", nilai=None))


def test_pg_nilai_wajib_sama_dengan_kunci():
    with pytest.raises(ValueError):
        C.validasi_soal(_pg(kunci="8", nilai=9))


@pytest.mark.parametrize("ubah", [
    dict(id="uji_pg"),                  # tanpa awalan topik
    dict(id="bil_uji_pg"),              # awalan topik lain (topik operasi)
    dict(id="ukur_uji_pg"),
])
def test_daftarkan_menolak_id_tanpa_awalan_topik_yang_benar(registri_kosong, ubah):
    with pytest.raises(ValueError):
        C.daftarkan(_template(**ubah))


# --- ambil_pengecoh: satu cara menyaring kandidat untuk semua template ----------------

def _kandidat(*nilai):
    return [C.Pengecoh(n, f"salah {n}") for n in nilai]


def test_ambil_pengecoh_mengambil_tiga_pertama_yang_sah_menurut_urutan_prioritas():
    hasil = C.ambil_pengecoh("8", _kandidat("7", "9", "10", "11"))
    assert [p.nilai for p in hasil] == ["7", "9", "10"]


def test_ambil_pengecoh_membuang_kunci_kembar_dan_angka_tidak_wajar():
    hasil = C.ambil_pengecoh("8", _kandidat("8", "7", "7", "0", "-1", "9", "x", "10"))
    assert [p.nilai for p in hasil] == ["7", "9", "10"]


def test_ambil_pengecoh_non_angka_membuang_kembar_setelah_normalisasi():
    hasil = C.ambil_pengecoh("Rabu", _kandidat("rabu", "Selasa", " selasa", "Kamis", "Jumat"))
    assert [p.nilai for p in hasil] == ["Selasa", "Kamis", "Jumat"]


def test_ambil_pengecoh_kurang_dari_tiga_memicu_ulang_parameter():
    with pytest.raises(C.ParameterTidakSah):
        C.ambil_pengecoh("8", _kandidat("8", "7", "9"))
