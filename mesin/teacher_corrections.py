"""Adaptasi formulir guru tanpa mengubah arti catatan dan diagnosis tersimpan."""


def pilihan_tersimpan(butir):
    """Otomatis bukan override; pertahankan keputusan manual yang sudah ada."""
    if not butir["manual"]:
        return ""
    return "benar" if butir["benar"] else butir["kode_final"] or ""


def cara_untuk_form(cara):
    """Baca pilihan cepat sebagai kalimat, tanpa membuat bukti cara baru."""
    from students import AWALAN_PILIHAN, PILIHAN_CARA

    if cara.startswith(AWALAN_PILIHAN):
        kode, pemisah, catatan = cara[len(AWALAN_PILIHAN):].partition(" — ")
        label = dict(PILIHAN_CARA).get(kode)
        if label:
            return "Pilihan anak: " + label + (pemisah + catatan if pemisah else "")
    return cara


def cara_dari_form(teks, lama):
    """Pertahankan pilihan cepat, termasuk ketika guru menambah penjelasan."""
    from students import AWALAN_PILIHAN, PILIHAN_CARA

    if teks == cara_untuk_form(lama):
        return lama
    for kode, label in PILIHAN_CARA:
        awalan = "Pilihan anak: " + label
        if teks == awalan or teks.startswith(awalan + " — "):
            return AWALAN_PILIHAN + kode + teks[len(awalan):]
    return teks


def label_penilaian(kode):
    """Label manusia untuk kategori diagnosis yang sudah ada."""
    return {
        "benar": "Jawaban benar",
        "K": "Perlu memahami konsep",
        "B": "Perlu membaca soal lebih teliti",
        "H": "Perlu memeriksa hitungan",
        "E": "Perlu memeriksa penulisan jawaban akhir",
        "N": "Menebak atau belum menunjukkan cara",
        "T": "Perlu pengenalan tipe soal",
        "": "Perlu penilaian orang tua/guru",
    }[kode or ""]
