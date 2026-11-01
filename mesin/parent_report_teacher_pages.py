"""Permukaan guru untuk menyusun, menerbitkan, dan mencabut laporan orang tua.

Presentasi saja: kepemilikan, transaksi, dan token tetap milik
``parent_report_http``/``parent_report_store``. Semua halaman dikirim lewat
``_kirim_tautan`` karena halaman terbit menampilkan token sekali dan halaman
pratinjau memuat nama anak. Tidak ada skrip: aksi memakai form POST + 303.
"""
from __future__ import annotations

import html

import design_tokens as T
import parent_report
import parent_report_pages as halaman_ortu
from teacher_shell import _halaman_stitch

TATA_LETAK_GURU = f"""
.laporan-ortu-guru-st .kartu-laporan-ortu-st{{border:1px solid {T.CETAK_GARIS_TULIS};
border-radius:.75rem;padding:1rem 1.15rem;margin:0 0 1.25rem;background:{T.TEKS_PUTIH}}}
.laporan-ortu-guru-st .pratinjau-laporan-ortu-st{{border:1px solid {T.CETAK_GARIS_TULIS};
border-radius:.75rem;padding:1rem 1.15rem;margin:1rem 0;background:{T.TEKS_PUTIH}}}
.laporan-ortu-guru-st .aksi-laporan-ortu-st{{display:flex;flex-wrap:wrap;gap:.65rem;
align-items:center;margin:.75rem 0}}
.laporan-ortu-guru-st .tabel-laporan-ortu-st{{width:100%;border-collapse:collapse;margin:.5rem 0 1.25rem}}
.laporan-ortu-guru-st .tabel-laporan-ortu-st th,
.laporan-ortu-guru-st .tabel-laporan-ortu-st td{{text-align:left;padding:.45rem .5rem;
border-bottom:1px solid {T.CETAK_GARIS_TULIS};vertical-align:top}}
.laporan-ortu-guru-st textarea{{width:100%;min-height:7rem}}
.laporan-ortu-guru-st .tautan-laporan-ortu-st{{font-weight:600}}
.laporan-ortu-guru-st .peringatan-laporan-ortu-st{{border-left:3px solid {T.AKSEN_MURID_AMBER};
padding-left:.75rem;margin:.75rem 0}}
.laporan-ortu-guru-st .galat-laporan-ortu-st{{border-left:3px solid {T.TEKS_GALAT};
padding-left:.75rem;margin:.75rem 0}}
"""

PESAN = {
    "draf-dibuat": "Draf dibuat. Periksa pratinjau di bawah, lalu terbitkan bila sudah siap.",
    "catatan-disimpan": "Catatan tersimpan di draf ini.",
    "tautan-dicabut": "Tautan dicabut. Tautan lama tidak bisa dipakai lagi.",
    "draf-dihapus": "Draf dihapus.",
    "tautan-baru": "Tautan baru dibuat. Token lama sudah tidak berlaku.",
}


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _peringatan(teks: str, kelas: str = "peringatan-laporan-ortu-st") -> str:
    return f'<p class="{kelas}" role="status">{teks}</p>'


def _status_laporan(baris) -> str:
    return "Terbit" if baris["diterbitkan"] else "Draf"


def _tautan_status(tautan, laporan_id: int, kini) -> str:
    """Ringkasan status tautan tanpa pernah menampilkan token/hash."""
    if tautan is None:
        return "Belum ada tautan."
    if tautan["dicabut"] is not None:
        return "Tautan sudah dicabut. Buat tautan baru bila orang tua perlu membukanya lagi."
    if int(tautan["kedaluarsa"]) <= int(kini):
        return ("Tautan sudah kedaluwarsa (berlaku 30 hari, tanpa perpanjangan "
                "otomatis). Buat tautan baru bila masih diperlukan.")
    if int(tautan["laporan_id"]) != int(laporan_id):
        return ("Tautan aktif saat ini menunjuk laporan terbit terbaru. "
                "Membuat tautan baru di halaman ini akan mengarahkannya ke "
                "laporan yang sedang dibuka dan mematikan token sebelumnya.")
    return (f'Tautan aktif sampai {halaman_ortu.tanggal_tag(tautan["kedaluarsa"])} '
            '(30 hari sejak dibuat, tanpa perpanjangan otomatis).')


def _tautan_ringkas(tautan, kini: int) -> str:
    """Ringkasan status tautan untuk daftar; token/hash tidak pernah tampil."""
    if tautan is None:
        return "Belum ada tautan untuk anak ini."
    if tautan["dicabut"] is not None:
        return "Tautan anak ini sudah dicabut."
    if int(tautan["kedaluarsa"]) <= int(kini):
        return "Tautan anak ini sudah kedaluwarsa."
    return (f'Tautan anak ini aktif sampai '
            f'{halaman_ortu.tanggal_tag(tautan["kedaluarsa"])}.')


def halaman_daftar(
    siswa,
    laporan,
    tautan,
    *,
    pengguna: str,
    peran: str,
    kini: int,
    pesan: str = "",
    galat: str = "",
) -> bytes:
    """Daftar laporan + form periode. Admin hanya membaca (tanpa form)."""
    sid = int(siswa["id"])
    bagian = [
        f'<p class="jejak"><a href="/anak/{sid}?section=perkembangan">'
        '&larr; Kembali ke Perkembangan</a></p>',
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">'
        'KOMUNIKASI KE ORANG TUA</p>'
        f'<h1 id="judul-laporan-ortu">{_e(siswa["nama"])} — laporan untuk orang tua</h1>'
        '<p class="sub">Satu tautan baca-saja per anak, berlaku 30 hari. Isinya '
        'tanpa skor: topik yang sudah dikonfirmasi, tahap belajar, langkah '
        'berikutnya, dan catatan Anda.</p></header>',
    ]
    if pesan:
        bagian.append(_peringatan(_e(PESAN.get(pesan, pesan))))
    if galat:
        bagian.append(_peringatan(_e(galat), "galat-laporan-ortu-st"))
    if peran == "admin":
        bagian.append(_peringatan(
            "Admin hanya dapat melihat. Menerbitkan atau mencabut laporan adalah "
            "tugas guru pemilik anak. Tidak ada aksi tulis di halaman ini."
        ))
    else:
        bagian.append(
            '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-buat-laporan">'
            '<h2 id="judul-buat-laporan">Buat draf periode baru</h2>'
            f'<form method="post" action="/anak/{sid}/laporan-ortu">'
            '<fieldset><legend>Periode latihan</legend>'
            '<label><input type="radio" name="periode" value="30" checked> '
            '30 hari terakhir</label><br>'
            '<label><input type="radio" name="periode" value="bulan"> '
            'Bulan ini</label><br>'
            '<label><input type="radio" name="periode" value="custom"> '
            'Pilih tanggal</label>'
            '<p class="sub">Isi tanggal hanya bila memilih &ldquo;Pilih tanggal&rdquo;.</p>'
            '<label>Dari <input type="date" name="mulai"></label> '
            '<label>Sampai <input type="date" name="sampai"></label>'
            '</fieldset>'
            '<p><button type="submit">Buat draf</button></p></form>'
            '<p class="sub">Hanya sesi yang sudah selesai dan dikonfirmasi guru '
            'yang masuk laporan. Draf belum bisa dibuka lewat tautan.</p></section>'
        )

    baris = ['<table class="tabel-laporan-ortu-st"><caption class="sub">'
             'Riwayat laporan anak ini</caption>'
             '<thead><tr><th scope="col">Periode</th><th scope="col">Status</th>'
             '<th scope="col">Terbit</th><th scope="col">Aksi</th></tr></thead><tbody>']
    if not laporan:
        baris.append('<tr><td colspan="4">Belum ada laporan untuk anak ini.</td></tr>')
    for item in laporan:
        periode = (f'{halaman_ortu.tanggal_tag(item["periode_mulai"])} – '
                   f'{halaman_ortu.tanggal_tag(item["periode_akhir"])}')
        terbit = (halaman_ortu.tanggal_tag(item["diterbitkan"])
                  if item["diterbitkan"] else "—")
        baris.append(
            f'<tr><td>{periode}</td><td>{_status_laporan(item)}</td>'
            f'<td>{terbit}</td><td>'
            f'<a href="/anak/{sid}/laporan-ortu/{int(item["id"])}">Buka</a></td></tr>'
        )
    baris.append('</tbody></table>')
    bagian.append("".join(baris))
    bagian.append(f'<p class="sub">{_tautan_ringkas(tautan, kini)}</p>')
    isi = (f'<style>{halaman_ortu.TATA_LETAK}{TATA_LETAK_GURU}</style>'
           '<main aria-labelledby="judul-laporan-ortu">' + "".join(bagian) + '</main>')
    return _halaman_stitch(
        "Laporan untuk orang tua", isi, ident=(pengguna, peran),
        kelas_bungkus="pendamping-editorial-st laporan-editorial-st "
                      "profil-workspace-st laporan-ortu-guru-st",
        privat=True,
    )


def halaman_detail(
    siswa,
    laporan,
    tautan,
    *,
    pengguna: str,
    peran: str,
    kini: int,
    pesan: str = "",
    galat: str = "",
    token_baru: str | None = None,
    kejadian_baru: int = 0,
    berlaku_sampai=None,
) -> bytes:
    """Pratinjau identik + kontrol draf/terbit. Token mentah hanya sekali."""
    sid = int(siswa["id"])
    lid = int(laporan["id"])
    terbit = bool(laporan["diterbitkan"])
    isi_snapshot = parent_report.muat_isi(laporan["isi"])
    bagian = [
        f'<p class="jejak"><a href="/anak/{sid}/laporan-ortu">'
        '&larr; Semua laporan anak ini</a> · '
        f'<a href="/anak/{sid}?section=perkembangan">Perkembangan</a></p>',
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">'
        + ("LAPORAN TERBIT (TIDAK DAPAT DIUBAH)" if terbit else "DRAF LAPORAN")
        + '</p>'
        f'<h1 id="judul-laporan-ortu">Laporan untuk orang tua</h1>'
        '<p class="sub">Semua yang tampil di pratinjau ini juga yang akan '
        'dibaca orang tua lewat tautan.</p></header>',
    ]
    if pesan:
        bagian.append(_peringatan(_e(PESAN.get(pesan, pesan))))
    if galat:
        bagian.append(_peringatan(_e(galat), "galat-laporan-ortu-st"))
    if peran == "admin":
        bagian.append(_peringatan(
            "Admin hanya dapat melihat pratinjau. Menerbitkan, mengganti, atau "
            "mencabut tautan adalah tugas guru pemilik anak."
        ))
    if kejadian_baru:
        bagian.append(_peringatan(
            f'Bukti berubah setelah laporan ini diterbitkan '
            f'({kejadian_baru} kejadian baru). Laporan terbit tidak diubah '
            'diam-diam: buat laporan baru untuk versi terbaru; tautan lama '
            'otomatis mati.'
        ))

    bagian.append(
        '<section class="pratinjau-laporan-ortu-st" '
        'aria-labelledby="judul-pratinjau-laporan">'
        '<p class="editorial-alis-st">PRATINJAU</p>'
        + halaman_ortu.isi_laporan(
            siswa["nama"], laporan["periode_mulai"], laporan["periode_akhir"],
            isi_snapshot, laporan["catatan"], laporan["guru"],
            laporan["diterbitkan"], berlaku_sampai,
            tingkat_judul=2, id_judul="judul-pratinjau-laporan",
        )
        + '</section>'
    )

    if not terbit and peran == "guru":
        bagian.append(
            '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-catatan-guru">'
            '<h2 id="judul-catatan-guru">Catatan guru (opsional)</h2>'
            f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/catatan">'
            '<label for="catatan-laporan-ortu">Catatan untuk orang tua</label>'
            '<textarea id="catatan-laporan-ortu" name="catatan" maxlength="2000" '
            'rows="6">' + _e(laporan["catatan"]) + '</textarea>'
            '<p class="sub">Teks polos, maksimal 2.000 karakter. Catatan ini '
            'tampil di bagian &ldquo;Catatan guru&rdquo;.</p>'
            '<p><button type="submit">Simpan catatan</button></p></form></section>'
        )
        bagian.append(
            '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-terbitkan">'
            '<h2 id="judul-terbitkan">Terbitkan</h2>'
            '<p class="peringatan-laporan-ortu-st">Setelah terbit, isi laporan '
            'tidak dapat diubah. Koreksi dibuat sebagai laporan baru. Menerbitkan '
            'sekaligus membuat tautan baru dan mematikan tautan lama anak ini.</p>'
            f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/terbitkan">'
            '<p><button type="submit">Terbitkan &amp; buat tautan</button></p></form>'
            f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/hapus" '
            'class="aksi-laporan-ortu-st">'
            '<button type="submit">Hapus draf</button>'
            '<span class="sub">Draf yang dihapus tidak pernah dibaca orang tua.</span>'
            '</form></section>'
        )

    if token_baru:
        bagian.append(
            '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-token-baru">'
            '<h2 id="judul-token-baru">Tautan baca-saja (tampil sekali)</h2>'
            '<label for="tautan-laporan">Tautan untuk orang tua</label>'
            f'<input id="tautan-laporan" type="text" readonly spellcheck="false" '
            f'value="{_e(token_baru)}">'
            '<p class="sub">Pilih seluruh isi kotak, lalu salin dan kirim ke orang '
            'tua lewat kanal yang Anda percaya. Token ini tidak disimpan dan tidak '
            'bisa ditampilkan lagi; bila hilang, buat tautan baru.</p>'
            '</section>'
        )

    bagian.append(
        '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-tautan">'
        '<h2 id="judul-tautan">Tautan</h2>'
        f'<p>{_tautan_status(tautan, lid, kini)}</p>'
    )
    if terbit and peran == "guru":
        bagian.append(
            f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/tautan" '
            'class="aksi-laporan-ortu-st">'
            '<button type="submit">Ganti tautan (token lama mati)</button></form>'
        )
        aktif = (tautan is not None and tautan["dicabut"] is None
                 and int(tautan["kedaluarsa"]) > int(kini))
        if aktif:
            bagian.append(
                f'<form method="post" action="/anak/{sid}/laporan-ortu/{lid}/tautan/cabut" '
                'class="aksi-laporan-ortu-st">'
                '<button type="submit">Cabut tautan</button></form>'
            )
        bagian.append(
            f'<p class="sub"><a href="/anak/{sid}/laporan-ortu">Buat laporan baru '
            'untuk periode lain</a></p>'
        )
    bagian.append('</section>')

    isi = (f'<style>{halaman_ortu.TATA_LETAK}{TATA_LETAK_GURU}</style>'
           '<main aria-labelledby="judul-laporan-ortu">' + "".join(bagian) + '</main>')
    return _halaman_stitch(
        "Laporan untuk orang tua", isi, ident=(pengguna, peran),
        kelas_bungkus="pendamping-editorial-st laporan-editorial-st "
                      "profil-workspace-st laporan-ortu-guru-st",
        privat=True,
    )
