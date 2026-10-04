"""Regresi arsitektur empat tujuan ruang anak dan kompatibilitas URL lama."""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

import pytest

import assistant_client
import assistant_service
import database
import llm
import mastery_report
import profile_history
import profile_workspace
import reports
from http_test_kit import SANDI_GURU, ServerUji, _basic


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _mentah(server, jalur, *, data=None):
    isi = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(server.alamat + jalur, data=isi)
    req.add_header("Authorization", _basic("guru", SANDI_GURU))
    if isi is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    pembuka = urllib.request.build_opener(_TanpaIkut())
    try:
        with pembuka.open(req, timeout=10) as respons:
            return respons.status, dict(respons.headers), respons.read().decode()
    except urllib.error.HTTPError as galat:
        return galat.code, dict(galat.headers), galat.read().decode("utf-8", "replace")


@pytest.fixture()
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.anak = database.tambah_siswa(kon, "Anak Arsitektur", "P3", pemilik="guru")
        srv.asing = database.tambah_siswa(kon, "Anak Keluarga Lain", "P3", pemilik="lain")
    yield srv
    srv.berhenti()


def test_default_dan_navigasi_empat_tujuan_berbasis_maksud(server):
    kode, isi, _ = server.minta(f"/anak/{server.anak}", auth=("guru", SANDI_GURU))
    assert kode == 200
    nav = isi.split('class="profil-tabs-st"', 1)[1].split("</nav>", 1)[0]
    label = ("Berikutnya", "Buat latihan", "Riwayat", "Perkembangan")
    assert [nav.index(teks) for teks in label] == sorted(nav.index(teks) for teks in label)
    assert f'href="/anak/{server.anak}?section=rencana" aria-current="page"' in nav
    assert "Langkah berikutnya" not in nav and "Laporan perkembangan" not in nav
    assert 'class="kartu-rencana-st"' in isi
    assert f'action="/sesi-baru/{server.anak}"' not in isi
    assert profile_history.parse_filter("").section == "rencana"
    assert profile_history.parse_filter("sorot=1").section == "latihan"


@pytest.mark.parametrize(
    "jalur,data,bagian",
    (
        ("/sesi-baru/{anak}", {"topik": "pola-bilangan"}, "latihan"),
        ("/sesi-gabungan/{anak}", {"topik": "pola-bilangan"}, "latihan"),
        ("/sesi-remedial/{anak}", {}, "latihan"),
    ),
)
def test_prg_latihan_manual_selalu_eksplisit(server, jalur, data, bagian):
    kode, tajuk, _ = _mentah(server, jalur.format(anak=server.anak), data=data)
    assert kode == 303
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(tajuk["Location"]).query)["section"] == [bagian]


def test_prg_siklus_dan_riwayat_selalu_eksplisit(server):
    kode, tajuk, _ = _mentah(server, f"/siklus/{server.anak}/buat", data={})
    assert kode == 303 and tajuk["Location"].startswith("/sesi/")
    with server.buka() as kon:
        sesi = kon.execute("SELECT id FROM sesi WHERE siswa_id=? ORDER BY id DESC", (server.anak,)).fetchone()[0]
    kode, tajuk, _ = _mentah(
        server, f"/sesi/{sesi}/batalkan", data={"alasan": "Regresi sintetis"},
    )
    assert kode == 303 and tajuk["Location"] == f"/anak/{server.anak}?section=rencana"

    with server.buka() as kon:
        manual = database.buat_sesi(kon, server.anak, seed=901, jumlah_soal=1)
    kode, tajuk, _ = _mentah(server, f"/sesi/{manual}/cabut-tautan", data={})
    assert kode == 303
    assert tajuk["Location"].startswith(f"/anak/{server.anak}?section=riwayat")


@pytest.mark.parametrize(
    "query,tujuan",
    (
        ("section=riwayat", "section=riwayat"),
        ("section=riwayat&tampilan=sesi", "section=riwayat"),
        ("section=riwayat&tampilan=mingguan", "section=perkembangan"),
        ("section=riwayat&tampilan=mingguan", "rincian=tren"),
        ("section=riwayat&tampilan=catatan", "section=perkembangan"),
        ("section=riwayat&tampilan=catatan", "bagian=penguasaan"),
        ("section=penguasaan&tampilan=konteks", "section=perkembangan"),
        ("section=penguasaan&tampilan=konteks", "bagian=penguasaan"),
        ("section=penguasaan&tampilan=kriteria", "rincian=kriteria"),
        ("section=penguasaan&tampilan=pilot", "section=perkembangan"),
        ("section=penguasaan&tampilan=pilot", "bagian=perjalanan"),
        ("section=penguasaan&tampilan=perjalanan", "section=perkembangan"),
        ("section=penguasaan&tampilan=perjalanan", "bagian=perjalanan"),
    ),
)
def test_deep_link_laporan_lama_dialihkan_setelah_guard(server, query, tujuan):
    kode, tajuk, _ = _mentah(server, f"/laporan/{server.anak}?{query}")
    assert kode == 303
    assert tujuan in tajuk["Location"]


def test_alias_laporan_asing_404_identik_tanpa_write(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    a = server.minta(
        f"/laporan/{server.asing}?section=penguasaan&tampilan=pilot",
        auth=("guru", SANDI_GURU),
    )
    b = server.minta(
        "/laporan/999999?section=penguasaan&tampilan=pilot",
        auth=("guru", SANDI_GURU),
    )
    assert a[0] == b[0] == 404 and a[1] == b[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_berikutnya_mendeduplikasi_sesi_cta_dari_tugas_sekunder(server):
    server.minta(f"/siklus/{server.anak}/buat", auth=("guru", SANDI_GURU), data={})
    with server.buka() as kon:
        sesi = kon.execute("SELECT id FROM sesi WHERE siswa_id=?", (server.anak,)).fetchone()[0]
    kode, isi, _ = server.minta(f"/anak/{server.anak}", auth=("guru", SANDI_GURU))
    assert kode == 200
    badan = isi.split("</style>", 1)[1]
    assert badan.count(f'href="/sesi/{sesi}"') == 1
    assert badan.count('class="st-kartu-baris kartu-sesi-guru') <= 3
    assert "Kelola tautan anak" not in badan


def test_get_semua_tujuan_alias_readonly_dan_tanpa_ai(server, monkeypatch):
    def terlarang(*args, **kwargs):
        pytest.fail("GET ruang anak memanggil AI")

    monkeypatch.setattr(assistant_service, "panggil_provider_default", terlarang)
    monkeypatch.setattr(assistant_client, "kirim", terlarang)
    monkeypatch.setattr(llm, "_panggil", terlarang)
    jalur = (
        f"/anak/{server.anak}",
        f"/anak/{server.anak}?section=latihan",
        f"/anak/{server.anak}?section=riwayat",
        f"/laporan/{server.anak}",
        f"/laporan/{server.anak}?section=penguasaan",
        f"/laporan/{server.anak}?section=perjalanan",
        f"/laporan/{server.anak}?section=penguasaan&tampilan=konteks",
    )
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    for url in jalur:
        kode, _, _ = server.minta(url, auth=("guru", SANDI_GURU))
        assert kode == 200
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_ringkasan_tanpa_bukti_memakai_empty_state_jujur(server):
    kode, isi, _ = server.minta(f"/laporan/{server.anak}", auth=("guru", SANDI_GURU))
    assert kode == 200
    konten = isi.split('id="konten-laporan"', 1)[1]
    assert "Belum cukup bukti untuk menilai perkembangan materi" in konten
    assert 'id="rencana-belajar-laporan"' not in konten
    assert "Rincian tugas" not in konten


def test_navigasi_mobile_satu_baris_dan_riwayat_satu_kolom_semantik():
    css = profile_workspace.GAYA_PROFIL
    mobile = css.split("@media(max-width:48rem)", 1)[1]
    nav = mobile.split(".profil-workspace-st .profil-tabs-st {", 1)[1].split("}", 1)[0]
    baris = mobile.split(".profil-workspace-st .riwayat-kartu-st {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in nav
    assert "overflow-x:hidden" in nav
    assert "flex-direction:column" in baris
    assert "position:absolute" not in baris
    aksi = mobile.split(".profil-workspace-st .riwayat-aksi-st {", 1)[1].split("}", 1)[0]
    assert "align-self:stretch" in aksi


def test_empty_state_presenter_tidak_mengubah_status_reducer():
    from learning_cycle import BuktiSiklus

    peta = mastery_report.peta_penguasaan(BuktiSiklus(1, "P3"), 1)
    sebelum = tuple((s.id, s.status) for s in peta.status)
    isi = mastery_report.render_peta(peta, reports._tanggal_pendek, ringkas=True)
    sesudah = tuple((s.id, s.status) for s in peta.status)
    assert sebelum == sesudah
    assert all(status == "belum_dinilai" for _, status in sesudah)
    assert "Belum cukup bukti untuk menilai perkembangan materi" in isi
