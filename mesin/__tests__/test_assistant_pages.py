"""Kontrak renderer Pendamping dengan objek sintetis, tanpa DB/provider."""

import html
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_pages as pages
from assistant_style import GAYA_PENDAMPING


CHAT_ID = "chat_" + "a" * 32
MEMORI_ID = "memori_" + "b" * 32
USULAN_ID = "usulan_" + "c" * 32


class Markup(HTMLParser):
    """Baca atribut DOM, bukan pencarian teks yang bisa mengenai CSS."""

    def __init__(self, isi):
        super().__init__()
        self.elemen = []
        self.forms = []
        self.form = None
        self.feed(isi.decode() if isinstance(isi, bytes) else isi)

    def handle_starttag(self, tag, attrs):
        nilai = dict(attrs)
        self.elemen.append((tag, nilai))
        if tag == 'form':
            self.form = dict(action=nilai.get('action'), inputs=[])
            self.forms.append(self.form)
        elif tag == 'input' and self.form is not None:
            self.form['inputs'].append(nilai)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form = None

    def ambil(self, tag, **attrs):
        return [a for t, a in self.elemen if t == tag and all(
            a.get(k) == v for k, v in attrs.items()
        )]


def chat(**kw):
    data = dict(id=CHAT_ID, dibuat=1789186800, diperbarui=1789187000,
                mode_memori="aktif", context_kind=None)
    data.update(kw)
    return NS(**data)


def memori(**kw):
    data = dict(id=MEMORI_ID, isi="Jawab ringkas dengan contoh konkret.",
                versi=3, dikonfirmasi=True, sumber_chat_id=CHAT_ID)
    data.update(kw)
    return NS(**data)


def usulan(**kw):
    data = dict(id=USULAN_ID, sesi_id=None, versi=2, hash_usulan="hash-sintetis",
                chat_id=CHAT_ID, sumber_request_id="asal-sintetis", status="diusulkan",
                payload_json=json.dumps(dict(topik_id="pola-bilangan", level="P3",
                                             jumlah_soal=10, template_ids=["deret_aritmetika"])))
    data.update(kw)
    return NS(**data)


@pytest.fixture
def proyeksi(monkeypatch):
    """Stub kontrak helper: unit renderer tidak mengulang logika/query helper."""
    modul = NS(label_chat=lambda c: "LABEL RESMI " + c.id,
               ringkasan_usulan=lambda payload: dict(topik="Pola Bilangan", level="P3",
                    jumlah=10, materi=(("Pola bilangan", 10, "deret_aritmetika"),)))
    monkeypatch.setitem(sys.modules, "assistant_view", modul)
    return modul


@pytest.mark.parametrize('modifier,token', [('sekunder', 'TEKS_UTAMA'), ('bahaya', 'TEKS_GALAT')])
def test_link_tombol_modifier_mengalahkan_warna_primary(modifier, token):
    import design_tokens as T
    # Specificity selector link primary adalah (0,2,1). Modifier wajib sama
    # atau lebih kuat, bukan hanya (0,2,0) yang membuat teks putih di atas putih.
    selector = '.pendamping-halaman a.pendamping-tombol.pendamping-' + modifier
    cocok = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', GAYA_PENDAMPING)
    assert cocok is not None
    assert re.search(r'(?:^|;)\s*color\s*:\s*' + re.escape(getattr(T, token)) + r'\s*;', cocok.group(1))
    primary = '.pendamping-halaman a.pendamping-tombol {'
    assert GAYA_PENDAMPING.index(selector) > GAYA_PENDAMPING.index(primary)


def test_bingkai_generic_tanpa_navigasi_privat():
    dom = Markup(pages._bingkai("Tidak ditemukan", '<h1 id="judul-pendamping">Tidak ditemukan</h1>'))
    assert not dom.ambil("nav", **{"aria-label": "Navigasi Pendamping"})
    assert not [a for a in dom.ambil("a") if a.get("href", "").startswith("/pendamping")]


def test_awal_hanya_satu_composer_dan_post_chat_baru():
    isi = pages.halaman_awal((), "", "req-sintetis")
    dom = Markup(isi)
    assert len(dom.ambil("form", action="/pendamping/chat-baru")) == 1
    assert len(dom.ambil("textarea", name="pesan_awal")) == 1
    assert "required" in dom.ambil("textarea")[0]
    assert dom.ambil("a", href="/pendamping/tanpa-memori")
    assert len(dom.ambil("a", href="/pendamping")) == 1


def test_memori_daftar_editor_dan_hapus_tidak_langsung():
    isi = pages.halaman_memori((memori(),), aktif=True, versi=4)
    dom = Markup(isi)
    assert not dom.ambil("form", action=f"/pendamping/memori/{MEMORI_ID}/ubah")
    assert not dom.ambil("form", action=f"/pendamping/memori/{MEMORI_ID}/hapus")
    assert not dom.ambil("form", action="/pendamping/memori/hapus-semua")
    assert not dom.ambil("a", href=f"/pendamping/memori/{MEMORI_ID}/ubah")


def test_usulan_hasil_tidak_memakai_pointer_sesi_mentah(proyeksi):
    isi = pages._kartu_usulan((usulan(sesi_id=991),))
    dom = Markup(isi)
    assert not dom.ambil("a", href="/sesi/991")
    assert dom.ambil("a", href=f"/pendamping/usulan/{USULAN_ID}")


def test_gaya_multiline_tanpa_penutup_overflow():
    rapat = "".join(GAYA_PENDAMPING.split())
    assert "white-space:pre-wrap" in rapat
    assert "overflow-x:hidden" not in rapat
    assert "overflow:hidden" not in rapat
    assert "font:" in rapat or "font-family:" in rapat


def test_awal_tanpa_memori_tetap_satu_form():
    isi = pages.halaman_awal((), request_id="req-sintetis", mode="tanpa_memori")
    dom = Markup(isi)
    assert dom.ambil("input", name="mode", value="tanpa_memori")
    assert len(dom.ambil("form")) == 1
    assert "tetap tersimpan" in isi.decode()


def test_galat_awal_kosong_escaped_dan_terkait_input():
    isi = pages.halaman_awal((), '<script>galat</script>', '"<req>')
    dom = Markup(isi)
    assert "&lt;script&gt;galat&lt;/script&gt;" in isi.decode()
    assert not dom.ambil("script")
    assert "galat-pendamping" in dom.ambil("textarea")[0]["aria-describedby"]
    assert dom.ambil("input", name="request_id", value='"<req>')
    assert dom.ambil("textarea")[0]["maxlength"] == "8000"


def test_riwayat_label_helper_stabil_aktif_escaped_dan_tidak_ganda(proyeksi):
    proyeksi.label_chat = lambda c: '<b>Label</b> ' + c.id
    isi = pages.halaman_riwayat((chat(),), halaman=2, ada_lagi=True, chat_id=CHAT_ID)
    dom = Markup(isi)
    entri = dom.ambil("a", href=f"/pendamping/chat/{CHAT_ID}")
    assert len(entri) == 1
    assert entri[0]["aria-current"] == "page"
    assert "&lt;b&gt;Label&lt;/b&gt;" in isi.decode()
    assert dom.ambil("a", href="/pendamping/riwayat?halaman=1")
    assert dom.ambil("a", href="/pendamping/riwayat?halaman=3")


def test_riwayat_kosong_tanpa_cta_ganda():
    isi = pages.halaman_riwayat(())
    dom = Markup(isi)
    assert "Belum ada percakapan" in isi.decode()
    assert len(dom.ambil("a", href="/pendamping")) == 1
    assert not [a for a in dom.ambil("a") if "?halaman=" in a.get("href", "")]


def test_shell_normal_menu_native_dan_brand_lokal(proyeksi):
    isi = pages.halaman_awal((chat(),))
    dom = Markup(isi)
    assert len(dom.ambil("details")) == 2
    assert dom.ambil("img", src="/aset/mark-sederhana.svg")
    assert dom.ambil("a", href="#utama")
    assert dom.ambil("main", id="utama", tabindex="-1")
    assert not dom.ambil("script")
    assert len(dom.ambil("a", href="/guru")) == 1
    assert all("disabled" not in a for a in dom.ambil("button"))
    assert b"Alat review prototype" not in isi
    assert b"cabut" not in isi and b"Hapus percakapan" not in isi


def test_chat_teks_selalu_escaped_dan_anchor_pesan(proyeksi):
    teks = '<script>alert(1)</script>\nBaris kedua & ketiga'
    pesan = (NS(id="pesan-sintetis", peran="asisten", teks=teks),)
    isi = pages.halaman_chat(chat(), pesan, (), request_id="req-sintetis",
                             status_memori="Memori nonaktif · 1 catatan")
    dom = Markup(isi)
    assert html.escape(teks) in isi.decode()
    assert not dom.ambil("script")
    assert dom.ambil("article", id="pesan-pesan-sintetis")
    assert len(dom.ambil("form")) == 1
    assert "Memori nonaktif · 1 catatan" in isi.decode()
    assert not dom.ambil("input", name="mode")


def test_readonly_tidak_merender_composer_draft_usulan(proyeksi):
    isi = pages.halaman_chat(chat(), (NS(id="p1", peran="asisten", teks="Transkrip sah"),), (),
        request_id="req-sintetis", draft=(memori(dikonfirmasi=False, isi="DRAFT RAHASIA"),),
        usulan=(usulan(),), hanya_baca=True)
    dom = Markup(isi)
    assert b"Transkrip sah" in isi and b"DRAFT RAHASIA" not in isi
    assert not dom.ambil("form") and not dom.ambil("textarea")
    assert not dom.ambil("a", href=f"/pendamping/usulan/{USULAN_ID}")
    assert "hanya dapat dibaca" in isi.decode()
    assert isi.decode().index("hanya dapat dibaca") < isi.decode().index("Transkrip sah")


def test_mode_tanpa_memori_mengalahkan_status_dan_draft(proyeksi):
    isi = pages.halaman_chat(chat(mode_memori="tanpa_memori"), (), (), request_id="req",
                            status_memori="Memori aktif · 9 catatan",
                            draft=(memori(dikonfirmasi=False, isi="DRAFT RAHASIA"),))
    assert "Chat tanpa memori" in isi.decode()
    assert b"Memori aktif" not in isi and b"DRAFT RAHASIA" not in isi


def test_chat_pending_tidak_mengirim_ulang(proyeksi):
    isi = pages.halaman_chat(chat(), (), (), request_id="req", draft=(memori(),),
                            usulan=(usulan(),), operasi_url="/pendamping/operasi/req")
    dom = Markup(isi)
    assert not dom.ambil("form") and not dom.ambil("textarea")
    assert dom.ambil("a", href="/pendamping/operasi/req")


@pytest.mark.parametrize("status", ["pending", "gagal"])
def test_status_operasi_hanya_get(status):
    isi = pages.halaman_status_operasi(status, chat_id=CHAT_ID, request_id="req-sintetis")
    dom = Markup(isi)
    assert not dom.ambil("form") and not dom.ambil("textarea")
    target = "/pendamping/operasi/req-sintetis" if status == "pending" else f"/pendamping/chat/{CHAT_ID}"
    assert dom.ambil("a", href=target)


def test_draft_konfirmasi_dan_abaikan_endpoint_existing(proyeksi):
    isi = pages.halaman_chat(chat(), (), (), request_id="req", draft=(memori(dikonfirmasi=False),))
    dom = Markup(isi)
    assert not dom.ambil("form", action=f"/pendamping/memori/{MEMORI_ID}/konfirmasi")
    assert dom.ambil("form", action=f"/pendamping/memori/{MEMORI_ID}/hapus")
    assert len(dom.ambil("input", name="kembali", value=CHAT_ID)) == 1
    assert dom.ambil("input", name="persetujuan_hapus", value="1")
    assert dom.ambil("input", name="versi", value="3")
    assert b"Abaikan" in isi


@pytest.mark.parametrize("aktif", [True, False])
def test_memori_status_hanya_menghitung_terkonfirmasi(aktif):
    isi = pages.halaman_memori((memori(), memori(id="draft", dikonfirmasi=False)), aktif=aktif,
                               versi=4, kembali=CHAT_ID)
    dom = Markup(isi)
    assert "tidak lagi dibuat, diubah, atau digunakan" in isi.decode()
    assert "Draft ini tidak dapat diaktifkan" in isi.decode()
    assert not dom.ambil("textarea")
    assert not any(f['action'].endswith(('/nonaktifkan', '/aktifkan')) for f in dom.forms)


def test_memori_kosong_tanpa_hapus_semua():
    dom = Markup(pages.halaman_memori((), aktif=True, versi=0))
    assert not dom.ambil("a", href="/pendamping/memori/hapus-semua")


def test_editor_versi_kembali_isi_escaped_dan_galat_tidak_echo():
    item = memori(isi="<b>Isi tersimpan</b>")
    isi = pages.halaman_edit_memori(item, kembali=CHAT_ID)
    dom = Markup(isi)
    assert "&lt;b&gt;Isi tersimpan&lt;/b&gt;" in isi.decode()
    assert not dom.ambil("form") and not dom.ambil("textarea")
    assert dom.ambil("a", href=f"/pendamping/memori/{MEMORI_ID}/hapus?kembali={CHAT_ID}")
    gagal = pages.halaman_edit_memori(item, galat="Isi di luar preferensi")
    assert b"Isi di luar preferensi" in gagal
    assert not Markup(gagal).ambil("textarea")


@pytest.mark.parametrize("semua", [True, False])
def test_hapus_memori_wajib_tinjau_checkbox_dan_versi(semua):
    isi = pages.halaman_hapus_memori((memori(),), versi=7 if semua else 3,
                                   semua=semua, kembali=CHAT_ID)
    dom = Markup(isi)
    target = "/pendamping/memori/hapus-semua" if semua else f"/pendamping/memori/{MEMORI_ID}/hapus"
    assert len(dom.ambil("form", action=target)) == 1
    cek = dom.ambil("input", name="persetujuan_hapus", value="1")
    assert len(cek) == 1 and "required" in cek[0]
    assert dom.ambil("input", name="versi", value="7" if semua else "3")
    assert b"Chat lama tetap ada" in isi
    assert "onclick" not in isi.decode() and "onsubmit" not in isi.decode()


def test_sumber_ui_tidak_merender_muatan_dan_batal_ke_sumber():
    konteks = NS(jenis="soal", resource_id="42:3", versi="v1", kategori="soal_resmi",
                 muatan={"nomor": 3, "kunci": "KUNCI TIDAK BOLEH DIRINCI"})
    sumber = dict(label="Soal nomor 3", nama="Anak <Contoh>", level="P3", url="/sesi/42#jwb-43")
    isi = pages.halaman_pilih_konteks(konteks, sumber=sumber)
    dom = Markup(isi)
    assert "Anak &lt;Contoh&gt;" in isi.decode()
    assert b"KUNCI TIDAK BOLEH DIRINCI" not in isi
    assert dom.ambil("a", href="/sesi/42#jwb-43")
    assert dom.ambil("input", name="resource_id", value="42:3")
    assert b"kunci" in isi and b"pembahasan resmi" in isi


def test_sumber_url_nonlokal_tidak_jadi_link():
    isi = pages.halaman_konteks_berubah(sumber=dict(label="Sumber", url="javascript:alert(1)"))
    assert not Markup(isi).ambil("a", href="javascript:alert(1)")


def test_tinjau_label_resmi_readonly_sumber_pesan_dan_batas_siklus(proyeksi):
    pesan = NS(id="p-asal", teks="Permintaan <sintetis>")
    isi = pages.halaman_tinjau_usulan(usulan(), chat(), None, request_id="req",
        sumber=dict(label="Ringkasan anak", nama="Anak Contoh", level="P3", url="/anak/42"),
        pesan_sumber=pesan)
    dom = Markup(isi)
    assert b"Pola Bilangan" in isi and b"Pola bilangan" in isi
    assert "Permintaan &lt;sintetis&gt;" in isi.decode()
    assert dom.ambil("a", href=f"/pendamping/chat/{CHAT_ID}#pesan-p-asal")
    assert not dom.ambil("select") and not dom.ambil("textarea")
    assert len(dom.ambil("form")) == 1
    assert dom.ambil("input", name="hash", value="hash-sintetis")
    assert b"tidak mengubah bukti atau putaran siklus belajar" in isi


def test_hasil_hanya_pakai_id_divalidasi_server():
    isi = pages.halaman_hasil_usulan(usulan(sesi_id=999), sesi_id=42)
    dom = Markup(isi)
    assert dom.ambil("a", href="/sesi/42") and not dom.ambil("a", href="/sesi/999")
    assert not dom.ambil("form")
    assert b"Sesi #42" in isi


def test_tinjau_selesai_ke_lookup_bukan_pointer(proyeksi):
    isi = pages.halaman_tinjau_usulan(usulan(sesi_id=999), chat(), None, request_id="req")
    dom = Markup(isi)
    assert not dom.ambil("form")
    assert not dom.ambil("a", href="/sesi/999")
    assert dom.ambil("a", href=f"/pendamping/usulan/{USULAN_ID}")


def test_persetujuan_lanjut_divalidasi_helper(monkeypatch):
    tujuan = "/pendamping/konteks/soal/42:3"
    dipanggil = []
    def validasi(nilai):
        dipanggil.append(nilai)
        return tujuan if nilai == tujuan else ""
    monkeypatch.setitem(sys.modules, "assistant_navigation", NS(tujuan_lanjut=validasi))
    isi = pages.halaman_persetujuan(lanjut=tujuan)
    assert Markup(isi).ambil("input", name="lanjut", value=tujuan)
    assert not Markup(pages.halaman_persetujuan(lanjut="https://asing.invalid")).ambil("input", name="lanjut")
    assert dipanggil == [tujuan, "https://asing.invalid"]
    assert not Markup(isi).ambil("nav", **{"aria-label": "Navigasi Pendamping"})


def test_generic_mengabaikan_chats_yang_tidak_boleh_dibaca():
    class TakBolehDibaca:
        def __iter__(self):
            raise AssertionError("Generic shell membaca daftar privat")
    isi = pages._bingkai("Tidak ditemukan", '<h1 id="judul-pendamping">Tidak ditemukan</h1>',
                         chats=TakBolehDibaca(), chat_id=CHAT_ID)
    assert CHAT_ID.encode() not in isi


def test_chat_satu_cta_primer_meski_ada_draft_dan_usulan(proyeksi):
    dom = Markup(pages.halaman_chat(chat(), (), (), request_id="req", draft=(memori(),), usulan=(usulan(),)))
    primer = [a for tag, a in dom.elemen if tag in ("a", "button")
              and "pendamping-tombol" in a.get("class", "").split()
              and "pendamping-sekunder" not in a.get("class", "").split()]
    assert len(primer) == 1
    assert primer[0]["aria-label"] == "Kirim pesan"


def test_kembali_invalid_tidak_menjadi_field_atau_url_bebas():
    dom = Markup(pages.halaman_edit_memori(memori(), kembali="https://asing.invalid"))
    assert not dom.ambil("input", name="kembali")
    assert not [a for a in dom.ambil("a") if "asing.invalid" in a.get("href", "")]


def test_persetujuan_batal_sumber_dari_proyeksi_sah():
    isi = pages.halaman_persetujuan(sumber=dict(url="/sesi/42#jwb-43"))
    assert Markup(isi).ambil("a", href="/sesi/42#jwb-43")
    assert not Markup(isi).ambil("a", href="/guru")


def test_label_usulan_helper_tidak_dianggap_html(proyeksi):
    proyeksi.ringkasan_usulan = lambda _: dict(topik="<img src=x>", level="<P3>", jumlah=10,
                                               materi=(("<b>Materi</b>", 10, "<template>"),))
    isi = pages.halaman_tinjau_usulan(usulan(), chat(), None, request_id="req")
    assert "&lt;img src=x&gt;" in isi.decode() and "&lt;b&gt;Materi&lt;/b&gt;" in isi.decode()
    assert not Markup(isi).ambil("img", src="x")


def test_status_operasi_invalid_dan_hapus_kosong_ditolak():
    with pytest.raises(ValueError):
        pages.halaman_status_operasi("selesai", chat_id=CHAT_ID, request_id="req")
    with pytest.raises(ValueError):
        pages.halaman_hapus_memori((), versi=1)
    with pytest.raises(ValueError):
        pages.halaman_hasil_usulan(usulan(), sesi_id=True)


def test_readonly_hasil_selesai_tetap_lookup_bukan_kandidat(proyeksi):
    daftar = (usulan(status="selesai", sesi_id=42),
              usulan(id="kandidat", status="diusulkan", sesi_id=None),
              usulan(id="status-belum-selesai", status="diusulkan", sesi_id=999))
    isi = pages.halaman_chat(chat(), (), (), request_id="req", hanya_baca=True, usulan=daftar)
    dom = Markup(isi)
    assert dom.ambil("a", href=f"/pendamping/usulan/{USULAN_ID}")
    assert not dom.ambil("a", href="/pendamping/usulan/kandidat")
    assert not dom.ambil("a", href="/pendamping/usulan/status-belum-selesai")
    assert not dom.ambil("a", href="/sesi/42")
    assert not dom.ambil("form") and not dom.ambil("textarea")


def test_menu_memori_membawa_chat_dan_ganti_sumber_tanpa_cta_ganda(proyeksi):
    isi = pages.halaman_chat(chat(context_kind="anak"), (), (), request_id="req",
                            sumber=dict(label="Ringkasan anak", nama="Anak Contoh", url="/anak/42"))
    dom = Markup(isi)
    assert dom.ambil("a", href=f"/pendamping/memori?kembali={CHAT_ID}")
    assert len(dom.ambil("a", href="/pendamping")) == 1
    assert len(dom.ambil("a", href="/anak/42")) == 1
    assert b"Ganti atau lepas sumber" in isi


def test_gaya_warna_token_tanpa_resource_jaringan():
    teks = (Path(__file__).resolve().parent.parent / "assistant_style.py").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\\b", teks)
    assert "@import" not in teks and "url(" not in teks
    assert "background:none" in GAYA_PENDAMPING
    assert ":focus-visible" in GAYA_PENDAMPING
    assert "overflow:clip" in GAYA_PENDAMPING  # Hanya label SR 1px, bukan halaman.
