"""Hak paket dan kalender Pendamping dengan snapshot sintetis, tanpa clock global."""
from dataclasses import replace
from datetime import datetime

import pytest

import assistant_entitlement as d
import subscription_packages as p

AKUN = "akun_" + "a" * 32
LAIN = "akun_" + "b" * 32


def waktu(tanggal):
    return int(datetime.fromisoformat(tanggal).replace(tzinfo=p.WIB).timestamp())


T0 = waktu("2023-12-31T09:30:00")


def snapshot(kode="jago_pro", penagihan="tahunan", jangkar=None, indeks=0):
    jangkar = jangkar if jangkar is not None else p.akhir_coba(T0)
    kuota = p.ambil_paket(kode).kuota
    g = d.GrantHak(AKUN, "inv_" + "1" * 32, kode, penagihan,
                   p.batas_bulan(jangkar, indeks),
                   p.batas_bulan(jangkar, indeks + p.jumlah_bulan(penagihan)),
                   jangkar, indeks, kuota.balasan, kuota.foto)
    return d.SnapshotHak(AKUN, T0, T0 + 1, (g,))


def hak(s, sekarang, fitur=d.FITUR[0], **kwargs):
    return d.selesaikan(AKUN, s, fitur=fitur, sekarang=sekarang, **kwargs)


def test_trial_tepat_deadline_prepay_dan_tidak_diulang():
    s = snapshot()
    akhir = p.akhir_coba(T0)
    awal = hak(s, T0 + 1)
    assert awal.status == "trial_aktif" and awal.limit == awal.tersisa == 10
    assert awal.entitlement_mulai == T0 and awal.entitlement_akhir == T0 + 30 * 86400
    assert hak(s, akhir - 1).status == "trial_aktif"
    assert hak(s, akhir).status == "pro_aktif"
    # Adopsi baru tidak membuat trial mulai ulang dari waktu transisi.
    terlambat = replace(s, transisi_mulai=akhir + 1, grants=())
    assert hak(terlambat, akhir + 1).status == "akses_berakhir"
    assert hak(s, T0 + 1, d.FITUR[1]).limit == 2
    assert awal.isi_ulang == akhir  # Sudah ada grant Pro yang menjamin.
    assert hak(replace(s, grants=()), T0 + 1).isi_ulang is None


@pytest.mark.parametrize("kode,status,limit", [("jago", "jago_tanpa_ai", 0), ("jago_pro", "pro_aktif", 50)])
def test_paket_limit_dan_enforcement_default_off(kode, status, limit):
    s = snapshot(kode)
    h = hak(s, s.grants[0].mulai)
    assert (h.status, h.limit) == (status, limit)
    assert h.boleh and not h.penegakan
    assert hak(s, s.grants[0].mulai, penegakan=True).boleh == (kode == "jago_pro")
    assert hak(s, s.grants[0].akhir).status == "akses_berakhir"


@pytest.mark.parametrize("jangkar", ["2024-01-31T09:30:00", "2024-02-29T12:00:00", "2025-01-31T23:59:00"])
def test_tahunan_refill_bulanan_leap_akhirbulan(jangkar):
    anchor = waktu(jangkar)
    s = snapshot(jangkar=anchor)
    ids = set()
    for n in range(12):
        kiri, kanan = p.batas_bulan(anchor, n), p.batas_bulan(anchor, n + 1)
        h = hak(s, kiri)
        assert h.status == "pro_aktif" and h.limit == h.tersisa == 50
        assert (h.jendela_mulai, h.jendela_akhir) == (kiri, kanan)
        assert hak(s, kanan - 1).jendela_id == h.jendela_id
        assert h.isi_ulang == (kanan if n < 11 else None)
        assert hak(s, kiri, d.FITUR[1]).limit == 5
        ids.add(h.jendela_id)
    assert len(ids) == 12
    assert hak(s, p.batas_bulan(anchor, 12)).status == "akses_berakhir"


def test_perpanjangan_jangkar_asli_dan_refill_hanya_grant_terjamin():
    anchor = waktu("2024-01-31T09:30:00")
    s = snapshot(penagihan="bulanan", jangkar=anchor)
    g = s.grants[0]
    h = hak(s, g.mulai)
    assert h.isi_ulang is None  # Bukan janji refill tanpa pembayaran.
    berikut = replace(g, invoice_id="inv_" + "2" * 32, mulai=g.akhir,
                      akhir=p.batas_bulan(anchor, 2), indeks_bulan=1)
    s = replace(s, grants=(g, berikut))
    assert hak(s, g.mulai).isi_ulang == g.akhir
    assert hak(s, g.akhir).jendela_akhir == waktu("2024-03-31T09:30:00")


def test_habis_satu_fitur_tidak_mencabut_fitur_lain_dan_tidak_rollover():
    s = snapshot()
    awal = s.grants[0].mulai
    h = hak(s, awal)
    pakai = (d.Pemakaian(h.jendela_id, h.fitur, 49, 1),)
    habis = hak(s, awal, pemakaian=pakai, penegakan=True)
    assert habis.status == "kuota_habis" and not habis.boleh
    assert (habis.digunakan, habis.direservasi, habis.tersisa) == (49, 1, 0)
    assert hak(s, awal, d.FITUR[1], pemakaian=pakai).tersisa == 5
    assert hak(s, h.jendela_akhir, pemakaian=pakai).tersisa == 50


def test_belum_transisi_dan_hak_lama_tidak_dikarang_sebagai_pro():
    assert hak(d.SnapshotHak(AKUN), T0).status == "belum_ditransisikan"
    assert hak(d.SnapshotHak(AKUN, T0), T0).status == "belum_ditransisikan"
    akhir = p.akhir_coba(T0)
    s = d.SnapshotHak(AKUN, T0, T0 + 1, periode_lama=((akhir, akhir + 1234),))
    assert hak(s, akhir).status == "belum_ditransisikan"


@pytest.mark.parametrize("ubah", [
    {"akun_id": LAIN}, {"terverifikasi": False}, {"trial_mulai": True},
    {"transisi_mulai": T0 - 1}, {"transisi_mulai": T0 + 100},
    {"grants": []}, {"periode_lama": ((T0, T0 + 1),)},
])
def test_snapshot_rusak_failclosed(ubah):
    assert hak(replace(snapshot(), **ubah), T0 + 1, penegakan=True).status == "storage_tidak_terverifikasi"


@pytest.mark.parametrize("ubah", [
    {"akun_id": LAIN}, {"balasan": 500}, {"foto": True}, {"versi": "asing"},
    {"akhir": T0}, {"mulai": T0}, {"indeks_bulan": True}, {"penagihan": "harian"},
])
def test_grant_rusak_failclosed(ubah):
    s = snapshot()
    s = replace(s, grants=(replace(s.grants[0], **ubah),))
    h = hak(s, p.akhir_coba(T0), penegakan=True)
    assert h.status == "storage_tidak_terverifikasi" and not h.boleh


@pytest.mark.parametrize("digunakan,direservasi", [(-1, 0), (0, -1), (51, 0), (49, 2), (True, 0)])
def test_counter_rusak_failclosed(digunakan, direservasi):
    s = snapshot()
    now = s.grants[0].mulai
    h = hak(s, now)
    pakai = (d.Pemakaian(h.jendela_id, h.fitur, digunakan, direservasi),)
    assert hak(s, now, pemakaian=pakai).status == "storage_tidak_terverifikasi"


def test_hash_pemakaian_nonhex_failclosed_bukan_jatah_utuh():
    s = snapshot()
    pakai = (d.Pemakaian("z" * 64, d.FITUR[0], 50, 0),)
    h = hak(s, s.grants[0].mulai, pemakaian=pakai, penegakan=True)
    assert h.status == "storage_tidak_terverifikasi" and not h.boleh


@pytest.mark.parametrize("kwargs", [{"fitur": "cerita"}, {"sekarang": True}, {"penegakan": 1}])
def test_parameter_pemrograman_invalid_ditolak(kwargs):
    args = dict(fitur=d.FITUR[0], sekarang=T0 + 1)
    args.update(kwargs)
    with pytest.raises(ValueError):
        d.selesaikan(AKUN, snapshot(), **args)
