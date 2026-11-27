"""Koreksi admin atas kehadiran dan jurnal pertemuan (2b) lewat HTTP: akses, urutan POST, dan tanpa efek samping.

Server HTTP sungguhan (`server` dari cek_http_kit) dengan data sepenuhnya sintetis: guru A dan B, murid, dan admin dari
cek_http_kit; anak buatan; jam lewat fixture `jam`. Catatan pertemuan di GURU_PERTEMUAN_DB sementara (tmp_path).
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import pytest

import admin_jurnal_koreksi_http as kh
import admin_store
import auth
import form_token
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import guru_pertemuan_http as gph
import jadwal_store as js
import kelas_kit
import learning_cycle_http
import schema_jadwal
import schema_tagihan_catatan
import sessions
from admin_pesanan_kit import id_admin, login_admin, minta_admin
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah, server, tambah_anak  # noqa: F401
from harian_kit import jam  # noqa: F401
from kelas_http_kit import pasang_skema

ADMIN_JADWAL = "admin_sintetis"
LOKASI_MEET = "https://meet.google.com/abc-defg-hij"
RUTE_LAMA = "/admin/jadwal/jurnal"
TAK_ADA = "/admin/tidak-ada"
RUTE_GURU = "/guru/pertemuan/"
GURU_TAK_ADA = "/guru/tidak-ada"
KINI_AWAL = "2026-11-23T03:00:00"  # Mini ke-1 (21 Nov) sudah mulai, Private ke-1 (25 Nov) belum
TOPIK = aturan.daftar_topik_jurnal()[0]
TOPIK_BARU = aturan.daftar_topik_jurnal()[1]
HARI_LEWAT_JENDELA = 30
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
POLA_HANDLE = re.compile(r'name="anak_([0-9a-f]{16})"')
POLA_ID_MENTAH = re.compile(r"kor_|klp_|akun_|siswa_id|order_id")
TEKS_TERSIMPAN = "Koreksi tersimpan."
TEKS_BELUM_MULAI = "belum dimulai"
TEKS_DIBATALKAN = "dibatalkan"
TEKS_TERKUNCI = "sudah ditutup"
LABEL_KOREKSI_ADMIN = "Koreksi admin"
LABEL_CATATAN_GURU = "Catatan guru: guru"


# --- data sintetis ----------------------------------------------------------------------------

def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN_JADWAL, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, guru, siswa, n, tanggal="2026-11-25", jam_wib="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN_JADWAL, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam_wib,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _pertemuan(kon, kolom: str, nilai, ke: int):
    """Baris pertemuan (id, mulai, menit) untuk kelompok (`kelompok_id`) atau order Private (`order_id`)."""
    return kon.execute("SELECT id, mulai, menit FROM jadwal_pertemuan WHERE %s=? AND ke=?" % kolom,
                       (nilai, ke)).fetchone()


def _isi_contoh(server):
    """Guru A: Mini Alfa (anak Alfa) dan Private (anak Beta). Guru B: Mini Beta (anak Gamma) dan Private (Delta)."""
    anak = {
        "alfa": tambah_anak(server, "Anak Sintetis Alfa", "guru", None),
        "beta": tambah_anak(server, "Anak Sintetis Beta", "guru", None),
        "gamma": tambah_anak(server, "Anak Sintetis Gamma", "guru-b", None),
        "delta": tambah_anak(server, "Anak Sintetis Delta", "guru-b", None),
    }
    guru_a, guru_b = id_akun(AKUN_A), id_akun(AKUN_B)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid_a = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Alfa", lokasi=LOKASI_MEET, guru_id=guru_a, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kid_b = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Beta", lokasi=LOKASI_MEET, guru_id=guru_b, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        ord_alfa = _tempatkan_mini(kon, kid_a, anak["alfa"], n=1)
        ord_beta = _tempatkan_privat(kon, guru_a, anak["beta"], n=2)
        ord_gamma = _tempatkan_mini(kon, kid_b, anak["gamma"], n=3)
        ord_delta = _tempatkan_privat(kon, guru_b, anak["delta"], n=4, tanggal="2026-11-26", jam_wib="10:00")
        kon.commit()
        mini_a1 = _pertemuan(kon, "kelompok_id", kid_a, 1)
        privat_a1 = _pertemuan(kon, "order_id", ord_beta, 1)
        mini_b1 = _pertemuan(kon, "kelompok_id", kid_b, 1)
        return {
            "kid_a": kid_a, "kid_b": kid_b,
            "ord_alfa": ord_alfa, "ord_beta": ord_beta, "ord_gamma": ord_gamma, "ord_delta": ord_delta,
            "mini_a1": mini_a1[0], "mini_a1_mulai": mini_a1[1],
            "privat_a1": privat_a1[0], "privat_a1_mulai": privat_a1[1],
            "mini_b1": mini_b1[0],
        }


@pytest.fixture()
def berkas_catatan(tmp_path, monkeypatch):
    """Berkas catatan pertemuan sementara; belum ada sampai tulis pertama."""
    berkas = tmp_path / "guru-pertemuan.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    return berkas


@pytest.fixture()
def jadwal(server, jam, berkas_catatan):
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)
    jam.nilai = KINI_AWAL
    return _isi_contoh(server)


@pytest.fixture()
def admin(jadwal, server):
    return login_admin(server)


# --- util ---------------------------------------------------------------------------------------

def _jalur(pertemuan_id) -> str:
    return f"{kh.RUTE_PREFIX}{pertemuan_id}"


def _jalur_guru(pertemuan_id) -> str:
    return f"{RUTE_GURU}{pertemuan_id}"


def _hash(path):
    """Hash isi berkas, atau None bila berkas belum ada (tanpa membuatnya)."""
    berkas = Path(path)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _keadaan_db() -> tuple:
    """Hash DB admin dan berkas catatan: dipakai untuk membuktikan penolakan tanpa efek samping."""
    return _hash(admin_store.BAWAAN), _hash(_berkas_catatan())


def _berkas_catatan() -> Path:
    return Path(os.environ[dasar.ENV_DB])


def _hitung_baris(path):
    """(jumlah jurnal, jumlah hadir) dibaca mode ro."""
    kon = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return tuple(kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]
                     for tabel in ("pertemuan_jurnal", "pertemuan_hadir"))
    finally:
        kon.close()


def _kunci_mini_a1(jadwal) -> str:
    return aturan.kunci_pertemuan(jadwal["kid_a"], 1)


def _kunci_privat_a1(jadwal) -> str:
    return aturan.kunci_pertemuan(jadwal["ord_beta"], 1)


def _riwayat_mini_a1(jadwal):
    return dasar.riwayat(_kunci_mini_a1(jadwal), jadwal["mini_a1_mulai"])


def _principal(akun):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal


def _principal_cookie(cookie):
    principal = sessions.ambil_principal(cookie, path=sessions.BERKAS_SESI, path_akun=auth.BERKAS_SANDI)
    assert principal is not None
    return principal


def _token_admin(cookie, pertemuan_id) -> str:
    """Token sah untuk admin sesi `cookie` dan pertemuan itu, dibuat dari modul token (bukan dari halaman)."""
    return form_token.buat_token(_principal_cookie(cookie), cookie, domain=kh.DOMAIN_TOKEN,
                                 aksi=f"koreksi:{pertemuan_id}")


def _halaman_admin(server, pertemuan_id, cookie) -> str:
    kode, isi, _ = minta_admin(server, _jalur(pertemuan_id), cookie)
    assert kode == 200, kode
    return isi


def _form_dari_halaman(isi: str, topik: str = TOPIK, status: str = "hadir") -> dict:
    """Isian lengkap seperti peramban: token, topik, dan satu status untuk setiap handle anak di halaman."""
    data = {"token": POLA_TOKEN.search(isi).group(1), "topik": topik}
    for handle in sorted(set(POLA_HANDLE.findall(isi))):
        data["anak_" + handle] = status
    return data


def _kirim_admin(server, pertemuan_id, data, cookie):
    return minta_admin(server, _jalur(pertemuan_id), cookie, data)


def _catat_guru(server, pertemuan_id, status="hadir", topik=TOPIK, akun=AKUN_A):
    kode, isi, _ = server.minta(_jalur_guru(pertemuan_id), auth=akun)
    assert kode == 200, kode
    data = _form_dari_halaman(isi, topik=topik, status=status)
    return minta_mentah(server, _jalur_guru(pertemuan_id), akun, data)


def _token_guru(pertemuan_id, akun=AKUN_A) -> str:
    """Token guru sah untuk pertemuan itu (domain guru), dibuat dari modul token. Dipakai bila halaman guru terkunci."""
    return form_token.buat_token(_principal(akun), None, domain=gph.DOMAIN_TOKEN_PERTEMUAN,
                                 aksi=f"pertemuan:{pertemuan_id}")


def _majukan_jam(jam, mulai: str, hari: int) -> None:
    waktu = datetime.strptime(mulai, aturan.FORMAT_WAKTU) + timedelta(days=hari)
    jam.nilai = waktu.strftime(aturan.FORMAT_WAKTU)


def _ubah_pertemuan(pertemuan_id: int, kolom_nilai: str) -> None:
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET %s WHERE id=?" % kolom_nilai, (pertemuan_id,))
        kon.commit()


# --- akses: 404 identik dan tanpa efek samping ----------------------------------------------------

AKUN_NON_ADMIN = [
    pytest.param(None, id="anonim"),
    pytest.param(AKUN_A, id="guru_pemilik"),
    pytest.param(AKUN_B, id="guru_lain"),
    pytest.param(AKUN_MURID, id="murid"),
]


@pytest.mark.parametrize("akun", AKUN_NON_ADMIN)
def test_get_non_admin_404_identik_dengan_rute_tak_dikenal(server, jadwal, akun):
    acuan = minta_mentah(server, TAK_ADA, akun)
    for pertemuan_id in (jadwal["mini_a1"], jadwal["privat_a1"]):
        kode, isi, _ = minta_mentah(server, _jalur(pertemuan_id), akun)
        assert (kode, isi) == acuan[:2], pertemuan_id


@pytest.mark.parametrize("akun", AKUN_NON_ADMIN)
def test_post_non_admin_404_identik_dan_tanpa_tulis(server, jadwal, berkas_catatan, akun):
    data = {"token": "x", "topik": TOPIK, "anak_0123456789abcdef": "hadir"}
    acuan = minta_mentah(server, TAK_ADA, akun, data)
    sebelum = _keadaan_db()

    kode, isi, _ = minta_mentah(server, _jalur(jadwal["mini_a1"]), akun, data)

    assert (kode, isi) == acuan[:2]
    assert _keadaan_db() == sebelum
    assert not berkas_catatan.exists()


def test_mode_lokal_tanpa_principal_404_identik(server, jadwal, monkeypatch):
    acuan = minta_mentah(server, TAK_ADA)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)

    kode, isi, _ = minta_mentah(server, _jalur(jadwal["mini_a1"]))

    assert (kode, isi) == acuan[:2]


def test_mode_lokal_post_404_identik_tanpa_tulis(server, jadwal, berkas_catatan, monkeypatch):
    data = {"token": "x", "topik": TOPIK}
    acuan = minta_mentah(server, TAK_ADA, None, data)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)
    sebelum = _keadaan_db()

    kode, isi, _ = minta_mentah(server, _jalur(jadwal["mini_a1"]), None, data)

    assert (kode, isi) == acuan[:2]
    assert _keadaan_db() == sebelum


def test_admin_basic_get_hanya_baca_tanpa_token(server, jadwal):
    kode, isi, _ = minta_mentah(server, _jalur(jadwal["mini_a1"]), AKUN_ADMIN)

    assert kode == 200
    assert POLA_TOKEN.search(isi) is None


def test_admin_basic_post_403_walau_token_sah(server, jadwal, berkas_catatan):
    token = form_token.buat_token(_principal(AKUN_ADMIN), None, domain=kh.DOMAIN_TOKEN,
                                  aksi=f"koreksi:{jadwal['mini_a1']}")
    data = {"token": token, "topik": TOPIK_BARU}
    sebelum = _keadaan_db()

    kode, _isi, _ = minta_mentah(server, _jalur(jadwal["mini_a1"]), AKUN_ADMIN, data)

    assert kode == 403
    assert _keadaan_db() == sebelum


def test_admin_cookie_di_rute_guru_404_identik_dengan_rute_tak_dikenal(server, jadwal, admin):
    acuan = minta_admin(server, GURU_TAK_ADA, admin)
    kode, isi, _ = minta_admin(server, _jalur_guru(jadwal["mini_a1"]), admin)
    assert (kode, isi) == acuan[:2]


@pytest.mark.parametrize("sufiks", ["0", "01", "abc", "1x", "+1", "-1", "9" * 13, "9999999"])
def test_get_id_cacat_atau_tak_ada_404_identik(server, jadwal, admin, sufiks):
    acuan = minta_admin(server, TAK_ADA, admin)
    kode, isi, _ = minta_admin(server, kh.RUTE_PREFIX + sufiks, admin)
    assert (kode, isi) == acuan[:2]


@pytest.mark.parametrize("sufiks", ["0", "01", "abc", "1x", "9" * 13])
def test_post_id_cacat_404_identik_sebelum_token_diperiksa(server, jadwal, admin, sufiks):
    data = {"token": "x", "topik": TOPIK}
    acuan = minta_admin(server, TAK_ADA, admin, data)
    kode, isi, _ = minta_admin(server, kh.RUTE_PREFIX + sufiks, admin, data)
    assert (kode, isi) == acuan[:2]


def test_post_id_tak_ada_dengan_token_sah_404_identik_tanpa_tulis(server, jadwal, admin, berkas_catatan):
    """Urutan POST: token diperiksa dulu, lalu pertemuan dimuat. Token sah ke id yang tak ada = 404 identik."""
    sufiks = "9999999"
    data = {"token": _token_admin(admin, sufiks), "topik": TOPIK}
    acuan = minta_admin(server, TAK_ADA, admin, data)
    sebelum = _keadaan_db()

    kode, isi, _ = minta_admin(server, kh.RUTE_PREFIX + sufiks, admin, data)

    assert (kode, isi) == acuan[:2]
    assert _keadaan_db() == sebelum


@pytest.mark.parametrize("query", ["x=1", "pesan=lain", "pesan="])
def test_query_selain_pesan_tersimpan_404(server, jadwal, admin, query):
    acuan = minta_admin(server, TAK_ADA, admin)
    kode, isi, _ = minta_admin(server, _jalur(jadwal["mini_a1"]) + "?" + query, admin)
    assert (kode, isi) == acuan[:2]


def test_rute_lama_jurnal_tetap_200_untuk_admin_dan_menolak_query(server, jadwal, admin):
    assert minta_admin(server, RUTE_LAMA, admin)[0] == 200
    assert minta_admin(server, RUTE_LAMA + "?x=1", admin)[0] == 404


# --- tampilan admin (GET) -----------------------------------------------------------------------

def test_admin_melihat_form_topik_dan_tiga_radio_per_anak(server, jadwal, admin):
    isi = _halaman_admin(server, jadwal["mini_a1"], admin)

    assert 'name="topik"' in isi and 'name="token"' in isi
    assert "Mini Class: Mini Alfa" in isi
    assert "Anak Sintetis Alfa" in isi
    assert isi.count('type="radio"') == 3
    assert len(set(POLA_HANDLE.findall(isi))) == 1


def test_form_mini_hanya_memuat_anggota_kelompok_itu(server, jadwal, admin):
    isi_a = _halaman_admin(server, jadwal["mini_a1"], admin)
    isi_b = _halaman_admin(server, jadwal["mini_b1"], admin)

    assert "Anak Sintetis Gamma" not in isi_a
    assert "Anak Sintetis Alfa" not in isi_b
    assert "Anak Sintetis Gamma" in isi_b


def test_private_menampilkan_satu_anak_dan_judul_private(server, jadwal, admin, jam):
    jam.nilai = jadwal["privat_a1_mulai"]  # sudah mulai: formulir tampil
    isi = _halaman_admin(server, jadwal["privat_a1"], admin)

    assert "Private: Anak Sintetis Beta" in isi
    assert isi.count('type="radio"') == 3


def test_halaman_admin_tanpa_id_mentah_dan_tanpa_id_admin(server, jadwal, admin):
    isi = _halaman_admin(server, jadwal["mini_a1"], admin)

    assert POLA_ID_MENTAH.search(isi) is None
    assert jadwal["ord_alfa"] not in isi
    assert id_admin() not in isi


def test_get_tidak_membuat_berkas_catatan_dan_tidak_mengubah_db(server, jadwal, admin, berkas_catatan):
    sebelum = _keadaan_db()

    _halaman_admin(server, jadwal["mini_a1"], admin)
    _halaman_admin(server, jadwal["privat_a1"], admin)

    assert _keadaan_db() == sebelum
    assert not berkas_catatan.exists()


def test_pesan_tersimpan_menampilkan_banner(server, jadwal, admin):
    kode, isi, _ = minta_admin(server, _jalur(jadwal["mini_a1"]) + "?pesan=tersimpan", admin)

    assert kode == 200
    assert TEKS_TERSIMPAN in isi


def test_belum_mulai_baca_saja_tanpa_form_dan_post_409_tanpa_tulis(server, jadwal, admin, berkas_catatan):
    isi = _halaman_admin(server, jadwal["privat_a1"], admin)
    assert TEKS_BELUM_MULAI in isi
    assert POLA_TOKEN.search(isi) is None
    sebelum = _keadaan_db()

    data = {"token": _token_admin(admin, jadwal["privat_a1"]), "topik": TOPIK}
    kode, _isi, _ = _kirim_admin(server, jadwal["privat_a1"], data, admin)

    assert kode == 409
    assert _keadaan_db() == sebelum


def test_dibatalkan_baca_saja_tanpa_form_dan_post_409_tanpa_tulis(server, jadwal, admin, berkas_catatan):
    _ubah_pertemuan(jadwal["mini_a1"], "dibatalkan=1")
    isi = _halaman_admin(server, jadwal["mini_a1"], admin)
    assert TEKS_DIBATALKAN in isi
    assert POLA_TOKEN.search(isi) is None
    sebelum = _keadaan_db()

    data = {"token": _token_admin(admin, jadwal["mini_a1"]), "topik": TOPIK}
    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 409
    assert _keadaan_db() == sebelum


# --- koreksi setelah jendela 7 hari --------------------------------------------------------------

def test_koreksi_setelah_30_hari_berhasil_dan_tercatat_peran_admin(server, jadwal, admin, jam, berkas_catatan):
    assert _catat_guru(server, jadwal["mini_a1"], status="hadir")[0] == 303
    _majukan_jam(jam, jadwal["mini_a1_mulai"], HARI_LEWAT_JENDELA)
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")

    kode, _isi, tajuk = _kirim_admin(server, jadwal["mini_a1"], form, admin)

    assert kode == 303
    assert tajuk["Location"] == _jalur(jadwal["mini_a1"]) + "?pesan=tersimpan"
    riwayat = _riwayat_mini_a1(jadwal)
    assert [b["peran"] for b in riwayat["jurnal"]] == ["guru", "admin"]
    assert [b["peran"] for b in riwayat["hadir"]] == ["guru", "admin"]
    assert riwayat["jurnal"][0]["oleh"] == id_akun(AKUN_A)
    assert riwayat["jurnal"][1]["oleh"] == id_admin()
    assert riwayat["hadir"][1]["oleh"] == id_admin()
    assert riwayat["hadir"][1]["status"] == "izin"
    assert riwayat["hadir"][1]["pada"] == jam.nilai


def test_guru_tetap_terkunci_setelah_30_hari_dan_admin_tetap_404_di_rute_guru(server, jadwal, admin, jam):
    _majukan_jam(jam, jadwal["mini_a1_mulai"], HARI_LEWAT_JENDELA)

    kode, isi, _ = minta_mentah(server, _jalur_guru(jadwal["mini_a1"]), AKUN_A,
                                {"token": _token_guru(jadwal["mini_a1"]), "topik": TOPIK})

    assert kode == 409
    assert TEKS_TERKUNCI in isi
    assert minta_admin(server, _jalur_guru(jadwal["mini_a1"]), admin)[:2] == \
        minta_admin(server, GURU_TAK_ADA, admin)[:2]


def test_kirim_ulang_identik_tidak_menambah_baris(server, jadwal, admin, berkas_catatan):
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), status="izin")
    assert _kirim_admin(server, jadwal["mini_a1"], form, admin)[0] == 303
    sebelum = _hitung_baris(berkas_catatan)

    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), status="izin")
    assert _kirim_admin(server, jadwal["mini_a1"], form, admin)[0] == 303

    assert _hitung_baris(berkas_catatan) == sebelum


def test_koreksi_hanya_menambah_baris_yang_berubah(server, jadwal, admin, berkas_catatan):
    assert _catat_guru(server, jadwal["mini_a1"], status="hadir")[0] == 303
    sebelum = _hitung_baris(berkas_catatan)
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK, status="izin")

    assert _kirim_admin(server, jadwal["mini_a1"], form, admin)[0] == 303

    assert _hitung_baris(berkas_catatan) == (sebelum[0], sebelum[1] + 1)


# --- riwayat: hanya di permukaan admin ------------------------------------------------------------

def test_riwayat_admin_berurutan_dengan_nama_tanpa_id_mentah(server, jadwal, admin, jam):
    _catat_guru(server, jadwal["mini_a1"], status="hadir")
    _majukan_jam(jam, jadwal["mini_a1_mulai"], HARI_LEWAT_JENDELA)
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    _kirim_admin(server, jadwal["mini_a1"], form, admin)

    isi = _halaman_admin(server, jadwal["mini_a1"], admin)

    assert LABEL_CATATAN_GURU in isi and LABEL_KOREKSI_ADMIN in isi
    assert isi.index(LABEL_CATATAN_GURU) < isi.index(LABEL_KOREKSI_ADMIN)
    assert "Anak Sintetis Alfa: Izin" in isi
    assert aturan.label_topik(TOPIK_BARU) in isi
    assert POLA_ID_MENTAH.search(isi) is None
    assert jadwal["ord_alfa"] not in isi
    assert id_akun(AKUN_A) not in isi
    assert id_admin() not in isi


def test_hanya_koreksi_admin_yang_membaca_riwayat_pertemuan():
    """Riwayat (pelaku dan waktu koreksi) hanya dibaca permukaan admin; modul guru dan orang tua tidak memakainya."""
    akar = Path(__file__).resolve().parent.parent
    pemanggil = sorted(p.name for p in akar.glob("*.py")
                       if re.search(r"\b(dasar|catatan)\.riwayat\(", p.read_text(encoding="utf-8")))
    assert pemanggil == ["admin_jurnal_koreksi_http.py"]


def test_halaman_guru_dan_orang_tua_tidak_memuat_riwayat_admin(server, jadwal, admin, jam):
    _catat_guru(server, jadwal["mini_a1"], status="hadir")
    _majukan_jam(jam, jadwal["mini_a1_mulai"], HARI_LEWAT_JENDELA)
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    _kirim_admin(server, jadwal["mini_a1"], form, admin)
    jam.nilai = KINI_AWAL

    kode, isi, _ = server.minta(_jalur_guru(jadwal["mini_a1"]), auth=AKUN_A)

    assert kode == 200
    assert LABEL_KOREKSI_ADMIN not in isi
    assert "Catatan guru:" not in isi


# --- token -------------------------------------------------------------------------------------

def _token_variasi(nama: str, cookie: str, jadwal) -> str:
    mini = jadwal["mini_a1"]
    if nama == "acak":
        return "x"
    if nama == "domain_guru":
        return form_token.buat_token(_principal_cookie(cookie), cookie, domain=gph.DOMAIN_TOKEN_PERTEMUAN,
                                     aksi=f"pertemuan:{mini}")
    if nama == "aksi_pertemuan_lain":
        return form_token.buat_token(_principal_cookie(cookie), cookie, domain=kh.DOMAIN_TOKEN,
                                     aksi=f"koreksi:{jadwal['privat_a1']}")
    if nama == "kedaluwarsa":
        return form_token.buat_token(_principal_cookie(cookie), cookie, domain=kh.DOMAIN_TOKEN,
                                     aksi=f"koreksi:{mini}", umur=-1)
    if nama == "akun_guru":
        return form_token.buat_token(_principal(AKUN_A), None, domain=kh.DOMAIN_TOKEN, aksi=f"koreksi:{mini}")
    raise AssertionError(nama)


@pytest.mark.parametrize("nama", ["acak", "domain_guru", "aksi_pertemuan_lain", "kedaluwarsa", "akun_guru"])
def test_token_tak_sah_403_tanpa_tulis(server, jadwal, admin, berkas_catatan, nama):
    isi = _halaman_admin(server, jadwal["mini_a1"], admin)
    data = _form_dari_halaman(isi, topik=TOPIK_BARU, status="izin")
    data["token"] = _token_variasi(nama, admin, jadwal)
    sebelum = _keadaan_db()

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 403
    assert _keadaan_db() == sebelum


def test_token_hilang_403_tanpa_tulis(server, jadwal, admin, berkas_catatan):
    data = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    del data["token"]
    sebelum = _keadaan_db()

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 403
    assert _keadaan_db() == sebelum


def test_token_sah_lolos_ke_pemeriksaan_isian(server, jadwal, admin):
    """Token sah tidak ditolak 403; handle palsu baru ditolak 400 pada pemeriksaan isian."""
    data = {"token": _token_admin(admin, jadwal["mini_a1"]), "topik": TOPIK_BARU, "anak_" + "0" * 16: "izin"}
    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)
    assert kode == 400


# --- isian -------------------------------------------------------------------------------------

def _isian_variasi(nama: str, form: dict, jadwal, server, admin) -> dict:
    data = dict(form)
    kunci_anak = [k for k in data if k.startswith("anak_")]
    if nama == "berlebih":
        data["ekstra"] = "1"
    elif nama == "anak_kurang":
        del data[kunci_anak[0]]
    elif nama == "handle_asing":
        data["anak_" + "0" * 16] = data.pop(kunci_anak[0])
    elif nama == "handle_pertemuan_lain":
        handle_lain = kh.handle_anak(_principal_cookie(admin), _kunci_privat_a1(jadwal), jadwal["ord_beta"])
        data["anak_" + handle_lain] = data.pop(kunci_anak[0])
    elif nama == "status_asing":
        data[kunci_anak[0]] = "entah"
    elif nama == "status_ganda":
        data[kunci_anak[0]] = ["hadir", "izin"]
    elif nama == "topik_asing":
        data["topik"] = "campuran"
    elif nama == "topik_kosong":
        data["topik"] = ""
    elif nama == "topik_hilang":
        del data["topik"]
    else:
        raise AssertionError(nama)
    return data


@pytest.mark.parametrize("nama", ["berlebih", "anak_kurang", "handle_asing", "handle_pertemuan_lain",
                                  "status_asing", "status_ganda", "topik_asing", "topik_kosong", "topik_hilang"])
def test_isian_tidak_sah_400_tanpa_tulis(server, jadwal, admin, berkas_catatan, nama):
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    data = _isian_variasi(nama, form, jadwal, server, admin)
    sebelum = _keadaan_db()

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 400
    assert _keadaan_db() == sebelum


def _tambah_empat_anak(server, jadwal) -> None:
    """Empat anak tambahan di Mini Alfa (kuota 5): form berisi lima anak dan tujuh field."""
    for nomor, nama in enumerate(("Dua", "Tiga", "Empat", "Lima"), start=5):
        siswa = tambah_anak(server, "Anak Sintetis " + nama, "guru", None)
        with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
            _tempatkan_mini(kon, jadwal["kid_a"], siswa, n=nomor)
            kon.commit()


def test_mini_lima_anak_lengkap_tersimpan_dengan_batas_field(server, jadwal, admin, berkas_catatan):
    _tambah_empat_anak(server, jadwal)
    data = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    assert len(data) == 7

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 303
    assert [b["status"] for b in _riwayat_mini_a1(jadwal)["hadir"]] == ["izin"] * 5


def test_kiriman_parsial_satu_anak_dari_lima_ditolak_400(server, jadwal, admin, berkas_catatan):
    """Mini dengan lima anak: satu status yang hilang membuat seluruh kiriman ditolak, tanpa tulis."""
    _tambah_empat_anak(server, jadwal)
    data = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")
    data.pop(next(k for k in data if k.startswith("anak_")))
    sebelum = _keadaan_db()

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 400
    assert _keadaan_db() == sebelum


# --- galat layanan dan laju -----------------------------------------------------------------------

def test_galat_catatan_503_tanpa_tulis(server, jadwal, admin, berkas_catatan, monkeypatch):
    form = _form_dari_halaman(_halaman_admin(server, jadwal["mini_a1"], admin), topik=TOPIK_BARU, status="izin")

    def gagal(**_kwargs):
        raise dasar.GalatCatatan("uji")

    monkeypatch.setattr(dasar, "catat", gagal)
    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], form, admin)

    assert kode == 503
    assert not berkas_catatan.exists()


def test_laju_429_setelah_batas(server, jadwal, admin, monkeypatch):
    monkeypatch.setattr(learning_cycle_http, "_riwayat", {})
    monkeypatch.setattr(learning_cycle_http, "_BATAS_PER_MENIT", 2)
    data = {"token": "x", "topik": TOPIK}

    kode_1, _i, _t = _kirim_admin(server, jadwal["mini_a1"], data, admin)
    kode_2, _i, _t = _kirim_admin(server, jadwal["mini_a1"], data, admin)
    kode_3, isi_3, _t = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert (kode_1, kode_2) == (403, 403)
    assert kode_3 == 429 and "Terlalu banyak permintaan" in isi_3


def test_galat_baca_db_jadwal_503_bukan_500(server, jadwal, admin, monkeypatch):
    def gagal(*_args, **_kwargs):
        raise sqlite3.OperationalError("uji")

    monkeypatch.setattr(kh, "_muat_pertemuan", gagal)
    kode, _isi, _ = minta_admin(server, _jalur(jadwal["mini_a1"]), admin)
    assert kode == 503


def _pasang_versi_asing(berkas) -> None:
    kon = sqlite3.connect(str(berkas))
    try:
        kon.execute("PRAGMA user_version = 99")
        kon.commit()
    finally:
        kon.close()


def test_get_dengan_versi_catatan_asing_503_tanpa_form_dan_tanpa_nama(server, jadwal, admin, berkas_catatan):
    """Catatan yang tak terbaca tidak boleh tampil sebagai form kosong: admin bisa menimpa keadaan yang sebenarnya."""
    _pasang_versi_asing(berkas_catatan)

    kode, isi, _ = minta_admin(server, _jalur(jadwal["mini_a1"]), admin)

    assert kode == 503
    assert POLA_TOKEN.search(isi) is None
    assert "Anak Sintetis Alfa" not in isi


def test_post_dengan_versi_catatan_asing_503_tanpa_tulis(server, jadwal, admin, berkas_catatan):
    _pasang_versi_asing(berkas_catatan)
    handle = kh.handle_anak(_principal_cookie(admin), _kunci_mini_a1(jadwal), jadwal["ord_alfa"])
    data = {"token": _token_admin(admin, jadwal["mini_a1"]), "topik": TOPIK_BARU, "anak_" + handle: "izin"}
    sebelum = _keadaan_db()

    kode, _isi, _ = _kirim_admin(server, jadwal["mini_a1"], data, admin)

    assert kode == 503
    assert _keadaan_db() == sebelum


def _buat_mini_kosong() -> Tuple[str, tuple]:
    """Kelompok Mini tanpa penempatan: pertemuan ke-1 ada, anggotanya kosong. Mengembalikan (kid, (id, mulai, menit))."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Kosong", lokasi=LOKASI_MEET, guru_id=id_akun(AKUN_A),
                               kuota=5, tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kon.commit()
        return kid, _pertemuan(kon, "kelompok_id", kid, 1)


def test_mini_tanpa_anak_formulir_hanya_topik_dan_tersimpan_tanpa_hadir(server, jadwal, admin, berkas_catatan):
    kid, (pertemuan_id, mulai, _menit) = _buat_mini_kosong()
    isi = _halaman_admin(server, pertemuan_id, admin)
    assert "Belum ada anak di pertemuan ini" in isi
    assert isi.count('type="radio"') == 0

    kode, _isi, _ = _kirim_admin(server, pertemuan_id, _form_dari_halaman(isi, topik=TOPIK_BARU), admin)

    assert kode == 303
    riwayat = dasar.riwayat(aturan.kunci_pertemuan(kid, 1), mulai)
    assert [(b["peran"], b["topik"]) for b in riwayat["jurnal"]] == [("admin", TOPIK_BARU)]
    assert riwayat["hadir"] == []
