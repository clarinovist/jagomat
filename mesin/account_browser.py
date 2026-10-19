"""Enhancement akun terbatas: mata kata sandi dan konfirmasi destruktif.

Tanpa jaringan atau validasi otomatis. Nilai konfirmasi berasal dari atribut
HTML escaped, tidak disisipkan ke kode JavaScript. Form native tetap tersedia.
"""
from teacher_style import SKRIP_MATA_SANDI

SKRIP_AKUN = SKRIP_MATA_SANDI + """document.querySelectorAll('form[data-konfirmasi]').forEach(function(f){
  f.addEventListener('submit',function(e){
    if(!window.confirm(f.dataset.konfirmasi)){e.preventDefault();}
  });
});"""
