"""Halaman baca-saja laporan untuk orang tua (tanpa login, lewat tautan bearer).

Modul ini sengaja terpisah dari semua renderer laporan guru: hanya mengimpor stdlib
dan token desain. Masukannya dipilih dengan ALLOWLIST (nama, topik, tahap, uraian,
langkah, catatan, guru, periode, tanggal) sehingga kunci tak dikenal pada payload
tidak pernah tampil. Tidak ada skrip, formulir, tautan, gambar, atau alamat luar.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import design_tokens as T

_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")
_WIB = timezone(timedelta(hours=7))
JUDUL = "Laporan belajar"


def _esc(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _tanggal(iso: str):
    tahun, bulan, hari = (int(x) for x in str(iso)[:10].split("-"))
    return hari, bulan, tahun


def _tanggal_panjang(iso: str) -> str:
    hari, bulan, tahun = _tanggal(iso)
    return f"{hari} {_BULAN[bulan - 1]} {tahun}"


def _rentang(mulai: str, akhir: str) -> str:
    h1, b1, t1 = _tanggal(mulai)
    h2, b2, t2 = _tanggal(akhir)
    if (b1, t1) == (b2, t2):
        awal = str(h1) if h1 != h2 else ""
        return (f"{awal} – " if awal else "") + _tanggal_panjang(akhir)
    if t1 == t2:
        return f"{h1} {_BULAN[b1 - 1]} – {h2} {_BULAN[b2 - 1]} {t2}"
    return f"{_tanggal_panjang(mulai)} – {_tanggal_panjang(akhir)}"


def _batas(epoch) -> str:
    waktu = datetime.fromtimestamp(int(epoch), tz=_WIB)
    return f"{waktu.day} {_BULAN[waktu.month - 1]} {waktu.year}"


_GAYA = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{T.LATAR_INTI};color:{T.TEKS_UTAMA};font-family:{T.FONT_CETAK};
font-size:1.0625rem;line-height:1.65}}
main{{max-width:34rem;margin:0 auto;padding:{T.SP_5} {T.SP_4} {T.SP_6};background:{T.LATAR_KARTU}}}
@media (min-width:36rem){{main{{margin-top:{T.SP_5};border-radius:{T.RADIUS_KARTU};border:1px solid {T.BORDER_HALUS}}}}}
.merek{{font-weight:700;color:{T.TEKS_JUDUL};margin:0 0 {T.SP_4}}}
h1{{font-size:1.5rem;line-height:1.3;margin:0;color:{T.TEKS_JUDUL}}}
.anak{{font-size:1.25rem;font-weight:700;margin:{T.SP_1} 0 0}}
.periode{{color:{T.TEKS_SUBTLE};margin:0 0 {T.SP_5}}}
section{{margin:0 0 {T.SP_5}}}
h2{{font-size:1.0625rem;margin:0 0 {T.SP_2};color:{T.TEKS_JUDUL}}}
ul{{margin:0;padding-left:1.25rem}}
p{{margin:0 0 {T.SP_2}}}
.tahap{{font-weight:700}}
.catatan{{white-space:pre-line;background:{T.LATAR_CATATAN};border:1px solid {T.BORDER_CATATAN};
border-radius:{T.RADIUS_SEDANG};padding:{T.SP_3} {T.SP_4}}}
.kecil{{color:{T.TEKS_SUBTLE};font-size:.9375rem}}
footer{{border-top:1px solid {T.BORDER_HALUS};padding-top:{T.SP_4}}}
@media print{{body{{background:#fff;color:#000}}main{{max-width:none;margin:0;padding:0;border:0}}
section,footer{{break-inside:avoid;page-break-inside:avoid}}@page{{margin:18mm}}}}
"""


def _dokumen(isi: str) -> bytes:
    return (
        '<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{_esc(JUDUL)} — {_esc(T.NAMA_PRODUK)}</title>"
        f"<style>{_GAYA}</style></head><body><main>{isi}</main></body></html>"
    ).encode("utf-8")


def _bagian_topik(topik) -> str:
    if not topik:
        return "<p>Belum ada latihan yang sudah diperiksa guru pada periode ini.</p>"
    return "<ul>" + "".join(f"<li>{_esc(t)}</li>" for t in topik) + "</ul>"


def _bagian_tahap(tahap) -> str:
    if not isinstance(tahap, dict):
        return "<p>Tahap belum bisa ditunjukkan saat ini.</p>"
    return (f'<p class="tahap">{_esc(tahap.get("label", ""))} ({_esc(tahap.get("nomor", ""))} dari 6)</p>'
            f"<p>{_esc(tahap.get('uraian', ''))}</p>")


def render_laporan(*, nama, isi, catatan, guru, periode, diterbitkan, kedaluarsa) -> bytes:
    """Satu laporan terbit. Hanya field allowlist yang dibaca dari `isi`."""
    topik = [str(t) for t in (isi.get("topik") or [])]
    bagian_catatan = ""
    if str(catatan).strip():
        bagian_catatan = (f'<section aria-labelledby="h-catatan"><h2 id="h-catatan">Catatan guru</h2>'
                          f'<div class="catatan">{_esc(catatan)}</div></section>')
    oleh = f" oleh {_esc(guru)}" if str(guru).strip() else ""
    return _dokumen(
        f'<p class="merek">{_esc(T.NAMA_PRODUK)}</p>'
        f"<header><h1>{_esc(JUDUL)}</h1><p class=\"anak\">{_esc(nama)}</p>"
        f'<p class="periode"><time datetime="{_esc(periode[0])}">{_esc(_rentang(*periode))}</time></p></header>'
        f'<section aria-labelledby="h-topik"><h2 id="h-topik">Yang dilatih</h2>{_bagian_topik(topik)}</section>'
        f'<section aria-labelledby="h-tahap"><h2 id="h-tahap">Tahap belajar sekarang</h2>'
        f"{_bagian_tahap(isi.get('tahap'))}</section>"
        f'<section aria-labelledby="h-langkah"><h2 id="h-langkah">Langkah berikutnya</h2>'
        f"<p>{_esc(isi.get('langkah', ''))}</p></section>"
        f"{bagian_catatan}"
        f'<footer><p class="kecil">Diterbitkan {_esc(_tanggal_panjang(diterbitkan))}{oleh}.</p>'
        '<p class="kecil">Latihan bukan penilaian akhir. Halaman ini bukan rapor dan tidak memuat skor.</p>'
        f'<p class="kecil">Tautan ini hanya untuk dibaca. Simpan atau cetak bila perlu. '
        f"Berlaku sampai {_esc(_batas(kedaluarsa))}.</p></footer>"
    )


def render_tidak_dapat_dibuka() -> bytes:
    """Satu badan untuk semua keadaan tidak sah: tidak ada oracle 'pernah ada'."""
    return _dokumen(
        f'<p class="merek">{_esc(T.NAMA_PRODUK)}</p>'
        "<h1>Laporan tidak dapat dibuka</h1>"
        "<p>Tautan ini sudah tidak berlaku. Minta tautan baru kepada guru anak Anda.</p>"
    )
