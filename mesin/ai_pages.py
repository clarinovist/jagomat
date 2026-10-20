"""Halaman zero-JS pengaturan dan pemakaian AI untuk pengelola."""

from __future__ import annotations

import html
import os

from teacher_style import SKRIP_MATA_SANDI

import ai_policy
import ai_store
import ai_service
import admin_pages
import admin_labels as L


def _usd(micro):
    return f"{int(micro) / 1_000_000:.2f}"


def _uang(micro, presisi=2):
    return format(int(micro) / 1_000_000, '.%df' % presisi).replace('.', ',')


def _kartu_status(ada_key, batas):
    kunci = ('<span class="admin-badge bien">Tersedia</span>' if ada_key
             else '<span class="admin-badge perhatian">Belum tersedia</span>')
    return (
        '<section class="admin-kartu"><h2>Status layanan</h2><dl class="admin-ai-status">'
        f'<div><dt>Kredensial</dt><dd>{kunci}</dd></div>'
        '<div><dt>Provider</dt><dd><strong>DeepSeek</strong></dd></div>'
        '<div><dt>Batas keras bulanan deployment</dt>'
        f'<dd><strong>USD {_uang(ai_policy.hard_ceiling_micro_usd())}</strong></dd></div>'
        '<div><dt>Pagu global</dt>'
        f'<dd><strong>USD {_uang(batas["global"]["batas_harian"])}/hari</strong> dan '
        f'<strong>USD {_uang(batas["global"]["batas_bulanan"])}/bulan</strong></dd></div></dl>'
        '<p class="admin-meta">Periode mengikuti WIB. Pagu 0 berarti tidak diizinkan. '
        'Izin admin tidak menggantikan izin deployment atau persetujuan keluarga.</p>'
        '<p class="admin-meta">Biaya di halaman ini adalah perhitungan aplikasi, bukan tagihan provider.</p></section>'
    )


def _baris_fitur(fitur, batas, pakai):
    profil = ai_policy.profil(fitur)
    efektif, alasan = ai_service.status_fitur(fitur)
    if batas[fitur]["batas_harian"] == 0 or batas[fitur]["batas_bulanan"] == 0:
        efektif = False
        alasan.append("pagu nol")
    status = ('<span class="admin-badge bien">Aktif</span>' if efektif else
              f'<span class="admin-badge perhatian">{html.escape("Tertahan: " + ", ".join(alasan))}</span>')
    return (
        f'<tr><td data-label="Fitur"><strong>{ai_policy.LABEL_FITUR[fitur]}</strong></td>'
        f'<td data-label="Status efektif">{status}</td>'
        f'<td data-label="Model"><code>{html.escape(profil.model)}</code></td>'
        f'<td data-angka data-label="Pagu per hari">USD {_uang(batas[fitur]["batas_harian"])}</td>'
        f'<td data-angka data-label="Pagu per bulan">USD {_uang(batas[fitur]["batas_bulanan"])}</td>'
        f'<td data-angka data-label="Terpakai hari ini">USD {_uang(pakai[fitur]["harian"], 4)}</td>'
        f'<td data-angka data-label="Terpakai bulan ini">USD {_uang(pakai[fitur]["bulanan"], 4)}</td></tr>'
    )


def _kartu_fitur(batas, pakai):
    kepala = ("Fitur", "Status", "Model", "Pagu/hari", "Pagu/bulan", "Terpakai hari ini", "Terpakai bulan ini")
    th = "".join(
        f'<th scope="col"{" data-angka" if i > 2 else ""}>{nama}</th>' for i, nama in enumerate(kepala)
    )
    baris = "".join(_baris_fitur(fitur, batas, pakai) for fitur in ai_policy.FITUR)
    return (
        '<section class="admin-kartu admin-kartu-tabel admin-ai-tabel"><div class="admin-kartu-kepala">'
        '<h2>Status dan pemakaian per fitur</h2></div><div class="admin-tabel-wrap">'
        f'<table class="admin-tabel"><thead><tr>{th}</tr></thead><tbody>{baris}</tbody></table></div></section>'
    )


def _grup_batas(fitur, batas):
    label = "Global" if fitur == "global" else ai_policy.LABEL_FITUR[fitur]
    cek = "" if fitur == "global" else (
        f'<label><input type="checkbox" name="aktif_{fitur}" value="1" '
        f'{"checked" if batas[fitur]["aktif"] else ""}> Izinkan {html.escape(label)}</label>'
    )
    return (
        f'<fieldset class="admin-ai-grup"><legend>{html.escape(label)}</legend>{cek}'
        '<div class="admin-ai-pagu">'
        f'<label>Pagu harian (USD)<input name="harian_{fitur}" type="number" min="0" step="0.01" '
        f'value="{_usd(batas[fitur]["batas_harian"])}" required></label>'
        f'<label>Pagu bulanan (USD)<input name="bulanan_{fitur}" type="number" min="0" step="0.01" '
        f'value="{_usd(batas[fitur]["batas_bulanan"])}" required></label></div></fieldset>'
    )


def _batas_lain(utama):
    return (
        '<fieldset class="admin-ai-grup"><legend>Batas lain</legend><div class="admin-ai-pagu admin-ai-tiga">'
        f'<label>Batas request per akun per hari<input name="request_akun_harian" type="number" min="0" value="{utama["request_akun_harian"]}" required></label>'
        f'<label>Batas tes per hari<input name="uji_harian" type="number" min="0" value="{utama["uji_harian"]}" required></label>'
        f'<label>Jeda tes (menit)<input name="uji_cooldown_menit" type="number" min="0" value="{utama["uji_cooldown_detik"] // 60}" required></label>'
        '</div></fieldset>'
    )


def _kendali_henti(utama):
    # Tetap checkbox pada form pengaturan yang sama: tanpa tombol/endpoint kedua.
    return (
        '<fieldset class="admin-galat admin-henti"><legend>Kendali penghentian</legend>'
        f'<label><input type="checkbox" name="dihentikan" value="1" {"checked" if utama["dihentikan"] else ""}>'
        ' Hentikan panggilan AI baru</label>'
        '<p>Permintaan yang sudah dikirim mungkin tetap selesai dan dikenai biaya. Data belajar dan hasil lama tidak dihapus.</p>'
        '<p>Perubahan ini diterapkan bersama tombol Simpan pengaturan AI.</p></fieldset>'
    )


def _kartu_batas(utama, batas, csrf, tinjauan):
    grup = "".join(_grup_batas(fitur, batas) for fitur in ("global", *ai_policy.FITUR))
    return (
        '<section class="admin-kartu"><h2>Ubah batas pemakaian</h2>'
        '<form method="post" action="/admin/ai/pengaturan">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">'
        f'<input type="hidden" name="tinjauan" value="{html.escape(tinjauan, quote=True)}">'
        f'<input type="hidden" name="revisi" value="{utama["revisi"]}">'
        + grup + _batas_lain(utama) + _kendali_henti(utama)
        + '<div class="admin-ai-simpan">'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button type="submit" class="admin-tombol">Simpan pengaturan AI</button></div></form></section>'
    )


def _kartu_uji(csrf, tinjauan):
    return (
        '<section class="admin-kartu"><h2>Tes koneksi sintetis</h2>'
        '<p class="admin-meta">Pengujian mengirim pesan tetap tanpa data keluarga dan memakai kuota tes serta global.</p>'
        '<form method="post" action="/admin/ai/uji">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">'
        f'<input type="hidden" name="tinjauan" value="{html.escape(tinjauan, quote=True)}">'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<label><input type="checkbox" name="konfirmasi" value="1" required> Saya memahami tes memakai kuota dan dapat menimbulkan biaya.</label>'
        '<button type="submit" class="admin-tombol admin-tombol-sekunder">Kirim tes sintetis</button></form></section>'
    )


def _kartu_riwayat(audit):
    butir = "".join(
        f'<li>{L.tanggal(a["dibuat"])} · Revisi {a["revisi"]}: {html.escape(L.label_status(a["field"]))} diubah oleh '
        f'{L.referensi(a["actor_id"])}.</li>' for a in audit
    ) or "<li>Belum ada perubahan.</li>"
    return f'<section class="admin-kartu"><h2>Riwayat pengaturan</h2><ul>{butir}</ul></section>'



def halaman(path, *, pengguna, csrf, pesan="", galat="",
            tinjauan_pengaturan="", tinjauan_uji="", sinyal=None,
            tema="sistem", csrf_tema=""):
    with ai_store.buka(path) as kon:
        utama, batas = ai_store.konfigurasi(kon)
        pakai = ai_store.ringkasan(kon)
        audit = kon.execute(
            "SELECT revisi,actor_id,field,lama,baru,dibuat FROM audit_konfigurasi ORDER BY id DESC LIMIT 20"
        ).fetchall()
    kabar = f'<div class="pesan">{html.escape(pesan)}</div>' if pesan else ""
    if galat:
        kabar += f'<div class="pesan galat" role="alert">{html.escape(galat)}</div>'
    ada_key = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    isi = (
        kabar
        + _kartu_status(ada_key, batas)
        + _kartu_fitur(batas, pakai)
        + _kartu_batas(utama, batas, csrf, tinjauan_pengaturan)
        + _kartu_uji(csrf, tinjauan_uji)
        + _kartu_riwayat(audit)
    )
    return admin_pages.halaman_admin(
        "ai", isi, pengguna=pengguna, judul="Pengaturan AI",
        subjudul="Kesiapan, batas biaya, dan pemakaian panggilan Jagomat.",
        skrip_sandi=SKRIP_MATA_SANDI, sinyal=sinyal,
        tema=tema, csrf_tema=csrf_tema,
    )
