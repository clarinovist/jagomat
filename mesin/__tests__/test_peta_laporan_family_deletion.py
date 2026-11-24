"""Penghapusan keluarga menghapus laporan Peta anak target (draf DAN terbit); siswa hanya dianonimkan, cascade tak berlaku."""
from __future__ import annotations

import pytest

import database
import family_deletion as hapus
import peta_laporan_store as store
from test_family_deletion import _jalankan, _perintah, penyimpanan  # noqa: F401  (fixture bersama)

ISI = {
    "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
    "jumlah_soal": 15, "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5}],
    "kuat": ["Berhitung"], "perlu_dilatih": [], "ringkasan_perlu": [],
}
CATATAN = "Catatan sintetis Guru tentang anak ini."


def _laporan(kon, siswa_id, *, terbit):
    store.buat_draf(kon, siswa_id, "keluarga-target", ISI, 1_800_000_000)
    if terbit:
        store.simpan_catatan(kon, siswa_id, CATATAN)
        store.terbitkan(kon, siswa_id, "keluarga-target", 1_800_000_100)


def _jumlah(kon, siswa_ids):
    q = ",".join("?" * len(siswa_ids))
    return kon.execute("SELECT COUNT(*) FROM peta_laporan WHERE siswa_id IN (%s)" % q, tuple(siswa_ids)).fetchone()[0]


def test_bundle_hasil_menghapus_laporan_peta_draf_dan_terbit_anak_target_saja(penyimpanan):
    paths, _bundle, hasil, target_sid, lain_sid, *_ = penyimpanan
    with database.buka(paths["belajar"]) as kon:
        target_kedua = database.tambah_siswa(kon, "Anak Target Dua", "P3", pemilik="keluarga-target")
        _laporan(kon, target_sid, terbit=True)
        _laporan(kon, target_kedua, terbit=False)
        _laporan(kon, lain_sid, terbit=True)
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id="akun_" + "b" * 32)

    _jalankan(penyimpanan, _perintah(inv))

    with database.buka(hasil / "bundle" / "latihan.db") as kon:
        assert _jumlah(kon, [target_sid, target_kedua]) == 0
        assert _jumlah(kon, [lain_sid]) == 1
        assert store.terbit_terakhir(kon, lain_sid)["catatan"] == CATATAN
    # Live tidak tersentuh: bundle hasil hanya kandidat cutover.
    with database.buka(paths["belajar"]) as kon:
        assert _jumlah(kon, [target_sid, target_kedua]) == 2


def test_bundle_hasil_tanpa_tabel_laporan_peta_tetap_berhasil(penyimpanan):
    """Basis lama tanpa tabel (belum migrasi aditif) tidak menggagalkan hapus."""
    paths, *_ = penyimpanan
    with database.buka(paths["belajar"]) as kon:
        kon.execute("DROP TABLE peta_laporan")
    inv = hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                        paths["ai"], paths["pendamping"], target_id="akun_" + "b" * 32)

    assert _jalankan(penyimpanan, _perintah(inv)).status == "succeeded"


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


def test_hapus_peta_laporan_target_saja_dan_tanpa_siswa_tidak_error(kon):
    target = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('T','P1','keluarga-a')").lastrowid
    lain = kon.execute("INSERT INTO siswa(nama,tingkat,pemilik) VALUES ('L','P1','keluarga-b')").lastrowid
    _laporan(kon, target, terbit=True)
    _laporan(kon, lain, terbit=False)

    hapus._hapus_peta_laporan(kon, ())
    assert _jumlah(kon, [target, lain]) == 2
    hapus._hapus_peta_laporan(kon, (target,))

    assert _jumlah(kon, [target]) == 0 and _jumlah(kon, [lain]) == 1
