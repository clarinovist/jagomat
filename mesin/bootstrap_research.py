"""Rencana bootstrap publik; asumsi sintetis, tanpa state atau data keluarga."""
from __future__ import annotations

from html import escape
from math import ceil
from pathlib import Path

import brand
import design_tokens as T
from competitive_research import GAYA_RISET, _font_link
from business_research import GAYA_BISNIS

JALUR = "/riset/mulai"
JALUR_PDF = "/riset/mulai.pdf"
NAMA_PDF = "jagomat-rencana-bootstrap-2026.pdf"
VERSI_ISI = "2026-10-14-r2"
BERKAS_PDF = Path(__file__).resolve().parent / "publik" / NAMA_PDF
JUDUL = "How Do We Start? — Rencana Bootstrap Jagomat dari Nol"

# Seluruh input model adalah asumsi manajemen, bukan baseline atau tarif aktif.
ARPA = 35_000
CHURN = .05
MENIT_DUKUNGAN = 15
TARIF_DUKUNGAN = 60_000
PROVIDER = 3_000
PAYMENT = .008
REFUND = .02
OPS_VARIABEL = 1_000
KONVERSI_NILAI = .60
KONVERSI_BAYAR = .25
MENIT_ONBOARDING = 10
NILAI_FOUNDER = 9_600_000  # 96 jam nonsupport × Rp100.000; support dihitung variabel.
BARU = (0, 0, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28)

BIAYA_TETAP = (
    ("Domain (alokasi renewal)", (25_000, 25_000, 25_000)),
    ("Server", (200_000, 350_000, 600_000)),
    ("Backup dan monitoring", (125_000, 225_000, 375_000)),
    ("Software/tool kerja", (100_000, 250_000, 500_000)),
    ("Desain dan konten", (250_000, 1_000_000, 2_500_000)),
    ("Iklan: plafon, tidak wajib dihabiskan", (0, 500_000, 3_000_000)),
    ("Riset pengguna tanpa data pribadi", (200_000, 400_000, 1_000_000)),
    ("Legal, privacy, accounting", (150_000, 500_000, 1_000_000)),
    ("Reviewer pedagogi kontrak", (500_000, 1_000_000, 1_500_000)),
    ("Engineering kontrak", (0, 2_000_000, 4_000_000)),
    ("Growth/research kontrak", (0, 0, 2_000_000)),
    ("Penarikan tunjangan founder", (0, 3_000_000, 5_000_000)),
    ("Gaji staf tetap: belum direkrut", (0, 0, 0)),
)
SKENARIO = (
    {"nama": "Super-lean bootstrap", "awal": 3_000_000, "darurat": 3_000_000, "faktor": 1, "kapasitas": 150, "draw": 0},
    {"nama": "Lean professional", "awal": 8_000_000, "darurat": 6_000_000, "faktor": 3, "kapasitas": 500, "draw": 3_000_000},
    {"nama": "Accelerated validation", "awal": 15_000_000, "darurat": 12_000_000, "faktor": 7, "kapasitas": 1_200, "draw": 5_000_000},
)

def rupiah(nilai):
    """Format angka rupiah hanya pada penyajian; model tidak dibulatkan per bulan."""
    return "Rp" + f"{nilai:,.0f}".replace(",", ".")

def angka(nilai):
    return f"{nilai:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")

def tetap(indeks):
    return sum(nilai[indeks] for _, nilai in BIAYA_TETAP)

def kontribusi_unit(arpa=ARPA, menit=MENIT_DUKUNGAN, provider=PROVIDER):
    """Kontribusi per akun-bulan; tarif dukungan memperhitungkan tenaga pengganti."""
    return arpa * (1 - PAYMENT - REFUND) - provider - menit / 60 * TARIF_DUKUNGAN - OPS_VARIABEL

def cohort(indeks, churn=CHURN, arpa=ARPA):
    """Ilustrasi ekspektasi akun; pembayaran prorata dan churn merata sepanjang bulan."""
    aktif = 0.0
    hasil = []
    for bulan, dasar in enumerate(BARU, 1):
        baru = dasar * SKENARIO[indeks]["faktor"]
        akhir = aktif * (1 - churn) + baru
        rata = (aktif + akhir) / 2
        revenue = rata * arpa
        kontribusi = rata * kontribusi_unit(arpa)
        akses = (5 if bulan == 1 else 15) * SKENARIO[indeks]["faktor"] if bulan < 3 else ceil(baru / (KONVERSI_NILAI * KONVERSI_BAYAR))
        # Setiap akses gratis mendapat plafon onboarding; nonpembayar tidak
        # mendapat layanan berulang tanpa batas. Biaya ini bukan CAC kedua.
        onboarding = akses * MENIT_ONBOARDING / 60 * TARIF_DUKUNGAN
        kontribusi -= onboarding
        keluar = revenue - kontribusi + tetap(indeks)
        hasil.append({"bulan": bulan, "baru": baru, "awal": aktif, "akhir": akhir,
                      "rata": rata, "revenue": revenue, "mrr": akhir * arpa,
                      "kontribusi": kontribusi, "keluar": keluar, "neto": revenue - keluar,
                      "akses": akses, "onboarding": onboarding})
        aktif = akhir
    return hasil

def modal(indeks, bulan):
    """Cadangan tanpa pemasukan; biaya variabel cohort tetap didanai sebagai stress case."""
    s = SKENARIO[indeks]
    pengeluaran = sum(b["keluar"] for b in cohort(indeks)[:bulan])
    return s["awal"] + pengeluaran * 1.15 + s["darurat"]

def tabel(judul, kepala, baris, label="Rekomendasi / asumsi manajemen"):
    """Tabel native berlabel, scroll region dapat menerima fokus keyboard."""
    th = "".join(f'<th scope="col">{escape(k)}</th>' for k in kepala)
    tr = "".join("<tr>" + "".join(f"<td>{sel}</td>" for sel in row) + "</tr>" for row in baris)
    return (f'<div class="riset-tabel-bungkus" tabindex="0" role="region" aria-label="{escape(judul)}">'
            f"<table><caption>{escape(judul)} · {escape(label)}</caption><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>")

def bagian(kode, judul, isi):
    return f'<section class="riset-bagian" id="{kode}" aria-labelledby="judul-{kode}"><div class="riset-kepala"><h2 id="judul-{kode}">{judul}</h2></div>{isi}</section>'

def detail(judul, isi):
    return f'<details class="riset-detail" open><summary>{judul}</summary><div class="riset-detail-isi">{isi}</div></details>'

def rumus(isi):
    return f'<pre class="riset-rumus" tabindex="0" role="region" aria-label="Rumus perhitungan"><code>{escape(isi)}</code></pre>'

GAYA_MULAI = f"""
.riset-mulai h1 {{ max-width: 28ch; font-size: clamp(2.15rem, 4.4vw, 3.6rem); }}
.riset-mulai .riset-hero {{ min-height: auto; padding: {T.SP_7} 0; }}
.riset-mulai .riset-indeks {{ flex-wrap: wrap; }}
.riset-mulai .riset-indeks a {{ flex-shrink: 1; }}
.riset-mulai main, .riset-mulai section, .riset-mulai .riset-detail-isi {{ min-width: 0; }}
.riset-mulai p + p, .riset-mulai p + .riset-tabel-bungkus,
.riset-mulai .riset-tabel-bungkus + p {{ margin-top: {T.SP_4}; }}
.riset-mulai .riset-tabel-bungkus {{ margin-bottom: {T.SP_5}; max-width: 100%; }}
.riset-mulai table {{ min-width: 40rem; }}
.riset-mulai td {{ overflow-wrap: anywhere; }}
.riset-mulai .riset-rumus {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.riset-mulai .riset-rumus:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; }}
.riset-mulai .riset-sumber a, .riset-mulai .riset-footer a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.riset-mulai .riset-lewati {{ min-height: {T.TARGET_SENTUH}; }}
@media (max-width: {T.BATAS_HP}) {{
 .riset-mulai h1 {{ font-size: 2.15rem; }}
 .riset-mulai .riset-topbar-dalam {{ gap: {T.SP_2}; }}
 .riset-mulai .riset-detail-isi {{ padding: {T.SP_3}; }}
}}
@media print {{
 .riset-mulai table {{ min-width: 0; table-layout: fixed; font-size: 8pt; }}
 .riset-mulai th, .riset-mulai td {{ padding: 2mm; }}
 .riset-mulai .riset-tabel-bungkus {{ overflow: visible; border-radius: 0; }}
 .riset-mulai .riset-detail {{ break-inside: auto; overflow: visible; }}
 .riset-mulai .riset-detail > summary {{ display: block; min-height: 0; padding: 3mm 0; }}
 .riset-mulai .riset-detail > summary::after {{ content: ""; }}
 .riset-mulai .riset-detail-isi {{ display: block; padding: 0; }}
 .riset-mulai .riset-bagian {{ padding: 5mm 0; }}
 .riset-mulai .riset-bagian h2 {{ break-after: avoid; }}
 .riset-mulai tr {{ break-inside: avoid; }}
 .riset-mulai .riset-lewati {{ display: none; }}
 .riset-mulai a {{ min-height: 0 !important; }}
}}
"""

def biaya_html():
    rincian = tabel("Biaya tetap bulanan · Rupiah", ("Pos", "Super-lean", "Lean", "Accelerated"),
        [(nama, *(rupiah(x) + " (Asumsi)" for x in nilai)) for nama, nilai in BIAYA_TETAP])
    baris = []
    for i, s in enumerate(SKENARIO):
        c = cohort(i)
        rata_keluar = sum(x["keluar"] for x in c) / 12
        baris.append((s["nama"], rupiah(s["awal"]) + " one-off (Asumsi)",
            rupiah(tetap(i)) + " tetap; " + rupiah(rata_keluar) + " keluar rata-rata termasuk variabel (Hitung)",
            rupiah(modal(i, 6)) + " / " + rupiah(modal(i, 12)) + " (Hitung)",
            rupiah(rata_keluar + NILAI_FOUNDER - s["draw"]) + " economic/bulan (Hitung)",
            str(s["kapasitas"]) + " keluarga aktif; bersyarat tenaga tersedia (Asumsi)"))
    ringkas = tabel("Modal untuk 6 / 12 bulan tanpa penerimaan", ("Skenario", "Modal awal sekali", "Cash burn", "Dana 6 / 12 bulan", "Nilai ekonomi", "Kapasitas"), baris, "Hasil hitung dari asumsi, bukan saldo atau runway aktual")
    oneoff = tabel("One-off dan cadangan terpisah", ("Pos", "Super-lean", "Lean", "Accelerated"), (
        ("Legal/privacy/finance awal", "Rp1.500.000", "Rp4.000.000", "Rp6.000.000"),
        ("Demo/desain/review awal", "Rp1.000.000", "Rp2.500.000", "Rp5.000.000"),
        ("Cadangan timing domain/top-up/perangkat kecil", "Rp500.000", "Rp1.500.000", "Rp4.000.000"),
        ("Dana darurat di luar one-off", "Rp3.000.000", "Rp6.000.000", "Rp12.000.000"),
    ), "Asumsi manajemen; bukan quote")
    return ("<p><b>Asumsi manajemen:</b> sudah punya laptop dan internet dasar. Tidak menyewa kantor. Budget adalah envelope, bukan kewajiban menghabiskan. Honor harus mendapat quote; jika review wajib lebih mahal, kecilkan scope atau tambah dana, jangan melemahkan review.</p>" + ringkas + rincian + oneoff +
        "<p><b>Biaya variabel (Asumsi):</b> AI/provider Rp3.000 per akun-bulan; payment 0,8% revenue; refund/fraud 2%; variable ops Rp1.000/akun-bulan; support ongoing 15 menit × Rp60.000/jam = Rp15.000/akun-bulan. Tambahan onboarding setiap akses gratis 10 menit = Rp10.000, termasuk yang tidak membayar. Akses awal bulan 1/2 = 5/15 × faktor skenario; sejak bulan 3 akses = pembayar baru ÷ (60% first value × 25% bayar), dibulatkan ke atas. Model mengasumsikan yang tidak membayar berhenti mendapat layanan berulang; akses gratis tanpa batas membutuhkan budget lain.</p>"
        "<p><b>Contingency (Asumsi):</b> 15% dari seluruh pengeluaran operasional horizon ditahan sebagai kas, ditambah dana darurat pada tabel. Dana 6/12 bulan = one-off + 1,15 × pengeluaran 6/12 bulan + darurat, <em>tanpa mengandalkan satu rupiah revenue</em>. Ini kebutuhan pendanaan skenario, bukan runway aktual. Runway aktual = kas bebas ÷ burn neto ke depan; saldo founder tidak diperiksa.</p>"
        "<p><b>Cash versus economic:</b> seluruh jam support dinilai dan dicadangkan sebagai tenaga pengganti, meski awalnya founder yang membantu. Nilai kerja founder nonsupport 96 jam × Rp100.000 = Rp9,6 juta/bulan (Asumsi), di luar support yang sudah dibebankan variabel. Economic burn = cash burn − draw founder + Rp9,6 juta; draw bukan biaya kedua. Jika founder mengerjakan support, kurangi jam fungsi lain atau intake; jangan mengaku punya tambahan waktu gratis.</p>"
        "<p><b>Timing kas:</b> tabel bulanan memakai penyisihan domain/legal/tool sebagai pengeluaran ke kantong cadangan, bukan seluruhnya pembayaran vendor bulan itu. Domain dibayar tahunan dan AI mungkin top-up. One-off timing menjembatani pembelian awal; rekonsiliasi agar invoice tidak dihitung dua kali. Penerimaan diasumsikan settled dalam bulan yang sama; cadangan darurat menutup satu bulan keterlambatan skala awal, bukan jaminan skala besar. Jika settlement tertunda, kas akhir berkurang sebesar piutang belum cair.</p>"
        "<p><b>Pajak:</b> angka envelope mengandung ruang overhead, bukan tarif pajak. Pajak penghasilan, PPN merchant, status badan, upah minimum lokasi, THR/BPJS, cuti/perangkat dan gross-up perlu hitung sesuai keadaan sebelum penawaran/hire. Cadangkan employer load 25% di atas gaji sebagai asumsi awal, bukan substitusi kewajiban hukum. Belum memasukkan pembelian laptop besar/pendirian badan; minta quote lalu tambahkan ke modal. Super-lean draw nol memerlukan biaya hidup pribadi terpisah—bukan berarti hidup gratis.</p>"
        "<p><b>Risiko kapasitas:</b> super-lean sangat bergantung founder; lean memerlukan kontraktor andal; accelerated berisiko membakar uang sebelum nilai teruji. Kapasitas 150/500/1.200 adalah plafon layanan asumsi, bukan hasil load test server. Turunkan intake jika jam bantuan, SLA atau reliability tidak mencukupi. Tidak ada alasan otomatis berpindah ke skenario lebih mahal.</p>")


def ekonomi_html():
    definisi = tabel("Unit yang tidak boleh dicampur", ("Istilah", "Arti operasional"), (
        ("Akun keluarga / profil anak", "Unit pembayar = keluarga. Satu keluarga dapat memiliki beberapa profil; profil bukan pelanggan tambahan otomatis. Model tidak memasukkan add-on anak."),
        ("Baru / aktif akhir / rata-rata", "Baru = keluarga pertama kali membayar bulan itu; aktif akhir mengikuti churn; rata-rata dua titik mendekati akun-hari, bukan jumlah signup."),
        ("MRR / ARR run-rate", "MRR akhir = aktif akhir × ARPA; ARR run-rate = 12 × MRR akhir, bukan omzet yang sudah diterima."),
        ("Omzet tahun pertama", "Jumlah revenue 12 bulan. Di model ini revenue bruto sebelum allowance refund; tidak mengurangi refund sekali lagi dalam revenue."),
        ("Contribution / operating profit", "Contribution setelah payment/provider/refund/support/variable ops. Operating profit sebelum pajak = contribution − biaya operasi tetap (draw founder dilaporkan terpisah dari laba akuntansi)."),
        ("Valuasi", "Nilai perusahaan hasil negosiasi/metode dengan bukti; tidak dihitung dari ARR dengan multiple rekaan."),
    ), "Definisi model")
    formulas = rumus("""akun_aktif_t = akun_aktif_(t-1) × (1 − churn_t) + pelanggan_baru_t
aktif_rata-rata_t = (aktif_awal_t + aktif_akhir_t) / 2
revenue_bulan_t = aktif_rata-rata_t × ARPA_t
contribution = revenue − payment − provider − refund/fraud − support variabel − variable ops
CAC = seluruh biaya akuisisi / pelanggan baru berbayar
kas_akhir = kas_awal + penerimaan − pengeluaran
economic_burn = cash_burn − draw_founder + nilai_kerja_founder""")
    target = []
    for judul, mrr in (("MRR Rp10 juta", 10_000_000), ("MRR Rp50 juta", 50_000_000), ("ARR run-rate Rp1 miliar", 1_000_000_000 / 12)):
        n = ceil(mrr / ARPA)
        baru = ceil(n * CHURN)
        akses = ceil(baru / (KONVERSI_NILAI * KONVERSI_BAYAR))
        jam = (n * MENIT_DUKUNGAN + akses * MENIT_ONBOARDING) / 60
        target.append((judul, str(n) + " akun (Hitung)", str(baru) + " pembayar baru/bulan pengganti churn (Hitung)",
                       str(akses) + " akses eligible/bulan (Hitung)", angka(jam) + " jam support/bulan; ≈" + str(ceil(jam / 96)) + " tenaga setara 96 jam produktif (Hitung)"))
    be = []
    margin_steady = kontribusi_unit() - CHURN / (KONVERSI_NILAI * KONVERSI_BAYAR) * MENIT_ONBOARDING / 60 * TARIF_DUKUNGAN
    for i, s in enumerate(SKENARIO):
        n = ceil(tetap(i) / margin_steady)
        ne = ceil((tetap(i) - s["draw"] + NILAI_FOUNDER) / margin_steady)
        be.append((s["nama"], str(n), rupiah(n * ARPA), str(ne),
                   ("Kas melampaui plafon; " if n > s["kapasitas"] else "Kas dalam plafon; ") +
                   ("ekonomi melampaui plafon" if ne > s["kapasitas"] else "ekonomi dalam plafon")))
    return (definisi + formulas +
        "<p><b>Asumsi:</b> ARPA Rp35.000/bulan = mix 80% harga desain Rp29.000 + 20% Rp59.000; bulanan saja, tanpa add-on/promo/tahunan. Ini bukan harga baru atau penawaran aktif. Churn 5% bulanan; masuk/keluar merata sehingga rata-rata dua titik dipakai. Kas penerimaan = revenue pada bulan sama, prorata sebagai penyederhanaan model, bukan kontrak billing existing. Tahun penuh harus dihitung akun-hari dan settlement aktual setelah tersedia.</p>"
        "<p><b>Revenue pertama (Target manajemen):</b> 5 keluarga × Rp35.000 ARPA = Rp175.000 MRR (Hitung); bila mulai merata selama bulan pertama, revenue pendekatan Rp87.500. Target hari 60 boleh mundur: tabel konservatif baru menerima pembayaran mulai bulan 3, hanya jika gate siap. Kalau belum, jangan menarik uang.</p>" +
        tabel("Jalan menuju pendapatan berulang", ("Target aspirasi", "Keluarga aktif", "Pengganti churn saja", "Funnel minimum", "Kapasitas layanan"), target, "Hasil hitung dari asumsi; belum mencakup pertumbuhan tambahan") +
        "<p>Jalan praktis: buktikan 5 pembeli → batch 20 → pengulangan M1/M3 → kanal repeatable → kapasitas layanan. Untuk menambah 100 keluarga bersih dalam sebulan, pembayar baru harus 100 + pengganti churn (Hitung), bukan cukup 100 signup. MRR Rp50 juta dan ARR Rp1 miliar melampaui kapasitas skenario awal; model tenaga/ops wajib dihitung ulang sebelum scale, bukan tenggat tahun pertama.</p>" +
        tabel("Break-even keadaan stabil", ("Skenario", "Akun impas kas", "MRR impas kas", "Akun impas ekonomi", "Batas"), be, "Hitung; churn replacement dan onboarding termasuk; bukan impas saat tumbuh") +
        f"<p>Kontribusi ongoing per akun = {rupiah(kontribusi_unit())} (Hitung), margin {angka(kontribusi_unit()/ARPA*100)}%. Sesudah onboarding pengganti churn, tersisa {rupiah(margin_steady)} per akun stabil (Hitung). Biaya akuisisi iklan/konten/growth sudah ada di fixed envelope; CAC tidak dikurangkan lagi. Namun envelope itu belum terbukti menghasilkan cukup pembeli; break-even bersifat kondisional dan tidak layak dipakai jika kapasitas atau funnel gagal. Saat pertumbuhan cepat, onboarding tambahan memperlambat impas.</p>"
        "<p><b>CAC bukan nol untuk kanal organik:</b> hitung konten, iklan, referral fee bila kelak disetujui, alokasi software, tenaga growth serta jam akuisisi founder. Contoh asumsi Rp500 ribu cash + 10 jam founder × Rp100 ribu untuk 5 pembayar: CAC cash Rp100 ribu, economic Rp300 ribu (Hitung). Jam ini bagian dari 96 jam nonsupport founder, bukan tambahan biaya ekonomi kedua. Tidak ada pembayar → CAC tidak terdefinisi/belum terukur. Support onboarding dihitung delivery di model; jika dialokasikan ke CAC analitis, jangan dikurangkan dua kali dari profit.</p>")


def kas_html():
    isi = "<p><b>Seluruh baris berikut hasil hitung dari asumsi, bukan forecast.</b> Bulan 1 dimulai setelah keputusan memulai program, bukan kalender revenue aktual. Pembayar baru super-lean: 0, 0, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28. Lean = 3×; accelerated = 7×. Faktor bukan bukti marketing budget menghasilkan pembeli. Akses masuk yang dibutuhkan ditampilkan agar target tidak muncul dari udara.</p>"
    for i, s in enumerate(SKENARIO):
        kas = modal(i, 12) - s["awal"]
        rows = []
        for b in cohort(i):
            kas += b["neto"]
            rows.append((str(b["bulan"]), str(b["akses"]) + " / " + str(b["baru"]), angka(b["akhir"]),
                         angka(b["revenue"] / 1_000_000), angka(b["keluar"] / 1_000_000), angka(b["neto"] / 1_000_000), angka(kas / 1_000_000)))
        c = cohort(i)
        total_rev = sum(b["revenue"] for b in c)
        total_cont = sum(b["kontribusi"] for b in c)
        laba = total_cont - 12 * (tetap(i) - s["draw"])
        ringkas = (f"<p>Kas awal {rupiah(modal(i,12))}, one-off bulan 0 {rupiah(s['awal'])}. "
                   f"Omzet 12 bulan {rupiah(total_rev)}; contribution setelah onboarding {rupiah(total_cont)}; "
                   f"laba operasi pendekatan sebelum pajak/draw/one-off {rupiah(laba)}; "
                   f"MRR akhir {rupiah(c[-1]['mrr'])}; ARR run-rate {rupiah(c[-1]['mrr']*12)} (semua Hitung). "
                   "Pecahan akun merupakan nilai ekspektasi, bukan orang pecahan. Nilai uang dibulatkan hanya saat ditampilkan.</p>")
        isi += detail(s["nama"] + " · arus kas 12 bulan", ringkas + tabel("Kas bulanan " + s["nama"],
            ("Bulan", "Akses / baru bayar", "Aktif akhir", "Masuk", "Keluar", "Neto", "Kas akhir"), rows,
            "Hasil hitung; kolom uang dalam JUTA RUPIAH, dibulatkan 0,1 juta; cadangan belum dibelanjakan"))
    return isi + "<p><b>Stress case tanpa monetisasi:</b> dana 12 bulan di atas tetap menutup pengeluaran model plus buffer meskipun penerimaan nol; jangan mengganti pembeli gagal dengan layanan gratis tanpa batas. Hentikan intake pada cap eksperimen lalu revisi. Kas akhir tabel bukan laba karena masih memuat dana yang disetor founder. Pembayaran tahunan, pinjaman, capex besar, pembagian keuntungan dan pajak aktual belum dimodelkan; jangan menganggap dana cadangan boleh dibagikan.</p>"



def sumber_html():
    return """<p>Diakses 14 Oktober 2026 WIB (13 Oktober UTC). Hierarki: sumber resmi/primer → sumber publik dapat diaudit → benchmark Indonesia → proxy → asumsi manajemen → hasil hitung → rekomendasi. Label angka ada pada kalimat atau caption tabel, bukan warna saja.</p>
<ol class="riset-sumber">
<li id="s1"><a href="https://github.com/clarinovist/jagomat/blob/5b5378f9afe69798f9e847da5d6d0208601bbef2/docs/spec.md">S1 · Source publik Jagomat pada ref audit</a> — Fakta kontrak: akses awal nonkomersial, first value, batas data; paket rinci di docs/subscription-packages.md pada ref sama. Source bukan bukti transaksi live.</li>
<li id="s2"><a href="https://www.domainesia.com/harga-domain/">S2 · DomaiNesia, harga domain</a> — Fakta sumber: .id daftar Rp219.000, renewal Rp249.000/tahun sebelum PPN 11% yang dicantumkan halaman. Renewal Rp276.390/tahun (Hitung). Budget Rp25.000/bulan (Asumsi pembulatan), bukan promo tahun pertama.</li>
<li id="s3"><a href="https://www.biznetgio.com/product/neo-lite">S3 · Biznet GIO NEO Lite</a> — Fakta sumber: 1 vCPU/2 GB Rp80.000/bulan; 2 vCPU/4 GB Rp139.000/bulan sebelum pajak. Bukan konfigurasi live Jagomat dan bukan benchmark kapasitas.</li>
<li id="s4"><a href="https://www.biznetgio.com/pricelist">S4 · Biznet GIO pricelist</a> — Fakta sumber: object storage single-region Rp1.000/GB/bulan; snapshot Rp1.500/GB/bulan, sebelum pajak. Storage bukan backup/restore lengkap. Anggaran backup+monitoring pada laporan adalah Asumsi untuk salinan dan operasi, bukan quote.</li>
<li id="s5"><a href="https://midtrans.com/id/biaya">S5 · Midtrans biaya</a> — Fakta sumber: QRIS 0,7%, VA Rp4.000/transaksi, kartu 2,9% + Rp2.000; pajak tidak termasuk kecuali catatan QRIS/GoPay/ShopeePay. Ada tarif berbeda untuk produk digital. Klasifikasi, settlement, refund dan biaya pencairan Jagomat harus dikonfirmasi. Model 0,8% adalah Asumsi QRIS-dominan, bukan tarif merchant yang sudah disetujui. Pada pembayaran Rp35.000, VA saja 11,4% sebelum pajak (Hitung); model akan terlalu optimistis jika VA dominan.</li>
<li id="s6"><a href="https://api-docs.deepseek.com/quick_start/pricing/">S6 · DeepSeek dokumentasi harga</a> — Fakta sumber snapshot: flash peak per sejuta token input cache-miss US$0,30; output US$1,20. Contoh 1.000 panggilan ×2.000 input +1.000 output = US$1,80; kurs Rp17.000/USD (Asumsi, bukan kurs pasar) → Rp30.600 (Hitung), sebelum pajak/retry/spread. Bukan provider/mutu runtime yang dijamin. Envelope Rp3.000/akun-bulan adalah Asumsi penggunaan, bukan hasil harga token saja.</li>
<li id="s7"><a href="https://id.jobstreet.com/id/career-advice/role/customer-service-representative-csr/salary">S7 · Jobstreet gaji CS</a> — Proxy Indonesia: JSON-LD iklan full-time, P25–P75 Rp3,07–5,39 juta/bulan, median Rp4,051 juta. Bukan gaji legal minimum atau quote CS pendidikan. Manfaat/senioritas/kota tidak seragam; metadata dapat berbeda dari ringkasan SEO.</li>
<li id="s8"><a href="https://id.jobstreet.com/id/career-advice/role/software-engineer/salary">S8 · Jobstreet software engineer</a> — Proxy: P25–P75 Rp7–10 juta, median Rp8,5 juta/bulan pada metadata snapshot; bukan full-stack senior/security atau tarif kontrak. Honor spesialis di roadmap seluruhnya Asumsi manajemen.</li>
<li id="s9"><a href="https://id.jobstreet.com/id/career-advice/role/content-writer/salary">S9 · Jobstreet content writer</a> — Proxy P25–P75 Rp3,56–6,04 juta/bulan; bukan penulis soal/reviewer pedagogi. Data platform iklan bukan payroll nasional.</li>
<li id="s10"><a href="https://id.jobstreet.com/id/career-advice/role/accountant/salary">S10 · Jobstreet akuntan</a> — Proxy P25–P75 Rp4,75–7,5 juta/bulan; bukan quote pembukuan mikro.</li>
<li id="s11"><a href="https://id.jobstreet.com/id/career-advice/role/legal-officer/salary">S11 · Jobstreet legal officer</a> — Proxy P25–P75 Rp5,5–7,5 juta/bulan; bukan fee praktisi privasi anak. Belum cukup benchmark yang cocok untuk pedagogi OSN/privacy; minta quote scoped.</li>
<li id="s12"><a href="https://www.bi.go.id/QRIS/default.aspx">S12 · Bank Indonesia QRIS</a> — Keterbatasan: akses otomatis reset saat riset; tidak digunakan untuk mengklaim MDR pendidikan/usaha mikro khusus. Konfirmasi regulator/acquirer sebelum memakai tarif preferensial.</li>
<li><a href="https://jagomat.id/riset">Business case Jagomat</a> dan <a href="https://jagomat.id/riset/persaingan-bimbel-2026">audit persaingan</a> — laporan terdahulu tetap tersedia; ARPA Rp32 ribu di business case adalah skenario berbeda, bukan baseline. Laporan bootstrap memakai Rp35 ribu beserta mix eksplisit agar unitnya konsisten.</li>
</ol><p>Analisis independen. Tidak ada wawancara baru, data anak/keluarga, DB produksi, backup atau credential yang menjadi bahan riset ini. Dua scout dan satu kritik independen dipakai untuk memeriksa kontrak/sumber dan blind spot. JEV hanya stress-test semantik pilihan model, urutan hiring dan kejelasan rencana; bukan responden, survei, bukti pasar atau izin ekspor data. Perhitungan diuji deterministik; kesiapan pasar belum terbukti.</p>"""


def halaman() -> bytes:
    """Satu renderer HTML untuk web dan cetak A4; tanpa lookup pengguna."""
    import bootstrap_content as C

    indeks = (("senin", "Senin pagi"), ("strategi", "Strategi"), ("action-plan", "Action plan"),
              ("funnel", "Funnel"), ("biaya", "Biaya"), ("sdm", "SDM"),
              ("economics", "Economics"), ("kas", "Kas 12 bulan"), ("asumsi", "Asumsi"),
              ("dashboard", "Dashboard"), ("risiko", "Kill/scale"), ("sumber", "Sumber"))
    nav = "".join(f'<a href="#{k}">{v}</a>' for k, v in indeks)
    senin = '<ol class="riset-urutan">' + "".join(f"<li><p>{x}</p></li>" for x in C.SENIN) + "</ol>"
    aksi = "<p><b>Semua target, biaya dan ambang berikut adalah rekomendasi/asumsi manajemen, bukan baseline.</b> n/N berarti jumlah yang mencapai tahap dibagi semua yang berhak dinilai. Sampel kecil adalah sinyal keputusan, bukan kepastian statistik. Kalender boleh bergeser bila gate belum siap.</p>"
    for t in C.TAHAP:
        nama, tujuan, pekerjaan, pic, deliver, biaya, kpi, counter, dep, risiko, keluar = t
        aksi += detail(nama + " · " + tujuan, tabel("Rencana " + nama, ("Dimensi", "Tindakan / bukti"), (
            ("Pekerjaan konkret", pekerjaan), ("Penanggung jawab", pic), ("Deliverable", deliver),
            ("Biaya", biaya), ("KPI", kpi), ("Counter-metric", counter), ("Dependency", dep),
            ("Risiko", risiko), ("Exit criteria: lanjut/revisi/berhenti", keluar))))
    sdm = "<p><b>Hiring sequence (Rekomendasi):</b> founder merangkap product, engineering, discovery, konten, partnership dan analytics. Reviewer pedagogi kontrak serta finance/privacy scoped lebih dulu. CS paruh waktu setelah beban terbukti. Full-time pertama kandidatnya CS/operasi, bukan VP Growth; jika engineering justru bottleneck kritis, gunakan kontrak terbatas dahulu. Tidak merekrut sales besar, data scientist, HR internal atau tim multi-jenjang.</p>"
    for p in C.PERAN:
        sdm += detail(p[0], tabel("Peran " + p[0], ("Dimensi", "Rencana"), tuple(zip(
            ("Tanggung jawab / skill", "Bentuk kerja / biaya", "Kapan mulai / hiring trigger", "Kapasitas / KPI adil", "Risiko dini / terlambat"), p[1:]))))
    sdm += tabel("RACI sederhana", ("Keputusan", "Founder", "Pedagogi", "CS", "Finance/legal"), C.RACI)
    sdm += "<p>A = pemilik keputusan akhir; R = pelaksana; C = dimintai masukan; I = diberi tahu. Bila kontraktor belum tersedia, founder menanggung tugas, bukan menghapus kontrol spesialis.</p>"
    sdm += detail("Ritme mingguan dan jam founder", "<p><b>Asumsi 30 jam/minggu:</b> 8 engineering/product, 6 discovery/growth, 4 konten/mitra, 6 support/onboarding, 3 cash/privacy/pedagogi, 3 review/buffer. Ini 120 jam per empat minggu; bulan panjang butuh buffer. Nilai ekonomi Rp9,6 juta untuk 96 jam nonsupport per empat minggu; jam support aktual sudah di biaya variabel dan tidak dihitung ulang. Jika support naik, potong intake atau kontrak, bukan bekerja dua shift.</p><p>Senin 30 menit: satu bottleneck dan budget; Rabu 20 menit: kualitas/insiden; Jumat 45 menit: cohort, kas, support dan keputusan lanjut/revisi/pause. Tidak perlu daily meeting jika founder tunggal. Simpan satu halaman keputusan anonim, bukan laporan rapat panjang.</p><p><b>Founder berhenti menjadi support utama</b> saat &gt;8 jam/minggu selama 3 minggu atau SLA terlewat berulang, dengan SOP, quote dan runway cukup. Tetap ikut minimal dua observasi sukarela per minggu (Target) agar tidak kehilangan suara pengguna. Full-time: &gt;80 jam/bulan dua bulan, tugas stabil, runway ≥6 bulan setelah gaji+25% allowance employer cost (Asumsi). Jangan merekrut bila hasilnya hanya memindahkan friksi yang bisa dihapus.</p>")
    sdm += detail("Hiring scorecard dan tiga brief pertama", "<p><b>Rubrik sebelum wawancara (Rekomendasi):</b> 40% uji kerja sintetis, 25% keselamatan/privacy dan eskalasi, 20% komunikasi awam, 15% reliabilitas/biaya. Lulus ≥75/100 dan tidak boleh gagal guard privacy/kebenaran; angka adalah ambang manajemen, bukan tes psikometrik. Uji kerja singkat berbayar, scope dan acceptance tertulis, kontrak akses minimum, tanpa data anak asli. Quote harus memuat pajak, jam, revisi, tenggat dan stop clause.</p>" + "".join(f"<h3>{a}</h3><p>{b}</p>" for a,b in C.BRIEF))
    asumsi = tabel("Assumption register", ("Asumsi", "Nilai awal / status", "Cara membantah / pemilik"), (
        ("ARPA dan mix", "Rp35.000; 80:20 harga desain bulanan; belum WTP", "Pembayaran sukarela/retensi; founder"),
        ("Churn", "5%/bulan; stress 2–10%; belum baseline", "Cohort pembayar matang, bukan login; founder"),
        ("Funnel", "60% first value ×25% bayar; belum diukur", "n/N akses eligible, penawaran eligible, umur cohort; growth"),
        ("Support", "10 menit onboarding/akses +15 menit ongoing/aktif", "Time log agregat termasuk gagal bayar; CS"),
        ("Provider/payment/refund", "Rp3.000/akun;0,8%;2% allowance", "Usage sintetis, quote merchant dan settlement; engineering/finance"),
        ("Kapasitas dan faktor akuisisi", "150/500/1.200 aktif; faktor baru 1/3/7", "Jam layanan dan funnel, bukan spesifikasi VPS; founder"),
        ("Modal dan tenaga", "One-off, envelope dan honor belum quote", "Quote serta biaya hidup founder; finance"),
        ("Monetisasi", "Tabel mulai M3 setelah gate; jika tidak siap penerimaan nol", "Harga/terms, payment, refund, tax, support siap; founder"),
    ), "Asumsi manajemen; tiap nilai dapat direvisi, tidak mengubah kontrak produk")
    konten = C.RINGKASAN
    konten += bagian("status", "Yang ada, yang live, dan yang belum terbukti", tabel("Batas klaim produk", ("Jenis bukti", "Status / batas"), C.STATUS, "Fakta kontrak, observasi teknis dan hipotesis dibedakan"))
    konten += bagian("senin", "Apa yang dikerjakan Senin pagi?", senin)
    konten += bagian("strategi", "Pilihan strategi bootstrap", tabel("Tiga model, tiga keputusan", ("Model", "Trade-off", "Eksperimen", "Bukti yang mengubah keputusan"), C.STRATEGI))
    konten += bagian("action-plan", "Action plan: dari 7 hari sampai 12 bulan", aksi)
    konten += bagian("funnel", "Funnel penjualan pertama, bukan funnel vanity", tabel("Tahap operasional", ("Tahap", "Kegiatan", "Bukti keluar", "Pemilik / guard"), C.FUNNEL) + "<p><b>Payment gate wajib:</b> harga/entitlement disetujui, merchant/category/fee jelas, terms/cancel/refund terbaca, sandbox sukses/gagal/duplikat teruji, settlement direkonsiliasi, kas refund tersedia, owner dan SLA support siap. Tidak melakukan pembelian produksi untuk riset. Laporan ini tidak mengaktifkan paket, masa coba, promo, checkout atau pembayaran.</p>")
    konten += bagian("biaya", "Biaya dan runway: tiga cara membatasi risiko", biaya_html())
    konten += bagian("sdm", "SDM: organisasi nol, rekrut ketika bottleneck nyata", sdm)
    konten += bagian("economics", "Revenue dan break-even: hitung keluarga, bukan profil anak", ekonomi_html())
    konten += bagian("kas", "Budget dan arus kas 12 bulan", kas_html())
    konten += bagian("asumsi", "Formula, assumption register dan sensitivitas", asumsi + sensitivitas_html())
    konten += bagian("dashboard", "Dashboard keputusan founder", "<p><b>Satu north-star:</b> keluarga yang mencapai first value lalu menjalankan satu langkah lanjutan sesuai kontrak. Saat data komposit belum ada, tulis ‘belum diukur’, bukan mengganti dengan signup. Empat guardrail: keselamatan/privacy, kebenaran/koreksi, beban orang tua/support, dan kas/contribution. Semua metrik pendukung di bawah cukup diperiksa mingguan.</p>" + tabel("Panel mingguan", ("Metrik", "Definisi / denominator", "Keputusan"), C.METRIK) + "<p><b>Rencana pengukuran, bukan fitur live:</b> first value komposit belum diinstrumentasi. Awal gunakan observasi sukarela terpisah dengan hasil agregat tanpa nama, kontak, akun, jawaban, rekaman atau screenshot anak. Jam 48 dimulai saat akses awal diterima keluarga yang siap mencoba, bukan saat founder memilih responden sukses. Cohort yang belum matang dipisahkan. Retention lintas bulan memerlukan protokol consent/retensi dan linkage minimal yang disetujui; tanpa itu laporkan self-report agregat dengan keterbatasannya, jangan mengarang retention terverifikasi. Event baru tidak ditambahkan dalam rilis ini.</p>")
    risiko = "<p><b>Kill bukan menyerah pada satu angka kecil.</b> Pause = hentikan akuisisi/penawaran terkait sambil melindungi pengguna. Revisi = ubah satu hipotesis dan ulang batch terbatas. Scale = tambah kapasitas bertahap setelah dua batch memenuhi gate nilai, ekonomi dan keselamatan. Tutup eksperimen/segmen bila dua siklus perbaikan tetap gagal dan runway &lt;3 bulan (Ambang manajemen); selesaikan kewajiban refund/layanan, bukan hilang begitu saja.</p>"
    for r in C.RISIKO:
        risiko += detail(r[0], tabel("Pre-mortem " + r[0], ("Dimensi", "Aturan"), tuple(zip(("Indikator dini", "Dampak", "Mitigasi", "Pemilik", "Kill/pause rule", "Recovery plan"), r[1:]))))
    konten += bagian("risiko", "Pre-mortem, kill rules dan scale rules", risiko)
    konten += bagian("sumber", "Sumber, tanggal akses dan keterbatasan", sumber_html())
    meta = brand.tag_kepala({"judul": JUDUL, "deskripsi": "Rencana bootstrap Jagomat: tindakan, biaya, SDM, unit economics dan batas keputusan dari nol.", "jalur": JALUR})
    return f'''<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul(f'Bootstrap Jagomat 2026 · {VERSI_ISI}')}</title>{meta}{_font_link()}
<link rel="canonical" href="https://jagomat.id{JALUR}"><style>{GAYA_RISET}{GAYA_BISNIS}{GAYA_MULAI}</style></head>
<body class="riset-mulai"><a class="riset-lewati" href="#konten-riset">Lewati ke laporan</a>
<header class="riset-topbar"><div class="riset-topbar-dalam"><a class="riset-brand" href="/riset">{brand.mark("topbar")}<span>Riset</span></a><nav class="riset-nav" aria-label="Aksi laporan"><a class="riset-unduh" href="{JALUR_PDF}">Unduh PDF</a></nav></div></header>
<main id="konten-riset"><div class="riset-bungkus"><section class="riset-hero"><div class="riset-hero-copy"><p class="riset-alis">Jagomat · Bootstrap playbook · 2026</p><h1>{JUDUL}</h1><p class="riset-dek">Dari produk yang sudah tersedia menuju bisnis yang layak dijalankan—satu eksperimen, satu batas biaya, satu keputusan pada satu waktu.</p><div class="riset-meta"><span class="riset-chip">Revisi isi · {VERSI_ISI}</span><span class="riset-chip">14 Oktober 2026</span><span class="riset-chip">Bukan forecast atau penawaran</span></div></div></section><nav class="riset-indeks" aria-label="Bagian laporan bootstrap">{nav}</nav>{konten}</div></main>
<footer class="riset-footer"><div class="riset-bungkus"><a href="/riset">Kembali ke pusat riset</a><p>Jagomat · Review dan konfirmasi manusia tetap utama.</p></div></footer></body></html>'''.encode("utf-8")


def kirim_pdf(penangan) -> None:
    """Kirim hanya artefak publik tetap; gagal tanpa membocorkan path lokal."""
    try:
        isi = BERKAS_PDF.read_bytes()
    except OSError:
        penangan._kirim(b"<h1>Laporan belum tersedia</h1><p>Coba lagi beberapa saat.</p>", 503)
        return
    penangan.send_response(200)
    penangan.send_header("Content-Type", "application/pdf")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Content-Disposition", f'attachment; filename="{NAMA_PDF}"')
    penangan.send_header("Cache-Control", "public, max-age=3600")
    penangan.send_header("X-Content-Type-Options", "nosniff")
    penangan.end_headers()
    penangan.wfile.write(isi)


def sensitivitas_html():
    rows = []
    for n in (5, 15, 30):
        rows.append(("Support", str(n) + " menit/akun-bulan (Asumsi)", rupiah(kontribusi_unit(menit=n)) + " kontribusi ongoing (Hitung)", "30 menit menyisakan margin hampir nol; jangan scale tanpa biaya akuisisi"))
    for a in (29_000, 35_000, 44_000):
        rows.append(("ARPA / mix paket", rupiah(a) + " (Asumsi)", rupiah(kontribusi_unit(arpa=a)) + " kontribusi (Hitung)", "Mix 100:0 / 80:20 / 50:50 harga desain 29:59; WTP belum terbukti"))
    for p in (1_000, 3_000, 10_000):
        rows.append(("AI/provider", rupiah(p) + "/akun-bulan (Asumsi)", rupiah(kontribusi_unit(provider=p)) + " kontribusi (Hitung)", "Kuota, panjang prompt, retry, model dan kurs menentukan biaya"))
    for c in (.02, .05, .10):
        akhir = cohort(0, churn=c)[-1]["akhir"]
        rows.append(("Churn", angka(c*100) + "%/bulan (Asumsi)", angka(akhir) + " akun akhir M12 (Hitung)", "Akuisisi tetap; ini bukan retensi cohort aktual"))
    for cac in (30_000, 100_000, 300_000):
        rows.append(("CAC", rupiah(cac) + " (Asumsi)", angka(cac / kontribusi_unit()) + " bulan payback ongoing (Hitung)", "Optimistis: belum churn/onboarding/tax; bukan LTV terukur"))
    for nilai, bayar in ((.4,.15),(.6,.25),(.8,.4)):
        akses = 100
        pembeli = akses * nilai * bayar
        rows.append(("Conversion first value × pembayaran", f"{nilai:.0%} × {bayar:.0%} (Asumsi)", angka(pembeli) + " pembayar /100 akses (Hitung)", "100 akses ×10 menit = Rp1 juta onboarding; beban nonpembayar tetap nyata"))
    return (tabel("Sensitivitas satu variabel pada satu waktu", ("Penggerak", "Input", "Dampak", "Keputusan"), rows, "Asumsi dan hasil hitung; bukan confidence interval") +
        "<p><b>Mix tahunan (Asumsi alternatif, tidak dipakai tabel kas):</b> 80:20 pada harga desain Rp290/590 ribu setahun = ARPA diakui Rp29.167/bulan (Hitung), bukan Rp35 ribu. Uang tahunan diterima di depan, kewajiban layanan/refund tetap ada; ARR dan kas tidak boleh disamakan. Uji mix bersama churn, bukan memilih hanya skenario yang terlihat untung.</p>"
        "<p><b>Interaksi terburuk:</b> ARPA Rp29 ribu, AI Rp10 ribu dan support 30 menit menghasilkan kontribusi −Rp12.812/akun-bulan (Hitung). Meningkatkan pelanggan memperbesar kerugian. Menunda monetisasi mengurangi kas sebesar seluruh penerimaan yang hilang, sementara biaya review/riset tetap berjalan. Ini alasan gate, bukan ramalan kegagalan.</p>")
