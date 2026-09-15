"""Rantai HTTP siklus dengan kalender dan data sintetis, tanpa DB produksi."""
import sqlite3
import urllib.parse
from datetime import date, timedelta

import pytest
import database
import learning_cycle
import interventions
from http_test_kit import ServerUji, SANDI_GURU
from test_learning_cycle_routes import _post


@pytest.fixture
def alur(tmp_path, monkeypatch):
    asli = sqlite3.connect

    def sambung(*args, **kwargs):
        kon = asli(*args, **kwargs)
        kon.create_function("date", 2, lambda *_: learning_cycle.date.today().isoformat())
        kon.create_function("datetime", 2, lambda *_: learning_cycle.date.today().isoformat() + " 10:00:00")
        return kon

    monkeypatch.setattr(sqlite3, "connect", sambung)
    hari(monkeypatch, 0)
    server = ServerUji(tmp_path, monkeypatch)
    with server.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak sintetis", "P3", pemilik="guru")
    yield server, siswa, monkeypatch
    server.berhenti()


def hari(monkeypatch, selisih):
    class Tanggal(date):
        @classmethod
        def today(cls):
            return date(2026, 1, 1) + timedelta(days=selisih)
    monkeypatch.setattr(learning_cycle, "date", Tanggal)
    monkeypatch.setattr(database, "date", Tanggal)


def rencana(alur):
    server, siswa, _ = alur
    with server.buka() as kon:
        return learning_cycle.rencana_berikutnya(database.muat_bukti_siklus(kon, siswa), siswa)


def kirim(alur, jalur, data=None):
    return _post(alur[0], jalur, urllib.parse.urlencode(data or {}).encode())


def buat(alur, tujuan):
    assert rencana(alur).tindakan == tujuan
    kode, isi, tajuk = kirim(alur, f"/siklus/{alur[1]}/buat")
    assert kode == 303, (kode, isi[-400:])
    return int(tajuk["Location"].split("/")[-1])


def konfirmasi(alur, sesi, salah=None, paham="bisa_menjelaskan", kode_salah="K"):
    with alur[0].buka() as kon:
        butir = database.isi_sesi(kon, sesi)
        # Simulasikan pekerjaan anak selesai, tanpa memalsukan hasil/rekomendasi.
        database.tandai_selesai(kon, sesi)
        pasangan = tuple((b["sesi_soal_id"], b["kunci"], b["template_id"]) for b in butir)
    payload = {nama: nilai for sid, kunci, tid in pasangan for nama, nilai in (
        (f"jwb_{sid}", "-999999" if tid == salah else kunci),
        (f"cara_{sid}", "Langkah sintetis untuk pengujian"),
        (f"kode_{sid}", kode_salah if tid == salah else "benar"),
        (f"cek_pemahaman_{sid}", paham),
    )}
    if kode_salah == "T":
        payload = {**payload, **{f"belum_{sid}": "1" for sid, _, tid in pasangan if tid == salah}}
    kode, isi, _ = kirim(alur, f"/sesi/{sesi}/konfirmasi", payload)
    assert kode == 303, isi[isi.find("<h1>"):isi.find("<h1>") + 400]


def intervensi(alur):
    rec = rencana(alur)
    assert rec.tindakan == "intervensi"
    fokus = rec.putaran.fokus[0]
    pendekatan = fokus.pendekatan_berikutnya or interventions.pilihan_untuk_fokus(fokus.kunci)[0].pendekatan_id
    kode, _, _ = kirim(alur, f"/siklus/{alur[1]}/aksi", {
        "aksi": "intervensi_selesai", "putaran_id": rec.putaran.id,
        "template_id": fokus.kunci[0], "kode_intervensi": fokus.kunci[1],
        "malrule_id": fokus.kunci[2] or "", "pendekatan_id": pendekatan,
    })
    assert kode == 303
    return pendekatan


def sampai_evaluasi(alur):
    for nomor in range(3):
        hari(alur[2], nomor)
        sesi = buat(alur, "pemetaan")
        with alur[0].buka() as kon:
            assert len(database.isi_sesi(kon, sesi)) == 15
        konfirmasi(alur, sesi, salah="deret_aritmetika")
    intervensi(alur)
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    assert rencana(alur).tindakan == "tunggu_evaluasi"
    hari(alur[2], 5)
    return buat(alur, "evaluasi")


def test_pengenalan_diikuti_probe_terkonfirmasi(alur):
    for nomor in range(3):
        hari(alur[2], nomor)
        konfirmasi(alur, buat(alur, "pemetaan"),
                   salah="deret_aritmetika" if nomor == 0 else None, kode_salah="T")
    konfirmasi(alur, buat(alur, "pengenalan"))
    rec = rencana(alur)
    assert rec.putaran is not None
    fokus = rec.kandidat[0]
    assert kirim(alur, f"/siklus/{alur[1]}/aksi", {
        "aksi": "pengenalan_selesai", "putaran_id": rec.putaran.id,
        "template_id": fokus[0], "kode_intervensi": "T",
        "pendekatan_id": interventions.pilihan_untuk_fokus(fokus)[0].pendekatan_id,
    })[0] == 303
    hari(alur[2], 3)
    konfirmasi(alur, buat(alur, "probe_setelah_pengenalan"))
    assert rencana(alur).tindakan == "mixed_maintenance"


def test_rantai_sampai_checkpoint_berulang(alur):
    evaluasi = sampai_evaluasi(alur)
    konfirmasi(alur, evaluasi)
    assert rencana(alur).putaran.fokus[0].status == "mulai_membaik"
    for nomor in (33, 61):
        hari(alur[2], nomor)
        konfirmasi(alur, buat(alur, "checkpoint"))
        assert rencana(alur).tindakan == "checkpoint"
        konfirmasi(alur, buat(alur, "checkpoint"))
        assert rencana(alur).putaran.fokus[0].status == "bertahan"
        assert rencana(alur).tindakan == "tunggu_checkpoint"


def test_gagal_pertama_intervensi_alternatif_bisa_dilanjutkan(alur):
    evaluasi = sampai_evaluasi(alur)
    konfirmasi(alur, evaluasi, paham="ragu")
    assert rencana(alur).tindakan == "intervensi"
    intervensi(alur)
    assert rencana(alur).tindakan == "latihan_terbimbing"
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    assert rencana(alur).tindakan == "tunggu_evaluasi"
    hari(alur[2], 8)
    konfirmasi(alur, buat(alur, "evaluasi"), paham="menghafal")
    assert rencana(alur).tindakan == "eskalasi"


def test_kambuh_dapat_membuka_putaran_baru_lewat_http(alur):
    evaluasi = sampai_evaluasi(alur)
    konfirmasi(alur, evaluasi)
    hari(alur[2], 33)
    konfirmasi(alur, buat(alur, "checkpoint"))
    konfirmasi(alur, buat(alur, "checkpoint"))
    hari(alur[2], 61)
    konfirmasi(alur, buat(alur, "checkpoint"), salah="deret_aritmetika")
    assert rencana(alur).tindakan == "putaran_baru"
    with alur[0].buka() as kon:
        lama = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome"))
        putaran_lama = kon.execute("SELECT MAX(id) FROM putaran_fokus").fetchone()[0]
    kode, isi, _ = alur[0].minta(f"/anak/{alur[1]}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert 'name="aksi" value="mulai_putaran_baru"' in isi
    assert 'Pemetaan 0 dari 3' not in isi
    assert 'Fokus kambuh — mulai putaran baru' in isi
    for _ in range(2):
        assert kirim(alur, f"/siklus/{alur[1]}/aksi", {"aksi": "mulai_putaran_baru"})[0] == 303
    assert rencana(alur).tindakan == "intervensi"
    aktif = rencana(alur).putaran
    assert aktif is not None
    assert aktif.id != putaran_lama
    with alur[0].buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM putaran_fokus").fetchone()[0] == 2
        assert tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome")) == lama
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
    intervensi(alur)
    assert rencana(alur).tindakan == "latihan_terbimbing"
