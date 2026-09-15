"""Uji alur penuh: sesi -> jawaban -> diagnosis -> laporan.

Memakai basis data sementara, bukan latihan.db, supaya data anak yang
sungguhan tidak tersentuh test.

Yang dibuktikan di sini bukan tiap fungsi bekerja sendiri-sendiri (itu tugas
test lain), melainkan bahwa rangkaiannya menghasilkan laporan yang benar —
termasuk aturan pencatatan yang mudah salah: satu miskonsepsi yang muncul di
beberapa soal tetap dihitung satu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from diagnosis import diagnosa  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    return p


# ── Kepemilikan keluarga (multi-keluarga) ───────────────────────────────


def test_tambah_siswa_membubuhkan_pemilik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Bima", "P3", pemilik="ortu-a")
        baris = kon.execute(
            "SELECT pemilik FROM siswa WHERE id = ?", (sid,)
        ).fetchone()
    assert baris["pemilik"] == "ortu-a"


def test_tambah_siswa_tanpa_pemilik_tetap_kosong(db):
    """Perilaku lama (panggilan tanpa pemilik) tidak berubah."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Rara")
        baris = kon.execute(
            "SELECT pemilik FROM siswa WHERE id = ?", (sid,)
        ).fetchone()
    assert baris["pemilik"] == ""


def test_daftar_siswa_terfilter_per_pemilik(db):
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Bima", pemilik="ortu-a")
        database.tambah_siswa(kon, "Rara", pemilik="ortu-b")
        database.tambah_siswa(kon, "Cici", pemilik="ortu-a")
        milik_a = [r["nama"] for r in database.daftar_siswa(kon, "ortu-a")]
        semua = [r["nama"] for r in database.daftar_siswa(kon)]
    assert milik_a == ["Bima", "Cici"]
    # None = tanpa filter: panggilan admin dan panggilan lama
    assert semua == ["Bima", "Cici", "Rara"]


def test_dobel_nama_dalam_satu_keluarga_mengembalikan_yang_lama(db):
    with database.buka(db) as kon:
        a1 = database.tambah_siswa(kon, "Bima", pemilik="ortu-a")
        a2 = database.tambah_siswa(kon, "Bima", pemilik="ortu-a")
        b1 = database.tambah_siswa(kon, "Bima", pemilik="ortu-b")
    assert a2 == a1
    assert b1 != a1


def test_siswa_milik_dan_sesi_milik(db):
    with database.buka(db) as kon:
        a1 = database.tambah_siswa(kon, "Bima", pemilik="ortu-a")
        b1 = database.tambah_siswa(kon, "Rara", pemilik="ortu-b")
        s1 = database.buat_sesi(kon, a1, seed=1)
        s2 = database.buat_sesi(kon, b1, seed=2)
        assert database.siswa_milik(kon, a1, "ortu-a")
        assert not database.siswa_milik(kon, a1, "ortu-b")
        assert not database.siswa_milik(kon, 9999, "ortu-a")
        assert database.sesi_milik(kon, s1, "ortu-a")
        assert not database.sesi_milik(kon, s1, "ortu-b")
        assert not database.sesi_milik(kon, s2, "ortu-a")
        assert not database.sesi_milik(kon, 9999, "ortu-a")


def test_sesi_berisi_dua_belas_soal(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Uji")
        sesi_id = database.buat_sesi(kon, sid, seed=555)
        isi = database.isi_sesi(kon, sesi_id)
    assert len(isi) == 12
    assert [r["nomor"] for r in isi] == list(range(1, 13))


def test_bank_soal_tidak_menggandakan_soal_yang_sama(db):
    """Seed sama dipakai dua siswa -> bank tetap 12, bukan 24.

    Kalau bank menggandakan, statistik "berapa varian yang sudah dipakai"
    jadi bohong dan tidak bisa dipakai memutuskan kapan menambah template.
    """
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "A")
        b = database.tambah_siswa(kon, "B")
        database.buat_sesi(kon, a, seed=777)
        database.buat_sesi(kon, b, seed=777)
        total = sum(r["jumlah"] for r in database.statistik_bank(kon))
    assert total == 12


def test_bank_tumbuh_saat_seed_berbeda(db):
    """Inti kebutuhan: tiap generate menambah kekayaan bank."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tumbuh")
        for seed in (1, 2, 3, 4, 5):
            database.buat_sesi(kon, sid, seed=seed)
        total = sum(r["jumlah"] for r in database.statistik_bank(kon))
    # 5 sesi x 12 soal = 60 maksimum; sebagian template bervarian sedikit
    # sehingga tabrakan wajar, tapi harus tumbuh jauh di atas 12.
    assert 30 < total <= 60


def test_seed_sama_menghasilkan_soal_identik(db):
    """Lembar bisa dicetak ulang persis — penting kalau kertasnya hilang."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Ulang")
        s1 = database.buat_sesi(kon, sid, seed=99)
        s2 = database.buat_sesi(kon, sid, seed=99)
        a = [r["soal_id"] for r in database.isi_sesi(kon, s1)]
        b = [r["soal_id"] for r in database.isi_sesi(kon, s2)]
    assert a == b


def test_alur_penuh_sampai_ringkasan(db):
    """Jalankan seluruh rantai dengan jawaban yang dirancang.

    Skenario: anak menjawab benar sebagian, sisanya salah dengan cara yang
    persis diprediksi malrule pertama tiap soal. Ringkasan harus mencatat
    kodenya, bukan sekadar skor.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Alur")
        sesi_id = database.buat_sesi(kon, sid, seed=321)

        for i, baris in enumerate(database.isi_sesi(kon, sesi_id)):
            mal = database.malrule_soal(kon, baris["soal_id"])
            # soal genap dijawab benar, ganjil dijawab sesuai malrule pertama
            if i % 2 == 0:
                jwb = baris["kunci"]
            else:
                jwb = mal[0]["jawaban"] if mal else "999"

            jid = database.simpan_jawaban(
                kon, baris["sesi_soal_id"], jawaban=jwb, cara="ada coretan"
            )
            u = diagnosa(baris["kunci"], jwb, "ada coretan", "", False, mal, False)
            database.simpan_diagnosis(
                kon, jid, u.benar, u.kode, u.kode, u.malrule_id, u.alasan
            )

        database.tandai_selesai(kon, sesi_id)
        r = database.ringkasan(kon, sid)[0]

    assert r["jumlah_soal"] == 12
    assert r["benar"] == 6
    # sisanya harus terkode, bukan menggantung tanpa diagnosis
    assert (r["k"] or 0) + (r["b"] or 0) + (r["h"] or 0) == 6


def test_miskonsepsi_sama_lintas_sesi_terhitung_sebagai_satu(db):
    """Aturan pencatatan yang paling mudah salah.

    Anak mengulang miskonsepsi yang SAMA di dua sesi dengan angka berbeda.
    Laporan harus menyebutnya satu miskonsepsi yang muncul di 2 sesi —
    bukan dua masalah terpisah. Inilah alasan yang dibandingkan malrule_id,
    bukan nomor soal atau angkanya.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Ulangi")

        for seed in (11, 22):  # dua sesi, angka soal berbeda
            sesi_id = database.buat_sesi(kon, sid, seed=seed, tanggal=f"2026-09-{seed:02d}")
            for baris in database.isi_sesi(kon, sesi_id):
                if baris["template_id"] != "deret_geometri":
                    continue
                mal = [
                    m for m in database.malrule_soal(kon, baris["soal_id"])
                    if m["kode"] == "K"
                ]
                if not mal:
                    continue
                m = mal[0]
                jid = database.simpan_jawaban(
                    kon, baris["sesi_soal_id"], jawaban=m["jawaban"], cara="coretan"
                )
                database.simpan_diagnosis(
                    kon, jid, False, "K", "K", m["malrule_id"], m["alasan"]
                )
                database.tandai_selesai(kon, sesi_id)

        hasil = database.miskonsepsi_berulang(kon, sid)

    assert len(hasil) == 1, "miskonsepsi yang sama harus menyatu jadi satu baris"
    assert hasil[0]["jumlah_sesi"] == 2
    assert hasil[0]["kemunculan"] == 2


def test_materi_bertanda_t_masuk_peta_bukan_nilai(db):
    """T bukan kegagalan — dikumpulkan sebagai daftar materi yang belum diajar."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "PetaT")
        sesi_id = database.buat_sesi(kon, sid, seed=404)
        baris = database.isi_sesi(kon, sesi_id)[-1]  # soal tantangan

        jid = database.simpan_jawaban(
            kon, baris["sesi_soal_id"], jawaban="", belum_pernah=True
        )
        u = diagnosa(baris["kunci"], "", "", "", True, [], False)
        assert u.kode is None  # Catatan anak belum berarti keputusan T.
        database.simpan_diagnosis(kon, jid, False, u.kode, 'T', None, 'Guru memastikan perlu pengenalan', manual=True)
        database.tandai_selesai(kon, sesi_id)

        peta = database.peta_materi_baru(kon, sid)

    assert len(peta) == 1
    assert peta[0]["kali"] == 1


def test_jawaban_bisa_diperbarui_tanpa_menggandakan(db):
    """Guru salah ketik lalu memperbaiki — tidak boleh jadi dua baris."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Ralat")
        sesi_id = database.buat_sesi(kon, sid, seed=808)
        ss = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]

        id1 = database.simpan_jawaban(kon, ss, jawaban="salah ketik")
        id2 = database.simpan_jawaban(kon, ss, jawaban="sudah benar")
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM jawaban WHERE sesi_soal_id = ?", (ss,)
        ).fetchone()["n"]
        isi = kon.execute(
            "SELECT jawaban FROM jawaban WHERE id = ?", (id2,)
        ).fetchone()["jawaban"]

    assert id1 == id2
    assert n == 1
    assert isi == "sudah benar"


def test_menghapus_sesi_membersihkan_jawaban_dan_diagnosis(db):
    """Kalau sesi dibatalkan, jejaknya tidak boleh tertinggal jadi data yatim."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Hapus")
        sesi_id = database.buat_sesi(kon, sid, seed=606)
        ss = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]
        jid = database.simpan_jawaban(kon, ss, jawaban="x", cara="y")
        database.simpan_diagnosis(kon, jid, False, "K", "K", None, "uji")

        kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))

        sisa_j = kon.execute("SELECT COUNT(*) AS n FROM jawaban").fetchone()["n"]
        sisa_d = kon.execute("SELECT COUNT(*) AS n FROM diagnosis").fetchone()["n"]
        # soal tetap di bank — itu aset, bukan data anak
        sisa_s = kon.execute("SELECT COUNT(*) AS n FROM soal").fetchone()["n"]

    assert sisa_j == 0
    assert sisa_d == 0
    assert sisa_s == 12


# ── Konfigurasi lewat lingkungan (dipakai saat deploy) ──────────────────


def test_lokasi_basis_data_bisa_disetel_lewat_lingkungan(tmp_path, monkeypatch):
    """Regresi deploy: container gagal start karena basis data menunjuk /app.

    Di dalam container /app dimiliki root dan read-only, sehingga basis data
    WAJIB tinggal di volume. Sebelum ada OSN_BERKAS_DB, `database.BAWAAN`
    dihitung sekali dari lokasi berkas sumber dan tidak bisa dialihkan —
    container mati berulang dengan "unable to open database file".

    Kegagalan seperti ini tidak pernah muncul saat dijalankan lokal, jadi
    satu-satunya cara menahannya adalah test yang meniru kondisi deploy.
    """
    import importlib

    tujuan = tmp_path / "volume" / "latihan.db"
    tujuan.parent.mkdir()
    monkeypatch.setenv("OSN_BERKAS_DB", str(tujuan))

    import database as basis_modul

    importlib.reload(basis_modul)
    try:
        assert basis_modul.BAWAAN == tujuan
        basis_modul.siapkan()
        with basis_modul.buka() as kon:
            basis_modul.tambah_siswa(kon, "Volume")
            assert [r["nama"] for r in basis_modul.daftar_siswa(kon)] == ["Volume"]
        assert tujuan.exists(), "basis data tidak dibuat di lokasi yang disetel"
    finally:
        monkeypatch.delenv("OSN_BERKAS_DB", raising=False)
        importlib.reload(basis_modul)


def test_lokasi_berkas_sandi_bisa_disetel_lewat_lingkungan(tmp_path, monkeypatch):
    """Alasan yang sama dengan basis data: sandi harus tinggal di volume,
    kalau tidak ia hilang tiap container diganti dan palangnya mati."""
    import importlib

    tujuan = tmp_path / "volume" / "sandi.json"
    tujuan.parent.mkdir()
    monkeypatch.setenv("OSN_BERKAS_SANDI", str(tujuan))

    import auth as sandi_modul

    importlib.reload(sandi_modul)
    try:
        assert sandi_modul.BERKAS_SANDI == tujuan
        sandi_modul.simpan_sandi("uji-volume", "guru")
        assert tujuan.exists()
        assert sandi_modul.wajib_sandi()
        assert sandi_modul.periksa("guru", "uji-volume")
    finally:
        monkeypatch.delenv("OSN_BERKAS_SANDI", raising=False)
        importlib.reload(sandi_modul)


def test_folder_lembar_bisa_disetel_lewat_lingkungan(tmp_path, monkeypatch):
    """Regresi deploy ketiga dari kelas yang sama.

    Setelah basis data dan berkas sandi, `buat_lembar.py` masih menulis ke
    /app/lembar dan gagal dengan "Permission denied" di container. Pola yang
    berulang: apa pun yang DITULIS aplikasi harus bisa diarahkan ke volume,
    karena /app read-only.

    Test ini menahan jalur ketiga; kalau nanti ada jalur tulis baru, ia harus
    ikut daftar di test_semua_jalur_tulis_bisa_diarahkan().
    """
    import importlib

    tujuan = tmp_path / "volume" / "lembar"
    monkeypatch.setenv("OSN_FOLDER_LEMBAR", str(tujuan))

    import generate_worksheet as bl

    importlib.reload(bl)
    try:
        assert bl.KELUARAN == tujuan
    finally:
        monkeypatch.delenv("OSN_FOLDER_LEMBAR", raising=False)
        importlib.reload(bl)


def test_semua_jalur_tulis_bisa_diarahkan(tmp_path, monkeypatch):
    """Daftar tunggal semua lokasi yang ditulis aplikasi.

    Tiga kali berturut-turut deploy gagal karena satu jalur tulis terlewat:
    basis data, lalu berkas sandi, lalu folder lembar. Masing-masing hanya
    ketahuan setelah container mati di VPS, tidak pernah saat dijalankan di
    Mac.

    Test ini menjadi tempat tunggal untuk memeriksanya. Menambah jalur tulis
    baru tanpa mendaftarkannya di sini berarti mengulang kesalahan yang sama
    untuk keempat kalinya.
    """
    import importlib

    jalur = [
        ("OSN_BERKAS_DB", "database", "BAWAAN", tmp_path / "v" / "x.db"),
        ("OSN_BERKAS_SANDI", "auth", "BERKAS_SANDI", tmp_path / "v" / "s.json"),
        ("OSN_FOLDER_LEMBAR", "generate_worksheet", "KELUARAN", tmp_path / "v" / "lembar"),
    ]

    for env, nama_modul, atribut, tujuan in jalur:
        monkeypatch.setenv(env, str(tujuan))
        modul = importlib.import_module(nama_modul)
        importlib.reload(modul)
        try:
            assert getattr(modul, atribut) == tujuan, (
                f"{nama_modul}.{atribut} tidak menghormati {env} — "
                f"akan gagal di container"
            )
        finally:
            monkeypatch.delenv(env, raising=False)
            importlib.reload(modul)
