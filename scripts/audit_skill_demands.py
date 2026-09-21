"""Audit sintetis tuntutan existing; tidak membuka DB atau menilai kemampuan anak.

Jalankan dari root dengan mesin/.venv/bin/python scripts/audit_skill_demands.py.
Output JSON ke stdout agar caller memilih lokasi privat. Rentang/varian hanya
hasil sampel, bukan klaim seluruh cabang, prasyarat, atau kesetaraan kemampuan.
"""
import argparse
import hashlib
import inspect
import json
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
if str(AKAR / "mesin") not in sys.path:
    sys.path.insert(0, str(AKAR / "mesin"))

import generator
import interventions
import mastery_catalog
import rumus
import topics
from generator_version import versi_generator_baru
from question_context import daftar_konteks
from render import _badan_soal
from skill_demand_draft import petakan_draft, VERSI_RUBRIK
from topic_combinatorics_visual import proyeksi_kombinatorik
from topic_measurement_visual import proyeksi_pengukuran
from topic_number_patterns_visual import proyeksi_pola
from topic_plane_geometry_visual import proyeksi_geometri_datar
from topic_solid_geometry_visual import proyeksi_geometri_ruang
from topic_statistics_visual import proyeksi_statistika
from visual_contract import buat_penyajian
from visual_renderer import render_pertanyaan

PROYEKTOR = (proyeksi_pola, proyeksi_geometri_datar, proyeksi_geometri_ruang,
             proyeksi_kombinatorik, proyeksi_pengukuran, proyeksi_statistika)


def _json(isi):
    return json.dumps(isi, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sidik(isi):
    return hashlib.sha256(_json(isi).encode()).hexdigest()


def _sumber(fungsi):
    path = Path(inspect.getsourcefile(fungsi)).resolve()
    return {"berkas": str(path.relative_to(AKAR)),
            "baris": inspect.getsourcelines(fungsi)[1],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _daun(nilai, jalur=""):
    """Pisahkan bilangan dari kategori; teks latar bukan otomatis variasi tugas."""
    if type(nilai) is dict:
        for nama, isi in sorted(nilai.items()):
            yield from _daun(isi, jalur + "." + nama if jalur else nama)
    elif type(nilai) in (list, tuple):
        for isi in nilai:
            yield from _daun(isi, jalur + "[]")
    else:
        yield jalur, nilai


def audit(jumlah_seed=25):
    """Semua pasangan komposisi aktual, tanpa profil anak atau urutan kemampuan."""
    if type(jumlah_seed) is not int or not 1 <= jumlah_seed <= 500:
        raise ValueError("jumlah seed harus 1–500")
    baris = []
    for konteks in daftar_konteks():
        paket = topics.ambil(konteks.topik_id)
        fungsi = paket.templates[konteks.template_id]
        target = [konteks.topik_id + "." + kode
                  for kode, _, pola in mastery_catalog.KELOMPOK[konteks.topik_id]
                  if konteks.template_id in pola]
        if len(target) != 1:
            raise ValueError("pola tidak memiliki satu target katalog warisan")
        angka, kategori, varian, bentuk = {}, {}, set(), set()
        contoh, malrule, mode, tanda, render, tuntutan = {}, set(), set(), [], [], set()
        tanpa_k = 0
        for seed in range(jumlah_seed):
            soal = generator.buat_soal(konteks.template_id, seed, konteks.profil_parameter, paket.id)
            if soal.level != konteks.profil_parameter:
                raise ValueError("generator mengganti profil saat audit")
            tanda.append(soal.tanda_tangan)
            render.append(_badan_soal(soal, paket))
            varian_soal = soal.parameter.get("varian")
            if varian_soal is not None:
                varian.add(_json(varian_soal))
            bentuk.add(tuple(sorted(soal.parameter)))
            contoh.setdefault(_json(varian_soal), {
                "seed": seed, "parameter": soal.parameter, "teks": soal.teks,
                "kunci": soal.kunci, "pembahasan": soal.pembahasan,
            })
            for nama, nilai in _daun(soal.parameter):
                if type(nilai) in (int, float):
                    rentang = angka.setdefault(nama, [nilai, nilai])
                    rentang[0], rentang[1] = min(rentang[0], nilai), max(rentang[1], nilai)
                else:
                    kategori.setdefault(nama, set()).add(_json(nilai))
            malrule.update((m.kode, m.id) for m in soal.malrule)
            tanpa_k += not any(m.kode == "K" for m in soal.malrule)
            mode.add("teks-v1")
            draft = petakan_draft(soal.template_id, soal.parameter, "teks-v1")
            if draft:
                tuntutan.add(draft.id)
            for proyektor in PROYEKTOR:
                visual = proyektor(soal.template_id, soal.parameter)
                if visual is None:
                    continue
                teks, descriptor = visual
                representasi = "{}-v{}".format(descriptor.jenis, descriptor.versi)
                mode.add(representasi)
                penyajian = buat_penyajian(
                    template_id=soal.template_id, level=soal.level, parameter=soal.parameter,
                    teks_soal=teks, bagian_soal=soal.bagian, tantangan_soal=soal.tantangan,
                    minta_restatement=soal.minta_restatement, asal_teks="bawaan",
                    status_visual="siap", mode_representasi=representasi, descriptor=descriptor,
                )
                render.append(render_pertanyaan(penyajian, namespace="audit"))
        kartu = rumus.kartu_untuk(konteks.template_id)
        pendekatan = []
        for kode, identitas in sorted(malrule):
            if kode != "K":
                continue
            materi = interventions.pilihan_untuk_fokus((konteks.template_id, kode, identitas))
            pendekatan.append({"malrule_id": identitas, "pendekatan": [
                {"id": m.pendekatan_id, "tersedia": m.tersedia,
                 "contoh": m.contoh_terbimbing, "bantuan_visual": m.bantuan is not None}
                for m in materi]})
        baris.append({
            "konteks_id": konteks.id, "topik_id": paket.id, "target_warisan": target[0],
            "template_id": konteks.template_id, "profil_parameter": konteks.profil_parameter,
            "deskripsi_source": inspect.getdoc(fungsi), "sumber_template": _sumber(fungsi),
            "sumber_parameter": _sumber(paket.parameter_untuk),
            "jumlah_seed": jumlah_seed, "varian_teramati": sorted(varian),
            "bentuk_parameter": sorted(bentuk), "rentang_angka_sampel": angka,
            "kategori_parameter_sampel": {k: sorted(v) for k, v in sorted(kategori.items())},
            "representasi_tersedia_sampel": sorted(mode), "contoh_per_varian": list(contoh.values()),
            "tuntutan_draft": sorted(tuntutan),
            "status_review_penalaran": "usulan pilot" if tuntutan else "belum direview per tuntutan",
            "prasyarat_terverifikasi": None,
            "kartu_rumus": None if kartu is None else {"judul": kartu.judul, "inti": kartu.inti,
                                                       "contoh": kartu.contoh},
            "intervensi_k_tersedia": pendekatan,
            "kecocokan_intervensi_per_varian": "belum disahkan",
            "jumlah_tanpa_malrule_k": tanpa_k,
            "signature_sha256": _sidik(tanda), "render_sha256": _sidik(render),
        })
    return {"versi_audit": 1, "versi_generator": versi_generator_baru(), "versi_rubrik_draft": VERSI_RUBRIK,
            "batas": ["Sampel bukan seluruh cabang", "Kategori teks bisa hanya latar cerita",
                      "Tersedia bukan cocok untuk setiap tuntutan", "Profil bukan tahap kemampuan",
                      "Inventaris bukan penyebut target wajib", "Tidak ada kebijakan aktif"],
            "jumlah_pola": len({b["template_id"] for b in baris}),
            "jumlah_pasangan": len(baris), "jumlah_soal": len(baris) * jumlah_seed,
            "konteks": baris}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jumlah-seed", type=int, default=25)
    argumen = parser.parse_args()
    print(json.dumps(audit(argumen.jumlah_seed), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
