"""Pembaca "Sesi berikutnya" anak (`jadwal_anak_baca`): hanya SELECT, tanpa lokasi, tautan, atau id di hasil.

Data sintetis di DB admin sementara. Order dibuat lewat kelas_kit, penempatan lewat jadwal_store, dan `kini`
disuntik langsung ke pembaca. Pemilihan order meniru jadwal_terbaru_murid: order AKTIF terbaru milik (akun, anak)
yang berpenempatan.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import jadwal_anak_baca as baca
import jadwal_store as js
import kelas_batal
import kelas_kit
import kelas_putusan
import schema_jadwal
import schema_tagihan_catatan
from pesanan_kit import AKUN_A, AKUN_B

ADMIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
GURU_B = "akun_" + "8" * 32
FORMAT = "%Y-%m-%dT%H:%M:%S"
KINI = kelas_kit.KINI                       # 2026-11-20T09:00:00 UTC
SEKARANG = kelas_kit.SESUDAH_UPLOAD         # tempat penempatan (sesudah order aktif)
TANGGAL_MINI = "2026-11-21"                 # 09.00 WIB = 02.00 UTC
KEDALUWARSA_KINI = "2026-11-25T00:00:00"    # jauh sesudah kedaluwarsa tagihan yang dibuat pada KINI
BARU_SEKARANG = "2026-11-20T10:00:00"
BARU_PUTUS = "2026-11-20T10:30:00"
KUNCI_HASIL = {"guru_id", "ke", "mulai", "menit", "berlangsung"}


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)   # pembatalan tagihan butuh tabel catatan (kelas_batal)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _kelompok(kon, *, guru=GURU, nama="Mini A"):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=guru, kuota=5,
                            tanggal=TANGGAL_MINI, jam="09:00", sekarang=KINI)


def _mini(kon, order_id, kid, sekarang=SEKARANG):
    return js.tempatkan(kon, ADMIN, order_id, kelompok_id=kid, sekarang=sekarang)


def _privat(kon, order_id, guru=GURU):
    return js.tempatkan(kon, ADMIN, order_id, guru_id=guru, tanggal="2026-11-23", jam="16:30", sekarang=SEKARANG)


def _pertemuan(kon, *, kelompok_id=None, order_id=None):
    """Baris pertemuan dibaca langsung dari tabel (bukan lewat pembaca yang diuji), urut mulai lalu id."""
    kolom, nilai = ("kelompok_id", kelompok_id) if kelompok_id is not None else ("order_id", order_id)
    return [dict(b) for b in kon.execute(
        "SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan WHERE %s=? ORDER BY mulai,id" % kolom, (nilai,))]


def _tambah_menit(waktu: str, menit: int) -> str:
    return (datetime.strptime(waktu, FORMAT) + timedelta(minutes=menit)).strftime(FORMAT)


def _selesai(sesi: dict) -> str:
    return _tambah_menit(sesi["mulai"], sesi["menit"])


def _baca(kon, *, akun=AKUN_A, siswa=1, kini=KINI):
    return baca.sesi_berikutnya_murid(kon, akun, siswa, kini)


def _hash_berkas(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _belum_bayar(kon):
    return kelas_kit.tagih(kon, 1, "mini").order_id


def _menunggu(kon):
    tagihan, _bukti = kelas_kit.menunggu(kon, 1, "mini")
    return tagihan.order_id


def _ditolak(kon):
    tagihan, bukti = kelas_kit.menunggu(kon, 1, "mini")
    kelas_putusan.tolak(kon, tagihan.order_id, kelas_kit.ADMIN, "Bukti tidak terbaca.", SEKARANG,
                        bukti_dilihat=bukti)
    return tagihan.order_id


def _dibatalkan(kon):
    order_id = kelas_kit.tagih(kon, 1, "mini").order_id
    kelas_batal.batalkan_tagihan(kon, AKUN_A, 1, "mini", KINI)
    return order_id


def _sisip_penempatan(kon, order_id, kid):
    """Penempatan mentah melewati guard store: trigger skema hanya menjaga paket dan anak, bukan status order."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,dibuat,diubah,dibuat_oleh,diubah_oleh) "
                "VALUES(?,?,?,?,?,?)", (order_id, kid, KINI, KINI, ADMIN, ADMIN))


# --- sesi berikutnya dan status pertemuan ----------------------------------------------------------

def test_mini_sebelum_sesi_pertama_memilih_pertemuan_pertama(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama = _pertemuan(kon, kelompok_id=kid)[0]
    assert _baca(kon) == {"guru_id": GURU, "ke": 1, "mulai": pertama["mulai"], "menit": pertama["menit"],
                          "berlangsung": False}


def test_sedang_berlangsung_ditandai_dan_tetap_sesi_berikutnya(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama = _pertemuan(kon, kelompok_id=kid)[0]
    hasil = _baca(kon, kini=_tambah_menit(pertama["mulai"], 30))
    assert hasil["ke"] == 1 and hasil["berlangsung"] is True


def test_mulai_tepat_pada_kini_dihitung_berlangsung(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama = _pertemuan(kon, kelompok_id=kid)[0]
    assert _baca(kon, kini=pertama["mulai"])["berlangsung"] is True


def test_selesai_tepat_pada_kini_sudah_lewat_dan_sebelumnya_masih_berlangsung(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama, kedua = _pertemuan(kon, kelompok_id=kid)[:2]
    sisa_satu_menit = _tambah_menit(_selesai(pertama), -1)
    assert _baca(kon, kini=sisa_satu_menit)["ke"] == 1
    hasil = _baca(kon, kini=_selesai(pertama))
    assert hasil["ke"] == 2 and hasil["mulai"] == kedua["mulai"] and hasil["berlangsung"] is False


def test_pertemuan_dibatalkan_dilewati(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama = _pertemuan(kon, kelompok_id=kid)[0]
    js.batalkan_pertemuan(kon, ADMIN, pertama["id"], batal=True, sekarang=KINI)
    assert _baca(kon)["ke"] == 2


def test_semua_pertemuan_lampau_tanpa_sesi_berikutnya(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    terakhir = _pertemuan(kon, kelompok_id=kid)[-1]
    assert _baca(kon, kini=_selesai(terakhir)) is None


def test_private_memakai_sesi_order_dan_guru_penempatan(kon):
    order = kelas_kit.lunas(kon, 1, "private", n=1)
    _privat(kon, order.order_id, guru=GURU_B)
    pertama = _pertemuan(kon, order_id=order.order_id)[0]
    hasil = _baca(kon)
    assert set(hasil) == KUNCI_HASIL
    assert hasil["guru_id"] == GURU_B and hasil["ke"] == 1 and hasil["mulai"] == pertama["mulai"]


def test_mini_mengambil_guru_dari_kelompok(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, order.order_id, _kelompok(kon, guru=GURU_B))
    assert _baca(kon)["guru_id"] == GURU_B


def test_tanpa_penempatan_tanpa_sesi_berikutnya(kon):
    kelas_kit.lunas(kon, 1, "mini", n=1)
    assert _baca(kon) is None


# --- order yang belum aktif tidak pernah terbaca ---------------------------------------------------

@pytest.mark.parametrize("siapkan", [_belum_bayar, _menunggu, _ditolak, _dibatalkan])
def test_order_belum_aktif_tidak_terbaca_walau_berpenempatan_mentah(kon, siapkan):
    order_id = siapkan(kon)
    _sisip_penempatan(kon, order_id, _kelompok(kon))
    assert _baca(kon) is None


def test_order_kedaluwarsa_tidak_terbaca_walau_berpenempatan_mentah(kon):
    order_id = _belum_bayar(kon)
    _sisip_penempatan(kon, order_id, _kelompok(kon))
    assert _baca(kon, kini=KEDALUWARSA_KINI) is None


# --- pemilihan order dan isolasi anak/akun ---------------------------------------------------------

def test_anak_dan_akun_lain_tidak_terbaca_walau_order_lain_lebih_baru(kon):
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, _kelompok(kon, guru=GURU, nama="Mini A"))
    baru = kelas_kit.lunas(kon, 2, "mini", n=2, sekarang=BARU_SEKARANG, putus=BARU_PUTUS)
    _mini(kon, baru.order_id, _kelompok(kon, guru=GURU_B, nama="Mini B"), sekarang=BARU_PUTUS)
    assert _baca(kon, siswa=1)["guru_id"] == GURU
    assert _baca(kon, siswa=2)["guru_id"] == GURU_B
    assert _baca(kon, akun=AKUN_B, siswa=1) is None
    assert _baca(kon, akun=AKUN_B, siswa=2) is None


def test_order_aktif_berpenempatan_dipilih_walau_order_lebih_baru_belum_ditempatkan(kon):
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, _kelompok(kon, guru=GURU))
    kelas_kit.lunas(kon, 1, "mini", n=2, sekarang=BARU_SEKARANG, putus=BARU_PUTUS)
    assert _baca(kon)["guru_id"] == GURU


def test_order_aktif_lama_tanpa_penempatan_dilewati_demi_yang_berpenempatan(kon):
    kelas_kit.lunas(kon, 1, "mini", n=1)
    baru = kelas_kit.lunas(kon, 1, "mini", n=2, sekarang=BARU_SEKARANG, putus=BARU_PUTUS)
    _mini(kon, baru.order_id, _kelompok(kon, guru=GURU_B), sekarang=BARU_PUTUS)
    assert _baca(kon)["guru_id"] == GURU_B


# --- validasi dan kontrak baca-saja ----------------------------------------------------------------

@pytest.mark.parametrize("akun, siswa", [("bukan-akun", 1), (AKUN_A, 0), (AKUN_A, "1")])
def test_argumen_tidak_sah_ditolak(kon, akun, siswa):
    with pytest.raises(ValueError):
        _baca(kon, akun=akun, siswa=siswa)


def test_kini_berupa_datetime_dinormalisasi(kon):
    order = kelas_kit.lunas(kon, 1, "mini", n=1)
    kid = _kelompok(kon)
    _mini(kon, order.order_id, kid)
    pertama = _pertemuan(kon, kelompok_id=kid)[0]
    hasil = _baca(kon, kini=datetime.strptime(pertama["mulai"], FORMAT))
    assert hasil["ke"] == 1 and hasil["berlangsung"] is True


def test_baca_tidak_mengubah_berkas_admin(db):
    with js.buka(db, tulis_data=True) as kon:
        order = kelas_kit.lunas(kon, 1, "mini", n=1)
        _mini(kon, order.order_id, _kelompok(kon))
    sebelum = _hash_berkas(db)
    with js.buka(db) as kon:
        assert _baca(kon) is not None
    assert _hash_berkas(db) == sebelum
