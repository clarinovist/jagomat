"""Kontrak CSS mobile halaman sesi guru: teks 14px, kontrol besar, aksi dan penilaian tidak berdesakan."""
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import design_tokens as T
import style_stitch

CSS = style_stitch.CSS_SESI


def _blok(selektor):
    hasil = re.findall(re.escape(selektor) + r"\s*\{([^}]*)\}", CSS)
    assert hasil, selektor
    return "\n".join(hasil)


def test_teks_informatif_tinjauan_minimal_14px():
    for selektor in style_stitch.SELEKTOR_TEKS_SESI:
        assert f"body.st {selektor} {{ font-size: {T.UKURAN_TEKS_LABEL}; }}" in CSS


def test_kotak_centang_tinjauan_24px_dan_baris_44px():
    blok = _blok("body.st .koreksi-editorial-st input[type=checkbox]")
    assert "width: 1.5rem" in blok and "height: 1.5rem" in blok
    assert f"min-height: {T.TARGET_SENTUH}" in _blok("body.st .koreksi-editorial-st .koreksi-centang-st")


def _ponsel():
    awal = CSS.rindex("@media (max-width: " + T.BATAS_HP + ") {", 0, CSS.index("Perbaikan mobile sesi") + 4000)
    return CSS[awal:]


def test_bilah_aksi_sticky_tetap_ringkas_di_ponsel():
    # Bilah menempel di dasar layar: hitungan di barisnya sendiri, dua tombol tetap berdampingan.
    ponsel = _ponsel()
    assert "body.st .koreksi-editorial-st .koreksi-simpan-st { flex-direction: column; align-items: stretch; }" in ponsel
    assert "body.st .koreksi-editorial-st .koreksi-aksi-sesi-st { flex-direction: row;" in ponsel
    assert "flex: 1 1 0" in ponsel and f"min-height: {T.TARGET_SENTUH}" in ponsel
    assert "flex-direction: column; }" not in ponsel.split(".koreksi-aksi-sesi-st", 1)[1].split("}", 1)[0]


def test_label_penilaian_dan_penanda_wajib_tidak_berdesakan_di_ponsel():
    ponsel = _ponsel()
    assert "body.st .koreksi-editorial-st .koreksi-label-st { flex-wrap: wrap; }" in ponsel
    assert "body.st .koreksi-editorial-st .koreksi-wajib-st { flex-basis: 100%; }" in ponsel
    assert "body.st .koreksi-editorial-st .koreksi-select-st { font-size: " + T.UKURAN_TEKS_LABEL in ponsel
