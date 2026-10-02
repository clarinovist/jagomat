"""Poin a feedback Filia — sesi REMEDIAL otomatis dari kesalahan anak.

Lanjutan poin b. Setelah anak tahu letak salahnya, guru butuh satu klik
untuk melatih ulang HAL YANG SAMA dengan angka baru:

  "setelah mengetahui hasil anak, next nya apa yang harus kita lakukan?"

Kontrak yang dikunci:
  1. Sasaran remedial diambil dari DATA nyata (template yang dijawab
     salah / didiagnosis K), bukan tebakan.
  2. Sesi remedial memakai template yang sama tapi SOAL BARU (seed lain)
     — melatih konsep, bukan menghafal jawaban lembar lama.
  3. Anak yang tidak punya kesalahan tercatat -> tidak ada sesi remedial
     (jangan mengarang latihan tanpa dasar).
  4. Palang kepemilikan sama ketat dengan rute guru lain.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import topics  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


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


def _sesi_dengan_kesalahan(kon, nama="AnakRemedial"):
    """Sesi yang sudah dinilai: soal 1 benar, soal 2 & 3 salah."""
    import reports

    sid = database.tambah_siswa(kon, nama, pemilik="guru")
    sesi_id = database.buat_sesi(kon, sid, seed=7, jumlah_soal=4)
    baris = database.isi_sesi(kon, sesi_id)
    database.simpan_jawaban(kon, baris[0]["sesi_soal_id"],
                            jawaban=baris[0]["kunci"], cara="hitung")
    for b in baris[1:3]:
        database.simpan_jawaban(kon, b["sesi_soal_id"],
                                jawaban="999999", cara="hitung")
    reports.diagnosa_murid(kon, sesi_id)
    database.tandai_selesai(kon, sesi_id)
    kon.execute(
        "UPDATE sesi SET direview = datetime('now', '+7 hours') WHERE id = ?",
        (sesi_id,),
    )
    return sid, sesi_id


def _catat_hasil(
    kon,
    siswa_id,
    template_id,
    *,
    kode="K",
    benar=False,
    tanggal="2026-09-01",
    selesai=True,
    direview=True,
    alasan="Perlu memahami konsep ini lagi",
    topik=None,
):
    """Buat satu sesi satu-soal dengan diagnosis terkontrol."""
    paket = topics.paket_untuk_template([template_id])
    level = next(iter(paket.komposisi))
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=10_000 + kon.execute("SELECT COUNT(*) FROM sesi").fetchone()[0],
        urutan=(template_id,),
        topik=(topik or paket),
        level=level,
    )
    butir = database.isi_sesi(kon, sesi_id)[0]
    jawaban_id = database.simpan_jawaban(
        kon,
        butir["sesi_soal_id"],
        jawaban=butir["kunci"] if benar else "999999",
        cara="hitung",
    )
    database.simpan_diagnosis(
        kon,
        jawaban_id,
        benar=benar,
        kode_usulan=None if benar else kode,
        kode_final=None if benar else kode,
        alasan="" if benar else alasan,
    )
    kon.execute(
        "UPDATE sesi SET tanggal = ?, selesai = ?, direview = ? WHERE id = ?",
        (
            tanggal,
            "2026-09-01 10:00:00" if selesai else None,
            "2026-09-01 11:00:00" if direview else None,
            sesi_id,
        ),
    )
    return sesi_id


# ── 1. Sasaran remedial dari data nyata ───────────────────────────────


def test_sasaran_anak_terstruktur_dan_k_hanya_yang_direkomendasikan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakProfil", pemilik="guru")
        sesi_k = _catat_hasil(
            kon, sid, "soal_umur", kode="K", tanggal="2026-09-02",
            alasan="Belum memahami hubungan umur",
        )
        _catat_hasil(
            kon, sid, "soal_uang", kode="H", tanggal="2026-09-03",
            alasan="Perhitungannya belum teliti",
        )
        _catat_hasil(kon, sid, "jumlah_selisih", kode="T")
        sasaran = database.sasaran_remedial_anak(kon, sid)

    per_id = {b["template_id"]: b for b in sasaran}
    assert set(per_id) == {"soal_umur", "soal_uang"}
    assert per_id["soal_umur"] == {
        "template_id": "soal_umur",
        "topik": "logika",
        "kode": "K",
        "alasan": "Belum memahami hubungan umur",
        "kali_salah": 1,
        "sesi_terakhir": sesi_k,
        "tanggal_terakhir": "2026-09-02",
        "direkomendasikan": True,
    }
    assert per_id["soal_uang"]["kode"] == "H"
    assert per_id["soal_uang"]["direkomendasikan"] is False


def test_sasaran_anak_hanya_sesi_selesai_dan_direview(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakBelumSah", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", selesai=False, direview=False)
        _catat_hasil(kon, sid, "soal_uang", selesai=True, direview=False)
        assert database.sasaran_remedial_anak(kon, sid) == []


def test_bukti_terbaru_benar_menutup_kesalahan_lama(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakSudahBenar", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", tanggal="2026-09-01")
        _catat_hasil(
            kon, sid, "soal_umur", benar=True, tanggal="2026-09-04"
        )
        assert database.sasaran_remedial_anak(kon, sid) == []


def test_sasaran_sesi_hanya_kesalahan_non_t_dari_sesi_itu(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakSatuSesi", pemilik="guru")
        sumber = _catat_hasil(kon, sid, "soal_umur", kode="K")
        _catat_hasil(kon, sid, "soal_uang", kode="H")
        sasaran = database.sasaran_remedial_sesi(kon, sid, sumber)

    assert [b["template_id"] for b in sasaran] == ["soal_umur"]
    assert sasaran[0]["direkomendasikan"] is True
    assert sasaran[0]["sesi_terakhir"] == sumber


def test_sasaran_sesi_non_k_tampil_tapi_tidak_direkomendasikan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakKodeLain", pemilik="guru")
        sumber = _catat_hasil(kon, sid, "soal_uang", kode="B")
        sasaran = database.sasaran_remedial_sesi(kon, sid, sumber)
    assert sasaran[0]["kode"] == "B"
    assert sasaran[0]["direkomendasikan"] is False


def test_sasaran_sesi_menolak_lintas_anak_dan_belum_direview(db):
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "AnakSumberA", pemilik="guru")
        b = database.tambah_siswa(kon, "AnakSumberB", pemilik="guru")
        sumber_a = _catat_hasil(kon, a, "soal_umur")
        belum_review = _catat_hasil(
            kon, b, "soal_uang", selesai=True, direview=False
        )
        assert database.sasaran_remedial_sesi(kon, b, sumber_a) == []
        assert database.sasaran_remedial_sesi(kon, b, belum_review) == []


def test_sasaran_remedial_hanya_template_yang_salah(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dengan_kesalahan(kon)
        baris = database.isi_sesi(kon, sesi_id)
        sasaran = database.sasaran_remedial(kon, sid)
    salah = {b["template_id"] for b in baris[1:3]}
    benar_saja = baris[0]["template_id"]
    assert set(sasaran) == salah or salah <= set(sasaran)
    # template yang HANYA dijawab benar tidak ikut dilatih ulang
    if benar_saja not in salah:
        assert benar_saja not in sasaran


def test_sasaran_remedial_kosong_kalau_semua_benar(db):
    import reports

    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakSempurna", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7, jumlah_soal=3)
        for b in database.isi_sesi(kon, sesi_id):
            database.simpan_jawaban(kon, b["sesi_soal_id"],
                                    jawaban=b["kunci"], cara="hitung")
        reports.diagnosa_murid(kon, sesi_id)
        database.tandai_selesai(kon, sesi_id)
        assert database.sasaran_remedial(kon, sid) == []


def test_sasaran_remedial_terpisah_per_anak(db):
    with database.buka(db) as kon:
        _sid_a, _ = _sesi_dengan_kesalahan(kon, "AnakA")
        sid_b = database.tambah_siswa(kon, "AnakB", pemilik="guru")
        assert database.sasaran_remedial(kon, sid_b) == []


# ── 2. Sesi remedial: template sama, SOAL BARU ────────────────────────


def test_buat_sesi_dari_urutan_menolak_jenis_asing(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak Jenis", pemilik="guru")
        with pytest.raises(ValueError, match="jenis sesi"):
            database.buat_sesi_dari_urutan(
                kon,
                sid,
                seed=45,
                urutan=("soal_umur",),
                topik=topics.paket_untuk_template(["soal_umur"]),
                level="P3",
                jenis="asing",
            )
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(
                "INSERT INTO sesi (siswa_id, seed, jenis) VALUES (?, ?, ?)",
                (sid, 46, "asing"),
            )


def test_remedial_satu_template_mengisi_seluruh_sesi_dan_metadata(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakFokus", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", kode="K")
        rem = database.buat_sesi_remedial(
            kon,
            sid,
            template_ids=["soal_umur"],
            seed=99,
            jumlah_soal=10,
        )
        isi = database.isi_sesi(kon, rem)
        metadata = kon.execute(
            "SELECT jenis, sumber_sesi_id FROM sesi WHERE id = ?", (rem,)
        ).fetchone()
    assert [b["template_id"] for b in isi] == ["soal_umur"] * 10
    assert dict(metadata) == {"jenis": "remedial", "sumber_sesi_id": None}


def test_remedial_menolak_jumlah_lebih_kecil_dari_banyak_fokus(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak Fokus Banyak", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", kode="K")
        _catat_hasil(kon, sid, "soal_uang", kode="H")
        sebelum = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()[0]
        with pytest.raises(ValueError, match="setiap fokus"):
            database.buat_sesi_remedial(
                kon,
                sid,
                template_ids=["soal_umur", "soal_uang"],
                seed=102,
                jumlah_soal=1,
            )
        sesudah = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()[0]
    assert sesudah == sebelum


def test_remedial_multi_template_round_robin_tanpa_template_lain(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakMulti", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", kode="K")
        _catat_hasil(kon, sid, "soal_uang", kode="H")
        rem = database.buat_sesi_remedial(
            kon,
            sid,
            template_ids=["soal_umur", "soal_uang"],
            seed=101,
            jumlah_soal=5,
        )
        ids = [b["template_id"] for b in database.isi_sesi(kon, rem)]
    assert set(ids) == {"soal_umur", "soal_uang"}
    assert sorted(ids.count(t) for t in set(ids)) == [2, 3]


@pytest.mark.parametrize(
    "template_ids, jumlah_soal, pesan",
    [
        ([], 10, "kosong"),
        (["soal_umur", "soal_umur"], 10, "duplikat"),
        (["soal_umur", "soal_uang", "jumlah_selisih", "tabel_penalaran"], 10,
         "maksimal 3"),
        (["soal_umur"], 0, "jumlah_soal"),
        (["soal_umur"], 51, "jumlah_soal"),
    ],
)
def test_remedial_menolak_boundary_tanpa_membuat_sesi(
    db, template_ids, jumlah_soal, pesan
):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakBoundary", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", kode="K")
        sebelum = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()[0]
        with pytest.raises(ValueError, match=pesan):
            database.buat_sesi_remedial(
                kon,
                sid,
                template_ids=template_ids,
                seed=1,
                jumlah_soal=jumlah_soal,
            )
        sesudah = kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()[0]
    assert sesudah == sebelum


def test_remedial_menolak_template_bukan_kandidat(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakAsing", pemilik="guru")
        _catat_hasil(kon, sid, "soal_umur", kode="K")
        with pytest.raises(ValueError, match="bukan kandidat"):
            database.buat_sesi_remedial(
                kon, sid, template_ids=["soal_uang"], seed=2
            )


def test_remedial_sumber_menyimpan_id_dan_membatasi_kandidat(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakSumber", pemilik="guru")
        sumber = _catat_hasil(kon, sid, "soal_umur", kode="K")
        _catat_hasil(kon, sid, "soal_uang", kode="K")
        rem = database.buat_sesi_remedial(
            kon,
            sid,
            template_ids=["soal_umur"],
            sumber_sesi_id=sumber,
            seed=3,
        )
        metadata = kon.execute(
            "SELECT jenis, sumber_sesi_id FROM sesi WHERE id = ?", (rem,)
        ).fetchone()
        with pytest.raises(ValueError, match="bukan kandidat"):
            database.buat_sesi_remedial(
                kon,
                sid,
                template_ids=["soal_uang"],
                sumber_sesi_id=sumber,
                seed=4,
            )
    assert dict(metadata) == {"jenis": "remedial", "sumber_sesi_id": sumber}


def test_remedial_menolak_sumber_lintas_anak_dan_belum_direview(db):
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "AnakAmanA", pemilik="guru")
        b = database.tambah_siswa(kon, "AnakAmanB", pemilik="guru")
        sumber_a = _catat_hasil(kon, a, "soal_umur", kode="K")
        belum_review = _catat_hasil(
            kon, b, "soal_umur", kode="K", direview=False
        )
        for sumber in (sumber_a, belum_review):
            with pytest.raises(ValueError, match="sumber"):
                database.buat_sesi_remedial(
                    kon,
                    b,
                    template_ids=["soal_umur"],
                    sumber_sesi_id=sumber,
                    seed=5,
                )


def test_sesi_remedial_hanya_berisi_template_yang_salah(db):
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dengan_kesalahan(kon, "AnakR2")
        sasaran = set(database.sasaran_remedial(kon, sid))
        rem = database.buat_sesi_remedial(kon, sid, seed=99, jumlah_soal=6)
        isi = database.isi_sesi(kon, rem)
    assert rem is not None
    assert len(isi) == 6
    assert {b["template_id"] for b in isi} <= sasaran


def test_sesi_remedial_soalnya_baru_bukan_ulangan_lembar_lama(db):
    """Konsep sama, angka baru — melatih konsep, bukan hafalan jawaban."""
    with database.buka(db) as kon:
        sid, sesi_id = _sesi_dengan_kesalahan(kon, "AnakR3")
        lama = {b["kunci"] for b in database.isi_sesi(kon, sesi_id)}
        param_lama = {b["parameter"] for b in database.isi_sesi(kon, sesi_id)}
        rem = database.buat_sesi_remedial(kon, sid, seed=12345, jumlah_soal=6)
        baru = database.isi_sesi(kon, rem)
    # setidaknya ada soal yang parameternya berbeda dari lembar lama
    assert any(b["parameter"] not in param_lama for b in baru), (
        "sesi remedial mengulang soal identik — seharusnya angka baru"
    )


def test_sesi_remedial_none_kalau_tak_ada_kesalahan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakBersih", pemilik="guru")
        assert database.buat_sesi_remedial(kon, sid, seed=5) is None
        # dan tidak ada sesi yang terlanjur dibuat
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == 0


def test_sesi_remedial_deterministik(db):
    """Seed sama -> lembar sama (kontrak generator tidak boleh rusak)."""
    with database.buka(db) as kon:
        sid, _ = _sesi_dengan_kesalahan(kon, "AnakR4")
        a = database.buat_sesi_remedial(kon, sid, seed=777, jumlah_soal=5)
        b = database.buat_sesi_remedial(kon, sid, seed=777, jumlah_soal=5)
        ta = [x["kunci"] for x in database.isi_sesi(kon, a)]
        tb = [x["kunci"] for x in database.isi_sesi(kon, b)]
    assert ta == tb


# ── 3. Tombol + rute HTTP ─────────────────────────────────────────────


def _anak_dengan_kesalahan(server, nama="feby"):
    with server.buka() as kon:
        sid, _ = _sesi_dengan_kesalahan(kon, nama)
    return sid


def test_tombol_latihan_ulang_muncul_kalau_ada_kesalahan(server):
    sid = _anak_dengan_kesalahan(server, "AnakTombolR")
    kode, isi, _ = server.minta(
        f"/anak/{sid}?section=latihan", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert f'action="/sesi-remedial/{sid}"' in isi
    assert "Buat latihan ulang" in isi


def test_tombol_latihan_ulang_absen_kalau_belum_ada_kesalahan(server):
    """Tanpa dasar data, jangan menawarkan remedial."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakBaruBanget", pemilik="guru")
    kode, isi, _ = server.minta(f"/anak/{sid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "/sesi-remedial/" not in isi


def test_http_buat_latihan_ulang(server):
    sid = _anak_dengan_kesalahan(server, "AnakHttpR")
    with server.buka() as kon:
        sasaran = set(database.sasaran_remedial(kon, sid))
        fokus = next(iter(sasaran))
        sebelum = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    kode, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU),
        data={"template_id": fokus, "jumlah_soal": "10"},
    )
    assert kode == 200                       # 303 diikuti ke /anak/<id>
    assert "Remedial" in isi
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC", (sid,)
        ).fetchall()
        assert len(sesudah) == sebelum + 1
        isi_baru = database.isi_sesi(kon, int(sesudah[0]["id"]))
    assert len(isi_baru) == 10
    assert {b["template_id"] for b in isi_baru} <= sasaran


def test_http_latihan_ulang_tanpa_dasar_tidak_membuat_sesi(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakKosongR", pemilik="guru")
    kode, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 200
    assert "Pilih setidaknya satu tipe soal" in isi
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == 0


def test_http_latihan_ulang_anak_keluarga_lain_404(server):
    """Palang kepemilikan: guru lain tidak boleh membuat sesi untuk anak ini.

    Assertion WAJIB memeriksa efek sampingnya (jumlah sesi tidak bertambah),
    bukan hanya kode 404: mutation test membuktikan versi yang hanya
    meng-assert 404 tetap lolos walau palangnya dihapus, karena kode 404
    bisa datang dari cabang lain.
    """
    with server.buka() as kon:
        sid, _ = _sesi_dengan_kesalahan(kon, "AnakOrangLainR")
        kon.execute("UPDATE siswa SET pemilik = 'guru2' WHERE id = ?", (sid,))
        sebelum = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    kode, _, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 404
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert sesudah == sebelum, "sesi terbuat padahal bukan anak keluarganya"


# ── 4. Lintas topik — akar 502 produksi (3 Sep 2026) ──────────────────
#
# Sasaran remedial diambil dari SEMUA sesi anak, jadi template-nya bisa
# milik topik mana pun. Sebelum perbaikan ini `buat_sesi_remedial` selalu
# memakai paket bawaan (pola-bilangan), sehingga template topik lain
# (`soal_umur`, `tabel_penalaran`, ...) tidak ada di `paket.templates` dan
# generator melempar KeyError -> handler POST mati -> Caddy menjawab 502.
# Test lama tidak menangkapnya karena fixture-nya selalu memakai topik
# bawaan; di sini sesi sumbernya sengaja topik lain.


def _sesi_salah_topik(kon, nama, topik, level, jumlah=4):
    """Sesi topik NON-bawaan yang seluruh jawabannya salah."""
    import reports

    sid = database.tambah_siswa(kon, nama, pemilik="guru", tingkat=level)
    sesi_id = database.buat_sesi(
        kon, sid, seed=7, topik=topik, level=level, jumlah_soal=jumlah
    )
    for b in database.isi_sesi(kon, sesi_id):
        database.simpan_jawaban(kon, b["sesi_soal_id"],
                                jawaban="999999", cara="hitung")
    reports.diagnosa_murid(kon, sesi_id)
    database.tandai_selesai(kon, sesi_id)
    kon.execute(
        "UPDATE sesi SET direview = datetime('now', '+7 hours') WHERE id = ?",
        (sesi_id,),
    )
    return sid, sesi_id


def test_remedial_topik_selain_bawaan_tidak_meledak(db):
    """Regresi 502: anak yang salah di topik logika harus tetap dapat sesi."""
    with database.buka(db) as kon:
        sid, _ = _sesi_salah_topik(kon, "AnakLogika", "logika", "P5")
        sasaran = set(database.sasaran_remedial(kon, sid))
        assert sasaran, "prasyarat: harus ada kesalahan tercatat"
        rem = database.buat_sesi_remedial(
            kon, sid, seed=4242, level="P5", jumlah_soal=6
        )
        isi = database.isi_sesi(kon, rem)
    assert rem is not None
    assert len(isi) == 6
    assert {b["template_id"] for b in isi} <= sasaran


def test_remedial_lintas_dua_topik_sekaligus(db):
    """Kesalahan di dua topik berbeda tetap satu sesi remedial."""
    import reports

    with database.buka(db) as kon:
        sid, _ = _sesi_salah_topik(kon, "AnakDuaTopik", "logika", "P5")
        sesi2 = database.buat_sesi(
            kon, sid, seed=11, topik="statistika", level="P5", jumlah_soal=3
        )
        for b in database.isi_sesi(kon, sesi2):
            database.simpan_jawaban(kon, b["sesi_soal_id"],
                                    jawaban="999999", cara="hitung")
        reports.diagnosa_murid(kon, sesi2)
        database.tandai_selesai(kon, sesi2)
        kon.execute(
            "UPDATE sesi SET direview = datetime('now', '+7 hours') WHERE id = ?",
            (sesi2,),
        )

        sasaran = {
            b["template_id"] for b in database.sasaran_remedial_anak(kon, sid)
        }
        rem = database.buat_sesi_remedial(
            kon, sid, seed=555, level="P5", jumlah_soal=8
        )
        isi = database.isi_sesi(kon, rem)
    assert len(isi) == 8
    assert {b["template_id"] for b in isi} <= sasaran


def test_remedial_level_anak_tidak_didukung_topik_sasaran(db):
    """`siswa.tingkat` teks bebas: level yang tak didukung paket sasaran
    tidak boleh meledak — kontrak yang sama dengan komposisi_untuk()."""
    with database.buka(db) as kon:
        sid, _ = _sesi_salah_topik(kon, "AnakP4", "logika", "P5")
        # logika hanya punya P3/P5/P6; anak dipindah ke P4
        kon.execute("UPDATE siswa SET tingkat = 'P4' WHERE id = ?", (sid,))
        rem = database.buat_sesi_remedial(
            kon, sid, seed=606, level="P4", jumlah_soal=5
        )
        isi = database.isi_sesi(kon, rem)
    assert rem is not None
    assert len(isi) == 5


def test_remedial_topik_tersimpan_bisa_dibaca_ulang(db):
    """Kolom sesi.topik sesi remedial harus bisa direkonstruksi paketnya,
    supaya halaman lembar/cetak tidak jatuh ke paket bawaan yang salah."""
    import topics

    with database.buka(db) as kon:
        sid, _ = _sesi_salah_topik(kon, "AnakTopikSimpan", "logika", "P5")
        rem = database.buat_sesi_remedial(
            kon, sid, seed=808, level="P5", jumlah_soal=4
        )
        nilai = kon.execute(
            "SELECT topik FROM sesi WHERE id = ?", (rem,)
        ).fetchone()["topik"]
        template = {b["template_id"] for b in database.isi_sesi(kon, rem)}
    paket = topics.dari_sesi(nilai)
    assert template <= set(paket.templates), (
        f"paket {nilai!r} tidak memuat template sesinya sendiri"
    )


def test_http_remedial_lintas_topik_tidak_500(server):
    """Jalur HTTP penuh — inilah yang di produksi menjadi 502."""
    with server.buka() as kon:
        sid, _ = _sesi_salah_topik(kon, "AnakHttpLintas", "logika", "P5")
        fokus = database.sasaran_remedial(kon, sid)[0]
    kode, isi, _ = server.minta(
        f"/sesi-remedial/{sid}", auth=("guru", SANDI_GURU),
        data={"template_id": fokus, "jumlah_soal": "10"},
    )
    assert kode == 200, f"rute remedial gagal (kode {kode})"
    assert "Remedial" in isi
    with server.buka() as kon:
        terakhir = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC", (sid,)
        ).fetchone()["id"]
        assert len(database.isi_sesi(kon, int(terakhir))) == 10
