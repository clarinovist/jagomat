"""Presentasi laporan orang tua: satu kolom, tanpa skrip atau tautan keluar.

Halaman ini hanya memakai nama anak, periode, snapshot allowlist
(:func:`parent_report.isi_tampil`), catatan guru, dan tanggal. Tidak ada
skor, persentase, kode diagnosis, ID sesi, level, atau kelas sekolah.
``<title>`` generik supaya pratinjau tautan chat tidak memuat nama anak.

Modul ini sengaja tidak mengimpor renderer laporan guru (``reports``,
``report_*``, ``mastery_report``, ``cycle_report``): satu-satunya jalan masuk
data adalah argumen fungsi. Dengan begitu kolom baru di laporan guru tidak
otomatis menjadi kebocoran di sini.
"""
from __future__ import annotations

import html
from datetime import date

import brand
import design_tokens as T
import parent_report
from format_tanggal import tanggal_pendek

# Gaya kecil khusus halaman ini. Tanpa @import webfont: halaman ber-token
# tidak boleh melakukan permintaan jaringan ke pihak ketiga.
TATA_LETAK = f"""
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{background:{T.LATAR_MURID};color:{T.TEKS_UTAMA};
font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
font-size:17px;line-height:1.65;-webkit-text-size-adjust:100%}}
.laporan-ortu-st{{max-width:34rem;margin:0 auto;padding:1.5rem 1.25rem 3rem}}
.laporan-ortu-brand{{display:flex;align-items:center;gap:.5rem;font-weight:700;
color:{T.TEKS_JUDUL};margin-bottom:1.75rem}}
.laporan-ortu-st h1,.laporan-ortu-st h2{{color:{T.TEKS_JUDUL};line-height:1.25}}
.laporan-ortu-st h1{{font-size:1.7rem;margin:0 0 .25rem}}
.laporan-ortu-st h2{{font-size:1.05rem;margin:0 0 .35rem}}
.laporan-ortu-anak{{font-size:1.15rem;font-weight:600;margin:0}}
.laporan-ortu-periode,.laporan-ortu-meta{{color:{T.TEKS_SUBTLE};margin:.15rem 0 0}}
.laporan-ortu-st section{{border-top:1px solid {T.CETAK_GARIS_TULIS};padding:1.1rem 0;
break-inside:avoid}}
.laporan-ortu-st ul{{margin:.35rem 0 0;padding-left:1.25rem}}
.laporan-ortu-catatan{{white-space:pre-line;margin:.35rem 0 0}}
.laporan-ortu-catatan-kutip{{border-left:3px solid {T.AKSEN_MURID_UTAMA};
padding-left:.85rem;margin:.5rem 0 0}}
.laporan-ortu-catatan-kutip p{{margin:0}}
.laporan-ortu-tahap{{font-weight:600;margin:.2rem 0}}
.laporan-ortu-tanda{{font-size:.92rem;color:{T.TEKS_SUBTLE};margin:1.5rem 0 0}}
@media print{{
body{{background:#fff;color:{T.CETAK_TINTA}}}
.laporan-ortu-st{{max-width:none;padding:0}}
@page{{margin:18mm}}
}}
"""

_TAHAP_KETERANGAN = (
    "Anak dan guru mengenali cara anak membaca soal dan mengerjakan latihan.",
    "Anak mempelajari satu cara yang cocok untuk bagian yang masih sulit.",
    "Anak berlatih mengerjakan soal, dengan bantuan yang makin berkurang.",
    "Guru mengecek apakah pemahaman bertahan setelah beberapa hari.",
    "Guru mengecek kembali pemahaman tanpa contoh atau catatan lama.",
    "Anak melanjutkan ke latihan campuran atau ke bagian berikutnya.",
)


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def tanggal_tag(nilai, *, kelas: str = "") -> str:
    """``<time>`` bila nilainya tanggal; teks apa adanya bila data warisan aneh."""
    teks = str(nilai or "")
    try:
        tanggal = nilai if isinstance(nilai, date) else date.fromisoformat(teks[:10])
    except ValueError:
        return f'<span class="{kelas}">{_e(teks or "—")}</span>' if kelas else _e(teks or "—")
    atribut = f' class="{kelas}"' if kelas else ""
    return (f'<time{atribut} datetime="{tanggal.isoformat()}">'
            f'{_e(tanggal_pendek(tanggal))}</time>')


def _periode(mulai, akhir) -> str:
    if str(mulai)[:10] == str(akhir)[:10]:
        return tanggal_tag(mulai)
    return f'{tanggal_tag(mulai)} – {tanggal_tag(akhir)}'


def isi_laporan(
    nama,
    periode_mulai,
    periode_akhir,
    isi,
    catatan,
    guru,
    diterbitkan,
    berlaku_sampai,
    *,
    tingkat_judul: int = 1,
    id_judul: str = "judul-laporan",
) -> str:
    """Isi laporan yang sama untuk halaman orang tua dan pratinjau guru."""
    tampil = parent_report.isi_tampil(isi)
    judul = "h1" if tingkat_judul == 1 else "h2"
    bagian = [
        f'<{judul} id="{_e(id_judul)}">Laporan belajar</{judul}>',
        f'<p class="laporan-ortu-anak">{_e(nama)}</p>',
        f'<p class="laporan-ortu-periode">{_periode(periode_mulai, periode_akhir)}</p>',
    ]
    bagian.append('<section aria-labelledby="bagian-dilatih">'
                  '<h2 id="bagian-dilatih">Yang dilatih</h2>')
    if tampil["topik"]:
        bagian.append('<ul>' + "".join(
            f'<li>{_e(topik)}</li>' for topik in tampil["topik"]
        ) + '</ul>')
    else:
        bagian.append('<p>Belum ada latihan yang dikonfirmasi pada periode ini.</p>')
    bagian.append('</section>')

    bagian.append('<section aria-labelledby="bagian-tahap">'
                  '<h2 id="bagian-tahap">Tahap belajar sekarang</h2>')
    tahap = tampil["tahap"]
    if tahap:
        keterangan = _TAHAP_KETERANGAN[tahap["nomor"] - 1]
        bagian.append(
            f'<p class="laporan-ortu-tahap">{_e(tahap["label"])} '
            f'({tahap["nomor"]} dari 6)</p><p>{_e(keterangan)}</p>'
        )
    else:
        bagian.append('<p>Tahap belum bisa ditunjukkan saat ini.</p>')
    bagian.append('</section>')

    bagian.append('<section aria-labelledby="bagian-langkah">'
                  '<h2 id="bagian-langkah">Langkah berikutnya</h2>'
                  f'<p>{_e(tampil["langkah"])}</p></section>')

    teks_catatan = str(catatan or "")
    if teks_catatan.strip():
        bagian.append(
            '<section aria-labelledby="bagian-catatan">'
            '<h2 id="bagian-catatan">Catatan guru</h2>'
            f'<div class="laporan-ortu-catatan-kutip">'
            f'<p class="laporan-ortu-catatan">{_e(teks_catatan)}</p></div></section>'
        )

    meta = []
    if diterbitkan:
        baris = f'Diterbitkan {tanggal_tag(diterbitkan)}'
        if guru:
            baris += f' oleh {_e(guru)}'
        meta.append(f'<p>{baris}.</p>')
    meta.append(
        '<p>Latihan bukan penilaian akhir. Halaman ini bukan rapor dan tidak '
        'memuat skor.</p>'
    )
    if berlaku_sampai:
        meta.append(
            '<p>Tautan ini hanya untuk dibaca. Simpan atau cetak bila perlu. '
            f'Berlaku sampai {tanggal_tag(berlaku_sampai)}.</p>'
        )
    bagian.append('<footer class="laporan-ortu-tanda">' + "".join(meta) + '</footer>')
    return "".join(bagian)


def halaman_orang_tua(
    nama,
    periode_mulai,
    periode_akhir,
    isi,
    catatan,
    guru,
    diterbitkan,
    berlaku_sampai,
) -> bytes:
    """Dokumen utuh halaman baca-saja; ``<title>`` generik tanpa nama anak."""
    isi_html = isi_laporan(
        nama, periode_mulai, periode_akhir, isi, catatan, guru,
        diterbitkan, berlaku_sampai,
    )
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(brand.judul("Laporan belajar"))}</title>
{brand.tag_kepala()}<style>{TATA_LETAK}</style></head>
<body><main class="laporan-ortu-st" aria-labelledby="judul-laporan">
<header class="laporan-ortu-brand">{brand.mark("topbar")}<span>{_e(T.NAMA_PRODUK)}</span></header>
{isi_html}
</main></body></html>""".encode()


def halaman_tidak_ada() -> bytes:
    """Satu halaman 404 identik untuk semua keadaan tautan yang tidak sah.

    Tanpa tautan, tanpa ``Set-Cookie``, tanpa petunjuk apakah token pernah ada
    (404, bukan 410). Query string tidak pernah dipantulkan ke badan halaman.
    """
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(brand.judul("Laporan tidak dapat dibuka"))}</title>
{brand.tag_kepala()}<style>{TATA_LETAK}</style></head>
<body><main class="laporan-ortu-st" aria-labelledby="judul-tidak-ada">
<header class="laporan-ortu-brand">{brand.mark("topbar")}<span>{_e(T.NAMA_PRODUK)}</span></header>
<h1 id="judul-tidak-ada">Laporan tidak dapat dibuka</h1>
<p>Tautan ini sudah tidak berlaku. Minta tautan baru kepada guru anak Anda.</p>
</main></body></html>""".encode()


def kartu_masuk(siswa_id: int) -> str:
    """Satu entry point di tab Perkembangan; tanpa form dan tanpa skrip."""
    return (
        '<section class="kartu-laporan-ortu-st" aria-labelledby="judul-kartu-laporan-ortu">'
        '<h2 id="judul-kartu-laporan-ortu">Laporan untuk orang tua</h2>'
        '<p>Susun satu laporan dari latihan yang sudah dikonfirmasi, lalu bagikan '
        'sebagai tautan baca-saja. Isinya tanpa skor: topik, tahap belajar, '
        'langkah berikutnya, dan catatan Anda.</p>'
        '<p><a class="tautan-laporan-ortu-st" href="/anak/%d/laporan-ortu">'
        'Buka laporan untuk orang tua</a></p></section>' % int(siswa_id)
    )
