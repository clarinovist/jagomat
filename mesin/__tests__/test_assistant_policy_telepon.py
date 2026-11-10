"""Kebijakan teks Pendamping: nomor telepon boleh, email dan credential tetap ditolak."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_policy  # noqa: E402


# Nomor palsu untuk test, bukan nomor sungguhan.
TELEPON_DITERIMA = (
    "Hubungi saya di 081234567890",
    "Nomorku +62 812-3456-7890",
    "WA: 0812 3456 7890",
)

DITOLAK = (
    "hubungi aku di orang@example.test",
    "Authorization: Bearer token-rahasia-panjang",
    "api_key=sk-contoh-rahasia-panjang",
)


@pytest.mark.parametrize("teks", TELEPON_DITERIMA)
def test_pastikan_teks_aman_menerima_nomor_telepon(teks):
    assert assistant_policy.pastikan_teks_aman(teks) == teks


@pytest.mark.parametrize("teks", DITOLAK)
def test_pastikan_teks_aman_tetap_menolak_email_dan_credential(teks):
    with pytest.raises(ValueError, match="email atau credential"):
        assistant_policy.pastikan_teks_aman(teks)


def test_pastikan_teks_aman_menolak_email_walau_ada_telepon():
    with pytest.raises(ValueError, match="email atau credential"):
        assistant_policy.pastikan_teks_aman("081234567890 atau orang@example.test")


def _teks(halaman: bytes) -> str:
    return " ".join(halaman.decode("utf-8").split())


def test_halaman_persetujuan_tidak_melarang_telepon_tapi_tetap_melarang_email_dan_sandi():
    import assistant_pages

    teks = _teks(assistant_pages.halaman_persetujuan())

    assert "Jangan menulis email, sandi, token" in teks
    assert "email, nomor telepon" not in teks
    assert "DeepSeek" in teks
    assert "Nomor telepon yang kamu tulis ikut terkirim" in teks


def test_panel_persetujuan_tidak_melarang_telepon_tapi_tetap_melarang_email_dan_sandi():
    import assistant_components
    import assistant_inline

    panel = assistant_components.panel_persetujuan(
        assistant_inline.tujuan_anak(7), sumber={"label": "Ringkasan anak", "level": "P3"}
    )
    teks = _teks(panel.encode("utf-8"))

    assert "Jangan tulis email, sandi, token" in teks
    assert "kontak, sandi" not in teks
    assert "DeepSeek" in teks
    assert "Nomor telepon yang ditulis ikut terkirim" in teks


def test_kebijakan_publik_tidak_melarang_telepon_di_chat_tapi_menyebut_ikut_terkirim():
    import landing

    teks = _teks(landing.halaman_kebijakan())

    assert "Jangan menulis email, sandi, token" in teks
    assert "Jangan menulis email, nomor telepon" not in teks
    assert "nomor telepon yang ditulis ikut terkirim" in teks
