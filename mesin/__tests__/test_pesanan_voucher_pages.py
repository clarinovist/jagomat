"""Renderer kartu "Voucher dan laporan" (V4a): murni, tanpa DB. Syarat tombol, isi, dan batas data."""
from __future__ import annotations

import re
from dataclasses import replace

import pesanan_permukaan as permukaan
import pesanan_voucher_pages as hv
import purna
from pesanan_murid_kit import KEADAAN_TERLAMBAT as DASAR
from pesanan_transfer_pages import waktu_wib

TOMBOL = re.compile(r'<button type="submit" name="pilihan" value="(\w+)"')
TOKEN = "123.abc"


def tombol(k, rute=permukaan.RUTE_MURID, token=TOKEN):
    return TOMBOL.findall(hv.kartu_voucher(k, rute, token))


def _form(isi, pilihan):
    """Isi <form> yang memuat tombol dengan nilai pilihan tertentu (form terpisah per pilihan)."""
    for bagian in re.findall(r"<form.*?</form>", isi, re.S):
        if f'name="pilihan" value="{pilihan}"' in bagian:
            return bagian
    return None


def test_dua_tombol_bila_bisa_pilih_dan_belum_memilih():
    assert tombol(DASAR) == ["menunggu", "uang_kembali"]


def test_form_menunggu_dan_uang_kembali_terpisah_dan_hanya_uang_kembali_punya_kotak_yakin():
    isi = hv.kartu_voucher(DASAR, permukaan.RUTE_MURID, TOKEN)
    assert isi.count("<form") == 2
    menunggu, kembali = _form(isi, "menunggu"), _form(isi, "uang_kembali")
    assert menunggu != kembali and 'name="pilihan" value="uang_kembali"' not in menunggu
    assert "yakin" not in menunggu
    assert '<input type="checkbox" name="yakin" value="1" required>' in kembali
    assert hv.COPY_YAKIN in kembali
    for bagian in (menunggu, kembali):
        assert 'action="/murid/pesanan/pilih"' in bagian and f'name="token" value="{TOKEN}"' in bagian


def test_teks_yakin_menyebut_final_dan_voucher_tidak_berlaku():
    assert hv.COPY_YAKIN == "Saya yakin meminta uang kembali. Pilihan ini final dan voucher tidak berlaku lagi."


def test_kamus_status_voucher_total_untuk_semua_status_dan_ditahan_punya_kalimat_awam():
    semua = {nilai for nama, nilai in vars(purna).items() if nama.startswith("VOUCHER_")}
    assert semua == set(hv.COPY_STATUS_VOUCHER)
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_DITAHAN] == "Voucher ditahan sampai pembayaran selesai diperiksa tim."


def test_kartu_menampilkan_kalimat_ditahan_tanpa_tombol_bila_tidak_bisa_pilih():
    k = replace(DASAR, voucher=purna.VOUCHER_DITAHAN, ditahan=True, bisa_pilih=False)
    isi = hv.kartu_voucher(k, permukaan.RUTE_MURID, TOKEN)
    assert hv.COPY_STATUS_VOUCHER[purna.VOUCHER_DITAHAN] in isi and "<button" not in isi


def test_satu_tombol_uang_kembali_bila_sudah_memilih_menunggu():
    isi = hv.kartu_voucher(replace(DASAR, pilihan=purna.PILIHAN_MENUNGGU), permukaan.RUTE_MURID, TOKEN)
    assert TOMBOL.findall(isi) == ["uang_kembali"] and hv.COPY_MEMILIH_MENUNGGU in isi
    assert isi.count("<form") == 1 and 'name="yakin"' in isi


def test_tanpa_tombol_bila_uang_kembali_walau_bisa_pilih_masih_true():
    k = replace(DASAR, pilihan=purna.PILIHAN_UANG_KEMBALI, voucher=purna.VOUCHER_BATAL)
    isi = hv.kartu_voucher(k, permukaan.RUTE_MURID, TOKEN)
    assert k.bisa_pilih and "<form" not in isi and "<button" not in isi
    assert hv.COPY_UANG_KEMBALI_DICATAT in isi


def test_tanpa_tombol_bila_tidak_bisa_pilih():
    assert tombol(replace(DASAR, bisa_pilih=False)) == []


def test_tanpa_tombol_untuk_permukaan_guru_tanpa_rute_pilih():
    assert permukaan.RUTE_GURU.pilih is None
    isi = hv.kartu_voucher(DASAR, permukaan.RUTE_GURU, TOKEN)
    assert "<form" not in isi and "<button" not in isi and "pilihan" not in isi
    assert not hv.tombol_tampil(DASAR, permukaan.RUTE_GURU)


def test_tanpa_tombol_tanpa_token():
    assert hv.kartu_voucher(DASAR, permukaan.RUTE_MURID, None).count("<button") == 0


def test_form_menunjuk_rute_pilih_murid_dengan_token_tersembunyi():
    isi = hv.kartu_voucher(DASAR, permukaan.RUTE_MURID, TOKEN)
    assert 'action="/murid/pesanan/pilih"' in isi and f'name="token" value="{TOKEN}"' in isi


def test_isi_kode_tenggat_dan_janji_dalam_wib():
    isi = hv.kartu_voucher(DASAR, permukaan.RUTE_MURID, None)
    assert "JGV-ABCDEF123456" in isi
    assert "Berlaku hingga " + waktu_wib(DASAR.berlaku_hingga) in isi
    assert hv.COPY_JANJI + waktu_wib(DASAR.janji_terbit) in isi and hv.COPY_TERLAMBAT in isi


def test_laporan_terbit_tanpa_penjelasan_terlambat():
    isi = hv.kartu_voucher(replace(DASAR, terbit="2026-11-21T10:00:00", terlambat=False, bisa_pilih=False),
                           permukaan.RUTE_MURID, None)
    assert hv.COPY_TERBIT in isi and hv.COPY_TERLAMBAT not in isi and hv.COPY_JANJI not in isi


def test_belum_terlambat_tanpa_penjelasan_dan_tanpa_tombol():
    k = replace(DASAR, terlambat=False, bisa_pilih=False)
    isi = hv.kartu_voucher(k, permukaan.RUTE_MURID, None)
    assert hv.COPY_TERLAMBAT not in isi and "<button" not in isi


def test_kartu_tanpa_kontak_dan_id_internal():
    isi = hv.kartu_voucher(DASAR, permukaan.RUTE_MURID, TOKEN).lower()
    for kata in ("tel:", "wa.me", "operasi", "ord_", "kunci", "diagnos", "malrule"):
        assert kata not in isi
