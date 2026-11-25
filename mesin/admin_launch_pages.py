"""Panel layanan ringkas; renderer hanya menerima proyeksi terjaga."""

import html
from datetime import datetime

import product_analytics as d
import support_settings as dukungan
import admin_labels as L
import admin_harga_pages as hg
import admin_sakelar_pages as sak
from admin_daftar_pages import kartu_tabel, sel_nama
from admin_komponen import kartu_akan_dimatikan, kepala_cari, lipat_aksi  # noqa: F401 (dipakai admin_launch_http)


def e(nilai):
    return html.escape(str(nilai),quote=True)


def rupiah(n):
    return 'Rp'+format(n,',').replace(',','.')


def tanggal(epoch):
    return L.tanggal(epoch)


def info(label,isi):
    return '<details class="admin-info"><summary aria-label="Info %s">ⓘ</summary><p>%s</p></details>'%(e(label),e(isi))


def tabel(kepala,baris, *, label='Rincian layanan'):
    return '<div class="admin-tabel-wrap" tabindex="0" role="region" aria-label="'+e(label)+'"><table class="admin-tabel"><thead><tr>'+''.join('<th scope="col">'+e(x)+'</th>' for x in kepala)+'</tr></thead><tbody>'+(''.join(baris) or '<tr><td colspan="%d" class="admin-kosong">Belum ada catatan untuk tampilan ini. Data muncul setelah aktivitas terkait tercatat.</td></tr>'%len(kepala))+'</tbody></table></div>'


def formulir(aksi,csrf,token,isi,tombol,hidden=(),konfirmasi=None):
    fields=(('csrf',csrf),('tinjauan',token),*hidden)
    atribut=' data-konfirmasi="%s"'%e(konfirmasi) if konfirmasi else ''
    return '<form method="post" action="/admin/layanan/'+e(aksi)+'"'+atribut+'>'+''.join('<input type="hidden" name="%s" value="%s">'%(e(k),e(v)) for k,v in fields)+isi+'<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label><button class="admin-tombol" type="submit">'+e(tombol)+'</button></form>'


def _form_cari_langganan(csrf,cari):
    if not csrf: return ''
    return kepala_cari('<form class="admin-form-cari" method="post" action="/admin/layanan/cari">'
            '<input type="hidden" name="csrf" value="%s">'
            '<label class="admin-cari"><span class="admin-sr">Cari akun orang tua</span>'
            '<input name="cari" maxlength="80" value="%s" placeholder="Cari akun orang tua"></label>'
            '<button class="admin-tombol admin-tombol-sekunder" type="submit">Cari</button></form>')%(e(csrf),e(cari))


def _pager_langganan(halaman,total,cari,csrf):
    kontrol=''
    for nomor, label in ((halaman-1, 'Sebelumnya'), (halaman+1, 'Berikutnya')):
        if nomor < 1 or (nomor > halaman and halaman*25 >= total):
            continue
        if cari and csrf:
            kontrol += ('<form method="post" action="/admin/layanan/cari">'
                        '<input type="hidden" name="csrf" value="%s">'
                        '<input type="hidden" name="cari" value="%s">'
                        '<input type="hidden" name="halaman" value="%d">'
                        '<button class="admin-tombol admin-tombol-sekunder" type="submit">%s</button></form>'
                        % (e(csrf), e(cari), nomor, label))
        else:
            kontrol += '<a class="admin-tautan" href="/admin?section=langganan&amp;halaman=%d">%s</a>' % (nomor,label)
    return '<div class="admin-aksi-baca">%s</div>'%kontrol if kontrol else ''


def daftar_langganan(rows,total,*,halaman,cari,csrf,kandidat=(),forms=None):
    baris=''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'%(
        sel_nama(r['alias'],'/admin?section=langganan&id=%s'%r['akun_id']),tanggal(r['mulai']),
        '<span class="admin-badge bien">Ya</span>' if r['peserta_promo'] else '<span class="admin-badge">Tidak</span>',
        e(L.label_status(r['asal']))) for r in rows) or '<tr><td colspan="4" class="admin-kosong">Belum ada catatan untuk tampilan ini.</td></tr>'
    kartu_kandidat=''
    if cari and kandidat:
        baris_k=''.join('<tr><td>%s</td><td>%s</td></tr>'%(e(k['alias']),(forms or {}).get(k['akun_id'],'Tidak ada tindakan')) for k in kandidat)
        kartu_kandidat=('<section class="admin-kartu"><h2>Belum terdaftar di langganan · %d</h2>'%len(kandidat)
                        +tabel(('Keluarga','Tindakan'),baris_k,label='Keluarga calon transisi')
                        +'<p class="admin-meta">Jalur transisi untuk akun lama sebelum sinkron registrasi publik. Satu aksi melengkapi enrollment dan paket v2 akun; tidak membuat pembayaran dan tidak mengaktifkan paywall.</p></section>')
    kepala=tuple('<th scope="col">%s</th>'%x for x in ('Keluarga','Mulai','Peserta promo','Sumber'))
    stat='<section class="admin-grid-stat" aria-label="Ringkasan langganan"><div class="admin-stat"><h2>Keluarga tercatat</h2><div><strong>%d</strong></div></div></section>'%total
    return (_form_cari_langganan(csrf,cari)+stat
            +kartu_tabel('Langganan keluarga',kepala,baris,_pager_langganan(halaman,total,cari,csrf),keterangan='%d tercatat · Halaman %d'%(total,halaman))
            +kartu_kandidat
            +'<p class="admin-meta">Akun yang belum diikutkan tidak dianggap kedaluwarsa. Panel ini tidak mengaktifkan paywall.</p>')


AKSES={'promo':'Promo aktif','trial':'Masa coba','aktif':'Aktif','expired':'Masa aktif habis','kedaluwarsa':'Masa aktif habis','belum_terverifikasi':'Belum terverifikasi','paid':'Berbayar'}
STATUS={'grant':'Hak akses tercatat','lunas':'Pembayaran tercatat','perlu_diperiksa':'Perlu diperiksa','belum_terverifikasi':'Belum terverifikasi','settlement':'Settlement teramati','ditutup':'Ditutup tanpa pembayaran'}


def detail_langganan(r,forms):
    a=r['akses']
    isi='<p class="admin-jejak"><a href="/admin?section=langganan">← Kembali ke daftar langganan</a></p><section class="admin-kartu"><h2>%s</h2><dl class="admin-rincian"><dt>Status akses</dt><dd>%s</dd><dt>Batas periode</dt><dd>%s</dd><dt>Cakupan terbaru</dt><dd>%d profil</dd><dt>Promo tersisa</dt><dd>%d periode berbayar</dd></dl></section>'%(e(r['alias']),e(AKSES.get(a.status,a.status)),tanggal(a.akhir),r['jumlah_profil'],r['promo_tersisa'])
    baris=[]
    for i in r['invoices']:
        g=i['grant']
        baris.append('<tr><td>%s<br><small>Periode %d</small></td><td>%s<br>%d profil</td><td>%s</td><td>%s</td><td>%s</td></tr>'%(L.referensi(i['invoice_id']),i['urutan'],rupiah(i['rupiah']),i['jumlah_profil'],e(STATUS.get(i['status'],i['status'])),tanggal(g.periode.akhir) if g else 'Belum ada grant',forms.get(i['invoice_id'],'Tidak ada tindakan provider')))
    return isi+'<section class="admin-kartu"><h2>Invoice dan hak akses</h2>'+tabel(('Referensi','Nominal','Pembayaran','Akhir grant','Tindakan'),baris,label='Invoice dan hak akses')+'</section><p class="admin-meta">Pembayaran tercatat tidak selalu berarti akses aktif sekarang. Refund, pembayaran lebih, dan kasus terlambat tetap perlu keputusan; tidak ada tombol paksa lunas.</p>'


def antrean(rows,total,halaman=1):
    baris=[]
    for r in rows:
        link='/admin?section=langganan&amp;id='+e(r['akun']) if r['sumber'] in ('pembayaran','layanan') and r['akun'].startswith('akun_') else '/admin?section=riwayat'
        baris.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><a href="%s">Periksa sumber</a></td></tr>'%(e(L.label_status(r['sumber'])),L.referensi(r['ref']),'<span class="admin-badge perhatian">'+e(L.label_status(r['status']))+'</span>',tanggal(r['waktu']),link))
    pager = ''
    if halaman > 1:
        pager += '<a class="admin-tautan" href="/admin?section=perhatian&amp;halaman=%d">Sebelumnya</a> ' % (halaman-1)
    if halaman*25 < total:
        pager += '<a class="admin-tautan" href="/admin?section=perhatian&amp;halaman=%d">Berikutnya</a>' % (halaman+1)
    return '<section class="admin-kartu"><h2>Perlu ditangani · %d</h2>'%total+tabel(('Sumber','Referensi','Status','Sejak','Lanjut'),baris,label='Antrean layanan')+('<nav class="admin-pager" aria-label="Halaman antrean">'+pager+'</nav>' if pager else '')+'</section><p class="admin-meta">Status belum pasti bukan gagal aman. Periksa hasil operasinya; jangan mengulang atau memaksa status lunas. Jangan membuat pembayaran atau kelompok pengganti.</p>'


def formulir_dukungan(csrf, token, config):
    opsi=''.join('<option value="%s"%s>%s</option>'%(e(k),' selected' if k==config.jam_layanan_kode else '',e(v)) for k,v in dukungan.JAM_LAYANAN.items())
    return ('<form method="post" action="/admin/layanan/dukungan">'
            '<input type="hidden" name="csrf_dukungan" value="%s">'
            '<input type="hidden" name="tinjauan_dukungan" value="%s">'
            '<label for="dukungan-wa">Nomor WhatsApp Business'
            '<input id="dukungan-wa" name="whatsapp" inputmode="numeric" autocomplete="off" '
            'maxlength="24" value="%s" aria-describedby="dukungan-wa-bantuan" required></label>'
            '<p id="dukungan-wa-bantuan" class="admin-meta">Contoh: 0821 3711 1988. URL wa.me dibuat oleh aplikasi; jangan masukkan URL atau kode negara.</p>'
            '<label for="dukungan-jam">Jam layanan<select id="dukungan-jam" name="jam_layanan">%s</select></label>'
            '<label for="dukungan-respons">SLA respons awal (hari kerja)'
            '<input id="dukungan-respons" name="sla_respons" type="number" min="1" max="30" value="%d" required></label>'
            '<label for="dukungan-status">SLA status atau penyelesaian awal (hari kerja)'
            '<input id="dukungan-status" name="sla_status" type="number" min="1" max="30" value="%d" required></label>'
            '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami perubahan ini langsung menjadi kontak dan janji layanan pada halaman publik.</label>'
            '<label for="dukungan-reauth">Sandi admin saat ini<input id="dukungan-reauth" type="password" name="reauth" required autocomplete="current-password"></label>'
            '<button class="admin-tombol" type="submit">Simpan dukungan</button></form>')%(
                e(csrf),e(token),e(dukungan._kelompok_nomor(config.whatsapp_digits)),opsi,
                config.sla_respons_hari,config.sla_status_hari)


LABEL_TAHAP={'nonaktif':'Tutup','rekonsiliasi':'Tutup untuk pesanan baru (pesanan lama tetap diproses)','checkout':'Buka','penegakan':'Buka + akses berbayar'}
BADGE_TAHAP={'nonaktif':('Tutup',''),'rekonsiliasi':('Tutup untuk pesanan baru',' perhatian'),'checkout':('Buka',' bien'),'penegakan':('Buka + akses berbayar',' bien')}
DAMPAK_TAHAP={'nonaktif':'Pembeli tidak bisa membayar lewat QRIS dan tidak ada transaksi QRIS yang diperiksa.',
              'rekonsiliasi':'Tidak ada pesanan QRIS baru. Pesanan yang sudah berjalan tetap diperiksa sampai selesai.',
              'checkout':'Pembeli bisa membayar lewat QRIS. Pesanan yang berjalan tetap diperiksa.',
              'penegakan':'Sama seperti Buka, ditambah akses berbayar mulai diberlakukan.'}
TAHAP_PEMBAYARAN=('nonaktif','rekonsiliasi','checkout','penegakan')
TAHAP_QRIS_TUTUP=('nonaktif','rekonsiliasi')
PRASYARAT_QRIS=(('provider_produksi','Kunci Midtrans produksi terpasang di server'),
                ('callback','Server siap menerima notifikasi pembayaran dari Midtrans'),
                ('recovery','Pemulihan rilis (rollback) sudah terverifikasi'),
                ('kebijakan','Kebijakan refund, pajak, dan penghapusan data sudah diputuskan'))
COPY_ATURAN_QRIS=('Membuka dilakukan bertahap, satu langkah sekali. Menutup boleh langsung saat ada masalah; '
                  'pilih Tutup untuk pesanan baru supaya pesanan yang sudah berjalan tetap diperiksa. '
                  'Kunci rahasia hanya dipasang di server dan isinya tidak pernah tampil di panel.')
COPY_DUKUNGAN_BELUM=('Pengaturan dukungan belum terpasang atau rusak di server ini, jadi kontak publik ditahan. '
                     'Operator perlu memasangnya dan memeriksa pemulihan sebelum layanan dibuka.')


def _baris_status(nama,nilai,perhatian=False):
    return '<li class="admin-baris-status%s"><span>%s</span><span class="admin-badge%s">%s</span></li>'%(' perhatian' if perhatian else '',e(nama),' perhatian' if perhatian else '',e(nilai))


def _kartu_kesiapan(r):
    baris=''.join(_baris_status(k,r[v],v=='backup' and r['backup_cutoff'] is None) for k,v in [('Penyimpanan admin','admin'),('Pembayaran','pembayaran'),('Cadangan','backup')])
    cutoff='belum tercatat' if r['backup_cutoff'] is None else tanggal(r['backup_cutoff'])
    return ('<section class="admin-sub-bagian" id="kesiapan"><h3>Kesiapan layanan</h3>'
            '<ul class="admin-daftar-status">%s</ul><div class="admin-kaki-garis"><p>Cadangan mencakup data sampai: %s</p>'
            '<p class="admin-meta">Cadangan yang valid belum tentu terjadwal, tersalin ke luar server, atau sudah dilatih pemulihannya.</p></div></section>')%(baris,cutoff)


def _kartu_dukungan(r,form_dukungan):
    support=r.get('dukungan_config')
    if not support:
        return ('<section class="admin-sub-bagian" id="dukungan"><h3>Dukungan pengguna</h3>'
                '<p><span class="admin-badge">Belum siap</span></p><p>%s</p></section>')%e(COPY_DUKUNGAN_BELUM)
    publik=dukungan.proyeksi_publik(support)
    ubah=lipat_aksi('Ubah kontak dukungan…','admin-tombol admin-tombol-sekunder',form_dukungan) if form_dukungan else ''
    return ('<section class="admin-sub-bagian" id="dukungan"><div class="admin-fitur-kepala"><h3>Dukungan pengguna</h3>'
            '<span class="admin-badge bien">Siap</span></div>'
            '<dl class="admin-rincian"><dt>WhatsApp Business</dt><dd>%s</dd><dt>Jam layanan</dt><dd>%s</dd>'
            '<dt>Respons awal</dt><dd>Maksimal %d hari kerja</dd><dt>Status awal</dt><dd>Maksimal %d hari kerja</dd></dl>%s'
            '<p class="admin-meta">WhatsApp adalah kanal komunikasi, bukan bukti kepemilikan akun. Reset hanya setelah verifikasi independen; bila tidak tersedia, reset ditahan.</p>'
            '<details class="admin-detail-teknis"><summary>Detail teknis</summary><p class="admin-meta">Revisi %d.</p></details></section>')%(
                e(publik.whatsapp_label),e(publik.jam_layanan_label),
                support.sla_respons_hari,support.sla_status_hari,ubah,support.revisi)


def _stepper(tahap):
    kartu=''
    for nomor,kode in enumerate(TAHAP_PEMBAYARAN,1):
        aktif=kode==tahap
        kartu+=('<li%s class="admin-tahap%s"><span class="admin-meta">Langkah %d%s</span><strong>%s</strong>'
                '<span class="admin-tahap-hint">%s</span></li>')%(' aria-current="step"' if aktif else '',' admin-tahap-aktif' if aktif else '',nomor,' · saat ini' if aktif else '',e(LABEL_TAHAP[kode]),e(DAMPAK_TAHAP[kode]))
    return '<ol class="admin-stepper" aria-label="Status pembayaran QRIS">%s</ol>'%kartu


def _syarat_qris(kesiapan):
    siap=sum(1 for k,_ in PRASYARAT_QRIS if kesiapan.get(k))
    baris=''.join(_baris_status(label,'Siap' if kesiapan.get(k) else 'Belum siap',not kesiapan.get(k)) for k,label in PRASYARAT_QRIS)
    return ('<details class="admin-prasyarat"%s><summary>Syarat membuka QRIS · %d dari %d siap</summary>'
            '<ul class="admin-daftar-status">%s</ul></details>')%('' if siap==len(PRASYARAT_QRIS) else ' open',siap,len(PRASYARAT_QRIS),baris)


def _kepala_qris(tahap):
    if tahap not in BADGE_TAHAP:
        return '<span class="admin-badge admin-status-besar">Tidak bisa dibaca</span>'
    teks,varian=BADGE_TAHAP[tahap]
    return '<span class="admin-badge admin-status-besar%s">%s</span>'%(varian,e(teks))


def _kartu_pembayaran(r,form_pembayaran):
    cfg=r.get('pembayaran_config')
    tahap=cfg['tahap'] if cfg else None
    kesiapan=r.get('pembayaran_kesiapan',{})
    ubah=lipat_aksi('Ubah status QRIS…','admin-tombol',form_pembayaran) if form_pembayaran else ''
    teknis=('<details class="admin-detail-teknis"><summary>Detail teknis</summary><p class="admin-meta">Tahap internal: %s · revisi %d.</p></details>'%(e(tahap),cfg['revisi'])) if cfg else ''
    return ('<section class="admin-kartu admin-kartu-fitur" id="pembayaran"><div class="admin-fitur-kepala"><h3>Pembayaran QRIS (Midtrans)</h3>%s</div>'
            '<p>%s</p>%s%s%s%s<p class="admin-meta">%s</p></section>')%(
                _kepala_qris(tahap),e(DAMPAK_TAHAP.get(tahap,'Status pembayaran QRIS tidak tersedia.')),
                _stepper(tahap),_syarat_qris(kesiapan),ubah,teknis,e(COPY_ATURAN_QRIS))


def _item_ringkasan(label,badge,href):
    return '<li class="admin-ringkasan-item"><a class="admin-tautan-teks" href="#%s">%s</a>%s</li>'%(href,e(label),badge)


def _ringkasan_aktif(sakelar,cfg,pendaftaran_dibuka,ada_pendaftaran):
    """Ringkasan "Yang aktif sekarang": satu baris per layanan dengan penanda Aktif/Mati, bahasa awam."""
    tahap=cfg['tahap'] if cfg else None
    status={nama:(label,aktif) for nama,label,aktif in sakelar.status} if isinstance(sakelar,sak.BagianSakelar) else {}
    def baris_sakelar(nama):
        label,aktif=status[nama]
        return _item_ringkasan(label,sak.badge_status(aktif),sak.id_kartu(nama))
    baris=[]
    if sak.FUNNEL in status: baris.append(baris_sakelar(sak.FUNNEL))
    baris.append(_item_ringkasan('Pembayaran QRIS (Midtrans)',_kepala_qris(tahap),'pembayaran'))
    if sak.TRANSFER in status: baris.append(baris_sakelar(sak.TRANSFER))
    if ada_pendaftaran:
        badge='<span class="admin-badge admin-status-besar">Tidak bisa dibaca</span>' if pendaftaran_dibuka is None else sak.badge_status(pendaftaran_dibuka,teks_aktif='Dibuka',teks_mati='Ditutup')
        baris.append(_item_ringkasan('Pendaftaran mandiri',badge,'pendaftaran'))
    baris+=[baris_sakelar(n) for n in status if n not in (sak.FUNNEL,sak.TRANSFER)]
    return '<section class="admin-kartu admin-ringkasan" id="ringkasan"><h2>Yang aktif sekarang</h2><ul class="admin-ringkasan-daftar">%s</ul></section>'%''.join(baris)


def _navigasi_bagian(punya_belajar,pendaftaran=''):
    tautan=[('ringkasan','Yang aktif sekarang'),('penjualan','Penjualan dan pembayaran')]
    tautan+=[('belajar','Fitur belajar')] if punya_belajar else []
    tautan+=[('pendaftaran','Pendaftaran mandiri')] if pendaftaran else []
    tautan+=[('kesehatan','Kesehatan sistem')]
    return '<nav class="admin-navigasi-bagian" aria-label="Bagian pengaturan layanan"><span>Lompat ke</span>'+''.join('<a href="#%s">%s</a>'%(sid,label) for sid,label in tautan)+'</nav>'


def _kelompok(sid,judul,isi):
    return '<section class="admin-kelompok" id="%s"><h2 class="admin-kelompok-judul">%s</h2>%s</section>'%(sid,e(judul),isi)


def _kelompok_penjualan(r,sakelar,pembayaran,rekening,status_rekening):
    if not isinstance(sakelar,sak.BagianSakelar):
        return _kelompok('penjualan',sak.LABEL_KELOMPOK['penjualan'],sakelar+pembayaran+rekening)
    cfg=r.get('pembayaran_config')
    status={nama:aktif for nama,_l,aktif in sakelar.status}
    checklist=sak.checklist_transfer(rekening=status_rekening,
        qris_tutup=None if not cfg else cfg['tahap'] in TAHAP_QRIS_TUTUP,
        transfer_aktif=status.get(sak.TRANSFER,False)) if sak.TRANSFER in status else ''
    kartu=dict(sakelar.penjualan)
    isi=kartu.pop(sak.FUNNEL,'')+pembayaran+kartu.pop(sak.TRANSFER,'')+checklist+''.join(kartu.values())+rekening+hg.tautan_pengaturan()
    return _kelompok('penjualan',sak.LABEL_KELOMPOK['penjualan'],isi)


def _kesehatan(r,form_dukungan,buka):
    perlu=int(r['backup_cutoff'] is None)+int(not r.get('dukungan_config'))
    badge='<span class="admin-badge perhatian">%d perlu dilihat</span>'%perlu if perlu else '<span class="admin-badge bien">Semua siap</span>'
    return ('<details class="admin-kartu admin-kesehatan" id="kesehatan"%s><summary><h2>Kesehatan sistem</h2>%s'
            '<span class="admin-meta">Penyimpanan, cadangan, dan dukungan pengguna</span></summary>%s%s</details>')%(
                ' open' if buka else '',badge,_kartu_kesiapan(r),_kartu_dukungan(r,form_dukungan))


def operasional(r,form_pembayaran='',form_dukungan='',feedback='',*,sakelar='',rekening='',pendaftaran='',status_rekening=None,pendaftaran_dibuka=None):
    """Halaman Pengaturan layanan. Urutan: ringkasan "Yang aktif sekarang", Penjualan dan pembayaran (Cek Kemampuan,
    QRIS, transfer + checklist, rekening), Fitur belajar, Pendaftaran mandiri, Kesehatan sistem (terlipat).

    `sakelar` = `BagianSakelar` (atau HTML galat), `pendaftaran` dan `rekening` sudah dirender modul pemiliknya
    (kartu ringkas; form ubah tetap di rutenya). `status_rekening` = keadaan rekening untuk checklist transfer."""
    status='<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>'%e(feedback) if feedback else ''
    bagian=sakelar if isinstance(sakelar,sak.BagianSakelar) else None
    umpan=bagian.umpan_balik if bagian else ''
    catatan=bagian.catatan if bagian else ''
    belajar=_kelompok('belajar',sak.LABEL_KELOMPOK['belajar'],''.join(bagian.belajar.values())) if bagian and bagian.belajar else ''
    teknis=bagian.catatan_teknis if bagian else ''
    penjualan=_kelompok_penjualan(r,sakelar,_kartu_pembayaran(r,form_pembayaran),rekening,status_rekening)
    wadah='<div id="sakelar">' if sakelar else '<div>'
    return (umpan+status+_ringkasan_aktif(sakelar,r.get('pembayaran_config'),pendaftaran_dibuka,bool(pendaftaran))
            +_navigasi_bagian(bool(belajar),pendaftaran)+catatan+wadah+penjualan+belajar+teknis+'</div>'
            +pendaftaran+_kesehatan(r,form_dukungan,bool(feedback)))


def _hero_manfaat(m,judul,bantuan,angka,persen):
    """KPI utama; tanpa respons hasil tetap "—" dan bilah tidak terisi."""
    ada=bool(m.penyebut)
    label=('Hasil %.1f persen; target %d persen'%(persen,m.target)) if ada else 'Belum ada respons; target %d persen'%m.target
    isi_bilah='<span style="width:%.2f%%"></span>'%persen if ada else ''
    ket='<p class="admin-meta">Jawaban Ya %d dari %d respons.</p>'%(m.pembilang,m.penyebut) if ada else ''
    return ('<section class="admin-kartu admin-kpi-hero" aria-labelledby="h-kpi-manfaat">'
            '<div class="admin-kpi-hero-kepala"><h2 id="h-kpi-manfaat">%s</h2>%s<span class="admin-meta">Target ≥ %d%%</span></div>'
            '<div class="admin-kpi-hero-angka"><div><span class="admin-meta">Hasil saat ini</span>'
            '<strong class="admin-angka%s">%s</strong></div>'
            '<div><span class="admin-meta">Respons</span><strong>%d / %d</strong></div></div>'
            '<div class="admin-bilah" role="img" aria-label="%s">%s<i style="left:%d%%"></i></div>'
            '<div class="admin-bilah-skala"><span>0%%</span><span>Target %d%%</span><span>100%%</span></div>%s'
            '<div><span class="admin-badge">%s</span>%s</div></section>')%(
                e(judul),bantuan,m.target,'' if ada else ' admin-redup',angka,m.respons,m.penawaran,
                e(label),isi_bilah,m.target,m.target,ket,e(m.status),'<p>Sampel kecil</p>' if m.kecil else '')


def halaman_kpi(config,laporan,biaya,cakupan,*,bulan,form_biaya='',form_config=''):
    labels={'aktivasi':'Berhasil mencoba','retensi':'Memakai kembali','manfaat':'Merasa terbantu','organik':'Tumbuh organik'}
    bantuan={'aktivasi':'Pengiriman sah atau lembar soal dibuka pada minggu pertama. Populasi utama sudah melewati 14 hari.',
             'retensi':'Mencoba pada minggu pertama dan aktif lagi pada minggu kedua. Penyebut adalah seluruh peserta matang.',
             'manfaat':'Jawaban Ya dibanding seluruh respons. Target dinilai bila sedikitnya 40% penawaran dijawab.',
             'organik':'Sumber rekomendasi atau pencarian noniklan, dilaporkan pengguna. Khusus peserta teraktivasi yang mendaftar minggu 5–8.'}
    items=laporan.metrik if laporan else tuple(d.Metrik(k,0,0,t,'Belum ada eksperimen',False) for k,t in [('aktivasi',60),('retensi',25),('manfaat',70),('organik',20)])
    kartu=[]
    hero=''
    for m in items:
        angka='%.1f%%'%(m.pembilang*100/m.penyebut) if m.penyebut else '—'
        detail='%d/%d · Target ≥%d%%'%(m.pembilang,m.penyebut,m.target)
        if m.kode=='manfaat': detail+='<br>Respons %d/%d'%(m.respons,m.penawaran)
        if m.kode=='organik': detail+='<br>Minggu 5–8'
        persen = min(100, max(0, m.pembilang*100/m.penyebut)) if m.penyebut else 0
        bilah = '<div class="admin-bilah" aria-hidden="true"><span style="width:%.2f%%"></span><i style="left:%d%%"></i></div>' % (persen, m.target)
        if m.kode=='manfaat':
            hero=_hero_manfaat(m,labels[m.kode],info(labels[m.kode],bantuan[m.kode]),angka,persen)
            continue
        kartu.append('<article class="admin-kartu admin-kpi-carte"><header><h2>%s</h2>%s</header><strong class="admin-angka">%s</strong><p>%s</p>%s<span class="admin-badge">%s</span>%s</article>'%(labels[m.kode],info(labels[m.kode],bantuan[m.kode]),angka,detail,bilah,e(m.status),'<p>Sampel kecil</p>' if m.kecil else ''))
    total=sum(biaya[k] for k in ('server','domain','ai','pendukung')) if biaya else 0
    status='Belum ada anggaran' if not biaya else 'Data biaya belum lengkap' if not biaya['lengkap'] else 'Dalam anggaran' if total<=biaya['anggaran'] else 'Melebihi anggaran'
    kartu.append('<article class="admin-kartu admin-kpi-biaya"><h2>Biaya · %s</h2><strong class="admin-angka">%s</strong><p>Anggaran %s</p><span class="admin-badge">%s</span></article>'%(e(bulan),rupiah(total) if biaya else '—',rupiah(biaya['anggaran']) if biaya else '—',status))
    meta='Koleksi belum aktif' if not config else ('Koleksi aktif' if config['koleksi'] else 'Koleksi dihentikan')
    if laporan: meta+=' · %d peserta · %d matang · %d menunggu · %d terlambat'%(laporan.peserta,laporan.matang,laporan.menunggu,laporan.terlambat)
    if cakupan.get('pendaftaran') is not None:
        meta+=' · %d pendaftaran publik total' % cakupan['pendaftaran']
    meta+=' · %d dicabut · %d melewati retensi'%(cakupan['dicabut'],cakupan['kedaluwarsa'])
    minggu=laporan.minggu if laporan else ()
    arsip = '<details class="admin-kartu"><summary>Arsip agregat setelah retensi</summary>'+tabel(
        ('Minggu','Peserta','Mencoba','Kembali','Ditawari','Respons','Ya','Organik'),
        ['<tr>'+''.join('<td>%d</td>'%x for x in row)+'</tr>' for row in cakupan.get('arsip',())]
    )+'<p>Tanpa mapping keluarga. Tidak digabung diam-diam dengan detail yang masih aktif.</p></details>'
    kosong = '<section class="admin-kartu admin-kosong-kartu"><h2>Belum ada eksperimen</h2><p>Hasil belum ditampilkan agar tidak terbaca sebagai 0%. Angka muncul setelah eksperimen aktif dan ada respons yang memenuhi definisi metrik.</p></section>' if not laporan else ''
    return hero+kosong+'<p class="admin-meta">'+e(meta)+'</p><form class="admin-filtre-periode" method="get" action="/admin"><input type="hidden" name="section" value="kpi"><label>Bulan biaya<input type="month" name="bulan" value="'+e(bulan)+'" required></label><button class="admin-tombol admin-tombol-sekunder">Terapkan</button></form><div class="admin-grid-kpi">'+''.join(kartu)+'</div><details class="admin-kartu"><summary>Per minggu</summary>'+tabel(('Minggu','Matang','Mencoba','Kembali'),['<tr>'+''.join('<td>%d</td>'%x for x in row)+'</tr>' for row in minggu])+'<p>Kelompok kurang dari 5 tidak dirinci. Metrik hanya untuk peserta analitik, bukan seluruh keluarga.</p></details><details class="admin-kartu"><summary>Catat biaya bulanan</summary>'+form_biaya+'</details><details class="admin-kartu"><summary>Pengaturan eksperimen</summary>'+form_config+'</details>'+arsip
