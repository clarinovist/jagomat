"""Kecocokan PG di permukaan guru; pilihan tidak menentukan diagnosis anak."""
from diagnosis import Usulan


def nilai_pilihan(kunci, jawaban):
    """Nilai kanonis berasal dari snapshot, tanpa inferensi kode dari pengecoh."""
    benar = bool(jawaban) and jawaban == kunci
    alasan = ('Pilihan cocok dengan kunci; pemahaman tetap perlu ditinjau.' if benar else
              'Pilihan belum tepat; tanyakan cara anak sebelum menentukan penyebab.' if jawaban else
              'Belum memilih jawaban; tinjau pekerjaan anak.')
    return Usulan(benar, None, None, alasan, False)
