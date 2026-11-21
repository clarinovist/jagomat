"""Riwayat dan progress Latihan Lomba untuk guru/admin lewat HTTP sungguhan (ServerUji).

Data sintetis di tmp_path; sesi dibuat lewat `contest_store`, jawaban benar/salah ditentukan dari kunci yang
dibaca langsung dari DB di sisi uji. Waktu server dipalsukan lewat `contest_guru_http._sekarang`.
"""
import base64
import html
import http.client
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_core as C  # noqa: E402
import contest_guru_http  # noqa: E402
import contest_store as K  # noqa: E402
import database  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

T0 = 1_800_000_000
JARAK_SESI = 5000
SEKARANG_UJI = T0 + 1_000_000
GURU = ("guru", SANDI_GURU)
GURU_LAIN = ("guru-lain", "sandi-guru-lain-123")
ADMIN = ("admin-uji", "sandi-admin-uji-123")
MURID = ("feby", SANDI_MURID)
NAMA_ANAK = "Anak <script>alert(1)</script> & Co"
HEADER_PENTING = ("cache-control", "content-security-policy", "content-type", "x-frame-options", "referrer-policy")


@pytest.fixture()
def s(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    monkeypatch.setattr(contest_guru_http, "_sekarang", lambda: SEKARANG_UJI)
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("guru-lain", GURU_LAIN[1], "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("admin-uji", ADMIN[1], "admin", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        server.anak = database.tambah_siswa(kon, NAMA_ANAK, pemilik="guru")
        server.kosong = database.tambah_siswa(kon, "Anak Kosong", pemilik="guru")
        server.asing = database.tambah_siswa(kon, "Anak Guru Lain", pemilik="guru-lain")
    yield server
    server.berhenti()


def raw(s, jalur, data=None, auth=GURU):
    """Satu permintaan tanpa mengikuti redirect: (status, header huruf kecil, isi bytes)."""
    kepala = {}
    if auth:
        kepala["Authorization"] = "Basic " + base64.b64encode(":".join(auth).encode()).decode()
    tubuh = None
    if data is not None:
        tubuh = urllib.parse.urlencode(data)
        kepala["Content-Type"] = "application/x-www-form-urlencoded"
    k = http.client.HTTPConnection(s.alamat.split("//")[1], timeout=10)
    k.request("POST" if data is not None else "GET", jalur, body=tubuh, headers=kepala)
    r = k.getresponse()
    isi = r.read()
    header = {nama.lower(): nilai for nama, nilai in r.getheaders()}
    k.close()
    return r.status, header, isi


def sidik(hasil):
    kode, header, isi = hasil
    return kode, isi, {k: header[k] for k in HEADER_PENTING if k in header}


def _dump(s):
    with s.buka() as kon:
        return tuple(kon.iterdump())


# --- pembuat sesi sintetis -------------------------------------------------------------------

def _baris(kon, sesi_id):
    return kon.execute("SELECT * FROM lomba_soal WHERE sesi_id=? ORDER BY nomor", (sesi_id,)).fetchall()


def _huruf_kunci(baris):
    return C.HURUF[json.loads(baris["pilihan_json"]).index(baris["kunci"])]


def _jawaban(baris, benar):
    if baris["jenis"] == "isian":
        return baris["kunci"] if benar else str(int(baris["kunci"]) + 1)
    huruf = _huruf_kunci(baris)
    return huruf if benar else next(h for h in C.HURUF if h != huruf)


def buat_sesi(s, siswa_id, urut, benar_sampai, jawab_sampai=10):
    """Sesi selesai: soal <= benar_sampai benar, sampai jawab_sampai salah, sisanya kosong. Mulai T0 + urut*5000."""
    mulai = T0 + urut * JARAK_SESI
    with s.buka() as kon:
        sesi = K.mulai_atau_lanjut(kon, siswa_id, mulai, seed=urut)
        for baris in _baris(kon, sesi.id):
            if baris["nomor"] <= jawab_sampai:
                K.simpan_jawaban(kon, siswa_id, sesi.id, baris["nomor"], _jawaban(baris, baris["nomor"] <= benar_sampai),
                                 mulai + 10)
        K.kumpulkan(kon, siswa_id, sesi.id, mulai + 300)
    return sesi.id


def buat_sesi_berjalan(s, siswa_id, mulai):
    with s.buka() as kon:
        return K.mulai_atau_lanjut(kon, siswa_id, mulai, seed=77).id


def _halaman(s, jalur, auth=GURU):
    kode, _, isi = raw(s, jalur, auth=auth)
    assert kode == 200, (jalur, kode)
    return isi.decode()


@pytest.fixture()
def empat_sesi(s):
    """Nilai 3, 5, 7, 9 (urut 1..4, terlama dulu); mengembalikan {urut: sesi_id}."""
    return {urut: buat_sesi(s, s.anak, urut, nilai) for urut, nilai in ((1, 3), (2, 5), (3, 7), (4, 9))}


# --- halaman progress ---------------------------------------------------------------------------

def test_progress_menampilkan_ringkasan_dengan_angka_yang_benar(s, empat_sesi):
    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert '<span class="hl-stat-nilai">4</span><span class="hl-stat-label">Sesi selesai</span>' in isi
    assert '<span class="hl-stat-nilai">9/10</span><span class="hl-stat-label">Nilai terbaik</span>' in isi
    assert '<span class="hl-stat-nilai">6,0</span><span class="hl-stat-label">Rata-rata nilai</span>' in isi
    assert '<span class="hl-stat-nilai">9/10</span><span class="hl-stat-label">Nilai terakhir</span>' in isi
    assert '<span class="hl-stat-nilai">naik 2,0</span>' in isi


def test_progress_tren_belum_cukup_sesi_dan_turun(s):
    buat_sesi(s, s.anak, 1, 5)
    buat_sesi(s, s.anak, 2, 6)
    assert "belum cukup sesi" in _halaman(s, f"/anak/{s.anak}/lomba")
    buat_sesi(s, s.anak, 3, 4)
    buat_sesi(s, s.anak, 4, 2)

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert '<span class="hl-stat-nilai">turun 1,0</span>' in isi    # nilai 5,6,4,2: rata-rata (6+4+2)/3 - (5+6+4)/3


def test_grafik_memuat_titik_per_sesi_dengan_nilai_dan_label_netral(s, empat_sesi):
    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert re.findall(r'<circle [^>]*data-nilai="(\d+)"', isi) == ["3", "5", "7", "9"]
    assert 'role="img" aria-label="Grafik garis nilai 4 sesi latihan, skala 0 sampai 10, dari sesi 1 sampai sesi 4"' in isi


def test_grafik_dibatasi_tiga_puluh_sesi_terakhir_dengan_nomor_sesi_asli(s):
    for urut in range(1, 33):
        buat_sesi(s, s.anak, urut, urut % 11, jawab_sampai=0)

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert len(re.findall(r"<circle ", isi)) == 30
    assert "dari sesi 3 sampai sesi 32" in isi and "(30 sesi terakhir)" in isi
    assert len(re.findall(r"<tr><td", isi)) == 32


def test_bar_per_topik_total_memakai_angka_dan_persen_dihitung_dari_db(s, empat_sesi):
    benar_sampai = {1: 3, 2: 5, 3: 7, 4: 9}
    hitung = {t: [0, 0] for t in C.TOPIK}
    with s.buka() as kon:
        for urut, sesi_id in empat_sesi.items():
            for baris in _baris(kon, sesi_id):
                hitung[baris["topik"]][0] += int(baris["nomor"] <= benar_sampai[urut])
                hitung[baris["topik"]][1] += 1

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    for topik, (benar, total) in hitung.items():
        if total:
            assert re.search(rf'<span class="hl-topik-nama">{re.escape(C.LABEL_TOPIK[topik])}</span><svg .*?</svg>'
                             rf'<span class="hl-topik-angka">{benar}/{total} \({benar * 100 // total}%\)</span>', isi), topik


def test_riwayat_terbaru_dulu_dengan_tanggal_wib_nilai_waktu_status_dan_tautan_detail(s, empat_sesi):
    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    baris = re.findall(r"<tr><td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td>"
                       r'<td>([^<]*)</td><td[^>]*><a href="([^"]+)">Lihat</a></td></tr>', isi)
    assert [b[5] for b in baris] == [f"/anak/{s.anak}/lomba/{empat_sesi[u]}" for u in (4, 3, 2, 1)]
    assert [b[0] for b in baris] == ["15 Jan 2027, 20:33", "15 Jan 2027, 19:10", "15 Jan 2027, 17:46", "15 Jan 2027, 16:23"]
    assert [b[1] for b in baris] == ["9/10", "7/10", "5/10", "3/10"]
    assert all(b[2] == "05:00" and b[3] == "Selesai" for b in baris)
    assert all(re.search(r"\w+ \d+/\d+", b[4]) for b in baris)


def test_sesi_waktu_habis_tampil_sebagai_waktu_habis_di_riwayat(s):
    sesi_id = buat_sesi_berjalan(s, s.anak, T0)
    with s.buka() as kon:
        K.tutup_yang_habis(kon, s.anak, T0 + 900)

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert '<td class="hl-angka">Waktu habis</td>' in isi and f"/anak/{s.anak}/lomba/{sesi_id}" in isi and "15:00" in isi


def test_paling_sering_salah_urut_salah_terbanyak_dengan_label_dan_hitungan_dari_db(s, empat_sesi):
    benar_sampai = {1: 3, 2: 5, 3: 7, 4: 9}
    hitung = {}
    with s.buka() as kon:
        for urut, sesi_id in empat_sesi.items():
            for baris in _baris(kon, sesi_id):
                akun = hitung.setdefault(baris["template_id"], [0, 0])
                akun[0] += int(baris["nomor"] > benar_sampai[urut])
                akun[1] += 1
    urut = sorted(((t, a) for t, a in hitung.items() if a[0]), key=lambda x: (-x[1][0], -(x[1][0] / x[1][1]), x[0]))[:5]

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    daftar = re.findall(r"<li>([^<]*): salah (\d+) dari (\d+)</li>", isi)
    assert daftar == [(re.sub(r"^(?:bil|ops|ukur|bgn)_", "", t).replace("_", " "), str(a[0]), str(a[1])) for t, a in urut]


def test_topik_dengan_persentase_benar_terendah_disebut(s, empat_sesi):
    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert re.search(r"Persentase benar terendah: <strong>[^<]+</strong> \(\d+%\)", isi)


def test_anak_tanpa_sesi_selesai_menampilkan_keadaan_kosong_ramah(s):
    buat_sesi_berjalan(s, s.kosong, SEKARANG_UJI - 100)

    isi = _halaman(s, f"/anak/{s.kosong}/lomba")

    assert "Belum ada sesi latihan yang selesai" in isi and 'class="hl-stat"' not in isi and "data-nilai" not in isi


def test_halaman_progress_memuat_catatan_bahwa_label_kesalahan_adalah_dugaan(s, empat_sesi):
    assert "Label kesalahan adalah dugaan" in _halaman(s, f"/anak/{s.anak}/lomba")
    assert "Label kesalahan adalah dugaan" in _halaman(s, f"/anak/{s.kosong}/lomba")


def test_progress_hanya_menampilkan_sesi_anak_itu(s, empat_sesi):
    buat_sesi(s, s.asing, 9, 10)

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert '<span class="hl-stat-nilai">4</span><span class="hl-stat-label">Sesi selesai</span>' in isi
    assert "10/10" not in isi


def test_sesi_berjalan_tidak_ikut_riwayat_progress(s, empat_sesi):
    buat_sesi_berjalan(s, s.anak, SEKARANG_UJI - 100)

    isi = _halaman(s, f"/anak/{s.anak}/lomba")

    assert '<span class="hl-stat-nilai">4</span><span class="hl-stat-label">Sesi selesai</span>' in isi
    assert len(re.findall(r">Lihat</a>", isi)) == 4


# --- halaman detail ------------------------------------------------------------------------------

def _wajib_kesalahan(s, sesi_id):
    """Label kesalahan yang harus tampil: untuk tiap jawaban PG salah, label pengecoh yang dipilih anak."""
    daftar = []
    with s.buka() as kon:
        for baris in _baris(kon, sesi_id):
            if baris["jenis"] != "pg":
                continue
            jawaban = kon.execute("SELECT jawaban FROM lomba_jawaban WHERE sesi_id=? AND nomor=?",
                                  (sesi_id, baris["nomor"])).fetchone()
            if jawaban is None or jawaban[0] == _huruf_kunci(baris):
                continue
            teks = json.loads(baris["pilihan_json"])[C.HURUF.index(jawaban[0])]
            daftar += [p["kesalahan"] for p in json.loads(baris["pengecoh_json"]) if p["nilai"] == teks]
    return daftar


def test_detail_menampilkan_kemungkinan_kesalahan_kunci_dan_pembahasan_semua_soal(s):
    sesi_id = buat_sesi(s, s.anak, 1, 0)

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    wajib = _wajib_kesalahan(s, sesi_id)
    assert len(wajib) >= 3
    for label in wajib:
        assert f"Kemungkinan kesalahan: {html.escape(label, quote=True)}" in isi, label
    assert isi.count('class="hl-soal"') == 10 and isi.count("Jawaban anak: <strong>") == 10
    assert isi.count("Jawaban yang benar: <strong>") == 10 and "Nilai</span>" in isi
    with s.buka() as kon:
        for baris in _baris(kon, sesi_id):
            assert all(html.escape(b, quote=True) in isi for b in json.loads(baris["pembahasan_json"]))


def test_detail_sesi_benar_semua_tanpa_kemungkinan_kesalahan(s):
    sesi_id = buat_sesi(s, s.anak, 1, 10)

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert "Kemungkinan kesalahan" not in isi and '<span class="hl-stat-nilai">10/10</span>' in isi


def test_detail_menampilkan_ringkasan_tanggal_waktu_dan_status(s):
    sesi_id = buat_sesi(s, s.anak, 2, 6)

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert '<span class="hl-stat-nilai">6/10</span><span class="hl-stat-label">Nilai</span>' in isi
    assert '<span class="hl-stat-nilai">05:00</span>' in isi and '<span class="hl-stat-nilai">Selesai</span>' in isi
    assert "15 Jan 2027, 17:46" in isi and f'href="/anak/{s.anak}/lomba"' in isi


def test_detail_sesi_yang_lewat_batas_tapi_belum_ditutup_tampil_sebagai_waktu_habis(s):
    sesi_id = buat_sesi_berjalan(s, s.anak, T0)       # _sekarang = T0 + 1_000_000, jauh lewat batas 900 detik

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert '<span class="hl-stat-nilai">Waktu habis</span>' in isi and '<span class="hl-stat-nilai">15:00</span>' in isi


# --- gerbang mati ----------------------------------------------------------------------------------

@pytest.mark.parametrize("bagian", ["lomba", "lomba/1"])
def test_gerbang_mati_respons_identik_dengan_jalur_anak_tak_dikenal_untuk_guru_yang_sama(s, monkeypatch, bagian):
    buat_sesi(s, s.anak, 1, 5)
    monkeypatch.setenv("OSN_LOMBA", "0")

    lomba = raw(s, f"/anak/{s.anak}/{bagian}")
    biasa = raw(s, f"/anak/{s.anak}/jalur-tidak-ada")

    assert sidik(lomba) == sidik(biasa)


def test_gerbang_mati_tidak_menulis_apa_pun(s, monkeypatch):
    sesi_id = buat_sesi_berjalan(s, s.anak, T0)
    monkeypatch.setenv("OSN_LOMBA", "0")
    sebelum = _dump(s)

    raw(s, f"/anak/{s.anak}/lomba")
    raw(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert _dump(s) == sebelum


# --- 404 byte-identik --------------------------------------------------------------------------------

def _tidak_ada(s, auth=GURU, anak_id=None):
    """Referensi: 404 laporan orang tua untuk anak yang bukan milik pemanggil."""
    hasil = raw(s, f"/anak/{anak_id or s.asing}/laporan-ortu", auth=auth)
    assert hasil[0] == 404 and b"Halaman tidak ada" in hasil[2]
    return sidik(hasil)


def test_anak_milik_guru_lain_dan_anak_tidak_ada_dijawab_404_identik(s):
    buat_sesi(s, s.asing, 1, 5)
    referensi = _tidak_ada(s)
    sebelum = _dump(s)

    for jalur in (f"/anak/{s.asing}/lomba", f"/anak/{s.asing}/lomba/1", "/anak/987654/lomba", "/anak/987654/lomba/1"):
        assert sidik(raw(s, jalur)) == referensi, jalur
    assert _dump(s) == sebelum


def test_sesi_milik_anak_lain_sesi_tidak_ada_dan_sesi_berjalan_dijawab_404_identik_tanpa_efek(s):
    punya_asing = buat_sesi(s, s.asing, 1, 5)
    milik_anak = buat_sesi(s, s.anak, 2, 5)
    berjalan = buat_sesi_berjalan(s, s.kosong, SEKARANG_UJI - 100)
    referensi = _tidak_ada(s)
    sebelum = _dump(s)

    assert milik_anak != punya_asing
    for jalur in (f"/anak/{s.anak}/lomba/{punya_asing}", f"/anak/{s.anak}/lomba/987654",
                  f"/anak/{s.kosong}/lomba/{berjalan}"):
        assert sidik(raw(s, jalur)) == referensi, jalur
    assert _dump(s) == sebelum


@pytest.mark.parametrize("jalur", [
    "/anak/abc/lomba", "/anak/1x/lomba", "/anak/-1/lomba", "/anak/%20/lomba", "/anak/%D9%A1/lomba",
    "/anak/1234567890123/lomba", "/anak/1/lomba/abc", "/anak/1/lomba/1x", "/anak/1/lomba/%D9%A1", "/anak/1/lomba/-1",
    "/anak/1/lomba/1234567890123",
])
def test_id_tidak_sah_dijawab_404_identik(s, jalur):
    assert sidik(raw(s, jalur)) == _tidak_ada(s)


def test_sesi_berjalan_milik_anak_sendiri_dijawab_404_dan_tidak_membocorkan_kunci(s):
    berjalan = buat_sesi_berjalan(s, s.anak, SEKARANG_UJI - 100)
    referensi = _tidak_ada(s)

    hasil = raw(s, f"/anak/{s.anak}/lomba/{berjalan}")

    assert sidik(hasil) == referensi


# --- akses -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bagian", ["lomba", "lomba/1"])
def test_murid_masuk_ditolak_seperti_rute_anak_lain(s, bagian):
    buat_sesi(s, s.anak, 1, 5)

    lomba = raw(s, f"/anak/{s.anak}/{bagian}", auth=MURID)
    lain = raw(s, f"/anak/{s.anak}/laporan-ortu", auth=MURID)

    assert lomba[0] == 401 and sidik(lomba) == sidik(lain)


@pytest.mark.parametrize("bagian", ["lomba", "lomba/1"])
def test_anonim_ditolak_seperti_rute_guru_lain(s, bagian):
    lomba = raw(s, f"/anak/{s.anak}/{bagian}", auth=None)
    lain = raw(s, f"/anak/{s.anak}/laporan-ortu", auth=None)

    assert sidik(lomba) == sidik(lain) and lomba[0] in (303, 401)


def test_admin_boleh_melihat_anak_guru_lain_dan_guru_lain_tidak(s):
    sesi_id = buat_sesi(s, s.anak, 1, 5)

    admin = raw(s, f"/anak/{s.anak}/lomba", auth=ADMIN)
    admin_detail = raw(s, f"/anak/{s.anak}/lomba/{sesi_id}", auth=ADMIN)
    lain = raw(s, f"/anak/{s.anak}/lomba", auth=GURU_LAIN)
    lain_detail = raw(s, f"/anak/{s.anak}/lomba/{sesi_id}", auth=GURU_LAIN)

    assert admin[0] == 200 and admin_detail[0] == 200
    assert sidik(lain) == sidik(lain_detail) == _tidak_ada(s, GURU_LAIN, s.anak)
    assert b'class="hl-stat"' not in lain[2] and b"Pembahasan" not in lain_detail[2]


def test_respons_guru_tidak_disimpan_dan_dilindungi_dari_bingkai_dan_referer(s, empat_sesi):
    kode, header, _ = raw(s, f"/anak/{s.anak}/lomba")

    assert kode == 200 and header["cache-control"] == "no-store" and header["x-frame-options"] == "DENY"
    assert header["referrer-policy"] == "no-referrer" and "script-src 'none'" in header["content-security-policy"]


def test_halaman_guru_hanya_lihat_post_tidak_mengubah_apa_pun(s, empat_sesi):
    sebelum = _dump(s)

    for jalur in (f"/anak/{s.anak}/lomba", f"/anak/{s.anak}/lomba/{empat_sesi[1]}"):
        hasil = raw(s, jalur, data={"nilai": "10"})
        assert hasil[0] != 200 and b'class="hl-stat"' not in hasil[2]
    assert _dump(s) == sebelum


def test_melihat_halaman_guru_tidak_mengubah_data_bila_semua_sesi_sudah_selesai(s, empat_sesi):
    sebelum = _dump(s)

    for jalur in (f"/anak/{s.anak}/lomba", f"/anak/{s.anak}/lomba/{empat_sesi[2]}", f"/anak/{s.kosong}/lomba"):
        assert raw(s, jalur)[0] == 200

    assert _dump(s) == sebelum


# --- escape dan markup aman ---------------------------------------------------------------------------

@pytest.mark.parametrize("bagian", ["", "/SESI"])
def test_nama_anak_di_escape_di_halaman_progress_dan_detail(s, empat_sesi, bagian):
    jalur = f"/anak/{s.anak}/lomba" + bagian.replace("/SESI", f"/{empat_sesi[1]}")

    isi = _halaman(s, jalur)

    assert "<script>alert(1)</script>" not in isi and "<script" not in isi
    assert html.escape(NAMA_ANAK, quote=True) in isi
    assert not re.search(r"\son[a-z]+\s*=", isi, re.I)


def test_label_dan_pembahasan_dari_db_di_escape_di_detail(s):
    sesi_id = buat_sesi(s, s.anak, 1, 0)
    with s.buka() as kon:
        kon.execute("UPDATE lomba_soal SET teks = ?, pembahasan_json = ? WHERE sesi_id = ? AND nomor = 1",
                    ('<img src=x onerror=alert(1)> & "teks"', json.dumps(["<script>langkah</script>"]), sesi_id))

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert "<img src=x" not in isi and "<script>langkah" not in isi
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; &quot;teks&quot;" in isi and "&lt;script&gt;langkah&lt;/script&gt;" in isi


def test_label_kesalahan_dari_db_di_escape_di_detail(s):
    sesi_id = buat_sesi(s, s.anak, 1, 0)
    with s.buka() as kon:
        baris = next(b for b in _baris(kon, sesi_id) if b["jenis"] == "pg")
        pengecoh = [dict(p, kesalahan="<b>lupa</b> & salah") for p in json.loads(baris["pengecoh_json"])]
        kon.execute("UPDATE lomba_soal SET pengecoh_json = ? WHERE sesi_id = ? AND nomor = ?",
                    (json.dumps(pengecoh), sesi_id, baris["nomor"]))

    isi = _halaman(s, f"/anak/{s.anak}/lomba/{sesi_id}")

    assert "<b>lupa</b>" not in isi and "Kemungkinan kesalahan: &lt;b&gt;lupa&lt;/b&gt; &amp; salah" in isi


# --- tautan di halaman satu anak ------------------------------------------------------------------------

def _tab(s, section, auth=GURU):
    kode, isi, _ = s.minta(f"/anak/{s.anak}?section={section}", auth=auth)
    assert kode == 200
    return isi


def test_tautan_latihan_lomba_ada_sekali_di_tab_perkembangan_saat_gerbang_hidup(s):
    isi = _tab(s, "perkembangan")

    assert isi.count(f'href="/anak/{s.anak}/lomba"') == 1 and "Latihan lomba" in isi


def test_tautan_latihan_lomba_tidak_ada_saat_gerbang_mati(s, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")

    assert "/lomba" not in _tab(s, "perkembangan")


def test_hanya_kartu_lomba_yang_berbeda_antara_gerbang_hidup_dan_mati_dan_tab_lain_identik(s, monkeypatch):
    import contest_guru_pages

    hidup = {sec: _tab(s, sec) for sec in ("rencana", "latihan", "riwayat", "perkembangan")}
    monkeypatch.setenv("OSN_LOMBA", "0")
    mati = {sec: _tab(s, sec) for sec in hidup}

    for sec in ("rencana", "latihan", "riwayat"):
        assert hidup[sec] == mati[sec], sec
    assert hidup["perkembangan"].replace(contest_guru_pages.kartu_masuk(s.anak), "") == mati["perkembangan"]
