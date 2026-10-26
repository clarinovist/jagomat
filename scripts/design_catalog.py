#!/usr/bin/env python3
"""Ekspor katalog design system statis dari token dan CSS sumber, tanpa DB/JS/jaringan."""
import argparse
from dataclasses import dataclass
import html
from pathlib import Path
import re
import subprocess
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "mesin"))
import admin_komponen  # noqa: E402
import admin_style  # noqa: E402
import account_style  # noqa: E402
import child_components as K  # noqa: E402
import child_header  # noqa: E402
import child_style  # noqa: E402
import design_roles as R  # noqa: E402
import design_tokens as T  # noqa: E402
import profile_workspace  # noqa: E402
import style_stitch  # noqa: E402
import teacher_style  # noqa: E402

WEBFONT = re.compile(r"@import url\([^)]*\);")
PROFIL = "bungkus-st pendamping-editorial-st profil-editorial-st profil-workspace-st anak-header-st"
KODE = ("benar", "K", "B", "H", "E", "T", "N")


@dataclass(frozen=True)
class Demo:
    judul: str
    css: str
    body: str
    isi: str
    tinggi: int


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def tanpa_webfont(css: str) -> str:
    """Katalog luring: buang @import font jaringan, jatuh ke stack font sistem."""
    return WEBFONT.sub("", css)


def _dasar() -> str:
    info = ('<p class="info-baris">Pilih nama untuk mulai. <button type="button" class="info" '
            'aria-label="Penjelasan contoh">i<span class="info-bubble" role="tooltip">'
            'Penjelasan contoh</span></button></p>')
    badge = "".join(f'<span class="st-badge {k}">{k}</span> '
                    for k in ("diagnostik", "latihan", "baru", "selesai", "review"))
    return f"""<div class="bungkus-st">
<div class="st-kartu"><h2 class="st">Kartu konten</h2><p>Teks badan pada kartu.</p>{info}</div>
<h3 class="st">Tombol</h3><p><button class="st-tombol-coral" type="button">Simpan</button>
<a class="tombol-coral" href="#">Tautan aksi</a></p>
<h3 class="st">Input</h3><label>Nama <input class="st-input" value="Contoh"></label>
<label>Pilihan <select class="st-input"><option>Satu</option><option>Dua</option></select></label>
<div class="kolom-sandi"><input class="st-input" type="password" value="contoh-sandi" aria-label="Sandi">
<button type="button" class="tombol-mata" aria-label="Tampilkan sandi" aria-pressed="false">Lihat</button></div>
<h3 class="st">Badge</h3><p>{badge}<span class="badge-peran badge-peran-admin">Pengelola</span>
<span class="badge-peran badge-peran-guru">Guru</span></p>
<div class="st-banner-sukses" role="status">Perubahan tersimpan.</div>
<details class="rincian-ui-st"><summary>Rincian (tertutup)</summary><p>Isi sekunder.</p></details>
<details class="rincian-ui-st" open><summary>Rincian (terbuka)</summary><p>Isi sekunder.</p></details>
</div>"""


def _profil() -> str:
    chip = " ".join(K.chip_status(n.capitalize(), n) for n in K.NADA_CHIP)
    pil = K.pil_filter("Semua", "#") + " " + K.pil_filter("Perlu dicek", "#", aktif=True)
    kartu = K.kartu_sesi(judul="Sesi contoh", sub="Latihan · 10 soal", peringatan="Menunggu konfirmasi",
                         chip_html=K.chip_status("Perlu dicek", "perhatian"),
                         aksi_html='<a class="tombol-coral" href="#">Buka sesi</a>')
    return f"""<nav class="profil-tabs-st" aria-label="Contoh tab">{profile_workspace.navigasi_profil(1, 0, "riwayat")}</nav>
<p>{chip}</p><p>{pil}</p>{kartu}
{K.banner_tautan("Contoh banner tautan", "#", "Lihat")}
{K.disclosure("Disclosure tertutup", "<p>Isi.</p>")}{K.disclosure("Disclosure terbuka", "<p>Isi.</p>", terbuka=True)}
<p><button class="st-tombol-coral" type="button">Aksi utama profil</button></p>"""


def _tinjauan() -> str:
    baru = " ".join(f'<span class="koreksi-status-st {k}">{k}</span>' for k in KODE)
    lama = " ".join(f'<span class="kode {k}">{k}</span>' for k in KODE)
    return (f'<div class="bungkus"><p>Pill tinjauan: {baru}</p><p>Pill lama: {lama}</p>'
            f'<p class="kunci">Kunci: 42</p></div>')


def _admin() -> str:
    return f"""<main class="admin-utama"><p class="admin-jejak"><a href="#">← Kembali ke daftar</a></p>
<div class="admin-tab-baris"><a class="admin-tab" href="#" aria-current="page">Tab aktif</a>
<a class="admin-tab" href="#">Tab</a></div><div class="admin-kartu"><h2>Kartu admin</h2>
<p><button class="admin-tombol" type="button">Simpan</button>
<button class="admin-tombol admin-tombol-sekunder" type="button">Cari</button>
<button class="admin-tombol admin-bahaya" type="button">Hapus</button>
<a class="admin-tautan" href="#">Tautan</a></p>
<p class="admin-chip-baris"><a class="admin-chip" href="#" aria-current="true">Semua</a>
<a class="admin-chip" href="#">Pil filter</a></p>
<form class="admin-cari"><label>Cari <input value="contoh"></label></form>
<p>{admin_komponen.badge_status(())} {admin_komponen.badge_status(("ok",))}
{admin_komponen.badge_status(("perlu_diperiksa",))}</p></div></main>"""


def _akun() -> str:
    return ('<div class="akun-editorial-st"><nav class="nav-samping" aria-label="Contoh tab akun">'
            '<a href="#" aria-current="page">Akun saya</a><a href="#">Anak</a></nav>'
            '<p><a class="akun-tombol-garis-st" href="#">Tombol garis</a> '
            '<a class="akun-tautan-st" href="#">Tautan akun</a></p>'
            '<p><button class="tombol-bahaya-akun" type="button">Cabut semua izin</button></p></div>')


def demo() -> tuple:
    stitch = tanpa_webfont(style_stitch.gaya_stitch())
    profil = stitch + profile_workspace.GAYA_PROFIL + child_style.GAYA_ANAK + child_header.GAYA_HEADER_ANAK
    admin = admin_style.GAYA_ADMIN
    return (
        Demo("Dasar (Stitch)", stitch, 'class="st"', _dasar(), 900),
        Demo("Profil anak dan ruang guru", profil, 'class="st"', f'<div class="{PROFIL}">{_profil()}</div>', 760),
        Demo("Tinjauan: pill kode", teacher_style.GAYA_GURU + style_stitch.CSS_SESI, "", _tinjauan(), 200),
        Demo("Akun", stitch + account_style.GAYA_AKUN, 'class="st"', _akun(), 210),
        Demo("Admin — terang", admin, 'class="admin-readonly" data-tema="terang"', _admin(), 470),
        Demo("Admin — gelap", admin, 'class="admin-readonly" data-tema="gelap"', _admin(), 470),
    )


def _srcdoc(d: Demo) -> str:
    return (f'<!doctype html><html lang="id"><head><meta charset="utf-8"><style>{d.css}</style></head>'
            f'<body {d.body}>{d.isi}</body></html>')


def _swatch(hex_warna: str) -> str:
    return f'<span class="sw" style="background:{_e(hex_warna)}"></span><code>{_e(hex_warna)}</code>'


def _tabel_kontras(nama: str) -> str:
    baris = []
    for p in R.PERMUKAAN[nama]:
        a, b = R.nilai(p.depan), R.nilai(p.belakang)
        r = R.rasio_kontras(a, b)
        kunci = (nama, p.depan.peran, p.belakang.peran)
        status = "lulus" if r >= p.minimum else ("gagal (tercatat)" if kunci in R.PENGECUALIAN else "GAGAL")
        baris.append(f"<tr><td>{_e(p.depan.peran)}<br><small>{_e(p.depan.token)}</small> {_swatch(a)}</td>"
                     f"<td>{_e(p.belakang.peran)}<br><small>{_e(p.belakang.token)}</small> {_swatch(b)}</td>"
                     f"<td>{r:.2f}:1</td><td>{p.minimum:g}:1</td><td>{status}</td>"
                     f"<td><code>{_e(p.depan.selektor)}</code></td></tr>")
    return (f'<h3>{_e(nama)}</h3><table><tr><th>Depan</th><th>Belakang</th><th>Rasio</th>'
            f'<th>Minimum</th><th>Status</th><th>Aturan</th></tr>{"".join(baris)}</table>')


def _skala() -> str:
    tipe = ("UKURAN_JUDUL_DEWASA", "UKURAN_BAGIAN_DEWASA", "UKURAN_ANGKA_DEWASA", "UKURAN_BADAN_LAYAR",
            "UKURAN_TEKS_BANTUAN", "UKURAN_TEKS_LABEL", "UKURAN_TEKS_CATATAN", "UKURAN_TEKS_META")
    teks = "".join(f'<p style="font-size:{_e(getattr(T, t))}"><code>{t}</code> {_e(getattr(T, t))} — '
                   f'Jago karena tahu caranya.</p>' for t in tipe)
    jarak = "".join(f'<div class="jarak"><span style="width:{_e(getattr(T, f"SP_{i}"))}"></span>'
                    f'<code>SP_{i} {_e(getattr(T, f"SP_{i}"))}</code></div>' for i in range(1, 9))
    radius = "".join(f'<span class="radius" style="border-radius:{_e(getattr(T, r))}"><code>{r}</code></span>'
                     for r in ("RADIUS_KECIL", "RADIUS_SEDANG", "RADIUS_KARTU", "RADIUS_KARTU_BESAR", "RADIUS_PIL"))
    return f"<h2>Skala</h2><h3>Tipografi</h3>{teks}<h3>Jarak</h3>{jarak}<h3>Radius</h3><p>{radius}</p>"


def _sumber() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(AKAR), "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True, timeout=30).stdout.strip()
        kotor = subprocess.run(["git", "-C", str(AKAR), "status", "--porcelain", "--", "mesin", "scripts"],
                               capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "sumber Git tidak diketahui"
    return f"commit {sha}" + (" + perubahan belum di-commit" if kotor else "")


GAYA_KATALOG = f"""
body {{ margin: 0 auto; max-width: 72rem; padding: {T.SP_5} {T.SP_4}; font-family: {T.FONT_LAYAR};
  color: {T.TEKS_UTAMA}; background: {T.LATAR_KARTU}; line-height: 1.5; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: {T.SP_5}; font-size: {T.UKURAN_TEKS_LABEL}; }}
th, td {{ border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; padding: {T.SP_2}; text-align: left; vertical-align: top; }}
.sw {{ display: inline-block; width: 1rem; height: 1rem; border: {T.TEBAL_GARIS} solid {T.TEKS_UTAMA};
  vertical-align: middle; margin-right: {T.SP_1}; }}
iframe {{ width: 100%; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; margin-bottom: {T.SP_5}; }}
.jarak span {{ display: inline-block; height: 1rem; background: {T.AKSEN_TEAL_TUA}; margin-right: {T.SP_2}; }}
.radius {{ display: inline-block; padding: {T.SP_3}; margin: {T.SP_1}; border: 2px solid {T.AKSEN_TEAL_TUA}; }}
"""


def bangun_html() -> str:
    kontras = "".join(_tabel_kontras(n) for n in R.PERMUKAAN)
    iframe = "".join(f'<h3>{_e(d.judul)}</h3><iframe title="{_e(d.judul)}" height="{d.tinggi}" '
                     f'sandbox srcdoc="{_e(_srcdoc(d))}"></iframe>' for d in demo())
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Katalog design system Jagomat</title><style>{GAYA_KATALOG}</style></head><body>
<h1>Katalog design system Jagomat</h1>
<p>Dihasilkan dari <code>design_tokens.py</code>, <code>design_roles.py</code> dan CSS aplikasi
({_e(_sumber())}). Bukan halaman aplikasi; data contoh sintetis. Webfont dan Material Symbols
tidak dimuat (luring), jadi teks memakai font sistem. Kontrak: <code>docs/design-system.md</code>.</p>
<h2>Peran dan kontras per permukaan</h2>{kontras}{_skala()}
<h2>Komponen dengan CSS asli</h2><p>Hover dan fokus perlu diuji langsung di browser;
state statis (aktif, terbuka, nonaktif) ditampilkan.</p>{iframe}</body></html>"""


def ekspor(tujuan: Path) -> Path:
    # Bangun dulu: kegagalan render tidak meninggalkan folder kosong yang memblokir ulang.
    isi = bangun_html()
    tujuan.mkdir(parents=True, exist_ok=False)
    berkas = tujuan / "index.html"
    berkas.write_text(isi, encoding="utf-8")
    return berkas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="folder baru untuk index.html")
    berkas = ekspor(parser.parse_args().output)
    print(berkas.resolve())


if __name__ == "__main__":
    main()
