"""Satu alur per sesi (blok D, 5 Nov 2026): tinjauan terkonfirmasi menautkan tab
Perkembangan (satu-satunya pintu masuk laporan orang tua), dan lembar persiapan menyebut
langkah sesudah sesi. Tidak menyentuh laporan orang tua atau bukti belajar."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
import session_prep  # noqa: E402
import teacher_session_pages  # noqa: E402


def _sesi_terkonfirmasi(kon, nama="Anak Alur", pemilik="guru"):
    anak = database.tambah_siswa(kon, nama, pemilik=pemilik)
    sesi = database.buat_sesi(kon, anak, 77, jumlah_soal=3, topik="logika")
    for b in database.isi_sesi(kon, sesi):
        jid = database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban="RAHASIA_JWB_X", cara="hitung")
        database.simpan_diagnosis(kon, jid, benar=False, kode_usulan="K", kode_final="K", alasan="RAHASIA_ALASAN_X")
    database.tandai_selesai(kon, sesi)
    database.konfirmasi_hasil(kon, sesi, "guru", dilewati=set())
    return anak, sesi


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "alur.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def test_hasil_dikonfirmasi_menautkan_laporan_ortu_hanya_untuk_guru(db):
    with database.buka(db) as kon:
        anak, sesi = _sesi_terkonfirmasi(kon)
        html_guru = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        html_admin = teacher_session_pages.halaman_sesi_stitch(kon, sesi, peran="admin").decode()
        anak2 = database.tambah_siswa(kon, "Anak Belum", pemilik="guru")
        sesi2 = database.buat_sesi(kon, anak2, 78, jumlah_soal=1)
        b = database.isi_sesi(kon, sesi2)[0]
        database.simpan_jawaban(kon, b["sesi_soal_id"], "1", "cara")
        database.tandai_selesai(kon, sesi2)
        html_belum = teacher_session_pages.halaman_sesi_stitch(kon, sesi2).decode()
    # Keputusan pemilik 6 Nov (K3): tautan langsung ke halaman laporan, satu tautan saja.
    assert f'href="/anak/{anak}/laporan-ortu"' in html_guru and "Siapkan laporan untuk orang tua" in html_guru
    assert html_guru.count("/laporan-ortu") == 1
    assert "Snapshot" not in html_guru
    assert "Siapkan laporan untuk orang tua" not in html_admin
    assert "Siapkan laporan untuk orang tua" not in html_belum


def test_lembar_persiapan_menyebut_langkah_setelah_sesi(db):
    with database.buka(db) as kon:
        anak, _ = _sesi_terkonfirmasi(kon)
        siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (anak,)).fetchone()
        html = session_prep.halaman_persiapan(kon, siswa, peran="guru").decode()
    assert "Setelah sesi" in html and "Tinjau hasil" in html


# --- Langkah 4 penuh (6 Nov 2026): Terapkan → tinjauan, ringkasan wajib jujur,
# tautan laporan langsung. Plan: docs/plan/2026-11-06-satu-alur-sesi.md.

import re  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402

import attachments  # noqa: E402
import auth  # noqa: E402
import learning_cycle_service  # noqa: E402
import llm  # noqa: E402
import teacher_review_service  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji, _basic  # noqa: E402

SANDI_GURU_LAIN = "sandi-guru-lain-panjang-456"


class _TanpaAlih(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _post_tanpa_alih(server, jalur, data, akun=("guru", SANDI_GURU)):
    req = urllib.request.Request(
        server.alamat + jalur, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", _basic(*akun))
    try:
        with urllib.request.build_opener(_TanpaAlih).open(req, timeout=10) as r:
            return r.status, r.read().decode(), r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers.get("Location")


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(tmp_path / "lampiran"))
    monkeypatch.setattr(llm, "konfigurasi_vision", lambda: {"base_url": "", "api_key": "", "model": ""})
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _lampiran_kertas(kon, pemilik="guru"):
    anak = database.tambah_siswa(kon, "Anak Kertas", pemilik=pemilik)
    sesi = database.buat_sesi(kon, anak, seed=7)
    lid = database.simpan_lampiran(kon, sesi, "l.jpg", hasil_json="")
    return anak, sesi, lid


def _isian_lembar(butir, salah=None, kosongkan=()):
    """Payload seperti browser: semua kolom terkirim; benar dicentang, salah diketik."""
    salah = salah or {}
    data = {}
    for b in butir:
        sid = b["sesi_soal_id"]
        data[f"jwb_{sid}"] = ""
        data[f"cara_{sid}"] = ""
        if sid in kosongkan:
            continue
        if sid in salah:
            data[f"jwb_{sid}"], data[f"cara_{sid}"] = salah[sid]
        else:
            data[f"benar_{sid}"] = "on"
    return data


def test_terapkan_lengkap_membawa_guru_ke_tinjauan(server):
    with server.buka() as kon:
        _anak, sesi, lid = _lampiran_kertas(kon)
        butir = database.isi_sesi(kon, sesi)
    kode, _isi, lokasi = _post_tanpa_alih(server, f"/lampiran/{lid}/terapkan", _isian_lembar(butir))
    assert kode == 303
    assert lokasi == f"/sesi/{sesi}?pesan=Hasil%20lembar%20tersimpan"
    kode, html, _ = server.minta(lokasi, auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Hasil dari lembar tersimpan" in html
    assert f'formaction="/sesi/{sesi}/konfirmasi"' in html


def test_terapkan_sebagian_tetap_di_halaman_isi(server):
    with server.buka() as kon:
        _anak, sesi, lid = _lampiran_kertas(kon)
        butir = database.isi_sesi(kon, sesi)
    data = _isian_lembar(butir, kosongkan={butir[-1]["sesi_soal_id"]})
    kode, html, lokasi = _post_tanpa_alih(server, f"/lampiran/{lid}/terapkan", data)
    assert kode == 200 and lokasi is None
    assert f'action="/lampiran/{lid}/terapkan"' in html
    with server.buka() as kon:
        assert kon.execute("SELECT selesai FROM sesi WHERE id=?", (sesi,)).fetchone()[0] is None


def test_terapkan_ditolak_tetap_400_tanpa_tulis_dan_tanpa_alih(server):
    with server.buka() as kon:
        _anak, sesi, lid = _lampiran_kertas(kon)
        butir = database.isi_sesi(kon, sesi)
    data = _isian_lembar(butir)
    data[f"jwb_{butir[0]['sesi_soal_id']}"] = "tidak"  # dicentang benar, teks beda
    kode, html, lokasi = _post_tanpa_alih(server, f"/lampiran/{lid}/terapkan", data)
    assert kode == 400 and lokasi is None
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=?",
            (sesi,)).fetchone()[0]
    assert n == 0


def test_terapkan_guru_asing_404_identik_tanpa_tulis(server):
    auth.tambah_akun("guru-lain", SANDI_GURU_LAIN, "guru", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        _anak, sesi, lid = _lampiran_kertas(kon)
        butir = database.isi_sesi(kon, sesi)
        sebelum = tuple(kon.iterdump())
    asing = _post_tanpa_alih(server, f"/lampiran/{lid}/terapkan", _isian_lembar(butir),
                             akun=("guru-lain", SANDI_GURU_LAIN))
    tidak_ada = _post_tanpa_alih(server, "/lampiran/999999/terapkan", {},
                                 akun=("guru-lain", SANDI_GURU_LAIN))
    assert asing[0] == tidak_ada[0] == 404
    assert asing[1] == tidak_ada[1] and asing[2] is None
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def _sesi_kertas_campuran(kon):
    """15 soal: 2 salah cocok pola (dugaan), 2 salah tanpa pola (Belum yakin), sisanya dicentang."""
    _anak, sesi, lid = _lampiran_kertas(kon)
    butir = database.isi_sesi(kon, sesi)
    berpola = [b for b in butir if database.malrule_soal(kon, b["soal_id"])][:2]
    assert len(berpola) == 2
    salah = {b["sesi_soal_id"]: (database.malrule_soal(kon, b["soal_id"])[0]["jawaban"], "aku hitung")
             for b in berpola}
    asal = [b for b in butir if b["sesi_soal_id"] not in salah][-2:]
    salah.update({b["sesi_soal_id"]: ("987654", "aku coba-coba") for b in asal})
    attachments.terapkan(kon, lid, _isian_lembar(butir, salah))
    kon.commit()
    return sesi, [b["sesi_soal_id"] for b in asal]


def _angka_wajib(html):
    cocok = re.search(r"(\d+) soal wajib Anda putuskan", html)
    return int(cocok.group(1)) if cocok else 0


def test_ringkasan_wajib_sama_dengan_yang_ditolak_server(db):
    with database.buka(db) as kon:
        sesi, belum_yakin = _sesi_kertas_campuran(kon)
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert _angka_wajib(html) == 2
        assert "2 wajib diputuskan" in html
        assert "masih perlu diperiksa" not in html
        assert "tidak wajib untuk konfirmasi" in html  # soal benar: tanya cara opsional
        # Kartu selaras dengan ringkasan: 2 wajib, 2 dugaan yang boleh disetujui.
        assert html.count("Wajib diputuskan sebelum konfirmasi.") == 2
        assert html.count("Dugaan Jagomat. Boleh disetujui apa adanya saat konfirmasi.") == 2
        assert "Periksa soal yang ditandai sebelum" not in html
        with pytest.raises(learning_cycle_service.KonfirmasiBelumLengkap) as galat:
            learning_cycle_service.konfirmasi_dari_form(kon, sesi, "guru", {})
        kon.rollback()
        assert len(galat.value.masalah) == 2
        teacher_review_service.simpan_sesi(kon, sesi, {f"kode_{sid}": "K" for sid in belum_yakin})
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert _angka_wajib(html) == 0
        assert "Siap dikonfirmasi" in html
        assert "Wajib diputuskan sebelum konfirmasi." not in html
        learning_cycle_service.konfirmasi_dari_form(kon, sesi, "guru", {})
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id=?", (sesi,)).fetchone()[0]
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert "Sudah dikonfirmasi" in html and "Siap dikonfirmasi" not in html


def test_tautan_laporan_sesudah_konfirmasi_langsung_ke_halaman_laporan(db):
    with database.buka(db) as kon:
        anak, sesi = _sesi_terkonfirmasi(kon, nama="Anak Lapor")
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        html_admin = teacher_session_pages.halaman_sesi_stitch(kon, sesi, peran="admin").decode()
    assert f'href="/anak/{anak}/laporan-ortu"' in html
    assert html.count("Siapkan laporan untuk orang tua") == 1
    assert "/laporan-ortu" not in html_admin
