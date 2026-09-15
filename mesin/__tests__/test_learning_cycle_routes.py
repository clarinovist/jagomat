"""Palang request dan transaksi endpoint siklus melalui HTTP nyata."""
import http.client
import urllib.parse

import pytest

from http_test_kit import SANDI_GURU, _basic
from test_learning_cycle_http import server, _payload_benar, _jumlah_bukti
import database


def _post(s, jalur, data=b"", headers=None, pengguna="guru"):
    koneksi = http.client.HTTPConnection(s.server.server_address[0], s.server.server_address[1])
    tajuk = {"Authorization": _basic(pengguna, SANDI_GURU),
             "Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
    koneksi.request("POST", jalur, body=data, headers=tajuk)
    respons = koneksi.getresponse()
    hasil = (respons.status, respons.read().decode(), dict(respons.getheaders()))
    koneksi.close()
    return hasil


@pytest.mark.parametrize("jalur", ["/siklus/{id}/tambahan/buat", "/siklus/0{id}/buat"])
def test_path_tidak_kanonis_404_tanpa_mutasi(server, jalur):
    s, ids = server
    kode, _, _ = _post(s, jalur.format(id=ids["siswa_buat"]))
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM putaran_fokus").fetchone()[0] == 0
    assert kode == 404


@pytest.mark.parametrize("mentah,tajuk,kode_harap", [
    (b"aksi=ubah_fokus&aksi=intervensi_selesai", {}, 400),
    (b"%FF=x", {}, 400),
    (b"", {"Content-Length": "-1"}, 400),
    (b"", {"Content-Length": "1000001"}, 413),
    (b"", {"Origin": "https://asing.invalid"}, 403),
])
def test_payload_rusak_ditolak_sebelum_mutasi(server, mentah, tajuk, kode_harap):
    s, ids = server
    kode, _, _ = _post(s, f'/siklus/{ids["siswa_buat"]}/aksi', mentah, tajuk)
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM kejadian_belajar").fetchone()[0] == 0
    assert kode == kode_harap


@pytest.mark.parametrize("jenis,aksi", [("sesi", "konfirmasi"), ("sesi", "batalkan"), ("siklus", "buat"), ("siklus", "aksi")])
def test_semua_endpoint_asing_404_identik_tanpa_efek(server, jenis, aksi):
    s, ids = server
    asing = ids["sesi_b"] if jenis == "sesi" else ids["siswa_b"]
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    nyata = _post(s, f"/{jenis}/{asing}/{aksi}", b"payload=asing")
    hilang = _post(s, f"/{jenis}/999999/{aksi}", b"payload=asing")
    assert nyata[:2] == hilang[:2]
    assert nyata[0] == 404
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("kasus", ["belum_selesai", "outcome_kosong", "opt_in_drill"])
def test_konfirmasi_gagal_rollback_seluruh_koreksi(server, kasus):
    s, ids = server
    with s.buka() as kon:
        sesi = ids["sesi_a"]
        if kasus == "outcome_kosong":
            sesi = database.buat_sesi(kon, ids["siswa_a"], seed=900, jumlah_soal=2)
            database.tandai_selesai(kon, sesi)
        elif kasus == "belum_selesai":
            kon.execute("UPDATE sesi SET selesai = NULL WHERE id = ?", (sesi,))
        else:
            kon.execute("UPDATE sesi SET mode = 'drill' WHERE id = ?", (sesi,))
        _, payload = _payload_benar(kon, sesi, sertakan=kasus == "opt_in_drill")
        sebelum = tuple(kon.iterdump())
    kode, _, _ = _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(payload).encode())
    assert kode == 400
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_guru_mengoreksi_malrule_menjadi_benar_dapat_dikonfirmasi(server):
    s, ids = server
    sesi = ids["sesi_a"]
    with s.buka() as kon:
        butir = database.isi_sesi(kon, sesi)[0]
        malrule = database.malrule_soal(kon, butir["soal_id"])[0]
        payload = {f'jwb_{butir["sesi_soal_id"]}': malrule["jawaban"],
                   f'kode_{butir["sesi_soal_id"]}': "benar"}
    kode, _, _ = _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(payload).encode())
    assert kode == 303
    with s.buka() as kon:
        hasil = kon.execute("SELECT benar, kode_final, malrule_id FROM snapshot_outcome").fetchone()
        assert tuple(hasil) == (1, None, None)


def test_hapus_sesi_berbukti_409_tanpa_menghilangkan_histori(server):
    s, ids = server
    with s.buka() as kon:
        database.konfirmasi_hasil(kon, ids["sesi_a"], guru="guru")
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = _post(s, f'/sesi/{ids["sesi_a"]}/hapus', b"konfirmasi=1")
    assert kode == 409
    assert "Batalkan sesi" in isi
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_koreksi_menginvalidasi_tanpa_menghapus_snapshot_lama(server):
    s, ids = server
    sesi = ids["sesi_a"]
    with s.buka() as kon:
        _, payload = _payload_benar(kon, sesi)
    assert _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(payload).encode())[0] == 303
    with s.buka() as kon:
        lama = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome"))
    kode_field = next(k for k in payload if k.startswith("kode_"))
    koreksi = {**payload, kode_field: "H"}
    # Tinjauan pemahaman sudah tersimpan: payload lama tanpa versi harus
    # ditolak, bukan diberi izin menimpa tab yang lebih baru.
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    assert _post(s, f"/sesi/{sesi}", urllib.parse.urlencode(koreksi).encode())[0] == 400
    with s.buka() as kon:
        import review_store
        assert tuple(kon.iterdump()) == sebelum
        sid = int(kode_field.removeprefix('kode_'))
        koreksi[f'versi_tinjauan_{sid}'] = review_store.tanda(kon, sid)
    assert _post(s, f"/sesi/{sesi}", urllib.parse.urlencode(koreksi).encode())[0] == 200
    with s.buka() as kon:
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)).fetchone()[0] is None
        assert tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome")) == lama
    assert _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(koreksi).encode())[0] == 303
    with s.buka() as kon:
        assert _jumlah_bukti(kon, sesi)["snapshot"] == 2


def test_level_baru_tidak_diblokir_sesi_putaran_lama(server):
    s, ids = server
    siswa = ids["siswa_buat"]
    jalur = f"/siklus/{siswa}/buat"
    assert _post(s, jalur)[0] == 303
    with s.buka() as kon:
        database.ganti_level(kon, siswa, "P4")
    assert _post(s, jalur)[0] == 303
    with s.buka() as kon:
        assert [b[0] for b in kon.execute("SELECT level FROM sesi WHERE siswa_id = ? ORDER BY id", (siswa,))] == ["P3", "P4"]


def test_dua_request_buat_paralel_hanya_membuat_satu_sesi(server):
    from concurrent.futures import ThreadPoolExecutor

    s, ids = server
    jalur = f'/siklus/{ids["siswa_buat"]}/buat'
    with ThreadPoolExecutor(max_workers=2) as pekerja:
        hasil = tuple(pekerja.map(lambda _: _post(s, jalur), range(2)))
    assert all(h[0] == 303 for h in hasil)
    assert hasil[0][2]["Location"] == hasil[1][2]["Location"]
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (ids["siswa_buat"],)).fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM putaran_fokus WHERE siswa_id = ?", (ids["siswa_buat"],)).fetchone()[0] == 1


def test_endpoint_memiliki_batas_request_tanpa_mutasi_kedua(server, monkeypatch):
    import learning_cycle_http as http

    s, ids = server
    monkeypatch.setattr(http, "_BATAS_PER_MENIT", 1, raising=False)
    monkeypatch.setattr(http, "_riwayat", {}, raising=False)
    jalur = f'/siklus/{ids["siswa_buat"]}/buat'
    assert _post(s, jalur)[0] == 303
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
    assert _post(s, jalur)[0] == 429
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_simpan_identik_tidak_menginvalidasi_konfirmasi(server):
    s, ids = server
    sesi = ids["sesi_a"]
    with s.buka() as kon:
        _, payload = _payload_benar(kon, sesi)
    isi = urllib.parse.urlencode(payload).encode()
    assert _post(s, f"/sesi/{sesi}/konfirmasi", isi)[0] == 303
    assert _post(s, f"/sesi/{sesi}", isi)[0] == 200
    with s.buka() as kon:
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)).fetchone()[0]


def test_opt_in_dapat_dicabut_dengan_konfirmasi_baru(server):
    from learning_cycle import _sesi_bukti_pemetaan

    s, ids = server
    sesi = ids["sesi_a"]
    with s.buka() as kon:
        _, payload = _payload_benar(kon, sesi, sertakan=True)
    assert _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(payload).encode())[0] == 303
    tanpa_opt_in = {k: v for k, v in payload.items() if k != "sertakan_pemetaan"}
    assert _post(s, f"/sesi/{sesi}/konfirmasi", urllib.parse.urlencode(tanpa_opt_in).encode())[0] == 303
    with s.buka() as kon:
        assert not _sesi_bukti_pemetaan(database.muat_bukti_siklus(kon, ids["siswa_a"]), None)
        assert _jumlah_bukti(kon, sesi)["konfirmasi"] == 2


def test_batal_sesi_manual_berbukti_mempertahankan_snapshot(server):
    s, ids = server
    with s.buka() as kon:
        database.konfirmasi_hasil(kon, ids["sesi_a"], guru="guru")
    kode, _, _ = _post(s, f'/sesi/{ids["sesi_a"]}/batalkan')
    assert kode == 303
    with s.buka() as kon:
        assert _jumlah_bukti(kon, ids["sesi_a"])["snapshot"] == 1
        assert kon.execute("SELECT dibatalkan FROM sesi WHERE id = ?", (ids["sesi_a"],)).fetchone()[0]


def test_pemetaan_hari_berikutnya_membuat_occurrence_baru(server):
    s, ids = server
    jalur = f'/siklus/{ids["siswa_buat"]}/buat'
    assert _post(s, jalur)[0] == 303
    with s.buka() as kon:
        pertama = kon.execute("SELECT id FROM sesi WHERE siswa_id = ?", (ids["siswa_buat"],)).fetchone()[0]
        kon.execute("UPDATE sesi SET tanggal = '2026-01-01', selesai = '2026-01-01' WHERE id = ?", (pertama,))
        lewat = {b["sesi_soal_id"] for b in database.isi_sesi(kon, pertama)}
        database.konfirmasi_hasil(kon, pertama, guru="guru", dilewati=lewat)
    kode, _, tajuk = _post(s, jalur)
    assert kode == 303
    assert tajuk["Location"] != f"/sesi/{pertama}"
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (ids["siswa_buat"],)).fetchone()[0] == 2


def test_konfirmasi_prg_dan_double_submit_tidak_menambah_bukti(server):
    s, ids = server
    with s.buka() as kon:
        _, payload = _payload_benar(kon, ids["sesi_a"], sertakan=True)
    jalur = f'/sesi/{ids["sesi_a"]}/konfirmasi'
    for _ in range(2):
        kode, _, headers = _post(s, jalur, urllib.parse.urlencode(payload).encode())
        assert kode == 303
        assert headers["Location"] == f'/sesi/{ids["sesi_a"]}'
    with s.buka() as kon:
        assert _jumlah_bukti(kon, ids["sesi_a"]) == {
            "konfirmasi": 1, "snapshot": 1, "kejadian": 2,
        }
