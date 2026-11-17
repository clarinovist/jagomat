"""Kontak WhatsApp pada pendaftaran jalur funnel (`/daftar?jalur=cek`).

Semua keputusan jalur ada di sini supaya `landing`, `registration_http`, dan
saga `admin_registration` tidak menyebar logika yang sama. Jalur biasa tidak
disentuh: tanpa `jalur=cek` dan sakelar hidup, tidak ada field baru, tidak ada
kontak, dan `sidik` operasi tetap sama byte-per-byte.

Nomor tidak pernah dimasukkan ke pesan galat, log, atau URL. Satu-satunya tempat
nomor boleh muncul kembali adalah atribut `value` input form (di-escape) saat
validasi gagal, supaya pengguna tidak mengetik ulang.
"""
from __future__ import annotations

import html
import urllib.parse
from datetime import datetime, timezone

import funnel_flag
import kontak_akun

JALUR_FUNNEL = "cek"
KUNCI_FORM = frozenset({"wa", "jalur"})
PESAN_FORM_TIDAK_SAH = "Isian pendaftaran tidak sah."
PESAN_WA_WAJIB = "Isi nomor WhatsApp Indonesia yang valid, ya."
PETUNJUK_NAMA_FUNNEL = (
    "Pilih nama pengguna tanpa spasi (3–40 karakter): huruf, angka, titik, "
    "garis bawah, atau tanda hubung."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_FUNNEL_WA = (
    "Nomor WhatsApp dipakai tim untuk mengirim hasil dan mengonfirmasi jadwal. "
    "Hanya tim yang melihatnya; tidak pernah ditampilkan ke anak."
)


def jalur_funnel_di_query(path: str) -> bool:
    """GET: True hanya bila `?jalur=cek` dan sakelar hidup; selain itu diabaikan."""
    if not funnel_flag.funnel_aktif():
        return False
    nilai = urllib.parse.parse_qs(urllib.parse.urlparse(path).query).get("jalur", [])
    return nilai == [JALUR_FUNNEL]


def baca_mode_form(data) -> bool:
    """POST: True bila `jalur=cek` sah. Field `wa`/`jalur` di luar jalur sah ditolak.

    Dipanggil setelah whitelist umum; `wa` atau `jalur` tanpa (`jalur=cek` dan
    sakelar hidup) diperlakukan seperti field tak dikenal, tanpa menyimpan apa pun.
    """
    if not (KUNCI_FORM & set(data)):
        return False
    if data.get("jalur") != JALUR_FUNNEL or not funnel_flag.funnel_aktif():
        raise ValueError(PESAN_FORM_TIDAK_SAH)
    return True


def normalisasi_dari_form(data) -> str | None:
    """Nomor ternormalisasi dari field form `wa`, atau None bila tidak sah."""
    return kontak_akun.normalisasi_wa(data.get("wa"))


def echo_wa(data) -> str:
    """Nilai mentah untuk diisi kembali ke input (dipotong; di-escape saat render)."""
    mentah = data.get("wa", "")
    return mentah[: kontak_akun.PANJANG_MASUKAN_MAKS] if type(mentah) is str else ""


def field_form(wa: str = "") -> str:
    """Field WhatsApp wajib + penanda jalur tersembunyi untuk form funnel."""
    nilai = html.escape(wa, quote=True)
    return (
        '<input type="hidden" name="jalur" value="cek">\n'
        '  <div class="masuk-field-st">\n'
        '    <label for="wa-daftar">Nomor WhatsApp</label>\n'
        '    <input type="tel" id="wa-daftar" name="wa" autocomplete="tel" required '
        f'inputmode="tel" maxlength="{kontak_akun.PANJANG_MASUKAN_MAKS}" '
        f'aria-describedby="petunjuk-wa-daftar" value="{nilai}">\n'
        f'    <p class="daftar-petunjuk-st" id="petunjuk-wa-daftar">{html.escape(COPY_FUNNEL_WA)}</p>\n'
        '  </div>\n  '
    )


def periksa(wa) -> None:
    """Saga: `wa` None (jalur biasa) atau string yang sudah ternormalisasi."""
    if wa is None:
        return
    if type(wa) is not str or kontak_akun.normalisasi_wa(wa) != wa:
        raise ValueError("nomor WhatsApp tidak sah")


def simpan_di_transaksi(kon, id_akun: str, wa, kini: int) -> None:
    """Tulis kontak di transaksi pemanggil (tanpa commit); no-op pada jalur biasa."""
    if wa is None:
        return
    waktu = datetime.fromtimestamp(kini, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    kontak_akun.simpan(kon, id_akun, wa, waktu)
