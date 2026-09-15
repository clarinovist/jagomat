"""Dashboard aktivitas anak, resume rencana, dan rincian bukti yang dilipat."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import reports  # noqa: E402
import teacher_style  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    import auth

    berkas = tmp_path / "sandi.json"
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    auth.simpan_sandi("sandi-lama-panjang", "guru", berkas)
    d = tmp_path / "uji.db"
    database.siapkan(d)
    return d


def _sesi_dinilai(kon, sid, benar=8, jumlah=10, kode="K"):
    """Satu sesi berisi + diagnosis manual, tanpa lewat HTTP."""
    import teacher_pages

    sesi_id = database.buat_sesi(kon, sid, seed=jumlah * 100 + benar)
    isi = database.isi_sesi(kon, sesi_id)
    data = {}
    for i, b in enumerate(isi[:jumlah]):
        if i < benar:
            data[f"jwb_{b['sesi_soal_id']}"] = b["kunci"]
            data[f"cara_{b['sesi_soal_id']}"] = "coretan"
        else:
            data[f"jwb_{b['sesi_soal_id']}"] = "pasti salah"
            data[f"cara_{b['sesi_soal_id']}"] = "coretan"
            data[f"kode_{b['sesi_soal_id']}"] = kode
    teacher_pages.simpan_sesi(kon, sesi_id, data)
    database.tandai_selesai(kon, sesi_id)
    return sesi_id


def test_dashboard_menyebut_nama_dan_aktivitas(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Bima")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        _sesi_dinilai(kon, sid, benar=7, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()
    assert "Ringkasan untuk orang tua" not in h
    assert "Bima" in h
    assert "soal dikerjakan" in h
    assert "butir benar" in h and "butir salah" in h


def test_ringkasan_merayakan_tanpa_kata_teknis(db):
    """K=0: kalimat perayaan, tanpa kata yang menakuti (miskonsepsi).

    CSS global ikut ter-render di <style> (kata "diagnosis" ada di nama
    kelas), jadi yang dicek hanya ISI laporan — setelah </style>.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Rara")
        _sesi_dinilai(kon, sid, benar=10, jumlah=10)
        h = reports.halaman_laporan(kon, sid).decode()
    assert "Aktivitas 7 hari terakhir" in h
    isi = h.split("</style>", 1)[1]
    assert "miskonsepsi" not in isi.lower()
    assert "malrule" not in isi.lower()


def test_kamus_tanpa_jargon(db):
    """Enam kode dijelaskan bahasa sehari-hari, tanpa kata teknis.

    Seperti test di atas: CSS ikut ter-render, jadi cek isi saja.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Kamus")
        h = reports.halaman_laporan(kon, sid).decode()
    assert "Cara membaca laporan" in h
    for kata in ("salah konsep", "salah baca", "salah hitung",
                 "salah tulis", "belum pernah", "menebak"):
        assert kata in h.lower(), f"kamus kehilangan '{kata}'"
    # kamus & ringkasan bebas jargon teknis
    atas = h.split("</style>", 1)[1].split("Detail per sesi")[0]
    assert "malrule" not in atas.lower()
    assert "miskonsepsi" not in atas.lower()


def test_topik_tampil_nama_ramah(db):
    """Id teknis (pola-bilangan) tampil sebagai nama ramah (Pola Bilangan)."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Topik")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()
    assert "Pola Bilangan" in h


def test_kartu_perhatian_tidak_bilang_kuat_saat_ada_k(db):
    """Regresi dari screenshot: ringkasan bilang 6 K tapi kartu bilang
    'belum ada kekeliruan' — K manual tanpa malrule tak masuk miskonsepsi."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Kontradiksi")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()
    isi = h.split("</style>", 1)[1].split("Detail per sesi")[0]
    assert "Belum ada kekeliruan" not in isi
    assert "butir salah" in isi
    assert "persentase pemahaman" in isi


def test_tabel_teknis_dilipat_tapi_tetap_ada(db):
    """Guru tetap dapat tabelnya: markup utuh di dalam <details>."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lipat")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()
    assert "<details" in h
    assert '<th scope="col">Topik</th>' in h
    assert h.index("<details") < h.index('<th scope="col">Topik</th>')


def test_topik_tak_dikenal_tidak_500(db):
    """Sesi warisan ber-topik asing: laporan tetap 200, tampil apa adanya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Warisan")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        kon.execute("UPDATE sesi SET topik = ? WHERE id = ?", ("topik-hantu", sesi_id))
        database.tandai_selesai(kon, sesi_id)
        h = reports.halaman_laporan(kon, sid).decode()
    assert "Aktivitas 7 hari terakhir" in h
    assert "topik-hantu" in h


def test_nama_tipe_soal_menerjemahkan_id_internal():
    assert reports._nama_tipe_soal("benar_salah_pengandaian") == (
        "Pengandaian benar atau salah"
    )
    assert reports._nama_tipe_soal("luas_kotak_satuan") == (
        "Menghitung luas dengan kotak satuan"
    )
    assert reports._nama_tipe_soal("tipe_warisan_asing") == "Tipe warisan asing"


def test_tanggal_laporan_pendek_dan_aman_untuk_data_lama():
    assert reports._tanggal_pendek("2026-09-04") == (
        '<time class="tanggal-ringkas" datetime="2026-09-04">4 Sep 2026</time>'
    )
    assert reports._tanggal_pendek("tanggal lama") == (
        '<span class="tanggal-ringkas">tanggal lama</span>'
    )


def _beri_diagnosis(kon, sesi_id, indeks, kode, malrule_id=None, alasan=""):
    baris = database.isi_sesi(kon, sesi_id)[indeks]
    jawaban_id = database.simpan_jawaban(
        kon,
        baris["sesi_soal_id"],
        jawaban="0",
        belum_pernah=kode == "T",
    )
    database.simpan_diagnosis(
        kon,
        jawaban_id,
        benar=False,
        kode_usulan=kode,
        kode_final=kode,
        malrule_id=malrule_id,
        alasan=alasan,
    )
    database.tandai_selesai(kon, sesi_id)
    return baris["template_id"]


def test_laporan_memisahkan_prioritas_dari_materi_baru(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Aksi")
        sesi_k1 = database.buat_sesi(kon, sid, seed=77, topik="logika")
        sesi_k2 = database.buat_sesi(kon, sid, seed=79, topik="logika")
        sesi_t = database.buat_sesi(kon, sid, seed=78, topik="geometri-datar")
        tipe_k = _beri_diagnosis(
            kon,
            sesi_k1,
            0,
            "K",
            malrule_id="uji.pengandaian",
            alasan="menganggap kebalikan pernyataan selalu benar",
        )
        _beri_diagnosis(
            kon,
            sesi_k2,
            0,
            "K",
            malrule_id="uji.pengandaian",
            alasan="menganggap kebalikan pernyataan selalu benar",
        )
        tipe_t = _beri_diagnosis(kon, sesi_t, 0, "T")
        h = reports.halaman_laporan(kon, sid).decode()

    utama = h.split("Detail per sesi", 1)[0]
    assert "Perjalanan fokus belajar" in utama
    assert "Prioritas latihan" not in utama
    assert "Materi berikutnya untuk dikenalkan" not in utama
    assert "belum cukup bukti" in utama.lower()
    assert "Semua latihan" in utama
    assert tipe_k not in utama
    assert tipe_t not in utama
    assert "_" not in reports._nama_tipe_soal(tipe_k)
    assert "_" not in reports._nama_tipe_soal(tipe_t)


def test_prioritas_belum_menganggap_satu_sesi_sebagai_pola_berulang(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Belum Berulang")
        sesi_id = database.buat_sesi(kon, sid, seed=80, topik="logika")
        tipe = _beri_diagnosis(
            kon,
            sesi_id,
            0,
            "K",
            malrule_id="uji.sekali",
            alasan="baru muncul sekali",
        )
        h = reports.halaman_laporan(kon, sid).decode()

    utama = h.split('id="rencana-belajar-laporan"', 1)[1].split("Detail per sesi", 1)[0]
    assert reports._nama_tipe_soal(tipe) not in utama
    assert "belum cukup bukti" in utama.lower()
    assert "Mulai dari topik" not in utama


def test_label_singkatan_dan_alasan_tidak_dirusak(db):
    assert reports._nama_tipe_soal("fpb_kpk_hubungan") == "Hubungan FPB dan KPK"
    assert reports._rapikan_kalimat("menggunakan FPB & KPK.") == (
        "Menggunakan FPB & KPK."
    )


def test_ringkasan_memasangkan_tipe_dengan_topik_fokus(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Fokus Konsisten", "P5")
        # Logika dibuat lebih dulu agar berada di belakang urutan DESC.
        sesi_logika_1 = database.buat_sesi(kon, sid, seed=90, topik="logika")
        sesi_logika_2 = database.buat_sesi(kon, sid, seed=91, topik="logika")
        _beri_diagnosis(
            kon, sesi_logika_1, 0, "K", "uji.logika", "keliru logika"
        )
        _beri_diagnosis(
            kon, sesi_logika_2, 0, "K", "uji.logika", "keliru logika"
        )
        for seed in (92, 93, 94):
            sesi_geo = database.buat_sesi(
                kon, sid, seed=seed, level="P5", topik="geometri-datar"
            )
            _beri_diagnosis(
                kon, sesi_geo, 0, "K", "uji.geometri", "keliru geometri"
            )
        pola_geo = {
            reports._nama_tipe_soal(str(m["template_id"]))
            for m in database.miskonsepsi_berulang(kon, sid)
            if m["topik"] == "geometri-datar" and m["jumlah_sesi"] > 1
        }
        h = reports.halaman_laporan(kon, sid).decode()

    awal = h.index('<div class="kartu ringkasan-laporan">')
    akhir = h.index("</div>", awal) + 6
    ringkasan = h[awal:akhir]
    assert pola_geo
    assert not any(nama in ringkasan for nama in pola_geo)
    assert "bukti yang sudah dikonfirmasi" in ringkasan.lower()
    assert "belum cukup untuk menetapkan fokus" in ringkasan.lower()
    assert "Pengandaian benar atau salah" not in ringkasan


def test_hierarki_utama_mengutamakan_aktivitas_dan_persentase(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Hierarki")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()

    utama = h.split("Detail per sesi", 1)[0]
    assert "sesi dinilai" not in utama
    assert "soal dikerjakan" in utama
    assert "butir benar" in utama and "butir salah" in utama
    assert "jawaban benar dari yang dinilai" in utama
    assert "Persentase = benar" in utama
    assert "Cara membaca laporan" not in utama
    detail = h.split("Detail per sesi", 1)[1]
    assert '<details class="kartu cara-baca-laporan">' in detail
    assert "Cara membaca laporan" in detail
    assert "Arti nilai anak" not in utama


def test_laporan_memakai_kanvas_lebar_dan_kembali_ke_riwayat_anak(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Claudia")
        h = reports.halaman_laporan(kon, sid, pengguna="ortu").decode()

    isi = h.split("</style>", 1)[1]
    assert 'class="bungkus-st laporan-lebar pendamping-editorial-st laporan-editorial-st"' in h
    assert f'<a href="/anak/{sid}">&larr; Riwayat Claudia</a>' in isi
    assert "Laporan perkembangan Claudia" in isi
    assert "Laporan — Claudia" not in isi


def test_urutan_metrik_lalu_materi_lalu_resume_dan_bukti(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Urutan")
        _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        h = reports.halaman_laporan(kon, sid).decode()

    isi = h.split("</style>", 1)[1]
    assert isi.index('class="kartu-stat laporan-metrik"') < isi.index("Hasil dan tren per materi")
    assert isi.index("Hasil dan tren per materi") < isi.index("Lihat rencana belajar")
    assert isi.index("Lihat rencana belajar") < isi.index("Perjalanan fokus belajar")
    assert "Ringkasan untuk orang tua" not in isi


def _blok_css(css: str, selektor: str) -> str:
    cocok = re.search(
        r"^" + re.escape(selektor) + r"\s*\{(.*?)\}", css, re.S | re.M
    )
    assert cocok, f"selektor {selektor} tidak ditemukan"
    return cocok.group(1)


def test_css_laporan_lebar_hanya_di_desktop_dan_mobile_tetap_satu_kolom():
    css = teacher_style.GAYA_GURU
    mulai_desktop = css.index("@media (min-width: 64rem)")
    blok_desktop = css[mulai_desktop:css.index("@media (max-width: 46rem)", mulai_desktop)]
    blok_metrik_umum = _blok_css(css, ".kartu-stat")
    blok_admin = _blok_css(css, ".kartu-stat-admin")

    assert ".bungkus-st.laporan-lebar" in blok_desktop
    assert "max-width: 72rem" in blok_desktop
    assert ".bungkus-st.laporan-lebar .sesi-badan-st" in blok_desktop
    assert 'grid-template-areas: "ringkasan metrik"' in blok_desktop
    assert "grid-template-columns: repeat(3" in blok_metrik_umum
    assert "grid-template-columns: repeat(3" in blok_admin
    assert ".ringkasan-dashboard-laporan .kartu-stat" in css
    assert "align-items: stretch" in _blok_css(css, ".grid-tindakan-laporan")


def test_nama_siswa_di_laporan_di_escape(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Ayu <B> & "C"')
        h = reports.halaman_laporan(kon, sid, pengguna="ortu").decode()

    isi = h.split("</style>", 1)[1]
    assert 'Ayu &lt;B&gt; &amp; &quot;C&quot;' in isi
    assert 'Ayu <B> & "C"' not in isi


def test_detail_teknis_semantik_dan_legenda_dekat_tabel(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Teknis")
        sesi_id = _sesi_dinilai(kon, sid, benar=6, jumlah=10, kode="K")
        kon.execute(
            "UPDATE sesi SET tanggal = ? WHERE id = ?", ("2026-09-04", sesi_id)
        )
        h = reports.halaman_laporan(kon, sid).decode()

    detail = h.split("Detail per sesi", 1)[1]
    assert "K = keliru konsep" in detail
    assert '<th scope="col">Tanggal</th>' in detail
    assert "<thead>" in detail and "<tbody>" in detail
    assert '<time class="tanggal-ringkas" datetime="2026-09-04">4 Sep 2026</time>' in detail
