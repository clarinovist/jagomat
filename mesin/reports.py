"""Halaman laporan per anak + diagnosa jawaban.

Dipecah dari web.py (refactor 31 Aug 2026) — fungsi pindah utuh, perilaku
identik. Frame halaman diimpor dari teacher_pages.
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import brand
import database
import profile_workspace
from learning_journey import perjalanan_belajar
from cycle_report import render_perjalanan
from report_dashboard import GAYA_LAPORAN, render_aktivitas, render_materi, render_tugas
from report_navigation import halaman_daftar, navigasi_halaman, parameter_laporan, pilihan, url_laporan
from report_metrics import hari_wib, statistik_laporan, tugas_belum_selesai
from mastery_report import GAYA_PETA, peta_penguasaan, render_kriteria, render_peta
from mastery_evidence import lengkapi_bukti_materi
import design_tokens as T
from diagnosis import diagnosa
from generator import LEVEL_BAWAAN
from template_labels import nama_tipe_soal as _nama_tipe_soal
from question_context import label_profil_parameter as label_kelas
from topics import TOPIK_BAWAAN
from teacher_pages import _ambil, _halaman, _soal_dari_baris



def diagnosa_murid(kon, sesi_id: int) -> int:
    """Jalankan diagnosis atas semua jawaban SESI ini yang belum dinilai.

    Dipanggil otomatis setiap kali anak menyimpan dari HP, supaya guru yang
    membuka halaman sesi langsung melihat BENAR/kode — bukan deretan "?"
    oranye yang menunggu diklik dulu.

    Satu palang yang membuat ini aman: baris diagnosis yang `manual=1`
    (keputusan guru) DILEWATI, bukan dihitung ulang. Mesin boleh menyegarkan
    usulannya di kode_usulan, tapi kode_final dan benar milik guru tetap.
    Tanpa itu, sekali anak memperbarui jawaban dari HP, penilaian guru
    terhapus senyap — kegagalan paling mahal jenisnya.

    Mengembalikan jumlah soal yang baru didiagnosis. Baris tanpa jawaban
    (soal yang anak lewati) tidak dibuat — aturan yang sama dengan guru.
    """
    jumlah = 0
    from choice_store import format_sesi
    if format_sesi(kon, sesi_id) == 'pilihan_ganda':
        from choice_assessment import nilai_pilihan
        for b in database.isi_sesi(kon, sesi_id):
            if b['jawaban_id'] is None or b['manual'] == 1:
                continue
            u = nilai_pilihan(b['kunci'], b['jawaban'] or '')
            database.simpan_diagnosis(kon, b['jawaban_id'], u.benar, None, None, None, u.alasan, False)
            jumlah += 1
        return jumlah
    # Mode sesi: drill (Latihan Cepat) tidak meminta Caraku, jadi diagnosis
    # memakai cara sintetis supaya aturan "jawaban tanpa cara = N (menebak)"
    # tidak salah menuduh. Storage tetap cara='' — lihat students.AWALAN_DRILL.
    import students  # impor terlambat: modul halaman tidak boleh mengimpor students di atas

    baris_mode = kon.execute(
        "SELECT mode FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    drill = bool(baris_mode and baris_mode["mode"] == "drill")

    def _cara(b) -> str:
        cara = b["cara"] or ""
        return students.AWALAN_DRILL + cara if drill else cara

    for b in database.isi_sesi(kon, sesi_id):
        if b["jawaban_id"] is None:
            continue  # anak melewati soal ini: biarkan tanpa baris
        if b["manual"] == 1:
            # Segarkan usulan mesin saja; vonis guru tidak disentuh.
            soal = _soal_dari_baris(b)
            u = diagnosa(
                b["kunci"], b["jawaban"] or "", _cara(b),
                b["restatement"] or "", bool(b["belum_pernah"]),
                database.malrule_soal(kon, b["soal_id"]),
                soal.minta_restatement, soal=soal,
            )
            kon.execute(
                """UPDATE diagnosis SET kode_usulan = ?, alasan = ?
                   WHERE jawaban_id = ?""",
                (u.kode, u.alasan, b["jawaban_id"]),
            )
            continue
        soal = _soal_dari_baris(b)
        u = diagnosa(
            b["kunci"], b["jawaban"] or "", _cara(b),
            b["restatement"] or "", bool(b["belum_pernah"]),
            database.malrule_soal(kon, b["soal_id"]),
            soal.minta_restatement, soal=soal,
        )
        database.simpan_diagnosis(
            kon, b["jawaban_id"],
            benar=u.benar, kode_usulan=u.kode, kode_final=u.kode,
            malrule_id=u.malrule_id, alasan=u.alasan, manual=False,
        )
        jumlah += 1
    return jumlah

def _chart_tren(ring) -> str:
    """SVG line chart % benar per sesi (mockup guru-laporan).

    ring diurutkan DESC oleh database.ringkasan; dibalik supaya sumbu x
    berjalan kronologis (sesi terbaru di kanan). Kalau kurang dari 2 titik
    tidak digambar — satu titik tidak bisa disebut tren.
    """
    if len(ring) < 2:
        return ""
    TEAL, GRID, AXIS = T.STATUS_KUAT, T.CHART_GRID, T.CHART_AXIS
    urut = list(reversed(ring))
    LEBAR, TINGGI = 540, 240
    PAD_X, PAD_Y, PAD_B = 40, 16, 40
    n = len(urut)
    def x(i):  # posisi titik ke-i
        return PAD_X + i * (LEBAR - PAD_X - 12) / max(1, n - 1)
    def y(persen):  # 0..100 -> koordinat (SVG y ke bawah)
        return PAD_Y + (100 - persen) * (TINGGI - PAD_Y - PAD_B) / 100
    pts = []
    for i, r in enumerate(urut):
        jml = r["jumlah_soal"] or 0
        psen = (r["benar"] or 0) / jml * 100 if jml else 0
        pts.append(round(x(i), 1))
        pts.append(round(y(psen), 1))
    poly = " ".join(",".join(str(p) for p in pts[i:i+2]) for i in range(0, len(pts), 2))
    titik = "".join(
        f'<circle cx="{(pts[i])}" cy="{pts[i+1]}" r="4" fill="{TEAL}"/>'
        for i in range(0, len(pts), 2)
    )
    grid = "".join(
        f'<line x1="{PAD_X}" y1="{y(p)}" x2="{LEBAR-12}" y2="{y(p)}" '
        f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>'
        f'<text x="{PAD_X-6}" y="{y(p)+4}" text-anchor="end" '
        f'font-size="11" fill="{AXIS}">{p}</text>'
        for p in (25, 50, 75, 100)
    )
    xlab = "".join(
        f'<text x="{x(i)}" y="{TINGGI-16}" text-anchor="middle" '
        f'font-size="11" fill="{AXIS}">#{urut[i]["sesi_id"]}</text>'
        for i in range(n)
    )
    return (
        f'<svg viewBox="0 0 {LEBAR} {TINGGI}" role="img" '
        f'aria-label="Tren persentase benar per sesi">'
        f"{grid}{poly and ''}"
        f'<polyline points="{poly}" fill="none" stroke="{TEAL}" '
        f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f"{titik}{xlab}"
        f'<line x1="{PAD_X}" y1="{y(0)}" x2="{LEBAR-12}" y2="{y(0)}" '
        f'stroke="{AXIS}" stroke-width="1"/>'
        f'<text x="{LEBAR-12}" y="{PAD_Y-2}" text-anchor="end" font-size="11" '
        f'fill="{AXIS}">% benar</text>'
        f"</svg>"
    )

# Kamus kode diagnosis dalam bahasa sehari-hari (untuk orang tua).
# Kunci = kode di basis data; nilai = (sebutan ramah, arti 1 kalimat).
# Dipakai panel "Arti kode penilaian" — bebas jargon teknis (malrule,
# miskonsepsi, diagnosis tidak boleh muncul di sini).
KAMUS_ORTU = (
    ("BENAR", "Tepat", "jawabannya cocok dengan kunci."),
    ("K", "Keliru konsep (salah konsep)", "caranya belum tepat — perlu diajar ulang, bukan dimarahi."),
    ("B", "Salah baca soal", "yang ditanya disalahartikan — latih membaca soal, bukan materinya."),
    ("H", "Salah hitung", "caranya sudah benar, berhitungnya meleset — latihan saja."),
    ("E", "Salah tulis akhir", "hitungan benar tapi salah menyalin ke jawaban — kecerobohan, bukan tak paham."),
    ("T", "Perlu cek pengenalan", "anak menandai belum pernah melihat atau masih bingung — periksa pengalamannya, bukan langsung dianggap salah."),
    ("N", "Menebak", "jawab tanpa menunjukkan cara — tanyakan langsung sebelum dinilai."),
)


def _nama_topik(topik_id: str) -> str:
    """Nama ramah topik; id mentah bila tak dikenal (data warisan).

    topics.ambil melempar untuk topik asing — laporan warisan tidak boleh
    500 hanya karena satu sesi menyimpan topik yang sudah tidak ada.
    """
    from topics import ambil

    if topik_id.startswith("gabungan:"):
        jumlah = len([t for t in topik_id.split(":", 1)[1].split(",") if t])
        return f"Gabungan {jumlah} topik"
    try:
        return ambil(topik_id).nama
    except KeyError:
        return topik_id


BULAN_PENDEK = (
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
)

def _rapikan_kalimat(teks: str) -> str:
    """Kapitalisasi awal dan akhiri kalimat tanpa merusak singkatan."""
    bersih = teks.strip()
    if not bersih:
        return ""
    hasil = bersih[0].upper() + bersih[1:]
    return hasil if hasil.endswith((".", "!", "?")) else hasil + "."


def _tanggal_pendek(nilai) -> str:
    """Tanggal Indonesia ringkas; data warisan yang aneh tetap tampil aman."""
    mentah = str(nilai or "")
    try:
        tanggal = datetime.strptime(mentah, "%Y-%m-%d")
    except ValueError:
        return f'<span class="tanggal-ringkas">{html.escape(mentah or "—")}</span>'
    label = f"{tanggal.day} {BULAN_PENDEK[tanggal.month - 1]} {tanggal.year}"
    return (
        f'<time class="tanggal-ringkas" datetime="{html.escape(mentah)}">'
        f"{label}</time>"
    )


def _periode_aktivitas(parameter):
    """Rentang inklusif untuk ringkasan; input tidak sah kembali aman ke 7 hari."""
    akhir = hari_wib()
    periode = parameter.get('periode', '7')
    if periode == 'minggu':
        mulai = akhir - timedelta(days=akhir.weekday())
        label = 'Aktivitas minggu ini'
    elif periode == 'bulan':
        mulai = akhir.replace(day=1)
        label = 'Aktivitas bulan ini'
    elif periode == 'custom':
        try:
            mulai = date.fromisoformat(parameter.get('mulai', ''))
            akhir_custom = date.fromisoformat(parameter.get('sampai', ''))
            panjang = (akhir_custom - mulai).days + 1
            if mulai > akhir_custom or mulai.toordinal() <= panjang:
                raise ValueError
        except ValueError:
            periode, mulai = '7', akhir - timedelta(days=6)
            label = 'Aktivitas 7 hari terakhir'
        else:
            akhir = akhir_custom
            label = 'Aktivitas pada rentang pilihan'
    else:
        periode, mulai = '7', akhir - timedelta(days=6)
        label = 'Aktivitas 7 hari terakhir'
    return periode, mulai, akhir, label


def _kontrol_periode_aktivitas(siswa_id, periode, mulai, akhir):
    """Preset tautan dan form GET native; tanpa JavaScript."""
    opsi = (
        ('7', '7 hari'),
        ('minggu', 'Minggu ini'),
        ('bulan', 'Bulan ini'),
    )
    preset = pilihan(
        'Periode aktivitas', opsi, periode,
        lambda k: url_laporan(siswa_id, periode=k),
    )
    nilai_mulai = mulai.isoformat() if periode == 'custom' else ''
    nilai_akhir = akhir.isoformat() if periode == 'custom' else ''
    return (
        '<div class="laporan-periode-kontrol">' + preset
        + f'<form method="get" action="/anak/{siswa_id}" class="laporan-rentang-form">'
        '<strong class="laporan-rentang-label">Rentang sendiri</strong>'
        '<input type="hidden" name="section" value="perkembangan">'
        '<input type="hidden" name="periode" value="custom">'
        f'<label>Dari tanggal<input type="date" name="mulai" value="{nilai_mulai}" required></label>'
        f'<label>Sampai tanggal<input type="date" name="sampai" value="{nilai_akhir}" required></label>'
        '<button type="submit" class="st-tombol-sekunder">Terapkan rentang</button>'
        '</form></div>'
    )


def _kartu_kamus() -> str:
    baris = "".join(
        f'<li><span class="dot {"kuat" if kode == "BENAR" else ("salah" if kode == "K" else "lemah")}"></span>'
        f"<span><b>{'' if kode == 'BENAR' else kode + ' — '}{html.escape(sebutan)}</b> — {html.escape(arti)}</span></li>"
        for kode, sebutan, arti in KAMUS_ORTU
    )
    return (
        f'<section class="kartu-st cara-baca-laporan" id="arti-kode"><h2>'
        f'Arti kode penilaian</h2>'
        f'<p class="sub">Tiap soal dinilai dengan salah satu sebutan ini:</p>'
        f'<ul class="diagnosis-lis">{baris}</ul></section>'
    )


def _riwayat_latihan(kon, siswa_id: int, periode='semua', topik='semua', halaman='1') -> str:
    """Filter tanggal sesi; tidak mengubah statistik aktivitas jawaban."""
    semua = database.ringkasan(kon, siswa_id)

    def kelompok(r):
        kode = _ambil(r, 'topik', TOPIK_BAWAAN) or TOPIK_BAWAAN
        return 'gabungan' if kode.startswith('gabungan:') else kode

    topik_ada = sorted({kelompok(r) for r in semua})
    if topik not in topik_ada:
        topik = 'semua'
    if periode not in {'7', '30', 'semua'}:
        periode = 'semua'
    akhir = hari_wib()
    mulai = akhir - timedelta(days=int(periode) - 1) if periode != 'semua' else None

    def masuk(r):
        if topik != 'semua' and kelompok(r) != topik:
            return False
        if mulai is None:
            return True
        try:
            tanggal_sesi = date.fromisoformat(str(r['tanggal']))
        except ValueError:
            return False
        return mulai <= tanggal_sesi <= akhir

    tersaring = [r for r in semua if masuk(r)]
    ring, nomor, jumlah = halaman_daftar(tersaring, halaman, 20)

    def url(**opsi):
        return url_laporan(siswa_id, 'riwayat', **opsi)

    filter_html = (
        '<h3>Periode</h3>' + pilihan('Periode sesi',
            [('7', '7 hari'), ('30', '30 hari'), ('semua', 'Semua waktu')], periode,
            lambda k: url(periode=k, topik=topik))
        + '<h3>Topik</h3>' + pilihan('Topik sesi', [('semua', 'Semua')] + [
            (k, 'Gabungan' if k == 'gabungan' else _nama_topik(k)) for k in topik_ada],
            topik, lambda k: url(periode=periode, topik=k))
        + '<p class="laporan-catatan">Sesi terkirim · berdasarkan tanggal sesi.</p>'
        '<details class="rincian-ui-st"><summary>Aturan filter tanggal</summary>'
        '<p class="laporan-catatan">Periode berdasarkan tanggal sesi, bukan tanggal aktivitas jawaban '
        'atau tanggal pengiriman. Hanya sesi yang selesai dikirim. '
        + (f'{_tanggal_pendek(mulai.isoformat())} – {_tanggal_pendek(akhir.isoformat())} · WIB. '
           'Tanggal sesi yang tidak valid tidak masuk periode ini.' if mulai else 'Semua tanggal, termasuk catatan tanggal warisan.')
        + f'</p></details><p>{len(tersaring)} sesi sesuai filter · {len(semua)} sesi seluruh catatan.</p>'
    )
    tren = "".join(
        f'<tr><td data-label="Sesi"><span><b>Sesi #{r["sesi_id"]}</b>'
        f'<small>{_tanggal_pendek(r["tanggal"])}</small></span></td>'
        f'<td data-label="Topik"><span>{html.escape(_nama_topik(_ambil(r, "topik", TOPIK_BAWAAN) or TOPIK_BAWAAN))}'
        f'<small>{html.escape(label_kelas(str(_ambil(r, "level", LEVEL_BAWAAN))))}</small></span></td>'
        f'<td class="angka" data-label="Benar / tersedia"><span class="rasio-laporan">{r["benar"] or 0} / {r["jumlah_soal"]}</span></td>'
        f'<td data-label="Rincian"><a href="/sesi/{r["sesi_id"]}" '
        f'aria-label="Buka sesi {r["sesi_id"]}">Buka sesi <span aria-hidden="true">↗</span></a></td></tr>'
        for r in ring
    ) or '<tr><td colspan="4" class="kosong">Tidak ada sesi yang cocok dengan filter. Belum ada sesi yang selesai dikirim pada pilihan ini.</td></tr>'
    return (
        filter_html
        + '<section class="kartu detail-teknis-laporan" id="riwayat-hasil-sesi" aria-labelledby="judul-riwayat-sesi">'
        '<h2 id="judul-riwayat-sesi">Riwayat hasil sesi</h2>'
        '<p class="laporan-catatan" id="penjelasan-hasil-sesi">Benar / tersedia: jawaban benar dari semua soal tersedia, '
        'termasuk yang belum dijawab. Bukan persentase pemahaman atau tren kemampuan antar topik.</p>'
        '<div class="tabel-wrap tabel-tren"><table aria-describedby="penjelasan-hasil-sesi">'
        '<caption class="sr-only">Hasil sesi dari yang terbaru, beserta tanggal dan variasi soal</caption>'
        '<thead><tr><th scope="col">Sesi / tanggal</th><th scope="col">Topik</th>'
        '<th scope="col">Benar / tersedia</th><th scope="col">Rincian</th></tr></thead>'
        f'<tbody>{tren}</tbody></table></div></section>'
        + f'<p class="laporan-catatan">Menampilkan {len(ring)} dari {len(tersaring)} sesi sesuai filter.</p>'
        + navigasi_halaman(nomor, jumlah, lambda n: url(periode=periode, topik=topik, halaman=n))
    )


def _catatan_latihan(kon, siswa_id):
    """Catatan seluruh latihan dipisahkan dari filter tanggal sesi."""
    mis = [m for m in database.miskonsepsi_berulang(kon, siswa_id) if m["jumlah_sesi"] > 1]
    daftar_mis = "".join(
        f'<tr><td data-label="Kekeliruan:">{html.escape(m["alasan"] or "Cara yang dipakai belum tepat")}</td>'
        f'<td data-label="Tipe soal:">{html.escape(_nama_tipe_soal(m["template_id"]))}</td>'
        f'<td data-label="Topik:">{html.escape(_nama_topik(m["topik"]))}</td>'
        f'<td data-label="Jumlah sesi:" class="angka">{m["jumlah_sesi"]}</td>'
        f'<td data-label="Rentang:">{_tanggal_pendek(m["pertama"])} &rarr; '
        f'{_tanggal_pendek(m["terakhir"])}</td></tr>' for m in mis
    ) or '<tr><td colspan="5" class="kosong">Belum ada pola keliru berulang yang tercatat.</td></tr>'
    daftar_peta = "".join(
        f'<tr><td data-label="Tipe soal:">{html.escape(_nama_tipe_soal(p["template_id"]))}</td>'
        f'<td data-label="Topik:">{html.escape(_nama_topik(p["topik"]))}</td>'
        f'<td data-label="Berapa kali:" class="angka">{p["kali"]}</td>'
        f'<td data-label="Terakhir:">{_tanggal_pendek(p["terakhir"])}</td></tr>'
        for p in database.peta_materi_baru(kon, siswa_id)
    ) or '<tr><td colspan="4" class="kosong">Belum ada catatan pengenalan materi.</td></tr>'
    return (
        '<p class="laporan-catatan">Catatan mencakup seluruh sesi yang selesai dikirim, '
        'lintas tanggal dan variasi soal. Filter pada tampilan Sesi tidak berlaku di sini.</p>'
        '<section class="kartu catatan-latihan-laporan"><h2>Catatan pola pada semua latihan</h2>'
        '<p class="laporan-catatan">Rincian pola keliru yang sama dan muncul kembali. Jumlah K '
        'dan jenis kesalahan adalah catatan, bukan skor kelulusan atau penetapan fokus.</p>'
        '<table class="laporan-materi"><caption class="sr-only">Pola keliru yang berulang lintas sesi</caption>'
        '<thead><tr><th scope="col">Kekeliruan</th><th scope="col">Tipe soal</th><th scope="col">Topik</th>'
        '<th scope="col">Jumlah sesi</th><th scope="col">Rentang</th></tr></thead>'
        f'<tbody>{daftar_mis}</tbody></table></section>'
        '<section class="kartu catatan-latihan-laporan"><h2>Catatan pengenalan materi</h2>'
        '<p class="laporan-catatan">Ditandai belum pernah melihat atau masih bingung; '
        'perlu diperiksa, bukan kepastian materi belum diajarkan.</p>'
        '<table class="laporan-materi"><caption class="sr-only">Materi yang perlu cek pengenalan</caption>'
        '<thead><tr><th scope="col">Tipe soal</th><th scope="col">Topik</th>'
        '<th scope="col">Berapa kali</th><th scope="col">Terakhir</th></tr></thead>'
        f'<tbody>{daftar_peta}</tbody></table></section>'
    )


BAGIAN_LAPORAN = (
    ("ringkasan", "Ringkasan"),
    ("penguasaan", "Materi"),
    ("perjalanan", "Perjalanan"),
)

ANGKOR_LAPORAN = {
    "ringkasan": "progres",
    "penguasaan": "materi",
    "perjalanan": "perjalanan",
}


def konten_laporan(kon, siswa_id: int, query: str = "", section: str = "ringkasan"):
    """Isi + navigasi laporan tanpa bingkai; dipakai tab profil dan halaman lama."""
    parameter = parameter_laporan(query)
    # Tab Perkembangan memakai kunci 'bagian' agar tak bentrok section profil.
    # 'section' lama tetap dibaca sebagai fallback deep link/bookmark.
    section = parameter.get('bagian', '') or parameter.get('section', section)
    kompat_lama = section == 'riwayat'
    tampilan = parameter.get('tampilan', '')
    halaman = parameter.get('halaman', '1')
    if section not in dict(BAGIAN_LAPORAN) and not kompat_lama:
        section = "ringkasan"
    section_nav = 'ringkasan' if kompat_lama else section
    rincian = parameter.get('rincian', '')
    if tampilan == 'perjalanan':
        section_nav = 'perjalanan'
    elif tampilan in {'konteks', 'kriteria'}:
        section_nav = 'penguasaan'
    if tampilan == 'kriteria':
        rincian = 'kriteria'
    angkor = ANGKOR_LAPORAN.get(section_nav, "progres")
    navigasi = '<nav class="laporan-navigasi" aria-label="Bagian laporan">' + "".join(
        f'<a href="#{ANGKOR_LAPORAN[kode]}"'
        + (' aria-current="page"' if ANGKOR_LAPORAN[kode] == angkor else '')
        + f'>{label}</a>' for kode, label in BAGIAN_LAPORAN
    ) + '</nav>'
    # Renderer kompatibilitas lama tetap dapat dipanggil langsung oleh caller
    # internal. HTTP mengalihkannya sesudah guard sehingga ia tidak muncul lagi
    # sebagai navigasi global Perkembangan.
    if section == 'riwayat':
        opsi = [('sesi', 'Sesi'), ('mingguan', 'Mingguan'), ('catatan', 'Catatan')]
        if tampilan not in dict(opsi):
            tampilan = 'sesi'
        isi = pilihan('Tampilan riwayat', opsi, tampilan,
                      lambda k: url_laporan(siswa_id, section, tampilan=k))
        if tampilan == 'sesi':
            isi += _riwayat_latihan(
                kon, siswa_id, parameter.get('periode', 'semua'),
                parameter.get('topik', 'semua'), halaman,
            )
        elif tampilan == 'mingguan':
            isi += render_materi(
                statistik_laporan(kon, siswa_id, hari_wib()),
                _nama_tipe_soal, _tanggal_pendek,
            )
        else:
            isi += _catatan_latihan(kon, siswa_id) + _kartu_kamus()
    else:
        # Seluruh status dan denominator tetap memakai reducer/proyeksi existing.
        bukti = database.muat_bukti_siklus(kon, siswa_id)
        perjalanan = perjalanan_belajar(bukti, siswa_id)
        bukti_materi = lengkapi_bukti_materi(kon, bukti)
        peta_target = peta_penguasaan(bukti_materi, siswa_id)
        periode, mulai, akhir, judul_aktivitas = _periode_aktivitas(parameter)
        statistik = statistik_laporan(kon, siswa_id, mulai=mulai, akhir=akhir)
        materi = parameter.get('materi', '')
        if not materi and rincian in {'konteks', 'kriteria', 'catatan'} and peta_target.target:
            materi = peta_target.target[0].topik_id
        buka = tampilan if tampilan in {'konteks', 'pilot', 'tugas'} else ''
        isi = '<section class="laporan-bagian-st" id="progres" aria-label="Ringkasan perkembangan">'
        isi += '<h2>Ringkasan perkembangan</h2>'
        isi += '<div class="laporan-ringkasan-grid">'
        peta_ringkas = render_peta(peta_target, _tanggal_pendek, ringkas=True)
        # Bedakan id dari peta full di #materi agar id halaman unik.
        peta_ringkas = (peta_ringkas
            .replace('id="peta-penguasaan"', 'id="peta-ringkas"')
            .replace('id="judul-peta"', 'id="judul-peta-ringkas"')
            .replace('aria-labelledby="judul-peta"', 'aria-labelledby="judul-peta-ringkas"'))
        isi += peta_ringkas
        isi += render_aktivitas(
            statistik, _tanggal_pendek, judul=judul_aktivitas,
            kontrol=_kontrol_periode_aktivitas(siswa_id, periode, mulai, akhir),
        )
        isi += '</div>'
        if rincian == 'tren':
            isi += render_materi(
                statistik_laporan(kon, siswa_id, hari_wib()),
                _nama_tipe_soal, _tanggal_pendek,
            )
        isi += '</section>'
        isi += '<section class="laporan-bagian-st" id="materi" aria-label="Materi">'
        isi += render_peta(
            peta_target, _tanggal_pendek, siswa_id=siswa_id,
            materi=materi, status=parameter.get('status', 'semua'),
            halaman=halaman, bukti_konteks=bukti_materi, rincian=rincian,
        )
        if buka == 'konteks' or rincian == 'konteks':
            from context_report import render_konteks
            isi += ('<details class="rincian-ui-st" open><summary>Bukti per konteks latihan</summary>'
                    '<div class="laporan-lipatan-st">'
                    + render_konteks(bukti_materi, siswa_id, _tanggal_pendek, halaman=halaman)
                    + '</div></details>')
        if rincian == 'catatan':
            isi += _catatan_latihan(kon, siswa_id) + _kartu_kamus()
        if buka == 'tugas':
            isi += ('<details class="rincian-ui-st" open><summary>Belum selesai dikerjakan</summary>'
                    '<div class="laporan-lipatan-st">'
                    + render_tugas(tugas_belum_selesai(kon, siswa_id), siswa_id, _nama_topik, halaman)
                    + '</div></details>')
        isi += '</section>'
        isi += '<section class="laporan-bagian-st" id="perjalanan" aria-label="Perjalanan belajar">'
        isi += render_perjalanan(
            perjalanan, _nama_tipe_soal, _tanggal_pendek,
            siswa_id=siswa_id, halaman=halaman,
        )
        if buka == 'pilot':
            from skill_pilot_ui import laporan
            pilot = laporan(kon, siswa_id, hanya_relevan=True)
            if pilot:
                isi += ('<details class="rincian-ui-st" open><summary>Pendampingan orang tua</summary>'
                        '<div class="laporan-lipatan-st">' + pilot + '</div></details>')
        isi += '</section>'
    return navigasi + '<div id="konten-laporan">' + isi + '</div>'


def halaman_laporan(
    kon, siswa_id: int, pengguna: str = "", peran: str = "guru", section: str = "ringkasan",
    query: str = "",
) -> bytes:
    """Halaman laporan lama; kini membungkus konten yang sama dengan tab."""
    siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    if not siswa:
        return _halaman("Tidak ada", "<h1>Siswa tidak ditemukan</h1>")
    parameter = parameter_laporan(query)
    section = parameter.get('bagian', '') or parameter.get('section', section)
    isi = konten_laporan(kon, siswa_id, query=query, section=section)
    total_sesi = kon.execute(
        'SELECT COUNT(*) FROM sesi WHERE siswa_id=?', (siswa_id,)
    ).fetchone()[0]
    kembali = '/admin' if peran == 'admin' else '/guru'
    kelas_sekolah = None
    if siswa['pemilik']:
        from learning_profile import baca
        kelas_sekolah = baca(
            kon, siswa_id, pemilik=siswa['pemilik']
        ).kelas_sekolah
    return _halaman(
        f"Laporan {siswa['nama']}",
        f'<style>{profile_workspace.GAYA_PROFIL}{GAYA_LAPORAN}{GAYA_PETA}</style>'
        + profile_workspace.bagian_identitas(
            siswa, peran=peran, kelas_sekolah=kelas_sekolah,
            id_judul='judul-profil-laporan', kembali=kembali,
        )
        + '<nav class="profil-tabs-st" aria-label="Bagian profil anak">'
        + profile_workspace.navigasi_profil(siswa_id, total_sesi, 'perkembangan')
        + '</nav>' + isi,
        ident=(pengguna, peran) if pengguna else None,
        stitch=True,
        kelas_bungkus="laporan-lebar pendamping-editorial-st laporan-editorial-st profil-workspace-st",
        id_utama="judul-profil-laporan",
    )
