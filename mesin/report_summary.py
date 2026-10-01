"""Ringkasan deterministik untuk orang tua dari proyeksi perjalanan belajar.

Modul ini hanya memilih bahasa tampilan. Status, jadwal, fokus, dan tindakan
selalu berasal dari ``PerjalananBelajar`` yang sudah diputuskan reducer.
"""
from __future__ import annotations

import html
from typing import Callable

from cycle_report import judul_tindakan
from learning_journey import PerjalananBelajar


_STATUS_TERLIHAT = {
    "perlu_dipelajari": "masih perlu dipelajari bersama",
    "latihan_terbimbing": "sedang berlatih dengan bimbingan",
    "penguatan": "sedang menguatkan cara secara mandiri",
    "menunggu_evaluasi": "menunggu pemeriksaan setelah jeda",
    "mulai_membaik": "mulai membaik berdasarkan evaluasi terkonfirmasi",
    "bertahan": "bertahan pada pemeriksaan terakhir",
    "perlu_diperkuat": "masih perlu diperkuat dengan pendekatan berikutnya",
    "perlu_eskalasi": "perlu ditinjau bersama pendamping",
}
_TINDAKAN_DENGAN_INSTRUKSI = {"intervensi", "pengenalan"}
_STATUS_PERIKSA = {
    "perlu_dipelajari": "Pemahaman setelah belajar bersama belum diperiksa.",
    "latihan_terbimbing": "Kesiapan untuk mencoba mandiri belum diperiksa.",
    "penguatan": "Hasil pemeriksaan setelah jeda belum tersedia.",
    "menunggu_evaluasi": "Hasil pemeriksaan setelah jeda berikutnya masih perlu diperiksa.",
    "mulai_membaik": "Ketahanan pemahaman masih perlu diperiksa berkala.",
    "bertahan": "Status ini bukan penguasaan permanen; checkpoint berkala tetap diperlukan.",
    "perlu_diperkuat": "Pendekatan berikutnya dan pemahaman anak masih perlu diperiksa.",
    "perlu_eskalasi": "Penyebabnya belum disimpulkan oleh ringkasan ini.",
}


def _nama_fokus(fokus, nomor: int, nama_tipe: Callable[[str], str]) -> str:
    nama = html.escape(nama_tipe(fokus.kunci[0]))
    return f"Bagian {nomor}, {nama}"


def _pemahaman_relevan(fokus) -> str:
    """Ambil catatan dari evaluasi/checkpoint terbaru, bukan union histori."""
    relevan = [
        bukti for bukti in fokus.bukti
        if bukti.jenis in {"evaluasi", "checkpoint"}
    ]
    if not relevan:
        return ""
    terbaru = max(relevan, key=lambda bukti: (bukti.tanggal, bukti.sesi_id or 0))
    nilai = set(terbaru.cek_pemahaman)
    if "menghafal" in nilai:
        return "; catatan pemeriksaan terakhir: masih menghafal"
    if "ragu" in nilai:
        return "; catatan pemeriksaan terakhir: masih ragu"
    return ""


def _terlihat(perjalanan: PerjalananBelajar, nama_tipe: Callable[[str], str]) -> str:
    if perjalanan.fokus:
        item = []
        for nomor, fokus in enumerate(perjalanan.fokus, 1):
            status = _STATUS_TERLIHAT.get(
                fokus.tahap, "perlu ditinjau pada rencana belajar"
            )
            item.append(
                f'<li class="item-fokus-ringkasan">'
                f"{_nama_fokus(fokus, nomor, nama_tipe)} "
                f"{status}{_pemahaman_relevan(fokus)}.</li>"
            )
        return '<ul class="daftar-fokus-ringkasan">' + "".join(item) + "</ul>"

    tindakan = perjalanan.rekomendasi.tindakan
    if tindakan in {"pengenalan", "probe_setelah_pengenalan"}:
        materi = ", ".join(
            html.escape(nama_tipe(kunci[0]))
            for kunci in perjalanan.rekomendasi.kandidat[:2]
        )
        tambahan = f" Materi yang sedang diproses: {materi}." if materi else ""
        return "<p>Belum ada bagian aktif yang perlu dibantu; materi baru bukan kelemahan anak." + tambahan + "</p>"
    if tindakan == "mixed_maintenance":
        return "<p>Belum ada bagian aktif yang perlu dibantu dari hasil yang sudah diperiksa.</p>"
    return "<p>Catatan hasil yang sudah diperiksa belum cukup untuk menetapkan bagian yang perlu dibantu.</p>"


def _perlu_diperiksa(
    perjalanan: PerjalananBelajar, nama_tipe: Callable[[str], str]
) -> str:
    catatan = " ".join(html.escape(teks) for teks in perjalanan.catatan)
    if perjalanan.rekomendasi.tindakan == "konfirmasi_hasil":
        rincian = "Ada hasil latihan yang belum dikonfirmasi dan belum dipakai untuk menentukan langkah."
    elif perjalanan.rekomendasi.tindakan == "lanjutkan_sesi":
        rincian = "Hasil latihan yang sedang berjalan belum tersedia untuk menentukan langkah."
    elif perjalanan.fokus:
        rincian = '<ul class="daftar-fokus-ringkasan">' + "".join(
            f'<li class="item-fokus-ringkasan">'
            f"{_nama_fokus(fokus, nomor, nama_tipe)}: "
            + _STATUS_PERIKSA.get(
                fokus.tahap,
                "Status berikutnya perlu ditinjau di rencana belajar.",
            )
            + "</li>"
            for nomor, fokus in enumerate(perjalanan.fokus, 1)
        ) + "</ul>"
    else:
        rincian = "Perkembangan berikutnya perlu dilihat dari hasil yang selesai dan dikonfirmasi."
    catatan_html = f'<p class="catatan-ringkasan-laporan">{catatan}</p>' if catatan else ""
    if not rincian.startswith("<ul"):
        rincian = f"<p>{rincian}</p>"
    return catatan_html + rincian


def _langkah(perjalanan: PerjalananBelajar, tanggal: Callable[[object], str]) -> str:
    rencana = perjalanan.rekomendasi
    tindakan = judul_tindakan(perjalanan)
    if rencana.tindakan in _TINDAKAN_DENGAN_INSTRUKSI and rencana.intervensi is not None:
        tindakan = rencana.intervensi.tindakan
    jadwal = (
        f" Tersedia mulai {tanggal(rencana.tersedia_pada.isoformat())}."
        if rencana.tersedia_pada is not None else ""
    )
    return f"{html.escape(tindakan)}.{jadwal}"


def render_ringkasan(
    nama: str,
    perjalanan: PerjalananBelajar,
    siswa_id: int,
    nama_tipe: Callable[[str], str],
    tanggal: Callable[[object], str],
) -> str:
    """Render tiga bagian singkat tanpa statistik, penyimpanan, atau inferensi baru."""
    return (
        '<div class="kartu ringkasan-laporan">'
        '<h2 id="judul-ringkasan-laporan">Ringkasan untuk orang tua</h2>'
        f'<p class="sub">Ringkasan perjalanan belajar {html.escape(nama)}.</p>'
        '<section class="bagian-ringkasan-laporan"><h3>Yang terlihat</h3>'
        f'{_terlihat(perjalanan, nama_tipe)}</section>'
        '<section class="bagian-ringkasan-laporan"><h3>Yang masih perlu diperiksa</h3>'
        f'{_perlu_diperiksa(perjalanan, nama_tipe)}</section>'
        '<section class="bagian-ringkasan-laporan"><h3>Langkah berikutnya</h3>'
        f'<p>{_langkah(perjalanan, tanggal)}</p></section>'
        '<p class="sumber-ringkasan-laporan">Dasar ringkasan: '
        '<a href="#perjalanan-belajar">perjalanan dan status catatan hasil</a>.</p>'
        f'<a class="tombol sekunder aksi-ringkasan-laporan" '
        f'href="/anak/{int(siswa_id)}?section=rencana#judul-rencana-belajar">Lihat langkah berikutnya</a>'
        '</div>'
    )
