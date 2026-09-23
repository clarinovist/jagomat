"""Kontrak editorial pendamping: landmark, formulir, dan aksesibilitas."""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import account_pages
import admin_pages
import admin_queries
import assistant_components
import assistant_inline
import attachments
import auth
import database
import design_tokens as T
import reports
import style_stitch
import teacher_pages


class Markup(HTMLParser):
    """Catat elemen dan relasi label tanpa menjalankan JavaScript."""

    def __init__(self, isi):
        super().__init__()
        self.elemen = []
        self.dalam_label = 0
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        if tag == "label":
            self.dalam_label += 1
        self.elemen.append((tag, dict(attrs), bool(self.dalam_label)))

    def handle_endtag(self, tag):
        if tag == "label":
            self.dalam_label -= 1

    def pilih(self, tag):
        return [atribut for nama, atribut, _ in self.elemen if nama == tag]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "editorial-sintetis.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "sandi-sintetis.json")
    akun = [{"pengguna": "pendamping-uji", "peran": "guru"}]
    monkeypatch.setattr(auth, "muat_akun", lambda: akun)
    monkeypatch.setattr(auth, "cari_akun", lambda nama: next((a for a in akun if a["pengguna"] == nama), None))
    with database.buka(jalur) as kon:
        sid = database.tambah_siswa(kon, 'Tunas <b> & "Senja"', pemilik="pendamping-uji")
        database.tambah_siswa(kon, "Belum terhubung", pemilik="pendamping-uji")
        akun.append({"pengguna": "tunas-uji", "peran": "murid", "siswa_id": sid})
        sesi = database.buat_sesi(kon, sid, seed=7, jumlah_soal=10)
        kon.execute("UPDATE sesi SET tanggal = '2026-09-13' WHERE id = ?", (sesi,))
        lamp = database.simpan_lampiran(kon, sesi, "foto-sintetis.png")
        yield kon, sid, sesi, lamp


def _halaman(db):
    kon, sid, sesi, lamp = db
    siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (sid,)).fetchone()
    return {
        "profil": teacher_pages.halaman_anak(kon, siswa, pengguna="pendamping-uji"),
        "koreksi": teacher_pages.halaman_sesi_stitch(kon, sesi, pengguna="pendamping-uji"),
        "laporan": reports.halaman_laporan(kon, sid, pengguna="pendamping-uji"),
        "akun": account_pages.halaman_akun(kon, pengguna="pendamping-uji"),
        "siswa": account_pages.halaman_akun(kon, pengguna="pendamping-uji", section="siswa"),
        "akun-murid": account_pages.halaman_akun(kon, pengguna="pendamping-uji", section="akun-murid"),
        "admin": admin_pages.halaman_admin(
            "ringkasan", admin_pages.render_ringkasan(admin_queries.ringkasan_admin(
                kon, admin_queries.buat_konteks(kon, auth.muat_akun()),
            )), pengguna="pengelola-uji",
        ),
        "cetak": teacher_pages.halaman_sesi_cetak(kon, sesi),
        "lampiran": teacher_pages.halaman_sesi_lampiran(kon, sesi),
        "foto": attachments.halaman_konfirmasi(kon, lamp),
        "hapus": teacher_pages.halaman_konfirmasi_hapus(kon, sesi),
    }


def test_sebelas_tampilan_punya_landmark_dan_wrapper_scoped(db):
    for nama, isi in _halaman(db).items():
        markup = Markup(isi.decode())
        assert len(markup.pilih("main")) == 1, nama
        assert len(markup.pilih("h1")) == 1, nama
        assert markup.pilih("main")[0]["aria-labelledby"] == markup.pilih("h1")[0]["id"], nama
        if nama == "admin":
            assert "admin-readonly" in markup.pilih("body")[0]["class"].split()
        else:
            assert any("pendamping-editorial-st" in a.get("class", "").split() for a in markup.pilih("div")), nama
        assert 'Tunas <b>' not in isi.decode(), nama


def test_kontrol_form_punya_nama_aksesibel_dan_id_unik(db):
    kon, _, sesi, _ = db
    database.tandai_selesai(kon, sesi)
    for nama, isi in _halaman(db).items():
        m = Markup(isi.decode())
        label = {a["for"] for a in m.pilih("label") if "for" in a}
        ids = [a["id"] for _, a, _ in m.elemen if "id" in a]
        assert len(ids) == len(set(ids)), nama
        for tag, a, induk_label in m.elemen:
            if tag not in {"input", "select", "textarea"} or a.get("type") == "hidden":
                continue
            assert induk_label or a.get("id") in label or a.get("aria-label"), (nama, tag, a)


def test_rencana_tetap_satu_di_tab_terpisah_dari_alat_manual(db):
    kon, sid, _, _ = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
    isi = teacher_pages.halaman_anak(kon, siswa, query='section=rencana').decode().split('</style>', 1)[1]
    assert isi.count('class="kartu-rencana-st"') == 1
    assert isi.count('class="rencana-cta-utama-st"') == 1
    assert f'action="/sesi-baru/{sid}"' not in isi
    manual = _halaman(db)['profil'].decode().split('</style>', 1)[1]
    assert 'class="kartu-rencana-st"' not in manual
    assert 'Latihan bebas tidak mengubah progres rencana terpandu.' in manual


def test_navigasi_section_dan_sesi_menandai_halaman_aktif(db):
    for nama in ("akun", "siswa", "akun-murid", "koreksi", "cetak", "lampiran"):
        markup = Markup(_halaman(db)[nama].decode())
        aktif = [a for a in markup.pilih("a") if a.get("aria-current") == "page"]
        assert len(aktif) == 1, nama
        assert any("aria-label" in a for a in markup.pilih("nav")), nama


def test_header_sesi_memakai_tanggal_ramah_kelas_dan_jumlah_aktual(db):
    halaman = _halaman(db)["koreksi"].decode()
    kepala = halaman.split('<header class="editorial-kepala-st">', 1)[1].split("</header>", 1)[0]
    assert '<time datetime="2026-09-13">13 Sep 2026</time>' in kepala
    assert "Variasi A" in kepala
    jumlah = db[0].execute(
        "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (db[2],)
    ).fetchone()[0]
    assert f"{jumlah} soal" in kepala
    assert "seed 7" not in kepala
    assert "campuran" not in kepala


def test_empat_host_merender_style_dan_markup_composer_shared(db):
    kon, sid, sesi, _ = db
    siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (sid,)).fetchone()
    chat = SimpleNamespace(id="chat_" + "a" * 32, mode_memori="aktif", dibuat=0)

    def panel(target, dalam_form=False):
        return assistant_components.panel_chat(
            target, chat, (), (chat,),
            sumber={"label": "Sumber sintetis", "level": "P3"},
            dalam_form=dalam_form,
            status_memori="Memori aktif · belum ada catatan",
        )

    halaman = {
        "rencana": teacher_pages.halaman_anak(
            kon, siswa, pengguna="pendamping-uji",
            bantuan_rencana=panel(assistant_inline.tujuan_anak(sid, chat_id=chat.id)),
        ).decode(),
        "latihan": teacher_pages.halaman_anak(
            kon, siswa, pengguna="pendamping-uji",
            bantuan_latihan=panel(
                assistant_inline.tujuan_anak(sid, "latihan", chat_id=chat.id), True
            ),
        ).decode(),
        "sesi": teacher_pages.halaman_sesi_stitch(
            kon, sesi, pengguna="pendamping-uji",
            bantuan=panel(assistant_inline.tujuan_sesi(sesi, chat_id=chat.id)),
        ).decode(),
    }
    database.tandai_selesai(kon, sesi)
    halaman["soal"] = teacher_pages.halaman_sesi_stitch(
        kon, sesi, pengguna="pendamping-uji",
        bantuan=panel(
            assistant_inline.tujuan_sesi(sesi, nomor=1, chat_id=chat.id), True
        ),
        bantuan_nomor=1,
    ).decode()

    for nama, isi in halaman.items():
        assert '<div class="pendamping-composer">' in isi, nama
        assert '.pendamping-inline .pendamping-transkrip, .pendamping-inline .pendamping-composer {' in isi, nama
        assert f"max-width: {T.LEBAR_KONTEN}" in isi, nama
        assert 'formaction="/pendamping/inline/pesan">Kirim</button>' in isi, nama
        assert '<summary>Preferensi</summary>' in isi, nama


def test_form_upload_terapkan_baca_ulang_dan_hapus_tetap_terpisah(db):
    _, _, sesi, lamp = db
    halaman = _halaman(db)
    unggah = Markup(halaman["lampiran"].decode())
    assert any(a.get("enctype") == "multipart/form-data" and a["action"] == f"/lampiran/{sesi}" for a in unggah.pilih("form"))
    foto = Markup(halaman["foto"].decode())
    assert [a["action"] for a in foto.pilih("form") if a["action"] != "/keluar"] == [f"/lampiran/{lamp}/baca-ulang", f"/lampiran/{lamp}/terapkan"]
    hapus = Markup(halaman["hapus"].decode())
    assert any(a.get("action") == f"/sesi/{sesi}/hapus" and a.get("method") == "post" for a in hapus.pilih("form"))
    assert {"type": "hidden", "name": "konfirmasi", "value": "1"} in hapus.pilih("input")
    assert "tidak bisa dibatalkan" in halaman["hapus"].decode()


def test_siswa_kosong_punya_petunjuk_dan_foto_punya_nama_menu(db):
    kon, _, _, _ = db
    kosong = account_pages.halaman_akun(kon, pengguna="tanpa-anak", section="siswa").decode()
    assert "Belum ada siswa. Tambahkan anak pertama di bawah." in kosong
    foto = _halaman(db)["foto"].decode()
    assert '<summary aria-label="Menu pendamping">Menu</summary>' in foto


def test_bingkai_opsional_tidak_mengubah_landmark_pemanggil_lama():
    lama = teacher_pages._halaman("Judul", "<h1>Judul</h1>", stitch=True).decode()
    assert '<div class="sesi-badan-st"><h1>Judul</h1></div>' in lama
    assert "<main" not in lama
    beranda = teacher_pages._halaman_stitch("Judul", "<h1>Judul</h1>").decode()
    assert '<div class="bungkus-st"><h1>Judul</h1></div>' in beranda


def test_css_hanya_scoped_dan_tidak_menambah_hex_atau_font():
    sumber = Path(style_stitch.__file__).read_text()
    blok = sumber.split("/* WORKER A editorial scoped", 1)[1].split("/* FIN WORKER A", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", blok)
    assert "@import" not in blok
    for baris in blok.splitlines():
        if baris and not baris.startswith((" ", "@", "}")) and "{{" in baris:
            assert "editorial-st" in baris, baris
    assert "height: auto; min-height: {T.TARGET_SENTUH}; position: relative" in blok
    assert "opacity: 1" in blok
    assert ":focus-visible" in blok
    assert "min-height: {T.TARGET_SENTUH}" in blok


def test_navigasi_akun_tidak_mewarisi_sidebar_sticky():
    css = style_stitch.GAYA_STITCH
    aturan = re.search(r'\.akun-editorial-st \.nav-samping \{([^}]+)\}', css).group(1)
    assert 'position: static' in aturan
    assert 'flex-direction: row' in aturan


def test_siswa_tanpa_kartu_catatan_operasional_dan_batas_hapus_dekat_daftar(db):
    kon, _, _, _ = db
    isi = account_pages.halaman_akun(kon, pengguna='pendamping-uji', section='siswa').decode()
    badan = isi.split('</style>', 1)[1]
    assert '<h2>Catatan</h2>' not in badan
    assert 'Mac' not in badan and '22:00' not in badan
    daftar = badan.split('<h2>Siswa</h2>', 1)[1].split('<h2>Tambah anak</h2>', 1)[0]
    assert 'Anak dengan riwayat sesi tidak bisa dihapus.' in daftar
    assert 'Anak tanpa sesi dapat dihapus beserta akun latihannya.' in daftar


def test_status_perlu_perhatian_dan_foto_tetap_terbaca():
    css = style_stitch.GAYA_STITCH
    assert f'.pendamping-editorial-st .status-buruk {{ color: {T.AKSEN_KORAL_TUA}; }}' in css
    assert '.foto-editorial-st .foto-lembar { max-height: 70vh; }' in css


def test_aksen_editorial_kontras_teks_normal():
    def luminansi(warna):
        nilai = [int(warna[i:i+2], 16) / 255 for i in (1, 3, 5)]
        kanal = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in nilai]
        return sum(v*b for v, b in zip(kanal, (.2126, .7152, .0722)))
    for depan, belakang in [(T.TEKS_PUTIH, T.AKSEN_TEAL_TUA), (T.TEKS_PUTIH, T.AKSEN_KORAL_TUA), (T.TEKS_VARIAN, T.LATAR_MURID), (T.AKSEN_TEAL_TUA, T.LATAR_MURID)]:
        a, b = sorted((luminansi(depan), luminansi(belakang)))
        assert (b+.05)/(a+.05) >= 4.5
