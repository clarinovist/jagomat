"""Skrip peramban Latihan Lomba: hanya penghitung mundur di bilah atas.

Server tetap satu-satunya penegak waktu (jawaban setelah batas ditolak, sesi ditutup di server);
skrip ini cuma menampilkan sisa waktu agar anak tahu kapan waktunya habis. Memakai selisih terbesar dari jam monoton (`performance.now`, berhenti saat perangkat tidur) dan
jam dinding (`Date.now`, terus maju; bila dimundurkan tidak menambah waktu). Jam dinding hanya
dipakai untuk selisih sejak halaman dimuat, bukan sebagai waktu mutlak.
Tanpa network, storage, atau autosave. Tanpa JS, halaman tetap benar: MM:SS statis dari server tampil.

`SKRIP_TIMER` hanya isi skrip; halaman membungkusnya sebagai `<script>` polos tanpa atribut
supaya `csp_tautan` menghash-nya.
"""
from __future__ import annotations

SKRIP_TIMER = """
(function () {
  var BATAS_MERAH = 180;
  var JEDA_MS = 500;
  try {
    var penanda = document.getElementById('timer');
    if (!penanda) { return; }
    var sisa = parseInt(penanda.getAttribute('data-sisa'), 10);
    var tujuan = penanda.getAttribute('data-hasil');
    if (isNaN(sisa) || !tujuan) { return; }
    var mulaiPerf = performance.now();
    var mulaiJam = Date.now();
    var sudahPindah = false;
    function dua(angka) { return (angka < 10 ? '0' : '') + angka; }
    function berlalu() { return Math.max(performance.now() - mulaiPerf, Date.now() - mulaiJam); }
    function tampilkan() {
      var detik = Math.ceil(sisa - berlalu() / 1000);
      if (detik <= 0) {
        if (!sudahPindah) { sudahPindah = true; location.replace(tujuan); }
        return;
      }
      penanda.textContent = dua(Math.floor(detik / 60)) + ':' + dua(detik % 60);
      if (detik <= BATAS_MERAH) { penanda.classList.add('merah'); }
    }
    tampilkan();
    setInterval(tampilkan, JEDA_MS);
    document.addEventListener('visibilitychange', tampilkan);
    window.addEventListener('pageshow', function (kejadian) {
      if (kejadian.persisted) { location.reload(); }
    });
  } catch (galat) {
    /* Penghitung hanya tambahan tampilan; server tetap menegakkan batas waktu. */
  }
})();
"""
