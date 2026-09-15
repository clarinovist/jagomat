"""Peningkatan chat inline tanpa navigasi; skrip tetap dipagari hash CSP."""

import base64
import hashlib


SKRIP_CHAT = r"""(function () {
'use strict';
if (!window.fetch || !window.FormData || !window.DOMParser ||
    !window.AbortController || !window.URLSearchParams || !window.SubmitEvent ||
    !('submitter' in window.SubmitEvent.prototype)) return;
var berjalan = false;
var tertunda = null;
var statusUI = document.createElement('p');
statusUI.className = 'pendamping-info';
statusUI.setAttribute('role', 'status');
statusUI.setAttribute('aria-live', 'polite');
var ulang = document.createElement('button');
ulang.type = 'button';
ulang.className = 'pendamping-tombol pendamping-sekunder';
ulang.hidden = true;
var bidang = /^(inline_host|inline_host_id|inline_posisi|inline_nomor|chat|request_id|pesan|topik|jumlah_soal|mode|hadir_timer_mode|timer_mode|durasi_menit|timer_auto|sertakan_pemetaan|hadir_sertakan_pemetaan|(?:jwb_|kode_|cara_|cek_pemahaman_|hadir_dilewati_|dilewati_|hadir_belum_|belum_|catatan_tinjauan_|provenance_|jawaban_bantuan_|versi_tinjauan_)\d+)$/;
function pesanStatus(panel, teks) {
  var tempat = panel.querySelector('.pendamping-composer') || panel.querySelector('.pendamping-inline-isi');
  tempat.appendChild(statusUI);
  tempat.appendChild(ulang);
  statusUI.textContent = teks;
}
function kunci(panel, nilai) {
  panel.querySelectorAll('button').forEach(function (tombol) {
    if (tombol === ulang) return;
    if (nilai) {
      if (!tombol.disabled) { tombol.dataset.chatDikunci = '1'; tombol.disabled = true; }
    } else if (tombol.dataset.chatDikunci) {
      tombol.disabled = false;
      delete tombol.dataset.chatDikunci;
    }
  });
  var input = panel.querySelector('[name="pesan"]');
  if (input) input.readOnly = nilai;
}
function bolehPanel(panel, baru) {
  return baru && baru.classList.contains('pendamping-inline') &&
    baru.dataset.pendampingChat === panel.dataset.pendampingChat;
}
async function kirim(permintaan) {
  if (berjalan) return;
  berjalan = true;
  tertunda = permintaan;
  var panel = permintaan.panel;
  ulang.hidden = true;
  kunci(panel, true);
  panel.setAttribute('aria-busy', 'true');
  pesanStatus(panel, permintaan.aksi === 'pesan' ?
    'Pendamping sedang menyiapkan jawaban… Pesanmu tetap ada di sini.' : 'Memeriksa status jawaban…');
  var pengendali = new AbortController();
  var tenggat = setTimeout(function () { pengendali.abort(); }, 90000);
  try {
    var respons = await fetch('/pendamping/inline/' + permintaan.aksi, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: permintaan.data.toString(), signal: pengendali.signal
    });
    if (![200, 400, 409].includes(respons.status) ||
        !(respons.headers.get('Content-Type') || '').startsWith('text/html')) {
      throw new Error(respons.status === 401 ? 'login' :
        ([403, 404].includes(respons.status) ? 'akses' : 'respons'));
    }
    var dokumen = new DOMParser().parseFromString(await respons.text(), 'text/html');
    var baru = dokumen.getElementById(panel.id);
    if (!bolehPanel(panel, baru)) throw new Error('respons');
    var selesai = Array.from(baru.querySelectorAll('[data-request-id]')).some(function (item) {
      return item.dataset.requestId === permintaan.data.get('request_id') + ':jawaban';
    });
    if (!selesai && baru.querySelector('[formaction="/pendamping/inline/status"]')) {
      permintaan.aksi = 'status';
      permintaan.data.delete('pesan');
      pesanStatus(panel, 'Jawaban masih ditunggu. Periksa status tanpa mengirim pesan lagi.');
      ulang.textContent = 'Periksa status';
      ulang.hidden = false;
      return;
    }
    // Isian preferensi lokal bukan hasil chat; jangan timpa suntingan pengguna.
    panel.querySelectorAll('textarea[name^="isi_memori"]').forEach(function (lama) {
      var identitas = lama.form && lama.form.querySelector('[name="memori"]');
      var pengganti = Array.from(baru.querySelectorAll('textarea')).find(function (item) {
        var pasangan = item.form && item.form.querySelector('[name="memori"]');
        return item.name === lama.name && (!identitas ||
          (pasangan && pasangan.value === identitas.value));
      });
      if (pengganti) pengganti.value = lama.value;
    });
    var fokus = document.activeElement;
    var fokusDiChat = panel.contains(fokus) ||
      (fokus === document.body && permintaan.fokusDiChat);
    var gulir = window.scrollY;
    var inputBaru = baru.querySelector('[name="pesan"]');
    if (!selesai && !inputBaru && permintaan.teks) {
      var salinan = document.createElement('label');
      salinan.textContent = 'Balasan belum tersedia — salin pesanmu sebelum meninggalkan halaman';
      inputBaru = document.createElement('textarea');
      inputBaru.readOnly = true;
      salinan.appendChild(inputBaru);
      baru.querySelector('.pendamping-inline-isi').appendChild(salinan);
    }
    if (!selesai && inputBaru) inputBaru.value = permintaan.teks;
    // Jangan mengganti DOM form host: edit koreksi selama menunggu tetap utuh.
    panel.replaceWith(baru);
    tertunda = null;
    kunci(baru, false);
    pesanStatus(baru, selesai ? 'Jawaban sudah tersedia.' :
      'Balasan belum tersedia. Teks pesanmu tetap ada; periksa keterangan di atas sebelum mencoba lagi.');
    if (fokusDiChat) {
      var tujuan = inputBaru || baru.querySelector('summary');
      if (tujuan) tujuan.focus({preventScroll: true});
    }
    window.scrollTo(window.scrollX, gulir);
  } catch (galat) {
    pesanStatus(panel, galat.message === 'login' ?
      'Sesi masuk berakhir. Salin pesanmu sebelum masuk lagi; pesan tidak dikirim ulang otomatis.' :
      (galat.message === 'akses' ?
      'Percakapan tidak dapat diakses. Salin pesanmu sebelum membuka ulang bantuan.' :
      'Jawaban belum dapat dipastikan. Pesanmu tetap ada. Coba lagi memakai permintaan yang sama; tidak dikirim ulang otomatis.'));
    ulang.textContent = permintaan.aksi === 'status' ? 'Periksa status' : 'Coba lagi';
    ulang.hidden = ['login', 'akses'].includes(galat.message);
  } finally {
    clearTimeout(tenggat);
    panel.removeAttribute('aria-busy');
    berjalan = false;
  }
}
ulang.addEventListener('click', function () { if (tertunda) kirim(tertunda); });
document.addEventListener('submit', function (kejadian) {
  var tombol = kejadian.submitter;
  var panel = tombol && tombol.closest('.pendamping-inline[data-pendamping-chat]');
  if (!panel) return;
  if (tertunda) { kejadian.preventDefault(); return; }
  var action = tombol.getAttribute('formaction');
  if (!['/pendamping/inline/pesan', '/pendamping/inline/status'].includes(action)) return;
  kejadian.preventDefault();
  var data = new URLSearchParams();
  new FormData(kejadian.target).forEach(function (nilai, nama) {
    if (bidang.test(nama) && typeof nilai === 'string') data.append(nama, nilai);
  });
  if (tombol.name === 'data_aksi') {
    new URLSearchParams(tombol.value).forEach(function (nilai, nama) {
      if (nama === 'request_id') data.set(nama, nilai);
    });
  }
  var teks = data.get('pesan') || '';
  if (action.endsWith('/pesan') && !teks.trim()) {
    pesanStatus(panel, 'Tulis pesan dulu sebelum mengirim.');
    panel.querySelector('[name="pesan"]').focus();
    return;
  }
  if (action.endsWith('/status')) data.delete('pesan');
  kirim({panel: panel, data: data, teks: teks, aksi: action.split('/').pop(),
    fokusDiChat: panel.contains(document.activeElement)});
});
})();"""

HASH_CSP = base64.b64encode(hashlib.sha256(SKRIP_CHAT.encode("utf-8")).digest()).decode("ascii")


def lengkapi_respons(isi: bytes):
    """Izin JS hanya untuk panel chat server; consent/arsip tetap tanpa skrip."""
    if b'data-pendamping-chat="' not in isi:
        return isi, ""
    skrip = ('<script>' + SKRIP_CHAT + '</script>').encode("utf-8")
    return (
        isi.replace(b"</body>", skrip + b"</body>", 1),
        "script-src 'sha256-" + HASH_CSP + "'; connect-src 'self'; ",
    )
