"""Tahap 4 G3: rute dan halaman guru untuk laporan orang tua (kepemilikan, alur, tanpa efek samping)."""
import base64
import http.client
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import parent_report_store as toko  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

GURU = ("guru", SANDI_GURU)
TABEL_BUKTI = ("konfirmasi_hasil", "snapshot_outcome", "kejadian_belajar", "bukti_fokus")


@pytest.fixture()
def s(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("guru-lain", "sandi-guru-lain-123", "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("admin-uji", "sandi-admin-uji-123", "admin", path=auth.BERKAS_SANDI)
    with server.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Milik Guru", pemilik="guru")
        asing = database.tambah_siswa(kon, "Anak Guru Lain", pemilik="guru-lain")
    server.anak, server.asing = anak, asing
    yield server
    server.berhenti()


def raw(s, jalur, data=None, auth=GURU):
    """Satu permintaan tanpa mengikuti redirect: (status, header, isi)."""
    kepala = {"Authorization": "Basic " + base64.b64encode(":".join(auth).encode()).decode()}
    tubuh = None
    if data is not None:
        tubuh = urllib.parse.urlencode(data)
        kepala["Content-Type"] = "application/x-www-form-urlencoded"
    host = s.alamat.split("//")[1]
    k = http.client.HTTPConnection(host, timeout=10)
    k.request("POST" if data is not None else "GET", jalur, body=tubuh, headers=kepala)
    r = k.getresponse()
    isi = r.read().decode()
    h = dict(r.getheaders())
    k.close()
    return r.status, h, isi


def _dump(s):
    with s.buka() as kon:
        return tuple(kon.iterdump())


def _bukti(s):
    with s.buka() as kon:
        return {t: [tuple(r) for r in kon.execute("SELECT * FROM " + t)] for t in TABEL_BUKTI}


def _buat(s, anak=None, **form):
    data = {"periode": "30hari"}
    data.update(form)
    kode, h, isi = raw(s, f"/anak/{anak or s.anak}/laporan-ortu", data)
    return kode, isi, h


def _id_dari(h):
    return int(re.search(r"/laporan-ortu/(\d+)$", h["Location"]).group(1))


def test_satu_entry_point_di_tab_perkembangan(s):
    kode, isi, _ = s.minta(f"/anak/{s.anak}?section=perkembangan", auth=GURU)
    assert kode == 200
    assert isi.count(f'href="/anak/{s.anak}/laporan-ortu"') == 1
    assert "Laporan untuk orang tua" in isi
    for section in ("rencana", "latihan", "riwayat"):
        _, lain, _ = s.minta(f"/anak/{s.anak}?section={section}", auth=GURU)
        assert "/laporan-ortu" not in lain, section


def test_halaman_daftar_privat_dan_ada_form_periode(s):
    kode, isi, h = s.minta(f"/anak/{s.anak}/laporan-ortu", auth=GURU)
    assert kode == 200 and h["Cache-Control"] == "no-store"
    assert f'action="/anak/{s.anak}/laporan-ortu"' in isi and 'name="periode"' in isi
    assert 'type="date"' in isi and "<script" not in isi


def test_buat_draf_lalu_pratinjau_tanpa_pesan_di_url(s):
    kode, _, h = _buat(s)
    assert kode == 303 and "pesan=" not in h["Location"] and "token" not in h["Location"].lower()
    lid = _id_dari(h)
    kode, isi, _ = s.minta(h["Location"], auth=GURU)
    assert kode == 200 and "Anak Milik Guru" in isi and "Yang dilatih" in isi and 'maxlength="2000"' in isi
    assert f"/anak/{s.anak}/laporan-ortu/{lid}/terbitkan" in isi
    with s.buka() as kon:
        assert toko.ambil(kon, s.anak, lid)["diterbitkan"] is None


def test_alur_penuh_terbit_ganti_cabut(s):
    bukti = _bukti(s)
    _, _, h = _buat(s)
    lid = _id_dari(h)
    dasar = f"/anak/{s.anak}/laporan-ortu/{lid}"
    kode, _, _ = raw(s, dasar + "/catatan", {"catatan": "Sudah lebih tenang."})
    assert kode == 303
    kode, isi, hd = s.minta(dasar + "/terbitkan", auth=GURU, data={})
    assert kode == 200 and hd["Cache-Control"] == "no-store"
    tautan = re.search(r'value="(https://[^"]+/laporan-ortu/([A-Za-z0-9_-]{43}))"', isi)
    assert tautan, isi[:300]
    token = tautan.group(2)
    kode, ortu, _ = s.minta(f"/laporan-ortu/{token}")
    assert kode == 200 and "Sudah lebih tenang." in ortu and "Anak Milik Guru" in ortu
    # Token hanya tampil sekali: GET detail berikutnya tidak memuatnya.
    _, detail, _ = s.minta(dasar, auth=GURU)
    assert token not in detail and "Tautan aktif sampai" in detail
    # Ganti: token lama mati.
    kode, isi2, _ = s.minta(dasar + "/tautan", auth=GURU, data={})
    token2 = re.search(r"/laporan-ortu/([A-Za-z0-9_-]{43})", isi2).group(1)
    assert token2 != token and s.minta(f"/laporan-ortu/{token}")[0] == 404
    assert s.minta(f"/laporan-ortu/{token2}")[0] == 200
    # Cabut.
    kode, _, _ = raw(s, dasar + "/tautan/cabut", {})
    assert kode == 303 and s.minta(f"/laporan-ortu/{token2}")[0] == 404
    _, detail, _ = s.minta(dasar, auth=GURU)
    assert "Tautan tidak aktif" in detail
    assert _bukti(s) == bukti


def test_terbit_tidak_bisa_diulang_dan_tidak_bisa_dihapus(s):
    _, _, h = _buat(s)
    dasar = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h)}"
    assert s.minta(dasar + "/terbitkan", auth=GURU, data={})[0] == 200
    sebelum = _dump(s)
    assert s.minta(dasar + "/terbitkan", auth=GURU, data={})[0] in (400, 409)
    assert s.minta(dasar + "/hapus", auth=GURU, data={})[0] in (400, 409)
    assert s.minta(dasar + "/catatan", auth=GURU, data={"catatan": "ubah"})[0] in (400, 409)
    assert _dump(s) == sebelum


def test_hapus_draf(s):
    _, _, h = _buat(s)
    lid = _id_dari(h)
    kode, _, _ = raw(s, f"/anak/{s.anak}/laporan-ortu/{lid}/hapus", {})
    assert kode == 303
    with s.buka() as kon:
        assert toko.ambil(kon, s.anak, lid) is None


@pytest.mark.parametrize("form", [
    {"periode": "rentang", "dari": "2026-12-01", "sampai": "2026-11-01"},
    {"periode": "rentang", "dari": "bukan-tanggal", "sampai": "2026-11-01"},
    {"periode": "rentang", "dari": "2020-01-01", "sampai": "2026-11-01"},
    {"periode": "aneh"},
    {},
])
def test_periode_tidak_sah_ditolak_tanpa_menulis(s, form):
    sebelum = _dump(s)
    kode, isi, _ = s.minta(f"/anak/{s.anak}/laporan-ortu", auth=GURU, data=form)
    assert kode == 400 and _dump(s) == sebelum


def test_catatan_terlalu_panjang_ditolak_dan_html_di_escape(s):
    _, _, h = _buat(s)
    dasar = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h)}"
    sebelum = _dump(s)
    assert s.minta(dasar + "/catatan", auth=GURU, data={"catatan": "x" * 2001})[0] == 400
    assert _dump(s) == sebelum
    s.minta(dasar + "/catatan", auth=GURU, data={"catatan": "<script>alert(1)</script>"})
    _, isi, _ = s.minta(dasar, auth=GURU)
    assert "<script>alert(1)</script>" not in isi and "&lt;script&gt;" in isi


def test_guru_asing_404_identik_dengan_tidak_ada_dan_tanpa_efek(s):
    with s.buka() as kon:
        punya_asing = toko.buat_draf(kon, s.asing, "2026-11-01", "2026-11-30", {"versi": 1, "topik": [], "tahap": None, "langkah": "x"})
    sebelum = _dump(s)
    tidak_ada = s.minta("/anak/99999/laporan-ortu", auth=GURU)
    for jalur in (f"/anak/{s.asing}/laporan-ortu", f"/anak/{s.asing}/laporan-ortu/{punya_asing}"):
        kode, isi, _ = s.minta(jalur, auth=GURU)
        assert (kode, isi) == tidak_ada[:2], jalur
    for aksi in ("catatan", "terbitkan", "tautan", "tautan/cabut", "hapus"):
        kode, isi, _ = s.minta(f"/anak/{s.asing}/laporan-ortu/{punya_asing}/{aksi}", auth=GURU, data={"catatan": "x"})
        assert kode == 404 and isi == tidak_ada[1], aksi
    assert s.minta(f"/anak/{s.asing}/laporan-ortu", auth=GURU, data={"periode": "30hari"})[0] == 404
    assert _dump(s) == sebelum


def test_laporan_anak_lain_lewat_id_anak_sendiri_404(s):
    with s.buka() as kon:
        punya_asing = toko.buat_draf(kon, s.asing, "2026-11-01", "2026-11-30", {"versi": 1, "topik": [], "tahap": None, "langkah": "x"})
    sebelum = _dump(s)
    assert s.minta(f"/anak/{s.anak}/laporan-ortu/{punya_asing}", auth=GURU)[0] == 404
    assert s.minta(f"/anak/{s.anak}/laporan-ortu/{punya_asing}/terbitkan", auth=GURU, data={})[0] == 404
    assert _dump(s) == sebelum


def test_tanpa_login_ditolak_dan_tidak_menulis(s):
    sebelum = _dump(s)
    assert s.minta(f"/anak/{s.anak}/laporan-ortu")[0] == 401
    assert s.minta(f"/anak/{s.anak}/laporan-ortu", data={"periode": "30hari"})[0] == 401
    assert _dump(s) == sebelum


def test_post_lintas_situs_ditolak(s):
    sebelum = _dump(s)
    kode, _, _ = s.minta(f"/anak/{s.anak}/laporan-ortu", auth=GURU, data={"periode": "30hari"},
                         headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://jahat.example"})
    assert kode in (400, 403) and _dump(s) == sebelum


def test_admin_hanya_melihat(s):
    admin = ("admin-uji", "sandi-admin-uji-123")
    _, _, h = _buat(s)
    dasar = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h)}"
    kode, isi, _ = s.minta(dasar, auth=admin)
    assert kode == 200 and f"{dasar}/terbitkan" not in isi and "<form" not in isi.split("Pratinjau")[-1]
    sebelum = _dump(s)
    for aksi in ("terbitkan", "catatan", "tautan", "hapus"):
        assert s.minta(f"{dasar}/{aksi}", auth=admin, data={"catatan": "x"})[0] in (403, 404), aksi
    assert s.minta(f"/anak/{s.anak}/laporan-ortu", auth=admin, data={"periode": "30hari"})[0] in (403, 404)
    assert _dump(s) == sebelum


def test_penanda_bukti_berubah_setelah_terbit(s):
    _, _, h = _buat(s)
    dasar = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h)}"
    s.minta(dasar + "/terbitkan", auth=GURU, data={})
    with s.buka() as kon:
        kon.execute("INSERT INTO kejadian_belajar (siswa_id, jenis) VALUES (?, 'uji')", (s.anak,))
    _, isi, _ = s.minta(dasar, auth=GURU)
    assert "Bukti berubah setelah laporan ini diterbitkan" in isi and "Buat laporan baru" in isi


def test_terbit_baru_mematikan_tautan_laporan_lama(s):
    _, _, h1 = _buat(s)
    d1 = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h1)}"
    _, isi1, _ = s.minta(d1 + "/terbitkan", auth=GURU, data={})
    t1 = re.search(r"/laporan-ortu/([A-Za-z0-9_-]{43})", isi1).group(1)
    _, _, h2 = _buat(s)
    d2 = f"/anak/{s.anak}/laporan-ortu/{_id_dari(h2)}"
    _, isi2, _ = s.minta(d2 + "/terbitkan", auth=GURU, data={})
    t2 = re.search(r"/laporan-ortu/([A-Za-z0-9_-]{43})", isi2).group(1)
    assert s.minta(f"/laporan-ortu/{t1}")[0] == 404 and s.minta(f"/laporan-ortu/{t2}")[0] == 200


# --- Kalimat pembuka catatan (keputusan pemilik 6 Nov, K1): templat netral berpenanda
# [isi] yang wajib dilengkapi guru; tidak pernah terbit diam-diam.

import html as _html  # noqa: E402

import parent_report_guru_pages as guru_pages  # noqa: E402


def test_draf_kosong_menampilkan_kalimat_pembuka_berpenanda(s):
    _, _, h = _buat(s)
    _, isi, _ = s.minta(h["Location"], auth=GURU)
    textarea = re.search(r'<textarea id="catatan"[^>]*>(.*?)</textarea>', isi, re.S).group(1)
    assert _html.unescape(textarea) == guru_pages.KALIMAT_PEMBUKA
    assert guru_pages.PENANDA_ISI in guru_pages.KALIMAT_PEMBUKA


def test_simpan_catatan_yang_masih_memuat_penanda_ditolak_tanpa_tulis(s):
    _, _, h = _buat(s)
    lid = _id_dari(h)
    sebelum = _dump(s)
    kode, _, isi = raw(s, f"/anak/{s.anak}/laporan-ortu/{lid}/catatan",
                       {"catatan": "Minggu ini kami berlatih pola bilangan. Di rumah, [isi]."})
    assert kode == 400
    assert "[isi]" in _html.unescape(isi) and "Lengkapi" in isi
    # Ketikan guru tetap tampil untuk dilengkapi, bukan diganti templat lagi.
    assert "berlatih pola bilangan. Di rumah, [isi]." in _html.unescape(isi)
    assert _dump(s) == sebelum


def test_terbit_tanpa_simpan_catatan_tidak_memuat_templat(s):
    _, _, h = _buat(s)
    lid = _id_dari(h)
    _, detail, _ = s.minta(h["Location"], auth=GURU)
    form_terbit = detail.split(f'action="/anak/{s.anak}/laporan-ortu/{lid}/terbitkan"', 1)[1].split("</form>", 1)[0]
    assert "Catatan yang belum disimpan tidak ikut terbit" in form_terbit
    kode, isi, _ = s.minta(f"/anak/{s.anak}/laporan-ortu/{lid}/terbitkan", auth=GURU, data={})
    token = re.search(r"/laporan-ortu/([A-Za-z0-9_-]{43})", isi).group(1)
    _, ortu, _ = s.minta(f"/laporan-ortu/{token}")
    with s.buka() as kon:
        assert toko.ambil(kon, s.anak, lid)["catatan"] == ""
    assert "[isi]" not in ortu and "kami berlatih" not in ortu


def test_catatan_tersimpan_tidak_ditimpa_kalimat_pembuka(s):
    _, _, h = _buat(s)
    lid = _id_dari(h)
    raw(s, f"/anak/{s.anak}/laporan-ortu/{lid}/catatan", {"catatan": "Sudah lebih teliti."})
    _, isi, _ = s.minta(h["Location"], auth=GURU)
    assert "Sudah lebih teliti." in isi and "[isi]" not in _html.unescape(isi.split("<textarea", 1)[1].split("</textarea>", 1)[0])
