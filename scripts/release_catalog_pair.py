"""Probe katalog baru untuk gate image exact; hanya data sintetis pada volume uji."""
# Ditempel ke probe existing agar menjalankan modul milik image, bukan host.
TULIS = r'''
from catalog_versions import versi_writer, TEMPLATE_DIPERBAIKI
# Hanya proses sandbox probe sintetis: exercise writer2 meski aktivasi aplikasi
# menunggu manusia. Reader B tidak mengikuti flag C. Pulihkan flag di akhir.
_catalog_flag_lama=os.environ.get('OSN_KATALOG_VERSI')
os.environ['OSN_KATALOG_VERSI']='2'
catalog_versi=versi_writer()
catalog_pembahasan=[]
if catalog_versi==2:
    from topics import daftar_topik,ambil
    for topik in daftar_topik():
        if topik=='campuran':continue
        for lv,tids in ambil(topik).komposisi.items():
            soal_katalog=[]
            for tid in sorted(set(tids)&TEMPLATE_DIPERBAIKI):
                cabang=set()
                for seed in range(25):
                    baru=buat_soal(tid,seed,lv,topik)
                    p=baru.parameter
                    varian=(p.get('varian'),p.get('tanya'),p.get('bangun'))
                    if varian in cabang:continue
                    cabang.add(varian)
                    lama=replace(REGISTRI[tid](**{k:v for k,v in p.items() if k not in ('versi_katalog','konteks_umur')}),level=lv)
                    assert database.simpan_soal(c,lama)!=database.simpan_soal(c,baru), 'identitas_katalog_tabrakan'
                    soal_katalog.extend((lama,baru))
            if not soal_katalog:continue
            sid=database.buat_sesi_dari_urutan(c,anak,50,tuple(s.template_id for s in soal_katalog),
                topik=topik,level=lv,soal_terpilih=tuple(soal_katalog))
            sesi.append(sid)
            catalog_pembahasan.append((sid,[s.pembahasan for s in soal_katalog]))
            for b in database.isi_sesi(c,sid):
                database.simpan_jawaban(c,b['sesi_soal_id'],b['kunci'],'perhitungan sintetis')
            import reports
            reports.diagnosa_murid(c,sid)
            assert all(b['benar']==1 for b in database.isi_sesi(c,sid)), 'diagnosis_katalog_berubah'
            database.tandai_selesai(c,sid)
            database.konfirmasi_hasil(c,sid,'guru')
            # Opsi PG harus cocok bank baru, juga sesudah writer dimundurkan.
            sid_pg=database.buat_sesi(c,anak,51,topik=topik,level=lv,format_jawaban='pilihan_ganda')
            sesi.append(sid_pg)
if _catalog_flag_lama is None:
    os.environ.pop('OSN_KATALOG_VERSI',None)
else:
    os.environ['OSN_KATALOG_VERSI']=_catalog_flag_lama
'''
BACA = r'''
    if m.get('catalog_versi',1)==2:
        import importlib.util
        assert importlib.util.find_spec('catalog_versions') is not None, 'reader_katalog_baru_belum_didukung'
        for sid,pembahasan in m['catalog_pembahasan']:
            assert [question_views.soal_dari_baris(b).pembahasan for b in database.isi_sesi(c,sid)]==pembahasan, 'pembahasan_katalog_berubah'
'''
