"""Kontrak narasi deterministik ringkasan laporan orang tua."""
from datetime import date
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning_cycle import Intervensi, RencanaBelajar
from learning_journey import BuktiFokusPerjalanan, FokusPerjalanan, PerjalananBelajar
from report_summary import render_ringkasan


def _nama(template_id):
    return template_id.replace("_", " ").title()


def _tanggal(nilai):
    return str(nilai)


def _teks(perjalanan):
    html = render_ringkasan("Anak Uji", perjalanan, 7, _nama, _tanggal)
    return re.sub(r"<[^>]+>", " ", html), html


@pytest.mark.parametrize(
    "kode,tindakan",
    (
        ("B", "Tandai informasi dan ucapkan ulang yang ditanya"),
        ("K", "Gunakan konsep konkret atau visual dan contoh terbimbing"),
        ("H", "Tulis langkah dan periksa ulang perhitungan"),
        ("E", "Cocokkan hasil kerja dengan jawaban akhir"),
        ("N", "Tanyakan: dapat dari mana?"),
        ("T", "Kenalkan materi dengan contoh sederhana"),
    ),
)
def test_langkah_memakai_tindakan_reducer_yang_berbeda(kode, tindakan):
    rencana = RencanaBelajar(
        "intervensi", "alasan internal", intervensi=Intervensi(kode, tindakan, "uji")
    )
    teks, _ = _teks(PerjalananBelajar(rencana))
    assert tindakan in teks
    assert "alasan internal" not in teks


def test_dua_fokus_template_sama_tetap_dua_slot_dan_status_terpisah():
    fokus = (
        FokusPerjalanan(("soal_umur", "K", "rahasia-a"), "mulai_membaik"),
        FokusPerjalanan(("soal_umur", "K", "rahasia-b"), "perlu_diperkuat"),
    )
    teks, html = _teks(PerjalananBelajar(RencanaBelajar("intervensi", ""), fokus=fokus))
    assert teks.count("Bagian 1") == 2
    assert teks.count("Bagian 2") == 2
    assert "mulai membaik" in teks
    assert "masih perlu diperkuat" in teks
    assert "rahasia-a" not in html and "rahasia-b" not in html
    terlihat = html.split("Yang terlihat", 1)[1].split("</section>", 1)[0]
    diperiksa = html.split("Yang masih perlu diperiksa", 1)[1].split("</section>", 1)[0]
    assert terlihat.count('<li class="item-fokus-ringkasan">') == 2
    assert diperiksa.count('<li class="item-fokus-ringkasan">') == 2


@pytest.mark.parametrize("pemahaman", ("ragu", "menghafal"))
def test_ragu_atau_menghafal_tidak_disebut_lulus(pemahaman):
    bukti = BuktiFokusPerjalanan(
        date(2026, 9, 10), 2, "evaluasi", (pemahaman,), hasil="perlu_diperkuat"
    )
    fokus = FokusPerjalanan(("soal_umur", "K", None), "perlu_diperkuat", (bukti,))
    teks, _ = _teks(PerjalananBelajar(RencanaBelajar("intervensi", ""), fokus=(fokus,)))
    assert pemahaman in teks
    assert "mulai membaik" not in teks
    assert "bertahan" not in teks


def test_menunggu_jadwal_dan_bertahan_tidak_dipercepat_atau_dipermanenkan():
    menunggu = PerjalananBelajar(
        RencanaBelajar("tunggu_evaluasi", "", tersedia_pada=date(2026, 9, 16)),
        fokus=(FokusPerjalanan(("soal_umur", "K", None), "menunggu_evaluasi"),),
    )
    teks, _ = _teks(menunggu)
    assert "Tunggu cek beberapa hari lagi" in teks
    assert "2026-09-16" in teks
    bertahan = PerjalananBelajar(
        RencanaBelajar("tunggu_checkpoint", ""),
        fokus=(FokusPerjalanan(("soal_umur", "K", None), "bertahan"),),
    )
    teks, _ = _teks(bertahan)
    assert "bukan penguasaan permanen" in teks
    assert "checkpoint berkala" in teks


@pytest.mark.parametrize("tindakan", ("intervensi", "pengenalan"))
def test_hanya_action_instruksional_memakai_teks_intervensi(tindakan):
    rencana = RencanaBelajar(
        tindakan, "", intervensi=Intervensi("K", "Instruksi reducer", "uji")
    )
    teks, _ = _teks(PerjalananBelajar(rencana))
    assert "Instruksi reducer" in teks


def test_known_action_noninstruksional_tidak_memakai_teks_intervensi():
    rencana = RencanaBelajar(
        "evaluasi", "", intervensi=Intervensi("K", "Instruksi tak relevan", "uji")
    )
    teks, html = _teks(PerjalananBelajar(rencana))
    assert "Cek lagi setelah jeda" in teks
    assert "Instruksi tak relevan" not in html


def test_unknown_action_dengan_intervensi_tetap_memakai_fallback_konservatif():
    rencana = RencanaBelajar(
        "aksi_internal_rahasia",
        "jangan bocor",
        intervensi=Intervensi("K", "Teks intervensi tak boleh dipakai", "uji"),
    )
    teks, html = _teks(PerjalananBelajar(rencana))
    assert "Tinjau rencana bersama" in teks
    assert "Teks intervensi tak boleh dipakai" not in html
    assert "aksi_internal_rahasia" not in html
    assert "jangan bocor" not in html


def test_materi_baru_dan_unknown_state_dijelaskan_konservatif():
    materi = PerjalananBelajar(
        RencanaBelajar("pengenalan", "", kandidat=(("piktogram", "T", None),))
    )
    teks, _ = _teks(materi)
    assert "materi baru bukan kelemahan" in teks.lower()
    asing = PerjalananBelajar(
        RencanaBelajar("aksi_internal_rahasia", "jangan bocor"),
        fokus=(FokusPerjalanan(("soal_umur", "K", "malrule-rahasia"), "status_rahasia"),),
    )
    teks, html = _teks(asing)
    assert "Tinjau rencana bersama" in teks
    assert "perlu ditinjau" in teks.lower()
    assert "aksi_internal_rahasia" not in html
    assert "status_rahasia" not in html
    assert "malrule-rahasia" not in html
    assert "jangan bocor" not in html


@pytest.mark.parametrize(
    "tindakan",
    (
        "lanjutkan_sesi", "konfirmasi_hasil", "eskalasi", "pemetaan",
        "tunggu_pemetaan", "probe_diagnostik", "intervensi",
        "latihan_terbimbing", "penguatan", "evaluasi", "tunggu_evaluasi",
        "checkpoint", "tunggu_checkpoint", "probe_setelah_pengenalan",
        "pengenalan", "mixed_maintenance", "putaran_baru", "tidak_dikenal",
    ),
)
def test_semua_action_rencana_punya_label_atau_fallback_tanpa_raw_state(tindakan):
    rencana = RencanaBelajar(tindakan, "alasan-rahasia")
    teks, html = _teks(PerjalananBelajar(rencana))
    assert "Langkah berikutnya" in teks
    assert "alasan-rahasia" not in html
    if "_" in tindakan or tindakan == "tidak_dikenal":
        assert tindakan not in html
    if tindakan == "tidak_dikenal":
        assert "Tinjau rencana bersama" in teks


def test_dua_fokus_dengan_catatan_tetap_di_bawah_180_kata_dan_aman():
    fokus = (
        FokusPerjalanan(("<tipe-a>", "K", "rahasia-a"), "mulai_membaik"),
        FokusPerjalanan(("tipe_b", "H", "rahasia-b"), "perlu_diperkuat"),
    )
    perjalanan = PerjalananBelajar(
        RencanaBelajar("eskalasi", "alasan-rahasia"),
        fokus=fokus,
        catatan=("Catatan <b>dikoreksi</b>; perlu konfirmasi ulang.",),
    )
    teks, html = _teks(perjalanan)
    isi = re.sub(r"<[^>]+>", " ", html.split("Dasar ringkasan:", 1)[0])
    assert len(re.findall(r"\b[\wÀ-ÿ-]+\b", isi)) <= 180
    assert "<tipe-a>" not in html and "&lt;Tipe-A&gt;" in html
    assert "<b>dikoreksi</b>" not in html and "&lt;b&gt;dikoreksi&lt;/b&gt;" in html
    assert "rahasia-a" not in html and "rahasia-b" not in html
    assert "alasan-rahasia" not in html
    assert teks.count("Bagian 1") == 2 and teks.count("Bagian 2") == 2


def test_sumber_ringkasan_tidak_mengaku_semua_bukti_sudah_dikonfirmasi():
    _, html = _teks(PerjalananBelajar(RencanaBelajar("konfirmasi_hasil", "")))
    assert "perjalanan dan status catatan hasil" in html
    assert "perjalanan dan bukti yang dikonfirmasi" not in html


def test_catatan_koreksi_dan_beda_level_tetap_terlihat_dan_ringkas():
    perjalanan = PerjalananBelajar(
        RencanaBelajar("konfirmasi_hasil", ""),
        catatan=(
            "Bukti dikoreksi; perlu konfirmasi ulang.",
            "Riwayat kelas berbeda tetap tersimpan dan tidak menjadi bukti kelas aktif.",
        ),
    )
    teks, html = _teks(perjalanan)
    assert "perlu konfirmasi ulang" in teks.lower()
    assert "kelas berbeda" in teks.lower()
    isi = re.sub(r"<[^>]+>", " ", html.split("Dasar ringkasan:", 1)[0])
    assert len(re.findall(r"\b[\wÀ-ÿ-]+\b", isi)) <= 180
    assert html.count("Lihat langkah berikutnya") == 1
