"""Sepuluh perjalanan onboarding sintetis desktop/mobile sampai laporan."""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
import secrets

import pytest

import admin_registration
import auth
import database
import sessions
from http_test_kit import ServerUji
from test_admin_http_c import _minta


class Struktur(HTMLParser):
    def __init__(self, sumber):
        super().__init__()
        self.elemen = []
        self._stack = []
        self.feed(sumber)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.elemen.append((tag, data))
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self._stack:
            self._stack.reverse(); self._stack.remove(tag); self._stack.reverse()

    def semua(self, tag):
        return [a for t, a in self.elemen if t == tag]


@dataclass(frozen=True)
class BuktiPerjalanan:
    viewport: str
    nomor: int
    tahapan: tuple
    cta_utama: tuple


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("admin-onboarding", "sandi-admin-onboarding", "admin")
    admin_registration.migrasikan_profil_registrasi(database.BAWAAN)
    yield s
    s.berhenti()


def _token_daftar(html):
    return re.search(r'name="token_form" value="([^"]+)"', html).group(1)


def _satu_cta(html, penanda):
    assert html.count(penanda) == 1, penanda
    return penanda


def _cek_viewport(html, viewport):
    struktur = Struktur(html)
    assert any(a.get("name") == "viewport" and "width=device-width" in a.get("content", "")
               for a in struktur.semua("meta"))
    if viewport == "mobile":
        assert 'max-width: 40rem' in html
    else:
        assert 'grid-template-columns' in html


def _jalan(server, viewport, nomor):
    kode, landing, _ = server.minta("/")
    assert kode == 200
    _satu_cta(landing, 'class="tombol-coral"')
    assert "Buat akun pendamping." in landing
    _cek_viewport(landing, viewport)

    kode, daftar, _ = server.minta("/daftar")
    assert kode == 200, daftar[:500]
    _satu_cta(daftar, 'class="masuk-tombol-st" type="submit"')
    _cek_viewport(daftar, viewport)
    nama = "akses-%s-%02d-%s" % (viewport, nomor, secrets.token_hex(2))
    sandi = "sandi-onboarding-%s-%02d" % (viewport, nomor)
    data = {
        "nama": nama, "sandi": sandi, "nama_anak": "Anak-%02d" % nomor,
        "kelas_sekolah": "4", "setuju": "1", "token_form": _token_daftar(daftar),
    }
    kode, _isi, header = _minta(server, "/daftar", data=data)
    assert kode == 303
    login = (nama, sandi)
    with server.buka() as kon:
        siswa_id = int(kon.execute("SELECT id FROM siswa WHERE pemilik=?", (nama,)).fetchone()[0])
    assert header["Location"] == "/anak/%d?section=rencana" % siswa_id

    kode, ruang, _ = server.minta(header["Location"], auth=login)
    assert kode == 200
    assert "Langkah berikutnya" in ruang
    assert "Mulai dengan latihan awal" in ruang
    assert "Perkiraan sekitar 45 menit" in ruang
    assert "Jagomat menampilkan catatan awal setelah hasil diperiksa" in ruang
    _satu_cta(ruang, ">Siapkan latihan awal</button>")
    assert 'action="/sesi-baru/%d"' % siswa_id not in ruang

    kode, _selesai, _ = server.minta(
        "/siklus/%d/buat" % siswa_id, auth=login, data={},
    )
    assert kode == 200
    with server.buka() as kon:
        sesi_id = int(kon.execute(
            "SELECT id FROM sesi WHERE siswa_id=? ORDER BY id DESC LIMIT 1", (siswa_id,)
        ).fetchone()[0])
        butir = database.isi_sesi(kon, sesi_id)
        assert len(butir) == 15

    akun_murid = "murid-%s-%02d" % (viewport, nomor)
    sandi_murid = "sandi-murid-%s-%02d" % (viewport, nomor)
    auth.tambah_akun(akun_murid, sandi_murid, "murid", siswa_id=siswa_id)
    principal_murid = auth.autentikasi(akun_murid, sandi_murid)
    cookie_murid = sessions.buat_dari_principal(principal_murid)
    kode, murid, _ = server.minta("/murid/kerjakan/%d" % sesi_id, cookie=cookie_murid)
    assert kode == 200
    rendah_murid = murid.lower()
    for rahasia in ("malrule", "kode diagnosis", "laporan perkembangan", "kunci jawaban"):
        assert rahasia not in rendah_murid
    kode, lembar, _ = server.minta("/lembar/%d" % sesi_id, auth=login)
    assert kode == 200
    assert "Lembar jawaban / penilaian" not in lembar and "malrule_id" not in lembar

    with server.buka() as kon:
        revisi = __import__("student_submissions").revisi(kon, sesi_id)
    jawaban_murid = {
        **{"jwb_%d" % b["sesi_soal_id"]: b["kunci"] for b in butir},
        **{"cara_%d" % b["sesi_soal_id"]: "Langkah sintetis" for b in butir},
        "aksi": "selesai", "revisi_pekerjaan": str(revisi), "flow_kosong": "1",
    }
    kode, selesai_murid, _ = server.minta(
        "/murid/kerjakan/%d" % sesi_id, cookie=cookie_murid, data=jawaban_murid)
    assert kode == 200 and "sudah masuk" in selesai_murid

    kode, tinjau, _ = server.minta("/sesi/%d" % sesi_id, auth=login)
    assert kode == 200
    _satu_cta(tinjau, 'formaction="/sesi/%d/konfirmasi"' % sesi_id)
    payload = {}
    with server.buka() as kon:
        for b in database.isi_sesi(kon, sesi_id):
            payload["jwb_%d" % b["sesi_soal_id"]] = b["kunci"]
            payload["cara_%d" % b["sesi_soal_id"]] = "Langkah sintetis"
            payload["kode_%d" % b["sesi_soal_id"]] = "benar"
            payload["cek_pemahaman_%d" % b["sesi_soal_id"]] = "bisa_menjelaskan"
    kode, hasil, header = server.minta(
        "/sesi/%d/konfirmasi" % sesi_id, auth=login, data=payload)
    assert kode == 200
    assert "Langkah pertama selesai" in hasil
    assert "Latihan awal 1 dari 3 selesai" in hasil
    assert "belum cukup untuk menyimpulkan" in hasil
    kode, laporan, _ = server.minta("/laporan/%d" % siswa_id, auth=login)
    assert kode == 200
    assert "Laporan perkembangan" in laporan
    assert laporan.count('class="tombol aksi-rencana-laporan"') == 1
    _cek_viewport(laporan, viewport)
    return BuktiPerjalanan(
        viewport, nomor,
        ("landing", "daftar", "langkah berikutnya", "siapkan latihan awal", "latihan pertama",
         "lembar aman", "masukkan hasil", "tinjau-konfirmasi", "laporan", "kembali besok"),
        ("Buat akun pendamping.", "Buat akun", "Siapkan latihan awal",
         "Konfirmasi hasil", "aksi-rencana-laporan"),
    )


@pytest.mark.parametrize("viewport", ("desktop", "mobile"))
@pytest.mark.parametrize("nomor", range(1, 6))
def test_sepuluh_perjalanan_onboarding_lengkap(server, viewport, nomor):
    bukti = _jalan(server, viewport, nomor)
    assert len(bukti.tahapan) == 10
    assert len(bukti.cta_utama) == 5
