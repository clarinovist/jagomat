"""Kontrak image: image membawa seluruh paket, bukan daftar manual.

Riwayat 25 Agustus 2026: render.py, gaya_*.py, students.py, dan llm.py lahir
tanpa dimasukkan ke COPY Dockerfile. Semua test lolos di lokal (filenya
ada), build GitHub Actions juga hijau — lalu deploy gagal sehat karena
import error DI DALAM container, dan rollback otomatis menyembunyikan
penyebabnya.

Sejak A4 akar masalahnya dihapus: Dockerfile menyalin `*.py` wildcard, jadi
modul baru otomatis ikut. Dua guard lama (transitif-per-impor dan daftar
titik masuk) dihapus — keduanya membaca daftar manual yang sudah tidak ada.
Penegakan kini dua arah:

  - test_copy_dockerfile_paket_utuh_wildcard  — wildcard wajib, daftar
    manual ditolak (lengkap ataupun tidak);
  - test_semua_modul_root_yang_diimpor_tersalin_wildcard — seluruh modul
    lokal yang diimpor titik masuk benar-benar ada sebagai .py di root,
    sehingga wildcard pasti membawanya.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent

# Titik masuk & modul inti yang pasti dibutuhkan saat container jalan.
# rekonsiliasi_langganan.py dijalankan di container via `docker exec` (worker
# terjadwal), jadi rantai impornya juga wajib berada di root repo.
TITIK_MASUK = ("serve.py", "web.py", "healthcheck.py", "rekonsiliasi_langganan.py")


def _impor_lokal(blok: str) -> set[str]:
    """Nama modul .py lokal yang diimpor dari sebuah berkas.

    Hanya impor level-atas bentuk `import x` / `from x import ...` yang
    cocok dengan berkas di root — impor stdlib/pytest otomatis tereliming
    karena tidak punya berkasnya.
    """
    hasil: set[str] = set()
    for m in re.finditer(
        r"^\s*(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)", blok, flags=re.M
    ):
        nama = m.group(1)
        if (ROOT / f"{nama}.py").exists():
            hasil.add(f"{nama}.py")
    return hasil


def test_copy_dockerfile_paket_utuh_wildcard():
    """Kontrak A4 (keputusan desain #6): daftar COPY manual adalah sumber
    insiden 25 Aug — modul baru lahir, lupa didaftarkan, semua test lokal
    hijau, lalu deploy gagal sehat dan rollback menyembunyikan penyebabnya.
    Daftar manual diganti `COPY *.py`: modul apa pun yang ada di root repo
    otomatis ada di image. Guard ini merah bila ada yang mengembalikan
    Dockerfile ke daftar manual (lengkap ataupun tidak)."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    blok = re.search(r"COPY --chown=osn:osn(.*?)\n\n", dockerfile, flags=re.S)
    assert blok, "blok COPY tidak ditemukan di Dockerfile"
    assert "*.py" in blok.group(1), (
        "Dockerfile harus menyalin paket utuh lewat 'COPY ... *.py /app/' — "
        "daftar modul manual adalah sumber insiden deploy 25 Aug"
    )
    nama_eksplisit = re.findall(r"([a-z_]+\.py)", blok.group(1))
    assert not nama_eksplisit, (
        f"COPY masih menyebut modul manual: {nama_eksplisit} — pakai *.py"
    )


def test_helper_readiness_admin_ikut_wildcard_tanpa_state_privat():
    """Helper F harus tersedia di image tanpa COPY manual atau data backup."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert (ROOT / "admin_backup.py").is_file()
    assert "COPY --chown=osn:osn *.py /app/" in dockerfile
    assert "admin_backup.py" not in dockerfile
    perintah_copy = "\n".join(
        baris for baris in dockerfile.splitlines()
        if baris.lstrip().startswith("COPY ")
    )
    assert "sandi.json" not in perintah_copy
    assert "sesi.json" not in perintah_copy
    assert "admin-control.db" not in perintah_copy
    assert "admin-drafts.db" not in perintah_copy


def test_semua_modul_root_yang_diimpor_tersalin_wildcard():
    """Wildcard menyalin semua .py root — pastikan tidak ada modul lokal
    yang diimpor titik masuk tapi TIDAK berada di root (subfolder/spesifik
    build): itu yang tetap lolos dari wildcard dan gagal di container."""
    diperiksa: set[str] = set()
    antre: list[str] = list(TITIK_MASUK)
    while antre:
        berkas = antre.pop()
        if berkas in diperiksa:
            continue
        diperiksa.add(berkas)
        assert (ROOT / berkas).exists(), f"{berkas} hilang dari root repo"
        for modul in _impor_lokal((ROOT / berkas).read_text(encoding="utf-8")):
            assert (ROOT / modul).exists(), (
                f"{modul} diimpor {berkas} tapi tidak ada sebagai .py root — "
                "wildcard COPY tidak akan membawanya"
            )
            antre.append(modul)
