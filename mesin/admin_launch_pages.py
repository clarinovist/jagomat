"""Panel layanan ringkas; renderer hanya menerima proyeksi terjaga."""

import html
from datetime import datetime

import product_analytics as d


def e(nilai):
    return html.escape(str(nilai),quote=True)


def rupiah(n):
    return 'Rp'+format(n,',').replace(',','.')


def tanggal(epoch):
    return datetime.fromtimestamp(epoch,d.WIB).strftime('%d/%m/%Y %H:%M WIB') if epoch is not None else '—'


def info(label,isi):
    return '<details class="admin-info"><summary aria-label="Info %s">ⓘ</summary><p>%s</p></details>'%(e(label),e(isi))


def tabel(kepala,baris):
    return '<div class="admin-tabel-wrap"><table class="admin-tabel"><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in kepala)+'</tr></thead><tbody>'+(''.join(baris) or '<tr><td colspan="%d">Belum ada data.</td></tr>'%len(kepala))+'</tbody></table></div>'


def formulir(aksi,csrf,token,isi,tombol,hidden=()):
    fields=(('csrf',csrf),('tinjauan',token),*hidden)
    return '<form method="post" action="/admin/layanan/'+e(aksi)+'">'+''.join('<input type="hidden" name="%s" value="%s">'%(e(k),e(v)) for k,v in fields)+isi+'<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label><button class="admin-tombol" type="submit">'+e(tombol)+'</button></form>'


def daftar_langganan(rows,total,*,halaman,cari,csrf,kandidat=(),forms=None):
    form='<form method="post" action="/admin/layanan/cari"><input type="hidden" name="csrf" value="%s"><label>Cari akun orang tua<input name="cari" maxlength="80" value="%s"></label><button class="admin-tombol">Cari</button></form>'%(e(csrf),e(cari)) if csrf else ''
    baris=['<tr><td><a href="/admin?section=langganan&amp;id=%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'%(e(r['akun_id']),e(r['alias']),tanggal(r['mulai']),'Ya' if r['peserta_promo'] else 'Tidak',e(r['asal'])) for r in rows]
    pager=''
    for nomor, label in ((halaman-1, 'Sebelumnya'), (halaman+1, 'Berikutnya')):
        if nomor < 1 or (nomor > halaman and halaman*25 >= total):
            continue
        if cari and csrf:
            pager += ('<form method="post" action="/admin/layanan/cari">'
                      '<input type="hidden" name="csrf" value="%s">'
                      '<input type="hidden" name="cari" value="%s">'
                      '<input type="hidden" name="halaman" value="%d">'
                      '<button class="admin-tombol">%s</button></form>'
                      % (e(csrf), e(cari), nomor, label))
        else:
            pager += '<a href="/admin?section=langganan&amp;halaman=%d">%s</a> ' % (nomor,label)
    kartu_kandidat=''
    if cari and kandidat:
        baris_k=''.join('<tr><td>%s</td><td>%s</td></tr>'%(e(k['alias']),(forms or {}).get(k['akun_id'],'Tidak ada tindakan')) for k in kandidat)
        kartu_kandidat=('<section class="admin-kartu"><h2>Belum terdaftar di langganan · %d</h2>'%len(kandidat)
                        +tabel(('Keluarga','Tindakan'),baris_k)
                        +'<p class="admin-meta">Jalur transisi untuk akun lama sebelum sinkron registrasi publik. Satu aksi satu akun; tidak membuat pembayaran dan tidak mengaktifkan paywall.</p></section>')
    return '<section class="admin-kartu"><h2>Langganan keluarga</h2><p>%d tercatat · Halaman %d</p>%s%s%s</section>'%(total,halaman,form,tabel(('Keluarga','Mulai','Peserta promo','Sumber'),baris),pager)+kartu_kandidat+'<p class="admin-meta">Akun yang belum diikutkan tidak dianggap kedaluwarsa. Panel ini tidak mengaktifkan paywall.</p>'


AKSES={'promo':'Promo aktif','trial':'Masa coba','aktif':'Aktif','expired':'Masa aktif habis','kedaluwarsa':'Masa aktif habis','belum_terverifikasi':'Belum terverifikasi','paid':'Berbayar'}
STATUS={'grant':'Hak akses tercatat','lunas':'Pembayaran tercatat','perlu_diperiksa':'Perlu diperiksa','belum_terverifikasi':'Belum terverifikasi','settlement':'Settlement teramati'}


def detail_langganan(r,forms):
    a=r['akses']
    isi='<section class="admin-kartu"><h2>%s</h2><dl class="admin-rincian"><dt>Status akses</dt><dd>%s</dd><dt>Batas periode</dt><dd>%s</dd><dt>Cakupan terbaru</dt><dd>%d profil</dd><dt>Promo tersisa</dt><dd>%d periode berbayar</dd></dl></section>'%(e(r['alias']),e(AKSES.get(a.status,a.status)),tanggal(a.akhir),r['jumlah_profil'],r['promo_tersisa'])
    baris=[]
    for i in r['invoices']:
        g=i['grant']
        baris.append('<tr><td>%s<br><small>Periode %d</small></td><td>%s<br>%d profil</td><td>%s</td><td>%s</td><td>%s</td></tr>'%(e(i['invoice_id']),i['urutan'],rupiah(i['rupiah']),i['jumlah_profil'],e(STATUS.get(i['status'],i['status'])),tanggal(g.periode.akhir) if g else 'Belum ada grant',forms.get(i['invoice_id'],'Tidak ada tindakan provider')))
    return isi+'<section class="admin-kartu"><h2>Invoice dan hak akses</h2>'+tabel(('Referensi','Nominal','Pembayaran','Akhir grant','Tindakan'),baris)+'</section><p class="admin-meta">Pembayaran tercatat tidak selalu berarti akses aktif sekarang. Refund, pembayaran lebih, dan kasus terlambat tetap perlu keputusan; tidak ada tombol paksa lunas.</p>'


def antrean(rows,total,halaman=1):
    baris=[]
    for r in rows:
        link='/admin?section=langganan&amp;id='+e(r['akun']) if r['sumber'] in ('pembayaran','layanan') and r['akun'].startswith('akun_') else '/admin?section=riwayat'
        baris.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><a href="%s">Periksa sumber</a></td></tr>'%(e(r['sumber']),e(r['ref']),e(r['status']),tanggal(r['waktu']),link))
    pager = ''
    if halaman > 1:
        pager += '<a href="/admin?section=perhatian&amp;halaman=%d">Sebelumnya</a> ' % (halaman-1)
    if halaman*25 < total:
        pager += '<a href="/admin?section=perhatian&amp;halaman=%d">Berikutnya</a>' % (halaman+1)
    return '<section class="admin-kartu"><h2>Perlu ditangani · %d</h2>'%total+tabel(('Sumber','Referensi','Status','Sejak','Lanjut'),baris)+pager+'</section><p class="admin-meta">Status belum pasti bukan gagal aman. Gunakan operasi yang sama; jangan membuat pembayaran atau batch pengganti.</p>'


def operasional(r,form_pembayaran=''):
    isi='<section class="admin-kartu"><h2>Kesiapan layanan</h2>'+tabel(('Komponen','Status'),['<tr><td>%s</td><td>%s</td></tr>'%(e(k),e(r[v])) for k,v in [('Penyimpanan admin','admin'),('Pembayaran','pembayaran'),('Backup','backup')]])
    isi+='<p>Cutoff backup: %s</p><p class="admin-meta">Validitas bundle bukan bukti backup terjadwal, salinan luar server, atau rehearsal terbaru.</p></section>'%tanggal(r['backup_cutoff'])
    cfg=r.get('pembayaran_config')
    tahap=cfg['tahap'] if cfg else 'tidak tersedia'
    kesiapan=r.get('pembayaran_kesiapan',{})
    status_kesiapan=''.join('<li>%s: <strong>%s</strong></li>'%(e(label),'Siap' if kesiapan.get(k) else 'Belum siap') for k,label in [('provider_produksi','Key/provider produksi'),('callback','Callback dan rekonsiliasi'),('recovery','Recovery exact-pair'),('kebijakan','Kebijakan D8/D9')])
    dampak={'nonaktif':'Tidak membuat atau memeriksa pembayaran.','rekonsiliasi':'Hanya memeriksa transaksi yang sudah ada; pembayaran baru tetap ditutup.','checkout':'Membuka pembayaran baru dan rekonsiliasi.','penegakan':'Menerapkan akses berbayar setelah checkout.'}.get(tahap,'Status tidak tersedia.')
    isi+='<section class="admin-kartu"><h2>Sakelar pembayaran</h2><p>Tahap saat ini: <strong>%s</strong>%s</p><p>%s</p><ol><li>Nonaktif</li><li>Rekonsiliasi transaksi yang sudah ada</li><li>Checkout dan rekonsiliasi</li><li>Penegakan akses</li></ol><h3>Prasyarat tepercaya</h3><ul>%s</ul>%s<p class="admin-meta">Tahap harus dinaikkan satu per satu. Penurunan boleh langsung saat insiden. Secret hanya dipasang di server dan nilainya tidak pernah tampil di panel.</p></section>'%(e(tahap),' · revisi %d'%cfg['revisi'] if cfg else '',e(dampak),status_kesiapan,form_pembayaran)
    return isi+'<section class="admin-kartu"><h2>AI</h2>'+tabel(('Fitur','Konfigurasi'),['<tr><td>%s</td><td>%s</td></tr>'%(e(k),e(v)) for k,v in r['ai']])+'<p>Gagal/tak pasti 24 jam: <strong>%s</strong></p><p class="admin-meta">Konfigurasi bukan jaminan provider sedang online. Tidak ada panggilan berbayar saat halaman dibuka.</p><a href="/admin/ai">Batas pemakaian dan tes sintetis</a></section>'%('—' if r['ai_gagal'] is None else r['ai_gagal'])


def halaman_kpi(config,laporan,biaya,cakupan,*,bulan,form_biaya='',form_config=''):
    labels={'aktivasi':'Berhasil mencoba','retensi':'Memakai kembali','manfaat':'Merasa terbantu','organik':'Tumbuh organik'}
    bantuan={'aktivasi':'Pengiriman sah atau lembar soal dibuka pada minggu pertama. Populasi utama sudah melewati 14 hari.',
             'retensi':'Mencoba pada minggu pertama dan aktif lagi pada minggu kedua. Penyebut adalah seluruh peserta matang.',
             'manfaat':'Jawaban Ya dibanding seluruh respons. Target dinilai bila sedikitnya 40% penawaran dijawab.',
             'organik':'Sumber rekomendasi atau pencarian noniklan, dilaporkan pengguna. Khusus peserta teraktivasi yang mendaftar minggu 5–8.'}
    items=laporan.metrik if laporan else tuple(d.Metrik(k,0,0,t,'Belum ada eksperimen',False) for k,t in [('aktivasi',60),('retensi',25),('manfaat',70),('organik',20)])
    kartu=[]
    for m in items:
        angka='%.1f%%'%(m.pembilang*100/m.penyebut) if m.penyebut else '—'
        detail='%d/%d · Target ≥%d%%'%(m.pembilang,m.penyebut,m.target)
        if m.kode=='manfaat': detail+='<br>Respons %d/%d'%(m.respons,m.penawaran)
        if m.kode=='organik': detail+='<br>Minggu 5–8'
        kartu.append('<article class="admin-kartu admin-kpi-carte"><header><h2>%s</h2>%s</header><strong class="admin-angka">%s</strong><p>%s</p><span class="admin-badge">%s</span>%s</article>'%(labels[m.kode],info(labels[m.kode],bantuan[m.kode]),angka,detail,e(m.status),'<p>Sampel kecil</p>' if m.kecil else ''))
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
    return '<p class="admin-meta">'+e(meta)+'</p><form class="admin-filtre-periode" method="get" action="/admin"><input type="hidden" name="section" value="kpi"><label>Bulan biaya<input type="month" name="bulan" value="'+e(bulan)+'" required></label><button class="admin-tombol">Terapkan</button></form><div class="admin-grid-kpi">'+''.join(kartu)+'</div><details class="admin-kartu"><summary>Per minggu</summary>'+tabel(('Minggu','Matang','Mencoba','Kembali'),['<tr>'+''.join('<td>%d</td>'%x for x in row)+'</tr>' for row in minggu])+'<p>Kelompok kurang dari 5 tidak dirinci. Metrik hanya untuk peserta analitik, bukan seluruh keluarga.</p></details><details class="admin-kartu"><summary>Catat biaya bulanan</summary>'+form_biaya+'</details><details class="admin-kartu"><summary>Pengaturan eksperimen</summary>'+form_config+'</details>'+arsip
