"""Perilaku skrip timer Latihan Lomba di sandbox Node (stub DOM, jam, dan lokasi); dilewati bila Node tidak ada."""
import json
import shutil
import subprocess

import pytest

import contest_browser as B

HASIL = "/murid/lomba/hasil/7"
DETIK = 1000

HARNESS = r"""
const vm = require('node:vm');
const berkas = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
let P = 1000, W = 1700000000000;
const kelas = new Set();
let teks = '';
const nilaiAtribut = {'data-sisa': String(berkas.sisa), 'data-hasil': berkas.tujuan};
const penanda = berkas.tanpaPenanda ? null : {
  getAttribute: function (nama) { return nama in nilaiAtribut ? nilaiAtribut[nama] : null; },
  set textContent(v) { teks = v; },
  get textContent() { return teks; },
  classList: { add: function (c) { kelas.add(c); } },
};
const dokumen = {}, jendela = {};
let interval = null, reload = 0;
const dialihkan = [];
const kotak = {
  document: {
    getElementById: function (id) { return id === 'timer' ? penanda : null; },
    addEventListener: function (n, f) { dokumen[n] = f; },
  },
  window: { addEventListener: function (n, f) { jendela[n] = f; } },
  performance: { now: function () { return P; } },
  Date: { now: function () { return W; } },
  location: { replace: function (u) { dialihkan.push(u); }, reload: function () { reload++; } },
  setInterval: function (f) { interval = f; },
};
vm.createContext(kotak);
vm.runInContext(berkas.skrip, kotak);
for (const l of berkas.langkah) {
  if (l.op === 'maju') { P += l.perf; W += l.wall; }
  else if (l.op === 'tick') { if (interval) { interval(); } }
  else if (l.op === 'lihat') { if (dokumen.visibilitychange) { dokumen.visibilitychange(); } }
  else if (l.op === 'pageshow') { jendela.pageshow({ persisted: l.persisted }); }
}
console.log(JSON.stringify({ teks: teks, kelas: Array.from(kelas), dialihkan: dialihkan, reload: reload }));
"""


def _jalankan(tmp_path, sisa, langkah=(), tanpa_penanda=False, skrip=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node tidak tersedia; gate browser wajib sebelum rilis.")
    masukan = tmp_path / "masukan.json"
    harness = tmp_path / "harness.js"
    masukan.write_text(json.dumps({"skrip": skrip or B.SKRIP_TIMER, "sisa": sisa, "tujuan": HASIL,
                                   "langkah": list(langkah), "tanpaPenanda": tanpa_penanda}))
    harness.write_text(HARNESS)
    proses = subprocess.run([node, str(harness), str(masukan)], capture_output=True, text=True, timeout=20)
    assert proses.returncode == 0, proses.stderr
    return json.loads(proses.stdout)


def _maju(perf, wall=None):
    return {"op": "maju", "perf": perf, "wall": perf if wall is None else wall}


TICK = {"op": "tick"}


def test_menampilkan_sisa_waktu_dari_server_saat_dimuat(tmp_path):
    assert _jalankan(tmp_path, 900)["teks"] == "15:00"


def test_hitung_mundur_berjalan_mengikuti_jam(tmp_path):
    hasil = _jalankan(tmp_path, 900, [_maju(61 * DETIK), TICK])
    assert hasil["teks"] == "13:59"


def test_layar_terkunci_perf_berhenti_tetapi_jam_dinding_maju_waktu_tetap_benar(tmp_path):
    # Perangkat tidur 5 menit: performance.now tidak maju, Date.now maju 300 detik.
    hasil = _jalankan(tmp_path, 900, [_maju(0, 300 * DETIK), {"op": "lihat"}])
    assert hasil["teks"] == "10:00"


def test_jam_sistem_dimundurkan_tidak_menambah_waktu(tmp_path):
    hasil = _jalankan(tmp_path, 900, [_maju(100 * DETIK, -3600 * DETIK), TICK])
    assert hasil["teks"] == "13:20"


def test_kelas_merah_hanya_pada_seratus_delapan_puluh_detik_terakhir(tmp_path):
    assert _jalankan(tmp_path, 181)["kelas"] == []
    assert _jalankan(tmp_path, 181, [_maju(DETIK), TICK])["kelas"] == ["merah"]
    assert _jalankan(tmp_path, 180)["kelas"] == ["merah"]


def test_saat_waktu_habis_pindah_ke_hasil_tepat_sekali(tmp_path):
    hasil = _jalankan(tmp_path, 3, [_maju(2 * DETIK), TICK, _maju(DETIK), TICK, TICK, _maju(5 * DETIK), TICK])
    assert hasil["dialihkan"] == [HASIL]


def test_belum_habis_tidak_berpindah(tmp_path):
    assert _jalankan(tmp_path, 3, [_maju(2 * DETIK), TICK])["dialihkan"] == []


def test_waktu_habis_karena_perangkat_tidur_juga_pindah_ke_hasil(tmp_path):
    hasil = _jalankan(tmp_path, 60, [_maju(0, 120 * DETIK), {"op": "lihat"}])
    assert hasil["dialihkan"] == [HASIL]


@pytest.mark.parametrize("persisted,jumlah", [(True, 1), (False, 0)])
def test_halaman_dari_cache_riwayat_dimuat_ulang_agar_timer_sinkron_dengan_server(tmp_path, persisted, jumlah):
    hasil = _jalankan(tmp_path, 900, [{"op": "pageshow", "persisted": persisted}])
    assert hasil["reload"] == jumlah


def test_tanpa_elemen_timer_skrip_diam_tanpa_galat(tmp_path):
    hasil = _jalankan(tmp_path, 900, [_maju(DETIK), TICK], tanpa_penanda=True)
    assert hasil["dialihkan"] == [] and hasil["teks"] == ""


def test_data_sisa_rusak_membuat_skrip_diam(tmp_path):
    node_skrip = B.SKRIP_TIMER
    hasil = _jalankan(tmp_path, "bukan-angka", [_maju(DETIK), TICK], skrip=node_skrip)
    assert hasil["teks"] == "" and hasil["dialihkan"] == []
