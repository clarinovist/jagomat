"""Kartu orang tua pilot; status/tindakan berasal dari reducer, bukan UI."""
import html
import learning_cycle as lc
from skill_pilot import TUNTUTAN, RUJUKAN_LUAS
from skill_pilot_materials import pilihan_materi
from skill_pilot_service import keadaan, revisi

LABEL={'terbukti':'Menunjukkan pemahaman','belum_dinilai':'Belum dinilai',
       'dipelajari':'Masih dipelajari','perlu_cek':'Perlu cek kembali'}
JUDUL={'pulihkan_sumber':'Tinjau ulang sumber fokus pilot','pemetaan':'Periksa pemahaman dengan probe baru','intervensi':'Pelajari konsep bersama',
       'pengenalan':'Kenalkan tugas ini bersama','lanjutkan_sesi':'Lanjutkan sesi pilot',
       'konfirmasi_hasil':'Tinjau dan konfirmasi hasil','latihan_terbimbing':'Coba dengan pendampingan',
       'penguatan':'Coba mandiri','evaluasi':'Evaluasi setelah jeda','checkpoint':'Cek kembali pemahaman',
       'eskalasi':'Periksa prasyarat atau lakukan uji ulang lisan','putaran_baru':'Periksa kembali fokus yang kambuh',
       'tunggu_pemetaan':'Beri jeda sebelum pemeriksaan berikutnya','tunggu_evaluasi':'Tunggu evaluasi berjeda',
       'tunggu_checkpoint':'Pemahaman diperiksa kembali secara berkala'}


def _e(s): return html.escape(str(s),quote=True)


def form_mulai(siswa_id, versi, balik_tersedia=False):
    tersedia=(*TUNTUTAN,RUJUKAN_LUAS) if balik_tersedia else (TUNTUTAN[0],RUJUKAN_LUAS)
    pilihan=''.join('<option value="%s">%s</option>'%(_e(t.id),_e(t.nama)) for t in tersedia)
    return ('<details class="ubah-fokus-st pilot-mulai-st"><summary>Pilot keliling dan luas — opsional</summary>'
      '<p>Pilih satu tuntutan untuk diperiksa. Ini bukan tangga kelas atau persen kemampuan. '
      'Latihan manual tetap tersedia. Tugas balik baru ditawarkan bila bukti keliling dan rujukan luas sah.</p>'
      '<p>P3: keliling langsung (sisi 2–16) atau kisi luas (2–8). P4–P6: keliling langsung (3–40), '
      'atau tugas balik (panjang 3–30, lebar yang dicari 2–25). Tidak ada perpindahan profil otomatis.</p>'
      f'<form method="post" action="/siklus/{siswa_id}/pilot" class="profil-filter-st">'
      f'<input type="hidden" name="aksi" value="mulai"><input type="hidden" name="revisi" value="{versi}">'
      f'<label>Tuntutan<select name="tuntutan" required>{pilihan}</select></label>'
      '<label>Profil parameter<select name="profil" required><option value="">Pilih profil</option>'
      '<option>P3</option><option>P4</option><option>P5</option><option>P6</option></select></label>'
      '<label>Penyajian<select name="representasi" required><option value="teks-v1">Soal cerita</option>'
      '<option value="geometri_datar-v1">Diagram</option></select></label>'
      '<label><input type="checkbox" name="belum_dikenal" value="1"> Anak belum mengenal tugas ini; mulai dengan pengenalan</label>'
      '<button class="st-tombol-sekunder" type="submit">Pilih dan mulai pilot</button></form></details>')


def status_pilot(paket,siswa_id,daftar,hari=None):
    # Riwayat konteks tetap terlihat sesudah putaran bermasalah ditutup.
    konteks=tuple(dict.fromkeys([k for _,k,_,_ in daftar] + [b.konteks for b in paket.butir]))
    hasil=lc.penguasaan_pilot(paket,siswa_id,konteks,hari)
    isi=[]
    for h in hasil:
        k=h.konteks
        nama=next(t.nama for t in (*TUNTUTAN,RUJUKAN_LUAS) if t.id==k.tuntutan_id)
        sumber=', '.join('<a href="/sesi/%d">#%d</a>'%(sid,sid) for sid in h.hasil.sesi_ids)
        isi.append('<li><b>%s</b> · %s · %s<br>%s%s</li>'%(_e(nama),_e(k.profil_parameter),
          _e('Diagram' if k.mode_representasi=='geometri_datar-v1' else 'Soal cerita'),LABEL[h.hasil.status],
          ' · Sumber '+sumber if sumber else ''))
    tersedia={k.tuntutan_id for k in konteks}
    for t in TUNTUTAN:
        if t.id not in tersedia: isi.append('<li><b>%s</b><br>Belum dinilai</li>'%_e(t.nama))
    return ('<section class="kartu-rencana-st"><h3>Bukti per tuntutan pilot</h3><ul>'+''.join(isi)+
            '</ul><p>Belum dinilai bukan berarti tidak mampu. Profil dan penyajian tidak disetarakan. '
            'Keberhasilan tugas langsung tidak meluluskan tugas balik; kegagalan balik tidak menghapus bukti langsung.</p></section>')


def materi_sesi(kon,sesi_id,siswa_id):
    """Contoh khusus pendamping pada sesi pengenalan/terbimbing, bukan probe."""
    from skill_pilot_store import baca_kontrak
    kontrak=baca_kontrak(kon,sesi_id,siswa_id)
    if kontrak is None or kontrak.tujuan not in ('pengenalan','latihan_terbimbing'):
        return ''
    butir=next(b for b in kontrak.butir if b.konteks is not None)
    fokus=butir.target_fokus or (butir.konteks.template_id,'T',None)
    materi=pilihan_materi(butir.konteks,fokus)[0]
    return ('<section class="contoh-rencana-st"><h2>Pelajari bersama</h2><p>%s</p>'
            '<p>%s</p><p>Catat bantuan dengan jujur. Sesi ini tidak menyertifikasi pemahaman mandiri.</p></section>')%(
            _e(materi.contoh_terbimbing),_e(materi.instruksi_orang_tua))


def laporan(kon,siswa_id):
    """Laporan memakai reducer pilot yang sama, bukan persentase baru."""
    try:
        paket,daftar,_,_=keadaan(kon,siswa_id)
        return status_pilot(paket,siswa_id,daftar)
    except ValueError:
        return '<p>Sumber bukti pilot perlu diperiksa; tidak ada klaim kelulusan baru.</p>'


def kartu(kon,siswa_id,*,hari=None):
    """Return kartu pilot/opsi; None sebagai kartu berarti tetap gunakan rencana lama."""
    try:
        paket,daftar,aktif,warisan=keadaan(kon,siswa_id,hari)
    except ValueError:
        return None, ('<section class="kartu-rencana-st"><h3>Pilot perlu diperiksa</h3>'
                      '<p>Sumber bukti belum dapat diverifikasi. Histori tetap tersimpan; '
                      'jangan menganggap hasil lama sebagai kelulusan pilot.</p></section>')
    from skill_pilot import LANGSUNG, PRASYARAT, KonteksPilot
    sumber_langsung=tuple(dict.fromkeys(b.konteks for b in paket.butir if b.konteks.tuntutan_id==LANGSUNG))
    balik_tersedia=any(lc.tawaran_probe_balik(paket,siswa_id,k,
        KonteksPilot(PRASYARAT,'P3',k.mode_representasi),hari) for k in sumber_langsung)
    pilihan=form_mulai(siswa_id,revisi(kon,siswa_id),balik_tersedia) if warisan is None else ''
    status=status_pilot(paket,siswa_id,daftar,hari)
    if not daftar:
        return None,(status if paket.butir else '')+pilihan
    if warisan is not None:
        return None,status+'<p>Pilot menunggu tugas rencana yang diprioritaskan selesai.</p>'
    pid,k,r,_=aktif
    materi=''; aksi=''
    if r.tindakan in ('pengenalan','intervensi'):
        fokus=r.kandidat or (tuple(x.kunci for x in r.putaran.fokus) if r.putaran else ())
        if not fokus: fokus=((k.template_id,'T',None),)
        for f in fokus:
            daftar_materi=pilihan_materi(k,f)
            fs=next((x for x in r.putaran.fokus if x.kunci==f),None) if r.putaran else None
            m=next((x for x in daftar_materi if fs and x.pendekatan_id==fs.pendekatan_berikutnya),daftar_materi[0])
            materi+='<div class="contoh-rencana-st"><b>Contoh dipelajari bersama</b><p>%s</p><p>%s</p></div>'%(_e(m.contoh_terbimbing),_e(m.instruksi_orang_tua))
    if r.tindakan=='pulihkan_sumber':
        sumber=sorted({sid for m in lc.sumber_pilot_perlu_tinjauan(paket)
                       if m.putaran_id==pid for sid in m.sesi_ids})
        materi='<p>Tinjau sumber: '+', '.join('<a href="/sesi/%d">Sesi #%d</a>'%(sid,sid) for sid in sumber)+'.</p>'
        akibat='Tutup putaran pilot ini dan batalkan seluruh sesinya? Histori dan snapshot tetap tersimpan; fokus lama tidak diteruskan.'
        aksi=(f'<form class="pilot-pemulihan-st" method="post" action="/siklus/{siswa_id}/pilot" '
              f'onsubmit="return confirm(\'{_e(akibat)}\')">'
              '<input type="hidden" name="aksi" value="pulihkan_sumber">'
              f'<input type="hidden" name="revisi" value="{revisi(kon,siswa_id)}">'
              '<label><input type="checkbox" name="konfirmasi_pemulihan" value="1" required> '
              '<span>Saya menyetujui penutupan putaran dan pembatalan seluruh sesinya tanpa menghapus histori.</span></label>'
              '<button class="rencana-cta-utama-st" type="submit">Tutup putaran dan batalkan sesinya</button></form>')
    elif r.tindakan in ('lanjutkan_sesi','konfirmasi_hasil'):
        aksi='<a class="rencana-cta-utama-st" href="/sesi/%d">%s</a>'%(r.sesi_id,_e(JUDUL[r.tindakan]))
    elif r.tindakan in ('pengenalan','pemetaan','intervensi','latihan_terbimbing','penguatan','evaluasi','checkpoint','putaran_baru'):
        jenis='pelajari' if r.tindakan=='intervensi' else 'putaran_baru' if r.tindakan=='putaran_baru' else 'lanjut'
        label='Tandai sudah dipelajari bersama' if jenis=='pelajari' else 'Mulai putaran penguatan baru' if jenis=='putaran_baru' else 'Siapkan sesi berikutnya'
        aksi=(f'<form method="post" action="/siklus/{siswa_id}/pilot"><input type="hidden" name="aksi" value="{jenis}">'
              f'<input type="hidden" name="revisi" value="{revisi(kon,siswa_id)}">'
              f'<button class="rencana-cta-utama-st" type="submit">{label}</button></form>')
    tanggal='<p>Tersedia pada %s.</p>'%r.tersedia_pada.isoformat() if r.tersedia_pada else ''
    konten=('<section class="kartu-rencana-st" aria-labelledby="judul-pilot"><p class="label-rencana-st">Langkah belajar berikutnya · pilot opsional</p>'
             '<h2 id="judul-pilot">%s</h2><p>%s</p>%s%s%s'
             '<p><a href="/anak/%d?section=latihan">Tetap buat latihan manual</a></p></section>')%(
             _e(JUDUL.get(r.tindakan,r.tindakan)),_e(r.alasan),materi,tanggal,aksi,siswa_id)
    boleh_mulai = lc.boleh_mulai_pilot(paket,siswa_id,daftar,hari)
    return konten+status,(pilihan if boleh_mulai else '')
