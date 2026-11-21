"""Descriptor `adegan_awal` v1: validator ketat, allow-list ikon, dan aset WebP."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_data as data_modul
import adegan_awal_svg
import brand
from adegan_awal_data import IKON_DIDUKUNG, validasi_adegan_awal
from visual_contract import DescriptorVisual

ASET = Path(brand.FOLDER_ASET)


def _sah(**ubah):
    dasar = {
        "adegan": "deret_ikon",
        "baris": [
            {"nama": "Bola", "ikon": "bola", "jumlah": 3},
            {"nama": "Mobil", "ikon": "mobil", "jumlah": 5},
            {"nama": "Boneka", "ikon": "boneka", "jumlah": 2},
        ],
        "satuan_ikon": 1,
        "tanya": {"varian": "baca", "i": 1},
    }
    return {**dasar, **ubah}


def _dengan_baris(indeks, **ubah):
    baris = [dict(b) for b in _sah()["baris"]]
    baris[indeks] = {**baris[indeks], **ubah}
    return baris


def _tolak(data):
    with pytest.raises(ValueError):
        validasi_adegan_awal(data)
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)


def test_descriptor_sah_diterima_dan_dibekukan():
    descriptor = DescriptorVisual("adegan_awal", 1, _sah())
    assert descriptor.data["baris"][1]["jumlah"] == 5
    with pytest.raises(TypeError):
        descriptor.data["baris"][1]["jumlah"] = 9
    validasi_adegan_awal(descriptor.data)  # bentuk beku juga lolos (jalur renderer)


@pytest.mark.parametrize("tanya", (
    {"varian": "baca", "i": 0}, {"varian": "terbanyak"},
    {"varian": "selisih", "x": 2, "y": 0}, {"varian": "jumlah", "x": 0, "y": 1},
))
def test_semua_bentuk_tanya_sah(tanya):
    validasi_adegan_awal(_sah(tanya=tanya))


@pytest.mark.parametrize("jumlah", (0, 1, 12))
def test_jumlah_batas_dalam_rentang_diterima(jumlah):
    validasi_adegan_awal(_sah(baris=_dengan_baris(0, jumlah=jumlah)))


@pytest.mark.parametrize("jumlah", (-1, 13, 100, 2.0, "3", True, None))
def test_jumlah_di_luar_rentang_atau_bukan_int_murni_ditolak(jumlah):
    _tolak(_sah(baris=_dengan_baris(0, jumlah=jumlah)))


@pytest.mark.parametrize("ikon", (
    "../bola", "bola.png", "ikon-bola-v1.webp", "/aset/ikon-bola-v1.webp",
    "BOLA", "bola ", "", "maskot", "http://contoh.invalid/a", None, 3, ["bola"],
    "bo\x00la",
))
def test_ikon_di_luar_allow_list_atau_liar_ditolak(ikon):
    _tolak(_sah(baris=_dengan_baris(0, ikon=ikon)))


@pytest.mark.parametrize("nama", (
    "<b>Bola</b>", "<script>x</script>", "Bola<", "", "   ", "W" * 25,
    "Bo\x00la", "Bo‮la", "Bo​la", "Bo\x1fla", None, 3,
))
def test_nama_baris_markup_kontrol_atau_terlalu_panjang_ditolak(nama):
    _tolak(_sah(baris=_dengan_baris(0, nama=nama)))


def test_nama_baris_dua_puluh_empat_karakter_diterima():
    validasi_adegan_awal(_sah(baris=_dengan_baris(0, nama="W" * 24)))


def test_nama_baris_duplikat_ditolak_termasuk_beda_huruf_besar():
    baris = _dengan_baris(1, nama="bola")
    _tolak(_sah(baris=baris))


@pytest.mark.parametrize("banyak", (0, 1, 6))
def test_banyak_baris_di_luar_dua_sampai_lima_ditolak(banyak):
    # Batas atas naik 4 -> 5 (21 Nov 2026, piktogram P5); turus tetap 2..4 (test_visual_adegan_awal_turus).
    contoh = [{"nama": f"K{i}", "ikon": IKON_DIDUKUNG[i], "jumlah": 1} for i in range(6)]
    _tolak(_sah(baris=contoh[:banyak], tanya={"varian": "terbanyak"}))


@pytest.mark.parametrize("banyak", (2, 3, 4, 5))
def test_banyak_baris_dua_sampai_lima_diterima(banyak):
    contoh = [{"nama": f"K{i}", "ikon": IKON_DIDUKUNG[i], "jumlah": 1} for i in range(5)]
    validasi_adegan_awal(_sah(baris=contoh[:banyak], tanya={"varian": "terbanyak"}))


@pytest.mark.parametrize("ubah", (
    {"adegan": "deret_titik"}, {"adegan": None}, {"satuan_ikon": 0}, {"satuan_ikon": 3},
    {"satuan_ikon": -1}, {"satuan_ikon": 2.0}, {"satuan_ikon": "2"}, {"satuan_ikon": None},
    {"satuan_ikon": True}, {"satuan_ikon": 1.0}, {"baris": "Bola"},
    {"baris": None}, {"tanya": None}, {"tanya": "baca"},
))
def test_nilai_field_tidak_sah_ditolak(ubah):
    _tolak(_sah(**ubah))


@pytest.mark.parametrize("field", (
    "kunci", "jawaban", "answer", "malrule", "pembahasan", "svg", "html",
    "onload", "xlink:href", "label", "extra",
))
def test_field_tambahan_apa_pun_ditolak_termasuk_kunci_terlarang(field):
    _tolak({**_sah(), field: "uji"})
    _tolak(_sah(baris=_dengan_baris(0, **{field: "uji"})))
    _tolak(_sah(tanya={"varian": "terbanyak", field: "uji"}))


@pytest.mark.parametrize("hapus", ("adegan", "baris", "satuan_ikon", "tanya"))
def test_field_hilang_ditolak(hapus):
    _tolak({k: v for k, v in _sah().items() if k != hapus})


@pytest.mark.parametrize("hapus", ("nama", "ikon", "jumlah"))
def test_field_baris_hilang_ditolak(hapus):
    baris = _sah()["baris"]
    baris[0] = {k: v for k, v in baris[0].items() if k != hapus}
    _tolak(_sah(baris=baris))


@pytest.mark.parametrize("tanya", (
    {"varian": "baca"}, {"varian": "baca", "i": 3}, {"varian": "baca", "i": -1},
    {"varian": "baca", "i": True}, {"varian": "baca", "i": 1, "x": 0},
    {"varian": "terbanyak", "i": 0},
    {"varian": "selisih", "x": 1, "y": 1}, {"varian": "selisih", "x": 0},
    {"varian": "jumlah", "x": 0, "y": 3}, {"varian": "jumlah", "x": "0", "y": 1},
    {"varian": "lain"}, {"varian": None}, {},
))
def test_tanya_tidak_sah_ditolak(tanya):
    _tolak(_sah(tanya=tanya))


def test_jenis_versi_lain_tidak_terdaftar():
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 2, _sah())


# ── aset ikon ────────────────────────────────────────────────────────────

def test_dua_puluh_sembilan_ikon_terdaftar_tanpa_duplikat():
    assert len(IKON_DIDUKUNG) == 29
    assert len(set(IKON_DIDUKUNG)) == 29
    assert list(IKON_DIDUKUNG) == sorted(IKON_DIDUKUNG)


@pytest.mark.parametrize("nama", IKON_DIDUKUNG)
def test_setiap_ikon_ada_di_aset_dan_webp_alfa_192(nama):
    berkas = f"ikon-{nama}-v1.webp"
    assert brand.ASET[berkas] == "image/webp"
    isi = (ASET / berkas).read_bytes()
    assert isi[:4] == b"RIFF" and isi[8:12] == b"WEBP"
    assert struct.unpack("<I", isi[4:8])[0] == len(isi) - 8
    assert isi[12:16] == b"VP8X"  # kanvas diperluas: wajib untuk kanal alfa
    assert isi[20] & 0x10, "bendera alfa VP8X mati"
    lebar = int.from_bytes(isi[24:27], "little") + 1
    tinggi = int.from_bytes(isi[27:30], "little") + 1
    assert (lebar, tinggi) == (192, 192)
    assert len(isi) < 20_000, "ikon terlalu berat"


def test_semua_aset_ikon_di_allow_list_adalah_ikon_terdaftar():
    ikon_aset = {n for n in brand.ASET if n.startswith("ikon-")}
    assert ikon_aset == {f"ikon-{n}-v1.webp" for n in IKON_DIDUKUNG}


@pytest.mark.parametrize("nama", IKON_DIDUKUNG)
def test_href_renderer_menunjuk_aset_terdaftar(nama):
    href = adegan_awal_svg.jalur_ikon(nama)
    assert href == f"/aset/ikon-{nama}-v1.webp"
    assert href.rsplit("/", 1)[1] in brand.ASET


def test_konstanta_renderer_sama_dengan_modul_data():
    assert adegan_awal_svg.validasi_adegan_awal is data_modul.validasi_adegan_awal
