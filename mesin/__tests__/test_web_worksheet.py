"""Verifikasi rute lembar di web — soal bisa dicetak langsung dari situs.

Bahaya terbesar di lapisan ini: rute lembar anak dan lembar kunci hanya
berbeda satu ruas URL. Salah menyambungkannya berarti anak bisa membuka
kunci jawaban lewat tautan yang dia lihat di layar guru — dan halamannya
tetap tampil normal, jadi tidak ada yang menyadari sampai terlambat.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import presentation_lock  # noqa: E402
import question_views  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def teks(html_bytes: bytes | None) -> str:
    assert html_bytes is not None, "lembar tidak terbangkit"
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_bytes.decode(), flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


def html_dari(isi: bytes | None) -> str:
    """Pastikan lembar benar-benar terbangkit sebelum diperiksa isinya."""
    assert isi is not None, "lembar tidak terbangkit — sesi tidak ditemukan?"
    return isi.decode()


def test_lembar_soal_bisa_dibangkitkan_dari_sesi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Cetak")
        sesi_id = database.buat_sesi(kon, sid, seed=1234)
        isi = teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=False)

    assert isi is not None
    h = isi.decode()
    assert h.startswith("<!DOCTYPE html>")
    assert h.count('class="soal"') == 12
    assert "Cetak" in h


def test_lembar_membekukan_penyajian_tanpa_menandai_pengerjaan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Freeze cetak")
        sesi_id = database.buat_sesi(kon, sid, seed=4321)

        assert teacher_pages.halaman_lembar(kon, sesi_id) is not None
        keadaan = kon.execute(
            """SELECT penyajian_dibekukan, mulai, selesai
               FROM sesi WHERE id = ?""",
            (sesi_id,),
        ).fetchone()

    assert keadaan["penyajian_dibekukan"] is not None
    assert keadaan["mulai"] is None
    assert keadaan["selesai"] is None


def test_setelah_print_service_dan_raw_sql_tidak_bisa_mengubah_snapshot(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Palang print")
        sesi_id = database.buat_sesi(kon, sid, seed=9876, jumlah_soal=1)
        awal = database.isi_sesi(kon, sesi_id)[0]
        snapshot_baru = question_views.penyajian_dari_baris(awal)

        assert teacher_pages.halaman_lembar(kon, sesi_id) is not None
        assert presentation_lock.perbarui_snapshot(
            kon,
            awal["sesi_soal_id"],
            awal["fingerprint_penyajian"],
            snapshot_baru,
        ) is False
        with pytest.raises(sqlite3.IntegrityError, match="snapshot penyajian terkunci"):
            kon.execute(
                "UPDATE sesi_soal SET teks_soal = teks_soal || ' berubah' WHERE id = ?",
                (awal["sesi_soal_id"],),
            )

        akhir = database.isi_sesi(kon, sesi_id)[0]
    assert akhir["fingerprint_penyajian"] == awal["fingerprint_penyajian"]
    assert akhir["teks_soal"] == awal["teks_soal"]


def test_lembar_membekukan_sebelum_renderer_dipanggil(db, monkeypatch):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Urutan freeze")
        sesi_id = database.buat_sesi(kon, sid, seed=6789)

        def periksa_beku(*_args, **_kwargs):
            keadaan = kon.execute(
                "SELECT penyajian_dibekukan FROM sesi WHERE id = ?", (sesi_id,)
            ).fetchone()
            assert keadaan["penyajian_dibekukan"] is not None
            return "<html>beku</html>"

        monkeypatch.setattr(teacher_pages.worksheets, "lembar_soal", periksa_beku)
        assert teacher_pages.halaman_lembar(kon, sesi_id) == b"<html>beku</html>"


def test_lembar_tidak_commit_transaksi_pemanggil(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Transaksi freeze")
        sesi_id = database.buat_sesi(kon, sid, seed=2468)
        kon.commit()
        kon.execute("SAVEPOINT transaksi_pemanggil")

        assert teacher_pages.halaman_lembar(kon, sesi_id) is not None
        kon.execute("ROLLBACK TO SAVEPOINT transaksi_pemanggil")
        kon.execute("RELEASE SAVEPOINT transaksi_pemanggil")
        keadaan = kon.execute(
            "SELECT penyajian_dibekukan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()

    assert keadaan["penyajian_dibekukan"] is None


def test_kegagalan_render_menggulung_pembekuan(db, monkeypatch):
    with pytest.raises(RuntimeError, match="render sengaja gagal"):
        with database.buka(db) as kon:
            sid = database.tambah_siswa(kon, "Render gagal")
            sesi_id = database.buat_sesi(kon, sid, seed=1357)
            kon.commit()
            monkeypatch.setattr(
                teacher_pages.worksheets,
                "lembar_soal",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("render sengaja gagal")
                ),
            )
            teacher_pages.halaman_lembar(kon, sesi_id)

    with database.buka(db) as kon:
        keadaan = kon.execute(
            "SELECT penyajian_dibekukan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
    assert keadaan["penyajian_dibekukan"] is None


def test_lembar_anak_tidak_memuat_kunci_di_posisi_jawaban(db):
    """Rute /lembar/<id> dipegang anak — kotak jawaban harus kosong."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(kon, sid, seed=555)
        h = html_dari(teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=False))

    for potongan in re.findall(r'class="jawab">(.*?)</div>', h, flags=re.S):
        terbaca = teks(potongan.encode()).replace("Jawabanku:", "")
        terbaca = terbaca.replace("urutan ke-", "").replace("dan", "").strip()
        assert not terbaca, f"ada teks di posisi jawaban: {terbaca!r}"


def test_lembar_anak_tidak_memuat_kata_kunci_atau_kode(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak2")
        sesi_id = database.buat_sesi(kon, sid, seed=77)
        t = teks(teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=False)).lower()

    for terlarang in ("kunci", "malrule", "miskonsepsi", "salah konsep",
                      "jangan diperlihatkan"):
        assert terlarang not in t, f"{terlarang!r} bocor ke lembar anak"


def test_lembar_penilaian_justru_memuat_kunci(db):
    """Kebalikannya: guru harus melihat semua kunci."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Guru")
        sesi_id = database.buat_sesi(kon, sid, seed=99)
        kunci = [b["kunci"] for b in database.isi_sesi(kon, sesi_id)]
        h = html_dari(teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=True))

    for k in kunci:
        assert k in h
    assert "Jangan diperlihatkan ke anak" in h


def test_lembar_cocok_dengan_soal_yang_tercatat_di_sesi(db):
    """Lembar dibangkitkan dari seed, bukan dibaca berkas — harus tetap
    cocok dengan soal yang tersimpan, kalau tidak guru menilai soal lain."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Cocok")
        sesi_id = database.buat_sesi(kon, sid, seed=31337)
        tercatat = database.isi_sesi(kon, sesi_id)
        h = html_dari(teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=True))

    for b in tercatat:
        assert b["kunci"] in h, f"kunci soal {b['nomor']} tidak ada di lembar"


def test_sesi_tidak_ada_mengembalikan_none(db):
    with database.buka(db) as kon:
        assert teacher_pages.halaman_lembar(kon, 99999) is None


# ── Buat sesi baru dari web ─────────────────────────────────────────────


def test_sesi_baru_memakai_seed_yang_belum_pernah_dipakai(db):
    """Seed berulang = soal persis sama = anak bisa hafal jawabannya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Seed")
        dibuat = [teacher_pages.buat_sesi_seed_baru(kon, sid) for _ in range(12)]
        seeds = [
            r["seed"]
            for r in kon.execute(
                "SELECT seed FROM sesi WHERE siswa_id = ?", (sid,)
            ).fetchall()
        ]

    assert len(dibuat) == len(set(dibuat)), "id sesi terduplikasi"
    assert len(seeds) == len(set(seeds)), "seed terulang — anak bisa hafal soal"


def test_sesi_baru_langsung_berisi_dua_belas_soal(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Isi")
        sesi_id = teacher_pages.buat_sesi_seed_baru(kon, sid)
        assert len(database.isi_sesi(kon, sesi_id)) == 12


def test_dua_siswa_dapat_soal_berbeda(db):
    """Kalau lembarnya sama, satu anak bisa menyalin yang lain."""
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "A")
        b = database.tambah_siswa(kon, "B")
        sa = teacher_pages.buat_sesi_seed_baru(kon, a)
        sb = teacher_pages.buat_sesi_seed_baru(kon, b)
        soal_a = [r["soal_id"] for r in database.isi_sesi(kon, sa)]
        soal_b = [r["soal_id"] for r in database.isi_sesi(kon, sb)]

    assert soal_a != soal_b


def test_halaman_utama_tautan_lembar_pindah_ke_halaman_sesi(db):
    """Backward-compat alias — nama lama tetap hijau."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "TautanAlias")
        sesi_id = database.buat_sesi(kon, sid, seed=99)
        hc_raw = teacher_pages.halaman_sesi_cetak(kon, sesi_id)
        assert hc_raw is not None
        assert f'href="/lembar/{sesi_id}"' in hc_raw.decode()


def test_halaman_utama_tautan_lembar_pindah_ke_halaman_cetak(db):
    """Lembar soal/kunci cukup satu pintu: dari halaman cetak (opsi 3).
    Dashboard dan halaman koreksi tidak lagi memuatnya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tautan")
        sesi_id = database.buat_sesi(kon, sid, seed=42)
        h = teacher_pages.halaman_utama_stitch(kon).decode()
        hs = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
        hc_raw = teacher_pages.halaman_sesi_cetak(kon, sesi_id)
        assert hc_raw is not None
        hc = hc_raw.decode()
        siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (sid,)).fetchone()
        profil = teacher_pages.halaman_anak(
            kon, siswa, query="section=latihan"
        ).decode()

    assert f'href="/lembar/{sesi_id}"' not in h
    assert f'href="/lembar/{sesi_id}/penilaian"' not in h
    assert f'href="/lembar/{sesi_id}"' not in hs
    assert f'href="/lembar/{sesi_id}/penilaian"' not in hs
    assert f'href="/lembar/{sesi_id}"' in hc
    assert f'href="/lembar/{sesi_id}/penilaian"' in hc
    assert f'action="/sesi-baru/{sid}"' not in h
    assert f'action="/sesi-baru/{sid}"' in profil


def test_navigasi_sesi_kembali_ke_semua_sesi_anak(db):
    """Ketiga tab sesi kembali ke riwayat anak, bukan lompat ke dashboard."""
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Claudia")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=42)
        halaman = (
            teacher_pages.halaman_sesi_stitch(kon, sesi_id),
            teacher_pages.halaman_sesi_cetak(kon, sesi_id),
            teacher_pages.halaman_sesi_lampiran(kon, sesi_id),
        )

    for isi in halaman:
        html = html_dari(isi)
        assert f'href="/anak/{siswa_id}?section=riwayat"' in html
        assert ("&larr; Semua sesi Claudia" in html or "&larr; Riwayat Claudia" in html)
        assert "Kembali ke koreksi" not in html
        assert "&larr; Semua siswa" not in html
