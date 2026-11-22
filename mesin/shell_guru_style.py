"""Shell bersama halaman guru: satu wadah, satu topbar, satu menu akun.

Keputusan pemilik 22 Nov 2026: semua permukaan guru (ruang guru, profil anak,
akun, tinjauan sesi, laporan, lomba) memakai topbar yang sama dengan posisi logo
yang sama. Wadah selalu `LEBAR_SHELL_GURU` ditambah gutter; kolom isi yang lebih
sempit diletakkan di tengah. Semua aturan diikat ke `.shell-guru-st` (kelas yang
dipasang `teacher_shell`) dengan spesifisitas di atas stylesheet per halaman.
"""
import design_tokens as T

_W = "body.st .bungkus-st.shell-guru-st"
_TOPBAR = f"{_W} > .st-topbar"
# Halaman yang isinya memang kolom baca 46rem di dalam wadah 60rem.
_KOLOM_SEMPIT = f"{_W}:is(.guru-beranda-st, .bagikan-editorial-st, .akun-sempit-st, .hapus-editorial-st)"

GAYA_SHELL_GURU = f"""
/* Wadah: lebar & gutter yang sama di semua halaman guru. */
{_W} {{
  width: 100%; max-width: calc({T.LEBAR_SHELL_GURU} + 2 * {T.ANAK_GUTTER});
  margin-inline: auto; padding-inline: {T.ANAK_GUTTER}; padding-top: {T.SP_5};
}}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_W} {{ padding-inline: {T.SP_4}; padding-top: {T.SP_4}; }}
}}
{_KOLOM_SEMPIT} > :not(.st-topbar) {{ max-width: {T.LEBAR_KONTEN}; margin-inline: auto; }}

/* Topbar: lockup kiri, kontrol akun kanan (peran + nama keluarga). */
{_TOPBAR} {{
  display: flex; align-items: center; justify-content: space-between; flex-wrap: nowrap;
  width: 100%; max-width: none; height: auto; min-height: {T.TARGET_SENTUH};
  margin: 0 0 {T.SP_5}; padding: 0 0 {T.SP_4}; gap: {T.SP_3};
  position: relative; top: auto; z-index: 50; background: transparent;
  border: 0; border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  font-family: {T.FONT_HEADLINE};
}}
{_TOPBAR} .brand {{
  display: inline-flex; align-items: center; flex: none; gap: {T.SP_2};
  min-height: {T.TARGET_SENTUH}; text-decoration: none; color: {T.AKSEN_TEAL_TUA}; font-size: 1rem;
}}
{_TOPBAR} .brand .nama {{
  color: {T.AKSEN_TEAL_TUA}; font: 800 1.5rem/1.4 {T.FONT_HEADLINE}; letter-spacing: -.04em;
}}
{_TOPBAR} .topbar-navigasi {{
  display: flex; align-items: center; flex: 0 1 auto; min-width: 0; margin-left: auto;
  flex-wrap: nowrap; justify-content: flex-end; gap: {T.SP_2};
}}
{_TOPBAR} .topbar-navigasi > form {{ display: contents; }}
{_TOPBAR} .menu-pengguna {{ position: relative; min-width: 0; }}
{_TOPBAR} .menu-pengguna summary {{
  display: flex; align-items: center; gap: {T.SP_2}; min-width: 0; max-width: none;
  min-height: {T.TARGET_SENTUH}; height: auto; padding: 0 {T.SP_2};
  border: 0; border-radius: {T.RADIUS_SEDANG}; background: transparent;
  font: 600 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; cursor: pointer;
}}
{_TOPBAR} .menu-pengguna summary:hover, {_TOPBAR} .menu-pengguna[open] summary {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
{_TOPBAR} .menu-pengguna summary::after {{ content: none; }}
{_TOPBAR} .identitas-akun-st {{ display: grid; gap: 0; min-width: 0; text-align: left; }}
{_TOPBAR} .nama-akun-st {{ overflow-wrap: anywhere; white-space: normal; }}
{_TOPBAR} .badge-peran {{ padding: 0; background: transparent; color: {T.TEKS_VARIAN}; font-weight: 400; }}
{_TOPBAR} .menu-isi {{
  position: absolute; top: calc(100% + 6px); right: 0; left: auto; z-index: 60;
  min-width: 12rem; max-width: min(12rem, calc(100vw - 1.2rem));
  padding: {T.SP_2}; gap: {T.SP_1};
}}
{_TOPBAR} .menu-isi > a {{
  display: flex; align-items: center; width: 100%; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL};
  color: {T.TEKS_UTAMA}; background: transparent; text-decoration: none;
  font: 400 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE};
}}
{_TOPBAR} .menu-isi > a:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
{_TOPBAR} .menu-isi > a[aria-current="page"] {{ font-weight: 700; color: {T.AKSEN_TEAL_TUA}; }}
{_TOPBAR} .menu-isi .menu-pisah {{ margin: {T.SP_1} 0; }}
{_TOPBAR} .menu-isi form {{ margin: 0; }}
/* Keluar = tautan bahaya (teks merah), bukan tombol aksi utama. */
{_TOPBAR} .menu-isi .menu-keluar-st {{
  display: flex; align-items: center; width: 100%; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_3}; border: 0; border-radius: {T.RADIUS_KECIL};
  background: transparent; box-shadow: none; color: {T.AKSEN_KORAL_TUA}; cursor: pointer;
  font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE}; text-align: left;
}}
{_TOPBAR} .menu-isi .menu-keluar-st:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; opacity: .9; }}
{_TOPBAR} :is(a, button, summary):focus-visible {{
  outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px;
}}
@media (max-width: 36rem) {{
  {_TOPBAR} {{ flex-wrap: wrap; }}
  {_TOPBAR} .topbar-navigasi {{ flex-wrap: wrap; }}
}}
@media print {{
  {_TOPBAR} {{ display: none; }}
}}
"""
