"""Diagnosis otomatis saat murid simpan dari HP (Fase berikutnya).

Dulu: anak simpan dari HP -> jawaban masuk TANPA diagnosis. Halaman sesi
guru penuh "?" oranye sampai guru menekan "Simpan & diagnosis" — padahal
guru sering hanya ingin membaca hasilnya dulu.

Sekarang: setiap jawaban yang masuk lewat jalur murid langsung didiagnosis
mesin (usulan, manual=0). Guru tetap berkuasa penuh: kode yang IA tetapkan
(manual=1) tidak boleh tertimpa kalau anak memperbarui jawabannya.

Palang tetap utuh: semua diagnosis terjadi di sisi server lewat modul web,
bukan di students.py. Test palang di test_murid.py tetap mengawasi.
"""

from __future__ import annotations

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


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _simpan_sebagai_murid(kon, siswa_id, sesi_id, nomor: int, isi: dict):
    """Kirim form persis seperti yang HP anak kirim: kunci field pakai
    sesi_soal_id, bukan nomor. Diagnosisnya dijalankan terpisah lewat
    reports.diagnosa_murid — persis urutan yang dilakukan handler POST
    /murid/kerjakan/ (wiring otomatisnya diuji test HTTP di bawah)."""
    baris = next(
        b for b in database.isi_sesi(kon, sesi_id) if b["nomor"] == nomor
    )
    ssid = baris["sesi_soal_id"]
    data = {}
    for k, v in isi.items():
        data[k.replace("<ssid>", str(ssid))] = v
    hasil = students.simpan_jawaban_murid(kon, siswa_id, sesi_id, data)
    if hasil:
        reports.diagnosa_murid(kon, sesi_id)
    return hasil


def _diagnosis(kon, sesi_id, nomor: int):
    return next(
        b for b in database.isi_sesi(kon, sesi_id) if b["nomor"] == nomor
    )


# ── Diagnosis terisi tanpa guru ──────────────────────────────────────────


def test_jawaban_benar_dari_murid_langsung_didiagnosis(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakOtomatis")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        kunci = _diagnosis(kon, sesi_id, 1)["kunci"]

        _simpan_sebagai_murid(
            kon, sid, sesi_id, 1,
            {"jwb_<ssid>": kunci, "cara_<ssid>": "aku hitung maju"},
        )
        b = _diagnosis(kon, sesi_id, 1)

    assert b["benar"] == 1
    assert b["manual"] == 0
    assert b["alasan"] == "jawaban benar"


def test_jawaban_malrule_dari_murid_langsung_dapat_kode(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakMalrule")
        sesi_id = database.buat_sesi(kon, sid, seed=6)
        for b in database.isi_sesi(kon, sesi_id):
            mal = database.malrule_soal(kon, b["soal_id"])
            if mal:
                _simpan_sebagai_murid(
                    kon, sid, sesi_id, b["nomor"],
                    {"jwb_<ssid>": mal[0]["jawaban"], "cara_<ssid>": "hmm"},
                )
                hasil = _diagnosis(kon, sesi_id, b["nomor"])
                assert hasil["kode_final"] == mal[0]["kode"]
                break
        else:
            pytest.fail("seed 6 tidak punya malrule untuk diuji")


def test_mengaku_menebak_dari_murid_jadi_N_tanpa_guru(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakTebak")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        _simpan_sebagai_murid(
            kon, sid, sesi_id, 1,
            {"jwb_<ssid>": "123", "pilih_<ssid>": "tebak"},
        )
        b = _diagnosis(kon, sesi_id, 1)

    assert b["kode_final"] == "N"
    assert b["benar"] == 0


# ── Keputusan guru tidak boleh tertimpa ──────────────────────────────────


def test_kode_manual_guru_bertahan_saat_murid_perbarui_jawaban(db):
    """Guru menimpa usulan mesin (manual). Anak lalu memperbarui jawabannya
    dari HP (teks sama — simpan idempoten). Kode guru TIDAK boleh berubah.
    Usulan mesin baru tetap tercatat di kode_usulan untuk direview."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakTimpa")
        sesi_id = database.buat_sesi(kon, sid, seed=8)
        b = database.isi_sesi(kon, sesi_id)[0]
        ssid = b["sesi_soal_id"]
        jwb = (b["kunci"] + "-salah") if b["kunci"] else "salah"

        # 1) murid simpan dari HP -> diagnosis usulan otomatis
        students.simpan_jawaban_murid(
            kon, sid, sesi_id, {f"jwb_{ssid}": jwb, f"cara_{ssid}": "coba"}
        )
        # 2) guru menimpa: kode E manual
        teacher_pages.simpan_sesi(
            kon, sesi_id,
            {f"jwb_{ssid}": jwb, f"cara_{ssid}": "coba", f"kode_{ssid}": "E"},
        )
        assert database.isi_sesi(kon, sesi_id)[0]["manual"] == 1

        # 3) anak memperbarui (teks sama) dari HP — handler menjalankan
        #    diagnosa_murid lagi; di sinilah palang manual diuji
        students.simpan_jawaban_murid(
            kon, sid, sesi_id, {f"jwb_{ssid}": jwb, f"cara_{ssid}": "coba"}
        )
        reports.diagnosa_murid(kon, sesi_id)
        hasil = database.isi_sesi(kon, sesi_id)[0]

    assert hasil["kode_final"] == "E", "keputusan guru tertimpa mesin!"
    assert hasil["manual"] == 1
    assert hasil["kode_usulan"] != "E" or hasil["benar"] == 0


# ── Palang tetap: murid tidak melihat hasilnya ───────────────────────────


def test_halaman_murid_tetap_bersih_setelah_diagnosis_otomatis(db):
    """Setelah diagnosis terisi (benar + kode), lembar kerja murid TETAP
    tidak menampilkan BENAR/kode/kunci — kolom diagnosis hanya muncul di
    sisi guru."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakBersih")
        sesi_id = database.buat_sesi(kon, sid, seed=9)
        kunci = database.isi_sesi(kon, sesi_id)[0]["kunci"]
        # simpan jawaban benar untuk semua soal lewat jalur murid
        for b in database.isi_sesi(kon, sesi_id):
            students.simpan_jawaban_murid(
                kon, sid, sesi_id,
                {f"jwb_{b['sesi_soal_id']}": b["kunci"],
                 f"cara_{b['sesi_soal_id']}": "yakin"},
            )
        html = student_pages.halaman_kerja_baru(kon, sid, sesi_id)
        assert html is not None
        html = html.decode()

    assert "BENAR" not in html
    assert 'class="kode' not in html


# ── Ujung ke ujung lewat socket ──────────────────────────────────────────


def test_http_murid_simpan_guru_langsung_lihat_benar(server):
    """Alur nyata: anak POST dari HP -> guru buka halaman sesi -> badge
    BENAR sudah terpasang TANPA guru menekan 'Simpan & diagnosis' dulu."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")  # nama == akun murid uji

    server.minta(
        f"/sesi-baru/{siswa_id}", auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan", "profil_parameter": "P3"},
    )
    with server.buka() as kon:
        sesi_id = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"]
        kunci = database.isi_sesi(kon, sesi_id)[0]["kunci"]
        ssid = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]

    kode, _, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={
            f"jwb_{ssid}": kunci,
            f"cara_{ssid}": "lihat polanya",
            "aksi": "selesai",
        },
    )
    assert kode == 200

    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert '<span class="kode benar">BENAR</span>' in isi, (
        "guru masih melihat '?' padahal jawaban anak sudah benar"
    )
