"""Verifikasi mesin diagnosis — pemisahan kode yang mudah tertukar.

Yang diuji di sini bukan "apakah kodenya keluar", tapi apakah kode yang
keluar memisahkan hal-hal yang memang berbeda. Kesalahan diagnosis yang
paling merusak bukan kode yang kosong, melainkan kode yang salah tapi
terlihat meyakinkan — mis. B (salah baca) tercatat sebagai K (salah konsep),
lalu materi diajar ulang padahal yang perlu dilatih membaca soal.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnosis import diagnosa, normalisasi, setara  # noqa: E402

MAL_ARITMETIKA = [
    {"malrule_id": "aritmetika.beda_dikira_satu", "jawaban": "24, 25", "kode": "K",
     "alasan": "pola dikira +1"},
    {"malrule_id": "aritmetika.penjumlahan_meleset", "jawaban": "26, 30", "kode": "H",
     "alasan": "selisih benar, jumlah meleset"},
]


# ── Normalisasi: utang dalam arsip lokal osn-resources/referensi/spike/LANJUTAN.md ─────────────────


def test_spasi_antara_angka_dan_huruf_tidak_dianggap_salah():
    """Utang nyata dari sesi 19 Agustus.

    Anak menulis "6 jam 25menit", kunci "6 jam 25 menit" — jawabannya BENAR
    tapi terhitung salah karena satu spasi. Kalau tidak diperbaiki, angka
    kecocokan tercemar oleh kesalahan yang bukan kesalahan.
    """
    assert setara("6 jam 25menit", "6 jam 25 menit")
    assert setara("25menit", "25 menit")


def test_huruf_besar_kecil_dan_spasi_berlebih_diabaikan():
    assert setara("KAMIS", "Kamis")
    assert setara("  merah  ", "merah")
    assert setara("hijau ", "Hijau")


def test_koma_desimal_disamakan_dengan_titik():
    assert setara("0,85", "0.85")
    assert normalisasi("0,85") == normalisasi("0.85")


def test_pemisah_daftar_bebas_bentuk():
    """"27, 31" / "27 dan 31" / "27 31" — sama maksudnya."""
    assert setara("27 dan 31", "27, 31")
    assert setara("27 31", "27, 31")


def test_urutan_jawaban_majemuk_tetap_penting():
    """Yang diminta suku berikutnya BERURUTAN, jadi 31,27 bukan jawaban sama."""
    assert not setara("31, 27", "27, 31")


def test_jawaban_beda_tetap_beda():
    assert not setara("24", "27")
    assert not setara("Kamis", "Jumat")


# ── Alur baca 5 langkah: tiap langkah mengesampingkan yang di bawahnya ───


def test_pengalaman_anak_perlu_dipastikan_guru():
    """Catatan pengalaman tidak cukup untuk otomatis memberi T."""
    u = diagnosa("39", "36", "6x6=36", "", True, [], False)
    assert u.kode is None
    assert not u.yakin and not u.benar


def test_jawaban_tanpa_cara_adalah_menebak():
    """N harus menghentikan penilaian — kode lain tidak bisa dipercaya
    tanpa coretan yang bisa dibaca."""
    u = diagnosa("96", "96", "", "", False, [], False)
    assert u.kode == "N"
    assert not u.benar


def test_kosong_total_bukan_menebak_dan_bukan_tidak_tahu():
    """Tidak dikerjakan sama sekali ≠ menebak (N) ≠ mengakui belum tahu (T).

    Dibedakan karena tindak lanjutnya berbeda: yang ini perlu ditanya kenapa
    dilewati — kehabisan waktu, lelah menulis, atau memang tidak tahu.
    """
    u = diagnosa("96", "", "", "", False, [], False)
    assert u.kode is None
    assert not u.yakin


def test_jawaban_benar_dengan_cara_terisi():
    u = diagnosa("27, 31", "27, 31", "+4 tiap langkah", "", False, MAL_ARITMETIKA, False)
    assert u.benar
    assert u.kode is None


def test_jawaban_benar_dengan_penulisan_berbeda():
    u = diagnosa("27, 31", "27 dan 31", "tambah 4", "", False, MAL_ARITMETIKA, False)
    assert u.benar


# ── Pemisahan K dari H: inti seluruh sistem ─────────────────────────────


def test_malrule_konsep_terdeteksi_sebagai_k():
    u = diagnosa("27, 31", "24, 25", "24, 25", "", False, MAL_ARITMETIKA, False)
    assert u.kode == "K"
    assert u.malrule_id == "aritmetika.beda_dikira_satu"
    assert u.yakin


def test_malrule_hitung_terdeteksi_sebagai_h():
    """H dan K harus terpisah: H cuma perlu latihan, K perlu diajar ulang."""
    u = diagnosa("27, 31", "26, 30", "+4 tiap langkah", "", False, MAL_ARITMETIKA, False)
    assert u.kode == "H"
    assert u.malrule_id == "aritmetika.penjumlahan_meleset"


def test_salah_di_luar_tabel_tidak_dipaksa_diberi_kode():
    """Mesin harus mengaku tidak tahu, bukan menebak.

    Kesalahan di luar tabel sering berarti ada jalan pikir yang belum
    terpetakan — itu temuan, dan memaksakan kode akan menutupinya.
    """
    u = diagnosa("27, 31", "99, 100", "entah", "", False, MAL_ARITMETIKA, False)
    assert u.kode is None
    assert not u.yakin
    assert "belum terdaftar" in u.alasan


def test_soal_terbalik_jawab_nilainya_adalah_b_bukan_k():
    """Kesalahan yang paling sering salah didiagnosis.

    Anak menjawab 41 pada "41 ada di urutan ke berapa" — dia PAHAM polanya,
    dia tidak paham pertanyaannya. Obatnya latih baca soal, bukan ajar ulang
    pola. Kalau ini tercatat K, materi yang sudah dikuasai diajar ulang.
    """
    mal = [
        {"malrule_id": "terbalik.jawab_nilainya", "jawaban": "41", "kode": "B",
         "alasan": "yang diminta nomor urut, yang dijawab nilainya"},
        {"malrule_id": "terbalik.lupa_tambah_satu", "jawaban": "12", "kode": "K",
         "alasan": "lupa +1"},
    ]
    u = diagnosa("13", "41", "5,8,11,...,41", "cari 41 urutan berapa", False, mal, True)
    assert u.kode == "B"
    assert u.malrule_id == "terbalik.jawab_nilainya"


def test_lupa_tambah_satu_tetap_k():
    mal = [
        {"malrule_id": "terbalik.jawab_nilainya", "jawaban": "41", "kode": "B",
         "alasan": "dijawab nilainya"},
        {"malrule_id": "terbalik.lupa_tambah_satu", "jawaban": "12", "kode": "K",
         "alasan": "lupa +1 untuk suku pertama"},
    ]
    u = diagnosa("13", "12", "(41-5)/3 = 12", "cari urutan", False, mal, True)
    assert u.kode == "K"


def test_benar_tetap_benar_walau_restatement_diminta():
    """Soal yang minta restatement tidak boleh menandai jawaban benar sebagai B."""
    u = diagnosa("13", "13", "5,8,11 sampai 41", "cari 41 urutan ke berapa",
                 False, [], True)
    assert u.benar
    assert u.kode is None


def test_usulan_selalu_punya_alasan_terbaca():
    """Guru harus bisa menilai usulan mesin, bukan menerima kode telanjang."""
    kasus = [
        ("27, 31", "24, 25", "24 25", "", False, MAL_ARITMETIKA, False),
        ("96", "96", "", "", False, [], False),
        ("39", "36", "6x6", "", True, [], False),
        ("27, 31", "99", "?", "", False, MAL_ARITMETIKA, False),
    ]
    for k in kasus:
        assert diagnosa(*k).alasan.strip()
