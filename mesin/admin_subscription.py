"""Permukaan admin langganan: baca ledger dan query pembayaran yang sudah ada."""

from dataclasses import dataclass
import json

import admin_accounts
import admin_registration
import admin_store
import admin_launch_service as guard
import auth
import midtrans_contract
import subscription as d
import subscription_store as store


@dataclass(frozen=True, repr=False)
class RuntimePembayaran:
    config: object
    transport: object
    sakelar: d.Sakelar
    kesiapan: object = None


RUNTIME = None
_BELUM_SIAP = {
    'provider_produksi': False, 'callback': False, 'recovery': False,
    'kebijakan': False,
}


def kesiapan_penangan(penangan):
    """Readiness berasal runtime tepercaya, bukan field form atau config Admin."""
    runtime = getattr(penangan.server, 'pembayaran_runtime', None)
    data = getattr(runtime, 'kesiapan', None)
    if (not isinstance(runtime, RuntimePembayaran) or type(data) is not dict
            or set(data) != set(_BELUM_SIAP)
            or any(type(v) is not bool for v in data.values())):
        return dict(_BELUM_SIAP)
    return dict(data)


def runtime_penangan(penangan):
    """Runtime eksplisit; sakelar Admin tidak pernah mengaktifkan provider sendiri."""
    import subscription_http
    runtime = subscription_http.runtime(penangan)
    if runtime is not None:
        return RuntimePembayaran(runtime.config, runtime.transport,
                                 d.Sakelar(fondasi=True, buat_pembayaran=True,
                                           rekonsiliasi=True), dict(_BELUM_SIAP))
    runtime = getattr(penangan.server, 'pembayaran_runtime', None)
    if (not isinstance(runtime, RuntimePembayaran)
            or getattr(runtime.config, 'lingkungan', None) != 'production'
            or not callable(runtime.transport)):
        return None
    return RuntimePembayaran(runtime.config, runtime.transport,
                             sakelar_runtime(admin_store.BAWAAN),
                             kesiapan_penangan(penangan))


def _otorisasi(path_auth, principal):
    return guard.principal_hidup(auth.muat_akun(path_auth),principal)


def sakelar_runtime(path_admin):
    """Reader fail-closed untuk caller runtime; tidak membuka provider/secret."""
    try:
        with admin_store.buka_baca(path_admin) as kon:
            return guard.sakelar_pembayaran(kon)
    except (admin_store.StoreBelumSiap, ValueError):
        return d.SAKELAR


def daftar(path,path_auth,principal,*,halaman=1,cari=''):
    _otorisasi(path_auth,principal)
    if type(halaman) is not int or not 1 <= halaman <= 10000 or len(cari)>80:
        raise ValueError('filter tidak sah')
    akun={a['id_akun']:a['pengguna'] for a in auth.muat_akun(path_auth) if a.get('peran')=='guru'}
    cocok=tuple(k for k,v in akun.items() if cari.casefold() in v.casefold()) if cari else ()
    with admin_store.buka_baca(path) as kon:
        if cari and not cocok:
            return (),0
        where=' WHERE akun_id IN (%s)' % ','.join('?' for _ in cocok) if cari else ''
        total=kon.execute('SELECT COUNT(*) FROM langganan_enrollment'+where,cocok).fetchone()[0]
        rows=kon.execute('SELECT akun_id,mulai,peserta_promo,asal FROM langganan_enrollment'+where+' ORDER BY mulai DESC,akun_id LIMIT 25 OFFSET ?',(*cocok,(halaman-1)*25)).fetchall()
        hasil = tuple({**dict(r),'alias':akun.get(r['akun_id'],'Akun tidak tersedia')} for r in rows)
    _otorisasi(path_auth, principal)
    return hasil, total


def detail(path,path_auth,principal,akun_id,*,sekarang):
    _otorisasi(path_auth,principal)
    d.identitas(akun_id,'akun'); d.waktu(sekarang)
    with admin_store.buka_baca(path) as kon:
        kon.execute('BEGIN')
        e=store._enrollment(kon,akun_id)
        store.validasi_ledger(kon,akun_id=akun_id)
        grants=store._grants(kon,akun_id)
        akses=d.akses(e,grants,sekarang=sekarang)
        invoices=[]
        for r in kon.execute('SELECT invoice_id,urutan,rupiah,dibuat,kedaluwarsa,promo,profil_json FROM langganan_invoice WHERE akun_id=? ORDER BY urutan DESC LIMIT 100',(akun_id,)):
            receipts=tuple(dict(x) for x in kon.execute('SELECT hasil,diterima,rupiah FROM langganan_receipt WHERE invoice_id=?',(r['invoice_id'],)))
            grant=next((g for g in grants if g.invoice_id==r['invoice_id']),None)
            observ=kon.execute('SELECT status,diamati FROM langganan_rekonsiliasi WHERE invoice_id=? ORDER BY diamati DESC,operasi_id DESC LIMIT 1',(r['invoice_id'],)).fetchone()
            intent=kon.execute('SELECT 1 FROM langganan_rekonsiliasi WHERE operasi_id=?',('create_'+r['invoice_id'][4:],)).fetchone()
            status=('perlu_diperiksa' if any(x['hasil']=='perlu_diperiksa' for x in receipts)
                    else 'lunas' if grant else observ['status'] if observ else 'belum_terverifikasi')
            invoices.append({**dict(r),'status':status,'receipt':receipts,'grant':grant,
                             'dapat_periksa':bool(intent),'jumlah_profil':len(json.loads(r['profil_json']))})
        cakupan=kon.execute('SELECT profil_json,urutan,revisi FROM langganan_cakupan WHERE akun_id=? ORDER BY urutan DESC,revisi DESC LIMIT 1',(akun_id,)).fetchone()
    akun=next((a for a in auth.muat_akun(path_auth) if a.get('id_akun')==akun_id and a.get('peran')=='guru'),None)
    _otorisasi(path_auth,principal)
    return dict(akun_id=akun_id,alias=akun['pengguna'] if akun else 'Akun tidak tersedia',
                enrollment=e,akses=akses,grants=grants,invoices=tuple(invoices),
                jumlah_profil=len(json.loads(cakupan['profil_json'])) if cakupan else 0,
                promo_tersisa=max(0,3-sum(g.promo for g in grants)) if e.peserta_promo else 0)


def _snapshot(path,path_auth,kon,akun_id,invoice_id,target_revisi):
    """Pemanggil memegang lock DB→auth, tanpa jaringan atau grant terselubung."""
    akun=next((a for a in auth.muat_akun(path_auth) if a.get('id_akun')==akun_id),None)
    if not akun or akun.get('peran')!='guru' or auth.revisi_auth(akun)!=target_revisi:
        raise LookupError('resource tidak ditemukan')
    inv=store.baca_invoice(path,akun_id,invoice_id)
    for sid in json.loads(inv['profil_json']):
        r=kon.execute('SELECT pemilik FROM siswa WHERE id=?',(sid,)).fetchone()
        if not r or r[0]!=akun['pengguna']:
            raise LookupError('resource tidak ditemukan')
    return inv


def periksa(path,path_auth,path_db,principal,*,akun_id,invoice_id,target_revisi,operasi,sekarang,runtime=None,periksa_sesi=None,jam=None):
    """Serialize operasi yang sama, bukan menahan transaksi selama provider."""
    import admin_service
    _otorisasi(path_auth,principal)
    d.identitas(operasi,'operasi')
    with admin_service.kunci_operasi(path,operasi):
        return _periksa_terkunci(path,path_auth,path_db,principal,akun_id=akun_id,
                                invoice_id=invoice_id,target_revisi=target_revisi,
                                operasi=operasi,sekarang=sekarang,runtime=runtime,
                                periksa_sesi=periksa_sesi,jam=jam)


def _periksa_terkunci(path,path_auth,path_db,principal,*,akun_id,invoice_id,target_revisi,operasi,sekarang,runtime,periksa_sesi,jam):
    """Hanya query order tersimpan; receipt/grant existing tetap tepat-sekali."""
    _otorisasi(path_auth,principal)
    runtime=runtime if runtime is not None else RUNTIME
    if runtime is None:
        raise d.FiturNonaktif('rekonsiliasi provider belum dikonfigurasi')
    runtime.sakelar.wajib('rekonsiliasi')
    d.waktu(sekarang)
    # Urutan fencing tetap DB→auth→admin; jaringan berada di luar semua lock.
    with admin_registration.kunci_database_pemilik(path_db) as belajar:
        with guard.kunci_principal(path_auth,principal):
            inv=_snapshot(path,path_auth,belajar,akun_id,invoice_id,target_revisi)
            if inv['merchant']!=runtime.config.merchant or sekarang<inv['dibuat']:
                raise ValueError('konfigurasi pembayaran berbeda')
            with admin_store._transaksi(path) as kon:
                if not kon.execute('SELECT 1 FROM langganan_rekonsiliasi WHERE operasi_id=?',('create_'+invoice_id[4:],)).fetchone():
                    raise ValueError('belum ada intent pembayaran')
                aktif = kon.execute("SELECT COUNT(*) FROM layanan_operasi WHERE aksi='periksa_pembayaran' AND dibuat>? AND operasi_id!=?", (sekarang-60,operasi)).fetchone()[0]
                if aktif >= 10:
                    raise d.FiturNonaktif('batas pemeriksaan pembayaran tercapai')
                lama=guard.reservasi(kon,principal,operasi,'periksa_pembayaran',invoice_id,[akun_id,invoice_id,target_revisi],sekarang)
                if lama and lama['status']!='tertunda':
                    return lama['hasil']
    if periksa_sesi is not None and not periksa_sesi():
        raise LookupError('resource tidak ditemukan')
    hasil=midtrans_contract.periksa_status(runtime.config,inv,akun_id=akun_id,
                                           transport=runtime.transport,sakelar=runtime.sakelar)
    selesai = d.waktu(int(jam())) if jam is not None else sekarang
    if selesai < sekarang:
        raise ValueError('clock mundur saat pemeriksaan')
    sekarang = selesai
    with admin_registration.kunci_database_pemilik(path_db) as belajar:
        with guard.kunci_principal(path_auth,principal):
            if periksa_sesi is not None and not periksa_sesi():
                raise LookupError('resource tidak ditemukan')
            _snapshot(path,path_auth,belajar,akun_id,invoice_id,target_revisi)
            status='belum_terverifikasi'
            if hasil.bukti is not None:
                status=store.terapkan_pembayaran(path,akun_id,hasil.bukti,sekarang=sekarang,sakelar=runtime.sakelar)
            elif hasil.status=='perlu_diperiksa':
                status='perlu_diperiksa'
            store.catat_pengamatan(path,akun_id,invoice_id,operasi_id=operasi,
                                  status='settlement' if status=='grant' else status,sekarang=sekarang,sakelar=runtime.sakelar)
            with admin_store._transaksi(path) as kon:
                guard.selesaikan(kon,operasi,status,sekarang)
            return status
