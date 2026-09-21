"""Materi pilot pra-tulis untuk orang tua mendampingi; bukan soal probe."""
from interventions import MateriIntervensi
from skill_pilot import LANGSUNG, BALIK, PRASYARAT, validasi_fokus

CONTOH = {
    LANGSUNG: "Persegi panjang mempunyai dua sisi 8 cm dan dua sisi 3 cm. "
              "Telusuri batasnya: 8 + 3 + 8 + 3 = 22 cm. "
              "Dua pasangan sisi membuat (8 + 3) × 2 sama dengan jumlah empat sisi.",
    BALIK: "Keliling persegi panjang 22 cm, panjangnya 8 cm. "
           "Separuh keliling memuat satu panjang dan satu lebar: 22 ÷ 2 = 11 cm. "
           "Lebarnya 11 − 8 = 3 cm. Luasnya 8 × 3 = 24 cm². "
           "Bayangkan tiga baris, masing-masing delapan petak 1 cm².",
    PRASYARAT: "Susun tiga baris petak, masing-masing delapan petak 1 cm². "
               "Seluruhnya 8 + 8 + 8 = 8 × 3 = 24 petak. Luasnya 24 cm², "
               "bukan panjang batas luarnya.",
}
ALTERNATIF = {
    LANGSUNG: "Gambar persegi panjang bersisi 8 cm dan 3 cm. Pasangkan satu sisi "
              "panjang dengan satu sisi pendek: 8 + 3 = 11 cm. Ada dua pasangan "
              "seperti itu, sehingga kelilingnya 11 + 11 = 22 cm.",
    BALIK: "Gambar empat sisi. Dari keliling 22 cm, kurangi kedua panjang: "
           "22 − 8 − 8 = 6 cm. Itu jumlah dua lebar yang sama, jadi satu lebar "
           "6 ÷ 2 = 3 cm. Luasnya 8 × 3 = 24 cm². Periksa batasnya: "
           "8 + 3 + 8 + 3 = 22 cm.",
    PRASYARAT: "Gambar delapan kolom yang masing-masing berisi tiga petak 1 cm². "
               "Hitung seluruh petak dengan 8 × 3 = 24. Putar gambar: jumlah "
               "petaknya tetap 24, walaupun baris dan kolom bertukar.",
}


def pilihan_materi(konteks, fokus):
    """Konteks dan diagnosis harus cocok; tidak memakai kartu generik sebagai fallback."""
    validasi_fokus(konteks, fokus)
    identitas = konteks.tuntutan_id
    kode = fokus[1]
    if kode in ("K", "T"):
        utama = MateriIntervensi(
            "pilot-v1:pasangan:" + identitas,
            "Pelajari contoh bersama. Minta anak menunjuk arti setiap langkah. "
            "Catat bantuan; contoh ini bukan bukti mandiri.",
            CONTOH[identitas],
            "Tunjukkan arti setiap langkah dengan gambar atau petak.",
        )
        if kode == "T":
            return (utama,)
        return (utama, MateriIntervensi(
            "pilot-v1:empat-sisi:" + identitas,
            "Gunakan cara berbeda ini, bukan mengulang cara pertama. "
            "Dengarkan penjelasan anak sebelum memberi probe baru.",
            ALTERNATIF[identitas],
            "Gambar bagian-bagiannya, lalu periksa kembali hubungan panjang dan luas.",
        ))
    instruksi = {
        "B": "Tandai informasi dan ucapkan ulang apa yang ditanya. "
             "Menemukan sisi saja belum menjawab pertanyaan luas.",
        "H": "Tulis satu operasi tiap langkah dan periksa kembali hitungannya.",
        "E": "Cocokkan hasil terakhir beserta satuannya dengan kotak jawaban.",
        "N": "Tanyakan dari mana setiap angka diperoleh. Jawaban benar tanpa "
             "penjelasan belum menunjukkan pemahaman.",
    }[kode]
    return (MateriIntervensi("pilot-v1:" + kode + ":" + identitas,
                            instruksi, CONTOH[identitas], instruksi),)
