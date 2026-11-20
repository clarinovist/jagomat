"""Renderer HTML halaman admin "Buat soal" per bab Kurikulum Merdeka (tanpa JS; soal tidak disimpan).

Badan soal memakai renderer lembar cetak yang ada (`render._badan_soal`), bukan renderer baru.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

import kurikulum_buat_soal as buat
import kurikulum_kelas as kk
from admin_komponen import e, opsi
from admin_kurikulum_tab import TAB_KURIKULUM, tab_kurikulum
from render import _badan_soal
from template_labels import nama_tipe_soal

RUTE = "/admin/kurikulum/buat"
RUTE_UTAMA = "/admin/kurikulum"
CATATAN_BELUM_TERSIMPAN = (
    "Soal ini belum tersimpan; untuk dipakai anak, buat lewat Latihan guru seperti biasa."
)
CATATAN_CETAK = "Untuk mencetak halaman ini, gunakan Cetak di browser."
PESAN_TANPA_PELATIH = "Bab ini belum punya jenis soal di kelas %d."
PESAN_TERTUTUP = "Jenis soal bab ini sudah ada di kode, tetapi belum dinyalakan di server ini, jadi belum bisa dibuatkan contoh."


def url_buat(kelas: int, bab: int, jumlah: int, seed: Optional[int] = None) -> str:
    kueri = {"kelas": kelas, "bab": bab, "jumlah": jumlah}
    if seed is not None:
        kueri["seed"] = seed
    return "%s?%s" % (RUTE, urlencode(kueri))


def _form(kelas: int, bab: int, jumlah: int, seed: int) -> str:
    pilihan = "".join(opsi(str(j), "%d soal" % j, str(jumlah)) for j in buat.JUMLAH_PILIHAN)
    return (
        '<form method="get" action="%s" class="admin-form-cari kur-layar">'
        '<input type="hidden" name="kelas" value="%d"><input type="hidden" name="bab" value="%d">'
        '<input type="hidden" name="seed" value="%d">'
        '<label>Jumlah soal<select name="jumlah">%s</select></label>'
        '<button class="admin-tombol" type="submit">Tampilkan</button></form>'
    ) % (RUTE, kelas, bab, seed, pilihan)


def _baris_item(item: buat.ItemSoal) -> str:
    s = item.soal
    jenis = [item.nama_grup, nama_tipe_soal(s.template_id)]
    return (
        '<li><p class="admin-meta">Soal %d · %s</p><div class="kur-soal">%s</div>'
        '<p class="kur-kunci"><strong>Kunci jawaban:</strong> %s</p></li>'
    ) % (item.nomor, e(" · ".join(dict.fromkeys(jenis))),
         _badan_soal(s, item.paket, "buat-%d" % item.nomor), e(s.kunci))


def _isi_soal(kelas: int, hasil: buat.HasilBuat) -> str:
    if not hasil.ada_pelatih:
        return '<p class="admin-kartu admin-catatan" role="note">%s</p>' % e(PESAN_TANPA_PELATIH % kelas)
    if not hasil.bisa_dibuat:
        return '<p class="admin-kartu admin-catatan" role="note">%s</p>' % e(PESAN_TERTUTUP)
    kurang = ""
    if len(hasil.item) < hasil.jumlah_diminta:
        kurang = '<p class="admin-meta">Hanya %d dari %d soal yang berhasil dibuat tanpa kembar: variasi bab ini sudah habis.</p>' % (
            len(hasil.item), hasil.jumlah_diminta)
    tutup = ""
    if hasil.template_tertutup:
        tutup = '<p class="admin-meta">Belum dinyalakan, tidak ikut dibuat: %s.</p>' % e(
            ", ".join(nama_tipe_soal(t) for t in hasil.template_tertutup))
    return '%s%s<ol class="kur-soal-daftar">%s</ol>' % (
        kurang, tutup, "".join(_baris_item(i) for i in hasil.item))


def halaman(kelas: int, bab: kk.Bab, hasil: buat.HasilBuat, jumlah: int, seed: int) -> str:
    """Isi halaman Buat soal untuk satu bab; `seed` sudah final (diundi pemanggil bila tak diberikan)."""
    sub = "".join("<li>%s</li>" % e(x) for x in bab.sub_materi)
    return (
        tab_kurikulum(TAB_KURIKULUM)
        + '<p class="kur-layar"><a href="%s">&larr; Kembali ke Kurikulum Merdeka</a></p>' % RUTE_UTAMA
        + '<section class="admin-kartu"><h2>Kelas %d · Bab %d: %s</h2><ul>%s</ul>'
          '<p class="admin-meta">%s</p><p class="admin-meta kur-layar">%s</p>'
          '<div class="kur-aksi-baris kur-layar"><span class="admin-meta">Seed: %d</span>'
          '<a href="%s">Buat ulang dengan soal lain</a><a href="%s">Tautan tetap soal ini</a></div>%s</section>' % (
              kelas, bab.nomor, e(bab.judul), sub, e(CATATAN_BELUM_TERSIMPAN), e(CATATAN_CETAK), seed,
              e(url_buat(kelas, bab.nomor, jumlah)), e(url_buat(kelas, bab.nomor, jumlah, seed)),
              _form(kelas, bab.nomor, jumlah, seed))
        + _isi_soal(kelas, hasil)
    )
