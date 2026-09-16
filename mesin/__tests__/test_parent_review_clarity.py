"""Status profil orang tua jujur tentang tinjauan dan konfirmasi hasil."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
import review_store
import teacher_pages


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "profil.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    return jalur


def _render(kon, siswa_id):
    siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    return teacher_pages.halaman_anak(kon, siswa, privat=True).decode()


@pytest.mark.parametrize("keadaan, label", [
    ("baru", "Belum Dikerjakan"),
    ("dibuka_belum_kirim", "Belum Dikerjakan"),
    ("sebagian_dibuka", "Sedang Dikerjakan"),
    ("terkirim", "Belum ditinjau"),
    ("dibuka", "Sudah dibuka · belum dikonfirmasi"),
    ("draf", "Draf tinjauan tersimpan · belum dikonfirmasi"),
    ("dikonfirmasi", "✓ Hasil dikonfirmasi"),
    ("dikonfirmasi_ulang", "✓ Hasil dikonfirmasi"),
    ("snapshot_lama", "Perlu konfirmasi ulang"),
    ("diinvalidasi", "Perlu konfirmasi ulang"),
    ("fingerprint_berbeda", "Perlu konfirmasi ulang"),
    ("stamp_tanpa_snapshot", "Sudah dibuka · belum dikonfirmasi"),
    ("snapshot_tanpa_stamp", "Perlu konfirmasi ulang"),
    ("batal_terkonfirmasi", "Dibatalkan"),
])
def test_badge_profil_mengikuti_status_hasil_bukan_sekadar_dibuka(db, keadaan, label):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Status Sintetis", "P3", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=781, level="P3", jumlah_soal=1)
        butir_id = database.isi_sesi(kon, sesi_id)[0]["sesi_soal_id"]
        if keadaan not in {"baru", "dibuka_belum_kirim", "sebagian_dibuka"}:
            database.tandai_selesai(kon, sesi_id)
        if keadaan not in {"baru", "terkirim"}:
            kon.execute("UPDATE sesi SET direview = '2026-09-15 10:00:00' WHERE id = ?", (sesi_id,))
        if keadaan == "sebagian_dibuka":
            database.simpan_jawaban(kon, butir_id, "7")
        if keadaan == "draf":
            review_store.simpan(kon, sesi_id, {f"catatan_tinjauan_{butir_id}": "Tanyakan cara anak."})
        if keadaan in {"dikonfirmasi", "dikonfirmasi_ulang", "snapshot_lama", "diinvalidasi", "fingerprint_berbeda", "snapshot_tanpa_stamp", "batal_terkonfirmasi"}:
            database.konfirmasi_hasil(kon, sesi_id, guru="guru", dilewati={butir_id})
        if keadaan in {"diinvalidasi", "dikonfirmasi_ulang", "snapshot_lama"}:
            review_store.simpan(kon, sesi_id, {f"catatan_tinjauan_{butir_id}": "Perlu diperiksa lagi."})
        if keadaan in {"dikonfirmasi_ulang", "snapshot_lama"}:
            database.konfirmasi_hasil(kon, sesi_id, guru="guru", dilewati={butir_id})
        if keadaan == "snapshot_lama":
            kon.execute("""UPDATE sesi SET fingerprint_konfirmasi = (
                SELECT fingerprint FROM konfirmasi_hasil WHERE sesi_id = ?
                ORDER BY nomor_urut, id LIMIT 1) WHERE id = ?""", (sesi_id, sesi_id))
        if keadaan == "fingerprint_berbeda":
            kon.execute("UPDATE sesi SET fingerprint_konfirmasi = 'berbeda' WHERE id = ?", (sesi_id,))
        if keadaan == "snapshot_tanpa_stamp":
            kon.execute("UPDATE sesi SET dikonfirmasi_guru = NULL WHERE id = ?", (sesi_id,))
        if keadaan == "stamp_tanpa_snapshot":
            kon.execute("UPDATE sesi SET dikonfirmasi_guru = '2026-09-15', fingerprint_konfirmasi = 'tanpa-snapshot' WHERE id = ?", (sesi_id,))
        if keadaan == "batal_terkonfirmasi":
            database.batalkan_sesi(kon, sesi_id, "Pembatalan sintetis")
        sebelum = tuple(kon.iterdump())

        isi = _render(kon, siswa_id)

        assert tuple(kon.iterdump()) == sebelum
        kartu = re.search(r'<article class="st-kartu-baris kartu-sesi-guru .*?</article>', isi, re.S).group()
        badge = re.search(r'<span class="badge-direview [^"]*"[^>]*>(.*?)</span>', kartu, re.S).group(1)
        assert badge == label
        assert "Sudah Direview" not in kartu
        assert ("✓" in badge) == (keadaan in {"dikonfirmasi", "dikonfirmasi_ulang"})
        assert "masuk pemetaan" not in kartu


def test_kartu_menyebut_sesi_rekomendasi_bukan_riwayat_terbaru(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Rencana Sintetis", "P3", pemilik="guru")
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        terpandu = database.buat_sesi(kon, siswa_id, seed=782, level="P3", jumlah_soal=1)
        kon.execute("""UPDATE sesi SET tujuan = 'pemetaan', putaran_id = ?,
            tanggal = '2026-09-12', selesai = '2026-09-12 10:00:00' WHERE id = ?""", (putaran_id, terpandu))
        manual = database.buat_sesi(kon, siswa_id, seed=783, level="P3", jumlah_soal=1)
        kon.execute("UPDATE sesi SET tanggal = '2026-09-15' WHERE id = ?", (manual,))
        sebelum = tuple(kon.iterdump())

        isi = _render(kon, siswa_id)

        assert tuple(kon.iterdump()) == sebelum
        kartu = re.search(r'<section class="kartu-rencana-st".*?</section>', isi, re.S).group()
        assert f'Sesi #{terpandu} · <time datetime="2026-09-12">12 September 2026</time>' in kartu
        assert f'Sesi #{manual}' not in kartu
        assert '15 September 2026' not in kartu
        assert f'href="/sesi/{terpandu}">Tinjau hasil</a>' in kartu
        assert kartu.count('class="rencana-cta-utama-st"') == 1
        assert 'Hasil belum dikonfirmasi.' in kartu
        assert 'Hasil sesi belum dikonfirmasi guru' not in kartu
        assert 'Bagaimana kamu mendapat jawaban ini?' in kartu
        assert 'tanpa memberi jawaban' in kartu
        assert 'Simpan draf' in kartu
        assert 'Konfirmasi hanya setelah hasil diperiksa.' in kartu


def test_kartu_tanpa_sesi_bukti_tidak_mengarang_tanggal():
    from learning_cycle import BuktiSiklus, RencanaBelajar
    from learning_cycle_ui import render_rencana

    isi = render_rencana(RencanaBelajar("konfirmasi_hasil", "uji", sesi_id=71), BuktiSiklus(9, "P3"), 9)
    assert '<time' not in isi
    assert 'class="identitas-sesi-rencana-st"' not in isi


def test_gaya_badge_profil_membedakan_konfirmasi_dan_membungkus_teks():
    from style_stitch import GAYA_STITCH
    import design_tokens as T

    blok = GAYA_STITCH.split('.profil-editorial-st .badge-direview {', 1)[1].split('}', 1)[0]
    assert 'white-space: normal' in blok
    assert 'overflow-wrap: anywhere' in blok
    sukses = GAYA_STITCH.split('.profil-editorial-st .badge-direview.sudah {', 1)[1].split('}', 1)[0]
    belum = GAYA_STITCH.split('.profil-editorial-st .badge-direview.perlu {', 1)[1].split('}', 1)[0]
    assert f'background: {T.AKSEN_TEAL_TUA}' in sukses
    assert f'color: {T.TEKS_PUTIH}' in sukses
    assert f'background: {T.LATAR_CATATAN}' in belum
