"""Rute HTTP laporan guru -> orang tua.

Dua permukaan dengan aturan berbeda:

- ``GET /laporan-ortu/<token>``: capability baca-saja, tanpa login, didaftarkan
  **sebelum** palang guru seperti ``/mulai/``. Semua keadaan tidak sah menjawab
  satu halaman 404 yang identik.
- ``/anak/<id>/laporan-ortu[/<lid>[/<aksi>]]``: guru pemilik (admin hanya
  membaca). Aksi POST memakai pembaca form guru yang sudah ada (Origin/
  Sec-Fetch-Site, batas ukuran, field tunggal) lalu transaksi domain.
"""
from __future__ import annotations

import re
import urllib.parse

import database
import parent_report
import parent_report_pages
import parent_report_store
import parent_report_teacher_pages as halaman_guru
from support_pages import halaman_pesan as _halaman

_POLA_PUBLIK = r"/laporan-ortu/([A-Za-z0-9_-]{43})\Z"
_POLA_ANAK = (
    r"/anak/([0-9]{1,19})/laporan-ortu"
    r"(?:/([0-9]{1,19})(?:/(tautan/cabut|tautan|catatan|terbitkan|hapus))?)?\Z"
)
_BATAS_ID = 2**63 - 1


def _cocok(pola: str, jalur: str):
    return re.fullmatch(pola, jalur)


def _tidak_ada(penangan, kode: int = 404) -> None:
    penangan._kirim_tautan(
        _halaman("404", "<h1>Halaman tidak ada</h1>"), kode
    )


def _kirim_halaman(penangan, isi: bytes, kode: int = 200) -> None:
    penangan._kirim_tautan(isi, kode)


def tangani_publik_get(penangan, jalur: str) -> bool:
    """Halaman baca-saja orang tua dari token; tanpa login dan tanpa tulis DB."""
    if not (jalur == "/laporan-ortu" or jalur.startswith("/laporan-ortu/")):
        return False
    tidak_ada = parent_report_pages.halaman_tidak_ada()
    cocok = _cocok(_POLA_PUBLIK, jalur)
    if cocok is None:
        penangan._kirim_tautan(tidak_ada, 404, ketat=True)
        return True
    with database.buka() as kon:
        akses = parent_report_store.ambil_tautan(kon, cocok.group(1))
        if akses is None:
            penangan._kirim_tautan(tidak_ada, 404, ketat=True)
            return True
        isi = parent_report_pages.halaman_orang_tua(
            akses["nama"],
            akses["periode_mulai"],
            akses["periode_akhir"],
            parent_report.muat_isi(akses["isi"]),
            akses["catatan"],
            akses["guru"],
            akses["diterbitkan"],
            parent_report_store.tanggal_wib(akses["kedaluarsa"]),
        )
    penangan._kirim_tautan(isi, ketat=True)
    return True


def _pesan_query(jalur_penuh: str) -> str:
    """Hanya kunci pesan yang dikenal yang diteruskan ke halaman."""
    try:
        q = urllib.parse.parse_qs(
            urllib.parse.urlsplit(jalur_penuh or "").query,
            keep_blank_values=False, max_num_fields=20,
        )
    except ValueError:
        return ""
    nilai = (q.get("pesan") or [""])[0]
    return nilai if nilai in halaman_guru.PESAN else ""


def _identitas_guru(penangan, kon, anak_id: int):
    """(identitas, siswa) atau (None, None) untuk semua tolakan 404 identik."""
    ident = penangan._identitas()
    if not ident or not penangan._bisa_lihat_siswa(kon, anak_id):
        return None, None
    siswa = kon.execute(
        "SELECT id, nama, pemilik FROM siswa WHERE id = ?", (anak_id,)
    ).fetchone()
    return (ident, siswa) if siswa is not None else (None, None)


def _berlaku(tautan, laporan_id: int, kini: int):
    if (tautan is None or tautan["dicabut"] is not None
            or int(tautan["kedaluarsa"]) <= int(kini)
            or int(tautan["laporan_id"]) != int(laporan_id)):
        return None
    return parent_report_store.tanggal_wib(tautan["kedaluarsa"])


def _halaman_detail(
    kon,
    siswa,
    laporan,
    ident,
    *,
    kini: int,
    pesan: str = "",
    galat: str = "",
    token_baru: str | None = None,
):
    tautan = parent_report_store.tautan_aktif(kon, int(siswa["id"]), sekarang=kini)
    kejadian_baru = 0
    if laporan["diterbitkan"]:
        _ada, kejadian_baru = parent_report.perubahan_bukti(
            kon, int(siswa["id"]), int(laporan["kejadian_terakhir"])
        )
    return halaman_guru.halaman_detail(
        siswa,
        laporan,
        tautan,
        pengguna=ident[0],
        peran=ident[1],
        kini=kini,
        pesan=pesan,
        galat=galat,
        token_baru=token_baru,
        kejadian_baru=kejadian_baru,
        berlaku_sampai=_berlaku(tautan, int(laporan["id"]), kini),
    )


def _halaman_daftar(
    kon, siswa, ident, *, kini: int, pesan: str = "", galat: str = ""
):
    return halaman_guru.halaman_daftar(
        siswa,
        parent_report_store.daftar(kon, int(siswa["id"])),
        parent_report_store.tautan_aktif(kon, int(siswa["id"]), sekarang=kini),
        pengguna=ident[0],
        peran=ident[1],
        kini=kini,
        pesan=pesan,
        galat=galat,
    )


def tangani_guru_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """Daftar/detail laporan milik anak; dipanggil setelah palang guru utama."""
    cocok = _cocok(_POLA_ANAK, jalur)
    if cocok is None:
        return False
    anak_id = int(cocok.group(1))
    laporan_id = int(cocok.group(2)) if cocok.group(2) else None
    if anak_id > _BATAS_ID or (laporan_id is not None and laporan_id > _BATAS_ID):
        _tidak_ada(penangan)
        return True
    pesan = _pesan_query(jalur_penuh)
    kini = parent_report_store.sekarang_detik()
    with database.buka() as kon:
        ident, siswa = _identitas_guru(penangan, kon, anak_id)
        if ident is None:
            _tidak_ada(penangan)
            return True
        if laporan_id is None:
            _kirim_halaman(penangan, _halaman_daftar(
                kon, siswa, ident, kini=kini, pesan=pesan,
            ))
            return True
        laporan = parent_report_store.ambil(kon, laporan_id, anak_id)
        if laporan is None:
            _tidak_ada(penangan)
            return True
        _kirim_halaman(penangan, _halaman_detail(
            kon, siswa, laporan, ident, kini=kini, pesan=pesan,
        ))
    return True


def _galat_form(galat: Exception) -> tuple[str, int]:
    return str(galat), int(getattr(galat, "status", 400) or 400)


def tangani_guru_post(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """Buat draf, simpan catatan, terbitkan, ganti/cabut tautan, hapus draf."""
    cocok = _cocok(_POLA_ANAK, jalur)
    if cocok is None:
        return False
    from learning_cycle_http import GalatForm, _baca_form

    anak_id = int(cocok.group(1))
    laporan_id = int(cocok.group(2)) if cocok.group(2) else None
    aksi = cocok.group(3)
    if anak_id > _BATAS_ID or (laporan_id is not None and laporan_id > _BATAS_ID):
        _tidak_ada(penangan)
        return True
    kini = parent_report_store.sekarang_detik()
    with database.buka() as kon:
        ident = penangan._identitas()
        # Admin membaca, tidak menulis: penerbitan adalah pernyataan guru.
        if (not ident or ident[1] != "guru"
                or not penangan._bisa_lihat_siswa(kon, anak_id)):
            _tidak_ada(penangan)
            return True
        siswa = kon.execute(
            "SELECT id, nama, pemilik FROM siswa WHERE id = ?", (anak_id,)
        ).fetchone()
        if siswa is None:
            _tidak_ada(penangan)
            return True

        def tolak_pesan(galat: str, kode: int = 400):
            if laporan_id is None:
                isi = _halaman_daftar(
                    kon, siswa, ident, kini=kini, galat=galat,
                )
            else:
                laporan = parent_report_store.ambil(
                    kon, laporan_id, anak_id
                )
                if laporan is None:
                    _tidak_ada(penangan)
                    return
                isi = _halaman_detail(
                    kon, siswa, laporan, ident, kini=kini, galat=galat,
                )
            _kirim_halaman(penangan, isi, kode)

        try:
            data = _baca_form(penangan)
        except GalatForm as galat:
            pesan, kode = _galat_form(galat)
            tolak_pesan(pesan, kode)
            return True

        if laporan_id is None:
            try:
                mulai, akhir = parent_report.periode_dari_form(data)
                isi = parent_report.serialisasi(
                    parent_report.proyeksi(kon, anak_id, mulai, akhir)
                )
                kon.execute("BEGIN IMMEDIATE")
                baru = parent_report_store.buat_draf(
                    kon, anak_id, mulai.isoformat(), akhir.isoformat(),
                    isi, guru=parent_report.nama_guru(ident[0]),
                )
                kon.commit()
            except ValueError as galat:
                kon.rollback()
                tolak_pesan(str(galat), 400)
                return True
            _alihkan(penangan, f"/anak/{anak_id}/laporan-ortu/{baru}?pesan=draf-dibuat")
            return True

        if aksi not in ("catatan", "terbitkan", "tautan", "tautan/cabut", "hapus"):
            _tidak_ada(penangan)
            return True

        if aksi == "catatan":
            if set(data) - {"catatan"}:
                tolak_pesan("Isian catatan tidak dikenal.", 400)
                return True
            catatan = data.get("catatan", "")
            kon.execute("BEGIN IMMEDIATE")
            try:
                tersimpan = parent_report_store.simpan_catatan(
                    kon, laporan_id, anak_id, catatan
                )
            except ValueError as galat:
                kon.rollback()
                tolak_pesan(str(galat), 400)
                return True
            if not tersimpan:
                laporan = parent_report_store.ambil(kon, laporan_id, anak_id)
                kon.rollback()
                if laporan is None:
                    _tidak_ada(penangan)
                    return True
                tolak_pesan(
                    "Laporan terbit tidak dapat diubah. Buat laporan baru untuk "
                    "koreksi.", 409,
                )
                return True
            kon.commit()
            _alihkan(
                penangan,
                f"/anak/{anak_id}/laporan-ortu/{laporan_id}?pesan=catatan-disimpan",
            )
            return True

        if aksi == "terbitkan":
            if data:
                tolak_pesan("Isian penerbitan tidak dikenal.", 400)
                return True
            kon.execute("BEGIN IMMEDIATE")
            laporan = parent_report_store.ambil(kon, laporan_id, anak_id)
            if laporan is None:
                kon.rollback()
                _tidak_ada(penangan)
                return True
            if laporan["diterbitkan"]:
                kon.rollback()
                tolak_pesan(
                    "Laporan ini sudah terbit dan tidak dapat diubah. "
                    "Buat laporan baru untuk koreksi.", 409,
                )
                return True
            tampil = parent_report.muat_isi(laporan["isi"])
            if not tampil["topik"]:
                kon.rollback()
                tolak_pesan(
                    "Belum ada latihan yang selesai dan dikonfirmasi pada periode "
                    "ini. Pilih periode lain atau konfirmasi hasil latihan guru "
                    "terlebih dahulu.", 409,
                )
                return True
            token = parent_report_store.terbitkan(
                kon, laporan_id, anak_id,
                parent_report.kejadian_terakhir(kon, anak_id),
                parent_report.nama_guru(ident[0]), sekarang=kini,
            )
            if token is None:
                kon.rollback()
                tolak_pesan("Laporan tidak dapat diterbitkan.", 409)
                return True
            kon.commit()
            laporan = parent_report_store.ambil(kon, laporan_id, anak_id)
            _kirim_halaman(penangan, _halaman_detail(
                kon, siswa, laporan, ident, kini=kini, token_baru=token,
            ))
            return True

        if aksi in ("tautan", "tautan/cabut"):
            if data:
                tolak_pesan("Isian tautan tidak dikenal.", 400)
                return True
            kon.execute("BEGIN IMMEDIATE")
            laporan = parent_report_store.ambil(kon, laporan_id, anak_id)
            if laporan is None:
                kon.rollback()
                _tidak_ada(penangan)
                return True
            if not laporan["diterbitkan"]:
                kon.rollback()
                tolak_pesan(
                    "Tautan hanya tersedia untuk laporan yang sudah terbit.",
                    409,
                )
                return True
            if aksi == "tautan/cabut":
                parent_report_store.cabut_tautan(kon, anak_id, sekarang=kini)
                kon.commit()
                _alihkan(
                    penangan,
                    f"/anak/{anak_id}/laporan-ortu/{laporan_id}"
                    "?pesan=tautan-dicabut",
                )
                return True
            token = parent_report_store.ganti_tautan(
                kon, laporan_id, anak_id, sekarang=kini
            )
            if token is None:
                kon.rollback()
                tolak_pesan(
                    "Tautan hanya dapat dibuat untuk laporan yang sudah terbit.",
                    409,
                )
                return True
            kon.commit()
            _kirim_halaman(penangan, _halaman_detail(
                kon, siswa, laporan, ident, kini=kini,
                pesan="tautan-baru", token_baru=token,
            ))
            return True

        # aksi == "hapus": hanya draf.
        if data:
            tolak_pesan("Isian penghapusan tidak dikenal.", 400)
            return True
        kon.execute("BEGIN IMMEDIATE")
        terhapus = parent_report_store.hapus_draf(kon, laporan_id, anak_id)
        if not terhapus:
            kon.rollback()
            tolak_pesan(
                "Laporan terbit tidak dapat dihapus; cabut tautannya bila perlu.",
                409,
            )
            return True
        kon.commit()
    _alihkan(penangan, f"/anak/{anak_id}/laporan-ortu?pesan=draf-dihapus")
    return True


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
