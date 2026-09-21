"""Halaman /admin — panel khusus pengelola (role admin).

Admin = pemilik produk: melihat semua keluarga dan membuat akun orang tua.
Guru, murid, dan anonim tidak boleh masuk — tolakan 401, karena halaman
ini memuat daftar akun dan nama anak lintas keluarga.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SANDI_A = "sandi-ortu-a-1234567"
SANDI_ADMIN = "sandi-pengelola-9999"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        a = database.tambah_siswa(kon, "BimaA", "P3", pemilik="ortu-a")
        database.buat_sesi(kon, a, seed=5)
    auth.tambah_akun("ortu-a", SANDI_A, "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("pengelola", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    yield s
    s.berhenti()


def test_bukan_admin_ditolak(server):
    assert server.minta("/admin")[0] == 404
    kode, isi, _ = server.minta("/admin", auth=("guru", SANDI_GURU))
    assert kode == 404
    assert "BimaA" not in isi, "daftar keluarga bocor ke guru"
    kode, _, _ = server.minta("/admin", auth=("feby", SANDI_MURID))
    assert kode == 404
    kode, _, _ = server.minta("/admin", method="POST", data={})
    assert kode == 404


def test_admin_melihat_daftar_keluarga(server):
    kode, isi, _ = server.minta("/admin", auth=("pengelola", SANDI_ADMIN))
    assert kode == 200
    assert "ortu-a" in isi
    assert "BimaA" in isi
    assert "Panel Pengelola" in isi
    kode, keluarga, _ = server.minta(
        "/admin?section=keluarga", auth=("pengelola", SANDI_ADMIN)
    )
    assert kode == 200 and "guru" in keluarga


def test_post_admin_lama_tidak_bisa_membuat_akun_orang_tua(server):
    kode, _, _ = server.minta(
        "/admin",
        auth=("pengelola", SANDI_ADMIN),
        data={
            "aksi": "guru_baru",
            "pengguna": "ortu-baru",
            "sandi": "sandi-ortu-baru-123",
        },
    )
    assert kode == 400
    assert auth.cari_akun("ortu-baru") is None


def test_guru_baru_nama_ganda_ditolak_tanpa_mengubah_lama(server):
    server.minta(
        "/admin",
        auth=("pengelola", SANDI_ADMIN),
        data={
            "aksi": "guru_baru",
            "pengguna": "ortu-a",
            "sandi": "sandi-penyerang-999",
        },
    )
    assert auth.periksa("ortu-a", SANDI_A), "sandi ortu-a ternyata berubah!"


def test_guru_baru_sandi_pendek_ditolak(server):
    kode, isi, _ = server.minta(
        "/admin",
        auth=("pengelola", SANDI_ADMIN),
        data={"aksi": "guru_baru", "pengguna": "pendek", "sandi": "pendek"},
    )
    assert kode == 400
    assert auth.cari_akun("pendek") is None


def test_css_badge_peran_tersedia():
    """Badge peran harus bergaya — bukan span telanjang di topbar."""
    import teacher_style

    assert ".badge-peran" in teacher_style.GAYA_GURU
    assert ".badge-keluarga" in teacher_style.GAYA_GURU


# --- Kebijakan admin: full-write (keputusan 4 Sep 2026) --------------------
#
# Dulu admin baca-semua-tulis-tidak (semua POST tulis -> 404). Kini admin
# boleh menulis seperti guru — panel /admin tanpa tombol hapus/edit
# menyulitkan kerja dukungan. Satu-satunya yang tetap tertutup: menyentuh
# sandi sesama admin/pengelola (milik deploy) via aksi guru_sandi/guru_hapus.


def _ids_siswa_dan_sesi(server):
    with server.buka() as kon:
        siswa = kon.execute(
            "SELECT id FROM siswa WHERE nama = 'BimaA'"
        ).fetchone()["id"]
        sesi_id = kon.execute("SELECT id FROM sesi LIMIT 1").fetchone()["id"]
    return siswa, sesi_id


def _opener_tanpa_ikut():
    import urllib.error
    import urllib.request

    class TanpaIkut(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(TanpaIkut)


def test_admin_setelah_masuk_diarahkan_ke_panel(server):
    import urllib.error
    import urllib.parse
    import urllib.request

    req = urllib.request.Request(
        server.alamat + "/masuk",
        data=urllib.parse.urlencode(
            {"nama": "pengelola", "sandi": SANDI_ADMIN}
        ).encode(),
        method="POST",
    )
    try:
        _opener_tanpa_ikut().open(req)
        kode, header = 200, {}
    except urllib.error.HTTPError as e:
        kode, header = e.code, dict(e.headers)
    assert kode == 303
    lokasi = [v for k, v in header.items() if k.lower() == "location"]
    assert lokasi == ["/admin"], "admin harus darat di dashboard admin"


def test_admin_buka_root_diarahkan_ke_panel(server):
    # urllib mengikuti 303 -> halaman /admin, BUKAN dashboard guru.
    kode, isi, _ = server.minta("/", auth=("pengelola", SANDI_ADMIN))
    assert kode == 200
    assert "Panel Pengelola" in isi
    assert "Buat sesi baru" not in isi, "admin masih pegang murid lewat /"


def test_admin_boleh_membuat_sesi(server):
    """Admin full-write: POST sesi-baru jalan dan sesinya benar-benar ada."""
    siswa_a, _ = _ids_siswa_dan_sesi(server)
    with server.buka() as kon:
        n0 = kon.execute("SELECT COUNT(*) AS n FROM sesi").fetchone()["n"]
    kode, _, _ = server.minta(
        f"/sesi-baru/{siswa_a}",
        auth=("pengelola", SANDI_ADMIN),
        data={"topik": "pola-bilangan", "mode": "diagnostik", "profil_parameter": "P3"},
    )
    assert kode in (200, 303)
    with server.buka() as kon:
        n1 = kon.execute("SELECT COUNT(*) AS n FROM sesi").fetchone()["n"]
    assert n1 == n0 + 1, "sesi admin tidak tersimpan"


def test_admin_boleh_hapus_sesi(server):
    """Admin full-write: hapus sesi jalan dan barisnya benar-benar hilang."""
    _, sesi_a = _ids_siswa_dan_sesi(server)
    kode, _, _ = server.minta(
        f"/sesi/{sesi_a}/hapus",
        auth=("pengelola", SANDI_ADMIN),
        data={"konfirmasi": "1"},
    )
    assert kode in (200, 303)
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE id = ?", (sesi_a,)
        ).fetchone()["n"]
    assert n == 0, "sesi tidak terhapus oleh admin"


def test_admin_boleh_simpan_jawaban(server):
    """Admin full-write: simpan jawaban jalan dan halaman bilang tersimpan."""
    import database

    _, sesi_a = _ids_siswa_dan_sesi(server)
    with server.buka() as kon:
        database.tandai_selesai(kon, sesi_a)
        sid = database.isi_sesi(kon, sesi_a)[0]["sesi_soal_id"]
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_a}",
        auth=("pengelola", SANDI_ADMIN),
        data={f"jwb_{sid}": "diisi admin", f"cara_{sid}": "cara admin"},
    )
    assert kode == 200
    # Tulisnya commit sesaat setelah respons (pola konteks buka()), jadi
    # yang diassert responsnya — bukan baca-ulang yang balapan dengan commit.
    assert "1 koreksi tersimpan" in isi, "simpan admin tidak jalan"


def test_admin_boleh_variasi_cerita_dan_lampiran(server):
    """Admin full-write: rute cerita & lampiran tidak lagi 404 khusus admin.

    Isi fiturnya sendiri bisa gagal-diam (tanpa kunci LLM / tanpa berkas),
    yang dijaga di sini: admin tidak ditolak di pintu hanya karena perannya."""
    _, sesi_a = _ids_siswa_dan_sesi(server)
    kode, _, _ = server.minta(
        f"/cerita/{sesi_a}", auth=("pengelola", SANDI_ADMIN), data={}
    )
    assert kode != 404, "rute cerita masih menutup admin"
    kode, _, _ = server.minta(
        f"/lampiran/{sesi_a}", auth=("pengelola", SANDI_ADMIN), data={"x": "1"}
    )
    assert kode != 404, "rute lampiran masih menutup admin"


def test_admin_ubah_tingkat_lama_ditolak_sandi_sendiri_tetap_di_akun(server):
    """Pengelolaan lintas keluarga wajib panel baru; sandi sendiri tetap tersedia."""
    siswa_a, _ = _ids_siswa_dan_sesi(server)
    awal = server.db.read_bytes()
    kode, isi, _ = server.minta(
        "/akun",
        auth=("pengelola", SANDI_ADMIN),
        data={"aksi": "tingkat", "siswa_id": siswa_a, "tingkat": "P4"},
    )
    assert kode == 200
    assert "Panel Pengelola" in isi  # urllib mengikuti redirect kanonis
    assert server.db.read_bytes() == awal

    kode, isi, _ = server.minta(
        "/akun",
        auth=("pengelola", SANDI_ADMIN),
        data={
            "aksi": "sandi",
            "lama": SANDI_ADMIN,
            "baru": "sandi-pengelola-baru-1",
            "ulang": "sandi-pengelola-baru-1",
        },
    )
    assert kode == 200
    assert "Sandi diganti" in isi


def test_halaman_sesi_admin_bisa_tulis(server):
    """Admin full-write: form tulis tampil untuk admin, bukan fieldset mati."""
    _, sesi_a = _ids_siswa_dan_sesi(server)
    with server.buka() as kon:
        database.tandai_selesai(kon, sesi_a)
    kode, isi, _ = server.minta(
        f"/sesi/{sesi_a}", auth=("pengelola", SANDI_ADMIN)
    )
    assert kode == 200
    assert "Konfirmasi hasil" in isi, "form tulis hilang untuk admin"
    assert "Hapus sesi" in isi
    # alat sesi pindah ke /cetak & /lampiran — /sesi hanya koreksi
    kode2, isi2, _ = server.minta(
        f"/sesi/{sesi_a}/cetak", auth=("pengelola", SANDI_ADMIN)
    )
    assert kode2 == 200
    assert "Lembar soal" in isi2, "jalur baca harus tetap ada"


def test_post_admin_lama_tidak_menghapus_akun_orang_tua_atau_anaknya(server):
    kode, _, _ = server.minta(
        "/admin",
        auth=("pengelola", SANDI_ADMIN),
        data={"aksi": "guru_hapus", "nama": "ortu-a"},
    )
    assert kode == 400
    assert auth.cari_akun("ortu-a") is not None
    with server.buka() as kon:
        n_siswa = kon.execute(
            "SELECT COUNT(*) AS n FROM siswa WHERE pemilik = 'ortu-a'"
        ).fetchone()["n"]
        n_sesi = kon.execute("SELECT COUNT(*) AS n FROM sesi").fetchone()["n"]
    assert n_siswa == 1, "anak ikut terhapus!"
    assert n_sesi == 1, "sesi ikut terhapus!"


def test_admin_tidak_bisa_hapus_akun_pengelola(server):
    """Sandi/akun sesama pengelola milik deploy — panel tidak boleh menyentuhnya."""
    auth.tambah_akun("pengelola-2", "sandi-pengelola-dua-1", "admin")
    kode, isi, _ = server.minta(
        "/admin",
        auth=("pengelola", SANDI_ADMIN),
        data={"aksi": "guru_hapus", "nama": "pengelola-2"},
    )
    assert kode == 400
    assert auth.cari_akun("pengelola-2") is not None, "akun pengelola ikut terhapus!"


def test_admin_laporan_tetap_terbuka(server):
    siswa_a, _ = _ids_siswa_dan_sesi(server)
    kode, _, _ = server.minta(
        f"/laporan/{siswa_a}", auth=("pengelola", SANDI_ADMIN)
    )
    assert kode == 200, "admin masih boleh MEMBACA laporan"


def test_admin_detail_anak_ditautkan_ke_laporan(server):
    siswa_a, _ = _ids_siswa_dan_sesi(server)
    kode, isi, _ = server.minta(
        f"/admin?section=siswa&id={siswa_a}",
        auth=("pengelola", SANDI_ADMIN),
    )
    assert kode == 200
    assert f'href="/laporan/{siswa_a}"' in isi
