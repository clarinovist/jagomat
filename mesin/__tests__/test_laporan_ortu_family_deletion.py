"""Penghapusan keluarga menghapus laporan orang tua (laporan_ortu) dan tautannya untuk anak target.

Siswa hanya dianonimkan, jadi cascade FK tidak berlaku. Tanpa penghapusan eksplisit, tautan lama tetap membuka isi
laporan (catatan Guru + hasil belajar anak) dengan nama samaran. Data sintetis. Sasaran mutation di
`test_family_deletion_laporan_ortu_mutation.py`.
"""
from __future__ import annotations

import pytest

import database
import family_deletion as hapus
import parent_report_http
import parent_report_store as toko
from test_family_deletion import _jalankan, _perintah, penyimpanan  # noqa: F401  (fixture bersama)

ISI = {"versi": 1, "topik": ["Pola Bilangan"], "tahap": {"nomor": 3, "label": "Latihan"},
       "langkah": "Coba sendiri beberapa soal pendek."}
SEKARANG = 4_102_444_800  # tahun 2100: tautan tidak kedaluwarsa selama tes


def _draf(kon, siswa_id):
    return toko.buat_draf(kon, siswa_id, "2026-11-01", "2026-11-30", ISI)


def _terbit(kon, siswa_id) -> str:
    """Satu laporan terbit (tautan aktif) untuk anak; mengembalikan token mentah."""
    lid = _draf(kon, siswa_id)
    toko.simpan_catatan(kon, siswa_id, lid, "Catatan sintetis Guru untuk orang tua.")
    return toko.terbitkan(kon, siswa_id, lid, "Guru Uji", sekarang=SEKARANG - 10)


def _jumlah(kon, tabel, siswa_ids):
    q = ",".join("?" * len(siswa_ids))
    return kon.execute("SELECT COUNT(*) FROM %s WHERE siswa_id IN (%s)" % (tabel, q), tuple(siswa_ids)).fetchone()[0]


class _Penangan:
    """Pengganti penangan HTTP: merekam jawaban rute baca tautan."""

    def __init__(self):
        self.jawaban = None

    def _kirim_tautan(self, isi, kode, csp=None):
        self.jawaban = (bytes(isi), kode, csp)


def _buka_route(monkeypatch, jalur, token):
    asli = database.buka
    monkeypatch.setattr(database, "buka", lambda *a, **k: asli(jalur))
    penangan = _Penangan()
    assert parent_report_http.tangani_get(penangan, "/laporan-ortu/" + token) is True
    return penangan.jawaban


def test_bundle_hasil_menghapus_laporan_dan_tautan_anak_target_saja(penyimpanan):
    paths, _bundle, hasil, target_sid, lain_sid, *_ = penyimpanan
    with database.buka(paths["belajar"]) as kon:
        target_kedua = database.tambah_siswa(kon, "Anak Target Dua", "P3", pemilik="keluarga-target")
        _terbit(kon, target_sid)
        _draf(kon, target_kedua)
        token_lain = _terbit(kon, lain_sid)
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id="akun_" + "b" * 32)

    _jalankan(penyimpanan, _perintah(inv))

    with database.buka(hasil / "bundle" / "latihan.db") as kon:
        for tabel in ("laporan_ortu", "tautan_laporan"):
            assert _jumlah(kon, tabel, [target_sid, target_kedua]) == 0, tabel
        assert _jumlah(kon, "laporan_ortu", [lain_sid]) == 1
        assert _jumlah(kon, "tautan_laporan", [lain_sid]) == 1
        assert toko.ambil_dengan_token(kon, token_lain, SEKARANG) is not None
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
    # Live tidak tersentuh: bundle hasil hanya kandidat cutover.
    with database.buka(paths["belajar"]) as kon:
        assert _jumlah(kon, "laporan_ortu", [target_sid, target_kedua]) == 2
        assert _jumlah(kon, "tautan_laporan", [target_sid]) == 1


def test_bundle_hasil_tanpa_tabel_laporan_ortu_tetap_berhasil(penyimpanan):
    """Basis lama tanpa tabel (belum migrasi aditif) tidak menggagalkan hapus."""
    paths, *_ = penyimpanan
    with database.buka(paths["belajar"]) as kon:
        kon.execute("DROP TABLE tautan_laporan")
        kon.execute("DROP TABLE laporan_ortu")
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id="akun_" + "b" * 32)

    assert _jalankan(penyimpanan, _perintah(inv)).status == "succeeded"


def test_tautan_lama_setelah_penghapusan_dijawab_sama_dengan_token_tak_dikenal(penyimpanan, monkeypatch):
    paths, _bundle, hasil, target_sid, _lain, *_ = penyimpanan
    with database.buka(paths["belajar"]) as kon:
        token = _terbit(kon, target_sid)
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id="akun_" + "b" * 32)
    # Kontrol positif: sebelum dihapus, tautan membuka laporan (200).
    sebelum = _buka_route(monkeypatch, paths["belajar"], token)
    assert sebelum[1] == 200

    _jalankan(penyimpanan, _perintah(inv))

    bundle = hasil / "bundle" / "latihan.db"
    sesudah = _buka_route(monkeypatch, bundle, token)
    asing = _buka_route(monkeypatch, bundle, "x" * 43)
    assert sesudah == asing and sesudah[1] == 404
    assert b"Catatan sintetis" not in sesudah[0]


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


def test_hapus_laporan_ortu_target_saja_dan_tanpa_siswa_tidak_error(kon):
    target = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('T','P1','keluarga-a')").lastrowid
    lain = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('L','P1','keluarga-b')").lastrowid
    _terbit(kon, target)
    _terbit(kon, lain)

    hapus._hapus_laporan_ortu(kon, ())
    assert _jumlah(kon, "laporan_ortu", [target, lain]) == 2
    hapus._hapus_laporan_ortu(kon, (target,))

    assert _jumlah(kon, "laporan_ortu", [target]) == 0 and _jumlah(kon, "tautan_laporan", [target]) == 0
    assert _jumlah(kon, "laporan_ortu", [lain]) == 1 and _jumlah(kon, "tautan_laporan", [lain]) == 1


def test_hapus_laporan_ortu_tanpa_tabel_dilewati_per_tabel(kon):
    target = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('T','P1','keluarga-a')").lastrowid
    _draf(kon, target)
    kon.execute("DROP TABLE tautan_laporan")
    hapus._hapus_laporan_ortu(kon, (target,))
    assert _jumlah(kon, "laporan_ortu", [target]) == 0
    kon.execute("DROP TABLE laporan_ortu")
    hapus._hapus_laporan_ortu(kon, (target,))
