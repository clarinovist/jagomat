"""Renderer aman untuk snapshot pertanyaan yang sudah tervalidasi."""

from __future__ import annotations

import html
import pecahan
from statistics_svg import render_statistika
from topic_number_patterns_svg import _svg_korek, _svg_titik
from visual_contract import (
    DescriptorVisual,
    PenyajianPertanyaan,
    serialisasi_penyajian,
)

_GAYA_DIDUKUNG = frozenset({"cetak", "murid", "stitch", "guru"})


def _validasi_untuk_render(
    penyajian: PenyajianPertanyaan,
) -> PenyajianPertanyaan:
    """Validasi ulang objek, termasuk descriptor dan fingerprint-nya."""
    if not isinstance(penyajian, PenyajianPertanyaan):
        raise ValueError("objek bukan PenyajianPertanyaan")
    serialisasi_penyajian(penyajian)
    if penyajian.status_visual == "tidak_valid":
        raise ValueError("status visual tidak valid dan tidak boleh dirender")
    return penyajian


def _baris(teks: str) -> list[str]:
    return [baris.strip() for baris in teks.split("\n") if baris.strip()]


def _render_baris(teks: str, kelas_teks: str, kelas_tanya: str,
                  pecahan_aktif: bool = True) -> str:
    """Cetak wajib identik dengan baseline recovery; pecahan hanya di layar."""
    ubah = pecahan.render if pecahan_aktif else html.escape
    baris = _baris(teks)
    if len(baris) == 1:
        return f'<div class="{kelas_teks}">{ubah(baris[0])}</div>'
    return "".join(
        f'<div class="{kelas_tanya if indeks == len(baris) - 1 else kelas_teks}">'
        f"{ubah(isi)}</div>"
        for indeks, isi in enumerate(baris)
    )


def _render_teks_guru(teks: str) -> str:
    return f'<div class="teks-soal">{pecahan.render(teks)}</div>'


def _render_teks_per_gaya(teks: str, gaya: str) -> str:
    aktif = gaya != "cetak"
    if gaya in {"cetak", "murid"}:
        return _render_baris(teks, "teks", "tanya", pecahan_aktif=aktif)
    if gaya == "stitch":
        return _render_baris(teks, "kerja-teks-st", "kerja-tanya-st", pecahan_aktif=aktif)
    return _render_teks_guru(teks)


def _render_visual(
    descriptor: DescriptorVisual,
    namespace: str,
) -> str:
    data = descriptor.data
    pasangan = (descriptor.jenis, descriptor.versi)
    if descriptor.versi == 2 and descriptor.jenis in {"korek", "titik"}:
        from number_patterns_svg import render_pola
        return render_pola(descriptor.jenis, data, namespace)
    if pasangan == ("korek", 1):
        return _svg_korek(
            data["n_tampil"],
            data["awal"],
            data["tambah"],
            namespace=namespace,
        )
    if pasangan == ("titik", 1):
        return _svg_titik(data["n_tampil"], namespace=namespace)
    if descriptor.versi == 1 and descriptor.jenis in {
        "batang", "turus", "piktogram", "lingkaran"
    }:
        return render_statistika(descriptor.jenis, data, namespace)
    if pasangan == ("geometri_ruang", 1):
        from solid_geometry_svg import render_geometri_ruang
        return render_geometri_ruang(data, namespace)
    if pasangan == ("skala_peta", 1):
        from measurement_scale_visual import render_skala
        return render_skala(data, namespace)
    if pasangan == ("venn_dua", 1):
        from combinatorics_sets_visual import render_venn
        return render_venn(data, namespace)
    if pasangan == ("susunan_objek", 1):
        from combinatorics_arrangements_svg import render_susunan
        return render_susunan(data, namespace)
    if pasangan == ("jalur_petak", 1):
        from combinatorics_svg import render_petak
        return render_petak(data, namespace)
    if pasangan == ("linimasa_jam", 1):
        from measurement_svg import render_waktu
        return render_waktu(data, namespace)
    if pasangan == ("geometri_datar", 1):
        from plane_geometry_svg import render_geometri_datar
        return render_geometri_datar(data, namespace)
    if descriptor.jenis == "placeholder":
        raise ValueError("placeholder bukan visual asli dan tidak boleh dirender")
    raise ValueError(
        f"descriptor visual tidak didukung: {descriptor.jenis!r} v{descriptor.versi!r}"
    )


def _sisipkan_visual(teks: str, gaya: str, visual: str) -> str:
    """Taruh visual sebelum pertanyaan akhir seperti renderer lama."""
    baris = _baris(teks)
    if gaya == "guru" or len(baris) == 1:
        return _render_teks_per_gaya(teks, gaya) + visual

    pengantar = "\n".join(baris[:-1])
    pertanyaan = baris[-1]
    if gaya in {"cetak", "murid"}:
        kelas_teks, kelas_tanya = "teks", "tanya"
    else:
        kelas_teks, kelas_tanya = "kerja-teks-st", "kerja-tanya-st"
    return (
        _render_baris(pengantar, kelas_teks, kelas_teks,
                      pecahan_aktif=gaya != "cetak")
        + visual
        + f'<div class="{kelas_tanya}">{html.escape(pertanyaan)}</div>'
    )


def _descriptor_visual_siap(
    penyajian: PenyajianPertanyaan,
) -> DescriptorVisual | None:
    if penyajian.status_visual != "siap":
        return None
    descriptor = penyajian.descriptor
    if descriptor is None:  # Sudah dijaga kontrak; pertahanan berlapis.
        raise ValueError("descriptor wajib ada untuk visual siap")
    mode_diharapkan = f"{descriptor.jenis}-v{descriptor.versi}"
    if penyajian.mode_representasi != mode_diharapkan:
        raise ValueError("mode representasi tidak cocok dengan descriptor")
    if descriptor.jenis == "placeholder":
        raise ValueError("placeholder bukan visual asli dan tidak boleh dirender")
    return descriptor


def render_pertanyaan(
    penyajian: PenyajianPertanyaan,
    *,
    gaya: str = "cetak",
    namespace: str = "soal",
) -> str:
    """Render snapshot menjadi HTML aman tanpa menyentuh Soal atau kunci."""
    penyajian = _validasi_untuk_render(penyajian)
    if gaya not in _GAYA_DIDUKUNG:
        raise ValueError(f"gaya renderer tidak dikenal: {gaya!r}")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace wajib berupa teks yang tidak kosong")

    badan = _render_teks_per_gaya(penyajian.teks_soal, gaya)
    descriptor = _descriptor_visual_siap(penyajian)
    if descriptor is not None:
        visual = _render_visual(descriptor, namespace)
        badan = _sisipkan_visual(penyajian.teks_soal, gaya, visual)

    fingerprint = html.escape(penyajian.fingerprint_penyajian, quote=True)
    return f'<div data-fingerprint-penyajian="{fingerprint}">{badan}</div>'


def _ringkasan_descriptor(descriptor: DescriptorVisual) -> str:
    data = descriptor.data
    if (descriptor.jenis, descriptor.versi) == ("geometri_ruang", 1):
        from solid_geometry_svg import ringkasan_geometri_ruang
        return ringkasan_geometri_ruang(data)
    if (descriptor.jenis, descriptor.versi) == ("skala_peta", 1):
        from measurement_scale_visual import ringkasan_skala
        return ringkasan_skala(data)
    if (descriptor.jenis, descriptor.versi) == ("venn_dua", 1):
        from combinatorics_sets_visual import ringkasan_venn
        return ringkasan_venn(data)
    if (descriptor.jenis, descriptor.versi) == ("susunan_objek", 1):
        from combinatorics_arrangements_svg import ringkasan_susunan
        return ringkasan_susunan(data)
    if (descriptor.jenis, descriptor.versi) == ("jalur_petak", 1):
        from combinatorics_svg import ringkasan_petak
        return ringkasan_petak(data)
    if (descriptor.jenis, descriptor.versi) == ("linimasa_jam", 1):
        from measurement_svg import ringkasan_waktu
        return ringkasan_waktu(data)
    if (descriptor.jenis, descriptor.versi) == ("geometri_datar", 1):
        from plane_geometry_svg import ringkasan_geometri_datar
        return ringkasan_geometri_datar(data)
    if descriptor.jenis == "korek" and descriptor.versi in {1, 2}:
        jumlah = [
            data["awal"] + data["tambah"] * indeks
            for indeks in range(data["n_tampil"])
        ]
        daftar = ", ".join(str(nilai) for nilai in jumlah)
        return f"Visual menampilkan {data['n_tampil']} tahap: {daftar} batang."
    if descriptor.jenis == "titik" and descriptor.versi in {1, 2}:
        jumlah = [
            tahap * (tahap + 1) // 2
            for tahap in range(1, data["n_tampil"] + 1)
        ]
        daftar = ", ".join(str(nilai) for nilai in jumlah)
        return f"Visual menampilkan {data['n_tampil']} tahap: {daftar} titik."
    if (descriptor.jenis, descriptor.versi) == ("batang", 1):
        daftar = ", ".join(
            f"{nama} setinggi {nilai}"
            for nama, nilai in zip(data["nama"], data["data"])
        )
        return f"Fakta visual: diagram batang memuat {daftar}."
    if (descriptor.jenis, descriptor.versi) == ("turus", 1):
        daftar = ", ".join(
            f"{nama} memiliki {nilai} turus"
            for nama, nilai in zip(data["nama"], data["data"])
        )
        return f"Fakta visual: tabel memuat {daftar}."
    if (descriptor.jenis, descriptor.versi) == ("piktogram", 1):
        daftar = ", ".join(
            f"{nama} memiliki {jumlah} gambar"
            for nama, jumlah in zip(data["nama"], data["gambar"])
        )
        return (
            f"Fakta visual: {daftar}; satu gambar mewakili "
            f"{data['satuan']} buah."
        )
    if (descriptor.jenis, descriptor.versi) == ("lingkaran", 1):
        if data["varian"] == "cari_nilai":
            return (
                "Fakta visual: total data "
                f"{data['total']} siswa dan sudut bagian olahraga "
                f"{data['sudut']} derajat."
            )
        return (
            "Fakta visual: total data "
            f"{data['total']} siswa dan bagian membaca berisi "
            f"{data['nilai']} siswa; sudutnya belum diberi nilai."
        )
    raise ValueError(
        f"descriptor visual tidak didukung: {descriptor.jenis!r} v{descriptor.versi!r}"
    )


def ringkasan_pertanyaan(penyajian: PenyajianPertanyaan) -> str:
    """Teks polos beserta fakta visual aman untuk konteks non-HTML."""
    penyajian = _validasi_untuk_render(penyajian)
    descriptor = _descriptor_visual_siap(penyajian)
    if descriptor is None:
        return penyajian.teks_soal
    return f"{penyajian.teks_soal}\n{_ringkasan_descriptor(descriptor)}"


def render_teks(penyajian: PenyajianPertanyaan) -> str:
    """Kompatibilitas Fase 1: kembalikan teks snapshot tervalidasi."""
    penyajian = _validasi_untuk_render(penyajian)
    return penyajian.teks_soal
