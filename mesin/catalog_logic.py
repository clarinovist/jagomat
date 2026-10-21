"""Koreksi konten logika tanpa mengubah rekonstruksi soal historis."""
from dataclasses import replace
from templates import Malrule, Soal, saring_malrule


def soal_umur(a, b, k, n, tanya, konteks_umur="ayah_anak_v1"):
    """Jawab besaran yang diminta; konteks eksplisit tidak mengubah histori."""
    if konteks_umur not in ("ayah_anak_v1", "dua_orang_v1"):
        raise ValueError("konteks umur tidak didukung")
    if any(type(v) is not int or v <= 0 for v in (a, b, k, n)) or k <= 1:
        raise ValueError("parameter umur wajib bulat positif dan rasio lebih dari satu")
    if a + n != k * (b + n):
        raise ValueError("fakta umur dan rasio tidak konsisten")
    if tanya == "n_tahun":
        kunci = (a - k * b) // (k - 1)
        teks = (f"Umur ayah sekarang {a} tahun, umur anak {b} tahun. Dalam "
                f"berapa tahun lagi umur ayah menjadi {k} kali umur anak?")
        kandidat = (
            ("umur.lupa_penyebut_n_tahun", a - k * b,
             "mengurangi umur ayah dengan k kali umur anak, tetapi lupa membagi dengan k−1"),
            ("umur.selisih_umur_n_tahun", a - b,
             "menjawab selisih umur, bukan waktu hingga perbandingan terpenuhi"),
        )
        pembahasan = (
            f"Setiap tahun kedua umur bertambah satu. Setelah {kunci} tahun, "
            f"umur ayah {a + kunci} dan anak {b + kunci} tahun; "
            f"{a + kunci} = {k} × {b + kunci}. "
            f"Waktu = ({a} − {k} × {b}) : ({k} − 1) = {kunci} tahun."
        )
    elif tanya == "kali_umur":
        kunci = (a + n) // (b + n)
        teks = (f"Umur ayah sekarang {a} tahun, umur anak {b} tahun. Dalam "
                f"{n} tahun, umur ayah menjadi berapa kali umur anak?")
        kandidat = (
            ("umur.umur_anak_kali_umur", b + n,
             "menjawab umur anak pada waktu yang diminta, bukan rasio umur"),
            ("umur.umur_ayah_kali_umur", a + n,
             "menjawab umur ayah pada waktu yang diminta, bukan rasio umur"),
        )
        pembahasan = (
            f"Dalam {n} tahun, umur ayah {a} + {n} = {a + n} tahun "
            f"dan umur anak {b} + {n} = {b + n} tahun. "
            f"Perbandingan umur saat itu = {a + n} : {b + n} = {kunci} kali."
        )
    else:
        raise ValueError("pertanyaan umur tidak didukung")
    # Kandidat yang kebetulan benar tidak membuktikan kesalahan konsep.
    # Tidak digeser menjadi angka lain demi jumlah opsi atau quota kode.
    mal = [Malrule("umur.kurang_satu", str(kunci - 1), "H",
                   "perhitungan benar, hasilnya meleset satu")]
    mal.extend(Malrule(ident, str(nilai), "K", alasan) for ident, nilai, alasan in kandidat)
    parameter = {"a": a, "b": b, "k": k, "n": n, "tanya": tanya}
    if konteks_umur == "dua_orang_v1":
        # Nama tanpa hubungan keluarga sah untuk seluruh domain umur existing.
        # Marker masuk identitas; parameter katalog2 tanpa marker tetap persis.
        parameter["konteks_umur"] = konteks_umur
        teks = teks.replace("ayah", "Ari").replace("anak", "Bima")
        pembahasan = pembahasan.replace("ayah", "Ari").replace("anak", "Bima")
        mal = [replace(m, alasan=m.alasan.replace("ayah", "Ari").replace("anak", "Bima")) for m in mal]
    return Soal("soal_umur", parameter,
                teks, str(kunci), saring_malrule(str(kunci), mal),
                minta_restatement=True, bagian="B", pembahasan=pembahasan)
