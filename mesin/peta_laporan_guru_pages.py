"""Halaman Guru untuk laporan Peta Kemampuan orang tua (D1-2): renderer murni, zero-JS.

Tiga keadaan satu anak: (a) belum ada draf (ringkasan data cek + tombol buat draf), (b) draf (pratinjau, catatan,
hapus, terbitkan), (c) terbit (baca-saja). Tanpa I/O: data datang dari `peta_laporan_guru_http` dan sudah lolos
allowlist (`cek_ringkasan_admin`, `peta_laporan_snapshot.periksa_isi`). Konfirmasi aksi tak bisa dibatalkan =
kotak centang yang ditegakkan SERVER (tanpa JS). Tanpa kunci jawaban, kode diagnosis, kontak, atau nomor order.
Semua nilai dinamis di-escape; warna hanya token `T.*`.
"""
from __future__ import annotations

import html

import admin_labels as L
import design_tokens as T
from teacher_shell import _halaman as _bingkai

RUTE_DASAR = "/anak/%d/peta"
LABEL_TINJAU = "Ditinjau Guru Jagomat"
BATAS_CATATAN = 2000
PETUNJUK_CATATAN = "Catatan ini dibaca orang tua dan anak. Jangan tulis nomor telepon, tautan, atau kunci jawaban."
PESAN_RETENSI = "Data per materi sudah dihapus (retensi 30 hari); laporan tidak bisa dibuat."
PESAN_BELUM_DINILAI = "Jawaban cek belum selesai dinilai; laporan belum bisa dibuat."
PESAN_TIDAK_TERBACA = "Data cek tidak terbaca; laporan belum bisa dibuat."
KONFIRMASI_TERBIT = "Setelah terbit, laporan tidak bisa diubah dan langsung terlihat oleh orang tua"
KONFIRMASI_HAPUS = (
    "Draf ini akan dihapus dan tidak bisa dikembalikan; data per materi tidak dapat dibuat ulang bila sudah lewat "
    "30 hari sejak cek")
PESAN_INFO = {
    "belum_bayar": "Pembayaran Peta Kemampuan untuk anak ini belum selesai, jadi laporan belum bisa dibuat.",
    "menunggu_verifikasi": "Bukti pembayaran Peta Kemampuan untuk anak ini masih diperiksa tim.",
    "ditolak": "Bukti pembayaran Peta Kemampuan untuk anak ini belum diterima tim.",
    "kedaluwarsa": "Pesanan Peta Kemampuan untuk anak ini kedaluwarsa sebelum dibayar.",
    "perlu_diperiksa": "Pembayaran Peta Kemampuan untuk anak ini sedang diperiksa tim. Laporan ditahan dulu.",
    "direfund": "Pembayaran Peta Kemampuan untuk anak ini sudah dikembalikan, jadi laporan tidak dibuat.",
}
PESAN_INFO_LAIN = "Pesanan Peta Kemampuan untuk anak ini belum bisa dipakai untuk laporan."

_GAYA = f"""<style>
.peta-guru .kartu-st{{padding:{T.SP_5}}}
.peta-guru .kartu-st > h2{{margin-top:0}}
.peta-guru label{{display:block;font-weight:700;margin:{T.SP_3} 0 {T.SP_1}}}
.peta-guru label.centang{{display:flex;gap:{T.SP_2};align-items:flex-start;font-weight:400}}
.peta-guru textarea{{width:100%;min-height:8rem;font:inherit;padding:{T.SP_3}}}
.peta-guru .baris-aksi{{display:flex;flex-wrap:wrap;gap:{T.SP_3};margin-top:{T.SP_4}}}
.peta-guru .peringatan{{background:{T.LATAR_CATATAN};border:1px solid {T.BORDER_CATATAN};border-radius:{T.RADIUS_SEDANG};padding:{T.SP_3} {T.SP_4};margin:{T.SP_3} 0}}
.peta-guru .pratinjau{{border:1px dashed {T.BORDER_HALUS};border-radius:{T.RADIUS_KARTU};padding:{T.SP_4};margin:{T.SP_4} 0;background:{T.LATAR_KARTU}}}
.peta-guru table{{width:100%;border-collapse:collapse}}
.peta-guru th,.peta-guru td{{text-align:left;padding:{T.SP_2};border-bottom:1px solid {T.BORDER_HALUS}}}
.peta-guru meter{{width:100%;min-width:6rem}}
</style>"""


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _bungkus(judul: str, isi: str, ident) -> bytes:
    return _bingkai(
        judul, _GAYA + '<div class="peta-guru">' + isi + "</div>", ident=ident, stitch=True,
        kelas_bungkus="pendamping-editorial-st bagikan-editorial-st", id_utama="judul-peta", privat=True)


def _kepala(siswa, galat: str = "") -> str:
    return (
        f'<div class="jejak"><a href="/anak/{int(siswa["id"])}?section=perkembangan">&larr; Perkembangan</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">PETA KEMAMPUAN</p>'
        f'<h1 id="judul-peta">Peta Kemampuan — {_e(siswa["nama"])}</h1></header>'
        + (f'<p class="peringatan" role="alert">{_e(galat)}</p>' if galat else ""))


def _waktu(nilai) -> str:
    return _e(L.tanggal(nilai + "Z"))


def _ringkasan_status(purna: dict, laporan, cek) -> str:
    """Janji terbit, terlambat, dan hitung mundur retensi data cek (hanya selagi belum ada laporan)."""
    baris = []
    if purna.get("janji_terbit"):
        baris.append(f"<li>Janji laporan terbit: {_waktu(purna['janji_terbit'])}</li>")
    if purna.get("terbit"):
        baris.append(f"<li>Laporan terbit: {_waktu(purna['terbit'])}</li>")
    elif laporan is not None and laporan["diterbitkan"]:
        baris.append(f"<li>Laporan terbit: {_e(laporan['diterbitkan'][:10])}</li>")
    elif purna.get("terlambat"):
        baris.append("<li><strong>Laporan terlambat dari janji.</strong> Mohon segera diterbitkan.</li>")
    if laporan is None and cek and cek.get("bahan") == "ada" and cek.get("hari_tersisa") is not None:
        baris.append(f"<li>Data per materi dihapus otomatis dalam {int(cek['hari_tersisa'])} hari "
                     "(retensi 30 hari). Buat draf laporan sebelum itu.</li>")
    if not baris:
        return ""
    return '<section class="kartu-st"><h2>Status laporan</h2><ul>' + "".join(baris) + "</ul></section>"


def _tabel_materi(per_materi) -> str:
    baris = "".join(
        f'<tr><th scope="row">{_e(m["materi"])}</th><td>{int(m["benar"])}</td><td>{int(m["total"])}</td>'
        f'<td><meter min="0" max="{int(m["total"])}" value="{int(m["benar"])}">'
        f'{int(m["benar"])} dari {int(m["total"])}</meter></td></tr>' for m in per_materi)
    return ('<table><thead><tr><th scope="col">Materi</th><th scope="col">Benar</th><th scope="col">Soal</th>'
            f'<th scope="col">Penguasaan</th></tr></thead><tbody>{baris}</tbody></table>')


def _daftar(judul: str, butir) -> str:
    if not butir:
        return ""
    return f"<h3>{_e(judul)}</h3><ul>" + "".join(f"<li>{_e(b)}</li>" for b in butir) + "</ul>"


def _pratinjau(isi: dict, catatan: str, tanggal_terbit) -> str:
    kelas = f"Kelas {int(isi['kelas'])} · " if isi["kelas"] else ""
    terbit = f"<p>Diterbitkan {_e(tanggal_terbit[:10])}</p>" if tanggal_terbit else ""
    catatan_html = "<h3>Catatan Guru</h3>" + (
        "".join(f"<p>{_e(p)}</p>" for p in catatan.split("\n") if p.strip())
        if catatan.strip() else "<p>Belum ada catatan.</p>")
    return (
        '<div class="pratinjau">'
        f'<p>{_e(LABEL_TINJAU)}</p><p>{kelas}Cek tanggal {_e(isi["tanggal_cek"])} · {int(isi["jumlah_soal"])} soal</p>'
        f'<p><strong>Skor {int(isi["skor"])} dari 100</strong> · {_e(isi["kategori"])}</p>'
        + _tabel_materi(isi["per_materi"]) + _daftar("Paling perlu dilatih dulu", isi["perlu_dilatih"])
        + _daftar("Sudah kuat", isi["kuat"]) + _daftar("Perlu penguatan", isi["ringkasan_perlu"])
        + catatan_html + terbit + "</div>")


def _kartu_cek(cek) -> str:
    """Keadaan (a): ringkasan per materi dan penjelasan bila bahan belum/tidak ada."""
    if cek is None:
        return f'<section class="kartu-st"><p>{_e(PESAN_TIDAK_TERBACA)}</p></section>'
    if cek["bahan"] == "dihapus":
        return f'<section class="kartu-st"><p>{_e(PESAN_RETENSI)}</p></section>'
    if cek["bahan"] != "ada":
        return f'<section class="kartu-st"><p>{_e(PESAN_BELUM_DINILAI)}</p></section>'
    kelas = f"Kelas {int(cek['kelas'])} · " if cek["kelas"] else ""
    return ('<section class="kartu-st"><h2>Hasil cek</h2>'
            f'<p>{kelas}Skor {int(cek["skor"])} dari 100 · {_e(cek["kategori"])} · {int(cek["jumlah_soal"])} soal</p>'
            + _tabel_materi(cek["per_materi"]) + "</section>")


def _form_buat(sid: int) -> str:
    return (f'<form method="post" action="{RUTE_DASAR % sid}/buat" class="kartu-st">'
            "<p>Draf memuat ringkasan hasil cek (dibekukan sekarang) dan catatan Anda untuk orang tua.</p>"
            '<div class="baris-aksi"><button class="btn-st" type="submit">Buat draf laporan</button></div></form>')


def _form_draf(sid: int, laporan, catatan_kiriman) -> str:
    dasar = RUTE_DASAR % sid
    isi_catatan = laporan["catatan"] if catatan_kiriman is None else catatan_kiriman
    return (
        f'<form method="post" action="{dasar}/catatan" class="kartu-st">'
        '<label for="catatan">Catatan untuk orang tua (teks ini dibaca orang tua)</label>'
        f'<textarea id="catatan" name="catatan" maxlength="{BATAS_CATATAN}">{_e(isi_catatan)}</textarea>'
        f'<p class="sub">Teks biasa, sampai {BATAS_CATATAN} karakter. Simpan catatan dulu sebelum menerbitkan.</p>'
        f'<p class="sub">{_e(PETUNJUK_CATATAN)}</p>'
        '<div class="baris-aksi"><button class="btn-st" type="submit">Simpan catatan</button></div></form>'
        f'<form method="post" action="{dasar}/terbitkan" class="kartu-st"><h2>Terbitkan</h2>'
        '<p>Yang diterbitkan adalah catatan yang sudah disimpan.</p>'
        f'<label class="centang"><input type="checkbox" name="konfirmasi" value="1" required> {_e(KONFIRMASI_TERBIT)}</label>'
        '<div class="baris-aksi"><button class="btn-st" type="submit">Terbitkan laporan</button></div></form>'
        f'<form method="post" action="{dasar}/hapus" class="kartu-st"><h2>Hapus draf</h2>'
        f'<label class="centang"><input type="checkbox" name="konfirmasi" value="1" required> {_e(KONFIRMASI_HAPUS)}</label>'
        '<div class="baris-aksi"><button class="btn-st" type="submit">Hapus draf</button></div></form>')


def halaman_peta(siswa, ident, *, purna: dict, laporan, cek, hanya_lihat: bool = False,
                 galat: str = "", catatan_kiriman=None) -> bytes:
    """Halaman Peta satu anak (order lunas). `laporan` None = belum ada draf; `cek` dipakai hanya bila belum ada."""
    sid = int(siswa["id"])
    isi = _kepala(siswa, galat) + _ringkasan_status(purna, laporan, cek)
    if laporan is None:
        isi += _kartu_cek(cek)
        if hanya_lihat:
            isi += '<p class="sub">Admin hanya dapat melihat. Laporan dibuat dan diterbitkan oleh Guru.</p>'
        elif cek is not None and cek["bahan"] == "ada":
            isi += _form_buat(sid)
    else:
        isi += "<h2>Pratinjau (sama dengan yang dilihat orang tua)</h2>" + _pratinjau(
            laporan["isi"], laporan["catatan"], laporan["diterbitkan"])
        if laporan["diterbitkan"]:
            isi += '<p class="sub">Laporan sudah terbit dan tidak bisa diubah.</p>'
        elif hanya_lihat:
            isi += '<p class="sub">Admin hanya dapat melihat. Laporan dibuat dan diterbitkan oleh Guru.</p>'
        else:
            isi += _form_draf(sid, laporan, catatan_kiriman)
    return _bungkus(f"Peta Kemampuan — {siswa['nama']}", isi, ident)


def halaman_info(siswa, ident, status: str) -> bytes:
    """Order ada tetapi belum lunas/ditahan/direfund: informasi saja, tanpa form dan tanpa data cek."""
    pesan = PESAN_INFO.get(status, PESAN_INFO_LAIN)
    return _bungkus(f"Peta Kemampuan — {siswa['nama']}",
                    _kepala(siswa) + f'<section class="kartu-st"><p>{_e(pesan)}</p></section>', ident)


def halaman_belum_bisa(siswa, ident) -> bytes:
    """Data pesanan tidak terbaca (DB admin): pesan tetap, tanpa detail galat."""
    return _bungkus(f"Peta Kemampuan — {siswa['nama']}",
                    _kepala(siswa) + '<section class="kartu-st"><p>Halaman ini belum bisa dibuka. '
                    "Coba lagi sebentar lagi.</p></section>", ident)


def kartu_masuk(siswa_id: int, *, purna: dict, laporan) -> str:
    """Satu kartu kecil di halaman anak: status laporan dan satu tautan ke halaman Peta."""
    if laporan is not None and laporan["diterbitkan"]:
        status = "Laporan sudah terbit."
    elif laporan is not None:
        status = "Draf laporan siap dilengkapi."
    elif purna.get("janji_terbit"):
        status = f"Janji laporan terbit: {_waktu(purna['janji_terbit'])}."
    else:
        status = "Laporan belum dibuat."
    return ('<section class="kartu-st laporan-ortu-masuk-st"><h2>Peta Kemampuan</h2>'
            f"<p>{_e(status)}</p>"
            f'<a class="kartu-masuk-aksi-st" href="{RUTE_DASAR % int(siswa_id)}">Buka Peta Kemampuan</a></section>')
