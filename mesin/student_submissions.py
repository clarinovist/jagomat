"""Refleksi dan arsip pengiriman; tidak membaca kunci atau diagnosis anak."""
from __future__ import annotations

import json
import re

ALASAN = {
    'maksud_soal': 'Aku belum paham maksud soalnya',
    'langkah_awal': 'Aku paham soalnya, tetapi belum tahu cara memulai',
    'belum_sempat': 'Aku belum sempat mengerjakan',
    'belum_bisa_menjelaskan': 'Aku belum bisa menjelaskan alasannya',
}


class VersiBerubah(ValueError):
    """Tab lama tidak boleh menimpa pekerjaan yang lebih baru."""
    status = 409


def revisi(kon, sesi_id):
    b = kon.execute('SELECT revisi FROM versi_pekerjaan WHERE sesi_id=?', (sesi_id,)).fetchone()
    return int(b[0]) if b else 0


def validasi_versi(kon, sesi_id, data):
    if 'revisi_pekerjaan' not in data:
        from choice_store import format_sesi
        if format_sesi(kon, sesi_id) == 'pilihan_ganda':
            raise VersiBerubah('Muat ulang latihan sebelum menyimpan pilihan.')
        return  # Klien lama: tetap dapat mengirim langsung tanpa refleksi.
    nilai = data['revisi_pekerjaan']
    if not re.fullmatch(r'[0-9]{1,12}', nilai) or int(nilai) != revisi(kon, sesi_id):
        raise VersiBerubah('Pekerjaan berubah di halaman lain. Muat ulang sebelum melanjutkan.')


def kosong(kon, sesi_id):
    """Isian akhir, bukan keberadaan cara/baris jawaban, menentukan kosong."""
    return tuple(int(b[0]) for b in kon.execute(
        """SELECT ss.id FROM sesi_soal ss LEFT JOIN jawaban j ON j.sesi_soal_id=ss.id
           WHERE ss.sesi_id=? AND TRIM(COALESCE(j.jawaban,''))='' ORDER BY ss.nomor""", (sesi_id,)))


def refleksi(kon, sesi_id):
    return {int(b[0]): b[1] for b in kon.execute(
        'SELECT r.sesi_soal_id,r.alasan FROM refleksi_jawaban r JOIN sesi_soal ss ON ss.id=r.sesi_soal_id WHERE ss.sesi_id=?',
        (sesi_id,))}


def simpan_refleksi(kon, sesi_id, data):
    status = kon.execute('SELECT selesai,dibatalkan FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    if not status or status['selesai'] or status['dibatalkan']:
        raise ValueError('Refleksi hanya dapat diubah sebelum latihan dikirim.')
    sah = set(kosong(kon, sesi_id))
    pasangan = []
    for nama, nilai in data.items():
        if not nama.startswith('alasan_kosong_'):
            if nama not in {'aksi', 'revisi_pekerjaan', 'flow_kosong'}:
                raise ValueError('Field refleksi tidak dikenal.')
            continue
        angka = nama[len('alasan_kosong_'):]
        if not angka.isdigit() or int(angka) not in sah or nilai not in {'', *ALASAN}:
            raise ValueError('Alasan atau butir tidak dikenal.')
        pasangan.append((int(angka), nilai))
    for sid, nilai in pasangan:
        kon.execute('INSERT INTO refleksi_jawaban VALUES (?,?) ON CONFLICT(sesi_soal_id) DO UPDATE SET alasan=excluded.alasan', (sid, nilai))


def perlu_refleksi(kon, info, data):
    if data.get('flow_kosong') != '1' or not kosong(kon, info['id']):
        return False
    # Timer konfigurasi server yang sudah jatuh tempo tidak tertahan pertanyaan
    # opsional. Tidak percaya hidden field yang mengaku auto-submit.
    otomatis = (info['mode'] == 'drill' and info['timer_mode'] == 'sesi'
                and info['timer_auto'] and info['detik_lalu'] >= info['durasi_menit'] * 60)
    return not otomatis


def arsipkan(kon, sesi_id, sumber):
    """Atomik dengan finalisasi pemanggil; tidak merekonstruksi sesi warisan."""
    kon.execute('SAVEPOINT arsip_pengiriman')
    try:
        _arsipkan(kon, sesi_id, sumber)
        kon.execute('RELEASE SAVEPOINT arsip_pengiriman')
    except Exception:
        kon.execute('ROLLBACK TO SAVEPOINT arsip_pengiriman')
        kon.execute('RELEASE SAVEPOINT arsip_pengiriman')
        raise


def _arsipkan(kon, sesi_id, sumber):
    """Snapshot satu kali setelah pemeriksaan lifecycle."""
    if sumber not in {'akun', 'tautan', 'foto'}:
        raise ValueError('Sumber pengiriman tidak dikenal.')
    info = kon.execute('SELECT selesai,dibatalkan FROM sesi WHERE id=?', (sesi_id,)).fetchone()
    if not info or info['dibatalkan']:
        raise ValueError('Sesi tidak aktif.')
    if info['selesai'] or kon.execute('SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?', (sesi_id,)).fetchone():
        return
    lampiran = [int(b[0]) for b in kon.execute('SELECT id FROM lampiran WHERE sesi_id=? ORDER BY id', (sesi_id,))]
    kon.execute('INSERT INTO pengiriman_sesi(sesi_id,sumber,lampiran_json) VALUES (?,?,?)',
                (sesi_id, sumber, json.dumps(lampiran)))
    kon.execute("""INSERT INTO pengiriman_butir
        (sesi_id,sesi_soal_id,nomor,jawaban,cara,restatement,belum_pernah,alasan,penyajian_json)
        SELECT ss.sesi_id,ss.id,ss.nomor,COALESCE(j.jawaban,''),COALESCE(j.cara,''),
               COALESCE(j.restatement,''),COALESCE(j.belum_pernah,0),COALESCE(r.alasan,''),
               COALESCE(ss.penyajian_json,'')
        FROM sesi_soal ss LEFT JOIN jawaban j ON j.sesi_soal_id=ss.id
        LEFT JOIN refleksi_jawaban r ON r.sesi_soal_id=ss.id WHERE ss.sesi_id=?""", (sesi_id,))
    from choice_store import arsipkan_pilihan
    arsipkan_pilihan(kon, sesi_id)
