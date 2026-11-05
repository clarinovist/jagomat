"""Lembar persiapan sesi tatap muka satu anak — halaman cetak untuk guru.

Isinya tidak menyusun rencana baru: seluruh judul, instruksi, contoh
terbimbing, dan playbook diambil dari ``learning_cycle_ui.kartu_rencana``,
sumber yang sama dengan kartu Beranda profil. Modul ini hanya menambah
kepala cetak, catatan tangan, dan aturan tampilan kertas.

Tanpa JavaScript: halaman ini dokumen cetak biasa. Elemen interaktif kartu
(form, tombol, tautan aksi) dibuang dari HTML, bukan hanya disembunyikan,
supaya yang tercetak tidak pernah terlihat seperti tombol yang bisa ditekan.
"""
from __future__ import annotations

import html
import logging
import sqlite3

import brand
import design_tokens as T
import domain_clock
import learning_cycle_ui
import learning_profile
from format_tanggal import tanggal_pendek
from print_style import GAYA_CETAK

_log = logging.getLogger(__name__)

PESAN_TIDAK_TERBACA = (
    "Rencana belum bisa dibaca. Buka profil anak untuk memeriksa."
)
LABEL_GURU = "Untuk guru — jangan diberikan ke anak."
PETUNJUK_CETAK = "Gunakan Cetak di browser (Ctrl/⌘+P)."
JUDUL_CATATAN = "Catatan sesi (tulis tangan)"
SAAT_SESI = (
    "Saat sesi: anak mengerjakan di HP-nya sendiri. Buka sesi, tekan Mulai di HP anak, "
    "lalu anak memindai kode QR. Kertas sebagai cadangan: tombol Cetak di halaman sesi."
)
SETELAH_SESI = (
    "Setelah sesi: buka Tinjau hasil untuk latihan anak, lalu Konfirmasi hasil sesi. "
    "Tautan laporan untuk orang tua muncul sesudah konfirmasi."
)
JUMLAH_GARIS_CATATAN = 6

GAYA_PERSIAPAN = f"""
@page {{ size: A4; margin: 13mm 12mm 11mm 12mm; }}
body.persiapan-cetak-st {{ margin: 0; color: {T.CETAK_TINTA}; }}
.persiapan-st {{ max-width: 186mm; margin: 0 auto; padding: 6mm 4mm 8mm; }}
.persiapan-kepala-st {{
  border-bottom: 1.2pt solid {T.CETAK_TINTA}; padding-bottom: 2.5mm; margin-bottom: 4mm;
}}
.persiapan-alis-st {{
  margin: 0 0 1mm; font-size: 9pt; letter-spacing: .4pt;
  color: {T.CETAK_TEKS_SEKUNDER}; text-transform: uppercase;
}}
.persiapan-kepala-st h1 {{ margin: 0 0 1mm; font-size: 15pt; }}
.persiapan-meta-st {{ margin: 0; font-size: 9.5pt; color: {T.CETAK_TEKS_SEKUNDER}; }}
.persiapan-label-st {{
  margin: 2.5mm 0 0; padding: 1.6mm 2.5mm; border: 1pt solid {T.CETAK_TINTA};
  font-size: 9.5pt; font-weight: bold;
}}
.persiapan-rencana-st {{ margin: 0 0 4mm; }}
.persiapan-rencana-st :is(h2, h3) {{ margin: 0 0 1.5mm; font-size: 12pt; }}
.persiapan-rencana-st p {{ margin: 0 0 1.6mm; }}
.persiapan-rencana-st .beranda-caranya-st,
.persiapan-rencana-st .contoh-rencana-st,
.persiapan-rencana-st .playbook-guru {{
  border: .8pt solid {T.CETAK_GARIS_HALUS}; padding: 2.5mm 3mm; margin: 3mm 0;
  break-inside: avoid; page-break-inside: avoid;
}}
.persiapan-rencana-st .playbook-guru {{ background: transparent; }}
.persiapan-rencana-st .playbook-guru > summary {{ font-weight: bold; cursor: auto; }}
.persiapan-rencana-st .playbook-peringatan {{ font-weight: bold; }}
.persiapan-rencana-st .strip-rencana-st {{
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 2mm; margin: 2mm 0 0; padding: 0; list-style: none;
}}
.persiapan-rencana-st .tahap-rencana-st {{
  margin: 0; padding: 0; font-size: 8.5pt; line-height: 1.35; overflow-wrap: anywhere;
}}
.persiapan-rencana-st .tahap-rencana-st.aktif {{ font-weight: bold; }}
.persiapan-catatan-st {{
  margin-top: 5mm; break-inside: avoid; page-break-inside: avoid;
}}
.persiapan-catatan-st h2 {{ margin: 0 0 1mm; font-size: 11pt; }}
.persiapan-catatan-st p {{ margin: 0 0 2.5mm; font-size: 9pt; color: {T.CETAK_TEKS_SEKUNDER}; }}
.persiapan-garis-tulis-st {{ height: 9mm; border-bottom: .6pt solid {T.CETAK_GARIS_HALUS}; }}
.persiapan-petunjuk-cetak-st {{
  margin: 4mm 0 0; font-size: 9pt; color: {T.CETAK_TEKS_SEKUNDER};
}}
/* Interaksi tidak pernah ikut tercetak; form malah sudah dibuang dari HTML. */
.persiapan-st form,
.persiapan-st button,
.persiapan-st .beranda-aksi-st,
.persiapan-st .ubah-fokus-st,
.persiapan-st .tautan-persiapan-st {{
  display: none !important;
}}
@media print {{
  .persiapan-st {{ max-width: none; padding: 0; }}
  .persiapan-petunjuk-cetak-st {{ display: none; }}
}}
"""


def _tanpa_form(fragmen: str) -> str:
    """Buang blok form utuh; fragmen kartu tidak pernah memuat form bersarang."""
    bagian = fragmen.split("<form")
    hasil = [bagian[0]]
    for sisa in bagian[1:]:
        akhir = sisa.find("</form>")
        if akhir < 0:
            continue
        hasil.append(sisa[akhir + len("</form>"):])
    return "".join(hasil)


def _siapkan_untuk_cetak(fragmen: str) -> str:
    """Buka playbook tanpa JS dan buang interaksi yang tidak berguna di kertas."""
    return _tanpa_form(fragmen).replace(
        '<details class="playbook-guru"', '<details open class="playbook-guru"'
    )


def _kelas_sekolah(kon, siswa) -> str:
    """Label kelas sekolah bila sudah diisi; selain itu kosong."""
    try:
        profil = learning_profile.baca(
            kon, int(siswa["id"]), pemilik=str(siswa["pemilik"] or "")
        )
    except (ValueError, sqlite3.Error):
        return ""
    if profil.kelas_sekolah is None:
        return ""
    return learning_profile.label_kelas_sekolah(profil.kelas_sekolah)


def _meta_kepala(kon, siswa, hari_ini) -> str:
    bagian = [b for b in (_kelas_sekolah(kon, siswa), tanggal_pendek(hari_ini)) if b]
    return " · ".join(html.escape(b, quote=True) for b in bagian)


def halaman_persiapan(kon, siswa, *, peran, hari_ini=None) -> bytes:
    """HTML cetak persiapan satu sesi; isi rencana milik kartu Beranda."""
    siswa_id = int(siswa["id"])
    nama = str(siswa["nama"])
    try:
        kartu = learning_cycle_ui.kartu_rencana(
            kon, siswa_id, siswa=siswa, peran=peran, tautan_persiapan=False,
        )
    except (ValueError, sqlite3.Error) as galat:
        _log.warning(
            "persiapan: rencana siswa %s tidak terbaca (%s)",
            siswa_id, type(galat).__name__,
        )
        kartu = f'<p class="persiapan-kosong-st">{html.escape(PESAN_TIDAK_TERBACA)}</p>'
    else:
        kartu = _siapkan_untuk_cetak(kartu)

    hari_ini = hari_ini or domain_clock.hari_wib()
    garis = "".join(
        '<div class="persiapan-garis-tulis-st"></div>'
        for _ in range(JUMLAH_GARIS_CATATAN)
    )
    judul = f"Persiapan sesi — {nama}"
    return (
        '<!DOCTYPE html>\n'
        '<html lang="id"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(brand.judul(judul))}</title>\n"
        f"{brand.tag_kepala(cetak=True)}<style>{GAYA_CETAK}{GAYA_PERSIAPAN}</style></head>\n"
        '<body class="lembar-editorial persiapan-cetak-st"><main class="persiapan-st">'
        '<header class="persiapan-kepala-st">'
        f'<p class="persiapan-alis-st">{html.escape(T.NAMA_PRODUK)} · Lembar persiapan</p>'
        f"<h1>{html.escape(judul)}</h1>"
        f'<p class="persiapan-meta-st">{_meta_kepala(kon, siswa, hari_ini)}</p>'
        f'<p class="persiapan-label-st">{html.escape(LABEL_GURU)}</p>'
        "</header>"
        f'<section class="persiapan-rencana-st" aria-label="Rencana sesi">{kartu}</section>'
        '<section class="persiapan-catatan-st">'
        f"<h2>{html.escape(JUDUL_CATATAN)}</h2>"
        "<p>Tulis hal yang perlu diingat sebelum dan sesudah sesi.</p>"
        f"{garis}"
        f"<p class=\"persiapan-setelah-st\">{html.escape(SAAT_SESI)}</p>"
        f"<p class=\"persiapan-setelah-st\">{html.escape(SETELAH_SESI)}</p></section>"
        f'<p class="persiapan-petunjuk-cetak-st">{html.escape(PETUNJUK_CETAK)}</p>'
        "</main></body></html>"
    ).encode()
