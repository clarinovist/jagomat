"""Kontrak beranda anak: metadata aman, satu prioritas, dan status jujur."""
import re
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import database
import learning_cycle as lc
import student_pages
import students


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "beranda.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    return jalur


@pytest.fixture()
def db_terjaga(db, monkeypatch):
    class BarisTerjaga(sqlite3.Row):
        def __getitem__(self, nama):
            assert nama not in {"kunci", "malrule_id", "kode_final", "kode_usulan", "alasan", "data"}
            return super().__getitem__(nama)
    monkeypatch.setattr(sqlite3, "Row", BarisTerjaga)
    return db


def _siswa(kon, nama="Anak Demo", level="P4"):
    return database.tambah_siswa(kon, nama, tingkat=level, pemilik="guru")


def _sesi(kon, siswa, **kwargs):
    return database.buat_sesi(kon, siswa, seed=17, level=kwargs.pop("level", "P4"),
                              jumlah_soal=4, **kwargs)


def _isi(kon, siswa, sesi, n=1):
    butir = students.soal_murid(kon, sesi, siswa)
    students.simpan_jawaban_murid(kon, siswa, sesi,
        {f"jwb_{b['sesi_soal_id']}": "7" for b in butir[:n]})


def _html(kon, siswa, selesai=None):
    return student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Demo", selesai).decode()


def _utama(html):
    return re.findall(r'<a\b[^>]*data-utama="true"[^>]*href="/murid/kerjakan/(\d+)"', html)


def test_satu_aksi_utama_manual_yang_sudah_dimulai_didahulukan(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        proses = _sesi(kon, siswa)
        _isi(kon, siswa, proses)
        baru = _sesi(kon, siswa)
        html = _html(kon, siswa)
    assert _utama(html) == [str(proses)]
    assert html.count(f'href="/murid/kerjakan/{proses}"') == 1
    assert html.count(f'href="/murid/kerjakan/{baru}"') == 1
    assert "Lanjutkan latihan" in html
    assert "Pola bilangan" in html


def test_beranda_tanpa_sesi_tidak_menyuruh_memilih(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        html = _html(kon, siswa)
    assert "Siap untuk" in html and "latihan pertama?" in html
    assert "Pilih sesi" not in html
    assert not _utama(html)
    assert "<script" not in html
    assert html.count('action="/keluar"') == 1


@pytest.mark.parametrize("keadaan", ["baru", "selesai", "direview"])
@pytest.mark.parametrize("ada_pengganti", [False, True])
def test_sesi_dibatalkan_tetap_tersembunyi_di_beranda(db_terjaga, keadaan, ada_pengganti):
    with database.buka(db_terjaga) as kon:
        siswa = _siswa(kon)
        batal = _sesi(kon, siswa)
        if keadaan != "baru":
            database.tandai_selesai(kon, batal)
        if keadaan == "direview":
            kon.execute("UPDATE sesi SET direview='2026-09-09' WHERE id=?", (batal,))
        database.batalkan_sesi(kon, batal, "Alasan pembatalan sintetis rahasia")
        pengganti = _sesi(kon, siswa) if ada_pengganti else None
        sebelum = tuple(kon.iterdump())
        html = _html(kon, siswa)
        assert tuple(kon.iterdump()) == sebelum
    assert f'href="/murid/kerjakan/{batal}"' not in html
    assert f'href="/murid/hasil/{batal}"' not in html
    assert "Alasan pembatalan sintetis rahasia" not in html
    if ada_pengganti:
        assert _utama(html) == [str(pengganti)]
        assert html.count(f'href="/murid/kerjakan/{pengganti}"') == 1
    else:
        assert not _utama(html)
        assert "Belum ada sesi latihan yang disiapkan." in html


@pytest.mark.parametrize("kondisi", ["manual", "level", "tertutup", "batal", "putaran_lama", "siswa_lain"])
def test_sesi_tidak_relevan_tidak_mengambil_prioritas_terpandu(db, kondisi):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        lain = _siswa(kon, "Anak lain")
        putaran_lama = database.buat_putaran_fokus(kon, siswa, "P4")
        putaran = database.buat_putaran_fokus(kon, siswa, "P4")
        salah = _sesi(kon, lain if kondisi == "siswa_lain" else siswa,
                      level="P3" if kondisi == "level" else "P4")
        benar = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=? WHERE id IN (?, ?)", (putaran, salah, benar))
        if kondisi == "manual":
            kon.execute("UPDATE sesi SET tujuan='bebas' WHERE id=?", (salah,))
        elif kondisi == "batal":
            database.batalkan_sesi(kon, salah)
        elif kondisi in {"tertutup", "putaran_lama"}:
            kon.execute("UPDATE sesi SET putaran_id=? WHERE id=?", (putaran_lama, salah))
            if kondisi == "tertutup":
                kon.execute("INSERT INTO kejadian_belajar (siswa_id, putaran_id, jenis) VALUES (?, ?, 'putaran_ditutup')", (siswa, putaran_lama))
        html = _html(kon, siswa)
        rencana = lc.rencana_berikutnya(database.muat_bukti_siklus(kon, siswa), siswa)
    assert rencana.sesi_id == benar
    assert _utama(html) == [str(benar)]
    if kondisi in {"batal", "siswa_lain"}:
        assert f'href="/murid/kerjakan/{salah}"' not in html


def test_putaran_ditutup_tidak_dianggap_aktif_oleh_selector(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        putaran = database.buat_putaran_fokus(kon, siswa, "P4")
        sesi = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=? WHERE id=?", (putaran, sesi))
        kon.execute("INSERT INTO kejadian_belajar (siswa_id, putaran_id, jenis) VALUES (?, ?, 'putaran_ditutup')", (siswa, putaran))
        assert not _utama(_html(kon, siswa))


def test_selector_bersama_dipakai_reducer_dan_beranda(db, monkeypatch):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        putaran = database.buat_putaran_fokus(kon, siswa, "P4")
        sesi = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=? WHERE id=?", (putaran, sesi))
        asli = lc.sesi_berjalan
        panggilan = []
        def catat(bukti):
            panggilan.append(bukti)
            return asli(bukti)
        monkeypatch.setattr(lc, "sesi_berjalan", catat)
        assert lc.rencana_berikutnya(database.muat_bukti_siklus(kon, siswa), siswa).sesi_id == sesi
        assert _utama(_html(kon, siswa)) == [str(sesi)]
    assert len(panggilan) == 2


def test_selector_tertua_deterministik_bukan_id_terbaru(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        putaran = database.buat_putaran_fokus(kon, siswa, "P4")
        pertama = _sesi(kon, siswa, tanggal="2026-09-03")
        kedua = _sesi(kon, siswa, tanggal="2026-09-01")
        kon.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=?, dibuat='2026-09-01 10:00'", (putaran,))
        assert _utama(_html(kon, siswa)) == [str(kedua)]
        kon.execute("UPDATE sesi SET tanggal='2026-09-01'")
        assert _utama(_html(kon, siswa)) == [str(pertama)]


def test_putaran_aktif_menunggu_tidak_diganti_manual(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        database.buat_putaran_fokus(kon, siswa, "P4")
        manual = _sesi(kon, siswa)
        html = _html(kon, siswa)
    assert not _utama(html)
    assert f'href="/murid/kerjakan/{manual}"' in html


@pytest.mark.parametrize("isi", [0, 1, 4])
def test_sudah_dikirim_tidak_diajak_kerjakan_ulang_atau_buka_hasil(db, isi):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        if isi:
            _isi(kon, siswa, sesi, isi)
        database.tandai_selesai(kon, sesi)
        html = _html(kon, siswa)
    assert "Menunggu diperiksa" in html
    assert f'href="/murid/kerjakan/{sesi}"' not in html
    assert f'href="/murid/hasil/{sesi}"' not in html
    assert not _utama(html)


def test_review_tanpa_selesai_tetap_sesi_kerja(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET direview='2026-09-09' WHERE id=?", (sesi,))
        html = _html(kon, siswa)
    assert f'href="/murid/kerjakan/{sesi}"' in html
    assert f'href="/murid/hasil/{sesi}"' not in html


def test_hasil_hanya_satu_di_riwayat_setelah_selesai_dan_review(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        database.tandai_selesai(kon, sesi)
        kon.execute("UPDATE sesi SET direview='2026-09-09' WHERE id=?", (sesi,))
        html = _html(kon, siswa)
    assert html.count(f'href="/murid/hasil/{sesi}"') == 1
    assert '<details class="murid-riwayat-st"' in html
    assert f'href="/murid/kerjakan/{sesi}"' not in html


@pytest.mark.parametrize("jenis", ["belum_selesai", "lain", "tidak_ada", "batal"])
def test_banner_tidak_percaya_parameter_url(db, jenis):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        lain = _siswa(kon, "Lain")
        sesi = _sesi(kon, lain if jenis == "lain" else siswa)
        if jenis != "belum_selesai":
            database.tandai_selesai(kon, sesi)
        if jenis == "batal":
            database.batalkan_sesi(kon, sesi)
        html = _html(kon, siswa, 99999 if jenis == "tidak_ada" else sesi)
    assert 'class="st-banner-sukses"' not in html
    assert "Semua jawabanmu sudah masuk" not in html


def test_banner_valid_tidak_mengklaim_semua_soal_terisi(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        database.tandai_selesai(kon, sesi)
        html = _html(kon, siswa, sesi)
    assert 'class="st-banner-sukses"' in html
    assert "Semua jawabanmu" not in html


def test_beranda_tidak_membaca_bukti_diagnosis_atau_menulis(db_terjaga):
    with database.buka(db_terjaga) as kon:
        siswa = _siswa(kon)
        putaran = database.buat_putaran_fokus(kon, siswa, "P4")
        sesi = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=? WHERE id=?", (putaran, sesi))
        kon.commit()
        tabel_aman = {"siswa", "sesi", "sesi_soal", "jawaban", "putaran_fokus", "kejadian_belajar", "pilot_sesi", "pilot_putaran"}
        def palang(aksi, tabel, kolom, db_nama, sumber):
            if aksi == sqlite3.SQLITE_READ:
                assert tabel in tabel_aman
                assert kolom not in {"kunci", "malrule_id", "kode_final", "kode_usulan", "alasan", "data", "kontrak_json", "konteks_json", "fingerprint"}
            return sqlite3.SQLITE_OK
        kon.set_authorizer(palang)
        sebelum = kon.total_changes
        html = _html(kon, siswa)
        assert kon.total_changes == sebelum
        kon.set_authorizer(None)
    badan = html.split("</style>")[-1]
    assert _utama(html) == [str(sesi)]
    for rahasia in ("Diagnostik", "Remedial", "malrule", "kode_final", "kelemahan", "Rencana belajar hari ini"):
        assert rahasia not in badan


def test_akun_http_tidak_melihat_sesi_anak_lain_dan_get_tanpa_mutasi(tmp_path, monkeypatch):
    from http_test_kit import SANDI_MURID, ServerUji
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            lain = _siswa(kon, "Anak lain")
            sendiri = _sesi(kon, siswa)
            rahasia = _sesi(kon, lain)
            database.tandai_selesai(kon, rahasia)
            sebelum = tuple(kon.iterdump())
        badan = []
        for jalur in ("/murid", f"/murid?selesai={rahasia}", "/murid?selesai=999999"):
            status, html, _ = server.minta(jalur, auth=("feby", SANDI_MURID))
            badan.append(html)
            assert status == 200
            assert _utama(html) == [str(sendiri)]
            assert f'/murid/hasil/{rahasia}' not in html
            assert 'class="st-banner-sukses"' not in html
        assert badan[0] == badan[1] == badan[2]
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    finally:
        server.berhenti()


def test_progres_menghitung_cara_dan_centang_tetapi_bukan_baris_kosong(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        butir = students.soal_murid(kon, sesi, siswa)
        students.simpan_jawaban_murid(kon, siswa, sesi, {
            f"cara_{butir[0]['sesi_soal_id']}": "Digambar dulu",
            f"blm_{butir[1]['sesi_soal_id']}": "on",
        })
        kon.execute("INSERT INTO jawaban(sesi_soal_id, jawaban, cara) VALUES (?, '   ', '')",
                    (butir[2]['sesi_soal_id'],))
        data = students.beranda_murid(kon, siswa)
        html = _html(kon, siswa)
    assert set(data["sesi"][0]) == {"id", "tanggal", "level", "topik", "mode", "jenis", "tujuan",
                                    "selesai", "direview", "jumlah", "terisi", "format_jawaban"}
    assert data["sesi"][0]["terisi"] == 2
    assert "2 dari 4 soal tersimpan" in html
    assert 'aria-valuenow="2"' in html


def test_nama_tanggal_level_dan_topik_aneh_tetap_aman(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon, level='<svg onload="alert(1)">')
        sesi = _sesi(kon, siswa)
        kon.execute("UPDATE sesi SET tanggal=?, topik=? WHERE id=?",
                    ('<b>tanggal</b>', '<script>topik</script>', sesi))
        html = student_pages.halaman_daftar_sesi_baru(kon, siswa, '<img src=x onerror="alert(1)">').decode()
    assert '<img src=x' not in html and '<svg onload=' not in html
    assert '&lt;b&gt;tanggal&lt;/b&gt;' in html
    assert '&lt;img src=x' in html
    assert "Pola bilangan" in html
    assert not _utama(html)


def test_semua_soal_dijawab_belum_dikirim_tetap_bisa_dilanjutkan(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        _isi(kon, siswa, sesi, 4)
        html = _html(kon, siswa)
    assert _utama(html) == [str(sesi)]
    assert "4 dari 4 soal tersimpan" in html
    assert f'href="/murid/hasil/{sesi}"' not in html


def test_sesi_nol_soal_tidak_membagi_nol_atau_jadi_utama_manual(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa)
        kon.execute("DELETE FROM sesi_soal WHERE sesi_id=?", (sesi,))
        html = _html(kon, siswa)
    assert not _utama(html)
    assert "0 soal" in html


def test_siswa_tidak_dikenal_dapat_proyeksi_kosong(db):
    with database.buka(db) as kon:
        assert students.beranda_murid(kon, 999999) == {
            "level": "", "sesi": [], "utama_id": None, "terpandu": False,
        }


def test_ikon_topik_stabil_walau_sesi_baru_ditambahkan(db):
    with database.buka(db) as kon:
        siswa = _siswa(kon)
        sesi = _sesi(kon, siswa, topik="statistika")
        data = students.beranda_murid(kon, siswa)["sesi"][0]
        judul = student_pages._judul_beranda(data)
        _sesi(kon, siswa)
        data_baru = next(b for b in students.beranda_murid(kon, siswa)["sesi"] if b["id"] == sesi)
        assert student_pages._judul_beranda(data_baru) == judul == ("Statistika", "grafik")


def test_css_beranda_scoped_dan_kontras_tombol():
    import design_tokens as T
    import style_stitch
    css = style_stitch.gaya_stitch()
    for marker in (".murid-beranda-st", ".murid-tombol-utama-st", ".murid-riwayat-st", ".murid-lewati-st"):
        assert marker in css
    tombol = re.search(r"\.murid-tombol-utama-st\s*\{([^}]+)\}", css).group(1)
    assert T.AKSEN_KORAL_TUA in tombol
    assert "min-height: 3.25rem" in tombol
    assert 'outline: 3px solid ' + T.AKSEN_TEAL_TUA in css
