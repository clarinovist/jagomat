"""Tes CLI ringkasan tunggakan admin: hanya agregat, DB baca-saja, kode keluar, dan satu baris keluaran.

Data sintetis dari kit kelas (`db_kelas`); transport palsu; `isolasi_surel` menjamin tanpa jaringan.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

import pytest

import kelas_kit as kk
import kelas_tunggakan as kt
import pesanan
import surel_tunggakan_admin as sta
from kelas_kit import db_kelas  # noqa: F401
from pesanan_kit import AKUN_A
from surel_kit import ALAMAT_SINTETIS_ADMIN, KUNCI_SINTETIS, TransportPalsu, isolasi_surel  # noqa: F401

pytestmark = pytest.mark.usefixtures("isolasi_surel")

FORMAT = "%Y-%m-%dT%H:%M:%S"
SISWA = 4711
NAMA_ANAK_SINTETIS = "Anak Sintetis Rafi"
ENV_SEHAT = {"SUREL_ADMIN": ALAMAT_SINTETIS_ADMIN, "RESEND_API_KEY": KUNCI_SINTETIS}
DAFTAR_CONTOH = (
    kt.Tunggakan(4711, "mini", "Mini", "2026-12-20T09:00:00", 35),
    kt.Tunggakan(4712, "private", "Private", "2026-10-01T09:00:00", 75),
    kt.Tunggakan(4713, "mini", "Mini", "2026-12-01T09:00:00", 59),
)


def _lewat(waktu, hari=0):
    return (datetime.strptime(waktu, FORMAT) + timedelta(days=hari)).strftime(FORMAT)


def _siapkan_tunggakan(path, siswa=SISWA, paket="mini"):
    """Satu paket lunas yang sudah 35 hari lewat dari akhir aksesnya; mengembalikan waktu uji (UTC naif)."""
    with pesanan.buka(path, tulis_data=True) as kon:
        kk.lunas(kon, siswa, paket, sekarang=kk.KINI, putus=kk.SESUDAH_UPLOAD)
        (berakhir,) = kon.execute(
            "SELECT MAX(a.berakhir) FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
            "WHERE a.siswa_id=? AND o.paket=?", (siswa, paket)).fetchone()
    return _lewat(berakhir, hari=35)


def _jalankan(path, *, sekarang, transport, env=ENV_SEHAT):
    return sta.main(["--database", str(path)], sekarang=sekarang, transport=transport, env=env)


def _hash_berkas(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- kode keluar dan jumlah pengiriman ----------------------------------------------------------

def test_tanpa_tunggakan_keluar_nol_dan_tidak_mengirim(db_kelas, capsys):
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang="2027-01-24T09:00:00", transport=transport)

    assert kode == 0
    assert transport.panggilan == []
    assert capsys.readouterr().out == "surel tunggakan: tidak ada tunggakan, tidak ada yang dikirim\n"


def test_ada_tunggakan_kirim_tepat_satu_email_berisi_agregat(db_kelas, capsys):
    sekarang = _siapkan_tunggakan(db_kelas)
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=transport)

    assert kode == 0
    (panggilan,) = transport.panggilan
    muatan = json.loads(panggilan["badan"])
    assert muatan["to"] == [ALAMAT_SINTETIS_ADMIN]
    assert "Mini" in muatan["text"]
    assert "https://jagomat.id/admin" in muatan["text"]
    assert capsys.readouterr().out == "surel tunggakan: terkirim, 1 tunggakan\n"


def test_isi_email_tidak_memuat_id_anak_akun_nama_atau_tanggal_berakhir(db_kelas):
    # Tabel kelas tidak menyimpan nama anak; sentinel ini menjaga agar regresi tidak memasukkannya.
    sekarang = _siapkan_tunggakan(db_kelas)
    transport = TransportPalsu()

    _jalankan(db_kelas, sekarang=sekarang, transport=transport)

    muatan = json.loads(transport.panggilan[0]["badan"])
    berakhir = _lewat(sekarang, hari=-35)
    terlarang = (str(SISWA), AKUN_A, NAMA_ANAK_SINTETIS, berakhir[:10])
    for isi in (muatan["subject"], muatan["text"]):
        for data in terlarang:
            assert data not in isi


# --- kunci idempotensi berdasar tanggal WIB -----------------------------------------------------

@pytest.mark.parametrize("sekarang,harapan", [
    ("2027-01-24T16:59:59", "tunggakan-kelas-2027-01-24"),
    ("2027-01-24T17:00:00", "tunggakan-kelas-2027-01-25"),
    ("2026-12-31T17:00:00", "tunggakan-kelas-2027-01-01"),
])
def test_kunci_idempotensi_dari_tanggal_wib(sekarang, harapan):
    assert sta.kunci_idempotensi(sekarang) == harapan


@pytest.mark.parametrize("jam_utc,selisih_hari", [("16:59:59", 0), ("17:00:00", 1)])
def test_header_idempotensi_mengikuti_tanggal_wib_dari_sekarang(db_kelas, jam_utc, selisih_hari):
    dasar = _siapkan_tunggakan(db_kelas)
    tanggal_utc = dasar[:10]
    transport = TransportPalsu()

    _jalankan(db_kelas, sekarang="%sT%s" % (tanggal_utc, jam_utc), transport=transport)

    tanggal_wib = (datetime.strptime(tanggal_utc, "%Y-%m-%d") + timedelta(days=selisih_hari)).strftime("%Y-%m-%d")
    assert transport.panggilan[0]["headers"]["Idempotency-Key"] == "tunggakan-kelas-" + tanggal_wib


# --- konfigurasi, galat kirim, dan database gagal tertutup --------------------------------------

@pytest.mark.parametrize("env", [
    {"SUREL_ADMIN": "", "RESEND_API_KEY": KUNCI_SINTETIS},
    {"SUREL_ADMIN": ALAMAT_SINTETIS_ADMIN, "RESEND_API_KEY": ""},
    {"RESEND_API_KEY": KUNCI_SINTETIS},
])
def test_konfigurasi_belum_diatur_keluar_dua_tanpa_mengirim(db_kelas, capsys, env):
    sekarang = _siapkan_tunggakan(db_kelas)
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=transport, env=env)

    keluaran = capsys.readouterr().out
    assert kode == 2
    assert transport.panggilan == []
    assert keluaran.count("\n") == 1
    assert "ditahan" in keluaran


def test_konfigurasi_dicek_sebelum_db_walau_tanpa_tunggakan(db_kelas):
    # Urutan yang dikunci: konfigurasi kosong keluar 2 walau tabel kelas kosong (tanpa tunggakan).
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang="2027-01-24T09:00:00", transport=transport,
                     env={"RESEND_API_KEY": KUNCI_SINTETIS})

    assert kode == 2
    assert transport.panggilan == []


@pytest.mark.parametrize("alamat", [
    "admin@contoh.test, lain@contoh.test", "bukan-alamat", "<admin@contoh.test>",
])
def test_alamat_admin_tidak_sah_keluar_dua_tanpa_mengirim(db_kelas, alamat):
    sekarang = _siapkan_tunggakan(db_kelas)
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=transport,
                     env={"SUREL_ADMIN": alamat, "RESEND_API_KEY": KUNCI_SINTETIS})

    assert kode == 2
    assert transport.panggilan == []


def test_kirim_gagal_keluar_satu_dengan_satu_baris(db_kelas, capsys):
    sekarang = _siapkan_tunggakan(db_kelas)
    transport = TransportPalsu(kode=500, badan=b"{}")

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=transport)

    keluaran = capsys.readouterr().out
    assert kode == 1
    assert len(transport.panggilan) == 1
    assert keluaran == "surel tunggakan: gagal, layanan galat (kode 500)\n"


def test_database_tidak_ada_keluar_dua_tanpa_traceback(tmp_path, capsys):
    transport = TransportPalsu()

    kode = _jalankan(tmp_path / "tidak-ada.db", sekarang="2027-01-24T09:00:00", transport=transport)

    keluaran = capsys.readouterr()
    assert kode == 2
    assert transport.panggilan == []
    assert "Traceback" not in keluaran.out + keluaran.err
    assert keluaran.out.count("\n") == 1


def test_tabel_kelas_belum_ada_keluar_dua(tmp_path, capsys):
    path = tmp_path / "admin-tanpa-kelas.db"
    with closing(sqlite3.connect(str(path))) as kon:
        kon.execute("CREATE TABLE lain (x INTEGER)")
        kon.commit()
    transport = TransportPalsu()

    kode = _jalankan(path, sekarang="2027-01-24T09:00:00", transport=transport)

    assert kode == 2
    assert transport.panggilan == []
    assert "Traceback" not in capsys.readouterr().out


def test_tabel_kelas_parsial_keluar_dua(db_kelas):
    with closing(sqlite3.connect(str(db_kelas))) as kon:
        kon.execute("DROP TABLE kelas_verifikasi")
        kon.commit()
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang="2027-01-24T09:00:00", transport=transport)

    assert kode == 2
    assert transport.panggilan == []


# --- baca-saja ----------------------------------------------------------------------------------

def test_database_dibuka_baca_saja_dan_tidak_berubah(db_kelas):
    sekarang = _siapkan_tunggakan(db_kelas)
    sebelum = _hash_berkas(db_kelas)
    transport = TransportPalsu()

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=transport)

    assert kode == 0
    assert _hash_berkas(db_kelas) == sebelum
    with closing(sta.buka_baca_saja(db_kelas)) as kon:
        with pytest.raises(sqlite3.OperationalError):
            kon.execute("CREATE TABLE uji_tulis (x INTEGER)")


def test_main_menulis_lewat_koneksinya_gagal(db_kelas, monkeypatch):
    sekarang = _siapkan_tunggakan(db_kelas)
    tulisan_gagal = []
    asli = kt.daftar_tunggakan

    def daftar_dengan_uji_tulis(kon, waktu):
        try:
            kon.execute("CREATE TABLE uji_tulis (x INTEGER)")
        except sqlite3.OperationalError as galat:
            tulisan_gagal.append(galat)
        return asli(kon, waktu)

    monkeypatch.setattr(kt, "daftar_tunggakan", daftar_dengan_uji_tulis)

    kode = _jalankan(db_kelas, sekarang=sekarang, transport=TransportPalsu())

    assert kode == 0
    assert len(tulisan_gagal) == 1


# --- ringkasan (fungsi murni) -------------------------------------------------------------------

def test_ringkasan_kosong_menghasilkan_none():
    assert sta.susun_ringkasan(()) is None


def test_ringkasan_berisi_total_per_paket_dan_rentang_hari():
    subjek, teks = sta.susun_ringkasan(DAFTAR_CONTOH)

    assert "3 tunggakan" in subjek
    assert "Total: 3 tunggakan" in teks
    assert "- Mini: 2" in teks
    assert "- Private: 1" in teks
    assert "- 30 sampai 59 hari: 2" in teks
    assert "- 60 hari atau lebih: 1" in teks
    assert "https://jagomat.id/admin" in teks


def test_ringkasan_tidak_memuat_data_anak_atau_tanggal():
    subjek, teks = sta.susun_ringkasan(DAFTAR_CONTOH)

    for data in ("4711", "4712", "4713", "2026-12-20", "2026-10-01", "2026-12-01"):
        assert data not in subjek
        assert data not in teks


def test_ringkasan_memakai_batas_hari_dari_kelas_tunggakan():
    _, teks_penting = sta.susun_ringkasan((kt.Tunggakan(1, "mini", "Mini", "x", kt.HARI_TUNGGAKAN_PENTING),))
    _, teks_sedang = sta.susun_ringkasan((kt.Tunggakan(1, "mini", "Mini", "x", kt.HARI_TUNGGAKAN_PENTING - 1),))

    assert "- 60 hari atau lebih: 1" in teks_penting
    assert "- 30 sampai 59 hari: 1" in teks_sedang
