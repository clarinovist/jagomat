"""Variasi cerita LLM (B2) — kalimat berubah, kunci tidak."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import llm  # noqa: E402
import presentation_lock  # noqa: E402
import web  # noqa: E402
import teacher_pages  # noqa: E402
from visual_contract import deserialisasi_penyajian  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-uji")
    return p


def _palsu(monkeypatch, kalimat_fn):
    """Ganti llm.bungkus supaya tidak ada panggilan API sungguhan.

    Tanda tangannya harus ikut `putaran` (latar berputar): bungkus_sesi
    memanggil ulang dengan latar berikutnya kalau latar pertama gagal
    verifikasi.
    """
    monkeypatch.setattr(
        llm, "bungkus", lambda kon, soal, putaran=0: kalimat_fn(soal)
    )


def test_cerita_mengganti_kalimat_tanpa_menyentuh_kunci(db, monkeypatch):
    """Inti kontrak B2: parameter & kunci tetap hasil hitungan Python.
    Kalau kunci ikut berubah, seluruh diagnosis jadi salah menilai."""
    _palsu(monkeypatch, lambda s: "Di toko ada " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        sebelum = {b["nomor"]: b["kunci"] for b in database.isi_sesi(kon, ses)}
        n, dicoba, _ = llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
        assert n == dicoba == 12
        sesudah = {b["nomor"]: b["kunci"] for b in database.isi_sesi(kon, ses)}
    assert sebelum == sesudah, "kunci berubah — diagnosis akan menilai salah"


def test_sesi_terkunci_tidak_menawarkan_variasi_cerita(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Fixture terkunci")
        ses = database.buat_sesi(kon, sid, seed=42, jumlah_soal=1)
        presentation_lock.bekukan_penyajian(kon, ses)
        isi = teacher_pages._tombol_cerita(kon, ses)
        assert f'action="/cerita/{ses}"' not in isi
        assert "dikunci" in isi


def test_status_ui_cerita_membaca_snapshot_bukan_bank(db, monkeypatch):
    _palsu(monkeypatch, lambda s: "Cerita: " + s.teks)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Fixture")
        ses = database.buat_sesi(kon, sid, seed=42, jumlah_soal=1)
        llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
        isi = teacher_pages._tombol_cerita(kon, ses)
        assert "Semua 1 soal sudah punya versi cerita" in isi
        assert f'action="/cerita/{ses}"' not in isi


def test_soal_bercerita_tidak_dibayar_dua_kali(db, monkeypatch):
    """Soal yang sudah punya cerita dilewati — kalimatnya sudah dibayar,
    dan anak mungkin sudah mengerjakannya."""
    _palsu(monkeypatch, lambda s: "Cerita: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
        n2, dicoba2, catatan = llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
    assert dicoba2 == 0
    assert "sudah punya" in catatan


def test_bank_cerita_bersama_tidak_membuat_snapshot_sesi_lain_dianggap_selesai(
    db, monkeypatch
):
    nomor_cerita = 0

    def cerita_baru(soal):
        nonlocal nomor_cerita
        nomor_cerita += 1
        return f"Cerita {nomor_cerita}: " + soal.teks.replace(chr(10), " ")

    _palsu(monkeypatch, cerita_baru)
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        pertama = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        kedua = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)

        llm.bungkus_sesi(kon, pertama, teacher_pages._soal_dari_baris)
        berhasil, dicoba, _ = llm.bungkus_sesi(
            kon, kedua, teacher_pages._soal_dari_baris
        )
        baris_pertama = database.isi_sesi(kon, pertama)[0]
        baris_kedua = database.isi_sesi(kon, kedua)[0]

    assert (berhasil, dicoba) == (1, 1)
    assert baris_pertama["teks_soal"].startswith("Cerita 1:")
    assert baris_kedua["teks_soal"].startswith("Cerita 2:")


def test_fitur_mati_tanpa_kunci_api(db, monkeypatch):
    """Gagal-diam: tanpa kunci, tidak ada panggilan dan tidak ada exception."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        n, dicoba, catatan = llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
    assert n == 0 and dicoba == 0
    assert "tidak aktif" in catatan


def test_tombol_tidak_muncul_kalau_fitur_mati(db, monkeypatch):
    """Fitur yang mati harus terlihat mati — bukan muncul lalu gagal
    saat ditekan."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        html_sesi = teacher_pages.halaman_sesi_stitch(kon, ses).decode()
        html_cetak_raw = teacher_pages.halaman_sesi_cetak(kon, ses)
        html_cetak = html_cetak_raw.decode() if html_cetak_raw else ""
    assert "Opsi tambahan: ubah cerita soal" not in html_sesi
    assert "Opsi tambahan: ubah cerita soal" not in html_cetak


def test_tombol_muncul_di_cetak_kalau_fitur_hidup(db):
    """Opsi 3: Variasi cerita pindah ke /sesi/{id}/cetak."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        html_sesi = teacher_pages.halaman_sesi_stitch(kon, ses).decode()
        html_cetak_raw = teacher_pages.halaman_sesi_cetak(kon, ses)
        assert html_cetak_raw is not None
        html_cetak = html_cetak_raw.decode()
    assert "Opsi tambahan: ubah cerita soal" not in html_sesi
    assert "Opsi tambahan: ubah cerita soal" in html_cetak
    assert "0 dari 12" in html_cetak


def test_latar_kedua_dicoba_kalau_latar_pertama_gagal(db, monkeypatch):
    """Verifikasi angka sengaja galak, dan sebagian latar memang sulit
    dipakai tanpa menambah angka ("lomba 17 Agustus" menggoda model
    menulis 17). Menyerah setelah satu latar berarti soal kembali ke
    kalimat bawaan padahal latar berikutnya mungkin lolos."""
    putaran_terlihat: list[int] = []

    def bungkus_palsu(kon, soal, putaran=0):
        putaran_terlihat.append(putaran)
        # Latar pertama selalu gagal verifikasi; yang kedua lolos.
        if putaran == 0:
            return None
        return "Latar kedua: " + soal.teks.replace(chr(10), " ")

    monkeypatch.setattr(llm, "bungkus", bungkus_palsu)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        n, dicoba, _ = llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
    assert set(putaran_terlihat) == {0, 1}
    assert n == dicoba == 12, "latar kedua tidak menyelamatkan soal"


def test_kalimat_cerita_tampil_di_lembar_anak(db, monkeypatch):
    """Yang dikerjakan anak harus kalimat ceritanya, bukan kalimat bawaan."""
    _palsu(monkeypatch, lambda s: "Kebun Pak Tani: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak")
        ses = database.buat_sesi(kon, sid, seed=42)
        llm.bungkus_sesi(kon, ses, teacher_pages._soal_dari_baris)
        lembar = teacher_pages.halaman_lembar(kon, ses).decode()
    assert "Kebun Pak Tani" in lembar


def _kunci_mulai(kon, _siswa_id, sesi_id, _butir):
    kon.execute("UPDATE sesi SET mulai = '2026-09-06 10:00:00' WHERE id = ?", (sesi_id,))


def _kunci_selesai(kon, _siswa_id, sesi_id, _butir):
    kon.execute("UPDATE sesi SET selesai = '2026-09-06 10:30:00' WHERE id = ?", (sesi_id,))


def _kunci_jawaban(kon, _siswa_id, _sesi_id, butir):
    kon.execute("INSERT INTO jawaban (sesi_soal_id) VALUES (?)", (butir,))


def _kunci_konfirmasi(kon, _siswa_id, sesi_id, _butir):
    kon.execute(
        """INSERT INTO konfirmasi_hasil (sesi_id, nomor_urut, guru, fingerprint)
           VALUES (?, 1, 'guru', 'story-lock')""",
        (sesi_id,),
    )


def _kunci_bukti(kon, siswa_id, sesi_id, _butir):
    putaran = kon.execute(
        "INSERT INTO putaran_fokus (siswa_id, level) VALUES (?, 'P3')",
        (siswa_id,),
    ).lastrowid
    anggota = kon.execute(
        """INSERT INTO anggota_fokus
               (putaran_id, slot, template_id, kode_intervensi)
           VALUES (?, 1, 'deret_aritmetika', 'K')""",
        (putaran,),
    ).lastrowid
    kon.execute(
        "INSERT INTO bukti_fokus (anggota_fokus_id, sesi_id) VALUES (?, ?)",
        (anggota, sesi_id),
    )


def _kunci_cetak(kon, _siswa_id, sesi_id, _butir):
    kon.execute(
        "UPDATE sesi SET penyajian_dibekukan = datetime('now') WHERE id = ?",
        (sesi_id,),
    )


@pytest.mark.parametrize(
    "pengunci",
    [
        _kunci_mulai,
        _kunci_selesai,
        _kunci_jawaban,
        _kunci_konfirmasi,
        _kunci_bukti,
        _kunci_cetak,
    ],
)
def test_preflight_menolak_state_terkunci_sebelum_memanggil_api(
    db, monkeypatch, pengunci
):
    panggilan_saldo = 0
    panggilan_model = 0

    def cek_saldo_mahal(*_args, **_kwargs):
        nonlocal panggilan_saldo
        panggilan_saldo += 1
        return True

    def bungkus_mahal(*_args, **_kwargs):
        nonlocal panggilan_model
        panggilan_model += 1
        return "Tidak boleh dibayar"

    monkeypatch.setattr(llm, "cek_saldo", cek_saldo_mahal)
    monkeypatch.setattr(llm, "bungkus", bungkus_mahal)
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        sesi = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=2)
        sebelum = database.isi_sesi(kon, sesi)
        butir = sebelum[0]["sesi_soal_id"]
        pengunci(kon, siswa, sesi, butir)

        hasil = llm.bungkus_sesi(kon, sesi, teacher_pages._soal_dari_baris)

        sesudah = database.isi_sesi(kon, sesi)
        assert hasil[0:2] == (0, 0)
        assert "terkunci" in hasil[2]
        assert panggilan_saldo == 0
        assert panggilan_model == 0
        assert [b["cerita"] for b in sesudah] == [b["cerita"] for b in sebelum]
        assert [b["fingerprint_penyajian"] for b in sesudah] == [
            b["fingerprint_penyajian"] for b in sebelum
        ]


def test_cerita_dual_write_hanya_mengubah_snapshot_sesi_target(db, monkeypatch):
    _palsu(monkeypatch, lambda s: "Cerita target: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        target = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=2)
        lain = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=2)
        awal_target = database.isi_sesi(kon, target)
        awal_lain = database.isi_sesi(kon, lain)
        sidik_awal = [b["fingerprint_penyajian"] for b in awal_target]
        cerita_bank_awal = [b["cerita"] for b in awal_target]

        berhasil, dicoba, _ = llm.bungkus_sesi(
            kon, target, teacher_pages._soal_dari_baris
        )

        akhir_target = database.isi_sesi(kon, target)
        akhir_lain = database.isi_sesi(kon, lain)

    assert berhasil == dicoba == 2
    assert [b["soal_id"] for b in akhir_target] == [b["soal_id"] for b in akhir_lain]
    for sebelum, sesudah in zip(awal_target, akhir_target):
        snapshot_awal = deserialisasi_penyajian(sebelum["penyajian_json"])
        snapshot_akhir = deserialisasi_penyajian(sesudah["penyajian_json"])
        assert sesudah["cerita"] == cerita_bank_awal[sesudah["nomor"] - 1]
        assert snapshot_akhir.teks_soal.startswith("Cerita target:")
        assert snapshot_akhir.asal_teks == "cerita"
        assert snapshot_akhir.fingerprint_matematis == snapshot_awal.fingerprint_matematis
        assert snapshot_akhir.descriptor == snapshot_awal.descriptor
        assert snapshot_akhir.status_visual == snapshot_awal.status_visual
        assert snapshot_akhir.mode_representasi == snapshot_awal.mode_representasi
        assert snapshot_akhir.penyajian_versi == snapshot_awal.penyajian_versi
        assert snapshot_akhir.renderer_versi == snapshot_awal.renderer_versi
        assert snapshot_akhir.fingerprint_penyajian != snapshot_awal.fingerprint_penyajian
    assert [b["fingerprint_penyajian"] for b in akhir_lain] == [
        b["fingerprint_penyajian"] for b in awal_lain
    ]
    assert [b["teks_soal"] for b in akhir_lain] == [b["teks_soal"] for b in awal_lain]
    assert [b["fingerprint_penyajian"] for b in akhir_target] != sidik_awal


def test_cerita_tidak_mengakhiri_transaksi_pemanggil(db, monkeypatch):
    _palsu(monkeypatch, lambda s: "Cerita transaksi: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        sesi = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        kon.commit()
        kon.execute("SAVEPOINT transaksi_luar")

        llm.bungkus_sesi(kon, sesi, teacher_pages._soal_dari_baris)
        kon.execute("ROLLBACK TO SAVEPOINT transaksi_luar")
        kon.execute("RELEASE SAVEPOINT transaksi_luar")

        sesudah = database.isi_sesi(kon, sesi)[0]

    assert sesudah["asal_teks"] == "bawaan"


def test_cache_bungkus_mengikuti_rollback_transaksi_pemanggil(
    db, monkeypatch
):
    with database.buka(db) as kon:
        llm.ensure_table(kon)
        siswa = database.tambah_siswa(kon, "Anak")
        sesi = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        soal = teacher_pages._soal_dari_baris(database.isi_sesi(kon, sesi)[0])
        monkeypatch.setattr(llm, "_panggil", lambda _pesan: soal.teks)
        kon.commit()
        kon.execute("SAVEPOINT transaksi_luar")

        assert llm.bungkus(kon, soal) is not None
        kon.execute("ROLLBACK TO SAVEPOINT transaksi_luar")
        kon.execute("RELEASE SAVEPOINT transaksi_luar")

        assert kon.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0] == 0


def test_dual_write_dirollback_jika_update_snapshot_gagal(db, monkeypatch):
    _palsu(monkeypatch, lambda s: "Cerita atomik: " + s.teks.replace(chr(10), " "))
    asli = presentation_lock.perbarui_snapshot
    panggilan = 0

    def gagal_kedua(*args, **kwargs):
        nonlocal panggilan
        panggilan += 1
        if panggilan == 2:
            return False
        return asli(*args, **kwargs)

    monkeypatch.setattr(presentation_lock, "perbarui_snapshot", gagal_kedua)
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        sesi = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=2)
        sebelum = database.isi_sesi(kon, sesi)

        berhasil, dicoba, catatan = llm.bungkus_sesi(
            kon, sesi, teacher_pages._soal_dari_baris
        )

        sesudah = database.isi_sesi(kon, sesi)

    assert (berhasil, dicoba) == (0, 2)
    assert "berubah" in catatan or "gagal" in catatan
    assert [b["cerita"] for b in sesudah] == [b["cerita"] for b in sebelum]
    assert [b["fingerprint_penyajian"] for b in sesudah] == [
        b["fingerprint_penyajian"] for b in sebelum
    ]


def test_snapshot_all_null_warisan_diinisialisasi_per_sesi_tanpa_mutasi_bank(
    db, monkeypatch
):
    _palsu(monkeypatch, lambda s: "Cerita warisan: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        sesi = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        butir = database.isi_sesi(kon, sesi)[0]
        cerita_bank_awal = butir["cerita"]
        kon.execute(
            """UPDATE sesi_soal SET
                   teks_soal = NULL, bagian_soal = NULL, tantangan_soal = NULL,
                   minta_restatement = NULL, penyajian_json = NULL,
                   penyajian_versi = NULL, renderer_versi = NULL,
                   asal_teks = NULL, status_visual = NULL,
                   mode_representasi = NULL, fingerprint_matematis = NULL,
                   fingerprint_penyajian = NULL
               WHERE id = ?""",
            (butir["sesi_soal_id"],),
        )

        berhasil, dicoba, _ = llm.bungkus_sesi(
            kon, sesi, teacher_pages._soal_dari_baris
        )
        sesudah = database.isi_sesi(kon, sesi)[0]
        snapshot = deserialisasi_penyajian(sesudah["penyajian_json"])
        teks_reader = teacher_pages._soal_dari_baris(sesudah).teks

    assert (berhasil, dicoba) == (1, 1)
    assert sesudah["cerita"] == cerita_bank_awal
    assert snapshot.teks_soal.startswith("Cerita warisan:")
    assert snapshot.asal_teks == "cerita"
    assert snapshot.status_visual == "warisan"
    assert snapshot.mode_representasi == "teks-v1"
    assert teks_reader == snapshot.teks_soal


def test_sesi_warisan_terkunci_tidak_diubah_oleh_cerita_sesi_lain(
    db, monkeypatch
):
    _palsu(monkeypatch, lambda s: "Cerita A: " + s.teks.replace(chr(10), " "))
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak")
        sesi_a = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        sesi_b = database.buat_sesi(kon, siswa, seed=42, jumlah_soal=1)
        butir_b = database.isi_sesi(kon, sesi_b)[0]
        kon.execute(
            "UPDATE sesi_soal SET "
            + ", ".join(
                f"{nama} = NULL"
                for nama in (
                    "teks_soal", "bagian_soal", "tantangan_soal",
                    "minta_restatement", "penyajian_json", "penyajian_versi",
                    "renderer_versi", "asal_teks", "status_visual",
                    "mode_representasi", "fingerprint_matematis",
                    "fingerprint_penyajian",
                )
            )
            + " WHERE id = ?",
            (butir_b["sesi_soal_id"],),
        )
        kon.execute(
            "UPDATE sesi SET mulai = '2026-09-06 10:00:00' WHERE id = ?",
            (sesi_b,),
        )
        terlihat_sebelum = teacher_pages._soal_dari_baris(
            database.isi_sesi(kon, sesi_b)[0]
        ).teks

        llm.bungkus_sesi(kon, sesi_a, teacher_pages._soal_dari_baris)
        baris_b = database.isi_sesi(kon, sesi_b)[0]
        terlihat_sesudah = teacher_pages._soal_dari_baris(baris_b).teks

    assert terlihat_sesudah == terlihat_sebelum
    assert baris_b["fingerprint_penyajian"] is None
