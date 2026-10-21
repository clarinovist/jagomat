"""Beranda guru: anak dikelompokkan menurut langkah reducer, bukan sekadar abjad.

Tidak ada keputusan belajar baru: kelompok dan label berasal dari
``learning_cycle.rencana_berikutnya`` lewat ``teacher_home_priority``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import reports  # noqa: E402
import teacher_home_priority as P  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


def _urutan_nama(isi):
    return re.findall(r'<h3 class="guru-nama-st">([^<]+)</h3>', isi)


def _judul_kelompok(isi):
    return re.findall(r'<h3 class="guru-kelompok-st"[^>]*>([^<]+?)\s*<span', isi)


def _sesi_terpandu(kon, siswa_id, seed):
    putaran = database.buat_putaran_fokus(kon, siswa_id, "P3")
    sesi = database.buat_sesi(kon, siswa_id, seed=seed, level="P3", jumlah_soal=2)
    kon.execute("UPDATE sesi SET tujuan='pemetaan', putaran_id=? WHERE id=?", (putaran, sesi))
    return sesi


def _kirim(kon, sesi):
    for butir in database.isi_sesi(kon, sesi):
        database.simpan_jawaban(kon, butir["sesi_soal_id"], jawaban="999", cara="")
    reports.diagnosa_murid(kon, sesi)
    database.tandai_selesai(kon, sesi)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    with uji.buka() as kon:
        # Abjad: Aaa(menunggu anak) < Bbb(siap) < Ccc(perlu tindakan)
        menunggu = database.tambah_siswa(kon, "Aaa Menunggu", "P3", pemilik="guru")
        database.tambah_siswa(kon, "Bbb Baru", "P3", pemilik="guru")
        tindakan = database.tambah_siswa(kon, "Ccc Terkirim", "P3", pemilik="guru")
        _sesi_terpandu(kon, menunggu, 801)
        _kirim(kon, _sesi_terpandu(kon, tindakan, 802))
    yield uji
    uji.berhenti()


def _beranda(uji):
    kode, isi, _ = uji.minta("/guru", auth=("guru", SANDI_GURU))
    assert kode == 200
    return isi


def test_anak_perlu_tindakan_muncul_paling_atas_walau_abjad_terakhir(server):
    isi = _beranda(server)
    assert _urutan_nama(isi) == ["Ccc Terkirim", "Bbb Baru", "Aaa Menunggu"]


def test_kelompok_berjudul_dan_berurutan(server):
    isi = _beranda(server)
    assert _judul_kelompok(isi) == ["Perlu tindakan Anda", "Siap dilanjutkan", "Menunggu"]


def test_kartu_menampilkan_langkah_dari_reducer(server):
    isi = _beranda(server)
    assert "Periksa dan konfirmasi hasil" in isi
    assert "Siapkan latihan awal" in isi


def test_sesi_dibuka_belum_dikonfirmasi_tidak_dilabeli_semua_direview(server):
    with server.buka() as kon:
        kon.execute(
            "UPDATE sesi SET direview = datetime('now', '+7 hours') "
            "WHERE siswa_id = (SELECT id FROM siswa WHERE nama = 'Ccc Terkirim')"
        )
    isi = _beranda(server)
    assert "Sudah dibuka, belum dikonfirmasi" in isi
    assert "semua direview" not in isi
    assert "Periksa dan konfirmasi hasil" in isi


def test_satu_tautan_profil_per_anak(server):
    isi = _beranda(server)
    assert len(re.findall(r'href="/anak/\d+"', isi)) == 3


def test_anak_keluarga_lain_tidak_muncul(server):
    with server.buka() as kon:
        database.tambah_siswa(kon, "Zzz Asing", "P3", pemilik="pendamping-lain")
    assert "Zzz Asing" not in _beranda(server)


def test_reducer_gagal_pada_satu_anak_tidak_merusak_beranda(server, monkeypatch):
    asli = database.muat_bukti_siklus

    def rusak(kon, siswa_id, **kw):
        nama = kon.execute("SELECT nama FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0]
        if nama == "Bbb Baru":
            raise ValueError("bukti sintetis rusak")
        return asli(kon, siswa_id, **kw)

    monkeypatch.setattr(database, "muat_bukti_siklus", rusak)
    isi = _beranda(server)
    assert "Bbb Baru" in isi
    assert "Rencana belum dapat dibaca" in isi
    assert "bukti sintetis rusak" not in isi


def test_beranda_kosong_tetap_ajakan_tambah_anak(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            kon.execute("DELETE FROM siswa WHERE pemilik='guru'")
        isi = _beranda(uji)
    finally:
        uji.berhenti()
    assert "Tambahkan anak pertama" in isi
    assert _judul_kelompok(isi) == []


# ── unit: pengelompokan murni ─────────────────────────────────────────


def test_tindakan_dipetakan_ke_kelompok():
    assert P.kelompok_untuk("konfirmasi_hasil") == P.PERLU_TINDAKAN
    assert P.kelompok_untuk("eskalasi") == P.PERLU_TINDAKAN
    assert P.kelompok_untuk("pemetaan") == P.SIAP
    assert P.kelompok_untuk("intervensi") == P.SIAP
    assert P.kelompok_untuk("lanjutkan_sesi") == P.MENUNGGU
    assert P.kelompok_untuk("tunggu_pemetaan") == P.MENUNGGU
    assert P.kelompok_untuk("tunggu_evaluasi") == P.MENUNGGU
    assert P.kelompok_untuk("tunggu_checkpoint") == P.MENUNGGU


def test_tindakan_tak_dikenal_jatuh_ke_siap_bukan_disembunyikan():
    assert P.kelompok_untuk("tindakan_baru_tak_terdaftar") == P.SIAP
    assert P.kelompok_untuk(None) == P.SIAP


def test_urutkan_menurut_kelompok_lalu_nama_tanpa_mengubah_masukan():
    masuk = [
        P.LangkahAnak(1, "Dini", "x", P.MENUNGGU, "Menunggu"),
        P.LangkahAnak(2, "budi", "y", P.PERLU_TINDAKAN, "Periksa"),
        P.LangkahAnak(3, "Andi", "z", P.SIAP, "Siap"),
        P.LangkahAnak(4, "Citra", "w", P.PERLU_TINDAKAN, "Periksa"),
    ]
    salinan = list(masuk)
    hasil = P.urutkan(masuk)
    assert [a.nama for a in hasil] == ["budi", "Citra", "Andi", "Dini"]
    assert masuk == salinan
