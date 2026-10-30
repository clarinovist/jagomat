"""Kontrak paket topik (Fase A, Task A1).

Paket topik adalah unit mandiri: satu topik membawa template, komposisi
lembar per level, profil batas angka, judul bagian, dan renderer badan
khusus miliknya sendiri. Menambah topik baru tidak boleh menyentuh paket
lain — test ini mengunci kontraknya.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import templates  # noqa: E402
import topics  # noqa: E402
from templates import LEVEL  # noqa: E402


@pytest.fixture()
def pb():
    return topics.paket_bawaan()


# ── Registry & identitas paket ─────────────────────────────────────────


def test_paket_pola_bilangan_terdaftar(pb):
    # Superset, bukan daftar tertutup: paket baru boleh masuk tanpa
    # mengubah test lama (keputusan plan 30 Aug 2026, Fase 0).
    assert "pola-bilangan" in topics.daftar_topik()
    assert "aritmetika-dasar" in topics.daftar_topik()
    assert pb.id == "pola-bilangan"
    assert pb.nama == "Pola Bilangan"
    assert pb.judul_lembar == "Latihan Pola Bilangan"
    assert pb.judul_penilaian == "Penilaian — Pola Bilangan"


def test_paket_membawa_16_template(pb):
    assert len(pb.templates) == 16
    for nama in (
        "deret_aritmetika",
        "siklus_huruf",
        "korek_api",
        "titik_segitiga",
        "deret_terbalik_geometri",
        "suku_ke_n",
        "pola_pecahan",
        "jumlah_deret",
    ):
        assert nama in pb.templates, nama


# ── Komposisi lembar per level ─────────────────────────────────────────


def test_komposisi_per_level(pb):
    p3 = pb.komposisi_untuk("P3")
    assert "suku_ke_n" not in p3  # P3: bisa diselesaikan dengan menulis deret
    assert len(pb.komposisi_untuk("P4")) == 12
    assert "pola_pecahan" in pb.komposisi_untuk("P5")
    assert "jumlah_deret" in pb.komposisi_untuk("P6")
    # P3 adalah komposisi bawaan
    assert pb.komposisi_untuk("P3") == pb.komposisi_untuk("XL-tak-dikenal")


def test_profil_per_level(pb):
    assert pb.profil_untuk("P3")["posisi_siklus"] == (15, 40)
    assert pb.profil_untuk("P6")["posisi_siklus"] == (100, 300)
    # Level tak dikenal jatuh ke P3 — data produksi tidak boleh membuat
    # guru gagal membuat sesi (kontrak lama generator.profil).
    assert pb.profil_untuk("tidak-ada") == pb.profil_untuk("P3")


# ── Judul bagian ───────────────────────────────────────────────────────


def test_judul_bagian(pb):
    assert set(pb.judul_bagian) == set("ABCDEF")
    assert "Pola dalam cerita" in pb.judul_bagian["E"]
    assert "jalan pintas" in pb.judul_bagian["F"]


# ── Renderer badan khusus ──────────────────────────────────────────────


def test_render_badan_deret_ditebalkan(pb):
    soal = pb.templates["deret_aritmetika"](awal=2, beda=3, n_tampil=4, n_minta=2)
    badan = pb.render_badan(soal)
    assert 'class="teks deret"' in badan
    assert 'class="isian"' in badan


def test_render_badan_korek_api_menggambar_svg(pb):
    soal = pb.templates["korek_api"](awal=3, tambah=2, gambar_ke=10)
    badan = pb.render_badan(soal)
    assert "<svg" in badan
    assert "batang korek api" in badan


def test_render_badan_titik_segitiga_menggambar_svg(pb):
    soal = pb.templates["titik_segitiga"](gambar_ke=12)
    badan = pb.render_badan(soal)
    assert "<svg" in badan


def test_render_badan_template_lain_menyerahkan_ke_bawaan(pb):
    """Soal tanpa bentuk visual khusus pulang None — render.py memakai
    renderer teks bawaannya."""
    soal = pb.templates["siklus_huruf"](pola=("A", "B", "B", "C"), posisi=9)
    assert pb.render_badan(soal) is None


# ── Kompatibilitas jalur lama lewat templates.py ───────────────────────


def test_templates_registri_menggabungkan_semua_paket():
    pb = topics.paket_bawaan()
    aritmetika = topics.ambil("aritmetika-dasar")
    # Superset, bukan persis dua paket: paket baru tidak boleh memaksa
    # test lama berubah (keputusan plan 30 Aug 2026, Fase 0).
    assert set(pb.templates) | set(aritmetika.templates) <= set(templates.REGISTRI)
    for paket in (pb, aritmetika):
        for tid in paket.templates:
            assert templates.REGISTRI[tid] is paket.templates[tid]


def test_templates_masih_mengekspor_simbol_lama():
    assert templates.URUTAN_LEMBAR == templates.URUTAN_PER_LEVEL["P3"]
    assert templates.susun_lembar("P4") == templates.URUTAN_PER_LEVEL["P4"]
    assert templates.susun_lembar("aneh") == templates.URUTAN_LEMBAR
    # fungsi template ikut diekspor (dipakai test_llm & pemanggil lama)
    assert callable(templates.deret_aritmetika)


# ── Generator sadar-topik (A2) ─────────────────────────────────────────


@pytest.mark.parametrize("level", [lv for lv in LEVEL if lv in templates.URUTAN_PER_LEVEL])
def test_buat_lembar_bertopik_eksplisit_identik_dengan_bawaan(level):
    """Seed sama + topik sama = lembar identik, apa pun cara menyebutnya."""
    from generator import buat_lembar

    bawaan = buat_lembar(2026, level=level)
    eksplisit = buat_lembar(2026, level=level, topik="pola-bilangan")
    assert bawaan.tanda_tangan == eksplisit.tanda_tangan


@pytest.mark.parametrize("level", [lv for lv in LEVEL if lv in templates.URUTAN_PER_LEVEL])
def test_buat_soal_bertopik_eksplisit_identik_dengan_bawaan(level):
    from generator import buat_soal

    bawaan = buat_soal("suku_ke_n", 7, level=level)
    eksplisit = buat_soal("suku_ke_n", 7, level=level, topik="pola-bilangan")
    assert bawaan.tanda_tangan == eksplisit.tanda_tangan


def test_topik_tak_dikenal_melempar_jelas():
    """Topik salah ketik adalah bug pemanggil — dilempar dengan daftar
    topik yang ada, BUKAN jatuh diam-diam ke pola bilangan (beda dengan
    level, yang sengaja fallback karena data produksi)."""
    import generator
    import topics as modul_topik

    with pytest.raises(KeyError, match="geometri-belum-ada"):
        generator.buat_lembar(1, topik="geometri-belum-ada")
    with pytest.raises(KeyError, match="geometri-belum-ada"):
        generator.buat_soal("deret_aritmetika", 1, topik="geometri-belum-ada")
    with pytest.raises(KeyError, match="pola-bilangan"):
        modul_topik.ambil("geometri-belum-ada")


# ── sesi.topik nyata (A3) ──────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    import database

    p = tmp_path / "uji.db"
    database.siapkan(p)
    with database.buka(p) as kon:
        database.tambah_siswa(kon, "Uji Topik", "P3")
        yield kon


def test_buat_sesi_default_pakai_id_kanonik(db):
    import database

    siswa = database.daftar_siswa(db)[0]
    sesi_id = database.buat_sesi(db, siswa["id"], 12345)
    topik = db.execute(
        "SELECT topik FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()["topik"]
    assert topik == "pola-bilangan"
    # lembar yang dibangkitkan memang dari topik itu
    assert len(database.isi_sesi(db, sesi_id)) == 12


def test_buat_sesi_menerima_topik_eksplisit(db):
    import database

    siswa = database.daftar_siswa(db)[0]
    sesi_id = database.buat_sesi(db, siswa["id"], 12345, topik="pola-bilangan")
    topik = db.execute(
        "SELECT topik FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()["topik"]
    assert topik == "pola-bilangan"


def test_ringkasan_memuat_kolom_topik(db):
    import database

    siswa = database.daftar_siswa(db)[0]
    sesi_id = database.buat_sesi(db, siswa["id"], 12345)
    r = db.execute(
        "SELECT topik FROM ringkasan_sesi WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()
    assert r["topik"] == "pola-bilangan"


def test_buat_sesi_seed_baru_meneruskan_topik(db):
    import database
    import teacher_pages

    siswa = database.daftar_siswa(db)[0]
    sesi_id = teacher_pages.buat_sesi_seed_baru(db, siswa["id"], topik="pola-bilangan")
    topik = db.execute(
        "SELECT topik FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()["topik"]
    assert topik == "pola-bilangan"


def test_nilai_sesi_lama_tetap_terbaca():
    """Sesi lama menyimpan 'pola bilangan' (spasi, default kolom pra-Fase A)
    dan bisa saja berisi nilai aneh — keduanya jatuh ke paket bawaan, bukan
    melempar. Kontrak berbeda dari ambil() yang tegas."""
    from topics import dari_sesi

    assert dari_sesi("pola bilangan").id == "pola-bilangan"
    assert dari_sesi(None).id == "pola-bilangan"
    assert dari_sesi("").id == "pola-bilangan"
    with pytest.raises(KeyError):
        topics.ambil("pola bilangan")


# ── Aman terhadap urutan impor ─────────────────────────────────────────


def test_urutan_impor_apapun_hasil_sama():
    """Modul-modul ini saling berkenalan lewat impor malas; urutan impor
    pertama (topik dulu, templates dulu, atau paket dulu) tidak boleh
    mengubah isi."""
    prolog = (
        "import sys; sys.path.insert(0, "
        f"{str(Path(__file__).resolve().parent.parent)!r})\n"
    )
    skenario = {
        "topik_dulu": (
            "import topics\nimport templates\n"
            "assert len(templates.REGISTRI) >= 19\n"
        ),
        "templates_dulu": (
            "import templates\nimport topics\n"
            "assert len(templates.REGISTRI) >= 19\n"
        ),
        "paket_dulu": (
            "import topic_number_patterns\nimport templates\n"
            "assert len(templates.REGISTRI) >= 19\n"
        ),
        "generator_dulu": (
            "import generator\nimport topics\n"
            "assert len(topics.registri()) >= 19\n"
            "assert generator.buat_soal('suku_ke_n', 1, level='P6')\n"
        ),
    }
    for nama, isi in skenario.items():
        hasil = subprocess.run(
            [sys.executable, "-c", prolog + isi],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert hasil.returncode == 0, f"{nama}: {hasil.stderr}"
