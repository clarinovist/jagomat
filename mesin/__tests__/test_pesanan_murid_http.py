"""F2c: pesanan Peta Kemampuan Rp49.000 dari akun anak (murid) lewat HTTP nyata.

Mesin pesanan/transfer SAMA dengan sisi guru; yang diuji di sini penentu pembeli + alamat: sakelar
DAFTAR_AKUN_ANAK, palang sesi/peran, anak dari sesi (bukan form/kueri), prasyarat, idempotensi,
jalur transfer (bukti diunggah_oleh akun murid), isolasi antar murid, dan nomor WA tidak tampil.
Semua data sintetis di tmp_path; provider pembayaran PALSU.
"""
from __future__ import annotations

import pytest

import admin_store
import auth
import cek_gratis
import kontak_akun
import pesanan
import pesanan_dasar
import pesanan_pages
import pesanan_transfer
import pesanan_transfer_pages as teks
from cek_gratis_kit import jawab, tandai_selesai
from pesanan_http_kit import (  # noqa: F401
    KOSONG, WA_SINTETIS, WAKTU_AWAL, bayar, jam, keadaan_ledger, kirim, ledger, minta_mentah,
    satu_order, server, teks_tampak, tertutup, token,
)
from pesanan_transfer_http_kit import (  # noqa: F401
    JPEG, PDF, ATAS_NAMA, BANK, NOMOR_LABEL, POLA_NOMINAL, berkas_tersimpan, dua_jalur,
    hitung, kirim_bukti, minta_multipart, transfer,
)
from bukti_kit import bukti, tipe_konten
import cek_http_kit
from cek_http_kit import AKUN_A as GURU_A, AKUN_ADMIN, keluarga  # noqa: F401
from pesanan_murid_kit import (  # noqa: F401
    KATA_TERLARANG, M, NAMA_ANAK_A, NAMA_ANAK_B, SANDI, SELESAI, Murid, buat_murid, cek_gratis_kit_tambah,
    sakelar_hidup,
)

@pytest.fixture()
def dua(transfer, sakelar_hidup):
    """Transfer terbuka + sakelar anak hidup + dua murid siap pesan (A dan B)."""
    transfer.a = buat_murid(transfer, "murid-a", NAMA_ANAK_A)
    transfer.b = buat_murid(transfer, "murid-b", NAMA_ANAK_B)
    return transfer


def post(server, jalur, murid, aksi, **kw):
    return kirim(server, jalur, murid.akun, aksi=aksi, **kw)


def pesan_murid(server, murid, **kw):
    return post(server, M + "/pesan", murid, "pesan", **kw)


def tagihan_murid(server, murid, **kw):
    return post(server, M + "/tagihan", murid, "tagihan", **kw)


def pesan_dan_tagihan(server, murid):
    assert pesan_murid(server, murid)[0] == 303
    assert tagihan_murid(server, murid)[0] == 303


def tak_dikenal(server, akun=None, post_data=None):
    """Jawaban penangan untuk jalur /murid yang tidak dikenal (pembanding 'identik')."""
    return minta_mentah(server, "/murid/tidak-ada-rute", akun, post_data)[:2]


def tanpa_efek():
    assert keadaan_ledger() == KOSONG


def semua_halaman(server, murid):
    kode, isi, _ = minta_mentah(server, M, murid.akun)
    return isi


# --- sakelar, sesi, peran ---------------------------------------------------------------------

JALUR_GET = (M, M + "/qr", M + "/pesan")
JALUR_POST = (M + "/pesan", M + "/periksa", M + "/ulang", M + "/buat", M + "/tagihan", M + "/bukti",
              M + "/tagihan/ulang", M + "/pilih")


def test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal(transfer, monkeypatch, tmp_path):
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.delenv("DAFTAR_AKUN_ANAK", raising=False)
    murid = buat_murid(transfer, "murid-a", NAMA_ANAK_A)
    harap_get = tak_dikenal(transfer, murid.akun)
    for jalur in JALUR_GET:
        assert minta_mentah(transfer, jalur, murid.akun)[:2] == harap_get, jalur
    harap_post = tak_dikenal(transfer, murid.akun, {"x": "1"})
    for jalur in JALUR_POST:
        assert minta_mentah(transfer, jalur, murid.akun, {"token": "x"})[:2] == harap_post, jalur
    tanpa_efek()


def test_anonim_get_303_ke_masuk_dan_post_401_tanpa_efek(dua):
    for jalur in JALUR_GET:
        kode, isi, tajuk = minta_mentah(dua, jalur)
        assert (kode, tajuk.get("Location")) == (303, "/masuk"), jalur
    for jalur in JALUR_POST:
        assert minta_mentah(dua, jalur, None, {"token": "x"})[0] == 401, jalur
    tanpa_efek()


@pytest.mark.parametrize("akun", [GURU_A, AKUN_ADMIN], ids=["guru", "admin"])
def test_guru_dan_admin_tidak_dilayani_di_rute_murid(dua, akun):
    harap = tak_dikenal(dua, akun)
    for jalur in JALUR_GET:
        assert minta_mentah(dua, jalur, akun)[:2] == harap, jalur
    harap_post = tak_dikenal(dua, akun, {"x": "1"})
    for jalur in JALUR_POST:
        assert minta_mentah(dua, jalur, akun, {"token": "x"})[:2] == harap_post, jalur
    tanpa_efek()


def test_guru_bernama_sama_dengan_siswa_tetap_tidak_dilayani_di_rute_murid(dua):
    """Akun warisan tanpa siswa_id dicocokkan lewat nama: peran harus tetap diperiksa lebih dulu."""
    with dua.buka() as kon:
        cek_gratis_kit_tambah(kon, GURU_A[0])           # siswa bernama persis "guru"
    harap = tak_dikenal(dua, GURU_A)
    for jalur in JALUR_GET:
        assert minta_mentah(dua, jalur, GURU_A)[:2] == harap, jalur
    harap_post = tak_dikenal(dua, GURU_A, {"x": "1"})
    for jalur in JALUR_POST:
        assert minta_mentah(dua, jalur, GURU_A, {"token": "x"})[:2] == harap_post, jalur
    tanpa_efek()


# --- alur pesan -------------------------------------------------------------------------------

def test_titik_masuk_tanpa_pesanan_menampilkan_kartu_pesan_dengan_rute_murid(dua):
    kode, isi, tajuk = minta_mentah(dua, M, dua.a.akun)
    assert kode == 200
    assert 'action="/murid/pesanan/pesan"' in isi
    assert "Pesan Peta Kemampuan" in teks_tampak(isi)
    assert 'action="/paket-coba' not in isi and 'href="/guru"' not in isi
    assert "murid-topbar-st" in isi and "akun-editorial-st" in isi
    assert "no-store" in tajuk.get("Cache-Control", "")
    tanpa_efek()


def test_pesan_membuat_order_untuk_akun_dan_anak_sesi_nominal_konstanta(dua):
    kode, _isi, tajuk = pesan_murid(dua, dua.a)
    assert (kode, tajuk.get("Location")) == (303, M)
    order = satu_order()
    assert (order["akun_id"], order["siswa_id"]) == (dua.a.id_akun, dua.a.siswa_id)
    assert order["rupiah"] == pesanan_dasar.RUPIAH_PAKET == 49000


def test_transfer_saja_tidak_pernah_menghubungi_provider_pembayaran(dua):
    pesan_dan_tagihan(dua, dua.a)
    assert dua.provider.panggilan == []


def test_pesan_idempoten_satu_order_per_anak(dua):
    assert pesan_murid(dua, dua.a)[0] == 303
    assert pesan_murid(dua, dua.a)[0] == 303
    with ledger() as kon:
        assert kon.execute("SELECT COUNT(*) FROM pesanan_order").fetchone()[0] == 1


def test_cek_belum_selesai_ditolak_pesan_sama_dengan_guru_tanpa_efek(transfer, sakelar_hidup):
    c = buat_murid(transfer, "murid-c", "Anak Murid Gamma", cek=False)
    kode, isi, _ = pesan_murid(transfer, c)
    assert kode == 409
    tampak = teks_tampak(isi)
    assert pesanan_pages.COPY_CEK_BELUM_SELESAI in tampak
    assert "/cek-kemampuan" not in isi
    tanpa_efek()
    kode_get, isi_get, _ = minta_mentah(transfer, M, c.akun)
    assert kode_get == 409 and pesanan_pages.COPY_CEK_BELUM_SELESAI in teks_tampak(isi_get)


def test_tanpa_kontak_ditolak_pesan_sama_dengan_guru_tanpa_tautan_kontak(transfer, sakelar_hidup):
    c = buat_murid(transfer, "murid-c", "Anak Murid Gamma", kontak=False)
    kode, isi, _ = pesan_murid(transfer, c)
    assert kode == 409
    assert pesanan_pages.COPY_BUTUH_KONTAK in teks_tampak(isi)
    assert "/akun/kontak" not in isi
    tanpa_efek()


def test_nominal_id_akun_dan_anak_dari_form_ditolak_tanpa_efek(dua):
    for ekstra in ({"rupiah": "1000"}, {"siswa_id": str(dua.b.siswa_id)}, {"id_akun": dua.b.id_akun}):
        assert pesan_murid(dua, dua.a, ekstra=ekstra)[0] == 400, ekstra
    tanpa_efek()


def test_kueri_tidak_menentukan_anak_atau_akun(dua):
    assert pesan_murid(dua, dua.a)[0] == 303
    tagihan_murid(dua, dua.a)
    jalur = M + "?siswa_id=%d&akun=%s&pengguna=murid-a" % (dua.a.siswa_id, dua.a.id_akun)
    kode, isi, _ = minta_mentah(dua, jalur, dua.b.akun)       # B memakai kueri yang menunjuk A
    assert kode == 200
    assert 'action="/murid/pesanan/pesan"' in isi          # B tetap melihat keadaan B (belum memesan)
    assert 'action="/murid/pesanan/bukti"' not in isi
    assert NOMOR_LABEL not in isi
    # POST dengan kueri yang menunjuk akun A tetap membuat order atas nama B sendiri
    kode_p = kirim(dua, M + "/pesan?akun=%s&siswa_id=%d" % (dua.a.id_akun, dua.a.siswa_id),
                   dua.b.akun, aksi="pesan")[0]
    assert kode_p == 303
    with ledger() as kon:
        pasangan = {tuple(r) for r in kon.execute("SELECT akun_id, siswa_id FROM pesanan_order")}
    assert pasangan == {(dua.a.id_akun, dua.a.siswa_id), (dua.b.id_akun, dua.b.siswa_id)}


def test_token_milik_murid_lain_ditolak_tanpa_efek(dua):
    token_b = token(dua.b.akun, "pesan")
    assert pesan_murid(dua, dua.a, tok=token_b)[0] == 403
    tanpa_efek()


# --- transfer ---------------------------------------------------------------------------------

def test_tagihan_dan_unggah_bukti_tercatat_atas_akun_murid(dua):
    pesan_dan_tagihan(dua, dua.a)
    kode, isi, _ = minta_mentah(dua, M, dua.a.akun)
    assert kode == 200
    tampak = teks_tampak(isi)
    assert BANK in tampak and NOMOR_LABEL in tampak and ATAS_NAMA in tampak
    assert POLA_NOMINAL.search(tampak)
    assert 'action="/murid/pesanan/bukti"' in isi and "5 MB" in tampak
    tok = token(dua.a.akun, "bukti")
    kode_u, _, tajuk = minta_multipart(dua, M + "/bukti", dua.a.akun, bukti(tok, JPEG))
    assert (kode_u, tajuk.get("Location")) == (303, M)
    with ledger() as kon:
        baris = kon.execute("SELECT diunggah_oleh, order_id FROM transfer_bukti").fetchall()
    assert [b["diunggah_oleh"] for b in baris] == [dua.a.id_akun]
    assert len(berkas_tersimpan(dua)) == 1
    assert "Bukti diterima" in teks_tampak(minta_mentah(dua, M, dua.a.akun)[1])


def test_bukti_mengikuti_batas_ukuran_dan_tipe_sama_dengan_guru(dua):
    pesan_dan_tagihan(dua, dua.a)
    besar = JPEG + b"\x00" * (5 * 1024 * 1024)
    tok = token(dua.a.akun, "bukti")
    assert minta_multipart(dua, M + "/bukti", dua.a.akun, bukti(tok, besar))[0] == 413
    tok = token(dua.a.akun, "bukti")
    assert minta_multipart(dua, M + "/bukti", dua.a.akun, bukti(tok, b"teks biasa bukan gambar"))[0] == 415
    assert berkas_tersimpan(dua) == []


def test_jendela_kedaluwarsa_tombol_ulang_memakai_rute_murid(dua, jam):
    pesan_dan_tagihan(dua, dua.a)
    jam.maju_jam(pesanan_dasar.KEDALUWARSA_JAM + 1)
    kode, isi, _ = minta_mentah(dua, M, dua.a.akun)
    assert 'action="/murid/pesanan/tagihan/ulang"' in isi
    assert post(dua, M + "/tagihan/ulang", dua.a, teks.AKSI_ULANG)[0] == 303
    with ledger() as kon:   # jendela baru dibuka untuk order yang sama (id tetap)
        assert kon.execute("SELECT COUNT(*) FROM pesanan_order").fetchone()[0] == 1
        assert kon.execute("SELECT MAX(urutan) FROM pesanan_jendela").fetchone()[0] == 2


def test_satu_pesanan_menunggu_per_akun_tetap_berlaku(dua):
    """Akun A sudah punya pesanan LAIN yang menunggu verifikasi: tagihan/bukti order barunya ditolak."""
    with ledger() as kon:
        lain = pesanan.buat_order(kon, akun_id=dua.a.id_akun, siswa_id=9999, cek_id=9999,
                                  cek_selesai=True, punya_kontak=True, sekarang=WAKTU_AWAL,
                                  merchant="M_SINTETIS")
        pesanan_transfer.buat_tagihan_transfer(kon, lain["order_id"], dua.a.id_akun, WAKTU_AWAL)
        pesanan_transfer.catat_bukti(kon, lain["order_id"], dua.a.id_akun, "image/jpeg", 10,
                                     "ab" * 32, "cd" * 16, WAKTU_AWAL)
    assert pesan_murid(dua, dua.a)[0] == 303
    sebelum = keadaan_ledger()
    assert tagihan_murid(dua, dua.a)[0] == 409           # tagihan baru ditolak selama ada yang menunggu
    tok = token(dua.a.akun, "bukti")
    assert minta_multipart(dua, M + "/bukti", dua.a.akun, bukti(tok, PDF))[0] == 409
    assert keadaan_ledger() == sebelum
    assert berkas_tersimpan(dua) == []


# --- isolasi antar murid ----------------------------------------------------------------------

def test_murid_b_tidak_bisa_menyentuh_pesanan_a_404_identik_tanpa_efek(dua):
    pesan_dan_tagihan(dua, dua.a)
    sebelum = keadaan_ledger()
    harap = tak_dikenal(dua, dua.b.akun)
    kode, isi, _ = tagihan_murid(dua, dua.b)       # B belum punya order sendiri
    assert (kode, isi) == (404, harap[1])
    tok = token(dua.b.akun, "bukti")
    kode_u, isi_u, _ = minta_multipart(dua, M + "/bukti", dua.b.akun, bukti(tok, JPEG))
    assert (kode_u, isi_u) == (404, harap[1])
    assert keadaan_ledger() == sebelum
    assert berkas_tersimpan(dua) == []
    # B melihat keadaan B sendiri, bukan tagihan A
    halaman_b = minta_mentah(dua, M, dua.b.akun)[1]
    assert NOMOR_LABEL not in halaman_b and NAMA_ANAK_A not in halaman_b


def test_dua_murid_memesan_masing_masing_untuk_anak_sendiri(dua):
    assert pesan_murid(dua, dua.a)[0] == 303 and pesan_murid(dua, dua.b)[0] == 303
    with ledger() as kon:
        pasangan = {tuple(r) for r in kon.execute("SELECT akun_id, siswa_id FROM pesanan_order")}
    assert pasangan == {(dua.a.id_akun, dua.a.siswa_id), (dua.b.id_akun, dua.b.siswa_id)}


# --- isi halaman ------------------------------------------------------------------------------

def test_wa_dan_kata_terlarang_tidak_tampil_di_halaman_murid_mana_pun(dua):
    halaman = [semua_halaman(dua, dua.a)]
    pesan_murid(dua, dua.a)
    halaman.append(semua_halaman(dua, dua.a))
    tagihan_murid(dua, dua.a)
    halaman.append(semua_halaman(dua, dua.a))
    c = buat_murid(dua, "murid-c", "Anak Murid Gamma", kontak=False)
    halaman.append(pesan_murid(dua, c)[1])
    for isi in halaman:
        assert WA_SINTETIS not in isi and "0812" not in isi and "+62" not in isi
        tampak = teks_tampak(isi).lower()
        for kata in KATA_TERLARANG:
            assert kata not in tampak, kata


def test_status_murid_memuat_teks_copy_yang_sama_dengan_guru(dua):
    pesan_dan_tagihan(dua, dua.a)
    tampak = teks_tampak(minta_mentah(dua, M, dua.a.akun)[1])
    assert pesanan_pages.COPY_STATUS_PILIH in tampak
    assert pesanan_pages.COPY_REFUND in tampak


# --- gerbang pembayaran -----------------------------------------------------------------------

def test_sakelar_hidup_gerbang_pembayaran_tertutup_halaman_jujur_dan_post_404(tertutup, sakelar_hidup):
    a = buat_murid(tertutup, "murid-a", NAMA_ANAK_A)
    kode, isi, _ = minta_mentah(tertutup, M, a.akun)
    assert kode == 200 and "Belum dibuka" in teks_tampak(isi)
    assert minta_mentah(tertutup, M + "/qr", a.akun)[:2] == tak_dikenal(tertutup, a.akun)
    harap = tak_dikenal(tertutup, a.akun)
    kode_p, isi_p, _ = pesan_murid(tertutup, a)
    assert (kode_p, isi_p) == harap
    tanpa_efek()


# --- QRIS (Midtrans) --------------------------------------------------------------------------

def test_qris_murid_gambar_qr_same_origin_dan_tombol_rute_murid(bayar, sakelar_hidup):
    a = buat_murid(bayar, "murid-a", NAMA_ANAK_A)
    assert pesan_murid(bayar, a)[0] == 303
    kode, isi, _ = minta_mentah(bayar, M, a.akun)
    assert kode == 200
    assert 'src="/murid/pesanan/qr"' in isi and 'src="/pesanan/qr"' not in isi
    assert 'action="/murid/pesanan/periksa"' in isi
    kode_qr, _png, tajuk = minta_mentah(bayar, M + "/qr", a.akun)
    assert kode_qr == 200 and tajuk.get("Content-Type") == "image/png"


def test_qris_form_asing_dan_token_salah_ditolak_tanpa_efek(bayar, sakelar_hidup):
    a = buat_murid(bayar, "murid-a", NAMA_ANAK_A)
    b = buat_murid(bayar, "murid-b", NAMA_ANAK_B)
    for ekstra in ({"rupiah": "1000"}, {"siswa_id": str(b.siswa_id)}, {"id_akun": b.id_akun}):
        assert pesan_murid(bayar, a, ekstra=ekstra)[0] == 400, ekstra
    assert pesan_murid(bayar, a, tok=token(a.akun, "periksa"))[0] == 403     # token aksi lain
    assert pesan_murid(bayar, a, tok=token(b.akun, "pesan"))[0] == 403       # token murid lain
    tanpa_efek()
    assert bayar.provider.panggilan == []
