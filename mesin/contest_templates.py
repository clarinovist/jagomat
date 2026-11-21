"""Pemuat template Latihan Lomba: satu modul per topik, terdaftar saat diimpor."""
from __future__ import annotations

import contest_templates_arithmetic  # noqa: F401
import contest_templates_geometry  # noqa: F401
import contest_templates_measurement  # noqa: F401
import contest_templates_number  # noqa: F401
from contest_core import Template, semua


def katalog() -> "tuple[Template, ...]":
    """Seluruh template terdaftar, terurut menurut id."""
    return semua()
