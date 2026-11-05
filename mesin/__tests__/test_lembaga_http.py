"""Lembaga les lewat HTTP: halaman pemilik, pindah anak, 404 identik, tanpa bocor.

Data sepenuhnya sintetis. Setiap penolakan dibuktikan tanpa tulis ke DB lewat
perbandingan snapshot baris `siswa` + `pindah_siswa` + `sesi`.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import lembaga_store as L  # noqa: E402
import share_links  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji, _basic  # noqa: E402

SANDI = "sandi-lembaga-sintetis-123"
PEMILIK = "pemilik-les"
GURU_A = "guru-a"
GURU_B = "guru-b"
LUAR = "guru-luar"
LINTAS_SITUS = {"Sec-Fetch-Site": "cross-site", "Origin": "http://situs-lain.invalid"}
TIDAK_ADA = "/rute-yang-tidak-ada"
JAWABAN_RAHASIA = "JAWABAN-RAHASIA-777"
CARA_RAHASIA = "CARA-RAHASIA-888"
KUNCI_RAHASIA = "KUNCI-RAHASIA-999"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        for nama in (PEMILIK, GURU_A, GURU_B, LUAR):
            auth.tambah_akun(nama, SANDI, "guru")
        auth.tambah_akun("pengelola-l", SANDI, "admin")
        with uji.buka() as kon:
            lid = L.buat_lembaga(kon, nama="Les Sintetis Cerdas", pemilik=PEMILIK)
            L.tambah_anggota(kon, lembaga_id=lid, guru=GURU_A)
            L.tambah_anggota(kon, lembaga_id=lid, guru=GURU_B)
            uji.lid = lid
            uji.anak = {
                "a": database.tambah_siswa(kon, "Anak Alfa", "P3", pemilik=GURU_A),
                "b": database.tambah_siswa(kon, "Anak Beta", "P3", pemilik=GURU_B),
                "o": database.tambah_siswa(kon, "Anak Omega", "P3", pemilik=PEMILIK),
                "luar": database.tambah_siswa(kon, "Anak Luar", "P3", pemilik=LUAR),
            }
        yield uji
    finally:
        uji.berhenti()


def _sebagai(nama):
    return (nama, SANDI)


def _snapshot(server):
    with server.buka() as kon:
        return tuple(
            tuple(tuple(r) for r in kon.execute(sql))
            for sql in (
                "SELECT * FROM siswa ORDER BY id",
                "SELECT * FROM pindah_siswa ORDER BY id",
                "SELECT * FROM sesi ORDER BY id",
                "SELECT * FROM anggota_lembaga ORDER BY guru",
                "SELECT * FROM lembaga ORDER BY id",
            )
        )


def _pemilik(server, siswa_id):
    with server.buka() as kon:
        return kon.execute("SELECT pemilik FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0]


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    """Pertahankan 303 sebagai 303; status asli rute yang diuji."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(server, jalur, nama, data, headers=None):
    req = urllib.request.Request(
        server.alamat + jalur, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", _basic(*_sebagai(nama)))
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def _pindah(server, nama, siswa_id, ke, **kw):
    return _post(server, "/lembaga/pindah", nama,
                 {"siswa_id": str(siswa_id), "ke": ke}, **kw)


# --- GET /lembaga --------------------------------------------------------------

def test_pemilik_melihat_ringkasan_per_guru(server):
    kode, isi, tajuk = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    assert kode == 200
    assert "Les Sintetis Cerdas" in isi
    for nama in ("Anak Alfa", "Anak Beta", "Anak Omega"):
        assert nama in isi
    assert "Anak Luar" not in isi and ">" + LUAR + "<" not in isi
    assert tajuk["Cache-Control"] == "no-store"
    assert "<script" not in isi.split("<main", 1)[1].split("</main>")[0]
    # Urutan: pemilik dulu, lalu anggota terurut abjad.
    assert re.findall(r"<h2>([^<]*)</h2>", isi) == [
        PEMILIK + " (pemilik les)", GURU_A, GURU_B]


def test_halaman_pemilik_hanya_agregat_tanpa_jawaban_kode_kunci(server):
    with server.buka() as kon:
        sesi = database.buat_sesi(kon, server.anak["a"], seed=5, jumlah_soal=1)
        baris = database.isi_sesi(kon, sesi)[0]
        jid = database.simpan_jawaban(
            kon, baris["sesi_soal_id"], jawaban=JAWABAN_RAHASIA, cara=CARA_RAHASIA)
        database.simpan_diagnosis(kon, jid, False, "K", "K", "malrule-rahasia-id", "ALASAN-RAHASIA")
        kon.execute("UPDATE soal SET kunci=? WHERE id=?", (KUNCI_RAHASIA, baris["soal_id"]))
        kon.execute("UPDATE sesi SET selesai='2026-11-01 08:00:00' WHERE id=?", (sesi,))
    kode, isi, _ = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    assert kode == 200
    for rahasia in (JAWABAN_RAHASIA, CARA_RAHASIA, KUNCI_RAHASIA, "malrule-rahasia-id", "ALASAN-RAHASIA"):
        assert rahasia not in isi
    assert f"/sesi/{sesi}" not in isi and "/lembar/" not in isi
    # Hanya agregat: satu sesi menunggu konfirmasi untuk Anak Alfa.
    assert "Menunggu konfirmasi" in isi


@pytest.mark.parametrize("nama", [GURU_A, LUAR, "pengelola-l", "guru"])
def test_selain_pemilik_mendapat_404_identik_dengan_rute_tak_dikenal(server, nama):
    pakai = ("guru", SANDI_GURU) if nama == "guru" else _sebagai(nama)
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    kode, isi, _ = server.minta("/lembaga", auth=pakai)
    assert (kode, isi) == (acuan[0], acuan[1])
    assert kode == 404
    assert "Anak Alfa" not in isi and "Les Sintetis" not in isi


def test_anonim_dan_murid_ditolak_palang_sandi(server):
    assert server.minta("/lembaga")[0] == 401
    assert server.minta("/lembaga", auth=("feby", "sandi-feby-12345"))[0] == 401


def test_get_tidak_menulis(server):
    sebelum = _snapshot(server)
    server.minta("/lembaga", auth=_sebagai(PEMILIK))
    server.minta("/lembaga?pesan=pindah_ok", auth=_sebagai(PEMILIK))
    assert _snapshot(server) == sebelum


def test_form_pindah_menawarkan_guru_lain_saja(server):
    _, isi, _ = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    assert isi.count('action="/lembaga/pindah"') == 3
    form_alfa = re.search(
        r'<form[^>]*action="/lembaga/pindah"[^>]*>(?:(?!</form>).)*?name="siswa_id" value="%d"'
        r'(?:(?!</form>).)*</form>' % server.anak["a"], isi, re.S)
    assert form_alfa, "form Anak Alfa tidak ditemukan"
    pilihan = re.findall(r'<option value="([^"]*)"', form_alfa.group(0))
    assert sorted(pilihan) == sorted([PEMILIK, GURU_B])
    assert "csrf" not in form_alfa.group(0).lower()  # guru memakai palang asal, bukan token


def test_pesan_ditampilkan_dari_kode_tetap_tanpa_memantulkan_isian(server):
    _, ok, _ = server.minta("/lembaga?pesan=pindah_ok", auth=_sebagai(PEMILIK))
    assert "sudah dipindahkan" in ok
    _, asing, _ = server.minta(
        "/lembaga?pesan=%3Cb%3Ejahil%3C/b%3E", auth=_sebagai(PEMILIK))
    assert "jahil" not in asing and "role=\"status\"" not in asing


# --- POST /lembaga/pindah ------------------------------------------------------------

def test_pindah_sukses_alihkan_dengan_kode_dan_ubah_pemilik(server):
    kode, _, tajuk = _pindah(server, PEMILIK, server.anak["a"], GURU_B)
    assert kode == 303
    assert tajuk["Location"] == "/lembaga?pesan=pindah_ok"
    assert _pemilik(server, server.anak["a"]) == GURU_B
    with server.buka() as kon:
        jejak = kon.execute("SELECT dari,ke,oleh FROM pindah_siswa").fetchall()
    assert [tuple(r) for r in jejak] == [(GURU_A, GURU_B, PEMILIK)]


def test_pemilik_les_boleh_memindahkan_anaknya_sendiri_ke_anggota(server):
    assert _pindah(server, PEMILIK, server.anak["o"], GURU_A)[0] == 303
    assert _pemilik(server, server.anak["o"]) == GURU_A


@pytest.mark.parametrize("aktor", [GURU_A, LUAR, "pengelola-l"])
def test_pindah_non_pemilik_404_identik_tanpa_tulis(server, aktor):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    kode, isi, _ = _pindah(server, aktor, server.anak["a"], GURU_B)
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


def test_pindah_non_pemilik_dengan_isian_sampah_tetap_404_bukan_400(server):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    kode, isi, _ = _post(server, "/lembaga/pindah", GURU_A, {"x": "y"})
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


@pytest.mark.parametrize("siswa_id,ke", [
    ("luar", GURU_B),      # anak di luar lembaga
    ("a", LUAR),           # tujuan di luar lembaga
    ("a", "pengelola-l"),  # tujuan admin
    ("a", "tidak-ada"),    # tujuan tak dikenal
    ("99999", GURU_B),     # anak tak ada
])
def test_pindah_otorisasi_gagal_404_identik_tanpa_tulis(server, siswa_id, ke):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    sid = server.anak.get(siswa_id, siswa_id)
    kode, isi, _ = _pindah(server, PEMILIK, sid, ke)
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


def test_pindah_ditolak_bila_lembaga_lain(server):
    lain_pemilik = "pemilik-dua"
    auth.tambah_akun(lain_pemilik, SANDI, "guru")
    auth.tambah_akun("anggota-dua", SANDI, "guru")
    with server.buka() as kon:
        lid = L.buat_lembaga(kon, nama="Les Dua", pemilik=lain_pemilik)
        L.tambah_anggota(kon, lembaga_id=lid, guru="anggota-dua")
    sebelum = _snapshot(server)
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    # Pemilik dua mencoba memindahkan anak lembaga pertama.
    kode, isi, _ = _pindah(server, lain_pemilik, server.anak["a"], "anggota-dua")
    assert (kode, isi) == (acuan[0], acuan[1])
    # Pemilik pertama mencoba memindahkan ke anggota lembaga dua.
    kode, isi, _ = _pindah(server, PEMILIK, server.anak["a"], "anggota-dua")
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


def test_penolakan_bisnis_303_dengan_kode_tanpa_tulis(server):
    with server.buka() as kon:
        database.tambah_siswa(kon, "Anak Alfa", "P3", pemilik=GURU_B)  # bentrok nama
        sesi = database.buat_sesi(kon, server.anak["o"], seed=9, jumlah_soal=1)
        kon.execute("UPDATE sesi SET mulai='2026-11-01 08:00:00' WHERE id=?", (sesi,))
    sebelum = _snapshot(server)
    kasus = (
        (server.anak["a"], GURU_B, "bentrok_nama"),
        (server.anak["o"], GURU_A, "sesi_berjalan"),
        (server.anak["a"], GURU_A, "sama"),
    )
    for sid, ke, kode_pesan in kasus:
        kode, _, tajuk = _pindah(server, PEMILIK, sid, ke)
        assert kode == 303, kode_pesan
        assert tajuk["Location"] == "/lembaga?pesan=" + kode_pesan
        assert _snapshot(server) == sebelum
        _, halaman, _ = server.minta(tajuk["Location"], auth=_sebagai(PEMILIK))
        assert 'role="status"' in halaman


@pytest.mark.parametrize("data", [
    {"siswa_id": "abc", "ke": GURU_B},
    {"siswa_id": "", "ke": GURU_B},
    {"siswa_id": "-1", "ke": GURU_B},
    {"siswa_id": "1.5", "ke": GURU_B},
    {"ke": GURU_B},
    {"siswa_id": "1"},
    {"siswa_id": "1", "ke": GURU_B, "tambahan": "x"},
])
def test_isian_salah_bentuk_dari_pemilik_400_tanpa_tulis(server, data):
    sebelum = _snapshot(server)
    kode, _, _ = _post(server, "/lembaga/pindah", PEMILIK, data)
    assert kode == 400
    assert _snapshot(server) == sebelum


def test_post_lintas_situs_403_tanpa_tulis(server):
    sebelum = _snapshot(server)
    kode, isi, _ = _pindah(server, PEMILIK, server.anak["a"], GURU_B, headers=LINTAS_SITUS)
    assert kode == 403 and "Permintaan ditolak" in isi
    kode, _, _ = _pindah(
        server, PEMILIK, server.anak["a"], GURU_B,
        headers={"Origin": "http://situs-lain.invalid"})
    assert kode == 403
    assert _snapshot(server) == sebelum


def test_post_anonim_dan_murid_ditolak_palang_sandi_tanpa_tulis(server):
    sebelum = _snapshot(server)
    anonim = server.minta(
        "/lembaga/pindah", data={"siswa_id": str(server.anak["a"]), "ke": GURU_B})
    murid = server.minta(
        "/lembaga/pindah", auth=("feby", "sandi-feby-12345"),
        data={"siswa_id": str(server.anak["a"]), "ke": GURU_B})
    assert anonim[0] == 401 and murid[0] == 401
    assert _snapshot(server) == sebelum


def test_get_pada_rute_pindah_404(server):
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    kode, isi, _ = server.minta("/lembaga/pindah", auth=_sebagai(PEMILIK))
    assert (kode, isi) == (acuan[0], acuan[1])


def test_pindah_memakai_batas_laju(server, monkeypatch):
    import learning_cycle_http as siklus
    monkeypatch.setattr(siklus, "_BATAS_PER_MENIT", 2)
    monkeypatch.setattr(siklus, "_riwayat", {})
    hasil = [
        _pindah(server, PEMILIK, server.anak["a"], GURU_A)[0] for _ in range(4)
    ]
    assert hasil[:2] == [303, 303]
    assert 429 in hasil[2:]


# --- dampak pada anak yang dipindah ---------------------------------------------------

def test_setelah_pindah_guru_lama_404_guru_baru_buka_murid_dan_tautan_tetap(server):
    anak = server.anak["a"]
    with server.buka() as kon:
        sesi = database.buat_sesi(kon, anak, seed=11, jumlah_soal=1)
        token = share_links.buat(kon, sesi)
    auth.tambah_akun("anak-alfa", "sandi-anak-alfa-123", "murid", siswa_id=anak)
    murid = ("anak-alfa", "sandi-anak-alfa-123")
    assert server.minta("/murid", auth=murid)[0] == 200
    assert server.minta(f"/mulai/{token}")[0] == 200
    assert server.minta(f"/anak/{anak}", auth=_sebagai(GURU_A))[0] == 200
    assert server.minta(f"/anak/{anak}", auth=_sebagai(GURU_B))[0] == 404

    assert _pindah(server, PEMILIK, anak, GURU_B)[0] == 303

    lama = server.minta(f"/anak/{anak}", auth=_sebagai(GURU_A))
    lama_sesi = server.minta(f"/sesi/{sesi}", auth=_sebagai(GURU_A))
    acuan = server.minta("/anak/999999", auth=_sebagai(GURU_A))
    assert lama[0] == 404 and (lama[0], lama[1]) == (acuan[0], acuan[1])
    assert lama_sesi[0] == 404
    assert server.minta(f"/anak/{anak}", auth=_sebagai(GURU_B))[0] == 200
    assert server.minta(f"/sesi/{sesi}", auth=_sebagai(GURU_B))[0] == 200
    # Pemilik les tidak ikut mendapat akses ke halaman anak/sesi anggota.
    assert server.minta(f"/anak/{anak}", auth=_sebagai(PEMILIK))[0] == 404
    assert server.minta(f"/sesi/{sesi}", auth=_sebagai(PEMILIK))[0] == 404
    # Murid dan tautan bearer tidak terputus.
    assert server.minta("/murid", auth=murid)[0] == 200
    assert server.minta(f"/mulai/{token}")[0] == 200


def test_pemilik_les_tidak_mendapat_akses_anak_anggota_sebelum_pindah(server):
    anak = server.anak["a"]
    assert server.minta(f"/anak/{anak}", auth=_sebagai(PEMILIK))[0] == 404


def test_beranda_guru_menautkan_lembaga_hanya_untuk_pemilik(server):
    _, pemilik, _ = server.minta("/guru", auth=_sebagai(PEMILIK))
    assert pemilik.count('href="/lembaga"') == 1 and "Lembaga les" in pemilik
    for nama in (GURU_A, LUAR):
        _, isi, _ = server.minta("/guru", auth=_sebagai(nama))
        assert 'href="/lembaga"' not in isi


def test_murid_tidak_pernah_melihat_data_lembaga(server):
    auth.tambah_akun("anak-alfa", "sandi-anak-alfa-123", "murid", siswa_id=server.anak["a"])
    _, isi, _ = server.minta("/murid", auth=("anak-alfa", "sandi-anak-alfa-123"))
    assert "Les Sintetis" not in isi and "lembaga" not in isi.lower()


def test_akun_admin_tidak_pernah_diperlakukan_pemilik_meski_baris_rusak(server):
    """Pembelaan berlapis: baris lembaga milik akun admin (keadaan mustahil lewat
    UI) tetap tidak membuka halaman maupun aksi pindah bagi akun admin."""
    with server.buka() as kon:
        kon.execute("INSERT INTO lembaga (nama, pemilik) VALUES ('Rusak', 'pengelola-l')")
    acuan = server.minta(TIDAK_ADA, auth=_sebagai(LUAR))
    sebelum = _snapshot(server)
    kode, isi, _ = server.minta("/lembaga", auth=_sebagai("pengelola-l"))
    assert (kode, isi) == (acuan[0], acuan[1])
    kode, isi, _ = _pindah(server, "pengelola-l", server.anak["a"], GURU_B)
    assert (kode, isi) == (acuan[0], acuan[1])
    assert _snapshot(server) == sebelum


def test_tata_letak_ponsel_kartu_bertumpuk_dan_gaya_tautan_kembali(server):
    _, isi, _ = server.minta("/lembaga", auth=_sebagai(PEMILIK))
    assert "@media (max-width: 560px)" in isi
    for label in ("Sesi", "Sesi terakhir", "Menunggu konfirmasi"):
        assert 'data-label="%s"' % label in isi
    assert 'class="guru-tambah-st" href="/guru"' in isi
    assert 'class="lembaga-aksi-st"' in isi
    assert "overflow-x" not in isi.split("lembaga-st", 1)[1].split("</style>")[0]
