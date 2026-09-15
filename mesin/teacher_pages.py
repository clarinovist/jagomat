"""Halaman-halaman guru: dashboard, sesi, konfirmasi hapus, lembar.

Dipecah dari web.py (refactor 31 Aug 2026) — fungsi pindah utuh, perilaku
identik. Router HTTP tetap di web.py; frame halaman (_halaman/_topbar)
tinggal di sini dan dipakai reports.py serta account_pages.py.
Aturan lama tetap berlaku: modul ini tidak boleh mengimpor students di atas
file (impor terlambat di dalam fungsi, lihat pemakaian aslinya).
"""

from __future__ import annotations

import html
import random
from datetime import datetime

import database
import brand
import design_tokens as T
import learning_cycle_ui
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
from templates import LEVEL, Soal, label_kelas
from topics import TOPIK_BAWAAN, ambil, daftar_topik, dari_sesi
from teacher_style import GAYA_GURU as GAYA, SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA
from style_stitch import GAYA_STITCH


KODE_PILIHAN = [
    ("", "— pilih —"),
    ("benar", "Benar"),
    ("K", "K — salah konsep"),
    ("B", "B — salah baca soal"),
    ("H", "H — salah hitung"),
    ("E", "E — salah tulis akhir"),
    ("N", "N — menebak"),
]


LABEL_KODE_REMEDIAL = {
    "K": "Salah konsep",
    "B": "Salah memahami soal",
    "H": "Salah hitung",
    "E": "Salah menyalin jawaban",
    "N": "Menebak atau belum menunjukkan cara",
}


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


def _form_remedial(
    sasaran,
    siswa_id: int,
    *,
    judul: str,
    penjelasan: str,
    sumber_sesi_id: int | None = None,
) -> str:
    """Form pilihan remedial bersama untuk profil anak dan hasil satu sesi."""
    if not sasaran:
        return ""
    pilihan = []
    sudah_dipilih = False
    for kandidat in sasaran:
        template_id = str(kandidat["template_id"])
        kode = str(kandidat["kode"] or "")
        direkomendasikan = bool(kandidat["direkomendasikan"])
        checked = direkomendasikan and not sudah_dipilih
        sudah_dipilih = sudah_dipilih or checked
        label_kode = LABEL_KODE_REMEDIAL.get(kode, "Perlu diperhatikan")
        meta = f'{html.escape(label_kode)} · {int(kandidat["kali_salah"])} kali'
        pilihan.append(
            '<label class="pilihan-remedial-st">'
            f'<input type="checkbox" name="template_id" value="{html.escape(template_id)}"'
            f'{" checked" if checked else ""}>'
            '<span class="isi-pilihan-remedial-st">'
            f'<b>{html.escape(_nama_template(template_id))}</b>'
            f'<span class="meta-remedial-st">{meta}</span>'
            '</span></label>'
        )
    sumber = (
        f'<input type="hidden" name="sumber_sesi_id" value="{sumber_sesi_id}">'
        if sumber_sesi_id is not None else ""
    )
    return (
        f'<section class="remedial-st"><h2>{html.escape(judul)}</h2>'
        f'<p class="sub">{html.escape(penjelasan)}</p>'
        f'<form method="post" action="/sesi-remedial/{siswa_id}" class="strip-sesi">'
        f'{sumber}<div class="daftar-remedial-st">{"".join(pilihan)}</div>'
        '<p class="batas-remedial-st">Pilih maksimal 3 tipe soal.</p>'
        '<div class="strip-kolom"><label>Jumlah Soal</label>'
        '<select name="jumlah_soal" class="st-input">'
        '<option value="10" selected>10 soal (± 30 mnt)</option>'
        '<option value="15">15 soal (± 45 mnt)</option>'
        '<option value="20">20 soal (± 60 mnt)</option>'
        '</select></div>'
        '<button type="submit" class="st-tombol-coral">'
        '<span class="material-symbols-outlined" aria-hidden="true">restart_alt</span>'
        'Buat latihan ulang terarah</button></form></section>'
    )


def _halaman(
    judul: str, isi: str, ident: tuple[str, str] | None = None,
    stitch: bool = False, kelas_bungkus: str = "", id_utama: str = "",
    privat: bool = False,
) -> bytes:
    """Bingkai semua halaman pengelola. `ident=(pengguna, peran)` menampilkan
    topbar dengan menu pengguna di atas isi — satu pintu agar konsisten.

    stitch=True: pakai GAYA_STITCH + body.st + <link> font CDN (S11-S17).
    `kelas_bungkus` hanya berlaku pada bingkai Stitch untuk kanvas khusus.
    `id_utama` opsional memberi landmark main; default menjaga markup lama.
    """
    if stitch:
        from style_stitch import gaya_stitch, CSS_SESI
        batang = _topbar_stitch(*ident) if ident else ""
        kelas = f"bungkus-st {kelas_bungkus}".strip()
        buka_isi = (
            f'<main class="sesi-badan-st" aria-labelledby="{html.escape(id_utama)}">'
            if id_utama else '<div class="sesi-badan-st">'
        )
        tutup_isi = "</main>" if id_utama else "</div>"
        font = "" if privat else """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">"""
        gaya = gaya_stitch()
        if privat:
            gaya = gaya.replace(
                "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
                "",
            )
        return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
{font}
<style>{GAYA}{gaya}{CSS_SESI}</style></head>
<body class="st"><div class="{kelas}">{batang}{buka_isi}{isi}{tutup_isi}</div>{'' if privat else f'<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script>'}</body></html>""".encode()
    batang = _topbar(*ident) if ident else ""
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}<style>{GAYA}</style></head>
<body><div class="bungkus">{batang}{isi}</div><script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script></body></html>""".encode()

def _soal_dari_baris(baris) -> Soal:
    """Wrapper kompatibilitas menuju adapter pembaca penyajian sesi."""
    return question_views.soal_dari_baris(baris)

def _ambil(baris, kolom: str, bawaan):
    """Baca kolom yang mungkin belum ada di baris.

    sqlite3.Row melempar IndexError untuk kolom tak dikenal, dan sebagian
    test memberi dict biasa. Dipakai untuk kolom hasil migrasi supaya
    pemanggil lama tidak pecah.
    """
    try:
        nilai = baris[kolom]
    except (IndexError, KeyError):
        return bawaan
    return bawaan if nilai is None else nilai

def _tanggal_ringkas(nilai) -> str:
    """Tanggal Indonesia ringkas; nilai warisan tetap ditampilkan aman."""
    mentah = str(nilai or "")
    bulan = (
        "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
    )
    try:
        tanggal = datetime.strptime(mentah, "%Y-%m-%d")
    except ValueError:
        return f'<span>{html.escape(mentah or "—")}</span>'
    label = f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"
    nilai_datetime = tanggal.strftime("%Y-%m-%d")
    return f'<time datetime="{nilai_datetime}">{label}</time>'


def _nama_topik_sesi(topik_id: str) -> tuple[str, str]:
    """Judul dan rincian topik dalam bahasa orang tua, bukan ID basis data."""
    if topik_id.startswith("gabungan:"):
        ids = [nilai for nilai in topik_id.split(":", 1)[1].split(",") if nilai]
        nama = []
        for nilai in ids:
            try:
                nama.append(ambil(nilai).nama)
            except KeyError:
                nama.append(nilai.replace("-", " ").title())
        return f"Gabungan {len(nama)} topik", " &middot; ".join(
            html.escape(nilai) for nilai in nama
        )
    try:
        nama_topik = ambil(topik_id).nama
    except KeyError:
        nama_topik = topik_id.replace("-", " ").title()
    if topik_id == "campuran":
        awalan_dekoratif = "✨ "
        if nama_topik.startswith(awalan_dekoratif):
            nama_topik = nama_topik[len(awalan_dekoratif):]
        nama_topik = nama_topik.split(" (", 1)[0]
    return nama_topik, ""


def _mode_sesi(baris) -> str:
    if _ambil(baris, "mode", "diagnostik") == "drill":
        return "Latihan Cepat"
    return "Mode Diagnosa"


def _ringkasan_angka_sesi(baris) -> str:
    """Hanya tampilkan angka yang sudah bermakna pada tahap sesi saat ini."""
    terisi = int(_ambil(baris, "terisi", 0) or 0)
    jumlah = int(_ambil(baris, "n", 0) or 0)
    if terisi == 0:
        return ""
    bagian = [f"{terisi} dari {jumlah} terisi"]
    if _ambil(baris, "selesai", None):
        benar = int(_ambil(baris, "benar", 0) or 0)
        bagian[0] = f"{benar} dari {jumlah} benar"
        durasi = _fmt_durasi(
            _ambil(baris, "mulai", None),
            _ambil(baris, "selesai", None),
            _ambil(baris, "dicatat_awal", None),
            _ambil(baris, "dicatat_akhir", None),
        )
        if durasi != "&mdash;":
            bagian.append(f"Waktu {durasi}")
    return " &middot; ".join(bagian)


def _topik_untuk_level(level: str) -> list[str]:
    """ID topik yang tersedia pada level resmi atau fallback data lama."""
    level_efektif = level if level in LEVEL else LEVEL_BAWAAN
    daftar = [
        topik_id
        for topik_id in daftar_topik()
        if level_efektif in ambil(topik_id).komposisi and topik_id != "campuran"
    ]
    if "campuran" in daftar_topik():
        daftar = ["campuran"] + daftar
    return daftar

def _badge_review_status(baris) -> str:
    if _ambil(baris, "dibatalkan", None) is not None:
        return '<span class="badge-direview batal st-badge selesai">Dibatalkan</span>'
    direview = _ambil(baris, "direview", None)
    selesai = _ambil(baris, "selesai", None)
    terisi = _ambil(baris, "terisi", 0)
    if direview is not None:
        return '<span class="badge-direview sudah" style="background:#d4edda;color:#155724;padding:0.2rem 0.45rem;border-radius:4px;font-size:0.78rem;font-weight:bold;">✓ Sudah Direview</span>'
    elif selesai is not None:
        return '<span class="badge-direview perlu" style="background:#fff3cd;color:#856404;padding:0.2rem 0.45rem;border-radius:4px;font-size:0.78rem;font-weight:bold;">⏳ Belum Direview</span>'
    elif terisi > 0:
        return '<span class="badge-direview proses" style="background:#e2e8f0;color:#2d3748;padding:0.2rem 0.45rem;border-radius:4px;font-size:0.78rem;">✏️ Sedang Dikerjakan</span>'
    else:
        return '<span class="badge-direview belum" style="background:#edf2f7;color:#718096;padding:0.2rem 0.45rem;border-radius:4px;font-size:0.78rem;">Belum Dikerjakan</span>'

def _badge_mode(baris) -> str:
    """Badge 'Latihan Cepat' untuk sesi drill; kosong untuk diagnostik.

    CSS guru memuat kata "Latihan Cepat" di komentar, jadi badge-nya
    harus marker kelas, bukan teks yang dicari mentah.
    """
    if _ambil(baris, "mode", "diagnostik") == "drill":
        return '<span class="badge-mode">Latihan Cepat</span>'
    return ""

def _fmt_durasi(mulai, selesai, dicatat_awal=None, dicatat_akhir=None) -> str:
    """Durasi pengerjaan mm:ss dari kolom mulai/selesai sesi.

    Utama: selesai − mulai, dan hanya bila keduanya tercatat. Kalau salah
    satu tidak ada (sesi kertas yang dilengkapi lewat foto) atau durasinya
    nol — versi lama mencatat mulai saat simpan pertama, jadi sesi sekali
    simpan tercatat 0 detik — jatuh ke rentang waktu tercatatnya jawaban
    (dicatat_awal → dicatat_akhir): perkiraan yang tetap jujur karena tiap
    simpan mencatat waktunya. Tanpa jejak waktu sama sekali, tampil '—';
    mengarang durasi lebih buruk daripada menampilkan kosong.
    """
    BENTUK = "%Y-%m-%d %H:%M:%S"
    for awal, akhir in ((mulai, selesai), (dicatat_awal, dicatat_akhir)):
        if not awal or not akhir:
            continue
        try:
            detik = int(
                (
                    datetime.strptime(str(akhir), BENTUK)
                    - datetime.strptime(str(awal), BENTUK)
                ).total_seconds()
            )
        except ValueError:
            continue
        if detik > 0:
            return f"{detik // 60}:{detik % 60:02d}"
    return "&mdash;"

def _badge_peran(peran: str) -> str:
    """Penanda peran di topbar — supaya siapa pun langsung tahu di sisi mana
    dia berada. Murid punya dunia visual sendiri, jadi cukup dua ini."""
    if peran == "admin":
        return '<span class="badge-peran badge-peran-admin">Pengelola</span>'
    if peran == "guru":
        return '<span class="badge-peran badge-peran-guru">Orang Tua / Guru</span>'
    return ""

def _topbar(pengguna: str, peran: str) -> str:
    """Topbar semua halaman pengelola: brand + menu pengguna dropdown.

    Menu dari <details> CSS-only — tanpa JS. Gemboknya nama akun + badge
    peran supaya keluhan "cuma teks polos" hilang: batas menunya jelas.
    Isinya menyesuaikan peran (guru: pintu keluarga; admin: dashboard,
    pengaturan AI, dan ganti sandi), lalu satu pintu keluar."""
    if peran == "admin":
        brand_href, item = "/admin", (
            '<a href="/admin">Dashboard admin</a>'
            '<a href="/admin/ai">Pengaturan AI</a>'
            '<a href="/akun?section=akun">Ganti sandi</a>'
        )
    else:
        brand_href, item = "/guru", '<a href="/akun">Akun &amp; Siswa</a>'
    siapa = html.escape(pengguna) if pengguna else ""
    return (
        f'<div class="topbar">'
        f'<a class="brand" href="{brand_href}">'
        f'{brand.mark("topbar")}<span>{T.NAMA_PRODUK}</span></a>'
        f'<nav class="topbar-navigasi">'
        f'<details class="menu-pengguna">'
        f'<summary>{siapa} {_badge_peran(peran)}</summary>'
        f'<div class="menu-isi">{item}'
        f'<div class="menu-pisah"></div>'
        f'<form method="post" action="/keluar" style="margin:0">'
        f'<button type="submit">Keluar</button>'
        f"</form></div></details></nav></div>"
    )


def _topbar_stitch(pengguna: str, peran: str) -> str:
    """Topbar versi Stitch — pakai .st-topbar supaya CSS lama tidak dicampur.

    Menu pengguna tetap CSS-only (<details>), satu pintu keluar, tautan
    menyesuaikan peran. Logo ikon owl = Material Symbols 'school'.
    """
    if peran == "admin":
        brand_href, item = "/admin", (
            '<a href="/admin">Dashboard admin</a>'
            '<a href="/admin/ai">Pengaturan AI</a>'
            '<a href="/akun?section=akun">Ganti sandi</a>'
        )
    else:
        brand_href, item = "/guru", '<a href="/akun">Akun &amp; Siswa</a>'
    siapa = html.escape(pengguna) if pengguna else ""
    return (
        '<div class="st-topbar">'
        f'<a class="brand" href="{brand_href}">'
        f'{brand.mark("topbar")}'
        f'<span class="nama">{html.escape(T.NAMA_PRODUK)}</span>'
        "</a>"
        '<nav class="topbar-navigasi">'
        f'{_badge_peran(peran)}'           # badge peran lama (Pengelola/Orang Tua)
        f'<details class="menu-pengguna">'
        f"<summary>{siapa}</summary>"
        f'<div class="menu-isi">{item}'
        '<div class="menu-pisah"></div>'
        '<form method="post" action="/keluar" style="margin:0">'
        '<button type="submit" class="cta">Keluar</button>'
        "</form></div></details></nav></div>"
    )


def _halaman_stitch(
    judul: str, isi: str, ident: tuple[str, str] | None = None,
    kelas_bungkus: str = "", privat: bool = False,
) -> bytes:
    """Bingkai halaman versi Stitch — pakai GAYA_STITCH dan body.st.

    Dipisah dari _halaman lama supaya halaman lama tetap utuh; fungsi ini
    satu-satunya penghubung ke CSS Stitch di tree.

    `kelas_bungkus` menempel di .bungkus-st untuk halaman yang butuh kanvas
    berbeda (mis. "lebar" di /anak/<id> yang memakai dua kolom di desktop).
    Bawaannya kosong: semua pemanggil lama menghasilkan HTML yang sama persis.
    """
    batang = _topbar_stitch(*ident) if ident else ""
    kelas = f"bungkus-st {kelas_bungkus}".strip()
    font = "" if privat else """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap" rel="stylesheet">"""
    gaya = GAYA_STITCH
    if privat:
        gaya = gaya.replace(
            "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
            "",
        )
    skrip = "" if privat else f"<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script>"
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
{font}
<style>{gaya}</style></head>
<body class="st"><div class="{kelas}">{batang}{isi}</div>{skrip}</body></html>""".encode()


def halaman_utama_stitch(
    kon,
    pesan: str = "",
    pemilik: str | None = None,
    peran: str = "guru",
    sorot: int | None = None,
) -> bytes:
    """Beranda pendamping: satu pintu per anak, tanpa keputusan belajar baru.

    Status kirim/review hanya ringkasan aktivitas, bukan bukti penguasaan.
    Rencana belajar tetap berada pada profil anak dan reducer yang sama.
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
        baris.append(
            f'<a class="st-kartu kartu-anak" href="/anak/{s["id"]}">'
            f'<span class="guru-inisial-st" aria-hidden="true">{html.escape(nama[:1].upper())}</span>'
            '<div class="guru-identitas-st">'
            f'<h3 class="guru-nama-st">{html.escape(nama)}</h3>'
            '<div class="guru-meta-st">'
            f'<span>{html.escape(label_kelas(str(s["tingkat"])))}</span>'
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
        '<p class="guru-petunjuk-st">Pilih nama untuk membuka rencana belajar dan riwayat sesi.</p>'
        f'<div class="daftar-anak">{"".join(baris)}</div>'
    ) if baris else (
        '<div class="guru-kosong-st">'
        '<p class="guru-alis-st">MULAI DARI SINI</p>'
        '<h2 id="daftar-anak">Kenali langkah pertama mereka.</h2>'
        '<p>Akunmu sudah siap. Tambahkan anak dengan nama panggilan, '
        'lalu buka profilnya untuk mulai mendampingi belajar.</p>'
        f'{tambah}<p class="guru-petunjuk-st">Belum ada sesi latihan. '
        'Rencana belajar akan tersedia di profil anak.</p></div>'
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


def _kontrol_mode_sesi(draf=None) -> str:
    """Pilihan cara menjawab dan batas waktu sebagai dua keputusan terpisah."""
    mode = draf.mode if draf else "diagnostik"
    timer = draf.timer_mode if draf else False
    durasi = draf.durasi_menit if draf else "30"
    timer_auto = draf.timer_auto if draf else "0"
    return (
        '<div class="strip-kolom"><label>Mode sesi</label>'
        '<div class="mode-pilih">'
        '<label class="mode-opsi"><input type="radio" name="mode" '
        f'value="diagnostik"{" checked" if mode == "diagnostik" else ""}>'
        '<span class="mode-teks">Mode Diagnosa'
        '<span class="mode-desk">Jawaban dan cara berpikir anak ikut diperiksa.</span>'
        '</span></label>'
        f'<label class="mode-opsi"><input type="radio" name="mode" value="drill"{" checked" if mode == "drill" else ""}>'
        '<span class="mode-teks">Latihan Cepat'
        '<span class="mode-desk">Anak langsung mengisi jawaban. Cocok untuk pengulangan.</span>'
        '</span></label>'
        '</div></div>'
        '<fieldset class="pengaturan-timer">'
        '<legend>Batas waktu</legend>'
        '<label class="mode-opsi timer-toggle">'
        '<input type="hidden" name="hadir_timer_mode" value="1">'
        f'<input type="checkbox" name="timer_mode" value="sesi"{" checked" if timer else ""}>'
        '<span class="mode-teks">Gunakan batas waktu'
        '<span class="mode-desk">Hitung mundur ditampilkan selama seluruh sesi.</span>'
        '</span></label>'
        '<div class="rincian-timer">'
        '<label class="durasi-timer">Durasi sesi '
        '<span><input type="text" inputmode="numeric" '
        f'name="durasi_menit" value="{html.escape(durasi, quote=True)}"> menit</span>'
        '<small>Saran: sekitar 3 menit per soal.</small></label>'
        '<fieldset class="akibat-timer"><legend>Ketika waktu habis</legend>'
        '<label class="mode-opsi"><input type="radio" name="timer_auto" '
        f'value="0"{" checked" if timer_auto == "0" else ""}> Ingatkan anak, tetapi tetap boleh menyelesaikan</label>'
        '<label class="mode-opsi"><input type="radio" name="timer_auto" '
        f'value="1"{" checked" if timer_auto == "1" else ""}> Kirim jawaban secara otomatis</label>'
        '</fieldset></div></fieldset>'
    )


def halaman_anak(
    kon,
    siswa,
    peran: str = "guru",
    pengguna: str = "",
    sorot: int | None = None,
    pesan: str = "",
    bantuan_rencana: str = "",
    bantuan_latihan: str = "",
    draf_latihan=None,
    privat: bool = False,
) -> bytes:
    """History satu anak (feedback Filia 1 Sep 2026 no. 6).

    Masuk dari kartu nama di dashboard. Berisi: daftar sesi anak (dengan
    badge review & mode), strip buat sesi baru, dan pintasan laporan.
    `siswa` baris sqlite dari tabel siswa.
    """
    privat = privat or bool(bantuan_rencana or bantuan_latihan)
    opsi_topik = "".join(
        f'<option value="{html.escape(t)}"'
        f'{" selected" if draf_latihan and draf_latihan.topik == t else ""}>'
        f'{html.escape(ambil(t).nama)}</option>'
        for t in _topik_untuk_level(siswa["tingkat"])
    )
    sesi = kon.execute(
        """SELECT s.id, s.tanggal, s.seed, s.level, s.topik, s.mode,
                  s.jenis, s.sumber_sesi_id,
                  s.mulai, s.selesai, s.direview, s.dibatalkan,
                  (SELECT MIN(j.dicatat) FROM sesi_soal ss
                   JOIN jawaban j ON j.sesi_soal_id = ss.id
                   WHERE ss.sesi_id = s.id) AS dicatat_awal,
                  (SELECT MAX(j.dicatat) FROM sesi_soal ss
                   JOIN jawaban j ON j.sesi_soal_id = ss.id
                   WHERE ss.sesi_id = s.id) AS dicatat_akhir,
                  (SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = s.id) AS n,
                  (SELECT COUNT(*) FROM sesi_soal ss
                   JOIN jawaban j ON j.sesi_soal_id = ss.id
                   WHERE ss.sesi_id = s.id) AS terisi,
                  (SELECT COUNT(*) FROM sesi_soal ss
                   JOIN jawaban j ON j.sesi_soal_id = ss.id
                   JOIN diagnosis d ON d.jawaban_id = j.id
                   WHERE ss.sesi_id = s.id AND d.benar = 1) AS benar
           FROM sesi s WHERE s.siswa_id = ?
           ORDER BY s.tanggal DESC, s.id DESC""",
        (siswa["id"],),
    ).fetchall()

    def _kelas_sorot(rid):
        return "sorot-baru" if sorot is not None and rid == sorot else ""

    def _aksi_tautan(baris):
        rid = baris["id"]
        if baris["selesai"] or baris["dibatalkan"] is not None:
            return ""
        aktif = share_links.aktif(kon, rid)
        cabut = ""
        if aktif:
            cabut = (
                f'<form method="post" action="/sesi/{rid}/cabut-tautan" style="margin:0">'
                '<button type="submit" class="tombol-ikon-st" '
                'aria-label="Cabut tautan sesi" title="Cabut tautan">'
                '<span class="material-symbols-outlined">link_off</span></button></form>'
            )
        if privat:
            # Fallback native: fungsi tetap tersedia tanpa fetch/confirm JS.
            peringatan = (
                '<p class="sub">Membuat tautan baru akan menonaktifkan tautan sebelumnya.</p>'
                if aktif else ""
            )
            return (
                '<div class="blok-bagikan-st"><div class="aksi-bagikan-st">'
                f'<form method="post" action="/sesi/{rid}/bagikan">{peringatan}'
                f'<button type="submit">{("Buat tautan baru" if aktif else "Bagikan sesi ke anak")}</button>'
                '</form>' + cabut + '</div></div>'
            )
        return (
            '<div class="blok-bagikan-st">'
            '<div class="aksi-bagikan-st">'
            f'<button type="button" class="tombol-ikon-st tombol-bagikan-st" '
            f'data-bagikan-url="/sesi/{rid}/bagikan" '
            f'data-bagikan-aktif="{1 if aktif else 0}" '
            'aria-label="Bagikan sesi ke anak" title="Bagikan sesi">'
            '<span class="material-symbols-outlined">share</span></button>'
            f"{cabut}</div>"
            '<span class="kabar-bagikan-st" aria-live="polite"></span>'
            "</div>"
        )

    def _kartu_sesi(r, kelas):
        topik_id = str(_ambil(r, "topik", TOPIK_BAWAAN))
        judul_topik, rincian_topik = _nama_topik_sesi(topik_id)
        rincian = (
            f'<div class="rincian-topik-st">{rincian_topik}</div>'
            if rincian_topik
            else ""
        )
        angka = _ringkasan_angka_sesi(r)
        ringkasan = (
            f'<div class="ringkasan-sesi-st">{angka}</div>' if angka else ""
        )
        identitas_remedial = ""
        if _ambil(r, "jenis", "biasa") == "remedial":
            fokus_ids = [
                b["template_id"] for b in database.isi_sesi(kon, int(r["id"]))
            ]
            fokus_unik = list(dict.fromkeys(fokus_ids))
            fokus = " & ".join(_nama_template(t) for t in fokus_unik)
            asal = (
                f' · dari sesi #{int(r["sumber_sesi_id"])}'
                if _ambil(r, "sumber_sesi_id", None) else ""
            )
            identitas_remedial = (
                '<div class="rincian-topik-st"><span class="st-badge latihan">'
                'Remedial</span> '
                f'Fokus {html.escape(fokus)}{asal}</div>'
            )
        return (
            f'<article class="st-kartu-baris kartu-sesi-guru {kelas}">'
            '<div class="isi-kartu-sesi-st">'
            f'<a class="judul-sesi-st" href="/sesi/{r["id"]}">'
            f'{html.escape(judul_topik)}</a>'
            f"{rincian}"
            f"{identitas_remedial}"
            '<div class="meta-sesi-st">'
            f'{_tanggal_ringkas(r["tanggal"])}<span aria-hidden="true">&middot;</span>'
            f'<span>{html.escape(label_kelas(str(_ambil(r, "level", LEVEL_BAWAAN))))}</span>'
            '<span aria-hidden="true">&middot;</span>'
            f'<span>{html.escape(_mode_sesi(r))}</span>'
            '<span aria-hidden="true">&middot;</span>'
            f'<span class="nomor-sesi-st">Sesi #{r["id"]}</span>'
            "</div>"
            f"{ringkasan}"
            "</div>"
            '<div class="aksi-sesi-st">'
            f'{_badge_review_status(r)}'
            f'{_aksi_tautan(r)}'
            "</div>"
            "</article>"
        )

    if sesi:
        item = "".join(
            _kartu_sesi(r, _kelas_sorot(r["id"])) for r in sesi
        )
    else:
        item = '<p class="sub">Belum ada sesi — mulai dari rencana belajar di atas.</p>'

    label_keluarga = ""
    if peran == "admin":
        siapa = siswa["pemilik"] or "warisan"
        label_keluarga = (
            '<span class="st-badge selesai">keluarga: '
            f"{html.escape(siapa)}</span>"
        )

    strip_sesi = (
        f'<form method="post" action="/sesi-baru/{siswa["id"]}" class="strip-sesi">'
        f'<div class="strip-kolom"><label for="manual-topik">Topik</label>'
        f'<select id="manual-topik" name="topik" class="st-input">{opsi_topik}</select></div>'
        f'<div class="strip-kolom"><label for="manual-jumlah">Jumlah Soal (estimasi ±3 mnt/soal)</label>'
        f'<select id="manual-jumlah" name="jumlah_soal" class="st-input">'
        + "".join(
            f'<option value="{nilai}"'
            f'{" selected" if (draf_latihan.jumlah_soal if draf_latihan else "") == nilai else ""}>'
            f'{label}</option>'
            for nilai, label in (("", "Default (sesuai topik)"), ("10", "10 soal (± 30 mnt)"),
                                 ("15", "15 soal (± 45 mnt)"), ("20", "20 soal (± 60 mnt)"),
                                 ("25", "25 soal (± 75 mnt)"), ("30", "30 soal (± 90 mnt)"))
        )
        + f'</select></div>{_kontrol_mode_sesi(draf_latihan)}'
        + (bantuan_latihan or (
            __import__("assistant_components").tombol_buka(
                __import__("assistant_inline").tujuan_anak(int(siswa["id"]), "latihan"),
                dalam_form=True,
            ) if peran == "guru" and pengguna else ""
        ))
        + '<button type="submit" class="st-tombol-coral">'
        '<span class="material-symbols-outlined" style="font-size:1.1rem">play_arrow</span>'
        "Buat sesi baru</button>"
        "</form>"
    )

    # Remedial terarah dari seluruh riwayat yang sudah ditinjau. Guru melihat
    # bukti dan memilih fokus; sistem tidak lagi mencampur enam tipe diam-diam.
    sasaran = database.sasaran_remedial_anak(kon, siswa["id"])
    strip_remedial = _form_remedial(
        sasaran,
        int(siswa["id"]),
        judul="Perkuat kelemahan",
        penjelasan=(
            "Pilih yang ingin dilatih. Pilihan yang dicentang adalah rekomendasi "
            "berdasarkan hasil terbaru."
        ),
    )

    # Latihan gabungan (poin 4 tahap 2): guru memilih BEBERAPA topik saja,
    # mis. "geometri datar + pengukuran" untuk anak yang lemah di dua itu.
    # Berbeda dari topik "campuran" yang selalu memakai SEMUA topik.
    centang_topik = "".join(
        f'<label class="mode-opsi"><input type="checkbox" name="topik" '
        f'value="{html.escape(t)}"> {html.escape(ambil(t).nama)}</label>'
        for t in _topik_untuk_level(siswa["tingkat"])
        if t != "campuran"      # campuran sudah = semua, tak perlu dicentang
    )
    strip_gabungan = (
        '<form method="post" '
        f'action="/sesi-gabungan/{siswa["id"]}" class="strip-sesi">'
        '<div class="strip-kolom">'
        "<label>Latihan gabungan — pilih beberapa topik</label>"
        '<p class="sub">Centang dua topik atau lebih. Soalnya dicampur '
        "bergantian antar-topik yang kamu pilih.</p>"
        f'<div class="mode-pilih">{centang_topik}</div></div>'
        '<div class="strip-kolom"><label for="gabungan-jumlah">Jumlah Soal</label>'
        '<select id="gabungan-jumlah" name="jumlah_soal" class="st-input">'
        '<option value="10" selected>10 soal (± 30 mnt)</option>'
        '<option value="15">15 soal (± 45 mnt)</option>'
        '<option value="20">20 soal (± 60 mnt)</option>'
        "</select></div>"
        '<button type="submit" class="st-tombol-coral">'
        '<span class="material-symbols-outlined" style="font-size:1.1rem">'
        "library_add</span>Buat latihan gabungan</button>"
        "</form>"
    )

    # Fase C: tiga form di atas dibungkus SATU kartu "Buat latihan" dengan tab
    # radio. Tanpa JS (CLAUDE.md: zero-JS by default) — pemilihan tab memakai
    # :has(), teknik yang sudah dipakai .mode-opsi:has(input:checked).
    #
    # Panel disusun dinamis: strip_remedial kosong kalau anak belum punya
    # kesalahan tercatat. Menyusunnya dari daftar mencegah tab hantu yang
    # menunjuk panel kosong.
    panel = [("baru", "add_circle", "Sesi baru", strip_sesi)]
    if strip_remedial:
        panel.append(("ulang", "restart_alt", "Perkuat kelemahan", strip_remedial))
    if strip_gabungan:
        panel.append(("gabungan", "library_add", "Gabungan topik", strip_gabungan))

    if len(panel) > 1:
        tab = "".join(
            f'<input type="radio" name="jenis-latihan" id="tab-{kode}" '
            f'class="tab-radio-st"{" checked" if i == 0 else ""}>'
            for i, (kode, _, _, _) in enumerate(panel)
        )
        label = "".join(
            f'<label class="tab-label-st" for="tab-{kode}">'
            f'<span class="material-symbols-outlined">{ikon}</span>'
            f"{html.escape(judul)}</label>"
            for kode, ikon, judul, _ in panel
        )
        isi_panel = "".join(
            f'<div class="panel-latihan-st" data-panel="{kode}">{badan}</div>'
            for kode, _, _, badan in panel
        )
        blok_buat_latihan = (
            '<section class="buat-latihan-st">'
            '<h2 class="st">Buat latihan</h2>'
            f"{tab}"
            f'<div class="tab-bar-st">{label}</div>'
            f"{isi_panel}"
            "</section>"
        )
    else:
        # Hanya satu bentuk latihan yang tersedia — tab justru menambah klik
        # tanpa memberi pilihan. Tampilkan formnya langsung.
        blok_buat_latihan = (
            '<section class="buat-latihan-st">'
            '<h2 class="st">Buat latihan</h2>'
            f"{strip_sesi}"
            "</section>"
        )

    kabar = (
        '<div class="st-banner-sukses"><span class="ikon">✓</span>'
        f"<span>{html.escape(pesan)}</span></div>"
        if pesan
        else ""
    )
    tautan_bantuan = (
        __import__("assistant_components").tombol_buka(
            __import__("assistant_inline").tujuan_anak(int(siswa["id"]), "rencana")
        )
        if peran == "guru" and pengguna and not bantuan_rencana else ""
    )
    kartu_rencana = learning_cycle_ui.kartu_rencana(
        kon, int(siswa["id"]), slot_bantuan=bantuan_rencana or tautan_bantuan,
    )
    latihan_manual = (
        '<details class="atur-latihan-st"' + (' open' if bantuan_latihan else '') + '>'
        '<summary>Atur latihan sendiri</summary>'
        '<p class="sub">Latihan bebas tidak mengubah progres rencana terpandu.</p>'
        f"{blok_buat_latihan}</details>"
    )

    skrip_bagikan = "" if privat else (
        "<script>(function(){var b=document.querySelectorAll('.tombol-bagikan-st');"
        "async function salin(t,k){try{await navigator.clipboard.writeText(t);k.textContent='Tautan tersalin dan berlaku 7 hari.';return true;}catch(e){window.prompt('Salin tautan ini:',t);k.textContent='Salin tautan yang tampil. Tautan berlaku 7 hari.';return false;}}"
        "async function bagikan(t,k){if(navigator.share){try{await navigator.share({title:'Sesi Jagomat',url:t});k.textContent='Tautan dibagikan dan berlaku 7 hari.';return;}catch(e){if(e.name==='AbortError'){k.textContent='';return;}}}await salin(t,k);}"
        "for(var i=0;i<b.length;i++){b[i].addEventListener('click',async function(){var x=this,k=x.closest('.blok-bagikan-st').querySelector('.kabar-bagikan-st');if(x.dataset.tautan){await bagikan(x.dataset.tautan,k);return;}if(x.dataset.bagikanAktif==='1'&&!window.confirm('Membuat tautan baru akan menonaktifkan tautan sebelumnya. Lanjutkan?'))return;x.disabled=true;"
        "try{var r=await fetch(x.dataset.bagikanUrl,{method:'POST',headers:{'X-Requested-With':'fetch'}});"
        "if(!r.ok)throw new Error('gagal');var d=await r.json();x.dataset.tautan=d.tautan;x.dataset.bagikanAktif='1';await bagikan(d.tautan,k);}"
        "catch(e){k.textContent='Tautan belum berhasil dibuat. Coba lagi.';}finally{x.disabled=false;}});}})()</script>"
    )
    return _halaman_stitch(
        f"{siswa['nama']} — {T.NAMA_PRODUK}",
        '<main aria-labelledby="judul-profil">'
        f'<div class="jejak"><a href="{"/admin" if peran == "admin" else "/guru"}">&larr; Semua anak</a></div>'
        '<header class="kepala-anak-st editorial-kepala-st">'
        '<p class="editorial-alis-st">CATATAN BELAJAR ANAK</p>'
        f'<h1 class="st" id="judul-profil">{html.escape(siswa["nama"])}'
        f'<span class="st-badge selesai">({html.escape(label_kelas(str(siswa["tingkat"])))})</span>'
        f"{label_keluarga}"
        "</h1>"
        "</header>"
        f"{kabar}"
        f"{kartu_rencana}"
        # Struktur lama dipertahankan; CSS data-rencana memindahkan kolom
        # alat manual secara visual ke atas riwayat tanpa entry point ganda.
        '<div class="anak-grid" data-rencana="vertikal">'
        '<section class="anak-kolom-kiri">'
        '<div class="kepala-riwayat-st">'
        '<h2 class="st">Riwayat latihan</h2>'
        f'<a class="tautan-laporan-st" href="/laporan/{siswa["id"]}">'
        '<svg class="ikon-laporan-st" viewBox="0 0 24 24" aria-hidden="true" '
        'focusable="false" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 19V10M10 19V5M16 19v-7M22 19V8"/></svg>'
        'Lihat laporan perkembangan <span aria-hidden="true">&rarr;</span></a>'
        "</div>"
        f'<div class="daftar-anak">{item}</div>'
        "</section>"
        '<div class="anak-kolom-kanan">'
        f"{latihan_manual}"
        f"</div></div></main>{skrip_bagikan}",
        ident=(pengguna if pengguna else "guru", peran),
        kelas_bungkus="lebar pendamping-editorial-st profil-editorial-st",
        privat=privat,
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
            f'style="margin-top:0">Variasi cerita &nbsp;✨</button></form>'
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
        f'<div class="kartu kartu-variasi"><h2>Variasi cerita ✨</h2>'
        f'<p class="sub">{catatan}</p>{tombol}</div>'
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
    """Pil navigasi di halaman sesi: Koreksi · Cetak & Cerita · Lampiran."""
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
        + _a("cetak", "Cetak & Cerita", f"/sesi/{sesi_id}/cetak")
        + _a("lampiran", f"Lampiran ({n_lamp})", f"/sesi/{sesi_id}/lampiran")
        + "</nav>"
    )


def halaman_sesi_cetak(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "",
) -> bytes | None:
    """Halaman cetak & cerita per sesi — lembar soal/kunci + variasi cerita."""
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
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">CETAK &amp; CERITA</p>'
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
        '<label for="foto-lembar">Foto lembar yang sudah diisi anak (jpeg/png, maks 8MB)</label>'
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
        + _a("cetak", "Cetak &amp; Cerita", f"/sesi/{sesi_id}/cetak")
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
                """SELECT sesi_soal_id, dilewati, cek_pemahaman
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
        "kosong": "Belum ada jawaban atau cara yang bisa dinilai. Catat yang benar-benar dikerjakan anak; bila tidak dikerjakan, buka Lewati soal ini dari penilaian.",
        "penilaian": "Penilaian belum ditentukan. Tanyakan cara anak, lalu pilih penilaian yang sesuai. Jangan menebak penilaian hanya agar bisa lanjut.",
        "tidak_konsisten": "Penilaian tersimpan belum konsisten. Periksa jawaban dan cara anak, lalu pilih kembali penilaian yang sesuai.",
    }
    masalah_per_butir = {sid: pesan_masalah[alasan] for sid, _, alasan in masalah_konfirmasi}
    kartu = []
    outcome_tampilan = []
    for b in database.isi_sesi(kon, sesi_id):
        soal = _soal_dari_baris(b)
        sudah = b["jawaban_id"] is not None
        kode = b["kode_final"]
        benar = b["benar"]

        restate = ""
        if b["restatement"]:
            restate = (
                '<div class="info-anak-st">'
                '<span class="info-anak-label-st">Dari anak:</span> '
                f'{html.escape(b["restatement"])}'
                "</div>"
            )

        draf_butir = draf_koreksi.untuk(int(b["sesi_soal_id"])) if draf_koreksi else None
        jawaban_tampil = draf_butir.jawaban if draf_butir else (b["jawaban"] or "")
        kode_tampil = draf_butir.kode if draf_butir else pilihan_tersimpan(b)
        cara_tampil = cara_untuk_form(draf_butir.cara if draf_butir else b["cara"] or "")
        belum_terpilih = (
            draf_butir.belum_pernah if draf_butir else bool(b["belum_pernah"])
        )
        cara_diagnosis = cara_dari_form(cara_tampil.strip(), b["cara"] or "")
        if drill:
            from students import AWALAN_DRILL
            cara_diagnosis = AWALAN_DRILL + cara_diagnosis
        rekomendasi = diagnosa(
            b["kunci"], jawaban_tampil, cara_diagnosis, b["restatement"] or "",
            belum_terpilih, database.malrule_soal(kon, b["soal_id"]), soal.minta_restatement,
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
        keterangan_otomatis = (
            "Usulan ini tidak dipakai selama penilaian guru dipilih."
            if kode_tampil else
            "Pilih penilaian di bawah sebelum mengonfirmasi."
            if belum_dinilai else
            "Dipakai otomatis saat konfirmasi. Jika jawaban, cara, atau pengalaman diubah, Jagomat menilai ulang."
        )
        penilaian_guru = (
            f'<p class="koreksi-catatan-st"><b>Penilaian guru:</b> '
            f'{html.escape(label_penilaian(kode_tampil))}. Pilihan ini tetap dipakai.</p>'
            if kode_tampil else ""
        )
        usulan = (
            f'<div class="usulan-st"><b>Usulan Jagomat: {html.escape(label_usulan)}</b>'
            f'<p class="koreksi-catatan-st">{keterangan_otomatis}</p>'
            f'{penilaian_guru}</div>'
        ) if not belum_dinilai else penilaian_guru
        label_otomatis = (
            "Belum yakin — perlu ditinjau" if belum_dinilai else "Gunakan usulan Jagomat"
        )
        pilihan_kode = [v for v, _ in KODE_PILIHAN if not (drill and v == "N")]
        if kode_tampil == "T":
            pilihan_kode.append("T")  # Override warisan, bukan kontrol pengalaman baru.
        pilih = "".join(
            f'<option value="{v}"{" selected" if v == kode_tampil else ""}>'
            f'{html.escape(label_otomatis if not v else dict(KODE_PILIHAN).get(v, "Perlu pengenalan").split(" — ")[-1].capitalize())}</option>'
            for v in pilihan_kode
        )

        masalah_butir = masalah_per_butir.get(int(b["sesi_soal_id"]))
        petunjuk_masalah = ""
        atribut_penilaian = ""
        atribut_kartu = ""
        if masalah_butir:
            sid = int(b["sesi_soal_id"])
            atribut_kartu = f' id="tinjau-soal-{sid}" tabindex="-1"'
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
    <div class="teks-soal-st">{visual_renderer.render_pertanyaan(question_views.penyajian_dari_baris(b), gaya="guru", namespace=str(b["nomor"]))}</div>
    <div class="kunci-baris-st">Kunci: <span class="kunci-val">{html.escape(b["kunci"])}</span></div>
  </div>
</div>""")
            continue

        cara_html = ""
        if not drill:
            cara_html = (
                f'<label class="koreksi-label-st" for="cara-{b["sesi_soal_id"]}">Bagaimana anak mendapatkan jawabannya?</label>'
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
            snapshot_butir["cek_pemahaman"] if snapshot_butir is not None else None
        )
        dilewati_terpilih = (
            draf_butir.dilewati if draf_butir else
            bool(snapshot_butir is not None and snapshot_butir["dilewati"])
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
        ringkas = bool(benar_tampil and not (
            cek_penguasaan or perlu_perhatian or masalah_butir or dilewati_terpilih
        ))
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
      <p class="koreksi-tanya-st">Tanyakan: “Kamu dapat jawaban ini dari mana?”</p>
      {petunjuk_pemahaman}
      <fieldset class="koreksi-radio-paham-st">
        <legend>Apakah anak bisa menjelaskan caranya?</legend>
        <div class="koreksi-pilihan-paham-grid-st">{pilihan_pemahaman}</div>
      </fieldset>
      {cara_html}
      <details class="koreksi-opsi-st koreksi-pengalaman-st"{" open" if belum_terpilih else ""}>
        <summary>{"Anak belum mengenal soal ini — dicatat" if belum_terpilih else "Anak belum mengenal soal ini?"}</summary>
        <div class="koreksi-centang-st">
          <input type="hidden" name="hadir_belum_{b["sesi_soal_id"]}" value="1">
          <input type="checkbox" id="bp{b["sesi_soal_id"]}"
               name="belum_{b["sesi_soal_id"]}" value="1"
               {"checked" if belum_terpilih else ""} aria-describedby="belum-info-{b["sesi_soal_id"]}">
          <label for="bp{b["sesi_soal_id"]}"><span class="info-anak-label-st">Dari anak:</span> Belum pernah melihat soal seperti ini</label>
        </div>
        <p class="koreksi-catatan-st" id="belum-info-{b["sesi_soal_id"]}">Centang hanya jika anak mengatakannya, bukan karena ia bingung. Pada penilaian otomatis, ini mengarah ke pengenalan materi, bukan kesalahan anak.</p>
      </details>
    </fieldset>"""
        if benar_tampil:
            judul_catatan = (
                "Cek pemahaman" if cek_penguasaan else
                "Catatan pendampingan — perlu perhatian" if perlu_perhatian else
                "Catatan pendampingan (opsional)"
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
            "Penilaian: " + label_penilaian("benar" if benar_tampil else kode_efektif) + " — ubah"
        )
        kartu.append(f"""
<div class="koreksi-kartu-st"{atribut_kartu}>
  <div class="koreksi-isi-st {kelas_isi}">
    <div class="koreksi-kepala-st">{nomor}{tipe}{status}</div>
    {petunjuk_masalah}
    <div class="teks-soal-st">{visual_renderer.render_pertanyaan(question_views.penyajian_dari_baris(b), gaya="guru", namespace=str(b["nomor"]))}</div>
    <details class="koreksi-opsi-st"><summary>Lihat kunci &amp; pembahasan</summary>
      <div class="kunci-baris-st">Kunci: <span class="kunci-val">{html.escape(b["kunci"])}</span></div>
      {pembahasan_html}
    </details>
    {restate}
    <div class="koreksi-bukti-st koreksi-bukti-tunggal-st">
      <div>
        <label class="koreksi-label-st" for="jwb-{b["sesi_soal_id"]}">Jawaban anak</label>
        <input type="text" class="koreksi-input-st" id="jwb-{b["sesi_soal_id"]}" name="jwb_{b["sesi_soal_id"]}"
               value="{html.escape(jawaban_tampil)}">
      </div>
    </div>
    {pendampingan}
    <details class="koreksi-opsi-st koreksi-penilaian-st"{" open" if masalah_butir else ""}>
      <summary>{judul_penilaian}</summary>
      {usulan}
      <label class="koreksi-label-st" for="kode-{b["sesi_soal_id"]}">Penilaian yang dipakai</label>
      <select class="koreksi-select-st" id="kode-{b["sesi_soal_id"]}" name="kode_{b["sesi_soal_id"]}"{atribut_penilaian}>{pilih}</select>
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
        <p class="koreksi-catatan-st">Otomatis menilai ulang jawaban dan cara saat konfirmasi. Pilihan lain adalah keputusan guru, bukan usulan Jagomat.</p>
        <p class="koreksi-catatan-st"><b>Jagomat:</b> {html.escape(rekomendasi.alasan)}</p>
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
    {bantuan if bantuan_nomor == int(b["nomor"]) else ""}
  </div>
</div>""")

    kabar = f'<div class="pesan-st">{html.escape(pesan)}</div>' if pesan else ""
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
        if bantuan and (bantuan_nomor is None or not sudah_dikirim):
            # Sesi belum dikirim belum mempunyai kartu koreksi. Bantuan soal
            # tetap muncul di pengantar tanpa membuka koreksi lebih dini.
            konteks_pendamping = bantuan
        else:
            if sudah_dikirim:
                import assistant_components
                import assistant_inline
                tautan_soal = "".join(
                    assistant_components.tombol_buka(
                        assistant_inline.tujuan_sesi(sesi_id, nomor=int(b["nomor"])),
                        form_id=f"form-koreksi-{sesi_id}", label=f'Bahas soal {int(b["nomor"])}',
                    ) for b in database.isi_sesi(kon, sesi_id)
                )
            else:
                tautan_soal = "".join(
                    f'<a href="/sesi/{sesi_id}?bantuan=soal&amp;nomor={int(b["nomor"])}#bantuan-soal-{int(b["nomor"])}">'
                    f'Bahas soal {int(b["nomor"])}</a>'
                    for b in database.isi_sesi(kon, sesi_id)
                )
            if sudah_dikirim:
                tautan_sesi = assistant_components.tombol_buka(
                    assistant_inline.tujuan_sesi(sesi_id),
                    form_id=f"form-koreksi-{sesi_id}", label="Bahas sesi ini",
                )
            else:
                tautan_sesi = f'<a href="/sesi/{sesi_id}?bantuan=sesi#bantuan-sesi">Bahas sesi ini</a>'
            konteks_pendamping = (
                '<details class="alat-pendamping-st"><summary>Bahas dengan Pendamping</summary>'
                f'{tautan_sesi}{tautan_soal}</details>'
            )
    if not sudah_dikirim:
        pil = pil.replace(">Koreksi</a>", ">Soal &amp; kunci</a>")

    blok_remedial = ""
    blok_latihan_serupa = ""
    if sudah_dikirim and info["direview"]:
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
    if sudah_dikirim:
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
                    '<div class="status-sesi-st selesai">'
                    '<span class="material-symbols-outlined">rule</span>'
                    f'<div><b>{"Koreksi berubah — konfirmasi ulang diperlukan" if pernah_dikonfirmasi else "Tinjau jawaban, cara, dan pemahaman anak"}</b>'
                    '<p>Periksa catatan anak dan usulan Jagomat. Jika sudah sesuai, '
                    'konfirmasi hasil untuk menyimpan seluruh isian sekaligus mengesahkan bukti belajar.</p>'
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
            label_konfirmasi = "Konfirmasi ulang" if pernah_dikonfirmasi else "Konfirmasi hasil"
            aksi_konfirmasi = (
                f'<button type="submit" formaction="/sesi/{sesi_id}/konfirmasi">'
                f'{label_konfirmasi}</button>'
            )
        if sesi_dibatalkan:
            blok_isi = "".join(kartu)
        else:
            # Submit default disabled memblokir implicit Enter secara native.
            # Hanya tombol konfirmasi yang dipilih eksplisit mengesahkan bukti.
            urutan_aksi = (
                '<p class="koreksi-catatan-st">Konfirmasi menyimpan jawaban, penilaian, '
                'cek pemahaman, dan pilihan lewati sekaligus. Tidak perlu menyimpan terpisah.</p>'
                f'{aksi_konfirmasi}'
            )
            form_hasil = (
                f'<form id="form-koreksi-{sesi_id}" method="post" action="/sesi/{sesi_id}">'
                f'{"".join(kartu)}<input type="hidden" name="hadir_sertakan_pemetaan" value="1">{opsi_pemetaan}'
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
            ikon_status = "pending_actions" if sudah_mulai else "send"
            penjelasan_status = (
                f'Terisi {info["terisi"]} dari {info["jumlah_soal"]}. '
                'Tunggu anak menekan “Selesai &amp; kirim” sebelum meninjau.'
                if sudah_mulai else
                'Bagikan tautan sesi, lalu biarkan anak mencoba dengan caranya sendiri.'
            )
            label_bagikan = (
                "Bagikan ulang ke anak" if sudah_mulai else
                "Buat tautan baru" if tautan_aktif else
                "Bagikan sesi ke anak"
            )
            konfirmasi_rotasi = (
                ' onsubmit="return confirm(\'Membuat tautan baru akan '
                'menonaktifkan tautan sebelumnya. Lanjutkan?\')"'
                if tautan_aktif else ""
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
                f'<span class="material-symbols-outlined">{ikon_status}</span>'
                f'<div><b>{label_status}</b>{marker_status_lama}'
                f'<p>{penjelasan_status}</p>'
                f'<form class="{kelas_aksi}" method="post" '
                f'action="/sesi/{sesi_id}/bagikan"{konfirmasi_rotasi}>'
                f'<button type="submit">{label_bagikan}</button></form>'
                '</div></section>'
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
            hasil_pemetaan = mapping_results.render_sementara(
                outcome_tampilan, draf_gagal=bool(masalah_konfirmasi),
            )
    if hasil_pemetaan:
        label_tab = "Hasil pemetaan" if rencana_pemetaan else "Ringkasan &amp; tinjauan"
        pil = pil.replace(">Koreksi</a>", f">{label_tab}</a>")
    tautan_profil = f'/anak/{info["siswa_id"]}'
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
        f"{status_sesi}"
        f"{hasil_pemetaan}{rencana_pemetaan}"
        f"{aksi_rencana}"
        f"{blok_isi}"
        f"{alat_lanjutan}"
        f'<div class="danger-zone-st">'
        f'<p class="sub">{keterangan_bahaya}</p>'
        f'{aksi_bahaya_tampil}</div>'
        f"</main>"
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
{brand.tag_kepala()}
{'' if (bantuan or privat) else '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">'}
<style>{gaya_sesi}{CSS_SESI}{mapping_results.GAYA_HASIL if hasil_pemetaan else ''}</style></head>
<body class="st"><div class="bungkus-st pendamping-editorial-st koreksi-editorial-st">{batang}{isi}</div>{skrip_extra}</body></html>"""
    ).encode()


def simpan_sesi(kon, sesi_id: int, data: dict) -> str:
    """Simpan koreksi guru tanpa mengubah kontrak mode sesi."""
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
        jwb = data.get(f"jwb_{sid}", "").strip()
        cara = cara_dari_form(data.get(f"cara_{sid}", "").strip(), b["cara"] or "")
        restate = b["restatement"] or ""
        belum = f"belum_{sid}" in data
        pilihan = data.get(f"kode_{sid}", "").strip()
        kode_diizinkan = {nilai for nilai, _label in KODE_PILIHAN if nilai}
        if b["manual"] and b["kode_final"] == "T":
            kode_diizinkan.add("T")  # Hanya mempertahankan override warisan.
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
        u = diagnosa(
            b["kunci"], jwb, cara_diagnosis, restate, belum,
            database.malrule_soal(kon, b["soal_id"]),
            soal.minta_restatement,
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
                timer_auto=timer_auto, jumlah_soal=jumlah_soal,
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
