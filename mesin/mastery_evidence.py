"""Adapter baca peta penguasaan; tidak mengubah penyimpanan atau bukti asli."""
from collections import defaultdict
from dataclasses import replace


def lengkapi_bukti_materi(kon, bukti):
    """Perkaya snapshot aktif dengan mode/pola/sidik matematika immutable.

    Adapter database umum tetap mengeluarkan kontrak lama. Metadata ini hanya
    diperlukan laporan; tidak menulis dan tidak memakai diagnosis mutable.
    """
    metadata = {b["id"]: b["mode"] for b in kon.execute(
        "SELECT id, mode FROM sesi WHERE siswa_id = ?", (bukti.siswa_id,),
    )}
    pola = defaultdict(list)
    sidik = {}
    for b in kon.execute(
        """SELECT ss.id, ss.sesi_id, so.template_id, ss.fingerprint_matematis
           FROM sesi_soal ss JOIN sesi se ON se.id = ss.sesi_id
           JOIN soal so ON so.id = ss.soal_id
           WHERE se.siswa_id = ? ORDER BY ss.sesi_id, ss.nomor""", (bukti.siswa_id,),
    ):
        pola[b["sesi_id"]].append(b["template_id"])
        sidik[(b["sesi_id"], b["id"])] = b["fingerprint_matematis"]
    outcomes = defaultdict(list)
    for b in kon.execute(
        """SELECT kh.sesi_id, o.konfirmasi_id, o.sesi_soal_id, o.template_id
           FROM snapshot_outcome o JOIN konfirmasi_hasil kh ON kh.id = o.konfirmasi_id
           JOIN sesi se ON se.id = kh.sesi_id
           WHERE se.siswa_id = ? AND se.dikonfirmasi_guru IS NOT NULL
             AND kh.id = (SELECT aktif.id FROM konfirmasi_hasil aktif
                          WHERE aktif.sesi_id = se.id AND aktif.fingerprint = se.fingerprint_konfirmasi
                          ORDER BY aktif.nomor_urut DESC, aktif.id DESC LIMIT 1)
           ORDER BY kh.sesi_id, o.nomor""", (bukti.siswa_id,),
    ):
        outcomes[(b["sesi_id"], b["konfirmasi_id"])].append(b)
    sesi = []
    for s in bukti.sesi:
        if s.siswa_id != bukti.siswa_id or s.id not in metadata:
            raise ValueError("metadata sesi bukan milik siswa")
        baris = outcomes[(s.id, s.konfirmasi_id)]
        if len(baris) != len(s.outcomes):
            raise ValueError("versi bukti peta berubah; muat ulang laporan")
        hasil = []
        for o, b in zip(s.outcomes, baris):
            if o.template_id != b["template_id"]:
                raise ValueError("pola snapshot tidak cocok")
            hasil.append(replace(o, fingerprint_matematis=sidik.get((s.id, b["sesi_soal_id"]))))
        sesi.append(replace(s, mode=metadata[s.id],
                            pola_tersedia=tuple(dict.fromkeys(pola[s.id])), outcomes=tuple(hasil)))
    return replace(bukti, sesi=tuple(sesi))
