"""CSS redesain /akun (fase 1: Akun saya dan Anak), tersekop `.akun-editorial-st`.

Hanya token dari design_tokens; font mengikuti `.akun-editorial-st` (sistem), tanpa
sumber luar. Dimuat oleh `teacher_shell._halaman` pada halaman akun saja.
"""
import design_tokens as T

_A = ".akun-editorial-st"

GAYA_AKUN = f"""
{_A} .akun-kepala-st {{ display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: {T.SP_4}; }}
{_A} .akun-kepala-st > div:first-child {{ flex: 1 1 18rem; min-width: 0; }}
{_A} .akun-aksi-kepala-st {{ display: flex; align-items: center; flex-wrap: wrap; gap: {T.SP_2}; }}
{_A} .akun-aksi-kepala-st .akun-form-keluar button {{
  min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA};
  border-radius: {T.RADIUS_KECIL}; background: transparent; color: {T.AKSEN_TEAL_TUA}; font-weight: 700;
}}
{_A} .akun-aksi-kepala-st .akun-form-keluar button:hover {{ background: {T.LATAR_SEKUNDER_NETRAL}; filter: none; }}
{_A} .akun-chip-st {{
  display: inline-flex; align-items: center; width: fit-content; padding: {T.SP_1} {T.SP_3};
  border-radius: {T.RADIUS_PIL}; background: {T.LATAR_SEKUNDER_NETRAL}; color: {T.TEKS_VARIAN};
  font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; line-height: 1.4; white-space: nowrap;
}}
{_A} .akun-grid-st {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
{_A} .akun-kolom-st {{ display: flex; flex-direction: column; gap: {T.SP_4}; min-width: 0; }}
{_A} .akun-kolom-st > .kartu-st {{ margin-bottom: 0; }}
{_A} .kartu-st {{ padding: {T.SP_5}; }}
{_A} .kartu-st > h2 {{ margin: 0 0 {T.SP_2}; }}
@media (min-width: {T.MULAI_DESKTOP}) {{
  {_A} .akun-grid-st {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: {T.SP_5}; align-items: start; }}
  {_A} .akun-grid-st:has(> .akun-kolom-st:only-child) {{ grid-template-columns: minmax(0, {T.LEBAR_KONTEN}); }}
}}
{_A} .akun-aksi-sandi {{ display: flex; align-items: center; flex-wrap: wrap; gap: {T.SP_2} {T.SP_4}; }}
{_A} .akun-aksi-sandi a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; font-weight: 600; }}
{_A} .akun-tombol-garis-st {{
  display: inline-flex; align-items: center; justify-content: center; min-height: {T.TINGGI_KONTROL};
  padding: 0 {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KECIL};
  background: transparent; color: {T.AKSEN_TEAL_TUA}; font-weight: 700; text-decoration: none;
}}
{_A} .akun-tombol-garis-st:hover {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
{_A} .akun-tombol-garis-st:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
{_A} .akun-anak-daftar {{ display: flex; flex-direction: column; gap: {T.SP_3}; margin-top: {T.SP_3}; }}
{_A} .akun-anak-kartu {{
  position: relative; padding: {T.SP_4}; background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU};
}}
{_A} .akun-anak-kartu:has(> .akun-kelola[open]) {{ border-color: {T.AKSEN_TEAL_TUA}; box-shadow: 0 0 0 {T.TEBAL_GARIS} {T.AKSEN_TEAL_TUA}; }}
{_A} .akun-anak-kepala {{ display: flex; align-items: center; gap: {T.SP_3}; min-height: 3.5rem; padding-right: 6.5rem; }}
{_A} .akun-inisial-st {{
  display: grid; place-items: center; flex: none; width: 3rem; height: 3.5rem; background: {T.LATAR_SEKUNDER_LEMBUT};
  color: {T.AKSEN_TEAL_TUA}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  font-size: 1.5rem; font-weight: 700; line-height: 1;
}}
{_A} .akun-anak-judul {{ min-width: 0; }}
{_A} .akun-anak-judul h3 {{ margin: 0; font-size: {T.UKURAN_BAGIAN_DEWASA}; line-height: 1.4; color: {T.TEKS_JUDUL}; overflow-wrap: anywhere; }}
{_A} .akun-anak-meta {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: {T.SP_1} 0 0; }}
{_A} .akun-anak-login {{ margin: {T.SP_1} 0 0; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; overflow-wrap: anywhere; }}
{_A} .akun-kelola > summary {{
  position: absolute; top: {T.SP_4}; right: {T.SP_4}; display: inline-flex; align-items: center; list-style: none;
  min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA};
  border-radius: {T.RADIUS_KECIL}; color: {T.AKSEN_TEAL_TUA}; font-weight: 700; cursor: pointer;
}}
{_A} .akun-kelola > summary::-webkit-details-marker {{ display: none; }}
{_A} .akun-kelola > summary:hover {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
{_A} .akun-kelola > summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
@media (max-width: {T.BATAS_HP}) {{
  {_A} .akun-anak-kepala {{ padding-right: 0; }}
  {_A} .akun-kelola > summary {{ position: static; justify-content: center; width: 100%; margin-top: {T.SP_3}; box-sizing: border-box; }}
}}
{_A} .akun-paket-kepala-st {{ display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: {T.SP_3}; }}
{_A} .akun-paket-kepala-st h2 {{ margin: {T.SP_1} 0 0; font-size: {T.UKURAN_JUDUL_DEWASA}; }}
{_A} .akun-paket-profil-st {{
  display: flex; align-items: center; flex-wrap: wrap; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; margin: 0;
  padding: {T.SP_2} {T.SP_4}; border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_SEKUNDER_LEMBUT};
}}
{_A} .akun-paket-profil-st a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; margin-left: auto; font-weight: 700; }}
{_A} .akun-catatan-st, {_A} .peringatan {{
  margin: 0; padding: {T.SP_3} {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_CATATAN}; color: {T.TEKS_UTAMA};
}}
{_A} .akun-langganan-st > :not(.akun-grid-st) {{ max-width: {T.LEBAR_KONTEN}; }}
{_A} fieldset {{ border: 0; padding: 0; margin: {T.SP_3} 0; }}
{_A} fieldset label {{ display: flex; align-items: center; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; font-size: 1rem; color: {T.TEKS_UTAMA}; }}
{_A} fieldset input[type=checkbox] {{ flex: none; width: 1.25rem; height: 1.25rem; accent-color: {T.AKSEN_TEAL_TUA}; }}
{_A} a.tombol {{
  display: inline-flex; align-items: center; justify-content: center; min-height: {T.TINGGI_KONTROL}; padding: 0 {T.SP_4};
  border: {T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KECIL}; color: {T.AKSEN_TEAL_TUA}; font-weight: 700; text-decoration: none;
}}
{_A} .tombol-bahaya-akun {{ min-height: {T.TARGET_SENTUH}; border-radius: {T.RADIUS_KECIL}; font-weight: 700; cursor: pointer; }}
{_A} .akun-baris-pilihan-st {{
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} 0; border-top: {T.TEBAL_GARIS} solid {T.BORDER_HALUS};
}}
{_A} .akun-label-st {{ flex: 1; min-width: 0; }}
{_A} .akun-chip-ok-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
{_A} .akun-tautan-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; font-weight: 600; }}
{_A} .akun-aksi-baris-st {{ display: flex; align-items: center; flex-wrap: wrap; gap: {T.SP_2} {T.SP_4}; }}
{_A} .akun-bahaya-st, {_A} .akun-bahaya-kartu-st {{
  margin-top: {T.SP_2}; padding: {T.SP_1} {T.SP_4} {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_GALAT};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_GALAT};
}}
{_A} .akun-bahaya-kartu-st {{ padding: {T.SP_4}; }}
{_A} .akun-bahaya-kartu-st h2, {_A} .akun-bahaya-st > summary {{ color: {T.TEKS_GALAT}; }}
{_A} .akun-bahaya-st > summary, {_A} .kartu-st > summary {{
  min-height: {T.TARGET_SENTUH}; display: list-item; cursor: pointer; font-weight: 600;
}}
{_A} .kartu-st > summary {{ color: {T.AKSEN_TEAL_TUA}; }}
{_A} .akun-status-data-st {{ background: {T.LATAR_TERSIMPAN}; border-color: {T.BORDER_TERSIMPAN}; }}
{_A} .akun-status-data-st h2 {{ margin-bottom: {T.SP_1}; }}
{_A} .akun-opsi-st {{ display: flex; align-items: flex-start; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; padding: {T.SP_3} 0; border-top: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; }}
{_A} .akun-opsi-st input {{ flex: none; width: 1.5rem; height: 1.5rem; margin: 2px 0 0; accent-color: {T.AKSEN_TEAL_TUA}; }}
{_A} .akun-opsi-st label {{ display: flex; flex-direction: column; gap: {T.SP_1}; flex: 1; cursor: pointer; }}
{_A} .akun-opsi-judul-st {{ font-weight: 700; }}
{_A} .akun-opsi-isi-st {{ font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
{_A} .akun-pilihan-data .sub, {_A} .akun-status-data-st .sub {{ margin: {T.SP_2} 0 0; }}
{_A} .akun-status-data-st .sub {{ margin-top: 0; }}
{_A} details.kartu-st {{ padding-block: {T.SP_1}; }}
{_A} .akun-bahaya-st:not([open]) {{ padding-bottom: {T.SP_1}; }}
{_A} .akun-kelola-tutup {{ display: none; }}
{_A} .akun-kelola[open] .akun-kelola-tutup {{ display: inline; }}
{_A} .akun-kelola[open] .akun-kelola-buka {{ display: none; }}
{_A} .akun-kelola-isi {{ display: flex; flex-direction: column; gap: {T.SP_4}; margin-top: {T.SP_4}; padding-top: {T.SP_4}; border-top: {T.TEBAL_GARIS} solid {T.BORDER_HALUS}; }}
{_A} .akun-kelola-bagian .akun-form-sandi button {{ align-self: flex-start; }}
{_A} .akun-kelola-bagian h4 {{ margin: 0 0 {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_JUDUL}; }}
"""
