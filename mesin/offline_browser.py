"""Banner offline berhash CSP; hanya event offline/online tanpa network.

Pengecualian zero-JS disetujui pemilik 2 Nov 2026. Skrip ini tidak memakai
fetch/XHR, storage, autosave, atau timer. Ia hanya menambah satu banner di
halaman yang sudah terbuka; halaman baru saat offline tetap ditangani browser.
"""

import base64
import hashlib

PESAN_OFFLINE = (
    "Sinyal terputus. Halaman ini belum bisa dimuat ulang. Isian yang sudah "
    "tertulis tetap ada di layar ini; jangan tutup halaman, lalu coba lagi "
    "saat sinyal kembali."
)
PESAN_ONLINE = "Sinyal kembali. Coba muat ulang halaman."
CATATAN_SINYAL = (
    "Aplikasi butuh sinyal. Kalau sinyal hilang, jangan tutup halaman; "
    "tunggu sampai kembali lalu kirim ulang."
)

SKRIP_OFFLINE = """\
(function () {
  'use strict';
  if (!window.addEventListener || !document.body || !document.createElement) return;
  if (document.getElementById('banner-offline-jagomat')) return;
  var banner = document.createElement('div');
  banner.id = 'banner-offline-jagomat';
  banner.className = 'banner-offline-st';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.hidden = true;
  document.body.insertBefore(banner, document.body.firstChild);
  function tampilkan(teks) {
    banner.textContent = teks;
    banner.hidden = false;
  }
  window.addEventListener('offline', function () {
    tampilkan(%(putus)r);
  });
  window.addEventListener('online', function () {
    tampilkan(%(kembali)r);
  });
})();""" % {"putus": PESAN_OFFLINE, "kembali": PESAN_ONLINE}

HASH_OFFLINE = base64.b64encode(
    hashlib.sha256(SKRIP_OFFLINE.encode("utf-8")).digest()
).decode("ascii")
