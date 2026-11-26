"""Kumpulan antrean "Perlu ditangani" per item; read-only, tanpa migrasi atau tulis."""
from __future__ import annotations

from typing import Optional, Tuple

import admin_labels as L
import admin_operations
import admin_queries as Q
import admin_store
import admin_antrean_bayar
import admin_antrean_guru
import admin_antrean_jurnal
import admin_antrean_private
import admin_transfer_menunggu
import admin_verifikasi_pages
import harian_langganan_admin_pages
import kelas_admin_pages
import kelas_tunggakan as kt
from admin_antrean_pages import AntreanAdmin, BATAS_BARIS, ItemAntrean
from pesanan_transfer_pages import rupiah

JALUR_PERHATIAN = "/admin?section=perhatian"
JALUR_KELUARGA = "/admin?section=keluarga&status=perlu_perhatian"
STATUS_LOGIN_ANTREAN = ("legacy_same_name_ambiguous", "orphan_login", "legacy_orphan_login")
PERINGATAN_LUNAS = "Periksa hasil operasinya; jangan mengulang atau memaksa status lunas."
CATATAN_BACKUP = "Bukti ini tidak menyatakan jadwal atau salinan di luar server."
JALUR_KESIAPAN = "/admin/sakelar#kesiapan"  # Pengaturan layanan, bagian Kesiapan layanan
JALUR_SISWA_TANPA_LOGIN = "/admin?section=siswa&status=student_without_login"
KALIMAT_TINDAK_LANJUT_TUNGGAKAN = "Hubungi orang tua: ajak ikut kelas lagi atau tanyakan umpan balik."
JALUR_BELUM_BAYAR = "/admin/pembayaran?status=belum_bayar"
JALUR_PETA_BELUM_TERBIT = "/admin/pembayaran?status=dibayar"
KALIMAT_PETA_BELUM_TERBIT = "Laporan belum terbit otomatis; periksa bahan cek atau terbitkan manual."
JALUR_GURU_BARU = "/admin?section=guru&status=belum_lembaga"
KALIMAT_GURU_BARU = ("Guru ini mendaftar sendiri dan belum dimasukkan ke lembaga mana pun. Buka Akun guru, lalu pakai Tambah ke "
                     "lembaga bila perlu; boleh dibiarkan bila memang tidak bergabung.")
JALUR_BELUM_DITEMPATKAN = kelas_admin_pages.RUTE
KALIMAT_BELUM_DITEMPATKAN = ("Sudah bayar dan disetujui, tetapi jadwal belum ada. Buka Paket belajar, tempatkan anak ke kelompok atau "
                            "jadwalkan Private, atau hubungi orang tua bila jadwalnya perlu dicocokkan.")
KALIMAT_BELUM_BAYAR = ("Peta Kemampuan, Latihan Harian, atau Paket Belajar yang sudah dipesan tetapi belum ada bukti "
                       "transfer (jendela 24 jam belum lewat). Belum perlu diperiksa; hubungi orang tua bila lama menggantung.")
PERINGKAT_TINGKAT = {"mendesak": 0, "penting": 1, "tinjau": 2}
CATATAN_TANPA_LOGIN = ("Normal: anak masuk lewat QR atau tautan HP dari guru. "
                       "Buka daftar hanya bila perlu membuat login.")


def _umur_hari(waktu, sekarang: float) -> Optional[int]:
    dt = L.waktu(waktu)
    return None if dt is None else max(0, int((sekarang - dt.timestamp()) // 86400))


def _sejak(waktu) -> str:
    dt = L.waktu(waktu)
    return "" if dt is None else " sejak %d %s %d" % (dt.day, L.BULAN[dt.month - 1], dt.year)


def _ringkas_ref(ref) -> str:
    teks = str(ref)
    return teks if len(teks) <= 16 else "%s…%s" % (teks[:8], teks[-6:])


def _item_transfer_satu(transfer, sekarang: float, judul: str = "Transfer menunggu verifikasi",
                       rute: str = admin_verifikasi_pages.RUTE_VERIFIKASI) -> ItemAntrean:
    waktu_unggah = transfer.diunggah + "Z" if transfer.diunggah else None  # ledger UTC naif; L.waktu menganggap WIB
    nominal = rupiah(transfer.nominal) if transfer.nominal else "nominal belum tercatat"
    unggah = ("bukti diunggah %s" % L.tanggal(waktu_unggah) if L.waktu(waktu_unggah)
              else "waktu unggah bukti tidak tercatat")
    return ItemAntrean(
        "mendesak", judul,
        "%s · %s. Cocokkan dengan mutasi rekening sebelum menyetujui." % (nominal, unggah),
        "%s?order=%s" % (rute, transfer.order_id),
        "Periksa bukti", "Order", _ringkas_ref(transfer.order_id), _umur_hari(waktu_unggah, sekarang),
    )


def _item_transfer(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu item mendesak per transfer menunggu, terlama dulu. Transfer belum terpasang/galat baca = ()."""
    try:
        menunggu = admin_transfer_menunggu.baca(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    except admin_transfer_menunggu.GALAT_BACA:
        return ()
    return tuple(_item_transfer_satu(t, sekarang) for t in menunggu)


def _item_bayar_lain(path_admin, sekarang: float):
    """(item Latihan Harian, item Paket Belajar): bukti menunggu di jalur selain Peta, terlama dulu."""
    harian = admin_antrean_bayar.harian_menunggu(admin_transfer_menunggu.waktu_iso(sekarang))
    kelas = admin_antrean_bayar.kelas_menunggu(path_admin)
    return (
        tuple(_item_transfer_satu(t, sekarang, admin_antrean_bayar.JUDUL_HARIAN,
                                  harian_langganan_admin_pages.RUTE_VERIFIKASI) for t in harian),
        tuple(_item_transfer_satu(t, sekarang, admin_antrean_bayar.JUDUL_KELAS,
                                  kelas_admin_pages.RUTE_VERIFIKASI) for t in kelas),
    )


def _item_tunggakan_satu(tunggakan: kt.Tunggakan) -> ItemAntrean:
    """Paket kelas habis dan belum diperpanjang; 60 hari ke atas naik jadi penting. Tanpa nama atau kontak."""
    penting = tunggakan.hari_lewat >= kt.HARI_TUNGGAKAN_PENTING
    return ItemAntrean(
        "penting" if penting else "tinjau",
        "Paket %s anak #%d belum diperpanjang" % (tunggakan.nama_paket, tunggakan.siswa_id),
        "berakhir %d hari lalu. %s" % (tunggakan.hari_lewat, KALIMAT_TINDAK_LANJUT_TUNGGAKAN),
        kelas_admin_pages.RUTE, "Tinjau paket", umur_hari=tunggakan.hari_lewat,
    )


def _item_tunggakan(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    daftar = admin_antrean_bayar.kelas_tunggakan(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    return tuple(_item_tunggakan_satu(t) for t in daftar)


def _item_belum_bayar(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu butir tinjau bila ada pesanan menggantung; terpisah dari hitungan transfer menunggu verifikasi."""
    jumlah = admin_antrean_bayar.belum_bayar(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    if not jumlah:
        return ()
    return (ItemAntrean("tinjau", "%d pembayaran belum dibayar" % jumlah, KALIMAT_BELUM_BAYAR,
                        JALUR_BELUM_BAYAR, "Lihat daftar"),)


def _item_belum_ditempatkan(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu butir penting bila ada paket aktif tanpa jadwal: pembeli sudah membayar dan menunggu tindak lanjut."""
    jumlah = admin_antrean_bayar.belum_ditempatkan(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    if not jumlah:
        return ()
    return (ItemAntrean("penting", "%d paket aktif belum ditempatkan" % jumlah, KALIMAT_BELUM_DITEMPATKAN,
                        JALUR_BELUM_DITEMPATKAN, "Buka paket belajar"),)


KALIMAT_PRIVATE = "Orang tua memilih slot Private; setujui yang masih hidup, tolak yang basi."
JALUR_PRIVATE = "/admin/kelas/private"


def _item_pengajuan_private(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu butir tinjau bila ada pengajuan jadwal Private yang masih hidup; tanpa nama anak atau guru."""
    jumlah = admin_antrean_private.jumlah(path_admin, sekarang)
    if not jumlah:
        return ()
    return (ItemAntrean("tinjau", "%d pengajuan jadwal Private menunggu" % jumlah, KALIMAT_PRIVATE,
                        JALUR_PRIVATE, "Lihat jadwal"),)


JALUR_JURNAL = "/admin/jadwal/jurnal"
KALIMAT_JURNAL = ("Guru belum mencatat kehadiran dan jurnal untuk pertemuan yang sudah lewat. "
                  "Guru masih bisa mengisinya sampai 7 hari setelah pertemuan.")


def _item_jurnal(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu butir tinjau bila ada pertemuan lewat tanpa jurnal (aturan R6); tanpa nama anak, guru, atau order."""
    jumlah = admin_antrean_jurnal.jumlah(path_admin, sekarang)
    if not jumlah:
        return ()
    return (ItemAntrean("tinjau", "%d pertemuan lewat tanpa jurnal" % jumlah, KALIMAT_JURNAL,
                        JALUR_JURNAL, "Lihat daftar"),)


def _item_peta_belum_terbit(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu butir penting bila ada Peta dibayar yang laporannya belum terbit otomatis; tanpa masa tunggu."""
    menanti, _terlambat = admin_antrean_bayar.peta_belum_terbit(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    if not menanti:
        return ()
    return (ItemAntrean("penting", "%d Peta dibayar, laporan belum terbit" % menanti, KALIMAT_PETA_BELUM_TERBIT,
                        JALUR_PETA_BELUM_TERBIT, "Lihat pembayaran"),)


def _item_guru_baru() -> Tuple[ItemAntrean, ...]:
    """Satu butir tinjau bila ada guru yang mendaftar sendiri dan belum dimasukkan ke lembaga (tanpa nama akun)."""
    jumlah = admin_antrean_guru.jumlah()
    if not jumlah:
        return ()
    return (ItemAntrean("tinjau", "%d guru baru belum masuk lembaga" % jumlah, KALIMAT_GURU_BARU,
                        JALUR_GURU_BARU, "Buka akun guru"),)


def _urutkan_tingkat(item: Tuple[ItemAntrean, ...]) -> Tuple[ItemAntrean, ...]:
    """Mendesak, lalu penting, lalu tinjau; dalam satu tingkat urutan asal dipertahankan (sort stabil)."""
    return tuple(sorted(item, key=lambda i: PERINGKAT_TINGKAT.get(i.tingkat, PERINGKAT_TINGKAT["tinjau"])))


def _item_operasi(baris, sekarang: float) -> ItemAntrean:
    umur = _umur_hari(baris["waktu"], sekarang)
    ref = _ringkas_ref(baris["ref"])
    sumber = baris["sumber"]
    if sumber == "pembayaran":
        return ItemAntrean(
            "mendesak", "Pembayaran perlu diperiksa",
            "menunggu pemeriksaan%s. %s" % (_sejak(baris["waktu"]), PERINGATAN_LUNAS),
            JALUR_PERHATIAN, "Periksa invoice", "Invoice", ref, umur,
        )
    status = L.label_status(baris["status"]).lower()
    if sumber == "layanan":
        return ItemAntrean(
            "mendesak", "Operasi layanan perlu diperiksa",
            "berstatus %s%s. %s" % (status, _sejak(baris["waktu"]), PERINGATAN_LUNAS),
            JALUR_PERHATIAN, "Tinjau operasi", "Operasi", ref, umur,
        )
    return ItemAntrean(
        "mendesak", "Tindakan admin %s" % status,
        "belum selesai dipastikan%s. Periksa hasilnya sebelum mengulang tindakan." % _sejak(baris["waktu"]),
        JALUR_PERHATIAN, "Tinjau operasi", "Tindakan", ref, umur,
    )


def _item_operasi_semua(path_admin, sekarang: float):
    """(item, total, tersedia). Sumber hilang dibedakan dari antrean kosong."""
    try:
        baris, total = admin_operations.antrean(path_admin)
    except admin_store.StoreBelumSiap:
        return (), 0, False
    return tuple(_item_operasi(b, sekarang) for b in baris), total, True


def _fallback_operasi(path_admin) -> Tuple[ItemAntrean, ...]:
    try:
        belum_pasti = admin_store.daftar_riwayat(path_admin, status="uncertain", per_halaman=1).total
        tertunda = admin_store.daftar_riwayat(path_admin, status="reserved", per_halaman=1).total
    except admin_store.StoreBelumSiap:
        return ()
    if not (belum_pasti or tertunda):
        return ()
    return (ItemAntrean(
        "mendesak", "Operasi perlu diperiksa",
        "%d belum pasti · %d menunggu hasil (tindakan admin). %s" % (belum_pasti, tertunda, PERINGATAN_LUNAS),
        "/admin?section=riwayat", "Tinjau operasi",
    ),)


def _item_backup(sekarang: float):
    label, cutoff = admin_operations.bukti_backup(sekarang)
    if cutoff is not None:
        return (), label, True
    if label == "Bukti backup tidak valid":
        item = ItemAntrean(
            "penting", "Bukti backup tidak valid",
            "Bundle backup tidak lolos validasi. " + CATATAN_BACKUP,
            JALUR_KESIAPAN, "Periksa backup",
        )
    else:
        item = ItemAntrean(
            "penting", "Backup belum terverifikasi",
            "Belum ada cutoff backup yang tercatat. " + CATATAN_BACKUP,
            JALUR_KESIAPAN, "Periksa backup",
        )
    return (item,), label, False


def item_pengguna(konteks: Q.KonteksAdmin) -> Tuple[ItemAntrean, ...]:
    """Satu baris per keluarga/login bermasalah; siswa tanpa login diringkas jadi satu baris. Tanpa I/O."""
    pasangan = sorted(Q.status_per_siswa(konteks), key=lambda p: (p[0].nama.casefold(), p[0].id))
    pemilik_tanpa_akun = {}
    jumlah_tanpa_pemilik = 0
    for siswa, status in pasangan:
        if "owner_without_account" in status:
            pemilik_tanpa_akun[siswa.pemilik] = pemilik_tanpa_akun.get(siswa.pemilik, 0) + 1
        if "owner_empty" in status:
            jumlah_tanpa_pemilik += 1
    keluarga = [
        ItemAntrean(
            "penting", "Keluarga %s belum punya akun pemilik" % pemilik,
            "%d siswa terkait. Konfirmasi kaitan keluarga sebelum akun digunakan." % jumlah,
            JALUR_KELUARGA, "Tinjau keluarga",
        )
        for pemilik, jumlah in sorted(pemilik_tanpa_akun.items(), key=lambda p: (p[0].casefold(), p[0]))
    ]
    if jumlah_tanpa_pemilik:
        keluarga.append(ItemAntrean(
            "penting", "%d siswa belum punya pemilik" % jumlah_tanpa_pemilik,
            "Konfirmasi kaitan keluarga sebelum akun digunakan.", JALUR_KELUARGA, "Tinjau keluarga",
        ))
    jumlah_tanpa_login = sum(1 for _siswa, status in pasangan if "student_without_login" in status)
    ringkasan_tanpa_login = [] if not jumlah_tanpa_login else [ItemAntrean(
        "tinjau", "%d siswa belum punya login" % jumlah_tanpa_login, CATATAN_TANPA_LOGIN,
        JALUR_SISWA_TANPA_LOGIN, "Lihat daftar",
    )]
    login = [
        ItemAntrean(
            "tinjau", "Login %s perlu ditinjau" % masalah.pengguna,
            "%s · %d kandidat nama. Daftar ini tidak memperbaiki atau mengaitkan akun otomatis."
            % (L.label_status(masalah.status), masalah.jumlah_kandidat),
            "#login-perlu-perhatian", "Lihat rincian login",
        )
        for masalah in konteks.login_bermasalah if masalah.status in STATUS_LOGIN_ANTREAN
    ]
    return tuple(keluarga + ringkasan_tanpa_login + login)


def kumpulkan(konteks: Q.KonteksAdmin, path_admin, *, sekarang: float) -> AntreanAdmin:
    """Antrean diurutkan per tingkat (mendesak, penting, tinjau); di dalam tingkat: transfer, operasi, backup, tunggakan paket, pengguna. Dipotong ``BATAS_BARIS``."""
    transfer = _item_transfer(path_admin, sekarang)
    harian, kelas = _item_bayar_lain(path_admin, sekarang)
    operasi, total_operasi, tersedia = _item_operasi_semua(path_admin, sekarang)
    if not tersedia:
        operasi = _fallback_operasi(path_admin)
        total_operasi = len(operasi)
    backup, bukti, terverifikasi = _item_backup(sekarang)
    tunggakan = _item_tunggakan(path_admin, sekarang)
    belum_bayar = _item_belum_bayar(path_admin, sekarang)
    belum_tempat = _item_belum_ditempatkan(path_admin, sekarang)
    privat = _item_pengajuan_private(path_admin, sekarang)
    guru_baru = _item_guru_baru()
    peta_belum = _item_peta_belum_terbit(path_admin, sekarang)
    lain = item_pengguna(konteks)
    jurnal = _item_jurnal(path_admin, sekarang)
    semua = _urutkan_tingkat(transfer + harian + kelas + operasi + backup + tunggakan + belum_bayar + belum_tempat + peta_belum + guru_baru + privat + lain + jurnal)
    menunggu_semua = len(transfer) + len(harian) + len(kelas)
    mendesak = total_operasi + menunggu_semua
    penting = sum(1 for i in backup + tunggakan + belum_tempat + peta_belum + lain if i.tingkat == "penting")
    return AntreanAdmin(
        item=semua[:BATAS_BARIS],
        total=menunggu_semua + total_operasi + len(backup) + len(tunggakan) + len(belum_bayar) + len(belum_tempat) + len(peta_belum) + len(guru_baru) + len(privat) + len(lain) + len(jurnal),
        mendesak=mendesak,
        layanan_tersedia=tersedia,
        bukti_backup=bukti,
        backup_terverifikasi=terverifikasi,
        transfer_menunggu=len(transfer),
        harian_menunggu=len(harian),
        kelas_menunggu=len(kelas),
        perlu_keputusan=mendesak + penting,
    )
