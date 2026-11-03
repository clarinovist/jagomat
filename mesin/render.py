"""Render lembar soal jadi HTML — struktur saja, tanpa CSS.

Dipecah dari worksheets.py (Fase 3). Pemisahan tiga lapis:

  render.py       struktur DOM (fungsi di berkas ini)
  screen_style.py   tampilan browser/HP
  print_style.py   tampilan kertas A4

Struktur DOM-nya identik untuk kedua tampilan, sehingga test yang menjaga
kontrak — terutama "berkas anak tidak boleh memuat kunci" — cukup ditulis
sekali dan berlaku untuk keduanya.

Dua berkas per sesi, dan pemisahan ini tidak boleh dilanggar:

  <sesi>-SOAL.html      dipegang anak — TIDAK boleh memuat kunci
  <sesi>-PENILAIAN.html dipegang guru — kunci + tabel malrule

Alasan pemisahan: begitu kunci terlihat anak, dua kode yang paling berharga
(N menebak, K salah konsep) hilang selamanya dari data. Ada test yang
memastikan berkas anak tidak mengandung kunci.

Diagram digambar sebagai SVG, bukan ASCII: font monospace tidak dijamin ada
di headless Chrome, dan seni ASCII dari '/' dan '\\' berubah jadi coretan
tak beraturan saat font-nya proporsional.
"""

from __future__ import annotations

import html
import json

import brand
import visual_renderer
import design_tokens as T
from print_style import GAYA_CETAK
from templates import Soal
from topics import Topik, paket_bawaan


def _badan_soal(soal: Soal, topik_paket: Topik | None = None,
                 namespace: str = "soal") -> str:
    """Teks soal + diagram. Paket topik boleh mengambil alih bentuk
    khusus (deret ditebalkan, diagram SVG); sisanya renderer teks bawaan:
    baris pertama jadi badan, sisanya jadi pertanyaan."""
    if soal.penyajian is not None:
        return visual_renderer.render_pertanyaan(
            soal.penyajian, gaya="cetak", namespace=namespace
        )
    if topik_paket is None:
        topik_paket = paket_bawaan()
    khusus = topik_paket.render_badan
    if khusus is not None:
        hasil = khusus(soal)
        if hasil is not None:
            return hasil

    baris = [b for b in soal.teks.split("\n") if b.strip()]
    if len(baris) == 1:
        return f'<div class="teks">{html.escape(baris[0])}</div>'
    isi = "".join(
        f'<div class="{"tanya" if i == len(baris) - 1 else "teks"}">'
        f"{html.escape(b.strip())}</div>"
        for i, b in enumerate(baris)
    )
    return isi


def _kartu_soal(nomor: int, soal: Soal, topik_paket: Topik | None = None) -> str:
    """Satu kartu soal dengan kotak-kotak diagnostik.

    Tinggi kotak 'Caraku' disesuaikan bagian: soal terbalik, tantangan, dan
    Bagian F butuh ruang lebih — soal terbalik dan Bagian F karena anak
    biasanya menulis deret panjang atau coretan rumus di situ.
    """
    tinggi = "besar" if soal.bagian in ("D", "E", "F") else (
        "sedang" if soal.bagian == "C" else "kecil"
    )

    restate = ""
    if soal.minta_restatement:
        restate = (
            '<div class="label">Soal ini mintanya apa? '
            "(tulis pakai kalimatmu sendiri)</div>"
            '<div class="restate"></div>'
        )

    lebar = "lebar" if soal.template_id in (
        "siklus_warna", "siklus_hari", "siklus_huruf"
    ) else ""
    n_isian = soal.parameter.get("n_minta", 1) if soal.template_id == "deret_aritmetika" else 1
    isian = " dan ".join(f'<span class="isian {lebar}"></span>' for _ in range(n_isian))

    awalan = "urutan ke-" if soal.template_id.startswith("deret_terbalik") else ""
    bintang = ' <span class="bintang">★</span>' if soal.tantangan else ""

    return (
        f'<div class="soal">'
        f'<span class="nomor">{nomor}</span>{bintang}'
        f"{_badan_soal(soal, topik_paket, str(nomor))}"
        f"{restate}"
        f'<div class="label">Caraku:</div>'
        f'<div class="cara {tinggi}"></div>'
        f'<div class="jawab">Jawabanku: {awalan}{isian}</div>'
        f'<div class="centang"><span class="kotak"></span>'
        f"belum pernah lihat soal seperti ini</div>"
        f"</div>"
    )


def _isi_lembar(soal: list[Soal], topik_paket: Topik) -> list[str]:
    """Kartu-kartu soal + judul bagian, urut sesuai komposisi lembar.

    Judul dan catatan bagian milik paket topik — bukan milik renderer."""
    isi, bagian_kini = [], None
    for i, s in enumerate(soal, start=1):
        if s.bagian != bagian_kini:
            bagian_kini = s.bagian
            judul = topik_paket.judul_bagian.get(bagian_kini, f"Bagian {bagian_kini}")
            isi.append(f'<div class="bagian">{judul}</div>')
            if bagian_kini in topik_paket.catatan_bagian:
                isi.append(f'<div class="catatan-bagian">'
                           f"{topik_paket.catatan_bagian[bagian_kini]}</div>")
        isi.append(_kartu_soal(i, s, topik_paket))
    return isi


def lembar_soal(
    soal: list[Soal],
    nama: str = "",
    tanggal: str = "",
    gaya: str | None = None,
    topik_paket: Topik | None = None,
) -> str:
    """HTML lembar anak. Tidak memuat kunci — dijaga oleh test.

    gaya: CSS mentah. Default GAYA_CETAK supaya pemanggil lama (cetak CLI,
    PDF via browser) tetap menghasilkan kertas yang sama persis; web
    (web.py) memanggil dengan GAYA_LAYAR.
    topik_paket: judul dari paket topik; None berarti paket bawaan.
    """
    css = GAYA_CETAK if gaya is None else gaya
    if topik_paket is None:
        topik_paket = paket_bawaan()
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(topik_paket.judul_lembar))}</title>
{brand.tag_kepala(cetak=True)}<style>{css}</style></head><body class="lembar-editorial">
<main class="wrap">
<div class="mesin-banner">
  <span class="nama-app">{html.escape(T.NAMA_PRODUK)}</span>
  <span class="meta-sesi">{html.escape(nama)} &middot; {len(soal)} soal</span>
</div>
<h1>{html.escape(topik_paket.judul_lembar)}</h1>
<div class="identitas">
  <span>Nama: <span class="garis">{html.escape(nama)}</span></span>
  <span>Tanggal: <span class="garis pendek">{html.escape(tanggal)}</span></span>
  <span>Mulai: <span class="garis pendek"></span></span>
  <span>Selesai: <span class="garis pendek"></span></span>
</div>
<div class="petunjuk">
  <p><b>Cara mengerjakan — baca dulu:</b></p>
  <p>Tiap soal ada kotak <b>Caraku</b>. Tulis di situ bagaimana kamu dapat
  jawabannya. Boleh berantakan, boleh dicoret-coret. Yang penting kelihatan
  caramu.</p>
  <p>Kalau ada soal yang belum pernah kamu lihat, centang kotaknya. Itu
  <b>bukan</b> salah — itu menandakan soalnya memang baru, dan itu berguna.</p>
  <p>Tidak apa-apa ada yang kosong. Jangan menebak asal.</p>
</div>
{"".join(_isi_lembar(soal, topik_paket))}
<div class="akhir"><b>Sudah selesai?</b> Cek sekali lagi: apakah setiap kotak
"Caraku" ada isinya? Kalau ada jawaban yang kamu tulis tanpa cara, tulis dulu
caranya sekarang.</div>
</main>
</body></html>"""


def lembar_penilaian(
    soal: list[Soal],
    nama: str = "",
    tanggal: str = "",
    seed: int | None = None,
    gaya: str | None = None,
    topik_paket: Topik | None = None,
) -> str:
    """HTML lembar guru: kunci + tabel malrule + rekap."""
    baris = []
    for i, s in enumerate(soal, start=1):
        mal = "".join(
            f"<tr><td><span class=\"kode\">{m.kode}</span></td>"
            f"<td><b>{html.escape(m.jawaban)}</b></td>"
            f"<td>{html.escape(m.alasan)}</td></tr>"
            for m in s.malrule
        )
        tabel = (
            '<table class="kunci-tabel">'
            "<tr><th>Kode</th><th>Kalau dijawab</th><th>Artinya</th></tr>"
            f"{mal}</table>"
            if mal else '<div class="catatan-guru">'
                        "(tidak ada pola kesalahan terdaftar — baca kotak Caraku)</div>"
        )
        param = html.escape(json.dumps(s.parameter, ensure_ascii=False))
        baris.append(
            f'<div class="soal"><span class="nomor">{i}</span>'
            f'<span class="meta-template">{s.template_id} '
            f"<code>{param}</code></span>"
            f'<div class="kunci-nilai">'
            f"Kunci: {html.escape(s.kunci)}</div>{tabel}</div>"
        )

    rekap = "".join(
        f"<tr><td>{i}{' ★' if s.tantangan else ''}</td>"
        f"<td>{'&nbsp;' if s.minta_restatement else '—'}</td>"
        f"<td></td><td></td><td></td></tr>"
        for i, s in enumerate(soal, start=1)
    )

    css = GAYA_CETAK if gaya is None else gaya
    if topik_paket is None:
        topik_paket = paket_bawaan()
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(topik_paket.judul_penilaian))}</title>
{brand.tag_kepala(cetak=True)}<style>{css}</style></head><body class="lembar-editorial">
<main class="wrap">
<div class="mesin-banner banner-kunci">
  <span class="nama-app">{html.escape(T.NAMA_PRODUK)}</span>
  <span class="meta-sesi">{html.escape(nama)} &middot; {len(soal)} soal</span>
</div>
<div class="kunci-headline">Kunci — Rahasia Guru</div>
<h1>Lembar {html.escape(topik_paket.judul_penilaian)}</h1>
<div class="identitas">
  <span>Nama: <b>{html.escape(nama) or "______"}</b></span>
  <span>Tanggal: <b>{html.escape(tanggal) or "______"}</b></span>
  {f"<span>seed: <code>{seed}</code></span>" if seed is not None else ""}
</div>
<div class="petunjuk">
  <p><b>Jangan diperlihatkan ke anak.</b></p>
  <p><b>Metrik utama = jumlah K, bukan skor.</b> Anak dengan 9 H skor 3 lebih
  siap daripada anak dengan 3 K skor 9.</p>
  <p>Alur baca, berhenti di yang pertama cocok:
  centang "belum pernah lihat" → <b>T</b>;
  jawaban tanpa Caraku → <b>N</b>;
  "mintanya apa" salah → <b>B</b>;
  cara/aturannya keliru → <b>K</b>;
  jawaban ≠ hasil di Caraku → <b>E</b>; selain itu salah hitung → <b>H</b>.</p>
</div>
{"".join(baris)}
<div class="bagian">Rekap</div>
<table class="rekap">
<tr><th>No</th><th>"Mintanya apa"</th><th>Jawaban</th><th>Kode</th>
<th>Catatan</th></tr>
{rekap}
</table>
<div class="akhir">
<p><b>Jumlah K: ______</b> ← angka yang dipantau</p>
<p><b>Jumlah T: ______</b> ← bukan kegagalan, ini peta materi yang belum diajarkan</p>
<p>Miskonsepsi yang muncul (tulis gagasannya, bukan nomor soalnya):</p>
<p>1. ______________________________________________</p>
<p>2. ______________________________________________</p>
<p>3. ______________________________________________</p>
</div>
</main>
</body></html>"""


def tulis(path, isi: str):
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(isi, encoding="utf-8")
    return path
