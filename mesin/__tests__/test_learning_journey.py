"""Kontrak proyeksi perjalanan belajar untuk laporan Fase 5."""

from __future__ import annotations

import dataclasses
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning_cycle import (  # noqa: E402
    BuktiSiklus,
    KejadianSiklus,
    OutcomeSiklus,
    PutaranSiklus,
    SesiSiklus,
    rencana_berikutnya,
)
from learning_journey import (  # noqa: E402
    BuktiFokusPerjalanan,
    FokusPerjalanan,
    HistoriPutaran,
    PerjalananBelajar,
    perjalanan_belajar,
)


FOKUS_A = ("deret", "K", "malrule-a")
FOKUS_B = ("deret", "K", "malrule-b")


def _outcome(
    fokus=FOKUS_A,
    *,
    benar=False,
    kode=None,
    paham=None,
    target=True,
):
    if kode is None and not benar:
        kode = fokus[1]
    return OutcomeSiklus(
        fokus[0],
        benar,
        kode,
        fokus[2] if kode else None,
        cek_pemahaman=paham,
        target_fokus=fokus if target else None,
    )


def _sesi(
    identitas,
    tanggal,
    *,
    tujuan="pemetaan",
    putaran: int | None = 1,
    siswa=1,
    level="P3",
    fokus=FOKUS_A,
    outcomes=None,
    selesai=True,
    konfirmasi=True,
    konfirmasi_id=None,
    dibatalkan=None,
    bagian=None,
    occurrence=None,
):
    if outcomes is None:
        outcomes = (_outcome(fokus),)
    target = (fokus,) if tujuan != "pemetaan" else ()
    tanggal_domain = date.fromisoformat(tanggal)
    return SesiSiklus(
        identitas,
        siswa,
        level,
        tujuan,
        tanggal_domain,
        dibuat=tanggal + " 08:00:00",
        selesai=tanggal + " 09:00:00" if selesai else None,
        dikonfirmasi=tanggal + " 10:00:00" if konfirmasi else None,
        putaran_id=putaran,
        bagian_checkpoint=bagian,
        dibatalkan=dibatalkan,
        outcomes=tuple(outcomes),
        target_fokus=target,
        occurrence=occurrence,
        konfirmasi_id=konfirmasi_id,
        selesai_pada=tanggal_domain if selesai else None,
        dikonfirmasi_pada=tanggal_domain if konfirmasi else None,
    )


def _event(
    identitas,
    jenis,
    tanggal,
    *,
    putaran=1,
    sesi=None,
    konfirmasi=None,
    fokus=None,
    **data,
):
    if fokus is not None:
        data["fokus"] = fokus
    return KejadianSiklus(
        identitas,
        jenis,
        date.fromisoformat(tanggal),
        putaran,
        sesi,
        konfirmasi,
        data=tuple(sorted(data.items())),
    )


def _bukti(*sesi, putaran=None, kejadian=(), level="P3", pendekatan=()):
    if putaran is None:
        putaran = (PutaranSiklus(1, 1, level, date(2026, 9, 1), (FOKUS_A,)),)
    return BuktiSiklus(
        1,
        level,
        tuple(sesi),
        tuple(putaran),
        tuple(kejadian),
        tuple(pendekatan),
    )


def _event_intervensi(fokus=FOKUS_A, identitas=1, putaran=1):
    return _event(
        identitas,
        "intervensi_selesai",
        "2026-09-03",
        putaran=putaran,
        fokus=fokus,
        pendekatan_id="visual-1",
    )


def _evaluasi(identitas, fokus=FOKUS_A, *, lulus=True, tanggal="2026-09-10"):
    outcomes = tuple(
        _outcome(
            fokus,
            benar=lulus,
            kode=None if lulus else "H",
            paham="bisa_menjelaskan",
        )
        for _ in range(4)
    )
    return _sesi(
        identitas,
        tanggal,
        tujuan="evaluasi",
        fokus=fokus,
        outcomes=outcomes,
    )


def _checkpoint(awal_id, fokus=FOKUS_A):
    outcomes = tuple(
        _outcome(fokus, benar=True, kode=None, paham="bisa_menjelaskan")
        for _ in range(2)
    )
    return tuple(
        _sesi(
            awal_id + bagian - 1,
            "2026-10-%02d" % (5 + bagian),
            tujuan="checkpoint",
            fokus=fokus,
            outcomes=outcomes,
            bagian=bagian,
            occurrence=1,
        )
        for bagian in (1, 2)
    )


def test_histori_per_fokus_mempertahankan_hasil_sebelum_kambuh():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A, FOKUS_B))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 10, 9), (FOKUS_A,))
    sesi = (_evaluasi(4),) + _checkpoint(5)
    sumber = _bukti(
        *sesi, putaran=(lama, baru),
        kejadian=(_event(20, "putaran_ditutup", "2026-10-09"),),
    )
    hasil = perjalanan_belajar(sumber, 1, date(2026, 10, 10))
    histori = hasil.histori[0].perjalanan_fokus
    assert histori[0].kunci == FOKUS_A
    assert histori[1].kunci == FOKUS_B
    assert histori[0].tahap == "bertahan"
    assert histori[1].tahap == "perlu_dipelajari"
    assert [b.hasil for b in histori[0].bukti] == ["mulai_membaik", None, "bertahan"]
    assert histori[1].bukti == ()
    assert hasil.fokus[0].tahap == "perlu_dipelajari"


def test_kekambuhan_aktif_tetap_menampilkan_bukti_bertahan_sebelumnya():
    sesi = (_evaluasi(4),) + _checkpoint(5) + (_sesi(7, "2026-10-09"),)
    hasil = perjalanan_belajar(_bukti(*sesi), 1, date(2026, 10, 10))
    assert hasil.rekomendasi.tindakan == "putaran_baru"
    assert hasil.fokus[0].tahap == "perlu_dipelajari"
    assert "bertahan" in tuple(item.hasil for item in hasil.fokus[0].bukti)


def test_checkpoint_occurrence_baru_tidak_meminjam_hasil_hari_yang_sama():
    pasangan = tuple(dataclasses.replace(sesi, tanggal=date(2026, 10, 7))
                     for sesi in _checkpoint(5))
    lanjutan = dataclasses.replace(pasangan[0], id=7, occurrence=2)
    hasil = perjalanan_belajar(
        _bukti(_evaluasi(4), *pasangan, lanjutan), 1, date(2026, 10, 8)
    )
    terakhir = next(b for b in hasil.fokus[0].bukti if b.sesi_id == 7)
    assert terakhir.hasil is None


def test_histori_tidak_memuat_putaran_siswa_lain():
    asing = PutaranSiklus(3, 999, "P3", date(2026, 8, 1), (FOKUS_B,))
    sumber = _bukti(putaran=(asing,), kejadian=(
        _event(1, "putaran_ditutup", "2026-08-10", putaran=3),
    ))
    assert perjalanan_belajar(sumber, 1).histori == ()


def test_proyeksi_immutable_dan_pemblokir_tidak_menghilangkan_status_fokus():
    pemetaan = _sesi(1, "2026-09-01")
    belum_selesai = _sesi(
        2,
        "2026-09-04",
        tujuan="latihan_terbimbing",
        selesai=False,
        konfirmasi=False,
    )
    sumber = _bukti(pemetaan, belum_selesai)

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert isinstance(hasil, PerjalananBelajar)
    assert hasil.rekomendasi.tindakan == "lanjutkan_sesi"
    assert hasil.rekomendasi.putaran is None
    assert hasil.fokus[0].kunci == FOKUS_A
    assert hasil.fokus[0].tahap == "perlu_dipelajari"
    assert hasil.fokus[0].bukti == (
        BuktiFokusPerjalanan(
            date(2026, 9, 1),
            1,
            "pemetaan",
            (),
            "terkonfirmasi",
        ),
    )
    assert sumber.sesi[0].outcomes[0].kode_final == "K"
    with pytest.raises(dataclasses.FrozenInstanceError):
        hasil.fokus[0].tahap = "bertahan"


def test_ringkasan_hanya_menyebut_pemahaman_dari_evaluasi_relevan_terbaru():
    from report_summary import render_ringkasan

    lama_ragu = _sesi(
        4, "2026-09-08", tujuan="evaluasi",
        outcomes=tuple(
            _outcome(FOKUS_A, benar=True, kode=None, paham="ragu")
            for _ in range(4)
        ),
    )
    terbaru_bisa = _evaluasi(5, tanggal="2026-09-10")
    perjalanan = perjalanan_belajar(
        _bukti(lama_ragu, terbaru_bisa), 1, date(2026, 9, 11)
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.fokus[0].tahap == "mulai_membaik"
    assert "mulai membaik" in ringkasan
    assert "ragu" not in ringkasan
    assert "menghafal" not in ringkasan


def test_ringkasan_tidak_meminjam_ragu_lama_saat_evaluasi_terbaru_tanpa_catatan():
    from report_summary import render_ringkasan

    lama_ragu = _sesi(
        4, "2026-09-08", tujuan="evaluasi",
        outcomes=tuple(
            _outcome(FOKUS_A, benar=True, kode=None, paham="ragu")
            for _ in range(4)
        ),
    )
    terbaru_tanpa_catatan = _sesi(
        5, "2026-09-10", tujuan="evaluasi",
        outcomes=tuple(
            _outcome(FOKUS_A, benar=True, kode=None, paham=None)
            for _ in range(4)
        ),
    )
    perjalanan = perjalanan_belajar(
        _bukti(
            lama_ragu,
            terbaru_tanpa_catatan,
            kejadian=(_event_intervensi(),),
            pendekatan=((FOKUS_A, ("visual-1", "visual-2")),),
        ),
        1,
        date(2026, 9, 11),
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.fokus[0].bukti[-1].cek_pemahaman == ()
    assert "ragu" not in ringkasan
    assert "menghafal" not in ringkasan


def test_ringkasan_menyebut_pemahaman_evaluasi_terbaru_bukan_yang_lama():
    from report_summary import render_ringkasan

    lama_bisa = _evaluasi(4, tanggal="2026-09-08")
    terbaru_ragu = _sesi(
        5, "2026-09-10", tujuan="evaluasi",
        outcomes=tuple(
            _outcome(FOKUS_A, benar=True, kode=None, paham="ragu")
            for _ in range(4)
        ),
    )
    perjalanan = perjalanan_belajar(
        _bukti(
            lama_bisa,
            terbaru_ragu,
            kejadian=(_event_intervensi(),),
            pendekatan=((FOKUS_A, ("visual-1", "visual-2")),),
        ),
        1,
        date(2026, 9, 11),
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.fokus[0].tahap == "perlu_diperkuat"
    assert "catatan pemeriksaan terakhir: masih ragu" in ringkasan
    assert "pemahaman terbaru" not in ringkasan
    assert "menghafal" not in ringkasan


def test_ringkasan_memakai_tahap_dari_reducer_untuk_hasil_ragu():
    from report_summary import render_ringkasan

    outcomes = tuple(
        _outcome(FOKUS_A, benar=True, kode=None, paham="ragu")
        for _ in range(4)
    )
    evaluasi_ragu = _sesi(
        4, "2026-09-10", tujuan="evaluasi", outcomes=outcomes
    )
    perjalanan = perjalanan_belajar(
        _bukti(
            evaluasi_ragu,
            kejadian=(_event_intervensi(),),
            pendekatan=((FOKUS_A, ("visual-1", "visual-2")),),
        ),
        1,
        date(2026, 9, 11),
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.fokus[0].tahap == "perlu_diperkuat"
    assert "masih perlu diperkuat" in ringkasan
    assert "ragu" in ringkasan
    assert "mulai membaik" not in ringkasan
    assert "menghafal" not in ringkasan


def test_ringkasan_dua_fokus_tidak_menyebut_keduanya_siap_saat_hanya_satu_due():
    from report_summary import render_ringkasan

    putaran = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A, FOKUS_B))
    kejadian = (
        _event_intervensi(FOKUS_A, identitas=1),
        _event_intervensi(FOKUS_B, identitas=2),
    )
    sesi = (
        _sesi(2, "2026-09-02", tujuan="latihan_terbimbing", fokus=FOKUS_A),
        _sesi(3, "2026-09-03", tujuan="penguatan", fokus=FOKUS_A),
        _sesi(4, "2026-09-06", tujuan="latihan_terbimbing", fokus=FOKUS_B),
        _sesi(5, "2026-09-07", tujuan="penguatan", fokus=FOKUS_B),
    )
    perjalanan = perjalanan_belajar(
        _bukti(*sesi, putaran=(putaran,), kejadian=kejadian),
        1,
        date(2026, 9, 8),
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.rekomendasi.tindakan == "evaluasi"
    assert perjalanan.rekomendasi.kandidat == (FOKUS_A,)
    assert len(perjalanan.fokus) == 2
    assert ringkasan.count("menunggu pemeriksaan setelah jeda") == 2
    assert "sudah siap" not in ringkasan


def test_ringkasan_dua_fokus_due_tetap_netral_saat_reducer_memilih_satu():
    from report_summary import render_ringkasan

    putaran = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A, FOKUS_B))
    kejadian = (
        _event_intervensi(FOKUS_A, identitas=1),
        _event_intervensi(FOKUS_B, identitas=2),
    )
    sesi = tuple(
        _sesi(identitas, tanggal, tujuan=tujuan, fokus=fokus)
        for identitas, tanggal, tujuan, fokus in (
            (2, "2026-09-02", "latihan_terbimbing", FOKUS_A),
            (3, "2026-09-03", "penguatan", FOKUS_A),
            (4, "2026-09-02", "latihan_terbimbing", FOKUS_B),
            (5, "2026-09-03", "penguatan", FOKUS_B),
        )
    )
    perjalanan = perjalanan_belajar(
        _bukti(*sesi, putaran=(putaran,), kejadian=kejadian),
        1,
        date(2026, 9, 8),
    )
    ringkasan = render_ringkasan(
        "Tunas", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.rekomendasi.tindakan == "evaluasi"
    assert perjalanan.rekomendasi.kandidat == (FOKUS_A,)
    assert [fokus.tahap for fokus in perjalanan.fokus] == [
        "menunggu_evaluasi", "menunggu_evaluasi",
    ]
    assert ringkasan.count("menunggu pemeriksaan setelah jeda") == 2
    assert "menunggu evaluasi" not in ringkasan.lower()
    assert "belum tersedia" not in ringkasan.lower()


def test_ringkasan_evaluasi_jatuh_tempo_tidak_menyuruh_menunggu():
    from report_summary import render_ringkasan

    perjalanan = perjalanan_belajar(
        _bukti(
            _sesi(2, "2026-09-04", tujuan="latihan_terbimbing"),
            _sesi(3, "2026-09-05", tujuan="penguatan"),
            kejadian=(_event_intervensi(),),
        ),
        1,
        date(2026, 9, 8),
    )
    ringkasan = render_ringkasan(
        "Anak Sintetis", perjalanan, 1, lambda nilai: nilai.replace("_", " "), str
    )

    assert perjalanan.rekomendasi.tindakan == "evaluasi"
    assert perjalanan.fokus[0].tahap == "menunggu_evaluasi"
    assert "Cek lagi setelah jeda" in ringkasan
    assert "menunggu evaluasi" not in ringkasan.lower()
    assert "belum tersedia" not in ringkasan.lower()


@pytest.mark.parametrize(
    ("nama_tahap", "sesi", "kejadian", "pendekatan", "hari"),
    [
        ("perlu_dipelajari", (), (), (), date(2026, 9, 4)),
        ("latihan_terbimbing", (), (_event_intervensi(),), (), date(2026, 9, 4)),
        ("penguatan", (_sesi(2, "2026-09-04", tujuan="latihan_terbimbing"),),
         (_event_intervensi(),), (), date(2026, 9, 5)),
        ("menunggu_evaluasi", (
            _sesi(2, "2026-09-04", tujuan="latihan_terbimbing"),
            _sesi(3, "2026-09-05", tujuan="penguatan"),
        ), (_event_intervensi(),), (), date(2026, 9, 6)),
        ("mulai_membaik", (_evaluasi(4),), (), (), date(2026, 9, 11)),
        ("bertahan", (_evaluasi(4),) + _checkpoint(5), (), (), date(2026, 10, 8)),
        ("perlu_diperkuat", (_evaluasi(4, lulus=False),), (_event_intervensi(),),
         ((FOKUS_A, ("visual-1", "visual-2")),), date(2026, 9, 11)),
        ("perlu_eskalasi", (_evaluasi(4, lulus=False),), (_event_intervensi(),),
         (), date(2026, 9, 11)),
    ],
)
def test_tahap_fokus_mengikuti_reducer(
    nama_tahap, sesi, kejadian, pendekatan, hari
):
    hasil = perjalanan_belajar(
        _bukti(*sesi, kejadian=kejadian, pendekatan=pendekatan),
        1,
        hari,
    )

    assert hasil.fokus[0].tahap == nama_tahap


def test_kandidat_otomatis_belum_ditampilkan_sebagai_fokus_sebelum_tiga_tanggal():
    sesi = (
        _sesi(1, "2026-09-01", putaran=None),
        _sesi(2, "2026-09-02", putaran=None),
    )
    bukti = _bukti(*sesi, putaran=())

    hasil = perjalanan_belajar(bukti, 1, date(2026, 9, 3))

    assert hasil.rekomendasi.tindakan == "pemetaan"
    assert hasil.fokus == ()


def test_dua_kunci_kanonis_template_sama_memiliki_tahap_dan_bukti_terpisah():
    putaran = (
        PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A, FOKUS_B)),
    )
    evaluasi_a = _evaluasi(10, FOKUS_A)
    intervensi_b = _event_intervensi(FOKUS_B, identitas=2)
    terbimbing_b = _sesi(
        11,
        "2026-09-05",
        tujuan="latihan_terbimbing",
        fokus=FOKUS_B,
        outcomes=(_outcome(FOKUS_B, benar=True, kode=None),),
    )

    hasil = perjalanan_belajar(
        _bukti(
            evaluasi_a,
            terbimbing_b,
            putaran=putaran,
            kejadian=(intervensi_b,),
        ),
        1,
        date(2026, 9, 11),
    )

    per_kunci = {fokus.kunci: fokus for fokus in hasil.fokus}
    assert len(per_kunci) == 2
    assert per_kunci[FOKUS_A].tahap == "mulai_membaik"
    assert per_kunci[FOKUS_B].tahap == "penguatan"
    assert {b.jenis for b in per_kunci[FOKUS_A].bukti} == {"evaluasi"}
    assert {b.jenis for b in per_kunci[FOKUS_B].bukti} == {
        "intervensi",
        "latihan_terbimbing",
    }


def test_histori_level_lama_dan_invalidasi_aman_tanpa_klaim_lulus():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 7, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P4", date(2026, 9, 1), (FOKUS_B,))
    sesi_lama = _sesi(
        20,
        "2026-07-10",
        tujuan="evaluasi",
        putaran=1,
        level="P3",
        fokus=FOKUS_A,
        outcomes=(),
        konfirmasi=False,
    )
    kejadian = (
        _event(
            1,
            "konfirmasi_dibatalkan",
            "2026-07-11",
            putaran=1,
            sesi=20,
        ),
        _event(2, "diganti_level", "2026-08-01", putaran=1),
    )
    sumber = _bukti(
        sesi_lama,
        putaran=(lama, baru),
        kejadian=kejadian,
        level="P4",
    )

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert hasil.histori == (
        HistoriPutaran(
            1,
            "P3",
            date(2026, 7, 1),
            date(2026, 8, 1),
            "diganti_level",
            (FOKUS_A,),
            (
                BuktiFokusPerjalanan(
                    date(2026, 7, 11),
                    20,
                    "bukti_dibatalkan",
                    (),
                    "perlu_konfirmasi_ulang",
                ),
            ),
            "perlu_konfirmasi_ulang",
            (FokusPerjalanan(FOKUS_A, "perlu_dipelajari"),),
        ),
    )
    assert "lulus" not in repr(hasil.histori).lower()
    assert hasil.fokus[0].kunci == FOKUS_B


def test_api_aditif_membawa_identitas_putaran_tanggal_pemetaan_dan_rekomendasi_persis():
    sesi = (
        _sesi(1, "2026-09-01", outcomes=(_outcome(FOKUS_A),)),
        _sesi(2, "2026-09-02", outcomes=(_outcome(FOKUS_A),)),
        _sesi(3, "2026-09-03", outcomes=(_outcome(FOKUS_B),)),
    )
    sumber = _bukti(*sesi)
    hari = date(2026, 9, 4)

    hasil = perjalanan_belajar(sumber, 1, hari)

    assert hasil.rekomendasi == rencana_berikutnya(sumber, 1, hari)
    assert hasil.putaran_id == 1
    assert hasil.tanggal_pemetaan == (
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
    )
    assert hasil.catatan == ()


def test_fokus_otomatis_sesudah_tiga_tanggal_selalu_membawa_bukti_sesi():
    sesi = (
        _sesi(1, "2026-09-01", putaran=None, outcomes=(_outcome(FOKUS_A),)),
        _sesi(2, "2026-09-02", putaran=None, outcomes=(_outcome(FOKUS_A),)),
        _sesi(3, "2026-09-03", putaran=None, outcomes=(_outcome(FOKUS_B),)),
    )
    sumber = _bukti(*sesi, putaran=())

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 4))

    assert hasil.putaran_id is None
    assert hasil.fokus == (
        FokusPerjalanan(
            FOKUS_A,
            "perlu_dipelajari",
            (
                BuktiFokusPerjalanan(date(2026, 9, 1), 1, "pemetaan"),
                BuktiFokusPerjalanan(date(2026, 9, 2), 2, "pemetaan"),
            ),
        ),
    )


def test_invalidasi_sesi_aktif_yang_belum_dikonfirmasi_memberi_catatan_koreksi():
    sesi = _sesi(
        2,
        "2026-09-04",
        tujuan="latihan_terbimbing",
        konfirmasi=False,
    )
    sumber = _bukti(
        sesi,
        kejadian=(
            _event(
                8,
                "konfirmasi_dibatalkan",
                "2026-09-04",
                sesi=2,
            ),
        ),
    )

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert hasil.rekomendasi.tindakan == "konfirmasi_hasil"
    assert hasil.catatan == ("Bukti dikoreksi; perlu konfirmasi ulang.",)


def test_invalidasi_lama_tetap_riwayat_tetapi_rekonfirmasi_tidak_pending():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 7, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 9, 1), (FOKUS_B,))
    rekonfirmasi = _sesi(
        20,
        "2026-07-10",
        tujuan="evaluasi",
        putaran=1,
        outcomes=(_outcome(FOKUS_A, benar=True, kode=None),),
    )
    sumber = _bukti(
        rekonfirmasi,
        putaran=(lama, baru),
        kejadian=(
            _event(
                1,
                "konfirmasi_dibatalkan",
                "2026-07-11",
                putaran=1,
                sesi=20,
            ),
            _event(2, "putaran_ditutup", "2026-08-01", putaran=1),
        ),
    )

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert hasil.histori[0].status_bukti == "tersedia"
    assert [item.jenis for item in hasil.histori[0].bukti] == [
        "evaluasi",
        "bukti_dibatalkan",
    ]
    assert hasil.histori[0].bukti[-1].status == "riwayat_invalidasi"
    assert hasil.catatan == ()


def test_histori_hanya_meringkas_bukti_siswa_level_selesai_terkonfirmasi_aktif():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 7, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P4", date(2026, 9, 1), (FOKUS_B,))
    sesi = (
        _sesi(10, "2026-07-01", tujuan="evaluasi", putaran=1, level="P3"),
        _sesi(11, "2026-07-02", tujuan="evaluasi", putaran=1, level="P3", siswa=2),
        _sesi(12, "2026-07-03", tujuan="evaluasi", putaran=1, level="P4"),
        _sesi(13, "2026-07-04", tujuan="evaluasi", putaran=1, level="P3", selesai=False),
        _sesi(14, "2026-07-05", tujuan="evaluasi", putaran=1, level="P3", konfirmasi=False),
        _sesi(
            15,
            "2026-07-06",
            tujuan="evaluasi",
            putaran=1,
            level="P3",
            dibatalkan="2026-07-07 08:00:00",
        ),
    )
    sumber = _bukti(
        *sesi,
        putaran=(lama, baru),
        kejadian=(_event(1, "diganti_level", "2026-08-01", putaran=1),),
        level="P4",
    )

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert [item.sesi_id for item in hasil.histori[0].bukti] == [10]


def test_invalidasi_putaran_aktif_tidak_pending_setelah_sesi_dikonfirmasi_ulang():
    sesi = _sesi(20, "2026-09-04", tujuan="latihan_terbimbing")
    sumber = _bukti(
        sesi,
        kejadian=(
            _event(
                1,
                "konfirmasi_dibatalkan",
                "2026-09-04",
                putaran=1,
                sesi=20,
            ),
        ),
    )

    hasil = perjalanan_belajar(sumber, 1, date(2026, 9, 5))

    assert hasil.catatan == ()
    assert hasil.rekomendasi.tindakan != "konfirmasi_hasil"


def test_bukti_fokus_hanya_dari_sesi_siswa_level_selesai_terkonfirmasi_aktif():
    sesi = (
        _sesi(10, "2026-09-02", tujuan="latihan_terbimbing"),
        _sesi(11, "2026-09-03", tujuan="latihan_terbimbing", siswa=2),
        _sesi(12, "2026-09-04", tujuan="latihan_terbimbing", level="P4"),
        _sesi(13, "2026-09-05", tujuan="latihan_terbimbing", selesai=False),
        _sesi(14, "2026-09-06", tujuan="latihan_terbimbing", konfirmasi=False),
        _sesi(
            15,
            "2026-09-07",
            tujuan="latihan_terbimbing",
            dibatalkan="2026-09-08 08:00:00",
        ),
    )

    hasil = perjalanan_belajar(_bukti(*sesi), 1, date(2026, 9, 9))

    bukti_sesi = [item.sesi_id for item in hasil.fokus[0].bukti]
    assert bukti_sesi == [10]


def test_penutupan_berulang_tidak_memperpanjang_batas_histori():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P4", date(2026, 9, 10), (FOKUS_B,))
    hasil = perjalanan_belajar(_bukti(
        _evaluasi(10, tanggal="2026-09-15"), putaran=(lama, baru), level="P4",
        kejadian=(
            _event(1, "putaran_ditutup", "2026-09-10"),
            _event(2, "diganti_level", "2026-09-20"),
        ),
    ), 1, date(2026, 9, 21))
    assert hasil.histori[0].ditutup == date(2026, 9, 10)
    assert hasil.histori[0].perjalanan_fokus[0].bukti == ()


def test_histori_memotong_sesi_dan_intervensi_setelah_event_penutup():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 9, 10), (FOKUS_B,))
    sebelum = _sesi(
        10, "2026-09-08", tujuan="latihan_terbimbing", konfirmasi_id=100
    )
    sesudah = _sesi(
        11, "2026-09-11", tujuan="evaluasi", konfirmasi_id=101
    )
    kejadian = (
        _event(
            20,
            "hasil_dikonfirmasi",
            "2026-09-08",
            sesi=10,
            konfirmasi=100,
        ),
        _event(30, "putaran_ditutup", "2026-09-09"),
        _event(
            31,
            "intervensi_selesai",
            "2026-09-11",
            fokus=FOKUS_A,
            pendekatan_id="visual-terlambat",
        ),
        _event(
            40,
            "hasil_dikonfirmasi",
            "2026-09-11",
            sesi=11,
            konfirmasi=101,
        ),
    )
    sumber = _bukti(
        sebelum,
        sesudah,
        putaran=(lama, baru),
        kejadian=kejadian,
    )

    histori = perjalanan_belajar(sumber, 1, date(2026, 9, 12)).histori[0]

    assert [item.sesi_id for item in histori.bukti] == [10]
    assert [item.jenis for item in histori.perjalanan_fokus[0].bukti] == [
        "latihan_terbimbing"
    ]


def test_histori_memakai_urutan_event_konfirmasi_pada_hari_penutupan():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 9, 10), (FOKUS_B,))
    sebelum = _sesi(
        10, "2026-09-09", tujuan="latihan_terbimbing", konfirmasi_id=100
    )
    sesudah = _sesi(
        11, "2026-09-09", tujuan="evaluasi", konfirmasi_id=101
    )
    kejadian = (
        _event(
            20,
            "hasil_dikonfirmasi",
            "2026-09-09",
            sesi=10,
            konfirmasi=100,
        ),
        _event(30, "putaran_ditutup", "2026-09-09"),
        _event(
            31,
            "intervensi_selesai",
            "2026-09-09",
            fokus=FOKUS_A,
            pendekatan_id="visual-terlambat",
        ),
        _event(
            40,
            "hasil_dikonfirmasi",
            "2026-09-09",
            sesi=11,
            konfirmasi=101,
        ),
    )
    sumber = _bukti(
        sebelum,
        sesudah,
        putaran=(lama, baru),
        kejadian=kejadian,
    )

    histori = perjalanan_belajar(sumber, 1, date(2026, 9, 10)).histori[0]

    assert [item.sesi_id for item in histori.bukti] == [10]
    assert [item.jenis for item in histori.perjalanan_fokus[0].bukti] == [
        "latihan_terbimbing"
    ]


def test_histori_memakai_fokus_override_efektif_pada_cutoff():
    lama = PutaranSiklus(1, 1, "P3", date(2026, 9, 1), (FOKUS_A,))
    baru = PutaranSiklus(2, 1, "P3", date(2026, 9, 10), (FOKUS_A,))
    kejadian = (
        _event(10, "fokus_diubah", "2026-09-02", fokus=(FOKUS_B,)),
        _event(20, "putaran_ditutup", "2026-09-09"),
        _event(30, "fokus_diubah", "2026-09-10", fokus=(FOKUS_A,)),
    )
    sumber = _bukti(putaran=(lama, baru), kejadian=kejadian)

    histori = perjalanan_belajar(sumber, 1, date(2026, 9, 11)).histori[0]

    assert histori.fokus == (FOKUS_B,)
    assert [item.kunci for item in histori.perjalanan_fokus] == [FOKUS_B]
