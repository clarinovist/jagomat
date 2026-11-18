"""Alur pesanan Paket Coba (funnel Fase 3c-3): prasyarat, create, periksa, ulang, tampilan.

Lapisan antara HTTP (`pesanan_http`) dan domain ledger (`pesanan`). Semua fakta uang
datang dari ledger atau dari hasil provider server-ke-server; tidak ada nominal,
`id_akun`, atau URL dari klien. Panggilan jaringan (klien provider) tidak pernah
terjadi di dalam transaksi tulis.

Keputusan penting:

- Cek harus SELESAI untuk anak yang dipesan: `cek_gratis.hasil_siswa` (per `siswa_id`),
  bukan `baca_hasil` (cek terbaru akun, bisa milik anak lain).
- Jejak create = pengamatan ledger `{order_id, transaction_id}` saja dengan
  `operasi_id` `buat_` + hash (order, kunci idempotensi JENDELA). Respons create asli tidak
  tersedia di klien order, jadi status/kode tidak dikarang: status pengamatan menjadi
  `tidak_dikenal` dan domain tidak membuat receipt darinya. Baris itu = "transaksi jendela
  terbaru": dasar tombol buat, QR, dan syarat buat ulang (sinyal mati dari transaksi
  jendela SEBELUMNYA tidak membuka jendela baru, walau tetap dicatat di ledger).
- Setiap hasil status provider diterapkan ke ledger (`sts_` + hash), termasuk untuk
  transaksi lama: pembayaran terlambat adalah uang nyata dan tidak boleh disaring.
- QR hanya diturunkan dari hasil status yang cocok (pending, 201, fraud ok, nominal/
  merchant/IDR/QRIS cocok order, `transaction_id` = transaksi jendela terbaru).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Optional

import cek_gratis
import database
import kontak_akun
import pesanan
import pesanan_jendela as jendela_modul
import pesanan_provider as provider_modul
from cek_http import _anak_akun

AKSI_PERIKSA = "periksa"
AKSI_BUAT = "buat"
AKSI_ULANG = "ulang"
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_STATUS_TERBUKA = (pesanan.STATUS_BELUM_BAYAR, pesanan.STATUS_KEDALUWARSA)
_PANJANG_HASH = 32
_KUNCI_STATUS = ("order_id", "status_code", "transaction_status", "transaction_id",
                 "fraud_status", "gross_amount")


class PesananTanpaAnak(Exception):
    """Akun belum punya anak (tidak ada yang bisa dipesan)."""


class PesananCekBelumSelesai(Exception):
    """Cek gratis anak ini belum selesai/berskor; tidak ada order."""


@dataclass(frozen=True)
class HasilPeriksa:
    dicoba: bool = False
    ok: bool = False
    data: Optional[dict] = field(default=None, repr=False)


@dataclass(frozen=True)
class Tampilan:
    status: str
    nama_anak: str
    qr_url: Optional[str] = field(default=None, repr=False)
    boleh_buat: bool = False
    boleh_ulang: bool = False
    boleh_periksa: bool = False
    belum_terperiksa: bool = False


@dataclass(frozen=True)
class Keadaan:
    """Potret ledger satu order pada satu waktu (tanpa data sensitif tambahan)."""
    order: dict = field(repr=False)
    jendela: dict = field(repr=False)
    status: str
    transaksi: Optional[str] = field(repr=False)
    pernah_transaksi: bool
    mati: bool


def _sekarang() -> str:
    return datetime.now(timezone.utc).strftime(_FORMAT_WAKTU)


def _hash(*bagian) -> str:
    return hashlib.sha256("|".join(str(b) for b in bagian).encode("utf-8")).hexdigest()[:_PANJANG_HASH]


def operasi_buat(order_id: str, kunci_jendela: str) -> str:
    return "buat_" + _hash(order_id, kunci_jendela)


def operasi_status(hasil: dict) -> str:
    """Id deterministik dari field status; nominal ikut agar isi beda tak berbenturan."""
    return "sts_" + _hash(*(hasil.get(k, "") for k in _KUNCI_STATUS))


def operasi_ulang(order_id: str, urutan_baru: int) -> str:
    return "ulg_" + _hash(order_id, urutan_baru)


def _order_anak(kon, akun_id, siswa_id):
    """Order milik akun untuk anak ini, divalidasi ulang kepemilikannya; None bila belum ada."""
    baris = kon.execute("SELECT order_id FROM pesanan_order WHERE akun_id=? AND siswa_id=?",
                        (akun_id, siswa_id)).fetchone()
    if baris is None:
        return None
    return pesanan.ambil_order(kon, baris["order_id"], akun_id)


def _transaksi_jendela(kon, order_id, jendela):
    baris = kon.execute("SELECT transaksi_id FROM pesanan_pengamatan WHERE operasi_id=?",
                        (operasi_buat(order_id, jendela["idempotency_key"]),)).fetchone()
    return None if baris is None else baris["transaksi_id"]


def _pernah_transaksi(kon, order_id):
    return kon.execute("SELECT 1 FROM pesanan_pengamatan WHERE order_id=? "
                       "AND transaksi_id IS NOT NULL LIMIT 1", (order_id,)).fetchone() is not None


def _mati_untuk(kon, order_id, transaksi):
    """Provider menyatakan expire/cancel/deny untuk TRANSAKSI jendela terbaru ini."""
    if transaksi is None:
        return False
    return kon.execute(
        "SELECT 1 FROM pesanan_pengamatan WHERE order_id=? AND sumber='status' AND transaksi_id=? "
        "AND transaction_status IN (%s) LIMIT 1" % ",".join("'%s'" % s for s in jendela_modul.KELAS_MATI),
        (order_id, transaksi)).fetchone() is not None


def _keadaan(kon, order, kini) -> Keadaan:
    order_id = order["order_id"]
    jendela = pesanan.jendela_terbaru(kon, order_id)
    transaksi = _transaksi_jendela(kon, order_id, jendela)
    return Keadaan(
        order=order, jendela=jendela,
        status=pesanan.status_order(kon, order_id, order["akun_id"], kini)["status"],
        transaksi=transaksi, pernah_transaksi=_pernah_transaksi(kon, order_id),
        mati=_mati_untuk(kon, order_id, transaksi))


def _siap_klien(keadaan: Keadaan) -> dict:
    """Dict order untuk klien provider: kedaluwarsa dan kunci TIMPA dengan jendela terbaru."""
    return {**keadaan.order, "kedaluwarsa": keadaan.jendela["kedaluwarsa"],
            "idempotency_key": keadaan.jendela["idempotency_key"]}


def _baca_keadaan(path, akun_id, order_id) -> Keadaan:
    with pesanan.buka(path, tulis_data=True) as kon:
        return _keadaan(kon, pesanan.ambil_order(kon, order_id, akun_id), _sekarang())


def ambil_anak(principal):
    """(id, nama) anak akun sesi (satu anak per akun: id terkecil) atau None."""
    with database.buka() as kon:
        baris = _anak_akun(kon, principal.pengguna)
    return None if baris is None else {"id": baris["id"], "nama": baris["nama"]}


def _prasyarat(principal):
    """(anak, cek_id, selesai, punya_kontak) dari DB belajar; hanya baca, per anak."""
    with database.buka() as kon:
        baris = _anak_akun(kon, principal.pengguna)
        if baris is None:
            raise PesananTanpaAnak()
        hasil = cek_gratis.hasil_siswa(kon, principal.id_akun, baris["id"])
        cek = kon.execute("SELECT id FROM cek_gratis WHERE id_akun=? AND siswa_id=?",
                          (principal.id_akun, baris["id"])).fetchone()
        kontak = kontak_akun.ambil(kon, principal.id_akun)
    selesai = pesanan.periksa_prasyarat_cek(hasil) and cek is not None
    return (baris["id"], None if cek is None else cek["id"], selesai,
            kontak is not None and bool(kontak.get("wa")))


def pastikan_transaksi(path, order_id, akun_id, klien) -> None:
    """Create ke provider bila order belum lunas dan jendela terbaru belum punya transaksi.

    Gagal create tidak mengubah ledger (order tetap belum_bayar tanpa QR; kunci
    idempotensi jendela sama, jadi mengulang tidak membuat order/transaksi ganda).
    """
    keadaan = _baca_keadaan(path, akun_id, order_id)
    if keadaan.status != pesanan.STATUS_BELUM_BAYAR or keadaan.transaksi is not None:
        return
    hasil = klien.buat(_siap_klien(keadaan))
    if hasil.transaksi_id is None:
        return
    with pesanan.buka(path, tulis_data=True) as kon:
        pesanan.terapkan_hasil_provider(
            kon, order_id, {"order_id": order_id, "transaction_id": hasil.transaksi_id},
            _sekarang(), operasi_buat(order_id, keadaan.jendela["idempotency_key"]))


def pesan(path, principal, klien, merchant) -> None:
    """Prasyarat server -> order (idempoten per anak) -> create ke provider bila perlu.

    Raise: PesananTanpaAnak, PesananCekBelumSelesai, pesanan.PesananButuhKontak,
    pesanan.PesananKuotaHabis, pesanan.PesananTidakDitemukan, pesanan.PesananKonflik.
    """
    siswa_id, cek_id, selesai, punya_kontak = _prasyarat(principal)
    if not selesai:
        raise PesananCekBelumSelesai()
    with pesanan.buka(path, tulis_data=True) as kon:
        order = pesanan.buat_order(
            kon, akun_id=principal.id_akun, siswa_id=siswa_id, cek_id=cek_id,
            cek_selesai=True, punya_kontak=punya_kontak, sekarang=_sekarang(), merchant=merchant)
    pastikan_transaksi(path, order["order_id"], principal.id_akun, klien)


def _order_id_anak(path, principal, anak):
    with pesanan.buka(path, tulis_data=True) as kon:
        order = _order_anak(kon, principal.id_akun, anak["id"])
    return None if order is None else order["order_id"]


def buat(path, principal, klien) -> bool:
    """Ulangi create untuk order anak ini; False bila belum ada order."""
    anak = ambil_anak(principal)
    order_id = None if anak is None else _order_id_anak(path, principal, anak)
    if order_id is None:
        return False
    pastikan_transaksi(path, order_id, principal.id_akun, klien)
    return True


def periksa_status(path, order_id, akun_id, klien) -> HasilPeriksa:
    """Satu pemeriksaan status server-ke-server bila belum lunas dan sudah ada transaksi.

    Hasil diterapkan ke ledger lewat jalur domain; galat provider/ledger menghasilkan
    `ok=False` tanpa mengubah ledger (status jujur "belum bisa diperiksa").
    """
    keadaan = _baca_keadaan(path, akun_id, order_id)
    if keadaan.status not in _STATUS_TERBUKA or not keadaan.pernah_transaksi:
        return HasilPeriksa()
    status = klien.status(_siap_klien(keadaan))
    if not status.ok:
        return HasilPeriksa(dicoba=True)
    if status.tanpa_transaksi:
        return HasilPeriksa(dicoba=True, ok=True)
    try:
        with pesanan.buka(path, tulis_data=True) as kon:
            pesanan.terapkan_hasil_provider(kon, order_id, status.hasil_provider, _sekarang(),
                                            operasi_status(status.hasil_provider))
    except pesanan.PesananError:
        return HasilPeriksa(dicoba=True)
    return HasilPeriksa(dicoba=True, ok=True, data=status.hasil_provider)


def periksa(path, principal, klien) -> bool:
    """Periksa manual order anak ini; False bila belum ada order."""
    anak = ambil_anak(principal)
    order_id = None if anak is None else _order_id_anak(path, principal, anak)
    if order_id is None:
        return False
    periksa_status(path, order_id, principal.id_akun, klien)
    return True


def _boleh_ulang(keadaan: Keadaan) -> bool:
    """Syarat server buat ulang: tanpa receipt, jendela lokal habis ATAU transaksi jendela ini mati."""
    if keadaan.status not in _STATUS_TERBUKA:
        return False
    if keadaan.jendela["urutan"] >= jendela_modul.MAKS_JENDELA:
        return False
    return keadaan.status == pesanan.STATUS_KEDALUWARSA or keadaan.mati


def ulang(path, principal, klien) -> bool:
    """Buka jendela baru lalu create dengan kunci jendela baru; False bila tidak diizinkan.

    Syarat ditegakkan di server (bukan hanya tombol disembunyikan), lalu sekali lagi
    oleh domain (`buka_jendela_ulang`: kuota, batas, receipt). Order sama (id tetap).
    """
    anak = ambil_anak(principal)
    order_id = None if anak is None else _order_id_anak(path, principal, anak)
    if order_id is None:
        return False
    keadaan = _baca_keadaan(path, principal.id_akun, order_id)
    if not _boleh_ulang(keadaan):
        return False
    with pesanan.buka(path, tulis_data=True) as kon:
        pesanan.buka_jendela_ulang(kon, order_id, principal.id_akun, _sekarang(),
                                   operasi_ulang(order_id, keadaan.jendela["urutan"] + 1))
    pastikan_transaksi(path, order_id, principal.id_akun, klien)
    return True


def url_qr(data, order: dict, transaksi_jendela, config) -> Optional[str]:
    """URL QR dari hasil status yang cocok; diturunkan seperti `midtrans_contract.periksa_status`."""
    if data is None or transaksi_jendela is None:
        return None
    if (data.get("transaction_status") != "pending" or data.get("status_code") != "201"
            or data.get("fraud_status") not in (None, "accept")):
        return None
    if (data.get("transaction_id") != transaksi_jendela
            or provider_modul.nominal_provider(data.get("gross_amount")) != order["rupiah"]
            or data.get("merchant_id") != order["merchant"]
            or data.get("currency") != order["currency"]
            or data.get("payment_type") != order["channel"]):
        return None
    return config.base_url + "/v2/qris/" + transaksi_jendela + "/qr-code"


def _susun(keadaan: Keadaan, hasil: HasilPeriksa, config, nama: str) -> Tampilan:
    terbuka = keadaan.status in _STATUS_TERBUKA
    belum = keadaan.status == pesanan.STATUS_BELUM_BAYAR
    qr = url_qr(hasil.data, keadaan.order, keadaan.transaksi, config) if belum else None
    boleh_buat = belum and keadaan.transaksi is None
    boleh_ulang = _boleh_ulang(keadaan)
    return Tampilan(
        status=keadaan.status, nama_anak=nama, qr_url=qr, boleh_buat=boleh_buat,
        boleh_ulang=boleh_ulang,
        boleh_periksa=terbuka and keadaan.pernah_transaksi and not boleh_buat and not boleh_ulang,
        belum_terperiksa=terbuka and keadaan.pernah_transaksi and not (hasil.dicoba and hasil.ok))


def tampilan(path, principal, anak, klien, *, periksa_provider: bool) -> Optional[Tampilan]:
    """Status order anak akun sesi; None bila belum ada order.

    `periksa_provider` (diputuskan pembatas laju pemanggil) mengizinkan SATU pemeriksaan
    status; tanpa itu tampilan murni dari ledger dan ditandai `belum_terperiksa`.
    """
    with pesanan.buka(path, tulis_data=True) as kon:
        order = _order_anak(kon, principal.id_akun, anak["id"])
    if order is None:
        return None
    hasil = HasilPeriksa()
    if periksa_provider:
        hasil = periksa_status(path, order["order_id"], principal.id_akun, klien)
    keadaan = _baca_keadaan(path, principal.id_akun, order["order_id"])
    return _susun(keadaan, hasil, klien.config, anak["nama"])
