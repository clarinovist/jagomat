"""Butir antrean admin "guru baru belum masuk lembaga" (butir QA #5; 25 Nov 2026; data sintetis, read-only).

Penanda guru mandiri = receipt pendaftaran publik (`operasi_registrasi`, kode teacher_created) TANPA entri `registrasi_profil` dengan
operasi yang sama: alur orang tua lama selalu membuat profil anak, jadi tidak ikut terhitung. Tanpa kolom atau skema baru.
"""
import re
import urllib.parse
import urllib.request

import pytest

import admin_antrean as A
import admin_antrean_guru as G
import admin_queries as Q
import admin_registration as reg
import auth
import database
import lembaga_store
from http_test_kit import ServerUji

KONTEKS_KOSONG = Q.KonteksAdmin((), (), ())


def _receipt(op, akun_id, kode="teacher_created"):
    return {"versi": 1, "operasi_id": op, "target_id": "candidate_" + "0" * 32, "hasil_id": akun_id,
            "hasil_kode": kode, "revisi_hasil": 1, "dibuat": 1, "sidik_perintah": "0" * 64}


def _id(n):
    return "akun_" + ("%032x" % n)


def test_penanda_hanya_receipt_guru_tanpa_profil():
    mentah = {
        "operasi_registrasi": {"op1": _receipt("op1", _id(1)),                       # guru mandiri
                               "op2": _receipt("op2", _id(2)),                       # orang tua lama: punya profil
                               "op3": _receipt("op3", _id(3), "child_created")},     # akun anak
        "registrasi_profil": {"op2": {}},
    }
    assert G.id_guru_mandiri(mentah) == frozenset({_id(1)})


@pytest.mark.parametrize("mentah", [{}, {"operasi_registrasi": []}, {"operasi_registrasi": {"x": "bukan dict"}},
                                    {"operasi_registrasi": {"x": _receipt("x", _id(1))}, "registrasi_profil": []}, None])
def test_bentuk_data_rusak_tidak_menjatuhkan_penghitungan(mentah):
    assert isinstance(G.id_guru_mandiri(mentah), frozenset)


def _akun(n, nama, peran="guru", **lebih):
    return {"pengguna": nama, "peran": peran, "id_akun": _id(n), **lebih}


def test_hitungan_mengecualikan_terikat_lembaga_pemilik_siswa_nonaktif_dan_peran_lain():
    mentah = {"operasi_registrasi": {"o%d" % n: _receipt("o%d" % n, _id(n)) for n in range(1, 7)}}
    akun = [_akun(1, "baru-satu"), _akun(2, "sudah-lembaga"), _akun(3, "punya-murid"),
            _akun(4, "nonaktif", dinonaktifkan=True), _akun(5, "bukan-guru", peran="murid"), _akun(6, "Baru-Dua")]
    assert G.hitung(mentah, akun, terikat=frozenset({"sudah-lembaga"}), pemilik_siswa=frozenset({"punya-murid"})) == 2


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_GURU", "1")
    auth.tambah_akun("admin-sintetis", "sandi-admin-sintetis", "admin")
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    yield s
    s.berhenti()


def _daftar(server, nama, **tambahan):
    kode, isi, _ = server.minta("/daftar?peran=guru")
    token = re.search(r'name="token_form" value="([^"]+)"', isi).group(1)
    data = urllib.parse.urlencode(dict(nama=nama, sandi="sandi-guru-sintetis", setuju="1", token_form=token)).encode()
    req = urllib.request.Request(server.alamat + "/daftar?peran=guru", data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})

    class TanpaIkut(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        urllib.request.build_opener(TanpaIkut).open(req, timeout=10)
    except urllib.error.HTTPError as galat:
        assert galat.code == 303


def test_guru_mandiri_nyata_terhitung_lalu_hilang_setelah_masuk_lembaga(server):
    assert G.jumlah() == 0
    _daftar(server, "bu-ratna")
    assert G.jumlah() == 1
    auth.tambah_akun("koordinator", "sandi-koordinator-sintetis", "guru")
    with server.buka() as kon:
        lembaga_id = lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="koordinator")
        lembaga_store.tambah_anggota(kon, lembaga_id=lembaga_id, guru="bu-ratna")
    assert G.jumlah() == 0


def test_akun_guru_buatan_admin_dan_orang_tua_lama_tidak_terhitung(server):
    auth.tambah_akun("guru-buatan-admin", "sandi-guru-sintetis", "guru")
    assert G.jumlah() == 0


def test_galat_baca_berarti_nol(monkeypatch):
    def rusak(*a, **k):
        raise OSError("tidak terbaca")
    monkeypatch.setattr(auth, "muat_sandi", rusak)
    assert G.jumlah() == 0


def test_butir_antrean_tinjau_tanpa_menambah_perlu_keputusan(server, monkeypatch, tmp_path):
    import admin_operations
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))
    sebelum = A.kumpulkan(KONTEKS_KOSONG, tmp_path / "x.db", sekarang=1_800_000_000.0)
    _daftar(server, "bu-ratna")
    sesudah = A.kumpulkan(KONTEKS_KOSONG, tmp_path / "x.db", sekarang=1_800_000_000.0)
    baru = [i for i in sesudah.item if i.judul == "1 guru baru belum masuk lembaga"]
    assert len(baru) == 1 and baru[0].tingkat == "tinjau" and baru[0].jalur == "/admin/lembaga"
    assert sesudah.total == sebelum.total + 1 and sesudah.perlu_keputusan == sebelum.perlu_keputusan
    assert "bu-ratna" not in str([baru[0].judul, baru[0].deskripsi])           # tanpa nama akun
