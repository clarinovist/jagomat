"""Pembantu bersama tes pesanan dari akun anak (murid): akun murid bertaut siswa, sakelar anak hidup.

Dipakai `test_pesanan_murid_http.py` dan `test_pesanan_murid_purna.py`. Semua data sintetis; server dan
provider palsu dari `pesanan_http_kit`.
"""
from __future__ import annotations

import pytest

import auth
import cek_gratis
import kontak_akun
import purna
from cek_gratis_kit import jawab, tandai_selesai
from pesanan_http_kit import WA_SINTETIS, WAKTU_AWAL

M = "/murid/pesanan"
SANDI = "sandi-murid-sintetis-123"
NAMA_ANAK_A = "Anak Murid Alfa"
NAMA_ANAK_B = "Anak Murid Beta"
KATA_TERLARANG = ("malrule", "diagnosis", "kode_final", "persentil", "peringkat", "kunci jawaban")
SELESAI = "2026-11-18T09:30:00"


class Murid:
    def __init__(self, akun, id_akun, siswa_id):
        self.akun, self.id_akun, self.siswa_id = akun, id_akun, siswa_id


def buat_murid(server, nama, nama_anak, *, cek=True, kontak=True):
    """Akun murid bertaut ke siswa baru (pemilik koordinator sintetis), cek selesai + kontak opsional."""
    with server.buka() as kon:
        siswa = cek_gratis_kit_tambah(kon, nama_anak)
    principal = auth.tambah_akun_dan_principal(nama, SANDI, "murid", siswa_id=siswa)
    if cek:
        with server.buka() as kon:
            cek_gratis.mulai(kon, principal.id_akun, siswa, "koordinator-sintetis", True, WAKTU_AWAL, seed=7)
            sesi = kon.execute("SELECT sesi_id FROM cek_gratis WHERE id_akun=?", (principal.id_akun,)).fetchone()[0]
            jawab(kon, sesi, semua_benar=10)
            tandai_selesai(kon, sesi)
            assert cek_gratis.selesaikan_jika_siap(kon, principal.id_akun, WAKTU_AWAL)
    if kontak:
        with server.buka() as kon:
            kon.execute("BEGIN IMMEDIATE")
            kontak_akun.simpan(kon, principal.id_akun, WA_SINTETIS, "2026-11-18T09:00:00")
            kon.commit()
    return Murid((nama, SANDI), principal.id_akun, siswa)


def cek_gratis_kit_tambah(kon, nama_anak):
    from cek_gratis_kit import tambah_anak
    return tambah_anak(kon, nama_anak, "koordinator-sintetis", 4)


@pytest.fixture()
def sakelar_hidup(monkeypatch, tmp_path):
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")


# Keadaan purna sintetis (order lunas yang sudah terlambat dan belum memilih) untuk tes renderer kartu voucher.
KEADAAN_TERLAMBAT = purna.KeadaanPurna(
    lunas=True, direfund=False, waktu_lunas="2026-11-18T10:00:00", kode="JGV-ABCDEF123456",
    voucher=purna.VOUCHER_AKTIF, berlaku_hingga="2027-02-16T10:00:00", janji_terbit="2026-11-20T10:00:00",
    batas_pilihan="2026-11-23T10:00:00", terbit=None, terlambat=True, pilihan=None, bisa_pilih=True, dipakai=False,
    ditahan=False)
