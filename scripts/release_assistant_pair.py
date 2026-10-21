"""Probe retirement Pendamping C→R→C; delapan kelompok invariant, tanpa provider.

Schema/fingerprint identik tidak membuktikan retirement. Helper ini dieksekusi
oleh verifier dari candidate pada KEDUA image exact dengan data sintetis bersama.
Callback jaringan tiruan tidak mengesahkan mutu prompt atau kebijakan provider.
"""

BERSAMA = r'''
import contextlib, http.client, json, os, socket, threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
root=Path('/data/assistant-retirement');root.mkdir(exist_ok=True)
os.environ.update(OSN_BERKAS_DB=str(root/'belajar.db'), AI_BERKAS_DB=str(root/'ai.db'),
    PENDAMPING_AKTIF='1', PENDAMPING_ENTITLEMENT_AKTIF='0',
    DEEPSEEK_API_KEY='kunci-probe-sintetis', OSN_PBKDF2_ITERASI='1000')
import database, auth, sessions, assistant_schema as schema
import assistant_store as store, assistant_policy as policy
import assistant_service as service, assistant_client as client
import assistant_context as context, assistant_actions as actions
import sensor_http, ai_service, ai_store, web
schema.BAWAAN=root/'pendamping.db';database.BAWAAN=root/'belajar.db'
auth.BERKAS_SANDI=root/'sandi.json';sessions.BERKAS_SESI=root/'sesi.json'
# Sensor bukan target probe; tidak membaca data admin/auth di luar direktori ini.
sensor_http.izin_akun=lambda *a,**k:None
sensor_http.chat_selesai=lambda *a,**k:None
panggilan_provider=[]
def dilarang(*a,**k):
    panggilan_provider.append(1)
    raise AssertionError('provider_dilarang')
service_default=service.panggil_provider_default
client.kirim=dilarang
service.panggil_provider_default=dilarang
connect_asli=socket.socket.connect
def connect(s, alamat):
    assert isinstance(alamat,tuple) and alamat[0]=='127.0.0.1','network_asing'
    return connect_asli(s,alamat)
socket.socket.connect=connect
resolve_asli=socket.getaddrinfo
def resolve(host,*a,**k):
    assert host=='127.0.0.1','dns_asing'
    return resolve_asli(host,*a,**k)
socket.getaddrinfo=resolve
sah={'jawaban':'Satu langkah sintetis.', 'butuh_klarifikasi':False}
legacy={'jawaban':'Usulan sintetis.', 'draft_memori':None,
    'usulan_latihan':{'topik_id':'pola-bilangan','template_ids':['deret_aritmetika'],
                      'level':'P3','jumlah_soal':10}, 'butuh_klarifikasi':False}
def simpan(nama,data): (root/nama).write_text(json.dumps(data,sort_keys=True))
def baca(nama): return json.loads((root/nama).read_text())
def snapshot():
    with contextlib.closing(schema.buka()) as c: return list(c.iterdump())
def sumber(meta):
    with database.buka() as c:
        return context.ambil(c,'soal',meta['resource'],pemilik='guru-probe')
def kirim(c,meta,chat,req,*,callback=None,teks='Pertanyaan sintetis.'):
    ctx=sumber(meta)
    return service.kirim_pesan(c,meta['akun'],chat,teks,request_id=req,
        panggil_provider=callback, konteks=ctx,
        validasi_konteks=lambda:sumber(meta).versi,sekarang=110)
def gagal(aksi,kode):
    try: aksi()
    except (ValueError,service.GalatPendamping): pass
    else: raise AssertionError(kode)
def chat_baru(c,meta):
    asal=store.ambil_chat(c,meta['akun'],meta['chat'])
    return store.buat_chat(c,meta['akun'],'tanpa_memori',sekarang=100,
        context_kind=asal.context_kind,context_id=asal.context_id,
        context_version=asal.context_version,context_resource_version=asal.context_resource_version,
        context_category='soal_resmi')
def periksa_kontrak(c,meta):
    # Aktif legacy maupun tanpa_memori harus identik tanpa katalog/memori outbound.
    import assistant_catalog
    asli_memori=store.memori_untuk_chat;asli_katalog=assistant_catalog.buat_katalog
    def retired(*a,**k): raise AssertionError('payload_retired_kembali')
    store.memori_untuk_chat=retired;assistant_catalog.buat_katalog=retired
    try:
        for mode in ('aktif','tanpa_memori'):
            chat=chat_baru(c,meta) if mode=='tanpa_memori' else store.ambil_chat(c,meta['akun'],meta['chat'])
            payload=json.loads(service._pesan_provider(c,meta['akun'],chat.id,'Sintetis.',konteks=sumber(meta))[-1]['content'])
            assert set(payload)=={'percakapan','konteks'},'payload_retired_kembali'
        assert set(vars(policy.validasi_respons(sah)))=={'jawaban','butuh_klarifikasi'},'kontrak_bukan_dua_field'
        gagal(lambda:policy.validasi_respons(legacy),'respons_legacy_diterima')
    finally:
        store.memori_untuk_chat=asli_memori;assistant_catalog.buat_katalog=asli_katalog

def http_mulai(meta):
    galat=[]
    class Server(ThreadingHTTPServer):
        def handle_error(self,*a): galat.append(1)
    server=Server(('127.0.0.1',0),web.Penangan)
    ulir=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});ulir.start()
    return server,ulir,galat
def request(server,meta,path,data=None,*,cookie=True,origin=True):
    h={'Cookie':'osn_sesi='+meta['token']} if cookie else {}
    if data is not None:
        h['Content-Type']='application/x-www-form-urlencoded'
        if origin: h.update(Origin='http://127.0.0.1:'+str(server.server_port),**{'Sec-Fetch-Site':'same-origin'})
    c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
    try:
        c.request('POST' if data is not None else 'GET',path,
                  body=urlencode(data) if data is not None else None,headers=h)
        r=c.getresponse();return r.status,r.read(),dict(r.getheaders())
    finally:c.close()
def periksa_endpoint(server,meta):
    akun=meta['akun']
    with contextlib.closing(schema.buka()) as c:
        item=next(m for m in store.daftar_memori(c,akun) if m.id==meta['draft'])
        versi=store.versi_memori(c,akun)
    dasar=dict(inline_host='sesi',inline_host_id=str(meta['sesi']),inline_posisi='soal',inline_nomor='1',chat=meta['chat'])
    awal=snapshot()
    for aksi in ('konfirmasi-memori','ubah-memori','aktifkan-memori'):
        field=({'versi_memori':str(versi)} if aksi=='aktifkan-memori' else {'memori':item.id,'versi_item':str(item.versi)})
        assert request(server,meta,'/pendamping/inline/'+aksi,{**dasar,**field})[0]==410,'endpoint_inline_retired_hidup'
    for aksi in ('konfirmasi','ubah'):
        assert request(server,meta,'/pendamping/memori/'+item.id+'/'+aksi,{'versi':str(item.versi)})[0]==410,'endpoint_legacy_retired_hidup'
    assert request(server,meta,'/pendamping/memori/aktifkan',{'versi':str(versi)})[0]==410,'aktivasi_legacy_hidup'
    assert snapshot()==awal,'retirement_mengubah_data'
    return dasar,item
'''

SUMBER_TULIS = BERSAMA + r'''
database.siapkan(database.BAWAAN);schema.siapkan();ai_store.siapkan(root/'ai.db',sekarang=100)
auth.simpan_sandi('sandi-probe-sintetis-123','guru-probe',path=auth.BERKAS_SANDI)
auth.pastikan_metadata_auth(auth.BERKAS_SANDI)
principal=auth.autentikasi('guru-probe','sandi-probe-sintetis-123')
token=sessions.buat_dari_principal(principal)
akun=principal.id_akun
with database.buka() as c:
    anak=database.tambah_siswa(c,'Anak Probe Sintetis','P3',pemilik='guru-probe')
    sesi=database.buat_sesi_dari_urutan(c,anak,17,('deret_aritmetika',),level='P3')
    ctx=context.ambil(c,'soal',str(sesi)+':1',pemilik='guru-probe')
meta=dict(akun=akun,token=token,anak=anak,sesi=sesi,resource=ctx.resource_id)
with database.buka() as c:
    asing_anak=database.tambah_siswa(c,'Anak Asing Sintetis','P3',pemilik='guru-asing')
    asing_sesi=database.buat_sesi_dari_urutan(c,asing_anak,18,('deret_aritmetika',),level='P3')
    asing_ctx=context.ambil(c,'soal',str(asing_sesi)+':1',pemilik='guru-asing')
with contextlib.closing(schema.buka()) as c,c:
    store.beri_persetujuan(c,akun,policy_version=policy.VERSI_KEBIJAKAN,provider_id=policy.PROVIDER_ID,kategori='chat_umum',sekarang=100)
    grant=store.beri_persetujuan_konteks(c,akun,jenis='soal',resource_id=ctx.resource_id,resource_version=ctx.versi,kategori=ctx.kategori,sekarang=100)
    chat=store.buat_chat(c,akun,'aktif',sekarang=100,context_kind='soal',context_id=ctx.resource_id,context_version=grant.versi,context_resource_version=ctx.versi,context_category=ctx.kategori)
    meta['chat']=chat.id
    asing_akun='akun_'+'f'*32
    asing_grant=store.beri_persetujuan_konteks(c,asing_akun,jenis='soal',resource_id=asing_ctx.resource_id,
        resource_version=asing_ctx.versi,kategori=asing_ctx.kategori,sekarang=100)
    asing=store.buat_chat(c,asing_akun,'tanpa_memori',sekarang=100,context_kind='soal',
        context_id=asing_ctx.resource_id,context_version=asing_grant.versi,
        context_resource_version=asing_ctx.versi,context_category=asing_ctx.kategori)
    meta.update(asing_chat=asing.id,asing_sesi=asing_sesi)
    # Legacy fixture: catatan yang sudah tersimpan sebelum retirement, bukan model baru.
    aktif=store.tambah_memori(c,akun,'Jawab singkat.',sumber_chat_id=chat.id,dikonfirmasi=True,sekarang=100)
    draft=store.tambah_memori(c,akun,'Gunakan kalimat pendek.',sumber_chat_id=chat.id,dikonfirmasi=False,sekarang=100)
    store.atur_penggunaan_memori(c,akun,True,versi_diharapkan=store.versi_memori(c,akun),sekarang=100)
    meta.update(memori=aktif.id,draft=draft.id)
    kirim(c,meta,chat.id,'req_pair_legacy',callback=lambda _:sah)
    chat=store.ambil_chat(c,akun,chat.id)
    usulan=actions.validasi_usulan(legacy['usulan_latihan'])
    lama=store.simpan_usulan(c,akun,chat.id,'req_pair_legacy',payload_json=json.dumps(usulan.ke_dict()),
        hash_usulan=actions.hash_usulan(usulan),chat_version=chat.versi,
        consent_version=store.versi_persetujuan(c,akun),context_version=chat.context_version,
        context_resource_version=ctx.versi,sekarang=100)
    meta['usulan']=lama.id
    pending=chat_baru(c,meta);meta['pending']=pending.id
    store.mulai_operasi(c,akun,pending.id,'req_pair_pending',consent_version=store.versi_persetujuan(c,akun),
        memory_version=store.versi_memori(c,akun),context_version=pending.context_version,sekarang=100)
    deleted=chat_baru(c,meta);meta['deleted']=deleted.id
    store.hapus_chat(c,akun,deleted.id,versi_diharapkan=deleted.versi,sekarang=101,retensi_detik=0)
with contextlib.closing(schema.buka()) as c:
    periksa_kontrak(c,meta);c.rollback()
server,ulir,galat=http_mulai(meta)
try:periksa_endpoint(server,meta)
finally:
    server.shutdown();server.server_close();ulir.join(timeout=10)
assert not ulir.is_alive() and not galat,'http_gagal'
simpan('awal.json',meta);simpan('baseline.json',snapshot())
assert not panggilan_provider
print('OSN_ASSISTANT_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
meta=baca('awal.json');akun=meta['akun']
assert snapshot()==baca('baseline.json'),'histori_berubah_saat_recovery'
with contextlib.closing(schema.buka()) as c:
    # 1. Payload/response retirement, termasuk mode aktif legacy dan tanpa_memori.
    periksa_kontrak(c,meta)
    c.rollback()
    # 2. Replay selesai/pending tidak mengirim atau membuat efek samping baru.
    assert kirim(c,meta,meta['chat'],'req_pair_legacy',callback=dilarang)==sah['jawaban']
    gagal(lambda:kirim(c,meta,meta['pending'],'req_pair_pending',callback=dilarang),'pending_dikirim_ulang')
    assert snapshot()==baca('baseline.json'),'replay_mengubah_histori'
    # 3. Usulan lama ditinjau, dikonfirmasi, retry idempoten; marker tetap.
    token=actions.tinjau_usulan(c,akun,'guru-probe',meta['usulan'],sekarang=110)
    item=store.ambil_usulan(c,akun,meta['usulan'])
    parameter=dict(versi=item.versi,hash_diharapkan=item.hash_usulan,request_id=token,sekarang=111)
    hasil=actions.konfirmasi_dan_buat_sesi(c,akun,'guru-probe',item.id,**parameter)
    assert actions.konfirmasi_dan_buat_sesi(c,akun,'guru-probe',item.id,**parameter)==hasil,'usulan_ganda'
    meta['hasil']=hasil
    c.commit()
# 4. Endpoint legacy aktifkan/konfirmasi/ubah ditolak, bukan hanya UI disembunyikan.
server,ulir,galat=http_mulai(meta)
try:
    dasar,item=periksa_endpoint(server,meta)
    # 5. Izin/owner/CSRF tidak dilewati, kontrol lihat/hapus legacy tetap hidup.
    assert request(server,meta,'/pendamping/kelola')[0]==200,'manage_tidak_tersedia'
    assert request(server,meta,'/pendamping/inline/konfirmasi-memori',{**dasar,'memori':item.id,'versi_item':str(item.versi)},origin=False)[0]==403,'csrf_dilewati'
    missing={**dasar,'chat':'chat_'+'f'*32}
    missing_response=request(server,meta,'/pendamping/inline/pesan',{**missing,'request_id':'req_asing','pesan':'Sintetis.'})
    foreign={**dasar,'inline_host_id':str(meta['asing_sesi']),'chat':meta['asing_chat']}
    foreign_response=request(server,meta,'/pendamping/inline/pesan',{**foreign,'request_id':'req_asing','pesan':'Sintetis.'})
    assert missing_response[0]==foreign_response[0]==404 and missing_response[1]==foreign_response[1],'owner_dilewati'
    assert request(server,meta,'/pendamping/inline/hapus-memori',{**dasar,'memori':item.id,'versi_item':str(item.versi),'persetujuan_hapus':'1'})[0]==200,'hapus_legacy_rusak'
finally:
    server.shutdown();server.server_close();ulir.join(timeout=10)
assert not ulir.is_alive() and not galat,'http_gagal'
# 6. Response lama terlambat tidak menulis draft/usulan; provider tiruan saja.
with contextlib.closing(schema.buka()) as c:
    awal=snapshot()
    gagal(lambda:kirim(c,meta,meta['chat'],'req_output_legacy',callback=lambda _:legacy),'output_retired_disimpan')
    assert len(store.daftar_usulan_chat(c,akun,meta['chat']))==1,'usulan_baru_dibuat'
    assert len(store.daftar_memori(c,akun))==1,'draft_baru_dibuat'
    chat=chat_baru(c,meta);c.commit()
    def balasan_baru(pesan):
        assert set(json.loads(pesan[-1]['content']))=={'percakapan','konteks'},'payload_retired_kembali'
        return sah
    assert kirim(c,meta,chat.id,'req_output_baru',callback=balasan_baru)==sah['jawaban']
    assert not store.daftar_usulan_chat(c,akun,chat.id),'usulan_baru_dibuat'
    assert len(store.daftar_memori(c,akun))==1,'draft_baru_dibuat'
    assert store.pesan_dari_request(c,akun,'req_output_legacy:jawaban',peran='asisten') is None
# 7. Fence sebelum client setelah admission dan late-response tombstone tetap aktif.
for timing in ('admission','late'):
    with contextlib.closing(schema.buka()) as c,c:
        chat=chat_baru(c,meta)
    calls=[]
    def hapus():
        with contextlib.closing(schema.buka()) as c,c:
            store.hapus_chat(c,akun,chat.id,versi_diharapkan=chat.versi,sekarang=112,retensi_detik=0)
    def admission(fitur,account,pemanggil,**kw):
        if timing=='admission':hapus()
        return pemanggil()
    def tiruan(*a,**k):
        calls.append(1)
        if timing=='late':hapus()
        return sah
    ai_service.panggil=admission;client.kirim=tiruan
    # Default memakai pagar client asli; mock hanya transport dan admission.
    service.panggil_provider_default=service_default
    with contextlib.closing(schema.buka()) as c:
        gagal(lambda:kirim(c,meta,chat.id,'req_race_'+timing),'race_disimpan')
        assert not store.daftar_pesan(c,akun,chat.id),'late_response_hidup'
    assert len(calls)==(0 if timing=='admission' else 1),'fence_client_dilewati'
client.kirim=dilarang;service.panggil_provider_default=dilarang
# 8. Revoke+reconsent tidak menghidupkan snapshot/deleted chat; data hasil tetap.
import assistant_manage
with contextlib.closing(schema.buka()) as c,c:
    assistant_manage.cabut_semua(c,akun,store.versi_persetujuan(c,akun),sekarang=120)
    store.beri_persetujuan(c,akun,policy_version=policy.VERSI_KEBIJAKAN,provider_id=policy.PROVIDER_ID,kategori='chat_umum',sekarang=121)
    c.commit()  # Cabut/reconsent durable sebelum request terpisah yang ditolak.
    gagal(lambda:kirim(c,meta,meta['chat'],'req_reconsent',callback=dilarang),'reconsent_menghidupkan_chat')
    assert store.ambil_chat(c,akun,meta['deleted']) is None,'tombstone_hidup'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert not panggilan_provider
simpan('akhir.json',meta);simpan('sesudah.json',snapshot())
print('OSN_ASSISTANT_RECOVERY_OK')
'''
SUMBER_KEMBALI = BERSAMA + r'''
meta=baca('akhir.json');akun=meta['akun']
assert snapshot()==baca('sesudah.json'),'readback_berubah'
with contextlib.closing(schema.buka()) as c:
    assert store.ambil_chat(c,akun,meta['deleted']) is None
    gagal(lambda:kirim(c,meta,meta['chat'],'req_readback',callback=dilarang),'readback_menghidupkan_izin')
    assert len(store.daftar_usulan_chat(c,akun,meta['chat']))==1
    assert len(store.daftar_memori(c,akun))==1
    assert c.execute("SELECT status FROM operasi WHERE request_id='req_pair_pending'").fetchone()[0]=='pending'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
with database.buka() as c:
    assert c.execute('SELECT 1 FROM sesi WHERE id=?',(meta['hasil'],)).fetchone()
    assert c.execute('SELECT COUNT(*) FROM eksekusi_pendamping').fetchone()[0]==1
assert not panggilan_provider
print('OSN_ASSISTANT_RETURN_OK')
'''
