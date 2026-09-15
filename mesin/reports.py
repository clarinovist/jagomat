"""Halaman laporan per anak + diagnosa jawaban.

Dipecah dari web.py (refactor 31 Aug 2026) — fungsi pindah utuh, perilaku
identik. Frame halaman diimpor dari teacher_pages.
"""

from __future__ import annotations

import html
from datetime import datetime

import database
from learning_journey import perjalanan_belajar
from report_dashboard import GAYA_LAPORAN, render_aktivitas, render_materi, render_resume
from report_metrics import hari_wib, statistik_laporan, tugas_belum_selesai
from mastery_report import GAYA_PETA, peta_penguasaan, render_peta
from mastery_evidence import lengkapi_bukti_materi
import design_tokens as T
from diagnosis import diagnosa
from generator import LEVEL_BAWAAN
from template_labels import nama_tipe_soal as _nama_tipe_soal
from templates import label_kelas
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
# Dipakai panel "Cara membaca laporan" — bebas jargon teknis (malrule,
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


def _kartu_kamus() -> str:
    baris = "".join(
        f'<li><span class="dot {"kuat" if kode == "BENAR" else ("salah" if kode == "K" else "lemah")}"></span>'
        f"<span><b>{html.escape(sebutan)}</b> — {html.escape(arti)}</span></li>"
        for kode, sebutan, arti in KAMUS_ORTU
    )
    return (
        f'<details class="kartu cara-baca-laporan"><summary><h2>'
        f"Cara membaca laporan</h2>"
        f'<span class="sub">Arti istilah penilaian</span></summary>'
        f'<p class="sub">Tiap soal dinilai dengan salah satu sebutan ini:</p>'
        f'<ul class="diagnosis-lis">{baris}</ul></details>'
    )


def halaman_laporan(
    kon, siswa_id: int, pengguna: str = "", peran: str = "guru"
) -> bytes:
    siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    if not siswa:
        return _halaman("Tidak ada", "<h1>Siswa tidak ditemukan</h1>")

    ring = database.ringkasan(kon, siswa_id)
    hari = hari_wib()
    statistik = statistik_laporan(kon, siswa_id, hari)

    mis_semua = database.miskonsepsi_berulang(kon, siswa_id)
    # Statistik mentah hanya untuk rincian semua latihan, bukan status fokus.
    mis = [m for m in mis_semua if m["jumlah_sesi"] > 1]
    # Clock rekomendasi harus sama dengan profil/POST orkestrator existing.
    # WIB khusus batas statistik; jangan majukan jadwal hanya pada laporan.
    bukti = database.muat_bukti_siklus(kon, siswa_id)
    perjalanan = perjalanan_belajar(bukti, siswa_id)
    peta_target = peta_penguasaan(lengkapi_bukti_materi(kon, bukti), siswa_id)
    resume = render_resume(
        perjalanan, tugas_belum_selesai(kon, siswa_id), siswa_id,
        _nama_tipe_soal, _nama_topik, _tanggal_pendek,
    )

    tren = "".join(
        f'<tr><td data-label="Sesi"><a href="/sesi/{r["sesi_id"]}">#{r["sesi_id"]}</a></td>'
        f'<td data-label="Tanggal">{_tanggal_pendek(r["tanggal"])}</td>'
        f'<td class="tipe" data-label="Kelas">{html.escape(label_kelas(str(_ambil(r, "level", LEVEL_BAWAAN))))}</td>'
        f'<td data-label="Topik">{html.escape(_nama_topik(_ambil(r, "topik", TOPIK_BAWAAN) or TOPIK_BAWAAN))}</td>'
        f'<td class="angka" data-label="Benar">{r["benar"] or 0}/{r["jumlah_soal"]}</td>'
        f'<td class="angka" data-label="K"><b>{r["k"] or 0}</b></td>'
        f'<td class="angka" data-label="B">{r["b"] or 0}</td><td class="angka" data-label="H">{r["h"] or 0}</td>'
        f'<td class="angka" data-label="E">{r["e"] or 0}</td><td class="angka" data-label="T">{r["t"] or 0}</td>'
        f'<td class="angka" data-label="N">{r["n"] or 0}</td></tr>'
        for r in ring
    ) or '<tr><td colspan="11" class="kosong">belum ada sesi dinilai</td></tr>'

    daftar_mis = "".join(
        f'<tr><td>{html.escape(m["alasan"] or "Cara yang dipakai belum tepat")}</td>'
        f'<td>{html.escape(_nama_tipe_soal(m["template_id"]))}</td>'
        f'<td>{html.escape(_nama_topik(m["topik"]))}</td>'
        f'<td class="angka">{m["jumlah_sesi"]}</td>'
        f'<td>{_tanggal_pendek(m["pertama"])} &rarr; '
        f'{_tanggal_pendek(m["terakhir"])}</td></tr>'
        for m in mis
    ) or ('<tr><td colspan="5" class="kosong">belum ada kekeliruan '
          "yang bertahan</td></tr>")

    peta = database.peta_materi_baru(kon, siswa_id)
    daftar_peta = "".join(
        f'<tr><td>{html.escape(_nama_tipe_soal(p["template_id"]))}</td>'
        f'<td>{html.escape(_nama_topik(p["topik"]))}</td>'
        f'<td class="angka">{p["kali"]}</td>'
        f'<td>{_tanggal_pendek(p["terakhir"])}</td></tr>'
        for p in peta
    ) or '<tr><td colspan="4" class="kosong">tidak ada</td></tr>'

    nama_siswa = html.escape(siswa["nama"])
    return _halaman(
        f"Laporan {siswa['nama']}",
        f'<style>{GAYA_LAPORAN}{GAYA_PETA}</style>'
        f'<div class="jejak"><a href="/anak/{siswa_id}">&larr; Riwayat '
        f"{nama_siswa}</a></div>"
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">CATATAN PERKEMBANGAN</p>'
        f'<h1 id="judul-laporan">Laporan perkembangan {nama_siswa}</h1></header>'
        f'{render_peta(peta_target, _tanggal_pendek)}'
        f'{resume}'
        f'{render_aktivitas(statistik, _tanggal_pendek)}'
        '<details class="kartu"><summary>Rincian hasil latihan mingguan</summary>'
        f'{render_materi(statistik, _nama_tipe_soal, _tanggal_pendek)}</details>'
        f'<details class="kartu detail-teknis-laporan"><summary><h2>'
        f"Detail per sesi (teknis)</h2>"
        f'<span class="sub">Rincian untuk guru</span></summary>'
        f'<p class="sub">Rincian semua latihan: jumlah <b>K</b> dan jenis '
        f"kesalahan adalah catatan, bukan skor kelulusan atau penetapan fokus. "
        f"Kolom Benar di tabel sesi memakai pembanding soal tersedia, termasuk "
        f"yang belum dijawab; bukan penyebut persentase dashboard.</p>"
        f'<p class="legenda-teknis"><b>K = keliru konsep</b> · '
        f'B = salah baca · H = salah hitung · E = salah tulis akhir · '
        f"T = perlu cek pengenalan · N = menebak</p>"
        f'<div class="tabel-wrap tabel-tren"><h3>Tren per sesi</h3><table>'
        f'<caption class="sr-only">Rincian hasil dan jenis kekeliruan setiap sesi</caption>'
        f'<thead><tr><th scope="col">Sesi</th><th scope="col">Tanggal</th>'
        f'<th scope="col">Kelas</th><th scope="col">Topik</th>'
        f'<th scope="col">Benar</th><th scope="col">K</th>'
        f'<th scope="col">B</th><th scope="col">H</th>'
        f'<th scope="col">E</th><th scope="col">T</th>'
        f'<th scope="col">N</th></tr></thead><tbody>{tren}</tbody></table></div>'
        f'<div class="tabel-wrap"><h3>Catatan pola pada semua latihan</h3>'
        f'<p class="sub">Rincian pola keliru yang sama dan muncul kembali.</p>'
        f'<table><caption class="sr-only">Pola keliru yang berulang lintas sesi</caption>'
        f'<thead><tr><th scope="col">Kekeliruan</th>'
        f'<th scope="col">Tipe soal</th><th scope="col">Topik</th>'
        f'<th scope="col">Jumlah sesi</th><th scope="col">Rentang</th>'
        f'</tr></thead><tbody>{daftar_mis}</tbody></table></div>'
        f'<div class="tabel-wrap"><h3>Catatan pengenalan materi</h3>'
        f'<p class="sub">Ditandai belum pernah melihat atau masih bingung; '
        f'perlu diperiksa, bukan kepastian materi belum diajarkan.</p>'
        f'<table><caption class="sr-only">Materi yang perlu cek pengenalan</caption>'
        f'<thead><tr><th scope="col">Tipe soal</th>'
        f'<th scope="col">Topik</th><th scope="col">Berapa kali</th>'
        f'<th scope="col">Terakhir</th></tr></thead>'
        f'<tbody>{daftar_peta}</tbody></table></div>{_kartu_kamus()}</details>',
        ident=(pengguna, peran) if pengguna else None,
        stitch=True,
        kelas_bungkus="laporan-lebar pendamping-editorial-st laporan-editorial-st",
        id_utama="judul-laporan",
    )
