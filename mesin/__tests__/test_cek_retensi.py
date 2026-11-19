"""CLI sapuan retensi cek: target, akun hidup, agregat, dan fail-closed."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import cek_gratis  # noqa: E402
import cek_retensi  # noqa: E402
import database  # noqa: E402
from cek_gratis_kit import (  # noqa: E402
    ID_A, SEKARANG, jawab, mulai_cek, tambah_anak, tandai_selesai,
)

TIGA_PULUH_SATU_HARI = "2026-10-17 09:00:00"


def _siapkan(tmp_path):
    db = tmp_path / "latihan.db"
    database.siapkan(db)
    sandi = tmp_path / "sandi.json"
    auth.tambah_akun("guru-uji", "sandi-sintetis-uji", "guru", sandi)
    id_akun = next(a["id_akun"] for a in auth.muat_akun(sandi) if a["pengguna"] == "guru-uji")
    with database.buka(db) as kon:
        anak = tambah_anak(kon, "Anak Sintetis Retensi", "guru-uji", 4)
        sesi_id = mulai_cek(kon, id_akun, anak, "guru-uji")
        jawab(kon, sesi_id, semua_benar=9)
        tandai_selesai(kon, sesi_id, TIGA_PULUH_SATU_HARI)
        assert cek_gratis.selesaikan_jika_siap(kon, id_akun, SEKARANG) is True
    return db, sandi, id_akun, sesi_id


def _bahan(db, sesi_id):
    with database.buka(db) as kon:
        return kon.execute("SELECT COUNT(*) FROM sesi WHERE id = ?", (sesi_id,)).fetchone()[0]


def test_sapuan_cli_menghapus_bahan_dan_mempertahankan_turunan(tmp_path, capsys):
    db, sandi, _id_akun, sesi_id = _siapkan(tmp_path)

    kode = cek_retensi.main(
        ["--database", str(db), "--sandi", str(sandi)], sekarang=SEKARANG)
    keluaran = capsys.readouterr().out

    assert kode == 0
    assert "1 bahan dihapus" in keluaran and "0 terlindungi" in keluaran
    assert _bahan(db, sesi_id) == 0
    with database.buka(db) as kon:
        baris = kon.execute("SELECT sesi_id, skor, bahan_dihapus_pada FROM cek_gratis").fetchone()
    assert baris["sesi_id"] is None and baris["skor"] is not None and baris["bahan_dihapus_pada"]


def test_sapuan_cli_idempoten(tmp_path, capsys):
    db, sandi, _id_akun, _sesi_id = _siapkan(tmp_path)

    assert cek_retensi.main(["--database", str(db), "--sandi", str(sandi)], sekarang=SEKARANG) == 0
    assert cek_retensi.main(["--database", str(db), "--sandi", str(sandi)], sekarang=SEKARANG) == 0

    assert "0 bahan dihapus" in capsys.readouterr().out


def test_cli_menolak_akun_tidak_terbaca_tanpa_menghapus(tmp_path, capsys):
    db, sesi_id = tmp_path / "latihan.db", None
    database.siapkan(db)
    with database.buka(db) as kon:
        anak = tambah_anak(kon, "Anak Sintetis Yatim", "guru-uji", 4)
        sesi_id = mulai_cek(kon, ID_A, anak, "guru-uji")
        tandai_selesai(kon, sesi_id, TIGA_PULUH_SATU_HARI)

    kode = cek_retensi.main(
        ["--database", str(db), "--sandi", str(tmp_path / "tidak-ada.json")], sekarang=SEKARANG)

    assert kode == 2 and "Tidak ada yang diubah" in capsys.readouterr().err
    assert _bahan(db, sesi_id) == 1


def test_cli_database_tidak_ada_exit_2(tmp_path, capsys):
    assert cek_retensi.main(["--database", str(tmp_path / "tidak-ada.db")]) == 2
    assert "tidak ada yang diubah" in capsys.readouterr().err.lower()
