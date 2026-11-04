"""Tahap 5 G3: guard kebocoran halaman orang tua (M1 authorizer, M3 teks terlarang, M4 tanpa tulis bukti)."""
import ast
import contextlib
import re
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import parent_report_store as toko  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402
from test_laporan_ortu_guru import GURU, raw  # noqa: E402

MESIN = Path(__file__).resolve().parent.parent
MODUL_BARU = ("parent_report_links.py", "parent_report_store.py", "parent_report_snapshot.py",
              "parent_report_page.py", "parent_report_http.py", "parent_report_guru_pages.py",
              "schema_parent_report.py")
SQLITE_READ, SQLITE_OK, SQLITE_DENY = 20, 0, 1
KOLOM_RAHASIA = {("soal", "kunci"), ("diagnosis", "kode_usulan"), ("diagnosis", "kode_final"),
                 ("diagnosis", "alasan"), ("diagnosis", "malrule_id"), ("malrule", "id"), ("malrule", "alasan"),
                 ("snapshot_outcome", "kode_final"), ("snapshot_outcome", "malrule_id"), ("jawaban", "jawaban")}
TABEL_BUKTI = ("konfirmasi_hasil", "snapshot_outcome", "kejadian_belajar", "bukti_fokus", "sesi", "sesi_soal",
               "jawaban", "diagnosis", "soal", "malrule", "putaran_fokus", "anggota_fokus", "siswa")


def _authorizer(aksi, tabel, kolom, *_):
    if aksi == SQLITE_READ and (tabel, kolom) in KOLOM_RAHASIA:
        return SQLITE_DENY
    return SQLITE_OK


@pytest.fixture()
def s(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    with server.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Bocor Uji", pemilik="guru")
        server.rahasia = {"alasan": "UJI_BOCOR_" + uuid.uuid4().hex, "jawaban": "JAWAB_" + uuid.uuid4().hex[:10]}
        sesi = database.buat_sesi(kon, anak, 77, jumlah_soal=3, topik="logika")
        butir = database.isi_sesi(kon, sesi)
        for b in butir:
            jid = database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban=server.rahasia["jawaban"], cara="hitung")
            database.simpan_diagnosis(kon, jid, benar=False, kode_usulan="K", kode_final="K",
                                      alasan=server.rahasia["alasan"])
        database.tandai_selesai(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, "guru", dilewati=set())
        server.sesi_id = sesi
    server.anak = anak
    yield server
    server.berhenti()


def _terbit(s):
    _, h, _ = raw(s, f"/anak/{s.anak}/laporan-ortu", {"periode": "30hari"})
    lid = int(re.search(r"/(\d+)$", h["Location"]).group(1))
    dasar = f"/anak/{s.anak}/laporan-ortu/{lid}"
    raw(s, dasar + "/catatan", {"catatan": "Catatan guru biasa."})
    _, _, isi = raw(s, dasar + "/terbitkan", {})
    return re.search(r"/laporan-ortu/([A-Za-z0-9_-]{43})", isi).group(1)


def _snapshot_bukti(kon):
    return {t: [tuple(r) for r in kon.execute("SELECT * FROM " + t)] for t in TABEL_BUKTI}


def test_kontrol_authorizer_memang_memblokir_kolom_rahasia(s):
    with s.buka() as kon:
        kon.set_authorizer(_authorizer)
        with pytest.raises(sqlite3.DatabaseError):
            kon.execute("SELECT kunci FROM soal").fetchall()
        with pytest.raises(sqlite3.DatabaseError):
            kon.execute("SELECT kode_final FROM diagnosis").fetchall()


def test_m1_halaman_orang_tua_tidak_membaca_kolom_rahasia(s, monkeypatch):
    """Render sisi orang tua dengan SQLite authorizer: membaca kolom rahasia = gagal."""
    token = _terbit(s)
    asli = database.buka

    @contextlib.contextmanager
    def buka_terjaga(path=None):
        with asli(path) as kon:
            kon.set_authorizer(_authorizer)
            yield kon

    monkeypatch.setattr(database, "buka", buka_terjaga)
    kode, _, isi = raw(s, f"/laporan-ortu/{token}", auth=("x", "y"))
    assert kode == 200 and "Anak Bocor Uji" in isi


def test_m1_store_token_tidak_membaca_kolom_rahasia(s):
    token = _terbit(s)
    with s.buka() as kon:
        kon.set_authorizer(_authorizer)
        assert toko.ambil_dengan_token(kon, token) is not None


def test_m3_teks_terlarang_tidak_muncul_di_halaman_orang_tua(s):
    token = _terbit(s)
    _, _, halaman = raw(s, f"/laporan-ortu/{token}", auth=("x", "y"))
    tampil = re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>", "", halaman, flags=re.S))
    for rahasia in s.rahasia.values():
        assert rahasia not in halaman
    with s.buka() as kon:
        malrule_ids = [r[0] for r in kon.execute("SELECT DISTINCT malrule_id FROM diagnosis WHERE malrule_id IS NOT NULL")]
        template_ids = [r[0] for r in kon.execute("SELECT DISTINCT template_id FROM soal")]
        kunci = [r[0] for r in kon.execute("SELECT DISTINCT kunci FROM soal")]
    for nilai in malrule_ids + template_ids:
        assert nilai not in halaman, nilai
    for pola in (r"malrule", r"miskonsepsi", r"diagnos", r"kunci", r"/sesi/", r"Variasi ", r"benar\s*/", r"%", r"#\d+"):
        assert not re.search(pola, tampil, re.I), pola
    assert not re.search(r"\bP[3-6]\b", tampil)
    for k in kunci:
        if len(k) > 3:
            assert k not in tampil


def test_m3_halaman_guru_pratinjau_juga_bebas_rahasia(s):
    _, h, _ = raw(s, f"/anak/{s.anak}/laporan-ortu", {"periode": "30hari"})
    _, _, detail = raw(s, h["Location"])
    pratinjau = detail.split("Pratinjau")[-1]
    for rahasia in s.rahasia.values():
        assert rahasia not in pratinjau


def test_m4_alur_penuh_tidak_menulis_bukti(s):
    with s.buka() as kon:
        sebelum = _snapshot_bukti(kon)
    token = _terbit(s)
    raw(s, f"/laporan-ortu/{token}", auth=("x", "y"))
    _, h, _ = raw(s, f"/anak/{s.anak}/laporan-ortu", {"periode": "bulan"})
    dasar = h["Location"]
    raw(s, dasar + "/hapus", {})
    laporan_terbit = re.search(r"/laporan-ortu/(\d+)", dasar).group(1)
    raw(s, f"/anak/{s.anak}/laporan-ortu/1/tautan", {})
    raw(s, f"/anak/{s.anak}/laporan-ortu/1/tautan/cabut", {})
    with s.buka() as kon:
        assert _snapshot_bukti(kon) == sebelum
    assert laporan_terbit


def test_m4_statik_sql_modul_baru_hanya_menulis_tabel_laporan():
    boleh = {"laporan_ortu", "tautan_laporan"}
    for nama in MODUL_BARU:
        teks = (MESIN / nama).read_text(encoding="utf-8")
        for cocok in re.finditer(r"(INSERT INTO|UPDATE|DELETE FROM)\s+([a-z_]+)", teks):
            if nama == "schema_parent_report.py":
                continue
            assert cocok.group(2) in boleh, (nama, cocok.group(0))


def test_modul_baru_tidak_mengimpor_telemetri_atau_renderer_laporan_guru():
    terlarang = {"sensor_http", "product_analytics_http", "reports", "report_dashboard", "report_summary",
                 "mastery_report", "cycle_report", "report_store", "report_metrics_html"}
    # Modul pembangun snapshot/halaman guru boleh membaca domain; renderer sisi orang tua tidak.
    for nama in ("parent_report_page.py", "parent_report_links.py", "parent_report_store.py"):
        pohon = ast.parse((MESIN / nama).read_text(encoding="utf-8"))
        impor = {a.name.split(".")[0] for n in ast.walk(pohon) if isinstance(n, ast.Import) for a in n.names}
        impor |= {(n.module or "").split(".")[0] for n in ast.walk(pohon) if isinstance(n, ast.ImportFrom)}
        assert not (impor & terlarang), (nama, impor & terlarang)
    for nama in MODUL_BARU:
        sumber = (MESIN / nama).read_text(encoding="utf-8")
        assert "sensor_http" not in sumber and "product_analytics_http" not in sumber, nama
