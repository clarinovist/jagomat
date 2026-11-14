"""Snapshot isi laporan orang tua: peta kemampuan ramah orang tua tanpa data internal.

Allowlist yang sempit disengaja: skor, persentase, kode diagnosis, malrule, ID, level,
kelas sekolah, dan nama pola soal tidak pernah masuk. Kalimat tahap/langkah/fokus berasal
dari tabel netral di sini, bukan dari alasan atau teks rencana internal guru.
Fungsi ini hanya membaca; tidak menulis bukti belajar.
"""
from __future__ import annotations

VERSI = 2

# Harus sama dengan learning_cycle_ui._LABEL_TAHAP (dijaga test).
LABEL_TAHAP = ("Kenali cara anak", "Pelajari", "Latihan", "Cek setelah jeda", "Cek kembali", "Lanjut")
URAIAN = (
    "Guru sedang mengenali cara anak mengerjakan soal.",
    "Anak mempelajari caranya lewat contoh dan arahan guru.",
    "Anak berlatih mengerjakan soal, dengan bantuan yang makin berkurang.",
    "Setelah jeda, guru mengecek apakah caranya masih diingat.",
    "Guru mengecek kembali setelah beberapa minggu.",
    "Anak siap melanjutkan ke materi berikutnya.",
)
LANGKAH = (
    "Anak mengerjakan beberapa soal pendek, lalu guru memeriksa caranya bersama anak.",
    "Bahas satu contoh bersama, lalu anak mencoba dengan bantuan guru.",
    "Coba sendiri beberapa soal pendek di rumah, lalu hasilnya diperiksa guru.",
    "Beri jeda beberapa hari, lalu anak mengerjakan soal pendek tanpa bantuan.",
    "Anak mengerjakan soal pendek lagi; guru melihat apakah caranya tetap terpakai.",
    "Guru memilih materi berikutnya bersama anak.",
)
LANGKAH_TANPA_TAHAP = "Guru akan menentukan langkah berikutnya bersama anak."

STATUS_PETA = {
    "kuat": "Sudah Kuat",
    "pelan": "Perlu Pelan",
    "fokus": "Fokus Konsep",
    "belum": "Belum Diuji",
}

STATUS_ALUR = {
    "aman": "Sudah lancar",
    "perlu": "Perlu pelan",
    "macet": "Perlu ditemani",
    "belum": "Belum diamati",
}

_FOKUS_TOPIK = {
    "berhitung-sekolah": (
        "Pada hitungan dasar dan bagian pecahan, anak terbantu jika menuliskan langkah pengelompokan atau arsirannya satu per satu.",
        "Luangkan waktu mendampingi dua sampai tiga soal perkalian atau pecahan pendek menggunakan benda nyata atau coretan sederhana di rumah.",
    ),
    "bilangan-dasar": (
        "Pada nilai tempat dan urutan bilangan, anak masih perlu memisahkan posisi satuan, puluhan, dan ratusan pelan-pelan.",
        "Minta anak membaca bilangan keras-keras lalu menunjuk angka ratusan, puluhan, dan satuannya sebelum menghitung.",
    ),
    "aritmetika-dasar": (
        "Pada operasi hitung bertahap, anak cenderung langsung menghitung dari kiri sebelum memeriksa tanda kurung atau perkalian.",
        "Biasakan anak melingkari tanda kurung atau operasi kali dan bagi terlebih dahulu sebelum mulai menghitung.",
    ),
    "pola-bilangan": (
        "Pada pola bilangan, anak masih perlu menuliskan selisih antar suku satu per satu sebelum menebak angka lanjutannya.",
        "Latih anak menulis selisih di antara setiap dua bilangan berurutan di kertas coretan sebelum mengisi titik-titik.",
    ),
    "geometri-datar": (
        "Pada bangun datar, anak masih sering tertukar antara langkah mencari keliling tepi dan luas bagian dalam.",
        "Minta anak menelusuri garis tepi bangun dengan jari untuk keliling, dan mengarsir bagian dalam untuk luas.",
    ),
    "geometri-ruang": (
        "Pada bangun ruang, anak masih perlu membedakan sisi alas, tinggi bangun, serta satuan kubik dengan satuan biasa.",
        "Ajak anak menggambar bentuk alas terlebih dahulu dan menandai tinggi bangunnya sebelum menghitung.",
    ),
    "statistika": (
        "Pada pembacaan data, anak masih perlu mengecek label sumbu atau skala gambar sebelum menyimpulkan jumlahnya.",
        "Minta anak menyebutkan dulu satu gambar mewakili berapa satuan sebelum membaca grafik.",
    ),
    "desimal-persen": (
        "Pada bilangan berkoma dan bagian perseratus, anak masih sering menyamakan langsung dengan bilangan bulat biasa.",
        "Biasakan anak mensejajarkan tanda koma ke bawah seperti menjumlahkan uang pecahan sebelum berhitung.",
    ),
    "perbandingan": (
        "Pada soal perbandingan, anak masih perlu memastikan kedua besaran memakai satuan yang sama sebelum dibandingkan.",
        "Ajak anak memberi label satuan pada kedua angka yang dibandingkan sebelum mencari nilainya.",
    ),
    "logika": (
        "Pada soal cerita logika, anak terbantu jika mencoret pilihan yang tidak cocok dengan petunjuk satu per satu.",
        "Dampingi anak membaca satu kalimat petunjuk pada satu waktu dan mencatat petunjuk singkat di samping soal.",
    ),
}

_LANGKAH_RUMAH_BAWAAN = (
    "Dampingi anak berlatih singkat di rumah dengan kertas coretan, dan minta anak menceritakan caranya memilih langkah sebelum melihat hasil akhir."
)


def _peta_template_ke_topik() -> dict[str, tuple[str, str]]:
    from topics import PAKET, _pastikan_dimuat

    _pastikan_dimuat()
    peta: dict[str, tuple[str, str]] = {}
    for topik_id, paket in PAKET.items():
        if topik_id == "campuran":
            continue
        for tid in paket.templates:
            peta[tid] = (topik_id, paket.nama)
    return peta


def _topik(kon, siswa_id, mulai, akhir):
    """Nama topik dari sesi selesai dan terkonfirmasi dalam periode, urut kemunculan."""
    from reports import _nama_topik

    baris = kon.execute(
        """SELECT s.topik FROM sesi s
           WHERE s.siswa_id = ? AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL
             AND s.tanggal BETWEEN ? AND ?
             AND EXISTS (SELECT 1 FROM konfirmasi_hasil kh WHERE kh.sesi_id = s.id)
           ORDER BY s.tanggal, s.id""",
        (siswa_id, mulai, akhir),
    ).fetchall()
    hasil = []
    for (topik,) in baris:
        nama = _nama_topik(topik)
        if nama not in hasil:
            hasil.append(nama)
    return hasil


def _tahap(kon, siswa_id):
    import database
    import learning_cycle_ui as ui
    from learning_cycle import rencana_berikutnya

    bukti = database.muat_bukti_siklus(kon, siswa_id)
    rencana = rencana_berikutnya(bukti, siswa_id)
    indeks = ui._tahap_tampil(rencana, bukti)
    return None if indeks is None else indeks


def _ringkas_topik_statistik(kon, siswa_id, mulai, akhir, daftar_topik):
    """Kumpulkan peta topik, alur berpikir, dan catatan awam dari bukti terkonfirmasi."""
    from reports import _nama_topik

    peta_tpl = _peta_template_ke_topik()
    baris = kon.execute(
        """SELECT s.topik, q.template_id, d.benar, d.kode_final
           FROM sesi s
           JOIN sesi_soal ss ON ss.sesi_id = s.id
           JOIN soal q ON q.id = ss.soal_id
           JOIN jawaban j ON j.sesi_soal_id = ss.id
           JOIN diagnosis d ON d.jawaban_id = j.id
           WHERE s.siswa_id = ? AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL
             AND s.tanggal BETWEEN ? AND ?
             AND EXISTS (SELECT 1 FROM konfirmasi_hasil kh WHERE kh.sesi_id = s.id)
           ORDER BY s.tanggal, s.id, ss.nomor""",
        (siswa_id, mulai, akhir),
    ).fetchall()

    per_topik: dict[str, dict] = {}
    kode_totals = {"B": 0, "K": 0, "H": 0, "E": 0, "T": 0, "N": 0}
    ada_cek_satuan = False
    kendala_satuan = False

    for sesi_topik, tpl_id, benar, kode_final in baris:
        kode = kode_final or ("B" if benar else "E")
        if kode in kode_totals:
            kode_totals[kode] += 1
        topik_id, nama_topik = peta_tpl.get(tpl_id, (sesi_topik, _nama_topik(sesi_topik)))
        entri = per_topik.setdefault(
            topik_id,
            {"nama": nama_topik, "b": 0, "k": 0, "h": 0, "e": 0, "nt": 0},
        )
        if benar or kode == "B":
            entri["b"] += 1
        elif kode == "K":
            entri["k"] += 1
        elif kode == "H":
            entri["h"] += 1
        elif kode == "E":
            entri["e"] += 1
        else:
            entri["nt"] += 1

        if topik_id in ("geometri-datar", "geometri-ruang", "desimal-persen", "perbandingan", "statistika"):
            ada_cek_satuan = True
            if not benar and kode in ("K", "E", "H"):
                kendala_satuan = True

    peta_topik: list[dict[str, str]] = []
    kuat: list[str] = []
    fokus: list[str] = []
    kandidat_rumah: list[str] = []

    if per_topik:
        for topik_id, st in per_topik.items():
            n_kh = st["k"] + st["h"]
            if n_kh >= 2 or (n_kh >= 1 and st["b"] == 0):
                status = "fokus"
            elif st["b"] > 0 and (n_kh > 0 or st["e"] > 0 or st["nt"] > 0):
                status = "pelan"
            elif st["b"] > 0:
                status = "kuat"
            else:
                status = "belum"
            peta_topik.append({"nama": st["nama"], "status": status, "label": STATUS_PETA[status]})
            if status == "kuat" and len(kuat) < 3:
                kuat.append(f"Pada {st['nama']}, anak sudah mengerjakan butir dasar dengan lancar dan mandiri.")
            elif status in ("fokus", "pelan"):
                pola, saran = _FOKUS_TOPIK.get(topik_id, ("", ""))
                if len(fokus) < 2:
                    if pola:
                        fokus.append(pola)
                    elif status == "fokus":
                        fokus.append(
                            f"Pada {st['nama']}, anak masih perlu memantapkan pemahaman dasarnya dengan contoh pelan."
                        )
                    else:
                        fokus.append(
                            f"Pada {st['nama']}, arah langkah anak sudah terlihat dan perlu dicek ulang agar lebih stabil."
                        )
                if saran:
                    kandidat_rumah.append(saran)
        peta_topik = peta_topik[:6]
    elif daftar_topik:
        for nama in daftar_topik[:6]:
            peta_topik.append({"nama": nama, "status": "belum", "label": STATUS_PETA["belum"]})

    # Bangun alur 4 langkah berpikir anak dalam bahasa netral.
    total_catatan = sum(kode_totals.values())
    if total_catatan == 0:
        alur = [
            {"kode": "baca", "langkah": "Baca Soal", "status": "belum", "label": STATUS_ALUR["belum"]},
            {"kode": "konsep", "langkah": "Pilih Konsep", "status": "belum", "label": STATUS_ALUR["belum"]},
            {"kode": "hitung", "langkah": "Hitung Angka", "status": "belum", "label": STATUS_ALUR["belum"]},
            {"kode": "cek", "langkah": "Cek Satuan", "status": "belum", "label": STATUS_ALUR["belum"]},
        ]
    else:
        st_baca = "macet" if kode_totals["N"] + kode_totals["T"] >= 2 else ("perlu" if kode_totals["N"] + kode_totals["T"] == 1 else "aman")
        st_konsep = "macet" if kode_totals["K"] >= 2 else ("perlu" if kode_totals["K"] == 1 else "aman")
        st_hitung = "macet" if kode_totals["H"] >= 2 else ("perlu" if kode_totals["H"] + kode_totals["E"] >= 1 else "aman")
        if ada_cek_satuan and kendala_satuan:
            st_cek = "perlu"
        elif kode_totals["K"] == 0 and kode_totals["H"] == 0 and kode_totals["E"] == 0 and kode_totals["B"] > 0:
            st_cek = "aman"
        else:
            st_cek = "perlu" if kode_totals["E"] >= 1 else "aman"

        alur = [
            {"kode": "baca", "langkah": "Baca Soal", "status": st_baca, "label": STATUS_ALUR[st_baca]},
            {"kode": "konsep", "langkah": "Pilih Konsep", "status": st_konsep, "label": STATUS_ALUR[st_konsep]},
            {"kode": "hitung", "langkah": "Hitung Angka", "status": st_hitung, "label": STATUS_ALUR[st_hitung]},
            {"kode": "cek", "langkah": "Cek Satuan", "status": st_cek, "label": STATUS_ALUR[st_cek]},
        ]

    if not peta_topik:
        cakupan = "Belum ada sesi terperiksa guru dalam rentang laporan ini."
        langkah_rumah = "Tunggu arahan latihan pertama dari guru sebelum memulai pendampingan di rumah."
    elif total_catatan == 0:
        cakupan = "Menampilkan daftar topik dari sesi selesai; pemeriksaan rinci masih diselesaikan guru."
        langkah_rumah = _LANGKAH_RUMAH_BAWAAN
    else:
        cakupan = "Ringkasan disusun dari sesi latihan yang sudah diperiksa langsung oleh guru pada rentang laporan ini."
        langkah_rumah = kandidat_rumah[0] if kandidat_rumah else _LANGKAH_RUMAH_BAWAAN

    if total_catatan > 0 and not kuat and kode_totals["B"] > 0:
        kuat.append("Anak sudah mampu menyelesaikan sebagian soal dengan langkah yang teratur.")
    if total_catatan > 0 and not fokus and kode_totals["N"] + kode_totals["T"] > 0:
        fokus.append("Beberapa butir masih dilewati; anak lebih nyaman jika membaca satu contoh lebih dulu bersama guru.")

    return peta_topik, alur, kuat[:3], fokus[:2], langkah_rumah, cakupan


def _susun_ringkasan_teruskan(topik, tahap, peta_topik, kuat, fokus, langkah_rumah, langkah):
    baris = []
    if topik:
        baris.append("Materi yang dilatih: " + ", ".join(topik[:4]) + ".")
    else:
        baris.append("Belum ada latihan terperiksa guru pada rentang laporan ini.")
    if tahap:
        baris.append(f"Tahap belajar saat ini: {tahap['label']}.")
    fokus_topik = [p["nama"] for p in peta_topik if p["status"] == "fokus"]
    kuat_topik = [p["nama"] for p in peta_topik if p["status"] == "kuat"]
    if kuat_topik:
        baris.append("Sudah kuat di: " + ", ".join(kuat_topik[:3]) + ".")
    elif kuat:
        baris.append(kuat[0])
    if fokus_topik:
        baris.append("Perlu ditemani di: " + ", ".join(fokus_topik[:2]) + ".")
    elif fokus:
        baris.append(fokus[0])
    baris.append("Langkah di rumah: " + (langkah_rumah or langkah))
    return "\n".join(baris)


def bangun(kon, siswa_id: int, mulai: str, akhir: str) -> dict:
    daftar_topik = _topik(kon, siswa_id, mulai, akhir)
    indeks = _tahap(kon, siswa_id)
    if indeks is None:
        tahap, langkah = None, LANGKAH_TANPA_TAHAP
    else:
        tahap = {"nomor": indeks + 1, "label": LABEL_TAHAP[indeks], "uraian": URAIAN[indeks]}
        langkah = LANGKAH[indeks]
    peta_topik, alur, kuat, fokus, langkah_rumah, cakupan = _ringkas_topik_statistik(
        kon, siswa_id, mulai, akhir, daftar_topik
    )
    ringkasan_teruskan = _susun_ringkasan_teruskan(
        daftar_topik, tahap, peta_topik, kuat, fokus, langkah_rumah, langkah
    )
    return {
        "versi": VERSI,
        "topik": daftar_topik,
        "tahap": tahap,
        "langkah": langkah,
        "peta_topik": peta_topik,
        "alur_berpikir": alur,
        "kuat": kuat,
        "fokus": fokus,
        "langkah_rumah": langkah_rumah,
        "cakupan": cakupan,
        "ringkasan_teruskan": ringkasan_teruskan,
    }
