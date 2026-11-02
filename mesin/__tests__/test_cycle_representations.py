"""Bukti teks dan gambar tidak boleh menggenapkan syarat satu sama lain."""
from dataclasses import replace
from datetime import date
import pytest
import learning_cycle as lc
from learning_journey import perjalanan_belajar

FOKUS = ("korek_api", "K", None)
PUTARAN = lc.PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS,))


def outcome(mode="teks-v1", benar=True):
    return lc.OutcomeSiklus("korek_api", benar, None if benar else "K",
        cek_pemahaman="bisa_menjelaskan", target_fokus=FOKUS,
        mode_representasi=mode, fingerprint_penyajian="a" * 64)


def sesi(nomor, mode="teks-v1", *, tujuan="evaluasi", benar=True, jumlah=4, **lebih):
    return lc.SesiSiklus(nomor, 1, "P3", tujuan, date(2026, 9, nomor),
        selesai="sah", dikonfirmasi="sah", putaran_id=1,
        outcomes=tuple(outcome(mode, benar) for _ in range(jumlah)),
        target_fokus=(FOKUS,), **lebih)


def bukti(*semua):
    return lc.BuktiSiklus(1, "P3", semua, (PUTARAN,),
        pendekatan_tersedia=((FOKUS, ("cara-1", "cara-2", "cara-3")),))


def test_probe_campuran_tidak_melengkapi_minimum_kelulusan():
    campuran = (outcome(), outcome(), outcome("korek-v2"), outcome("korek-v2"))
    assert not lc._lulus(campuran, 4)
    assert lc._lulus(tuple(outcome("korek-v2") for _ in range(4)), 4)


def test_pemetaan_dua_representasi_bukan_kelemahan_berulang():
    awal = sesi(1, tujuan="pemetaan", benar=False)
    baru = sesi(2, "korek-v2", tujuan="pemetaan", benar=False)
    ringkas = lc._ringkas_kandidat((awal, baru))
    assert ringkas == ((FOKUS, 1, baru.tanggal),)
    assert lc._ringkas_kandidat((awal, replace(baru, outcomes=awal.outcomes)))[0][1] == 2


def test_dua_gagal_berbeda_representasi_bukan_gagal_kedua():
    sumber = bukti(sesi(1, benar=False), sesi(2, "korek-v2", benar=False))
    hasil = lc.rencana_berikutnya(sumber, 1, date(2026, 9, 10))
    assert hasil.tindakan == "intervensi"
    assert len(lc._evaluasi_fokus(sumber, PUTARAN, FOKUS)) == 1


def test_evaluasi_campuran_tidak_dihitung_sebagai_lulus_atau_gagal_sah():
    campuran = replace(sesi(1), outcomes=(outcome(), outcome(), outcome("korek-v2"), outcome("korek-v2")))
    assert lc._evaluasi_fokus(bukti(campuran), PUTARAN, FOKUS) == ()


def test_checkpoint_lintas_representasi_tidak_mewarisi_evaluasi_teks():
    awal = sesi(1)
    bagian = tuple(sesi(i, "korek-v2", tujuan="checkpoint", jumlah=2,
                        bagian_checkpoint=i-1, occurrence=1) for i in (2, 3))
    sumber = bukti(awal, *bagian)
    assert lc._checkpoint_sukses(sumber, PUTARAN, FOKUS)[0] is None
    hasil = lc.rencana_berikutnya(sumber, 1, date(2026, 9, 10))
    assert hasil.putaran is not None
    assert hasil.putaran.fokus[0].status not in {"bertahan", "mulai_membaik"}


def test_checkpoint_dua_bagian_berbeda_mode_tidak_digabung():
    sumber = bukti(sesi(1, "korek-v2"),
        sesi(2, tujuan="checkpoint", jumlah=2, bagian_checkpoint=1, occurrence=1),
        sesi(3, "korek-v2", tujuan="checkpoint", jumlah=2, bagian_checkpoint=2, occurrence=1))
    assert lc._checkpoint_sukses(sumber, PUTARAN, FOKUS)[0] is None


def test_checkpoint_sama_mode_lulus_dan_histori_tidak_dimutasi():
    # Checkpoint baru sah sebagai retensi setelah jeda 28 hari dari evaluasi.
    bagian = tuple(
        replace(
            sesi(i, "korek-v2", tujuan="checkpoint", jumlah=2,
                 bagian_checkpoint=i - 1, occurrence=1),
            tanggal=date(2026, 9, 27 + i),
        )
        for i in (2, 3)
    )
    sumber = bukti(sesi(1, "korek-v2"), *bagian)
    sebelum = repr(sumber)
    assert lc._checkpoint_sukses(sumber, PUTARAN, FOKUS)[0] == date(2026, 9, 30)
    hasil = perjalanan_belajar(sumber, 1, date(2026, 10, 1))
    assert hasil.fokus[0].tahap == "bertahan"
    assert hasil == perjalanan_belajar(sumber, 1, date(2026, 10, 1))
    assert repr(sumber) == sebelum


@pytest.mark.parametrize("ubah", ({"dikonfirmasi": None}, {"dibatalkan": "batal"},
    {"siswa_id": 999}, {"level": "P4"}, {"putaran_id": 999}, {"tujuan": "bebas"}))
def test_sesi_tidak_sah_tidak_mengganti_representasi_aktif(ubah):
    lama = sesi(1)
    asing = replace(sesi(2, "korek-v2"), **ubah)
    hasil = lc._evaluasi_fokus(bukti(lama, asing), PUTARAN, FOKUS)
    assert tuple(s.id for s, baik in hasil if baik) == (1,)


def test_probe_terbaru_dari_penguat_bukan_mewarisi_kelulusan_lama():
    sumber = bukti(sesi(1), sesi(2, "korek-v2", tujuan="penguatan",
        selesai_pada=date(2026, 9, 2), dikonfirmasi_pada=date(2026, 9, 2)))
    assert lc._evaluasi_fokus(sumber, PUTARAN, FOKUS) == ()
    assert perjalanan_belajar(sumber, 1, date(2026, 9, 5)).fokus[0].tahap != "mulai_membaik"


@pytest.mark.parametrize("mode", ("", "tidak-diketahui", "teks", "teks-v0", "ＴＥＫＳ-v1"))
def test_provenance_tidak_dikenal_tidak_dianggap_bukti_teks(mode):
    contoh = tuple(outcome(mode) for _ in range(4))
    assert not lc._lulus(contoh, 4)
    assert lc._evaluasi_fokus(bukti(sesi(1, mode)), PUTARAN, FOKUS) == ()


def test_histori_putaran_teks_tetap_ada_setelah_putaran_visual():
    lama = sesi(1)
    baru = replace(sesi(3, "korek-v2"), putaran_id=2)
    penutup = lc.KejadianSiklus(1, "putaran_ditutup", date(2026, 9, 2), putaran_id=1)
    sumber = replace(bukti(lama, baru),
        putaran=(PUTARAN, replace(PUTARAN, id=2, dibuka=date(2026, 9, 3))),
        kejadian=(penutup,))
    sebelum = repr(sumber)
    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 10))
    assert hasil.histori[0].id == 1
    assert hasil.histori[0].perjalanan_fokus[0].tahap == "mulai_membaik"
    assert hasil.fokus[0].tahap == "mulai_membaik"
    assert repr(sumber) == sebelum


def test_checkpoint_parsial_sebelum_evaluasi_baru_tidak_diteruskan():
    sumber = bukti(sesi(1),
        sesi(2, "korek-v2", tujuan="checkpoint", jumlah=2, bagian_checkpoint=1, occurrence=1),
        sesi(3, "korek-v2"))
    assert lc._checkpoint_sukses(sumber, PUTARAN, FOKUS) == (None, ())
