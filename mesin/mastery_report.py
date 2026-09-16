"""Peta seluruh target Jagomat; angka dan grafik berasal dari reducer murni."""
from collections import Counter
from dataclasses import dataclass
from typing import Tuple
import html

import design_tokens as T
from learning_cycle import StatusTargetMateri, penguasaan_target
from mastery_catalog import TargetMateri, VERSI_KATALOG, katalog_target
from report_dashboard import persen
from report_navigation import halaman_daftar, navigasi_halaman, pilihan, url_laporan
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
.peta-materi-st .peta-angka small {{display:inline;font-size:1.1rem;font-weight:600;line-height:1.5;}}
.peta-materi-st .peta-catatan {{color:{T.TEKS_SUBTLE};font-size:.9rem;}}
.peta-materi-st .peta-grafik {{display:block;width:100%;height:2.5rem;margin:{T.SP_4} 0;}}
.peta-materi-st .peta-legenda {{display:flex;flex-wrap:wrap;gap:{T.SP_3} {T.SP_5};list-style:none;padding:0;}}
.peta-materi-st .peta-legenda li {{display:flex;align-items:center;gap:{T.SP_2};}}
.peta-materi-st .peta-swatch {{width:1rem;height:1rem;display:inline-block;border:1px solid {T.TEKS_SUBTLE};}}
.peta-materi-st .peta-panel {{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:{T.SP_5};align-items:start;}}
.peta-materi-st .peta-daftar {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:{T.SP_3};}}
.peta-materi-st .peta-pilihan {{display:block;min-width:0;padding:{T.SP_4};border:1px solid {T.BORDER_CATATAN};border-radius:{T.RADIUS_KARTU};background:{T.LATAR_KARTU};text-decoration:none;}}
.peta-materi-st .peta-pilihan[aria-current="true"],.peta-materi-st .peta-pilihan[data-preview="true"] {{border:2px solid {T.AKSEN_TEAL_TUA};padding:calc({T.SP_4} - 1px);background:{T.LATAR_TERSIMPAN};}}
.peta-materi-st .peta-pilihan small {{display:block;margin-top:{T.SP_2};color:{T.TEKS_SUBTLE};}}
.peta-materi-st .peta-pilihan .peta-nilai {{display:block;margin-top:{T.SP_3};font-weight:700;}}
.peta-materi-st .peta-detail {{min-width:0;margin:0;}}
.peta-materi-st .peta-auto-lihat {{display:none;}}
.peta-materi-st .peta-kembali {{display:none;}}
.peta-materi-st .peta-status {{display:block;font-size:.85rem;font-weight:600;color:{T.TEKS_SUBTLE};margin:{T.SP_2} 0;}}
.peta-materi-st .peta-status-terbukti {{color:{T.TEKS_TERSIMPAN};}}
@media(min-width:46.01rem) and (max-width:63.99rem) {{
 .peta-materi-st .peta-daftar {{grid-template-columns:minmax(0,1fr);}}
}}
.peta-materi-st .peta-ringkas {{margin-bottom:{T.SP_5};}}
.peta-materi-st .peta-ringkas p {{margin:{T.SP_2} 0;}}
.peta-materi-st .peta-target {{list-style:none;padding:0;margin:0;}}
.peta-materi-st .peta-target > li {{padding:{T.SP_3} 0;border-top:1px solid {T.BORDER_HALUS};overflow-wrap:anywhere;}}
.peta-materi-st .peta-target p {{margin:{T.SP_2} 0;}}
.peta-materi-st .peta-bukti {{padding-left:{T.SP_5};}}
.peta-materi-st .peta-aktivitas {{font-size:.95rem;}}
@media(max-width:46rem) {{
 .peta-materi-st .peta-kepala {{grid-template-columns:minmax(0,1fr);}}
 .peta-materi-st .peta-angka {{font-size:2.5rem;}}
 .peta-materi-st .peta-panel {{grid-template-columns:minmax(0,1fr);}}
 .peta-materi-st .peta-detail {{display:none;}}
 .peta-materi-st .peta-pilihan[data-preview="true"] {{border:1px solid {T.BORDER_CATATAN};padding:{T.SP_4};background:{T.LATAR_KARTU};}}
 .peta-materi-st .peta-auto-pilih {{display:none;}}
 .peta-materi-st .peta-auto-lihat {{display:inline;}}
 .peta-materi-st.peta-detail-aktif .peta-detail {{display:block;}}
 .peta-materi-st.peta-detail-aktif .peta-pemilih,.peta-materi-st.peta-detail-aktif .peta-ringkas {{display:none;}}
 .peta-materi-st .peta-kembali {{display:inline-flex;align-items:center;min-height:{T.TARGET_SENTUH};margin-bottom:{T.SP_3};}}
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
        f'<li><b>{html.escape(target.nama)}</b>'
        f'<span class="peta-status peta-status-{hasil.status}">{LABEL[hasil.status]}</span>'
        f'<p class="peta-catatan"><span class="rasio-laporan">{terpenuhi}/{len(target.pola)}</span> pola menunjukkan pemahaman</p>'
        '<ul class="peta-bukti">' + ''.join(bukti) + '</ul></li>'
    )


def render_peta(peta, tanggal, ringkas=False, *, siswa_id=0, materi='', status='semua', halaman='1'):
    kelas = html.escape(label_kelas(peta.level))
    if not peta.target:
        return ('<section class="kartu peta-materi-st" id="peta-penguasaan">'
                '<h2>Progres penguasaan materi Jagomat</h2>'
                '<p>Target Jagomat untuk kelas ini belum tersedia. Periksa kelas belajar anak.</p></section>')
    per_topik = {}
    for t, s in zip(peta.target, peta.status):
        per_topik.setdefault((t.topik_id, t.topik), []).append((t, s))
    if not ringkas:
        return _pilih_materi(peta, per_topik, tanggal, siswa_id, materi, status, halaman)
    jumlah = peta.jumlah
    total = len(peta.target)
    sudah_dinilai = total - jumlah["belum_dinilai"]
    legenda = ''.join(
        f'<li><span class="peta-swatch" style="background:{warna}" aria-hidden="true"></span>'
        f'<span><b>{jumlah[kode]}</b> {nama.lower()}</span></li>' for kode, nama, warna in STATUS
    )
    topik_dinilai = sum(any(s.status != "belum_dinilai" for _, s in pasangan)
                        for pasangan in per_topik.values())
    label_angka = "Belum dinilai" if peta.persen is None else "dari seluruh target Jagomat"
    return (
        '<section class="kartu peta-materi-st" id="peta-penguasaan" aria-labelledby="judul-peta">'
        '<div class="peta-kepala"><div><h2 id="judul-peta">Progres penguasaan materi Jagomat</h2>'
        f'<p>{kelas} · {total} target keterampilan dalam {len(per_topik)} materi</p></div>'
        f'<div class="peta-angka">{jumlah["terbukti"]} <small>dari {total} target</small></div></div>'
        '<p><b>menunjukkan pemahaman</b></p>'
        f'<p class="peta-catatan peta-persentase">{html.escape(persen(peta.persen))} · {label_angka}</p>'
        + _grafik(jumlah, total) + f'<ul class="peta-legenda">{legenda}</ul>'
        f'<p class="peta-aktivitas">Cakupan penilaian: {topik_dinilai}/{len(per_topik)} materi '
        f'· {sudah_dinilai}/{total} target dinilai atau diperiksa.</p>'
        '<p class="peta-catatan">Belum dinilai bukan berarti tidak mampu. Angka ini menunjukkan '
        'kemajuan target Jagomat, bukan nilai seluruh kurikulum sekolah.</p>'
        '<p class="peta-catatan">Semua pola perlu bukti terkonfirmasi dan anak bisa menjelaskan; '
        'bukan hanya jawaban benar sekali.</p></section>'
    )


def render_kriteria():
    """Kriteria existing tetap terbaca, terpisah dari daftar materi."""
    return (
        '<section class="kartu laporan-dasar" id="kriteria-penguasaan">'
        '<h2>Kriteria target menunjukkan pemahaman</h2>'
        '<ul><li>Semua pola dalam target telah diperiksa dengan soal bervariasi.</li>'
        '<li>Bukti terkonfirmasi, hasil cukup baik, dan anak bisa menjelaskan; '
        'bukan sekadar banyak latihan atau jawaban benar sekali.</li>'
        '<li>Pemetaan diperiksa pada tanggal berbeda atau melalui evaluasi terpandu. '
        'Bukti yang perlu diperbarui ditandai cek kembali.</li>'
        '<li>Mulai dari pemetaan pada rencana belajar. Latihan biasa hanya menjadi '
        'bukti bila hasil dikonfirmasi dan disertakan dalam pemetaan.</li></ul>'
        f'<p class="peta-catatan">Katalog {VERSI_KATALOG}; tiap target berbobot sama. '
        'Status tidak berarti penguasaan permanen.</p></section>'
    )


def _pilih_materi(peta, per_topik, tanggal, siswa_id, materi, status, halaman):
    """Filter kartu saja; panel selalu memuat semua target materi terpilih."""
    def cocok(pasangan, kode):
        if kode == 'semua':
            return True
        if kode == 'dinilai':
            return any(s.status != 'belum_dinilai' for _, s in pasangan)
        if kode == 'belum_dinilai':
            return all(s.status == kode for _, s in pasangan)
        return any(s.status == kode for _, s in pasangan)

    opsi = [('semua', 'Semua'), ('dinilai', 'Ada penilaian')] + [(k, n) for k, n, _ in STATUS]
    if status not in dict(opsi):
        status = 'semua'
    hitungan = {k: sum(cocok(p, k) for p in per_topik.values()) for k, _ in opsi}
    tombol = [(k, f'{n} ({hitungan[k]})') for k, n in opsi if k == 'semua' or hitungan[k]]
    daftar = [(k, p) for k, p in per_topik.items() if cocok(p, status)]
    indeks = next((i for i, (k, _) in enumerate(daftar) if k[0] == materi), None)
    eksplisit = indeks is not None
    if eksplisit:
        halaman = indeks // 6 + 1
    bagian, nomor, jumlah = halaman_daftar(daftar, halaman, 6)
    aktif = materi if eksplisit else bagian[0][0][0] if bagian else ''

    def url(**opsi_url):
        return url_laporan(siswa_id, 'penguasaan', **opsi_url)

    kartu = []
    detail = ''
    for (kode, nama), pasangan in bagian:
        hasil = tuple(s for _, s in pasangan)
        terbukti = sum(s.status == 'terbukti' for s in hasil)
        belum = sum(s.status == 'belum_dinilai' for s in hasil)
        label = 'Belum dinilai' if _persentase(hasil) is None else persen(_persentase(hasil))
        kartu.append(
            f'<a class="peta-pilihan" data-materi="{html.escape(kode)}" '
            f'href="{url(materi=kode, status=status, halaman=nomor)}"'
            + ((' aria-current="true"' if eksplisit else ' data-preview="true"') if kode == aktif else '') + '>'
            f'<b>{html.escape(nama)}</b><small><span class="rasio-laporan">{terbukti}/{len(hasil)} target</span> '
            'menunjukkan pemahaman</small>'
            + (f'<small>{belum} belum dinilai · {html.escape(label)}</small>' if belum != len(hasil)
               else '<small>Belum dinilai</small>')
            + '<span class="peta-nilai">'
            + (('✓ Dipilih' if eksplisit else '<span class="peta-auto-pilih">✓ Dipilih</span>'
                '<span class="peta-auto-lihat">Lihat target →</span>') if kode == aktif else 'Lihat target →')
            + '</span></a>'
        )
        if kode == aktif:
            detail = (
                '<section class="kartu peta-detail" id="detail-materi" aria-labelledby="judul-materi">'
                f'<a class="peta-kembali" href="{url(status=status, halaman=nomor)}">← Kembali ke materi</a>'
                '<p class="editorial-alis-st">MATERI DIPILIH</p>'
                f'<h2 id="judul-materi">{html.escape(nama)}</h2>'
                f'<p><b>{terbukti} dari {len(hasil)} target</b> menunjukkan pemahaman.</p>'
                '<p class="peta-catatan">Belum dinilai bukan berarti tidak mampu. '
                'Bukti terkonfirmasi dan anak bisa menjelaskan diperlukan, bukan hanya jawaban benar.</p>'
                '<ul class="peta-target">' + ''.join(_rincian_target(t, s, tanggal) for t, s in pasangan)
                + '</ul>'
                f'<a class="laporan-tautan" href="{url(tampilan="kriteria")}">Baca kriteria penilaian →</a></section>'
            )
    kosong = (
        '<p>Tidak ada materi yang cocok dengan filter ini.</p>'
        f'<a class="laporan-tautan" href="{url()}">Tampilkan semua materi</a>' if not bagian else ''
    )
    return (
        '<section class="peta-materi-st' + (' peta-detail-aktif' if eksplisit else '')
        + '" id="peta-penguasaan" aria-labelledby="judul-peta">'
        '<header class="peta-ringkas"><h2 id="judul-peta">Progres penguasaan materi Jagomat</h2>'
        f'<p><b>{peta.jumlah["terbukti"]} dari {len(peta.target)} target</b> menunjukkan pemahaman '
        f'· {html.escape(label_kelas(peta.level))} · {len(per_topik)} materi.</p>'
        '<p class="peta-catatan">Filter hanya memilih kartu, bukan mengubah jumlah seluruh target. '
        'Urutan mengikuti katalog, bukan prioritas belajar.</p></header>'
        '<div class="peta-panel"><div class="peta-pemilih"><h3>Pilih materi untuk melihat targetnya</h3>'
        + pilihan('Status materi', tombol, status, lambda k: url(status=k))
        + '<p class="peta-catatan">Belum dinilai: seluruh target belum dinilai. '
        'Status lain: ada target dengan status tersebut.</p>'
        + '<div class="peta-daftar">' + ''.join(kartu) + '</div>' + kosong
        + navigasi_halaman(nomor, jumlah, lambda n: url(status=status, halaman=n))
        + f'<p class="peta-catatan">Menampilkan {len(bagian)} dari {len(daftar)} materi sesuai filter.</p>'
        + '</div>' + detail + '</div></section>'
    )
