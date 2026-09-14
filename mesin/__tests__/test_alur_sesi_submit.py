"""Kontrak sesi: simpan sementara, kirim final, dan gerbang koreksi guru."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import student_pages  # noqa: E402
import style_stitch  # noqa: E402
import teacher_pages  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    jalur = tmp_path / "uji.db"
    database.siapkan(jalur)
    return jalur


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=7, jumlah_soal=3,
        )
    yield s, siswa_id, sesi_id
    s.berhenti()


def _field_pertama(kon, sesi_id):
    return database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]


def test_lembar_murid_memisahkan_simpan_sementara_dan_kirim_final(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        halaman = student_pages.halaman_kerja_baru(kon, siswa_id, sesi_id).decode()

    assert 'name="aksi" value="simpan"' in halaman
    assert "Simpan sementara" in halaman
    assert 'name="aksi" value="selesai"' in halaman
    assert "Selesai &amp; kirim" in halaman
    assert "aksi.type = 'hidden'; aksi.name = pemicu.name; aksi.value = pemicu.value" in halaman


def test_semua_jawaban_terisi_belum_selesai_bila_hanya_disimpan(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        data = {
            f"jwb_{b['sesi_soal_id']}": "1"
            for b in database.isi_sesi(kon, sesi_id)
        }
    data["aksi"] = "simpan"

    kode, isi, _ = s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID), data=data,
    )

    assert kode == 200
    assert "Tersimpan" in isi
    assert "Simpan sementara" in isi
    with s.buka() as kon:
        assert kon.execute(
            "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,),
        ).fetchone()["selesai"] is None


def test_kirim_final_boleh_menyisakan_soal_kosong_dan_mengunci_sesi(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        ssid = _field_pertama(kon, sesi_id)

    kode, isi, _ = s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "24", "aksi": "selesai"},
    )

    assert kode == 200
    assert "Selesai! Latihanmu sudah dikirim." in isi
    assert "Semua jawabanmu" not in isi
    with s.buka() as kon:
        selesai = kon.execute(
            "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,),
        ).fetchone()["selesai"]
        jumlah = kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0]
    assert selesai is not None
    assert jumlah == 1

    kode, isi, _ = s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
    )
    assert kode == 200
    assert "Jawabanmu sudah dikirim" in isi
    assert 'name="jwb_' not in isi


def test_kirim_final_boleh_semua_soal_kosong(server):
    s, _, sesi_id = server

    kode, isi, _ = s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={"aksi": "selesai"},
    )

    assert kode == 200
    assert "Selesai! Latihanmu sudah dikirim." in isi
    assert "Semua jawabanmu" not in isi
    with s.buka() as kon:
        baris = kon.execute(
            "SELECT mulai, selesai FROM sesi WHERE id = ?", (sesi_id,),
        ).fetchone()
        assert baris["mulai"] is not None
        assert baris["selesai"] is not None
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_post_setelah_kirim_final_tidak_mengubah_jawaban(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        ssid = _field_pertama(kon, sesi_id)
    s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "24", "aksi": "selesai"},
    )

    kode, _, _ = s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "DIUBAH", "aksi": "simpan"},
    )

    assert kode == 409
    with s.buka() as kon:
        jawaban = kon.execute(
            "SELECT jawaban FROM jawaban WHERE sesi_soal_id = ?", (ssid,),
        ).fetchone()["jawaban"]
    assert jawaban == "24"


def test_simpan_sementara_tidak_mendiagnosis_atau_masuk_laporan(server):
    s, siswa_id, sesi_id = server
    with s.buka() as kon:
        ssid = _field_pertama(kon, sesi_id)

    s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "24", "aksi": "simpan"},
    )

    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM diagnosis").fetchone()[0] == 0
        assert database.ringkasan(kon, siswa_id) == []
        assert database.sasaran_remedial(kon, siswa_id) == []
    kode, isi, _ = s.minta(f"/anak/{siswa_id}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "1 dari 3 terisi" in isi
    assert "Benar 1/" not in isi
    assert "Benar —" not in isi


def test_simpan_sementara_bisa_mengosongkan_jawaban_lama(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        ssid = _field_pertama(kon, sesi_id)
    s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "24", "aksi": "simpan"},
    )

    s.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "", f"cara_{ssid}": "", "aksi": "simpan"},
    )

    with s.buka() as kon:
        assert kon.execute(
            "SELECT COUNT(*) FROM jawaban WHERE sesi_soal_id = ?", (ssid,),
        ).fetchone()[0] == 0


def test_post_sesi_bukan_milik_murid_memakai_404_seragam(server):
    s, _, _ = server
    with s.buka() as kon:
        siswa_lain = database.tambah_siswa(kon, "Anak lain", pemilik="guru")
        sesi_lain = database.buat_sesi(kon, siswa_lain, seed=19, jumlah_soal=1)
        ssid = _field_pertama(kon, sesi_lain)

    kode, isi, _ = s.minta(
        f"/murid/kerjakan/{sesi_lain}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "disusupkan", "aksi": "selesai"},
    )

    assert kode == 404
    assert "Halaman tidak ada" in isi
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_guru_sebelum_kirim_hanya_melihat_pratinjau_soal_dan_kunci(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=2)
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    badan = halaman.split("</style>", 1)[-1]
    assert "Menunggu anak" in badan
    assert '>Soal &amp; kunci</a>' in badan
    assert '>Koreksi</a>' not in badan
    assert "Kunci:" in badan
    assert "Jawaban anak" not in badan
    assert 'name="kode_' not in badan
    assert 'name="cara_' not in badan
    assert "Simpan koreksi" not in badan


def test_guru_saat_dikerjakan_melihat_progres_tanpa_jawaban_sementara(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=3)
        ssid = _field_pertama(kon, sesi_id)
        database.simpan_jawaban(kon, ssid, jawaban="rahasia-sementara")
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    badan = halaman.split("</style>", 1)[-1]
    assert "Sedang dikerjakan" in badan
    assert "Terisi 1 dari 3" in badan
    assert "rahasia-sementara" not in badan
    assert "Kunci:" in badan


def test_guru_setelah_kirim_mendapat_form_simpan_koreksi(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=7, jumlah_soal=1)
        ssid = _field_pertama(kon, sesi_id)
        database.simpan_jawaban(kon, ssid, jawaban="24", cara="aku hitung")
        database.tandai_selesai(kon, sesi_id)
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    badan = halaman.split("</style>", 1)[-1]
    assert "Periksa catatan anak dan usulan mesin" in badan
    assert "Konfirmasi hasil" in badan
    assert ">Simpan koreksi</button>" not in badan
    assert 'name="jwb_' in badan
    assert 'name="kode_' in badan


def test_post_koreksi_sebelum_anak_mengirim_ditolak_tanpa_efek(server):
    s, _, sesi_id = server
    with s.buka() as kon:
        ssid = _field_pertama(kon, sesi_id)

    kode, _, _ = s.minta(
        f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU),
        data={f"jwb_{ssid}": "jawaban guru"},
    )

    assert kode == 409
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0


def test_koreksi_latihan_cepat_tanpa_caraku_dan_submit_tetap_benar(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=7, mode="drill", jumlah_soal=1,
        )
        baris = database.isi_sesi(kon, sesi_id)[0]
        database.simpan_jawaban(kon, baris["sesi_soal_id"], jawaban=baris["kunci"])
        database.tandai_selesai(kon, sesi_id)
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
        teacher_pages.simpan_sesi(
            kon, sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": baris["kunci"],
                f"kode_{baris['sesi_soal_id']}": "N",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[0]

    badan = halaman.split("</style>", 1)[-1]
    assert "Caraku" not in badan
    assert 'name="cara_' not in badan
    assert '<option value="N"' not in badan
    assert hasil["benar"] == 1
    assert hasil["kode_final"] is None


def test_halaman_anak_memakai_ikon_share_inline_tanpa_navigasi_baru(server):
    s, siswa_id, sesi_id = server

    kode, isi, _ = s.minta(f"/anak/{siswa_id}", auth=("guru", SANDI_GURU))

    assert kode == 200
    assert f'data-bagikan-url="/sesi/{sesi_id}/bagikan"' in isi
    assert 'aria-label="Bagikan sesi ke anak"' in isi
    assert 'class="material-symbols-outlined">share</span>' in isi
    assert '<span class="kabar-bagikan-st" aria-live="polite"></span>' in isi
    assert "x.closest('.blok-bagikan-st').querySelector('.kabar-bagikan-st')" in isi
    assert "k.textContent='Tautan tersalin dan berlaku 7 hari.'" in isi
    assert "if(e.name==='AbortError'){k.textContent='';return;}" in isi
    assert "navigator.share" in isi
    assert "navigator.clipboard.writeText" in isi
    assert "window.prompt('Salin tautan ini:'" in isi
    assert "Membuat tautan baru akan menonaktifkan tautan sebelumnya" in isi
    assert "if(x.dataset.tautan){await bagikan(x.dataset.tautan,k);return;}" in isi
    assert "window.location" not in isi
    assert f"width: {style_stitch.T.TARGET_SENTUH}" in style_stitch.GAYA_STITCH
    assert f"height: {style_stitch.T.TARGET_SENTUH}" in style_stitch.GAYA_STITCH


def test_endpoint_bagikan_inline_mengembalikan_json_no_store(server):
    s, _, sesi_id = server

    kode, isi, header = s.minta(
        f"/sesi/{sesi_id}/bagikan", auth=("guru", SANDI_GURU), data={},
        headers={"X-Requested-With": "fetch"},
    )

    payload = json.loads(isi)
    assert kode == 200
    assert payload["tautan"].startswith("https://jagomat.id/mulai/")
    assert header["Content-Type"].startswith("application/json")
    assert header["Cache-Control"] == "no-store"


def test_countdown_mengurangi_waktu_yang_sudah_berjalan(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=7, mode="drill", timer_mode="sesi",
            durasi_menit=10, jumlah_soal=1,
        )
        kon.execute(
            "UPDATE sesi SET mulai = datetime('now', '+7 hours', '-2 minutes') "
            "WHERE id = ?", (sesi_id,),
        )
        halaman = student_pages.halaman_kerja_baru(kon, siswa_id, sesi_id).decode()

    cocok = re.search(r"var DETIK_LALU = (\d+);", halaman)
    assert cocok
    assert 115 <= int(cocok.group(1)) <= 125
    assert "var mulai = Date.now() - DETIK_LALU * 1000" in halaman
    assert 'a.name = "aksi"; a.value = "selesai"' in halaman
