"""Halaman guru/admin untuk Latihan Lomba satu anak: progress, riwayat, dan detail sesi (hanya-lihat, tanpa skrip).

Menampilkan kunci, pembahasan, dan label `kesalahan` pengecoh (dugaan), jadi hanya dipakai rute guru yang
sudah menegakkan kepemilikan (`contest_guru_http`). Kartu soal dibagi dengan halaman anak lewat
`contest_results_pages.kartu_soal(untuk_guru=True)`. Semua teks dari DB di-escape.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

import contest_assignment_store as AS
import contest_chart_svg as G
import contest_pages as P
import contest_paket as PK
import contest_results as R
import contest_results_pages as RP
import contest_store as K
from contest_format import desimal, durasi_menit_detik, persen, tanggal_wib
from contest_style import GAYA_HASIL, GAYA_PENGATURAN
from teacher_shell import _halaman as _bingkai

BATAS_TITIK_GRAFIK = 30
SKALA_PERSEN = 100
BATAS_BARIS_RIWAYAT = 50
MIN_TOPIK_BANDING = 2
_LABEL_STATUS = {K.DIKUMPUL: "Selesai", K.WAKTU_HABIS: "Waktu habis"}
LABEL_CEPAT = "Dikumpulkan cepat"
CATATAN_GRAFIK_REDUP = "Titik abu-abu = dikumpulkan cepat, tidak dihitung di rata-rata."
_LABEL_TOPIK_PENDEK = {"bilangan": "Bil", "operasi": "Operasi", "pengukuran": "Ukur", "bangun": "Bangun"}
PESAN_TERSIMPAN = "Pengaturan Mode Lomba tersimpan."
GALAT_DURASI = (f"Waktu harus angka bulat {PK.DURASI_MIN_MENIT} sampai {PK.DURASI_MAKS_MENIT} menit, atau dikosongkan "
                "untuk memakai waktu bawaan. Pengaturan belum disimpan.")
CATATAN_DURASI = (f"Kosongkan untuk memakai waktu bawaan. Boleh {PK.DURASI_MIN_MENIT} sampai {PK.DURASI_MAKS_MENIT} "
                  "menit. Perubahan berlaku untuk sesi berikutnya, bukan sesi yang sedang berjalan.")
NAMA_ISIAN_DURASI = {PK.MODE_LATIHAN: "durasi_latihan", PK.MODE_SIMULASI: "durasi_simulasi"}
PILIHAN_TARGET = (0, 1, 2, 3)       # target harian yang boleh dipilih Guru; "ikut paket" disimpan sebagai NULL
NILAI_IKUT_PAKET = "paket"
CATATAN_DUGAAN = ("Label kesalahan adalah dugaan dari pilihan jawaban yang dipilih anak, bukan diagnosis; "
                  "pakai sebagai bahan bertanya, bukan kesimpulan.")


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def alamat_progres(siswa_id: int) -> str:
    return f"/anak/{int(siswa_id)}/lomba"


def alamat_detail(siswa_id: int, sesi_id: int) -> str:
    return f"{alamat_progres(siswa_id)}/{int(sesi_id)}"


def alamat_pengaturan(siswa_id: int) -> str:
    return f"{alamat_progres(siswa_id)}/pengaturan"


def _opsi(nilai: str, label: str, terpilih: bool) -> str:
    pilih = " selected" if terpilih else ""
    return f'<option value="{_e(nilai)}"{pilih}>{_e(label)}</option>'


def _pilihan_target(penugasan: Optional[AS.Penugasan]) -> str:
    dipilih = None if penugasan is None else penugasan.target_harian
    angka = PILIHAN_TARGET if dipilih is None or dipilih in PILIHAN_TARGET else PILIHAN_TARGET + (dipilih,)
    opsi = [_opsi(NILAI_IKUT_PAKET, f"Ikut paket ({PK.PAKET_AKTIF.target_harian})", dipilih is None)]
    opsi.extend(_opsi(str(n), "Tanpa target" if n == 0 else f"{n} latihan per hari", n == dipilih) for n in angka)
    return "".join(opsi)


def _hitung_mundur_tampil(penugasan: Optional[AS.Penugasan]) -> bool:
    if penugasan is None or penugasan.tampil_hitung_mundur is None:
        return PK.PAKET_AKTIF.tampil_hitung_mundur
    return penugasan.tampil_hitung_mundur


def _durasi_tersimpan(penugasan: Optional[AS.Penugasan], mode: str) -> Optional[int]:
    if penugasan is None:
        return None
    return penugasan.durasi_latihan_detik if mode == PK.MODE_LATIHAN else penugasan.durasi_simulasi_detik


def _isian_durasi(penugasan: Optional[AS.Penugasan], mode: str) -> str:
    """Isian menit satu mode; kosong = bawaan paket (placeholder menunjukkan angka bawaan)."""
    bawaan = PK.PAKET_AKTIF.format_mode(mode)
    detik = _durasi_tersimpan(penugasan, mode)
    nilai = "" if detik is None else str(detik // PK.DETIK_PER_MENIT)
    return (f'<label class="hl-isian">Waktu {_e(bawaan.label)} ({bawaan.jumlah_soal} soal), menit'
            f'<input type="number" name="{NAMA_ISIAN_DURASI[mode]}" min="{PK.DURASI_MIN_MENIT}" '
            f'max="{PK.DURASI_MAKS_MENIT}" step="1" inputmode="numeric" value="{nilai}" '
            f'placeholder="{bawaan.durasi_menit}"></label>')


def menit_anak(penugasan: Optional[AS.Penugasan], mode: str) -> int:
    """Menit yang berlaku untuk anak: durasi Guru bila diisi, selain itu bawaan paket."""
    detik = _durasi_tersimpan(penugasan, mode)
    return (PK.PAKET_AKTIF.format_mode(mode).durasi_detik if detik is None else detik) // PK.DETIK_PER_MENIT


def kartu_pengaturan(siswa, penugasan: Optional[AS.Penugasan], tersimpan: bool = False, galat: str = "") -> str:
    """Kartu "Mode Lomba": status, form aktifkan/matikan, target harian, hitung mundur, dan waktu per mode."""
    sid = int(siswa["id"])
    nama = _e(siswa["nama"])
    aktif = penugasan is not None and penugasan.aktif
    pesan = f'<p class="hl-pesan-simpan" role="status">{PESAN_TERSIMPAN}</p>' if tersimpan else ""
    if galat:
        pesan = f'<p class="hl-galat" role="alert">{_e(galat)}</p>'
    status = (f'<p><span class="hl-lencana-st hl-lencana-aktif-st">Aktif untuk {nama}</span></p>' if aktif
              else '<p><span class="hl-lencana-st hl-lencana-netral-st">Belum aktif</span></p>')
    centang = " checked" if _hitung_mundur_tampil(penugasan) else ""
    return (
        '<section class="hl-kartu" aria-labelledby="judul-mode-lomba"><h2 id="judul-mode-lomba">Mode Lomba</h2>'
        f"{pesan}{status}"
        f'<p class="hl-sub">Setelah aktif, {nama} melihat Mode Lomba di berandanya dan bisa memilih Latihan '
        f"({PK.PAKET_AKTIF.jumlah_soal} soal, {menit_anak(penugasan, PK.MODE_LATIHAN)} menit) atau Simulasi Lomba "
        f"({PK.PAKET_AKTIF.jumlah_soal_simulasi} soal, {menit_anak(penugasan, PK.MODE_SIMULASI)} menit).</p>"
        f'<form class="hl-form" method="post" action="{alamat_pengaturan(sid)}">'
        '<fieldset class="pilihan-kartu-st"><legend>Mode Lomba</legend>'
        f'<label class="pilihan-kartu-opsi-st"><input type="radio" name="aktif" value="1"{" checked" if aktif else ""}> Aktif</label>'
        f'<label class="pilihan-kartu-opsi-st"><input type="radio" name="aktif" value="0"{"" if aktif else " checked"}> Belum aktif</label></fieldset>'
        '<label class="hl-isian">Target latihan harian'
        f'<select name="target">{_pilihan_target(penugasan)}</select></label>'
        f'<label><input type="checkbox" name="hitung_mundur" value="1"{centang}> '
        "Tampilkan hitung mundur ke hari lomba</label>"
        + _isian_durasi(penugasan, PK.MODE_LATIHAN) + _isian_durasi(penugasan, PK.MODE_SIMULASI)
        + f'<p class="hl-sub">{CATATAN_DURASI}</p>'
        '<button class="btn-st" type="submit">Simpan</button></form></section>')


def _bungkus(judul: str, isi: str, ident) -> bytes:
    return _bingkai(
        judul, f"<style>{GAYA_HASIL}{GAYA_PENGATURAN}</style>" + '<div class="hasil-lomba">' + isi + "</div>",
        ident=ident, stitch=True, kelas_bungkus="pendamping-editorial-st bagikan-editorial-st",
        id_utama="judul-lomba", privat=True)


def _kepala(siswa, judul: str, tujuan: str, teks_kembali: str) -> str:
    return (
        f'<div class="jejak"><a href="{tujuan}">\u2190 {_e(teks_kembali)}</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">LATIHAN LOMBA</p>'
        f'<h1 id="judul-lomba">{_e(judul)} &mdash; {_e(siswa["nama"])}</h1></header>')


def _stat(nilai: str, label: str) -> str:
    return f'<div class="hl-stat"><span class="hl-stat-nilai">{nilai}</span><span class="hl-stat-label">{_e(label)}</span></div>'


def _stat_tren(progres: R.Progres) -> str:
    if progres.rata_awal is None or progres.rata_akhir is None:
        return _stat("&ndash;", "Belum cukup sesi untuk melihat tren")
    return (_stat(desimal(progres.rata_akhir), "Rata-rata 3 sesi terakhir")
            + _stat(desimal(progres.rata_awal), "Rata-rata 3 sesi pertama"))


def _label_sesi_selesai(progres: R.Progres) -> str:
    if not progres.jumlah_asal_kumpul:
        return "Sesi selesai"
    return f"Sesi selesai ({progres.jumlah_asal_kumpul} dikumpulkan cepat)"


def _kartu_ringkas(progres: R.Progres) -> str:
    """Terbaik/tren dari Latihan (dari 10); Simulasi punya stat terbaik sendiri (dari 35)."""
    total = P.JUMLAH_SOAL
    ada_simulasi = progres.terbaik_simulasi is not None
    terbaik = "&ndash;" if progres.terbaik is None else f"{progres.terbaik}/{total}"
    stat_simulasi = (_stat(f"{progres.terbaik_simulasi}/{PK.PAKET_AKTIF.jumlah_soal_simulasi}", "Simulasi terbaik")
                     if ada_simulasi else "")
    return ('<div class="hl-ringkas">'
            + _stat(str(progres.jumlah), _label_sesi_selesai(progres))
            + _stat(terbaik, "Latihan terbaik" if ada_simulasi else "Nilai terbaik")
            + stat_simulasi
            + _stat(f"{progres.terakhir}/{progres.terakhir_jumlah or total}", "Nilai terakhir")
            + _stat_tren(progres)
            + "</div>")


def _grafik(progres: R.Progres) -> str:
    """Nilai per sesi; bila ada sesi selain 10 soal (Simulasi), skala persen benar supaya bisa dibandingkan."""
    sesi = progres.sesi[-BATAS_TITIK_GRAFIK:]
    redup = [s.asal_kumpul for s in sesi]
    awal = progres.jumlah - len(sesi) + 1
    persen_mode = any(s.jumlah_soal != P.JUMLAH_SOAL for s in sesi)
    if persen_mode:
        nilai = [persen(s.nilai, s.jumlah_soal) for s in sesi]
        maks = SKALA_PERSEN
    else:
        nilai = [s.nilai for s in sesi]
        maks = max(P.JUMLAH_SOAL, *nilai)
    judul = ("Persen benar per sesi" if persen_mode else "Nilai per sesi") + (
        f" ({BATAS_TITIK_GRAFIK} sesi terakhir)" if progres.jumlah > BATAS_TITIK_GRAFIK else "")
    catatan = f'<p class="hl-sub">{CATATAN_GRAFIK_REDUP}</p>' if any(redup) else ""
    return (f'<section class="hl-kartu"><h2>{judul}</h2>'
            f'{G.grafik_nilai(nilai, maks, nomor_awal=awal, redup=redup)}{catatan}</section>')


def _topik_terendah(per_topik: Sequence[R.NilaiTopik]) -> str:
    ada = [n for n in per_topik if n.total]
    if len(ada) < MIN_TOPIK_BANDING:
        return ""
    paling = min(ada, key=lambda n: persen(n.benar, n.total))
    return (f'<p>Persentase benar terendah: <strong>{_e(RP.label_topik(paling.topik))}</strong> '
            f"({persen(paling.benar, paling.total)}%)</p>")


def _kartu_topik(progres: R.Progres) -> str:
    return ('<section class="hl-kartu"><h2>Nilai per topik (semua sesi)</h2>'
            + RP.daftar_topik(progres.per_topik_total, tampil_persen=True)
            + _topik_terendah(progres.per_topik_total) + "</section>")


def _kartu_sering_salah(sering: Sequence[R.JenisSering]) -> str:
    if not sering:
        return ('<section class="hl-kartu"><h2>Paling sering salah</h2>'
                '<p class="hl-sub">Belum ada jenis soal yang salah.</p></section>')
    butir = "".join(f"<li>{_e(j.label)}: salah {j.salah} dari {j.total}</li>" for j in sering)
    return f'<section class="hl-kartu"><h2>Paling sering salah</h2><ol class="hl-daftar-sering">{butir}</ol></section>'


def _teks_topik_sesi(sesi: R.RingkasSesi) -> str:
    return ", ".join(f"{RP.label_topik(n.topik)} {n.benar}/{n.total}" for n in sesi.per_topik)


def _chip(teks: str, kelas: str = "") -> str:
    kelas_penuh = f"hl-chip {kelas}".strip()
    return f'<li class="{kelas_penuh}">{_e(teks)}</li>'


def label_mode(sesi) -> str:
    return PK.LABEL_MODE_PENDEK.get(sesi.mode, PK.LABEL_MODE_PENDEK[PK.MODE_LATIHAN])


def _chip_sesi(sesi: R.RingkasSesi) -> str:
    chip = [_chip(label_mode(sesi)), _chip(durasi_menit_detik(sesi.waktu_terpakai_detik))]
    if sesi.status == K.WAKTU_HABIS:
        chip.append(_chip(_LABEL_STATUS[K.WAKTU_HABIS]))
    chip.extend(_chip(f"{_LABEL_TOPIK_PENDEK.get(n.topik, RP.label_topik(n.topik))} {n.benar}/{n.total}")
                for n in sesi.per_topik)
    if sesi.asal_kumpul:
        chip.append(_chip(LABEL_CEPAT, "hl-chip-cepat"))
    chip.append(_chip(f"{sesi.terisi} dari {sesi.jumlah_soal} diisi"))
    return "".join(chip)


def _kartu_sesi_hp(siswa_id: int, sesi: R.RingkasSesi) -> str:
    return (
        '<li class="hl-sesi-hp"><div class="hl-sesi-atas">'
        f'<span class="hl-sesi-tanggal">{_e(tanggal_wib(sesi.mulai_epoch))}</span>'
        f'<strong class="hl-sesi-nilai">{sesi.nilai}/{sesi.jumlah_soal}</strong></div>'
        f'<ul class="hl-chip-baris">{_chip_sesi(sesi)}</ul>'
        f'<a class="hl-sesi-lihat" href="{alamat_detail(siswa_id, sesi.sesi_id)}">Lihat</a></li>')


def _status_tabel(sesi: R.RingkasSesi) -> str:
    teks = _e(_LABEL_STATUS.get(sesi.status, sesi.status))
    if sesi.asal_kumpul:
        teks += f' <span class="hl-chip hl-chip-cepat">{LABEL_CEPAT}</span>'
    return teks


def _baris_riwayat(siswa_id: int, sesi: R.RingkasSesi) -> str:
    return (
        f'<tr><td class="hl-angka">{_e(tanggal_wib(sesi.mulai_epoch))}</td><td>{_e(label_mode(sesi))}</td>'
        f'<td class="hl-angka">{sesi.nilai}/{sesi.jumlah_soal}</td>'
        f'<td class="hl-angka">{durasi_menit_detik(sesi.waktu_terpakai_detik)}</td>'
        f'<td>{_status_tabel(sesi)}</td><td>{_e(_teks_topik_sesi(sesi))}</td>'
        f'<td class="hl-angka"><a href="{alamat_detail(siswa_id, sesi.sesi_id)}">Lihat</a></td></tr>')


def _kartu_riwayat(siswa_id: int, progres: R.Progres) -> str:
    terbaru = tuple(reversed(progres.sesi))[:BATAS_BARIS_RIWAYAT]
    catatan = ""
    if progres.jumlah > BATAS_BARIS_RIWAYAT:
        catatan = f'<p class="hl-sub">Menampilkan {BATAS_BARIS_RIWAYAT} sesi terbaru dari {progres.jumlah}.</p>'
    baris = "".join(_baris_riwayat(siswa_id, s) for s in terbaru)
    kartu = "".join(_kartu_sesi_hp(siswa_id, s) for s in terbaru)
    return ('<section class="hl-kartu"><h2>Riwayat sesi</h2>'
            '<div class="hl-gulir hl-riwayat-lebar"><table class="hl-tabel"><thead><tr>'
            "<th>Tanggal (WIB)</th><th>Jenis</th><th>Nilai</th><th>Waktu</th><th>Status</th><th>Nilai per topik</th><th></th>"
            f"</tr></thead><tbody>{baris}</tbody></table></div>"
            f'<ol class="hl-riwayat-hp">{kartu}</ol>{catatan}</section>')


def halaman_progres(siswa, progres: R.Progres, sering: Sequence[R.JenisSering], ident, *,
                    penugasan: Optional[AS.Penugasan] = None, tersimpan: bool = False, galat: str = "") -> bytes:
    """Kartu Mode Lomba (pengaturan), lalu progress satu anak: ringkasan, grafik, bar per topik, sering salah, riwayat."""
    kepala = (_kepala(siswa, "Latihan lomba", f"/anak/{int(siswa['id'])}?section=perkembangan", "Perkembangan")
              + kartu_pengaturan(siswa, penugasan, tersimpan, galat))
    catatan = f'<p class="hl-catatan">{CATATAN_DUGAAN}</p>'
    if progres.jumlah == 0:
        kosong = ('<section class="hl-kartu"><h2>Belum ada sesi latihan yang selesai</h2>'
                  '<p class="hl-sub">Hasil muncul di sini setelah anak menyelesaikan satu sesi Latihan Lomba.</p></section>')
        return _bungkus(f"Latihan lomba — {siswa['nama']}", kepala + kosong + catatan, ident)
    isi = (kepala + _kartu_ringkas(progres) + _grafik(progres) + _kartu_topik(progres)
           + _kartu_sering_salah(sering) + _kartu_riwayat(int(siswa["id"]), progres) + catatan)
    return _bungkus(f"Latihan lomba — {siswa['nama']}", isi, ident)


def halaman_detail(siswa, hasil: R.HasilRinci, ident) -> bytes:
    """Detail satu sesi selesai: ringkasan dan semua soal, termasuk dugaan kesalahan pengecoh."""
    sid = int(siswa["id"])
    status = _LABEL_STATUS.get(hasil.sesi.status, hasil.sesi.status)
    ringkas = ('<div class="hl-ringkas">'
               + _stat(f"{hasil.nilai}/{hasil.jumlah_soal}", "Nilai")
               + _stat(_e(label_mode(hasil.sesi)), "Jenis")
               + _stat(durasi_menit_detik(hasil.waktu_terpakai_detik), "Waktu")
               + _stat(_e(status), "Status")
               + _stat(_e(tanggal_wib(hasil.sesi.mulai_epoch)), "Mulai (WIB)")
               + "</div>")
    topik = f'<section class="hl-kartu"><h2>Nilai per topik</h2>{RP.daftar_topik(hasil.per_topik, tampil_persen=True)}</section>'
    kartu = "".join(RP.kartu_soal(butir, untuk_guru=True) for butir in hasil.butir)
    isi = (_kepala(siswa, "Sesi latihan", alamat_progres(sid), "Riwayat latihan lomba") + ringkas + topik
           + f'<p class="hl-catatan">{CATATAN_DUGAAN}</p>'
           + f'<section aria-labelledby="judul-soal-guru"><h2 id="judul-soal-guru">Semua soal</h2>'
           f'<div class="hl-daftar-soal">{kartu}</div></section>')
    return _bungkus(f"Sesi latihan — {siswa['nama']}", isi, ident)
