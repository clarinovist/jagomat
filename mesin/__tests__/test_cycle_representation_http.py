"""Rantai HTTP melintasi aktivasi visual tanpa mewariskan kelulusan teks."""
import database
from http_test_kit import SANDI_GURU
from test_learning_cycle_e2e import alur, buat, hari, intervensi, kirim, konfirmasi, rencana


def test_http_checkpoint_visual_memerlukan_evaluasi_visual_sendiri(alur):
    server, siswa, monkeypatch = alur
    monkeypatch.delenv("OSN_VISUAL_KELUARGA", raising=False)
    for nomor in range(3):
        hari(monkeypatch, nomor)
        konfirmasi(alur, buat(alur, "pemetaan"), salah="deret_aritmetika")
    assert kirim(alur, f"/siklus/{siswa}/aksi", {
        "aksi": "ubah_fokus", "template_id": "korek_api", "kode_intervensi": "K",
    })[0] == 303
    intervensi(alur)
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    hari(monkeypatch, 5)
    evaluasi_lama = buat(alur, "evaluasi")
    konfirmasi(alur, evaluasi_lama)
    status = rencana(alur)
    assert status.putaran is not None
    assert status.putaran.fokus[0].status == "mulai_membaik"
    with server.buka() as kon:
        sebelum = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome ORDER BY id"))
        sidik = tuple(b["fingerprint_penyajian"] for b in database.isi_sesi(kon, evaluasi_lama))
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "pola-bilangan")
    hari(monkeypatch, 33)
    checkpoint = buat(alur, "checkpoint")
    konfirmasi(alur, checkpoint)
    hasil = rencana(alur)
    assert hasil.putaran is not None
    assert hasil.putaran.fokus[0].status not in {"mulai_membaik", "bertahan"}
    assert hasil.tindakan == "latihan_terbimbing"
    with server.buka() as kon:
        semua = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome ORDER BY id"))
        assert semua[:len(sebelum)] == sebelum
        assert tuple(b["fingerprint_penyajian"] for b in database.isi_sesi(kon, evaluasi_lama)) == sidik
        sumber = database.muat_bukti_siklus(kon, siswa)
        lama = next(s for s in sumber.sesi if s.id == evaluasi_lama)
        baru = next(s for s in sumber.sesi if s.id == checkpoint)
        assert {o.mode_representasi for o in lama.outcomes} == {"teks-v1"}
        fokus_baru = tuple(o for o in baru.outcomes if o.template_id == "korek_api")
        assert fokus_baru and {o.mode_representasi for o in fokus_baru} == {"korek-v2"}
        assert all(o.fingerprint_penyajian for o in (*lama.outcomes, *baru.outcomes))
    kode, html, _ = server.minta(f"/anak/{siswa}?section=rencana", auth=("guru", SANDI_GURU))
    assert kode == 200 and "representasi terbaru" in html
    konfirmasi(alur, buat(alur, "latihan_terbimbing"))
    konfirmasi(alur, buat(alur, "penguatan"))
    hari(monkeypatch, 36)
    konfirmasi(alur, buat(alur, "evaluasi"))
    status = rencana(alur)
    assert status.putaran is not None
    assert status.putaran.fokus[0].status == "mulai_membaik"
