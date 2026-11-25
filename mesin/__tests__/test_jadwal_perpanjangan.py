"""Perpanjangan bulanan jadwal: penempatan lama dipensiunkan, Private tidak dilepas setelah mulai, dan bacaan murid.

Data sintetis. Akses `lunas` pada SESUDAH_UPLOAD = 2026-11-20T09:30:00 sampai 2026-12-20T09:30:00 UTC; order kedua
paket yang sama menyambung (mulai = akhir order pertama).
"""
import pytest

import jadwal_dasar as jd
import jadwal_store as js
import kelas_kit
import pesanan_dasar as d
import schema_jadwal

ADMIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
SEKARANG = kelas_kit.SESUDAH_UPLOAD
AKHIR_PERTAMA = "2026-12-20T09:30:00"
SETELAH_AKHIR_PERTAMA = "2026-12-21T00:00:00"
SETELAH_SESI_LAMA = "2026-12-18T00:00:00"   # sesi terakhir order pertama = 17 Des; akses lama baru habis 20 Des
KUNCI_SESI = {"ke", "mulai", "menit", "dibatalkan"}


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def _kelompok(kon, *, nama="Mini A", lokasi="Ruang 1", tanggal="2026-11-21", kuota=5):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=lokasi, guru_id=GURU, kuota=kuota,
                            tanggal=tanggal, jam="09:00", sekarang=kelas_kit.KINI)


def _privat(kon, order_id, tanggal="2026-11-23", sekarang=SEKARANG):
    return js.tempatkan(kon, ADMIN, order_id, guru_id=GURU, tanggal=tanggal, jam="16:30", sekarang=sekarang)


def _mini(kon, order_id, kid, sekarang=SEKARANG):
    return js.tempatkan(kon, ADMIN, order_id, kelompok_id=kid, sekarang=sekarang)


def _versi(kon, order_id):
    return js.ringkas_order(kon, order_id)["dibuat"]


def _jumlah(kon, tabel, **kolom):
    sql = "SELECT COUNT(*) FROM %s" % tabel
    if kolom:
        sql += " WHERE " + " AND ".join("%s=?" % k for k in kolom)
    return kon.execute(sql, tuple(kolom.values())).fetchone()[0]


def _rantai_privat(kon):
    """Dua order Private anak yang sama; yang pertama sudah ditempatkan (8 sesi)."""
    lama = kelas_kit.lunas(kon, 1, "private", n=1)
    _privat(kon, lama.order_id)
    baru = kelas_kit.lunas(kon, 1, "private", n=2)
    return lama.order_id, baru.order_id


# --- pensiun penempatan lama ------------------------------------------------------------------

def test_perpanjangan_private_memensiunkan_penempatan_lama_dan_sesinya_tetap_riwayat(kon):
    lama, baru = _rantai_privat(kon)
    _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)
    assert js.ringkas_order(kon, lama) is None
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 0
    assert _jumlah(kon, "jadwal_pertemuan", order_id=lama) == 8
    assert len(js.ringkas_order(kon, baru)["sesi"]) == 8
    assert _jumlah(kon, "jadwal_penempatan") == 1


def test_perpanjangan_mini_memensiunkan_anggota_lama_dan_sesi_kelompok_utuh(kon):
    kid_lama, kid_baru = _kelompok(kon), _kelompok(kon, nama="Mini B", tanggal="2026-12-21")
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, kid_lama)
    baru = kelas_kit.lunas(kon, 1, "mini", n=2)
    _mini(kon, baru.order_id, kid_baru, sekarang=SETELAH_SESI_LAMA)
    assert js.detail_kelompok(kon, kid_lama)["terisi"] == 0
    assert js.detail_kelompok(kon, kid_baru)["terisi"] == 1
    assert len(js.detail_kelompok(kon, kid_lama)["sesi"]) == 8


def test_perpanjangan_mini_ke_kelompok_penuh_dibatalkan_dan_pensiun_ikut_rollback(kon):
    kid_lama = _kelompok(kon)
    kid_penuh = _kelompok(kon, nama="Mini B", tanggal="2026-12-21", kuota=1)
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, kid_lama)
    lain = kelas_kit.lunas(kon, 2, "mini", n=2, putus="2026-12-15T00:00:00")   # akses sampai pertengahan Jan
    _mini(kon, lain.order_id, kid_penuh)
    baru = kelas_kit.lunas(kon, 1, "mini", n=3)
    with pytest.raises(jd.JadwalPenuh):
        _mini(kon, baru.order_id, kid_penuh, sekarang=SETELAH_SESI_LAMA)
    assert js.detail_kelompok(kon, kid_lama)["terisi"] == 1
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama.order_id) == 1
    assert _jumlah(kon, "jadwal_penempatan", order_id=baru.order_id) == 0


def test_pensiun_private_ikut_rollback_bila_penulisan_sesi_gagal(kon, monkeypatch):
    lama, baru = _rantai_privat(kon)

    def gagal(*_a, **_k):
        raise RuntimeError("gagal sintetis")

    monkeypatch.setattr(js, "_tulis_sesi", gagal)
    with pytest.raises(RuntimeError):
        _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 1
    assert _jumlah(kon, "jadwal_penempatan", order_id=baru) == 0
    assert _jumlah(kon, "jadwal_pertemuan", order_id=lama) == 8
    assert _jumlah(kon, "jadwal_pertemuan", order_id=baru) == 0
    assert not kon.in_transaction


def test_akses_lama_masih_berjalan_melewati_mulai_baru_tetap_konflik_tanpa_efek(kon):
    kid = _kelompok(kon)
    lama = kelas_kit.lunas(kon, 1, "private", n=1)
    _privat(kon, lama.order_id)
    mini = kelas_kit.lunas(kon, 1, "mini", n=2)          # paket lain: tidak menyambung, mulai = SEKARANG
    with pytest.raises(jd.JadwalKonflik, match="lepas dulu"):
        _mini(kon, mini.order_id, kid)
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama.order_id) == 1
    assert _jumlah(kon, "jadwal_pertemuan", order_id=lama.order_id) == 8
    assert _jumlah(kon, "jadwal_penempatan", order_id=mini.order_id) == 0
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_penempatan_lama_yang_sudah_lewat_waktu_sekarang_dipensiunkan_walau_tak_menyambung(kon):
    kid = _kelompok(kon, tanggal="2026-12-21")
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, _kelompok(kon, nama="Mini Lama"))
    privat = kelas_kit.lunas(kon, 1, "private", n=2, putus="2026-12-15T00:00:00")   # akses 15 Des - 15 Jan
    _privat(kon, privat.order_id, tanggal="2026-12-21", sekarang=SETELAH_AKHIR_PERTAMA)
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama.order_id) == 0
    assert _jumlah(kon, "jadwal_penempatan", order_id=privat.order_id) == 1
    assert js.detail_kelompok(kon, kid)["terisi"] == 0


def test_pensiun_hanya_bila_akses_lama_berakhir_tepat_di_batas_atau_lebih_awal(kon):
    """Batas persis: akhir akses lama == mulai akses baru dipensiunkan (<=), bukan hanya yang lebih awal."""
    lama, baru = _rantai_privat(kon)
    akhir_lama = kon.execute("SELECT berakhir FROM kelas_akses WHERE order_id=?", (lama,)).fetchone()[0]
    mulai_baru = kon.execute("SELECT mulai FROM kelas_akses WHERE order_id=?", (baru,)).fetchone()[0]
    assert akhir_lama == mulai_baru == AKHIR_PERTAMA
    _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 0


def test_private_order_yang_sudah_bersesi_tidak_bisa_ditempatkan_ulang(kon):
    lama, baru = _rantai_privat(kon)
    _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)   # lama dipensiunkan, sesinya tetap
    with pytest.raises(jd.JadwalKonflik, match="sudah pernah dijadwalkan"):
        _privat(kon, lama, tanggal="2026-11-25")
    assert _jumlah(kon, "jadwal_pertemuan", order_id=lama) == 8
    assert _jumlah(kon, "jadwal_penempatan", order_id=baru) == 1
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 0


def test_private_order_bersesi_ditolak_sebelum_menulis_apa_pun(kon):
    lama, _baru = _rantai_privat(kon)
    sebelum = (_jumlah(kon, "jadwal_penempatan"), _jumlah(kon, "jadwal_pertemuan"))
    with pytest.raises(jd.JadwalKonflik):
        _privat(kon, lama, tanggal="2026-11-25")         # order sudah ditempatkan DAN bersesi
    assert (_jumlah(kon, "jadwal_penempatan"), _jumlah(kon, "jadwal_pertemuan")) == sebelum


# --- lepas Private hanya sebelum mulai ---------------------------------------------------------

def test_lepas_private_diizinkan_bila_semua_sesi_di_masa_depan_dan_sesi_terhapus(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    _privat(kon, tagihan.order_id)                         # sesi 1 = 2026-11-23T09:30:00
    js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=_versi(kon, tagihan.order_id), sekarang="2026-11-23T09:30:00")   # tepat saat mulai: masih boleh
    assert _jumlah(kon, "jadwal_penempatan", order_id=tagihan.order_id) == 0
    assert _jumlah(kon, "jadwal_pertemuan", order_id=tagihan.order_id) == 0


def test_lepas_private_ditolak_setelah_ada_sesi_yang_sudah_mulai_tanpa_efek(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    _privat(kon, tagihan.order_id)
    with pytest.raises(jd.JadwalKonflik, match="sudah berlangsung"):
        js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=_versi(kon, tagihan.order_id), sekarang="2026-11-23T09:30:01")   # satu detik lewat
    assert _jumlah(kon, "jadwal_penempatan", order_id=tagihan.order_id) == 1
    assert _jumlah(kon, "jadwal_pertemuan", order_id=tagihan.order_id) == 8


def test_lepas_private_ditolak_bila_hanya_sebagian_sesi_yang_sudah_mulai(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    _privat(kon, tagihan.order_id)
    with pytest.raises(jd.JadwalKonflik):
        js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=_versi(kon, tagihan.order_id), sekarang="2026-12-10T00:00:00")
    assert _jumlah(kon, "jadwal_pertemuan", order_id=tagihan.order_id) == 8


def test_lepas_mini_tetap_boleh_kapan_saja_dan_sesi_kelompok_utuh(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    _mini(kon, mini.order_id, kid)
    js.lepas_penempatan(kon, ADMIN, mini.order_id, versi=_versi(kon, mini.order_id), sekarang="2026-12-16T00:00:00")   # semua sesi kelompok lewat
    assert js.detail_kelompok(kon, kid)["terisi"] == 0
    assert len(js.detail_kelompok(kon, kid)["sesi"]) == 8


# --- jadwal_untuk_murid ------------------------------------------------------------------------

def test_jadwal_untuk_murid_private_hanya_lokasi_dan_sesi(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    _privat(kon, tagihan.order_id)
    sesi_id = js.ringkas_order(kon, tagihan.order_id)["sesi"][1]["id"]
    js.batalkan_pertemuan(kon, ADMIN, sesi_id, batal=True, sekarang=SEKARANG)
    hasil = js.jadwal_untuk_murid(kon, tagihan.order_id)
    assert set(hasil) == {"lokasi", "sesi"} and hasil["lokasi"] == schema_jadwal.LOKASI_PRIVATE
    assert [s["ke"] for s in hasil["sesi"]] == list(range(1, 9))
    assert all(set(s) == KUNCI_SESI and s["menit"] == 60 for s in hasil["sesi"])
    assert hasil["sesi"][0]["mulai"] == "2026-11-23T09:30:00" and hasil["sesi"][0]["dibatalkan"] is False
    assert [s["ke"] for s in hasil["sesi"] if s["dibatalkan"]] == [2]


def test_jadwal_untuk_murid_mini_memakai_lokasi_dan_sesi_kelompok(kon):
    kid = _kelompok(kon, lokasi="Ruang Melati")
    mini = kelas_kit.lunas(kon, 1, "mini")
    _mini(kon, mini.order_id, kid)
    hasil = js.jadwal_untuk_murid(kon, mini.order_id)
    assert set(hasil) == {"lokasi", "sesi"} and hasil["lokasi"] == "Ruang Melati"
    assert [s["mulai"] for s in hasil["sesi"]] == [s["mulai"] for s in js.detail_kelompok(kon, kid)["sesi"]]
    assert all(set(s) == KUNCI_SESI for s in hasil["sesi"])


def test_jadwal_untuk_murid_tanpa_guru_dan_tanpa_id(kon):
    kid = _kelompok(kon)
    mini = kelas_kit.lunas(kon, 1, "mini")
    _mini(kon, mini.order_id, kid)
    privat = kelas_kit.lunas(kon, 2, "private", n=2, akun=kelas_kit.AKUN_B)
    _privat(kon, privat.order_id)
    for order_id, id_lain in ((mini.order_id, kid), (privat.order_id, privat.order_id)):
        teks = repr(js.jadwal_untuk_murid(kon, order_id))
        assert GURU not in teks and "akun_" not in teks and "klp_" not in teks and "kor_" not in teks, teks
        assert id_lain not in teks


def test_jadwal_untuk_murid_tanpa_penempatan_atau_order_asing_none(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    assert js.jadwal_untuk_murid(kon, tagihan.order_id) is None
    assert js.jadwal_untuk_murid(kon, kelas_kit.kor(999)) is None


def test_jadwal_untuk_murid_order_id_tidak_sah_ditolak(kon):
    with pytest.raises(d.PesananDataTidakSah):
        js.jadwal_untuk_murid(kon, "bukan-order")


def test_jadwal_untuk_murid_order_pensiun_none_dan_order_baru_ada(kon):
    lama, baru = _rantai_privat(kon)
    _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)
    assert js.jadwal_untuk_murid(kon, lama) is None
    assert js.jadwal_untuk_murid(kon, baru)["sesi"][0]["mulai"] == "2026-12-21T09:30:00"


# --- jadwal_terbaru_murid (order dari akun + anak, bukan dari pemanggil) --------------------------

def test_jadwal_terbaru_murid_hanya_milik_akun_dan_anak_sendiri(kon):
    kid_a, kid_b = _kelompok(kon, lokasi="Ruang Alfa"), _kelompok(kon, nama="Mini B", lokasi="Ruang Beta")
    a = kelas_kit.lunas(kon, 1, "mini", n=1)
    b = kelas_kit.lunas(kon, 2, "mini", n=2, akun=kelas_kit.AKUN_B)
    _mini(kon, a.order_id, kid_a)
    _mini(kon, b.order_id, kid_b)
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG)["lokasi"] == "Ruang Alfa"
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_B, 2, SEKARANG)["lokasi"] == "Ruang Beta"
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_B, 1, SEKARANG) is None   # akun lain, anak orang lain
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 2, SEKARANG) is None


def test_jadwal_terbaru_murid_hanya_order_aktif_dan_tetap_ada_saat_tagihan_baru_menunggu(kon):
    kid = _kelompok(kon, lokasi="Ruang Alfa")
    a = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, a.order_id, kid)
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG)["lokasi"] == "Ruang Alfa"
    kelas_kit.tagih(kon, 1, "mini")                                       # perpanjangan belum dibayar
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG)["lokasi"] == "Ruang Alfa"


def test_jadwal_terbaru_murid_order_belum_aktif_tidak_pernah_ditampilkan(kon):
    kelas_kit.tagih(kon, 1, "private")
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG) is None


def test_jadwal_terbaru_murid_setelah_perpanjangan_menampilkan_order_baru(kon):
    lama, baru = _rantai_privat(kon)
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG)["sesi"][0]["mulai"] == "2026-11-23T09:30:00"
    _privat(kon, baru, tanggal="2026-12-21", sekarang=SETELAH_SESI_LAMA)
    assert js.jadwal_terbaru_murid(kon, kelas_kit.AKUN_A, 1, SEKARANG)["sesi"][0]["mulai"] == "2026-12-21T09:30:00"


# --- perpanjangan dini: tidak boleh memensiunkan penempatan lama yang masih punya pertemuan tersisa --------------

def test_perpanjangan_dini_private_dengan_sesi_lama_tersisa_tetap_konflik_tanpa_efek(kon):
    lama, baru = _rantai_privat(kon)                       # sesi lama sampai 17 Des; sekarang 20 Nov
    with pytest.raises(jd.JadwalKonflik, match="lepas dulu"):
        _privat(kon, baru, tanggal="2026-12-21")
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 1
    assert _jumlah(kon, "jadwal_penempatan", order_id=baru) == 0
    assert _jumlah(kon, "jadwal_pertemuan", order_id=baru) == 0
    assert len(js.ringkas_order(kon, lama)["sesi"]) == 8


def test_perpanjangan_dini_mini_dengan_sesi_kelompok_tersisa_tetap_konflik_tanpa_efek(kon):
    kid_lama, kid_baru = _kelompok(kon), _kelompok(kon, nama="Mini B", tanggal="2026-12-21")
    lama = kelas_kit.lunas(kon, 1, "mini", n=1)
    _mini(kon, lama.order_id, kid_lama)
    baru = kelas_kit.lunas(kon, 1, "mini", n=2)
    with pytest.raises(jd.JadwalKonflik, match="lepas dulu"):
        _mini(kon, baru.order_id, kid_baru)
    assert js.detail_kelompok(kon, kid_lama)["terisi"] == 1
    assert js.detail_kelompok(kon, kid_baru)["terisi"] == 0


def test_perpanjangan_dini_boleh_bila_sisa_sesi_lama_semuanya_dibatalkan(kon):
    lama, baru = _rantai_privat(kon)
    for sesi in js.ringkas_order(kon, lama)["sesi"]:
        js.batalkan_pertemuan(kon, ADMIN, sesi["id"], batal=True, sekarang=SEKARANG)
    _privat(kon, baru, tanggal="2026-12-21")               # tak ada pertemuan aktif tersisa: dipensiunkan
    assert _jumlah(kon, "jadwal_penempatan", order_id=lama) == 0
    assert _jumlah(kon, "jadwal_penempatan", order_id=baru) == 1


def test_lepas_private_diizinkan_bila_sesi_yang_sudah_lewat_semuanya_dibatalkan(kon):
    tagihan = kelas_kit.lunas(kon, 1, "private")
    _privat(kon, tagihan.order_id)
    pertama = js.ringkas_order(kon, tagihan.order_id)["sesi"][0]
    js.batalkan_pertemuan(kon, ADMIN, pertama["id"], batal=True, sekarang=SEKARANG)
    js.lepas_penempatan(kon, ADMIN, tagihan.order_id, versi=_versi(kon, tagihan.order_id), sekarang="2026-11-23T10:00:00")   # sesi 1 lewat tetapi dibatalkan
    assert _jumlah(kon, "jadwal_penempatan", order_id=tagihan.order_id) == 0
