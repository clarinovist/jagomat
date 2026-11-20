"""Heatmap pemakaian guru (D6): aturan sinyal, tingkat warna, renderer, agregasi mingguan, dan halaman.

Data sintetis. Batas minggu mengikuti Senin 00:00 WIB. Tidak ada nama anak di halaman.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import admin_usage_heatmap as H  # noqa: E402
import database  # noqa: E402
import teacher_usage as P  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)

NAMA_ANAK = "Zorblat Sintetis Heat"
SENIN_AWAL = date(2026, 9, 14)


# --- aturan sinyal (fungsi murni) ----------------------------------------------------------

def _riwayat(awal: int, akhir: int):
    """8 minggu dengan aktivitas awal (bukan Baru mulai); 2 minggu sebelum = awal, 2 terakhir = akhir."""
    return (1, 0, 0, 0, awal // 2, awal - awal // 2, akhir // 2, akhir - akhir // 2)


@pytest.mark.parametrize("awal,akhir,harap", [
    (4, 2, H.SINYAL_TURUN),    # selisih -2 dan 50% persis
    (4, 3, H.SINYAL_STABIL),   # selisih -1 (< 2 sesi)
    (6, 4, H.SINYAL_STABIL),   # selisih -2 tetapi hanya 33% (< 50%)
    (3, 1, H.SINYAL_TURUN),    # selisih -2, 67%
    (1, 0, H.SINYAL_STABIL),   # selisih -1 (< 2 sesi) walau turun 100%
    (10, 5, H.SINYAL_TURUN),
    (0, 2, H.SINYAL_NAIK),     # dari kosong, selisih +2
    (0, 1, H.SINYAL_STABIL),   # dari kosong, selisih hanya +1
    (2, 4, H.SINYAL_NAIK),     # +2, 100%
    (4, 6, H.SINYAL_NAIK),     # +2, 50% persis
    (6, 8, H.SINYAL_STABIL),   # +2 tetapi 33%
    (5, 5, H.SINYAL_STABIL),
    (0, 0, H.SINYAL_STABIL),   # pernah aktif lalu diam >= 4 minggu: aturan 2-vs-2 membacanya Stabil
])
def test_sinyal_batas_selisih_dan_relatif(awal, akhir, harap):
    assert H.sinyal(_riwayat(awal, akhir)) == harap


def test_belum_mulai_hanya_bila_delapan_minggu_kosong():
    assert H.sinyal((0,) * 8) == H.SINYAL_BELUM_MULAI
    assert H.sinyal((0,) * 7 + (1,)) != H.SINYAL_BELUM_MULAI


@pytest.mark.parametrize("minggu", [
    (0, 0, 0, 0, 0, 0, 1, 0), (0, 0, 0, 0, 0, 0, 0, 3), (0, 0, 0, 0, 0, 0, 5, 5),
])
def test_baru_mulai_bila_semua_sesi_ada_di_dua_minggu_terakhir(minggu):
    assert H.sinyal(minggu) == H.SINYAL_BARU_MULAI


def test_sesi_pertama_di_minggu_ke_enam_bukan_baru_mulai():
    assert H.sinyal((0, 0, 0, 0, 0, 1, 0, 0)) == H.SINYAL_STABIL


def test_baru_mulai_menang_atas_naik_dan_belum_mulai_menang_atas_semuanya():
    assert H.sinyal((0, 0, 0, 0, 0, 0, 4, 4)) == H.SINYAL_BARU_MULAI  # akan Naik bila tidak diprioritaskan


def test_sinyal_tidak_mengubah_masukan():
    minggu = [0, 1, 2, 3, 4, 5, 6, 7]
    H.sinyal(minggu)
    assert minggu == [0, 1, 2, 3, 4, 5, 6, 7]


@pytest.mark.parametrize("jumlah,harap", [(0, 0), (1, 1), (2, 1), (3, 2), (5, 2), (6, 3), (100, 3)])
def test_tingkat_warna_batas(jumlah, harap):
    assert H.tingkat(jumlah) == harap


# --- renderer ------------------------------------------------------------------------------

def _guru(nama, per_minggu):
    minggu = tuple(P.MingguGuru(SENIN_AWAL + timedelta(weeks=i), n, 0, 0) for i, n in enumerate(per_minggu))
    return P.PemakaianGuru(
        pengguna=nama, minggu=minggu, sesi_dibuat=sum(per_minggu), sesi_selesai=0, sesi_dikonfirmasi=0,
        minggu_aktif=sum(1 for n in per_minggu if n), median_kerja_menit=None,
        median_jeda_konfirmasi_menit=None, median_tinjau_menit=None, sumber=(), laporan_terbit=0)


def _baris(isi, nama):
    cocok = re.search(r'<tr><th scope="row">%s</th>(.*?)</tr>' % re.escape(nama), isi, re.S)
    assert cocok, nama
    return cocok.group(1)


def test_sel_berkelas_per_tingkat_dengan_angka_tertulis():
    isi = H.heatmap([_guru("Guru-A", (0, 1, 2, 3, 5, 6, 9, 0))])
    sel = re.findall(r'<td class="admin-heat admin-heat-(\d)">(\d+)</td>', _baris(isi, "Guru-A"))
    assert sel == [("0", "0"), ("1", "1"), ("1", "2"), ("2", "3"), ("2", "5"), ("3", "6"), ("3", "9"), ("0", "0")]


def test_kolom_total_dan_sinyal_per_guru():
    isi = H.heatmap([_guru("Guru-A", (0, 0, 0, 0, 1, 1, 3, 3)), _guru("Guru-B", (0,) * 8)])
    a, b = _baris(isi, "Guru-A"), _baris(isi, "Guru-B")
    assert '<td class="admin-heat-total">8</td>' in a and ">Naik<" in a and "admin-badge bien" in a
    assert '<td class="admin-heat-total">0</td>' in b and ">Belum mulai<" in b


def test_sinyal_turun_memakai_kelas_perhatian_dan_teks_hubungi():
    isi = H.heatmap([_guru("Guru-A", (0, 0, 0, 0, 3, 3, 1, 0))])
    assert "admin-badge perhatian" in isi and "Turun — hubungi" in isi


def test_legenda_menyebut_empat_tingkat_dan_kepala_minggu_berjalan():
    isi = H.heatmap([_guru("Guru-A", (0,) * 8)])
    legenda = isi.split('class="admin-heat-legenda"', 1)[1].split("</ul>", 1)[0]
    assert re.findall(r'admin-heat-(\d)">([^<]+)<', legenda) == [("0", "0"), ("1", "1–2"), ("2", "3–5"), ("3", "6+")]
    assert "14/09" in isi and "02/11 · ini" in isi and isi.count(" · ini") == 1
    assert 'scope="col">Total<' in isi and 'scope="col">Sinyal<' in isi
    assert "2 minggu terakhir dengan 2 minggu sebelumnya" in isi


def test_nama_guru_di_escape():
    isi = H.heatmap([_guru('<img src=x onerror=1>&"\'', (0,) * 8)])
    assert "<img" not in isi and "&lt;img src=x onerror=1&gt;&amp;" in isi


def test_tanpa_guru_tidak_merender_kartu_dan_tanpa_skrip():
    assert H.heatmap([]) == ""
    assert "<script" not in H.heatmap([_guru("G", (1,) * 8)]).lower() + H.ringkasan_utama([_guru("G", (1,) * 8)])


def test_ringkasan_utama_empat_angka_dari_metrik_yang_ada():
    a = _guru("A", (0, 0, 0, 0, 0, 0, 2, 2))
    b = _guru("B", (1, 0, 0, 0, 0, 0, 0, 0))
    c = _guru("C", (0,) * 8)
    a = P.PemakaianGuru(**{**a.__dict__, "sesi_selesai": 3, "sesi_dikonfirmasi": 2})
    isi = H.ringkasan_utama([a, b, c])
    teks = re.sub(r"<[^>]+>", "|", isi)
    assert isi.count('class="admin-ringkas-kartu"') == 4
    assert "Guru aktif minggu ini|1 dari 3|" in teks.replace("||", "|")
    assert "Sesi dibuat · 8 minggu|5|" in teks.replace("||", "|")
    assert "Sesi selesai|60%|3 dari 5 sesi dibuat" in teks.replace("||", "|")
    assert "Sesi dikonfirmasi guru|40%|2 dari 5 sesi dibuat" in teks.replace("||", "|")


def test_ringkasan_tanpa_sesi_tidak_membagi_nol():
    isi = H.ringkasan_utama([])
    assert "0 dari 0" in isi and isi.count("<strong>—</strong>") == 2


# --- agregasi mingguan (batas Senin WIB) dan halaman --------------------------------------

def _sesi(kon, siswa_id, dibuat):
    kon.execute("INSERT INTO sesi (siswa_id, seed, dibuat) VALUES (?,?,?)", (siswa_id, 1, dibuat))


@pytest.fixture()
def guru(server):
    for nama in ("Guru-Batas", "Guru-Naik", "Guru-Turun", "Guru-Stabil", "Guru-Baru", "Guru-Nol"):
        auth.tambah_akun(nama, SANDI_ORANG_TUA + nama, "guru")
    server.token = _login(server, "Admin-C", SANDI_ADMIN)
    return server


def _siswa(kon, pemilik):
    return database.tambah_siswa(kon, NAMA_ANAK, "P3", pemilik=pemilik)


def test_batas_minggu_senin_nol_nol_wib(guru):
    sekarang = datetime(2026, 11, 6, 12, 0, 0)  # Jumat; minggu berjalan = Senin 2 Nov
    with guru.buka() as kon:
        s = _siswa(kon, "Guru-Batas")
        _sesi(kon, s, "2026-11-01 23:59:59")            # Minggu malam -> minggu 26 Okt
        _sesi(kon, s, "2026-11-02 00:00:00")            # Senin tepat -> minggu 2 Nov
        _sesi(kon, s, "2026-11-01T17:00:00+00:00")      # = Senin 00:00 WIB -> minggu 2 Nov
        _sesi(kon, s, "2026-11-01T16:59:59+00:00")      # = Minggu 23:59:59 WIB -> minggu 26 Okt
        hasil = {g.pengguna: g for g in P.ambil_pemakaian(kon, sekarang=sekarang)}
    per_minggu = {m.senin.isoformat(): m.sesi_dibuat for m in hasil["Guru-Batas"].minggu}
    assert per_minggu["2026-10-26"] == 2 and per_minggu["2026-11-02"] == 2
    assert tuple(m.sesi_dibuat for m in hasil["Guru-Batas"].minggu)[-2:] == (2, 2)
    assert H.sinyal(tuple(m.sesi_dibuat for m in hasil["Guru-Batas"].minggu)) == H.SINYAL_BARU_MULAI


def test_guru_terdaftar_tanpa_sesi_muncul_dengan_nilai_nol_tanpa_duplikat(guru):
    with guru.buka() as kon:
        _sesi(kon, _siswa(kon, "Guru-Batas"), "2026-11-03 09:00:00")
        hasil = P.ambil_pemakaian(kon, sekarang=datetime(2026, 11, 6, 12, 0, 0),
                                  guru_terdaftar=("Guru-Nol", "Guru-Batas", "Guru-Nol"))
    nama = [g.pengguna for g in hasil]
    assert nama.count("Guru-Nol") == 1 and nama.count("Guru-Batas") == 1
    nol = next(g for g in hasil if g.pengguna == "Guru-Nol")
    assert nol.sesi_dibuat == 0 and len(nol.minggu) == 8
    assert H.sinyal(tuple(m.sesi_dibuat for m in nol.minggu)) == H.SINYAL_BELUM_MULAI


def _isi_minggu(kon, pemilik, per_minggu):
    """Sesi per minggu (lama ke baru) relatif terhadap minggu berjalan WIB saat ini."""
    sekarang = datetime.now(P.ZONA_WIB).replace(tzinfo=None)
    senin = datetime.combine(sekarang.date() - timedelta(days=sekarang.weekday()), datetime.min.time())
    s = _siswa(kon, pemilik)
    for indeks, jumlah in enumerate(per_minggu):
        awal = senin - timedelta(weeks=len(per_minggu) - 1 - indeks)
        for n in range(jumlah):
            _sesi(kon, s, (awal + timedelta(hours=1 + n)).strftime("%Y-%m-%d %H:%M:%S"))


def test_halaman_pemakaian_heatmap_sinyal_rincian_dan_tanpa_nama_anak(guru):
    with guru.buka() as kon:
        _isi_minggu(kon, "Guru-Naik", (0, 0, 0, 0, 1, 1, 3, 3))
        _isi_minggu(kon, "Guru-Turun", (0, 0, 0, 0, 3, 3, 1, 0))
        _isi_minggu(kon, "Guru-Stabil", (0, 0, 0, 0, 2, 2, 2, 2))
        _isi_minggu(kon, "Guru-Baru", (0, 0, 0, 0, 0, 0, 2, 2))
    kode, isi, tajuk = _minta(guru, "/admin/pemakaian", cookie=guru.token)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    assert "<script" not in isi and NAMA_ANAK not in isi
    heat = isi.split('class="admin-tabel admin-heat-tabel"', 1)[1].split("</table>", 1)[0]
    for nama, sinyal in (("Guru-Naik", "Naik"), ("Guru-Turun", "Turun — hubungi"), ("Guru-Stabil", "Stabil"),
                         ("Guru-Baru", "Baru mulai"), ("Guru-Nol", "Belum mulai")):
        assert ">%s<" % sinyal in _baris(heat, nama), nama
    assert 'admin-heat-2">3<' in _baris(heat, "Guru-Naik")
    # Empat angka utama di atas heatmap, rincian lama tertutup di <details>.
    assert isi.index("Guru aktif minggu ini") < isi.index("Sesi dibuat per minggu")
    detail = isi.split('<details class="admin-kartu admin-pakai-rincian">', 1)[1]
    assert detail.startswith("<summary>Rincian per guru</summary>") and "Minggu aktif" in detail
    assert "Waktu persiapan belum bisa diukur." in detail
    assert "Minggu aktif" not in isi.split("<details", 1)[0]
    assert 'aria-current="page" href="/admin/pemakaian"' in isi or 'href="/admin/pemakaian" aria-current="page"' in isi
    assert 'href="/admin/profil-guru"' in isi  # tab Profil dari Fase B tetap


def test_halaman_tanpa_data_tetap_200(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, _ = _minta(server, "/admin/pemakaian", cookie=token)
    assert kode == 200 and "Rincian per guru" in isi
