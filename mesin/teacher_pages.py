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
import presentation_lock
import question_views
import worksheets
from diagnosis import diagnosa
from generator import LEVEL_BAWAAN
from question_context import label_profil_parameter as label_kelas
from template_labels import nama_tipe_soal as _nama_template
from templates import Soal
from topics import TOPIK_BAWAAN, ambil, dari_sesi
from teacher_corrections import cara_dari_form, pilihan_tersimpan
from teacher_shell import (
    _halaman,
    _halaman_stitch,
    _topbar,
    _topbar_stitch,
)
from teacher_session_pages import (
    KODE_PILIHAN,
    _badge_mode,
    _blok_latihan_serupa,
    _label_tahap_sesi,
    _pil_sesi_stitch,
    halaman_sesi_stitch as _halaman_sesi_stitch_impl,
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


# Satu sumber teks bubble ikon "ⓘ" beranda guru: dipakai sebagai aria-label
# tombol sekaligus isi bubble supaya pembaca layar dan mata membaca hal sama.
INFO_DAFTAR_ANAK = (
    "Setiap anak punya halaman sendiri: buat latihan, rencana belajar, "
    "dan riwayat."
)



def _soal_dari_baris(baris) -> Soal:
    """Wrapper kompatibilitas menuju adapter pembaca penyajian sesi."""
    return question_views.soal_dari_baris(baris)




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








def halaman_sesi_stitch(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "", bantuan: str = "", bantuan_nomor: int | None = None,
    draf_koreksi=None,
    privat: bool = False,
    masalah_konfirmasi=(),
) -> bytes:
    """Façade renderer sesi dengan lookup adapter soal tetap runtime."""
    return _halaman_sesi_stitch_impl(
        kon, sesi_id, pesan=pesan, peran=peran, pengguna=pengguna,
        bantuan=bantuan, bantuan_nomor=bantuan_nomor,
        draf_koreksi=draf_koreksi, privat=privat,
        masalah_konfirmasi=masalah_konfirmasi,
        soal_dari_baris=_soal_dari_baris,
    )


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
