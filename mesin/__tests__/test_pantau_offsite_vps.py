"""Monitor off-site VPS (jalan di Mac): alert bila penanda basi, salah kunci, atau VPS tak terjangkau.

Jadwal dan ambang saling bergantung (lihat docstring skrip): monitor jalan pagi, ambang 26 jam.
ssh diganti perintah tiruan; tidak ada jaringan atau VPS sungguhan.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pantau_offsite_vps as pantau  # noqa: E402

SKRIP = _SCRIPTS / "pantau_offsite_vps.py"
KUNCI = "a" * 64
MAC = "b" * 64
SHA = "c" * 64


def _lastok(stempel="20261121-150757", id_="20261121-140623", kunci=KUNCI):
    return f"{stempel} {id_} mac={MAC} sha256={SHA} kunci={kunci}\n"


def _retensi(stempel="20261121-150757", id_="20261121-140623"):
    return f"{stempel} {id_} terhapus=0\n"


def _nilai(lastok=None, retensi=None, sekarang="20261122-080000", kunci=KUNCI, umur=26.0):
    return pantau.nilai(
        _lastok() if lastok is None else lastok,
        _retensi() if retensi is None else retensi,
        sekarang, kunci, umur)


# ---- fungsi murni -------------------------------------------------------------------------

def test_segar_tanpa_masalah():
    assert _nilai() == []


def test_stempel_basi_dilaporkan():
    # Pagi 08:00 tanggal 23: stempel terakhir 15:07 tanggal 21 = ~41 jam.
    masalah = _nilai(sekarang="20261123-080000")
    assert any("last-ok" in m and "basi" in m for m in masalah)


def test_id_bundle_basi_dengan_stempel_segar_dilaporkan():
    # Run ulang `sudah_ada` menyegarkan stempel meski bundle kemarin: backup harian mungkin gagal.
    masalah = _nilai(lastok=_lastok(stempel="20261122-060000", id_="20261120-214501"),
                     retensi=_retensi(stempel="20261122-060000", id_="20261120-214501"))
    assert any("bundle" in m and "basi" in m for m in masalah)
    assert not any("last-ok" in m and "stempel" in m for m in masalah)


def test_kunci_beda_dilaporkan():
    masalah = _nilai(lastok=_lastok(kunci="d" * 64))
    assert any("kunci" in m for m in masalah)


def test_kunci_tak_ada_di_penanda_dilaporkan():
    baris = f"20261121-150757 20261121-140623 mac={MAC} sha256={SHA}\n"
    assert any("kunci" in m for m in _nilai(lastok=baris))


def test_retensi_id_berbeda_dilaporkan_sebagai_retensi_tertinggal():
    masalah = _nilai(retensi=_retensi(id_="20261120-214501"))
    assert any("retensi" in m for m in masalah)
    assert not any("last-ok" in m for m in masalah)


def test_retensi_basi_dilaporkan():
    masalah = _nilai(retensi=_retensi(stempel="20261119-000000"))
    assert any("retensi" in m and "basi" in m for m in masalah)


@pytest.mark.parametrize("isi", ["", "\n", "bukan-penanda\n", "20261121-150757\n",
                                 "tanggal 20261121-140623 kunci=x\n"])
def test_lastok_kosong_atau_rusak_dilaporkan(isi):
    masalah = _nilai(lastok=isi)
    assert any("last-ok" in m for m in masalah)


@pytest.mark.parametrize("isi", ["", "rusak\n"])
def test_retensi_kosong_atau_rusak_dilaporkan(isi):
    assert any("retensi" in m for m in _nilai(retensi=isi))


def test_stempel_di_masa_depan_dilaporkan_sebagai_jam_tak_wajar():
    masalah = _nilai(lastok=_lastok(stempel="20261125-000000"))
    assert any("masa depan" in m or "jam" in m for m in masalah)


def test_batas_umur_tepat_tidak_dilaporkan_dan_lewat_sedikit_dilaporkan():
    # Stempel dan id sama-sama 15:07:57; 26 jam persis -> 17:07:57 hari berikutnya.
    lastok = _lastok(id_="20261121-150757")
    retensi = _retensi(id_="20261121-150757")
    assert _nilai(lastok=lastok, retensi=retensi, sekarang="20261122-170757") == []
    assert _nilai(lastok=lastok, retensi=retensi, sekarang="20261122-170758") != []


def test_hitungan_jadwal_pagi_menangkap_satu_malam_gagal():
    # Normal: run 22:00 sukses, cek 08:00 -> ~10 jam: tenang.
    tenang = _nilai(lastok=_lastok(stempel="20261121-220005", id_="20261121-214501"),
                    retensi=_retensi(stempel="20261121-220005", id_="20261121-214501"),
                    sekarang="20261122-080000")
    assert tenang == []
    # Satu malam gagal: cek 08:00 hari berikutnya -> ~34 jam: alert.
    gagal = _nilai(lastok=_lastok(stempel="20261121-220005", id_="20261121-214501"),
                   retensi=_retensi(stempel="20261121-220005", id_="20261121-214501"),
                   sekarang="20261123-080000")
    assert gagal != []


# ---- parsing keluaran ssh ------------------------------------------------------------------

def test_urai_keluaran_ssh_lengkap():
    keluaran = (f"20261122-080000\n@@last-ok\n{_lastok()}@@retention-ok\n{_retensi()}@@end\n")
    sekarang, lastok, retensi = pantau.urai_keluaran(keluaran)
    assert sekarang == "20261122-080000"
    assert lastok == _lastok()
    assert retensi == _retensi()


def test_urai_keluaran_terpotong_ditolak():
    with pytest.raises(pantau.GalatPantau):
        pantau.urai_keluaran("20261122-080000\n@@last-ok\n")


def test_urai_keluaran_berkas_hilang_memberi_bagian_kosong():
    sekarang, lastok, retensi = pantau.urai_keluaran(
        "20261122-080000\n@@last-ok\n@@retention-ok\n@@end\n")
    assert (lastok, retensi) == ("", "")


def test_sidik_jari_kunci_publik_dari_pem(tmp_path):
    import base64
    import hashlib
    der = b"\x30\x82" + bytes(range(40))
    isi = base64.b64encode(der).decode()
    pem = tmp_path / "pub.pem"
    pem.write_text(f"-----BEGIN PUBLIC KEY-----\n{isi}\n-----END PUBLIC KEY-----\n")
    assert pantau.sidik_jari_pem(pem) == hashlib.sha256(der).hexdigest()


def test_sidik_jari_pem_menolak_kunci_privat(tmp_path):
    pem = tmp_path / "priv.pem"
    pem.write_text("-----BEGIN ENCRYPTED PRIVATE KEY-----\nAAAA\n-----END ENCRYPTED PRIVATE KEY-----\n")
    with pytest.raises(pantau.GalatPantau):
        pantau.sidik_jari_pem(pem)


# ---- proses penuh (ssh tiruan) -------------------------------------------------------------

def _siapkan(tmp_path, ssh_isi, kunci_pem=True):
    ssh = tmp_path / "ssh"
    ssh.write_text("#!/bin/bash\n" + ssh_isi, encoding="utf-8")
    ssh.chmod(0o755)
    alert = tmp_path / "alert"
    alert.write_text(f'#!/bin/bash\necho "$1" >> "{tmp_path}/alert.log"\n', encoding="utf-8")
    alert.chmod(0o755)
    pem = tmp_path / "pub.pem"
    if kunci_pem:
        import base64
        pem.write_text("-----BEGIN PUBLIC KEY-----\n"
                       + base64.b64encode(b"kunci-publik-tes").decode()
                       + "\n-----END PUBLIC KEY-----\n")
    env = {
        "HOME": str(tmp_path), "PATH": os.environ["PATH"],
        "OSN_PANTAU_SSH": str(ssh), "OSN_ALERT": str(alert),
        "OSN_PANTAU_KUNCI_PUBLIK": str(pem),
    }
    return env, tmp_path / "alert.log"


def _jalankan(env):
    return subprocess.run([sys.executable, str(SKRIP)], env=env, capture_output=True,
                          text=True, timeout=30)


def _kunci_tes():
    import hashlib
    return hashlib.sha256(b"kunci-publik-tes").hexdigest()


def test_proses_ok_tanpa_alert(tmp_path):
    sekarang_pasti = "20261122-080000"
    badan = (f"{sekarang_pasti}\\n@@last-ok\\n"
             f"20261121-220005 20261121-214501 mac={MAC} sha256={SHA} kunci={_kunci_tes()}\\n"
             f"@@retention-ok\\n20261121-220005 20261121-214501 terhapus=0\\n@@end\\n")
    env, log = _siapkan(tmp_path, f'printf "{badan}"\n')
    hasil = _jalankan(env)
    assert hasil.returncode == 0, hasil.stderr
    assert not log.exists()
    assert hasil.stdout.startswith("ok")


def test_proses_ssh_gagal_mengirim_alert_dan_keluar_nonnol(tmp_path):
    env, log = _siapkan(tmp_path, 'echo "ssh: connect timed out" >&2\nexit 255\n')
    hasil = _jalankan(env)
    assert hasil.returncode != 0
    assert log.exists() and "GAGAL" in log.read_text()


def test_proses_penanda_basi_mengirim_alert_tanpa_membocorkan_mac(tmp_path):
    badan = ("20261125-080000\\n@@last-ok\\n"
             f"20261121-220005 20261121-214501 mac={MAC} sha256={SHA} kunci={_kunci_tes()}\\n"
             "@@retention-ok\\n20261121-220005 20261121-214501 terhapus=0\\n@@end\\n")
    env, log = _siapkan(tmp_path, f'printf "{badan}"\n')
    hasil = _jalankan(env)
    assert hasil.returncode != 0
    teks = log.read_text()
    assert "basi" in teks
    assert MAC not in teks and SHA not in teks


def test_proses_kunci_publik_lokal_hilang_mengirim_alert(tmp_path):
    env, log = _siapkan(tmp_path, 'printf "x"\n', kunci_pem=False)
    hasil = _jalankan(env)
    assert hasil.returncode != 0
    assert log.exists()


def test_proses_keluaran_ssh_sampah_mengirim_alert(tmp_path):
    env, log = _siapkan(tmp_path, 'echo "halo"\n')
    hasil = _jalankan(env)
    assert hasil.returncode != 0
    assert log.exists()
