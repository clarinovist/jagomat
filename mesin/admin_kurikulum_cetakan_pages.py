"""Renderer HTML murni halaman admin cetakan soal berpola (tanpa JS, tanpa DB, tanpa I/O): daftar per bab,
form baru, dan periksa (pola, 10 contoh soal, uji kelayakan, riwayat, aksi menurut status).

Form hanya membawa csrf, tinjauan, sandi ulang, dan isian cetakan; target (kelas/bab atau id/revisi) hidup di
tinjauan bertanda tangan, bukan di field. SEMUA nilai dinamis (judul, teks, pembahasan, ekspresi, soal hasil,
pesan galat, nama pelaku) di-escape: isi cetakan nanti juga datang dari draf AI (C3), jadi anggap stored-XSS.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple
from urllib.parse import urlencode

import admin_kurikulum_cetakan_form as form
import cetakan_pola as pola
import cetakan_store as store
import kurikulum_kelas as kk
from admin_komponen import e
from admin_kurikulum_tab import TAB_KURIKULUM, tab_kurikulum

RUTE = "/admin/kurikulum/cetakan"
RUTE_BARU = RUTE + "/baru"
RUTE_PERIKSA = RUTE + "/periksa"
RUTE_UBAH = RUTE + "/ubah"
RUTE_SETUJUI = RUTE + "/setujui"
RUTE_NONAKTIFKAN = RUTE + "/nonaktifkan"
RUTE_AKTIFKAN = RUTE + "/aktifkan"
RUTE_KURIKULUM = "/admin/kurikulum"
AKSI_BUAT = "buat_cetakan_soal"
AKSI_UBAH = "ubah_cetakan_soal"
AKSI_SETUJUI = "setujui_cetakan_soal"
AKSI_NONAKTIFKAN = "nonaktifkan_cetakan_soal"
AKSI_AKTIFKAN = "aktifkan_cetakan_soal"
FIELD_BUAT = form.FIELD_ISI
FIELD_UBAH = form.FIELD_ISI
JUDUL_DAFTAR = "Cetakan soal"
SUBJUDUL_DAFTAR = "Cetakan berpola per bab: draf diperiksa dulu, baru disetujui. Cetakan aktif ikut tabel dan Buat soal."
JUDUL_BARU = "Cetakan soal baru"
JUDUL_PERIKSA = "Periksa cetakan soal"
SUBJUDUL_PERIKSA = "Pola, 10 contoh soal beserta kunci yang dihitung mesin, dan riwayat. Kunci tidak pernah ditulis tangan."

LABEL_STATUS = {store.STATUS_DRAF: "Draf", store.STATUS_AKTIF: "Aktif", store.STATUS_NONAKTIF: "Nonaktif"}
LABEL_SUMBER = {"manual": "Ditulis manual", "ai": "Draf AI"}
LABEL_AKSI = {"buat": "dibuat", "ubah": "diubah", "setujui": "disetujui", "nonaktifkan": "dinonaktifkan",
              "aktifkan": "diaktifkan kembali"}
COPY_HASIL = {
    "dibuat": "Cetakan draf tersimpan. Periksa contoh soalnya, lalu setujui bila sudah benar.",
    "tersimpan": "Perubahan draf tersimpan. Contoh soal di bawah dihitung ulang dari isi terbaru.",
    "disetujui": "Cetakan disetujui dan sekarang aktif: ikut tabel Kurikulum Merdeka dan Buat soal.",
    "dinonaktifkan": "Cetakan dinonaktifkan dan tidak lagi tampil di tabel maupun Buat soal. Riwayat tetap ada.",
    "diaktifkan": "Cetakan diaktifkan kembali.",
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_GALAT_KONFLIK = (
    "Cetakan ini sudah diubah sejak halaman dibuka. Buka ulang halaman periksa, lihat nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_GALAT_ISIAN = "Isian tidak sah. Tidak ada yang diubah."
COPY_TIDAK_SIAP = (
    "Database cetakan tidak dapat diubah atau tidak dapat dibaca di server ini. "
    "Tidak ada yang diubah. Operator perlu memeriksa berkas cetakan."
)
COPY_PETUNJUK = (
    "Tulis teks soal dengan placeholder seperti {a} atau {nama}, isi variabel beserta rentangnya, dan rumus "
    "kunci dari variabel itu (angka, variabel, + - * // % dan kurung). Syarat (misalnya a + b <= 99) "
    "membatasi nilai yang boleh keluar. Kunci selalu dihitung mesin dari rumus; pembahasan boleh memakai {kunci}."
)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah cetakan."
CONTOH_TEKS = "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?"
PLACEHOLDER = {
    "judul": "Penjumlahan dua angka dalam soal cerita", "teks": CONTOH_TEKS, "kunci": "a + b",
    "pembahasan": "{a} + {b} = {kunci}", "syarat_1": "a + b <= 99",
    "var_1_nama": "a", "var_1_min": "10", "var_1_max": "50",
    "var_2_nama": "b", "var_2_min": "1", "var_2_max": "40",
}

Token = Tuple[str, str]
Tokens = Optional[Dict[str, Token]]


def url_daftar(kelas: int, bab: int) -> str:
    return "%s?%s" % (RUTE, urlencode({"kelas": kelas, "bab": bab}))


def url_baru(kelas: int, bab: int) -> str:
    return "%s?%s" % (RUTE_BARU, urlencode({"kelas": kelas, "bab": bab}))


def url_periksa(id_cetakan: int, hasil: Optional[str] = None) -> str:
    kueri = {"id": id_cetakan}
    if hasil is not None:
        kueri["hasil"] = hasil
    return "%s?%s" % (RUTE_PERIKSA, urlencode(kueri))


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _sandi() -> str:
    # Sandi tidak pernah diisi ulang oleh server (juga saat galat); selalu kosong.
    return ('<label>Sandi admin saat ini<input type="password" name="reauth" value="" required '
            'autocomplete="current-password"></label>')


def _atribut_placeholder(nama: str) -> str:
    return ' placeholder="%s"' % e(PLACEHOLDER[nama]) if nama in PLACEHOLDER else ""


def _teks(nama: str, label: str, nilai: Dict[str, str], *, wajib: bool = True) -> str:
    return '<label>%s<input type="text" name="%s" value="%s"%s%s></label>' % (
        e(label), nama, e(nilai[nama]), _atribut_placeholder(nama), " required" if wajib else "")


def _area(nama: str, label: str, nilai: Dict[str, str], *, wajib: bool = True) -> str:
    return '<label>%s<textarea name="%s" rows="3"%s%s>%s</textarea></label>' % (
        e(label), nama, _atribut_placeholder(nama), " required" if wajib else "", e(nilai[nama]))


def _pilih_nama(nilai: Dict[str, str]) -> str:
    opsi = "".join('<option value="%s"%s>%s</option>' % (
        e(v), " selected" if nilai["nama"] == v else "", e(v)) for v in form.PILIHAN_NAMA)
    return '<label>Pakai nama anak ({nama}) di teks<select name="nama">%s</select></label>' % opsi


def _baris_variabel(no: int, nilai: Dict[str, str]) -> str:
    kolom = "".join(_teks("var_%d_%s" % (no, b), label, nilai, wajib=False)
                    for b, label in (("nama", "Variabel %d (satu huruf kecil)" % no), ("min", "Terkecil"),
                                     ("max", "Terbesar")))
    return "<li>%s</li>" % kolom


def _bidang_isi(nilai: Dict[str, str]) -> str:
    variabel = "".join(_baris_variabel(no, nilai) for no in range(1, form.BANYAK_VARIABEL + 1))
    syarat = "".join("<li>%s</li>" % _teks("syarat_%d" % no, "Syarat %d" % no, nilai, wajib=False)
                     for no in range(1, form.BANYAK_SYARAT + 1))
    return (
        _teks("judul", "Judul", nilai) + _area("teks", "Teks soal", nilai) + _pilih_nama(nilai)
        + '<ul class="kurikulum-daftar" aria-label="Variabel">%s</ul>' % variabel
        + _teks("kunci", "Rumus kunci jawaban", nilai)
        + '<ul class="kurikulum-daftar" aria-label="Syarat">%s</ul>' % syarat
        + _area("pembahasan", "Pembahasan (boleh kosong)", nilai, wajib=False))


def _form_isi(aksi_url: str, token: Token, nilai: Dict[str, str], tombol: str) -> str:
    return (
        '<form class="admin-form-bagian" method="post" action="%s">%s%s%s'
        '<button class="admin-tombol" type="submit">%s</button></form>'
        % (aksi_url, _hidden(*token), _bidang_isi(nilai), _sandi(), e(tombol)))


def _form_pindah(aksi_url: str, token: Token, catatan: str, tombol: str) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<p class="admin-meta">%s</p>%s<button class="admin-tombol" type="submit">%s</button></form>'
        % (aksi_url, _hidden(*token), e(catatan), _sandi(), e(tombol)))


def _umpan_balik(hasil: Optional[str], galat: Optional[str]) -> str:
    teks = ""
    if galat:
        teks += '<p class="admin-kartu admin-galat" role="alert">%s</p>' % e(galat)
    if hasil in COPY_HASIL:
        teks += '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])
    return teks


def _kepala_bab(kelas: int, bab: kk.Bab) -> str:
    sub = "".join("<li>%s</li>" % e(x) for x in bab.sub_materi)
    return '<h2>Kelas %d · Bab %d: %s</h2><ul>%s</ul>' % (kelas, bab.nomor, e(bab.judul), sub)


def _balik(teks: str, href: str) -> str:
    return '<p><a href="%s">&larr; %s</a></p>' % (e(href), e(teks))


def _baris_daftar(item: store.ItemCetakan) -> str:
    return (
        '<li><p class="kurikulum-kepala"><a href="%s">%s</a></p>'
        '<p class="admin-meta">%s · %s · revisi %d · diperbarui %s · <a href="%s">Periksa</a></p></li>'
        % (e(url_periksa(item.id)), e(item.cetakan.judul), e(LABEL_STATUS[item.status]),
           e(LABEL_SUMBER[item.sumber]), item.revisi, e(item.diperbarui), e(url_periksa(item.id))))


def halaman_daftar(kelas: int, bab: kk.Bab, items: Sequence[store.ItemCetakan]) -> str:
    """Daftar semua cetakan (semua status) satu bab, plus tautan buat baru."""
    daftar = ('<ul class="kurikulum-daftar" aria-label="Cetakan bab ini">%s</ul>' % "".join(
        _baris_daftar(i) for i in items)) if items else '<p class="admin-meta">Belum ada cetakan untuk bab ini.</p>'
    return (
        tab_kurikulum(TAB_KURIKULUM) + _balik("Kembali ke Kurikulum Merdeka", RUTE_KURIKULUM)
        + '<section class="admin-kartu">%s<p><a class="admin-tombol" href="%s">Buat cetakan baru</a></p></section>'
        % (_kepala_bab(kelas, bab), e(url_baru(kelas, bab.nomor)))
        + '<section class="admin-kartu"><h2>Cetakan bab ini</h2>%s</section>' % daftar)


def _bagian_baru(token: Optional[Token], nilai: Optional[Dict[str, str]]) -> str:
    if token is None:
        return '<section class="admin-kartu"><p class="admin-meta">%s</p></section>' % e(COPY_TANPA_SESI)
    return '<section class="admin-kartu"><h2>Cetakan baru</h2>%s</section>' % _form_isi(
        RUTE_BARU, token, nilai if nilai is not None else form.kosong(), "Simpan sebagai draf")


def halaman_baru(kelas: int, bab: kk.Bab, token: Optional[Token], nilai: Optional[Dict[str, str]] = None,
                 galat: Optional[str] = None) -> str:
    """Form cetakan baru; `nilai` (bila ada) = isian yang diketik sebelumnya (dipertahankan, di-escape).
    `token` None = sesi tanpa kuki (baca-saja, tanpa form)."""
    return (
        tab_kurikulum(TAB_KURIKULUM) + _balik("Kembali ke daftar cetakan bab", url_daftar(kelas, bab.nomor))
        + _umpan_balik(None, galat)
        + '<section class="admin-kartu">%s<p class="admin-meta">%s</p></section>' % (_kepala_bab(kelas, bab), e(COPY_PETUNJUK))
        + _bagian_baru(token, nilai))


def _daftar_pola(c: pola.Cetakan) -> str:
    variabel = ", ".join("%s: %d sampai %d" % v for v in c.variabel)
    syarat = "; ".join(c.syarat) or "tanpa syarat"
    return (
        '<dl class="admin-rincian"><dt>Teks soal</dt><dd>%s</dd><dt>Variabel</dt><dd>%s</dd>'
        '<dt>Nama anak</dt><dd>%s</dd><dt>Syarat</dt><dd>%s</dd><dt>Rumus kunci</dt><dd><code>%s</code></dd>'
        '<dt>Pembahasan</dt><dd>%s</dd></dl>' % (
            e(c.teks), e(variabel), "ya" if c.nama else "tidak", e(syarat), e(c.kunci), e(c.pembahasan or "-")))


def _kepala_item(item: store.ItemCetakan) -> str:
    return (
        '<section class="admin-kartu"><h2>%s</h2><p class="admin-meta">Kelas %d · Bab %d · %s · %s · revisi %d · '
        'diperbarui %s</p>%s</section>' % (
            e(item.cetakan.judul), item.kelas, item.bab, e(LABEL_STATUS[item.status]), e(LABEL_SUMBER[item.sumber]),
            item.revisi, e(item.diperbarui), _daftar_pola(item.cetakan)))


def _tampil_angka(teks: str) -> str:
    return pola.ribuan(int(teks)) if teks.isdigit() else teks


def baris_soal(soal: pola.SoalCetakan) -> str:
    """Soal cetakan satu blok: teks, kunci (titik ribuan), pembahasan; semua di-escape."""
    pembahasan = ('<p class="admin-meta">Pembahasan: %s</p>' % e(soal.pembahasan)) if soal.pembahasan else ""
    return ('<div class="kur-soal"><p>%s</p></div><p class="kur-kunci"><strong>Kunci jawaban:</strong> %s</p>%s'
            % (e(soal.teks), e(_tampil_angka(soal.kunci)), pembahasan))


def _contoh(contoh: Sequence[pola.SoalCetakan]) -> str:
    if not contoh:
        isi = '<p class="admin-meta">Tidak ada contoh soal yang bisa dibuat dari pola ini.</p>'
    else:
        isi = '<ol class="kur-soal-daftar">%s</ol>' % "".join("<li>%s</li>" % baris_soal(s) for s in contoh)
    return ('<section class="admin-kartu"><h2>%d contoh soal</h2><p class="admin-meta">Dihitung mesin dari isi '
            'tersimpan; kunci tidak ditulis tangan.</p>%s</section>' % (pola.BANYAK_CONTOH, isi))


def _kelayakan(hasil: pola.HasilKelayakan) -> str:
    if hasil.lolos:
        isi = "Lolos uji kelayakan: %d soal unik dari %d seed (minimal %d)." % (
            hasil.jumlah_unik, pola.JUMLAH_SAMPEL, pola.MIN_UNIK)
    else:
        isi = "Belum lolos uji kelayakan: %s." % "; ".join(hasil.alasan)
    return '<section class="admin-kartu"><h2>Uji kelayakan</h2><p>%s</p></section>' % e(isi)


def _entri_riwayat(r: store.RiwayatCetakan) -> str:
    perubahan = ""
    if r.aksi not in ("buat", "ubah") and r.lama and r.baru:
        perubahan = " · %s → %s" % (r.lama, r.baru)
    return '<li><p class="kurikulum-kepala">Revisi %d · %s</p><p class="admin-meta">%s · <code>%s</code>%s</p></li>' % (
        r.revisi, e(LABEL_AKSI.get(r.aksi, r.aksi)), e(r.dibuat), e(r.actor_id), e(perubahan))


def _riwayat(daftar: Sequence[store.RiwayatCetakan]) -> str:
    if not daftar:
        isi = '<p class="admin-meta">Belum ada riwayat terbaca untuk cetakan ini.</p>'
    else:
        isi = '<ul class="kurikulum-daftar" aria-label="Riwayat">%s</ul>' % "".join(_entri_riwayat(r) for r in daftar)
    return '<section class="admin-kartu"><h2>Riwayat terakhir</h2>%s</section>' % isi


def _aksi(item: store.ItemCetakan, tokens: Tokens, nilai: Optional[Dict[str, str]]) -> str:
    if tokens is None:
        return '<section class="admin-kartu"><p class="admin-meta">%s</p></section>' % e(COPY_TANPA_SESI)
    if item.status == store.STATUS_DRAF:
        awal = nilai if nilai is not None else form.dari_cetakan(item.cetakan)
        return (
            '<section class="admin-kartu"><h2>Ubah draf</h2><p class="admin-meta">%s</p>%s</section>'
            '<section class="admin-kartu"><h2>Setujui</h2>%s</section>' % (
                e(COPY_PETUNJUK), _form_isi(RUTE_UBAH, tokens[AKSI_UBAH], awal, "Simpan perubahan"),
                _form_pindah(RUTE_SETUJUI, tokens[AKSI_SETUJUI],
                             "Setuju berarti cetakan ini aktif dan ikut tabel Kurikulum Merdeka dan Buat soal. "
                             "Isi yang tersimpan diuji kelayakannya lagi saat disetujui.", "Setujui")))
    if item.status == store.STATUS_AKTIF:
        return '<section class="admin-kartu"><h2>Nonaktifkan</h2>%s</section>' % _form_pindah(
            RUTE_NONAKTIFKAN, tokens[AKSI_NONAKTIFKAN],
            "Cetakan langsung hilang dari tabel dan Buat soal. Riwayat tetap ada dan bisa diaktifkan kembali.",
            "Nonaktifkan")
    return '<section class="admin-kartu"><h2>Aktifkan kembali</h2>%s</section>' % _form_pindah(
        RUTE_AKTIFKAN, tokens[AKSI_AKTIFKAN],
        "Isi diuji kelayakannya lagi; bila lolos cetakan aktif kembali.", "Aktifkan kembali")


def halaman_periksa(item: store.ItemCetakan, *, contoh: Sequence[pola.SoalCetakan], kelayakan: pola.HasilKelayakan,
                    riwayat: Sequence[store.RiwayatCetakan], tokens: Tokens, hasil: Optional[str] = None,
                    galat: Optional[str] = None, nilai: Optional[Dict[str, str]] = None) -> str:
    """Isi halaman periksa. `tokens` None = sesi tanpa kuki (baca-saja). `nilai` = isian form edit yang
    diketik sebelumnya (dipertahankan); contoh dan uji kelayakan selalu atas isi TERSIMPAN."""
    return (
        tab_kurikulum(TAB_KURIKULUM) + _balik("Kembali ke daftar cetakan bab", url_daftar(item.kelas, item.bab))
        + _umpan_balik(hasil, galat) + _kepala_item(item) + _contoh(contoh) + _kelayakan(kelayakan)
        + _aksi(item, tokens, nilai) + _riwayat(riwayat))
