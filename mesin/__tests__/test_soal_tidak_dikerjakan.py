"""Soal "tidak dikerjakan" (keputusan pemilik K5, 6 Nov 2026).

Kertas: guru mencentang "Anak tidak mengerjakan soal ini" di halaman isi dari lembar,
sehingga sesi dengan soal kosong bisa selesai (sebelumnya jalan buntu). Soal kosong
tidak menulis baris jawaban, sama dengan jalur tautan. Tinjauan: soal tanpa jawaban
bawaan tercentang "dilewati" (bukan benar, bukan salah, bukan bukti) selama guru belum
menyimpan keputusan lain; konfirmasi tetap tombol guru dan server tidak berubah.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import attachments  # noqa: E402
import database  # noqa: E402
import learning_cycle_service  # noqa: E402
import teacher_review_service  # noqa: E402
import teacher_session_pages  # noqa: E402

LABEL_KOSONG = "Anak tidak mengerjakan soal ini"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "kosong.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _lampiran(kon):
    anak = database.tambah_siswa(kon, "Anak Kosong", pemilik="guru")
    sesi = database.buat_sesi(kon, anak, seed=7)
    return sesi, database.simpan_lampiran(kon, sesi, "l.jpg", hasil_json="")


def _isian(butir, kosong=(), salah=None):
    salah = salah or {}
    data = {}
    for b in butir:
        sid = b["sesi_soal_id"]
        data[f"jwb_{sid}"] = ""
        data[f"cara_{sid}"] = ""
        if sid in kosong:
            data[f"kosong_{sid}"] = "on"
        elif sid in salah:
            data[f"jwb_{sid}"], data[f"cara_{sid}"] = salah[sid]
        else:
            data[f"benar_{sid}"] = "on"
    return data


def _jumlah_jawaban(kon, sesi):
    return kon.execute(
        "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=?",
        (sesi,)).fetchone()[0]


def _selesai(kon, sesi):
    return kon.execute("SELECT selesai FROM sesi WHERE id=?", (sesi,)).fetchone()[0] is not None


def _dilewati_bawaan(html):
    return {int(s) for s in re.findall(r'name="dilewati_(\d+)" value="1" checked', html)}


def _angka_wajib(html):
    cocok = re.search(r"(\d+) soal wajib Anda putuskan", html)
    return int(cocok.group(1)) if cocok else 0


def test_halaman_isi_menawarkan_centang_tidak_dikerjakan_per_soal(db):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    for b in butir:
        assert f'name="kosong_{b["sesi_soal_id"]}"' in html
    assert html.count('class="centang centang-kosong"') == len(butir)
    assert LABEL_KOSONG in html
    assert "Sesi ditandai selesai setelah semua soal terisi." not in html


def test_satu_soal_tidak_dikerjakan_membuat_sesi_kertas_selesai(db):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        kosong = butir[7]["sesi_soal_id"]
        attachments.terapkan(kon, lid, _isian(butir, kosong={kosong}))
        assert _selesai(kon, sesi)
        assert _jumlah_jawaban(kon, sesi) == len(butir) - 1
        assert kon.execute("SELECT 1 FROM jawaban WHERE sesi_soal_id=?", (kosong,)).fetchone() is None
        assert kon.execute("SELECT sumber FROM pengiriman_sesi WHERE sesi_id=?", (sesi,)).fetchone()[0] == "foto"


def test_soal_kosong_tanpa_centang_tetap_tidak_selesai(db):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        data = _isian(butir)
        del data[f"benar_{butir[3]['sesi_soal_id']}"]
        attachments.terapkan(kon, lid, data)
        assert not _selesai(kon, sesi)


@pytest.mark.parametrize("isian", ["jwb", "cara", "benar", "blm"])
def test_centang_kosong_bersama_isian_ditolak_utuh(db, isian):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        kon.commit()
        sid = butir[2]["sesi_soal_id"]
        data = _isian(butir, kosong={sid})
        data[f"{isian}_{sid}"] = {"jwb": "12", "cara": "aku hitung"}.get(isian, "on")
        with pytest.raises(ValueError, match="tidak dikerjakan"):
            attachments.terapkan(kon, lid, data)
        kon.rollback()
        assert _jumlah_jawaban(kon, sesi) == 0 and not _selesai(kon, sesi)


def test_centang_kosong_pada_soal_yang_sudah_berjawaban_ditolak(db):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        sid = butir[0]["sesi_soal_id"]
        database.simpan_jawaban(kon, sid, "5", "cara lama", "", False)
        kon.commit()
        with pytest.raises(ValueError, match="sudah punya jawaban"):
            attachments.terapkan(kon, lid, _isian(butir, kosong={sid}))
        kon.rollback()
        assert _jumlah_jawaban(kon, sesi) == 1 and not _selesai(kon, sesi)


def test_semua_soal_kosong_ditolak_dan_diarahkan_ke_batalkan(db):
    with database.buka(db) as kon:
        sesi, lid = _lampiran(kon)
        butir = database.isi_sesi(kon, sesi)
        kon.commit()
        semua = {b["sesi_soal_id"] for b in butir}
        with pytest.raises(ValueError, match="Batalkan sesi"):
            attachments.terapkan(kon, lid, _isian(butir, kosong=semua))
        kon.rollback()
        assert _jumlah_jawaban(kon, sesi) == 0 and not _selesai(kon, sesi)


def _sesi_dengan_satu_kosong(kon):
    sesi, lid = _lampiran(kon)
    butir = database.isi_sesi(kon, sesi)
    kosong = butir[7]["sesi_soal_id"]
    attachments.terapkan(kon, lid, _isian(butir, kosong={kosong}))
    kon.commit()
    return sesi, kosong


def test_tinjauan_soal_kosong_bawaan_dilewati_dan_bukan_wajib(db):
    with database.buka(db) as kon:
        sesi, kosong = _sesi_dengan_satu_kosong(kon)
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert _dilewati_bawaan(html) == {kosong}
        assert _angka_wajib(html) == 0
        assert LABEL_KOSONG in html
        # Server tidak berubah: tanpa centang dilewati, soal kosong tetap ditolak.
        with pytest.raises(learning_cycle_service.KonfirmasiBelumLengkap):
            learning_cycle_service.konfirmasi_dari_form(kon, sesi, "guru", {})
        kon.rollback()
        # Isian bawaan form (centang dilewati) lolos: UI 0 wajib = server menerima.
        data = {f"dilewati_{sid}": "1" for sid in _dilewati_bawaan(html)}
        learning_cycle_service.konfirmasi_dari_form(kon, sesi, "guru", data)
        baris = kon.execute(
            """SELECT so.dilewati, so.benar, so.kode_final FROM snapshot_outcome so
               JOIN konfirmasi_hasil k ON k.id = so.konfirmasi_id
               WHERE k.sesi_id=? AND so.sesi_soal_id=?""", (sesi, kosong)).fetchone()
    assert tuple(baris) == (1, None, None)


def test_bawaan_dilewati_tidak_menimpa_keputusan_guru_yang_tersimpan(db):
    with database.buka(db) as kon:
        sesi, kosong = _sesi_dengan_satu_kosong(kon)
        # Guru menyimpan tinjauan soal itu tanpa centang dilewati ("Sertakan kembali" + catatan).
        import review_store
        review_store.simpan(kon, sesi, {f"hadir_dilewati_{kosong}": "1",
                                        f"catatan_tinjauan_{kosong}": "anak bilang lupa waktu"}, "guru")
        kon.commit()
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert kosong not in _dilewati_bawaan(html)
        assert _angka_wajib(html) == 1
        # Draf konfirmasi gagal juga dihormati: tidak dicentang ulang diam-diam.
        with pytest.raises(learning_cycle_service.KonfirmasiBelumLengkap) as galat:
            learning_cycle_service.konfirmasi_dari_form(kon, sesi, "guru", {})
        kon.rollback()
        html = teacher_session_pages.halaman_sesi_stitch(
            kon, sesi, draf_koreksi=galat.value.draf, masalah_konfirmasi=galat.value.masalah).decode()
    assert kosong not in _dilewati_bawaan(html)


def test_tautan_soal_kosong_juga_bawaan_dilewati(db):
    """Jalur HP: anak mengosongkan satu soal lalu mengirim; soal itu bawaan dilewati."""
    import reports
    import student_submissions
    with database.buka(db) as kon:
        anak = database.tambah_siswa(kon, "Anak HP", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, seed=7)
        butir = database.isi_sesi(kon, sesi)
        kosong = butir[4]["sesi_soal_id"]
        for b in butir:
            if b["sesi_soal_id"] != kosong:
                database.simpan_jawaban(kon, b["sesi_soal_id"], b["kunci"], "aku hitung", "", False)
        student_submissions.arsipkan(kon, sesi, "tautan")
        reports.diagnosa_murid(kon, sesi)
        database.tandai_selesai(kon, sesi)
        kon.commit()
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
    assert _dilewati_bawaan(html) == {kosong}


def test_sesi_terkirim_tanpa_satu_jawaban_pun_tidak_diberi_bawaan_dilewati(db):
    """Anak menekan kirim tanpa mengisi apa pun: guru harus memutuskan (atau membatalkan),
    bukan mengonfirmasi sesi kosong dengan satu klik."""
    import student_submissions
    with database.buka(db) as kon:
        anak = database.tambah_siswa(kon, "Anak HP Kosong", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, seed=7)
        student_submissions.arsipkan(kon, sesi, "tautan")
        database.tandai_selesai(kon, sesi)
        kon.commit()
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        n = len(database.isi_sesi(kon, sesi))
    assert _dilewati_bawaan(html) == set()
    assert _angka_wajib(html) == n
