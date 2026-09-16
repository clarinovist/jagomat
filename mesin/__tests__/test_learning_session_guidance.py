"""Regresi panduan peran pada halaman sesi belajar terpandu."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import share_links  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    with uji.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=812, level="P3", jumlah_soal=1)
        kon.execute(
            "UPDATE sesi SET tujuan = 'pemetaan', putaran_id = ? WHERE id = ?",
            (putaran_id, sesi_id),
        )
    yield uji, siswa_id, sesi_id
    uji.berhenti()


def _halaman(server, sesi_id):
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    return isi


def test_sesi_siap_mengarahkan_handoff_dengan_post_tanpa_efek_get(server):
    uji, _, sesi_id = server

    halaman = _halaman(uji, sesi_id)

    assert "Pemetaan · giliran orang tua/guru" in halaman
    assert "Sesi siap — berikut cara anak mengerjakan" in halaman
    form = re.search(
        rf'<form[^>]+method="post"[^>]+action="/sesi/{sesi_id}/bagikan"[^>]*>(.*?)</form>',
        halaman,
        re.S,
    )
    assert form and "Bagikan sesi ke anak" in form.group(1)
    assert halaman.count(f'action="/sesi/{sesi_id}/bagikan"') == 1
    assert '<details class="panduan-pratinjau-st">' in halaman
    assert "Pratinjau soal &amp; kunci untuk guru" in halaman
    with uji.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM tautan_sesi").fetchone()[0] == 0


def test_tautan_aktif_memperingatkan_rotasi_dengan_teks_persis(server):
    uji, _, sesi_id = server
    with uji.buka() as kon:
        share_links.buat(kon, sesi_id)

    halaman = _halaman(uji, sesi_id)

    assert "Buat tautan baru" in halaman
    assert (
        "Membuat tautan baru akan menonaktifkan tautan sebelumnya. Lanjutkan?"
        in halaman
    )


def test_sesi_mulai_menunggu_anak_dan_bagikan_ulang_sekunder(server):
    uji, _, sesi_id = server
    with uji.buka() as kon:
        kon.execute(
            "UPDATE sesi SET mulai = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )

    halaman = _halaman(uji, sesi_id)

    assert "Sedang dikerjakan · giliran anak" in halaman
    assert "Bagikan ulang ke anak" in halaman
    assert 'class="panduan-aksi-sekunder-st"' in halaman


def test_sesi_dibatalkan_tidak_bisa_dibagikan_atau_ditulis(server):
    uji, siswa_id, sesi_id = server
    with uji.buka() as kon:
        kon.execute(
            "UPDATE sesi SET dibatalkan = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )

    halaman = _halaman(uji, sesi_id)

    assert "Sesi dibatalkan. Riwayat tetap tersimpan dan hasilnya tidak aktif dalam rencana." in halaman
    assert "Riwayat pemetaan · tidak aktif" in halaman
    assert f'href="/anak/{siswa_id}"' in halaman
    assert f'action="/sesi/{sesi_id}/bagikan"' not in halaman
    assert f'action="/sesi/{sesi_id}"' not in halaman
    assert "Konfirmasi hasil" not in halaman


def test_sesi_putaran_ditutup_adalah_riwayat_dan_tidak_mengubah_rencana(server):
    uji, siswa_id, sesi_id = server
    with uji.buka() as kon:
        putaran_id = kon.execute(
            "SELECT putaran_id FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["putaran_id"]
        kon.execute(
            """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, jenis, data)
               VALUES (?, ?, ?, 'putaran_ditutup', '{}')""",
            (siswa_id, putaran_id, sesi_id),
        )

    halaman = _halaman(uji, sesi_id)

    assert "Riwayat pemetaan · tidak aktif" in halaman
    assert "Sesi ini tersimpan sebagai riwayat dan tidak mengubah rencana level aktif." in halaman
    assert f'action="/sesi/{sesi_id}/bagikan"' not in halaman


def test_sesi_beda_level_adalah_riwayat_tanpa_memblokir_latihan_manual(server):
    uji, siswa_id, sesi_id = server
    with uji.buka() as kon:
        kon.execute("UPDATE siswa SET tingkat = 'P4' WHERE id = ?", (siswa_id,))

    halaman = _halaman(uji, sesi_id)

    assert "Riwayat pemetaan · tidak aktif" in halaman
    assert "Sesi level lama ini tidak mengubah rencana level aktif." in halaman
    assert f'action="/sesi/{sesi_id}/bagikan"' not in halaman

    with uji.buka() as kon:
        kon.execute(
            "UPDATE sesi SET tujuan = 'bebas', putaran_id = NULL WHERE id = ?",
            (sesi_id,),
        )
    manual = _halaman(uji, sesi_id)
    assert "Latihan pilihan sendiri" in manual
    assert f'action="/sesi/{sesi_id}/bagikan"' in manual


def test_selesai_meminta_tinjau_lalu_satu_jalan_kembali_setelah_sah(server):
    uji, siswa_id, sesi_id = server
    with uji.buka() as kon:
        butir = database.isi_sesi(kon, sesi_id)[0]
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], butir["kunci"], "cara sintetis"
        )
        database.simpan_diagnosis(
            kon, jawaban_id, benar=True, kode_usulan=None, kode_final=None,
            alasan="jawaban benar",
        )
        database.tandai_selesai(kon, sesi_id)

    perlu_tinjau = _halaman(uji, sesi_id)
    assert "Tinjau jawaban, cara, dan pemahaman anak" in perlu_tinjau
    assert perlu_tinjau.count(">Konfirmasi hasil sesi</button>") == 1
    assert ">Simpan koreksi</button>" not in perlu_tinjau

    with uji.buka() as kon:
        database.konfirmasi_hasil(
            kon,
            sesi_id,
            guru="guru",
            cek_pemahaman={int(butir["sesi_soal_id"]): "bisa_menjelaskan"},
        )

    sah = _halaman(uji, sesi_id)
    assert "Hasil sudah dikonfirmasi" in sah
    assert "Lihat rencana berikutnya" not in sah
    assert sah.count('class="kartu-rencana-st"') == 1
    assert 'id="hasil-pemetaan"' in sah
    assert f'href="/anak/{siswa_id}"' in sah
    assert "Semua sesi Anak Sintetis" in sah
    detail_edit = re.search(
        r'<details class="panduan-edit-hasil-st">(.*?)</form></details>', sah, re.S
    )
    assert detail_edit and "open" not in detail_edit.group(0).split(">", 1)[0]
    assert "Koreksi hasil — perlu konfirmasi ulang bila diubah" in detail_edit.group(1)
    assert f'action="/sesi/{sesi_id}"' in detail_edit.group(1)
    assert ">Konfirmasi ulang hasil sesi</button>" in detail_edit.group(1)


def test_koreksi_setelah_konfirmasi_meminta_konfirmasi_ulang(server):
    uji, _, sesi_id = server
    with uji.buka() as kon:
        butir = database.isi_sesi(kon, sesi_id)[0]
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], butir["kunci"], "cara awal"
        )
        database.simpan_diagnosis(
            kon, jawaban_id, benar=True, kode_usulan=None, kode_final=None,
            alasan="jawaban benar",
        )
        database.tandai_selesai(kon, sesi_id)
        database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        database.simpan_diagnosis(
            kon, jawaban_id, benar=False, kode_usulan="H", kode_final="H",
            alasan="dikoreksi guru", manual=True,
        )

    halaman = _halaman(uji, sesi_id)

    assert "Koreksi berubah — konfirmasi ulang diperlukan" in halaman
    assert halaman.count(">Konfirmasi ulang hasil sesi</button>") == 1
    assert '<details class="panduan-edit-hasil-st">' not in halaman
    assert ">Simpan koreksi</button>" not in halaman
    assert 'hidden disabled aria-hidden="true"' in halaman


def test_sesi_dibatalkan_tetap_punya_backlink_saat_konfirmasi_tampak_aktif(server):
    uji, siswa_id, sesi_id = server
    with uji.buka() as kon:
        butir = database.isi_sesi(kon, sesi_id)[0]
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], butir["kunci"], "cara sintetis"
        )
        database.simpan_diagnosis(
            kon, jawaban_id, benar=True, kode_usulan=None, kode_final=None,
            alasan="jawaban benar",
        )
        database.tandai_selesai(kon, sesi_id)
        database.konfirmasi_hasil(kon, sesi_id, guru="guru")
        kon.execute(
            "UPDATE sesi SET dibatalkan = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )

    halaman = _halaman(uji, sesi_id)

    assert "Lihat rencana berikutnya" not in halaman
    assert halaman.count(f'href="/anak/{siswa_id}"') == 1
    assert "Semua sesi Anak Sintetis" in halaman


def test_sesi_manual_memakai_konteks_netral_bukan_klaim_pemetaan(server):
    uji, _, sesi_id = server
    with uji.buka() as kon:
        kon.execute(
            "UPDATE sesi SET tujuan = 'bebas', putaran_id = NULL WHERE id = ?",
            (sesi_id,),
        )

    halaman = _halaman(uji, sesi_id)

    assert "Latihan pilihan sendiri" in halaman
    assert "ikut pemetaan" not in halaman
