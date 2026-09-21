"""Kartu rencana belajar guru di profil anak (Fase 4)."""
from __future__ import annotations

import re
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import interventions  # noqa: E402
import learning_cycle_ui  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402
from learning_cycle import (  # noqa: E402
    BuktiSiklus,
    PutaranFokus,
    RencanaBelajar,
    StatusFokus,
)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Rencana", "P3", pemilik="guru")
    yield s, siswa_id
    s.berhenti()


def _sesi_pemetaan(kon, siswa_id, putaran_id, nomor, *, salah=True, kode="H"):
    sesi_id = database.buat_sesi_dari_urutan(
        kon,
        siswa_id,
        seed=6100 + nomor,
        urutan=("deret_aritmetika",),
        level="P3",
    )
    tanggal = f"2026-09-0{nomor}"
    kon.execute(
        """UPDATE sesi
           SET tujuan = 'pemetaan', putaran_id = ?, tanggal = ?, selesai = ?
           WHERE id = ?""",
        (putaran_id, tanggal, tanggal + " 09:00:00", sesi_id),
    )
    butir = database.isi_sesi(kon, sesi_id)[0]
    butir_id = int(butir["sesi_soal_id"])
    if salah:
        jawaban_id = database.simpan_jawaban(kon, butir_id, "0", cara="cara uji")
        database.simpan_diagnosis(
            kon,
            jawaban_id,
            benar=False,
            kode_usulan=kode,
            kode_final=kode,
            alasan="Guru memastikan pengenalan" if kode == "T" else "diagnosis uji",
            manual=kode == "T",
        )
        database.konfirmasi_hasil(kon, sesi_id, guru="guru")
    else:
        database.konfirmasi_hasil(kon, sesi_id, guru="guru", dilewati={butir_id})
    return sesi_id


def _badan(isi):
    return isi.split("</style>", 1)[1]


def test_tab_rencana_anak_baru_menampilkan_satu_cta_tanpa_form_manual(server):
    s, siswa_id = server

    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))

    assert kode == 200
    assert f'href="/anak/{siswa_id}?section=rencana" aria-current="page"' in isi
    assert "Kenali cara anak menyelesaikan soal" in isi
    assert "Pemetaan membantu melihat materi yang sudah nyaman" in isi
    assert "Hari ini: 1 sesi · 15 soal" in isi
    assert "Sesi ini hanya untuk pemetaan awal." not in isi
    assert "Pemetaan awal: 0 dari 3 sesi terkonfirmasi" in isi
    assert "Ketiga sesi dilakukan pada tanggal berbeda." in isi
    assert "Peran orang tua/guru" in isi
    assert "Setelah selesai, periksa hasil dan konfirmasikan." in isi
    assert f'<form method="post" action="/siklus/{siswa_id}/buat"' in isi
    assert ">Siapkan sesi pemetaan pertama</button>" in isi
    assert "Sesudah ini, ikuti petunjuk agar anak mulai mengerjakan." in isi
    assert '<details class="alur-rencana-jelas-st">' in isi
    assert "<summary>" in isi
    assert "Detail progres dan alur belajar" in isi
    assert "Tahap sekarang: Pemetaan" in isi
    kartu = isi.split('<section class="kartu-rencana-st"', 1)[1].split("</section>", 1)[0]
    assert kartu.count("<h2") == 1
    assert '<h2 class="st judul-tugas-rencana-st" id="judul-rencana-belajar">' in kartu
    assert '<span class="penanda-judul-rencana-lama-st" aria-hidden="true">Mulai pemetaan</span>' in kartu
    assert isi.count("Pemetaan membantu melihat materi yang sudah nyaman") == 1
    assert "/* Rencana belajar jelas — kartu */" in isi.split("</style>", 1)[0]
    form_utama = isi.split(f'action="/siklus/{siswa_id}/buat"', 1)[1].split("</form>", 1)[0]
    assert "<input" not in form_utama
    assert '<details class="atur-latihan-st"' not in isi
    assert f'action="/sesi-baru/{siswa_id}"' not in isi
    assert f'action="/sesi-gabungan/{siswa_id}"' not in isi
    _, manual, _ = s.minta(f"/anak/{siswa_id}?section=latihan", auth=("guru", SANDI_GURU))
    assert manual.count(f'action="/sesi-baru/{siswa_id}"') == 1
    assert manual.count(f'action="/sesi-gabungan/{siswa_id}"') == 1


def test_get_profil_hanya_membaca_database(server):
    s, siswa_id = server
    with s.buka() as kon:
        sebelum = tuple(kon.iterdump())

    kode, _, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))

    with s.buka() as kon:
        sesudah = tuple(kon.iterdump())
    assert kode == 200
    assert sesudah == sebelum


def test_pemetaan_dua_dari_tiga_berasal_dari_snapshot_terkonfirmasi(server):
    s, siswa_id = server
    with s.buka() as kon:
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        _sesi_pemetaan(kon, siswa_id, putaran_id, 1)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 2)

    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))

    assert kode == 200
    assert "Pemetaan awal: 2 dari 3 sesi terkonfirmasi" in isi
    assert "Dua sesi terkonfirmasi membantu memperjelas pola belajar anak." in isi
    assert "Lanjutkan pemetaan level aktif." not in isi
    assert "Lanjutkan pemetaan" in isi
    assert ">Siapkan sesi pemetaan berikutnya</button>" in isi
    assert "Siapkan sesi pemetaan pertama" not in isi
    assert f'action="/siklus/{siswa_id}/buat"' in isi


def test_sesi_manual_dan_beda_level_tidak_menggantikan_cta_pemetaan(server):
    s, siswa_id = server
    with s.buka() as kon:
        manual = database.buat_sesi(kon, siswa_id, seed=6201, level="P3", jumlah_soal=1)
        lama = database.buat_sesi(kon, siswa_id, seed=6202, level="P4", jumlah_soal=1)

    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    kartu = isi.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]

    assert kode == 200
    assert f'action="/siklus/{siswa_id}/buat"' in kartu
    assert f'href="/sesi/{manual}"' not in kartu
    assert f'href="/sesi/{lama}"' not in kartu


def test_sesi_terpandu_sudah_dilihat_tetap_meminta_konfirmasi(server):
    s, siswa_id = server
    kode_buat, _, _ = s.minta(
        f"/siklus/{siswa_id}/buat", auth=("guru", SANDI_GURU), data={}
    )
    with s.buka() as kon:
        sesi = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? AND tujuan = 'pemetaan'",
            (siswa_id,),
        ).fetchone()["id"]
        kon.execute(
            "UPDATE sesi SET selesai = CURRENT_TIMESTAMP, direview = CURRENT_TIMESTAMP WHERE id = ?",
            (sesi,),
        )

    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    kartu = isi.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]

    assert kode_buat == 200
    assert kode == 200
    assert "Tinjau dan konfirmasi hasil" in kartu
    assert f'href="/sesi/{sesi}"' in kartu
    assert f'action="/siklus/{siswa_id}/buat"' not in kartu


def test_intervensi_memakai_materi_konkret_satu_form_aksi_dan_escape(server):
    s, siswa_id = server
    with s.buka() as kon:
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        _sesi_pemetaan(kon, siswa_id, putaran_id, 1)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 2)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 3, salah=False)

    kode, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    kartu = isi.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]
    materi = interventions.untuk_fokus(("deret_aritmetika", "H", None))

    assert kode == 200
    assert "Pelajari cara memeriksa hitungan" in kartu
    assert materi.instruksi_orang_tua in kartu
    assert materi.contoh_terbimbing in kartu
    assert "Salah hitung pada Deret aritmetika muncul di 2 sesi" in kartu
    assert f'action="/siklus/{siswa_id}/aksi"' in kartu
    assert 'name="aksi" value="intervensi_selesai"' in kartu
    assert f'name="putaran_id" value="{putaran_id}"' in kartu
    assert f'name="pendekatan_id" value="{materi.pendekatan_id}"' in kartu
    assert kartu.count('class="rencana-cta-utama-st"') == 1
    assert f'action="/siklus/{siswa_id}/buat"' not in kartu


def test_tunggu_dan_materi_tidak_tersedia_tidak_menawarkan_buat(monkeypatch):
    fokus = ("materi_<baru>", "K", "m&1")
    putaran = PutaranFokus(
        7,
        "P3",
        (StatusFokus(fokus, "perlu_dipelajari", jumlah_sesi=2),),
    )
    bukti = BuktiSiklus(9, "P3")
    tunggu = RencanaBelajar(
        "tunggu_evaluasi",
        "Evaluasi tersedia tiga hari setelah penguatan",
        putaran=putaran,
        kandidat=(fokus,),
        tersedia_pada=date(2026, 9, 12),
    )
    tidak_tersedia = interventions.MateriIntervensi(
        "konsep:<asing>",
        "Materi <belum> tersedia & perlu ditinjau.",
        "",
        "",
        tersedia=False,
    )
    intervensi = replace(tunggu, tindakan="intervensi", tersedia_pada=None)
    monkeypatch.setattr(
        learning_cycle_ui.interventions,
        "pilihan_untuk_fokus",
        lambda _: (tidak_tersedia,),
    )

    html_tunggu = learning_cycle_ui.render_rencana(tunggu, bukti, 9)
    html_materi = learning_cycle_ui.render_rencana(intervensi, bukti, 9)

    assert "12 September 2026" in html_tunggu
    assert "/siklus/9/buat" not in html_tunggu
    assert "Materi &lt;belum&gt; tersedia &amp; perlu ditinjau." in html_materi
    assert "materi_<baru>" not in html_materi
    assert "m&1" not in html_materi
    assert "/siklus/9/buat" not in html_materi
    assert "Tandai sudah dipelajari" not in html_materi


def test_progres_memakai_fokus_kandidat_dan_maintenance_tidak_kembali_nol():
    fokus_a = StatusFokus(("deret_aritmetika", "H", None), "bertahan", jumlah_sesi=2)
    fokus_b = StatusFokus(("soal_umur", "K", None), "perlu_diperkuat", jumlah_sesi=3)
    putaran = PutaranFokus(
        7,
        "P3",
        (fokus_a, fokus_b),
        (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)),
    )
    bukti = BuktiSiklus(9, "P3")
    rencana_fokus_b = RencanaBelajar(
        "intervensi", "uji", putaran=putaran, kandidat=(fokus_b.kunci,)
    )
    maintenance = RencanaBelajar(
        "mixed_maintenance",
        "Tidak ada fokus aktif",
        putaran=replace(putaran, fokus=()),
    )

    html_fokus = learning_cycle_ui.render_rencana(rencana_fokus_b, bukti, 9)
    html_maintenance = learning_cycle_ui.render_rencana(maintenance, bukti, 9)

    assert "Fokus: Perlu diperkuat" in html_fokus
    assert "Fokus: Bertahan" not in html_fokus
    assert "Pemetaan selesai — tidak ada fokus aktif" in html_maintenance
    assert "Pemetaan 0 dari 3" not in html_maintenance


def test_pengenalan_membuat_sesi_dulu_lalu_menandai_setelah_dikonfirmasi(server):
    s, siswa_id = server
    with s.buka() as kon:
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        _sesi_pemetaan(kon, siswa_id, putaran_id, 1, kode="T")
        _sesi_pemetaan(kon, siswa_id, putaran_id, 2, salah=False)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 3, salah=False)

    kode_awal, awal, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    kartu_awal = awal.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]
    assert kode_awal == 200
    assert "Kenalkan materi baru" in kartu_awal
    assert f'action="/siklus/{siswa_id}/buat"' in kartu_awal
    assert 'value="pengenalan_selesai"' not in kartu_awal

    kode_buat, _, _ = s.minta(
        f"/siklus/{siswa_id}/buat", auth=("guru", SANDI_GURU), data={}
    )
    with s.buka() as kon:
        sesi = kon.execute(
            "SELECT id FROM sesi WHERE siswa_id = ? AND tujuan = 'pengenalan'",
            (siswa_id,),
        ).fetchone()["id"]
        butir = database.isi_sesi(kon, sesi)[0]
        butir_id = int(butir["sesi_soal_id"])
        database.tandai_selesai(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, guru="guru", dilewati={butir_id})

    kode_sesudah, sesudah, _ = s.minta(
        f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU)
    )
    kartu_sesudah = sesudah.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]
    assert kode_buat == kode_sesudah == 200
    assert 'name="aksi" value="pengenalan_selesai"' in kartu_sesudah
    assert f'name="putaran_id" value="{putaran_id}"' in kartu_sesudah

    fokus = ("deret_aritmetika", "T", None)
    pendekatan = interventions.pilihan_untuk_fokus(fokus)[0].pendekatan_id
    kode_tandai, _, _ = s.minta(
        f"/siklus/{siswa_id}/aksi",
        auth=("guru", SANDI_GURU),
        data={
            "aksi": "pengenalan_selesai",
            "putaran_id": str(putaran_id),
            "template_id": fokus[0],
            "kode_intervensi": fokus[1],
            "malrule_id": "",
            "pendekatan_id": pendekatan,
        },
    )
    with s.buka() as kon:
        jumlah = kon.execute(
            "SELECT COUNT(*) FROM kejadian_belajar WHERE jenis = 'pengenalan_selesai'"
        ).fetchone()[0]
    assert kode_tandai == 200
    assert jumlah == 1


def test_pemblokir_tanpa_putaran_domain_memakai_tujuan_sesi_untuk_strip():
    from learning_cycle import SesiSiklus

    sesi = SesiSiklus(
        41,
        9,
        "P3",
        "penguatan",
        date(2026, 9, 9),
        selesai=None,
        putaran_id=7,
    )
    bukti = BuktiSiklus(9, "P3", sesi=(sesi,))
    rencana = RencanaBelajar(
        "lanjutkan_sesi",
        "Sesi terpandu aktif belum selesai",
        sesi_id=41,
    )

    isi = learning_cycle_ui.render_rencana(rencana, bukti, 9)

    assert "Penguatan mandiri" in isi
    assert 'class="tahap-rencana-st aktif" aria-current="step">Latihan' in isi
    assert "Pemetaan 0 dari 3" not in isi


def test_strip_tahap_dan_override_terpandu_terpisah_dari_latihan_bebas(server):
    s, siswa_id = server
    with s.buka() as kon:
        putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
        _sesi_pemetaan(kon, siswa_id, putaran_id, 1)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 2)
        _sesi_pemetaan(kon, siswa_id, putaran_id, 3, salah=False)

    _, isi, _ = s.minta(f"/anak/{siswa_id}?section=rencana", auth=("guru", SANDI_GURU))
    kartu = isi.split('<section class="kartu-rencana-st"', 1)[1].split('</section>', 1)[0]

    for label in ("Pemetaan", "Pelajari", "Latihan", "Evaluasi", "Cek kembali", "Lanjut"):
        assert label in kartu
    assert "Checkpoint" not in kartu
    assert '<details class="alur-rencana-jelas-st">' in kartu
    assert "Detail progres dan alur belajar" in kartu
    assert "Tahap sekarang: Pelajari" in kartu
    assert 'class="tahap-rencana-st selesai"' not in kartu
    assert kartu.index('class="tindakan-rencana-st"') < kartu.index('class="alur-rencana-jelas-st"')
    assert '<details class="ubah-fokus-st">' in kartu
    assert "Ubah fokus terpandu" in kartu
    assert "menutup konfigurasi lama" in kartu
    assert '<select name="template_id"' in kartu
    assert '>Deret aritmetika</option>' in kartu
    assert 'id="konfirmasi-dampak"' in kartu
    assert "required" in kartu
    assert f'action="/siklus/{siswa_id}/aksi"' in kartu
    assert 'name="aksi" value="ubah_fokus"' in kartu
    _, manual, _ = s.minta(f"/anak/{siswa_id}?section=latihan", auth=("guru", SANDI_GURU))
    assert "Latihan bebas tidak mengubah progres rencana terpandu" in manual


@pytest.mark.parametrize("kasus", ["materi_lain", "dibatalkan", "diinvalidasi"])
def test_pengenalan_tidak_memakai_konfirmasi_yang_tidak_relevan(kasus):
    from learning_cycle import SesiSiklus, KejadianSiklus

    fokus = ("deret_aritmetika", "T", None)
    target = ("soal_umur", "T", None) if kasus == "materi_lain" else fokus
    sesi = SesiSiklus(
        41, 9, "P3", "pengenalan", date(2026, 9, 1),
        selesai="2026-09-01", putaran_id=7, target_fokus=(target,),
        dikonfirmasi=None if kasus == "diinvalidasi" else "2026-09-01",
        dibatalkan="2026-09-02" if kasus == "dibatalkan" else None,
    )
    event = KejadianSiklus(1, "hasil_dikonfirmasi", date(2026, 9, 1), 7, 41, 1)
    bukti = BuktiSiklus(9, "P3", sesi=(sesi,), kejadian=(event,))
    rencana = RencanaBelajar(
        "pengenalan", "Materi baru", putaran=PutaranFokus(7, "P3", ()), kandidat=(fokus,),
    )
    isi = learning_cycle_ui.render_rencana(rencana, bukti, 9)
    assert 'action="/siklus/9/buat"' in isi
    assert 'value="pengenalan_selesai"' not in isi


@pytest.mark.parametrize("aksi", ["lanjutkan_sesi", "konfirmasi_hasil"])
def test_pemetaan_aktif_tidak_mengarang_progres_nol(aksi):
    from learning_cycle import SesiSiklus

    sesi = SesiSiklus(41, 9, "P3", "pemetaan", date(2026, 9, 2), putaran_id=7)
    bukti = BuktiSiklus(9, "P3", sesi=(sesi,))
    rencana = RencanaBelajar(aksi, "Sesi pemetaan aktif", sesi_id=41)
    isi = learning_cycle_ui.render_rencana(rencana, bukti, 9)
    assert "Tahap pemetaan" in isi
    assert "Pemetaan 0 dari 3" not in isi


def test_override_hanya_menawarkan_template_level_aktif():
    import re
    import topics

    fokus = ("deret_aritmetika", "H", None)
    rencana = RencanaBelajar("intervensi", "uji", putaran=PutaranFokus(
        7, "P3", (StatusFokus(fokus, "perlu_dipelajari"),),
    ))
    isi = learning_cycle_ui.render_rencana(rencana, BuktiSiklus(9, "P3"), 9)
    pilihan = isi.split('<select name="template_id"', 1)[1].split('</select>', 1)[0]
    aktual = set(re.findall(r'<option value="([^"]+)"', pilihan))
    sah = {tid for nama in topics.daftar_topik() if nama != "campuran"
           for tid in topics.ambil(nama).komposisi.get("P3", ())}
    assert aktual and aktual <= sah


def test_tunggu_pemetaan_memakai_copy_positif_dan_tanggal_reducer():
    putaran = PutaranFokus(
        7, "P3", (), (date(2026, 9, 10),),
    )
    rencana = RencanaBelajar(
        "tunggu_pemetaan",
        "Sesi pemetaan harus pada tanggal berbeda",
        putaran=putaran,
        tersedia_pada=date(2026, 9, 11),
    )

    isi = learning_cycle_ui.render_rencana(rencana, BuktiSiklus(9, "P3"), 9)

    assert '<h2 class="st" id="judul-rencana-belajar">Cukup untuk hari ini</h2>' in isi
    assert "Satu langkah pemetaan sudah selesai untuk hari ini." in isi
    assert "11 September 2026" in isi
    assert "Lanjutkan pemetaan besok" not in isi


def test_slot_bantuan_berada_di_dalam_kartu_dan_di_luar_form_tindakan():
    bukti = BuktiSiklus(9, "P3")
    from learning_cycle import rencana_berikutnya
    rencana = rencana_berikutnya(bukti, 9)
    dasar = learning_cycle_ui.render_rencana(rencana, bukti, 9)
    slot = '<aside id="bantuan-rencana">Bantuan sintetis</aside>'
    isi = learning_cycle_ui.render_rencana(
        rencana, bukti, 9, slot_bantuan=slot
    )
    assert dasar == learning_cycle_ui.render_rencana(rencana, bukti, 9)
    assert isi.count(slot) == 1
    assert isi.index(slot) < isi.rindex("</section>")
    assert not re.search(
        r"<form[^>]*>.*bantuan-rencana.*</form>", isi, re.DOTALL
    )


def test_css_kartu_rencana_berada_di_gaya_profil_dengan_disclosure_native():
    import style_stitch

    css = style_stitch.gaya_stitch()
    assert "/* Rencana belajar jelas — kartu */" in css
    assert "/* Rencana belajar jelas — kartu */" not in style_stitch.CSS_SESI
    blok = css.split("/* Rencana belajar jelas — kartu */", 1)[1].split(
        "/* Akhir rencana belajar jelas — kartu */", 1
    )[0]
    aturan_summary = blok.split(".alur-rencana-jelas-st > summary {", 1)[1].split("}", 1)[0]
    assert "display: list-item" in aturan_summary
    assert ".alur-rencana-jelas-st > summary:focus-visible" in blok
    assert "outline" in blok


def test_layout_vertikal_manual_meregang_di_desktop():
    css = Path(Path(__file__).resolve().parent.parent / "style_stitch.py").read_text(
        encoding="utf-8"
    )
    aturan = css.split('.anak-grid[data-rencana="vertikal"] {{', 1)[1].split("}}", 1)[0]
    assert "align-items: stretch" in aturan
    assert "width: 100%" in aturan
