"""Kontrak antrean "Perlu ditangani" per item: data sintetis, read-only, terbatas 50 baris."""
import pytest

import admin_antrean as A
import admin_antrean_pages as AP
import admin_operations
import admin_queries as Q
import admin_store

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


def test_satu_baris_per_keluarga_dan_siswa_bermasalah():
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
    # Setiap siswa tanpa login punya baris sendiri dan tautan detail masing-masing.
    login = [i for i in item if i.judul.endswith("belum punya login")]
    assert sorted(i.judul for i in login) == ["Ani belum punya login", "Budi belum punya login",
                                              "Cici belum punya login", "Dedi belum punya login"]
    assert {i.jalur for i in login} == {"/admin?section=siswa&id=%d" % n for n in (1, 2, 3, 4)}
    # Urutan: keluarga (penting) sebelum siswa/login (tinjau).
    assert [i.tingkat for i in item] == sorted((i.tingkat for i in item), key=["penting", "tinjau"].index)


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
    siswa = [_siswa(n, "Anak %03d" % n, "") for n in range(1, 71)]
    hasil = A.kumpulkan(_konteks(siswa), "/tmp/x", sekarang=SEKARANG)
    assert len(hasil.item) == AP.BATAS_BARIS == 50
    assert hasil.total == 71  # 1 baris pemilik kosong + 70 siswa tanpa login
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
    assert sinyal.total == hasil.total == 2 and sinyal.mendesak == 0
    assert sinyal.operasional_perhatian is False  # backup valid, tanpa operasi mendesak
    assert AP.sinyal_dari(AP.AntreanAdmin()).operasional_perhatian is True  # backup belum terverifikasi


def test_render_meng_escape_nama_siswa_dan_keluarga():
    item = A.item_pengguna(_konteks([_siswa(1, '<img src=x onerror=1>', 'k"><script>')]))
    html = AP.render_antrean(AP.AntreanAdmin(item=item, total=len(item)))
    assert "<img" not in html and "<script" not in html
    assert "&lt;img src=x onerror=1&gt;" in html


def test_tidak_ada_data_contoh_mockup_di_kode_produksi():
    from pathlib import Path
    akar = Path(__file__).resolve().parent.parent
    for nama in ("admin_antrean.py", "admin_antrean_pages.py", "admin_pages.py", "admin_http.py"):
        isi = (akar / nama).read_text(encoding="utf-8")
        for contoh in ("Claudia", "Eugelion", "inv_87e4", "Keluarga Lion", "23 hari", "Belum ditugaskan"):
            assert contoh not in isi, (nama, contoh)
