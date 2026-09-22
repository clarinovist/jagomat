"""Pilih CI lengkap kecuali seluruh delta push berupa dokumen aman eksplisit."""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


# Bukan wildcard *.md: kontrak domain/runbook dan preset eksekusi tetap lengkap.
# Panduan agent bukan input runtime/build; review maknanya tetap wajib.
DOKUMEN_AMAN = frozenset({
    "README.md", "docs/README.md", "docs/ci-selective.md", "CLAUDE.md",
})
SHA = re.compile(r"[0-9a-f]{40}")
TAUTAN = re.compile(r'!?\[[^\]\n]*\]\(([^()\s]+)(?:\s+"[^"\n]*")?\)')


def _git(akar, *argumen):
    """Baca metadata Git tanpa shell, isi dokumen, atau log nama berkas."""
    return subprocess.run(
        ["git", "-C", str(akar), *argumen], check=True,
        capture_output=True, timeout=30,
    ).stdout


def pilih_jalur(akar, nama_event, event, revisi):
    """Kembalikan lengkap/alasan/path; ketidakpastian tidak boleh menjadi skip."""
    if nama_event != "push":
        return True, "Manual atau event lain selalu lengkap.", ()
    if not isinstance(event, dict):
        return True, "Metadata push tidak valid.", ()
    sebelum, sesudah = event.get("before"), event.get("after")
    if (event.get("ref") != "refs/heads/main" or event.get("forced") is not False
            or not all(isinstance(x, str) and SHA.fullmatch(x)
                       and x != "0" * 40 for x in (sebelum, sesudah))
            or sesudah != revisi):
        return True, "Rentang push tidak dapat dipastikan.", ()
    try:
        if _git(akar, "rev-parse", "HEAD").decode("ascii").strip() != sesudah:
            return True, "Checkout tidak sama dengan revisi event.", ()
        _git(akar, "merge-base", "--is-ancestor", sebelum, sesudah)
        # Seluruh push, bukan HEAD^ atau daftar commits payload yang dapat terpotong.
        # Rename menjadi delete+add: path asal tidak boleh tersembunyi.
        mentah = _git(akar, "diff", "--name-only", "--no-renames", "-z",
                      sebelum, sesudah, "--")
        daftar = tuple(x for x in mentah.decode("utf-8").split("\0") if x)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return True, "Riwayat Git tidak tersedia atau tidak linier.", ()
    if not daftar or not all(nama in DOKUMEN_AMAN for nama in daftar):
        return True, "Delta kosong atau memuat berkas di luar daftar dokumen aman.", ()
    return False, "Seluruh delta push merupakan dokumen aman.", daftar


def periksa_dokumen(akar, daftar):
    """Periksa UTF-8, konflik merge, dan target tautan inline lokal yang tersisa.

    Tidak mengakses jaringan, memvalidasi anchor, atau menilai makna dokumen.
    Penghapusan dokumen sah; symlink bukan dokumen teks biasa.
    """
    akar = akar.resolve()
    for nama in daftar:
        if nama not in DOKUMEN_AMAN:
            raise ValueError("Dokumen tidak termasuk daftar aman.")
        path = akar / nama
        if path.is_symlink():
            raise ValueError("Dokumen aman tidak boleh berupa symlink.")
        if not path.exists():
            continue
        teks = path.read_text(encoding="utf-8")
        if "\0" in teks or re.search(r"^(?:<{7}|={7}|>{7})(?: |$)", teks, re.M):
            raise ValueError("Dokumen bukan teks bersih atau berisi konflik merge.")
        for target in TAUTAN.findall(teks):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            tujuan = (path.parent / unquote(url.path)).resolve()
            if akar not in (tujuan, *tujuan.parents) or not tujuan.exists():
                raise ValueError("Target tautan lokal dokumen tidak tersedia di repo.")


def utama(akar):
    """Tulis output boolean tetap; jangan menyalin event/path ke log Actions."""
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        event = None
    lengkap, alasan, daftar = pilih_jalur(
        akar, os.environ.get("GITHUB_EVENT_NAME", ""), event,
        os.environ.get("GITHUB_SHA", ""),
    )
    if not lengkap:
        try:
            periksa_dokumen(akar, daftar)
        except (OSError, ValueError):
            print("Pemeriksaan dokumen gagal; CI ditahan.")
            return 1
    nilai = str(lengkap).lower()
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write("lengkap=" + nilai + "\n")
    ringkasan = "Jalur CI: " + ("lengkap" if lengkap else "dokumen aman") + ". " + alasan
    print(ringkasan)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write("## Pemilihan pemeriksaan\n\n" + ringkasan + "\n")
            if not lengkap:
                output.write("Tidak membuat image atau bukti kelayakan rilis.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(utama(Path(__file__).resolve().parents[1]))
