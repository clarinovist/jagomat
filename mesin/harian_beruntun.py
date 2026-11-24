"""Hitung jawaban beruntun Latihan Harian untuk pose maskot (tampilan saja).

Berkas ini sengaja bukan `*store*`: nama berkas berstem store/schema/database ikut sidik kontrak rilis,
dan pose maskot tidak boleh menggeser kontrak. Hanya dipanggil setelah soal terjawab (umpan balik ada),
membaca hasil benar/salah jawaban anak itu sendiri dalam sesi yang sudah lolos pemeriksaan kepemilikan.
"""


def hitung(kon, sesi_id: int, nomor: int, benar: bool) -> int:
    """Berapa jawaban terakhir (sampai soal `nomor`, dalam sesi ini) yang hasilnya sama dengan `benar`."""
    baris = kon.execute("SELECT benar FROM harian_jawaban WHERE sesi_id = ? AND nomor <= ? ORDER BY nomor DESC",
                        (sesi_id, nomor)).fetchall()
    jumlah = 0
    for b in baris:
        if bool(b["benar"]) != benar:
            break
        jumlah += 1
    return jumlah
