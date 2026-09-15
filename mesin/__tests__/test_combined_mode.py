"""Mode gabungan harus eksplisit dan konsisten sampai penilaian anak."""

from html.parser import HTMLParser

import pytest

import database
import students
import teacher_pages
import web
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji


class FormGabungan(HTMLParser):
    """Pisahkan kontrol berdasarkan form agar mode form lain tidak ikut teruji."""

    def __init__(self, html):
        super().__init__()
        self.form = {}
        self.aksi = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.aksi = attrs.get("action", "")
            self.form[self.aksi] = []
        elif self.aksi is not None:
            self.form[self.aksi].append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == "form":
            self.aksi = None


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "gabungan-sintetis.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    # Seed ini menghasilkan soal 36 km/jam × 10 jam, tanpa mengganti generator.
    monkeypatch.setattr(web.random, "randint", lambda a, b: 570)
    with s.buka() as kon:
        s.siswa = database.tambah_siswa(kon, "feby", "P5", pemilik="guru")
    yield s
    s.berhenti()


def _data(mode=None):
    data = [("topik", "pola-bilangan"), ("topik", "aritmatika-lanjut"), ("jumlah_soal", "4")]
    if mode is not None:
        data.append(("mode", mode))
    return data


def _buat(server, mode=None):
    status, html, _ = server.minta(
        f"/sesi-gabungan/{server.siswa}", auth=("guru", SANDI_GURU), data=_data(mode),
    )
    assert status == 200
    with server.buka() as kon:
        sesi = dict(kon.execute("SELECT * FROM sesi ORDER BY id DESC LIMIT 1").fetchone())
    return sesi, html


def test_form_gabungan_default_cepat_dan_form_biasa_tetap_diagnostik(server):
    status, html, _ = server.minta(f"/anak/{server.siswa}", auth=("guru", SANDI_GURU))
    assert status == 200
    form = FormGabungan(html).form
    gabungan = form[f"/sesi-gabungan/{server.siswa}"]
    mode = [a for t, a in gabungan if t == "input" and a.get("name") == "mode"]
    assert len(mode) == 2
    assert {a["value"] for a in mode} == {"drill", "diagnostik"}
    assert [a["value"] for a in mode if "checked" in a] == ["drill"]
    assert all(a.get("type") == "radio" for a in mode)
    assert any(a.get("role") == "radiogroup" and a.get("aria-labelledby") for _, a in gabungan)
    assert not any(a.get("name") in {"timer_mode", "durasi_menit", "timer_auto"} for _, a in gabungan)
    biasa = form[f"/sesi-baru/{server.siswa}"]
    assert [a["value"] for t, a in biasa if t == "input" and a.get("name") == "mode" and "checked" in a] == ["diagnostik"]


@pytest.mark.parametrize("mode,harapan", [(None, "drill"), ("drill", "drill"), ("diagnostik", "diagnostik")])
def test_http_mode_gabungan_tersimpan_sampai_penilaian_360(server, mode, harapan):
    sesi, _ = _buat(server, mode)
    assert sesi["mode"] == harapan
    assert (sesi["timer_mode"], sesi["timer_auto"]) == ("tanpa", 0)
    with server.buka() as kon:
        butir = next(b for b in database.isi_sesi(kon, sesi["id"])
                     if b["template_id"] == "kecepatan_jarak_waktu" and b["kunci"] == "360")
        ssid = butir["sesi_soal_id"]
        assert students.hasil_murid(kon, server.siswa, sesi["id"]) is None
    status, html, _ = server.minta(f'/murid/kerjakan/{sesi["id"]}', auth=("feby", SANDI_MURID))
    assert status == 200
    assert (f'name="cara_{ssid}"' in html) == (harapan == "diagnostik")
    status, _, _ = server.minta(
        f'/murid/kerjakan/{sesi["id"]}', auth=("feby", SANDI_MURID),
        data={f"jwb_{ssid}": "360", "aksi": "selesai"},
    )
    assert status == 200
    with server.buka() as kon:
        b = next(b for b in database.isi_sesi(kon, sesi["id"]) if b["sesi_soal_id"] == ssid)
        assert b["jawaban"] == "360" and b["cara"] == ""
        assert bool(b["benar"]) == (harapan == "drill")
        assert b["kode_final"] == (None if harapan == "drill" else "N")
    assert server.minta(f'/sesi/{sesi["id"]}', auth=("guru", SANDI_GURU))[0] == 200
    status, html, _ = server.minta(f'/murid/hasil/{sesi["id"]}', auth=("feby", SANDI_MURID))
    assert status == 200
    assert ('>Benar</span>' in html) == (harapan == "drill")


@pytest.mark.parametrize("nilai", [[""], ["cepat"], ["<script>"], ["drill", "diagnostik"], ["drill", "drill"]])
def test_mode_http_tidak_sah_tidak_menulis_apapun(server, nilai):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    status, html, _ = server.minta(
        f"/sesi-gabungan/{server.siswa}", auth=("guru", SANDI_GURU),
        data=_data() + [("mode", m) for m in nilai],
    )
    assert status == 400
    assert "Mode tidak dikenal" in html
    assert "<script>" not in html
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("mode", ["drill", "diagnostik", "asing"])
def test_mode_tidak_melewati_palang_kepemilikan(server, mode):
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, "Peserta Keluarga Lain", "P5", pemilik="guru2")
        sebelum = tuple(kon.iterdump())
    hasil = [server.minta(f"/sesi-gabungan/{sid}", auth=("guru", SANDI_GURU), data=_data(mode))
             for sid in (asing, 999999)]
    assert hasil[0][0] == hasil[1][0] == 404
    assert hasil[0][1] == hasil[1][1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("mode", ["", "asing", None])
def test_service_menolak_mode_tidak_sah_sebelum_generator(db, monkeypatch, mode):
    def dilarang(*args, **kwargs):
        raise AssertionError("Generator tidak boleh dipanggil untuk mode tidak sah")

    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Peserta Sintetis", "P5", pemilik="guru")
        sebelum = tuple(kon.iterdump())
        monkeypatch.setattr(database, "buat_lembar", dilarang)
        with pytest.raises(ValueError, match="mode tidak dikenal"):
            database.buat_sesi_gabungan(kon, siswa, 570, ["pola-bilangan", "aritmatika-lanjut"], mode=mode)
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("mode,jawaban,cara,belum,benar,kode", [
    ("drill", "361", "", False, False, None),
    ("drill", "360", "", True, False, None),
    ("diagnostik", "360", "36 dikali 10", False, True, None),
])
def test_aturan_penilaian_tidak_dilonggarkan(server, mode, jawaban, cara, belum, benar, kode):
    sesi, _ = _buat(server, mode)
    with server.buka() as kon:
        butir = next(b for b in database.isi_sesi(kon, sesi["id"])
                     if b["template_id"] == "kecepatan_jarak_waktu" and b["kunci"] == "360")
        ssid = butir["sesi_soal_id"]
    data = {f"jwb_{ssid}": jawaban, f"cara_{ssid}": cara, "aksi": "selesai"}
    if belum:
        data[f"blm_{ssid}"] = "1"
    assert server.minta(f'/murid/kerjakan/{sesi["id"]}', auth=("feby", SANDI_MURID), data=data)[0] == 200
    with server.buka() as kon:
        b = next(b for b in database.isi_sesi(kon, sesi["id"]) if b["sesi_soal_id"] == ssid)
        assert bool(b["benar"]) == benar
        assert b["kode_final"] == kode
        assert b["cara"] == cara and b["jawaban"] == jawaban


def test_default_form_sepuluh_soal_gabungan_bisa_dibuka(server):
    status, _, _ = server.minta(
        f"/sesi-gabungan/{server.siswa}", auth=("guru", SANDI_GURU),
        data=[("topik", "pola-bilangan"), ("topik", "teori-bilangan"),
              ("jumlah_soal", "10"), ("mode", "drill")],
    )
    assert status == 200
    with server.buka() as kon:
        sesi = kon.execute("SELECT id, mode FROM sesi ORDER BY id DESC LIMIT 1").fetchone()
        assert sesi["mode"] == "drill"
        assert len(database.isi_sesi(kon, sesi["id"])) == 10
    assert server.minta(f'/sesi/{sesi["id"]}', auth=("guru", SANDI_GURU))[0] == 200
    assert server.minta(f'/murid/kerjakan/{sesi["id"]}', auth=("feby", SANDI_MURID))[0] == 200


def test_default_service_dan_histori_lama_tidak_berubah(server):
    with server.buka() as kon:
        lama = database.buat_sesi_gabungan(
            kon, server.siswa, 570, ["pola-bilangan", "aritmatika-lanjut"],
            level="P5", jumlah_soal=4,
        )
        assert kon.execute("SELECT mode FROM sesi WHERE id = ?", (lama,)).fetchone()[0] == "diagnostik"
        data = {}
        for b in database.isi_sesi(kon, lama):
            ssid = b["sesi_soal_id"]
            data.update({f"jwb_{ssid}": b["kunci"], f"cara_{ssid}": "Saya hitung", f"kode_{ssid}": "benar"})
        teacher_pages.simpan_sesi(kon, lama, data)
        database.tandai_selesai(kon, lama)
        kon.execute("UPDATE sesi SET direview = datetime('now') WHERE id = ?", (lama,))
        database.konfirmasi_hasil(kon, lama, "guru")
        sesi_lama = tuple(kon.execute("SELECT * FROM sesi WHERE id = ?", (lama,)).fetchone())
        butir_lama = tuple(tuple(b) for b in database.isi_sesi(kon, lama))
        snapshot_lama = tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome"))
        kejadian_lama = tuple(tuple(b) for b in kon.execute("SELECT * FROM kejadian_belajar"))
    baru, _ = _buat(server)
    assert baru["mode"] == "drill"
    assert server.minta(f'/sesi/{lama}', auth=("guru", SANDI_GURU))[0] == 200
    with server.buka() as kon:
        assert tuple(kon.execute("SELECT * FROM sesi WHERE id = ?", (lama,)).fetchone()) == sesi_lama
        assert tuple(tuple(b) for b in database.isi_sesi(kon, lama)) == butir_lama
        assert tuple(tuple(b) for b in kon.execute("SELECT * FROM snapshot_outcome")) == snapshot_lama
        assert tuple(tuple(b) for b in kon.execute("SELECT * FROM kejadian_belajar")) == kejadian_lama
