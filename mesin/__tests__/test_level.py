"""Level P3-P6 harus benar-benar berpengaruh, bukan sekadar label.

Kolom `siswa.tingkat` sempat ada di skema sejak awal TAPI tidak pernah
dibaca siapa pun: mengubahnya jadi P4 tidak mengubah satu soal pun. Test di
berkas ini yang mencegah keadaan itu kembali diam-diam.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
import account_pages  # noqa: E402
from generator import buat_lembar, buat_soal, profil  # noqa: E402
from schema import MIGRASI  # noqa: E402
from templates import LEVEL, URUTAN_PER_LEVEL, level_valid, susun_lembar  # noqa: E402
from topic_number_patterns import PROFIL_LEVEL  # noqa: E402

SEED_UJI = list(range(1, 61))


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    with database.buka(p) as kon:
        yield kon


# -- Profil level ---------------------------------------------------------


def test_semua_level_punya_profil():
    assert set(PROFIL_LEVEL) == set(LEVEL)


def test_level_tak_dikenal_jatuh_ke_bawaan():
    """Satu nilai aneh di siswa.tingkat tidak boleh membuat guru gagal."""
    assert profil("kelas 4") == PROFIL_LEVEL["P3"]
    assert susun_lembar("entah") == susun_lembar("P3")


def test_level_valid_menolak_yang_di_luar_daftar():
    assert level_valid("P4")
    assert not level_valid("p4")
    assert not level_valid("kelas 4")
    assert not level_valid("")


def test_batas_angka_naik_monoton_antar_level():
    """P3 < P4 < P5 < P6 untuk tiap batas yang berupa rentang (lo, hi).

    Kunci yang berisi daftar pilihan (mis. beda_aritmetika, posisi_suku_n)
    dikecualikan: panjangnya bebas dan urutannya tidak bermakna. Yang
    diperiksa untuk daftar adalah nilai maksimumnya, di test terpisah.
    """
    berentang = [
        k
        for k, v in PROFIL_LEVEL["P3"].items()
        if isinstance(v, tuple)
        and len(v) == 2
        and all(isinstance(x, int) for x in v)
        and v[0] <= v[1]
        # daftar dua-pilihan (mis. n_jumlah_deret P3 = (8, 10)) tidak boleh
        # ikut: bentuknya sama dengan rentang tapi maknanya berbeda
        and k not in DAFTAR_PILIHAN
    ]
    assert berentang, "tidak ada satu pun batas berbentuk rentang"
    for kunci in berentang:
        nilai = [PROFIL_LEVEL[lv][kunci] for lv in LEVEL]
        atas = [hi for _, hi in nilai]
        assert atas == sorted(atas), f"{kunci}: batas atas tidak menaik: {atas}"
        assert len(set(atas)) == len(atas), f"{kunci}: ada level yang batasnya sama"


# Kunci profil yang isinya daftar pilihan rng.choice(), bukan rentang randint().
DAFTAR_PILIHAN = {
    "beda_aritmetika",
    "rasio_geometri",
    "kenaikan_bertingkat",
    "tambah_hari",
    "posisi_suku_n",
    "penyebut_pecahan",
    "n_jumlah_deret",
    "posisi_terbalik_geometri",
}


def test_daftar_pilihan_maksimumnya_menaik():
    """Untuk kunci berbentuk daftar, yang harus menaik adalah nilai terbesar."""
    for kunci in DAFTAR_PILIHAN:
        if kunci == "posisi_terbalik_geometri":
            continue  # bentuknya (lo2, hi2, lo3, hi3), diuji terpisah
        maks = [max(PROFIL_LEVEL[lv][kunci]) for lv in LEVEL]
        assert maks == sorted(maks), f"{kunci}: maksimum tidak menaik: {maks}"
        assert len(set(maks)) > 1, f"{kunci}: semua level punya maksimum sama"


# -- Level benar-benar mengubah soal --------------------------------------


@pytest.mark.parametrize("seed", SEED_UJI)
def test_seed_sama_level_beda_menghasilkan_lembar_beda(seed):
    """Inti Fase 1: level bukan label, ia mengubah soalnya."""
    p3 = buat_lembar(seed, level="P3")
    p6 = buat_lembar(seed, level="P6")
    assert p3.tanda_tangan != p6.tanda_tangan


@pytest.mark.parametrize("seed", SEED_UJI)
def test_setiap_template_berubah_antara_p3_dan_p6(seed):
    """Tidak boleh ada satu pun tipe soal yang identik di P3 dan P6.

    Versi pertama test ini hanya membandingkan tanda tangan SELURUH lembar,
    dan itu lolos meski 4 dari 12 soal (seluruh Bagian A) sama persis di
    keempat level — cukup satu soal berbeda untuk membuat tanda tangan
    lembar berbeda. Perbandingan per template yang menangkapnya.
    """
    p3 = buat_lembar(seed, level="P3")
    p6 = buat_lembar(seed, level="P6")
    sama = [
        a.template_id
        for a, b in zip(p3.soal, p6.soal)
        if a.parameter == b.parameter
    ]
    assert not sama, f"identik di P3 dan P6: {sama}"


def test_tiap_level_berbeda_dari_tetangganya():
    """P3≠P4, P4≠P5, P5≠P6 — bukan cuma ujung ke ujung."""
    for kiri, kanan in zip(LEVEL, LEVEL[1:]):
        beda = 0
        for seed in SEED_UJI:
            a = buat_lembar(seed, level=kiri)
            b = buat_lembar(seed, level=kanan)
            if a.tanda_tangan != b.tanda_tangan:
                beda += 1
        # Tabrakan sesekali wajar (rentang bertetangga bisa beririsan),
        # tapi mayoritas seed harus menghasilkan lembar berbeda.
        assert beda > len(SEED_UJI) * 0.9, f"{kiri} vs {kanan}: cuma {beda} beda"


@pytest.mark.parametrize("level", LEVEL)
def test_lembar_membawa_levelnya(level):
    lembar = buat_lembar(99, level=level)
    assert lembar.level == level
    assert all(s.level == level for s in lembar.soal)


@pytest.mark.parametrize("level", LEVEL)
def test_deterministik_per_level(level):
    a = buat_lembar(4242, level=level)
    b = buat_lembar(4242, level=level)
    assert a.tanda_tangan == b.tanda_tangan
    assert [s.kunci for s in a.soal] == [s.kunci for s in b.soal]


@pytest.mark.parametrize("seed", SEED_UJI)
def test_titik_segitiga_menghormati_batas_level(seed):
    for lv in LEVEL:
        s = buat_soal("titik_segitiga", seed, level=lv)
        lo, hi = PROFIL_LEVEL[lv]["gambar_titik"]
        assert lo <= s.parameter["gambar_ke"] <= hi


@pytest.mark.parametrize("seed", SEED_UJI)
def test_siklus_huruf_posisi_dalam_batas_level(seed):
    for lv in LEVEL:
        s = buat_soal("siklus_huruf", seed, level=lv)
        lo, hi = PROFIL_LEVEL[lv]["posisi_siklus"]
        # cabang "sisa 0" membulatkan ke kelipatan panjang pola, jadi batas
        # bawahnya bisa sedikit di bawah lo — yang dijaga adalah batas atas
        assert s.parameter["posisi"] <= hi


@pytest.mark.parametrize("seed", SEED_UJI)
def test_semua_level_tetap_punya_malrule(seed):
    """Soal tanpa malrule = beban menulis tanpa imbalan diagnosis."""
    for lv in LEVEL:
        for s in buat_lembar(seed, level=lv).soal:
            assert s.malrule, f"{s.template_id} di {lv} tidak punya malrule"


@pytest.mark.parametrize("seed", SEED_UJI)
def test_kunci_tidak_pernah_negatif_di_level_mana_pun(seed):
    for lv in LEVEL:
        s = buat_soal("deret_aritmetika_turun", seed, level=lv)
        assert int(s.kunci) >= 0


# -- Tanda tangan --------------------------------------------------------


def test_tanda_tangan_memisahkan_level():
    """Parameter identik di dua level harus jadi dua baris bank berbeda."""
    a = buat_soal("titik_segitiga", 1, level="P3")
    b = buat_soal("titik_segitiga", 1, level="P4")
    if a.parameter == b.parameter:
        assert a.tanda_tangan != b.tanda_tangan


def test_bank_tidak_menggabungkan_soal_lintas_level(db):
    from dataclasses import replace

    soal_p3 = buat_soal("titik_segitiga", 7, level="P3")
    soal_p5 = replace(soal_p3, level="P5")

    id_p3 = database.simpan_soal(db, soal_p3)
    id_p5 = database.simpan_soal(db, soal_p5)
    assert id_p3 != id_p5

    baris = db.execute(
        "SELECT level FROM soal WHERE id IN (?, ?) ORDER BY id", (id_p3, id_p5)
    ).fetchall()
    assert [r["level"] for r in baris] == ["P3", "P5"]


# -- Sesi menyimpan level -------------------------------------------------


@pytest.mark.parametrize("level", LEVEL)
def test_sesi_menyimpan_levelnya(db, level):
    sid = database.tambah_siswa(db, f"Anak{level}", level)
    sesi_id = database.buat_sesi(db, sid, 5150, level=level)
    baris = db.execute("SELECT level FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    assert baris["level"] == level
    for b in database.isi_sesi(db, sesi_id):
        assert b["level"] == level


def test_sesi_baru_memakai_tingkat_siswa(db):
    """Ini yang membuat kolom siswa.tingkat akhirnya berarti."""
    sid = database.tambah_siswa(db, "Naik", "P5")
    sesi_id = teacher_pages.buat_sesi_seed_baru(db, sid)
    baris = db.execute("SELECT level FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    assert baris["level"] == "P5"


def test_menaikkan_tingkat_tidak_mengubah_sesi_lama(db):
    """Riwayat tidak boleh berubah surut saat anak naik level."""
    sid = database.tambah_siswa(db, "Riwayat", "P3", pemilik="guru")
    lama = teacher_pages.buat_sesi_seed_baru(db, sid)

    pesan, galat = account_pages.proses_akun(
        db, {"aksi": "tingkat", "siswa_id": str(sid), "tingkat": "P6"}, "guru"
    )
    assert galat == ""
    assert "Kelas 6" in pesan

    baru = teacher_pages.buat_sesi_seed_baru(db, sid)

    level_lama = db.execute("SELECT level FROM sesi WHERE id = ?", (lama,)).fetchone()
    level_baru = db.execute("SELECT level FROM sesi WHERE id = ?", (baru,)).fetchone()
    assert level_lama["level"] == "P3"
    assert level_baru["level"] == "P6"


def test_lembar_sesi_lama_tetap_dirender_pada_levelnya(db):
    sid = database.tambah_siswa(db, "Cetak", "P3")
    sesi_id = database.buat_sesi(db, sid, 777, level="P3")
    db.execute("UPDATE siswa SET tingkat = 'P6' WHERE id = ?", (sid,))

    for b in database.isi_sesi(db, sesi_id):
        assert teacher_pages._soal_dari_baris(b).level == "P3"


# -- Validasi lewat halaman akun -----------------------------------------


def test_tambah_siswa_menolak_tingkat_ngawur(db):
    pesan, galat = account_pages.proses_akun(
        db, {"aksi": "anak_baru", "nama": "Salah", "tingkat": "kelas 4",
             "sandi_anak": "sandi-uji-12345"}, "guru"
    )
    assert pesan == ""
    assert "profil parameter" in galat and "P3" in galat
    assert db.execute("SELECT 1 FROM siswa WHERE nama = 'Salah'").fetchone() is None


def test_ubah_tingkat_menolak_nilai_ngawur(db):
    sid = database.tambah_siswa(db, "Tetap", "P3")
    pesan, galat = account_pages.proses_akun(
        db, {"aksi": "tingkat", "siswa_id": str(sid), "tingkat": "p4"}, "guru"
    )
    assert pesan == ""
    assert galat
    baris = db.execute("SELECT tingkat FROM siswa WHERE id = ?", (sid,)).fetchone()
    assert baris["tingkat"] == "P3"


def test_ubah_tingkat_menolak_siswa_tak_dikenal(db):
    pesan, galat = account_pages.proses_akun(
        db, {"aksi": "tingkat", "siswa_id": "9999", "tingkat": "P4"}, "guru"
    )
    assert pesan == ""
    assert galat


# -- Migrasi --------------------------------------------------------------


def test_migrasi_menambah_kolom_pada_db_lama(tmp_path):
    """Simulasikan basis data yang sudah jalan sebelum kolom level ada."""
    p = tmp_path / "lama.db"
    kon = sqlite3.connect(str(p))
    kon.row_factory = sqlite3.Row
    kon.executescript(
        """
        CREATE TABLE siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL UNIQUE,
            tingkat TEXT NOT NULL DEFAULT 'P3',
            dibuat TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE soal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanda_tangan TEXT NOT NULL UNIQUE,
            template_id TEXT NOT NULL,
            parameter TEXT NOT NULL,
            kunci TEXT NOT NULL,
            bagian TEXT NOT NULL DEFAULT '',
            tantangan INTEGER NOT NULL DEFAULT 0,
            dibuat TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE sesi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            siswa_id INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
            seed INTEGER NOT NULL,
            topik TEXT NOT NULL DEFAULT 'pola bilangan',
            tanggal TEXT NOT NULL DEFAULT (date('now')),
            mulai TEXT, selesai TEXT,
            catatan TEXT NOT NULL DEFAULT '',
            dibuat TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO siswa (nama) VALUES ('Lama');
        INSERT INTO sesi (siswa_id, seed) VALUES (1, 12345);
        """
    )
    kon.commit()
    kon.close()

    database.siapkan(p)

    with database.buka(p) as kon:
        kolom_sesi = {r["name"] for r in kon.execute("PRAGMA table_info(sesi)")}
        kolom_soal = {r["name"] for r in kon.execute("PRAGMA table_info(soal)")}
        assert "level" in kolom_sesi
        assert "level" in kolom_soal
        # Data lama selamat dan dapat level bawaan, bukan NULL.
        baris = kon.execute("SELECT seed, level FROM sesi WHERE id = 1").fetchone()
        assert baris["seed"] == 12345
        assert baris["level"] == "P3"


def test_migrasi_aman_dijalankan_berulang(tmp_path):
    p = tmp_path / "ulang.db"
    database.siapkan(p)
    database.siapkan(p)
    database.siapkan(p)
    with database.buka(p) as kon:
        assert database.migrasi(kon) == []


def test_view_ringkasan_terbangun_ulang_dengan_kolom_level(tmp_path):
    """View lama tidak diperbarui CREATE VIEW IF NOT EXISTS — harus di-DROP."""
    p = tmp_path / "view.db"
    database.siapkan(p)
    with database.buka(p) as kon:
        sid = database.tambah_siswa(kon, "Lihat", "P4")
        database.buat_sesi(kon, sid, 31337, level="P4")
    # panggil ulang: view harus tetap sehat, bukan menyisakan definisi lama
    database.siapkan(p)
    with database.buka(p) as kon:
        baris = kon.execute("SELECT * FROM ringkasan_sesi").fetchall()
        assert baris
        assert baris[0]["level"] == "P4"


def test_daftar_migrasi_tidak_punya_duplikat():
    pasangan = [(t, k) for t, k, _ in MIGRASI]
    assert len(pasangan) == len(set(pasangan))


# -- Bagian F: template yang menuntut rumus, bukan enumerasi -------------

BAGIAN_F = ("suku_ke_n", "sisa_bagi_siklus", "pola_pecahan", "jumlah_deret")


def test_bagian_f_tidak_muncul_di_p3():
    """P3 harus tetap seperti lembar 20 Agustus yang sudah terverifikasi."""
    dipakai = set(susun_lembar("P3"))
    assert not (dipakai & set(BAGIAN_F))


def test_bagian_f_makin_banyak_di_level_atas():
    jumlah = [
        sum(1 for t in susun_lembar(lv) if t in BAGIAN_F) for lv in LEVEL
    ]
    assert jumlah == sorted(jumlah), f"porsi Bagian F tidak menaik: {jumlah}"
    assert jumlah[0] == 0, "P3 seharusnya tanpa Bagian F"
    assert jumlah[-1] >= 4, f"P6 cuma {jumlah[-1]} soal Bagian F"


def test_tiap_level_tetap_dua_belas_soal():
    """Batas stamina, bukan angka keramat — lihat komentar URUTAN_PER_LEVEL."""
    for lv in LEVEL:
        assert len(susun_lembar(lv)) == 12, lv


def test_tidak_ada_template_terulang_dalam_satu_lembar():
    for lv in LEVEL:
        urutan = susun_lembar(lv)
        assert len(set(urutan)) == len(urutan), f"{lv} punya template ganda"


# Kunci Bagian F dihitung ulang dengan cara yang BERBEDA dari implementasinya
# (enumerasi/brute force, bukan rumus). Kalau keduanya sepakat, kuncinya sah.
# Satu kunci salah meracuni seluruh diagnosis di bawahnya.


@pytest.mark.parametrize("seed", SEED_UJI)
def test_kunci_suku_ke_n_dengan_enumerasi(seed):
    for lv in ("P4", "P5", "P6"):
        s = buat_soal("suku_ke_n", seed, level=lv)
        p = s.parameter
        # cara anak: tulis deretnya satu per satu sampai posisi yang diminta
        nilai = p["awal"]
        for _ in range(p["posisi"] - 1):
            nilai += p["beda"]
        assert s.kunci == str(nilai)


@pytest.mark.parametrize("seed", SEED_UJI)
def test_kunci_sisa_bagi_siklus_dengan_enumerasi(seed):
    for lv in ("P4", "P5", "P6"):
        s = buat_soal("sisa_bagi_siklus", seed, level=lv)
        pola = list(s.parameter["pola"])
        posisi = s.parameter["posisi"]
        rantai = (pola * (posisi // len(pola) + 2))[:posisi]
        assert s.kunci == rantai[-1]


@pytest.mark.parametrize("seed", SEED_UJI)
def test_kunci_pola_pecahan(seed):
    for lv in ("P5", "P6"):
        s = buat_soal("pola_pecahan", seed, level=lv)
        p = s.parameter
        pemb = p["pembilang"]
        for _ in range(p["n_tampil"]):
            pemb += p["beda_pembilang"]
        assert s.kunci == f"{pemb}/{p['penyebut']}"
        # penyebut TIDAK boleh berubah — itu justru malrule-nya
        assert s.kunci.split("/")[1] == str(p["penyebut"])


@pytest.mark.parametrize("seed", SEED_UJI)
def test_kunci_jumlah_deret_dengan_penjumlahan_beruntun(seed):
    s = buat_soal("jumlah_deret", seed, level="P6")
    p = s.parameter
    # cara anak: jumlahkan satu per satu, bukan rumus
    total = 0
    nilai = p["awal"]
    for _ in range(p["n"]):
        total += nilai
        nilai += p["beda"]
    assert s.kunci == str(total)


@pytest.mark.parametrize("seed", SEED_UJI)
def test_suku_ke_n_posisinya_jauh_supaya_manual_mati(seed):
    """Kalau posisinya cukup dekat untuk ditulis satu per satu, soal ini
    kehilangan seluruh maksudnya — ia jadi deret_aritmetika berbaju baru."""
    for lv in ("P4", "P5", "P6"):
        s = buat_soal("suku_ke_n", seed, level=lv)
        assert s.parameter["posisi"] >= 50, f"{lv}: posisi {s.parameter['posisi']}"


@pytest.mark.parametrize("seed", SEED_UJI)
def test_sisa_bagi_siklus_posisinya_jauh(seed):
    for lv in ("P4", "P5", "P6"):
        s = buat_soal("sisa_bagi_siklus", seed, level=lv)
        assert s.parameter["posisi"] >= 80


@pytest.mark.parametrize("seed", SEED_UJI)
def test_bagian_f_malrule_tidak_pernah_sama_dengan_kunci(seed):
    """Malrule yang menebak jawaban benar akan mencatat miskonsepsi palsu."""
    for nama in BAGIAN_F:
        for lv in ("P4", "P5", "P6"):
            s = buat_soal(nama, seed, level=lv)
            for m in s.malrule:
                assert m.jawaban != s.kunci, f"{nama}/{lv}: {m.id} == kunci"


@pytest.mark.parametrize("seed", SEED_UJI)
def test_bagian_f_malrule_tidak_saling_tabrakan(seed):
    """Satu jawaban salah tidak boleh memetakan ke dua kode berbeda."""
    for nama in BAGIAN_F:
        for lv in ("P4", "P5", "P6"):
            s = buat_soal(nama, seed, level=lv)
            jawaban = [m.jawaban for m in s.malrule]
            assert len(jawaban) == len(set(jawaban)), f"{nama}/{lv}"


@pytest.mark.parametrize("seed", SEED_UJI)
def test_bagian_f_angkanya_masih_terbayang_anak(seed):
    """Bilangan raksasa berhenti mendiagnosis dan hanya menguji ketelitian."""
    for nama in BAGIAN_F:
        for lv in ("P4", "P5", "P6"):
            s = buat_soal(nama, seed, level=lv)
            angka = [
                int(t)
                for t in s.kunci.replace("/", " ").replace(",", " ").split()
                if t.lstrip("-").isdigit()
            ]
            for a in angka:
                assert abs(a) <= 20000, f"{nama}/{lv}: kunci {s.kunci}"


def test_bagian_f_punya_kode_k_dan_h():
    """Tiap template harus bisa memisahkan salah konsep dari salah hitung.

    Template yang seluruh malrule-nya K tidak bisa membedakan anak yang
    caranya keliru dari anak yang cuma tersandung aritmetika — dan itu
    perbedaan yang seluruh aplikasi ini dibangun untuk menangkapnya.
    """
    for nama in BAGIAN_F:
        kode = set()
        for seed in range(1, 40):
            for lv in ("P4", "P5", "P6"):
                kode |= {m.kode for m in buat_soal(nama, seed, level=lv).malrule}
        assert "K" in kode, f"{nama}: tidak pernah menghasilkan K"
        assert "H" in kode, f"{nama}: tidak pernah menghasilkan H"


def test_setiap_template_bisa_membedakan_k_dari_h():
    """Berlaku untuk SELURUH template, bukan hanya Bagian F.

    Generalisasi dari bug nyata di `pola_pecahan`: malrule H-nya memakai
    rumus yang secara matematis SELALU sama dengan malrule K lain, sehingga
    selalu dibuang `saring_malrule` dan template itu tidak pernah punya
    jalur H. Anak yang cuma salah menjumlahkan tercatat salah konsep —
    kesalahan diagnosis yang paling mahal, karena mengirimnya mengulang
    materi yang sebenarnya sudah ia pahami.

    Bug seperti itu tidak kelihatan dari membaca kode template satu per
    satu; ia hanya muncul setelah penyaringan. Karena itu diperiksa di sini,
    terpusat, untuk semua template sekaligus.
    """
    from topics import paket_bawaan

    paket = paket_bawaan()
    tanpa_h: list[str] = []
    for nama in paket.templates:
        level_pemakai = [lv for lv in LEVEL if nama in paket.komposisi[lv]]
        kode = set()
        for seed in range(1, 60):
            for lv in level_pemakai:
                kode |= {m.kode for m in buat_soal(nama, seed, level=lv).malrule}
        if "H" not in kode:
            tanpa_h.append(f"{nama} (kode yang muncul: {sorted(kode)})")

    assert not tanpa_h, "template tanpa jalur H: " + "; ".join(tanpa_h)


def test_soal_bermalrule_tunggal_tidak_mendominasi():
    """Malrule tunggal = soal yang nyaris tidak mendiagnosis apa pun.

    Angka acuan diambil dari pengukuran nyata, bukan tebakan. `sisa_bagi_siklus`
    sempat 78% bermalrule tunggal karena polanya boleh hanya 2 huruf unik —
    dengan 2 huruf cuma ada SATU jawaban salah yang mungkin, jadi seluruh
    malrule menyusut jadi satu setelah penyaringan dan jalur H tidak pernah
    selamat. Setelah pola diwajibkan 4-6 huruf, angkanya turun ke ~6%.
    """
    from topics import paket_bawaan

    paket = paket_bawaan()
    buruk: list[str] = []
    for nama in paket.templates:
        level_pemakai = [lv for lv in LEVEL if nama in paket.komposisi[lv]]
        tunggal = total = 0
        for seed in range(1, 120):
            for lv in level_pemakai:
                total += 1
                if len(buat_soal(nama, seed, level=lv).malrule) <= 1:
                    tunggal += 1
        if total and tunggal / total > 0.35:
            buruk.append(f"{nama} {tunggal}/{total}")

    assert not buruk, "terlalu banyak soal bermalrule tunggal: " + "; ".join(buruk)


def test_pola_pecahan_selalu_pecahan_sejati():
    """Pecahan seperti 12/12 atau 15/12 benar secara pola tapi janggal.

    Sempat terjadi di 56% soal. Anak SD membaca 12/12 sebagai keanehan dan
    perhatiannya pindah ke situ, bukan ke pola yang sedang diuji.
    """
    for seed in range(1, 200):
        for lv in ("P5", "P6"):
            s = buat_soal("pola_pecahan", seed, level=lv)
            pembilang, penyebut = (int(x) for x in s.kunci.split("/"))
            assert pembilang < penyebut, f"{lv} seed {seed}: {s.kunci}"
            # malrule H melewati satu langkah — ia pun harus tetap sejati
            for m in s.malrule:
                if "/" in m.jawaban and m.id.endswith("penjumlahan_meleset"):
                    a, b = (int(x) for x in m.jawaban.split("/"))
                    assert a < b, f"malrule {m.id}: {m.jawaban}"


def test_sisa_bagi_siklus_polanya_cukup_kaya():
    """Minimal 3 huruf unik — batas matematis untuk punya >1 malrule."""
    for seed in range(1, 150):
        for lv in ("P4", "P5", "P6"):
            s = buat_soal("sisa_bagi_siklus", seed, level=lv)
            unik = len(set(s.parameter["pola"]))
            assert unik >= 3, f"{lv} seed {seed}: pola {s.parameter['pola']}"


# -- Urutan bagian di lembar --------------------------------------------


def test_bagian_tidak_pernah_terpecah_dalam_satu_lembar():
    """Tiap huruf bagian hanya boleh muncul sebagai SATU blok berurutan.

    `worksheets.lembar_soal` mencetak judul bagian setiap kali `soal.bagian`
    berganti. Kalau komposisi menaruh Bagian F, lalu E, lalu F lagi, lembar
    anak akan memuat judul "Bagian F" DUA KALI dengan Bagian E terselip di
    antaranya. Itu persis yang terjadi saat Bagian F pertama disusun:
    P6 keluar sebagai AAACDDFFFEEF.

    Anak membaca judul berulang sebagai tanda ia salah halaman atau ada
    yang terlewat. Bug ini tidak akan tertangkap test kunci mana pun karena
    seluruh soalnya benar — yang rusak hanya urutannya.
    """
    for lv in LEVEL:
        urut = [s.bagian for s in buat_lembar(7, level=lv).soal]
        blok: list[str] = []
        for b in urut:
            if not blok or blok[-1] != b:
                blok.append(b)
        assert len(blok) == len(set(blok)), (
            f"{lv}: bagian terpecah, urutannya {''.join(urut)}"
        )


def test_urutan_bagian_selalu_menaik():
    """A -> B -> C -> ... -> F, tidak pernah mundur.

    Lembar disusun mudah ke sulit, dan Bagian F adalah yang paling menuntut.
    Menaruhnya sebelum Bagian E berarti anak menabrak soal terberat saat
    tenaganya masih dibutuhkan untuk sisa lembar.
    """
    for lv in LEVEL:
        urut = [s.bagian for s in buat_lembar(7, level=lv).soal]
        assert urut == sorted(urut), f"{lv}: urutan bagian mundur — {''.join(urut)}"


def test_tiap_bagian_yang_terpakai_punya_judul_sendiri():
    """Judul fallback "Bagian F" polos berarti anak tidak diberi tahu apa
    yang berubah — dan Bagian F adalah satu-satunya bagian yang menuntut
    cara kerja berbeda."""
    from topics import paket_bawaan

    judul_bagian = paket_bawaan().judul_bagian

    for lv in LEVEL:
        for s in buat_lembar(7, level=lv).soal:
            assert s.bagian in judul_bagian, f"{lv}: bagian {s.bagian} tanpa judul"


# -- Malrule yang kolaps secara matematis ---------------------------------
#
# Dua bug sejenis sudah pernah lolos dari review manusia karena bentuknya
# tidak kelihatan dari membaca kode template — ia baru muncul SETELAH
# saring_malrule membuang kandidat yang bertabrakan:
#
#   1. pola_pecahan: malrule H `jawab_pemb - beda_pembilang` selalu sama
#      dengan malrule K `pemb[-1]`, jadi template tidak pernah punya jalur H.
#   2. deret_terbalik_geometri: saat awal == 1, malrule K
#      `target // awal` selalu sama dengan malrule B `target`, jadi 15,8%
#      soal tidak punya jalur K sama sekali.
#
# Keduanya satu kelas: malrule yang untuk SEBAGIAN parameter secara
# matematis identik dengan malrule lain, sehingga diam-diam dibuang dan
# soalnya kehilangan salah satu jalur diagnosis. Test di bawah menjaga
# SELURUH registri terhadap kelas itu, bukan dua kasusnya saja.


def _tanpa_jalur(nama: str, lv: str, kode_dibutuhkan: set[str]) -> int:
    from topics import paket_bawaan

    jumlah = total = 0
    paket = paket_bawaan()
    level_pemakai = [l for l in LEVEL if nama in paket.komposisi[l]]
    if lv not in level_pemakai:
        return 0
    for seed in range(1, 200):
        s = buat_soal(nama, seed, level=lv)
        total += 1
        if not kode_dibutuhkan & {m.kode for m in s.malrule}:
            jumlah += 1
    return jumlah * 100 // max(total, 1)


def test_tiap_template_per_soal_tidak_kehilangan_jalur_k():
    """Setiap soal harus punya minimal satu jalur K.

    Metrik utama proyek ini adalah jumlah miskonsepsi (K) yang tertangkap.
    Soal tanpa jalur K tidak menyumbang apa-apa ke situ DAN lebih berbahaya
    daripada itu: anak yang benar-benar salah konsep di soal itu tercatat
    sebagai salah hitung (B/H), lalu tindak lanjutnya meleset arah.
    """
    from topics import paket_bawaan

    buruk = []
    for nama in paket_bawaan().templates:
        persen = max(_tanpa_jalur(nama, lv, {"K"}) for lv in LEVEL)
        if persen > 2:
            buruk.append(f"{nama} {persen}%")
    assert not buruk, "soal tanpa jalur K terlalu sering: " + "; ".join(buruk)


def test_malrule_kolaps_tidak_ada_yang_identik_dengan_kunci():
    """Malrule yang jawabannya == kunci akan dibuang penyaringan, tapi
    kehadirannya di kode menyesatkan pembaca: ia SEolah-olah meng-cover
    miskonsepsi yang sebenarnya tidak pernah terdeteksi."""
    from topics import paket_bawaan

    paket = paket_bawaan()
    buruk = []
    for nama in paket.templates:
        level_pemakai = [lv for lv in LEVEL if nama in paket.komposisi[lv]]
        for seed in range(1, 120):
            for lv in level_pemakai:
                s = buat_soal(nama, seed, level=lv)
                tabrak = [m.id for m in s.malrule if m.jawaban == s.kunci]
                if tabrak:
                    buruk.append(f"{nama}/{lv} seed {seed}: {tabrak[0]}")
                    break
        if any(b.startswith(nama) for b in buruk):
            continue
    assert not buruk, "malrule identik dengan kunci: " + "; ".join(buruk[:8])
