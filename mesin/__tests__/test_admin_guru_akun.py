"""Daftar akun guru admin (butir QA #5, 25 Nov 2026; data sintetis, baca-saja)."""
import pytest

import admin_guru_akun as G
import admin_queries as Q
import database
import lembaga_store


def _id(n):
    return "akun_" + ("%032x" % n)


def _receipt(op, akun_id, kode="teacher_created"):
    return {"versi": 1, "operasi_id": op, "target_id": "candidate_" + "0" * 32, "hasil_id": akun_id,
            "hasil_kode": kode, "revisi_hasil": 1, "dibuat": 1, "sidik_perintah": "0" * 64}


def _akun(n, nama, peran="guru", **lebih):
    return {"pengguna": nama, "peran": peran, "id_akun": _id(n), **lebih}


@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _anak(kon, nama, pemilik):
    kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', ?)", (nama, pemilik))
    kon.commit()


AKUN = [_akun(1, "bu-mandiri"), _akun(2, "pak-admin"), _akun(3, "ortu-lama"), _akun(4, "koordinator"),
        _akun(5, "anggota"), _akun(6, "nonaktif", dinonaktifkan=True), _akun(7, "admin-x", peran="admin"),
        _akun(8, "murid-x", peran="murid")]
MENTAH = {"operasi_registrasi": {"o1": _receipt("o1", _id(1)), "o3": _receipt("o3", _id(3))},
          "registrasi_profil": {"o3": {}}}


@pytest.fixture
def lembaga(kon):
    lid = lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="koordinator")
    lembaga_store.tambah_anggota(kon, lembaga_id=lid, guru="anggota")
    return lid


def test_hanya_guru_aktif_bukan_orang_tua_lama(kon, lembaga):
    nama = [g.pengguna for g in G.daftar_guru(kon, AKUN, MENTAH)]
    assert nama == ["anggota", "bu-mandiri", "koordinator", "pak-admin"]


def test_asal_lembaga_dan_peran(kon, lembaga):
    g = {x.pengguna: x for x in G.daftar_guru(kon, AKUN, MENTAH)}
    assert (g["bu-mandiri"].asal, g["bu-mandiri"].lembaga) == (G.ASAL_MANDIRI, None)
    assert (g["pak-admin"].asal, g["pak-admin"].lembaga) == (G.ASAL_ADMIN, None)
    assert (g["koordinator"].lembaga, g["koordinator"].peran_lembaga) == ("Jagomat", G.PERAN_KOORDINATOR)
    assert (g["anggota"].lembaga, g["anggota"].peran_lembaga) == ("Jagomat", G.PERAN_ANGGOTA)


def test_jumlah_anak_dihitung_dari_pemilik(kon, lembaga):
    _anak(kon, "Anak Satu", "pak-admin")
    _anak(kon, "Anak Dua", "pak-admin")
    g = {x.pengguna: x for x in G.daftar_guru(kon, AKUN, MENTAH)}
    assert g["pak-admin"].jumlah_siswa == 2 and g["bu-mandiri"].jumlah_siswa == 0


@pytest.mark.parametrize("saring,harap", [
    ("semua", ["anggota", "bu-mandiri", "koordinator", "pak-admin"]),
    ("belum_lembaga", ["bu-mandiri", "pak-admin"]),
    ("mandiri", ["bu-mandiri"]),
    ("di_lembaga", ["anggota", "koordinator"]),
])
def test_filter(kon, lembaga, saring, harap):
    assert [g.pengguna for g in G.daftar_guru(kon, AKUN, MENTAH, saring)] == harap


def test_filter_tak_dikenal_ditolak(kon):
    with pytest.raises(Q.InputQueryTidakSah):
        G.daftar_guru(kon, AKUN, MENTAH, "apa-saja")


def test_hitungan_chip(kon, lembaga):
    assert G.hitung_per_saring(kon, AKUN, MENTAH) == {"semua": 4, "belum_lembaga": 2, "mandiri": 1, "di_lembaga": 2, "nonaktif": 0}


def test_satu_guru_hanya_untuk_guru_yang_tampil(kon, lembaga):
    assert G.satu_guru(kon, AKUN, MENTAH, _id(2)).pengguna == "pak-admin"
    for bukan in (_id(3), _id(6), _id(7), _id(8), "akun_" + "f" * 32):
        assert G.satu_guru(kon, AKUN, MENTAH, bukan) is None


def test_guru_di_luar_batas_tabel_tetap_bisa_dikelola(kon, lembaga, monkeypatch):
    monkeypatch.setattr(G, "BATAS_BARIS", 2)
    assert [g.pengguna for g in G.daftar_guru(kon, AKUN, MENTAH)] == ["anggota", "bu-mandiri"]
    assert G.satu_guru(kon, AKUN, MENTAH, _id(2)).pengguna == "pak-admin"           # urutan ke-4
    assert G.hitung_per_saring(kon, AKUN, MENTAH)["semua"] == 4


def test_tanpa_kredensial_di_hasil(kon, lembaga):
    akun = [{**a, "garam": "RAHASIA", "kunci": "RAHASIA", "iterasi": 1} for a in AKUN]
    assert "RAHASIA" not in repr(G.daftar_guru(kon, akun, MENTAH))


def test_nonaktif_admin_hanya_di_chip_nonaktif_dan_tombstone_tersembunyi(kon, lembaga):
    marka = {"oleh": _id(7), "pada": 1_800_000_000}
    akun = AKUN + [_akun(9, "dinonaktifkan-admin", dinonaktifkan=True, nonaktif_admin=marka)]
    assert "dinonaktifkan-admin" not in [g.pengguna for g in G.daftar_guru(kon, akun, MENTAH)]
    for saring in ("belum_lembaga", "mandiri", "di_lembaga"):
        assert "dinonaktifkan-admin" not in [g.pengguna for g in G.daftar_guru(kon, akun, MENTAH, saring)]
    (g,) = G.daftar_guru(kon, akun, MENTAH, "nonaktif")        # tombstone "nonaktif" (id 6, tanpa marka) tidak ikut
    assert (g.pengguna, g.nonaktif, g.nonaktif_oleh, g.nonaktif_pada) == ("dinonaktifkan-admin", True, "admin-x", 1_800_000_000)
    assert G.hitung_per_saring(kon, akun, MENTAH) == {"semua": 4, "belum_lembaga": 2, "mandiri": 1, "di_lembaga": 2, "nonaktif": 1}
    assert G.satu_guru(kon, akun, MENTAH, _id(9)).nonaktif is True
    assert G.satu_guru(kon, akun, MENTAH, _id(6)) is None
