"""Regresi presentasi Studio Belajar pada profil pendamping."""
from __future__ import annotations

import re
import sys
from dataclasses import replace
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interventions  # noqa: E402
import learning_cycle_ui  # noqa: E402
import style_stitch  # noqa: E402
from learning_cycle import BuktiSiklus, PutaranFokus, RencanaBelajar, StatusFokus  # noqa: E402


class _Markup(HTMLParser):
    def __init__(self, isi: str):
        super().__init__()
        self.tumpukan = []
        self.form = []
        self.details = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == "form":
            assert "form" not in self.tumpukan
            self.form.append(atribut)
        if tag == "details":
            self.details.append(atribut)
        self.tumpukan.append(tag)

    def handle_endtag(self, tag):
        if tag in self.tumpukan:
            indeks = len(self.tumpukan) - 1 - self.tumpukan[::-1].index(tag)
            self.tumpukan = self.tumpukan[:indeks]


def _putaran(*fokus):
    return PutaranFokus(
        7,
        "P3",
        tuple(StatusFokus(kunci, "perlu_dipelajari", jumlah_sesi=2) for kunci in fokus),
        (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)),
    )


def _render(tindakan: str, *, fokus=("deret_aritmetika", "K", None), tanggal=None):
    putaran = _putaran(fokus)
    rencana = RencanaBelajar(
        tindakan,
        "Alasan sintetis yang cukup panjang untuk menguji pembungkusan presentasi",
        putaran=putaran,
        kandidat=(fokus,),
        tersedia_pada=tanggal,
    )
    return learning_cycle_ui.render_rencana(rencana, BuktiSiklus(9, "P3"), 9)


def test_wrapper_studio_membagi_tugas_pendamping_dan_aksi_dengan_urutan_aman():
    isi = _render("intervensi")
    materi = interventions.untuk_fokus(("deret_aritmetika", "K", None))

    assert isi.count('class="studio-layout-st"') == 1
    assert isi.count('class="studio-utama-st"') == 1
    assert isi.count('class="studio-pendamping-st"') == 1
    assert isi.count('class="studio-aksi-st"') == 1
    assert 'aria-label="Posisi dan peran pendamping"' in isi
    assert isi.count('class="rencana-cta-utama-st"') == 1
    assert isi.index(materi.contoh_terbimbing) < isi.index('class="rencana-cta-utama-st"')
    assert isi.index(materi.instruksi_orang_tua) < isi.index('class="rencana-cta-utama-st"')
    assert isi.index('class="studio-utama-st"') < isi.index('class="studio-pendamping-st"') < isi.index('class="studio-aksi-st"')
    assert isi.index('class="studio-pendamping-st"') < isi.index('class="alur-rencana-jelas-st"')
    pendamping = isi.split('class="studio-pendamping-st"', 1)[1].split("</aside>", 1)[0]
    assert 'class="alur-rencana-jelas-st"' not in pendamping


def test_semua_tindakan_renderer_tetap_satu_cta_atau_tanpa_cta_sesuai_domain():
    tanpa_cta = {"tunggu_pemetaan", "tunggu_evaluasi", "tunggu_checkpoint", "eskalasi"}
    tindakan = (
        "pemetaan", "tunggu_pemetaan", "probe_diagnostik", "intervensi",
        "latihan_terbimbing", "penguatan", "tunggu_evaluasi", "evaluasi",
        "tunggu_checkpoint", "checkpoint", "probe_setelah_pengenalan",
        "mixed_maintenance", "putaran_baru", "eskalasi",
    )
    for nama in tindakan:
        isi = _render(nama, tanggal=date(2026, 9, 20) if nama.startswith("tunggu_") else None)
        jumlah = isi.count('class="rencana-cta-utama-st"')
        assert jumlah == (0 if nama in tanpa_cta else 1), nama
        assert isi.count('aria-current="step"') == 1, nama
        assert 'class="tahap-rencana-st selesai"' not in isi, nama


def test_materi_panjang_dua_fokus_override_dan_materi_tidak_ada_tetap_utuh(monkeypatch):
    fokus_a = ("deret_aritmetika", "K", None)
    fokus_b = ("soal_umur", "H", "langkah-panjang")
    putaran = _putaran(fokus_a, fokus_b)
    panjang = "Instruksi panjang " + "yang tetap harus terbaca " * 20
    materi = interventions.MateriIntervensi("pendekatan-uji", panjang, panjang, "", tersedia=True)
    monkeypatch.setattr(learning_cycle_ui.interventions, "pilihan_untuk_fokus", lambda _: (materi,))
    rencana = RencanaBelajar("intervensi", "uji", putaran=putaran, kandidat=(fokus_a, fokus_b))

    isi = learning_cycle_ui.render_rencana(rencana, BuktiSiklus(9, "P3"), 9)
    assert isi.count(panjang) == 2
    assert '<details class="ubah-fokus-st">' in isi
    assert isi.index(panjang) < isi.index('class="rencana-cta-utama-st"')

    kosong = replace(materi, tersedia=False, contoh_terbimbing="")
    monkeypatch.setattr(learning_cycle_ui.interventions, "pilihan_untuk_fokus", lambda _: (kosong,))
    tanpa = learning_cycle_ui.render_rencana(rencana, BuktiSiklus(9, "P3"), 9)
    assert panjang in tanpa
    assert 'class="rencana-cta-utama-st"' not in tanpa


def test_sesi_aktif_dan_konfirmasi_mempertahankan_tautan_cta_tunggal():
    from learning_cycle import SesiSiklus

    sesi = SesiSiklus(41, 9, "P3", "pemetaan", date(2026, 9, 2), putaran_id=7)
    bukti = BuktiSiklus(9, "P3", sesi=(sesi,))
    for tindakan, label in (("lanjutkan_sesi", "Lanjutkan sesi"), ("konfirmasi_hasil", "Tinjau hasil")):
        isi = learning_cycle_ui.render_rencana(
            RencanaBelajar(tindakan, "Sesi aktif", sesi_id=41), bukti, 9
        )
        assert isi.count('class="rencana-cta-utama-st"') == 1
        assert f'href="/sesi/41">{label}</a>' in isi


def test_menunggu_memiliki_layout_utuh_tanggal_dan_tanpa_kolom_aksi_palsu():
    isi = _render("tunggu_evaluasi", tanggal=date(2026, 9, 20))
    assert "20 September 2026" in isi
    assert 'class="studio-pendamping-st"' in isi
    assert '<div class="studio-aksi-st"></div>' in isi
    assert 'class="rencana-cta-utama-st"' not in isi


def test_css_studio_scoped_responsif_dan_fallback_kontrol_manual():
    sumber = Path(style_stitch.__file__).read_text(encoding="utf-8")
    mulai = sumber.index(".profil-editorial-st .studio-layout-st")
    akhir = sumber.index(".koreksi-editorial-st", mulai)
    blok = sumber[mulai:akhir]

    assert 'grid-template-areas: "utama pendamping" "aksi aksi" "alur alur"' in blok
    assert "grid-template-columns: repeat(6, minmax(0, 1fr))" in blok
    aksi = blok.split(".profil-editorial-st .studio-aksi-st {{", 1)[1].split("}}", 1)[0]
    assert "align-self: start" in aksi
    tombol = blok.split(".profil-editorial-st .rencana-cta-utama-st {{", 1)[1].split("}}", 1)[0]
    assert "align-self: start" in tombol
    assert "padding-block: {T.SP_3}" in tombol
    responsif = sumber.split("/* Studio kembali satu kolom", 1)[1].split(
        "@media (max-width: 40rem)", 1
    )[0]
    assert "@media (max-width: 48rem)" in responsif
    assert ".profil-editorial-st .studio-pendamping-st {{ display: contents; }}" in responsif
    assert ".profil-editorial-st .isi-alur-rencana-st .strip-rencana-st {{ grid-template-columns: minmax(0, 1fr); }}" in responsif
    assert '[data-panel=\"baru\"] > .strip-sesi' in blok
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in blok
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", blok)

    css = style_stitch.GAYA_STITCH
    supports = css.index("@supports selector(:has(*))")
    assert css.index(".panel-latihan-st { display: none; }", supports) > supports
    assert ".tab-radio-st:focus-visible" in css


def test_form_manual_actual_tetap_default_dan_langsung_terlihat(tmp_path, monkeypatch):
    import auth
    import database
    import sessions
    import teacher_pages

    jalur = tmp_path / "studio-sintetis.db"
    monkeypatch.setattr(database, "BAWAAN", jalur)
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi.json")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Studio", "P3", pemilik="guru")
        siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (siswa_id,)).fetchone()
        isi = teacher_pages.halaman_anak(kon, siswa, pengguna="guru").decode()
    badan = isi.split("</style>", 1)[1]
    markup = _Markup(badan)

    assert '<section class="profil-formulaire-st">' in badan
    assert '<details class="atur-latihan-st"' not in badan
    assert badan.count('<h2 class="st">Buat latihan</h2>') == 1
    assert f'action="/sesi-baru/{siswa_id}"' in badan
    assert f'action="/sesi-gabungan/{siswa_id}"' in badan
    for bidang in ('name="topik"', 'name="jumlah_soal"', 'name="mode"', 'name="timer_mode"', 'name="durasi_menit"', 'name="timer_auto"'):
        assert bidang in badan
    assert 'name="mode" value="diagnostik" checked' in badan
    assert 'name="timer_auto" value="0" checked' in badan
    assert all("open" not in detail for detail in markup.details if detail.get("class") == "atur-latihan-st")
