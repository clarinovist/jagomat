"""Kontrak pilot disetujui: dua tugas berbeda, bukan jenjang P3–P6.

Modul murni ini tidak mengaktifkan writer atau memproyeksikan histori menjadi
kelulusan. Kisi luas hanya rujukan prasyarat, bukan target pilot ketiga.
"""
from dataclasses import dataclass
import hashlib
import json
from typing import Optional, Tuple

VERSI_RUBRIK = "pilot-keliling-luas-v1"
VERSI_VARIASI = "persegi-panjang-variasi-v1"
LANGSUNG = "persegi-panjang.keliling-langsung.v1"
BALIK = "persegi-panjang.luas-dari-keliling.v1"
PRASYARAT = "persegi-panjang.rujukan-kisi-luas.v1"
POLA = "keliling_luas_datar"
POLA_KISI = "luas_kotak_satuan"
REPRESENTASI = ("teks-v1", "geometri_datar-v1")
KODE = ("B", "K", "H", "E", "N", "T")
KunciFokus = Tuple[str, str, Optional[str]]


@dataclass(frozen=True)
class TuntutanPilot:
    id: str
    nama: str
    template_id: str
    varian: Optional[str]
    profil: Tuple[str, ...]
    cek_penjelasan: Tuple[str, ...]


TUNTUTAN = (
    TuntutanPilot(LANGSUNG, "Keliling dari panjang dan lebar", POLA, "keliling",
                  ("P3", "P4", "P5", "P6"),
                  ("Tunjukkan dua pasang sisi yang sama panjang.",
                   "Mengapa dua sisi dijumlahkan lalu dikali dua, bukan dikalikan?")),
    TuntutanPilot(BALIK, "Luas setelah mencari sisi dari keliling", POLA, "balik_luas",
                  ("P4", "P5", "P6"),
                  ("Apa arti separuh keliling?", "Bagaimana menemukan sisi yang belum diketahui?",
                   "Mengapa masih perlu perkalian, dan apa arti satuan persegi?")),
)
RUJUKAN_LUAS = TuntutanPilot(
    PRASYARAT, "Rujukan luas melalui baris dan kolom", POLA_KISI, None, ("P3",),
    ("Mengapa banyak petak dalam satu baris dikalikan banyak baris?",
     "Apa arti satu petak satuan persegi?"),
)


def tuntutan(identitas):
    """ID asing tidak menjadi tugas langsung atau rujukan prasyarat."""
    if type(identitas) is not str:
        raise ValueError("identitas tuntutan tidak sah")
    for item in (*TUNTUTAN, RUJUKAN_LUAS):
        if item.id == identitas:
            return item
    raise ValueError("tuntutan di luar pilot")


@dataclass(frozen=True)
class KonteksPilot:
    tuntutan_id: str
    profil_parameter: str
    mode_representasi: str
    versi_rubrik: str = VERSI_RUBRIK

    def __post_init__(self):
        item = tuntutan(self.tuntutan_id)
        if (type(self.versi_rubrik) is not str or self.versi_rubrik != VERSI_RUBRIK
                or type(self.profil_parameter) is not str or self.profil_parameter not in item.profil
                or type(self.mode_representasi) is not str or self.mode_representasi not in REPRESENTASI):
            raise ValueError("versi, profil atau representasi pilot tidak didukung")

    @property
    def template_id(self):
        return tuntutan(self.tuntutan_id).template_id

    @property
    def id(self):
        return ":".join((self.versi_rubrik, self.tuntutan_id,
                         self.profil_parameter, self.mode_representasi))


def validasi_fokus(konteks, fokus):
    """Pertahankan kunci kanonis; malrule tidak boleh berasal dari varian lain."""
    if type(konteks) is not KonteksPilot:
        raise ValueError("konteks pilot tidak sah")
    if (type(fokus) is not tuple or len(fokus) != 3
            or type(fokus[0]) is not str or fokus[0] != konteks.template_id
            or type(fokus[1]) is not str or fokus[1] not in KODE
            or (fokus[2] is not None and type(fokus[2]) is not str)):
        raise ValueError("kunci fokus pilot tidak sah")
    if fokus[2] is None:
        return
    daftar = {
        LANGSUNG: {"datar.tukar_luas": "K", "datar.lupa_kali_dua": "K", "datar.kurang_satu": "H"},
        BALIK: {"datar.balik_lupa_bagi_dua": "K", "datar.balik_jawab_panjang": "B",
                "datar.balik_kurang_satu": "H"},
        PRASYARAT: {"datar.hitung_keliling": "H", "datar.hanya_satu_baris": "K",
                    "datar.hanya_satu_kolom": "K", "datar.kurang_satu": "H"},
    }
    if daftar[konteks.tuntutan_id].get(fokus[2]) != fokus[1]:
        raise ValueError("malrule tidak cocok dengan tuntutan dan diagnosis")


def ukuran_matematis(konteks, template_id, parameter):
    """Validasi bentuk dan batas source; jangan percaya label tuntutan saja."""
    if type(konteks) is not KonteksPilot or template_id != konteks.template_id:
        raise ValueError("pola tidak cocok tuntutan")
    if type(parameter) is not dict:
        raise ValueError("parameter pilot wajib objek")
    if konteks.tuntutan_id == PRASYARAT:
        if (set(parameter) != {"p", "l", "satuan", "konteks"}
                or type(parameter["satuan"]) is not str or parameter["satuan"] not in ("cm", "m")
                or type(parameter["konteks"]) is not str
                or parameter["konteks"] not in ("ubin", "keramik", "kotak kue", "potongan cokelat", "stiker", "kancing")):
            raise ValueError("parameter kisi di luar sumber pilot")
        p, l = parameter["p"], parameter["l"]
        batas_p, batas_l = (2, 8), (2, 8)
    else:
        balik = konteks.tuntutan_id == BALIK
        field = {"varian", "p", "K" if balik else "l"}
        if (set(parameter) != field or type(parameter["varian"]) is not str
                or parameter["varian"] != tuntutan(konteks.tuntutan_id).varian):
            raise ValueError("varian tidak cocok tuntutan")
        p = parameter["p"]
        if balik:
            keliling = parameter["K"]
            if type(p) is not int or type(keliling) is not int or keliling % 2:
                raise ValueError("keliling tidak menghasilkan sisi bulat")
            l = keliling // 2 - p
            batas_p, batas_l = (3, 30), (2, 25)
        else:
            l = parameter["l"]
            batas_p = batas_l = (2, 16) if konteks.profil_parameter == "P3" else (3, 40)
    if any(type(n) is not int or not bawah <= n <= atas
           for n, (bawah, atas) in ((p, batas_p), (l, batas_l))):
        raise ValueError("ukuran tidak tersedia pada profil sumber")
    if konteks.tuntutan_id == PRASYARAT:
        ditolak = p * l in (2 * (p + l), 2 * (p + l) + 1)
    elif konteks.tuntutan_id == LANGSUNG:
        ditolak = p * l == 2 * (p + l) or p == l == 2
        if konteks.profil_parameter == "P3":
            ditolak = ditolak or p * l == 2 * (p + l) - 1
    else:
        ditolak = False
    if ditolak:
        raise ValueError("ukuran dikecualikan generator sumber")
    return p, l


def sidik_variasi(konteks, template_id, parameter):
    """Sidik tambahan, tidak mengganti fingerprint historis/provenance.

    Nama benda, satuan kisi cm/m saja, cerita dan pertukaran orientasi ukuran
    yang sama bukan probe matematika baru. Profil/mode tetap dipisahkan oleh
    konteks bukti, bukan disatukan oleh kesamaan sidik ini.
    """
    ukuran = sorted(ukuran_matematis(konteks, template_id, parameter))
    isi = [VERSI_VARIASI, konteks.tuntutan_id, ukuran]
    return hashlib.sha256(json.dumps(isi, separators=(",", ":")).encode()).hexdigest()


def profil_tujuan(konteks_sumber, tuntutan_id, pilihan=None):
    """Sumber yang tidak mendukung varian wajib pilihan eksplisit orang tua."""
    if type(konteks_sumber) is not KonteksPilot:
        raise ValueError("konteks sumber tidak sah")
    tujuan = tuntutan(tuntutan_id)
    if pilihan is None:
        if konteks_sumber.profil_parameter not in tujuan.profil:
            raise ValueError("Pilih profil parameter tujuan secara eksplisit.")
        return konteks_sumber.profil_parameter
    if type(pilihan) is not str or pilihan not in tujuan.profil:
        raise ValueError("profil tujuan tidak mendukung tuntutan")
    return pilihan
