"""Renderer HTML murni halaman admin "Peta kurikulum" (tanpa JS, tanpa DB).

Semua isi diturunkan dari `kurikulum_katalog` (topik, grup, topik cek) dan `kurikulum_cp`
(butir CP Merdeka dan pemetaannya) serta registri `topics` untuk nama resmi topik.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import kurikulum_cp as cp
import kurikulum_katalog as kat
import topics
from admin_komponen import e
from admin_kurikulum_tab import TAB_KURIKULUM, tab_kurikulum

FASE_SD = ("A", "B", "C")
TANPA_SOAL = "belum ada soal"
DI_LUAR_CP = "di luar CP (pengayaan)"
CATATAN = (
    "Peta ini data di kode (kurikulum_katalog dan kurikulum_cp). Mengubahnya berarti mengubah "
    "kode dan merilis ulang, sampai halaman ubah di admin tersedia."
)

# butir id -> ((topik_id, kode grup, nama grup, kecocokan), ...)
_Pelatih = Tuple[str, str, str, str]


def _nama_topik(topik_id: str) -> str:
    try:
        return topics.ambil(topik_id).nama
    except KeyError:
        return topik_id


def _nama_grup() -> Dict[Tuple[str, str], str]:
    return {(t.topik_id, kode): nama for t in kat.KATALOG for kode, nama, _pola in t.grup}


def pelatih_per_butir() -> Dict[str, Tuple[_Pelatih, ...]]:
    """Peta id butir CP -> grup yang melatihnya, urut KATALOG."""
    nama = _nama_grup()
    hasil: Dict[str, List[_Pelatih]] = {}
    for entri in kat.KATALOG:
        for kode, _n, _pola in entri.grup:
            for capaian_id, cocok in cp.CP_PER_GRUP.get((entri.topik_id, kode), ()):
                hasil.setdefault(capaian_id, []).append((entri.topik_id, kode, nama[(entri.topik_id, kode)], cocok))
    return {k: tuple(v) for k, v in hasil.items()}


def _kartu(judul: str, isi: str, meta: str = "") -> str:
    kepala = '<div class="admin-kartu-kepala"><h2>%s</h2>%s</div>' % (
        e(judul), '<span class="admin-meta">%s</span>' % e(meta) if meta else "")
    return '<section class="admin-kartu">%s%s</section>' % (kepala, isi)


def _tabel(kepala: Tuple[str, ...], baris: str, label: str) -> str:
    th = "".join('<th scope="col">%s</th>' % e(k) for k in kepala)
    return (
        '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="%s">'
        '<table class="admin-tabel"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
    ) % (e(label), th, baris)


def _ringkasan(celah_sd: Tuple[cp.ButirCP, ...]) -> str:
    di_luar = sum(1 for isi in cp.CP_PER_GRUP.values() if not isi)
    jumlah_grup = sum(len(t.grup) for t in kat.KATALOG)
    angka = (
        ("Status pemetaan", cp.STATUS_PEMETAAN),
        ("Topik", str(len(kat.KATALOG))),
        ("Grup soal", str(jumlah_grup)),
        ("Butir CP", str(len(cp.CAPAIAN))),
        ("Butir CP SD tanpa soal", str(len(celah_sd))),
        ("Grup di luar CP (pengayaan)", str(di_luar)),
    )
    baris = "".join("<tr><th scope=\"row\">%s</th><td>%s</td></tr>" % (e(k), e(v)) for k, v in angka)
    return _kartu("Ringkasan", _tabel(("Hal", "Nilai"), baris, "Ringkasan peta kurikulum"))


def _celah(celah_sd: Tuple[cp.ButirCP, ...]) -> str:
    di_d = sum(1 for b in cp.butir_tanpa_grup() if b.fase not in FASE_SD)
    if not celah_sd:
        isi = '<p class="admin-meta">Semua butir CP fase A–C sudah dilatih minimal satu grup.</p>'
    else:
        baris = "".join(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(b.id), e(cp.FASE[b.fase]), e(cp.ELEMEN[b.elemen]), e(b.teks))
            for b in celah_sd
        )
        isi = _tabel(("Butir", "Kelas", "Elemen", "Teks CP"), baris, "Celah cakupan SD")
    catatan = '<p class="admin-meta">Fase D (%s) belum dilatih: %d butir, di luar pilot SD.</p>' % (
        e(cp.FASE["D"]), di_d)
    return _kartu("Celah cakupan SD", isi + catatan, "%d butir" % len(celah_sd))


def _sel_pelatih(daftar: Tuple[_Pelatih, ...]) -> str:
    if not daftar:
        return '<span class="admin-meta">%s</span>' % e(TANPA_SOAL)
    return "<br>".join(
        "%s · %s <span class=\"admin-meta\">(%s)</span>" % (e(_nama_topik(t)), e(nama), e(cocok))
        for t, _kode, nama, cocok in daftar
    )


def _baris_elemen(fase: str, elemen: str, peta: Dict[str, Tuple[_Pelatih, ...]]) -> str:
    butir = [b for b in cp.CAPAIAN if b.fase == fase and b.elemen == elemen]
    return "".join(
        "<tr><td><code>%s</code><br>%s</td><td>%s</td></tr>" % (
            e(b.id), e(b.teks), _sel_pelatih(peta.get(b.id, ())))
        for b in butir
    )


def _fase(fase: str, peta: Dict[str, Tuple[_Pelatih, ...]]) -> str:
    bagian = []
    for elemen, nama in cp.ELEMEN.items():
        baris = _baris_elemen(fase, elemen, peta)
        if baris:
            bagian.append("<h3>%s</h3>%s" % (e(nama), _tabel(
                ("Butir CP", "Dilatih oleh"), baris, "%s, %s" % (cp.FASE[fase], nama))))
    jumlah = sum(1 for b in cp.CAPAIAN if b.fase == fase)
    return '<details class="admin-kartu"><summary>Fase %s · %s <span class="admin-meta">%d butir</span></summary>%s</details>' % (
        e(fase), e(cp.FASE[fase]), jumlah, "".join(bagian))


def _per_fase(peta: Dict[str, Tuple[_Pelatih, ...]]) -> str:
    return '<h2>Butir CP per fase</h2>' + "".join(_fase(f, peta) for f in cp.FASE)


def _info_topik(topik_id: str, label: str) -> str:
    kelas_cek = [k for k, daftar in kat.TOPIK_CEK_PER_KELAS.items() if topik_id in daftar]
    if topik_id == kat.TOPIK_CEK_DASAR:
        kelas_cek = [1, 2] + kelas_cek
    cek = "dipakai cek gratis kelas %s" % ", ".join(str(k) for k in kelas_cek) if kelas_cek else "tidak dipakai cek gratis"
    bagian = [("Label awam", label or "-"), ("Cek gratis", cek)]
    try:
        paket = topics.ambil(topik_id)
        bagian.insert(1, ("Level", ", ".join(paket.komposisi) or "-"))
        if paket.hanya_manual:
            bagian.append(("Penanda", "manual-saja"))
    except KeyError:
        bagian.append(("Penanda", "tidak terdaftar di registri topik"))
    return '<p class="admin-meta">%s</p>' % " · ".join("%s: %s" % (e(k), e(v)) for k, v in bagian)


def _baris_grup(topik_id: str, kode: str, nama: str) -> str:
    isi = cp.CP_PER_GRUP.get((topik_id, kode), ())
    if isi:
        sel = "<br>".join(
            "<code>%s</code> %s <span class=\"admin-meta\">(%s)</span>" % (
                e(cid), e(cp.butir(cid).teks), e(cocok))
            for cid, cocok in isi)
    else:
        sel = '<span class="admin-meta">%s</span>' % e(DI_LUAR_CP)
    return "<tr><td>%s<br><code>%s</code></td><td>%s</td></tr>" % (e(nama), e(kode), sel)


def _topik(entri: kat.EntriTopik) -> str:
    baris = "".join(_baris_grup(entri.topik_id, kode, nama) for kode, nama, _p in entri.grup)
    return (
        '<details class="admin-kartu"><summary>%s <span class="admin-meta">%d grup</span></summary>%s%s</details>'
    ) % (e(_nama_topik(entri.topik_id)), len(entri.grup), _info_topik(entri.topik_id, entri.label_awam or ""),
         _tabel(("Grup", "Butir CP dan kecocokan"), baris, "Grup topik " + _nama_topik(entri.topik_id)))


def halaman() -> str:
    celah_sd = tuple(b for b in cp.butir_tanpa_grup() if b.fase in FASE_SD)
    peta = pelatih_per_butir()
    return (
        tab_kurikulum(TAB_KURIKULUM)
        + _ringkasan(celah_sd) + _celah(celah_sd) + _per_fase(peta)
        + "<h2>Topik dan grup soal</h2>" + "".join(_topik(t) for t in kat.KATALOG)
        + '<section class="admin-kartu admin-catatan"><p class="admin-meta">%s</p></section>' % e(CATATAN)
    )
