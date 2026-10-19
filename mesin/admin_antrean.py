"""Kumpulan antrean "Perlu ditangani" per item; read-only, tanpa migrasi atau tulis."""
from __future__ import annotations

from typing import Optional, Tuple

import admin_labels as L
import admin_operations
import admin_queries as Q
import admin_store
from admin_antrean_pages import AntreanAdmin, BATAS_BARIS, ItemAntrean

JALUR_PERHATIAN = "/admin?section=perhatian"
JALUR_KELUARGA = "/admin?section=keluarga&status=perlu_perhatian"
STATUS_LOGIN_ANTREAN = ("legacy_same_name_ambiguous", "orphan_login", "legacy_orphan_login")
PERINGATAN_LUNAS = "Periksa hasil operasinya; jangan mengulang atau memaksa status lunas."
CATATAN_BACKUP = "Bukti ini tidak menyatakan jadwal atau salinan di luar server."


def _umur_hari(waktu, sekarang: float) -> Optional[int]:
    dt = L.waktu(waktu)
    return None if dt is None else max(0, int((sekarang - dt.timestamp()) // 86400))


def _sejak(waktu) -> str:
    dt = L.waktu(waktu)
    return "" if dt is None else " sejak %d %s %d" % (dt.day, L.BULAN[dt.month - 1], dt.year)


def _ringkas_ref(ref) -> str:
    teks = str(ref)
    return teks if len(teks) <= 16 else "%s…%s" % (teks[:8], teks[-6:])


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
            "/admin?section=operasional", "Buka operasional",
        )
    else:
        item = ItemAntrean(
            "penting", "Backup belum terverifikasi",
            "Belum ada cutoff backup yang tercatat. " + CATATAN_BACKUP,
            "/admin?section=operasional", "Buka operasional",
        )
    return (item,), label, False


def item_pengguna(konteks: Q.KonteksAdmin) -> Tuple[ItemAntrean, ...]:
    """Satu baris per keluarga/siswa/login bermasalah dari snapshot; tanpa I/O."""
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
    siswa_tanpa_login = [
        ItemAntrean(
            "tinjau", "%s belum punya login" % siswa.nama,
            "%s. Periksa kaitan siswa dan keluarga sebelum membuat akses."
            % ("Keluarga %s" % siswa.pemilik if siswa.pemilik else "Siswa belum punya pemilik"),
            "/admin?section=siswa&id=%d" % siswa.id, "Tinjau siswa",
        )
        for siswa, status in pasangan if "student_without_login" in status
    ]
    login = [
        ItemAntrean(
            "tinjau", "Login %s perlu ditinjau" % masalah.pengguna,
            "%s · %d kandidat nama. Daftar ini tidak memperbaiki atau mengaitkan akun otomatis."
            % (L.label_status(masalah.status), masalah.jumlah_kandidat),
            "#login-perlu-perhatian", "Lihat rincian login",
        )
        for masalah in konteks.login_bermasalah if masalah.status in STATUS_LOGIN_ANTREAN
    ]
    return tuple(keluarga + siswa_tanpa_login + login)


def kumpulkan(konteks: Q.KonteksAdmin, path_admin, *, sekarang: float) -> AntreanAdmin:
    """Antrean terurut mendesak → penting → tinjau, dipotong ``BATAS_BARIS`` baris."""
    operasi, total_operasi, tersedia = _item_operasi_semua(path_admin, sekarang)
    if not tersedia:
        operasi = _fallback_operasi(path_admin)
        total_operasi = len(operasi)
    backup, bukti, terverifikasi = _item_backup(sekarang)
    lain = item_pengguna(konteks)
    semua = operasi + backup + lain
    return AntreanAdmin(
        item=semua[:BATAS_BARIS],
        total=total_operasi + len(backup) + len(lain),
        mendesak=total_operasi,
        layanan_tersedia=tersedia,
        bukti_backup=bukti,
        backup_terverifikasi=terverifikasi,
    )
