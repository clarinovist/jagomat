"""Layout halaman /anak/<id> — regresi CSS (audit 3 Sep 2026).

Halaman ini dirender ke Chrome headless lalu geometri tiap elemen diukur di
viewport 1440px dan 390px. Tiga bug ditemukan; test di sini menguncinya
supaya tidak kembali saat CSS dirapikan lagi.

B1  `.strip-sesi` terdefinisi DUA KALI di GAYA_STITCH. Definisi lama (strip
    satu baris) membawa `align-items: flex-end`; definisi S6 mengubah arah
    jadi kolom tapi tidak me-reset align-items, sehingga setiap anak yang
    tidak selebar penuh menempel ke tepi KANAN. Terukur di 1440px: kolom
    "Jumlah Soal" di x=866 dan "Mode Sesi" di x=744, sementara tombol di
    x=383 — form terlihat miring.

B2  Media query layar sempit memakai selector `.st-kartu-baris > span`.
    Kartu sesi di halaman GURU anaknya <div>, jadi aturan itu tidak pernah
    kena; di 390px kolom pertama menyusut ke 76px dan judul sesi terlipat
    tiga baris.

B3  `.daftar-anak` hanya ada di GAYA_GURU, yang TIDAK dimuat oleh
    `_halaman_stitch`. Grid+gap hilang dan kartu sesi dempet — jarak
    terukur 1px, bukan 1.2rem.

Test membaca STRING CSS, bukan browser: sama seperti test gaya lain di repo
ini, supaya cepat dan tanpa dependensi luar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import student_pages  # noqa: E402
import teacher_pages  # noqa: E402
from style_stitch import GAYA_STITCH  # noqa: E402


def _blok(css: str, selektor: str) -> str:
    """Isi blok CSS untuk `selektor` sebagai deklarasi berdiri sendiri.

    Diikat ke awal baris: tanpa itu `.strip-sesi` juga cocok dengan
    `.panel-latihan-st > .strip-sesi` yang kebetulan muncul lebih dulu di
    file, dan test memeriksa blok yang salah.
    """
    cocok = re.search(
        r"^" + re.escape(selektor) + r"\s*\{(.*?)\}", css, re.S | re.M
    )
    assert cocok, f"selektor {selektor} tidak ada di GAYA_STITCH"
    return _tanpa_komentar(cocok.group(1))


def _tanpa_komentar(css: str) -> str:
    """Buang komentar /* ... */.

    Komentar di file ini MENJELASKAN bug (menyebut `align-items:flex-end`),
    jadi assert yang polos ikut menangkap penjelasannya dan gagal padahal
    aturannya sudah benar.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _tanpa_gaya(html: str) -> str:
    """Buang isi <style>…</style>.

    Halaman meng-inline SELURUH GAYA_STITCH, jadi memeriksa nama kelas di
    HTML mentah selalu menemukannya di CSS — bukan bukti bahwa MARKUP-nya
    memakai kelas itu.
    """
    return re.sub(r"<style>.*?</style>", "", html, flags=re.S)


def _jumlah_definisi(css: str, selektor: str) -> int:
    """Berapa kali `selektor` dideklarasikan sendirian di awal baris."""
    return len(re.findall(r"^" + re.escape(selektor) + r"\s*\{", css, re.M))


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def anak(db):
    """Satu anak dengan dua sesi — cukup untuk merender halaman utuh."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Claudia", pemilik="ortu", tingkat="P3")
        database.buat_sesi(kon, sid, seed=11, topik="statistika")
        database.buat_sesi(kon, sid, seed=17, topik="geometri-datar")
    return db, sid


def _render_anak(db, siswa_id, section='latihan') -> str:
    with database.buka(db) as kon:
        baris = kon.execute(
            "SELECT * FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        return teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu", query='section=' + section
        ).decode()


# ── B1 — strip-sesi: satu definisi, rata kiri ─────────────────────────


def test_strip_sesi_hanya_satu_definisi():
    """Dua blok `.strip-sesi` = properti blok lama bocor ke blok kolom."""
    assert _jumlah_definisi(GAYA_STITCH, ".strip-sesi") == 1


def test_mode_pilih_dan_mode_opsi_hanya_satu_definisi():
    """Sisa refactor S6 yang sama: keduanya sempat ganda."""
    assert _jumlah_definisi(GAYA_STITCH, ".mode-pilih") == 1
    assert _jumlah_definisi(GAYA_STITCH, ".mode-opsi") == 1


def test_strip_sesi_tidak_rata_kanan():
    """`align-items: flex-end` pada container KOLOM melempar semua anak
    ke tepi kanan — inilah penyebab form terlihat miring."""
    assert "flex-end" not in _blok(GAYA_STITCH, ".strip-sesi")


def test_strip_sesi_menegakkan_align_items_stretch():
    """Ditulis eksplisit meski itu nilai default: yang dijaga di sini
    adalah TIDAK adanya warisan flex-end kalau blok lama muncul lagi."""
    blok = _blok(GAYA_STITCH, ".strip-sesi")
    assert "flex-direction: column" in blok
    assert "align-items: stretch" in blok


def test_select_dalam_strip_dibatasi_lebarnya():
    """Tanpa batas, dropdown melar selebar kartu (673px) di desktop."""
    assert ".strip-sesi select.st-input" in GAYA_STITCH


# ── B2 — media query kartu mengenai div, bukan hanya span ─────────────


def test_media_query_kartu_tidak_hanya_menyasar_span():
    """Kartu guru memakai <div>, kartu murid memakai <span>. Selector
    `> span` membuat aturan HP hanya berlaku untuk kartu murid."""
    aturan = _tanpa_komentar(GAYA_STITCH)
    assert ".st-kartu-baris > *" in aturan
    assert ".st-kartu-baris > span" not in aturan


def test_aturan_baris_penuh_dibatasi_ke_kartu_guru():
    """Anak pertama kartu MURID adalah ikon bulat 2.5rem yang harus tetap
    `flex: none`. Aturan "ambil baris penuh" karena itu tidak boleh
    digeneralkan ke .st-kartu-baris, melainkan pakai kelas sendiri."""
    assert ".kartu-sesi-guru" in GAYA_STITCH


def test_kartu_guru_memakai_kelas_penanda_di_markup(anak):
    """CSS tanpa markup yang memakainya = aturan mati."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert "kartu-sesi-guru" in markup


def test_kartu_murid_tidak_memakai_kelas_guru(anak):
    """Kelas penanda tidak boleh bocor ke kartu murid — beda struktur."""
    db, sid = anak
    with database.buka(db) as kon:
        html = student_pages.halaman_daftar_sesi_baru(
            kon, sid, nama="Claudia"
        ).decode()
    markup = _tanpa_gaya(html)
    assert "st-kartu-baris" in markup, "fixture harus benar-benar punya kartu"
    assert "kartu-sesi-guru" not in markup


# ── B3 — daftar-anak butuh gaya di halaman Stitch ─────────────────────


def test_daftar_anak_punya_gaya_di_stitch():
    """_halaman_stitch tidak memuat GAYA_GURU, jadi grid+gap harus ada di
    GAYA_STITCH — kalau tidak, kartu sesi dempet 1px."""
    blok = _blok(GAYA_STITCH, ".daftar-anak")
    assert "grid" in blok
    assert "gap" in blok


# ── Guard anti-regresi ────────────────────────────────────────────────


def test_timer_form_mengandalkan_state_css_bukan_javascript(anak):
    """Panel mengikuti radio/checkbox agar relasi pilihan terlihat konsisten."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert 'class="pengaturan-timer"' in markup
    assert 'class="rincian-timer"' in markup
    assert "querySelectorAll('input[name=\"mode\"]')" not in markup

    aturan = _tanpa_komentar(GAYA_STITCH)
    assert ".strip-sesi:has(input[name=mode][value=drill]:checked) .pengaturan-timer" in aturan
    assert ".pengaturan-timer:has(.timer-toggle input:checked) .rincian-timer" in aturan


def test_halaman_anak_tetap_utuh(anak):
    db, sid = anak
    html = _render_anak(db, sid)
    assert "Sesi #" in html
    assert "Buat sesi baru" in html
    assert "Buat latihan gabungan" in html
    assert "Claudia" in html


# ── Fase B — layout desktop dua kolom ─────────────────────────────────
#
# Di 1440px halaman ini tinggi 1698px dengan konten hanya 51% viewport:
# history sesi dan tiga form bertumpuk vertikal, sisa ~350px kosong di
# kiri-kanan. Di >= 64rem keduanya dipisah jadi dua kolom.
#
# Palang yang dijaga: HP tidak boleh ikut berubah. Grid dan pelebar hanya
# boleh hidup di dalam media query.


def test_halaman_anak_punya_bungkus_ruang_kerja_scoped(anak):
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert 'profil-workspace-st' in markup
    assert 'class="profil-formulaire-st"' in markup
    assert 'class="profil-champs-st"' in markup
    assert 'class="profil-assistant-st"' in markup


def test_form_sebelum_pendamping_dan_tugas_ringkas(anak):
    """HP mengikuti urutan form, bantuan kontekstual, lalu tugas ringkas."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert markup.index('profil-champs-st') < markup.index('profil-assistant-st')
    assert markup.index('Buat sesi baru') < markup.index('profil-taches-st')


def test_grid_dua_kolom_hanya_di_desktop():
    """Di bawah breakpoint halaman harus tetap satu kolom seperti semula."""
    aturan = _tanpa_komentar(GAYA_STITCH)
    assert "grid-template-columns" in aturan, "grid belum ada"
    # blok .anak-grid di luar media query tidak boleh punya dua kolom
    assert "grid-template-columns" not in _blok(aturan, ".anak-grid")


def test_pelebar_konten_hanya_untuk_kelas_lebar():
    """Halaman lain tidak boleh ikut melebar — pelebar diikat ke kelas."""
    assert ".bungkus-st.lebar" in _tanpa_komentar(GAYA_STITCH)


def test_topbar_halaman_anak_mengikuti_kanvas_lebar():
    """Topbar halaman anak harus selebar kanvas dua kolom di desktop."""
    aturan = _tanpa_komentar(GAYA_STITCH)
    cocok = re.search(
        r"^\s+\.bungkus-st\.lebar > \.st-topbar\s*\{(.*?)\}",
        aturan,
        re.S | re.M,
    )
    assert cocok, "aturan topbar lebar tidak ditemukan di media query desktop"
    assert "max-width: none" in cocok.group(1)


def test_halaman_anak_kembali_ke_semua_anak(anak):
    """Breadcrumb singkat tetap menunjukkan tujuan kembali dengan jelas."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert '<a href="/guru">&larr; Semua anak</a>' in markup
    assert "&larr; Daftar anak" not in markup


@pytest.mark.parametrize("privat", [False, True])
def test_kepala_riwayat_memuat_tautan_laporan_dengan_svg_inline(anak, privat):
    """Ikon laporan tetap nyata tanpa bergantung pada font di host privat."""
    db, sid = anak
    with database.buka(db) as kon:
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (sid,)).fetchone()
        markup = _tanpa_gaya(teacher_pages.halaman_anak(
            kon, siswa, peran="guru", pengguna="ortu", privat=privat, query='section=riwayat',
        ).decode())
    kepala = markup[markup.index('class="kepala-riwayat-st"'):]
    kepala = kepala[:kepala.index("</div>")]
    assert "Riwayat latihan" in kepala
    assert f'<a class="tautan-laporan-st" href="/laporan/{sid}">' in kepala
    assert "Lihat laporan perkembangan" in kepala
    assert "History latihan" not in markup
    assert "trending_up" not in kepala
    assert '<svg class="ikon-laporan-st"' in kepala
    assert 'aria-hidden="true"' in kepala
    assert 'focusable="false"' in kepala
    assert 'stroke="currentColor"' in kepala


def test_kartu_sesi_mengutamakan_topik_dan_metadata_ramah(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Claudia", pemilik="ortu", tingkat="P4")
        sesi_id = database.buat_sesi_gabungan(
            kon,
            sid,
            seed=23,
            topik_ids=["logika", "geometri-datar", "statistika"],
            level="P3",
            jumlah_soal=10,
        )
        kon.execute(
            "UPDATE sesi SET tanggal = '2026-09-04' WHERE id = ?", (sesi_id,)
        )

    markup = _tanpa_gaya(_render_anak(db, sid))

    assert '<a class="judul-sesi-st"' in markup
    assert "Gabungan 3 topik" in markup
    assert "Logika &amp; Penalaran &middot; Geometri Datar &middot; Statistika" in markup
    assert "gabungan:logika,geometri-datar,statistika" not in markup
    assert '<time datetime="2026-09-04">4 Sep 2026</time>' in markup
    assert "Profil P3" in markup
    assert "Mode Diagnosa" in markup
    assert f"Sesi #{sesi_id}" in markup


def test_kartu_belum_dikerjakan_tidak_memamerkan_statistik_kosong(anak):
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert "Belum Dikerjakan" in markup
    assert "Terisi 0/" not in markup
    assert "Benar &mdash;" not in markup
    assert "Waktu &mdash;" not in markup


def test_status_sesi_mengikuti_pengiriman_final_bukan_jumlah_isian():
    tersimpan_penuh = {"direview": None, "selesai": None, "terisi": 3, "n": 3}
    terkirim_sebagian = {
        "direview": None, "selesai": "2026-09-05 10:00:00", "terisi": 1, "n": 3,
    }
    terkirim_kosong = {
        "direview": None, "selesai": "2026-09-05 10:00:00", "terisi": 0, "n": 3,
    }

    assert "Sedang Dikerjakan" in teacher_pages._badge_review_status(tersimpan_penuh)
    assert "Belum ditinjau" in teacher_pages._badge_review_status(terkirim_sebagian)
    assert "Belum ditinjau" in teacher_pages._badge_review_status(terkirim_kosong)


@pytest.mark.parametrize("keadaan", ["baru", "sebagian", "selesai", "direview", "warisan"])
def test_badge_riwayat_mendahulukan_pembatalan(db, keadaan):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Demo Batal", pemilik="ortu")
        sesi = database.buat_sesi(kon, siswa, seed=27)
        if keadaan == "sebagian":
            soal = kon.execute("SELECT id FROM sesi_soal WHERE sesi_id=? LIMIT 1", (sesi,)).fetchone()[0]
            kon.execute("INSERT INTO jawaban (sesi_soal_id, jawaban) VALUES (?, '7')", (soal,))
        kon.execute("UPDATE sesi SET selesai=?, direview=? WHERE id=?", (
            "2026-09-09 12:00:00" if keadaan in ("selesai", "direview") else None,
            "2026-09-09 12:01:00" if keadaan in ("direview", "warisan") else None,
            sesi,
        ))
        database.batalkan_sesi(kon, sesi, "Pembatalan sintetis")
        sebelum = tuple(kon.iterdump())
    markup = _tanpa_gaya(_render_anak(db, siswa, 'riwayat'))
    kartu = re.search(r'<tr data-sesi-id=".*?</tr>', markup, re.S).group()
    assert ">Dibatalkan</span>" in kartu
    for status in ("Belum Dikerjakan", "Sedang Dikerjakan", "Belum ditinjau", "Hasil dikonfirmasi", "belum dikonfirmasi"):
        assert status not in kartu
    assert f'href="/sesi/{sesi}"' in kartu
    assert "data-bagikan-url" not in kartu
    with database.buka(db) as kon:
        assert tuple(kon.iterdump()) == sebelum
        baris = kon.execute("SELECT * FROM sesi WHERE id=?", (sesi,)).fetchone()
        assert ">Dibatalkan</span>" in teacher_pages._badge_review_status(baris)


def test_tanggal_kartu_kanonis_aman_dan_tidak_terpotong():
    assert teacher_pages._tanggal_ringkas("2026-9-4") == (
        '<time datetime="2026-09-04">4 Sep 2026</time>'
    )
    assert teacher_pages._tanggal_ringkas("<script>x</script>") == (
        "<span>&lt;script&gt;x&lt;/script&gt;</span>"
    )
    blok = _blok(GAYA_STITCH, ".meta-sesi-st time")
    assert "white-space: nowrap" in blok


def test_catatan_tautan_berada_di_dekat_aksi_bagikan(anak):
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    badan = markup.split("<script>", 1)[0]
    assert 'id="kabar-bagikan"' not in badan
    assert '<span class="kabar-bagikan-st" aria-live="polite"></span>' in badan
    assert "Tautan berlaku 7 hari" not in badan


def test_halaman_lain_tidak_ikut_melebar(anak):
    """Dashboard memakai bingkai yang sama; ia harus tetap 46rem."""
    db, sid = anak
    with database.buka(db) as kon:
        html = teacher_pages.halaman_utama_stitch(
            kon, pemilik="ortu", peran="guru"
        ).decode()
    assert "bungkus-st lebar" not in _tanpa_gaya(html)


# ── Fase C — satu kartu "Buat latihan", tab CSS-only ──────────────────
#
# Tiga form (sesi baru / latihan ulang / gabungan topik) sebelumnya berdiri
# sebagai tiga kartu abu-abu berurutan. Kini dibungkus satu kartu dengan tab
# radio; hanya panel terpilih yang tampil.
#
# Palang yang dijaga:
# - TANPA JS baru (CLAUDE.md: zero-JS by default). Tab memakai radio +
#   selector :has(), teknik yang sudah dipakai .mode-opsi:has(input:checked).
# - Backend tidak tersentuh: tetap TIGA <form> dengan action masing-masing.
# - Browser tanpa dukungan :has() harus tetap melihat SEMUA form (degradasi
#   anggun), bukan halaman kosong tanpa cara membuat sesi.


def test_tiga_form_tetap_utuh_dengan_action_masing_masing(anak):
    """Pembungkusan visual tidak boleh mengubah kontrak POST."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert f'action="/sesi-baru/{sid}"' in markup
    assert f'action="/sesi-gabungan/{sid}"' in markup
    assert markup.count('<form method="post"') >= 2


def test_kartu_buat_latihan_membungkus_form(anak):
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert 'class="buat-latihan-st"' in markup
    assert markup.index('buat-latihan-st') < markup.index('/sesi-baru/')


def test_tab_memakai_radio_bukan_javascript(anak):
    """Tab harus radio murni; tidak boleh ada handler JS baru."""
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    assert 'name="jenis-latihan"' in markup
    assert "addEventListener(\"click\"" not in markup
    assert "onclick=" not in markup


def test_radio_tab_di_luar_form(anak):
    """Radio tab tidak boleh ikut terkirim sebagai field form.

    Diperiksa dengan menghitung <form> yang masih terbuka di titik radio
    berada — bukan sekadar membandingkan posisi dengan form pertama di
    halaman, karena topbar sudah memuat form logout jauh di atas.
    """
    db, sid = anak
    markup = _tanpa_gaya(_render_anak(db, sid))
    sebelum = markup[: markup.index('name="jenis-latihan"')]
    assert sebelum.count("<form") == sebelum.count("</form>"), (
        "radio tab berada di dalam <form> — nilainya akan ikut terkirim"
    )


def test_panel_disembunyikan_hanya_bila_has_didukung():
    """Tanpa @supports, browser lama menyembunyikan panel tanpa bisa
    menampilkannya lagi — guru kehilangan tombol buat sesi.

    Yang diperiksa: aturan `display: none` untuk panel harus berada DI DALAM
    blok @supports, bukan sekadar muncul sesudahnya di file.
    """
    aturan = _tanpa_komentar(GAYA_STITCH)
    mulai = aturan.index("@supports selector(:has(*))")
    # ambil isi blok @supports dengan menghitung kurung kurawal
    i = aturan.index("{", mulai)
    dalam, j = 0, i
    while j < len(aturan):
        if aturan[j] == "{":
            dalam += 1
        elif aturan[j] == "}":
            dalam -= 1
            if dalam == 0:
                break
        j += 1
    blok_supports = aturan[i : j + 1]

    assert ".panel-latihan-st" in blok_supports
    assert "display: none" in blok_supports
    # dan di luar @supports panel TIDAK boleh disembunyikan
    luar = aturan[:mulai] + aturan[j + 1 :]
    assert "\n.panel-latihan-st { display: none" not in luar
