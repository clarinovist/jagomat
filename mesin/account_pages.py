"""Akun keluarga: kata sandi, profil anak, dan pemulihan login kontekstual.

Admin hanya mengganti kata sandi sendiri di permukaan ini; pengelolaan
lintas keluarga berada di pusat kendali admin. Guard tetap di server.
"""

from __future__ import annotations

import html

import auth
import database
import learning_profile
import learning_profile_ui
from templates import LEVEL, label_kelas, level_valid
from teacher_pages import _halaman
from account_browser import SKRIP_AKUN



PETA_SECTION_AKUN = {
    # Aksi POST /akun -> section tempat hasilnya ditampilkan, supaya
    # pengguna kembali ke tempat formnya, bukan melompat ke bawaan.
    "sandi": "akun",
    "anak_baru": "siswa",
    "tingkat": "siswa",
    "kelas_sekolah": "siswa",
    "siswa_hapus": "siswa",
    "akun_murid_tambah": "siswa",
    "akun_murid_hapus": "siswa",
    "akun_murid_sandi": "siswa",
}

def _kartu_akun_murid(kon, pengguna: str | None = None, peran: str = "guru") -> str:
    """Pemulihan kontekstual untuk profil tanpa login atau login tanpa profil.

    Guru hanya melihat akun keluarganya. Akun yang sudah terpasang tidak
    diulang di sini; kata sandinya dikelola dari daftar anak.
    """
    import students as _murid

    filter_siswa = None if (peran == "admin" or pengguna is None) else pengguna
    daftar_siswa = database.daftar_siswa(kon, filter_siswa)
    akun_murid = [a for a in auth.muat_akun() if a.get("peran") == "murid"]
    if pengguna is not None and peran != "admin":
        akun_murid = [
            a
            for a in akun_murid
            if _akun_murid_milik(kon, pengguna, peran, a["pengguna"])
        ]

    akun_murid = [a for a in akun_murid if _murid.siswa_dari_akun(kon, a['pengguna']) is None]
    if akun_murid:
        baris = ""
        for a in akun_murid:
            nama = a["pengguna"]
            nama_esc = html.escape(nama)
            penanda = ' <span class="status-buruk">tidak terpasang pada profil anak</span>'
            baris += (
                f'<tr><td data-label="Nama">{nama_esc}{penanda}</td>'
                f'<td data-label="Aksi">'
                f'<div class="baris-aksi">'
                f'<form method="post" action="/akun" '
                f'class="akun-form-aksi" '
                f'data-konfirmasi="Hapus akun login {nama_esc}? '
                f'Akun ini tidak bisa dipakai masuk lagi. Profil dan riwayat belajar tidak dihapus.">'
                f'<input type="hidden" name="aksi" value="akun_murid_hapus">'
                f'<input type="hidden" name="nama" value="{nama_esc}">'
                f'<button type="submit" class="tombol-bahaya-akun">Hapus login {nama_esc}</button></form>'
                f"</div>"
                f"</td></tr>"
            )
    else:
        baris = ''

    # Form pembuat akun sengaja kontekstual: alur normal (Tambah anak)
    # sudah membuatkan akun sekaligus, jadi form permanen cuma jadi
    # duplikasi yang membingungkan — dan memungkinkan akun kedua untuk
    # anak yang sama. Ia hanya tampil bila ada anak yang belum
    # terhubung: warisan lama, atau akun yang terhapus tanpa sengaja.
    belum_terhubung = [
        s
        for s in daftar_siswa
        if _murid.akun_murid_dari_siswa(kon, s["id"]) is None
    ]

    if belum_terhubung:
        opsi = "".join(
            f'<option value="{s["id"]}">{html.escape(s["nama"])}</option>'
            for s in belum_terhubung
        )
        pilih = (
            '<select id="pulihkan-siswa" name="siswa_id" required>'
            '<option value="">— pilih anak —</option>' + opsi + "</select>"
        )
        tambah = (
            f'<form method="post" action="/akun" class="akun-pulihkan">'
            f'<input type="hidden" name="aksi" value="akun_murid_tambah">'
            f'<p class="sub">Anak berikut belum punya akun masuk — '
            f"buatkan di sini:</p>"
            f'<div class="baris">'
            f'<div><label for="pulihkan-siswa">Anak</label>'
            f"{pilih}</div>"
            f'<div><label for="pulihkan-nama">Nama untuk masuk</label>'
            f'<input id="pulihkan-nama" type="text" name="nama_akun" placeholder="mis. bima-santoso" required>'
            '<p class="sub">Nama login harus unik. Jika sudah dipakai keluarga lain, pilih nama lain.</p></div>'
            f"</div>"
            f'<div><label for="pulihkan-sandi">Kata sandi baru (minimal 8 karakter)</label>'
            f'<input id="pulihkan-sandi" type="password" name="sandi" autocomplete="new-password" required minlength="8">'
            f"</div>"
            f'<p class="akun-aksi-pulihkan"><button type="submit">Buat akun masuk</button></p>'
            f"</form>"
        )
    elif daftar_siswa:
        tambah = (
            '<p class="sub akun-status-login">Semua anak sudah '
            "punya akun masuk.</p>"
        )
    else:
        # Belum ada anak sama sekali: jalurnya kartu Tambah anak di
        # section Siswa, bukan di sini.
        tambah = ""

    tabel = (
        '<h3>Akun login tanpa profil anak</h3>'
        '<p class="sub">Menghapus login hanya mencabut akses masuk akun tersebut, '
        'bukan menghapus profil atau riwayat belajar anak.</p>'
        f'<div class="tabel-wrap"><table><tr><th>Nama login</th><th>Aksi</th></tr>{baris}</table></div>'
    ) if baris else ''
    return f'<div class="akun-pemulihan">{tabel}{tambah}</div>'

def _baris_siswa(kon, s: dict, pengguna: str | None, peran: str) -> str:
    """Identitas login dan alasan penolakan hapus; guard server tetap otoritatif."""
    import students as _murid

    nama = html.escape(s["nama"])
    if pengguna and peran == "guru":
        profil = learning_profile.baca(kon, s["id"], pemilik=pengguna)
        kelas = learning_profile_ui.form_kelas(profil, s["nama"])
        kelas_label = learning_profile.label_kelas_sekolah(profil.kelas_sekolah)
    else:
        kelas = ""
        kelas_label = "Kelas belum diisi"
    sesi = kon.execute(
        "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (s["id"],)
    ).fetchone()["n"]
    login = _murid.akun_murid_dari_siswa(kon, s["id"])
    if login:
        status = f'Login: {html.escape(login)}'
        sandi = (
            '<form method="post" action="/akun" class="akun-form-aksi akun-form-sandi">'
            '<input type="hidden" name="aksi" value="akun_murid_sandi">'
            f'<input type="hidden" name="nama" value="{html.escape(login)}">'
            f'<label class="pendamping-sr" for="sandi-baru-{s["id"]}">'
            f"Kata sandi baru untuk {nama} (minimal 8 karakter)</label>"
            f'<input id="sandi-baru-{s["id"]}" type="password" name="baru" '
            'placeholder="Kata sandi baru" autocomplete="new-password" minlength="8" required class="input-sandi-kecil">'
            f'<button type="submit" class="tombol-sekunder" aria-label="Simpan kata sandi {nama}">'
            'Simpan kata sandi</button>'
            "</form>"
        )
    else:
        status = (
            '<a class="status-buruk" href="/akun?section=siswa#perbaikan-login">'
            "belum ada login</a>"
        )
        sandi = ""
    alasan_hapus = ''
    if sesi:
        alasan_hapus = f'Punya {sesi} sesi latihan; tidak bisa dihapus.'
    elif kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='registrasi_profil_anak'"
    ).fetchone() and kon.execute(
        'SELECT 1 FROM registrasi_profil_anak WHERE siswa_id = ? LIMIT 1', (s['id'],)
    ).fetchone():
        alasan_hapus = 'Profil pendaftaran dilindungi; tidak bisa dihapus di sini.'
    if alasan_hapus:
        hapus = (
            f'<div><button type="button" class="tombol-bahaya-akun" disabled '
            f'aria-describedby="alasan-hapus-{s["id"]}">Hapus {nama}</button>'
            f'<p class="sub" id="alasan-hapus-{s["id"]}">{alasan_hapus}</p></div>'
        )
    else:
        hapus = (
            f'<form method="post" action="/akun" class="akun-form-hapus" '
            f'data-konfirmasi="Hapus anak {nama} beserta akun loginnya? '
            'Profil akan dihapus permanen dan akun tidak bisa dipakai masuk lagi.">'
            '<input type="hidden" name="aksi" value="siswa_hapus">'
            f'<input type="hidden" name="siswa_id" value="{s["id"]}">'
            f'<button type="submit" class="tombol-bahaya-akun">Hapus {nama}</button></form>'
        )
    bagian_kelas = (
        f'<div class="akun-kelola-bagian"><h4>Kelas sekolah</h4>{kelas}</div>' if kelas else ''
    )
    bagian_sandi = (
        f'<div class="akun-kelola-bagian"><h4>Kata sandi anak</h4>{sandi}</div>' if sandi else ''
    )
    return (
        f'<article class="akun-anak-kartu" aria-labelledby="anak-nama-{s["id"]}">'
        '<div class="akun-anak-kepala">'
        f'<h3 id="anak-nama-{s["id"]}">{nama}</h3>'
        f'<p class="akun-anak-meta">{html.escape(kelas_label)} · {status} · {sesi} sesi latihan</p></div>'
        '<details class="akun-kelola"><summary>Kelola</summary>'
        f'<div class="akun-kelola-isi">{bagian_kelas}{bagian_sandi}'
        f'<div class="akun-kelola-bagian"><h4>Hapus anak</h4>{hapus}</div></div></details>'
        '</article>'
    )

def _perlu_perbaikan_login(kon, pengguna, peran) -> bool:
    """Ada anak tanpa login atau akun yatim? Buka subbagian bila ya."""
    import students as _murid

    filter_siswa = None if (peran == "admin" or pengguna is None) else pengguna
    for s in database.daftar_siswa(kon, filter_siswa):
        if _murid.akun_murid_dari_siswa(kon, s["id"]) is None:
            return True
    akun_murid = [a for a in auth.muat_akun() if a.get("peran") == "murid"]
    if pengguna is not None and peran != "admin":
        akun_murid = [
            a
            for a in akun_murid
            if _akun_murid_milik(kon, pengguna, peran, a["pengguna"])
        ]
    return any(
        _murid.siswa_dari_akun(kon, a["pengguna"]) is None for a in akun_murid
    )


def halaman_akun(
    kon,
    pesan: str = "",
    galat: str = "",
    pengguna: str | None = None,
    peran: str = "guru",
    section: str = "akun",
    arsip_pendamping: str = "",
    privat: bool = False,
    analitik: str = "",
    langganan_sandbox: bool = False,
    langganan_produksi: bool = False,
    langganan_html: str = "",
) -> bytes:
    """Kelola kata sandi dan anak; navigasi native, mata/konfirmasi berhash.

    Satu halaman, tiga section via ?section=: "akun" (ganti sandi),
    "siswa" (daftar anak + perbaikan login kasus tepi),
    "langganan" (ringkasan checkout inline, drill-down invoice tetap di
    /langganan/<inv>). "akun-murid" tetap diterima sebagai alias lama
    menuju "siswa".
    Nilai tak dikenal jatuh ke "akun". Admin hanya mendapat bagian akun
    sendiri dan arsip. Argumen `privat` lama tetap diterima; semua tab
    kini memakai bingkai privat tanpa aset pihak ketiga.

    `pengguna`/`peran` berasal dari sesi: guru melihat & mengelola
    keluarganya saja. Panggilan langsung tanpa `pengguna` (mode lokal,
    test) melihat semuanya — perilaku lama.

    Sandi bisa diganti dari sini supaya sandi acak hasil deploy tidak jadi
    satu-satunya yang pernah ada. Siswa ber-riwayat sengaja tidak bisa
    dihapus dari sini — penjelasan singkat ada di bawah daftar siswa;
    siswa tanpa riwayat boleh dihapus beserta akun latihannya.
    """
    if section not in ("akun", "siswa", "akun-murid", "arsip-pendamping", "langganan"):
        # Nilai asing dari URL jatuh ke bawaan.
        section = "akun"
    if section == "akun-murid":
        # Alias lama: tab Akun latihan sudah digabung ke Siswa.
        section = "siswa"
    if peran == "admin" and section not in ("akun", "arsip-pendamping"):
        section = "akun"

    daftar = "".join(
        _baris_siswa(kon, s, pengguna, peran)
        for s in database.daftar_siswa(kon, None if peran == "admin" else pengguna)
    ) or '<p class="kosong">Belum ada anak. Tambahkan anak pertama di bawah.</p>'

    kabar = f'<div class="pesan" role="status">{html.escape(pesan)}</div>' if pesan else ""
    if galat:
        kabar += f'<div class="pesan galat" role="alert">{html.escape(galat)}</div>'

    if pengguna is not None:
        pengguna_tampil = html.escape(pengguna)
    else:
        d = auth.muat_sandi()
        if not d:
            pengguna_tampil = "(belum disetel)"
        elif "akun" in d:
            g = next((a for a in d["akun"] if a.get("peran") in ("guru", "admin")), None)
            pengguna_tampil = html.escape(g["pengguna"]) if g else "(belum disetel)"
        else:
            pengguna_tampil = html.escape(d["pengguna"])

    kartu_sandi = (
        f'<div class="kartu-st akun-kartu-sandi">'
        f'<div class="kartu-judul"><span class="ikon-kartu">🔑</span>'
        f"<h2>Ganti kata sandi</h2></div>"
        f'<p class="sub">Nama login Anda: <b>{pengguna_tampil}</b>. Setelah diganti, '
        f'masuk lagi dengan kata sandi baru.</p>'
        '<p class="sub"><a href="/lupa-sandi">Bantuan pemulihan akun</a>. '
        'Untuk keluar, buka menu nama akun di kanan atas lalu pilih <b>Keluar</b>.</p>'
        f'<form method="post" action="/akun">'
        f'<input type="hidden" name="aksi" value="sandi">'
        f'<label for="sandi-lama">Kata sandi lama</label>'
        f'<input id="sandi-lama" type="password" name="lama" autocomplete="current-password" required>'
        f'<label for="sandi-baru">Kata sandi baru (minimal 12 karakter)</label>'
        f'<input id="sandi-baru" type="password" name="baru" autocomplete="new-password" minlength="12" required>'
        f'<label for="sandi-ulang">Ulangi kata sandi baru</label>'
        f'<input id="sandi-ulang" type="password" name="ulang" autocomplete="new-password" required>'
        f'<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">Ganti kata sandi</button></p>'
        f"</form></div>"
    )
    kartu_siswa = (
        f'<div class="kartu-st">'
        f'<div class="kartu-judul"><span class="ikon-kartu">📚</span>'
        f"<h2>Daftar anak</h2></div>"
        '<p class="sub" id="keterangan-kelas">Kelas sekolah SD 1–6 bersifat opsional. '
        'Kelas hanya informasi profil, bukan kemampuan anak. Pilih kelas lalu tekan Simpan kelas.</p>'
        '<details class="rincian-ui-st"><summary>Tentang kelas dan sesi latihan</summary>'
        '<p class="sub">Mengubah kelas tidak mengubah soal lama atau memulai ulang rencana belajar. '
        'Sesi latihan adalah satu kumpulan soal yang disiapkan untuk anak, termasuk yang belum selesai.</p></details>'
        f'<div class="akun-anak-daftar">{daftar}</div>'
        '<p class="sub akun-catatan-hapus">Anak dengan riwayat sesi tidak bisa dihapus. '
        'Profil pendaftaran juga dilindungi. Profil lain tanpa sesi dapat dihapus beserta akun loginnya.</p></div>'
    )
    kartu_anak = (
        f'<div class="kartu-st">'
        f'<div class="kartu-judul"><span class="ikon-kartu">🧒</span>'
        f"<h2>Tambah anak</h2></div>"
        '<p class="sub">Buat profil dan akun login anak sekaligus. '
        'Gunakan nama panggilan atau inisial untuk menjaga privasi. '
        'Gratis selama akses awal nonkomersial.</p>'
        f'<form method="post" action="/akun">'
        f'<input type="hidden" name="aksi" value="anak_baru">'
        f'<div class="baris">'
        f'<div><label for="anak-nama">Nama anak (nama panggilan)</label>'
        f'<input id="anak-nama" type="text" name="nama" placeholder="mis. Aisha" maxlength="40" required></div>'
        f'<div><label for="anak-kelas">Kelas sekolah (opsional)</label>'
        f'<select id="anak-kelas" name="kelas_sekolah" aria-describedby="keterangan-kelas">'
        + learning_profile_ui.opsi_kelas()
        + '</select></div></div>'
        f'<label for="anak-login">Nama login anak (opsional — bawaan sama dengan nama anak)'
        f"</label>"
        f'<input id="anak-login" type="text" name="nama_akun" '
        f'placeholder="mis. aisha2" aria-describedby="bantuan-login-anak">'
        '<p class="sub" id="bantuan-login-anak">Kosongkan untuk memakai nama anak. '
        'Jika nama login sudah dipakai, pilih nama lain atau tambahkan angka. Ketersediaan diperiksa saat disimpan.</p>'
        f'<label for="anak-sandi">Kata sandi anak (minimal 8 karakter)</label>'
        '<p class="sub" id="bantuan-sandi-anak">Pilih gabungan kata yang mudah diingat, '
        'tetapi berbeda dari kata sandi orang tua. Jangan memakai nama atau tanggal lahir anak.</p>'
        f'<input id="anak-sandi" type="password" name="sandi_anak" autocomplete="new-password" '
        f'required minlength="8" aria-describedby="bantuan-sandi-anak">'
        '<p class="sub">Penggunaan data anak mengikuti '
        '<a href="/kebijakan-privasi" target="_blank" rel="noopener">Kebijakan Privasi</a> '
        'dalam persetujuan awal. Tidak perlu mencentang persetujuan lagi untuk setiap anak. '
        'Menambah anak tidak mengubah pilihan penggunaan data tambahan.</p>'
        f'<button type="submit" class="tombol-utama-akun">Buat anak &amp; akunnya</button>'
        f"</form></div>"
    )
    if section == "langganan" and peran == "guru" and (langganan_produksi or langganan_sandbox):
        isi_section = langganan_html or (
            '<div class="kartu-st"><h2>Langganan</h2>'
            '<p class="sub">Ringkasan langganan belum tersedia. '
            '<a href="/langganan">Buka halaman tagihan</a>.</p></div>'
        )
    elif section == "langganan":
        section = "akun"
        isi_section = kartu_sandi
        if arsip_pendamping:
            isi_section += (
                '<div class="kartu-st"><details><summary>Arsip percakapan lama</summary>'
                '<p class="sub">Percakapan umum lama tersedia hanya-baca.</p>'
                '<a href="/akun?section=arsip-pendamping">Buka arsip</a>'
                '</details></div>'
            )
    elif section == "siswa" and peran != "admin":
        sub_login = ''
        if _perlu_perbaikan_login(kon, pengguna, peran):
            sub_login = (
                '<details class="kartu-st rincian-ui-st" id="perbaikan-login" open>'
                '<summary>Perbaikan login anak</summary>'
                '<p class="sub">Ada profil tanpa akun masuk atau akun login tanpa profil anak. '
                'Buat akun masuk untuk profil yang belum memilikinya.</p>'
                f'{_kartu_akun_murid(kon, pengguna, peran)}</details>'
            )
        isi_section = kartu_siswa + kartu_anak + sub_login
    elif section == "arsip-pendamping":
        isi_section = arsip_pendamping or kartu_sandi
        if not arsip_pendamping:
            section = "akun"
    else:
        isi_section = kartu_sandi
        if arsip_pendamping:
            isi_section += (
                '<div class="kartu-st"><details><summary>Arsip percakapan lama</summary>'
                '<p class="sub">Percakapan umum lama tersedia hanya-baca.</p>'
                '<a href="/akun?section=arsip-pendamping">Buka arsip</a>'
                '</details></div>'
            )

    if section == 'akun' and peran == 'guru':
        isi_section += (
            '<section class="kartu-st"><h2>Data Pendamping AI</h2>'
            '<p>Kelola chat tersimpan dan izin pengiriman AI, juga saat pengiriman AI tidak tersedia.</p>'
            '<a href="/pendamping/kelola">Kelola data Pendamping</a></section>'
        )
        isi_section += analitik
    item = [("akun", "Akun saya", "/akun?section=akun")]
    if peran != "admin":
        item.append(("siswa", "Anak", "/akun?section=siswa"))
    if arsip_pendamping:
        item.append(("arsip-pendamping", "Arsip percakapan lama", "/akun?section=arsip-pendamping"))
    if peran == "guru":
        if langganan_produksi:
            item.append(("langganan", "Langganan", "/akun?section=langganan"))
        elif langganan_sandbox:
            item.append(("langganan", "Langganan sandbox", "/akun?section=langganan"))
    nav = "".join(
        f'<a href="{href}"'
        + (' class="aktif" aria-current="page"' if sid == section else "")
        + f'>{label}</a>'
        for sid, label, href in item
    )

    return _halaman(
        "Akun",
        f'<div class="jejak"><a href="{"/admin" if peran == "admin" else "/guru"}">&larr; Beranda</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">AKUN KELUARGA</p>'
        '<h1 id="judul-akun">Akun &amp; pengaturan</h1>'
        '<p class="sub">Kelola akses dan ruang belajar keluarga.</p></header>'
        f"{kabar}"
        f'<div class="layout-samping">'
        f'<nav class="nav-samping" aria-label="Pengaturan akun">{nav}</nav>'
        f"<div>{isi_section}</div>"
        f"</div>",
        ident=(pengguna or "guru", peran),
        stitch=True, kelas_bungkus="pendamping-editorial-st akun-editorial-st",
        id_utama="judul-akun", privat=True,
        skrip_privat='' if section == 'arsip-pendamping' else SKRIP_AKUN,
    )

def _akun_murid_milik(kon, pengguna: str, peran: str, nama: str) -> bool:
    """Apakah akun murid `nama` boleh dikelola oleh pengguna ini?

    Admin boleh semua. Guru hanya akun murid yang terikat ke siswa
    miliknya — lewat siswa_id eksplisit, atau (akun warisan) lewat nama
    siswa ber-pemilik dirinya.
    """
    if peran == "admin":
        return True
    a = auth.cari_akun(nama)
    if not a or a.get("peran") != "murid":
        return False
    if a.get("siswa_id") is not None:
        return database.siswa_milik(kon, int(a["siswa_id"]), pengguna)
    baris = kon.execute(
        "SELECT 1 FROM siswa WHERE nama = ? COLLATE NOCASE AND pemilik = ?",
        (nama, pengguna),
    ).fetchone()
    return baris is not None

def proses_akun(
    kon, data: dict, pengguna_kini: str, peran: str = "guru"
) -> tuple[str, str]:
    """Jalankan aksi halaman akun. Mengembalikan (pesan, galat).

    Sandi lama SELALU diverifikasi ulang, walaupun pengguna sudah lolos
    palang untuk membuka halaman ini. Peramban menyimpan kredensial Basic
    dan mengirimkannya otomatis, jadi tanpa pemeriksaan ini siapa pun yang
    menemukan laptop dalam keadaan terbuka bisa mengganti sandi tanpa tahu
    yang lama.

    Multi-keluarga: siswa yang dibuat tercatat ber-pemilik pengguna_kini,
    dan aksi ber-id (tingkat, akun murid) hanya menyentuh milik sendiri —
    admin bebas, dengan `peran="admin"`.
    """
    aksi = data.get("aksi", "")

    if aksi == "sandi":
        lama = data.get("lama", "")
        baru = data.get("baru", "")
        ulang = data.get("ulang", "")

        if not auth.periksa(pengguna_kini, lama):
            return "", "Sandi lama salah."
        if baru != ulang:
            return "", "Sandi baru dan ulangannya tidak sama."
        if len(baru) < 12:
            return "", "Sandi baru minimal 12 karakter."
        if baru == lama:
            return "", "Sandi baru sama dengan yang lama."

        auth.simpan_sandi(baru, pengguna_kini)
        return (
            "Sandi diganti. Masuk lagi dengan sandi baru.",
            "",
        )

    if aksi == "anak_baru":
        """Onboarding publik: siswa + akun murid sekaligus (atomic).

        Validasi SEMUA dulu sebelum menulis apa pun — siswa yang dibuat
        lalu akunnya gagal meninggalkan siswa tanpa akun ("anak yatim")
        yang hanya bisa dirapikan manual lewat halaman akun.
        """
        nama = data.get("nama", "").strip()
        # UI baru mengirim tanpa field profil; payload lama yang sah tetap dibaca
        # untuk kompatibilitas retry/integrasi, tanpa mengaitkannya ke kelas.
        tingkat = data.get('profil_parameter', data.get('tingkat', '')).strip() or ''
        sandi_anak = data.get("sandi_anak", "")
        # Nama login boleh beda dari nama anak — jalannya bila nama anak
        # sudah dipakai keluarga lain sebagai login (nama anak tetap unik
        # per keluarga, nama login unik global).
        nama_akun = (data.get("nama_akun") or "").strip() or nama

        if not nama:
            return "", "Nama anak tidak boleh kosong."
        if len(nama) > 40:
            return "", "Nama terlalu panjang."
        if ('profil_parameter' in data and 'tingkat' in data) or 'level' in data:
            return '', 'Form pengaturan soal lama tidak cocok. Muat ulang sebelum menambahkan anak.'
        if tingkat and not level_valid(tingkat):
            return '', 'Pilihan variasi soal tidak sah. Muat ulang formulir.'
        try:
            kelas = learning_profile_ui.baca_kelas_form(data.get('kelas_sekolah', ''))
        except ValueError as galat:
            return '', str(galat)
        if len(sandi_anak) < 8:
            return "", "Kata sandi anak minimal 8 karakter."
        if kon.execute(
            "SELECT 1 FROM siswa WHERE lower(nama) = lower(?) AND pemilik = ?",
            (nama, pengguna_kini),
        ).fetchone():
            return "", f"Siswa bernama {nama} sudah ada di keluargamu."
        if auth.cari_akun(nama_akun) is not None:
            return "", (f"Nama login {nama_akun} sudah dipakai keluarga lain. "
                        "Tambahkan angka/inisial, mis. aisha2.")

        siswa_id = database.tambah_siswa(kon, nama, tingkat, pemilik=pengguna_kini)
        learning_profile.simpan_kelas(kon, siswa_id, kelas, revisi=0, pemilik=pengguna_kini)
        try:
            auth.tambah_akun(nama_akun, sandi_anak, "murid", siswa_id=siswa_id)
        except ValueError as e:
            # Pembuatan akun meledak di tengah: batalkan siswa yang baru
            # dibuat supaya tidak ada anak yatim tanpa akun.
            kon.execute(
                "DELETE FROM siswa WHERE id = ? AND NOT EXISTS "
                "(SELECT 1 FROM sesi WHERE sesi.siswa_id = siswa.id)",
                (siswa_id,),
            )
            return "", str(e)
        return (
            f"Anak {nama} ditambahkan ({learning_profile.label_kelas_sekolah(kelas)}) "
            f"beserta akun loginnya. Kembali ke daftar anak, buka profil {nama}, "
            f"lalu ikuti langkah di Beranda untuk menyiapkan latihan awal. "
            f"Anak masuk lewat /murid dengan nama login {nama_akun}.",
            "",
        )

    if aksi == 'kelas_sekolah':
        # Periksa resource sebelum validasi isi agar asing/hilang identik.
        if peran != 'guru':
            raise learning_profile.ProfilTidakDitemukan('Profil tidak ditemukan.')
        try:
            siswa_id = int(data.get('siswa_id', ''))
            if not 0 < siswa_id <= 9_223_372_036_854_775_807:
                raise ValueError('ID di luar rentang')
        except (ValueError, TypeError):
            raise learning_profile.ProfilTidakDitemukan('Profil tidak ditemukan.')
        learning_profile.baca(kon, siswa_id, pemilik=pengguna_kini)
        try:
            kelas = learning_profile_ui.baca_kelas_form(data.get('kelas_sekolah'))
            revisi = learning_profile_ui.baca_revisi_form(data.get('revisi_profil'))
            learning_profile.simpan_kelas(
                kon, siswa_id, kelas, revisi=revisi, pemilik=pengguna_kini,
            )
        except learning_profile.ProfilTidakDitemukan:
            raise
        except ValueError as galat:
            return '', str(galat)
        return 'Kelas sekolah disimpan. Konteks latihan dan rencana belajar tidak berubah.', ''

    if aksi == "tingkat":
        # Jalur programatis warisan, bukan perubahan kelas sekolah.
        # Menaikkan level anak. Sesi LAMA tidak ikut berubah — levelnya
        # tersimpan di baris sesi masing-masing, jadi riwayat tetap terbaca
        # apa adanya. Yang berubah hanya sesi yang dibuat setelah ini.
        try:
            siswa_id = int(data.get("siswa_id", ""))
        except ValueError:
            return "", "Siswa tidak dikenal."
        tingkat = data.get("tingkat", "").strip()
        if not level_valid(tingkat):
            return "", f"Kelas harus salah satu dari: {', '.join(label_kelas(lv) for lv in LEVEL)}."
        baris = kon.execute(
            "SELECT nama FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        if not baris or (
            peran != "admin"
            and not database.siswa_milik(kon, siswa_id, pengguna_kini)
        ):
            return "", "Siswa tidak dikenal."
        database.ganti_level(kon, siswa_id, tingkat)
        return (
            f"{baris['nama']} sekarang {label_kelas(tingkat)}. Sesi lama tetap pada "
            f"kelasnya masing-masing; yang berubah hanya sesi berikutnya.",
            "",
        )

    if aksi == "siswa_hapus":
        # Pengaman riwayat: menghapus siswa = CASCADE menghapus seluruh
        # sesi, jawaban, dan diagnosisnya. Yang sudah berriwayat sengaja
        # tak bisa dihapus; yang kosong (salah ketik / data uji) boleh,
        # dan akun latihannya ikut dihapus supaya tak ada anak yatim.
        try:
            siswa_id = int(data.get("siswa_id", ""))
        except ValueError:
            return "", "Siswa tidak dikenal."
        baris = kon.execute(
            "SELECT nama FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        if not baris or (
            peran != "admin"
            and not database.siswa_milik(kon, siswa_id, pengguna_kini)
        ):
            return "", "Siswa tidak dikenal."
        nama = baris["nama"]
        n_sesi = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchone()["n"]
        if n_sesi:
            return (
                "",
                f"{nama} masih punya {n_sesi} sesi. Siswa ber-riwayat "
                f"sengaja tidak bisa dihapus — sesi, jawaban, dan "
                f"diagnosisnya tidak bisa dibangun ulang.",
            )
        # Receipt registrasi append-only: hapus wajib ditahan SEBELUM efek auth
        # apa pun supaya tidak ada receipt yatim yang merusak validasi backup.
        if kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='registrasi_profil_anak'"
        ).fetchone() and kon.execute(
            "SELECT 1 FROM registrasi_profil_anak WHERE siswa_id = ? LIMIT 1", (siswa_id,)
        ).fetchone():
            return (
                "",
                f"{nama} punya bukti registrasi profil anak. Siswa "
                f"ber-receipt pendaftaran sengaja tidak bisa dihapus.",
            )
        import students as _murid

        login = _murid.akun_murid_dari_siswa(kon, siswa_id)
        if login:
            auth.hapus_akun(login)
        kon.execute("DELETE FROM siswa WHERE id = ?", (siswa_id,))
        return f"Siswa {nama} dihapus beserta akun latihannya.", ""

    if aksi == "akun_murid_tambah":
        nama_siswa = (data.get("nama") or "").strip()
        nama_akun = (data.get("nama_akun") or "").strip()
        sandi_baru = data.get("sandi", "")
        # kalau form lama masih mengirim "baru", dukung juga
        if not sandi_baru:
            sandi_baru = data.get("baru", "")

        siswa_id = None
        if data.get("siswa_id"):
            # Bentuk form baru: pilih siswa dari dropdown milik sendiri,
            # lalu tentukan nama login-nya (boleh berbeda dari nama siswa).
            try:
                siswa_id = int(data["siswa_id"])
            except ValueError:
                return "", "Siswa tidak dikenal."
            if peran != "admin" and not database.siswa_milik(
                kon, siswa_id, pengguna_kini
            ):
                return "", "Siswa tidak dikenal."
            baris = kon.execute(
                "SELECT nama FROM siswa WHERE id = ?", (siswa_id,)
            ).fetchone()
            nama_siswa = baris["nama"]
        elif nama_siswa:
            # Bentuk lama: nama akun = nama siswa. Pencarian dibatasi ke
            # keluarga sendiri supaya nama dobel antar keluarga tak ambigu.
            if peran == "admin":
                baris = kon.execute(
                    "SELECT id, nama FROM siswa WHERE nama = ? COLLATE NOCASE",
                    (nama_siswa,),
                ).fetchone()
            else:
                baris = kon.execute(
                    "SELECT id, nama FROM siswa "
                    "WHERE nama = ? COLLATE NOCASE AND pemilik = ?",
                    (nama_siswa, pengguna_kini),
                ).fetchone()
            if not baris:
                return "", f"Siswa bernama {nama_siswa} tidak ditemukan."
            siswa_id = int(baris["id"])
        else:
            return "", "Pilih siswanya dulu."

        import students as _murid

        # Satu anak satu akun: dropdown form kontekstual sudah menyaring,
        # tetapi POST tidak boleh dipercaya — tanpa pagar ini anak yang
        # sudah terhubung bisa diam-diam dapat akun kedua, padahal
        # seluruh aplikasi mengasumsikan satu akun satu anak.
        login_lama = _murid.akun_murid_dari_siswa(kon, siswa_id)
        if login_lama:
            return "", f"{nama_siswa} sudah punya akun masuk ({login_lama})."

        if not nama_akun:
            nama_akun = nama_siswa
        if len(sandi_baru) < 8:
            return "", "Sandi murid minimal 8 karakter."
        try:
            auth.tambah_akun(nama_akun, sandi_baru, "murid", siswa_id=siswa_id)
        except ValueError as e:
            return "", str(e)
        return f"Akun murid {nama_akun} ditambahkan.", ""

    if aksi == "akun_murid_hapus":
        nama = data.get("nama", "").strip()
        if not nama:
            return "", "Nama tidak boleh kosong."
        if not _akun_murid_milik(kon, pengguna_kini, peran, nama):
            return "", f"Akun {nama} tidak ditemukan."
        ok = auth.hapus_akun(nama)
        if not ok:
            return "", f"Akun {nama} tidak ditemukan."
        return f"Akun murid {nama} dihapus.", ""

    if aksi == "akun_murid_sandi":
        nama = data.get("nama", "").strip()
        baru = data.get("baru", "")
        if not nama:
            return "", "Nama tidak boleh kosong."
        if len(baru) < 8:
            return "", "Sandi murid minimal 8 karakter."
        if not _akun_murid_milik(kon, pengguna_kini, peran, nama):
            return "", f"Akun {nama} tidak ditemukan."
        ok = auth.setel_sandi_murid(nama, baru)
        if not ok:
            return "", f"Akun {nama} tidak ditemukan."
        return f"Sandi {nama} diperbarui.", ""

    return "", "Aksi tidak dikenal."
