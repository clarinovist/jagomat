"""Latihan serupa manual dari hasil final T, dengan palang HTTP dan bukti."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import learning_cycle  # noqa: E402
import learning_cycle_service  # noqa: E402
import share_links  # noqa: E402
import similar_practice  # noqa: E402
import sessions  # noqa: E402
import teacher_pages  # noqa: E402
import topics  # noqa: E402
import web  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SANDI_ADMIN = "sandi-pengelola-sintetis"
SANDI_ASING = "sandi-keluarga-asing"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "uji.db"
    database.siapkan(path)
    monkeypatch.setattr(database, "BAWAAN", path)
    return path


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("pengelola", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    auth.tambah_akun("guru-lain", SANDI_ASING, "guru", path=auth.BERKAS_SANDI)
    yield s
    s.berhenti()


def _hasil_t(
    kon,
    *,
    pemilik="guru",
    level="P3",
    kode="T",
    selesai=True,
    dibatalkan=False,
    template_ids=("soal_umur",),
):
    siswa_id = database.tambah_siswa(
        kon, f"Anak-{kon.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]}",
        tingkat=level, pemilik=pemilik,
    )
    paket = topics.paket_untuk_template(template_ids)
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=40_000 + siswa_id,
        urutan=tuple(template_ids),
        topik=paket,
        level=level,
    )
    for butir in database.isi_sesi(kon, sesi_id):
        jawaban_id = database.simpan_jawaban(
            kon, butir["sesi_soal_id"], jawaban="belum tahu", belum_pernah=True
        )
        database.simpan_diagnosis(
            kon, jawaban_id, benar=False, kode_usulan=kode,
            kode_final=kode, alasan="Guru memastikan pengenalan" if kode == "T" else "Data sintetis",
            manual=kode == "T",
        )
    if selesai:
        database.tandai_selesai(kon, sesi_id)
        kon.execute(
            "UPDATE sesi SET direview = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )
    if dibatalkan:
        kon.execute(
            "UPDATE sesi SET dibatalkan = datetime('now', '+7 hours') WHERE id = ?",
            (sesi_id,),
        )
    return siswa_id, sesi_id, database.isi_sesi(kon, sesi_id)


def _jumlah_domain(kon):
    tabel = (
        "sesi", "sesi_soal", "jawaban", "diagnosis", "putaran_fokus",
        "anggota_fokus", "bukti_fokus", "konfirmasi_hasil",
        "snapshot_outcome", "kejadian_belajar",
    )
    return {nama: kon.execute(f"SELECT COUNT(*) FROM {nama}").fetchone()[0]
            for nama in tabel}


def test_kandidat_ui_unik_per_template_dan_di_luar_form_koreksi(db):
    with database.buka(db) as kon:
        _siswa, sesi, _ = _hasil_t(
            kon, template_ids=("soal_umur", "soal_umur")
        )
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()

    assert halaman.count("Latih tipe soal ini") == 1
    assert "Lihat pembahasan soal nomor 1, 2" in halaman
    assert "Kenalkan konsepnya" in halaman
    assert "Minta anak menjelaskan caranya" in halaman
    assert "Latihan manual:" in halaman
    assert "tidak mengubah progres rencana terpandu" in halaman
    posisi_aksi = halaman.index(f'action="/sesi/{sesi}/latihan-serupa"')
    posisi_form_koreksi = halaman.index(f'method="post" action="/sesi/{sesi}">')
    assert halaman.index("</form>", posisi_form_koreksi) < posisi_aksi
    blok = halaman.split('class="remedial-st latihan-serupa-st"', 1)[1].split(
        "</section>", 1
    )[0]
    assert blok.count("<form") == blok.count("</form>") == 1


@pytest.mark.parametrize("kasus", ["non_t", "belum_selesai", "dibatalkan", "beda_level"])
def test_cta_absen_dan_service_menolak_sumber_tidak_sah(db, kasus):
    with database.buka(db) as kon:
        _siswa, sesi, butir = _hasil_t(
            kon,
            kode="K" if kasus == "non_t" else "T",
            selesai=kasus != "belum_selesai",
            dibatalkan=kasus == "dibatalkan",
        )
        if kasus == "beda_level":
            kon.execute(
                "UPDATE siswa SET tingkat = 'P4' WHERE id = (SELECT siswa_id FROM sesi WHERE id = ?)",
                (sesi,),
            )
        sebelum = _jumlah_domain(kon)
        assert similar_practice.kandidat_sesi(kon, sesi) == []
        with pytest.raises(similar_practice.LatihanSerupaTidakTersedia):
            similar_practice.buat_dari_hasil_t(
                kon, sesi, int(butir[0]["sesi_soal_id"]), seed=71
            )
        assert _jumlah_domain(kon) == sebelum
        assert "Latih tipe soal ini" not in teacher_pages.halaman_sesi_stitch(
            kon, sesi
        ).decode()


def test_lima_soal_satu_template_baru_unik_deterministik_dan_manual(db):
    with database.buka(db) as kon:
        siswa, sumber, butir = _hasil_t(kon)
        sumber_sig = {
            b[0] for b in kon.execute(
                """SELECT so.tanda_tangan FROM sesi_soal ss
                   JOIN soal so ON so.id = ss.soal_id WHERE ss.sesi_id = ?""",
                (sumber,),
            )
        }
        baru_a = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(butir[0]["sesi_soal_id"]), seed=8123
        )
        baru_b = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(butir[0]["sesi_soal_id"]), seed=8123
        )
        def data(sesi_id):
            return kon.execute(
                """SELECT so.template_id, so.tanda_tangan FROM sesi_soal ss
                   JOIN soal so ON so.id = ss.soal_id
                   WHERE ss.sesi_id = ? ORDER BY ss.nomor""",
                (sesi_id,),
            ).fetchall()
        a, b = data(baru_a), data(baru_b)
        meta = kon.execute(
            """SELECT siswa_id, level, mode, jenis, sumber_sesi_id, tujuan,
                      putaran_id, kunci_idempotensi
               FROM sesi WHERE id = ?""",
            (baru_a,),
        ).fetchone()

    assert len(a) == 5
    assert {x["template_id"] for x in a} == {butir[0]["template_id"]}
    assert len({x["tanda_tangan"] for x in a}) == 5
    assert not ({x["tanda_tangan"] for x in a} & sumber_sig)
    assert [x["tanda_tangan"] for x in a] == [x["tanda_tangan"] for x in b]
    assert dict(meta) == {
        "siswa_id": siswa,
        "level": "P3",
        "mode": "drill",
        "jenis": "biasa",
        "sumber_sesi_id": None,
        "tujuan": "bebas",
        "putaran_id": None,
        "kunci_idempotensi": None,
    }


def test_butir_dari_sesi_lain_anak_yang_sama_ditolak_tanpa_efek(db):
    with database.buka(db) as kon:
        siswa, sesi_a, _ = _hasil_t(kon)
        paket = topics.paket_untuk_template(["soal_uang"])
        sesi_b = database.buat_sesi_dari_urutan(
            kon, siswa, 52_001, ("soal_uang",), topik=paket, level="P3"
        )
        butir_b = database.isi_sesi(kon, sesi_b)
        jid = database.simpan_jawaban(
            kon, int(butir_b[0]["sesi_soal_id"]), jawaban="belum tahu",
            belum_pernah=True,
        )
        database.simpan_diagnosis(
            kon, jid, False, "T", "T", alasan="Data sintetis"
        )
        database.tandai_selesai(kon, sesi_b)
        sebelum = tuple(kon.iterdump())
        with pytest.raises(similar_practice.LatihanSerupaTidakTersedia):
            similar_practice.buat_dari_hasil_t(
                kon, sesi_a, int(butir_b[0]["sesi_soal_id"]), seed=92
            )
        assert tuple(kon.iterdump()) == sebelum


def test_orchestrasi_lintas_topik_level_dan_seed(db):
    """Semua paket/level memilih template nyata tanpa mengubah generator."""
    kombinasi = []
    for topik_id in topics.daftar_topik():
        if topik_id == "campuran":
            continue
        paket = topics.ambil(topik_id)
        for level, urutan in paket.komposisi.items():
            if urutan:
                kombinasi.append((topik_id, level, urutan[0]))
    with database.buka(db) as kon:
        for indeks, (topik_id, level, template_id) in enumerate(kombinasi):
            siswa = database.tambah_siswa(
                kon, f"Sapuan-{indeks}", tingkat=level, pemilik="guru"
            )
            sumber = database.buat_sesi_dari_urutan(
                kon, siswa, 60_000 + indeks, (template_id,),
                topik=topics.ambil(topik_id), level=level,
            )
            item = database.isi_sesi(kon, sumber)[0]
            jid = database.simpan_jawaban(
                kon, int(item["sesi_soal_id"]), jawaban="belum tahu",
                belum_pernah=True,
            )
            database.simpan_diagnosis(
                kon, jid, False, "T", "T", alasan="Data sintetis"
            )
            database.tandai_selesai(kon, sumber)
            sumber_sig = kon.execute(
                "SELECT tanda_tangan FROM soal WHERE id = ?", (item["soal_id"],)
            ).fetchone()[0]
            for nomor_seed in (0, 1, 2):
                baru = similar_practice.buat_dari_hasil_t(
                    kon, sumber, int(item["sesi_soal_id"]),
                    seed=70_000 + indeks * 10 + nomor_seed,
                )
                isi = database.isi_sesi(kon, baru)
                tanda = [kon.execute(
                    "SELECT tanda_tangan FROM soal WHERE id = ?", (b["soal_id"],)
                ).fetchone()[0] for b in isi]
                assert len(isi) == 5
                assert {b["template_id"] for b in isi} == {template_id}
                assert {b["level"] for b in isi} == {level}
                assert len(set(tanda)) == 5
                assert sumber_sig not in tanda


def test_generator_menolak_tanda_tangan_sumber_dan_duplikat(monkeypatch):
    paket = topics.paket_untuk_template(["soal_umur"])
    contoh = __import__("generator").buat_soal(
        "soal_umur", 1, level="P3", topik=paket.id
    )
    monkeypatch.setattr(similar_practice, "_BATAS_PERCOBAAN", 6)
    monkeypatch.setattr(similar_practice, "buat_soal", lambda *_a, **_k: contoh)
    with pytest.raises(RuntimeError, match="variasi soal serupa belum cukup"):
        similar_practice._pilih_soal_baru(
            "soal_umur", "P3", 1, {contoh.tanda_tangan}
        )


def test_exhaustion_service_tidak_menyimpan_artefak(db, monkeypatch):
    with database.buka(db) as kon:
        _siswa, sesi, butir = _hasil_t(kon)
        contoh = __import__("generator").buat_soal(
            "soal_umur", 1, level="P3", topik="logika"
        )
        sebelum = tuple(kon.iterdump())
        monkeypatch.setattr(similar_practice, "_BATAS_PERCOBAAN", 4)
        monkeypatch.setattr(similar_practice, "buat_soal", lambda *_a, **_k: contoh)
        with pytest.raises(RuntimeError, match="variasi soal serupa"):
            similar_practice.buat_dari_hasil_t(
                kon, sesi, int(butir[0]["sesi_soal_id"]), seed=113
            )
        assert tuple(kon.iterdump()) == sebelum


def test_gagal_setelah_sebagian_butir_rollback_semua_artefak(db, monkeypatch):
    with database.buka(db) as kon:
        _siswa, sesi, butir = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
        asli = database._simpan_butir_sesi
        jumlah = 0

        def gagal_ketiga(*args, **kwargs):
            nonlocal jumlah
            jumlah += 1
            if jumlah == 3:
                raise ValueError("penyimpanan sintetis gagal")
            return asli(*args, **kwargs)

        monkeypatch.setattr(database, "_simpan_butir_sesi", gagal_ketiga)
        with pytest.raises(ValueError, match="penyimpanan sintetis gagal"):
            similar_practice.buat_dari_hasil_t(
                kon, sesi, int(butir[0]["sesi_soal_id"]), seed=992
            )
        assert tuple(kon.iterdump()) == sebelum


def test_generator_gagal_tidak_menyimpan_artefak(db, monkeypatch):
    with database.buka(db) as kon:
        _siswa, sesi, butir = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())

        def gagal(*_args, **_kwargs):
            raise RuntimeError("generator sintetis gagal")

        monkeypatch.setattr(similar_practice, "buat_soal", gagal)
        with pytest.raises(RuntimeError, match="generator sintetis gagal"):
            similar_practice.buat_dari_hasil_t(
                kon, sesi, int(butir[0]["sesi_soal_id"]), seed=123
            )
        assert tuple(kon.iterdump()) == sebelum


def test_pembuatan_tidak_mengubah_sumber_snapshot_rencana_atau_bukti(db):
    with database.buka(db) as kon:
        siswa, sumber, butir = _hasil_t(kon)
        sumber_sebelum = tuple(tuple(x) for x in database.isi_sesi(kon, sumber))
        domain_sebelum = _jumlah_domain(kon)
        baru = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(butir[0]["sesi_soal_id"]), seed=781
        )
        sumber_sesudah = tuple(tuple(x) for x in database.isi_sesi(kon, sumber))
        domain_sesudah = _jumlah_domain(kon)
        assert kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE id = ? AND siswa_id = ?", (baru, siswa)
        ).fetchone()[0] == 1

    assert sumber_sesudah == sumber_sebelum
    assert domain_sesudah["sesi"] == domain_sebelum["sesi"] + 1
    assert domain_sesudah["sesi_soal"] == domain_sebelum["sesi_soal"] + 5
    for nama in ("jawaban", "diagnosis", "putaran_fokus", "anggota_fokus",
                 "bukti_fokus", "konfirmasi_hasil", "snapshot_outcome",
                 "kejadian_belajar"):
        assert domain_sesudah[nama] == domain_sebelum[nama]


def test_drill_serupa_tidak_bisa_dipaksa_masuk_pemetaan(db):
    with database.buka(db) as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        baru = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(butir[0]["sesi_soal_id"]), seed=888
        )
        payload = {"sertakan_pemetaan": "1"}
        for item in database.isi_sesi(kon, baru):
            database.simpan_jawaban(
                kon, int(item["sesi_soal_id"]), jawaban=item["kunci"]
            )
            payload[f'jwb_{item["sesi_soal_id"]}'] = item["kunci"]
            payload[f'kode_{item["sesi_soal_id"]}'] = "benar"
        database.tandai_selesai(kon, baru)
        sebelum = _jumlah_domain(kon)
        with pytest.raises(ValueError, match="hanya sesi diagnostik bebas"):
            learning_cycle_service.konfirmasi_dari_form(
                kon, baru, "guru", payload
            )
        assert _jumlah_domain(kon) == sebelum
        halaman = teacher_pages.halaman_sesi_stitch(kon, baru).decode()
    assert 'name="sertakan_pemetaan"' not in halaman


def test_konfirmasi_latihan_manual_tidak_mengubah_rencana_atau_bukti_putaran(db):
    with database.buka(db) as kon:
        siswa, sumber, sumber_butir = _hasil_t(kon)
        putaran = database.buat_putaran_fokus(kon, siswa, "P3")
        kon.execute(
            "UPDATE sesi SET putaran_id = ?, tujuan = 'pemetaan' WHERE id = ?",
            (putaran, sumber),
        )
        database.konfirmasi_hasil(kon, sumber, "guru")
        rencana_sebelum = learning_cycle.rencana_berikutnya(
            database.muat_bukti_siklus(kon, siswa), siswa
        )
        sumber_snapshot = tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM snapshot_outcome WHERE konfirmasi_id IN "
            "(SELECT id FROM konfirmasi_hasil WHERE sesi_id = ?)", (sumber,)
        ))
        bukti_sebelum = tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM bukti_fokus WHERE sesi_id = ?", (sumber,)
        ))
        kejadian_putaran = tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM kejadian_belajar WHERE putaran_id = ? ORDER BY id", (putaran,)
        ))
        baru = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(sumber_butir[0]["sesi_soal_id"]), seed=1291
        )
        for item in database.isi_sesi(kon, baru):
            jid = database.simpan_jawaban(
                kon, int(item["sesi_soal_id"]), jawaban=item["kunci"]
            )
            database.simpan_diagnosis(
                kon, jid, benar=True, kode_usulan=None, kode_final=None,
                alasan="jawaban benar",
            )
        database.tandai_selesai(kon, baru)
        database.konfirmasi_hasil(kon, baru, "guru")
        rencana_sesudah = learning_cycle.rencana_berikutnya(
            database.muat_bukti_siklus(kon, siswa), siswa
        )

        assert rencana_sesudah == rencana_sebelum
        assert tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM snapshot_outcome WHERE konfirmasi_id IN "
            "(SELECT id FROM konfirmasi_hasil WHERE sesi_id = ?)", (sumber,)
        )) == sumber_snapshot
        assert tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM bukti_fokus WHERE sesi_id = ?", (sumber,)
        )) == bukti_sebelum
        assert tuple(tuple(x) for x in kon.execute(
            "SELECT * FROM kejadian_belajar WHERE putaran_id = ? ORDER BY id", (putaran,)
        )) == kejadian_putaran
        assert kon.execute(
            "SELECT COUNT(*) FROM snapshot_outcome WHERE konfirmasi_id IN "
            "(SELECT id FROM konfirmasi_hasil WHERE sesi_id = ?)", (baru,)
        ).fetchone()[0] == 5
        event = kon.execute(
            "SELECT putaran_id, jenis FROM kejadian_belajar WHERE sesi_id = ?", (baru,)
        ).fetchall()
        assert [tuple(x) for x in event] == [(None, "hasil_dikonfirmasi")]


def test_http_guru_membuat_dan_admin_boleh_untuk_keluarga_lain(server):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        siswa_lain, sumber_lain, butir_lain = _hasil_t(kon, pemilik="guru-lain")
    for sesi, item, kredensial in (
        (sumber, butir[0], ("guru", SANDI_GURU)),
        (sumber_lain, butir_lain[0], ("pengelola", SANDI_ADMIN)),
    ):
        kode, isi, _ = server.minta(
            f"/sesi/{sesi}/latihan-serupa",
            auth=kredensial,
            data={"sesi_soal_id": str(item["sesi_soal_id"])},
        )
        assert kode == 200
        assert "Latihan Cepat" in isi
    with server.buka() as kon:
        assert kon.execute(
            "SELECT COUNT(*) FROM sesi WHERE siswa_id = ?", (siswa_lain,)
        ).fetchone()[0] == 2


def test_body_dibaca_tanpa_lock_writer_dan_otorisasi_di_dalam_transaksi(server, monkeypatch):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
    jalur = f"/sesi/{sumber}/latihan-serupa"
    asli_rute = web.Penangan._rute_post
    asli_palang = web.Penangan._bisa_lihat_sesi
    diperiksa = []

    class Pembaca:
        def __init__(self, asli):
            self.asli = asli

        def read(self, ukuran):
            with sqlite3.connect(str(server.db), timeout=0) as lain:
                lain.execute("BEGIN IMMEDIATE")
                lain.rollback()
            diperiksa.append("body_tanpa_lock")
            return self.asli.read(ukuran)

        def __getattr__(self, nama):
            return getattr(self.asli, nama)

    def rute(penangan):
        if penangan.path != jalur:
            return asli_rute(penangan)
        pembaca = penangan.rfile
        penangan.rfile = Pembaca(pembaca)
        try:
            return asli_rute(penangan)
        finally:
            penangan.rfile = pembaca

    def palang(penangan, kon, sesi_id):
        if penangan.command == "POST" and penangan.path == jalur:
            assert kon.in_transaction
            diperiksa.append("otorisasi_dalam_transaksi")
        return asli_palang(penangan, kon, sesi_id)

    monkeypatch.setattr(web.Penangan, "_rute_post", rute)
    monkeypatch.setattr(web.Penangan, "_bisa_lihat_sesi", palang)
    kode, _, _ = server.minta(
        jalur, auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 200
    assert diperiksa == ["body_tanpa_lock", "otorisasi_dalam_transaksi"]


@pytest.mark.parametrize("id_palsu", ["0", "-1", "9" * 30, "tidak-sah"])
def test_http_id_sesi_tidak_sah_404_tanpa_efek(server, id_palsu):
    with server.buka() as kon:
        _siswa, _sumber, butir = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(
        f"/sesi/{id_palsu}/latihan-serupa", auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 404
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_url_alias_dengan_segment_tambahan_404_tanpa_efek(server):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(
        f"/sesi/{sumber}/foo/latihan-serupa",
        auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 404
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_asing_dan_hilang_404_identik_tanpa_efek(server):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon, pemilik="guru-lain")
        sebelum = tuple(kon.iterdump())
    payload = {"sesi_soal_id": str(butir[0]["sesi_soal_id"])}
    asing = server.minta(
        f"/sesi/{sumber}/latihan-serupa", auth=("guru", SANDI_GURU), data=payload
    )
    hilang = server.minta(
        "/sesi/999999/latihan-serupa", auth=("guru", SANDI_GURU), data=payload
    )
    assert asing[:2] == hilang[:2]
    assert asing[0] == 404
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize(
    "auth_data,pakai_token",
    [(None, False), (("feby", SANDI_MURID), False), (None, True)],
)
def test_http_anonim_dan_murid_tidak_bisa_membuat(server, auth_data, pakai_token):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        sebelum = _jumlah_domain(kon)
    akun_murid = auth.cari_akun("feby")
    token = sessions.buat(
        akun_murid["pengguna"], "murid", id_akun=akun_murid["id_akun"],
        revisi_auth=akun_murid["revisi_auth"],
    ) if pakai_token else None
    kode, isi, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa",
        auth=auth_data,
        cookie=token,
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 401
    assert "Latih tipe soal ini" not in isi
    with server.buka() as kon:
        assert _jumlah_domain(kon) == sebelum


def test_share_token_asli_bukan_otorisasi_dan_html_anak_tanpa_cta(server):
    with server.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak Tautan", pemilik="guru")
        sesi_terbuka = database.buat_sesi(kon, siswa, seed=611, jumlah_soal=1)
        token = share_links.buat(kon, sesi_terbuka)
        _siswa, sumber, butir = _hasil_t(kon)
        sebelum = _jumlah_domain(kon)
    kode_anak, html_anak, _ = server.minta(f"/mulai/{token}")
    kode_post, isi_post, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa",
        cookie=token,
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode_anak == 200
    assert "Latih tipe soal ini" not in html_anak
    assert "/latihan-serupa" not in html_anak
    assert kode_post == 401
    assert "Latih tipe soal ini" not in isi_post
    with server.buka() as kon:
        assert _jumlah_domain(kon) == sebelum


def test_http_exhaustion_409_ramah_tanpa_artefak(server, monkeypatch):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        contoh = __import__("generator").buat_soal(
            "soal_umur", 1, level="P3", topik="logika"
        )
        sebelum = tuple(kon.iterdump())
    monkeypatch.setattr(similar_practice, "_BATAS_PERCOBAAN", 3)
    monkeypatch.setattr(similar_practice, "buat_soal", lambda *_a, **_k: contoh)
    kode, isi, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa",
        auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 409
    assert "variasi soalnya belum cukup" in isi
    assert "RuntimeError" not in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_forged_opt_in_drill_rollback_snapshot_dan_event(server):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        baru = similar_practice.buat_dari_hasil_t(
            kon, sumber, int(butir[0]["sesi_soal_id"]), seed=721
        )
        payload = {"sertakan_pemetaan": "1"}
        for item in database.isi_sesi(kon, baru):
            jid = database.simpan_jawaban(
                kon, int(item["sesi_soal_id"]), jawaban=item["kunci"]
            )
            database.simpan_diagnosis(
                kon, jid, True, None, None, alasan="jawaban benar"
            )
            payload[f'jwb_{item["sesi_soal_id"]}'] = item["kunci"]
            payload[f'kode_{item["sesi_soal_id"]}'] = "benar"
        database.tandai_selesai(kon, baru)
        sebelum = _jumlah_domain(kon)
    kode, isi, _ = server.minta(
        f"/sesi/{baru}/konfirmasi",
        auth=("guru", SANDI_GURU), data=payload,
    )
    assert kode == 400
    assert "hanya sesi diagnostik bebas" in isi
    with server.buka() as kon:
        assert _jumlah_domain(kon) == sebelum


@pytest.mark.parametrize("payload,status", [
    ({}, 400),
    ({"sesi_soal_id": ""}, 409),
    ({"sesi_soal_id": "bukan-angka"}, 409),
    ({"sesi_soal_id": "-1"}, 409),
    ({"sesi_soal_id": "999999"}, 409),
    ({"sesi_soal_id": "9" * 30}, 409),
    ([("sesi_soal_id", "1"), ("sesi_soal_id", "2")], 400),
])
def test_http_referensi_rusak_atau_duplikat_tanpa_efek(server, payload, status):
    with server.buka() as kon:
        _siswa, sumber, _ = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa", auth=("guru", SANDI_GURU), data=payload,
    )
    assert kode == status
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_butir_sesi_lain_tidak_bisa_dipilih(server):
    with server.buka() as kon:
        _siswa, sumber, _ = _hasil_t(kon)
        _lain, _sumber_lain, butir_lain = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa", auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir_lain[0]["sesi_soal_id"])},
    )
    assert kode == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_payload_palsu_ditolak_dan_tidak_memilih_template_dari_form(server):
    with server.buka() as kon:
        _siswa, sumber, butir = _hasil_t(kon)
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa",
        auth=("guru", SANDI_GURU),
        data={
            "sesi_soal_id": str(butir[0]["sesi_soal_id"]),
            "template_id": "soal_uang",
            "level": "P6",
            "jumlah": "50",
        },
    )
    assert kode == 400
    assert "Referensi soal tidak dikenal" in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("perubahan", ["non_t", "belum_selesai", "dibatalkan", "level"])
def test_http_status_berubah_setelah_render_ditolak_tanpa_sesi_baru(server, perubahan):
    with server.buka() as kon:
        siswa, sumber, butir = _hasil_t(kon)
        if perubahan == "non_t":
            kon.execute(
                "UPDATE diagnosis SET kode_final = 'K' WHERE jawaban_id = ?",
                (butir[0]["jawaban_id"],),
            )
        elif perubahan == "belum_selesai":
            kon.execute("UPDATE sesi SET selesai = NULL WHERE id = ?", (sumber,))
        elif perubahan == "dibatalkan":
            kon.execute("UPDATE sesi SET dibatalkan = '2026-09-10' WHERE id = ?", (sumber,))
        else:
            kon.execute("UPDATE siswa SET tingkat = 'P4' WHERE id = ?", (siswa,))
        sebelum = _jumlah_domain(kon)
    kode, isi, _ = server.minta(
        f"/sesi/{sumber}/latihan-serupa",
        auth=("guru", SANDI_GURU),
        data={"sesi_soal_id": str(butir[0]["sesi_soal_id"])},
    )
    assert kode == 409
    assert "tidak lagi memenuhi syarat" in isi
    with server.buka() as kon:
        assert _jumlah_domain(kon) == sebelum
