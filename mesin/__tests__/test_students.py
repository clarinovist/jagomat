"""Fase 4 — palang keras sisi murid.

Yang dijaga di sini bukan kenyamanan, tapi kontrak data:

  Rute & fungsi murid tidak boleh pernah menyentuh kunci, malrule,
  diagnosis, atau laporan.

Cara menegakkannya bukan membaca kode dan berdoa: kolom-kolom sensitif
diblokir di level sqlite3.Row lewat monkeypatch, sehingga kalau satu pun
fungsi halaman murid mencoba SELECT/akses kolom itu, test meledak — apa pun
jalurnya, sekarang atau lima bulan lagi.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import students  # noqa: E402
import student_pages  # noqa: E402
import auth  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


KOLOM_TERLARANG = {"kunci", "malrule_id", "kode_usulan", "kode_final", "alasan"}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Basis data biasa, TANPA palang Row.

    Dipakai test yang memang perlu membaca kunci dari sudut pandang guru
    (mis. memeriksa isi HTML murid terhadap kunci sebenarnya). Palang ada
    di fixture `db_terjaga` — memasangnya di sini akan membuat test yang
    sah ikut meledak, dan itu sempat terjadi.
    """
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def db_terjaga(db, monkeypatch):
    """Basis data + palang level-Row.

    Akses ke kolom terlarang dari kode mana pun yang berjalan di bawah
    fixture ini akan meledak. Karena seluruh rute murid diuji lewat
    fixture ini, satu SELECT kunci yang tidak sengaja ditambahkan lima
    bulan lagi akan gagal di CI, bukan di tangan anak.
    """
    import sqlite3

    asli = sqlite3.Row

    class RowTerjaga(asli):
        def __getitem__(self, kunci):
            if isinstance(kunci, str) and kunci in KOLOM_TERLARANG:
                raise AssertionError(
                    f"KODE MURID MENGAKSES '{kunci}' — palang Fase 4"
                )
            return super().__getitem__(kunci)

    monkeypatch.setattr(sqlite3, "Row", RowTerjaga)
    return db


@pytest.fixture()
def db_dengan_sesi(db_terjaga):
    with database.buka(db_terjaga) as kon:
        siswa_id = database.tambah_siswa(kon, "AnakUji")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=42)
    return db_terjaga, siswa_id, sesi_id


# ── Palang data ──────────────────────────────────────────────────────────


def test_palang_halaman_kerja_tidak_menyentuh_kunci(db_dengan_sesi):
    db, siswa_id, sesi_id = db_dengan_sesi
    with database.buka(db) as kon:
        isi = student_pages.halaman_kerja_baru(kon, siswa_id, sesi_id)  # tidak boleh raise


def test_palang_daftar_sesi_tidak_menyentuh_diagnosis(db_dengan_sesi):
    db, siswa_id, _ = db_dengan_sesi
    with database.buka(db) as kon:
        student_pages.halaman_daftar_sesi_baru(kon, siswa_id, "AnakUji")


def test_palang_soal_murid_tanpa_kunci(db_dengan_sesi):
    """soal_murid mengirim soal ke browser anak — satu field pun bocor,
    anak tinggal view-source."""
    db, siswa_id, sesi_id = db_dengan_sesi
    with database.buka(db) as kon:
        for s in students.soal_murid(kon, sesi_id, siswa_id):
            assert not set(s) & {"kunci", "malrule"}, f"field terlarang: {set(s)}"


# ── Isolasi antar murid ────────────────────────────────────────────────


def test_murid_tidak_bisa_buka_sesi_anak_lain(db_terjaga):
    """Dua anak. B menebak alamat sesi A. Harus ditolak — bukan dibisukan,
    ditolak: None agar handler mengirim 404/403."""
    with database.buka(db_terjaga) as kon:
        a = database.tambah_siswa(kon, "AnakA")
        b = database.tambah_siswa(kon, "AnakB")
        sesi_a = database.buat_sesi(kon, a, seed=7)
        assert students.sesi_murid(kon, b, sesi_a) is None
        assert students.soal_murid(kon, sesi_a, b) == []
        assert student_pages.halaman_kerja_baru(kon, b, sesi_a) is None


def test_simpan_jawaban_menolak_sesi_orang_lain(db_terjaga):
    with database.buka(db_terjaga) as kon:
        a = database.tambah_siswa(kon, "AnakA")
        b = database.tambah_siswa(kon, "AnakB")
        sesi_a = database.buat_sesi(kon, a, seed=7)
        assert not students.simpan_jawaban_murid(kon, b, sesi_a, {})


# ── Jawaban tersimpan benar (dan bisa didiagnosis guru kemudian) ───────


def test_jawaban_murid_masuk_jalur_yang_sama_dengan_guru(db_dengan_sesi):
    """Jawaban anak disimpan lewat database.simpan_jawaban yang sama. Guru
    membukanya dari halaman sesi seperti biasa — tidak ada jalur kedua yang
    bisa salah bentuk."""
    db, siswa_id, sesi_id = db_dengan_sesi
    with database.buka(db) as kon:
        daftar = students.soal_murid(kon, sesi_id, siswa_id)
        ssid = daftar[0]["sesi_soal_id"]
        ok = students.simpan_jawaban_murid(
            kon, siswa_id, sesi_id, {f"jwb_{ssid}": "24", f"cara_{ssid}": "dikali 3"}
        )
        assert ok
        baris = kon.execute(
            """SELECT j.jawaban, j.cara FROM jawaban j
               JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.id = ?""",
            (ssid,),
        ).fetchone()
        assert baris["jawaban"] == "24"
        assert baris["cara"] == "dikali 3"


def test_soal_dilewati_tidak_membuat_baris_kosong(db_dengan_sesi):
    db, siswa_id, sesi_id = db_dengan_sesi
    with database.buka(db) as kon:
        students.simpan_jawaban_murid(kon, siswa_id, sesi_id, {})
        n = kon.execute("SELECT COUNT(*) AS n FROM jawaban").fetchone()["n"]
        assert n == 0


# ── Peran & akun ────────────────────────────────────────────────────────


def test_akun_murid_dan_guru_hidup_bersebelahan(tmp_path):
    p = tmp_path / "sandi.json"
    auth.simpan_sandi("rahasia-guru", "guru", path=p)      # bentuk lama
    auth.tambah_akun("Feby", "rahasia-anak", "murid", path=p)

    assert auth.periksa_peran("guru", "rahasia-guru", "guru", path=p)
    assert not auth.periksa_peran("guru", "rahasia-guru", "murid", path=p)
    assert auth.periksa_peran("feby", "rahasia-anak", "murid", path=p)
    assert not auth.periksa_peran("Feby", "rahasia-anak", "guru", path=p)
    # sandi guru tidak membuka pintu murid, sandi murid tidak membuka guru
    assert auth.peran_dari("guru", "rahasia-guru", path=p) == "guru"
    assert auth.peran_dari("Feby", "rahasia-anak", path=p) == "murid"


def test_nama_pengguna_case_insensitive(tmp_path):
    p = tmp_path / "sandi.json"
    auth.tambah_akun("Putri", "sandi123", "murid", path=p)
    assert auth.cari_akun("putri", path=p) is not None
    assert auth.cari_akun("PUTRI", path=p) is not None


def test_nama_ganda_ditolak(tmp_path):
    p = tmp_path / "sandi.json"
    auth.tambah_akun("ika", "s1", "murid", path=p)
    with pytest.raises(ValueError):
        auth.tambah_akun("Ika", "s2", "murid", path=p)


def test_peran_aneh_ditolak(tmp_path):
    p = tmp_path / "sandi.json"
    # "admin" kini peran sah (multi-keluarga); contoh peran asing diganti.
    with pytest.raises(ValueError):
        auth.tambah_akun("hantu", "s3", "bos", path=p)


# ── Tautan akun murid → siswa (multi-keluarga) ──────────────────────────


def test_siswa_dari_akun_memakai_siswa_id_eksplisit(db, tmp_path, monkeypatch):
    """Akun dengan siswa_id menang: nama login tak harus sama dengan nama
    siswa mana pun (dua keluarga boleh punya anak bernama sama)."""
    berkas = tmp_path / "sandi.json"
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakLain", pemilik="ortu-a")
    auth.tambah_akun("feby2", "sandi-feby-12345", "murid", siswa_id=sid)
    with database.buka(db) as kon:
        assert students.siswa_dari_akun(kon, "feby2") == sid


def test_siswa_dari_akun_fallback_nama_untuk_akun_warisan(db, tmp_path, monkeypatch):
    """Akun lama tanpa siswa_id tetap terhubung lewat pencocokan nama."""
    berkas = tmp_path / "sandi.json"
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "feby")
    auth.tambah_akun("feby", "sandi-feby-12345", "murid")
    with database.buka(db) as kon:
        assert students.siswa_dari_akun(kon, "feby") == sid


# ── Halaman HTML murid bersih dari jejak jawaban ───────────────────────


def test_html_kerja_tanpa_kunci_dalam_form(db):
    """Input value= tidak boleh pernah memuat kunci — anak yang lihat source
    mendapat jawabannya gratis, dan semua kode diagnosis mati.

    Test ini TIDAK memakai fixture palang (kunci dibaca langsung di sini,
    peran guru) supaya yang diuji adalah isi HTML-nya, bukan jalur akses.
    """
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "AnakHtml")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=42)
        halaman = student_pages.halaman_kerja_baru(kon, siswa_id, sesi_id)
        assert halaman is not None
        isi = halaman.decode()
        for b in database.isi_sesi(kon, sesi_id):
            kunci = b["kunci"]
            if len(kunci) >= 2:
                assert f'value="{kunci}"' not in isi


# ── Pilihan cepat "Caraku" (uji HP nyata: caraku sering kosong) ────────


def test_pilihan_cara_tersimpan_ke_kolom_cara(db_terjaga):
    """Pilihan digabung ke kolom `cara` yang sama, bukan kolom baru:
    diagnosis.py dan laporan guru sudah membaca kolom itu."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        ssid = students.soal_murid(kon, ses, sid)[0]["sesi_soal_id"]
        n = students.simpan_jawaban_murid(kon, sid, ses, {
            f"jwb_{ssid}": "24", f"pilih_{ssid}": "hitung_satu_satu",
        })
        assert n == 1
        r = kon.execute(
            "SELECT cara FROM jawaban WHERE sesi_soal_id = ?", (ssid,)
        ).fetchone()
        assert r["cara"] == students.AWALAN_PILIHAN + "hitung_satu_satu"


def test_pilihan_palsu_dari_form_dibuang(db_terjaga):
    """Nilai datang dari form; yang tidak dikenal tidak boleh tersimpan."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        ssid = students.soal_murid(kon, ses, sid)[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(kon, sid, ses, {
            f"jwb_{ssid}": "24", f"pilih_{ssid}": "<script>jahat</script>",
        })
        r = kon.execute(
            "SELECT cara FROM jawaban WHERE sesi_soal_id = ?", (ssid,)
        ).fetchone()
        assert "script" not in r["cara"]
        assert r["cara"] == ""


def test_pilihan_dan_teks_bisa_berdampingan(db_terjaga):
    """Anak boleh memilih DAN menulis. Teksnya lebih berharga, jadi jangan
    sampai pilihan menimpanya."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        ssid = students.soal_murid(kon, ses, sid)[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(kon, sid, ses, {
            f"jwb_{ssid}": "24", f"pilih_{ssid}": "pakai_rumus",
            f"cara_{ssid}": "aku kali 3 terus tambah 2",
        })
        r = kon.execute(
            "SELECT cara FROM jawaban WHERE sesi_soal_id = ?", (ssid,)
        ).fetchone()
        assert "pakai_rumus" in r["cara"]
        assert "aku kali 3 terus tambah 2" in r["cara"]


def test_mengaku_menebak_jadi_kode_n(db_terjaga):
    """Inti seluruh fitur ini: pengakuan anak menggantikan kekosongan yang
    ambigu. Sebelumnya kotak kosong -> N (mesin menduga menebak); sekarang
    anak bisa menyatakannya sendiri."""
    from diagnosis import diagnosa

    u = diagnosa("24", "27", students.AWALAN_PILIHAN + "tebak", "", False, [])
    assert u.kode == "N"
    assert not u.benar


def test_menebak_tapi_kebetulan_benar_tetap_n(db_terjaga):
    """Jawaban benar hasil tebakan adalah tanda bahaya yang paling mudah
    hilang dari data — pengakuan diperiksa SEBELUM kunci dibandingkan."""
    from diagnosis import diagnosa

    u = diagnosa("24", "24", students.AWALAN_PILIHAN + "tebak", "", False, [])
    assert u.kode == "N", "menebak lalu benar tetap harus tercatat menebak"
    assert not u.benar


def test_mengaku_bingung_perlu_ditinjau_tanpa_kode(db_terjaga):
    """Bingung belum membuktikan kebutuhan pengenalan materi."""
    from diagnosis import diagnosa

    u = diagnosa("24", "", students.AWALAN_PILIHAN + "bingung", "", False, [])
    assert u.kode is None and not u.yakin


def test_konfirmasi_tersimpan_muncul_dengan_jumlah(db_terjaga):
    """Tanpa konfirmasi, anak tidak tahu jawabannya masuk lalu menekan
    tombol berulang atau mengira kerjanya hilang."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        html = student_pages.halaman_kerja_baru(kon, sid, ses, tersimpan=3).decode()
    assert "Tersimpan" in html
    assert "3 soal" in html


def test_konfirmasi_tidak_muncul_saat_pertama_buka(db_terjaga):
    """Halaman yang baru dibuka belum menyimpan apa pun."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        html = student_pages.halaman_kerja_baru(kon, sid, ses).decode()
    assert "Tersimpan" not in html


def test_pilihan_tampil_kembali_saat_dibuka_lagi(db_terjaga):
    """Anak yang membuka lagi harus melihat pilihannya masih tercentang.

    Kalau tidak, ia mengira jawabannya hilang lalu mengisi ulang dari nol —
    dan pengisian ulang itu biasanya lebih asal daripada yang pertama.
    """
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        ssid = students.soal_murid(kon, ses, sid)[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(
            kon, sid, ses, {f"jwb_{ssid}": "24", f"pilih_{ssid}": "lihat_pola"}
        )
        html = student_pages.halaman_kerja_baru(kon, sid, ses).decode()

    assert 'value="lihat_pola" checked' in html
    # dan pilihan lain tidak ikut tercentang
    assert 'value="tebak" checked' not in html


def test_semua_pilihan_muncul_di_halaman(db_terjaga):
    """Kalau satu pilihan hilang dari HTML, anak tidak punya cara
    menyatakannya dan datanya jatuh kembali jadi kekosongan ambigu."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        html = student_pages.halaman_kerja_baru(kon, sid, ses).decode()

    for kode, label in students.PILIHAN_CARA:
        assert f'value="{kode}"' in html, f"pilihan {kode} hilang"
        assert label in html, f"label {label!r} hilang"


# ── Semua soal terisi (penentu status "sudah dikirim") ──────────────────


def test_semua_terisi_false_saat_kosong(db_terjaga):
    """Belum ada satu jawaban pun → belum selesai."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakSelesai")
        ses = database.buat_sesi(kon, sid, seed=42)
        assert students.semua_terisi(kon, sid, ses) is False


def test_semua_terisi_false_saat_sebagian(db_dengan_sesi):
    """Satu soal terisi dari 12 → masih ada yang kosong, belum selesai."""
    db, siswa_id, sesi_id = db_dengan_sesi
    with database.buka(db) as kon:
        ssid = students.soal_murid(kon, sesi_id, siswa_id)[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(kon, siswa_id, sesi_id, {f"jwb_{ssid}": "24"})
        assert students.semua_terisi(kon, siswa_id, sesi_id) is False


def test_semua_terisi_true_saat_semua_soal_terisi(db_terjaga):
    """Semua soal sesi diisi (jawaban minimal) → selesai = True."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakSelesai")
        ses = database.buat_sesi(kon, sid, seed=42)
        daftar = students.soal_murid(kon, ses, sid)
        data = {f"jwb_{s['sesi_soal_id']}": "1" for s in daftar}
        students.simpan_jawaban_murid(kon, sid, ses, data)
        assert students.semua_terisi(kon, sid, ses) is True


def test_semua_terisi_false_untuk_sesi_orang_lain(db_terjaga):
    """Sesi anak lain tidak boleh dianggap selesai oleh murid ini —
    konsisten dengan simpan_jawaban_murid yang menolak sesi orang lain."""
    with database.buka(db_terjaga) as kon:
        sid_a = database.tambah_siswa(kon, "AnakA")
        sid_b = database.tambah_siswa(kon, "AnakB")
        ses_a = database.buat_sesi(kon, sid_a, seed=42)
        assert students.semua_terisi(kon, sid_b, ses_a) is False


# ── Badge status daftar sesi (/murid) ────────────────────────────────────
#
# Badge mengikuti STATUS pengerjaan, bukan tanggal: belum disentuh → "Baru",
# sebagian terisi → "Dikerjakan", sudah dikirim → "Masih di review",
# sudah dinilai guru → tautan hasil dengan status netral, bukan skor.
# Marker dan tujuan tautan diperiksa agar status tidak tertukar.


def _isi_semua_jawaban(kon, siswa_id, sesi_id) -> int:
    """Isi SEMUA kotak jawaban sesi lewat jalur murid yang sama dengan HP."""
    data = {
        f"jwb_{s['sesi_soal_id']}": "1"
        for s in students.soal_murid(kon, sesi_id, siswa_id)
    }
    return students.simpan_jawaban_murid(kon, siswa_id, sesi_id, data)


def test_daftar_sesi_tanpa_jawaban_berbadge_baru(db_terjaga):
    """Sesi yang belum disentuh menawarkan mulai, bukan hasil/review."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakDaftar")
        database.buat_sesi(kon, sid, seed=42)
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakDaftar").decode()
    assert "Mulai latihan" in html
    assert 'class="murid-menunggu-st"' not in html
    assert "Selesai! Latihanmu sudah dikirim." not in html, (
        "banner konfirmasi hanya boleh muncul untuk sesi selesai miliknya"
    )


def test_daftar_sesi_sebagian_terisi_berbadge_dikerjakan(db_terjaga):
    """Satu jawaban dari 12 → progres tersimpan dan tawaran lanjut."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakDaftar")
        ses = database.buat_sesi(kon, sid, seed=42)
        ssid = students.soal_murid(kon, ses, sid)[0]["sesi_soal_id"]
        students.simpan_jawaban_murid(kon, sid, ses, {f"jwb_{ssid}": "24"})
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakDaftar").decode()
    assert "Lanjutkan latihan" in html
    assert "1 dari 12 soal tersimpan" in html
    assert 'class="murid-menunggu-st"' not in html


def test_daftar_sesi_sudah_dikirim_berbadge_masih_di_review(db_terjaga):
    """Sesi sudah dikirim tetapi belum diperiksa tidak menawarkan hasil."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakDaftar")
        ses = database.buat_sesi(kon, sid, seed=42)
        assert _isi_semua_jawaban(kon, sid, ses)
        kon.execute(
            "UPDATE sesi SET selesai = '2026-08-30 09:00:00' WHERE id = ?",
            (ses,),
        )
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakDaftar").decode()
    assert '<span class="st-badge review">Menunggu diperiksa</span>' in html
    assert f'href="/murid/hasil/{ses}"' not in html


def test_daftar_sesi_sudah_direview_menaut_hasil_tanpa_skor(db_terjaga):
    """Beranda aktif hanya status netral; skor tetap di halaman hasil."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakDaftar")
        ses = database.buat_sesi(kon, sid, seed=42)
        assert _isi_semua_jawaban(kon, sid, ses)
        kon.execute(
            "UPDATE sesi SET selesai = '2026-08-30 09:00:00',"
            " direview = '2026-08-30 10:00:00' WHERE id = ?",
            (ses,),
        )
        jwb_id = kon.execute(
            """SELECT j.id FROM jawaban j
               JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.sesi_id = ? LIMIT 1""",
            (ses,),
        ).fetchone()["id"]
        kon.execute(
            "INSERT INTO diagnosis (jawaban_id, benar) VALUES (?, 1)", (jwb_id,)
        )
        jumlah = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi_soal WHERE sesi_id = ?", (ses,)
        ).fetchone()["n"]
        html = student_pages.halaman_daftar_sesi_baru(kon, sid, "AnakDaftar").decode()
    assert '<span class="st-badge diagnostik">Selesai · sudah diperiksa</span>' in html
    assert f'href="/murid/hasil/{ses}"' in html
    assert f'1/{jumlah} benar' not in html


def test_daftar_sesi_banner_setelah_submit_penuh(db_terjaga):
    """QA: setelah submit semua soal, anak kembali ke DAFTAR sesi dengan
    banner konfirmasi — bukan ke halaman terpisah. Parameter sesi_selesai
    harus merujuk sesi miliknya yang benar-benar selesai."""
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, "AnakDaftar")
        ses = database.buat_sesi(kon, sid, seed=42)
        html_biasa = student_pages.halaman_daftar_sesi_baru(
            kon, sid, "AnakDaftar"
        ).decode()
        html_palsu = student_pages.halaman_daftar_sesi_baru(
            kon, sid, "AnakDaftar", sesi_selesai=ses
        ).decode()
        database.tandai_selesai(kon, ses)
        html_banner = student_pages.halaman_daftar_sesi_baru(
            kon, sid, "AnakDaftar", sesi_selesai=ses
        ).decode()
    assert 'Selesai! Latihanmu sudah dikirim.' in html_banner
    assert 'Selesai! Latihanmu sudah dikirim.' not in html_biasa
    assert 'Selesai! Latihanmu sudah dikirim.' not in html_palsu


# ── E2E HTTP: alur simpan jawaban ────────────────────────────────────────


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _bikin_sesi_untuk_feby(server) -> int:
    """Guru buat sesi untuk 'feby' (akun murid uji) → kembalikan sesi_id."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")
    server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan"},
    )
    with server.buka() as kon:
        return kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"]


def test_http_simpan_sebagian_tetap_di_lembar_dengan_banner(server):
    """Murid mengisi SEBAGIAN soal → kembali ke lembar + banner tersimpan,
    supaya bisa lanjut mengerjakan sisanya."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        daftar = database.isi_sesi(kon, sesi_id)
        satu = {f"jwb_{daftar[0]['sesi_soal_id']}": "24"}

    kode, isi, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=satu,
    )
    assert kode == 200
    assert "Tersimpan" in isi, "simpan sebagian harus tetap menampilkan banner"
    assert "Masih di review" not in isi, (
        "belum semua soal terisi — jangan menampilkan status review"
    )


def test_http_semua_terisi_langsung_ke_daftar_sesi_dengan_banner(server):
    """Semua soal terisi → langsung ke daftar sesi dengan banner perayaan,
    bukan halaman terpisah dengan pilihan "kembali / keluar" (masukan QA:
    satu klik lebih sedikit; tombol Keluar memang sudah ada di daftar)."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        data = {
            f"jwb_{b['sesi_soal_id']}": str(i)
            for i, b in enumerate(database.isi_sesi(kon, sesi_id), start=1)
        }
        data["aksi"] = "selesai"

    kode, isi, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=data,
    )
    assert kode == 200  # 303 diikuti sampai /murid
    assert "Selesai! Latihanmu sudah dikirim." in isi, "banner perayaan tampil"
    assert "Simpan jawabanku" not in isi, "bukan lembar kerja lagi"


# ── Penandaan direview: guru membuka sesi yang terisi penuh ──────────


def test_http_guru_membuka_sesi_terisi_mencatat_direview(server):
    """Badge "Selesai" di daftar murid butuh penanda kapan guru sudah
    melihat hasilnya. Momen yang murah dan jujur: guru membuka /sesi/<id>
    saat sesi terisi penuh — bukan saat lembar masih kosong (bisa jadi
    baru mau dicetak)."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        data = {
            f"jwb_{b['sesi_soal_id']}": str(i)
            for i, b in enumerate(database.isi_sesi(kon, sesi_id), start=1)
        }
        data["aksi"] = "selesai"
    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=data,
    )
    server.minta(f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU))
    with server.buka() as kon:
        direview = kon.execute(
            "SELECT direview FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["direview"]
    assert direview is not None


def test_http_sesi_kosong_dibuka_guru_tidak_dicatat_direview(server):
    """Membuka lembar kosong untuk mencetak bukan momen review — kalau
    tercatat, sesi yang belum dikerjakan langsung ber-badge "Selesai" di
    ponsel anak."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    server.minta(f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU))
    with server.buka() as kon:
        direview = kon.execute(
            "SELECT direview FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["direview"]
    assert direview is None


def test_http_membuka_lembar_mencatat_mulai(server):
    """Buka lembar = mulai pengerjaan — perbaikan durasi 0 detik untuk sesi
    yang dikerjakan sekali simpan. Commit stamp mendahului respons: pembaca
    yang menindaklanjuti respons detik itu juga tidak boleh melihat
    keadaan pra-commit."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    server.minta(f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID))
    with server.buka() as kon:
        mulai = kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["mulai"]
    assert mulai is not None


# ── Pencatatan waktu pengerjaan (kolom mulai/selesai sesi) ────────────


def test_http_post_pertama_mencatat_mulai(server):
    """POST jawaban pertama = anak mulai mengerjakan. Selesai tetap kosong
    sampai SEMUA soal terisi — durasi setengah jalan menyesatkan."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        b = database.isi_sesi(kon, sesi_id)[0]

    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={f"jwb_{b['sesi_soal_id']}": "1"},
    )
    with server.buka() as kon:
        baris = kon.execute(
            "SELECT mulai, selesai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
    assert baris["mulai"] is not None
    assert baris["selesai"] is None


def test_http_post_kedua_tidak_menggeser_mulai(server):
    """Idempoten lewat HTTP: POST berulang dari HP tidak boleh menggeser
    mulai, kalau tidak, durasi pengerjaan jadi bohong. Nilai mulai dipaksa
    ke angka pasti supaya dua POST di detik yang sama pun tetap terdeteksi
    kalau pelindungnya hilang."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        b = database.isi_sesi(kon, sesi_id)[0]
        ssid = b["sesi_soal_id"]

    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "1"},
    )
    with server.buka() as kon:
        kon.execute(
            "UPDATE sesi SET mulai = '2026-08-01 08:00:00' WHERE id = ?",
            (sesi_id,),
        )
    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "2"},
    )
    with server.buka() as kon:
        mulai = kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["mulai"]
    assert mulai == "2026-08-01 08:00:00", "POST kedua menggeser mulai"


def test_tandai_mulai_tidak_menggeser_yang_sudah_ada(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "IdemMulai")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        kon.execute(
            "UPDATE sesi SET mulai = '2026-08-01 08:00:00' WHERE id = ?",
            (sesi_id,),
        )
        database.tandai_mulai(kon, sesi_id)
        m = kon.execute(
            "SELECT mulai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["mulai"]
        database.tandai_mulai(kon, 99999)  # sesi tak dikenal: no-op, tidak meledak
    assert m == "2026-08-01 08:00:00"


def test_tandai_selesai_tidak_menggeser_yang_sudah_ada(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "IdemSelesai")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        kon.execute(
            "UPDATE sesi SET selesai = '2026-08-01 09:00:00' WHERE id = ?",
            (sesi_id,),
        )
        database.tandai_selesai(kon, sesi_id)
        s = kon.execute(
            "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["selesai"]
        database.tandai_selesai(kon, 99999)
    assert s == "2026-08-01 09:00:00"


def test_http_semua_terisi_mencatat_selesai(server):
    """Alur penuh: isi semua → mulai dan selesai keduanya tercatat, sehingga
    dashboard guru bisa menampilkan durasi pengerjaan."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        daftar = database.isi_sesi(kon, sesi_id)
        data = {f"jwb_{b['sesi_soal_id']}": "1" for b in daftar}
        data["aksi"] = "selesai"

    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=data,
    )
    with server.buka() as kon:
        baris = kon.execute(
            "SELECT mulai, selesai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
    assert baris["mulai"] is not None
    assert baris["selesai"] is not None


def test_http_post_ulang_setelah_selesai_tidak_menggeser_selesai(server):
    """Anak iseng menekan simpan lagi setelah halaman selesai — selesai
    yang tercatat saat semua soal terisi tetap yang pertama."""
    sesi_id = _bikin_sesi_untuk_feby(server)
    with server.buka() as kon:
        daftar = database.isi_sesi(kon, sesi_id)
        data = {f"jwb_{b['sesi_soal_id']}": "1" for b in daftar}
        data["aksi"] = "selesai"

    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=data,
    )
    server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data=data,
    )
    with server.buka() as kon:
        baris = kon.execute(
            "SELECT selesai FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
    assert baris["selesai"] is not None  # dijaga WHERE selesai IS NULL
