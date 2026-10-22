"""Enhancement filter instan beranda guru; tidak menulis, mengirim, atau menyimpan apa pun.

Chip tetap tautan GET biasa (fallback tanpa JS). Skrip hanya menyembunyikan/menampilkan
kartu yang sudah dirender server untuk anak milik guru ini, memperbarui penanda chip,
hitungan, dan URL (replaceState); tidak ada koneksi jaringan.
"""
import base64
import hashlib

SKRIP_FILTER_GURU = r"""(function () {
'use strict';
var daftar = document.querySelector('[data-daftar-guru]');
if (!daftar) return;
var kartu = Array.prototype.slice.call(daftar.querySelectorAll('[data-kelompok]'));
var chip = Array.prototype.slice.call(document.querySelectorAll('a[data-chip-kelompok]'));
var hasil = document.querySelector('[data-hasil-guru]');
var kosong = document.querySelector('[data-kosong-guru]');
var form = document.getElementById('guru-filter');
var hapus = document.getElementById('guru-hapus-filter');
var total = hasil ? parseInt(hasil.getAttribute('data-total'), 10) : kartu.length;
function sinkronkanForm(kelompok) {
  if (!form) return;
  var isi = form.querySelector('input[name="kelompok"]');
  if (kelompok === 'semua') {
    if (isi) isi.parentNode.removeChild(isi);
  } else {
    if (!isi) {
      isi = document.createElement('input');
      isi.type = 'hidden';
      isi.name = 'kelompok';
      form.appendChild(isi);
    }
    isi.value = kelompok;
  }
  if (hapus) hapus.setAttribute('href', kelompok === 'semua' ? '/guru' : '/guru?kelompok=' + encodeURIComponent(kelompok));
}
function terapkan(kelompok, href) {
  var tampil = 0;
  kartu.forEach(function (k) {
    var cocok = kelompok === 'semua' || k.getAttribute('data-kelompok') === kelompok;
    k.hidden = !cocok;
    if (cocok) tampil += 1;
  });
  chip.forEach(function (c) {
    if (c.getAttribute('data-chip-kelompok') === kelompok) c.setAttribute('aria-current', 'true');
    else c.removeAttribute('aria-current');
  });
  if (hasil) hasil.textContent = tampil + ' dari ' + total + ' siswa ditampilkan.';
  if (kosong) kosong.hidden = tampil !== 0;
  sinkronkanForm(kelompok);
  try { history.replaceState(null, '', href); } catch (_) { /* URL tetap; tampilan sudah benar */ }
}
chip.forEach(function (c) {
  c.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    terapkan(c.getAttribute('data-chip-kelompok'), c.getAttribute('href'));
  });
});
})();"""

HASH_FILTER_GURU = base64.b64encode(
    hashlib.sha256(SKRIP_FILTER_GURU.encode('utf-8')).digest()
).decode('ascii')
