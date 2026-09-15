"""Roundtrip koreksi ringkas melalui HTML dan POST asli, seluruh data sintetis."""
from html.parser import HTMLParser
import re

import pytest

import database
import teacher_pages
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji


class FormKoreksi(HTMLParser):
    """Baca successful controls form host seperti browser tanpa JavaScript."""

    def __init__(self, isi, sesi):
        super().__init__(convert_charrefs=True)
        self.target = f"form-koreksi-{sesi}"
        self.aktif = False
        self.data = {}
        self.nama = None
        self.tag = None
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.aktif = a.get("id") == self.target
        if not self.aktif:
            return
        if tag == "input" and "name" in a and "disabled" not in a:
            if a.get("type") not in ("checkbox", "radio") or "checked" in a:
                self.data[a["name"]] = a.get("value", "")
        if tag in ("select", "textarea"):
            self.nama, self.tag = a["name"], tag
            if tag == "textarea":
                self.data[self.nama] = ""
        if tag == "option" and ("selected" in a or self.nama not in self.data):
            self.data[self.nama] = a["value"]

    def handle_data(self, teks):
        if self.aktif and self.tag == "textarea":
            self.data[self.nama] += teks

    def handle_endtag(self, tag):
        if tag == "form":
            self.aktif = False
        if tag in ("textarea", "select"):
            self.nama = self.tag = None


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Contoh", "P3", pemilik="guru")
        s.sesi = database.buat_sesi(kon, anak, seed=71, level="P3", jumlah_soal=1)
        s.butir = dict(database.isi_sesi(kon, s.sesi)[0])
        s.sid = s.butir["sesi_soal_id"]
        database.tandai_selesai(kon, s.sesi)
    yield s
    s.berhenti()


def isi_awal(s, cara, *, jawaban=None, kode="", belum=False):
    data = {f"jwb_{s.sid}": s.butir["kunci"] if jawaban is None else jawaban,
            f"cara_{s.sid}": cara, f"kode_{s.sid}": kode}
    if belum:
        data[f"belum_{s.sid}"] = "1"
    with s.buka() as kon:
        teacher_pages.simpan_sesi(kon, s.sesi, data)


def form(s):
    status, isi, _ = s.minta(f"/sesi/{s.sesi}", auth=("guru", SANDI_GURU))
    assert status == 200
    return FormKoreksi(isi, s.sesi).data, isi


def kirim(s, data, *, jalur="/konfirmasi", akun=("guru", SANDI_GURU)):
    return s.minta(f"/sesi/{s.sesi}{jalur}", data=data, auth=akun)


def keadaan(s):
    with s.buka() as kon:
        return (dict(database.isi_sesi(kon, s.sesi)[0]),
                [dict(r) for r in kon.execute("SELECT * FROM snapshot_outcome ORDER BY id")],
                [tuple(r) for r in kon.execute("SELECT * FROM konfirmasi_hasil ORDER BY id")])


@pytest.mark.parametrize("cara,benar,kode", [
    ("Aku menghitung.", 1, None),
    ("[pilihan] bingung", 0, "T"),
    ("[pilihan] tebak — aku belum tahu", 0, "N"),
    ("", 0, "N"),
])
def test_default_mesin_roundtrip_tidak_menciptakan_override_atau_pengakuan(server, cara, benar, kode):
    s = server
    isi_awal(s, cara)
    sebelum = keadaan(s)[0]
    data, isi = form(s)
    assert data[f"kode_{s.sid}"] == ""
    assert f"belum_{s.sid}" not in data
    assert "Usulan Jagomat:" in isi
    assert "Dipakai otomatis saat konfirmasi" in isi
    assert kirim(s, data)[0] == 200
    hasil, snapshot, bukti = keadaan(s)
    for key in ("cara", "jawaban", "manual", "belum_pernah", "kode_usulan", "alasan", "malrule_id"):
        assert hasil[key] == sebelum[key], key
    assert hasil["manual"] == 0
    assert hasil["benar"] == benar and hasil["kode_final"] == kode
    assert snapshot[0]["cek_pemahaman"] is None
    assert len(bukti) == 1
    assert kirim(s, form(s)[0])[0] == 200
    assert keadaan(s)[2] == bukti  # Retry bukan snapshot/koreksi baru.


@pytest.mark.parametrize("kode", ["K", "B", "H", "E", "N", "benar", "T"])
def test_override_lama_tetap_dan_kembali_otomatis_mencabut_manual(server, kode):
    s = server
    isi_awal(s, "Cara tertulis", kode=kode)
    if kode == "T":
        with s.buka() as kon:
            b = database.isi_sesi(kon, s.sesi)[0]
            database.simpan_diagnosis(kon, b["jawaban_id"], False, None, "T", manual=True)
    data, isi = form(s)
    assert data[f"kode_{s.sid}"] == kode
    assert "Penilaian guru:" in isi
    assert kirim(s, data)[0] == 200
    hasil, snapshots, bukti = keadaan(s)
    assert hasil["manual"] == 1
    assert snapshots[0]["kode_final"] == (None if kode == "benar" else kode)
    data[f"kode_{s.sid}"] = ""
    assert kirim(s, data)[0] == 200
    hasil, baru, _ = keadaan(s)
    assert hasil["manual"] == 0 and hasil["benar"] == 1
    assert baru[0] == snapshots[0]  # Snapshot lama immutable.


def test_override_sama_dengan_usulan_tetap_keputusan_manual(server):
    s = server
    isi_awal(s, "Cara tertulis")
    data, _ = form(s)
    data[f"kode_{s.sid}"] = "benar"
    assert kirim(s, data)[0] == 200
    assert keadaan(s)[0]["manual"] == 1
    assert form(s)[0][f"kode_{s.sid}"] == "benar"


def test_otomatis_menilai_ulang_jawaban_dan_override_guru_menyimpan_usulan(server):
    s = server
    isi_awal(s, "Cara tertulis")
    data, _ = form(s)
    with s.buka() as kon:
        malrule = dict(database.malrule_soal(kon, s.butir["soal_id"])[0])
    data[f"jwb_{s.sid}"] = malrule["jawaban"]
    assert kirim(s, data)[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["manual"] == 0 and hasil["kode_final"] == malrule["kode"]
    data[f"kode_{s.sid}"] = "E"
    assert kirim(s, data)[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["manual"] == 1 and hasil["kode_final"] == "E"
    assert hasil["kode_usulan"] == malrule["kode"]


@pytest.mark.parametrize("pemahaman", ["", "bisa_menjelaskan", "ragu", "menghafal"])
def test_pemahaman_dan_belum_pernah_satu_konfirmasi(server, pemahaman):
    s = server
    isi_awal(s, "Cara tertulis")
    data, _ = form(s)
    data.update({f"cek_pemahaman_{s.sid}": pemahaman, f"belum_{s.sid}": "1"})
    assert kirim(s, data)[0] == 200
    hasil, snapshots, _ = keadaan(s)
    assert hasil["belum_pernah"] == 1 and hasil["kode_final"] == "T"
    assert hasil["manual"] == 0
    assert snapshots[0]["cek_pemahaman"] == (pemahaman or None)
    del data[f"belum_{s.sid}"]
    assert kirim(s, data)[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["belum_pernah"] == 0 and hasil["benar"] == 1


def test_mesin_belum_yakin_dan_lewati_aman(server):
    s = server
    isi_awal(s, "Cara tidak terpetakan", jawaban="999999")
    data, isi = form(s)
    assert '<summary>Tentukan penilaian — belum dipilih</summary>' in isi
    sebelum = keadaan(s)
    assert kirim(s, data)[0] == 400
    assert keadaan(s) == sebelum
    data[f"dilewati_{s.sid}"] = "1"
    assert kirim(s, data)[0] == 200
    hasil, snapshot, _ = keadaan(s)
    assert hasil["jawaban"] == "999999"
    assert snapshot[0]["dilewati"] == 1
    assert snapshot[0]["jawaban"] == "" and snapshot[0]["kode_final"] is None
    assert "Dilewati dari penilaian — ubah" in form(s)[1]


@pytest.mark.parametrize("pilihan,kode", [("tebak", "N"), ("bingung", "T")])
def test_tambahan_catatan_tidak_menghilangkan_pengakuan_pilihan(server, pilihan, kode):
    s = server
    isi_awal(s, "[pilihan] " + pilihan)
    data, _ = form(s)
    data[f"cara_{s.sid}"] += " — catatan tambahan"
    assert kirim(s, data)[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["cara"] == "[pilihan] " + pilihan + " — catatan tambahan"
    assert hasil["kode_final"] == kode and hasil["manual"] == 0


def test_mengganti_pengakuan_dengan_penjelasan_dapat_menilai_ulang(server):
    s = server
    isi_awal(s, "[pilihan] tebak")
    data, _ = form(s)
    data[f"cara_{s.sid}"] = "Anak menjelaskan hitungan satu per satu."
    assert kirim(s, data)[0] == 200
    assert keadaan(s)[0]["benar"] == 1


def test_hapus_semua_isian_tidak_mengesahkan_jawaban_lama(server):
    s = server
    isi_awal(s, "Cara tertulis")
    data, _ = form(s)
    sebelum = keadaan(s)
    data[f"jwb_{s.sid}"] = data[f"cara_{s.sid}"] = ""
    assert kirim(s, data)[0] == 400
    assert keadaan(s) == sebelum  # Gagal konfirmasi rollback atomik.
    data[f"dilewati_{s.sid}"] = "1"
    assert kirim(s, data)[0] == 200
    hasil, snapshot, _ = keadaan(s)
    assert hasil["jawaban"] == hasil["cara"] == ""
    assert snapshot[0]["dilewati"] == 1


def test_drill_default_tidak_menjadi_menebak_dan_cara_lama_terjaga(server):
    s = server
    with s.buka() as kon:
        kon.execute("UPDATE sesi SET mode='drill' WHERE id=?", (s.sesi,))
    isi_awal(s, "")
    data, isi = form(s)
    assert f'name="cara_{s.sid}"' not in isi
    assert '<option value="N"' not in isi
    assert data[f"kode_{s.sid}"] == ""
    assert kirim(s, data)[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["benar"] == 1 and hasil["manual"] == 0


def test_diagnosis_warisan_tak_diedit_sesuai_usulan_yang_ditampilkan(server):
    s = server
    isi_awal(s, "Cara tertulis")
    with s.buka() as kon:
        b = database.isi_sesi(kon, s.sesi)[0]
        database.simpan_diagnosis(kon, b["jawaban_id"], False, "H", "H", alasan="Usulan tersimpan")
    data, isi = form(s)
    assert "Usulan Jagomat: Perlu memeriksa hitungan" in isi
    assert kirim(s, data)[0] == 200
    assert keadaan(s)[0]["kode_final"] == "H"


def test_hierarki_form_tunggal_dan_palang_enter(server):
    s = server
    isi_awal(s, "[pilihan] bingung")
    data, isi = form(s)
    badan = isi.split("</style>")[-1]
    assert data[f"cara_{s.sid}"] == "Pilihan anak: Aku bingung"
    assert "[pilihan]" not in badan
    assert "Kode (kosong" not in badan and "— pilih —" not in badan
    assert badan.count(f'action="/sesi/{s.sesi}"') == 1
    assert ">Simpan koreksi</button>" not in badan
    assert badan.count(">Konfirmasi hasil</button>") == 1
    assert re.search(r'<button type="submit" form="form-koreksi-\d+" hidden disabled', badan)
    paham = re.search(r'<fieldset class="koreksi-pemahaman-st">(.*?)</fieldset>', badan, re.S)[1]
    pengalaman = re.search(r'<details class="koreksi-opsi-st koreksi-pengalaman-st"[^>]*>(.*?)</details>', badan, re.S)[1]
    assert f'name="belum_{s.sid}"' in pengalaman
    assert "Apakah anak bisa menjelaskan caranya?" in paham
    lewati = re.search(r'<details class="koreksi-opsi-st koreksi-perbaikan-st">(.*?)</details>', badan, re.S)[1]
    assert f'name="dilewati_{s.sid}"' in lewati
    assert "Jawaban dan catatan asli tetap tersimpan" in lewati


@pytest.mark.parametrize("field,nilai", [
    ("belum", "0"), ("belum", "on"), ("dilewati", "0"),
    ("cek_pemahaman", "paham"), ("kode", "X"), ("kode", "T"),
])
def test_post_manipulatif_ditolak_sebelum_efek(server, field, nilai):
    s = server
    isi_awal(s, "Cara awal")
    data, _ = form(s)
    data[f"jwb_{s.sid}"] = "Rusak jika ditulis"
    data[f"{field}_{s.sid}"] = nilai
    sebelum = keadaan(s)
    assert kirim(s, data)[0] == 400
    assert keadaan(s) == sebelum


def test_t_baru_http_ditolak_meski_outcome_otomatis_valid(server):
    s = server
    isi_awal(s, "Cara awal")
    data, _ = form(s)
    data[f"kode_{s.sid}"] = "T"
    sebelum = keadaan(s)
    assert kirim(s, data)[0] == 400
    assert keadaan(s) == sebelum


def test_t_baru_handler_lama_tidak_menciptakan_override(server):
    s = server
    isi_awal(s, "Cara awal")
    data, _ = form(s)
    data[f"kode_{s.sid}"] = "T"
    assert kirim(s, data, jalur="")[0] == 200
    hasil = keadaan(s)[0]
    assert hasil["kode_final"] != "T" and hasil["manual"] == 0
    assert hasil["belum_pernah"] == 0


def test_post_lama_parsial_tidak_menghapus_butir_yang_tidak_dikirim(server):
    s = server
    isi_awal(s, "Cara awal")
    sebelum = keadaan(s)
    assert kirim(s, {}, jalur="")[0] == 200
    assert keadaan(s) == sebelum


def test_handler_simpan_lama_tetap_bukan_konfirmasi(server):
    s = server
    isi_awal(s, "[pilihan] tebak")
    data, _ = form(s)
    assert kirim(s, data, jalur="")[0] == 200
    hasil, snapshot, bukti = keadaan(s)
    assert hasil["cara"] == "[pilihan] tebak" and hasil["manual"] == 0
    assert snapshot == bukti == []


def test_murid_dan_butir_asing_tidak_bisa_mengubah_hasil(server):
    s = server
    isi_awal(s, "Cara awal")
    data, _ = form(s)
    sebelum = keadaan(s)
    assert kirim(s, {**data, "kode_999999": "benar"})[0] == 400
    status, badan, _ = kirim(s, data, akun=("feby", SANDI_MURID))
    assert status == 401  # Basic murid tidak membuka permukaan guru.
    assert "Usulan Jagomat:" not in badan and "Cara awal" not in badan
    assert keadaan(s) == sebelum
