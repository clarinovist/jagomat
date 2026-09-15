"""Hasil pemetaan guru: ringkasan sementara, snapshot sah, dan langkah berikutnya."""
from __future__ import annotations

import http.client
import sys
import urllib.parse
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth
import database
import learning_cycle as lc
import learning_cycle_service as layanan
from http_test_kit import SANDI_GURU, ServerUji, _basic


@pytest.fixture
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    with uji.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak Pemetaan", "P3", pemilik="guru")
        sesi, _ = layanan.buat_dari_rekomendasi(kon, siswa)
        payload = {}
        for b in database.isi_sesi(kon, sesi):
            sid = int(b["sesi_soal_id"])
            jawaban = database.simpan_jawaban(kon, sid, b["kunci"], "cara sintetis")
            database.simpan_diagnosis(kon, jawaban, benar=True, kode_usulan=None,
                                      kode_final=None, alasan="jawaban tepat")
            payload[f"jwb_{sid}"] = b["kunci"]
            payload[f"kode_{sid}"] = "benar"
        database.tandai_selesai(kon, sesi)
    yield uji, siswa, sesi, payload
    uji.berhenti()


def _halaman(uji, sesi):
    kode, isi, _ = uji.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert kode == 200
    return isi.split("<body", 1)[1]


def _post(uji, sesi, payload):
    koneksi = http.client.HTTPConnection(*uji.server.server_address, timeout=10)
    try:
        koneksi.request("POST", f"/sesi/{sesi}/konfirmasi",
                        urllib.parse.urlencode(payload), {
                            "Authorization": _basic("guru", SANDI_GURU),
                            "Content-Type": "application/x-www-form-urlencoded",
                        })
        respons = koneksi.getresponse()
        return respons.status, respons.read().decode(), respons.getheader("Location")
    finally:
        koneksi.close()


def test_ringkasan_sementara_mendahului_koreksi_tanpa_mengesahkan(server):
    uji, _, sesi, _ = server
    isi = _halaman(uji, sesi)
    assert "Ringkasan sementara sesi ini" in isi
    assert isi.index("Ringkasan sementara sesi ini") < isi.index(f'<form id="form-koreksi-{sesi}"')
    assert "Belum menjadi bukti pemetaan" in isi
    assert "15 tepat" in isi
    assert "Hasil pemetaan terkonfirmasi" not in isi
    with uji.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 0


def test_konfirmasi_menuju_hasil_dengan_satu_rekomendasi_dan_koreksi_sekunder(server):
    uji, _, sesi, payload = server
    status, _, tujuan = _post(uji, sesi, payload)
    assert status == 303
    assert tujuan == f"/sesi/{sesi}#hasil-pemetaan"
    isi = _halaman(uji, sesi)
    assert 'id="hasil-pemetaan"' in isi
    assert "Hasil pemetaan terkonfirmasi" in isi
    assert "Pemetaan awal: 1 dari 3 tanggal" in isi
    assert "Gambaran awal, belum kesimpulan akhir" in isi
    assert "Rencana belajar hari ini" in isi
    assert "Cukup untuk hari ini" in isi
    assert "Lihat rencana berikutnya" not in isi
    assert isi.count('class="kartu-rencana-st"') == 1
    assert isi.index("Hasil pemetaan terkonfirmasi") < isi.index('class="panduan-edit-hasil-st"')
    assert _post(uji, sesi, payload)[2] == tujuan
    with uji.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 1


def test_konfirmasi_gagal_setelah_sah_tetap_draf_dan_snapshot_lama_utuh(server):
    uji, _, sesi, payload = server
    assert _post(uji, sesi, payload)[0] == 303
    sid = next(iter(payload)).split("_", 1)[1]
    payload.update({f"jwb_{sid}": "", f"cara_{sid}": "", f"kode_{sid}": ""})
    status, isi, _ = _post(uji, sesi, payload)
    assert status == 400
    assert "Ringkasan sementara belum ditampilkan" in isi
    assert 'id="hasil-pemetaan"' not in isi
    with uji.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 1
        assert kon.execute("SELECT dikonfirmasi_guru FROM sesi WHERE id=?", (sesi,)).fetchone()[0]


def test_konfirmasi_manual_tidak_dialihkan_ke_anchor_pemetaan(server):
    uji, _, sesi, payload = server
    with uji.buka() as kon:
        kon.execute("UPDATE sesi SET tujuan='bebas', putaran_id=NULL WHERE id=?", (sesi,))
    assert _post(uji, sesi, payload)[2] == f"/sesi/{sesi}"


def test_konfirmasi_gagal_tidak_menampilkan_hasil_sah_baru(server):
    uji, _, sesi, payload = server
    sid = next(iter(payload)).split("_", 1)[1]
    payload[f"jwb_{sid}"] = ""
    payload[f"cara_{sid}"] = ""
    payload[f"kode_{sid}"] = ""
    status, isi, _ = _post(uji, sesi, payload)
    assert status == 400
    assert "Ringkasan sementara belum ditampilkan" in isi
    assert "Hasil pemetaan terkonfirmasi" not in isi
    assert 'role="alert"' in isi


@pytest.mark.parametrize("kasus", ["manual", "batal", "level", "putaran"])
def test_sesi_tidak_aktif_tidak_dipromosikan_sebagai_peta(server, kasus):
    uji, siswa, sesi, payload = server
    with uji.buka() as kon:
        layanan.konfirmasi_dari_form(kon, sesi, "guru", payload)
        if kasus == "manual":
            kon.execute("UPDATE sesi SET tujuan='bebas', putaran_id=NULL WHERE id=?", (sesi,))
        elif kasus == "batal":
            database.batalkan_sesi(kon, sesi)
        elif kasus == "level":
            kon.execute("UPDATE siswa SET tingkat='P4' WHERE id=?", (siswa,))
        else:
            database.buat_putaran_fokus(kon, siswa, "P3")
    isi = _halaman(uji, sesi)
    assert 'id="hasil-pemetaan"' not in isi
    assert 'id="ringkasan-sementara"' not in isi


def _bukti(jumlah=1):
    fokus = ("deret_aritmetika", "H", None)
    outcomes = (lc.OutcomeSiklus("deret_aritmetika", False, "H"),
                lc.OutcomeSiklus("soal_umur", True),
                lc.OutcomeSiklus("pecahan", False, "T"),
                lc.OutcomeSiklus("luas", None, dilewati=True))
    sesi = tuple(lc.SesiSiklus(
        i, 9, "P3", "pemetaan", date(2026, 9, i),
        selesai=f"2026-09-{i:02d}", dikonfirmasi=f"2026-09-{i:02d}",
        putaran_id=7, outcomes=outcomes, konfirmasi_id=i,
    ) for i in range(1, jumlah + 1))
    return lc.BuktiSiklus(9, "P3", sesi, (lc.PutaranSiklus(7, 9, "P3", date(2026, 9, 1)),))


@pytest.mark.parametrize("jumlah", [1, 2, 3])
def test_peta_memisahkan_gambaran_awal_dan_fokus_reducer(jumlah):
    import mapping_results as hasil
    isi = hasil.render_hasil(_bukti(jumlah), jumlah)
    assert f"Pemetaan awal: {jumlah} dari 3 tanggal" in isi
    assert "Materi belum dikenalkan" in isi
    assert "Dilewati" in isi
    if jumlah < 3:
        assert "Gambaran awal, belum kesimpulan akhir" in isi
        assert "Fokus belajar yang disarankan" not in isi
    else:
        assert "Fokus belajar yang disarankan" in isi
        assert "Periksa hitungan" in isi
    assert "bukan kelemahan" in isi
    assert "bukan klaim penguasaan" in isi


@pytest.mark.parametrize("kasus", ["belum_sah", "batal", "asing", "level", "putaran", "manual"])
def test_ringkasan_hanya_menghitung_bukti_pemetaan_relevan(kasus):
    import mapping_results as hasil
    bukti = _bukti()
    lain = replace(bukti.sesi[0], id=88, outcomes=(lc.OutcomeSiklus("JANGAN_MASUK", False, "K"),))
    if kasus == "belum_sah":
        lain = replace(lain, dikonfirmasi=None, konfirmasi_id=None)
    elif kasus == "batal":
        lain = replace(lain, dibatalkan="2026-09-02")
    elif kasus == "asing":
        lain = replace(lain, siswa_id=10)
    elif kasus == "level":
        lain = replace(lain, level="P4")
    elif kasus == "putaran":
        lain = replace(lain, putaran_id=8)
    elif kasus == "manual":
        lain = replace(lain, tujuan="bebas")
    isi = hasil.render_hasil(replace(bukti, sesi=bukti.sesi + (lain,)), 1)
    assert "Jangan masuk" not in isi
    assert "1 tepat" in isi


def test_selector_pemetaan_menolak_sesi_level_berbeda():
    import mapping_results as hasil
    bukti = _bukti()
    beda = replace(bukti.sesi[0], level="P4")
    assert hasil.sesi_pemetaan_aktif(replace(bukti, sesi=(beda,)), 1) is None


def test_sesi_belum_dikonfirmasi_tidak_punya_hasil_sah():
    import mapping_results as hasil
    bukti = _bukti()
    belum = replace(bukti.sesi[0], dikonfirmasi=None, konfirmasi_id=None)
    assert hasil.render_hasil(replace(bukti, sesi=(belum,)), 1) == ""


def test_benar_dilewati_dan_teks_asing_tetap_aman():
    import mapping_results as hasil
    isi = hasil.render_sementara((
        lc.OutcomeSiklus("<script>uji</script>", True, dilewati=True),
        lc.OutcomeSiklus("materi", False, "B"),
        lc.OutcomeSiklus("materi", False, "E"),
        lc.OutcomeSiklus("materi", False, "N"),
    ))
    assert "0 tepat" in isi and "1 dilewati" in isi
    assert "Baca ulang soal: 1" in isi
    assert "Periksa penulisan jawaban: 1" in isi
    assert "Tanyakan cara menjawab: 1" in isi
    assert "<script>" not in isi.lower()
    assert "&lt;" in isi


def test_satu_k_dan_satu_h_bukan_fokus_berulang():
    import mapping_results as hasil
    bukti = _bukti(3)
    sesi = list(bukti.sesi)
    sesi[1] = replace(sesi[1], outcomes=(lc.OutcomeSiklus("deret_aritmetika", False, "K"),))
    sesi[2] = replace(sesi[2], outcomes=(lc.OutcomeSiklus("soal_umur", True),))
    isi = hasil.render_hasil(replace(bukti, sesi=tuple(sesi)), 3)
    assert "Fokus belajar yang disarankan" not in isi
    assert "bahan pantauan" in isi


def test_representasi_terbaru_per_materi_tidak_dicampur():
    import mapping_results as hasil
    bukti = _bukti()
    terbaru = replace(bukti.sesi[0], id=88, tanggal=date(2026, 9, 2), outcomes=(
        lc.OutcomeSiklus("soal_umur", False, "K", mode_representasi="visual-v1"),
    ))
    isi = hasil.render_hasil(replace(bukti, sesi=bukti.sesi + (terbaru,)), 88)
    assert "0 tepat" in isi
    assert "Tinjau konsep: 1" in isi
    assert "representasi lain tetap di riwayat" in isi


def test_bukti_sah_tidak_membaca_diagnosis_mutable(server):
    uji, _, sesi, payload = server
    assert _post(uji, sesi, payload)[0] == 303
    with uji.buka() as kon:
        # Simulasikan cache mutable menyimpang tanpa mengubah snapshot.
        kon.execute("UPDATE diagnosis SET benar=0, kode_final='K'")
    isi = _halaman(uji, sesi).split('id="hasil-pemetaan"', 1)[1].split('class="kartu-rencana-st"', 1)[0]
    assert "15 tepat" in isi
    assert "Tinjau konsep: 15" not in isi


def test_koreksi_resmi_mengembalikan_ringkasan_sementara(server):
    uji, _, sesi, payload = server
    assert _post(uji, sesi, payload)[0] == 303
    with uji.buka() as kon:
        b = database.isi_sesi(kon, sesi)[0]
        database.simpan_diagnosis(kon, b["jawaban_id"], benar=False,
                                  kode_usulan="H", kode_final="H", manual=True,
                                  alasan="catatan guru")
    isi = _halaman(uji, sesi)
    assert "Ringkasan sementara sesi ini" in isi
    assert 'id="hasil-pemetaan"' not in isi


def test_hasil_pemetaan_tetap_di_balik_palang_kepemilikan_dan_murid(server):
    uji, _, sesi, _ = server
    auth.tambah_akun("lain", "sandi-sintetis-lain", "guru", path=auth.BERKAS_SANDI)
    hasil = [uji.minta(jalur, auth=("lain", "sandi-sintetis-lain"))[:2]
             for jalur in (f"/sesi/{sesi}", "/sesi/999999")]
    assert hasil[0] == hasil[1]
    assert hasil[0][0] == 404
    from http_test_kit import SANDI_MURID
    kode, isi, _ = uji.minta(f"/sesi/{sesi}", auth=("feby", SANDI_MURID))
    assert 'id="hasil-pemetaan"' not in isi
    assert 'id="ringkasan-sementara"' not in isi
    with uji.buka() as kon:
        assert kon.execute("SELECT direview FROM sesi WHERE id=?", (sesi,)).fetchone()[0] is None
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 0


def test_istilah_penilaian_memakai_jagomat(server):
    uji, _, sesi, _ = server
    isi = _halaman(uji, sesi)
    assert "Usulan Jagomat" in isi
    assert "mesin" not in isi.lower()
    assert "Gunakan usulan Jagomat" in isi
    assert "Usulan mesin" not in isi
    assert ">Mesin:</b>" not in isi
