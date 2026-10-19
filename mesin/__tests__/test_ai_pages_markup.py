"""Kontrak markup halaman Pengaturan AI setelah redesain: form, pengaman, struktur."""

from __future__ import annotations

from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_pages  # noqa: E402
import ai_policy  # noqa: E402
import ai_store  # noqa: E402

FORM_PENGATURAN = re.compile(r'<form method="post" action="/admin/ai/pengaturan">(.*?)</form>', re.S)
FORM_UJI = re.compile(r'<form method="post" action="/admin/ai/uji">(.*?)</form>', re.S)


@pytest.fixture()
def render(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sintetis-bukan-rahasia")
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    berkas = tmp_path / "ai.db"
    monkeypatch.setenv("AI_BERKAS_DB", str(berkas))
    ai_store.siapkan(berkas)

    def _render(sql=None):
        if sql:
            with ai_store.buka(berkas) as kon:
                kon.execute(sql)
        return ai_pages.halaman(
            berkas, pengguna="Pengelola Demo", csrf="csrf-sintetis",
            tinjauan_pengaturan="tinjauan-pengaturan-sintetis",
            tinjauan_uji="tinjauan-uji-sintetis",
        ).decode()

    return _render


def _utama(isi):
    """Isi <main> saja; form Keluar milik kerangka tidak ikut dihitung."""
    return isi.split("<main", 1)[1].split("</main>", 1)[0]


def _nama(form, tag):
    return re.findall(r'<%s\b[^>]*\bname="([^"]+)"' % tag, form)


def test_hanya_dua_form_dan_dua_tombol_kirim(render):
    isi = _utama(render())
    assert isi.count('<form ') == 2
    assert len(FORM_PENGATURAN.findall(isi)) == 1 and len(FORM_UJI.findall(isi)) == 1
    assert len(re.findall(r'<button\b', isi)) == 2
    assert 'Hentikan panggilan AI</button>' not in isi


def test_dihentikan_hanya_checkbox_di_dalam_form_pengaturan(render):
    isi = _utama(render())
    form = FORM_PENGATURAN.search(isi).group(1)
    assert len(re.findall(r'name="dihentikan"', isi)) == 1
    assert re.search(r'<input type="checkbox" name="dihentikan" value="1"', form)
    assert 'class="admin-galat admin-henti"' in form
    assert "Permintaan yang sudah dikirim mungkin tetap selesai dan dikenai biaya." in form
    assert "Perubahan ini diterapkan bersama tombol Simpan pengaturan AI." in form


def test_dihentikan_tercentang_mengikuti_konfigurasi(render):
    isi = render("UPDATE konfigurasi SET dihentikan=1")
    assert 'name="dihentikan" value="1" checked' in FORM_PENGATURAN.search(isi).group(1)


def test_field_tersembunyi_dan_reauth_form_pengaturan(render):
    form = FORM_PENGATURAN.search(render()).group(1)
    assert 'name="csrf" value="csrf-sintetis"' in form
    assert 'name="tinjauan" value="tinjauan-pengaturan-sintetis"' in form
    assert re.search(r'<input type="hidden" name="revisi" value="1">', form)
    assert re.search(r'<input type="password" name="reauth" required autocomplete="current-password">', form)
    assert form.count('type="submit"') == 1


def test_form_uji_menjaga_konfirmasi_dan_reauth(render):
    form = FORM_UJI.search(render()).group(1)
    assert 'name="tinjauan" value="tinjauan-uji-sintetis"' in form
    assert re.search(r'<input type="checkbox" name="konfirmasi" value="1" required>', form)
    assert "memakai kuota dan dapat menimbulkan biaya" in form
    assert re.search(r'name="reauth" required', form)
    assert sorted(_nama(form, "input")) == ["csrf", "konfirmasi", "reauth", "tinjauan"]


def test_pagu_tetap_number_desimal_titik_dan_required(render):
    form = FORM_PENGATURAN.search(render()).group(1)
    for fitur in ("global", *ai_policy.FITUR):
        for periode in ("harian", "bulanan"):
            tag = re.search(r'<input name="%s_%s"[^>]*>' % (periode, fitur), form).group(0)
            assert 'type="number"' in tag and 'min="0"' in tag and 'step="0.01"' in tag
            assert " required" in tag and re.search(r'value="\d+\.\d{2}"', tag)
    for fitur in ai_policy.FITUR:
        assert 'name="aktif_%s" value="1"' % fitur in form
    assert 'name="aktif_global"' not in form
    for nama in ("request_akun_harian", "uji_harian", "uji_cooldown_menit"):
        assert re.search(r'<input name="%s" type="number" min="0"[^>]* required>' % nama, form)


def test_pagu_dikelompokkan_per_fitur_dengan_grid_dua_kolom(render):
    form = FORM_PENGATURAN.search(render()).group(1)
    assert form.count('class="admin-ai-pagu"') == 5
    assert form.count('class="admin-ai-grup"') == 6  # global + 4 fitur + batas lain
    assert "Pagu 0 berarti tidak diizinkan" in render()


def test_status_fitur_berbentuk_badge_dengan_teks_alasan_penuh(render):
    isi = render()
    assert isi.count('<span class="admin-badge bien">Aktif</span>') == 4
    henti = render("UPDATE konfigurasi SET dihentikan=1")
    assert 'class="admin-badge perhatian">Tertahan: dihentikan</span>' in henti
    nol = render("UPDATE batas_fitur SET batas_harian=0 WHERE fitur='cerita'")
    assert "Tertahan: dihentikan, pagu nol" in nol


def test_tabel_pemakaian_dua_kolom_dengan_th_scope(render):
    isi = render()
    for judul in ("Fitur", "Status", "Model", "Pagu/hari", "Pagu/bulan", "Terpakai hari ini", "Terpakai bulan ini"):
        assert '<th scope="col"' in isi and ">%s</th>" % judul in isi
    assert isi.count("USD 0,0000") >= 8
    assert 'class="admin-tabel-wrap"' in isi


def test_status_layanan_dan_catatan_akurat_dipertahankan(render):
    isi = render()
    assert 'class="admin-ai-status"' in isi
    assert "tersedia" in isi.lower() and "DeepSeek" in isi
    assert "USD 100,00" in isi and "USD 1,00/hari" in isi and "USD 20,00/bulan" in isi
    assert "Biaya di halaman ini adalah perhitungan aplikasi, bukan tagihan provider." in isi
    assert "Izin admin tidak menggantikan izin deployment atau persetujuan keluarga." in isi
    assert "Belum ada perubahan." in isi


def test_kredensial_belum_tersedia_memakai_badge_perhatian(render, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert 'class="admin-badge perhatian">Belum tersedia</span>' in render()
