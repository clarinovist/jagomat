"""Penyimpanan sesi Latihan Lomba: timer yang dipegang server, satu sesi berjalan, jawaban, kepemilikan."""
import dataclasses
import json
import sqlite3

import pytest

import contest_core as C
import contest_session as S
import contest_store as T
import database

SEKARANG = 1_800_000_000
DURASI = 900                      # literal: 15 menit (bukan konstanta modul)
PG, ISIAN = "pg", "isian"
KOLOM_TERLARANG_UNTUK_ANAK = {
    "kunci", "posisi_kunci", "pengecoh_json", "pembahasan_json", "parameter",
    "tanda_tangan", "template_id", "tingkat", "inggris",
}


@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "lomba.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Satu", pemilik="guru")


@pytest.fixture
def anak_lain(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Dua", pemilik="guru")


def _mulai(kon, siswa_id, sekarang=SEKARANG, seed=1):
    return T.mulai_atau_lanjut(kon, siswa_id, sekarang, seed=seed)


def _soal_mentah(kon, sesi_id, nomor):
    return kon.execute("SELECT * FROM lomba_soal WHERE sesi_id=? AND nomor=?", (sesi_id, nomor)).fetchone()


def _jawaban_benar(kon, sesi_id, nomor):
    """Jawaban benar dari sisi uji (membaca kunci langsung dari DB): huruf untuk PG, angka untuk isian."""
    baris = _soal_mentah(kon, sesi_id, nomor)
    if baris["jenis"] == ISIAN:
        return baris["kunci"]
    return C.HURUF[json.loads(baris["pilihan_json"]).index(baris["kunci"])]


def _jawaban_salah(kon, sesi_id, nomor):
    baris = _soal_mentah(kon, sesi_id, nomor)
    if baris["jenis"] == ISIAN:
        return str(int(baris["kunci"]) + 1)
    benar = _jawaban_benar(kon, sesi_id, nomor)
    return next(h for h in C.HURUF if h != benar)


def _jenis(kon, sesi_id, nomor):
    return _soal_mentah(kon, sesi_id, nomor)["jenis"]


def _isi_semua(kon, siswa_id, sesi_id, benar_sampai, sekarang=SEKARANG + 10):
    """Jawab 10 soal: nomor <= benar_sampai dijawab benar, sisanya salah."""
    for nomor in range(1, 11):
        pilih = _jawaban_benar if nomor <= benar_sampai else _jawaban_salah
        T.simpan_jawaban(kon, siswa_id, sesi_id, nomor, pilih(kon, sesi_id, nomor), sekarang)


# --- skema ---------------------------------------------------------------------------

def test_tabel_lomba_ada_dan_siapkan_idempoten(tmp_path):
    path = tmp_path / "idem.db"
    database.siapkan(path)
    database.siapkan(path)
    with database.buka(path) as k:
        tabel = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"lomba_sesi", "lomba_soal", "lomba_jawaban"} <= tabel
        assert k.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_indeks_unik_menolak_dua_sesi_berjalan_untuk_satu_anak(kon, anak):
    sql = ("INSERT INTO lomba_sesi(siswa_id, paket_id, seed, mulai_epoch, batas_epoch, status) "
           "VALUES (?, 'x', 1, 10, 910, 'berjalan')")
    kon.execute(sql, (anak,))
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(sql, (anak,))


def test_sesi_selesai_boleh_banyak_untuk_satu_anak(kon, anak):
    sql = ("INSERT INTO lomba_sesi(siswa_id, paket_id, seed, mulai_epoch, batas_epoch, selesai_epoch, status) "
           "VALUES (?, 'x', 1, 10, 910, 910, 'waktu_habis')")
    kon.execute(sql, (anak,))
    kon.execute(sql, (anak,))
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 2


def test_menghapus_siswa_ikut_menghapus_data_lomba_tanpa_terblokir(kon, anak):
    sesi = _mulai(kon, anak)
    T.simpan_jawaban(kon, anak, sesi.id, 1, _jawaban_benar(kon, sesi.id, 1), SEKARANG + 5)
    kon.execute("DELETE FROM siswa WHERE id=?", (anak,))
    for tabel in ("lomba_sesi", "lomba_soal", "lomba_jawaban"):
        assert kon.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone()[0] == 0


# --- mulai dan lanjut ----------------------------------------------------------------

def test_mulai_membuat_sesi_berjalan_dengan_batas_lima_belas_menit_dan_sepuluh_soal(kon, anak):
    sesi = _mulai(kon, anak)
    assert (sesi.status, sesi.mulai_epoch, sesi.batas_epoch) == ("berjalan", SEKARANG, SEKARANG + 900)
    jenis = [r["jenis"] for r in kon.execute("SELECT jenis FROM lomba_soal WHERE sesi_id=? ORDER BY nomor", (sesi.id,))]
    assert len(jenis) == 10 and jenis.count(PG) == 8 and jenis.count(ISIAN) == 2


def test_mulai_dua_kali_melanjutkan_sesi_yang_sama(kon, anak):
    pertama = _mulai(kon, anak)
    kedua = _mulai(kon, anak, sekarang=SEKARANG + 300, seed=99)
    assert kedua.id == pertama.id and kedua.batas_epoch == SEKARANG + 900
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 1


def test_mulai_setelah_waktu_habis_menutup_sesi_lama_dan_membuat_yang_baru(kon, anak):
    lama = _mulai(kon, anak)
    baru = _mulai(kon, anak, sekarang=SEKARANG + 900, seed=2)
    assert baru.id != lama.id and baru.status == "berjalan"
    baris = kon.execute("SELECT status, selesai_epoch FROM lomba_sesi WHERE id=?", (lama.id,)).fetchone()
    assert (baris["status"], baris["selesai_epoch"]) == ("waktu_habis", SEKARANG + 900)


def test_sesi_anak_lain_tidak_saling_mengganggu(kon, anak, anak_lain):
    a, b = _mulai(kon, anak), _mulai(kon, anak_lain, seed=2)
    assert a.id != b.id and a.status == b.status == "berjalan"


def test_mulai_yang_kalah_balapan_melanjutkan_sesi_pemenang(kon, anak, monkeypatch):
    pemenang = _mulai(kon, anak)
    asli = T._berjalan
    panggilan = {"n": 0}

    def berjalan_basi(*argumen, **kata):
        panggilan["n"] += 1
        return None if panggilan["n"] == 1 else asli(*argumen, **kata)

    monkeypatch.setattr(T, "_berjalan", berjalan_basi)
    hasil = _mulai(kon, anak, sekarang=SEKARANG + 5, seed=7)
    assert hasil.id == pemenang.id
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 1


def test_gagal_merakit_tidak_meninggalkan_sesi_setengah_jadi(kon, anak, monkeypatch):
    def gagal(*argumen, **kata):
        raise S.GagalMerakitSesi("uji")

    monkeypatch.setattr(S, "rakit_sesi", gagal)
    with pytest.raises(S.GagalMerakitSesi):
        _mulai(kon, anak)
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 0


def test_kegagalan_menyimpan_soal_membatalkan_seluruh_sesi(kon, anak, monkeypatch):
    asli = S.rakit_sesi

    def rusak(*argumen, **kata):
        sesi = asli(*argumen, **kata)
        butir = list(sesi.butir)
        butir[-1] = dataclasses.replace(butir[-1], nomor=1)        # nomor ganda -> melanggar PK
        return dataclasses.replace(sesi, butir=tuple(butir))

    monkeypatch.setattr(S, "rakit_sesi", rusak)
    with pytest.raises(sqlite3.IntegrityError):
        _mulai(kon, anak)
    assert kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM lomba_soal").fetchone()[0] == 0


def test_sesi_berurutan_tidak_mengulang_soal_dan_merotasi_jenis(kon, anak):
    sebelumnya_tanda, sebelumnya_template = None, None
    for urut in range(6):
        sesi = _mulai(kon, anak, sekarang=SEKARANG + urut * 2000, seed=urut)
        baris = kon.execute("SELECT tanda_tangan, template_id FROM lomba_soal WHERE sesi_id=?", (sesi.id,)).fetchall()
        tanda = {r["tanda_tangan"] for r in baris}
        template = {r["template_id"] for r in baris}
        if sebelumnya_tanda is not None:
            assert not tanda & sebelumnya_tanda
            assert not template & sebelumnya_template
        sebelumnya_tanda, sebelumnya_template = tanda, template
        T.kumpulkan(kon, anak, sesi.id, SEKARANG + urut * 2000 + 30)


# --- membaca sesi dan finalisasi malas -------------------------------------------------

def test_ambil_sesi_menghitung_sisa_detik_dari_jam_server(kon, anak):
    sesi = _mulai(kon, anak)
    ambil = T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 100)
    assert ambil.status == "berjalan" and ambil.sisa_detik(SEKARANG + 100) == 800


def test_satu_detik_sebelum_batas_masih_berjalan(kon, anak):
    sesi = _mulai(kon, anak)
    assert T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 899).status == "berjalan"


def test_tepat_pada_batas_waktu_sesi_ditutup(kon, anak):
    sesi = _mulai(kon, anak)
    ambil = T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 900)
    assert (ambil.status, ambil.selesai_epoch, ambil.sisa_detik(SEKARANG + 900)) == ("waktu_habis", SEKARANG + 900, 0)


def test_finalisasi_waktu_habis_memakai_batas_bukan_waktu_dibuka(kon, anak):
    sesi = _mulai(kon, anak)
    ambil = T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 5000)
    assert ambil.selesai_epoch == SEKARANG + 900


def test_ambil_sesi_berulang_setelah_habis_tetap_sama(kon, anak):
    sesi = _mulai(kon, anak)
    pertama = T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 1000)
    kedua = T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 9000)
    assert pertama == kedua


def test_sesi_milik_anak_lain_atau_tidak_ada_ditolak_sama_rata(kon, anak, anak_lain):
    sesi = _mulai(kon, anak)
    with pytest.raises(T.SesiTidakDitemukan):
        T.ambil_sesi(kon, anak_lain, sesi.id, SEKARANG)
    with pytest.raises(T.SesiTidakDitemukan):
        T.ambil_sesi(kon, anak, sesi.id + 999, SEKARANG)


def test_sesi_berjalan_milik_anak_mengembalikan_none_bila_tidak_ada(kon, anak):
    assert T.sesi_berjalan(kon, anak, SEKARANG) is None
    sesi = _mulai(kon, anak)
    assert T.sesi_berjalan(kon, anak, SEKARANG + 1).id == sesi.id
    assert T.sesi_berjalan(kon, anak, SEKARANG + 900) is None


# --- soal yang dilihat anak: tanpa kunci --------------------------------------------------

def test_soal_untuk_anak_tidak_pernah_membaca_kolom_berkunci(kon, anak):
    sesi = _mulai(kon, anak)
    terbaca = set()

    def pengawas(aksi, tabel, kolom, *_):
        if aksi == sqlite3.SQLITE_READ and tabel == "lomba_soal":
            terbaca.add(kolom)
        return sqlite3.SQLITE_OK

    kon.set_authorizer(pengawas)
    try:
        for nomor in range(1, 11):
            T.soal_untuk_anak(kon, anak, sesi.id, nomor)
    finally:
        kon.set_authorizer(lambda *_: sqlite3.SQLITE_OK)     # Python 3.9 belum mendukung set_authorizer(None)
    assert terbaca, "pengawas tidak melihat pembacaan apa pun"
    assert not terbaca & KOLOM_TERLARANG_UNTUK_ANAK, terbaca & KOLOM_TERLARANG_UNTUK_ANAK


def test_soal_untuk_anak_hanya_membawa_bidang_yang_aman(kon, anak):
    sesi = _mulai(kon, anak)
    soal = T.soal_untuk_anak(kon, anak, sesi.id, 1)
    assert {f.name for f in dataclasses.fields(soal)} == {
        "nomor", "jenis", "topik", "teks", "svg", "pilihan", "gambar_pilihan", "jawaban"}


def test_soal_pg_punya_empat_pilihan_dan_isian_tidak_punya(kon, anak):
    sesi = _mulai(kon, anak)
    for nomor in range(1, 11):
        soal = T.soal_untuk_anak(kon, anak, sesi.id, nomor)
        if soal.jenis == PG:
            assert len(soal.pilihan) == 4 and len(set(soal.pilihan)) == 4 and len(soal.gambar_pilihan) == 4
        else:
            assert soal.pilihan == () and soal.gambar_pilihan == ()


def test_soal_untuk_anak_menolak_nomor_tidak_ada_dan_milik_anak_lain(kon, anak, anak_lain):
    sesi = _mulai(kon, anak)
    for nomor in (0, 11):
        with pytest.raises(T.SesiTidakDitemukan):
            T.soal_untuk_anak(kon, anak, sesi.id, nomor)
    with pytest.raises(T.SesiTidakDitemukan):
        T.soal_untuk_anak(kon, anak_lain, sesi.id, 1)


# --- menyimpan jawaban ------------------------------------------------------------------

def test_simpan_jawaban_pg_dan_ganti_jawaban(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "B", SEKARANG + 5)
    assert T.soal_untuk_anak(kon, anak, sesi.id, nomor).jawaban == "B"
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "d", SEKARANG + 6)
    assert T.soal_untuk_anak(kon, anak, sesi.id, nomor).jawaban == "D"


def test_simpan_jawaban_isian_menormalkan_angka(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == ISIAN)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, " 007 ", SEKARANG + 5)
    assert T.soal_untuk_anak(kon, anak, sesi.id, nomor).jawaban == "7"


def test_jawaban_kosong_menghapus_jawaban_tersimpan(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "A", SEKARANG + 5)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "", SEKARANG + 6)
    assert T.soal_untuk_anak(kon, anak, sesi.id, nomor).jawaban is None
    assert nomor not in T.nomor_terjawab(kon, anak, sesi.id)


@pytest.mark.parametrize("jawaban", ["E", "AB", "1", "-", "<b>"])
def test_jawaban_pg_tidak_sah_ditolak(kon, anak, jawaban):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    with pytest.raises(T.JawabanTidakSah):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, jawaban, SEKARANG + 5)


@pytest.mark.parametrize("jawaban", ["abc", "1.5", "-1", "1234567", "A", "1e3", "12 3"])
def test_jawaban_isian_tidak_sah_ditolak(kon, anak, jawaban):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == ISIAN)
    with pytest.raises(T.JawabanTidakSah):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, jawaban, SEKARANG + 5)


@pytest.mark.parametrize("nomor", [0, 11, -1])
def test_nomor_di_luar_sesi_ditolak(kon, anak, nomor):
    sesi = _mulai(kon, anak)
    with pytest.raises(T.SesiTidakDitemukan):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, "A", SEKARANG + 5)


def test_jawaban_ditolak_tepat_pada_batas_dan_jawaban_lama_tidak_berubah(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "A", SEKARANG + 899)
    with pytest.raises(T.SesiSelesai):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, "B", SEKARANG + 900)
    assert kon.execute("SELECT jawaban FROM lomba_jawaban WHERE sesi_id=? AND nomor=?",
                       (sesi.id, nomor)).fetchone()["jawaban"] == "A"
    assert T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 900).status == "waktu_habis"


def test_jawaban_ditolak_setelah_dikumpulkan(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    T.kumpulkan(kon, anak, sesi.id, SEKARANG + 60)
    with pytest.raises(T.SesiSelesai):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, "A", SEKARANG + 61)
    assert kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] == 0


def test_hapus_jawaban_juga_ditolak_setelah_waktu_habis(kon, anak):
    sesi = _mulai(kon, anak)
    nomor = next(n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG)
    T.simpan_jawaban(kon, anak, sesi.id, nomor, "C", SEKARANG + 10)
    with pytest.raises(T.SesiSelesai):
        T.simpan_jawaban(kon, anak, sesi.id, nomor, "", SEKARANG + 901)
    assert kon.execute("SELECT jawaban FROM lomba_jawaban WHERE sesi_id=?", (sesi.id,)).fetchone()["jawaban"] == "C"


def test_anak_lain_tidak_bisa_menyimpan_jawaban_dan_tanpa_efek_samping(kon, anak, anak_lain):
    sesi = _mulai(kon, anak)
    with pytest.raises(T.SesiTidakDitemukan):
        T.simpan_jawaban(kon, anak_lain, sesi.id, 1, "A", SEKARANG + 5)
    assert kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] == 0


def test_nomor_terjawab_hanya_memuat_soal_yang_dijawab(kon, anak):
    sesi = _mulai(kon, anak)
    pg = [n for n in range(1, 11) if _jenis(kon, sesi.id, n) == PG][:2]
    for nomor in pg:
        T.simpan_jawaban(kon, anak, sesi.id, nomor, "A", SEKARANG + 5)
    assert T.nomor_terjawab(kon, anak, sesi.id) == frozenset(pg)


# --- mengumpulkan ------------------------------------------------------------------------

def test_kumpul_sebelum_batas_mencatat_waktu_kumpul(kon, anak):
    sesi = _mulai(kon, anak)
    hasil = T.kumpulkan(kon, anak, sesi.id, SEKARANG + 120)
    assert (hasil.status, hasil.selesai_epoch) == ("dikumpul", SEKARANG + 120)


def test_kumpul_setelah_batas_dicatat_sebagai_waktu_habis_pada_batas(kon, anak):
    sesi = _mulai(kon, anak)
    hasil = T.kumpulkan(kon, anak, sesi.id, SEKARANG + 2000)
    assert (hasil.status, hasil.selesai_epoch) == ("waktu_habis", SEKARANG + 900)


def test_kumpul_dua_kali_tidak_mengubah_apa_pun(kon, anak):
    sesi = _mulai(kon, anak)
    pertama = T.kumpulkan(kon, anak, sesi.id, SEKARANG + 120)
    kedua = T.kumpulkan(kon, anak, sesi.id, SEKARANG + 500)
    assert pertama == kedua


def test_kumpul_milik_anak_lain_ditolak(kon, anak, anak_lain):
    sesi = _mulai(kon, anak)
    with pytest.raises(T.SesiTidakDitemukan):
        T.kumpulkan(kon, anak_lain, sesi.id, SEKARANG + 5)
    assert T.ambil_sesi(kon, anak, sesi.id, SEKARANG + 6).status == "berjalan"


# --- hasil ringkas -----------------------------------------------------------------------

def test_hasil_saat_sesi_masih_berjalan_ditolak(kon, anak):
    sesi = _mulai(kon, anak)
    with pytest.raises(T.SesiBerjalan):
        T.hasil_ringkas(kon, anak, sesi.id, SEKARANG + 10)


@pytest.mark.parametrize("benar_sampai", [0, 3, 10])
def test_nilai_dihitung_dari_jawaban_benar_saja(kon, anak, benar_sampai):
    sesi = _mulai(kon, anak)
    _isi_semua(kon, anak, sesi.id, benar_sampai)
    T.kumpulkan(kon, anak, sesi.id, SEKARANG + 300)
    hasil = T.hasil_ringkas(kon, anak, sesi.id, SEKARANG + 301)
    assert (hasil.nilai, hasil.jumlah_soal, hasil.waktu_terpakai_detik) == (benar_sampai, 10, 300)


def test_soal_tanpa_jawaban_dihitung_salah(kon, anak):
    sesi = _mulai(kon, anak)
    T.simpan_jawaban(kon, anak, sesi.id, 1, _jawaban_benar(kon, sesi.id, 1), SEKARANG + 5)
    T.kumpulkan(kon, anak, sesi.id, SEKARANG + 20)
    assert T.hasil_ringkas(kon, anak, sesi.id, SEKARANG + 21).nilai == 1


def test_nilai_sesi_yang_habis_waktunya_memakai_jawaban_sebelum_batas(kon, anak):
    sesi = _mulai(kon, anak)
    _isi_semua(kon, anak, sesi.id, 4, sekarang=SEKARANG + 800)
    hasil = T.hasil_ringkas(kon, anak, sesi.id, SEKARANG + 5000)
    assert (hasil.nilai, hasil.status, hasil.waktu_terpakai_detik) == (4, "waktu_habis", 900)


def test_hasil_milik_anak_lain_ditolak(kon, anak, anak_lain):
    sesi = _mulai(kon, anak)
    T.kumpulkan(kon, anak, sesi.id, SEKARANG + 5)
    with pytest.raises(T.SesiTidakDitemukan):
        T.hasil_ringkas(kon, anak_lain, sesi.id, SEKARANG + 6)


# --- sambungan riwayat ke perakit sesi --------------------------------------------------------

def test_riwayat_lima_sesi_untuk_tanda_tangan_dan_dua_sesi_untuk_rotasi_diteruskan_ke_perakit(
        kon, anak, monkeypatch):
    id_sesi = []
    for urut in range(7):
        sesi = _mulai(kon, anak, sekarang=SEKARANG + urut * 2000, seed=urut)
        T.kumpulkan(kon, anak, sesi.id, SEKARANG + urut * 2000 + 30)
        id_sesi.append(sesi.id)
    tercatat = {}
    asli = S.rakit_sesi

    def mata(seed, pool, terlarang, template_dihindari=frozenset()):
        tercatat["terlarang"], tercatat["hindari"] = terlarang, template_dihindari
        return asli(seed, pool, terlarang, template_dihindari)

    monkeypatch.setattr(S, "rakit_sesi", mata)
    _mulai(kon, anak, sekarang=SEKARANG + 20000, seed=99)

    def kolom(nama, sesi_ids):
        penampung = ",".join("?" * len(sesi_ids))
        return {r[0] for r in kon.execute(
            f"SELECT {nama} FROM lomba_soal WHERE sesi_id IN ({penampung})", sesi_ids)}

    assert tercatat["terlarang"] == kolom("tanda_tangan", id_sesi[-5:])        # tepat lima sesi terakhir
    assert tercatat["hindari"] == kolom("template_id", id_sesi[-2:])           # tepat dua sesi terakhir
    assert kolom("tanda_tangan", id_sesi[:2]) - tercatat["terlarang"]          # sesi lama sudah tidak dilarang
