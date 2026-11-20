"""Keselarasan pemetaan CP Kurikulum Merdeka dengan katalog kurikulum."""
import ast
import re
import sys
from pathlib import Path

import kurikulum_cp as cp
import kurikulum_katalog as katalog

POLA_ID = re.compile(r"^[ABCD]\.(bilangan|aljabar|pengukuran|geometri|data)\.[1-9][0-9]*$")


def _semua_grup():
    return {(e.topik_id, kode) for e in katalog.KATALOG for kode, _nama, _pola in e.grup}


def test_setiap_grup_katalog_punya_entri_cp_dan_tidak_ada_entri_asing():
    assert set(cp.CP_PER_GRUP) == _semua_grup()


def test_id_butir_unik_berpola_dan_konsisten_dengan_fase_elemen():
    ids = [b.id for b in cp.CAPAIAN]
    assert len(ids) == len(set(ids))
    for b in cp.CAPAIAN:
        assert POLA_ID.match(b.id), b.id
        fase, elemen, _ = b.id.split(".")
        assert (b.fase, b.elemen) == (fase, elemen)
        assert b.fase in cp.FASE and b.elemen in cp.ELEMEN
        assert b.teks.strip() == b.teks and "  " not in b.teks and b.teks


def test_pemetaan_hanya_merujuk_butir_dikenal_dengan_kecocokan_sah_tanpa_ganda():
    for grup, isi in cp.CP_PER_GRUP.items():
        dirujuk = [cid for cid, _ in isi]
        assert len(dirujuk) == len(set(dirujuk)), grup
        for cid, kecocokan in isi:
            assert cp.butir(cid).id == cid, grup
            assert kecocokan in cp.KECOCOKAN, (grup, kecocokan)


def test_grup_inti_kelas_1_sampai_5_terpetakan_ke_cp_sd():
    for topik in ("bilangan-dasar", "bilangan-sekolah", "berhitung-sekolah"):
        for (t, kode), isi in cp.CP_PER_GRUP.items():
            if t == topik:
                assert any(cp.butir(cid).fase in "ABC" for cid, _ in isi), (t, kode)


def test_butir_tanpa_grup_adalah_selisih_cakupan():
    terpakai = {cid for isi in cp.CP_PER_GRUP.values() for cid, _ in isi}
    celah = cp.butir_tanpa_grup()
    assert {b.id for b in celah} == {b.id for b in cp.CAPAIAN} - terpakai
    assert [b.id for b in celah] == [b.id for b in cp.CAPAIAN if b.id not in terpakai]


def test_butir_tak_dikenal_menolak():
    try:
        cp.butir("Z.bilangan.1")
    except KeyError:
        return
    raise AssertionError("butir tak dikenal harus KeyError")


def test_modul_cp_hanya_mengimpor_stdlib():
    sumber = Path(cp.__file__).read_text(encoding="utf-8")
    nama = set()
    for simpul in ast.walk(ast.parse(sumber)):
        if isinstance(simpul, ast.Import):
            nama |= {a.name.split(".")[0] for a in simpul.names}
        elif isinstance(simpul, ast.ImportFrom) and simpul.module:
            nama.add(simpul.module.split(".")[0])
    assert nama <= set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else nama <= {
        "__future__", "dataclasses", "typing"}
