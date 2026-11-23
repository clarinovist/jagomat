"""Retensi bukti transfer langganan Latihan Harian: 30 hari sesudah keputusan, urutan aman, jalur CLI cron yang sama.

Data dan berkas sintetis di tmp_path; DB belajar dan DB admin sintetis, tidak menyentuh folder bukti atau DB nyata.
"""
import os
import sqlite3
from datetime import datetime, timezone

import pytest

import database
import harian_langganan_berkas as berkas_harian
import harian_langganan_dasar as h
import harian_langganan_putusan as putusan
import harian_bukti_retensi as retensi
import harian_langganan_store as store
import pesanan_dasar as d
import pesanan_retensi as pr
from bukti_kit import JPEG
from transfer_kit import siapkan_db_transfer

T0 = "2026-11-23T03:00:00"
ADMIN = "admin_sintetis"
TEPAT_30_HARI = "2026-12-23T03:00:00"
KURANG_SEDETIK = "2026-12-23T02:59:59"
FORMAT = "%Y-%m-%dT%H:%M:%S"


@pytest.fixture(autouse=True)
def lingkungan(monkeypatch):
    monkeypatch.delenv("OSN_BERKAS_DB", raising=False)
    monkeypatch.delenv("OSN_DIREKTORI_BUKTI", raising=False)


@pytest.fixture
def jalur(tmp_path):
    p = tmp_path / "latihan.db"
    database.siapkan(p)
    return p


@pytest.fixture
def kon(jalur):
    with database.buka(jalur) as k:
        yield k


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "bukti-transfer"
    (f / berkas_harian.SUBFOLDER).mkdir(parents=True)
    return f


def _hurup(n):
    return "%032x" % (0xABC000 + n)


_nomor = [0]


def _bukti(kon, folder, siswa, waktu=T0, tulis=True):
    """Satu bukti menunggu untuk `siswa`; berkas fisik ditulis di subfolder harian bila `tulis`."""
    _nomor[0] += 1
    nama = _hurup(_nomor[0])
    if tulis:
        (folder / berkas_harian.SUBFOLDER / nama).write_bytes(JPEG)
    return store.catat_bukti(kon, siswa, "image/jpeg", len(JPEG), "%064x" % _nomor[0], nama, waktu), nama


def _anak(kon):
    nama = "Anak Uji %d" % (_nomor[0] + 1)
    siswa = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES (?, 'P3', 'guru')", (nama,)).lastrowid
    kon.commit()
    return siswa


def _tagihan_dan_bukti(kon, folder, siswa=None, waktu=T0, tulis=True):
    siswa = _anak(kon) if siswa is None else siswa
    tagihan = store.buat_tagihan(kon, siswa, "bulanan", waktu)
    b, nama = _bukti(kon, folder, siswa, waktu, tulis)
    return siswa, tagihan["order_id"], b["bukti_id"], nama


def _putuskan(kon, folder, *, setuju=True, waktu=T0, tulis=True):
    siswa, order, bukti_id, nama = _tagihan_dan_bukti(kon, folder, waktu=waktu, tulis=tulis)
    if setuju:
        putusan.setujui(kon, order, ADMIN, waktu, bukti_dilihat=bukti_id)
    else:
        putusan.tolak(kon, order, ADMIN, "Nominal tidak sesuai", waktu, bukti_dilihat=bukti_id)
    return siswa, order, bukti_id, nama


def _ada(folder, nama):
    return (folder / berkas_harian.SUBFOLDER / nama).exists()


def _tertanda(kon):
    return kon.execute("SELECT COUNT(*) FROM harian_bukti_hapus").fetchone()[0]


# --- sapuan inti --------------------------------------------------------------------------------

def test_sapu_menghapus_berkas_lalu_menandai_bukti_yang_sudah_30_hari(kon, folder):
    _, _, _, nama = _putuskan(kon, folder)

    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert (hasil.berkas_dihapus, hasil.ditandai, hasil.gagal) == (1, 1, 0)
    assert not _ada(folder, nama) and _tertanda(kon) == 1


def test_sapu_kurang_sedetik_dari_30_hari_tidak_menyentuh_apa_pun(kon, folder):
    _, _, _, nama = _putuskan(kon, folder)

    hasil = retensi.sapu(kon, folder, KURANG_SEDETIK)

    assert (hasil.berkas_dihapus, hasil.ditandai) == (0, 0)
    assert _ada(folder, nama) and _tertanda(kon) == 0


def test_hitungan_30_hari_dari_keputusan_bukan_dari_unggah(kon, folder):
    siswa, order, bukti_id, nama = _tagihan_dan_bukti(kon, folder, waktu=T0)
    putusan.setujui(kon, order, ADMIN, "2026-11-30T03:00:00", bukti_dilihat=bukti_id)  # keputusan 7 hari kemudian

    assert retensi.sapu(kon, folder, TEPAT_30_HARI).ditandai == 0 and _ada(folder, nama)
    assert retensi.sapu(kon, folder, "2026-12-30T03:00:00").ditandai == 1 and not _ada(folder, nama)


def test_hari_lebih_pendek_diteruskan_ke_penandaan(kon, folder):
    _, _, _, nama = _putuskan(kon, folder)

    hasil = retensi.sapu(kon, folder, "2026-11-30T03:00:00", hari=7)

    assert hasil.ditandai == 1 and not _ada(folder, nama)


def test_bukti_menunggu_tidak_pernah_dihapus_walau_sangat_lama(kon, folder):
    _, _, _, nama = _tagihan_dan_bukti(kon, folder)

    hasil = retensi.sapu(kon, folder, "2027-12-31T00:00:00")

    assert (hasil.berkas_dihapus, hasil.ditandai, hasil.gagal) == (0, 0, 0)
    assert _ada(folder, nama) and _tertanda(kon) == 0


def test_bukti_ditolak_ikut_dihapus_tetapi_bukti_baru_yang_menunggu_tetap(kon, folder):
    siswa, order, lama_id, lama = _tagihan_dan_bukti(kon, folder)
    putusan.tolak(kon, order, ADMIN, "Buram", T0, bukti_dilihat=lama_id)
    baru, nama_baru = _bukti(kon, folder, siswa, "2026-11-23T05:00:00")

    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert hasil.ditandai == 1 and not _ada(folder, lama) and _ada(folder, nama_baru)
    assert [r[0] for r in kon.execute("SELECT bukti_id FROM harian_bukti_hapus")] == [lama_id]


def test_sapu_idempoten_dijalankan_berulang(kon, folder):
    _putuskan(kon, folder)
    retensi.sapu(kon, folder, TEPAT_30_HARI)

    ulang = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert (ulang.berkas_dihapus, ulang.ditandai, ulang.gagal) == (0, 0, 0) and _tertanda(kon) == 1


def test_berkas_hilang_duluan_tidak_membuat_macet_dan_tetap_ditandai(kon, folder):
    _putuskan(kon, folder, tulis=False)

    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert (hasil.berkas_sudah_hilang, hasil.ditandai, hasil.gagal) == (1, 1, 0)


def test_urutan_aman_berkas_dihapus_sebelum_bukti_ditandai(kon, folder, monkeypatch):
    _, _, _, nama = _putuskan(kon, folder)
    kejadian = []
    asli_hapus, asli_tandai = retensi.bukti_berkas.hapus_berkas, retensi.tandai_dihapus
    monkeypatch.setattr(retensi.bukti_berkas, "hapus_berkas",
                        lambda *a, **k: (kejadian.append("hapus"), asli_hapus(*a, **k))[1])
    monkeypatch.setattr(retensi, "tandai_dihapus",
                        lambda *a, **k: (kejadian.append("tandai"), asli_tandai(*a, **k))[1])

    retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert kejadian == ["hapus", "tandai"]


def test_tandai_gagal_setelah_berkas_terhapus_diselesaikan_sapu_berikutnya(kon, folder, monkeypatch):
    _, _, _, nama = _putuskan(kon, folder)
    asli = retensi.tandai_dihapus

    def gagal(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(retensi, "tandai_dihapus", gagal)
    pertama = retensi.sapu(kon, folder, TEPAT_30_HARI)
    assert (pertama.gagal, pertama.berkas_dihapus, pertama.ditandai) == (1, 1, 0) and not _ada(folder, nama)

    monkeypatch.setattr(retensi, "tandai_dihapus", asli)
    kedua = retensi.sapu(kon, folder, TEPAT_30_HARI)
    assert (kedua.ditandai, kedua.berkas_sudah_hilang, kedua.gagal) == (1, 1, 0)


def test_gagal_hapus_satu_berkas_tidak_menandai_dan_tidak_menghentikan_yang_lain(kon, folder, monkeypatch):
    _, _, id_a, nama_a = _putuskan(kon, folder)
    _, _, id_b, nama_b = _putuskan(kon, folder)
    asli = retensi.bukti_berkas.hapus_berkas

    def selektif(nama, folder_=None):
        if nama == nama_a:
            raise PermissionError("izin")
        return asli(nama, folder_)

    monkeypatch.setattr(retensi.bukti_berkas, "hapus_berkas", selektif)
    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert (hasil.gagal, hasil.ditandai) == (1, 1) and _ada(folder, nama_a) and not _ada(folder, nama_b)
    assert [r[0] for r in kon.execute("SELECT bukti_id FROM harian_bukti_hapus")] == [id_b]


def test_subfolder_tidak_ada_dengan_bukti_kedaluwarsa_tidak_menandai_apa_pun(kon, folder, tmp_path):
    _, _, _, nama = _putuskan(kon, folder)

    hasil = retensi.sapu(kon, tmp_path / "salah", TEPAT_30_HARI)

    assert (hasil.gagal, hasil.ditandai, hasil.berkas_sudah_hilang) == (1, 0, 0)
    assert _ada(folder, nama) and _tertanda(kon) == 0


def test_sisa_sementara_lama_di_subfolder_dibuang_yang_baru_tidak(kon, folder):
    sub = folder / berkas_harian.SUBFOLDER
    lama, baru = sub / (".tmp-" + "a" * 32), sub / (".tmp-" + "b" * 32)
    epoch = datetime.strptime(TEPAT_30_HARI, FORMAT).replace(tzinfo=timezone.utc).timestamp()
    for jalur_, umur in ((lama, 7200), (baru, 60)):
        jalur_.write_bytes(b"sisa")
        os.utime(jalur_, (epoch - umur, epoch - umur))

    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert hasil.sementara_dibersihkan == 1 and not lama.exists() and baru.exists()


def test_berkas_tak_dirujuk_di_subfolder_tidak_pernah_dibuang_sebagai_yatim(kon, folder):
    asing = folder / berkas_harian.SUBFOLDER / ("c" * 32)
    asing.write_bytes(b"x")
    os.utime(asing, (1, 1))

    hasil = retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert asing.exists() and hasil.berkas_dihapus == 0


def test_sapu_hanya_menyentuh_subfolder_harian_bukan_folder_induk(kon, folder):
    _putuskan(kon, folder)
    induk = folder / ("d" * 32)
    induk.write_bytes(b"paket coba")
    os.utime(induk, (1, 1))

    retensi.sapu(kon, folder, TEPAT_30_HARI)

    assert induk.exists()


# --- skema penanda ------------------------------------------------------------------------------

def test_penanda_bukti_belum_diputuskan_ditolak_skema(kon, folder):
    _, _, bukti_id, _ = _tagihan_dan_bukti(kon, folder)

    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO harian_bukti_hapus(bukti_id, dihapus) VALUES (?, ?)", (bukti_id, T0))


def test_penanda_append_only_dan_tidak_bisa_ditimpa(kon, folder):
    _, _, bukti_id, _ = _putuskan(kon, folder)
    retensi.sapu(kon, folder, TEPAT_30_HARI)

    for sql in ("UPDATE harian_bukti_hapus SET dihapus='2030-01-01T00:00:00'", "DELETE FROM harian_bukti_hapus",
                "INSERT OR REPLACE INTO harian_bukti_hapus(bukti_id, dihapus) VALUES (%d, '2030-01-01T00:00:00')"
                % bukti_id):
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(sql)


def test_tandai_dihapus_menolak_bukti_belum_kedaluwarsa_dan_id_tak_dikenal(kon, folder):
    _, _, bukti_id, _ = _putuskan(kon, folder)

    with pytest.raises(h.LanggananKonflik):
        retensi.tandai_dihapus(kon, bukti_id, KURANG_SEDETIK)
    with pytest.raises(d.PesananTidakDitemukan):
        retensi.tandai_dihapus(kon, 9999, TEPAT_30_HARI)


# --- jalur CLI cron yang sama (pesanan_retensi.main) ------------------------------------------------

@pytest.fixture
def admin_db(tmp_path):
    return siapkan_db_transfer(tmp_path)  # admin-control.db di folder yang sama dengan latihan.db


def _jalankan(admin_db, folder, *ekstra, sekarang=TEPAT_30_HARI):
    return pr.main(["--database", str(admin_db), "--folder", str(folder), *ekstra], sekarang=sekarang)


def test_cli_menyapu_langganan_lewat_jalur_pesanan_retensi_dengan_db_belajar_di_samping(
        admin_db, jalur, kon, folder, capsys):
    _, _, _, nama = _putuskan(kon, folder)
    kon.commit()

    kode = _jalankan(admin_db, folder)
    keluar = capsys.readouterr().out

    assert kode == 0 and not _ada(folder, nama)
    assert "langganan Latihan Harian" in keluar and "1 bukti ditandai" in keluar and nama not in keluar
    with database.buka(jalur) as baca:
        assert _tertanda(baca) == 1


def test_cli_opsi_database_belajar_mengalahkan_env_dan_samping(admin_db, tmp_path, folder, monkeypatch):
    lain = tmp_path / "lain" / "belajar-pilihan.db"
    lain.parent.mkdir()
    database.siapkan(lain)
    with database.buka(lain) as pilihan:
        _, _, _, nama = _putuskan(pilihan, folder)
    monkeypatch.setenv("OSN_BERKAS_DB", str(tmp_path / "tidak-ada-env.db"))

    assert _jalankan(admin_db, folder, "--database-belajar", str(lain)) == 0
    assert not _ada(folder, nama)


def test_cli_env_osn_berkas_db_dipakai_bila_tanpa_opsi_dan_mengalahkan_samping(admin_db, tmp_path, folder, monkeypatch):
    lain = tmp_path / "lain" / "belajar-env.db"
    lain.parent.mkdir()
    database.siapkan(lain)
    with database.buka(lain) as pilihan:
        _, _, _, nama = _putuskan(pilihan, folder)
    monkeypatch.setenv("OSN_BERKAS_DB", str(lain))

    assert _jalankan(admin_db, folder) == 0
    assert not _ada(folder, nama)


def test_cli_tanpa_db_belajar_dilewati_tanpa_membuat_berkas_dan_transfer_tetap_jalan(admin_db, tmp_path, folder, capsys,
                                                                                    monkeypatch):
    baku = tmp_path / "kode" / "latihan.db"  # tiruan database.BAWAAN: tidak boleh dipakai sebagai cadangan
    baku.parent.mkdir()
    monkeypatch.setattr(database, "BAWAAN", baku)

    kode = _jalankan(admin_db, folder)
    keluar = capsys.readouterr().out

    assert kode == 0 and "dilewati" in keluar and "Sapu retensi selesai" in keluar
    assert not (tmp_path / "latihan.db").exists() and not baku.exists()


def test_cli_db_belajar_tanpa_tabel_penanda_dilewati_tanpa_membuat_tabel(admin_db, tmp_path, folder, capsys):
    kosong = tmp_path / "latihan.db"
    sqlite3.connect(kosong).close()

    assert _jalankan(admin_db, folder) == 0
    assert "dilewati" in capsys.readouterr().out
    with sqlite3.connect(kosong) as baca:
        assert baca.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0


def test_cli_gagal_langganan_keluar_1_dan_ledger_belajar_utuh(admin_db, jalur, kon, folder, tmp_path, capsys):
    _, _, _, nama = _putuskan(kon, folder)
    kon.commit()
    (folder / berkas_harian.SUBFOLDER).rename(folder / "dipindah")  # subfolder harian tidak ada

    kode = _jalankan(admin_db, folder)
    keluar = capsys.readouterr()

    assert kode == pr.EXIT_SEBAGIAN and "1 gagal" in keluar.out and "OSN_DIREKTORI_BUKTI" in keluar.err
    with database.buka(jalur) as baca:
        assert _tertanda(baca) == 0


def test_cli_ringkasan_langganan_tanpa_nama_berkas_atau_id(admin_db, kon, folder, capsys):
    _, order, _, nama = _putuskan(kon, folder)
    kon.commit()

    _jalankan(admin_db, folder)

    keluar = capsys.readouterr().out
    assert nama not in keluar and order not in keluar
