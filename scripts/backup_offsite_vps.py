#!/usr/bin/env python3
"""Off-site backup dari VPS ke Cloudflare R2, dienkripsi hibrida dengan kunci PUBLIK.

Dijalankan root di VPS oleh cron terpisah setelah backup harian, contoh baris
yang DIUSULKAN (belum dipasang; `-I` = mode terisolasi, abaikan env PYTHON* dan
direktori kerja):

    0 22 * * * root /usr/bin/python3 -I /opt/osn/backup-harian/backup_offsite_vps.py \
        >> /opt/osn/log/offsite-vps.log 2>&1

Berkas `backup_offsite_vps.py`, `offsite_kripto.py`, `offsite_kerja.py`,
`offsite_retensi.py`, `offsite_penanda.py`, `r2_s3.py`, dan `backup_harian.py`
harus dipasang berdampingan di /opt/osn/backup-harian/.

Alur: pilih bundle terbaru -> tolak bila basi atau tak lolos `validasi` -> List
`vps/<id>/`: bila ketiga objek sudah ada, LEWATI unggahan; bila hanya sebagian,
unggah ulang (meta.json terakhir) -> tar.gz dari manifest -> enkripsi AES-256 dengan
sandi sesi acak -> sandi sesi dibungkus RSA-OAEP dengan kunci publik (RSA >= 3072
bit) -> HMAC -> unggah -> verifikasi (List, ukuran sama) -> tulis penanda
`last-ok` (memuat mac, sha256, sidik kunci: sumber tepercaya untuk pemulihan) ->
retensi `vps/` -> tulis penanda `retention-ok` HANYA bila retensi sukses -> satu
baris JSON. Skrip ini TIDAK punya kode atau argumen untuk kunci privat, dan tidak
pernah menaruh rahasia di argv/env. Detail format: lihat `offsite_kripto.py`.

Keluar: 0 sukses; 1 gagal sebelum/selama unggah; 3 set baru terunggah dan
terverifikasi (penanda `last-ok` sudah ditulis) tetapi retensi gagal atau
dibatalkan karena melebihi `--hapus-maks`; `retention-ok` lama dibiarkan.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import time
from typing import Dict, List, Optional

_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.append(_DIR)

import backup_harian  # noqa: E402
import offsite_kerja  # noqa: E402
import offsite_kripto as kripto  # noqa: E402
import offsite_penanda  # noqa: E402
import offsite_retensi  # noqa: E402
import r2_s3  # noqa: E402
from offsite_kerja import buat_tar  # noqa: E402,F401  (dipanggil lewat nama modul ini)
from offsite_kripto import GalatOffsite  # noqa: E402,F401
from offsite_retensi import POLA_KUNCI_OBJEK  # noqa: E402,F401

WIB = dt.timezone(dt.timedelta(hours=7))
UMUR_MAKS_JAM = 26.0
RETENSI_HARI = 30
KUNCI_ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
MODE_LONGGAR = 0o177  # bit selain rw pemilik (maks 0600)
POLA_AKUN = re.compile(r"[A-Za-z0-9]{1,64}")
KODE_RETENSI_GAGAL = 3
ENV_UJI = "OSN_OFFSITE_UJI"
NAMA_RETENSI_OK = "offsite-vps.retention-ok"


class GalatKonfigurasi(GalatOffsite):
    pass


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle-dir", default="/opt/osn/backup-harian")
    p.add_argument("--env", default="/etc/osn/offsite-r2.env")
    p.add_argument("--kunci-publik", default="/etc/osn/offsite-publik.pem")
    p.add_argument("--penanda", default="/opt/osn/log/offsite-vps.last-ok")
    p.add_argument("--penanda-retensi", help=f"bawaan: {NAMA_RETENSI_OK} di samping --penanda")
    p.add_argument("--umur-maks-jam", type=float, default=UMUR_MAKS_JAM)
    p.add_argument("--retensi-hari", type=int, default=RETENSI_HARI)
    p.add_argument("--simpan-minimal", type=int, default=offsite_retensi.SIMPAN_MINIMAL,
                   help="set lengkap terbaru yang selalu dijaga apa pun umurnya")
    p.add_argument("--hapus-maks", type=int, default=offsite_retensi.HAPUS_MAKS,
                   help="batas set dihapus per run; lebih dari itu: kode 3, tanpa hapus")
    p.add_argument("--endpoint", help="timpa endpoint R2 (untuk tes)")
    p.add_argument("--tmp-dir", help="induk direktori kerja sementara (bawaan: tmp sistem)")
    p.add_argument("--openssl", default="openssl")
    p.add_argument("--uji-lewati-pemilik-env", action="store_true",
                   help=f"HANYA untuk tes (wajib env {ENV_UJI}=1): lewati cek pemilik root")
    return p


def urai_env(teks: str) -> Dict[str, str]:
    nilai = {}
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, isi = baris.partition("=")
        nilai[kunci.strip()] = isi.strip().strip("'\"")
    return nilai


def muat_env(path, *, lewati_pemilik: bool = False) -> Dict[str, str]:
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as galat:
        raise GalatKonfigurasi("berkas env tidak bisa dibuka (tidak ada atau symlink)") from galat
    with os.fdopen(fd, "r", encoding="utf-8") as berkas:
        info = os.fstat(berkas.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise GalatKonfigurasi("berkas env bukan berkas biasa")
        if not lewati_pemilik and info.st_uid != 0:
            raise GalatKonfigurasi("berkas env harus milik root")
        if info.st_mode & MODE_LONGGAR:
            raise GalatKonfigurasi("mode berkas env terlalu longgar (maksimal 0600)")
        nilai = urai_env(berkas.read())
    kosong = [k for k in KUNCI_ENV if not nilai.get(k)]
    if kosong:
        raise GalatKonfigurasi("kunci env kosong atau tidak ada: " + ", ".join(kosong))
    if not POLA_AKUN.fullmatch(nilai["R2_ACCOUNT_ID"]):
        raise GalatKonfigurasi("R2_ACCOUNT_ID tidak sah")
    return {k: nilai[k] for k in KUNCI_ENV}


def periksa_kunci_publik(path, openssl: str = "openssl") -> str:
    """Tolak kunci privat/non-RSA/<3072 bit; kembalikan sidik jari SHA-256 (DER)."""
    try:
        teks = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as galat:
        raise GalatKonfigurasi("kunci publik tidak terbaca") from galat
    if "PRIVATE KEY" in teks:
        raise GalatKonfigurasi("berkas kunci publik ternyata kunci privat; ditolak")
    if "-----BEGIN PUBLIC KEY-----" not in teks:
        raise GalatKonfigurasi("berkas bukan PEM kunci publik")
    try:
        return kripto.validasi_kunci_publik(openssl, path)
    except kripto.GalatKripto as galat:
        raise GalatKonfigurasi(f"kunci publik tidak memenuhi syarat: {galat}") from galat


def epoch_id(id_bundle: str) -> float:
    waktu = dt.datetime.strptime(id_bundle, "%Y%m%d-%H%M%S").replace(tzinfo=WIB)
    return waktu.timestamp()


def pilih_bundle(akar: Path) -> Path:
    try:
        kandidat = sorted((p for p in akar.iterdir() if p.is_dir() and not p.is_symlink()
                           and kripto.POLA_ID.fullmatch(p.name)), key=lambda p: p.name)
    except OSError as galat:
        raise GalatOffsite("direktori bundle tidak terbaca") from galat
    if not kandidat:
        raise GalatOffsite("tidak ada bundle backup harian")
    return kandidat[-1]


def periksa_umur(id_bundle: str, sekarang: float, umur_maks_jam: float) -> None:
    umur_jam = (sekarang - epoch_id(id_bundle)) / 3600
    if umur_jam > umur_maks_jam:
        raise GalatOffsite(f"bundle {id_bundle} lebih tua dari {umur_maks_jam:g} jam")


def validasi_bundle(bundle: Path) -> None:
    try:
        manifest = backup_harian.validasi(bundle)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as galat:
        raise GalatOffsite(f"validasi bundle gagal: {type(galat).__name__}") from galat
    if manifest["id"] != bundle.name:
        raise GalatOffsite("validasi bundle gagal: id manifest berbeda dari nama direktori")


def enkripsi_paket(openssl: str, publik: Path, bundle: Path, kerja: Path, sidik_kunci: str):
    """Kembalikan ({nama objek: path}, meta)."""
    tar, data, kunci = kerja / "bundle.tar.gz", kerja / "data.enc", kerja / "kunci.enc"
    buat_tar(bundle, tar)
    sandi = kripto.bangkitkan_sandi()
    berkas_sandi = kripto.tulis_privat(kerja, "sandi.sesi", sandi.encode("ascii"))
    kripto.jalankan_openssl(openssl, [
        "enc", "-aes-256-cbc", "-pbkdf2", "-iter", str(kripto.ITERASI), "-md", "sha256",
        "-salt", "-pass", f"file:{berkas_sandi}", "-in", str(tar), "-out", str(data)])
    tar.unlink()
    kripto.jalankan_openssl(openssl, [
        "pkeyutl", "-encrypt", "-pubin", "-inkey", str(publik),
        "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
        "-pkeyopt", "rsa_mgf1_md:sha256", "-in", str(berkas_sandi), "-out", str(kunci)])
    meta = kripto.bangun_meta(bundle.name, data.stat().st_size, kripto.sha256_berkas(data),
                              kripto.hitung_mac(sandi, bundle.name, data, sidik_kunci), sidik_kunci)
    berkas_meta = kripto.tulis_privat(kerja, "meta.json",
                                      (json.dumps(meta, sort_keys=True) + "\n").encode("utf-8"))
    berkas_sandi.unlink()
    return {"data.enc": data, "kunci.enc": kunci, "meta.json": berkas_meta}, meta


def objek_yang_ada(klien, id_bundle: str) -> frozenset:
    awalan = f"{kripto.PREFIKS}{id_bundle}/"
    return frozenset(o.kunci[len(awalan):] for o in klien.daftar_objek(awalan))


def unggah_dan_verifikasi(klien, id_bundle: str, berkas: Dict[str, Path],
                          ada: frozenset = frozenset()) -> None:
    awalan = f"{kripto.PREFIKS}{id_bundle}/"
    if "meta.json" in ada:  # set sebagian: buat tampak tak lengkap selama ditimpa
        klien.hapus_objek(awalan + "meta.json")
    for nama in kripto.NAMA_OBJEK:  # meta.json terakhir: penanda set lengkap
        klien.put_objek(awalan + nama, berkas[nama])
    terlihat = {o.kunci: o.ukuran for o in klien.daftar_objek(awalan)}
    for nama in kripto.NAMA_OBJEK:
        if terlihat.get(awalan + nama) != berkas[nama].stat().st_size:
            raise GalatOffsite(f"verifikasi unggahan gagal: {nama}")


def _buat_klien(a, kredensial) -> r2_s3.KlienR2:
    endpoint = a.endpoint or f"https://{kredensial['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return r2_s3.KlienR2(endpoint, kredensial["R2_BUCKET"], kredensial["R2_ACCESS_KEY_ID"],
                         kredensial["R2_SECRET_ACCESS_KEY"])


def _periksa_argumen(a) -> None:
    for nama, nilai in (("retensi-hari", a.retensi_hari), ("simpan-minimal", a.simpan_minimal),
                        ("hapus-maks", a.hapus_maks)):
        if nilai < 1:
            raise GalatOffsite(f"{nama} minimal 1")
    if a.uji_lewati_pemilik_env and os.environ.get(ENV_UJI) != "1":
        raise GalatOffsite(f"--uji-lewati-pemilik-env hanya untuk tes (butuh env {ENV_UJI}=1)")


def _pastikan_terunggah(a, klien, bundle: Path, sidik_kunci: str) -> Dict:
    """Unggah set baru; set yang sudah lengkap dilewati. Kembalikan nilai tepercaya set ini."""
    ada = objek_yang_ada(klien, bundle.name)
    if set(kripto.NAMA_OBJEK) <= ada:
        return {"sudah_ada": True}
    kerja = Path(tempfile.mkdtemp(prefix="offsite-", dir=a.tmp_dir))
    try:
        berkas, meta = enkripsi_paket(a.openssl, Path(a.kunci_publik), bundle, kerja, sidik_kunci)
        unggah_dan_verifikasi(klien, bundle.name, berkas, ada)
    finally:
        offsite_kerja.hapus_kerja(kerja)
    return {"sudah_ada": False, "ukuran": meta["ukuran"], "mac": meta["mac"],
            "sha256": meta["sha256"], "kunci_publik_sha256": meta["kunci_publik_sha256"]}


def _nilai_tepercaya(hasil: Dict, id_bundle: str, penanda: Path) -> Dict:
    """Nilai mac/sha256/sidik kunci set ini; untuk set yang dilewati hanya dari penanda lama
    BERID SAMA (tidak pernah dari meta.json di R2, yang tidak tepercaya)."""
    if not hasil["sudah_ada"]:
        return hasil
    lama = offsite_penanda.baca_penanda(penanda)
    if lama is None or lama["id"] != id_bundle:
        lama = {}

    def ambil(kunci: str) -> Optional[str]:
        nilai = lama.get(kunci)
        return None if nilai in (None, offsite_penanda.TANPA_NILAI) else nilai

    return {**hasil, "ukuran": None, "mac": ambil("mac"), "sha256": ambil("sha256"),
            "kunci_publik_sha256": ambil("kunci")}


def _tulis_last_ok(path: Path, id_bundle: str, sekarang: float, nilai: Dict) -> None:
    tanda = offsite_penanda.TANPA_NILAI
    bidang = {"mac": nilai["mac"] or tanda, "sha256": nilai["sha256"] or tanda,
              "kunci": nilai["kunci_publik_sha256"] or tanda}
    offsite_penanda.tulis_penanda(path, offsite_penanda.baris_penanda(
        backup_harian._stempel(int(sekarang)), id_bundle, bidang))


def _jalankan_retensi(a, klien, id_bundle: str, sekarang: float):
    """Kembalikan (jumlah terhapus, None) atau (None, alasan gagal)."""
    try:
        return offsite_retensi.terapkan_retensi(klien, id_bundle, sekarang, a.retensi_hari,
                                                a.simpan_minimal, a.hapus_maks), None
    except (r2_s3.GalatS3, offsite_retensi.GalatRetensi) as galat:
        return None, str(galat)


def _proses(a, rahasia: List[str]) -> int:
    _periksa_argumen(a)
    kredensial = muat_env(a.env, lewati_pemilik=a.uji_lewati_pemilik_env)
    rahasia.extend(kredensial.values())
    sidik_kunci = periksa_kunci_publik(a.kunci_publik, a.openssl)
    sekarang = time.time()
    sisa = offsite_kerja.sapu_sisa(a.tmp_dir or tempfile.gettempdir(), sekarang)
    if sisa:
        print(f"peringatan: {sisa} direktori sisa run sebelumnya dibersihkan", file=sys.stderr)
    bundle = pilih_bundle(Path(a.bundle_dir))
    periksa_umur(bundle.name, sekarang, a.umur_maks_jam)
    validasi_bundle(bundle)
    klien = _buat_klien(a, kredensial)
    penanda = Path(a.penanda)
    nilai = _nilai_tepercaya(_pastikan_terunggah(a, klien, bundle, sidik_kunci),
                             bundle.name, penanda)
    _tulis_last_ok(penanda, bundle.name, sekarang, nilai)
    terhapus, alasan = _jalankan_retensi(a, klien, bundle.name, sekarang)
    ringkasan = {"id": bundle.name, "ok": alasan is None, "terhapus": terhapus or 0,
                 "sudah_ada": nilai["sudah_ada"], "ukuran": nilai["ukuran"], "mac": nilai["mac"],
                 "sha256": nilai["sha256"], "kunci_publik_sha256": nilai["kunci_publik_sha256"]}
    if alasan is not None:
        print("galat: set baru terunggah dan terverifikasi (penanda last-ok sudah diperbarui), "
              "tetapi retensi gagal: " + _samarkan(alasan, rahasia), file=sys.stderr)
        print(json.dumps({**ringkasan, "retensi": "gagal"}, sort_keys=True))
        return KODE_RETENSI_GAGAL
    retensi_ok = Path(a.penanda_retensi) if a.penanda_retensi else penanda.with_name(NAMA_RETENSI_OK)
    offsite_penanda.tulis_penanda(retensi_ok, offsite_penanda.baris_penanda(
        backup_harian._stempel(int(sekarang)), bundle.name, {"terhapus": str(terhapus)}))
    print(json.dumps(ringkasan, sort_keys=True))
    return 0


def _samarkan(pesan: str, rahasia: List[str]) -> str:
    for nilai in rahasia:
        pesan = pesan.replace(nilai, "***")
    return pesan


def main(argv: Optional[List[str]] = None) -> int:
    a = buat_parser().parse_args(argv)
    rahasia: List[str] = []
    try:
        return _proses(a, rahasia)
    except (GalatOffsite, kripto.GalatKripto, r2_s3.GalatS3, ValueError, OSError) as galat:
        print("galat: " + _samarkan(str(galat), rahasia), file=sys.stderr)
    except Exception as galat:  # noqa: BLE001 - jangan bocorkan rahasia lewat traceback
        print("galat tak terduga: " + type(galat).__name__ + ": "
              + _samarkan(str(galat), rahasia), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
