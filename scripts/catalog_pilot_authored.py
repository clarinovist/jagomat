"""Draf item tetap authored untuk lengan B, bukan hasil ekspor template.

Ditulis offline oleh agent, belum ditinjau manusia. Nol malrule disengaja:
ketidaktersediaan diagnosis/PG dicatat, bukan diisi angka palsu demi kuota.
"""

ITEM = {
'pecahan_operasi_campuran': (
 ({'n1':1,'d1':3,'n2':1,'d2':4,'n3':1,'d3':6},'5/12',
  'Hitung 1/3 + 1/4 − 1/6. Tuliskan nilai tepatnya.', 'Dalam per dua belas: 4/12 + 3/12 − 2/12 = 5/12.'),
 ({'n1':3,'d1':4,'n2':2,'d2':5,'n3':1,'d3':8},'41/40',
  'Tentukan hasil tepat 3/4 + 2/5 − 1/8.', 'Penyebut 40 memberi 30/40 + 16/40 − 5/40 = 41/40.'),
 ({'n1':5,'d1':6,'n2':1,'d2':3,'n3':3,'d3':4},'5/12',
  'Berapakah 5/6 + 1/3 − 3/4? Jangan dibulatkan.', 'Ubah ke per dua belas: 10 + 4 − 9 = 5, jadi 5/12.'),
 ({'n1':3,'d1':5,'n2':1,'d2':4,'n3':1,'d3':6},'41/60',
  'Hitung nilai tepat dari 3/5 + 1/4 − 1/6.', 'Pakai penyebut 60: 36/60 + 15/60 − 10/60 = 41/60.'),
 ({'n1':7,'d1':8,'n2':1,'d2':6,'n3':1,'d3':3},'17/24',
  'Tentukan 7/8 + 1/6 − 1/3 dalam nilai tepat.', 'Dalam per dua puluh empat: 21/24 + 4/24 − 8/24 = 17/24.'),
 ({'n1':2,'d1':3,'n2':3,'d2':8,'n3':1,'d3':4},'19/24',
  'Berapakah hasil tepat 2/3 + 3/8 − 1/4?', 'Samakan penyebut ke 24: 16/24 + 9/24 − 6/24 = 19/24.'),
),
'pecahan_kali_bagi': (
 ({'n1':2,'d1':3,'n2':3,'d2':5,'op':'kali'},'2/5',
  'Hitung 2/3 × 3/5 tanpa pembulatan.', 'Kalikan pembilang dan penyebut: 6/15 = 2/5.'),
 ({'n1':3,'d1':4,'n2':2,'d2':7,'op':'kali'},'3/14',
  'Tentukan nilai tepat 3/4 × 2/7.', 'Hasil perkalian 6/28 disederhanakan menjadi 3/14.'),
 ({'n1':5,'d1':6,'n2':3,'d2':8,'op':'kali'},'5/16',
  'Berapakah 5/6 × 3/8?', 'Kalikan menjadi 15/48, lalu bagi pembilang dan penyebut dengan 3: 5/16.'),
 ({'n1':2,'d1':3,'n2':4,'d2':5,'op':'bagi'},'5/6',
  'Hitung nilai tepat 2/3 ÷ 4/5.', 'Balik pecahan kedua: 2/3 × 5/4 = 10/12 = 5/6.'),
 ({'n1':3,'d1':7,'n2':2,'d2':5,'op':'bagi'},'15/14',
  'Tentukan hasil 3/7 ÷ 2/5 tanpa pembulatan.', 'Pembagian menjadi 3/7 × 5/2 = 15/14.'),
 ({'n1':5,'d1':8,'n2':3,'d2':4,'op':'bagi'},'5/6',
  'Berapakah nilai tepat 5/8 ÷ 3/4?', 'Kalikan 5/8 dengan 4/3: 20/24 = 5/6.'),
),
'menyusul': (
 ({'jarak':40,'v1':40,'v2':60},'2','Mobil A melaju tetap 40 km/jam. Mobil B berada 40 km di belakang dan melaju tetap 60 km/jam searah. Mulai sekarang, berapa jam sampai B menyusul A?', 'B menutup jarak 20 km setiap jam. Jarak 40 km tertutup dalam 2 jam.'),
 ({'jarak':30,'v1':30,'v2':60},'1','Bus bergerak tetap 30 km/jam. Mobil 30 km di belakang bergerak tetap 60 km/jam searah. Berapa jam dari sekarang hingga mobil menyusul?', 'Selisih laju 30 km/jam menutup jarak 30 km dalam 1 jam.'),
 ({'jarak':60,'v1':25,'v2':45},'3','Kendaraan pertama melaju tetap 25 km/jam. Pengejar di belakang sejauh 60 km melaju tetap 45 km/jam pada arah yang sama. Berapa jam hingga bertemu?', 'Setiap jam jarak berkurang 20 km. Setelah 3 jam, seluruh 60 km tertutup.'),
 ({'jarak':100,'v1':50,'v2':75},'4','Mobil depan melaju tetap 50 km/jam; mobil belakang 75 km/jam searah. Selisih posisi sekarang 100 km. Berapa jam sampai keduanya sejajar?', 'Jarak mengecil 25 km per jam, maka 100 : 25 = 4 jam.'),
 ({'jarak':150,'v1':30,'v2':60},'5','Dua kendaraan bergerak searah dengan kecepatan tetap 30 dan 60 km/jam. Kendaraan cepat berada 150 km di belakang. Berapa jam dari sekarang untuk menyusul?', 'Selisih kecepatan 30 km/jam. Lima jam menutup 150 km.'),
 ({'jarak':40,'v1':20,'v2':40},'2','Kendaraan lambat 20 km/jam berada 40 km di depan kendaraan 40 km/jam. Keduanya bergerak searah dengan laju tetap. Berapa jam hingga bertemu?', 'Selisih laju 20 km/jam. Waktu untuk menutup 40 km adalah 2 jam.'),
),
'satuan_waktu_lama': (
 ({'varian':'windu_ke_lustrum','nilai':5},'8','Lima windu sama dengan berapa lustrum?', 'Satu windu 8 tahun, satu lustrum 5 tahun. Lima windu 40 tahun, yaitu 8 lustrum.'),
 ({'varian':'windu_ke_lustrum','nilai':10},'16','Ubah 10 windu menjadi lustrum.', 'Sepuluh windu 80 tahun. Dibagi 5 tahun per lustrum menjadi 16.'),
 ({'varian':'windu_ke_lustrum','nilai':15},'24','Berapa lustrum yang setara dengan 15 windu?', 'Lima belas kali 8 adalah 120 tahun, setara 24 lustrum.'),
 ({'varian':'windu_ke_lustrum','nilai':25},'40','Tentukan banyak lustrum dalam 25 windu.', 'Dua puluh lima windu 200 tahun. Dua ratus dibagi 5 = 40 lustrum.'),
 ({'varian':'windu_ke_lustrum','nilai':40},'64','Empat puluh windu sama dengan berapa lustrum?', 'Empat puluh windu 320 tahun. Tiga ratus dua puluh dibagi 5 = 64.'),
 ({'varian':'windu_ke_lustrum','nilai':125},'200','Ubah 125 windu ke satuan lustrum.', 'Seratus dua puluh lima windu = 1000 tahun = 200 lustrum.'),
),
'luas_permukaan': (
 ({'varian':'tabung_LP','r':7,'t':3},'440','Tabung tertutup berjari-jari 7 cm dan tinggi 3 cm. Dengan π = 22/7, berapa luas permukaannya dalam cm²?', 'Dua lingkaran luasnya 308 cm², selimutnya 132 cm². Total 440 cm².'),
 ({'varian':'tabung_LP','r':10,'t':5},'942','Tabung tertutup memiliki jari-jari 10 cm dan tinggi 5 cm. Gunakan π = 3,14. Berapa luas seluruh permukaannya dalam cm²?', 'Dua alas 628 cm² ditambah selimut 314 cm² = 942 cm².'),
 ({'varian':'tabung_LP','r':14,'t':6},'1760','Hitung luas permukaan tabung tertutup, r = 14 cm dan tinggi 6 cm, dengan π = 22/7. Jawab dalam cm².', 'Dua lingkaran 1232 cm² dan selimut 528 cm² menghasilkan 1760 cm².'),
 ({'varian':'tabung_cari_t','r':7,'LP':616},'7','Luas permukaan tabung tertutup 616 cm², jari-jari 7 cm. Jika π = 22/7, berapa tingginya dalam cm?', 'Kurangi dua lingkaran 308 cm². Selimut 308 cm² dibagi keliling 44 cm memberi tinggi 7 cm.'),
 ({'varian':'tabung_cari_t','r':5,'LP':471},'10','Sebuah tabung tertutup mempunyai luas permukaan 471 cm² dan jari-jari 5 cm. Gunakan π = 3,14. Berapa tinggi tabung dalam cm?', 'Dua lingkaran 157 cm². Sisa 314 cm² dibagi keliling 31,4 cm menghasilkan 10 cm.'),
 ({'varian':'tabung_cari_t','r':14,'LP':2288},'12','Luas permukaan tabung tertutup 2288 cm² dan jari-jari 14 cm. Gunakan π = 22/7. Tentukan tingginya dalam cm.', 'Kurangi 1232 cm² untuk dua lingkaran. Selimut 1056 cm² dibagi keliling 88 cm memberi 12 cm.'),
),
}
