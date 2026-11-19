"""Skrip peningkatan landing `/cek-kemampuan` (disetujui Pemilik 19 Nov 2026).

Tiga kasus: chip gejala mengganti panel jawaban, demo "tebak di langkah mana
salahnya", dan kartu hero yang terangkat. Konstanta string statis tanpa
interpolasi (hash CSP dihitung dari isi `<script>` di respons), tanpa network,
storage, `eval`, `innerHTML`, maupun event handler inline. Fallback tanpa JS:
semua jawaban gejala tampil sebagai `<details>` dan penjelasan demo ada di
`<details>`; markup tidak bergantung pada skrip ini.
"""

SKRIP_LANDING_CEK = """
(function () {
  "use strict";
  var KELAS_JS = "cek-js-st";

  function semua(selektor, akar) {
    return Array.prototype.slice.call((akar || document).querySelectorAll(selektor));
  }

  function satu(selektor, akar) {
    return (akar || document).querySelector(selektor);
  }

  function aktifkanGejala() {
    var akar = satu("[data-cek-gejala]");
    if (!akar) { return; }
    var chip = satu("[data-cek-chip]", akar);
    var daftar = satu("[data-cek-daftar]", akar);
    var panel = semua("[data-cek-panel]", akar);
    var tombol = chip ? semua("button", chip) : [];
    if (!chip || !daftar || tombol.length === 0 || tombol.length !== panel.length) { return; }

    function pilih(n) {
      tombol.forEach(function (t, i) {
        t.setAttribute("aria-pressed", i === n ? "true" : "false");
      });
      panel.forEach(function (p, i) {
        p.hidden = i !== n;
        p.open = i === n;
      });
    }

    tombol.forEach(function (t, i) {
      t.addEventListener("click", function () { pilih(i); });
    });
    chip.hidden = false;
    daftar.setAttribute("aria-live", "polite");
    akar.classList.add(KELAS_JS);
    pilih(0);
  }

  function aktifkanDemo() {
    var akar = satu("[data-cek-demo]");
    if (!akar) { return; }
    var item = semua("[data-cek-langkah]", akar);
    var umpan = satu("[data-cek-umpan]", akar);
    if (item.length === 0 || !umpan) { return; }
    var kunci = satu("[data-cek-kunci]", akar);
    var digit = satu("[data-cek-digit]", akar);
    var teksSalah = akar.getAttribute("data-umpan-salah") || "";
    var teksTepat = akar.getAttribute("data-umpan-tepat") || "";
    var selesai = false;

    var tombol = item.map(function (li) {
      var t = document.createElement("button");
      t.type = "button";
      while (li.firstChild) { t.appendChild(li.firstChild); }
      li.appendChild(t);
      return t;
    });

    function tebak(t, li) {
      if (selesai) { return; }
      if (li.hasAttribute("data-cek-tepat")) {
        selesai = true;
        t.classList.add("cek-tepat-st");
        umpan.className = "cek-umpan-st cek-umpan-ok-st";
        umpan.textContent = teksTepat;
        if (digit) { digit.classList.add("cek-digit-salah-st"); }
        tombol.forEach(function (b) { b.setAttribute("aria-disabled", "true"); });
        return;
      }
      t.classList.remove("cek-keliru-st");
      void t.offsetWidth;
      t.classList.add("cek-keliru-st");
      umpan.className = "cek-umpan-st";
      umpan.textContent = teksSalah;
    }

    tombol.forEach(function (t, i) {
      t.addEventListener("click", function () { tebak(t, item[i]); });
    });
    umpan.hidden = false;
    if (kunci) { kunci.hidden = true; }
  }

  function aktifkanKartuHero() {
    var kartu = semua(".cek-kt-st");
    if (kartu.length === 0) { return; }

    function angkat(k) {
      kartu.forEach(function (x) {
        x.classList.toggle("cek-kt-depan-st", x === k);
      });
    }

    kartu.forEach(function (k) {
      k.addEventListener("click", function () { angkat(k); });
      k.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          angkat(k);
        }
      });
    });
  }

  aktifkanGejala();
  aktifkanDemo();
  aktifkanKartuHero();
})();
"""
