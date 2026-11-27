"""Render blok Peta Kemampuan versi 2 di halaman orang tua (F4): seksi 1-8, v1 tetap, kata terlarang, grid, cetak, CSP.

Data sintetis saja. Isi dibangun lewat `peta_laporan_snapshot.periksa_isi` agar bentuknya sama dengan yang tersimpan.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_skor  # noqa: E402
import kurikulum_katalog  # noqa: E402
import orang_tua_http  # noqa: E402
import orang_tua_pages  # noqa: E402
import pesanan_pages  # noqa: E402
import peta_browser  # noqa: E402
import peta_laporan_ortu_pages as halaman  # noqa: E402
import peta_laporan_ortu_v2 as v2  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import peta_saran_rumah as saran  # noqa: E402
import web  # noqa: E402
from orang_tua_data import DataOrangTua  # noqa: E402
from teacher_style import SKRIP_MATA_SANDI  # noqa: E402

# Grid 15 soal: 9 benar (1), 4 salah (0), 2 dilewati (2); sama dengan jumlah per materi di bawah.
GRID = [1, 1, 0, 1, 1, 2, 1, 0, 0, 1, 1, 1, 1, 2, 0]
KATA_NILAI = {1: "benar", 0: "salah", 2: "dilewati"}
CATATAN = "Catatan sintetis untuk uji laporan."
KATA_TERLARANG = (
    "kunci", "malrule", "diagnos", "kode_final", "kode_usulan", "pembahasan", "jawaban benar",
    "tel:", "wa.me", "peringkat", "persentil", "pasti", "dijamin", "menjamin", "tidak ditampilkan",
    "/sesi/", "raka",
)
SEKSI_BERURUTAN = (
    "Gambaran kemampuan", "Peta Kemampuan Matematika", "Detail penguasaan per materi", "Yang paling perlu dilatih dulu",
    "Materi yang sudah kuat", "Urutan belajar", "Cara mengerjakan", "Yang bisa dilakukan di rumah",
    "Rekomendasi pendampingan",
)


def _isi_v2(**ubah) -> dict:
    dasar = {
        "versi": 2, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 60, "kategori": "Cukup baik",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5},
                       {"materi": "Geometri datar", "benar": 2, "total": 5}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran", "Geometri datar"],
        "ringkasan_perlu": ["Pengukuran"],
        "grid": list(GRID), "dilewati": 2, "menit_total": 15, "rata_detik": 60,
    }
    return snap.periksa_isi({**dasar, **ubah})


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


def _sr_grid(html: str) -> list:
    return re.findall(r'<span class="ortu-peta-sr-st">([^<]*)</span>', html)


def test_v2_menampilkan_seksi_satu_sampai_delapan_berurutan():
    html = halaman.blok_peta(_peta(_isi_v2()))
    posisi = [html.index(judul) for judul in SEKSI_BERURUTAN]
    assert posisi == sorted(posisi)
    tampak = _tampak(html)
    assert "60 dari 100" in tampak and "Cukup baik" in tampak and "9 dari 15 soal benar" in tampak


def test_seksi_yang_datanya_belum_ada_tidak_dibuat():
    html = halaman.blok_peta(_peta(_isi_v2()))
    tampak = _tampak(html).lower()
    for judul in ("perilaku belajar", "cara berpikir", "aspek berpikir", "jenis kesalahan", "pola salah",
                  "yang sudah bagus", "desktop", "tampilan hp", "tes psikologi"):
        assert judul not in tampak, judul
    assert "<details" not in html


def test_kata_terlarang_dan_pola_mentah_tidak_tampil_di_blok_v2():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v2()))).lower()
    for kata in KATA_TERLARANG:
        assert kata not in tampak, kata
    assert "%" not in tampak and "#" not in tampak
    assert not re.search(r"benar\s*/", tampak) and not re.search(r"#\d+", tampak)
    assert str(GRID) not in tampak and "menit_total" not in tampak and "grid" not in tampak


def test_guru_tidak_disebut_pada_laporan_sistem_dan_catatan_disembunyikan():
    html = halaman.blok_peta(_peta(_isi_v2(), oleh_sistem=True))
    tampak = _tampak(html)
    assert "guru" not in tampak.lower()
    assert CATATAN not in tampak


def test_catatan_guru_tampil_hanya_pada_laporan_bukan_sistem():
    html = halaman.blok_peta(_peta(_isi_v2()))
    assert CATATAN in _tampak(html) and "Catatan dari Guru" in _tampak(html)


def test_grid_punya_teks_aksesibel_per_nomor_dan_tidak_hanya_warna():
    html = halaman.blok_peta(_peta(_isi_v2()))
    assert _sr_grid(html) == [f"Nomor {n}: {KATA_NILAI[g]}" for n, g in enumerate(GRID, start=1)]
    assert html.count('class="ortu-peta-soal-st ') == len(GRID)
    assert '<ol class="ortu-peta-grid-st">' in html


def test_waktu_none_tanpa_angka_dan_tanpa_kata_perkiraan():
    html = halaman.blok_peta(_peta(_isi_v2(menit_total=None, rata_detik=None)))
    tampak = _tampak(html).lower()
    assert "perkiraan" not in tampak and "menit" not in tampak and "detik" not in tampak
    assert "2 soal dilewati" in tampak


def test_waktu_ada_angkanya_diberi_kata_perkiraan():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v2())))
    assert "Perkiraan total waktu 15 menit" in tampak
    assert "Perkiraan rata-rata 60 detik per soal" in tampak


def test_target_berikutnya_hanya_bila_kelas_ada():
    ada = _tampak(halaman.blok_peta(_peta(_isi_v2())))
    tanpa = _tampak(halaman.blok_peta(_peta(_isi_v2(kelas=None))))
    assert "Target berikutnya: Siap materi Kelas 4" in ada
    assert "Target berikutnya" not in tanpa


def test_rekomendasi_tanpa_tautan_kelas_agar_pintu_kelas_tetap_satu():
    """Kartu lunas sudah memuat satu-satunya pintu kelas di halaman; blok laporan tidak menambah tautan ke /murid/paket."""
    html = halaman.blok_peta(_peta(_isi_v2()))
    assert "/murid/paket" not in html and "Lihat pilihan kelas" not in html


def test_kategori_tak_dikenal_tanpa_rekomendasi_tanpa_galat():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v2(kategori="Kategori lain"))))
    assert "Rekomendasi pendampingan" not in tampak
    assert "Yang bisa dilakukan di rumah" in tampak


def test_setiap_kategori_katalog_punya_kalimat_rekomendasi():
    assert set(v2.TEKS_REKOMENDASI) == set(cek_gratis_skor.KATEGORI)


def test_urutan_belajar_dan_saran_hilang_bila_tak_ada_materi_perlu_dilatih():
    isi = _isi_v2(perlu_dilatih=[], grid=[1] * 15, dilewati=0)
    tampak = _tampak(halaman.blok_peta(_peta(isi)))
    assert "Urutan belajar" not in tampak
    assert "Yang bisa dilakukan di rumah" not in tampak
    assert "Semua materi sudah baik, pertahankan." in tampak


def test_urutan_belajar_mengikuti_perlu_dilatih_dengan_kalimat_jujur():
    tampak = _tampak(halaman.blok_peta(_peta(_isi_v2())))
    assert "Mulai dari materi yang paling perlu dilatih." in tampak
    assert tampak.index("Urutan belajar") < tampak.index("Pengukuran Geometri datar", tampak.index("Urutan belajar"))


def test_v1_tetap_tanpa_penanda_v2():
    html = halaman.blok_peta(_peta(_isi_v1()))
    for penanda in ("ortu-peta-v2-st", "data-peta-cetak", "<script", "<noscript", "href=",
                    "Yang bisa dilakukan di rumah", "Target berikutnya"):
        assert penanda not in html, penanda


def test_tombol_cetak_tanpa_onclick_dan_skrip_cetak_berhash_di_dalam_blok():
    html = halaman.blok_peta(_peta(_isi_v2()))
    assert '<button type="button" class="ortu-peta-cetak-st" data-peta-cetak>' in html
    assert "onclick" not in html.lower()
    assert f"<script>{peta_browser.SKRIP_CETAK}</script>" in html


def test_tanpa_js_tombol_cetak_disembunyikan_lewat_noscript():
    html = halaman.blok_peta(_peta(_isi_v2()))
    assert "<noscript><style>.ortu-peta-cetak-baris-st{display:none}</style></noscript>" in html


def test_css_cetak_a4_dan_hanya_blok_laporan_yang_tampil():
    halaman_penuh = orang_tua_pages._dokumen("<p>tes</p>").decode("utf-8")
    assert "@page { size: A4 portrait; margin: 14mm; }" in halaman_penuh
    assert ".funnel-alur-st:has(> .ortu-peta-v2-st) > :not(.ortu-peta-v2-st) { display: none; }" in halaman_penuh


def test_csp_header_memuat_hash_skrip_cetak_hanya_bila_diminta():
    import web

    isi = ("<html><body>" + f"<script>{peta_browser.SKRIP_CETAK}</script>" + "</body></html>").encode("utf-8")
    hash_cetak = web._hash_skrip(peta_browser.SKRIP_CETAK)
    assert hash_cetak in _csp_untuk(isi, skrip_cetak=True)
    assert hash_cetak not in _csp_untuk(isi, skrip_cetak=False)


class _PenangahUji:
    """Pengganti minimal penangan HTTP: `_kirim_privat` asli dijalankan atas objek ini dan header dicatat."""

    def __init__(self):
        self.header = {}
        self.wfile = io.BytesIO()

    def send_response(self, kode, *_):
        self.kode = kode

    def send_header(self, nama, nilai):
        self.header[nama] = nilai

    def end_headers(self):
        pass

    def _kirim_privat(self, isi: bytes, kode: int = 200, **kwargs) -> None:
        import web

        web.Penangan._kirim_privat(self, isi, kode, **kwargs)


def _csp_untuk(isi: bytes, **kwargs) -> str:
    penangah = _PenangahUji()
    penangah._kirim_privat(isi, 200, **kwargs)
    return penangah.header["Content-Security-Policy"]


def _halaman_orang_tua(peta: dict) -> bytes:
    data = DataOrangTua("Anak Sintetis", {"status": "belum_mulai"}, None, pesanan_pages.STATUS_SUDAH_DIBAYAR,
                        peta=peta, nominal_bayar=49000)
    return orang_tua_pages.halaman_isi(data, False)


def _csp_lewat_rute_orang_tua(isi: bytes) -> str:
    penangah = _PenangahUji()
    orang_tua_http._kirim(penangah, isi)
    return penangah.header["Content-Security-Policy"]


def _hash_bytes(badan: bytes) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(badan).digest()).decode("ascii") + "'"


def test_rute_orang_tua_memasang_hash_setiap_skrip_inline_halaman():
    isi = _halaman_orang_tua(_peta(_isi_v2()))
    csp = _csp_lewat_rute_orang_tua(isi)
    badan_skrip = re.findall(rb"<script>(.*?)</script>", isi, flags=re.S)
    assert len(badan_skrip) == 2
    for badan in badan_skrip:
        assert _hash_bytes(badan) in csp
    assert web._hash_skrip(peta_browser.SKRIP_CETAK) in csp
    assert web._hash_skrip(SKRIP_MATA_SANDI) in csp


def test_rute_orang_tua_v1_tanpa_hash_cetak_di_csp():
    csp = _csp_lewat_rute_orang_tua(_halaman_orang_tua(_peta(_isi_v1())))
    assert web._hash_skrip(peta_browser.SKRIP_CETAK) not in csp
    assert web._hash_skrip(SKRIP_MATA_SANDI) in csp


def test_saran_maks_tiga_urut_dari_perlu_dilatih():
    hasil = saran.pilih_saran(["Pengukuran", "Berhitung", "Bilangan dasar", "Statistika"], dilewati=0)
    assert hasil == [saran.SARAN_PER_MATERI[n] for n in ("Pengukuran", "Berhitung", "Bilangan dasar")]


def test_saran_dilewati_mendapat_slot_terakhir_tanpa_melebihi_tiga():
    hasil = saran.pilih_saran(["Pengukuran", "Berhitung", "Bilangan dasar"], dilewati=2)
    assert hasil == [saran.SARAN_PER_MATERI["Pengukuran"], saran.SARAN_PER_MATERI["Berhitung"], saran.SARAN_DILEWATI]


def test_materi_tanpa_templat_dilewati_tanpa_galat_dan_tanpa_materi_tanpa_saran():
    assert saran.pilih_saran(["Label ubahan admin", "Berhitung"], dilewati=0) == [saran.SARAN_PER_MATERI["Berhitung"]]
    assert saran.pilih_saran([], dilewati=0) == []


def test_kunci_saran_adalah_label_awam_katalog():
    assert set(saran.SARAN_PER_MATERI) <= set(kurikulum_katalog.label_awam().values())


def test_daftar_teks_templat_memuat_semua_saran_dan_bebas_kata_terlarang():
    assert saran.DAFTAR_TEKS_TEMPLAT == (*saran.SARAN_PER_MATERI.values(), saran.SARAN_DILEWATI)
    for teks in saran.DAFTAR_TEKS_TEMPLAT + tuple(v2.TEKS_REKOMENDASI.values()):
        assert teks.strip() and "guru" not in teks.lower()
        assert not any(kata in teks.lower() for kata in KATA_TERLARANG), teks
