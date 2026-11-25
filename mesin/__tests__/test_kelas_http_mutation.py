"""Mutation guard BARU lapisan HTTP Paket Belajar: gerbang sakelar, admin-saja, siswa dari sesi, bukti dilihat, form ketat.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi dan memastikan tes terkait MERAH karena perilaku, lalu
hijau setelah dipulihkan (harness bersama Latihan Harian: `harian_mutasi_kit`). Workspace asli tidak disentuh.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_ADMIN = "test_kelas_admin_http.py"
TES_MURID = "test_kelas_murid_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + (
    "conftest.py", TES_ADMIN, TES_MURID)

MURID = "kelas_murid_http.py"
ADMIN = "kelas_admin_http.py"

_GERBANG_MURID = "test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal"
_ADMIN_SAJA = "test_non_admin_404_identik_rute_tak_dikenal_sakelar_mati_atau_hidup or test_post_non_admin_tanpa_efek"
_SISWA_SESI = "test_kueri_siswa_diabaikan_get_dan_post or test_isolasi_murid_a_b_tagihan_status_dan_bukti"
_FORM_KETAT = "test_nominal_tidak_bisa_dari_form"
_TOKEN_KODE = "test_token_salah_atau_untuk_kode_lain_atau_akun_lain_ditolak"
_SATU_TAGIHAN = "test_satu_tagihan_terbuka_per_anak_idempoten_dan_paket_lain_konflik"
_REKENING = "test_rekening_kosong_halaman_jujur_dan_post_404_tanpa_efek"
_BUKTI_BASI = "test_tinjauan_basi_bukti_baru_ditolak_409_tanpa_efek"
_FIELD_ASING = "test_target_tidak_dari_field_form"
_DEPOSIT_PESAN = "test_deposit_tidak_lagi_berlaku_setujui_ditolak_pesan_jelas_tanpa_akses"
_SAKELAR_ADMIN = "test_sakelar_mati_antrean_detail_pratinjau_dan_putusan_admin_tetap_terbuka"
_BERKAS_GAGAL = "test_gagal_catat_menghapus_berkas"
_BERKAS_SAMA = "test_unggah_berkas_sama_tidak_ganda_dan_batas_lima"
_ADMIN_GET_ANTREAN = ("    principal = h._principal_admin(penangan)\n    if principal is None:\n"
                      "        h._tidak_ada(penangan)\n        return True\n    {ui.RUTE: _get_antrean")
_ADMIN_POST_PALANG = ("    principal = h._principal_admin(penangan)\n    if principal is None:\n"
                      "        h._tidak_ada(penangan)\n        return True\n    aksi.jalankan_aman(")

# (nama, berkas, [(lama, baru), ...], berkas tes, ekspresi -k)
KASUS = (
    ("murid_get_tanpa_gerbang_sakelar", MURID, [
        ("    if jalur not in _GET or not paket_belajar_gate.aktif():", "    if jalur not in _GET:"),
    ], TES_MURID, _GERBANG_MURID),
    ("murid_post_tanpa_gerbang_sakelar", MURID, [
        ("    if jalur not in _POST or not paket_belajar_gate.aktif():", "    if jalur not in _POST:"),
    ], TES_MURID, _GERBANG_MURID),
    ("admin_get_tanpa_palang_admin", ADMIN, [
        (_ADMIN_GET_ANTREAN, "    principal = penangan._principal()\n    if False:\n"
                             "        h._tidak_ada(penangan)\n        return True\n    {ui.RUTE: _get_antrean"),
    ], TES_ADMIN, _ADMIN_SAJA),
    ("admin_post_tanpa_palang_admin", ADMIN, [
        (_ADMIN_POST_PALANG, "    principal = penangan._principal()\n    if principal is None:\n"
                             "        h._tidak_ada(penangan)\n        return True\n    aksi.jalankan_aman("),
    ], TES_ADMIN, _ADMIN_SAJA),
    ("admin_get_kembali_dibatasi_sakelar", ADMIN, [
        ("import paket_belajar_katalog as katalog\n", "import paket_belajar_katalog as katalog\nimport paket_belajar_gate\n"),
        ("    if jalur not in RUTE_GET:\n        return False\n",
         "    if jalur not in RUTE_GET or not paket_belajar_gate.aktif():\n        return False\n"),
    ], TES_ADMIN, _SAKELAR_ADMIN),
    ("siswa_dari_kueri_bukan_sesi", MURID, [
        ("    return None if siswa_id is None else (principal, siswa_id)",
         "    import urllib.parse as _u\n    _q = _u.parse_qs(_u.urlsplit(penangan.path).query).get('siswa_id')\n"
         "    siswa_id = int(_q[0]) if _q else siswa_id\n    return None if siswa_id is None else (principal, siswa_id)"),
    ], TES_MURID, _SISWA_SESI),
    ("form_buat_menerima_field_asing", MURID, [
        ("    if data is None or set(data) != KUNCI_FORM_BUAT:", "    if data is None or not set(data) >= KUNCI_FORM_BUAT:"),
    ], TES_MURID, _FORM_KETAT),
    ("token_buat_tidak_terikat_kode", MURID, [
        ("aksi + kode, data[\"token\"]", "aksi + \"mini\", data[\"token\"]"),
    ], TES_MURID, _TOKEN_KODE),
    ("satu_tagihan_lintas_paket_dilepas", MURID, [
        ("store.buat_tagihan(kon, akun_id, siswa_id, kode, kini, tolak_paket_lain_terbuka=True)",
         "store.buat_tagihan(kon, akun_id, siswa_id, kode, kini, tolak_paket_lain_terbuka=False)"),
    ], TES_MURID, _SATU_TAGIHAN),
    ("rekening_kosong_tetap_melayani_post", MURID, [
        ("    if _rekening() is None:  # gerbang pembayaran tertutup", "    if False:  # gerbang pembayaran tertutup"),
    ], TES_MURID, _REKENING),
    ("berkas_tidak_dihapus_bila_catat_gagal", MURID, [
        ("    except BaseException:\n        berkas.hapus(nama)\n        raise", "    except BaseException:\n        raise"),
    ], TES_MURID, _BERKAS_GAGAL),
    ("berkas_duplikat_tidak_dihapus", MURID, [
        ("    if not hasil[\"baru\"]:\n        berkas.hapus(nama)", "    if False:\n        berkas.hapus(nama)"),
    ], TES_MURID, _BERKAS_SAMA),
    ("bukti_dilihat_bukan_dari_tinjauan", ADMIN, [
        ("    with _buka(tulis=True) as kon:\n        if setuju:",
         "    with _buka(tulis=True) as kon:\n"
         "        dilihat = putusan.detail(kon, order_id, alur.waktu_sekarang())['bukti_terakhir_id']\n        if setuju:"),
    ], TES_ADMIN, _BUKTI_BASI),
    ("field_asing_putusan_diterima", ADMIN, [
        ("    aksi.wajib_field(data, frozenset() if setuju else frozenset({\"alasan\"}))\n", ""),
    ], TES_ADMIN, _FIELD_ASING),
    ("deposit_tidak_aktif_pesan_generik", ADMIN, [
        ("    except dasar.DepositTidakAktif:\n        h._galat(penangan, 409, COPY_DEPOSIT_TIDAK_AKTIF)",
         "    except dasar.DepositTidakAktif:\n        raise"),
    ], TES_ADMIN, _DEPOSIT_PESAN),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_guard_http_kelas_merah_lalu_pulih(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)


# --- ganti paket (butir QA #3, 25 Nov 2026) -------------------------------------------------------------------
TES_GANTI_DOMAIN = "test_kelas_ganti.py"
TES_GANTI_HTTP = "test_kelas_ganti_http.py"
SALIN_GANTI = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + (
    "conftest.py", TES_GANTI_DOMAIN, TES_GANTI_HTTP)

KASUS_GANTI = (
    # Dua guard lain di kelas_ganti (jumlah_bukti, len(terbuka)) tumpang tindih dengan status turunan dan trigger DB
    # untuk dua paket yang ada sekarang (mutan setara, tak bisa merah); dipertahankan sebagai pertahanan berlapis.
    ("ganti_deposit_tidak_dipindah", "kelas_ganti.py", [
        ('kon, akun_id, siswa_id, paket, kini, lama["id"])', "kon, akun_id, siswa_id, paket, kini)"),
    ], TES_GANTI_DOMAIN, "test_deposit_peta_ikut_ke_tagihan_baru"),
    ("ganti_token_tidak_terikat_aksi", MURID, [
        ("_form_buat(penangan, principal, halaman.AKSI_GANTI)", "_form_buat(penangan, principal, halaman.AKSI_BUAT)"),
    ], TES_GANTI_HTTP, "test_ganti_berhasil_halaman_menampilkan_tagihan_baru_dan_bukti_masuk_ke_tagihan_baru"),
    ("tagihan_berjalan_bukan_yang_terbaru", MURID, [
        ("    for order, _fakta, _status in ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini):\n        return",
         "    for order, _fakta, _status in reversed(list(ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini))):\n        return"),
    ], TES_GANTI_HTTP, "test_ganti_berhasil_halaman_menampilkan_tagihan_baru_dan_bukti_masuk_ke_tagihan_baru"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS_GANTI, ids=[k[0] for k in KASUS_GANTI])
def test_mutasi_guard_ganti_paket_merah_lalu_pulih(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_GANTI)
