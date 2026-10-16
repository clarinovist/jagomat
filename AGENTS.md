# AGENTS.md — Jagomat

Baca `CLAUDE.md` sebagai panduan utama workflow, arsitektur, domain, privasi anak,
gate verifikasi, Git, dan produksi. Instruksi workspace induk tetap berlaku.

## Codemode — routing adaptif

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
