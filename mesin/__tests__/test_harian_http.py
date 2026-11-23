"""Latihan Harian lewat HTTP sungguhan (ServerUji): gerbang sakelar, akses, alur sesi, isolasi anak, batas gratis, kebocoran.

Waktu memakai epoch literal dan jam server dipalsukan lewat `harian_http._sekarang`; seed lewat
`harian_latihan_store._seed_baru`. Data sepenuhnya sintetis di tmp_path.
"""
import itertools
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import akses_harian  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import harian_http  # noqa: E402
import harian_latihan_store as hs  # noqa: E402
from http_test_kit import SANDI_MURID, ServerUji, _basic  # noqa: E402

T0 = 1_800_000_000  # 2027-01-15 15:00 WIB
SANDI_DUA = "sandi-budi-12345"
MURID_SATU = ("feby", SANDI_MURID)
MURID_DUA = ("budi-uji", SANDI_DUA)
HEADER_PENTING = ("location", "cache-control", "content-security-policy", "content-type")
DASAR = "/murid/latihan-harian"
RUTE_GET = (DASAR, DASAR + "/sesi/1?no=1", DASAR + "/sesi/1", DASAR + "/sesi/1/ringkasan")
RUTE_POST = (DASAR + "/mulai", DASAR + "/sesi/1/jawab")
COPY_HABIS = "Jatah latihan gratis hari ini sudah dipakai"


class _Jam:
    def __init__(self, awal):
        self.t = awal

    def __call__(self):
        return self.t


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Hasil:
    def __init__(self, kode, isi, header):
        self.kode, self.isi = kode, isi
        self.header = {k.lower(): v for k, v in header.items()}

    @property
    def lokasi(self):
        return self.header.get("location")

    def sidik(self):
        return self.kode, self.isi, {k: self.header[k] for k in HEADER_PENTING if k in self.header}


def _minta(uji, jalur, *, auth_=None, data=None, isi_mentah=None, header=None, tipe="application/x-www-form-urlencoded"):
    isi = isi_mentah if isi_mentah is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
    req = urllib.request.Request(uji.alamat + jalur, data=isi, method="POST" if isi is not None else "GET")
    if isi is not None:
        req.add_header("Content-Type", tipe)
    if auth_:
        req.add_header("Authorization", _basic(*auth_))
    for nama, nilai in (header or {}).items():
        req.add_header(nama, nilai)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(req, timeout=10) as r:
            return Hasil(r.status, r.read().decode("utf-8", "replace"), dict(r.headers))
    except urllib.error.HTTPError as e:
        return Hasil(e.code, e.read().decode("utf-8", "replace"), dict(e.headers))


@pytest.fixture
def jam(monkeypatch):
    jam_uji = _Jam(T0)
    monkeypatch.setattr(harian_http, "_sekarang", jam_uji)
    return jam_uji


@pytest.fixture
def server(tmp_path, monkeypatch, jam):
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    benih = itertools.count(501)
    monkeypatch.setattr(hs, "_seed_baru", lambda: next(benih))
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            uji.anak_satu = database.tambah_siswa(kon, "feby", pemilik="guru")
            uji.anak_dua = database.tambah_siswa(kon, "Budi Sintetis", pemilik="guru")
        auth.tambah_akun("budi-uji", SANDI_DUA, "murid", siswa_id=uji.anak_dua)
        yield uji
    finally:
        uji.berhenti()


def _get(uji, jalur, pengguna=MURID_SATU):
    return _minta(uji, jalur, auth_=pengguna)


def _post(uji, jalur, data=None, pengguna=MURID_SATU, **kw):
    return _minta(uji, jalur, auth_=pengguna, data={} if data is None else data, **kw)


def _mulai(uji, tingkat="t3", pengguna=MURID_SATU):
    hasil = _post(uji, DASAR + "/mulai", {"tingkat": tingkat}, pengguna)
    cocok = re.fullmatch(r"/murid/latihan-harian/sesi/(\d+)\?no=(\d+)", hasil.lokasi or "")
    assert hasil.kode == 303 and cocok, (hasil.kode, hasil.lokasi)
    return int(cocok.group(1))


def _db(uji, sql, args=()):
    with uji.buka() as kon:
        return [tuple(b) for b in kon.execute(sql, args)]


def _kunci_huruf(uji, sesi, nomor):
    return "ABCD"[_db(uji, "SELECT kunci_indeks FROM harian_soal WHERE sesi_id=? AND nomor=?", (sesi, nomor))[0][0]]


def _pembahasan(uji, sesi, nomor):
    return _db(uji, "SELECT pembahasan FROM harian_soal WHERE sesi_id=? AND nomor=?", (sesi, nomor))[0][0]


def _jawab(uji, sesi, nomor, huruf, pengguna=MURID_SATU):
    return _post(uji, "%s/sesi/%d/jawab" % (DASAR, sesi), {"no": str(nomor), "pilihan": huruf}, pengguna)


def _selesaikan(uji, sesi, pengguna=MURID_SATU, benar=True):
    for n in range(1, 11):
        kunci = _kunci_huruf(uji, sesi, n)
        huruf = kunci if benar else next(h for h in "ABCD" if h != kunci)
        assert _jawab(uji, sesi, n, huruf, pengguna).kode == 303


def _tabel_harian(uji):
    return {t: _db(uji, "SELECT * FROM %s ORDER BY 1, 2" % t) for t in ("harian_sesi", "harian_soal", "harian_jawaban")}


def _tidak_ada(uji, pengguna=MURID_SATU):
    return _get(uji, "/murid/tidak-ada", pengguna)


def _hapus_html(isi):
    """Teks tampak saja: tanpa blok <style>/<script> dan tanpa tag."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script)\b.*?</\1>", " ", isi, flags=re.S))


# 1 --- gerbang mati ------------------------------------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_GET)
@pytest.mark.parametrize("pengguna", [MURID_SATU, None], ids=["murid", "anonim"])
def test_sakelar_mati_get_identik_dengan_jalur_murid_tak_dikenal(server, monkeypatch, jalur, pengguna):
    monkeypatch.setenv("LATIHAN_HARIAN", "0")

    harian = _get(server, jalur, pengguna)
    biasa = _get(server, "/murid/tidak-ada", pengguna)

    assert harian.sidik() == biasa.sidik()
    assert (harian.kode == 404) if pengguna else (harian.kode == 303)


@pytest.mark.parametrize("jalur", RUTE_POST)
@pytest.mark.parametrize("pengguna", [MURID_SATU, None], ids=["murid", "anonim"])
def test_sakelar_mati_post_identik_dengan_jalur_tak_dikenal_dan_tanpa_efek(server, monkeypatch, jalur, pengguna):
    monkeypatch.setenv("LATIHAN_HARIAN", "0")
    sebelum = _tabel_harian(server)

    harian = _post(server, jalur, {"tingkat": "t3", "no": "1", "pilihan": "A"}, pengguna)
    biasa = _post(server, "/murid/tidak-ada", {"tingkat": "t3", "no": "1", "pilihan": "A"}, pengguna)

    assert harian.sidik() == biasa.sidik()
    assert _tabel_harian(server) == sebelum == {"harian_sesi": [], "harian_soal": [], "harian_jawaban": []}


def test_sakelar_mati_beranda_murid_tanpa_kartu(server, monkeypatch):
    monkeypatch.setenv("LATIHAN_HARIAN", "0")

    isi = _get(server, "/murid").isi

    assert "Latihan Harian" not in isi and "judul-harian" not in isi


# 2 --- gerbang hidup, anonim ---------------------------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_GET)
def test_anonim_get_dialihkan_ke_masuk(server, jalur):
    hasil = _get(server, jalur, None)

    assert hasil.kode == 303 and hasil.lokasi == "/masuk"


@pytest.mark.parametrize("jalur", RUTE_POST)
def test_anonim_post_ditolak_401_tanpa_efek(server, jalur):
    hasil = _post(server, jalur, {"tingkat": "t3", "no": "1", "pilihan": "A"}, None)

    assert hasil.kode == 401
    assert _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 0


# 3 --- beranda ------------------------------------------------------------------------------------

def test_beranda_menampilkan_delapan_tingkat_dengan_judul_materi(server):
    hasil = _get(server, DASAR)

    assert hasil.kode == 200 and hasil.header["cache-control"] == "no-store"
    for kode in ("t1", "t2", "t3", "t4", "t5", "t6", "osn-pemula", "osn-lanjut"):
        assert 'name="tingkat" value="%s"' % kode in hasil.isi
    assert "Tantangan OSN Pemula" in hasil.isi and "Tantangan OSN Lanjut" in hasil.isi
    assert "Kelas" not in _hapus_html(hasil.isi)


def test_beranda_menandai_saran_dari_profil_kelas_anak(server):
    with server.buka() as kon:
        kon.execute("INSERT INTO profil_belajar(siswa_id, kelas_sekolah, revisi) VALUES (?, 5, 1)", (server.anak_satu,))

    isi = _get(server, DASAR).isi

    cocok = re.search(r'value="(\w[\w-]*)">\s*<button[^>]*><b>[^<]*</b><span>[^<]*</span><span class="hr-lencana">Disarankan', isi)
    assert cocok and cocok.group(1) == "t5"
    assert "Disarankan untukmu" not in _get(server, DASAR, MURID_DUA).isi  # anak lain tanpa profil: tanpa saran


# 4 --- mulai ---------------------------------------------------------------------------------------

def test_mulai_membuat_sesi_untuk_anak_dari_sesi_login_dan_mengalihkan_ke_soal_pertama(server):
    sesi = _mulai(server, "t4")

    baris = _db(server, "SELECT siswa_id, tingkat, jumlah_soal, status FROM harian_sesi WHERE id=?", (sesi,))
    assert baris == [(server.anak_satu, "t4", 10, "berjalan")]
    assert _db(server, "SELECT COUNT(*) FROM harian_soal WHERE sesi_id=?", (sesi,))[0][0] == 10


@pytest.mark.parametrize("data", [{}, {"tingkat": "t9"}, {"tingkat": ""}, {"tingkat": "t3", "siswa_id": "2"},
                                  {"tingkat": "t3", "x": "1"}])
def test_mulai_isian_tak_sah_ditolak_400_tanpa_efek(server, data):
    hasil = _post(server, DASAR + "/mulai", data)

    assert hasil.kode == 400
    assert _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 0


def test_mulai_dengan_content_type_bukan_form_ditolak(server):
    hasil = _minta(server, DASAR + "/mulai", auth_=MURID_SATU, isi_mentah=b'{"tingkat": "t3"}', tipe="application/json")

    assert hasil.kode == 400
    assert _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 0


def test_mulai_lagi_saat_berjalan_melanjutkan_sesi_yang_sama(server):
    pertama = _mulai(server, "t3")

    kedua = _mulai(server, "t5")

    assert kedua == pertama and _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 1


def test_beranda_saat_berjalan_menawarkan_lanjutkan(server):
    sesi = _mulai(server, "t3")
    _jawab(server, sesi, 1, "A")

    isi = _get(server, DASAR).isi

    assert "Latihanmu masih berjalan" in isi and "Lanjutkan" in isi and ("sesi/%d?no=2" % sesi) in isi
    assert 'name="tingkat"' not in isi


# 4b --- CSRF: asal lintas situs ditolak tanpa efek ----------------------------------------------------

ASAL_ASING = [{"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://contoh.example"}]


@pytest.mark.parametrize("header", ASAL_ASING, ids=["cross-site", "origin-asing"])
def test_post_mulai_lintas_situs_ditolak_tanpa_efek(server, header):
    hasil = _minta(server, DASAR + "/mulai", auth_=MURID_SATU, data={"tingkat": "t3"}, header=header)

    assert hasil.kode == 403
    assert _tabel_harian(server) == {"harian_sesi": [], "harian_soal": [], "harian_jawaban": []}


@pytest.mark.parametrize("header", ASAL_ASING, ids=["cross-site", "origin-asing"])
def test_post_jawab_lintas_situs_ditolak_tanpa_efek(server, header):
    sesi = _mulai(server)
    sebelum = _tabel_harian(server)

    hasil = _minta(server, "%s/sesi/%d/jawab" % (DASAR, sesi), auth_=MURID_SATU, data={"no": "1", "pilihan": "A"}, header=header)

    assert hasil.kode == 403
    assert _tabel_harian(server) == sebelum


def test_post_mulai_asal_sama_tetap_diterima(server):
    hasil = _minta(server, DASAR + "/mulai", auth_=MURID_SATU, data={"tingkat": "t3"},
                   header={"Sec-Fetch-Site": "same-origin"})

    assert hasil.kode == 303


# 5 --- soal tanpa kebocoran ----------------------------------------------------------------------

def _label_pilihan(isi):
    return re.findall(r'<label class="hr-pilih">.*?</label>', isi, re.S)


def test_soal_belum_dijawab_tanpa_pembahasan_kunci_dan_markup_pilihan_seragam(server):
    sesi = _mulai(server)

    hasil = _get(server, "%s/sesi/%d?no=1" % (DASAR, sesi))

    assert hasil.kode == 200 and hasil.header["cache-control"] == "no-store"
    for n in range(1, 11):  # pembahasan satu pun soal sesi ini tidak ada di halaman
        assert _pembahasan(server, sesi, n) not in hasil.isi
    for kata in ("Caranya", "Jawaban yang benar", "Jawabanmu", "Benar! Hebat", "Belum tepat", "kunci_indeks"):
        assert kata not in hasil.isi
    label = _label_pilihan(hasil.isi)
    assert len(label) == 4
    seragam = {re.sub(r'value="[A-D]"|<span class="hr-huruf">[A-D]</span>|<span class="hr-isi-pilihan">.*?</span>', "", x, flags=re.S)
               for x in label}
    assert len(seragam) == 1  # posisi/kebenaran tidak membedakan markup
    assert "data-" not in "".join(label) and "checked" not in "".join(label)
    assert not re.search(r'class="hr-pilih (benar|salah)', hasil.isi)


def test_jawab_mengunci_lalu_halaman_menampilkan_benar_salah_dan_pembahasan(server):
    sesi = _mulai(server)
    kunci = _kunci_huruf(server, sesi, 1)
    salah = next(h for h in "ABCD" if h != kunci)

    kirim = _jawab(server, sesi, 1, salah)
    halaman = _get(server, kirim.lokasi)

    assert kirim.kode == 303 and kirim.lokasi == "%s/sesi/%d?no=1" % (DASAR, sesi)
    assert "Belum tepat" in halaman.isi and "Caranya" in halaman.isi and "Jawaban yang benar" in halaman.isi
    assert _pembahasan(server, sesi, 1).split("\n")[0][:20] in halaman.isi.replace("<br>", "\n")
    assert 'type="radio"' not in halaman.isi  # terkunci: tidak ada kontrol jawab
    assert ("sesi/%d?no=2" % sesi) in halaman.isi  # tombol lanjut
    assert _db(server, "SELECT pilihan, benar FROM harian_jawaban WHERE sesi_id=? AND nomor=1", (sesi,)) == [
        ("ABCD".index(salah), 0)]


def test_jawab_benar_menampilkan_umpan_benar(server):
    sesi = _mulai(server)

    _jawab(server, sesi, 1, _kunci_huruf(server, sesi, 1))

    assert "Benar! Hebat." in _get(server, "%s/sesi/%d?no=1" % (DASAR, sesi)).isi


def test_soal_berikutnya_tidak_bocor_setelah_menjawab_soal_sebelumnya(server):
    sesi = _mulai(server)
    _jawab(server, sesi, 1, "A")

    halaman2 = _get(server, "%s/sesi/%d?no=2" % (DASAR, sesi))

    assert halaman2.kode == 200 and "Caranya" not in halaman2.isi
    for n in range(2, 11):
        assert _pembahasan(server, sesi, n) not in halaman2.isi


def test_soal_tanpa_parameter_no_membuka_soal_berikutnya_yang_belum_dijawab(server):
    sesi = _mulai(server)
    _jawab(server, sesi, 1, "A")

    tanpa = _get(server, "%s/sesi/%d" % (DASAR, sesi))

    assert tanpa.kode == 200 and "Soal 2 dari 10" in tanpa.isi


@pytest.mark.parametrize("no", ["2", "10", "0", "11", "-1", "abc", "1.5", "", "001", "99999"])
def test_nomor_soal_belum_gilirannya_atau_tak_sah_404_identik(server, no):
    sesi = _mulai(server)
    biasa = _tidak_ada(server)

    hasil = _get(server, "%s/sesi/%d?no=%s" % (DASAR, sesi, no))

    assert hasil.sidik() == biasa.sidik()


def test_nomor_ganda_di_query_404(server):
    sesi = _mulai(server)

    assert _get(server, "%s/sesi/%d?no=1&no=1" % (DASAR, sesi)).sidik() == _tidak_ada(server).sidik()


def test_jawab_soal_yang_belum_gilirannya_404_tanpa_efek(server):
    sesi = _mulai(server)
    sebelum = _tabel_harian(server)

    hasil = _jawab(server, sesi, 2, "A")

    assert hasil.kode == 404 and hasil.isi == _tidak_ada(server).isi
    assert _tabel_harian(server) == sebelum


# 6 --- jawab sekali ------------------------------------------------------------------------------

def test_jawab_kedua_soal_sama_tidak_mengubah_apa_pun(server):
    sesi = _mulai(server)
    kunci = _kunci_huruf(server, sesi, 1)
    salah = next(h for h in "ABCD" if h != kunci)
    _jawab(server, sesi, 1, salah)
    sebelum = _tabel_harian(server)

    kedua = _jawab(server, sesi, 1, kunci)

    assert kedua.kode == 303 and kedua.lokasi == "%s/sesi/%d?no=1" % (DASAR, sesi)
    assert _tabel_harian(server) == sebelum
    assert sebelum["harian_jawaban"][0][3] == 0  # tetap salah, tidak berubah jadi benar


@pytest.mark.parametrize("data", [{"no": "1"}, {"pilihan": "A"}, {"no": "1", "pilihan": "E"}, {"no": "1", "pilihan": "a"},
                                  {"no": "x", "pilihan": "A"}, {"no": "1", "pilihan": "A", "siswa_id": "2"}])
def test_jawab_isian_tak_sah_tanpa_efek(server, data):
    sesi = _mulai(server)

    hasil = _post(server, "%s/sesi/%d/jawab" % (DASAR, sesi), data)

    assert hasil.kode in (400, 404)
    assert _db(server, "SELECT COUNT(*) FROM harian_jawaban")[0][0] == 0


# 7 --- ringkasan -----------------------------------------------------------------------------------

def test_sesi_penuh_ringkasan_jumlah_benar_tanpa_peringkat(server):
    sesi = _mulai(server)
    assert _get(server, "%s/sesi/%d/ringkasan" % (DASAR, sesi)).kode == 303  # belum selesai: kembali ke soal
    for n in range(1, 11):
        kunci = _kunci_huruf(server, sesi, n)
        _jawab(server, sesi, n, kunci if n <= 6 else next(h for h in "ABCD" if h != kunci))

    soal_terakhir = _get(server, "%s/sesi/%d?no=10" % (DASAR, sesi))
    hasil = _get(server, "%s/sesi/%d/ringkasan" % (DASAR, sesi))

    assert ("sesi/%d/ringkasan" % sesi) in soal_terakhir.isi and "Lihat hasilku" in soal_terakhir.isi
    assert hasil.kode == 200 and "6 dari 10" in _hapus_html(hasil.isi).replace("  ", " ")
    for kata in ("peringkat", "persentil", "juara", "dibanding"):
        assert kata not in hasil.isi.lower()
    assert _db(server, "SELECT status FROM harian_sesi WHERE id=?", (sesi,)) == [("selesai",)]
    assert _get(server, "%s/sesi/%d" % (DASAR, sesi)).lokasi == "%s/sesi/%d/ringkasan" % (DASAR, sesi)


# 8 --- batas gratis --------------------------------------------------------------------------------

def test_batas_gratis_satu_sesi_dimulai_per_hari_wib_dengan_halaman_ramah(server, jam):
    sesi = _mulai(server)
    _selesaikan(server, sesi)

    kedua = _post(server, DASAR + "/mulai", {"tingkat": "t3"})
    beranda = _get(server, kedua.lokasi)

    assert kedua.kode == 303 and kedua.lokasi == DASAR
    assert COPY_HABIS in beranda.isi and 'href="/murid/orang-tua"' in beranda.isi
    assert 'name="tingkat"' not in beranda.isi
    assert _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 1
    jam.t = T0 + 9 * 3600 + 60  # 00:01 WIB hari berikutnya (literal; T0 = 15:00 WIB)
    assert _mulai(server) != sesi


def test_batas_gratis_tidak_menghalangi_menyelesaikan_sesi_yang_sudah_berjalan(server, jam):
    sesi = _mulai(server)

    assert _mulai(server) == sesi  # lanjut tidak dihitung
    assert _jawab(server, sesi, 1, "A").kode == 303


def test_tanpa_batas_untuk_les_atau_langganan(server, monkeypatch):
    monkeypatch.setattr(akses_harian, "akses", lambda k, s, kini: akses_harian.Akses(True, "les", None))
    pertama = _mulai(server)
    _selesaikan(server, pertama)

    assert _mulai(server) != pertama


def test_batas_gratis_per_anak(server):
    sesi = _mulai(server)
    _selesaikan(server, sesi)

    assert _mulai(server, "t2", MURID_DUA) != sesi


# 9 --- isolasi anak ------------------------------------------------------------------------------

def test_anak_lain_tidak_bisa_membaca_menjawab_atau_melihat_hasil_dan_tanpa_efek(server):
    sesi = _mulai(server)
    _jawab(server, sesi, 1, "A")
    sebelum = _tabel_harian(server)
    biasa = _tidak_ada(server, MURID_DUA).sidik()

    asing = [
        _get(server, "%s/sesi/%d?no=1" % (DASAR, sesi), MURID_DUA),
        _get(server, "%s/sesi/%d" % (DASAR, sesi), MURID_DUA),
        _get(server, "%s/sesi/%d/ringkasan" % (DASAR, sesi), MURID_DUA),
        _jawab(server, sesi, 2, "A", MURID_DUA),
        _jawab(server, sesi, 1, "B", MURID_DUA),
    ]

    for hasil in asing:
        assert hasil.kode == 404 and hasil.isi == _tidak_ada(server, MURID_DUA).isi
    assert _tabel_harian(server) == sebelum
    assert biasa[0] == 404


def test_sesi_tak_ada_atau_id_bukan_angka_404_identik(server):
    biasa = _tidak_ada(server).sidik()

    for jalur in (DASAR + "/sesi/99999?no=1", DASAR + "/sesi/abc", DASAR + "/sesi/-1?no=1", DASAR + "/sesi/1234567890123?no=1",
                  DASAR + "/sesi/", DASAR + "/sesi", DASAR + "/mulai"):
        assert _get(server, jalur).sidik() == biasa, jalur


def test_id_siswa_dari_query_atau_form_diabaikan_atau_ditolak_anak_lain_tidak_tersentuh(server):
    sesi = _mulai(server, "t3")
    asal = _db(server, "SELECT siswa_id FROM harian_sesi")[0][0]
    assert asal == server.anak_satu

    # Anak 2 memakai parameter siswa= anak 1: tetap tidak melihat sesi anak 1.
    lihat = _get(server, "%s/sesi/%d?no=1&siswa=%d&siswa_id=%d" % (DASAR, sesi, server.anak_satu, server.anak_satu), MURID_DUA)
    assert lihat.kode == 404
    # Mulai dengan siswa_id di form ditolak; sesi tidak terbuat untuk anak 2.
    assert _post(server, DASAR + "/mulai", {"tingkat": "t2", "siswa_id": str(server.anak_satu)}, MURID_DUA).kode == 400
    # Mulai dengan query siswa=: diabaikan, sesi untuk anak sesi login.
    dua = _post(server, DASAR + "/mulai?siswa=%d" % server.anak_satu, {"tingkat": "t2"}, MURID_DUA)
    assert dua.kode == 303
    assert _db(server, "SELECT siswa_id FROM harian_sesi ORDER BY id") == [(server.anak_satu,), (server.anak_dua,)]


def test_guru_diperlakukan_sama_seperti_di_beranda_murid_dan_tanpa_efek(server):
    from http_test_kit import SANDI_GURU
    guru = ("guru", SANDI_GURU)

    hasil = _get(server, DASAR, guru)
    pos = _post(server, DASAR + "/mulai", {"tingkat": "t3"}, guru)

    assert hasil.sidik() == _get(server, "/murid", guru).sidik()
    assert pos.kode in (303, 401, 404) and _db(server, "SELECT COUNT(*) FROM harian_sesi")[0][0] == 0


# 10 --- bukan bukti siklus ------------------------------------------------------------------------

def test_sesi_http_penuh_tidak_mengubah_satu_pun_tabel_non_harian(server):
    daftar = [b[0] for b in _db(server, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'harian_%' "
                                         "AND name NOT LIKE 'sqlite_%'")]
    sebelum = {t: _db(server, "SELECT * FROM %s" % t) for t in daftar}

    sesi = _mulai(server, "t5")
    _selesaikan(server, sesi)
    _get(server, "%s/sesi/%d?no=3" % (DASAR, sesi))
    _get(server, "%s/sesi/%d/ringkasan" % (DASAR, sesi))
    _get(server, "/murid")

    assert {t: _db(server, "SELECT * FROM %s" % t) for t in daftar} == sebelum


# 11 --- kartu beranda murid -----------------------------------------------------------------------

def test_kartu_beranda_murid_tingkat_titik_dan_tombol(server):
    awal = _get(server, "/murid").isi

    assert 'id="judul-harian"' in awal and "Latihan Harian" in awal and "Pilih tingkatmu" in awal
    assert awal.count('class="hr-titik"') == 7 and "Mulai latihan" in awal
    sesi = _mulai(server, "t3")
    _jawab(server, sesi, 1, "A")
    lanjut = _get(server, "/murid").isi
    assert "Tingkat 3" in lanjut and "Lanjutkan" in lanjut and ("sesi/%d?no=2" % sesi) in lanjut
    assert re.search(r'<li class="ada">', lanjut)  # hari ini bertitik


def test_kartu_beranda_saat_jatah_habis(server):
    sesi = _mulai(server)
    _selesaikan(server, sesi)

    isi = _get(server, "/murid").isi

    assert "Jatah latihan gratis hari ini sudah dipakai" in isi and "Lihat latihan" in isi


def test_kartu_beranda_anak_lain_tidak_memuat_riwayat_anak_ini(server):
    sesi = _mulai(server, "t3")
    _jawab(server, sesi, 1, "A")

    isi = _get(server, "/murid", MURID_DUA).isi

    assert "Pilih tingkatmu" in isi and '<li class="ada">' not in isi


# 12 --- ringkasan di halaman orang tua -------------------------------------------------------------

def test_halaman_orang_tua_menampilkan_ringkasan_hanya_bila_sakelar_hidup(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    sesi = _mulai(server, "t3")
    for n in range(1, 5):
        _jawab(server, sesi, n, _kunci_huruf(server, sesi, n) if n <= 3 else next(h for h in "ABCD" if h != _kunci_huruf(server, sesi, n)))

    hidup = _get(server, "/murid/orang-tua")
    monkeypatch.setenv("LATIHAN_HARIAN", "0")
    mati = _get(server, "/murid/orang-tua")

    assert hidup.kode == 200 and 'id="ortu-harian"' in hidup.isi
    teks = _hapus_html(hidup.isi)
    assert "Tingkat 3" in teks and "4" in teks and "75%" in teks
    assert 'id="ortu-harian"' not in mati.isi
    for kata in ("pembahasan", "jawaban benar", "kunci"):
        assert kata not in teks.lower()


def test_halaman_orang_tua_anak_lain_tidak_melihat_ringkasan_anak_ini(server, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    sesi = _mulai(server, "t3")
    _jawab(server, sesi, 1, "A")

    isi = _hapus_html(_get(server, "/murid/orang-tua", MURID_DUA).isi)

    assert "Belum ada Latihan Harian" in isi
