"""Modul 3: otomatisasi snapshot peta kemampuan + SVG sebaris Zero-JS laporan orang tua."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import parent_report_page as halaman  # noqa: E402
import parent_report_snapshot as snap  # noqa: E402


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "m3.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon, database.tambah_siswa(kon, "Anak Modul Tiga", pemilik="guru", tingkat="P4")


def _teks_tampil(markup: str) -> str:
    tanpa_gaya = re.sub(r"<style.*?</style>", "", markup, flags=re.S)
    return re.sub(r"<[^>]+>", " ", tanpa_gaya)


def _isi_diagnostik_contoh(kon, anak, hasil_kode: list[tuple[bool, str, str | None]]):
    sesi = database.buat_sesi_diagnostik(kon, anak, 81, level="P4")
    kon.execute("UPDATE sesi SET tanggal = '2026-11-14' WHERE id = ?", (sesi,))
    butir = database.isi_sesi(kon, sesi)
    for idx, b in enumerate(butir):
        benar, kode, mal = hasil_kode[idx % len(hasil_kode)]
        jid = database.simpan_jawaban(
            kon, b["sesi_soal_id"],
            jawaban="JWB_RAHASIA_99" if not benar else "42",
            cara="[pilihan] hitung_kertas",
        )
        database.simpan_diagnosis(
            kon, jid, benar=benar, kode_usulan=None if benar else kode,
            kode_final=None if benar else kode,
            malrule_id=mal, alasan="ALASAN_INTERNAL_GURU_XY",
        )
    database.tandai_selesai(kon, sesi)
    database.konfirmasi_hasil(kon, sesi, "guru", dilewati=set())
    return sesi


def test_snapshot_otomatis_memetakan_fokus_dan_kuat_bebas_rahasia(db):
    kon, anak = db
    # Campur butir K berulang & B supaya muncul "fokus" & alur berpikir terisi.
    pola = [
        (False, "K", "kali_sebagai_tambah"),
        (False, "K", "kali_sebagai_tambah"),
        (True, "B", None),
        (True, "B", None),
        (False, "H", None),
        (True, "B", None),
    ]
    _isi_diagnostik_contoh(kon, anak, pola)

    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert hasil["versi"] == 2
    assert hasil["peta_topik"] and len(hasil["peta_topik"]) <= 6
    status_ada = {p["status"] for p in hasil["peta_topik"]}
    assert status_ada & {"fokus", "pelan", "kuat"}
    assert [a["kode"] for a in hasil["alur_berpikir"]] == ["baca", "konsep", "hitung", "cek"]
    assert hasil["alur_berpikir"][1]["status"] == "macet"  # K >= 2
    assert hasil["langkah_rumah"]
    assert hasil["ringkasan_teruskan"]

    # Pastikan tidak ada satupun sidik rahasia atau istilah internal di JSON snapshot.
    dumped = json.dumps(hasil, ensure_ascii=False)
    for terlarang in (
        "JWB_RAHASIA_99", "ALASAN_INTERNAL_GURU_XY", "kali_sebagai_tambah",
        "malrule", "miskonsepsi", "diagnos", "kunci", "skor", "%", "P3", "P4", "P5", "P6",
    ):
        assert terlarang.lower() not in dumped.lower(), terlarang
    assert not re.search(r"\b[BKHETN]\b(?=\s*[:=])", dumped)


def test_snapshot_tanpa_konfirmasi_memberi_fallback_jujur(db):
    kon, anak = db
    hasil = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")
    assert hasil["peta_topik"] == []
    assert all(a["status"] == "belum" for a in hasil["alur_berpikir"])
    assert "Belum ada" in hasil["cakupan"]


def test_halaman_v2_merender_dua_svg_zero_js_bebas_istilah_terlarang(db):
    kon, anak = db
    _isi_diagnostik_contoh(kon, anak, [(False, "K", "kali_sebagai_tambah"), (True, "B", None)])
    isi = snap.bangun(kon, anak, "2026-11-01", "2026-11-30")

    html_bytes = halaman.render_laporan(
        nama="Raka", isi=isi, catatan="Semangat belajar!", guru="Bu Sari",
        periode=("2026-11-01", "2026-11-30"), diterbitkan="2026-12-01 08:00:00",
        kedaluarsa=1_800_000_000,
    )
    doc = html_bytes.decode("utf-8")
    assert doc.count("<svg") == 2
    assert 'aria-label="Peta kemampuan anak per materi"' in doc
    assert 'aria-label="Peta alur cara berpikir anak"' in doc
    for terlarang in ("<script", "<form", "<a ", "<img", "onclick", "http://", "https://"):
        assert terlarang not in doc, terlarang

    tampil = _teks_tampil(doc)
    for pola in (r"malrule", r"miskonsepsi", r"diagnos", r"kunci", r"/sesi/", r"\bP[3-6]\b",
                 r"Variasi ", r"benar\s*/", r"%", r"#\d", r"\b[BKHETN]\b(?=\s*[:=])"):
        assert not re.search(pola, tampil, re.I if pola != r"\bP[3-6]\b" else 0), pola

    # Urutan heading klasik tetap terjaga.
    urutan = [tampil.index(x) for x in ("Catatan guru", "Langkah berikutnya", "Tahap belajar sekarang", "Yang dilatih")]
    assert urutan == sorted(urutan)


def test_mutasi_status_tak_dikenal_dan_payload_kotor_diabaikan():
    """Negatif/mutasi: status asing di SVG atau kunci rahasia di payload ditolak allowlist."""
    dasar = {
        "versi": 2,
        "topik": ["Pola Bilangan"],
        "tahap": {"nomor": 2, "label": "Pelajari", "uraian": "Belajar lewat contoh."},
        "langkah": "Bahas satu contoh bersama.",
        "peta_topik": [{"nama": "Pola Bilangan", "status": "kuat", "label": "Sudah Kuat"}],
        "alur_berpikir": [{"kode": "baca", "langkah": "Baca Soal", "status": "aman", "label": "Sudah lancar"}],
        "kuat": ["Sudah memahami pola naik."],
        "fokus": [],
        "langkah_rumah": "Ajak anak menyebut selisih antar bilangan.",
        "cakupan": "Ringkasan sesi terperiksa guru.",
        "ringkasan_teruskan": "Materi: Pola Bilangan.",
    }
    kotor = dict(
        dasar,
        peta_topik=dasar["peta_topik"] + [{"nama": "<script>x</script>", "status": "hacked_status", "label": "BOBOL"}],
        kunci="KUNCI_BOCOR",
        malrule_id="MALRULE_BOCOR",
        skor=100,
    )
    hasil_dasar = halaman.render_laporan(
        nama="Tari", isi=dasar, catatan="", guru="Pak Budi",
        periode=("2026-11-01", "2026-11-15"), diterbitkan="2026-11-16 08:00:00",
        kedaluarsa=1_800_000_000,
    )
    hasil_kotor = halaman.render_laporan(
        nama="Tari", isi=kotor, catatan="", guru="Pak Budi",
        periode=("2026-11-01", "2026-11-15"), diterbitkan="2026-11-16 08:00:00",
        kedaluarsa=1_800_000_000,
    )
    assert hasil_dasar == hasil_kotor
    assert b"BOBOL" not in hasil_kotor and b"KUNCI_BOCOR" not in hasil_kotor
