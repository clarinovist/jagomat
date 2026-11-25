"""Daftar peserta paket aktif di /admin/kelas (butir QA #7, 25 Nov 2026; data sintetis, baca-saja).

Latar: setelah admin menyetujui bukti, order hilang dari antrean "Menunggu verifikasi". Bila admin belum menempatkan
anak saat menyetujui, tidak ada lagi daftar tempat mencarinya. Pembaca ini menampilkan paket yang sudah dibayar dan
masih aktif beserta status penempatannya, tanpa nama anak atau kontak.
"""
import pytest

import jadwal_store as js
import kelas_admin_pages as ui
import kelas_kit
import kelas_peserta as kp
import schema_jadwal

ADMIN = "admin_sintetis"
GURU = "akun_" + "9" * 32
KINI = "2026-11-25T03:00:00"        # akses lunas kelas_kit: 20 Nov 09.30 sampai 20 Des 09.30 (UTC naif)
SETELAH_AKHIR = "2026-12-21T00:00:00"


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    return path


@pytest.fixture()
def kon(db):
    with js.buka(db, tulis_data=True) as koneksi:
        yield koneksi


def test_paket_aktif_belum_ditempatkan_terbaca_tanpa_nama(kon):
    tagihan = kelas_kit.lunas(kon, siswa=7)
    (peserta,) = kp.daftar_peserta_aktif(kon, KINI)
    assert (peserta.order_id, peserta.siswa_id, peserta.kode_paket) == (tagihan.order_id, 7, "mini")
    assert peserta.berakhir == "2026-12-20T09:30:00" and peserta.ditempatkan is False


def test_paket_yang_sudah_ditempatkan_ditandai(kon):
    tagihan = kelas_kit.lunas(kon, siswa=7)
    kelompok = js.buat_kelompok(kon, ADMIN, nama="Mini A", lokasi="https://meet.google.com/abc-defg-hij", guru_id=GURU,
                                kuota=5, tanggal="2026-11-26", jam="09:00", sekarang=kelas_kit.KINI)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok, sekarang=KINI)
    (peserta,) = kp.daftar_peserta_aktif(kon, KINI)
    assert peserta.ditempatkan is True


def test_belum_ditempatkan_tampil_lebih_dulu(kon):
    pertama = kelas_kit.lunas(kon, siswa=1, n=1)
    kedua = kelas_kit.lunas(kon, siswa=2, n=2)
    kelompok = js.buat_kelompok(kon, ADMIN, nama="Mini A", lokasi="https://meet.google.com/abc-defg-hij", guru_id=GURU,
                                kuota=5, tanggal="2026-11-26", jam="09:00", sekarang=kelas_kit.KINI)
    js.tempatkan(kon, ADMIN, pertama.order_id, kelompok_id=kelompok, sekarang=KINI)
    urutan = [(p.order_id, p.ditempatkan) for p in kp.daftar_peserta_aktif(kon, KINI)]
    assert urutan == [(kedua.order_id, False), (pertama.order_id, True)]


def test_order_menunggu_dan_paket_berakhir_tidak_masuk(kon):
    kelas_kit.menunggu(kon, siswa=1, n=1)               # bukti belum disetujui: urusan antrean verifikasi
    kelas_kit.lunas(kon, siswa=2, n=2)
    assert [p.siswa_id for p in kp.daftar_peserta_aktif(kon, KINI)] == [2]
    assert kp.daftar_peserta_aktif(kon, SETELAH_AKHIR) == ()


def test_tabel_jadwal_belum_ada_tetap_terdaftar_dengan_penempatan_tidak_diketahui(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)         # tanpa migrasi jadwal (image lama / rollback)
    import pesanan
    with pesanan.buka(path, tulis_data=True) as kon:
        kelas_kit.lunas(kon, siswa=3)
        (peserta,) = kp.daftar_peserta_aktif(kon, KINI)
    assert peserta.siswa_id == 3 and peserta.ditempatkan is None


def test_blok_halaman_menampilkan_status_tautan_detail_dan_tanpa_nama(kon):
    tagihan = kelas_kit.lunas(kon, siswa=7)
    isi = ui.blok_peserta(kp.daftar_peserta_aktif(kon, KINI))
    assert "Peserta paket aktif" in isi and "Anak #7" in isi and "Belum ditempatkan" in isi
    assert '/admin/kelas/verifikasi?order=%s"' % tagihan.order_id in isi


def test_blok_halaman_kosong_pesan_jujur():
    assert "Belum ada paket aktif" in ui.blok_peserta(())
