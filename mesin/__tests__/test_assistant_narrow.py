"""Kontrak kandidat sempit; semua provider, akun, dan penyimpanan sintetis."""
import json

import pytest

import assistant_catalog
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
from test_assistant_runtime import AKUN, _kon


JAWABAN = {"jawaban": "Mari pahami satu langkah.", "butuh_klarifikasi": False}


def test_respons_baru_tepat_dua_field():
    hasil = assistant_policy.validasi_respons(JAWABAN)
    assert set(vars(hasil)) == {"jawaban", "butuh_klarifikasi"}
    assert hasil.jawaban == JAWABAN["jawaban"]


@pytest.mark.parametrize("tambahan", [
    {"draft_memori": None}, {"usulan_latihan": None},
    {"draft_memori": None, "usulan_latihan": None},
    {"usulan_latihan": {"topik_id": "pecahan"}}, {"tools": []},
])
def test_field_retired_ditolak_bukan_dibuang(tambahan):
    with pytest.raises(assistant_policy.GalatRespons):
        assistant_policy.validasi_respons({**JAWABAN, **tambahan})


@pytest.mark.parametrize("jawaban,klarifikasi", [
    ("", False), ("<b>Halo</b>", False), ("orang@example.test", False),
    ("x" * 6001, False), ("Halo", "false"), ("Halo", 0), ([], False),
])
def test_dua_field_tetap_fail_closed(jawaban, klarifikasi):
    with pytest.raises(assistant_policy.GalatRespons):
        assistant_policy.validasi_respons({"jawaban": jawaban, "butuh_klarifikasi": klarifikasi})


def test_client_menolak_json_key_ganda(monkeypatch):
    import assistant_client
    class Respons:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, batas):
            return json.dumps({'choices': [{'message': {'content':
                '{"jawaban":"Pertama","jawaban":"Kedua","butuh_klarifikasi":false}'}}]}).encode()
    class Pembuka:
        def open(self, *_a, **_k): return Respons()
    monkeypatch.setattr(assistant_client.urllib.request, 'build_opener', lambda *_: Pembuka())
    with pytest.raises(assistant_client.GalatProvider):
        assistant_client.kirim(assistant_client.Konfigurasi('https://api.deepseek.com', 'sintetis', 'deepseek-flash'), [])


def test_payload_tidak_mengambil_katalog_memori_dan_replay_lama(tmp_path, monkeypatch):
    with _kon(tmp_path) as kon:
        assistant_store.beri_persetujuan(kon, AKUN,
            policy_version=assistant_policy.VERSI_KEBIJAKAN,
            provider_id="deepseek", kategori="chat_umum", sekarang=100)
        chat = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
        assistant_store.tambah_memori(kon, AKUN, "Gunakan kalimat pendek.",
            sumber_chat_id=chat.id, dikonfirmasi=True, sekarang=100)
        # Ukur serialized user payload terhadap fixture yang identik sebelum retirement.
        pesan_lama = [{"peran": "pengguna", "teks": "Bantu saya mendampingi."}]
        sebelum = json.dumps({
            "katalog": json.loads(assistant_catalog.serialisasi_ringkas(assistant_catalog.buat_katalog())),
            "memori": ["Gunakan kalimat pendek."], "percakapan": pesan_lama,
        }, ensure_ascii=False, separators=(",", ":")).encode()
        def dilarang(*args, **kwargs):
            pytest.fail("Outbound baru tidak boleh mengambil katalog/memori")
        monkeypatch.setattr(assistant_catalog, "buat_katalog", dilarang)
        monkeypatch.setattr(assistant_store, "memori_untuk_chat", dilarang)
        terlihat = []
        def provider(pesan):
            terlihat.append(pesan)
            return JAWABAN
        hasil = assistant_service.kirim_pesan(kon, AKUN, chat.id, "Bantu saya mendampingi.",
            request_id="req_kontrak_sempit", panggil_provider=provider, sekarang=101)
        assert hasil == JAWABAN["jawaban"]
        sesudah = terlihat[0][-1]["content"].encode()
        assert json.loads(sesudah) == {"percakapan": pesan_lama}
        assert len(sesudah) < len(sebelum)
        assert assistant_store.ambil_chat(kon, AKUN, chat.id).mode_memori == "aktif"
        assert len(assistant_store.daftar_memori(kon, AKUN)) == 1
        assert not assistant_store.daftar_usulan_chat(kon, AKUN, chat.id)
        # Replay durable tidak perlu mem-parsing protokol respons lagi.
        monkeypatch.setattr(assistant_policy, "validasi_respons", dilarang)
        assert assistant_service.kirim_pesan(kon, AKUN, chat.id, "Bantu saya mendampingi.",
            request_id="req_kontrak_sempit", panggil_provider=dilarang, sekarang=102) == hasil
        assert len(terlihat) == 1
        print("payload_user_bytes_sebelum=%d sesudah=%d" % (len(sebelum), len(sesudah)))
