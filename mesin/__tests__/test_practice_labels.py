"""Nama tipe soal konsisten dari usulan sampai pilihan latihan ulang."""

from __future__ import annotations

import html
import json
import re

import pytest

import assistant_view
import database
import learning_cycle_ui
import reports
import rumus
import teacher_pages
import topics


@pytest.mark.parametrize("template_id", sorted(topics.registri()))
def test_nama_usulan_sama_dengan_pilihan_dan_laporan(template_id):
    paket = topics.ambil(topics.pemilik_template(template_id))
    level = next(lv for lv, isi in paket.komposisi.items() if template_id in isi)
    ringkasan = assistant_view.ringkasan_usulan(json.dumps({
        "topik_id": paket.id, "template_ids": [template_id],
        "level": level, "jumlah_soal": 10,
    }))
    nama = ringkasan["materi"][0][0]
    assert nama == teacher_pages._nama_template(template_id)
    assert nama == learning_cycle_ui._nama_template(template_id)
    assert nama == reports._nama_tipe_soal(template_id)
    pilihan = teacher_pages._form_remedial(
        [{"template_id": template_id, "kode": "K", "kali_salah": 1,
          "direkomendasikan": True}],
        1, judul="Latihan ulang", penjelasan="Pilih tipe soal.",
    )
    assert f'<b>{html.escape(nama)}</b>' in pilihan
    assert f'name="template_id" value="{template_id}" checked' in pilihan


def test_tiga_pola_berbeda_dan_variasi_satu_konsep_tidak_disatukan():
    template_ids = ["deret_aritmetika", "siklus_huruf", "deret_geometri",
                    "deret_terbalik_geometri"]
    ringkasan = assistant_view.ringkasan_usulan(json.dumps({
        "topik_id": "pola-bilangan", "template_ids": template_ids,
        "level": "P3", "jumlah_soal": 10,
    }))
    assert ringkasan["materi"] == (
        ("Deret aritmetika", 3, "deret_aritmetika"),
        ("Siklus huruf", 3, "siklus_huruf"),
        ("Barisan geometri", 2, "deret_geometri"),
        ("Barisan geometri — mencari posisi", 2, "deret_terbalik_geometri"),
    )
    assert rumus.kartu_untuk("deret_geometri").judul == "Barisan geometri"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    lokasi = tmp_path / "label-sintetis.db"
    database.siapkan(lokasi)
    monkeypatch.setattr(database, "BAWAAN", lokasi)
    return lokasi


def test_badge_soal_dan_remedial_geometri_sama_dengan_usulan(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")
        template_ids = ("deret_aritmetika", "siklus_huruf", "deret_geometri")
        sesi_id = database.buat_sesi_dari_urutan(
            kon, siswa_id, seed=27, urutan=template_ids, level="P3",
            topik=topics.ambil("pola-bilangan"),
        )
        for butir in database.isi_sesi(kon, sesi_id):
            salah = butir["template_id"] == "deret_geometri"
            jawaban_id = database.simpan_jawaban(
                kon, butir["sesi_soal_id"],
                jawaban="999999" if salah else butir["kunci"], cara="hitung",
            )
            database.simpan_diagnosis(
                kon, jawaban_id, benar=not salah,
                kode_usulan="K" if salah else None, kode_final="K" if salah else None,
                alasan="Catatan sintetis",
            )
        database.tandai_selesai(kon, sesi_id)
        kon.execute("UPDATE sesi SET direview = datetime('now') WHERE id = ?", (sesi_id,))
        halaman = teacher_pages.halaman_sesi_stitch(kon, sesi_id).decode()
        badge = re.findall(r'<span class="koreksi-tipe-st">(.*?)</span>', halaman)
        assert badge == [teacher_pages._nama_template(tid) for tid in template_ids]
        assert "Barisan geometri" in badge
        panel = halaman.split('<section class="remedial-st">', 1)[1].split('</section>', 1)[0]
        assert '<b>Barisan geometri</b>' in panel
        assert 'value="deret_geometri"' in panel
        assert 'value="deret_aritmetika"' not in panel
        assert 'value="siklus_huruf"' not in panel
        ulang = database.buat_sesi_remedial(
            kon, siswa_id, seed=28, jumlah_soal=10,
            template_ids=["deret_geometri"], sumber_sesi_id=sesi_id,
        )
        assert [b["template_id"] for b in database.isi_sesi(kon, ulang)] == ["deret_geometri"] * 10


def test_latihan_serupa_memakai_nama_yang_sama(monkeypatch):
    import similar_practice
    monkeypatch.setattr(similar_practice, "kandidat_sesi", lambda *_: [
        {"template_id": "deret_geometri", "nomor": [3], "sesi_soal_id": 3},
    ])
    panel = teacher_pages._blok_latihan_serupa(None, 1)
    assert '<b>Barisan geometri</b>' in panel


def test_fallback_label_warisan_tetap_terbaca_dan_di_escape():
    template_id = 'pola_<lama>-asing'
    nama = teacher_pages._nama_template(template_id)
    assert nama == reports._nama_tipe_soal(template_id)
    assert nama == learning_cycle_ui._nama_template(template_id)
    panel = teacher_pages._form_remedial(
        [{"template_id": template_id, "kode": "H", "kali_salah": 1,
          "direkomendasikan": False}],
        1, judul="Latihan ulang", penjelasan="Pilih tipe soal.",
    )
    assert f'<b>{html.escape(nama)}</b>' in panel
    assert '<lama>' not in panel
