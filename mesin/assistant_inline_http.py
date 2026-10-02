"""Alur HTTP inline Pendamping pada host profil dan sesi."""
from __future__ import annotations

import re
import time
import urllib.parse

import assistant_actions
import assistant_components
import assistant_context
import assistant_inline
import assistant_pages
import assistant_policy
import assistant_service
import assistant_store
import assistant_view
from assistant_http_common import (
    GalatForm, _kirim_privat, _principal, _tidak_ada, _tolak_login, aktif,
)


def _legacy(nama):
    import assistant_http
    return getattr(assistant_http, nama)


def _akses_terkunci(*args, **kwargs):
    return _legacy("_akses_terkunci")(*args, **kwargs)


def _consent(*args, **kwargs):
    return _legacy("_consent")(*args, **kwargs)


def _host_milik(*args, **kwargs):
    return _legacy("_host_milik")(*args, **kwargs)


def _siapkan_db(*args, **kwargs):
    return _legacy("_siapkan_db")(*args, **kwargs)


def _sumber(*args, **kwargs):
    return _legacy("_sumber")(*args, **kwargs)


def _versi_konteks_chat(*args, **kwargs):
    return _legacy("_versi_konteks_chat")(*args, **kwargs)


def fragmen_inline(*args, **kwargs):
    return _legacy("fragmen_inline")(*args, **kwargs)


def _data_inline(penangan):
    """Parser form host lebih besar dari chat lama, tetap strict/owner-local."""
    asal = penangan.headers.get("Origin")
    situs = penangan.headers.get("Sec-Fetch-Site")
    if asal == "null":
        silang = situs != "same-origin"
    else:
        silang = bool(asal) and urllib.parse.urlsplit(asal).netloc != penangan.headers.get("Host")
    if (not asal and situs != "same-origin") or silang or situs == "cross-site":
        raise GalatForm("Permintaan harus berasal dari situs ini.", 403)
    panjang = penangan.headers.get("Content-Length", "0")
    if not re.fullmatch(r"[0-9]+", panjang) or int(panjang) > 110_000:
        raise GalatForm("Isian terlalu besar.", 413)
    if penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        raise GalatForm("Format isian tidak dikenal.")
    try:
        mentah = penangan.rfile.read(int(panjang)).decode("utf-8")
        return urllib.parse.parse_qs(
            mentah, keep_blank_values=True, errors="strict", max_num_fields=500
        )
    except (UnicodeError, ValueError) as galat:
        raise GalatForm("Isian tidak dapat dibaca.") from galat

def _target_inline_sah(principal, target):
    import database
    with database.buka() as kon_data:
        return assistant_context.ambil(
            kon_data, target.jenis_resource, target.resource_id,
            pemilik=principal.pengguna,
        )

def _pisahkan_draf_inline(data, target):
    """Pisahkan draf host dari aksi; draf tak pernah masuk store/provider."""
    data = dict(data)
    jenis_form = data.pop("inline_form", [""])
    if len(jenis_form) != 1:
        raise GalatForm("Identitas form bantuan tidak sah.")
    jenis_form = jenis_form[0]
    if target.jenis_host == "sesi":
        if jenis_form not in ("", "koreksi"):
            raise GalatForm("Identitas form bantuan tidak sah.")
        import database
        with database.buka() as kon_data:
            info = kon_data.execute("SELECT mode FROM sesi WHERE id = ?", (target.host_id,)).fetchone()
            ids = tuple(int(b["sesi_soal_id"]) for b in database.isi_sesi(kon_data, target.host_id))
        if info is None:
            raise LookupError("host tidak tersedia")
        awalan = ("jwb_", "kode_", "cara_", "cek_pemahaman_", "hadir_dilewati_", "dilewati_", "hadir_belum_", "belum_", "catatan_tinjauan_", "provenance_", "jawaban_bantuan_", "versi_tinjauan_")
        nama = {
            k for k in data
            if k.startswith(awalan)
            or k in ("sertakan_pemetaan", "hadir_sertakan_pemetaan")
            or k.startswith("isi_memori_")
        }
        if not nama:
            return data, None, None, None
        field_memori = {k: data[k] for k in nama if k.startswith("isi_memori_")}
        field_draf = {k: data[k] for k in nama if not k.startswith("isi_memori_")}
        draf = assistant_inline.parse_draf_koreksi(field_draf, ids, mode=info["mode"]) if field_draf else None
        sisa = {k: v for k, v in data.items() if k not in nama}
        sisa.update(field_memori)
        return sisa, draf, None, None
    if target.jenis_host != "anak" or target.posisi != "latihan":
        if jenis_form:
            raise GalatForm("Identitas form bantuan tidak sah.")
        return data, None, None, None
    import topics
    if jenis_form == "gabungan":
        nama = {"topik", "jumlah_soal", "mode", "format_jawaban", "profil_parameter"}
        draf = assistant_inline.parse_draf_gabungan(
            {k: data[k] for k in nama if k in data}, topics.daftar_topik()
        )
        return {k: v for k, v in data.items() if k not in nama}, None, draf, None
    if jenis_form == "remedial":
        import database
        with database.buka() as kon_data:
            sumber = data.get("sumber_sesi_id", [""])
            if len(sumber) != 1:
                raise assistant_inline.GalatInline("Sumber remedial ganda.")
            if sumber[0]:
                sumber_id = assistant_inline._id_kanonik(sumber[0])
                milik = kon_data.execute(
                    "SELECT 1 FROM sesi WHERE id=? AND siswa_id=?", (sumber_id, target.host_id)
                ).fetchone()
                if not milik:
                    raise LookupError("sumber tidak tersedia")
                kandidat = database.sasaran_remedial_sesi(kon_data, target.host_id, sumber_id)
            else:
                kandidat = database.sasaran_remedial_anak(kon_data, target.host_id)
            remedial_sah = tuple(str(k["template_id"]) for k in kandidat)
        nama = {"template_id", "jumlah_soal", "sumber_sesi_id"}
        draf = assistant_inline.parse_draf_remedial(
            {k: data[k] for k in nama if k in data}, remedial_sah
        )
        return {k: v for k, v in data.items() if k not in nama}, None, None, draf
    if jenis_form not in ("", "manual"):
        raise GalatForm("Identitas form bantuan tidak sah.")
    nama_sah = {"topik", "jumlah_soal", "mode", "hadir_timer_mode", "timer_mode", "durasi_menit", "timer_auto", "format_jawaban", "profil_parameter"}
    nama = nama_sah & set(data)
    if not (nama - {"mode"}):
        return data, None, None, None
    draf = assistant_inline.parse_draf_latihan({k: data[k] for k in nama}, topics.daftar_topik())
    return {k: v for k, v in data.items() if k not in nama}, draf, None, None

def _dalam_form_inline(target, draf, draf_gabungan=None, draf_remedial=None) -> bool:
    return bool(
        target.jenis_host == "anak" and target.posisi == "latihan"
        or draf is not None or draf_gabungan is not None or draf_remedial is not None
    )

def _render_host_dengan_fragmen(
    penangan, principal, target, fragmen: str, *, draf=None,
    draf_gabungan=None, draf_remedial=None, kode=200,
):
    if penangan.headers.get("X-Pendamping-Panel") == "fragment":
        _kirim_privat(penangan, fragmen.encode("utf-8"), kode)
        return
    import database
    import teacher_pages
    with database.buka() as kon_data:
        if target.jenis_host == "sesi":
            isi = teacher_pages.halaman_sesi_stitch(
                kon_data, target.host_id, peran="guru", pengguna=principal.pengguna,
                bantuan=fragmen, bantuan_nomor=target.nomor, draf_koreksi=draf,
            )
        else:
            siswa = kon_data.execute("SELECT * FROM siswa WHERE id = ?", (target.host_id,)).fetchone()
            if siswa is None:
                raise LookupError("host tidak tersedia")
            isi = teacher_pages.halaman_anak(
                kon_data, siswa, peran="guru", pengguna=principal.pengguna,
                bantuan_rencana=fragmen if target.posisi == "rencana" else "",
                bantuan_latihan=fragmen if target.posisi == "latihan" else "",
                draf_latihan=draf, draf_gabungan=draf_gabungan,
                draf_remedial=draf_remedial,
            )
    penangan._kirim_privat(isi, kode)

def _render_host_inline(
    penangan, principal, target, *, draf=None, draf_gabungan=None,
    draf_remedial=None, galat="", kode=200, halaman_riwayat: int = 1,
    request_id: str = "",
):
    fragmen = fragmen_inline(
        principal, target,
        dalam_form=(penangan.headers.get("X-Pendamping-Panel") != "fragment"
                    and _dalam_form_inline(target, draf, draf_gabungan, draf_remedial)),
        galat=galat, halaman_riwayat=halaman_riwayat,
    )
    if request_id and re.fullmatch(r"req_[0-9A-Za-z_-]{8,80}", request_id):
        fragmen = fragmen.replace('<aside ', '<aside data-pendamping-request="' + request_id + '" ', 1)
    _render_host_dengan_fragmen(
        penangan, principal, target, fragmen, draf=draf,
        draf_gabungan=draf_gabungan, draf_remedial=draf_remedial, kode=kode,
    )

def tangani_inline_post(penangan, jalur: str) -> bool:
    """Aksi inti inline. Host sesi merender draf di router setelah aksi."""
    if not jalur.startswith("/pendamping/inline/"):
        return False
    if not aktif():
        _tidak_ada(penangan)
        return True
    principal = _principal(penangan)
    if principal is None:
        _tolak_login(penangan)
        return True
    draf_host = {}
    try:
        data = _data_inline(penangan)
        muatan_aksi = data.pop("data_aksi", None)
        if muatan_aksi is not None:
            if len(muatan_aksi) != 1:
                raise GalatForm("Data aksi ganda tidak sah.")
            try:
                ekstra = urllib.parse.parse_qs(
                    muatan_aksi[0], keep_blank_values=True, errors="strict",
                    max_num_fields=8,
                )
            except (ValueError, UnicodeError) as galat:
                raise GalatForm("Data aksi tidak sah.") from galat
            if any(len(nilai) != 1 for nilai in ekstra.values()) or set(ekstra) & set(data):
                raise GalatForm("Data aksi ambigu.")
            data.update(ekstra)
        cocok_buka = re.fullmatch(
            r"/pendamping/inline/buka/sesi/([1-9][0-9]{0,18})/(sesi|soal(?:/([1-9][0-9]{0,18}))?)",
            jalur,
        )
        if cocok_buka:
            sesi_id = int(cocok_buka[1])
            target = assistant_inline.tujuan_sesi(
                sesi_id, nomor=int(cocok_buka[3]) if cocok_buka[3] else None,
            )
        else:
            target = assistant_inline.target_dari_form(data)
        aksi = "buka" if cocok_buka else jalur.rsplit("/", 1)[-1]
        akses = _akses_terkunci(principal.id_akun)
        if aksi == "buka" and akses is not None and not target.chat_id:
            if not _host_milik(principal, target):
                raise LookupError("host tidak tersedia")
            fragmen_request = penangan.headers.get("X-Pendamping-Panel") == "fragment"
            draf = draf_gabungan = draf_remedial = None
            if not fragmen_request:
                _sisa, draf, draf_gabungan, draf_remedial = _pisahkan_draf_inline(
                    data, target,
                )
            fragmen = assistant_components.panel_akses(
                target, akses, dalam_form=not fragmen_request,
            )
            _render_host_dengan_fragmen(
                penangan, principal, target, fragmen, draf=draf,
                draf_gabungan=draf_gabungan, draf_remedial=draf_remedial,
            )
            return True
        if aksi == "pilih-sumber":
            draf = draf_gabungan = draf_remedial = None
            konteks = _target_inline_sah(principal, target)
            if konteks is None:
                raise LookupError("sumber tidak tersedia")
            if target.jenis_resource != "sesi" or set(data) != {
                "inline_host", "inline_host_id", "inline_posisi", "pilih_nomor"
            }:
                raise GalatForm("Sumber bantuan tidak sah.")
            nomor = data["pilih_nomor"]
            if len(nomor) != 1:
                raise GalatForm("Sumber bantuan tidak sah.")
            if nomor[0]:
                if not re.fullmatch(r"[1-9][0-9]{0,18}", nomor[0]):
                    raise GalatForm("Sumber bantuan tidak sah.")
                target = assistant_inline.tujuan_sesi(target.host_id, nomor=int(nomor[0]))
                konteks = _target_inline_sah(principal, target)
                if konteks is None:
                    raise LookupError("sumber tidak tersedia")
            _render_host_inline(penangan, principal, target)
            return True
        konteks = _target_inline_sah(principal, target)
        if konteks is None:
            raise LookupError("sumber tidak tersedia")
        field_panel = {
            "inline_host", "inline_host_id", "inline_posisi", "inline_nomor", "chat",
            "kebijakan", "setuju", "resource_version", "kategori", "mode_chat",
            "request_id", "setuju_konteks", "pesan", "halaman", "pilih_chat",
            "memori", "versi_item", "versi_memori", "isi_field", "isi_memori",
            "persetujuan_hapus", "usulan", "versi_usulan", "hash_usulan",
        }
        if penangan.headers.get("X-Pendamping-Panel") == "fragment" and set(data) - field_panel:
            raise assistant_inline.GalatInline("Draf hanya boleh pada fallback native.")
        data, draf, draf_gabungan, draf_remedial = _pisahkan_draf_inline(data, target)
        draf_host = dict(draf=draf, draf_gabungan=draf_gabungan, draf_remedial=draf_remedial)
        # Sesudah pemisahan, hanya field panel tunggal yang boleh tersisa.
        if any(len(v) != 1 or (k not in field_panel and not re.fullmatch(
            r"isi_memori_memori_[0-9a-f]{32}", k
        )) for k, v in data.items()):
            raise assistant_inline.GalatInline("Field panel ganda atau asing.")
        # Fallback in-form mengirim semua kontrol panel yang sah, bukan hanya
        # tombol terpilih. Suntingan memori/composer bukan payload aksi lain.
        if aksi != "ubah-memori":
            data = {k: v for k, v in data.items() if not k.startswith("isi_memori_")}
        if aksi not in ("pesan", "status", "mulai", "konfirmasi-usulan"):
            data.pop("request_id", None)
            data.pop("pesan", None)
        if aksi == "buka" and penangan.headers.get("X-Pendamping-Panel") == "fragment":
            if target.jenis_resource == "sesi" and target.chat_id is None:
                import database
                with database.buka() as kon_data:
                    sumber = assistant_view.sumber_tampilan(
                        kon_data, "sesi", str(target.host_id), pemilik=principal.pengguna,
                    )
                    nomor_soal = tuple(
                        int(baris["nomor"])
                        for baris in database.isi_sesi(kon_data, target.host_id)
                    )
                if sumber is None:
                    raise LookupError("sumber tidak tersedia")
                fragmen = assistant_components.panel_pilih_sumber_sesi(
                    target, nomor_soal, sumber=sumber,
                )
            else:
                fragmen = fragmen_inline(principal, target, dalam_form=False)
            _kirim_privat(penangan, fragmen.encode("utf-8"))
            return True
        if aksi == "buka":
            _render_host_inline(
                penangan, principal, target, **draf_host,
            )
            return True
        if aksi == "tutup" and penangan.headers.get("X-Pendamping-Panel") == "fragment":
            _kirim_privat(
                penangan,
                assistant_components.fragmen_tutup(target).encode("utf-8"),
            )
            return True
        if aksi == "tutup":
            # Fallback native tetap dalam request yang sama agar draf belum
            # disimpan tidak hilang; enhancement menutup panel di DOM.
            # Field draf yang divalidasi tidak masuk store/provider. Lepaskan
            # assisted-state dan kembalikan alat host native.
            import database
            import teacher_pages
            with database.buka() as kon_data:
                if target.jenis_host == "sesi":
                    isi = teacher_pages.halaman_sesi_stitch(
                        kon_data, target.host_id, peran="guru", pengguna=principal.pengguna,
                        draf_koreksi=draf, privat=True,
                    )
                else:
                    siswa = kon_data.execute("SELECT * FROM siswa WHERE id=?", (target.host_id,)).fetchone()
                    if siswa is None:
                        raise LookupError("host tidak tersedia")
                    isi = teacher_pages.halaman_anak(
                        kon_data, siswa, peran="guru", pengguna=principal.pengguna,
                        draf_latihan=draf, draf_gabungan=draf_gabungan,
                        draf_remedial=draf_remedial, privat=True,
                        query="section=" + target.posisi,
                    )
            penangan._kirim_privat(isi)
            return True
        kini = int(time.time())
        with _siapkan_db() as kon:
            if aksi == "persetujuan":
                if (
                    set(data) - {"inline_host", "inline_host_id", "inline_posisi", "inline_nomor", "kebijakan", "setuju"}
                    or data.get("setuju") != ["1"]
                    or data.get("kebijakan") != [assistant_policy.VERSI_KEBIJAKAN]
                ):
                    raise GalatForm("Persetujuan tidak lengkap.")
                if not _consent(kon, principal.id_akun):
                    assistant_store.beri_persetujuan(
                        kon, principal.id_akun,
                        policy_version=assistant_policy.VERSI_KEBIJAKAN,
                        provider_id=assistant_policy.PROVIDER_ID,
                        kategori="chat_umum", sekarang=kini,
                    )
                kon.commit()
                _render_host_inline(penangan, principal, target, **draf_host)
                return True
            if not _consent(kon, principal.id_akun):
                raise GalatForm("Persetujuan berubah.", 409)
            if aksi == "mulai":
                wajib = {"inline_host", "inline_host_id", "inline_posisi", "resource_version", "kategori", "mode_chat", "request_id", "setuju_konteks"}
                if target.nomor is not None:
                    wajib.add("inline_nomor")
                mode_chat = data.get("mode_chat", [""])[0]
                if set(data) != wajib or data.get("setuju_konteks") != ["1"] or mode_chat not in ("aktif", "tanpa_memori"):
                    raise GalatForm("Persetujuan konteks tidak lengkap.")
                if data["resource_version"][0] != konteks.versi or data["kategori"][0] != konteks.kategori:
                    raise LookupError("sumber berubah")
                # Deduplikasi sebelum membuat grant baru: grant terbaru baru
                # akan membuat versi chat lama tidak aktif.
                chat = next((c for c in assistant_store.daftar_chat(kon, principal.id_akun)
                             if c.context_kind == konteks.jenis and c.context_id == konteks.resource_id
                             and c.context_resource_version == konteks.versi and c.mode_memori == mode_chat
                             and assistant_view.hak_baca_chat(
                                 kon, principal.id_akun, c, pemilik=principal.pengguna
                             )), None)
                if chat is None:
                    persetujuan = assistant_store.beri_persetujuan_konteks(
                        kon, principal.id_akun, jenis=konteks.jenis,
                        resource_id=konteks.resource_id, resource_version=konteks.versi,
                        kategori=konteks.kategori, sekarang=kini,
                    )
                    chat = assistant_store.buat_chat(
                        kon, principal.id_akun, mode_chat, sekarang=kini,
                        context_kind=konteks.jenis, context_id=konteks.resource_id,
                        context_version=persetujuan.versi,
                        context_resource_version=konteks.versi,
                        context_category=konteks.kategori,
                    )
                kon.commit()
                from dataclasses import replace as ganti
                _render_host_inline(
                    penangan, principal, ganti(target, chat_id=chat.id), **draf_host,
                )
                return True
            chat_id = data.get("chat", [""])[0]
            chat = assistant_store.ambil_chat(kon, principal.id_akun, chat_id)
            if (chat is None or chat.context_kind != target.jenis_resource
                    or chat.context_id != target.resource_id
                    or not assistant_view.hak_baca_chat(kon, principal.id_akun, chat, pemilik=principal.pengguna)):
                raise LookupError("chat tidak tersedia")
            if aksi in (
                "tinjau-hapus-memori", "batal-hapus-memori",
                "konfirmasi-memori", "ubah-memori", "hapus-memori",
            ):
                if aksi == "batal-hapus-memori":
                    _render_host_inline(penangan, principal, target, **draf_host)
                    return True
                memori_id = data.get("memori", [""])[0]
                versi_item = data.get("versi_item", [""])[0]
                if not versi_item.isdigit():
                    raise GalatForm("Versi memori tidak sah.")
                item = next((m for m in assistant_store.daftar_memori(
                    kon, principal.id_akun
                ) if m.id == memori_id), None)
                if item is None:
                    raise LookupError("memori tidak tersedia")
                if item.versi != int(versi_item):
                    raise GalatForm("Memori berubah. Tinjau ulang sebelum menghapus.", 409)
                if aksi == "tinjau-hapus-memori":
                    sumber = _sumber(chat, principal.pengguna)
                    fragmen = assistant_components.panel_tinjauan_hapus_memori(
                        target, chat, item, sumber=sumber,
                        dalam_form=_dalam_form_inline(target, **draf_host),
                    )
                    _render_host_dengan_fragmen(
                        penangan, principal, target, fragmen, **draf_host,
                    )
                    return True
                if aksi == "konfirmasi-memori":
                    berhasil = assistant_store.konfirmasi_memori(
                        kon, principal.id_akun, memori_id,
                        versi_diharapkan=int(versi_item), sekarang=kini,
                    )
                elif aksi == "ubah-memori":
                    nama_isi = data.get("isi_field", ["isi_memori"])[0]
                    if nama_isi not in ("isi_memori", f"isi_memori_{memori_id}"):
                        raise GalatForm("Field isi memori tidak sah.")
                    nilai_isi = data.get(nama_isi, [""])[0]
                    berhasil = assistant_store.ubah_memori(
                        kon, principal.id_akun, memori_id, nilai_isi,
                        versi_diharapkan=int(versi_item), sekarang=kini,
                    )
                else:
                    diizinkan = {
                        "inline_host", "inline_host_id", "inline_posisi",
                        "inline_nomor", "chat", "memori", "versi_item",
                        "persetujuan_hapus",
                    }
                    if set(data) - diizinkan or data.get("persetujuan_hapus") != ["1"]:
                        sumber = _sumber(chat, principal.pengguna)
                        fragmen = assistant_components.panel_tinjauan_hapus_memori(
                            target, chat, item, sumber=sumber,
                            dalam_form=_dalam_form_inline(target, **draf_host),
                            galat="Centang konfirmasi sebelum menghapus catatan.",
                        )
                        _render_host_dengan_fragmen(
                            penangan, principal, target, fragmen, **draf_host, kode=400,
                        )
                        return True
                    berhasil = assistant_store.hapus_memori(
                        kon, principal.id_akun, memori_id,
                        versi_diharapkan=int(versi_item), sekarang=kini,
                    )
                if not berhasil:
                    raise GalatForm("Memori berubah atau isi tidak didukung.", 409)
                kon.commit()
                _render_host_inline(penangan, principal, target, **draf_host)
                return True
            if aksi in ("aktifkan-memori", "nonaktifkan-memori"):
                if set(data) - {"inline_host", "inline_host_id", "inline_posisi", "inline_nomor", "chat", "versi_memori"}:
                    raise GalatForm("Aksi memori tidak sah.")
                versi = data.get("versi_memori", [""])[0]
                if not versi.isdigit():
                    raise GalatForm("Versi memori tidak sah.")
                assistant_store.atur_penggunaan_memori(
                    kon, principal.id_akun, aksi == "aktifkan-memori",
                    versi_diharapkan=int(versi), sekarang=kini,
                )
                kon.commit()
                _render_host_inline(penangan, principal, target, **draf_host)
                return True
            if aksi == "status":
                request_id = data.get("request_id", [""])[0]
                operasi = kon.execute(
                    "SELECT status FROM operasi WHERE request_id=? AND account_id=? AND chat_id=?",
                    (request_id, principal.id_akun, chat.id),
                ).fetchone()
                if operasi is None:
                    raise LookupError("operasi tidak tersedia")
                _render_host_inline(penangan, principal, target, **draf_host, request_id=request_id)
                return True
            if aksi == "tinjau":
                usulan_id = data.get("usulan", [""])[0]
                usulan = assistant_store.ambil_usulan(kon, principal.id_akun, usulan_id)
                if usulan is None or usulan.chat_id != chat.id:
                    raise LookupError("usulan tidak tersedia")
                sumber = _sumber(chat, principal.pengguna)
                sesi_hasil = assistant_actions.ambil_hasil_usulan(
                    kon, principal.id_akun, principal.pengguna, usulan.id
                )
                if sesi_hasil is not None:
                    fragmen = assistant_components.panel_hasil(
                        target, chat, sesi_hasil, sumber=sumber,
                        dalam_form=_dalam_form_inline(target, **draf_host),
                    )
                else:
                    token_tinjau = assistant_actions.tinjau_usulan(
                        kon, principal.id_akun, principal.pengguna, usulan.id, sekarang=kini,
                    )
                    fragmen = assistant_components.panel_tinjauan(
                        target, chat, usulan, token_tinjau, sumber=sumber,
                        dalam_form=_dalam_form_inline(target, **draf_host),
                    )
                _render_host_dengan_fragmen(penangan, principal, target, fragmen, **draf_host)
                return True
            if aksi == "konfirmasi-usulan":
                wajib_usulan = {"usulan", "versi_usulan", "hash_usulan", "request_id"}
                if not wajib_usulan <= set(data) or not data["versi_usulan"][0].isdigit():
                    raise GalatForm("Konfirmasi usulan tidak sah.")
                sesi_hasil = assistant_actions.konfirmasi_dan_buat_sesi(
                    kon, principal.id_akun, principal.pengguna, data["usulan"][0],
                    versi=int(data["versi_usulan"][0]), hash_diharapkan=data["hash_usulan"][0],
                    request_id=data["request_id"][0], sekarang=kini,
                )
                sumber = _sumber(chat, principal.pengguna)
                fragmen = assistant_components.panel_hasil(
                        target, chat, sesi_hasil, sumber=sumber,
                        dalam_form=_dalam_form_inline(target, **draf_host),
                    )
                _render_host_dengan_fragmen(penangan, principal, target, fragmen, **draf_host)
                return True
            if aksi == "riwayat":
                halaman = data.get("halaman", ["1"])
                if len(halaman) != 1 or not re.fullmatch(r"[1-9][0-9]{0,2}", halaman[0]):
                    raise GalatForm("Halaman riwayat tidak sah.")
                pilihan = data.get("pilih_chat", [chat.id])
                if len(pilihan) != 1:
                    raise GalatForm("Percakapan tujuan tidak sah.")
                tujuan_chat = assistant_store.ambil_chat(kon, principal.id_akun, pilihan[0])
                if (tujuan_chat is None or tujuan_chat.context_kind != target.jenis_resource
                        or tujuan_chat.context_id != target.resource_id
                        or not assistant_view.hak_baca_chat(
                            kon, principal.id_akun, tujuan_chat, pemilik=principal.pengguna
                        )):
                    raise LookupError("chat tidak tersedia")
                from dataclasses import replace as ganti
                _render_host_inline(
                    penangan, principal, ganti(target, chat_id=tujuan_chat.id),
                    **draf_host, halaman_riwayat=int(halaman[0]),
                )
                return True
            if aksi != "pesan" or set(data) - {"inline_host", "inline_host_id", "inline_posisi", "inline_nomor", "chat", "request_id", "pesan"}:
                raise GalatForm("Aksi bantuan tidak sah.")
            request_id = data.get("request_id", [""])[0]
            if not re.fullmatch(r"req_[0-9A-Za-z_-]{8,80}", request_id):
                raise GalatForm("Penanda permintaan tidak sah.")
            assistant_service.kirim_pesan(
                kon, principal.id_akun, chat.id, data.get("pesan", [""])[0],
                request_id=request_id, sekarang=kini, konteks=konteks,
                validasi_konteks=lambda: _versi_konteks_chat(chat, principal.pengguna),
            )
            kon.commit()
            _render_host_inline(penangan, principal, target, **draf_host, request_id=request_id)
            return True
    except (LookupError, assistant_inline.GalatInline):
        _tidak_ada(penangan)
    except (GalatForm, assistant_service.GalatPendamping, ValueError) as galat:
        try:
            # Pantulkan draf hanya setelah principal/resource/chat tetap sah.
            if "target" in locals() and _target_inline_sah(principal, target) is not None:
                _render_host_inline(
                    penangan, principal, target,
                    **draf_host, galat=str(galat),
                    request_id=locals().get("request_id", ""),
                    kode=getattr(galat, "status", 409),
                )
                return True
        except LookupError:
            pass
        _kirim_privat(penangan, assistant_pages._bingkai(
            "Permintaan ditolak", '<h1 id="judul-pendamping">Permintaan ditolak</h1>'
            '<p role="alert">Permintaan bantuan tidak dapat diproses.</p>'
        ), getattr(galat, "status", 409))
    return True
