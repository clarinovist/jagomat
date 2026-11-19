"""Panel admin verifikasi transfer lewat HTTP: tab, detail, pratinjau bukti, setujui, tolak, refund.

Server loopback + runtime/provider PALSU, data dan berkas SINTETIS. Efek (atau ketiadaannya) dibuktikan dari
ledger, bukan hanya kode status. Guard keamanan diuji lewat jalur yang sama dengan mutation di
test_admin_transfer_mutation.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import bukti_berkas  # noqa: E402
import pesanan_transfer  # noqa: E402
from admin_transfer_kit import (  # noqa: E402
    BUKTI, HALAMAN, LINTAS_SITUS, NAMA_KLIEN, SETUJUI, TAK_ADA, TOLAK, VERIFIKASI, AKSI_SETUJUI,
    AKSI_TOLAK, form_detail, id_admin, id_bukti_terakhir, kirim_putusan, login_admin, minta_admin,
    minta_biner, order_menunggu, stempel_putusan, tabel, teks_halaman, token_putusan,
)
from bukti_kit import JPEG, PDF, PNG, TEKS_PALSU  # noqa: E402
from cek_http_kit import AKUN_ADMIN  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    AKUN_A, STATUS, bayar, jam, keluarga, kirim_bukti, kirim_tagihan, ledger, minta_mentah, server,
    siap_order, siap_tagihan, tertutup, transfer,
)

ORDER_ASING = "ord_" + "0" * 32
POLA_HASIL = re.compile(r"/admin/pesanan\?halaman=\d+&hasil=([a-z_]+)")


@pytest.fixture()
def admin(transfer):
    return login_admin(transfer)


def _hasil(tajuk) -> str:
    cocok = POLA_HASIL.fullmatch(tajuk["Location"])
    assert cocok, tajuk["Location"]
    return cocok.group(1)


def _detail(server, cookie, order_id):
    kode, isi, _t = minta_admin(server, "%s?order=%s" % (VERIFIKASI, order_id), cookie)
    assert kode == 200
    return isi


def _nominal(order_id) -> int:
    with ledger() as kon:
        return kon.execute("SELECT nominal_transfer FROM transfer_tagihan WHERE order_id=?",
                           (order_id,)).fetchone()[0]


# --- daftar: kolom transfer dan tab ---------------------------------------------------------

def test_daftar_memuat_nominal_persis_jumlah_bukti_waktu_unggah_dan_status(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = minta_admin(transfer, HALAMAN, admin)[1]
    baris = [b for b in re.findall(r"<tr>.*?</tr>", isi, re.S) if order_id in b]
    assert len(baris) == 1
    teks = teks_halaman(baris[0])
    assert "Rp49.%03d" % (_nominal(order_id) - 49000) in teks
    assert "Menunggu verifikasi" in teks and "Periksa bukti" in teks
    assert "18 Nov 2026, 17.00 WIB" in teks                     # waktu unggah (10.00 UTC)
    assert 'href="%s?order=%s"' % (VERIFIKASI, order_id) in baris[0]


def test_daftar_baris_tanpa_transfer_tidak_menampilkan_nominal_atau_bukti(bayar):
    from admin_pesanan_kit import order_bayar
    order, _trx = order_bayar(bayar)
    isi = minta_admin(bayar, HALAMAN, login_admin(bayar))[1]
    baris = [b for b in re.findall(r"<tr>.*?</tr>", isi, re.S) if order["order_id"] in b][0]
    assert "Periksa bukti" not in baris and "Lihat bukti" not in baris


def test_tab_menunggu_hanya_menampilkan_order_menunggu_verifikasi(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = minta_admin(transfer, HALAMAN + "?status=menunggu", admin)[1]
    assert order_id in isi and "Menunggu verifikasi" in isi
    assert 'href="/admin/pesanan?status=menunggu"' in isi and 'href="/admin/pesanan"' in isi
    kode, _i, tajuk = kirim_putusan(transfer, admin, SETUJUI, order_id)
    assert kode == 303
    assert order_id not in minta_admin(transfer, HALAMAN + "?status=menunggu", admin)[1]
    assert order_id in minta_admin(transfer, HALAMAN, admin)[1]


def test_tab_menunggu_kosong_pesan_jujur(transfer, admin):
    isi = minta_admin(transfer, HALAMAN + "?status=menunggu", admin)[1]
    assert "Tidak ada transfer yang menunggu verifikasi" in isi


@pytest.mark.parametrize("query", ["?status=lain", "?status=", "?status=menunggu&status=menunggu",
                                   "?status=menunggu&x=1"])
def test_tab_status_tak_sah_404_identik(transfer, admin, query):
    acuan = minta_admin(transfer, TAK_ADA, admin)
    kode, isi, _t = minta_admin(transfer, HALAMAN + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


def test_daftar_label_ditolak(transfer, admin):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, TOLAK, order_id)[0] == 303
    isi = minta_admin(transfer, HALAMAN, admin)[1]
    baris = [b for b in re.findall(r"<tr>.*?</tr>", isi, re.S) if order_id in b][0]
    assert "Ditolak" in baris and "Lihat bukti" in baris


# --- detail ------------------------------------------------------------------------------

def test_detail_memuat_nominal_bukti_pratinjau_dan_dua_form_dengan_token(transfer, admin):
    order_id = order_menunggu(transfer)
    isi = _detail(transfer, admin, order_id)
    teks = teks_halaman(isi)
    assert "Rp49.%03d" % (_nominal(order_id) - 49000) in teks
    bukti_id = id_bukti_terakhir(order_id)
    assert 'src="%s?id=%d"' % (BUKTI, bukti_id) in isi
    assert 'href="%s?id=%d&amp;unduh=1"' % (BUKTI, bukti_id) in isi
    forms = form_detail(isi)
    assert set(forms) == {SETUJUI, TOLAK}
    for isian in forms.values():
        assert set(isian) == {"csrf", "tinjauan"}
    assert 'name="reauth"' in isi and 'name="alasan"' in isi and 'maxlength="200"' in isi
    assert NAMA_KLIEN not in isi                                      # nama berkas klien tak pernah tampil


def test_detail_form_dari_halaman_bekerja_ujung_ke_ujung(transfer, admin):
    from cek_http_kit import SANDI_ADMIN
    order_id = order_menunggu(transfer)
    data = {**form_detail(_detail(transfer, admin, order_id))[SETUJUI], "reauth": SANDI_ADMIN}
    kode, isi, tajuk = minta_admin(transfer, SETUJUI, admin, data)
    assert (kode, isi, _hasil(tajuk)) == (303, "", "verifikasi_setuju")
    assert "Pembayaran diterima" in minta_mentah(transfer, STATUS, AKUN_A)[1]


def test_detail_basic_auth_baca_saja_tanpa_form(transfer):
    order_id = order_menunggu(transfer)
    kode, isi, _t = minta_mentah(transfer, "%s?order=%s" % (VERIFIKASI, order_id), AKUN_ADMIN)
    assert kode == 200 and SETUJUI not in isi and TOLAK not in isi


def test_detail_order_sudah_lunas_tanpa_form_keputusan_dan_riwayat_tampil(transfer, admin):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    isi = _detail(transfer, admin, order_id)
    assert form_detail(isi) == {} and "Disetujui" in teks_halaman(isi)    # riwayat keputusan, bukan form


@pytest.mark.parametrize("order", ["", "ord_x", ORDER_ASING, "ord_" + "A" * 32, "../etc/passwd", "ord_" + "0" * 33])
def test_detail_order_tak_sah_atau_tak_ada_404_identik(transfer, admin, order):
    acuan = minta_admin(transfer, TAK_ADA, admin)
    kode, isi, _t = minta_admin(transfer, "%s?order=%s" % (VERIFIKASI, order), admin)
    assert (kode, isi) == acuan[:2] and kode == 404


@pytest.mark.parametrize("query", ["", "?order=ord_" + "0" * 32 + "&x=1", "?id=1"])
def test_detail_query_tak_dikenal_404(transfer, admin, query):
    assert minta_admin(transfer, VERIFIKASI + query, admin)[0] == 404


def test_detail_escape_alasan_penolakan(transfer, admin):
    order_id = order_menunggu(transfer)
    kirim_putusan(transfer, admin, TOLAK, order_id, ganti={"alasan": "<script>alert(1)</script>"})
    isi = _detail(transfer, admin, order_id)
    assert "<script>alert(1)" not in isi and "&lt;script&gt;alert(1)" in isi


# --- pratinjau bukti -----------------------------------------------------------------------

@pytest.mark.parametrize("isi,mime,ekstensi", [(JPEG, "image/jpeg", ".jpg"), (PNG, "image/png", ".png"),
                                               (PDF, "application/pdf", ".pdf")])
def test_pratinjau_header_aman_nama_generik_dan_isi_persis(transfer, admin, isi, mime, ekstensi):
    order_id = order_menunggu(transfer, isi)
    kode, badan, tajuk = minta_biner(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)), admin)
    assert (kode, badan) == (200, isi)
    assert tajuk["Content-Type"] == mime
    assert tajuk["X-Content-Type-Options"] == "nosniff"
    assert tajuk["Cache-Control"] == "no-store"
    assert tajuk.get_all("Content-Security-Policy") == ["default-src 'none'; sandbox"]
    disposisi = tajuk["Content-Disposition"]
    assert disposisi == 'inline; filename="bukti-transfer%s"' % ekstensi
    assert NAMA_KLIEN not in disposisi and len(tajuk.get_all("Content-Type")) == 1
    assert tajuk["Content-Length"] == str(len(isi))


def test_pratinjau_unduh_memakai_attachment(transfer, admin):
    order_id = order_menunggu(transfer)
    kode, _b, tajuk = minta_biner(transfer, "%s?id=%d&unduh=1" % (BUKTI, id_bukti_terakhir(order_id)), admin)
    assert kode == 200 and tajuk["Content-Disposition"].startswith("attachment;")


@pytest.mark.parametrize("query", [
    "", "?id=", "?id=abc", "?id=0", "?id=-1", "?id=1.5", "?id=1%20OR%201=1", "?id=%2e%2e%2f", "?id=" + "9" * 40,
    "?id=1&id=2", "?id=1&berkas=../../etc/passwd", "?id=1&unduh=2", "?berkas=" + "a" * 32,
    "?id=%EF%BC%91",
])
def test_pratinjau_id_tak_sah_404_identik_tanpa_membuka_berkas(transfer, admin, monkeypatch, query):
    order_menunggu(transfer)
    dibuka = []
    monkeypatch.setattr(bukti_berkas, "buka_berkas", lambda nama: dibuka.append(nama))
    acuan = minta_admin(transfer, TAK_ADA, admin)
    kode, isi, _t = minta_admin(transfer, BUKTI + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert dibuka == []


def test_pratinjau_id_tidak_ada_404_ramah(transfer, admin):
    order_menunggu(transfer)
    kode, isi, _t = minta_admin(transfer, "%s?id=999" % BUKTI, admin)
    assert kode == 404 and "tidak tersedia" in isi and "Traceback" not in isi


def test_pratinjau_bukti_ditandai_dihapus_404_ramah_tanpa_membuka_berkas(transfer, admin, monkeypatch):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    bukti_id = id_bukti_terakhir(order_id)
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan_transfer.tandai_dihapus(kon, bukti_id, "2027-01-01T00:00:00")
    dibuka = []
    monkeypatch.setattr(bukti_berkas, "buka_berkas", lambda nama: dibuka.append(nama))
    kode, isi, _t = minta_admin(transfer, "%s?id=%d" % (BUKTI, bukti_id), admin)
    assert kode == 404 and "tidak tersedia" in isi and dibuka == []
    assert "Dihapus" in teks_halaman(_detail(transfer, admin, order_id))


def test_pratinjau_berkas_hilang_di_cakram_404_ramah(transfer, admin):
    order_id = order_menunggu(transfer)
    (Path(transfer.folder) / tabel("transfer_bukti")[0]["berkas"]).unlink()
    kode, isi, _t = minta_admin(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)), admin)
    assert kode == 404 and "tidak tersedia" in isi


def test_pratinjau_symlink_tidak_diikuti_dan_isi_luar_tidak_bocor(transfer, admin, tmp_path):
    order_id = order_menunggu(transfer)
    luar = tmp_path / "rahasia-luar.txt"
    luar.write_bytes(b"ISI-RAHASIA-LUAR")
    berkas = Path(transfer.folder) / tabel("transfer_bukti")[0]["berkas"]
    berkas.unlink()
    berkas.symlink_to(luar)
    kode, badan, _t = minta_biner(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)), admin)
    assert kode in (404, 503) and b"ISI-RAHASIA-LUAR" not in badan


def test_pratinjau_isi_tidak_cocok_dengan_tipe_tersimpan_tidak_disajikan(transfer, admin):
    order_id = order_menunggu(transfer)
    (Path(transfer.folder) / tabel("transfer_bukti")[0]["berkas"]).write_bytes(TEKS_PALSU)
    kode, badan, tajuk = minta_biner(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)), admin)
    assert kode == 503 and TEKS_PALSU not in badan and tajuk["Content-Type"].startswith("text/html")


def test_pratinjau_basic_auth_admin_boleh_membaca(transfer):
    order_id = order_menunggu(transfer)
    kode, badan, _t = minta_biner(transfer, "%s?id=%d" % (BUKTI, id_bukti_terakhir(order_id)),
                                  akun=AKUN_ADMIN)
    assert (kode, badan) == (200, JPEG)


# --- setujui -------------------------------------------------------------------------------

def test_setujui_sukses_lunas_dicatat_oleh_admin_sesi_dan_guru_melihat_diterima(transfer, admin):
    order_id = order_menunggu(transfer)
    kode, isi, tajuk = kirim_putusan(transfer, admin, SETUJUI, order_id)
    assert (kode, isi, _hasil(tajuk)) == (303, "", "verifikasi_setuju")
    (putusan,) = tabel("transfer_verifikasi")
    assert (putusan["keputusan"], putusan["admin_id"], putusan["alasan"]) == ("setuju", id_admin(), None)
    (lunas,) = tabel("transfer_lunas")
    assert lunas["order_id"] == order_id and lunas["rupiah"] == 49000
    assert "Pembayaran diterima" in minta_mentah(transfer, STATUS, AKUN_A)[1]
    assert "Dibayar" in minta_admin(transfer, HALAMAN, admin)[1]
    assert transfer.provider.panggilan == []                            # tidak ada panggilan provider


def test_setujui_admin_id_dari_sesi_bukan_dari_form(transfer, admin):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    kode, _i, _t = kirim_putusan(transfer, admin, SETUJUI, order_id, ekstra={"admin_id": "admin_palsu_x"})
    assert kode == 400 and stempel_putusan() == sebelum
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    assert tabel("transfer_verifikasi")[0]["admin_id"] == id_admin()


def test_setujui_dua_kali_kedua_ditolak_409_satu_lunas(transfer, admin):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    sebelum = stempel_putusan()
    kode, isi, _t = kirim_putusan(transfer, admin, SETUJUI, order_id)
    assert kode == 409 and "Traceback" not in isi and stempel_putusan() == sebelum
    assert len(tabel("transfer_lunas")) == 1


def test_setujui_bukti_baru_masuk_setelah_dilihat_ditolak_409_tanpa_efek(transfer, admin):
    order_id = order_menunggu(transfer)
    dilihat = id_bukti_terakhir(order_id)
    assert kirim_bukti(transfer, PNG)[0] == 303                         # guru unggah lagi sesudah admin membuka
    sebelum = stempel_putusan()
    kode, _i, _t = kirim_putusan(transfer, admin, SETUJUI, order_id, bukti_id=dilihat)
    assert kode == 409 and stempel_putusan() == sebelum
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303  # dengan token terbaru sah


def test_setujui_tanpa_bukti_menunggu_409(transfer, admin):
    siap_tagihan(transfer)
    with ledger() as kon:
        order_id = kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]
    kode, _i, _t = minta_admin(transfer, SETUJUI, admin, token_putusan(admin, AKSI_SETUJUI, order_id, 1))
    assert kode == 409 and tabel("transfer_lunas") == []


def test_setujui_order_tak_ada_404_identik(transfer, admin):
    order_menunggu(transfer)
    acuan = minta_admin(transfer, TAK_ADA, admin, {"x": "1"})
    kode, isi, _t = minta_admin(transfer, SETUJUI, admin, token_putusan(admin, AKSI_SETUJUI, ORDER_ASING, 1))
    assert (kode, isi) == acuan[:2] and kode == 404


def test_setujui_order_id_hanya_dari_tinjauan_bukan_form(transfer, admin):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, SETUJUI, order_id, ekstra={"order_id": ORDER_ASING})[0] == 400
    assert kirim_putusan(transfer, admin, SETUJUI, order_id, ekstra={"target_id": ORDER_ASING})[0] == 400
    assert stempel_putusan() == sebelum


# --- tolak ---------------------------------------------------------------------------------

def test_tolak_sukses_alasan_tersimpan_guru_melihat_alasan_dan_bisa_unggah_ulang(transfer, admin):
    order_id = order_menunggu(transfer)
    kode, isi, tajuk = kirim_putusan(transfer, admin, TOLAK, order_id, ganti={"alasan": "  Nominal kurang  "})
    assert (kode, isi, _hasil(tajuk)) == (303, "", "verifikasi_tolak")
    (putusan,) = tabel("transfer_verifikasi")
    assert (putusan["keputusan"], putusan["alasan"], putusan["admin_id"]) == ("tolak", "Nominal kurang", id_admin())
    assert tabel("transfer_lunas") == []
    guru = minta_mentah(transfer, STATUS, AKUN_A)[1]
    assert "Bukti belum sesuai" in guru and "Nominal kurang" in guru and 'name="berkas"' in guru
    assert kirim_bukti(transfer, PNG)[0] == 303                         # unggah ulang selama jendela terbuka
    assert "Bukti diterima, menunggu pemeriksaan" in minta_mentah(transfer, STATUS, AKUN_A)[1]


@pytest.mark.parametrize("alasan", ["", "   ", "\t\n", "a" * 201, "ada\x07kontrol", "baris\nbaru", "x​y"])
def test_tolak_alasan_tak_sah_400_tanpa_efek(transfer, admin, alasan):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    kode, isi, _t = kirim_putusan(transfer, admin, TOLAK, order_id, ganti={"alasan": alasan})
    assert kode == 400 and "Traceback" not in isi and "alasan" in isi.lower()
    assert stempel_putusan() == sebelum


def test_tolak_tanpa_field_alasan_400_tanpa_efek(transfer, admin):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, TOLAK, order_id, hapus=("alasan",))[0] == 400
    assert stempel_putusan() == sebelum


def test_tolak_alasan_batas_tepat_200_sah(transfer, admin):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, TOLAK, order_id, ganti={"alasan": "a" * 200})[0] == 303


def test_tolak_dua_kali_kedua_409(transfer, admin):
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, TOLAK, order_id)[0] == 303
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, TOLAK, order_id)[0] == 409
    assert stempel_putusan() == sebelum


def test_tolak_bukti_baru_masuk_setelah_dilihat_409(transfer, admin):
    order_id = order_menunggu(transfer)
    dilihat = id_bukti_terakhir(order_id)
    assert kirim_bukti(transfer, PNG)[0] == 303
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, TOLAK, order_id, bukti_id=dilihat)[0] == 409
    assert stempel_putusan() == sebelum


def test_tolak_alasan_xss_di_halaman_guru_ter_escape(transfer, admin):
    order_id = order_menunggu(transfer)
    kirim_putusan(transfer, admin, TOLAK, order_id, ganti={"alasan": "<img src=x onerror=alert(1)>"})
    guru = minta_mentah(transfer, STATUS, AKUN_A)[1]
    assert "<img src=x" not in guru and "&lt;img src=x" in guru


# --- guard form bersama (CSRF, sandi, tinjauan, asal, peran) -----------------------------------

@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_csrf_salah_403_tanpa_efek(transfer, admin, jalur):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, jalur, order_id, ganti={"csrf": "rusak"})[0] == 403
    assert kirim_putusan(transfer, admin, jalur, order_id, hapus=("csrf",))[0] == 403
    assert stempel_putusan() == sebelum


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_sandi_ulang_salah_atau_hilang_403_tanpa_efek(transfer, admin, jalur):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, jalur, order_id, ganti={"reauth": "salah-sandi"})[0] == 403
    assert kirim_putusan(transfer, admin, jalur, order_id, hapus=("reauth",))[0] == 403
    assert stempel_putusan() == sebelum


def test_tinjauan_aksi_lain_tidak_berlaku_lintas_rute(transfer, admin):
    order_id = order_menunggu(transfer)
    bukti_id = id_bukti_terakhir(order_id)
    sebelum = stempel_putusan()
    tolak = token_putusan(admin, AKSI_TOLAK, order_id, bukti_id)
    assert minta_admin(transfer, SETUJUI, admin, tolak)[0] == 403
    setuju = {**token_putusan(admin, AKSI_SETUJUI, order_id, bukti_id), "alasan": "x"}
    assert minta_admin(transfer, TOLAK, admin, setuju)[0] == 403
    assert stempel_putusan() == sebelum


def test_tinjauan_dari_sesi_lain_atau_basic_auth_ditolak(transfer, admin):
    order_id = order_menunggu(transfer)
    bukti_id = id_bukti_terakhir(order_id)
    sebelum = stempel_putusan()
    asing = token_putusan("sesi-lain-sintetis", AKSI_SETUJUI, order_id, bukti_id)
    assert minta_admin(transfer, SETUJUI, admin, asing)[0] == 403
    sah = token_putusan(admin, AKSI_SETUJUI, order_id, bukti_id)
    assert minta_mentah(transfer, SETUJUI, AKUN_ADMIN, sah)[0] == 403
    assert stempel_putusan() == sebelum


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_permintaan_lintas_situs_ditolak_403_tanpa_efek(transfer, admin, jalur):
    order_id = order_menunggu(transfer)
    sebelum = stempel_putusan()
    assert kirim_putusan(transfer, admin, jalur, order_id, headers=LINTAS_SITUS)[0] == 403
    assert stempel_putusan() == sebelum


@pytest.mark.parametrize("jalur", [SETUJUI, TOLAK])
def test_tidak_ada_penolakan_membocorkan_galat_internal(transfer, admin, jalur):
    order_id = order_menunggu(transfer)
    for ganti in ({"csrf": "x"}, {"reauth": "x"}):
        kode, isi, _t = kirim_putusan(transfer, admin, jalur, order_id, ganti=ganti)
        assert kode == 403 and "Traceback" not in isi and "sqlite" not in isi.lower()


# --- refund order lunas-transfer (jalur refund admin yang ada) ----------------------------------

def _lunas_transfer(transfer, admin) -> str:
    order_id = order_menunggu(transfer)
    assert kirim_putusan(transfer, admin, SETUJUI, order_id)[0] == 303
    return order_id


def test_refund_order_lunas_transfer_tampil_dan_dicatat_ke_transfer_refund(transfer, admin):
    from admin_pesanan_kit import REFUND, form_halaman, kirim_dari_halaman, hasil_dari
    order_id = _lunas_transfer(transfer, admin)
    isi = minta_admin(transfer, HALAMAN, admin)[1]
    assert REFUND in form_halaman(isi, order_id)
    kode, _i, tajuk = kirim_dari_halaman(transfer, admin, REFUND, order_id)
    assert (kode, hasil_dari(tajuk)) == (303, "refund_dicatat")
    (baris,) = tabel("transfer_refund")
    assert (baris["order_id"], baris["dicatat_oleh"]) == (order_id, id_admin())
    assert tabel("pesanan_refund") == []
    assert "Direfund" in minta_admin(transfer, HALAMAN, admin)[1]
    assert "Pembayaran dikembalikan" in minta_mentah(transfer, STATUS, AKUN_A)[1]


def test_refund_order_lunas_transfer_replay_idempoten_dan_catatan_beda_409(transfer, admin):
    from admin_pesanan_kit import REFUND, hasil_dari, kirim_aksi
    order_id = _lunas_transfer(transfer, admin)
    assert hasil_dari(kirim_aksi(transfer, admin, REFUND, order_id)[2]) == "refund_dicatat"
    assert hasil_dari(kirim_aksi(transfer, admin, REFUND, order_id)[2]) == "refund_sudah_ada"
    assert kirim_aksi(transfer, admin, REFUND, order_id, ganti={"catatan_kode": "lainnya"})[0] == 409
    assert len(tabel("transfer_refund")) == 1


def test_refund_order_transfer_belum_lunas_409_tanpa_catatan(transfer, admin):
    from admin_pesanan_kit import REFUND, kirim_aksi
    order_id = order_menunggu(transfer)
    assert kirim_aksi(transfer, admin, REFUND, order_id)[0] == 409
    assert tabel("transfer_refund") == []
