"""Regresi layout halaman koreksi sesi guru.

Layout aktif memasangkan jawaban singkat dengan Caraku; penilaian terpisah
pada details. Test mengunci DOM pemakai CSS, proporsi, kepadatan, serta
ringkasan status agar tidak sekadar mempertahankan selector yang sudah mati.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import style_stitch  # noqa: E402
import teacher_pages  # noqa: E402


def _blok(css: str, selektor: str) -> str:
    cocok = re.search(
        r"^" + re.escape(selektor) + r"\s*\{(.*?)\}", css, re.S | re.M
    )
    assert cocok, f"selektor {selektor} tidak ditemukan"
    return cocok.group(1)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "uji.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    return jalur


def _buat_sesi(db, seed=7):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Claudia", tingkat="P3")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=seed, level="P3", topik="statistika"
        )
        database.tandai_selesai(kon, sesi_id)
    return sesi_id


def test_kolom_jawaban_ringkas_dan_caraku_memakai_grid_aktif(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    badan = halaman.split("</style>", 1)[-1]
    bukti = re.findall(r'<div class="koreksi-bukti-st">(.*?)</div>\s*</div>', badan, re.S)
    assert bukti, "grid harus dipakai kartu koreksi, bukan CSS tanpa elemen"
    for isi in bukti:
        assert 'class="koreksi-input-st"' in isi
        assert 'class="koreksi-textarea-st"' in isi
        assert 'name="kode_' not in isi
    assert 'class="koreksi-opsi-st koreksi-penilaian-st"' in badan
    assert "grid-template-columns: minmax(8rem, 10rem) minmax(0, 1fr)" in style_stitch.CSS_SESI


def test_form_tetap_satu_kolom_sebelum_breakpoint_desktop():
    css = style_stitch.CSS_SESI
    dasar = _blok(css, ".koreksi-bukti-st")
    assert "grid-template-columns: minmax(0, 1fr)" in dasar
    bagian_grid = css.split("/* Hierarki koreksi:", 1)[1].split(
        ".koreksi-catatan-st", 1
    )[0]
    assert "@media (min-width: 40rem)" in bagian_grid
    assert "@media (min-width: 30rem)" not in bagian_grid


def test_kartu_dan_caraku_lebih_padat_tanpa_mengecilkan_target_sentuh():
    css = style_stitch.CSS_SESI
    kartu = _blok(css, ".koreksi-kartu-st")
    isi = _blok(css, ".koreksi-isi-st")
    textarea = _blok(css, ".koreksi-textarea-st")
    kontrol = _blok(css, ".koreksi-input-st")

    assert "gap: 1rem" in kartu
    assert "margin-bottom: 1rem" in kartu
    assert "gap: 0.75rem" in isi
    assert "min-height: 56px" in textarea
    assert f"min-height: {style_stitch.T.TARGET_SENTUH}" in kontrol


def test_label_kode_ringkas_dan_nama_template_ramah(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    badan = halaman.split("</style>", 1)[-1]
    assert "Kode (kosong = usulan mesin)" not in badan
    assert "Penilaian yang dipakai" in badan
    assert "Usulan mesin:" in badan
    assert "kosongkan = pakai usulan mesin" not in badan
    assert "median_modus" not in badan
    assert "Median &amp; modus" in badan


def test_pembahasan_memakai_kelas_bukan_gaya_inline(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    assert '<div class="pembahasan-soal-st">' in halaman
    pembahasan = _blok(style_stitch.CSS_SESI, ".pembahasan-soal-st")
    assert style_stitch.T.LATAR_SEKUNDER_LEMBUT in pembahasan
    assert style_stitch.T.AKSEN_MURID_UTAMA in pembahasan


def test_alasan_mesin_benar_tidak_mengulang_status_benar(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": baris["kunci"],
                f"cara_{baris['sesi_soal_id']}": "coretan",
            },
        )
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    badan = halaman.split("</style>", 1)[-1]
    assert "Mesin: jawaban benar" not in badan
    assert "BENAR" in badan


def test_alasan_mesin_benar_tetap_tampil_saat_guru_mengoreksi_manual(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": baris["kunci"],
                f"cara_{baris['sesi_soal_id']}": "coretan",
                f"kode_{baris['sesi_soal_id']}": "H",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[0]
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    assert hasil["manual"]
    assert hasil["alasan"] == "jawaban benar"
    assert '<b>Mesin:</b> jawaban benar' in halaman


def test_alasan_mesin_tetap_tampil_saat_guru_menandai_benar_manual(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": "jawaban lain",
                f"cara_{baris['sesi_soal_id']}": "cara alternatif",
                f"kode_{baris['sesi_soal_id']}": "benar",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[0]
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    assert hasil["benar"]
    assert hasil["alasan"] != "jawaban benar"
    assert f'<b>Mesin:</b> {hasil["alasan"]}' in halaman


def test_alasan_mesin_yang_membantu_tetap_tampil(db):
    sesi_id = _buat_sesi(db, seed=11)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        malrule = database.malrule_soal(kon, baris["soal_id"])[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": malrule["jawaban"],
                f"cara_{baris['sesi_soal_id']}": "coretan",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[0]
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    assert hasil["alasan"]
    assert f'<b>Mesin:</b> {hasil["alasan"]}' in halaman


def test_status_menyatu_dengan_nomor_dan_jenis_soal(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": baris["kunci"],
                f"kode_{baris['sesi_soal_id']}": "benar",
            },
        )
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    kepala = re.search(r'<div class="koreksi-kepala-st">(.*?)</div>', halaman, re.S)
    assert kepala
    assert "koreksi-nomor-st" in kepala.group(1)
    assert "koreksi-tipe-st" in kepala.group(1)
    assert "koreksi-status-st" in kepala.group(1)
    assert '<span class="kode benar">BENAR</span>' in kepala.group(1)
    assert '<span class="koreksi-status-label-st">Tepat</span>' in kepala.group(1)
    assert f"background: {style_stitch.T.KODE_BENAR_BG}" in _blok(
        style_stitch.CSS_SESI, ".koreksi-status-st.benar"
    )
    assert f"color: {style_stitch.T.KODE_BENAR_TEKS}" in _blok(
        style_stitch.CSS_SESI, ".koreksi-status-st.benar"
    )
    assert f"color: {style_stitch.T.TEKS_JUDUL}" in _blok(
        style_stitch.CSS_SESI, ".koreksi-status-st.B"
    )
    assert f"color: {style_stitch.T.TEKS_JUDUL}" in _blok(
        style_stitch.CSS_SESI, ".koreksi-status-st.T"
    )
    assert "display: none" in _blok(
        style_stitch.CSS_SESI, ".koreksi-status-st .kode"
    )
    assert 'class="koreksi-bulat-st' not in halaman


def test_kartu_tidak_memakai_kolom_status_kanan(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    kartu = _blok(style_stitch.CSS_SESI, ".koreksi-kartu-st")
    status = _blok(style_stitch.CSS_SESI, ".koreksi-status-st")
    assert "flex-direction: row" not in kartu
    assert "margin-left: auto" in status
    assert ".koreksi-kartu-st .koreksi-status-st" not in style_stitch.CSS_SESI
    assert "width: 6rem" not in style_stitch.CSS_SESI


def test_mintanya_apa_bukan_input_guru_dan_nilai_anak_tetap_terjaga(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        database.simpan_jawaban(
            kon,
            baris["sesi_soal_id"],
            restatement="Yang dicari adalah banyak data",
        )
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{baris['sesi_soal_id']}": "jawaban baru",
                f"restate_{baris['sesi_soal_id']}": "nilai manipulasi",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[0]

    sid = baris["sesi_soal_id"]
    assert "Kotak &quot;mintanya apa&quot;" not in halaman
    assert '<span class="info-anak-label-st">Dari anak:</span>' in halaman
    assert "Yang dicari adalah banyak data" in halaman
    assert f'name="restate_{sid}"' not in halaman
    assert hasil["restatement"] == "Yang dicari adalah banyak data"


def test_belum_pernah_hanya_satu_kontrol_dari_anak(db):
    sesi_id = _buat_sesi(db)
    with database.buka(db) as kon:
        baris = database.isi_sesi(kon, sesi_id)[0]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {f"belum_{baris['sesi_soal_id']}": "on"},
        )
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

    sid = baris["sesi_soal_id"]
    assert '<option value="T"' not in halaman
    assert halaman.count(f'name="belum_{sid}"') == 1
    assert '<span class="info-anak-label-st">Dari anak:</span>' in halaman
    assert "Belum pernah melihat soal seperti ini" in halaman
    assert f'name="belum_{sid}"' in halaman
    assert "checked" in halaman.split(f'name="belum_{sid}"', 1)[1].split(">", 1)[0]
