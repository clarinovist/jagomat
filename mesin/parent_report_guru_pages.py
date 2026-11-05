"""Halaman guru untuk menyusun, menerbitkan, dan mencabut laporan orang tua (zero-JS).

Aksi destruktif memakai <details> dengan kalimat konsekuensi dan tombol konfirmasi,
bukan skrip. Token mentah hanya tampil pada respons penerbitan/penggantian.
"""
from __future__ import annotations

import html
import json

import design_tokens as T
import parent_report_page as halaman
from teacher_shell import _halaman as _bingkai

_GAYA = f"""<style>
.lap-guru label{{display:block;font-weight:700;margin:{T.SP_3} 0 {T.SP_1}}}
.lap-guru textarea{{width:100%;min-height:8rem;font:inherit;padding:{T.SP_3}}}
.lap-guru .baris-aksi{{display:flex;flex-wrap:wrap;gap:{T.SP_3};margin-top:{T.SP_4}}}
.lap-guru details{{border:1px solid {T.BORDER_HALUS};border-radius:{T.RADIUS_SEDANG};padding:{T.SP_3};margin-top:{T.SP_3}}}
.lap-guru summary{{cursor:pointer;font-weight:700}}
.lap-guru .pratinjau{{border:1px dashed {T.BORDER_HALUS};border-radius:{T.RADIUS_KARTU};padding:{T.SP_4};margin:{T.SP_4} 0;background:{T.LATAR_KARTU}}}
.lap-guru .peringatan{{background:{T.LATAR_CATATAN};border:1px solid {T.BORDER_CATATAN};border-radius:{T.RADIUS_SEDANG};padding:{T.SP_3} {T.SP_4};margin:{T.SP_3} 0}}
.lap-guru table{{width:100%;border-collapse:collapse}}
.lap-guru th,.lap-guru td{{text-align:left;padding:{T.SP_2};border-bottom:1px solid {T.BORDER_HALUS}}}
.lap-guru input[type=text]{{width:100%}}
{halaman.GAYA_LO}
</style>"""


# Kalimat pembuka catatan (keputusan pemilik 6 Nov 2026, K1): templat netral yang harus
# dilengkapi guru. Tidak mengambil isi laporan; simpan ditolak selama PENANDA_ISI tersisa,
# dan terbit memakai catatan tersimpan saja, jadi templat tidak pernah terbit diam-diam.
PENANDA_ISI = "[isi]"
KALIMAT_PEMBUKA = f"Minggu ini kami berlatih {PENANDA_ISI}. Di rumah, Anda bisa membantu dengan {PENANDA_ISI}."


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _kembali(siswa_id) -> str:
    return f'<div class="jejak"><a href="/anak/{siswa_id}?section=perkembangan">&larr; Perkembangan</a></div>'


def _bungkus(judul, isi, ident, id_utama="judul-lap"):
    return _bingkai(
        judul, _GAYA + '<div class="lap-guru">' + isi + "</div>", ident=ident, stitch=True,
        kelas_bungkus="pendamping-editorial-st bagikan-editorial-st", id_utama=id_utama, privat=True,
    )


def kartu_masuk(siswa_id: int) -> str:
    """Satu-satunya pintu masuk: tab Perkembangan."""
    return (
        '<section class="kartu-st laporan-ortu-masuk-st"><h2>Laporan untuk orang tua</h2>'
        "<p>Bagikan ringkasan sederhana tanpa skor lewat tautan baca-saja yang bisa dicabut.</p>"
        f'<p><a class="btn-st" href="/anak/{siswa_id}/laporan-ortu">Laporan untuk orang tua</a></p></section>'
    )


def halaman_daftar(siswa, daftar, tautan, ident, *, hanya_lihat=False, galat="") -> bytes:
    sid = siswa["id"]
    if hanya_lihat:
        form = '<p class="sub">Admin hanya dapat melihat. Laporan dibuat dan diterbitkan oleh guru.</p>'
    else:
        form = (
            f'<form method="post" action="/anak/{sid}/laporan-ortu" class="kartu-st">'
            "<h2>Buat laporan baru</h2>"
            '<fieldset><legend>Periode</legend>'
            '<p><label><input type="radio" name="periode" value="30hari" checked> 30 hari terakhir</label></p>'
            '<p><label><input type="radio" name="periode" value="bulan"> Bulan ini</label></p>'
            '<p><label><input type="radio" name="periode" value="rentang"> Dari – sampai</label></p>'
            '<label for="dari">Dari</label><input id="dari" type="date" name="dari">'
            '<label for="sampai">Sampai</label><input id="sampai" type="date" name="sampai"></fieldset>'
            '<p class="sub">Laporan memuat topik latihan yang sudah kamu periksa, tahap belajar, dan langkah '
            "berikutnya. Tanpa skor, tanpa kode, tanpa nama pola soal.</p>"
            '<div class="baris-aksi"><button class="btn-st" type="submit">Buat draf laporan</button></div></form>'
        )
    if daftar:
        baris = "".join(
            f'<tr><td>{_e(d["periode_mulai"])} – {_e(d["periode_akhir"])}</td>'
            f'<td>{"Terbit " + _e(d["diterbitkan"][:10]) if d["diterbitkan"] else "Draf"}</td>'
            f'<td><a href="/anak/{sid}/laporan-ortu/{d["id"]}">Buka</a></td></tr>'
            for d in daftar
        )
        tabel = ('<section class="kartu-st"><h2>Laporan sebelumnya</h2><table><thead><tr><th>Periode</th>'
                 f"<th>Status</th><th></th></tr></thead><tbody>{baris}</tbody></table></section>")
    else:
        tabel = '<section class="kartu-st"><h2>Laporan sebelumnya</h2><p>Belum ada laporan.</p></section>'
    status = ""
    if tautan:
        status = ('<p class="peringatan">Satu tautan aktif untuk anak ini. Menerbitkan laporan baru '
                  "mematikan tautan sebelumnya.</p>")
    return _bungkus(
        f"Laporan untuk orang tua — {siswa['nama']}",
        _kembali(sid) + '<header class="editorial-kepala-st"><p class="editorial-alis-st">LAPORAN</p>'
        f'<h1 id="judul-lap">Laporan untuk orang tua — {_e(siswa["nama"])}</h1></header>'
        + (f'<p class="peringatan">{_e(galat)}</p>' if galat else "") + status + form + tabel,
        ident,
    )


def _pratinjau(siswa, lap):
    isi = json.loads(lap["isi"])
    return (
        '<div class="pratinjau">' + halaman.isi_laporan(
            nama=siswa["nama"], isi=isi, catatan=lap["catatan"], guru=lap["guru"],
            periode=(lap["periode_mulai"], lap["periode_akhir"]),
            diterbitkan=lap["diterbitkan"], kedaluarsa=None if not lap.get("kedaluarsa") else lap["kedaluarsa"],
            judul_tag="h2",
        ) + "</div>"
    )


def _konfirmasi(sid, lid, aksi, judul, akibat, tombol):
    return (
        f"<details><summary>{_e(judul)}</summary><p>{_e(akibat)}</p>"
        f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/{aksi}">'
        f'<button class="btn-st" type="submit">{_e(tombol)}</button></form></details>'
    )


def halaman_detail(siswa, lap, ident, *, tautan=None, berubah=0, token_url="", hanya_lihat=False,
                   galat="", catatan_kiriman=None) -> bytes:
    sid, lid = siswa["id"], lap["id"]
    dasar = f"/anak/{sid}/laporan-ortu/{lid}"
    kedaluarsa = tautan["kedaluarsa"] if tautan and tautan["laporan_id"] == lid else None
    pratinjau = _pratinjau(siswa, dict(lap, kedaluarsa=kedaluarsa))
    bagian = ""
    if token_url:
        bagian += (
            '<section class="kartu-st bagikan-kartu-st" aria-labelledby="label-tautan">'
            '<label id="label-tautan" for="tautan-ortu">Tautan untuk orang tua</label>'
            f'<input id="tautan-ortu" type="text" readonly value="{_e(token_url)}" spellcheck="false">'
            '<p class="sub">Salin sekarang: tautan ini hanya ditampilkan sekali. Siapa pun yang memegangnya '
            "dapat membaca laporan ini. Kirim hanya kepada orang tua anak, bukan di tempat umum. "
            "Berlaku 30 hari atau sampai dicabut.</p></section>"
        )
    if hanya_lihat:
        aksi = '<p class="sub">Admin hanya dapat melihat laporan.</p>'
    elif lap["diterbitkan"] is None:
        aksi = (
            f'<form method="post" action="{dasar}/catatan" class="kartu-st"><label for="catatan">Catatan guru (opsional)</label>'
            f'<textarea id="catatan" name="catatan" maxlength="2000">{_e(catatan_kiriman if catatan_kiriman is not None else (lap["catatan"] or KALIMAT_PEMBUKA))}</textarea>'
            f'<p class="sub">Ganti setiap {_e(PENANDA_ISI)} dengan kata-kata Anda, atau hapus kalimatnya, lalu Simpan catatan. '
            'Teks biasa, sampai 2000 karakter. Tidak bisa diubah setelah diterbitkan.</p>'
            '<div class="baris-aksi"><button class="btn-st" type="submit">Simpan catatan</button></div></form>'
            f'<form method="post" action="{dasar}/terbitkan" class="kartu-st"><p>Menerbitkan membuat tautan baca-saja '
            "30 hari dan mematikan tautan laporan lain untuk anak ini. Catatan yang belum disimpan tidak ikut terbit; "
            "tekan Simpan catatan dulu bila menulis catatan.</p>"
            '<div class="baris-aksi"><button class="btn-st" type="submit">Terbitkan dan buat tautan</button></div></form>'
            + _konfirmasi(sid, lid, "hapus", "Hapus draf", "Draf ini akan dihapus dan tidak bisa dikembalikan.", "Ya, hapus draf")
        )
    else:
        aktif = kedaluarsa is not None
        if aktif:
            status = ('<p class="peringatan">Tautan aktif sampai '
                      f"{_e(halaman._batas(kedaluarsa))}. Tautan lengkap tidak ditampilkan lagi; "
                      "buat tautan baru bila perlu.</p>")
        else:
            status = ('<p class="peringatan">Tautan tidak aktif (dicabut, kedaluwarsa, atau digantikan laporan lain).</p>')
        aksi = status
        if berubah > 0:
            aksi += (f'<p class="peringatan">Bukti berubah setelah laporan ini diterbitkan ({berubah} kejadian baru). '
                     "Laporan yang sudah terbit tidak ikut berubah. Buat laporan baru, atau cabut tautan.</p>"
                     f'<p><a class="btn-st" href="/anak/{sid}/laporan-ortu">Buat laporan baru</a></p>')
        aksi += _konfirmasi(
            sid, lid, "tautan", "Buat tautan baru" if not aktif else "Ganti tautan",
            "Tautan lama berhenti berlaku dan tautan baru ditampilkan sekali.", "Ya, buat tautan baru")
        if aktif:
            aksi += _konfirmasi(
                sid, lid, "tautan/cabut", "Cabut tautan",
                "Orang tua tidak bisa lagi membuka laporan ini. Tautan yang dicabut tidak dihidupkan lagi.",
                "Ya, cabut tautan")
    jenis = "Draf" if lap["diterbitkan"] is None else "Terbit " + lap["diterbitkan"][:10]
    return _bungkus(
        f"Laporan {lap['periode_mulai']} — {siswa['nama']}",
        f'<div class="jejak"><a href="/anak/{sid}/laporan-ortu">&larr; Daftar laporan</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">LAPORAN</p>'
        f'<h1 id="judul-lap">Laporan {_e(jenis)}</h1></header>'
        + (f'<p class="peringatan">{_e(galat)}</p>' if galat else "")
        + bagian + "<h2>Pratinjau (sama dengan yang dilihat orang tua)</h2>" + pratinjau + aksi,
        ident,
    )
