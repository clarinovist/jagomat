"""Identitas A4: tanda tangan lembar & soal pasca-parameter-JSON.

Snapshot ini dibangkitkan dari kode pasca-A4 (28 Aug 2026). Pergantian dari
snapshot pra-refactor dilakukan DENGAN VERIFIKASI OTOMATIS: snapshot lama
dikonversi format pola (string -> list, satu-satunya perubahan yang direncanakan
A4) lalu dibandingkan entri per entri — 84/84 cocok. Perilaku generator tidak
berubah; yang berubah hanya bentuk parameter pola di tanda_tangan.

Kalau test ini gagal tanpa perubahan template, perilaku berubah — cari kenapa,
jangan perbarui angkanya.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator import buat_lembar, buat_soal  # noqa: E402
from templates import LEVEL_TINGKAT  # noqa: E402
from topics import paket_bawaan  # noqa: E402

EMAS = {
 "lembar": {
  "P3|1": "P3|deret_aritmetika(awal=4,beda=7,n_minta=2,n_tampil=4)|P3|deret_aritmetika_turun(awal=21,beda=3,n_tampil=5)|P3|deret_geometri(awal=2,n_tampil=4,rasio=3)|P3|deret_bertingkat(awal=7,beda_awal=2,kenaikan=1,n_tampil=6)|P3|siklus_huruf(pola=['A', 'D', 'C', 'D'],posisi=32)|P3|siklus_warna(pola=['hijau', 'hijau', 'kuning', 'merah', 'putih'],posisi=20)|P3|korek_api(awal=7,gambar_ke=14,tambah=2)|P3|titik_segitiga(gambar_ke=11)|P3|deret_terbalik_aritmetika(awal=3,beda=6,posisi_target=15)|P3|deret_terbalik_geometri(awal=3,posisi_target=6,rasio=2)|P3|siklus_hari(hari_awal=Minggu,tambah=30)|P3|jumlah_siklus(n_angka=34,pola=[5, 2, 4, 1])",
  "P3|2026": "P3|deret_aritmetika(awal=3,beda=5,n_minta=2,n_tampil=4)|P3|deret_aritmetika_turun(awal=49,beda=7,n_tampil=4)|P3|deret_geometri(awal=3,n_tampil=4,rasio=3)|P3|deret_bertingkat(awal=9,beda_awal=4,kenaikan=3,n_tampil=6)|P3|siklus_huruf(pola=['A', 'B', 'A', 'D'],posisi=18)|P3|siklus_warna(pola=['biru', 'merah', 'ungu', 'ungu'],posisi=26)|P3|korek_api(awal=6,gambar_ke=13,tambah=3)|P3|titik_segitiga(gambar_ke=8)|P3|deret_terbalik_aritmetika(awal=8,beda=6,posisi_target=15)|P3|deret_terbalik_geometri(awal=3,posisi_target=3,rasio=3)|P3|siklus_hari(hari_awal=Senin,tambah=40)|P3|jumlah_siklus(n_angka=23,pola=[3, 4, 1, 2])",
  "P3|42": "P3|deret_aritmetika(awal=12,beda=3,n_minta=2,n_tampil=4)|P3|deret_aritmetika_turun(awal=24,beda=3,n_tampil=5)|P3|deret_geometri(awal=2,n_tampil=3,rasio=2)|P3|deret_bertingkat(awal=9,beda_awal=1,kenaikan=3,n_tampil=6)|P3|siklus_huruf(pola=['A', 'B', 'C', 'D'],posisi=20)|P3|siklus_warna(pola=['ungu', 'putih', 'biru', 'ungu'],posisi=38)|P3|korek_api(awal=5,gambar_ke=20,tambah=2)|P3|titik_segitiga(gambar_ke=12)|P3|deret_terbalik_aritmetika(awal=3,beda=6,posisi_target=12)|P3|deret_terbalik_geometri(awal=3,posisi_target=4,rasio=2)|P3|siklus_hari(hari_awal=Minggu,tambah=23)|P3|jumlah_siklus(n_angka=32,pola=[1, 4, 5])",
  "P3|7": "P3|deret_aritmetika(awal=7,beda=4,n_minta=2,n_tampil=4)|P3|deret_aritmetika_turun(awal=36,beda=6,n_tampil=4)|P3|deret_geometri(awal=1,n_tampil=4,rasio=3)|P3|deret_bertingkat(awal=1,beda_awal=2,kenaikan=1,n_tampil=5)|P3|siklus_huruf(pola=['D', 'B', 'C', 'D', 'E'],posisi=17)|P3|siklus_warna(pola=['kuning', 'putih', 'merah', 'kuning'],posisi=38)|P3|korek_api(awal=7,gambar_ke=8,tambah=3)|P3|titik_segitiga(gambar_ke=7)|P3|deret_terbalik_aritmetika(awal=2,beda=4,posisi_target=12)|P3|deret_terbalik_geometri(awal=6,posisi_target=4,rasio=2)|P3|siklus_hari(hari_awal=Senin,tambah=40)|P3|jumlah_siklus(n_angka=41,pola=[5, 2, 1, 3])",
  "P3|99999": "P3|deret_aritmetika(awal=3,beda=5,n_minta=2,n_tampil=4)|P3|deret_aritmetika_turun(awal=56,beda=7,n_tampil=4)|P3|deret_geometri(awal=1,n_tampil=4,rasio=3)|P3|deret_bertingkat(awal=7,beda_awal=2,kenaikan=1,n_tampil=6)|P3|siklus_huruf(pola=['A', 'B', 'E', 'D', 'E'],posisi=30)|P3|siklus_warna(pola=['ungu', 'hijau', 'kuning', 'kuning'],posisi=22)|P3|korek_api(awal=4,gambar_ke=12,tambah=2)|P3|titik_segitiga(gambar_ke=10)|P3|deret_terbalik_aritmetika(awal=3,beda=4,posisi_target=15)|P3|deret_terbalik_geometri(awal=5,posisi_target=6,rasio=2)|P3|siklus_hari(hari_awal=Sabtu,tambah=50)|P3|jumlah_siklus(n_angka=16,pola=[4, 5, 1])",
  "P4|1": "P4|deret_aritmetika(awal=4,beda=11,n_minta=2,n_tampil=4)|P4|deret_aritmetika_turun(awal=42,beda=6,n_tampil=5)|P4|deret_geometri(awal=2,n_tampil=5,rasio=3)|P4|deret_bertingkat(awal=7,beda_awal=2,kenaikan=2,n_tampil=6)|P4|siklus_huruf(pola=['A', 'D', 'C', 'D'],posisi=68)|P4|korek_api(awal=6,gambar_ke=38,tambah=3)|P4|titik_segitiga(gambar_ke=11)|P4|deret_terbalik_aritmetika(awal=6,beda=3,posisi_target=17)|P4|deret_terbalik_geometri(awal=2,posisi_target=6,rasio=2)|P4|siklus_hari(hari_awal=Sabtu,tambah=100)|P4|suku_ke_n(awal=2,beda=9,posisi=60)|P4|sisa_bagi_siklus(pola=['A', 'A', 'C', 'D', 'E'],posisi=136)",
  "P4|2026": "P4|deret_aritmetika(awal=3,beda=8,n_minta=2,n_tampil=4)|P4|deret_aritmetika_turun(awal=77,beda=11,n_tampil=4)|P4|deret_geometri(awal=3,n_tampil=5,rasio=4)|P4|deret_bertingkat(awal=9,beda_awal=4,kenaikan=4,n_tampil=6)|P4|siklus_huruf(pola=['A', 'B', 'A', 'D'],posisi=37)|P4|korek_api(awal=3,gambar_ke=15,tambah=3)|P4|titik_segitiga(gambar_ke=15)|P4|deret_terbalik_aritmetika(awal=7,beda=5,posisi_target=15)|P4|deret_terbalik_geometri(awal=4,posisi_target=7,rasio=2)|P4|siklus_hari(hari_awal=Rabu,tambah=150)|P4|suku_ke_n(awal=8,beda=12,posisi=50)|P4|sisa_bagi_siklus(pola=['C', 'B', 'C', 'D', 'E', 'F'],posisi=148)",
  "P4|42": "P4|deret_aritmetika(awal=12,beda=6,n_minta=2,n_tampil=4)|P4|deret_aritmetika_turun(awal=48,beda=6,n_tampil=5)|P4|deret_geometri(awal=2,n_tampil=4,rasio=2)|P4|deret_bertingkat(awal=9,beda_awal=1,kenaikan=4,n_tampil=6)|P4|siklus_huruf(pola=['A', 'B', 'C', 'D'],posisi=44)|P4|korek_api(awal=7,gambar_ke=37,tambah=2)|P4|titik_segitiga(gambar_ke=16)|P4|deret_terbalik_aritmetika(awal=5,beda=4,posisi_target=19)|P4|deret_terbalik_geometri(awal=2,posisi_target=5,rasio=3)|P4|siklus_hari(hari_awal=Minggu,tambah=150)|P4|suku_ke_n(awal=4,beda=12,posisi=100)|P4|sisa_bagi_siklus(pola=['A', 'C', 'C', 'D', 'E'],posisi=107)",
  "P4|7": "P4|deret_aritmetika(awal=7,beda=7,n_minta=2,n_tampil=4)|P4|deret_aritmetika_turun(awal=54,beda=9,n_tampil=4)|P4|deret_geometri(awal=1,n_tampil=5,rasio=4)|P4|deret_bertingkat(awal=1,beda_awal=2,kenaikan=2,n_tampil=5)|P4|siklus_huruf(pola=['D', 'B', 'C', 'D', 'E'],posisi=35)|P4|korek_api(awal=3,gambar_ke=18,tambah=4)|P4|titik_segitiga(gambar_ke=11)|P4|deret_terbalik_aritmetika(awal=7,beda=3,posisi_target=21)|P4|deret_terbalik_geometri(awal=2,posisi_target=5,rasio=3)|P4|siklus_hari(hari_awal=Selasa,tambah=45)|P4|suku_ke_n(awal=10,beda=7,posisi=75)|P4|sisa_bagi_siklus(pola=['B', 'B', 'C', 'D', 'E'],posisi=119)",
  "P4|99999": "P4|deret_aritmetika(awal=3,beda=8,n_minta=2,n_tampil=4)|P4|deret_aritmetika_turun(awal=88,beda=11,n_tampil=4)|P4|deret_geometri(awal=1,n_tampil=5,rasio=3)|P4|deret_bertingkat(awal=7,beda_awal=2,kenaikan=2,n_tampil=6)|P4|siklus_huruf(pola=['A', 'B', 'E', 'D', 'E'],posisi=55)|P4|korek_api(awal=4,gambar_ke=25,tambah=4)|P4|titik_segitiga(gambar_ke=16)|P4|deret_terbalik_aritmetika(awal=8,beda=4,posisi_target=17)|P4|deret_terbalik_geometri(awal=3,posisi_target=8,rasio=2)|P4|siklus_hari(hari_awal=Selasa,tambah=75)|P4|suku_ke_n(awal=11,beda=7,posisi=60)|P4|sisa_bagi_siklus(pola=['A', 'B', 'C', 'D', 'D', 'F'],posisi=129)",
  "P5|1": "P5|deret_aritmetika(awal=4,beda=14,n_minta=3,n_tampil=4)|P5|deret_geometri(awal=3,n_tampil=5,rasio=2)|P5|deret_bertingkat(awal=8,beda_awal=4,kenaikan=4,n_tampil=6)|P5|siklus_huruf(pola=['A', 'A', 'C', 'D'],posisi=109)|P5|korek_api(awal=7,gambar_ke=53,tambah=2)|P5|titik_segitiga(gambar_ke=14)|P5|deret_terbalik_aritmetika(awal=7,beda=4,posisi_target=18)|P5|deret_terbalik_geometri(awal=2,posisi_target=8,rasio=2)|P5|jumlah_siklus(n_angka=56,pola=[5, 1, 2])|P5|suku_ke_n(awal=2,beda=14,posisi=120)|P5|sisa_bagi_siklus(pola=['A', 'D', 'C', 'D', 'E'],posisi=238)|P5|pola_pecahan(beda_pembilang=3,n_tampil=4,pembilang=2,penyebut=18)",
  "P5|2026": "P5|deret_aritmetika(awal=3,beda=12,n_minta=3,n_tampil=4)|P5|deret_geometri(awal=3,n_tampil=4,rasio=5)|P5|deret_bertingkat(awal=4,beda_awal=4,kenaikan=5,n_tampil=6)|P5|siklus_huruf(pola=['B', 'B', 'C', 'D', 'E'],posisi=74)|P5|korek_api(awal=3,gambar_ke=25,tambah=3)|P5|titik_segitiga(gambar_ke=20)|P5|deret_terbalik_aritmetika(awal=5,beda=5,posisi_target=21)|P5|deret_terbalik_geometri(awal=4,posisi_target=9,rasio=2)|P5|jumlah_siklus(n_angka=59,pola=[4, 1, 3, 2])|P5|suku_ke_n(awal=10,beda=12,posisi=150)|P5|sisa_bagi_siklus(pola=['A', 'B', 'B', 'D', 'E'],posisi=156)|P5|pola_pecahan(beda_pembilang=2,n_tampil=4,pembilang=3,penyebut=15)",
  "P5|42": "P5|deret_aritmetika(awal=12,beda=9,n_minta=3,n_tampil=4)|P5|deret_geometri(awal=6,n_tampil=6,rasio=2)|P5|deret_bertingkat(awal=4,beda_awal=2,kenaikan=3,n_tampil=5)|P5|siklus_huruf(pola=['D', 'B', 'C', 'A'],posisi=64)|P5|korek_api(awal=4,gambar_ke=26,tambah=4)|P5|titik_segitiga(gambar_ke=18)|P5|deret_terbalik_aritmetika(awal=3,beda=6,posisi_target=22)|P5|deret_terbalik_geometri(awal=4,posisi_target=10,rasio=2)|P5|jumlah_siklus(n_angka=61,pola=[2, 4, 5])|P5|suku_ke_n(awal=5,beda=16,posisi=150)|P5|sisa_bagi_siklus(pola=['A', 'A', 'C', 'D'],posisi=174)|P5|pola_pecahan(beda_pembilang=2,n_tampil=4,pembilang=3,penyebut=16)",
  "P5|7": "P5|deret_aritmetika(awal=7,beda=11,n_minta=3,n_tampil=4)|P5|deret_geometri(awal=3,n_tampil=5,rasio=4)|P5|deret_bertingkat(awal=2,beda_awal=1,kenaikan=4,n_tampil=5)|P5|siklus_huruf(pola=['A', 'B', 'C', 'D'],posisi=116)|P5|korek_api(awal=4,gambar_ke=60,tambah=2)|P5|titik_segitiga(gambar_ke=16)|P5|deret_terbalik_aritmetika(awal=2,beda=3,posisi_target=22)|P5|deret_terbalik_geometri(awal=3,posisi_target=5,rasio=3)|P5|jumlah_siklus(n_angka=50,pola=[2, 1, 3])|P5|suku_ke_n(awal=8,beda=11,posisi=100)|P5|sisa_bagi_siklus(pola=['A', 'B', 'C', 'D', 'C', 'F'],posisi=196)|P5|pola_pecahan(beda_pembilang=3,n_tampil=4,pembilang=1,penyebut=19)",
  "P5|99999": "P5|deret_aritmetika(awal=3,beda=12,n_minta=3,n_tampil=4)|P5|deret_geometri(awal=3,n_tampil=4,rasio=5)|P5|deret_bertingkat(awal=6,beda_awal=4,kenaikan=3,n_tampil=6)|P5|siklus_huruf(pola=['A', 'E', 'C', 'D', 'E'],posisi=148)|P5|korek_api(awal=7,gambar_ke=42,tambah=3)|P5|titik_segitiga(gambar_ke=14)|P5|deret_terbalik_aritmetika(awal=6,beda=4,posisi_target=20)|P5|deret_terbalik_geometri(awal=2,posisi_target=6,rasio=3)|P5|jumlah_siklus(n_angka=121,pola=[1, 2, 5, 4])|P5|suku_ke_n(awal=10,beda=14,posisi=120)|P5|sisa_bagi_siklus(pola=['A', 'B', 'C', 'D', 'D', 'F'],posisi=248)|P5|pola_pecahan(beda_pembilang=2,n_tampil=4,pembilang=2,penyebut=14)",
  "P6|1": "P6|deret_aritmetika(awal=4,beda=13,n_minta=3,n_tampil=4)|P6|deret_geometri(awal=1,n_tampil=5,rasio=5)|P6|deret_bertingkat(awal=8,beda_awal=4,kenaikan=7,n_tampil=5)|P6|titik_segitiga(gambar_ke=13)|P6|deret_terbalik_aritmetika(awal=5,beda=3,posisi_target=32)|P6|deret_terbalik_geometri(awal=1,posisi_target=12,rasio=2)|P6|siklus_hari(hari_awal=Sabtu,tambah=500)|P6|jumlah_siklus(n_angka=81,pola=[2, 1, 5, 4])|P6|suku_ke_n(awal=12,beda=21,posisi=150)|P6|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B', 'E'],posisi=671)|P6|pola_pecahan(beda_pembilang=3,n_tampil=4,pembilang=1,penyebut=17)|P6|jumlah_deret(awal=8,beda=5,n=25)",
  "P6|2026": "P6|deret_aritmetika(awal=3,beda=17,n_minta=3,n_tampil=4)|P6|deret_geometri(awal=1,n_tampil=7,rasio=3)|P6|deret_bertingkat(awal=9,beda_awal=4,kenaikan=7,n_tampil=5)|P6|titik_segitiga(gambar_ke=12)|P6|deret_terbalik_aritmetika(awal=6,beda=3,posisi_target=23)|P6|deret_terbalik_geometri(awal=5,posisi_target=10,rasio=2)|P6|siklus_hari(hari_awal=Senin,tambah=1000)|P6|jumlah_siklus(n_angka=126,pola=[3, 2, 4, 5])|P6|suku_ke_n(awal=8,beda=21,posisi=150)|P6|sisa_bagi_siklus(pola=['C', 'B', 'C', 'D', 'E', 'F'],posisi=585)|P6|pola_pecahan(beda_pembilang=2,n_tampil=4,pembilang=3,penyebut=15)|P6|jumlah_deret(awal=3,beda=4,n=20)",
  "P6|42": "P6|deret_aritmetika(awal=12,beda=13,n_minta=3,n_tampil=4)|P6|deret_geometri(awal=3,n_tampil=6,rasio=3)|P6|deret_bertingkat(awal=4,beda_awal=2,kenaikan=5,n_tampil=5)|P6|titik_segitiga(gambar_ke=22)|P6|deret_terbalik_aritmetika(awal=7,beda=3,posisi_target=38)|P6|deret_terbalik_geometri(awal=2,posisi_target=10,rasio=2)|P6|siklus_hari(hari_awal=Senin,tambah=300)|P6|jumlah_siklus(n_angka=80,pola=[5, 1, 3])|P6|suku_ke_n(awal=5,beda=19,posisi=500)|P6|sisa_bagi_siklus(pola=['A', 'A', 'C', 'D', 'E'],posisi=657)|P6|pola_pecahan(beda_pembilang=2,n_tampil=4,pembilang=4,penyebut=15)|P6|jumlah_deret(awal=3,beda=3,n=30)",
  "P6|7": "P6|deret_aritmetika(awal=7,beda=14,n_minta=3,n_tampil=4)|P6|deret_geometri(awal=3,n_tampil=4,rasio=6)|P6|deret_bertingkat(awal=2,beda_awal=1,kenaikan=6,n_tampil=5)|P6|titik_segitiga(gambar_ke=20)|P6|deret_terbalik_aritmetika(awal=3,beda=3,posisi_target=22)|P6|deret_terbalik_geometri(awal=2,posisi_target=11,rasio=2)|P6|siklus_hari(hari_awal=Selasa,tambah=200)|P6|jumlah_siklus(n_angka=155,pola=[1, 5, 4, 3])|P6|suku_ke_n(awal=8,beda=12,posisi=200)|P6|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B'],posisi=514)|P6|pola_pecahan(beda_pembilang=3,n_tampil=4,pembilang=2,penyebut=18)|P6|jumlah_deret(awal=5,beda=3,n=20)",
  "P6|99999": "P6|deret_aritmetika(awal=3,beda=16,n_minta=3,n_tampil=4)|P6|deret_geometri(awal=2,n_tampil=5,rasio=4)|P6|deret_bertingkat(awal=4,beda_awal=3,kenaikan=7,n_tampil=5)|P6|titik_segitiga(gambar_ke=12)|P6|deret_terbalik_aritmetika(awal=7,beda=5,posisi_target=36)|P6|deret_terbalik_geometri(awal=1,posisi_target=12,rasio=2)|P6|siklus_hari(hari_awal=Minggu,tambah=365)|P6|jumlah_siklus(n_angka=136,pola=[2, 3, 4])|P6|suku_ke_n(awal=7,beda=13,posisi=200)|P6|sisa_bagi_siklus(pola=['A', 'B', 'C', 'C'],posisi=383)|P6|pola_pecahan(beda_pembilang=3,n_tampil=4,pembilang=2,penyebut=19)|P6|jumlah_deret(awal=9,beda=5,n=25)"
 },
 "soal": {
  "P3|deret_aritmetika_turun|7": "P3|deret_aritmetika_turun(awal=45,beda=5,n_tampil=4)",
  "P3|deret_aritmetika|7": "P3|deret_aritmetika(awal=7,beda=4,n_minta=2,n_tampil=4)",
  "P3|deret_bertingkat|7": "P3|deret_bertingkat(awal=6,beda_awal=2,kenaikan=2,n_tampil=5)",
  "P3|deret_geometri|7": "P3|deret_geometri(awal=2,n_tampil=4,rasio=2)",
  "P3|deret_terbalik_aritmetika|7": "P3|deret_terbalik_aritmetika(awal=4,beda=4,posisi_target=13)",
  "P3|deret_terbalik_geometri|7": "P3|deret_terbalik_geometri(awal=5,posisi_target=4,rasio=2)",
  "P3|jumlah_deret|7": "P3|jumlah_deret(awal=6,beda=3,n=10)",
  "P3|jumlah_siklus|7": "P3|jumlah_siklus(n_angka=27,pola=[2, 4, 3, 1])",
  "P3|korek_api|7": "P3|korek_api(awal=5,gambar_ke=14,tambah=2)",
  "P3|pola_pecahan|7": "P3|pola_pecahan(beda_pembilang=1,n_tampil=4,pembilang=3,penyebut=10)",
  "P3|siklus_hari|7": "P3|siklus_hari(hari_awal=Rabu,tambah=20)",
  "P3|siklus_huruf|7": "P3|siklus_huruf(pola=['A', 'B', 'C', 'B', 'E'],posisi=20)",
  "P3|siklus_warna|7": "P3|siklus_warna(pola=['kuning', 'biru', 'kuning', 'merah', 'putih'],posisi=38)",
  "P3|sisa_bagi_siklus|7": "P3|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B', 'E'],posisi=60)",
  "P3|suku_ke_n|7": "P3|suku_ke_n(awal=7,beda=4,posisi=30)",
  "P3|titik_segitiga|7": "P3|titik_segitiga(gambar_ke=8)",
  "P4|deret_aritmetika_turun|7": "P4|deret_aritmetika_turun(awal=72,beda=8,n_tampil=4)",
  "P4|deret_aritmetika|7": "P4|deret_aritmetika(awal=7,beda=7,n_minta=2,n_tampil=4)",
  "P4|deret_bertingkat|7": "P4|deret_bertingkat(awal=6,beda_awal=2,kenaikan=3,n_tampil=5)",
  "P4|deret_geometri|7": "P4|deret_geometri(awal=1,n_tampil=5,rasio=3)",
  "P4|deret_terbalik_aritmetika|7": "P4|deret_terbalik_aritmetika(awal=4,beda=4,posisi_target=18)",
  "P4|deret_terbalik_geometri|7": "P4|deret_terbalik_geometri(awal=5,posisi_target=6,rasio=2)",
  "P4|jumlah_deret|7": "P4|jumlah_deret(awal=6,beda=3,n=12)",
  "P4|jumlah_siklus|7": "P4|jumlah_siklus(n_angka=39,pola=[2, 4, 3, 1])",
  "P4|korek_api|7": "P4|korek_api(awal=5,gambar_ke=27,tambah=2)",
  "P4|pola_pecahan|7": "P4|pola_pecahan(beda_pembilang=1,n_tampil=4,pembilang=3,penyebut=10)",
  "P4|siklus_hari|7": "P4|siklus_hari(hari_awal=Rabu,tambah=60)",
  "P4|siklus_huruf|7": "P4|siklus_huruf(pola=['A', 'B', 'C', 'B', 'E'],posisi=35)",
  "P4|siklus_warna|7": "P4|siklus_warna(pola=['kuning', 'biru', 'kuning', 'merah', 'putih'],posisi=77)",
  "P4|sisa_bagi_siklus|7": "P4|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B', 'E'],posisi=86)",
  "P4|suku_ke_n|7": "P4|suku_ke_n(awal=7,beda=7,posisi=100)",
  "P4|titik_segitiga|7": "P4|titik_segitiga(gambar_ke=13)",
  "P5|deret_aritmetika_turun|7": "P5|deret_aritmetika_turun(awal=108,beda=12,n_tampil=4)",
  "P5|deret_aritmetika|7": "P5|deret_aritmetika(awal=7,beda=11,n_minta=3,n_tampil=4)",
  "P5|deret_bertingkat|7": "P5|deret_bertingkat(awal=6,beda_awal=2,kenaikan=4,n_tampil=5)",
  "P5|deret_geometri|7": "P5|deret_geometri(awal=1,n_tampil=6,rasio=3)",
  "P5|deret_terbalik_aritmetika|7": "P5|deret_terbalik_aritmetika(awal=4,beda=4,posisi_target=27)",
  "P5|deret_terbalik_geometri|7": "P5|deret_terbalik_geometri(awal=5,posisi_target=8,rasio=2)",
  "P5|jumlah_deret|7": "P5|jumlah_deret(awal=6,beda=3,n=20)",
  "P5|jumlah_siklus|7": "P5|jumlah_siklus(n_angka=59,pola=[2, 4, 3, 1])",
  "P5|korek_api|7": "P5|korek_api(awal=5,gambar_ke=50,tambah=2)",
  "P5|pola_pecahan|7": "P5|pola_pecahan(beda_pembilang=1,n_tampil=4,pembilang=3,penyebut=10)",
  "P5|siklus_hari|7": "P5|siklus_hari(hari_awal=Rabu,tambah=150)",
  "P5|siklus_huruf|7": "P5|siklus_huruf(pola=['A', 'B', 'C', 'B', 'E'],posisi=70)",
  "P5|siklus_warna|7": "P5|siklus_warna(pola=['kuning', 'biru', 'kuning', 'merah', 'putih'],posisi=149)",
  "P5|sisa_bagi_siklus|7": "P5|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B', 'E'],posisi=162)",
  "P5|suku_ke_n|7": "P5|suku_ke_n(awal=7,beda=11,posisi=200)",
  "P5|titik_segitiga|7": "P5|titik_segitiga(gambar_ke=15)",
  "P6|deret_aritmetika_turun|7": "P6|deret_aritmetika_turun(awal=153,beda=17,n_tampil=4)",
  "P6|deret_aritmetika|7": "P6|deret_aritmetika(awal=7,beda=14,n_minta=3,n_tampil=4)",
  "P6|deret_bertingkat|7": "P6|deret_bertingkat(awal=6,beda_awal=2,kenaikan=7,n_tampil=5)",
  "P6|deret_geometri|7": "P6|deret_geometri(awal=1,n_tampil=5,rasio=5)",
  "P6|deret_terbalik_aritmetika|7": "P6|deret_terbalik_aritmetika(awal=4,beda=4,posisi_target=32)",
  "P6|deret_terbalik_geometri|7": "P6|deret_terbalik_geometri(awal=5,posisi_target=10,rasio=2)",
  "P6|jumlah_deret|7": "P6|jumlah_deret(awal=6,beda=3,n=40)",
  "P6|jumlah_siklus|7": "P6|jumlah_siklus(n_angka=91,pola=[2, 4, 3, 1])",
  "P6|korek_api|7": "P6|korek_api(awal=5,gambar_ke=65,tambah=2)",
  "P6|pola_pecahan|7": "P6|pola_pecahan(beda_pembilang=1,n_tampil=4,pembilang=3,penyebut=12)",
  "P6|siklus_hari|7": "P6|siklus_hari(hari_awal=Rabu,tambah=300)",
  "P6|siklus_huruf|7": "P6|siklus_huruf(pola=['A', 'B', 'C', 'B', 'E'],posisi=120)",
  "P6|siklus_warna|7": "P6|siklus_warna(pola=['kuning', 'biru', 'kuning', 'merah', 'putih'],posisi=269)",
  "P6|sisa_bagi_siklus|7": "P6|sisa_bagi_siklus(pola=['A', 'B', 'C', 'B', 'E'],posisi=633)",
  "P6|suku_ke_n|7": "P6|suku_ke_n(awal=7,beda=14,posisi=300)",
  "P6|titik_segitiga|7": "P6|titik_segitiga(gambar_ke=17)"
 }
}

SEEDS = [1, 7, 42, 2026, 99999]


def test_cakupan_snapshot_tepat_p3_sampai_p6():
    assert set(LEVEL_TINGKAT) == {"P3", "P4", "P5", "P6"}
    for bagian in EMAS.values():
        assert {k.split("|", 1)[0] for k in bagian} == set(LEVEL_TINGKAT)


@pytest.mark.parametrize("level", LEVEL_TINGKAT)
@pytest.mark.parametrize("seed", SEEDS)
def test_lembar_identik_dengan_snapshot_a4(level, seed):
    kunci = EMAS["lembar"][f"{level}|{seed}"]
    assert buat_lembar(seed, level=level).tanda_tangan == kunci


@pytest.mark.parametrize("level", LEVEL_TINGKAT)
def test_setiap_template_identik_dengan_snapshot_a4(level):
    for tid in sorted(paket_bawaan().templates):
        kunci = EMAS["soal"][f"{level}|{tid}|7"]
        assert buat_soal(tid, 7, level).tanda_tangan == kunci, tid
