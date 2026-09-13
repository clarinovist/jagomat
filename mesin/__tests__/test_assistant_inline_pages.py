"""Fragmen Pendamping inline tetap escaped, scoped, dan form-valid."""

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import sys

import pytest
import re

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_components
import assistant_inline
import style_stitch


@dataclass
class Konteks:
    jenis: str = "anak"
    versi: str = "versi-aman"
    kategori: str = "ringkasan_netral"


@dataclass
class Chat:
    id: str
    mode_memori: str = "aktif"
    dibuat: int = 0


@dataclass
class Pesan:
    peran: str
    teks: str


class FormParser(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.dalam = 0
        self.maks = 0
        self.form = 0
        self.feed(isi)

    def handle_starttag(self, tag, _attrs):
        if tag == "form":
            self.dalam += 1
            self.form += 1
            self.maks = max(self.maks, self.dalam)

    def handle_endtag(self, tag):
        if tag == "form":
            self.dalam -= 1


def test_tombol_buka_mandiri_punya_form_dan_mode_dalam_form_tidak_nested():
    target = assistant_inline.tujuan_anak(7)
    mandiri = assistant_components.tombol_buka(target)
    assert '<form method="post" action="/pendamping/inline/buka">' in mandiri
    tertanam = assistant_components.tombol_buka(target, dalam_form=True)
    assert "<form" not in tertanam
    assert 'formaction="/pendamping/inline/buka"' in tertanam


def test_persetujuan_dalam_form_host_tidak_membuat_form_bersarang():
    target = assistant_inline.tujuan_sesi(42, nomor=3)
    panel = assistant_components.panel_persetujuan(
        target, sumber={"label": "Soal 3", "level": "P3"}, dalam_form=True
    )
    parser = FormParser('<form id="host">' + panel + "</form>")
    assert parser.form == 1
    assert parser.maks == 1
    assert 'formaction="/pendamping/inline/persetujuan"' in panel
    assert 'required' not in panel


def test_persetujuan_memuat_retensi_penerima_dan_kebijakan_lengkap():
    panel = assistant_components.panel_persetujuan(
        assistant_inline.tujuan_anak(7),
        sumber={"label": "Ringkasan anak", "level": "P3"},
    )
    assert "Pendamping Jagomat" in panel
    assert "DeepSeek" in panel
    assert "180 hari" in panel and "30 hari" in panel
    assert 'href="/kebijakan-privasi"' in panel


@pytest.mark.parametrize("jenis,teks_wajib,pengecualian,teks_dilarang", [
    ("anak", "tahap, level, dan tanggal ketersediaan", "bukan seluruh catatan anak", "jumlah soal sesi"),
    ("sesi", "topik, status, level, dan jumlah soal sesi", "bukan jawaban atau koreksi anak", "tanggal ketersediaan"),
    ("soal", "Teks soal resmi, kunci, dan pembahasan", "Jawaban dan cara anak tidak ikut dikirim", "jumlah soal sesi"),
])
def test_copy_konteks_tepat_untuk_tiga_jenis(
    jenis, teks_wajib, pengecualian, teks_dilarang
):
    target = (assistant_inline.tujuan_anak(7) if jenis == "anak" else
              assistant_inline.tujuan_sesi(42) if jenis == "sesi" else
              assistant_inline.tujuan_sesi(42, nomor=3))
    konteks = Konteks(
        jenis=jenis,
        kategori="soal_resmi" if jenis == "soal" else "ringkasan_netral",
    )
    panel = assistant_components.panel_konteks(
        target, konteks, sumber={"label": jenis, "level": "P3"}
    )
    assert teks_wajib in panel
    assert pengecualian in panel
    assert "layanan AI eksternal untuk Pendamping Jagomat" in panel
    assert "DeepSeek" not in panel
    assert teks_dilarang not in panel


def test_fragmen_escape_teks_model_dan_hanya_satu_composer():
    cid = "chat_" + "a" * 32
    target = assistant_inline.tujuan_anak(7, chat_id=cid)
    chat = Chat(cid)
    panel = assistant_components.panel_chat(
        target, chat, (Pesan("asisten", '<script>alert("x")</script>'),), (chat,),
        sumber={"label": "Ringkasan anak", "level": "P3"},
    )
    assert "<script>" not in panel
    assert "&lt;script&gt;" in panel
    assert panel.count('name="pesan"') == 1
    assert panel.count("pendamping-inline") >= 1
    assert f"chat={cid}" in panel


@pytest.mark.parametrize("dalam_form", [False, True])
def test_composer_blok_dan_preferensi_ringkas_setelah_area_kirim(dalam_form):
    cid = "chat_" + "b" * 32
    chat = Chat(cid)
    panel = assistant_components.panel_chat(
        assistant_inline.tujuan_anak(7, chat_id=cid), chat, (), (chat,),
        sumber={"label": "Ringkasan anak", "level": "P3"},
        status_memori="Memori aktif · belum ada catatan", versi_memori=1,
        dalam_form=dalam_form,
    )
    parser = FormParser(('<form id="host">' if dalam_form else "") + panel
                        + ("</form>" if dalam_form else ""))
    assert parser.maks == 1
    assert parser.form == (1 if dalam_form else 3)
    assert '<div class="pendamping-composer">' in panel
    assert '<textarea id="pesan-inline" name="pesan" rows="5"' in panel
    assert 'formaction="/pendamping/inline/pesan">Kirim</button>' in panel
    assert "Enter membuat baris baru" not in panel
    assert 'name="pesan"' in panel and "required" not in panel
    assert '<details class="pendamping-memori"><summary>Preferensi</summary>' in panel
    assert panel.index('name="pesan"') < panel.index("<summary>Preferensi</summary>")
    assert "Preferensi berlaku lintas percakapan" not in panel


def test_gaya_pendamping_inline_tersedia_di_stylesheet_semua_host():
    css = style_stitch.GAYA_STITCH
    composer = re.search(
        r"^\.pendamping-inline \.pendamping-composer \{([^}]*)\}", css, re.M
    ).group(1)
    textarea = re.search(
        r"\.pendamping-inline \.pendamping-composer textarea \{([^}]*)\}", css
    ).group(1)
    preferensi = re.search(
        r"\.pendamping-inline \.pendamping-memori > summary \{([^}]*)\}", css
    ).group(1)
    batas = re.search(
        r"\.pendamping-inline \.pendamping-transkrip, \.pendamping-inline \.pendamping-composer \{([^}]*)\}", css
    ).group(1)
    assert "grid-template-columns: minmax(0, 1fr)" in composer
    assert "gap: 1rem" in composer and "min-width: 0" in composer
    assert "width: 100%" in batas and f"max-width: {style_stitch.T.LEBAR_KONTEN}" in batas
    assert "min-height: 7.5rem" in textarea
    assert f"min-height: {style_stitch.T.TARGET_SENTUH}" in preferensi
    assert "display: list-item" in preferensi
    assert ".pendamping-inline .pendamping-composer" not in style_stitch.CSS_SESI


def test_preferensi_host_latihan_mematikan_marker_plus_minus_buatan():
    css = style_stitch.GAYA_STITCH
    selektor = ".profil-editorial-st .atur-latihan-st .pendamping-inline .pendamping-memori > summary"
    blok = re.search(r"^" + re.escape(selektor) + r" \{([^}]*)\}", css, re.M).group(1)
    before = re.search(
        r"^" + re.escape(selektor + "::before") + r" \{([^}]*)\}", css, re.M
    ).group(1)
    assert "display: list-item" in blok
    assert f"min-height: {style_stitch.T.TARGET_SENTUH}" in blok
    assert "content: none" in before


def test_riwayat_dalam_form_memakai_post_bukan_tautan_get():
    cid = "chat_" + "c" * 32
    chat = Chat(cid)
    panel = assistant_components.panel_chat(
        assistant_inline.tujuan_sesi(42, nomor=3, chat_id=cid), chat, (), (chat,),
        sumber={"label": "Soal 3", "level": "P3"}, dalam_form=True,
    )
    assert 'formaction="/pendamping/inline/riwayat"' in panel
    assert f'name="pilih_chat" value="{cid}"' in panel
    assert f'name="chat" value="{cid}"' in panel
    assert f"chat={cid}" not in panel


def test_pagination_dan_crud_memori_dalam_form_memakai_satu_data_aksi_per_tombol():
    cid = "chat_" + "d" * 32
    chat = Chat(cid)
    from assistant_store import Memori
    memori = Memori("memori_" + "e" * 32, "akun_" + "a" * 32,
                    "preferensi_orang_tua", "Jawab singkat.", 2, cid, True, 1, None)
    panel = assistant_components.panel_chat(
        assistant_inline.tujuan_sesi(42, nomor=3, chat_id=cid), chat, (), (chat,),
        sumber={"label": "Soal 3", "level": "P3"}, dalam_form=True,
        status_memori="Memori aktif · 1 catatan", versi_memori=3,
        memori=(memori,), halaman_riwayat=2, ada_lagi=True,
    )
    assert 'value="halaman=1"' in panel and 'value="halaman=3"' in panel
    assert 'isi_memori_memori_' in panel
    assert 'formaction="/pendamping/inline/ubah-memori"' in panel
    assert 'formaction="/pendamping/inline/tinjau-hapus-memori"' in panel
    assert 'persetujuan_hapus=1' not in panel
    assert panel.count('name="data_aksi"') >= 5
    assert panel.count('name="memori"') == 0


@pytest.mark.parametrize("target", [
    assistant_inline.tujuan_sesi(42, nomor=3),
    assistant_inline.tujuan_anak(7, "latihan"),
])
def test_tinjauan_hapus_dalam_form_host_tidak_nested_dan_tanpa_auto_consent(target):
    from assistant_store import Memori
    cid = "chat_" + "f" * 32
    chat = Chat(cid)
    item = Memori("memori_" + "a" * 32, "akun_" + "b" * 32,
                  "preferensi_orang_tua", "Gunakan analogi singkat.", 4,
                  cid, True, 1, None)
    panel = assistant_components.panel_tinjauan_hapus_memori(
        target, chat, item, sumber={"label": "Sumber", "level": "P3"},
        dalam_form=True,
    )
    parser = FormParser('<form id="host">' + panel + "</form>")
    assert parser.form == parser.maks == 1
    assert 'name="persetujuan_hapus" value="1"' in panel
    assert 'type="hidden" name="persetujuan_hapus"' not in panel
    assert 'formaction="/pendamping/inline/hapus-memori"' in panel
    assert 'formaction="/pendamping/inline/batal-hapus-memori"' in panel
    assert "Chat sumber tetap ada" in panel and "maksimal 30 hari" in panel


def test_provider_mati_menjaga_histori_lokal_tanpa_composer():
    cid = "chat_" + "b" * 32
    chat = Chat(cid)
    panel = assistant_components.panel_chat(
        assistant_inline.tujuan_anak(7, chat_id=cid), chat,
        (Pesan("pengguna", "Pesan lama"),), (chat,),
        sumber={"label": "Ringkasan anak", "level": "P3"}, provider_aktif=False,
    )
    assert "Pesan lama" in panel
    assert "Pengiriman AI sedang tidak tersedia" in panel
    assert 'name="pesan"' not in panel
