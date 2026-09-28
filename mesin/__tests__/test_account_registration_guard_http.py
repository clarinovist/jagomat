"""HTTP hapus login akun: guard receipt registrasi fail-closed (409 tanpa efek)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json as _json

import auth  # noqa: E402
from test_admin_http_c import server, _minta, _login, _hidden, SANDI_ADMIN  # noqa: E402


def test_hapus_login_guru_terikat_registrasi_ditolak_409_tanpa_efek(server):
    """Akun guru ber-intent registrasi tidak boleh dihapus: 409 dengan auth/DB
    utuh; hanya jurnal operasi yang mencatat percobaan."""
    token = _login(server, "Admin-C", SANDI_ADMIN)
    target = auth.cari_akun("Ortu-C")
    assert target is not None
    raw = _json.loads(auth.BERKAS_SANDI.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and "akun" in raw
    raw["registrasi_profil"] = {
        "operasi_registrasi_http": {
            "versi": 1, "target_id": "candidate_" + "e" * 32,
            "akun_id": target["id_akun"], "siswa_id": 9, "sequence_awal": 8,
            "sidik_perintah": "a" * 64, "alias_sidik": "b" * 64,
            "profil_sidik": "c" * 64, "status": "selesai", "dibuat": 9,
            "kredensial": auth.buat_hash("sandi-sintetis-http"),
        }
    }
    auth.BERKAS_SANDI.write_text(_json.dumps(raw), encoding="utf-8")
    sebelum = auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes()
    _, review, _ = _minta(
        server, "/admin/tinjau?aksi=account_login_delete&id=" + target["id_akun"], cookie=token,
    )
    kode, _, _ = _minta(server, "/admin/akun", cookie=token, data={
        "aksi": "account_login_delete", "csrf": _hidden(review, "csrf"),
        "tinjauan": _hidden(review, "tinjauan"), "reauth": SANDI_ADMIN,
        "konfirmasi": "1",
    }, headers={"Origin": server.alamat})
    assert kode == 409
    assert sebelum == (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes())
    assert auth.cari_akun("Ortu-C") is not None
