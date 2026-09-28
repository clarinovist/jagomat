"""Ledger kuota prototype admin9: DB sementara saja, tanpa migrasi aplikasi."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
import threading
import time

import pytest

import admin_store
import assistant_entitlement as d
import assistant_quota_schema as schema
import assistant_quota_store as store
import subscription as lama
import subscription_store as langganan
import subscription_package_store as paket_store
from test_assistant_entitlement_domain import AKUN, LAIN, T0, snapshot

ON = lama.Sakelar(True, True, True, False)


def koneksi(path):
    kon = sqlite3.connect(str(path), timeout=5)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    return kon


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / "kuota-sintetis.db"
    kon = koneksi(path)
    # Proposal DDL, bukan migrator runtime/GET atau fixture DB produksi.
    kon.executescript(schema.DDL)
    kon.execute("PRAGMA user_version=9")
    kon.close()
    return path


def trial(akun_id=AKUN):
    return d.SnapshotHak(akun_id, T0, T0)


def reserve(kon, operasi="operasi_sintetis01", akun_id=AKUN, fitur=d.FITUR[0],
            sekarang=T0 + 1, sumber=None, penegakan=True):
    return store.reservasi_kon(kon, akun_id, operasi_id=operasi, fitur=fitur,
                              sekarang=sekarang, penegakan=penegakan,
                              muat_snapshot=lambda k, a: sumber or trial(a))


def isi(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT * FROM kuota_pendamping_operasi ORDER BY operasi_id"))


def test_default_off_tidak_menulis_dan_versi_tidak_sah_ditolak(ledger):
    kon = koneksi(ledger)
    try:
        assert reserve(kon, penegakan=False) is None
        assert not isi(kon)
        kon.execute("PRAGMA user_version=8")
        with pytest.raises(admin_store.StoreBelumSiap):
            reserve(kon)
        assert not isi(kon)
    finally:
        kon.close()


def test_replay_restart_tidak_outbound_atau_charge_ganda(ledger):
    kon = koneksi(ledger)
    r = reserve(kon)
    assert r.dibuat_baru and r.boleh_outbound and r.status == "reserved"
    kon.close()
    kon = koneksi(ledger)
    try:
        ulang = reserve(kon)
        assert not ulang.dibuat_baru and not ulang.boleh_outbound
        assert ulang.ikatan == r.ikatan and len(isi(kon)) == 1
        selesai = store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 2, hasil_valid_tersimpan=True)
        assert selesai.status == "completed"
        assert store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 3, hasil_valid_tersimpan=True) == selesai
        assert not reserve(kon).boleh_outbound
        assert len(isi(kon)) == 1
        pakai = store._pemakaian(kon, AKUN)
        h = d.selesaikan(AKUN, trial(), fitur=d.FITUR[0], sekarang=T0 + 3, pemakaian=pakai)
        assert (h.digunakan, h.direservasi, h.tersisa) == (1, 0, 9)
    finally:
        kon.close()


@pytest.mark.parametrize("ubah", [
    {"akun_id": LAIN}, {"fitur": d.FITUR[1]},
    {"jendela_id": "f" * 64}, {"entitlement_sidik": "f" * 64},
])
def test_binding_operasi_harus_exact_tanpa_efek(ledger, ubah):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        sebelum = isi(kon)
        salah = replace(r.ikatan, **ubah)
        with pytest.raises(store.KonflikKuota):
            store.finalisasi_kon(kon, salah, sekarang=T0 + 2, hasil_valid_tersimpan=True)
        assert isi(kon) == sebelum
        with pytest.raises(store.KonflikKuota):
            store.baca_operasi_kon(kon, salah)
    finally:
        kon.close()


def test_replay_account_fitur_window_dan_snapshot_berbeda_ditolak(ledger):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        sebelum = isi(kon)
        for kwargs in ({"akun_id": LAIN}, {"fitur": d.FITUR[1]},
                       {"sumber": snapshot(), "sekarang": snapshot().grants[0].mulai},
                       {"sumber": replace(trial(), trial_mulai=T0 - 1)}):
            with pytest.raises(store.KonflikKuota):
                reserve(kon, **kwargs)
        assert isi(kon) == sebelum
        assert not store.baca_operasi_kon(kon, r.ikatan).boleh_outbound
    finally:
        kon.close()


def test_unknown_tetap_reserved_bukan_release_atau_retry_otomatis(ledger):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        store.tandai_unknown_kon(kon, r.ikatan, sekarang=T0 + 2)
        assert reserve(kon).status == "unknown" and not reserve(kon).boleh_outbound
        assert store._pemakaian(kon, AKUN)[0].direservasi == 1
        with pytest.raises(store.KonflikKuota):
            store.lepaskan_kon(kon, r.ikatan, sekarang=T0 + 3, tanpa_output_terbukti=True)
        with pytest.raises(store.KonflikKuota):
            store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 3, hasil_valid_tersimpan=True)
        with pytest.raises(store.KonflikKuota):
            store.lepaskan_kon(kon, r.ikatan, sekarang=T0 + 3, tanpa_output_terbukti=False, rekonsiliasi=True)
        store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 3, hasil_valid_tersimpan=True, rekonsiliasi=True)
        assert store._pemakaian(kon, AKUN)[0].digunakan == 1
    finally:
        kon.close()


def test_release_known_no_output_dan_finalisasi_perlu_hasil_tersimpan(ledger):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        for bukti in (False, None, 1):
            with pytest.raises(store.KonflikKuota):
                store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 2, hasil_valid_tersimpan=bukti)
            with pytest.raises(store.KonflikKuota):
                store.lepaskan_kon(kon, r.ikatan, sekarang=T0 + 2, tanpa_output_terbukti=bukti)
        store.lepaskan_kon(kon, r.ikatan, sekarang=T0 + 2, tanpa_output_terbukti=True)
        assert not reserve(kon).boleh_outbound
        assert store._pemakaian(kon, AKUN)[0].direservasi == 0
        with pytest.raises(store.KonflikKuota):
            store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 3, hasil_valid_tersimpan=True)
        baru = reserve(kon, operasi="operasi_sintetis02")
        store.tandai_unknown_kon(kon, baru.ikatan, sekarang=T0 + 4)
        store.lepaskan_kon(kon, baru.ikatan, sekarang=T0 + 5,
                          tanpa_output_terbukti=True, rekonsiliasi=True)
        assert all(r["status"] == "released" for r in kon.execute("SELECT status FROM kuota_pendamping_operasi"))
    finally:
        kon.close()


def test_dua_tab_unit_terakhir_hanya_satu_atomic(ledger, monkeypatch):
    kon = koneksi(ledger)
    for n in range(9):
        reserve(kon, operasi="operasi_awal_%02d" % n)
    kon.close()
    asli = store._bekukan_jendela

    def lambat(kon, hak):
        asli(kon, hak)
        time.sleep(0.12)  # Memperlebar race setelah cek kuota, sebelum INSERT.

    monkeypatch.setattr(store, "_bekukan_jendela", lambat)
    barier = threading.Barrier(2)

    def tab(n):
        kon = koneksi(ledger)
        try:
            barier.wait(timeout=5)
            try:
                return reserve(kon, operasi="operasi_tab_%02d" % n).boleh_outbound
            except store.KuotaDitolak as galat:
                assert galat.status == "kuota_habis"
                return False
        finally:
            kon.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        hasil = list(pool.map(tab, (1, 2)))
    assert sorted(hasil) == [False, True]
    kon = koneksi(ledger)
    try:
        assert len(isi(kon)) == 10
        store.validasi_ledger(kon)
    finally:
        kon.close()


def test_kuota_akun_dipakai_bersama_lintas_profil(ledger):
    kon = koneksi(ledger)
    try:
        # Label request sintetis mewakili dua caller profil. API tidak menerima
        # profil sebagai key kuota; semuanya tetap memakai akun yang sama.
        for profil in (1, 2):
            for n in range(5):
                reserve(kon, operasi="profil_%d_operasi_%02d" % (profil, n))
        with pytest.raises(store.KuotaDitolak, match="kuota_habis"):
            reserve(kon, operasi="profil_3_operasi_00")
        assert reserve(kon, akun_id=LAIN, operasi="akun_lain_operasi").boleh_outbound
        assert reserve(kon, fitur=d.FITUR[1], operasi="foto_operasi_0001").boleh_outbound
        assert len(isi(kon)) == 12
    finally:
        kon.close()


def test_trial_beku_tidak_direset_bahkan_lintas_fitur(ledger):
    kon = koneksi(ledger)
    try:
        reserve(kon)
        sebelum = isi(kon)
        bergeser = replace(trial(), trial_mulai=T0 + 1, transisi_mulai=T0 + 1)
        with pytest.raises(store.KonflikKuota, match="sumber kuota telah dibekukan"):
            reserve(kon, operasi="operasi_trial_ulang", sekarang=T0 + 2,
                    sumber=bergeser, fitur=d.FITUR[1])
        assert isi(kon) == sebelum
    finally:
        kon.close()


def test_satu_grant_snapshot_bergeser_tidak_memberi_jendela_baru(ledger):
    kon = koneksi(ledger)
    try:
        s = snapshot()
        g = s.grants[0]
        reserve(kon, sekarang=g.mulai, sumber=s)
        sebelum = isi(kon)
        # Invoice sama tetapi kalender digeser satu detik. Ini bukan grant baru.
        berubah = replace(g, mulai=g.mulai + 1, akhir=g.akhir + 1,
                          jangkar_mulai=g.jangkar_mulai + 1)
        with pytest.raises(store.KonflikKuota, match="sumber kuota telah dibekukan"):
            reserve(kon, operasi="operasi_grant_bergeser", sekarang=g.mulai + 2,
                    sumber=replace(s, grants=(berubah,)), fitur=d.FITUR[1])
        assert isi(kon) == sebelum
    finally:
        kon.close()


def test_no_rollover_replay_lama_tidak_mencuri_window_baru(ledger):
    kon = koneksi(ledger)
    try:
        s = snapshot()
        awal = s.grants[0].mulai
        r = reserve(kon, sekarang=awal, sumber=s)
        h = d.selesaikan(AKUN, s, fitur=d.FITUR[0], sekarang=awal)
        with pytest.raises(store.KonflikKuota):
            reserve(kon, sekarang=h.jendela_akhir, sumber=s)
        # Crash/output yang terlambat tetap dibebankan ke jendela asal.
        store.finalisasi_kon(kon, r.ikatan, sekarang=h.jendela_akhir + 1, hasil_valid_tersimpan=True)
        baru = reserve(kon, operasi="operasi_bulan_baru", sekarang=h.jendela_akhir, sumber=s)
        assert baru.ikatan.jendela_id != r.ikatan.jendela_id
        h2 = d.selesaikan(AKUN, s, fitur=d.FITUR[0], sekarang=h.jendela_akhir,
                         pemakaian=store._pemakaian(kon, AKUN))
        assert (h2.digunakan, h2.direservasi, h2.tersisa) == (0, 1, 49)
    finally:
        kon.close()


def test_callback_gagal_rollback_dan_schema_rusak_failclosed(ledger):
    kon = koneksi(ledger)
    try:
        def gagal(k, a):
            raise ValueError("snapshot gagal sintetis")
        with pytest.raises(ValueError):
            store.reservasi_kon(kon, AKUN, operasi_id="operasi_sintetis00", fitur=d.FITUR[0],
                                sekarang=T0 + 1, muat_snapshot=gagal, penegakan=True)
        assert not isi(kon) and not kon.in_transaction
        kon.execute("DROP TRIGGER kuota_pendamping_operasi_ikat_update")
        with pytest.raises(ValueError, match="struktur"):
            reserve(kon)
        assert not isi(kon)
    finally:
        kon.close()


def test_reserve_insert_gagal_rollback_jendela(ledger, monkeypatch):
    kon = koneksi(ledger)
    asli = store._bekukan_jendela
    try:
        def gagal(k, h):
            asli(k, h)
            raise RuntimeError("crash sintetis setelah jendela")
        monkeypatch.setattr(store, "_bekukan_jendela", gagal)
        with pytest.raises(RuntimeError, match="crash sintetis"):
            reserve(kon)
        assert not isi(kon)
        assert kon.execute("SELECT COUNT(*) FROM kuota_pendamping_jendela").fetchone()[0] == 0
    finally:
        kon.close()


def test_ledger_melebihi_batas_ditolak_bukan_dianggap_nol(ledger):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        # Simulasi salinan restore korup dengan writer luar aplikasi; metadata
        # masih sesuai DDL. Validator semantik tetap menolak over-limit.
        for n in range(10):
            kon.execute("INSERT INTO kuota_pendamping_operasi VALUES(?,?,?,?,?,'reserved',?,?)",
                        ("korup_sintetis_%02d" % n, AKUN, r.ikatan.jendela_id, d.FITUR[0],
                         r.ikatan.entitlement_sidik, T0 + 1, T0 + 1))
        kon.commit()
        with pytest.raises(store.KonflikKuota, match="pemakaian melebihi kuota"):
            reserve(kon, operasi="operasi_setelah_korup")
        assert len(isi(kon)) == 11
    finally:
        kon.close()


def test_sql_immutable_binding_dan_terminal(ledger):
    kon = koneksi(ledger)
    try:
        r = reserve(kon)
        for sql in (
            "DELETE FROM kuota_pendamping_operasi",
            "UPDATE kuota_pendamping_operasi SET fitur='pembacaan_foto'",
            "UPDATE kuota_pendamping_jendela SET batas=50",
            "DELETE FROM kuota_pendamping_jendela",
            "INSERT OR REPLACE INTO kuota_pendamping_operasi SELECT * FROM kuota_pendamping_operasi",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sql)
            kon.rollback()
        store.finalisasi_kon(kon, r.ikatan, sekarang=T0 + 2, hasil_valid_tersimpan=True)
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("UPDATE kuota_pendamping_operasi SET status='released'")
        kon.rollback()
        store.validasi_ledger(kon)
    finally:
        kon.close()


def test_reader_tidak_membuat_file_schema_trial_window_dan_failclosed(tmp_path):
    path = tmp_path / "admin-sintetis.db"
    status = d.baca_status(path, AKUN, fitur=d.FITUR[0], sekarang=T0, penegakan=True)
    assert status.status == "storage_tidak_terverifikasi" and not status.boleh
    assert not path.exists()
    admin_store.siapkan(path, sekarang=T0)
    sebelum = path.read_bytes()
    assert store.baca_snapshot(path, AKUN).trial_mulai is None
    assert d.baca_status(path, AKUN, fitur=d.FITUR[0], sekarang=T0).status == "belum_ditransisikan"
    assert path.read_bytes() == sebelum
    langganan.enroll(path, AKUN, sumber_id="enrollment_sintetis", asal="transisi", mulai=T0,
                peran="guru", sakelar=ON)
    admin_store.siapkan(path, paket_v2=True, sekarang=T0)
    paket_store.adopsi(path, AKUN, operasi_id="adopsi_sintetis", sekarang=T0 + 1, sakelar=ON)
    sebelum = path.read_bytes()
    s = store.baca_snapshot(path, AKUN)
    assert d.selesaikan(AKUN, s, fitur=d.FITUR[0], sekarang=T0 + 1).status == "trial_aktif"
    # Storage quota absent: dry-run hak bukan janji sisa jatah utuh.
    assert d.baca_status(path, AKUN, fitur=d.FITUR[0], sekarang=T0 + 1).status == "storage_tidak_terverifikasi"
    assert path.read_bytes() == sebelum
    with pytest.raises(langganan.KonflikLangganan):
        langganan.enroll(path, AKUN, sumber_id="enrollment_ulang", asal="transisi", mulai=T0 + 100,
                    peran="guru", sakelar=ON)
    assert store.baca_snapshot(path, AKUN).trial_mulai == T0


def test_adapter_admin8_memakai_grant_invoice_terverifikasi(tmp_path):
    path = tmp_path / "admin-sintetis.db"
    admin_store.siapkan(path, paket_v2=True, sekarang=T0)
    langganan.enroll(path, AKUN, sumber_id="enrollment_sintetis", asal="transisi", mulai=T0,
                    peran="guru", sakelar=ON)
    paket_store.adopsi(path, AKUN, operasi_id="adopsi_sintetis", sekarang=T0 + 1, sakelar=ON)
    inv = paket_store.buat_invoice(
        path, AKUN, (1, 2), kode="jago_pro", penagihan="tahunan",
        invoice_id="inv_" + "2" * 32, idempotency_key="invoice_sintetis",
        provider="sintetis", merchant="sintetis", sekarang=T0 + 2,
        kedaluwarsa=T0 + 600, pemilik_profil=lambda p: AKUN, sakelar=ON)
    bukti = lama.Pembayaran("sintetis", "transaksi_sintetis", inv["invoice_id"], AKUN,
                           inv["rupiah"], "IDR", "qris", "sintetis", "settlement", True)
    assert langganan.terapkan_pembayaran(path, AKUN, bukti, sekarang=T0 + 3, sakelar=ON) == "grant"
    sebelum = path.read_bytes()
    s = store.baca_snapshot(path, AKUN)
    assert len(s.grants) == 1 and s.grants[0].mulai == T0 + lama.DURASI_TRIAL
    h = d.selesaikan(AKUN, s, fitur=d.FITUR[0], sekarang=s.grants[0].mulai)
    assert (h.status, h.limit, h.sumber_id) == ("pro_aktif", 50, inv["invoice_id"])
    assert path.read_bytes() == sebelum
