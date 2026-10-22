"""Beranda guru (/guru): ringkasan satu kalimat, chip langkah, kartu anak beraksi.

Semua kelompok, urutan, dan label langkah berasal dari ``teacher_home_priority``
(proyeksi reducer yang sama dengan profil anak). Chip dan pencarian adalah GET
server-side tanpa JS; hitungan chip dihitung dari anak milik guru ini saja,
sebelum pencarian atau chip diterapkan.
"""
from __future__ import annotations

import html
from urllib.parse import urlencode

import database
import domain_clock
import teacher_home_priority as prioritas
from cycle_report import TINDAKAN
from teacher_shell import _halaman_stitch
from teacher_workspace import _kelas_sekolah_profil

# Pencarian baru berguna setelah daftar cukup panjang; tebakan, bukan data.
AMBANG_PENCARIAN = 5
JUMLAH_WARNA_AVATAR = 4
KETERANGAN_DAFTAR = (
    "Setiap anak punya halaman sendiri: buat latihan, rencana belajar, "
    "dan riwayat."
)

_NADA_PIL = {
    prioritas.PERLU_TINDAKAN: "perhatian",
    prioritas.SIAP: "baik",
    prioritas.MENUNGGU: "netral",
}
_URUT_CHIP = ("semua", "perlu-tindakan", "siap", "menunggu")
_KELOMPOK_CHIP = {
    "perlu-tindakan": prioritas.PERLU_TINDAKAN,
    "siap": prioritas.SIAP,
    "menunggu": prioritas.MENUNGGU,
}

_CTA = {
    "konfirmasi_hasil": "Tinjau hasil",
    "lanjutkan_sesi": "Lanjutkan latihan",
    "pemetaan": "Lanjutkan latihan",
    "pilih_variasi": "Siapkan latihan",
}
CTA_BAWAAN = "Lihat rencana"
CTA_TIDAK_TERBACA = "Buka profil"


def _cta(langkah) -> str:
    """Label tombol sesuai langkah; anak baru memakai label 'siapkan', bukan 'lanjutkan'."""
    if langkah.tindakan is None:
        return CTA_TIDAK_TERBACA
    if langkah.tindakan == "pemetaan" and langkah.label == TINDAKAN["pilih_variasi"]:
        return _CTA["pilih_variasi"]
    return _CTA.get(langkah.tindakan, CTA_BAWAAN)


def _tautan(kelompok: str, cari: str) -> str:
    """URL /guru yang mempertahankan hanya parameter yang bukan bawaan."""
    parameter = {}
    if kelompok != "semua":
        parameter["kelompok"] = kelompok
    if cari:
        parameter["cari"] = cari
    return "/guru" + ("?" + urlencode(parameter) if parameter else "")


def _ringkasan(jumlah: dict[int, int], total: int) -> str:
    """Satu kalimat posisi kelompok; tidak mengklaim hasil siap ditinjau."""
    if not total:
        return "Temani prosesnya, bukan hanya hasilnya."
    bagian = []
    if jumlah[prioritas.PERLU_TINDAKAN]:
        bagian.append(f"{jumlah[prioritas.PERLU_TINDAKAN]} anak perlu tindakan Anda.")
    if jumlah[prioritas.SIAP]:
        bagian.append(f"{jumlah[prioritas.SIAP]} anak siap dilanjutkan.")
    return " ".join(bagian) or "Semua anak sedang menunggu langkah berikutnya."


def _chip_filter(jumlah: dict[int, int], total: int, kelompok: str, cari: str) -> str:
    hitung = {"semua": total}
    hitung.update({k: jumlah[v] for k, v in _KELOMPOK_CHIP.items()})
    chip = []
    for nilai in _URUT_CHIP:
        aktif = ' aria-current="true"' if nilai == kelompok else ""
        chip.append(
            f'<a class="guru-chip-st" href="{html.escape(_tautan(nilai, cari), quote=True)}"{aktif}>'
            f'{html.escape(prioritas.PILIHAN_FILTER[nilai])} <strong>{hitung[nilai]}</strong></a>'
        )
    return (
        '<nav class="guru-chip-baris-st" aria-label="Saring menurut langkah">'
        + "".join(chip) + "</nav>"
    )


def _form_cari(kelompok: str, cari: str) -> str:
    """Muncul hanya untuk daftar panjang atau bila pencarian sedang aktif."""
    hidden = (
        f'<input type="hidden" name="kelompok" value="{html.escape(kelompok, quote=True)}">'
        if kelompok != "semua" else ""
    )
    hapus = (
        f'<a id="guru-hapus-filter" href="{html.escape(_tautan(kelompok, ""), quote=True)}">'
        "Hapus pencarian</a>" if cari else ""
    )
    return (
        '<form id="guru-filter" class="guru-cari-st" method="get" action="/guru" role="search">'
        '<div><label for="guru-cari">Cari nama anak</label>'
        '<input id="guru-cari" name="cari" type="search" maxlength="100" '
        f'autocomplete="off" value="{html.escape(cari, quote=True)}"></div>'
        f'{hidden}<button type="submit">Cari</button>{hapus}</form>'
    )


def _status(kon, siswa_id: int, langkah) -> tuple[str, str, str]:
    """(baris catatan, label dibatalkan, jumlah latihan) dari rekap sesi anak ini."""
    rekap = kon.execute(
        """SELECT COUNT(*) AS jumlah,
                  SUM(CASE WHEN dibatalkan IS NOT NULL THEN 1 ELSE 0 END) AS dibatalkan,
                  SUM(CASE WHEN dibatalkan IS NULL
                      AND selesai IS NOT NULL AND direview IS NULL
                      THEN 1 ELSE 0 END) AS belum_review,
                  SUM(CASE WHEN dibatalkan IS NULL AND selesai IS NULL
                      THEN 1 ELSE 0 END) AS belum_kirim
           FROM sesi WHERE siswa_id = ?""",
        (siswa_id,),
    ).fetchone()
    jumlah_sesi = rekap["jumlah"] or 0
    dibatalkan = rekap["dibatalkan"] or 0
    belum_review = rekap["belum_review"] or 0
    belum_kirim = rekap["belum_kirim"] or 0
    status = []
    if belum_review:
        status.append(f'<span class="guru-status-st periksa">{belum_review} menunggu diperiksa</span>')
    if belum_kirim:
        status.append(f'<span class="guru-status-st">{belum_kirim} belum dikirim</span>')
    if not status:
        if jumlah_sesi == 0:
            ringkasan = "Belum ada sesi"
        elif jumlah_sesi == dibatalkan:
            ringkasan = "Tidak ada latihan yang perlu dikerjakan."
        elif langkah.tindakan == "konfirmasi_hasil":
            # Dibuka bukan dikonfirmasi: jangan tampak selesai; kalimat berupa tindakan.
            ringkasan = "Hasil menunggu Anda tinjau"
        else:
            ringkasan = "semua direview"
        status.append(f'<span class="guru-status-st">{ringkasan}</span>')
    label_batal = f"<span>{dibatalkan} dibatalkan</span>" if dibatalkan else ""
    return "".join(status), label_batal, f"<span>{jumlah_sesi} latihan tercatat</span>"


def _kartu(kon, siswa, langkah, hari_ini, peran: str) -> str:
    from learning_profile import label_kelas_sekolah
    siswa_id, nama = int(siswa["id"]), str(siswa["nama"])
    catatan, label_batal, label_jumlah = _status(kon, siswa_id, langkah)
    keluarga = (
        f'<span>keluarga: {html.escape(siswa["pemilik"] or "warisan")}</span>'
        if peran == "admin" else ""
    )
    hari = prioritas.hari_menunggu(langkah, hari_ini)
    tunggu = (
        f'<span class="guru-tunggu-st">Menunggu {hari} hari</span>'
        if hari is not None and hari >= 1 else ""
    )
    perlu = langkah.kelompok == prioritas.PERLU_TINDAKAN
    kelas_kartu = "guru-kartu-st guru-kartu-perhatian-st" if perlu else "guru-kartu-st"
    kelas_cta = "guru-cta-st guru-cta-utama-st" if perlu else "guru-cta-st"
    cta = _cta(langkah)
    kelas = label_kelas_sekolah(_kelas_sekolah_profil(kon, siswa))
    return (
        f'<article class="{kelas_kartu}">'
        f'<span class="guru-inisial-st guru-avatar-{siswa_id % JUMLAH_WARNA_AVATAR}" aria-hidden="true">'
        f'{html.escape(nama[:1].upper())}</span>'
        '<div class="guru-identitas-st">'
        '<div class="guru-judul-kartu-st">'
        f'<h3 class="guru-nama-st">{html.escape(nama)}</h3>'
        f'<span class="guru-kelas-st">{html.escape(kelas)}</span>'
        f'<span class="guru-pil-st guru-pil-{_NADA_PIL[langkah.kelompok]}-st">'
        f'{html.escape(prioritas.JUDUL_KELOMPOK[langkah.kelompok])}</span></div>'
        '<p class="guru-alis-st">LANGKAH BERIKUTNYA</p>'
        f'<strong class="guru-langkah-st">{html.escape(langkah.label)}</strong>'
        f'<div class="guru-status-daftar-st">{catatan}{tunggu}</div>'
        f'<div class="guru-meta-st">{label_jumlah}{label_batal}{keluarga}</div></div>'
        f'<a class="{kelas_cta}" href="/anak/{siswa_id}" '
        f'aria-label="{html.escape(cta + ": " + nama, quote=True)}">'
        f'{html.escape(cta)} <span aria-hidden="true">→</span></a>'
        '</article>'
    )


def _daftar(kon, baris, hari_ini, peran: str) -> str:
    per_anak = {langkah.siswa_id: (siswa, langkah) for siswa, langkah in baris}
    urut = prioritas.urutkan([langkah for _, langkah in baris])
    kartu = [_kartu(kon, *per_anak[a.siswa_id], hari_ini, peran) for a in urut]
    return f'<div class="daftar-anak">{"".join(kartu)}</div>'


def _tambah_anak(total: int) -> str:
    return (
        '<a class="guru-tambah-st" href="/akun?section=siswa">'
        '<span aria-hidden="true">＋</span> '
        + ("Tambah anak" if total else "Tambahkan anak pertama") + "</a>"
    )


def _isi_daftar(kon, baris_semua, jumlah, cari, kelompok, hari_ini, peran) -> str:
    """Bagian daftar anak: chip, pencarian bersyarat, hitungan, dan kartu."""
    total = len(baris_semua)
    tampil = []
    for s, langkah in baris_semua:
        nama_akun = None
        if cari:
            # Lookup existing hanya untuk siswa yang sudah lolos scope pemilik.
            from students import akun_murid_dari_siswa
            nama_akun = akun_murid_dari_siswa(kon, int(s["id"]))
        if prioritas.cocok_filter(langkah, cari, kelompok, nama_akun):
            tampil.append((s, langkah))
    if tampil:
        isi = _daftar(kon, tampil, hari_ini, peran)
    else:
        isi = (
            '<div class="guru-cocok-kosong-st">'
            "<strong>Tidak ada siswa yang cocok.</strong>"
            "<p>Ubah pencarian atau pilih kelompok lain.</p>"
            '<a class="guru-tambah-st" href="/guru">Tampilkan semua</a></div>'
        )
    form = _form_cari(kelompok, cari) if total > AMBANG_PENCARIAN or cari else ""
    return (
        '<div class="guru-kepala-daftar-st"><div>'
        '<h2 id="daftar-anak">Anak &amp; siswa</h2>'
        f'<p class="guru-petunjuk-st">{html.escape(KETERANGAN_DAFTAR)}</p>'
        f'</div>{_tambah_anak(total)}</div>'
        + _chip_filter(jumlah, total, kelompok, cari) + form
        + f'<p class="guru-hasil-filter-st" role="status">{len(tampil)} dari {total} siswa ditampilkan.</p>'
        + isi
    )


def _isi_kosong(total: int) -> str:
    return (
        '<div class="guru-kosong-st">'
        '<p class="guru-alis-st">MULAI DARI SINI</p>'
        '<h2 id="daftar-anak">Kenali langkah pertama mereka.</h2>'
        "<p>Akunmu sudah siap. Tambahkan anak dengan nama panggilan, "
        "lalu buka profilnya untuk mulai mendampingi belajar.</p>"
        f'{_tambah_anak(total)}<p class="guru-petunjuk-st">Belum ada latihan. '
        "Langkah berikutnya akan tersedia di profil anak.</p></div>"
    )


def halaman(kon, pesan: str, pemilik, peran: str, cari: str, kelompok: str) -> bytes:
    cari, kelompok = prioritas.normalkan_filter(cari, kelompok)
    siswa_milik = database.daftar_siswa(kon, pemilik)
    total = len(siswa_milik)
    hari_ini = domain_clock.hari_wib()
    baris_semua = [(s, prioritas.langkah_anak(kon, s)) for s in siswa_milik]
    jumlah = prioritas.hitung_kelompok(langkah for _, langkah in baris_semua)
    isi_utama = (
        _isi_daftar(kon, baris_semua, jumlah, cari, kelompok, hari_ini, peran)
        if total else _isi_kosong(total)
    )
    kabar = (
        '<div class="st-banner-sukses" role="status"><span class="ikon" aria-hidden="true">✓</span>'
        f'<span>{html.escape(pesan)}</span></div>' if pesan else ""
    )
    return _halaman_stitch(
        "Ruang guru",
        '<main aria-labelledby="judul-guru">'
        '<header class="guru-sapaan-st"><div>'
        '<p class="guru-alis-st">RUANG GURU</p>'
        '<h1 id="judul-guru">Langkah kecil,<br><span>tumbuh bersama.</span></h1>'
        f'<p>{html.escape(_ringkasan(jumlah, total))}</p></div>'
        '<div class="guru-catatan-st" aria-hidden="true">'
        '<img src="/aset/maskot-membaca-v3-240.png" width="96" height="96" alt="">'
        '<span>Satu langkah yang berarti.</span></div></header>'
        f'{kabar}<section aria-labelledby="daftar-anak">{isi_utama}</section>'
        '<footer class="guru-kaki-st"><span aria-hidden="true">✳</span> '
        'Beri ruang untuk mencoba, bertanya, dan menjelaskan.</footer></main>',
        ident=(pemilik if pemilik else "guru", peran),
        kelas_bungkus="guru-beranda-st",
    )
