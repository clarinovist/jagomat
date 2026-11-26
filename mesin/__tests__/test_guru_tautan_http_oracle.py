"""Tambah anak dengan kode, sisi oracle: setiap kegagalan kode berbentuk SATU jawaban byte-identik (status,
Content-Type, Content-Length, badan), 429 dan 403 tidak bergantung pada validitas kode, dan kegagalan yang
diblokir atau ditolak token tidak menambah hitungan. Juga auth tak terbaca, dan log yang bersih dari kode.

Setiap kegagalan kode menambah tepat satu baris `percobaan_gagal` dan tidak menyentuh tabel lain.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Callable

import pytest

import admin_store
import guru_tautan_aturan as aturan
import guru_tautan_anak
import guru_tautan_dasar as dasar
import guru_tautan_http as tautan
import guru_tautan_laju as laju
import guru_tautan_pages as halaman
import jadwal_store as js
import kelas_kit
from cek_http_kit import AKUN_A, ambil_token, minta_mentah, server  # noqa: F401
from guru_tautan_kit import (
    ADMIN,
    JAM_KELOMPOK,
    KINI,
    KODE,
    KODE_LAIN,
    LOGIN_ANAK,
    LOGIN_KELUARGA_LAIN,
    LOKASI,
    SANDI_KELUARGA_LAIN,
    SESUDAH,
    JALUR_TAUTAN,
    KondisiTautan,
    baris_tabel,
    buat_kode_anak,
    hapus_keluarga_sintetis,
    keadaan_tautan,
    siapkan_db_tautan,
    siapkan_kelompok_dan_order,
    tambah_murid,
)
from cek_http_kit import tambah_anak
from harian_kit import jam  # noqa: F401
import auth

KODE_REF = "2345EFGH6789ABCD"  # format sah, tidak pernah diterbitkan di tes mana pun
IP_BLOKIR = "203.0.113.7"
IP_LAIN = "203.0.113.8"
KELOMPOK_TIDAK_ADA = "klp_" + "0" * 32


def _hash_berkas(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jawaban(hasil) -> tuple:
    kode, isi, headers = hasil
    kecil = {nama.lower(): nilai for nama, nilai in headers.items()}
    return (kode, kecil.get("content-type"), kecil.get("content-length"), isi)


def _ajukan(server, kelompok_id: str, kode: str, *, akun=AKUN_A, ip: str | None = None,
            token: str | None = None):
    tok = ambil_token(server, akun, f"/guru/kelas/{kelompok_id}") if token is None else token
    headers = {"X-Forwarded-For": ip} if ip else None
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), akun,
                        data={"kode": kode, "token": tok}, headers=headers)


def _anak_keluarga_lain(server, kode_id_unused=None) -> KondisiTautan:
    """Anak kedua dengan order Mini lunas dan kode sendiri, milik keluarga yang nanti dihapus."""
    auth.tambah_akun(LOGIN_KELUARGA_LAIN, SANDI_KELUARGA_LAIN, "guru")
    siswa = tambah_anak(server, "Anak Sintetis Lain", LOGIN_KELUARGA_LAIN, None)
    murid = tambah_murid(login="anak-lain", siswa_id=siswa)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_kit.lunas(kon, siswa, "mini", n=2, akun=murid["id_akun"], sekarang=KINI)
        kon.commit()
    return KondisiTautan(kelompok_id="", siswa_id=siswa, murid_id=murid["id_akun"], guru_id="")


def _anak_tanpa_order(server) -> KondisiTautan:
    siswa = tambah_anak(server, "Anak Sintetis Tanpa Order", AKUN_A[0], None)
    murid = tambah_murid(login="anak-tanpa-order", siswa_id=siswa)
    return KondisiTautan(kelompok_id="", siswa_id=siswa, murid_id=murid["id_akun"], guru_id="")


def _skenario_kode_salah(server, kondisi, kode_id, db) -> str:
    return KODE_LAIN


def _skenario_kode_non_ascii(server, kondisi, kode_id, db) -> str:
    return "ÀBCD2345EFGH6789"


def _skenario_kode_terlalu_panjang(server, kondisi, kode_id, db) -> str:
    return "A" * 70


def _skenario_kode_kosong(server, kondisi, kode_id, db) -> str:
    return ""


def _skenario_kode_dicabut(server, kondisi, kode_id, db) -> str:
    dasar.cabut_kode(akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id, kode_id_aktif=kode_id,
                     oleh=kondisi.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=SESUDAH, path=db)
    return KODE


def _skenario_kode_diganti(server, kondisi, kode_id, db) -> str:
    dasar.ganti_kode(akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id, kode_id_aktif=kode_id,
                     kode_hash_baru=aturan.hash_kode(KODE_LAIN), oleh=kondisi.murid_id,
                     peran=aturan.PERAN_ORANG_TUA, pada=SESUDAH, path=db)
    return KODE


def _skenario_tanpa_order_mini(server, kondisi, kode_id, db) -> str:
    anak = _anak_tanpa_order(server)
    dasar.buat_kode(akun_id=anak.murid_id, siswa_id=anak.siswa_id, kode_hash=aturan.hash_kode(KODE_LAIN),
                    oleh=anak.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=KINI, path=db)
    return KODE_LAIN


def _skenario_anak_dihapus(server, kondisi, kode_id, db) -> str:
    anak = _anak_keluarga_lain(server)
    dasar.buat_kode(akun_id=anak.murid_id, siswa_id=anak.siswa_id, kode_hash=aturan.hash_kode(KODE_LAIN),
                    oleh=anak.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=KINI, path=db)
    hapus_keluarga_sintetis(LOGIN_KELUARGA_LAIN)
    return KODE_LAIN


def _skenario_jeda_tolak(server, kondisi, kode_id, db) -> str:
    _ajukan(server, kondisi.kelompok_id, KODE)
    permintaan = dasar.daftar_untuk_guru(kondisi.guru_id, KINI, path=db)[0]
    dasar.putusan(permintaan_id=permintaan["id"], akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id,
                  hasil=aturan.HASIL_TOLAK, oleh=kondisi.murid_id, pada=KINI, path=db)
    return KODE


def _skenario_duplikat_menunggu(server, kondisi, kode_id, db) -> str:
    _ajukan(server, kondisi.kelompok_id, KODE)
    return KODE


def _pastikan_akun_ada_tapi_anak_tak_dihitung(kondisi) -> None:
    """Syarat skenario: nama login masih ada, jadi yang menolak hanya `anak_masih_ada`, bukan `nama_login`."""
    assert guru_tautan_anak.nama_login(kondisi.murid_id) == LOGIN_ANAK
    assert guru_tautan_anak.anak_masih_ada(kondisi.murid_id, kondisi.siswa_id) is False


def _ubah_akun_murid(pengguna: str, **kunci) -> None:
    """Ubah satu akun murid di berkas auth secara mentah; berkas dibaca ulang setiap permintaan."""
    berkas = auth.BERKAS_SANDI
    data = json.loads(berkas.read_text(encoding="utf-8"))
    for akun in data["akun"]:
        if akun["pengguna"] == pengguna:
            akun.update(kunci)
    berkas.write_text(json.dumps(data), encoding="utf-8")


def _skenario_akun_murid_nonaktif(server, kondisi, kode_id, db) -> str:
    _ubah_akun_murid(LOGIN_ANAK, dinonaktifkan=True)
    assert auth.cari_akun(LOGIN_ANAK).get("dinonaktifkan") is True
    _pastikan_akun_ada_tapi_anak_tak_dihitung(kondisi)
    return KODE


def _skenario_siswa_dianonimkan(server, kondisi, kode_id, db) -> str:
    with server.buka() as kon:
        kon.execute("UPDATE siswa SET nama='Dihapus-1' WHERE id=?", (kondisi.siswa_id,))
        kon.commit()
    _pastikan_akun_ada_tapi_anak_tak_dihitung(kondisi)
    return KODE


SKENARIO_GAGAL: dict[str, Callable] = {
    "kode_salah": _skenario_kode_salah,
    "kode_non_ascii": _skenario_kode_non_ascii,
    "kode_terlalu_panjang": _skenario_kode_terlalu_panjang,
    "kode_kosong": _skenario_kode_kosong,
    "kode_dicabut": _skenario_kode_dicabut,
    "kode_diganti": _skenario_kode_diganti,
    "tanpa_order_mini": _skenario_tanpa_order_mini,
    "anak_dihapus": _skenario_anak_dihapus,
    "jeda_tolak": _skenario_jeda_tolak,
    "duplikat_menunggu": _skenario_duplikat_menunggu,
    "akun_murid_nonaktif": _skenario_akun_murid_nonaktif,
    "siswa_dianonimkan": _skenario_siswa_dianonimkan,
}


@pytest.mark.parametrize("nama", list(SKENARIO_GAGAL))
def test_setiap_kegagalan_kode_byte_identik_dan_mencatat_satu_percobaan(server, jam, tmp_path, monkeypatch, nama):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kode_id = buat_kode_anak(kondisi)
    kode_uji = SKENARIO_GAGAL[nama](server, kondisi, kode_id, db)
    sebelum = keadaan_tautan(db)
    hash_admin = _hash_berkas(admin_store.BAWAAN)

    referensi = _ajukan(server, kondisi.kelompok_id, KODE_REF)
    setelah_referensi = keadaan_tautan(db)
    uji = _ajukan(server, kondisi.kelompok_id, kode_uji)
    setelah_uji = keadaan_tautan(db)

    assert _jawaban(uji) == _jawaban(referensi)
    assert _jawaban(referensi)[0] == 400
    assert "Location" not in uji[2]
    for tabel in ("kode_anak", "kode_cabut", "permintaan", "putusan"):
        assert setelah_referensi[tabel] == sebelum[tabel], tabel
        assert setelah_uji[tabel] == setelah_referensi[tabel], tabel
    assert setelah_referensi["percobaan_gagal"] == sebelum["percobaan_gagal"] + 1
    assert setelah_uji["percobaan_gagal"] == setelah_referensi["percobaan_gagal"] + 1
    assert _hash_berkas(admin_store.BAWAAN) == hash_admin, "DB admin tidak boleh berubah oleh kegagalan kode"


def test_kontrol_anak_kedua_sah_sebelum_dihapus(server, jam, tmp_path, monkeypatch):
    """Kontrol positif skenario `anak_dihapus`: tanpa penghapusan, kode anak kedua diterima. Dengan begitu
    kegagalan skenario itu disebabkan penghapusan, bukan oleh order atau kode yang memang tidak valid."""
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    anak = _anak_keluarga_lain(server)
    dasar.buat_kode(akun_id=anak.murid_id, siswa_id=anak.siswa_id, kode_hash=aturan.hash_kode(KODE_LAIN),
                    oleh=anak.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=KINI, path=db)

    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE_LAIN)

    assert kode == 200
    assert baris_tabel(db, "percobaan_gagal") == 0


def test_404_403_dan_429_ip_tidak_membuat_berkas_tautan(server, jam, tmp_path, monkeypatch):
    """Sebelum kode pernah terbit, jawaban 404, 403, dan 429 (per IP) tidak membuat `guru-tautan.db`."""
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    for _ in range(aturan.GAGAL_PER_IP):
        laju.catat_gagal(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK)

    hasil_404 = minta_mentah(server, JALUR_TAUTAN.format(klp=KELOMPOK_TIDAK_ADA), AKUN_A,
                             data={"kode": KODE, "token": "tidak-dipakai"})
    hasil_403 = _ajukan(server, kondisi.kelompok_id, KODE, token="bukan-token")
    hasil_429 = _ajukan(server, kondisi.kelompok_id, KODE, ip=IP_BLOKIR)

    assert (hasil_404[0], hasil_403[0], hasil_429[0]) == (404, 403, 429)
    assert not db.exists()


def test_kegagalan_kode_juga_menambah_penghitung_ip(server, jam, tmp_path, monkeypatch):
    """Kegagalan kode mencatat ke penghitung memori per IP, bukan hanya ke DB per guru."""
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    assert laju.diblokir(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK, batas=1) is False

    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE_REF, ip=IP_BLOKIR)

    assert kode == 400
    assert laju.diblokir(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK, batas=1) is True


def test_kode_sah_tidak_mencatat_percobaan_gagal(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)

    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE)

    assert kode == 200
    assert baris_tabel(db, "percobaan_gagal") == 0


def test_429_per_guru_sama_untuk_kode_sah_dan_salah_tanpa_tulis(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    for _ in range(aturan.GAGAL_PER_GURU):
        dasar.catat_gagal(guru_id=kondisi.guru_id, pada=KINI, path=db)
    sebelum = keadaan_tautan(db)

    sah = _ajukan(server, kondisi.kelompok_id, KODE)
    salah = _ajukan(server, kondisi.kelompok_id, KODE_REF)

    assert sah[0] == 429
    assert _jawaban(sah) == _jawaban(salah)
    assert keadaan_tautan(db) == sebelum


def test_429_per_ip_sama_untuk_kode_sah_dan_salah_tanpa_tulis(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    for _ in range(aturan.GAGAL_PER_IP):
        laju.catat_gagal(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK)
    sebelum = keadaan_tautan(db)

    sah = _ajukan(server, kondisi.kelompok_id, KODE, ip=IP_BLOKIR)
    salah = _ajukan(server, kondisi.kelompok_id, KODE_REF, ip=IP_BLOKIR)

    assert sah[0] == 429
    assert _jawaban(sah) == _jawaban(salah)
    assert keadaan_tautan(db) == sebelum
    # Permintaan yang diblokir tidak menambah hitungan IP: tepat batas, belum batas+1.
    assert laju.diblokir(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK,
                         batas=aturan.GAGAL_PER_IP + 1) is False


def test_ip_lain_tetap_bisa_mengajukan_saat_satu_ip_diblokir(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    for _ in range(aturan.GAGAL_PER_IP):
        laju.catat_gagal(tautan.NAMA_LAJU_IP, IP_BLOKIR, jendela=aturan.JENDELA_IP_DETIK)

    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE, ip=IP_LAIN)

    assert kode == 200


def test_token_salah_dan_aksi_lain_403_tanpa_hitungan(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    ambil_token(server, AKUN_A, f"/guru/kelas/{kondisi.kelompok_id}")
    sebelum = keadaan_tautan(db)
    from sessions import principal_basic
    token_aksi_lain = tautan._buat_token(principal_basic(*AKUN_A), None, KELOMPOK_TIDAK_ADA)

    rusak = _ajukan(server, kondisi.kelompok_id, KODE, token="bukan-token")
    lain = _ajukan(server, kondisi.kelompok_id, KODE, token=token_aksi_lain)

    assert rusak[0] == 403 and lain[0] == 403
    assert keadaan_tautan(db) == sebelum


def test_auth_tak_terbaca_membuat_kode_tidak_berfungsi(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)

    def _rusak(_path):
        raise OSError("berkas auth tidak bisa dibaca")

    monkeypatch.setattr(guru_tautan_anak, "_baca_akun", _rusak)

    kode, isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE)

    assert kode == 400
    assert baris_tabel(db, "permintaan") == 0
    assert baris_tabel(db, "percobaan_gagal") == 1


def test_kode_tidak_masuk_log_atau_jawaban(server, jam, tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kode_id = buat_kode_anak(kondisi)
    dasar.cabut_kode(akun_id=kondisi.murid_id, siswa_id=kondisi.siswa_id, kode_id_aktif=kode_id,
                     oleh=kondisi.murid_id, peran=aturan.PERAN_ORANG_TUA, pada=SESUDAH,
                     path=tmp_path / "guru-tautan-uji.db")

    _kode, isi_dashed, _h = _ajukan(server, kondisi.kelompok_id, "ABCD-2345-EFGH-6789")
    _kode2, isi_kecil, _h2 = _ajukan(server, kondisi.kelompok_id, "abcd2345efgh6789")

    teks_log = caplog.text.upper()
    for kandidat in ("ABCD-2345-EFGH-6789", "ABCD2345EFGH6789", "ABCD-2345"):
        assert kandidat not in teks_log
        assert kandidat not in isi_dashed.upper() and kandidat not in isi_kecil.upper()


# --- isian longgar, daftar per kelompok, dan galat tak terduga -------------------------------

def _kirim_isian(server, kelompok_id: str, isian: dict):
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), AKUN_A, data=isian)


def _siapkan_isian_sah(server, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    tok = ambil_token(server, AKUN_A, f"/guru/kelas/{kondisi.kelompok_id}")
    return db, kondisi, tok


def _assert_ditolak_di_form(uji, referensi, db, sebelum) -> None:
    """Isian longgar dijawab persis seperti isian tak lengkap (`_tolak_isian`), bukan halaman kegagalan kode, tanpa efek."""
    assert _jawaban(referensi)[0] == 400
    assert _jawaban(uji) == _jawaban(referensi)
    assert halaman.JUDUL_GAGAL not in uji[1]
    assert keadaan_tautan(db) == sebelum


def test_isian_berlebih_ditolak_form_tanpa_efek(server, jam, tmp_path, monkeypatch):
    db, kondisi, tok = _siapkan_isian_sah(server, tmp_path, monkeypatch)
    referensi = _kirim_isian(server, kondisi.kelompok_id, {"kode": KODE})
    sebelum = keadaan_tautan(db)

    uji = _kirim_isian(server, kondisi.kelompok_id, {"kode": KODE, "token": tok, "catatan": "lain"})

    _assert_ditolak_di_form(uji, referensi, db, sebelum)


def test_isian_tanpa_kode_ditolak_form_tanpa_efek(server, jam, tmp_path, monkeypatch):
    db, kondisi, tok = _siapkan_isian_sah(server, tmp_path, monkeypatch)
    referensi = _kirim_isian(server, kondisi.kelompok_id, {"kode": KODE})
    sebelum = keadaan_tautan(db)

    uji = _kirim_isian(server, kondisi.kelompok_id, {"token": tok})

    _assert_ditolak_di_form(uji, referensi, db, sebelum)


def _halaman_kelas(server, kelompok_id: str) -> str:
    kode, isi, _headers = minta_mentah(server, f"/guru/kelas/{kelompok_id}", AKUN_A)
    assert kode == 200, kode
    return isi


def _bagian_permintaan(isi: str) -> str:
    """Hanya bagian 'Permintaan kode anak' di detail kelas, supaya teks di bagian lain tidak ikut terhitung."""
    return isi.split('aria-label="Permintaan kode anak"', 1)[1].split("</section>", 1)[0]


def _buat_kelompok_lain(guru_id: str) -> str:
    """Kelompok Mini kedua milik guru yang sama; nama dan jam mulai berbeda dari kelompok pertama."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelompok = js.buat_kelompok(kon, ADMIN, nama="Mini Beta", lokasi=LOKASI, guru_id=guru_id,
                                    kuota=5, tanggal="2026-11-27", jam=JAM_KELOMPOK, sekarang=kelas_kit.KINI)
        kon.commit()
    return kelompok


def test_daftar_permintaan_hanya_tampil_di_kelompok_pemiliknya(server, jam, tmp_path, monkeypatch):
    siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    kelompok_lain = _buat_kelompok_lain(kondisi.guru_id)
    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE)
    assert kode == 200

    bagian_a = _bagian_permintaan(_halaman_kelas(server, kondisi.kelompok_id))
    bagian_b = _bagian_permintaan(_halaman_kelas(server, kelompok_lain))

    assert bagian_a.count("<li>") == 1, "kontrol: permintaan di kelompok asalnya harus tampil"
    assert bagian_b.count("<li>") == 0
    assert halaman.COPY_KOSONG_PERMINTAAN in bagian_b


def test_galat_tak_terduga_di_ajukan_dijawab_seperti_kode_salah(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    buat_kode_anak(kondisi)
    referensi = _ajukan(server, kondisi.kelompok_id, KODE_REF)
    sebelum = keadaan_tautan(db)
    dipanggil = []

    def _meledak(*, guru_id, kelompok_id, kode_id, pada, path=None):
        dipanggil.append(kode_id)
        raise RuntimeError("galat uji di dalam ajukan")

    monkeypatch.setattr(dasar, "ajukan", _meledak)
    uji = _ajukan(server, kondisi.kelompok_id, KODE)

    setelah = keadaan_tautan(db)
    assert len(dipanggil) == 1, "kode sah harus sampai ke ajukan, bukan ditolak gerbang sebelumnya"
    assert _jawaban(referensi)[0] == 400
    assert _jawaban(uji) == _jawaban(referensi)
    assert setelah["permintaan"] == sebelum["permintaan"] == 0
    assert setelah["percobaan_gagal"] == sebelum["percobaan_gagal"] + 1, "tepat satu percobaan gagal tercatat"


# --- kuota 10 permintaan per hari per kode (PERMINTAAN_PER_KODE, JENDELA_KODE) ----------------

def _guru_sintetis(nomor: int) -> str:
    """ID akun guru berbentuk sah (`akun_` + 32 hex) yang tidak pernah diterbitkan `auth`."""
    return f"akun_{nomor:032x}"


def _isi_permintaan(db, kondisi, kode_id: int, jumlah: int) -> None:
    """Isi `jumlah` permintaan lewat `dasar.ajukan`. Tiap baris dari guru sintetis berbeda: satu permintaan menunggu
    per (guru, anak), jadi guru HTTP (AKUN_A) harus tetap bebas dari permintaan menunggu."""
    for nomor in range(jumlah):
        dasar.ajukan(guru_id=_guru_sintetis(nomor), kelompok_id=kondisi.kelompok_id, kode_id=kode_id,
                     pada=KINI, path=db)


def test_kuota_kode_permintaan_ke_sepuluh_lewat_http_masih_sukses(server, jam, tmp_path, monkeypatch):
    """Kontrol positif: dengan sembilan permintaan tersimpan, permintaan HTTP ke-10 untuk kode yang sama diterima."""
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kode_id = buat_kode_anak(kondisi)
    _isi_permintaan(db, kondisi, kode_id, aturan.PERMINTAAN_PER_KODE - 1)

    kode, _isi, _headers = _ajukan(server, kondisi.kelompok_id, KODE)

    assert kode == 200
    assert baris_tabel(db, "permintaan") == aturan.PERMINTAAN_PER_KODE


def test_kuota_kode_permintaan_ke_sebelas_dijawab_seperti_kegagalan_generik(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kode_id = buat_kode_anak(kondisi)
    _isi_permintaan(db, kondisi, kode_id, aturan.PERMINTAAN_PER_KODE)
    referensi = _ajukan(server, kondisi.kelompok_id, KODE_REF)
    sebelum = keadaan_tautan(db)

    uji = _ajukan(server, kondisi.kelompok_id, KODE)

    setelah = keadaan_tautan(db)
    assert _jawaban(referensi)[0] == 400
    assert _jawaban(uji) == _jawaban(referensi)
    assert "Location" not in uji[2]
    assert setelah["permintaan"] == sebelum["permintaan"] == aturan.PERMINTAAN_PER_KODE
    assert setelah["kode_anak"] == sebelum["kode_anak"]
    assert setelah["percobaan_gagal"] == sebelum["percobaan_gagal"] + 1, "tepat satu percobaan gagal tercatat"


def test_kuota_kode_pulih_setelah_lebih_dari_24_jam(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kode_id = buat_kode_anak(kondisi)
    _isi_permintaan(db, kondisi, kode_id, aturan.PERMINTAAN_PER_KODE)
    penuh = _ajukan(server, kondisi.kelompok_id, KODE)
    assert penuh[0] == 400, "kontrol: sebelum jendela lewat, kuota masih penuh"

    jam.maju_jam(25)
    pulih = _ajukan(server, kondisi.kelompok_id, KODE)

    assert pulih[0] == 200
    assert baris_tabel(db, "permintaan") == aturan.PERMINTAAN_PER_KODE + 1
