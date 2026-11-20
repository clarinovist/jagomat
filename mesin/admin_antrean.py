"""Kumpulan antrean "Perlu ditangani" per item; read-only, tanpa migrasi atau tulis."""
from __future__ import annotations

from typing import Optional, Tuple

import admin_labels as L
import admin_operations
import admin_queries as Q
import admin_store
import admin_transfer_menunggu
import admin_verifikasi_pages
from admin_antrean_pages import AntreanAdmin, BATAS_BARIS, ItemAntrean
from pesanan_transfer_pages import rupiah

JALUR_PERHATIAN = "/admin?section=perhatian"
JALUR_KELUARGA = "/admin?section=keluarga&status=perlu_perhatian"
STATUS_LOGIN_ANTREAN = ("legacy_same_name_ambiguous", "orphan_login", "legacy_orphan_login")
PERINGATAN_LUNAS = "Periksa hasil operasinya; jangan mengulang atau memaksa status lunas."
CATATAN_BACKUP = "Bukti ini tidak menyatakan jadwal atau salinan di luar server."
JALUR_KESIAPAN = "/admin/sakelar#kesiapan"  # Pengaturan layanan, bagian Kesiapan layanan
JALUR_SISWA_TANPA_LOGIN = "/admin?section=siswa&status=student_without_login"
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


def _item_transfer_satu(transfer, sekarang: float) -> ItemAntrean:
    waktu_unggah = transfer.diunggah + "Z" if transfer.diunggah else None  # ledger UTC naif; L.waktu menganggap WIB
    nominal = rupiah(transfer.nominal) if transfer.nominal else "nominal belum tercatat"
    unggah = ("bukti diunggah %s" % L.tanggal(waktu_unggah) if L.waktu(waktu_unggah)
              else "waktu unggah bukti tidak tercatat")
    return ItemAntrean(
        "mendesak", "Transfer menunggu verifikasi",
        "%s · %s. Cocokkan dengan mutasi rekening sebelum menyetujui." % (nominal, unggah),
        "%s?order=%s" % (admin_verifikasi_pages.RUTE_VERIFIKASI, transfer.order_id),
        "Periksa bukti", "Order", _ringkas_ref(transfer.order_id), _umur_hari(waktu_unggah, sekarang),
    )


def _item_transfer(path_admin, sekarang: float) -> Tuple[ItemAntrean, ...]:
    """Satu item mendesak per transfer menunggu, terlama dulu. Transfer belum terpasang/galat baca = ()."""
    try:
        menunggu = admin_transfer_menunggu.baca(path_admin, admin_transfer_menunggu.waktu_iso(sekarang))
    except admin_transfer_menunggu.GALAT_BACA:
        return ()
    return tuple(_item_transfer_satu(t, sekarang) for t in menunggu)


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
    """Antrean terurut transfer → operasi → backup → pengguna, dipotong ``BATAS_BARIS`` baris."""
    transfer = _item_transfer(path_admin, sekarang)
    operasi, total_operasi, tersedia = _item_operasi_semua(path_admin, sekarang)
    if not tersedia:
        operasi = _fallback_operasi(path_admin)
        total_operasi = len(operasi)
    backup, bukti, terverifikasi = _item_backup(sekarang)
    lain = item_pengguna(konteks)
    semua = transfer + operasi + backup + lain
    mendesak = total_operasi + len(transfer)
    penting = len(backup) + sum(1 for i in lain if i.tingkat == "penting")
    return AntreanAdmin(
        item=semua[:BATAS_BARIS],
        total=len(transfer) + total_operasi + len(backup) + len(lain),
        mendesak=mendesak,
        layanan_tersedia=tersedia,
        bukti_backup=bukti,
        backup_terverifikasi=terverifikasi,
        transfer_menunggu=len(transfer),
        perlu_keputusan=mendesak + penting,
    )
