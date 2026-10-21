"""Proyeksi pola baca gambar v2 tanpa mengubah identitas soal warisan."""
from number_patterns_visual_data import bidang, bulat
from visual_contract import DescriptorVisual


def proyeksi_pola(template_id, parameter):
    """Ambil hanya data gambar contoh; target berada pada kalimat pertanyaan."""
    if not isinstance(template_id, str):
        raise ValueError("template pola wajib teks")
    if template_id == "korek_api":
        from catalog_versions import parameter_visual
        parameter = parameter_visual(template_id, parameter, {"korek_api"})
        bidang(parameter, ("awal", "tambah", "gambar_ke"))
        bulat(parameter["gambar_ke"], "gambar_ke", 4, 100)
        data = {"n_tampil": 3, "awal": parameter["awal"], "tambah": parameter["tambah"]}
        teks = (
            "Pola batang korek api bertumbuh seperti pada gambar. "
            "Batang lama tetap ada; banyak batang baru pada setiap langkah tetap. "
            "Satu ruas di antara dua titik sambungan adalah satu batang.\n"
            f"Gambar ke-{parameter['gambar_ke']} butuh berapa batang?"
        )
        return teks, DescriptorVisual("korek", 2, data)
    if template_id == "titik_segitiga":
        bidang(parameter, ("gambar_ke",))
        bulat(parameter["gambar_ke"], "gambar_ke", 5, 25)
        teks = (
            "Titik disusun menjadi segitiga seperti pada gambar.\n"
            f"Gambar ke-{parameter['gambar_ke']} punya berapa titik?"
        )
        return teks, DescriptorVisual("titik", 2, {"n_tampil": 4})
    return None
