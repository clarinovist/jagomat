"""Halaman admin antrean dan detail Paket Belajar (murni render, data sintetis)."""
import re
from pathlib import Path

import kelas_admin_pages as ui
import paket_belajar_katalog as k

ORDER = "kls_" + "b" * 32
BUKTI_ID = "c" * 32
FORMS = {"setujui": ("csrf-s", "tinjauan-s"), "tolak": ("csrf-t", "tinjauan-t")}
SOROT = '<mark class="admin-digit-unik">427</mark>'


def _item(kode=k.KODE_PRIVATE, total=591_427, siswa=7654321):
    return k.ItemAntrean(ORDER, siswa, kode, total, "2026-11-24T03:00:00")


def _tagihan(status=k.STATUS_MENUNGGU):
    r = k.hitung_rincian(k.KODE_PRIVATE, deposit_aktif=True, anak_kedua=False)
    return k.TagihanKelas(ORDER, k.KODE_PRIVATE, r, 427, r.nominal + 427, status, "2026-11-25T03:00:00", 1, None)


def _bukti(**kw):
    dasar = dict(id=BUKTI_ID, waktu="2026-11-24T03:00:00", ukuran=2049, mime="image/png")
    return ui.BuktiView(**{**dasar, **kw})


def _teks(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_antrean_memuat_paket_nominal_tersorot_dan_tautan_detail():
    html = ui.halaman_antrean([_item(), _item(k.KODE_MINI, 201_427)])
    assert "Private" in html and "Mini Class" in html
    assert "Rp591." + SOROT in html and "Rp201." + SOROT in html
    assert f'href="/admin/kelas/verifikasi?order={ORDER}"' in html


def test_antrean_kosong_dan_pesan_ter_escape():
    html = ui.halaman_antrean([], pesan="<script>x</script>")
    assert "Tidak ada" in _teks(html)
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_antrean_dan_detail_tidak_memuat_id_anak():
    assert "7654321" not in ui.halaman_antrean([_item()])
    assert "7654321" not in ui.halaman_detail(_item(), _tagihan(), [_bukti()], FORMS)


def test_detail_menunggu_punya_form_setujui_tanpa_alasan_dan_tolak_wajib_alasan():
    html = ui.halaman_detail(_item(), _tagihan(), [_bukti()], FORMS)
    setujui = html.split('action="/admin/kelas/setujui"')[1].split("</form>")[0]
    assert 'name="alasan"' not in setujui
    assert 'name="csrf" value="csrf-s"' in setujui and 'name="tinjauan" value="tinjauan-s"' in setujui
    tolak = html.split('action="/admin/kelas/tolak"')[1].split("</form>")[0]
    assert 'name="alasan"' in tolak and "required" in tolak and 'value="tinjauan-t"' in tolak
    assert 'name="reauth"' in setujui and 'name="reauth"' in tolak


def test_detail_tanpa_form_bila_bukan_menunggu_atau_tanpa_sesi():
    assert "<form" not in ui.halaman_detail(_item(), _tagihan(k.STATUS_AKTIF), [_bukti()], FORMS)
    html = ui.halaman_detail(_item(), _tagihan(), [_bukti()], None, baca_saja=True)
    assert "<form" not in html and "baca-saja" in html


def test_detail_rincian_nominal_dan_bukti():
    bukti = [_bukti(), _bukti(id="d" * 32, mime="application/pdf", ukuran=10)]
    html = ui.halaman_detail(_item(), _tagihan(), bukti, FORMS)
    teks = _teks(html)
    assert "Rp640.000" in teks and "Rp49.000" in teks and "Rp591." + SOROT in html
    assert "3 KB" in teks and "PNG" in teks and "PDF" in teks
    assert f"/admin/kelas/bukti?id={BUKTI_ID}" in html


def test_detail_id_bukti_bukan_hex_tidak_dirender_mentah():
    html = ui.halaman_detail(_item(), _tagihan(), [_bukti(id="../etc<x>")], FORMS)
    assert "../etc" not in html and "<x>" not in html


def test_detail_tanpa_bukti_tidak_pecah():
    assert "Belum ada bukti" in _teks(ui.halaman_detail(_item(), _tagihan(), [], FORMS))


def test_admin_tanpa_kata_terlarang_dan_tanpa_hex():
    html = ui.halaman_antrean([_item()]) + ui.halaman_detail(_item(), _tagihan(), [_bukti()], FORMS)
    for kata in ("malrule", "diagnosis", "kunci"):
        assert kata not in _teks(html).lower()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", Path(ui.__file__).read_text())


def test_rute():
    assert ui.RUTE == "/admin/kelas" and ui.RUTE_SETUJUI == "/admin/kelas/setujui"
