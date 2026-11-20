"""Renderer HTML murni halaman admin "Kurikulum Merdeka" (tabel materi per kelas; tanpa JS, tanpa I/O).

Data (status, jenis, variasi, pemakaian) dihitung `kurikulum_kelas_hitung` dan disuntikkan pemanggil.
Halaman hanya menampilkan agregat; tidak ada data atau jawaban anak.
"""
from __future__ import annotations

from typing import Sequence, Tuple
from urllib.parse import urlencode

import kurikulum_kelas as kk
import kurikulum_kelas_hitung as hitung
from admin_komponen import e
from admin_kurikulum_tab import TAB_KURIKULUM, tab_kurikulum
from template_labels import nama_tipe_soal

RUTE = "/admin/kurikulum"
RUTE_BUAT = "/admin/kurikulum/buat"
RUTE_CETAKAN = "/admin/kurikulum/cetakan"
TANPA_DATA = "–"
# Lima kolom agar Status dan tombol Buat soal tetap terlihat di layar 1280 px tanpa gulir samping.
KOLOM = ("No", "Materi dan sub-materi", "Soal Jagomat", "Jumlah soal", "Status")
KETERANGAN_KOLOM = (
    ("Materi dan sub-materi", "Judul bab di buku siswa kelas itu, lalu pokok bahasan di dalamnya."),
    ("Soal Jagomat", "Jenis soal Jagomat yang melatih bab itu; baris \"Cetakan\" = cetakan berpola aktif buatan admin."),
    ("Jumlah soal: jenis", "Berapa macam soal yang tersedia untuk bab itu di kelas tersebut."),
    ("Jumlah soal: variasi", "Perkiraan banyaknya soal berbeda yang bisa dibuat: angka tanpa tanda itu tepat, \"±\" perkiraan "
                "dari %d contoh, \"banyak\" berarti lebih dari itu." % hitung.JUMLAH_SAMPEL),
    ("Jumlah soal: dipakai", "Berapa soal bab ini yang pernah dibuat untuk latihan di aplikasi (jumlahnya saja)."),
    ("Status", "Sudah ada soal, perlu disempurnakan (soal ada tetapi belum pas), atau belum ada soal. "
               "Tautan Buat soal membuat contoh soal dari bab itu, hanya untuk dilihat; Kelola cetakan membuka cetakan berpola bab itu."),
)
CATATAN_TUTUP = (
    "Jenis soal bertanda \"belum dinyalakan\" sudah ada di kode tetapi sakelar rilisnya masih mati di server ini, "
    "jadi belum dihitung dalam variasi dan belum bisa dibuatkan contoh."
)


def url_buat(kelas: int, bab: int) -> str:
    return "%s?%s" % (RUTE_BUAT, urlencode({"kelas": kelas, "bab": bab}))


def _nama_pelatih(p: hitung.PelatihKelas) -> str:
    isi = "%s · %s" % (e(p.nama_topik), e(p.nama_grup))
    if not p.tersedia:
        ada = ", ".join(str(k) for k in p.kelas_lain)
        return isi + ' <span class="admin-meta">(%s)</span>' % (
            "baru ada di kelas %s" % ada if ada else "belum ada di kelas mana pun")
    if p.kecocokan == "sebagian":
        isi += ' <span class="admin-meta">(sebagian)</span>'
    return isi


def url_cetakan(kelas: int, bab: int) -> str:
    return "%s?%s" % (RUTE_CETAKAN, urlencode({"kelas": kelas, "bab": bab}))


def _sel_soal(b: hitung.RingkasanBab) -> str:
    baris = [_nama_pelatih(p) for p in b.pelatih]
    baris += ["Cetakan: %s" % e(c.cetakan.judul) for c in b.cetakan]
    return "<br>".join(baris) or '<span class="admin-meta">-</span>'


def teks_variasi(v: hitung.VariasiBab) -> str:
    if v.jenis == hitung.JENIS_BANYAK:
        return "banyak"
    return ("±%d" if v.jenis == hitung.JENIS_PERKIRAAN else "%d") % v.total


def _sel_variasi(b: hitung.RingkasanBab) -> str:
    v = b.variasi
    isi = e(teks_variasi(v))
    for label, daftar in ((hitung.CATATAN_TUTUP, v.tertutup), (hitung.CATATAN_GALAT, v.galat)):
        if daftar:
            isi += '<br><span class="admin-meta">%s: %s</span>' % (
                e(label), e(", ".join(nama_tipe_soal(t) for t in daftar)))
    return isi


def _sel_aksi(kelas: int, b: hitung.RingkasanBab) -> str:
    kelola = '<br><a href="%s">Kelola cetakan</a>' % e(url_cetakan(kelas, b.nomor))
    if b.jenis - len(b.variasi.tertutup) <= 0:
        return kelola
    return '<br><a href="%s">Buat soal</a>' % e(url_buat(kelas, b.nomor)) + kelola


def _baris(kelas: int, b: hitung.RingkasanBab) -> str:
    sub = "<br>".join("• " + e(x) for x in b.sub_materi)
    pakai = TANPA_DATA if b.terpakai is None else str(b.terpakai)
    jumlah = "Jenis: %d<br>Variasi: %s<br>Dipakai: %s" % (b.jenis, _sel_variasi(b), e(pakai))
    return (
        "<tr><td>%d</td><td><strong>%s</strong><br>%s</td><td>%s</td><td>%s</td><td><strong>%s</strong>%s</td></tr>"
    ) % (b.nomor, e(b.judul), sub, _sel_soal(b), jumlah, e(hitung.LABEL_STATUS[b.status]), _sel_aksi(kelas, b))


def _kartu_kelas(kelas: int, bab: Sequence[hitung.RingkasanBab]) -> str:
    st = [b.status for b in bab]
    kepala = "".join('<th scope="col">%s</th>' % e(k) for k in KOLOM)
    return (
        '<section class="admin-kartu admin-kartu-tabel" aria-labelledby="kelas-%d"><div class="admin-kartu-kepala">'
        '<h2 id="kelas-%d">Kelas %d</h2><span class="admin-meta">%d bab · %d sudah ada soal · '
        '%d perlu disempurnakan · %d belum ada soal</span></div>'
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-labelledby="kelas-%d">'
        '<table class="admin-tabel kur-tabel"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div></section>'
    ) % (kelas, kelas, kelas, len(st), st.count(hitung.STATUS_ADA), st.count(hitung.STATUS_SEBAGIAN),
         st.count(hitung.STATUS_BELUM), kelas, kepala, "".join(_baris(kelas, b) for b in bab))


def _kepala(semua: Sequence[hitung.RingkasanBab], pemakaian_terbaca: bool) -> str:
    st = [b.status for b in semua]
    ringkas = "Total %d bab · %d sudah ada soal · %d perlu disempurnakan · %d belum ada soal." % (
        len(st), st.count(hitung.STATUS_ADA), st.count(hitung.STATUS_SEBAGIAN), st.count(hitung.STATUS_BELUM))
    keterangan = "".join("<dt>%s</dt><dd>%s</dd>" % (e(k), e(v)) for k, v in KETERANGAN_KOLOM)
    catatan = "" if pemakaian_terbaca else (
        '<p class="admin-meta">Data pemakaian belum bisa dibaca saat ini, jadi kolom "Sudah dipakai" kosong (%s).</p>'
        % TANPA_DATA)
    tutup = any(b.variasi.tertutup for b in semua)
    return (
        '<section class="admin-kartu"><h2>Kurikulum Merdeka per kelas</h2><p class="admin-meta">Sumber bab: %s. %s</p>'
        '%s%s<details><summary>Arti tiap kolom</summary><dl class="admin-rincian">%s</dl></details></section>'
    ) % (e(kk.SUMBER_BAB), e(ringkas), catatan,
         '<p class="admin-meta">%s</p>' % e(CATATAN_TUTUP) if tutup else "", keterangan)


def _pengayaan() -> str:
    daftar = hitung.grup_pengayaan()
    isi = "".join(
        '<li><p class="kurikulum-kepala">%s</p><p class="admin-meta">%s</p></li>' % (e(t), e(", ".join(n)))
        for t, n in daftar)
    return (
        '<details class="admin-kartu"><summary>Pengayaan di luar buku <span class="admin-meta">%d grup soal</span>'
        '</summary><ul class="kurikulum-daftar">%s</ul></details>'
    ) % (sum(len(n) for _t, n in daftar), isi)


def halaman(per_kelas: Sequence[Tuple[int, Sequence[hitung.RingkasanBab]]], pemakaian_terbaca: bool) -> str:
    """Isi halaman; `per_kelas` = ((kelas, ringkasan bab), ...) urut kelas."""
    semua = [b for _k, bab in per_kelas for b in bab]
    return (
        tab_kurikulum(TAB_KURIKULUM) + _kepala(semua, pemakaian_terbaca)
        + "".join(_kartu_kelas(k, bab) for k, bab in per_kelas) + _pengayaan()
    )
