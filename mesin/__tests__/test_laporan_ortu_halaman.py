"""Tahap 3 G3: halaman baca-saja orang tua (renderer murni + rute token tanpa login)."""
import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import parent_report_page as halaman  # noqa: E402
import parent_report_store as toko  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

ISI = {"versi": 1, "topik": ["Pola Bilangan", "Geometri Datar"],
       "tahap": {"nomor": 3, "label": "Latihan", "uraian": "Anak berlatih mengerjakan soal."},
       "langkah": "Coba sendiri beberapa soal pendek di rumah."}
DATA = {"nama": "Bima", "isi": ISI, "catatan": "Sudah lebih tenang membaca soal.\nMinggu depan soal cerita.",
        "guru": "Bu Feby", "periode": ("2026-11-01", "2026-11-30"),
        "diterbitkan": "2026-12-01 09:30:00", "kedaluarsa": 1_798_000_000}
MODUL = Path(halaman.__file__)


def _teks_tampil(html):
    tanpa_gaya = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", tanpa_gaya)


def test_isi_halaman_sesuai_acceptance():
    h = halaman.render_laporan(**DATA).decode()
    teks = _teks_tampil(h)
    for harus in ("Bima", "1 – 30 November 2026", "Pola Bilangan", "Geometri Datar", "Latihan (3 dari 6)",
                  "Coba sendiri beberapa soal pendek di rumah.", "Sudah lebih tenang membaca soal.",
                  "Bu Feby", "1 Desember 2026"):
        assert harus in teks, harus
    assert "<title>Laporan belajar" in h and "Bima" not in re.search(r"<title>.*?</title>", h).group(0)
    assert 'lang="id"' in h and h.count("<h1") == 1 and h.count("<main") == 1


def test_tanpa_skrip_form_tautan_og_dan_alamat_luar():
    h = halaman.render_laporan(**DATA).decode()
    for terlarang in ("<script", "<form", "<a ", "<a>", "onclick", "javascript:", "https://", "http://",
                      "og:", "twitter:", "<img", "<iframe", "@import", "fonts.googleapis"):
        assert terlarang not in h, terlarang


def test_teks_tampil_bebas_istilah_internal():
    h = halaman.render_laporan(**DATA).decode()
    teks = _teks_tampil(h)
    for pola in (r"malrule", r"miskonsepsi", r"diagnos", r"kunci", r"/sesi/", r"\bP[3-6]\b", r"Variasi ",
                 r"benar\s*/", r"%", r"#\d", r"\b[BKHETN]\b(?=\s*[:=])"):
        assert not re.search(pola, teks, re.I if pola != r"\bP[3-6]\b" else 0), pola


def test_catatan_di_escape_dan_baris_baru_terlihat():
    data = dict(DATA, catatan="<script>alert(1)</script>\nbaris dua", guru="<b>Guru</b>")
    h = halaman.render_laporan(**data).decode()
    assert "<script>" not in h and "&lt;script&gt;" in h and "&lt;b&gt;Guru&lt;/b&gt;" in h
    assert "pre-line" in h


def test_allowlist_payload_kunci_ekstra_diabaikan():
    """M2: kunci di luar allowlist tidak pernah tampil (bukan daftar larangan)."""
    kotor = dict(DATA, isi=dict(ISI, kunci="UJI_BOCOR_KUNCI", skor=97, sesi_ids=[1, 2], malrule_id="UJI_BOCOR_MAL",
                                tahap=dict(ISI["tahap"], kode_final="K")))
    assert halaman.render_laporan(**kotor) == halaman.render_laporan(**DATA)


def test_tanpa_tahap_dan_tanpa_topik_tetap_jujur():
    data = dict(DATA, isi={"versi": 1, "topik": [], "tahap": None, "langkah": "Guru akan menentukan langkah."})
    teks = _teks_tampil(halaman.render_laporan(**data).decode())
    assert "Belum ada latihan yang sudah diperiksa guru" in teks
    assert "Tahap belum bisa ditunjukkan" in teks


def test_renderer_hanya_mengimpor_stdlib_html_waktu_dan_token():
    pohon = ast.parse(MODUL.read_text(encoding="utf-8"))
    impor = set()
    for node in ast.walk(pohon):
        if isinstance(node, ast.Import):
            impor |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            impor.add((node.module or "").split(".")[0])
    assert impor <= {"__future__", "html", "datetime", "design_tokens"}, impor


def test_halaman_tidak_dapat_dibuka_tunggal_dan_netral():
    h = halaman.render_tidak_dapat_dibuka().decode()
    assert "Laporan tidak dapat dibuka" in h and "Minta tautan baru kepada guru" in h
    assert halaman.render_tidak_dapat_dibuka() == halaman.render_tidak_dapat_dibuka()
    assert "<a " not in h and "<script" not in h


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Tautan", pemilik="guru")
        laporan = toko.buat_draf(kon, anak, "2026-11-01", "2026-11-30", ISI)
        toko.simpan_catatan(kon, anak, laporan, "Catatan uji.")
        token = toko.terbitkan(kon, anak, laporan, "Guru Uji")
    yield s, anak, laporan, token
    s.berhenti()


def test_token_sah_dibuka_tanpa_login_dengan_header_privat(server):
    s, _, _, token = server
    kode, isi, h = s.minta(f"/laporan-ortu/{token}")
    assert kode == 200 and "Anak Tautan" in isi and "Pola Bilangan" in isi
    assert h["Cache-Control"] == "no-store" and h["Referrer-Policy"] == "no-referrer"
    assert "noindex" in h["X-Robots-Tag"] and h["X-Frame-Options"] == "DENY"
    assert h["X-Content-Type-Options"] == "nosniff"
    csp = h["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "form-action 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "script-src" not in csp.replace("default-src 'none'", "") or "script-src 'none'" in csp
    assert "Set-Cookie" not in h
    assert not re.search(r"<title>[^<]*Anak Tautan", isi)


def test_query_string_diabaikan_total(server):
    s, _, _, token = server
    dasar = s.minta(f"/laporan-ortu/{token}")[1]
    kode, isi, _ = s.minta(f"/laporan-ortu/{token}?nama=%3Cscript%3E&x=1")
    assert kode == 200 and isi == dasar and "<script" not in isi


def _tidak_sah(server):
    s, anak, laporan, token = server
    tokens = {"salah": "x" * 43, "pendek": "abc", "unicode": "%C3%A9" * 43, "kosong": "", "slash": "a/b" + "c" * 40}
    kode_isi = {nama: s.minta(f"/laporan-ortu/{t}") for nama, t in tokens.items()}
    with s.buka() as kon:
        toko.cabut_tautan(kon, anak)
    kode_isi["dicabut"] = s.minta(f"/laporan-ortu/{token}")
    with s.buka() as kon:
        draf = toko.buat_draf(kon, anak, "2026-11-01", "2026-11-30", ISI)
        kon.execute("DELETE FROM laporan_ortu WHERE id = ?", (draf,))
    return kode_isi


def test_semua_keadaan_tidak_sah_satu_404_identik_tanpa_cookie(server):
    hasil = _tidak_sah(server)
    badan = {isi for _, isi, _ in hasil.values()}
    assert len(badan) == 1, {n: (k, i[:60]) for n, (k, i, _) in hasil.items() if i != next(iter(badan))}
    for nama, (kode, isi, h) in hasil.items():
        assert kode == 404, nama
        assert "Set-Cookie" not in h and h["Cache-Control"] == "no-store", nama
    assert "Laporan tidak dapat dibuka" in badan.pop()


def test_kedaluwarsa_dan_draf_sama_dengan_tidak_ada(server):
    s, anak, laporan, token = server
    sah404 = s.minta("/laporan-ortu/" + "x" * 43)
    with s.buka() as kon:
        kon.execute("UPDATE tautan_laporan SET kedaluarsa = 1 WHERE siswa_id = ?", (anak,))
    assert s.minta(f"/laporan-ortu/{token}")[:2] == sah404[:2]
    with s.buka() as kon:
        kon.execute("UPDATE tautan_laporan SET kedaluarsa = 9999999999 WHERE siswa_id = ?", (anak,))
        kon.execute("UPDATE laporan_ortu SET diterbitkan = NULL WHERE id = ?", (laporan,))
    assert s.minta(f"/laporan-ortu/{token}")[:2] == sah404[:2]


def test_rute_ortu_tidak_menulis_apa_pun_dan_post_tidak_berefek(server):
    s, _, _, token = server
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    s.minta(f"/laporan-ortu/{token}")
    s.minta("/laporan-ortu/" + "x" * 43)
    kode, isi, _ = s.minta(f"/laporan-ortu/{token}", data={"catatan": "ubah"})
    assert kode == 404 and "Laporan tidak dapat dibuka" in isi
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_nama_anak_dan_id_tidak_ada_di_url(server):
    _, _, _, token = server
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)


def test_catatan_guru_tampil_paling_awal_sebelum_bagian_baku():
    """Nilai laporan ada di catatan guru: urutan catatan → langkah → tahap → topik."""
    teks = _teks_tampil(halaman.render_laporan(**DATA).decode())
    urutan = [teks.index(x) for x in ("Catatan guru", "Langkah berikutnya", "Tahap belajar sekarang", "Yang dilatih")]
    assert urutan == sorted(urutan)


def test_titik_tahap_dekoratif_enam_dan_jumlah_terisi_sama_dengan_nomor():
    h = halaman.render_laporan(**DATA).decode()
    titik = re.search(r'<p class="titik" aria-hidden="true">(.*?)</p>', h).group(1)
    assert titik.count("<span") == 6 and titik.count('class="isi"') == 3
    assert "Latihan (3 dari 6)" in _teks_tampil(h)


@pytest.mark.parametrize("nomor", [0, 7, "3", None, True, 2.5])
def test_titik_tahap_tak_sah_tidak_dirender_tetapi_teks_tetap(nomor):
    data = dict(DATA, isi=dict(ISI, tahap=dict(ISI["tahap"], nomor=nomor)))
    assert 'class="titik"' not in halaman.render_laporan(**data).decode()


def test_tanpa_tahap_tidak_ada_titik():
    data = dict(DATA, isi=dict(ISI, tahap=None))
    assert 'class="titik"' not in halaman.render_laporan(**data).decode()


def test_nama_guru_sekali_di_tanda_catatan_dan_di_baris_terbit_bila_tanpa_catatan():
    dengan = _teks_tampil(halaman.render_laporan(**DATA).decode())
    assert dengan.count("Bu Feby") == 1 and "Ditulis oleh Bu Feby" in dengan
    tanpa = _teks_tampil(halaman.render_laporan(**dict(DATA, catatan="  ")).decode())
    assert tanpa.count("Bu Feby") == 1 and "Diterbitkan 1 Desember 2026 oleh Bu Feby" in tanpa


def test_topik_chip_tetap_daftar_semantik_dan_ter_escape():
    data = dict(DATA, isi=dict(ISI, topik=["<b>x</b>", "Pecahan"]))
    h = halaman.render_laporan(**data).decode()
    assert '<ul class="chip"><li>&lt;b&gt;x&lt;/b&gt;</li><li>Pecahan</li></ul>' in h
