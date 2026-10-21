"""Beranda guru: anak dikelompokkan menurut langkah reducer, bukan sekadar abjad.

Tidak ada keputusan belajar baru: kelompok dan label berasal dari
``learning_cycle.rencana_berikutnya`` lewat ``teacher_home_priority``.
"""

from __future__ import annotations

import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import domain_clock  # noqa: E402
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
    assert "Hasil menunggu Anda tinjau" in isi
    assert "Sudah dibuka, belum dikonfirmasi" not in isi
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


# ── lama menunggu: yang terlama dahulu ───────────────────────────────


def _terkirim_dengan_tanggal(kon, nama, hari_lalu, seed):
    siswa = database.tambah_siswa(kon, nama, "P3", pemilik="guru")
    sesi = _sesi_terpandu(kon, siswa, seed)
    _kirim(kon, sesi)
    tanggal = (domain_clock.hari_wib() - timedelta(days=hari_lalu)).isoformat()
    kon.execute("UPDATE sesi SET tanggal = ? WHERE id = ?", (tanggal, sesi))
    return sesi


@pytest.fixture()
def server_menunggu(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    with uji.buka() as kon:
        # Abjad terbalik terhadap lama menunggu: Aaa baru, Zzz paling lama.
        _terkirim_dengan_tanggal(kon, "Aaa Hari Ini", 0, 811)
        _terkirim_dengan_tanggal(kon, "Mmm Dua Hari", 2, 812)
        _terkirim_dengan_tanggal(kon, "Zzz Lima Hari", 5, 813)
    yield uji
    uji.berhenti()


def test_perlu_tindakan_diurutkan_terlama_dahulu(server_menunggu):
    isi = _beranda(server_menunggu)
    assert _urutan_nama(isi) == ["Zzz Lima Hari", "Mmm Dua Hari", "Aaa Hari Ini"]


def test_lama_menunggu_ditampilkan_hanya_bila_sehari_atau_lebih(server_menunggu):
    isi = _beranda(server_menunggu)
    assert "menunggu 5 hari" in isi
    assert "menunggu 2 hari" in isi
    assert "menunggu 0 hari" not in isi
    assert isi.count("menunggu 5 hari") == 1


def test_urutkan_menaruh_yang_bertanggal_sebelum_tanpa_tanggal_dalam_kelompok():
    hari = domain_clock.hari_wib()
    masuk = [
        P.LangkahAnak(1, "Andi", "eskalasi", P.PERLU_TINDAKAN, "Tinjau"),
        P.LangkahAnak(2, "Zed", "konfirmasi_hasil", P.PERLU_TINDAKAN, "Periksa",
                      hari - timedelta(days=1)),
        P.LangkahAnak(3, "Budi", "konfirmasi_hasil", P.PERLU_TINDAKAN, "Periksa",
                      hari - timedelta(days=4)),
    ]
    assert [a.nama for a in P.urutkan(masuk)] == ["Budi", "Zed", "Andi"]


def test_hari_menunggu_dan_keterangan():
    hari = domain_clock.hari_wib()
    lama = P.LangkahAnak(1, "A", "konfirmasi_hasil", P.PERLU_TINDAKAN, "Periksa",
                         hari - timedelta(days=3))
    baru = P.LangkahAnak(2, "B", "konfirmasi_hasil", P.PERLU_TINDAKAN, "Periksa", hari)
    tanpa = P.LangkahAnak(3, "C", "pemetaan", P.SIAP, "Lanjutkan")
    assert P.hari_menunggu(lama, hari) == 3
    assert P.hari_menunggu(baru, hari) == 0
    assert P.hari_menunggu(tanpa, hari) is None
    assert P.keterangan_langkah(lama, hari) == "Periksa · menunggu 3 hari"
    assert P.keterangan_langkah(baru, hari) == "Periksa"
    assert P.keterangan_langkah(tanpa, hari) == "Lanjutkan"
