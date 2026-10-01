"""Layanan penyimpanan koreksi dan diagnosis guru."""
from __future__ import annotations

import database
import question_views
from diagnosis import diagnosa
from teacher_corrections import KODE_PILIHAN, cara_dari_form, pilihan_tersimpan


def simpan_sesi(
    kon, sesi_id: int, data: dict, *, tinjauan_disimpan: bool = False,
    guru: str = 'guru', soal_dari_baris=None,
) -> str:
    """Simpan koreksi guru tanpa menimpa arsip dan provenance pekerjaan asli."""
    soal_dari_baris = soal_dari_baris or question_views.soal_dari_baris
    if not tinjauan_disimpan:
        import review_store
        kon.execute('SAVEPOINT koreksi_lokal')
        try:
            review_store.simpan(kon, sesi_id, data, guru)
            hasil = simpan_sesi(
                kon, sesi_id, data, tinjauan_disimpan=True, guru=guru,
                soal_dari_baris=soal_dari_baris,
            )
            kon.execute('RELEASE SAVEPOINT koreksi_lokal')
            return hasil
        except Exception:
            kon.execute('ROLLBACK TO SAVEPOINT koreksi_lokal')
            kon.execute('RELEASE SAVEPOINT koreksi_lokal')
            raise
    mode_baris = kon.execute(
        "SELECT mode FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    drill = bool(mode_baris and mode_baris["mode"] == "drill")
    awalan_drill = ""
    if drill:
        from students import AWALAN_DRILL
        awalan_drill = AWALAN_DRILL

    diubah = 0
    for b in database.isi_sesi(kon, sesi_id):
        sid = b["sesi_soal_id"]
        if not any(nama in data for nama in (f'jwb_{sid}', f'cara_{sid}', f'kode_{sid}', f'belum_{sid}')):
            continue
        jwb = data.get(f"jwb_{sid}", b['jawaban'] or "").strip()
        cara = cara_dari_form(data.get(f"cara_{sid}", b['cara'] or "").strip(), b["cara"] or "")
        restate = b["restatement"] or ""
        belum = f"belum_{sid}" in data if f'jwb_{sid}' in data else bool(b['belum_pernah']) or f'belum_{sid}' in data
        pilihan = data.get(f"kode_{sid}", pilihan_tersimpan(b)).strip()
        kode_diizinkan = {nilai for nilai, _label in KODE_PILIHAN if nilai}
        kode_diizinkan.add("T")  # Keputusan pengenalan eksplisit oleh guru.
        if drill:
            kode_diizinkan.discard("N")
        if pilihan not in kode_diizinkan:
            pilihan = ""

        if not (jwb or cara or restate or belum or pilihan):
            if b["jawaban_id"] is None or f"jwb_{sid}" not in data:
                continue
        kode_lama = pilihan_tersimpan(b)
        if (b["jawaban_id"] is not None and b["benar"] is not None
                and jwb == (b["jawaban"] or "")
                and cara == (b["cara"] or "")
                and belum == bool(b["belum_pernah"]) and pilihan == kode_lama):
            continue

        jid = database.simpan_jawaban(kon, sid, jwb, cara, restate, belum)

        cara_diagnosis = awalan_drill + cara if drill else cara
        soal = soal_dari_baris(b)
        from choice_store import format_sesi
        if format_sesi(kon, sesi_id) == 'pilihan_ganda':
            from choice_assessment import nilai_pilihan
            u = nilai_pilihan(b['kunci'], jwb)
        else:
            u = diagnosa(
                b["kunci"], jwb, cara_diagnosis, restate, belum,
                database.malrule_soal(kon, b["soal_id"]),
                soal.minta_restatement, soal=soal,
            )

        if pilihan == "benar":
            benar, final, manual = True, None, True
        elif pilihan:
            benar, final, manual = False, pilihan, True
        else:
            benar, final, manual = u.benar, u.kode, False

        database.simpan_diagnosis(
            kon, jid, benar, u.kode, final,
            None if benar else u.malrule_id, u.alasan, manual
        )
        diubah += 1

    return f"{diubah} koreksi tersimpan."
