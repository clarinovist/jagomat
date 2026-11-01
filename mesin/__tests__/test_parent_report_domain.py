"""Kontrak domain laporan guru -> orang tua: allowlist, token, append-only.

Semua test memakai basis data sintetis di ``tmp_path``; tidak ada DB nyata,
jaringan, atau server HTTP. Rute HTTP diuji terpisah di
``test_parent_report_http.py``.
"""
from __future__ import annotations

import ast
import hashlib
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import parent_report  # noqa: E402
import parent_report_pages  # noqa: E402
import parent_report_store  # noqa: E402

PERIODE = (date(2026, 11, 1), date(2026, 11, 30))


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "laporan.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Bima", "P3", pemilik="guru")
        asing = database.tambah_siswa(kon, "Rara", "P4", pemilik="lain")
        yield kon, anak, asing


def _sesi_terkonfirmasi(kon, siswa_id, tanggal, topik="pola-bilangan", seed=7):
    sesi_id = database.buat_sesi(
        kon, siswa_id, seed=seed, jumlah_soal=1, tanggal=tanggal, topik=topik,
    )
    database.tandai_selesai(kon, sesi_id)
    soal = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]
    database.konfirmasi_hasil(kon, sesi_id, guru="guru", dilewati={soal})
    return sesi_id


def _isi_proyeksi(kon, siswa_id, periode=PERIODE):
    return parent_report.proyeksi(kon, siswa_id, *periode)


def _draf(kon, siswa_id, catatan="", periode=PERIODE, isi=None):
    isi = isi if isi is not None else _isi_proyeksi(kon, siswa_id, periode)
    return parent_report_store.buat_draf(
        kon, siswa_id, periode[0].isoformat(), periode[1].isoformat(),
        parent_report.serialisasi(isi), catatan=catatan, guru="guru",
    )


def _terbitkan(kon, laporan_id, siswa_id, sekarang=1_000):
    return parent_report_store.terbitkan(
        kon, laporan_id, siswa_id,
        parent_report.kejadian_terakhir(kon, siswa_id), "guru", sekarang=sekarang,
    )


def test_topik_hanya_dari_sesi_selesai_dan_terkonfirmasi_dalam_periode(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    # Selesai tetapi belum dikonfirmasi guru: tidak boleh muncul.
    belum = database.buat_sesi(
        kon, anak, seed=9, jumlah_soal=1, tanggal="2026-11-12",
        topik="geometri-datar",
    )
    database.tandai_selesai(kon, belum)
    # Terkonfirmasi tetapi di luar periode: tidak boleh muncul.
    _sesi_terkonfirmasi(kon, anak, "2026-10-31", topik="logika", seed=11)

    isi = _isi_proyeksi(kon, anak)
    assert isi["topik"] == ["Pola Bilangan"]
    assert isi["versi"] == parent_report.VERSI
    assert isi["tahap"]["nomor"] in range(1, 7)
    assert isi["langkah"]


def test_tahap_memakai_peta_netral_enam_pita_dari_reducer(db):
    kon, anak, _ = db
    tahap = parent_report.tahap_sekarang(kon, anak)
    # Anak tanpa riwayat: reducer memulai di tahap 1 "Kenali cara anak".
    assert tahap == {"nomor": 1, "label": "Kenali cara anak"}
    isi = _isi_proyeksi(kon, anak)
    assert isi["langkah"] == parent_report._LANGKAH[0]


def test_isi_allowlist_mengabaikan_kunci_terlarang_di_payload():
    """Mutation M2: kunci tambahan tidak boleh mengubah satu byte pun."""
    bersih = {
        "versi": 1,
        "topik": ["Pola Bilangan"],
        "tahap": {"nomor": 3, "label": "Latihan"},
        "langkah": "Biarkan anak mencoba sendiri.",
    }
    kotor = dict(bersih)
    kotor.update({
        "skor": 0.75,
        "persentase": "80%",
        "kunci": "JAWABAN_RAHASIA",
        "malrule_id": "MALRULE_RAHASIA",
        "sesi_ids": [91, 92],
        "kode_final": "K",
        "kelas_sekolah": 4,
    })
    argumen = ("Bima", "2026-11-01", "2026-11-30", None, "Catatan.", "guru",
               "2026-12-01 10:00:00", date(2026, 12, 31))
    a = parent_report_pages.isi_laporan(*(argumen[:3] + (bersih,) + argumen[4:]))
    b = parent_report_pages.isi_laporan(*(argumen[:3] + (kotor,) + argumen[4:]))
    assert a == b
    for terlarang in ("JAWABAN_RAHASIA", "MALRULE_RAHASIA", "80%", "0.75",
                      "Sesi", "kelas"):
        assert terlarang not in b


def test_renderer_orang_tua_tidak_mengimpor_renderer_laporan_guru():
    sumber = (Path(parent_report_pages.__file__)).read_text()
    pohon = ast.parse(sumber)
    diimpor = set()
    for simpul in ast.walk(pohon):
        if isinstance(simpul, ast.Import):
            diimpor.update(alias.name.split(".")[0] for alias in simpul.names)
        elif isinstance(simpul, ast.ImportFrom) and simpul.module:
            diimpor.add(simpul.module.split(".")[0])
    terlarang = {
        "reports", "report_dashboard", "report_metrics", "report_summary",
        "mastery_report", "cycle_report", "learning_cycle", "learning_journey",
        "learning_cycle_ui", "database", "sqlite3", "sensor_http",
        "product_analytics_http", "parent_report_teacher_pages",
    }
    assert diimpor.isdisjoint(terlarang), diimpor & terlarang


def test_catatan_ditolak_bila_bukan_teks_polos_dan_dibatasi_2000():
    assert parent_report_store.catatan_aman("baris 1\nbaris 2") == "baris 1\nbaris 2"
    with pytest.raises(ValueError):
        parent_report_store.catatan_aman("a\x00b")
    with pytest.raises(ValueError):
        parent_report_store.catatan_aman("a\x07b")
    with pytest.raises(ValueError):
        parent_report_store.catatan_aman("x" * 2001)
    assert len(parent_report_store.catatan_aman("x" * 2000)) == 2000


def test_catatan_di_escape_di_halaman_orang_tua():
    halaman = parent_report_pages.halaman_orang_tua(
        "Bima", "2026-11-01", "2026-11-30",
        {"topik": ["Pola Bilangan"], "tahap": {"nomor": 3, "label": "Latihan"},
         "langkah": "Coba sendiri."},
        "<script>alert(1)</script> & <b>tebal</b>", "guru",
        "2026-12-01 10:00:00", date(2026, 12, 31),
    ).decode()
    assert "<script" not in halaman
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in halaman
    assert "<b>tebal</b>" not in halaman


def test_terbit_append_only_dan_hapus_hanya_untuk_draf(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak, catatan="Awal")
    assert parent_report_store.simpan_catatan(kon, laporan, anak, "Draf boleh diubah")
    assert parent_report_store.hapus_draf(kon, laporan, anak) is True

    laporan = _draf(kon, anak, catatan="Final")
    token = _terbitkan(kon, laporan, anak)
    assert token
    assert parent_report_store.simpan_catatan(kon, laporan, anak, "Ubah") is False
    assert parent_report_store.hapus_draf(kon, laporan, anak) is False
    assert _terbitkan(kon, laporan, anak, sekarang=2_000) is None
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            "UPDATE laporan_ortu SET catatan = 'diam-diam' WHERE id = ?",
            (laporan,),
        )
    baris = parent_report_store.ambil(kon, laporan)
    assert baris["catatan"] == "Final"
    assert baris["diterbitkan"] is not None


def test_hanya_hash_token_disimpan_dan_berlaku_30_hari(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    token = _terbitkan(kon, laporan, anak, sekarang=1_000)
    baris = kon.execute(
        "SELECT token_hash, dibuat, kedaluarsa FROM tautan_laporan WHERE siswa_id = ?",
        (anak,),
    ).fetchone()
    assert baris["token_hash"] == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert token not in tuple(baris)
    assert baris["kedaluarsa"] == 1_000 + 30 * 24 * 60 * 60
    assert " ".join(kon.iterdump()).find(token) == -1
    assert parent_report_store.ambil_tautan(
        kon, token, sekarang=baris["kedaluarsa"] - 1)
    assert parent_report_store.ambil_tautan(
        kon, token, sekarang=baris["kedaluarsa"]) is None


@pytest.mark.parametrize("token", [
    "", "x", "x" * 42, "x" * 44, "!" * 43, " " + "x" * 43, "é" * 43, None, 123,
])
def test_bentuk_token_salah_selalu_none(db, token):
    kon, anak, _ = db
    assert parent_report_store.ambil_tautan(kon, token) is None


def test_terbit_laporan_baru_merotasi_dan_mematikan_token_lama(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    pertama = _draf(kon, anak, periode=(date(2026, 11, 1), date(2026, 11, 15)))
    token_lama = _terbitkan(kon, pertama, anak, sekarang=1_000)
    kedua = _draf(kon, anak, periode=(date(2026, 11, 16), date(2026, 11, 30)))
    token_baru = _terbitkan(kon, kedua, anak, sekarang=2_000)

    assert token_lama != token_baru
    assert parent_report_store.ambil_tautan(kon, token_lama, sekarang=2_001) is None
    assert parent_report_store.ambil_tautan(kon, token_baru, sekarang=2_001)
    jumlah = kon.execute(
        "SELECT COUNT(*) FROM tautan_laporan WHERE siswa_id = ?", (anak,)
    ).fetchone()[0]
    assert jumlah == 1


def test_ganti_tautan_mematikan_token_sebelumnya(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    token1 = _terbitkan(kon, laporan, anak, sekarang=1_000)
    token2 = parent_report_store.ganti_tautan(kon, laporan, anak, sekarang=2_000)
    assert token2 and token1 != token2
    assert parent_report_store.ambil_tautan(kon, token1, sekarang=2_001) is None
    assert parent_report_store.ambil_tautan(kon, token2, sekarang=2_001)
    draf = _draf(kon, anak)
    assert parent_report_store.ganti_tautan(kon, draf, anak) is None


def test_cabut_idempoten_tanpa_perpanjangan_otomatis(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    token = _terbitkan(kon, laporan, anak, sekarang=1_000)
    awal = kon.execute(
        "SELECT kedaluarsa FROM tautan_laporan WHERE siswa_id = ?", (anak,)
    ).fetchone()["kedaluarsa"]
    assert parent_report_store.cabut_tautan(kon, anak, sekarang=1_500) is True
    assert parent_report_store.cabut_tautan(kon, anak, sekarang=1_600) is False
    assert parent_report_store.ambil_tautan(kon, token, sekarang=1_601) is None
    akhir = parent_report_store.tautan_aktif(kon, anak, sekarang=1_700)
    assert akhir["dicabut"] == 1_500
    assert akhir["dapat_dibuka"] == 0
    # Tidak ada perpanjangan: masa berlaku tetap dari saat terbit.
    assert awal == 1_000 + parent_report_store.TTL_DETIK


def test_tautan_ke_draf_tidak_pernah_dapat_dibuka(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    token = "a" * 43
    kon.execute(
        """INSERT INTO tautan_laporan
               (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa)
           VALUES (?, ?, ?, 1, 9999999999)""",
        (anak, laporan, hashlib.sha256(token.encode()).hexdigest()),
    )
    assert parent_report_store.ambil_tautan(kon, token, sekarang=2) is None


def test_fk_komposit_menolak_laporan_anak_lain(db):
    kon, anak, asing = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    _terbitkan(kon, laporan, anak)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            """INSERT INTO tautan_laporan
                   (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa)
               VALUES (?, ?, ?, 1, 9999999999)""",
            (asing, laporan, "b" * 64),
        )


def test_watermark_mendeteksi_bukti_baru(db):
    kon, anak, _ = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    watermark = parent_report.kejadian_terakhir(kon, anak)
    _terbitkan(kon, laporan, anak)
    assert parent_report.perubahan_bukti(kon, anak, watermark) == (False, 0)
    _sesi_terkonfirmasi(kon, anak, "2026-11-20", seed=13)
    ada, jumlah = parent_report.perubahan_bukti(kon, anak, watermark)
    assert ada is True and jumlah == 1


def test_periode_form_menolak_input_tidak_sah():
    hari = date(2026, 11, 20)
    assert parent_report.periode_dari_form({"periode": "30"}, hari) == (
        date(2026, 10, 22), hari)
    assert parent_report.periode_dari_form({"periode": "bulan"}, hari) == (
        date(2026, 11, 1), hari)
    assert parent_report.periode_dari_form(
        {"periode": "custom", "mulai": "2026-11-01", "sampai": "2026-11-10"},
        hari,
    ) == (date(2026, 11, 1), date(2026, 11, 10))
    for data in (
        {"periode": "custom", "mulai": "2026-11-10", "sampai": "2026-11-01"},
        {"periode": "custom", "mulai": "", "sampai": "2026-11-01"},
        {"periode": "custom", "mulai": "2024-01-01", "sampai": "2026-11-20"},
        {"periode": "custom", "mulai": "2026-11-01", "sampai": "2026-12-01"},
        {"periode": "tahun"},
    ):
        with pytest.raises(ValueError):
            parent_report.periode_dari_form(data, hari)


def test_topik_gabungan_tampil_sebagai_nama_ramah(db):
    kon, anak, _ = db
    sesi = _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    kon.execute(
        "UPDATE sesi SET topik = ? WHERE id = ?",
        ("gabungan:pola-bilangan,geometri-datar", sesi),
    )
    assert _isi_proyeksi(kon, anak)["topik"] == ["Gabungan 2 topik"]


def test_hapus_anak_menghapus_laporan_dan_tautannya(tmp_path):
    path = tmp_path / "hapus.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Tanpa Riwayat", "P3", pemilik="guru")
        laporan = _draf(kon, anak, isi={"topik": [], "tahap": None, "langkah": ""})
        token = _terbitkan(kon, laporan, anak)
        assert parent_report_store.ambil_tautan(kon, token, sekarang=1_001)
        kon.execute("DELETE FROM siswa WHERE id = ?", (anak,))
        assert kon.execute("SELECT COUNT(*) FROM laporan_ortu").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 0


def test_upsert_rotasi_menimpa_satu_baris_tautan_per_anak(db):
    """Satu tautan aktif per anak: PK siswa_id menjaga rotasi, bukan duplikasi."""
    kon, anak, asing = db
    _sesi_terkonfirmasi(kon, anak, "2026-11-10")
    laporan = _draf(kon, anak)
    token1 = _terbitkan(kon, laporan, anak)
    kon.execute(
        """INSERT INTO tautan_laporan
               (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa)
           VALUES (?, ?, ?, 1, 9999999999)
           ON CONFLICT(siswa_id) DO UPDATE SET token_hash = excluded.token_hash""",
        (anak, laporan, "c" * 64),
    )
    assert parent_report_store.ambil_tautan(kon, token1) is None
    assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 1


def test_nama_guru_snapshot_memakai_nama_tampilan():
    assert parent_report.nama_guru("feby") == "feby"
    assert parent_report.nama_guru("ibu-ani") == "Ibu Ani"
    assert parent_report.nama_guru("") == ""
    assert parent_report.nama_guru(None) == ""
