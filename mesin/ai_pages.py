"""Halaman zero-JS pengaturan dan pemakaian AI untuk pengelola."""

from __future__ import annotations

import html
import os

import ai_policy
import ai_store
from teacher_pages import _halaman


def _usd(micro):
    return f"{int(micro) / 1_000_000:.2f}"


def halaman(path, *, pengguna, csrf, pesan="", galat=""):
    with ai_store.buka(path) as kon:
        utama, batas = ai_store.konfigurasi(kon)
        pakai = ai_store.ringkasan(kon)
        audit = kon.execute(
            "SELECT revisi,actor_id,field,lama,baru,dibuat FROM audit_konfigurasi ORDER BY id DESC LIMIT 20"
        ).fetchall()
    kabar = f'<div class="pesan">{html.escape(pesan)}</div>' if pesan else ""
    if galat:
        kabar += f'<div class="pesan galat" role="alert">{html.escape(galat)}</div>'
    key = "tersedia" if os.environ.get("DEEPSEEK_API_KEY", "").strip() else "belum tersedia"
    baris = []
    for fitur in ai_policy.FITUR:
        profil = ai_policy.profil(fitur)
        izin_server = ai_policy.deployment_mengizinkan(fitur)
        efektif = bool(batas[fitur]["aktif"] and izin_server and key == "tersedia" and not utama["dihentikan"])
        baris.append(
            f'<tr><td data-label="Fitur">{ai_policy.LABEL_FITUR[fitur]}</td>'
            f'<td data-label="Status efektif">{"Aktif" if efektif else "Tertahan"}</td>'
            f'<td data-label="Model">{html.escape(profil.model)}</td>'
            f'<td data-label="Pagu per hari">USD {_usd(batas[fitur]["batas_harian"])}</td>'
            f'<td data-label="Pagu per bulan">USD {_usd(batas[fitur]["batas_bulanan"])}</td>'
            f'<td data-label="Terpakai hari / bulan (USD)">{pakai[fitur]["harian"] / 1_000_000:.4f} / {pakai[fitur]["bulanan"] / 1_000_000:.4f}</td></tr>'
        )
    field_batas = []
    for fitur in ("global", *ai_policy.FITUR):
        label = "Global" if fitur == "global" else ai_policy.LABEL_FITUR[fitur]
        cek = "" if fitur == "global" else (
            f'<label><input type="checkbox" name="aktif_{fitur}" value="1" '
            f'{"checked" if batas[fitur]["aktif"] else ""}> Izinkan {html.escape(label)}</label>'
        )
        field_batas.append(
            f'<fieldset><legend>{html.escape(label)}</legend>{cek}'
            f'<label>Pagu harian (USD)<input name="harian_{fitur}" type="number" min="0" step="0.01" '
            f'value="{_usd(batas[fitur]["batas_harian"])}" required></label>'
            f'<label>Pagu bulanan (USD)<input name="bulanan_{fitur}" type="number" min="0" step="0.01" '
            f'value="{_usd(batas[fitur]["batas_bulanan"])}" required></label></fieldset>'
        )
    audit_html = "".join(
        f'<li>Revisi {a["revisi"]}: {html.escape(a["field"])} diubah oleh '
        f'{html.escape(a["actor_id"])}.</li>' for a in audit
    ) or "<li>Belum ada perubahan.</li>"
    isi = (
        '<header class="editorial-kepala-st"><p class="editorial-alis-st">RUANG PENGELOLA</p>'
        '<h1 id="judul-ai">Pengaturan AI</h1><p class="sub">Kesiapan, batas biaya, dan pemakaian panggilan Jagomat.</p></header>'
        + kabar
        + '<div class="kartu"><h2>Status layanan</h2>'
        f'<p>Credential: <strong>{key}</strong>. Provider: DeepSeek. Hard ceiling bulanan deployment: '
        f'<strong>USD {_usd(ai_policy.hard_ceiling_micro_usd())}</strong>.</p>'
        f'<p>Pagu global: <strong>USD {_usd(batas["global"]["batas_harian"])}/hari</strong> dan '
        f'<strong>USD {_usd(batas["global"]["batas_bulanan"])}/bulan</strong>.</p>'
        '<p>Biaya di halaman ini adalah perhitungan aplikasi, bukan tagihan provider.</p></div>'
        '<div class="kartu"><h2>Status dan pemakaian per fitur</h2><div class="tabel-wrap">'
        '<table><tr><th>Fitur</th><th>Status efektif</th><th>Model</th><th>Pagu/hari</th><th>Pagu/bulan</th><th>Terpakai hari/bulan (USD)</th></tr>'
        + "".join(baris) + '</table></div></div>'
        '<div class="kartu"><h2>Ubah batas pemakaian</h2>'
        '<form method="post" action="/admin/ai/pengaturan">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">'
        f'<input type="hidden" name="revisi" value="{utama["revisi"]}">'
        f'<label><input type="checkbox" name="dihentikan" value="1" {"checked" if utama["dihentikan"] else ""}>'
        ' Hentikan panggilan AI baru</label><p class="sub">Permintaan yang sudah dikirim mungkin tetap selesai dan dikenai biaya. Data belajar dan hasil lama tidak dihapus.</p>'
        + "".join(field_batas)
        + f'<label>Batas request per akun per hari<input name="request_akun_harian" type="number" min="0" value="{utama["request_akun_harian"]}" required></label>'
        f'<label>Batas tes per hari<input name="uji_harian" type="number" min="0" value="{utama["uji_harian"]}" required></label>'
        f'<label>Jeda tes (menit)<input name="uji_cooldown_menit" type="number" min="0" value="{utama["uji_cooldown_detik"] // 60}" required></label>'
        '<button type="submit" class="tombol-coral">Simpan pengaturan AI</button></form></div>'
        '<div class="kartu"><h2>Tes koneksi sintetis</h2><p>Pengujian mengirim pesan tetap tanpa data keluarga dan memakai kuota tes serta global.</p>'
        '<form method="post" action="/admin/ai/uji">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">'
        '<button type="submit" class="tombol-sekunder">Kirim tes sintetis</button></form></div>'
        f'<div class="kartu"><h2>Riwayat pengaturan</h2><ul>{audit_html}</ul></div>'
    )
    return _halaman(
        "Pengaturan AI", isi, ident=(pengguna, "admin"), stitch=True,
        kelas_bungkus="pendamping-editorial-st admin-editorial-st", id_utama="judul-ai",
    )
