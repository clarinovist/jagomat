"""Adapter baca peta penguasaan; tidak mengubah penyimpanan atau bukti asli."""
from collections import defaultdict
from dataclasses import replace

import question_views


def lengkapi_bukti_materi(kon, bukti):
    """Perkaya snapshot aktif dengan mode/pola/sidik serta profil soal tervalidasi.

    Metadata hanya untuk pembaca guru. Profil global bukan sumber profil outcome;
    snapshot, sesi, bank soal, dan penyajian harus cocok. Tidak merekonstruksi sidik
    warisan atau mengubah diagnosis mutable menjadi bukti baru.
    """
    metadata = {b['id']: b for b in kon.execute(
        '''SELECT s.id, s.mode, s.level, s.format_jawaban,
                  s.tujuan, s.tanggal, s.selesai, s.dikonfirmasi_guru, s.dibatalkan, s.putaran_id,
                  (SELECT kh.id FROM konfirmasi_hasil kh
                   WHERE kh.sesi_id=s.id AND s.dikonfirmasi_guru IS NOT NULL
                     AND kh.fingerprint=s.fingerprint_konfirmasi
                   ORDER BY kh.nomor_urut DESC, kh.id DESC LIMIT 1) AS konfirmasi_id
           FROM sesi s WHERE s.siswa_id=?''', (bukti.siswa_id,),
    )}
    pola = defaultdict(list)
    sumber = {}
    for b in kon.execute(
        '''SELECT ss.*, so.template_id, so.parameter, so.level, so.cerita
           FROM sesi_soal ss JOIN sesi se ON se.id=ss.sesi_id
           JOIN soal so ON so.id=ss.soal_id
           WHERE se.siswa_id=? ORDER BY ss.sesi_id, ss.nomor''', (bukti.siswa_id,),
    ):
        pola[b['sesi_id']].append(b['template_id'])
        sumber[(b['sesi_id'], b['id'])] = b
    outcomes = defaultdict(list)
    for b in kon.execute(
        '''SELECT kh.sesi_id, o.* FROM snapshot_outcome o
           JOIN konfirmasi_hasil kh ON kh.id=o.konfirmasi_id
           JOIN sesi se ON se.id=kh.sesi_id
           WHERE se.siswa_id=? AND se.dikonfirmasi_guru IS NOT NULL
             AND kh.id=(SELECT aktif.id FROM konfirmasi_hasil aktif
                        WHERE aktif.sesi_id=se.id AND aktif.fingerprint=se.fingerprint_konfirmasi
                        ORDER BY aktif.nomor_urut DESC, aktif.id DESC LIMIT 1)
           ORDER BY kh.sesi_id, o.nomor''', (bukti.siswa_id,),
    ):
        outcomes[(b['sesi_id'], b['konfirmasi_id'])].append(b)
    sesi = []
    for s in bukti.sesi:
        if s.siswa_id != bukti.siswa_id or s.id not in metadata:
            raise ValueError('metadata sesi bukan milik siswa')
        meta = metadata[s.id]
        if (s.konfirmasi_id != meta['konfirmasi_id'] or s.level != meta['level']
                or s.format_jawaban != meta['format_jawaban'] or s.tujuan != meta['tujuan']
                or s.tanggal.isoformat() != meta['tanggal'][:10] or s.selesai != meta['selesai']
                or s.dikonfirmasi != meta['dikonfirmasi_guru'] or s.dibatalkan != meta['dibatalkan']
                or s.putaran_id != meta['putaran_id']):
            raise ValueError('versi bukti peta berubah; muat ulang laporan')
        baris = outcomes[(s.id, s.konfirmasi_id)]
        if len(baris) != len(s.outcomes):
            raise ValueError('versi bukti peta berubah; muat ulang laporan')
        if s.konfirmasi_id is not None:
            import context_store
            target_snapshot = {
                b['nomor']: (b['target_template_id'], b['target_kode_intervensi'], b['target_malrule_id'])
                for b in baris if b['target_template_id'] is not None
            }
            context_store.validasi_arsip(kon, s.id, s.konfirmasi_id, target_snapshot)
        hasil = []
        for o, b in zip(s.outcomes, baris):
            asal = sumber.get((s.id, b['sesi_soal_id']))
            if (asal is None or o.template_id != b['template_id']
                    or asal['template_id'] != b['template_id'] or asal['nomor'] != b['nomor']
                    or b['level_efektif'] != s.level or asal['level'] != b['level_efektif']):
                raise ValueError('konteks sumber snapshot tidak cocok')
            target = (None if b['target_template_id'] is None else
                      (b['target_template_id'], b['target_kode_intervensi'], b['target_malrule_id']))
            nilai = (o.benar, o.kode_final, o.malrule_id, o.dilewati, o.cek_pemahaman, o.target_fokus)
            harapan = (None if b['benar'] is None else bool(b['benar']), b['kode_final'],
                       b['malrule_id'], bool(b['dilewati']), b['cek_pemahaman'], target)
            if nilai != harapan:
                raise ValueError('outcome tidak cocok dengan snapshot aktif')
            penyajian = question_views.penyajian_dari_baris(asal)
            warisan = all(asal[n] is None for n in question_views.KOLOM_SNAPSHOT)
            fingerprint = None if warisan else penyajian.fingerprint_penyajian
            if (o.mode_representasi != penyajian.mode_representasi
                    or o.fingerprint_penyajian != fingerprint):
                raise ValueError('konteks penyajian bukti tidak cocok')
            hasil.append(replace(o, fingerprint_matematis=asal['fingerprint_matematis'],
                                 profil_parameter=b['level_efektif']))
        sesi.append(replace(s, mode=meta['mode'],
                            pola_tersedia=tuple(dict.fromkeys(pola[s.id])), outcomes=tuple(hasil)))
    return replace(bukti, sesi=tuple(sesi))
