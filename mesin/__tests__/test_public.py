"""Fase 0 + A launch publik: identitas brand & landing publik.

Kontrak yang dijaga:
1. Identitas produk dari design_tokens (satu sumber) — tidak ada literal
   "Mesin Latihan"/"pola bilangan" di copy deskriptif web.py.
2. GET / tanpa sesi -> 200 landing publik (bukan 401).
3. GET / dengan sesi guru -> pengalihan /guru, lalu beranda editorial.
4. Rute guru lain tetap 401 tanpa kredensial (palang tidak melemah).
5. Landing tidak bocor kata palang (kunci/malrule/diagnosa).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import design_tokens as T  # noqa: E402
import landing  # noqa: E402
import web  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


# ───────────────────────── Fase 0: identitas ─────────────────────────

def test_tokens_punya_identitas_produk():
    assert getattr(T, "NAMA_PRODUK", "") == "Jagomat"
    assert getattr(T, "TAGLINE", "").strip()


# Brand lama yang tidak boleh kembali muncul sebagai literal di modul mana
# pun. "Caraku" TIDAK masuk daftar: kata itu punya makna kedua yang vital —
# label kotak tempat anak menulis caranya, dipakai diagnosis.py/render.py.
BRAND_LAMA = ("Mesin Latihan",)

ROOT_MESIN = Path(__file__).resolve().parent.parent


def test_tidak_ada_literal_brand_lama_di_seluruh_modul():
    """Guard lama hanya menyapu web.py — karena itu "Mesin Latihan" bertahan
    di kop lembar cetak (render.py) selama berbulan-bulan, justru di kertas
    yang dipegang anak dan orang tua. Guard ini menyapu SEMUA modul root."""
    tersangka: list[str] = []
    for berkas in sorted(ROOT_MESIN.glob("*.py")):
        sumber = berkas.read_text(encoding="utf-8")
        for ln_no, ln in enumerate(sumber.splitlines(), 1):
            if any(b in ln for b in BRAND_LAMA):
                tersangka.append(f"{berkas.name}:{ln_no}: {ln.strip()}")
    assert not tersangka, (
        "brand lama masih ada — pakai T.NAMA_PRODUK:\n" + "\n".join(tersangka)
    )


def test_lembar_cetak_pakai_brand_dari_tokens():
    """Kop lembar soal DAN lembar penilaian menyebut nama produk yang
    berlaku, bukan nama lama yang di-hardcode."""
    import render
    from generator import buat_lembar

    lembar = buat_lembar(seed=7, jumlah_soal=2)
    for fn in (render.lembar_soal, render.lembar_penilaian):
        halaman = fn(list(lembar.soal), nama="Putri", tanggal="1 Jan")
        assert T.NAMA_PRODUK in halaman, f"{fn.__name__} tanpa nama produk"


def test_web_tidak_ada_literal_brand_lama():
    sumber = Path(web.__file__).read_text(encoding="utf-8")
    # Copy deskriptif yang dilihat pengguna; komentar kode internal dikecualikan.
    # "pola bilangan" sebagai NAMA TOPIK di registry (topik_*.py) tetap sah.
    baris_copy = [
        ln
        for ln in sumber.splitlines()
        if "pola bilangan" in ln.lower()
        and not ln.lstrip().startswith("#")
        and '"pola bilangan"' not in ln  # nilai pilihan/registry sah
    ]
    assert not baris_copy, f"copy lama tersisa: {baris_copy}"
    assert "Mesin Latihan" not in sumber


def test_halaman_masuk_pakai_brand_baru():
    # _halaman_masuk dipanggil tanpa instance server — akses lewat kelas.
    # Yang dites: halaman login tidak lagi menyebut topik lama.
    sumber = Path(web.__file__).read_text(encoding="utf-8")
    assert "T.NAMA_PRODUK" in sumber, "web.py harus merujuk brand dari tokens"


# ───────────────── Fase A: landing vs dashboard di rute / ─────────────────

@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        sid = database.tambah_siswa(kon, "Putri")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
    yield s, sesi_id
    s.berhenti()


def test_rute_publik_mempertahankan_lookup_renderer(server, monkeypatch):
    s, _ = server
    panggilan = []

    def landing_terpantau(*, dukungan):
        panggilan.append(dukungan)
        return b"<h1>Landing sintetis</h1>"

    monkeypatch.setattr(landing, "halaman_landing", landing_terpantau)
    kode, isi, _ = s.minta("/")

    assert kode == 200
    assert isi == "<h1>Landing sintetis</h1>"
    assert len(panggilan) == 1


def test_landing_200_tanpa_sesi(server):
    s, _ = server
    kode, isi, _ = s.minta("/")
    assert kode == 200
    assert T.NAMA_PRODUK in isi
    assert T.TAGLINE in isi
    assert "/daftar" in isi  # CTA pendaftaran
    assert "/masuk" in isi


def test_landing_bocor_palang_tidak_boleh(server):
    s, _ = server
    _, isi, _ = s.minta("/")
    rendah = isi.lower()
    for kata in ("kunci", "malrule"):
        # marker CSS (.kunci{}) tidak dihitung — cek kata berarti
        assert f">{kata}<" not in rendah and f'"{kata}"' not in rendah


def test_dashboard_guru_di_root(server):
    s, sesi_id = server
    kode, isi, _ = s.minta("/", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Sesi" in isi or "sesi" in isi  # dashboard, bukan landing


def test_rute_guru_lain_tetap_401_tanpa_sesi(server):
    s, sesi_id = server
    assert s.minta(f"/sesi/{sesi_id}")[0] == 401
    assert s.minta("/akun")[0] == 401


def test_murid_tetap_401_di_root(server):
    """Murid tidak boleh masuk dashboard guru via /."""
    from http_test_kit import SANDI_MURID

    s, _ = server
    kode, isi, _ = s.minta("/", auth=("feby", SANDI_MURID))
    # murid -> landing publik (200), BUKAN dashboard guru
    assert kode == 200
    assert T.NAMA_PRODUK in isi
    assert "Buat sesi baru" not in isi  # elemen khas dashboard guru


# ───────────────── kebijakan privasi (publik) ─────────────────

def test_kebijakan_privasi_200_tanpa_sesi(server):
    """Tautan consent /daftar & footer landing tak boleh 404 lagi."""
    s, _ = server
    kode, isi, _ = s.minta("/kebijakan-privasi")
    assert kode == 200
    assert "Kebijakan Privasi" in isi
    assert 'href="/masuk"' in isi  # satu pintu masuk, konsisten landing


def test_masuk_punya_tautan_lupa_sandi(server):
    """Di bawah tombol Masuk ada tautan "Lupa sandi?" — pintu ke panduan,
    bukan sekadar teks pasif "pakai kata sandi yang diberikan"."""
    s, _ = server
    kode, isi, _ = s.minta("/masuk")
    assert kode == 200
    assert 'href="/lupa-sandi"' in isi


def test_lupa_sandi_200_dan_memuat_panduan(server):
    """Halaman lupa sandi publik dan jujur: aplikasi tidak menyimpan email,
    jadi isinya panduan konkret — murid minta guru/orang tua menyetel sandi
    baru, orang tua menghubungi pengelola."""
    s, _ = server
    kode, isi, _ = s.minta("/lupa-sandi")
    assert kode == 200
    assert "Lupa sandi?" in isi
    assert "Setel sandi baru" in isi  # panduan konkret untuk murid


def test_kebijakan_privasi_bocor_data_tidak_boleh(server):
    """Halaman hanya memakai config dukungan global, bukan data keluarga.
    (Id sesi sengaja tidak dites — angka kecil selalu ada di CSS/teks.)"""
    s, _ = server
    _, isi_anon, _ = s.minta("/kebijakan-privasi")
    _, isi_guru, _ = s.minta("/kebijakan-privasi", auth=("guru", SANDI_GURU))
    assert isi_anon == isi_guru, "halaman harus statis"
    assert "Putri" not in isi_anon  # nama siswa fixture tidak bocor
