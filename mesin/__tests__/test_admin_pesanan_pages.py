"""Renderer murni halaman admin pesanan: aksi yang tersedia, escape, tanpa hex, penanda DRAF."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_pages as pg  # noqa: E402

ORDER = "ord_" + "a" * 32


def _item(**ganti):
    dasar = {"order_id": ORDER, "akun": "akun_a1a1a1a1", "dibuat": "2026-11-18T10:00:00",
             "kedaluwarsa": "2026-11-19T10:00:00", "alasan_kode": None, "status": "belum_bayar"}
    return {**dasar, **ganti}


def _daftar(*items, total=None):
    return {"items": tuple(items), "total": len(items) if total is None else total,
            "halaman": 1, "per_halaman": 25}


@pytest.mark.parametrize("status,gerbang,harap", [
    ("belum_bayar", True, ("periksa",)),
    ("kedaluwarsa", True, ("periksa",)),
    ("belum_bayar", False, ()),
    ("kedaluwarsa", False, ()),
    ("sudah_dibayar", True, ("refund",)),
    ("sudah_dibayar", False, ("refund",)),
    ("perlu_diperiksa", False, ("refund",)),
    ("direfund", True, ()),
])
def test_aksi_tersedia_menurut_status_dan_gerbang(status, gerbang, harap):
    assert pg.aksi_tersedia(_item(status=status), gerbang) == harap


def _render(*items, **ganti):
    argumen = {"halaman": 1, "gerbang_terbuka": False, "hasil": None, **ganti}
    return pg.halaman(_daftar(*items), **argumen)


def test_halaman_escape_semua_nilai_dinamis():
    item = _item(order_id="ord_<script>alert(1)</script>", akun='akun_"><b>', alasan_kode="<img src=x>")
    isi = _render(item, gerbang_terbuka=True)
    assert "<script>alert" not in isi and "<img src=x>" not in isi and "<b>" not in isi
    assert "&lt;script&gt;" in isi


def test_halaman_daftar_tanpa_form_dan_tanpa_kolom_sandi():
    # Regresi Fase C: tidak ada form/kolom sandi per baris, apa pun statusnya.
    semua = [_item(status=s) for s in pg.COPY_STATUS]
    isi = _render(*semua, gerbang_terbuka=True)
    assert "<form" not in isi and 'type="password"' not in isi and 'name="reauth"' not in isi
    assert pg.RUTE_PERIKSA not in isi and pg.RUTE_REFUND not in isi


def test_kolom_tabel_sesuai_rancangan_fase_c():
    isi = _render(_item())
    kepala = re.findall(r'<th scope="col">([^<]+)</th>', isi)
    assert kepala == ["Order", "Akun", "Nominal", "Dibayar / diunggah", "Status", "Laporan", "Aksi"]


def test_halaman_umpan_balik_hanya_dari_kode_dikenal():
    isi = _render(hasil="refund_dicatat")
    assert pg.COPY_HASIL["refund_dicatat"] in isi
    assert _render().count("role=\"status\"") == 0
    assert _render(hasil="sembarang").count("role=\"status\"") == 0


def test_tidak_ada_hex_warna_di_renderer():
    for nama in ("admin_pesanan_pages.py", "admin_pesanan_detail_pages.py"):
        sumber = (Path(__file__).resolve().parent.parent / nama).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber), nama


def test_tidak_ada_penanda_draf_di_sumber_renderer():
    for nama in ("admin_pesanan_pages.py", "admin_pesanan_detail_pages.py"):
        sumber = (Path(__file__).resolve().parent.parent / nama).read_text(encoding="utf-8")
        assert not re.search(r"\bDRAF\b|menunggu persetujuan Pemilik", sumber), nama


def test_halaman_terender_tanpa_penanda_draf():
    isi = _render(_item(), gerbang_terbuka=True, hasil="refund_dicatat")
    assert "draf" not in isi.lower() and "draf" not in pg.halaman_tidak_siap().lower()


def _item_transfer(**ganti):
    return _item(status="menunggu_verifikasi", **ganti)


RINGKAS = {ORDER: {"nominal": 49321, "jumlah_bukti": 2, "diunggah": "2026-11-18T12:30:00"}}


def test_baris_transfer_memuat_nominal_persis_waktu_unggah_dan_tautan_periksa_bukti():
    isi = _render(_item_transfer(), transfer=RINGKAS)
    assert "Rp49.321" in isi and "18 Nov 2026, 19.30 WIB" in isi
    assert "Menunggu verifikasi" in isi
    assert 'href="/admin/pesanan/verifikasi?order=%s"' % ORDER in isi and pg.COPY_PERIKSA_BUKTI in isi
    assert pg.RUTE_ORDER not in isi


@pytest.mark.parametrize("status", [s for s in pg.COPY_STATUS if s != "menunggu_verifikasi"])
def test_baris_selain_menunggu_hanya_punya_tautan_detail_ke_halaman_order(status):
    isi = _render(_item(status=status), transfer=RINGKAS)
    assert 'href="%s?id=%s"' % (pg.RUTE_ORDER, ORDER) in isi and ">%s<" % pg.COPY_DETAIL in isi
    assert pg.COPY_PERIKSA_BUKTI not in isi and "/verifikasi?" not in isi


def test_satu_aksi_per_baris():
    isi = _render(_item_transfer(), _item(order_id="ord_" + "b" * 32, status="sudah_dibayar"))
    baris = re.findall(r"<tr>.*?</tr>", isi, re.S)[1:]
    assert len(baris) == 2 and all(len(re.findall(r"<a ", b)) == 1 for b in baris)


def test_nominal_dan_unggah_kosong_tanpa_data_transfer():
    isi = _render(_item(), transfer={ORDER: {"nominal": None, "jumlah_bukti": 0, "diunggah": None}})
    assert "Rp" not in isi and "<td>—</td><td>—</td>" in isi


@pytest.mark.parametrize("kode,harap", [
    ("nominal", "Nominal tidak sesuai"), ("merchant", "Penjual tidak sesuai"),
    ("mata_uang", "Mata uang tidak sesuai"), ("kanal", "Cara bayar tidak sesuai"),
    ("refund", "Ada pengembalian dana di penyedia"), ("ok", "Pembayaran sesuai"), ("lainnya", "Lainnya"),
    ("kode_baru_tak_dikenal", "Lainnya"),
])
def test_alasan_receipt_berlabel_manusiawi_dan_kode_mentah_tidak_tampil(kode, harap):
    isi = _render(_item(status="perlu_diperiksa", alasan_kode=kode))
    assert harap in isi
    assert ">%s<" % kode not in isi


def test_tanpa_alasan_tidak_ada_label_alasan():
    isi = _render(_item(alasan_kode=None))
    assert "Lainnya" not in isi


def test_peta_alasan_menutup_semua_kode_skema():
    from schema_pesanan import ALASAN_KODE
    assert set(ALASAN_KODE) <= set(pg.COPY_ALASAN)


def test_chip_saringan_lima_dengan_hitungan_dan_penanda_aktif():
    hitungan = {"menunggu": 2, "belum_bayar": 3, "dibayar": 4, "ditolak": 5, "semua": 14}
    isi = _render(_item_transfer(), saring="dibayar", hitungan=hitungan)
    chips = re.findall(r'<a class="admin-chip"( aria-current="true")? href="([^"]*)">([^<]+)<span class="admin-cnt">(\d+)</span></a>', isi)
    assert [(c[1], c[2], c[3]) for c in chips] == [
        ("/admin/pesanan?status=menunggu", "Menunggu verifikasi", "2"),
        ("/admin/pesanan?status=belum_bayar", "Belum bayar", "3"),
        ("/admin/pesanan?status=dibayar", "Dibayar", "4"),
        ("/admin/pesanan?status=ditolak", "Ditolak / kedaluwarsa", "5"),
        ("/admin/pesanan", "Semua", "14")]
    assert [c[2] for c in chips if c[0]] == ["Dibayar"]


def test_chip_tanpa_hitungan_tidak_menampilkan_angka_dan_semua_aktif_secara_bawaan():
    isi = _render(_item())
    assert "admin-cnt" not in isi
    assert re.search(r'<a class="admin-chip" aria-current="true" href="/admin/pesanan">Semua</a>', isi)


def test_kode_saringan_diizinkan_sesuai_chip_dan_kelompok_domain():
    import pesanan_admin
    assert pg.KODE_SARING == frozenset(pesanan_admin.KELOMPOK_STATUS)
    assert pg.SARING_MENUNGGU in pg.KODE_SARING


def test_pager_mempertahankan_filter():
    daftar = _daftar(_item_transfer(), total=60)
    isi = pg.halaman(daftar, halaman=2, gerbang_terbuka=False, hasil=None, saring="menunggu")
    pager = isi.split("admin-pager")[1]
    assert "status=menunggu&amp;halaman=1" in pager or "halaman=1&amp;status=menunggu" in pager
    semua = pg.halaman(daftar, halaman=2, gerbang_terbuka=False, hasil=None)
    assert "status=" not in semua.split("admin-pager")[1]


@pytest.mark.parametrize("saring", sorted(pg.KODE_SARING))
def test_kosong_tiap_saringan_memakai_pesan_sendiri(saring):
    isi = _render(saring=saring)
    assert pg.COPY_KOSONG_SARING[saring] in isi and pg.COPY_KOSONG not in isi


def test_kosong_semua_memakai_pesan_umum():
    assert pg.COPY_KOSONG in _render()


def test_strip_layanan_satu_baris_dengan_tautan_pengaturan_dan_tanpa_form():
    buka = _render(gerbang_terbuka=True, rekening_terisi=True)
    assert pg.COPY_GERBANG_BUKA in buka and pg.COPY_REKENING_TERISI in buka
    assert 'href="/admin/sakelar#rekening"' in buka and pg.COPY_ATUR_LAYANAN in buka
    tutup = _render(gerbang_terbuka=False, rekening_terisi=False)
    assert pg.COPY_GERBANG_TUTUP in tutup and pg.COPY_REKENING_KOSONG in tutup
    assert pg.COPY_REKENING_TERISI not in _render(rekening_terisi=None)


def test_kode_hasil_verifikasi_dikenal_dan_label_status_baru_ada():
    assert {"verifikasi_setuju", "verifikasi_tolak"} <= pg.KODE_HASIL
    assert pg.COPY_STATUS["menunggu_verifikasi"] and pg.COPY_STATUS["ditolak"]


def test_kode_hasil_detail_hanya_aksi_detail_order():
    assert pg.KODE_HASIL_DETAIL == {"periksa_ok", "periksa_dilewati", "periksa_gagal", "gerbang_tertutup",
                                    "refund_dicatat", "refund_sudah_ada", "voucher_dicatat", "voucher_sudah_ada"}


def test_penanda_dua_jalur_dan_menunggu_lama_tampil_di_sel_status():
    isi = _render(_item(status="perlu_diperiksa", dua_jalur=True),
                  _item(order_id="ord_" + "b" * 32, status="menunggu_verifikasi", menunggu_lama=True))
    assert isi.count("admin-badge perhatian") >= 2
    assert pg.e(pg.COPY_DUA_JALUR) in isi and pg.e(pg.COPY_MENUNGGU_LAMA) in isi


def test_tanpa_penanda_bila_kunci_tidak_ada_atau_salah():
    isi = _render(_item(), _item(order_id="ord_" + "b" * 32, dua_jalur=False, menunggu_lama=False))
    assert pg.e(pg.COPY_DUA_JALUR) not in isi and pg.e(pg.COPY_MENUNGGU_LAMA) not in isi
