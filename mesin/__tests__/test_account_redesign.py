"""Redesain /akun (fase 1: tab Akun saya dan Anak): tata letak, header, kartu anak.

Hanya markup dan CSS; handler POST dan guard tetap dijaga test_akun*.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import account_pages  # noqa: E402
import account_style  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import design_tokens as T  # noqa: E402


@pytest.fixture()
def siap(tmp_path, monkeypatch):
    db = tmp_path / "uji.db"
    berkas = tmp_path / "sandi.json"
    database.siapkan(db)
    monkeypatch.setattr(database, "BAWAAN", db)
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    auth.simpan_sandi("sandi-lama-panjang", "guru", berkas)
    return db


def _halaman(siap, section="akun", peran="guru", tambah_anak=0):
    with database.buka(siap) as kon:
        for n in range(tambah_anak):
            sid = database.tambah_siswa(kon, f"Anak Uji {n}", pemilik="guru")
            auth.tambah_akun(f"login-uji-{n}", "rahasia-uji-12345", "murid", siswa_id=sid)
        return account_pages.halaman_akun(
            kon, pengguna="guru", peran=peran, section=section,
            analitik="<section class='kartu-st'><h2>Analitik uji</h2></section>",
        ).decode()


def _badan(isi):
    return isi.split("<body", 1)[1]


def test_wadah_akun_lebar_agar_dua_kolom_muat(siap):
    isi = _halaman(siap)
    assert re.search(r'<div class="bungkus-st [^"]*\bakun-editorial-st\b[^"]*\blebar\b', isi)


def test_akun_saya_dua_kolom_sandi_di_kiri_pendamping_di_kanan(siap):
    badan = _badan(_halaman(siap))
    grid = badan.split('<div class="akun-grid-st">', 1)[1]
    kiri, _, kanan = grid.partition('<div class="akun-kolom-st">')[2].partition('<div class="akun-kolom-st">')
    assert "<h2>Ganti kata sandi</h2>" in kiri and "Kelola data Pendamping" not in kiri
    assert "<h2>Data Pendamping AI</h2>" in kanan and "Analitik uji" in kanan


def test_tombol_keluar_ada_di_header_bukan_di_kartu_sandi(siap):
    badan = _badan(_halaman(siap))
    kepala, _, sisa = badan.partition('<div class="layout-samping">')
    assert 'class="akun-form-keluar" method="post" action="/keluar"' in kepala
    assert "/keluar" not in sisa


def test_header_menampilkan_jumlah_profil_anak_untuk_guru(siap):
    assert "0 profil anak" in _halaman(siap)
    assert "2 profil anak" in _halaman(siap, tambah_anak=2)


def test_header_admin_tanpa_chip_profil_anak(siap):
    assert "profil anak" not in _badan(_halaman(siap, peran="admin")).split('<div class="layout-samping">')[0]


def test_kartu_tanpa_ikon_emoji_dekoratif(siap):
    for section in ("akun", "siswa"):
        badan = _badan(_halaman(siap, section=section)).split("</style>", 1)[-1]
        assert "ikon-kartu" not in badan
        assert not any(e in badan for e in ("🔑", "📚", "🧒"))


def test_bantuan_pemulihan_sejajar_tombol_ganti_sandi(siap):
    badan = _badan(_halaman(siap))
    baris = badan.split('class="akun-aksi-sandi"', 1)[1].split("</form>", 1)[0]
    assert "Ganti kata sandi</button>" in baris
    assert '<a href="/lupa-sandi">Bantuan pemulihan akun</a>' in baris


def test_kartu_pendamping_memakai_tombol_garis(siap):
    badan = _badan(_halaman(siap))
    assert re.search(
        r'<a class="akun-tombol-garis-st" href="/pendamping/kelola">Kelola data Pendamping</a>', badan
    )


def test_siswa_dua_kolom_daftar_kiri_form_tambah_kanan(siap):
    badan = _badan(_halaman(siap, section="siswa", tambah_anak=1))
    _, _, grid = badan.partition('<div class="akun-grid-st">')
    kiri, _, kanan = grid.partition('<div class="akun-kolom-st">')[2].partition('<div class="akun-kolom-st">')
    assert "<h2>Daftar anak</h2>" in kiri and "<h2>Tambah anak</h2>" not in kiri
    assert "<h2>Tambah anak</h2>" in kanan


def test_kartu_anak_punya_inisial_chip_dan_tombol_kelola_tutup(siap):
    badan = _badan(_halaman(siap, section="siswa", tambah_anak=1))
    kartu = badan[badan.index('<article class="akun-anak-kartu"'):badan.index("</article>")]
    assert '<span class="akun-inisial-st" aria-hidden="true">A</span>' in kartu
    assert '<span class="akun-chip-st">0 sesi latihan</span>' in kartu
    assert "Login: login-uji-0" in kartu
    assert '<summary><span class="akun-kelola-buka">Kelola</span><span class="akun-kelola-tutup">Tutup</span></summary>' in kartu
    assert '<details class="akun-kelola">' in kartu
    assert "<script" not in kartu


def test_istilah_orang_dewasa_pakai_anda_di_form_tambah_anak(siap):
    badan = _badan(_halaman(siap, section="siswa"))
    assert "berbeda dari kata sandi Anda" in badan
    assert "orang tua" not in badan


def test_gaya_akun_dimuat_di_halaman_akun(siap):
    isi = _halaman(siap)
    assert ".akun-editorial-st .akun-grid-st" in isi


def test_gaya_akun_hanya_token_dan_tersekop():
    css = account_style.GAYA_AKUN
    sumber = Path(account_style.__file__).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber), "hex literal harus lewat design_tokens"
    for baris in css.splitlines():
        if baris and not baris.startswith((" ", "@", "}")) and "{" in baris:
            assert "akun-editorial-st" in baris, baris
    assert f"@media (min-width: {T.MULAI_DESKTOP})" in css
    assert f"min-height: {T.TARGET_SENTUH}" in css


def test_gaya_akun_tanpa_font_atau_sumber_luar():
    css = account_style.GAYA_AKUN
    assert "@import" not in css and "url(" not in css and "font-family" not in css


# ── Fase 2: tab Langganan ───────────────────────────────────────────────


def _status_layanan(siap, monkeypatch, anak=1):
    import account_http
    import subscription

    with database.buka(siap) as kon:
        for n in range(anak):
            database.tambah_siswa(kon, f"Sendiri {n}", pemilik="guru")
        database.tambah_siswa(kon, "Bukan milik", pemilik="lain")
    monkeypatch.setattr("subscription_produksi_http.ada", lambda p: True)

    def nonaktif(p):
        raise subscription.FiturNonaktif()

    monkeypatch.setattr("subscription_produksi_http._runtime", nonaktif)
    return account_http._fragmen_langganan(None, ("guru", "guru"))


def test_status_layanan_dua_kartu_paket_dan_bantuan(siap, monkeypatch):
    h = _status_layanan(siap, monkeypatch, anak=2)
    assert h.count('<div class="akun-kolom-st">') == 2 and 'class="akun-grid-st"' in h
    paket, _, bantuan = h.partition('<div class="akun-kolom-st">')[2].partition('<div class="akun-kolom-st">')
    assert "PAKET SAAT INI" in paket and "<h2" in paket and ">Akses awal</h2>" in paket
    assert '<span class="akun-chip-st">Gratis · nonkomersial</span>' in paket
    assert "<b>2 profil anak</b> sedang digunakan" in paket and "Tidak ada penagihan baru" in paket
    assert '<a href="/akun?section=siswa">Lihat</a>' in paket
    assert "<h2>Pembayaran &amp; bantuan</h2>" in bantuan
    assert 'class="akun-tombol-garis-st" href="/lupa-sandi">Hubungi dukungan Jagomat</a>' in bantuan
    assert "Bukan milik" not in h and "Status layanan" not in h


def test_status_layanan_tanpa_form_atau_aksi_pembayaran(siap, monkeypatch):
    h = _status_layanan(siap, monkeypatch)
    assert "<form" not in h and "<button" not in h and "/langganan/" not in h


def test_tab_langganan_membungkus_fragmen_agar_tertata(siap):
    with database.buka(siap) as kon:
        isi = account_pages.halaman_akun(
            kon, pengguna="guru", section="langganan", langganan_sandbox=True,
            langganan_html='<section class="kartu-st"><h2>Siapkan tagihan</h2></section>',
        ).decode()
    badan = _badan(isi).split("</style>", 1)[-1]
    assert '<div class="akun-kolom-st akun-langganan-st"><section class="kartu-st"><h2>Siapkan tagihan' in badan


def test_gaya_langganan_di_akun_tanpa_garis_kiri_dan_kontrol_44():
    css = account_style.GAYA_AKUN
    aturan = re.search(r"\.akun-editorial-st \.peringatan[^{]*\{([^}]+)\}", css).group(1)
    assert "border-left" not in aturan and f"border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}" in aturan
    assert f"min-height: {T.TARGET_SENTUH}" in re.search(r"\.akun-editorial-st fieldset label[^{]*\{([^}]+)\}", css).group(1)


# ── Penyelarasan dengan mockup: label, placeholder, Langganan, CSS HP ──


def test_form_sandi_label_bersih_dan_petunjuk_jadi_placeholder(siap):
    badan = _badan(_halaman(siap))
    assert '<label for="sandi-baru">Kata sandi baru</label>' in badan
    assert re.search(r'<input id="sandi-baru"[^>]*minlength="12"[^>]*placeholder="Minimal 12 karakter"', badan)
    assert re.search(r'<input id="sandi-ulang"[^>]*placeholder="Ketik ulang"', badan)
    # Alasan lengkap tetap tersambung ke kolom lewat aria-describedby, bukan hanya placeholder.
    assert 'aria-describedby="alasan-sandi-baru"' in badan and 'id="alasan-sandi-baru"' in badan


def test_status_layanan_catatan_berikon_menyatukan_pernyataan_pembayaran(siap, monkeypatch):
    h = _status_layanan(siap, monkeypatch, anak=2)
    _, _, bantuan = h.partition('<div class="akun-kolom-st">')[2].partition('<div class="akun-kolom-st">')
    catatan = bantuan.split('<p class="akun-catatan-st akun-catatan-ikon-st">', 1)[1].split("</p>", 1)[0]
    assert catatan.startswith("<svg") and 'aria-hidden="true"' in catatan
    assert "Pembayaran online belum tersedia di Jagomat." in catatan
    assert "Halaman ini tidak mengaktifkan paket atau tagihan baru." in catatan
    assert "Pembayaran online belum tersedia" not in h.split("<h2>Pembayaran", 1)[0]


def test_css_akun_label_tebal_dan_ikon_tersekop_token():
    css = account_style.GAYA_AKUN
    assert re.search(r"\.akun-editorial-st form > label:not\(\.akun-label-persetujuan\):not\(\.pendamping-sr\)[^{]*\{[^}]*font-weight: 600", css)
    assert '[href="/persetujuan"]::after' in css and ".akun-catatan-ikon-st svg" in css
    sumber = Path(account_style.__file__).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", sumber), "CSS akun hanya boleh memakai token T.*"


def test_css_hp_tombol_sandi_penuh_dan_tautan_di_tengah():
    css = account_style.GAYA_AKUN
    blok = css.split(f"@media (max-width: {T.BATAS_HP})")[-1]
    assert ".akun-kartu-sandi .akun-aksi-sandi" in blok and "flex-direction: column" in blok
    assert "align-items: stretch" in blok and "justify-content: center" in blok
