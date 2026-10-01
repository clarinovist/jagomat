"""Façade kompatibel halaman guru: workspace, sesi, review, dan lembar.

Router HTTP tetap di web.py. Bingkai/topbar dimiliki ``teacher_shell.py``
dan di-re-export di sini agar caller lama tetap bekerja. Aturan lama tetap:
modul ini tidak boleh mengimpor students di atas file (impor terlambat di
fungsi yang membutuhkannya).
"""

from __future__ import annotations

import html
import random
import database
import brand
import design_tokens as T
import question_views
import visual_renderer
import presentation_lock
import share_links
import worksheets
from diagnosis import diagnosa, Usulan
from teacher_corrections import (
    pilihan_tersimpan, cara_untuk_form, cara_dari_form, label_penilaian,
)
from generator import LEVEL_BAWAAN
from template_labels import nama_tipe_soal as _nama_template
from templates import Soal
from question_context import label_profil_parameter as label_kelas
from topics import TOPIK_BAWAAN, ambil, dari_sesi
from teacher_style import SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA
from teacher_shell import (
    _halaman,
    _halaman_stitch,
    _topbar,
    _topbar_stitch,
)
from teacher_workspace import (
    INFO_LATIHAN_BEBAS,
    LABEL_KODE_REMEDIAL,
    _ambil,
    _badge_review_status,
    _kelas_sekolah_profil,
    _kontrol_mode_sesi,
    _kontrol_profil_parameter,
    _fmt_durasi,
    _form_remedial,
    _mode_sesi,
    _nama_topik_sesi,
    _ringkasan_angka_sesi,
    _tanggal_ringkas,
    _topik_untuk_level,
    halaman_anak,
)


KODE_PILIHAN = [
    ("", "— pilih —"),
    ("benar", "Benar"),
    ("K", "K — salah konsep"),
    ("B", "B — salah baca soal"),
    ("H", "H — salah hitung"),
    ("E", "E — salah tulis akhir"),
    ("N", "N — menebak"),
]


# Satu sumber teks bubble ikon "ⓘ" beranda guru: dipakai sebagai aria-label
# tombol sekaligus isi bubble supaya pembaca layar dan mata membaca hal sama.
INFO_DAFTAR_ANAK = (
    "Setiap anak punya halaman sendiri: buat latihan, rencana belajar, "
    "dan riwayat."
)

def _blok_latihan_serupa(kon, sesi_id: int) -> str:
    """CTA manual per tipe T, terpisah dari form koreksi hasil."""
    from similar_practice import kandidat_sesi

    kandidat = kandidat_sesi(kon, sesi_id)
    if not kandidat:
        return ""
    aksi = []
    for item in kandidat:
        nomor = ", ".join(str(n) for n in item["nomor"])
        nama = _nama_template(str(item["template_id"]))
        aksi.append(
            '<article class="pilihan-remedial-st">'
            '<span class="isi-pilihan-remedial-st">'
            f'<b>{html.escape(nama)}</b>'
            f'<span class="meta-remedial-st">Lihat pembahasan soal nomor {html.escape(nomor)}</span>'
            '</span>'
            f'<form method="post" action="/sesi/{sesi_id}/latihan-serupa">'
            f'<input type="hidden" name="sesi_soal_id" value="{int(item["sesi_soal_id"])}">'
            '<button type="submit" class="st-tombol-coral">Latih tipe soal ini</button>'
            '</form></article>'
        )
    return (
        '<section class="remedial-st latihan-serupa-st" aria-labelledby="judul-latihan-serupa">'
        '<h2 id="judul-latihan-serupa">Setelah materi baru dikenalkan</h2>'
        '<p>Kenalkan konsepnya, kerjakan satu contoh dari pembahasan bersama, '
        'lalu tutup contoh sebelum anak mencoba lima soal baru.</p>'
        '<p class="sub">Bedakan belum belajar dari bingung membaca atau menghitung. '
        'Minta anak menjelaskan caranya; jawaban benar saja belum berarti sudah paham.</p>'
        '<p class="sub"><b>Latihan manual:</b> tidak mengubah progres rencana terpandu '
        'dan bukan tanda materi sudah dikuasai.</p>'
        f'<div class="daftar-remedial-st">{"".join(aksi)}</div></section>'
    )


def _soal_dari_baris(baris) -> Soal:
    """Wrapper kompatibilitas menuju adapter pembaca penyajian sesi."""
    return question_views.soal_dari_baris(baris)


def _badge_mode(baris) -> str:
    """Badge 'Latihan Cepat' untuk sesi drill; kosong untuk diagnostik.

    CSS guru memuat kata "Latihan Cepat" di komentar, jadi badge-nya
    harus marker kelas, bukan teks yang dicari mentah.
    """
    if _ambil(baris, "mode", "diagnostik") == "drill":
        return '<span class="badge-mode">Latihan Cepat</span>'
    return ""


def halaman_utama_stitch(
    kon,
    pesan: str = "",
    pemilik: str | None = None,
    peran: str = "guru",
    sorot: int | None = None,
) -> bytes:
    """Beranda pendamping: satu pintu per anak, tanpa keputusan belajar baru.

    Status kirim/review hanya ringkasan aktivitas, bukan bukti penguasaan.
    Langkah berikutnya tetap berada pada profil anak dan reducer yang sama.
    """
    baris = []
    for s in database.daftar_siswa(kon, pemilik):
        rekap = kon.execute(
            """SELECT COUNT(*) AS jumlah,
                      SUM(CASE WHEN dibatalkan IS NOT NULL
                          THEN 1 ELSE 0 END) AS dibatalkan,
                      SUM(CASE WHEN dibatalkan IS NULL
                          AND selesai IS NOT NULL AND direview IS NULL
                          THEN 1 ELSE 0 END) AS belum_review,
                      SUM(CASE WHEN dibatalkan IS NULL AND selesai IS NULL
                          THEN 1 ELSE 0 END) AS belum_kirim
               FROM sesi WHERE siswa_id = ?""",
            (s["id"],),
        ).fetchone()
        jumlah_sesi = rekap["jumlah"] or 0
        dibatalkan = rekap["dibatalkan"] or 0
        belum_review = rekap["belum_review"] or 0
        belum_kirim = rekap["belum_kirim"] or 0
        status = []
        if belum_review:
            status.append(f'<span class="guru-status-st periksa">{belum_review} menunggu diperiksa</span>')
        if belum_kirim:
            status.append(f'<span class="guru-status-st">{belum_kirim} belum dikirim</span>')
        if not status:
            if jumlah_sesi == 0:
                ringkasan = "Belum ada sesi"
            elif jumlah_sesi == dibatalkan:
                ringkasan = "Tidak ada latihan yang perlu dikerjakan."
            else:
                ringkasan = "semua direview"
            status.append(f'<span class="guru-status-st">{ringkasan}</span>')
        label_batal = (
            f'<span>{dibatalkan} dibatalkan</span>' if dibatalkan else ""
        )
        label_keluarga = ""
        if peran == "admin":
            label_keluarga = f'<span>keluarga: {html.escape(s["pemilik"] or "warisan")}</span>'
        nama = str(s["nama"])
        from learning_profile import label_kelas_sekolah
        kelas_sekolah = _kelas_sekolah_profil(kon, s)
        tujuan_anak = (
            f'/anak/{s["id"]}?section=rencana'
            if not s["tingkat"] else f'/anak/{s["id"]}'
        )
        baris.append(
            f'<a class="st-kartu kartu-anak" href="{tujuan_anak}">'
            f'<span class="guru-inisial-st" aria-hidden="true">{html.escape(nama[:1].upper())}</span>'
            '<div class="guru-identitas-st">'
            f'<h3 class="guru-nama-st">{html.escape(nama)}</h3>'
            '<div class="guru-meta-st">'
            f'<span>{html.escape(label_kelas_sekolah(kelas_sekolah))}</span>'
            f'<span>{jumlah_sesi} latihan tercatat</span>{label_batal}{label_keluarga}</div>'
            f'<div class="guru-status-daftar-st">{"".join(status)}</div></div>'
            '<span class="guru-buka-st">Buka profil <span aria-hidden="true">↗</span></span>'
            '</a>'
        )

    tambah = (
        '<a class="guru-tambah-st" href="/akun?section=siswa">'
        '<span aria-hidden="true">＋</span> '
        + ('Tambah anak' if baris else 'Tambahkan anak pertama') + '</a>'
    )
    isi_utama = (
        '<div class="guru-kepala-daftar-st"><div>'
        '<p class="guru-alis-st">RUANG BELAJAR MEREKA</p>'
        f'<h2 id="daftar-anak">Anak &amp; siswa <span>{len(baris)}</span></h2>'
        f'</div>{tambah}</div>'
        '<p class="guru-petunjuk-st info-baris">Pilih nama untuk mulai. '
        f'<button type="button" class="info" aria-label="{html.escape(INFO_DAFTAR_ANAK, quote=True)}">'
        f'i<span class="info-bubble" role="tooltip">{html.escape(INFO_DAFTAR_ANAK)}</span></button></p>'
        f'<div class="daftar-anak">{"".join(baris)}</div>'
    ) if baris else (
        '<div class="guru-kosong-st">'
        '<p class="guru-alis-st">MULAI DARI SINI</p>'
        '<h2 id="daftar-anak">Kenali langkah pertama mereka.</h2>'
        '<p>Akunmu sudah siap. Tambahkan anak dengan nama panggilan, '
        'lalu buka profilnya untuk mulai mendampingi belajar.</p>'
        f'{tambah}<p class="guru-petunjuk-st">Belum ada latihan. '
        'Langkah berikutnya akan tersedia di profil anak.</p></div>'
    )
    kabar = (
        '<div class="st-banner-sukses" role="status"><span class="ikon" aria-hidden="true">✓</span>'
        f'<span>{html.escape(pesan)}</span></div>' if pesan else ''
    )
    return _halaman_stitch(
        "Ruang pendamping",
        '<main aria-labelledby="judul-guru">'
        '<header class="guru-sapaan-st"><div>'
        '<p class="guru-alis-st">RUANG ORANG TUA &amp; GURU</p>'
        '<h1 id="judul-guru">Langkah kecil,<br><span>tumbuh bersama.</span></h1>'
        '<p>Temani prosesnya, bukan hanya hasilnya.<br>'
        'Mulai dari ruang belajar anak di bawah ini.</p></div>'
        '<div class="guru-catatan-st" aria-hidden="true">'
        '<span class="guru-coret-st">✳</span>'
        '<img src="/aset/maskot-membaca-v3-240.png" width="240" height="240" alt="">'
        '<span>Satu langkah yang berarti.</span></div></header>'
        f'{kabar}<section aria-labelledby="daftar-anak">{isi_utama}</section>'
        '<footer class="guru-kaki-st"><span aria-hidden="true">✳</span> '
        'Beri ruang untuk mencoba, bertanya, dan menjelaskan.</footer></main>',
        ident=(pemilik if pemilik else "guru", peran),
        kelas_bungkus="guru-beranda-st",
    )


def _tombol_cerita(kon, sesi_id: int) -> str:
    """Tombol "variasi cerita" (LLM B2). Manual, bukan otomatis.

    Otomatis saat buat sesi berarti tiap sesi membayar 12 panggilan API
    tanpa guru pernah memilih. Satu tombol membuat biayanya sadar: guru
    menekannya kalau anak mulai hafal kalimat soalnya, bukan tiap kali.

    Kalau kunci DeepSeek tidak dipasang, tombolnya tidak muncul sama sekali
    — bukan muncul lalu gagal saat ditekan. Fitur yang mati harus terlihat
    mati.
    """
    import llm

    if not llm.aktif():
        return ""

    penyajian = question_views.penyajian_sesi_aman(kon, sesi_id)
    sudah = sum(p.asal_teks == "cerita" for p in penyajian)
    total = len(penyajian)

    if sudah >= total and total:
        catatan = f"Semua {total} soal sudah punya versi cerita."
        tombol = ""
    else:
        catatan = (
            f"{sudah} dari {total} soal punya versi cerita. "
            "Angka dan kuncinya tidak berubah — hanya kalimatnya."
        )
        tombol = (
            f'<form method="post" action="/cerita/{sesi_id}" '
            f'style="margin-top:.6rem">'
            f'<button type="submit" class="tombol-amber" '
            f'style="margin-top:0">Ubah cerita soal</button></form>'
        )

    jumlah_visual = sum(p.status_visual == "siap" for p in penyajian)
    if jumlah_visual:
        catatan += (
            f" {jumlah_visual} soal visual memakai kalimat tetap agar sesuai gambar."
        )
        if not any(
            p.status_visual != "siap" and p.asal_teks != "cerita"
            for p in penyajian
        ):
            tombol = ""

    if llm._sesi_terkunci(kon, sesi_id):
        catatan += " Penyajian sesi sudah dikunci; buat sesi baru untuk variasi lain."
        tombol = ""

    return (
        '<details class="cerita-tambahan-st">'
        '<summary>Opsi tambahan: ubah cerita soal</summary>'
        '<div class="kartu-variasi"><p>Mengubah redaksi; angka dan jawaban tetap.</p>'
        f'<p class="sub">{catatan}</p>{tombol}</div></details>'
    )

def halaman_bagikan_sesi(sesi_id: int, siswa_id: int, tautan: str, pengguna: str, peran: str) -> bytes:
    """Salin tautan secara manual; hanya presentasi, tanpa membaca/membuat token."""
    return _halaman(
        f"Bagikan sesi #{sesi_id}",
        f'<div class="jejak"><a href="/anak/{siswa_id}">&larr; Kembali ke profil anak</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">BELAJAR LEWAT TAUTAN</p>'
        f'<h1 id="judul-bagikan">Bagikan sesi #{sesi_id}</h1>'
        '<p class="sub">Salin tautan ini dan berikan kepada anak yang mengerjakan sesi ini.</p></header>'
        '<section class="kartu bagikan-kartu-st" aria-labelledby="label-tautan">'
        '<label id="label-tautan" for="tautan-sesi">Tautan latihan anak</label>'
        f'<input id="tautan-sesi" type="text" readonly value="{html.escape(tautan, quote=True)}" '
        'aria-describedby="petunjuk-tautan" spellcheck="false">'
        '<p id="petunjuk-tautan" class="sub">Pilih seluruh isi kotak, lalu salin. '
        'Tautan berlaku 7 hari, atau sampai sesi selesai maupun tautan dicabut.</p>'
        '<p class="bagikan-perhatian-st">Siapa pun yang memegang tautan dapat mengerjakan '
        'sesi ini tanpa masuk. Bagikan hanya kepada anak yang dituju, bukan di tempat umum.</p>'
        '</section>',
        ident=(pengguna, peran), stitch=True,
        kelas_bungkus="pendamping-editorial-st bagikan-editorial-st",
        id_utama="judul-bagikan",
    )


def halaman_konfirmasi_hapus(
    kon, sesi_id: int, pengguna: str = "", peran: str = "guru"
) -> bytes | None:
    """Halaman konfirmasi sebelum menghapus sesi (dua langkah, tanpa JS).

    Peringatannya menyebut angka NYATA sesi ini — berapa jawaban, diagnosis,
    dan foto yang ikut hilang. Tanpa angka, "hapus" terasa ringan; dengan
    angka, keputusannya sadar. Mengembalikan None bila sesi tidak ada.
    """
    info = kon.execute(
        """SELECT s.id, s.tanggal, s.level, s.topik, w.nama
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
        (sesi_id,),
    ).fetchone()
    if not info:
        return None

    def _hitung(sql: str) -> int:
        return kon.execute(sql, (sesi_id,)).fetchone()[0]

    n_jawaban = _hitung(
        """SELECT COUNT(*) FROM jawaban j
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?"""
    )
    n_diagnosis = _hitung(
        """SELECT COUNT(*) FROM diagnosis d
           JOIN jawaban j ON j.id = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?"""
    )
    n_foto = _hitung("SELECT COUNT(*) FROM lampiran WHERE sesi_id = ?")

    return _halaman(
        f"Hapus sesi #{sesi_id}?",
        f'<div class="jejak"><a href="/sesi/{sesi_id}">&larr; Batal, kembali ke sesi</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">PERIKSA SEBELUM MENGHAPUS</p>'
        f'<h1 id="judul-hapus">Hapus sesi #{sesi_id}?</h1></header>'
        f'<div class="kartu">'
        f'<p>Sesi <b>#{sesi_id}</b> milik <b>{html.escape(info["nama"])}</b> '
        f'&middot; {info["tanggal"]} &middot; {html.escape(label_kelas(_ambil(info, "level", LEVEL_BAWAAN)))} '
        f'&middot; {_ambil(info, "topik", TOPIK_BAWAAN)}</p>'
        f"<p>Yang ikut hilang bersama sesi ini:</p>"
        f"<ul><li><b>{n_jawaban} jawaban</b></li>"
        f"<li><b>{n_diagnosis} diagnosis</b></li>"
        f"<li><b>{n_foto} foto</b> lembar</li></ul>"
        f'<div class="pesan galat">Tindakan ini <b>tidak bisa dibatalkan</b>. '
        f"Riwayat diagnosis tidak bisa dibangun ulang.</div>"
        f'<form method="post" action="/sesi/{sesi_id}/hapus" '
        f'style="margin-top:.9rem;display:flex;gap:.6rem;align-items:center">'
        f'<input type="hidden" name="konfirmasi" value="1">'
        f'<button type="submit" class="tombol-hapus">Ya, hapus sesi ini</button>'
        f'<a href="/sesi/{sesi_id}">Batal</a>'
        f"</form></div>",
        ident=(pengguna, peran) if pengguna else None,
        stitch=True, kelas_bungkus="pendamping-editorial-st hapus-editorial-st",
        id_utama="judul-hapus",
    )

def _pil_sesi(kon, sesi_id: int, aktif: str) -> str:
    """Pil navigasi di halaman sesi: Koreksi · Cetak · Lampiran."""
    n_lamp = kon.execute(
        "SELECT COUNT(*) FROM lampiran WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()[0]
    def _a(kunci: str, label: str, href: str) -> str:
        cls = "pil aktif" if kunci == aktif else "pil"
        kini = ' aria-current="page"' if kunci == aktif else ''
        return f'<a class="{cls}" href="{href}"{kini}>{label}</a>'
    return (
        '<nav class="pil-sesi" aria-label="Alat sesi">'
        + _a("koreksi", "Koreksi", f"/sesi/{sesi_id}")
        + _a("cetak", "Cetak", f"/sesi/{sesi_id}/cetak")
        + _a("lampiran", f"Lampiran ({n_lamp})", f"/sesi/{sesi_id}/lampiran")
        + "</nav>"
    )


def halaman_sesi_cetak(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "",
) -> bytes | None:
    """Halaman cetak per sesi; perubahan cerita merupakan opsi tambahan."""
    info = kon.execute(
        """SELECT s.id, s.tanggal, s.seed, s.level, s.topik, s.mode,
                  w.nama, w.id AS siswa_id
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
        (sesi_id,),
    ).fetchone()
    if not info:
        return None
    badge_mode = _badge_mode(info)
    kabar = f'<div class="pesan">{html.escape(pesan)}</div>' if pesan else ""
    blok_cerita = _tombol_cerita(kon, sesi_id)
    pil = _pil_sesi(kon, sesi_id, "cetak")
    return _halaman(
        f"Sesi #{sesi_id} — Cetak",
        f'<div class="jejak"><a href="/anak/{info["siswa_id"]}">&larr; '
        f'Semua sesi {html.escape(info["nama"])}</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">CETAK</p>'
        f'<h1 id="judul-cetak">{html.escape(info["nama"])} — Sesi #{sesi_id}</h1></header>'
        f'<p class="sub">{info["tanggal"]} &middot; '
        f'{html.escape(label_kelas(_ambil(info, "level", LEVEL_BAWAAN)))} &middot; '
        f'{_ambil(info, "topik", TOPIK_BAWAAN)} &middot; '
        f'seed {info["seed"]} {badge_mode}</p>'
        f"{kabar}"
        f"{pil}"
        f'<div class="kartu cetak-pilihan-st"><h2>Siapkan lembar latihan</h2>'
        f'<p><a class="btn" href="/lembar/{sesi_id}" target="_blank">Lembar soal</a> '
        f'<a class="btn" href="/lembar/{sesi_id}/penilaian" target="_blank">Lembar kunci</a></p>'
        f'<p class="sub">Dibuka di tab baru — siap cetak. Lembar soal untuk anak; '
        f'lembar kunci untuk pendamping.</p></div>'
        f"{blok_cerita}",
        ident=(pengguna, peran) if pengguna else None,
        stitch=True, kelas_bungkus="pendamping-editorial-st cetak-editorial-st",
        id_utama="judul-cetak",
    )


def halaman_sesi_lampiran(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "",
) -> bytes | None:
    """Halaman lampiran foto per sesi — daftar + upload."""
    info = kon.execute(
        """SELECT s.id, s.tanggal, s.seed, s.level, s.topik, s.mode,
                  w.nama, w.id AS siswa_id
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
        (sesi_id,),
    ).fetchone()
    if not info:
        return None
    badge_mode = _badge_mode(info)
    kabar = f'<div class="pesan">{html.escape(pesan)}</div>' if pesan else ""
    baris_lampiran = []
    for lamp in database.daftar_lampiran(kon, sesi_id):
        status_cls = "benar" if lamp["status"] == "diterapkan" else "N"
        baris_lampiran.append(
            f'<li><a href="/lampiran/{lamp["id"]}">'
            f'{html.escape(lamp["nama_berkas"])}</a> '
            f'<span class="kode {status_cls}">{lamp["status"]}</span> '
            f'<span class="waktu">{html.escape(lamp["dibuat"])}</span></li>'
        )
    daftar = (
        f'<ul class="daftar-lampiran">{"".join(baris_lampiran)}</ul>'
        if baris_lampiran
        else '<p class="sub">Belum ada foto lembar.</p>'
    )
    unggah = (
        f'<form method="post" action="/lampiran/{sesi_id}" '
        'enctype="multipart/form-data">'
        + __import__('attachments').field_operasi_foto()
        + '<label for="foto-lembar">Foto lembar yang sudah diisi anak (jpeg/png, maks 8MB)</label>'
        '<input id="foto-lembar" type="file" name="foto" accept="image/jpeg,image/png">'
        '<button type="submit">Upload foto</button>'
        "</form>"
    )
    blok_lampiran = (
        '<div class="kartu blok-lampiran">'
        "<h2>Lampiran — foto lembar</h2>"
        f"{daftar}"
        f"{unggah}"
        "</div>"
    )
    pil = _pil_sesi(kon, sesi_id, "lampiran")
    return _halaman(
        f"Sesi #{sesi_id} — Lampiran",
        f'<div class="jejak"><a href="/anak/{info["siswa_id"]}">&larr; '
        f'Semua sesi {html.escape(info["nama"])}</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">ARSIP LEMBAR LATIHAN</p>'
        f'<h1 id="judul-lampiran">{html.escape(info["nama"])} — Sesi #{sesi_id}</h1></header>'
        f'<p class="sub">{info["tanggal"]} &middot; '
        f'{html.escape(label_kelas(_ambil(info, "level", LEVEL_BAWAAN)))} &middot; '
        f'{_ambil(info, "topik", TOPIK_BAWAAN)} &middot; '
        f'seed {info["seed"]} {badge_mode}</p>'
        f"{kabar}"
        f"{pil}"
        f"{blok_lampiran}",
        ident=(pengguna, peran) if pengguna else None,
        stitch=True, kelas_bungkus="pendamping-editorial-st lampiran-editorial-st",
        id_utama="judul-lampiran",
    )


def _pil_sesi_stitch(kon, sesi_id: int, aktif: str) -> str:
    """Pil navigasi sesi versi Stitch."""
    n_lamp = kon.execute(
        "SELECT COUNT(*) FROM lampiran WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()[0]
    def _a(kunci: str, label: str, href: str) -> str:
        cls = "aktif" if kunci == aktif else ""
        kini = ' aria-current="page"' if kunci == aktif else ''
        return f'<a class="{cls}" href="{href}"{kini}>{label}</a>'
    return (
        '<nav class="pil-sesi-st" aria-label="Alat sesi">'
        + _a("koreksi", "Koreksi", f"/sesi/{sesi_id}")
        + _a("cetak", "Cetak", f"/sesi/{sesi_id}/cetak")
        + _a("lampiran", f"Lampiran ({n_lamp})", f"/sesi/{sesi_id}/lampiran")
        + "</nav>"
    )


def _label_tahap_sesi(tujuan: str, *, riwayat: bool = False) -> str:
    """Label tahap ramah; sesi nonaktif ditandai sebagai riwayat."""
    label = {
        "pemetaan": "Pemetaan",
        "pengenalan": "Pelajari bersama",
        "latihan_terbimbing": "Latihan terbimbing",
        "penguatan": "Coba mandiri",
        "evaluasi": "Evaluasi setelah jeda",
        "checkpoint": "Cek kembali pemahaman",
        "maintenance": "Latihan campuran",
        "bebas": "Latihan pilihan sendiri",
    }.get(tujuan, "Sesi belajar")
    return f"Riwayat {label.lower()}" if riwayat else label


def halaman_sesi_stitch(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "", bantuan: str = "", bantuan_nomor: int | None = None,
    draf_koreksi=None,
    privat: bool = False,
    masalah_konfirmasi=(),
) -> bytes:
    """Detail sesi versi Stitch: pratinjau lalu koreksi setelah dikirim."""
    privat = privat or (peran == 'guru' and bool(pengguna))
    from style_stitch import gaya_stitch, CSS_SESI

    info = kon.execute(
        """SELECT s.id, s.tanggal, s.seed, s.level, s.topik, s.mode,
                  s.jenis, s.sumber_sesi_id,
                  s.mulai, s.selesai, s.direview, s.dikonfirmasi_guru,
                  s.fingerprint_konfirmasi,
                  s.tujuan, s.putaran_id, s.dibatalkan,
                  (SELECT COUNT(*) FROM sesi_soal ss
                   WHERE ss.sesi_id = s.id) AS jumlah_soal,
                  (SELECT COUNT(*) FROM sesi_soal ss
                   JOIN jawaban j ON j.sesi_soal_id = ss.id
                   WHERE ss.sesi_id = s.id) AS terisi,
                  w.nama, w.id AS siswa_id, w.tingkat AS level_aktif
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
        (sesi_id,),
    ).fetchone()
    if not info:
        return _halaman("Tidak ada", "<h1>Sesi tidak ditemukan</h1>")

    sudah_dikirim = bool(info["selesai"])
    drill = info["mode"] == "drill"
    sesi_dibatalkan = info["dibatalkan"] is not None
    sesi_terpandu = info["putaran_id"] is not None and info["tujuan"] != "bebas"
    from learning_cycle import OutcomeSiklus, _putaran_aktif, rencana_berikutnya
    import mapping_results
    bukti_siklus = database.muat_bukti_siklus(kon, int(info["siswa_id"]))
    putaran_aktif = _putaran_aktif(bukti_siklus)
    putaran_aktif_id = putaran_aktif.id if putaran_aktif is not None else None
    sesi_terpandu_aktif = (
        sesi_terpandu
        and int(info["putaran_id"]) == putaran_aktif_id
        and info["level"] == info["level_aktif"]
        and not sesi_dibatalkan
    )
    from skill_pilot_store import daftar_pilot
    sesi_pilot = sesi_id in daftar_pilot(kon, int(info['siswa_id']))[0]
    if sesi_pilot:
        sesi_terpandu_aktif = not sesi_dibatalkan
    sesi_terpandu_riwayat = sesi_terpandu and not sesi_terpandu_aktif
    tautan_aktif = (
        not sesi_dibatalkan
        and not sudah_dikirim
        and share_links.aktif(kon, sesi_id)
    )
    snapshot_terakhir = {}
    opt_in_pemetaan_aktif = False
    konfirmasi_masih_aktif = False
    konfirmasi_terakhir = kon.execute(
        """SELECT id, fingerprint FROM konfirmasi_hasil
           WHERE sesi_id = ? ORDER BY nomor_urut DESC, id DESC LIMIT 1""",
        (sesi_id,),
    ).fetchone()
    pernah_dikonfirmasi = konfirmasi_terakhir is not None
    if konfirmasi_terakhir is not None:
        snapshot_terakhir = {
            int(baris["sesi_soal_id"]): baris
            for baris in kon.execute(
                """SELECT sesi_soal_id, nomor, template_id, jawaban, benar,
                          kode_final, malrule_id, dilewati, cek_pemahaman
                   FROM snapshot_outcome WHERE konfirmasi_id = ?""",
                (konfirmasi_terakhir["id"],),
            ).fetchall()
        }
        konfirmasi_masih_aktif = (
            info["dikonfirmasi_guru"] is not None
            and info["fingerprint_konfirmasi"] == konfirmasi_terakhir["fingerprint"]
        )
        opt_in_pemetaan_aktif = konfirmasi_masih_aktif and kon.execute(
            """SELECT 1 FROM kejadian_belajar
               WHERE sesi_id = ? AND konfirmasi_id = ?
                 AND jenis = 'sertakan_pemetaan' LIMIT 1""",
            (sesi_id, konfirmasi_terakhir["id"]),
        ).fetchone() is not None
    pesan_masalah = {
        "provenance": "Periksa sumber koreksi dan versi tinjauan. Catatan asli tidak boleh ditimpa hasil bantuan; pengalaman anak perlu dipastikan guru. Jika tab lain sudah berubah, muat ulang sebelum menyimpan.",
        "kosong": "Belum ada jawaban atau cara yang bisa dinilai. Catat yang benar-benar dikerjakan anak; bila tidak dikerjakan, buka Lewati soal ini dari penilaian.",
        "penilaian": "Penilaian belum ditentukan. Tanyakan cara anak, lalu pilih penilaian yang sesuai. Jangan menebak penilaian hanya agar bisa lanjut.",
        "tidak_konsisten": "Penilaian tersimpan belum konsisten. Periksa jawaban dan cara anak, lalu pilih kembali penilaian yang sesuai.",
    }
    masalah_per_butir = {sid: pesan_masalah.get(alasan, alasan) for sid, _, alasan in masalah_konfirmasi}
    import review_store
    import review_pages
    from choice_store import daftar_pilihan
    from choice_pages import select_guru, ringkas_opsi, pertanyaan
    pilihan_pg = daftar_pilihan(kon, sesi_id)
    tinjauan_sesi = review_store.muat(kon, sesi_id)
    pengiriman_sesi = review_store.pengiriman(kon, sesi_id)
    ada_foto = kon.execute('SELECT 1 FROM lampiran WHERE sesi_id=? LIMIT 1', (sesi_id,)).fetchone() is not None
    from review_navigation import tindakan_tinjauan, render_progres
    kartu = []
    kartu_tercatat = []
    antrean_tinjauan = []
    outcome_tampilan = []
    for b in database.isi_sesi(kon, sesi_id):
        soal = _soal_dari_baris(b)
        sudah = b["jawaban_id"] is not None
        kode = b["kode_final"]
        benar = b["benar"]

        draf_butir = draf_koreksi.untuk(int(b["sesi_soal_id"])) if draf_koreksi else None
        jawaban_tampil = draf_butir.jawaban if draf_butir else (b["jawaban"] or "")
        pg_butir = pilihan_pg.get(b['sesi_soal_id'])
        teks_pertanyaan = pertanyaan(question_views.penyajian_dari_baris(b), pg_butir, b['template_id'], 'guru', str(b['nomor']))
        label_jawaban = next((o.label + ' — ' + o.teks for o in pg_butir.opsi if o.nilai == jawaban_tampil), jawaban_tampil) if pg_butir else jawaban_tampil
        input_jawaban = (select_guru(pg_butir, jawaban_tampil) if pg_butir else
                         f'<input type="text" class="koreksi-input-st" id="jwb-{b["sesi_soal_id"]}" name="jwb_{b["sesi_soal_id"]}"\n               value="{html.escape(jawaban_tampil)}">')
        kode_tampil = draf_butir.kode if draf_butir else pilihan_tersimpan(b)
        cara_tampil = cara_untuk_form(draf_butir.cara if draf_butir else b["cara"] or "")
        tinjauan_butir = tinjauan_sesi.get(int(b['sesi_soal_id']), {})
        sumber_asli, pertanyaan_tinjauan, kosong_asli = review_pages.sumber_html(
            pengiriman_sesi.get(int(b['sesi_soal_id'])), b, ada_foto,
        )
        belum_terpilih = (
            draf_butir.belum_pernah if draf_butir else bool(b["belum_pernah"])
        )
        cara_diagnosis = cara_dari_form(cara_tampil.strip(), b["cara"] or "")
        if drill:
            from students import AWALAN_DRILL
            cara_diagnosis = AWALAN_DRILL + cara_diagnosis
        if pg_butir:
            from choice_assessment import nilai_pilihan
            rekomendasi = nilai_pilihan(b['kunci'], jawaban_tampil)
        else:
            rekomendasi = diagnosa(
                b["kunci"], jawaban_tampil, cara_diagnosis, b["restatement"] or "",
                belum_terpilih, database.malrule_soal(kon, b["soal_id"]), soal.minta_restatement,
                soal=soal,
            )
        if (sudah and b["benar"] is not None and not b["manual"]
                and jawaban_tampil.strip() == (b["jawaban"] or "")
                and cara_dari_form(cara_tampil.strip(), b["cara"] or "") == (b["cara"] or "")
                and belum_terpilih == bool(b["belum_pernah"])):
            # Diagnosis warisan yang tak diedit tetap dipakai oleh jalur no-op.
            rekomendasi = Usulan(bool(benar), kode, b["malrule_id"], b["alasan"] or "", bool(benar or kode))
        # Status dan disclosure memakai penilaian efektif, bukan lencana DB
        # sebelum draf. Ini hanya presentasi; konfirmasi tetap menilai ulang.
        benar_tampil = kode_tampil == "benar" if kode_tampil else rekomendasi.benar
        kode_efektif = None if benar_tampil else (kode_tampil or rekomendasi.kode)
        kelas_isi = "sudah" if benar_tampil or kode_efektif else ""
        bulat_cls = "benar" if benar_tampil else (kode_efektif or "N")
        lencana = (
            '<span class="kode benar">BENAR</span>' if benar_tampil
            else f'<span class="kode {bulat_cls}">{kode_efektif or "?"}</span>'
        )
        bulat_label = "Tepat" if benar_tampil else {
            "K": "Salah konsep", "B": "Salah baca", "H": "Salah hitung",
            "E": "Salah tulis", "T": "Perlu pengenalan", "N": "Menebak",
        }.get(kode_efektif, "Belum dinilai")
        status = (
            f'<span class="koreksi-status-st {bulat_cls}">{lencana}'
            f'<span class="koreksi-status-label-st">{bulat_label}</span></span>'
        ) if sudah or draf_butir else ""
        label_usulan = label_penilaian("benar" if rekomendasi.benar else rekomendasi.kode)
        belum_dinilai = not rekomendasi.benar and not rekomendasi.kode
        judul_usulan = (
            "Jagomat belum dapat mengusulkan penilaian." if belum_dinilai else
            f"Usulan Jagomat: {label_usulan}"
        )
        usulan = (
            f'<div class="usulan-st"><b>{html.escape(judul_usulan)}</b>'
            f'<p class="koreksi-catatan-st"><b>Alasan:</b> {html.escape(rekomendasi.alasan)}</p>'
            '<p class="koreksi-catatan-st">Usulan berdasarkan isian saat halaman dimuat. '
            'Jika jawaban, cara, atau pengalaman diubah, Jagomat menilai ulang saat disimpan.</p></div>'
        )
        label_otomatis = (
            "Belum yakin — perlu ditinjau" if belum_dinilai else f"Otomatis — {label_usulan}"
        )
        pilihan_kode = [v for v, _ in KODE_PILIHAN if not (drill and v == "N")]
        if "T" not in pilihan_kode:
            pilihan_kode.append("T")  # Pengalaman anak saja tidak menentukan kode ini.
        pilih = "".join(
            f'<option value="{v}"{" selected" if v == kode_tampil else ""}>'
            f'{html.escape(label_otomatis if not v else dict(KODE_PILIHAN).get(v, "Perlu pengenalan").split(" — ")[-1].capitalize())}</option>'
            for v in pilihan_kode
        )

        masalah_butir = masalah_per_butir.get(int(b["sesi_soal_id"]))
        petunjuk_masalah = ""
        atribut_penilaian = ""
        sid = int(b["sesi_soal_id"])
        atribut_kartu = f' id="tinjau-soal-{sid}" tabindex="-1" aria-label="Soal {int(b["nomor"])}"'
        if masalah_butir:
            atribut_penilaian = f' aria-invalid="true" aria-describedby="masalah-soal-{sid}"'
            petunjuk_masalah = (
                f'<p class="koreksi-masalah-st" id="masalah-soal-{sid}">'
                f'<b>Perlu ditinjau.</b> {html.escape(masalah_butir)}</p>'
            )
            status = '<span class="koreksi-status-st">Perlu ditinjau</span>'
            kelas_isi = ""
            if not kode_tampil:
                pilih = pilih.replace(label_otomatis, "Belum yakin — perlu ditinjau")

        nomor = f'<span class="koreksi-nomor-st">{b["nomor"]}</span>'
        tipe = (
            f'<span class="koreksi-tipe-st">'
            f'{html.escape(_nama_template(b["template_id"]))}</span>'
        )

        pembahasan_html = ""
        if getattr(soal, "pembahasan", ""):
            pembahasan_html = (
                '<div class="pembahasan-soal-st">'
                f'<b>Perhitungan/Langkah:</b> {html.escape(soal.pembahasan)}'
                '</div>'
            )

        if not sudah_dikirim:
            kartu.append(f"""
<div class="koreksi-kartu-st pratinjau">
  <div class="koreksi-isi-st">
    <div class="koreksi-kepala-st">{nomor}{tipe}</div>
    <div class="teks-soal-st">{teks_pertanyaan}</div>
    {ringkas_opsi(pg_butir, b['template_id'])}
    <div class="kunci-baris-st">Kunci: <span class="kunci-val">{html.escape(b["kunci"])}</span></div>
  </div>
</div>""")
            continue

        cara_html = ""
        if not drill or pg_butir:
            cara_html = (
                f'<label class="koreksi-label-st" for="cara-{b["sesi_soal_id"]}">{"Catatan pekerjaan sebagian" if kosong_asli else "Bagaimana anak mendapatkan jawabannya?"}</label>'
                f'<textarea class="koreksi-textarea-st" id="cara-{b["sesi_soal_id"]}" name="cara_{b["sesi_soal_id"]}" '
                f'aria-describedby="cara-info-{b["sesi_soal_id"]}" placeholder="Catat penjelasan anak, jika ada.">'
                f'{html.escape(cara_tampil)}</textarea>'
                f'<p class="koreksi-catatan-st" id="cara-info-{b["sesi_soal_id"]}">'
                'Pilihan anak bukan penjelasan lengkap. Ganti catatan hanya setelah mendengar caranya; '
                'jangan isi dengan cara dari kunci.</p>'
            )

        snapshot_butir = snapshot_terakhir.get(int(b["sesi_soal_id"]))
        pemahaman_terpilih = (
            draf_butir.pemahaman if draf_butir else
            tinjauan_butir['pemahaman'] if tinjauan_butir else
            snapshot_butir["cek_pemahaman"] if snapshot_butir is not None else None
        )
        dilewati_terpilih = (
            draf_butir.dilewati if draf_butir else
            bool(tinjauan_butir['dilewati']) if tinjauan_butir else
            bool(snapshot_butir is not None and snapshot_butir["dilewati"])
        )
        # Persetujuan hanya untuk outcome yang cocok dengan snapshot aktif.
        # Draf/diagnosis mutable saja bukan bukti keputusan yang sudah disahkan.
        penilaian_disahkan = bool(
            konfirmasi_masih_aktif and not sesi_dibatalkan
            and draf_koreksi is None and not masalah_konfirmasi
            and snapshot_butir is not None and not dilewati_terpilih
            and not snapshot_butir["dilewati"]
            and snapshot_butir["nomor"] == b["nomor"]
            and snapshot_butir["template_id"] == b["template_id"]
            and snapshot_butir["jawaban"] == (b["jawaban"] or "")
            and snapshot_butir["benar"] == b["benar"]
            and snapshot_butir["kode_final"] == b["kode_final"]
            and snapshot_butir["malrule_id"] == b["malrule_id"]
        )
        sumber_penilaian = "Pilihan sendiri" if kode_tampil else "Usulan Jagomat"
        if sesi_dibatalkan:
            status_persetujuan = "Sesi dibatalkan · Penilaian tidak aktif."
        elif draf_koreksi is not None:
            status_persetujuan = "Belum disimpan · Periksa draf lalu konfirmasikan hasil sesi."
        elif dilewati_terpilih:
            status_persetujuan = "Dilewati dari penilaian · Bukan persetujuan atas usulan diagnosis."
        elif penilaian_disahkan:
            status_persetujuan = sumber_penilaian + (
                " · Ditetapkan saat konfirmasi sesi" if kode_tampil else
                " · Disetujui saat konfirmasi sesi"
            )
        else:
            status_persetujuan = (
                "Belum ada penilaian" if belum_dinilai and not kode_tampil else sumber_penilaian
            ) + " · Belum dikonfirmasi"
        penilaian_status = (
            f'<p class="koreksi-catatan-st" id="penilaian-status-{sid}">'
            f'<b>Penilaian saat halaman dimuat: {html.escape(label_penilaian("benar" if benar_tampil else kode_efektif))}</b>'
            f'<br>{html.escape(status_persetujuan)}</p>'
        )
        # Proyeksi pekerjaan bukan palang konfirmasi. Semua nilai form tetap
        # dikirim, termasuk saat kartu dilipat; server memvalidasi ulang.
        sumber_tampil = review_pages.nilai(tinjauan_butir, draf_butir, 'provenance')
        awal = pengiriman_sesi.get(sid)
        koreksi_jawaban = bool(awal and jawaban_tampil.strip() != awal['jawaban'].strip())
        koreksi_cara = bool(awal and cara_dari_form(cara_tampil.strip(), b['cara'] or '').strip() != awal['cara'].strip())
        sumber_perlu_diperiksa = (
            (benar_tampil and not jawaban_tampil.strip())
            or sumber_tampil == 'setelah_bantuan'
            or koreksi_jawaban and not (sumber_tampil == 'koreksi_transkripsi'
                and review_pages.nilai(tinjauan_butir, draf_butir, 'catatan_tinjauan').strip())
            or koreksi_cara and sumber_tampil not in {'penjelasan_asli', 'koreksi_transkripsi'}
        )
        tindakan = tindakan_tinjauan(
            benar=benar_tampil, kode=kode_efektif, pilihan=kode_tampil,
            pemahaman=pemahaman_terpilih, dilewati=dilewati_terpilih,
            masalah=bool(masalah_butir), sumber_perlu_diperiksa=sumber_perlu_diperiksa,
            terkonfirmasi=konfirmasi_masih_aktif and draf_butir is None,
        )
        if tindakan:
            antrean_tinjauan.append((sid, int(b['nomor'])))
        buka_kartu = bool(
            (tindakan and len(antrean_tinjauan) == 1) or masalah_butir
            or (sumber_perlu_diperiksa and not dilewati_terpilih)
            or bantuan_nomor == int(b['nomor'])
        )
        outcome_tampilan.append(OutcomeSiklus(
            b["template_id"], benar_tampil, kode_efektif,
            dilewati=dilewati_terpilih,
        ))
        pilihan_pemahaman = "".join(
            '<div class="koreksi-pilihan-paham-st">'
            f'<input type="radio" id="paham-{b["sesi_soal_id"]}-{nilai or "kosong"}" '
            f'name="cek_pemahaman_{b["sesi_soal_id"]}" value="{nilai}"'
            f'{" checked" if nilai == (pemahaman_terpilih or "") else ""}>'
            f'<label for="paham-{b["sesi_soal_id"]}-{nilai or "kosong"}">{label}</label></div>'
            for nilai, label in (
                ("", "Belum dicatat"),
                ("bisa_menjelaskan", "Bisa menjelaskan"),
                ("ragu", "Masih ragu"),
                ("menghafal", "Cenderung menghafal"),
            )
        )
        cek_penguasaan = info["tujuan"] in {"evaluasi", "checkpoint"}
        petunjuk_pemahaman = (
            '<p class="koreksi-catatan-st">Pada evaluasi dan cek kembali, '
            'catatan pemahaman pada soal fokus dipakai untuk menilai penguasaan. '
            'Jawaban benar saja belum cukup; catat setelah anak menjelaskan.</p>'
            if cek_penguasaan else ""
        )
        catatan = []
        label_pemahaman = {
            "bisa_menjelaskan": "Bisa menjelaskan", "ragu": "Masih ragu",
            "menghafal": "Cenderung menghafal",
        }
        if pemahaman_terpilih:
            catatan.append(label_pemahaman[pemahaman_terpilih])
        cara_asli = cara_dari_form(cara_tampil.strip(), b["cara"] or "")
        menebak = cara_asli.startswith("[pilihan] tebak")
        bingung = cara_asli.startswith("[pilihan] bingung")
        if menebak:
            catatan.append("Anak menandai menebak")
        if bingung:
            catatan.append("Anak menandai bingung")
        if belum_terpilih:
            catatan.append("Belum pernah melihat soal seperti ini")
        perlu_perhatian = (
            pemahaman_terpilih in {"ragu", "menghafal"}
            or menebak or bingung or belum_terpilih
        )
        ringkas = not (tindakan or cek_penguasaan or perlu_perhatian or masalah_butir or dilewati_terpilih)
        pengalaman_html = f"""
      <details class="koreksi-opsi-st koreksi-pengalaman-st"{" open" if belum_terpilih else ""}>
        <summary>{"Catatan pengalaman anak — tersimpan" if belum_terpilih else "Catatan pengalaman anak (opsional)"}</summary>
        <div class="koreksi-centang-st">
          <input type="hidden" name="hadir_belum_{sid}" value="1">
          <input type="checkbox" id="bp{sid}" name="belum_{sid}" value="1"
                 {"checked" if belum_terpilih else ""} aria-describedby="belum-info-{sid}">
          <label for="bp{sid}"><span class="info-anak-label-st">Dari anak:</span> Belum pernah melihat soal seperti ini</label>
        </div>
        <p class="koreksi-catatan-st" id="belum-info-{sid}">Centang hanya jika anak mengatakannya, bukan karena ia bingung. Ini catatan pengalaman anak, bukan keputusan pengenalan. Pilih Perlu pengenalan hanya setelah guru memastikannya.</p>
      </details>"""
        if cara_html:
            buka_cara = cek_penguasaan or perlu_perhatian or masalah_butir or dilewati_terpilih
            judul_cara = "Catatan cara anak" if cara_tampil.strip() else "Catat penjelasan anak (opsional)"
            cara_html = (
                f'<details class="koreksi-opsi-st koreksi-cara-st"{" open" if buka_cara else ""}>'
                f'<summary>{judul_cara}</summary>{cara_html}</details>'
            )
        pendampingan = f"""
    <fieldset class="koreksi-pemahaman-st">
      <legend>Tinjau bersama anak</legend>
      <p class="koreksi-tanya-st">Tanyakan: “{html.escape(pertanyaan_tinjauan)}”</p>
      {petunjuk_pemahaman}
      {"<details class='koreksi-opsi-st'><summary>Catat pemahaman bila sudah diamati</summary>" if kosong_asli else ""}
      <fieldset class="koreksi-radio-paham-st">
        <legend>Apakah anak bisa menjelaskan caranya?</legend>
        <div class="koreksi-pilihan-paham-grid-st">{pilihan_pemahaman}</div>
      </fieldset>
      {"</details>" if kosong_asli else ""}
      {cara_html}
    </fieldset>"""
        if benar_tampil:
            judul_catatan = (
                "Cek pemahaman" if cek_penguasaan else
                "Catatan pendampingan — perlu perhatian" if perlu_perhatian else
                "Periksa cara anak" if tindakan else "Catatan pendampingan (opsional)"
            )
            if cara_tampil.strip() or catatan:
                catatan.append("catatan belum disimpan" if draf_butir else "catatan tersimpan")
            ringkasan_catatan = (
                '<span class="koreksi-ringkasan-catatan-st">'
                + html.escape(" · ".join(catatan)) + '</span>' if catatan else ""
            )
            pendampingan = (
                f'<details class="koreksi-opsi-st koreksi-pendampingan-st"{"" if ringkas else " open"}>'
                f'<summary>{judul_catatan}{ringkasan_catatan}</summary>'
                f'<div class="koreksi-pendampingan-isi-st">{pendampingan}</div></details>'
            )
        judul_penilaian = (
            "Tentukan penilaian — belum dipilih" if belum_dinilai and not kode_tampil else
            "Penilaian saat halaman dimuat: " + label_penilaian("benar" if benar_tampil else kode_efektif) + " — ubah"
        )
        ringkasan_hasil = 'Dilewati dari penilaian' if dilewati_terpilih else (
            'Jawaban tepat' if benar_tampil else bulat_label
        )
        sinyal = [teks for teks in catatan if not teks.startswith('catatan ')]
        if sinyal and not dilewati_terpilih:
            ringkasan_hasil += ' · ' + ' · '.join(sinyal)
        label_tindakan = tindakan or 'Tinjauan tercatat'
        buka_sumber = bool(masalah_butir or sumber_perlu_diperiksa or koreksi_jawaban
                           or draf_butir and jawaban_tampil != (b['jawaban'] or ''))
        buka_lanjutan = bool(masalah_butir or sumber_perlu_diperiksa or dilewati_terpilih
                             or not benar_tampil and not kode_efektif
                             or belum_terpilih
                             or kode_efektif == 'T' and not kode_tampil)
        kontrol_tinjauan = review_pages.kontrol(
            kon, sid, tinjauan_butir, draf_butir,
            perlu_sumber=bool(sumber_perlu_diperiksa or masalah_butir),
        )
        petunjuk_penilaian = (
            '<p class="koreksi-catatan-st">Sesi dibatalkan; penilaian ini hanya untuk melihat riwayat.</p>'
            if sesi_dibatalkan else
            '<p class="koreksi-catatan-st">Pilihan dropdown baru disimpan setelah menekan Simpan draf atau Konfirmasi hasil sesi. '
            'Ringkasan di atas belum mengikuti perubahan yang belum disimpan.</p>'
            '<p class="koreksi-catatan-st">Setuju dengan usulan? Anda tidak perlu mengganti dropdown. '
            'Konfirmasi hasil sesi berarti menyetujui penilaian, termasuk usulan Jagomat yang dipakai. '
            'Simpan draf belum mengesahkan hasil.</p>'
        )
        kartu_html = f"""
<details class="koreksi-kartu-st koreksi-lipat-st"{atribut_kartu} data-tindakan="{html.escape(label_tindakan)}"{' open' if buka_kartu else ''}>
  <summary class="koreksi-ringkas-st">
    <span class="koreksi-ringkas-kepala-st">{nomor}{tipe}<span class="koreksi-tindakan-st">{html.escape(label_tindakan)}</span></span>
    <span class="koreksi-ringkas-hasil-st">{html.escape(ringkasan_hasil)}</span>
  </summary>
  <div class="koreksi-isi-st {kelas_isi}">
    <div class="koreksi-kepala-st">{status}</div>
    {penilaian_status}
    {petunjuk_masalah}
    <div class="teks-soal-st">{teks_pertanyaan}</div>
    {ringkas_opsi(pg_butir, b['template_id'])}
    {'<p>Pilihan ganda · latihan manual, bukan bukti penguasaan.</p>' if pg_butir else ''}
    {review_pages.jawaban_utama(label_jawaban, dikoreksi=koreksi_jawaban)}
    <details class="koreksi-opsi-st"><summary>Lihat kunci &amp; pembahasan</summary>
      <div class="kunci-baris-st">Kunci: <span class="kunci-val">{html.escape(b["kunci"])}</span></div>
      {pembahasan_html}
    </details>
    <details class="koreksi-opsi-st koreksi-sumber-st"{' open' if buka_sumber else ''}>
    <summary>Sumber &amp; koreksi salinan</summary>
    {sumber_asli}
    <div class="koreksi-bukti-st koreksi-bukti-tunggal-st">
      <div>
        <label class="koreksi-label-st" for="jwb-{b["sesi_soal_id"]}">Jawaban anak (koreksi salinan bila perlu)</label>
        {input_jawaban}
      </div>
    </div>
    </details>
    {pendampingan}
    <details class="koreksi-opsi-st koreksi-lanjutan-st"{' open' if buka_lanjutan else ''}>
    <summary>Catatan &amp; penilaian lanjutan</summary>
    {pengalaman_html}
    {kontrol_tinjauan}
    <details class="koreksi-opsi-st koreksi-penilaian-st"{" open" if buka_lanjutan else ""}>
      <summary>{judul_penilaian}</summary>
      {usulan}
      <label class="koreksi-label-st" for="kode-{b["sesi_soal_id"]}">Penilaian yang dipakai saat disimpan</label>
      <select class="koreksi-select-st" id="kode-{b["sesi_soal_id"]}" name="kode_{b["sesi_soal_id"]}"{atribut_penilaian}>{pilih}</select>
      {petunjuk_penilaian}
      <p class="koreksi-catatan-st">Belum yakin? Tinjau cara anak; jangan menebak penilaian agar bisa lanjut.</p>
      <details class="koreksi-opsi-st koreksi-alasan-st">
        <summary>Panduan memilih penilaian</summary>
        <ul class="koreksi-catatan-st">
          <li><b>Salah baca:</b> anak memahami pertanyaan berbeda dari yang dimaksud.</li>
          <li><b>Salah konsep:</b> ada pemahaman konsep yang keliru dalam cara anak.</li>
          <li><b>Salah hitung:</b> langkah sesuai, tetapi hitungannya keliru.</li>
          <li><b>Salah tulis akhir:</b> hasil pengerjaan berbeda dari jawaban yang ditulis.</li>
          {"" if drill else "<li><b>Menebak:</b> periksa cara anak, bukan hanya jawaban akhirnya.</li>"}
        </ul>
        <p class="koreksi-catatan-st">Otomatis memakai usulan Jagomat; pilihan lain menetapkan penilaian sendiri.</p>
      </details>
    </details>
    <details class="koreksi-opsi-st koreksi-perbaikan-st">
      <summary>{"Dilewati dari penilaian — ubah" if dilewati_terpilih else "Lewati soal ini dari penilaian"}</summary>
      <div class="koreksi-centang-st">
        <input type="hidden" name="hadir_dilewati_{b["sesi_soal_id"]}" value="1">
        <input type="checkbox" id="lewati-{b["sesi_soal_id"]}"
             name="dilewati_{b["sesi_soal_id"]}" value="1"
             {"checked" if dilewati_terpilih else ""} aria-describedby="lewati-info-{b["sesi_soal_id"]}">
        <label for="lewati-{b["sesi_soal_id"]}">Jangan sertakan soal ini dalam penilaian</label>
      </div>
      <p class="koreksi-catatan-st" id="lewati-info-{b["sesi_soal_id"]}">Saat dikonfirmasi, soal dicatat sebagai dilewati, bukan benar atau salah, dan bukan bukti pemahaman. Jawaban dan catatan asli tetap tersimpan.</p>
    </details>
    </details>
  </div>
</details>"""
        (kartu if tindakan or buka_kartu else kartu_tercatat).append(kartu_html)

    kabar = f'<div class="pesan-st" role="status">{html.escape(pesan)}</div>' if pesan else ""
    if masalah_konfirmasi:
        tautan_masalah = "".join(
            f'<li><a href="#tinjau-soal-{sid}">Tinjau soal {nomor}</a></li>'
            for sid, nomor, _ in masalah_konfirmasi
        )
        kabar += (
            '<section class="koreksi-galat-st" role="alert" aria-labelledby="judul-galat">'
            f'<h2 id="judul-galat">Ada {len(masalah_konfirmasi)} soal yang perlu ditinjau</h2>'
            '<p>Isian Anda tetap ditampilkan di bawah, tetapi perubahan ini <b>belum disimpan</b>. '
            'Tinjau soal berikut, lalu konfirmasikan kembali.</p>'
            f'<ul>{tautan_masalah}</ul></section>'
        )
    badge_mode = _badge_mode(info)
    badge_remedial = (
        '<span class="st-badge latihan">Remedial</span>'
        if info["jenis"] == "remedial" else ""
    )
    pil = _pil_sesi_stitch(kon, sesi_id, "koreksi")
    konteks_pendamping = ""
    if peran == "guru" and pengguna:
        import assistant_components
        import assistant_inline
        target_sesi = assistant_inline.tujuan_sesi(sesi_id)
        status_akses = __import__("assistant_entitlement_runtime").status_pengguna(pengguna)
        if sudah_dikirim and not sesi_dibatalkan:
            # Satu entry konsisten; pilihan soal tetap dilakukan di dalam panel,
            # bukan lewat sederet tombol yang bersaing dengan koreksi.
            konteks_pendamping = assistant_components.tombol_buka(
                target_sesi, form_id=f"form-koreksi-{sesi_id}", label="Pendamping",
                status_akses=status_akses,
            )
        else:
            konteks_pendamping = assistant_components.tombol_buka(
                target_sesi, status_akses=status_akses,
            )
    if not sudah_dikirim:
        pil = pil.replace(">Koreksi</a>", ">Soal &amp; kunci</a>")

    blok_remedial = ""
    blok_latihan_serupa = ""
    if sudah_dikirim and info["direview"] and not sesi_pilot:
        sasaran_sesi = database.sasaran_remedial_sesi(
            kon, int(info["siswa_id"]), sesi_id
        )
        blok_remedial = _form_remedial(
            sasaran_sesi,
            int(info["siswa_id"]),
            judul="Perbaiki kesalahan dari sesi ini",
            penjelasan=(
                "Pilih tipe soal yang ingin diulang. Soal baru memakai angka "
                "berbeda, tetapi melatih hal yang sama."
            ),
            sumber_sesi_id=sesi_id,
        )
    if sudah_dikirim and not sesi_pilot:
        blok_latihan_serupa = _blok_latihan_serupa(kon, sesi_id)

    if sudah_dikirim:
        sudah_dikonfirmasi = konfirmasi_masih_aktif
        status_sesi = (
            '<div class="status-sesi-st selesai">'
            '<span class="material-symbols-outlined">cancel</span>'
            '<div><b>Sesi dibatalkan</b>'
            '<p>Sesi dibatalkan. Riwayat tetap tersimpan dan hasilnya tidak aktif dalam rencana.</p>'
            '</div></div>'
            if sesi_dibatalkan
            else (
                '<div class="status-sesi-st selesai">'
                '<span class="material-symbols-outlined">task_alt</span>'
                '<div><b>Hasil sudah dikonfirmasi</b>'
                '<p>Snapshot hasil ini sudah menjadi bukti perjalanan belajar.</p>'
                '</div></div>'
                if sudah_dikonfirmasi
                else (
                    '<div class="status-sesi-st koreksi-pengantar-st">'
                    f'<div><b>{"Koreksi berubah — konfirmasi ulang diperlukan" if pernah_dikonfirmasi else "Tinjau bersama anak"}</b>'
                    '<p>Periksa jawaban dan dengarkan cara anak sebelum mengonfirmasi hasil sesi.</p>'
                    '</div></div>'
                )
            )
        )
        if masalah_konfirmasi:
            catatan_lama = " Hasil sebelumnya tetap tersimpan." if konfirmasi_masih_aktif else ""
            status_sesi = (
                '<div class="status-sesi-st"><div><b>Konfirmasi perubahan belum berhasil</b>'
                f'<p>Yang ditampilkan adalah isian untuk ditinjau, bukan hasil baru yang sah.{catatan_lama}</p>'
                '</div></div>'
            )
        opsi_pemetaan = ""
        if (
            not sesi_dibatalkan
            and info["mode"] == "diagnostik"
            and not pilihan_pg
            and info["tujuan"] == "bebas"
        ):
            pilihan_pemetaan_draf = draf_koreksi.sertakan_pemetaan if draf_koreksi else opt_in_pemetaan_aktif
            centang_pemetaan = " checked" if pilihan_pemetaan_draf else ""
            status_pemetaan = (
                '<span class="sub">Aktif — hasil terkonfirmasi ini ikut pemetaan.</span>'
                if opt_in_pemetaan_aktif
                else '<span class="sub">Opsional — hanya berlaku untuk konfirmasi ini.</span>'
            )
            if draf_koreksi:
                status_pemetaan = '<span class="sub">Pilihan ini belum disimpan; berlaku setelah konfirmasi berhasil.</span>'
            opsi_pemetaan = (
                '<label class="koreksi-centang-st">'
                f'<input type="checkbox" name="sertakan_pemetaan" value="1"{centang_pemetaan}> '
                'Sertakan dalam pemetaan</label>'
                f'{status_pemetaan}'
            )
        aksi_konfirmasi = ""
        if not sesi_dibatalkan:
            label_konfirmasi = "Konfirmasi ulang hasil sesi" if pernah_dikonfirmasi else "Konfirmasi hasil sesi"
            aksi_konfirmasi = (
                f'<button type="submit" formaction="/sesi/{sesi_id}/konfirmasi">'
                f'{label_konfirmasi}</button>'
            )
        kumpulan_kartu = ''.join(kartu)
        if kartu_tercatat:
            kumpulan_kartu += (
                '<details class="koreksi-opsi-st koreksi-tercatat-st">'
                f'<summary>{len(kartu_tercatat)} soal dengan tinjauan tercatat</summary>'
                '<p class="koreksi-catatan-st">Termasuk jawaban belum tepat yang sudah diperiksa. '
                'Buka kembali bila perlu mengoreksi.</p>'
                + ''.join(kartu_tercatat) + '</details>'
            )
        if sesi_dibatalkan:
            blok_isi = kumpulan_kartu
        else:
            # Submit default disabled memblokir implicit Enter secara native.
            # Hanya tombol konfirmasi yang dipilih eksplisit mengesahkan bukti.
            urutan_aksi = (
                '<p class="koreksi-catatan-st">Berlaku untuk seluruh sesi. '
                'Simpan draf untuk melanjutkan nanti, tanpa mengesahkan hasil.</p>'
                '<div class="koreksi-aksi-sesi-st">'
                f'<button type="submit" class="sekunder" formaction="/sesi/{sesi_id}/tinjauan">Simpan draf</button>'
                f'{aksi_konfirmasi}</div>'
                '<p class="koreksi-catatan-st">Konfirmasi menyimpan semua isian dan mengesahkan hasil sesi. '
                'Anda juga menyetujui usulan Jagomat yang tetap dipilih; tidak perlu mengganti dropdown. '
                'Isian yang belum lengkap akan ditandai.</p>'
            )
            from review_navigation import render_antrean
            navigasi_tinjauan = (
                render_antrean(antrean_tinjauan, draf=draf_koreksi is not None)
                if not masalah_konfirmasi and (not konfirmasi_masih_aktif or draf_koreksi is not None)
                else ''
            )
            form_hasil = (
                f'<form id="form-koreksi-{sesi_id}" method="post" action="/sesi/{sesi_id}">'
                f'{navigasi_tinjauan}{kumpulan_kartu}<input type="hidden" name="hadir_sertakan_pemetaan" value="1">{opsi_pemetaan}'
                f'<div class="koreksi-simpan-st">{urutan_aksi}</div></form>'
            )
            blok_isi = (
                '<details class="panduan-edit-hasil-st">'
                '<summary>Koreksi hasil — perlu konfirmasi ulang bila diubah</summary>'
                '<p class="sub">Hasil saat ini sudah sah. Jika koreksi diubah, '
                'periksa kembali lalu konfirmasikan ulang.</p>'
                f'{form_hasil}</details>'
                if konfirmasi_masih_aktif and not masalah_konfirmasi else form_hasil
            )
    else:
        sudah_mulai = bool(info["mulai"] or info["terisi"])
        if sesi_dibatalkan:
            status_sesi = (
                '<div class="status-sesi-st selesai">'
                '<span class="material-symbols-outlined">cancel</span>'
                '<div><b>Sesi dibatalkan</b>'
                '<p>Sesi dibatalkan. Riwayat tetap tersimpan dan hasilnya tidak aktif dalam rencana.</p>'
                '</div></div>'
            )
            blok_isi = "".join(kartu)
        elif sesi_terpandu_riwayat:
            keterangan_riwayat = (
                "Sesi level lama ini tidak mengubah rencana level aktif."
                if info["level"] != info["level_aktif"] else
                "Sesi ini tersimpan sebagai riwayat dan tidak mengubah rencana level aktif."
            )
            status_sesi = (
                '<div class="status-sesi-st">'
                '<span class="material-symbols-outlined">history</span>'
                '<div><b>Riwayat sesi terpandu</b>'
                f'<p>{keterangan_riwayat}</p></div></div>'
            )
            blok_isi = (
                '<details class="panduan-pratinjau-st">'
                '<summary>Pratinjau soal &amp; kunci untuk guru</summary>'
                f'{"".join(kartu)}</details>'
            )
        else:
            label_status = (
                "Sedang dikerjakan · giliran anak"
                if sudah_mulai else
                "Sesi siap — berikut cara anak mengerjakan"
            )
            ikon_status = (
                '<svg class="ikon-status-sesi-st" viewBox="0 0 24 24" '
                'fill="none" stroke="currentColor" stroke-width="1.8" '
                'stroke-linecap="round" stroke-linejoin="round" '
                'aria-hidden="true" focusable="false">'
                '<circle cx="12" cy="12" r="8.5"/>'
                '<path d="M12 7.5V12l3 2"/></svg>'
                if sudah_mulai else
                '<svg class="ikon-status-sesi-st" viewBox="0 0 24 24" '
                'fill="none" stroke="currentColor" stroke-width="1.8" '
                'stroke-linecap="round" stroke-linejoin="round" '
                'aria-hidden="true" focusable="false">'
                '<path d="M4 12 20 4l-5 16-3-6-8-2Z"/>'
                '<path d="m12 14 4-6"/></svg>'
            )
            penjelasan_status = (
                f'Terisi {info["terisi"]} dari {info["jumlah_soal"]}. '
                'Tunggu anak menekan “Selesai &amp; kirim” sebelum meninjau.'
                if sudah_mulai else
                'Bagikan tautan sesi, lalu biarkan anak mencoba dengan caranya sendiri.'
            )
            label_bagikan = (
                "Buat dan salin tautan baru" if tautan_aktif else
                "Salin tautan sesi"
            )
            kelas_aksi = (
                "panduan-aksi-sekunder-st" if sudah_mulai else
                "panduan-aksi-utama-st"
            )
            marker_status_lama = (
                "" if sudah_mulai else
                '<span class="marker-status-lama-st">Menunggu anak</span>'
            )
            status_sesi = (
                '<section class="status-sesi-st panduan-sesi-st">'
                f'{ikon_status}'
                f'<div><b>{label_status}</b>{marker_status_lama}'
                f'<p>{penjelasan_status}</p>'
                '<div class="blok-bagikan-st">'
                f'<form class="{kelas_aksi}" method="post" '
                f'action="/sesi/{sesi_id}/bagikan" data-bagikan-sesi '
                f'data-bagikan-aktif="{1 if tautan_aktif else 0}">'
                f'<button type="submit"><span data-label-bagikan>{label_bagikan}</span>'
                '</button></form>'
                '<span class="kabar-bagikan-st" role="status" aria-live="polite"></span>'
                '</div></div></section>'
            )
            blok_isi = (
                '<details class="panduan-pratinjau-st">'
                '<summary>Pratinjau soal &amp; kunci untuk guru</summary>'
                '<p class="sub">Bagian ini untuk pendamping, bukan halaman yang dibagikan kepada anak.</p>'
                f'{"".join(kartu)}</details>'
            )

    sesi_manual_berbukti = pernah_dikonfirmasi and not sesi_dibatalkan
    if sesi_dibatalkan:
        tombol_hapus = ""
        keterangan_bahaya = (
            "Sesi ini sudah dibatalkan. Histori dan bukti tetap tersimpan."
        )
    elif sesi_terpandu or sesi_manual_berbukti:
        tombol_hapus = (
            f'<form method="post" action="/sesi/{sesi_id}/batalkan" '
            'class="form-pembatalan-st" '
            'onsubmit="return confirm(\'Batalkan sesi ini? Sesi dan bukti tetap '
            'tersimpan dalam histori, tetapi tidak lagi aktif dalam siklus belajar.\')">'
            '<label for="alasan-batal">Alasan pembatalan <span>(opsional)</span></label>'
            '<input id="alasan-batal" type="text" name="alasan" maxlength="300" '
            'placeholder="Tulis alasan">'
            '<button type="submit" class="tombol-kecil-st">'
            'Batalkan sesi</button></form>'
        )
        keterangan_bahaya = "Pembatalan menjaga histori dan bukti sesi."
    else:
        tombol_hapus = (
            f'<form method="get" action="/sesi/{sesi_id}/hapus" '
            f'style="margin:.4rem 0">'
            f'<button type="submit" class="tombol-kecil-st">'
            f"Hapus sesi</button></form>"
        )
        keterangan_bahaya = "Zona bahaya — hapus tidak bisa dibatalkan."

    tahap_ramah = _label_tahap_sesi(
        info["tujuan"], riwayat=sesi_terpandu_riwayat
    )
    if sesi_dibatalkan or sesi_terpandu_riwayat:
        orientasi_peran = "tidak aktif"
    elif sudah_dikirim:
        orientasi_peran = "hasil sah" if konfirmasi_masih_aktif and not masalah_konfirmasi else "giliran orang tua/guru"
    elif info["mulai"] or info["terisi"]:
        orientasi_peran = "giliran anak"
    else:
        orientasi_peran = "giliran orang tua/guru"
    hasil_pemetaan = ""
    rencana_pemetaan = ""
    pemetaan_aktif = mapping_results.sesi_pemetaan_aktif(bukti_siklus, sesi_id)
    if pemetaan_aktif is not None:
        if konfirmasi_masih_aktif and not masalah_konfirmasi:
            hasil_pemetaan = mapping_results.render_hasil(bukti_siklus, sesi_id)
            if hasil_pemetaan:
                from learning_cycle_ui import render_rencana
                rencana_pemetaan = render_rencana(
                    rencana_berikutnya(bukti_siklus, int(info["siswa_id"])),
                    bukti_siklus, int(info["siswa_id"]),
                )
        else:
            hasil_pemetaan = (
                '<details class="koreksi-opsi-st koreksi-ringkasan-sesi-st">'
                '<summary>Ringkasan jawaban &amp; cara penilaian</summary>'
                + mapping_results.render_sementara(
                    outcome_tampilan, draf_gagal=bool(masalah_konfirmasi),
                ) + '</details>'
            )
    if hasil_pemetaan:
        label_tab = "Hasil pemetaan" if rencana_pemetaan else "Ringkasan &amp; tinjauan"
        pil = pil.replace(">Koreksi</a>", f">{label_tab}</a>")
    tautan_profil = f'/anak/{info["siswa_id"]}' + ('?section=rencana' if sesi_pilot else '')
    aksi_rencana = (
        f'<a class="panduan-rencana-st" href="{tautan_profil}">Lihat rencana berikutnya</a>'
        if konfirmasi_masih_aktif and not sesi_dibatalkan and not masalah_konfirmasi
        and not rencana_pemetaan else ""
    )
    jejak = (
        "" if aksi_rencana else
        f'<div class="sesi-jejak-st"><a href="{tautan_profil}">&larr; '
        f'Semua sesi {html.escape(info["nama"])}</a></div>'
    )

    batang = _topbar_stitch(pengguna, peran) if pengguna else ""
    aksi_bahaya_tampil = (
        '<p class="sub">Tutup bantuan untuk membuka aksi pembatalan atau hapus.</p>'
        if bantuan else tombol_hapus
    )
    if privat and not bantuan and "onsubmit=" in aksi_bahaya_tampil:
        # Fallback native tanpa inline handler: konsekuensi terlihat dan checkbox
        # required mencegah submit tak sengaja. Handler ownership tetap otoritatif.
        aksi_bahaya_tampil = (
            f'<form method="post" action="/sesi/{sesi_id}/batalkan" class="form-pembatalan-st">'
            '<p class="sub">Sesi dan bukti tetap tersimpan dalam histori, tetapi tidak lagi aktif dalam siklus belajar.</p>'
            '<label for="alasan-batal">Alasan pembatalan <span>(opsional)</span></label>'
            '<input id="alasan-batal" type="text" name="alasan" maxlength="300" placeholder="Tulis alasan">'
            '<label class="koreksi-centang-st"><input type="checkbox" required> '
            'Saya memahami sesi ini akan dibatalkan.</label>'
            '<button type="submit" class="tombol-kecil-st">Batalkan sesi</button></form>'
        )
    alat_lanjutan = (
        '<details class="koreksi-opsi-st"><summary>Atur latihan lanjutan sendiri</summary>'
        f'{blok_latihan_serupa}{blok_remedial}</details>'
        if blok_latihan_serupa or blok_remedial else ""
    )
    palang_enter = (
        f'<button type="submit" form="form-koreksi-{sesi_id}" hidden disabled aria-hidden="true"></button>'
        if sudah_dikirim and not sesi_dibatalkan else ""
    )
    progres_tinjauan = (
        render_progres(len(outcome_tampilan), len(outcome_tampilan) - len(antrean_tinjauan),
                       draf=draf_koreksi is not None)
        if sudah_dikirim and not sesi_dibatalkan and not konfirmasi_masih_aktif else ''
    )
    isi = (
        f'<main class="sesi-badan-st" aria-labelledby="judul-koreksi">'
        f'{jejak}'
        f'<header class="editorial-kepala-st"><p class="editorial-alis-st">{html.escape(tahap_ramah)} · {orientasi_peran}</p>'
        f'<h1 class="sesi-judul-st" id="judul-koreksi">{html.escape(info["nama"])} — Sesi #{sesi_id}</h1>'
        f'<p class="sesi-sub-st">{_tanggal_ringkas(info["tanggal"])} &middot; '
        f'{html.escape(label_kelas(_ambil(info, "level", LEVEL_BAWAAN)))} &middot; '
        f'{int(info["jumlah_soal"])} soal {badge_mode} {badge_remedial}</p></header>'
        f"{kabar}"
        f"{palang_enter}{pil}{konteks_pendamping}"
        f"{status_sesi}{progres_tinjauan}"
        f"{hasil_pemetaan}{rencana_pemetaan}"
        + (__import__('skill_pilot_ui').materi_sesi(kon,sesi_id,int(info['siswa_id'])) if sesi_pilot else '') +
        f"{aksi_rencana}"
        f"{blok_isi}"
        f"{alat_lanjutan}"
        f'<div class="danger-zone-st">'
        f'<p class="sub">{keterangan_bahaya}</p>'
        f'{aksi_bahaya_tampil}</div>'
        f"</main>"
        + (__import__("assistant_components").hubungkan_form(
            bantuan, f"form-koreksi-{sesi_id}",
        ) if bantuan else "")
    )
    skrip_extra = "" if (bantuan or privat) else (
        f"<script>{SKRIP_MATA_SANDI}</script>"
        f"<script>{SKRIP_CEGAH_KIRIM_GANDA}</script>"
    )
    gaya_sesi = gaya_stitch()
    if bantuan or privat:
        gaya_sesi = gaya_sesi.replace(
            "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
            "",
        )
    return (
        f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(f"Sesi #{sesi_id}"))}</title>
{brand.tag_kepala(cetak=bool(bantuan or privat))}
{'' if (bantuan or privat) else '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">'}
<style>{gaya_sesi}{CSS_SESI}{mapping_results.GAYA_HASIL if hasil_pemetaan else ''}</style></head>
<body class="st"><div class="bungkus-st pendamping-editorial-st koreksi-editorial-st">{batang}{isi}</div>{skrip_extra}</body></html>"""
    ).encode()


def simpan_sesi(kon, sesi_id: int, data: dict, *, tinjauan_disimpan: bool = False, guru: str = 'guru') -> str:
    """Simpan koreksi guru tanpa menimpa arsip dan provenance pekerjaan asli."""
    if not tinjauan_disimpan:
        import review_store
        kon.execute('SAVEPOINT koreksi_lokal')
        try:
            review_store.simpan(kon, sesi_id, data, guru)
            hasil = simpan_sesi(kon, sesi_id, data, tinjauan_disimpan=True, guru=guru)
            kon.execute('RELEASE SAVEPOINT koreksi_lokal')
            return hasil
        except Exception:
            kon.execute('ROLLBACK TO SAVEPOINT koreksi_lokal')
            kon.execute('RELEASE SAVEPOINT koreksi_lokal')
            raise
    mode_baris = kon.execute(
        "SELECT mode FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    drill = bool(mode_baris and mode_baris["mode"] == "drill")
    awalan_drill = ""
    if drill:
        from students import AWALAN_DRILL
        awalan_drill = AWALAN_DRILL

    diubah = 0
    for b in database.isi_sesi(kon, sesi_id):
        sid = b["sesi_soal_id"]
        if not any(nama in data for nama in (f'jwb_{sid}', f'cara_{sid}', f'kode_{sid}', f'belum_{sid}')):
            continue
        jwb = data.get(f"jwb_{sid}", b['jawaban'] or "").strip()
        cara = cara_dari_form(data.get(f"cara_{sid}", b['cara'] or "").strip(), b["cara"] or "")
        restate = b["restatement"] or ""
        belum = f"belum_{sid}" in data if f'jwb_{sid}' in data else bool(b['belum_pernah']) or f'belum_{sid}' in data
        pilihan = data.get(f"kode_{sid}", pilihan_tersimpan(b)).strip()
        kode_diizinkan = {nilai for nilai, _label in KODE_PILIHAN if nilai}
        kode_diizinkan.add("T")  # Keputusan pengenalan eksplisit oleh guru.
        if drill:
            kode_diizinkan.discard("N")
        if pilihan not in kode_diizinkan:
            pilihan = ""

        if not (jwb or cara or restate or belum or pilihan):
            if b["jawaban_id"] is None or f"jwb_{sid}" not in data:
                continue
        kode_lama = pilihan_tersimpan(b)
        if (b["jawaban_id"] is not None and b["benar"] is not None
                and jwb == (b["jawaban"] or "")
                and cara == (b["cara"] or "")
                and belum == bool(b["belum_pernah"]) and pilihan == kode_lama):
            continue

        jid = database.simpan_jawaban(kon, sid, jwb, cara, restate, belum)

        cara_diagnosis = awalan_drill + cara if drill else cara
        soal = _soal_dari_baris(b)
        from choice_store import format_sesi
        if format_sesi(kon, sesi_id) == 'pilihan_ganda':
            from choice_assessment import nilai_pilihan
            u = nilai_pilihan(b['kunci'], jwb)
        else:
            u = diagnosa(
                b["kunci"], jwb, cara_diagnosis, restate, belum,
                database.malrule_soal(kon, b["soal_id"]),
                soal.minta_restatement, soal=soal,
            )

        if pilihan == "benar":
            benar, final, manual = True, None, True
        elif pilihan:
            benar, final, manual = False, pilihan, True
        else:
            benar, final, manual = u.benar, u.kode, False

        database.simpan_diagnosis(
            kon, jid, benar, u.kode, final,
            None if benar else u.malrule_id, u.alasan, manual
        )
        diubah += 1

    return f"{diubah} koreksi tersimpan."

def buat_sesi_seed_baru(
    kon,
    siswa_id: int,
    level: str | None = None,
    topik: str | None = None,
    mode: str = "diagnostik",
    timer_mode: str = "tanpa",
    durasi_menit: int = 15,
    timer_auto: int = 0,
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
) -> int:
    """Sesi baru dengan seed yang belum pernah dipakai siswa ini."""
    if level is None:
        baris = kon.execute(
            "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        level = baris["tingkat"] if baris else LEVEL_BAWAAN
    if topik is None:
        topik = TOPIK_BAWAAN
    else:
        ambil(topik)  # validasi awal: gagal cepat sebelum menyentuh basis data

    dipakai = {
        r["seed"]
        for r in kon.execute(
            "SELECT seed FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchall()
    }
    for _ in range(500):
        seed = random.randint(1, 9_999_999)
        if seed not in dipakai:
            return database.buat_sesi(
                kon, siswa_id, seed, level=level, topik=topik, mode=mode,
                timer_mode=timer_mode, durasi_menit=durasi_menit,
                timer_auto=timer_auto, jumlah_soal=jumlah_soal, format_jawaban=format_jawaban,
            )
    raise RuntimeError("gagal menemukan seed baru")

def halaman_lembar(kon, sesi_id: int, untuk_guru: bool = False) -> bytes | None:
    """Lembar siap cetak, dibangkitkan ulang dari seed.

    Tidak membaca berkas dari cakram: seed tersimpan di basis data, dan
    membangkitkan ulang menjamin lembar yang tampil SELALU cocok dengan soal
    yang tercatat di sesi ini. Berkas di cakram bisa terhapus, tertimpa, atau
    tertinggal versi lama; seed tidak bisa.
    """
    info = kon.execute(
        """SELECT s.seed, s.tanggal, s.topik, w.nama
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id WHERE s.id = ?""",
        (sesi_id,),
    ).fetchone()
    if not info:
        return None

    # Ambil kunci tulis sebelum snapshot dibaca: writer yang lebih dulu selesai
    # ikut tercetak, sedangkan writer sesudah freeze ditolak service/trigger.
    # Commit/rollback tetap milik pemanggil (handler database.buka), sehingga
    # kegagalan render menggulung pembekuan bersama transaksi ini.
    if not presentation_lock.bekukan_penyajian(kon, sesi_id):
        return None
    from choice_store import format_sesi
    if format_sesi(kon, sesi_id) == 'pilihan_ganda':
        from choice_pages import lembar_pilihan
        return lembar_pilihan(kon, sesi_id, untuk_guru)
    soal = [_soal_dari_baris(b) for b in database.isi_sesi(kon, sesi_id)]
    # Judul dari paket topik sesi ini — bukan selalu paket bawaan. Sesi lama
    # dengan nilai kolom aneh jatuh ke bawaan lewat dari_sesi(), sesuai
    # kontrak data produksi.
    paket = dari_sesi(info["topik"])
    # Lembar yang sama, dua tampilan (Fase 3): di web ia dibaca dari layar,
    # jadi dipakai gaya layar — kartu sentuh, tanpa satuan mm. Versi cetak
    # tetap keluar lewat tombol cetak browser (@media print di gaya layar
    # menurunkan dirinya ke perilaku kertas).
    from screen_style import GAYA_LAYAR

    if untuk_guru:
        isi = worksheets.lembar_penilaian(
            soal, info["nama"], info["tanggal"], info["seed"],
            gaya=GAYA_LAYAR, topik_paket=paket,
        )
    else:
        isi = worksheets.lembar_soal(
            soal, info["nama"], info["tanggal"], gaya=GAYA_LAYAR,
            topik_paket=paket,
        )
    return isi.encode()
