"""Kontrak markup dashboard Riset konsumen setelah redesain: form, consent, ekspor POST."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pages  # noqa: E402
import admin_research_pages as ui  # noqa: E402

FORM = re.compile(r'<form\b([^>]*)>(.*?)</form>', re.S)
PERINGATAN = ("Gunakan kode anonim. Jangan masukkan nama orang tua, nama anak, sekolah, "
              "kontak, foto, atau jawaban soal anak.")
CONSENT_WAWANCARA = "Responden setuju mengikuti wawancara."
CONSENT_REKAMAN = "Responden secara terpisah setuju direkam. Berkas rekaman tidak disimpan di Jagomat."
TOKEN_EKSPOR = {"csv": "token-csv", "json": "token-json"}


def _item(kode, status="draf"):
    return {"id": "rw_" + kode.lower() * 8, "kode_responden": kode, "status": status,
            "sumber": "meta_ads", "terisi": 3, "diperbarui": int(time.time())}


def _halaman(items=(), *, status_filter="", ringkasan=None):
    data = {
        "ringkasan": ringkasan or dict(draf=0, final=0, perlu_redaksi=0, mendekati_retensi=0),
        "daftar": NS(item=list(items), total=len(items), per_halaman=20, halaman=1),
    }
    isi = ui.dashboard(data, csrf="csrf-sintetis", token_buat="token-buat",
                       token_ekspor=TOKEN_EKSPOR, status_filter=status_filter)
    aksi = ui.aksi_data(csrf="csrf-sintetis", token_ekspor=TOKEN_EKSPOR)
    return admin_pages.halaman_admin("riset", isi, pengguna="Pengelola Demo",
                                     judul="Riset konsumen", aksi_header=aksi).decode()


def _konten(html):
    """Header halaman + main saja; form Keluar milik kerangka tidak ikut."""
    kepala = html.split('<header class="admin-kepala', 1)[1]
    return kepala.split("</main>", 1)[0]


def _form(html, aksi, metode="post"):
    cocok = [m for m in FORM.finditer(_konten(html))
             if 'action="%s"' % aksi in m.group(1) and 'method="%s"' % metode in m.group(1)]
    return cocok


def test_tepat_empat_form_di_konten_dan_tanpa_form_lain():
    html = _halaman()
    daftar = FORM.findall(_konten(html))
    assert len(daftar) == 4
    assert len(_form(html, "/admin/riset", "get")) == 1
    assert len(_form(html, "/admin/riset/buat")) == 1
    assert len(_form(html, "/admin/riset/ekspor")) == 2


def test_ekspor_tetap_post_signed_tanpa_tautan_get():
    html = _halaman()
    assert 'href="/admin/riset/ekspor' not in html
    formats = []
    for m in _form(html, "/admin/riset/ekspor"):
        isi = m.group(2)
        assert 'name="csrf" value="csrf-sintetis"' in isi
        formats.append(re.search(r'name="format" value="(\w+)"', isi).group(1))
        assert 'name="tinjauan" value="token-%s"' % formats[-1] in isi
        assert isi.count('type="submit"') == 1
    assert sorted(formats) == ["csv", "json"]
    assert '<form method="post" action="/admin/riset/ekspor">' in html


def test_aksi_data_ada_di_header_dan_matriks_tautan_biasa():
    html = _halaman()
    kepala = html.split('<header class="admin-kepala', 1)[1].split("</header>", 1)[0]
    assert "admin-kepala-aksi" in html.split('<header class="admin-kepala', 1)[1][:40]
    assert 'href="/admin/riset/matriks"' in kepala
    assert kepala.count('action="/admin/riset/ekspor"') == 2
    assert "Ekspor CSV anonim" in kepala and "Ekspor JSON anonim" in kepala


def test_kepala_tanpa_aksi_tidak_berubah():
    html = admin_pages.halaman_admin("riset", "<p>x</p>", pengguna="Pengelola Demo",
                                     judul="Riset konsumen", subjudul="s").decode()
    assert '<header class="admin-kepala"><h1 id="judul-admin">Riset konsumen</h1>' in html
    assert 'class="admin-kepala admin-kepala-aksi"' not in html


def test_form_buat_mempertahankan_field_validasi_dan_consent_terpisah():
    isi = _form(_halaman(), "/admin/riset/buat")[0].group(2)
    assert 'name="csrf" value="csrf-sintetis"' in isi and 'name="tinjauan" value="token-buat"' in isi
    kode = re.search(r'<input name="kode_responden"[^>]*>', isi).group(0)
    assert 'maxlength="32"' in kode and 'pattern="[A-Za-z0-9][A-Za-z0-9_-]{2,31}"' in kode and " required" in kode
    assert re.search(r'<input type="datetime-local" name="diwawancarai" required>', isi)
    assert re.search(r'<select name="sumber">', isi)
    assert re.search(r'<input type="checkbox" name="consent_wawancara" value="1" required>', isi)
    rekaman = re.search(r'<input type="checkbox" name="consent_rekaman" value="1"[^>]*>', isi).group(0)
    assert "required" not in rekaman
    assert sorted(re.findall(r'<(?:input|select|textarea)\b[^>]*\bname="([^"]+)"', isi)) == [
        "consent_rekaman", "consent_wawancara", "csrf", "diwawancarai",
        "kode_responden", "sumber", "tinjauan"]


def test_teks_privasi_dan_persetujuan_kata_per_kata():
    html = _halaman()
    assert PERINGATAN in html
    assert CONSENT_WAWANCARA in html and CONSENT_REKAMAN in html
    assert 'class="riset-persetujuan"' in html


def test_penghitung_bertumpuk_dengan_label_dan_angka_dari_data():
    html = _halaman(ringkasan=dict(draf=1, final=2, perlu_redaksi=3, mendekati_retensi=4))
    assert 'class="admin-grid-stat riset-stat"' in html
    for label, angka in (("Draf", 1), ("Final", 2), ("Perlu redaksi", 3), ("Retensi ≤7 hari", 4)):
        assert re.search(r'<h2>%s</h2><div><strong>%d</strong><span>wawancara</span>' % (label, angka), html)


def test_filter_get_di_kepala_kartu_dengan_tombol_sekunder():
    html = _halaman(status_filter="final")
    m = _form(html, "/admin/riset", "get")[0]
    assert 'class="admin-form-cari riset-filter"' in m.group(1)
    assert re.search(r'<select name="status">.*<option value="final" selected>Final</option>', m.group(2), re.S)
    assert 'class="admin-tombol admin-tombol-sekunder" type="submit">Terapkan' in m.group(2)
    kepala = re.search(r'<div class="admin-kartu-kepala riset-kepala-filter"><h2>Wawancara</h2>(.*?)</div>', html, re.S)
    assert kepala and "/admin/riset" in kepala.group(1)


def test_keadaan_kosong_memakai_teks_aplikasi():
    html = _halaman()
    assert "Belum ada wawancara pada filter ini." in html
    assert "Daftar muncul setelah draf wawancara dibuat, atau pilih status lainnya." in html
    assert 'class="riset-kosong"' in html


def test_daftar_wawancara_hanya_metadata_tanpa_isi_jawaban():
    html = _halaman([_item("R01", "final"), _item("R02")])
    assert html.count('class="riset-sesi"') == 2
    assert "R01" in html and "3/9 topik" in html and "Meta Ads" in html
