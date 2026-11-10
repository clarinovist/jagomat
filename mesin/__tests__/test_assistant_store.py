"""Schema/store privat Pendamping: ownership, versi, lifecycle, dan purge."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_schema  # noqa: E402
import assistant_store  # noqa: E402


AKUN_A = "akun_" + "a" * 32
AKUN_B = "akun_" + "b" * 32


@pytest.fixture()
def kon(tmp_path):
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as koneksi:
        yield koneksi


def test_schema_idempoten_fk_integritas_dan_izin_berkas(tmp_path):
    path = tmp_path / "pendamping.db"
    assistant_schema.siapkan(path)
    assistant_schema.siapkan(path)
    with assistant_schema.buka(path) as koneksi:
        assert koneksi.execute("PRAGMA user_version").fetchone()[0] == 4
        assert koneksi.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert koneksi.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []
        assert koneksi.execute(
            "SELECT COUNT(*) FROM migrasi_pendamping WHERE versi IN (1, 2, 3, 4)"
        ).fetchone()[0] == 4
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_schema_lebih_baru_gagal_tertutup(tmp_path):
    path = tmp_path / "pendamping.db"
    with sqlite3.connect(path) as koneksi:
        koneksi.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="lebih baru"):
        assistant_schema.siapkan(path)


def test_owner_wajib_dan_api_tidak_menerima_admin_bypass(kon):
    with pytest.raises(ValueError, match="account_id"):
        assistant_store.buat_chat(kon, "", "aktif", sekarang=100)
    with pytest.raises(TypeError):
        assistant_store.ambil_chat(kon, AKUN_A, "chat_x", peran="admin")


def test_chat_asing_dan_hilang_identik_tanpa_mutasi(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    sebelum = kon.total_changes

    assert assistant_store.ambil_chat(kon, AKUN_B, chat.id) is None
    assert assistant_store.ambil_chat(kon, AKUN_B, "chat_tidak_ada") is None
    assert kon.total_changes == sebelum
    assert assistant_store.daftar_chat(kon, AKUN_B) == ()


def test_mode_chat_immutable_dan_urutan_pesan_unik(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "tanpa_memori", sekarang=100)
    assistant_store.tambah_pesan(
        kon, AKUN_A, chat.id, "pengguna", "Tolong jelaskan pecahan.",
        request_id="req_1", sekarang=101,
    )
    with pytest.raises(sqlite3.IntegrityError):
        assistant_store.tambah_pesan(
            kon, AKUN_A, chat.id, "asisten", "Duplikat request.",
            request_id="req_1", sekarang=102,
        )
    with pytest.raises(ValueError, match="mode"):
        assistant_store.buat_chat(kon, AKUN_A, "mode-asing", sekarang=100)

    baris = kon.execute(
        "SELECT mode_memori FROM chat WHERE id = ?", (chat.id,)
    ).fetchone()
    assert baris["mode_memori"] == "tanpa_memori"
    pesan = assistant_store.daftar_pesan(kon, AKUN_A, chat.id)
    assert [item.urut for item in pesan] == [1]


def test_store_menolak_email_dan_credential_sebelum_tulis(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    contoh = (
        "hubungi aku di orang@example.test",
        "Authorization: Bearer token-rahasia-panjang",
        "api_key=sk-contoh-rahasia-panjang",
    )
    for indeks, teks in enumerate(contoh):
        with pytest.raises(ValueError, match="email atau credential"):
            assistant_store.tambah_pesan(
                kon, AKUN_A, chat.id, "pengguna", teks,
                request_id=f"req_{indeks}", sekarang=101 + indeks,
            )
    assert assistant_store.daftar_pesan(kon, AKUN_A, chat.id) == ()


@pytest.mark.parametrize("teks", (
    "nomorku +62 812-3456-7890",
    "hubungi saya di 081234567890",
))
def test_store_menerima_nomor_telepon_orang_tua(kon, teks):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    assistant_store.tambah_pesan(
        kon, AKUN_A, chat.id, "pengguna", teks,
        request_id="req_telepon", sekarang=101,
    )
    pesan = assistant_store.daftar_pesan(kon, AKUN_A, chat.id)
    assert [item.teks for item in pesan] == [teks]


def test_filter_tidak_menolak_angka_matematika_biasa(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    assistant_store.tambah_pesan(
        kon, AKUN_A, chat.id, "pengguna",
        "Hitung 12 + 34 = 46 dan 1.250 dibagi 25.",
        request_id="req_matematika", sekarang=101,
    )
    assert len(assistant_store.daftar_pesan(kon, AKUN_A, chat.id)) == 1


def test_chat_tanpa_memori_tidak_membaca_memori(kon, monkeypatch):
    chat = assistant_store.buat_chat(kon, AKUN_A, "tanpa_memori", sekarang=100)

    def tidak_boleh(*_args, **_kwargs):
        raise AssertionError("query memori terpanggil")

    monkeypatch.setattr(assistant_store, "_query_memori", tidak_boleh)
    assert assistant_store.memori_untuk_chat(kon, AKUN_A, chat.id) == ()


def test_memori_hanya_preferensi_terkonfirmasi_dan_milik_sendiri(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    memori = assistant_store.tambah_memori(
        kon, AKUN_A, "Jelaskan singkat dengan contoh konkret.",
        sumber_chat_id=chat.id, dikonfirmasi=True, sekarang=101,
    )
    assert assistant_store.memori_untuk_chat(kon, AKUN_A, chat.id) == ()
    assert assistant_store.atur_penggunaan_memori(
        kon, AKUN_A, True, versi_diharapkan=1, sekarang=102
    ) == 2
    assert [item.id for item in assistant_store.memori_untuk_chat(
        kon, AKUN_A, chat.id
    )] == [memori.id]
    assert assistant_store.memori_untuk_chat(kon, AKUN_B, chat.id) == ()
    assert assistant_store.versi_memori(kon, AKUN_A) == 2

    with pytest.raises(ValueError, match="lingkup"):
        assistant_store.tambah_memori(
            kon, AKUN_A, "Anak mudah terdistraksi.", lingkup="profil_anak",
            sumber_chat_id=chat.id, dikonfirmasi=True, sekarang=102,
        )


def test_draft_memori_belum_dikonfirmasi_tidak_mengubah_payload_atau_versi(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    assistant_store.tambah_memori(
        kon, AKUN_A, "Gunakan diagram bila membantu.", sumber_chat_id=chat.id,
        dikonfirmasi=False, sekarang=101,
    )
    assert assistant_store.versi_memori(kon, AKUN_A) == 0
    assert assistant_store.memori_untuk_chat(kon, AKUN_A, chat.id) == ()


def test_nonaktif_dan_hapus_memori_menaikkan_versi(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    memori = assistant_store.tambah_memori(
        kon, AKUN_A, "Gunakan kalimat pendek.", sumber_chat_id=chat.id,
        dikonfirmasi=True, sekarang=101,
    )
    versi_satu = assistant_store.versi_memori(kon, AKUN_A)
    assert not assistant_store.penggunaan_memori_aktif(kon, AKUN_A)
    versi_aktif = assistant_store.atur_penggunaan_memori(
        kon, AKUN_A, True, versi_diharapkan=versi_satu, sekarang=102
    )
    assert assistant_store.penggunaan_memori_aktif(kon, AKUN_A)

    assert assistant_store.atur_penggunaan_memori(
        kon, AKUN_A, False, versi_diharapkan=versi_aktif, sekarang=103
    ) == versi_aktif + 1
    assert assistant_store.memori_untuk_chat(kon, AKUN_A, chat.id) == ()
    assert assistant_store.hapus_memori(
        kon, AKUN_A, memori.id, versi_diharapkan=memori.versi, sekarang=103
    )
    assert assistant_store.versi_memori(kon, AKUN_A) == versi_satu + 3
    assert not assistant_store.hapus_memori(
        kon, AKUN_B, memori.id, versi_diharapkan=memori.versi, sekarang=104
    )


def test_persetujuan_milik_sendiri_dan_pencabutan_menaikkan_versi(kon):
    persetujuan = assistant_store.beri_persetujuan(
        kon, AKUN_A, policy_version="privasi-v1", provider_id="deepseek",
        kategori="chat_umum", sekarang=100,
    )
    assert assistant_store.versi_persetujuan(kon, AKUN_A) == 1
    assert assistant_store.persetujuan_aktif(
        kon, AKUN_A, kategori="chat_umum", provider_id="deepseek"
    )
    assert not assistant_store.cabut_persetujuan(
        kon, AKUN_B, persetujuan.id,
        versi_diharapkan=persetujuan.versi, sekarang=101,
    )
    assert assistant_store.cabut_persetujuan(
        kon, AKUN_A, persetujuan.id,
        versi_diharapkan=persetujuan.versi, sekarang=101,
    )
    assert assistant_store.versi_persetujuan(kon, AKUN_A) == 2
    assert not assistant_store.persetujuan_aktif(
        kon, AKUN_A, kategori="chat_umum", provider_id="deepseek"
    )


def test_retensi_otomatis_tombstone_chat_lama_tanpa_menghapus_memori(kon):
    lama = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    baru = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=200)
    memori = assistant_store.tambah_memori(
        kon, AKUN_A, "Jawab ringkas.", sumber_chat_id=lama.id,
        dikonfirmasi=True, sekarang=100,
    )
    draft = assistant_store.tambah_memori(
        kon, AKUN_A, "Gunakan tabel.", sumber_chat_id=lama.id,
        dikonfirmasi=False, sekarang=100,
    )
    sekarang = 100 + assistant_store.RETENSI_CHAT_DETIK
    assert assistant_store.jadwalkan_retensi_chat(
        kon, sekarang=sekarang
    ) == 1
    assert assistant_store.ambil_chat(kon, AKUN_A, lama.id) is None
    assert assistant_store.ambil_chat(kon, AKUN_A, baru.id) is not None
    assert {item.id for item in assistant_store.daftar_memori(kon, AKUN_A)} == {
        memori.id, draft.id,
    }
    assert assistant_store.purge(kon, sekarang=sekarang) == 1
    tersisa = assistant_store.daftar_memori(kon, AKUN_A)
    assert [item.id for item in tersisa] == [memori.id]
    assert tersisa[0].sumber_chat_id is None
    assert assistant_store.ambil_chat(kon, AKUN_A, lama.id) is None
    assert kon.execute(
        "SELECT COUNT(*) FROM memori WHERE id = ?", (draft.id,)
    ).fetchone()[0] == 0


def test_soft_delete_menaikkan_versi_dan_purge_sesuai_waktu(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    assistant_store.tambah_pesan(
        kon, AKUN_A, chat.id, "pengguna", "Pesan aman.",
        request_id="req_hapus", sekarang=101,
    )
    versi = assistant_store.ambil_chat(kon, AKUN_A, chat.id).versi

    assert assistant_store.hapus_chat(
        kon, AKUN_A, chat.id, versi_diharapkan=versi,
        sekarang=200, retensi_detik=30,
    )
    terhapus = kon.execute("SELECT * FROM chat WHERE id = ?", (chat.id,)).fetchone()
    assert terhapus["versi"] == versi
    assert terhapus["purge_setelah"] == 230
    assert assistant_store.purge(kon, sekarang=229) == 0
    assert assistant_store.purge(kon, sekarang=230) == 1
    assert kon.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM pesan").fetchone()[0] == 0


def test_operasi_version_check_dan_request_id_idempoten(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    persetujuan = assistant_store.beri_persetujuan(
        kon, AKUN_A, policy_version="privasi-v1", provider_id="deepseek",
        kategori="chat_umum", sekarang=100,
    )
    consent_version = assistant_store.versi_persetujuan(kon, AKUN_A)
    memory_version = assistant_store.versi_memori(kon, AKUN_A)
    operasi = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_operasi", consent_version=consent_version,
        memory_version=memory_version, context_version=4, sekarang=101,
    )
    kedua = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_operasi", consent_version=consent_version,
        memory_version=memory_version, context_version=4, sekarang=102,
    )
    assert kedua == operasi
    with pytest.raises(ValueError, match="operasi berbeda"):
        assistant_store.mulai_operasi(
            kon, AKUN_A, chat.id, "req_operasi", consent_version=99,
            memory_version=memory_version, context_version=4, sekarang=102,
        )

    assert assistant_store.selesaikan_operasi(
        kon, AKUN_A, "req_operasi", chat_version=operasi.chat_version,
        consent_version=consent_version, memory_version=memory_version,
        context_version=4, sekarang=103,
    )

    lain = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_usang", consent_version=consent_version,
        memory_version=memory_version, context_version=4, sekarang=104,
    )
    assert assistant_store.cabut_persetujuan(
        kon, AKUN_A, persetujuan.id,
        versi_diharapkan=persetujuan.versi, sekarang=105,
    )
    assert not assistant_store.selesaikan_operasi(
        kon, AKUN_A, "req_usang", chat_version=lain.chat_version,
        consent_version=consent_version, memory_version=memory_version,
        context_version=4, sekarang=106,
    )


def test_operasi_chat_berubah_saat_network_tidak_bisa_commit(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    consent_version = assistant_store.versi_persetujuan(kon, AKUN_A)
    memory_version = assistant_store.versi_memori(kon, AKUN_A)
    operasi = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_chat_usang", consent_version=consent_version,
        memory_version=memory_version, context_version=0, sekarang=101,
    )
    assistant_store.tambah_pesan(
        kon, AKUN_A, chat.id, "pengguna", "Chat berubah.",
        request_id="req_perubahan_chat", sekarang=102,
    )
    assert not assistant_store.selesaikan_operasi(
        kon, AKUN_A, operasi.request_id, chat_version=operasi.chat_version,
        consent_version=consent_version, memory_version=memory_version,
        context_version=0, sekarang=103,
    )


def test_operasi_memori_berubah_saat_network_tidak_bisa_commit(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    consent_version = assistant_store.versi_persetujuan(kon, AKUN_A)
    memory_version = assistant_store.versi_memori(kon, AKUN_A)
    operasi = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_memori", consent_version=consent_version,
        memory_version=memory_version, context_version=0, sekarang=101,
    )
    assistant_store.atur_penggunaan_memori(
        kon, AKUN_A, False, versi_diharapkan=memory_version, sekarang=102
    )
    assert not assistant_store.selesaikan_operasi(
        kon, AKUN_A, operasi.request_id, chat_version=operasi.chat_version,
        consent_version=consent_version, memory_version=memory_version,
        context_version=0, sekarang=103,
    )


def test_operasi_gagal_dipurge_setelah_tujuh_hari(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    operasi = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_gagal", consent_version=0,
        memory_version=0, context_version=0, sekarang=101,
    )
    assert assistant_store.gagalkan_operasi(
        kon, AKUN_A, operasi.request_id, sekarang=102
    )
    hampir = 101 + assistant_store.RETENSI_OPERASI_GAGAL_DETIK - 1
    assert assistant_store.purge_operasi(kon, sekarang=hampir) == 0
    assert assistant_store.purge_operasi(kon, sekarang=hampir + 1) == 1


def test_cabut_izin_konteks_pengganti_tidak_menghidupkan_izin_lama(kon):
    pertama = assistant_store.beri_persetujuan_konteks(
        kon, AKUN_A, jenis="anak", resource_id="1", resource_version="v1",
        kategori="ringkasan_netral", sekarang=100,
    )
    kedua = assistant_store.beri_persetujuan_konteks(
        kon, AKUN_A, jenis="anak", resource_id="1", resource_version="v1",
        kategori="ringkasan_netral", sekarang=101,
    )
    assert assistant_store.cabut_persetujuan_konteks(
        kon, AKUN_A, kedua.id, versi_diharapkan=kedua.versi, sekarang=102,
    )
    assert not assistant_store.persetujuan_konteks_aktif(
        kon, AKUN_A, jenis="anak", resource_id="1", resource_version="v1",
        kategori="ringkasan_netral", versi=pertama.versi,
    )
    assert not assistant_store.persetujuan_konteks_aktif(
        kon, AKUN_A, jenis="anak", resource_id="1", resource_version="v1",
    )


def test_operasi_asing_tidak_dapat_diselesaikan(kon):
    chat = assistant_store.buat_chat(kon, AKUN_A, "aktif", sekarang=100)
    operasi = assistant_store.mulai_operasi(
        kon, AKUN_A, chat.id, "req_rahasia", consent_version=1,
        memory_version=1, context_version=1, sekarang=101,
    )
    sebelum = kon.total_changes
    assert not assistant_store.selesaikan_operasi(
        kon, AKUN_B, operasi.request_id, chat_version=operasi.chat_version,
        consent_version=1, memory_version=1, context_version=1, sekarang=102,
    )
    assert kon.total_changes == sebelum
