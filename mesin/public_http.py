"""Halaman HTTP publik tanpa data keluarga.

Modul ini memilih renderer publik dan proyeksi konfigurasi dukungan minimum.
Primitive respons dan keputusan identitas tetap milik ``web.Penangan``.
"""
from __future__ import annotations


def tangani_get(penangan, jalur: str) -> bool:
    """Tangani landing, laporan riset, privasi, dan panduan lupa sandi."""
    # Impor modul menjaga monkeypatch renderer publik pada lookup runtime.
    import landing

    if jalur in (
        "/riset/persaingan-bimbel-2026",
        "/riset/persaingan-bimbel-2026.pdf",
    ):
        import competitive_research

        if jalur.endswith(".pdf"):
            competitive_research.kirim_pdf(penangan)
        else:
            penangan._kirim(competitive_research.halaman())
        return True

    if jalur == "/":
        ident = penangan._identitas()
        if ident and ident[1] in ("guru", "admin"):
            return False
        import admin_store
        import support_settings

        penangan._kirim(landing.halaman_landing(
            dukungan=support_settings.baca_publik(admin_store.BAWAAN)
        ))
        return True

    if jalur == "/aset" or jalur.startswith("/aset/"):
        # Penangan mempertahankan allow-list, MIME, cache, dan header transport.
        nama = jalur[len("/aset/"):] if len(jalur) > 5 else ""
        penangan._kirim_aset(nama)
        return True

    if jalur == "/kebijakan-privasi":
        import admin_store
        import support_settings

        penangan._kirim(landing.halaman_kebijakan(
            dukungan=support_settings.baca_publik(admin_store.BAWAAN)
        ))
        return True

    if jalur == "/lupa-sandi":
        import admin_store
        import support_settings

        penangan._kirim(landing.halaman_lupa_sandi(
            dukungan=support_settings.baca_publik(admin_store.BAWAAN)
        ))
        return True

    return False
