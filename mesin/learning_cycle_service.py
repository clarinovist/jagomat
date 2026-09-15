"""Layanan transaksi untuk aksi HTTP siklus belajar terpandu."""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Mapping

import database
import interventions
import topics
from learning_cycle import rencana_berikutnya
from teacher_corrections import pilihan_tersimpan, cara_dari_form

_AWALAN_BUTIR = (
    "jwb_",
    "cara_",
    "kode_",
    "cek_pemahaman_",
    "belum_",
    "dilewati_",
    "catatan_tinjauan_", "provenance_", "jawaban_bantuan_", "versi_tinjauan_",
)
_KODE_SAH = {"", "benar", "B", "K", "H", "E", "N", "T"}
_PEMAHAMAN_SAH = {"", "bisa_menjelaskan", "ragu", "menghafal"}
_AKSI_SESI = {
    "pemetaan",
    "probe_diagnostik",
    "latihan_terbimbing",
    "penguatan",
    "evaluasi",
    "checkpoint",
    "pengenalan",
    "probe_setelah_pengenalan",
    "mixed_maintenance",
}
_EVENT_PUTARAN_TUTUP = {"putaran_ditutup", "diganti_level", "override_ditutup"}


def _id_butir_dari_field(nama: str) -> int | None:
    for awalan in _AWALAN_BUTIR:
        if nama.startswith(awalan):
            mentah = nama[len(awalan):]
            if not mentah.isdigit():
                raise ValueError("referensi butir tidak dikenal")
            return int(mentah)
    return None


def validasi_form_konfirmasi(
    kon: sqlite3.Connection, sesi_id: int, data: Mapping[str, str]
) -> None:
    """Validasi seluruh payload sebelum koreksi pertama ditulis."""
    butir_sah = {
        int(baris["sesi_soal_id"]): baris
        for baris in database.isi_sesi(kon, sesi_id)
    }
    id_sah = set(butir_sah)
    if not id_sah:
        raise ValueError("sesi tidak memiliki butir")
    for nama, nilai in data.items():
        if nama == "sertakan_pemetaan":
            if nilai not in {"", "1"}:
                raise ValueError("opsi pemetaan tidak dikenal")
            continue
        butir_id = _id_butir_dari_field(nama)
        if butir_id is None or butir_id not in id_sah:
            raise ValueError("referensi butir tidak dikenal")
        if nama.startswith("kode_") and nilai not in _KODE_SAH:
            raise ValueError("kode koreksi tidak dikenal")
        if nama.startswith("cek_pemahaman_") and nilai not in _PEMAHAMAN_SAH:
            raise ValueError("cek pemahaman tidak dikenal")
        if nama.startswith(("belum_", "dilewati_")) and nilai != "1":
            raise ValueError("penanda butir tidak dikenal")


def _koreksi_form(kon, sesi_id, data):
    """Lengkapi field parsial dan bedakan retry dari koreksi nyata."""
    pasangan = []
    berubah = False
    for butir in database.isi_sesi(kon, sesi_id):
        sid = butir["sesi_soal_id"]
        lama = {
            f"jwb_{sid}": butir["jawaban"] or "",
            f"cara_{sid}": butir["cara"] or "",
            f"kode_{sid}": pilihan_tersimpan(butir),
        }
        baru = {kunci: data.get(kunci, nilai).strip() for kunci, nilai in lama.items()}
        baru[f"cara_{sid}"] = cara_dari_form(baru[f"cara_{sid}"], lama[f"cara_{sid}"])
        penuh = f"jwb_{sid}" in data or f"hadir_belum_{sid}" in data
        belum = f"belum_{sid}" in data if penuh else bool(butir["belum_pernah"]) or f"belum_{sid}" in data
        berubah = berubah or baru != lama or belum != bool(butir["belum_pernah"])
        pasangan.extend(baru.items())
        if belum:
            pasangan.append((f"belum_{sid}", "1"))
    return dict(pasangan), berubah


def _cabut_opt_in_bila_diminta(kon, sesi_id, data):
    """Pencabutan opt-in mengakhiri versi lama, bukan menghapus event."""
    if data.get("sertakan_pemetaan") == "1":
        return
    aktif = kon.execute(
        """SELECT s.siswa_id, s.putaran_id, kh.id FROM sesi s
           JOIN konfirmasi_hasil kh ON kh.sesi_id = s.id
           WHERE s.id = ? AND s.dikonfirmasi_guru IS NOT NULL
             AND kh.id = (SELECT MAX(id) FROM konfirmasi_hasil WHERE sesi_id = s.id)
             AND EXISTS (SELECT 1 FROM kejadian_belajar kb
                         WHERE kb.konfirmasi_id = kh.id AND kb.jenis = 'sertakan_pemetaan')""",
        (sesi_id,),
    ).fetchone()
    if aktif is None:
        return
    kon.execute(
        """INSERT INTO kejadian_belajar
           (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data)
           VALUES (?, ?, ?, ?, 'konfirmasi_dibatalkan', ?)""",
        (aktif["siswa_id"], aktif["putaran_id"], sesi_id, aktif["id"],
         json.dumps({"alasan": "opt_in_dicabut"})),
    )
    kon.execute("UPDATE sesi SET dikonfirmasi_guru = NULL, fingerprint_konfirmasi = NULL WHERE id = ?", (sesi_id,))


class KonfirmasiBelumLengkap(ValueError):
    """Pemulihan request-local setelah validasi, tanpa persistensi draf."""

    def __init__(self, masalah, draf):
        super().__init__("Hasil perlu ditinjau sebelum dikonfirmasi.")
        self.masalah = masalah
        self.draf = draf


def _masalah_kelengkapan(kon, sesi_id, dilewati):
    """Jelaskan butir setelah DB menolak; bukan pengganti validasi bukti."""
    masalah = []
    for butir in database.isi_sesi(kon, sesi_id):
        sid = int(butir["sesi_soal_id"])
        if sid in dilewati:
            continue
        alasan = None
        if (butir["jawaban_id"] is None or butir["benar"] is None
                or (not bool(butir["benar"]) and butir["kode_final"] is None)):
            alasan = (
                "kosong" if not (butir["jawaban"] or "").strip()
                and not (butir["cara"] or "").strip() else "penilaian"
            )
        elif bool(butir["benar"]) and (
            butir["kode_final"] is not None or butir["malrule_id"] is not None
        ):
            alasan = "tidak_konsisten"
        if alasan:
            masalah.append((sid, int(butir["nomor"]), alasan))
    return tuple(masalah)


def _draf_pemulihan(kon, sesi_id, data, koreksi):
    """Pertahankan input yang sah dan fallback parsial sesuai kontrak koreksi."""
    from assistant_inline import DrafButir, DrafKoreksi

    butir = []
    for baris in database.isi_sesi(kon, sesi_id):
        sid = int(baris["sesi_soal_id"])
        butir.append((sid, DrafButir(
            data.get(f"jwb_{sid}", koreksi[f"jwb_{sid}"]),
            data.get(f"kode_{sid}", koreksi[f"kode_{sid}"]),
            data.get(f"cara_{sid}", koreksi[f"cara_{sid}"]),
            data.get(f"cek_pemahaman_{sid}", ""),
            f"dilewati_{sid}" in data,
            f"belum_{sid}" in koreksi,
            data.get(f'catatan_tinjauan_{sid}'), data.get(f'provenance_{sid}'),
            data.get(f'jawaban_bantuan_{sid}'), data.get(f'versi_tinjauan_{sid}'),
        )))
    return DrafKoreksi(tuple(butir), data.get("sertakan_pemetaan") == "1")


def _masalah_tinjauan(kon, sesi_id, galat):
    sid = getattr(galat, 'sid', None)
    return tuple((int(b['sesi_soal_id']), int(b['nomor']), str(galat))
                 for b in database.isi_sesi(kon, sesi_id)
                 if sid is None or int(b['sesi_soal_id']) == sid)


def konfirmasi_dari_form(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    data: Mapping[str, str],
) -> int:
    """Simpan koreksi dan snapshot sebagai satu transaksi kecil atomik."""
    validasi_form_konfirmasi(kon, sesi_id, data)
    sesi = kon.execute(
        "SELECT siswa_id, putaran_id, mode, tujuan FROM sesi WHERE id = ?",
        (sesi_id,),
    ).fetchone()
    if sesi is None:
        raise ValueError("sesi tidak dikenal")

    kon.execute("SAVEPOINT konfirmasi_http")
    try:
        from teacher_pages import simpan_sesi

        import review_store
        _cabut_opt_in_bila_diminta(kon, sesi_id, data)
        koreksi, berubah = _koreksi_form(kon, sesi_id, data)
        try:
            review_store.simpan(kon, sesi_id, data, guru)
        except ValueError as galat:
            raise KonfirmasiBelumLengkap(_masalah_tinjauan(kon, sesi_id, galat), _draf_pemulihan(kon, sesi_id, data, koreksi)) from galat
        if berubah:
            simpan_sesi(kon, sesi_id, koreksi, tinjauan_disimpan=True)
        tersimpan = review_store.muat(kon, sesi_id)
        dilewati = {
            sid for sid, t in tersimpan.items()
            if t['dilewati'] and f'jwb_{sid}' not in data and f'dilewati_{sid}' not in data
        } | {
            butir_id
            for nama, nilai in data.items()
            if nama.startswith("dilewati_") and nilai == "1"
            for butir_id in (_id_butir_dari_field(nama),)
            if butir_id is not None
        }
        cek_pemahaman = {sid: t['pemahaman'] for sid, t in tersimpan.items()
                         if t['pemahaman'] and f'cek_pemahaman_{sid}' not in data}
        cek_pemahaman.update({
            butir_id: nilai
            for nama, nilai in data.items()
            if nama.startswith("cek_pemahaman_") and nilai
            for butir_id in (_id_butir_dari_field(nama),)
            if butir_id is not None
        })
        try:
            konfirmasi_id = database.konfirmasi_hasil(
                kon,
                sesi_id,
                guru=guru,
                dilewati=dilewati,
                cek_pemahaman=cek_pemahaman,
            )
        except ValueError as galat:
            masalah = _masalah_kelengkapan(kon, sesi_id, dilewati)
            if str(galat) in {'sesi belum selesai', 'sesi dibatalkan', 'sesi tidak dikenal', 'sesi tidak memiliki butir'}:
                raise
            if str(galat) != "outcome belum lengkap":
                masalah = _masalah_tinjauan(kon, sesi_id, galat)
            if not masalah:
                raise
            raise KonfirmasiBelumLengkap(
                masalah, _draf_pemulihan(kon, sesi_id, data, koreksi)
            ) from galat
        if data.get("sertakan_pemetaan") == "1":
            if sesi["mode"] != "diagnostik" or sesi["tujuan"] != "bebas":
                raise ValueError("hanya sesi diagnostik bebas dapat disertakan")
            ada = kon.execute(
                """SELECT 1 FROM kejadian_belajar
                   WHERE sesi_id = ? AND konfirmasi_id = ?
                     AND jenis = 'sertakan_pemetaan'""",
                (sesi_id, konfirmasi_id),
            ).fetchone()
            if ada is None:
                kon.execute(
                    """INSERT INTO kejadian_belajar
                           (siswa_id, putaran_id, sesi_id, konfirmasi_id,
                            jenis, data)
                       VALUES (?, ?, ?, ?, 'sertakan_pemetaan', '{}')""",
                    (
                        sesi["siswa_id"],
                        sesi["putaran_id"],
                        sesi_id,
                        konfirmasi_id,
                    ),
                )
        kon.execute("RELEASE SAVEPOINT konfirmasi_http")
        return konfirmasi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT konfirmasi_http")
        kon.execute("RELEASE SAVEPOINT konfirmasi_http")
        raise


def simpan_tinjauan_dari_form(kon, sesi_id, guru, data):
    """Simpan draft tinjauan tanpa membuat bukti, opt-in, atau kelulusan."""
    validasi_form_konfirmasi(kon, sesi_id, data)
    status = kon.execute('SELECT selesai,dibatalkan FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    if not status or not status['selesai'] or status['dibatalkan']:
        raise ValueError('Sesi belum tersedia untuk ditinjau.')
    kon.execute('SAVEPOINT tinjauan_http')
    try:
        import review_store
        from teacher_pages import simpan_sesi
        koreksi, berubah = _koreksi_form(kon, sesi_id, data)
        try:
            review_store.simpan(kon, sesi_id, data, guru)
        except ValueError as galat:
            raise KonfirmasiBelumLengkap(_masalah_tinjauan(kon, sesi_id, galat), _draf_pemulihan(kon, sesi_id, data, koreksi)) from galat
        if berubah:
            simpan_sesi(kon, sesi_id, koreksi, tinjauan_disimpan=True)
        kon.execute('RELEASE SAVEPOINT tinjauan_http')
    except Exception:
        kon.execute('ROLLBACK TO SAVEPOINT tinjauan_http')
        kon.execute('RELEASE SAVEPOINT tinjauan_http')
        raise


def _putaran_aktif(
    kon: sqlite3.Connection, siswa_id: int, level: str
) -> int | None:
    tutup = tuple(sorted(_EVENT_PUTARAN_TUTUP))
    baris = kon.execute(
        """SELECT pf.id FROM putaran_fokus pf
           WHERE pf.siswa_id = ? AND pf.level = ?
             AND NOT EXISTS (
                 SELECT 1 FROM kejadian_belajar kb
                 WHERE kb.putaran_id = pf.id
                   AND kb.jenis IN (?, ?, ?)
             )
           ORDER BY pf.id DESC LIMIT 1""",
        (siswa_id, level, *tutup),
    ).fetchone()
    return None if baris is None else int(baris["id"])


def _occurrence_berikutnya(kon, putaran_id, rencana):
    """Nomori pengulangan sah; retry pembatalan memakai nomor yang sama."""
    fokus = rencana.kandidat or tuple(
        item.kunci for item in (rencana.putaran.fokus if rencana.putaran else ())
    )
    cocok = []
    for baris in kon.execute(
        """SELECT kb.data, s.bagian_checkpoint FROM kejadian_belajar kb
           JOIN sesi s ON s.id = kb.sesi_id
           WHERE kb.putaran_id = ? AND kb.jenis = 'sesi_dibuat'
             AND s.dibatalkan IS NULL AND s.dikonfirmasi_guru IS NOT NULL""",
        (putaran_id,),
    ):
        data = json.loads(baris["data"])
        if data.get("tindakan") != rencana.tindakan:
            continue
        if {tuple(item) for item in data.get("fokus", [])} != set(fokus):
            continue
        if rencana.tindakan == "checkpoint" and baris["bagian_checkpoint"] != rencana.bagian_checkpoint:
            continue
        cocok.append(int(data.get("occurrence", 1)))
    if rencana.tindakan == "checkpoint":
        from cycle_carry import bukti_lanjutan

        siswa = kon.execute("SELECT siswa_id FROM putaran_fokus WHERE id = ?",
                            (putaran_id,)).fetchone()
        if siswa is not None:
            bukti = bukti_lanjutan(database.muat_bukti_siklus(kon, siswa["siswa_id"]))
            cocok = [*cocok, *(s.occurrence for s in bukti.sesi
                     if s.putaran_id == putaran_id and s.tujuan == "checkpoint"
                     and s.dikonfirmasi is not None and s.dibatalkan is None
                     and s.bagian_checkpoint == rencana.bagian_checkpoint
                     and s.occurrence is not None and set(fokus) <= set(s.target_fokus))]
    return max(cocok, default=0) + 1


def buat_dari_rekomendasi(
    kon: sqlite3.Connection, siswa_id: int
) -> tuple[int, bool]:
    """Hitung ulang rekomendasi dan kembalikan sesi tujuan secara atomik.

    Nilai bool menandai apakah sesi baru dibuat. Seluruh keputusan berasal dari
    state server; tidak ada tahap, fokus, putaran, seed, atau occurrence dari
    browser yang dipakai.
    """
    kon.execute("SAVEPOINT buat_rekomendasi_http")
    try:
        siswa = kon.execute(
            "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        if siswa is None:
            raise ValueError("siswa tidak dikenal")
        putaran_id = _putaran_aktif(kon, siswa_id, siswa["tingkat"])
        if putaran_id is None:
            putaran_id = database.buat_putaran_fokus(
                kon, siswa_id, siswa["tingkat"]
            )

        bukti = database.muat_bukti_siklus(kon, siswa_id)
        rencana = rencana_berikutnya(bukti, siswa_id)
        if rencana.tindakan in {"lanjutkan_sesi", "konfirmasi_hasil"}:
            if rencana.sesi_id is None:
                raise ValueError("rekomendasi sesi tidak lengkap")
            kon.execute("RELEASE SAVEPOINT buat_rekomendasi_http")
            return rencana.sesi_id, False
        if rencana.tindakan not in _AKSI_SESI:
            raise ValueError("rekomendasi belum dapat dibuat menjadi sesi")

        sebelum = {
            int(baris["id"])
            for baris in kon.execute(
                "SELECT id FROM sesi WHERE siswa_id = ?", (siswa_id,)
            ).fetchall()
        }
        sesi_id = database.buat_sesi_dari_rencana(
            kon,
            siswa_id,
            rencana,
            putaran_id=putaran_id,
            seed=random.SystemRandom().randint(1, 9_999_999),
            occurrence=_occurrence_berikutnya(kon, putaran_id, rencana),
        )
        kon.execute("RELEASE SAVEPOINT buat_rekomendasi_http")
        return sesi_id, sesi_id not in sebelum
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_rekomendasi_http")
        kon.execute("RELEASE SAVEPOINT buat_rekomendasi_http")
        raise


def _simpan_fokus_otomatis(kon, bukti, putaran, fokus):
    """Ikat fokus pilihan reducer ke snapshot sumber yang sah."""
    from learning_cycle import _sesi_bukti_pemetaan, _kunci_outcome

    sesi_sah = _sesi_bukti_pemetaan(bukti, putaran)
    sumber_per_fokus = tuple(
        (kunci, [s.id for s in sesi_sah
                 if any(_kunci_outcome(o) == kunci for o in s.outcomes)])
        for kunci in fokus
    )
    if any(not sumber for _, sumber in sumber_per_fokus):
        raise ValueError("fokus tidak memiliki bukti pemetaan")
    for kunci, sumber in sumber_per_fokus:
        database.tambah_anggota_fokus(
            kon, putaran.id, *kunci, sumber,
            izinkan_provenance_historis=True,
        )


def catat_intervensi_selesai(
    kon: sqlite3.Connection,
    siswa_id: int,
    putaran_id: int,
    fokus: tuple[str, str, str | None],
    pendekatan_id: str,
) -> None:
    """Catat intervensi hanya untuk fokus aktif dan materi yang direview."""
    bukti = database.muat_bukti_siklus(kon, siswa_id)
    from learning_cycle import _putaran_aktif as aktif_domain, _putaran_dengan_override

    putaran = _putaran_dengan_override(aktif_domain(bukti), bukti.kejadian)
    if putaran is None or putaran.id != putaran_id:
        raise ValueError("fokus bukan anggota putaran aktif")
    rencana = rencana_berikutnya(bukti, siswa_id)
    otomatis = not putaran.fokus and rencana.tindakan == "intervensi"
    fokus_sah = (
        tuple(item.kunci for item in rencana.putaran.fokus)
        if otomatis and rencana.putaran else putaran.fokus
    )
    if fokus not in fokus_sah:
        raise ValueError("fokus bukan anggota putaran aktif")
    pendekatan_sah = {
        materi.pendekatan_id
        for materi in interventions.pilihan_untuk_fokus(fokus)
        if materi.tersedia
    }
    if pendekatan_id not in pendekatan_sah:
        raise ValueError("pendekatan intervensi tidak dikenal")
    if otomatis:
        _simpan_fokus_otomatis(kon, bukti, putaran, fokus_sah)
    data = json.dumps(
        {"fokus": list(fokus), "pendekatan_id": pendekatan_id},
        ensure_ascii=False,
        sort_keys=True,
    )
    ada = kon.execute(
        """SELECT 1 FROM kejadian_belajar
           WHERE siswa_id = ? AND putaran_id = ?
             AND jenis = 'intervensi_selesai' AND data = ?""",
        (siswa_id, putaran_id, data),
    ).fetchone()
    if ada is None:
        kon.execute(
            """INSERT INTO kejadian_belajar
                   (siswa_id, putaran_id, jenis, data)
               VALUES (?, ?, 'intervensi_selesai', ?)""",
            (siswa_id, putaran_id, data),
        )


def ubah_fokus(kon, siswa_id, fokus_baru):
    """Jalankan override berikut provenance dalam transaksi atomik."""
    kon.execute("SAVEPOINT override_atomik")
    try:
        hasil = _ubah_fokus(kon, siswa_id, fokus_baru)
        kon.execute("RELEASE SAVEPOINT override_atomik")
        return hasil
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT override_atomik")
        kon.execute("RELEASE SAVEPOINT override_atomik")
        raise


def _ubah_fokus(
    kon: sqlite3.Connection,
    siswa_id: int,
    fokus_baru: tuple[str, str, str | None],
) -> int:
    """Ganti fokus; setelah intervensi, tutup putaran dan batalkan turunannya."""
    siswa = kon.execute(
        "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None:
        raise ValueError("siswa tidak dikenal")
    if fokus_baru[1] not in {"B", "K", "H", "E", "N", "T"} or topics.pemilik_template(fokus_baru[0]) is None:
        raise ValueError("fokus baru tidak dikenal")
    putaran_id = _putaran_aktif(kon, siswa_id, siswa["tingkat"])
    if putaran_id is None:
        raise ValueError("putaran aktif tidak ditemukan")
    sumber = [
        int(baris["sesi_id"])
        for baris in kon.execute(
            """SELECT DISTINCT bf.sesi_id FROM bukti_fokus bf
               JOIN anggota_fokus af ON af.id = bf.anggota_fokus_id
               WHERE af.putaran_id = ? ORDER BY bf.sesi_id""",
            (putaran_id,),
        ).fetchall()
    ]
    if not sumber:
        bukti = database.muat_bukti_siklus(kon, siswa_id)
        from learning_cycle import _putaran_aktif as aktif_domain

        rencana = rencana_berikutnya(bukti, siswa_id)
        if rencana.tindakan != "intervensi" or rencana.putaran is None:
            raise ValueError("override fokus memerlukan provenance")
        from learning_cycle import _sesi_bukti_pemetaan

        sumber = [s.id for s in _sesi_bukti_pemetaan(bukti, aktif_domain(bukti))]
    sudah_intervensi = kon.execute(
        """SELECT 1 FROM kejadian_belajar
           WHERE putaran_id = ? AND jenis = 'intervensi_selesai' LIMIT 1""",
        (putaran_id,),
    ).fetchone() is not None
    kon.execute("SAVEPOINT ubah_fokus_http")
    try:
        if belum := kon.execute(
            """SELECT 1 FROM anggota_fokus
               WHERE putaran_id = ? AND template_id = ?
                 AND kode_intervensi = ? AND malrule_id_kanonis = ?""",
            (putaran_id, fokus_baru[0], fokus_baru[1], fokus_baru[2] or ""),
        ).fetchone():
            raise ValueError("fokus baru sama dengan fokus aktif")
        del belum
        if sudah_intervensi:
            kon.execute(
                """INSERT INTO kejadian_belajar
                       (siswa_id, putaran_id, jenis, data)
                   VALUES (?, ?, 'override_ditutup', ?)""",
                (
                    siswa_id,
                    putaran_id,
                    json.dumps({"fokus_baru": list(fokus_baru)}, sort_keys=True),
                ),
            )
            turunan = kon.execute(
                """SELECT id FROM sesi
                   WHERE siswa_id = ? AND putaran_id = ?
                     AND tujuan != 'bebas' AND dibatalkan IS NULL""",
                (siswa_id, putaran_id),
            ).fetchall()
            for sesi in turunan:
                database.batalkan_sesi(
                    kon, int(sesi["id"]), "fokus putaran diubah"
                )
            baru = database.buat_putaran_fokus(
                kon, siswa_id, siswa["tingkat"]
            )
            database.tambah_anggota_fokus(
                kon,
                baru,
                fokus_baru[0],
                fokus_baru[1],
                fokus_baru[2],
                sumber,
                izinkan_provenance_historis=True,
            )
        else:
            ada_anggota = kon.execute(
                "SELECT 1 FROM anggota_fokus WHERE putaran_id = ?", (putaran_id,)
            ).fetchone()
            if ada_anggota is None:
                database.tambah_anggota_fokus(
                    kon, putaran_id, fokus_baru[0], fokus_baru[1], fokus_baru[2],
                    sumber, izinkan_provenance_historis=True,
                )
            data = json.dumps(
                {"fokus": [list(fokus_baru)]}, ensure_ascii=False, sort_keys=True
            )
            kon.execute(
                """INSERT INTO kejadian_belajar
                       (siswa_id, putaran_id, jenis, data)
                   VALUES (?, ?, 'fokus_diubah', ?)""",
                (siswa_id, putaran_id, data),
            )
            baru = putaran_id
        kon.execute("RELEASE SAVEPOINT ubah_fokus_http")
        return baru
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT ubah_fokus_http")
        kon.execute("RELEASE SAVEPOINT ubah_fokus_http")
        raise


def proses_aksi(
    kon: sqlite3.Connection, siswa_id: int, data: Mapping[str, str]
) -> None:
    """Validasi payload aksi domain sebelum menulis event."""
    aksi = data.get("aksi", "")
    if aksi == "mulai_putaran_baru":
        if set(data) != {"aksi"}:
            raise ValueError("putaran baru dihitung ulang oleh server")
        from cycle_restart import mulai_putaran_baru

        mulai_putaran_baru(kon, siswa_id)
        return
    kunci_sah = {
        "aksi", "putaran_id", "template_id", "kode_intervensi",
        "malrule_id", "pendekatan_id",
    }
    if set(data) - kunci_sah:
        raise ValueError("payload aksi tidak dikenal")
    fokus = (
        data.get("template_id", ""),
        data.get("kode_intervensi", ""),
        data.get("malrule_id") or None,
    )
    if aksi in {"intervensi_selesai", "pengenalan_selesai"}:
        try:
            putaran_id = int(data.get("putaran_id", ""))
        except ValueError as exc:
            raise ValueError("putaran tidak dikenal") from exc
        if aksi == "pengenalan_selesai":
            from learning_sessions import tandai_pengenalan_selesai

            siswa = kon.execute(
                "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
            ).fetchone()
            if siswa is None or _putaran_aktif(kon, siswa_id, siswa["tingkat"]) != putaran_id:
                raise ValueError("putaran pengenalan tidak aktif")
            tandai_pengenalan_selesai(
                kon, siswa_id, putaran_id, fokus, data.get("pendekatan_id", "")
            )
        else:
            catat_intervensi_selesai(
                kon, siswa_id, putaran_id, fokus, data.get("pendekatan_id", "")
            )
        return
    if aksi == "ubah_fokus":
        ubah_fokus(kon, siswa_id, fokus)
        return
    raise ValueError("aksi siklus tidak dikenal")


def batalkan_sesi(
    kon: sqlite3.Connection, sesi_id: int, alasan: str
) -> int:
    """Batalkan sesi siklus tanpa menghapus soal maupun provenance."""
    sesi = kon.execute(
        """SELECT siswa_id, putaran_id, tujuan, dibatalkan
           FROM sesi WHERE id = ?""",
        (sesi_id,),
    ).fetchone()
    if sesi is None:
        raise ValueError("sesi tidak dikenal")
    berbukti = kon.execute(
        """SELECT 1 FROM konfirmasi_hasil WHERE sesi_id = ?
           UNION ALL SELECT 1 FROM bukti_fokus WHERE sesi_id = ?""",
        (sesi_id, sesi_id),
    ).fetchone() is not None
    if (sesi["putaran_id"] is None or sesi["tujuan"] == "bebas") and not berbukti:
        raise ValueError("hanya sesi terpandu atau berbukti yang dapat dibatalkan")
    if sesi["dibatalkan"] is not None:
        raise ValueError("sesi sudah dibatalkan")
    if len(alasan) > 300:
        raise ValueError("alasan pembatalan terlalu panjang")
    database.batalkan_sesi(kon, sesi_id, alasan.strip())
    return int(sesi["siswa_id"])
