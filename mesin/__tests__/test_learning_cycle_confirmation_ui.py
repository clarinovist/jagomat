"""Kontrak UI koreksi dan konfirmasi hasil siklus belajar Fase 3."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    jalur = tmp_path / "uji.db"
    database.siapkan(jalur)
    return jalur


def _sesi_selesai(kon, *, seed=71):
    siswa_id = database.tambah_siswa(kon, f"Anak {seed}", "P3", pemilik="guru")
    sesi_id = database.buat_sesi(
        kon, siswa_id, seed=seed, level="P3", jumlah_soal=1
    )
    butir = database.isi_sesi(kon, sesi_id)[0]
    database.tandai_selesai(kon, sesi_id)
    return siswa_id, sesi_id, butir


def _isi_benar(kon, butir):
    jawaban_id = database.simpan_jawaban(
        kon,
        butir["sesi_soal_id"],
        jawaban=butir["kunci"],
        cara="cara anak",
    )
    database.simpan_diagnosis(
        kon,
        jawaban_id,
        benar=True,
        kode_usulan=None,
        kode_final=None,
        alasan="jawaban benar",
    )
    return jawaban_id


def _badan(halaman):
    return halaman.decode().split("</style>", 1)[-1]


def test_pemahaman_dan_status_dilewati_dipulihkan_dari_snapshot_terakhir(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon)
        sid = int(butir["sesi_soal_id"])
        database.konfirmasi_hasil(
            kon,
            sesi_id,
            guru="guru",
            dilewati={sid},
            cek_pemahaman={sid: "ragu"},
        )

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    pilihan = re.search(
        rf'name="cek_pemahaman_{sid}"[^>]*>(.*?)</select>', halaman, re.S
    )
    centang = re.search(rf'<input[^>]+name="dilewati_{sid}"[^>]*>', halaman, re.S)
    assert pilihan
    assert '<option value="ragu" selected>Masih ragu</option>' in pilihan.group(1)
    assert centang and "checked" in centang.group(0)
    assert "Lewati butir ini dari hasil" in halaman


def test_semua_butir_menyediakan_checkbox_dilewati(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=72)
        sid = int(butir["sesi_soal_id"])
        _isi_benar(kon, butir)

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    assert f'name="dilewati_{sid}"' in halaman
    assert f'id="lewati-{sid}"' in halaman


def test_tombol_konfirmasi_tetap_ada_setelah_dikonfirmasi_dan_setelah_koreksi(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=73)
        jawaban_id = _isi_benar(kon, butir)
        database.konfirmasi_hasil(
            kon,
            sesi_id,
            guru="guru",
            cek_pemahaman={int(butir["sesi_soal_id"]): "bisa_menjelaskan"},
        )
        halaman_terkonfirmasi = _badan(
            teacher_pages.halaman_sesi_stitch(kon, sesi_id)
        )

        database.simpan_diagnosis(
            kon,
            jawaban_id,
            benar=False,
            kode_usulan="H",
            kode_final="H",
            alasan="dikoreksi guru",
            manual=True,
        )
        halaman_setelah_koreksi = _badan(
            teacher_pages.halaman_sesi_stitch(kon, sesi_id)
        )

    assert halaman_terkonfirmasi.count(">Konfirmasi ulang</button>") == 1
    assert halaman_setelah_koreksi.count(">Konfirmasi ulang</button>") == 1
    assert 'formaction="/sesi/{}/konfirmasi"'.format(sesi_id) in halaman_setelah_koreksi


def test_opt_in_pemetaan_menjelaskan_status_aktif(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=74)
        _isi_benar(kon, butir)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        kon.execute(
            """INSERT INTO kejadian_belajar
                   (siswa_id, sesi_id, konfirmasi_id, jenis, data)
               SELECT siswa_id, id, ?, 'sertakan_pemetaan', '{}'
               FROM sesi WHERE id = ?""",
            (konfirmasi_id, sesi_id),
        )

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    opt_in = re.search(
        r'<input[^>]+name="sertakan_pemetaan"[^>]*>', halaman, re.S
    )
    assert opt_in and "checked" in opt_in.group(0)
    assert "Aktif — hasil terkonfirmasi ini ikut pemetaan." in halaman


def test_sesi_dibatalkan_tidak_menawarkan_konfirmasi_atau_penghapusan(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=75)
        _isi_benar(kon, butir)
        kon.execute(
            "UPDATE sesi SET dibatalkan = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    assert "Sesi dibatalkan" in halaman
    assert "Konfirmasi hasil" not in halaman
    assert "Konfirmasi ulang" not in halaman
    assert "Hapus sesi" not in halaman
    assert "Batalkan sesi" not in halaman


def test_sesi_manual_berbukti_dibatalkan_bukan_dihapus(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=76)
        _isi_benar(kon, butir)
        database.konfirmasi_hasil(kon, sesi_id, guru="guru")

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    assert f'action="/sesi/{sesi_id}/batalkan"' in halaman
    assert "Batalkan sesi" in halaman
    assert f'action="/sesi/{sesi_id}/hapus"' not in halaman
    assert "Hapus sesi" not in halaman


def test_zona_pembatalan_menjelaskan_histori_dan_meminta_konfirmasi(db):
    with database.buka(db) as kon:
        siswa_id, sesi_id, _ = _sesi_selesai(kon, seed=77)
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        kon.execute(
            "UPDATE sesi SET tujuan = 'pemetaan', putaran_id = ? WHERE id = ?",
            (putaran_id, sesi_id),
        )

        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    assert "Pembatalan menjaga histori dan bukti sesi." in halaman
    assert 'class="form-pembatalan-st"' in halaman
    formulir = halaman.split('class="form-pembatalan-st"', 1)[1].split("</form>", 1)[0]
    assert formulir.index('for="alasan-batal"') < formulir.index('id="alasan-batal"')
    assert '<span>(opsional)</span>' in formulir
    assert "style=" not in formulir
    assert "hapus tidak bisa dibatalkan" not in halaman
    assert (
        "Batalkan sesi ini? Sesi dan bukti tetap tersimpan dalam histori, "
        "tetapi tidak lagi aktif dalam siklus belajar."
    ) in halaman
    assert "onsubmit=\"return confirm(" in halaman


def test_tombol_koreksi_dan_konfirmasi_punya_jarak_dan_hierarki():
    from style_stitch import CSS_SESI
    import design_tokens as T

    blok = CSS_SESI.split(".koreksi-simpan-st {", 1)[1].split("}", 1)[0]
    assert "display: grid" in blok
    assert f"gap: {T.SP_2}" in blok
    assert ".koreksi-simpan-st:has(button[formaction]) button:not([formaction])" in CSS_SESI


def test_form_pembatalan_bertumpuk_dengan_input_lebar_dan_tombol_ringkas():
    from style_stitch import GAYA_STITCH
    import design_tokens as T

    blok = GAYA_STITCH.split(".koreksi-editorial-st .form-pembatalan-st {", 1)[1].split("}", 1)[0]
    assert "display: grid" in blok
    assert "grid-template-columns: minmax(0, 1fr)" in blok
    input_css = GAYA_STITCH.split(".koreksi-editorial-st .form-pembatalan-st input {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in input_css
    assert f"min-height: {T.TARGET_SENTUH}" in input_css
    tombol = GAYA_STITCH.split(".koreksi-editorial-st .form-pembatalan-st .tombol-kecil-st {", 1)[1].split("}", 1)[0]
    assert "width: auto" in tombol


def test_marker_penjelasan_koreksi_lama_tetap_ada(db):
    with database.buka(db) as kon:
        _, sesi_id, butir = _sesi_selesai(kon, seed=78)
        _isi_benar(kon, butir)
        halaman = _badan(teacher_pages.halaman_sesi_stitch(kon, sesi_id))

    assert "Periksa catatan anak dan usulan mesin" in halaman
    assert "menyimpan seluruh isian sekaligus mengesahkan bukti belajar" in halaman
    assert ">Simpan koreksi</button>" not in halaman
