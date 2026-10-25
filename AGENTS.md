# AGENTS.md — Jagomat

Baca `CLAUDE.md` sebagai panduan utama workflow, arsitektur, domain, privasi anak,
gate verifikasi, Git, dan produksi. Instruksi workspace induk tetap berlaku.

## Runner dan batas rilis

- Jika tersedia, baca kebijakan workspace `../AGENTS.md`. Commit lokal dulu;
  push/deploy perlu izin eksplisit. Izin push tidak mencakup deploy; jika push
  memicu auto-deploy, izin deploy harus ada sebelum push.
- Dalam Hermes, kerjakan langsung di sesi yang sama. CommandCode tidak aktif;
  jangan otomatis menjalankan CLI/API, login, atau smoke-test CommandCode.
- Worker/reviewer tambahan hanya setelah persetujuan atas runner, model, scope,
  dan biaya yang relevan; verifikasi akses sebelum tugas nyata. Jangan otomatis
  berpindah CLI atau mengaktifkan delegasi bawaan. Review sendiri adalah
  self-review, bukan review independen; gate dan bukti nyata tetap wajib.
- Gunakan tool yang tersedia pada runner aktif. Di luar Pi, jangan mengasumsikan
  adanya `codemode`, `bash`, atau ekstensi Pi. Payload kompleks tetap file-backed;
  call independen boleh paralel, mutasi bergantung berurutan, exit status diperiksa.

## Codemode — khusus Pi

Bagian berikut berlaku hanya ketika berjalan di Pi dengan `codemode` tersedia.
Di Hermes gunakan tool native sesi; jangan memasang Pi hanya untuk mengikuti resep ini.

- Gunakan `codemode` hanya bila manfaatnya material: minimal dua tool call independen,
  loop/filter/agregasi, output besar yang perlu diringkas, atau chaining sederhana.
  Untuk satu `read`, `bash`, `edit`, atau `write` trivial, panggil tool langsung.
- Repo ini punya banyak Python/shell/SQLite/SSH. Payload heredoc, SQL multi-statement,
  Markdown/code fence, SSH→SQLite/DB, atau nested quoting wajib **file-backed**:
  `write` file sementara → `read`/inspect → `bash` menjalankan file. Jangan menanam
  payload kompleks sebagai string JavaScript codemode inline.
- Setelah satu parse failure (`SyntaxError`, `unterminated string`, atau tidak ada tool
  call karena parse gagal), jangan retry inline kompleks. Beralih ke direct tool atau
  file-backed path dan pastikan apakah call sebelumnya sudah menimbulkan side effect.
- Call bergantung dan mutasi harus berurutan. Untuk produksi/data:
  target + backup → read-only preview/dry-run → apply atomic → verifikasi read-only.
  Hanya call yang benar-benar independen yang boleh diparalelkan.
- Periksa setiap hasil `bash`: `exit_code`, `truncated`, dan `full_output_path`.
  Expected-nonzero harus dinyatakan eksplisit; jangan menyembunyikan kegagalan lewat
  pipeline atau `; echo $?`. Gunakan `set -euo pipefail` bila tepat.
- Personal quality guard (`~/.pi/agent/codemode-quality/extension.ts`) melakukan syntax
  preflight, memblokir inline payload kompleks, dan menambahkan diagnostic terstruktur.
  Playbook dan helper canonical ada di `~/.pi/agent/docs/codemode-playbook.md`.
- Jangan mengirim data anak, sandi/sesi, DB/backup, atau artefak privat ke model/tool
  eksternal. Untuk evaluasi gunakan data sintetis dan output agregat sesuai `CLAUDE.md`.
