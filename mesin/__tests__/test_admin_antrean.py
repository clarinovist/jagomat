"""Kontrak antrean "Perlu ditangani" per item: data sintetis, read-only, terbatas 50 baris."""
import sqlite3
from datetime import datetime, timezone

import pytest

import admin_antrean as A
import admin_antrean_pages as AP
import admin_operations
import admin_queries as Q
import admin_store
import admin_transfer_menunggu as TM
import pesanan_transfer as tf
from transfer_kit import SESUDAH_UPLOAD, akun_ke, siapkan_db_transfer, tagihan, unggah

SEKARANG = 1_760_000_000.0  # 2025-10-09; sintetis
HARI = 86400


def _akun(pengguna, peran="guru", siswa_id=None):
    return Q.AkunPublik("akun_" + pengguna, pengguna, peran, siswa_id)


def _konteks(siswa, akun=(), login=()):
    return Q.KonteksAdmin(tuple(akun), tuple(siswa), tuple(login))


def _siswa(id_, nama, pemilik):
    return Q.IdentitasSiswa(id_, nama, "P3", pemilik)


@pytest.fixture
def tanpa_operasi(monkeypatch):
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))


def test_satu_baris_per_keluarga_dan_ringkasan_siswa_tanpa_login():
    konteks = _konteks(
        [_siswa(1, "Ani", "ortu-a"), _siswa(2, "Budi", "tanpa-akun"), _siswa(3, "Cici", "tanpa-akun"),
         _siswa(4, "Dedi", "")],
        akun=[_akun("ortu-a")],
    )
    item = A.item_pengguna(konteks)
    judul = [i.judul for i in item]
    # Dua siswa dalam keluarga tanpa akun = SATU baris keluarga dengan jumlah siswa.
    assert judul.count("Keluarga tanpa-akun belum punya akun pemilik") == 1
    keluarga = next(i for i in item if i.judul.startswith("Keluarga tanpa-akun"))
    assert keluarga.deskripsi.startswith("2 siswa terkait")
    assert "1 siswa belum punya pemilik" in judul
    # Empat siswa tanpa login = SATU baris ringkasan (normal: anak masuk lewat QR), tanpa nama siswa.
    login = [i for i in item if i.judul.endswith("belum punya login")]
    assert [i.judul for i in login] == ["4 siswa belum punya login"]
    assert login[0].tingkat == "tinjau" and login[0].cta == "Lihat daftar"
    assert login[0].jalur == "/admin?section=siswa&status=student_without_login"
    assert login[0].deskripsi.startswith("Normal: anak masuk lewat QR atau tautan HP dari guru.")
    assert not any(nama in i.judul + i.deskripsi for i in item for nama in ("Ani", "Budi", "Cici", "Dedi"))
    # Urutan: keluarga (penting) sebelum ringkasan login (tinjau).
    assert [i.tingkat for i in item] == sorted((i.tingkat for i in item), key=["penting", "tinjau"].index)


def test_n_siswa_tanpa_login_hanya_satu_item_tinjau_berisi_jumlahnya():
    akun = [_akun("ortu-a")]
    siswa = [_siswa(n, "Anak %02d" % n, "ortu-a") for n in range(1, 8)]
    item = A.item_pengguna(_konteks(siswa, akun=akun))
    assert len(item) == 1 and item[0].tingkat == "tinjau"
    assert item[0].judul == "7 siswa belum punya login"


def test_siswa_sehat_tidak_muncul():
    akun = [_akun("ortu-a"), Q.AkunPublik("akun_murid", "ani", "murid", 1)]
    assert A.item_pengguna(_konteks([_siswa(1, "Ani", "ortu-a")], akun)) == ()


def test_login_bermasalah_per_login_hanya_status_antrean():
    login = (Q.LoginBermasalah("a1", "login-yatim", 9, "orphan_login", 0),
             Q.LoginBermasalah("a2", "login-lama", None, "legacy_same_name_ambiguous", 2),
             Q.LoginBermasalah("a3", "login-lain", None, "legacy_login_unverified", 1))
    item = A.item_pengguna(_konteks([], login=login))
    assert [i.judul for i in item] == ["Login login-yatim perlu ditinjau", "Login login-lama perlu ditinjau"]
    assert all(i.jalur == "#login-perlu-perhatian" for i in item)
    assert "2 kandidat nama" in item[1].deskripsi


def test_operasi_per_baris_dengan_umur_dan_ref_diringkas(monkeypatch, tanpa_operasi):
    baris = ({"sumber": "pembayaran", "ref": "inv_" + "a" * 12 + "bcdef9", "akun": "x",
              "status": "perlu_diperiksa", "waktu": SEKARANG - 23 * HARI},
             {"sumber": "admin", "ref": "op1", "akun": "x", "status": "uncertain", "waktu": None})
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: (baris, 2))
    hasil = A.kumpulkan(_konteks([]), "/tmp/tak-dipakai", sekarang=SEKARANG)
    bayar, admin = hasil.item
    assert bayar.tingkat == "mendesak" and bayar.umur_hari == 23
    assert bayar.ref == "inv_aaaa…bcdef9" and bayar.cta == "Periksa invoice"
    assert "sejak" in bayar.deskripsi and "jangan mengulang atau memaksa status lunas" in bayar.deskripsi
    assert admin.umur_hari is None and admin.judul == "Tindakan admin belum pasti"
    assert hasil.mendesak == 2 and hasil.total == 2 and hasil.layanan_tersedia


def test_umur_tidak_dipalsukan_untuk_item_tanpa_waktu(tanpa_operasi):
    konteks = _konteks([_siswa(1, "Ani", "")])
    hasil = A.kumpulkan(konteks, "/tmp/x", sekarang=SEKARANG)
    assert hasil.item and all(i.umur_hari is None for i in hasil.item)


def test_batas_50_baris_dan_total_tetap_penuh(monkeypatch, tanpa_operasi):
    siswa = [_siswa(n, "Anak %03d" % n, "pemilik-%03d" % n) for n in range(1, 71)]
    hasil = A.kumpulkan(_konteks(siswa), "/tmp/x", sekarang=SEKARANG)
    assert len(hasil.item) == AP.BATAS_BARIS == 50
    assert hasil.total == 71  # 70 keluarga tanpa akun (penting) + 1 ringkasan siswa tanpa login (tinjau)
    assert hasil.perlu_keputusan == 70
    html = AP.render_antrean(hasil)
    assert "dan 21 lainnya" in html
    assert html.count('<li class="admin-antrean-item">') == 50


def test_sumber_layanan_hilang_memakai_fallback_agregat(monkeypatch):
    def hilang(path, **k):
        raise admin_store.StoreBelumSiap("x")

    class Total:
        def __init__(self, total):
            self.total = total

    monkeypatch.setattr(admin_operations, "antrean", hilang)
    monkeypatch.setattr(admin_store, "daftar_riwayat",
                        lambda path, status, per_halaman: Total(2 if status == "uncertain" else 3))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Bundle valid", 1.0))
    hasil = A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG)
    assert not hasil.layanan_tersedia and hasil.mendesak == 1
    assert "2 belum pasti · 3 menunggu hasil" in hasil.item[0].deskripsi
    assert hasil.item[0].jalur == "/admin?section=riwayat"
    assert "Jumlah antrean layanan belum tersedia" in AP.render_antrean(hasil)


def test_backup_belum_terverifikasi_dan_tidak_valid_beda_judul(monkeypatch):
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Belum terverifikasi", None))
    awal = A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG)
    assert awal.item[0].judul == "Backup belum terverifikasi" and not awal.backup_terverifikasi
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Bukti backup tidak valid", None))
    assert A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG).item[0].judul == "Bukti backup tidak valid"
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Bundle valid", 5.0))
    ok = A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG)
    assert ok.item == () and ok.backup_terverifikasi and ok.total == 0


def test_sinyal_nav_dari_antrean_yang_sama(monkeypatch, tanpa_operasi):
    konteks = _konteks([_siswa(1, "Ani", "ortu")])
    hasil = A.kumpulkan(konteks, "/tmp/x", sekarang=SEKARANG)
    sinyal = AP.sinyal_dari(hasil)
    # Keluarga tanpa akun (penting) dihitung; ringkasan siswa tanpa login (tinjau) tidak.
    assert hasil.total == 2 and hasil.perlu_keputusan == 1
    assert sinyal.total == 1 and sinyal.mendesak == 0 and sinyal.transfer_menunggu == 0
    assert sinyal.operasional_perhatian is False  # backup valid, tanpa operasi mendesak
    assert AP.sinyal_dari(AP.AntreanAdmin()).operasional_perhatian is True  # backup belum terverifikasi


def test_badge_tidak_menghitung_tinjau_ringan(tanpa_operasi):
    siswa = [_siswa(n, "Anak %d" % n, "ortu") for n in range(1, 21)]
    login = (Q.LoginBermasalah("a1", "login-yatim", 9, "orphan_login", 0),)
    konteks = _konteks(siswa, akun=[_akun("ortu")], login=login)
    hasil = A.kumpulkan(konteks, "/tmp/x", sekarang=SEKARANG)
    assert {i.tingkat for i in hasil.item} == {"tinjau"} and hasil.total == 2
    assert hasil.perlu_keputusan == 0 and AP.sinyal_dari(hasil).total == 0


def test_perlu_keputusan_menghitung_mendesak_dan_penting_penuh(monkeypatch):
    baris = tuple({"sumber": "layanan", "ref": "op%d" % n, "akun": "x", "status": "uncertain",
                   "waktu": SEKARANG} for n in range(3))
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: (baris, 3))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Belum terverifikasi", None))
    hasil = A.kumpulkan(_konteks([_siswa(1, "Ani", "ortu")]), "/tmp/x", sekarang=SEKARANG)
    # 3 operasi (mendesak) + backup (penting) + keluarga tanpa akun (penting); ringkasan login tidak dihitung.
    assert hasil.mendesak == 3 and hasil.perlu_keputusan == 5 and hasil.total == 6


# --- transfer menunggu verifikasi (A1) ---------------------------------------------------------

def _epoch(waktu_iso):
    return datetime.fromisoformat(waktu_iso).replace(tzinfo=timezone.utc).timestamp()


def _transfer(order_id, nominal, diunggah):
    return TM.TransferMenunggu(order_id, nominal, diunggah)


def test_transfer_menunggu_jadi_item_mendesak_pertama_dengan_nominal_dan_jalur(monkeypatch, tanpa_operasi):
    daftar = (_transfer("ord_" + "a" * 32, 49007, "2026-11-18T10:00:00"),
              _transfer("ord_" + "b" * 32, 49123, "2026-11-19T10:00:00"))
    monkeypatch.setattr(TM, "baca", lambda path, sekarang_iso: daftar)
    sekarang = _epoch("2026-11-20T10:00:00")
    hasil = A.kumpulkan(_konteks([_siswa(1, "Ani", "ortu")]), "/tmp/x", sekarang=sekarang)
    pertama, kedua = hasil.item[:2]
    assert pertama.tingkat == "mendesak" and pertama.judul == "Transfer menunggu verifikasi"
    assert "Rp49.007" in pertama.deskripsi and "18 Nov 2026, 17.00 WIB" in pertama.deskripsi
    assert pertama.jalur == "/admin/pesanan/verifikasi?order=ord_" + "a" * 32
    assert pertama.cta == "Periksa bukti" and pertama.ref_awalan == "Order"
    assert pertama.ref == "ord_aaaa…aaaaaa" and pertama.umur_hari == 2
    assert "Rp49.123" in kedua.deskripsi and kedua.umur_hari == 1
    assert hasil.transfer_menunggu == 2 and hasil.mendesak == 2
    assert hasil.perlu_keputusan == 3  # 2 transfer + keluarga tanpa akun
    sinyal = AP.sinyal_dari(hasil)
    assert sinyal.transfer_menunggu == 2 and sinyal.mendesak == 2 and sinyal.total == 3


def test_transfer_tanpa_nama_anak_atau_kontak_dan_urutan_sebelum_operasi(monkeypatch):
    baris = ({"sumber": "layanan", "ref": "op1", "akun": "x", "status": "uncertain", "waktu": SEKARANG},)
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: (baris, 1))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Belum terverifikasi", None))
    monkeypatch.setattr(TM, "baca", lambda path, sekarang_iso: (_transfer("ord_" + "c" * 32, None, None),))
    hasil = A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG)
    assert [i.judul for i in hasil.item][0] == "Transfer menunggu verifikasi"
    assert hasil.item[1].judul.startswith("Operasi layanan") and hasil.item[2].judul == "Backup belum terverifikasi"
    assert "nominal belum tercatat" in hasil.item[0].deskripsi and hasil.item[0].umur_hari is None
    assert hasil.mendesak == 2 and hasil.perlu_keputusan == 3


def test_transfer_nyata_dari_ledger_terurut_terlama_dulu(tmp_path, tanpa_operasi):
    path = siapkan_db_transfer(tmp_path)
    with tf.buka(path, tulis_data=True) as kon:
        baru, tag_baru = tagihan(kon, 1)
        unggah(kon, baru, 1, sekarang="2026-11-18T12:00:00")
        lama, tag_lama = tagihan(kon, 2, akun=akun_ke(2))
        unggah(kon, lama, 2, akun=akun_ke(2), sekarang="2026-11-18T11:00:00")
    hasil = A.kumpulkan(_konteks([]), path, sekarang=_epoch("2026-11-18T13:00:00"))
    assert [i.jalur.rsplit("=", 1)[1] for i in hasil.item] == [lama["order_id"], baru["order_id"]]
    assert "Rp49.%03d" % (tag_lama["nominal_transfer"] - 49000) in hasil.item[0].deskripsi
    assert hasil.transfer_menunggu == 2 and hasil.mendesak == 2


@pytest.mark.parametrize("galat", [admin_store.StoreBelumSiap("x"), sqlite3.OperationalError("x"), OSError("x")])
def test_sumber_transfer_galat_antrean_tetap_jalan_tanpa_item_transfer(monkeypatch, galat):
    def gagal(path, sekarang_iso):
        raise galat

    baris = ({"sumber": "layanan", "ref": "op1", "akun": "x", "status": "uncertain", "waktu": SEKARANG},)
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: (baris, 1))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda s: ("Bundle valid", 1.0))
    monkeypatch.setattr(TM, "baca", gagal)
    hasil = A.kumpulkan(_konteks([]), "/tmp/x", sekarang=SEKARANG)
    assert [i.judul for i in hasil.item] == ["Operasi layanan perlu diperiksa"]
    assert hasil.transfer_menunggu == 0 and hasil.mendesak == 1


def test_pesanan_belum_dipasang_dan_path_hilang_berarti_tanpa_transfer(tmp_path, tanpa_operasi):
    kosong = tmp_path / "admin-kosong.db"
    admin_store.siapkan(kosong, sekarang=1)  # skema admin ada, namespace pesanan belum
    for path in (kosong, tmp_path / "tidak-ada.db"):
        hasil = A.kumpulkan(_konteks([]), path, sekarang=SEKARANG)
        assert hasil.item == () and hasil.transfer_menunggu == 0


def test_render_meng_escape_nama_keluarga_dan_login():
    login = (Q.LoginBermasalah("a1", '<img src=x onerror=1>', 9, "orphan_login", 0),)
    item = A.item_pengguna(_konteks([_siswa(1, "Ani", 'k"><script>')], login=login))
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=len(item)))
    assert "<img" not in html and "<script" not in html
    assert "&lt;img src=x onerror=1&gt;" in html and "k&quot;&gt;&lt;script&gt;" in html


def test_render_tinjau_di_dalam_details_tertutup_dan_penting_di_luar():
    item = (AP.ItemAntrean("mendesak", "Transfer menunggu verifikasi", "d", "/a", "Periksa bukti"),
            AP.ItemAntrean("penting", "Keluarga X", "d", "/b", "Tinjau keluarga"),
            AP.ItemAntrean("tinjau", "<b>7</b> siswa belum punya login", "d", "/c", "Lihat daftar"))
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=3))
    awal = html.index('<details class="admin-antrean-tinjau">')
    akhir = html.index("</details>")
    assert "<details class=\"admin-antrean-tinjau\" open" not in html
    dalam, luar = html[awal:akhir], html[:awal] + html[akhir:]
    assert "Tinjauan ringan (1)" in dalam and "&lt;b&gt;7&lt;/b&gt; siswa belum punya login" in dalam
    assert '<ol class="admin-antrean">' in dalam and "<li " in dalam
    assert "Transfer menunggu verifikasi" in luar and "Keluarga X" in luar and "siswa belum punya login" not in luar
    assert "satu baris per siswa" not in html.lower() and "<b>7</b>" not in html


def test_render_hanya_tinjau_menampilkan_pesan_kosong_dan_details():
    item = (AP.ItemAntrean("tinjau", "5 siswa belum punya login", "d", "/c", "Lihat daftar"),)
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=1))
    assert "Tidak ada kondisi administratif yang perlu perhatian" in html
    assert html.index("Tidak ada kondisi") < html.index("<details")
    assert "Tinjauan ringan (1)" in html


def test_render_tanpa_tinjau_tidak_ada_details_dan_tombol_solid_hanya_pertama():
    item = (AP.ItemAntrean("mendesak", "A", "d", "/a", "Periksa"), AP.ItemAntrean("penting", "B", "d", "/b", "Tinjau"))
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=2))
    assert "<details" not in html
    assert html.count('class="admin-tombol"') == 1 and html.count('class="admin-antrean-cta"') == 1


def test_render_sisa_lainnya_tampil_di_daftar_terakhir_bersama_tinjau():
    item = (AP.ItemAntrean("penting", "B", "d", "/b", "Tinjau"),
            AP.ItemAntrean("tinjau", "5 siswa belum punya login", "d", "/c", "Lihat daftar"))
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=5))
    assert html.count("dan 3 lainnya") == 1
    assert html.index("dan 3 lainnya") > html.index("<details")


def test_tidak_ada_data_contoh_mockup_di_kode_produksi():
    from pathlib import Path
    akar = Path(__file__).resolve().parent.parent
    for nama in ("admin_antrean.py", "admin_antrean_pages.py", "admin_pages.py", "admin_http.py"):
        isi = (akar / nama).read_text(encoding="utf-8")
        for contoh in ("Claudia", "Eugelion", "inv_87e4", "Keluarga Lion", "23 hari", "Belum ditugaskan"):
            assert contoh not in isi, (nama, contoh)


def test_badge_menu_pesanan_hanya_bila_ada_transfer_menunggu_dan_badge_ringkasan_tidak_berubah():
    import admin_pages
    ada = admin_pages._badge_nav(AP.SinyalNav(total=3, mendesak=2, transfer_menunggu=2), "pesanan")
    assert 'class="admin-nav-badge">2<' in ada and " transfer menunggu verifikasi" in ada
    assert admin_pages._badge_nav(AP.SinyalNav(total=3), "pesanan") == ""
    assert admin_pages._badge_nav(None, "pesanan") == ""
    ringkasan = admin_pages._badge_nav(AP.SinyalNav(total=3, transfer_menunggu=2), "ringkasan")
    assert ">3<" in ringkasan and " hal menunggu keputusan" in ringkasan
    nav = admin_pages._nav("ringkasan", AP.SinyalNav(total=3, transfer_menunggu=2))
    assert nav.count("transfer menunggu verifikasi") == 1
