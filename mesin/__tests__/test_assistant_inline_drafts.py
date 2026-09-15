"""Kontrak navigasi host dan draf request-local Pendamping inline."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_inline


def _data():
    return {
        "jwb_11": [""], "kode_11": ["K"], "cara_11": ["Baris 1\nBaris 2"],
        "cek_pemahaman_11": ["ragu"], "hadir_dilewati_11": ["1"],
        "hadir_belum_11": ["1"], "belum_11": ["1"],
        "jwb_12": ["42"], "kode_12": ["benar"], "cara_12": ["Cara kedua"],
        "cek_pemahaman_12": ["bisa_menjelaskan"], "hadir_dilewati_12": ["1"],
        "dilewati_12": ["1"], "hadir_belum_12": ["1"],
        "hadir_sertakan_pemetaan": ["1"],
    }


def test_draf_latihan_mempertahankan_kontrak_timer_sesi():
    data = {
        "topik": ["campuran"], "jumlah_soal": ["15"], "mode": ["drill"],
        "hadir_timer_mode": ["1"], "timer_mode": ["sesi"],
        "durasi_menit": ["47"], "timer_auto": ["1"],
    }
    draf = assistant_inline.parse_draf_latihan(data, ("campuran", "aritmatika"))
    assert draf.timer_mode is True
    data["timer_mode"] = ["1"]
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_latihan(data, ("campuran",))


def test_tujuan_host_kanonik_dan_resource_persis():
    anak = assistant_inline.parse_query_host("anak", 7, [("bantuan", "rencana")])
    assert anak.resource_id == "7"
    assert anak.jalur == "/anak/7?bantuan=rencana#bantuan-rencana"
    soal = assistant_inline.parse_query_host(
        "sesi", 42, [("bantuan", "soal"), ("nomor", "3"), ("chat", "chat_" + "a" * 32)]
    )
    assert (soal.jenis_resource, soal.resource_id, soal.anchor) == ("soal", "42:3", "bantuan-soal-3")
    assert soal.jalur == "/sesi/42?bantuan=soal&nomor=3&chat=chat_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa#bantuan-soal-3"


@pytest.mark.parametrize("host,identitas,pasangan", [
    ("anak", 7, [("bantuan", "rencana"), ("bantuan", "latihan")]),
    ("anak", 7, [("bantuan", "soal"), ("nomor", "1")]),
    ("sesi", 42, [("bantuan", "soal"), ("nomor", "01")]),
    ("sesi", 42, [("bantuan", "soal"), ("nomor", "-1")]),
    ("sesi", 42, [("bantuan", "soal"), ("nomor", "１")]),
    ("sesi", 42, [("bantuan", "sesi"), ("asing", "1")]),
    ("sesi", 42, [("bantuan", "soal"), ("nomor", "1"), ("chat", "chat_buruk")]),
])
def test_query_host_menolak_bentuk_ambigu(host, identitas, pasangan):
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_query_host(host, identitas, pasangan)


def test_draf_lengkap_mempertahankan_kosong_checkbox_caraku_dan_pemahaman():
    draf = assistant_inline.parse_draf_koreksi(_data(), (11, 12))
    satu = draf.untuk(11)
    dua = draf.untuk(12)
    assert (satu.jawaban, satu.cara, satu.pemahaman) == ("", "Baris 1\nBaris 2", "ragu")
    assert (satu.dilewati, satu.belum_pernah) == (False, True)
    assert (dua.jawaban, dua.kode, dua.dilewati, dua.belum_pernah) == ("42", "benar", True, False)
    assert draf.sertakan_pemetaan is False


def test_draf_mode_drill_tanpa_caraku_dan_menolak_kode_menebak():
    data = _data()
    data.pop("cara_11")
    data.pop("cara_12")
    draf = assistant_inline.parse_draf_koreksi(data, (11, 12), mode="drill")
    assert draf.untuk(11).cara == ""
    data["kode_11"] = ["N"]
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_koreksi(data, (11, 12), mode="drill")


@pytest.mark.parametrize("ubah", [
    lambda d: d.update({"jwb_11": ["a", "b"]}),
    lambda d: d.update({"kode_11": ["asing"]}),
    lambda d: d.pop("hadir_dilewati_11"),
    lambda d: d.update({"jwb_999": ["asing"]}),
    lambda d: d.update({"cara_11": ["x" * 8001]}),
    lambda d: d.update({"sertakan_pemetaan": ["0"]}),
])
def test_draf_menolak_duplikat_enum_marker_id_asing_dan_batas(ubah):
    data = _data()
    ubah(data)
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_koreksi(data, (11, 12))


def test_draf_tinjauan_tetap_request_local_lengkap():
    data = _data()
    data.update({'catatan_tinjauan_11': ['Catatan lokal <sintetis>'],
                 'provenance_11': ['setelah_bantuan'], 'jawaban_bantuan_11': ['42'],
                 'versi_tinjauan_11': ['a' * 64]})
    draf = assistant_inline.parse_draf_koreksi(data, (11, 12))
    b = draf.untuk(11)
    assert (b.catatan_tinjauan, b.provenance, b.jawaban_bantuan, b.versi_tinjauan) == (
        'Catatan lokal <sintetis>', 'setelah_bantuan', '42', 'a' * 64)
    assert draf.untuk(12).catatan_tinjauan is None


@pytest.mark.parametrize('field,nilai', [('provenance_11', 'mandiri_palsu'), ('versi_tinjauan_11', '123')])
def test_draf_tinjauan_tidak_sah_ditolak(field, nilai):
    data = _data()
    data[field] = [nilai]
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline.parse_draf_koreksi(data, (11, 12))
