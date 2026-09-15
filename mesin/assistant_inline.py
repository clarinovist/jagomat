"""Kontrak kecil untuk Pendamping yang disisipkan pada host orang tua.

Modul ini tidak membuka DB, menyimpan draf, atau memanggil provider. Router wajib
mengotorisasi host terlebih dahulu lalu memberikan daftar ID butir yang sah.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode


_MAKS_ID = 2 ** 63 - 1
_POLA_ID = re.compile(r"[1-9][0-9]{0,18}\Z")
_POLA_CHAT = re.compile(r"chat_[0-9a-f]{32}\Z")
_KODE = frozenset(("", "benar", "B", "K", "H", "E", "N", "T"))
_PEMAHAMAN = frozenset(("", "bisa_menjelaskan", "ragu", "menghafal"))
_MAKS_TEKS = 8_000
_MAKS_TOTAL = 96_000


class GalatInline(ValueError):
    """Input navigasi/draf inline tidak memenuhi kontrak kanonik."""


@dataclass(frozen=True)
class TujuanInline:
    jenis_host: str
    host_id: int
    posisi: str
    jenis_resource: str
    resource_id: str
    nomor: Optional[int] = None
    chat_id: Optional[str] = None

    @property
    def anchor(self) -> str:
        if self.posisi == "soal":
            return f"bantuan-soal-{self.nomor}"
        return f"bantuan-{self.posisi}"

    @property
    def jalur(self) -> str:
        dasar = f"/{self.jenis_host}/{self.host_id}"
        nilai = {"bantuan": self.posisi}
        if self.nomor is not None:
            nilai["nomor"] = str(self.nomor)
        if self.chat_id:
            nilai["chat"] = self.chat_id
        return dasar + "?" + urlencode(nilai) + "#" + self.anchor


@dataclass(frozen=True)
class DrafButir:
    jawaban: str
    kode: str
    cara: str
    pemahaman: str
    dilewati: bool
    belum_pernah: bool
    catatan_tinjauan: Optional[str] = None
    provenance: Optional[str] = None
    jawaban_bantuan: Optional[str] = None
    versi_tinjauan: Optional[str] = None


@dataclass(frozen=True)
class DrafKoreksi:
    butir: Tuple[Tuple[int, DrafButir], ...]
    sertakan_pemetaan: bool

    def untuk(self, sesi_soal_id: int) -> Optional[DrafButir]:
        return next((nilai for identitas, nilai in self.butir if identitas == sesi_soal_id), None)


@dataclass(frozen=True)
class DrafLatihan:
    topik: str
    jumlah_soal: str
    mode: str
    timer_mode: bool
    durasi_menit: str
    timer_auto: str


def _id_kanonik(nilai: str) -> Optional[int]:
    if type(nilai) is not str or not _POLA_ID.fullmatch(nilai):
        return None
    angka = int(nilai)
    return angka if angka <= _MAKS_ID else None


def tujuan_anak(anak_id: int, posisi: str = "rencana", *, chat_id: str = "") -> TujuanInline:
    if type(anak_id) is not int or not 0 < anak_id <= _MAKS_ID:
        raise GalatInline("ID anak tidak sah.")
    if posisi not in ("rencana", "latihan") or (chat_id and not _POLA_CHAT.fullmatch(chat_id)):
        raise GalatInline("Tujuan bantuan tidak sah.")
    return TujuanInline("anak", anak_id, posisi, "anak", str(anak_id), chat_id=chat_id or None)


def tujuan_sesi(sesi_id: int, *, nomor: Optional[int] = None, chat_id: str = "") -> TujuanInline:
    if type(sesi_id) is not int or not 0 < sesi_id <= _MAKS_ID:
        raise GalatInline("ID sesi tidak sah.")
    if nomor is not None and (type(nomor) is not int or not 0 < nomor <= _MAKS_ID):
        raise GalatInline("Nomor soal tidak sah.")
    if chat_id and not _POLA_CHAT.fullmatch(chat_id):
        raise GalatInline("ID chat tidak sah.")
    posisi = "soal" if nomor is not None else "sesi"
    resource = f"{sesi_id}:{nomor}" if nomor is not None else str(sesi_id)
    return TujuanInline("sesi", sesi_id, posisi, posisi, resource, nomor, chat_id or None)


def target_dari_form(data: Mapping[str, Sequence[str]]) -> TujuanInline:
    """Bangun target hanya dari hidden field kanonik; bukan return URL bebas."""
    def satu(nama: str, wajib: bool = True) -> str:
        nilai = data.get(nama, ())
        if len(nilai) != 1:
            if not wajib and not nilai:
                return ""
            raise GalatInline("Identitas host tidak sah.")
        return nilai[0]

    jenis = satu("inline_host")
    host_id = _id_kanonik(satu("inline_host_id"))
    posisi = satu("inline_posisi")
    chat = satu("chat", wajib=False)
    nomor_txt = satu("inline_nomor", wajib=False)
    if host_id is None:
        raise GalatInline("Identitas host tidak sah.")
    if jenis == "anak" and not nomor_txt:
        return tujuan_anak(host_id, posisi, chat_id=chat)
    if jenis == "sesi":
        if posisi == "sesi" and not nomor_txt:
            return tujuan_sesi(host_id, chat_id=chat)
        nomor = _id_kanonik(nomor_txt)
        if posisi == "soal" and nomor is not None:
            return tujuan_sesi(host_id, nomor=nomor, chat_id=chat)
    raise GalatInline("Identitas host tidak sah.")


def parse_query_host(jenis_host: str, host_id: int, pasangan: Sequence[Tuple[str, str]]) -> Optional[TujuanInline]:
    """Parse query sekali dari ``parse_qsl``; duplikat/key asing ditolak.

    Query kosong berarti halaman host biasa dan tidak mengaktifkan subsistem
    privat. Fragment tidak pernah dikirim ke server dan dibentuk sendiri.
    """
    if not pasangan:
        return None
    if len(pasangan) != len({kunci for kunci, _ in pasangan}):
        raise GalatInline("Parameter ganda tidak sah.")
    data = dict(pasangan)
    if set(data) - {"bantuan", "nomor", "chat"}:
        raise GalatInline("Parameter tidak dikenal.")
    posisi = data.get("bantuan", "")
    chat_id = data.get("chat", "")
    if jenis_host == "anak" and set(data) <= {"bantuan", "chat"}:
        return tujuan_anak(host_id, posisi, chat_id=chat_id)
    if jenis_host == "sesi" and posisi == "sesi" and set(data) <= {"bantuan", "chat"}:
        return tujuan_sesi(host_id, chat_id=chat_id)
    if jenis_host == "sesi" and posisi == "soal" and set(data) <= {"bantuan", "nomor", "chat"}:
        nomor = _id_kanonik(data.get("nomor", ""))
        if nomor is not None:
            return tujuan_sesi(host_id, nomor=nomor, chat_id=chat_id)
    raise GalatInline("Tujuan bantuan tidak sah.")


def parse_draf_latihan(data: Mapping[str, Sequence[str]], topik_sah: Sequence[str]) -> DrafLatihan:
    """Draf form sesi baru pada profil; tidak membuat sesi atau menyimpan DB."""
    wajib = {"topik", "jumlah_soal", "mode", "hadir_timer_mode", "durasi_menit", "timer_auto"}
    diizinkan = wajib | {"timer_mode"}
    if set(data) != wajib and set(data) != diizinkan:
        raise GalatInline("Field latihan tidak lengkap atau asing.")
    if any(len(nilai) != 1 for nilai in data.values()):
        raise GalatInline("Field latihan ganda tidak diizinkan.")
    satu = {k: v[0] for k, v in data.items()}
    if (
        satu["topik"] not in set(topik_sah)
        or satu["jumlah_soal"] not in ("", "10", "15", "20", "25", "30")
        or satu["mode"] not in ("diagnostik", "drill")
        or satu["hadir_timer_mode"] != "1"
        or satu.get("timer_mode", "sesi") != "sesi"
        or not re.fullmatch(r"[0-9]{1,3}", satu["durasi_menit"])
        or satu["timer_auto"] not in ("0", "1")
    ):
        raise GalatInline("Nilai latihan tidak sah.")
    return DrafLatihan(
        satu["topik"], satu["jumlah_soal"], satu["mode"],
        "timer_mode" in satu, satu["durasi_menit"], satu["timer_auto"],
    )


def parse_draf_koreksi(
    data: Mapping[str, Sequence[str]], sesi_soal_ids: Sequence[int], *,
    mode: str = "diagnostik",
) -> DrafKoreksi:
    """Ambil draf request-local lengkap tanpa fallback ke DB.

    ``data`` mempertahankan list hasil parser form agar field ganda dapat ditolak.
    Marker ``hadir_*`` membedakan checkbox tidak dicentang dari field yang hilang.
    """
    ids = tuple(sesi_soal_ids)
    if not ids or len(ids) != len(set(ids)) or any(type(i) is not int or i < 1 for i in ids):
        raise GalatInline("Daftar butir tidak sah.")
    if mode not in ("diagnostik", "drill"):
        raise GalatInline("Mode sesi tidak sah.")
    if sum(len(k) + sum(len(v) for v in nilai) for k, nilai in data.items()) > _MAKS_TOTAL:
        raise GalatInline("Draf terlalu besar.")
    diizinkan = {"sertakan_pemetaan", "hadir_sertakan_pemetaan"}
    wajib = {"hadir_sertakan_pemetaan"}
    for sid in ids:
        for awal in ("jwb", "kode", "cara", "cek_pemahaman", "hadir_dilewati", "dilewati", "hadir_belum", "belum", "catatan_tinjauan", "provenance", "jawaban_bantuan", "versi_tinjauan"):
            diizinkan.add(f"{awal}_{sid}")
        wajib.update((f"jwb_{sid}", f"kode_{sid}", f"cek_pemahaman_{sid}",
                      f"hadir_dilewati_{sid}", f"hadir_belum_{sid}"))
        if mode != "drill":
            wajib.add(f"cara_{sid}")
    if set(data) - diizinkan or not wajib <= set(data):
        raise GalatInline("Field draf tidak lengkap atau asing.")
    if any(len(nilai) != 1 for nilai in data.values()):
        raise GalatInline("Field draf ganda tidak diizinkan.")

    def satu(nama: str) -> str:
        nilai = data[nama][0]
        if len(nilai) > _MAKS_TEKS:
            raise GalatInline("Nilai draf terlalu panjang.")
        return nilai

    hasil = []
    for sid in ids:
        if satu(f"hadir_dilewati_{sid}") != "1" or satu(f"hadir_belum_{sid}") != "1":
            raise GalatInline("Marker checkbox tidak sah.")
        kode = satu(f"kode_{sid}")
        pemahaman = satu(f"cek_pemahaman_{sid}")
        if kode not in _KODE or (mode == "drill" and kode == "N") or pemahaman not in _PEMAHAMAN:
            raise GalatInline("Pilihan draf tidak sah.")
        for nama in (f"dilewati_{sid}", f"belum_{sid}"):
            if nama in data and satu(nama) != "1":
                raise GalatInline("Nilai checkbox tidak sah.")
        tambahan = [satu(f'{awal}_{sid}') if f'{awal}_{sid}' in data else None
                    for awal in ('catatan_tinjauan', 'provenance', 'jawaban_bantuan', 'versi_tinjauan')]
        if tambahan[1] not in (None, '', 'penjelasan_asli', 'koreksi_transkripsi', 'setelah_bantuan'):
            raise GalatInline('Provenance tinjauan tidak sah.')
        if tambahan[3] is not None and not re.fullmatch(r'[0-9a-f]{64}', tambahan[3]):
            raise GalatInline('Versi tinjauan tidak sah.')
        hasil.append((sid, DrafButir(
            satu(f"jwb_{sid}"), kode, satu(f"cara_{sid}") if f"cara_{sid}" in data else "", pemahaman,
            f"dilewati_{sid}" in data, f"belum_{sid}" in data, *tambahan,
        )))
    if satu("hadir_sertakan_pemetaan") != "1":
        raise GalatInline("Marker pemetaan tidak sah.")
    if "sertakan_pemetaan" in data and satu("sertakan_pemetaan") != "1":
        raise GalatInline("Nilai pemetaan tidak sah.")
    return DrafKoreksi(tuple(hasil), "sertakan_pemetaan" in data)
