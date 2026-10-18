"""Enhancement tampilan tinjauan; tidak menilai, menyimpan, atau mengirim data."""
import base64
import hashlib

SKRIP_TINJAUAN = r"""(function () {
'use strict';
document.querySelectorAll('form[data-tinjauan-ringkas]').forEach(function (form) {
  var kartu = Array.from(form.querySelectorAll('[data-kartu-tinjauan]'));
  if (!kartu.length) return;
  function buka(target, fokus) {
    kartu.forEach(function (item) {
      var aktif = item === target;
      item.querySelector('[data-isi-kartu]').hidden = !aktif;
      item.querySelector('[data-buka-kartu]').setAttribute('aria-expanded', String(aktif));
    });
    if (fokus) target.querySelector('[data-buka-kartu]').focus();
  }
  function dariHash(fokus) {
    var id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return false; }
    var target = kartu.find(function (item) { return item.id === id; });
    if (!target) return false;
    buka(target, fokus);
    return true;
  }
  kartu.forEach(function (item) {
    var tombol = item.querySelector('[data-buka-kartu]');
    tombol.addEventListener('click', function () {
      if (tombol.getAttribute('aria-expanded') === 'true') {
        item.querySelector('[data-isi-kartu]').hidden = true;
        tombol.setAttribute('aria-expanded', 'false');
      } else buka(item, false);
    });
    tombol.disabled = false;
    var tambahan = item.querySelector('[data-catatan-tambahan]');
    var penanda = item.querySelector('[data-penanda-catatan]');
    item.querySelector('[data-isi-kartu]').addEventListener('input', function (e) {
      if (tambahan.contains(e.target)) return;
      penanda.hidden = false;
      penanda.textContent = 'Isian diubah — belum disimpan';
    });
    tambahan.addEventListener('input', function () {
      penanda.hidden = false;
      penanda.textContent = 'Catatan diubah — belum disimpan';
    });
    var native = item.querySelector('[data-lewati-native]');
    var centang = native.querySelector('input[type="checkbox"]');
    var lewati = item.querySelector('[data-lewati-tombol]');
    var status = item.querySelector('[data-status-lewati]');
    native.hidden = true;
    lewati.hidden = false;
    lewati.addEventListener('click', function () {
      var pesan = centang.checked ? 'Sertakan kembali soal ini? Penilaian akan diperiksa saat konfirmasi hasil sesi.' : lewati.dataset.konfirmasi;
      if (!window.confirm(pesan)) return;
      centang.checked = !centang.checked;
      centang.dispatchEvent(new Event('change', {bubbles: true}));
      lewati.textContent = centang.checked ? 'Sertakan kembali soal ini' : 'Lewati soal ini';
      status.textContent = (centang.checked ? 'Dilewati dari penilaian' : 'Disertakan dalam penilaian') + ' — belum disimpan';
      penanda.hidden = false;
      penanda.textContent = 'Pilihan lewati diubah — belum disimpan';
    });
  });
  var prioritas = kartu.find(function (item) { return item.dataset.prioritas === '2'; }) ||
    kartu.find(function (item) { return item.dataset.prioritas === '1'; }) || kartu[0];
  if (!dariHash(false)) buka(prioritas, false);
  window.addEventListener('hashchange', function () { dariHash(true); });
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var tautan = e.target.closest('a[href^="#tinjau-soal-"]');
    if (!tautan) return;
    var target = kartu.find(function (item) { return '#' + item.id === tautan.getAttribute('href'); });
    if (target) {
      e.preventDefault();
      history.pushState(null, '', '#' + target.id);
      buka(target, true);
      target.scrollIntoView({block: 'start'});
    }
  });
});
})();"""

HASH_TINJAUAN = base64.b64encode(
    hashlib.sha256(SKRIP_TINJAUAN.encode('utf-8')).digest()
).decode('ascii')
