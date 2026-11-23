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


def test_operasional_teks_keamanan_dan_konfirmasi_dipertahankan():
    isi = ui.operasional(_ringkas(), _form_pembayaran(), ui.formulir_dukungan("c", "t", _config()))

    for teks in (
        "Saya memahami perubahan ini langsung menjadi kontak dan janji layanan pada halaman publik.",
        "Contoh: 0821 3711 1988. URL wa.me dibuat oleh aplikasi; jangan masukkan URL atau kode negara.",
        "Kunci rahasia hanya dipasang di server dan isinya tidak pernah tampil di panel.",
        "Membuka dilakukan bertahap, satu langkah sekali. Menutup boleh langsung saat ada masalah;",
        "WhatsApp adalah kanal komunikasi, bukan bukti kepemilikan akun.",
        "Cadangan yang valid belum tentu terjadwal, tersalin ke luar server, atau sudah dilatih pemulihannya.",
        "Tahap internal: checkout · revisi 3.",
        "Saya sudah meninjau.",
    ):
        assert teks in isi, teks


import admin_sakelar_pages as sak
import feature_switch as fs
import sakelar_registry as reg


def _bagian(aktif=(), tokens=None, hasil=None):
    daftar = tuple(fs.Sakelar(n, n in aktif, 2 if n in aktif else 0, "db" if n in aktif else "env")
                   for n in fs.NAMA_SAKELAR)
    return sak.bagian(daftar, tokens, hasil=hasil)


def _kartu(isi, sid):
    return isi.split('id="%s"' % sid, 1)[1].split("</section>", 1)[0]


def test_operasional_ringkasan_aktif_di_atas_dengan_badge_awam():
    bagian = _bagian(aktif=(sak.FUNNEL,))
    isi = ui.operasional(_ringkas("penegakan"), "", "", sakelar=bagian, pendaftaran='<section id="pendaftaran">P</section>',
                         pendaftaran_dibuka=False)

    ringkasan = _kartu(isi, "ringkasan")
    assert "Yang aktif sekarang" in ringkasan
    assert isi.index('id="ringkasan"') < isi.index('id="sakelar"') < isi.index('id="penjualan"')
    baris = re.findall(r'<li class="admin-ringkasan-item"><a class="admin-tautan-teks" href="#([^"]+)">(.*?)</a>(.*?)</li>', ringkasan)
    assert [b[0] for b in baris] == [sak.id_kartu(sak.FUNNEL), "pembayaran", sak.id_kartu(sak.TRANSFER), "pendaftaran",
                                     "s-osn_cetak_ringkas", "s-osn_bank_kalimat", "s-osn_lomba"]
    status = {b[1]: re.sub(r"<[^>]+>", "", b[2]) for b in baris}
    assert status["Cek Kemampuan dan Paket Coba"] == "Aktif"
    assert status["Pembayaran QRIS (Midtrans)"] == "Buka + akses berbayar"
    assert status["Pembayaran transfer rekening"] == "Mati"
    assert status["Pendaftaran mandiri"] == "Ditutup"
    assert status["Latihan Lomba (Grand Final)"] == "Mati"
    assert ringkasan.count("admin-status-besar bien") == 2  # funnel + QRIS terbuka


def test_operasional_ringkasan_qris_untuk_setiap_tahap_dengan_value_select_tetap():
    for tahap, teks in (("nonaktif", "Tutup"), ("rekonsiliasi", "Tutup untuk pesanan baru"), ("checkout", "Buka"),
                        ("penegakan", "Buka + akses berbayar")):
        isi = ui.operasional(_ringkas(tahap), "", "")
        assert re.sub(r"<[^>]+>", "", _kartu(isi, "pembayaran").split("</div>", 1)[0]).endswith(teks), tahap
    assert ui.LABEL_TAHAP == {"nonaktif": "Tutup",
                              "rekonsiliasi": "Tutup untuk pesanan baru (pesanan lama tetap diproses)",
                              "checkout": "Buka", "penegakan": "Buka + akses berbayar"}
    assert ui.TAHAP_PEMBAYARAN == ("nonaktif", "rekonsiliasi", "checkout", "penegakan")


def test_operasional_kartu_qris_awam_tanpa_jargon_dan_prasyarat_satu_kolom():
    isi = ui.operasional(_ringkas(siap=False), _form_pembayaran(), "")
    kartu = _kartu(isi, "pembayaran")

    assert "<h3>Pembayaran QRIS (Midtrans)</h3>" in kartu and "Sakelar pembayaran" not in isi
    assert isi.count('aria-current="step"') == 1 and "Langkah 3 · saat ini" in isi
    for label in ui.LABEL_TAHAP.values():
        assert "<strong>%s</strong>" % label in kartu
    for jargon in ("Key/provider produksi", "Recovery exact-pair", "Kebijakan D8/D9", "Prasyarat tepercaya",
                   "Callback dan rekonsiliasi", "Penegakan", "Nonaktif"):
        assert jargon not in isi, jargon
    # Prasyarat = daftar satu kolom (bukan grid), terbuka bila ada yang belum siap, dengan hitungan.
    assert '<details class="admin-prasyarat" open><summary>Syarat membuka QRIS · 0 dari 4 siap</summary>' in kartu
    assert kartu.count('class="admin-baris-status perhatian"') == 4 and "admin-prasyarat-item" not in isi
    lengkap = ui.operasional(_ringkas(siap=True), "", "")
    assert '<details class="admin-prasyarat"><summary>Syarat membuka QRIS · 4 dari 4 siap' in lengkap


def test_operasional_sandi_di_dalam_details_untuk_qris_dan_dukungan():
    isi = ui.operasional(_ringkas(), _form_pembayaran(), ui.formulir_dukungan("c", "t", _config()))

    sisa = re.sub(r'<details class="admin-aksi-ubah">.*?</details>', "", isi, flags=re.S)
    assert 'name="reauth"' not in sisa and isi.count('name="reauth"') == 2
    assert isi.count('<details class="admin-aksi-ubah"><summary class="admin-tombol">Ubah status QRIS…</summary>') == 1
    assert 'Ubah kontak dukungan…</summary><form method="post" action="/admin/layanan/dukungan"' in isi


def test_operasional_urutan_kelompok_dan_id_lama_tetap_ada():
    bagian = _bagian(tokens=None)
    isi = ui.operasional(_ringkas(), _form_pembayaran(), "", sakelar=bagian,
                         rekening='<section id="rekening">REKENING</section>',
                         pendaftaran='<section id="pendaftaran">P</section>', status_rekening="terisi",
                         pendaftaran_dibuka=True)

    urutan = [isi.index(t) for t in ('id="ringkasan"', 'id="sakelar"', 'id="penjualan"', 'id="s-funnel_aktif"',
                                     'id="pembayaran"', 'id="s-pesanan_transfer_aktif"', 'id="buka-transfer"',
                                     'id="rekening"', 'id="belajar"', 'id="pendaftaran"', 'id="kesehatan"',
                                     'id="kesiapan"', 'id="dukungan"')]
    assert urutan == sorted(urutan)
    penjualan = isi.split('id="penjualan"', 1)[1].split('id="belajar"', 1)[0]
    assert "Penjualan dan pembayaran" in isi and 'id="pembayaran"' in penjualan and 'id="rekening"' in penjualan
    belajar = isi.split('id="belajar"', 1)[1].split('id="pendaftaran"', 1)[0]
    assert "Fitur belajar" in belajar and "Latihan Lomba" in belajar and "Cek Kemampuan" not in belajar
    for sid in ("ringkasan", "penjualan", "belajar", "pendaftaran", "kesehatan"):
        assert 'href="#%s"' % sid in isi and isi.count('id="%s"' % sid) == 1


def test_operasional_tanpa_bagian_isian_tidak_menautkan_bagian_kosong():
    isi = ui.operasional(_ringkas(), "", "")

    assert 'href="#belajar"' not in isi and 'href="#pendaftaran"' not in isi and 'id="belajar"' not in isi
    assert 'id="sakelar"' not in isi and 'id="buka-transfer"' not in isi
    assert 'id="pembayaran"' in isi and 'href="#penjualan"' in isi


def test_operasional_sakelar_galat_tetap_tampil_tanpa_ringkasan_sakelar_dan_checklist():
    isi = ui.operasional(_ringkas(), "", "", sakelar=sak.halaman_galat())

    assert 'role="alert"' in isi and 'id="buka-transfer"' not in isi and 'id="pembayaran"' in isi
    assert isi.index('role="alert"') < isi.index('id="pembayaran"')


def _langkah(isi):
    kartu = _kartu(isi, "buka-transfer")
    return re.findall(r'<li class="admin-langkah-item (\S+)">', kartu)


def test_operasional_checklist_transfer_status_dari_rekening_qris_dan_sakelar():
    kasus = (
        (dict(status_rekening="kosong", tahap="checkout", aktif=()), ["belum", "belum", "belum"]),
        (dict(status_rekening="terisi", tahap="nonaktif", aktif=()), ["selesai", "selesai", "belum"]),
        (dict(status_rekening="terisi", tahap="rekonsiliasi", aktif=(sak.TRANSFER,)), ["selesai", "selesai", "selesai"]),
        (dict(status_rekening="terisi", tahap="penegakan", aktif=(sak.TRANSFER,)), ["selesai", "belum", "selesai"]),
        (dict(status_rekening="belum_dipasang", tahap="nonaktif", aktif=()), ["belum", "selesai", "belum"]),
    )
    for param, harapan in kasus:
        isi = ui.operasional(_ringkas(param["tahap"]), "", "", sakelar=_bagian(aktif=param["aktif"]),
                             status_rekening=param["status_rekening"])
        assert _langkah(isi) == harapan, param
    isi = ui.operasional(_ringkas("nonaktif"), "", "", sakelar=_bagian(), status_rekening="belum_dipasang")
    assert "belum dipasang operator" in _kartu(isi, "buka-transfer")


def test_operasional_checklist_tanpa_config_pembayaran_atau_rekening_tak_terbaca_bukan_selesai():
    ringkas = _ringkas()
    ringkas["pembayaran_config"] = None
    isi = ui.operasional(ringkas, "", "", sakelar=_bagian(), status_rekening=None)

    assert _langkah(isi) == ["tak-tahu", "tak-tahu", "belum"]
    assert 'class="admin-badge admin-status-besar">Tidak bisa dibaca<' in isi  # QRIS di ringkasan


def test_operasional_kesehatan_sistem_terlipat_memuat_kesiapan_dan_dukungan():
    isi = ui.operasional(_ringkas(siap=False), "", ui.formulir_dukungan("c", "t", _config()))

    kesehatan = isi.split('<details class="admin-kartu admin-kesehatan" id="kesehatan">', 1)[1].split("</details>", 1)[0]
    assert "Kesehatan sistem" in kesehatan and 'id="kesiapan"' in kesehatan and 'id="dukungan"' in kesehatan
    assert "Cadangan mencakup data sampai: belum tercatat" in isi
    assert '<span class="admin-badge perhatian">1 perlu dilihat</span>' in kesehatan  # hanya cadangan
    terbuka = ui.operasional(_ringkas(), "", "", feedback="Pengaturan dukungan tersimpan.")
    assert '<details class="admin-kartu admin-kesehatan" id="kesehatan" open>' in terbuka  # umpan balik terlihat


def test_operasional_tidak_ada_baris_ai_dan_tidak_ada_tautan_pengaturan_ai():
    isi = ui.operasional(_ringkas(), "", "")

    assert 'id="ai"' not in isi and 'href="#ai"' not in isi and 'href="/admin/ai"' not in isi
    assert "AI: tidak dipakai" not in isi and "akan dimatikan" not in isi


def test_operasional_backup_belum_tercatat_dan_prasyarat_belum_siap_tetap_teks():
    isi = ui.operasional(_ringkas(siap=False), "", "")

    assert "Cadangan mencakup data sampai:" in isi and "belum tercatat" in isi
    assert isi.count("Belum siap") >= 4
    assert 'admin-baris-status perhatian' in isi  # baris cadangan yang belum terverifikasi disorot


def test_operasional_tanpa_config_dukungan_netral_bukan_kotak_merah():
    isi = ui.operasional(_ringkas(dukungan=False), "", "")

    kartu = _kartu(isi, "dukungan")
    assert "admin-galat" not in kartu and 'role="alert"' not in kartu
    assert '<span class="admin-badge">Belum siap</span>' in kartu and "kontak publik ditahan" in kartu
    assert "migrator" not in isi and "<form" not in isi
    assert '<span class="admin-badge perhatian">2 perlu dilihat</span>' in isi  # cadangan + dukungan


def test_operasional_baca_saja_tanpa_form_walau_semua_bagian_ada():
    bagian = _bagian(tokens=None)
    isi = ui.operasional(_ringkas(), "", "", sakelar=bagian, pendaftaran=sak.halaman_pendaftaran_baca(True),
                         status_rekening="terisi", pendaftaran_dibuka=True)

    assert "<form" not in isi and 'name="reauth"' not in isi and "<button" not in isi
    assert "Tampilan baca-saja" in isi
