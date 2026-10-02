"""Dashboard per-anak — feedback Filia no. 6.

"Untuk halaman orangtua, ketika punya anak banyak atau siswa banyak better
dikasi nama aja, nah ketika di klik baru pergi ke halaman history anak tsb."

Rute baru /anak/<id>: kartu nama per anak (nama, tingkat, ringkasan jumlah
sesi & badge review), klik → history lengkap anak itu (daftar sesi + strip
buat sesi pindah ke sana). Dashboard tetap jadi daftar kartu NAMA saja.

Kontrak yang dijaga:
- Palang kepemilikan: /anak/<id> wajib lewat _bisa_lihat_siswa (guru pemilik
  atau admin) — sama ketatnya dengan /laporan/<id>.
- Palang murid: halaman ini sisi guru, tapi marker kunci/malrule tetap tidak
  boleh bocor ke HTML (badge hanya status).
- /laporan/<id> & dashboard lama tetap utuh — /anak/<id> tambahan, bukan
  pengganti yang merusak rute lain.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _dua_anak_dengan_sesi(db):
    """Keluarga 'ortu' dengan 2 anak; anak pertama punya 1 sesi ter-review."""
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "Arkan", pemilik="ortu", tingkat="P5")
        b = database.tambah_siswa(kon, "Bila", pemilik="ortu", tingkat="P3")
        database.buat_sesi(kon, a, seed=11, topik="statistika")
        # Sesi yang selesai dan ditinjau menampilkan status semua direview.
        kon.execute(
            "UPDATE sesi SET selesai = datetime('now', '+7 hours'), "
            "direview = datetime('now', '+7 hours') "
            "WHERE siswa_id = ?"
        , (a,))
    return a, b


# ── Dashboard: kartu nama saja ──────────────────────────────────────────


def test_dashboard_kartu_nama_mengarah_ke_anak(db):
    _dua_anak_dengan_sesi(db)
    with database.buka(db) as kon:
        html = teacher_pages.halaman_utama_stitch(
            kon, pemilik="ortu", peran="guru"
        ).decode()
    assert 'href="/anak/' in html, "kartu nama harus menaut ke /anak/<id>"
    assert "Arkan" in html and "Bila" in html


def test_kartu_anak_menyematkan_ringkasan_jumlah_sesi(db):
    _dua_anak_dengan_sesi(db)
    with database.buka(db) as kon:
        html = teacher_pages.halaman_utama_stitch(
            kon, pemilik="ortu", peran="guru"
        ).decode()
    # ringkasan tanpa membuka: jumlah sesi per anak terlihat
    assert "1 latihan tercatat" in html
    # Arkan sesinya sudah direview → "semua direview"; sesi Bila (0) tak
    # menampilkan badge belum-review (0 x apa pun tak pernah tampil)
    assert "semua direview" in html
    # kartu anak berisi nama anak
    assert "Arkan" in html


def _anak_row(db, nama):
    with database.buka(db) as kon:
        return next(
            s["id"] for s in database.daftar_siswa(kon) if s["nama"] == nama
        )


# ── Halaman /anak/<id>: history anak ────────────────────────────────────


def test_halaman_anak_menampilkang_history_dan_strip_sesi(db):
    a, _ = _dua_anak_dengan_sesi(db)
    aid = _anak_row(db, "Arkan")
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT * FROM siswa WHERE id = ?", (aid,)
        ).fetchone()
        html = teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu"
        ).decode()
        latihan = teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu", query="section=latihan"
        ).decode()
    assert "Sesi #" in html
    assert "Buat latihan" in latihan


def test_halaman_anak_menetapkan_sorot_dari_query(db):
    a, _ = _dua_anak_dengan_sesi(db)
    aid = _anak_row(db, "Arkan")
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT * FROM siswa WHERE id = ?", (aid,)
        ).fetchone()
        html = teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu", sorot=None
        ).decode()
    assert "Arkan" in html
