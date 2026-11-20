"""Renderer HTML murni halaman admin "Peta kurikulum" (tanpa JS, tanpa DB).

Topik, grup, dan butir CP diturunkan dari `kurikulum_katalog` dan `kurikulum_cp`; pemetaan CP per grup
yang ditampilkan adalah nilai EFEKTIF (`kurikulum_override.ItemCP`, bawaan kode atau diubah admin) yang
disuntikkan pemanggil lewat `daftar`. Tanpa `daftar`, nilai bawaan kode dipakai (tanpa menyentuh DB).
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

import kurikulum_cp as cp
import kurikulum_katalog as kat
from kurikulum_override import SUMBER_ADMIN, SUMBER_BAWAAN, ItemCP
import topics
from admin_komponen import e
from admin_kurikulum_tab import TAB_KURIKULUM, tab_kurikulum

FASE_SD = ("A", "B", "C")
TANPA_SOAL = "belum ada soal"
DI_LUAR_CP = "di luar CP (pengayaan)"
CATATAN = (
    "Topik, grup soal, dan butir CP adalah data di kode (kurikulum_katalog dan kurikulum_cp); mengubahnya "
    "berarti mengubah kode dan merilis ulang. Pemetaan CP per grup bisa diubah admin lewat tautan Ubah: "
    "langsung berlaku, tercatat di riwayat, dan bisa dikembalikan ke bawaan kode."
)
RUTE_UBAH = "/admin/kurikulum/cp"

# butir id -> ((topik_id, kode grup, nama grup, kecocokan), ...)
_Pelatih = Tuple[str, str, str, str]


def _nama_topik(topik_id: str) -> str:
    try:
        return topics.ambil(topik_id).nama
    except KeyError:
        return topik_id


def _nama_grup() -> Dict[Tuple[str, str], str]:
    return {(t.topik_id, kode): nama for t in kat.KATALOG for kode, nama, _pola in t.grup}


def _item_bawaan() -> Tuple[ItemCP, ...]:
    """ItemCP bawaan kode (tanpa DB), urut KATALOG; dipakai saat pemanggil tidak menyuntik `daftar`."""
    return tuple(
        ItemCP(t, k, tuple(isi), tuple(isi), SUMBER_BAWAAN, 0, None) for (t, k), isi in cp.CP_PER_GRUP.items())


def url_ubah(topik_id: str, grup_kode: str, hasil: Optional[str] = None) -> str:
    """URL halaman ubah satu grup (`grup` di-encode; `hasil` opsional kode banner)."""
    kueri = {"grup": "%s/%s" % (topik_id, grup_kode)}
    if hasil:
        kueri["hasil"] = hasil
    return "%s?%s" % (RUTE_UBAH, urlencode(kueri))


def peta_efektif(daftar: Sequence[ItemCP]) -> Dict[Tuple[str, str], Tuple[Tuple[str, str], ...]]:
    return {(i.topik_id, i.grup_kode): i.efektif for i in daftar}


def butir_tanpa_grup_efektif(daftar: Sequence[ItemCP]) -> Tuple[cp.ButirCP, ...]:
    """Celah cakupan dari pemetaan EFEKTIF (butir CP yang tak dilatih grup mana pun), urut CAPAIAN."""
    terpakai = {cid for isi in peta_efektif(daftar).values() for cid, _ in isi}
    return tuple(b for b in cp.CAPAIAN if b.id not in terpakai)


def pelatih_per_butir(daftar: Optional[Sequence[ItemCP]] = None) -> Dict[str, Tuple[_Pelatih, ...]]:
    """Peta id butir CP -> grup yang melatihnya (pemetaan efektif), urut KATALOG."""
    peta = peta_efektif(_item_bawaan() if daftar is None else daftar)
    nama = _nama_grup()
    hasil: Dict[str, List[_Pelatih]] = {}
    for entri in kat.KATALOG:
        for kode, _n, _pola in entri.grup:
            for capaian_id, cocok in peta.get((entri.topik_id, kode), ()):
                hasil.setdefault(capaian_id, []).append((entri.topik_id, kode, nama[(entri.topik_id, kode)], cocok))
    return {k: tuple(v) for k, v in hasil.items()}


def _kartu(judul: str, isi: str, meta: str = "") -> str:
    kepala = '<div class="admin-kartu-kepala"><h2>%s</h2>%s</div>' % (
        e(judul), '<span class="admin-meta">%s</span>' % e(meta) if meta else "")
    return '<section class="admin-kartu">%s%s</section>' % (kepala, isi)


def _daftar(butir: str, label: str) -> str:
    """Daftar blok bertumpuk, bukan tabel: teks CP panjang tetap terbaca utuh di HP 390 px."""
    return '<ul class="kurikulum-daftar" aria-label="%s">%s</ul>' % (e(label), butir)


def _blok(kepala: str, isi: str) -> str:
    return '<li><p class="kurikulum-kepala">%s</p><div>%s</div></li>' % (kepala, isi)


def _ringkasan(celah_sd: Tuple[cp.ButirCP, ...], daftar: Sequence[ItemCP]) -> str:
    di_luar = sum(1 for item in daftar if not item.efektif)
    diubah = sum(1 for item in daftar if item.sumber == SUMBER_ADMIN)
    jumlah_grup = sum(len(t.grup) for t in kat.KATALOG)
    angka = (
        ("Status pemetaan", cp.STATUS_PEMETAAN),
        ("Topik", str(len(kat.KATALOG))),
        ("Grup soal", str(jumlah_grup)),
        ("Butir CP", str(len(cp.CAPAIAN))),
        ("Butir CP SD tanpa soal", str(len(celah_sd))),
        ("Grup di luar CP (pengayaan)", str(di_luar)),
        ("Grup dengan pemetaan diubah admin", str(diubah)),
    )
    # Daftar rincian, bukan tabel: di HP `admin-rincian` menjadi satu kolom tanpa gulir samping.
    isi = "".join("<dt>%s</dt><dd>%s</dd>" % (e(k), e(v)) for k, v in angka)
    return _kartu("Ringkasan", '<dl class="admin-rincian">%s</dl>' % isi)


def _celah(celah_sd: Tuple[cp.ButirCP, ...], daftar: Sequence[ItemCP]) -> str:
    di_d = sum(1 for b in butir_tanpa_grup_efektif(daftar) if b.fase not in FASE_SD)
    if not celah_sd:
        isi = '<p class="admin-meta">Semua butir CP fase A–C sudah dilatih minimal satu grup.</p>'
    else:
        # Teks CP panjang: daftar rincian agar terbaca utuh di HP (tabel 4 kolom menyembunyikannya).
        isi = '<dl class="admin-rincian">%s</dl>' % "".join(
            '<dt><code>%s</code><br><span class="admin-meta">%s · %s</span></dt><dd>%s</dd>' % (
                e(b.id), e(cp.FASE[b.fase]), e(cp.ELEMEN[b.elemen]), e(b.teks))
            for b in celah_sd
        )
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
        _blok("<code>%s</code> %s" % (e(b.id), e(b.teks)),
              '<span class="admin-meta">Dilatih oleh:</span> ' + _sel_pelatih(peta.get(b.id, ())))
        for b in butir
    )


def _fase(fase: str, peta: Dict[str, Tuple[_Pelatih, ...]]) -> str:
    bagian = []
    for elemen, nama in cp.ELEMEN.items():
        baris = _baris_elemen(fase, elemen, peta)
        if baris:
            bagian.append("<h3>%s</h3>%s" % (e(nama), _daftar(baris, "%s, %s" % (cp.FASE[fase], nama))))
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


def _sumber_grup(item: Optional[ItemCP]) -> str:
    """Keterangan sumber pemetaan sebuah grup: bawaan kode, atau diubah admin (revisi dan waktu)."""
    if item is None or item.sumber != SUMBER_ADMIN:
        return "bawaan kode"
    return "diubah admin, revisi %d, %s" % (item.revisi, item.diperbarui or "waktu tak tercatat")


def _baris_grup(topik_id: str, kode: str, nama: str, item: Optional[ItemCP]) -> str:
    isi = () if item is None else item.efektif
    if isi:
        sel = "<br>".join(
            "<code>%s</code> %s <span class=\"admin-meta\">(%s)</span>" % (
                e(cid), e(cp.butir(cid).teks), e(cocok))
            for cid, cocok in isi)
    else:
        sel = '<span class="admin-meta">%s</span>' % e(DI_LUAR_CP)
    sel += '<br><span class="admin-meta">Sumber: %s.</span> <a href="%s">Ubah</a>' % (
        e(_sumber_grup(item)), e(url_ubah(topik_id, kode)))
    return _blok('%s <code>%s</code>' % (e(nama), e(kode)), sel)


def _topik(entri: kat.EntriTopik, per_grup: Mapping[Tuple[str, str], ItemCP]) -> str:
    baris = "".join(
        _baris_grup(entri.topik_id, kode, nama, per_grup.get((entri.topik_id, kode)))
        for kode, nama, _p in entri.grup)
    return (
        '<details class="admin-kartu"><summary>%s <span class="admin-meta">%d grup</span></summary>%s%s</details>'
    ) % (e(_nama_topik(entri.topik_id)), len(entri.grup), _info_topik(entri.topik_id, entri.label_awam or ""),
         _daftar(baris, "Grup topik " + _nama_topik(entri.topik_id)))


def halaman(daftar: Optional[Sequence[ItemCP]] = None) -> str:
    """Isi halaman. `daftar` = ItemCP efektif per grup (dari `kurikulum_override.daftar_cp()`); None = bawaan kode."""
    daftar = _item_bawaan() if daftar is None else tuple(daftar)
    per_grup = {(i.topik_id, i.grup_kode): i for i in daftar}
    celah_sd = tuple(b for b in butir_tanpa_grup_efektif(daftar) if b.fase in FASE_SD)
    peta = pelatih_per_butir(daftar)
    return (
        tab_kurikulum(TAB_KURIKULUM)
        + _ringkasan(celah_sd, daftar) + _celah(celah_sd, daftar) + _per_fase(peta)
        + "<h2>Topik dan grup soal</h2>" + "".join(_topik(t, per_grup) for t in kat.KATALOG)
        + '<section class="admin-kartu admin-catatan"><p class="admin-meta">%s</p></section>' % e(CATATAN)
    )
