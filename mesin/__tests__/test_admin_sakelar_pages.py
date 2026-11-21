"""Renderer murni halaman admin sakelar fitur: escape, status, sumber, form per baris, baca-saja."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_sakelar_pages as ui  # noqa: E402
import feature_switch as fs  # noqa: E402
import sakelar_registry as reg  # noqa: E402

XSS = '"><script>alert(1)</script>'


def _daftar(**ganti):
    dasar = {nama: fs.Sakelar(nama, False, 0, "env") for nama in fs.NAMA_SAKELAR}
    dasar.update(ganti)
    return tuple(dasar[nama] for nama in fs.NAMA_SAKELAR)


def _tokens(*nama):
    return {n: ("csrf-" + n, "tinjauan-" + n) for n in nama}


def test_setiap_sakelar_punya_label_status_sumber_revisi_dan_dampak():
    daftar = _daftar(OSN_CETAK_RINGKAS=fs.Sakelar("OSN_CETAK_RINGKAS", True, 3, "db"))
    isi = ui.halaman(daftar, None)
    for nama in fs.NAMA_SAKELAR:
        assert reg.info(nama).label in isi and reg.info(nama).dampak in isi
    assert isi.count("Aktif") >= 1 and isi.count("Mati") == 4
    assert "Admin (DB)" in isi and isi.count("Env (belum diatur admin)") == 4
    assert "Revisi 3" in isi and "Revisi 0" in isi


def test_tanpa_token_tampilan_baca_saja_tanpa_form():
    isi = ui.halaman(_daftar(), None)
    assert "<form" not in isi and "baca-saja" in isi.lower()


def test_form_per_baris_membawa_tepat_csrf_tinjauan_reauth_dan_tombol_target():
    daftar = _daftar(OSN_BANK_KALIMAT=fs.Sakelar("OSN_BANK_KALIMAT", True, 2, "db"))
    isi = ui.halaman(daftar, _tokens(*fs.NAMA_SAKELAR))
    formulir = re.findall(r"<form.*?</form>", isi, re.S)
    assert len(formulir) == 5
    for f in formulir:
        assert sorted(re.findall(r'name="(\w+)"', f)) == ["csrf", "reauth", "tinjauan"]
        assert 'action="/admin/sakelar"' in f and 'method="post"' in f
    assert sum("Nyalakan" in f for f in formulir) == 4 and sum("Matikan" in f for f in formulir) == 1


def test_nama_dan_target_tidak_pernah_menjadi_field_form():
    isi = ui.halaman(_daftar(), _tokens(*fs.NAMA_SAKELAR))
    for terlarang in ('name="nama"', 'name="aktif"', 'name="revisi"'):
        assert terlarang not in isi


def test_prasyarat_belum_terpenuhi_tanpa_form_dan_tombol_nyalakan_nonaktif():
    isi = ui.halaman(_daftar(), _tokens(*(n for n in fs.NAMA_SAKELAR if n != "PESANAN_TRANSFER_AKTIF")),
                     prasyarat={"PESANAN_TRANSFER_AKTIF": ("Funnel harus aktif.", "Rekening harus terisi.")})
    baris = isi.split(reg.info("PESANAN_TRANSFER_AKTIF").label, 1)[1].split("</section>", 1)[0]
    assert "Funnel harus aktif." in baris and "Rekening harus terisi." in baris
    assert "disabled" in baris and "<form" not in baris
    assert len(re.findall(r"<form", isi)) == 4


def test_nilai_dinamis_di_escape():
    isi = ui.halaman(_daftar(), {"FUNNEL_AKTIF": (XSS, XSS)},
                     prasyarat={"PESANAN_TRANSFER_AKTIF": (XSS,)}, hasil="tersimpan")
    assert "<script>" not in isi and "&lt;script&gt;" in isi


def test_hasil_tak_dikenal_tidak_menampilkan_umpan_balik():
    assert 'role="status"' not in ui.halaman(_daftar(), None, hasil=XSS)
    assert 'role="status"' in ui.halaman(_daftar(), None, hasil="tersimpan")


def test_halaman_galat_jujur_tanpa_form_dan_tanpa_path():
    isi = ui.halaman_galat()
    assert 'role="alert"' in isi and "<form" not in isi and "/data/" not in isi and ".db" not in isi


def test_registry_seed_env_memetakan_semua_nama_ke_bool_dan_env_tak_sah_jadi_false(monkeypatch):
    monkeypatch.setenv("OSN_CETAK_RINGKAS", "1")
    monkeypatch.setenv("OSN_BANK_KALIMAT", "bukan-nol-satu")
    monkeypatch.setenv("FUNNEL_AKTIF", " 1 ")
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF", raising=False)
    monkeypatch.delenv("OSN_LOMBA", raising=False)
    seed = reg.seed_env()
    assert set(seed) == set(fs.NAMA_SAKELAR) and all(type(v) is bool for v in seed.values())
    assert seed == {"FUNNEL_AKTIF": True, "PESANAN_TRANSFER_AKTIF": False,
                    "OSN_CETAK_RINGKAS": True, "OSN_BANK_KALIMAT": False, "OSN_LOMBA": False}


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
