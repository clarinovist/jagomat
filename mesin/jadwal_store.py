"""Kelompok, penempatan, dan jadwal Paket Belajar (tanpa HTTP, jaringan, env, atau berkas).

Mini Class dijadwalkan sebagai kelompok (satu lokasi/guru, 8 pertemuan 2x seminggu selama 4 pekan, kuota 5); Private per anak
(guru per anak, lokasi "Online"). Semua tulis dalam satu `BEGIN IMMEDIATE` (`pesanan_dasar.tulis`) di
admin-control.db. Nominal tidak disentuh di sini; jadwal hanya membaca order/akses kelas.

Kuota dan kecocokan paket dijaga dua lapis: store (pesan jelas) dan trigger skema (fail-closed). Penempatan
hanya untuk order yang statusnya `aktif`; satu penempatan per order dan per anak. Perpanjangan bulanan: penempatan
LAMA anak yang sama dipensiunkan (baris penempatan dihapus, sesi Private tetap sebagai riwayat) bila akses order
lamanya sudah berakhir pada waktu penempatan, atau menyambung ke akses order baru dan semua pertemuan lamanya sudah
lewat/dibatalkan; selain itu lepas dulu.
Pertemuan tidak boleh jatuh setelah akses paket berakhir (`_batas_akses_*`): delapan pertemuan harus selesai
dalam masa akses satu bulan. Pendaftaran kelompok ditutup begitu dua pertemuan aktif sudah mulai.
Bentrok jadwal guru (sesi aktif guru yang sama beririsan waktu) hanya DITANDAI untuk peringatan; tidak pernah menolak.
Lepas penempatan wajib membawa `versi` (= `dibuat` penempatan saat halaman dibuka) supaya form lama tidak bisa diputar ulang.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import jadwal_dasar as jd
import kelas_dasar as dasar
import kelas_status as ks
import kelas_store
import paket_belajar_katalog as katalog
import pesanan_dasar as d
import schema_jadwal
import schema_kelas

PESAN_LEWAT_AKSES = "pertemuan terakhir jatuh setelah masa akses paket berakhir; mulai lebih awal"
PESAN_GESER_LEWAT_AKSES = "pertemuan tidak boleh digeser melewati masa akses paket berakhir"
# Pendaftaran kelompok Mini ditutup begitu sekian pertemuan aktif sudah mulai ("boleh masuk sampai pertemuan ke-2").
# Sengaja di store (bukan jadwal_dasar): store byte-identik dipakai sebagai pin recovery dan harus berdiri sendiri.
TUTUP_SETELAH_PERTEMUAN_MULAI = 2
PESAN_DITUTUP = "pendaftaran kelompok sudah ditutup (dua pertemuan pertama sudah berlangsung)"
PESAN_VERSI_BASI = "penempatan sudah berubah sejak halaman dibuka; muat ulang"


@contextmanager
def buka(path, *, tulis_data=False):
    """Koneksi admin dengan kelas DAN jadwal yang sah (salah satunya belum dipasang -> StoreBelumSiap)."""
    import admin_store_core
    with kelas_store.buka(path, tulis_data=tulis_data) as kon:
        if not schema_jadwal.validasi(kon):
            raise admin_store_core.StoreBelumSiap("jadwal belum dipasang")
        yield kon


def _group(kon, kelompok_id):
    baris = kon.execute(
        "SELECT id,paket,nama,lokasi,guru_id,kuota,dibuat,diubah FROM jadwal_kelompok WHERE id=?",
        (kelompok_id,)).fetchone()
    return None if baris is None else dict(baris)


def _isi_kelompok(kon, kelompok_id) -> int:
    return kon.execute("SELECT COUNT(*) FROM jadwal_penempatan WHERE kelompok_id=?",
                       (kelompok_id,)).fetchone()[0]


def _batas_akses_order(kon, order_id) -> Optional[str]:
    """Akhir akses terjauh order (UTC baku); None bila belum ada akses."""
    return kon.execute("SELECT MAX(berakhir) FROM kelas_akses WHERE order_id=?", (order_id,)).fetchone()[0]


def _batas_akses_kelompok(kon, kelompok_id) -> Optional[str]:
    """Batas terkecil di antara anggota yang punya akses; None bila tidak ada anggota berakses (tanpa batas)."""
    return kon.execute(
        """SELECT MIN(akhir) FROM (SELECT MAX(a.berakhir) AS akhir FROM jadwal_penempatan p
                                    JOIN kelas_akses a ON a.order_id=p.order_id
                                   WHERE p.kelompok_id=? GROUP BY p.order_id)""",
        (kelompok_id,)).fetchone()[0]


def _pertemuan_aktif_terakhir(kon, kelompok_id) -> Optional[str]:
    return kon.execute("SELECT MAX(mulai) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0",
                       (kelompok_id,)).fetchone()[0]


def _jumlah_sudah_mulai(kon, kelompok_id, kini) -> int:
    """Pertemuan aktif (tidak dibatalkan) kelompok yang sudah mulai: `mulai < kini` (tepat saat mulai belum dihitung)."""
    return kon.execute("SELECT COUNT(*) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0 AND mulai<?",
                       (kelompok_id, kini)).fetchone()[0]


def _id_sesi_bentrok(kon) -> frozenset:
    """Id sesi aktif yang beririsan waktu dengan sesi aktif LAIN milik guru yang sama (hanya baca, untuk peringatan).

    Guru sesi kelompok = guru kelompok; guru sesi Private = guru penempatannya. Penempatan yang sudah dipensiunkan
    tidak punya guru (NULL) sehingga sesi riwayatnya tidak dihitung. Bersentuhan tepat (akhir A = mulai B) bukan bentrok.
    """
    baris = kon.execute(
        """SELECT s.id AS id, s.mulai AS mulai, s.menit AS menit, COALESCE(k.guru_id, p.guru_id) AS guru
             FROM jadwal_pertemuan s
             LEFT JOIN jadwal_kelompok k ON k.id=s.kelompok_id
             LEFT JOIN jadwal_penempatan p ON p.order_id=s.order_id
            WHERE s.dibatalkan=0 AND COALESCE(k.guru_id, p.guru_id) IS NOT NULL
            ORDER BY guru, s.mulai""").fetchall()
    # Sapuan terurut per guru (O(n log n), bukan self-join kuadratik): `aktif` = sesi guru ini yang belum selesai
    # pada waktu mulai sesi berjalan; sesi yang akhirnya tepat = mulai sesi berjalan sudah tidak aktif (bersentuhan).
    bentrok, aktif, guru_kini = set(), [], None
    for b in baris:
        if b["guru"] != guru_kini:
            guru_kini, aktif = b["guru"], []
        mulai = datetime.strptime(b["mulai"], jd.FORMAT_BAKU)
        aktif = [(akhir, sid) for akhir, sid in aktif if akhir > mulai]
        if aktif:
            bentrok.add(b["id"])
            bentrok.update(sid for _akhir, sid in aktif)
        aktif.append((mulai + timedelta(minutes=b["menit"]), b["id"]))
    return frozenset(bentrok)


def _tandai_bentrok(sesi: List[dict], bentrok: frozenset) -> List[dict]:
    return [{**s, "bentrok": s["id"] in bentrok} for s in sesi]


def _pertemuan_mendatang(kon, kelompok_id, kini) -> Optional[str]:
    return kon.execute("SELECT MIN(mulai) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0 AND mulai>=?",
                       (kelompok_id, kini)).fetchone()[0]


def _pastikan_dalam_akses(waktu_akhir: Optional[str], batas: Optional[str], pesan: str = PESAN_LEWAT_AKSES) -> None:
    if waktu_akhir is not None and batas is not None and waktu_akhir > batas:
        raise jd.JadwalTidakSah(pesan)


def _sesi_lama_tersisa(kon, order_lama, kini: str) -> bool:
    """Masih ada pertemuan aktif (tidak dibatalkan) yang belum mulai pada penempatan lama (sesi order atau kelompok)."""
    return kon.execute(
        "SELECT 1 FROM jadwal_pertemuan s WHERE s.dibatalkan=0 AND s.mulai>=? AND (s.order_id=? OR "
        "s.kelompok_id=(SELECT kelompok_id FROM jadwal_penempatan WHERE order_id=?)) LIMIT 1",
        (kini, order_lama, order_lama)).fetchone() is not None


def _akses_lama_berakhir(kon, order_lama, mulai_baru: Optional[str], kini: str) -> bool:
    """True bila akses order lama sudah berakhir pada `kini`, atau menyambung ke `mulai_baru` TANPA pertemuan tersisa.

    Perpanjangan dini (akses lama belum habis) hanya boleh bila semua pertemuan lama sudah lewat atau dibatalkan;
    kalau tidak, penempatan lama tetap (konflik) supaya anak tidak hilang dari jadwal yang masih berjalan.
    """
    akhir = _batas_akses_order(kon, order_lama)
    if akhir is None:
        return False
    if akhir <= kini:
        return True
    return mulai_baru is not None and akhir <= mulai_baru and not _sesi_lama_tersisa(kon, order_lama, kini)


def _pensiunkan_penempatan_lama(kon, order_id, kini: str) -> None:
    """Hapus penempatan LAIN anak yang sama bila semuanya sudah berakhir aksesnya; kalau tidak, tidak menghapus apa pun.

    Hanya baris `jadwal_penempatan` yang dihapus: sesi Private lama tetap sebagai riwayat dan sesi kelompok milik
    kelompok. Penempatan lama yang masih berjalan dibiarkan, sehingga trigger `jadwal_penempatan_anak` menolak
    penempatan baru (JadwalKonflik). Dipanggil di dalam transaksi `tempatkan`: gagal sesudahnya = rollback bersama.
    """
    lama = [b["order_id"] for b in kon.execute(
        "SELECT p.order_id FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
        "WHERE p.order_id<>? AND o.siswa_id=(SELECT siswa_id FROM kelas_order WHERE id=?)",
        (order_id, order_id))]
    if not lama:
        return
    mulai_baru = kon.execute("SELECT MIN(mulai) FROM kelas_akses WHERE order_id=?", (order_id,)).fetchone()[0]
    if not all(_akses_lama_berakhir(kon, ada, mulai_baru, kini) for ada in lama):
        return
    for ada in lama:
        kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (ada,))


def _tulis_sesi(kon, *, kelompok_id=None, order_id=None, mulai, menit, aktor, kini):
    for ke, waktu in enumerate(jd.delapan_pertemuan(mulai), start=1):
        kon.execute(
            "INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,diubah_oleh) "
            "VALUES(?,?,?,?,?,0,?,?)",
            (kelompok_id, order_id, ke, waktu, menit, kini, aktor))


# --- kelompok -------------------------------------------------------------------------------

def _tolak_kelompok_kembar(kon, nama: str, mulai: str) -> None:
    """Nama sama (casefold) dan pertemuan pertama sama = klik ganda; ditolak tanpa menulis."""
    serupa = kon.execute(
        "SELECT k.nama FROM jadwal_kelompok k JOIN jadwal_pertemuan s ON s.kelompok_id=k.id AND s.ke=1 "
        "WHERE s.mulai=?", (mulai,)).fetchall()
    if any(baris["nama"].casefold() == nama.casefold() for baris in serupa):
        raise jd.JadwalKonflik("kelompok dengan nama dan waktu mulai yang sama sudah ada")


def buat_kelompok(kon, admin_id, *, nama, lokasi, guru_id, kuota, tanggal, jam, sekarang) -> str:
    """Buat kelompok Mini + delapan pertemuan (2x seminggu); kelompok kembar ditolak; mengembalikan id (atomik)."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    nama = jd.periksa_teks(nama, "nama kelompok", 80)
    lokasi = jd.periksa_teks(lokasi, "lokasi", 200)
    guru = jd.periksa_guru_id(guru_id)
    kuota = jd.periksa_kuota(kuota)
    mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
    kid, kini = jd.id_kelompok_baru(), dasar.ke_baku(sekarang)
    menit = katalog.ambil(schema_jadwal.KODE_PAKET_MINI).menit
    with d.tulis(kon):
        _tolak_kelompok_kembar(kon, nama, mulai)
        kon.execute(
            "INSERT INTO jadwal_kelompok(id,paket,nama,lokasi,guru_id,kuota,dibuat,diubah,"
            "dibuat_oleh,diubah_oleh) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (kid, schema_jadwal.KODE_PAKET_MINI, nama, lokasi, guru, kuota, kini, kini, aktor, aktor))
        _tulis_sesi(kon, kelompok_id=kid, mulai=mulai, menit=menit, aktor=aktor, kini=kini)
    return kid


def ubah_kelompok(kon, admin_id, kelompok_id, *, nama, lokasi, guru_id, kuota, sekarang) -> None:
    """Ubah nama/lokasi/guru/kuota kelompok; kuota tidak boleh di bawah jumlah anggota."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    kid = jd.periksa_kelompok_id(kelompok_id)
    nama = jd.periksa_teks(nama, "nama kelompok", 80)
    lokasi = jd.periksa_teks(lokasi, "lokasi", 200)
    guru = jd.periksa_guru_id(guru_id)
    kuota = jd.periksa_kuota(kuota)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        if _group(kon, kid) is None:
            raise jd.JadwalTidakDitemukan()
        try:
            kon.execute(
                "UPDATE jadwal_kelompok SET nama=?,lokasi=?,guru_id=?,kuota=?,diubah=?,diubah_oleh=? "
                "WHERE id=?", (nama, lokasi, guru, kuota, kini, aktor, kid))
        except sqlite3.IntegrityError:
            raise jd.JadwalKonflik("kuota lebih kecil dari jumlah anggota") from None


def daftar_kelompok(kon, sekarang) -> List[dict]:
    """Semua kelompok + terisi/kuota + pertemuan aktif berikutnya (mulai >= `sekarang`; None bila selesai).

    Tambahan: `terbuka` (masih menerima anak baru: belum selesai dan kurang dari dua pertemuan aktif yang sudah mulai)
    dan `bentrok` (jumlah pertemuan aktif kelompok yang beririsan dengan jadwal guru yang sama; peringatan saja).
    """
    d.periksa_koneksi(kon)
    kini = dasar.ke_baku(sekarang)
    baris = kon.execute(
        """SELECT k.id,k.nama,k.lokasi,k.guru_id,k.kuota,
                  (SELECT COUNT(*) FROM jadwal_penempatan p WHERE p.kelompok_id=k.id) AS terisi,
                  (SELECT MIN(s.mulai) FROM jadwal_pertemuan s
                    WHERE s.kelompok_id=k.id AND s.dibatalkan=0 AND s.mulai>=?) AS berikut,
                  (SELECT COUNT(*) FROM jadwal_pertemuan s
                    WHERE s.kelompok_id=k.id AND s.dibatalkan=0 AND s.mulai<?) AS sudah_mulai
             FROM jadwal_kelompok k ORDER BY k.nama,k.id""", (kini, kini))
    bentrok = _id_sesi_bentrok(kon)
    per_kelompok = {}
    for sesi in kon.execute("SELECT id,kelompok_id FROM jadwal_pertemuan WHERE kelompok_id IS NOT NULL"):
        if sesi["id"] in bentrok:
            per_kelompok[sesi["kelompok_id"]] = per_kelompok.get(sesi["kelompok_id"], 0) + 1
    hasil = []
    for b in baris:
        isi = {k: b[k] for k in b.keys() if k != "sudah_mulai"}
        isi["terbuka"] = b["berikut"] is not None and b["sudah_mulai"] < TUTUP_SETELAH_PERTEMUAN_MULAI
        isi["bentrok"] = per_kelompok.get(b["id"], 0)
        hasil.append(isi)
    return hasil


def detail_kelompok(kon, kelompok_id) -> dict:
    """Kelompok + anggota (order/anak/akhir akses) + delapan pertemuan (tiap sesi dengan `bentrok`: bool)."""
    d.periksa_koneksi(kon)
    kid = jd.periksa_kelompok_id(kelompok_id)
    kelompok = _group(kon, kid)
    if kelompok is None:
        raise jd.JadwalTidakDitemukan()
    anggota = [dict(b) for b in kon.execute(
        """SELECT p.order_id,o.siswa_id,o.paket,MAX(a.berakhir) AS berakhir
             FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id
             LEFT JOIN kelas_akses a ON a.order_id=p.order_id
            WHERE p.kelompok_id=? GROUP BY p.order_id,o.siswa_id,o.paket
            ORDER BY p.order_id""", (kid,))]
    sesi = [dict(b) for b in kon.execute(
        """SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan
            WHERE kelompok_id=? ORDER BY ke,id""", (kid,))]
    return {"kelompok": kelompok, "anggota": anggota, "sesi": _tandai_bentrok(sesi, _id_sesi_bentrok(kon)),
            "terisi": _isi_kelompok(kon, kid)}


# --- penempatan -----------------------------------------------------------------------------

def _order_aktif(kon, order_id, kini):
    order = ks.baris_order(kon, order_id)
    if order is None:
        raise jd.JadwalTidakDitemukan()
    if ks.status_dari(order, ks.fakta_order(kon, order_id), kini) != dasar.STATUS_AKTIF:
        raise jd.JadwalKonflik("paket belum aktif; setujui bukti dulu")
    return order


def tempatkan(kon, admin_id, order_id, *, kelompok_id=None, guru_id=None, tanggal=None, jam=None,
              sekarang) -> dict:
    """Tempatkan order aktif: Mini ke kelompok (kuota dijaga), Private per anak + 8 pertemuan.

    Mengembalikan `{"jenis": "kelompok"|"privat", "kelompok_id", "guru_id", "sesi"}`.
    """
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    order_id = dasar.periksa_order_id(order_id)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        order = _order_aktif(kon, order_id, kini)
        if order["paket"] == schema_jadwal.KODE_PAKET_MINI:
            if kelompok_id is None or guru_id is not None or tanggal is not None or jam is not None:
                raise jd.JadwalTidakSah("penempatan Mini harus memilih kelompok")
            kid = jd.periksa_kelompok_id(kelompok_id)
            kelompok = _group(kon, kid)
            if kelompok is None:
                raise jd.JadwalTidakDitemukan()
            if _pertemuan_mendatang(kon, kid, kini) is None:
                raise jd.JadwalKonflik("kelompok sudah selesai")
            if _jumlah_sudah_mulai(kon, kid, kini) >= TUTUP_SETELAH_PERTEMUAN_MULAI:
                raise jd.JadwalKonflik(PESAN_DITUTUP)
            _pastikan_dalam_akses(_pertemuan_aktif_terakhir(kon, kid), _batas_akses_order(kon, order_id))
            _pensiunkan_penempatan_lama(kon, order_id, kini)
            if _isi_kelompok(kon, kid) >= kelompok["kuota"]:
                raise jd.JadwalPenuh()
            try:
                kon.execute(
                    "INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                    "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                    (order_id, kid, kini, kini, aktor, aktor))
            except sqlite3.IntegrityError as galat:
                raise _peta_integritas(galat) from None
            return {"jenis": "kelompok", "kelompok_id": kid, "guru_id": None, "sesi": []}
        if order["paket"] != schema_jadwal.KODE_PAKET_PRIVATE:
            raise jd.JadwalTidakSah("paket tidak didukung jadwal")
        if kelompok_id is not None or guru_id is None or tanggal is None or jam is None:
            raise jd.JadwalTidakSah("penempatan Private butuh guru, tanggal, dan jam")
        guru = jd.periksa_guru_id(guru_id)
        mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
        if _punya_sesi(kon, order_id):
            raise jd.JadwalKonflik("pertemuan order ini sudah pernah dijadwalkan")
        _pastikan_dalam_akses(jd.delapan_pertemuan(mulai)[-1], _batas_akses_order(kon, order_id))
        _pensiunkan_penempatan_lama(kon, order_id, kini)
        try:
            kon.execute(
                "INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (order_id, guru, schema_jadwal.LOKASI_PRIVATE, kini, kini, aktor, aktor))
        except sqlite3.IntegrityError as galat:
            raise _peta_integritas(galat) from None
        _tulis_sesi(kon, order_id=order_id, mulai=mulai,
                    menit=katalog.ambil(schema_jadwal.KODE_PAKET_PRIVATE).menit, aktor=aktor, kini=kini)
        return {"jenis": "privat", "kelompok_id": None, "guru_id": guru, "sesi": []}


def _punya_sesi(kon, order_id) -> bool:
    return kon.execute("SELECT 1 FROM jadwal_pertemuan WHERE order_id=? LIMIT 1", (order_id,)).fetchone() is not None


def _sesi_sudah_mulai(kon, order_id, kini: str) -> bool:
    return kon.execute("SELECT 1 FROM jadwal_pertemuan WHERE order_id=? AND mulai<? AND dibatalkan=0 LIMIT 1",
                       (order_id, kini)).fetchone() is not None


def _peta_integritas(galat):
    pesan = str(galat).lower()
    if "kelompok penuh" in pesan:
        return jd.JadwalPenuh()
    if "sudah punya penempatan" in pesan:
        return jd.JadwalKonflik("anak sudah punya penempatan; lepas dulu sebelum pindah")
    if "paket dan jenis" in pesan:
        return jd.JadwalTidakSah("paket dan jenis penempatan tidak cocok")
    if "unique" in pesan or "primary key" in pesan:
        return jd.JadwalKonflik("order sudah punya penempatan; lepas dulu untuk mengubah")
    return jd.JadwalTidakSah("penempatan bentrok dengan catatan yang ada")


def lepas_penempatan(kon, admin_id, order_id, *, versi, sekarang) -> None:
    """Lepas penempatan. Mini boleh kapan saja (sesi tetap milik kelompok).

    `versi` WAJIB sama dengan `dibuat` penempatan sekarang (nilai yang dilihat admin saat halaman dibuka): form lama
    dari penempatan sebelumnya (sudah dilepas lalu ditempatkan ulang) ditolak JadwalKonflik tanpa efek.

    Private hanya sebelum ada pertemuan yang mulai (semua `mulai >= sekarang`); sesinya ikut dihapus. Sesudah itu
    sesi adalah riwayat, jadi penempatan tidak dilepas (JadwalKonflik, tanpa efek).
    """
    d.periksa_koneksi(kon)
    d.periksa_pelaku(admin_id)
    order_id = dasar.periksa_order_id(order_id)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        ada = kon.execute("SELECT kelompok_id,dibuat FROM jadwal_penempatan WHERE order_id=?",
                          (order_id,)).fetchone()
        if ada is None:
            raise jd.JadwalTidakDitemukan()
        if type(versi) is not str or versi != ada["dibuat"]:
            raise jd.JadwalKonflik(PESAN_VERSI_BASI)
        if ada["kelompok_id"] is None:
            if _sesi_sudah_mulai(kon, order_id, kini):
                raise jd.JadwalKonflik("sebagian pertemuan sudah berlangsung; penempatan tidak dilepas")
            kon.execute("DELETE FROM jadwal_pertemuan WHERE order_id=?", (order_id,))
        kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (order_id,))


def ringkas_order(kon, order_id) -> Optional[dict]:
    """Penempatan satu order + kelompok + sesi (tiap sesi dengan `bentrok`: bool) untuk halaman detail admin."""
    d.periksa_koneksi(kon)
    order_id = dasar.periksa_order_id(order_id)
    baris = kon.execute(
        """SELECT p.order_id,p.kelompok_id,p.guru_id,p.lokasi,p.dibuat,
                  k.nama AS kelompok_nama,k.lokasi AS kelompok_lokasi,k.guru_id AS kelompok_guru,
                  o.siswa_id,o.paket
             FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id
             LEFT JOIN jadwal_kelompok k ON k.id=p.kelompok_id
            WHERE p.order_id=?""", (order_id,)).fetchone()
    if baris is None:
        return None
    hasil = dict(baris)
    sesi = [dict(b) for b in kon.execute(
        """SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan
            WHERE kelompok_id=? OR order_id=? ORDER BY ke,id""",
        (baris["kelompok_id"], order_id))]
    hasil["sesi"] = _tandai_bentrok(sesi, _id_sesi_bentrok(kon))
    return hasil


# --- bacaan untuk orang tua -----------------------------------------------------------------

def jadwal_untuk_murid(kon, order_id) -> Optional[dict]:
    """Jadwal penempatan satu order untuk orang tua: `{"lokasi", "sesi": [{ke,mulai,menit,dibatalkan}]}` atau None.

    Sengaja TANPA guru, id kelompok/order, atau nama/kontak apa pun. Private: lokasi "Online" dan sesi order;
    Mini: lokasi dan sesi kelompok. Order tanpa penempatan (termasuk yang sudah dipensiunkan) -> None.
    """
    d.periksa_koneksi(kon)
    order_id = dasar.periksa_order_id(order_id)
    baris = kon.execute(
        """SELECT p.kelompok_id,COALESCE(p.lokasi,k.lokasi) AS lokasi
             FROM jadwal_penempatan p LEFT JOIN jadwal_kelompok k ON k.id=p.kelompok_id
            WHERE p.order_id=?""", (order_id,)).fetchone()
    if baris is None:
        return None
    sesi = kon.execute(
        """SELECT ke,mulai,menit,dibatalkan FROM jadwal_pertemuan
            WHERE kelompok_id=? OR order_id=? ORDER BY ke,id""", (baris["kelompok_id"], order_id))
    return {"lokasi": baris["lokasi"],
            "sesi": [{"ke": s["ke"], "mulai": s["mulai"], "menit": s["menit"], "dibatalkan": bool(s["dibatalkan"])}
                     for s in sesi]}


def jadwal_terbaru_murid(kon, akun_id, siswa_id, sekarang) -> Optional[dict]:
    """Jadwal order AKTIF terbaru milik (akun, anak) ini yang punya penempatan, atau None.

    Order hanya dari akun dan anak yang disuntik pemanggil (dari sesi); order akun/anak lain tidak pernah terbaca.
    Order yang belum aktif (menunggu, ditolak, kedaluwarsa) dilewati, jadi perpanjangan yang belum dibayar tidak
    menyembunyikan jadwal yang sedang berjalan.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    dasar.periksa_siswa_id(siswa_id)
    kini = dasar.ke_baku(sekarang)
    for order in kon.execute("SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? "
                             "ORDER BY dibuat DESC,id DESC" % ks.KOLOM_ORDER, (akun_id, siswa_id)).fetchall():
        if ks.status_dari(order, ks.fakta_order(kon, order["id"]), kini) != dasar.STATUS_AKTIF:
            continue
        jadwal = jadwal_untuk_murid(kon, order["id"])
        if jadwal is not None:
            return jadwal
    return None


# --- pertemuan ------------------------------------------------------------------------------

def pertemuan_dari(kon, pertemuan_id) -> Optional[dict]:
    d.periksa_koneksi(kon)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    baris = kon.execute(
        "SELECT id,kelompok_id,order_id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan WHERE id=?",
        (pid,)).fetchone()
    return None if baris is None else dict(baris)


def _batas_akses_sesi(kon, sesi: dict) -> Optional[str]:
    if sesi["order_id"] is not None:
        return _batas_akses_order(kon, sesi["order_id"])
    return _batas_akses_kelompok(kon, sesi["kelompok_id"])


def ubah_pertemuan(kon, admin_id, pertemuan_id, *, tanggal, jam, sekarang) -> None:
    """Geser satu pertemuan; identitas (kelompok/order/ke) tidak berubah dan waktu tidak melewati masa akses."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    mulai = jd.pertemuan_pertama(tanggal, jam, sekarang)
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        sesi = pertemuan_dari(kon, pid)
        if sesi is None:
            raise jd.JadwalTidakDitemukan()
        _pastikan_dalam_akses(mulai, _batas_akses_sesi(kon, sesi), PESAN_GESER_LEWAT_AKSES)
        kon.execute("UPDATE jadwal_pertemuan SET mulai=?,diubah=?,diubah_oleh=? WHERE id=?",
                    (mulai, kini, aktor, pid))


def batalkan_pertemuan(kon, admin_id, pertemuan_id, *, batal, sekarang) -> None:
    """Batalkan/pulihkan satu pertemuan tanpa menghapus baris (jejak tetap)."""
    d.periksa_koneksi(kon)
    aktor = d.periksa_pelaku(admin_id)
    pid = jd.periksa_pertemuan_id(pertemuan_id)
    if type(batal) is not bool:
        raise d.PesananDataTidakSah("status batal tidak sah")
    kini = dasar.ke_baku(sekarang)
    with d.tulis(kon):
        if pertemuan_dari(kon, pid) is None:
            raise jd.JadwalTidakDitemukan()
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=?,diubah=?,diubah_oleh=? WHERE id=?",
                    (1 if batal else 0, kini, aktor, pid))
