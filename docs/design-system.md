# Design System — OSN Mesin Latihan

Sumber tunggal untuk semua nilai visual aplikasi. Implementasi ada di
`mesin/design_tokens.py`; dokumen ini adalah referensi naratif.

Mockup UI/UX (9 halaman) ada di arsip lokal `../../osn-resources/referensi/desain-ui/`. Generator: `gen_guru.py`
(gpt-image-2 via chenzk.top).

## Satu palet hangat (restyle 29 Agu 2026)

Sejak restyle, seluruh permukaan — guru, murid, dan lembar cetak — memakai
SATU palet hangat dari mockup. Keputusan ini diambil karena mockup guru
(guru-*.png) semuanya dibangkitkan dengan palet yang sama dengan murid
(cream + teal + coral + amber), sehingga memisahkan dua palet justru
membuat halaman guru tidak cocok dengan desain yang sudah disetujui.

### Palet INTI (biru tua #16213e + abu #f0f1f4)

Dipakai di: dashboard, sesi, laporan, akun, lembar cetak (5 mockup guru).

| Token | Nilai | Konteks |
|-------|-------|---------|
| LATAR_INTI | #f0f1f4 | Badan halaman, abu muda netral |
| LATAR_KARTU | #fff | Kartu soal, identitas |
| LATAR_KARTU_SEKUNDER | #eef3fb | Petunjuk, kartu interaktif |
| TEKS_UTAMA | #111 | Body text |
| TEKS_JUDUL | #16213e | Heading, border, judul — biru tua |
| TEKS_SUBTLE | #555 | Label, meta |
| BORDER_HALUS | #d5d8de | Border kartu |
| BORDER_INTERAKTIF | #c4d3ea | Border petunjuk |
| LATAR_CATATAN | #fff7e6 | Catatan bagian |
| BORDER_CATATAN | #ecd9a8 | Border catatan |
| BINTANG | #b8860b | Challenge star (legacy gold) |

Filosofi: biru tua (#16213e) sebagai warna otoritas — guru butuh konsentrasi,
bukan semangat. Netral, terbaca lama, tidak melelahkan mata.

> CATATAN (29 Agu 2026): token di atas masih ada untuk kompatibilitas dan
> sebagai warna judul/teks/garis cetak, TETAPI bukan lagi palet latar default.
> Foto yang benar: lihat bagian "Palet MURID" di bawah — semua halaman kini
> berlatar LATAR_MURID (cream). Biru tua tersisa sebagai TEKS_JUDUL.

### Palet MURID (permukaan semua halaman)

Dipakai di: /murid, /murid/kerjakan (2 mockup murid) DAN semua halaman guru
+ lembar cetak. Ini palet latar default seluruh aplikasi sejak restyle.

| Token | Nilai | Konteks |
|-------|-------|---------|
| LATAR_MURID | #FFF8EE | Cream hangat — badan halaman (guru & murid) |
| AKSEN_MURID_UTAMA | #0FA3A3 | Teal — primary action, nomor badge |
| AKSEN_MURID_KORAL | #FF6B5B | Coral — tombol simpan/CTA, headline kunci |
| AKSEN_MURID_AMBER | #FFB020 | Amber — star/challenge, tombol variasi cerita |
| LATAR_KARTU_MURID | #fff | Kartu soal |

Filosofi: hangat dan cerah untuk anak SD — dan, sesuai mockup, juga yang
dipakai permukaan guru. Teal sebagai aksen utama (bukan biru tua) karena lebih
ramah dan menos intimidating. Coral untuk CTA supaya menonjol dari teal.

### Status (diagnosis)

Dari mockup guru-laporan, untuk diagram tren dan diagnosis.

| Token | Nilai | Status |
|-------|-------|--------|
| STATUS_KUAT | #0FA3A3 | Teal — kuat |
| STATUS_LEMAH | #FFB020 | Amber — lemah |
| STATUS_SALAH | #FF6B5B | Coral — salah konsep |

## Tipografi

| Token | Nilai | Konteks |
|-------|-------|---------|
| FONT_LAYAR | -apple-system, "Segoe UI", Roboto, ... | Semua permukaan layar |
| FONT_CETAK | "Helvetica Neue", Arial, sans-serif | Lembar cetak A4 |
| UKURAN_BADAN_LAYAR | 16px | Body text layar |
| UKURAN_BADAN_CETAK | 10.5pt | Body text cetak |
| LINE_HEIGHT | 1.55 | Spacing baris |

Tidak ada font custom/webfont — pakai system stack supaya tidak ada loading
delay dan konsisten di semua device. Rounded sans-serif (terlihat di mockup)
tercapai via system font di Apple/Windows.

## Spacing

Skala 4px base, ratio 1.5x:

| Token | rem | px | Penggunaan |
|-------|-----|----|------------|
| SP_1 | 0.25rem | 4px | Gap mini |
| SP_2 | 0.5rem | 8px | Padding dalam, gap |
| SP_3 | 0.75rem | 12px | Padding kartu |
| SP_4 | 1rem | 16px | Default padding, margin |
| SP_5 | 1.5rem | 24px | Margin section |
| SP_6 | 2rem | 32px | Margin besar |

## Radius

| Token | Nilai | Konteks |
|-------|-------|---------|
| RADIUS_KARTU | 12px | Kartu soal |
| RADIUS_SEDANG | 10px | Petunjuk, identitas |
| RADIUS_KECIL | 8px | Catatan, input |
| RADIUS_PIL | 999px | Pilihan cara, badge |
| RADIUS_BULAT | 50% | Nomor badge (lingkaran) |

## Touch target

| Token | Nilai | Sumber |
|-------|-------|--------|
| TARGET_SENTUH | 44px | WCAG 2.5.5 — minimum untuk layar sentuh |
| LEBAR_KONTEN | 46rem | Max-width konten layar |

## Komponen patterns

Dari 9 mockup, pattern yang berulang:

1. **Kartu** — kontainer dasar: background putih/cream, border halus,
   radius 12px, padding 1rem, shadow halus. Dipakai di soal, petunjuk,
   identitas, stat cards, session cards.

2. **Nomor badge** — lingkaran dengan angka, border 2px teal (murid) atau
   biru tua (guru). Min 2rem x 2rem.

3. **Pill / badge** — border-radius 999px, padding .55rem .9rem,
   min-height 44px (touch target). Dipakai di pilihan "Caraku", badge soal,
   badge status.

4. **Btn (primary)** — background teal/coral (murid) atau biru tua (guru),
   text putih, border-radius 9px, padding .7rem 1.2rem.

5. **Btn (secondary)** — background abu muda, text biru tua, border halus.

6. **Sticky simpan bar** — position sticky bottom, background warna latar,
   button full-width coral. Hanya di halaman kerja murid.

7. **Tabel** — border-collapse, th background #eef/#eee, td border halus.
   Dipakai di dashboard (sesi), lembar penilaian (kunci), rekap.

## Viewport

| Viewport | Halaman | Orientasi mockup |
|----------|---------|-----------------|
| Mobile portrait | /murid, /murid/kerjakan | 1024x1536 |
| Desktop landscape | /, /masuk, /sesi, /laporan, /akun | 1536x1024 |
| A4 portrait | /lembar, /lembar/penilaian | 1024x1536 |

Halaman murid adalah mobile-first — di desktop, layout sama tapi column
di-tengah (max-width 46rem). Tidak perlu layout desktop terpisah.

## Cara pakai tokens di kode

```python
import design_tokens as T

# CSS string pakai f-string, escape {} jadi {{ }}
CSS = f"""
.soal {{
  background: {T.LATAR_KARTU};
  border-radius: {T.RADIUS_KARTU};
}}
"""
```

Aturan:
- Ubah nilai visual di `design_tokens.py`, bukan di file CSS.
- Jangan hardcode hex literal di file CSS — selalu rujuk token.
- Token baru tambahkan ke `design_tokens.py` + catat di dokumen ini.

### Token Figma v2 (sinkron 2026-09-25)

Sumber: file desain "Jagomat · Sistem Desain & Pilot UI" (pilot 25 Sep 2026,
arsip di `osn-resources/referensi/desain-ui/figma-pilot-2026-09-25/`). Hanya
nilai yang belum ada yang ditambahkan; padanan lama tetap dipakai apa adanya
(cream = `LATAR_MURID`, teal-strong = `AKSEN_TEAL_TUA`, radius/lg 12 =
`RADIUS_KARTU`, radius/pill = `RADIUS_PIL`, size/touch-min 44 = `TARGET_SENTUH`).

| Token | Nilai | Asal di Figma |
|-------|-------|---------------|
| `AKSEN_KORAL_HOVER` / `AKSEN_TEAL_HOVER` | `#ba3c2d` / `#0b7477` | `action/primary-hover`, `action/secondary-hover` |
| `LATAR_TOOLTIP` / `TEKS_TOOLTIP` | `#16213e` / `#ffffff` | `bg/tooltip`, `text/tooltip` — balon pola "ⓘ" |
| `RADIUS_KARTU_BESAR` | `22px` | `radius/card` |
| `TINGGI_KONTROL` / `TINGGI_CTA` | `48px` / `52px` | `size/control`, `size/cta` |
| `UKURAN_IKON` | `24px` | `size/icon` |
| `TEBAL_GARIS` / `TEBAL_FOKUS` | `1px` / `2px` | `border/width`, `border/focus-width` |
| `SP_7` / `SP_8` | `3rem` / `4rem` | `space/3xl`, `space/4xl` |

Token di tabel ini **belum dipakai CSS mana pun**. Sinkron ini hanya menyamakan
nama antara desain dan kode, bukan mengubah tampilan; penerapannya (mis. radius
kartu 22 atau tinggi CTA 52) menyusul lewat jalur Normal terpisah agar
perubahan tampilan bisa direview sendiri.

File CSS per permukaan (semuanya `import design_tokens as T`):
- `teacher_style.py` → 5 halaman layar guru (masuk, dashboard, sesi, laporan, akun)
- `screen_style.py` → lembar yang dibaca di browser/HP (anak & guru)
- `print_style.py` → lembar kertas A4 (satuan mm/pt, hemat tinta: garis saja)
- `student_pages.py` (CSS_MURID) → halaman murid

## Mockup reference

| File | Halaman | Viewport | Implementasi |
|------|---------|----------|--------------|
| murid-sesiku.png | /murid — daftar sesi | Mobile | student_pages.py |
| murid-kerjakan.png | /murid/kerjakan — halaman kerja | Mobile | student_pages.py |
| guru-masuk.png | /masuk — login | Desktop | web.py + teacher_style.py |
| guru-dashboard.png | / — dashboard utama | Desktop | teacher_pages.py + teacher_style.py |
| guru-sesi.png | /sesi/<id> — detail sesi | Desktop | teacher_pages.py + teacher_style.py |
| guru-laporan.png | /laporan/<id> — laporan + tren | Desktop | reports.py + teacher_style.py |
| guru-akun.png | /akun — kelola akun & siswa | Desktop | account_pages.py + teacher_style.py |
| guru-lembar-soal.png | /lembar/<id> — soal cetak | A4 | render.py + print_style.py |
| guru-lembar-kunci.png | /lembar/<id>/penilaian — kunci cetak | A4 | render.py + print_style.py |

Kontrak penting: implementasi lembar anak (`/lembar/<id>`) TIDAK boleh memuat
kunci; lembar kunci (`/lembar/<id>/penilaian`) justru memuat semuanya. Keduanya
hanya beda satu ruas URL — dijaga `__tests__/test_web_worksheet.py`.

## Workflow: halaman baru

1. Tentukan jalur risiko menurut `../CLAUDE.md`; halaman/alur baru minimal Normal,
   perubahan akses/data tetap Kritis. Mockup baru hanya bila desainnya membutuhkan
   keputusan visual, bukan syarat setiap typo atau perubahan gaya lokal.
2. Ekstrak nilai visual baru ke `design_tokens.py` (jika ada).
3. Implementasi HTML/CSS di file yang sesuai, rujuk tokens.
4. Perbarui referensi desain bila relevan; mockup tetap lokal di `osn-resources/referensi`.
5. Render dan cek visual dengan data/profil sintetis sesuai `workflow-reference.md`.
   Jalankan scoped test markup/style dan gate jalur di `../CLAUDE.md`; full suite
   mengikuti risiko/trigger, bukan otomatis untuk semua perubahan tampilan.
