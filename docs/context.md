# Jagomat — Konteks teknis ringkas

> Peta orientasi ±1 halaman; baca [spec.md](spec.md) untuk kontrak produk.
> [CLAUDE.md](../CLAUDE.md) tetap acuan palang dan workflow; status produksi diperiksa terpisah.
> Wajib disinkronkan saat arsitektur/struktur/konvensi/keputusan teknis berubah,
> dalam perubahan yang sama; tetap ±1 halaman. Aturan: [sinkronisasi ringkasan](../CLAUDE.md#jaga-ringkasan-proyek-tetap-sinkron).

## Arsitektur

**Monolit Python stdlib, HTML dirender server, penyimpanan SQLite.**
`serve.py` menjalankan server HTTP; `web.py` mengatur rute dan palang akses.
Nama modul di bawah relatif terhadap `mesin/`, bukan direktori baru.

| Lapisan | Modul dan tanggung jawab |
| --- | --- |
| Identitas | `auth.py`, `sessions.py`: akun dan sesi login; `students.py`: data anak |
| Soal | `topics.py` + `topic_*.py`: topik; `generator.py`: pembangkitan; `templates.py`: kontrak soal |
| Penyajian | `render.py`, `worksheets.py`, `*_pages.py`, `*_ui.py`: HTML, lembar dan layar |
| Data | `database.py`, `schema.py`, `*_store.py`, `*_schema.py`: penyimpanan dan migrasi |
| Belajar | `diagnosis.py`, `learning_cycle.py`, `learning_cycle_service.py`: diagnosis, reducer murni, orkestrasi |
| Laporan | `reports.py`, `report_*.py`, `mastery_*.py`: laporan dan penguasaan berbasis bukti |
| Layanan lain | `assistant_*`/`ai_*`: Pendamping; `subscription_*`/`midtrans_*`: langganan/pembayaran; `admin_*`: pengelola |

Alur domain: topik → generator/kontrak soal → penyajian → hasil tersimpan →
tinjauan/diagnosis → bukti terkonfirmasi → reducer siklus → rekomendasi/laporan.
`learning_cycle.py` sumber tunggal status/rekomendasi; reducer tidak menulis DB.

## Struktur folder

```text
jagomat/                  # repo Git luar, branch kanonis main
├── mesin/                # modul aplikasi, Dockerfile, alat operasional
│   ├── __tests__/        # pytest dan fixture sintetis
│   ├── aset/             # aset runtime
│   └── cadangan/         # privat/lokal, tidak dilacak
├── scripts/              # palang repo, otomasi CI dan rilis
├── docs/                 # spesifikasi, keputusan, runbook
│   └── plan/             # rencana kerja lokal/gitignored
├── .github/workflows/    # CI, build, pemasangan
└── CLAUDE.md             # aturan pengembangan lengkap
```

Riset/materi/mockup: `../osn-resources/referensi/`, lokal di luar repo; bukan
kebutuhan runtime/test/build. `.venv`, DB, kredensial, cache dan cadangan tetap privat.

## Konvensi dan keputusan penting

- **Stdlib saja**, tanpa framework/dependensi runtime pihak ketiga; dev dependency
  hanya `pytest` dan `pytest-xdist`. Dependency baru perlu persetujuan pengguna.
- **Zero-JS default**: `<details>` dan `?section=` server-side. Pengecualian disetujui:
  mata sandi, `confirm()` destruktif, Kirim/Periksa Pendamping inline dengan CSP,
  same-origin dan fallback form; bukan izin menambah JS umum.
- Nama modul Inggris; fungsi/variabel, docstring, UI dan commit Bahasa Indonesia.
  Commit conventional (`fix(murid): …`). Nilai visual melalui `design_tokens.py`
  (`T.*`); jangan hardcode hex di modul lain. Satu aksi, satu entry point.
- Kunci/diagnosis tetap deterministik; `llm.py` hanya memparafrase kalimat soal.
  Pendamping tidak boleh mengambil alih reducer atau konfirmasi bukti belajar.
- Lokal memakai `mesin/.venv/bin/python` (3.9.6); CI/container 3.12. Kode kompatibel
  3.9. Verifikasi sesuai risiko: Ringan/Normal/Kritis; tes scoped lokal, gate berat
  di CI. Palang index: `mesin/.venv/bin/python scripts/check_repo.py` setelah stage.
- Git selalu `git -C /Users/nugroho/Documents/jagomat …`; hindari repo basi
  `mesin/.git`, jaga WIP sesi lain. Repo `clarinovist/jagomat`; domain `jagomat.id`.
- Image tetap `ghcr.io/clarinovist/osn-mesin-latihan` demi kompatibilitas recovery.
  Rilis mengikuti **uji → bangun → pasang**, artifact/digest yang sama. CI hijau
  bukan bukti pemasangan; jangan build di VPS atau otomatis menyalakan Docker lokal.

Detail: [workflow](workflow-reference.md) · [design system](design-system.md) ·
[CI selektif](ci-selective.md) · [rilis produksi](production-release.md) ·
[penamaan repo](repository-naming.md). Ringkasan ini bukan izin mengubah palang.
