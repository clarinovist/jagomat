# Mesin latihan — container terisolasi.
#
# Berjalan sebagai user tanpa hak istimewa. Aplikasi ini memuat data anak,
# jadi tidak menumpang user `sekolahdesain` yang dipakai layanan lain dan
# punya cron auto-pull ke repo kerja.
#
# Tanpa dependensi pihak ketiga: seluruh aplikasi hanya memakai stdlib,
# sehingga image-nya tetap kecil dan tidak ada yang perlu diperbarui karena
# CVE pustaka.

FROM python:3.12-slim

# Pengguna khusus, bukan root. UID/GID dipatok agar berkas basis data di
# volume tetap dimiliki pengguna yang sama setelah image dibangun ulang.
RUN groupadd -g 10001 osn && useradd -u 10001 -g osn -m -s /usr/sbin/nologin osn

WORKDIR /app

# Hanya berkas aplikasi. Basis data dan sandi TIDAK ikut masuk image —
# keduanya datang dari volume saat dijalankan.
#
# Sejak A4: SELURUH .py root disalin lewat wildcard, bukan daftar manual.
# Daftar manual pernah menjadi insiden 25 Agustus 2026: render.py & students.py
# lahir tapi tidak masuk daftar, image terbangun "sukses", deploy gagal
# sehat karena import error, dan rollback otomatis yang menyelamatkan situs
# justru menyembunyikan penyebabnya — di lokal semua test hijau karena
# filenya ada; yang hilang hanya di dalam image. Dengan wildcard, modul apa
# pun yang ada di repo otomatis ada di image; guard test_image.py menegakkan
# kontrak ini dan menolak kembalinya daftar manual.
COPY --chown=osn:osn *.py /app/

# Aset brand (favicon, lockup, og-image, ikon PWA) — non-.py, jadi wildcard
# di atas TIDAK membawanya. Tanpa baris ini favicon 404 di produksi meski
# semua test hijau di lokal: pola insiden 25 Agustus 2026 terulang, kali ini
# untuk berkas biner. Guard: __tests__/test_brand.py.
COPY --chown=osn:osn aset/ /app/aset/

# Basis data & sandi tinggal di volume supaya selamat saat container diganti.
ENV OSN_BERKAS_SANDI=/data/sandi.json \
    OSN_BERKAS_SESI=/data/sesi.json \
    OSN_BERKAS_DB=/data/latihan.db \
    PENDAMPING_BERKAS_DB=/data/pendamping.db \
    AI_BERKAS_DB=/data/ai-control.db \
    PENDAMPING_AKTIF=0 \
    OSN_FOLDER_LEMBAR=/data/lembar \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /data && chown osn:osn /data
VOLUME ["/data"]

USER osn
EXPOSE 8724

# Pemeriksaan kesehatan: 401 dihitung SEHAT, karena justru menandakan server
# menjawab DAN palang sandi aktif. Yang tidak sehat adalah tidak menjawab
# sama sekali, atau menjawab 200 tanpa diminta sandi (palang jebol).
COPY --chown=osn:osn healthcheck.py /app/
HEALTHCHECK --interval=60s --timeout=8s --start-period=15s --retries=3 \
  CMD ["python", "/app/healthcheck.py"]

CMD ["python", "serve.py", "--jaringan", "--port", "8724"]
