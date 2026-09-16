"""Tampilan laporan perjalanan; keputusan pedagogis milik reducer."""
from __future__ import annotations

import html
from typing import Callable

from learning_journey import PerjalananBelajar
from templates import label_kelas


TAHAP = {
    "perlu_dipelajari": "Perlu dipelajari",
    "latihan_terbimbing": "Latihan terbimbing",
    "penguatan": "Penguatan mandiri",
    "menunggu_evaluasi": "Menunggu evaluasi",
    "mulai_membaik": "Mulai membaik",
    "bertahan": "Bertahan",
    "perlu_diperkuat": "Perlu diperkuat lagi",
    "perlu_eskalasi": "Perlu eskalasi",
}
TINDAKAN = {
    "lanjutkan_sesi": "Lanjutkan sesi",
    "konfirmasi_hasil": "Konfirmasi hasil",
    "eskalasi": "Tinjau bersama pendamping",
    "pemetaan": "Lanjutkan pemetaan",
    "tunggu_pemetaan": "Tunggu pemetaan berikutnya",
    "probe_diagnostik": "Periksa kembali fokus pantauan",
    "intervensi": "Pelajari strategi bersama",
    "latihan_terbimbing": "Coba dengan bimbingan",
    "penguatan": "Coba mandiri",
    "evaluasi": "Lakukan evaluasi berjeda",
    "tunggu_evaluasi": "Tunggu evaluasi berjeda",
    "checkpoint": "Periksa ketahanan pemahaman",
    "tunggu_checkpoint": "Tunggu pemeriksaan berkala",
    "probe_setelah_pengenalan": "Periksa materi yang baru dikenalkan",
    "pengenalan": "Kenalkan materi baru",
    "mixed_maintenance": "Latihan campuran pemeliharaan",
    "putaran_baru": "Mulai putaran penguatan baru",
}
JENIS = {
    "pemetaan": "Pemetaan", "intervensi": "Strategi dipelajari bersama",
    "latihan_terbimbing": "Latihan terbimbing", "penguatan": "Penguatan mandiri",
    "evaluasi": "Evaluasi berjeda", "checkpoint": "Checkpoint",
    "pengenalan": "Pengenalan materi", "bebas": "Latihan manual",
    "maintenance": "Latihan pemeliharaan", "bukti_dibatalkan": "Bukti dikoreksi",
}
PEMAHAMAN = {
    "bisa_menjelaskan": "Bisa menjelaskan", "ragu": "Masih ragu",
    "menghafal": "Masih menghafal",
}
PENUTUP = {
    "putaran_ditutup": "Putaran ditutup", "diganti_level": "Kelas belajar berubah",
    "override_ditutup": "Fokus diganti oleh pendamping",
}


def judul_tindakan(perjalanan: PerjalananBelajar) -> str:
    """Label tindakan aman tanpa memantulkan kode internal."""
    return TINDAKAN.get(perjalanan.rekomendasi.tindakan, "Tinjau rencana bersama")


def _daftar_bukti(bukti, tanggal: Callable) -> str:
    item = []
    for satu in bukti:
        sesi = (
            f' · <a href="/sesi/{satu.sesi_id}">Sesi #{satu.sesi_id}</a>'
            if satu.sesi_id is not None else ""
        )
        pemahaman = ", ".join(
            PEMAHAMAN.get(nilai, "Pemahaman belum tercatat")
            for nilai in satu.cek_pemahaman
        )
        catatan = f" · {pemahaman}" if pemahaman else ""
        if satu.jenis in {"evaluasi", "checkpoint"} and not pemahaman:
            catatan = " · Pemahaman belum tercatat"
        if satu.jenis == "bukti_dibatalkan":
            catatan += (
                " · sudah dikonfirmasi ulang" if satu.status == "riwayat_invalidasi"
                else " · perlu konfirmasi ulang"
            )
        if satu.hasil is not None:
            catatan += " · " + TAHAP.get(satu.hasil, "Perlu ditinjau")
        label = JENIS.get(satu.jenis, "Kegiatan belajar")
        item.append(f"<li>{tanggal(satu.tanggal.isoformat())} · {label}{sesi}{catatan}</li>")
    if not item:
        return '<p class="sub">Belum ada bukti terkonfirmasi untuk fokus ini.</p>'
    return '<ul class="diagnosis-lis">' + "".join(item) + "</ul>"


def _bukti_ringkas(bukti, tanggal: Callable) -> str:
    """Tampilkan bukti awal dan tahap terbaru; sisanya tetap dapat dibuka."""
    jenis = {satu.jenis for satu in bukti}
    terpilih = {
        next(i for i, satu in enumerate(bukti) if satu.jenis == nama)
        if nama == "pemetaan" else
        max(i for i, satu in enumerate(bukti) if satu.jenis == nama)
        for nama in jenis
    }
    ringkas = tuple(satu for i, satu in enumerate(bukti) if i in terpilih)
    lainnya = tuple(satu for i, satu in enumerate(bukti) if i not in terpilih)
    detail = (
        '<details class="bukti-lainnya"><summary>Bukti sebelumnya</summary>'
        + _daftar_bukti(lainnya, tanggal) + '</details>' if lainnya else ""
    )
    return _daftar_bukti(ringkas, tanggal) + detail


def _kartu_fokus(fokus, nomor: int, nama_tipe: Callable, tanggal: Callable) -> str:
    nama = html.escape(nama_tipe(fokus.kunci[0]))
    status = TAHAP.get(fokus.tahap, "Perlu ditinjau")
    return (
        '<li class="aksi-laporan">'
        f'<h3>Fokus {nomor}: {nama}</h3><p><b>{status}</b></p>'
        f'{_bukti_ringkas(fokus.bukti, tanggal)}</li>'
    )


def _histori(perjalanan: PerjalananBelajar, nama_tipe: Callable, tanggal: Callable) -> str:
    if not perjalanan.histori:
        return ""
    item = []
    for putaran in perjalanan.histori:
        nama = ", ".join(html.escape(nama_tipe(kunci[0])) for kunci in putaran.fokus)
        kelas = html.escape(label_kelas(putaran.level))
        alasan = PENUTUP.get(putaran.alasan_penutupan, "Putaran ditutup")
        catatan = (
            "Sebagian bukti perlu konfirmasi ulang."
            if putaran.status_bukti == "perlu_konfirmasi_ulang" else
            "Ringkasan bukti yang masih terkonfirmasi saat ini, bukan klaim penguasaan permanen."
        )
        per_fokus = "".join(
            _kartu_fokus(fokus, nomor, nama_tipe, tanggal)
            for nomor, fokus in enumerate(putaran.perjalanan_fokus, 1)
        )
        rincian = (
            f'<ul class="daftar-aksi-laporan">{per_fokus}</ul>' if per_fokus
            else _daftar_bukti(putaran.bukti, tanggal)
        )
        koreksi = tuple(satu for satu in putaran.bukti if satu.jenis == "bukti_dibatalkan")
        if per_fokus and koreksi:
            rincian += '<p>Riwayat koreksi bukti:</p>' + _daftar_bukti(koreksi, tanggal)
        item.append(
            f'<li><h3>Putaran #{putaran.id} · {kelas}</h3><p>{nama}</p>'
            f'<p>{tanggal(putaran.dibuka.isoformat())} sampai '
            f'{tanggal(putaran.ditutup.isoformat())} · {alasan}.</p>'
            f'<p class="sub">{catatan}</p>{rincian}</li>'
        )
    return (
        '<section class="riwayat-putaran-laporan"><h3>Riwayat putaran sebelumnya</h3>'
        '<p>Putaran lama tetap tercatat meskipun fokus perlu diperkuat lagi.</p>'
        '<ul class="daftar-aksi-laporan">' + "".join(item) + '</ul></section>'
    )


def _tanpa_fokus(perjalanan: PerjalananBelajar, nama_tipe: Callable) -> str:
    rencana = perjalanan.rekomendasi
    if rencana.tindakan in {"pengenalan", "probe_setelah_pengenalan"}:
        materi = ", ".join(html.escape(nama_tipe(kunci[0])) for kunci in rencana.kandidat)
        return (
            '<p>Tidak ada fokus aktif. Materi baru bukan kelemahan anak.</p>'
            f'<p>Materi yang sedang dikenalkan atau diperiksa: <b>{materi}</b>.</p>'
        )
    if rencana.tindakan == "mixed_maintenance":
        return '<p>Tidak ada fokus aktif. Lanjutkan latihan pemeliharaan sesuai rencana.</p>'
    return (
        '<p>Belum cukup bukti untuk menetapkan fokus aktif. '
        'Hasil perlu selesai dan dikonfirmasi; latihan manual tidak otomatis masuk pemetaan.</p>'
    )


def render_perjalanan(perjalanan: PerjalananBelajar, nama_tipe: Callable, tanggal: Callable) -> str:
    """Render hanya data proyeksi; tidak membaca diagnosis atau menulis basis data."""
    rencana = perjalanan.rekomendasi
    putaran = (
        f"Putaran #{perjalanan.putaran_id}" if perjalanan.putaran_id else
        "Fokus disarankan — putaran belum dimulai" if perjalanan.fokus else
        "Pemetaan awal"
    )
    progres = min(len(perjalanan.tanggal_pemetaan), 3)
    fokus = "".join(
        _kartu_fokus(satu, nomor, nama_tipe, tanggal)
        for nomor, satu in enumerate(perjalanan.fokus, 1)
    )
    isi = (
        f'<ul class="daftar-aksi-laporan">{fokus}</ul>' if fokus else
        _tanpa_fokus(perjalanan, nama_tipe)
    )
    jadwal = (
        f'<p>Tersedia mulai {tanggal(rencana.tersedia_pada.isoformat())}.</p>'
        if rencana.tersedia_pada else ""
    )
    catatan = "".join(f'<p class="sub">{html.escape(teks)}</p>' for teks in perjalanan.catatan)
    return (
        '<section class="kartu" id="perjalanan-belajar" aria-labelledby="judul-perjalanan">'
        '<h2 id="judul-perjalanan">Perjalanan fokus belajar</h2>'
        f'<p class="sub">{putaran} · Pemetaan {progres} dari 3 tanggal</p>'
        f'<p><b>Langkah berikutnya: {judul_tindakan(perjalanan)}</b></p>'
        f'{jadwal}{catatan}{isi}'
        '<p class="sub">Status menggambarkan bukti saat ini. Mulai membaik perlu '
        'diperiksa lagi; bertahan tetap mendapat checkpoint berkala.</p>'
        f'{_histori(perjalanan, nama_tipe, tanggal)}</section>'
    )
