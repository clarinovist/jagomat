"""Mesin diagnosis — dari jawaban anak ke kode B/K/H/E/T/N.

Menerjemahkan "alur baca 5 langkah" di lembar penilaian menjadi kode.
Urutannya tidak boleh diubah: tiap langkah mengesampingkan yang di bawahnya,
dan urutan itulah yang memisahkan kode-kode yang mudah tertukar.

Yang dihasilkan adalah **usulan**, bukan vonis. Guru selalu bisa menimpa.
Kolom kode_usulan dan kode_final disimpan terpisah supaya nanti bisa diukur
seberapa sering mesin meleset — kalau sering, malrule-nya yang diperbaiki.

Batas yang disadari: mesin membaca teks, bukan maksud. Kotak "Caraku" hanya
diperiksa terisi atau tidak, tidak dinilai benar-salahnya. Karena itu
pemisahan K dari H bersandar pada tabel malrule; kalau jawaban salah anak
tidak ada di tabel, mesin mengembalikan None dan menyerahkannya ke guru.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from templates import Soal


# Hanya varian konversi yang kontraknya sudah diketahui. Bukan penghapus
# satuan umum: satuan tujuan berasal dari parameter soal, bukan isian anak.
_SATUAN_TUJUAN = {
    "km_ke_m": "m", "m_ke_km": "km",
    "jam_ke_menit": "menit", "menit_ke_jam": "jam",
    "kg_ke_g": "g", "g_ke_kg": "kg",
    "liter_ke_ml": "ml", "ml_ke_liter": "liter",
}


@dataclass(frozen=True)
class Usulan:
    benar: bool
    kode: str | None
    malrule_id: str | None
    alasan: str
    yakin: bool  # False -> guru perlu memutuskan sendiri


def _rapikan_teks(teks: str) -> str:
    """Samakan Unicode dan tanda minus tanpa menafsirkan tanda koma."""
    t = unicodedata.normalize("NFKC", teks).strip().lower()
    return t.replace("−", "-").replace("–", "-")


def normalisasi(teks: str) -> str:
    """Samakan bentuk penulisan sebelum dibandingkan.

    Utang yang dicatat di arsip lokal ~/Documents/osn-resources/referensi/spike/LANJUTAN.md: anak menulis "6 jam 25menit",
    kunci "6 jam 25 menit" — benar tapi terhitung salah karena spasi. Kalau
    dibiarkan, angka kecocokan tercemar oleh kesalahan yang bukan kesalahan.

    Yang disamakan: huruf besar-kecil, spasi berlebih, koma/titik desimal,
    spasi antara angka dan huruf, serta tanda baca di ujung.
    """
    t = _rapikan_teks(teks)
    # Konteks skalar: koma rapat dibaca sebagai desimal. Daftar bilangan
    # ditangani setara() SEBELUM normalisasi ini, dengan metadata soal.
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    # sisipkan spasi di batas angka<->huruf: "25menit" -> "25 menit"
    t = re.sub(r"(?<=\d)(?=[a-z])", " ", t)
    t = re.sub(r"(?<=[a-z])(?=\d)", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .;:")


def _daftar_bulat(teks: str) -> list[str] | None:
    """Baca seluruh daftar, tanpa mengabaikan isian kosong atau angka desimal."""
    t = _rapikan_teks(teks).rstrip(" .;:")
    angka = r"[+-]?[0-9]+"
    pemisah = r"(?:\s*,\s*|\s+dan\s+|\s+)"
    if not re.fullmatch(angka + "(?:" + pemisah + angka + ")*", t):
        return None
    return re.split(pemisah, t)


def _angka_bersatuan(teks: str, satuan: str) -> str | None:
    """Terima angka saja atau angka dengan tepat satu satuan tujuan."""
    cocok = re.fullmatch(
        r"([+-]?[0-9]+(?:[.,][0-9]+)?)(?:\s*" + re.escape(satuan) + r")?",
        _rapikan_teks(teks).rstrip(" .;:"),
    )
    return cocok.group(1).replace(",", ".") if cocok else None


def setara(a: str, b: str, *, soal: Soal | None = None) -> bool:
    """Bandingkan dua jawaban dengan toleransi penulisan.

    Untuk jawaban berisi beberapa bagian ("27, 31"), urutan tetap penting —
    "31, 27" bukan jawaban yang sama, karena yang diminta suku berikutnya
    secara berurutan. Metadata soal dari server memberi konteks daftar
    bilangan atau satuan; tanpa konteks, pertahankan pencocokan lama.
    Kunci pembanding tetap argumen b (termasuk kunci tersimpan/warisan),
    bukan kunci yang dihitung ulang pada objek soal.
    """
    if soal is not None:
        if (soal.template_id == "deret_aritmetika"
                and isinstance(soal.parameter.get("n_minta"), int)
                and soal.parameter["n_minta"] > 1):
            # Malrule hanya-satu-isian juga berupa daftar panjang satu.
            pa, pb = _daftar_bulat(a), _daftar_bulat(b)
            return pa is not None and pb is not None and pa == pb
        if soal.template_id == "satuan_konversi":
            satuan = _SATUAN_TUJUAN.get(soal.parameter.get("varian"))
            if satuan:
                angka_a = _angka_bersatuan(a, satuan)
                angka_b = _angka_bersatuan(b, satuan)
                return angka_a is not None and angka_b is not None and angka_a == angka_b

    na, nb = normalisasi(a), normalisasi(b)
    if na == nb:
        return True
    # samakan pemisah daftar: "27,31" / "27 dan 31" / "27 31"
    def bagian(s: str) -> list[str]:
        s = s.replace(" dan ", " ").replace(",", " ")
        return [x for x in s.split() if x]

    pa, pb = bagian(na), bagian(nb)
    return len(pa) > 1 and pa == pb


def diagnosa(
    kunci: str,
    jawaban: str,
    cara: str,
    restatement: str,
    belum_pernah: bool,
    malrule: list[sqlite3.Row] | list[dict],
    minta_restatement: bool = False,
    *,
    soal: Soal | None = None,
) -> Usulan:
    """Alur baca 5 langkah. Berhenti di kecocokan pertama.

    1. pengalaman belum pernah / bingung -> perlu tinjauan guru, tanpa kode
    2. ada jawaban tanpa "Caraku"        -> N  (jangan dinilai, tanya lisan)
    3. restatement salah menyebut        -> B  (walaupun caranya benar)
    4. jawaban cocok malrule             -> kode malrule itu
    5. jawaban == kunci                  -> benar
       selain itu                        -> tidak yakin, serahkan ke guru
    """
    jwb = jawaban.strip()
    crk = cara.strip()

    # Pengalaman/bingung adalah ucapan anak, bukan keputusan pengenalan.
    # T baru ditentukan guru setelah percakapan, bukan dari checkbox semata.
    if belum_pernah:
        return Usulan(False, None, None, "anak mencatat belum pernah melihat tipe soal ini — perlu ditinjau guru", False)
    if crk.startswith("[pilihan] bingung"):
        return Usulan(False, None, None, "anak menandai bingung — tanyakan bagian yang membingungkan", False)

    # Jawaban kosong tidak cukup untuk menebak penyebab, termasuk bila
    # ada coretan atau pengakuan menebak tanpa hasil akhir.
    if not jwb:
        return Usulan(False, None, None, "jawaban akhir belum diisi — tinjau pekerjaan dan catatan anak", False)

    # 2 — jawaban muncul tanpa jejak cara: tebakan sampai terbukti sebaliknya.
    if jwb and not crk:
        return Usulan(
            False, "N", None,
            "ada jawaban tanpa kotak Caraku — tanya lisan dulu sebelum menilai",
            True,
        )

    # 2b — anak MENGAKU menebak lewat pilihan cepat di halaman murid.
    #
    # Pengakuan sendiri lebih kuat daripada tebakan mesin: kalau anak memilih
    # "aku tebak saja", itu N tanpa perlu ditanya lisan lagi. Nilainya sama
    # dengan N dari cara-kosong, tapi alasannya berbeda supaya guru tahu ini
    # datang dari anaknya sendiri, bukan dari ketiadaan bukti.
    #
    # Dicek SEBELUM kunci dibandingkan: anak yang menebak lalu kebetulan benar
    # tetap harus tercatat menebak. Jawaban benar hasil tebakan adalah tanda
    # bahaya yang paling mudah hilang dari data.
    if crk.startswith("[pilihan] tebak"):
        return Usulan(
            False, "N", None,
            "anak sendiri menandai menebak — tanya lisan sebelum dinilai",
            True,
        )

    benar = bool(jwb) and setara(jwb, kunci, soal=soal)

    if benar:
        return Usulan(True, None, None, "jawaban benar", True)

    # 3 — cocokkan dengan kesalahan yang sudah diprediksi.
    #
    # Dicek SEBELUM restatement, dan itu perbaikan atas kesalahan desain
    # sebelumnya. Mesin tidak bisa menilai isi kotak "mintanya apa" — itu
    # kalimat bebas. Versi pertama menandai B setiap kali kotak itu terisi
    # dan jawaban salah, sehingga jawaban yang jelas-jelas K (mis. "12" pada
    # soal terbalik: lupa +1) tertutup jadi B. Akibatnya miskonsepsi yang
    # perlu diajar ulang justru menghilang dari laporan.
    #
    # Malrule membawa kodenya sendiri — termasuk B untuk kesalahan baca yang
    # memang bisa diprediksi, seperti menjawab nilainya pada soal terbalik.
    for m in malrule:
        m_jwb = m["jawaban"] if isinstance(m, sqlite3.Row) else m.get("jawaban", "")
        if setara(jwb, m_jwb, soal=soal):
            kode = m["kode"] if isinstance(m, sqlite3.Row) else m["kode"]
            mid = m["malrule_id"] if isinstance(m, sqlite3.Row) else m["malrule_id"]
            alasan = m["alasan"] if isinstance(m, sqlite3.Row) else m["alasan"]
            return Usulan(False, kode, mid, alasan, True)

    # 4 — salah, di luar tabel, dan soal ini rawan salah baca: arahkan guru
    # ke kotak "mintanya apa". Tidak yakin, karena hanya guru yang bisa
    # menilai apakah kalimat anak menyebut hal yang benar.
    if minta_restatement and restatement.strip():
        return Usulan(
            False, "B", None,
            "salah di luar pola yang terdaftar — periksa kotak 'mintanya apa': "
            "kalau menyebut hal lain, ini salah baca (B), bukan salah konsep",
            False,
        )

    # 5 — salah dengan cara yang tidak terduga. Ini bukan kegagalan mesin;
    # justru kasus paling menarik: kesalahan di luar tabel sering berarti
    # ada jalan pikir yang belum pernah terpetakan.
    return Usulan(
        False, None, None,
        "salah, tapi tidak cocok pola mana pun — baca kotak Caraku, "
        "mungkin miskonsepsi baru yang belum terdaftar",
        False,
    )
