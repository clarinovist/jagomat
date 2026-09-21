"""Integrasi laporan perjalanan: hanya bukti sah, tanpa mutasi GET."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import reports
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji


@pytest.fixture()
def db(tmp_path):
    berkas = tmp_path / "laporan.db"
    database.siapkan(berkas)
    return berkas


def _pemetaan(kon, sid, putaran, nomor, konfirmasi=True):
    sesi = database.buat_sesi_dari_urutan(
        kon, sid, nomor, ("deret_aritmetika",), level="P3"
    )
    database.tautkan_sesi_putaran(kon, putaran, [sesi])
    kon.execute(
        "UPDATE sesi SET tujuan = 'pemetaan', tanggal = ? WHERE id = ?",
        (f"2026-08-{nomor:02d}", sesi),
    )
    butir = database.isi_sesi(kon, sesi)[0]
    jawaban = database.simpan_jawaban(kon, butir["sesi_soal_id"], "salah")
    database.simpan_diagnosis(
        kon, jawaban, False, "K", "K", "uji-rahasia", "alasan-internal"
    )
    database.tandai_selesai(kon, sesi)
    if konfirmasi:
        database.konfirmasi_hasil(kon, sesi, "guru")
    return sesi, jawaban


def _fokus(kon, sid):
    putaran = database.buat_putaran_fokus(kon, sid, "P3")
    sumber = tuple(_pemetaan(kon, sid, putaran, n) for n in (1, 2, 3))
    database.tambah_anggota_fokus(
        kon, putaran, "deret_aritmetika", "K", "uji-rahasia",
        [sesi for sesi, _ in sumber],
    )
    return putaran, sumber


def _utama(teks):
    assert 'id="perjalanan-belajar"' in teks
    return teks.split('id="perjalanan-belajar"', 1)[1]


def test_resume_laporan_bersumber_dari_perjalanan_bukan_statistik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Ringkas Uji", pemilik="guru")
        _pemetaan(kon, sid, database.buat_putaran_fokus(kon, sid, "P3"), 1)
        h = reports.halaman_laporan(kon, sid).decode()

    ringkasan = h.split('<div class="kartu ringkasan-laporan">', 1)[1].split(
        "</div>", 1
    )[0]
    assert "Posisi belajar saat ini" in ringkasan
    assert "Masih perlu diperiksa" in ringkasan
    assert 'class="resume-langkah"' in ringkasan
    assert f'href="/anak/{sid}#judul-rencana-belajar"' in ringkasan
    assert h.count('<section class="kartu laporan-resume"') == 1
    assert '<summary>Lihat rencana belajar</summary>' not in h
    assert "1 sesi dinilai" not in ringkasan
    assert "kekeliruan konsep" not in ringkasan


def test_laporan_baru_meminta_pemetaan_bukan_menyimpulkan_penguasaan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak Uji", pemilik="guru")
        sebelum = kon.total_changes
        h = reports.halaman_laporan(kon, sid, section="penguasaan", query='tampilan=perjalanan').decode()
        assert kon.total_changes == sebelum
    assert 'id="perjalanan-belajar"' in h
    assert "Pemetaan 0 dari 3" in _utama(h)
    assert "belum cukup bukti" in _utama(h).lower()
    assert 'tampilan=materi' in h and 'tampilan=kriteria' in h
    assert 'id="judul-peta"' not in h


def test_hasil_belum_disahkan_tidak_menjadi_fokus_laporan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Belum Sah", pemilik="guru")
        putaran = database.buat_putaran_fokus(kon, sid, "P3")
        for n in (1, 2, 3):
            _pemetaan(kon, sid, putaran, n, konfirmasi=False)
        h = reports.halaman_laporan(kon, sid, section="penguasaan", query='tampilan=perjalanan').decode()
    utama = _utama(h)
    assert "Konfirmasi hasil" in utama
    assert "Perlu dipelajari" not in utama
    assert "uji-rahasia" not in utama
    assert "alasan-internal" not in utama
    assert "Mulai dari topik" not in h


def test_ringkasan_fokus_lama_tetap_menyebut_ada_hasil_belum_dikonfirmasi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Pending Uji", pemilik="guru")
        putaran, _ = _fokus(kon, sid)
        sesi = database.buat_sesi_dari_urutan(
            kon, sid, 88, ("deret_aritmetika",), level="P3"
        )
        database.tautkan_sesi_putaran(kon, putaran, [sesi])
        kon.execute(
            "UPDATE sesi SET tujuan = 'latihan_terbimbing' WHERE id = ?", (sesi,)
        )
        database.tandai_selesai(kon, sesi)
        h = reports.halaman_laporan(kon, sid).decode()

    ringkasan = h.split('<div class="kartu ringkasan-laporan">', 1)[1].split(
        "</div>", 1
    )[0]
    assert "ada hasil sesi yang belum dikonfirmasi" in ringkasan.lower()
    assert "hasil terbaru" not in ringkasan.lower()
    assert "Konfirmasi hasil" in ringkasan


def test_laporan_memakai_bukti_sah_dan_tidak_menulis_db(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Fokus Uji", pemilik="guru")
        putaran, sumber = _fokus(kon, sid)
        sebelum = kon.total_changes
        h = reports.halaman_laporan(kon, sid, section="penguasaan", query='tampilan=perjalanan').decode()
        assert kon.total_changes == sebelum
    utama = _utama(h)
    assert f"Putaran #{putaran}" in utama
    assert "Perlu dipelajari" in utama
    assert reports._nama_tipe_soal("deret_aritmetika") in utama
    assert all(f'/sesi/{sesi}' in utama for sesi, _ in sumber)
    assert "uji-rahasia" not in utama
    assert "alasan-internal" not in utama


def test_actual_report_memisahkan_dua_fokus_dengan_status_reducer_berbeda(db):
    from learning_cycle import PutaranFokus, RencanaBelajar, StatusFokus

    fokus_a = ("deret_aritmetika", "K", "uji-rahasia")
    fokus_b = ("soal_umur", "H", None)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tunas", pemilik="guru")
        putaran, sumber = _fokus(kon, sid)
        database.tambah_anggota_fokus(
            kon, putaran, fokus_b[0], fokus_b[1], fokus_b[2],
            [sesi for sesi, _ in sumber],
        )
        rencana = RencanaBelajar(
            "evaluasi", "uji",
            putaran=PutaranFokus(
                putaran, "P3",
                (StatusFokus(fokus_a, "perlu_dipelajari"),
                 StatusFokus(fokus_b, "perlu_dipelajari")),
            ),
            kandidat=(fokus_a,), jumlah_probe_minimum=4,
        )
        evaluasi = database.buat_sesi_dari_rencana(
            kon, sid, rencana, putaran_id=putaran, seed=909
        )
        cek = {}
        dilewati = set()
        for butir in database.isi_sesi(kon, evaluasi):
            if butir["template_id"] != fokus_a[0]:
                dilewati.add(butir["sesi_soal_id"])
                continue
            jawaban = database.simpan_jawaban(
                kon, butir["sesi_soal_id"], butir["kunci"]
            )
            database.simpan_diagnosis(
                kon, jawaban, True, None, None, None, "tepat"
            )
            cek[butir["sesi_soal_id"]] = "bisa_menjelaskan"
        database.tandai_selesai(kon, evaluasi)
        database.konfirmasi_hasil(
            kon, evaluasi, "guru", dilewati=dilewati, cek_pemahaman=cek
        )
        h = reports.halaman_laporan(kon, sid).decode()

    ringkasan = h.split('<div class="kartu ringkasan-laporan">', 1)[1].split(
        "</div>", 1
    )[0]
    terlihat = ringkasan.split("Posisi belajar saat ini", 1)[1].split("</section>", 1)[0]
    assert terlihat.count('<li class="item-fokus-ringkasan">') == 2
    fokus_1, fokus_2 = terlihat.split("Fokus 1", 1)[1].split("Fokus 2", 1)
    assert "mulai membaik" in fokus_1
    assert "masih perlu dipelajari" in fokus_2
    assert "uji-rahasia" not in ringkasan


def test_invalidasi_tidak_menghilangkan_riwayat_atau_mengaku_bukti_aktif(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Koreksi Uji", pemilik="guru")
        putaran, sumber = _fokus(kon, sid)
        sesi, jawaban = sumber[-1]
        database.simpan_diagnosis(kon, jawaban, True, None, None, None, "benar")
        sebelum = kon.execute("SELECT COUNT(*) FROM snapshot_outcome").fetchone()[0]
        h = reports.halaman_laporan(kon, sid, section="penguasaan", query='tampilan=perjalanan').decode()
        assert kon.execute("SELECT COUNT(*) FROM snapshot_outcome").fetchone()[0] == sebelum
    assert "Konfirmasi hasil" in _utama(h)
    assert "konfirmasi ulang" in _utama(h).lower()
    assert f"Putaran #{putaran}" in _utama(h)


def test_rekonfirmasi_setelah_putaran_ditutup_tidak_disebut_pending(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Koreksi Histori", pemilik="guru")
        putaran, sumber = _fokus(kon, sid)
        kon.execute(
            "INSERT INTO kejadian_belajar (siswa_id, putaran_id, jenis) "
            "VALUES (?, ?, 'putaran_ditutup')", (sid, putaran),
        )
        sesi, jawaban = sumber[-1]
        database.simpan_diagnosis(kon, jawaban, True, None, None, None, "benar")
        database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = kon.total_changes
        h = reports.halaman_laporan(kon, sid, section="penguasaan", query='tampilan=perjalanan').decode()
        assert kon.total_changes == sebelum
    histori = h.split("Riwayat putaran sebelumnya", 1)[1]
    assert "sudah dikonfirmasi ulang" in histori
    assert "perlu konfirmasi ulang" not in histori


def test_renderer_histori_pemahaman_dan_escape():
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import BuktiFokusPerjalanan, HistoriPutaran, PerjalananBelajar
    from cycle_report import render_perjalanan

    bukti = (
        BuktiFokusPerjalanan(date(2026, 8, 3), 3, "evaluasi", ("bisa_menjelaskan",)),
        BuktiFokusPerjalanan(date(2026, 8, 4), 4, "checkpoint"),
    )
    histori = HistoriPutaran(
        1, "P3", date(2026, 8, 1), date(2026, 8, 5), "diganti_level",
        (("<script>uji</script>", "K", "rahasia"),), bukti,
    )
    data = PerjalananBelajar(RencanaBelajar("pemetaan", ""), histori=(histori,))
    h = render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek)
    assert "Riwayat putaran sebelumnya" in h
    assert "Variasi soal rencana berubah" in h
    assert "Bisa menjelaskan" in h
    assert "Pemahaman belum tercatat" in h
    assert "<script>" not in h
    assert "rahasia" not in h
    assert "&lt;script&gt;" in h.lower()


@pytest.mark.parametrize("tindakan", ("pengenalan", "probe_setelah_pengenalan", "mixed_maintenance"))
def test_tanpa_fokus_setelah_pemetaan_bukan_kekurangan_bukti(tindakan):
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import PerjalananBelajar
    from cycle_report import render_perjalanan

    rencana = RencanaBelajar(tindakan, "", kandidat=(("piktogram", "T", None),))
    data = PerjalananBelajar(
        rencana, tanggal_pemetaan=(date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3))
    )
    h = render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek)
    assert "Belum cukup bukti" not in h
    assert "Tidak ada fokus aktif" in h
    if tindakan != "mixed_maintenance":
        assert "Piktogram" in h
        assert "bukan kelemahan" in h.lower()


def test_histori_menampilkan_hasil_terpisah_setiap_fokus():
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import (
        BuktiFokusPerjalanan, FokusPerjalanan, HistoriPutaran, PerjalananBelajar,
    )
    from cycle_report import render_perjalanan

    kunci_a = ("deret_aritmetika", "K", "rahasia-a")
    kunci_b = ("deret_aritmetika", "K", "rahasia-b")
    bukti_a = BuktiFokusPerjalanan(date(2026, 8, 3), 3, "evaluasi", hasil="mulai_membaik")
    fokus = (
        FokusPerjalanan(kunci_a, "mulai_membaik", (bukti_a,)),
        FokusPerjalanan(kunci_b, "perlu_dipelajari"),
    )
    histori = HistoriPutaran(
        1, "P3", date(2026, 8, 1), date(2026, 8, 5), "putaran_ditutup",
        (kunci_a, kunci_b), perjalanan_fokus=fokus,
    )
    data = PerjalananBelajar(RencanaBelajar("pemetaan", ""), histori=(histori,))
    h = render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek)
    riwayat = h.split("Riwayat putaran sebelumnya", 1)[1]
    pertama, kedua = riwayat.split("Fokus 1:", 1)[1].split("Fokus 2:", 1)
    assert "Mulai membaik" in pertama
    assert "Perlu dipelajari" in kedua
    assert '/sesi/3' in pertama and '/sesi/3' not in kedua
    assert "rahasia-a" not in h and "rahasia-b" not in h


def test_histori_per_fokus_tetap_memuat_jejak_koreksi_setelah_konfirmasi_ulang():
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import (
        BuktiFokusPerjalanan, FokusPerjalanan, HistoriPutaran, PerjalananBelajar,
    )
    from cycle_report import render_perjalanan

    kunci = ("deret_aritmetika", "K", "uji")
    koreksi = BuktiFokusPerjalanan(
        date(2026, 8, 3), 3, "bukti_dibatalkan", status="riwayat_invalidasi"
    )
    histori = HistoriPutaran(
        1, "P3", date(2026, 8, 1), date(2026, 8, 5), "putaran_ditutup",
        (kunci,), (koreksi,), perjalanan_fokus=(FokusPerjalanan(kunci, "mulai_membaik"),),
    )
    h = render_perjalanan(
        PerjalananBelajar(RencanaBelajar("pemetaan", ""), histori=(histori,)),
        reports._nama_tipe_soal, reports._tanggal_pendek,
    )
    assert "Bukti dikoreksi" in h
    assert "sudah dikonfirmasi ulang" in h
    assert "perlu konfirmasi ulang" not in h.lower()


def test_bukti_perjalanan_membungkus_teks_bukan_flex_sebaris():
    from teacher_style import GAYA_GURU

    selector = "#perjalanan-belajar .diagnosis-lis li"
    assert selector in GAYA_GURU
    aturan = GAYA_GURU.split(selector, 1)[1].split("}", 1)[0]
    assert "display: block" in aturan


def test_usulan_fokus_tanpa_putaran_tidak_disebut_pemetaan_awal():
    from learning_cycle import RencanaBelajar
    from learning_journey import FokusPerjalanan, PerjalananBelajar
    from cycle_report import render_perjalanan

    data = PerjalananBelajar(
        RencanaBelajar("intervensi", ""),
        fokus=(FokusPerjalanan(("deret_aritmetika", "K", None), "perlu_dipelajari"),),
    )
    h = render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek)
    assert "Fokus disarankan — putaran belum dimulai" in h
    assert "Pemetaan awal" not in h


def test_bukti_lama_terbuka_tanpa_menggandakan_tautan_sesi():
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import BuktiFokusPerjalanan, FokusPerjalanan, PerjalananBelajar
    from cycle_report import render_perjalanan

    bukti = tuple(BuktiFokusPerjalanan(date(2026, 8, n), n, "penguatan") for n in range(1, 7))
    data = PerjalananBelajar(
        RencanaBelajar("evaluasi", ""),
        fokus=(FokusPerjalanan(("deret_aritmetika", "K", None), "menunggu_evaluasi", bukti),),
        putaran_id=1,
    )
    h = render_perjalanan(data, reports._nama_tipe_soal, reports._tanggal_pendek)
    assert '<details' not in h
    assert '<section class="bukti-lainnya">' in h
    ringkas = h.split('<section class="bukti-lainnya">', 1)[0]
    assert '/sesi/6' in ringkas
    assert '/sesi/1"' not in ringkas
    assert all(h.count(f'href="/sesi/{n}"') == 1 for n in range(1, 7))


@pytest.mark.parametrize("bagian", ["ringkasan", "penguasaan", "riwayat"])
def test_get_laporan_lewat_http_menjaga_kepemilikan(tmp_path, monkeypatch, bagian):
    import assistant_client
    import assistant_service
    import llm

    panggilan = []

    def ai_terlarang(*args, **kwargs):
        panggilan.append((args, kwargs))
        raise AssertionError("GET laporan tidak boleh memanggil provider AI")

    monkeypatch.setattr(assistant_service, "panggil_provider_default", ai_terlarang)
    monkeypatch.setattr(assistant_client, "kirim", ai_terlarang)
    monkeypatch.setattr(llm, "_panggil", ai_terlarang)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            sid = database.tambah_siswa(kon, "Anak Milik Guru", pemilik="guru")
            asing = database.tambah_siswa(kon, "Jangan Bocor", pemilik="lain")
            _fokus(kon, sid)
            sebelum = tuple(kon.iterdump())
        kode, h, _ = server.minta(f"/laporan/{sid}?section={bagian}", auth=("guru", SANDI_GURU))
        kode_ulang, h_ulang, _ = server.minta(
            f"/laporan/{sid}?section={bagian}", auth=("guru", SANDI_GURU)
        )
        assert kode == kode_ulang == 200
        assert h == h_ulang
        assert isinstance(h, str)
        assert ('tampilan=perjalanan' in h) == (bagian == "penguasaan")
        kode_asing, h_asing, _ = server.minta(f"/laporan/{asing}", auth=("guru", SANDI_GURU))
        kode_hilang, h_hilang, _ = server.minta("/laporan/999999", auth=("guru", SANDI_GURU))
        assert kode_asing == kode_hilang == 404
        assert h_asing == h_hilang
        assert isinstance(h_asing, str)
        assert "Jangan Bocor" not in h_asing
        kode_murid, h_murid, _ = server.minta(f"/laporan/{sid}", auth=("feby", SANDI_MURID))
        assert kode_murid in (401, 403)
        assert isinstance(h_murid, str)
        assert "Perjalanan fokus belajar" not in h_murid
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
        assert panggilan == []
    finally:
        server.berhenti()
