"""Regresi balasan Pendamping: metadata aman, ledger, dan gagal tanpa efek samping."""

import io
import json
import logging
import socket
import urllib.error
from contextlib import closing

import pytest

import ai_errors
import ai_service
import ai_store
import assistant_client
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
from test_assistant_runtime import AKUN, ProviderPalsu, _kon
from test_assistant_inline_http import server, _origin
from test_assistant_browser import mulai


_PANGGIL_DEFAULT = assistant_service.panggil_provider_default


RAHASIA = "RAHASIA_SINTETIS_JANGAN_DICATAT"


def _respons(**ganti):
    return {**ProviderPalsu().respons, **ganti}


def _transport(monkeypatch, *, konten=None, mentah=None, galat=None, akhir="stop"):
    panggilan = []

    class Respons:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _batas):
            if galat:
                raise galat
            if mentah is not None:
                return mentah
            return json.dumps({"choices": [{
                "finish_reason": akhir,
                "message": {"content": konten if konten is not None else json.dumps(_respons())},
            }]}).encode()

    class Pembuka:
        def open(self, req, timeout):
            panggilan.append(req)
            if isinstance(galat, urllib.error.HTTPError):
                raise galat
            return Respons()

    monkeypatch.setattr(assistant_client.urllib.request, "build_opener", lambda *_: Pembuka())
    return panggilan


def _chat(kon):
    assistant_store.beri_persetujuan(
        kon, AKUN, kategori="chat_umum", policy_version=assistant_policy.VERSI_KEBIJAKAN,
        provider_id=assistant_policy.PROVIDER_ID, sekarang=1,
    )
    chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=1)
    kon.commit()
    return chat


def _siapkan_default(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("AI_NONAKTIF", "0")


@pytest.mark.parametrize("ganti,kategori", [
    ({"asing": RAHASIA}, "respons_bentuk"),
    ({"jawaban": "<b>" + RAHASIA + "</b>"}, "respons_jawaban"),
    ({"draft_memori": {"lingkup": "preferensi_orang_tua", "isi": RAHASIA}}, "respons_memori"),
    ({"usulan_latihan": {"asing": RAHASIA}}, "respons_usulan"),
    ({"butuh_klarifikasi": RAHASIA}, "respons_klarifikasi"),
])
def test_respons_invalid_tidak_dicatat_sukses_atau_disimpan(monkeypatch, tmp_path, caplog, ganti, kategori):
    _siapkan_default(monkeypatch)
    panggilan = _transport(monkeypatch, konten=json.dumps(_respons(**ganti)))
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        with caplog.at_level(logging.WARNING, logger="assistant_service"):
            with pytest.raises(assistant_service.GalatPendamping) as gagal:
                assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_invalid")
        with ai_store.buka(ai_service.path_store()) as ai:
            baris = ai.execute("SELECT status,kategori,biaya,reservation FROM ledger WHERE operasi_id='pendamping:req_invalid'").fetchone()
        assert baris[0] == "tak_pasti"
        assert baris[1] == kategori
        assert baris[2] is None and baris[3] == 15000
        assert kategori in caplog.text and RAHASIA not in caplog.text
        assert "Teks sintetis." not in caplog.text and AKUN not in caplog.text
        assert "kunci-sintetis" not in caplog.text
        assert all(r.exc_info is None for r in caplog.records)
        assert "format balasan" in str(gagal.value).lower()
        assert RAHASIA not in str(gagal.value)
        for tabel in ("pesan", "memori", "usulan_latihan"):
            assert kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0] == 0
        assert kon.execute("SELECT status FROM operasi").fetchone()[0] == "gagal"
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_invalid")
    assert len(panggilan) == 1


@pytest.mark.parametrize("galat,kategori,pesan_ui", [
    (socket.timeout(RAHASIA), "provider_timeout", "terlalu lama"),
    (urllib.error.URLError(RAHASIA), "provider_koneksi", "Coba lagi nanti"),
])
def test_transport_gagal_masuk_ledger_dan_log_aman(monkeypatch, tmp_path, caplog, galat, kategori, pesan_ui):
    _siapkan_default(monkeypatch)
    panggilan = _transport(monkeypatch, galat=galat)
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        with caplog.at_level(logging.WARNING, logger="assistant_service"):
            with pytest.raises(assistant_service.GalatPendamping) as gagal:
                assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_transport")
        assert pesan_ui in str(gagal.value)
        assert kategori in caplog.text and RAHASIA not in caplog.text
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
    with ai_store.buka(ai_service.path_store()) as ai:
        baris = ai.execute("SELECT status,kategori,biaya,reservation FROM ledger").fetchone()
        assert tuple(baris) == ("tak_pasti", kategori, None, 15000)
    assert len(panggilan) == 1


@pytest.mark.parametrize("kode,kategori", [
    (302, "provider_redirect"), (401, "provider_otorisasi"),
    (403, "provider_otorisasi"), (429, "provider_batas"), (500, "provider_gagal"),
])
def test_kategori_http_tanpa_body_atau_url(monkeypatch, kode, kategori):
    galat = urllib.error.HTTPError("https://contoh.invalid/" + RAHASIA, kode, RAHASIA, {}, io.BytesIO(RAHASIA.encode()))
    _transport(monkeypatch, galat=galat)
    with pytest.raises(assistant_client.GalatProvider) as gagal:
        assistant_client.kirim(assistant_client.Konfigurasi("https://contoh.invalid", "kunci", "model"), [])
    assert getattr(gagal.value, "kategori", None) == kategori
    assert RAHASIA not in str(gagal.value)
    assert galat.fp.closed


@pytest.mark.parametrize("galat,kategori", [
    (socket.timeout(RAHASIA), "provider_timeout"),
    (urllib.error.URLError(socket.timeout(RAHASIA)), "provider_timeout"),
    (urllib.error.URLError(RAHASIA), "provider_koneksi"),
    (OSError(RAHASIA), "provider_koneksi"),
])
def test_transport_dibedakan_tanpa_exception_mentah(monkeypatch, galat, kategori):
    _transport(monkeypatch, galat=galat)
    with pytest.raises(assistant_client.GalatProvider) as gagal:
        assistant_client.kirim(assistant_client.Konfigurasi("https://contoh.invalid", "kunci", "model"), [])
    assert getattr(gagal.value, "kategori", None) == kategori
    assert RAHASIA not in str(gagal.value)


@pytest.mark.parametrize("pilihan,kategori", [
    ({"akhir": "length"}, "respons_terpotong"),
    ({"konten": "bukan JSON " + RAHASIA}, "respons_json"),
    ({"mentah": b'not json'}, "respons_json"),
    ({"mentah": b'{}'}, "respons_json"),
])
def test_json_dan_truncation_fail_closed(monkeypatch, pilihan, kategori):
    _transport(monkeypatch, **pilihan)
    with pytest.raises(assistant_client.GalatProvider) as gagal:
        assistant_client.kirim(assistant_client.Konfigurasi("https://contoh.invalid", "kunci", "model"), [])
    assert getattr(gagal.value, "kategori", None) == kategori
    assert RAHASIA not in str(gagal.value)


def test_sukses_dan_replay_tetap_satu_provider(monkeypatch, tmp_path):
    _siapkan_default(monkeypatch)
    panggilan = _transport(monkeypatch)
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        for _ in range(2):
            assert assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_sukses") == _respons()["jawaban"]
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 2
        assert kon.execute("SELECT status FROM operasi").fetchone()[0] == "selesai"
    with ai_store.buka(ai_service.path_store()) as ai:
        baris = ai.execute("SELECT status,kategori FROM ledger WHERE operasi_id='pendamping:req_sukses'").fetchone()
        assert tuple(baris) == ("selesai", "terukur_konservatif")
    assert len(panggilan) == 1


def test_exception_asing_tidak_bocor_ke_log_ledger_ui(monkeypatch, tmp_path, caplog):
    _siapkan_default(monkeypatch)
    galat = ValueError(RAHASIA)
    galat.kategori = RAHASIA
    def gagal(*_):
        raise galat
    monkeypatch.setattr(assistant_client, "kirim", gagal)
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        with caplog.at_level(logging.WARNING, logger="assistant_service"):
            with pytest.raises(assistant_service.GalatPendamping) as hasil:
                assistant_service.kirim_pesan(kon, AKUN, chat.id, "Pesan sintetis.", request_id="req_asing")
    assert caplog.records
    assert RAHASIA not in caplog.text + str(hasil.value)
    assert all(r.exc_info is None for r in caplog.records)
    with ai_store.buka(ai_service.path_store()) as ai:
        baris = ai.execute("SELECT kategori FROM ledger WHERE operasi_id='pendamping:req_asing'").fetchone()
        assert baris[0] == "network_atau_provider"


def test_admission_ditahan_tidak_network_dan_ui_jelas(monkeypatch, tmp_path, caplog):
    _siapkan_default(monkeypatch)
    panggilan = _transport(monkeypatch)
    with ai_store.buka(ai_service.path_store()) as ai:
        ai.execute("UPDATE konfigurasi SET request_akun_harian=0")
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        with caplog.at_level(logging.WARNING, logger="assistant_service"):
            with pytest.raises(assistant_service.GalatPendamping) as gagal:
                assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_kuota")
        assert "batas pemakaian" in str(gagal.value)
        assert "ai_kuota" in caplog.text
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
    assert panggilan == []
    with ai_store.buka(ai_service.path_store()) as ai:
        assert ai.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 0


@pytest.mark.parametrize("kategori", [RAHASIA, [RAHASIA], {"isi": RAHASIA}, 1, None])
def test_kategori_asing_tidak_diteruskan(kategori):
    galat = ValueError(RAHASIA)
    galat.kategori = kategori
    assert ai_errors.kategori_aman(galat) == "network_atau_provider"


@pytest.mark.parametrize("jenis", ["validasi", "timeout", "kuota"])
def test_http_default_error_aman_draf_host_utuh_dan_tanpa_autosave(server, monkeypatch, caplog, jenis):
    token, data, _, _ = mulai(server, soal=True)
    monkeypatch.setattr(assistant_service, "panggil_provider_default", _PANGGIL_DEFAULT)
    _siapkan_default(monkeypatch)
    pilihan = {"konten": json.dumps(_respons(butuh_klarifikasi=RAHASIA))} if jenis == "validasi" else {}
    if jenis == "timeout":
        pilihan["galat"] = socket.timeout(RAHASIA)
    if jenis == "kuota":
        with ai_store.buka(ai_service.path_store()) as ai:
            ai.execute("UPDATE konfigurasi SET request_akun_harian=0")
    panggilan = _transport(monkeypatch, **pilihan)
    with caplog.at_level(logging.WARNING, logger="assistant_service"):
        kode, isi, header = server.minta(
            "/pendamping/inline/pesan", cookie=token,
            data={**data, "pesan": "Pesan sintetis."}, headers=_origin(server),
        )
    assert kode == 409
    pesan_ui = {"validasi": "Format balasan", "timeout": "terlalu lama", "kuota": "Batas pemakaian"}[jenis]
    assert pesan_ui in isi
    assert RAHASIA not in isi + caplog.text
    assert 'role="alert"' in isi and 'name="pesan"' in isi
    assert "Baris satu\nbaris dua" in isi
    assert "Baris satu" not in caplog.text
    assert f'data-request-id="{data["request_id"]}:jawaban"' not in isi
    assert header["Cache-Control"] == "no-store"
    with assistant_schema.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM jawaban").fetchone()[0] == 0
    assert len(panggilan) == (0 if jenis == "kuota" else 1)


@pytest.mark.parametrize("pengaturan,kategori", [
    ({"PENDAMPING_AKTIF": "0"}, "ai_nonaktif"),
    ({"AI_NONAKTIF": "1"}, "ai_nonaktif"),
    ({"DEEPSEEK_API_KEY": ""}, "ai_konfigurasi"),
    ({"DEEPSEEK_BASE_URL": "http://contoh.invalid"}, "ai_konfigurasi"),
])
def test_konfigurasi_ditahan_tanpa_provider(monkeypatch, tmp_path, caplog, pengaturan, kategori):
    _siapkan_default(monkeypatch)
    for nama, nilai in pengaturan.items():
        monkeypatch.setenv(nama, nilai)
    panggilan = _transport(monkeypatch)
    with closing(_kon(tmp_path)) as kon:
        chat = _chat(kon)
        with caplog.at_level(logging.WARNING, logger="assistant_service"):
            with pytest.raises(assistant_service.GalatPendamping) as gagal:
                assistant_service.kirim_pesan(kon, AKUN, chat.id, "Teks sintetis.", request_id="req_config")
        assert kategori in caplog.text
        assert "pengaturan layanan" in str(gagal.value)
        assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0
    assert panggilan == []
    with ai_store.buka(ai_service.path_store()) as kon:
        assert kon.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 0


@pytest.mark.parametrize("sql,kategori", [
    ("UPDATE konfigurasi SET dihentikan=1", "ai_nonaktif"),
    ("UPDATE batas_fitur SET aktif=0 WHERE fitur='pendamping'", "ai_nonaktif"),
    ("UPDATE batas_fitur SET batas_harian=0 WHERE fitur='global'", "ai_kuota"),
    ("UPDATE batas_fitur SET batas_bulanan=0 WHERE fitur='global'", "ai_kuota"),
    ("UPDATE batas_fitur SET batas_harian=0 WHERE fitur='pendamping'", "ai_kuota"),
    ("UPDATE batas_fitur SET batas_bulanan=0 WHERE fitur='pendamping'", "ai_kuota"),
])
def test_admission_semua_batas_tetap_fail_closed(monkeypatch, sql, kategori):
    _siapkan_default(monkeypatch)
    with ai_store.buka(ai_service.path_store()) as kon:
        kon.execute(sql)
    panggilan = []
    with pytest.raises(ai_service.AIUnavailable) as gagal:
        ai_service.panggil("pendamping", AKUN, lambda: panggilan.append(1))
    assert gagal.value.kategori == kategori
    assert panggilan == []
    with ai_store.buka(ai_service.path_store()) as kon:
        assert kon.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 0


def test_fitur_lain_tidak_berubah_kategori(monkeypatch):
    _siapkan_default(monkeypatch)
    def gagal():
        raise assistant_policy.GalatRespons("Teks sintetis.", kategori="respons_jawaban")
    with pytest.raises(assistant_policy.GalatRespons):
        ai_service.panggil("cerita", AKUN, gagal)
    with ai_store.buka(ai_service.path_store()) as kon:
        assert kon.execute("SELECT kategori FROM ledger").fetchone()[0] == "network_atau_provider"


def test_prompt_menyatakan_kontrak_lengkap_dan_batas():
    sistem = assistant_policy.PROMPT_SISTEM
    contoh = '{"jawaban":"Mari bahas satu langkah dulu.","draft_memori":null,"usulan_latihan":null,"butuh_klarifikasi":false}'
    assert contoh in sistem
    assistant_policy.validasi_respons(json.loads(contoh))
    for batas in ("6000", "10, 15, 20, 25, atau 30", "maksimal 8", "tanpa HTML", "boolean"):
        assert batas in sistem
