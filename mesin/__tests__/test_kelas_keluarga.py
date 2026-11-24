"""kelas_keluarga.tautkan_keluarga: admin menautkan dua anak sebagai satu keluarga. Data sintetis."""
import pytest

import kelas_dasar as k
import kelas_keluarga
import kelas_store
import pesanan_dasar as d
from kelas_kit import ADMIN, ADMIN_B, KINI, baris, db_kelas, kon_kelas  # noqa: F401


def tautkan(kon, a, b, *, admin=ADMIN, sekarang=KINI):
    return kelas_keluarga.tautkan_keluarga(kon, admin, a, b, sekarang)


def test_antarmuka_dibuka_juga_lewat_kelas_store():
    assert kelas_store.tautkan_keluarga is kelas_keluarga.tautkan_keluarga


def test_tautan_baru_membuat_keluarga_untuk_kedua_anak(kon_kelas):
    hasil = tautkan(kon_kelas, 1, 2)
    assert hasil["baru"] is True and hasil["keluarga_id"].startswith("kel_")
    isi = baris(kon_kelas, "kelas_keluarga")
    assert [(r[1], r[2], r[3], r[4]) for r in isi] == [
        (hasil["keluarga_id"], 1, ADMIN, KINI), (hasil["keluarga_id"], 2, ADMIN, KINI)]
    assert not kon_kelas.in_transaction


def test_tautan_ulang_idempoten_dalam_urutan_apa_pun(kon_kelas):
    pertama = tautkan(kon_kelas, 1, 2)
    assert tautkan(kon_kelas, 2, 1, admin=ADMIN_B) == {"keluarga_id": pertama["keluarga_id"], "baru": False}
    assert len(baris(kon_kelas, "kelas_keluarga")) == 2


def test_anak_baru_bergabung_ke_keluarga_yang_sudah_ada(kon_kelas):
    pertama = tautkan(kon_kelas, 1, 2)
    kedua = tautkan(kon_kelas, 3, 1)
    assert kedua == {"keluarga_id": pertama["keluarga_id"], "baru": True}
    assert {r[2] for r in baris(kon_kelas, "kelas_keluarga")} == {1, 2, 3}


def test_dua_keluarga_berbeda_tidak_dileburkan_dan_tidak_ada_efek(kon_kelas):
    tautkan(kon_kelas, 1, 2)
    tautkan(kon_kelas, 3, 4)
    sebelum = baris(kon_kelas, "kelas_keluarga")
    with pytest.raises(k.KelasKonflik):
        tautkan(kon_kelas, 2, 3)
    assert baris(kon_kelas, "kelas_keluarga") == sebelum


@pytest.mark.parametrize("a,b", [(1, 1), (0, 1), (1, 0), ("1", 2), (1, None), (True, 2), (-1, 2)])
def test_anak_tidak_sah_atau_sama_ditolak(kon_kelas, a, b):
    with pytest.raises(d.PesananDataTidakSah):
        tautkan(kon_kelas, a, b)
    assert baris(kon_kelas, "kelas_keluarga") == []


@pytest.mark.parametrize("admin", ["", "a b", None, "x" * 65])
def test_admin_tidak_sah_ditolak(kon_kelas, admin):
    with pytest.raises(d.PesananDataTidakSah):
        tautkan(kon_kelas, 1, 2, admin=admin)
    assert baris(kon_kelas, "kelas_keluarga") == []


def test_waktu_tidak_sah_ditolak(kon_kelas):
    with pytest.raises(d.PesananDataTidakSah):
        tautkan(kon_kelas, 1, 2, sekarang="kemarin")
    assert baris(kon_kelas, "kelas_keluarga") == []
