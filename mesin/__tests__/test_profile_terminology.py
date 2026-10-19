"""Istilah dan warna profil tidak mengganti kontrak domain atau rute lama."""
import re

import context_report
import design_tokens as T
import mastery_report
import profile_workspace
import skill_pilot_ui


def _kontras(a, b):
    def luminansi(warna):
        warna = warna.lstrip('#')
        if len(warna) == 3:
            warna = ''.join(c * 2 for c in warna)
        rgb = [int(warna[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * bobot for v, bobot in zip(linear, (.2126, .7152, .0722)))
    nilai = sorted((luminansi(a), luminansi(b)))
    return (nilai[1] + .05) / (nilai[0] + .05)


def test_navigasi_baku_mempertahankan_section_dan_pagination():
    for aktif in ('rencana', 'latihan', 'riwayat', 'perkembangan'):
        isi = profile_workspace.navigasi_profil(7, 12, aktif)
        assert re.findall(r'>([^<]+)</a>', isi) == ['Beranda', 'Latihan', 'Riwayat', 'Perkembangan']
        assert f'href="/anak/7?section={aktif}" aria-current="page"' in isi
        assert isi.count('aria-current="page"') == 1


def test_label_target_sama_tanpa_mengubah_kode_status():
    baku = {'terbukti': 'Menunjukkan pemahaman', 'dipelajari': 'Sedang dipelajari',
            'perlu_cek': 'Perlu dicek kembali', 'belum_dinilai': 'Belum dinilai'}
    assert mastery_report.LABEL == context_report._LABEL == skill_pilot_ui.LABEL == baku


def test_aksi_profil_teal_scoped_dan_pasangan_teks_kontras():
    css = profile_workspace.GAYA_PROFIL
    selector = '.profil-workspace-st :is(.st-tombol-coral, .tombol-coral, .rencana-cta-utama-st)'
    biasa = css.split(selector + ' {', 1)[1].split('}', 1)[0]
    hover = css.split(selector + ':hover {', 1)[1].split('}', 1)[0]
    assert f'background:{T.AKSEN_TEAL_TUA}' in biasa
    assert f'background:{T.AKSEN_TEAL_HOVER}' in hover
    assert f'color:{T.TEKS_PUTIH}' in biasa
    for teks, latar in ((T.TEKS_PUTIH, T.AKSEN_TEAL_TUA),
                        (T.TEKS_PUTIH, T.AKSEN_TEAL_HOVER),
                        (T.TEKS_JUDUL, T.LATAR_KARTU_SEKUNDER),
                        (T.KODE_BENAR_TEKS, T.KODE_BENAR_BG),
                        (T.TEKS_JUDUL, T.LATAR_CATATAN)):
        assert _kontras(teks, latar) >= 4.5
