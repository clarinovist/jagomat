"""Skrip laporan Peta Kemampuan (disetujui pemilik, Keputusan 19; PANDUAN §5).

Dua konstanta statis, tanpa interpolasi per permintaan (hash CSP tetap):

- `SKRIP_PETA`: tab, pergantian maskot, donat yang bisa diklik, stiker hari
  (localStorage dibungkus try/catch, tanpa network), tantangan + konfeti.
- `SKRIP_CETAK`: tombol cetak lembar 1 halaman (tanpa `onclick=`).

Disisipkan sebagai `<script>...</script>` polos tanpa atribut agar `web.csp_tautan`
menghitung hash-nya. Tanpa `fetch`, XHR, `eval`, atau `innerHTML`: semua teks lewat
`textContent`; konten spesifik laporan (pose, kalimat maskot, umpan tantangan)
dibaca dari atribut `data-*` yang sudah di-escape server. Tanpa JS, semua panel,
detail pola, dan jawaban tantangan tetap tampil (lihat `peta_laporan`).
"""

SKRIP_PETA = """\
(function () {
  'use strict';
  var doc = document;
  if (!doc.querySelectorAll || !doc.addEventListener || !doc.documentElement.classList) return;
  doc.documentElement.classList.add('peta-js-st');
  function semua(selektor, akar) {
    return Array.prototype.slice.call((akar || doc).querySelectorAll(selektor));
  }
  function aman(fungsi) {
    try { return fungsi(); } catch (galat) { return undefined; }
  }

  var gambar = doc.getElementById('peta-maskot');
  var gelembung = doc.getElementById('peta-gelembung');
  function ubahMaskot(pose, kata) {
    if (!gambar || !pose) return;
    gambar.src = pose;
    if (gelembung && kata) gelembung.textContent = kata;
    gambar.classList.remove('peta-lompat-st');
    void gambar.offsetWidth;
    gambar.classList.add('peta-lompat-st');
  }

  var tab = semua('[data-peta-tab]');
  var panel = semua('[data-peta-panel]');
  function tampil(id, fokus) {
    if (!doc.getElementById(id) || !panel.some(function (p) { return p.id === id; })) id = 'ringkasan';
    panel.forEach(function (p) { p.hidden = p.id !== id; });
    tab.forEach(function (t) {
      var aktif = t.getAttribute('data-peta-tab') === id;
      t.setAttribute('aria-current', aktif ? 'true' : 'false');
      if (aktif) ubahMaskot(t.getAttribute('data-pose'), t.getAttribute('data-kata'));
    });
    var sasaran = fokus ? doc.getElementById(fokus) : null;
    if (!sasaran) return;
    if (sasaran.tagName === 'DETAILS') sasaran.open = true;
    window.setTimeout(function () { sasaran.scrollIntoView({ block: 'start' }); }, 30);
  }
  function catatRiwayat(hash) {
    aman(function () { window.history.replaceState(null, '', '#' + hash); });
  }
  tab.forEach(function (t) {
    t.addEventListener('click', function (acara) {
      acara.preventDefault();
      var id = t.getAttribute('data-peta-tab');
      tampil(id);
      catatRiwayat(id);
    });
  });
  function bukaMateri(acara) {
    var id = acara.currentTarget.getAttribute('data-buka');
    acara.preventDefault();
    tampil('per-materi', id);
    catatRiwayat(id);
  }
  semua('[data-buka]').forEach(function (a) { a.addEventListener('click', bukaMateri); });
  var awal = window.location.hash.slice(1);
  if (awal.indexOf('m-') === 0) tampil('per-materi', awal); else tampil(awal || 'ringkasan');

  var donat = doc.getElementById('peta-donat');
  if (donat) {
    var irisan = semua('.peta-seg-st', donat);
    var tombol = semua('button[data-pola]');
    var rincian = semua('[data-detail]');
    var teksTengah = ['peta-donat-angka', 'peta-donat-teks', 'peta-donat-kecil'].map(function (id) {
      return doc.getElementById(id);
    });
    var awalTengah = teksTengah.map(function (el) { return el ? el.textContent : ''; });
    var terpilih = null;
    var atributTengah = ['data-angka', 'data-teks', 'data-kecil'];
    var tampilkanPola = function () {
      donat.classList.toggle('peta-pilih-st', !!terpilih);
      irisan.forEach(function (s) {
        s.classList.toggle('peta-aktif-st', s.getAttribute('data-pola') === terpilih);
      });
      tombol.forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-pola') === terpilih ? 'true' : 'false');
      });
      rincian.forEach(function (d) { d.hidden = d.getAttribute('data-detail') !== (terpilih || 'semua'); });
      var sumber = terpilih ? irisan.filter(function (s) {
        return s.getAttribute('data-pola') === terpilih && s.hasAttribute('data-angka');
      })[0] : null;
      teksTengah.forEach(function (el, i) {
        if (el) el.textContent = sumber ? sumber.getAttribute(atributTengah[i]) : awalTengah[i];
      });
    };
    var pilihPola = function (kunci) {
      terpilih = terpilih === kunci ? null : kunci;
      tampilkanPola();
    };
    irisan.concat(tombol).forEach(function (el) {
      el.addEventListener('click', function () { pilihPola(el.getAttribute('data-pola')); });
    });
    tampilkanPola();
  }

  var hari = semua('input[data-peta-hari]');
  var statusHari = doc.getElementById('peta-hari-status');
  var kunciHari = hari.length ? hari[0].getAttribute('data-peta-kunci') : '';
  function bacaHari() {
    return aman(function () { return JSON.parse(window.localStorage.getItem(kunciHari) || '[]'); }) || [];
  }
  function simpanHari(nilai) {
    aman(function () { window.localStorage.setItem(kunciHari, JSON.stringify(nilai)); });
  }
  function perbaruiHari() {
    var jumlah = hari.filter(function (k) { return k.checked; }).length;
    if (statusHari) {
      statusHari.textContent = jumlah ? 'Sudah dicoba ' + jumlah + ' dari ' + hari.length + ' hari minggu ini.' : 'Belum ada hari yang ditandai.';
    }
  }
  if (hari.length) {
    var tersimpan = bacaHari();
    hari.forEach(function (k) {
      k.checked = tersimpan.indexOf(k.id) > -1;
      k.addEventListener('change', function () {
        simpanHari(hari.filter(function (x) { return x.checked; }).map(function (x) { return x.id; }));
        perbaruiHari();
      });
    });
    perbaruiHari();
  }

  var coba = doc.querySelector('[data-peta-coba]');
  var konfeti = doc.getElementById('peta-konfeti');
  var BANYAK_KONFETI = 28;
  function hujanKonfeti() {
    if (!konfeti) return;
    while (konfeti.firstChild) konfeti.removeChild(konfeti.firstChild);
    for (var i = 0; i < BANYAK_KONFETI; i++) {
      var kepingan = doc.createElement('i');
      kepingan.style.left = Math.random() * 100 + '%';
      kepingan.style.animationDelay = Math.random() * 0.3 + 's';
      konfeti.appendChild(kepingan);
    }
    konfeti.classList.remove('peta-jalan-st');
    void konfeti.offsetWidth;
    konfeti.classList.add('peta-jalan-st');
  }
  if (coba) {
    var umpan = doc.getElementById('peta-coba-umpan');
    var pilihan = semua('[data-peta-jawab]', coba);
    pilihan.forEach(function (tombolJawab) {
      tombolJawab.addEventListener('click', function () {
        var benar = tombolJawab.getAttribute('data-peta-jawab') === coba.getAttribute('data-benar');
        pilihan.forEach(function (x) { x.classList.remove('peta-benar-st', 'peta-keliru-st'); });
        tombolJawab.classList.add(benar ? 'peta-benar-st' : 'peta-keliru-st');
        if (umpan) umpan.textContent = coba.getAttribute(benar ? 'data-umpan-benar' : 'data-umpan-salah');
        if (!benar) return;
        hujanKonfeti();
        ubahMaskot(coba.getAttribute('data-pose-hore'), coba.getAttribute('data-kata-hore'));
      });
    });
  }
})();"""

SKRIP_CETAK = """\
(function () {
  'use strict';
  if (!document.querySelectorAll || !window.print) return;
  Array.prototype.slice.call(document.querySelectorAll('[data-peta-cetak]')).forEach(function (tombol) {
    tombol.addEventListener('click', function () { window.print(); });
  });
})();"""
