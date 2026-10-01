"""Server preview soft launch dengan seluruh state sintetis dan terisolasi."""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

import admin_bulk
import admin_registration
import admin_store
import admin_students
import ai_store
import assistant_schema
import auth
import database
import sessions
import support_settings


def siapkan(*, akar=None):
    akar = Path(tempfile.mkdtemp(prefix="jagomat-launch-preview-") if akar is None else akar).resolve()
    akar.mkdir(mode=0o700, parents=False, exist_ok=True)
    akar.chmod(0o700)
    if any(akar.iterdir()):
        raise ValueError("direktori preview harus baru dan kosong")
    paths = {
        "belajar": akar / "latihan.db", "auth": akar / "sandi.json",
        "admin": akar / "admin-control.db", "ai": akar / "ai-control.db",
        "pendamping": akar / "pendamping.db", "sesi": akar / "sesi.json",
    }
    admin_store.BAWAAN = paths["admin"]
    auth.BERKAS_SANDI = paths["auth"]
    database.BAWAAN = paths["belajar"]
    ai_store.BAWAAN = paths["ai"]
    assistant_schema.BAWAAN = paths["pendamping"]
    sessions.BERKAS_SESI = paths["sesi"]
    os.environ["ADMIN_TRANSIENT_DB"] = str(akar / "admin-drafts.db")
    os.environ["AI_BERKAS_DB"] = str(paths["ai"])
    os.environ["PENDAMPING_BERKAS_DB"] = str(paths["pendamping"])

    kini = int(time.time())
    admin_store.siapkan(paths["admin"], sekarang=kini)
    admin_bulk.siapkan_transient(Path(os.environ["ADMIN_TRANSIENT_DB"]))
    support_settings.migrasikan(paths["admin"], sekarang=kini)
    database.siapkan(paths["belajar"])
    admin_students.siapkan(paths["belajar"])
    admin_registration.migrasikan_profil_registrasi(paths["belajar"])
    ai_store.siapkan(paths["ai"], sekarang=kini)
    assistant_schema.siapkan(paths["pendamping"])
    sandi_admin = secrets.token_urlsafe(18)
    auth.simpan_sandi(sandi_admin, "admin-preview", path=paths["auth"])
    auth.pastikan_admin(paths["auth"])
    data = json.loads(paths["auth"].read_text(encoding="utf-8"))
    if "akun" in data:
        data["akun"][0]["peran"] = "admin"
    else:
        data["peran"] = "admin"
    paths["auth"].write_text(json.dumps(data), encoding="utf-8")
    paths["auth"].chmod(0o600)

    from web import Penangan
    class PenanganPreview(Penangan):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), PenanganPreview)
    return server, akar, sandi_admin


def utama():
    server, akar, sandi = siapkan()
    (akar / "login-preview.json").write_text(
        json.dumps({"pengguna": "admin-preview", "sandi": sandi}), encoding="utf-8")
    (akar / "login-preview.json").chmod(0o600)
    print("Preview akses awal: http://127.0.0.1:%d/" % server.server_address[1], flush=True)
    print("State sintetis privat:", akar, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(utama())
