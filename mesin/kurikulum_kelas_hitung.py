"""Hitungan per kelas untuk halaman admin "Kurikulum Merdeka": ketersediaan soal, jenis, variasi, pemakaian.

Data bab ada di `kurikulum_kelas`; modul ini menghubungkannya dengan registri topik. Ketersediaan sebuah
grup di kelas K dihitung dari `Topik.komposisi["P<K>"]` (inventaris pembaca), lalu dibatasi palang rilis
`basic_numbers_versions.template_dibuka` untuk variasi dan pembuatan soal. Variasi (banyak soal berbeda)
dibangkitkan dari generator dan deterministik, jadi hasil murni per (topik, template, level) di-cache per proses;
palang rilis dibaca di luar cache supaya perubahan env langsung terlihat. Pemakaian dibaca dari tabel `soal`
sebagai agregat COUNT saja (tanpa `parameter`, `kunci`, atau data anak).

Cetakan berpola AKTIF (`cetakan_store.aktif_untuk_bab`, C2) ikut dihitung sebagai jenis soal bab: variasinya dianggap
"banyak" tanpa dijalankan (tidak ada uji kelayakan/sampel saat render tabel), dan bab tanpa soal kode tetapi
punya >= 1 cetakan aktif berstatus "sebagian" (Perlu disempurnakan). Draf dan nonaktif tidak pernah dibaca di sini.
Kolom "Dipakai" tidak berubah: cetakan belum masuk sesi anak (C4).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Dict, Mapping, Optional, Tuple

import basic_numbers_versions
import cetakan_store
import database
import generator
import generator_domain
import kurikulum_katalog as kat
import kurikulum_kelas as kk
import topics

JUMLAH_SAMPEL = 40
STATUS_ADA, STATUS_SEBAGIAN, STATUS_BELUM = "ada", "sebagian", "belum"
LABEL_STATUS = {
    STATUS_ADA: "Sudah ada soal",
    STATUS_SEBAGIAN: "Perlu disempurnakan",
    STATUS_BELUM: "Belum ada soal",
}
JENIS_TEPAT, JENIS_PERKIRAAN, JENIS_BANYAK, JENIS_NOL = "tepat", "perkiraan", "banyak", "nol"
CATATAN_TUTUP = "belum dinyalakan"
CATATAN_GALAT = "galat"

# (topik_id, template_id)
RefTemplate = Tuple[str, str]


@dataclass(frozen=True)
class PelatihKelas:
    topik_id: str
    nama_topik: str
    kode: str
    nama_grup: str
    kecocokan: str
    template: Tuple[str, ...]  # template pola grup yang ada di komposisi level kelas ini
    kelas_lain: Tuple[int, ...]  # kelas yang menyediakan grup ini (diisi bila tidak tersedia di kelas ini)

    @property
    def tersedia(self) -> bool:
        return bool(self.template)


@dataclass(frozen=True)
class VariasiBab:
    total: int
    ada_banyak: bool
    ada_perkiraan: bool
    tertutup: Tuple[str, ...]  # template_id yang belum dinyalakan
    galat: Tuple[str, ...]

    @property
    def jenis(self) -> str:
        if self.ada_banyak:
            return JENIS_BANYAK
        return JENIS_PERKIRAAN if self.ada_perkiraan else JENIS_TEPAT


@dataclass(frozen=True)
class RingkasanBab:
    nomor: int
    judul: str
    sub_materi: Tuple[str, ...]
    pelatih: Tuple[PelatihKelas, ...]
    status: str
    template: Tuple[RefTemplate, ...]  # unik, urut pelatih
    variasi: VariasiBab
    terpakai: Optional[int]  # None = DB tak terbaca
    cetakan: Tuple[cetakan_store.ItemCetakan, ...] = ()  # cetakan berpola AKTIF bab ini

    @property
    def jenis(self) -> int:
        """Jumlah jenis soal: template kode unik + cetakan aktif."""
        return len(self.template) + len(self.cetakan)


def level_kelas(kelas: int) -> str:
    return "P%d" % kelas


@lru_cache(maxsize=1)
def _info_grup() -> Dict[Tuple[str, str], Tuple[str, Tuple[str, ...]]]:
    return {(e.topik_id, kode): (nama, tuple(pola)) for e in kat.KATALOG for kode, nama, pola in e.grup}


def _nama_topik(topik_id: str) -> str:
    try:
        return topics.ambil(topik_id).nama
    except KeyError:
        return topik_id


def _template_di_level(topik_id: str, pola: Tuple[str, ...], level: str) -> Tuple[str, ...]:
    try:
        komposisi = topics.ambil(topik_id).komposisi.get(level, ())
    except KeyError:
        return ()
    return tuple(t for t in pola if t in komposisi)


def _kelas_penyedia(topik_id: str, pola: Tuple[str, ...]) -> Tuple[int, ...]:
    try:
        komposisi = topics.ambil(topik_id).komposisi
    except KeyError:
        return ()
    return tuple(sorted(int(lv[1:]) for lv, urut in komposisi.items() if set(pola) & set(urut)))


def pelatih_kelas(topik_id: str, kode: str, kecocokan: str, kelas: int) -> PelatihKelas:
    nama, pola = _info_grup()[(topik_id, kode)]
    template = _template_di_level(topik_id, pola, level_kelas(kelas))
    return PelatihKelas(topik_id, _nama_topik(topik_id), kode, nama, kecocokan, template,
                        () if template else _kelas_penyedia(topik_id, pola))


def status_bab(pelatih: Tuple[PelatihKelas, ...]) -> str:
    """'ada' bila ada pelatih tersedia berkecocokan 'ada'; 'sebagian' bila hanya yang lain; 'belum' bila tak ada."""
    tersedia = [p.kecocokan for p in pelatih if p.tersedia]
    if "ada" in tersedia:
        return STATUS_ADA
    return STATUS_SEBAGIAN if tersedia else STATUS_BELUM


def template_unik(pelatih: Tuple[PelatihKelas, ...]) -> Tuple[RefTemplate, ...]:
    """(topik_id, template_id) tersedia di level kelas, tanpa ganda, urut pelatih."""
    return tuple(dict.fromkeys((p.topik_id, t) for p in pelatih for t in p.template))


def template_dibuka(template_id: str) -> bool:
    """Palang rilis (sakelar env); nilai env tak sah dianggap tertutup."""
    try:
        return basic_numbers_versions.template_dibuka(template_id)
    except ValueError:
        return False


@lru_cache(maxsize=None)
def _variasi_murni(topik_id: str, template_id: str, level: str) -> Tuple[int, str, str]:
    """(jumlah, jenis, catatan) untuk satu template di satu level; tanpa palang rilis (dicek pemanggil)."""
    paket = topics.ambil(topik_id)
    try:
        if paket.domain_parameter is not None:
            try:
                return _variasi_domain(paket, template_id, level)
            except KeyError:
                pass  # enumerator topik ini tidak mencakup template ini: jatuh ke sampel
        return _variasi_sampel(topik_id, template_id, level)
    except Exception:  # noqa: BLE001 - satu template rusak tidak boleh menjatuhkan halaman; dicatat "galat"
        return 0, JENIS_NOL, CATATAN_GALAT


def _variasi_domain(paket, template_id: str, level: str) -> Tuple[int, str, str]:
    domain = generator_domain.domain_sidik(paket.templates[template_id], paket.domain_parameter, template_id, level)
    return len(domain.tanda), JENIS_TEPAT, ""


def _variasi_sampel(topik_id: str, template_id: str, level: str) -> Tuple[int, str, str]:
    tanda = {generator.buat_soal(template_id, seed, level, topik_id).tanda_tangan
             for seed in range(JUMLAH_SAMPEL)}
    if len(tanda) == JUMLAH_SAMPEL:
        return JUMLAH_SAMPEL, JENIS_BANYAK, ""
    return len(tanda), JENIS_PERKIRAAN, ""


def variasi_bab(template: Tuple[RefTemplate, ...], level: str) -> VariasiBab:
    total, banyak, kira = 0, False, False
    tutup, galat = [], []
    for topik_id, tid in template:
        if not template_dibuka(tid):
            tutup.append(tid)
            continue
        jumlah, jenis, catatan = _variasi_murni(topik_id, tid, level)
        if catatan == CATATAN_GALAT:
            galat.append(tid)
        total += jumlah
        banyak = banyak or jenis == JENIS_BANYAK
        kira = kira or jenis == JENIS_PERKIRAAN
    return VariasiBab(total, banyak, kira, tuple(tutup), tuple(galat))


def pemakaian_per_template_level() -> Optional[Mapping[Tuple[str, str], int]]:
    """{(template_id, level): COUNT baris `soal`}; None bila DB tidak terbaca. Hanya agregat, hanya baca."""
    try:
        with database.buka() as kon:
            kon.execute("PRAGMA query_only = ON")
            baris = kon.execute(
                "SELECT template_id, level, COUNT(*) FROM soal GROUP BY template_id, level").fetchall()
    except sqlite3.Error:
        return None
    return {(r[0], r[1]): r[2] for r in baris}


def _terpakai(template: Tuple[RefTemplate, ...], level: str,
              pemakaian: Optional[Mapping[Tuple[str, str], int]]) -> Optional[int]:
    if pemakaian is None:
        return None
    return sum(pemakaian.get((tid, level), 0) for _topik, tid in template)


def _status_dengan_cetakan(status: str, cetakan: Tuple[cetakan_store.ItemCetakan, ...]) -> str:
    """Bab tanpa soal kode (belum) tetapi punya cetakan aktif = sebagian; selain itu status kode tetap."""
    return STATUS_SEBAGIAN if status == STATUS_BELUM and cetakan else status


def _variasi_dengan_cetakan(variasi: VariasiBab, cetakan: Tuple[cetakan_store.ItemCetakan, ...]) -> VariasiBab:
    """Cetakan dianggap "banyak" (tanpa dijalankan); jumlah total soal kode tidak berubah."""
    return replace(variasi, ada_banyak=True) if cetakan else variasi


def ringkasan_bab(bab: kk.Bab, kelas: int, pemakaian: Optional[Mapping[Tuple[str, str], int]]) -> RingkasanBab:
    pelatih = tuple(pelatih_kelas(t, g, c, kelas) for t, g, c in bab.pelatih)
    template = template_unik(pelatih)
    level = level_kelas(kelas)
    cetakan = cetakan_store.aktif_untuk_bab(kelas, bab.nomor)
    return RingkasanBab(bab.nomor, bab.judul, bab.sub_materi, pelatih,
                        _status_dengan_cetakan(status_bab(pelatih), cetakan), template,
                        _variasi_dengan_cetakan(variasi_bab(template, level), cetakan),
                        _terpakai(template, level, pemakaian), cetakan)


def ringkasan_kelas(kelas: kk.Kelas, pemakaian: Optional[Mapping[Tuple[str, str], int]]) -> Tuple[RingkasanBab, ...]:
    return tuple(ringkasan_bab(b, kelas.kelas, pemakaian) for b in kelas.bab)


def cari_bab(kelas: int, nomor: int) -> Optional[Tuple[kk.Kelas, kk.Bab]]:
    for k in kk.KELAS:
        if k.kelas == kelas:
            for b in k.bab:
                if b.nomor == nomor:
                    return k, b
    return None


def grup_pengayaan() -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    """(nama topik, (nama grup, ...)) untuk grup yang tidak ditunjuk bab mana pun, urut KATALOG."""
    terpakai = kk.grup_terpakai()
    hasil = []
    for e in kat.KATALOG:
        nama = tuple(n for kode, n, _p in e.grup if (e.topik_id, kode) not in terpakai)
        if nama:
            hasil.append((_nama_topik(e.topik_id), nama))
    return tuple(hasil)
