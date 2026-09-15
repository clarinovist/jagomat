"""Peta seluruh target Jagomat; angka dan grafik berasal dari reducer murni."""
from collections import Counter
from dataclasses import dataclass
from typing import Tuple
import html

import design_tokens as T
from learning_cycle import StatusTargetMateri, penguasaan_target
from mastery_catalog import TargetMateri, VERSI_KATALOG, katalog_target
from report_dashboard import persen
from template_labels import nama_tipe_soal
from templates import label_kelas

STATUS = (
    ("terbukti", "Menunjukkan pemahaman", T.AKSEN_TEAL_TUA),
    ("dipelajari", "Masih dipelajari", T.STATUS_LEMAH),
    ("perlu_cek", "Perlu cek kembali", T.STATUS_SALAH),
    ("belum_dinilai", "Belum dinilai", T.BORDER_HALUS),
)
LABEL = {kode: nama for kode, nama, _ in STATUS}

GAYA_PETA = f"""
.peta-materi-st {{margin:{T.SP_5} 0;}}
.peta-materi-st .peta-kepala {{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:{T.SP_4};align-items:center;}}
.peta-materi-st .peta-angka {{font-size:3rem;font-weight:800;line-height:1.2;color:{T.TEKS_JUDUL};}}
.peta-materi-st .peta-angka small {{display:block;font-size:.9rem;font-weight:600;line-height:1.5;}}
.peta-materi-st .peta-catatan {{color:{T.TEKS_SUBTLE};font-size:.9rem;}}
.peta-materi-st .peta-grafik {{display:block;width:100%;height:2.5rem;margin:{T.SP_4} 0;}}
.peta-materi-st .peta-legenda {{display:flex;flex-wrap:wrap;gap:{T.SP_3} {T.SP_5};list-style:none;padding:0;}}
.peta-materi-st .peta-legenda li {{display:flex;align-items:center;gap:{T.SP_2};}}
.peta-materi-st .peta-swatch {{width:1rem;height:1rem;display:inline-block;border:1px solid {T.TEKS_SUBTLE};}}
.peta-materi-st .peta-topik {{margin-top:{T.SP_4};border-top:1px solid {T.BORDER_HALUS};}}
.peta-materi-st .peta-topik > summary {{display:flex;justify-content:space-between;gap:{T.SP_4};padding:{T.SP_4} 0;min-height:{T.TARGET_SENTUH};cursor:pointer;}}
.peta-materi-st .peta-topik summary:focus-visible {{outline:2px solid {T.AKSEN_TEAL_TUA};outline-offset:2px;}}
.peta-materi-st .peta-nilai::after {{content:' ▸';display:inline-block;margin-left:{T.SP_2};}}
.peta-materi-st .peta-topik[open] > summary .peta-nilai::after {{content:' ▾';}}
.peta-materi-st .peta-topik summary small {{display:block;color:{T.TEKS_SUBTLE};font-weight:400;}}
.peta-materi-st .peta-nilai {{text-align:right;white-space:nowrap;color:{T.TEKS_JUDUL};font-weight:700;}}
.peta-materi-st .peta-target {{list-style:none;padding:0;margin:0;}}
.peta-materi-st .peta-target > li {{padding:{T.SP_3} 0;border-top:1px solid {T.BORDER_HALUS};overflow-wrap:anywhere;}}
.peta-materi-st .peta-target summary {{cursor:pointer;min-height:{T.TARGET_SENTUH};padding:{T.SP_2} 0;}}
.peta-materi-st .peta-target p {{margin:{T.SP_2} 0;}}
.peta-materi-st .peta-bukti {{padding-left:{T.SP_5};}}
.peta-materi-st .peta-aktivitas {{font-size:.95rem;}}
@media(max-width:46rem) {{
 .peta-materi-st .peta-kepala {{grid-template-columns:minmax(0,1fr);}}
 .peta-materi-st .peta-angka {{font-size:2.5rem;}}
 .peta-materi-st .peta-topik > summary {{gap:{T.SP_3};}}
 .peta-materi-st .peta-topik summary small {{font-size:.85rem;}}
}}
"""


@dataclass(frozen=True)
class PetaPenguasaan:
    level: str
    target: Tuple[TargetMateri, ...]
    status: Tuple[StatusTargetMateri, ...]

    @property
    def jumlah(self):
        return Counter(s.status for s in self.status)

    @property
    def persen(self):
        return _persentase(self.status)


def _persentase(status):
    if not status or all(s.status == "belum_dinilai" for s in status):
        return None
    return 100 * sum(s.status == "terbukti" for s in status) / len(status)


def peta_penguasaan(bukti, siswa_id, hari_ini=None):
    target = katalog_target(bukti.level_aktif)
    return PetaPenguasaan(bukti.level_aktif, target,
                         penguasaan_target(bukti, siswa_id, target, hari_ini))


def _grafik(jumlah, total):
    """Batang proporsi semua target, termasuk yang belum pernah dinilai."""
    posisi = 0.0
    bagian = []
    for kode, nama, warna in STATUS:
        lebar = 600 * jumlah[kode] / total if total else 0
        if lebar:
            bagian.append(f'<rect x="{posisi:.3f}" y="1" width="{lebar:.3f}" height="30" '
                          f'fill="{warna}" stroke="{T.TEKS_SUBTLE}" stroke-width="1">'
                          f'<title>{nama}: {jumlah[kode]} target</title></rect>')
        posisi += lebar
    label = "; ".join(f"{nama}: {jumlah[kode]} dari {total} target" for kode, nama, _ in STATUS)
    return ('<svg class="peta-grafik" viewBox="0 0 600 32" preserveAspectRatio="none" role="img" '
            f'aria-label="{html.escape(label)}">' + ''.join(bagian) + '</svg>')


def _rincian_target(target, hasil, tanggal):
    bukti = []
    for pola in hasil.pola:
        tautan = ", ".join(f'<a href="/sesi/{sid}">#{sid}</a>' for sid in pola.sesi_ids)
        kapan = f' · {tanggal(pola.terakhir.isoformat())}' if pola.terakhir else ""
        bukti.append(f'<li>{html.escape(nama_tipe_soal(pola.template_id))}: '
                     f'{LABEL[pola.status]}{kapan}' + (f' · sesi {tautan}' if tautan else '') + '</li>')
    terpenuhi = sum(p.status == "terbukti" for p in hasil.pola)
    return (
        f'<li><b>{html.escape(target.nama)}</b> — {LABEL[hasil.status]}'
        f'<details><summary>{terpenuhi}/{len(target.pola)} pola menunjukkan pemahaman</summary>'
        '<ul class="peta-bukti">' + ''.join(bukti) + '</ul></details></li>'
    )


def render_peta(peta, tanggal):
    kelas = html.escape(label_kelas(peta.level))
    if not peta.target:
        return ('<section class="kartu peta-materi-st" id="peta-penguasaan">'
                '<h2>Progres penguasaan materi Jagomat</h2>'
                '<p>Target Jagomat untuk kelas ini belum tersedia. Periksa kelas belajar anak.</p></section>')
    jumlah = peta.jumlah
    total = len(peta.target)
    sudah_dinilai = total - jumlah["belum_dinilai"]
    legenda = ''.join(
        f'<li><span class="peta-swatch" style="background:{warna}" aria-hidden="true"></span>'
        f'<span><b>{jumlah[kode]}</b> {nama.lower()}</span></li>' for kode, nama, warna in STATUS
    )
    per_topik = {}
    for t, s in zip(peta.target, peta.status):
        per_topik.setdefault((t.topik_id, t.topik), []).append((t, s))
    topik_dinilai = sum(any(s.status != "belum_dinilai" for _, s in pasangan)
                        for pasangan in per_topik.values())
    rincian = []
    for (_, nama), pasangan in per_topik.items():
        hasil = tuple(s for _, s in pasangan)
        terbukti = sum(s.status == "terbukti" for s in hasil)
        belum = sum(s.status == "belum_dinilai" for s in hasil)
        angka = _persentase(hasil)
        label = "Belum dinilai" if angka is None else persen(angka)
        rincian.append(
            '<details class="peta-topik"><summary>'
            f'<span><b>{html.escape(nama)}</b><small>{terbukti}/{len(hasil)} target menunjukkan pemahaman '
            f'· {belum} belum dinilai</small></span><span class="peta-nilai">{html.escape(label)}</span>'
            '</summary><ul class="peta-target">'
            + ''.join(_rincian_target(t, s, tanggal) for t, s in pasangan) + '</ul></details>'
        )
    label_angka = "Belum dinilai" if peta.persen is None else "target menunjukkan pemahaman"
    return (
        '<section class="kartu peta-materi-st" id="peta-penguasaan" aria-labelledby="judul-peta">'
        '<div class="peta-kepala"><div><h2 id="judul-peta">Progres penguasaan materi Jagomat</h2>'
        f'<p>{kelas} · {total} target keterampilan dalam {len(per_topik)} materi</p></div>'
        f'<div class="peta-angka">{html.escape(persen(peta.persen))}<small>{label_angka}</small></div></div>'
        f'<p><b>{jumlah["terbukti"]} dari {total} target</b> sudah menunjukkan pemahaman.</p>'
        + _grafik(jumlah, total) + f'<ul class="peta-legenda">{legenda}</ul>'
        f'<p class="peta-aktivitas">Cakupan penilaian: {topik_dinilai}/{len(per_topik)} materi '
        f'· {sudah_dinilai}/{total} target memiliki catatan penilaian atau pemeriksaan.</p>'
        '<p class="peta-catatan">Belum dinilai bukan berarti tidak mampu. Angka ini menunjukkan '
        'kemajuan target Jagomat, bukan nilai seluruh kurikulum sekolah.</p>'
        '<h3>Penguasaan per materi</h3>' + ''.join(rincian) +
        '<details class="laporan-dasar"><summary>Kriteria target menunjukkan pemahaman</summary>'
        '<ul><li>Semua pola dalam target telah diperiksa dengan soal bervariasi.</li>'
        '<li>Bukti terkonfirmasi, hasil cukup baik, dan anak bisa menjelaskan; '
        'bukan sekadar banyak latihan atau jawaban benar sekali.</li>'
        '<li>Pemetaan diperiksa pada tanggal berbeda atau melalui evaluasi terpandu. '
        'Bukti yang perlu diperbarui ditandai cek kembali.</li>'
        '<li>Mulai dari pemetaan pada rencana belajar. Latihan biasa hanya menjadi '
        'bukti bila hasil dikonfirmasi dan disertakan dalam pemetaan.</li></ul>'
        f'<p class="peta-catatan">Katalog {VERSI_KATALOG}; tiap target berbobot sama. '
        'Status tidak berarti penguasaan permanen.</p></details></section>'
    )
