"""Regresi respons terpotong dan pemulihan Pendamping dengan data sintetis."""

import json
import re
import sqlite3
from pathlib import Path

import pytest

import ai_errors
import ai_policy
import ai_service
import ai_store
import assistant_browser
import assistant_client
import assistant_schema
import assistant_service
from test_assistant_browser import mulai
from test_assistant_errors import _transport
from test_assistant_inline_http import server, _origin


_PANGGIL_DEFAULT = assistant_service.panggil_provider_default


def test_transport_mematikan_thinking_tanpa_menaikkan_batas(monkeypatch):
    panggilan = _transport(monkeypatch)
    assistant_client.kirim(
        assistant_client.Konfigurasi("https://contoh.invalid", "sintetis", "deepseek-flash"), []
    )
    muatan = json.loads(panggilan[0].data)
    assert muatan.get("thinking") == {"type": "disabled"}
    assert muatan["max_tokens"] == ai_policy.profil("pendamping").max_output == 1200
    assert muatan["response_format"] == {"type": "json_object"}
    assert ai_policy.profil("pendamping").timeout == 25
    assert ai_policy.profil("pendamping").reservasi_micro_usd == 15000
    assert len(panggilan) == 1


def test_truncation_punya_penjelasan_tersendiri_bukan_json_rusak():
    pesan = ai_errors.pesan_pendamping("respons_terpotong")
    assert "terpotong" in pesan
    assert "tidak ditampilkan" in pesan
    assert pesan != ai_errors.pesan_pendamping("respons_json")


def _gagalkan(server, monkeypatch):
    token, data, _, _ = mulai(server)
    monkeypatch.setattr(assistant_service, "panggil_provider_default", _PANGGIL_DEFAULT)
    panggilan = _transport(monkeypatch, akhir="length")
    kode, isi, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token, headers=_origin(server),
        data={**data, "pesan": "Jelaskan contoh pola sintetis."},
    )
    assert kode == 409
    return token, data, isi, panggilan


def _jalur(server, data):
    return f'/anak/{server.ids_inline[0]}?bantuan=rencana&chat={data["chat"]}'


def test_length_json_valid_tetap_gagal_tanpa_simpanan_atau_retry(server, monkeypatch):
    token, data, isi, panggilan = _gagalkan(server, monkeypatch)
    assert "terpotong" in isi
    assert isi.count('class="pendamping-galat"') == 1
    assert isi.index('class="pendamping-galat"') > isi.index('class="pendamping-transkrip"')
    with assistant_schema.buka() as kon:
        for tabel in ("pesan", "memori", "usulan_latihan"):
            assert kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0] == 0
    with ai_store.buka(ai_service.path_store()) as kon:
        assert tuple(kon.execute("SELECT status,kategori,biaya,reservation FROM ledger").fetchone()) == (
            "tak_pasti", "respons_terpotong", None, 15000,
        )
    server.minta("/pendamping/inline/pesan", cookie=token, headers=_origin(server),
                 data={**data, "pesan": "Jelaskan contoh pola sintetis."})
    assert len(panggilan) == 1


def test_get_ulang_menampilkan_kategori_tanpa_network_atau_tulisan(server, monkeypatch):
    token, data, _, panggilan = _gagalkan(server, monkeypatch)
    paths = (ai_service.path_store(), assistant_schema.BAWAAN, server.db)
    sebelum = {p: Path(p).read_bytes() for p in paths}
    kode, isi, _ = server.minta(_jalur(server, data), cookie=token)
    assert kode == 200
    status = re.findall(r'<p class="pendamping-galat"[^>]*>(.*?)</p>', isi, re.S)
    assert len(status) == 1 and "terpotong" in status[0]
    assert sebelum == {p: Path(p).read_bytes() for p in paths}
    assert len(panggilan) == 1


def test_sukses_baru_menghapus_status_gagal_lama_pada_detik_yang_sama(server, monkeypatch):
    token, data, isi, _ = _gagalkan(server, monkeypatch)
    _transport(monkeypatch)
    baru = re.search(r'name="request_id" value="(req_[^"]+)"', isi).group(1)
    kode, isi, _ = server.minta(
        "/pendamping/inline/pesan", cookie=token, headers=_origin(server),
        data={**data, "request_id": baru, "pesan": "Bantu satu langkah lagi."},
    )
    assert kode == 200
    with assistant_schema.buka() as kon:
        kon.execute("UPDATE operasi SET dibuat=100 WHERE chat_id=?", (data["chat"],))
    kode, isi, _ = server.minta(_jalur(server, data), cookie=token)
    assert kode == 200
    assert 'class="pendamping-galat"' not in isi
    assert "Mari kita bahas" in isi


def _catat_ledger(*, akun="akun_sintetis", fitur="pendamping", status="tak_pasti", kategori="respons_terpotong"):
    with ai_store.buka(ai_service.path_store()) as kon:
        kon.execute(
            """INSERT INTO ledger(operasi_id,fitur,bucket_akun,revisi,model,status,
                   reservation,kategori,periode_hari,periode_bulan,dibuat)
               VALUES(?,?,?,1,'sintetis',?,15000,?,'2026-09-15','2026-09',1)""",
            ("pendamping:req_sintetis", fitur, akun, status, kategori),
        )


@pytest.mark.parametrize("ubah", [
    {"akun": "akun_lain"}, {"fitur": "cerita"}, {"status": "selesai"},
    {"kategori": "ISI_PRIVAT_SINTETIS"},
])
def test_kategori_tidak_dipinjam_dari_akun_fitur_status_atau_teks_asing(ubah):
    _catat_ledger(**ubah)
    assert ai_service.kategori_gagal_pendamping("akun_sintetis", "req_sintetis") == ""


def test_kategori_hanya_request_pemilik_yang_sesuai(monkeypatch):
    _catat_ledger()
    assert ai_service.kategori_gagal_pendamping("akun_sintetis", "req_lain") == ""
    sambung = sqlite3.connect
    koneksi = []
    def periksa(*args, **kwargs):
        assert args[0].endswith("?mode=ro") and kwargs["uri"] is True
        kon = sambung(*args, **kwargs)
        koneksi.append(kon)
        return kon
    monkeypatch.setattr(sqlite3, "connect", periksa)
    assert ai_service.kategori_gagal_pendamping("akun_sintetis", "req_sintetis") == "respons_terpotong"
    with pytest.raises(sqlite3.ProgrammingError):
        koneksi[0].execute("SELECT 1")


@pytest.mark.parametrize("jenis", ["hilang", "rusak", "tanpa_tabel"])
def test_metadata_tidak_tersedia_tidak_membuat_db_dan_fallback(tmp_path, monkeypatch, jenis):
    path = tmp_path / "metadata.db"
    if jenis == "rusak":
        path.write_bytes(b"bukan sqlite")
    elif jenis == "tanpa_tabel":
        sqlite3.connect(path).close()
    sebelum = path.read_bytes() if path.exists() else None
    monkeypatch.setenv("AI_BERKAS_DB", str(path))
    assert ai_service.kategori_gagal_pendamping("akun_sintetis", "req_sintetis") == ""
    assert (path.read_bytes() if path.exists() else None) == sebelum


@pytest.mark.parametrize("rusak", ["akun", "kategori", "hilang"])
def test_get_metadata_asing_atau_hilang_tetap_pesan_generik(server, monkeypatch, rusak):
    token, data, _, panggilan = _gagalkan(server, monkeypatch)
    with ai_store.buka(ai_service.path_store()) as kon:
        if rusak == "akun":
            kon.execute("UPDATE ledger SET bucket_akun='akun_asing'")
        elif rusak == "kategori":
            kon.execute("UPDATE ledger SET kategori='ISI_PRIVAT_SINTETIS'")
        else:
            kon.execute("DELETE FROM ledger")
    kode, isi, _ = server.minta(_jalur(server, data), cookie=token)
    assert kode == 200
    status = re.findall(r'<p class="pendamping-galat"[^>]*>(.*?)</p>', isi, re.S)
    assert len(status) == 1 and "Jawaban sebelumnya belum tersedia" in status[0]
    assert "ISI_PRIVAT_SINTETIS" not in isi
    assert len(panggilan) == 1


def test_status_setelah_length_tidak_memanggil_provider_lagi(server, monkeypatch):
    token, data, _, panggilan = _gagalkan(server, monkeypatch)
    kode, isi, _ = server.minta("/pendamping/inline/status", cookie=token,
                               data=data, headers=_origin(server))
    assert kode == 200
    status = re.findall(r'<p class="pendamping-galat"[^>]*>(.*?)</p>', isi, re.S)
    assert len(status) == 1 and "terpotong" in status[0]
    assert len(panggilan) == 1


def test_asing_dan_hilang_tidak_membaca_metadata_gagal(server, monkeypatch):
    token, data, _, _ = _gagalkan(server, monkeypatch)
    def dilarang(*_):
        pytest.fail("Metadata AI dibaca sebelum palang resource")
    monkeypatch.setattr(ai_service, "kategori_gagal_pendamping", dilarang)
    hasil = [server.minta(f'/anak/{anak}?bantuan=rencana&chat={data["chat"]}', cookie=token)
             for anak in (server.ids_inline[2], 999999)]
    assert hasil[0][:2] == hasil[1][:2] and hasil[0][0] == 404


@pytest.mark.parametrize("kondisi", ["stale", "dicabut"])
def test_konteks_tidak_aktif_tidak_membaca_kategori_ledger(server, monkeypatch, kondisi):
    token, data, _, panggilan = _gagalkan(server, monkeypatch)
    if kondisi == "stale":
        with server.buka() as kon:
            kon.execute("UPDATE siswa SET tingkat='P4' WHERE id=?", (server.ids_inline[0],))
    else:
        with assistant_schema.buka() as kon:
            kon.execute("UPDATE persetujuan_konteks SET dicabut=1")
    def dilarang(*_):
        pytest.fail("Metadata AI dibaca untuk konteks tidak aktif")
    monkeypatch.setattr(ai_service, "kategori_gagal_pendamping", dilarang)
    kode, isi, _ = server.minta(_jalur(server, data), cookie=token)
    if kondisi == "stale":
        assert kode == 200 and "hanya dapat dibaca" in isi
    else:
        assert kode == 404
    assert len(panggilan) == 1


def test_browser_tidak_mengklaim_pesan_belum_sampai_server():
    assert "Pesan belum terkirim" not in assistant_browser.SKRIP_CHAT
    assert "Balasan belum tersedia" in assistant_browser.SKRIP_CHAT
    assert "tidak dikirim ulang otomatis" in assistant_browser.SKRIP_CHAT
