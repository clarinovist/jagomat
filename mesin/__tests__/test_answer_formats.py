"""Regresi format jawaban melalui jalur guru, murid, dan lampiran sintetis."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import attachments
import database
import reports
import student_pages
import students
import teacher_pages
from assistant_inline import DrafButir, DrafKoreksi
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji
from topic_advanced_arithmetic import satuan_konversi
from topic_number_patterns import deret_aritmetika


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "format-sintetis.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _buat_sesi(kon, jenis, mode="diagnostik", nama="Peserta Sintetis"):
    if jenis == "daftar":
        soal = deret_aritmetika(6, 12, 4, 3)
        topik = "pola-bilangan"
    else:
        soal = satuan_konversi("m_ke_km", 71000)
        topik = "aritmatika-lanjut"
    soal = replace(soal, level="P5")
    siswa = database.tambah_siswa(kon, nama, pemilik="guru")
    sesi = database.buat_sesi_dari_urutan(
        kon, siswa, 1, (soal.template_id,), topik=topik, level="P5",
        mode=mode, soal_terpilih=(soal,),
    )
    ssid = database.isi_sesi(kon, sesi)[0]["sesi_soal_id"]
    return siswa, sesi, ssid


@pytest.mark.parametrize("jenis,jawaban", [("daftar", "54,66,78"), ("satuan", "71km")])
@pytest.mark.parametrize("mode", ["diagnostik", "drill"])
def test_format_benar_dari_murid_sampai_hasil(db, jenis, jawaban, mode):
    with database.buka(db) as kon:
        siswa, sesi, ssid = _buat_sesi(kon, jenis, mode)
        assert students.simpan_jawaban_murid(kon, siswa, sesi, {
            f"jwb_{ssid}": jawaban,
            f"cara_{ssid}": "Saya hitung sesuai langkah" if mode == "diagnostik" else "",
        }) == 1
        assert reports.diagnosa_murid(kon, sesi) == 1
        baris = database.isi_sesi(kon, sesi)[0]
        assert baris["jawaban"] == jawaban
        assert baris["benar"] == 1
        assert baris["kode_final"] is None
        assert baris["manual"] == 0
        assert students.hasil_murid(kon, siswa, sesi) is None
        database.tandai_selesai(kon, sesi)
        kon.execute("UPDATE sesi SET direview = datetime('now') WHERE id = ?", (sesi,))
        hasil = students.hasil_murid(kon, siswa, sesi)
        assert hasil["soal"][0]["benar"] is True
        html = student_pages.halaman_hasil_murid(kon, siswa, sesi).decode()
        assert '>Benar</span>' in html
        assert '>Belum tepat</span>' not in html
        assert f'<b>{jawaban}</b>' in html


@pytest.mark.parametrize("jenis,jawaban", [("daftar", "54,66,78"), ("satuan", "71km")])
def test_usulan_guru_dan_simpan_konsisten(db, jenis, jawaban):
    with database.buka(db) as kon:
        _, sesi, ssid = _buat_sesi(kon, jenis)
        database.tandai_selesai(kon, sesi)
        draf = DrafKoreksi(((ssid, DrafButir(jawaban, "", "Saya hitung", "", False, False)),), False)
        html = teacher_pages.halaman_sesi_stitch(kon, sesi, draf_koreksi=draf).decode()
        assert '<span class="koreksi-status-label-st">Tepat</span>' in html
        assert database.isi_sesi(kon, sesi)[0]["jawaban_id"] is None
        teacher_pages.simpan_sesi(kon, sesi, {
            f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung",
        })
        b = database.isi_sesi(kon, sesi)[0]
        assert b["benar"] == 1 and b["manual"] == 0 and b["jawaban"] == jawaban


@pytest.mark.parametrize("jenis,jawaban", [("daftar", "54,66,78"), ("satuan", "71km")])
def test_lampiran_terkonfirmasi_memakai_pemeriksa_yang_sama(db, jenis, jawaban):
    with database.buka(db) as kon:
        _, sesi, ssid = _buat_sesi(kon, jenis)
        lid = database.simpan_lampiran(kon, sesi, "lembar-sintetis.jpg")
        jumlah, _ = attachments.terapkan(kon, lid, {
            f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung",
        })
        assert jumlah == 1
        b = database.isi_sesi(kon, sesi)[0]
        assert b["benar"] == 1 and b["jawaban"] == jawaban


@pytest.mark.parametrize("jenis,jawaban", [("daftar", "54,66,78"), ("satuan", "71km")])
@pytest.mark.parametrize("kode,benar", [("H", 0), ("benar", 1)])
def test_override_guru_tetap_berlaku_dan_usulan_memakai_konteks(db, jenis, jawaban, kode, benar):
    with database.buka(db) as kon:
        siswa, sesi, ssid = _buat_sesi(kon, jenis)
        data = {f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung"}
        teacher_pages.simpan_sesi(kon, sesi, dict(data, **{f"kode_{ssid}": kode}))
        assert students.simpan_jawaban_murid(kon, siswa, sesi, data) == 1
        assert reports.diagnosa_murid(kon, sesi) == 0
        b = database.isi_sesi(kon, sesi)[0]
        assert b["benar"] == benar and b["manual"] == 1
        assert b["kode_final"] == (None if benar else kode)
        assert b["alasan"] == "jawaban benar"
        assert b["jawaban"] == jawaban


@pytest.mark.parametrize("jenis,jawaban", [("daftar", "54,66,78"), ("satuan", "71km")])
def test_hasil_lama_tidak_dinilai_ulang_saat_get_dan_noop(db, jenis, jawaban):
    with database.buka(db) as kon:
        siswa, sesi, ssid = _buat_sesi(kon, jenis)
        jid = database.simpan_jawaban(kon, ssid, jawaban, "Saya hitung")
        database.simpan_diagnosis(kon, jid, False, "H", "H", alasan="Hasil warisan", manual=False)
        database.tandai_selesai(kon, sesi)
        kon.execute("UPDATE sesi SET direview = datetime('now') WHERE id = ?", (sesi,))
        lama = database.konfirmasi_hasil(kon, sesi, "guru")
        sebelum = tuple(kon.iterdump())
        bukti = database.muat_bukti_siklus(kon, siswa)
        html = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert '<span class="koreksi-status-label-st">Salah hitung</span>' in html
        assert '>Belum tepat</span>' in student_pages.halaman_hasil_murid(kon, siswa, sesi).decode()
        teacher_pages.simpan_sesi(kon, sesi, {
            f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung",
        })
        assert tuple(kon.iterdump()) == sebelum
        assert database.muat_bukti_siklus(kon, siswa) == bukti
        snapshot = tuple(kon.execute("SELECT * FROM snapshot_outcome WHERE konfirmasi_id = ?", (lama,)).fetchone())
        # Koreksi eksplisit memakai jalur guru, bukan backfill otomatis.
        teacher_pages.simpan_sesi(kon, sesi, {
            f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung", f"kode_{ssid}": "benar",
        })
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)).fetchone()[0] is None
        assert tuple(kon.execute("SELECT * FROM snapshot_outcome WHERE konfirmasi_id = ?", (lama,)).fetchone()) == snapshot
        baru = database.konfirmasi_hasil(kon, sesi, "guru")
        assert baru != lama
        assert kon.execute("SELECT COUNT(*) FROM snapshot_outcome").fetchone()[0] == 2
        assert kon.execute("SELECT benar FROM snapshot_outcome WHERE konfirmasi_id = ?", (baru,)).fetchone()[0] == 1


@pytest.mark.parametrize("jenis,jawaban,benar", [
    ("daftar", "54,66,78", True), ("satuan", "71km", True),
    ("daftar", "78,66,54", False), ("satuan", "71 m", False),
])
def test_http_murid_kirim_dan_halaman_hasil(server, jenis, jawaban, benar):
    with server.buka() as kon:
        _, sesi, ssid = _buat_sesi(kon, jenis, nama="feby")
    status, _, _ = server.minta(
        f"/murid/kerjakan/{sesi}", auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": jawaban, f"cara_{ssid}": "Saya hitung", "aksi": "selesai"},
    )
    assert status == 200
    status, _, _ = server.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert status == 200
    status, isi, _ = server.minta(f"/murid/hasil/{sesi}", auth=("feby", SANDI_MURID))
    assert status == 200
    assert ('>Benar</span>' in isi) == benar
    assert ('>Belum tepat</span>' in isi) != benar
    with server.buka() as kon:
        b = database.isi_sesi(kon, sesi)[0]
        assert bool(b["benar"]) == benar and b["jawaban"] == jawaban
