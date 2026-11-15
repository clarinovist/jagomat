"""Regresi integrasi Ringkasan Analisis Pasangan Diagnostik (halaman guru).

Membuktikan agregator benar-benar dipanggil alur produk, bukan hanya dari tes
unitnya, serta guard komposisi/peran dan escaping tetap aktif.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import diagnostic_battery  # noqa: E402
import diagnostic_summary  # noqa: E402
import diagnosis  # noqa: E402
import students  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "ringkasan-diagnostik.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    return p


def _butir(level, per_konsep=None):
    """Butir berpasangan exact; per_konsep: {template_id: [(benar, kode), ...]}."""
    per_konsep = per_konsep or {}
    daftar = []
    for spec in diagnostic_battery.daftar_spesifikasi(level):
        for benar, kode in per_konsep.get(spec.template_id, [(1, None), (1, None)]):
            daftar.append({
                "template_id": spec.template_id,
                "benar": int(bool(benar)),
                "kode_final": kode,
                "kode_usulan": kode,
                "alasan": "",
                "belum_pernah": 0,
                "dilewati": 0,
            })
    return daftar


def _jawab_satu_butir(kon, siswa_id, sesi_id):
    butir = database.isi_sesi(kon, sesi_id)
    ssid = butir[0]["sesi_soal_id"]
    students.simpan_jawaban_murid(kon, siswa_id, sesi_id, {
        f"jwb_{ssid}": str(butir[0]["kunci"]) + "?",
        f"pilih_{ssid}": "hitung_kertas",
    })
    database.tandai_selesai(kon, sesi_id)


def test_halaman_guru_memanggil_agregator_untuk_sesi_baterai(db):
    """Regresi utama: tanpa integrasi, halaman sesi tidak memuat blok ini."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Alya Contoh", "P3", pemilik="guru")
        sesi_id = database.buat_sesi_diagnostik(kon, sid, seed=11)
        _jawab_satu_butir(kon, sid, sesi_id)
        halaman = teacher_pages.halaman_sesi_stitch(
            kon, sesi_id, peran="guru", pengguna="guru"
        ).decode()
    assert 'data-ringkasan-diagnostik' in halaman
    assert 'Ringkasan Tes Diagnostik Baku' in halaman
    # Label awam, bukan kode diagnosis / malrule / skor mentah.
    assert 'konsisten_k' not in halaman
    assert '<span class="kode' not in halaman.split('data-ringkasan-diagnostik')[1].split('</section>')[0]


def test_halaman_guru_tanpa_blok_untuk_sesi_biasa(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Bima Contoh", "P3", pemilik="guru")
        sesi_id = database.buat_sesi(
            kon, sid, seed=3, topik="pola-bilangan", level="P3"
        )
        _jawab_satu_butir(kon, sid, sesi_id)
        halaman = teacher_pages.halaman_sesi_stitch(
            kon, sesi_id, peran="guru", pengguna="guru"
        ).decode()
    assert 'data-ringkasan-diagnostik' not in halaman


def test_status_triase_dan_label_awam():
    butir = _butir("P3", {
        "perkalian_dasar": [(0, "K"), (0, "K")],       # konsisten_k + triase
        "pecahan_bagian_dasar": [(0, "H"), (1, None)],  # teliti
    })
    hasil = diagnostic_summary.ringkasan(butir, "P3", "guru")
    assert 'data-ringkasan-diagnostik' in hasil
    assert 'Perlu pendalaman konsep' in hasil
    assert 'Perlu ketelitian' in hasil
    assert 'Triase prasyarat belum kuat' in hasil
    assert 'Prasyarat' in hasil


def test_guard_peran_dan_level_asing():
    butir = _butir("P3")
    assert diagnostic_summary.ringkasan(butir, "P3", "murid") == ""
    assert diagnostic_summary.ringkasan(butir, "P3", "ortu") == ""
    assert diagnostic_summary.ringkasan(butir, "SMA", "guru") == ""
    assert diagnostic_summary.ringkasan(butir[:-1], "P3", "guru") == ""


def test_judul_diescape(monkeypatch):
    from diagnosis import RingkasanKonsep
    butir = _butir("P3")
    monkeypatch.setattr(
        diagnosis, "evaluasi_pasangan_diagnostik",
        lambda *a, **k: {
            "level": "P3", "triase_macet": False,
            "ringkasan": [RingkasanKonsep(
                "x", "<script>alert(1)</script>", "D", False, "kuat", None
            )],
        },
    )
    hasil = diagnostic_summary.ringkasan(butir, "P3", "guru")
    assert '<script>' not in hasil
    assert '&lt;script&gt;' in hasil


def test_mutation_guard_komposisi(monkeypatch):
    """Guard dinonaktifkan → sesi biasa ikut diringkas; pulihkan → kosong."""
    butir = _butir("P3")
    butir[0]["template_id"] = "template_asing"
    assert diagnostic_summary.ringkasan(butir, "P3", "guru") == ""
    monkeypatch.setattr(
        diagnostic_summary, "sesi_baterai", lambda *a, **k: True
    )
    assert diagnostic_summary.ringkasan(butir, "P3", "guru") != ""


def test_mutation_guard_peran(monkeypatch):
    """Guard peran dinonaktifkan → peran murid ikut menerima ringkasan."""
    butir = _butir("P3")
    assert diagnostic_summary.ringkasan(butir, "P3", "murid") == ""
    monkeypatch.setattr(
        diagnostic_summary, "_peran_diizinkan", lambda *a, **k: True
    )
    assert diagnostic_summary.ringkasan(butir, "P3", "murid") != ""
