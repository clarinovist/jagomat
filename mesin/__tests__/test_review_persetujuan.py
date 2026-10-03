"""Regression: label centang persetujuan & kontras tombol pembatalan.

Anomali dari screenshot sesi #62 (mode privat / tanpa JS):
1. Label "Saya memahami sesi ini akan dibatalkan" dirender vertikal satu huruf
   per baris.
2. Checkbox tampak sebagai kotak putih kosong tanpa label.
3. Tombol "Batalkan sesi" pucat, lebih lemah dari CTA coral "Lihat rencana
   berikutnya", sehingga membingungkan.

Akar masalah 1-2: .koreksi-centang-st adalah wadah *daftar* centang (flex row
berisi <label>), bukan label pembungkus checkbox. Dipakai pada <label> yang
membungkus checkbox, teks label jatuh ke baris berikutnya.
"""
from html.parser import HTMLParser

import pytest

import database
import design_tokens as T
import teacher_pages
from style_stitch import gaya_stitch


class LabelPersetujuan(HTMLParser):
    """Ambil label centang beserta checkbox yang dibungkusnya."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.label = None
        self._depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label" and "koreksi-persetujuan-st" in a.get("class", "").split():
            self._depth = 1
            self.label = {"class": a["class"], "teks": "", "checkbox": False}
            return
        if self._depth:
            self._depth += 1
            if tag == "input" and a.get("type") == "checkbox":
                self.label["checkbox"] = True

    def handle_data(self, teks):
        if self._depth and self.label is not None:
            self.label["teks"] += teks

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1
            if self._depth == 0 and tag == "label":
                self.label["teks"] = " ".join(self.label["teks"].split())


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "persetujuan-sintetis.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


def _sesi_terkonfirmasi(kon):
    """Sesi yang pernah dikonfirmasi memicu cabang form pembatalan (onsubmit)."""
    siswa = database.tambah_siswa(kon, "Peserta Persetujuan", pemilik="guru")
    sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=3)
    database.tandai_selesai(kon, sesi)
    butir = database.isi_sesi(kon, sesi)
    jid = database.simpan_jawaban(kon, butir[0]["sesi_soal_id"], butir[0]["kunci"], "Cara asli")
    database.simpan_diagnosis(kon, jid, True, None, None)
    database.konfirmasi_hasil(kon, sesi, "guru", dilewati=set(b["sesi_soal_id"] for b in butir[1:]))
    return sesi


def test_label_persetujuan_inline_dan_checkbox_terikat(db):
    """Label centang harus inline (checkbox + teks satu baris), bukan vertikal."""
    with database.buka(db) as kon:
        sesi = _sesi_terkonfirmasi(kon)
        html = teacher_pages.halaman_sesi_stitch(kon, sesi, privat=True).decode()

    label = LabelPersetujuan(html).label
    assert label is not None, "label centang persetujuan tidak ditemukan"
    assert label["checkbox"], "checkbox tidak dibungkus label"
    assert "Saya memahami sesi ini akan dibatalkan" in label["teks"]
    # Kelas wadah daftar centang tidak boleh dipakai sebagai label pembungkus.
    # (Cek markup, bukan CSS: definisi kelas itu sendiri wajar ada di stylesheet.)
    # Pola serupa juga ada di checkbox "Sertakan dalam pemetaan".
    assert '<label class="koreksi-centang-st"' not in html
    assert html.count('koreksi-persetujuan-st') >= 2, (
        "label centang lain (Sertakan dalam pemetaan) harus ikut memakai kelas yang sama"
    )


def test_css_label_persetujuan_inline_flex(db):
    """CSS label centang harus inline-flex agar checkbox dan teks sejajar."""
    css = gaya_stitch()
    aturan = ".koreksi-editorial-st .koreksi-persetujuan-st {"
    assert aturan in css
    blok = css.split(aturan, 1)[1].split("}", 1)[0]
    assert "display: inline-flex" in blok
    assert "align-items: center" in blok


def test_tombol_batalkan_sesi_tampak_destruktif(db):
    """Tombol pembatalan harus solid galat, bukan pucat seperti CTA utama."""
    css = gaya_stitch()
    aturan = ".koreksi-editorial-st .form-pembatalan-st .tombol-kecil-st {"
    assert aturan in css
    blok = css.split(aturan, 1)[1].split("}", 1)[0]
    assert f"background: {T.TEKS_GALAT}" in blok
    assert f"color: {T.TEKS_PUTIH}" in blok
    # Pastikan bukan latar pucat generik.
    assert f"background: {T.LATAR_GALAT}" not in blok
