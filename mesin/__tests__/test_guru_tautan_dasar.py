"""Penyimpanan tautan kode anak guru: DB terpisah, append-only, CHECK/UNIQUE, kode basi, aturan permintaan, atomik (data sintetis)."""

import hashlib
import os
import sqlite3
import stat
from contextlib import closing

import pytest

import guru_tautan_aturan as A
import guru_tautan_dasar as T

ID_GURU = "akun_" + "a" * 32
ID_GURU_LAIN = "akun_" + "b" * 32
ID_ORTU = "akun_" + "c" * 32
ID_ANAK = "akun_" + "e" * 32
ID_ANAK_LAIN = "akun_" + "f" * 32
SISWA = 7
SISWA_LAIN = 8
KLP = "klp_" + "1" * 32
KLP_LAIN = "klp_" + "2" * 32
PADA = "2026-11-10T10:00:00"
PADA_LAIN = "2026-11-10T10:30:00"
KEDALUWARSA = "2026-11-17T10:00:00"
TUJUH_HARI_KURANG_DETIK = "2026-11-17T09:59:59"
DELAPAN_HARI = "2026-11-18T10:00:00"
SEHARI_KURANG_DETIK = "2026-11-11T09:59:59"
SEHARI_TEPAT = "2026-11-11T10:00:00"
SATU_JAM_KURANG_DETIK = "2026-11-10T10:59:59"
SATU_JAM_TEPAT = "2026-11-10T11:00:00"
HASH_1 = hashlib.sha256(b"kode-uji-1").hexdigest()
HASH_2 = hashlib.sha256(b"kode-uji-2").hexdigest()
HASH_3 = hashlib.sha256(b"kode-uji-3").hexdigest()
PESAN_TOLAK_UBAH = "hanya boleh ditambah"
JUMLAH_GURU_KUOTA = A.PERMINTAAN_PER_KODE
TABEL_MENTAH = ("kode_anak", "kode_cabut", "permintaan", "putusan", "percobaan_gagal")
BARIS_MENTAH_SAH = {
    "kode_anak": {"akun_id": ID_ANAK, "siswa_id": SISWA, "kode_hash": HASH_3, "dibuat": PADA_LAIN,
                  "oleh": ID_ORTU, "peran": "orang_tua"},
    "kode_cabut": {"kode_id": 1, "pada": PADA_LAIN, "oleh": ID_ORTU, "peran": "orang_tua"},
    "permintaan": {"guru_id": ID_GURU, "kelompok_id": KLP, "kode_id": 1, "dibuat": PADA_LAIN,
                   "kedaluwarsa": KEDALUWARSA},
    "putusan": {"permintaan_id": 2, "hasil": "setuju", "pada": PADA_LAIN, "oleh": ID_ORTU},
    "percobaan_gagal": {"guru_id": ID_GURU, "pada": PADA_LAIN},
}
AKUN_BESAR = "akun_" + "A" * 32
TOLAK_MENTAH = [
    pytest.param("kode_anak", {"akun_id": AKUN_BESAR}, id="kode_anak-akun-huruf-besar"),
    pytest.param("kode_anak", {"akun_id": KLP}, id="kode_anak-akun-prefiks-klp"),
    pytest.param("kode_anak", {"siswa_id": 0}, id="kode_anak-siswa-nol"),
    pytest.param("kode_anak", {"kode_hash": HASH_3.upper()}, id="kode_anak-hash-huruf-besar"),
    pytest.param("kode_anak", {"kode_hash": HASH_3[:-1]}, id="kode_anak-hash-63-karakter"),
    pytest.param("kode_anak", {"kode_hash": "g" * 64}, id="kode_anak-hash-bukan-hex"),
    pytest.param("kode_anak", {"kode_hash": HASH_1}, id="kode_anak-hash-duplikat"),
    pytest.param("kode_anak", {"dibuat": "2026-11-10 10:00:00"}, id="kode_anak-waktu-pakai-spasi"),
    pytest.param("kode_anak", {"oleh": AKUN_BESAR}, id="kode_anak-oleh-huruf-besar"),
    pytest.param("kode_anak", {"peran": "guru"}, id="kode_anak-peran-guru"),
    pytest.param("kode_cabut", {"kode_id": 2}, id="kode_cabut-kode-id-duplikat"),
    pytest.param("kode_cabut", {"peran": "guru"}, id="kode_cabut-peran-guru"),
    pytest.param("permintaan", {"guru_id": AKUN_BESAR}, id="permintaan-guru-huruf-besar"),
    pytest.param("permintaan", {"guru_id": KLP}, id="permintaan-guru-prefiks-klp"),
    pytest.param("permintaan", {"kelompok_id": "kor_" + "1" * 32}, id="permintaan-kelompok-prefiks-kor"),
    pytest.param("permintaan", {"dibuat": "2026-11-10 10:00:00"}, id="permintaan-waktu-pakai-spasi"),
    pytest.param("putusan", {"permintaan_id": 1}, id="putusan-permintaan-duplikat"),
    pytest.param("putusan", {"hasil": "ya"}, id="putusan-hasil-asing"),
    pytest.param("putusan", {"oleh": "bukan-akun"}, id="putusan-oleh-tidak-sah"),
    pytest.param("percobaan_gagal", {"guru_id": AKUN_BESAR}, id="percobaan-guru-huruf-besar"),
    pytest.param("percobaan_gagal", {"pada": "2026-11-10 10:00:00"}, id="percobaan-waktu-pakai-spasi"),
]


@pytest.fixture(autouse=True)
def env_ke_berkas_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh DB sungguhan: env diarahkan ke berkas sementara."""
    monkeypatch.setenv(T.ENV_DB, str(tmp_path / "env-sintetis.db"))


@pytest.fixture
def berkas(tmp_path):
    return tmp_path / "guru-tautan.db"


def _gagal_sisipkan(*args, **kwargs):
    raise sqlite3.OperationalError("gangguan uji")


def _baca(path, sql, parameter=()):
    """Baca lewat mode=ro; berkas harus sudah ada (tes ini tidak boleh membuatnya)."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(sql, parameter).fetchall()


def _jumlah(path, tabel):
    return _baca(path, "SELECT COUNT(*) FROM " + tabel)[0][0]


def _versi(path):
    return _baca(path, "PRAGMA user_version")[0][0]


def _tabel(path):
    sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    return {baris[0] for baris in _baca(path, sql)}


def _insert_mentah(path, tabel, baris):
    """INSERT langsung tanpa validasi Python, tanpa PRAGMA foreign_keys: menguji CHECK dan UNIQUE skema."""
    kolom = tuple(baris)
    sql = "INSERT INTO " + tabel + " (" + ", ".join(kolom) + ") VALUES (" + ", ".join(["?"] * len(kolom)) + ")"
    with closing(sqlite3.connect(str(path))) as kon, kon:
        kon.execute(sql, [baris[k] for k in kolom])


def _guru(indeks):
    return "akun_" + format(indeks + 1, "032x")


def _buat(path, *, akun=ID_ANAK, siswa=SISWA, hash_=HASH_1, pada=PADA):
    return T.buat_kode(akun_id=akun, siswa_id=siswa, kode_hash=hash_, oleh=ID_ORTU,
                       peran="orang_tua", pada=pada, path=path)


def _ganti(path, kode_id, hash_, *, pada=PADA_LAIN):
    return T.ganti_kode(akun_id=ID_ANAK, siswa_id=SISWA, kode_id_aktif=kode_id, kode_hash_baru=hash_,
                        oleh=ID_ORTU, peran="orang_tua", pada=pada, path=path)


def _cabut(path, kode_id, *, akun=ID_ANAK, siswa=SISWA, pada=PADA_LAIN):
    return T.cabut_kode(akun_id=akun, siswa_id=siswa, kode_id_aktif=kode_id, oleh=ID_ORTU,
                        peran="orang_tua", pada=pada, path=path)


def _ajukan(path, *, kode_id, guru=ID_GURU, klp=KLP, pada=PADA):
    return T.ajukan(guru_id=guru, kelompok_id=klp, kode_id=kode_id, pada=pada, path=path)


def _tolak(path, permintaan_id, *, pada=PADA):
    return T.putusan(permintaan_id=permintaan_id, hasil="tolak", oleh=ID_ORTU, pada=pada, path=path)


def _isi_lengkap(path):
    """Satu baris pada kelima tabel lewat API: kode 1 aktif, kode 2 dicabut, permintaan 1 ditolak."""
    kode_a = _buat(path)
    kode_b = _buat(path, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    permintaan_id = _ajukan(path, kode_id=kode_a)
    _tolak(path, permintaan_id, pada=PADA_LAIN)
    _cabut(path, kode_b, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN)
    T.catat_gagal(guru_id=ID_GURU, pada=PADA, path=path)


def _siapkan_mentah(path):
    """`_isi_lengkap` ditambah permintaan 2 tanpa putusan, untuk baseline INSERT mentah."""
    _isi_lengkap(path)
    _ajukan(path, kode_id=1, guru=ID_GURU_LAIN, klp=KLP_LAIN)


# --- berkas, skema, dan baca -------------------------------------------------------------

def test_konstanta_berkas_dan_skema_sesuai_rancangan():
    assert T.NAMA_BERKAS == "guru-tautan.db"
    assert T.BERKAS_BAWAAN == "/data/guru-tautan.db"
    assert T.VERSI_SKEMA == 1
    assert T.TABEL_SKEMA == ("kode_anak", "kode_cabut", "permintaan", "putusan", "percobaan_gagal")


def test_berkas_belum_ada_lalu_dibuat_0600_pada_tulis_pertama(berkas):
    assert not berkas.exists()
    _buat(berkas)
    assert stat.S_IMODE(os.stat(berkas).st_mode) == 0o600


def test_skema_baru_memakai_versi_satu_dengan_kelima_tabel(berkas):
    _buat(berkas)
    assert _versi(berkas) == T.VERSI_SKEMA == 1
    assert set(T.TABEL_SKEMA) <= _tabel(berkas)


def test_baca_tidak_pernah_membuat_berkas(berkas):
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas) is None
    assert T.cari_kode_aktif(HASH_1, path=berkas) is None
    assert T.permintaan_dengan_status(1, PADA, path=berkas) is None
    assert T.daftar_untuk_guru(ID_GURU, PADA, path=berkas) == []
    assert T.daftar_untuk_anak(ID_ANAK, SISWA, PADA, path=berkas) == []
    assert T.jumlah_gagal_guru(ID_GURU, PADA, path=berkas) == 0
    assert not berkas.exists()


def test_baca_berkas_kosong_versi_nol_tidak_mengubah_berkas(berkas):
    berkas.touch(mode=0o600)
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas) is None
    assert berkas.stat().st_size == 0


@pytest.mark.parametrize(
    ("tabel", "sql"),
    [
        pytest.param("kode_anak", "UPDATE kode_anak SET siswa_id = 9", id="kode_anak-ubah"),
        pytest.param("kode_anak", "DELETE FROM kode_anak", id="kode_anak-hapus"),
        pytest.param("kode_cabut", "UPDATE kode_cabut SET pada = '2026-11-11T10:00:00'", id="kode_cabut-ubah"),
        pytest.param("kode_cabut", "DELETE FROM kode_cabut", id="kode_cabut-hapus"),
        pytest.param("permintaan", "UPDATE permintaan SET guru_id = '" + ID_GURU_LAIN + "'", id="permintaan-ubah"),
        pytest.param("permintaan", "DELETE FROM permintaan", id="permintaan-hapus"),
        pytest.param("putusan", "UPDATE putusan SET hasil = 'setuju'", id="putusan-ubah"),
        pytest.param("putusan", "DELETE FROM putusan", id="putusan-hapus"),
        pytest.param("percobaan_gagal", "UPDATE percobaan_gagal SET pada = '2026-11-11T10:00:00'",
                     id="percobaan_gagal-ubah"),
        pytest.param("percobaan_gagal", "DELETE FROM percobaan_gagal", id="percobaan_gagal-hapus"),
    ],
)
def test_trigger_menolak_ubah_dan_hapus_pada_kelima_tabel(berkas, tabel, sql):
    _isi_lengkap(berkas)
    jumlah_awal = _jumlah(berkas, tabel)
    with closing(sqlite3.connect(str(berkas))) as kon:
        with pytest.raises(sqlite3.IntegrityError, match=PESAN_TOLAK_UBAH):
            kon.execute(sql)
    assert _jumlah(berkas, tabel) == jumlah_awal


@pytest.mark.parametrize("tabel", TABEL_MENTAH)
def test_baris_mentah_yang_sah_diterima_oleh_check_dan_unique(berkas, tabel):
    _siapkan_mentah(berkas)
    jumlah = _jumlah(berkas, tabel)
    _insert_mentah(berkas, tabel, BARIS_MENTAH_SAH[tabel])
    assert _jumlah(berkas, tabel) == jumlah + 1


@pytest.mark.parametrize(("tabel", "ubah"), TOLAK_MENTAH)
def test_check_dan_unique_skema_menolak_baris_mentah_tidak_sah(berkas, tabel, ubah):
    _siapkan_mentah(berkas)
    jumlah = _jumlah(berkas, tabel)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_mentah(berkas, tabel, {**BARIS_MENTAH_SAH[tabel], **ubah})
    assert _jumlah(berkas, tabel) == jumlah


def test_versi_skema_asing_ditolak_saat_tulis_dan_baca(berkas):
    with closing(sqlite3.connect(str(berkas))) as kon, kon:
        kon.execute("PRAGMA user_version = 7")
    with pytest.raises(T.GalatTautan):
        _buat(berkas)
    with pytest.raises(T.GalatTautan):
        T.kode_aktif(ID_ANAK, SISWA, path=berkas)
    with pytest.raises(T.GalatTautan):
        T.cari_kode_aktif(HASH_1, path=berkas)
    assert _versi(berkas) == 7
    assert _tabel(berkas) == set()


def test_path_env_dipakai_bila_argumen_path_tidak_diberikan(tmp_path, monkeypatch):
    tujuan = tmp_path / "dari-env.db"
    monkeypatch.setenv(T.ENV_DB, str(tujuan))
    T.catat_gagal(guru_id=ID_GURU, pada=PADA)
    assert tujuan.exists()


# --- validasi sebelum berkas disentuh ---------------------------------------------------

@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"akun": AKUN_BESAR}, id="akun-huruf-besar"),
        pytest.param({"akun": KLP}, id="akun-prefiks-klp"),
        pytest.param({"siswa": 0}, id="siswa-nol"),
        pytest.param({"siswa": True}, id="siswa-bool"),
        pytest.param({"siswa": "7"}, id="siswa-teks"),
        pytest.param({"hash_": HASH_1.upper()}, id="hash-huruf-besar"),
        pytest.param({"hash_": HASH_1[:-1]}, id="hash-pendek"),
        pytest.param({"hash_": "g" * 64}, id="hash-bukan-hex"),
        pytest.param({"pada": "2026-11-10 10:00:00"}, id="pada-pakai-spasi"),
        pytest.param({"pada": None}, id="pada-kosong"),
    ],
)
def test_buat_kode_menolak_argumen_tidak_sah_sebelum_berkas_dibuat(berkas, ubah):
    with pytest.raises(ValueError):
        _buat(berkas, **ubah)
    assert not berkas.exists()


@pytest.mark.parametrize(
    ("oleh", "peran"),
    [
        pytest.param(ID_ORTU, "guru", id="peran-guru"),
        pytest.param(ID_ORTU, "Admin", id="peran-huruf-besar"),
        pytest.param("bukan-akun", "admin", id="oleh-bukan-akun"),
    ],
)
def test_buat_kode_menolak_oleh_dan_peran_tidak_sah_tanpa_berkas(berkas, oleh, peran):
    with pytest.raises(ValueError):
        T.buat_kode(akun_id=ID_ANAK, siswa_id=SISWA, kode_hash=HASH_1, oleh=oleh, peran=peran,
                    pada=PADA, path=berkas)
    assert not berkas.exists()


@pytest.mark.parametrize(
    "ubah",
    [
        pytest.param({"guru_id": AKUN_BESAR}, id="guru-huruf-besar"),
        pytest.param({"kelompok_id": "kor_" + "1" * 32}, id="kelompok-prefiks-kor"),
        pytest.param({"kelompok_id": "klp_" + "G" * 32}, id="kelompok-bukan-hex"),
        pytest.param({"kode_id": 0}, id="kode-id-nol"),
        pytest.param({"kode_id": True}, id="kode-id-bool"),
        pytest.param({"pada": "2026-11-10 10:00:00"}, id="pada-pakai-spasi"),
    ],
)
def test_ajukan_menolak_argumen_tidak_sah_sebelum_berkas_dibuat(berkas, ubah):
    data = {"guru_id": ID_GURU, "kelompok_id": KLP, "kode_id": 1, "pada": PADA}
    with pytest.raises(ValueError):
        T.ajukan(**{**data, **ubah}, path=berkas)
    assert not berkas.exists()


@pytest.mark.parametrize(
    ("fungsi", "argumen"),
    [
        pytest.param(T.catat_gagal, {"guru_id": "bukan-akun", "pada": PADA}, id="catat-guru-tidak-sah"),
        pytest.param(T.catat_gagal, {"guru_id": ID_GURU, "pada": "2026-11-10 10:00:00"}, id="catat-pada-tidak-sah"),
        pytest.param(T.putusan, {"permintaan_id": 0, "hasil": "setuju", "oleh": ID_ORTU, "pada": PADA},
                     id="putusan-id-nol"),
        pytest.param(T.putusan, {"permintaan_id": 1, "hasil": "ya", "oleh": ID_ORTU, "pada": PADA},
                     id="putusan-hasil-tidak-dikenal"),
        pytest.param(T.putusan, {"permintaan_id": 1, "hasil": "tolak", "oleh": "bukan-akun", "pada": PADA},
                     id="putusan-oleh-tidak-sah"),
        pytest.param(T.cabut_semua, {"akun_id": ID_ANAK, "siswa_id": 0, "oleh": ID_ORTU,
                                     "peran": "orang_tua", "pada": PADA}, id="cabut-semua-siswa-nol"),
        pytest.param(T.cabut_semua, {"akun_id": ID_ANAK, "siswa_id": SISWA, "oleh": ID_ORTU,
                                     "peran": "guru", "pada": PADA}, id="cabut-semua-peran-guru"),
        pytest.param(T.ganti_kode, {"akun_id": ID_ANAK, "siswa_id": SISWA, "kode_id_aktif": 1,
                                    "kode_hash_baru": "xyz", "oleh": ID_ORTU, "peran": "orang_tua",
                                    "pada": PADA}, id="ganti-hash-tidak-sah"),
        pytest.param(T.cabut_kode, {"akun_id": ID_ANAK, "siswa_id": SISWA, "kode_id_aktif": 0,
                                    "oleh": ID_ORTU, "peran": "orang_tua", "pada": PADA}, id="cabut-kode-id-nol"),
        pytest.param(T.permintaan_dengan_status, {"permintaan_id": 0, "kini": PADA}, id="status-id-nol"),
        pytest.param(T.permintaan_dengan_status, {"permintaan_id": 1, "kini": "2026-13-01T00:00:00"},
                     id="status-kini-bulan-tiga-belas"),
        pytest.param(T.daftar_untuk_guru, {"guru_id": "bukan-akun", "kini": PADA}, id="daftar-guru-tidak-sah"),
        pytest.param(T.daftar_untuk_anak, {"akun_id": ID_ANAK, "siswa_id": 0, "kini": PADA},
                     id="daftar-anak-siswa-nol"),
        pytest.param(T.jumlah_gagal_guru, {"guru_id": "bukan-akun", "kini": PADA}, id="jumlah-guru-tidak-sah"),
        pytest.param(T.kode_aktif, {"akun_id": "bukan-akun", "siswa_id": SISWA}, id="kode-aktif-akun-tidak-sah"),
    ],
)
def test_panggilan_argumen_tidak_sah_ditolak_sebelum_berkas_dibuat(berkas, fungsi, argumen):
    with pytest.raises(ValueError):
        fungsi(**argumen, path=berkas)
    assert not berkas.exists()


def test_cari_kode_aktif_menolak_hash_tidak_sah_sebelum_berkas_dibuat(berkas):
    with pytest.raises(ValueError):
        T.cari_kode_aktif("pendek", path=berkas)
    assert not berkas.exists()


# --- buat, ganti, dan cabut kode --------------------------------------------------------

def test_buat_kode_mengembalikan_id_dan_kode_aktif_tanpa_hash(berkas):
    assert _buat(berkas) == 1
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas) == {
        "id": 1, "dibuat": PADA, "oleh": ID_ORTU, "peran": "orang_tua",
    }


def test_buat_kode_ditolak_bila_anak_masih_punya_kode_aktif(berkas):
    _buat(berkas)
    with pytest.raises(T.KodeSudahAda):
        _buat(berkas, hash_=HASH_2)
    assert _jumlah(berkas, "kode_anak") == 1


def test_setelah_dicabut_anak_boleh_memiliki_kode_baru(berkas):
    _cabut(berkas, _buat(berkas))
    assert _buat(berkas, hash_=HASH_2, pada=PADA_LAIN) == 2
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas)["id"] == 2


def test_hash_kode_yang_sudah_pernah_dipakai_tidak_boleh_berulang(berkas):
    _cabut(berkas, _buat(berkas))
    with pytest.raises(T.GalatTautan):
        _buat(berkas, hash_=HASH_1, pada=PADA_LAIN)
    assert _jumlah(berkas, "kode_anak") == 1


def test_ganti_kode_mencabut_yang_lama_dan_membuat_yang_baru(berkas):
    lama = _buat(berkas)
    assert _ganti(berkas, lama, HASH_2) == 2
    assert _jumlah(berkas, "kode_anak") == 2
    assert _jumlah(berkas, "kode_cabut") == 1
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas)["id"] == 2


def test_ganti_dengan_id_basi_ditolak_dan_kirim_ulang_tidak_menambah_kode(berkas):
    lama = _buat(berkas)
    _ganti(berkas, lama, HASH_2)
    with pytest.raises(T.KodeBasi):
        _ganti(berkas, lama, HASH_2)
    with pytest.raises(T.KodeBasi):
        _ganti(berkas, lama, HASH_3)
    assert _jumlah(berkas, "kode_anak") == 2
    assert _jumlah(berkas, "kode_cabut") == 1
    assert T.cari_kode_aktif(HASH_3, path=berkas) is None


def test_kode_id_milik_anak_lain_ditolak_tanpa_tulis(berkas):
    _buat(berkas)
    kode_b = _buat(berkas, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    with pytest.raises(T.KodeBasi):
        _ganti(berkas, kode_b, HASH_3)
    with pytest.raises(T.KodeBasi):
        _cabut(berkas, kode_b)
    assert _jumlah(berkas, "kode_anak") == 2
    assert _jumlah(berkas, "kode_cabut") == 0


def test_ganti_kode_anak_tanpa_kode_aktif_ditolak_dan_tidak_meninggalkan_berkas(berkas):
    with pytest.raises(T.KodeBasi):
        _ganti(berkas, 1, HASH_2)
    assert not berkas.exists()


def test_cabut_basi_ditolak_dan_hanya_mencabut_sekali(berkas):
    kode_id = _buat(berkas)
    _cabut(berkas, kode_id)
    with pytest.raises(T.KodeBasi):
        _cabut(berkas, kode_id)
    assert _jumlah(berkas, "kode_cabut") == 1
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas) is None


def test_cabut_semua_idempoten_dan_mengembalikan_nol_atau_satu(berkas):
    _buat(berkas)
    assert T.cabut_semua(akun_id=ID_ANAK, siswa_id=SISWA, oleh=ID_ORTU, peran="orang_tua",
                         pada=PADA_LAIN, path=berkas) == 1
    assert T.cabut_semua(akun_id=ID_ANAK, siswa_id=SISWA, oleh=ID_ORTU, peran="orang_tua",
                         pada=PADA_LAIN, path=berkas) == 0
    assert _jumlah(berkas, "kode_cabut") == 1


def test_cabut_semua_tanpa_berkas_mengembalikan_nol_tanpa_membuat_berkas(berkas):
    assert T.cabut_semua(akun_id=ID_ANAK, siswa_id=SISWA, oleh=ID_ORTU, peran="orang_tua",
                         pada=PADA_LAIN, path=berkas) == 0
    assert not berkas.exists()


def test_cari_kode_aktif_hanya_untuk_hash_yang_masih_aktif(berkas):
    lama = _buat(berkas)
    assert T.cari_kode_aktif(HASH_1, path=berkas) == {"id": lama, "akun_id": ID_ANAK, "siswa_id": SISWA}
    _ganti(berkas, lama, HASH_2)
    assert T.cari_kode_aktif(HASH_1, path=berkas) is None
    assert T.cari_kode_aktif(HASH_2, path=berkas) == {"id": 2, "akun_id": ID_ANAK, "siswa_id": SISWA}
    assert T.cari_kode_aktif(HASH_3, path=berkas) is None
    _cabut(berkas, 2)
    assert T.cari_kode_aktif(HASH_2, path=berkas) is None


def test_gagal_di_tengah_ganti_membatalkan_cabut_dan_kode_baru(berkas, monkeypatch):
    lama = _buat(berkas)
    monkeypatch.setattr(T, "_sisipkan_kode", _gagal_sisipkan)
    with pytest.raises(T.GalatTautan):
        _ganti(berkas, lama, HASH_2)
    assert _jumlah(berkas, "kode_cabut") == 0
    assert _jumlah(berkas, "kode_anak") == 1
    assert T.kode_aktif(ID_ANAK, SISWA, path=berkas)["id"] == lama


def test_gagal_pada_tulis_pertama_tidak_meninggalkan_berkas_kosong(berkas, monkeypatch):
    """Berkas 0 byte tidak punya header SQLite: `sqlite_copy` backup operasional menolaknya."""
    monkeypatch.setattr(T, "_sisipkan_kode", _gagal_sisipkan)
    with pytest.raises(T.GalatTautan):
        _buat(berkas)
    assert not berkas.exists()


def test_gagal_pada_berkas_kosong_buatan_pihak_lain_tidak_dihapus(berkas, monkeypatch):
    berkas.touch(mode=0o600)
    monkeypatch.setattr(T, "_sisipkan_kode", _gagal_sisipkan)
    with pytest.raises(T.GalatTautan):
        _buat(berkas)
    assert berkas.exists()


# --- permintaan (ajukan) ----------------------------------------------------------------

def test_ajukan_membuat_permintaan_menunggu_dengan_kedaluwarsa_tujuh_hari(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    assert permintaan_id == 1
    assert T.permintaan_dengan_status(permintaan_id, PADA_LAIN, path=berkas) == {
        "id": 1,
        "guru_id": ID_GURU,
        "kelompok_id": KLP,
        "akun_id": ID_ANAK,
        "siswa_id": SISWA,
        "dibuat": PADA,
        "kedaluwarsa": KEDALUWARSA,
        "status": "menunggu",
        "pada_putusan": None,
    }


def test_ajukan_dengan_kode_yang_tidak_ada_ditolak_tanpa_berkas(berkas):
    with pytest.raises(T.KodeTakAktif):
        _ajukan(berkas, kode_id=1)
    assert not berkas.exists()


def test_ajukan_dengan_kode_yang_sudah_diganti_ditolak(berkas):
    lama = _buat(berkas)
    _ganti(berkas, lama, HASH_2)
    with pytest.raises(T.KodeTakAktif):
        _ajukan(berkas, kode_id=lama)
    assert _jumlah(berkas, "permintaan") == 0


def test_menunggu_ada_untuk_guru_dan_anak_yang_sama(berkas):
    kode_id = _buat(berkas)
    _ajukan(berkas, kode_id=kode_id)
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode_id, pada=PADA_LAIN)
    assert info.value.alasan == "menunggu_ada"
    assert _jumlah(berkas, "permintaan") == 1


def test_guru_berbeda_dan_anak_berbeda_boleh_mengajukan(berkas):
    kode_a = _buat(berkas)
    kode_b = _buat(berkas, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    _ajukan(berkas, kode_id=kode_a)
    assert _ajukan(berkas, kode_id=kode_a, guru=ID_GURU_LAIN, klp=KLP_LAIN) == 2
    assert _ajukan(berkas, kode_id=kode_b) == 3


def test_ganti_kode_membatalkan_permintaan_menunggu_dan_kode_baru_tetap_dijaga_menunggu_ada(berkas):
    kode1 = _buat(berkas)
    p1 = _ajukan(berkas, kode_id=kode1)
    kode2 = _ganti(berkas, kode1, HASH_2)
    assert T.permintaan_dengan_status(p1, PADA_LAIN, path=berkas)["status"] == "batal"
    assert _ajukan(berkas, kode_id=kode2, pada=PADA_LAIN) == 2
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode2, pada=PADA_LAIN)
    assert info.value.alasan == "menunggu_ada"


def test_jeda_tolak_berlaku_hingga_tepat_tujuh_hari(berkas):
    kode_id = _buat(berkas)
    _tolak(berkas, _ajukan(berkas, kode_id=kode_id))
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode_id, pada=TUJUH_HARI_KURANG_DETIK)
    assert info.value.alasan == "jeda_tolak"
    assert _ajukan(berkas, kode_id=kode_id, pada=KEDALUWARSA) == 2


def test_jeda_dihitung_dari_tolak_terakhir_bukan_yang_pertama(berkas):
    kode_id = _buat(berkas)
    _tolak(berkas, _ajukan(berkas, kode_id=kode_id))
    p2 = _ajukan(berkas, kode_id=kode_id, pada=KEDALUWARSA)
    _tolak(berkas, p2, pada=KEDALUWARSA)
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode_id, pada=DELAPAN_HARI)
    assert info.value.alasan == "jeda_tolak"


def test_ganti_kode_tidak_mereset_jeda_tolak(berkas):
    kode1 = _buat(berkas)
    _tolak(berkas, _ajukan(berkas, kode_id=kode1))
    kode2 = _ganti(berkas, kode1, HASH_2)
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode2, pada=PADA_LAIN)
    assert info.value.alasan == "jeda_tolak"


def test_jeda_tolak_hanya_berlaku_untuk_guru_dan_anak_yang_ditolak(berkas):
    kode_a = _buat(berkas)
    kode_b = _buat(berkas, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    _tolak(berkas, _ajukan(berkas, kode_id=kode_a))
    assert _ajukan(berkas, kode_id=kode_a, guru=ID_GURU_LAIN, klp=KLP_LAIN, pada=PADA_LAIN) == 2
    assert _ajukan(berkas, kode_id=kode_b, pada=PADA_LAIN) == 3


def test_kode_penuh_pada_permintaan_kesebelas_dalam_satu_hari(berkas):
    kode_id = _buat(berkas)
    for indeks in range(JUMLAH_GURU_KUOTA):
        _ajukan(berkas, kode_id=kode_id, guru=_guru(indeks))
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode_id, guru=_guru(JUMLAH_GURU_KUOTA))
    assert info.value.alasan == "kode_penuh"


def test_kode_penuh_jendela_satu_hari_tepat_di_batas_tidak_dihitung(berkas):
    kode_id = _buat(berkas)
    for indeks in range(JUMLAH_GURU_KUOTA):
        _ajukan(berkas, kode_id=kode_id, guru=_guru(indeks))
    with pytest.raises(T.PermintaanDitolakAturan) as info:
        _ajukan(berkas, kode_id=kode_id, guru=_guru(JUMLAH_GURU_KUOTA), pada=SEHARI_KURANG_DETIK)
    assert info.value.alasan == "kode_penuh"
    assert _ajukan(berkas, kode_id=kode_id, guru=_guru(JUMLAH_GURU_KUOTA), pada=SEHARI_TEPAT) == 11


def test_foreign_key_menolak_permintaan_ke_kode_yang_tidak_ada(berkas, monkeypatch):
    """Pertahanan lapis dua: PRAGMA foreign_keys menolak `kode_id` yang tidak ada meski pemeriksaan anak lolos."""
    _buat(berkas)
    monkeypatch.setattr(T, "_anak_dari_kode_aktif", lambda kon, kode_id: (ID_ANAK, SISWA))
    with pytest.raises(T.GalatTautan) as info:
        _ajukan(berkas, kode_id=999)
    assert isinstance(info.value.__cause__, sqlite3.IntegrityError)
    assert _jumlah(berkas, "permintaan") == 0


# --- putusan ----------------------------------------------------------------------------

@pytest.mark.parametrize("hasil", ["setuju", "tolak"])
def test_putusan_dari_menunggu_tercatat(berkas, hasil):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    T.putusan(permintaan_id=permintaan_id, hasil=hasil, oleh=ID_ORTU, pada=PADA_LAIN, path=berkas)
    baca = T.permintaan_dengan_status(permintaan_id, PADA_LAIN, path=berkas)
    assert (baca["status"], baca["pada_putusan"]) == (hasil, PADA_LAIN)


def test_putusan_pada_permintaan_kedaluwarsa_ditolak_tanpa_tulis(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    with pytest.raises(T.PutusanTakBisa):
        T.putusan(permintaan_id=permintaan_id, hasil="setuju", oleh=ID_ORTU, pada=KEDALUWARSA, path=berkas)
    assert _jumlah(berkas, "putusan") == 0


def test_putusan_pada_permintaan_yang_kodenya_dicabut_ditolak(berkas):
    kode_id = _buat(berkas)
    permintaan_id = _ajukan(berkas, kode_id=kode_id)
    _cabut(berkas, kode_id)
    with pytest.raises(T.PutusanTakBisa):
        T.putusan(permintaan_id=permintaan_id, hasil="setuju", oleh=ID_ORTU, pada=PADA_LAIN, path=berkas)
    assert _jumlah(berkas, "putusan") == 0


def test_putusan_kedua_pada_permintaan_yang_sama_ditolak(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    _tolak(berkas, permintaan_id, pada=PADA_LAIN)
    with pytest.raises(T.PutusanTakBisa):
        T.putusan(permintaan_id=permintaan_id, hasil="setuju", oleh=ID_ORTU, pada=PADA_LAIN, path=berkas)
    assert _jumlah(berkas, "putusan") == 1


def test_putusan_pada_permintaan_yang_tidak_ada_ditolak_tanpa_berkas(berkas):
    with pytest.raises(T.PutusanTakBisa):
        T.putusan(permintaan_id=1, hasil="setuju", oleh=ID_ORTU, pada=PADA, path=berkas)
    assert not berkas.exists()


def test_putusan_gagal_di_tengah_tidak_meninggalkan_baris(berkas, monkeypatch):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    monkeypatch.setattr(T, "_sisipkan_putusan", _gagal_sisipkan)
    with pytest.raises(T.GalatTautan):
        T.putusan(permintaan_id=permintaan_id, hasil="setuju", oleh=ID_ORTU, pada=PADA_LAIN, path=berkas)
    assert _jumlah(berkas, "putusan") == 0
    assert T.permintaan_dengan_status(permintaan_id, PADA_LAIN, path=berkas)["status"] == "menunggu"


# --- status turunan dan daftar ----------------------------------------------------------

def test_status_batal_setelah_ganti_dan_setelah_cabut(berkas):
    kode1 = _buat(berkas)
    p1 = _ajukan(berkas, kode_id=kode1)
    kode2 = _ganti(berkas, kode1, HASH_2)
    p2 = _ajukan(berkas, kode_id=kode2, pada=PADA_LAIN)
    _cabut(berkas, kode2, pada=PADA_LAIN)
    assert T.permintaan_dengan_status(p1, PADA_LAIN, path=berkas)["status"] == "batal"
    assert T.permintaan_dengan_status(p2, PADA_LAIN, path=berkas)["status"] == "batal"


def test_status_kedaluwarsa_tepat_saat_kini_mencapai_batas_tujuh_hari(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    assert T.permintaan_dengan_status(permintaan_id, TUJUH_HARI_KURANG_DETIK, path=berkas)["status"] == "menunggu"
    assert T.permintaan_dengan_status(permintaan_id, KEDALUWARSA, path=berkas)["status"] == "kedaluwarsa"


def test_putusan_setuju_tetap_terbaca_setelah_kedaluwarsa(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    T.putusan(permintaan_id=permintaan_id, hasil="setuju", oleh=ID_ORTU, pada=PADA_LAIN, path=berkas)
    assert T.permintaan_dengan_status(permintaan_id, "2026-12-01T00:00:00", path=berkas)["status"] == "setuju"


def test_permintaan_tidak_ada_mengembalikan_none(berkas):
    _buat(berkas)
    assert T.permintaan_dengan_status(99, PADA, path=berkas) is None


def test_daftar_untuk_guru_hanya_memuat_permintaan_guru_itu_terbaru_dulu(berkas):
    kode_a = _buat(berkas)
    kode_b = _buat(berkas, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    p1 = _ajukan(berkas, kode_id=kode_a)
    p2 = _ajukan(berkas, kode_id=kode_b)
    _ajukan(berkas, kode_id=kode_a, guru=ID_GURU_LAIN, klp=KLP_LAIN)
    daftar = T.daftar_untuk_guru(ID_GURU, PADA_LAIN, path=berkas)
    assert [item["id"] for item in daftar] == [p2, p1]


def test_daftar_untuk_anak_hanya_permintaan_kode_anak_itu_termasuk_yang_dicabut(berkas):
    kode_a = _buat(berkas)
    kode_b = _buat(berkas, akun=ID_ANAK_LAIN, siswa=SISWA_LAIN, hash_=HASH_2)
    p1 = _ajukan(berkas, kode_id=kode_a)
    _ajukan(berkas, kode_id=kode_b)
    T.cabut_semua(akun_id=ID_ANAK, siswa_id=SISWA, oleh=ID_ORTU, peran="orang_tua", pada=PADA_LAIN, path=berkas)
    daftar = T.daftar_untuk_anak(ID_ANAK, SISWA, PADA_LAIN, path=berkas)
    assert [(item["id"], item["status"]) for item in daftar] == [(p1, "batal")]


def test_pembaca_tidak_pernah_memuat_kode_hash(berkas):
    permintaan_id = _ajukan(berkas, kode_id=_buat(berkas))
    hasil = [
        T.kode_aktif(ID_ANAK, SISWA, path=berkas),
        T.cari_kode_aktif(HASH_1, path=berkas),
        T.permintaan_dengan_status(permintaan_id, PADA_LAIN, path=berkas),
        T.daftar_untuk_guru(ID_GURU, PADA_LAIN, path=berkas),
        T.daftar_untuk_anak(ID_ANAK, SISWA, PADA_LAIN, path=berkas),
    ]
    teks = repr(hasil)
    assert HASH_1 not in teks
    assert "kode_hash" not in teks


# --- percobaan gagal per guru -----------------------------------------------------------

def test_jumlah_gagal_guru_menghitung_satu_jam_terakhir_per_guru(berkas):
    T.catat_gagal(guru_id=ID_GURU, pada=PADA, path=berkas)
    T.catat_gagal(guru_id=ID_GURU, pada=PADA_LAIN, path=berkas)
    T.catat_gagal(guru_id=ID_GURU_LAIN, pada=PADA, path=berkas)
    assert T.jumlah_gagal_guru(ID_GURU, "2026-11-10T10:45:00", path=berkas) == 2


def test_jumlah_gagal_guru_tepat_di_batas_jendela_tidak_dihitung(berkas):
    T.catat_gagal(guru_id=ID_GURU, pada=PADA, path=berkas)
    assert T.jumlah_gagal_guru(ID_GURU, SATU_JAM_TEPAT, path=berkas) == 0
    assert T.jumlah_gagal_guru(ID_GURU, SATU_JAM_KURANG_DETIK, path=berkas) == 1
