"""Catatan histori beda kelas pada profil dan laporan (Fase 6)."""
from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import learning_cycle_ui  # noqa: E402
import reports  # noqa: E402
from cycle_report import render_perjalanan  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402
from learning_cycle import (  # noqa: E402
    BuktiSiklus,
    PutaranFokus,
    RencanaBelajar,
    SesiSiklus,
)  # noqa: E402
from learning_journey import perjalanan_belajar  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    server_uji = ServerUji(tmp_path, monkeypatch)
    with server_uji.buka() as kon:
        siswa_id = database.tambah_siswa(
            kon, "Anak Histori", "P5", pemilik="guru"
        )
    yield server_uji, siswa_id
    server_uji.berhenti()


def _sesi(
    sesi_id: int,
    siswa_id: int,
    level: str,
    *,
    selesai: str | None = "2026-08-01 09:00:00",
) -> SesiSiklus:
    return SesiSiklus(
        sesi_id,
        siswa_id,
        level,
        "bebas",
        date(2026, 8, 1),
        selesai=selesai,
    )


def _helper():
    modul = importlib.import_module("learning_history")
    return modul.catatan_histori_beda_level


def _buat_sesi_warisan(kon, siswa_id, *, level="P3", selesai=True, direview=False):
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=7300 + kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0],
        urutan=("deret_aritmetika",),
        level=level,
    )
    kon.execute(
        "UPDATE sesi SET selesai = ?, direview = ? WHERE id = ?",
        (
            "2026-08-01 09:00:00" if selesai else None,
            "2026-08-01 10:00:00" if direview else None,
            sesi_id,
        ),
    )
    return sesi_id


def _buat_sesi_aktif(kon, siswa_id, *, selesai):
    putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P5")
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=7388,
        urutan=("deret_aritmetika",),
        level="P5",
    )
    kon.execute(
        """UPDATE sesi
           SET tujuan = 'pemetaan', putaran_id = ?, selesai = ?
           WHERE id = ?""",
        (putaran_id, "2026-09-01 09:00:00" if selesai else None, sesi_id),
    )
    return sesi_id


def _buat_pemetaan_aktif(kon, siswa_id):
    putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P5")
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=7399,
        urutan=("deret_aritmetika",),
        level="P5",
    )
    kon.execute(
        """UPDATE sesi
           SET tujuan = 'pemetaan', putaran_id = ?, tanggal = '2026-09-01',
               selesai = '2026-09-01 09:00:00'
           WHERE id = ?""",
        (putaran_id, sesi_id),
    )
    butir_id = int(database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"])
    database.konfirmasi_hasil(kon, sesi_id, guru="guru", dilewati={butir_id})


def test_helper_tanpa_histori_atau_hanya_level_sama_tidak_memberi_catatan():
    helper = _helper()

    assert helper(BuktiSiklus(7, "P5"), mulai_dari_awal=True) == ()
    assert helper(
        BuktiSiklus(7, "P5", sesi=(_sesi(1, 7, "P5"),)),
        mulai_dari_awal=True,
    ) == ()


def test_helper_merangkum_banyak_level_dan_mengabaikan_siswa_lain():
    helper = _helper()
    bukti = BuktiSiklus(
        7,
        "P5",
        sesi=(
            _sesi(1, 7, "P4"),
            _sesi(2, 7, "P3"),
            _sesi(3, 99, "P2"),
            _sesi(4, 7, "P5"),
        ),
    )

    catatan = helper(bukti, mulai_dari_awal=True)

    assert catatan == (
        "Riwayat Profil P3 dan Profil P4 tetap tersimpan sebagai catatan; "
        "tidak dihitung dalam pemetaan Profil P5.",
        "Mulai pemetaan Profil P5 dari awal.",
    )
    assert "P2" not in " ".join(catatan)


def test_helper_tidak_mengaku_mulai_dari_awal_jika_pemetaan_aktif_sudah_berjalan():
    helper = _helper()
    bukti = BuktiSiklus(7, "P5", sesi=(_sesi(1, 7, "P3"),))

    catatan = helper(bukti, mulai_dari_awal=False)

    assert len(catatan) == 1
    assert "Riwayat Profil P3" in catatan[0]
    assert "dari awal" not in " ".join(catatan)


@pytest.mark.parametrize(
    "rencana",
    (
        RencanaBelajar("lanjutkan_sesi", "", sesi_id=8),
        RencanaBelajar("konfirmasi_hasil", "", sesi_id=8),
        RencanaBelajar(
            "intervensi", "", putaran=PutaranFokus(3, "P5", ())
        ),
    ),
)
def test_profil_state_berjalan_hanya_menampilkan_catatan_histori(rencana):
    bukti = BuktiSiklus(7, "P5", sesi=(_sesi(1, 7, "P3"),))

    profil = learning_cycle_ui.render_rencana(rencana, bukti, 7)

    assert "Riwayat Profil P3" in profil
    assert "Mulai pemetaan Profil P5 dari awal." not in profil


@pytest.mark.parametrize(
    "selesai, langkah",
    (
        (False, "Lanjutkan sesi"),
        (True, "Konfirmasi hasil"),
    ),
)
def test_http_laporan_state_berjalan_hanya_menampilkan_catatan_histori(
    server, selesai, langkah
):
    server_uji, siswa_id = server
    with server_uji.buka() as kon:
        _buat_sesi_warisan(kon, siswa_id, level="P3")
        _buat_sesi_aktif(kon, siswa_id, selesai=selesai)

    kode, laporan, _ = server_uji.minta(
        f"/laporan/{siswa_id}", auth=("guru", SANDI_GURU)
    )

    assert kode == 200
    assert "Riwayat Profil P3" in laporan
    assert langkah in laporan
    assert "Mulai pemetaan Profil P5 dari awal." not in laporan


def test_renderer_profil_dan_laporan_meloloskan_escape_catatan_level():
    bukti = BuktiSiklus(
        7,
        "P5",
        sesi=(_sesi(1, 7, '<script>alert("x")</script>'),),
    )
    rencana = RencanaBelajar("pemetaan", "Mulai pemetaan")

    profil = learning_cycle_ui.render_rencana(rencana, bukti, 7)
    laporan = render_perjalanan(
        perjalanan_belajar(bukti, 7),
        lambda nilai: nilai,
        lambda nilai: nilai,
    )

    assert "<script>" not in profil
    assert "<script>" not in laporan
    assert "&lt;script&gt;" in profil
    assert "&lt;script&gt;" in laporan


def test_http_profil_dan_laporan_menjelaskan_histori_beda_level_tanpa_mutasi(server):
    server_uji, siswa_id = server
    with server_uji.buka() as kon:
        _buat_sesi_warisan(kon, siswa_id, level="P3", selesai=True)
        _buat_sesi_warisan(
            kon, siswa_id, level="P3", selesai=False, direview=True
        )
        sebelum = tuple(kon.iterdump())

    kode_profil, profil, _ = server_uji.minta(
        f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU)
    )
    kode_laporan, laporan, _ = server_uji.minta(
        f"/laporan/{siswa_id}", auth=("guru", SANDI_GURU)
    )

    with server_uji.buka() as kon:
        sesudah = tuple(kon.iterdump())
    catatan = (
        "Riwayat Profil P3 tetap tersimpan sebagai catatan; "
        "tidak dihitung dalam pemetaan Profil P5."
    )
    assert kode_profil == kode_laporan == 200
    assert catatan in profil
    assert catatan in laporan
    assert "Mulai pemetaan Profil P5 dari awal." in profil
    assert "Mulai pemetaan Profil P5 dari awal." in laporan
    assert "Pemetaan 0 dari 3" in profil
    assert "Pemetaan 0 dari 3" in laporan
    assert profil.count('class="rencana-cta-utama-st"') == 1
    kartu = profil.split('class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]
    assert 'id="judul-rencana-belajar">Kenali cara anak menyelesaikan soal</h2>' in kartu
    assert "Siapkan sesi pemetaan pertama" in kartu
    assert f'action="/siklus/{siswa_id}/buat"' in kartu
    assert "Lanjutkan sesi" not in kartu
    assert "Tinjau hasil" not in kartu
    assert "Pelajari konsep bersama" not in kartu
    assert sesudah == sebelum


def _potret_baris_lama(kon):
    """Simpan semua baris domain agar insert baru tidak menutupi mutasi lama."""
    tabel = ("siswa", "sesi", "sesi_soal", "soal", "malrule", "jawaban", "diagnosis", "lampiran")
    return {
        nama: tuple(tuple(r) for r in kon.execute(f'SELECT * FROM "{nama}" ORDER BY id'))
        for nama in tabel
    }


def test_http_post_cta_membuat_pemetaan_level_aktif_tanpa_mengubah_histori(server):
    server_uji, siswa_id = server
    with server_uji.buka() as kon:
        lama_selesai = _buat_sesi_warisan(kon, siswa_id, level="P3")
        lama_incomplete = _buat_sesi_warisan(
            kon, siswa_id, level="P3", selesai=False, direview=True
        )
        butir = database.isi_sesi(kon, lama_selesai)[0]
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], "0", cara="Cara sintetis lama"
        )
        database.simpan_diagnosis(
            kon, jawaban_id, benar=False, kode_usulan="H", kode_final="H",
            alasan="Diagnosis sintetis lama",
        )
        kon.execute(
            "INSERT INTO lampiran (sesi_id, nama_berkas) VALUES (?, ?)",
            (lama_selesai, "sintetis-tanpa-berkas.jpg"),
        )
        histori = _potret_baris_lama(kon)
        id_lama = (lama_selesai, lama_incomplete)
        sebelum = tuple(
            tuple(baris)
            for baris in kon.execute(
                "SELECT * FROM sesi WHERE id IN (?, ?) ORDER BY id", id_lama
            ).fetchall()
        )

    kode, _, _ = server_uji.minta(
        f"/siklus/{siswa_id}/buat", auth=("guru", SANDI_GURU), data={}
    )

    with server_uji.buka() as kon:
        setelah = _potret_baris_lama(kon)
        for nama, baris_lama in histori.items():
            assert set(baris_lama) <= set(setelah[nama]), nama
        sesudah = tuple(
            tuple(baris)
            for baris in kon.execute(
                "SELECT * FROM sesi WHERE id IN (?, ?) ORDER BY id", id_lama
            ).fetchall()
        )
        baru = kon.execute(
            """SELECT level, tujuan, putaran_id, kunci_idempotensi
               FROM sesi WHERE siswa_id = ? AND id NOT IN (?, ?)""",
            (siswa_id, *id_lama),
        ).fetchall()
        metadata = kon.execute(
            """SELECT jenis, putaran_id, sesi_id FROM kejadian_belajar
               WHERE siswa_id = ? AND jenis = 'sesi_dibuat'""",
            (siswa_id,),
        ).fetchall()

    assert kode == 200
    assert sesudah == sebelum
    assert len(baru) == 1
    assert baru[0]["level"] == "P5"
    assert baru[0]["tujuan"] == "pemetaan"
    assert baru[0]["putaran_id"] is not None
    assert baru[0]["kunci_idempotensi"]
    assert len(metadata) == 1
    assert metadata[0]["putaran_id"] == baru[0]["putaran_id"]
    assert metadata[0]["sesi_id"] is not None


def test_http_tidak_mengaku_mulai_dari_awal_setelah_pemetaan_aktif(server):
    server_uji, siswa_id = server
    with server_uji.buka() as kon:
        _buat_sesi_warisan(kon, siswa_id, level="P3")
        _buat_pemetaan_aktif(kon, siswa_id)

    kode_profil, profil, _ = server_uji.minta(
        f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU)
    )
    kode_laporan, laporan, _ = server_uji.minta(
        f"/laporan/{siswa_id}", auth=("guru", SANDI_GURU)
    )

    assert kode_profil == kode_laporan == 200
    assert "Riwayat Profil P3" in profil
    assert "Riwayat Profil P3" in laporan
    assert "Mulai pemetaan Profil P5 dari awal." not in profil
    assert "Mulai pemetaan Profil P5 dari awal." not in laporan
    assert "Pemetaan 1 dari 3" in profil
    assert "Pemetaan 1 dari 3" in laporan
