"""Layanan aplikasi untuk wawancara, matriks, dan ekspor riset."""
from __future__ import annotations

import csv
import io
import json
from typing import Iterable, Optional

import research_instrument as instrumen
import research_store as store


KOLOM_MATRIKS = (
    ("Q1", "Konteks/pemicu"),
    ("Q3", "Kesulitan utama"),
    ("Q4", "Solusi sekarang"),
    ("Q5", "Alasan/fungsi"),
    ("Q6", "Hasil"),
    ("Q7", "Masalah tersisa"),
    ("Q8", "Frekuensi"),
    ("Q9", "Bantuan biasa"),
)


def dashboard(path=None, *, status="", halaman=1, sekarang=None) -> dict:
    return {
        "ringkasan": store.ringkasan(path, sekarang=sekarang),
        "daftar": store.daftar_wawancara(path, status=status, halaman=halaman),
    }


def detail(path, identitas):
    return store.detail_wawancara(path, identitas)


def pertanyaan_berikutnya(detail_wawancara, kode: str) -> Optional[str]:
    daftar = [item["kode"] for item in detail_wawancara["instrumen"]["pertanyaan"]]
    try:
        indeks = daftar.index(kode)
    except ValueError:
        raise LookupError("pertanyaan tidak tersedia") from None
    return daftar[indeks + 1] if indeks + 1 < len(daftar) else None


def pertanyaan_sebelumnya(detail_wawancara, kode: str) -> Optional[str]:
    daftar = [item["kode"] for item in detail_wawancara["instrumen"]["pertanyaan"]]
    try:
        indeks = daftar.index(kode)
    except ValueError:
        raise LookupError("pertanyaan tidak tersedia") from None
    return daftar[indeks - 1] if indeks > 0 else None


def matriks(path=None) -> dict:
    wawancara = store.wawancara_final(path)
    denominator = {}
    hitungan = {}
    for item in wawancara:
        for kode_q, jawaban in item["jawaban"].items():
            if jawaban["status_jawaban"] != "dijawab":
                continue
            denominator[kode_q] = denominator.get(kode_q, 0) + 1
            for label in dict.fromkeys(jawaban.get("kode_label", ())):
                hitungan[(kode_q, label)] = hitungan.get((kode_q, label), 0) + 1
    return {
        "wawancara": wawancara,
        "denominator": denominator,
        "hitungan": hitungan,
        "kolom": KOLOM_MATRIKS,
    }


def _netral_csv(nilai) -> str:
    teks = "" if nilai is None else str(nilai)
    if teks.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + teks
    return teks


def _jawaban(item, kode_q):
    return item["jawaban"].get(kode_q, {})


def ekspor_csv(path=None) -> bytes:
    data = store.wawancara_final(path)
    tujuan = io.StringIO(newline="")
    kolom = ["kode_responden", "versi_instrumen", "tanggal", "sumber"]
    for kode_q, label in KOLOM_MATRIKS:
        kolom.extend((kode_q + "_status", kode_q + "_kode", kode_q + "_jawaban", kode_q + "_catatan"))
    kolom.append("kutipan_terpilih")
    writer = csv.writer(tujuan, lineterminator="\r\n")
    writer.writerow(kolom)
    for item in data:
        baris = [item["kode_responden"], item["kode_versi"], item["diwawancarai"], item["sumber"]]
        kutipan = []
        for kode_q, _label in KOLOM_MATRIKS:
            jaw = _jawaban(item, kode_q)
            if not jaw:
                baris.extend(("", "", "", ""))
                continue
            baris.extend((
                jaw["status_jawaban"],
                " | ".join(jaw.get("kode_label", ())),
                jaw["jawaban_responden"],
                jaw["catatan_interviewer"],
            ))
            if jaw["kutipan_terpilih"] and jaw["kutipan_responden"]:
                kutipan.append("%s: %s" % (kode_q, jaw["kutipan_responden"]))
        baris.append(" | ".join(kutipan))
        writer.writerow([_netral_csv(nilai) for nilai in baris])
    return tujuan.getvalue().encode("utf-8-sig")


def ekspor_json(path=None) -> bytes:
    data = []
    for item in store.wawancara_final(path):
        data.append({
            "kode_responden": item["kode_responden"],
            "versi_instrumen": item["kode_versi"],
            "diwawancarai": item["diwawancarai"],
            "sumber": item["sumber"],
            "jawaban": {
                kode: {
                    "status": jaw["status_jawaban"],
                    "jawaban_responden": jaw["jawaban_responden"],
                    "kutipan_terpilih": jaw["kutipan_responden"] if jaw["kutipan_terpilih"] else "",
                    "catatan_interviewer": jaw["catatan_interviewer"],
                    "kode": list(jaw.get("kode_label", ())),
                    "klarifikasi": jaw["status_klarifikasi"],
                }
                for kode, jaw in item["jawaban"].items()
            },
        })
    dokumen = {
        "versi": 1,
        "batas": "Studi eksploratif; tidak mewakili seluruh orang tua Indonesia dan bukan bukti PMF.",
        "jumlah": len(data),
        "wawancara": data,
    }
    return (json.dumps(dokumen, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
