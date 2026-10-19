"""Enhancement akun: kata sandi, konfirmasi, galat field, dan kelas belum disimpan.

Tanpa jaringan/autosave. Pesan dimasukkan sebagai teks, bukan HTML. JavaScript
hanya membantu UX; validasi dan kepemilikan tetap ditegakkan server. Bila skrip
tidak tersedia, form native beserta validasi browser tetap dapat digunakan.
"""
from teacher_style import SKRIP_MATA_SANDI

SKRIP_AKUN = SKRIP_MATA_SANDI + """(function(){
  document.querySelectorAll('form[data-konfirmasi]').forEach(function(f){
    f.addEventListener('submit',function(e){
      if(!window.confirm(f.dataset.konfirmasi)){e.preventDefault();}
    });
  });
  document.querySelectorAll('.akun-editorial-st .form-kelas-sekolah').forEach(function(f){
    var pilih=f.querySelector('select'), tombol=f.querySelector('button[type=submit]');
    var awal=pilih.value, status=document.createElement('p');
    status.className='sub akun-status-kelas';
    status.setAttribute('role','status');
    f.appendChild(status);
    function perbarui(){
      var berubah=pilih.value!==awal;
      tombol.disabled=!berubah;
      status.textContent=berubah?'Perubahan kelas belum disimpan.':'Kelas sesuai data tersimpan.';
    }
    pilih.addEventListener('change',perbarui);
    window.addEventListener('pageshow',perbarui);
    perbarui();
  });
  document.querySelectorAll('.akun-editorial-st form[action="/akun"]').forEach(function(f){
    var bidang=Array.from(f.querySelectorAll('input:not([type=hidden]),select'));
    if(!bidang.length){return;}
    var pernah=false, ringkasan=document.createElement('p');
    ringkasan.className='akun-galat-field';
    ringkasan.setAttribute('role','alert');
    f.prepend(ringkasan);
    var pesanBaru={lama:'Masukkan kata sandi lama.',baru:'Masukkan kata sandi baru.',
      ulang:'Ulangi kata sandi baru.',nama:'Masukkan nama panggilan anak.',
      sandi_anak:'Masukkan kata sandi anak.',nama_akun:'Masukkan nama login anak.',
      sandi:'Masukkan kata sandi anak.',siswa_id:'Pilih anak yang akan dibuatkan akun.'};
    bidang.forEach(function(el){
      var pesan=document.createElement('p');
      pesan.id='galat-'+el.id;
      pesan.className='akun-galat-field';
      var target=el.closest('.kolom-sandi')||el;
      target.insertAdjacentElement('afterend',pesan);
      var bantuan=el.getAttribute('aria-describedby')||'';
      el.setAttribute('aria-describedby',(bantuan+' '+pesan.id).trim());
      el._pesanAkun=pesan;
      el.addEventListener('input',function(){if(pernah){validasi(false);}});
      el.addEventListener('change',function(){if(pernah){validasi(false);}});
    });
    function validasi(fokus){
      var pertama=null, jumlah=0;
      bidang.forEach(function(el){
        var pesan='', nilai=el.value, sandi=el.autocomplete.indexOf('password')!==-1;
        if(el.required && !(sandi?nilai:nilai.trim())){
          pesan=pesanBaru[el.name]||'Isi bagian ini.';
        }else if(nilai && el.minLength>0 && Array.from(nilai).length<el.minLength){
          pesan='Kata sandi minimal '+el.minLength+' karakter.';
        }else if(nilai && el.maxLength>0 && Array.from(nilai).length>el.maxLength){
          pesan='Maksimal '+el.maxLength+' karakter.';
        }else if(el.name==='ulang' && nilai!==f.elements.namedItem('baru').value){
          pesan='Kata sandi baru dan ulangannya tidak sama.';
        }else if(el.name==='baru' && f.elements.namedItem('lama') && nilai===f.elements.namedItem('lama').value){
          pesan='Kata sandi baru harus berbeda dari kata sandi lama.';
        }else if(!el.validity.valid){
          pesan='Periksa isian ini.';
        }
        el._pesanAkun.textContent=pesan;
        if(pesan){el.setAttribute('aria-invalid','true');jumlah++;if(!pertama){pertama=el;}}
        else{el.removeAttribute('aria-invalid');}
      });
      ringkasan.textContent=jumlah?'Periksa '+jumlah+' isian yang ditandai.':'';
      if(pertama && fokus){pertama.focus();}
      return !pertama;
    }
    // Hanya sesudah semua listener siap; tanpa JS validasi native tetap aktif.
    f.noValidate=true;
    f.addEventListener('submit',function(e){pernah=true;if(!validasi(true)){e.preventDefault();}});
  });
})();"""
