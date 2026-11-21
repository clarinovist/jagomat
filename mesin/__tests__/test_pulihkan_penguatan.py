"""Pemulihan pasca-tinjauan: keaslian terhadap sumber tepercaya, unduhan berbatas, id ketat."""
import gzip
import io
import json
import tarfile

import pytest

from offsite_kit import tulis_env
from offsite_lingkungan import (_lingkungan_uji, kunci, kunci_lain, paket, pulihkan,  # noqa: F401
                                s3, simpan_objek, unggah)
from s3_tiruan_kit import S3Tiruan

import backup_offsite_vps as vps  # noqa: E402
import offsite_kripto  # noqa: E402
import pulihkan_offsite as pulih  # noqa: E402


def _mata_mata_dekripsi(monkeypatch):
    dipanggil = []
    asli = pulih.dekripsi_data
    monkeypatch.setattr(pulih, "dekripsi_data", lambda *a, **k: (dipanggil.append(1), asli(*a, **k))[1])
    return dipanggil


def _salah(hex64: str) -> str:
    return ("0" if hex64[0] != "0" else "1") + hex64[1:]


def _pulihkan_s3(p, capsys, *tambahan, id_bundle=None):
    env = tulis_env(p["tmp"] / "baca.env")
    argv = ["--id", id_bundle or p["id"], "--env", str(env), "--endpoint", p["s3"].url,
            "--kunci-privat", str(p["privat"]), "--tujuan", str(p["tujuan"]), *tambahan]
    kode = pulih.main(argv)
    keluar = capsys.readouterr()
    return kode, keluar.out, keluar.err


# --- M1: --mac-harapan / --sha256-harapan ---

def test_nilai_harapan_benar_pulih_tanpa_stderr_dan_cetak_sidik_kunci(paket, capsys):
    kode, out, err = pulihkan(paket, capsys)

    assert kode == 0 and err == ""
    meta = json.loads((paket["dir"] / "meta.json").read_text())
    assert json.loads(out)["kunci_publik_sha256"] == meta["kunci_publik_sha256"]
    assert json.loads(out)["keaslian_terverifikasi"] is True


def test_tanpa_nilai_harapan_pulih_tetapi_beri_peringatan_ke_stderr(paket, capsys):
    kode, out, err = pulihkan(paket, capsys, harapan=False)

    assert kode == 0 and "TIDAK diverifikasi" in err and "--mac-harapan" in err
    assert json.loads(out)["keaslian_terverifikasi"] is False


@pytest.mark.parametrize("opsi", ["--mac-harapan", "--sha256-harapan"])
def test_nilai_harapan_salah_ditolak_sebelum_dekripsi(paket, capsys, monkeypatch, opsi):
    dipanggil = _mata_mata_dekripsi(monkeypatch)
    benar = paket["ringkas"]["mac" if opsi == "--mac-harapan" else "sha256"]

    kode, _, err = pulihkan(paket, capsys, opsi, _salah(benar), harapan=False)

    assert kode == 1 and "sumber tepercaya" in err
    assert not dipanggil and not paket["tujuan"].exists()


def test_set_palsu_dengan_mac_internal_sah_ditolak_bila_harapan_diberikan(tmp_path, paket, kunci, capsys):
    # Penyerang bertoken R2 + kunci publik membuat set sah lain dengan id yang sama.
    with S3Tiruan(akses=paket["s3"].akses, rahasia=paket["s3"].rahasia) as s3_palsu:
        unggah(tmp_path / "palsu", s3_palsu, kunci[1], capsys, bundle=_bundel_sama(tmp_path, paket))
        palsu = simpan_objek(s3_palsu, paket["id"], tmp_path / "unduhan-palsu")
    korban = dict(paket, dir=palsu, tujuan=tmp_path / "pulih-palsu")

    kode, _, err = pulihkan(korban, capsys)

    assert kode == 1 and "sumber tepercaya" in err and not korban["tujuan"].exists()
    kode, _, err = pulihkan(korban, capsys, harapan=False)  # tanpa harapan: celah yang didokumentasikan
    assert kode == 0 and "TIDAK diverifikasi" in err


def _bundel_sama(tmp_path, paket):
    (tmp_path / "palsu").mkdir()
    import shutil
    akar = tmp_path / "palsu" / "backup-harian"
    akar.mkdir()
    shutil.copytree(paket["bundle"], akar / paket["id"])
    return akar / paket["id"]


@pytest.mark.parametrize("opsi", ["--mac-harapan", "--sha256-harapan"])
@pytest.mark.parametrize("nilai", ["abc", "G" * 64, "a" * 64 + "\n", "A" * 64])
def test_nilai_harapan_berformat_salah_ditolak_parser(paket, opsi, nilai):
    with pytest.raises(SystemExit) as info:
        pulih.main(["--id", paket["id"], "--dari-direktori", str(paket["dir"]),
                    "--kunci-privat", str(paket["privat"]), "--tujuan", str(paket["tujuan"]),
                    opsi, nilai])

    assert info.value.code == 2


# --- L10: id divalidasi, meta dulu, unduhan berbatas ---

@pytest.mark.parametrize("id_buruk", ["../x", "20260101-000000\n", "٢٠٢٦٠١٠١-٠٠٠٠٠٠", "vps/x", ""])
def test_id_tidak_sah_ditolak_di_parser_sebelum_permintaan_apa_pun(paket, id_buruk):
    paket["s3"].permintaan.clear()
    with pytest.raises(SystemExit) as info:
        pulih.main(["--id", id_buruk, "--env", str(tulis_env(paket["tmp"] / "baca.env")),
                    "--endpoint", paket["s3"].url, "--kunci-privat", str(paket["privat"]),
                    "--tujuan", str(paket["tujuan"])])

    assert info.value.code == 2 and paket["s3"].permintaan == []


def test_meta_diunduh_lebih_dulu_dan_data_dibatasi_sebesar_ukuran_meta(paket, capsys, monkeypatch):
    panggilan = []
    asli = pulih.r2_s3.KlienR2.ambil_objek

    def awasi(self, kunci_objek, simpan_ke, **kw):
        panggilan.append((kunci_objek.rsplit("/", 1)[1], kw.get("maks_byte")))
        return asli(self, kunci_objek, simpan_ke, **kw)

    monkeypatch.setattr(pulih.r2_s3.KlienR2, "ambil_objek", awasi)

    kode, _, err = _pulihkan_s3(paket, capsys, "--mac-harapan", paket["ringkas"]["mac"])

    ukuran = json.loads((paket["dir"] / "meta.json").read_text())["ukuran"]
    assert kode == 0, err
    assert panggilan[0][0] == "meta.json" and panggilan[0][1] is not None
    assert ("data.enc", ukuran) in panggilan
    kunci_enc = [m for n, m in panggilan if n == "kunci.enc"]
    assert kunci_enc and kunci_enc[0] is not None


def test_data_lebih_besar_dari_meta_ditolak_saat_unduh(paket, capsys):
    kunci_data = f"vps/{paket['id']}/data.enc"
    isi, waktu = paket["s3"].objek[kunci_data]
    paket["s3"].objek[kunci_data] = (isi + b"\x00" * 5000, waktu)

    kode, _, err = _pulihkan_s3(paket, capsys)

    assert kode == 1 and "melebihi batas" in err and not paket["tujuan"].exists()


def test_meta_tidak_sah_menghentikan_sebelum_data_diunduh(paket, capsys):
    kunci_meta = f"vps/{paket['id']}/meta.json"
    paket["s3"].objek[kunci_meta] = (b"{}", 0)
    paket["s3"].permintaan.clear()

    kode, _, _ = _pulihkan_s3(paket, capsys)

    assert kode == 1
    assert paket["s3"].permintaan == [("GET", kunci_meta)]


def test_set_tanpa_meta_di_r2_ditolak_dengan_pesan_tidak_lengkap(paket, capsys):
    del paket["s3"].objek[f"vps/{paket['id']}/meta.json"]
    paket["s3"].permintaan.clear()

    kode, out, err = _pulihkan_s3(paket, capsys)

    assert kode == 1 and out == "" and "tidak lengkap" in err and "meta.json" in err
    assert paket["s3"].permintaan == [("GET", f"vps/{paket['id']}/meta.json")]
    assert not paket["tujuan"].exists()


def test_set_tanpa_meta_di_direktori_ditolak_dengan_pesan_tidak_lengkap(paket, capsys):
    (paket["dir"] / "meta.json").unlink()

    kode, _, err = pulihkan(paket, capsys)

    assert kode == 1 and "tidak lengkap" in err and not paket["tujuan"].exists()


# --- L11: batas byte terdekompresi sebelum membaca tar ---

def test_periksa_ukuran_terdekompresi_menolak_gzip_bomb(tmp_path):
    berkas = tmp_path / "bom.tar.gz"
    berkas.write_bytes(gzip.compress(b"\x00" * 3_000_000))

    with pytest.raises(offsite_kripto.GalatKripto, match="melebihi batas"):
        pulih.periksa_ukuran_terdekompresi(berkas, 1_000_000)
    pulih.periksa_ukuran_terdekompresi(berkas, 3_000_000)  # tepat di batas: lolos


def test_periksa_ukuran_terdekompresi_gz_rusak_jadi_galat_kripto(tmp_path):
    berkas = tmp_path / "rusak.tar.gz"
    berkas.write_bytes(b"bukan gzip sama sekali")

    with pytest.raises(offsite_kripto.GalatKripto):
        pulih.periksa_ukuran_terdekompresi(berkas, 10)


def test_bom_gzip_ditolak_sebelum_tar_dibuka(tmp_path, s3, kunci, capsys, monkeypatch):
    def tar_besar(bundle, tujuan):
        with tarfile.open(str(tujuan), "w:gz") as tar:
            info = tarfile.TarInfo(f"{bundle.name}/besar.bin")
            info.size = 3_000_000
            tar.addfile(info, io.BytesIO(b"\x00" * 3_000_000))

    with monkeypatch.context() as lokal:
        lokal.setattr(vps, "buat_tar", tar_besar)
        bundle, ringkas = unggah(tmp_path, s3, kunci[1], capsys)
    p = {"id": bundle.name, "dir": simpan_objek(s3, bundle.name, tmp_path / "u"),
         "privat": kunci[0], "tujuan": tmp_path / "pulih", "ringkas": ringkas}
    monkeypatch.setattr(pulih, "BATAS_BYTE", 1_000_000)
    dibuka = []
    asli = pulih.tarfile.open
    monkeypatch.setattr(pulih.tarfile, "open", lambda *a, **k: (dibuka.append(1), asli(*a, **k))[1])

    kode, _, err = pulihkan(p, capsys)

    assert kode == 1 and "tar" in err and "melebihi batas" in err
    assert dibuka == [] and not p["tujuan"].exists()


def test_kegagalan_hapus_direktori_kerja_dicatat_bukan_ditelan(paket, capsys, monkeypatch):
    import offsite_kerja
    from types import SimpleNamespace

    def gagal(*_a, **_k):
        raise PermissionError("/tmp/pulihkan-x/sandi.sesi")

    monkeypatch.setattr(offsite_kerja, "shutil", SimpleNamespace(rmtree=gagal))

    kode, _, err = pulihkan(paket, capsys)

    assert kode == 0 and "tidak terhapus" in err and "PermissionError" in err
    assert "sandi.sesi" not in err
