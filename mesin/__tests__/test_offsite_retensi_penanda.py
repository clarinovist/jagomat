"""Off-site VPS pasca-tinjauan: penanda ganda aman, retensi berbatas, set sudah ada/sebagian."""
import hashlib
import json
import os
import subprocess
import time

import pytest

from offsite_kit import buat_pasangan_kunci
from offsite_lingkungan import (_lingkungan_uji, baca_penanda, jalankan, kunci,  # noqa: F401
                                lingkungan, s3)

import backup_offsite_vps as vps  # noqa: E402

HARI = 86400
NAMA = ("data.enc", "kunci.enc", "meta.json")


def _id_set(indeks: int) -> str:
    return f"2020010{indeks}-000000" if indeks < 10 else f"202001{indeks}-000000"


def _isi_set(s3, id_set: str, umur_hari: float) -> None:
    for nama in NAMA:
        s3.taruh(f"vps/{id_set}/{nama}", b"x", diubah=time.time() - umur_hari * HARI)


def _set_ada(s3) -> set:
    return {k.split("/")[1] for k in s3.objek if k.startswith("vps/")}


def _hapus(s3):
    return [k for m, k in s3.permintaan if m == "DELETE"]


# --- M1: nilai tepercaya di ringkasan dan penanda last-ok ---

def test_ringkasan_dan_penanda_memuat_mac_sha256_dan_sidik_kunci(lingkungan, capsys):
    kode, out, _ = jalankan(lingkungan, capsys)

    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    meta = json.loads(s3.objek[f"vps/{id_bundle}/meta.json"][0])
    data = s3.objek[f"vps/{id_bundle}/data.enc"][0]
    der = subprocess.run(["openssl", "pkey", "-pubin", "-in", str(lingkungan["publik"]),
                          "-outform", "DER"], check=True, capture_output=True).stdout
    ringkas = json.loads(out)
    assert kode == 0
    assert ringkas["mac"] == meta["mac"] and ringkas["sha256"] == hashlib.sha256(data).hexdigest()
    assert ringkas["kunci_publik_sha256"] == meta["kunci_publik_sha256"] == hashlib.sha256(der).hexdigest()
    assert ringkas["sudah_ada"] is False
    penanda = baca_penanda(lingkungan["penanda"])
    assert penanda["id"] == id_bundle and penanda["mac"] == ringkas["mac"]
    assert penanda["sha256"] == ringkas["sha256"] and penanda["kunci"] == ringkas["kunci_publik_sha256"]


def test_kunci_publik_rsa_2048_ditolak_sebelum_permintaan_apa_pun(lingkungan, capsys, tmp_path):
    (tmp_path / "k").mkdir()
    lingkungan["publik"] = buat_pasangan_kunci(tmp_path / "k", bit=2048)[1]

    kode, out, err = jalankan(lingkungan, capsys)

    assert kode == 1 and out == "" and "3072" in err
    assert lingkungan["s3"].permintaan == []


# --- M2: penanda ditulis lewat berkas sementara acak, tidak mengikuti symlink ---

@pytest.mark.parametrize("nama_penanda", ["last-ok", "retention-ok"])
def test_penanda_tidak_mengikuti_symlink_di_nama_sementara_lama(lingkungan, capsys, tmp_path, nama_penanda):
    korban = tmp_path / "korban.txt"
    korban.write_text("JANGAN-DITIMPA")
    penanda = lingkungan["penanda"]
    target = penanda if nama_penanda == "last-ok" else penanda.with_name("offsite-vps.retention-ok")
    (target.parent / f".{target.name}.tmp-{os.getpid()}").symlink_to(korban)

    kode, _, _ = jalankan(lingkungan, capsys)

    assert kode == 0 and korban.read_text() == "JANGAN-DITIMPA"
    assert baca_penanda(target)["id"] == lingkungan["bundle"].name


def test_penanda_berupa_symlink_diganti_bukan_diikuti(lingkungan, capsys, tmp_path):
    korban = tmp_path / "korban.txt"
    korban.write_text("JANGAN-DITIMPA")
    lingkungan["penanda"].unlink()
    lingkungan["penanda"].symlink_to(korban)

    kode, _, _ = jalankan(lingkungan, capsys)

    assert kode == 0 and korban.read_text() == "JANGAN-DITIMPA"
    assert not lingkungan["penanda"].is_symlink()
    assert baca_penanda(lingkungan["penanda"])["id"] == lingkungan["bundle"].name


def test_penanda_mode_0644_dan_tanpa_sisa_berkas_sementara(lingkungan, capsys):
    kode, _, _ = jalankan(lingkungan, capsys)

    folder = lingkungan["penanda"].parent
    assert kode == 0 and oct(lingkungan["penanda"].stat().st_mode & 0o777) == "0o644"
    assert sorted(p.name for p in folder.iterdir()) == ["offsite-vps.retention-ok", "offsite.last-ok"]


# --- M3: retensi berbatas ---

def test_simpan_minimal_menjaga_set_terbaru_walau_semuanya_kedaluwarsa(lingkungan, capsys):
    s3 = lingkungan["s3"]
    for i in range(1, 10):
        _isi_set(s3, _id_set(i), 100)

    kode, out, _ = jalankan(lingkungan, capsys)

    # 9 set tua + set baru = 10 set lengkap; 7 terbaru dijaga -> hanya 3 tertua boleh hilang.
    assert kode == 0 and json.loads(out)["terhapus"] == 9
    assert _set_ada(s3) == {_id_set(i) for i in range(4, 10)} | {lingkungan["bundle"].name}


def test_jam_vps_salah_60_hari_tidak_menghapus_hampir_semuanya(lingkungan, capsys, monkeypatch):
    s3 = lingkungan["s3"]
    for i in range(1, 10):
        _isi_set(s3, _id_set(i), 5)
    asli = time.time
    monkeypatch.setattr(vps.time, "time", lambda: asli() + 60 * HARI)

    kode, _, _ = jalankan(lingkungan, capsys, "--umur-maks-jam", "100000")

    assert kode == 0
    assert len(_set_ada(s3)) >= 7  # sebelumnya 8 dari 9 set lama terhapus


def test_kandidat_melebihi_hapus_maks_keluar_kode_3_tanpa_menghapus_apa_pun(lingkungan, capsys):
    s3 = lingkungan["s3"]
    for i in range(1, 15):
        _isi_set(s3, _id_set(i), 100)
    sebelum = sorted(s3.objek)

    kode, out, err = jalankan(lingkungan, capsys)

    assert kode == 3 and _hapus(s3) == [] and sorted(s3.objek) == sorted(sebelum + [
        f"vps/{lingkungan['bundle'].name}/{n}" for n in NAMA])
    assert "hapus-maks" in err and "terunggah" in err and "retensi gagal" in err
    assert json.loads(out)["retensi"] == "gagal"
    assert baca_penanda(lingkungan["penanda"])["id"] == lingkungan["bundle"].name
    assert not lingkungan["penanda"].with_name("offsite-vps.retention-ok").exists()


def test_hapus_maks_dapat_diatur(lingkungan, capsys):
    s3 = lingkungan["s3"]
    for i in range(1, 15):
        _isi_set(s3, _id_set(i), 100)

    kode, out, _ = jalankan(lingkungan, capsys, "--hapus-maks", "8")

    assert kode == 0 and json.loads(out)["terhapus"] == 24  # 8 set x 3 objek
    assert len(_set_ada(s3)) == 7


def test_set_baru_tidak_pernah_dihapus_walau_jam_membuatnya_tampak_kedaluwarsa(lingkungan, capsys, monkeypatch):
    asli = time.time
    monkeypatch.setattr(vps.time, "time", lambda: asli() + 60 * HARI)

    kode, _, _ = jalankan(lingkungan, capsys, "--umur-maks-jam", "100000", "--retensi-hari", "1",
                          "--simpan-minimal", "1")

    assert kode == 0 and _set_ada(lingkungan["s3"]) == {lingkungan["bundle"].name}


@pytest.mark.parametrize("opsi", ["--simpan-minimal", "--hapus-maks"])
def test_batas_retensi_minimal_satu(lingkungan, capsys, opsi):
    kode, _, err = jalankan(lingkungan, capsys, opsi, "0")

    assert kode == 1 and opsi.lstrip("-") in err and lingkungan["s3"].permintaan == []


def test_retention_ok_ditulis_hanya_bila_retensi_sukses(lingkungan, capsys):
    s3 = lingkungan["s3"]
    _isi_set(s3, _id_set(1), 100)
    retensi_ok = lingkungan["penanda"].with_name("offsite-vps.retention-ok")
    retensi_ok.write_text("lama 00000000-000000\n")
    s3.gagal[("DELETE", f"vps/{_id_set(1)}/data.enc")] = 500

    kode, out, err = jalankan(lingkungan, capsys, "--simpan-minimal", "1")

    assert kode == 3 and "retensi gagal" in err
    assert retensi_ok.read_text() == "lama 00000000-000000\n"
    assert baca_penanda(lingkungan["penanda"])["id"] == lingkungan["bundle"].name
    s3.gagal.clear()
    kode, out, _ = jalankan(lingkungan, capsys, "--simpan-minimal", "1")
    assert kode == 0 and baca_penanda(retensi_ok)["terhapus"] == "3"


def test_retention_ok_mencatat_jumlah_terhapus(lingkungan, capsys):
    _isi_set(lingkungan["s3"], _id_set(1), 100)

    kode, _, _ = jalankan(lingkungan, capsys, "--simpan-minimal", "1")

    penanda = baca_penanda(lingkungan["penanda"].with_name("offsite-vps.retention-ok"))
    assert kode == 0 and penanda["terhapus"] == "3" and penanda["id"] == lingkungan["bundle"].name


def test_retention_ok_bisa_diarahkan_dengan_opsi(lingkungan, capsys, tmp_path):
    tujuan = tmp_path / "lain" / "retensi.ok"

    kode, _, _ = jalankan(lingkungan, capsys, "--penanda-retensi", str(tujuan))

    assert kode == 0 and tujuan.is_file()
    assert not lingkungan["penanda"].with_name("offsite-vps.retention-ok").exists()


# --- M4: run ulang pada id yang sama ---

def test_set_sudah_lengkap_dilewati_dan_mac_penanda_dipertahankan(lingkungan, capsys):
    s3 = lingkungan["s3"]
    jalankan(lingkungan, capsys)
    pertama = baca_penanda(lingkungan["penanda"])
    objek_pertama = dict(s3.objek)
    s3.permintaan.clear()

    kode, out, _ = jalankan(lingkungan, capsys)

    assert kode == 0 and [m for m, _ in s3.permintaan if m in ("PUT", "DELETE")] == []
    assert s3.objek == objek_pertama
    ringkas = json.loads(out)
    assert ringkas["sudah_ada"] is True and ringkas["ok"] is True
    assert ringkas["mac"] == pertama["mac"] and ringkas["sha256"] == pertama["sha256"]
    kedua = baca_penanda(lingkungan["penanda"])
    assert kedua["id"] == pertama["id"] and kedua["mac"] == pertama["mac"]
    assert kedua["kunci"] == pertama["kunci"]


def test_set_ada_tanpa_riwayat_penanda_tidak_diberi_mac_palsu(lingkungan, capsys):
    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    for nama in NAMA:
        s3.taruh(f"vps/{id_bundle}/{nama}", b"ditanam-pihak-lain")

    kode, out, _ = jalankan(lingkungan, capsys)

    assert kode == 0 and _puts_vps(s3) == []
    ringkas = json.loads(out)
    assert ringkas["sudah_ada"] is True and ringkas["mac"] is None and ringkas["sha256"] is None
    penanda = baca_penanda(lingkungan["penanda"])
    assert penanda["id"] == id_bundle and penanda["mac"] == "-" and penanda["sha256"] == "-"


def test_set_ada_dengan_penanda_milik_id_lain_tidak_meminjam_mac(lingkungan, capsys):
    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    for nama in NAMA:
        s3.taruh(f"vps/{id_bundle}/{nama}", b"ditanam-pihak-lain")
    lingkungan["penanda"].write_text(f"lama 20200101-000000 mac={'a' * 64} sha256={'b' * 64} "
                                     f"kunci={'c' * 64}\n")

    kode, out, _ = jalankan(lingkungan, capsys)

    assert kode == 0 and json.loads(out)["mac"] is None
    assert baca_penanda(lingkungan["penanda"])["mac"] == "-"


def _puts_vps(s3):
    return [k for m, k in s3.permintaan if m == "PUT"]


def test_set_sebagian_diunggah_ulang_dengan_meta_terakhir(lingkungan, capsys):
    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    s3.taruh(f"vps/{id_bundle}/data.enc", b"sisa-unggahan-terputus")

    kode, _, _ = jalankan(lingkungan, capsys)

    assert kode == 0
    assert _puts_vps(s3) == [f"vps/{id_bundle}/{n}" for n in NAMA]
    assert s3.objek[f"vps/{id_bundle}/data.enc"][0] != b"sisa-unggahan-terputus"
    assert sorted(k for k in s3.objek) == sorted(f"vps/{id_bundle}/{n}" for n in NAMA)


def test_set_sebagian_dengan_meta_lama_menghapus_meta_dulu_agar_tak_tampak_lengkap(lingkungan, capsys):
    s3, id_bundle = lingkungan["s3"], lingkungan["bundle"].name
    s3.taruh(f"vps/{id_bundle}/data.enc", b"lama")
    s3.taruh(f"vps/{id_bundle}/meta.json", b"{}")

    kode, _, _ = jalankan(lingkungan, capsys)

    urutan = [(m, k) for m, k in s3.permintaan if m in ("PUT", "DELETE")]
    meta = f"vps/{id_bundle}/meta.json"
    assert kode == 0 and urutan[0] == ("DELETE", meta) and urutan[-1] == ("PUT", meta)
    assert [m for m, _ in urutan].count("DELETE") == 1


def test_kunci_objek_vps_dan_akun_tidak_menerima_newline_atau_angka_unicode():
    assert vps.POLA_KUNCI_OBJEK.fullmatch("vps/20260101-000000/data.enc\n") is None
    assert vps.POLA_KUNCI_OBJEK.fullmatch("vps/٢٠٢٦٠١٠١-٠٠٠٠٠٠/data.enc") is None
    assert vps.POLA_KUNCI_OBJEK.fullmatch("vps/20260101-000000/data.enc")
    assert vps.POLA_AKUN.fullmatch("abc\n") is None


def test_direktori_bundle_berangka_unicode_tidak_dipilih(lingkungan):
    akar = lingkungan["bundle"].parent
    (akar / "٢٠٢٦٠١٠١-٠٠٠٠٠٠").mkdir()

    assert vps.pilih_bundle(akar) == lingkungan["bundle"]
