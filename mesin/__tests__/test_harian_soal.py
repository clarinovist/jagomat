"""Latihan Harian: PG 4 opsi murni, tingkat, audit jenis tersisih, dan rakitan sesi (tanpa DB, data sintetis)."""
import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

import database
import generator
import harian_pg
import harian_rakit
import harian_tingkat as ht
import multiple_choice
import visual_contract

AKAR_MESIN = str(Path(__file__).resolve().parent.parent)


@pytest.fixture(autouse=True)
def palang_rilis_terbuka(monkeypatch, tmp_path):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))


# --- PG 4 opsi sah ---------------------------------------------------------------------------

def test_pg_empat_opsi_berbeda_dengan_tepat_satu_kunci():
    soal = harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)

    assert len(soal.opsi) == 4 == len(set(soal.opsi))
    assert 0 <= soal.kunci_indeks < 4
    asal = generator.buat_soal("tambah_dasar", 7001, "P2", "bilangan-dasar")
    assert soal.opsi[soal.kunci_indeks] == asal.kunci
    assert soal.tanda_tangan == asal.tanda_tangan
    assert soal.pembahasan.strip()


def test_pg_menjalankan_validasi_semantik_keunikan(monkeypatch):
    dipanggil = []
    asli = multiple_choice.validasi_kebenaran
    monkeypatch.setattr(multiple_choice, "validasi_kebenaran", lambda *a: (dipanggil.append(a), asli(*a))[1])

    harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)

    assert len(dipanggil) == 1 and len(dipanggil[0][0].opsi) == 4


def test_pg_opsi_setara_secara_matematis_ditolak(monkeypatch):
    """Dua pengecoh bernilai sama ('7' dan '7.0') tidak boleh lolos sebagai dua opsi."""
    monkeypatch.setattr(harian_pg.choice_generation, "kandidat", lambda soal, n=None: ("empat-v1", "angka", ("7.0", "8", "9")))
    asal = generator.buat_soal("tambah_dasar", 7001, "P2", "bilangan-dasar")
    monkeypatch.setattr(generator, "buat_soal", lambda *a, **k: dataclasses.replace(asal, kunci="7"))

    with pytest.raises(harian_pg.SoalTidakLayak):
        harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)


def test_pg_deterministik_per_seed_dan_beda_antar_seed():
    a = harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)

    assert a == harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)
    assert a != harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7002)


def test_pg_menyimpan_snapshot_penyajian_yang_sah():
    soal = harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)

    penyajian = visual_contract.deserialisasi_penyajian(soal.penyajian_json)

    assert penyajian.teks_soal.strip()
    assert len(penyajian.fingerprint_penyajian) == 64


def test_pg_tertanam_lima_opsi_dikeluarkan():
    with pytest.raises(harian_pg.SoalTidakLayak) as galat:
        harian_pg.buat_soal_pg("geometri-ruang", "jaring_jaring", "P6", 7001)
    assert galat.value.alasan == harian_pg.ALASAN_LIMA_OPSI


def test_pg_pengecoh_kurang_dikeluarkan():
    """bandingkan_bilangan hanya punya tiga simbol: empat opsi mustahil, tidak ditambal."""
    with pytest.raises(harian_pg.SoalTidakLayak) as galat:
        harian_pg.buat_soal_pg("bilangan-dasar", "bandingkan_bilangan", "P1", 7001)
    assert galat.value.alasan == harian_pg.ALASAN_PENGECOH_KURANG


def test_pg_tanpa_pembahasan_dikeluarkan(monkeypatch):
    asal = generator.buat_soal("tambah_dasar", 7001, "P2", "bilangan-dasar")
    monkeypatch.setattr(generator, "buat_soal", lambda *a, **k: dataclasses.replace(asal, pembahasan="  "))

    with pytest.raises(harian_pg.SoalTidakLayak) as galat:
        harian_pg.buat_soal_pg("bilangan-dasar", "tambah_dasar", "P2", 7001)
    assert galat.value.alasan == harian_pg.ALASAN_TANPA_PEMBAHASAN


def test_audit_template_melaporkan_lolos_dan_alasan():
    bagus = harian_pg.audit_template("bilangan-dasar", "tambah_dasar", "P2")
    jaring = harian_pg.audit_template("geometri-ruang", "jaring_jaring", "P6")

    assert bagus.layak and bagus.lolos >= 0.2 * bagus.jumlah
    assert not jaring.layak and dict(jaring.alasan) == {harian_pg.ALASAN_LIMA_OPSI: harian_pg.SAMPEL_AUDIT}


# --- tingkat -----------------------------------------------------------------------------------

def test_delapan_tingkat_dan_judul_bukan_kelas():
    assert ht.KODE_SAH == ("t1", "t2", "t3", "t4", "t5", "t6", "osn-pemula", "osn-lanjut")
    assert all("kelas" not in (t.judul + t.ringkas).lower() for t in ht.DAFTAR_TINGKAT)


def test_tingkat_kode_tidak_sah_keyerror():
    for buruk in ("t7", "", "T1", None, 3, "osn"):
        with pytest.raises(KeyError):
            ht.ambil_tingkat(buruk)


@pytest.mark.parametrize("kode,level", [("t1", "P1"), ("t3", "P3"), ("t6", "P6")])
def test_tingkat_kelas_memakai_level_kelasnya_dan_bab_buku(kode, level):
    sumber = ht.sumber_dibuka(kode)

    assert sumber and all(r[2] == level for s in sumber for r in s.refs)
    assert all(s.label[0].isdigit() for s in sumber)


def test_tingkat_osn_memakai_level_pemula_p3_p4_dan_lanjut_p5_p6():
    pemula = {r[2] for s in ht.sumber_dibuka("osn-pemula") for r in s.refs}
    lanjut = {r[2] for s in ht.sumber_dibuka("osn-lanjut") for r in s.refs}

    assert pemula and pemula <= {"P3", "P4"}
    assert lanjut and lanjut <= {"P5", "P6"}


def test_grup_osn_tidak_bertumpuk_dengan_bab_kurikulum():
    import kurikulum_kelas as kk
    import kurikulum_katalog as kat
    terpakai = kk.grup_terpakai()
    for kode in ("osn-pemula", "osn-lanjut"):
        for s in ht.sumber_dibuka(kode):
            topik = next(e for e in kat.KATALOG if s.label.startswith(ht.topics.ambil(e.topik_id).nama + ":"))
            nama = s.label.split(": ", 1)[1]
            grup = next(g for g in topik.grup if g[1] == nama)
            assert (topik.topik_id, grup[0]) not in terpakai


def test_palang_rilis_tertutup_mengeluarkan_template_dan_dicatat_tersisih(monkeypatch):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "0")

    labels = {s.label for s in ht.sumber_dibuka("t3")}
    lap = ht.audit_tingkat("t3")

    assert not any(l.startswith("2. ") for l in labels)  # bab 2 hanya berisi jenis Bilangan Sekolah
    assert any(t.alasan == "tertutup" and t.template_id == "kalimat_matematika" for t in lap.tersisih)
    assert any(l.startswith("2. ") for l in lap.sumber_kosong)


def test_audit_tingkat_melaporkan_jenis_tersisih_dan_sumber_kosong():
    t1, t6 = ht.audit_tingkat("t1"), ht.audit_tingkat("t6")

    assert any(t.template_id == "bandingkan_bilangan" and t.level == "P1" for t in t1.tersisih)
    assert any(l.startswith("3. Pengurangan") for l in t1.sumber_kosong)  # satu-satunya pelatih bab ini tersisih
    assert any(t.template_id == "jaring_jaring" and "lima_opsi" in t.alasan for t in t6.tersisih)
    assert "Tingkat 1" in ht.laporan_audit() and "bandingkan_bilangan" in ht.laporan_audit()


def test_semua_tingkat_punya_sumber_layak():
    for kode in ht.KODE_SAH:
        assert ht.sumber_layak(kode), kode


# --- saran tingkat -----------------------------------------------------------------------------

@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        yield k


def _anak(kon, kelas):
    sid = kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES ('Anak Uji', 'P3', 'guru-uji')").lastrowid
    if kelas is not None:
        kon.execute("INSERT INTO profil_belajar(siswa_id, kelas_sekolah, revisi) VALUES (?, ?, 1)", (sid, kelas))
    return sid


def test_saran_tingkat_dari_profil_kelas(kon):
    assert ht.saran_tingkat(kon, _anak(kon, 4)) == "t4"


def test_saran_tingkat_kosong_bila_profil_belum_diisi(kon):
    assert ht.saran_tingkat(kon, _anak(kon, None)) is None
    assert ht.saran_tingkat(kon, 99999) is None


# --- rakitan sesi ------------------------------------------------------------------------------

@pytest.mark.parametrize("kode", ht.KODE_SAH)
def test_rakitan_sepuluh_soal_unik_dan_pg_empat_opsi(kode):
    sesi = harian_rakit.rakit_sesi(kode, 4242)

    assert [s.nomor for s in sesi] == list(range(1, 11))
    assert len({s.soal.tanda_tangan for s in sesi}) == 10
    for s in sesi:
        assert len(s.soal.opsi) == 4 == len(set(s.soal.opsi))
        assert 0 <= s.soal.kunci_indeks < 4 and s.soal.pembahasan.strip()


def test_rakitan_ulangan_tingkat_bawah_maks_dua_dan_hanya_bila_ada_bawah():
    assert sum(s.ulangan for s in harian_rakit.rakit_sesi("t4", 11)) == 2
    assert all(s.soal.level == "P3" for s in harian_rakit.rakit_sesi("t4", 11) if s.ulangan)
    assert all(s.soal.level == "P4" for s in harian_rakit.rakit_sesi("t4", 11) if not s.ulangan)
    assert not any(s.ulangan for s in harian_rakit.rakit_sesi("t1", 11))
    assert not any(s.ulangan for s in harian_rakit.rakit_sesi("osn-pemula", 11))
    lanjut = harian_rakit.rakit_sesi("osn-lanjut", 11)
    assert sum(s.ulangan for s in lanjut) == 2 and all(s.soal.level in ("P3", "P4") for s in lanjut if s.ulangan)


def test_rakitan_campur_beberapa_bab():
    assert len({s.sumber for s in harian_rakit.rakit_sesi("t5", 77)}) >= 4


@pytest.mark.parametrize("kode", ["t2", "osn-pemula", "osn-lanjut"])
def test_rakitan_osn_menghasilkan_soal_level_tingkatnya(kode):
    tingkat = ht.ambil_tingkat(kode)
    levels = {s.soal.level for s in harian_rakit.rakit_sesi(kode, 5) if not s.ulangan}

    assert levels and levels <= set(tingkat.level)


def test_rakitan_deterministik_per_seed():
    a = harian_rakit.rakit_sesi("t3", 31337)

    assert a == harian_rakit.rakit_sesi("t3", 31337)
    assert a != harian_rakit.rakit_sesi("t3", 31338)


def test_rakitan_sama_lintas_proses_dengan_pythonhashseed_berbeda():
    kode = ("import sys; sys.path.insert(0, %r); import harian_rakit as r; "
            "print([(s.soal.tanda_tangan, s.soal.opsi, s.soal.kunci_indeks) for s in r.rakit_sesi('t5', 2024)])" % AKAR_MESIN)
    env = dict(os.environ, OSN_BILANGAN_SEKOLAH="1", OSN_DASAR_LENGKAP="1", SAKELAR_BERKAS_DB="/tidak/ada.db")

    hasil = {subprocess.run([sys.executable, "-c", kode], env=dict(env, PYTHONHASHSEED=h), capture_output=True,
                            text=True, timeout=120, check=True).stdout for h in ("0", "12345")}

    assert len(hasil) == 1


@pytest.mark.parametrize("seed", [0, -1, 2 ** 31, "5", 1.5, True, None])
def test_rakitan_menolak_seed_tak_sah(seed):
    with pytest.raises(ValueError):
        harian_rakit.rakit_sesi("t1", seed)


def test_rakitan_tingkat_tanpa_soal_layak_ditolak(monkeypatch):
    monkeypatch.setattr(ht, "sumber_layak", lambda kode: ())

    with pytest.raises(harian_rakit.TingkatKosong):
        harian_rakit.rakit_sesi("t1", 5)


def test_rakitan_kode_tingkat_tak_dikenal_keyerror():
    with pytest.raises(KeyError):
        harian_rakit.rakit_sesi("t9", 5)
