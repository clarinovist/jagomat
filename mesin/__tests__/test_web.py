"""Verifikasi halaman guru — terutama rekonstruksi soal dari basis data.

Titik paling rapuh di lapisan ini: teks soal TIDAK disimpan, hanya
parameternya. Halaman guru membangun ulang soalnya lewat REGISTRI. Kalau
rekonstruksi meleset, guru menilai jawaban terhadap soal yang salah — dan
kesalahan itu senyap, karena halamannya tetap tampil normal.

Parameter bertipe tuple (pola siklus) melewati JSON sebagai string, jadi
harus dikembalikan ke bentuk semula. Itu yang paling mudah salah.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
import reports  # noqa: E402
from generator import buat_lembar  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


# ── Rekonstruksi soal ───────────────────────────────────────────────────


@pytest.mark.parametrize("seed", [1, 12, 77, 404, 2026])
def test_soal_dibangun_ulang_persis_sama(db, seed):
    """Soal hasil rekonstruksi harus identik dengan yang dicetak di kertas.

    Kalau berbeda, guru membaca soal yang tidak dikerjakan anak.
    """
    asli = buat_lembar(seed).soal
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Rekon")
        sesi_id = database.buat_sesi(kon, sid, seed=seed)
        for a, b in zip(asli, database.isi_sesi(kon, sesi_id)):
            ulang = teacher_pages._soal_dari_baris(b)
            assert ulang.teks == a.teks, f"teks {a.template_id} berbeda"
            assert ulang.kunci == a.kunci
            assert ulang.minta_restatement == a.minta_restatement
            assert ulang.tanda_tangan == a.tanda_tangan


def test_pola_siklus_terrestorasi_tanpa_konversi_khusus(db):
    """Soal siklus direstorasi dari bank tanpa konversi apa pun: parameter
    tersimpan JSON murni (A4) dan template menerima bentuk itu langsung."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tuple")
        sesi_id = database.buat_sesi(kon, sid, seed=88)
        for b in database.isi_sesi(kon, sesi_id):
            if b["template_id"] in ("siklus_huruf", "siklus_warna", "jumlah_siklus"):
                s = teacher_pages._soal_dari_baris(b)
                assert s.kunci == b["kunci"]


# ── Alur simpan + diagnosis ─────────────────────────────────────────────


def _isi(kon, sesi_id, jawaban_per_nomor, extra=None):
    data = {}
    for b in database.isi_sesi(kon, sesi_id):
        n = b["nomor"]
        if n in jawaban_per_nomor:
            data[f"jwb_{b['sesi_soal_id']}"] = jawaban_per_nomor[n]
            data[f"cara_{b['sesi_soal_id']}"] = "ada coretan"
        if extra:
            for k, v in extra.get(n, {}).items():
                data[f"{k}_{b['sesi_soal_id']}"] = v
    return data


def test_jawaban_benar_tercatat_benar(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Benar")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        isi = database.isi_sesi(kon, sesi_id)
        data = _isi(kon, sesi_id, {b["nomor"]: b["kunci"] for b in isi})

        teacher_pages.simpan_sesi(kon, sesi_id, data)
        database.tandai_selesai(kon, sesi_id)
        r = database.ringkasan(kon, sid)[0]

    assert r["benar"] == 12


def test_malrule_menghasilkan_kode_otomatis(db):
    """Inti penghematan waktu guru: kode muncul tanpa diketik."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Auto")
        sesi_id = database.buat_sesi(kon, sid, seed=6)

        jawaban, harapan = {}, {}
        for b in database.isi_sesi(kon, sesi_id):
            mal = database.malrule_soal(kon, b["soal_id"])
            if mal:
                jawaban[b["nomor"]] = mal[0]["jawaban"]
                harapan[b["nomor"]] = mal[0]["kode"]

        teacher_pages.simpan_sesi(kon, sesi_id, _isi(kon, sesi_id, jawaban))

        for b in database.isi_sesi(kon, sesi_id):
            if b["nomor"] in harapan:
                assert b["kode_final"] == harapan[b["nomor"]], (
                    f"soal {b['nomor']} ({b['template_id']}): "
                    f"kode {b['kode_final']} != {harapan[b['nomor']]}"
                )


def test_guru_bisa_menimpa_usulan_mesin(db):
    """Guru melihat coretan; mesin tidak. Keputusan guru harus menang."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Timpa")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        b = database.isi_sesi(kon, sesi_id)[0]
        mal = database.malrule_soal(kon, b["soal_id"])

        data = {
            f"jwb_{b['sesi_soal_id']}": mal[0]["jawaban"],
            f"cara_{b['sesi_soal_id']}": "coretan",
            f"kode_{b['sesi_soal_id']}": "E",  # guru memutuskan lain
        }
        teacher_pages.simpan_sesi(kon, sesi_id, data)
        hasil = database.isi_sesi(kon, sesi_id)[0]

    assert hasil["kode_final"] == "E"
    assert hasil["kode_usulan"] == mal[0]["kode"]  # usulan mesin tetap tersimpan
    assert hasil["manual"] == 1


def test_guru_bisa_menandai_benar_walau_mesin_bilang_salah(db):
    """Anak bisa benar dengan cara tak terduga; mesin tidak boleh memaksa."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Sah")
        sesi_id = database.buat_sesi(kon, sid, seed=8)
        b = database.isi_sesi(kon, sesi_id)[0]
        data = {
            f"jwb_{b['sesi_soal_id']}": "bentuk lain",
            f"cara_{b['sesi_soal_id']}": "cara alternatif",
            f"kode_{b['sesi_soal_id']}": "benar",
        }
        teacher_pages.simpan_sesi(kon, sesi_id, data)
        hasil = database.isi_sesi(kon, sesi_id)[0]

    assert hasil["benar"] == 1
    assert hasil["kode_final"] is None


def test_soal_dilewati_tidak_membuat_baris_kosong(db):
    """Guru sering mengisi sebagian dulu; sisanya tidak boleh tercatat
    sebagai 'sudah dinilai' dengan data kosong."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Sebagian")
        sesi_id = database.buat_sesi(kon, sid, seed=9)
        isi = database.isi_sesi(kon, sesi_id)
        data = {
            f"jwb_{isi[0]['sesi_soal_id']}": isi[0]["kunci"],
            f"cara_{isi[0]['sesi_soal_id']}": "coretan",
        }
        teacher_pages.simpan_sesi(kon, sesi_id, data)
        n = kon.execute("SELECT COUNT(*) AS n FROM jawaban").fetchone()["n"]

    assert n == 1


def test_centang_pengalaman_perlu_ditinjau_tanpa_kode(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tidak")
        sesi_id = database.buat_sesi(kon, sid, seed=10)
        b = database.isi_sesi(kon, sesi_id)[-1]
        teacher_pages.simpan_sesi(kon, sesi_id, {f"belum_{b['sesi_soal_id']}": "on"})
        hasil = database.isi_sesi(kon, sesi_id)[-1]

    assert hasil["kode_final"] is None


def test_kode_t_dipilih_guru_tanpa_memalsukan_pengalaman_anak(db):
    """T adalah keputusan guru, bukan checkbox yang diatribusikan kepada anak."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Tidak manual")
        sesi_id = database.buat_sesi(kon, sid, seed=10)
        b = database.isi_sesi(kon, sesi_id)[-1]
        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{b['sesi_soal_id']}": "jawaban lain",
                f"kode_{b['sesi_soal_id']}": "T",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[-1]

    assert hasil["kode_final"] == "T" and hasil['manual'] == 1
    assert not hasil["belum_pernah"]


def test_kode_t_lama_tetap_tanpa_mengarang_pengakuan_anak(db):
    """Data lama dengan T manual tidak boleh hilang saat form disimpan ulang."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Data T lama")
        sesi_id = database.buat_sesi(kon, sid, seed=10)
        b = database.isi_sesi(kon, sesi_id)[-1]
        jawaban_id = database.simpan_jawaban(
            kon, b["sesi_soal_id"], jawaban="jawaban lama"
        )
        database.simpan_diagnosis(
            kon,
            jawaban_id,
            benar=False,
            kode_usulan="N",
            kode_final="T",
            malrule_id=None,
            alasan="ditandai guru pada versi lama",
            manual=True,
        )
        database.tandai_selesai(kon, sesi_id)
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()

        potongan = halaman.split(f'name="belum_{b["sesi_soal_id"]}"', 1)[1]
        assert "checked" not in potongan.split(">", 1)[0]
        assert '<option value="T" selected>' in halaman

        teacher_pages.simpan_sesi(
            kon,
            sesi_id,
            {
                f"jwb_{b['sesi_soal_id']}": "jawaban lama",
                f"kode_{b['sesi_soal_id']}": "T",
            },
        )
        hasil = database.isi_sesi(kon, sesi_id)[-1]

    assert hasil["kode_final"] == "T"
    assert hasil["manual"]
    assert not hasil["belum_pernah"]


# ── Halaman tampil ──────────────────────────────────────────────────────


def test_halaman_utama_menampilkan_siswa(db):
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Andi")
        database.tambah_siswa(kon, "Bila")
        h = teacher_pages.halaman_utama_stitch(kon).decode()
    assert "Andi" in h
    assert "Bila" in h


def test_halaman_sesi_menampilkan_kunci_untuk_guru(db):
    """Kebalikan lembar anak: guru justru harus melihat kuncinya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lihat")
        sesi_id = database.buat_sesi(kon, sid, seed=13)
        isi = database.isi_sesi(kon, sesi_id)
        h = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
    for b in isi:
        assert b["kunci"] in h


def test_catatan_k_laporan_bukan_skor_kelulusan(db):
    """Catatan K bukan skor penguasaan; tetap dijelaskan pada riwayat."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lapor")
        database.buat_sesi(kon, sid, seed=14)
        h = reports.halaman_laporan(kon, sid, section="riwayat", query='tampilan=catatan').decode()
    assert "Jumlah K" in h
    assert "bukan skor" in h.lower()


def test_halaman_tidak_error_saat_sesi_kosong(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Kosong")
        h = reports.halaman_laporan(kon, sid).decode()
    assert "belum ada" in h.lower()


def test_nama_siswa_di_html_di_escape(db):
    """Nama anak masuk HTML; karakter khusus tidak boleh merusak halaman."""
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "A<script>x</script>")
        h = teacher_pages.halaman_utama_stitch(kon).decode()
    assert "<script>x</script>" not in h
    assert "&lt;script&gt;" in h


# ── Profil: skor, mode, durasi; beranda tanpa kolom lembar ──────────────


def _profil_anak(kon, siswa_id):
    siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (siswa_id,)).fetchone()
    return teacher_pages.halaman_anak(kon, siswa, pengguna="guru")


def test_profil_menampilkan_terisi_lalu_skor_saat_selesai(db):
    """Progres 3 terisi berubah ke 2 benar setelah sesi dikirim."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Skor")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        isi = database.isi_sesi(kon, sesi_id)
        data = _isi(
            kon, sesi_id,
            {1: isi[0]["kunci"], 2: isi[1]["kunci"], 3: "pasti salah"},
            {3: {"kode": "H"}},  # guru paksa salah hitung
        )
        teacher_pages.simpan_sesi(kon, sesi_id, data)
        h = _profil_anak(kon, sid).decode()
        database.tandai_selesai(kon, sesi_id)
        selesai = _profil_anak(kon, sid).decode()
    assert "3 dari 12 terisi" in h
    assert "2 dari 12 benar" in selesai
    assert "2 dari 12 benar" not in h


def test_dashboard_tanpa_kolom_lembar(db):
    """Lembar soal/kunci cukup satu pintu: dari halaman cetak. Dashboard
    yang menampilkan keduanya terasa redundant."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Lembar")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        h = teacher_pages.halaman_utama_stitch(kon).decode()
        hs = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
        hc_raw = teacher_pages.halaman_sesi_cetak(kon, sesi_id)
        assert hc_raw is not None
        hc = hc_raw.decode()
    assert 'href="/lembar/' not in h
    assert 'href="/lembar/' not in hs
    assert 'href="/lembar/' in hc


def test_profil_badge_mode_hanya_untuk_drill(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "ModeDrill")
        database.buat_sesi(kon, sid, seed=5, mode="drill")
        database.buat_sesi(kon, sid, seed=6)  # diagnostik
        h = _profil_anak(kon, sid).decode()
    assert h.count('<span>Latihan Cepat</span>') == 1


def test_profil_menampilkan_durasi_sesi_selesai(db):
    """Waktu = selesai − mulai (mm:ss), hanya bila keduanya tercatat."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Durasi")
        sesi_id = database.buat_sesi(kon, sid, seed=5)
        kon.execute(
            "UPDATE sesi SET mulai = '2026-08-30 10:00:00', "
            "selesai = '2026-08-30 10:12:30'"
        )
        butir = database.isi_sesi(kon, sesi_id)[0]
        database.simpan_jawaban(kon, butir["sesi_soal_id"], "1")
        h = _profil_anak(kon, sid).decode()
    assert "12:30" in h


def test_profil_tanpa_waktu_tidak_mengarang_durasi(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "TanpaWaktu")
        database.buat_sesi(kon, sid, seed=5)
        h = _profil_anak(kon, sid).decode()
    assert "Waktu 12:30" not in h
