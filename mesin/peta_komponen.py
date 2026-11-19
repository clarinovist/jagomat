"""Komponen markup kecil yang dipakai berulang di panel laporan Peta Kemampuan."""
from __future__ import annotations

from cek_gratis_skor import LABEL_BELUM_CUKUP, LABEL_KUAT, hitung_skor, label_materi
from peta_ikon import ikon, ubin
from peta_teks import e

_KELAS_STATUS = {LABEL_KUAT: "kuat", LABEL_BELUM_CUKUP: "belum"}
JALUR_LEMBAR_CONTOH = "/contoh-peta-kemampuan/lembar"
JALUR_LAPORAN_CONTOH = "/contoh-peta-kemampuan"


def gabung_nama(nama: list) -> str:
    """`a`, `a serta b`, `a, b, serta c` (nama materi sendiri memuat kata "dan")."""
    if len(nama) <= 1:
        return "".join(nama)
    if len(nama) == 2:
        return "%s serta %s" % tuple(nama)
    return "%s, serta %s" % (", ".join(nama[:-1]), nama[-1])


def kepala_panel(nama_ikon: str, warna: str, id_judul: str, judul: str, bantuan: str) -> str:
    """Kepala panel: ubin ikon, judul h2, dan satu kalimat bantuan."""
    return (
        '<div class="peta-kepala-panel-st">%s<div><h2 id="%s">%s</h2><p class="peta-bantuan-st">%s</p></div></div>'
        % (ubin(nama_ikon, warna, "m"), e(id_judul), e(judul), e(bantuan))
    )


def status_chip(label: str) -> str:
    """Chip status berteks; warna hanya pendukung."""
    kelas = _KELAS_STATUS.get(label, "perkuat")
    pendukung = ikon("cek", 14, "2.8") if label == LABEL_KUAT else ""
    return '<span class="peta-status-st peta-status-%s-st">%s%s</span>' % (kelas, pendukung, e(label))


def persen_materi(materi) -> int:
    return hitung_skor(materi.benar, materi.soal)


def label_dari_materi(materi) -> str:
    return label_materi(materi.benar, materi.soal)


def bar_penguasaan(materi) -> str:
    """Bar lebar persen (atribut gaya, bukan skrip); kelas warna mengikuti label."""
    kelas = "kuat" if label_dari_materi(materi) == LABEL_KUAT else "perkuat"
    return '<span class="peta-bar-st"><i class="peta-bar-%s-st" style="width:%d%%"></i></span>' % (kelas, persen_materi(materi))


def pola_per_materi(data, kunci_materi: str) -> tuple:
    """Pola yang menyumbang jawaban salah di materi tersebut, urut jumlah terbanyak."""
    terkait = [p for p in data.pola if any(k == kunci_materi for k, _j in p.sebaran)]
    return tuple(sorted(terkait, key=lambda p: -dict(p.sebaran)[kunci_materi]))


def pola_teratas(data):
    """Pola dengan jumlah salah terbanyak (urutan data bila seri); None bila tidak ada."""
    return max(data.pola, key=lambda p: p.jumlah) if data.pola else None

