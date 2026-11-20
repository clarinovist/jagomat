"""Permukaan anak sesi Cek Kemampuan gratis (`/mulai/{token}`): alur, palang, dispatch, validasi."""
from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_anak_http  # noqa: E402
import cek_anak_komponen  # noqa: E402
import cek_gratis  # noqa: E402
import cek_gratis_skor  # noqa: E402
import database  # noqa: E402
import student_pages  # noqa: E402
import students  # noqa: E402
from cek_anak_kit import (  # noqa: E402
    JUMLAH, POLA_REVISI, Cek, PenanganPalsu, buang_soal_dan_gaya, daftar_sesi_biasa, lokasi, minta,
    pasang_gerbang_kunci, lepas_gerbang, server,  # noqa: F401  (fixture)
)
from cek_gratis_kit import ID_A, SEKARANG  # noqa: E402

KATA_TERLARANG = (
    "kunci", "malrule", "diagnos", "skor", "kategori", "benar", "salah", "kelemahan",
    "gurumu akan memeriksa", "kode_final", "persentil", "peringkat",
)
DI = "di=hp-ini"


@pytest.fixture()
def cek(server):
    return Cek(server)


def _simpan_semua(cek, lewati=()):
    for nomor in range(1, JUMLAH + 1):
        if nomor not in lewati:
            assert cek.simpan(nomor)[0] == 303


# --- konstanta ------------------------------------------------------------

def test_topik_cek_anak_sama_dengan_modul_skor():
    assert set(cek_anak_komponen.TOPIK_CEK) == set(cek_gratis_skor.semua_topik_cek())
    assert len(cek_anak_komponen.TOPIK_CEK) == len(set(cek_anak_komponen.TOPIK_CEK))
    for topik_id in cek_anak_komponen.TOPIK_CEK:
        assert topik_id in cek_anak_komponen.WARNA_TOPIK
        assert topik_id in cek_anak_komponen.IKON_TOPIK


@pytest.mark.parametrize("topik_id,nama", [
    ("berhitung-sekolah", "Berhitung"), ("pengukuran", "Pengukuran"),
    ("aritmetika-dasar", "Aritmetika dasar"), ("aritmatika-lanjut", "Aritmetika lanjut"),
])
def test_label_topik_baru_tampil_nama_materi_tanpa_kata_skor(topik_id, nama):
    import topics

    template_id = next(iter(topics.ambil(topik_id).templates))

    html_label = cek_anak_komponen.label_topik(template_id)

    assert ">" + nama + "</span>" in html_label
    assert "<svg" in html_label and "#" not in html_label
    for terlarang in ("kemampuan", "kelemahan", "skor", "kategori", "benar", "salah"):
        assert terlarang not in html_label.lower()


def test_tujuan_login_persis_sesuai_kontrak_orang_tua():
    assert cek_anak_komponen.TUJUAN_LOGIN_HASIL == "/masuk?lanjut=/cek-kemampuan/hasil"


# --- alur penuh -----------------------------------------------------------

def test_alur_penuh_sapaan_simpan_lewati_jeda_peta_kumpulkan_hore(cek):
    kode, isi, _t = cek.get()
    assert kode == 200 and "Ayo mulai!" in isi and 'name="aksi" value="mulai"' in isi
    assert cek.status_sesi()[0] is None

    kode, _i, tajuk = cek.post({"aksi": "mulai"})
    assert (kode, lokasi(tajuk)) == (303, cek.jalur(soal=1))
    assert cek.status_sesi()[0] is not None

    kode, isi, _t = cek.get(soal=1)
    assert kode == 200 and f"Soal <b>1</b> dari {JUMLAH}" in isi and 'name="opsi_' in isi

    lokasi_setelah = {}
    for nomor in range(1, 6):
        if nomor == 3:
            continue  # "Lewati dulu" = tautan biasa, tanpa menulis
        kode, _i, tajuk = cek.simpan(nomor)
        assert kode == 303
        lokasi_setelah[nomor] = lokasi(tajuk)
    assert "soal=2" in lokasi_setelah[1] and "ok=simpan" in lokasi_setelah[1]
    assert lokasi_setelah[5].endswith("?jeda=5")
    assert cek.terjawab() == 4

    kode, isi, _t = cek.get(jeda=5)
    assert kode == 200 and "Wah, sudah 5 soal!" in isi and "Sepertiga jalan" in isi
    assert f'href="/mulai/{cek.token}?soal=6"' in isi

    for nomor in range(6, 11):
        kode, _i, tajuk = cek.simpan(nomor)
        assert kode == 303
    assert lokasi(tajuk).endswith("?jeda=10")
    assert cek.get(jeda=10)[0] == 200

    for nomor in (11, 12, 14, 15):  # 13 sengaja dikosongkan
        kode, _i, tajuk = cek.simpan(nomor)
        assert kode == 303
    assert lokasi(tajuk).endswith("peta=1&ok=simpan")
    assert cek.terjawab() == 13

    kode, isi, _t = cek.get(peta=1)
    assert kode == 200 and "2 soal yang masih kosong" in isi
    assert isi.count('class="kosong"') == 2 and "Ya, kumpulkan" in isi

    kode, isi, _t = cek.kumpul()
    assert kode == 200 and "Hore" in isi and "13 dari 15 soal dijawab" in isi
    assert "Pejuang 15 Soal" in isi

    assert cek.get()[0] == 404 and cek.post({"aksi": "mulai"})[0] == 404
    assert cek.get(soal=1)[0] == 404
    with cek.server.buka() as kon:
        assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
        hasil = cek_gratis.baca_hasil(kon, ID_A)
        sumber = kon.execute("SELECT sumber FROM pengiriman_sesi WHERE sesi_id = ?", (cek.sesi_id,)).fetchone()[0]
    assert hasil["status"] == "selesai" and 0 <= hasil["skor"] <= 100
    assert sumber == "tautan"


def test_kumpulkan_tanpa_satu_pun_jawaban_tetap_menyelesaikan_sesi(cek):
    kode, isi, _t = cek.kumpul()
    assert kode == 200 and "0 dari 15 soal dijawab" in isi
    with cek.server.buka() as kon:
        assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
        assert cek_gratis.baca_hasil(kon, ID_A)["skor"] == 0


def test_jeda_hanya_sekali_dan_tidak_dari_peta(cek):
    for nomor in range(1, 7):
        cek.simpan(nomor)
    kode, _i, tajuk = cek.get(jeda=5)
    assert (kode, lokasi(tajuk)) == (303, cek.jalur(soal=6))  # soal 6 sudah terjawab: jeda tak diulang
    kode, _i, tajuk = cek.simpan(5, dari="peta")
    assert kode == 303 and lokasi(tajuk).endswith("peta=1&ok=simpan") and "jeda" not in lokasi(tajuk)


def test_jeda_ditolak_di_luar_soal_5_dan_10(cek):
    for nilai in ("1", "4", "15", "0", "x"):
        assert cek.get(jeda=nilai)[0] == 404


def test_lanjut_dari_soal_kosong_pertama_atau_peta(cek):
    assert "Ayo mulai!" in cek.get()[1]
    cek.simpan(1)
    cek.simpan(2)
    kode, _i, tajuk = cek.get()
    assert (kode, lokasi(tajuk)) == (303, cek.jalur(soal=3))
    _simpan_semua(cek)
    kode, _i, tajuk = cek.get()
    assert (kode, lokasi(tajuk)) == (303, cek.jalur(peta=1))


def test_istirahat_menyimpan_pilihan_lalu_layar_tersimpan(cek):
    kode, _i, tajuk = cek.simpan(1, aksi="keluar")
    assert (kode, lokasi(tajuk)) == (303, cek.jalur(keluar=1)) and cek.terjawab() == 1
    kode, isi, _t = cek.get(keluar=1)
    assert kode == 200 and "Tersimpan!" in isi and "tautan yang sama" in isi
    kode, _i, tajuk = cek.post({"aksi": "keluar", "soal": "2", "revisi_pekerjaan": str(cek.revisi())})
    assert kode == 303 and cek.terjawab() == 1  # tanpa pilihan: tidak ada yang tertulis


def test_simpan_tanpa_pilihan_tampil_pesan_netral_tanpa_menulis(cek):
    sebelum = cek.jawaban()
    kode, isi, _t = cek.simpan(2, opsi=None)
    assert kode == 200 and "Pilih satu jawaban dulu" in isi and "Soal <b>2</b>" in isi
    assert cek.jawaban() == sebelum


def test_revisi_naik_dan_halaman_berikutnya_memuat_revisi_terkini(cek):
    awal = cek.revisi()
    cek.simpan(1)
    assert cek.revisi() == awal + 1
    _k, isi, _t = cek.get(soal=2)
    assert POLA_REVISI.search(isi).group(1) == str(cek.revisi())


def test_mengganti_pilihan_menimpa_jawaban_lama(cek):
    cek.simpan(1, opsi="opsi_1")
    cek.simpan(1, opsi="opsi_2")
    assert cek.terjawab() == 1
    _k, isi, _t = cek.get(soal=1)
    assert re.search(r'value="opsi_2" checked', isi) and not re.search(r'value="opsi_1" checked', isi)


# --- tautan lain tidak berubah -------------------------------------------

def test_sesi_biasa_dengan_funnel_hidup_byte_identik_dengan_jalur_lama(server):
    siswa, sesi, token = daftar_sesi_biasa(server)
    kode, isi, _t = minta(server, f"/mulai/{token}")
    with server.buka() as kon:
        lama = student_pages.halaman_kerja_baru(kon, siswa, sesi, jalur_aksi=f"/mulai/{token}", akses_tautan=True)
    assert kode == 200 and isi.encode() == lama
    assert "cek-anak" not in isi
    kode, isi, _t = minta(server, f"/mulai/{token}", {"aksi": "mulai"})
    assert (kode, isi) == (200, '{"mulai": true}')


def test_sesi_cek_dengan_funnel_mati_byte_identik_dengan_jalur_lama(cek, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    kode, isi, _t = cek.get()
    with cek.server.buka() as kon:
        lama = student_pages.halaman_kerja_baru(
            kon, cek.siswa_id, cek.sesi_id, jalur_aksi=f"/mulai/{cek.token}", akses_tautan=True)
    assert kode == 200 and isi.encode() == lama and "cek-anak" not in isi
    # Aksi lama tetap berlaku: simpan lewat jalur lama tidak ditolak oleh whitelist cek.
    kode, _i, _t = cek.post({"aksi": "mulai", "bebas": "1"})
    assert kode == 200


def test_token_tidak_sah_404_identik_di_semua_jalur(server, cek):
    palsu = "A" * 43
    kode_a, isi_a, _t = minta(server, f"/mulai/{palsu}")
    kode_b, isi_b, _t = minta(server, f"/mulai/{palsu}?soal=1")
    kode_c, isi_c, _t = minta(server, f"/mulai/{palsu}", {"aksi": "simpan"})
    assert (kode_a, kode_b, kode_c) == (404, 404, 404) and isi_a == isi_b == isi_c


# --- palang murid ----------------------------------------------------------

def _semua_layar_html(cek):
    """HTML tiap layar anak (kondisi terjawab sebagian)."""
    cek.simpan(1)
    cek.simpan(2)
    hasil = {
        "soal1": cek.get(soal=1)[1], "soal2": cek.get(soal=2)[1], "soal15": cek.get(soal=15)[1],
        "jeda": cek.get(jeda=5)[1], "peta": cek.get(peta=1)[1], "keluar": cek.get(keluar=1)[1],
        "galat": cek.simpan(3, opsi=None)[1],
        "usang": cek.post({"aksi": "simpan", "soal": "3", "revisi_pekerjaan": "999"})[1],
    }
    hasil["hore_hp_ini"] = cek.kumpul(di=True)[1]
    return hasil


def test_tidak_ada_kunci_skor_kategori_atau_benar_salah_di_layar_anak(cek):
    layar = _semua_layar_html(cek)
    sapaan = Cek(cek.server, nama="Anak Dua", akun="akun_" + "d4" * 16).get()[1]
    layar["sapaan"] = sapaan
    for nama, isi in layar.items():
        polos = buang_soal_dan_gaya(isi).lower()
        for kata in KATA_TERLARANG:
            assert kata not in polos, (nama, kata)
        assert 'name="jwb_' not in isi and 'value=""' not in isi and "Belum menjawab" not in isi, nama
        assert "confirm(" not in isi and "<script src" not in isi, nama


def test_layar_anak_tidak_membaca_kolom_kunci_atau_diagnosis(cek):
    with cek.server.buka() as kon:
        cek_anak = cek_anak_http
        pasang_gerbang_kunci(kon)
        akses = {"siswa_id": cek.siswa_id, "sesi_id": cek.sesi_id}
        for query in ("", "?soal=3", "?soal=15&dari=peta", "?jeda=5", "?peta=1", "?keluar=1", "?di=hp-ini"):
            penangan = PenanganPalsu(f"/mulai/{cek.token}{query}")
            assert cek_anak.tangani_get(penangan, kon, cek.token, akses) is True
            assert penangan.kode in (200, 303), query
        lepas_gerbang(kon)


def test_penyaring_palang_menolak_pembacaan_kunci_lewat_gerbang(cek):
    """Pastikan gerbang benar-benar menolak (supaya tes di atas bermakna)."""
    with cek.server.buka() as kon:
        pasang_gerbang_kunci(kon)
        with pytest.raises(Exception):
            database.isi_sesi(kon, cek.sesi_id)
        lepas_gerbang(kon)


def test_gaya_dan_modul_anak_tanpa_hex_literal():
    pola = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    akar = Path(__file__).resolve().parent.parent
    for nama in ("cek_anak_style.py", "cek_anak_komponen.py", "cek_anak_pages.py", "cek_anak_http.py"):
        sumber = (akar / nama).read_text()
        assert not pola.search(sumber), nama


def test_css_hanya_di_halaman_cek_anak_dan_bukan_gaya_stitch(cek):
    _k, isi, _t = cek.get()
    assert 'class="cek-anak"' in isi and ".kerja-editorial-st" not in isi
    siswa, sesi, token = daftar_sesi_biasa(cek.server)
    assert "opsi-satu" not in minta(cek.server, f"/mulai/{token}")[1]


def test_tidak_ada_sensitif_di_header_dan_tidak_di_cache(cek):
    _k, _i, tajuk = cek.get(soal=1)
    assert tajuk["Cache-Control"] == "no-store" and "noindex" in tajuk["X-Robots-Tag"]
    kode, _i, tajuk = cek.simpan(1)
    assert kode == 303 and tajuk["Cache-Control"] == "no-store"


# --- skrip papan coret & CSP ----------------------------------------------

def test_hanya_soal_memuat_satu_skrip_polos_berhash_tanpa_network(cek):
    _k, isi, tajuk = cek.get(soal=1)
    skrip = re.findall(r"<script>(.*?)</script>", isi, flags=re.S)
    assert len(skrip) == 1 and isi.count("<script") == 1
    hash_skrip = base64.b64encode(hashlib.sha256(skrip[0].encode()).digest()).decode()
    assert f"'sha256-{hash_skrip}'" in tajuk["Content-Security-Policy"]
    for terlarang in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "indexedDB", "WebSocket", "sendBeacon", "confirm("):
        assert terlarang not in skrip[0]
    assert re.search(r'<button[^>]*id="btn-coret"[^>]*\bhidden\b', isi)
    assert re.search(r'<div[^>]*id="papan"[^>]*\bhidden\b', isi)
    for halaman in (cek.get()[1], cek.get(peta=1)[1], cek.get(jeda=5)[1], cek.get(keluar=1)[1]):
        assert "<script" not in halaman
    assert "script-src 'none'" in cek.get(peta=1)[2]["Content-Security-Policy"]


def test_lewati_dulu_tautan_biasa_bukan_pengiriman_form(cek):
    _k, isi, _t = cek.get(soal=2)
    assert f'<a class="sekunder" href="/mulai/{cek.token}?soal=3&amp;ok=lewat">Lewati dulu</a>' in isi
    _k, isi, _t = cek.get(soal=5)
    assert f'?jeda=5">Lewati dulu</a>' in isi
    _k, isi, _t = cek.get(soal=2, dari="peta")
    assert "peta=1" in re.search(r'<a class="sekunder" href="([^"]+)">Lewati dulu', isi).group(1)


# --- validasi ---------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "soal=0", "soal=16", "soal=abc", "soal=-1", "soal=1.5", "soal=", "soal=1&soal=2",
    "soal=1&peta=1", "peta=1&keluar=1", "jeda=5&soal=6", "soal=%E0%A4%A", "soal=1000", "soal=0003x",
])
def test_query_get_tidak_sah_ditolak_404_tanpa_efek(cek, query):
    sebelum, status = cek.jawaban(), cek.status_sesi()
    kode, isi, _t = minta(cek.server, f"/mulai/{cek.token}?{query}")
    assert kode == 404 and "Halaman tidak ada" in isi
    assert (cek.jawaban(), cek.status_sesi()) == (sebelum, status)


@pytest.mark.parametrize("nilai", ["0", "16", "x", "-1", "1.5", "", "99999"])
def test_post_nomor_soal_tidak_sah_ditolak_tanpa_efek(cek, nilai):
    cek.simpan(1)
    sebelum = cek.jawaban()
    kode, _i, _t = cek.post({
        "aksi": "simpan", "soal": nilai, "revisi_pekerjaan": str(cek.revisi()),
        f"opsi_{cek.id_butir(2)}": "opsi_1",
    })
    assert kode == 400 and cek.jawaban() == sebelum


def test_opsi_bukan_milik_butir_itu_ditolak(cek):
    sebelum = cek.jawaban()
    asing = cek.id_butir(2)
    kode, _i, _t = cek.post({
        "aksi": "simpan", "soal": "1", "revisi_pekerjaan": str(cek.revisi()), f"opsi_{asing}": "opsi_1",
    })
    assert kode == 400 and cek.jawaban() == sebelum
    kode, _i, _t = cek.post({
        "aksi": "simpan", "soal": "1", "revisi_pekerjaan": str(cek.revisi()), "opsi_999999": "opsi_1",
    })
    assert kode == 400 and cek.jawaban() == sebelum


@pytest.mark.parametrize("nilai", ["", "opsi_9", "A", "opsi_1 ", "OPSI_1", "../x"])
def test_nilai_opsi_di_luar_pilihan_butir_ditolak_dan_tidak_menghapus(cek, nilai):
    cek.simpan(1)
    sebelum = cek.jawaban()
    kode, _i, _t = cek.simpan(1, opsi=nilai)
    assert kode == 400 and cek.jawaban() == sebelum


@pytest.mark.parametrize("ekstra", [
    {"cara_1": "isi"}, {"jwb_1": "9"}, {"restate_1": "x"}, {"blm_1": "on"}, {"hadir_blm_1": "1"},
    {"flow_kosong": "1"}, {"aksi_lain": "x"}, {"dari": "bukan-peta"},
])
def test_field_di_luar_daftar_putih_ditolak_tanpa_efek(cek, ekstra):
    sebelum = cek.jawaban()
    kode, _i, _t = cek.simpan(1, **ekstra)
    assert kode == 400 and cek.jawaban() == sebelum


@pytest.mark.parametrize("data", [
    {"aksi": "selesai"}, {"aksi": "kirim_latihan"}, {"aksi": "kembali"}, {"aksi": ""}, {},
    {"aksi": "mulai", "soal": "1"}, {"aksi": "kumpul", "opsi_1": "opsi_1"},
])
def test_aksi_dan_kombinasi_tidak_dikenal_ditolak(cek, data):
    kode, _i, _t = cek.post(data)
    assert kode == 400
    assert cek.status_sesi()[1] is None and cek.jawaban() == []


def test_revisi_usang_atau_hilang_ditolak_409_tanpa_efek(cek):
    cek.simpan(1)
    sebelum = cek.jawaban()
    id2 = cek.id_butir(2)
    kode, isi, _t = cek.post({"aksi": "simpan", "soal": "2", "revisi_pekerjaan": "0", f"opsi_{id2}": "opsi_1"})
    assert kode == 409 and "Muat ulang halaman" in isi and f"/mulai/{cek.token}?soal=2" in isi
    kode, _i, _t = cek.post({"aksi": "simpan", "soal": "2", f"opsi_{id2}": "opsi_1"})
    assert kode == 409
    kode, _i, _t = cek.post({"aksi": "kumpul", "revisi_pekerjaan": "999"})
    assert kode == 409 and cek.status_sesi()[1] is None
    kode, _i, _t = cek.post({"aksi": "kumpul"})
    assert kode == 409 and cek.status_sesi()[1] is None
    assert cek.jawaban() == sebelum


def test_isian_ganda_ditolak_seperti_jalur_lama(cek):
    kode, isi, _t = minta(cek.server, cek.jalur(), b"aksi=mulai&aksi=simpan")
    assert kode == 400 and "Isian ganda" in isi
    assert cek.status_sesi()[0] is None


# --- di=hp-ini ---------------------------------------------------------------

def test_tombol_masuk_hanya_muncul_dengan_penanda_di_hp_ini(cek):
    _k, isi_ini, _t = cek.kumpul(di=True)
    assert 'href="/masuk?lanjut=/cek-kemampuan/hasil"' in isi_ini
    assert "Ayah/Bunda, masuk untuk lihat hasil" in isi_ini and "Tunjukkan layar ini" not in isi_ini


def test_tanpa_penanda_hp_anak_tidak_menampilkan_login(server):
    cek = Cek(server, akun="akun_" + "e5" * 16)
    _k, isi, _t = cek.kumpul()
    assert "/masuk" not in isi and "Tunjukkan layar ini ke Ayah/Bunda" in isi
    assert "dibuka di HP Ayah/Bunda" in isi


def test_nilai_di_selain_hp_ini_dianggap_tanpa_penanda(cek):
    kode, isi, _t = minta(cek.server, cek.jalur(di="1", soal=1))
    assert kode == 200 and "di=hp-ini" not in isi
    _k, isi, _t = cek.post({"aksi": "kumpul", "revisi_pekerjaan": str(cek.revisi())}, di=False)
    assert "/masuk" not in isi


def test_penanda_dibawa_di_semua_tautan_aksi_dan_pengalihan(cek):
    semua = [cek.get(di="hp-ini")[1]]
    semua += [minta(cek.server, cek.jalur(**{"soal": n, "di": "hp-ini"}))[1] for n in (1, 5, 15)]
    semua += [minta(cek.server, cek.jalur(jeda=5, di="hp-ini"))[1], minta(cek.server, cek.jalur(peta=1, di="hp-ini"))[1],
              minta(cek.server, cek.jalur(keluar=1, di="hp-ini"))[1]]
    for isi in semua:
        tautan = re.findall(r'(?:href|action)="(/mulai/[^"]*)"', isi)
        assert tautan and all(DI in t for t in tautan), isi[:200]
    kode, _i, tajuk = cek.post({"aksi": "mulai"}, di=True)
    assert kode == 303 and DI in lokasi(tajuk)
    revisi = cek.revisi()
    kode, _i, tajuk = cek.post({"aksi": "simpan", "soal": "1", "revisi_pekerjaan": str(revisi),
                                f"opsi_{cek.id_butir(1)}": "opsi_1"}, di=True)
    assert kode == 303 and DI in lokasi(tajuk)
    kode, _i, tajuk = minta(cek.server, cek.jalur(di="hp-ini"))
    assert kode == 303 and DI in lokasi(tajuk)


def test_penanda_tidak_memberi_akses_ke_hasil(cek):
    _k, isi, _t = cek.kumpul(di=True)
    assert "skor" not in isi.lower() and 'href="/masuk?lanjut=/cek-kemampuan/hasil"' in isi
    assert minta(cek.server, "/cek-kemampuan/hasil")[0] in (302, 303, 401, 404)


# --- finalisasi & mutasi -----------------------------------------------------

def test_finalisasi_menandai_selesai_sekali_dan_mengarsip(cek):
    cek.simpan(1)
    kode, _i, _t = cek.kumpul()
    assert kode == 200
    mulai, selesai = cek.status_sesi()
    assert mulai is not None and selesai is not None
    with cek.server.buka() as kon:
        arsip = kon.execute("SELECT COUNT(*) FROM pengiriman_butir WHERE sesi_id = ?", (cek.sesi_id,)).fetchone()[0]
    assert arsip == JUMLAH


def test_soal_murid_dipakai_untuk_data_dan_jumlah_soal(cek):
    with cek.server.buka() as kon:
        daftar = students.soal_murid(kon, cek.sesi_id, cek.siswa_id)
    assert len(daftar) == JUMLAH and all(e["pilihan"] is not None for e in daftar)
    for entri in daftar[:3]:
        assert cek.get(soal=entri["nomor"])[0] == 200


def test_definisi_terjawab_sama_dengan_status_orang_tua(cek):
    """`sudah_dijawab` anak harus sejalan dengan hitungan cek_status (jawaban teks tidak kosong)."""
    import cek_status
    from cek_anak_pages import sudah_dijawab

    for nomor in (1, 4, 9):
        cek.simpan(nomor)
    cek.simpan(4, opsi="opsi_2")  # ganti pilihan tidak menambah hitungan
    with cek.server.buka() as kon:
        daftar = students.soal_murid(kon, cek.sesi_id, cek.siswa_id)
        assert sum(1 for e in daftar if sudah_dijawab(e)) == cek_status._terjawab(kon, cek.sesi_id) == 3
    assert not sudah_dijawab({"terjawab": {"jawaban": "  "}}) and not sudah_dijawab({"terjawab": None})
