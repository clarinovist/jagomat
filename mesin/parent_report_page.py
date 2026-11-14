"""Halaman baca-saja laporan untuk orang tua (tanpa login, lewat tautan bearer).

Modul ini sengaja terpisah dari semua renderer laporan guru: hanya mengimpor stdlib
dan token desain. Masukannya dipilih dengan ALLOWLIST (nama, topik, tahap, uraian,
langkah, peta_topik, alur_berpikir, kuat, fokus, langkah_rumah, cakupan,
ringkasan_teruskan, catatan, guru, periode, tanggal) sehingga kunci tak dikenal
pada payload tidak pernah tampil. Tidak ada skrip, formulir, tautan, gambar,
atau alamat luar; visualisasi memakai SVG sebaris sisi server (Zero-JS).
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import design_tokens as T

_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")
_WIB = timezone(timedelta(hours=7))
JUDUL = "Laporan belajar"

_PETA_STATUS_VISUAL = {
    "kuat": (T.LATAR_TERSIMPAN, T.BORDER_TERSIMPAN, T.TEKS_TERSIMPAN, T.AKSEN_MURID_UTAMA, 170, "Sudah Kuat"),
    "pelan": (T.LATAR_REVIEW, T.BORDER_CATATAN, T.AKSEN_AMBER_TUA, T.AKSEN_MURID_AMBER, 112, "Perlu Pelan"),
    "fokus": (T.LATAR_GALAT, T.BORDER_GALAT, T.TEKS_GALAT, T.AKSEN_MURID_KORAL, 62, "Fokus Konsep"),
    "belum": (T.LATAR_NONAKTIF, T.BORDER_HALUS, T.TEKS_SUBTLE, T.BORDER_HALUS, 26, "Belum Diuji"),
}

_ALUR_STATUS_VISUAL = {
    "aman": (T.LATAR_TERSIMPAN, T.BORDER_TERSIMPAN, T.TEKS_TERSIMPAN, T.AKSEN_MURID_UTAMA, "Sudah lancar"),
    "perlu": (T.LATAR_REVIEW, T.BORDER_CATATAN, T.AKSEN_AMBER_TUA, T.AKSEN_MURID_AMBER, "Perlu pelan"),
    "macet": (T.LATAR_GALAT, T.BORDER_GALAT, T.TEKS_GALAT, T.AKSEN_MURID_KORAL, "Perlu ditemani"),
    "belum": (T.LATAR_NONAKTIF, T.BORDER_HALUS, T.TEKS_SUBTLE, T.BORDER_HALUS, "Belum diamati"),
}

_URUT_ALUR_SAH = ("baca", "konsep", "hitung", "cek")
_JUDUL_ALUR = {
    "baca": "Baca Soal",
    "konsep": "Pilih Konsep",
    "hitung": "Hitung Angka",
    "cek": "Cek Satuan",
}


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


GAYA_LO = f"""
.lo{{font-family:{T.FONT_CETAK};font-size:{T.UKURAN_BAGIAN_DEWASA};line-height:1.65;color:{T.TEKS_UTAMA}}}
.lo *{{box-sizing:border-box}}
.lo .merek{{font-weight:700;color:{T.TEKS_JUDUL};margin:0 0 {T.SP_4}}}
.lo .judul{{font-size:{T.UKURAN_ANGKA_DEWASA};line-height:1.3;margin:0;color:{T.TEKS_JUDUL};font-weight:700}}
.lo .anak{{font-size:{T.UKURAN_JUDUL_STITCH};line-height:1.25;font-weight:800;color:{T.TEKS_JUDUL};margin:{T.SP_1} 0 0}}
.lo .periode{{color:{T.TEKS_SUBTLE};margin:0 0 {T.SP_5}}}
.lo section{{margin:0 0 {T.SP_5}}}
.lo .sub{{font-size:{T.UKURAN_BAGIAN_DEWASA};margin:0 0 {T.SP_2};color:{T.TEKS_JUDUL};font-weight:700}}
.lo ul{{margin:0;padding-left:1.25rem}}
.lo p{{margin:0 0 {T.SP_2}}}
.lo .tahap{{font-weight:700}}
.lo .catatan{{white-space:pre-line;background:{T.LATAR_CATATAN};border:1px solid {T.BORDER_CATATAN};
border-radius:{T.RADIUS_KARTU};padding:{T.SP_4} {T.SP_4}}}
.lo .ttd{{color:{T.TEKS_VARIAN};font-size:{T.UKURAN_TEKS_LABEL};margin:{T.SP_2} 0 0}}
.lo .langkah{{background:{T.ANAK_AKSEN_LATAR};border:1px solid {T.AKSEN_MURID_UTAMA};
border-radius:{T.RADIUS_KARTU};padding:{T.SP_3} {T.SP_4} {T.SP_2}}}
.lo .rumah{{margin-top:{T.SP_2};padding-top:{T.SP_2};border-top:1px dashed {T.BORDER_VARIAN};color:{T.TEKS_JUDUL}}}
.lo ul.chip{{display:flex;flex-wrap:wrap;gap:{T.SP_2};list-style:none;padding:0}}
.lo ul.chip li{{background:{T.ANAK_AKSEN_LATAR};color:{T.AKSEN_TEAL_TUA};font-weight:700;
border-radius:{T.RADIUS_PIL};padding:{T.SP_1} {T.SP_3}}}
.lo .titik{{display:flex;gap:6px;margin:0 0 {T.SP_2}}}
.lo .titik span{{width:14px;height:14px;border-radius:50%;border:2px solid {T.AKSEN_TEAL_TUA};background:{T.LATAR_KARTU}}}
.lo .titik span.isi{{background:{T.AKSEN_TEAL_TUA}}}
.lo .viz-kotak{{margin:{T.SP_3} 0 0;padding:{T.SP_2};border:1px solid {T.BORDER_HALUS};border-radius:{T.RADIUS_KARTU};background:{T.LATAR_KARTU}}}
.lo .viz-kotak svg{{display:block;width:100%;height:auto}}
.lo .grid-dukungan{{display:grid;gap:{T.SP_3}}}
@media (min-width:34rem){{.lo .grid-dukungan{{grid-template-columns:1fr 1fr}}}}
.lo .kartu-kuat{{background:{T.LATAR_TERSIMPAN};border:1px solid {T.BORDER_TERSIMPAN};border-radius:{T.RADIUS_KARTU};padding:{T.SP_3}}}
.lo .kartu-fokus{{background:{T.LATAR_REVIEW};border:1px solid {T.BORDER_CATATAN};border-radius:{T.RADIUS_KARTU};padding:{T.SP_3}}}
.lo .kartu-judul{{font-weight:700;color:{T.TEKS_JUDUL};margin:0 0 {T.SP_1}}}
.lo .ringkas{{white-space:pre-line;background:{T.LATAR_SEKUNDER_LEMBUT};border:1px solid {T.BORDER_HALUS};
border-radius:{T.RADIUS_KARTU};padding:{T.SP_3};font-size:{T.UKURAN_TEKS_LABEL};color:{T.TEKS_UTAMA}}}
.lo .kecil{{color:{T.TEKS_SUBTLE};font-size:{T.UKURAN_TEKS_LABEL}}}
.lo footer{{border-top:1px solid {T.BORDER_HALUS};padding-top:{T.SP_4}}}
@media print{{.lo{{color:{T.CETAK_TINTA}}}.lo section,.lo footer,.lo .viz-kotak{{break-inside:avoid;page-break-inside:avoid}}}}
"""

_GAYA_HALAMAN = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{T.LATAR_INTI}}}
main{{max-width:40rem;margin:0 auto;padding:{T.SP_5} {T.SP_4} {T.SP_6};background:{T.LATAR_KARTU}}}
@media (min-width:42rem){{main{{margin-top:{T.SP_5};border-radius:{T.RADIUS_KARTU};border:1px solid {T.BORDER_HALUS}}}}}
@media print{{body{{background:#fff}}main{{max-width:none;margin:0;padding:0;border:0}}@page{{margin:16mm}}}}
"""


def _dokumen(isi: str) -> bytes:
    return (
        '<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{_esc(JUDUL)} — {_esc(T.NAMA_PRODUK)}</title>"
        f"<style>{_GAYA_HALAMAN}{GAYA_LO}</style></head><body><main>{isi}</main></body></html>"
    ).encode("utf-8")


def _bagian_topik(topik) -> str:
    if not topik:
        return "<p>Belum ada latihan yang sudah diperiksa guru pada periode ini.</p>"
    return '<ul class="chip">' + "".join(f"<li>{_esc(t)}</li>" for t in topik) + "</ul>"


def _titik_tahap(nomor) -> str:
    """Enam titik dekoratif; maknanya tetap ada di teks 'n dari 6'. Nomor tak sah: tanpa titik."""
    if isinstance(nomor, bool) or not isinstance(nomor, int) or not 1 <= nomor <= 6:
        return ""
    titik = "".join('<span class="isi"></span>' if i < nomor else "<span></span>" for i in range(6))
    return f'<p class="titik" aria-hidden="true">{titik}</p>'


def _bagian_tahap(tahap) -> str:
    if not isinstance(tahap, dict):
        return "<p>Tahap belum bisa ditunjukkan saat ini.</p>"
    return (_titik_tahap(tahap.get("nomor"))
            + f'<p class="tahap">{_esc(tahap.get("label", ""))} ({_esc(tahap.get("nomor", ""))} dari 6)</p>'
            f"<p>{_esc(tahap.get('uraian', ''))}</p>")


def _svg_peta_topik(peta_topik) -> str:
    """Bangun SVG sebaris Zero-JS untuk peta kemampuan per topik."""
    if not isinstance(peta_topik, list) or not peta_topik:
        return ""
    item_sah = []
    for entri in peta_topik[:6]:
        if not isinstance(entri, dict):
            continue
        nama = str(entri.get("nama", "")).strip()
        status = str(entri.get("status", "belum"))
        if not nama or status not in _PETA_STATUS_VISUAL:
            continue
        item_sah.append((nama[:26], status))
    if not item_sah:
        return ""

    tinggi = 16 + len(item_sah) * 44
    baris_svg = []
    for idx, (nama, status) in enumerate(item_sah):
        bg, border, teks_c, bar_c, panjang, label_baku = _PETA_STATUS_VISUAL[status]
        y = 10 + idx * 44
        baris_svg.append(
            f'<rect x="6" y="{y}" width="508" height="36" rx="8" fill="{bg}" stroke="{border}" stroke-width="1"/>'
            f'<text x="20" y="{y + 23}" fill="{T.TEKS_JUDUL}" font-size="13" font-weight="700">{_esc(nama)}</text>'
            f'<rect x="210" y="{y + 13}" width="176" height="10" rx="5" fill="{T.LATAR_KARTU}" stroke="{border}" stroke-width="1"/>'
            f'<rect x="210" y="{y + 13}" width="{panjang}" height="10" rx="5" fill="{bar_c}"/>'
            f'<text x="500" y="{y + 22}" text-anchor="end" fill="{teks_c}" font-size="12" font-weight="700">{_esc(label_baku)}</text>'
        )
    return (
        '<div class="viz-kotak">'
        f'<svg viewBox="0 0 520 {tinggi}" role="img" aria-label="Peta kemampuan anak per materi">'
        + "".join(baris_svg)
        + "</svg></div>"
    )


def _svg_alur_berpikir(alur_berpikir) -> str:
    """Bangun diagram SVG 4 tahap alur berpikir anak (Zero-JS)."""
    if not isinstance(alur_berpikir, list) or not alur_berpikir:
        return ""
    peta_entri = {}
    for entri in alur_berpikir:
        if not isinstance(entri, dict):
            continue
        kode = str(entri.get("kode", ""))
        status = str(entri.get("status", "belum"))
        if kode in _JUDUL_ALUR and status in _ALUR_STATUS_VISUAL:
            peta_entri[kode] = status
    if not peta_entri:
        return ""

    nodes = []
    konektor = []
    x_awal = (8, 138, 268, 398)
    for idx, kode in enumerate(_URUT_ALUR_SAH):
        status = peta_entri.get(kode, "belum")
        bg, border, teks_c, aksen, label_baku = _ALUR_STATUS_VISUAL[status]
        x = x_awal[idx]
        if idx < 3:
            x1 = x + 114
            x2 = x_awal[idx + 1]
            konektor.append(
                f'<line x1="{x1}" y1="50" x2="{x2}" y2="50" stroke="{T.BORDER_VARIAN}" stroke-width="2"/>'
                f'<polygon points="{x2 - 5},45 {x2},50 {x2 - 5},55" fill="{T.BORDER_VARIAN}"/>'
            )
        nodes.append(
            f'<rect x="{x}" y="12" width="114" height="76" rx="10" fill="{bg}" stroke="{border}" stroke-width="1.5"/>'
            f'<rect x="{x + 12}" y="20" width="90" height="5" rx="2.5" fill="{aksen}"/>'
            f'<text x="{x + 57}" y="46" text-anchor="middle" fill="{T.TEKS_JUDUL}" font-size="12" font-weight="700">{_esc(_JUDUL_ALUR[kode])}</text>'
            f'<text x="{x + 57}" y="68" text-anchor="middle" fill="{teks_c}" font-size="11" font-weight="600">{_esc(label_baku)}</text>'
        )
    svg = (
        '<div class="viz-kotak">'
        '<svg viewBox="0 0 520 100" role="img" aria-label="Peta alur cara berpikir anak">'
        + "".join(konektor)
        + "".join(nodes)
        + "</svg></div>"
    )
    return f'<section><p class="sub">Alur cara berpikir anak</p>{svg}</section>'


def _bagian_kuat_fokus(kuat, fokus) -> str:
    daftar_kuat = [str(x).strip() for x in (kuat or []) if str(x).strip()][:3]
    daftar_fokus = [str(x).strip() for x in (fokus or []) if str(x).strip()][:2]
    if not daftar_kuat and not daftar_fokus:
        return ""
    kolom = []
    if daftar_kuat:
        isi_k = "<ul>" + "".join(f"<li>{_esc(p)}</li>" for p in daftar_kuat) + "</ul>"
        kolom.append(f'<div class="kartu-kuat"><p class="kartu-judul">Yang sudah lancar</p>{isi_k}</div>')
    if daftar_fokus:
        isi_f = "<ul>" + "".join(f"<li>{_esc(p)}</li>" for p in daftar_fokus) + "</ul>"
        kolom.append(f'<div class="kartu-fokus"><p class="kartu-judul">Yang perlu ditemani</p>{isi_f}</div>')
    return '<section><div class="grid-dukungan">' + "".join(kolom) + "</div></section>"


def _bagian_ringkasan(ringkasan, cakupan) -> str:
    teks_r = str(ringkasan or "").strip()
    teks_c = str(cakupan or "").strip()
    bagian = ""
    if teks_r:
        bagian += (
            '<section><p class="sub">Ringkasan untuk disimpan</p>'
            f'<div class="ringkas">{_esc(teks_r)}</div></section>'
        )
    if teks_c:
        bagian += f'<p class="kecil">{_esc(teks_c)}</p>'
    return bagian


def isi_laporan(*, nama, isi, catatan, guru, periode, diterbitkan=None, kedaluarsa=None, judul_tag="h1") -> str:
    """Markup satu laporan (`<article class="lo">`); dipakai halaman orang tua dan pratinjau guru.

    Hanya field allowlist yang dibaca dari `isi`. Tanggal terbit dan batas berlaku kosong
    pada pratinjau draf. Payload v1 lama tetap dirender utuh tanpa memaksa blok baru.
    """
    topik = [str(t) for t in (isi.get("topik") or [])]
    bagian_catatan = ""
    ada_guru = bool(str(guru).strip())
    if str(catatan).strip():
        tanda = f'<p class="ttd">Ditulis oleh {_esc(guru)}</p>' if ada_guru else ""
        bagian_catatan = (f'<section><p class="sub">Catatan guru</p>'
                          f'<div class="catatan">{_esc(catatan)}</div>{tanda}</section>')
    oleh = f" oleh {_esc(guru)}" if ada_guru and not bagian_catatan else ""
    if diterbitkan is None or kedaluarsa is None:
        penutup = '<p class="kecil">Pratinjau: tanggal terbit dan batas berlaku terisi saat laporan diterbitkan.</p>'
    else:
        penutup = (f'<p class="kecil">Diterbitkan {_esc(_tanggal_panjang(diterbitkan))}{oleh}.</p>'
                   '<p class="kecil">Tautan ini hanya untuk dibaca. Simpan atau cetak bila perlu. '
                   f"Berlaku sampai {_esc(_batas(kedaluarsa))}.</p>")
    judul = judul_tag if judul_tag in ("h1", "h2", "h3") else "h1"

    langkah_rumah = str(isi.get("langkah_rumah") or "").strip()
    blok_rumah = (
        f'<p class="rumah"><strong>Pendampingan di rumah:</strong> {_esc(langkah_rumah)}</p>'
        if langkah_rumah
        else ""
    )
    svg_peta = _svg_peta_topik(isi.get("peta_topik"))
    blok_alur = _svg_alur_berpikir(isi.get("alur_berpikir"))
    blok_dukungan = _bagian_kuat_fokus(isi.get("kuat"), isi.get("fokus"))
    blok_ringkas = _bagian_ringkasan(isi.get("ringkasan_teruskan"), isi.get("cakupan"))

    return (
        '<article class="lo">'
        f'<p class="merek">{_esc(T.NAMA_PRODUK)}</p>'
        f'<header><{judul} class="judul">{_esc(JUDUL)}</{judul}><p class="anak">{_esc(nama)}</p>'
        f'<p class="periode"><time datetime="{_esc(periode[0])}">{_esc(_rentang(*periode))}</time></p></header>'
        f"{bagian_catatan}"
        f'<section class="langkah"><p class="sub">Langkah berikutnya</p><p>{_esc(isi.get("langkah", ""))}</p>{blok_rumah}</section>'
        f'<section><p class="sub">Tahap belajar sekarang</p>{_bagian_tahap(isi.get("tahap"))}</section>'
        f'<section><p class="sub">Yang dilatih</p>{_bagian_topik(topik)}{svg_peta}</section>'
        f"{blok_alur}"
        f"{blok_dukungan}"
        f"{blok_ringkas}"
        f'<footer>{penutup}'
        '<p class="kecil">Latihan bukan penilaian akhir. Halaman ini bukan rapor dan tidak memuat skor.</p></footer>'
        "</article>"
    )


def render_laporan(*, nama, isi, catatan, guru, periode, diterbitkan, kedaluarsa) -> bytes:
    """Satu laporan terbit sebagai halaman penuh."""
    return _dokumen(isi_laporan(nama=nama, isi=isi, catatan=catatan, guru=guru, periode=periode,
                                diterbitkan=diterbitkan, kedaluarsa=kedaluarsa))


def render_tidak_dapat_dibuka() -> bytes:
    """Satu badan untuk semua keadaan tidak sah: tidak ada oracle 'pernah ada'."""
    return _dokumen(
        '<article class="lo">'
        f'<p class="merek">{_esc(T.NAMA_PRODUK)}</p>'
        '<h1 class="judul">Laporan tidak dapat dibuka</h1>'
        "<p>Tautan ini sudah tidak berlaku. Minta tautan baru kepada guru anak Anda.</p></article>"
    )
