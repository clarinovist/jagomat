"""Kontrak profil guru peninjau: migrasi opt-in, DDL persis, reader fail-closed, CRUD atomik."""
from dataclasses import replace
import sqlite3

import pytest

import admin_store
import auth
import profil_guru_settings as pg

OP = "op_" + "a" * 32


def _op(huruf):
    return "op_" + huruf * 32


def _akun(tmp_path):
    path = tmp_path / "sandi.json"
    auth.tambah_akun("Admin-Profil", "sandi-admin-profil-123", "admin", path)
    auth.tambah_akun("Guru-Profil", "sandi-guru-profil-123", "guru", path)
    return (path, auth.autentikasi("Admin-Profil", "sandi-admin-profil-123", path),
            auth.autentikasi("Guru-Profil", "sandi-guru-profil-123", path))


def _siap(tmp_path):
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    pg.migrasikan(path, sekarang=2)
    return path


def _tambah(path, path_auth, principal, *, operasi=OP, nama="Guru Contoh", latar="S1 Pendidikan Matematika",
            lama="5 tahun mengajar", urutan=1, tampil=False, sekarang=10, **kw):
    return pg.tambah(path, path_auth, principal, operasi=operasi, nama=nama, latar=latar,
                     lama_mengajar=lama, urutan=urutan, tampil=tampil, sekarang=sekarang, **kw)


def _snapshot(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def _ubah_args(profil, **timpa):
    dasar = dict(operasi=_op("b"), profil_id=profil.id, revisi=profil.revisi,
                 sidik_awal=pg.sidik_profil(profil), nama=profil.nama, latar=profil.latar,
                 lama_mengajar=profil.lama_mengajar, urutan=profil.urutan, tampil=profil.tampil,
                 sekarang=20)
    return {**dasar, **timpa}


# --- migrasi dan DDL ---------------------------------------------------------

@pytest.mark.parametrize("versi", [7, 8, 9])
def test_migrasi_opt_in_idempoten_dan_tidak_bump_versi(tmp_path, versi):
    path = tmp_path / ("admin-%d.db" % versi)
    admin_store.siapkan(path, sekarang=1, paket_v2=versi >= 8)
    if versi == 9:
        admin_store.migrasikan_kuota_pendamping(path)
    awal = _snapshot(path)

    pg.migrasikan(path, sekarang=10)
    pertama = _snapshot(path)
    pg.migrasikan(path, sekarang=11)

    assert _snapshot(path) == pertama
    assert all(baris in pertama for baris in awal if not baris.startswith("PRAGMA user_version"))
    with sqlite3.connect(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert kon.execute("SELECT COUNT(*) FROM profil_guru").fetchone()[0] == 0
    assert pg.baca(path) == ()


def test_migrasi_menolak_waktu_tak_sah_dan_db_hilang(tmp_path):
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    with pytest.raises(ValueError):
        pg.migrasikan(path, sekarang=-1)
    with pytest.raises(ValueError):
        pg.migrasikan(path, sekarang=True)
    with pytest.raises(admin_store.StoreBelumSiap):
        pg.migrasikan(tmp_path / "tidak-ada.db", sekarang=1)
    assert not (tmp_path / "tidak-ada.db").exists()


def test_skema_tanpa_kolom_kontak_foto_atau_data_anak(tmp_path):
    path = _siap(tmp_path)
    with sqlite3.connect(path) as kon:
        kolom = {r[1] for r in kon.execute("PRAGMA table_info(profil_guru)")}
        audit = {r[1] for r in kon.execute("PRAGMA table_info(profil_guru_audit)")}
    assert kolom == {"id", "nama", "latar", "lama_mengajar", "urutan", "tampil",
                     "revisi", "dibuat_pada", "diubah_pada"}
    semua = " ".join(sorted(kolom | audit))
    for terlarang in ("email", "telepon", "kontak", "foto", "hp", "wa", "siswa", "anak"):
        assert terlarang not in semua.split(), terlarang


def test_validasi_schema_absen_sah_false_dan_lengkap_true(tmp_path):
    kosong = tmp_path / "kosong.db"
    admin_store.siapkan(kosong, sekarang=1)
    with sqlite3.connect(kosong) as kon:
        assert pg.validasi_schema(kon) is False
    siap = _siap(tmp_path)
    with sqlite3.connect(siap) as kon:
        assert pg.validasi_schema(kon) is True


@pytest.mark.parametrize("rusak", [
    "DROP TABLE profil_guru_audit",
    "DROP TRIGGER profil_guru_audit_tolak_update",
    "DROP TRIGGER profil_guru_batas_baris",
    "CREATE INDEX profil_guru_liar ON profil_guru(nama)",
    "CREATE TABLE profil_guru_tambahan(x INTEGER)",
])
def test_validasi_schema_parsial_atau_berbeda_ditolak(tmp_path, rusak):
    path = _siap(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute(rusak)
        with pytest.raises(ValueError):
            pg.validasi_schema(kon)


def test_tabel_sebagian_tanpa_audit_ditolak(tmp_path):
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE profil_guru(id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError):
        pg.migrasikan(path, sekarang=3)
    assert pg.baca(path) is None
    assert pg.baca_publik(path) == ()


# --- reader fail-closed ------------------------------------------------------

def test_reader_publik_dan_admin_fail_closed_tanpa_tulis(tmp_path):
    hilang = tmp_path / "hilang.db"
    assert pg.baca_publik(hilang) == ()
    assert pg.baca(hilang) is None
    assert not hilang.exists()

    absen = tmp_path / "absen.db"
    admin_store.siapkan(absen, sekarang=1)
    awal = absen.read_bytes()
    assert pg.baca_publik(absen) == ()
    assert pg.baca(absen) is None
    assert absen.read_bytes() == awal

    rusak = _siap(tmp_path)
    with sqlite3.connect(rusak) as kon:
        kon.execute("DROP TABLE profil_guru_audit")
    assert pg.baca_publik(rusak) == ()
    assert pg.baca(rusak) is None


def test_reader_publik_hanya_tampil_urut_dan_tanpa_kolom_lain(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    _tambah(path, path_auth, admin, operasi=_op("1"), nama="Guru Contoh C", urutan=3, tampil=True)
    _tambah(path, path_auth, admin, operasi=_op("2"), nama="Guru Contoh Tersembunyi", urutan=1, tampil=False)
    _tambah(path, path_auth, admin, operasi=_op("3"), nama="Guru Contoh A", urutan=2, tampil=True)
    _tambah(path, path_auth, admin, operasi=_op("4"), nama="Guru Contoh B", urutan=2, tampil=True)

    publik = pg.baca_publik(path)

    assert isinstance(publik, tuple)
    assert [g["nama"] for g in publik] == ["Guru Contoh A", "Guru Contoh B", "Guru Contoh C"]
    assert all(set(g) == {"nama", "latar", "lama_mengajar"} for g in publik)
    assert "Tersembunyi" not in repr(publik)


def test_reader_publik_nilai_rusak_fail_closed(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    _tambah(path, path_auth, admin, tampil=True)
    with sqlite3.connect(path) as kon:
        kon.execute("PRAGMA ignore_check_constraints=ON")
        kon.execute("UPDATE profil_guru SET nama=''")
    assert pg.baca_publik(path) == ()


def test_reader_publik_dapat_dirender_kartu_dengan_escape(tmp_path):
    import funnel_pages
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    _tambah(path, path_auth, admin, nama='Guru "Contoh" & Rekan', tampil=True)
    html = funnel_pages.kartu_profil_guru(pg.baca_publik(path))
    assert "Guru &quot;Contoh&quot; &amp; Rekan" in html
    assert '"Contoh" & Rekan' not in html


# --- validasi ----------------------------------------------------------------

@pytest.mark.parametrize("nama", [
    "", "   ", "x" * 81, "Guru <b>Contoh</b>", "Guru > Contoh", "Guru\nContoh",
    "Guru\x00Contoh", "Guru\tContoh", "Guru‮Contoh", "Guru\x7fContoh", None, 5, b"Guru",
])
def test_nama_tak_sah_ditolak_tanpa_tulis(tmp_path, nama):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = path.read_bytes()
    with pytest.raises(pg.ProfilTidakSah):
        _tambah(path, path_auth, admin, nama=nama)
    assert path.read_bytes() == awal


def test_nama_batas_tepat_80_diterima_dan_dipangkas(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    profil = _tambah(path, path_auth, admin, nama="  " + "x" * 80 + "  ")
    assert profil.nama == "x" * 80


@pytest.mark.parametrize("kolom,nilai", [
    ("latar", ""), ("latar", "y" * 161), ("latar", "S1 <script>"), ("latar", "a\x00b"),
    ("lama", ""), ("lama", "z" * 61), ("lama", "5 tahun >"), ("lama", "5\r\ntahun"),
])
def test_latar_dan_lama_mengajar_tak_sah_ditolak(tmp_path, kolom, nilai):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    with pytest.raises(pg.ProfilTidakSah):
        _tambah(path, path_auth, admin, **{kolom: nilai})
    assert pg.baca(path) == ()


@pytest.mark.parametrize("urutan", [0, 100, -1, True, "1", 1.0, None])
def test_urutan_tak_sah_ditolak(tmp_path, urutan):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    with pytest.raises(pg.ProfilTidakSah):
        _tambah(path, path_auth, admin, urutan=urutan)


@pytest.mark.parametrize("tampil", [1, 0, "1", None])
def test_tampil_harus_bool(tmp_path, tampil):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    with pytest.raises(pg.ProfilTidakSah):
        _tambah(path, path_auth, admin, tampil=tampil)


def test_batas_enam_baris_di_kode_dan_di_database(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    for i in range(pg.BATAS_BARIS):
        _tambah(path, path_auth, admin, operasi=_op("abcdef"[i]), urutan=i + 1)
    assert len(pg.baca(path)) == 6
    with pytest.raises(pg.ProfilTidakSah, match="maksimal"):
        _tambah(path, path_auth, admin, operasi=_op("9"), urutan=7)
    assert len(pg.baca(path)) == 6
    with sqlite3.connect(path) as kon:
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO profil_guru(nama,latar,lama_mengajar,urutan,tampil,revisi,dibuat_pada,diubah_pada)"
                        " VALUES('a','b','c',1,0,1,1,1)")


def test_operasi_tak_sah_dan_waktu_tak_sah(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    with pytest.raises(ValueError):
        _tambah(path, path_auth, admin, operasi="x")
    with pytest.raises(ValueError):
        _tambah(path, path_auth, admin, sekarang=-5)


# --- CRUD, principal, atomik -------------------------------------------------

def test_tambah_default_tersembunyi_dan_audit_tanpa_data_sensitif(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    profil = _tambah(path, path_auth, admin, nama="Guru Contoh Rahasia", latar="S1 Contoh", tampil=False)
    assert (profil.id, profil.revisi, profil.tampil, profil.dibuat_pada) == (1, 1, False, 10)
    assert pg.baca_publik(path) == ()
    with admin_store.buka_baca(path) as kon:
        audit = [dict(r) for r in kon.execute("SELECT * FROM profil_guru_audit")]
    assert len(audit) == 1
    assert audit[0]["principal_id"] == admin.id_akun and audit[0]["aksi"] == "tambah"
    teks = " ".join(str(v) for v in audit[0].values())
    assert "Rahasia" not in teks and "S1 Contoh" not in teks


def test_tambah_replay_idempoten_dan_tabrakan_operasi(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    pertama = _tambah(path, path_auth, admin)
    assert _tambah(path, path_auth, admin) == pertama
    assert len(pg.baca(path)) == 1
    with pytest.raises(admin_store.KonflikOperasi):
        _tambah(path, path_auth, admin, nama="Guru Contoh Lain")
    assert len(pg.baca(path)) == 1


def test_ubah_naikkan_revisi_audit_dan_replay(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = _tambah(path, path_auth, admin)
    args = _ubah_args(awal, nama="Guru Contoh Baru", tampil=True, urutan=2)
    hasil = pg.ubah(path, path_auth, admin, **args)
    assert (hasil.revisi, hasil.nama, hasil.tampil, hasil.urutan, hasil.diubah_pada) == (2, "Guru Contoh Baru", True, 2, 20)
    assert pg.ubah(path, path_auth, admin, **args) == hasil
    with admin_store.buka_baca(path) as kon:
        aksi = [r[0] for r in kon.execute("SELECT aksi FROM profil_guru_audit ORDER BY id")]
    assert aksi == ["tambah", "ubah"]
    with pytest.raises(admin_store.KonflikOperasi):
        pg.ubah(path, path_auth, admin, **{**args, "nama": "Nama Lain"})


def test_ubah_revisi_atau_sidik_basi_ditolak_tanpa_perubahan(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = _tambah(path, path_auth, admin)
    pg.ubah(path, path_auth, admin, **_ubah_args(awal, nama="Guru Contoh Baru"))
    sekarang = pg.baca(path)
    for timpa in ({"operasi": _op("c")},                        # revisi basi
                  {"operasi": _op("d"), "revisi": 2, "sidik_awal": "0" * 64}):  # sidik salah
        with pytest.raises(admin_store.KonflikOperasi):
            pg.ubah(path, path_auth, admin, **_ubah_args(awal, **timpa))
        assert pg.baca(path) == sekarang
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM profil_guru_audit").fetchone()[0] == 2


def test_ubah_dan_hapus_profil_tak_ada_ditolak(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = _tambah(path, path_auth, admin)
    hantu = replace(awal, id=99)
    with pytest.raises(admin_store.KonflikOperasi):
        pg.ubah(path, path_auth, admin, **_ubah_args(hantu))
    with pytest.raises(admin_store.KonflikOperasi):
        pg.hapus(path, path_auth, admin, operasi=_op("e"), profil_id=99, revisi=1,
                 sidik_awal=pg.sidik_profil(hantu), sekarang=30)


def test_hapus_menghapus_baris_dan_audit_tetap_ada(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = _tambah(path, path_auth, admin, tampil=True)
    args = dict(operasi=_op("f"), profil_id=awal.id, revisi=awal.revisi,
                sidik_awal=pg.sidik_profil(awal), sekarang=40)
    assert pg.hapus(path, path_auth, admin, **args) is None
    assert pg.baca(path) == () and pg.baca_publik(path) == ()
    assert pg.hapus(path, path_auth, admin, **args) is None          # replay aman
    with admin_store.buka_baca(path) as kon:
        aksi = [r[0] for r in kon.execute("SELECT aksi FROM profil_guru_audit ORDER BY id")]
    assert aksi == ["tambah", "hapus"]
    # id tidak dipakai ulang sehingga jejak audit tidak ambigu
    baru = _tambah(path, path_auth, admin, operasi=_op("g"))
    assert baru.id > awal.id


def test_audit_append_only(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    _tambah(path, path_auth, admin)
    with sqlite3.connect(path) as kon:
        for sql in ("UPDATE profil_guru_audit SET aksi='hapus'", "DELETE FROM profil_guru_audit",
                    "INSERT OR REPLACE INTO profil_guru_audit SELECT * FROM profil_guru_audit LIMIT 1"):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sql)


@pytest.mark.parametrize("failpoint", ["setelah_tulis"])
def test_failpoint_membatalkan_tambah_ubah_dan_hapus(tmp_path, failpoint):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    with pytest.raises(RuntimeError, match="failpoint"):
        _tambah(path, path_auth, admin, failpoint=failpoint)
    assert pg.baca(path) == ()

    awal = _tambah(path, path_auth, admin, operasi=_op("h"))
    with pytest.raises(RuntimeError, match="failpoint"):
        pg.ubah(path, path_auth, admin, **_ubah_args(awal, nama="Nama Lain", failpoint=failpoint))
    with pytest.raises(RuntimeError, match="failpoint"):
        pg.hapus(path, path_auth, admin, operasi=_op("i"), profil_id=awal.id, revisi=awal.revisi,
                 sidik_awal=pg.sidik_profil(awal), sekarang=50, failpoint=failpoint)
    assert pg.baca(path) == (awal,)
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM profil_guru_audit").fetchone()[0] == 1


def test_hanya_admin_hidup_boleh_menulis(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, guru = _akun(tmp_path)
    awal = path.read_bytes()
    for p in (guru, replace(admin, revisi_auth=admin.revisi_auth + 1), replace(admin, peran="guru")):
        with pytest.raises(LookupError):
            _tambah(path, path_auth, p)
        assert path.read_bytes() == awal
    with pytest.raises(LookupError):
        _tambah(path, path_auth, "bukan-principal")


def test_tulis_tanpa_skema_ditolak_tanpa_menulis(tmp_path):
    path = tmp_path / "admin.db"
    admin_store.siapkan(path, sekarang=1)
    path_auth, admin, _guru = _akun(tmp_path)
    awal = path.read_bytes()
    with pytest.raises(admin_store.StoreBelumSiap):
        _tambah(path, path_auth, admin)
    assert path.read_bytes() == awal


def test_argumen_tidak_dimutasi_dan_dataclass_beku(tmp_path):
    path = _siap(tmp_path)
    path_auth, admin, _guru = _akun(tmp_path)
    profil = _tambah(path, path_auth, admin)
    with pytest.raises(Exception):
        profil.nama = "x"
    assert pg.sidik_profil(profil) == pg.sidik_profil(replace(profil))
    assert pg.sidik_profil(profil) != pg.sidik_profil(replace(profil, revisi=2))
