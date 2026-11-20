"""Ringkasan utama dan heatmap "Sesi dibuat per minggu" halaman admin Pemakaian guru.

Renderer HTML murni: tabel server-side, sel berwarna 4 tingkat lewat kelas CSS bertoken, angka tetap
tertulis di sel (warna bukan satu-satunya pembawa informasi), tanpa JS, tanpa nama anak. Semua angka
berasal dari `teacher_usage.PemakaianGuru` yang sudah ada; tidak ada metrik baru.
"""
from __future__ import annotations

from typing import Sequence, Tuple

from admin_komponen import e
from teacher_usage import JUMLAH_MINGGU, PemakaianGuru

SINYAL_BELUM_MULAI = "Belum mulai"
SINYAL_BARU_MULAI = "Baru mulai"
SINYAL_NAIK = "Naik"
SINYAL_STABIL = "Stabil"
SINYAL_TURUN = "Turun — hubungi"

MINGGU_BANDING = 2  # jumlah minggu di tiap sisi perbandingan: 2 terakhir vs 2 sebelumnya
SELISIH_MINIMAL = 2  # selisih sesi minimal agar dianggap berubah (mencegah 1 sesi = "Turun")
PEMBAGI_RELATIF = 2  # selisih >= pembanding / 2, yaitu >= 50% dari 2 minggu sebelumnya
BATAS_TINGKAT = (0, 2, 5)  # tingkat 0 = 0 sesi, 1 = 1-2, 2 = 3-5, 3 = 6 ke atas

_KELAS_SINYAL = {SINYAL_NAIK: " bien", SINYAL_TURUN: " perhatian"}
_CATATAN_SINYAL = (
    "Kolom = hari Senin awal minggu (WIB); kolom terakhir adalah minggu berjalan yang belum penuh. "
    "Sinyal membandingkan 2 minggu terakhir dengan 2 minggu sebelumnya: Naik atau Turun bila "
    "selisihnya sedikitnya %d sesi dan sedikitnya 50%% dari 2 minggu sebelumnya, selain itu Stabil. "
    "Baru mulai = sesi pertama dalam %d minggu jatuh di 2 minggu terakhir. "
    "Belum mulai = tidak ada sesi dalam %d minggu."
) % (SELISIH_MINIMAL, JUMLAH_MINGGU, JUMLAH_MINGGU)


def tingkat(jumlah: int) -> int:
    """Tingkat warna 0..3 untuk jumlah sesi satu minggu: 0 / 1-2 / 3-5 / 6+."""
    return sum(1 for batas in BATAS_TINGKAT if jumlah > batas)


def sinyal(minggu: Sequence[int]) -> str:
    """Sinyal pemakaian dari sesi dibuat per minggu (lama ke baru, biasanya 8 minggu).

    Urutan aturan (yang pertama cocok menang):
    1. Belum mulai: total semua minggu = 0.
    2. Baru mulai: semua sesi jatuh di 2 minggu terakhir (minggu sebelumnya kosong).
    3. Bandingkan ``akhir`` (jumlah 2 minggu terakhir) dengan ``awal`` (2 minggu sebelumnya),
       ``selisih = akhir - awal``. Berubah hanya bila ``|selisih| >= 2`` dan
       ``|selisih| >= 50% x awal`` (dihitung bilangan bulat: ``2 x |selisih| >= awal``).
       Naik bila selisih positif, Turun bila negatif; awal = 0 otomatis lolos syarat relatif.
    4. Selain itu Stabil.
    """
    jumlah = list(minggu)
    if not any(jumlah):
        return SINYAL_BELUM_MULAI
    if not any(jumlah[:-MINGGU_BANDING]):
        return SINYAL_BARU_MULAI
    akhir = sum(jumlah[-MINGGU_BANDING:])
    awal = sum(jumlah[-2 * MINGGU_BANDING:-MINGGU_BANDING])
    selisih = akhir - awal
    berubah = abs(selisih) >= SELISIH_MINIMAL and PEMBAGI_RELATIF * abs(selisih) >= awal
    if not berubah:
        return SINYAL_STABIL
    return SINYAL_NAIK if selisih > 0 else SINYAL_TURUN


def _jumlah_per_minggu(guru: PemakaianGuru) -> Tuple[int, ...]:
    return tuple(m.sesi_dibuat for m in guru.minggu)


def _persen(bagian: int, total: int) -> str:
    return "—" if total == 0 else "%d%%" % round(100 * bagian / total)


def _kartu_angka(label: str, nilai: str, keterangan: str) -> str:
    return ('<div class="admin-ringkas-kartu"><span>%s</span><strong>%s</strong><span>%s</span></div>'
            % (e(label), e(nilai), e(keterangan)))


def ringkasan_utama(daftar: Sequence[PemakaianGuru]) -> str:
    """Empat angka utama: guru aktif minggu ini, sesi dibuat, persen selesai, persen dikonfirmasi."""
    aktif = sum(1 for g in daftar if g.minggu and g.minggu[-1].sesi_dibuat)
    dibuat = sum(g.sesi_dibuat for g in daftar)
    selesai = sum(g.sesi_selesai for g in daftar)
    konfirmasi = sum(g.sesi_dikonfirmasi for g in daftar)
    return '<div class="admin-ringkas">%s</div>' % "".join((
        _kartu_angka("Guru aktif minggu ini", "%d dari %d" % (aktif, len(daftar)),
                     "guru membuat sesi di minggu berjalan"),
        _kartu_angka("Sesi dibuat · %d minggu" % JUMLAH_MINGGU, str(dibuat), "semua guru, tanpa sesi batal"),
        _kartu_angka("Sesi selesai", _persen(selesai, dibuat), "%d dari %d sesi dibuat" % (selesai, dibuat)),
        _kartu_angka("Sesi dikonfirmasi guru", _persen(konfirmasi, dibuat),
                     "%d dari %d sesi dibuat" % (konfirmasi, dibuat)),
    ))


def _sel(jumlah: int) -> str:
    return '<td class="admin-heat admin-heat-%d">%d</td>' % (tingkat(jumlah), jumlah)


def _baris(guru: PemakaianGuru) -> str:
    jumlah = _jumlah_per_minggu(guru)
    kode = sinyal(jumlah)
    return (
        '<tr><th scope="row">%s</th>%s<td class="admin-heat-total">%d</td>'
        '<td><span class="admin-badge%s">%s</span></td></tr>'
    ) % (e(guru.pengguna), "".join(_sel(n) for n in jumlah), sum(jumlah), _KELAS_SINYAL.get(kode, ""), e(kode))


def _kepala(daftar: Sequence[PemakaianGuru]) -> str:
    minggu = daftar[0].minggu
    kolom = "".join(
        '<th scope="col" class="admin-heat-kepala">%s%s</th>' % (
            e(m.senin.strftime("%d/%m")), " · ini" if i == len(minggu) - 1 else "")
        for i, m in enumerate(minggu)
    )
    return '<tr><th scope="col">Guru</th>%s<th scope="col">Total</th><th scope="col">Sinyal</th></tr>' % kolom


def _legenda() -> str:
    item = "".join(
        '<li><span class="admin-heat admin-heat-%d">%s</span></li>' % (i, e(teks))
        for i, teks in enumerate(("0", "1–2", "3–5", "6+"))
    )
    return '<ul class="admin-heat-legenda" aria-label="Legenda warna: sesi dibuat per minggu">%s</ul>' % item


def heatmap(daftar: Sequence[PemakaianGuru]) -> str:
    """Kartu heatmap sesi dibuat per minggu per guru; string kosong bila tidak ada guru."""
    if not daftar:
        return ""
    return (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>Sesi dibuat per minggu</h2>%s</div>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Sesi dibuat per minggu">'
        '<table class="admin-tabel admin-heat-tabel"><thead>%s</thead><tbody>%s</tbody></table></div>'
        '<p class="admin-kartu-catatan admin-meta">%s</p></section>'
    ) % (_legenda(), _kepala(daftar), "".join(_baris(g) for g in daftar), e(_CATATAN_SINYAL))
