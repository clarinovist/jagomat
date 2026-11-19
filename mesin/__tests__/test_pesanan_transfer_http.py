"""HTTP transfer rekening (tahap 2) bagian gerbang, pesan, tagihan, dan halaman /pesanan.

Server loopback + runtime/provider PALSU, data sintetis di tmp_path. Unggah bukti ada di
test_pesanan_transfer_bukti_http.py. Gerbang transfer terpisah dari Midtrans: transfer-only
berarti provider TIDAK pernah dipanggil.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pesanan_pages  # noqa: E402
import pesanan_rekening  # noqa: E402
from cek_http_kit import HASIL  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    ATAS_NAMA, AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, BANK, NAMA_A, NOMOR_LABEL, PESAN, POLA_NOMINAL,
    QR, STATUS, TAGIHAN, atur_tahap, bayar, berkas_tersimpan, dua_jalur, hitung, jam, keadaan_ledger,
    form_mentah, jumlah_respons, keluarga, kirim, kirim_tagihan, ledger, minta_mentah, pesan, server,
    siap_order, siap_pesan, siap_tagihan, teks_tampak, tertutup, token, transfer,
)


def _acuan(server, *, post):
    kode, isi, _t = (minta_mentah(server, "/rute-tidak-ada", AKUN_A, {"x": "1"}) if post
                     else minta_mentah(server, "/rute-tidak-ada", AKUN_A))
    assert kode == 404
    return kode, isi


def _tanpa_efek_transfer(server):
    assert hitung("transfer_tagihan") == 0 and hitung("transfer_bukti") == 0
    assert berkas_tersimpan(server) == []
    assert server.provider.panggilan == []


# --- gerbang transfer ----------------------------------------------------------

def _tutup(server, monkeypatch, cara):
    if cara == "env-hilang":
        monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    elif cara in ("0", " 1", "true", "01", ""):
        monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", cara)
    elif cara == "funnel":
        monkeypatch.setenv("FUNNEL_AKTIF", "0")
    elif cara == "runtime":
        server.server.pembayaran_runtime = None
    elif cara == "rekening":
        monkeypatch.setattr(pesanan_rekening, "baca_publik", lambda path=None: None)
    elif cara == "rekening-galat":
        def _gagal(path=None):
            raise RuntimeError("db rusak")
        monkeypatch.setattr(pesanan_rekening, "baca_publik", _gagal)
    else:
        raise AssertionError(cara)


CARA_TUTUP = ["env-hilang", "0", " 1", "true", "01", "", "funnel", "runtime", "rekening", "rekening-galat"]


@pytest.mark.parametrize("cara", CARA_TUTUP)
def test_satu_syarat_hilang_semua_tertutup_fail_closed(transfer, monkeypatch, cara):
    siap_order(transfer)
    _tutup(transfer, monkeypatch, cara)
    acuan_post = _acuan(transfer, post=True)
    for jalur, aksi in ((TAGIHAN, "tagihan"), ("/pesanan/bukti", "bukti")):
        kode, isi, _t = minta_mentah(transfer, jalur, AKUN_A, {"token": token(AKUN_A, aksi)})
        assert (kode, isi) == acuan_post
    kode, isi, _t = minta_mentah(transfer, STATUS, AKUN_A)
    assert kode == 200 and pesanan_pages.COPY_TUTUP in isi.replace("&#x27;", "'")
    assert "<form" not in isi.split("</header>", 1)[1]
    assert minta_mentah(transfer, QR, AKUN_A)[:2] == _acuan(transfer, post=False)
    _tanpa_efek_transfer(transfer)


def test_transfer_terbuka_tidak_membuka_midtrans_qr_404_provider_tak_dipanggil(transfer):
    siap_order(transfer)
    assert minta_mentah(transfer, QR, AKUN_A)[:2] == _acuan(transfer, post=False)
    for jalur in ("/pesanan/periksa", "/pesanan/ulang", "/pesanan/buat"):
        acuan = _acuan(transfer, post=True)
        kode, isi, _t = minta_mentah(transfer, jalur, AKUN_A, {"token": token(AKUN_A, jalur.split("/")[-1])})
        assert (kode, isi) == acuan
    assert transfer.provider.panggilan == []


def test_midtrans_saja_tanpa_sakelar_transfer_halaman_lama_tanpa_blok_transfer(bayar):
    siap_pesan(bayar)
    assert pesan(bayar)[0] == 303
    kode, isi, _t = minta_mentah(bayar, STATUS, AKUN_A)
    assert kode == 200 and "Pindai kode QRIS" in isi and "Bayar lewat transfer" not in isi
    acuan = _acuan(bayar, post=True)
    assert minta_mentah(bayar, TAGIHAN, AKUN_A, {"token": token(AKUN_A, "tagihan")})[:2] == acuan


# --- order lewat gerbang transfer ---------------------------------------------------

def test_cta_pesan_muncul_di_hasil_cek_saat_hanya_transfer_terbuka(transfer):
    siap_pesan(transfer)
    kode, isi, _t = minta_mentah(transfer, HASIL, AKUN_A)
    assert kode == 200 and 'action="/paket-coba/pesan"' in isi


def test_get_pesan_transfer_saja_redirect_ke_status(transfer):
    siap_pesan(transfer)
    kode, _i, tajuk = minta_mentah(transfer, PESAN, AKUN_A)
    assert (kode, tajuk["Location"]) == (303, STATUS)


def test_pesan_transfer_saja_membuat_satu_order_tanpa_panggilan_provider(transfer):
    siap_pesan(transfer)
    kode, _i, tajuk = pesan(transfer)
    assert (kode, tajuk["Location"]) == (303, STATUS)
    assert keadaan_ledger()["pesanan_order"] == 1 and keadaan_ledger()["pesanan_pengamatan"] == 0
    assert pesan(transfer)[0] == 303 and keadaan_ledger()["pesanan_order"] == 1
    assert transfer.provider.panggilan == []


def test_pesan_transfer_saja_csrf_salah_403_tanpa_order(transfer):
    siap_pesan(transfer)
    assert pesan(transfer, tok="1.salah")[0] == 403
    assert keadaan_ledger() == {t: 0 for t in keadaan_ledger()}


# --- halaman /pesanan ----------------------------------------------------------------

def test_transfer_saja_halaman_hanya_transfer_tanpa_qris(transfer):
    siap_order(transfer)
    kode, isi, tajuk = minta_mentah(transfer, STATUS, AKUN_A)
    teks = teks_tampak(isi)
    assert kode == 200 and "no-store" in tajuk.get("Cache-Control", "")
    assert "Bayar lewat transfer" in teks and 'action="/pesanan/tagihan"' in isi
    assert "/pesanan/qr" not in isi and "QRIS" not in isi and "Kode QR belum" not in isi
    assert 'action="/pesanan/buat"' not in isi and 'action="/pesanan/periksa"' not in isi
    assert BANK not in isi and NOMOR_LABEL not in isi and ATAS_NAMA not in isi      # setelah tagihan
    assert NAMA_A in isi
    assert transfer.provider.panggilan == []


def test_tagihan_dibuat_nominal_persis_rekening_dan_batas_waktu_tampil(transfer):
    siap_order(transfer)
    kode, _i, tajuk = kirim_tagihan(transfer)
    assert (kode, tajuk["Location"]) == (303, STATUS)
    with ledger() as kon:
        baris = kon.execute("SELECT kode_unik,nominal_transfer FROM transfer_tagihan").fetchall()
    assert len(baris) == 1 and baris[0][1] == 49000 + baris[0][0] and 1 <= baris[0][0] <= 999
    kode, isi, _t = minta_mentah(transfer, STATUS, AKUN_A)
    teks = teks_tampak(isi)
    assert "Rp%s" % format(baris[0][1], ",").replace(",", ".") in teks
    assert BANK in teks and NOMOR_LABEL in teks and ATAS_NAMA in teks
    assert "19 November 2026 pukul 17.00 WIB" in teks and "persis" in teks.lower()
    assert 'action="/pesanan/bukti"' in isi and 'action="/pesanan/tagihan"' not in isi
    assert len(POLA_NOMINAL.findall(teks)) >= 1
    assert transfer.provider.panggilan == []


def test_tagihan_idempoten_post_kedua_tidak_menambah_dan_nominal_sama(transfer):
    siap_order(transfer)
    kirim_tagihan(transfer)
    with ledger() as kon:
        pertama = kon.execute("SELECT nominal_transfer FROM transfer_tagihan").fetchall()
    assert kirim_tagihan(transfer)[0] == 303
    with ledger() as kon:
        assert kon.execute("SELECT nominal_transfer FROM transfer_tagihan").fetchall() == pertama


def test_tagihan_tanpa_order_404_identik_tanpa_efek(transfer):
    siap_pesan(transfer)
    acuan = _acuan(transfer, post=True)
    kode, isi, _t = kirim_tagihan(transfer)
    assert (kode, isi) == acuan
    _tanpa_efek_transfer(transfer)


def test_tagihan_order_akun_lain_tidak_bisa_dipakai_404_tanpa_efek(transfer):
    siap_order(transfer, AKUN_A)
    siap_pesan(transfer, AKUN_B)
    acuan = _acuan(transfer, post=True)
    kode, isi, _t = kirim_tagihan(transfer, AKUN_B)
    assert (kode, isi) == acuan
    assert hitung("transfer_tagihan") == 0


@pytest.mark.parametrize("tok", ["", "1.salah", "bukan-token"])
def test_tagihan_csrf_salah_403_tanpa_efek(transfer, tok):
    siap_order(transfer)
    assert kirim_tagihan(transfer, tok=tok)[0] == 403
    _tanpa_efek_transfer(transfer)


def test_tagihan_token_aksi_lain_tidak_berlaku(transfer):
    siap_order(transfer)
    for aksi in ("pesan", "bukti", "buat", "kontak"):
        assert kirim_tagihan(transfer, tok=token(AKUN_A, aksi))[0] == 403
    assert hitung("transfer_tagihan") == 0


def test_tagihan_token_akun_lain_ditolak(transfer):
    siap_order(transfer)
    assert kirim_tagihan(transfer, tok=token(AKUN_B, "tagihan"))[0] == 403
    assert hitung("transfer_tagihan") == 0


def test_tagihan_field_asing_ditolak_400(transfer):
    siap_order(transfer)
    for ekstra in ({"order_id": "ord_x"}, {"nominal": "1"}, {"id_akun": "akun_x"}):
        assert kirim_tagihan(transfer, ekstra=ekstra)[0] == 400
    assert kirim_tagihan(transfer, hapus=("token",))[0] == 400
    assert hitung("transfer_tagihan") == 0


def test_tagihan_admin_404_identik_dan_murid_ditahan_palang(transfer):
    siap_order(transfer)
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_ADMIN, {"x": "1"})
    kode, isi, _t = minta_mentah(transfer, TAGIHAN, AKUN_ADMIN, {"token": "1.abc"})
    assert (kode, isi) == acuan[:2] and kode == 404
    assert minta_mentah(transfer, TAGIHAN, None, {"token": "x"})[0] == 401
    assert minta_mentah(transfer, TAGIHAN, AKUN_MURID, {"token": "x"})[0] == 401
    assert hitung("transfer_tagihan") == 0


def test_get_pada_rute_tagihan_tidak_dikenal(transfer):
    siap_order(transfer)
    assert minta_mentah(transfer, TAGIHAN, AKUN_A)[:2] == _acuan(transfer, post=False)


def test_pesan_dua_akun_tidak_saling_lihat_tagihan(transfer):
    siap_tagihan(transfer, AKUN_A)
    siap_pesan(transfer, AKUN_B)
    assert pesan(transfer, AKUN_B)[0] == 303
    kode, isi, _t = minta_mentah(transfer, STATUS, AKUN_B)
    assert kode == 200 and 'action="/pesanan/tagihan"' in isi and BANK not in isi


def test_kuota_kode_unik_habis_pesan_ramah_tanpa_efek(transfer, monkeypatch):
    import pesanan_transfer
    siap_order(transfer)
    def _habis(*_a, **_k):
        raise pesanan_transfer.PesananKodeUnikHabis()
    monkeypatch.setattr(pesanan_transfer, "buat_tagihan_transfer", _habis)
    kode, isi, _t = kirim_tagihan(transfer)
    assert kode == 409 and "dibuat" in isi.lower()
    assert "kode unik" not in isi.lower()
    assert hitung("transfer_tagihan") == 0


def test_jendela_lewat_tagihan_baru_ditolak_ramah(transfer, jam):
    siap_order(transfer)
    jam.maju_jam(25)
    kode, isi, _t = kirim_tagihan(transfer)
    assert kode == 409 and hitung("transfer_tagihan") == 0


# --- dua jalur -----------------------------------------------------------------------

def test_dua_jalur_transfer_dulu_qris_pilihan_kedua(dua_jalur):
    siap_pesan(dua_jalur)
    assert pesan(dua_jalur)[0] == 303
    assert dua_jalur.provider.jumlah_create == 1
    kode, isi, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert kode == 200 and 'src="/pesanan/qr"' in isi
    assert isi.index("Bayar lewat transfer") < isi.index('src="/pesanan/qr"')
    assert "Pilihan kedua" in isi


def test_dua_jalur_tagihan_tetap_jalan_dan_qris_tetap_tampil(dua_jalur):
    siap_pesan(dua_jalur)
    pesan(dua_jalur)
    assert kirim_tagihan(dua_jalur)[0] == 303
    kode, isi, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert BANK in isi and 'src="/pesanan/qr"' in isi


def test_tahap_checkout_dicabut_qris_hilang_transfer_tetap(dua_jalur):
    siap_pesan(dua_jalur)
    pesan(dua_jalur)
    atur_tahap("nonaktif")
    kode, isi, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert kode == 200 and "/pesanan/qr" not in isi and "Bayar lewat transfer" in isi


# --- setiap permintaan dijawab TEPAT satu kali (bukan 404 lalu 303 pada soket yang sama) ----------

def _satu_respons(mentah, kode):
    assert jumlah_respons(mentah) == 1, mentah[:400]
    assert mentah.startswith(b"HTTP/1.0 %d" % kode) or mentah.startswith(b"HTTP/1.1 %d" % kode), mentah[:60]


def test_tagihan_tanpa_order_dijawab_sekali_404_tanpa_location(transfer):
    siap_pesan(transfer)
    mentah = form_mentah(transfer, TAGIHAN, AKUN_A, {"token": token(AKUN_A, "tagihan")})
    _satu_respons(mentah, 404)
    assert b"Location:" not in mentah


def test_tagihan_akun_lain_tanpa_order_dijawab_sekali_404(transfer):
    siap_order(transfer, AKUN_A)
    siap_pesan(transfer, AKUN_B)
    mentah = form_mentah(transfer, TAGIHAN, AKUN_B, {"token": token(AKUN_B, "tagihan")})
    _satu_respons(mentah, 404)
    assert b"Location:" not in mentah


def test_jalur_sukses_dan_penolakan_lain_dijawab_sekali(transfer):
    siap_pesan(transfer)
    _satu_respons(form_mentah(transfer, PESAN, AKUN_A, {"token": token(AKUN_A, "pesan")}), 303)
    _satu_respons(form_mentah(transfer, TAGIHAN, AKUN_A, {"token": token(AKUN_A, "tagihan")}), 303)
    _satu_respons(form_mentah(transfer, TAGIHAN, AKUN_A, {"token": "1.salah"}), 403)
    _satu_respons(form_mentah(transfer, TAGIHAN, AKUN_A, {"x": "1"}), 400)
    _satu_respons(form_mentah(transfer, TAGIHAN, AKUN_ADMIN, {"token": "1.abc"}), 404)
    _satu_respons(form_mentah(transfer, TAGIHAN, AKUN_MURID, {"token": "1.abc"}), 401)
    _satu_respons(form_mentah(transfer, TAGIHAN, None, {"token": "1.abc"}), 401)


def test_gerbang_tertutup_jatuh_ke_404_sekali(transfer, monkeypatch):
    siap_order(transfer)
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    for jalur, aksi in ((TAGIHAN, "tagihan"), ("/pesanan/bukti", "bukti")):
        mentah = form_mentah(transfer, jalur, AKUN_A, {"token": token(AKUN_A, aksi)})
        _satu_respons(mentah, 404)


def test_pesan_tanpa_cek_dijawab_sekali(transfer):
    mentah = form_mentah(transfer, PESAN, AKUN_A, {"token": token(AKUN_A, "pesan")})
    _satu_respons(mentah, 409)
