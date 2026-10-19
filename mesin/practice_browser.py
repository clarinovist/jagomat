"""Enhancement lokal form latihan; tanpa jaringan, penyimpanan, atau penilaian."""
import base64
import hashlib
import re

SKRIP_LATIHAN = r"""(function () {
'use strict';
var form = document.querySelector('form[data-latihan-terpadu]');
if (!form) return;
var pilihan = document.querySelectorAll('input[name="mode_latihan"]');
var tombol = form.querySelector('[data-buat-latihan]');
var identitas = form.querySelector('input[name="inline_form"]');
function periksa() {
  var aktif = form.querySelector('fieldset[data-mode-latihan]:not([disabled])');
  var jumlah = aktif ? aktif.querySelectorAll('input[type="checkbox"][data-pilih]:checked').length : 0;
  tombol.disabled = !aktif || (aktif.dataset.modeLatihan === 'gabungan' && jumlah < 2) ||
    (aktif.dataset.modeLatihan === 'remedial' && (jumlah < 1 || jumlah > 3));
}
function ubah(mode) {
  var target = form.querySelector('fieldset[data-mode-latihan="' + mode + '"]');
  if (!target) return;
  var lama = form.id;
  form.querySelectorAll('fieldset[data-mode-latihan]').forEach(function (panel) {
    panel.disabled = panel !== target;
    panel.hidden = panel !== target;
  });
  form.action = target.dataset.url;
  form.id = target.dataset.formId;
  identitas.value = mode;
  document.querySelectorAll('[form]').forEach(function (el) {
    if (el.getAttribute('form') === lama) el.setAttribute('form', form.id);
  });
  periksa();
}
pilihan.forEach(function (radio) {
  radio.addEventListener('change', function () { if (radio.checked) ubah(radio.value); });
});
form.addEventListener('change', periksa);
form.addEventListener('submit', function (event) {
  if (event.submitter !== tombol) return;
  periksa();
  if (tombol.disabled) event.preventDefault();
});
periksa();
})();"""
HASH_LATIHAN = base64.b64encode(hashlib.sha256(SKRIP_LATIHAN.encode()).digest()).decode('ascii')


def memiliki_latihan(isi):
    """Hanya marker form aktual, bukan CSS atau teks escaped."""
    return bool(re.search(rb'<form\b[^>]*\bdata-latihan-terpadu(?:\s|=|>)', isi))
