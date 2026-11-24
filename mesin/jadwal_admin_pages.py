"""Render admin jadwal Paket Belajar: daftar kelompok, detail kelompok, penempatan, dan 8 pertemuan.

Murni render (tanpa DB/HTTP). Semua nilai dinamis di-escape; tidak ada nama anak, kontak, atau isi berkas.
Token CSRF/tinjauan disuntik pemanggil per aksi; tanpa sandi ulang karena ini penjadwalan, bukan aksi uang.
"""
from __future__ import annotations

import html
from typing import Mapping, Optional, Sequence

import admin_verifikasi_pages as vp
import jadwal_dasar as jd
import paket_belajar_katalog as katalog
from pesanan_transfer_pages import waktu_wib

RUTE_KELOMPOK = "/admin/kelas/kelompok"
JUDUL_DAFTAR = "Kelompok Mini Class & jadwal"
COPY_KOSONG = "Belum ada kelompok Mini Class."
COPY_PETUNJUK = ("Mini Class dijadwalkan per kelompok (maksimal 5 anak): satu lokasi, satu guru, delapan "
                 "pertemuan mingguan. Private dijadwalkan per anak dari halaman detail order.")
COPY_TANPA_GURU = "Belum ada akun guru aktif. Tambah akun guru dulu sebelum menjadwalkan."
COPY_KUOTA_PENUH = "Semua kelompok sudah penuh; buat kelompok baru atau lepaskan anggota."
COPY_TANPA_KELOMPOK = "Belum ada kelompok Mini Class. Buat kelompok dulu di halaman antrean."
COPY_SESI_KOSONG = "Belum ada pertemuan."
COPY_TANPA_ANGGOTA = "Belum ada anak ditempatkan di kelompok ini."
COPY_BELUM_AKTIF = "Jadwal bisa dibuat setelah bukti transfer disetujui (paket aktif)."
COPY_LEPAS = ("Lepas penempatan anak ini? Sesi Private ikut dihapus; sesi kelompok tetap milik kelompok. "
              "Anak bisa ditempatkan lagi setelahnya.")
COPY_BATAL = "Batalkan pertemuan ini? Pertemuan tetap tercatat sebagai dibatalkan dan bisa diaktifkan lagi."
COPY_AKTIFKAN = "Aktifkan lagi pertemuan yang dibatalkan ini?"


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _opsi_guru(guru: Mapping[str, str], terpilih: str = "") -> str:
    opsi = ['<option value="">Pilih guru</option>']
    for akun, nama in sorted(guru.items(), key=lambda x: x[1].casefold()):
        opsi.append('<option value="%s"%s>%s</option>'
                    % (_e(akun), " selected" if akun == terpilih else "", _e(nama)))
    if terpilih and terpilih not in guru:
        opsi.append('<option value="%s" selected>Akun guru tidak aktif</option>' % _e(terpilih))
    return "".join(opsi)


def _hidden(token) -> str:
    return vp._hidden(token["csrf"], token["tinjauan"])


def _waktu(baku: Optional[str]) -> str:
    return "—" if not baku else waktu_wib(baku)


def _form_buat(token, guru: Mapping[str, str]) -> str:
    return (
        '<section class="admin-kartu admin-form-pendek"><h2>Buat kelompok Mini Class</h2>'
        '<form method="post" action="%s">%s'
        '<label>Nama kelompok<input type="text" name="nama" required maxlength="80" autocomplete="off"></label>'
        '<label>Lokasi<input type="text" name="lokasi" required maxlength="200" autocomplete="off"></label>'
        '<label>Guru<select name="guru_id" required>%s</select></label>'
        '<label>Kuota<input type="number" name="kuota" min="1" max="5" value="5" required></label>'
        '<label>Tanggal mulai<input type="date" name="tanggal" required></label>'
        '<label>Jam mulai (WIB)<input type="time" name="jam" required></label>'
        '<button class="admin-tombol" type="submit">Buat kelompok + 8 pertemuan</button></form></section>'
        % (RUTE_KELOMPOK, _hidden(token), _opsi_guru(guru)))


def blok_daftar(daftar: Sequence[Mapping], guru: Mapping[str, str], token) -> str:
    """Blok di halaman antrean: petunjuk, tabel kelompok, dan form buat."""
    if guru:
        form = _form_buat(token, guru)
        catatan = ""
    else:
        form = ""
        catatan = '<p class="admin-meta">%s</p>' % _e(COPY_TANPA_GURU)
    baris = "".join(
        "<tr><td><a class=\"admin-tautan\" href=\"%s?id=%s\">%s</a></td><td>%s</td><td>%s</td>"
        "<td>%d/%d</td><td>%s</td></tr>"
        % (RUTE_KELOMPOK, _e(b["id"]), _e(b["nama"]), _e(b["lokasi"]),
           _e(guru.get(b["guru_id"], "Akun guru tidak aktif")), b["terisi"], b["kuota"],
           _waktu(b["berikut"]))
        for b in daftar)
    tabel = vp._tabel("Kelompok", ("Nama", "Lokasi", "Guru", "Terisi", "Pertemuan berikut"), baris, COPY_KOSONG)
    return ('<section class="admin-kartu"><h2>%s</h2><p class="admin-meta">%s</p>%s%s</section>'
            % (_e(JUDUL_DAFTAR), _e(COPY_PETUNJUK), tabel, form + catatan))


def _baris_sesi(sesi: Sequence[Mapping], token_ubah, token_batal, *, bisa_ubah: bool) -> str:
    baris = []
    for s in sesi:
        tanggal, jam = jd.tanggal_jam_wib(s["mulai"])
        status = "Dibatalkan" if s["dibatalkan"] else "Aktif"
        aksi = ""
        if bisa_ubah:
            aksi = (
                '<form method="post" action="/admin/kelas/pertemuan" class="admin-form-baris">%s'
                '<input type="hidden" name="pertemuan_id" value="%d">'
                '<input type="date" name="tanggal" value="%s" required>'
                '<input type="time" name="jam" value="%s" required>'
                '<button class="admin-tombol" type="submit">Simpan</button></form>'
                '<form method="post" action="/admin/kelas/pertemuan/batal" data-konfirmasi="%s">%s'
                '<input type="hidden" name="pertemuan_id" value="%d">'
                '<input type="hidden" name="batal" value="%d">'
                '<button class="admin-tombol admin-bahaya" type="submit">%s</button></form>'
                % (_hidden(token_ubah), s["id"], _e(tanggal), _e(jam),
                   _e(COPY_AKTIFKAN if s["dibatalkan"] else COPY_BATAL), _hidden(token_batal), s["id"],
                   0 if s["dibatalkan"] else 1, "Aktifkan" if s["dibatalkan"] else "Batalkan"))
        baris.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (s["ke"], _e(_waktu(s["mulai"])), _e(status), aksi))
    return vp._tabel("Delapan pertemuan", ("Ke", "Waktu (WIB)", "Status", "Aksi"), "".join(baris), COPY_SESI_KOSONG)


def halaman_kelompok(detail: Mapping, guru: Mapping[str, str], tokens: Mapping) -> str:
    """Detail kelompok: ringkasan, form ubah, anggota, dan delapan pertemuan."""
    b = detail["kelompok"]
    ubah = (
        '<section class="admin-kartu admin-form-pendek"><h2>Ubah kelompok</h2>'
        '<form method="post" action="%s/ubah">%s'
        '<label>Nama kelompok<input type="text" name="nama" value="%s" required maxlength="80"></label>'
        '<label>Lokasi<input type="text" name="lokasi" value="%s" required maxlength="200"></label>'
        '<label>Guru<select name="guru_id" required>%s</select></label>'
        '<label>Kuota<input type="number" name="kuota" min="1" max="5" value="%d" required></label>'
        '<button class="admin-tombol" type="submit">Simpan perubahan</button></form></section>'
        % (RUTE_KELOMPOK, _hidden(tokens["ubah"]), _e(b["nama"]), _e(b["lokasi"]),
           _opsi_guru(guru, b["guru_id"]), b["kuota"]))
    anggota = "".join(
        '<tr><td><a class="admin-tautan" href="/admin/kelas/verifikasi?order=%s">%s</a></td><td>%d</td>'
        "<td>%s</td></tr>" % (_e(a["order_id"]), _e(a["order_id"]), a["siswa_id"], _e(_waktu(a["berakhir"])))
        for a in detail["anggota"])
    tabel_anggota = vp._tabel("Anggota", ("Order", "Anak", "Akses berakhir"), anggota, COPY_TANPA_ANGGOTA)
    return (
        '<section class="admin-kartu"><h2>%s</h2>'
        '<p>%s · %s · Guru %s · %d/%d anak</p>'
        '<p><a class="admin-tautan" href="/admin/kelas">Kembali ke antrean</a></p></section>'
        % (_e(b["nama"]), _e(b["lokasi"]), _e(katalog.ambil(b["paket"]).nama),
           _e(guru.get(b["guru_id"], "Akun guru tidak aktif")), detail["terisi"], b["kuota"])
        + ubah + tabel_anggota
        + _baris_sesi(detail["sesi"], tokens["sesi_ubah"], tokens["sesi_batal"], bisa_ubah=True))


def _sisa_kelompok(daftar: Sequence[Mapping]) -> str:
    opsi = []
    for b in daftar:
        sisa = b["kuota"] - b["terisi"]
        if sisa > 0:
            opsi.append('<option value="%s">%s — sisa %d anak</option>'
                        % (_e(b["id"]), _e(b["nama"]), sisa))
    return "".join(opsi)


def blok_penempatan(order: Mapping, ringkas: Optional[Mapping], kelompok: Sequence[Mapping],
                    guru: Mapping[str, str], bisa_tempatkan: bool, tokens: Mapping) -> str:
    """Kartu di detail order: penempatan, ringkasan, dan jadwal Private."""
    if ringkas is None:
        if not bisa_tempatkan:
            return ('<section class="admin-kartu"><h2>Penempatan & jadwal</h2><p class="admin-meta">%s</p></section>'
                    % _e(COPY_BELUM_AKTIF))
        if order["paket"] == "mini":
            if not kelompok:
                return ('<section class="admin-kartu"><h2>Penempatan & jadwal</h2><p class="admin-meta">%s</p>'
                        '<p><a class="admin-tautan" href="/admin/kelas">Buka antrean & kelompok</a></p></section>'
                        % _e(COPY_TANPA_KELOMPOK))
            opsi = _sisa_kelompok(kelompok)
            if not opsi:
                return ('<section class="admin-kartu"><h2>Penempatan & jadwal</h2><p class="admin-meta">%s</p>'
                        '<p><a class="admin-tautan" href="/admin/kelas">Buka antrean & kelompok</a></p></section>'
                        % _e(COPY_KUOTA_PENUH))
            return (
                '<section class="admin-kartu admin-form-pendek"><h2>Penempatan & jadwal</h2>'
                '<form method="post" action="/admin/kelas/penempatan">%s'
                '<label>Kelompok Mini Class<select name="kelompok_id" required>%s</select></label>'
                '<button class="admin-tombol" type="submit">Tempatkan ke kelompok</button></form></section>'
                % (_hidden(tokens["tempatkan"]), opsi))
        return (
            '<section class="admin-kartu admin-form-pendek"><h2>Penempatan & jadwal Private</h2>'
            '<form method="post" action="/admin/kelas/penempatan">%s'
            '<label>Guru<select name="guru_id" required>%s</select></label>'
            '<label>Tanggal mulai<input type="date" name="tanggal" required></label>'
            '<label>Jam mulai (WIB)<input type="time" name="jam" required></label>'
            '<button class="admin-tombol" type="submit">Buat 8 pertemuan Private</button></form></section>'
            % (_hidden(tokens["tempatkan"]), _opsi_guru(guru)))
    if ringkas["kelompok_id"]:
        sesi = _baris_sesi(ringkas["sesi"], None, None, bisa_ubah=False)
        isi = ('<p>Kelompok <a class="admin-tautan" href="%s?id=%s">%s</a> · %s · Guru %s</p>'
               % (RUTE_KELOMPOK, _e(ringkas["kelompok_id"]), _e(ringkas["kelompok_nama"]),
                  _e(ringkas["kelompok_lokasi"]), _e(guru.get(ringkas["kelompok_guru"], "Akun guru tidak aktif"))))
    else:
        sesi = _baris_sesi(ringkas["sesi"], tokens["sesi_ubah"], tokens["sesi_batal"], bisa_ubah=True)
        isi = ('<p>Private · %s · Guru %s</p>'
               % (_e(ringkas["lokasi"]), _e(guru.get(ringkas["guru_id"], "Akun guru tidak aktif"))))
    lepas = ('<form method="post" action="/admin/kelas/penempatan/lepas" data-konfirmasi="%s">%s'
             '<button class="admin-tombol admin-bahaya" type="submit">Lepas penempatan</button></form>'
             % (_e(COPY_LEPAS), _hidden(tokens["lepas"])))
    return ('<section class="admin-kartu"><h2>Penempatan & jadwal</h2>%s%s%s</section>'
            % (isi, sesi, lepas))
