"""Tes batas impor inti soal (paket soal, Fase 0).

Inti soal = penutupan transitif impor `generator` di `mesin/`. Batas ini dijaga
supaya inti bisa dipisah jadi paket/layanan sendiri: inti tidak boleh bergantung
pada modul aplikasi (web, db, akun, dst.). Hanya AST yang dipakai; tidak ada modul
aplikasi yang diimpor atau dijalankan.

Cara memperbarui daftar (bila tes ini merah karena modul baru):
  * Modul baru memang bagian inti soal (mis. `awal_*.py` yang diimpor
    topik/generator): tambahkan namanya ke `INTI_SOAL` secara terurut.
  * Impor itu tidak disengaja / modul aplikasi: hapus impornya dari modul inti.
  Jangan melonggarkan tes ini dengan menambah modul aplikasi ke `INTI_SOAL`.
"""
import ast
import unittest
from pathlib import Path

MESIN = Path(__file__).resolve().parent.parent
TITIK_MASUK = "generator"

# Modul non-stdlib yang boleh diimpor inti, tetapi bukan bagian inti.
# Harus berupa daun: tidak boleh mengimpor modul mesin/ lain (dicek di bawah).
ALLOWLIST = frozenset({"design_tokens"})

# Inti soal: penutupan transitif impor `generator` (di luar ALLOWLIST).
INTI_SOAL = frozenset({
    "adegan_awal_bentuk_data",
    "adegan_awal_busur_data",
    "adegan_awal_jam_data",
    "adegan_awal_tumpukan_data",
    "adegan_awal_data",
    "assessment_revision",
    "awal_baca_diagram_gambar",
    "awal_baca_jam_awal",
    "awal_bandingkan_ciri_bangun",
    "awal_bilang_benda_awal",
    "awal_ciri_komposisi_bangun",
    "awal_keliling_gabungan",
    "awal_kenali_bangun_awal",
    "awal_kenali_bentuk",
    "awal_luas_petak_volume_kubus",
    "awal_pecahan_bilangan_asli_desimal",
    "awal_pecahan_senilai_desimal",
    "awal_pecahan_setengah",
    "awal_peluang_dasar",
    "awal_pola_posisi",
    "awal_tambah_kurang_100",
    "awal_tambah_kurang_20",
    "awal_turus_gambar_awal",
    "awal_ukur_konversi_awal",
    "awal_ukur_satuan_tak_baku",
    "awal_tampak_kubus_awal",
    "awal_ukur_sudut_awal",
    "awal_unsur_bangun_datar",
    "awal_waktu_berat_awal",
    "basic_numbers_place_compare",
    "basic_numbers_versions",
    "bentuk_katalog",
    "catalog_diagnosis",
    "catalog_exact",
    "catalog_followup",
    "catalog_keys",
    "catalog_logic",
    "catalog_malrules",
    "catalog_versions",
    "combinatorics_visual_data",
    "generator",
    "generator_version",
    "matematika_awal_versions",
    "measurement_combinatorics_visual_data",
    "measurement_scale_data",
    "measurement_versions",
    "number_patterns_visual_data",
    "number_theory_expansion",
    "number_theory_versions",
    "plane_geometry_visual_data",
    "school_numbers_column",
    "school_numbers_common",
    "school_numbers_equation",
    "school_numbers_muldiv",
    "school_numbers_order",
    "school_numbers_versions",
    "solid_geometry_nets",
    "solid_geometry_numbers",
    "solid_geometry_versions",
    "solid_geometry_visual_data",
    "statistics_visual_data",
    "templates",
    "topic_advanced_arithmetic",
    "topic_basic_arithmetic",
    "topic_basic_numbers",
    "topic_combinatorics",
    "topic_logic",
    "topic_matematika_awal",
    "topic_measurement",
    "topic_number_patterns",
    "topic_number_patterns_param",
    "topic_number_patterns_svg",
    "topic_number_theory",
    "topic_plane_geometry",
    "topic_plane_geometry_param",
    "topic_school_basics",
    "topic_school_numbers",
    "topic_solid_geometry",
    "topic_statistics",
    "topics",
    "visual_contract",
})

FUNGSI_IMPOR_DINAMIS = frozenset({"__import__", "import_module"})

PETUNJUK = (
    "Cara memperbarui: jika modul itu memang bagian inti soal, tambahkan ke "
    "INTI_SOAL di mesin/__tests__/test_batas_soal.py (terurut). Jika tidak, "
    "hapus impornya dari modul inti. Jangan menambah modul aplikasi ke INTI_SOAL."
)


def _modul_mesin():
    return {p.stem for p in MESIN.glob("*.py")}


def _nama_fungsi(panggilan):
    fungsi = panggilan.func
    if isinstance(fungsi, ast.Name):
        return fungsi.id
    if isinstance(fungsi, ast.Attribute):
        return fungsi.attr
    return None


def _akar(nama):
    return nama.split(".")[0]


def _impor_node(node):
    """Nama modul (akar) yang diimpor satu node; bisa kosong."""
    if isinstance(node, ast.Import):
        return {_akar(a.name) for a in node.names}
    if isinstance(node, ast.ImportFrom):
        if node.module:
            return {_akar(node.module)}
        # `from . import x` / `from .. import x`: x adalah modul sejawat.
        return {_akar(a.name) for a in node.names}
    return set()


def impor_modul(nama_modul):
    """(impor_statis_dan_literal, impor_dinamis_tak_terbaca) lewat AST.

    Mencakup impor di dalam fungsi (impor malas) karena `ast.walk` menelusuri
    seluruh pohon. Impor dinamis dengan argumen bukan literal string dicatat
    terpisah: tidak bisa diverifikasi sehingga dianggap pelanggaran di inti.
    """
    sumber = (MESIN / f"{nama_modul}.py").read_text(encoding="utf-8")
    pohon = ast.parse(sumber, filename=f"{nama_modul}.py")
    ditemukan, tak_terbaca = set(), []
    for node in ast.walk(pohon):
        ditemukan |= _impor_node(node)
        if isinstance(node, ast.Call) and _nama_fungsi(node) in FUNGSI_IMPOR_DINAMIS:
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ditemukan.add(_akar(arg.value))
            else:
                tak_terbaca.append(f"{nama_modul}.py:{node.lineno}")
    return ditemukan, tak_terbaca


def impor_mesin(nama_modul):
    statis, _ = impor_modul(nama_modul)
    return statis & _modul_mesin()


def hitung_penutupan(titik_masuk=TITIK_MASUK):
    terlihat, antrean = set(), [titik_masuk]
    while antrean:
        modul = antrean.pop()
        if modul in terlihat:
            continue
        terlihat.add(modul)
        antrean.extend(sorted(impor_mesin(modul)))
    return frozenset(terlihat)


class BatasImporInti(unittest.TestCase):
    def test_inti_tidak_mengimpor_modul_di_luar_daftar(self):
        diizinkan = INTI_SOAL | ALLOWLIST
        pelanggaran = []
        for modul in sorted(INTI_SOAL):
            for luar in sorted(impor_mesin(modul) - diizinkan):
                pelanggaran.append(f"{modul}.py mengimpor {luar}")
        self.assertEqual(
            pelanggaran, [],
            "Inti soal mengimpor modul di luar daftar:\n  "
            + "\n  ".join(pelanggaran) + "\n" + PETUNJUK)

    def test_inti_tidak_memakai_impor_dinamis_tak_terbaca(self):
        tak_terbaca = []
        for modul in sorted(INTI_SOAL | ALLOWLIST):
            tak_terbaca += impor_modul(modul)[1]
        self.assertEqual(
            tak_terbaca, [],
            "Impor dinamis dengan argumen bukan literal string tidak bisa "
            "diverifikasi; pakai literal atau keluarkan dari inti: "
            + ", ".join(tak_terbaca))

    def test_allowlist_adalah_daun(self):
        bocor = [f"{m}.py mengimpor {x}" for m in sorted(ALLOWLIST)
                 for x in sorted(impor_mesin(m))]
        self.assertEqual(bocor, [], "Modul allowlist harus tanpa impor mesin/: "
                         + "; ".join(bocor))


class DaftarIntiSinkron(unittest.TestCase):
    def test_semua_modul_daftar_ada(self):
        hilang = sorted((INTI_SOAL | ALLOWLIST) - _modul_mesin())
        self.assertEqual(
            hilang, [],
            f"Modul di daftar tidak ada di mesin/: {hilang}. Hapus dari daftar "
            "bila modulnya sudah dipindah/dihapus.")

    def test_daftar_sama_dengan_penutupan_transitif_generator(self):
        penutupan = hitung_penutupan() - ALLOWLIST
        baru = sorted(penutupan - INTI_SOAL)
        usang = sorted(INTI_SOAL - penutupan)
        pesan = []
        if baru:
            pesan.append(
                "Modul baru kini terjangkau dari `generator` tetapi belum ada "
                "di INTI_SOAL (tambahkan baris berikut bila memang inti soal):\n"
                + "\n".join(f'    "{m}",' for m in baru))
        if usang:
            pesan.append(
                "Modul di INTI_SOAL tidak lagi terjangkau dari `generator` "
                f"(hapus dari daftar): {usang}")
        self.assertEqual(
            (baru, usang), ([], []), "\n".join(pesan) + "\n" + PETUNJUK)


if __name__ == "__main__":
    unittest.main()
