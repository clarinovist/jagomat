"""Audit HTTP negatif handoff sesi dan provenance rencana belajar.

Semua identitas, basis data, dan token hanya hidup di fixture sementara. Alur
menemukan action/form dari HTML agar test tidak melompati kontrol yang hilang.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import share_links  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SANDI_GURU_LAIN = "sandi-guru-lain-aman-456"


class _FormParser(HTMLParser):
    """Ambil kontrak navigasi/form tanpa dependency parser eksternal."""

    def __init__(self):
        super().__init__()
        self.forms = []
        self.links = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == "form":
            self._form = {
                "action": atribut.get("action", ""),
                "method": atribut.get("method", "get").lower(),
                "fields": {},
                "buttons": [],
            }
            self.forms.append(self._form)
        elif tag == "a" and atribut.get("href"):
            self.links.append(atribut["href"])
        elif (
            self._form is not None
            and tag in {"input", "select", "textarea"}
            and atribut.get("name")
        ):
            self._form["fields"][atribut["name"]] = atribut.get("value", "")
        elif self._form is not None and tag == "button":
            self._form["buttons"].append({
                "name": atribut.get("name", ""),
                "value": atribut.get("value", ""),
                "formaction": atribut.get("formaction", ""),
                "type": atribut.get("type", "submit"),
            })

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None


def _parse(isi):
    parser = _FormParser()
    parser.feed(isi)
    return parser


def _form(parser, action, method="post"):
    cocok = [f for f in parser.forms if f["action"] == action and f["method"] == method]
    assert len(cocok) == 1, f"form {method.upper()} {action} harus tepat satu"
    return cocok[0]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun(
        "guru-lain", SANDI_GURU_LAIN, "guru", path=auth.BERKAS_SANDI
    )
    with s.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
        siswa_lain = database.tambah_siswa(
            kon, "Anak Keluarga Lain", "P3", pemilik="guru-lain"
        )
    yield s, siswa, siswa_lain
    s.berhenti()


def _buat_sesi_dari_form(s, siswa_id):
    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    assert kode == 200
    action = f"/siklus/{siswa_id}/buat"
    form = _form(_parse(isi), action)
    assert form["fields"] == {}
    kode, _, _ = s.minta(action, auth=("guru", SANDI_GURU), data=form["fields"])
    assert kode == 200
    with s.buka() as kon:
        sesi = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? ORDER BY id DESC", (siswa_id,)
        ).fetchone()
    assert sesi is not None
    return int(sesi["id"])


def _bagikan(s, sesi_id):
    kode, isi, _ = s.minta(
        f"/sesi/{sesi_id}/bagikan", auth=("guru", SANDI_GURU), data={}
    )
    assert kode == 200
    cocok = re.search(r'id="tautan-sesi"[^>]*value="[^"]*/mulai/([^"]+)"', isi)
    assert cocok is not None, "respons bagikan harus menyediakan token yang baru dibuat"
    return cocok.group(1)


def _batalkan_dari_form(s, sesi_id):
    kode, isi, _ = s.minta(f"/sesi/{sesi_id}", auth=("guru", SANDI_GURU))
    assert kode == 200
    action = f"/sesi/{sesi_id}/batalkan"
    form = _form(_parse(isi), action)
    assert set(form["fields"]) == {"alasan"}
    kode, _, _ = s.minta(
        action,
        auth=("guru", SANDI_GURU),
        data={"alasan": "dibatalkan dalam fixture sintetis"},
    )
    assert kode == 200
    with s.buka() as kon:
        assert kon.execute(
            "SELECT dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["dibatalkan"] is not None


def _snapshot_handoff(kon, sesi_id):
    sesi = kon.execute(
        "SELECT mulai, selesai, dibatalkan FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    return {
        "database": tuple(kon.iterdump()),
        "sesi": tuple(sesi),
        "tautan": tuple(tuple(b) for b in kon.execute(
            "SELECT token_hash, dibuat, kedaluarsa, dicabut FROM tautan_sesi WHERE sesi_id = ?",
            (sesi_id,),
        )),
        "jawaban": kon.execute(
            """SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss
               ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0],
        "bukti": kon.execute(
            "SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id = ?", (sesi_id,)
        ).fetchone()[0],
    }


@pytest.mark.parametrize("punya_tautan", [False, True])
@pytest.mark.parametrize("fetch", [False, True])
def test_sesi_dibatalkan_tidak_bisa_dibagikan_baru(server, punya_tautan, fetch, monkeypatch):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    if punya_tautan:
        _bagikan(s, sesi)
    _batalkan_dari_form(s, sesi)
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())

    pemanggilan = []
    buat_asli = share_links.buat

    def catat_pembuatan(*args, **kwargs):
        pemanggilan.append(True)
        return buat_asli(*args, **kwargs)

    monkeypatch.setattr(share_links, "buat", catat_pembuatan)
    kode, isi, header = s.minta(
        f"/sesi/{sesi}/bagikan", auth=("guru", SANDI_GURU), data={},
        headers={"X-Requested-With": "fetch"} if fetch else {},
    )

    assert kode == 409
    assert "Sesi dibatalkan" in isi
    assert 'id="tautan-sesi"' not in isi
    assert header["Cache-Control"] == "no-store"
    assert pemanggilan == [], "handler wajib menolak sebelum memanggil pembuat token"
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_tautan_lama_sesi_dibatalkan_ditolak_get_dengan_404_identik(server):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    token = _bagikan(s, sesi)
    _batalkan_dari_form(s, sesi)
    with s.buka() as kon:
        sebelum = _snapshot_handoff(kon, sesi)

    kode_acuan, isi_acuan, _ = s.minta(f"/mulai/{'x' * len(token)}")
    kode, isi, _ = s.minta(f"/mulai/{token}")

    with s.buka() as kon:
        sesudah = _snapshot_handoff(kon, sesi)
    assert (kode_acuan, kode, isi == isi_acuan, sesudah) == (
        404, 404, True, sebelum
    )


@pytest.mark.parametrize("aksi", ["mulai", "simpan", "selesai"])
def test_tautan_lama_sesi_dibatalkan_ditolak_post_tanpa_efek(server, aksi):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    token = _bagikan(s, sesi)
    _batalkan_dari_form(s, sesi)
    with s.buka() as kon:
        sebelum = _snapshot_handoff(kon, sesi)
        sesi_soal_id = database.isi_sesi(kon, sesi)[0]["sesi_soal_id"]
    payload = {f"jwb_{sesi_soal_id}": "jawaban sesudah batal", "aksi": aksi}

    kode_acuan, isi_acuan, _ = s.minta(
        f"/mulai/{'x' * len(token)}", data=payload
    )
    kode, isi, _ = s.minta(f"/mulai/{token}", data=payload)

    with s.buka() as kon:
        sesudah = _snapshot_handoff(kon, sesi)
    assert (kode_acuan, kode, isi == isi_acuan, sesudah) == (
        404, 404, True, sebelum
    )


def test_profil_tidak_menawarkan_bagikan_sesi_dibatalkan(server):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    _batalkan_dari_form(s, sesi)
    kode, isi, _ = s.minta(f"/anak/{siswa}?section=riwayat", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert f'data-bagikan-url="/sesi/{sesi}/bagikan"' not in isi
    assert f'href="/sesi/{sesi}"' in isi, "riwayat tetap dapat dibuka guru"


def test_status_tautan_dibatalkan_tidak_aktif(server):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    _bagikan(s, sesi)
    with s.buka() as kon:
        assert share_links.aktif(kon, sesi)
    _batalkan_dari_form(s, sesi)
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
        assert not share_links.aktif(kon, sesi)
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("status", ["dibatalkan", "selesai"])
def test_pembuat_token_menolak_sesi_nonaktif_tanpa_rotasi(server, status):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    _bagikan(s, sesi)
    if status == "dibatalkan":
        _batalkan_dari_form(s, sesi)
    else:
        with s.buka() as kon:
            database.tandai_selesai(kon, sesi)
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError, match="sesi tidak aktif"):
            share_links.buat(kon, sesi)
        assert tuple(kon.iterdump()) == sebelum


def test_handler_bagikan_mengunci_status_sebelum_membuat_token(server, monkeypatch):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    buat_asli = share_links.buat
    transaksi = []

    def catat_transaksi(kon, *args, **kwargs):
        transaksi.append(kon.in_transaction)
        return buat_asli(kon, *args, **kwargs)

    monkeypatch.setattr(share_links, "buat", catat_transaksi)
    _bagikan(s, sesi)
    assert transaksi == [True]


def test_sesi_hilang_sebelum_kunci_bagikan_404_tanpa_token(server, monkeypatch):
    from contextlib import contextmanager

    s, siswa, _ = server
    # Sesi manual tanpa bukti memang dapat dihapus lewat jalur existing.
    with s.buka() as kon:
        sesi = database.buat_sesi(kon, siswa, seed=119, jumlah_soal=1)
    buka_asli = database.buka

    class KoneksiDisela:
        def __init__(self, kon):
            self.kon = kon

        def __getattr__(self, nama):
            return getattr(self.kon, nama)

        def execute(self, sql, *args):
            if sql == "BEGIN IMMEDIATE":
                # Hanya simulasi race penghapusan, bukan kebijakan hapus sesi.
                with buka_asli(s.db) as kedua:
                    kedua.execute("DELETE FROM sesi WHERE id = ?", (sesi,))
            return self.kon.execute(sql, *args)

    @contextmanager
    def buka_disela(path=None):
        with buka_asli(path) as kon:
            yield KoneksiDisela(kon)

    monkeypatch.setattr(database, "buka", buka_disela)
    kode, isi, _ = s.minta(f"/sesi/{sesi}/bagikan", auth=("guru", SANDI_GURU), data={})
    kode_hilang, isi_hilang, _ = s.minta("/sesi/999999/bagikan", auth=("guru", SANDI_GURU), data={})
    assert kode == kode_hilang == 404
    assert isi == isi_hilang
    with buka_asli(s.db) as kon:
        assert kon.execute("SELECT COUNT(*) FROM tautan_sesi").fetchone()[0] == 0


def test_pembatalan_setelah_cek_keberadaan_tidak_menghasilkan_token(server, monkeypatch):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    _bagikan(s, sesi)
    token_asli = share_links.secrets.token_urlsafe

    def batalkan_sebelum_insert(jumlah):
        # Koneksi kedua mensimulasikan pembatalan sesudah SELECT keberadaan,
        # sebelum INSERT. Guard satu statement harus menangkap status terbaru.
        with s.buka() as kedua:
            database.batalkan_sesi(kedua, sesi, "Pembatalan paralel sintetis")
        return token_asli(jumlah)

    monkeypatch.setattr(share_links.secrets, "token_urlsafe", batalkan_sebelum_insert)
    with s.buka() as kon:
        sebelum = tuple(tuple(b) for b in kon.execute("SELECT * FROM tautan_sesi"))
        with pytest.raises(ValueError, match="sesi tidak aktif"):
            share_links.buat(kon, sesi)
        assert tuple(tuple(b) for b in kon.execute("SELECT * FROM tautan_sesi")) == sebelum
        assert not share_links.aktif(kon, sesi)


@pytest.mark.parametrize("akhir", ["bagikan", "batalkan", "konfirmasi"])
def test_post_guru_keluarga_lain_404_identik_tanpa_efek(server, akhir):
    s, _, siswa_lain = server
    with s.buka() as kon:
        sesi_lain = database.buat_sesi(
            kon, siswa_lain, seed=91, level="P3", jumlah_soal=1
        )
        sebelum = tuple(kon.iterdump())
    jalur_asing = f"/sesi/{sesi_lain}/{akhir}"
    jalur_hilang = f"/sesi/999999/{akhir}"

    asing = s.minta(jalur_asing, auth=("guru", SANDI_GURU), data={})
    hilang = s.minta(jalur_hilang, auth=("guru", SANDI_GURU), data={})

    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert "Anak Keluarga Lain" not in asing[1]
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize("jalur", [
    "/siklus/{siswa}/buat",
    "/siklus/{siswa}/aksi",
    "/sesi/{sesi}/bagikan",
    "/sesi/{sesi}/batalkan",
    "/sesi/{sesi}/konfirmasi",
])
def test_murid_tidak_bisa_memakai_endpoint_guru(server, jalur):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    jalur = jalur.format(siswa=siswa, sesi=sesi)
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())

    kode, isi, _ = s.minta(jalur, auth=("feby", SANDI_MURID), data={})

    assert kode == 401
    badan = isi.split("</style>", 1)[-1]
    assert 'name="kode_' not in badan
    assert "malrule" not in badan.lower()
    assert "Kunci:" not in badan
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_inventaris_handoff_menemukan_kontrol_di_html(server):
    """Profil → buat → halaman sesi harus mengekspos handoff native."""
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)

    kode, isi, _ = s.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert kode == 200
    form = _form(_parse(isi), f"/sesi/{sesi}/bagikan")
    assert form["fields"] == {}


def test_manual_beda_level_dan_batal_tidak_mengambil_cta_rencana(server):
    s, siswa, _ = server
    sesi_batal = _buat_sesi_dari_form(s, siswa)
    _batalkan_dari_form(s, sesi_batal)
    with s.buka() as kon:
        database.buat_sesi(
            kon, siswa, seed=111, level="P3", jumlah_soal=1
        )
        sesi_beda_level = database.buat_sesi(
            kon, siswa, seed=112, level="P4", jumlah_soal=1
        )
        putaran_beda_level = database.buat_putaran_fokus(kon, siswa, "P4")
        # Bentuk fixture sesi orkestrator beda level tanpa mengubah aturan runtime.
        kon.execute(
            "UPDATE sesi SET tujuan = 'pemetaan', putaran_id = ? WHERE id = ?",
            (putaran_beda_level, sesi_beda_level),
        )

    kode, isi, _ = s.minta(f"/anak/{siswa}?section=rencana", auth=("guru", SANDI_GURU))

    assert kode == 200
    forms = [
        form for form in _parse(isi).forms
        if form["action"] == f"/siklus/{siswa}/buat"
    ]
    assert len(forms) == 1


def test_simpan_sementara_dan_review_belum_membuat_bukti(server):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    token = _bagikan(s, sesi)
    kode, isi, _ = s.minta(f"/mulai/{token}")
    assert kode == 200
    form = _form(_parse(isi), f"/mulai/{token}")
    nama_jawaban = next(n for n in form["fields"] if n.startswith("jwb_"))
    kode, _, _ = s.minta(
        f"/mulai/{token}", data={nama_jawaban: "jawaban draft", "aksi": "simpan"}
    )
    assert kode == 200
    kode, _, _ = s.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert kode == 200

    with s.buka() as kon:
        sesi_baris = kon.execute(
            "SELECT selesai, dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)
        ).fetchone()
        assert sesi_baris["selesai"] is None
        assert sesi_baris["dikonfirmasi_guru"] is None
        assert kon.execute(
            "SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id = ?", (sesi,)
        ).fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM snapshot_outcome").fetchone()[0] == 0


def test_gagal_konfirmasi_lengkap_tidak_membuat_bukti(server):
    s, siswa, _ = server
    sesi = _buat_sesi_dari_form(s, siswa)
    token = _bagikan(s, sesi)
    with s.buka() as kon:
        butir = database.isi_sesi(kon, sesi)[0]
    kode, _, _ = s.minta(
        f"/mulai/{token}",
        data={f"jwb_{butir['sesi_soal_id']}": "jawaban sintetis", "aksi": "selesai"},
    )
    assert kode == 200
    kode, isi, _ = s.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    assert kode == 200
    form = _form(_parse(isi), f"/sesi/{sesi}")
    nama = set(form["fields"])
    assert any(n.startswith("jwb_") for n in nama)
    assert any(n.startswith("cara_") for n in nama)
    assert any(n.startswith("kode_") for n in nama)
    assert any(n.startswith("cek_pemahaman_") for n in nama)
    tombol = [b for b in form["buttons"] if b["formaction"] == f"/sesi/{sesi}/konfirmasi"]
    assert len(tombol) == 1

    kode, _, _ = s.minta(
        tombol[0]["formaction"], auth=("guru", SANDI_GURU), data={}
    )

    assert kode == 400
    with s.buka() as kon:
        baris = kon.execute(
            "SELECT direview, dikonfirmasi_guru FROM sesi WHERE id = ?", (sesi,)
        ).fetchone()
        assert baris["direview"] is not None, "membuka review boleh memberi stamp review"
        assert baris["dikonfirmasi_guru"] is None
        assert kon.execute(
            "SELECT COUNT(*) FROM konfirmasi_hasil WHERE sesi_id = ?", (sesi,)
        ).fetchone()[0] == 0
        assert kon.execute(
            "SELECT COUNT(*) FROM snapshot_outcome"
        ).fetchone()[0] == 0
