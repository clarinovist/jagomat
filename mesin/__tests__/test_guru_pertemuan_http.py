"""Halaman dan POST catat kehadiran & jurnal pertemuan guru lewat HTTP (Fase 2a-2).

Kasus H1-H12 dari plan Fase 2: GET pemilik, 404 identik, POST sah dan idempoten, token, handle anak, topik dan status,
jendela R1/R2, kepemilikan silang, tanpa efek samping, snapshot `mulai`, batas laju, dan galat DB. Server HTTP sungguhan
(`ServerUji`), data sepenuhnya sintetis: akun guru dan admin dari cek_http_kit, anak buatan, dan jam uji lewat fixture
`jam`. Berkas catatan pertemuan dibuat di tmp_path lewat env GURU_PERTEMUAN_DB.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import admin_store
import auth
import form_token
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import guru_pertemuan_http as gph
import jadwal_store as js
import kelas_kit
import kontak_http
import learning_cycle_http
import schema_jadwal
import schema_tagihan_catatan
import sessions
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, minta_mentah, server, tambah_anak  # noqa: F401
from harian_kit import jam  # noqa: F401
from kelas_http_kit import pasang_skema

ADMIN_JADWAL = "admin_sintetis"
LOKASI_MEET = "https://meet.google.com/abc-defg-hij"
TIDAK_ADA = "/guru/tidak-ada"
RUTE = "/guru/pertemuan/"
KINI_AWAL = "2026-11-23T03:00:00"  # sesi Mini ke-1 (21 Nov) sudah lewat, Private ke-1 (25 Nov) belum
TOPIK = aturan.daftar_topik_jurnal()[0]
TOPIK_LAINNYA = "lainnya"
POLA_TOKEN = re.compile(r'name="token" value="([^"]+)"')
POLA_HANDLE = re.compile(r'name="anak_([0-9a-f]{16})"')
POLA_ID_MENTAH = re.compile(r"kor_|klp_|akun_|siswa_id|order_id")
TEKS_TERSIMPAN = "Catatan tersimpan."
TEKS_BELUM_MULAI = "belum dimulai"
TEKS_DIBATALKAN = "dibatalkan"
TEKS_TERKUNCI = "sudah ditutup"
TEKS_TANPA_ANAK = "Belum ada anak"
STATUS_SAH = ("hadir", "izin", "tidak_hadir")


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
        _tempatkan_mini(kon, kid_b, anak["gamma"], n=3)
        ord_delta = _tempatkan_privat(kon, guru_b, anak["delta"], n=4, tanggal="2026-11-26", jam_wib="10:00")
        kon.commit()
        mini_a1 = _pertemuan(kon, "kelompok_id", kid_a, 1)
        privat_a1 = _pertemuan(kon, "order_id", ord_beta, 1)
        return {
            "kid_a": kid_a, "kid_b": kid_b, "anak": anak,
            "ord_alfa": ord_alfa, "ord_beta": ord_beta,
            "mini_a1": mini_a1[0], "mini_a1_mulai": mini_a1[1], "mini_a1_menit": mini_a1[2],
            "mini_a2": _pertemuan(kon, "kelompok_id", kid_a, 2)[0],
            "privat_a1": privat_a1[0], "privat_a1_mulai": privat_a1[1],
            "mini_b1": _pertemuan(kon, "kelompok_id", kid_b, 1)[0],
            "privat_b1": _pertemuan(kon, "order_id", ord_delta, 1)[0],
        }


@pytest.fixture()
def berkas_catatan(tmp_path, monkeypatch):
    """Berkas catatan pertemuan sementara; belum ada sampai tulis pertama (sesuai kontrak)."""
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


# --- util ---------------------------------------------------------------------------------------

def _jalur(pertemuan_id) -> str:
    return f"{RUTE}{pertemuan_id}"


def _hash(path):
    """Hash isi berkas, atau None bila berkas belum ada (tanpa membuatnya)."""
    berkas = Path(path)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _hitung_baris(path):
    """(jumlah jurnal, jumlah hadir) dibaca mode ro; hanya dipanggil setelah tulis sah."""
    kon = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return tuple(kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]
                     for tabel in ("pertemuan_jurnal", "pertemuan_hadir"))
    finally:
        kon.close()


def hashlib_hmac(kunci: bytes, pesan: bytes) -> str:
    """Rumus acuan handle (independen dari implementasi): HMAC-SHA256 hex, 16 karakter pertama."""
    import hmac as _hmac
    return _hmac.new(kunci, pesan, hashlib.sha256).hexdigest()[:16]


def _principal(akun):
    principal = sessions.principal_basic(*akun)
    assert principal is not None
    return principal


def _token_sah(pertemuan_id, akun=AKUN_A) -> str:
    """Token sah untuk pertemuan, dibuat langsung dari modul token: halaman baca-saja tidak memuat form."""
    aksi = "pertemuan:%d" % pertemuan_id
    return form_token.buat_token(_principal(akun), None, domain=gph.DOMAIN_TOKEN_PERTEMUAN, aksi=aksi)


def _halaman(server, pertemuan_id, akun=AKUN_A) -> str:
    kode, isi, _ = server.minta(_jalur(pertemuan_id), auth=akun)
    assert kode == 200, kode
    return isi


def _form_dari_halaman(isi: str, topik: str = TOPIK, status: str = "hadir") -> dict:
    """Isian lengkap seperti peramban: token, topik, dan satu status untuk setiap handle anak di halaman."""
    data = {"token": POLA_TOKEN.search(isi).group(1), "topik": topik}
    for handle in sorted(set(POLA_HANDLE.findall(isi))):
        data["anak_" + handle] = status
    return data


def _kirim(server, pertemuan_id, data, akun=AKUN_A, headers=None):
    return minta_mentah(server, _jalur(pertemuan_id), akun, data, headers)


def _terkini_mini_a1(jadwal, mulai=None):
    kunci = aturan.kunci_pertemuan(jadwal["kid_a"], 1)
    return dasar.terkini(kunci, mulai or jadwal["mini_a1_mulai"])


def _ada_radio_tercentang(isi: str) -> bool:
    """True bila ada `<input ... checked>`; kata `checked` di CSS shell tidak dihitung."""
    return re.search(r"<input[^>]*\schecked[\s>/]", isi) is not None


def _selesai_plus_hari(mulai: str, menit: int, hari: int) -> datetime:
    return datetime.strptime(mulai, aturan.FORMAT_WAKTU) + timedelta(minutes=menit, days=hari)


def _ubah_mulai(pertemuan_id, mulai_baru: str) -> None:
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET mulai=? WHERE id=?", (mulai_baru, pertemuan_id))
        kon.commit()


def _jadikan_pemilik(jadwal, id_pemilik: str) -> None:
    """Tetapkan `id_pemilik` (mis. id admin) sebagai guru Mini Alfa, untuk membuktikan peran dicek terpisah."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_kelompok SET guru_id=? WHERE id=?", (id_pemilik, jadwal["kid_a"]))
        kon.commit()


def _pasang_versi_asing(berkas) -> None:
    kon = sqlite3.connect(str(berkas))
    try:
        kon.execute("PRAGMA user_version = 99")
        kon.commit()
    finally:
        kon.close()


# --- H1: pemilik melihat form dan tanpa id mentah ----------------------------------------------

def test_guru_pemilik_melihat_form_dengan_topik_dan_radio_per_anak(server, jadwal):
    kode, isi, _ = server.minta(_jalur(jadwal["mini_a1"]), auth=AKUN_A)

    assert kode == 200
    assert "Mini Alfa" in isi and "Anak Sintetis Alfa" in isi
    assert 'name="topik"' in isi and 'name="token"' in isi
    assert isi.count('type="radio"') == 3
    for nilai in STATUS_SAH:
        assert 'value="%s"' % nilai in isi
    assert len(set(POLA_HANDLE.findall(isi))) == 1


def test_halaman_form_tidak_memuat_id_mentah(server, jadwal):
    isi = _halaman(server, jadwal["mini_a1"])

    assert POLA_ID_MENTAH.search(isi) is None


def test_prefill_menampilkan_catatan_terkini(server, jadwal):
    isi = _halaman(server, jadwal["mini_a1"])
    kode, _i, _t = _kirim(server, jadwal["mini_a1"], _form_dari_halaman(isi, status="izin"))
    assert kode == 303

    isi = _halaman(server, jadwal["mini_a1"])

    assert re.search(r'<option value="%s"[^>]*selected' % TOPIK, isi)
    radio_izin = re.search(r'<input[^>]*value="izin"[^>]*>', isi).group(0)
    assert "checked" in radio_izin


# --- H2: 404 identik dengan rute tak dikenal ----------------------------------------------------

@pytest.mark.parametrize("sufiks", ["9999999", "abc", "1x", "0", "01", "9" * 25])
def test_get_id_cacat_atau_tak_ada_404_identik(server, jadwal, sufiks):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = server.minta(RUTE + sufiks, auth=AKUN_A)

    assert acuan[0] == 404
    assert (kode, isi) == (acuan[0], acuan[1])


def test_get_milik_guru_lain_404_identik(server, jadwal):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    for pertemuan_id in (jadwal["mini_a1"], jadwal["privat_a1"]):
        kode, isi, _ = server.minta(_jalur(pertemuan_id), auth=AKUN_B)
        assert (kode, isi) == (acuan[0], acuan[1]), pertemuan_id
        assert "Mini Alfa" not in isi and "Anak Sintetis Beta" not in isi


def test_get_admin_404_identik_bahkan_bila_admin_pemilik_kelompok(server, jadwal):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_ADMIN)
    _jadikan_pemilik(jadwal, id_akun(AKUN_ADMIN))

    kode, isi, _ = server.minta(_jalur(jadwal["mini_a1"]), auth=AKUN_ADMIN)

    assert (kode, isi) == (acuan[0], acuan[1])


def test_mode_lokal_tanpa_principal_404_identik(server, jadwal, monkeypatch):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)

    kode, isi, _ = server.minta(_jalur(jadwal["mini_a1"]))

    assert (kode, isi) == (acuan[0], acuan[1])


@pytest.mark.parametrize("sufiks", ["9999999", "abc", "1x", "0", "01"])
def test_post_id_cacat_atau_tak_ada_404_identik(server, jadwal, sufiks):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)

    kode, isi, _ = minta_mentah(server, RUTE + sufiks, AKUN_A, {"token": "x", "topik": TOPIK})

    assert (kode, isi) == (acuan[0], acuan[1])


def test_post_milik_guru_lain_dan_admin_404_identik(server, jadwal):
    for akun in (AKUN_B, AKUN_ADMIN):
        acuan = server.minta(TIDAK_ADA, auth=akun)
        for pertemuan_id in (jadwal["mini_a1"], jadwal["privat_a1"]):
            kode, isi, _ = _kirim(server, pertemuan_id, {"token": "x", "topik": TOPIK}, akun=akun)
            assert (kode, isi) == (acuan[0], acuan[1]), (akun, pertemuan_id)


def test_post_admin_404_identik_bahkan_bila_admin_pemilik_kelompok(server, jadwal, berkas_catatan):
    _jadikan_pemilik(jadwal, id_akun(AKUN_ADMIN))
    acuan = server.minta(TIDAK_ADA, auth=AKUN_ADMIN)

    kode, isi, _ = _kirim(server, jadwal["mini_a1"], {"token": "x", "topik": TOPIK}, akun=AKUN_ADMIN)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert not berkas_catatan.exists()


# --- H3: POST sah menulis, 303, dan kirim ulang identik tidak menambah baris ---------------------

def test_post_sah_menulis_jurnal_dan_hadir_lalu_303(server, jadwal):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), status="izin")

    kode, _isi, tajuk = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 303
    assert tajuk["Location"] == _jalur(jadwal["mini_a1"]) + "?pesan=tersimpan"
    keadaan = _terkini_mini_a1(jadwal)
    assert keadaan["topik"] == TOPIK
    assert keadaan["hadir"] == {jadwal["ord_alfa"]: "izin"}


def test_kirim_ulang_identik_tidak_menambah_baris(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    _kirim(server, jadwal["mini_a1"], form)
    sebelum = _hitung_baris(berkas_catatan)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 303
    assert _hitung_baris(berkas_catatan) == sebelum


def test_pesan_tersimpan_hanya_dari_kode_tetap(server, jadwal):
    isi = _halaman(server, jadwal["mini_a1"])
    _kirim(server, jadwal["mini_a1"], _form_dari_halaman(isi))

    kode, isi_ok, _ = server.minta(_jalur(jadwal["mini_a1"]) + "?pesan=tersimpan", auth=AKUN_A)
    kode_lain, isi_lain, _ = server.minta(_jalur(jadwal["mini_a1"]) + "?pesan=bebas", auth=AKUN_A)

    assert kode == kode_lain == 200
    assert TEKS_TERSIMPAN in isi_ok
    assert TEKS_TERSIMPAN not in isi_lain


# --- H4: token wajib, terikat aksi, akun, dan domain, serta kedaluwarsa ---------------------------

def test_token_tak_sah_ditolak_403_tanpa_tulis(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    tanpa_token = {k: v for k, v in form.items() if k != "token"}
    tokens = {
        "tanpa": tanpa_token,
        "kosong": dict(form, token=""),
        "salah": dict(form, token="9999999999.abc"),
        "non_ascii": dict(form, token="9999999999.é"),
    }
    for nama, data in tokens.items():
        kode, _isi, _t = _kirim(server, jadwal["mini_a1"], data)
        assert kode == 403, nama
    assert not berkas_catatan.exists()


def test_token_pertemuan_lain_ditolak_403(server, jadwal, berkas_catatan):
    token_privat = _token_sah(jadwal["privat_a1"])
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, token=token_privat))

    assert kode == 403
    assert not berkas_catatan.exists()


def test_token_akun_lain_ditolak_403(server, jadwal, berkas_catatan):
    token_b = form_token.buat_token(_principal(AKUN_B), None, domain=gph.DOMAIN_TOKEN_PERTEMUAN,
                                    aksi="pertemuan:%d" % jadwal["mini_a1"])
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, token=token_b))

    assert kode == 403
    assert not berkas_catatan.exists()


def test_token_kontak_domain_lain_ditolak_403(server, jadwal, berkas_catatan):
    token_kontak = kontak_http.buat_token(_principal(AKUN_A), None)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, token=token_kontak))

    assert kode == 403
    assert not berkas_catatan.exists()


def test_token_domain_lain_dengan_aksi_pertemuan_yang_benar_ditolak_403(server, jadwal, berkas_catatan):
    """Pemisahan DOMAIN berdiri sendiri: aksi persis `pertemuan:<id>` tetapi domain form lain tetap ditolak."""
    token = form_token.buat_token(_principal(AKUN_A), None, domain=kontak_http._DOMAIN_TOKEN,
                                  aksi="pertemuan:%d" % jadwal["mini_a1"])
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, token=token))

    assert kode == 403
    assert not berkas_catatan.exists()


def test_token_kedaluwarsa_ditolak_403(server, jadwal, berkas_catatan, monkeypatch):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    asli = form_token.time.time
    monkeypatch.setattr(form_token.time, "time", lambda: asli() + form_token.UMUR_BAWAAN_DETIK + 5)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 403
    assert not berkas_catatan.exists()


def test_post_lintas_situs_ditolak_dispatcher_tanpa_tulis(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form, headers={"Sec-Fetch-Site": "cross-site"})

    assert kode == 403
    assert not berkas_catatan.exists()


# --- H5: handle anak, kunci form, dan kiriman parsial --------------------------------------------

def test_handle_asal_pertemuan_lain_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    handle_privat = gph.handle_anak(_principal(AKUN_A), aturan.kunci_pertemuan(jadwal["ord_beta"], 1),
                                    jadwal["ord_beta"])
    data = {k: v for k, v in form.items() if not k.startswith("anak_")}
    data["anak_" + handle_privat] = "hadir"

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], data)

    assert kode == 400
    assert not berkas_catatan.exists()


def test_handle_akun_lain_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    handle_b = gph.handle_anak(_principal(AKUN_B), aturan.kunci_pertemuan(jadwal["kid_a"], 1), jadwal["ord_alfa"])
    data = {k: v for k, v in form.items() if not k.startswith("anak_")}
    data["anak_" + handle_b] = "hadir"

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], data)

    assert kode == 400
    assert not berkas_catatan.exists()


def test_kunci_anak_berlebih_ditolak_400_tanpa_tulis(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, anak_0000000000000000="hadir"))

    assert kode == 400
    assert not berkas_catatan.exists()


def test_kunci_anak_hilang_ditolak_400_sebagai_kiriman_parsial(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    tanpa_anak = {k: v for k, v in form.items() if not k.startswith("anak_")}

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], tanpa_anak)

    assert kode == 400
    assert not berkas_catatan.exists()


def test_kunci_anak_ganda_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    handle = gph.handle_anak(_principal(AKUN_A), aturan.kunci_pertemuan(jadwal["kid_a"], 1), jadwal["ord_alfa"])
    data = {k: [v] for k, v in form.items()}
    data["anak_" + handle] = ["hadir", "izin"]

    kode, _isi, _t = minta_mentah(server, _jalur(jadwal["mini_a1"]), AKUN_A, data)

    assert kode == 400
    assert not berkas_catatan.exists()


def test_kunci_form_asing_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], dict(form, siswa_id=str(jadwal["anak"]["alfa"])))

    assert kode == 400
    assert not berkas_catatan.exists()


def test_topik_hilang_sebagai_kiriman_parsial_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    tanpa_topik = {k: v for k, v in form.items() if k != "topik"}

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], tanpa_topik)

    assert kode == 400
    assert not berkas_catatan.exists()


# --- H6: topik dan status ----------------------------------------------------------------------

@pytest.mark.parametrize("topik", ["campuran", "tidak-ada", ""])
def test_topik_campuran_asing_atau_kosong_ditolak_400(server, jadwal, berkas_catatan, topik):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), topik=topik)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 400
    assert not berkas_catatan.exists()


def test_topik_lainnya_sah(server, jadwal):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), topik=TOPIK_LAINNYA)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 303
    assert _terkini_mini_a1(jadwal)["topik"] == TOPIK_LAINNYA


def test_status_asing_ditolak_400(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), status="setengah")

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 400
    assert not berkas_catatan.exists()


# --- H7: jendela R1 (belum mulai, dibatalkan, tanpa anak) dan R2 (7 hari) -------------------------

def test_belum_mulai_409_dan_halaman_baca_saja(server, jadwal, berkas_catatan):
    privat = jadwal["privat_a1"]
    isi = _halaman(server, privat)
    assert 'name="token"' not in isi and TEKS_BELUM_MULAI in isi

    kode, isi_post, _t = _kirim(server, privat, {"token": _token_sah(privat), "topik": TOPIK})

    assert kode == 409
    assert TEKS_BELUM_MULAI in isi_post
    assert not berkas_catatan.exists()


def test_tepat_saat_mulai_masih_boleh_dicatat(server, jadwal, jam):
    privat = jadwal["privat_a1"]
    jam.nilai = jadwal["privat_a1_mulai"]
    form = _form_dari_halaman(_halaman(server, privat))

    kode, _isi, _t = _kirim(server, privat, form)

    assert kode == 303


def test_dibatalkan_409_dan_halaman_baca_saja(server, jadwal, berkas_catatan):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE id=?", (jadwal["mini_a1"],))
        kon.commit()

    isi = _halaman(server, jadwal["mini_a1"])
    kode, isi_post, _t = _kirim(server, jadwal["mini_a1"], {"token": _token_sah(jadwal["mini_a1"]), "topik": TOPIK})

    assert 'name="token"' not in isi and TEKS_DIBATALKAN in isi
    assert kode == 409 and TEKS_DIBATALKAN in isi_post
    assert not berkas_catatan.exists()


def test_pertemuan_tanpa_anak_409_dan_halaman_baca_saja(server, jadwal, berkas_catatan):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kosong = js.buat_kelompok(kon, ADMIN_JADWAL, nama="Mini Kosong", lokasi=LOKASI_MEET, guru_id=id_akun(AKUN_A),
                                  kuota=5, tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kon.commit()
        pertemuan_id = _pertemuan(kon, "kelompok_id", kosong, 1)[0]

    isi = _halaman(server, pertemuan_id)
    kode, isi_post, _t = _kirim(server, pertemuan_id, {"token": _token_sah(pertemuan_id), "topik": TOPIK})

    assert 'name="token"' not in isi and TEKS_TANPA_ANAK in isi
    assert kode == 409 and TEKS_TANPA_ANAK in isi_post
    assert not berkas_catatan.exists()


def test_lewat_jendela_7_hari_terkunci_tepat_di_batas(server, jadwal, berkas_catatan, jam):
    batas = _selesai_plus_hari(jadwal["mini_a1_mulai"], jadwal["mini_a1_menit"], 7)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    jam.nilai = batas.strftime(aturan.FORMAT_WAKTU)
    kode, isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 409 and TEKS_TERKUNCI in isi
    assert not berkas_catatan.exists()


def test_satu_detik_sebelum_batas_jendela_masih_boleh(server, jadwal, jam):
    batas = _selesai_plus_hari(jadwal["mini_a1_mulai"], jadwal["mini_a1_menit"], 7)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))

    jam.nilai = (batas - timedelta(seconds=1)).strftime(aturan.FORMAT_WAKTU)
    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 303


def test_jendela_terkunci_halaman_baca_saja_tanpa_form(server, jadwal, jam):
    batas = _selesai_plus_hari(jadwal["mini_a1_mulai"], jadwal["mini_a1_menit"], 7)
    jam.nilai = batas.strftime(aturan.FORMAT_WAKTU)

    isi = _halaman(server, jadwal["mini_a1"])

    assert 'name="token"' not in isi and TEKS_TERKUNCI in isi


# --- H8: guru B tidak bisa menulis pertemuan guru A --------------------------------------------

def test_guru_b_dengan_token_miliknya_tidak_bisa_menulis_pertemuan_a(server, jadwal, berkas_catatan):
    isi_b = _halaman(server, jadwal["mini_b1"], akun=AKUN_B)
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)

    kode, isi, _t = _kirim(server, jadwal["mini_a1"], _form_dari_halaman(isi_b), akun=AKUN_B)

    assert (kode, isi) == (acuan[0], acuan[1])
    assert not berkas_catatan.exists()


# --- H9: tanpa efek samping pada penolakan ------------------------------------------------------

def test_penolakan_tidak_mengubah_db_admin_atau_membuat_berkas_catatan(server, jadwal, berkas_catatan):
    admin_db = Path(admin_store.BAWAAN)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    sebelum = (_hash(admin_db), _hash(berkas_catatan))

    _kirim(server, jadwal["mini_a1"], dict(form, token="x"))
    _kirim(server, jadwal["mini_a1"], dict(form, topik="campuran"))
    _kirim(server, jadwal["mini_a1"], form, akun=AKUN_B)
    _kirim(server, jadwal["privat_a1"], {"token": "x", "topik": TOPIK})
    server.minta(_jalur(jadwal["mini_a1"]), auth=AKUN_MURID)

    assert (_hash(admin_db), _hash(berkas_catatan)) == sebelum
    assert not berkas_catatan.exists()


# --- H10: snapshot mulai -----------------------------------------------------------------------

def test_pertemuan_digeser_tampil_kosong_dan_tulis_baris_baru(server, jadwal):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), status="izin")
    _kirim(server, jadwal["mini_a1"], form)
    mulai_baru = "2026-11-22T02:00:00"
    _ubah_mulai(jadwal["mini_a1"], mulai_baru)

    isi = _halaman(server, jadwal["mini_a1"])
    assert not _ada_radio_tercentang(isi) and not re.search(r'<option value="[^"]+" selected', isi)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], _form_dari_halaman(isi))

    assert kode == 303
    kunci = aturan.kunci_pertemuan(jadwal["kid_a"], 1)
    assert dasar.terkini(kunci, mulai_baru)["hadir"] == {jadwal["ord_alfa"]: "hadir"}
    assert dasar.terkini(kunci, jadwal["mini_a1_mulai"])["hadir"] == {jadwal["ord_alfa"]: "izin"}


# --- H11: murid dan anonim, header privat, laju, dan lima anak ----------------------------------

def test_murid_dan_anonim_ditolak_401_get_dan_post(server, jadwal):
    for akun in (AKUN_MURID, None):
        kode, isi, _t = server.minta(_jalur(jadwal["mini_a1"]), auth=akun)
        assert kode == 401 and "perlu masuk" in isi.lower(), akun
        kode, isi, _t = minta_mentah(server, _jalur(jadwal["mini_a1"]), akun, {"token": "x", "topik": TOPIK})
        assert kode == 401 and "perlu masuk" in isi.lower(), akun
        assert "Mini Alfa" not in isi


def test_respons_halaman_guru_memakai_header_privat(server, jadwal):
    kode, _isi, tajuk = server.minta(_jalur(jadwal["mini_a1"]), auth=AKUN_A)

    assert kode == 200
    assert tajuk.get("Cache-Control") == "no-store"
    assert tajuk.get("Referrer-Policy") == "no-referrer"


def test_respons_409_memakai_header_privat(server, jadwal):
    privat = jadwal["privat_a1"]

    kode, _isi, tajuk = _kirim(server, privat, {"token": _token_sah(privat), "topik": TOPIK})

    assert kode == 409
    assert tajuk.get("Cache-Control") == "no-store"
    assert tajuk.get("Referrer-Policy") == "no-referrer"


def test_laju_429_setelah_batas(server, jadwal, monkeypatch):
    monkeypatch.setattr(learning_cycle_http, "_riwayat", {})
    monkeypatch.setattr(learning_cycle_http, "_BATAS_PER_MENIT", 2)
    data = {"token": "x", "topik": TOPIK}

    kode_1, _i, _t = _kirim(server, jadwal["mini_a1"], data)
    kode_2, _i, _t = _kirim(server, jadwal["mini_a1"], data)
    kode_3, isi_3, _t = _kirim(server, jadwal["mini_a1"], data)

    assert (kode_1, kode_2) == (403, 403)
    assert kode_3 == 429 and "Terlalu banyak permintaan" in isi_3


def _tambah_empat_anak(server, jadwal) -> None:
    """Empat anak tambahan di Mini Alfa (kuota 5), sehingga form berisi lima anak dan tujuh kolom."""
    siswa_tambahan = [tambah_anak(server, "Anak Sintetis " + nama, "guru", None)
                      for nama in ("Dua", "Tiga", "Empat", "Lima")]
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        for nomor, siswa in enumerate(siswa_tambahan, start=5):
            _tempatkan_mini(kon, jadwal["kid_a"], siswa, n=nomor)
        kon.commit()


def test_mini_lima_anak_mengisi_tujuh_kolom_dan_tersimpan(server, jadwal, berkas_catatan):
    _tambah_empat_anak(server, jadwal)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]), status="tidak_hadir")
    assert len(form) == 7

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 303
    assert len(_terkini_mini_a1(jadwal)["hadir"]) == 5


def test_mini_lima_anak_satu_status_hilang_ditolak_400(server, jadwal, berkas_catatan):
    _tambah_empat_anak(server, jadwal)
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    satu_anak = sorted(kunci for kunci in form if kunci.startswith("anak_"))[0]

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], {k: v for k, v in form.items() if k != satu_anak})

    assert kode == 400
    assert not berkas_catatan.exists()


# --- H12: galat DB pertemuan ---------------------------------------------------------------------

def test_post_dengan_versi_db_asing_503_tanpa_tulis(server, jadwal, berkas_catatan):
    form = _form_dari_halaman(_halaman(server, jadwal["mini_a1"]))
    _pasang_versi_asing(berkas_catatan)
    sebelum = _hash(berkas_catatan)

    kode, _isi, _t = _kirim(server, jadwal["mini_a1"], form)

    assert kode == 503
    assert _hash(berkas_catatan) == sebelum


def test_get_dengan_versi_db_asing_tetap_menampilkan_form_kosong(server, jadwal, berkas_catatan):
    _pasang_versi_asing(berkas_catatan)

    kode, isi, _t = server.minta(_jalur(jadwal["mini_a1"]), auth=AKUN_A)

    assert kode == 200
    assert 'name="token"' in isi and not _ada_radio_tercentang(isi)


# --- Handle anak (fungsi murni) ---------------------------------------------------------------

def test_handle_anak_16_hex_dan_deterministik(jadwal):
    kunci = aturan.kunci_pertemuan(jadwal["kid_a"], 1)
    pertama = gph.handle_anak(_principal(AKUN_A), kunci, jadwal["ord_alfa"])
    kedua = gph.handle_anak(_principal(AKUN_A), kunci, jadwal["ord_alfa"])

    assert pertama == kedua
    assert re.fullmatch(r"[0-9a-f]{16}", pertama)


def test_handle_anak_beda_per_kunci_order_dan_akun(jadwal):
    kunci_1 = aturan.kunci_pertemuan(jadwal["kid_a"], 1)
    kunci_2 = aturan.kunci_pertemuan(jadwal["kid_a"], 2)
    acuan = gph.handle_anak(_principal(AKUN_A), kunci_1, jadwal["ord_alfa"])

    assert gph.handle_anak(_principal(AKUN_A), kunci_2, jadwal["ord_alfa"]) != acuan
    assert gph.handle_anak(_principal(AKUN_A), kunci_1, jadwal["ord_beta"]) != acuan
    assert gph.handle_anak(_principal(AKUN_B), kunci_1, jadwal["ord_alfa"]) != acuan


def test_handle_anak_memakai_domain_terpisah_dari_token(jadwal):
    """Rumus acuan independen: HMAC kunci akun atas domain handle + kunci + '|' + order, 16 hex pertama."""
    kunci = aturan.kunci_pertemuan(jadwal["kid_a"], 1)
    akun = auth.cari_akun(AKUN_A[0])
    pesan = b"anak-handle-v1:" + kunci.encode() + b"|" + jadwal["ord_alfa"].encode()
    harapan = hashlib_hmac(bytes.fromhex(akun["kunci"]), pesan)

    assert gph.handle_anak(_principal(AKUN_A), kunci, jadwal["ord_alfa"]) == harapan
    assert gph.DOMAIN_HANDLE_ANAK != gph.DOMAIN_TOKEN_PERTEMUAN
    assert gph.DOMAIN_HANDLE_ANAK != kontak_http._DOMAIN_TOKEN


def test_handle_anak_tidak_memuat_order_id(jadwal):
    handle = gph.handle_anak(_principal(AKUN_A), aturan.kunci_pertemuan(jadwal["kid_a"], 1), jadwal["ord_alfa"])

    assert jadwal["ord_alfa"] not in handle and "kor_" not in handle
