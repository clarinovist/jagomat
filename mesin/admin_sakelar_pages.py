"""Renderer murni halaman admin sakelar fitur (tanpa I/O, tanpa JS baru).

Tiap sakelar satu kartu: label, status Aktif/Mati yang menonjol, dampak, dan satu tindakan. Sumber nilai dan
revisi disimpan di detail kecil. Tindakan (form sandi) terlipat di <details> sehingga kolom sandi baru tampil
setelah diklik; mematikan fitur yang sedang aktif memakai gaya peringatan dan konfirmasi (atribut
`data-konfirmasi`, skrip konfirmasi admin yang sudah ada) yang menyebut akibatnya. Form hanya membawa csrf,
tinjauan, dan sandi ulang; nama, target, dan revisi hidup di tinjauan bertanda tangan, bukan di field.
Prasyarat yang belum terpenuhi hanya ditampilkan di sini sebagai kenyamanan; penegakannya di server.
Semua nilai dinamis di-escape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from admin_komponen import badge_aktif, e, lipat_aksi
from admin_rekening_pages import KEADAAN_KOSONG, KEADAAN_TERISI, RUTE_REKENING
from feature_switch import Sakelar
import sakelar_registry

RUTE = "/admin/sakelar"
JUDUL = "Pengaturan layanan"
SUBJUDUL = "Nyalakan atau matikan fitur tanpa deploy. Nilai yang diatur di sini menang atas nilai bawaan server."
AKSI_UBAH = "ubah_sakelar"
FUNNEL = "FUNNEL_AKTIF"
TRANSFER = "PESANAN_TRANSFER_AKTIF"

COPY_HASIL = {
    "tersimpan": "Pengaturan tersimpan. Perubahan berlaku dalam beberapa detik.",
    "pendaftaran_tersimpan": "Pengaturan pendaftaran mandiri tersimpan.",
}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah pengaturan."
COPY_CATATAN = (
    "Saat Anda pertama kali mengubah salah satu fitur, nilai bawaan server untuk semua fitur di halaman ini "
    "disimpan lebih dulu. Sesudah itu pengaturan di halaman ini yang berlaku, dan mengubah nilai bawaan server "
    "tidak lagi berpengaruh."
)
COPY_TIDAK_SIAP = (
    "Database sakelar tidak dapat dibaca atau skemanya tidak dikenal di server ini. Tidak ada yang diubah. "
    "Operator perlu memeriksa berkas sakelar sebelum sakelar bisa dilihat atau diubah."
)
COPY_GALAT_KONFLIK = (
    "Sakelar sudah diubah sejak halaman ini dibuka. Buka ulang halaman sakelar, periksa nilai terbaru, "
    "lalu coba lagi. Tidak ada yang diubah."
)
COPY_GALAT_ISIAN = "Permintaan ubah sakelar tidak sah. Tidak ada yang diubah."
COPY_PRASYARAT = "Sakelar belum bisa dinyalakan karena prasyarat belum terpenuhi. Tidak ada yang diubah."
COPY_BELUM_FUNNEL = "Cek Kemampuan dan Paket Coba harus dibuka lebih dulu."
COPY_BELUM_REKENING = "Rekening transfer harus diisi dulu di halaman Rekening transfer (atau belum bisa diperiksa)."
COPY_KONFIRMASI_MATI = "Matikan %s? %s"
LABEL_SUMBER = {
    "db": "diatur admin di halaman ini",
    "env": "nilai bawaan server, belum pernah diubah di sini",
}
LABEL_KELOMPOK = {
    sakelar_registry.KELOMPOK_PENJUALAN: "Penjualan dan pembayaran",
    sakelar_registry.KELOMPOK_BELAJAR: "Fitur belajar",
}

Token = Tuple[str, str]


@dataclass(frozen=True)
class BagianSakelar:
    """Hasil render bagian sakelar: kartu per kelompok (urutan registri) agar halaman induk bisa menyisipkan
    kartu lain (pembayaran QRIS, rekening) tanpa membongkar markup."""

    penjualan: Mapping[str, str]
    belajar: Mapping[str, str]
    status: Tuple[Tuple[str, str, bool], ...]  # (nama, label, aktif) untuk ringkasan
    umpan_balik: str = ""
    catatan: str = ""
    catatan_teknis: str = ""


def id_kartu(nama: str) -> str:
    """Id jangkar kartu satu sakelar, mis. s-funnel_aktif."""
    return "s-" + nama.lower()


def badge_status(aktif: bool, *, teks_aktif: str = "Aktif", teks_mati: str = "Mati") -> str:
    """Penanda status besar: hijau untuk aktif, netral untuk mati."""
    return badge_aktif(aktif, teks_aktif, teks_mati)


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _form(sakelar: Sakelar, token: Token) -> str:
    info = sakelar_registry.info(sakelar.nama)
    if sakelar.aktif:
        teks, kelas_tombol = "Matikan", "admin-tombol admin-bahaya"
        konfirmasi = ' data-konfirmasi="%s"' % e(COPY_KONFIRMASI_MATI % (info.label, info.akibat_mati))
        ringkasan, kelas_ringkasan = "Matikan fitur ini…", "admin-tombol admin-bahaya-garis"
    else:
        teks, kelas_tombol, konfirmasi = "Nyalakan", "admin-tombol", ""
        ringkasan, kelas_ringkasan = "Nyalakan fitur ini…", "admin-tombol"
    form = (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s"%s>%s'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="%s" type="submit">%s</button></form>'
        % (RUTE, konfirmasi, _hidden(*token), kelas_tombol, teks))
    akibat = '<p class="admin-meta">%s</p>' % e(info.akibat_mati) if sakelar.aktif else ""
    return lipat_aksi(ringkasan, kelas_ringkasan, akibat + form)


def _tombol_terkunci() -> str:
    return '<button class="admin-tombol" type="button" disabled>Nyalakan fitur ini</button>'


def _tautan_prasyarat(teks: str) -> str:
    if teks != COPY_BELUM_REKENING:
        return ""
    return ' <a class="admin-tautan-teks" href="%s">Buka halaman rekening</a>' % RUTE_REKENING


def _prasyarat(belum: Sequence[str]) -> str:
    daftar = "".join("<li>%s%s</li>" % (e(teks), _tautan_prasyarat(teks)) for teks in belum)
    return '<p class="admin-meta">Belum bisa dinyalakan karena:</p><ul class="admin-meta">%s</ul>' % daftar


def _tindakan(sakelar: Sakelar, tokens: Optional[Mapping[str, Token]], belum: Sequence[str]) -> str:
    if tokens is None:
        return ""
    if sakelar.nama in tokens:
        return _form(sakelar, tokens[sakelar.nama])
    return _tombol_terkunci() + (_prasyarat(belum) if belum else "")


def _detail_teknis(sakelar: Sakelar) -> str:
    return ('<details class="admin-detail-teknis"><summary>Detail teknis</summary>'
            '<p class="admin-meta">Nilai ini %s. Revisi %d.</p></details>'
            % (e(LABEL_SUMBER.get(sakelar.sumber, sakelar.sumber)), sakelar.revisi))


def _kartu(sakelar: Sakelar, tokens: Optional[Mapping[str, Token]], prasyarat: Mapping[str, Sequence[str]]) -> str:
    info = sakelar_registry.info(sakelar.nama)
    belum = () if sakelar.aktif else tuple(prasyarat.get(sakelar.nama, ()))
    return (
        '<section class="admin-kartu admin-kartu-fitur" id="%s">'
        '<div class="admin-fitur-kepala"><h3>%s</h3>%s</div>'
        '<p>%s</p>%s%s</section>'
        % (id_kartu(sakelar.nama), e(info.label), badge_status(sakelar.aktif), e(info.dampak),
           _tindakan(sakelar, tokens, belum), _detail_teknis(sakelar)))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _catatan_teknis() -> str:
    return ('<details class="admin-detail-teknis admin-catatan-teknis"><summary>Cara kerja pengaturan ini</summary>'
            '<p class="admin-meta">%s</p></details>' % e(COPY_CATATAN))


def bagian(daftar: Sequence[Sakelar], tokens: Optional[Mapping[str, Token]], *,
           prasyarat: Optional[Mapping[str, Sequence[str]]] = None, hasil: Optional[str] = None) -> BagianSakelar:
    """Bagian sakelar. `tokens` = {nama: (csrf, tinjauan)} untuk baris yang boleh diubah, atau None
    (baca-saja, tanpa form); baris tanpa token memakai tombol nonaktif dan menampilkan `prasyarat`."""
    sisa = {} if prasyarat is None else prasyarat
    kartu = {s.nama: _kartu(s, tokens, sisa) for s in daftar}

    def kelompok(kode: str) -> Mapping[str, str]:
        return {nama: kartu[nama] for nama in sakelar_registry.nama_kelompok(kode) if nama in kartu}

    return BagianSakelar(
        penjualan=kelompok(sakelar_registry.KELOMPOK_PENJUALAN),
        belajar=kelompok(sakelar_registry.KELOMPOK_BELAJAR),
        status=tuple((s.nama, sakelar_registry.info(s.nama).label, s.aktif) for s in daftar),
        umpan_balik=_umpan_balik(hasil),
        catatan='<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI) if tokens is None else "",
        catatan_teknis=_catatan_teknis() if tokens is not None else "")


def _langkah(teks: str, selesai: Optional[bool], keterangan: str) -> str:
    kelas, badge = {
        True: ("selesai", '<span class="admin-badge bien">Selesai</span>'),
        False: ("belum", '<span class="admin-badge perhatian">Belum</span>'),
        None: ("tak-tahu", '<span class="admin-badge">Belum bisa diperiksa</span>'),
    }[selesai]
    return ('<li class="admin-langkah-item %s"><div class="admin-langkah-isi"><strong>%s</strong>'
            '<span class="admin-meta">%s</span></div>%s</li>' % (kelas, e(teks), keterangan, badge))


def _langkah_rekening(rekening: Optional[str]) -> str:
    if rekening == KEADAAN_TERISI:
        return _langkah("Isi rekening tujuan transfer", True,
                        'Rekening sudah terisi. <a class="admin-tautan-teks" href="%s">Lihat atau ubah rekening</a>.'
                        % RUTE_REKENING)
    if rekening == KEADAAN_KOSONG:
        return _langkah("Isi rekening tujuan transfer", False,
                        'Rekening belum diisi. <a class="admin-tautan-teks" href="%s">Isi di halaman rekening</a>.'
                        % RUTE_REKENING)
    if rekening is None:
        return _langkah("Isi rekening tujuan transfer", None, "Status rekening belum bisa dibaca di server ini.")
    return _langkah("Isi rekening tujuan transfer", False,
                    "Skema rekening belum dipasang operator, jadi rekening belum bisa diisi.")


def _langkah_qris(qris_tutup: Optional[bool]) -> str:
    awal = "Tutup pembayaran QRIS"
    if qris_tutup:
        return _langkah(awal, True, "QRIS sudah tertutup.")
    if qris_tutup is None:
        return _langkah(awal, None, "Status QRIS belum bisa dibaca di server ini.")
    return _langkah(awal, False, 'QRIS masih terbuka. Pilih Tutup di kartu '
                                 '<a class="admin-tautan-teks" href="#pembayaran">Pembayaran QRIS</a>.')


def _langkah_transfer(transfer_aktif: bool) -> str:
    return _langkah("Nyalakan pembayaran transfer rekening", transfer_aktif,
                    ('Sudah menyala.' if transfer_aktif else
                     'Belum menyala. Gunakan tombol Nyalakan di kartu '
                     '<a class="admin-tautan-teks" href="#%s">Pembayaran transfer rekening</a>.' % id_kartu(TRANSFER)))


def checklist_transfer(*, rekening: Optional[str], qris_tutup: Optional[bool], transfer_aktif: bool) -> str:
    """Langkah bernomor membuka transfer; status tiap langkah dari data server (bukan tebakan halaman).

    `rekening` = keadaan rekening (KEADAAN_*) atau None bila tak terbaca; `qris_tutup` = None bila tahap QRIS
    tak terbaca."""
    langkah = (_langkah_rekening(rekening), _langkah_qris(qris_tutup), _langkah_transfer(transfer_aktif))
    return ('<section class="admin-kartu admin-checklist" id="buka-transfer"><h3>Cara membuka transfer rekening</h3>'
            '<p class="admin-meta">Kerjakan berurutan. QRIS ditutup dulu supaya satu pesanan tidak terbayar dua kali.</p>'
            '<ol class="admin-langkah">%s</ol></section>' % "".join(langkah))


def halaman_galat() -> str:
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>'
            % e(COPY_TIDAK_SIAP))


COPY_PENDAFTARAN_GALAT = (
    "Pengaturan pendaftaran mandiri belum bisa dibaca di server ini. Tidak ada yang diubah. "
    "Operator perlu memeriksa penyimpanan admin."
)


def halaman_pendaftaran_galat() -> str:
    return ('<section class="admin-kartu admin-galat" id="pendaftaran" role="alert"><h2>Pendaftaran mandiri: belum siap</h2>'
            '<p>%s</p></section>' % e(COPY_PENDAFTARAN_GALAT))


def halaman_pendaftaran_baca(dibuka: bool) -> str:
    """Sesi tanpa kuki (baca-saja): status saja, tanpa form."""
    return ('<section class="admin-kartu" id="pendaftaran"><div class="admin-fitur-kepala">'
            '<h2>Pendaftaran mandiri: %s</h2>%s</div>'
            '<p class="admin-meta">%s</p></section>'
            % ("dibuka" if dibuka else "ditutup",
               badge_status(dibuka, teks_aktif="Dibuka", teks_mati="Ditutup"), e(COPY_TANPA_SESI)))
