"""Persetujuan orang tua atas permintaan guru (3b-3A): penempatan + putusan, aturan tertutup, idempotensi (data sintetis).

Setiap tes memakai DB admin, latihan, auth, dan tautan sementara di tmp_path; semua path dikirim eksplisit.
Ledger (`putusan`) dan penempatan (`jadwal_penempatan`) dibaca dengan koneksi mode=ro.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pytest

import auth
import database
import guru_tautan_aturan as aturan
import guru_tautan_dasar as tautan
import guru_tautan_tempat as tempat
import jadwal_pilih as jp
import jadwal_store as js
import kelas_kit
import schema_jadwal
from pesanan_kit import AKUN_A

ADMIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
GURU_LAIN = "akun_" + "8" * 32
MURID_LAIN = "akun_" + "d" * 32
LOKASI = "https://meet.google.com/abc-defg-hij"
SANDI_GURU = "sandi-sintetis-setuju-123"
LOGIN_ANAK = "anak-setuju"
SANDI_ANAK = "sandi-anak-setuju-123"
NAMA_KELOMPOK = "Mini Setuju"
NAMA_KELOMPOK_LAIN = "Mini Lain"
KODE = "ABCD2345EFGH6789"
PENGAJUAN = "2026-11-23T03:00:00"
SESUDAH = "2026-11-24T03:00:00"
KEDALUWARSA = "2026-11-30T03:00:00"
TUJUH_HARI_TEPAT = "2026-12-01T03:00:00"
TUJUH_HARI_KURANG_DETIK = "2026-12-01T02:59:59"
SISWA_PENGISI = 77
SISWA_LAIN = 99
TANGGAL_LAMPAU = "2026-11-20"
DIBUAT_LAMPAU = "2026-11-10T00:00:00"
TANGGAL_LEWAT_AKSES = "2026-12-10"


@dataclass(frozen=True)
class Kasus:
    admin: Path
    auth: Path
    belajar: Path
    tautan: Path
    murid_id: str
    siswa_id: int
    order_id: str
    kelompok_id: str
    permintaan_id: int
    kode_id: int


def _order_anak(kon, siswa: int, murid_id: str, paket: str, lunas: bool) -> str:
    if lunas:
        return kelas_kit.lunas(kon, siswa=siswa, paket=paket, akun=murid_id).order_id
    tagihan, _bukti = kelas_kit.menunggu(kon, siswa=siswa, paket=paket, akun=murid_id)
    return tagihan.order_id


def _siapkan(tmp_path: Path, *, tanggal: str = "2026-11-26", dibuat: str = kelas_kit.KINI, kuota: int = 5,
             paket: str = "mini", lunas: bool = True) -> Kasus:
    berkas_auth = tmp_path / "sandi.json"
    auth.simpan_sandi(SANDI_GURU, "guru", path=berkas_auth)
    belajar = tmp_path / "latihan-uji.db"
    database.siapkan(belajar)
    with database.buka(belajar) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis Setuju", "P3", pemilik="keluarga-uji")
        kon.commit()
    murid_id = auth.tambah_akun_dan_principal(LOGIN_ANAK, SANDI_ANAK, "murid", path=berkas_auth,
                                              siswa_id=siswa).id_akun
    admin = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(admin)
    with js.buka(admin, tulis_data=True) as kon:
        kelompok = js.buat_kelompok(kon, ADMIN, nama=NAMA_KELOMPOK, lokasi=LOKASI, guru_id=GURU, kuota=kuota,
                                    tanggal=tanggal, jam="09:00", sekarang=dibuat)
        order = _order_anak(kon, siswa, murid_id, paket, lunas)
        kon.commit()
    tautan_path = tmp_path / "guru-tautan-uji.db"
    kode_id = tautan.buat_kode(akun_id=murid_id, siswa_id=siswa, kode_hash=aturan.hash_kode(KODE),
                               oleh=murid_id, peran=aturan.PERAN_ORANG_TUA, pada=PENGAJUAN, path=tautan_path)
    permintaan_id = tautan.ajukan(guru_id=GURU, kelompok_id=kelompok, kode_id=kode_id, pada=PENGAJUAN,
                                  path=tautan_path)
    return Kasus(admin=admin, auth=berkas_auth, belajar=belajar, tautan=tautan_path, murid_id=murid_id,
                 siswa_id=siswa, order_id=order, kelompok_id=kelompok, permintaan_id=permintaan_id,
                 kode_id=kode_id)


def _setujui(k: Kasus, *, pada: str = SESUDAH, permintaan_id: int | None = None, akun_id: str | None = None,
             siswa_id: int | None = None) -> None:
    tempat.setujui_permintaan(
        permintaan_id=k.permintaan_id if permintaan_id is None else permintaan_id,
        akun_id=k.murid_id if akun_id is None else akun_id,
        siswa_id=k.siswa_id if siswa_id is None else siswa_id,
        oleh=k.murid_id, pada=pada,
        path_tautan=k.tautan, path_admin=k.admin, path_auth=k.auth, path_belajar=k.belajar)


def _sql(path: Path, kueri: str, parameter: tuple = ()) -> list:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        return [tuple(baris) for baris in kon.execute(kueri, parameter).fetchall()]


def _ledger(path: Path) -> list:
    return _sql(path, "SELECT permintaan_id, hasil, oleh FROM putusan ORDER BY id")


def _penempatan(k: Kasus) -> list:
    return [baris[0] for baris in _sql(k.admin, "SELECT kelompok_id FROM jadwal_penempatan ORDER BY kelompok_id")]


def _status(k: Kasus, pada: str = SESUDAH) -> str:
    return tautan.permintaan_dengan_status(k.permintaan_id, pada, path=k.tautan)["status"]


def _sidik(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tambah_kelompok(k: Kasus, *, nama: str = NAMA_KELOMPOK_LAIN, guru: str = GURU,
                     tanggal: str = "2026-11-26") -> str:
    with js.buka(k.admin, tulis_data=True) as kon:
        kid = js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=LOKASI, guru_id=guru, kuota=5, tanggal=tanggal,
                               jam="09:00", sekarang=kelas_kit.KINI)
        kon.commit()
    return kid


def _isi_kursi(k: Kasus, siswa: int = SISWA_PENGISI) -> None:
    """Anak lain ditempatkan ke kelompok anak ini: kelompok penuh bila kuotanya 1. `n=2`: berkas bukti unik per order."""
    with js.buka(k.admin, tulis_data=True) as kon:
        tagihan = kelas_kit.lunas(kon, siswa=siswa, n=2, akun=AKUN_A, sekarang=kelas_kit.KINI)
        js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=k.kelompok_id, sekarang=PENGAJUAN)
        kon.commit()


def _tempatkan_order_anak(k: Kasus, kelompok_id: str) -> None:
    with js.buka(k.admin, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN, k.order_id, kelompok_id=kelompok_id, sekarang=PENGAJUAN)
        kon.commit()


def _pindah_guru(k: Kasus, guru: str) -> None:
    with js.buka(k.admin, tulis_data=True) as kon:
        js.ubah_kelompok(kon, ADMIN, k.kelompok_id, nama=NAMA_KELOMPOK, lokasi=LOKASI, guru_id=guru, kuota=5,
                         sekarang=PENGAJUAN)
        kon.commit()


def _anonimkan_siswa(k: Kasus) -> None:
    with closing(sqlite3.connect(str(k.belajar))) as kon:
        kon.execute("UPDATE siswa SET nama=? WHERE id=?", ("Dihapus-1", k.siswa_id))
        kon.commit()


def _alasan(galat: pytest.ExceptionInfo) -> str:
    return galat.value.alasan


# --- putusan_dengan_tempat (lapisan tautan saja) ----------------------------------------

MURID = "akun_" + "e" * 32
SISWA = 7
KLP = "klp_" + "1" * 32


@pytest.fixture()
def tautan_saja(tmp_path):
    path = tmp_path / "guru-tautan-uji.db"
    kode = tautan.buat_kode(akun_id=MURID, siswa_id=SISWA, kode_hash=aturan.hash_kode(KODE), oleh=MURID,
                            peran=aturan.PERAN_ORANG_TUA, pada=PENGAJUAN, path=path)
    permintaan = tautan.ajukan(guru_id=GURU, kelompok_id=KLP, kode_id=kode, pada=PENGAJUAN, path=path)
    return path, permintaan


def _panggil_dengan_tempat(path: Path, permintaan: int, tempatkan, *, siswa_id: int = SISWA,
                           pada: str = SESUDAH) -> None:
    tautan.putusan_dengan_tempat(permintaan_id=permintaan, akun_id=MURID, siswa_id=siswa_id, oleh=MURID,
                                 pada=pada, tempatkan=tempatkan, path=path)


def test_galat_sqlite_dari_tempatkan_keluar_apa_adanya_tanpa_putusan(tautan_saja):
    path, permintaan = tautan_saja

    def tempatkan():
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError) as galat:
        _panggil_dengan_tempat(path, permintaan, tempatkan)
    assert type(galat.value) is sqlite3.OperationalError
    assert _ledger(path) == []


def test_galat_domain_dari_tempatkan_membatalkan_putusan_dan_dilempar_apa_adanya(tautan_saja):
    path, permintaan = tautan_saja

    class GagalUji(RuntimeError):
        pass

    def tempatkan():
        raise GagalUji("kelompok penuh")

    with pytest.raises(GagalUji):
        _panggil_dengan_tempat(path, permintaan, tempatkan)
    assert _ledger(path) == []
    assert tautan.permintaan_dengan_status(permintaan, SESUDAH, path=path)["status"] == aturan.STATUS_MENUNGGU


def test_sqlite_saat_sisip_putusan_dibungkus_galat_tautan_tanpa_putusan(tautan_saja, monkeypatch):
    path, permintaan = tautan_saja
    dipanggil = []

    def sisip_gagal(*_args):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(tautan, "_sisipkan_putusan", sisip_gagal)

    def tempatkan():
        dipanggil.append(True)

    with pytest.raises(tautan.GalatTautan):
        _panggil_dengan_tempat(path, permintaan, tempatkan)
    assert dipanggil == [True]
    assert _ledger(path) == []


@pytest.mark.parametrize("keadaan", ["anak_lain", "kedaluwarsa", "sudah_ditolak"])
def test_permintaan_tak_menunggu_atau_bukan_milik_anak_tidak_memanggil_tempatkan(tautan_saja, keadaan):
    path, permintaan = tautan_saja
    dipanggil = []
    pada, siswa = SESUDAH, SISWA
    if keadaan == "anak_lain":
        siswa = SISWA_LAIN
    elif keadaan == "kedaluwarsa":
        pada = KEDALUWARSA
    else:
        tautan.putusan(permintaan_id=permintaan, akun_id=MURID, siswa_id=SISWA, hasil=aturan.HASIL_TOLAK,
                       oleh=MURID, pada=SESUDAH, path=path)

    with pytest.raises(tautan.PutusanTakBisa):
        _panggil_dengan_tempat(path, permintaan, lambda: dipanggil.append(True), siswa_id=siswa, pada=pada)
    assert dipanggil == []
    assert [baris[1] for baris in _ledger(path)] == (["tolak"] if keadaan == "sudah_ditolak" else [])


def test_putusan_dengan_tempat_menolak_tempatkan_yang_bukan_fungsi(tautan_saja):
    path, permintaan = tautan_saja
    with pytest.raises(ValueError):
        _panggil_dengan_tempat(path, permintaan, "bukan-fungsi")
    assert _ledger(path) == []


TUNGGU_KUNCI_DETIK = 0.2
BATAS_THREAD_DETIK = 5.0


def _jalankan_di_thread(sasaran) -> BaseException | None:
    """Jalankan `sasaran` di thread lain dan tunggu selesai. Mengembalikan galat yang dilempar, atau None.

    Galat ditangkap di dalam thread supaya tidak lolos sebagai peringatan thread (`-W error` menjadikannya galat).
    """
    hasil: list = []

    def jalan() -> None:
        try:
            sasaran()
        except BaseException as galat:
            hasil.append(galat)
        else:
            hasil.append(None)

    thread = threading.Thread(target=jalan)
    thread.start()
    thread.join(BATAS_THREAD_DETIK)
    assert not thread.is_alive(), "thread tidak selesai; kemungkinan menggantung"
    return hasil[0]


def _pastikan_kalah_oleh_kunci(galat: BaseException | None) -> None:
    """Tolak serentak harus gagal sebagai GalatTautan yang disebabkan kunci tulis (BEGIN IMMEDIATE tertahan)."""
    assert type(galat) is tautan.GalatTautan, "tolak serentak harus GalatTautan, bukan %r" % (galat,)
    assert isinstance(galat.__cause__, sqlite3.OperationalError), "galat tolak bukan karena kunci SQLite"


def test_tolak_serentak_di_dalam_tempatkan_kalah_oleh_kunci_dan_setuju_tetap_tunggal(tautan_saja, monkeypatch):
    path, permintaan = tautan_saja
    monkeypatch.setattr(tautan, "TIMEOUT_DETIK", TUNGGU_KUNCI_DETIK)
    dipanggil: list = []
    ledger_di_dalam: list = []

    def tolak_dari_thread() -> None:
        tautan.putusan(permintaan_id=permintaan, akun_id=MURID, siswa_id=SISWA, hasil=aturan.HASIL_TOLAK,
                       oleh=MURID, pada=SESUDAH, path=path)

    def tempatkan() -> None:
        dipanggil.append(True)
        _pastikan_kalah_oleh_kunci(_jalankan_di_thread(tolak_dari_thread))
        ledger_di_dalam.append(_ledger(path))

    _panggil_dengan_tempat(path, permintaan, tempatkan)

    assert dipanggil == [True]
    assert ledger_di_dalam == [[]]
    assert _ledger(path) == [(permintaan, aturan.HASIL_SETUJU, MURID)]
    with pytest.raises(tautan.PutusanTakBisa):
        tautan.putusan(permintaan_id=permintaan, akun_id=MURID, siswa_id=SISWA, hasil=aturan.HASIL_TOLAK,
                       oleh=MURID, pada=SESUDAH, path=path)
    assert _ledger(path) == [(permintaan, aturan.HASIL_SETUJU, MURID)]


# --- setujui_permintaan: jalur normal dan aturan tertutup -------------------------------

def test_setujui_menempatkan_anak_dan_mencatat_putusan_oleh_anak(tmp_path):
    k = _siapkan(tmp_path)
    _setujui(k)
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]
    assert _penempatan(k) == [k.kelompok_id]


def test_setujui_kelompok_penuh_gagal_tanpa_putusan_dan_tanpa_penempatan_ganda(tmp_path):
    k = _siapkan(tmp_path, kuota=1)
    _isi_kursi(k)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_KELOMPOK_PENUH
    assert _ledger(k.tautan) == []
    assert _status(k) == aturan.STATUS_MENUNGGU
    assert _penempatan(k) == [k.kelompok_id]


def test_setujui_kelompok_tutup_setelah_dua_pertemuan_gagal_tanpa_efek(tmp_path):
    k = _siapkan(tmp_path, tanggal=TANGGAL_LAMPAU, dibuat=DIBUAT_LAMPAU)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k, pada="2026-11-25T03:00:00")
    assert _alasan(galat) == tempat.ALASAN_KELOMPOK_TAK_BISA
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_setujui_kelompok_lewat_akses_gagal_tanpa_efek(tmp_path):
    k = _siapkan(tmp_path, tanggal=TANGGAL_LEWAT_AKSES)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_KELOMPOK_TAK_BISA
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_setujui_paket_belum_aktif_gagal_tanpa_efek(tmp_path):
    k = _siapkan(tmp_path, lunas=False)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_PAKET_TAK_AKTIF
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


@pytest.mark.parametrize("cara", ["akun_dihapus", "siswa_dianonimkan"])
def test_setujui_anak_dihapus_antara_pengajuan_dan_persetujuan_gagal_tanpa_efek(tmp_path, cara):
    k = _siapkan(tmp_path)
    if cara == "akun_dihapus":
        assert auth.hapus_akun(LOGIN_ANAK, path=k.auth) is True
    else:
        _anonimkan_siswa(k)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_ANAK_TAK_ADA
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_setujui_anak_sudah_di_kelompok_lain_gagal_tanpa_penempatan_kedua(tmp_path):
    k = _siapkan(tmp_path)
    lain = _tambah_kelompok(k)
    _tempatkan_order_anak(k, lain)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_ANAK_DI_KELOMPOK_LAIN
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == [lain]


def test_setujui_kelompok_dipindah_guru_setelah_pengajuan_gagal_tanpa_penempatan(tmp_path):
    k = _siapkan(tmp_path)
    _pindah_guru(k, GURU_LAIN)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_BUKAN_MILIK_GURU
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_setujui_anak_sudah_anggota_kelompok_yang_dipindah_guru_tanpa_putusan(tmp_path):
    k = _siapkan(tmp_path)
    _tempatkan_order_anak(k, k.kelompok_id)
    _pindah_guru(k, GURU_LAIN)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_BUKAN_MILIK_GURU
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == [k.kelompok_id]


def test_ulang_setelah_commit_tautan_gagal_tidak_menempatkan_dua_kali(tmp_path, monkeypatch):
    k = _siapkan(tmp_path)
    asli = tautan._sisipkan_putusan
    sisa_gagal = [1]

    def sekali_gagal(kon, *args):
        if sisa_gagal[0]:
            sisa_gagal[0] -= 1
            raise sqlite3.OperationalError("disk I/O error")
        return asli(kon, *args)

    monkeypatch.setattr(tautan, "_sisipkan_putusan", sekali_gagal)
    with pytest.raises(tautan.GalatTautan):
        _setujui(k)
    assert _penempatan(k) == [k.kelompok_id]
    assert _ledger(k.tautan) == []

    _setujui(k)
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]
    assert _penempatan(k) == [k.kelompok_id]


def test_dua_persetujuan_beruntun_hanya_satu_penempatan_dan_satu_putusan(tmp_path):
    k = _siapkan(tmp_path)
    _setujui(k)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]
    assert _penempatan(k) == [k.kelompok_id]


def test_tolak_sesudah_setuju_ditolak_dan_putusan_tidak_berubah(tmp_path):
    k = _siapkan(tmp_path)
    _setujui(k)
    with pytest.raises(tempat.GagalPutusan) as galat:
        tempat.tolak_permintaan(permintaan_id=k.permintaan_id, akun_id=k.murid_id, siswa_id=k.siswa_id,
                                oleh=k.murid_id, pada=SESUDAH, path_tautan=k.tautan)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]


def test_setujui_tolak_serentak_di_tengah_penempatan_kalah_oleh_kunci_dan_setuju_tetap_tunggal(tmp_path,
                                                                                               monkeypatch):
    k = _siapkan(tmp_path)
    monkeypatch.setattr(tautan, "TIMEOUT_DETIK", TUNGGU_KUNCI_DETIK)
    pilih_asli = jp.pilih_kelompok
    dipanggil: list = []

    def tolak_dari_thread() -> None:
        tautan.putusan(permintaan_id=k.permintaan_id, akun_id=k.murid_id, siswa_id=k.siswa_id,
                       hasil=aturan.HASIL_TOLAK, oleh=k.murid_id, pada=SESUDAH, path=k.tautan)

    def pilih_dengan_tolak_serentak(kon, *args, **kwargs) -> None:
        dipanggil.append(True)
        _pastikan_kalah_oleh_kunci(_jalankan_di_thread(tolak_dari_thread))
        pilih_asli(kon, *args, **kwargs)

    monkeypatch.setattr(jp, "pilih_kelompok", pilih_dengan_tolak_serentak)
    _setujui(k)

    assert dipanggil == [True]
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]
    assert _penempatan(k) == [k.kelompok_id]
    with pytest.raises(tempat.GagalPutusan) as galat:
        tempat.tolak_permintaan(permintaan_id=k.permintaan_id, akun_id=k.murid_id, siswa_id=k.siswa_id,
                                oleh=k.murid_id, pada=SESUDAH, path_tautan=k.tautan)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _ledger(k.tautan) == [(k.permintaan_id, "setuju", k.murid_id)]


@pytest.mark.parametrize("cara", ["anak_lain", "permintaan_tidak_ada"])
def test_permintaan_anak_lain_atau_tidak_ada_gagal_tanpa_efek(tmp_path, cara):
    k = _siapkan(tmp_path)
    sebelum = _sidik(k.tautan)
    if cara == "anak_lain":
        with pytest.raises(tempat.GagalPutusan) as galat:
            _setujui(k, akun_id=MURID_LAIN, siswa_id=SISWA_LAIN)
    else:
        with pytest.raises(tempat.GagalPutusan) as galat:
            _setujui(k, permintaan_id=999)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _sidik(k.tautan) == sebelum
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_permintaan_kedaluwarsa_persis_pada_batas_tidak_bisa_disetujui(tmp_path):
    k = _siapkan(tmp_path)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k, pada=KEDALUWARSA)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_permintaan_batal_karena_kode_dicabut_tidak_bisa_disetujui(tmp_path):
    k = _siapkan(tmp_path)
    tautan.cabut_kode(akun_id=k.murid_id, siswa_id=k.siswa_id, kode_id_aktif=k.kode_id, oleh=k.murid_id,
                      peran=aturan.PERAN_ORANG_TUA, pada="2026-11-23T04:00:00", path=k.tautan)
    with pytest.raises(tempat.GagalPutusan) as galat:
        _setujui(k)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _ledger(k.tautan) == []
    assert _penempatan(k) == []


def test_penempatan_order_lama_yang_berakhir_tidak_menghalangi_penempatan_order_baru(tmp_path):
    k = _siapkan(tmp_path)
    _tempatkan_order_anak(k, k.kelompok_id)
    kedua = _tambah_kelompok(k, nama="Mini Baru", guru=GURU, tanggal="2026-12-22")
    with js.buka(k.admin, tulis_data=True) as kon:
        tagihan, bukti = kelas_kit.menunggu(kon, siswa=k.siswa_id, n=3, akun=k.murid_id,
                                            sekarang="2026-12-21T03:00:00", unggah_pada="2026-12-21T03:30:00")
        kelas_kit.setuju(kon, tagihan, bukti, sekarang="2026-12-21T04:00:00")
        kon.commit()
    with js.buka(k.admin, tulis_data=True) as kon:
        assert tempat.penempatan_anak(kon, k.murid_id, k.siswa_id, "2026-12-21T05:00:00") is None
        assert jp.pilihan_untuk(kon, k.murid_id, k.siswa_id, "2026-12-21T05:00:00") != ()
    permintaan_baru = tautan.ajukan(guru_id=GURU, kelompok_id=kedua, kode_id=k.kode_id, pada="2026-12-21T04:30:00",
                                    path=k.tautan)
    _setujui(k, pada="2026-12-21T05:00:00", permintaan_id=permintaan_baru)
    assert _ledger(k.tautan) == [(permintaan_baru, "setuju", k.murid_id)]
    assert _penempatan(k) == [kedua]


# --- tolak --------------------------------------------------------------------------------

def test_tolak_hanya_menulis_putusan_tanpa_penempatan_dan_memulai_jeda_tujuh_hari(tmp_path):
    k = _siapkan(tmp_path)
    tempat.tolak_permintaan(permintaan_id=k.permintaan_id, akun_id=k.murid_id, siswa_id=k.siswa_id,
                            oleh=k.murid_id, pada=SESUDAH, path_tautan=k.tautan)
    assert _ledger(k.tautan) == [(k.permintaan_id, "tolak", k.murid_id)]
    assert _penempatan(k) == []
    with pytest.raises(tautan.PermintaanDitolakAturan) as galat:
        tautan.ajukan(guru_id=GURU, kelompok_id=k.kelompok_id, kode_id=k.kode_id, pada=TUJUH_HARI_KURANG_DETIK,
                      path=k.tautan)
    assert galat.value.alasan == tautan.ALASAN_JEDA_TOLAK
    kedua = tautan.ajukan(guru_id=GURU, kelompok_id=k.kelompok_id, kode_id=k.kode_id, pada=TUJUH_HARI_TEPAT,
                          path=k.tautan)
    assert kedua > k.permintaan_id


def test_tolak_tetap_bisa_walau_akun_anak_sudah_dihapus(tmp_path):
    k = _siapkan(tmp_path)
    auth.hapus_akun(LOGIN_ANAK, path=k.auth)
    tempat.tolak_permintaan(permintaan_id=k.permintaan_id, akun_id=k.murid_id, siswa_id=k.siswa_id,
                            oleh=k.murid_id, pada=SESUDAH, path_tautan=k.tautan)
    assert _ledger(k.tautan) == [(k.permintaan_id, "tolak", k.murid_id)]
    assert _penempatan(k) == []


def test_tolak_permintaan_anak_lain_gagal_tanpa_efek(tmp_path):
    k = _siapkan(tmp_path)
    sebelum = _sidik(k.tautan)
    with pytest.raises(tempat.GagalPutusan) as galat:
        tempat.tolak_permintaan(permintaan_id=k.permintaan_id, akun_id=MURID_LAIN, siswa_id=SISWA_LAIN,
                                oleh=MURID_LAIN, pada=SESUDAH, path_tautan=k.tautan)
    assert _alasan(galat) == tempat.ALASAN_PERMINTAAN_TAK_BISA
    assert _sidik(k.tautan) == sebelum


def test_alasan_tak_dikenal_ditolak_saat_dibuat():
    with pytest.raises(ValueError):
        tempat.GagalPutusan("alasan_karangan")
    assert tempat.GagalPutusan(tempat.ALASAN_KELOMPOK_PENUH).alasan == tempat.ALASAN_KELOMPOK_PENUH
