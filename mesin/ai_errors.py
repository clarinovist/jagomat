"""Kategori kegagalan AI tertutup; bukan tempat menyimpan isi exception/provider."""

KATEGORI = frozenset({
    "network_atau_provider", "provider_timeout", "provider_koneksi",
    "provider_otorisasi", "provider_batas", "provider_gagal", "provider_redirect",
    "respons_terlalu_besar", "respons_terpotong", "respons_json",
    "respons_bentuk", "respons_jawaban", "respons_memori", "respons_usulan",
    "respons_klarifikasi", "ai_nonaktif", "ai_konfigurasi", "ai_storage",
    "ai_kuota", "ai_tertahan", "ai_pengaturan_berubah",
})


def kategori_aman(galat: Exception) -> str:
    """Jangan meneruskan pesan, atribut bebas, nama kelas, atau repr ke audit."""
    kategori = getattr(galat, "kategori", None)
    if type(kategori) is str and kategori in KATEGORI:
        return kategori
    return "network_atau_provider"


def pesan_pendamping(kategori: str) -> str:
    """Tindakan pemulihan untuk pengguna tanpa membocorkan konfigurasi internal."""
    awal = "Pendamping belum bisa menjawab. "
    if kategori == "ai_kuota":
        return awal + "Batas pemakaian AI tercapai. Minta pengelola memeriksa batas pemakaian."
    if kategori in {"ai_nonaktif", "ai_konfigurasi", "provider_otorisasi", "ai_storage", "ai_tertahan"}:
        return awal + "Layanan AI belum tersedia. Minta pengelola memeriksa pengaturan layanan."
    if kategori == "provider_timeout":
        return awal + "Layanan AI terlalu lama merespons. Coba lagi nanti."
    if kategori == "provider_batas":
        return awal + "Layanan AI sedang membatasi permintaan. Tunggu sebentar sebelum mencoba lagi."
    if kategori == "respons_terpotong":
        return awal + "Balasan AI terpotong sebelum selesai, jadi tidak ditampilkan. Kamu boleh mencoba lagi; pesan tidak dikirim ulang otomatis."
    if kategori.startswith("respons_") and kategori in KATEGORI:
        return awal + "Format balasan AI belum sesuai, jadi balasan tidak ditampilkan. Kamu boleh mencoba lagi."
    if kategori == "ai_pengaturan_berubah":
        return awal + "Pengaturan layanan berubah saat menunggu. Coba lagi setelah pengaturan selesai."
    return awal + "Coba lagi nanti."
