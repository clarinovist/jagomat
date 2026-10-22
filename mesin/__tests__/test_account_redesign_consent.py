"""Redesain /akun fase 3–4: kartu kesepakatan, /persetujuan mode tinjau, Data Pendamping.

Hanya tampilan: field form, token, guard, dan alur gate persetujuan dijaga
test_policy_*.py, test_sensor_http.py dan test_assistant_manage*.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import policy_http  # noqa: E402
import policy_pages  # noqa: E402
import policy_store  # noqa: E402
import sensor_http  # noqa: E402


# ── 3a: kartu "Kesepakatan dan pilihan data" ───────────────────────────


def _kartu(monkeypatch, pilihan=(1, 0, 1), aktif=True):
    row = dict(alur=pilihan[0], hasil=pilihan[1], chat=pilihan[2], dibuat=1700000000)
    monkeypatch.setattr("policy_http.tersedia", lambda: True)
    monkeypatch.setattr(policy_store, "baca", lambda *a: row)
    monkeypatch.setattr(policy_store, "berlaku", lambda r: True)
    monkeypatch.setattr("product_analytics_http._token", lambda *a: "token-sintetis")
    monkeypatch.setattr(
        sensor_http, "izin_akun", lambda *a: SimpleNamespace(berakhir=1800000000) if aktif else None
    )
    p = SimpleNamespace(_principal=lambda: SimpleNamespace(id_akun="sintetis"), _ambil_token=lambda: "sintetis")
    return sensor_http.form_akun(p)


def test_kartu_kesepakatan_baris_dengan_chip_status(monkeypatch):
    h = _kartu(monkeypatch, (1, 0, 1))
    assert '<span class="akun-label-st">Aktivitas penggunaan aplikasi</span><span class="akun-chip-st akun-chip-ok-st">Diizinkan</span>' in h
    assert '<span class="akun-label-st">Ringkasan hasil belajar</span><span class="akun-chip-st">Tidak diizinkan</span>' in h
    assert '<span class="akun-label-st">Kategori topik percakapan</span><span class="akun-chip-st akun-chip-ok-st">Diizinkan</span>' in h
    assert "<ul>" not in h and "Penggunaan tambahan aktif" in h


def test_kartu_kesepakatan_cabut_dilipat_tapi_form_utuh(monkeypatch):
    h = _kartu(monkeypatch)
    assert '<a class="akun-tautan-st" href="/persetujuan">Tinjau atau ubah persetujuan</a>' in h
    assert '<details class="akun-bahaya-st"><summary>Cabut izin dan hapus data tambahan</summary><form method="post" action="/analitik/sensor-cabut"' in h
    assert 'name="token" value="token-sintetis"' in h
    assert 'name="konfirmasi" value="1" required' in h and "data-konfirmasi=" in h
    assert 'class="tombol-bahaya-akun">Cabut izin dan hapus data tambahan</button>' in h


# ── 3b: /persetujuan mode tinjau ───────────────────────────────────────


def _tinjau(**kw):
    dasar = dict(pengguna="guru", token="tok-1", operasi="op-1", revisi=3, pilihan=(True, False, True),
                 dibuat=1700000000, berakhir=1800000000, aktif=True, token_cabut="tok-cabut")
    return policy_pages.halaman_tinjau(**{**dasar, **kw}).decode()


def test_tinjau_form_post_sama_dengan_gate():
    h = _tinjau()
    form = h.split('<form method="post" action="/persetujuan">', 1)[1].split("</form>", 1)[0]
    for nama, nilai in (("token", "tok-1"), ("lanjut", "/guru"), ("policy_versi", policy_store.VERSI),
                        ("policy_epoch", policy_store.EPOCH), ("policy_revisi", "3"), ("policy_operasi", "op-1")):
        assert f'<input type="hidden" name="{nama}" value="{nilai}">' in form
    assert '<button type="submit" class="tombol-utama-akun" name="policy_aksi" value="pilihan">Simpan pilihan</button>' in form
    assert 'value="semua"' not in h


def test_tinjau_checkbox_mengikuti_pilihan_tersimpan():
    h = _tinjau()
    assert re.search(r'<input type="checkbox" id="policy-alur" name="policy_alur" value="1" checked>', h)
    assert re.search(r'<input type="checkbox" id="policy-hasil" name="policy_hasil" value="1">', h)
    assert re.search(r'<input type="checkbox" id="policy-chat" name="policy_chat" value="1" checked>', h)
    assert 'for="policy-alur"' in h and "Hasil dan chat memerlukan pencatatan alur" in h


def test_tinjau_cabut_pakai_endpoint_dan_token_yang_ada():
    h = _tinjau()
    cabut = h.split('action="/analitik/sensor-cabut"', 1)[1].split("</form>", 1)[0]
    assert 'name="token" value="tok-cabut"' in cabut and 'name="konfirmasi" value="1" required' in cabut
    assert 'tombol-bahaya-akun' in cabut and "Data belajar dan percakapan asli tetap ada" in cabut


@pytest.mark.parametrize("kw,teks", [
    (dict(), "Penggunaan tambahan sedang aktif"),
    (dict(aktif=False), "Penggunaan tambahan tidak aktif"),
    (dict(pilihan=(False, False, False), aktif=False), "Penggunaan tambahan tidak diizinkan"),
])
def test_tinjau_status_menurut_izin_efektif(kw, teks):
    assert teks in _tinjau(**kw)


def test_tinjau_shell_akun_tanpa_script_dan_tautan_kembali():
    h = _tinjau()
    assert '<script' not in h and "akun-editorial-st" in h
    assert '<div class="jejak"><a href="/akun?section=akun">← Kembali ke Akun</a></div>' in h
    assert '<h1 id="judul-persetujuan">Pilihan data Anda</h1>' in h
    assert '<a class="akun-tautan-st" href="/akun?section=akun">Batal</a>' in h
    assert "/syarat-penggunaan" in h and "/kebijakan-privasi" in h


def test_tinjau_detail_memuat_paragraf_kesepakatan_verbatim():
    gate = policy_pages.bidang(revisi=0, operasi="x")
    h = _tinjau()
    for potongan in ("<b>Layanan inti:</b> aktivitas, jawaban dan hasil digunakan untuk menyediakan latihan, riwayat, "
                     "serta rekomendasi berbasis bukti. Orang tua/wali bertanggung jawab memberi izin penggunaan data anak.",
                     "Tidak menyalin teks mentah atau mengirim data ke AI untuk analitik; "
                     "bukan untuk iklan atau pelatihan model pihak ketiga."):
        assert potongan in gate and potongan in h


def test_gate_tidak_berubah_dan_tetap_dipakai_tanpa_izin(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi.json")
    auth.simpan_sandi("sandi-sintetis-12345", "guru", tmp_path / "sandi.json")
    akun = auth.cari_akun("guru")
    p = SimpleNamespace(pengguna="guru", id_akun=akun["id_akun"], revisi_auth=akun["revisi_auth"])
    pen = SimpleNamespace(_ambil_token=lambda: "sesi-sintetis")
    monkeypatch.setattr("policy_http.tersedia", lambda: True)
    monkeypatch.setattr(policy_http, "sensor_http", SimpleNamespace(izin_akun=lambda *a: None))
    monkeypatch.setattr("product_analytics_http._token", lambda *a: "tok-cabut")
    row = dict(alur=1, hasil=0, chat=0, dibuat=1700000000, revisi=2)
    monkeypatch.setattr(policy_store, "baca", lambda *a: None)
    assert "Satu persetujuan, lalu lanjut belajar" in policy_http.halaman(pen, p).decode()
    monkeypatch.setattr(policy_store, "baca", lambda *a: row)
    monkeypatch.setattr(policy_store, "berlaku", lambda r: False)
    assert "Satu persetujuan, lalu lanjut belajar" in policy_http.halaman(pen, p).decode()
    monkeypatch.setattr(policy_store, "berlaku", lambda r: True)
    h = policy_http.halaman(pen, p).decode()
    assert "Pilihan data Anda" in h and "Satu persetujuan" not in h
    assert 'name="policy_revisi" value="2"' in h
