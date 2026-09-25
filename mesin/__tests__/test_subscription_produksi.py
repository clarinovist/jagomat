"""Runtime produksi dan readiness artefak diuji dengan berkas/DB sintetis."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import admin_store
import admin_subscription
import midtrans_contract as m
import subscription as d
import subscription_produksi as prod

T0 = 1800000000
KUNCI = "Mid-server-SINTETIS-bukan-credential"
MERCHANT = "M_SINTETIS"


def tulis(path, isi, *, mode=0o600):
    path.write_bytes(isi if type(isi) is bytes else isi.encode())
    os.chmod(path, mode)
    return path


def rahasia(*, kunci=KUNCI, merchant=MERCHANT):
    return "merchant=%s\nserver_key=%s\n" % (merchant, kunci)


def artefak(**ubah):
    data = {"versi": 1, "revisi": "a" * 40, "digest": "sha256:" + "b" * 64,
            "kontrak": "c" * 64, "pasangan_terverifikasi": True, "kompatibel": True,
            "mode": "migrasi"}
    data.update(ubah)
    return json.dumps(data)


@pytest.fixture
def berkas(tmp_path):
    return {"rahasia": tulis(tmp_path / "rahasia.conf", rahasia()),
            "recovery": tulis(tmp_path / "recovery.json", artefak()),
            "tmp": tmp_path}


def test_runtime_dari_konfigurasi_tepercaya(berkas, monkeypatch):
    monkeypatch.setattr(prod, "permukaan_callback", lambda: True)
    r = prod.runtime(path_rahasia=berkas["rahasia"], path_recovery=berkas["recovery"])
    assert isinstance(r, admin_subscription.RuntimePembayaran)
    assert r.config.lingkungan == "production" and r.config.merchant == MERCHANT
    assert callable(r.transport) and KUNCI not in repr(r)
    assert r.kesiapan == {"provider_produksi": True, "callback": True,
                          "recovery": True, "kebijakan": False}


def test_tanpa_berkas_rahasia_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(prod, "permukaan_callback", lambda: True)
    assert prod.runtime(path_rahasia=tmp_path / "tidak-ada.conf",
                        path_recovery=tmp_path / "tidak-ada.json") is None
    server = SimpleNamespace()
    assert prod.pasang(server, path_rahasia=tmp_path / "tidak-ada.conf",
                       path_recovery=tmp_path / "tidak-ada.json") is False
    assert getattr(server, "pembayaran_runtime", None) is None


@pytest.mark.parametrize("jenis", ["symlink", "perm", "sandbox", "rusak"])
def test_rahasia_tidak_sah_tidak_memberi_runtime(tmp_path, jenis, monkeypatch):
    monkeypatch.setattr(prod, "permukaan_callback", lambda: True)
    asli = tulis(tmp_path / "asli.conf", rahasia(kunci="SB-Mid-server-X" if jenis == "sandbox" else KUNCI))
    path = asli
    if jenis == "symlink":
        path = tmp_path / "tautan.conf"
        path.symlink_to(asli)
    elif jenis == "perm":
        os.chmod(asli, 0o644)
    elif jenis == "rusak":
        tulis(asli, "merchant=M\n")
    assert prod.runtime(path_rahasia=path, path_recovery=tmp_path / "x.json") is None


def test_pasang_sekali_dan_menolak_ganda(berkas, monkeypatch):
    monkeypatch.setattr(prod, "permukaan_callback", lambda: True)
    server = SimpleNamespace()
    assert prod.pasang(server, path_rahasia=berkas["rahasia"], path_recovery=berkas["recovery"]) is True
    assert isinstance(server.pembayaran_runtime, admin_subscription.RuntimePembayaran)
    with pytest.raises(RuntimeError):
        prod.pasang(server)


@pytest.mark.parametrize("ubah,diterima", [
    ({}, True), ({"mode": "rutin"}, True),
    ({"revisi": "A" * 40}, False), ({"digest": "b" * 64}, False),
    ({"kontrak": "c" * 63}, False), ({"pasangan_terverifikasi": False}, False),
    ({"kompatibel": False}, False), ({"mode": "persiapan"}, False), ({"versi": 2}, False),
    ({"tambahan": 1}, False),
])
def test_artefak_recovery_dipatok_ketat(tmp_path, ubah, diterima):
    data = json.loads(artefak(**ubah))
    if ubah.get("tambahan"):
        data["setelah"] = 1
    p = tulis(tmp_path / "recovery.json", json.dumps(data))
    assert prod.baca_recovery(p) is diterima


@pytest.mark.parametrize("isi", [
    b"{", b'{"versi":1,"versi":1}', b'{"versi":1,"revisi":"a"*40}',
    b"#" * 2000, "{\"versi\": 1}".encode("utf-16"),
])
def test_artefak_recovery_rusak_ditolak(tmp_path, isi):
    p = tulis(tmp_path / "recovery.json", isi)
    assert prod.baca_recovery(p) is False


def test_artefak_recovery_izin_dan_symlink_ditolak(tmp_path):
    asli = tulis(tmp_path / "asli.json", artefak())
    os.chmod(asli, 0o644)
    assert prod.baca_recovery(asli) is False
    os.chmod(asli, 0o600)
    tautan = tmp_path / "tautan.json"
    tautan.symlink_to(asli)
    assert prod.baca_recovery(tautan) is False
    assert prod.baca_recovery(tmp_path / "tidak-ada.json") is False


def test_permukaan_callback_ikut_image():
    assert prod.permukaan_callback() in (True, False)
    assert prod.kesiapan_produksi(path_recovery="/run/secrets/tidak-ada")["recovery"] is False


@pytest.mark.parametrize("tahap", ["nonaktif", "rekonsiliasi", "checkout", "penegakan"])
@pytest.mark.parametrize("siap", [
    {"provider_produksi": False, "callback": False, "recovery": False, "kebijakan": False},
    {"provider_produksi": True, "callback": False, "recovery": False, "kebijakan": False},
    {"provider_produksi": True, "callback": True, "recovery": False, "kebijakan": False},
    {"provider_produksi": True, "callback": True, "recovery": True, "kebijakan": False},
    {"provider_produksi": True, "callback": True, "recovery": True, "kebijakan": True},
])
def test_sakelar_efektif_sepadan_permukaan_admin(tmp_path, monkeypatch, tahap, siap):
    db = tmp_path / "admin-control.db"
    admin_store.siapkan(db, sekarang=T0)
    with admin_store._transaksi(db) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap=?", (tahap,))
    monkeypatch.setattr(admin_store, "BAWAAN", db)
    runtime = admin_subscription.RuntimePembayaran(
        m.Konfigurasi("production", KUNCI, MERCHANT), lambda *a, **kw: None, d.SAKELAR, dict(siap))
    penangan = SimpleNamespace(server=SimpleNamespace(pembayaran_runtime=runtime))
    dari_admin = admin_subscription.runtime_penangan(penangan)
    dari_pekerja = prod.sakelar_efektif(db, siap)
    assert dari_admin is not None and dari_admin.sakelar == dari_pekerja
    if not siap["provider_produksi"]:
        assert dari_pekerja == d.SAKELAR


def test_tanpa_readiness_tidak_ada_kemampuan(tmp_path, monkeypatch):
    db = tmp_path / "admin-control.db"
    admin_store.siapkan(db, sekarang=T0)
    with admin_store._transaksi(db) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='penegakan'")
    monkeypatch.setattr(admin_store, "BAWAAN", db)
    kosong = {"provider_produksi": False, "callback": False, "recovery": False, "kebijakan": False}
    assert prod.sakelar_efektif(db, kosong) == d.SAKELAR
    for nama in ("fondasi", "buat_pembayaran", "rekonsiliasi", "penegakan"):
        with pytest.raises(d.FiturNonaktif):
            prod.sakelar_efektif(db, kosong).wajib(nama)
