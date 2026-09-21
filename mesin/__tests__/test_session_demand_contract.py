"""Kontrak campuran nonaktif tetap menolak fokus ambigu dan metadata palsu."""
from collections import UserString
from dataclasses import FrozenInstanceError, replace
import json

import pytest

import session_demand_contract as kontrak


def contoh():
    a = kontrak.KonteksTuntutan("keliling_luas_datar", "P3", "teks-v1", "draft-v1", "langsung.v1")
    b = kontrak.KonteksTuntutan("keliling_luas_datar", "P6", "teks-v1", "draft-v1", "balik.v1")
    fa = kontrak.FokusTuntutan((a.template_id, "K", "datar.tukar_luas"), a, (11, 13))
    fb = kontrak.FokusTuntutan((b.template_id, "K", "datar.balik_lupa_bagi_dua"), b, (12, 14))
    return kontrak.KontrakSesiTuntutan((kontrak.ButirTuntutan(1, a, fa.kunci),
                                       kontrak.ButirTuntutan(2, b, fb.kunci)), (fa, fb))


def test_campuran_beku_roundtrip_tanpa_level_global():
    sumber = contoh()
    teks = kontrak.serialisasi(sumber)
    hasil = kontrak.deserialisasi(teks)
    assert hasil == sumber
    assert kontrak.serialisasi(hasil) == teks
    assert hasil.profil_parameter == ("P3", "P6")
    assert hasil.ringkasan == "Profil campuran: P3, P6"
    assert "level" not in json.loads(teks)
    with pytest.raises(FrozenInstanceError):
        hasil.butir[0].konteks.profil_parameter = "P6"
    assert kontrak.serialisasi(replace(sumber, fokus=tuple(reversed(sumber.fokus)))) == teks
    f = sumber.fokus[0]
    assert replace(f, sumber_konfirmasi_ids=tuple(reversed(f.sumber_konfirmasi_ids))) == f


def test_homogen_manual_tanpa_fokus_tetap_jujur():
    sumber = contoh()
    manual = kontrak.KontrakSesiTuntutan((replace(sumber.butir[0], target_fokus=None),))
    assert manual.ringkasan == "Profil P3"
    assert kontrak.deserialisasi(kontrak.serialisasi(manual)) == manual


@pytest.mark.parametrize("field,nilai", (
    ("tuntutan_id", "lain.v1"), ("versi_rubrik", "draft-v2"),
    ("mode_representasi", "geometri_datar-v1"), ("profil_parameter", "P4"),
    ("template_id", "luas_kotak_satuan"),
))
def test_probe_wajib_tuntutan_sumber_masing_masing(field, nilai):
    sumber = contoh()
    b = replace(sumber.butir[0], konteks=replace(sumber.butir[0].konteks, **{field: nilai}))
    with pytest.raises(ValueError, match="konteks fokus sumber"):
        replace(sumber, butir=(b, sumber.butir[1]))


def test_fokus_kunci_sama_tidak_menyelundupkan_dua_tuntutan():
    sumber = contoh()
    kedua = replace(sumber.fokus[1], kunci=sumber.fokus[0].kunci)
    with pytest.raises(ValueError, match="dua fokus"):
        replace(sumber, fokus=(sumber.fokus[0], kedua))


def test_duplikasi_fokus_identik_tidak_diterima():
    sumber = contoh()
    with pytest.raises(ValueError, match="dua fokus"):
        kontrak.KontrakSesiTuntutan((sumber.butir[0],), (sumber.fokus[0], sumber.fokus[0]))


def test_duplikat_json_pada_kontrak_valid_ditolak():
    teks = kontrak.serialisasi(contoh())
    assert kontrak.deserialisasi(teks)
    with pytest.raises(ValueError, match="duplikat"):
        kontrak.deserialisasi(teks.replace('"versi":2', '"versi":2,"versi":2'))


def test_maksimal_dua_fokus_dan_tiap_fokus_punya_probe():
    sumber = contoh()
    ketiga = replace(sumber.fokus[0], kunci=("keliling_luas_datar", "H", None))
    butir = sumber.butir + (kontrak.ButirTuntutan(3, ketiga.konteks, ketiga.kunci),)
    with pytest.raises(ValueError, match="dua fokus"):
        replace(sumber, butir=butir, fokus=sumber.fokus + (ketiga,))
    with pytest.raises(ValueError, match="tanpa butir"):
        replace(sumber, butir=(sumber.butir[0],))
    with pytest.raises(ValueError, match="konteks fokus"):
        replace(sumber, fokus=())


@pytest.mark.parametrize("teks", (
    '{}', '[]', 'null', '{', '{"versi":2,"versi":2,"butir":[],"fokus":[]}',
))
def test_json_ambigu_ditolak(teks):
    with pytest.raises(ValueError):
        kontrak.deserialisasi(teks)


@pytest.mark.parametrize("ubah", (
    lambda d: d.update(versi=1), lambda d: d.update(versi=3), lambda d: d.update(versi=True),
    lambda d: d.update(level="P6"), lambda d: d.pop("fokus"),
    lambda d: d.update(butir=[]), lambda d: d.update(fokus={}),
    lambda d: d["butir"][0].update(nomor=True),
    lambda d: d["butir"][1].update(nomor=1),
    lambda d: d["butir"][1].update(nomor=3),
    lambda d: d["butir"][0].update(internal="tambahan"),
    lambda d: d["butir"][0]["konteks"].update(profil_parameter="campuran"),
    lambda d: d["butir"][0]["konteks"].update(tuntutan_id=""),
    lambda d: d["butir"][0]["konteks"].pop("versi_rubrik"),
    lambda d: d["butir"][0].update(target_fokus="abc"),
    lambda d: d["fokus"][0].update(sumber_konfirmasi_ids=[0]),
    lambda d: d["fokus"][0].update(sumber_konfirmasi_ids=[True]),
    lambda d: d["fokus"][0].update(sumber_konfirmasi_ids=[]),
    lambda d: d["fokus"][0].update(sumber_konfirmasi_ids=[11, 11]),
    lambda d: d["fokus"][0].update(sumber_konfirmasi_ids=11),
    lambda d: d["fokus"][0].update(kunci=["asing", "K", None]),
    lambda d: d["fokus"][0].update(kunci=["keliling_luas_datar", "X", None]),
))
def test_metadata_parsial_asing_dan_tipe_salah_ditolak(ubah):
    isi = json.loads(kontrak.serialisasi(contoh()))
    ubah(isi)
    with pytest.raises(ValueError):
        kontrak.deserialisasi(json.dumps(isi))


@pytest.mark.parametrize("permukaan", ("fokus", "butir"))
@pytest.mark.parametrize("jenis", ("user_string", "equality_terlarang"))
def test_kode_fokus_wajib_teks_immutable_sebelum_dibandingkan(permukaan, jenis):
    class KodeTerlarang:
        def __eq__(self, lain):
            raise AssertionError("kode salah-tipe tidak boleh dibandingkan")

    kode = UserString("K") if jenis == "user_string" else KodeTerlarang()
    konteks = contoh().butir[0].konteks
    kunci = (konteks.template_id, kode, None)
    with pytest.raises(ValueError):
        if permukaan == "fokus":
            kontrak.FokusTuntutan(kunci, konteks, (1,))
        else:
            kontrak.ButirTuntutan(1, konteks, kunci)


@pytest.mark.parametrize("kode", ("B", "K", "H", "E", "N", "T"))
def test_kode_teks_normal_tetap_beku_dan_roundtrip(kode):
    konteks = contoh().butir[0].konteks
    fokus = kontrak.FokusTuntutan((konteks.template_id, kode, None), konteks, (3, 1))
    sumber = kontrak.KontrakSesiTuntutan(
        (kontrak.ButirTuntutan(1, konteks, fokus.kunci),), (fokus,))
    teks = kontrak.serialisasi(sumber)
    hasil = kontrak.deserialisasi(teks)
    assert hasil == sumber
    assert kontrak.serialisasi(hasil) == teks
    assert type(hasil.fokus[0].kunci[1]) is str
    with pytest.raises(FrozenInstanceError):
        hasil.fokus[0].kunci = (konteks.template_id, "X", None)


_FIELD_KONTEKS = ("template_id", "profil_parameter", "mode_representasi", "versi_rubrik", "tuntutan_id")


@pytest.mark.parametrize("field", _FIELD_KONTEKS)
@pytest.mark.parametrize("kedalaman", (500, 700))
def test_json_scalar_bersarang_ditolak_sesudah_parser_berhasil(field, kedalaman):
    isi = json.loads(kontrak.serialisasi(contoh()))
    isi["butir"][0]["konteks"][field] = "PENANDA_BERSARANG"
    teks = json.dumps(isi).replace('"PENANDA_BERSARANG"', "[" * kedalaman + "0" + "]" * kedalaman)
    # Bukan menguji catch error parser: JSON ini harus berhasil diparse dahulu.
    assert type(json.loads(teks)["butir"][0]["konteks"][field]) is list
    with pytest.raises(ValueError, match="identitas konteks"):
        kontrak.deserialisasi(teks)


@pytest.mark.parametrize("field", _FIELD_KONTEKS)
def test_constructor_scalar_siklik_ditolak_tanpa_rekursi(field):
    nilai = []
    nilai.append(nilai)
    with pytest.raises(ValueError, match="identitas konteks"):
        replace(contoh().butir[0].konteks, **{field: nilai})


@pytest.mark.parametrize("field", _FIELD_KONTEKS)
def test_scalar_salah_tipe_tidak_memanggil_deepcopy(field):
    class SalinanTerlarang:
        def __deepcopy__(self, memo):
            raise AssertionError("scalar salah-tipe tidak boleh disalin")

    with pytest.raises(ValueError, match="identitas konteks"):
        replace(contoh().butir[0].konteks, **{field: SalinanTerlarang()})


def test_tidak_menerima_container_mutable():
    sumber = contoh()
    with pytest.raises(ValueError):
        replace(sumber, butir=list(sumber.butir))
    with pytest.raises(ValueError):
        replace(sumber, fokus=list(sumber.fokus))
    with pytest.raises(ValueError):
        replace(sumber.fokus[0], kunci=list(sumber.fokus[0].kunci))
