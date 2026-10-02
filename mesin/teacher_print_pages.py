"""Halaman cetak, lampiran, bagikan, dan konfirmasi hapus sesi guru."""
from __future__ import annotations

import html

import database
import presentation_lock
import question_views
import worksheets
from generator import LEVEL_BAWAAN
from question_context import label_profil_parameter as label_kelas
from teacher_session_pages import _badge_mode
from teacher_shell import _halaman
from teacher_workspace import _ambil
from topics import TOPIK_BAWAAN, dari_sesi


def _soal_dari_baris(baris):
    return question_views.soal_dari_baris(baris)


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
        f'<div class="jejak"><a href="/anak/{siswa_id}?section=riwayat">&larr; Kembali ke riwayat anak</a></div>'
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
        f'<div class="jejak"><a href="/anak/{info["siswa_id"]}?section=riwayat">&larr; '
        f'Riwayat {html.escape(info["nama"])}</a></div>'
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
        f'<div class="jejak"><a href="/anak/{info["siswa_id"]}?section=riwayat">&larr; '
        f'Riwayat {html.escape(info["nama"])}</a></div>'
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

def halaman_lembar(
    kon, sesi_id: int, untuk_guru: bool = False, *,
    soal_dari_baris=None, worksheets_module=None,
) -> bytes | None:
    """Lembar siap cetak, dibangkitkan ulang dari seed.

    Tidak membaca berkas dari cakram: seed tersimpan di basis data, dan
    membangkitkan ulang menjamin lembar yang tampil SELALU cocok dengan soal
    yang tercatat di sesi ini. Berkas di cakram bisa terhapus, tertimpa, atau
    tertinggal versi lama; seed tidak bisa.
    """
    soal_dari_baris = soal_dari_baris or _soal_dari_baris
    worksheets_module = worksheets_module or worksheets
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
    soal = [soal_dari_baris(b) for b in database.isi_sesi(kon, sesi_id)]
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
        isi = worksheets_module.lembar_penilaian(
            soal, info["nama"], info["tanggal"], info["seed"],
            gaya=GAYA_LAYAR, topik_paket=paket,
        )
    else:
        isi = worksheets_module.lembar_soal(
            soal, info["nama"], info["tanggal"], gaya=GAYA_LAYAR,
            topik_paket=paket,
        )
    return isi.encode()
