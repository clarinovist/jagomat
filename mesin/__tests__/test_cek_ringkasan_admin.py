"""Pembaca ringkasan cek untuk admin (irisan D1): allowlist, tiga kunci, retensi, tanpa tulis.

Semua data sintetis di basis sementara; waktu disuntik. Tes di sini menjadi sasaran mutation di
`test_admin_pesanan_cek_mutation.py`.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import cek_gratis_sapu  # noqa: E402
import cek_ringkasan_admin as cra  # noqa: E402
import database  # noqa: E402
import topik_awam  # noqa: E402
from cek_gratis_kit import (  # noqa: E402
    ID_A, ID_B, ID_C, SEKARANG, SELESAI_SESI, jawab, mulai_cek, tambah_anak, tandai_selesai,
)

NAMA_ANAK = "Anak Sintetis Rahasia"
KUNCI_PERSIS = {
    "status", "kelas", "skor", "kategori", "jumlah_soal", "selesai_pada", "ringkasan_kuat",
    "ringkasan_perlu", "per_materi", "bahan", "hari_tersisa",
}
BERHITUNG, UKUR, GEOMETRI = "berhitung-sekolah", "pengukuran", "geometri-datar"
BENAR_CAMPURAN = {BERHITUNG: 5, UKUR: 2, GEOMETRI: 0}  # 5/5, 2/5, 0/5 -> 7 dari 15 = 47
SELESAI_ISO = "2026-11-18T09:00:00"
AKHIR_RETENSI = "2026-12-18T09:00:00"  # selesai + 30 hari


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "ringkasan.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


@pytest.fixture(autouse=True)
def materi_dasar_mati(monkeypatch):
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)


def _nama(topik_id):
    return topik_awam.nama(topik_id)


def _cek_selesai(kon, id_akun=ID_A, pemilik="guru-a", *, nama=NAMA_ANAK, selesai=SELESAI_SESI,
                 benar_per_topik=None):
    """Cek yang selesai dan sudah dinilai (skor tersimpan) -> (siswa_id, cek_id, sesi_id)."""
    anak = tambah_anak(kon, nama, pemilik, 4)
    sesi_id = mulai_cek(kon, id_akun, anak, pemilik)
    jawab(kon, sesi_id, BENAR_CAMPURAN if benar_per_topik is None else benar_per_topik)
    tandai_selesai(kon, sesi_id, selesai)
    assert cek_gratis.selesaikan_jika_siap(kon, id_akun, SEKARANG) is True
    cek_id = kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]
    return anak, cek_id, sesi_id


def _baca(kon, anak, cek_id, id_akun=ID_A, sekarang=SEKARANG):
    return cra.ringkasan_untuk_order(kon, anak, cek_id, id_akun, sekarang)


def _potret(kon):
    """Isi seluruh tabel + jumlah perubahan koneksi: tulis apa pun terlihat di sini."""
    nama = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    isi = [(t, [tuple(r) for r in kon.execute('SELECT * FROM "%s" ORDER BY rowid' % t)]) for t in nama
           if t != "sqlite_sequence"]
    return kon.total_changes, hashlib.sha256(repr(isi).encode()).hexdigest()


# --- bentuk hasil ----------------------------------------------------------------------

def test_daftar_kunci_hasil_persis(kon):
    anak, cek_id, _s = _cek_selesai(kon)
    assert set(_baca(kon, anak, cek_id)) == KUNCI_PERSIS


def test_cek_selesai_dinilai_memuat_skor_ringkasan_dan_per_materi(kon):
    anak, cek_id, _s = _cek_selesai(kon)
    hasil = _baca(kon, anak, cek_id)
    assert (hasil["status"], hasil["kelas"], hasil["skor"], hasil["kategori"], hasil["jumlah_soal"]) == (
        "selesai", 4, 47, "Perlu penguatan", 15)
    assert hasil["selesai_pada"] == SELESAI_ISO
    assert hasil["ringkasan_kuat"] == [_nama(BERHITUNG)]
    assert hasil["ringkasan_perlu"] == [_nama(GEOMETRI), _nama(UKUR)]
    assert hasil["per_materi"] == [
        {"materi": _nama(BERHITUNG), "benar": 5, "total": 5},
        {"materi": _nama(GEOMETRI), "benar": 0, "total": 5},
        {"materi": _nama(UKUR), "benar": 2, "total": 5},
    ]
    assert (hasil["bahan"], hasil["hari_tersisa"]) == ("ada", 29)  # SEKARANG = 1 jam sesudah selesai


def test_ringkasan_sama_dengan_hasil_yang_disimpan_cek_gratis(kon):
    anak, cek_id, _s = _cek_selesai(kon)
    hasil, simpanan = _baca(kon, anak, cek_id), cek_gratis.hasil_siswa(kon, ID_A, anak)
    assert (hasil["skor"], hasil["kategori"]) == (simpanan["skor"], simpanan["kategori"])
    assert (hasil["ringkasan_kuat"], hasil["ringkasan_perlu"]) == (
        simpanan["ringkasan"]["kuat"], simpanan["ringkasan"]["perlu"])


def test_topik_kurang_dari_tiga_soal_tetap_muncul_di_per_materi(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon)
    peta = cek_gratis._peta_template_ke_topik()
    geometri = [b["soal_id"] for b in database.isi_sesi(kon, sesi_id)
                if peta[b["template_id"]] == GEOMETRI]
    # Tiga soal geometri dilepas dari peta topik cek (template tak dikenal): tersisa dua soal geometri.
    for soal_id in geometri[:3]:
        kon.execute("UPDATE soal SET template_id = 'template-tak-dikenal-sintetis' WHERE id = ?", (soal_id,))
    hasil = _baca(kon, anak, cek_id)
    assert [b for b in hasil["per_materi"] if b["materi"] == _nama(GEOMETRI)] == [
        {"materi": _nama(GEOMETRI), "benar": 0, "total": 2}]
    assert len(hasil["per_materi"]) == 3


def test_tak_dijawab_dihitung_salah_dan_topik_tanpa_jawaban_nol(kon):
    anak, cek_id, _s = _cek_selesai(kon, benar_per_topik={})
    hasil = _baca(kon, anak, cek_id)
    assert hasil["skor"] == 0
    assert [(b["benar"], b["total"]) for b in hasil["per_materi"]] == [(0, 5)] * 3


def test_kelas_kosong_bila_profil_tidak_ada(kon):
    anak, cek_id, _s = _cek_selesai(kon)
    kon.execute("UPDATE profil_belajar SET kelas_sekolah = NULL WHERE siswa_id = ?", (anak,))
    assert _baca(kon, anak, cek_id)["kelas"] is None


# --- tiga kunci kecocokan --------------------------------------------------------------

def test_cek_milik_siswa_lain_tidak_terbaca(kon):
    anak_a, cek_a, _ = _cek_selesai(kon, ID_A, "guru-a", nama="Anak A")
    anak_b, cek_b, _ = _cek_selesai(kon, ID_B, "guru-b", nama="Anak B")
    assert _baca(kon, anak_a, cek_a, ID_A) is not None
    assert _baca(kon, anak_a, cek_b, ID_A) is None   # cek anak B dengan siswa A
    assert _baca(kon, anak_b, cek_a, ID_B) is None   # cek anak A dengan siswa B
    assert _baca(kon, anak_b, cek_a, ID_A) is None   # akun dan cek cocok, hanya siswa yang salah


def test_cek_milik_akun_lain_tidak_terbaca(kon):
    anak, cek_id, _ = _cek_selesai(kon, ID_A, "guru-a")
    assert _baca(kon, anak, cek_id, ID_B) is None
    assert _baca(kon, anak, cek_id, ID_C) is None


def test_cek_id_salah_untuk_siswa_dan_akun_yang_benar_tidak_terbaca(kon):
    anak, cek_id, _ = _cek_selesai(kon)
    assert _baca(kon, anak, cek_id + 1000) is None
    assert _baca(kon, anak + 1000, cek_id) is None


@pytest.mark.parametrize("siswa_id,cek_id", [(0, 1), (1, 0), (-1, 1), ("1", 1), (1, "1"), (True, 1), (None, 1)])
def test_id_tak_sah_menghasilkan_none(kon, siswa_id, cek_id):
    _cek_selesai(kon)
    assert cra.ringkasan_untuk_order(kon, siswa_id, cek_id, ID_A, SEKARANG) is None


def test_id_akun_tak_sah_ditolak_dan_waktu_tak_sah_ditolak(kon):
    anak, cek_id, _ = _cek_selesai(kon)
    with pytest.raises(ValueError):
        _baca(kon, anak, cek_id, "bukan-akun")
    with pytest.raises(ValueError):
        _baca(kon, anak, cek_id, ID_A, "kemarin")


# --- bahan dihapus, belum dinilai, belum selesai -----------------------------------------

def test_bahan_dihapus_sapuan_retensi_per_materi_kosong_turunan_tetap(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon, selesai="2026-10-17 09:00:00")  # 32 hari sebelum SEKARANG
    assert cek_gratis_sapu.sapu_cek_gratis(kon, SEKARANG, frozenset({ID_A}))["bahan_dihapus"] == 1
    hasil = _baca(kon, anak, cek_id)
    assert (hasil["status"], hasil["bahan"], hasil["per_materi"], hasil["hari_tersisa"]) == (
        "selesai", "dihapus", [], None)
    assert (hasil["skor"], hasil["kategori"], hasil["ringkasan_kuat"]) == (47, "Perlu penguatan", [_nama(BERHITUNG)])


def test_sesi_id_null_berarti_bahan_dihapus(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon)
    kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))  # ON DELETE SET NULL
    assert kon.execute("SELECT sesi_id FROM cek_gratis WHERE id = ?", (cek_id,)).fetchone()[0] is None
    hasil = _baca(kon, anak, cek_id)
    assert (hasil["bahan"], hasil["per_materi"], hasil["hari_tersisa"]) == ("dihapus", [], None)


def test_jawaban_tanpa_diagnosis_berarti_belum_dinilai_dan_tidak_menebak(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon)
    kon.execute("DELETE FROM diagnosis WHERE jawaban_id IN "
                "(SELECT j.id FROM jawaban j JOIN sesi_soal ss ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?)",
                (sesi_id,))
    hasil = _baca(kon, anak, cek_id)
    assert (hasil["bahan"], hasil["per_materi"]) == ("belum_dinilai", [])
    assert hasil["status"] == "selesai" and hasil["skor"] == 47


def test_cek_belum_selesai_tanpa_skor_dan_tanpa_per_materi(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    mulai_cek(kon, ID_A, anak, "guru-a")
    cek_id = kon.execute("SELECT id FROM cek_gratis WHERE siswa_id = ?", (anak,)).fetchone()[0]
    hasil = _baca(kon, anak, cek_id)
    assert set(hasil) == KUNCI_PERSIS
    assert (hasil["status"], hasil["skor"], hasil["kategori"], hasil["selesai_pada"]) == (
        "belum_selesai", None, None, None)
    assert (hasil["ringkasan_kuat"], hasil["ringkasan_perlu"], hasil["per_materi"]) == ([], [], [])
    assert (hasil["bahan"], hasil["hari_tersisa"], hasil["kelas"]) == ("belum_dinilai", None, 4)


# --- retensi 30 hari -------------------------------------------------------------------

@pytest.mark.parametrize("sekarang,sisa", [
    ("2026-11-18T09:00:00", 30),   # saat selesai
    ("2026-11-19T09:00:00", 29),
    ("2026-12-17T09:00:00", 1),
    ("2026-12-17T21:00:00", 0),    # 12 jam tersisa: dibulatkan ke bawah (tidak melebihkan)
    (AKHIR_RETENSI, 0),            # tepat 30 hari: sapuan memakai < ketat, bahan belum dihapus
    ("2026-12-18T09:00:01", 0),    # lewat 1 detik tetapi sapuan belum jalan: bahan masih ada
    ("2026-12-25T09:00:00", 0),    # tidak pernah negatif
])
def test_hari_tersisa_dari_selesai_dengan_retensi_tiga_puluh_hari(kon, sekarang, sisa):
    anak, cek_id, _s = _cek_selesai(kon)
    hasil = _baca(kon, anak, cek_id, ID_A, sekarang)
    assert (hasil["bahan"], hasil["hari_tersisa"]) == ("ada", sisa)


def test_batas_hari_tersisa_selaras_dengan_sapuan(kon):
    """Pada waktu yang sama, bahan 'ada' tepat sampai sapuan tidak menghapusnya."""
    anak, cek_id, _s = _cek_selesai(kon)
    assert cek_gratis_sapu.sapu_cek_gratis(kon, AKHIR_RETENSI, frozenset({ID_A}))["bahan_dihapus"] == 0
    assert _baca(kon, anak, cek_id, ID_A, AKHIR_RETENSI)["bahan"] == "ada"
    assert cek_gratis_sapu.sapu_cek_gratis(kon, "2026-12-18T09:00:01", frozenset({ID_A}))["bahan_dihapus"] == 1
    assert _baca(kon, anak, cek_id, ID_A, "2026-12-18T09:00:01")["bahan"] == "dihapus"


# --- tanpa tulis ------------------------------------------------------------------------

@pytest.mark.parametrize("keadaan", ["dinilai", "belum_dinilai", "dihapus", "belum_selesai"])
def test_membaca_tidak_menulis_apa_pun(kon, keadaan, monkeypatch):
    if keadaan == "belum_selesai":
        anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
        mulai_cek(kon, ID_A, anak, "guru-a")
        cek_id = kon.execute("SELECT id FROM cek_gratis").fetchone()[0]
        # Jawaban ada tetapi belum dinilai dan sesi belum selesai.
        sesi = kon.execute("SELECT sesi_id FROM cek_gratis").fetchone()[0]
        jawab(kon, sesi, semua_benar=9)
    else:
        anak, cek_id, sesi = _cek_selesai(kon)
        if keadaan == "belum_dinilai":
            kon.execute("DELETE FROM diagnosis")
        if keadaan == "dihapus":
            kon.execute("DELETE FROM sesi WHERE id = ?", (sesi,))
    import reports

    def terlarang(*_a, **_k):
        raise AssertionError("pembaca admin tidak boleh menilai/menulis")
    monkeypatch.setattr(reports, "diagnosa_murid", terlarang)
    sebelum = _potret(kon)
    assert _baca(kon, anak, cek_id) is not None
    assert _potret(kon) == sebelum


def test_jawaban_belum_dinilai_tidak_diberi_diagnosis_oleh_pembaca(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon)
    kon.execute("DELETE FROM diagnosis")
    assert kon.execute("SELECT COUNT(*) FROM diagnosis").fetchone()[0] == 0
    assert _baca(kon, anak, cek_id)["bahan"] == "belum_dinilai"
    assert kon.execute("SELECT COUNT(*) FROM diagnosis").fetchone()[0] == 0


# --- tanpa data pribadi/rahasia ----------------------------------------------------------

def _nilai_teks(nilai):
    if isinstance(nilai, dict):
        return [t for v in nilai.values() for t in _nilai_teks(v)]
    if isinstance(nilai, (list, tuple)):
        return [t for v in nilai for t in _nilai_teks(v)]
    return [str(nilai)]


def test_hasil_tidak_memuat_nama_anak_kunci_soal_atau_identitas(kon):
    anak, cek_id, sesi_id = _cek_selesai(kon)
    hasil = _baca(kon, anak, cek_id)
    teks = " | ".join(_nilai_teks(hasil)).lower()
    assert NAMA_ANAK.lower() not in teks and ID_A not in teks and "guru-a" not in teks
    kunci_soal = {b["kunci"] for b in database.isi_sesi(kon, sesi_id) if len(b["kunci"]) > 3}
    assert not any(k.lower() in teks for k in kunci_soal)
    assert all(set(b) == {"materi", "benar", "total"} for b in hasil["per_materi"])
