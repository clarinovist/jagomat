"""Halaman sisi anak: kerjakan sesi, daftar sesi ber-status.

Dipecah dari students.py (refactor 31 Aug 2026) — fungsi pindah utuh,
perilaku identik. students.py kini lapisan data; modul ini lapisan tampilan
dan mengimpor dari sana (satu arah). Palang tetap: halaman anak TIDAK boleh
menampilkan kunci, malrule, atau diagnosis — dijaga test_palang_*.
"""

from __future__ import annotations

import json

import brand
import visual_renderer
import design_tokens as T
from learning_stage_labels import penanda_tahap
from murid_shell import (
    PANAH_KEMBALI, aksi_topbar, bungkus_murid, ikon_murid, kepala_murid, tombol_keluar, topbar_murid,
)
from topics import Topik, dari_sesi
from students import (
    AWALAN_PILIHAN,
    PILIHAN_CARA,
    _escape,
    hasil_murid,
    sesi_murid,
    soal_murid,
)


def _tanggal_beranda(nilai: str) -> str:
    """Tanggal manusiawi; nilai warisan yang bukan ISO tetap di-escape caller."""
    from datetime import date
    bulan = ("Januari", "Februari", "Maret", "April", "Mei", "Juni",
             "Juli", "Agustus", "September", "Oktober", "November", "Desember")
    try:
        tanggal = date.fromisoformat(str(nilai)[:10])
    except ValueError:
        return str(nilai)
    return f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"


def _judul_beranda(sesi: dict) -> tuple[str, str]:
    """Topik dan ikon stabil, tidak berubah ketika urutan daftar berubah."""
    paket = dari_sesi(sesi["topik"])
    if paket.id == "campuran":
        return "Latihan campuran", "buku"
    if paket.id.startswith("gabungan:"):
        return "Latihan gabungan", "buku"
    ikon = "grafik" if paket.id == "statistika" else (
        "bilangan" if paket.id in {"pola-bilangan", "teori-bilangan",
                                  "aritmetika-dasar", "aritmatika-lanjut"} else "buku"
    )
    return paket.nama[:1].upper() + paket.nama[1:].lower(), ikon


def _tahap_beranda(sesi: dict) -> str:
    """Sesi bebas dan warisan juga memakai istilah netral untuk anak."""
    tahap = penanda_tahap(sesi["tujuan"])
    if tahap:
        return tahap
    if sesi["jenis"] == "remedial":
        return "Latihan terarah"
    return "Latihan Cepat" if sesi["mode"] == "drill" else "Latihan campuran"


def _penanda_beranda(sesi: dict) -> str:
    """Progres hanya untuk sesi yang masih dikerjakan, bukan nilai benar."""
    n, jumlah = sesi["terisi"], sesi["jumlah"]
    if sesi["selesai"] is None and n > 0 and jumlah > 0:
        persen = round(min(n, jumlah) / jumlah * 100, 1)
        return (
            '<span class="st-progres-label">'
            f'{n} dari {jumlah} soal tersimpan</span>'
            '<span class="st-progres-jalur" role="progressbar" '
            f'aria-label="Soal tersimpan" aria-valuemin="0" aria-valuemax="{jumlah}" '
            f'aria-valuenow="{min(n, jumlah)}">'
            f'<span class="st-progres-isi" style="width:{persen}%"></span>'
            '</span>'
        )
    format_label = ' · Pilihan ganda' if sesi.get('format_jawaban') == 'pilihan_ganda' else ''
    return f'<span class="murid-jumlah-st">{jumlah} soal{format_label}</span>'


def _kartu_beranda(sesi: dict, utama: bool = False) -> str:
    """Satu tautan per sesi, tanpa tombol/link bersarang di kartu utama."""
    judul, ikon = _judul_beranda(sesi)
    tahap = _tahap_beranda(sesi)
    selesai = sesi["selesai"] is not None
    direview = selesai and sesi["direview"] is not None
    if direview:
        label, kelas = "Selesai · sudah diperiksa", "diagnostik"
        aksi, jalur = "Lihat hasil", f"/murid/hasil/{sesi['id']}"
    elif selesai:
        label, kelas = "Menunggu diperiksa", "review"
        aksi, jalur = "", ""
    elif sesi["terisi"]:
        label, kelas = "Sedang dikerjakan", "selesai"
        aksi, jalur = "Lanjutkan", f"/murid/kerjakan/{sesi['id']}"
    else:
        label, kelas = "Belum dimulai", "netral"
        aksi, jalur = "Mulai", f"/murid/kerjakan/{sesi['id']}"
    badge = f'<span class="st-badge {kelas}">{label}</span>'
    penanda = _penanda_beranda(sesi)
    kelas_penanda = (
        "st-progres-soal"
        if not selesai and sesi["terisi"] > 0 and sesi["jumlah"] > 0
        else "st-jumlah-soal"
    )
    tanggal = _escape(_tanggal_beranda(sesi["tanggal"]))
    meta = tanggal  # label variasi tidak ditampilkan ke anak (audit area anak #10)
    # Marker tiga anak kartu dipertahankan: ikon, kolom teks, penanda.
    if utama:
        label_utama = "Lanjutkan latihanmu" if sesi["terisi"] else "Latihan untukmu"
        aksi = "Lanjutkan latihan" if sesi["terisi"] else "Mulai latihan"
        ilustrasi = (
            '<span class="murid-ilustrasi-st" aria-hidden="true">'
            '<span class="murid-lingkaran-st"></span>'
            f'{brand.maskot("menulis", 240)}</span>'
        )
        teks = (
            '<span class="st-kartu-teks">'
            f'<span class="murid-label-utama-st">{label_utama}</span>'
            f'<span class="murid-tahap-st">{tahap}</span>'
            f'<span class="murid-judul-sampul-st" role="heading" aria-level="2">{_escape(judul)}</span>'
            '<span class="murid-sub-sampul-st">Kerjakan pelan-pelan, ya.</span>'
            f'<span class="murid-meta-st">{meta}</span></span>'
        )
        ujung = (
            f'<span class="murid-lanjut-bawah-st {kelas_penanda}">' + penanda
            + f'<span class="murid-tombol-utama-st">{aksi}{ikon_murid("panah")}</span>'
            + ('<span class="murid-aman-st">Jawaban tersimpan aman</span>' if sesi["terisi"] else '')
            + '</span>'
        )
        return (
            f'<a class="st-kartu-baris" data-utama="true" href="{jalur}">'
            f'{ilustrasi}{teks}{ujung}</a>'
        )
    teks = (
        '<span class="st-kartu-teks">'
        f'<span class="murid-judul-kartu-st">{_escape(judul)}</span>'
        f'<span class="murid-tahap-st">{tahap}</span>'
        f'<span class="murid-meta-st">{meta}</span>{badge}</span>'
    )
    ujung = f'<span class="murid-ujung-st {kelas_penanda}">' + penanda
    if aksi:
        ujung += f'<span class="murid-aksi-st">{aksi}{ikon_murid("panah")}</span>'
    ujung += '</span>'
    tag = "a" if jalur else "div"
    href = f' href="{jalur}"' if jalur else ''
    return (
        f'<{tag} class="st-kartu-baris"{href}>'
        f'<span class="murid-ikon-topik-st">{ikon_murid(ikon)}</span>'
        f'{teks}{ujung}</{tag}>'
    )


def _keadaan_beranda(daftar: list, tugas: list, menunggu: list) -> str:
    """Blok maskot + pesan saat tidak ada sesi utama."""
    if not daftar:
        judul, pesan = "Siap untuk latihan pertama?", (
            "Belum ada sesi latihan yang disiapkan. Minta orang tua atau gurumu membuatkan, ya."
        )
    elif tugas:
        judul, pesan = "Belajar selangkah lagi", (
            "Gurumu akan menyiapkan langkah berikutnya. Latihan lain yang tersedia tetap bisa kamu buka di bawah."
        )
    elif menunggu:
        judul, pesan = "Terima kasih sudah mencoba!", (
            "Latihanmu sudah dikirim. Sekarang boleh istirahat dulu."
        )
    else:
        judul, pesan = "Latihanmu sudah diperiksa", (
            "Kamu bisa membuka hasil latihan sebelumnya di bawah."
        )
    return (
        '<section class="murid-keadaan-st">'
        f'{brand.maskot("berpikir", 240)}'
        f'<div><h2>{judul}</h2><p>{pesan}</p></div></section>'
    )


def _kartu_lomba(kon, siswa_id: int, sekarang: int | None, besar: bool) -> str:
    """Kartu Latihan Lomba beranda (hanya dipanggil saat sakelar hidup); jam server bila `sekarang` tak diberikan."""
    import time
    from contest_home import kartu_untuk_siswa
    return kartu_untuk_siswa(kon, siswa_id, int(time.time()) if sekarang is None else sekarang, besar)


def halaman_daftar_sesi_baru(
    kon, siswa_id: int, nama: str, sesi_selesai: int | None = None, lomba_aktif: bool = False,
    sekarang: int | None = None, orang_tua: bool = False,
) -> bytes:
    """Beranda buku belajar: satu sesi utama, tugas lain, kabar, dan riwayat.

    `orang_tua` (sakelar DAFTAR_AKUN_ANAK hidup) menambah satu tautan sekunder "Untuk Ayah/Bunda";
    bawaan False menghasilkan halaman yang byte-identik dengan sebelumnya.
    """
    from orang_tua_style import GAYA_TAUTAN_BERANDA, TAUTAN_BERANDA
    from contest_style import GAYA_BERANDA
    from style_stitch import gaya_stitch
    from students import beranda_murid

    data = beranda_murid(kon, siswa_id)
    daftar = data["sesi"]
    utama = next((s for s in daftar if s["id"] == data["utama_id"]), None)
    tugas = [s for s in daftar if s["selesai"] is None and s is not utama]
    menunggu = [s for s in daftar if s["selesai"] is not None and s["direview"] is None]
    riwayat = [s for s in daftar if s["selesai"] is not None and s["direview"] is not None]
    banner = ""
    if any(s["id"] == sesi_selesai and s["selesai"] is not None for s in daftar):
        banner = (
            '<div class="st-banner-sukses" role="status">'
            f'{brand.maskot("merayakan", 96, kelas="maskot-banner")}'
            '<span>Selesai! Latihanmu sudah dikirim.</span></div>'
        )
    kolom = _kartu_beranda(utama, True) if utama else ""
    kartu_lomba = _kartu_lomba(kon, siswa_id, sekarang, besar=not daftar) if lomba_aktif else ""
    if not utama:
        if not daftar and lomba_aktif:
            kolom, kartu_lomba = kartu_lomba, ""  # kartu besar menggantikan "Siap untuk latihan pertama?"
        else:
            kolom = _keadaan_beranda(daftar, tugas, menunggu)
    if tugas:
        kolom += (
            '<section class="murid-latihan-lain-st" aria-labelledby="judul-lain">'
            '<div class="murid-kepala-bagian-st"><h2 id="judul-lain">Latihan lainnya</h2>'
            f'<span>{len(tugas)} latihan</span></div>'
            + ''.join(_kartu_beranda(s) for s in tugas) + '</section>'
        )
    kolom += kartu_lomba
    pendamping = ""
    if menunggu:
        pendamping += (
            '<section class="murid-menunggu-st" aria-labelledby="judul-menunggu">'
            f'<h2 id="judul-menunggu">{ikon_murid("jam")}Menunggu diperiksa</h2>'
            '<h3>Jawabanmu sudah masuk.</h3>'
            '<p>Gurumu akan memeriksanya. Kamu tidak perlu mengirim ulang.</p>'
            + ''.join(_kartu_beranda(s) for s in menunggu) + '</section>'
        )
    if riwayat:
        pendamping += (
            '<details class="murid-riwayat-st"><summary>'
            f'{ikon_murid("buku")}<span><b>Latihan selesai</b>'
            f'<span>{len(riwayat)} latihan sudah diperiksa</span></span>{ikon_murid("lipat")}'
            '</summary><div class="murid-riwayat-isi-st">'
            + ''.join(_kartu_beranda(s) for s in riwayat) + '</div></details>'
        )
    topbar = topbar_murid(tombol_keluar())
    isi = f'''<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul("Ruang belajarku")}</title>{brand.tag_kepala()}
{kepala_murid(gaya_stitch() + (GAYA_BERANDA if lomba_aktif else "") + (GAYA_TAUTAN_BERANDA if orang_tua else ""))}</head><body class="st murid-beranda-st">
<a class="murid-lewati-st" href="#utama">Lewati ke latihan</a>
<div class="murid-wadah-st">
{topbar}
<main id="utama" class="murid-kanvas-st">
<section class="murid-sapaan-st" aria-labelledby="judul-sapaan">
<p class="murid-alis-st">RUANG BELAJARKU</p>
<h1 id="judul-sapaan">Halo, {_escape(nama)}!</h1><p>Sedikit demi sedikit, makin mengerti.</p>
<span class="murid-akun-hint-st">Bukan kamu? Tekan Keluar dulu.</span></section>
{banner}<div class="murid-grid-st"><div class="murid-kolom-utama-st">{kolom}</div>
{'<aside class="murid-pendamping-st" aria-label="Kabar latihanmu">' + pendamping + '</aside>' if pendamping else ''}
</div>{TAUTAN_BERANDA if orang_tua else ''}</main><footer class="murid-kaki-st">{T.TAGLINE} <span aria-hidden="true">✦</span> Satu langkah setiap kali.</footer>
</div>
</body></html>'''
    return isi.encode()


def halaman_kerja_baru(
    kon, siswa_id: int, sesi_id: int, tersimpan: int = 0,
    topik_paket: Topik | None = None, kabar_foto: str = "",
    jalur_aksi: str | None = None, akses_tautan: bool = False, foto_galat: bool = False,
) -> bytes | None:
    """Versi Stitch dari halaman kerja murid (S4).

    ``akses_tautan`` dipakai untuk tautan satu-sesi tanpa login. Data yang
    dirender tetap melewati palang siswa+sesi yang sama; yang berubah hanya
    tujuan form dan hilangnya navigasi menuju area akun/sesi lain.

    Logika data, struktur kartu, mode drill, timer, jaga (guard submit/
    beforeunload) — tetap mengikuti kontrak pengerjaan; yang berubah hanya
    markup + kelas CSS (mengadopsi GAYA_STITCH). Palang mutlak: TIDAK memuat
    kata kunci/malrule/diagnosa.

    Sumber visual (arsip lokal): ~/Documents/jagomat/riset/referensi/desain-ui/stitch/murid_kerjakan_soal_mobile/screen.png
    — topbar sticky teal+coral, timer strip teal, kartu soal putih dgn nomor
    badge bulat teal menggantung, Jawabanku input pusat, Caraku pil 2-kolom
    radio, save strip sticky bawah coral penuh.
    """
    from style_stitch import gaya_stitch

    info = sesi_murid(kon, siswa_id, sesi_id)
    if not info:
        return None
    if topik_paket is None:
        topik_paket = dari_sesi(info.get("topik"))
    daftar = soal_murid(kon, sesi_id, siswa_id)

    drill = info.get("mode", "diagnostik") == "drill"
    timer_mode = info.get("timer_mode", "tanpa") or "tanpa"
    durasi_menit = int(info.get("durasi_menit") or 15)
    timer_auto = 1 if info.get("timer_auto") else 0
    detik_lalu = int(info.get("detik_lalu") or 0)
    sudah_dikirim = bool(info.get("selesai"))

    if sudah_dikirim:
        if akses_tautan:
            return None
        isi = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul("Jawaban sudah dikirim")}</title>{brand.tag_kepala()}
{kepala_murid(gaya_stitch())}</head><body class="st kerja-editorial-st">
<div class="murid-wadah-st">
{topbar_murid(aksi_topbar("/murid", "Beranda", PANAH_KEMBALI))}
<main class="kerja-badan-st kerja-selesai-st" aria-labelledby="judul-kerja">
<p class="kerja-alis-st">CATATAN LATIHAN</p>
<h1 id="judul-kerja">Selesai untuk sekarang.</h1>
<div class="kerja-tersimpan-st" role="status">
<span class="ikon">✓</span><span><b>Jawabanmu sudah dikirim.</b><br>
Gurumu akan memeriksanya. Kamu tidak perlu mengirim ulang.</span></div>
<p><a class="kerja-btn-sekunder-st" href="/murid">Kembali ke sesi lain</a></p>
</main></div></body></html>"""
        return isi.encode()

    kartu: list[str] = []
    bagian_kini = None
    for s in daftar:
        if s["bagian"] != bagian_kini:
            bagian_kini = s["bagian"]
            judul = topik_paket.judul_bagian.get(
                bagian_kini, f"Bagian {bagian_kini}"
            )
            kartu.append(f'<div class="kerja-bagian-st">{judul}</div>')
            if bagian_kini in topik_paket.catatan_bagian:
                kartu.append(
                    f'<div class="kerja-catatan-bagian-st">'
                    f"{topik_paket.catatan_bagian[bagian_kini]}</div>"
                )
        t = s["terjawab"] or {}
        ssid = s["sesi_soal_id"]
        belum = " checked" if t.get("belum_pernah") else ""
        bintang = '<span class="kerja-bintang-st">★</span>' if s["tantangan"] else ""
        nomor = f'<span class="kerja-nomor-st">{s["nomor"]}</span>'
        from choice_pages import pertanyaan, radio_pilihan
        teks = pertanyaan(s['penyajian'], s.get('pilihan'), s['template_id'], namespace=str(s['nomor']))
        if s.get('pilihan') is not None:
            restate_pg = (f'<label class="kerja-label-st" for="restate-{ssid}">Soal ini mintanya apa?</label>'
                          f'<textarea class="kerja-restate-st" id="restate-{ssid}" name="restate_{ssid}">{_escape(t.get("restatement", ""))}</textarea>'
                          if s['minta_restatement'] and not drill else '')
            kartu.append(f'<div class="kerja-soal-st">{nomor}{bintang}{teks}'
                         + radio_pilihan(s['pilihan'], t.get('jawaban', ''), s['template_id']) + restate_pg
                         + f'<details class="rincian-ui-st cara-opsional-st"{" open" if t.get("cara", "").strip() else ""}>'
                         '<summary>Tambah penjelasan (opsional)</summary>'
                         f'<label class="kerja-label-st" for="cara-{ssid}">Caraku (boleh dikosongkan)</label>'
                         f'<textarea class="kerja-cara-st" id="cara-{ssid}" name="cara_{ssid}">{_escape(t.get("cara", ""))}</textarea></details>'
                         f'<input type="hidden" name="hadir_blm_{ssid}" value="1">'
                         f'<label class="kerja-centang-st"><input type="checkbox" name="blm_{ssid}"{belum}> belum pernah lihat soal seperti ini</label></div>')
            continue

        if drill:
            catatan_soal = ""
            if timer_mode == "soal":
                catatan_soal = (
                    '<div class="catatan-soal-timer-st" style="display:none">'
                    "Waktu untuk soal ini habis — lanjut ke soal berikutnya.</div>"
                )
            kartu.append(f"""
<div class="kerja-soal-st drill">
  {nomor}{bintang}
  {teks}
  <div class="kerja-jawab-st">
    <label class="head-jawab" for="jawab-{ssid}">Jawabanku</label>
    <input type="text" id="jawab-{ssid}" name="jwb_{ssid}"
           value="{_escape(t.get('jawaban', ''))}" autocomplete="off">
  </div>
  <label class="kerja-centang-st">
    <input type="checkbox" name="blm_{ssid}"{belum}>
    belum pernah lihat soal seperti ini
  </label>
  {catatan_soal}
</div>""")
            continue

        restate = ""
        if s["minta_restatement"]:
            nilai = _escape(t.get("restatement", ""))
            restate = (
                f'<label class="kerja-label-st" for="restate-{ssid}">Soal ini mintanya apa? '
                "(tulis pakai kalimatmu sendiri)</label>"
                f'<textarea class="kerja-restate-st" id="restate-{ssid}" name="restate_{ssid}">{nilai}</textarea>'
            )

        cara_tersimpan = t.get("cara", "") or ""
        pilihan_kini = ""
        teks_cara = cara_tersimpan
        if cara_tersimpan.startswith(AWALAN_PILIHAN):
            sisa = cara_tersimpan[len(AWALAN_PILIHAN):]
            pilihan_kini, _, teks_cara = sisa.partition(" — ")
            pilihan_kini = pilihan_kini.strip()
            teks_cara = teks_cara.strip()

        tombol = "".join(
            f'<label class="kerja-pill-st">'
            f'<input type="radio" name="pilih_{ssid}" value="{kode}"'
            f'{" checked" if kode == pilihan_kini else ""}>'
            f"<span>{_escape(teks)}</span></label>"
            for kode, teks in PILIHAN_CARA
        )

        kartu.append(f"""
<div class="kerja-soal-st">
  {nomor}{bintang}
  {teks}
  {restate}
  <div class="kerja-jawab-st">
    <label class="head-jawab" for="jawab-{ssid}">Jawabanku</label>
    <input type="text" id="jawab-{ssid}" name="jwb_{ssid}"
           value="{_escape(t.get('jawaban', ''))}" autocomplete="off">
  </div>
  <fieldset class="kerja-cara-pilih-st">
  <legend class="kerja-label-st">Caraku — pilih dulu yang paling mirip:</legend>
  <div class="kerja-pill-grup-st">{tombol}</div>
  </fieldset>
  <details class="rincian-ui-st cara-opsional-st"{" open" if teks_cara.strip() else ""}>
  <summary>Tambah penjelasan (opsional)</summary>
  <label class="kerja-label-st" for="cara-{ssid}">Caraku (boleh dikosongkan)</label>
  <textarea class="kerja-cara-st" id="cara-{ssid}" name="cara_{ssid}">{_escape(teks_cara)}</textarea>
  </details>
  <label class="kerja-centang-st">
    <input type="checkbox" name="blm_{ssid}"{belum}>
    belum pernah lihat soal seperti ini
  </label>
</div>""")

    # Konfirmasi setelah simpan.
    kabar = ""
    if tersimpan:
        kabar = (
            '<div class="kerja-tersimpan-st">'
            '<span class="ikon">✓</span>'
            f"<span>Tersimpan ✓ — {tersimpan} soal sudah "
            f"masuk. Boleh lanjut, atau tutup halaman ini.</span></div>"
        )

    if drill:
        petunjuk = (
            "<p><b>Cara mengerjakan — baca dulu:</b></p>"
            "<p>Kerjakan sebisamu, tulis jawaban di kotak <b>Jawabanku</b>."
            + (" Perhatikan waktunya." if timer_mode == "sesi" else "")
            + "</p>"
            "<p>Kalau ada soal yang belum pernah kamu lihat, centang kotaknya. Itu "
            "<b>bukan</b> salah — itu berguna untuk gurumu.</p>"
            "<p>Tidak apa-apa ada yang kosong. Jangan menebak asal. Kalau sudah selesai, "
            "tekan <b>Selesai &amp; kirim</b> di paling bawah. Kamu juga bisa menyimpan sementara dulu.</p>"
        )
    else:
        petunjuk = (
            "<p><b>Cara mengerjakan — baca dulu:</b></p>"
            "<p>Tiap soal ada bagian <b>Caraku</b>. Pilih satu yang paling mirip dengan "
            "caramu mendapat jawaban. Kalau mau, tulis juga caranya di kotak tulisan.</p>"
            "<p>Kalau ada soal yang belum pernah kamu lihat, centang kotaknya. Itu "
            "<b>bukan</b> salah — itu berguna untuk gurumu.</p>"
            "<p>Tidak apa-apa ada yang kosong. Jangan menebak asal. Kalau sudah selesai, "
            "tekan <b>Selesai &amp; kirim</b> di paling bawah. Kamu juga bisa menyimpan sementara dulu.</p>"
        )

    if info.get('format_jawaban') == 'pilihan_ganda':
        petunjuk = '<p>Pilih satu jawaban tiap soal. Kamu boleh menuliskan caramu. Pilih <b>Belum menjawab</b> untuk mengosongkan pilihan. Tidak apa-apa ada yang belum bisa.</p>'

    if info.get('format_jawaban') != 'pilihan_ganda':
        ringkasan_petunjuk = (
            'Tulis jawabanmu. Boleh kosong kalau belum tahu.' if drill else
            'Tulis jawaban dan pilih Caraku yang paling mirip. Boleh kosong kalau belum tahu.'
        )
        petunjuk = (
            f'<p>{ringkasan_petunjuk} Jangan menebak asal.</p>'
            '<details class="rincian-ui-st petunjuk-lengkap-st"><summary>Petunjuk lengkap</summary>'
            + petunjuk + '</details>'
        )

    # Timer Latihan Cepat: marker strip/tampil dan kontrak JS tetap.
    strip = ""
    if drill and timer_mode == "sesi":
        strip = (
            '<div class="kerja-timer-st hanya-layar" id="timer-strip">'
            + ikon_murid("jam")
            + "Sisa waktu: <b id=\"timer-tampil\">"
            f"{durasi_menit:02d}:00</b>"
            '<span id="timer-pesan" style="display:none">'
            " — waktu habis, kerjakan sebisanya dan simpan</span></div>"
        )

    # Timer dan penjaga isian memakai kontrak pengerjaan yang sama.
    skrip = ""
    if drill and timer_mode in ("sesi", "soal"):
        skrip = f"""
<script>
(function(){{
  var MODE = {json.dumps(timer_mode)};
  var DETIK = {durasi_menit * 60};
  var DETIK_LALU = {detik_lalu};
  var AUTO = {1 if timer_auto else 0};
  var mulai = Date.now() - DETIK_LALU * 1000;
  function fmt(s){{ return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0"); }}
  if (MODE === "sesi") {{
    var strip = document.getElementById("timer-strip");
    var tampil = document.getElementById("timer-tampil");
    function tick(){{
      var sisa = DETIK - Math.floor((Date.now()-mulai)/1000);
      if (sisa <= 0) {{
        sisa = 0;
        if (AUTO) {{
          var f = document.querySelector("form");
          if (f) {{
            f.dataset.kirimOtomatis = "1";
            var a = document.createElement("input");
            a.type = "hidden"; a.name = "aksi"; a.value = "selesai";
            f.appendChild(a); f.submit();
          }}
          return;
        }}
        var p = document.getElementById("timer-pesan");
        if (p) p.style.display = "";
        if (strip) strip.className = "kerja-timer-st habis hanya-layar";
      }}
      if (tampil) tampil.textContent = fmt(sisa);
    }}
    tick();
    setInterval(tick, 1000);
  }} else if (MODE === "soal") {{
    var kartu = document.querySelectorAll(".kerja-soal-st");
    var mulaiSoal = {{}};
    document.addEventListener("focusin", function(ev){{
      var k = ev.target.closest ? ev.target.closest(".kerja-soal-st") : null;
      if (!k) return;
      var i = Array.prototype.indexOf.call(kartu, k);
      if (i >= 0 && !(i in mulaiSoal)) mulaiSoal[i] = Date.now();
    }});
    function tick(){{
      var t = Date.now();
      kartu.forEach(function(k, i){{
        if (!(i in mulaiSoal)) return;
        var sisa = DETIK - Math.floor((t - mulaiSoal[i])/1000);
        if (sisa > 0) return;
        if (AUTO) {{
          k.querySelectorAll("input, textarea, button").forEach(function(inp){{
            inp.disabled = true;
          }});
        }}
        var n = k.querySelector(".catatan-soal-timer-st");
        if (n) n.style.display = "";
      }});
    }}
    setInterval(tick, 1000);
  }}
}})();
</script>
"""

    jaga = """
<script>
(function(){
  var f = document.querySelector('form');
  if (!f) return;
  var kotor = false;
  f.addEventListener('input', function(){ kotor = true; }, true);
  f.addEventListener('change', function(){ kotor = true; }, true);
  f.addEventListener('submit', function(e){
    var pemicu = e.submitter;
    kotor = false;
    if (pemicu) {
      if (pemicu.name) {
        var aksi = document.createElement('input');
        aksi.type = 'hidden'; aksi.name = pemicu.name; aksi.value = pemicu.value;
        f.appendChild(aksi);
      }
      pemicu.disabled = true;
      pemicu.dataset.labelAsli = pemicu.textContent;
      pemicu.textContent = 'Menyimpan\\u2026';
    }
  });
  window.addEventListener('pageshow', function(){
    var tombol = f.querySelectorAll('button[type=submit]');
    for (var i=0;i<tombol.length;i++) {
      tombol[i].disabled = false;
      if (tombol[i].dataset.labelAsli) tombol[i].textContent = tombol[i].dataset.labelAsli;
    }
  });
  window.addEventListener('beforeunload', function(e){
    if (kotor && f.dataset.kirimOtomatis !== '1') {
      e.preventDefault();
      e.returnValue = '';
    }
  });
})();
</script>
"""

    # Kirim foto cara pengerjaan hanya tersedia untuk akun murid. Tautan
    # berbagi sengaja hanya memberi kapabilitas mengerjakan satu sesi; upload
    # berkas merupakan permukaan terpisah dan tidak ikut dibuka.
    blok_foto = ""
    n_foto = 0
    if not akses_tautan:
        n_foto = kon.execute(
            "SELECT COUNT(*) AS n FROM lampiran WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()["n"]
    if not akses_tautan and (info.get('format_jawaban') != 'pilihan_ganda' or n_foto):
        daftar_foto = ""
        kabar_foto_html = ""
        if kabar_foto:
            kabar_foto_html = (
                f'<p id="kabar-foto" tabindex="-1" class="kerja-foto-kabar-st{" galat" if foto_galat else ""}" '
                f'role="{"alert" if foto_galat else "status"}">{_escape(kabar_foto)}</p>'
            )
        if n_foto:
            daftar_foto = (
                f'<p class="kerja-foto-jumlah-st">Sudah terkirim: {n_foto} foto. '
                "Boleh kirim lagi kalau ada lembar lain.</p>"
            )
        blok_foto = f"""
<div id="foto-cara-anak" class="kerja-foto-st hanya-layar">
  <div class="kerja-foto-kepala-st">
    {ikon_murid("kamera")}
    <b>Kerjakan di kertas? Kirim fotonya</b>
  </div>
  <p class="kerja-foto-sub-st">Foto lembar yang sudah kamu isi (boleh
  tulisan tangan). Gurumu yang akan memeriksa — kamu tidak perlu
  mengetik ulang.</p>
  {kabar_foto_html}
  {daftar_foto}
  <form method="post" action="/murid/foto/{sesi_id}"
        enctype="multipart/form-data" class="kerja-foto-form-st">
    {__import__('attachments').field_operasi_foto()}<label class="kerja-label-st" for="foto-cara">Pilih foto lembar</label>
    <input type="file" id="foto-cara" name="foto" accept="image/*" capture="environment">
    <button type="submit" class="kerja-btn-sekunder-st">Kirim foto caraku</button>
  </form>
</div>"""

    aksi = _escape(jalur_aksi or f"/murid/kerjakan/{sesi_id}")
    tautan_tutup = "" if akses_tautan else aksi_topbar("/murid", "Tutup", ikon_murid("tutup"))
    script_mulai = ""
    if akses_tautan:
        script_mulai = (
            "<script>fetch(" + json.dumps(aksi)
            + ", {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},"
            "body:'aksi=mulai',keepalive:true}).catch(function(){});</script>"
        )

    isi = f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul(f"Kerjakan — {_escape(topik_paket.judul_lembar)}")}</title>
{brand.tag_kepala()}
{kepala_murid(gaya_stitch())}</head><body class="st kerja-editorial-st">
<div class="murid-wadah-st">
{topbar_murid(tautan_tutup)}
<main class="kerja-badan-st" aria-labelledby="judul-kerja">
<header class="kerja-pembuka-st">
<p class="kerja-alis-st">LEMBAR LATIHAN</p>
<h1 id="judul-kerja">{'Latihan cepat' if drill else 'Tunjukkan caramu.'}</h1>
<p class="kerja-meta-st"><b>Halo, {_escape(info['nama'])}</b> &middot; {_escape(_tanggal_beranda(info['tanggal']))}
 &middot; {len(daftar)} soal {penanda_tahap(info.get('tujuan', 'bebas'))}
 {'&middot; Latihan Cepat' if drill else ''}</p>
</header>
{strip}
{kabar}
<div class="kerja-petunjuk-st">
  <div class="baris-petunjuk">
    <div>
      {petunjuk}
    </div>
  </div>
</div>
<form method="post" action="{aksi}">
<input type="hidden" name="flow_kosong" value="1">
<input type="hidden" name="revisi_pekerjaan" value="{__import__('student_submissions').revisi(kon, sesi_id)}">
{" ".join(kartu)}
<div class="kerja-simpan-strip-st hanya-layar">
  <button type="submit" name="aksi" value="simpan" class="sekunder">Simpan sementara</button>
  <button type="submit" name="aksi" value="selesai">Selesai &amp; kirim
    {ikon_murid("panah")}</button>
</div>
</form>
{blok_foto}
{jaga}{skrip}{script_mulai}
</main></div></body></html>"""
    return isi.encode()


def halaman_hasil_murid(kon, siswa_id: int, sesi_id: int) -> bytes | None:
    """Halaman /murid/hasil/<id> — anak melihat letak salahnya.

    Poin b feedback Filia ("apa yang aplikasi bisa bantu agar anak mampu
    meningkatkan nilainya"): benar/salah saja tidak mengajari apa pun.
    Halaman ini menampilkan, per soal: jawaban anak sendiri, benar/salah,
    dan LANGKAH pengerjaan yang benar (Soal.pembahasan).

    Hanya terbuka setelah guru mereview — gerbangnya di students.hasil_murid
    (None = belum direview / bukan miliknya), dan pemanggil menjawab 404.

    Yang sengaja TIDAK ditampilkan: kode diagnosis K/H/E/N/B, malrule, dan
    alasan. Anak butuh tahu letak salahnya, bukan label tipe kesalahannya.
    """
    from style_stitch import gaya_stitch

    hasil = hasil_murid(kon, siswa_id, sesi_id)
    if hasil is None:
        return None

    kartu = []
    for b in hasil["soal"]:
        if not b["dijawab"]:
            status = '<span class="st-badge selesai">Belum dijawab</span>'
            kelas = "hasil-soal-st kosong"
        elif b["benar"]:
            status = '<span class="st-badge diagnostik">Benar</span>'
            kelas = "hasil-soal-st benar"
        elif b.get('perlu_ditinjau'):
            status = '<span class="st-badge baru">Perlu ditinjau bersama</span>'
            kelas = "hasil-soal-st kosong"
        else:
            status = '<span class="st-badge baru">Belum tepat</span>'
            kelas = "hasil-soal-st salah"

        jawabku = ""
        if b["dijawab"]:
            jawabku = (
                f'<p class="hasil-jawabku-st">Jawabanmu: '
                f'<b>{_escape(b["jawabanku"])}</b></p>'
            )

        # Pembahasan tersedia untuk SEMUA soal, termasuk yang benar (dilipat).
        # Jawaban benar karena menebak tetap dapat ditinjau caranya.
        # Tanpa pembahasan, blok tidak muncul — bukan diisi basa-basi.
        langkah = ""
        if b["pembahasan"]:
            langkah = (
                '<div class="hasil-langkah-st">'
                + ikon_murid("lampu") +
                f'<div><b>Caranya:</b> {_escape(b["pembahasan"])}</div></div>'
            )

        if langkah and b['benar']:
            langkah = ('<details class="rincian-ui-st hasil-cara-st">'
                       '<summary>Lihat caranya</summary>' + langkah + '</details>')
        kartu.append(
            f'<div class="{kelas}" id="hasil-soal-{b["nomor"]}">'
            f'<div class="hasil-kepala-st">'
            f'<span class="hasil-nomor-st">{b["nomor"]}</span>{status}</div>'
            f'<div class="hasil-teks-st">{visual_renderer.render_pertanyaan(b["penyajian"], gaya="stitch", namespace=str(b["nomor"]))}</div>'
            f"{jawabku}{langkah}</div>"
        )

    n_benar, n_soal = hasil["benar"], hasil["jumlah"]
    # Nada ringkasan sengaja tidak menghakimi: yang ditonjolkan adalah
    # "sudah dikoreksi, ini caranya", bukan skor telanjang.
    if n_benar == n_soal:
        pesan = "Semua benar! Baca juga caranya supaya makin mantap."
    elif any(b.get('perlu_ditinjau') for b in hasil['soal']):
        pesan = "Ada pekerjaan yang perlu ditinjau bersama. Ceritakan caramu kepada guru."
    elif n_benar == 0:
        pesan = "Belum ada yang tepat — tidak apa-apa. Baca caranya, lalu coba lagi."
    else:
        pesan = "Yang belum tepat ada caranya di bawah. Baca pelan-pelan, ya."

    # Kartu rumus (poin c feedback Filia): hanya untuk konsep yang anak
    # BELUM tepat. Diletakkan di atas daftar soal, saat anak paling siap
    # menerimanya — bukan sebagai modul teori terpisah yang harus dibaca
    # sebelum boleh berlatih (anak SD tidak membaca teori yang tidak
    # sedang ia butuhkan). Semua benar -> tidak ada kartu, jangan
    # menyodorkan teori tanpa keperluan.
    import rumus as modul_rumus

    salah_ids = [
        b["template_id"] for b in hasil["soal"]
        if b["dijawab"] and not b["benar"]
    ]
    from learning_visuals import render_bantuan

    kartu_rumus = modul_rumus.kartu_untuk_banyak(salah_ids)
    blok_rumus = ""
    if kartu_rumus:
        isi_kartu = "".join(
            '<div class="rumus-kartu-st">'
            f'<div class="rumus-judul-st">{_escape(k.judul)}</div>'
            f'<div class="rumus-inti-st">{_escape(k.inti)}</div>'
            + (
                f'<div class="rumus-contoh-st">Contoh: {_escape(k.contoh)}</div>'
                if k.contoh else ""
            )
            + (render_bantuan(k.bantuan, konteks="hasil_sah",
                              namespace=f"hasil-{sesi_id}-kartu-{indeks}")
               if k.bantuan is not None else "")
            + "</div>"
            for indeks, k in enumerate(kartu_rumus)
        )
        blok_rumus = (
            '<details class="rumus-blok-st">'
            '<summary class="rumus-kepala-st">'
            + ikon_murid("buku") +
            "<b>Ingat rumusnya dulu</b>" + ikon_murid("lipat") + "</summary>"
            f"{isi_kartu}</details>"
        )

    perlu_dilihat = [b for b in hasil['soal'] if not b['benar']]
    lompat = (
        '<nav class="hasil-lompat-st" aria-label="Soal untuk dilihat bersama">'
        + ''.join(f'<a href="#hasil-soal-{b["nomor"]}">Soal {b["nomor"]}</a>' for b in perlu_dilihat)
        + '</nav>' if perlu_dilihat else ''
    )
    isi = f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul("Hasil &amp; cara")}</title>
{brand.tag_kepala()}
{kepala_murid(gaya_stitch())}</head><body class="st hasil-editorial-st">
<div class="murid-wadah-st">
{topbar_murid(aksi_topbar("/murid", "Sesi lain", PANAH_KEMBALI))}
<main class="kerja-badan-st" aria-labelledby="judul-hasil">
<header class="kerja-pembuka-st">
<p class="kerja-alis-st">CATATAN LATIHAN</p>
<h1 id="judul-hasil">Lihat hasil &amp; caranya.</h1>
<p class="kerja-meta-st"><b>Halo, {_escape(hasil['nama'])}</b> &middot;
 {_escape(_tanggal_beranda(hasil['tanggal']))}</p>
</header>
<div class="hasil-ringkas-st">
  <div class="hasil-skor-st">{n_benar}<span>/{n_soal}</span><small>jawaban benar</small></div>
  <div class="hasil-pesan-st">{pesan}</div>
</div>
{lompat}{blok_rumus}
{"".join(kartu)}
<div class="kerja-navigasi-st hanya-layar">
  <a class="kerja-btn-sekunder-st" href="/murid/kerjakan/{sesi_id}">Lihat lembarku</a>
</div>
</main></div></body></html>"""
    return isi.encode()
