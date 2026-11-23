"""Renderer murni halaman admin sakelar fitur: escape, status, sumber, form per baris, baca-saja."""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_sakelar_pages as ui  # noqa: E402
import feature_switch as fs  # noqa: E402
import sakelar_registry as reg  # noqa: E402
from admin_rekening_pages import KEADAAN_BELUM_DIPASANG, KEADAAN_TERISI  # noqa: E402

XSS = '"><script>alert(1)</script>'


def _daftar(**ganti):
    dasar = {nama: fs.Sakelar(nama, False, 0, "env") for nama in fs.NAMA_SAKELAR}
    dasar.update(ganti)
    return tuple(dasar[nama] for nama in fs.NAMA_SAKELAR)


def _tokens(*nama):
    return {n: ("csrf-" + n, "tinjauan-" + n) for n in nama}


def _semua(daftar, tokens, **kw):
    """Semua kartu sakelar berurutan sebagai satu HTML (tanpa pengelompokan halaman induk)."""
    b = ui.bagian(daftar, tokens, **kw)
    return (b.umpan_balik + b.catatan + "".join(b.penjualan.values()) + "".join(b.belajar.values())
            + b.catatan_teknis)


def _kartu(isi, nama):
    return isi.split('id="%s"' % ui.id_kartu(nama), 1)[1].split("</section>", 1)[0]


def test_setiap_sakelar_punya_label_status_sumber_revisi_dan_dampak():
    daftar = _daftar(OSN_CETAK_RINGKAS=fs.Sakelar("OSN_CETAK_RINGKAS", True, 3, "db"))
    isi = _semua(daftar, None)
    for nama in fs.NAMA_SAKELAR:
        assert reg.info(nama).label in isi and reg.info(nama).dampak in isi
    assert isi.count('admin-badge admin-status-besar bien">Aktif<') == 1
    assert isi.count('admin-badge admin-status-besar">Mati<') == 6
    # Sumber dan revisi hanya di detail teknis kecil, bukan di baris status.
    assert "diatur admin di halaman ini. Revisi 3." in _kartu(isi, "OSN_CETAK_RINGKAS")
    assert isi.count("nilai bawaan server, belum pernah diubah di sini. Revisi 0.") == 6
    assert isi.count('<details class="admin-detail-teknis"><summary>Detail teknis</summary>') == 7
    for jargon in ("Admin (DB)", "Env (belum diatur admin)", "Sumber:"):
        assert jargon not in isi


def test_kelompok_penjualan_dan_belajar_mengikuti_registri():
    b = ui.bagian(_daftar(), None)
    assert tuple(b.penjualan) == (ui.FUNNEL, ui.TRANSFER, "DAFTAR_AKUN_ANAK")
    assert tuple(b.belajar) == ("OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT", "OSN_LOMBA") or set(b.belajar) == {
        "OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT", "OSN_LOMBA", "LATIHAN_HARIAN"}
    assert set(b.penjualan) | set(b.belajar) == set(fs.NAMA_SAKELAR)
    assert tuple(n for n, _l, _a in b.status) == fs.NAMA_SAKELAR


def test_tanpa_token_tampilan_baca_saja_tanpa_form():
    isi = _semua(_daftar(), None)
    assert "<form" not in isi and "baca-saja" in isi.lower()
    assert "<details class=\"admin-aksi-ubah\"" not in isi and "<button" not in isi  # tanpa tombol sama sekali


def test_form_per_baris_membawa_tepat_csrf_tinjauan_reauth_dan_tombol_target():
    daftar = _daftar(OSN_BANK_KALIMAT=fs.Sakelar("OSN_BANK_KALIMAT", True, 2, "db"))
    isi = _semua(daftar, _tokens(*fs.NAMA_SAKELAR))
    formulir = re.findall(r"<form.*?</form>", isi, re.S)
    assert len(formulir) == 7
    for f in formulir:
        assert sorted(re.findall(r'name="(\w+)"', f)) == ["csrf", "reauth", "tinjauan"]
        assert 'action="/admin/sakelar"' in f and 'method="post"' in f
    assert sum("Nyalakan</button>" in f for f in formulir) == 6 and sum("Matikan</button>" in f for f in formulir) == 1


def test_sandi_hanya_di_dalam_details_yang_terlipat():
    isi = _semua(_daftar(), _tokens(*fs.NAMA_SAKELAR))
    kartu = _kartu(isi, ui.FUNNEL)
    assert re.search(r'<details class="admin-aksi-ubah"><summary class="admin-tombol">Nyalakan fitur ini…</summary>'
                     r'<form[^>]*>.*name="reauth".*</form></details>', kartu, re.S)
    assert "<details class=\"admin-aksi-ubah\" open" not in isi  # terlipat bawaan
    # Tidak ada kolom sandi di luar <details> tindakan.
    sisa = re.sub(r'<details class="admin-aksi-ubah">.*?</details>', "", isi, flags=re.S)
    assert 'name="reauth"' not in sisa


def test_mematikan_fitur_aktif_gaya_peringatan_dan_konfirmasi_menyebut_akibat():
    daftar = _daftar(FUNNEL_AKTIF=fs.Sakelar("FUNNEL_AKTIF", True, 4, "db"))
    isi = _semua(daftar, _tokens(*fs.NAMA_SAKELAR))
    kartu = _kartu(isi, ui.FUNNEL)
    info = reg.info("FUNNEL_AKTIF")
    form = re.search(r"<form[^>]*>", kartu).group(0)
    konfirmasi = html.unescape(re.search(r'data-konfirmasi="([^"]*)"', form).group(1))
    assert konfirmasi == "Matikan %s? %s" % (info.label, info.akibat_mati)
    assert "belum dibuka" in konfirmasi and "semua pengunjung" in konfirmasi
    assert '<button class="admin-tombol admin-bahaya" type="submit">Matikan</button>' in kartu
    assert 'class="admin-tombol admin-bahaya-garis">Matikan fitur ini…' in kartu
    assert html.escape(info.akibat_mati) in kartu  # akibat juga terbaca sebelum form dibuka sandinya
    # Menyalakan tidak memakai konfirmasi maupun gaya peringatan.
    mati = _kartu(_semua(_daftar(), _tokens(*fs.NAMA_SAKELAR)), ui.FUNNEL)
    assert "data-konfirmasi" not in mati and "admin-bahaya" not in mati


def test_setiap_sakelar_punya_akibat_mati_dan_kelompok_di_registri():
    for nama in fs.NAMA_SAKELAR:
        info = reg.info(nama)
        assert info.akibat_mati.strip().endswith(".") and info.kelompok in reg.KELOMPOK
    assert set(reg.nama_kelompok(reg.KELOMPOK_PENJUALAN)) == {ui.FUNNEL, ui.TRANSFER, "DAFTAR_AKUN_ANAK"}


def test_status_aktif_mati_menonjol_dan_istilah_teknis_hilang():
    isi = _semua(_daftar(), _tokens(*fs.NAMA_SAKELAR))
    for jargon in ("runtime produksi", "funnel", "Funnel", "env", "Perubahan pertama menyimpan nilai env"):
        assert jargon not in re.sub(r'(name|id|value)="[^"]*"', "", isi), jargon


def test_nama_dan_target_tidak_pernah_menjadi_field_form():
    isi = _semua(_daftar(), _tokens(*fs.NAMA_SAKELAR))
    for terlarang in ('name="nama"', 'name="aktif"', 'name="revisi"'):
        assert terlarang not in isi


def test_prasyarat_belum_terpenuhi_tanpa_form_dan_tombol_nyalakan_nonaktif():
    isi = _semua(_daftar(), _tokens(*(n for n in fs.NAMA_SAKELAR if n != "PESANAN_TRANSFER_AKTIF")),
                 prasyarat={"PESANAN_TRANSFER_AKTIF": ("Funnel harus aktif.", ui.COPY_BELUM_REKENING)})
    baris = _kartu(isi, "PESANAN_TRANSFER_AKTIF")
    assert reg.info("PESANAN_TRANSFER_AKTIF").label in baris
    assert "Funnel harus aktif." in baris and ui.COPY_BELUM_REKENING in baris
    assert 'href="/admin/pesanan/rekening"' in baris  # prasyarat rekening memberi tautan
    assert "disabled" in baris and "<form" not in baris
    assert len(re.findall(r"<form", isi)) == 6


def test_nilai_dinamis_di_escape():
    isi = _semua(_daftar(), {"FUNNEL_AKTIF": (XSS, XSS)},
                 prasyarat={"PESANAN_TRANSFER_AKTIF": (XSS,)}, hasil="tersimpan")
    assert "<script>" not in isi and "&lt;script&gt;" in isi


def test_hasil_tak_dikenal_tidak_menampilkan_umpan_balik():
    assert 'role="status"' not in _semua(_daftar(), None, hasil=XSS)
    assert 'role="status"' in _semua(_daftar(), None, hasil="tersimpan")


def _checklist(rekening, qris_tutup, transfer_aktif):
    return ui.checklist_transfer(rekening=rekening, qris_tutup=qris_tutup, transfer_aktif=transfer_aktif)


def _status_langkah(isi):
    """[(kelas status, teks)] per langkah bernomor."""
    return [(m.group(1), m.group(2)) for m in re.finditer(
        r'<li class="admin-langkah-item (\S+)"><div class="admin-langkah-isi"><strong>(.*?)</strong>', isi)]


def test_checklist_transfer_semua_belum():
    isi = _checklist("kosong", False, False)
    assert isi.count('<li class="admin-langkah-item') == 3 and "<ol" in isi
    assert [s for s, _t in _status_langkah(isi)] == ["belum", "belum", "belum"]
    assert 'href="/admin/pesanan/rekening">Isi di halaman rekening</a>' in isi
    assert 'href="#pembayaran">Pembayaran QRIS</a>' in isi
    assert 'href="#%s">Pembayaran transfer rekening</a>' % ui.id_kartu(ui.TRANSFER) in isi
    assert "<form" not in isi and "<button" not in isi


def test_checklist_transfer_sebagian_selesai():
    isi = _checklist(KEADAAN_TERISI, False, False)
    assert [s for s, _t in _status_langkah(isi)] == ["selesai", "belum", "belum"]
    assert "Lihat atau ubah rekening" in isi and "QRIS masih terbuka" in isi


def test_checklist_transfer_semua_selesai():
    isi = _checklist(KEADAAN_TERISI, True, True)
    assert [s for s, _t in _status_langkah(isi)] == ["selesai", "selesai", "selesai"]
    assert isi.count('admin-badge bien">Selesai<') == 3 and "QRIS sudah tertutup" in isi and "Sudah menyala" in isi


def test_checklist_transfer_skema_rekening_belum_dipasang_jujur_dan_tanpa_tautan():
    isi = _checklist(KEADAAN_BELUM_DIPASANG, True, False)
    assert _status_langkah(isi)[0][0] == "belum"
    assert "belum dipasang operator" in isi and 'href="/admin/pesanan/rekening"' not in isi


def test_checklist_transfer_status_tak_terbaca_bukan_selesai():
    isi = _checklist(None, None, False)
    assert [s for s, _t in _status_langkah(isi)] == ["tak-tahu", "tak-tahu", "belum"]
    assert isi.count("Belum bisa diperiksa") == 2


def test_halaman_galat_jujur_tanpa_form_dan_tanpa_path():
    isi = ui.halaman_galat()
    assert 'role="alert"' in isi and "<form" not in isi and "/data/" not in isi and ".db" not in isi


def test_registry_seed_env_memetakan_semua_nama_ke_bool_dan_env_tak_sah_jadi_false(monkeypatch):
    monkeypatch.setenv("OSN_CETAK_RINGKAS", "1")
    monkeypatch.setenv("OSN_BANK_KALIMAT", "bukan-nol-satu")
    monkeypatch.setenv("FUNNEL_AKTIF", " 1 ")
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF", raising=False)
    monkeypatch.delenv("OSN_LOMBA", raising=False)
    monkeypatch.delenv("DAFTAR_AKUN_ANAK", raising=False)
    monkeypatch.delenv("LATIHAN_HARIAN", raising=False)
    seed = reg.seed_env()
    assert set(seed) == set(fs.NAMA_SAKELAR) and all(type(v) is bool for v in seed.values())
    assert seed == {"FUNNEL_AKTIF": True, "PESANAN_TRANSFER_AKTIF": False,
                    "OSN_CETAK_RINGKAS": True, "OSN_BANK_KALIMAT": False, "OSN_LOMBA": False,
                    "DAFTAR_AKUN_ANAK": False, "LATIHAN_HARIAN": False}


def test_navigasi_admin_memuat_pengaturan_layanan_di_grup_sistem():
    import admin_pages
    assert ("operasional", "Pengaturan layanan", "/admin/sakelar") in admin_pages.SECTION
    assert ("sakelar", "Sakelar fitur", "/admin/sakelar") in admin_pages.SECTION
    assert "operasional" in dict(admin_pages.GRUP_SECTION)["Sistem"]
    assert "sakelar" in admin_pages.SECTION_LOKAL
    # Id lama "sakelar" tetap sah dan menyorot butir Pengaturan layanan (satu butir untuk dua halaman lama).
    for section in ("sakelar", "operasional"):
        isi = admin_pages.halaman_admin(section, "", pengguna="Pengelola").decode()
        assert isi.count('<a href="/admin/sakelar" aria-current="page">') == 2  # desktop + seluler
        assert '<strong>Pengaturan layanan</strong>' in isi


def test_registry_info_lengkap_dan_nama_asing_ditolak():
    for nama in fs.NAMA_SAKELAR:
        info = reg.info(nama)
        assert info.label.strip() and info.dampak.strip().endswith(".")
    with pytest.raises(KeyError):
        reg.info("PENDAMPING_AKTIF")
