"""Penyimpanan opsi publik dan resolver nilai tanpa membaca kunci jawaban.

Pemasangan DDL tetap milik migrasi transaksi pemanggil. Koneksi wajib mendaftarkan
validator sebelum menulis; koneksi tanpa validator gagal tertutup di trigger.
"""
from __future__ import annotations

from contextlib import contextmanager
import sqlite3

from choice_contract import PilihanButir, deserialisasi, fingerprint, serialisasi


def _snapshot_sah(teks, sidik, butir_id, sidik_pertanyaan):
    try:
        deserialisasi(teks, sidik, sesi_soal_id=butir_id,
                      fingerprint_pertanyaan=sidik_pertanyaan)
    except (ValueError, TypeError, OverflowError):
        return 0
    return 1


def daftarkan_validasi(kon: sqlite3.Connection) -> None:
    """Daftarkan validasi struktur publik, tidak mengakses kunci jawaban."""
    kon.create_function("pilihan_snapshot_sah", 4, _snapshot_sah)
    kon.create_function('pilihan_jawaban_sah', 5, _jawaban_sah)


def _jawaban_sah(teks, sidik, sid, pertanyaan, jawaban):
    try:
        p = deserialisasi(teks, sidik, sesi_soal_id=sid, fingerprint_pertanyaan=pertanyaan)
        return int(jawaban == '' or jawaban in {o.nilai for o in p.opsi})
    except (ValueError, TypeError):
        return 0


def validasi_format(nilai):
    if nilai not in ('isian', 'pilihan_ganda'):
        raise ValueError('Format jawaban tidak dikenal.')
    return nilai


def format_sesi(kon, sesi_id):
    b = kon.execute('SELECT format_jawaban FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    if b is None:
        raise ValueError('Sesi tidak dikenal.')
    return validasi_format(b['format_jawaban'])


def daftar_pilihan(kon, sesi_id):
    if format_sesi(kon, sesi_id) == 'isian':
        return {}
    info = kon.execute('SELECT siswa_id FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    return {b['id']: baca_pilihan(kon, info['siswa_id'], sesi_id, b['id']) for b in
            kon.execute('SELECT id FROM sesi_soal WHERE sesi_id=? ORDER BY nomor', (sesi_id,))}


def lengkapi_sesi(kon, siswa_id, sesi_id, lembar):
    from choice_generation import pilihan_soal
    baris = kon.execute('SELECT ss.id,ss.nomor,ss.fingerprint_penyajian,s.kunci FROM sesi_soal ss JOIN soal s ON s.id=ss.soal_id WHERE ss.sesi_id=? ORDER BY ss.nomor', (sesi_id,)).fetchall()
    if len(baris) != len(lembar.soal) or any(s.kunci != b['kunci'] for s,b in zip(lembar.soal,baris)):
        raise ValueError('Kunci bank berbeda dari soal baru; pembuatan pilihan dibatalkan.')
    pilihan = tuple(pilihan_soal(s, b['id'], b['fingerprint_penyajian'], lembar.seed, b['nomor'])
                    for s, b in zip(lembar.soal, baris))
    simpan_pilihan(kon, siswa_id, sesi_id, pilihan)


def arsipkan_pilihan(kon, sesi_id, konfirmasi_id=None):
    tabel = 'konfirmasi_pilihan' if konfirmasi_id is not None else 'pengiriman_pilihan'
    kolom = 'konfirmasi_id' if konfirmasi_id is not None else 'sesi_id'
    induk = konfirmasi_id if konfirmasi_id is not None else sesi_id
    for sid, p in daftar_pilihan(kon, sesi_id).items():
        lama = kon.execute(f'SELECT snapshot_json,fingerprint_opsi FROM {tabel} WHERE {kolom}=? AND sesi_soal_id=?', (induk, sid)).fetchone()
        isi = (serialisasi(p), fingerprint(p))
        if lama is not None:
            if tuple(lama) != isi:
                raise ValueError('Arsip pilihan berubah.')
        else:
            kon.execute(f'INSERT INTO {tabel}({kolom},sesi_soal_id,snapshot_json,fingerprint_opsi) VALUES (?,?,?,?)', (induk, sid, *isi))


def validasi_arsip(kon, sesi_id, konfirmasi_id=None):
    """PG wajib punya salinan utuh; data hilang tidak direkonstruksi saat baca."""
    pilihan = daftar_pilihan(kon, sesi_id)
    if not pilihan:
        return
    tabel = 'konfirmasi_pilihan' if konfirmasi_id is not None else 'pengiriman_pilihan'
    kolom = 'konfirmasi_id' if konfirmasi_id is not None else 'sesi_id'
    induk = konfirmasi_id if konfirmasi_id is not None else sesi_id
    baris = kon.execute(f'SELECT sesi_soal_id,snapshot_json,fingerprint_opsi FROM {tabel} WHERE {kolom}=?', (induk,)).fetchall()
    if {b['sesi_soal_id'] for b in baris} != set(pilihan):
        raise ValueError('Arsip pilihan tidak lengkap; perlu pemulihan.')
    for b in baris:
        p = pilihan[b['sesi_soal_id']]
        if b['snapshot_json'] != serialisasi(p) or b['fingerprint_opsi'] != fingerprint(p):
            raise ValueError('Arsip pilihan tidak cocok; perlu pemulihan.')


def proyeksi_konfirmasi(kon, sesi_id):
    return [{'sesi_soal_id': sid, 'snapshot': serialisasi(p), 'sidik': fingerprint(p)}
            for sid, p in daftar_pilihan(kon, sesi_id).items()]


def baca_pilihan(kon, siswa_id: int, sesi_id: int,
                 sesi_soal_id: int) -> PilihanButir | None:
    """Baca butir milik siswa; snapshot hilang bukan fallback isian.

    Pemanggil menentukan apakah sesi memakai PG. None berarti resource tidak
    ditemukan/bukan milik siswa; ValueError berarti snapshot PG perlu pemulihan.
    """
    baris = kon.execute(
        """SELECT ss.id, ss.fingerprint_penyajian, p.snapshot_json, p.fingerprint_opsi
           FROM sesi_soal ss JOIN sesi se ON se.id=ss.sesi_id
           LEFT JOIN pilihan_butir p ON p.sesi_soal_id=ss.id
           WHERE ss.id=? AND se.id=? AND se.siswa_id=?""",
        (sesi_soal_id, sesi_id, siswa_id),
    ).fetchone()
    if baris is None:
        return None
    if baris["snapshot_json"] is None:
        raise ValueError("Snapshot pilihan belum tersedia.")
    return deserialisasi(baris["snapshot_json"], baris["fingerprint_opsi"],
                         sesi_soal_id=baris["id"],
                         fingerprint_pertanyaan=baris["fingerprint_penyajian"])


@contextmanager
def _transaksi(kon):
    # Tanpa transaksi induk, pertahankan transaksi sampai commit milik pemanggil.
    if not kon.in_transaction:
        kon.execute("BEGIN IMMEDIATE")
    kon.execute("SAVEPOINT simpan_pilihan")
    try:
        yield
        kon.execute("RELEASE SAVEPOINT simpan_pilihan")
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT simpan_pilihan")
        kon.execute("RELEASE SAVEPOINT simpan_pilihan")
        raise


def simpan_pilihan(kon, siswa_id: int, sesi_id: int,
                   pilihan: tuple[PilihanButir, ...]) -> None:
    """Simpan seluruh opsi atomik setelah layanan guru membentuk kandidat sah.

    Ini helper internal, bukan boundary auth guru. Siswa/sesi tetap diperiksa agar
    kandidat lintas keluarga tidak bisa terselip dalam batch. DDL menahan lifecycle.
    """
    if type(pilihan) is not tuple or not pilihan or any(type(p) is not PilihanButir for p in pilihan):
        raise ValueError("Kumpulan pilihan tidak sah.")
    ids = [p.sesi_soal_id for p in pilihan]
    if len(set(ids)) != len(ids):
        raise ValueError("Butir pilihan duplikat.")
    with _transaksi(kon):
        baris = kon.execute(
            """SELECT ss.id, ss.fingerprint_penyajian FROM sesi_soal ss
               JOIN sesi se ON se.id=ss.sesi_id WHERE se.id=? AND se.siswa_id=?""",
            (sesi_id, siswa_id),
        ).fetchall()
        sah = {b["id"]: b["fingerprint_penyajian"] for b in baris}
        if set(ids) != set(sah):
            raise ValueError("Pilihan wajib mencakup semua butir sesi milik siswa.")
        for p in pilihan:
            if p.fingerprint_pertanyaan != sah[p.sesi_soal_id]:
                raise ValueError("Pilihan tidak cocok dengan penyajian pertanyaan.")
            kon.execute(
                "INSERT INTO pilihan_butir(sesi_soal_id,snapshot_json,fingerprint_opsi) VALUES (?,?,?)",
                (p.sesi_soal_id, serialisasi(p), fingerprint(p)),
            )
