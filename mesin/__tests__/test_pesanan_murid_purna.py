"""V4a: kartu "Voucher dan laporan" dan pilihan terlambat di permukaan pembeli (murid) lewat HTTP nyata.

Order lunas di jalur QRIS DAN transfer rekening (fixture `lunas_murid`); provider dan data sintetis. Efek (atau
ketiadaannya) dibuktikan dari tabel purna + kedua tabel refund, bukan hanya kode status. Tes negatif di sini menjadi
sasaran mutation di `test_pesanan_murid_purna_mutation.py`.
"""
from __future__ import annotations

import re

import pytest

import pesanan
import pesanan_http
import purna
import schema_purna
from admin_pesanan_kit import login_admin
from admin_transfer_kit import SETUJUI, kirim_putusan
from bukti_kit import JPEG, bukti
from pesanan_http_kit import (  # noqa: F401
    KOSONG, WA_SINTETIS, bayar, jam, keluarga, kirim, ledger, minta_mentah, principal_basic_untuk, server, settlement,
    teks_tampak, tertutup, token,
)
from pesanan_murid_kit import M, NAMA_ANAK_A, NAMA_ANAK_B, buat_murid, sakelar_hidup  # noqa: F401
from pesanan_transfer_http_kit import minta_multipart, transfer  # noqa: F401
from pesanan_transfer_pages import waktu_wib
from purna_http_kit import bayar_purna, potret_efek, transfer_purna  # noqa: F401
from purna_http_kit import jadikan_ditahan as jadikan_ditahan_kit

PILIH = M + "/pilih"
JAM_LEWAT_BATAS = 24 * 5 + 1       # janji 48 jam + toleransi 72 jam + 1 jam
KATA_TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "pembahasan", "jawaban benar", "tel:", "wa.me")
KARTU = re.compile(r'<div class="kartu-st" id="kartu-voucher">(.*?)</div>', re.S)
TOMBOL = re.compile(r'<button type="submit" name="pilihan" value="(\w+)"')
COPY_UANG_KEMBALI = "Permintaan uang kembali dicatat. Tim akan menghubungi Anda."


class Siap:
    """Server + murid pembeli + order lunas."""

    def __init__(self, server, murid, order_id):
        self.server, self.murid, self.order_id = server, murid, order_id


def _pesan_dan_tagihan(server, murid):
    assert kirim(server, M + "/pesan", murid.akun, aksi="pesan")[0] == 303
    with ledger() as kon:
        return kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]


def _lunas_qris(server, murid):
    order_id = _pesan_dan_tagihan(server, murid)
    trx = server.provider.transaksi[order_id]
    server.provider.status_data = lambda oid: settlement(oid, trx)
    assert minta_mentah(server, M, murid.akun)[0] == 200       # GET status menerapkan hasil provider
    return order_id


def _lunas_transfer(server, murid):
    order_id = _pesan_dan_tagihan(server, murid)
    assert kirim(server, M + "/tagihan", murid.akun, aksi="tagihan")[0] == 303
    tok = token(murid.akun, "bukti")
    assert minta_multipart(server, M + "/bukti", murid.akun, bukti(tok, JPEG))[0] == 303
    admin = login_admin(server)
    assert kirim_putusan(server, admin, SETUJUI, order_id)[0] == 303
    return order_id


def _siapkan(server, jalur, nama="murid-a", nama_anak=NAMA_ANAK_A):
    murid = buat_murid(server, nama, nama_anak)
    pembuat = _lunas_qris if jalur == "qris" else _lunas_transfer
    return Siap(server, murid, pembuat(server, murid))


@pytest.fixture(params=["qris", "transfer"])
def lunas_murid(request, sakelar_hidup):
    """Order lunas milik murid di jalur QRIS lalu transfer rekening; skema purna terpasang."""
    server = request.getfixturevalue("bayar_purna" if request.param == "qris" else "transfer_purna")
    return _siapkan(server, request.param)


@pytest.fixture()
def transfer_lunas_tanpa_purna(transfer, sakelar_hidup):
    """Order transfer lunas, tetapi skema purna BELUM dimigrasikan (transfer sudah)."""
    return _siapkan(transfer, "transfer")


def refund_mentah(siap, jam, kon=None):
    """Catatan refund langsung ke ledger yang menjadi jalur order (receipt QRIS: pesanan_refund; selain itu transfer)."""
    if kon is None:
        with ledger() as baru:
            return refund_mentah(siap, jam, baru)
    tabel = ("pesanan_refund" if kon.execute("SELECT 1 FROM pesanan_receipt WHERE order_id=?",
                                             (siap.order_id,)).fetchone() else "transfer_refund")
    kon.execute("BEGIN IMMEDIATE")
    kon.execute("INSERT INTO %s(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) VALUES(?,?,?,?,?)" % tabel,
                ("rfd_sintetis_0001", siap.order_id, "admin_sintetis", "kebijakan", jam()))
    kon.commit()


def halaman(siap, akun=None):
    kode, isi, _ = minta_mentah(siap.server, M, siap.murid.akun if akun is None else akun)
    assert kode == 200
    return isi


def kartu(isi):
    cocok = KARTU.search(isi)
    return None if cocok is None else cocok.group(1)


def pilih(siap, pilihan, murid=None, **kw):
    """POST pilihan; 'uang_kembali' otomatis membawa kotak yakin kecuali yakin=False (konfirmasi M-1)."""
    ekstra = {} if pilihan is None else {"pilihan": pilihan}
    if kw.pop("yakin", True) and pilihan == purna.PILIHAN_UANG_KEMBALI:
        ekstra["yakin"] = "1"
    ekstra.update(kw.pop("ekstra", {}))
    return kirim(siap.server, PILIH, (murid or siap.murid).akun, aksi=kw.pop("aksi", "pilih"),
                 ekstra=ekstra, **kw)


def keadaan(siap):
    with ledger() as kon:
        return purna.keadaan(kon, siap.order_id, pesanan_http.alur.waktu_sekarang())


def terlambat(siap, jam):
    jam.maju_jam(JAM_LEWAT_BATAS)
    assert keadaan(siap).bisa_pilih


def jadikan_ditahan(siap, jam):
    jadikan_ditahan_kit(siap.server, siap.order_id, jam)


def baris_pilihan():
    return [b[1] for b in potret_efek()["purna_pilihan_terlambat"]]


# --- kartu: tampil dan isi ---------------------------------------------------------------------

def test_kartu_tampil_untuk_order_lunas_dengan_kode_tenggat_dan_janji_tanpa_tombol(lunas_murid):
    siap = lunas_murid
    k = keadaan(siap)
    isi = kartu(halaman(siap))
    assert isi is not None
    tampak = teks_tampak(isi)
    assert "Voucher dan laporan" in tampak
    assert k.kode in tampak and k.kode.startswith("JGV-")
    assert "Berlaku hingga " + waktu_wib(k.berlaku_hingga) in tampak
    assert "Laporan lengkap dijanjikan terbit " + waktu_wib(k.janji_terbit) in tampak
    assert "<form" not in isi and "<button" not in isi          # belum terlambat: tanpa tombol
    assert PILIH not in halaman(siap)


def test_kalimat_status_voucher_awam_mengikuti_keadaan(lunas_murid, jam):
    import pesanan_voucher_pages as hv
    siap = lunas_murid
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_AKTIF] in teks_tampak(kartu(halaman(siap)))
    with ledger() as kon:
        purna.catat_pakai(kon, siap.order_id, "vch_sintetis_0001", "admin_sintetis", "kelas", jam())
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_DIPAKAI] in teks_tampak(kartu(halaman(siap)))


def test_kalimat_status_voucher_kedaluwarsa(lunas_murid, jam):
    import pesanan_voucher_pages as hv
    jam.maju_jam(24 * 90 + 1)
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_KEDALUWARSA] in teks_tampak(kartu(halaman(lunas_murid)))


def test_kartu_tidak_tampil_sebelum_lunas(sakelar_hidup, bayar_purna):
    murid = buat_murid(bayar_purna, "murid-a", NAMA_ANAK_A)
    assert kirim(bayar_purna, M + "/pesan", murid.akun, aksi="pesan")[0] == 303
    kode, isi, _ = minta_mentah(bayar_purna, M, murid.akun)
    assert kode == 200 and "Menunggu pembayaran" in teks_tampak(isi)         # halaman lama tetap tampil utuh
    assert "kartu-voucher" not in isi and "Voucher dan laporan" not in isi and PILIH not in isi


def test_kartu_tidak_tampil_untuk_order_direfund(lunas_murid, jam):
    siap = lunas_murid
    assert kartu(halaman(siap)) is not None
    refund_mentah(siap, jam)
    isi = halaman(siap)
    assert "kartu-voucher" not in isi and PILIH not in isi


def test_kartu_tidak_tampil_bila_skema_purna_belum_dipasang(transfer_lunas_tanpa_purna, jam):
    siap = transfer_lunas_tanpa_purna
    jam.maju_jam(JAM_LEWAT_BATAS)
    isi = halaman(siap)
    assert "Pembayaran diterima" in teks_tampak(isi)             # perilaku lama tetap
    assert "kartu-voucher" not in isi and "Voucher dan laporan" not in isi and PILIH not in isi


# --- kartu: tombol dan keadaan pilihan ---------------------------------------------------------

def test_dua_tombol_dalam_dua_form_terpisah_hanya_saat_terlambat_dan_bisa_pilih(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    isi = kartu(halaman(siap))
    assert isi.count("<form") == 2 and isi.count(f'action="{PILIH}"') == 2
    assert TOMBOL.findall(isi) == ["menunggu", "uang_kembali"]
    assert isi.count('name="yakin" value="1" required') == 1        # hanya form uang kembali yang punya kotak yakin
    tampak = teks_tampak(isi)
    assert "Tetap menunggu" in tampak and "Minta uang kembali" in tampak
    assert 'name="token"' in isi and "Laporan lengkap dijanjikan terbit" in tampak


def test_memilih_menunggu_dicatat_prg_dan_kartu_menampilkan_pilihan_dengan_satu_tombol(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    kode, badan, tajuk = pilih(siap, "menunggu")
    assert (kode, badan, tajuk.get("Location")) == (303, "", M)
    assert baris_pilihan() == ["menunggu"]
    isi = kartu(halaman(siap))
    assert "Anda memilih menunggu" in teks_tampak(isi)
    assert TOMBOL.findall(isi) == ["uang_kembali"]


def test_memilih_uang_kembali_dicatat_tanpa_tombol_dan_voucher_batal(lunas_murid, jam):
    import pesanan_voucher_pages as hv
    siap = lunas_murid
    terlambat(siap, jam)
    kode, _badan, tajuk = pilih(siap, "uang_kembali")
    assert (kode, tajuk.get("Location")) == (303, M)
    assert baris_pilihan() == ["uang_kembali"]
    isi = kartu(halaman(siap))
    tampak = teks_tampak(isi)
    assert COPY_UANG_KEMBALI in tampak and hv.COPY_STATUS_VOUCHER[purna.VOUCHER_BATAL] in tampak
    assert "<form" not in isi and "<button" not in isi          # bisa_pilih tetap True, UI memakai k.pilihan
    assert keadaan(siap).bisa_pilih


def test_replay_identik_prg_biasa_satu_baris(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    tok = token(siap.murid.akun, "pilih")
    assert pilih(siap, "menunggu", tok=tok)[0] == 303
    assert pilih(siap, "menunggu", tok=tok)[0] == 303
    assert baris_pilihan() == ["menunggu"]


def test_monoton_menunggu_lalu_uang_kembali_boleh_sebaliknya_konflik(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    assert pilih(siap, "menunggu")[0] == 303 and pilih(siap, "uang_kembali")[0] == 303
    assert baris_pilihan() == ["menunggu", "uang_kembali"]
    sebelum = potret_efek()
    kode, isi, _ = pilih(siap, "menunggu")
    assert kode == 409 and pesan_bentrok() in isi
    assert potret_efek() == sebelum


def pesan_bentrok():
    import pesanan_pages
    return pesanan_pages.COPY_BENTROK


@pytest.mark.parametrize("keadaan_tolak", ["belum_terlambat", "terbit", "dipakai", "direfund", "ditahan"])
def test_pilih_ditolak_409_tanpa_efek_bila_tidak_bisa_pilih(lunas_murid, jam, keadaan_tolak):
    siap = lunas_murid
    if keadaan_tolak != "belum_terlambat":
        terlambat(siap, jam)
    with ledger() as kon:
        if keadaan_tolak == "terbit":
            purna.catat_terbit(kon, siap.order_id, "admin_sintetis", jam())
        elif keadaan_tolak == "dipakai":
            purna.catat_pakai(kon, siap.order_id, "vch_sintetis_0001", "admin_sintetis", "kelas", jam())
        elif keadaan_tolak == "direfund":
            refund_mentah(siap, jam, kon)
    if keadaan_tolak == "ditahan":
        jadikan_ditahan(siap, jam)
    sebelum = potret_efek()
    kode, isi, _ = pilih(siap, "menunggu")
    assert kode == 409 and pesan_bentrok() in isi
    tampak = teks_tampak(isi).lower()
    for alasan in ("belum terlambat", "sudah terbit", "sudah dipakai", "direfund", "purna", "perlu diperiksa"):
        assert alasan not in tampak
    assert potret_efek() == sebelum


def test_kartu_terbit_dan_terlambat_menurut_keadaan(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    assert "keterlambatan" in teks_tampak(kartu(halaman(siap)))
    with ledger() as kon:
        purna.catat_terbit(kon, siap.order_id, "admin_sintetis", jam())
    isi = kartu(halaman(siap))
    assert "Laporan sudah terbit" in teks_tampak(isi) and "<form" not in isi


# --- kepemilikan, palang, token, form, laju ----------------------------------------------------

def test_murid_lain_dan_order_tak_ada_404_identik_dengan_rute_tak_dikenal_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    b = buat_murid(siap.server, "murid-b", NAMA_ANAK_B)            # belum punya order
    sebelum = potret_efek()
    harap = minta_mentah(siap.server, "/murid/tidak-ada-rute", b.akun)[:2]       # jawaban jalur murid tak dikenal
    assert harap[0] == 404
    kode, isi, _ = pilih(siap, "uang_kembali", murid=b)
    assert (kode, isi) == harap
    assert potret_efek() == sebelum
    assert keadaan(siap).pilihan is None


def test_anonim_401_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    assert minta_mentah(siap.server, PILIH, None, {"token": "x", "pilihan": "menunggu"})[0] == 401
    assert potret_efek() == sebelum


@pytest.mark.parametrize("ragam", ["asal", "aksi_lain", "kedaluwarsa", "murid_lain"])
def test_token_tidak_sah_403_tanpa_efek(lunas_murid, jam, ragam):
    siap = lunas_murid
    terlambat(siap, jam)
    b = buat_murid(siap.server, "murid-b", NAMA_ANAK_B)
    tok = {"asal": "x", "aksi_lain": token(siap.murid.akun, "periksa"),
           "kedaluwarsa": "1.%s" % pesanan_http._mac(principal_basic_untuk(siap.murid.akun), None, "pilih", 1),
           "murid_lain": token(b.akun, "pilih")}[ragam]
    sebelum = potret_efek()
    assert pilih(siap, "menunggu", tok=tok)[0] == 403
    assert potret_efek() == sebelum


def test_token_pilih_tidak_berlaku_untuk_aksi_lain(lunas_murid):
    siap = lunas_murid
    tok = token(siap.murid.akun, "pilih")
    assert kirim(siap.server, M + "/periksa", siap.murid.akun, tok=tok)[0] in (403, 404)
    assert potret_efek()["purna_pilihan_terlambat"] == []


@pytest.mark.parametrize("data", [{"pilihan": "refund"}, {"pilihan": ""}, {"pilihan": "MENUNGGU"}, None,
                                  {"pilihan": "menunggu", "order_id": "ord_x"}, {"pilihan": "menunggu", "x": "1"}])
def test_pilihan_asing_dan_form_asing_400_tanpa_efek(lunas_murid, jam, data):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    ekstra = {} if data is None else {k: v for k, v in data.items() if k != "pilihan"}
    kode = pilih(siap, None if data is None else data.get("pilihan", None), ekstra=ekstra)[0]
    assert kode == 400
    assert potret_efek() == sebelum


def test_pilihan_ganda_dalam_form_ditolak(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    tok = token(siap.murid.akun, "pilih")
    kode, _i, _t = minta_mentah(siap.server, PILIH, siap.murid.akun,
                                [("token", tok), ("pilihan", "menunggu"), ("pilihan", "uang_kembali")])
    assert kode == 400 and potret_efek()["purna_pilihan_terlambat"] == []


def test_pembatas_laju_429_tanpa_efek_tambahan(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    for _ in range(pesanan_http.BATAS_PERIKSA):
        assert pilih(siap, "menunggu")[0] == 303
    sebelum = potret_efek()
    assert pilih(siap, "uang_kembali")[0] == 429
    assert potret_efek() == sebelum


def test_skema_purna_belum_dipasang_post_409_tanpa_efek(transfer_lunas_tanpa_purna, jam):
    siap = transfer_lunas_tanpa_purna
    jam.maju_jam(JAM_LEWAT_BATAS)
    kode, isi, _ = pilih(siap, "uang_kembali")
    assert kode == 409 and pesan_bentrok() in isi
    with ledger() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sqlite_master WHERE name GLOB 'purna_*'").fetchone()[0] == 0


# --- palang murid dan isi ----------------------------------------------------------------------

def test_halaman_murid_tanpa_kata_terlarang_kontak_atau_id_internal(lunas_murid, jam):
    siap = lunas_murid
    halamannya = [halaman(siap)]
    terlambat(siap, jam)
    halamannya.append(halaman(siap))
    assert pilih(siap, "menunggu")[0] == 303
    halamannya.append(halaman(siap))
    assert pilih(siap, "uang_kembali")[0] == 303
    halamannya.append(halaman(siap))
    halamannya.append(minta_mentah(siap.server, "/murid/orang-tua", siap.murid.akun)[1])
    for isi in halamannya:
        assert WA_SINTETIS not in isi and "0812" not in isi and "+62" not in isi
        tampak = teks_tampak(isi).lower()
        for kata in KATA_TERLARANG:
            assert kata not in tampak, kata
        assert siap.order_id not in isi and "vch_" not in isi and "operasi" not in tampak


def test_halaman_orang_tua_memuat_satu_baris_janji_tanpa_tombol_dan_beranda_tetap_satu_tautan(lunas_murid, jam):
    siap = lunas_murid
    k = keadaan(siap)
    terlambat(siap, jam)
    isi = minta_mentah(siap.server, "/murid/orang-tua", siap.murid.akun)[1]
    assert "Laporan lengkap dijanjikan terbit " + waktu_wib(k.janji_terbit) in teks_tampak(isi)
    assert PILIH not in isi and "<button" not in isi.split('id="ortu-pesanan"')[1].split("</section>")[0]
    beranda = minta_mentah(siap.server, "/murid", siap.murid.akun)[1]
    assert beranda.count('href="/murid/orang-tua"') == 1


def test_halaman_orang_tua_tanpa_baris_janji_bila_purna_belum_dipasang(transfer_lunas_tanpa_purna):
    isi = minta_mentah(transfer_lunas_tanpa_purna.server, "/murid/orang-tua", transfer_lunas_tanpa_purna.murid.akun)[1]
    assert "dijanjikan terbit" not in teks_tampak(isi)


def test_guru_lama_tanpa_kartu_dan_tanpa_tombol_dan_tanpa_rute_pilih(bayar_purna, sakelar_hidup, jam):
    from admin_pesanan_kit import order_lunas
    from pesanan_http_kit import AKUN_A
    admin = login_admin(bayar_purna)
    order_lunas(bayar_purna, admin)
    jam.maju_jam(JAM_LEWAT_BATAS)
    kode, isi, _ = minta_mentah(bayar_purna, "/pesanan", AKUN_A)
    assert kode == 200 and "Pembayaran diterima" in teks_tampak(isi)
    assert PILIH not in isi and 'name="pilihan"' not in isi and "kartu-voucher" not in isi
    harap = minta_mentah(bayar_purna, "/pesanan/tidak-ada-rute", AKUN_A, {"x": "1"})[:2]
    tok = token(AKUN_A, "pilih")
    assert minta_mentah(bayar_purna, "/pesanan/pilih", AKUN_A, {"token": tok, "pilihan": "menunggu"})[:2] == harap
    assert potret_efek()["purna_pilihan_terlambat"] == []


# --- M-2: POST manual pada order yang bukan lunas-normal harus konflik tanpa efek tulis -----------------

@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilih_manual_pada_order_perlu_diperiksa_konflik_tanpa_efek_dan_kartu_tidak_tampil(lunas_murid, jam, pilihan):
    siap = lunas_murid
    terlambat(siap, jam)
    jadikan_ditahan(siap, jam)
    k = keadaan(siap)
    assert (k.lunas, k.ditahan, k.bisa_pilih, k.voucher) == (True, True, False, purna.VOUCHER_DITAHAN)
    isi = halaman(siap)
    assert "kartu-voucher" not in isi and PILIH not in isi                # kartu pembeli hanya untuk sudah_dibayar
    sebelum = potret_efek()
    kode, badan, _ = pilih(siap, pilihan)
    assert kode == 409 and pesan_bentrok() in badan
    assert potret_efek() == sebelum


@pytest.mark.parametrize("pilihan", ["menunggu", "uang_kembali"])
def test_pilih_manual_pada_order_belum_dibayar_konflik_tanpa_efek(sakelar_hidup, bayar_purna, pilihan):
    murid = buat_murid(bayar_purna, "murid-a", NAMA_ANAK_A)
    siap = Siap(bayar_purna, murid, _pesan_dan_tagihan(bayar_purna, murid))
    assert not keadaan(siap).lunas
    sebelum = potret_efek()
    kode, badan, _ = pilih(siap, pilihan)
    assert kode == 409 and pesan_bentrok() in badan
    assert potret_efek() == sebelum


# --- M-1: konfirmasi "yakin" untuk uang kembali ditegakkan server ----------------------------------

def test_kartu_terlambat_memuat_kotak_yakin_hanya_di_form_uang_kembali(lunas_murid, jam):
    import pesanan_voucher_pages as hv
    siap = lunas_murid
    terlambat(siap, jam)
    isi = kartu(halaman(siap))
    assert isi.count('type="checkbox" name="yakin" value="1" required') == 1 and hv.COPY_YAKIN in teks_tampak(isi)
    assert "Final" not in isi.split("menunggu")[0]


def test_uang_kembali_tanpa_yakin_ditolak_400_dengan_pesan_konfirmasi_tanpa_efek(lunas_murid, jam):
    import pesanan_voucher_pages as hv
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    kode, badan, _ = pilih(siap, "uang_kembali", yakin=False)
    assert kode == 400 and hv.COPY_YAKIN_WAJIB in badan
    assert potret_efek() == sebelum and keadaan(siap).pilihan is None


@pytest.mark.parametrize("nilai", ["", "0", "2", "on", "true"])
def test_uang_kembali_dengan_yakin_bukan_satu_ditolak_400_tanpa_efek(lunas_murid, jam, nilai):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    assert pilih(siap, "uang_kembali", yakin=False, ekstra={"yakin": nilai})[0] == 400
    assert potret_efek() == sebelum


def test_menunggu_dengan_yakin_ditolak_400_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    assert pilih(siap, "menunggu", ekstra={"yakin": "1"})[0] == 400
    assert potret_efek() == sebelum


def test_uang_kembali_dengan_yakin_dan_field_asing_ditolak_400_tanpa_efek(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    sebelum = potret_efek()
    assert pilih(siap, "uang_kembali", ekstra={"order_id": "ord_x"})[0] == 400
    assert potret_efek() == sebelum


def test_uang_kembali_dengan_yakin_dicatat_prg_303_dan_menunggu_tanpa_yakin_tetap_303(lunas_murid, jam):
    siap = lunas_murid
    terlambat(siap, jam)
    assert pilih(siap, "menunggu")[0] == 303
    kode, badan, tajuk = pilih(siap, "uang_kembali")
    assert (kode, badan, tajuk.get("Location")) == (303, "", M)
    assert baris_pilihan() == ["menunggu", "uang_kembali"]
