"""Pemulihan konfirmasi melalui HTTP nyata dengan data sintetis saja."""
import re

import pytest

import auth
import database
import teacher_pages
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji
from test_teacher_corrections import FormKoreksi


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Contoh", "P3", pemilik="guru")
        s.sesi = database.buat_sesi(kon, anak, seed=71, level="P3", jumlah_soal=4)
        s.butir = [dict(b) for b in database.isi_sesi(kon, s.sesi)]
        data = {}
        for b in s.butir:
            sid = b["sesi_soal_id"]
            data.update({f"jwb_{sid}": b["kunci"], f"cara_{sid}": "Menghitung satu per satu.", f"kode_{sid}": ""})
        teacher_pages.simpan_sesi(kon, s.sesi, data)
        database.tandai_selesai(kon, s.sesi)
    yield s
    s.berhenti()


def _form(s):
    status, isi, _ = s.minta(f"/sesi/{s.sesi}", auth=("guru", SANDI_GURU))
    assert status == 200
    return FormKoreksi(isi, s.sesi).data


def _kirim(s, data, **kwargs):
    return s.minta(f"/sesi/{s.sesi}/konfirmasi", data=data, auth=("guru", SANDI_GURU), **kwargs)


def _keadaan(s):
    with s.buka() as kon:
        return tuple(kon.iterdump())


def _belum_lengkap(s, data):
    for b in s.butir[:2]:
        sid = b["sesi_soal_id"]
        data.update({f"jwb_{sid}": "999999", f"cara_{sid}": "Cara baru <script>alert(1)</script>", f"kode_{sid}": ""})
    return data


def test_gagal_menampilkan_semua_nomor_dan_draf_tanpa_menyimpan(server):
    s = server
    data = _belum_lengkap(s, _form(s))
    ketiga, keempat = [b["sesi_soal_id"] for b in s.butir[2:]]
    data.update({f"cek_pemahaman_{ketiga}": "ragu", f"belum_{ketiga}": "1",
                 f"dilewati_{keempat}": "1", "sertakan_pemetaan": "1"})
    sebelum = _keadaan(s)
    kode, isi, header = _kirim(s, data)
    assert kode == 400
    assert _keadaan(s) == sebelum
    assert "Ada 2 soal yang perlu ditinjau" in isi
    assert "outcome" not in isi
    assert 'role="alert"' in isi
    assert "belum disimpan" in isi
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert "<script>alert(1)</script>" not in isi
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in isi
    assert FormKoreksi(isi, s.sesi).data == data
    for b in s.butir[:2]:
        sid = b["sesi_soal_id"]
        assert f'href="#tinjau-soal-{sid}"' in isi
        assert f'id="tinjau-soal-{sid}"' in isi
        assert f'id="masalah-soal-{sid}"' in isi
        kontrol = re.search(rf'<select[^>]*id="kode-{sid}"[^>]*>', isi)[0]
        assert 'aria-invalid="true"' in kontrol
        assert f'aria-describedby="masalah-soal-{sid}"' in kontrol
    for b in s.butir[2:]:
        assert f'href="#tinjau-soal-{b["sesi_soal_id"]}"' not in isi
    assert isi.count(">Konfirmasi hasil</button>") == 1
    assert '<option value="" selected>Gunakan usulan mesin</option>' not in isi.split('id="kode-', 1)[1].split('</select>', 1)[0]

    pulih = FormKoreksi(isi, s.sesi).data
    for b in s.butir[:2]:
        pulih[f"kode_{b['sesi_soal_id']}"] = "H"
    assert _kirim(s, pulih)[0] == 200
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM snapshot_outcome").fetchone()[0] == 4
    assert _kirim(s, _form(s))[0] == 200
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0] == 1


@pytest.mark.parametrize("opt_in_awal", [False, True])
def test_konfirmasi_ulang_gagal_membuka_draf_dan_mempertahankan_bukti(server, opt_in_awal):
    s = server
    data = _form(s)
    if opt_in_awal:
        data["sertakan_pemetaan"] = "1"
    assert _kirim(s, data)[0] == 200
    data = _belum_lengkap(s, _form(s))
    if opt_in_awal:
        data.pop("sertakan_pemetaan")
    else:
        data["sertakan_pemetaan"] = "1"
    sebelum = _keadaan(s)
    kode, isi, _ = _kirim(s, data)
    assert kode == 400 and _keadaan(s) == sebelum
    assert FormKoreksi(isi, s.sesi).data == data
    assert "Konfirmasi perubahan belum berhasil" in isi
    assert "Hasil sebelumnya tetap tersimpan" in isi
    assert "Hasil saat ini sudah sah" not in isi
    assert "Lihat rencana berikutnya" not in isi
    assert '<details class="panduan-edit-hasil-st">' not in isi
    assert isi.count(">Konfirmasi ulang</button>") == 1
    assert "Pilihan ini belum disimpan" in isi


@pytest.mark.parametrize("mode", ["diagnostik", "drill"])
def test_payload_parsial_kosong_dan_lewati_eksplisit(server, mode):
    s = server
    with s.buka() as kon:
        kon.execute("UPDATE sesi SET mode=? WHERE id=?", (mode, s.sesi))
    _form(s)
    sid = s.butir[0]["sesi_soal_id"]
    data = {f"jwb_{sid}": "", f"cara_{sid}": ""}
    sebelum = _keadaan(s)
    kode, isi, _ = _kirim(s, data)
    assert kode == 400 and _keadaan(s) == sebelum
    assert "Ada 1 soal yang perlu ditinjau" in isi
    assert "Belum ada jawaban atau cara yang bisa dinilai" in isi
    pulih = FormKoreksi(isi, s.sesi).data
    assert pulih[f"jwb_{sid}"] == ""
    pulih[f"dilewati_{sid}"] = "1"
    assert _kirim(s, pulih)[0] == 200


@pytest.mark.parametrize("rusak,alasan", [
    ("tanpa_diagnosis", "penilaian"),
    ("salah_tanpa_kode", "penilaian"),
    ("benar_berkode", "tidak_konsisten"),
    ("benar_bermalrule", "tidak_konsisten"),
])
def test_domain_mempertahankan_semua_guard_kelengkapan(server, rusak, alasan):
    import learning_cycle_service as layanan

    s = server
    b = s.butir[0]
    sid = b["sesi_soal_id"]
    with s.buka() as kon:
        jawaban_id = database.isi_sesi(kon, s.sesi)[0]["jawaban_id"]
        if rusak == "tanpa_diagnosis":
            kon.execute("DELETE FROM diagnosis WHERE jawaban_id=?", (jawaban_id,))
        else:
            database.simpan_diagnosis(
                kon, jawaban_id, rusak != "salah_tanpa_kode", None,
                "K" if rusak == "benar_berkode" else None,
                "m-uji" if rusak == "benar_bermalrule" else None,
            )
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError, match="outcome belum lengkap"):
            database.konfirmasi_hasil(kon, s.sesi, guru="guru")
        with pytest.raises(layanan.KonfirmasiBelumLengkap) as galat:
            layanan.konfirmasi_dari_form(kon, s.sesi, "guru", {})
        assert galat.value.masalah == ((sid, b["nomor"], alasan),)
        assert tuple(kon.iterdump()) == sebelum
        database.konfirmasi_hasil(kon, s.sesi, guru="guru", dilewati={sid})
        assert kon.execute("SELECT dilewati FROM snapshot_outcome WHERE sesi_soal_id=?", (sid,)).fetchone()[0] == 1


def test_sesi_belum_selesai_tidak_disamarkan_sebagai_kelengkapan(server):
    s = server
    data = _belum_lengkap(s, _form(s))
    with s.buka() as kon:
        kon.execute("UPDATE sesi SET selesai=NULL WHERE id=?", (s.sesi,))
    sebelum = _keadaan(s)
    kode, isi, _ = _kirim(s, data)
    assert kode == 400 and "sesi belum selesai" in isi
    assert "Ada 2 soal yang perlu ditinjau" not in isi
    assert f'id="form-koreksi-{s.sesi}"' not in isi
    assert _keadaan(s) == sebelum


def test_service_gagal_rollback_meski_pemanggil_menangkap_exception(server):
    import learning_cycle_service as layanan

    s = server
    data = _belum_lengkap(s, _form(s))
    data = {k: v for k, v in data.items() if not k.startswith("hadir_")}
    sebelum = _keadaan(s)
    with s.buka() as kon:
        with pytest.raises(layanan.KonfirmasiBelumLengkap):
            layanan.konfirmasi_dari_form(kon, s.sesi, "guru", data)
        assert tuple(kon.iterdump()) == sebelum
    assert _keadaan(s) == sebelum


def test_form_tanpa_jawaban_tersimpan_bisa_dipulihkan(server):
    s = server
    _form(s)
    sid = s.butir[0]["sesi_soal_id"]
    with s.buka() as kon:
        kon.execute("DELETE FROM diagnosis WHERE jawaban_id IN (SELECT id FROM jawaban WHERE sesi_soal_id=?)", (sid,))
        kon.execute("DELETE FROM jawaban WHERE sesi_soal_id=?", (sid,))
    sebelum = _keadaan(s)
    kode, isi, _ = _kirim(s, {})
    assert kode == 400 and _keadaan(s) == sebelum
    assert "Belum ada jawaban atau cara yang bisa dinilai" in isi
    data = FormKoreksi(isi, s.sesi).data
    data[f"jwb_{sid}"] = s.butir[0]["kunci"]
    data[f"cara_{sid}"] = "Menghitung dengan teliti."
    assert _kirim(s, data)[0] == 200


def test_admin_dapat_memulihkan_tanpa_memalsukan_peran_guru(server):
    s = server
    data = _belum_lengkap(s, _form(s))
    auth.tambah_akun("pengelola-uji", SANDI_GURU, "admin", path=auth.BERKAS_SANDI)
    sebelum = _keadaan(s)
    kode, isi, _ = s.minta(f"/sesi/{s.sesi}/konfirmasi", data=data, auth=("pengelola-uji", SANDI_GURU))
    assert kode == 400 and _keadaan(s) == sebelum
    assert FormKoreksi(isi, s.sesi).data == data
    assert "Bahas dengan Pendamping" not in isi


def test_field_asing_dan_origin_tidak_memantulkan_draf(server):
    s = server
    data = _belum_lengkap(s, _form(s))
    sebelum = _keadaan(s)
    for tambahan, headers, status in [({"kode_999999": "H"}, {}, 400), ({}, {"Origin": "https://asing.invalid"}, 403)]:
        kode, isi, _ = _kirim(s, {**data, **tambahan}, headers=headers)
        assert kode == status
        assert f'id="form-koreksi-{s.sesi}"' not in isi
        assert "Cara baru" not in isi
        assert _keadaan(s) == sebelum


def test_pemulihan_tidak_membuka_sesi_keluarga_lain_atau_murid(server):
    s = server
    data = _belum_lengkap(s, _form(s))
    auth.tambah_akun("guru-lain", SANDI_GURU, "guru", path=auth.BERKAS_SANDI)
    sebelum = _keadaan(s)
    asing = s.minta(f"/sesi/{s.sesi}/konfirmasi", data=data, auth=("guru-lain", SANDI_GURU))
    hilang = s.minta("/sesi/999999/konfirmasi", data=data, auth=("guru-lain", SANDI_GURU))
    assert asing[:2] == hilang[:2] and asing[0] == 404
    for akun in (None, ("feby", SANDI_MURID)):
        kode, isi, _ = s.minta(f"/sesi/{s.sesi}/konfirmasi", data=data, auth=akun)
        assert kode == 401 and "Anak Contoh" not in isi
        assert "Cara baru" not in isi
    assert _keadaan(s) == sebelum
