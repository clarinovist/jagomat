"""Aturan murni jurnal dan kehadiran pertemuan guru: batas waktu, antrean, topik, kunci (tanpa I/O)."""

import pytest

import guru_pertemuan_aturan as A
import topics

ID_KLP = "klp_" + "a" * 32
ID_KOR = "kor_" + "b" * 32
MULAI = "2026-11-10T10:00:00"
MENIT = 60
SELESAI = "2026-11-10T11:00:00"
SEBELUM_MULAI = "2026-11-10T09:59:59"
TEPAT_MULAI = "2026-11-10T10:00:00"
SESUDAH_MULAI = "2026-11-10T10:00:01"
SATU_DETIK_SEBELUM_TERKUNCI = "2026-11-17T10:59:59"
TEPAT_TERKUNCI = "2026-11-17T11:00:00"
SATU_DETIK_SEBELUM_TERLAMBAT = "2026-11-11T10:59:59"
TEPAT_TERLAMBAT = "2026-11-11T11:00:00"
SATU_DETIK_SEBELUM_RIWAYAT = "2026-11-17T10:59:59"
TEPAT_RIWAYAT = "2026-11-17T11:00:00"


# --- kunci_pertemuan -----------------------------------------------------------------

def test_kunci_pertemuan_klp_membentuk_kunci_tiga_puluh_delapan_karakter():
    # Arrange / Act
    kunci = A.kunci_pertemuan(ID_KLP, 3)

    # Assert
    assert kunci == ID_KLP + ":3"
    assert len(kunci) == 38


def test_kunci_pertemuan_kor_diterima():
    # Arrange / Act
    kunci = A.kunci_pertemuan(ID_KOR, 8)

    # Assert
    assert kunci == ID_KOR + ":8"


@pytest.mark.parametrize("ke", [1, 8])
def test_kunci_pertemuan_menerima_batas_ke_satu_dan_delapan(ke):
    # Arrange / Act
    kunci = A.kunci_pertemuan(ID_KLP, ke)

    # Assert
    assert kunci.endswith(":" + str(ke))


@pytest.mark.parametrize("ke", [0, 9, -1, True, "2", 2.0])
def test_kunci_pertemuan_menolak_ke_di_luar_satu_sampai_delapan(ke):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        A.kunci_pertemuan(ID_KLP, ke)


@pytest.mark.parametrize(
    "id_awal",
    [
        "klp_" + "A" * 32,
        "klp_" + "a" * 31,
        "abc_" + "a" * 32,
        "akun_" + "a" * 32,
        "klp_" + "a" * 32 + "\n",
        None,
    ],
)
def test_kunci_pertemuan_menolak_id_awal_tidak_sah(id_awal):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        A.kunci_pertemuan(id_awal, 1)


def test_kunci_sah_menerima_kunci_bentuk_kanonik_dan_menolak_sisanya():
    # Arrange
    sah = ID_KLP + ":1"

    # Act / Assert
    assert A.kunci_sah(sah) is True
    assert A.kunci_sah(ID_KLP + ":9") is False
    assert A.kunci_sah(ID_KLP + "1") is False
    assert A.kunci_sah(sah + "\n") is False
    assert A.kunci_sah(None) is False


# --- selesai dan waktu ------------------------------------------------------------------

def test_selesai_menambah_menit_ke_mulai_dalam_format_baku():
    # Arrange / Act
    hasil = A.selesai(MULAI, MENIT)

    # Assert
    assert hasil == SELESAI


@pytest.mark.parametrize("menit", [0, -5, True, 1.5, "60"])
def test_selesai_menolak_menit_tidak_positif_bulat(menit):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        A.selesai(MULAI, menit)


@pytest.mark.parametrize(
    "waktu",
    ["2026-1-5T10:00:00", "2026-11-10 10:00:00", "2026-13-01T10:00:00", "2026-11-10T10:00:00Z", None],
)
def test_selesai_menolak_waktu_tidak_baku(waktu):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        A.selesai(waktu, MENIT)


def test_waktu_sah_hanya_menerima_format_baku_padat():
    # Act / Assert
    assert A.waktu_sah(MULAI) is True
    assert A.waktu_sah("2026-11-10T10:00:00 ") is False
    assert A.waktu_sah("2026-02-30T10:00:00") is False


def test_order_id_sah_hanya_kor_dengan_tiga_puluh_dua_hex():
    # Act / Assert
    assert A.order_id_sah(ID_KOR) is True
    assert A.order_id_sah(ID_KLP) is False
    assert A.order_id_sah("kor_" + "B" * 32) is False


# --- boleh_catat -------------------------------------------------------------------------

def test_boleh_catat_menolak_pertemuan_dibatalkan():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, True, SESUDAH_MULAI)

    # Assert
    assert alasan == A.ALASAN_DIBATALKAN


def test_boleh_catat_dibatalkan_didahulukan_di_atas_belum_mulai():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, True, SEBELUM_MULAI)

    # Assert
    assert alasan == A.ALASAN_DIBATALKAN


def test_boleh_catat_menolak_satu_detik_sebelum_mulai():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, False, SEBELUM_MULAI)

    # Assert
    assert alasan == A.ALASAN_BELUM_MULAI


def test_boleh_catat_tepat_di_detik_mulai_sudah_boleh():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, False, TEPAT_MULAI)

    # Assert
    assert alasan is None


def test_boleh_catat_satu_detik_sebelum_batas_terkunci_masih_boleh():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, False, SATU_DETIK_SEBELUM_TERKUNCI)

    # Assert
    assert alasan is None


def test_boleh_catat_tepat_tujuh_hari_sesudah_selesai_terkunci():
    # Arrange / Act
    alasan = A.boleh_catat(MULAI, MENIT, False, TEPAT_TERKUNCI)

    # Assert
    assert alasan == A.ALASAN_TERKUNCI


# --- status_antrean ----------------------------------------------------------------------

def test_status_antrean_dibatalkan_selalu_tidak():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, True, TEPAT_RIWAYAT)

    # Assert
    assert status == "tidak"


def test_status_antrean_belum_saat_sebelum_mulai():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, False, SEBELUM_MULAI)

    # Assert
    assert status == "belum"


def test_status_antrean_satu_detik_sebelum_jeda_terlambat_masih_belum():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, False, SATU_DETIK_SEBELUM_TERLAMBAT)

    # Assert
    assert status == "belum"


def test_status_antrean_tepat_jeda_terlambat_menjadi_aksi():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, False, TEPAT_TERLAMBAT)

    # Assert
    assert status == "aksi"


def test_status_antrean_satu_detik_sebelum_jendela_habis_masih_aksi():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, False, SATU_DETIK_SEBELUM_RIWAYAT)

    # Assert
    assert status == "aksi"


def test_status_antrean_tepat_tujuh_hari_sesudah_selesai_menjadi_riwayat():
    # Arrange / Act
    status = A.status_antrean(MULAI, MENIT, False, TEPAT_RIWAYAT)

    # Assert
    assert status == "riwayat"


# --- wajib_aktif -------------------------------------------------------------------------

def test_wajib_aktif_false_saat_konstanta_none(monkeypatch):
    # Arrange
    monkeypatch.setattr(A, "PERTEMUAN_WAJIB_SEJAK", None)

    # Act / Assert
    assert A.wajib_aktif(MULAI) is False


@pytest.mark.parametrize(
    ("mulai", "hasil"),
    [
        ("2026-11-10T09:59:59", False),
        ("2026-11-10T10:00:00", True),
        ("2026-11-10T10:00:01", True),
    ],
)
def test_wajib_aktif_membandingkan_terhadap_cutoff_saat_dipanggil(monkeypatch, mulai, hasil):
    # Arrange
    monkeypatch.setattr(A, "PERTEMUAN_WAJIB_SEJAK", "2026-11-10T10:00:00")

    # Act / Assert
    assert A.wajib_aktif(mulai) is hasil


# --- anggota_masuk_form ------------------------------------------------------------------

@pytest.mark.parametrize(
    ("dibuat", "hasil"),
    [
        ("2026-11-10T09:59:59", True),
        ("2026-11-10T10:00:00", True),
        ("2026-11-10T10:00:01", False),
    ],
)
def test_anggota_masuk_form_batas_penempatan_dibuat(dibuat, hasil):
    # Arrange / Act / Assert
    assert A.anggota_masuk_form(dibuat, MULAI) is hasil


# --- topik jurnal ------------------------------------------------------------------------

def test_daftar_topik_jurnal_tanpa_campuran_dan_berakhir_lainnya():
    # Arrange / Act
    daftar = A.daftar_topik_jurnal()

    # Assert
    assert "campuran" not in daftar
    assert daftar[-1] == "lainnya"
    assert "pola-bilangan" in daftar


def test_daftar_topik_jurnal_mengikuti_urutan_topics_lalu_lainnya():
    # Arrange
    diharapkan = [t for t in topics.daftar_topik() if t != "campuran"] + ["lainnya"]

    # Act
    daftar = A.daftar_topik_jurnal()

    # Assert
    assert daftar == diharapkan


def test_daftar_topik_jurnal_mengembalikan_salinan_baru_setiap_panggilan():
    # Arrange
    daftar = A.daftar_topik_jurnal()

    # Act
    daftar.append("sembarang")

    # Assert
    assert "sembarang" not in A.daftar_topik_jurnal()


def test_topik_sah_menerima_topik_terdaftar_dan_lainnya():
    # Act / Assert
    assert A.topik_sah("pola-bilangan") is True
    assert A.topik_sah("lainnya") is True


@pytest.mark.parametrize("nilai", ["campuran", "topik-asing", "", None, 7, ["pola-bilangan"]])
def test_topik_sah_menolak_campuran_asing_dan_non_teks(nilai):
    # Act / Assert
    assert A.topik_sah(nilai) is False


def test_label_topik_memakai_nama_tampil_dari_modul_topik():
    # Arrange
    nama = topics.ambil("pola-bilangan").nama

    # Act
    label = A.label_topik("pola-bilangan")

    # Assert
    assert label == nama
    assert label != "pola-bilangan"


def test_label_topik_lainnya_menjadi_topik_lain():
    # Act / Assert
    assert A.label_topik("lainnya") == "Topik lain"


def test_label_topik_id_tak_dikenal_dikembalikan_apa_adanya():
    # Act / Assert
    assert A.label_topik("topik-hilang") == "topik-hilang"


def test_label_topik_menolak_nilai_non_teks():
    # Act / Assert
    with pytest.raises(ValueError):
        A.label_topik(None)


# --- status_sah --------------------------------------------------------------------------

@pytest.mark.parametrize("nilai", ["hadir", "izin", "tidak_hadir"])
def test_status_sah_menerima_tiga_status_kehadiran(nilai):
    # Act / Assert
    assert A.status_sah(nilai) is True


@pytest.mark.parametrize("nilai", ["Hadir", "sakit", "", None, 1])
def test_status_sah_menolak_nilai_di_luar_daftar(nilai):
    # Act / Assert
    assert A.status_sah(nilai) is False
