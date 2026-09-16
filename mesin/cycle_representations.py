"""Proyeksi murni bukti satu representasi; histori masukan tidak dimutasi."""
from dataclasses import replace
import re

CATATAN_PEMISAHAN = "Ringkasan memakai representasi terbaru; bukti representasi lain tetap di riwayat sesi."

_MODE = re.compile(r"[a-z][a-z0-9_-]*-v[1-9][0-9]*\Z")


def mode_sah(mode):
    """Identitas versi wajib eksplisit; provenance tidak dikenal bukan teks."""
    return isinstance(mode, str) and len(mode) <= 80 and _MODE.fullmatch(mode) is not None


def satu_mode(outcomes):
    mode = frozenset(o.mode_representasi for o in outcomes)
    return len(mode) == 1 and all(mode_sah(m) for m in mode)


def sesi_satu_representasi(sesi):
    """Pilih mode sesi sah terbaru per template, bukan mayoritas lintas mode.

    Dua mode pada template sama dalam sesi terbaru bersifat ambigu dan tidak
    menyumbang bukti. Sesi lama dengan mode yang sama tetap boleh menyumbang.
    Pemanggil bertanggung jawab menyaring kepemilikan/level/konfirmasi dulu.
    """
    sesi = tuple(sesi)
    terbaru = {}
    for s in sorted(sesi, key=lambda s: (s.tanggal, s.id)):
        template = frozenset(o.template_id for o in s.outcomes if not o.dilewati)
        terbaru = {**terbaru, **{tid: frozenset(o.mode_representasi for o in s.outcomes
                    if o.template_id == tid and not o.dilewati) for tid in template}}
    pilihan = {tid: next(iter(mode)) for tid, mode in terbaru.items()
               if len(mode) == 1 and all(mode_sah(m) for m in mode)}
    hasil = ()
    for s in sesi:
        outcomes = tuple(o for o in s.outcomes
                         if pilihan.get(o.template_id) == o.mode_representasi
                         or o.dilewati)
        if s.outcomes and not outcomes:
            continue
        target = tuple(k for k in s.target_fokus
                       if any(o.template_id == k[0] for o in outcomes) or not s.outcomes)
        hasil = (*hasil, replace(s, outcomes=outcomes, target_fokus=target))
    return hasil


def sesi_bukti_sah(bukti, putaran):
    """Satu palang bukti untuk pemilihan mode dan semua konsumen pedagogis."""
    opt_in = frozenset((e.sesi_id, e.konfirmasi_id) for e in bukti.kejadian
                      if e.jenis == "sertakan_pemetaan" and e.konfirmasi_id is not None)
    kandidat = tuple(s for s in bukti.sesi
        if s.format_jawaban == 'isian' and s.siswa_id == bukti.siswa_id and s.level == bukti.level_aktif
        and s.dibatalkan is None and s.selesai is not None and s.dikonfirmasi is not None
        and ((s.tujuan == "bebas" and (s.id, s.konfirmasi_id) in opt_in)
             or (s.tujuan != "bebas" and (putaran is None or s.putaran_id == putaran.id))))
    return kandidat


def bukti_satu_representasi(bukti, putaran):
    """Pilih kelompok mode tanpa menghapus sesi lain dari histori masukan."""
    kandidat = sesi_bukti_sah(bukti, putaran)
    kunci = frozenset((s.id, s.putaran_id) for s in kandidat)
    dipilih = {(s.id, s.putaran_id): s for s in sesi_satu_representasi(kandidat)}
    semua = tuple(dipilih.get((s.id, s.putaran_id), s) for s in bukti.sesi
                  if (s.id, s.putaran_id) not in kunci or (s.id, s.putaran_id) in dipilih)
    return replace(bukti, sesi=semua)
