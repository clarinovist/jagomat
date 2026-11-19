"""Integrasi ujung ke ujung: orang tua mulai "Di HP ini" -> anak mengerjakan -> orang tua masuk lagi -> hasil.

Menyambungkan sisi orang tua (cek_http) dengan permukaan anak (cek_anak_http) lewat server nyata,
sesi login (cookie) nyata, dan data sintetis di tmp_path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cek_http_kit import (  # noqa: E402
    AKUN_A, HASIL, MULAI, POLA_TOKEN, keluarga, minta_mentah, server, teks_tampak,  # noqa: F401
)

JUMLAH = 15
LANJUT_HASIL = "/cek-kemampuan/hasil"
POLA_ANAK = re.compile(r"^/mulai/([A-Za-z0-9_-]{43})\?di=hp-ini$")
POLA_OPSI = re.compile(r'name="opsi_(\d+)" value="opsi_1"')
POLA_REVISI = re.compile(r'name="revisi_pekerjaan" value="([0-9]+)"')


def _cookie(server, lanjut=None):
    data = {"nama": AKUN_A[0], "sandi": AKUN_A[1]}
    if lanjut is not None:
        data["lanjut"] = lanjut
    kode, _i, tajuk = minta_mentah(server, "/masuk", data=data)
    assert kode == 303
    return tajuk["Set-Cookie"].split(";")[0], tajuk["Location"]


def _anak(server, jalur, data=None):
    return minta_mentah(server, jalur, data=data)


def test_hp_ini_sampai_hasil_dengan_skor_setelah_login_ulang(keluarga):
    cookie, _ = _cookie(keluarga)
    _k, halaman, _t = minta_mentah(keluarga, MULAI, headers={"Cookie": cookie})
    token_form = POLA_TOKEN.search(halaman).group(1)
    kode, isi, tajuk = minta_mentah(
        keluarga, MULAI, headers={"Cookie": cookie},
        data={"token": token_form, "setuju": "1", "cara": "hp_ini"},
    )
    assert (kode, isi) == (303, "")
    cocok = POLA_ANAK.fullmatch(tajuk["Location"])
    assert cocok, tajuk["Location"]
    dasar = f"/mulai/{cocok.group(1)}"
    # Sesi login orang tua sudah dihapus: cookie lama tidak lagi membuka area guru.
    assert minta_mentah(keluarga, "/guru", headers={"Cookie": cookie})[0] != 200

    kode, sapaan, _t = _anak(keluarga, tajuk["Location"])
    assert kode == 200 and "Ayo mulai!" in sapaan
    assert 'action="' + dasar + '?di=hp-ini"' in sapaan
    kode, _i, tajuk = _anak(keluarga, dasar + "?di=hp-ini", {"aksi": "mulai"})
    assert kode == 303 and tajuk["Location"] == dasar + "?soal=1&di=hp-ini"

    for nomor in range(1, JUMLAH + 1):
        _k, soal, _t = _anak(keluarga, f"{dasar}?soal={nomor}&di=hp-ini")
        ssid = POLA_OPSI.search(soal).group(1)
        revisi = POLA_REVISI.search(soal).group(1)
        kode, _i, tajuk = _anak(keluarga, dasar + "?di=hp-ini", {
            "aksi": "simpan", "soal": str(nomor), "revisi_pekerjaan": revisi, f"opsi_{ssid}": "opsi_1",
        })
        assert kode == 303 and "di=hp-ini" in tajuk["Location"]

    _k, peta, _t = _anak(keluarga, dasar + "?peta=1&di=hp-ini")
    revisi = POLA_REVISI.search(peta).group(1)
    kode, hore, _t = _anak(keluarga, dasar + "?di=hp-ini", {"aksi": "kumpul", "revisi_pekerjaan": revisi})
    assert kode == 200 and "15 dari 15 soal dijawab" in hore
    assert f'href="/masuk?lanjut={LANJUT_HASIL}"' in hore
    assert not any(k in teks_tampak(hore) for k in ("Skor keseluruhan", "dari 100", "Kategori"))
    assert _anak(keluarga, dasar)[0] == 404  # token mati setelah dikumpulkan

    # Orang tua masuk lewat tombol di layar Hore (lanjut persis) dan melihat hasil dengan skor.
    cookie_baru, tujuan = _cookie(keluarga, LANJUT_HASIL)
    assert tujuan == LANJUT_HASIL
    kode, isi, _t = minta_mentah(keluarga, HASIL, headers={"Cookie": cookie_baru})
    assert kode == 200 and "Skor keseluruhan" in isi and "dari 100" in isi
