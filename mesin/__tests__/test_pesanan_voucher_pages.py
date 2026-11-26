"""Renderer kartu "Deposit dan laporan": murni, tanpa DB. Isi, status, tanpa tombol, dan batas data."""
from __future__ import annotations

import re
from dataclasses import replace

import pesanan_dasar
import pesanan_voucher_pages as hv
import purna
from pesanan_murid_kit import KEADAAN_TERLAMBAT as DASAR
from pesanan_transfer_pages import rupiah, waktu_wib


def test_judul_dan_baris_deposit_memakai_nominal_dari_rupiah_paket():
    isi = hv.kartu_voucher(DASAR)
    assert "<h2>Potongan dan laporan</h2>" in isi
    assert "Potongan " + rupiah(pesanan_dasar.RUPIAH_PAKET) in isi and "Potongan Rp49.000" in isi


def test_baris_potongan_dan_berlaku_hingga_dalam_wib():
    isi = hv.kartu_voucher(DASAR)
    assert "Memotong tagihan bulan pertama kelas bersama Guru bila Anda mendaftar." in isi
    assert "otomatis" not in isi.lower()
    assert "Berlaku hingga " + waktu_wib(DASAR.berlaku_hingga) in isi


def test_kamus_status_total_untuk_semua_status_dan_ditahan_punya_kalimat_awam():
    semua = {nilai for nama, nilai in vars(purna).items() if nama.startswith("VOUCHER_")}
    assert semua == set(hv.COPY_STATUS_VOUCHER)
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_DITAHAN] == "Potongan ditahan sampai pembayaran selesai diperiksa tim."


def test_status_deposit_aktif_terpakai_kedaluwarsa_ditahan_batal_tampil_di_kartu():
    harapan = {
        purna.VOUCHER_AKTIF: "Potongan aktif.",
        purna.VOUCHER_DIPAKAI: "Potongan sudah terpakai.",
        purna.VOUCHER_KEDALUWARSA: "Potongan sudah kedaluwarsa.",
        purna.VOUCHER_DITAHAN: "Potongan ditahan sampai pembayaran selesai diperiksa tim.",
    }
    for status, kalimat in harapan.items():
        assert kalimat in hv.kartu_voucher(replace(DASAR, voucher=status))
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_BATAL] in hv.kartu_voucher(replace(DASAR, voucher=purna.VOUCHER_BATAL))


def test_kartu_menampilkan_janji_terbit_dan_kalimat_terlambat_bila_terlambat():
    isi = hv.kartu_voucher(DASAR)
    # Terlambat menggantikan janji (bukan menumpuk): janji "langsung terbit" lalu "belum terbit" saling bertentangan.
    assert "Laporan langsung terbit setelah pembayaran terverifikasi." not in isi and "paling lambat" not in isi
    assert "Laporan belum terbit. Hubungi tim lewat WhatsApp; kami bantu sampai laporan Anda terbit." in isi
    assert "WhatsApp" in isi


def test_laporan_terbit_tanpa_penjelasan_terlambat():
    isi = hv.kartu_voucher(replace(DASAR, terbit="2026-11-21T10:00:00", terlambat=False))
    assert hv.COPY_TERBIT in isi and hv.COPY_TERLAMBAT not in isi and hv.COPY_JANJI not in isi


def test_belum_terlambat_tanpa_penjelasan():
    isi = hv.kartu_voucher(replace(DASAR, terlambat=False))
    assert hv.COPY_TERLAMBAT not in isi and hv.COPY_JANJI in isi


def test_kartu_tanpa_tombol_form_atau_pilihan_apa_pun():
    for k in (DASAR, replace(DASAR, voucher=purna.VOUCHER_DITAHAN, ditahan=True),
              replace(DASAR, voucher=purna.VOUCHER_BATAL, direfund=True)):
        isi = hv.kartu_voucher(k).lower()
        for kata in ("<form", "<button", "<input"):
            assert kata not in isi, kata
        tampak = re.sub(r"<[^>]+>", " ", isi)
        for kata in ("pilihan", "uang kembali", "yakin", "voucher"):
            assert kata not in tampak, kata


def test_kode_voucher_internal_tidak_ditampilkan_ke_pembeli():
    isi = hv.kartu_voucher(DASAR)
    assert DASAR.kode not in isi and "JGV-" not in isi and "<code" not in isi


def test_tanpa_rute_atau_token_di_antarmuka_renderer():
    assert not hasattr(hv, "tombol_tampil") and not hasattr(hv, "COPY_YAKIN")
    assert not hasattr(hv, "COPY_YAKIN_WAJIB") and not hasattr(hv, "COPY_KEMBALI_STATUS")


def test_kartu_tanpa_kontak_dan_id_internal():
    isi = hv.kartu_voucher(DASAR).lower()
    for kata in ("tel:", "wa.me", "operasi", "ord_", "kunci", "diagnos", "malrule"):
        assert kata not in isi
