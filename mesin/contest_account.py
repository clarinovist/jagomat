"""Mode Lomba di halaman akun Guru (`/akun?section=siswa`): status + tombol Aktifkan/Matikan per anak.

Hanya tampil saat sakelar induk `OSN_LOMBA` hidup. Aksi `mode_lomba` hanya mengubah `aktif`; target harian dan
hitung mundur yang sudah diatur di `/anak/<id>/lomba` dipertahankan. Kepemilikan: Guru hanya anaknya sendiri,
admin semua (pola aksi ber-id lain di `account_pages.proses_akun`); bukan milik -> pesan generik tanpa tulis.
SQL penugasan tetap milik `contest_assignment_store`.
"""
from __future__ import annotations

import html
import time
from typing import Mapping, Tuple

import contest_assignment_store as AS
import contest_gate
import database

AKSI = "mode_lomba"
SECTION = "siswa"
_NILAI_AKTIF = {"1": True, "0": False}
_KOLOM_SAH = frozenset({"aksi", "siswa_id", "aktif", "section"})
_GALAT_SISWA = "Siswa tidak dikenal."
_GALAT_ISIAN = "Form Mode Lomba tidak sah. Muat ulang halaman."
_GALAT_MATI = "Mode Lomba sedang dimatikan admin."
MAKS_ID = 9_223_372_036_854_775_807


def _alamat_atur(siswa_id: int) -> str:
    return f"/anak/{int(siswa_id)}/lomba"


def bagian_kartu(kon, siswa_id: int, nama: str) -> str:
    """Baris Mode Lomba di kartu anak; kosong bila sakelar induk mati."""
    if not contest_gate.aktif():
        return ""
    aktif = contest_gate.penugasan_aktif(kon, siswa_id)
    nama_aman = html.escape(nama)
    status = "Aktif" if aktif else "Belum aktif"
    kelas = "akun-lomba-aktif" if aktif else "akun-lomba-mati"
    tombol = "Matikan" if aktif else "Aktifkan"
    return (
        f'<div class="akun-lomba-st" aria-label="Mode Lomba {nama_aman}">'
        f'<span class="akun-chip-st {kelas}">Mode Lomba: {status}</span>'
        '<form method="post" action="/akun" class="akun-form-aksi">'
        f'<input type="hidden" name="aksi" value="{AKSI}">'
        f'<input type="hidden" name="siswa_id" value="{int(siswa_id)}">'
        f'<input type="hidden" name="aktif" value="{"0" if aktif else "1"}">'
        f'<input type="hidden" name="section" value="{SECTION}">'
        f'<button type="submit" class="tombol-sekunder" aria-label="{tombol} Mode Lomba untuk {nama_aman}">'
        f'{tombol}</button></form>'
        f'<a class="akun-lomba-atur" href="{_alamat_atur(siswa_id)}">Atur target &amp; riwayat</a></div>')


def _siswa_id(mentah) -> int:
    try:
        nilai = int(str(mentah))
    except (TypeError, ValueError):
        return 0
    return nilai if 0 < nilai <= MAKS_ID else 0


def proses(kon, data: Mapping[str, str], pengguna: str, peran: str) -> Tuple[str, str]:
    """(pesan, galat) untuk aksi `mode_lomba`; menulis hanya bila semua palang lolos."""
    if not contest_gate.aktif():
        return "", _GALAT_MATI
    siswa_id = _siswa_id(data.get("siswa_id"))
    baris = kon.execute("SELECT nama FROM siswa WHERE id = ?", (siswa_id,)).fetchone() if siswa_id else None
    if baris is None or (peran != "admin" and not database.siswa_milik(kon, siswa_id, pengguna)):
        return "", _GALAT_SISWA
    if set(data) - _KOLOM_SAH or data.get("aktif") not in _NILAI_AKTIF:
        return "", _GALAT_ISIAN
    aktif = _NILAI_AKTIF[data["aktif"]]
    lama = AS.ambil(kon, siswa_id)
    AS.atur(kon, siswa_id, aktif=aktif,
            target_harian=lama.target_harian if lama else None,
            tampil_hitung_mundur=lama.tampil_hitung_mundur if lama else None,
            sekarang=int(time.time()), oleh=pengguna[:AS.MAKS_PANJANG_OLEH])
    nama = baris["nama"]
    return (f"Mode Lomba untuk {nama} diaktifkan." if aktif else f"Mode Lomba untuk {nama} dimatikan."), ""
