"""Renderer HTML murni halaman admin "Pemakaian guru" (tanpa JS, tanpa nama anak)."""
from __future__ import annotations

from typing import Optional, Sequence

from admin_komponen import e
from teacher_usage import BATAS_WAJAR_MENIT, JUMLAH_MINGGU, PemakaianGuru

LABEL_SUMBER = {
    "tautan": "HP anak (tautan/QR)",
    "foto": "Foto kertas",
    "akun": "Akun murid",
    "tanpa": "Belum dikirim",
}
CATATAN_KAKI = (
    "Semua hitungan memakai sesi yang dibuat dalam %d minggu ISO terakhir (zona WIB) "
    "dan tidak menghitung sesi yang dibatalkan. Kolom selesai dan konfirmasi menghitung "
    "sesi dari minggu pembuatannya. Durasi negatif diabaikan; lama mengerjakan dan "
    "waktu tinjau di atas %d menit (24 jam) juga diabaikan karena tidak masuk akal. "
    "Waktu tinjau hanyalah perkiraan batas atas: guru bisa saja membiarkan halaman "
    "terbuka. Angka tengah memakai median."
) % (JUMLAH_MINGGU, BATAS_WAJAR_MENIT)


def menit(nilai: Optional[float]) -> str:
    """Durasi menit untuk dibaca admin: '—', '7,5 mnt', atau '11 j 23 mnt'."""
    if nilai is None:
        return "—"
    if nilai < 60:
        return "%s mnt" % ("%.1f" % nilai).rstrip("0").rstrip(".").replace(".", ",")
    jam, sisa = divmod(int(round(nilai)), 60)
    return "%d j %d mnt" % (jam, sisa) if sisa else "%d j" % jam


def _baris(guru: PemakaianGuru) -> str:
    sumber = ", ".join(
        "%s %d" % (LABEL_SUMBER[kode], jumlah) for kode, jumlah in guru.sumber if jumlah
    ) or "—"
    return (
        '<tr><th scope="row">%s</th><td>%d / %d</td><td>%d</td><td>%d</td><td>%d</td>'
        "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>"
    ) % (
        e(guru.pengguna), guru.minggu_aktif, JUMLAH_MINGGU, guru.sesi_dibuat,
        guru.sesi_selesai, guru.sesi_dikonfirmasi, menit(guru.median_kerja_menit),
        menit(guru.median_jeda_konfirmasi_menit), menit(guru.median_tinjau_menit),
        e(sumber), guru.laporan_terbit,
    )


def _tabel_mingguan(daftar: Sequence[PemakaianGuru]) -> str:
    if not daftar:
        return ""
    kepala = "".join(
        '<th scope="col">%s</th>' % e(m.senin.strftime("%d/%m")) for m in daftar[0].minggu
    )
    baris = "".join(
        '<tr><th scope="row">%s</th>%s</tr>' % (
            e(g.pengguna), "".join("<td>%d</td>" % m.sesi_dibuat for m in g.minggu))
        for g in daftar
    )
    return (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>Sesi dibuat per minggu</h2><span class="admin-meta">Kolom = hari Senin awal minggu</span></div>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Sesi dibuat per minggu">'
        '<table class="admin-tabel"><thead><tr><th scope="col">Guru</th>%s</tr></thead>'
        "<tbody>%s</tbody></table></div></section>" % (kepala, baris)
    )


def halaman(daftar: Sequence[PemakaianGuru]) -> str:
    isi_baris = "".join(_baris(g) for g in daftar) or (
        '<tr><td colspan="10" class="admin-kosong">Belum ada guru yang memiliki sesi.</td></tr>'
    )
    kepala = "".join(
        '<th scope="col">%s</th>' % e(label) for label in (
            "Guru", "Minggu aktif", "Sesi dibuat", "Sesi selesai", "Sesi dikonfirmasi",
            "Lama anak mengerjakan", "Jeda selesai ke konfirmasi",
            "Buka tinjauan ke konfirmasi (perkiraan)", "Sumber pengiriman",
            "Laporan orang tua terbit",
        )
    )
    return (
        '<section class="admin-kartu admin-kartu-tabel"><div class="admin-kartu-kepala">'
        '<h2>Pemakaian per guru</h2><span class="admin-meta">%d minggu terakhir, hanya agregat</span></div>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="Pemakaian per guru">'
        '<table class="admin-tabel"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div></section>'
        "%s"
        '<section class="admin-kartu admin-catatan"><p><strong>Waktu persiapan belum bisa diukur.</strong></p>'
        '<p class="admin-meta">%s</p></section>'
    ) % (JUMLAH_MINGGU, kepala, isi_baris, _tabel_mingguan(daftar), e(CATATAN_KAKI))
