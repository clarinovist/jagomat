"""Enhancement browser berhash; form native tetap jalur fallback kanonik."""

import base64
import hashlib
import re


SKRIP_PILIHAN_ISI = r"""(function () {
'use strict';
if (!document.querySelectorAll) return;
document.querySelectorAll('[data-pilihan-isi-otomatis]').forEach(function (pilihan) {
  var form = pilihan.form;
  if (!form || typeof form.requestSubmit !== 'function' ||
      typeof form.querySelector !== 'function') return;
  var tombol = form.querySelector('button[data-pilihan-isi-fallback]');
  if (!tombol) return;
  pilihan.addEventListener('change', function () { form.requestSubmit(tombol); });
  tombol.hidden = true;
});
})();"""


SKRIP_CHAT = r"""(function () {
'use strict';
if (!window.fetch || !window.FormData || !window.DOMParser || !window.AbortController ||
    !window.URLSearchParams || !window.SubmitEvent || !('submitter' in SubmitEvent.prototype)) return;
var berjalan = null;
var pembuka = null;
var tertunda = null;
var generasi = 0;
var aksiPanel = /^(buka|persetujuan|mulai|riwayat|pilih-sumber|pesan|status)$/;
var identitas = ['inline_host', 'inline_host_id', 'inline_posisi', 'inline_nomor'];
var bidang = {
  buka: [], persetujuan: ['kebijakan', 'setuju'],
  mulai: ['resource_version', 'kategori', 'request_id', 'setuju_konteks', 'mode_chat'],
  riwayat: ['chat', 'pilih_chat', 'halaman'], 'pilih-sumber': ['pilih_nomor'],
  pesan: ['chat', 'request_id', 'pesan'], status: ['chat', 'request_id']
};
function jalurSah(aksi) {
  // Tidak menerima URL absolut, query, fragment, atau rute yang mirip.
  if (typeof aksi !== 'string' || !aksi.startsWith('/pendamping/inline/')) return '';
  var nama = aksi.slice('/pendamping/inline/'.length);
  if (aksiPanel.test(nama)) return nama;
  return /^buka\/sesi\/[1-9][0-9]{0,18}\/(sesi|soal\/[1-9][0-9]{0,18})$/.test(nama) ? 'buka' : '';
}
function binding(elemen) {
  var d = elemen.dataset;
  return {host: d.pendampingHost, id: d.pendampingHostId, posisi: d.pendampingPosisi,
    resource: d.pendampingResource, resourceId: d.pendampingResourceId,
    chat: d.pendampingChat || ''};
}
function cocokPanel(harap, baru, aksi, data) {
  if (!baru || !baru.classList.contains('pendamping-panel-kanan')) return false;
  var b = binding(baru);
  if (!harap.host || !harap.id || b.host !== harap.host || b.id !== harap.id) return false;
  var posisi = harap.posisi, resource = harap.resource, resourceId = harap.resourceId;
  if (aksi === 'pilih-sumber') {
    if (harap.host !== 'sesi' || harap.resource !== 'sesi') return false;
    var nomor = data.get('pilih_nomor');
    if (nomor === null || (nomor && !/^[1-9][0-9]{0,18}$/.test(nomor))) return false;
    posisi = resource = nomor ? 'soal' : 'sesi';
    resourceId = harap.id + (nomor ? ':' + nomor : '');
  }
  if (!resource || !resourceId || b.posisi !== posisi || b.resource !== resource ||
      b.resourceId !== resourceId) return false;
  if (aksi === 'mulai') return !b.chat || /^chat_[0-9a-f]{32}$/.test(b.chat);
  var chat = aksi === 'riwayat' ? (data.get('pilih_chat') || harap.chat) : harap.chat;
  if (b.chat !== chat) return false;
  return !['pesan', 'status'].includes(aksi) ||
    (!!chat && baru.dataset.pendampingRequest === data.get('request_id'));
}
function payload(form, tombol, batas, aksi) {
  var data = new URLSearchParams();
  var boleh = identitas.concat(bidang[aksi]);
  // Hanya kontrol panel/pembuka, bukan seluruh hidden atau FormData pekerjaan.
  batas.querySelectorAll('input, select, textarea').forEach(function (input) {
    if (input.form !== form || input.disabled || !boleh.includes(input.name) ||
        (['checkbox', 'radio'].includes(input.type) && !input.checked)) return;
    if (aksi === 'buka' && input.type !== 'hidden') return;
    data.append(input.name, input.value);
  });
  if (boleh.includes(tombol.name)) data.append(tombol.name, tombol.value);
  if (tombol.name === 'data_aksi') {
    new URLSearchParams(tombol.value).forEach(function (nilai, nama) {
      if (boleh.includes(nama)) data.set(nama, nilai);
    });
  }
  // Native dapat menyimpan identitas sekali di host; gunakan binding panel,
  // bukan membaca hidden pekerjaan di luar batas panel.
  if (aksi !== 'buka') {
    var b = binding(batas);
    data.set('inline_host', b.host);
    data.set('inline_host_id', b.id);
    data.set('inline_posisi', b.posisi);
    if (b.posisi === 'soal') data.set('inline_nomor', b.resourceId.split(':')[1]);
  }
  return data;
}
function formPekerjaan() {
  if (!pembuka) return null;
  var b = binding(pembuka.bungkus);
  var tab = document.querySelector('.tab-radio-st:checked');
  var jenis = tab && {'tab-baru': 'manual', 'tab-gabungan': 'gabungan', 'tab-ulang': 'remedial'}[tab.id];
  return (b.host === 'anak' && b.posisi === 'latihan' && jenis &&
    document.getElementById('form-latihan-' + jenis + '-' + b.id)) || pembuka.form;
}
function lengkapiFallback(form) {
  // Aksi native dari panel enhanced tetap membawa draf request-local.
  // Hanya form panel yang dilengkapi, form pekerjaan tidak pernah diubah.
  var pekerjaan = formPekerjaan();
  if (!pekerjaan || form === pekerjaan) return;
  var draf = /^(inline_form|topik|jumlah_soal|mode|hadir_timer_mode|timer_mode|durasi_menit|timer_auto|format_jawaban|profil_parameter|versi_pilihan_isi|topik_dibandingkan|template_id|sumber_sesi_id|sertakan_pemetaan|hadir_sertakan_pemetaan|(?:jwb_|kode_|cara_|cek_pemahaman_|hadir_dilewati_|dilewati_|hadir_belum_|belum_|catatan_tinjauan_|provenance_|jawaban_bantuan_|versi_tinjauan_)\d+)$/;
  form.querySelectorAll('[data-draf-native]').forEach(function (item) { item.remove(); });
  Array.from(pekerjaan.elements).forEach(function (input) {
    if (!draf.test(input.name) || input.disabled ||
        (['checkbox', 'radio'].includes(input.type) && !input.checked)) return;
    var salinan = document.createElement('input');
    salinan.type = 'hidden'; salinan.name = input.name; salinan.value = input.value;
    salinan.dataset.drafNative = '1'; form.appendChild(salinan);
  });
}
function pesanStatus(panel, teks, permintaan) {
  var tempat = panel.querySelector('.pendamping-composer') ||
    panel.querySelector('.pendamping-inline-isi') || panel;
  var status = tempat.querySelector('[data-status-browser]');
  if (!status) {
    status = document.createElement('p');
    status.className = 'pendamping-info';
    status.dataset.statusBrowser = '1';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    tempat.appendChild(status);
  }
  status.textContent = teks;
  var lama = panel.querySelector('[data-ulang-browser]');
  if (lama) lama.remove();
  if (permintaan) {
    var ulang = document.createElement('button');
    ulang.type = 'button';
    ulang.className = 'pendamping-tombol pendamping-sekunder';
    ulang.dataset.ulangBrowser = '1';
    ulang.textContent = permintaan.aksi === 'status' ? 'Periksa status' : 'Coba lagi';
    ulang.addEventListener('click', function () { kirim(permintaan); });
    tempat.appendChild(ulang);
  }
}
function kunci(panel, nilai) {
  panel.querySelectorAll('button').forEach(function (tombol) {
    if (tombol.classList.contains('pendamping-tutup')) return;
    if (nilai && !tombol.disabled) { tombol.dataset.chatDikunci = '1'; tombol.disabled = true; }
    else if (!nilai && tombol.dataset.chatDikunci) {
      tombol.disabled = false; delete tombol.dataset.chatDikunci;
    }
  });
  var input = panel.querySelector('[name="pesan"]');
  if (input) input.readOnly = nilai;
  if (nilai) panel.setAttribute('aria-busy', 'true');
  else panel.removeAttribute('aria-busy');
}
function tutupLokal(panel) {
  generasi += 1;
  berjalan = tertunda = null;
  panel.remove();
  pembuka.bungkus.hidden = false;
  pembuka.tombol.setAttribute('aria-expanded', 'false');
  var tujuan = Array.from(document.querySelectorAll('.pendamping-pemicu')).find(function (item) {
    return item.getClientRects().length && getComputedStyle(item).visibility !== 'hidden';
  }) || pembuka.tombol;
  tujuan.focus({preventScroll: true});
  window.scrollTo(pembuka.x, pembuka.y);
  pembuka = null;
}
async function kirim(p) {
  if (berjalan || !p.panel.isConnected || p.generasi !== generasi || jalurSah(p.jalur) !== p.aksi) return;
  berjalan = p;
  var panel = p.panel, aksi = p.aksi;
  var chat = ['pesan', 'status'].includes(aksi);
  if (chat) tertunda = p;
  var fokusDiPanel = panel.contains(document.activeElement);
  var x = window.scrollX, y = window.scrollY;
  kunci(panel, true);
  pesanStatus(panel, chat ? 'Jawaban sedang ditunggu. Pesan tidak dikirim ulang otomatis.' : 'Membuka bantuan…');
  var pengendali = new AbortController();
  var tenggat = setTimeout(function () { pengendali.abort(); }, 90000);
  function masihAktif() { return panel.isConnected && p.generasi === generasi; }
  try {
    var respons = await fetch(p.jalur, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-Pendamping-Panel': 'fragment'},
      body: p.data.toString(), signal: pengendali.signal
    });
    if (![200, 400, 409].includes(respons.status) ||
        !(respons.headers.get('Content-Type') || '').startsWith('text/html')) {
      throw new Error(respons.status === 401 ? 'login' :
        ([403, 404].includes(respons.status) ? 'akses' : 'respons'));
    }
    var dokumen = new DOMParser().parseFromString(await respons.text(), 'text/html');
    if (!masihAktif()) return;
    var semua = dokumen.querySelectorAll('.pendamping-panel-kanan');
    var baru = semua.length === 1 ? semua[0] : null;
    if (!cocokPanel(p.harap, baru, aksi, p.data)) throw new Error('respons');
    var selesai = chat && Array.from(baru.querySelectorAll('[data-request-id]')).some(function (item) {
      return item.dataset.requestId === p.data.get('request_id') + ':jawaban';
    });
    if (chat && !selesai && baru.querySelector('[formaction="/pendamping/inline/status"]')) {
      p.aksi = 'status'; p.jalur = '/pendamping/inline/status'; p.data.delete('pesan');
      pesanStatus(panel, 'Jawaban masih ditunggu. Periksa status tanpa mengirim pesan lagi.', p);
      return;
    }
    // Preferensi yang sedang disunting juga bukan hasil provider.
    panel.querySelectorAll('textarea[name^="isi_memori"]').forEach(function (lama) {
      var pasangan = Array.from(baru.querySelectorAll('textarea')).find(function (item) {
        var idLama = lama.form && lama.form.querySelector('[name="memori"]');
        var idBaru = item.form && item.form.querySelector('[name="memori"]');
        return item.name === lama.name && (!idLama || (idBaru && idLama.value === idBaru.value));
      });
      if (pasangan) pasangan.value = lama.value;
    });
    var input = baru.querySelector('[name="pesan"]');
    var drafLokal = panel.querySelector('[name="pesan"]');
    if (!chat && input && drafLokal && binding(baru).chat === p.harap.chat) input.value = drafLokal.value;
    if (chat && !selesai && p.teks) {
      if (!input) {
        var label = document.createElement('label');
        label.textContent = 'Balasan belum tersedia — salin pesanmu sebelum meninggalkan halaman';
        input = document.createElement('textarea'); input.readOnly = true;
        label.appendChild(input); baru.querySelector('.pendamping-inline-isi').appendChild(label);
      }
      input.value = p.teks;
    }
    if (aksi === 'buka') {
      pembuka = {tombol: p.tombol, form: p.tombol.form, bungkus: panel, x: x, y: y};
      panel.querySelectorAll('[data-status-browser]').forEach(function (item) { item.remove(); });
      panel.hidden = true;
      p.tombol.setAttribute('aria-expanded', 'true');
      (document.querySelector('.pendamping-editorial-st') || panel.parentElement).appendChild(baru);
    } else {
      // Hanya panel diganti, tidak form pekerjaan atau seluruh host.
      panel.replaceWith(baru);
    }
    tertunda = null;
    if (chat) pesanStatus(baru, selesai ? 'Jawaban sudah tersedia.' : 'Balasan belum tersedia. Pesanmu tetap ada.');
    // Tidak autofocus composer/keyboard HP; fokus tetap pada kontrol panel.
    var tujuan = baru.querySelector('.pendamping-tutup');
    if ((fokusDiPanel || aksi === 'buka') && tujuan) tujuan.focus({preventScroll: true});
    window.scrollTo(x, y);
  } catch (galat) {
    if (!masihAktif()) return;
    pesanStatus(panel, galat.message === 'login' ?
      'Sesi masuk berakhir. Salin pesanmu sebelum masuk lagi; tidak ada pengiriman ulang otomatis.' :
      (galat.message === 'akses' ? 'Percakapan tidak dapat diakses. Isian pekerjaan tetap ada.' :
      'Balasan belum tersedia atau panel belum dapat diperbarui. Isian tetap ada; tidak ada pengiriman ulang otomatis.'),
      chat && !['login', 'akses'].includes(galat.message) ? p : null);
  } finally {
    clearTimeout(tenggat);
    if (masihAktif()) kunci(panel, false);
    if (berjalan === p) berjalan = null;
  }
}
document.addEventListener('submit', function (kejadian) {
  var tombol = kejadian.submitter;
  if (!tombol) return;
  var panel = tombol.closest('.pendamping-panel-kanan');
  var jalur = tombol.getAttribute('formaction') || kejadian.target.getAttribute('action') || '';
  if (panel && jalur === '/pendamping/inline/tutup') {
    if (!pembuka) return; // Bookmark/fallback perlu POST native untuk mengembalikan entry point.
    kejadian.preventDefault(); tutupLokal(panel); return;
  }
  var buka = !panel && tombol.classList.contains('pendamping-pemicu');
  if (!panel && !buka) return;
  var aksi = jalurSah(jalur);
  // Aksi memori/usulan tetap native, tidak memperoleh izin fetch baru.
  if (!aksi) {
    if (panel && /^\/pendamping\/inline\/(tinjau|konfirmasi-usulan|tinjau-hapus-memori|batal-hapus-memori|konfirmasi-memori|ubah-memori|hapus-memori|aktifkan-memori|nonaktifkan-memori)$/.test(jalur)) {
      lengkapiFallback(kejadian.target);
    }
    return;
  }
  kejadian.preventDefault();
  if (berjalan || tertunda || (buka && document.querySelector('.pendamping-panel-kanan'))) return;
  if (buka) panel = tombol.closest('.pendamping-buka-inline');
  if (!panel || (buka && aksi !== 'buka')) return;
  var data = payload(kejadian.target, tombol, panel, aksi);
  var teks = data.get('pesan') || '';
  if (aksi === 'pesan' && !teks.trim()) {
    pesanStatus(panel, 'Tulis pesan dulu sebelum mengirim.'); return;
  }
  kirim({panel: panel, tombol: tombol, harap: binding(panel), generasi: generasi,
    jalur: jalur, aksi: aksi, data: data, teks: teks});
});
})();"""

HASH_CSP = base64.b64encode(hashlib.sha256(SKRIP_CHAT.encode("utf-8")).digest()).decode("ascii")
HASH_PILIHAN_ISI = base64.b64encode(
    hashlib.sha256(SKRIP_PILIHAN_ISI.encode("utf-8")).digest()
).decode("ascii")


def memiliki_panel(isi: bytes) -> bool:
    """Deteksi markup nyata, bukan nama kelas di stylesheet halaman murid."""
    return bool(re.search(
        rb'<(?:aside|span)\b[^>]*\bclass="[^"]*\bpendamping-(?:panel-kanan|buka-inline)\b', isi
    ) or re.search(rb'<aside\b[^>]*data-pendamping-chat="', isi))


def memiliki_pilihan_isi(isi: bytes) -> bool:
    """Deteksi atribut select aktual, bukan teks pengguna yang kebetulan sama."""
    return bool(re.search(
        rb'<select\b[^>]*\bdata-pilihan-isi-otomatis(?:\s|=|>)', isi
    ))


def memiliki_enhancement(isi: bytes) -> bool:
    """Halaman memerlukan salah satu skrip kecil berhash yang diizinkan."""
    return memiliki_panel(isi) or memiliki_pilihan_isi(isi)


def lengkapi_respons(isi: bytes):
    """Sisipkan hanya enhancement yang ditandai, dengan hash CSP masing-masing."""
    if b'</body>' not in isi:
        return isi, ""
    skrip = []
    hash_skrip = []
    izin_koneksi = ""
    if memiliki_pilihan_isi(isi):
        skrip.append(SKRIP_PILIHAN_ISI)
        hash_skrip.append(HASH_PILIHAN_ISI)
    if memiliki_panel(isi):
        skrip.append(SKRIP_CHAT)
        hash_skrip.append(HASH_CSP)
        izin_koneksi = "connect-src 'self'; "
    if not skrip:
        return isi, ""
    markup = ''.join('<script>' + item + '</script>' for item in skrip).encode("utf-8")
    izin = "script-src " + " ".join("'sha256-" + item + "'" for item in hash_skrip) + "; "
    return isi.replace(b"</body>", markup + b"</body>", 1), izin + izin_koneksi
