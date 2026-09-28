"""Bukti boundary foto existing; bukan klaim enforcement/replay telah terpasang.

Semua provider palsu dan DB/foto sintetis. Test karakterisasi ini sengaja tidak
memaksakan operasi baru ke kolom hasil_json atau nama berkas legacy.
"""
from contextlib import contextmanager
import json
import urllib.error

import pytest

import attachments
import database
import llm

JPEG = b"\xff\xd8\xff\xe0foto-sintetis"
HASIL = [{"nomor": 1, "jawaban": "12", "caraku": "contoh sintetis"}]


@pytest.fixture
def sesi(tmp_path, monkeypatch):
    path = tmp_path / "belajar.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(tmp_path / "foto"))
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, "Profil Sintetis", pemilik="guru-sintetis")
        sesi_id = database.buat_sesi(kon, sid, seed=17, jumlah_soal=1)
    return path, sesi_id


def multipart():
    boundary = "----FotoSintetisBoundary"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="foto"; '
            'filename="uji.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()
    return "multipart/form-data; boundary=" + boundary, body + JPEG + f"\r\n--{boundary}--\r\n".encode()


@pytest.mark.parametrize("murid", [False, True])
def test_provider_foto_fresh_tanpa_transaksi_tapi_return_belum_commit(sesi, monkeypatch, murid):
    path, sesi_id = sesi
    content_type, tubuh = multipart()
    panggilan = []
    with database.buka(path) as kon:
        def provider(konteks, gambar):
            panggilan.append(kon.in_transaction)
            return HASIL
        monkeypatch.setattr(llm, "ekstrak_lembar", provider)
        fungsi = attachments.proses_upload_murid if murid else attachments.proses_upload
        lid, pesan = fungsi(kon, sesi_id, content_type, tubuh)
        assert lid and pesan and panggilan == [False]
        assert kon.in_transaction
        # Menandai quota completed saat fungsi kembali masih mendahului commit.
        with database.buka(path) as pembaca:
            assert database.ambil_lampiran(pembaca, lid) is None
    with database.buka(path) as pembaca:
        assert database.ambil_lampiran(pembaca, lid) is not None


def test_retry_upload_existing_tidak_punya_receipt_operation_durable(sesi, monkeypatch):
    path, sesi_id = sesi
    panggilan = []
    monkeypatch.setattr(llm, "ekstrak_lembar", lambda *a: panggilan.append(1) or HASIL)
    content_type, tubuh = multipart()
    ids = []
    for _ in range(2):
        with database.buka(path) as kon:
            lid, _ = attachments.proses_upload(kon, sesi_id, content_type, tubuh)
            ids.append(lid)
    assert len(panggilan) == 2 and len(set(ids)) == 2
    with database.buka(path) as kon:
        assert len(database.daftar_lampiran(kon, sesi_id)) == 2
        kolom = {r[1] for r in kon.execute("PRAGMA table_info(lampiran)")}
        assert kolom == {"id", "sesi_id", "nama_berkas", "mime", "hasil_json", "status", "dibuat"}


def test_hasil_bacaulang_sama_tidak_membedakan_percobaan_atau_memulihkan_crash(sesi, monkeypatch):
    path, sesi_id = sesi
    nama = attachments.simpan_berkas(sesi_id, "uji.jpg", JPEG)
    with database.buka(path) as kon:
        lid = database.simpan_lampiran(kon, sesi_id, nama,
                                      hasil_json=json.dumps({"soal": HASIL}, ensure_ascii=False))
        database.tandai_lampiran(kon, lid, "diterapkan")
    monkeypatch.setattr(llm, "ekstrak_lembar", lambda *a: HASIL)
    snapshots = []
    for _ in range(2):
        with database.buka(path) as kon:
            attachments.baca_ulang(kon, lid)
        with database.buka(path) as kon:
            snapshots.append(tuple(database.ambil_lampiran(kon, lid)))
    assert snapshots[0] == snapshots[1]
    # Receipt operasi A dan B tidak dapat disimpulkan dari row identik ini.
    with database.buka(path) as kon:
        assert database.ambil_lampiran(kon, lid)["status"] == "diterapkan"


def test_rollback_setelah_hasil_foto_tidak_meninggalkan_bukti_output_durable(sesi, monkeypatch):
    path, sesi_id = sesi
    monkeypatch.setattr(llm, "ekstrak_lembar", lambda *a: HASIL)
    content_type, tubuh = multipart()
    with pytest.raises(RuntimeError, match="crash sintetis"):
        with database.buka(path) as kon:
            lid, _ = attachments.proses_upload(kon, sesi_id, content_type, tubuh)
            assert lid
            raise RuntimeError("crash sintetis sebelum commit")
    with database.buka(path) as kon:
        assert database.daftar_lampiran(kon, sesi_id) == []


def test_kontrak_vision_none_menyatukan_preflight_timeout_dan_parse(monkeypatch):
    # Kontrak publik lama tidak cukup untuk memilih release vs unknown.
    monkeypatch.setattr(llm, "konfigurasi_vision", lambda: {
        "api_key": "", "model": "sintetis", "base_url": "https://example.invalid"})
    assert llm.ekstrak_lembar(["Soal sintetis"], "c2ludGV0aXM=") is None
    monkeypatch.setattr(llm, "konfigurasi_vision", lambda: {
        "api_key": "kunci-sintetis", "model": "sintetis", "base_url": "https://example.invalid"})
    @contextmanager
    def timeout(*args, **kwargs):
        raise urllib.error.URLError("timeout sintetis")
        yield
    monkeypatch.setattr(llm.ai_control, "panggil", lambda fitur, akun, fungsi: fungsi())
    monkeypatch.setattr(llm.urllib.request, "urlopen", timeout)
    assert llm.ekstrak_lembar(["Soal sintetis"], "c2ludGV0aXM=") is None
    monkeypatch.setattr(llm.ai_control, "panggil", lambda *a: "bukan JSON")
    assert llm.ekstrak_lembar(["Soal sintetis"], "c2ludGV0aXM=") is None
