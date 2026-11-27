"""Render halaman koreksi admin atas jadwal tetap guru (3d, WP3). Murni render: tanpa I/O.

View-model disusun `admin_jadwal_tetap_http`:
- daftar: list {`guru`, `nama`, `blok_aktif` (teks kanonik atau None), `menunggu` (bool)};
- detail: {`guru`, `nama`, `pesan`, `aktif` (record atau None), `menunggu` (None atau {`usulan_id`, `blok`, `dibuat`,
  `token`: {`setuju`, `tolak`} atau None}), `riwayat` (record `dasar.riwayat`), `bisa_isi`, `token_tetapkan`}.
Tanpa id anak, order, kontak, atau id akun pengelola; id guru hanya di URL. Form native tanpa JS. Waktu tampil WIB.
"""
from __future__ import annotations

import html
from typing import Mapping, Optional, Sequence

import guru_jadwal_tetap_aturan as aturan
from pesanan_transfer_pages import waktu_wib

RUTE = "/admin/jadwal/tetap"
JUDUL = "Jadwal tetap guru"
SUBJUDUL = "Guru mengusulkan jam mengajar; admin menyetujui, menolak, atau menetapkan langsung. Tercatat atas nama admin."
COPY_BELUM_ADA = "Belum ada"
COPY_TANPA_JAM = "Tanpa jam tetap"
COPY_MENUNGGU = "Usulan menunggu"
COPY_TERSIMPAN = "Jadwal tetap tersimpan."
COPY_TIDAK_SIAP = "Jadwal tetap belum bisa dibaca di server. Coba lagi beberapa saat."
COPY_KOSONG_DAFTAR = "Belum ada guru aktif."
COPY_TIDAK_ADA_MENUNGGU = "Tidak ada usulan yang menunggu."
COPY_BACA_SAJA = "Tampilan baca-saja. Masuk melalui formulir pengelola untuk mengubah jadwal."
COPY_TIDAK_ADA_PILIHAN = "Tidak ada"
COPY_SIMPAN = "Simpan jadwal"
COPY_SETUJUI = "Setujui"
COPY_TOLAK = "Tolak"
COPY_KEMBALI = "Kembali ke daftar guru"
COPY_RIWAYAT_KOSONG = "Belum pernah ada usulan atau ketetapan."
COPY_MENUNGGU_KEPUTUSAN = "Menunggu keputusan"
JUDUL_DAFTAR = "Guru aktif"
JUDUL_AKTIF = "Jadwal aktif"
JUDUL_USULAN = "Usulan guru menunggu"
JUDUL_TETAPKAN = "Tetapkan langsung"
JUDUL_RIWAYAT = "Riwayat usulan dan putusan"
LABEL_ASAL = {"guru": "Usulan guru", "admin": "Ketetapan admin"}
LABEL_MULAI = "Mulai"
LABEL_SELESAI = "Selesai"
COPY_BLOK = "Blok"
_LABEL_PUTUSAN = {"setuju": COPY_SETUJUI, "tolak": COPY_TOLAK}


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def nama_select(hari: int, slot: str, ujung: str) -> str:
    """Nama field formulir, sama dengan `aturan.KUNCI_FORM` (dijaga tes)."""
    return f"h{hari}{slot}_{ujung}"


def ringkas_blok(blok_teks: str) -> str:
    """Teks kanonik menjadi "Senin 08.00–10.00; Rabu 15.00–17.00". Kosong = tanpa jam tetap. Teks tak sah = ValueError."""
    blok = aturan.urai_blok(blok_teks)
    if not blok:
        return COPY_TANPA_JAM
    return "; ".join(
        f"{aturan.NAMA_HARI[hari - aturan.HARI_MIN]} {aturan.label_menit(mulai)}–{aturan.label_menit(selesai)}"
        for hari, mulai, selesai in blok
    )


def _terpilih(aktif: Optional[Mapping]) -> dict:
    """Nama select -> nilai menit untuk jadwal aktif. Blok per hari diisi slot a lalu b, sesuai urutan kanonik."""
    if aktif is None:
        return {}
    hitung: dict = {}
    terpilih = {}
    for hari, mulai, selesai in aturan.urai_blok(aktif["blok"]):
        slot = aturan.SLOT_FORM[hitung.get(hari, 0)]
        hitung[hari] = hitung.get(hari, 0) + 1
        terpilih[nama_select(hari, slot, "m")] = str(mulai)
        terpilih[nama_select(hari, slot, "s")] = str(selesai)
    return terpilih


def _banner(pesan: Optional[str]) -> str:
    if not pesan:
        return ""
    return f'<p class="admin-ket" role="status">{_e(pesan)}</p>'


def _label_asal(asal: str) -> str:
    return LABEL_ASAL.get(asal, LABEL_ASAL["guru"])


def _waktu(nilai: Optional[str]) -> str:
    return waktu_wib(nilai) if nilai else ""


def tautan_guru(guru: str) -> str:
    """Jalur detail satu guru. Id guru hanya muncul di URL halaman admin."""
    return f"{RUTE}/{guru}"


# --- daftar -------------------------------------------------------------------------------------

def _baris_guru(baris: Mapping) -> str:
    ringkasan = COPY_BELUM_ADA if baris["blok_aktif"] is None else ringkas_blok(baris["blok_aktif"])
    penanda = f' <span class="admin-tanda">{_e(COPY_MENUNGGU)}</span>' if baris["menunggu"] else ""
    return (f'<li><a class="admin-tautan" href="{_e(tautan_guru(baris["guru"]))}">{_e(baris["nama"])}</a>'
            f' · {_e(ringkasan)}{penanda}</li>')


def halaman_daftar(daftar: Sequence[Mapping]) -> str:
    if not daftar:
        badan = f'<p class="admin-kosong">{_e(COPY_KOSONG_DAFTAR)}</p>'
    else:
        badan = "<ul>" + "".join(_baris_guru(baris) for baris in daftar) + "</ul>"
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_DAFTAR)}</h2>{badan}</section>'


# --- detail: kepala, aktif, dan usulan menunggu -------------------------------------------------

def _kepala(view: Mapping) -> str:
    return ('<section class="admin-kartu">'
            f'<h2>{_e(view["nama"])}</h2>'
            f'<p class="admin-meta">{_e(JUDUL)}</p>'
            f'{_banner(view["pesan"])}</section>')


def _kartu_aktif(aktif: Optional[Mapping]) -> str:
    if aktif is None:
        isi = f'<p><strong>{_e(COPY_BELUM_ADA)}</strong></p>'
    else:
        isi = (f'<p><strong>{_e(ringkas_blok(aktif["blok"]))}</strong></p>'
               f'<p class="admin-meta">{_e(_label_asal(aktif["asal"]))} · dibuat {_e(_waktu(aktif["dibuat"]))}'
               f' · diputus {_e(_waktu(aktif["diputus"]))}</p>')
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_AKTIF)}</h2>{isi}</section>'


def _form_putus(guru: str, usulan_id: int, putusan: str, token: str) -> str:
    return (f'<form method="post" action="{_e(tautan_guru(guru))}">'
            f'<input type="hidden" name="token" value="{_e(token)}">'
            f'<input type="hidden" name="aksi" value="putus">'
            f'<input type="hidden" name="usulan_id" value="{int(usulan_id)}">'
            f'<input type="hidden" name="putusan" value="{_e(putusan)}">'
            f'<button class="admin-tombol" type="submit">{_e(_LABEL_PUTUSAN[putusan])}</button></form>')


def _tombol_putus(view: Mapping) -> str:
    menunggu = view["menunggu"]
    if not view["bisa_isi"]:
        return f'<p class="admin-ket">{_e(COPY_BACA_SAJA)}</p>'
    return "".join(_form_putus(view["guru"], menunggu["usulan_id"], putusan, menunggu["token"][putusan])
                   for putusan in ("setuju", "tolak"))


def _kartu_menunggu(view: Mapping) -> str:
    menunggu = view["menunggu"]
    if menunggu is None:
        isi = f'<p class="admin-ket">{_e(COPY_TIDAK_ADA_MENUNGGU)}</p>'
    else:
        isi = (f'<p><strong>{_e(ringkas_blok(menunggu["blok"]))}</strong></p>'
               f'<p class="admin-meta">Diusulkan {_e(_waktu(menunggu["dibuat"]))}</p>'
               f'{_tombol_putus(view)}')
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_USULAN)}</h2>{isi}</section>'


# --- detail: formulir Tetapkan langsung ---------------------------------------------------------

def _select(nama: str, opsi: Sequence[int], terpilih: Optional[str]) -> str:
    kosong = " selected" if terpilih is None else ""
    baris = [f'<option value=""{kosong}>{_e(COPY_TIDAK_ADA_PILIHAN)}</option>']
    for menit in opsi:
        pilih = " selected" if str(menit) == terpilih else ""
        baris.append(f'<option value="{menit}"{pilih}>{_e(aturan.label_menit(menit))}</option>')
    return f'<select name="{nama}">' + "".join(baris) + "</select>"


def _blok_slot(hari: int, nomor: int, slot: str, terpilih: Mapping) -> str:
    mulai = nama_select(hari, slot, "m")
    selesai = nama_select(hari, slot, "s")
    return (f'<div><span>{_e(COPY_BLOK)} {nomor}</span>'
            f'<label>{_e(LABEL_MULAI)} {_select(mulai, aturan.opsi_mulai(), terpilih.get(mulai))}</label>'
            f'<label>{_e(LABEL_SELESAI)} {_select(selesai, aturan.opsi_selesai(), terpilih.get(selesai))}</label>'
            '</div>')


def _hari_tetapkan(hari: int, nama_hari: str, terpilih: Mapping) -> str:
    blok = "".join(_blok_slot(hari, nomor, slot, terpilih)
                   for nomor, slot in enumerate(aturan.SLOT_FORM, start=1))
    return f'<fieldset><legend>{_e(nama_hari)}</legend>{blok}</fieldset>'


def _kartu_tetapkan(view: Mapping) -> str:
    terpilih = _terpilih(view["aktif"])
    hari = "".join(_hari_tetapkan(nomor, nama, terpilih)
                   for nomor, nama in enumerate(aturan.NAMA_HARI, start=aturan.HARI_MIN))
    form = (f'<form method="post" action="{_e(tautan_guru(view["guru"]))}">'
            f'<input type="hidden" name="token" value="{_e(view["token_tetapkan"])}">'
            f'<input type="hidden" name="aksi" value="tetapkan">'
            f'{hari}<button class="admin-tombol" type="submit">{_e(COPY_SIMPAN)}</button></form>')
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_TETAPKAN)}</h2>{form}</section>'


def _kartu_tetapkan_atau_baca_saja(view: Mapping) -> str:
    if not view["bisa_isi"]:
        return f'<section class="admin-kartu"><p class="admin-ket">{_e(COPY_BACA_SAJA)}</p></section>'
    return _kartu_tetapkan(view)


# --- detail: riwayat ----------------------------------------------------------------------------

def _label_putusan(entri: Mapping) -> str:
    if entri["putusan"] is None:
        return COPY_MENUNGGU_KEPUTUSAN
    if entri["putusan"] == "tolak":
        return f'Ditolak · {_waktu(entri["diputus"])}'
    judul = "Ditetapkan langsung" if entri["asal"] == "admin" else "Disetujui"
    return f'{judul} · {_waktu(entri["diputus"])}'


def _entri_riwayat(entri: Mapping) -> str:
    return (f'<li><p><strong>{_e(_label_asal(entri["asal"]))}</strong> · {_e(ringkas_blok(entri["blok"]))}</p>'
            f'<p class="admin-meta">Diusulkan {_e(_waktu(entri["dibuat"]))}</p>'
            f'<p>{_e(_label_putusan(entri))}</p></li>')


def _kartu_riwayat(riwayat: Sequence[Mapping]) -> str:
    if not riwayat:
        badan = f'<p class="admin-kosong">{_e(COPY_RIWAYAT_KOSONG)}</p>'
    else:
        badan = "<ol>" + "".join(_entri_riwayat(entri) for entri in riwayat) + "</ol>"
    return f'<section class="admin-kartu"><h2>{_e(JUDUL_RIWAYAT)}</h2>{badan}</section>'


def halaman_detail(view: Mapping) -> str:
    """Isi halaman detail (tanpa shell admin): kepala, jadwal aktif, usulan menunggu, formulir, riwayat."""
    return "".join([
        _kepala(view),
        _kartu_aktif(view["aktif"]),
        _kartu_menunggu(view),
        _kartu_tetapkan_atau_baca_saja(view),
        _kartu_riwayat(view["riwayat"]),
        f'<p><a class="admin-tautan" href="{_e(RUTE)}">{_e(COPY_KEMBALI)}</a></p>',
    ])


def halaman_tidak_siap() -> str:
    return f'<section class="admin-kartu"><h2>{_e(JUDUL)}</h2><p>{_e(COPY_TIDAK_SIAP)}</p></section>'
