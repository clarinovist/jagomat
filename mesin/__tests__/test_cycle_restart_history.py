"""Restart setelah koreksi histori memakai DB dan HTTP, bukan mock reducer."""
import pytest

import database
import interventions
from http_test_kit import SANDI_GURU
from learning_cycle_service import catat_intervensi_selesai
from test_learning_cycle_e2e import (
    alur, buat, hari, intervensi, kirim, konfirmasi, rencana, sampai_evaluasi,
)

FOKUS_A = ("deret_aritmetika", "K", None)
FOKUS_B = ("soal_umur", "H", None)


def _dua_fokus_bertahan(alur):
    """Bangun evaluasi dua fokus dan checkpoint dari snapshot terkonfirmasi."""
    konfirmasi(alur, sampai_evaluasi(alur))
    with alur[0].buka() as kon:
        fokus = rencana(alur).putaran
        assert fokus is not None and fokus.id is not None
        putaran = fokus.id
        sumber = kon.execute("SELECT MIN(id) FROM sesi").fetchone()[0]
        database.tambah_anggota_fokus(kon, putaran, *FOKUS_B, [sumber])
        catat_intervensi_selesai(kon, alur[1], putaran, FOKUS_B,
            interventions.pilihan_untuk_fokus(FOKUS_B)[0].pendekatan_id)
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    hari(alur[2], 8)
    evaluasi_b = buat(alur, "evaluasi")
    konfirmasi(alur, evaluasi_b)
    hari(alur[2], 36)
    for _ in range(4):
        if rencana(alur).tindakan != "checkpoint":
            break
        konfirmasi(alur, buat(alur, "checkpoint"))
    fokus = rencana(alur).putaran
    assert fokus is not None
    assert {f.status for f in fokus.fokus} == {"bertahan"}
    return evaluasi_b


def _kambuh_kedua(alur):
    """Lewati restart pertama, lalu fokus A kambuh lagi di putaran kedua."""
    evaluasi_b = _dua_fokus_bertahan(alur)
    hari(alur[2], 64)
    konfirmasi(alur, buat(alur, "checkpoint"), salah=FOKUS_A[0])
    jalur = f"/siklus/{alur[1]}/aksi"
    assert kirim(alur, jalur, {"aksi": "mulai_putaran_baru"})[0] == 303
    intervensi(alur)
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    hari(alur[2], 67)
    konfirmasi(alur, buat(alur, "evaluasi"))
    hari(alur[2], 95)
    for _ in range(4):
        if rencana(alur).tindakan != "checkpoint":
            break
        konfirmasi(alur, buat(alur, "checkpoint"))
    hari(alur[2], 123)
    konfirmasi(alur, buat(alur, "checkpoint"), salah=FOKUS_A[0])
    assert rencana(alur).tindakan == "putaran_baru"
    return evaluasi_b


@pytest.mark.parametrize("koreksi_histori", [False, True])
def test_restart_kedua_tetap_berjalan_setelah_koreksi_histori(alur, koreksi_histori):
    evaluasi_b = _kambuh_kedua(alur)
    server, siswa, _ = alur
    with server.buka() as kon:
        if koreksi_histori:
            butir = database.isi_sesi(kon, evaluasi_b)[0]
            database.simpan_jawaban(kon, butir["sesi_soal_id"], "koreksi sintetis")
        sumber = database.muat_bukti_siklus(kon, siswa)
        historis = next(s for s in sumber.sesi if s.id == evaluasi_b)
        assert historis.putaran_id == 1
        assert (historis.dikonfirmasi is None) == koreksi_histori
        if koreksi_histori:
            assert historis.outcomes == ()
        lama = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome ORDER BY id"))
        penyajian = tuple(tuple(b) for b in kon.execute("SELECT * FROM penyajian_outcome ORDER BY 1"))
        assert kon.execute("SELECT COUNT(*) FROM putaran_fokus").fetchone()[0] == 2
    assert rencana(alur).tindakan == "putaran_baru"
    kode, html, _ = server.minta(f"/anak/{siswa}?section=rencana", auth=("guru", SANDI_GURU))
    assert kode == 200 and 'name="aksi" value="mulai_putaran_baru"' in html
    for _ in range(2):
        assert kirim(alur, f"/siklus/{siswa}/aksi", {"aksi": "mulai_putaran_baru"})[0] == 303
        with server.buka() as kon:
            assert kon.execute("SELECT COUNT(*) FROM putaran_fokus").fetchone()[0] == 3
            assert tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome ORDER BY id")) == lama
            assert tuple(tuple(b) for b in kon.execute("SELECT * FROM penyajian_outcome ORDER BY 1")) == penyajian
            assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
    hasil = rencana(alur)
    assert hasil.tindakan == ("evaluasi" if koreksi_histori else "intervensi")
    if koreksi_histori:
        assert hasil.kandidat == (FOKUS_B,)
    assert hasil.putaran is not None and hasil.putaran.id == 3
    assert {f.kunci for f in hasil.putaran.fokus} == {FOKUS_A, FOKUS_B}
