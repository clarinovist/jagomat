"""Render blok Peta Kemampuan versi 3 (F6): seksi, aturan ambang, aksesibilitas grafik, cetak, CSP, dan mutasi guard.

Data sintetis saja (tanpa nama anak). Isi dibangun lewat `peta_laporan_snapshot.periksa_isi` agar bentuknya sama dengan
yang tersimpan. Mutasi dijalankan lewat `harian_mutasi_kit.uji_mutasi` pada salinan tmp, berkas repo tidak ditulis.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import peta_browser  # noqa: E402
import peta_laporan_ortu_pages as halaman  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import peta_style_laporan_v2  # noqa: E402
import peta_style_laporan_v3 as gaya3  # noqa: E402
import peta_v3_aturan as aturan  # noqa: E402
import peta_v3_grafik as grafik  # noqa: E402
import peta_laporan_ortu_v3 as v3  # noqa: E402
from harian_mutasi_kit import uji_mutasi  # noqa: E402

TES_V3 = "test_peta_laporan_ortu_v3.py"
SALIN_TES = ("harian_mutasi_kit.py", TES_V3)
GRID_V2 = [1, 1, 0, 1, 1, 2, 1, 0, 0, 1, 1, 1, 1, 2, 0]
POLA_V3 = "BBSBB-BSSBBBB-S"  # B benar, S salah, - dilewati (sama dengan pola uji snapshot v3)
DETIK_V3 = (12, 45, 3, 30, 9, None, 5, 60, 8, 25, 40, 90, 15, None, 4)
GANTI_V3 = (1, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0)
MATERI_V3 = ("Berhitung", "Pengukuran", "Geometri datar")
CATATAN = "Catatan sintetis untuk uji laporan."
SEKSI_BERURUTAN = (
    "Peta Kemampuan", "Hasil cek kemampuan", "Skor keseluruhan", "Peta Kemampuan Matematika",
    "Detail penguasaan per materi", "Temuan utama", "Urutan belajar yang disarankan", "Perilaku belajar",
    "Cara mengerjakan", "Yang bisa dilakukan di rumah", "Rekomendasi pendampingan", "Setiap jawaban salah",
)
TIDAK_DIBUAT = ("Aspek berpikir", "Jenis kesalahan", "Pola salah", "Cara berpikir", "Yang sudah bagus")
KATA_TERLARANG = (
    "kunci", "jawaban benar", "malrule", "diagnos", "alasan", "sesi_id", "soal_id", "peringkat", "persentil",
    "pasti", "dijamin", "menjamin", "tel:", "wa.me", "/sesi/", "raka", "guru",
)
# Hash keluaran versi 1 dan 2 dari kode sebelum F6 (dihitung sekali dari masukan di `_isi_v2_lama`).
HASH_V2_PLAIN = "825b4d6d38711ff762176b9b995857a2efed7460b0c252b33dedbea1ddc8995c"
HASH_V2_SISTEM = "3327e11b6afcfd6d92dd40f538dfbccfb6324d84257ea725b88d7e7483d46cdf"
HASH_V1_PLAIN = "41f3d538d08b1c3413fa8c80c75e319315653e99bed511712e215d8fded57286"
HASH_GAYA_V2 = "c852b0583710128d1c5136e2e547ada5e472396b42cecf80ccb0af7668f3c664"


def _sidik(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


def _soal(pola=POLA_V3, detik=DETIK_V3, ganti=GANTI_V3, materi=MATERI_V3) -> list:
    butir = []
    for nomor, (simbol, d, g) in enumerate(zip(pola, detik, ganti), start=1):
        dijawab = simbol != "-"
        butir.append({"nomor": nomor, "dijawab": dijawab, "benar": int(simbol == "B") if dijawab else None,
                      "detik": d, "ganti": g, "materi": materi[(nomor - 1) % len(materi)]})
    return butir


def _isi_v3(soal=None, per_materi=None, **ubah) -> dict:
    """Isi versi 3 yang lolos `periksa_isi`; bagian turunan dihitung ulang dari butir soal."""
    soal = soal if soal is not None else _soal()
    grid = [2 if not b["dijawab"] else (1 if b["benar"] == 1 else 0) for b in soal]
    if per_materi is None:
        per_materi = [{"materi": m, "benar": sum(1 for b in soal if b["materi"] == m and b["benar"] == 1),
                       "total": sum(1 for b in soal if b["materi"] == m)} for m in MATERI_V3]
    detik = [b["detik"] for b in soal if b["detik"] is not None]
    dasar = {
        "versi": 3, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 60, "kategori": "Cukup baik",
        "jumlah_soal": len(soal), "per_materi": per_materi,
        "kuat": [m["materi"] for m in per_materi if m["total"] and m["benar"] / m["total"] >= 0.8],
        "perlu_dilatih": [m["materi"] for m in per_materi if m["benar"] < m["total"]][:3],
        "ringkasan_perlu": [m["materi"] for m in per_materi if m["benar"] < m["total"]][:1],
        "grid": grid, "dilewati": grid.count(2), "menit_total": 15, "rata_detik": 60,
        "soal": soal,
        "rata_detik_soal": sum(detik) // len(detik) if 2 * len(detik) >= len(soal) else None,
        "jumlah_cepat": sum(1 for b in soal if b["dijawab"] and b["benar"] == 0 and b["detik"] is not None
                            and b["detik"] < snap.AMBANG_CEPAT_DETIK),
    }
    return snap.periksa_isi({**dasar, **ubah})


def _isi_v2() -> dict:
    return snap.periksa_isi({
        "versi": 2, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 60, "kategori": "Cukup baik",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5},
                       {"materi": "Geometri datar", "benar": 2, "total": 5}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran", "Geometri datar"],
        "ringkasan_perlu": ["Pengukuran"],
        "grid": list(GRID_V2), "dilewati": 2, "menit_total": 15, "rata_detik": 60,
    })


def _isi_v1() -> dict:
    return snap.periksa_isi({
        "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 7}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": ["Pengukuran"],
    })


def _peta(isi: dict, **kunci) -> dict:
    return {"isi": isi, "catatan": CATATAN, "diterbitkan": "2026-11-24 15:00:00", **kunci}


def _tampak(html: str) -> str:
    """Teks yang dibaca pembaca: tanpa blok style, script, dan noscript, tanpa tag, spasi dirapikan."""
    tanpa_blok = re.sub(r"<(style|script|noscript)\b.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", tanpa_blok)).strip()


def _sr(html: str) -> list:
    daftar = re.findall(r'<ul class="ortu-peta-v3-sr-st">(.*?)</ul>', html, flags=re.S)
    return re.findall(r"<li>([^<]*)</li>", daftar[0]) if daftar else []


def _tanpa_svg(html: str) -> str:
    return re.sub(r"<svg.*?</svg>", "", html, flags=re.S)


# --- seksi dan dispatch -----------------------------------------------------------------------

def test_v3_memuat_semua_seksi_berurutan():
    html = halaman.blok_peta(_peta(_isi_v3()))
    posisi = [html.index(judul) for judul in SEKSI_BERURUTAN]
    assert posisi == sorted(posisi)
    tampak = _tampak(html)
    assert "9 dari 15 soal benar" in tampak
    assert "Anak sudah cukup baik di Berhitung." in tampak


def test_v3_tidak_memuat_bagian_yang_datanya_belum_ada():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3()))).lower()
    for judul in TIDAK_DIBUAT:
        assert judul.lower() not in tampak, judul
    assert "<details" not in halaman.blok_peta(_peta(_isi_v3()))


def test_dispatch_v3_lewat_renderer_baru_bukan_v2():
    html = halaman.blok_peta(_peta(_isi_v3()))
    assert "ortu-peta-v3-st" in html and "ortu-peta-v2-st" not in html


def test_v2_dan_v1_tetap_byte_identik_dengan_sebelum_f6():
    assert _sidik(halaman.blok_peta(_peta(_isi_v2()))) == HASH_V2_PLAIN
    assert _sidik(halaman.blok_peta(_peta(_isi_v2(), oleh_sistem=True))) == HASH_V2_SISTEM
    assert _sidik(halaman.blok_peta(_peta(_isi_v1()))) == HASH_V1_PLAIN
    assert _sidik(peta_style_laporan_v2.GAYA_PETA_V2) == HASH_GAYA_V2


def test_catatan_guru_tetap_tampil_pada_laporan_bukan_sistem_dan_hilang_saat_sistem():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3())))
    assert CATATAN in tampak and "Catatan dari Guru" in tampak
    tampak_sistem = _tampak(halaman.blok_peta(_peta(_isi_v3(), oleh_sistem=True)))
    assert CATATAN not in tampak_sistem and "Catatan dari Guru" not in tampak_sistem


# --- privasi dan escape -----------------------------------------------------------------------

def test_kata_terlarang_dan_nama_anak_tidak_tampil():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3(), oleh_sistem=True))).lower()
    for kata in KATA_TERLARANG:
        assert kata not in tampak, kata
    assert "anak" in tampak and "none" not in tampak


def test_materi_berbahaya_di_escape_di_semua_tempat():
    nama = "<img src=x onerror=alert(1)>"
    soal = _soal(materi=(nama,) + MATERI_V3[1:])
    per_materi = [{"materi": nama, "benar": 1, "total": 5}, {"materi": "Pengukuran", "benar": 3, "total": 5},
                  {"materi": "Berhitung", "benar": 5, "total": 5}]
    html = halaman.blok_peta(_peta(_isi_v3(soal=soal, per_materi=per_materi)))
    assert "<img src=x" not in html
    assert html.count("&lt;img src=x onerror=alert(1)&gt;") >= 4


def test_tidak_ada_style_inline_hex_atau_script_di_luar_skrip_cetak():
    html = halaman.blok_peta(_peta(_isi_v3()))
    assert ' style="' not in html
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", _tanpa_svg(html))
    assert html.count("<script>") == 1 and f"<script>{peta_browser.SKRIP_CETAK}</script>" in html


def test_kelas_css_yang_dipakai_terdefinisi_di_gaya_v3():
    html = halaman.blok_peta(_peta(_isi_v3()))
    for kelas in set(re.findall(r'class="([^"]+)"', html)) - {""}:
        for nama in kelas.split():
            if nama.startswith("ortu-peta-v3-") and not nama.startswith("ortu-peta-v3-h-"):
                assert f".{nama}" in gaya3.GAYA_PETA_V3, nama


def test_css_v3_tanpa_hex_rgba_important_dan_dengan_cetak_a4():
    sumber = Path(gaya3.__file__).read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
    gaya = gaya3.GAYA_PETA_V3
    assert "!important" not in gaya
    assert "@page { size: A4 portrait; margin: 14mm; }" in gaya
    assert "break-before: page" in gaya
    assert ".funnel-alur-st:has(> .ortu-peta-v3-st) > :not(.ortu-peta-v3-st) { display: none; }" in gaya


def test_tombol_cetak_tersembunyi_tanpa_js_dan_tanpa_onclick():
    html = halaman.blok_peta(_peta(_isi_v3()))
    assert '<button type="button" class="ortu-peta-v3-cetak-st" data-peta-cetak>' in html
    assert "onclick" not in html.lower()
    assert ("<noscript><style>.ortu-peta-v3-cetak-baris-st{display:none}</style></noscript>") in html


# --- aturan status dan ambang -----------------------------------------------------------------

@pytest.mark.parametrize("benar,total,status", [
    (5, 5, aturan.STATUS_DIKUASAI),
    (4, 5, aturan.STATUS_DIKUASAI),
    (3, 5, aturan.STATUS_PERLU),
    (3, 4, aturan.STATUS_PERLU),
    (2, 4, aturan.STATUS_BELUM),
    (1, 2, aturan.STATUS_BELUM),
    (0, 4, aturan.STATUS_BELUM),
])
def test_status_materi_batas_ambang(benar, total, status):
    assert aturan.status_materi(benar, total) == status


def test_rata_detik_soal_kosong_jatuh_ke_rata_detik():
    soal = _soal(pola="BBSBB-BSSBBBB-S", detik=(12, 45, 3, None, None, None, None, None, None, None, None, None,
                                                 None, None, None))
    html = halaman.blok_peta(_peta(_isi_v3(soal=soal, rata_detik=60)))
    tampak = _tampak(html)
    assert "60 detik Rata-rata per soal" in tampak
    assert "Rata-rata 60 detik" in tampak


def test_semua_ganti_nol_menjadi_jarang_dan_tanpa_jawaban_diganti():
    soal = _soal(ganti=(0,) * 15)
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3(soal=soal))))
    assert "Jarang" in tampak and "Tidak ada jawaban yang diganti." in tampak


def test_semua_soal_dilewati_di_renderer_tidak_galat_dan_tanpa_teks_terlarang():
    isi = dict(_isi_v3())
    soal = [{**b, "dijawab": False, "benar": None, "detik": None, "ganti": 0} for b in isi["soal"]]
    isi.update(soal=soal, grid=[2] * 15, dilewati=15, rata_detik_soal=None, jumlah_cepat=0,
               per_materi=[{"materi": m, "benar": 0, "total": 5} for m in MATERI_V3])
    html = v3.blok_peta_v3({"isi": isi, "catatan": "", "diterbitkan": "2026-11-24 15:00:00"})
    tampak = _tampak(html)
    assert "Mencoba semua" not in tampak and "15 soal dilewati" in tampak
    assert "tanpa catatan waktu" in html


def test_ambang_perilaku_batas_bawah_dan_atas():
    assert aturan.status_ketekunan(0) == ("Kuat", aturan.NADA_BAIK)
    assert aturan.status_ketekunan(1)[0] == "Perlu perhatian"
    assert aturan.status_fokus_akhir(3, 5)[0] == "Stabil"
    assert aturan.status_fokus_akhir(2, 5)[0] == "Perlu perhatian"
    assert aturan.status_fokus_akhir(0, 1)[0] == "Perlu perhatian"
    assert aturan.status_fokus_akhir(1, 1)[0] == "Stabil"
    assert aturan.status_fokus_akhir(2, 2)[0] == "Stabil"
    assert aturan.status_saat_sulit(0)[0] == "Tenang"
    assert aturan.status_saat_sulit(1)[0] == "Perlu perhatian"
    assert aturan.status_saat_sulit(2)[0] == "Cenderung menebak"
    assert aturan.status_periksa_ulang(2)[0] == "Jarang"
    assert aturan.status_periksa_ulang(3)[0] == "Sering memeriksa"


def test_soal_cepat_di_materi_lemah_dan_klausa_semua_atau_sebagian():
    soal = _soal()
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3(soal=soal))))
    assert "3 soal salah dijawab di bawah 10 detik, semuanya di materi yang belum dikuasai." in tampak


def test_kelas_none_tanpa_target_dan_tanpa_kelas_di_kepala():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3(kelas=None))))
    assert "Target berikutnya" not in tampak and "Kelas " not in tampak
    assert "Hasil cek kemampuan · 18 November 2026" in tampak


def test_urutan_belajar_dihilangkan_bila_semua_materi_dikuasai():
    per_materi = [{"materi": m, "benar": 5, "total": 5} for m in MATERI_V3]
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v3(per_materi=per_materi))))
    assert "Urutan belajar yang disarankan" not in tampak


# --- grafik waktu -----------------------------------------------------------------------------

def test_grafik_waktu_punya_teks_aksesibel_per_nomor():
    html = halaman.blok_peta(_peta(_isi_v3()))
    assert _sr(html) == [
        "Nomor 1: benar, 12 detik.", "Nomor 2: benar, 45 detik.", "Nomor 3: salah, 3 detik, dijawab di bawah 10 detik.",
        "Nomor 4: benar, 30 detik.", "Nomor 5: benar, 9 detik.", "Nomor 6: dilewati, tanpa catatan waktu.",
        "Nomor 7: benar, 5 detik.", "Nomor 8: salah, 60 detik.", "Nomor 9: salah, 8 detik, dijawab di bawah 10 detik.",
        "Nomor 10: benar, 25 detik.", "Nomor 11: benar, 40 detik.", "Nomor 12: benar, 90 detik.",
        "Nomor 13: benar, 15 detik.", "Nomor 14: dilewati, tanpa catatan waktu.",
        "Nomor 15: salah, 4 detik, dijawab di bawah 10 detik.",
    ]
    assert 'role="img" aria-label="Waktu per soal.' in html
    assert "Soal paling lama: nomor 12, 90 detik." in html


def test_tanpa_detik_sebagian_digambar_abu_dan_disebut_di_daftar():
    soal = _soal(detik=(None, None, 3) + DETIK_V3[3:])
    html = halaman.blok_peta(_peta(_isi_v3(soal=soal)))
    assert "ortu-peta-v3-batang-abu-st" in html
    assert "Nomor 1: benar, tanpa catatan waktu." in _sr(html)


def test_grafik_donat_skor_tanpa_style_dan_angka_di_tengah():
    donat = grafik.donat(25)
    assert "stroke-dasharray=" in donat and ' style="' not in donat
    assert "<b>25</b>" in donat and "/100" in donat


def test_enam_belas_soal_tampil_semua_nomor_di_grafik():
    pola = "BBSB-" * 3 + "B"  # 16 soal, tanpa batas dua puluh
    detik = tuple(None if simbol == "-" else 10 for simbol in pola)
    soal = _soal(pola=pola, detik=detik, ganti=(0,) * 16)
    html = halaman.blok_peta(_peta(_isi_v3(soal=soal, menit_total=20)))
    assert len(_sr(html)) == 16 and _sr(html)[-1].startswith("Nomor 16:")


# --- mutasi guard ------------------------------------------------------------------------------

def test_mutasi_escape_materi_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_v3_materi.py",
               [('<span class="ortu-peta-v3-teks-st"><b>{e(materi["materi"])}</b>',
                 '<span class="ortu-peta-v3-teks-st"><b>{materi["materi"]}</b>')],
               TES_V3, "test_materi_berbahaya_di_escape_di_semua_tempat", SALIN_TES)


def test_mutasi_ambang_dikuasai_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_v3_aturan.py",
               [("    if rasio >= skor.AMBANG_KUAT:", "    if rasio > skor.AMBANG_KUAT:")],
               TES_V3, "test_status_materi_batas_ambang", SALIN_TES)


def test_mutasi_kata_terlarang_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_v3_halaman2.py",
               [('COPY_RUMAH = "Yang bisa dilakukan di rumah"', 'COPY_RUMAH = "Jenis kesalahan"')],
               TES_V3, "test_v3_tidak_memuat_bagian_yang_datanya_belum_ada", SALIN_TES)


def test_mutasi_teks_aksesibel_grafik_tertangkap(tmp_path):
    uji_mutasi(tmp_path, "peta_v3_grafik.py",
               [("    return svg + _nomor_baris(soal) + _legenda(soal, rata) + _sr_daftar(soal)",
                 "    return svg + _nomor_baris(soal) + _legenda(soal, rata)")],
               TES_V3, "test_grafik_waktu_punya_teks_aksesibel_per_nomor", SALIN_TES)
