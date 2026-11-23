"""Saga pendaftaran mode anak (F2a): akun murid + siswa milik koordinator lembaga antrean, data sintetis.

Mode anak memparametrisasi saga yang sama dengan mode guru (bukan salinan). Yang dibuktikan di sini: pemilik
siswa = koordinator, nama kembar tidak pernah digabung, persetujuan + PIN ditulis satu transaksi dengan siswa,
fail-closed tanpa lembaga antrean, pemulihan failpoint tanpa duplikat, dan pembaca receipt lain tetap sehat.
"""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

import admin_backup
import admin_registration as reg
import admin_store
import auth
import cek_gratis_skor
import daftar_anak_store
import database
import lembaga_store
import pin_orang_tua_store
import product_analytics_store

WA = "6281234567890"
KOORDINATOR = "koordinator-jagomat"
NAMA = "Raka Pratama Sintetis"


@pytest.fixture
def kasus(tmp_path):
    paths = (tmp_path / "admin.db", tmp_path / "auth.json", tmp_path / "belajar.db")
    admin_store.siapkan(paths[0])
    database.siapkan(paths[2])
    reg.migrasikan_profil_registrasi(paths[2])
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin", paths[1])
    auth.tambah_akun(KOORDINATOR, "sandi-koordinator-sintetis", "guru", paths[1])
    with database.buka(paths[2]) as kon:
        lembaga_id = lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik=KOORDINATOR)
    kw = dict(operasi_id="registrasi_anak_001", alias="raka-login", sandi="sandi-anak-sintetis",
              token_form="x" * 64, sekarang=1800000000, nama_anak=NAMA, kelas_sekolah=4, wa=WA,
              mode_anak=reg.ModeAnak(lembaga_id=lembaga_id, setuju=True, pin="4821"))
    return paths, kw


def _daftar(kasus, **ubah):
    paths, kw = kasus
    return reg.daftar_dengan_profil(*paths, **{**kw, **ubah})


def _mode(kasus, **ubah):
    return reg.ModeAnak(**{"lembaga_id": kasus[1]["mode_anak"].lembaga_id, "setuju": True, "pin": None, **ubah})


def _tabel(paths, sql):
    with database.buka(paths[2]) as kon:
        return [tuple(b) for b in kon.execute(sql)]


def _tanpa_efek(paths, alias="raka-login"):
    assert _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(0,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM kontak_akun") == [(0,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM persetujuan_daftar_anak") == [(0,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM pin_orang_tua") == [(0,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM registrasi_profil_anak") == [(0,)]
    mentah = auth.muat_sandi(paths[1])
    assert mentah.get("registrasi_profil", {}) == {} and mentah.get("operasi_registrasi", {}) == {}
    assert auth.cari_akun(alias, paths[1]) is None


# --- sukses ----------------------------------------------------------------

def test_sukses_akun_murid_siswa_milik_koordinator_dan_semua_tulisan(kasus):
    paths, kw = kasus
    akun = _daftar(kasus)
    assert akun.baru and akun.peran == "murid" and akun.siswa_id
    entri = auth.cari_akun("raka-login", paths[1])
    assert entri["peran"] == "murid" and entri["siswa_id"] == akun.siswa_id
    assert entri["id_akun"] == akun.id_akun
    assert auth.autentikasi("raka-login", "sandi-anak-sintetis", paths[1]).peran == "murid"
    assert _tabel(paths, "SELECT id, nama, pemilik FROM siswa") == [(akun.siswa_id, NAMA, KOORDINATOR)]
    assert _tabel(paths, "SELECT id_akun, wa FROM kontak_akun") == [(akun.id_akun, WA)]
    assert _tabel(paths, "SELECT siswa_id, versi_notice FROM persetujuan_daftar_anak") == [
        (akun.siswa_id, cek_gratis_skor.VERSI_NOTICE)]
    assert _tabel(paths, "SELECT kelas_sekolah FROM profil_belajar") == [(4,)]
    with database.buka(paths[2]) as kon:
        assert pin_orang_tua_store.periksa_pin(kon, akun.siswa_id, "4821") is True
        assert pin_orang_tua_store.periksa_pin(kon, akun.siswa_id, "1111") is False


def test_receipt_child_created_dan_intent_menandai_pemilik_tanpa_nama_atau_pin(kasus):
    paths, kw = kasus
    akun = _daftar(kasus)
    mentah = auth.muat_sandi(paths[1])
    receipt = mentah["operasi_registrasi"][kw["operasi_id"]]
    assert receipt["hasil_kode"] == "child_created" and receipt["hasil_id"] == akun.id_akun
    intent = mentah["registrasi_profil"][kw["operasi_id"]]
    assert intent["status"] == "selesai"
    assert intent["pemilik_sidik"] == reg._sidik_registrasi(KOORDINATOR.casefold())
    teks = json.dumps(mentah)
    for rahasia in (NAMA, "Pratama", WA, "pin", "pin_ada"):
        assert rahasia not in teks
    assert "4821" not in json.dumps(mentah["registrasi_profil"]) + json.dumps(mentah["operasi_registrasi"])
    assert "pin_orang_tua" not in teks


def test_pin_kosong_tidak_menulis_baris_pin_tetapi_persetujuan_tetap(kasus):
    paths, _ = kasus
    akun = _daftar(kasus, mode_anak=_mode(kasus, pin=None))
    assert _tabel(paths, "SELECT COUNT(*) FROM pin_orang_tua") == [(0,)]
    assert _tabel(paths, "SELECT siswa_id FROM persetujuan_daftar_anak") == [(akun.siswa_id,)]


def test_mode_guru_tanpa_mode_anak_tetap_akun_guru_pemilik_alias(kasus):
    paths, kw = kasus
    dasar = {k: v for k, v in kw.items() if k not in ("mode_anak", "wa")}
    akun = reg.daftar_dengan_profil(*paths, **{**dasar, "alias": "ortu-guru", "nama_anak": "Panggilan"})
    assert akun.peran == "guru"
    assert auth.cari_akun("ortu-guru", paths[1])["peran"] == "guru"
    assert _tabel(paths, "SELECT pemilik FROM siswa") == [("ortu-guru",)]
    assert _tabel(paths, "SELECT COUNT(*) FROM persetujuan_daftar_anak") == [(0,)]
    kode = auth.muat_sandi(paths[1])["operasi_registrasi"][kw["operasi_id"]]["hasil_kode"]
    assert kode == "teacher_created"


def test_replay_selesai_idempoten_tanpa_menulis_ulang(kasus):
    paths, _ = kasus
    pertama = _daftar(kasus)
    awal = paths[1].read_bytes()
    kedua = _daftar(kasus)
    assert kedua.id_akun == pertama.id_akun and kedua.siswa_id == pertama.siswa_id
    assert not kedua.baru and kedua.peran == "murid"
    assert paths[1].read_bytes() == awal
    assert _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(1,)]


@pytest.mark.parametrize("ubah", [
    dict(nama_anak="Nama Lain Sintetis"), dict(kelas_sekolah=5), dict(wa="6285551234567"),
    dict(sandi="sandi-diubah-sintetis"),
])
def test_binding_replay_berbeda_ditolak_tanpa_efek(kasus, ubah):
    paths, _ = kasus
    _daftar(kasus)
    awal = paths[1].read_bytes()
    with pytest.raises(ValueError):
        _daftar(kasus, **ubah)
    assert paths[1].read_bytes() == awal and _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(1,)]


def test_replay_pin_beda_atau_hilang_ditolak(kasus):
    paths, _ = kasus
    _daftar(kasus)
    for mode in (_mode(kasus, pin="1111"), _mode(kasus, pin=None)):
        with pytest.raises(ValueError):
            _daftar(kasus, mode_anak=mode)
    with database.buka(paths[2]) as kon:
        assert pin_orang_tua_store.periksa_pin(kon, 1, "4821") is True


def test_replay_mode_guru_atas_operasi_anak_ditolak(kasus):
    paths, kw = kasus
    _daftar(kasus)
    dasar = {k: v for k, v in kw.items() if k not in ("mode_anak", "wa")}
    with pytest.raises(ValueError):
        reg.daftar_dengan_profil(*paths, **dasar)
    assert _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(1,)]


# --- fail-closed -----------------------------------------------------------

def test_lembaga_antrean_tidak_ada_ditolak_tanpa_menulis_apa_pun(kasus):
    paths, _ = kasus
    with pytest.raises(reg.AntreanBelumSiap):
        _daftar(kasus, mode_anak=_mode(kasus, lembaga_id=9999))
    _tanpa_efek(paths)


@pytest.mark.parametrize("keadaan", ["tanpa_akun", "peran_murid", "peran_admin"])
def test_koordinator_tanpa_akun_guru_sah_ditolak_tanpa_menulis(kasus, keadaan):
    paths, _ = kasus
    mentah = auth.muat_sandi(paths[1])
    akun = [a for a in mentah["akun"] if a["pengguna"] != KOORDINATOR] if keadaan == "tanpa_akun" else [
        {**a, "peran": keadaan.split("_")[1]} if a["pengguna"] == KOORDINATOR else a for a in mentah["akun"]]
    paths[1].write_text(json.dumps({**mentah, "akun": akun}))
    with pytest.raises(reg.AntreanBelumSiap):
        _daftar(kasus)
    _tanpa_efek(paths)


def test_koordinator_dinonaktifkan_ditolak(kasus):
    paths, _ = kasus
    mentah = auth.muat_sandi(paths[1])
    akun = [{**a, "dinonaktifkan": True} if a["pengguna"] == KOORDINATOR else a for a in mentah["akun"]]
    paths[1].write_text(json.dumps({**mentah, "akun": akun}))
    with pytest.raises(reg.AntreanBelumSiap):
        _daftar(kasus)
    _tanpa_efek(paths)


# --- validasi tanpa tulis --------------------------------------------------

@pytest.mark.parametrize("ubah", [
    dict(nama_anak=""), dict(nama_anak="   "), dict(nama_anak="A" * 81), dict(nama_anak="Raka\x00Uji"),
    dict(nama_anak="Raka\nUji"), dict(wa=None), dict(wa="0812"), dict(kelas_sekolah=None), dict(kelas_sekolah=7),
    dict(sandi="pendek"), dict(mode_anak=reg.ModeAnak(lembaga_id=1, setuju=False, pin=None)),
    dict(mode_anak=reg.ModeAnak(lembaga_id=1, setuju=True, pin="12")),
    dict(mode_anak=reg.ModeAnak(lembaga_id=1, setuju=True, pin="12a4")),
])
def test_input_tidak_sah_ditolak_tanpa_menulis(kasus, ubah):
    paths, _ = kasus
    with pytest.raises(ValueError):
        _daftar(kasus, **ubah)
    _tanpa_efek(paths)


def test_nama_lengkap_80_karakter_diterima_dan_di_pinggir_dipangkas(kasus):
    paths, _ = kasus
    _daftar(kasus, nama_anak="  " + "B" * 80 + "  ")
    assert _tabel(paths, "SELECT nama FROM siswa") == [("B" * 80,)]


# --- nama kembar: tidak pernah digabung ------------------------------------

def _daftar_dua(kasus, nama2=NAMA, **ubah2):
    pertama = _daftar(kasus)
    kedua = _daftar(kasus, operasi_id="registrasi_anak_002", alias="raka-dua", token_form="y" * 64,
                    nama_anak=nama2, wa="6285551234567", **ubah2)
    return pertama, kedua


def test_dua_pendaftar_nama_lengkap_sama_menjadi_dua_siswa_berbeda(kasus):
    paths, _ = kasus
    pertama, kedua = _daftar_dua(kasus)
    assert pertama.siswa_id != kedua.siswa_id
    assert _tabel(paths, "SELECT id, nama, pemilik FROM siswa ORDER BY id") == [
        (pertama.siswa_id, NAMA, KOORDINATOR), (kedua.siswa_id, NAMA + " (2)", KOORDINATOR)]
    assert auth.cari_akun("raka-login", paths[1])["siswa_id"] == pertama.siswa_id
    assert auth.cari_akun("raka-dua", paths[1])["siswa_id"] == kedua.siswa_id
    assert _tabel(paths, "SELECT COUNT(*) FROM persetujuan_daftar_anak") == [(2,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM kontak_akun") == [(2,)]


def test_nama_kembar_tidak_peduli_huruf_besar_kecil_dan_pembeda_berlanjut(kasus):
    paths, _ = kasus
    _daftar_dua(kasus, nama2=NAMA.upper())
    _daftar(kasus, operasi_id="registrasi_anak_003", alias="raka-tiga", token_form="z" * 64,
            nama_anak=NAMA.lower(), wa="6285559876543")
    assert [r[0] for r in _tabel(paths, "SELECT nama FROM siswa ORDER BY id")] == [
        NAMA, NAMA.upper() + " (2)", NAMA.lower() + " (3)"]


def test_integrity_error_unik_nama_pemilik_mencoba_pembeda_berikutnya_bukan_500(kasus, monkeypatch):
    paths, _ = kasus
    _daftar(kasus)
    asli = lembaga_store.nama_bebas
    panggilan = []

    def buta_sekali(kon, nama, pemilik, dipesan=()):
        panggilan.append(tuple(dipesan))
        return nama if len(panggilan) == 1 else asli(kon, nama, pemilik, dipesan)

    monkeypatch.setattr(lembaga_store, "nama_bebas", buta_sekali)
    kedua = _daftar(kasus, operasi_id="registrasi_anak_002", alias="raka-dua", token_form="y" * 64,
                    wa="6285551234567")
    assert _tabel(paths, "SELECT nama FROM siswa WHERE id=?".replace("?", str(kedua.siswa_id))) == [(NAMA + " (2)",)]
    assert panggilan[1] == (NAMA,)
    assert _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(2,)]


def test_pembeda_habis_ditolak_tanpa_menulis(kasus, monkeypatch):
    paths, _ = kasus
    monkeypatch.setattr(lembaga_store, "nama_bebas", lambda *a, **k: None)
    with pytest.raises(lembaga_store.PenolakanNamaAnak):
        _daftar(kasus)
    _tanpa_efek(paths)


def test_dua_koneksi_serentak_nama_sama_tidak_500_dan_tidak_digabung(kasus):
    paths, kw = kasus

    def satu(i):
        return reg.daftar_dengan_profil(*paths, **{
            **kw, "operasi_id": "registrasi_anak_%03d" % i, "alias": "anak-serentak-%d" % i,
            "token_form": chr(ord("a") + i) * 64, "wa": "62855512345%02d" % i})

    with ThreadPoolExecutor(max_workers=4) as pool:
        hasil = list(pool.map(satu, range(4)))
    assert len({h.siswa_id for h in hasil}) == 4
    assert sorted(r[0] for r in _tabel(paths, "SELECT nama FROM siswa")) == sorted(
        [NAMA] + [NAMA + " (%d)" % n for n in (2, 3, 4)])
    assert {r[0] for r in _tabel(paths, "SELECT pemilik FROM siswa")} == {KOORDINATOR}


# --- failpoint saga mode anak ----------------------------------------------

@pytest.mark.parametrize("titik", ["sebelum_intent", "setelah_intent", "setelah_db", "setelah_auth"])
def test_crash_lalu_lanjut_tepat_satu_siswa_akun_kontak_persetujuan_pin(kasus, titik):
    paths, kw = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        _daftar(kasus, failpoint=titik)
    akun = _daftar(kasus)
    assert auth.autentikasi("raka-login", "sandi-anak-sintetis", paths[1]).peran == "murid"
    for tabel in ("siswa", "kontak_akun", "persetujuan_daftar_anak", "pin_orang_tua", "registrasi_profil_anak"):
        assert _tabel(paths, "SELECT COUNT(*) FROM " + tabel) == [(1,)], tabel
    assert _tabel(paths, "SELECT pemilik, nama FROM siswa") == [(KOORDINATOR, NAMA)]
    assert auth.cari_akun("raka-login", paths[1])["siswa_id"] == akun.siswa_id
    assert [a["pengguna"] for a in auth.muat_sandi(paths[1])["akun"]].count("raka-login") == 1


def test_crash_setelah_intent_lalu_keluarga_lain_mengambil_nama_pemulihan_tetap_jalan(kasus):
    paths, kw = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        _daftar(kasus, failpoint="setelah_intent")
    lain = _daftar(kasus, operasi_id="registrasi_anak_002", alias="raka-dua", token_form="y" * 64,
                   wa="6285551234567")
    assert _tabel(paths, "SELECT nama FROM siswa WHERE id=?".replace("?", str(lain.siswa_id))) == [(NAMA,)]
    akun = _daftar(kasus)
    assert akun.siswa_id != lain.siswa_id
    assert _tabel(paths, "SELECT nama FROM siswa WHERE id=?".replace("?", str(akun.siswa_id))) == [(NAMA + " (2)",)]
    assert auth.cari_akun("raka-login", paths[1])["siswa_id"] == akun.siswa_id
    assert _tabel(paths, "SELECT COUNT(*) FROM persetujuan_daftar_anak") == [(2,)]
    assert _tabel(paths, "SELECT COUNT(*) FROM pin_orang_tua") == [(2,)]


def test_pemulihan_dengan_lembaga_berpindah_pemilik_ditolak_tanpa_menulis_ke_pemilik_lain(kasus):
    paths, _ = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        _daftar(kasus, failpoint="setelah_intent")
    auth.tambah_akun("koordinator-lain", "sandi-koordinator-lain", "guru", paths[1])
    with database.buka(paths[2]) as kon:
        lain = lembaga_store.buat_lembaga(kon, nama="Lembaga Lain", pemilik="koordinator-lain")
    with pytest.raises(ValueError):
        _daftar(kasus, mode_anak=_mode(kasus, lembaga_id=lain, pin="4821"))
    assert _tabel(paths, "SELECT COUNT(*) FROM siswa") == [(0,)]


# --- pembaca receipt lain tetap sehat dengan receipt anak ------------------

def test_receipt_lama_teacher_created_tetap_tervalidasi_bersama_child_created():
    receipt = dict(versi=1, operasi_id="registrasi_a_001", target_id="candidate_" + "a" * 32,
                   hasil_id="akun_" + "b" * 32, hasil_kode="teacher_created", revisi_hasil=1, dibuat=1,
                   sidik_perintah="c" * 64)
    anak = {**receipt, "operasi_id": "registrasi_b_001", "hasil_kode": "child_created"}
    reg._validasi_receipt_publik({"registrasi_a_001": receipt, "registrasi_b_001": anak})
    with pytest.raises(ValueError):
        reg._validasi_receipt_publik({"registrasi_a_001": {**receipt, "hasil_kode": "lain"}})


def test_pembaca_lain_sehat_setelah_pendaftaran_anak_dan_guru_baru_bisa_daftar(kasus):
    import subscription_service
    paths, kw = kasus
    akun_anak = _daftar(kasus)
    dasar = {k: v for k, v in kw.items() if k not in ("mode_anak", "wa")}
    guru = reg.daftar_dengan_profil(*paths, **{**dasar, "operasi_id": "registrasi_guru_001", "alias": "ortu-guru",
                                               "token_form": "g" * 64, "nama_anak": "Panggilan"})
    publik = reg.daftar_publik(paths[0], paths[1], paths[2], operasi_id="registrasi_guru_002", alias="guru-publik",
                               sandi="sandi-publik-sintetis", token_form="h" * 64, sekarang=1800000001)
    assert guru.peran == "guru" and publik.peran == "guru"
    assert admin_backup._validasi_registrasi_profil(paths[2], paths[1]) == (True, 0)
    assert product_analytics_store.pendaftaran_total(paths[1], 0, 2 ** 31) == 3
    mentah = auth.muat_sandi(paths[1])
    r, _daftar_receipt = subscription_service._receipt(
        mentah, "registrasi_guru_001", guru.id_akun, cutoff=0, sekarang=1900000000)
    assert r["hasil_kode"] == "teacher_created"
    with pytest.raises(LookupError):
        subscription_service._receipt(mentah, kw["operasi_id"], guru.id_akun, cutoff=0, sekarang=1900000000)
    assert auth.cari_akun("raka-login", paths[1])["id_akun"] == akun_anak.id_akun


def test_backup_menolak_pasangan_anak_yang_dirusak(kasus):
    paths, kw = kasus
    _daftar(kasus)
    assert admin_backup._validasi_registrasi_profil(paths[2], paths[1]) == (True, 0)
    mentah = auth.muat_sandi(paths[1])
    akun = [{**a, "peran": "guru"} if a["pengguna"] == "raka-login" else a for a in mentah["akun"]]
    paths[1].write_text(json.dumps({**mentah, "akun": akun}))
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup._validasi_registrasi_profil(paths[2], paths[1])


def test_backup_menolak_anak_yang_dipindah_ke_pemilik_lain_tanpa_pindah_resmi(kasus):
    paths, _ = kasus
    _daftar(kasus)
    with database.buka(paths[2]) as kon:
        kon.execute("UPDATE siswa SET pemilik='orang-lain'")
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup._validasi_registrasi_profil(paths[2], paths[1])


def test_backup_menerima_pending_anak_dan_menghitungnya(kasus):
    paths, _ = kasus
    with pytest.raises(reg.RegistrasiBelumSelesai):
        _daftar(kasus, failpoint="setelah_intent")
    assert admin_backup._validasi_registrasi_profil(paths[2], paths[1]) == (True, 1)
    _daftar(kasus)
    assert admin_backup._validasi_registrasi_profil(paths[2], paths[1]) == (True, 0)
