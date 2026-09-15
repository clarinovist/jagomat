"""Proyeksi UI privat Pendamping, terpisah dari muatan dan aksi belajar."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assistant_actions
import assistant_context
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
import database
import topics

import assistant_view as view


AKUN = "akun_" + "a" * 32
ASING = "akun_" + "b" * 32
PEMILIK = "ortu-sintetis"
NAMA = 'Nama UI Sintetis <b>&" panjang'


@pytest.fixture(autouse=True)
def isolasi(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BAWAAN", tmp_path / "tidak-disiapkan.db")
    monkeypatch.setattr(
        assistant_service, "panggil_provider_default",
        lambda *_: pytest.fail("Provider nyata tidak boleh dipanggil"),
    )


@pytest.fixture()
def privat(tmp_path):
    path = tmp_path / "pendamping-sintetis.db"
    assistant_schema.siapkan(path)
    kon = assistant_schema.buka(path)
    yield kon
    kon.close()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "belajar-sintetis.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, NAMA, "P3", pemilik=PEMILIK)
        sesi = database.buat_sesi(kon, anak, seed=42)
        soal = kon.execute(
            "SELECT id FROM sesi_soal WHERE sesi_id = ? AND nomor = 1", (sesi,)
        ).fetchone()[0]
    return path, anak, sesi, soal


def _riwayat_banyak(kon):
    chats = tuple(assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=100)
                  for _ in range(45))
    assistant_store.buat_chat(kon, ASING, "aktif", sekarang=1000)
    dihapus = assistant_store.buat_chat(kon, AKUN, "aktif", sekarang=1001)
    assistant_store.hapus_chat(
        kon, AKUN, dihapus.id, versi_diharapkan=1, sekarang=1002, retensi_detik=30
    )
    kon.commit()
    return tuple(sorted(chats, key=lambda item: item.id, reverse=True))


def test_riwayat_paginasi_terbatas_dan_tidak_bercampur(privat):
    semua = _riwayat_banyak(privat)
    sebelum = privat.total_changes
    pertama, lagi = view.riwayat(privat, AKUN)
    assert len(pertama) == 20, "baseline mengambil semua chat tanpa LIMIT"
    assert pertama == semua[:20]
    assert lagi is True
    kedua, lagi = view.riwayat(privat, AKUN, halaman=2)
    assert kedua == semua[20:40]
    assert lagi is True
    ketiga, lagi = view.riwayat(privat, AKUN, halaman=3)
    assert ketiga == semua[40:]
    assert lagi is False
    assert view.riwayat(privat, AKUN, halaman=4) == ((), False)
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("halaman,batas", [
    (0, 20), (-1, 20), (True, 20), ("1", 20), (1.0, 20), (502, 20),
    (1, 0), (1, 21), (1, True), (1, "20"), (10002, 1), (10 ** 100, 20),
])
def test_riwayat_invalid_tanpa_query(privat, halaman, batas):
    jejak = []
    privat.set_trace_callback(jejak.append)
    with pytest.raises(ValueError):
        view.riwayat(privat, AKUN, halaman=halaman, batas=batas)
    assert jejak == []


def test_riwayat_exact_resource_tidak_mencampur_chat_lain(privat):
    anak_a = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=100)
    anak_b = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=101)
    umum = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=102)
    privat.execute(
        "UPDATE chat SET context_kind = 'anak', context_id = '7' WHERE id = ?",
        (anak_a.id,),
    )
    privat.execute(
        "UPDATE chat SET context_kind = 'anak', context_id = '8' WHERE id = ?",
        (anak_b.id,),
    )
    privat.commit()
    hasil, lagi = view.riwayat(
        privat, AKUN, jenis_resource="anak", resource_id="7"
    )
    assert hasil == (replace(anak_a, context_kind="anak", context_id="7"),)
    assert anak_b.id not in {item.id for item in hasil}
    assert umum.id not in {item.id for item in hasil}
    assert lagi is False


@pytest.mark.parametrize("jenis,resource", [
    (None, "7"), ("anak", None), ("asing", "7"), ("anak", ""),
])
def test_riwayat_scope_invalid_tanpa_query(privat, jenis, resource):
    jejak = []
    privat.set_trace_callback(jejak.append)
    with pytest.raises(ValueError):
        view.riwayat(privat, AKUN, jenis_resource=jenis, resource_id=resource)
    assert jejak == []


def test_riwayat_limit_sql_metadata_dan_batas_offset(privat):
    _riwayat_banyak(privat)
    jejak = []
    privat.set_trace_callback(jejak.append)
    view.riwayat(privat, AKUN)
    assert len(jejak) == 1
    assert "LIMIT 21 OFFSET 0" in jejak[0]
    assert "pesan" not in jejak[0].lower()
    assert view.riwayat(privat, AKUN, halaman=501) == ((), False)
    assert "LIMIT 21 OFFSET 10000" in jejak[-1]
    assert view.riwayat(privat, AKUN, halaman=10001, batas=1) == ((), False)


def test_riwayat_batas_offset_tidak_menawarkan_halaman_invalid(privat):
    privat.executemany(
        "INSERT INTO chat(id, account_id, mode_memori, dibuat, diperbarui) "
        "VALUES (?, ?, 'aktif', 100, 100)",
        ((f"chat_{nomor:032x}", AKUN) for nomor in range(10021)),
    )
    hasil, ada_lagi = view.riwayat(privat, AKUN, halaman=501)
    assert len(hasil) == 20
    assert ada_lagi is False


def test_label_chat_stabil_wib_dan_id_penuh(privat):
    chat = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=0)
    assert view.label_chat(chat) == f"Chat 01 Jan 1970 · 07:00 WIB · {chat.id}"
    assert view.label_chat(chat) == view.label_chat(replace(chat, diperbarui=999))
    assert view.label_chat(chat) != view.label_chat(replace(chat, id=chat.id + "1"))
    assert "02 Jan 1970" in view.label_chat(replace(chat, dibuat=17 * 3600))


def _resource(jenis, db):
    _, anak, sesi, _ = db
    return str(anak) if jenis == "anak" else str(sesi) if jenis == "sesi" else f"{sesi}:1"


@pytest.mark.parametrize("jenis", ["anak", "sesi", "soal"])
def test_sumber_owner_minimal_readonly_dan_level_snapshot(db, jenis):
    path, anak, sesi, soal = db
    with database.buka(path) as kon:
        kon.execute("UPDATE siswa SET tingkat = 'P4' WHERE id = ?", (anak,))
        kon.commit()
        jejak = []
        kolom = []

        def authorizer(aksi, tabel, kol, *_):
            if aksi == sqlite3.SQLITE_READ:
                kolom.append((tabel, kol))
            if aksi in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        kon.set_authorizer(authorizer)
        kon.set_trace_callback(jejak.append)
        sebelum = kon.total_changes
        sumber = view.sumber_tampilan(kon, jenis, _resource(jenis, db), pemilik=PEMILIK)
        assert sumber == {
            "jenis": jenis, "nama": NAMA,
            "level": "P4" if jenis == "anak" else "P3",
            "label": {"anak": "Ringkasan anak", "sesi": f"Sesi #{sesi}",
                      "soal": f"Soal 1 · Sesi #{sesi}"}[jenis],
            "url": {"anak": f"/anak/{anak}", "sesi": f"/sesi/{sesi}",
                    "soal": f"/sesi/{sesi}"}[jenis],
            "kategori": "soal_resmi" if jenis == "soal" else "ringkasan_netral",
        }
        assert len(jejak) == 1
        assert set(kolom) <= {
            ("siswa", "nama"), ("siswa", "tingkat"), ("siswa", "id"),
            ("siswa", "pemilik"), ("sesi", "id"), ("sesi", "siswa_id"),
            ("sesi", "level"), ("sesi", "selesai"), ("sesi_soal", "sesi_id"),
            ("sesi_soal", "nomor"), ("sesi_soal", "id"),
        }
        assert kon.total_changes == sebelum


@pytest.mark.parametrize("jenis", ["anak", "sesi", "soal"])
def test_sumber_asing_hilang_identik_tanpa_write(db, jenis):
    with database.buka(db[0]) as kon:
        sebelum = kon.total_changes
        resource = _resource(jenis, db)
        hilang = "999999:1" if jenis == "soal" else "999999"
        assert view.sumber_tampilan(kon, jenis, resource, pemilik="asing") is None
        assert view.sumber_tampilan(kon, jenis, hilang, pemilik=PEMILIK) is None
        assert kon.total_changes == sebelum


@pytest.mark.parametrize("terkirim", [False, True])
def test_tautan_soal_memakai_anchor_render_existing(db, terkirim):
    import teacher_pages
    with database.buka(db[0]) as kon:
        if terkirim:
            kon.execute("UPDATE sesi SET selesai = '2026-09-12 07:00:00' WHERE id = ?", (db[2],))
        sumber = view.sumber_tampilan(kon, "soal", f"{db[2]}:1", pemilik=PEMILIK)
        halaman = teacher_pages.halaman_sesi_stitch(kon, db[2], pengguna=PEMILIK).decode()
    if terkirim:
        path, anchor = sumber["url"].split("#")
        assert path == f"/sesi/{db[2]}"
        assert f'id="{anchor}"' in halaman
    else:
        assert sumber["url"] == f"/sesi/{db[2]}"


def test_sumber_soal_harus_ada_nomornya(db):
    with database.buka(db[0]) as kon:
        assert view.sumber_tampilan(kon, "soal", f"{db[2]}:99", pemilik=PEMILIK) is None


@pytest.mark.parametrize("jenis,resource", [
    ("anak", None), ("anak", 1), ("anak", "01"), ("anak", "0"), ("sesi", "-1"),
    ("sesi", "1/"), ("anak", "١"), ("anak", "1\n"), ("anak", " 1"),
    ("anak", str(2 ** 63)), ("anak", "9" * 100), ("soal", "1"),
    ("soal", "1:01"), ("soal", "1:0"), ("soal", "1:2:3"),
    ("soal", "1;DROP TABLE siswa:1"), ("lain", "1"),
])
def test_sumber_invalid_tanpa_sql(db, jenis, resource):
    with database.buka(db[0]) as kon:
        jejak = []
        kon.set_trace_callback(jejak.append)
        assert view.sumber_tampilan(kon, jenis, resource, pemilik=PEMILIK) is None
        assert jejak == []


@pytest.mark.parametrize("pemilik", ["", None, False])
def test_sumber_pemilik_wajib(db, pemilik):
    with database.buka(db[0]) as kon:
        jejak = []
        kon.set_trace_callback(jejak.append)
        assert view.sumber_tampilan(kon, "anak", str(db[1]), pemilik=pemilik) is None
        assert jejak == []


def _aktifkan_memori(kon):
    assistant_store.atur_penggunaan_memori(
        kon, AKUN, True, versi_diharapkan=assistant_store.versi_memori(kon, AKUN),
        sekarang=100,
    )


def _catatan(kon, *, account_id=AKUN, dikonfirmasi=True):
    return assistant_store.tambah_memori(
        kon, account_id, "Jawab ringkas dengan contoh konkret.", sumber_chat_id=None,
        dikonfirmasi=dikonfirmasi, sekarang=100,
    )


def test_status_memori_count_confirmed_live_owner_saja(privat):
    assert view.status_memori(privat, AKUN) == "Memori nonaktif"
    _aktifkan_memori(privat)
    assert view.status_memori(privat, AKUN) == "Memori aktif · belum ada catatan"
    _catatan(privat, dikonfirmasi=False)
    _catatan(privat, account_id=ASING)
    dihapus = _catatan(privat)
    assistant_store.hapus_memori(
        privat, AKUN, dihapus.id, versi_diharapkan=dihapus.versi, sekarang=102
    )
    assert view.status_memori(privat, AKUN) == "Memori aktif · belum ada catatan"
    _catatan(privat)
    sebelum = privat.total_changes
    jejak = []
    privat.set_trace_callback(jejak.append)
    assert view.status_memori(privat, AKUN) == "Memori aktif · 1 catatan"
    assert len(jejak) == 2
    assert "SELECT COUNT(*)" in jejak[1]
    assert privat.total_changes == sebelum


def test_status_tanpa_memori_tidak_query_preferensi_atau_count(privat):
    _aktifkan_memori(privat)
    _catatan(privat)
    chat = assistant_store.buat_chat(privat, AKUN, "tanpa_memori", sekarang=100)
    jejak = []
    privat.set_trace_callback(jejak.append)
    assert view.status_memori(privat, AKUN, chat) == "Chat tanpa memori"
    assert jejak == []


def test_status_nonaktif_tidak_count(privat):
    _catatan(privat)
    jejak = []
    privat.set_trace_callback(jejak.append)
    assert view.status_memori(privat, AKUN) == "Memori nonaktif"
    assert len(jejak) == 1 and "preferensi_memori" in jejak[0]


@pytest.mark.parametrize("rusak", ["asing", "dihapus", "mode"])
def test_status_chat_invalid_tidak_query(privat, rusak):
    chat = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=100)
    chat = replace(chat, **{
        "asing": {"account_id": ASING}, "dihapus": {"dihapus": 101},
        "mode": {"mode_memori": "lain"},
    }[rusak])
    jejak = []
    privat.set_trace_callback(jejak.append)
    with pytest.raises(ValueError):
        view.status_memori(privat, AKUN, chat)
    assert jejak == []


def _payload(template_ids=None, jumlah=10):
    return {"topik_id": "pola-bilangan", "template_ids": template_ids or ["deret_aritmetika"],
            "level": "P3", "jumlah_soal": jumlah}


def test_ringkasan_memakai_nama_tipe_bukan_judul_kartu_umum():
    assert view.ringkasan_usulan(json.dumps(_payload())) == {
        "topik": "Pola Bilangan", "level": "P3", "jumlah": 10,
        "materi": (("Deret aritmetika", 10, "deret_aritmetika"),),
    }


@pytest.mark.parametrize("jumlah", [10, 15, 20, 25, 30])
def test_ringkasan_distribusi_sama_eksekusi_tanpa_generator(jumlah, monkeypatch):
    import generator
    from template_labels import nama_tipe_soal
    monkeypatch.setattr(generator, "buat_lembar", lambda *_a, **_k: pytest.fail("generator"))
    monkeypatch.setattr(database, "buat_sesi", lambda *_a, **_k: pytest.fail("buat sesi"))
    for topik_id in topics.daftar_topik():
        if topik_id == "campuran":
            continue
        topik = topics.ambil(topik_id)
        for level, komposisi in topik.komposisi.items():
            dasar = list(dict.fromkeys(komposisi))[:8]
            if not dasar:
                continue
            data = {"topik_id": topik_id, "template_ids": dasar,
                    "level": level, "jumlah_soal": jumlah}
            ringkasan = view.ringkasan_usulan(json.dumps(data))
            urutan = assistant_actions._urutan(assistant_actions.validasi_usulan(data))
            assert ringkasan["topik"] == topik.nama
            assert ringkasan["materi"] == tuple(
                (nama_tipe_soal(tid), urutan.count(tid), tid) for tid in dasar
            )
            assert sum(item[1] for item in ringkasan["materi"]) == jumlah


@pytest.mark.parametrize("mentah", [
    None, b"{}", "{", "null", "[]", "{}", "[" * 1100,
    json.dumps({**_payload(), "nama": "Tidak boleh"}),
    json.dumps({**_payload(), "jumlah_soal": True}),
    json.dumps({**_payload(), "jumlah_soal": 11}),
    json.dumps({**_payload(), "topik_id": "asing"}),
    json.dumps({**_payload(), "level": "P0"}),
    json.dumps({**_payload(), "template_ids": ["deret_aritmetika", "deret_aritmetika"]}),
    json.dumps({**_payload(), "template_ids": ["asing"]}),
    json.dumps(_payload())[:-1] + ',"jumlah_soal":20}',
])
def test_ringkasan_invalid_ditolak_tanpa_echo(mentah):
    with pytest.raises(ValueError, match="^Isi usulan tidak sah[.]$"):
        view.ringkasan_usulan(mentah)


def _provider(kon, **kwargs):
    return assistant_store.beri_persetujuan(
        kon, AKUN, policy_version=kwargs.get("policy_version", assistant_policy.VERSI_KEBIJAKAN),
        provider_id=kwargs.get("provider_id", assistant_policy.PROVIDER_ID),
        kategori=kwargs.get("kategori", "chat_umum"), sekarang=100,
    )


def _chat_konteks(kon, db, jenis="anak"):
    with database.buka(db[0]) as belajar:
        konteks = assistant_context.ambil(belajar, jenis, _resource(jenis, db), pemilik=PEMILIK)
    izin = assistant_store.beri_persetujuan_konteks(
        kon, AKUN, jenis=jenis, resource_id=konteks.resource_id,
        resource_version=konteks.versi, kategori=konteks.kategori, sekarang=100,
    )
    chat = assistant_store.buat_chat(
        kon, AKUN, "aktif", sekarang=100, context_kind=jenis,
        context_id=konteks.resource_id, context_version=izin.versi,
        context_resource_version=konteks.versi, context_category=konteks.kategori,
    )
    kon.commit()
    return chat, konteks, izin


def test_hak_baca_umum_tidak_membuka_db_belajar(privat, monkeypatch):
    _provider(privat)
    chat = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=100)
    monkeypatch.setattr(database, "buka", lambda *_: pytest.fail("DB belajar"))
    sebelum = privat.total_changes
    assert view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("rusak", ["tidak_ada", "dicabut", "provider", "policy", "grant_baru_dicabut"])
def test_hak_baca_provider_terbaru_wajib(privat, monkeypatch, rusak):
    chat = assistant_store.buat_chat(privat, AKUN, "aktif", sekarang=100)
    if rusak != "tidak_ada":
        izin = _provider(privat)
        if rusak in ("provider", "policy"):
            _provider(privat, **{"provider_id" if rusak == "provider" else "policy_version": "lama"})
        else:
            if rusak == "grant_baru_dicabut":
                izin = _provider(privat)
            assistant_store.cabut_persetujuan(
                privat, AKUN, izin.id, versi_diharapkan=izin.versi, sekarang=101
            )
    monkeypatch.setattr(database, "buka", lambda *_: pytest.fail("DB belajar"))
    sebelum = privat.total_changes
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("rusak", ["asing", "hilang", "dihapus", "pemilik", "objek_palsu"])
def test_hak_baca_chat_owner_dan_refetch(privat, monkeypatch, rusak):
    _provider(privat)
    chat = assistant_store.buat_chat(privat, ASING if rusak in ("asing", "objek_palsu") else AKUN,
                                     "aktif", sekarang=100)
    if rusak == "hilang":
        chat = replace(chat, id="chat_hilang")
    elif rusak == "objek_palsu":
        chat = replace(chat, account_id=AKUN)
    elif rusak == "dihapus":
        assistant_store.hapus_chat(
            privat, AKUN, chat.id, versi_diharapkan=1, sekarang=101, retensi_detik=30
        )
    monkeypatch.setattr(database, "buka", lambda *_: pytest.fail("DB belajar"))
    sebelum = privat.total_changes
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik="" if rusak == "pemilik" else PEMILIK)
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("jenis", ["anak", "sesi", "soal"])
def test_hak_baca_context_milik_readonly_tanpa_fresh_check(privat, db, jenis, monkeypatch):
    _provider(privat)
    chat, _, _ = _chat_konteks(privat, db, jenis)
    assistant_store.beri_persetujuan_konteks(
        privat, AKUN, jenis="anak", resource_id="999999", resource_version="lain",
        kategori="ringkasan_netral", sekarang=101,
    )
    monkeypatch.setattr(assistant_context, "versi_resource", lambda *_a, **_k: pytest.fail("fresh check"))
    sebelum = privat.total_changes
    assert view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik="asing")
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("perubahan", ["cabut", "grant_baru", "kategori", "versi_resource", "versi_grant"])
def test_hak_baca_context_grant_exact_terbaru(privat, db, perubahan, monkeypatch):
    _provider(privat)
    chat, konteks, izin = _chat_konteks(privat, db)
    if perubahan == "cabut":
        assistant_store.cabut_persetujuan_konteks(
            privat, AKUN, izin.id, versi_diharapkan=izin.versi, sekarang=101
        )
    elif perubahan == "grant_baru":
        assistant_store.beri_persetujuan_konteks(
            privat, AKUN, jenis=konteks.jenis, resource_id=konteks.resource_id,
            resource_version=konteks.versi, kategori=konteks.kategori, sekarang=101,
        )
    else:
        kolom, nilai = {"kategori": ("kategori", "soal_resmi"),
                       "versi_resource": ("resource_version", "usang"),
                       "versi_grant": ("versi", 99)}[perubahan]
        privat.execute(f"UPDATE persetujuan_konteks SET {kolom} = ? WHERE id = ?", (nilai, izin.id))
    monkeypatch.setattr(database, "buka", lambda *_: pytest.fail("DB belajar"))
    sebelum = privat.total_changes
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("jenis", ["anak", "sesi", "soal"])
def test_hak_baca_sumber_hilang_tidak_diizinkan(privat, db, jenis):
    _provider(privat)
    chat, _, _ = _chat_konteks(privat, db, jenis)
    # Resource kanonik tetapi tidak ada, consent sah tidak menggantikan ownership.
    hilang = "999999:1" if jenis == "soal" else "999999"
    privat.execute("UPDATE chat SET context_id = ? WHERE id = ?", (hilang, chat.id))
    privat.execute("UPDATE persetujuan_konteks SET resource_id = ?", (hilang,))
    sebelum = privat.total_changes
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert privat.total_changes == sebelum


def test_stale_boleh_baca_tetapi_service_tetap_tolak_kirim(privat, db):
    _provider(privat)
    chat, konteks, _ = _chat_konteks(privat, db)
    with database.buka(db[0]) as kon:
        kon.execute("UPDATE siswa SET tingkat = 'P4' WHERE id = ?", (db[1],))
    assert view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)

    def versi_sekarang():
        with database.buka(db[0]) as kon:
            return assistant_context.versi_resource(kon, "anak", str(db[1]), pemilik=PEMILIK)

    sebelum = privat.total_changes
    with pytest.raises(assistant_service.GalatPendamping, match="berubah"):
        assistant_service.kirim_pesan(
            privat, AKUN, chat.id, "Bahas lagi.", request_id="req_sintetis_stale",
            konteks=konteks, validasi_konteks=versi_sekarang,
            panggil_provider=lambda *_: pytest.fail("provider menerima stale"), sekarang=101,
        )
    assert privat.total_changes == sebelum


@pytest.mark.parametrize("jenis", ["anak", "sesi", "soal"])
def test_proyeksi_tidak_bocor_ke_payload_provider(privat, db, jenis):
    _provider(privat)
    chat, konteks, _ = _chat_konteks(privat, db, jenis)
    muatan_awal = json.dumps(konteks.muatan, sort_keys=True)
    provider_awal = assistant_service._pesan_provider(privat, AKUN, chat.id, "Bahas sumber.", konteks=konteks)
    with database.buka(db[0]) as kon:
        sumber = view.sumber_tampilan(kon, jenis, konteks.resource_id, pemilik=PEMILIK)
        assert sumber["nama"] == NAMA
        sumber["nama"] = "Nama tampilan berubah"
    assert view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    view.label_chat(chat)
    view.riwayat(privat, AKUN)
    view.status_memori(privat, AKUN, chat)
    view.ringkasan_usulan(json.dumps(_payload()))
    assert json.dumps(konteks.muatan, sort_keys=True) == muatan_awal
    provider_akhir = assistant_service._pesan_provider(privat, AKUN, chat.id, "Bahas sumber.", konteks=konteks)
    assert provider_awal == provider_akhir
    assert NAMA not in json.dumps(provider_akhir, ensure_ascii=False)
    assert "Nama tampilan berubah" not in json.dumps(provider_akhir, ensure_ascii=False)
    isi = json.loads(provider_akhir[1]["content"])
    assert set(isi) == {"katalog", "memori", "percakapan", "konteks"}
    assert not {"nama", "url", "label", "sumber"}.intersection(isi["konteks"])


@pytest.mark.parametrize("kolom,nilai", [
    ("context_version", None), ("context_version", 0),
    ("context_resource_version", None), ("context_resource_version", ""),
    ("context_kind", "lain"), ("context_kind", None), ("context_id", ""),
])
def test_hak_baca_context_tidak_lengkap_gagal_tertutup(privat, db, kolom, nilai):
    _provider(privat)
    chat, _, _ = _chat_konteks(privat, db)
    privat.execute(f"UPDATE chat SET {kolom} = ? WHERE id = ?", (nilai, chat.id))
    sebelum = privat.total_changes
    assert not view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert privat.total_changes == sebelum


def test_semua_proyeksi_privat_hanya_baca(privat, db):
    _provider(privat)
    _aktifkan_memori(privat)
    _catatan(privat)
    chat, _, _ = _chat_konteks(privat, db)
    privat.commit()
    snapshot = "\n".join(privat.iterdump())
    jejak = []

    def authorizer(aksi, *_):
        if aksi in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    privat.set_authorizer(authorizer)
    privat.set_trace_callback(jejak.append)
    view.status_memori(privat, AKUN, chat)
    view.riwayat(privat, AKUN)
    assert view.hak_baca_chat(privat, AKUN, chat, pemilik=PEMILIK)
    assert not privat.in_transaction
    assert all(sql.lstrip().startswith("SELECT") for sql in jejak)
    assert not any("FROM pesan" in sql or "FROM operasi" in sql for sql in jejak)
    privat.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert "\n".join(privat.iterdump()) == snapshot


@pytest.mark.parametrize("account_id", ["ortu", "", None, "akun_" + "A" * 32])
def test_account_id_kanonik_wajib(privat, account_id):
    jejak = []
    privat.set_trace_callback(jejak.append)
    for fungsi in (lambda: view.riwayat(privat, account_id),
                   lambda: view.status_memori(privat, account_id),
                   lambda: view.hak_baca_chat(privat, account_id, None, pemilik=PEMILIK)):
        with pytest.raises(ValueError):
            fungsi()
    assert jejak == []
