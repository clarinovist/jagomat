"""A3: sesi.topik nyata — guru memilih topik, UI menampilkan dari paket.

Titik rapuh: `sesi.topik` tadinya kolom mati (ditulis, tak pernah dibaca).
Kalau form guru tidak meneruskan pilihannya, atau laporan tidak
menampilkannya, kolomnya mati lagi — dan Fase B (topik kedua) akan diam-diam
menampilkan soal topik salah. Test ini mengunci jalurnya ujung ke ujung.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import students  # noqa: E402
import student_pages  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
import topics  # noqa: E402
import reports  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


# ── Rute POST /sesi-baru (socket sungguhan) ─────────────────────────────


def test_post_sesi_baru_prg_ke_halaman_anak_dengan_banner(server):
    """PRG buat sesi kini mendarat di /anak/<id> (feedback no. 6) — banner
    sukses + sesi baru disorot di history anak, bukan dashboard semua anak."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik PRG", pemilik="guru")
    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan"},
    )
    assert kode == 200
    assert "berhasil dibuat" in isi, "banner sukses harus tampil di /anak"
    assert "Sesi #" in isi, "sesi yang baru harus tampak di history anak"


def test_post_sesi_baru_menyimpan_topik_eksplisit(server):
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik Eksplisit", pemilik="guru")
    # urlopen mengikuti 303 sampai halaman sesi — yang dicek adalah
    # tempat akhir (halaman sesi) + nilai yang tersimpan di basis data.
    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan"},
    )
    assert kode == 200
    assert "Sesi #" in isi
    with server.buka() as kon:
        topik = kon.execute(
            """SELECT topik FROM sesi WHERE siswa_id = ?
               ORDER BY id DESC LIMIT 1""",
            (siswa_id,),
        ).fetchone()["topik"]
    assert topik == "pola-bilangan"


def test_post_sesi_baru_tanpa_topik_pakai_bawaan_kanonik(server):
    """Form tanpa pilihan topik tetap menyimpan id kanonik — bukan nilai
    lama 'pola bilangan' dengan spasi."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik Default", pemilik="guru")
    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 200
    assert "Sesi #" in isi
    with server.buka() as kon:
        topik = kon.execute(
            """SELECT topik FROM sesi WHERE siswa_id = ?
               ORDER BY id DESC LIMIT 1""",
            (siswa_id,),
        ).fetchone()["topik"]
    assert topik == "pola-bilangan"


def test_post_sesi_baru_topik_tak_dikenal_ditolak_400(server):
    """Topik asing = salah ketik pemanggil — ditolak jelas, bukan diam-diam
    jadi pola bilangan (kontrak beda dari level yang sengaja fallback)."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik Aneh")
    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "topik-hantu"},
    )
    assert kode == 400
    assert "topik-hantu" in isi


# ── UI guru: pilihan topik + tampilan ───────────────────────────────────


def _profil_anak(kon):
    """Pilihan topik/riwayat berada di profil, bukan kartu beranda."""
    siswa = kon.execute("SELECT * FROM siswa ORDER BY id DESC LIMIT 1").fetchone()
    return teacher_pages.halaman_anak(kon, siswa, pengguna="guru")


def test_profil_menyediakan_pilihan_topik_dari_registry(db):
    """Dropdown lahir dari registry — Fase B tinggal daftar, UI ikut."""
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Pilih Topik")
        isi = _profil_anak(kon).decode()
    assert 'name="topik"' in isi
    assert 'value="pola-bilangan"' in isi


def test_dropdown_menampilkan_nama_paket_bukan_id(db):
    """Task 1.6: opsi berlabel Paket.nama, value tetap id paket."""
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Pilih Nama Paket", "P5")
        isi = _profil_anak(kon).decode()
    # label = nama paket, value = id paket
    assert '<option value="geometri-datar">Geometri Datar</option>' in isi
    assert '<option value="pola-bilangan">Pola Bilangan</option>' in isi
    assert '<option value="aritmetika-dasar">Aritmetika Dasar</option>' in isi
    # id mentah tidak boleh tampil sebagai label
    assert ">geometri-datar</option>" not in isi
    assert ">pola-bilangan</option>" not in isi


def test_siswa_p3_tidak_ditawari_dan_tidak_bisa_memilih_aritmetika(server):
    """Topik P5/P6 tidak boleh memicu error server untuk siswa P3."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik P3", "P3", pemilik="guru")
        isi = _profil_anak(kon).decode()
    assert 'value="aritmetika-dasar"' not in isi

    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "aritmetika-dasar"},
    )
    assert kode == 400
    assert "tidak tersedia" in isi


def test_siswa_level_teks_lama_tetap_ditawari_dan_bisa_membuat_sesi(server):
    """Kolom tingkat lama yang bebas teks tetap mendapat fallback pola P3."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Topik Level Lama", "tingkat-lama", pemilik="guru")
        isi = _profil_anak(kon).decode()
    assert 'value="pola-bilangan"' in isi
    assert 'value="aritmetika-dasar"' not in isi

    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan"},
    )
    assert kode == 200
    assert "Sesi #" in isi
    with server.buka() as kon:
        level = kon.execute(
            "SELECT level FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["level"]
    assert level == "P3"


def test_profil_daftar_sesi_memuat_topik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Daftar Bertopik")
        database.buat_sesi(kon, sid, seed=77)
        isi = _profil_anak(kon).decode()
    assert "Topik" in isi
    assert "pola-bilangan" in isi


def test_header_halaman_sesi_meringkas_metadata_tanpa_slug(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Sesi Bertopik")
        sesi_id = database.buat_sesi(kon, sid, seed=78)
        jumlah = kon.execute(
            "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()[0]
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    kepala = isi.split('<header class="editorial-kepala-st">', 1)[1].split(
        "</header>", 1
    )[0]
    assert "pola-bilangan" not in kepala
    assert f"{jumlah} soal" in kepala


def test_laporan_menampilkan_kolom_topik(db):
    """Tren per sesi wajib menampilkan topiknya — laporan lintas-topik
    yang tercampur diam-diam adalah kegagalan desain (aturan plan §4)."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Laporan Bertopik")
        sesi_id = database.buat_sesi(kon, sid, seed=79)
        database.tandai_selesai(kon, sesi_id)
        isi = reports.halaman_laporan(kon, sid, section="riwayat").decode()
    assert '<th scope="col">Topik</th>' in isi
    assert "Pola Bilangan" in isi


def test_alur_aritmetika_memakai_judul_dan_laporan_topik_sendiri(server):
    """Topik kedua harus melewati jalur guru, murid, cetak, dan laporan.

    Test ini memakai socket sungguhan: dropdown yang berisi ID topik saja
    belum cukup kalau sesi, lembar, atau laporan masih diam-diam memilih
    paket pola bilangan.
    """
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", "P5", pemilik="guru")

    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "aritmetika-dasar"},
    )
    assert kode == 200
    assert "aritmetika-dasar" in isi

    with server.buka() as kon:
        sesi_id = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"]
        # 10 soal sejak komposisi aritmetika-dasar diperluas (gelombang 2,
        # 2 Sep 2026). Yang diuji di sini alurnya utuh, bukan angkanya —
        # dibaca dari komposisi paket supaya tidak perlu diubah lagi.
        harap = len(topics.ambil("aritmetika-dasar").komposisi["P5"])
        assert len(database.isi_sesi(kon, sesi_id)) == harap
        lembar = teacher_pages.halaman_lembar(kon, sesi_id)
        assert lembar is not None
        assert "Latihan Aritmetika Dasar" in lembar.decode()

    kode, isi, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID)
    )
    assert kode == 200
    assert "Latihan Aritmetika Dasar" in isi
    kode, _, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={"aksi": "selesai"},
    )
    assert kode == 200

    kode, isi, _ = server.minta(f"/laporan/{siswa_id}?section=riwayat", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Aritmetika Dasar" in isi


def test_laporan_detail_menampilkan_topik_pada_dua_tabel(db):
    """Query detail sudah memisahkan topik; UI wajib membuatnya terlihat."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Detail Topik", "P5")
        pola = database.buat_sesi(kon, sid, seed=77, topik="pola-bilangan")
        aritmetika = database.buat_sesi(
            kon, sid, seed=78, level="P5", topik="aritmetika-dasar"
        )
        for sesi_id, kode in ((pola, "K"), (aritmetika, "T")):
            baris = database.isi_sesi(kon, sesi_id)[0]
            jawaban_id = database.simpan_jawaban(kon, baris["sesi_soal_id"], "0")
            database.simpan_diagnosis(
                kon,
                jawaban_id,
                benar=False,
                kode_usulan=kode,
                kode_final=kode,
                malrule_id="uji.topik" if kode == "K" else None,
                alasan="uji topik",
            )
            database.tandai_selesai(kon, sesi_id)
        isi = reports.halaman_laporan(kon, sid, section="riwayat").decode()

        catatan = reports.halaman_laporan(kon, sid, section="riwayat", query='tampilan=catatan').decode()

    assert isi.count('<th scope="col">Topik</th>') == 1
    assert catatan.count('<th scope="col">Topik</th>') == 2
    assert 'Aritmetika Dasar' in catatan
    assert "Aritmetika Dasar" in isi
    assert "Pola Bilangan" in isi


# ── Judul dari paket topik (murid + lembar) ─────────────────────────────


def test_halaman_kerja_murid_judul_dari_paket(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Murid Judul")
        sesi_id = database.buat_sesi(kon, sid, seed=80)
        isi = student_pages.halaman_kerja_baru(kon, sid, sesi_id)
    assert isi is not None, "halaman kerja tidak terbangkit"
    # Judul kini berpola tunggal "<Halaman> · Jagomat" (brand.judul) —
    # yang dijaga test ini tetap sama: judulnya ikut PAKET TOPIK sesi.
    assert "<title>Kerjakan — Latihan Pola Bilangan · " in isi.decode()


def test_halaman_lembar_web_judul_dari_topik_sesi(db):
    """Lembar dibangkitkan ulang dari seed — judulnya harus mengikuti topik
    yang tersimpan di sesi, bukan paket bawaan yang selalu menang."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lembar Bertopik")
        sesi_id = database.buat_sesi(kon, sid, seed=81)
        isi = teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=False).decode()
        isi_guru = teacher_pages.halaman_lembar(kon, sesi_id, untuk_guru=True).decode()
    assert "Latihan Pola Bilangan" in isi
    assert "Penilaian — Pola Bilangan" in isi_guru


def test_murid_daftar_sesi_memuat_topik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Murid Daftar")
        database.buat_sesi(kon, sid, seed=82)
        isi = student_pages.halaman_daftar_sesi_baru(kon, sid, "Murid Daftar").decode()
    teks = re.sub(r"<[^>]+>", " ", isi)
    assert "Pola bilangan" in teks


# ── Alur penuh: guru buat → murid jawab → laporan guru ──────────────────


def test_alur_guru_murid_jawab_laporan_bertopik(server):
    """Sesi bertopik eksplisit dilalui ujung ke ujung lewat socket:
    laporan tetap utuh dan topiknya tampil, bukan tercampur diam-diam."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", pemilik="guru")  # nama == akun murid uji

    server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "pola-bilangan"},
    )
    with server.buka() as kon:
        sesi_id = kon.execute(
            """SELECT id FROM sesi WHERE siswa_id = ?
               ORDER BY id DESC LIMIT 1""",
            (siswa_id,),
        ).fetchone()["id"]
        ssid = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]

    kode, _, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}",
        auth=("feby", SANDI_MURID),
        data={
            f"jwb_{ssid}": "42",
            f"cara_{ssid}": "aku hitung",
            "aksi": "selesai",
        },
    )
    assert kode == 200

    kode, isi, _ = server.minta(f"/laporan/{siswa_id}?section=riwayat", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert '<th scope="col">Topik</th>' in isi
    assert "Pola Bilangan" in isi


# ── E2E geometri-datar (Task 1.7) ─────────────────────────────────────


def test_siswa_p5_melihat_geometri_datar_di_dropdown(server):
    """P5 melihat opsi Geometri Datar di dropdown."""
    with server.buka() as kon:
        database.tambah_siswa(kon, "P5 Geo", "P5")
        isi = _profil_anak(kon).decode()
    assert 'value="geometri-datar"' in isi
    assert "Geometri Datar" in isi


def test_siswa_p3_melihat_geometri_datar_di_dropdown(server):
    """P3 kini melihat Geometri Datar, Statistika, dan Logika di dropdown.

    Dulu P3 sengaja hanya pola-bilangan (Keputusan Pengguna #1 — test lama
    test_siswa_p3_tidak_melihat_geometri_datar). Dibalik 31 Agu 2026: band
    SASMO P1-4 memuat geometri/statistika/logika versi sederhana, jadi
    ketiga topik itu dibuka untuk P3 — dropdown lahir dari komposisi paket,
    topik tanpa kunci P3 tetap tersembunyi.
    """
    with server.buka() as kon:
        database.tambah_siswa(kon, "P3 Geo", "P3")
        isi = _profil_anak(kon).decode()
    for topik in ("pola-bilangan", "geometri-datar", "statistika", "logika"):
        assert f'value="{topik}"' in isi
    for topik in (
        "pengukuran",
        "teori-bilangan",
        "aritmetika-dasar",
        "kombinatorik",
        "aritmatika-lanjut",
        "geometri-ruang",
    ):
        assert f'value="{topik}"' not in isi


def test_siswa_p5_bisa_membuat_sesi_geometri_datar(server):
    """POST /sesi-baru geometri-datar → sesi tersimpan, lembar valid."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Sesi Geo", "P5", pemilik="guru")

    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "geometri-datar"},
    )
    assert kode == 200
    assert "Sesi #" in isi

    with server.buka() as kon:
        sesi = kon.execute(
            "SELECT id, topik FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()
        assert sesi["topik"] == "geometri-datar"
        n_soal = len(database.isi_sesi(kon, sesi["id"]))
        # P5 = 10 soal (komposisi tabel plan)
        assert n_soal == 10, f"P5 geometri punya {n_soal} soal, expected 10"


def test_alur_geometri_datar_guru_murid_laporan(server):
    """Alur penuh geometri lewat socket: dropdown, sesi, murid, laporan."""
    with server.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "feby", "P5", pemilik="guru")

    # dropdown memuat geometri-datar untuk P5
    with server.buka() as kon:
        isi = _profil_anak(kon).decode()
    assert 'value="geometri-datar"' in isi

    # buat sesi geometri
    kode, isi, _ = server.minta(
        f"/sesi-baru/{siswa_id}",
        auth=("guru", SANDI_GURU),
        data={"topik": "geometri-datar"},
    )
    assert kode == 200

    with server.buka() as kon:
        sesi_id = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
            (siswa_id,),
        ).fetchone()["id"]
        # Judul lembar diketik oleh paket
        lembar = teacher_pages.halaman_lembar(kon, sesi_id)
        assert lembar is not None
        assert "Latihan Geometri Datar" in lembar.decode()

    # halaman murid
    kode, isi, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID)
    )
    assert kode == 200
    assert "Latihan Geometri Datar" in isi
    kode, _, _ = server.minta(
        f"/murid/kerjakan/{sesi_id}", auth=("feby", SANDI_MURID),
        data={"aksi": "selesai"},
    )
    assert kode == 200

    # laporan guru menampilkan nama ramah, bukan ID internal
    kode, isi, _ = server.minta(f"/laporan/{siswa_id}?section=riwayat", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Geometri Datar" in isi
