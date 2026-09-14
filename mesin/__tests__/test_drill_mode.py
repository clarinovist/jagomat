"""Fase 1 mode drill — kolom mode + timer pada sesi.

Alur yang dijaga:
  - sesi punya mode 'diagnostik' (default) | 'drill' (Latihan Cepat)
  - sesi drill punya timer: timer_mode 'tanpa'|'sesi'|'soal',
    durasi_menit (default 15), timer_auto (0 peringatan, 1 auto-submit)
  - halaman kerja murid drill TANPA blok Caraku, dengan timer JS
  - diagnosis drill tidak pernah menghasilkan kode N (jawaban tanpa cara
    dianggap menebak) — via suntikan cara sintetis SAAT PANGGILAN, storage
    tetap bersih
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import students  # noqa: E402
import student_pages  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
import reports  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


# ── 1.1 Skema & migrasi ──────────────────────────────────────────────


def test_sesi_baru_default_diagnostik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        sesi_id = database.buat_sesi(kon, sid, seed=42)
        baris = kon.execute(
            "SELECT mode, timer_mode, durasi_menit, timer_auto FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()
        assert baris["mode"] == "diagnostik"
        assert baris["timer_mode"] == "tanpa"
        assert baris["durasi_menit"] == 15
        assert baris["timer_auto"] == 0


def test_migrasi_menambah_mode_dan_timer_pada_db_lama(tmp_path):
    p = tmp_path / "lama.db"
    kon = sqlite3.connect(p)
    # Skema sesi LAMA (tanpa mode/timer) — yang hidup di produksi sebelum ini.
    kon.executescript(
        """CREATE TABLE sesi (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        siswa_id  INTEGER NOT NULL,
        seed      INTEGER NOT NULL,
        topik     TEXT    NOT NULL DEFAULT 'pola-bilangan',
        level     TEXT    NOT NULL DEFAULT 'P3',
        tanggal   TEXT    NOT NULL DEFAULT (date('now', '+7 hours')),
        mulai     TEXT,
        selesai   TEXT,
        catatan   TEXT    NOT NULL DEFAULT '',
        dibuat    TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
    );
    INSERT INTO sesi (siswa_id, seed) VALUES (1, 99);"""
    )
    kon.commit()
    kon.close()

    database.siapkan(p)
    with database.buka(p) as kon:
        baris = kon.execute(
            "SELECT mode, timer_mode, durasi_menit, timer_auto FROM sesi"
        ).fetchone()
        assert baris is not None
        assert baris["mode"] == "diagnostik"
        assert baris["timer_mode"] == "tanpa"
        assert baris["durasi_menit"] == 15
        assert baris["timer_auto"] == 0


# ── 1.2 buat_sesi / buat_sesi_seed_baru terima mode + timer ──────────


def test_buat_sesi_drill_dengan_timer_tersimpan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        sesi_id = database.buat_sesi(
            kon, sid, seed=7, mode="drill",
            timer_mode="sesi", durasi_menit=10, timer_auto=1,
        )
        baris = kon.execute(
            "SELECT mode, timer_mode, durasi_menit, timer_auto FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()
        assert baris["mode"] == "drill"
        assert baris["timer_mode"] == "sesi"
        assert baris["durasi_menit"] == 10
        assert baris["timer_auto"] == 1


def test_buat_sesi_mode_asing_ditolak(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        with pytest.raises(ValueError):
            database.buat_sesi(kon, sid, seed=7, mode="aneh")


def test_buat_sesi_timer_mode_asing_ditolak(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        with pytest.raises(ValueError):
            database.buat_sesi(kon, sid, seed=7, mode="drill", timer_mode="aneh")


def test_buat_sesi_seed_baru_drill_via_web(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        sesi_id = teacher_pages.buat_sesi_seed_baru(
            kon, sid, mode="drill", timer_mode="soal",
            durasi_menit=5, timer_auto=0,
        )
        baris = kon.execute(
            "SELECT mode, timer_mode, durasi_menit, timer_auto FROM sesi WHERE id = ?",
            (sesi_id,),
        ).fetchone()
        assert baris["mode"] == "drill"
        assert baris["timer_mode"] == "soal"
        assert baris["durasi_menit"] == 5
        assert baris["timer_auto"] == 0


# ── 1.3 Form guru + rute /sesi-baru ──────────────────────────────────


def test_form_buat_sesi_memisahkan_mode_dari_batas_waktu(db):
    """Mode menentukan cara menjawab; timer hanya opsi tambahan Latihan Cepat."""
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "AnakUji", pemilik="guru")
        siswa = kon.execute(
            "SELECT * FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        html = teacher_pages.halaman_anak(
            kon, siswa, pengguna="guru", peran="guru",
        ).decode()

    assert "Jawaban dan cara berpikir anak ikut diperiksa." in html
    assert "Anak langsung mengisi jawaban. Cocok untuk pengulangan." in html
    assert 'type="checkbox" name="timer_mode" value="sesi"' in html
    assert "Gunakan batas waktu" in html
    assert "Durasi sesi" in html
    assert 'name="durasi_menit" value="30"' in html
    assert 'name="durasi_menit" value="30" min=' not in html
    assert "Saran: sekitar 3 menit per soal." in html
    assert "Ketika waktu habis" in html
    assert 'name="timer_auto" value="0" checked' in html
    assert "Ingatkan anak, tetapi tetap boleh menyelesaikan" in html
    assert 'name="timer_auto" value="1"' in html
    assert "Kirim jawaban secara otomatis" in html
    assert 'value="soal"' not in html
    assert "Per soal (internal)" not in html
    assert "Auto-submit" not in html


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def test_http_buat_sesi_drill_dengan_timer(server):
    """POST /sesi-baru/<id> dengan mode=drill + timer -> sesi drill."""
    db = server.db
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "AnakUji", pemilik="guru")
        sid = kon.execute("SELECT id FROM siswa WHERE nama = 'AnakUji'").fetchone()[0]
    kode, html, _ = server.minta(
        f"/sesi-baru/{sid}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan", "mode": "drill",
            "timer_mode": "sesi", "durasi_menit": "10", "timer_auto": "1",
        },
    )
    # urllib follow redirect 303 -> 200 (halaman sesi)
    assert kode == 200, f"expected 200 (303 redirect followed), got {kode}"
    assert "Sesi #" in html
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT mode, timer_mode, durasi_menit, timer_auto FROM sesi"
        ).fetchone()
        assert baris is not None
        assert baris["mode"] == "drill"
        assert baris["timer_mode"] == "sesi"
        assert baris["durasi_menit"] == 10
        assert baris["timer_auto"] == 1


def test_http_buat_latihan_cepat_tanpa_batas_waktu(server):
    """Checkbox timer yang tidak dicentang tidak dikirim oleh browser."""
    db = server.db
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "AnakTanpaTimer", pemilik="guru"
        )

    kode, _, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan",
            "mode": "drill",
            "durasi_menit": "30",
            "timer_auto": "0",
        },
    )

    assert kode == 200
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT timer_mode, durasi_menit, timer_auto FROM sesi"
        ).fetchone()
    assert baris["timer_mode"] == "tanpa"
    assert baris["durasi_menit"] == 15
    assert baris["timer_auto"] == 0


def test_http_latihan_cepat_tanpa_timer_mengabaikan_isian_durasi(server):
    """Tanpa timer harus sah meski browser/pemanggil tidak mengirim durasi."""
    db = server.db
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "AnakDurasiDiabaikan", pemilik="guru"
        )

    kode, _, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "mode": "drill"},
    )

    assert kode == 200
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT timer_mode, durasi_menit, timer_auto FROM sesi"
        ).fetchone()
    assert dict(baris) == {
        "timer_mode": "tanpa",
        "durasi_menit": 15,
        "timer_auto": 0,
    }


def test_http_timer_per_soal_lama_tetap_memproses_konfigurasinya(server):
    """API lama tetap sah meski form baru tidak lagi menawarkan per-soal."""
    db = server.db
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "AnakTimerLama", pemilik="guru"
        )

    kode, _, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan",
            "mode": "drill",
            "timer_mode": "soal",
            "durasi_menit": "7",
            "timer_auto": "1",
        },
    )

    assert kode == 200
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT timer_mode, durasi_menit, timer_auto FROM sesi"
        ).fetchone()
    assert dict(baris) == {
        "timer_mode": "soal",
        "durasi_menit": 7,
        "timer_auto": 1,
    }


def test_http_timer_aktif_menolak_durasi_di_luar_batas(server):
    db = server.db
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "AnakDurasiTidakSah", pemilik="guru"
        )

    kode, html, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan",
            "mode": "drill",
            "timer_mode": "sesi",
            "durasi_menit": "181",
        },
    )

    assert kode == 400
    assert "Durasi tidak wajar" in html
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == 0


def test_http_timer_aktif_menolak_digit_unicode_yang_tidak_bisa_diubah(server):
    """Input teks tidak boleh membuat handler melempar ValueError dan HTTP 500."""
    db = server.db
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(
            kon, "AnakDigitUnicode", pemilik="guru"
        )

    kode, html, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan",
            "mode": "drill",
            "timer_mode": "sesi",
            "durasi_menit": "²",
        },
    )

    assert kode == 400
    assert "Durasi tidak wajar" in html
    with database.buka(db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0] == 0


def test_http_buat_sesi_mode_asing_ditolak(server):
    """Mode asing -> 400 dengan pesan jelas."""
    db = server.db
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "AnakUji", pemilik="guru")
        sid = kon.execute("SELECT id FROM siswa WHERE nama = 'AnakUji'").fetchone()[0]
    kode, html, _ = server.minta(
        f"/sesi-baru/{sid}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "mode": "aneh"},
    )
    assert kode == 400
    assert "Mode" in html or "mode" in html


def test_http_buat_sesi_timer_mode_asing_ditolak(server):
    """Timer mode asing -> 400."""
    db = server.db
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "AnakUji", pemilik="guru")
        sid = kon.execute("SELECT id FROM siswa WHERE nama = 'AnakUji'").fetchone()[0]
    kode, html, _ = server.minta(
        f"/sesi-baru/{sid}",
        auth=("guru", SANDI_GURU),
        data={
            "topik": "pola-bilangan", "mode": "drill",
            "timer_mode": "aneh", "durasi_menit": "10",
        },
    )
    assert kode == 400
    assert "timer" in html.lower()


# ── 1.4 Halaman kerja murid — mode drill + timer ─────────────────────


def _buat(kon, nama: str, seed: int, **kw) -> tuple[int, int]:
    sid = database.tambah_siswa(kon, nama)
    sesi_id = database.buat_sesi(kon, sid, seed=seed, **kw)
    return sid, sesi_id


def test_halaman_kerja_drill_tanpa_caraku(db):
    """Drill: tanpa Caraku, tanpa restate; Jawabanku + centang tetap ada.

    Marker dicek di BADAN halaman (label/name), bukan string global —
    GAYA_STITCH memuat komentar "Caraku" dan kelas pilihan yang selalu
    ada di berkas CSS, jadi cek 'name=...' dan label persis.
    """
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakDrill", 7, mode="drill")
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    assert "Caraku — pilih dulu" not in html      # label pill tidak ada
    assert 'name="pilih_' not in html             # radio pill tidak ada
    assert 'name="cara_' not in html              # textarea cara tidak ada
    assert 'name="restate_' not in html           # restate tidak ada
    assert 'name="jwb_' in html                   # Jawabanku tetap
    assert "belum pernah lihat" in html           # centang tetap


def test_halaman_kerja_diagnostik_masih_punya_caraku(db):
    """Diagnosa (default): pill Caraku + textarea tetap ada."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakDiag", 7)
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    assert "Caraku — pilih dulu" in html
    assert 'name="pilih_' in html
    assert 'name="cara_' in html
    assert 'id="timer-strip"' not in html  # Diagnosa tanpa timer


def test_halaman_kerja_drill_timer_per_sesi_tampil(db):
    with database.buka(db) as kon:
        sid, sesi_id = _buat(
            kon, "AnakDrillSesi", 7, mode="drill",
            timer_mode="sesi", durasi_menit=10,
        )
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    assert 'id="timer-strip"' in html
    assert "Sisa waktu" in html
    assert "10:00" in html


def test_halaman_kerja_drill_timer_per_soal_internal(db):
    """Per-soal: tidak ada countdown tampil, tapi kartu punya penanda + JS."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(
            kon, "AnakDrillSoal", 7, mode="drill",
            timer_mode="soal", durasi_menit=5,
        )
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id).decode()
    assert "Sisa waktu" not in html             # internal, tak dimunculkan
    assert 'class="catatan-soal-timer-st"' in html    # penanda per kartu
    assert "setInterval" in html                # ada JS timer


# ── 1.5 Diagnosis drill — suntikan cara sintetis, tidak pernah N ──────


def _simpan_sebagai_murid(kon, siswa_id, sesi_id, nomor: int, isi: dict):
    """Kirim form persis seperti HP anak: kunci field pakai sesi_soal_id."""
    baris = next(
        b for b in database.isi_sesi(kon, sesi_id) if b["nomor"] == nomor
    )
    ssid = baris["sesi_soal_id"]
    data = {k.replace("<ssid>", str(ssid)): v for k, v in isi.items()}
    hasil = students.simpan_jawaban_murid(kon, siswa_id, sesi_id, data)
    if hasil:
        reports.diagnosa_murid(kon, sesi_id)
    return hasil


def _baris_soal(kon, sesi_id, nomor: int):
    return next(
        b for b in database.isi_sesi(kon, sesi_id) if b["nomor"] == nomor
    )


def test_drill_jawaban_benar_tanpa_cara_tidak_dinilai_menebak(db):
    """Kunci diagnosa drill: jawaban benar tanpa Caraku -> benar, BUKAN N."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakDrillBenar", 7, mode="drill")
        kunci = _baris_soal(kon, sesi_id, 1)["kunci"]
        _simpan_sebagai_murid(
            kon, sid, sesi_id, 1, {"jwb_<ssid>": kunci}
        )
        b = _baris_soal(kon, sesi_id, 1)
    assert b["benar"] == 1
    assert b["kode_final"] is None          # bukan N
    assert b["cara"] == ""                  # storage tetap bersih


def test_drill_salah_cocok_malrule_tetap_dapat_kode(db):
    """Jawaban salah yang cocok malrule -> kode malrule (K/H/E), bukan N."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakDrillMal", 7, mode="drill")
        for b in database.isi_sesi(kon, sesi_id):
            mal = database.malrule_soal(kon, b["soal_id"])
            if mal:
                _simpan_sebagai_murid(
                    kon, sid, sesi_id, b["nomor"], {"jwb_<ssid>": mal[0]["jawaban"]}
                )
                hasil = _baris_soal(kon, sesi_id, b["nomor"])
                assert hasil["kode_final"] == mal[0]["kode"]
                assert hasil["kode_final"] != "N"
                break
        else:
            pytest.fail("seed 7 tidak punya malrule untuk diuji")


def test_diagnostik_jawaban_benar_tanpa_cara_tetap_N(db):
    """Mode Diagnosa: aturan lama TIDAK berubah — benar tanpa cara = N."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakDiagN", 7)  # default diagnostik
        kunci = _baris_soal(kon, sesi_id, 1)["kunci"]
        _simpan_sebagai_murid(kon, sid, sesi_id, 1, {"jwb_<ssid>": kunci})
        b = _baris_soal(kon, sesi_id, 1)
    assert b["benar"] == 0
    assert b["kode_final"] == "N"


# ── 1.6 Label mode di guru + kartu sesi murid ─────────────────────────


def test_halaman_sesi_guru_menampilkan_badge_latihan_cepat(db):
    """Badge drill dicek lewat marker kelas — CSS guru memuat teks
    'Latihan Cepat' di komentar, jadi string global tidak bisa dipakai."""
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakBadge", 7, mode="drill")
        html = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    assert 'class="badge-mode"' in html


def test_halaman_sesi_guru_diagnostik_tanpa_badge_drill(db):
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakBadgeDiag", 7)
        html = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    assert 'class="badge-mode"' not in html


def test_kartu_sesi_murid_menampilkan_tag_latihan(db):
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakKartu", 7, mode="drill")
        nama = kon.execute(
            "SELECT nama FROM siswa WHERE id = ?", (sid,)
        ).fetchone()["nama"]
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, nama).decode()
    assert '<span class="murid-tahap-st">Latihan Cepat</span>' in html


def test_kartu_sesi_murid_diagnostik_tanpa_tag_latihan(db):
    with database.buka(db) as kon:
        sid, sesi_id = _buat(kon, "AnakKartuDiag", 7)
        nama = kon.execute(
            "SELECT nama FROM siswa WHERE id = ?", (sid,)
        ).fetchone()["nama"]
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, nama).decode()
    assert '<span class="murid-tahap-st">Latihan Cepat</span>' not in html


# ── 1.7 E2E HTTP: drill alur penuh ──────────────────────────────────


def test_http_drill_alur_penuh_tanpa_kode_N(server):
    """Guru buat sesi drill -> murid jawab tanpa cara (via HP) ->
    guru buka halaman sesi -> tidak ada kode N (menebak)."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")  # nama == akun murid uji

    # Guru buat sesi drill via POST
    server.minta(
        f"/sesi-baru/{siswa_id}", auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "mode": "drill",
              "timer_mode": "sesi", "durasi_menit": "15"},
    )
    with server.buka() as kon:
        sesi_id = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"]
        kunci = database.isi_sesi(kon, sesi_id)[0]["kunci"]
        ssid = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]

    # Murid jawab via HP (tanpa cara, persis yang dikirim browser)
    kode, _, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": kunci, "aksi": "selesai"},
    )
    assert kode == 200

    # Guru buka halaman sesi: harus BENAR, bukan N
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert '<span class="kode benar">BENAR</span>' in isi, (
        "guru melihat N padahal anak drill jawab benar tanpa cara"
    )
    # Tidak ada kode N untuk soal ini
    assert 'class="kode N"' not in isi

