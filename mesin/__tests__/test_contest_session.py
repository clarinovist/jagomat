"""Perakit sesi Latihan Lomba: komposisi 8 PG + 2 isian, sebaran topik, urutan, dedup, posisi kunci."""
from collections import Counter
import random

import pytest

import contest_core as C
import contest_session as S

JUMLAH_SEED = 60
BESAR_DOMAIN = 5000
SESI_BERURUTAN = 6
KELUARGA_KEMBAR = {("operasi", 2, 0): "ops_kembar_0", ("operasi", 2, 1): "ops_kembar_1"}


def _fake(topik, jenis, tingkat, indeks, inggris=False, domain=BESAR_DOMAIN, keluarga=""):
    id_ = f"{C.AWALAN_ID[topik]}{jenis}_{tingkat}_{indeks}{'_en' if inggris else ''}"

    def sampler(rng):
        return {"n": rng.randint(1, domain)}

    def bangun(p):
        n = p["n"]
        pengecoh = () if jenis == C.JENIS_ISIAN else tuple(
            C.Pengecoh(str(n + k), f"geser {k}") for k in (1, 2, 3))
        return C.SoalLomba(
            template_id=id_, topik=topik, jenis=jenis, tingkat=tingkat, teks=f"Soal {id_}",
            svg="", kunci=str(n), pengecoh=pengecoh, pembahasan=("langkah",),
            parameter=C.kanonik(p), nilai=n, inggris=inggris)

    return C.Template(id=id_, topik=topik, jenis=jenis, tingkat=tingkat, sampler=sampler,
                      bangun=bangun, verifikator=lambda p: str(p["n"]), keluarga=keluarga)


def _pool(domain=BESAR_DOMAIN, dengan_isian=True, dengan_inggris=True):
    pool = []
    for topik in C.TOPIK:
        for tingkat, jumlah in ((1, 2), (2, 3), (3, 2)):
            pool += [_fake(topik, C.JENIS_PG, tingkat, i, domain=domain,
                           keluarga=KELUARGA_KEMBAR.get((topik, tingkat, i), ""))
                     for i in range(jumlah)]
        if dengan_isian:
            pool.append(_fake(topik, C.JENIS_ISIAN, 3, 0, domain=domain))
    if dengan_inggris:
        pool += [_fake("operasi", C.JENIS_PG, 2, 90 + i, inggris=True, domain=domain,
                       keluarga=f"ops_kembar_{i}")
                 for i in range(2)]
    return tuple(pool)


POOL = _pool()


@pytest.fixture(scope="module")
def sesi_banyak():
    return [S.rakit_sesi(seed, POOL, frozenset()) for seed in range(JUMLAH_SEED)]


def test_sesi_berisi_sepuluh_butir_bernomor_satu_sampai_sepuluh(sesi_banyak):
    for sesi in sesi_banyak:
        assert [b.nomor for b in sesi.butir] == list(range(1, 11))


def test_sesi_berisi_delapan_pilihan_ganda_dan_dua_isian(sesi_banyak):
    for sesi in sesi_banyak:
        hitung = Counter(b.soal.jenis for b in sesi.butir)
        assert hitung == {C.JENIS_PG: 8, C.JENIS_ISIAN: 2}


def test_setiap_topik_muncul_dua_atau_tiga_kali(sesi_banyak):
    for sesi in sesi_banyak:
        hitung = Counter(b.soal.topik for b in sesi.butir)
        assert set(hitung) == set(C.TOPIK)
        assert all(2 <= jumlah <= 3 for jumlah in hitung.values()), hitung


def test_template_tidak_berulang_dalam_satu_sesi(sesi_banyak):
    for sesi in sesi_banyak:
        ids = [b.soal.template_id for b in sesi.butir]
        assert len(set(ids)) == len(ids)


def test_urutan_dari_mudah_ke_sulit_tidak_pernah_menurun(sesi_banyak):
    for sesi in sesi_banyak:
        tingkat = [b.soal.tingkat for b in sesi.butir]
        assert tingkat == sorted(tingkat)


def test_sesi_memuat_soal_mudah_dan_soal_sulit(sesi_banyak):
    for sesi in sesi_banyak:
        hitung = Counter(b.soal.tingkat for b in sesi.butir)
        assert hitung[1] >= 2 and hitung[3] >= 2, hitung


def test_paling_banyak_satu_soal_berbahasa_inggris_per_sesi(sesi_banyak):
    for sesi in sesi_banyak:
        assert sum(1 for b in sesi.butir if b.soal.inggris) <= 1


def test_ada_sesi_yang_memuat_soal_inggris_bila_tersedia(sesi_banyak):
    assert any(b.soal.inggris for sesi in sesi_banyak for b in sesi.butir)


def test_posisi_kunci_pg_seimbang_dua_per_huruf_dan_cocok_dengan_pilihan(sesi_banyak):
    for sesi in sesi_banyak:
        pg = [b for b in sesi.butir if b.soal.jenis == C.JENIS_PG]
        assert sorted(Counter(b.posisi_kunci for b in pg).items()) == [(0, 2), (1, 2), (2, 2), (3, 2)]
        for butir in pg:
            assert len(butir.pilihan) == 4 and len(set(butir.pilihan)) == 4
            assert butir.pilihan[butir.posisi_kunci] == butir.soal.kunci


def test_butir_isian_tanpa_pilihan_dan_tanpa_posisi(sesi_banyak):
    for sesi in sesi_banyak:
        for butir in (b for b in sesi.butir if b.soal.jenis == C.JENIS_ISIAN):
            assert butir.pilihan == () and butir.gambar_pilihan == () and butir.posisi_kunci == -1


def test_gambar_pilihan_pg_teks_berisi_empat_string_kosong(sesi_banyak):
    for butir in sesi_banyak[0].butir:
        if butir.soal.jenis == C.JENIS_PG:
            assert butir.gambar_pilihan == ("",) * 4


def test_seed_sama_menghasilkan_sesi_sama():
    assert S.rakit_sesi(7, POOL, frozenset()) == S.rakit_sesi(7, POOL, frozenset())


def test_seed_berbeda_menghasilkan_sesi_berbeda():
    assert S.rakit_sesi(1, POOL, frozenset()) != S.rakit_sesi(2, POOL, frozenset())


def test_tanda_tangan_terlarang_tidak_dipakai_ulang():
    pertama = S.rakit_sesi(5, POOL, frozenset())
    terlarang = frozenset(C.tanda_tangan(b.soal) for b in pertama.butir)
    kedua = S.rakit_sesi(5, POOL, terlarang)   # seed sama, tetapi soal lama dilarang
    assert not terlarang & {C.tanda_tangan(b.soal) for b in kedua.butir}


def test_enam_sesi_berurutan_tidak_mengulang_soal_dalam_lima_sesi_terakhir():
    riwayat = []
    for seed in range(SESI_BERURUTAN):
        terlarang = frozenset().union(*riwayat[-S.RIWAYAT_SESI:]) if riwayat else frozenset()
        sesi = S.rakit_sesi(seed, POOL, terlarang)
        tanda = frozenset(C.tanda_tangan(b.soal) for b in sesi.butir)
        assert not tanda & terlarang
        riwayat.append(tanda)


def test_gagal_bila_tidak_ada_template_isian():
    with pytest.raises(S.GagalMerakitSesi):
        S.rakit_sesi(1, _pool(dengan_isian=False), frozenset())


def test_gagal_bila_semua_varian_template_terlarang():
    kecil = _pool(domain=1)     # tiap template hanya punya satu varian
    terlarang = frozenset(
        C.tanda_tangan(C.buat_soal(t, random.Random(0))) for t in kecil)
    with pytest.raises(S.GagalMerakitSesi):
        S.rakit_sesi(1, kecil, terlarang)


def test_sesi_tetap_terbentuk_tanpa_template_inggris():
    sesi = S.rakit_sesi(3, _pool(dengan_inggris=False), frozenset())
    assert len(sesi.butir) == 10


def test_template_sekeluarga_tidak_pernah_muncul_bersama_dalam_satu_sesi(sesi_banyak):
    keluarga = {t.id: (t.keluarga or t.id) for t in POOL}
    for sesi in sesi_banyak:
        ids = [keluarga[b.soal.template_id] for b in sesi.butir]
        assert len(set(ids)) == len(ids), ids


def test_gagal_bila_topik_hanya_punya_satu_keluarga_template():
    satu_keluarga = tuple(
        _fake(t.topik, t.jenis, t.tingkat, i, keluarga="sama") if t.topik == "operasi" else t
        for i, t in enumerate(POOL))
    with pytest.raises(S.GagalMerakitSesi):
        S.rakit_sesi(1, satu_keluarga, frozenset())
