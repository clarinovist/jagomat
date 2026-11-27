"""Render admin jadwal Paket Belajar: daftar kelompok, detail kelompok, penempatan, dan 8 pertemuan.

Murni render (tanpa DB/HTTP). Semua nilai dinamis di-escape; tidak ada nama anak, kontak, atau isi berkas.
Token CSRF/tinjauan disuntik pemanggil per aksi; tanpa sandi ulang karena ini penjadwalan, bukan aksi uang.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Mapping, Optional, Sequence

import admin_labels as L
import admin_verifikasi_pages as vp
import jadwal_dasar as jd
import jadwal_private_admin_pages as pv
import paket_belajar_katalog as katalog
from pesanan_transfer_pages import waktu_wib

RUTE_KELOMPOK = "/admin/kelas/kelompok"
JUDUL_DAFTAR = "Kelompok Mini Class & jadwal"
COPY_KOSONG = "Belum ada kelompok Mini Class."
COPY_TAUTAN_PRIVATE = "Jadwal Private: slot guru dan pengajuan orang tua"
COPY_PETUNJUK = ("Mini Class dijadwalkan per kelompok (maksimal 5 anak): satu tautan Zoom atau Google Meet, "
                 "satu guru, delapan pertemuan, dua kali seminggu selama empat pekan (selesai dalam masa akses 1 bulan). "
                 "Private dijadwalkan per anak dari halaman detail order.")
COPY_TANPA_GURU = "Belum ada akun guru aktif. Tambah akun guru dulu sebelum menjadwalkan."
COPY_KUOTA_PENUH = ("Semua kelompok sudah penuh, selesai, atau ditutup (pendaftaran ditutup setelah dua pertemuan "
                    "mulai); buat kelompok baru atau lepaskan anggota.")
COPY_BENTROK_SESI = "Bentrok dengan jadwal guru lain"
COPY_BENTROK_PERINGATAN = ("Guru ini punya pertemuan lain di jam yang sama; periksa dan geser bila perlu. "
                           "Penyimpanan tidak diblokir.")
COPY_BENTROK_KOLOM = "Bentrok jadwal guru: %d pertemuan"
COPY_LUAR_JAM_SESI = "Di luar jam tetap guru"
COPY_LUAR_JAM_PERINGATAN = ("Ada pertemuan di luar jam tetap guru. "
                            "Jadwal tetap hanya acuan; penyimpanan tidak diblokir.")
COPY_TAUTAN_TETAP = "Jadwal tetap guru"
RUTE_TUNGGU_HAPUS = RUTE_KELOMPOK + "/tunggu/hapus"
COPY_TUNGGU_JUDUL = "Daftar tunggu Mini Class"
COPY_TUNGGU_KOSONG = "Belum ada anak di daftar tunggu kelompok ini."
COPY_TUNGGU_GAGAL = "Daftar tunggu belum bisa dibaca. Muat ulang halaman; penempatan tetap bisa dilakukan dari antrean."
COPY_HAPUS_TUNGGU = ("Hapus anak ini dari daftar tunggu? Orang tua harus masuk daftar lagi bila masih mau menunggu "
                     "kursi di kelompok ini.")
COPY_TUNGGU_DITEMPATKAN = "sudah ditempatkan"
COPY_TUNGGU_ANTRE = "menunggu kursi"
RUTE_TETAP = "/admin/jadwal/tetap"
KUNCI_LUAR_JAM = "luar_jam"
STRIP = "—"
COPY_TANPA_KELOMPOK = "Belum ada kelompok Mini Class. Buat kelompok dulu di halaman antrean."
COPY_SESI_KOSONG = "Belum ada pertemuan."
COPY_TANPA_ANGGOTA = "Belum ada anak ditempatkan di kelompok ini."
COPY_BELUM_AKTIF = "Jadwal bisa dibuat setelah bukti transfer disetujui (paket aktif)."
COPY_LEPAS = ("Lepas penempatan anak ini? Private hanya bisa dilepas sebelum pertemuan pertama; sesinya ikut dihapus. "
              "Mini Class bisa dilepas kapan saja; sesi kelompok tetap milik kelompok. "
              "Perpanjangan tidak perlu dilepas dulu: penempatan lama yang aksesnya sudah berakhir dipensiunkan otomatis.")
COPY_BATAL = "Batalkan pertemuan ini? Pertemuan tetap tercatat sebagai dibatalkan dan bisa diaktifkan lagi."
COPY_AKTIFKAN = "Aktifkan lagi pertemuan yang dibatalkan ini?"
RUTE_JURNAL = "/admin/jadwal/jurnal/%d"
COPY_TAUTAN_JURNAL = "Jurnal dan kehadiran"
FORMAT_WAKTU_BAKU = "%Y-%m-%dT%H:%M:%S"


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
    return STRIP if not baku else waktu_wib(baku)


def _peringatan_kelompok(kelompok: Mapping) -> str:
    """Teks peringatan bentrok per kelompok (angka dipaksa int); strip bila tidak ada."""
    jumlah = int(kelompok.get("bentrok", 0))
    return COPY_BENTROK_KOLOM % jumlah if jumlah > 0 else STRIP


def _form_buat(token, guru: Mapping[str, str]) -> str:
    return (
        '<section class="admin-kartu admin-form-pendek"><h2>Buat kelompok Mini Class</h2>'
        '<form method="post" action="%s">%s'
        '<label>Nama kelompok<input type="text" name="nama" required maxlength="80" autocomplete="off"></label>'
        '<label>Tautan Zoom atau Google Meet<input type="url" inputmode="url" name="lokasi" required maxlength="200" '
        'autocomplete="off" placeholder="https://..."></label>'
        '<label>Guru<select name="guru_id" required>%s</select></label>'
        '<label>Kuota<input type="number" name="kuota" min="1" max="5" value="5" required></label>'
        '<label>Tanggal mulai<input type="date" name="tanggal" required></label>'
        '<label>Jam mulai (WIB)<input type="time" name="jam" required></label>'
        '<button class="admin-tombol" type="submit">Buat kelompok + 8 pertemuan</button></form></section>'
        % (RUTE_KELOMPOK, _hidden(token), _opsi_guru(guru)))


def blok_daftar(daftar: Sequence[Mapping], guru: Mapping[str, str], token, *, tautan_tetap: bool = False) -> str:
    """Blok di halaman antrean: petunjuk, tabel kelompok, dan form buat."""
    if guru:
        form = _form_buat(token, guru)
        catatan = ""
    else:
        form = ""
        catatan = '<p class="admin-meta">%s</p>' % _e(COPY_TANPA_GURU)
    baris = "".join(
        "<tr><td><a class=\"admin-tautan\" href=\"%s?id=%s\">%s</a></td><td>%s</td><td>%s</td>"
        "<td>%d/%d</td><td>%s</td><td>%s</td></tr>"
        % (RUTE_KELOMPOK, _e(b["id"]), _e(b["nama"]), _e(b["lokasi"]),
           _e(guru.get(b["guru_id"], "Akun guru tidak aktif")), b["terisi"], b["kuota"],
           _waktu(b["berikut"]), _e(_peringatan_kelompok(b)))
        for b in daftar)
    tabel = vp._tabel("Kelompok", ("Nama", "Tautan", "Guru", "Terisi", "Pertemuan berikut", "Peringatan"),
                      baris, COPY_KOSONG)
    tautan = '<p><a class="admin-tautan" href="%s">%s</a></p>' % (pv.RUTE, _e(COPY_TAUTAN_PRIVATE))
    if tautan_tetap:
        tautan += '<p><a class="admin-tautan" href="%s">%s</a></p>' % (RUTE_TETAP, _e(COPY_TAUTAN_TETAP))
    return ('<section class="admin-kartu"><h2>%s</h2><p class="admin-meta">%s</p>%s%s%s</section>'
            % (_e(JUDUL_DAFTAR), _e(COPY_PETUNJUK), tautan, tabel, form + catatan))


def _aksi_sesi(sesi: Mapping, token_ubah, token_batal) -> str:
    """Dua form aksi satu pertemuan (simpan waktu, batalkan/aktifkan) dalam satu baris."""
    dibatalkan = bool(sesi["dibatalkan"])
    tanggal, jam = jd.tanggal_jam_wib(sesi["mulai"])
    kelas_tombol = "admin-tombol" if dibatalkan else "admin-tombol admin-bahaya"
    return (
        '<div class="admin-aksi-sesi-baris">'
        '<form method="post" action="/admin/kelas/pertemuan" class="admin-form-baris">%s'
        '<input type="hidden" name="pertemuan_id" value="%d">'
        '<input type="date" name="tanggal" value="%s" required>'
        '<input type="time" name="jam" value="%s" required>'
        '<button class="admin-tombol" type="submit">Simpan</button></form>'
        '<form method="post" action="/admin/kelas/pertemuan/batal" class="admin-form-baris" '
        'data-konfirmasi="%s">%s'
        '<input type="hidden" name="pertemuan_id" value="%d">'
        '<input type="hidden" name="batal" value="%d">'
        '<button class="%s" type="submit">%s</button></form></div>'
        % (_hidden(token_ubah), sesi["id"], _e(tanggal), _e(jam),
           _e(COPY_AKTIFKAN if dibatalkan else COPY_BATAL), _hidden(token_batal), sesi["id"],
           0 if dibatalkan else 1, kelas_tombol, "Aktifkan" if dibatalkan else "Batalkan"))


def _waktu_baku(baku: str) -> datetime:
    return datetime.strptime(baku, FORMAT_WAKTU_BAKU)


def _tautan_jurnal(sesi: Mapping, kini: Optional[str]) -> str:
    """Tautan koreksi untuk pertemuan yang sudah mulai dan tidak dibatalkan; kosong bila tidak berlaku."""
    if kini is None or bool(sesi["dibatalkan"]) or _waktu_baku(sesi["mulai"]) > _waktu_baku(kini):
        return ""
    return '<a class="admin-tautan" href="%s">%s</a>' % (RUTE_JURNAL % int(sesi["id"]), _e(COPY_TAUTAN_JURNAL))


def _baris_sesi(sesi: Sequence[Mapping], token_ubah, token_batal, *, bisa_ubah: bool,
                kini: Optional[str] = None) -> str:
    baris = []
    for s in sesi:
        status = "Dibatalkan" if s["dibatalkan"] else "Aktif"
        if s.get("bentrok"):
            status += " · " + COPY_BENTROK_SESI
        if s.get(KUNCI_LUAR_JAM):
            status += " · " + COPY_LUAR_JAM_SESI
        aksi = (_aksi_sesi(s, token_ubah, token_batal) if bisa_ubah else "") + _tautan_jurnal(s, kini)
        baris.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (s["ke"], _e(_waktu(s["mulai"])), _e(status), aksi))
    peringatan = ('<p class="admin-catatan" role="note">%s</p>' % _e(COPY_BENTROK_PERINGATAN)
                  if any(s.get("bentrok") for s in sesi) else "")
    peringatan_luar = ('<p class="admin-catatan" role="note">%s</p>' % _e(COPY_LUAR_JAM_PERINGATAN)
                       if any(s.get(KUNCI_LUAR_JAM) for s in sesi) else "")
    return peringatan + peringatan_luar + vp._tabel("Delapan pertemuan", ("Ke", "Waktu (WIB)", "Status", "Aksi"),
                                                    "".join(baris), COPY_SESI_KOSONG)


def _baris_tunggu(entri, token: Optional[Mapping]) -> str:
    """Satu baris daftar tunggu. Hapus hanya untuk entri yang masih antre dan punya token (sesi cookie)."""
    aksi = ""
    if token is not None and not entri.sudah_ditempatkan:
        aksi = ('<form method="post" action="%s" data-konfirmasi="%s">%s'
                '<button class="admin-tombol admin-bahaya" type="submit">Hapus dari daftar tunggu</button></form>'
                % (RUTE_TUNGGU_HAPUS, _e(COPY_HAPUS_TUNGGU), _hidden(token)))
    urutan = STRIP if entri.urutan is None else str(entri.urutan)
    keadaan = COPY_TUNGGU_DITEMPATKAN if entri.sudah_ditempatkan else COPY_TUNGGU_ANTRE
    return ("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (_e(urutan), L.referensi_pendek(entri.order_id), _e(_waktu(entri.dibuat)), _e(keadaan), aksi))


def blok_tunggu(entri: Optional[Sequence], token_hapus: Mapping[int, Mapping]) -> str:
    """Daftar tunggu kelompok: urutan, order ringkas, tanggal masuk, keadaan, dan hapus. `entri` None = tak terbaca."""
    if entri is None:
        return ('<section class="admin-kartu"><h2>%s</h2><p class="admin-meta">%s</p></section>'
                % (_e(COPY_TUNGGU_JUDUL), _e(COPY_TUNGGU_GAGAL)))
    baris = "".join(_baris_tunggu(x, token_hapus.get(x.id)) for x in entri)
    return vp._tabel(COPY_TUNGGU_JUDUL, ("Urutan", "Order", "Masuk", "Keadaan", ""), baris, COPY_TUNGGU_KOSONG)


def halaman_kelompok(detail: Mapping, guru: Mapping[str, str], tokens: Mapping, *,
                     kini: Optional[str] = None, tunggu: Optional[Sequence] = ()) -> str:
    """Detail kelompok: ringkasan, form ubah, anggota, daftar tunggu, dan delapan pertemuan.

    `tunggu` = entri daftar tunggu (`jadwal_tunggu_mini.daftar_admin`); None = berkas tak terbaca (pesan jujur, halaman utuh).
    """
    b = detail["kelompok"]
    ubah = (
        '<section class="admin-kartu admin-form-pendek"><h2>Ubah kelompok</h2>'
        '<form method="post" action="%s/ubah">%s'
        '<label>Nama kelompok<input type="text" name="nama" value="%s" required maxlength="80"></label>'
        '<label>Tautan Zoom atau Google Meet<input type="url" inputmode="url" name="lokasi" value="%s" required '
        'maxlength="200" placeholder="https://..."></label>'
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
        '<p>%s · Tautan: %s · Guru %s · %d/%d anak</p>'
        '<p><a class="admin-tautan" href="/admin/kelas">Kembali ke antrean</a></p></section>'
        % (_e(b["nama"]), _e(b["lokasi"]), _e(katalog.ambil(b["paket"]).nama),
           _e(guru.get(b["guru_id"], "Akun guru tidak aktif")), detail["terisi"], b["kuota"])
        + ubah + tabel_anggota + blok_tunggu(tunggu, tokens.get("hapus_tunggu", {}))
        + _baris_sesi(detail["sesi"], tokens["sesi_ubah"], tokens["sesi_batal"], bisa_ubah=True, kini=kini))


def _sisa_kelompok(daftar: Sequence[Mapping]) -> str:
    """Opsi kelompok yang masih bisa dimasuki: belum penuh, belum selesai, dan belum ditutup (`terbuka`)."""
    opsi = []
    for b in daftar:
        sisa = b["kuota"] - b["terisi"]
        if sisa > 0 and b.get("berikut") and b.get("terbuka", True):
            opsi.append('<option value="%s">%s — sisa %d anak</option>'
                        % (_e(b["id"]), _e(b["nama"]), sisa))
    return "".join(opsi)


def blok_penempatan(order: Mapping, ringkas: Optional[Mapping], kelompok: Sequence[Mapping],
                    guru: Mapping[str, str], bisa_tempatkan: bool, tokens: Mapping, *,
                    kini: Optional[str] = None) -> str:
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
        sesi = _baris_sesi(ringkas["sesi"], None, None, bisa_ubah=False, kini=kini)
        isi = ('<p>Kelompok <a class="admin-tautan" href="%s?id=%s">%s</a> · Tautan: %s · Guru %s</p>'
               % (RUTE_KELOMPOK, _e(ringkas["kelompok_id"]), _e(ringkas["kelompok_nama"]),
                  _e(ringkas["kelompok_lokasi"]), _e(guru.get(ringkas["kelompok_guru"], "Akun guru tidak aktif"))))
    else:
        sesi = _baris_sesi(ringkas["sesi"], tokens["sesi_ubah"], tokens["sesi_batal"], bisa_ubah=True, kini=kini)
        isi = ('<p>Private · %s · Guru %s</p>'
               % (_e(ringkas["lokasi"]), _e(guru.get(ringkas["guru_id"], "Akun guru tidak aktif"))))
    lepas = ('<form method="post" action="/admin/kelas/penempatan/lepas" data-konfirmasi="%s">%s'
             '<button class="admin-tombol admin-bahaya" type="submit">Lepas penempatan</button></form>'
             % (_e(COPY_LEPAS), _hidden(tokens["lepas"])))
    return ('<section class="admin-kartu"><h2>Penempatan & jadwal</h2>%s%s%s</section>'
            % (isi, sesi, lepas))
