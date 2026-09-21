"""Halaman akun (guru) & admin: kelola siswa, akun latihan, sandi.

Dipecah dari web.py (refactor 31 Aug 2026) — fungsi pindah utuh, perilaku
identik. Frame halaman diimpor dari teacher_pages. Admin baca-semua-
tulis-tidak: penulisan tetap ditolak di router (web.py).
"""

from __future__ import annotations

import html

import auth
import database
import learning_profile
import learning_profile_ui
import question_variants_ui
from question_context import label_profil_parameter
from templates import LEVEL, label_kelas, level_valid
from teacher_pages import _halaman



PETA_SECTION_AKUN = {
    # Aksi POST /akun -> section tempat hasilnya ditampilkan, supaya
    # pengguna kembali ke tempat formnya, bukan melompat ke bawaan.
    "sandi": "akun",
    "anak_baru": "siswa",
    "tingkat": "siswa",
    "kelas_sekolah": "siswa",
    "siswa_hapus": "siswa",
    "akun_murid_tambah": "akun-murid",
    "akun_murid_hapus": "akun-murid",
    "akun_murid_sandi": "akun-murid",
}

def _kartu_akun_murid(kon, pengguna: str | None = None, peran: str = "guru") -> str:
    """Kartu akun murid di halaman akun.

    Pola persis kartu Siswa: tabel + form di bawahnya. Daftar akun diambil
    dari auth.muat_akun() yang disaring peran == murid. Tiap akun dicek
    kecocokannya dengan tabel siswa lewat students.siswa_dari_akun; kalau tidak
    cocok ditandai jelas "belum terhubung ke siswa" supaya guru tahu kenapa
    anak tidak bisa masuk. Guru hanya melihat & mengelola akun keluarganya;
    panggilan langsung tanpa `pengguna` (mode lokal / test) melihat semua.
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

    if akun_murid:
        baris = ""
        for a in akun_murid:
            nama = a["pengguna"]
            nama_esc = html.escape(nama)
            sid = _murid.siswa_dari_akun(kon, nama)
            if sid is None:
                status = '<span class="status-buruk">belum terhubung ke siswa</span>'
            else:
                status = '<span class="status-ok">terhubung</span>'
            baris += (
                f'<tr><td data-label="Nama">{nama_esc}</td><td data-label="Status">{status}</td><td data-label="Aksi">'
                f'<div class="baris-aksi">'
                f'<form method="post" action="/akun" '
                f'style="display:inline-flex;gap:.3rem;align-items:center" '
                f'onsubmit="return confirm(\'Hapus akun ini? Anaknya tetap '
                f'ada — hanya loginnya yang hilang.\')">'
                f'<input type="hidden" name="aksi" value="akun_murid_hapus">'
                f'<input type="hidden" name="nama" value="{nama_esc}">'
                f'<button type="submit" class="tombol-kecil tombol-hapus">Hapus</button>'
                f"</form> "
                f'<form method="post" action="/akun" style="display:inline-flex;gap:.3rem;align-items:center;margin-left:.4rem">'
                f'<input type="hidden" name="aksi" value="akun_murid_sandi">'
                f'<input type="hidden" name="nama" value="{nama_esc}">'
                f'<label>Sandi baru untuk {nama_esc}'
                f'<input type="password" name="baru" placeholder="sandi baru" required class="input-sandi-kecil"></label>'
                f'<button type="submit" class="tombol-kecil">Setel sandi baru</button>'
                f"</form>"
                f"</div>"
                f"</td></tr>"
            )
    else:
        baris = '<tr><td colspan="3" class="kosong">belum ada akun murid</td></tr>'

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
            f'<form method="post" action="/akun" style="margin-top:.8rem">'
            f'<input type="hidden" name="aksi" value="akun_murid_tambah">'
            f'<p class="sub">Anak berikut belum punya akun masuk — '
            f"buatkan di sini:</p>"
            f'<div class="baris">'
            f'<div><label for="pulihkan-siswa">Anak</label>'
            f"{pilih}</div>"
            f'<div><label for="pulihkan-nama">Nama untuk masuk</label>'
            f'<input id="pulihkan-nama" type="text" name="nama_akun" placeholder="mis. bima-santoso" required></div>'
            f"</div>"
            f'<div><label for="pulihkan-sandi">Sandi baru (minimal 8 karakter)</label>'
            f'<input id="pulihkan-sandi" type="password" name="sandi" placeholder="sandi untuk murid" required minlength="8">'
            f"</div>"
            f'<p style="margin-top:.6rem"><button type="submit">Buat akun masuk</button></p>'
            f"</form>"
        )
    elif daftar_siswa:
        tambah = (
            '<p class="sub" style="margin-top:.8rem">Semua anak sudah '
            "punya akun masuk.</p>"
        )
    else:
        # Belum ada anak sama sekali: jalurnya kartu Tambah anak di
        # section Siswa, bukan di sini.
        tambah = ""

    return (
        f'<div class="kartu"><h2>Akun murid</h2>'
        f"<p class=\"sub\">Akun murid dipakai anak untuk masuk ke /murid. "
        f"Nama untuk masuk harus unik di seluruh aplikasi — kalau sudah "
        f"dipakai keluarga lain, pakai variasi lain (mis. tambah nama belakang).</p>"
        f'<div class="tabel-wrap"><table><tr><th>Nama</th><th>Status</th><th>Aksi</th></tr>{baris}</table></div>'
        f"{tambah}"
        f"</div>"
    )

def status_akun_latihan(kon, siswa_id: int) -> str:
    """Sel status akun latihan untuk tabel siswa.

    Nama login bila anaknya sudah punya akun, penanda jelas bila belum —
    supaya jelas bahwa menghapus akun latihan tidak menghapus anaknya.
    Penandanya sekaligus tautan ke section Akun latihan, tempat satu-
    satunya form pembuat akun (kontekstual) tinggal — jadi status
    langsung mengarahkan ke alat perbaikannya.
    """
    import students as _murid

    nama = _murid.akun_murid_dari_siswa(kon, siswa_id)
    if nama:
        return f'<span class="status-ok">{html.escape(nama)}</span>'
    return (
        '<a class="status-buruk" href="/akun?section=akun-murid">'
        "belum ada login</a>"
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
) -> bytes:
    """Kelola sandi dan daftar siswa — sidebar + section, tanpa JS.

    Satu halaman, tiga section via ?section=: "akun" (ganti sandi),
    "siswa" (daftar anak + hapus aman), "akun-murid" (akun latihan anak).
    Nilai tak dikenal jatuh ke "akun". Admin full-write (4 Sep 2026)
    melihat SEMUA keluarga di section siswa/akun-murid.

    `pengguna`/`peran` berasal dari sesi: guru melihat & mengelola
    keluarganya saja. Panggilan langsung tanpa `pengguna` (mode lokal,
    test) melihat semuanya — perilaku lama.

    Sandi bisa diganti dari sini supaya sandi acak hasil deploy tidak jadi
    satu-satunya yang pernah ada. Siswa ber-riwayat sengaja tidak bisa
    dihapus dari sini — penjelasannya ada di kartu Catatan, section
    siswa; siswa tanpa riwayat boleh dihapus beserta akun latihannya.
    """
    if section not in ("akun", "siswa", "akun-murid", "arsip-pendamping"):
        # Nilai asing dari URL jatuh ke bawaan.
        section = "akun"
    if peran == "admin" and section not in ("akun", "arsip-pendamping"):
        section = "akun"

    daftar = "".join(
        f'<tr><td data-label="Nama">{html.escape(s["nama"])}</td>'
        f'<td data-label="Kelas sekolah">'
        + (learning_profile_ui.form_kelas(
            learning_profile.baca(kon, s['id'], pemilik=pengguna), s['nama']
        ) if pengguna and peran == 'guru' else 'Kelas belum diisi')
        + '</td>'
        f'<td class="angka" data-label="Sesi">'
        f'{kon.execute("SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (s["id"],)).fetchone()["n"]}'
        f"</td>"
        f'<td data-label="Akun latihan">{status_akun_latihan(kon, s["id"])}</td>'
        f'<td data-label="Aksi"><form method="post" action="/akun" style="display:inline-flex">'
        f'<input type="hidden" name="aksi" value="siswa_hapus">'
        f'<input type="hidden" name="siswa_id" value="{s["id"]}">'
        f'<button type="submit" class="tombol-kecil tombol-hapus">Hapus</button>'
        f"</form></td></tr>"
        for s in database.daftar_siswa(kon, None if peran == "admin" else pengguna)
    ) or '<tr><td colspan="5" class="kosong">Belum ada siswa. Tambahkan anak pertama di bawah.</td></tr>'

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
        f'<div class="kartu">'
        f'<div class="kartu-judul"><span class="ikon-kartu">🔑</span>'
        f"<h2>Ganti sandi</h2></div>"
        f'<p class="sub">Pengguna saat ini: <b>{pengguna_tampil}</b>. Setelah diganti, '
        f"masuk lagi dengan sandi baru.</p>"
        f'<form method="post" action="/akun">'
        f'<input type="hidden" name="aksi" value="sandi">'
        f'<label for="sandi-lama">Sandi lama</label>'
        f'<input id="sandi-lama" type="password" name="lama" autocomplete="current-password" required>'
        f'<label for="sandi-baru">Sandi baru (minimal 12 karakter)</label>'
        f'<input id="sandi-baru" type="password" name="baru" autocomplete="new-password" required>'
        f'<label for="sandi-ulang">Ulangi sandi baru</label>'
        f'<input id="sandi-ulang" type="password" name="ulang" autocomplete="new-password" required>'
        f'<p style="margin-top:.8rem">'
        f'<button type="submit" class="tombol-sekunder">Ganti sandi</button></p>'
        f"</form></div>"
    )
    kartu_siswa = (
        f'<div class="kartu">'
        f'<div class="kartu-judul"><span class="ikon-kartu">📚</span>'
        f"<h2>Siswa</h2></div>"
        f'<p class="sub" id="keterangan-kelas">{learning_profile_ui.KETERANGAN_KELAS} '
        'Pengaturan soal dipilih terpisah saat membuat latihan.</p>'
        f'<div class="tabel-wrap"><table><tr><th>Nama</th><th>Kelas sekolah</th>'
        f"<th>Sesi</th><th>Akun latihan</th><th>Aksi</th></tr>{daftar}</table></div>"
        f'<p class="sub" style="margin-top:.7rem">Anak baru ditambahkan dari '
        f'kartu "Tambah anak" di bawah — sekalian dengan akun latihannya.'
        f"</p></div>"
    )
    kartu_anak = (
        f'<div class="kartu">'
        f'<div class="kartu-judul"><span class="ikon-kartu">🧒</span>'
        f"<h2>Tambah anak</h2></div>"
        f'<p class="sub">Satu langkah untuk pengguna baru: buat siswa '
        f"sekaligus akun yang dipakai anak untuk masuk ke /murid dari HP. "
        f"Pakai nama panggilan atau inisial, bukan nama lengkap — "
        f"mengurangi dampak bila basis data ini bocor.</p>"
        f'<form method="post" action="/akun">'
        f'<input type="hidden" name="aksi" value="anak_baru">'
        f'<div class="baris">'
        f'<div><label for="anak-nama">Nama anak (nama panggilan)</label>'
        f'<input id="anak-nama" type="text" name="nama" placeholder="mis. Aisha" required></div>'
        f'<div><label for="anak-kelas">Kelas sekolah (opsional)</label>'
        f'<select id="anak-kelas" name="kelas_sekolah" aria-describedby="keterangan-kelas">'
        + learning_profile_ui.opsi_kelas()
        + '</select></div></div>'
        '<fieldset class="pengaturan-awal"><legend>Pengaturan latihan awal</legend>'
        '<p>Pilih variasi untuk memulai latihan dan rencana belajar, bukan untuk menilai kemampuan anak. '
        'Saat membuat latihan bebas, Anda tetap dapat memilih variasi lain.</p>'
        + question_variants_ui.kontrol_variasi('anak')
        + question_variants_ui.panduan_variasi()
        + '</fieldset>'
        f'<label for="anak-login">Nama login anak (opsional — bawaan sama dengan nama anak)'
        f"</label>"
        f'<input id="anak-login" type="text" name="nama_akun" '
        f'placeholder="mis. aisha2 — isi bila nama anak dipakai keluarga lain">'
        f'<label for="anak-sandi">Kata sandi anak (minimal 8 karakter, boleh sama polanya dengan sandimu)</label>'
        f'<input id="anak-sandi" type="password" name="sandi_anak" autocomplete="new-password" '
        f'required minlength="8">'
        f'<p style="font-size:.9rem">'
        f'<label style="display:flex;gap:.5rem;align-items:flex-start">'
        f'<input type="checkbox" name="persetujuan_ortu" value="1" style="margin-top:.25rem">'
        f"<span>Saya orang tua/wali anak ini dan menyetujui "
        f'<a href="/kebijakan-privasi">Kebijakan Privasi</a> untuk data anak.</span>'
        f"</label></p>"
        f'<button type="submit" class="tombol-coral">Buat anak &amp; akunnya</button>'
        f"</form></div>"
    )
    kartu_catatan = (
        f'<div class="kartu">'
        f'<div class="kartu-judul"><span class="ikon-kartu amber">💡</span>'
        f"<h2>Catatan</h2></div>"
        f'<p class="sub">Siswa yang masih punya riwayat sesi sengaja tidak '
        f"bisa dihapus: menghapusnya ikut memusnahkan seluruh sesi, "
        f"jawaban, dan diagnosisnya — riwayat yang tidak bisa dibangun "
        f"ulang. Kalau seorang anak berhenti, biarkan saja datanya; ia "
        f"tidak mengganggu apa pun.</p>"
        f'<p class="sub">Siswa tanpa riwayat (salah ketik atau data uji) '
        f"boleh dihapus — akun latihannya ikut dihapus sekalian.</p>"
        f'<p class="sub">Cadangan basis data ditarik otomatis ke Mac tiap '
        f"malam pukul 22:00.</p></div>"
    )

    if section == "siswa" and peran != "admin":
        isi_section = kartu_siswa + kartu_anak + kartu_catatan
    elif section == "akun-murid" and peran != "admin":
        isi_section = _kartu_akun_murid(kon, pengguna, peran)
    elif section == "arsip-pendamping":
        isi_section = arsip_pendamping or kartu_sandi
        if not arsip_pendamping:
            section = "akun"
    else:
        isi_section = kartu_sandi
        if arsip_pendamping:
            isi_section += (
                '<div class="kartu"><details><summary>Arsip percakapan lama</summary>'
                '<p class="sub">Percakapan umum lama tersedia hanya-baca.</p>'
                '<a href="/akun?section=arsip-pendamping">Buka arsip</a>'
                '</details></div>'
            )

    item = [("akun", "Akun saya")]
    if peran != "admin":
        item.extend((("siswa", "Siswa"), ("akun-murid", "Akun latihan")))
    if arsip_pendamping:
        item.append(("arsip-pendamping", "Arsip percakapan lama"))
    nav = "".join(
        f'<a href="/akun?section={sid}"'
        + (' class="aktif" aria-current="page"' if sid == section else "")
        + f">{label}</a>"
        for sid, label in item
    )

    return _halaman(
        "Akun",
        f'<div class="jejak"><a href="{"/admin" if peran == "admin" else "/guru"}">&larr; Semua siswa</a></div>'
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">RUANG PENDAMPING</p>'
        '<h1 id="judul-akun">Akun &amp; pengaturan</h1>'
        '<p class="sub">Kelola akses dan ruang belajar keluarga.</p></header>'
        f"{kabar}"
        f'<div class="layout-samping">'
        f'<nav class="nav-samping" aria-label="Pengaturan akun">{nav}</nav>'
        f"<div>{isi_section}</div>"
        f"</div>",
        ident=(pengguna or "guru", peran),
        stitch=True, kelas_bungkus="pendamping-editorial-st akun-editorial-st",
        id_utama="judul-akun", privat=privat,
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
        # Payload programatis lama yang eksplisit tetap profil, bukan kelas.
        # Tidak ada default tersembunyi ketika pilihan hilang/kosong.
        tingkat = data.get('profil_parameter', data.get('tingkat', '')).strip()
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
            return '', 'Form profil lama atau tidak cocok. Muat ulang sebelum menambahkan anak.'
        if not level_valid(tingkat):
            return '', 'Pilih variasi soal untuk latihan awal. Bandingkan isi dan contoh soal bila belum yakin.'
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
        catatan = " (persetujuan orang tua dicatat)" if data.get("persetujuan_ortu") else ""
        return (
            f"Anak {nama} ditambahkan ({learning_profile.label_kelas_sekolah(kelas)}; "
            f"{label_profil_parameter(tingkat)}) beserta akun latihannya{catatan}. "
            f"Langkah 3: kembali ke beranda, klik nama {nama}, lalu tekan "
            f"“Buat sesi baru”. Anak masuk lewat /murid dengan nama {nama_akun}.",
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
