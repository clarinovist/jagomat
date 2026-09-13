"""Rute aset brand (/aset/<nama>) + tag kepala favicon/meta.

Palang yang dijaga:
1. Publik — favicon dibutuhkan sebelum login, jadi 200 tanpa kredensial.
2. Allow-list, bukan path gabung: traversal `../` mustahil.
3. MIME benar per ekstensi; cache panjang & immutable.
4. Tidak menyentuh basis data sama sekali.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand  # noqa: E402
import database  # noqa: E402
import design_tokens as T  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    # Pendaftaran terbuka membutuhkan penandatangan admin, sebagaimana startup.
    import auth
    auth.tambah_akun("pengelola-brand", "sandi-brand-sintetis-123", "admin")
    with s.buka() as kon:
        # pemilik distempel eksplisit — palang kepemilikan menolak id yang
        # bukan milik guru dengan 404, dan itu bukan yang sedang diuji.
        sid = database.tambah_siswa(kon, "Putri", pemilik="guru")
        s.sesi_id = database.buat_sesi(kon, sid, seed=7)
        # Akun murid "feby" harus punya siswa dengan nama yang sama, kalau
        # tidak /murid menjatuhkan ke halaman "Belum terhubung" dan test
        # brand mengukur halaman yang salah.
        sid_feby = database.tambah_siswa(kon, "feby", pemilik="guru")
        database.buat_sesi(kon, sid_feby, seed=11)
    yield s
    s.berhenti()


# ───────────────────────── berkas aset ada ─────────────────────────

def test_folder_aset_lengkap():
    """Allow-list dan isi folder harus sinkron: nama yang diizinkan rute
    benar-benar ada sebagai berkas, dan tidak ada berkas liar di luar
    allow-list yang diam-diam ikut ke image."""
    folder = ROOT / "aset"
    assert folder.is_dir(), "mesin/aset/ belum ada"
    di_disk = {p.name for p in folder.iterdir() if p.is_file()}
    assert set(brand.ASET) == di_disk, (
        f"allow-list vs disk beda: hanya-allow={set(brand.ASET) - di_disk}, "
        f"hanya-disk={di_disk - set(brand.ASET)}"
    )


def test_aset_wajib_ada_semua():
    wajib = (
        "mark-sederhana.svg",
        "mark-penuh.svg",
        "mark-tinta.svg",
        "lockup-horizontal.svg",
        "lockup-cetak.svg",
        "lockup-hero.svg",
        "favicon.svg",
        "favicon.ico",
        "apple-touch-180.png",
        "pwa-192.png",
        "pwa-512.png",
        "og-image.png",
    )
    for nama in wajib:
        assert nama in brand.ASET, f"{nama} tidak ada di allow-list"
        assert (ROOT / "aset" / nama).is_file(), f"{nama} tidak ada di disk"


# ───────────────────────── rute publik ─────────────────────────

def test_favicon_publik_tanpa_kredensial(server):
    """Favicon dibutuhkan browser SEBELUM login — kalau kena palang guru,
    tab menampilkan ikon kosong di halaman landing dan masuk."""
    kode, isi, hdr = server.minta("/aset/favicon.ico", biner=True)
    assert kode == 200
    assert isi == (ROOT / "aset" / "favicon.ico").read_bytes()
    assert hdr["Content-Type"] == "image/x-icon"
    assert "immutable" in hdr["Cache-Control"]


def test_semua_aset_terlayani_dan_mime_benar(server):
    harapan = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".json": "application/json",
    }
    for nama in brand.ASET:
        kode, isi, hdr = server.minta(f"/aset/{nama}", biner=True)
        assert kode == 200, f"{nama} -> {kode}"
        ext = Path(nama).suffix
        assert hdr["Content-Type"].startswith(harapan[ext]), f"{nama}: {hdr}"
        assert isi, f"{nama} kosong"


def test_traversal_ditolak(server):
    """Allow-list, bukan path gabung. Semua bentuk traversal -> 404, dan
    yang penting: TIDAK ada isi berkas sistem yang terkirim."""
    jahat = (
        "/aset/../../etc/passwd",
        "/aset/..%2f..%2fetc%2fpasswd",
        "/aset/web.py",
        "/aset/../design_tokens.py",
        "/aset/latihan.db",
        "/aset/",
    )
    for jalur in jahat:
        kode, isi, _ = server.minta(jalur, biner=True)
        assert kode == 404, f"{jalur} -> {kode} (harus 404)"
        assert b"root:" not in isi and b"NAMA_PRODUK" not in isi, (
            f"{jalur} membocorkan isi berkas"
        )


def test_manifest_pwa_dari_tokens(server):
    """manifest.json di-generate, bukan berkas statis: nama & warna harus
    ikut design_tokens supaya brand tidak punya dua sumber kebenaran."""
    kode, isi, hdr = server.minta("/aset/manifest.json")
    assert kode == 200
    assert hdr["Content-Type"].startswith("application/json")
    data = json.loads(isi)
    assert data["name"] == T.NAMA_PRODUK
    assert data["short_name"] == T.NAMA_PRODUK
    assert data["display"] == "standalone"
    assert data["theme_color"] == T.AKSEN_MURID_UTAMA
    src = [i["src"] for i in data["icons"]]
    assert "/aset/pwa-192.png" in src and "/aset/pwa-512.png" in src


def test_aset_tidak_menyentuh_basis_data(server, monkeypatch):
    """Rute publik ini hanya melayani berkas brand. Kalau ia membuka DB,
    permukaan publik tanpa palang jadi bersentuhan dengan data anak."""
    import database as db_mod

    def meledak(*a, **k):
        raise AssertionError("rute /aset tidak boleh membuka basis data")

    monkeypatch.setattr(db_mod, "buka", meledak)
    assert server.minta("/aset/favicon.svg", biner=True)[0] == 200


def test_aset_tetap_publik_untuk_murid_dan_guru(server):
    from http_test_kit import SANDI_MURID

    for kred in (None, ("guru", SANDI_GURU), ("feby", SANDI_MURID)):
        kode, _, _ = server.minta("/aset/mark-sederhana.svg", auth=kred, biner=True)
        assert kode == 200, f"{kred} -> {kode}"


def test_dockerfile_menyalin_folder_aset():
    """COPY *.py adalah wildcard .py saja — berkas non-.py tidak ikut.
    Tanpa baris COPY aset/, favicon 404 di produksi meski hijau di lokal
    (pola insiden 25 Agustus 2026, kali ini untuk berkas biner)."""
    isi = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "aset/" in isi, "Dockerfile tidak menyalin folder aset/"


# ───────────────────────── favicon di SEMUA halaman ─────────────────────────

# Halaman yang dilayani lewat HTTP. Guard ini menutup celah "template baru
# lahir tanpa favicon": sebelumnya tidak SATU pun halaman punya favicon.
JALUR_PUBLIK = ("/", "/masuk", "/daftar", "/kebijakan-privasi", "/lupa-sandi")
JALUR_GURU = ("/akun",)


def _jalur_guru_berdata(sesi_id: int) -> tuple[str, ...]:
    """Halaman guru yang butuh id — sengaja ikut diuji: justru di sinilah
    template baru biasanya lahir (halaman sesi, cetak, laporan)."""
    return (
        f"/sesi/{sesi_id}",
        f"/sesi/{sesi_id}/cetak",
        f"/sesi/{sesi_id}/lampiran",
        f"/laporan/{sesi_id}",
    )


def test_semua_halaman_publik_punya_favicon(server):
    for jalur in JALUR_PUBLIK:
        kode, isi, _ = server.minta(jalur)
        assert kode == 200, f"{jalur} -> {kode}"
        assert 'rel="icon"' in isi, f"{jalur} tanpa favicon"
        assert 'rel="manifest"' in isi, f"{jalur} tanpa manifest"
        assert 'name="theme-color"' in isi, f"{jalur} tanpa theme-color"


def test_semua_halaman_guru_punya_favicon(server):
    for jalur in JALUR_GURU + _jalur_guru_berdata(server.sesi_id):
        kode, isi, _ = server.minta(jalur, auth=("guru", SANDI_GURU))
        assert kode == 200, f"{jalur} -> {kode}"
        assert 'rel="icon"' in isi, f"{jalur} tanpa favicon"


def test_halaman_murid_punya_favicon(server):
    from http_test_kit import SANDI_MURID

    kode, isi, _ = server.minta("/murid", auth=("feby", SANDI_MURID))
    assert kode == 200
    assert 'rel="icon"' in isi, "halaman murid tanpa favicon"


def test_lembar_cetak_punya_favicon_tanpa_og():
    """Kertas A4 tidak di-share ke WhatsApp — og:* di sana hanya sampah."""
    import render
    from generator import buat_lembar

    lembar = buat_lembar(seed=3, jumlah_soal=2)
    for fn in (render.lembar_soal, render.lembar_penilaian):
        halaman = fn(list(lembar.soal), nama="Putri", tanggal="1 Jan")
        assert 'rel="icon"' in halaman, f"{fn.__name__} tanpa favicon"
        assert "og:image" not in halaman, f"{fn.__name__} tidak perlu og:*"


def test_landing_punya_meta_share_absolut(server):
    """Crawler WhatsApp/Facebook menolak path relatif — og:image & og:url
    wajib absolut. Satu konstanta brand.URL_SITUS supaya pindah domain
    nanti = ubah satu baris."""
    kode, isi, _ = server.minta("/")
    assert kode == 200
    assert f'content="{brand.URL_SITUS}/aset/og-image.png"' in isi
    assert f'property="og:url" content="{brand.URL_SITUS}' in isi
    assert 'name="twitter:card" content="summary_large_image"' in isi
    assert f'property="og:title" content="' in isi
    assert brand.URL_SITUS.startswith("https://")


def test_tag_kepala_dipakai_bukan_disalin():
    """Blok favicon harus datang dari brand.tag_kepala(), bukan disalin
    per template — kalau disalin, template ke-15 lahir tanpa favicon dan
    tidak ada yang sadar."""
    for nama in (
        "landing.py",
        "web.py",
        "teacher_pages.py",
        "student_pages.py",
        "attachments.py",
        "render.py",
    ):
        sumber = (ROOT / nama).read_text(encoding="utf-8")
        assert "tag_kepala" in sumber, f"{nama} tidak memakai brand.tag_kepala()"
        assert 'rel="icon"' not in sumber, (
            f"{nama} menyalin blok favicon — pakai brand.tag_kepala()"
        )


MODUL_HALAMAN = (
    "landing.py",
    "web.py",
    "teacher_pages.py",
    "student_pages.py",
    "attachments.py",
    "render.py",
)


def test_setiap_head_memanggil_tag_kepala():
    """Guard STRUKTURAL, bukan lewat HTTP.

    Test lewat HTTP hanya menyentuh halaman yang punya rute aktif — halaman
    legacy dan cabang jarang lolos begitu saja. Terbukti: menghapus satu
    sisipan di student_pages.py (halaman kerja legacy) tidak membuat satu
    pun test HTTP merah. Guard ini menghitung <head> di sumber, jadi
    template mana pun yang lahir tanpa favicon langsung ketahuan.
    """
    kurang: list[str] = []
    for nama in MODUL_HALAMAN:
        sumber = (ROOT / nama).read_text(encoding="utf-8")
        n_head = sumber.count("<head>")
        n_tag = sumber.count("brand.tag_kepala(")
        if n_head != n_tag:
            kurang.append(f"{nama}: {n_head} <head> tapi {n_tag} tag_kepala()")
    assert not kurang, "head tanpa favicon:\n" + "\n".join(kurang)


# ───────────────────── satu lambang, bukan empat ─────────────────────

# Audit 3 Sep: EMPAT lambang berbeda dipakai sebagai logo — 'school' (topi
# wisuda), 'pets' (jejak kaki), SVG owl icons.py, dan teks polos tanpa ikon.
# Anak melihat jejak kaki, orang tua melihat topi wisuda.
GLYPH_LOGO_LAMA = (">school<", ">pets<")


def test_tidak_ada_glyph_logo_lama():
    """Glyph Material Symbols tidak boleh lagi dipakai SEBAGAI LOGO.

    Semua halaman aktif memakai brand; ikon renderer lama sudah dilepas.
    """
    tersangka: list[str] = []
    for nama in MODUL_HALAMAN:
        sumber = (ROOT / nama).read_text(encoding="utf-8")
        for ln_no, ln in enumerate(sumber.splitlines(), 1):
            if any(g in ln for g in GLYPH_LOGO_LAMA):
                tersangka.append(f"{nama}:{ln_no}: {ln.strip()}")
    assert not tersangka, (
        "glyph logo lama masih dipakai — pakai brand.mark():\n"
        + "\n".join(tersangka)
    )


def test_token_ukuran_logo_ada():
    """Ukuran logo lewat token, bukan angka acak per CSS (audit menemukan
    20,8px vs 21,6px untuk ikon brand yang sama)."""
    for nama in ("LOGO_TOPBAR", "LOGO_BADGE", "LOGO_HERO", "WARNA_WORDMARK"):
        assert getattr(T, nama, None), f"token {nama} belum ada"


def test_warna_wordmark_satu_nilai():
    """Audit: wordmark dirender #0FA3A3 di satu tempat dan #0a7d7d di
    tempat lain — nama produk berganti rona antar halaman.

    Dua jebakan yang sudah kena saat menulis guard ini:
    1. Assert "token ada di CSS" TIDAK cukup — nilainya sama dengan
       AKSEN_MURID_UTAMA yang muncul di puluhan aturan lain, jadi test
       tetap hijau meski wordmark di-hardcode kembali.
    2. Memeriksa CSS yang sudah dirender juga sia-sia: di sana token SUDAH
       jadi hex. Yang harus diperiksa adalah SUMBER stylesheet.
    """
    import re

    from style_stitch import gaya_stitch

    assert T.WARNA_WORDMARK in gaya_stitch()

    tersangka: list[str] = []
    for nama in ("style_stitch.py", "teacher_style.py"):
        sumber = (ROOT / nama).read_text(encoding="utf-8")
        for blok in re.finditer(r"([^{}\n]*)\{\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\}", sumber):
            selektor, isi = blok.group(1), blok.group(2)
            if "brand" not in selektor and "wordmark" not in selektor:
                continue
            for hexa in re.findall(r"#[0-9a-fA-F]{3,8}\b", isi):
                tersangka.append(f"{nama}: {selektor.strip()} -> {hexa}")
    assert not tersangka, (
        "hex hardcoded di aturan brand — pakai T.WARNA_WORDMARK:\n"
        + "\n".join(tersangka)
    )


def test_mark_dipakai_di_semua_permukaan_brand(server):
    """Landing, masuk, dashboard guru, dan halaman anak memakai mark yang
    SAMA — satu lambang, bukan empat."""
    from http_test_kit import SANDI_MURID

    permukaan = (
        ("/", None),
        ("/masuk", None),
        ("/daftar", None),
        ("/", ("guru", SANDI_GURU)),
        ("/murid", ("feby", SANDI_MURID)),
    )
    for jalur, kred in permukaan:
        kode, isi, _ = server.minta(jalur, auth=kred)
        assert kode == 200, f"{jalur} -> {kode}"
        assert "/aset/mark-" in isi, f"{jalur} tanpa mark brand"


def test_topbar_guru_legacy_punya_mark():
    """Topbar guru non-Stitch dulu teks polos tanpa ikon sama sekali —
    lambang keempat dari audit."""
    import teacher_pages

    bar = teacher_pages._topbar("guru", "guru")
    assert "/aset/mark-" in bar, "topbar legacy tanpa mark"
    assert T.NAMA_PRODUK in bar


# ───────────────────────── judul halaman seragam ─────────────────────────

def test_judul_helper_pola_tunggal():
    """Satu pola: "<Halaman> · Jagomat". Landing cukup nama produk saja."""
    assert brand.judul("Akun") == f"Akun · {T.NAMA_PRODUK}"
    assert brand.judul("") == T.NAMA_PRODUK
    assert brand.judul(T.NAMA_PRODUK) == T.NAMA_PRODUK
    # pemisah lama (— dan ·) dinormalisasi, bukan ditumpuk
    assert brand.judul(f"Daftar — {T.NAMA_PRODUK}") == f"Daftar · {T.NAMA_PRODUK}"
    assert brand.judul(f"Sesiku · {T.NAMA_PRODUK}") == f"Sesiku · {T.NAMA_PRODUK}"
    assert brand.judul("Sesi #1 — Cetak") == f"Sesi #1 — Cetak · {T.NAMA_PRODUK}"


def test_semua_judul_halaman_menyebut_brand(server):
    """Audit 3 Sep: 6 halaman tanpa nama brand sama sekali di tab browser
    (Akun, Laporan Putri, Panel Pengelola, Sesi #1 — Cetak, Sesi #1 —
    Lampiran, Hapus sesi #3?), dan pemisah campur — vs ·."""
    import re

    from http_test_kit import SANDI_MURID

    permukaan = [(j, None) for j in JALUR_PUBLIK]
    permukaan += [(j, ("guru", SANDI_GURU)) for j in JALUR_GURU]
    permukaan += [
        (j, ("guru", SANDI_GURU)) for j in _jalur_guru_berdata(server.sesi_id)
    ]
    permukaan += [("/murid", ("feby", SANDI_MURID))]

    for jalur, kred in permukaan:
        kode, isi, _ = server.minta(jalur, auth=kred)
        assert kode == 200, f"{jalur} -> {kode}"
        m = re.search(r"<title>(.*?)</title>", isi, re.S)
        assert m, f"{jalur} tanpa <title>"
        judul = m.group(1)
        assert T.NAMA_PRODUK in judul, f"{jalur}: judul '{judul}' tanpa brand"
        if judul.strip() != T.NAMA_PRODUK:
            assert f"· {T.NAMA_PRODUK}" in judul, (
                f"{jalur}: '{judul}' tidak memakai pemisah tunggal '·'"
            )


def test_judul_lembar_cetak_menyebut_brand():
    import render
    from generator import buat_lembar

    lembar = buat_lembar(seed=5, jumlah_soal=2)
    for fn in (render.lembar_soal, render.lembar_penilaian):
        halaman = fn(list(lembar.soal), nama="Putri", tanggal="1 Jan")
        judul = halaman.split("<title>")[1].split("</title>")[0]
        assert f"· {T.NAMA_PRODUK}" in judul, f"{fn.__name__}: '{judul}'"


# ───────────────────────── maskot ayam jago ─────────────────────────

@pytest.mark.parametrize("versi", ("v2", "v3"))
def test_maskot_aset_ada_dan_transparan(versi):
    """Maskot wajib PNG beralpha. Aset asalnya latar putih solid
    (hasAlpha: no) — kalau yang itu yang terpasang, anak melihat kotak
    putih di halaman cream."""
    from struct import unpack

    for pose in brand.POSE_MASKOT:
        for px in (240, 96):
            nama = f"maskot-{pose}-{versi}-{px}.png"
            assert nama in brand.ASET, f"{nama} tidak di allow-list"
            p = ROOT / "aset" / nama
            assert p.is_file(), f"{nama} tidak ada di disk"
            data = p.read_bytes()
            assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{nama} bukan PNG"
            # IHDR: lebar, tinggi, bit depth, color type
            lebar, tinggi = unpack(">II", data[16:24])
            jenis_warna = data[25]
            assert max(lebar, tinggi) == px, f"{nama}: {lebar}x{tinggi} != {px}"
            # 3 = palette (alpha lewat tRNS), 6 = RGBA
            assert jenis_warna in (3, 6), f"{nama}: color type {jenis_warna}"
            if jenis_warna == 3:
                assert b"tRNS" in data, f"{nama}: palette tanpa tRNS = tak transparan"


def _piksel_maskot(pose, px, versi="v3"):
    """Dekode PNG palet stdlib untuk menguji warna dan alpha nyata."""
    import struct
    import zlib

    data = (ROOT / "aset" / f"maskot-{pose}-{versi}-{px}.png").read_bytes()
    assert struct.unpack(">II", data[16:24]) == (px, px)
    assert data[24:26] == bytes((8, 3)), "crop memakai palet 8-bit"
    offset, kompresi, alpha, palet = 8, bytearray(), b"", []
    while offset < len(data):
        panjang = struct.unpack(">I", data[offset:offset+4])[0]
        jenis = data[offset+4:offset+8]
        isi = data[offset+8:offset+8+panjang]
        crc = struct.unpack(">I", data[offset+8+panjang:offset+12+panjang])[0]
        assert zlib.crc32(jenis + isi) == crc
        if jenis == b"IDAT":
            kompresi.extend(isi)
        elif jenis == b"tRNS":
            alpha = isi
        elif jenis == b"PLTE":
            palet = [tuple(isi[i:i+3]) for i in range(0, len(isi), 3)]
        offset += panjang + 12
    mentah = zlib.decompress(kompresi)
    assert len(mentah) == (px + 1) * px
    baris_sebelum = [0] * px
    piksel = []
    for y in range(px):
        awal = y * (px + 1)
        filter_png = mentah[awal]
        assert filter_png in (0, 1, 2), "filter crop harus None, Sub, atau Up"
        baris = []
        for x, nilai in enumerate(mentah[awal+1:awal+1+px]):
            prediksi = (baris[x-1] if x else 0) if filter_png == 1 else (
                baris_sebelum[x] if filter_png == 2 else 0
            )
            baris.append((nilai + prediksi) % 256)
        piksel.append([palet[i] + (alpha[i],) for i in baris])
        baris_sebelum = baris
    return piksel


@pytest.mark.parametrize("versi", ("v2", "v3"))
@pytest.mark.parametrize("pose", brand.POSE_MASKOT)
@pytest.mark.parametrize("px", (96, 240))
def test_maskot_alpha_nyata_dan_margin_utuh(pose, px, versi):
    """Alpha di header saja tidak membuktikan latar transparan."""
    piksel_alpha = [[w[3] for w in baris] for baris in _piksel_maskot(pose, px, versi)]
    # Seluruh pinggir kosong: tubuh/jengger/kaki tidak menabrak batas crop.
    assert not any(piksel_alpha[0] + piksel_alpha[-1])
    assert all(baris[0] == baris[-1] == 0 for baris in piksel_alpha)
    datar = [a for baris in piksel_alpha for a in baris]
    assert datar.count(0) > px * px * 0.2
    assert datar.count(255) > px * px * 0.2, "karakter tidak boleh ikut hilang"
    assert any(0 < a < 255 for a in datar), "tepi harus punya antialias"


@pytest.mark.parametrize("pose,x,y,warna", (
    ("menyapa", 160, 160, (254, 245, 230)),
    ("menunjuk", 140, 184, (254, 245, 231)),
    ("berpikir", 148, 184, (254, 245, 232)),
    ("membaca", 144, 112, (254, 246, 232)),
    ("menulis", 148, 112, (254, 245, 232)),
    ("merayakan", 156, 188, (254, 246, 232)),
))
def test_maskot_perut_mulus_tanpa_bintik(pose, x, y, warna):
    """Sampel bidang krem 10×10 dari crop sebelum kuantisasi, bukan rerata PNG rusak.

    Periksa setiap piksel, karena rerata bisa menyembunyikan bintik kemerahan.
    Toleransi 12/255 menampung gradasi asli tanpa membolehkan bintik versi lama.
    """
    gambar = _piksel_maskot(pose, 240)
    for baris in gambar[y:y+10]:
        for piksel in baris[x:x+10]:
            assert piksel[3] == 255
            assert max(abs(piksel[d] - warna[d]) for d in range(3)) <= 12, (
                f"{pose}: bintik warna pada bidang krem: {piksel}"
            )


@pytest.mark.parametrize("pose", brand.POSE_MASKOT)
@pytest.mark.parametrize("px", (96, 240))
def test_ekspor_baru_tidak_mengubah_siluet(pose, px):
    lama = _piksel_maskot(pose, px, "v2")
    baru = _piksel_maskot(pose, px)
    assert [[w[3] > 0 for w in b] for b in lama] == [
        [w[3] > 0 for w in b] for b in baru
    ]


def test_maskot_ringan():
    """Enam pose tetap ringan: batas per berkas tidak naik dari versi lama."""
    total = 0
    for pose in brand.POSE_MASKOT:
        for px in (240, 96):
            n = (ROOT / "aset" / f"maskot-{pose}-v3-{px}.png").stat().st_size
            batas = 15_000 if px == 240 else 5_000
            assert n < batas, f"maskot-{pose}-v3-{px}.png {n}B melebihi {batas}B"
            total += n
    assert total < 80_000, f"total enam pose maskot {total}B terlalu berat"


def test_maskot_helper_menolak_pose_dan_ukuran_asing():
    """Enam pose disetujui; nama/ukuran asing tetap ditolak sebelum render."""
    assert set(brand.POSE_MASKOT) == {
        "menyapa", "menunjuk", "berpikir", "membaca", "menulis", "merayakan",
    }
    for pose in ("terbang", "../sandi", "netral"):
        with pytest.raises(ValueError):
            brand.maskot(pose)
    with pytest.raises(ValueError):
        brand.maskot("menyapa", 512)
    for pose in brand.POSE_MASKOT:
        assert f"/aset/maskot-{pose}-v3-240.png" in brand.maskot(pose)
    assert "/aset/maskot-menyapa-v3-240.png" in brand.maskot()


def test_maskot_alt_kosong_default():
    """Maskot hiasan, bukan informasi: pembaca layar harus melewatinya,
    supaya anak tidak mendengar 'gambar ayam' sebelum tiap sapaan."""
    assert 'alt=""' in brand.maskot()
    assert 'alt="Ayam jago merayakan"' in brand.maskot(
        "merayakan", alt="Ayam jago merayakan"
    )


def test_maskot_lazy_load():
    """Maskot tidak boleh memblokir render halaman anak."""
    m = brand.maskot()
    assert 'loading="lazy"' in m and 'decoding="async"' in m


@pytest.mark.parametrize("versi", ("v2", "v3"))
def test_maskot_terlayani_lewat_rute_aset(server, versi):
    for pose in brand.POSE_MASKOT:
        for px in (240, 96):
            nama = f"maskot-{pose}-{versi}-{px}.png"
            kode, isi, hdr = server.minta(f"/aset/{nama}", biner=True)
            assert kode == 200, f"{nama} -> {kode}"
            assert hdr["Content-Type"] == "image/png"
            assert isi == (ROOT / "aset" / nama).read_bytes()
            assert "immutable" in hdr["Cache-Control"]


@pytest.mark.parametrize("jalur,pose,kred", (
    ("/", "menunjuk", None),
    ("/masuk", "menyapa", None),
    ("/daftar", "menyapa", None),
    ("/", "membaca", ("guru", SANDI_GURU)),
))
def test_halaman_publik_dan_guru_pakai_pose_baru(server, jalur, pose, kred):
    """Tak ada URL maskot lama di halaman baru; logo identitas tetap terpisah."""
    import re

    kode, isi, _ = server.minta(jalur, auth=kred)
    assert kode == 200
    gambar = re.findall(r'src="(/aset/maskot-[^"]+)"', isi)
    assert gambar == [f"/aset/maskot-{pose}-v3-240.png"]
    assert "/aset/mark-" in isi or "/aset/lockup-" in isi


def test_maskot_helper_ukuran_intrinsik_tetap():
    """Ukuran disediakan sebelum unduhan agar gambar tidak menggeser layout."""
    for px in (96, 240):
        assert f'width="{px}" height="{px}"' in brand.maskot(px=px)


def test_maskot_tidak_dicetak():
    """Keputusan 3 Sep: kertas A4 tetap fokus ke soal, hemat tinta warna."""
    import render
    from generator import buat_lembar

    lembar = buat_lembar(seed=9, jumlah_soal=2)
    for fn in (render.lembar_soal, render.lembar_penilaian):
        halaman = fn(list(lembar.soal), nama="Putri", tanggal="1 Jan")
        assert "maskot-" not in halaman, f"{fn.__name__} memuat maskot"


@pytest.fixture()
def server_kosong(tmp_path, monkeypatch):
    """Anak yang PUNYA akun tapi BELUM punya sesi — keadaan kosong.

    Terpisah dari fixture `server` karena di sana feby sengaja punya sesi;
    keadaan kosong tidak bisa diuji dari fixture yang sama.
    """
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        database.tambah_siswa(kon, "feby", pemilik="guru")
    yield s
    s.berhenti()


def test_sapaan_anak_pakai_maskot(server):
    """Maskot mendampingi kartu utama; lambang tetap menjadi identitas topbar."""
    from http_test_kit import SANDI_MURID

    kode, isi, _ = server.minta("/murid", auth=("feby", SANDI_MURID))
    assert kode == 200
    assert "Halo, feby!" in isi
    assert "/aset/maskot-menulis-v3-240.png" in isi, "kartu utama anak tanpa maskot latihan"
    # topbar tetap memakai lambang: identitas tidak digeser hiasan
    assert "/aset/mark-sederhana.svg" in isi


def test_banner_selesai_pakai_maskot_merayakan(server):
    """Banner setelah semua jawaban terkirim memakai pose merayakan."""
    from http_test_kit import SANDI_MURID

    with server.buka() as kon:
        sesi_feby = kon.execute(
            "SELECT s.id FROM sesi s JOIN siswa w ON w.id=s.siswa_id WHERE w.nama='feby'"
        ).fetchone()["id"]
        database.tandai_selesai(kon, sesi_feby)
    kode, isi, _ = server.minta(
        f"/murid?selesai={sesi_feby}", auth=("feby", SANDI_MURID)
    )
    assert kode == 200
    assert "Selesai!" in isi
    assert "/aset/maskot-merayakan-v3-96.png" in isi, "banner perayaan tanpa maskot"


def test_keadaan_kosong_pakai_maskot(server_kosong):
    """Anak tanpa sesi melihat maskot, bukan kotak dashed kosong saja."""
    from http_test_kit import SANDI_MURID

    kode, isi, _ = server_kosong.minta("/murid", auth=("feby", SANDI_MURID))
    assert kode == 200
    assert "Belum ada sesi" in isi
    assert "/aset/maskot-berpikir-v3-240.png" in isi, "keadaan kosong tanpa maskot"


def test_keadaan_kosong_border_bukan_teks_literal(server_kosong):
    """Bug ditemukan 3 Sep: blok keadaan kosong memakai '{T.BORDER_VARIAN}'
    di string NON-f-string, jadi border-color terkirim sebagai teks literal
    ke browser dan bordernya tidak berwarna semestinya."""
    from http_test_kit import SANDI_MURID

    _, isi, _ = server_kosong.minta("/murid", auth=("feby", SANDI_MURID))
    assert "{T." not in isi, "ada placeholder f-string yang tidak ter-render"
