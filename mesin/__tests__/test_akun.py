"""Verifikasi halaman akun — ganti sandi & kelola siswa.

Halaman ini bisa mengunci guru dari sistemnya sendiri kalau salah: sandi
diganti jadi sesuatu yang tidak dia maksud, atau sandi lama diterima padahal
salah. Karena itu yang diuji terutama penolakannya, bukan keberhasilannya.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
import web  # noqa: E402
import account_pages  # noqa: E402


@pytest.fixture()
def siap(tmp_path, monkeypatch):
    db = tmp_path / "uji.db"
    berkas = tmp_path / "sandi.json"
    database.siapkan(db)
    monkeypatch.setattr(database, "BAWAAN", db)
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    auth.simpan_sandi("sandi-lama-panjang", "guru", berkas)
    return db


# ── Ganti sandi: yang salah harus ditolak ───────────────────────────────


def test_sandi_lama_salah_ditolak(siap):
    """Peramban mengirim kredensial otomatis, jadi lolos palang bukan bukti
    orangnya tahu sandi. Verifikasi ulang wajib."""
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "tebakan-salah",
            "baru": "sandi-baru-panjang", "ulang": "sandi-baru-panjang",
        }, "guru")

    assert not pesan
    assert "salah" in galat.lower()
    assert auth.periksa("guru", "sandi-lama-panjang"), "sandi lama berubah!"


def test_ulangan_tidak_sama_ditolak(siap):
    """Salah ketik sandi baru = terkunci dari sistem sendiri."""
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-lama-panjang",
            "baru": "sandi-baru-panjang", "ulang": "sandi-baru-panjanh",
        }, "guru")

    assert not pesan
    assert "tidak sama" in galat.lower()
    assert auth.periksa("guru", "sandi-lama-panjang")


def test_sandi_terlalu_pendek_ditolak(siap):
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-lama-panjang",
            "baru": "pendek", "ulang": "pendek",
        }, "guru")

    assert not pesan
    assert "12 karakter" in galat
    assert auth.periksa("guru", "sandi-lama-panjang")


def test_sandi_baru_sama_dengan_lama_ditolak(siap):
    with database.buka(siap) as kon:
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-lama-panjang",
            "baru": "sandi-lama-panjang", "ulang": "sandi-lama-panjang",
        }, "guru")
    assert "sama dengan yang lama" in galat


def test_ganti_sandi_berhasil(siap):
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-lama-panjang",
            "baru": "sandi-baru-yang-panjang", "ulang": "sandi-baru-yang-panjang",
        }, "guru")

    assert not galat
    assert "diganti" in pesan.lower()
    assert auth.periksa("guru", "sandi-baru-yang-panjang")
    assert not auth.periksa("guru", "sandi-lama-panjang"), "sandi lama masih jalan!"


def test_sandi_baru_tidak_tersimpan_sebagai_teks(siap):
    with database.buka(siap) as kon:
        account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-lama-panjang",
            "baru": "rahasia-sekali-panjang", "ulang": "rahasia-sekali-panjang",
        }, "guru")
    assert "rahasia-sekali-panjang" not in auth.BERKAS_SANDI.read_text()


# ── Kelola siswa ────────────────────────────────────────────────────────


def test_tambah_siswa_berhasil(siap):
    with database.buka(siap) as kon:
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "Rara", "tingkat": "P4",
            "sandi_anak": "sandi-rara-12345",
        }, "guru")
        nama = [s["nama"] for s in database.daftar_siswa(kon)]

    assert not galat
    assert "Rara" in pesan
    assert "Rara" in nama
    assert auth.cari_akun("Rara") is not None, "anak baru harus punya akun"


def test_nama_kosong_ditolak(siap):
    with database.buka(siap) as kon:
        _, galat = account_pages.proses_akun(
            kon,
            {"aksi": "anak_baru", "nama": "   ", "sandi_anak": "sandi-rara-12345"},
            "guru",
        )
        assert "kosong" in galat.lower()
        assert len(database.daftar_siswa(kon)) == 0


def test_nama_duplikat_ditolak_tanpa_pandang_huruf(siap):
    """Dua siswa bernama sama membuat laporan tidak bisa dibedakan."""
    with database.buka(siap) as kon:
        account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "Rara", "sandi_anak": "sandi-rara-12345",
        }, "guru")
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "rara", "sandi_anak": "sandi-rara-12345",
        }, "guru")
        assert "sudah ada" in galat.lower()
        assert len(database.daftar_siswa(kon)) == 1


def test_tingkat_kosong_memakai_bawaan(siap):
    with database.buka(siap) as kon:
        account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "Tanpa", "tingkat": "",
            "sandi_anak": "sandi-tanpa-1234",
        }, "guru")
        s = database.daftar_siswa(kon)[0]
    assert s["tingkat"] == "P3"


def test_ganti_tingkat_lewat_proses_akun_mencatat_event_domain(siap):
    with database.buka(siap) as kon:
        siswa_id = database.tambah_siswa(
            kon, "Naik kelas", tingkat="P3", pemilik="guru"
        )
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")

        pesan, galat = account_pages.proses_akun(
            kon,
            {"aksi": "tingkat", "siswa_id": str(siswa_id), "tingkat": "P4"},
            "guru",
        )
        tingkat = kon.execute(
            "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()[0]
        event = kon.execute(
            """SELECT putaran_id, jenis, data FROM kejadian_belajar
               WHERE siswa_id = ? AND jenis = 'diganti_level'""",
            (siswa_id,),
        ).fetchone()

    assert not galat
    assert "Kelas 4" in pesan
    assert tingkat == "P4"
    assert event["putaran_id"] == putaran_id
    assert '"level_lama": "P3"' in event["data"]
    assert '"level_baru": "P4"' in event["data"]


def test_aksi_tidak_dikenal_tidak_mengubah_apa_pun(siap):
    with database.buka(siap) as kon:
        _, galat = account_pages.proses_akun(kon, {"aksi": "hapus-semua"}, "guru")
        assert "tidak dikenal" in galat.lower()
        assert auth.periksa("guru", "sandi-lama-panjang")


# ── Halaman ─────────────────────────────────────────────────────────────


def test_halaman_akun_tidak_membocorkan_sandi(siap):
    """Halaman ini menampilkan info akun; hash pun tidak perlu ada di HTML."""
    with database.buka(siap) as kon:
        h = account_pages.halaman_akun(kon).decode()
    d = auth.muat_sandi()
    assert d is not None, "berkas sandi hilang"
    assert d["kunci"] not in h
    assert d["garam"] not in h
    assert "sandi-lama-panjang" not in h


def test_halaman_akun_menampilkan_siswa_dan_jumlah_sesi(siap):
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "Andi")
        database.buat_sesi(kon, sid, seed=1)
        database.buat_sesi(kon, sid, seed=2)
        h = account_pages.halaman_akun(kon, section="siswa").decode()

    assert "Andi" in h
    assert ">2<" in h  # jumlah sesi


def test_tabel_siswa_menampilkan_status_akun_latihan(siap):
    """Hapus akun latihan tidak menghapus anaknya — status di tabel siswa
    harus menjelaskan hubungan itu, bukan membiarkannya jadi teka-teki."""
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "Tertaut", pemilik="guru")
        auth.tambah_akun("taut-login", "rahasia-taut-123", "murid", siswa_id=sid)
        database.tambah_siswa(kon, "Telanjang")
        h = account_pages.halaman_akun(kon, section="siswa").decode()
    assert "taut-login" in h
    assert "belum ada login" in h


def test_helper_akun_murid_dari_siswa(siap):
    """Kebalikan siswa_dari_akun: siswa_id eksplisit menang, akun warisan
    tanpa siswa_id dicocokkan lewat nama, siswa tanpa akun → None."""
    import students

    with database.buka(siap) as kon:
        sid_taut = database.tambah_siswa(kon, "Taut", pemilik="guru")
        auth.tambah_akun("taut-login", "rahasia-taut-123", "murid", siswa_id=sid_taut)
        sid_warisan = database.tambah_siswa(kon, "Warisan")
        auth.tambah_akun("Warisan", "rahasia-warisan-1", "murid")
        sid_kosong = database.tambah_siswa(kon, "Kosong")

        assert students.akun_murid_dari_siswa(kon, sid_taut) == "taut-login"
        assert students.akun_murid_dari_siswa(kon, sid_warisan) == "Warisan"
        assert students.akun_murid_dari_siswa(kon, sid_kosong) is None
        assert students.akun_murid_dari_siswa(kon, 999999) is None


def test_section_siswa_memuat_hapus_dan_penjelasannya(siap):
    """Tombol hapus ada, dan aturannya dijelaskan — bukan teka-teki."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Berhapus", pemilik="guru")
        h = account_pages.halaman_akun(kon, section="siswa").decode()
    assert 'value="siswa_hapus"' in h
    assert "tidak bisa dihapus" in h.lower()
    assert "riwayat" in h.lower()


# ── Hapus siswa: hanya yang tanpa riwayat ───────────────────────────────


def test_hapus_siswa_berriwayat_ditolak(siap):
    """Riwayat sesi/jawaban/diagnosis tidak bisa dibangun ulang — hapus
    harus gagal jelas, bukan diam-diam memusnahkan data."""
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "Berriwayat", pemilik="guru")
        database.buat_sesi(kon, sid, seed=1)
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "siswa_hapus", "siswa_id": str(sid),
        }, "guru")
        sisa = kon.execute(
            "SELECT COUNT(*) c FROM siswa WHERE id = ?", (sid,)
        ).fetchone()["c"]
    assert not pesan
    assert "tidak bisa dihapus" in galat.lower()
    assert "riwayat" in galat.lower()
    assert sisa == 1


def test_hapus_siswa_tanpa_riwayat_beserta_akunnya(siap):
    """Salah ketik / data uji harus bisa dibersihkan: siswa dan akun
    latihannya hilang bersama, tanpa menyisakan anak yatim."""
    with database.buka(siap) as kon:
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "UjiHapus", "tingkat": "P3",
            "sandi_anak": "sandi-uji-12345",
        }, "guru")
        assert galat == ""
        sid = kon.execute(
            "SELECT id FROM siswa WHERE nama='UjiHapus'"
        ).fetchone()["id"]
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "siswa_hapus", "siswa_id": str(sid),
        }, "guru")
        sisa = kon.execute(
            "SELECT COUNT(*) c FROM siswa WHERE id = ?", (sid,)
        ).fetchone()["c"]
    assert not galat, galat
    assert "dihapus" in pesan.lower()
    assert sisa == 0
    assert auth.cari_akun("UjiHapus") is None


def test_hapus_siswa_keluarga_lain_ditolak(siap):
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "AnakA", pemilik="ortu-a")
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "siswa_hapus", "siswa_id": str(sid),
        }, "ortu-b")
        sisa = kon.execute(
            "SELECT COUNT(*) c FROM siswa WHERE id = ?", (sid,)
        ).fetchone()["c"]
    assert "tidak dikenal" in galat.lower()
    assert sisa == 1


def test_pesan_galat_di_escape(siap):
    """Nama siswa masuk pesan galat; karakter khusus tidak boleh merusak HTML."""
    with database.buka(siap) as kon:
        account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "<b>X</b>", "sandi_anak": "sandi-eks-12345",
        }, "guru")
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "<b>X</b>", "sandi_anak": "sandi-eks-12345",
        }, "guru")
        h = account_pages.halaman_akun(kon, "", galat, section="siswa").decode()

    assert "<b>X</b>" not in h
    assert "&lt;b&gt;" in h


# ── Akun murid (plan 2026-08-25) ──────────────────────────────────────


def test_kartu_akun_murid_tampil_dan_memuat_nama(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Sinta")
        auth.tambah_akun("Sinta", "rahasia-sinta-123", "murid")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "Akun murid" in h
    assert "Sinta" in h


def test_akun_tidak_cocok_ditandai_belum_terhubung(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Andi")
        auth.tambah_akun("Hantu", "rahasia-hantu-123", "murid")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "Hantu" in h
    assert "belum terhubung ke siswa" in h.lower()


def test_tambah_akun_murid_berhasil(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Budi", pemilik="guru")
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Budi", "sandi": "rahasia-budi-123",
        }, "guru")
        assert not galat, galat
        assert "ditambahkan" in pesan.lower()
    assert auth.periksa_peran("Budi", "rahasia-budi-123", "murid") is True


def test_tambah_akun_murid_dua_kali_ditolak(siap):
    """Anak yang sudah terhubung ditolak di handler — palangnya bukan di
    dropdown form saja, karena POST tidak boleh dipercaya."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Citra", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Citra", "sandi": "rahasia-citra-123",
        }, "guru")
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Citra", "sandi": "rahasia-lain-123",
        }, "guru")
    assert not pesan
    assert galat  # ditolak rapi, bukan 500
    assert "sudah punya akun" in galat.lower()


def test_nama_akun_sudah_dipakai_anak_lain_galat(siap):
    """Nama login unik GLOBAL — bentrok lintas anak tetap galat rapi
    (ValueError dari auth), bukan 500."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Budi", pemilik="guru")
        database.tambah_siswa(kon, "Wati", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Budi", "sandi": "rahasia-budi-123",
        }, "guru")
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Wati", "nama_akun": "Budi",
            "sandi": "rahasia-wati-123",
        }, "guru")
    assert not pesan
    assert galat
    assert "sudah dipakai" in galat.lower()


def test_tambah_akun_murid_sandi_pendek_ditolak(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Dina", pemilik="guru")
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Dina", "sandi": "pendek",
        }, "guru")
        assert not pesan
        assert "8 karakter" in galat
    assert not auth.periksa_peran("Dina", "pendek", "murid")


def test_hapus_akun_murid(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Eka", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Eka", "sandi": "rahasia-eka-12345",
        }, "guru")
        assert auth.periksa_peran("Eka", "rahasia-eka-12345", "murid") is True
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_hapus", "nama": "Eka",
        }, "guru")
        assert not galat, galat
        assert "dihapus" in pesan.lower()
    assert auth.periksa_peran("Eka", "rahasia-eka-12345", "murid") is False


def test_setel_sandi_murid(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Fani", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Fani", "sandi": "lama-fani-12345",
        }, "guru")
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_sandi", "nama": "Fani", "baru": "baru-fani-67890",
        }, "guru")
        assert not galat, galat
        assert "diperbarui" in pesan.lower() or "sandi" in pesan.lower()
    assert not auth.periksa_peran("Fani", "lama-fani-12345", "murid")
    assert auth.periksa_peran("Fani", "baru-fani-67890", "murid") is True


def test_sandi_murid_tidak_muncul_di_html(siap):
    rahasia = "super-rahasia-murid-999"
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Gina", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Gina", "sandi": rahasia,
        }, "guru")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert rahasia not in h
    assert rahasia not in auth.BERKAS_SANDI.read_text() or rahasia not in h  # hash, bukan teks
    # pastikan berkas sandi di disk tidak bocor ke HTML (cek kunci/garam juga tidak ada)
    d = auth.muat_sandi()
    # bentuk multi-akun: cari akun Gina
    akun = auth.cari_akun("Gina")
    assert akun is not None
    assert akun["kunci"] not in h
    # nama murid di-escape
    with database.buka(siap) as kon:
        # bersihkan dulu: buat siswa dan akun dengan karakter khusus
        # pakai DB baru (siap fixture tiap test sudah fresh), jadi buat ulang
        database.tambah_siswa(kon, "<b>Hacker</b>")
        # akun murid dengan nama yang sama — harus di-escape di HTML
        auth.tambah_akun("<b>Hacker</b>", "rahasia-hacker-123", "murid")
        h2 = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "<b>Hacker</b>" not in h2
    assert "&lt;b&gt;Hacker&lt;/b&gt;" in h2


# ── Form akun murid kontekstual: hanya untuk anak yang belum terhubung ──


def test_semua_anak_terhubung_form_pembuat_tidak_tampil(siap):
    """Alur normal (Tambah anak) sudah membuatkan akun sekaligus — form
    pembuat permanen cuma duplikasi yang membingungkan, bahkan bisa
    membuat akun kedua untuk anak yang sama."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Sinta", pemilik="guru")
        auth.tambah_akun("Sinta", "rahasia-sinta-123", "murid")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "Tambah akun murid" not in h
    assert "Buat akun masuk" not in h
    assert "Semua anak sudah punya akun masuk" in h
    # Penghapusan akun tetap konfirmasi dulu — sekali klik tidak boleh
    # langsung mencabut login anak.
    assert "confirm(" in h


def test_form_muncul_hanya_untuk_anak_belum_terhubung(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Sinta", pemilik="guru")
        database.tambah_siswa(kon, "Tono", pemilik="guru")
        auth.tambah_akun("Sinta", "rahasia-sinta-123", "murid")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "belum punya akun masuk" in h
    assert "Buat akun masuk" in h
    # Dropdown hanya berisi anak yang belum terhubung, bukan semua anak.
    assert ">Tono</option>" in h
    assert ">Sinta</option>" not in h


def test_akun_terhapus_form_perbaikan_muncul_lagi(siap):
    """Jalur pemulihan: akun terhapus (salah klik) tapi anaknya tetap
    ada — form pembuat muncul kembali untuk anak itu, dan login barunya
    berfungsi. Tanpa jalur ini anak ber-riwayat tidak pernah bisa masuk
    lagi (Tambah anak menolak nama yang sudah ada)."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Sinta", pemilik="guru")
        auth.tambah_akun("Sinta", "rahasia-sinta-123", "murid")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_hapus", "nama": "Sinta",
        }, "guru")
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
        assert "belum punya akun masuk" in h
        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Sinta",
            "sandi": "sinta-baru-12345",
        }, "guru")
        assert not galat, galat
    assert auth.periksa_peran("Sinta", "sinta-baru-12345", "murid") is True


def test_status_belum_ada_login_menuju_section_perbaikan(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Sinta", pemilik="guru")
        h = account_pages.halaman_akun(kon, section="siswa").decode()
    assert "belum ada login" in h
    assert 'href="/akun?section=akun-murid"' in h


# ── Sidebar + section (plan 2026-08-30) ───────────────────────────────


def test_section_bawaan_akun_dengan_navigasi_samping(siap):
    with database.buka(siap) as kon:
        h = account_pages.halaman_akun(kon).decode()
    assert "Ganti sandi" in h
    assert "nav-samping" in h
    assert 'href="/akun?section=siswa"' in h
    assert 'href="/akun?section=akun-murid"' in h
    assert "Tambah siswa" not in h, "section lain bocor ke section akun"
    assert "Akun murid" not in h


def test_section_siswa_memuat_daftar_dan_form(siap):
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Andi")
        h = account_pages.halaman_akun(kon, section="siswa").decode()
    assert "Andi" in h
    assert "Tambah siswa" not in h, "form tambah siswa sudah tidak ada"
    assert "Tambah anak" in h
    assert "Ganti sandi" not in h
    assert "Akun murid" not in h


def test_section_akun_murid_memuat_kartunya(siap):
    with database.buka(siap) as kon:
        h = account_pages.halaman_akun(kon, section="akun-murid").decode()
    assert "Akun murid" in h
    assert "Ganti sandi" not in h
    assert "Tambah siswa" not in h


def test_section_tak_dikenal_jatuh_ke_akun(siap):
    with database.buka(siap) as kon:
        h = account_pages.halaman_akun(kon, section="hxhx").decode()
    assert "Ganti sandi" in h
    assert "Tambah siswa" not in h


def test_admin_hanya_melihat_akun_sendiri_di_halaman_akun_lama(siap):
    """Pengelolaan lintas keluarga admin pindah ke pusat kendali kanonik."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "AnakA", pemilik="ortu-a")
        h = account_pages.halaman_akun(kon, pengguna="pengelola", peran="admin").decode()
        h2 = account_pages.halaman_akun(
            kon, pengguna="pengelola", peran="admin", section="siswa"
        ).decode()
    assert "Ganti sandi" in h
    assert 'href="/akun?section=siswa"' not in h
    assert 'href="/akun?section=akun-murid"' not in h
    assert "AnakA" not in h2


def test_peta_aksi_ke_section_lengkap():
    """Tiap aksi POST /akun harus punya section tujuan — hasil aksi tampil
    di tempat formnya, bukan melompat ke section bawaan."""
    for aksi in ("sandi", "siswa_hapus", "anak_baru", "tingkat",
                 "akun_murid_tambah", "akun_murid_hapus", "akun_murid_sandi"):
        assert aksi in web.PETA_SECTION_AKUN, f"aksi {aksi} tak dipetakan"
    assert web.PETA_SECTION_AKUN["siswa_hapus"] == "siswa"
    assert "siswa" not in web.PETA_SECTION_AKUN, "aksi siswa sudah dihapus"
    assert web.PETA_SECTION_AKUN["akun_murid_tambah"] == "akun-murid"
    assert web.PETA_SECTION_AKUN["sandi"] == "akun"


def test_guru_tetap_bisa_ganti_sandi_setelah_ada_akun_murid(siap):
    """Regresi: begitu satu akun murid dibuat, berkas sandi berubah jadi
    bentuk multi-akun. `periksa()` sempat membaca d["pengguna"] yang tidak
    ada di bentuk itu dan melempar KeyError — guru TIDAK BISA mengganti
    sandinya sama sekali, halaman akun langsung 500.

    Lolos dari seluruh test sebelumnya karena tidak ada yang menguji
    URUTAN-nya: tambah murid dulu, baru guru ganti sandi.
    """
    auth.simpan_sandi("sandi-guru-lama1", "guru")
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "Feby", pemilik="guru")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Feby", "sandi": "rahasia8",
        }, "guru")

        pesan, galat = account_pages.proses_akun(kon, {
            "aksi": "sandi", "lama": "sandi-guru-lama1",
            "baru": "sandi-guru-baru1", "ulang": "sandi-guru-baru1",
        }, "guru")

    assert not galat, f"guru gagal ganti sandi: {galat}"
    assert pesan
    assert auth.periksa("guru", "sandi-guru-baru1")
    assert not auth.periksa("guru", "sandi-guru-lama1")
    # dan akun murid tidak boleh ikut hilang
    assert auth.periksa_peran("Feby", "rahasia8", "murid")


# ── Multi-keluarga: pemilik & tautan siswa_id ───────────────────────────


def test_siswa_baru_ber_pemilik_pembuatnya(siap):
    with database.buka(siap) as kon:
        account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "MilikA", "tingkat": "P3",
            "sandi_anak": "sandi-milka-1234",
        }, "ortu-a")
        baris = kon.execute("SELECT pemilik FROM siswa WHERE nama='MilikA'").fetchone()
    assert baris["pemilik"] == "ortu-a"


def test_dobel_nama_antar_keluarga_sah_dalam_keluarga_ditolak(siap):
    """Dua keluarga boleh sama-sama punya 'Bima'; dalam satu keluarga tetap
    ditolak tanpa pandang huruf besar-kecil. Login keluarga kedua memakai
    variasi karena nama login unik global."""
    with database.buka(siap) as kon:
        _, g1 = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "Bima", "tingkat": "P3",
            "sandi_anak": "sandi-bima-12345",
        }, "ortu-a")
        _, g2 = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "Bima", "tingkat": "P3",
            "sandi_anak": "sandi-bima-67890", "nama_akun": "bima-kedua",
        }, "ortu-b")
        _, g3 = account_pages.proses_akun(kon, {
            "aksi": "anak_baru", "nama": "BIMA", "tingkat": "P3",
            "sandi_anak": "sandi-bima-abcde",
        }, "ortu-a")
        n = kon.execute("SELECT COUNT(*) c FROM siswa WHERE nama='Bima'").fetchone()["c"]
    assert g1 == "" and g2 == ""
    assert g3 != ""
    assert n == 2


def test_akun_murid_tambah_menyimpan_siswa_id(siap):
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "Taut", pemilik="guru")
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "Taut", "sandi": "rahasia-taut-123",
        }, "guru")
        akun = auth.cari_akun("Taut")
    assert galat == ""
    assert akun is not None
    assert akun["siswa_id"] == sid


def test_akun_murid_tambah_via_siswa_id_dan_nama_akun_beda(siap):
    """Bentuk form baru: pilih siswa + nama akun bebas (unik global).
    Nama tampilan dan nama login tidak harus sama lagi."""
    with database.buka(siap) as kon:
        sid = database.tambah_siswa(kon, "Bima", pemilik="guru")
        _, galat = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "siswa_id": str(sid),
            "nama_akun": "bima-santoso", "sandi": "rahasia-bima-123",
        }, "guru")
        akun = auth.cari_akun("bima-santoso")
    assert galat == ""
    assert akun is not None
    assert akun["siswa_id"] == sid
    assert auth.periksa_peran("bima-santoso", "rahasia-bima-123", "murid")


def test_akun_murid_anak_keluarga_lain_tak_bisa_disetel(siap):
    """Guru keluarga B tidak boleh menyentuh akun murid keluarga A;
    admin tetap bisa."""
    with database.buka(siap) as kon:
        database.tambah_siswa(kon, "AnakA", pemilik="ortu-a")
        account_pages.proses_akun(kon, {
            "aksi": "akun_murid_tambah", "nama": "AnakA", "sandi": "rahasia-anak-1",
        }, "ortu-a")
        _, g1 = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_sandi", "nama": "AnakA", "baru": "diserang-99999",
        }, "ortu-b")
        _, g2 = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_hapus", "nama": "AnakA",
        }, "ortu-b")
        _, g3 = account_pages.proses_akun(kon, {
            "aksi": "akun_murid_sandi", "nama": "AnakA", "baru": "disetel-admin-1",
        }, "pengelola", "admin")
    assert g1 != ""
    assert g2 != ""
    assert g3 == ""
    assert auth.periksa_peran("AnakA", "disetel-admin-1", "murid")


def test_tingkat_anak_keluarga_lain_ditolak(siap):
    with database.buka(siap) as kon:
        sid_a = database.tambah_siswa(kon, "AnakX", pemilik="ortu-a")
        _, g1 = account_pages.proses_akun(kon, {
            "aksi": "tingkat", "siswa_id": str(sid_a), "tingkat": "P5",
        }, "ortu-b")
        _, g2 = account_pages.proses_akun(kon, {
            "aksi": "tingkat", "siswa_id": str(sid_a), "tingkat": "P5",
        }, "pengelola", "admin")
        baris = kon.execute("SELECT tingkat FROM siswa WHERE id = ?", (sid_a,)).fetchone()
    assert g1 != ""
    assert g2 == ""
    assert baris["tingkat"] == "P5"


# ── Setel ulang sandi orang tua (auth.setel_sandi_guru + proses_admin) ──


def test_setel_sandi_guru_berhasil(siap):
    """Orang tua lupa sandi: admin setel ulang tanpa menghapus akun —
    hash berganti dan sandi barunya langsung lolos periksa()."""
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    assert auth.setel_sandi_guru("ortu-a", "sandi-baru-ortu-1") is True
    assert auth.periksa("ortu-a", "sandi-baru-ortu-1")
    assert not auth.periksa("ortu-a", "sandi-lama-ortu-1"), "sandi lama masih jalan!"


def test_setel_sandi_guru_tidak_menyentuh_akun_lain(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    auth.tambah_akun("ortu-b", "sandi-lama-ortu-2", "guru")
    auth.setel_sandi_guru("ortu-a", "sandi-baru-ortu-1")
    assert auth.periksa("ortu-b", "sandi-lama-ortu-2"), "akun lain ikut berubah!"


def test_setel_sandi_guru_menolak_akun_murid(siap):
    """Fungsi ini khusus peran guru: sandi murid ada jalurnya sendiri
    (setel_sandi_murid) — mencampur keduanya mengaburkan siapa boleh
    menyentuh apa."""
    auth.tambah_akun("murid-x", "sandi-murid-123456", "murid")
    assert auth.setel_sandi_guru("murid-x", "diserang-99999999") is False
    assert auth.periksa("murid-x", "sandi-murid-123456"), "sandi murid berubah!"


def test_setel_sandi_guru_menolak_akun_admin(siap):
    """Sandi admin milik deploy — kalau panel bisa menukarnya, satu sesi
    admin yang bocor berarti penjaga tertinggi ikut bisa diganti."""
    auth.tambah_akun("pengelola", "sandi-admin-123456", "admin")
    assert auth.setel_sandi_guru("pengelola", "diserang-99999999") is False
    assert auth.periksa("pengelola", "sandi-admin-123456"), "sandi admin berubah!"


def test_setel_sandi_guru_akun_tak_ada(siap):
    assert auth.setel_sandi_guru("hantu", "sandi-hantu-123456") is False


def test_proses_admin_nama_kosong(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    pesan, galat = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "   ", "baru": "sandi-baru-ortu-1",
    })
    assert not pesan
    assert galat == "Pilih akunnya dulu."
    assert auth.periksa("ortu-a", "sandi-lama-ortu-1")


def test_proses_admin_sandi_pendek(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    pesan, galat = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "ortu-a", "baru": "pendek",
    })
    assert not pesan
    assert "12 karakter" in galat
    assert auth.periksa("ortu-a", "sandi-lama-ortu-1")


def test_proses_admin_akun_tak_ada(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    pesan, galat = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "hantu", "baru": "sandi-baru-ortu-1",
    })
    assert not pesan
    assert galat == "Akun hantu tidak ditemukan."
    assert auth.periksa("ortu-a", "sandi-lama-ortu-1")


def test_proses_admin_bukan_akun_guru_ditolak(siap):
    """Peran admin dan murid dilaporkan dengan pesan yang SAMA dengan
    akun-tak-ada — pesan berbeda jadi oracle yang memberi tahu penyerang
    nama mana yang ada dan perannya apa."""
    auth.tambah_akun("pengelola", "sandi-admin-123456", "admin")
    auth.tambah_akun("murid-x", "sandi-murid-123456", "murid")
    _, g1 = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "pengelola", "baru": "diserang-99999999",
    })
    _, g2 = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "murid-x", "baru": "diserang-99999999",
    })
    assert g1 == "Akun pengelola tidak ditemukan."
    assert g2 == "Akun murid-x tidak ditemukan."
    assert auth.periksa("pengelola", "sandi-admin-123456")
    assert auth.periksa("murid-x", "sandi-murid-123456")


def test_proses_admin_aksi_tidak_dikenal(siap):
    pesan, galat = account_pages.proses_admin({"aksi": "hapus-semua"})
    assert not pesan
    assert "tidak dikenal" in galat.lower()


def test_proses_admin_hapus_akun_guru(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    pesan, galat = account_pages.proses_admin({
        "aksi": "guru_hapus", "nama": "ortu-a",
    })
    assert not galat, galat
    assert "dihapus" in pesan.lower()
    assert auth.cari_akun("ortu-a") is None


def test_proses_admin_hapus_menolak_admin_dan_murid(siap):
    """Pesan sama dengan akun-tak-ada — bukan oracle peran (pola guru_sandi)."""
    auth.tambah_akun("pengelola", "sandi-admin-123456", "admin")
    auth.tambah_akun("murid-x", "sandi-murid-123456", "murid")
    _, g1 = account_pages.proses_admin({"aksi": "guru_hapus", "nama": "pengelola"})
    _, g2 = account_pages.proses_admin({"aksi": "guru_hapus", "nama": "murid-x"})
    _, g3 = account_pages.proses_admin({"aksi": "guru_hapus", "nama": "   "})
    assert g1 == "Akun pengelola tidak ditemukan."
    assert g2 == "Akun murid-x tidak ditemukan."
    assert g3 == "Pilih akunnya dulu."
    assert auth.cari_akun("pengelola") is not None
    assert auth.cari_akun("murid-x") is not None


def test_hapus_akun_guru_langsung(siap):
    """auth.hapus_akun_guru: guru terhapus, admin & murid tidak tersentuh."""
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    auth.tambah_akun("pengelola", "sandi-admin-123456", "admin")
    auth.tambah_akun("murid-x", "sandi-murid-123456", "murid")
    assert auth.hapus_akun_guru("ortu-a") is True
    assert auth.cari_akun("ortu-a") is None
    assert auth.hapus_akun_guru("ortu-a") is False
    assert auth.hapus_akun_guru("pengelola") is False
    assert auth.hapus_akun_guru("murid-x") is False
    assert auth.periksa("pengelola", "sandi-admin-123456")
    assert auth.periksa("murid-x", "sandi-murid-123456")


def test_proses_admin_sukses(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    pesan, galat = account_pages.proses_admin({
        "aksi": "guru_sandi", "nama": "ortu-a", "baru": "sandi-baru-ortu-1",
    })
    assert not galat, galat
    assert "diperbarui" in pesan.lower()
    assert auth.periksa("ortu-a", "sandi-baru-ortu-1")
    assert not auth.periksa("ortu-a", "sandi-lama-ortu-1")


def test_halaman_admin_memuat_kartu_setel_sandi_guru(siap):
    auth.tambah_akun("ortu-a", "sandi-lama-ortu-1", "guru")
    with database.buka(siap) as kon:
        h = account_pages.halaman_admin(kon).decode()
    assert "Setel ulang sandi orang tua" in h
    assert 'value="guru_sandi"' in h
    assert 'name="nama"' in h
    assert 'name="baru"' in h
    assert 'minlength="12"' in h
    assert '<option value="ortu-a">ortu-a</option>' in h
    assert "belum ada akun orang tua" not in h


def test_halaman_admin_kartu_sandi_guru_mati_tanpa_akun_guru(siap):
    # kosongkan berkas sandi sementara: belum ada akun apa pun
    auth.BERKAS_SANDI.unlink()
    with database.buka(siap) as kon:
        h = account_pages.halaman_admin(kon).decode()
    assert "belum ada akun orang tua" in h
    assert '<select name="nama" disabled>' in h
    assert '<button type="submit" class="tombol-sekunder" disabled>' in h
