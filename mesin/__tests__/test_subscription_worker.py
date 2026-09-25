"""Pekerja rekonsiliasi: batch, cooldown, restart, owner/revisi, dan CLI."""

from dataclasses import replace
import importlib.util
import json
import os
from types import SimpleNamespace

import pytest
import admin_store
import auth
import database
import subscription as d
import subscription_store as store
import subscription_worker as worker
from test_midtrans_contract import CFG
from test_subscription import ts
from test_subscription_http import Provider

SANDI = "sandi-sintetis-panjang-123"
T0 = ts(2027, 1, 1)
ON = d.Sakelar(True, True, True, False)
CFGP = replace(CFG, lingkungan="production")
AKAR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _muat_cli():
    spec = importlib.util.spec_from_file_location(
        "rekonsiliasi_uji", os.path.join(AKAR, "scripts", "rekonsiliasi_langganan.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _akun_keluarga(k, nomor=1):
    """Akun guru sintetis per nomor, lengkap dengan profil, enrollment, dan cakupan."""
    if nomor in k.akun_keluarga:
        return k.akun_keluarga[nomor]
    if nomor == 1:
        akun, sid = k.akun, k.sid
    else:
        nama = "guru%d" % nomor
        auth.tambah_akun(nama, SANDI, "guru", path=k.auth)
        akun = auth.cari_akun(nama, path=k.auth)
        with database.buka(k.db) as kon:
            sid = database.tambah_siswa(kon, "Profil %d" % nomor, "P3", pemilik=nama)
    akun = dict(akun, sid=sid)
    store.enroll(k.admin, akun["id_akun"], sumber_id="daftar_%04d" % nomor, asal="publik",
                 mulai=T0, peran="guru", sakelar=ON)
    store.atur_cakupan(k.admin, akun["id_akun"], (sid,), operasi_id="cakupan_%04d" % nomor,
                       revisi=0, sekarang=T0, pemilik_profil=lambda _: akun["id_akun"], sakelar=ON)
    k.akun_keluarga[nomor] = akun
    return akun


@pytest.fixture
def uji(tmp_path):
    admin = tmp_path / "admin-control.db"
    admin_store.siapkan(admin, sekarang=T0)
    berkas = tmp_path / "sandi.json"
    auth.simpan_sandi(SANDI, "guru", path=berkas)
    akun = auth.muat_akun(berkas)[0]
    db = tmp_path / "belajar.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Profil Sintetis", "P3", pemilik=akun["pengguna"])
    with admin_store._transaksi(admin) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    store.buat_kampanye(admin, "promo_v1", mulai=T0, sakelar=ON)
    return SimpleNamespace(admin=admin, auth=berkas, db=db, akun=akun, sid=sid,
                           akun_keluarga={}, provider=Provider(), tmp=tmp_path)


def buat(k, nomor=1, *, intent=True, kedaluwarsa=None):
    """Invoice + intent untuk keluarga ke-`nomor`; kembalikan (invoice, akun)."""
    akun = _akun_keluarga(k, nomor)
    inv = store.buat_invoice(k.admin, akun["id_akun"], invoice_id="inv_" + "%032x" % nomor,
                             idempotency_key="idem_%032x" % nomor, provider="midtrans",
                             channel="qris", merchant=CFG.merchant, sekarang=T0,
                             kedaluwarsa=kedaluwarsa or T0 + 86400, sakelar=ON)
    if intent:
        store.reservasi_create(k.admin, akun["id_akun"], inv["invoice_id"], sekarang=T0, sakelar=ON)
    k.provider.nominal = inv["rupiah"]
    return inv, akun


def catat(k, sekarang, **ubah):
    return worker.jalankan(k.admin, k.auth, k.db, config=CFGP, transport=k.provider,
                           sekarang=sekarang, sakelar=ON, **ubah)


def jumlah(k, tabel):
    with admin_store.buka_baca(k.admin) as kon:
        return kon.execute("SELECT COUNT(*) FROM " + tabel).fetchone()[0]


def observasi(k):
    with admin_store.buka_baca(k.admin) as kon:
        return [tuple(b) for b in kon.execute(
            "SELECT operasi_id, status FROM langganan_rekonsiliasi ORDER BY rowid")]


def test_kandidat_bounded_cooldown_cutoff_dan_intent(uji):
    k = uji
    inv1, akun1 = buat(k, 1)
    inv2, _ = buat(k, 2, intent=False)
    inv3, akun3 = buat(k, 3)
    kandidat = worker.kandidat(k.admin, sekarang=T0 + 60)
    assert [b[0] for b in kandidat] == [inv3["invoice_id"], inv1["invoice_id"]]
    assert inv2["invoice_id"] not in [b[0] for b in kandidat]
    assert [b[0] for b in worker.kandidat(k.admin, sekarang=T0 + 60, batas=1)] == [inv3["invoice_id"]]
    assert k.provider.panggilan == []
    store.catat_pengamatan(k.admin, akun3["id_akun"], inv3["invoice_id"],
                           operasi_id="qry_" + "a" * 32, status="belum_terverifikasi",
                           sekarang=T0 + 60, sakelar=ON)
    assert [b[0] for b in worker.kandidat(k.admin, sekarang=T0 + 61)] == [inv1["invoice_id"]]
    assert worker.kandidat(k.admin, sekarang=T0 + 400) != []
    tua, _ = buat(k, 4, kedaluwarsa=T0 + 10)
    assert tua["invoice_id"] not in [b[0] for b in worker.kandidat(k.admin, sekarang=T0 + 8 * 86400)]
    # Hint callback tanpa intent tidak boleh memicu query provider.
    inv5, akun5 = buat(k, 5, intent=False)
    store.catat_pengamatan(k.admin, akun5["id_akun"], inv5["invoice_id"],
                           operasi_id="cbk_" + "b" * 32, status="belum_terverifikasi",
                           sekarang=T0 + 60, sakelar=ON)
    assert inv5["invoice_id"] not in [b[0] for b in worker.kandidat(k.admin, sekarang=T0 + 60)]
    assert k.provider.panggilan == []
    with pytest.raises(ValueError):
        worker.kandidat(k.admin, sekarang=T0 + 60, batas=0)


def test_settlement_tepat_sekali_dan_restart_tidak_double_grant(uji):
    k = uji
    buat(k, 1)
    k.provider.status = "settlement"
    awal = catat(k, T0 + 60)
    assert awal["lunas"] == 1 and awal["kandidat"] == 1
    assert jumlah(k, "langganan_receipt") == 1 and jumlah(k, "langganan_grant") == 1
    with admin_store.buka_baca(k.admin) as kon:
        assert kon.execute("SELECT hasil FROM langganan_receipt").fetchone()[0] == "grant"
    lagi = catat(k, T0 + 120, jeda=0)
    assert lagi["kandidat"] == 0 and jumlah(k, "langganan_grant") == 1
    assert [b[1] for b in observasi(k)].count("settlement") == 1


def test_crash_sebelum_receipt_melanjutkan_order_sama(uji):
    k = uji
    buat(k, 1)
    k.provider.status = "settlement"

    def putus():
        raise OSError("transport putus")

    k.provider.hook = putus
    pertama = catat(k, T0 + 60)
    assert pertama["menunggu"] == 1 and jumlah(k, "langganan_receipt") == 0
    k.provider.hook = None
    kedua = catat(k, T0 + 400)
    assert kedua["lunas"] == 1 and jumlah(k, "langganan_receipt") == 1
    assert jumlah(k, "langganan_grant") == 1
    assert len({b[0] for b in observasi(k) if b[0].startswith("qry_")}) == 2


def test_unknown_dijadwalkan_ulang_bounded(uji):
    k = uji
    buat(k, 1)
    ringkas = catat(k, T0 + 60)
    assert ringkas == {"kandidat": 1, "lunas": 0, "menunggu": 1, "perlu_diperiksa": 0,
                       "dilewati": 0}
    assert jumlah(k, "langganan_receipt") == 0 and len(k.provider.panggilan) == 1
    assert worker.kandidat(k.admin, sekarang=T0 + 61) == []
    assert worker.kandidat(k.admin, sekarang=T0 + 400) != []
    assert catat(k, T0 + 400)["kandidat"] == 1 and len(k.provider.panggilan) == 2


def test_refund_lalu_settlement_dan_nominal_lebih(uji):
    k = uji
    inv, _ = buat(k, 1)
    k.provider.status = "refund"
    assert catat(k, T0 + 60)["perlu_diperiksa"] == 1
    assert jumlah(k, "langganan_receipt") == 0
    k.provider.status = "settlement"
    k.provider.nominal = inv["rupiah"] + 5000
    assert catat(k, T0 + 400)["menunggu"] == 1
    assert jumlah(k, "langganan_receipt") == 0
    k.provider.nominal = inv["rupiah"]
    assert catat(k, T0 + 800)["lunas"] == 1
    assert jumlah(k, "langganan_grant") == 1


def test_settlement_terlambat_perlu_diperiksa_tanpa_grant(uji):
    k = uji
    buat(k, 1, kedaluwarsa=T0 + 100)
    k.provider.status = "settlement"
    ringkas = catat(k, T0 + 200)
    assert ringkas["perlu_diperiksa"] == 1 and ringkas["lunas"] == 0, ringkas
    with admin_store.buka_baca(k.admin) as kon:
        assert kon.execute("SELECT hasil FROM langganan_receipt").fetchone()[0] == "perlu_diperiksa"
    assert jumlah(k, "langganan_grant") == 0


def test_owner_berubah_selama_jaringan_tidak_grant(uji):
    k = uji
    _, akun = buat(k, 1)
    k.provider.status = "settlement"

    def ubah():
        with database.buka(k.db) as kon:
            kon.execute("UPDATE siswa SET pemilik='guru-lain' WHERE id=?", (akun["sid"],))
            kon.commit()

    k.provider.hook = ubah
    ringkas = catat(k, T0 + 60)
    assert ringkas["dilewati"] == 1 and jumlah(k, "langganan_receipt") == 0
    assert jumlah(k, "langganan_grant") == 0


def test_revisi_akun_berubah_selama_jaringan_tidak_grant(uji):
    k = uji
    _, akun = buat(k, 1)
    k.provider.status = "settlement"

    def ubah():
        auth.naikkan_revisi_auth(akun["id_akun"], path=k.auth)

    k.provider.hook = ubah
    assert catat(k, T0 + 60)["dilewati"] == 1
    assert jumlah(k, "langganan_receipt") == 0


def test_profil_bukan_milik_akun_tidak_diproses(uji):
    k = uji
    _, akun = buat(k, 1)
    k.provider.status = "settlement"
    with database.buka(k.db) as kon:
        kon.execute("UPDATE siswa SET pemilik='guru-lain' WHERE id=?", (akun["sid"],))
        kon.commit()
    assert worker.kandidat(k.admin, sekarang=T0 + 60) != []
    assert catat(k, T0 + 60)["dilewati"] == 1
    assert len(k.provider.panggilan) == 0 and jumlah(k, "langganan_receipt") == 0


def test_batch_bounded_dan_sakelar_off(uji):
    k = uji
    for nomor in (1, 2, 3):
        buat(k, nomor)
    k.provider.status = "settlement"
    ringkas = catat(k, T0 + 60, batas=2)
    assert ringkas["kandidat"] == 2 and len(k.provider.panggilan) == 2
    with pytest.raises(d.FiturNonaktif):
        worker.jalankan(k.admin, k.auth, k.db, config=CFGP, transport=k.provider,
                        sekarang=T0 + 200)
    assert len(k.provider.panggilan) == 2


def test_lease_eksklusif_antar_proses(tmp_path):
    path = tmp_path / "langganan.lock"
    with worker.lease(path) as pertama:
        assert pertama is True
        with worker.lease(path) as kedua:
            assert kedua is False
    with worker.lease(path) as ketiga:
        assert ketiga is True
    assert path.exists()


@pytest.fixture
def cli(uji):
    return SimpleNamespace(modul=_muat_cli(), k=uji)


def argumen(cli, **ubah):
    k = cli.k
    rahasia = k.tmp / "rahasia-cli.conf"
    if not rahasia.exists():
        rahasia.write_text("merchant=%s\nserver_key=Mid-server-SINTETIS\n" % CFG.merchant)
        os.chmod(rahasia, 0o600)
    dasar = {"--admin-db": str(k.admin), "--auth": str(k.auth), "--belajar": str(k.db),
             "--rahasia": str(rahasia), "--recovery": str(k.tmp / "belum-ada.json"),
             "--lease": str(k.tmp / "cli.lock"), "--sekarang": str(T0 + 60)}
    dasar.update(ubah)
    return [item for pasang in dasar.items() for item in pasang]


def test_cli_satu_putaran_agregat_tanpa_rahasia(cli, capsys):
    k = cli.k
    buat(k, 1)
    k.provider.status = "settlement"
    kode = cli.modul.main(argumen(cli), transport=k.provider)
    keluar = capsys.readouterr()
    assert kode == 0, keluar.err
    data = json.loads(keluar.out)
    assert data["lunas"] == 1 and data["kandidat"] == 1
    assert data["kesiapan"] == {"provider_produksi": True, "callback": True,
                                "recovery": False, "kebijakan": True}
    assert "Mid-server" not in keluar.out + keluar.err
    assert "inv_" not in keluar.out


def test_cli_exit_code_konfigurasi_lease_dan_sakelar(cli, capsys):
    k = cli.k
    args = argumen(cli)
    rusak = k.tmp / "rusak.conf"
    rusak.write_text("merchant=%s\n" % CFG.merchant)
    os.chmod(rusak, 0o600)
    ganti = dict(zip(args[::2], args[1::2]))
    ganti["--rahasia"] = str(rusak)
    assert cli.modul.main([item for pasang in ganti.items() for item in pasang]) == 2
    assert "konfigurasi produksi tidak sah" in capsys.readouterr().err
    with worker.lease(str(k.tmp / "cli.lock")):
        assert cli.modul.main(args, transport=k.provider) == 3
    assert "lease dipegang proses lain" in capsys.readouterr().err
    with admin_store._transaksi(k.admin) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap='nonaktif'")
    assert cli.modul.main(args, transport=k.provider) == 4
    assert "sakelar" in capsys.readouterr().err
    assert jumlah(k, "langganan_receipt") == 0


def test_cli_memakai_factory_konfigurasi_produksi(cli, monkeypatch):
    k = cli.k
    dipanggil = []

    def pabrik(*, path_rahasia=None):
        dipanggil.append(str(path_rahasia))
        return CFGP, k.provider

    monkeypatch.setattr(cli.modul.prod, "konfigurasi_dan_transport", pabrik)
    assert cli.modul.main(argumen(cli)) == 0
    assert dipanggil == [str(k.tmp / "rahasia-cli.conf")]
