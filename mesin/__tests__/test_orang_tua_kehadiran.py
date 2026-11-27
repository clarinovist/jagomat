"""Blok guru di halaman orang tua (3c): kehadiran dan jurnal, serta tugas dari Guru, baca-saja.

Tiga lapis: render murni (`halaman_isi(guru=...)`), pembaca `orang_tua_guru.kumpulkan_guru` di atas DB sintetis
nyata, dan HTTP nyata (`GET /murid/orang-tua`) termasuk tirai PIN. Data sintetis di tmp_path; waktu diatur lewat
`pesanan_alur._sekarang`. Blok bersifat fail-silent, jadi tes galat memakai pencatat log dan penghitung panggilan,
bukan asersi di dalam pembaca yang dilempar (asersi akan ikut tertelan).
"""
from __future__ import annotations

import logging
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from types import SimpleNamespace

import pytest

import admin_store
import auth
import database
import feature_switch
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import guru_pertemuan_ortu
import guru_tugas_aturan
import guru_tugas_baca
import guru_tugas_dasar
import jadwal_store as js
import kelas_kit
import orang_tua_data
import orang_tua_guru
import orang_tua_http
import orang_tua_pages as P
import pesanan_alur
import pin_orang_tua_store as pin_store
import schema_jadwal
import schema_tagihan_catatan
import tirai_orang_tua as tirai
from http_test_kit import ServerUji
from kelas_http_kit import pasang_skema
from pesanan_kit import AKUN_A

RUTE = "/murid/orang-tua"
ADMIN = "admin_sintetis"
GURU = "akun_" + "c" * 32
KELAS_ANAK = "P5"
SANDI_A = "sandi-raka-sintetis"
SANDI_B = "sandi-dina-sintetis"
PIN_A = "4821"
NAMA_A = "Raka Sintetis"
NAMA_B = "Dina Sintetis"
TOPIK_JURNAL = "pola-bilangan"
TOPIK_TUGAS = "geometri-datar"
TOPIK_TUGAS_B = "aritmetika-dasar"
LABEL_JURNAL = aturan.label_topik(TOPIK_JURNAL)
LABEL_TUGAS = aturan.label_topik(TOPIK_TUGAS)
LABEL_TUGAS_B = aturan.label_topik(TOPIK_TUGAS_B)
PADA = "2026-11-22T10:00:00"
DIBUAT_TUGAS = "2026-11-26T02:00:00"
TENGGAT = "2026-12-05"
# 26 Nov 2026 10.00 WIB: pertemuan Private ke-1 (25 Nov 16.30 WIB = 09.30 UTC) sudah mulai.
KINI = "2026-11-26T03:00:00"
HARI_INI = date(2026, 11, 26)
MULAI_KE1 = "2026-11-25T09:30:00"
PENANDA_KEHADIRAN = 'id="ortu-kehadiran"'
PENANDA_TUGAS = 'id="ortu-tugas"'
KUNCI_KEHADIRAN = {"mulai", "hadir", "topik"}
KUNCI_TUGAS = {"topik", "tenggat", "status_tenggat", "selesai", "benar", "total"}
CEK = {"status": "selesai", "skor": 60, "kategori": "Perlu penguatan",
       "ringkasan": {"kuat": ["Penjumlahan"], "perlu": []}, "jumlah_soal": 15}


# --- render murni ------------------------------------------------------------------------------

def _data():
    return orang_tua_data.DataOrangTua("Anak Sintetis", CEK, None, None, None, None)


def _guru(kehadiran=(), tugas=()):
    return {"kehadiran": list(kehadiran), "tugas": list(tugas)}


def _isi(guru=None):
    return P.halaman_isi(_data(), False, guru=guru).decode()


def _seksi(html, id_):
    awal = html.rfind("<section", 0, html.index(id_))
    return html[awal:html.index("</section>", awal) + len("</section>")]


def _item(seksi):
    return seksi.split("<li>")[1:]


def _kehadiran(*baris):
    return [{"mulai": mulai, "hadir": hadir, "topik": topik} for mulai, hadir, topik in baris]


def _tugas(topik=LABEL_TUGAS, tenggat=None, status="tanpa", selesai=False, benar=None, total=10):
    return {"topik": topik, "tenggat": tenggat, "status_tenggat": status, "selesai": selesai,
            "benar": benar, "total": total}


def test_guru_none_dan_daftar_kosong_identik_dengan_keluaran_lama():
    dasar = P.halaman_isi(_data(), False).decode()
    assert _isi(guru=None) == dasar
    assert _isi(guru=_guru()) == dasar


def test_kehadiran_tiap_status_dan_belum_dicatat_dengan_waktu_wib():
    html = _isi(guru=_guru(kehadiran=_kehadiran(
        ("2026-11-30T08:00:00", "hadir", None), ("2026-11-23T08:00:00", "izin", None),
        ("2026-11-16T08:00:00", "tidak_hadir", None), ("2026-11-09T08:00:00", None, None))))
    kartu = _seksi(html, PENANDA_KEHADIRAN)
    for status in ("<p>Hadir</p>", "<p>Izin</p>", "<p>Tidak hadir</p>", "<p>Belum dicatat</p>"):
        assert status in kartu
    assert "<b>Sen, 30 Nov 2026 · 15.00</b>" in kartu
    assert "tidak_hadir" not in kartu


def test_topik_jurnal_berlabel_dan_di_escape():
    html = _isi(guru=_guru(kehadiran=_kehadiran(("2026-11-30T08:00:00", "hadir", "<script>alert(1)</script>"))))
    kartu = _seksi(html, PENANDA_KEHADIRAN)
    assert "<p>Topik: &lt;script&gt;alert(1)&lt;/script&gt;</p>" in kartu
    assert "<script>alert(1)" not in html


def test_judul_tugas_di_escape():
    html = _isi(guru=_guru(tugas=[_tugas(topik="<b>X</b>", selesai=True, benar=1, total=2)]))
    assert "<b>&lt;b&gt;X&lt;/b&gt;</b>" in _seksi(html, PENANDA_TUGAS)


def test_tugas_selesai_menampilkan_skor_dan_belum_selesai_tanpa_angka():
    html = _isi(guru=_guru(tugas=[
        _tugas(selesai=True, benar=7, total=10, tenggat=TENGGAT, status="berjalan"),
        _tugas(topik=LABEL_TUGAS_B, total=12)]))
    selesai, belum = _item(_seksi(html, PENANDA_TUGAS))
    assert "Selesai · 7 dari 10 benar" in selesai
    assert "Belum dikerjakan" in belum
    assert "dari 12" not in belum and "benar" not in belum


def test_tenggat_tampil_tanggal_indonesia_dan_lewat_hanya_untuk_belum_selesai():
    html = _isi(guru=_guru(tugas=[
        _tugas(tenggat=TENGGAT, status="lewat"),
        _tugas(topik=LABEL_TUGAS_B, tenggat=TENGGAT, status="lewat", selesai=True, benar=3, total=5)]))
    belum, selesai = _item(_seksi(html, PENANDA_TUGAS))
    assert "<p>Tenggat 5 Des 2026</p>" in belum and "<p>Lewat tenggat</p>" in belum
    assert "Lewat tenggat" not in selesai and "Selesai · 3 dari 5 benar" in selesai


def test_tugas_berjalan_atau_tanpa_tenggat_tidak_menyebut_lewat():
    html = _isi(guru=_guru(tugas=[_tugas(tenggat=TENGGAT, status="berjalan"), _tugas(topik=LABEL_TUGAS_B)]))
    assert "Lewat tenggat" not in _seksi(html, PENANDA_TUGAS)


def test_blok_guru_tanpa_id_nama_guru_atau_kata_terlarang():
    html = _isi(guru=_guru(
        kehadiran=_kehadiran(("2026-11-30T08:00:00", "hadir", "Pola Bilangan")),
        tugas=[_tugas(tenggat=TENGGAT, status="berjalan", selesai=True, benar=7, total=10)]))
    blok = (_seksi(html, PENANDA_KEHADIRAN) + _seksi(html, PENANDA_TUGAS)).lower()
    for terlarang in ("kor_", "klp_", "akun_", "ord_", "oleh", "sesi", "/murid/kerjakan", "guru_akun", "order"):
        assert terlarang not in blok, terlarang
    assert GURU not in html


def test_urutan_blok_guru_setelah_laporan_lama_dan_sebelum_pin():
    html = _isi(guru=_guru(kehadiran=_kehadiran(("2026-11-30T08:00:00", "hadir", None)),
                           tugas=[_tugas(selesai=True, benar=1, total=2)]))
    penanda = ['id="ortu-laporan"', PENANDA_KEHADIRAN, PENANDA_TUGAS, 'id="ortu-pin"']
    posisi = [html.index(p) for p in penanda]
    assert posisi == sorted(posisi) and len(set(posisi)) == len(penanda)


def test_blok_kosong_tidak_menyisakan_section_dan_tanpa_maskot_atau_h1_ganda():
    html = _isi(guru=_guru(tugas=[_tugas(selesai=True, benar=1, total=2)]))
    assert PENANDA_KEHADIRAN not in html and PENANDA_TUGAS in html
    assert 'class="ceria-maskot"' not in _seksi(html, PENANDA_TUGAS)
    assert html.count("<h1") == 1


# --- pembaca kumpulkan_guru (DB sintetis nyata) -------------------------------------------------

@pytest.fixture
def basis(tmp_path, monkeypatch):
    admin = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(admin)
    schema_tagihan_catatan.migrasikan(admin)
    latihan = tmp_path / "latihan-uji.db"
    database.siapkan(latihan)
    monkeypatch.setattr(admin_store, "BAWAAN", admin)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv(guru_tugas_dasar.ENV_DB, str(tmp_path / "guru-tugas.db"))
    monkeypatch.setenv(catatan.ENV_DB, str(tmp_path / "guru-pertemuan.db"))
    monkeypatch.setattr(guru_tugas_aturan, "GURU_TUGAS_AKTIF", True)
    _ganti_sakelar(monkeypatch, "1")
    yield SimpleNamespace(admin=admin, latihan=latihan, tugas=tmp_path / "guru-tugas.db",
                          catatan=tmp_path / "guru-pertemuan.db")
    feature_switch.bersihkan_cache()


def _ganti_sakelar(monkeypatch, nilai):
    monkeypatch.setenv("PAKET_BELAJAR", nilai)
    feature_switch.bersihkan_cache()


def _meledak(kelas_galat):
    def fungsi(*args, **kwargs):
        raise kelas_galat("uji: galat sintetis")
    return fungsi


def _siswa_latihan(latihan, nama):
    with database.buka(latihan) as kon:
        return database.tambah_siswa(kon, nama, KELAS_ANAK, pemilik="koordinator-sintetis")


def _sesi(latihan, siswa, topik=TOPIK_TUGAS):
    with database.buka(latihan) as kon:
        return database.buat_sesi(kon, siswa, seed=101, topik=topik, level=KELAS_ANAK)


def _tugas_catat(tugas, sesi_id, siswa, topik=TOPIK_TUGAS, tenggat=TENGGAT):
    return guru_tugas_dasar.catat(sesi_id, siswa, GURU, topik, tenggat, DIBUAT_TUGAS, path=tugas)


def _anak_privat(admin, catatan_path, siswa, akun=AKUN_A):
    """Order Private lunas, penempatan ke GURU, dan pertemuan ke-1 yang sudah dicatat hadir."""
    with js.buka(admin, tulis_data=True) as kon:
        tagihan = kelas_kit.lunas(kon, siswa, "private", n=3, akun=akun)
        js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=GURU, tanggal="2026-11-25", jam="16:30",
                     sekarang=kelas_kit.SESUDAH_UPLOAD)
        kon.commit()
        sesi = kon.execute("SELECT id, mulai FROM jadwal_pertemuan WHERE order_id=? AND ke=1",
                           (tagihan.order_id,)).fetchone()
    catatan.catat(kunci=aturan.kunci_pertemuan(tagihan.order_id, 1), pertemuan_id=sesi["id"], mulai=sesi["mulai"],
                  topik=TOPIK_JURNAL, hadir={tagihan.order_id: "hadir"}, oleh=GURU, peran="guru", pada=PADA,
                  path=catatan_path)
    return tagihan.order_id


def _kumpul(b, siswa, *, akun=AKUN_A, kini=KINI, hari_ini=HARI_INI):
    with database.buka(b.latihan) as kon:
        return orang_tua_guru.kumpulkan_guru(kon, akun, siswa, kini, hari_ini,
                                             path_catatan=b.catatan, path_tugas=b.tugas)


def _total_soal(latihan, sesi_id):
    with database.buka(latihan) as kon:
        return kon.execute("SELECT COUNT(*) FROM sesi_soal WHERE sesi_id=?", (sesi_id,)).fetchone()[0]


def _skenario_anak_a(b):
    """Anak A: Private lunas dengan pertemuan ke-1 hadir, plus satu tugas yang belum dikerjakan."""
    siswa = _siswa_latihan(b.latihan, NAMA_A)
    _anak_privat(b.admin, b.catatan, siswa)
    sesi_id = _sesi(b.latihan, siswa)
    _tugas_catat(b.tugas, sesi_id, siswa)
    return SimpleNamespace(siswa=siswa, sesi_id=sesi_id)


def test_kumpul_positif_kehadiran_dan_tugas_terisi(basis, caplog):
    anak = _skenario_anak_a(basis)
    total = _total_soal(basis.latihan, anak.sesi_id)
    with caplog.at_level(logging.WARNING):
        hasil = _kumpul(basis, anak.siswa)
    assert hasil["kehadiran"] == [{"mulai": MULAI_KE1, "hadir": "hadir", "topik": LABEL_JURNAL}]
    assert hasil["tugas"] == [{"topik": LABEL_TUGAS, "tenggat": TENGGAT, "status_tenggat": "berjalan",
                               "selesai": False, "benar": None, "total": total}]
    assert caplog.records == []


def test_tugas_selesai_membawa_benar_dan_total_dari_skor(basis):
    anak = _skenario_anak_a(basis)
    total = _total_soal(basis.latihan, anak.sesi_id)
    with database.buka(basis.latihan) as kon:
        kon.execute("UPDATE sesi SET selesai=? WHERE id=?", ("2026-11-26T02:30:00", anak.sesi_id))
    tugas = _kumpul(basis, anak.siswa)["tugas"]
    assert tugas[0]["selesai"] is True and tugas[0]["benar"] == 0 and tugas[0]["total"] == total


def test_gerbang_paket_mati_tanpa_kehadiran_dan_db_jadwal_tidak_dibuka(basis, monkeypatch):
    anak = _skenario_anak_a(basis)
    _ganti_sakelar(monkeypatch, "0")
    dibuka = []
    asli = js.buka

    def dicatat(*args, **kwargs):
        dibuka.append(args)
        return asli(*args, **kwargs)
    monkeypatch.setattr(js, "buka", dicatat)
    hasil = _kumpul(basis, anak.siswa)
    assert hasil["kehadiran"] == [] and dibuka == []
    assert len(hasil["tugas"]) == 1


def test_gerbang_tugas_mati_tanpa_tugas_dan_pembaca_tidak_dipanggil(basis, monkeypatch):
    anak = _skenario_anak_a(basis)
    monkeypatch.setattr(guru_tugas_aturan, "GURU_TUGAS_AKTIF", False)
    dipanggil = []
    asli = guru_tugas_dasar.daftar_siswa
    monkeypatch.setattr(guru_tugas_dasar, "daftar_siswa", lambda *a, **k: dipanggil.append(1) or asli(*a, **k))
    hasil = _kumpul(basis, anak.siswa)
    assert hasil["tugas"] == [] and dipanggil == []
    # Gerbang rilis 3c (GURU_TUGAS_AKTIF) berlaku untuk kedua blok: kehadiran ikut mati.
    assert hasil["kehadiran"] == []


@pytest.mark.parametrize("gerbang_tugas,paket,kehadiran_tampil", [
    (False, "1", False),  # gerbang rilis mati, paket hidup: kehadiran tetap mati
    (False, "0", False),
    (True, "0", False),   # paket mati: kehadiran mati
    (True, "1", True),    # keduanya menyala: kehadiran terisi
])
def test_kehadiran_hanya_tampil_bila_gerbang_rilis_dan_paket_sama_sama_menyala(
        basis, monkeypatch, gerbang_tugas, paket, kehadiran_tampil):
    anak = _skenario_anak_a(basis)
    monkeypatch.setattr(guru_tugas_aturan, "GURU_TUGAS_AKTIF", gerbang_tugas)
    _ganti_sakelar(monkeypatch, paket)
    dibuka = []
    asli = js.buka

    def dicatat(*args, **kwargs):
        dibuka.append(args)
        return asli(*args, **kwargs)
    monkeypatch.setattr(js, "buka", dicatat)
    hasil = _kumpul(basis, anak.siswa)
    if kehadiran_tampil:
        assert hasil["kehadiran"] == [{"mulai": MULAI_KE1, "hadir": "hadir", "topik": LABEL_JURNAL}]
    else:
        assert hasil["kehadiran"] == []
    # Gerbang yang mati menghentikan pembukaan DB jadwal sebelum apa pun dibaca.
    assert (dibuka != []) == kehadiran_tampil


def test_galat_blok_tugas_tidak_menjatuhkan_kehadiran_dan_hanya_nama_tipe_yang_dicatat(basis, monkeypatch, caplog):
    anak = _skenario_anak_a(basis)
    monkeypatch.setattr(guru_tugas_dasar, "daftar_siswa", _meledak(sqlite3.OperationalError))
    with caplog.at_level(logging.WARNING):
        hasil = _kumpul(basis, anak.siswa)
    assert hasil["tugas"] == [] and len(hasil["kehadiran"]) == 1
    teks = " ".join(r.getMessage() for r in caplog.records)
    assert "OperationalError" in teks and "akun_" not in teks and GURU not in teks


def test_galat_blok_kehadiran_tidak_menjatuhkan_tugas(basis, monkeypatch, caplog):
    anak = _skenario_anak_a(basis)
    monkeypatch.setattr(guru_pertemuan_ortu, "riwayat_untuk_anak", _meledak(RuntimeError))
    with caplog.at_level(logging.WARNING):
        hasil = _kumpul(basis, anak.siswa)
    assert hasil["kehadiran"] == [] and len(hasil["tugas"]) == 1
    assert "RuntimeError" in " ".join(r.getMessage() for r in caplog.records)


def test_baris_kehadiran_dengan_waktu_rusak_dibuang_dan_tidak_menjatuhkan_halaman(basis, monkeypatch):
    anak = _skenario_anak_a(basis)
    baris = [{"mulai": "bukan-waktu", "hadir": "hadir", "topik": None},
             {"mulai": MULAI_KE1, "hadir": "izin", "topik": LABEL_JURNAL}]
    monkeypatch.setattr(guru_pertemuan_ortu, "riwayat_untuk_anak", lambda *a, **k: baris)
    hasil = _kumpul(basis, anak.siswa)
    assert hasil["kehadiran"] == [{"mulai": MULAI_KE1, "hadir": "izin", "topik": LABEL_JURNAL}]


def test_anak_lain_dan_tugas_yatim_tidak_ikut(basis):
    anak = _skenario_anak_a(basis)
    anak_c = _siswa_latihan(basis.latihan, "Anak Sintetis C")
    _tugas_catat(basis.tugas, _sesi(basis.latihan, anak_c, TOPIK_TUGAS_B), anak_c, TOPIK_TUGAS_B)
    _tugas_catat(basis.tugas, 987654, anak.siswa)  # sesi tidak ada di latihan: yatim, dibuang
    hasil = _kumpul(basis, anak.siswa)
    assert [t["topik"] for t in hasil["tugas"]] == [LABEL_TUGAS]
    assert len(hasil["kehadiran"]) == 1
    hasil_c = _kumpul(basis, anak_c)
    assert [t["topik"] for t in hasil_c["tugas"]] == [LABEL_TUGAS_B] and hasil_c["kehadiran"] == []


def test_urutan_belum_selesai_dulu_dan_batas_sepuluh(basis, monkeypatch):
    daftar = [{"id": n, "sesi_id": n, "siswa_id": 1, "guru_akun": GURU, "topik": TOPIK_TUGAS,
               "tenggat": None, "dibuat": DIBUAT_TUGAS} for n in range(12, 0, -1)]
    skor = {n: {"selesai": n > 2, "benar": n if n > 2 else None, "total": 20 + n} for n in range(1, 13)}
    monkeypatch.setattr(guru_tugas_dasar, "daftar_siswa", lambda siswa_id, **k: daftar)
    monkeypatch.setattr(guru_tugas_baca, "skor_ringkas",
                        lambda kon, pasangan: {sid: skor[sid] for sid, _ in pasangan})
    tugas = _kumpul(basis, 1)["tugas"]
    assert [t["total"] for t in tugas] == [22, 21, 32, 31, 30, 29, 28, 27, 26, 25]
    assert [t["selesai"] for t in tugas] == [False, False] + [True] * 8


def test_keluaran_hanya_kunci_yang_didefinisikan(basis):
    anak = _skenario_anak_a(basis)
    hasil = _kumpul(basis, anak.siswa)
    assert set(hasil) == {"kehadiran", "tugas"}
    assert all(set(item) == KUNCI_KEHADIRAN for item in hasil["kehadiran"])
    assert all(set(item) == KUNCI_TUGAS for item in hasil["tugas"])
    teks = repr(hasil)
    for terlarang in ("akun_", "kor_", "klp_", "sesi", "guru", GURU):
        assert terlarang not in teks, terlarang


def test_hari_ini_wib_bergeser_tujuh_jam():
    assert orang_tua_guru.hari_ini_wib("2026-12-05T18:00:00") == date(2026, 12, 6)
    assert orang_tua_guru.hari_ini_wib("2026-12-05T16:59:59") == date(2026, 12, 5)


def test_status_tenggat_memakai_tanggal_wib_bukan_utc(basis):
    anak = _skenario_anak_a(basis)
    kini = "2026-12-05T18:00:00"  # 6 Des 2026 01.00 WIB: tenggat 5 Des sudah lewat
    hasil = _kumpul(basis, anak.siswa, kini=kini, hari_ini=orang_tua_guru.hari_ini_wib(kini))
    assert hasil["tugas"][0]["status_tenggat"] == guru_tugas_aturan.TENGGAT_LEWAT


# --- HTTP nyata (GET /murid/orang-tua) ---------------------------------------------------------

class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _req(server, jalur, *, data=None, cookie=None):
    isi = None if data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(server.alamat + jalur, data=isi,
                                 method="POST" if isi is not None else "GET")
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        req.add_header("Cookie", "osn_sesi=" + cookie)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)


def _login(server, nama, sandi):
    kode, _, header = _req(server, "/masuk", data={"nama": nama, "sandi": sandi})
    assert kode == 303, kode
    return header["Set-Cookie"].split(";")[0].split("=", 1)[1]


@pytest.fixture
def dunia(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv(guru_tugas_dasar.ENV_DB, str(tmp_path / "guru-tugas.db"))
    monkeypatch.setenv(catatan.ENV_DB, str(tmp_path / "guru-pertemuan.db"))
    monkeypatch.setattr(guru_tugas_aturan, "GURU_TUGAS_AKTIF", True)
    monkeypatch.setattr(pesanan_alur, "_sekarang", lambda: KINI)
    _ganti_sakelar(monkeypatch, "1")
    tirai._reset()
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)
    d = SimpleNamespace(server=server, monkeypatch=monkeypatch, admin=admin_store.BAWAAN, latihan=server.db,
                        catatan=tmp_path / "guru-pertemuan.db", tugas=tmp_path / "guru-tugas.db")
    with server.buka() as kon:
        d.a = database.tambah_siswa(kon, NAMA_A, KELAS_ANAK, pemilik="koordinator-sintetis")
        d.b = database.tambah_siswa(kon, NAMA_B, KELAS_ANAK, pemilik="koordinator-sintetis")
    d.akun_a = auth.tambah_akun_dan_principal("raka-m", SANDI_A, "murid", siswa_id=d.a)
    d.akun_b = auth.tambah_akun_dan_principal("dina-m", SANDI_B, "murid", siswa_id=d.b)
    yield d
    tirai._reset()
    feature_switch.bersihkan_cache()
    server.berhenti()


def _seed_anak_a(d):
    _anak_privat(d.admin, d.catatan, d.a, akun=d.akun_a.id_akun)
    sesi_id = _sesi(d.latihan, d.a)
    _tugas_catat(d.tugas, sesi_id, d.a)
    return sesi_id


def _pasang_pin(d, siswa, pin):
    with d.server.buka() as kon:
        pin_store.simpan(kon, siswa, pin, 1_800_000_000)


def _buka_tirai(d, token):
    kode, _, _ = _req(d.server, RUTE + "/pin", data={"pin": PIN_A}, cookie=token)
    assert kode == 303


def _catat_pembaca(monkeypatch):
    """Pembaca dibungkus pencatat yang tetap meneruskan panggilan (tidak melempar)."""
    dipanggil = []

    def bungkus(modul, nama):
        asli = getattr(modul, nama)

        def catat(*args, **kwargs):
            dipanggil.append(nama)
            return asli(*args, **kwargs)
        monkeypatch.setattr(modul, nama, catat)
    bungkus(guru_pertemuan_ortu, "riwayat_untuk_anak")
    bungkus(guru_tugas_dasar, "daftar_siswa")
    bungkus(guru_tugas_baca, "skor_ringkas")
    return dipanggil


def test_anak_dengan_catatan_dan_tugas_melihat_blok_setelah_login_tanpa_pin(dunia):
    _seed_anak_a(dunia)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200
    blok = _seksi(isi, PENANDA_KEHADIRAN) + _seksi(isi, PENANDA_TUGAS)
    assert "<p>Hadir</p>" in blok and LABEL_JURNAL in blok and LABEL_TUGAS in blok
    assert "<p>Belum dikerjakan</p>" in blok and "<p>Tenggat 5 Des 2026</p>" in blok
    for terlarang in ("akun_", "kor_", "klp_", "ord_", GURU):
        assert terlarang not in blok, terlarang


def test_selesai_tampil_skor_dari_total_soal_di_halaman_http(dunia):
    sesi_id = _seed_anak_a(dunia)
    with dunia.server.buka() as kon:
        kon.execute("UPDATE sesi SET selesai=? WHERE id=?", ("2026-11-26T02:30:00", sesi_id))
    total = _total_soal(dunia.latihan, sesi_id)
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert f"<p>Selesai · 0 dari {total} benar</p>" in _seksi(isi, PENANDA_TUGAS)


def test_tirai_tertutup_tidak_membaca_blok_guru_dan_terbuka_setelah_pin(dunia, monkeypatch):
    _seed_anak_a(dunia)
    _pasang_pin(dunia, dunia.a, PIN_A)
    dipanggil = _catat_pembaca(monkeypatch)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="ortu-pin-masuk"' in isi
    assert PENANDA_KEHADIRAN not in isi and PENANDA_TUGAS not in isi
    assert dipanggil == []
    _buka_tirai(dunia, token)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and PENANDA_KEHADIRAN in isi and PENANDA_TUGAS in isi
    assert dipanggil


def test_anak_a_tidak_melihat_tugas_anak_b(dunia):
    _seed_anak_a(dunia)
    sesi_b = _sesi(dunia.latihan, dunia.b, TOPIK_TUGAS_B)
    _tugas_catat(dunia.tugas, sesi_b, dunia.b, TOPIK_TUGAS_B, "2026-12-09")
    isi_a = _req(dunia.server, RUTE, cookie=_login(dunia.server, "raka-m", SANDI_A))[1]
    assert LABEL_TUGAS_B not in isi_a and "9 Des 2026" not in isi_a
    isi_b = _req(dunia.server, RUTE, cookie=_login(dunia.server, "dina-m", SANDI_B))[1]
    assert LABEL_TUGAS_B in _seksi(isi_b, PENANDA_TUGAS)
    assert LABEL_TUGAS not in isi_b and PENANDA_KEHADIRAN not in isi_b


def test_galat_baca_tugas_halaman_tetap_200_tanpa_blok_tugas(dunia, monkeypatch, caplog):
    _seed_anak_a(dunia)
    monkeypatch.setattr(guru_tugas_dasar, "daftar_siswa", _meledak(sqlite3.OperationalError))
    token = _login(dunia.server, "raka-m", SANDI_A)
    with caplog.at_level(logging.WARNING):
        kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="judul-ortu"' in isi
    assert PENANDA_KEHADIRAN in isi and PENANDA_TUGAS not in isi


def test_galat_tak_terduga_di_kumpulkan_tidak_menjatuhkan_halaman(dunia, monkeypatch):
    _seed_anak_a(dunia)
    dipanggil = []

    def meledak(*args, **kwargs):
        dipanggil.append(1)
        raise RuntimeError("uji: galat sintetis")
    monkeypatch.setattr(orang_tua_guru, "kumpulkan_guru", meledak)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, isi, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200 and 'id="judul-ortu"' in isi
    assert PENANDA_KEHADIRAN not in isi and PENANDA_TUGAS not in isi
    assert dipanggil == [1]


def test_gerbang_tugas_mati_halaman_identik_dengan_halaman_tanpa_blok_guru(dunia, monkeypatch):
    _seed_anak_a(dunia)
    monkeypatch.setattr(guru_tugas_aturan, "GURU_TUGAS_AKTIF", False)
    dibuka = []
    asli = js.buka

    def dicatat(*args, **kwargs):
        dibuka.append(args)
        return asli(*args, **kwargs)
    monkeypatch.setattr(js, "buka", dicatat)
    token = _login(dunia.server, "raka-m", SANDI_A)
    kode, dengan_gerbang, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200
    assert PENANDA_KEHADIRAN not in dengan_gerbang and PENANDA_TUGAS not in dengan_gerbang
    assert dibuka == []
    monkeypatch.setattr(orang_tua_http, "_guru_anak", lambda kon, ctx: None)
    kode, tanpa_blok, _ = _req(dunia.server, RUTE, cookie=token)
    assert kode == 200
    assert dengan_gerbang == tanpa_blok


def test_sakelar_paket_mati_menyembunyikan_kehadiran_dan_menyisakan_tugas(dunia, monkeypatch):
    _seed_anak_a(dunia)
    _ganti_sakelar(monkeypatch, "0")
    token = _login(dunia.server, "raka-m", SANDI_A)
    isi = _req(dunia.server, RUTE, cookie=token)[1]
    assert PENANDA_KEHADIRAN not in isi and PENANDA_TUGAS in isi
