"""Mode "tandai benar" pada halaman isi jawaban dari lembar (blok A, 5 Nov 2026).

Guru mencentang "jawaban anak benar" alih-alih mengetik; jawaban tersimpan
sebagai kunci (bentuk kanonis), diagnosis manual benar, dan asal jawaban
``ditandai_benar`` tercatat di tinjauan. Butir salah tetap diketik persis.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import attachments  # noqa: E402
import database  # noqa: E402
import llm  # noqa: E402
import review_store  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _lampiran(kon, pemilik="", **sesi):
    sid = database.tambah_siswa(kon, "AnakTandai", pemilik=pemilik)
    sesi_id = database.buat_sesi(kon, sid, seed=7, **sesi)
    return sesi_id, database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")


def _butir(kon, sesi_id):
    return database.isi_sesi(kon, sesi_id)


def _data_semua_benar_kecuali(butir, salah):
    data = {}
    for b in butir:
        sid = b["sesi_soal_id"]
        data[f"jwb_{sid}"] = ""
        data[f"cara_{sid}"] = ""
        if sid in salah:
            data[f"jwb_{sid}"] = salah[sid]
        else:
            data[f"benar_{sid}"] = "1"
    return data


def test_mode_manual_menampilkan_centang_benar_per_soal_isian(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    for b in butir:
        assert f'name="benar_{b["sesi_soal_id"]}"' in html
        assert f'value="{b["kunci"]}"' not in html  # kolom jawaban tetap kosong
    assert 'class="kunci"' not in html
    assert "Jawaban anak benar" in html


def test_pg_tidak_menampilkan_centang_benar(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon, jumlah_soal=2, format_jawaban="pilihan_ganda")
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    assert 'name="benar_' not in html


def test_terapkan_centang_benar_menyimpan_kunci_manual_dan_provenance(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        sid_salah = butir[0]["sesi_soal_id"]
        data = _data_semua_benar_kecuali(butir, {sid_salah: "tidak"})
        jumlah, _pesan = attachments.terapkan(kon, lid, data)
        kon.commit()
        sesudah = {b["sesi_soal_id"]: b for b in _butir(kon, sesi_id)}
        selesai = kon.execute("SELECT selesai FROM sesi WHERE id=?", (sesi_id,)).fetchone()[0]
        arsip = kon.execute("SELECT sumber FROM pengiriman_sesi WHERE sesi_id=?", (sesi_id,)).fetchone()
    assert jumlah == len(butir)
    for sid, b in sesudah.items():
        if sid == sid_salah:
            assert b["jawaban"] == "tidak" and not b["benar"]
            assert not review_store.ditandai_benar(b)
            continue
        assert b["jawaban"] == b["kunci"]
        assert b["benar"] == 1 and b["manual"] == 1 and b["kode_final"] is None
        assert review_store.ditandai_benar(b)
    assert selesai and arsip["sumber"] == "foto"


def test_terapkan_centang_benar_teks_beda_ditolak_tanpa_efek(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        sid = butir[0]["sesi_soal_id"]
        kon.commit()  # lampiran tersimpan; rollback di bawah hanya membatalkan terapkan
        data = _data_semua_benar_kecuali(butir, {})
        data[f"jwb_{sid}"] = "tidak"  # dicentang benar tetapi teks berbeda
        with pytest.raises(ValueError):
            attachments.terapkan(kon, lid, data)
        kon.rollback()
        n_jawaban = kon.execute(
            "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=?",
            (sesi_id,)).fetchone()[0]
        status = database.ambil_lampiran(kon, lid)["status"]
    assert n_jawaban == 0 and status == "baru"


def _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban):
    """Guru mencentang benar sebagian (sesi belum selesai), lalu anak melanjutkan dari HP."""
    import reports
    import student_submissions
    sesi_id, lid = _lampiran(kon)
    butir = _butir(kon, sesi_id)
    sid_centang, sid_kosong = butir[0]["sesi_soal_id"], butir[-1]["sesi_soal_id"]
    data = _data_semua_benar_kecuali(butir, {})
    del data[f"benar_{sid_kosong}"]  # satu soal belum terisi: sesi belum selesai
    attachments.terapkan(kon, lid, data)
    assert not kon.execute("SELECT selesai FROM sesi WHERE id=?", (sesi_id,)).fetchone()[0]
    if ubah_jawaban:
        database.simpan_jawaban(kon, sid_centang, "tidak", "cara anak", "", False)
    kunci_kosong = butir[-1]["kunci"]
    database.simpan_jawaban(kon, sid_kosong, kunci_kosong, "cara anak", "", False)
    reports.diagnosa_murid(kon, sesi_id)
    student_submissions.arsipkan(kon, sesi_id, "akun")
    database.tandai_selesai(kon, sesi_id)
    kon.commit()
    return sesi_id, sid_centang


def test_validasi_bukti_lolos_bila_jawaban_tercentang_tetap_kunci(db):
    with database.buka(db) as kon:
        sesi_id, sid = _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban=False)
        outcome = _butir(kon, sesi_id)
        review_store.validasi_bukti(kon, sesi_id, outcome, set())


def test_validasi_bukti_menolak_centang_benar_yang_jawabannya_diubah_anak(db):
    """Arsip memuat jawaban baru anak, jadi aturan arsip diam; palang penanda yang menangkap."""
    with database.buka(db) as kon:
        sesi_id, sid = _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban=True)
        outcome = _butir(kon, sesi_id)
        b = {x["sesi_soal_id"]: x for x in outcome}[sid]
        assert review_store.ditandai_benar(b) and b["jawaban"] == "tidak"
        with pytest.raises(review_store.TinjauanTidakSah, match="berubah setelah ditandai benar"):
            review_store.validasi_bukti(kon, sesi_id, outcome, set())


def test_arsip_menolak_ubah_jawaban_butir_ditandai_benar_tanpa_koreksi_salinan(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        attachments.terapkan(kon, lid, _data_semua_benar_kecuali(butir, {}))
        kon.commit()
        sid = butir[0]["sesi_soal_id"]
        with pytest.raises(review_store.TinjauanTidakSah):
            review_store.simpan(kon, sesi_id, {f"jwb_{sid}": "tidak"})


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _buat_lampiran_http(server, tmp_path, monkeypatch):
    akar = tmp_path / "lampiran-http"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    monkeypatch.setattr(llm, "konfigurasi_vision", lambda: {"base_url": "", "api_key": "", "model": ""})
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakHttpTandai", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        return sesi_id, database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")


def test_http_terapkan_payload_browser_lengkap_dengan_centang(server, tmp_path, monkeypatch):
    sesi_id, lid = _buat_lampiran_http(server, tmp_path, monkeypatch)
    with server.buka() as kon:
        butir = _butir(kon, sesi_id)
    # Browser mengirim semua kolom teks walau kosong: 15 jwb + 15 cara + centang.
    data = _data_semua_benar_kecuali(butir, {})
    kode, isi, _ = server.minta(f"/lampiran/{lid}/terapkan", auth=("guru", SANDI_GURU), data=data)
    assert kode == 200
    with server.buka() as kon:
        benar = kon.execute(
            "SELECT COUNT(*) FROM diagnosis d JOIN jawaban j ON j.id=d.jawaban_id "
            "JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=? AND d.benar=1 AND d.manual=1",
            (sesi_id,)).fetchone()[0]
        html = server.minta(f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU))[1]
    assert benar == len(butir)
    assert "Ditandai benar dari lembar oleh guru" in html


def test_http_terapkan_centang_dan_teks_beda_400_tanpa_efek(server, tmp_path, monkeypatch):
    sesi_id, lid = _buat_lampiran_http(server, tmp_path, monkeypatch)
    with server.buka() as kon:
        butir = _butir(kon, sesi_id)
    data = _data_semua_benar_kecuali(butir, {})
    data[f"jwb_{butir[0]['sesi_soal_id']}"] = "tidak"
    kode, isi, _ = server.minta(f"/lampiran/{lid}/terapkan", auth=("guru", SANDI_GURU), data=data)
    assert kode == 400
    assert "berbeda" in isi
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id WHERE ss.sesi_id=?",
            (sesi_id,)).fetchone()[0]
    assert n == 0


def test_terapkan_ulang_tanpa_centang_melepas_keputusan_benar_lama(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        sid = butir[0]["sesi_soal_id"]
        attachments.terapkan(kon, lid, _data_semua_benar_kecuali(butir, {}))
        kon.commit()
        # Guru sadar soal pertama sebenarnya salah: terapkan ulang tanpa centang,
        # dengan jawaban yang anak tulis. Arsip sudah ada, jadi jalur koreksi
        # resmi adalah tinjauan; terapkan ulang hanya boleh menilai ulang butir
        # yang belum terkunci arsip. Di sini kita pastikan penanda tidak bertahan
        # senyap pada butir yang centangnya dicabut.
        data = _data_semua_benar_kecuali(butir, {sid: "tidak"})
        attachments.terapkan(kon, lid, data)
        kon.commit()
        b = {x["sesi_soal_id"]: x for x in _butir(kon, sesi_id)}[sid]
    assert b["jawaban"] == "tidak"
    assert not review_store.ditandai_benar(b)
    assert not b["benar"]


def test_halaman_mengisi_ulang_centang_untuk_butir_yang_sudah_ditandai(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        butir = _butir(kon, sesi_id)
        sid_salah = butir[0]["sesi_soal_id"]
        attachments.terapkan(kon, lid, _data_semua_benar_kecuali(butir, {sid_salah: "tidak"}))
        kon.commit()
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    assert f'name="benar_{sid_salah}">' in html  # tidak tercentang
    for b in butir[1:]:
        assert f'name="benar_{b["sesi_soal_id"]}" checked>' in html


def test_konfirmasi_sungguhan_lolos_bila_centang_tetap_kunci(db):
    """Jalur yang dipakai produksi: database.konfirmasi_hasil -> muat_outcome=isi_sesi."""
    with database.buka(db) as kon:
        sesi_id, _sid = _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban=False)
        konfirmasi_id = database.konfirmasi_hasil(kon, sesi_id, "guru", dilewati=set())
        kon.commit()
    assert konfirmasi_id


def test_konfirmasi_sungguhan_menolak_centang_yang_jawabannya_diubah_anak(db):
    with database.buka(db) as kon:
        sesi_id, _sid = _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban=True)
        with pytest.raises(review_store.TinjauanTidakSah, match="berubah setelah ditandai benar"):
            database.konfirmasi_hasil(kon, sesi_id, "guru", dilewati=set())
        kon.rollback()
        n = kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id=?", (sesi_id,)).fetchone()[0]
    assert n == 0


def test_validasi_bukti_menolak_baris_tanpa_kolom_penanda(db):
    with database.buka(db) as kon:
        sesi_id, _sid = _centang_sebagian_lalu_anak_lanjut(kon, ubah_jawaban=False)
        outcome = [{k: b[k] for k in b.keys() if k != "catatan"} for b in _butir(kon, sesi_id)]
        with pytest.raises(ValueError, match="tidak lengkap"):
            review_store.validasi_bukti(kon, sesi_id, outcome, set())
