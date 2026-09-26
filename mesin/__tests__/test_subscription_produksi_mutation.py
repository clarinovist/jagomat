"""Mutation guard runtime/callback/pekerja pada salinan temp; tanpa DB atau key nyata.

Setiap kasus mematikan satu guard di salinan source, membuktikan test penjaga menjadi
MERAH dengan marker yang jelas, lalu memulihkan file dan membuktikan test kembali HIJAU.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
PRODUKSI = 'test_subscription_produksi.py'
CALLBACK = 'test_subscription_callback.py'
RAHASIA = 'test_midtrans_secret.py'
PEKERJA = 'test_subscription_worker.py'
HTTP = 'test_subscription_produksi_http.py'
KASUS = [
    ('subscription_callback.py', 'if not midtrans.signature_cocok(mentah, config):', 'if False:', CALLBACK,
     'test_callback_penolakan_seragam_tanpa_efek', 'assert [kode for kode, _ in jawab] == [403] * len(kasus)'),
    ('subscription_callback.py',
     '    except (Exception, KeyboardInterrupt):\n        return 503, b"belum siap"',
     '    except (Exception, KeyboardInterrupt):\n        return 200, b"OK"', CALLBACK,
     'test_callback_tanpa_secret_atau_tier_rendah_fail_closed', 'assert kirim(k, muatan())[0] == 503'),
    ('subscription_callback.py',
     '        _simpan(admin_store.BAWAAN, invoice_id, status, sidik, int(time.time()), sakelar)',
     '        pass', CALLBACK, 'test_callback_valid_menyimpan_hint_dan_ack_bersih',
     'assert dump(admin_store.BAWAAN) != awal'),
    ('subscription_callback.py', '    if baris is None:\n        return False',
     '    if False:\n        return False', CALLBACK,
     'test_callback_asing_tanpa_dokumen_atau_grant_baru', 'assert kode == 200 and isi == "OK"'),
    ('subscription_callback.py',
     '    return (data.get("merchant_id") == config.merchant and data.get("currency") == "IDR"\n'
     '            and data.get("payment_type") == "qris")',
     '    return True', CALLBACK, 'test_callback_penolakan_seragam_tanpa_efek',
     'assert [kode for kode, _ in jawab] == [403] * len(kasus)'),
    ('subscription_callback.py',
     '("Origin", "Referer", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Cookie", "Authorization")',
     '("Origin", "Referer", "Sec-Fetch-Site", "Sec-Fetch-Mode")', CALLBACK,
     'test_callback_tanpa_login_dan_header_peramban', 'assert hasil == {nama: 403 for nama in peramban}, hasil'),
    ('subscription_callback.py', '    if jumlah > BATAS_BODY:', '    if False:', CALLBACK,
     'test_callback_kontrak_transport_ditolak_awal', '[0] == 413'),
    ('subscription_callback.py',
     '    return hashlib.sha256("|".join(wajib + [fraud]).encode("ascii")).hexdigest()[:32]',
     '    return hashlib.sha256(("%d" % id(data)).encode("ascii")).hexdigest()[:32]', CALLBACK,
     'test_callback_duplikat_idempoten_dan_out_of_order_append_only',
     'assert hint(admin_store.BAWAAN) == setelah_satu'),
    ('midtrans_secret.py', 'os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)', 'os.O_RDONLY', RAHASIA,
     'test_symlink_dan_bukan_file_biasa_ditolak', 'DID NOT RAISE'),
    ('midtrans_secret.py', 'or info.st_mode & (0o077 | 0o7000)', 'or False', RAHASIA,
     'test_izin_ketat', 'DID NOT RAISE'),
    ('midtrans_secret.py', '    if _SANDBOX.match(kunci) is not None:', '    if False:', RAHASIA,
     'test_kunci_sandbox_tidak_boleh_untuk_produksi', 'DID NOT RAISE'),
    ('midtrans_contract.py', 'or nominal_provider(data.get("gross_amount")) != invoice["rupiah"]',
     'or False', PEKERJA, 'test_refund_lalu_settlement_dan_nominal_lebih',
     'assert catat(k, T0 + 400)["menunggu"] == 1'),
    ('subscription_produksi.py',
     "    rekonsiliasi = tersimpan.rekonsiliasi and kesiapan[\"provider_produksi\"]",
     '    rekonsiliasi = tersimpan.rekonsiliasi', PRODUKSI,
     'test_sakelar_efektif_sepadan_permukaan_admin', 'assert dari_admin is not None and dari_admin.sakelar == dari_pekerja'),
    ('subscription_produksi.py', 'KEBIJAKAN_D8_D9 = True', 'KEBIJAKAN_D8_D9 = False', PRODUKSI,
     'test_runtime_dari_konfigurasi_tepercaya', 'assert r.kesiapan == {"provider_produksi": True, "callback": True,'),
    ('subscription_produksi.py',
     '        if getattr(server, "_pembayaran_dicoba", False):\n            return False',
     '        if False:\n            return False', PRODUKSI,
     'test_pastikan_terpasang_gagal_hanya_sekali_tanpa_raise', 'assert len(dipanggil) == 1'),
    ('subscription_produksi.py', '    if hasil is None:\n        return False',
     '    if False:\n        return False', PRODUKSI, 'test_tanpa_berkas_rahasia_fail_closed',
     'is False'),
    ('subscription_worker.py',
     'if inv_baru is None or sidik_baru is None or sidik_baru != sidik:', 'if False:', PEKERJA,
     'test_owner_berubah_selama_jaringan_tidak_grant',
     'assert ringkas["dilewati"] == 1 and jumlah(k, "langganan_receipt") == 0'),
    ('subscription_worker.py',
     '"              WHERE r.invoice_id = i.invoice_id AND substr(r.operasi_id, 1, 7) = \'create_\') "',
     '"              WHERE r.invoice_id = i.invoice_id) "', PEKERJA,
     'test_kandidat_bounded_cooldown_cutoff_dan_intent',
     'assert [b[0] for b in kandidat] == [inv3["invoice_id"], inv1["invoice_id"]]'),
    ('subscription_worker.py', 'if kedaluwarsa < sekarang - horizon:', 'if False:', PEKERJA,
     'test_kandidat_bounded_cooldown_cutoff_dan_intent',
     'assert tua["invoice_id"] not in [b[0] for b in worker.kandidat'),
    ('subscription_worker.py', 'if terakhir is not None and terakhir > sekarang - jeda:', 'if False:', PEKERJA,
     'test_unknown_dijadwalkan_ulang_bounded', 'assert worker.kandidat(k.admin, sekarang=T0 + 61) == []'),
    ('subscription_worker.py', '    sakelar.wajib("rekonsiliasi")\n    d.waktu(sekarang)', '    d.waktu(sekarang)',
     PEKERJA, 'test_batch_bounded_dan_sakelar_off', 'DID NOT RAISE'),
    ('subscription_worker.py', '        if ledger == "grant":', '        if True:', PEKERJA,
     'test_settlement_terlambat_perlu_diperiksa_tanpa_grant',
     'assert ringkas["perlu_diperiksa"] == 1 and ringkas["lunas"] == 0, ringkas'),
    # Surface checkout produksi: token form, allow-list QR, dan gate sakelar checkout.
    ('subscription_produksi_http.py',
     '        if not hmac.compare_digest(signature, harap):\n            raise ValueError()',
     '        if False:\n            raise ValueError()', HTTP,
     'test_token_wajib_terikat_sesi_aksi_dan_invoice', 'assert kode == 403'),
    ('subscription_produksi_http.py',
     '    if (not midtrans.url_qr_sah(url, "production")\n'
     '            or not url.startswith(runtime.config.base_url + "/v2/qris/")):\n'
     '        raise midtrans.KontrakTidakSah("tujuan QR produksi tidak sah")',
     '    if False:\n        raise midtrans.KontrakTidakSah("tujuan QR produksi tidak sah")', HTTP,
     'test_gambar_menolak_url_di_luar_allowlist', 'DID NOT RAISE'),
    ('subscription_produksi_http.py',
     '                boleh_buat = (runtime.sakelar.buat_pembayaran and not inv["create_dicoba"]\n'
     '                              and not lunas and sekarang < inv["kedaluwarsa"])',
     '                boleh_buat = True', HTTP,
     'test_turun_tahap_menyembunyikan_buat_dan_mematikan_qr', 'assert "/buat" not in isi'),
    # Buat ulang QR: hanya saat provider menyatakan mati, tanpa receipt, di dalam
    # jendela, dengan kunci idempotensi baru per transaksi mati.
    ('subscription_service.py',
     'if kelas == "mati" and identitas and pembayaran.status == "belum_terverifikasi":',
     'if identitas and pembayaran.status == "belum_terverifikasi":', HTTP,
     'test_ulang_qr_pending_tidak_membuat_create_baru', 'create saat pending'),
    ('midtrans_contract.py', 'if status in KELAS_MATI:', 'if True:', HTTP,
     'test_ulang_qr_status_tak_dikenal_atau_putus_tidak_membuat_create',
     'create saat status tak dikenal'),
    ('subscription_service.py', 'if receipt is not None or intent is None:',
     'if intent is None:', HTTP, 'test_ulang_qr_ditolak_tanpa_intent_atau_setelah_receipt',
     'setelah receipt'),
    ('subscription_produksi_http.py',
     'and sekarang < inv["kedaluwarsa"] and hasil.status != "pending")',
     'and sekarang < inv["kedaluwarsa"])', HTTP,
     'test_ulang_qr_pending_tidak_membuat_create_baru', 'CTA saat QR hidup'),
    ('subscription_service.py',
     'kunci = "ulang_" + hashlib.sha256(bahan).hexdigest()[:24]',
     'kunci = inv["idempotency_key"]', HTTP,
     'test_ulang_qr_setelah_expire_membuat_attempt_kedua', 'kunci ulang unik'),
    # CLI worker: jam produksi (time.time float) wajib dikoersi int — tick pertama
    # pasca-aktivasi gagal ValueError di jalur ini.
    ('rekonsiliasi_langganan.py',
     'sekarang = int(arg.sekarang or (clock or time.time)())',
     'sekarang = arg.sekarang or (clock or time.time)()', PEKERJA,
     'test_cli_tanpa_sekarang_memakai_jam_float_aman', 'putaran rekonsiliasi gagal (ValueError)'),
]


@pytest.mark.parametrize('modul,lama,baru,berkas,test,marker', KASUS)
def test_mutasi_guard_produksi(tmp_path, modul, lama, baru, berkas, test, marker):
    target = tmp_path / 'mesin'
    target.mkdir()
    for sumber in AKAR.glob('*.py'):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / '__tests__', target / '__tests__',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(AKAR.parent / 'scripts', tmp_path / 'scripts',
                    ignore=shutil.ignore_patterns('__pycache__'))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1
    p.write_text(teks.replace(lama, baru, 1))
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    node = str(target / '__tests__' / berkas) + '::' + test
    hasil = subprocess.run([sys.executable, '-m', 'pytest', node, '-q', '-W', 'error',
                            '-p', 'no:cacheprovider'], capture_output=True, text=True,
                           env=env, timeout=60)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert marker in hasil.stdout, hasil.stdout
    p.write_text(teks)
    pulih = subprocess.run([sys.executable, '-m', 'pytest', node, '-q', '-W', 'error',
                            '-p', 'no:cacheprovider'], capture_output=True, text=True,
                           env=env, timeout=60)
    assert pulih.returncode == 0, pulih.stdout + pulih.stderr


# Guard aktivasi pembayaran pada DEPLOYER (mount secret + artefak pasangan):
# satu kasus mematikan mount rahasia, satu menonaktifkan penulisan artefak —
# keduanya harus membuat test penjaga MERAH pada salinan source temp.
KASUS_DEPLOYER = [
    ('scripts/deploy.py', 'dst=/run/secrets/midtrans,readonly"]',
     'dst=/lupakan-rahasia,readonly"]', 'test_deployer.py',
     'test_run_utama_dan_recovery_membawa_mount_rahasia', 'mount-rahasia-hilang'),
    ('scripts/deploy.py',
     '            berkas.tulis_pasangan(docker.revision_image(id_kandidat), id_kandidat,\n'
     '                                  kontrak_kandidat, "rutin" if rutin else "migrasi")\n',
     '            pass\n', 'test_deployer.py', 'test_sukses_ordering_secret_dan_argv_tetap',
     'revision-candidate'),
]


@pytest.mark.parametrize('modul,lama,baru,berkas,test,marker', KASUS_DEPLOYER)
def test_mutasi_guard_deployer(tmp_path, modul, lama, baru, berkas, test, marker):
    target = tmp_path / 'mesin'
    target.mkdir()
    for sumber in AKAR.glob('*.py'):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / '__tests__', target / '__tests__',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(AKAR.parent / 'scripts', tmp_path / 'scripts',
                    ignore=shutil.ignore_patterns('__pycache__'))
    p = tmp_path / modul
    teks = p.read_text()
    assert teks.count(lama) == 1
    p.write_text(teks.replace(lama, baru, 1))
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    node = str(target / '__tests__' / berkas) + '::' + test
    hasil = subprocess.run([sys.executable, '-m', 'pytest', node, '-q', '-W', 'error',
                            '-p', 'no:cacheprovider'], capture_output=True, text=True,
                           env=env, timeout=60)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert marker in hasil.stdout, hasil.stdout
    p.write_text(teks)
    pulih = subprocess.run([sys.executable, '-m', 'pytest', node, '-q', '-W', 'error',
                            '-p', 'no:cacheprovider'], capture_output=True, text=True,
                           env=env, timeout=60)
    assert pulih.returncode == 0, pulih.stdout + pulih.stderr
