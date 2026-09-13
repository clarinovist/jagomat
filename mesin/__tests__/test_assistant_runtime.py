"""Chat umum Pendamping: policy, client, service, HTTP, dan UI privat."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_catalog  # noqa: E402
import assistant_client  # noqa: E402
import assistant_policy  # noqa: E402
import assistant_schema  # noqa: E402
import assistant_service  # noqa: E402
import assistant_store  # noqa: E402
import auth  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


AKUN = "akun_" + "a" * 32


class ProviderPalsu:
    def __init__(self, respons=None, galat=None):
        self.respons = respons or {
            "jawaban": "Mari kita bahas satu langkah dulu.",
            "draft_memori": None,
            "usulan_latihan": None,
            "butuh_klarifikasi": False,
        }
        self.galat = galat
        self.panggilan = []

    def __call__(self, pesan):
        self.panggilan.append(pesan)
        if self.galat:
            raise self.galat
        return self.respons


def _kon(tmp_path):
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    return assistant_schema.buka(path)


def test_policy_karakter_dan_output_ketat():
    sistem = assistant_policy.PROMPT_SISTEM
    for teks in (
        "hangat", "ringkas", "tidak asal mengiyakan", "tanpa mengambil alih",
        "bukan profesional kesehatan", "bukan diagnosis",
    ):
        assert teks in sistem.lower()

    sah = assistant_policy.validasi_respons({
        "jawaban": "Kita cek bagian yang membingungkan dulu.",
        "draft_memori": None,
        "usulan_latihan": None,
        "butuh_klarifikasi": True,
    })
    assert sah.jawaban.startswith("Kita cek")
    for rusak in (
        {"jawaban": "x", "draft_memori": None, "usulan_latihan": None,
         "butuh_klarifikasi": False, "asing": 1},
        {"jawaban": "<script>alert(1)</script>", "draft_memori": None,
         "usulan_latihan": None, "butuh_klarifikasi": False},
        {"jawaban": "orang@example.test", "draft_memori": None,
         "usulan_latihan": None, "butuh_klarifikasi": False},
        {"jawaban": "x", "draft_memori": {}, "usulan_latihan": None,
         "butuh_klarifikasi": False},
    ):
        with pytest.raises(ValueError):
            assistant_policy.validasi_respons(rusak)


def test_client_request_exact_dan_api_key_hanya_header(monkeypatch):
    terlihat = []

    class Respons:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _batas):
            return json.dumps({
                "choices": [{"message": {"content": json.dumps({
                    "jawaban": "Jawaban aman.", "draft_memori": None,
                    "usulan_latihan": None, "butuh_klarifikasi": False,
                })}}]
            }).encode()

    def buka(req, timeout):
        terlihat.append((req, timeout))
        return Respons()

    class Pembuka:
        def open(self, req, timeout):
            return buka(req, timeout)

    def buat_pembuka(handler):
        assert isinstance(handler, urllib.request.HTTPRedirectHandler)
        return Pembuka()

    monkeypatch.setattr(assistant_client.urllib.request, "build_opener", buat_pembuka)
    cfg = assistant_client.Konfigurasi(
        base_url="https://api.deepseek.com", api_key="kunci-sintetis",
        model="deepseek-flash",
    )
    hasil = assistant_client.kirim(
        cfg, [{"role": "system", "content": "sistem"},
              {"role": "user", "content": "halo"}]
    )
    req, timeout = terlihat[0]
    tubuh = json.loads(req.data)
    assert req.full_url == "https://api.deepseek.com/chat/completions"
    assert req.headers["Authorization"] == "Bearer kunci-sintetis"
    assert tubuh == {
        "model": "deepseek-flash",
        "messages": [{"role": "system", "content": "sistem"},
                     {"role": "user", "content": "halo"}],
        "temperature": 0.4,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }
    assert "kunci-sintetis" not in req.data.decode()
    assert timeout == assistant_client.BATAS_WAKTU_DETIK
    assert hasil["jawaban"] == "Jawaban aman."


def test_client_menolak_config_redirect_dan_respons_besar(monkeypatch):
    with pytest.raises(ValueError, match="HTTPS"):
        assistant_client.Konfigurasi("http://contoh.test", "k", "m")

    def redirect(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions", 302, "redirect",
            {"Location": "https://asing.test/ambil"}, io.BytesIO(b""),
        )

    cfg = assistant_client.Konfigurasi("https://api.deepseek.com", "k", "m")

    class PembukaRedirect:
        def open(self, req, timeout):
            return redirect(req, timeout)

    monkeypatch.setattr(
        assistant_client.urllib.request, "build_opener", lambda *_: PembukaRedirect()
    )
    with pytest.raises(assistant_client.GalatProvider, match="redirect"):
        assistant_client.kirim(cfg, [{"role": "user", "content": "x"}])

    class ResponsBesar:
        headers = {"Content-Length": str(assistant_client.BATAS_RESPONS_BYTE + 1)}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _batas): return b""

    class PembukaBesar:
        def open(self, req, timeout): return ResponsBesar()

    monkeypatch.setattr(
        assistant_client.urllib.request, "build_opener", lambda *_: PembukaBesar()
    )
    with pytest.raises(assistant_client.GalatProvider, match="terlalu besar"):
        assistant_client.kirim(cfg, [{"role": "user", "content": "x"}])


def test_service_payload_minimum_dan_tanpa_data_anak(tmp_path):
    provider = ProviderPalsu()
    with _kon(tmp_path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        hasil = assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Saya bingung mulai menjelaskan pecahan.",
            request_id="req_service", panggil_provider=provider, sekarang=101,
        )
    assert hasil == "Mari kita bahas satu langkah dulu."
    pesan = provider.panggilan[0]
    assert {item["role"] for item in pesan} == {"system", "user"}
    muatan = json.loads(next(item["content"] for item in pesan if item["role"] == "user"))
    assert set(muatan) == {"katalog", "memori", "percakapan"}
    assert muatan["memori"] == []
    mentah = json.dumps(muatan)
    for terlarang in ("nama_anak", "siswa_id", "diagnosis", "malrule", "kunci"):
        assert terlarang not in mentah.lower()


def test_service_version_berubah_saat_provider_berjalan_tidak_commit(tmp_path):
    with _kon(tmp_path) as kon:
        persetujuan = assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)

        def ubah_consent(_pesan):
            assert assistant_store.cabut_persetujuan(
                kon, AKUN, persetujuan.id,
                versi_diharapkan=persetujuan.versi, sekarang=102,
            )
            kon.commit()
            return {
                "jawaban": "Jawaban yang sudah usang.",
                "draft_memori": None,
                "usulan_latihan": None,
                "butuh_klarifikasi": False,
            }

        with pytest.raises(assistant_service.GalatPendamping, match="berubah"):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Pertanyaan sebelum consent dicabut.",
                request_id="req_race", panggil_provider=ubah_consent,
                sekarang=101,
            )
        pesan = assistant_store.daftar_pesan(kon, AKUN, chat.id)
        assert pesan == ()


def test_service_provider_gagal_tidak_menyimpan_jawaban_palsu(tmp_path):
    provider = ProviderPalsu(galat=assistant_client.GalatProvider("mati"))
    with _kon(tmp_path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        with pytest.raises(assistant_service.GalatPendamping):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Bantu saya memahami langkah berikutnya.",
                request_id="req_gagal", panggil_provider=provider, sekarang=101,
            )
        pesan = assistant_store.daftar_pesan(kon, AKUN, chat.id)
        assert pesan == ()
        assert kon.execute(
            "SELECT status FROM operasi WHERE request_id='req_gagal'"
        ).fetchone()[0] == "gagal"


def test_service_chat_tanpa_memori_tidak_mengirim_memori(tmp_path):
    provider = ProviderPalsu()
    with _kon(tmp_path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100,
        )
        sumber = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        assistant_store.tambah_memori(
            kon, AKUN, "Jawab dengan contoh konkret.", sumber_chat_id=sumber.id,
            dikonfirmasi=True, sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "tanpa_memori", sekarang=100)
        assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Halo Pendamping.",
            request_id="req_tanpa_memori", panggil_provider=provider,
            sekarang=101,
        )
        muatan = json.loads(provider.panggilan[0][1]["content"])
        assert muatan["memori"] == []


def test_service_tanpa_consent_nol_provider_dan_nol_pesan(tmp_path):
    provider = ProviderPalsu()
    with _kon(tmp_path) as kon:
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        with pytest.raises(assistant_service.GalatPendamping, match="Persetujuan"):
            assistant_service.kirim_pesan(
                kon, AKUN, chat.id, "Halo Pendamping.",
                request_id="req_tanpa_consent", panggil_provider=provider,
                sekarang=101,
            )
        assert provider.panggilan == []
        assert assistant_store.daftar_pesan(kon, AKUN, chat.id) == ()


def test_service_idempoten_tidak_memanggil_provider_dua_kali(tmp_path):
    provider = ProviderPalsu()
    with _kon(tmp_path) as kon:
        assistant_store.beri_persetujuan(
            kon, AKUN, policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100,
        )
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        pertama = assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Pertanyaan yang sama.",
            request_id="req_idem", panggil_provider=provider, sekarang=101,
        )
        kedua = assistant_service.kirim_pesan(
            kon, AKUN, chat.id, "Pertanyaan yang sama.",
            request_id="req_idem", panggil_provider=provider, sekarang=102,
        )
        assert pertama == kedua
        assert len(provider.panggilan) == 1
        assert [p.peran for p in assistant_store.daftar_pesan(
            kon, AKUN, chat.id
        )] == ["pengguna", "asisten"]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "kunci-sintetis")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    palsu = ProviderPalsu()
    monkeypatch.setattr(assistant_service, "panggil_provider_default", palsu)
    s = ServerUji(tmp_path, monkeypatch)
    s.provider = palsu
    yield s
    s.berhenti()


def _token_guru(server):
    akun = auth.cari_akun("guru")
    return sessions.buat(
        akun["pengguna"], "guru", id_akun=akun["id_akun"],
        revisi_auth=akun["revisi_auth"],
    )


def _consent(server, token):
    return server.minta(
        "/pendamping/persetujuan", cookie=token,
        data={"setuju": "1", "kebijakan": assistant_policy.VERSI_KEBIJAKAN},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )


def test_http_provider_tidak_lengkap_tidak_membuat_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    s = ServerUji(tmp_path, monkeypatch)
    try:
        kode, isi, _ = s.minta("/pendamping", cookie=_token_guru(s))
        assert kode == 200
        assert "Ruang pendamping" in isi
        assert not assistant_schema.BAWAAN.exists()
    finally:
        s.berhenti()


def test_http_feature_flag_default_nonaktif(tmp_path, monkeypatch):
    monkeypatch.delenv("PENDAMPING_AKTIF", raising=False)
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(assistant_schema, "BAWAAN", tmp_path / "pendamping.db")
    s = ServerUji(tmp_path, monkeypatch)
    try:
        kode, _, _ = s.minta("/pendamping", cookie=_token_guru(s))
        assert kode == 404
        assert not assistant_schema.BAWAAN.exists()
    finally:
        s.berhenti()


def test_nav_pendamping_standalone_tidak_lagi_ditawarkan():
    import teacher_pages

    assert 'href="/pendamping"' not in teacher_pages._topbar("ortu", "guru")
    assert 'href="/pendamping"' not in teacher_pages._topbar_stitch("ortu", "guru")
    assert 'href="/pendamping"' not in teacher_pages._topbar("admin", "admin")
    assert 'href="/pendamping"' not in teacher_pages._topbar_stitch("admin", "admin")


def test_http_hanya_cookie_guru_stabil(server):
    assert server.minta("/pendamping")[0] == 401
    assert server.minta("/pendamping", auth=("guru", SANDI_GURU))[0] == 401
    assert server.minta("/pendamping", auth=("feby", SANDI_MURID))[0] == 401

    akun_admin = auth.cari_akun("guru")
    akun_admin["peran"] = "admin"
    # Tidak menyunting fixture akun: cukup sesi admin dengan ID guru, reader
    # principal wajib tetap menolak karena peran sesi bukan guru.
    token_admin = sessions.buat(
        "guru", "admin", id_akun=akun_admin["id_akun"],
        revisi_auth=akun_admin["revisi_auth"],
    )
    assert server.minta("/pendamping", cookie=token_admin)[0] == 401
    assert server.minta("/pendamping", cookie=_token_guru(server))[0] == 200


def test_http_rute_umum_dialihkan_dan_post_umum_ditolak_tanpa_efek_samping(server):
    token = _token_guru(server)
    kode, isi, _ = server.minta("/pendamping", cookie=token)
    assert kode == 200
    assert "Ruang pendamping" in isi
    akun = auth.cari_akun("guru")["id_akun"]
    assert _consent(server, token)[0] == 200
    with assistant_schema.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, header = server.minta(
        "/pendamping/chat-baru", cookie=token,
        data={"mode": "aktif", "pesan_awal": "Pesan pertama.", "request_id": "req_http_12345678"},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 410
    assert "Percakapan umum baru sudah ditutup" in isi
    assert header["Cache-Control"] == "no-store"
    assert server.provider.panggilan == []
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert assistant_store.daftar_chat(kon, akun) == ()


def test_post_pesan_chat_umum_lama_ditolak_tanpa_pesan_atau_provider(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        chat = assistant_store.buat_chat(kon, akun, "aktif", sekarang=1)
        kon.commit()
        sebelum = tuple(kon.iterdump())
    kode, isi, header = server.minta(
        f"/pendamping/chat/{chat.id}/pesan", cookie=token,
        data={"pesan": "Jangan dikirim.", "request_id": "req_umum_ditutup"},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 410 and "Pesan ini tidak dikirim" in isi
    assert header["Cache-Control"] == "no-store"
    assert server.provider.panggilan == []
    with assistant_schema.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert assistant_store.daftar_pesan(kon, akun, chat.id) == ()


def urllib_parse_path_from_html(isi):
    import re
    cocok = re.search(r'action="(/pendamping/chat/([^/"]+)/pesan)"', isi)
    assert cocok, isi[:500]
    return cocok.group(1).rsplit("/pesan", 1)[0]


def test_http_cross_site_duplikat_besar_ditolak_sebelum_provider(server):
    token = _token_guru(server)
    _consent(server, token)
    sebelum = len(server.provider.panggilan)
    kode, _, _ = server.minta(
        "/pendamping/chat-baru", cookie=token, data={"mode": "aktif"},
        headers={"Origin": "https://asing.test", "Sec-Fetch-Site": "cross-site"},
    )
    assert kode == 403

    mentah = "mode=aktif&mode=tanpa_memori".encode()
    import urllib.request
    req = urllib.request.Request(
        server.alamat + "/pendamping/chat-baru", data=mentah, method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": f"osn_sesi={token}",
            "Origin": server.alamat,
            "Sec-Fetch-Site": "same-origin",
        },
    )
    try:
        urllib.request.urlopen(req)
        raise AssertionError("form duplikat harus ditolak")
    except urllib.error.HTTPError as galat:
        assert galat.code == 400

    kode, _, _ = server.minta(
        "/pendamping/chat-baru", cookie=token,
        data={"mode": "aktif", "pesan_awal": "x" * 13000, "request_id": "req_abcdefgh"},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 413
    assert len(server.provider.panggilan) == sebelum


def test_arsip_chat_umum_hanya_baca_owner_only_dan_tanpa_composer(server):
    token = _token_guru(server)
    _consent(server, token)
    akun = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        umum = assistant_store.buat_chat(kon, akun, "aktif", sekarang=1)
        assistant_store.tambah_pesan(
            kon, akun, umum.id, "pengguna", "Pertanyaan umum lama sintetis.",
            request_id="req_arsip_sintetis", sekarang=2,
        )
        kon.commit()
    kode, akun_html, header = server.minta("/akun", cookie=token)
    assert kode == 200 and "Arsip percakapan lama" in akun_html
    assert "Pertanyaan umum lama sintetis." not in akun_html
    assert header["Cache-Control"] == "no-store"
    kode, arsip, header = server.minta(
        f"/akun?section=arsip-pendamping&chat={umum.id}", cookie=token,
    )
    assert kode == 200 and "Pertanyaan umum lama sintetis." in arsip
    assert "Pesan untuk Pendamping" not in arsip and "Kirim pesan" not in arsip
    assert "tidak terhubung ke anak" in arsip
    assert "script-src" not in header["Content-Security-Policy"]
    assert "<script" not in arsip and "fonts.googleapis.com" not in arsip

    auth.tambah_akun("ortu-arsip", "sandi-ortu-arsip-123", "guru")
    akun_lain = auth.cari_akun("ortu-arsip")
    token_lain = sessions.buat(
        akun_lain["pengguna"], "guru", id_akun=akun_lain["id_akun"],
        revisi_auth=akun_lain["revisi_auth"],
    )
    asing = server.minta(
        f"/akun?section=arsip-pendamping&chat={umum.id}", cookie=token_lain,
    )
    hilang = server.minta(
        "/akun?section=arsip-pendamping&chat=chat_" + "f" * 32,
        cookie=token_lain,
    )
    assert asing[0] == hilang[0] == 404 and asing[1] == hilang[1]
    assert "Pertanyaan umum lama sintetis." not in asing[1]


def test_http_akun_lain_tidak_bisa_membaca_chat(server):
    token_a = _token_guru(server)
    _consent(server, token_a)
    akun_a = auth.cari_akun("guru")["id_akun"]
    with assistant_schema.buka() as kon:
        chat_id = assistant_store.buat_chat(
            kon, akun_a, "aktif", sekarang=1,
        ).id
        kon.commit()

    auth.tambah_akun("ortu-b", "sandi-ortu-b-123", "guru")
    akun_b = auth.cari_akun("ortu-b")
    token_b = sessions.buat(
        "ortu-b", "guru", id_akun=akun_b["id_akun"],
        revisi_auth=akun_b["revisi_auth"],
    )
    _consent(server, token_b)
    kode_asing, isi_asing, _ = server.minta(
        f"/pendamping/chat/{chat_id}", cookie=token_b
    )
    kode_hilang, isi_hilang, _ = server.minta(
        "/pendamping/chat/chat_ffffffffffffffffffffffffffffffff", cookie=token_b
    )
    assert kode_asing == kode_hilang == 404
    assert isi_asing == isi_hilang
