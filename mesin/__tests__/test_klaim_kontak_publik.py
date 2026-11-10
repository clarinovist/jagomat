"""Klaim publik soal email/telepon tetap jujur setelah nomor telepon boleh ditulis di chat Pendamping."""

from __future__ import annotations

import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import landing  # noqa: E402
import subscription_produksi_pages as halaman_langganan  # noqa: E402


def _teks(isi) -> str:
    mentah = isi.decode("utf-8") if isinstance(isi, bytes) else isi
    return re.sub(r"\s+", " ", mentah)


def _kebijakan() -> str:
    return _teks(landing.halaman_kebijakan())


def test_kebijakan_tidak_lagi_klaim_tanpa_nomor_telepon():
    teks = _kebijakan()
    assert "Tidak ada email, nomor telepon, atau alamat" not in teks


def test_kebijakan_data_tidak_dikumpulkan_jujur_soal_telepon_di_chat():
    teks = _kebijakan()
    assert "Aplikasi tidak meminta email atau alamat." in teks
    assert ("Nomor telepon hanya tersimpan bila Anda menuliskannya sendiri "
            "di chat Pendamping.") in teks


def test_kebijakan_tetap_menolak_email_dan_mengungkap_deepseek():
    teks = _kebijakan()
    assert "Jangan menulis email, sandi, token" in teks
    assert "mengirim isi chat ke DeepSeek" in teks


def test_bantuan_langganan_tidak_klaim_tanpa_nomor_telepon():
    teks = _teks(halaman_langganan._bantuan())
    assert "tidak menyimpan email atau nomor telepon" not in teks
    assert "Aplikasi ini tidak menyimpan email." in teks
    assert ("Nomor telepon hanya tersimpan bila kamu menuliskannya sendiri "
            "di chat Pendamping.") in teks


def test_klaim_pendaftaran_tanpa_kontak_tetap_benar():
    """Registrasi memang tidak meminta kontak; klaim ini tidak boleh ikut berubah."""
    assert "Tidak perlu email atau nomor telepon." in _teks(landing.halaman_daftar())
