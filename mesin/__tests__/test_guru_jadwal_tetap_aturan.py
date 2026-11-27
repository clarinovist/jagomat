"""Aturan murni jadwal tetap guru: gerbang, urai dan kanonik blok, formulir, opsi jam, dan luar_jam (data sintetis).

Kalender: 30 Nov 2026 = Senin (isoweekday 1), 1 Des 2026 = Selasa (2). Baku UTC = WIB dikurangi 7 jam.
"""

import pytest

import guru_jadwal_tetap_aturan as A

# Senin 08.00 WIB = 01.00 UTC; Senin 09.00 WIB = 02.00 UTC; dan seterusnya.
BAKU_SENIN_0700_WIB = "2026-11-30T00:00:00"
BAKU_SENIN_0730_WIB = "2026-11-30T00:30:00"
BAKU_SENIN_0759_WIB = "2026-11-30T00:59:00"
BAKU_SENIN_0800_WIB = "2026-11-30T01:00:00"
BAKU_SENIN_0830_WIB = "2026-11-30T01:30:00"
BAKU_SENIN_0900_WIB = "2026-11-30T02:00:00"
BAKU_SENIN_0930_WIB = "2026-11-30T02:30:00"
BAKU_SENIN_0901_WIB = "2026-11-30T02:01:00"
BAKU_SENIN_1000_WIB = "2026-11-30T03:00:00"
BAKU_SENIN_2300_WIB = "2026-11-30T16:00:00"
BAKU_SENIN_2330_WIB = "2026-11-30T16:30:00"
BAKU_SELASA_0800_WIB = "2026-12-01T01:00:00"
BAKU_SELASA_0100_WIB = "2026-11-30T18:00:00"  # 18.00 UTC Senin = 01.00 WIB Selasa

BLOK_PAGI_SENIN = ((1, 480, 600),)
BLOK_MALAM_SENIN = ((1, 1380, 1440),)
BLOK_DUA_SENIN = ((1, 480, 540), (1, 600, 660))
BLOK_BERSENTUHAN_SENIN = ((1, 480, 540), (1, 540, 600))
BLOK_DINI_SENIN = ((1, 60, 120),)

PENANDA_TIDAK_BOLEH_MUNCUL = "ZQX"


def _form_kosong() -> dict:
    """28 field formulir, semua kosong. Dibangun di sini, tidak diambil dari modul, supaya tes memeriksa kontraknya."""
    return {
        f"h{hari}{slot}_{ujung}": ""
        for hari in range(1, 8)
        for slot in ("a", "b")
        for ujung in ("m", "s")
    }


def _form_dengan(isi: dict) -> dict:
    return {**_form_kosong(), **isi}


# --- gerbang ----------------------------------------------------------------------------

def test_gerbang_jadwal_tetap_mati_secara_bawaan():
    # Act / Assert
    assert A.GURU_JADWAL_TETAP_AKTIF is False
    assert A.guru_jadwal_tetap_aktif() is False


def test_gerbang_dibaca_saat_dipanggil_bukan_saat_impor(monkeypatch):
    # Arrange
    monkeypatch.setattr(A, "GURU_JADWAL_TETAP_AKTIF", True)

    # Act / Assert
    assert A.guru_jadwal_tetap_aktif() is True


@pytest.mark.parametrize("nilai", [1, "True", None])
def test_gerbang_hanya_menerima_bool_true_sebagai_aktif(monkeypatch, nilai):
    # Arrange
    monkeypatch.setattr(A, "GURU_JADWAL_TETAP_AKTIF", nilai)

    # Act / Assert
    assert A.guru_jadwal_tetap_aktif() is False


# --- konstanta --------------------------------------------------------------------------

def test_konstanta_aturan_jadwal_sesuai_kontrak():
    # Act / Assert
    assert A.MAKS_BLOK == 14
    assert A.MAKS_BLOK_PER_HARI == 2
    assert A.LANGKAH_MENIT == 30
    assert A.PANJANG_MIN_MENIT == 60
    assert A.MENIT_SEHARI == 1440
    assert (A.HARI_MIN, A.HARI_MAKS) == (1, 7)
    assert A.BATAS_USULAN_PER_HARI == 10
    assert A.NAMA_HARI == ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


# --- urai_blok: teks sah ----------------------------------------------------------------

def test_urai_blok_teks_kosong_menjadi_tuple_kosong():
    # Act / Assert
    assert A.urai_blok("") == ()


def test_urai_blok_membaca_contoh_kanonik():
    # Act / Assert
    assert A.urai_blok("1@480-600;3@900-1020") == ((1, 480, 600), (3, 900, 1020))


@pytest.mark.parametrize(
    "teks",
    [
        "1@0-60",
        "7@1380-1440",
        "1@480-540;1@540-600",
        "2@480-540;2@600-660",
        "1@480-600;3@900-1020;7@1380-1440",
    ],
)
def test_urai_blok_menerima_teks_sah_dan_bolak_balik(teks):
    # Act
    hasil = A.urai_blok(teks)

    # Assert
    assert A.kanonik(hasil) == teks


# --- urai_blok: teks tidak sah ----------------------------------------------------------

@pytest.mark.parametrize("teks", [None, 1, b"1@480-600", ["1@480-600"], ("1@480-600",)])
def test_urai_blok_menolak_bukan_teks(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


def test_urai_blok_menolak_teks_bukan_ascii():
    # Arrange: angka lebar penuh terlihat seperti angka tetapi bukan ASCII
    teks = "１@480-600"

    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


def test_urai_blok_menolak_teks_di_atas_panjang_maksimum():
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok("1" * 201)


@pytest.mark.parametrize(
    "teks",
    [
        "480-600",
        "1-480-600",
        "1@480",
        "1@480-600;",
        ";1@480-600",
        "1@480-600;;3@900-1020",
        "1@ 480-600",
        " 1@480-600",
        "1@480-600 ",
        "a@480-600",
        "1@480-600@",
        "1@480--600",
        "1@+480-600",
        "1@480-600\n",
        "1@480,600",
    ],
)
def test_urai_blok_menolak_format_salah(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize("teks", ["0@480-600", "8@480-600", "10@480-600"])
def test_urai_blok_menolak_hari_di_luar_satu_sampai_tujuh(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize("teks", ["1@485-600", "1@480-595", "1@481-541"])
def test_urai_blok_menolak_jam_bukan_kelipatan_30_menit(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize("teks", ["1@600-480", "1@480-480"])
def test_urai_blok_menolak_selesai_tidak_setelah_mulai(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize("teks", ["1@480-510", "1@0-30"])
def test_urai_blok_menolak_panjang_kurang_dari_60_menit(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize("teks", ["1@1410-1470", "1@1440-1500"])
def test_urai_blok_menolak_selesai_lewat_tengah_malam(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize(
    "teks",
    ["1@480-600;1@540-660", "1@480-600;1@500-520", "1@480-600;1@480-600"],
)
def test_urai_blok_menolak_irisan_dalam_satu_hari(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


def test_urai_blok_menolak_lebih_dari_dua_blok_sehari_walau_bersentuhan():
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok("1@480-540;1@540-600;1@600-660")


def test_urai_blok_menolak_lebih_dari_empat_belas_blok():
    # Arrange: 15 blok; batas sehari juga terlanggar, jadi tes hanya memastikan ValueError
    blok = [f"{hari}@{mulai}-{mulai + 60}" for hari in range(1, 8) for mulai in (480, 600)]
    teks = ";".join(blok + ["7@720-780"])

    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


@pytest.mark.parametrize(
    "teks",
    [
        "3@900-1020;1@480-600",
        "1@480-540;1@480-540",
        "01@480-600",
        "1@0480-0600",
    ],
)
def test_urai_blok_menolak_teks_tidak_kanonik(teks):
    # Act / Assert
    with pytest.raises(ValueError):
        A.urai_blok(teks)


# --- kanonik ----------------------------------------------------------------------------

def test_kanonik_tuple_kosong_menjadi_teks_kosong():
    # Act / Assert
    assert A.kanonik(()) == ""


def test_kanonik_mengurutkan_blok_masukan():
    # Act / Assert
    assert A.kanonik(((3, 900, 1020), (1, 480, 600))) == "1@480-600;3@900-1020"


@pytest.mark.parametrize(
    "blok",
    [
        [(1, 480, 600)],
        ((1, 480, 600, 0),),
        ((1, 480),),
        ((True, 480, 600),),
        ((1, False, 60),),
        ((1, 480.0, 600),),
        ((1, 480, 600.0),),
        ((8, 480, 600),),
        ((0, 480, 600),),
        ((1, -30, 60),),
        ((1, 480, 1470),),
        ((1, 480, 510),),
        ((1, 485, 600),),
        ((1, 480, 540), (1, 500, 600)),
        ((1, 480, 540), (1, 600, 660), (1, 700, 760)),
        ("1@480-600",),
    ],
)
def test_kanonik_menolak_blok_tidak_sah(blok):
    # Act / Assert
    with pytest.raises(ValueError):
        A.kanonik(blok)


@pytest.mark.parametrize(
    "teks",
    ["", "1@480-600", "1@480-600;3@900-1020", "1@0-60;1@60-120", "7@1380-1440"],
)
def test_kanonik_bolak_balik_dengan_urai_blok(teks):
    # Act / Assert
    assert A.kanonik(A.urai_blok(teks)) == teks


def test_sama_blok_membandingkan_teks_kanonik():
    # Act / Assert
    assert A.sama_blok("1@480-600", "1@480-600") is True
    assert A.sama_blok("1@480-600", "1@480-660") is False
    assert A.sama_blok(None, None) is False


# --- blok_dari_form ---------------------------------------------------------------------

def test_blok_dari_form_semua_kosong_menjadi_tuple_kosong():
    # Act / Assert
    assert A.blok_dari_form(_form_kosong()) == ()


def test_blok_dari_form_mengurutkan_blok_otomatis():
    # Arrange
    form = _form_dengan({"h3a_m": "900", "h3a_s": "1020", "h1b_m": "480", "h1b_s": "600"})

    # Act / Assert
    assert A.blok_dari_form(form) == ((1, 480, 600), (3, 900, 1020))


def test_blok_dari_form_blok_b_sebelum_a_tetap_sah():
    # Arrange: blok pertama (a) lebih lambat daripada blok kedua (b)
    form = _form_dengan({"h1a_m": "900", "h1a_s": "1020", "h1b_m": "480", "h1b_s": "600"})

    # Act / Assert
    assert A.blok_dari_form(form) == ((1, 480, 600), (1, 900, 1020))


def test_blok_dari_form_bersentuhan_tepat_diterima():
    # Arrange
    form = _form_dengan({"h1a_m": "480", "h1a_s": "540", "h1b_m": "540", "h1b_s": "600"})

    # Act
    hasil = A.blok_dari_form(form)

    # Assert
    assert A.kanonik(hasil) == "1@480-540;1@540-600"


def test_blok_dari_form_menerima_nol_di_depan_hingga_empat_digit():
    # Arrange
    form = _form_dengan({"h1a_m": "0480", "h1a_s": "0600"})

    # Act / Assert
    assert A.blok_dari_form(form) == ((1, 480, 600),)


def test_blok_dari_form_menolak_field_kurang():
    # Arrange: satu field dibuang dari salinan formulir kosong
    form = {kunci: nilai for kunci, nilai in _form_kosong().items() if kunci != "h7b_s"}

    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(form)


def test_blok_dari_form_menolak_field_lebih():
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan({"h8a_m": ""}))
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan({"h1c_m": ""}))


@pytest.mark.parametrize(
    "isi",
    [
        {"h1a_m": "480"},
        {"h1a_s": "600"},
        {"h5b_s": "1020"},
    ],
)
def test_blok_dari_form_menolak_blok_yang_hanya_separuh_terisi(isi):
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan(isi))


@pytest.mark.parametrize(
    "nilai",
    ["abc", "-60", "480.0", " 480", "4 80", "٤٨٠", "1e3", "00480", "123456"],
)
def test_blok_dari_form_menolak_nilai_bukan_angka_desimal(nilai):
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan({"h1a_m": nilai, "h1a_s": "600"}))


@pytest.mark.parametrize("nilai", [None, 480, ["480"]])
def test_blok_dari_form_menolak_nilai_bukan_teks(nilai):
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan({"h1a_m": nilai, "h1a_s": "600"}))


@pytest.mark.parametrize(
    "isi",
    [
        {"h1a_m": "485", "h1a_s": "600"},
        {"h1a_m": "480", "h1a_s": "510"},
        {"h1a_m": "1440", "h1a_s": "1500"},
        {"h1a_m": "600", "h1a_s": "480"},
    ],
)
def test_blok_dari_form_menolak_jam_di_luar_aturan(isi):
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(_form_dengan(isi))


def test_blok_dari_form_menolak_irisan_antar_blok_sehari():
    # Arrange
    form = _form_dengan({"h1a_m": "480", "h1a_s": "600", "h1b_m": "540", "h1b_s": "660"})

    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(form)


@pytest.mark.parametrize("data", [None, [], [("h1a_m", "480")]])
def test_blok_dari_form_menolak_bukan_dict(data):
    # Act / Assert
    with pytest.raises(ValueError):
        A.blok_dari_form(data)


# --- opsi dan label jam -----------------------------------------------------------------

def test_opsi_mulai_nol_sampai_1410_per_30_menit():
    # Act / Assert
    assert A.opsi_mulai() == tuple(range(0, 1411, 30))


def test_opsi_selesai_30_sampai_1440_per_30_menit():
    # Act / Assert
    assert A.opsi_selesai() == tuple(range(30, 1441, 30))


def test_opsi_menit_nol_sampai_1440_per_30_menit():
    # Act / Assert
    assert A.opsi_menit() == tuple(range(0, 1441, 30))


@pytest.mark.parametrize(
    "menit, label",
    [(0, "00.00"), (480, "08.00"), (510, "08.30"), (1410, "23.30"), (1440, "24.00")],
)
def test_label_menit_format_jam_titik_menit(menit, label):
    # Act / Assert
    assert A.label_menit(menit) == label


@pytest.mark.parametrize("menit", [-30, 1441, True, "480"])
def test_label_menit_menolak_di_luar_rentang_dan_bukan_bilangan(menit):
    # Act / Assert
    with pytest.raises(ValueError):
        A.label_menit(menit)


# --- luar_jam: batas pas dan satu menit di luar -----------------------------------------

@pytest.mark.parametrize(
    "mulai_baku, menit, hasil",
    [
        (BAKU_SENIN_0800_WIB, 60, False),
        (BAKU_SENIN_0900_WIB, 60, False),
        (BAKU_SENIN_0830_WIB, 30, False),
        (BAKU_SENIN_0759_WIB, 60, True),
        (BAKU_SENIN_0901_WIB, 60, True),
        (BAKU_SENIN_0730_WIB, 60, True),
        (BAKU_SENIN_0930_WIB, 60, True),
        (BAKU_SENIN_0800_WIB, 120, False),
        (BAKU_SENIN_0800_WIB, 121, True),
        (BAKU_SENIN_0700_WIB, 60, True),
    ],
)
def test_luar_jam_batas_pas_dan_satu_menit_di_luar(mulai_baku, menit, hasil):
    # Act / Assert
    assert A.luar_jam(BLOK_PAGI_SENIN, mulai_baku, menit) is hasil


# --- luar_jam: tengah malam, hari, UTC vs WIB -------------------------------------------

@pytest.mark.parametrize(
    "mulai_baku, menit, hasil",
    [
        (BAKU_SENIN_2300_WIB, 60, False),
        (BAKU_SENIN_2330_WIB, 30, False),
        (BAKU_SENIN_2330_WIB, 60, True),
    ],
)
def test_luar_jam_pertemuan_lewat_tengah_malam_wib_selalu_di_luar(mulai_baku, menit, hasil):
    # Act / Assert
    assert A.luar_jam(BLOK_MALAM_SENIN, mulai_baku, menit) is hasil


def test_luar_jam_membedakan_jam_utc_dari_jam_wib():
    # Arrange: 01.00 UTC adalah 08.00 WIB, jadi di luar blok 01.00-02.00 WIB
    # Act / Assert
    assert A.luar_jam(BLOK_DINI_SENIN, BAKU_SENIN_0800_WIB, 60) is True


def test_luar_jam_mengubah_hari_ke_hari_wib_bukan_utc():
    # Arrange: 18.00 UTC Senin = 01.00 WIB Selasa, jadi masuk blok Selasa 01.00-02.00
    blok_selasa = ((2, 60, 120),)

    # Act / Assert
    assert A.luar_jam(blok_selasa, BAKU_SELASA_0100_WIB, 60) is False
    assert A.luar_jam(BLOK_MALAM_SENIN, BAKU_SELASA_0100_WIB, 60) is True


def test_luar_jam_hari_berbeda_di_luar_jam():
    # Act / Assert
    assert A.luar_jam(BLOK_PAGI_SENIN, BAKU_SELASA_0800_WIB, 60) is True


# --- luar_jam: beberapa blok sehari -----------------------------------------------------

@pytest.mark.parametrize(
    "mulai_baku, hasil",
    [
        (BAKU_SENIN_0800_WIB, False),
        (BAKU_SENIN_0900_WIB, True),
        (BAKU_SENIN_1000_WIB, False),
    ],
)
def test_luar_jam_dua_blok_sehari_jeda_di_luar_jam(mulai_baku, hasil):
    # Act / Assert
    assert A.luar_jam(BLOK_DUA_SENIN, mulai_baku, 60) is hasil


def test_luar_jam_pertemuan_yang_melintasi_dua_blok_bersentuhan_di_luar_jam():
    # Arrange: 08.30-09.30 menyentuh dua blok (08.00-09.00 tidak; 08.00-09.00 + 09.00-10.00 bersentuhan).
    # Aturan: seluruh pertemuan harus berada dalam SATU blok.
    # Act / Assert
    assert A.luar_jam(BLOK_BERSENTUHAN_SENIN, BAKU_SENIN_0830_WIB, 60) is True


def test_luar_jam_blok_kosong_semua_pertemuan_di_luar_jam():
    # Act / Assert
    assert A.luar_jam((), BAKU_SENIN_0800_WIB, 60) is True


# --- luar_jam: masukan tidak sah --------------------------------------------------------

@pytest.mark.parametrize("menit", [0, -60, True, "60", 60.0])
def test_luar_jam_menolak_durasi_bukan_bilangan_bulat_minimal_satu(menit):
    # Act / Assert
    with pytest.raises(ValueError):
        A.luar_jam(BLOK_PAGI_SENIN, BAKU_SENIN_0800_WIB, menit)


@pytest.mark.parametrize("mulai_baku", [None, "2026-11-30 01:00:00", "2026-11-30", PENANDA_TIDAK_BOLEH_MUNCUL])
def test_luar_jam_menolak_waktu_mulai_yang_bukan_format_baku(mulai_baku):
    # Act / Assert
    with pytest.raises(ValueError):
        A.luar_jam(BLOK_PAGI_SENIN, mulai_baku, 60)


def test_luar_jam_menolak_blok_yang_bukan_tuple():
    # Act / Assert
    with pytest.raises(ValueError):
        A.luar_jam([(1, 480, 600)], BAKU_SENIN_0800_WIB, 60)


# --- pesan galat tidak menggemakan isian -------------------------------------------------

@pytest.mark.parametrize(
    "panggilan",
    [
        lambda: A.urai_blok(PENANDA_TIDAK_BOLEH_MUNCUL),
        lambda: A.urai_blok(f"1@480-600;{PENANDA_TIDAK_BOLEH_MUNCUL}"),
        lambda: A.blok_dari_form(_form_dengan({"h1a_m": PENANDA_TIDAK_BOLEH_MUNCUL, "h1a_s": "600"})),
        lambda: A.luar_jam(BLOK_PAGI_SENIN, PENANDA_TIDAK_BOLEH_MUNCUL, 60),
        lambda: A.label_menit(PENANDA_TIDAK_BOLEH_MUNCUL),
    ],
)
def test_pesan_galat_tidak_menggemakan_isian(panggilan):
    # Act
    with pytest.raises(ValueError) as galat:
        panggilan()

    # Assert
    assert PENANDA_TIDAK_BOLEH_MUNCUL not in str(galat.value)
