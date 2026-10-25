"""Markup daftar langganan admin: kontrak form tetap, tampilan mengikuti redesain."""
import admin_launch_pages as ui


def _rows():
    return [
        dict(akun_id="akun_a", alias="Edi<x>", mulai=1790000000, peserta_promo=False, asal="transisi"),
        dict(akun_id="akun_b", alias="Lion", mulai=1790086400, peserta_promo=True, asal="transisi"),
    ]


def test_daftar_langganan_kontrak_form_cari_tetap():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="csrf<1>")

    assert isi.count("<form") == 1
    assert '<form class="admin-form-cari" method="post" action="/admin/layanan/cari">' in isi
    assert '<input type="hidden" name="csrf" value="csrf&lt;1&gt;">' in isi
    assert '<input name="cari" maxlength="80" value="">' in isi.replace(' placeholder="Cari akun orang tua"', "")
    assert "<script" not in isi


def test_daftar_langganan_tabel_pill_dan_angka_tercatat():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="x")

    assert isi.count('<th scope="col"') == 4
    assert '<div class="admin-stat"><h2>Keluarga tercatat</h2><div><strong>2</strong></div></div>' in isi
    assert 'href="/admin?section=langganan&amp;id=akun_a"' in isi
    assert "Edi&lt;x&gt;" in isi and "Edi<x>" not in isi
    assert '<span class="admin-badge bien">Ya</span>' in isi
    assert '<span class="admin-badge">Tidak</span>' in isi
    assert "2 tercatat · Halaman 1" in isi
    assert "Diurutkan menurut nama" not in isi
    assert "Panel ini tidak mengaktifkan paywall." in isi


def test_daftar_langganan_tanpa_csrf_tidak_menampilkan_form_cari():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="")

    assert "<form" not in isi


def test_daftar_langganan_pager_post_saat_mencari_dan_tidak_membocorkan_ke_url():
    isi = ui.daftar_langganan(_rows(), 60, halaman=1, cari="rahasia", csrf="c")

    assert 'name="halaman" value="2"' in isi
    assert "cari=" not in isi.replace('name="cari"', "")
    kandidat = [dict(akun_id="akun_z", alias="Siska")]
    dengan = ui.daftar_langganan(_rows(), 2, halaman=1, cari="si", csrf="c", kandidat=kandidat, forms={"akun_z": "<b>aksi</b>"})
    assert "Belum terdaftar di langganan · 1" in dengan and "<b>aksi</b>" in dengan


import re

import product_analytics as pa


def _laporan(manfaat):
    metrik = (
        pa.Metrik("aktivasi", 3, 5, 60, "Di bawah target", False),
        pa.Metrik("retensi", 1, 5, 25, "Di bawah target", False),
        manfaat,
        pa.Metrik("organik", 0, 0, 20, "Belum ada eksperimen", False),
    )
    return pa.Laporan(metrik, 5, 5, 0, 0, (), True)


def _kpi(laporan):
    return ui.halaman_kpi(
        None if laporan is None else {"koleksi": True}, laporan, None,
        {"dicabut": 0, "kedaluwarsa": 0, "pendaftaran": None}, bulan="2026-10",
    )


def test_kpi_tanpa_respons_menampilkan_strip_bukan_nol_dan_bilah_kosong():
    isi = _kpi(None)

    hero = isi.split('aria-labelledby="h-kpi-manfaat"', 1)[1].split("</section>", 1)[0]
    assert '<strong class="admin-angka admin-redup">—</strong>' in hero
    assert "0.0%" not in hero and "0%</strong>" not in hero
    assert 'role="img" aria-label="Belum ada respons; target 70 persen"' in hero
    assert '<span style="width' not in hero
    assert "Respons</span><strong>0 / 0</strong>" in hero
    assert "Target ≥ 70%" in hero
    assert "Belum ada eksperimen" in isi  # keadaan kosong dipertahankan
    assert isi.index("h-kpi-manfaat") < isi.index("Hasil belum ditampilkan agar tidak terbaca sebagai 0%")


def test_kpi_dengan_respons_mengisi_bilah_sesuai_persentase():
    isi = _kpi(_laporan(pa.Metrik("manfaat", 8, 10, 70, "Memenuhi target", False, 10, 12)))

    hero = isi.split('aria-labelledby="h-kpi-manfaat"', 1)[1].split("</section>", 1)[0]
    assert '<strong class="admin-angka">80.0%</strong>' in hero
    assert 'aria-label="Hasil 80.0 persen; target 70 persen"' in hero
    assert '<span style="width:80.00%"></span><i style="left:70%"></i>' in hero
    assert "Respons</span><strong>10 / 12</strong>" in hero
    assert "Memenuhi target" in hero
    assert "Hasil belum ditampilkan agar tidak terbaca sebagai 0%" not in isi


def test_kpi_tiga_metrik_lain_dan_biaya_tetap_ada_di_grid():
    isi = _kpi(None)
    grid = isi.split('<div class="admin-grid-kpi">', 1)[1]

    for judul in ("Berhasil mencoba", "Memakai kembali", "Tumbuh organik", "Biaya · 2026-10"):
        assert judul in grid
    assert "Merasa terbantu" not in grid
    assert re.search(r'<h2 id="h-kpi-manfaat">Merasa terbantu</h2>', isi)


# --- Operasional (jalur Kritis): kontrak form dikunci, tampilan boleh berubah ---
from html.parser import HTMLParser

import support_settings as ss


class _Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self._kini = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._kini = {"action": a.get("action"), "method": a.get("method"), "fields": []}
        elif self._kini is not None and tag in ("input", "select", "textarea") and a.get("name"):
            self._kini["fields"].append((a["name"], a.get("type", tag), "required" in a))

    def handle_endtag(self, tag):
        if tag == "form":
            self._kini["fields"].sort()
            self.forms.append(self._kini)
            self._kini = None


def _forms(isi):
    p = _Form()
    p.feed(isi)
    return {f["action"]: f for f in p.forms}


def _config():
    return ss.KonfigurasiDukungan("082137111988", ss.JAM_AWAL, 1, 3, 4, 1790000000, "akun_x")


def _ringkas(tahap="checkout", dukungan=True, siap=True):
    return {
        "admin": "Siap", "pembayaran": "Terkonfigurasi", "backup": "Belum terverifikasi",
        "backup_cutoff": None, "dukungan_config": _config() if dukungan else None,
        "pembayaran_config": {"tahap": tahap, "revisi": 3},
        "pembayaran_kesiapan": {k: siap for k in ("provider_produksi", "callback", "recovery", "kebijakan")},
        "ai": (("pendamping", "Diizinkan oleh konfigurasi"), ("cerita", "Tertahan: kunci kosong")),
        "ai_gagal": 2,
    }


def _form_pembayaran():
    return ui.formulir(
        "pembayaran", "c", "t",
        '<label>Tahap tujuan<select name="tahap"><option value="checkout">Checkout</option></select></label>'
        '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya sudah meninjau.</label>',
        "Terapkan perubahan tahap",
    )


def test_operasional_kontrak_form_dukungan_dan_pembayaran_tidak_berubah():
    isi = ui.operasional(_ringkas(), _form_pembayaran(), ui.formulir_dukungan("c", "t", _config()))
    forms = _forms(isi)

    assert forms["/admin/layanan/dukungan"]["method"] == "post"
    assert forms["/admin/layanan/dukungan"]["fields"] == sorted([
        ("csrf_dukungan", "hidden", False), ("tinjauan_dukungan", "hidden", False),
        ("whatsapp", "input", True), ("jam_layanan", "select", False),
        ("sla_respons", "number", True), ("sla_status", "number", True),
        ("konfirmasi", "checkbox", True), ("reauth", "password", True),
    ])
    assert forms["/admin/layanan/pembayaran"]["fields"] == sorted([
        ("csrf", "hidden", False), ("tinjauan", "hidden", False), ("tahap", "select", False),
        ("konfirmasi", "checkbox", True), ("reauth", "password", True),
    ])
    assert len(forms) == 2
    assert "revisi" not in {n for f in forms.values() for n, _t, _r in f["fields"]}
    assert "<script" not in isi


def test_operasional_teks_keamanan_dan_konfirmasi_dipertahankan_kata_per_kata():
    isi = ui.operasional(_ringkas(), _form_pembayaran(), ui.formulir_dukungan("c", "t", _config()))

    for teks in (
        "Saya memahami perubahan ini langsung menjadi kontak dan janji layanan pada halaman publik.",
        "Contoh: 0821 3711 1988. URL wa.me dibuat oleh aplikasi; jangan masukkan URL atau kode negara.",
        "Secret hanya dipasang di server dan nilainya tidak pernah tampil di panel.",
        "Tahap harus dinaikkan satu per satu. Penurunan boleh langsung saat insiden.",
        "WhatsApp adalah kanal komunikasi, bukan bukti kepemilikan akun.",
        "Validitas bundle bukan bukti backup terjadwal, salinan luar server, atau rehearsal terbaru.",
        "Konfigurasi bukan jaminan provider sedang online. Tidak ada panggilan berbayar saat halaman dibuka.",
        "Tahap saat ini: <strong>Checkout</strong> · revisi 3",
    ):
        assert teks in isi, teks


def test_operasional_tab_stepper_prasyarat_dan_tile_ai():
    isi = ui.operasional(_ringkas(), "", "")

    assert '<nav class="admin-navigasi-bagian" aria-label="Bagian operasional">' in isi
    for sid in ("kesiapan", "dukungan", "pembayaran", "ai"):
        assert 'href="#%s"' % sid in isi and 'id="%s"' % sid in isi
    assert isi.count('aria-current="step"') == 1
    assert '<li aria-current="step"' in isi and "Tahap 3 · saat ini" in isi
    for tahap in ("Nonaktif", "Rekonsiliasi", "Checkout", "Penegakan"):
        assert tahap in isi
    assert isi.count('class="admin-tahap-hint"') == 4
    assert "Key/provider produksi" in isi and "Kebijakan D8/D9" in isi
    assert isi.count('class="admin-ai-tile"') == 3  # dua fitur + gagal 24 jam
    assert "Gagal / tak pasti, 24 jam" in isi and "<strong>2</strong>" in isi
    assert 'href="/admin/ai"' in isi


def test_operasional_backup_belum_tercatat_dan_prasyarat_belum_siap_tetap_teks():
    isi = ui.operasional(_ringkas(siap=False), "", "")

    assert "Cutoff backup:" in isi and "belum tercatat" in isi
    assert isi.count("Belum siap") >= 4
    assert 'admin-baris-status perhatian' in isi  # baris backup yang belum terverifikasi disorot


def test_operasional_tanpa_config_dukungan_menampilkan_belum_siap():
    isi = ui.operasional(_ringkas(dukungan=False), "", "")

    assert 'class="admin-kartu admin-galat" id="dukungan"' in isi and "Belum siap" in isi
    assert "<form" not in isi
