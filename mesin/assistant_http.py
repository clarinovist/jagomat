"""Parser dan routing HTTP ketat untuk Pendamping."""

from __future__ import annotations

import html
from dataclasses import replace
import re
import secrets
import sqlite3
import time
import urllib.parse

from assistant_inline_http import (
    _data_inline,
    _dalam_form_inline,
    _pisahkan_draf_inline,
    _render_host_dengan_fragmen,
    _render_host_inline,
    _target_inline_sah,
    tangani_inline_post,
)
from assistant_http_common import (
    GalatForm,
    _baca_form,
    _batasi_laju,
    _kirim_host_privat,
    _kirim_privat,
    _principal,
    _redirect,
    _tidak_ada,
    _tolak_login,
    _usulan_berubah,
    aktif,
)

import ai_errors
import ai_service
import assistant_actions
import assistant_components
import assistant_inline
import assistant_navigation
import assistant_view
import assistant_context
import assistant_entitlement_runtime
import assistant_pages
import assistant_policy
import assistant_schema
import assistant_service
import assistant_store
import sessions

_POLA_CHAT = re.compile(r"/pendamping/chat/(chat_[0-9a-f]{32})\Z")
_POLA_PESAN = re.compile(r"/pendamping/chat/(chat_[0-9a-f]{32})/pesan\Z")
_POLA_MEMORI = re.compile(
    r"/pendamping/memori/(memori_[0-9a-f]{32})/(konfirmasi|ubah|hapus)\Z"
)
_POLA_KONTEKS = re.compile(
    r"/pendamping/konteks/(anak|sesi|soal)/([0-9]+(?::[0-9]+)?)\Z"
)
_POLA_USULAN = re.compile(r"/pendamping/usulan/(usulan_[0-9a-f]{32})\Z")
_POLA_KONFIRMASI_USULAN = re.compile(
    r"/pendamping/usulan/(usulan_[0-9a-f]{32})/konfirmasi\Z"
)

def _siapkan_db():
    assistant_schema.siapkan()
    return assistant_schema.buka()

def _konteks_chat(chat, pemilik: str):
    if chat.context_kind is None:
        return None
    import database

    with database.buka() as kon:
        konteks = assistant_context.ambil(
            kon, chat.context_kind, chat.context_id, pemilik=pemilik
        )
    if (
        konteks is None
        or konteks.versi != chat.context_resource_version
    ):
        return None
    return konteks

def _versi_konteks_chat(chat, pemilik: str):
    import database

    with database.buka() as kon:
        return assistant_context.versi_resource(
            kon, chat.context_kind, chat.context_id, pemilik=pemilik
        )

def _query(penangan):
    """Query terbatas; parameter URL bukan sumber otorisasi."""
    try:
        data = urllib.parse.parse_qs(
            urllib.parse.urlsplit(penangan.path).query,
            keep_blank_values=True, max_num_fields=4, errors='strict',
        )
    except (ValueError, UnicodeError):
        raise GalatForm('Parameter tidak sah.', 404) from None
    if any(len(nilai) != 1 for nilai in data.values()):
        raise GalatForm('Parameter ganda tidak sah.', 404)
    return {k: v[0] for k, v in data.items()}

def _sumber(chat, pemilik):
    if chat.context_kind is None:
        return None
    import database
    with database.buka() as kon_data:
        return assistant_view.sumber_tampilan(
            kon_data, chat.context_kind, chat.context_id, pemilik=pemilik
        )

def _target_chat_inline(chat):
    """Petakan snapshot berkonteks ke satu host inline kanonik."""
    if chat.context_kind == "anak":
        return assistant_inline.tujuan_anak(int(chat.context_id), chat_id=chat.id)
    if chat.context_kind == "sesi":
        return assistant_inline.tujuan_sesi(int(chat.context_id), chat_id=chat.id)
    if chat.context_kind == "soal":
        sesi_id, nomor = chat.context_id.split(":", 1)
        return assistant_inline.tujuan_sesi(
            int(sesi_id), nomor=int(nomor), chat_id=chat.id,
        )
    raise LookupError("chat umum tidak memiliki host")

def _kembali_sah(kon, principal, nilai):
    if not nilai:
        return ''
    if not re.fullmatch(r'chat_[0-9a-f]{32}', nilai):
        raise GalatForm('Tujuan tidak sah.', 404)
    chat = assistant_store.ambil_chat(kon, principal.id_akun, nilai)
    if chat is None or not assistant_view.hak_baca_chat(
        kon, principal.id_akun, chat, pemilik=principal.pengguna
    ):
        raise GalatForm('Tujuan tidak tersedia.', 404)
    return nilai

def _consent(kon, account_id):
    """Pilih izin provider terbaru; izin lama tidak hidup setelah pencabutan."""
    try:
        izin = kon.execute(
            "SELECT provider_id,policy_version,dicabut FROM persetujuan "
            "WHERE account_id=? AND kategori='chat_umum' ORDER BY versi DESC,rowid DESC LIMIT 1",
            (account_id,),
        ).fetchone()
    except sqlite3.OperationalError as galat:
        if "no such table" not in str(galat):
            raise
        return False
    return bool(izin is not None and izin['dicabut'] is None
                and izin['provider_id']==assistant_policy.PROVIDER_ID
                and izin['policy_version']==assistant_policy.VERSI_KEBIJAKAN)

def _daftar(kon, account_id):
    return assistant_view.riwayat(kon, account_id)[0]

def _akses_terkunci(account_id, *, sekarang=None):
    """Status generik sebelum konteks; default enforcement OFF tidak mengunci."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    hasil = assistant_entitlement_runtime.status(account_id, sekarang=kini)
    return hasil if hasil.enforcement_aktif and hasil.status not in {
        "trial_aktif", "pro_aktif",
    } else None

def _host_milik(principal, target):
    """Owner check minimum tanpa merakit payload konteks AI."""
    import database
    with database.buka() as kon:
        if target.jenis_host == "anak":
            return database.siswa_milik(kon, target.host_id, principal.pengguna)
        if target.jenis_host == "sesi":
            return database.sesi_milik(kon, target.host_id, principal.pengguna)
    return False

def fragmen_arsip_akun(principal, *, halaman: int = 1, chat_id: str = "") -> str:
    """Arsip chat umum lama untuk principal cookie bergenerasi yang sama."""
    if principal is None or principal.peran != "guru" or not principal.pengguna:
        return ""
    if not assistant_schema.BAWAAN.exists():
        return ""
    with assistant_schema.buka() as kon:
        if not _consent(kon, principal.id_akun):
            if chat_id:
                raise LookupError("arsip tidak tersedia")
            return ""
        chats, ada_lagi = assistant_view.riwayat_umum(
            kon, principal.id_akun, halaman=halaman,
        )
        dipilih = None
        pesan = ()
        if chat_id:
            if not re.fullmatch(r"chat_[0-9a-f]{32}", chat_id):
                raise LookupError("arsip tidak tersedia")
            calon = assistant_store.ambil_chat(kon, principal.id_akun, chat_id)
            if (
                calon is None or calon.context_kind is not None
                or not assistant_view.hak_baca_chat(
                    kon, principal.id_akun, calon, pemilik=principal.pengguna
                )
            ):
                raise LookupError("arsip tidak tersedia")
            dipilih = calon
            pesan = assistant_store.daftar_pesan(kon, principal.id_akun, calon.id)
        return assistant_components.arsip_percakapan_umum(
            chats, pesan=pesan, dipilih=dipilih,
            halaman=halaman, ada_lagi=ada_lagi,
        )

def fragmen_inline(
    principal, target, *, dalam_form: bool = False, galat: str = "",
    halaman_riwayat: int = 1,
) -> str:
    """Bangun fragmen host setelah ownership host diperiksa router.

    Chat dari query tetap harus cocok exact-resource dan lolos hak baca. Provider
    mati hanya menonaktifkan composer; persetujuan, histori lokal, dan host tetap
    dapat dibaca.
    """
    import database

    if principal is None or principal.pengguna == "" or principal.peran != "guru":
        raise LookupError("bantuan tidak tersedia")
    akses = _akses_terkunci(principal.id_akun)
    if akses is not None and not target.chat_id:
        return assistant_components.panel_akses(
            target, akses, dalam_form=dalam_form,
        )
    with database.buka() as kon_data:
        sumber = assistant_view.sumber_tampilan(
            kon_data, target.jenis_resource, target.resource_id,
            pemilik=principal.pengguna,
        )
        konteks = assistant_context.ambil(
            kon_data, target.jenis_resource, target.resource_id,
            pemilik=principal.pengguna,
        ) if sumber is not None else None
    if sumber is None or konteks is None:
        raise LookupError("bantuan tidak tersedia")
    if not assistant_schema.BAWAAN.exists():
        return assistant_components.panel_persetujuan(
            target, sumber=sumber, dalam_form=dalam_form, galat=galat,
        )
    with assistant_schema.buka() as kon:
        if not _consent(kon, principal.id_akun):
            return assistant_components.panel_persetujuan(
                target, sumber=sumber, dalam_form=dalam_form, galat=galat,
            )
        if not target.chat_id:
            return assistant_components.panel_konteks(
                target, konteks, sumber=sumber, dalam_form=dalam_form, galat=galat,
            )
        chat = assistant_store.ambil_chat(kon, principal.id_akun, target.chat_id)
        if (
            chat is None
            or chat.context_kind != target.jenis_resource
            or chat.context_id != target.resource_id
            or not assistant_view.hak_baca_chat(
                kon, principal.id_akun, chat, pemilik=principal.pengguna
            )
        ):
            raise LookupError("bantuan tidak tersedia")
        konteks_aktif = _konteks_chat(chat, principal.pengguna)
        hanya_baca = konteks_aktif is None
        usulan = []
        for item in assistant_store.daftar_usulan_chat(kon, principal.id_akun, chat.id):
            try:
                sesi_id = assistant_actions.ambil_hasil_usulan(
                    kon, principal.id_akun, principal.pengguna, item.id
                )
            except (LookupError, assistant_actions.GalatTindakan):
                sesi_id = None
            if sesi_id is not None:
                item = replace(item, sesi_id=sesi_id, status="selesai")
            if not hanya_baca or item.sesi_id is not None:
                usulan.append(item)
        operasi = kon.execute(
            """SELECT request_id, status FROM operasi
               WHERE account_id=? AND chat_id=?
               ORDER BY dibuat DESC, rowid DESC LIMIT 1""",
            (principal.id_akun, chat.id),
        ).fetchone()
        if not galat and not hanya_baca and operasi is not None and operasi["status"] == "gagal":
            kategori = ai_service.kategori_gagal_pendamping(principal.id_akun, operasi["request_id"])
            if kategori:
                galat = ai_errors.pesan_pendamping(kategori)
        riwayat, ada_lagi = assistant_view.riwayat(
            kon, principal.id_akun, halaman=halaman_riwayat,
            jenis_resource=target.jenis_resource,
            resource_id=target.resource_id,
        )
        return assistant_components.panel_chat(
            target, chat,
            assistant_store.daftar_pesan(kon, principal.id_akun, chat.id),
            riwayat, sumber=sumber, dalam_form=dalam_form, galat=galat,
            hanya_baca=hanya_baca,
            provider_aktif=assistant_service.tersedia(),
            entitlement_aktif=akses is None, usulan=tuple(usulan),
            status_memori=assistant_view.status_memori(kon, principal.id_akun, chat),
            versi_memori=assistant_store.versi_memori(kon, principal.id_akun),
            memori=assistant_store.daftar_memori(kon, principal.id_akun, termasuk_draft=False),
            draft_memori=tuple(
                item for item in assistant_store.daftar_memori(kon, principal.id_akun)
                if not item.dikonfirmasi and item.sumber_chat_id == chat.id
            ),
            operasi=operasi, halaman_riwayat=halaman_riwayat,
            ada_lagi=ada_lagi,
        )

def _chat_html(kon, principal, chat, *, galat='', request_id='', operasi_url=''):
    """Proyeksi baca terjaga; stale tidak mengaktifkan composer atau tindakan."""
    sumber = _sumber(chat, principal.pengguna)
    if chat.context_kind is not None and sumber is None:
        raise LookupError('chat tidak ditemukan')
    if not assistant_view.hak_baca_chat(
        kon, principal.id_akun, chat, pemilik=principal.pengguna
    ):
        return assistant_pages.halaman_konteks_berubah(sumber=sumber), 409
    konteks = _konteks_chat(chat, principal.pengguna)
    hanya_baca = chat.context_kind is not None and konteks is None
    # Hasil yang mengubah ringkasan anak tetap dapat diakses dari chat, tetapi
    # jangan tampilkan kandidat tindakan baru pada histori stale.
    usulan = []
    for item in assistant_store.daftar_usulan_chat(kon, principal.id_akun, chat.id):
        try:
            sesi_id = assistant_actions.ambil_hasil_usulan(kon,principal.id_akun,principal.pengguna,item.id)
        except (LookupError,assistant_actions.GalatTindakan):
            sesi_id = None
        if sesi_id is not None:
            # Proyeksi immutable saja: GET tidak finalisasi pointer privat.
            item = replace(item,sesi_id=sesi_id,status='selesai')
        if hanya_baca and item.sesi_id is None:
            continue
        usulan.append(item)
    draft = ()
    if not hanya_baca and chat.mode_memori != 'tanpa_memori' and assistant_store.penggunaan_memori_aktif(kon, principal.id_akun):
        draft = tuple(m for m in assistant_store.daftar_memori(kon, principal.id_akun)
                      if not m.dikonfirmasi and m.sumber_chat_id == chat.id)
    return assistant_pages.halaman_chat(
        chat, assistant_store.daftar_pesan(kon, principal.id_akun, chat.id),
        _daftar(kon, principal.id_akun), galat=galat,
        request_id=request_id or 'req_' + secrets.token_hex(16),
        draft=draft, konteks=konteks, usulan=tuple(usulan),
        status_memori=assistant_view.status_memori(kon, principal.id_akun, chat),
        sumber=sumber, hanya_baca=hanya_baca, operasi_url=operasi_url,
    ), 200








def tangani_get(penangan, jalur: str) -> bool:
    if not (jalur == '/pendamping' or jalur.startswith('/pendamping/')):
        return False
    if not aktif():
        _tidak_ada(penangan)
        return True
    principal = _principal(penangan)
    if principal is None:
        _tolak_login(penangan, assistant_navigation.tujuan_lanjut(jalur))
        return True
    try:
        query = _query(penangan)
        if jalur in ('/pendamping', '/pendamping/tanpa-memori'):
            if query:
                raise LookupError('parameter tidak tersedia')
            _redirect(penangan, '/guru')
            return True
        if jalur == '/pendamping/riwayat' or jalur.startswith('/pendamping/memori'):
            if query:
                raise LookupError('parameter tidak tersedia')
            _redirect(penangan, '/akun')
            return True
        cocok_konteks_lama = _POLA_KONTEKS.fullmatch(jalur)
        if cocok_konteks_lama:
            if query:
                raise LookupError('sumber tidak tersedia')
            jenis, resource_id = cocok_konteks_lama.groups()
            import database
            with database.buka() as kon_data:
                sumber = assistant_view.sumber_tampilan(
                    kon_data, jenis, resource_id, pemilik=principal.pengguna,
                )
            if sumber is None:
                raise LookupError('sumber tidak tersedia')
            if jenis == 'anak':
                target = assistant_inline.tujuan_anak(int(resource_id))
            elif jenis == 'sesi':
                target = assistant_inline.tujuan_sesi(int(resource_id))
            else:
                sesi_id, nomor = resource_id.split(':', 1)
                target = assistant_inline.tujuan_sesi(
                    int(sesi_id), nomor=int(nomor),
                )
            _redirect(penangan, target.jalur)
            return True
        cocok_chat_lama = _POLA_CHAT.fullmatch(jalur)
        if cocok_chat_lama:
            if query or not assistant_schema.BAWAAN.exists():
                raise LookupError('chat tidak tersedia')
            with assistant_schema.buka() as kon:
                chat = assistant_store.ambil_chat(
                    kon, principal.id_akun, cocok_chat_lama[1]
                )
                if chat is None or not assistant_view.hak_baca_chat(
                    kon, principal.id_akun, chat, pemilik=principal.pengguna
                ):
                    raise LookupError('chat tidak tersedia')
                if chat.context_kind is None:
                    _redirect(
                        penangan,
                        '/akun?section=arsip-pendamping&chat=' + chat.id,
                    )
                else:
                    _redirect(penangan, _target_chat_inline(chat).jalur)
            return True
        cocok_usulan_lama = _POLA_USULAN.fullmatch(jalur)
        cocok_operasi_lama = re.fullmatch(
            r'/pendamping/operasi/(req_[0-9A-Za-z_-]{8,80})', jalur
        )
        if cocok_usulan_lama or cocok_operasi_lama:
            if query or not assistant_schema.BAWAAN.exists():
                raise LookupError('sumber tidak tersedia')
            with assistant_schema.buka() as kon:
                if cocok_usulan_lama:
                    usulan = assistant_store.ambil_usulan(
                        kon, principal.id_akun, cocok_usulan_lama[1]
                    )
                    chat = None if usulan is None else assistant_store.ambil_chat(
                        kon, principal.id_akun, usulan.chat_id
                    )
                else:
                    operasi = kon.execute(
                        'SELECT chat_id,status FROM operasi WHERE request_id=? AND account_id=?',
                        (cocok_operasi_lama[1], principal.id_akun),
                    ).fetchone()
                    chat = None if operasi is None else assistant_store.ambil_chat(
                        kon, principal.id_akun, operasi['chat_id']
                    )
                if chat is None or chat.context_kind is None or not assistant_view.hak_baca_chat(
                    kon, principal.id_akun, chat, pemilik=principal.pengguna
                ):
                    raise LookupError('sumber tidak tersedia')
                target = _target_chat_inline(chat)
                sumber = _sumber(chat, principal.pengguna)
                if cocok_operasi_lama:
                    fragmen = fragmen_inline(principal, target)
                else:
                    sesi_hasil = assistant_actions.ambil_hasil_usulan(
                        kon, principal.id_akun, principal.pengguna, usulan.id
                    )
                    if sesi_hasil is not None:
                        fragmen = assistant_components.panel_hasil(
                            target, chat, sesi_hasil, sumber=sumber,
                        )
                    else:
                        token_tinjau = assistant_actions.tinjau_usulan(
                            kon, principal.id_akun, principal.pengguna, usulan.id,
                            sekarang=int(time.time()),
                        )
                        fragmen = assistant_components.panel_tinjauan(
                            target, chat, usulan, token_tinjau, sumber=sumber,
                        )
                _render_host_dengan_fragmen(
                    penangan, principal, target, fragmen,
                )
            return True
        if not assistant_service.tersedia():
            _kirim_privat(penangan, assistant_pages.halaman_tidak_aktif(), 503)
            return True
        # Semua pola URL yang dikenal sudah ditangani di atas. Pertahankan
        # fallback lama: provider belum siap -> 503, belum consent -> form,
        # selebihnya 404. Tidak ada renderer standalone kedua setelah redirect.
        with _siapkan_db() as kon:
            if not _consent(kon, principal.id_akun):
                _kirim_privat(penangan, assistant_pages.halaman_persetujuan())
                return True
            raise LookupError('chat tidak tersedia')
    except (LookupError, GalatForm):
        _tidak_ada(penangan)
    except ValueError:
        _tidak_ada(penangan)
    return True

def tangani_post(penangan, jalur: str) -> bool:
    if not (jalur == "/pendamping" or jalur.startswith("/pendamping/")):
        return False
    if not aktif():
        _tidak_ada(penangan)
        return True
    principal = _principal(penangan)
    if principal is None:
        _tolak_login(penangan)
        return True
    # Endpoint obrolan umum lama ditutup sebelum provider/store. Body tetap
    # diparse dengan batas/CSRF existing, tetapi tidak boleh membuat chat/pesan.
    if jalur == "/pendamping/chat-baru":
        try:
            _baca_form(penangan)
        except GalatForm as galat:
            _kirim_privat(penangan, assistant_pages._bingkai(
                "Permintaan ditolak", '<h1 id="judul-pendamping">Permintaan ditolak</h1>'
                '<p role="alert">Permintaan bantuan tidak dapat diproses.</p>'
            ), galat.status)
            return True
        _kirim_privat(penangan, assistant_pages._bingkai(
            "Percakapan umum ditutup",
            '<h1 id="judul-pendamping">Percakapan umum baru sudah ditutup</h1>'
            '<p>Pilih anak atau sesi dari <a href="/guru">ruang orang tua</a> untuk memakai bantuan terkait.</p>',
        ), 410)
        return True
    cocok_pesan_lama = _POLA_PESAN.fullmatch(jalur)
    if cocok_pesan_lama:
        # Form lama berkonteks masih menjadi adapter aman ke layanan yang sama;
        # chat umum tanpa resource ditutup dan tidak pernah mencapai provider.
        if not assistant_schema.BAWAAN.exists():
            _tidak_ada(penangan)
            return True
        with assistant_schema.buka() as kon:
            chat_lama = assistant_store.ambil_chat(
                kon, principal.id_akun, cocok_pesan_lama[1]
            )
        if chat_lama is None or chat_lama.context_kind is None:
            try:
                _baca_form(penangan)
            except GalatForm as galat:
                _kirim_privat(penangan, assistant_pages._bingkai(
                    "Permintaan ditolak", '<h1 id="judul-pendamping">Permintaan ditolak</h1>'
                    '<p role="alert">Permintaan bantuan tidak dapat diproses.</p>'
                ), galat.status)
                return True
            _kirim_privat(penangan, assistant_pages._bingkai(
                "Formulir lama ditutup",
                '<h1 id="judul-pendamping">Formulir percakapan lama sudah ditutup</h1>'
                '<p>Buka bantuan dari profil anak atau pemeriksaan sesi. Pesan ini tidak dikirim.</p>',
            ), 410)
            return True
    if not assistant_service.tersedia():
        _kirim_privat(penangan, assistant_pages.halaman_tidak_aktif(), 503)
        return True
    try:
        _batasi_laju(penangan, principal.id_akun)
        data = _baca_form(penangan)
    except GalatForm as galat:
        _kirim_privat(
            penangan,
            assistant_pages._bingkai(
                "Permintaan ditolak",
                f'<section class="pendamping-panel"><h1 id="judul-pendamping">Permintaan ditolak</h1><p>{html.escape(str(galat))}</p></section>',
            ),
            galat.status,
        )
        return True

    kini = int(time.time())
    with _siapkan_db() as kon:
        if jalur == "/pendamping/persetujuan":
            lanjut = assistant_navigation.tujuan_lanjut(data.get('lanjut', ''))
            if data.get('lanjut') and not lanjut:
                _tidak_ada(penangan)
                return True
            sumber = None
            if lanjut and lanjut != '/pendamping':
                import database
                cocok = _POLA_KONTEKS.fullmatch(lanjut)
                with database.buka() as kon_data:
                    sumber = assistant_view.sumber_tampilan(kon_data, cocok[1], cocok[2], pemilik=principal.pengguna)
                if sumber is None:
                    _tidak_ada(penangan)
                    return True
            if set(data) - {"setuju", "kebijakan", "lanjut"} or data.get("setuju") != "1" or data.get("kebijakan") != assistant_policy.VERSI_KEBIJAKAN:
                _kirim_privat(penangan, assistant_pages.halaman_persetujuan("Persetujuan tidak lengkap.", lanjut=lanjut,sumber=sumber), 400)
                return True
            assistant_store.beri_persetujuan(
                kon, principal.id_akun,
                policy_version=assistant_policy.VERSI_KEBIJAKAN,
                provider_id=assistant_policy.PROVIDER_ID,
                kategori="chat_umum", sekarang=kini,
            )
            kon.commit()
            _redirect(penangan, lanjut or "/pendamping")
            return True

        if not _consent(kon, principal.id_akun):
            _kirim_privat(penangan, assistant_pages.halaman_persetujuan(), 409)
            return True

        if jalur == "/pendamping/konteks/pilih":
            wajib = {
                "jenis", "resource_id", "resource_version", "kategori", "mode"
            }
            if set(data) != wajib or data.get('mode') not in ('aktif','tanpa_memori'):
                _tidak_ada(penangan)
                return True
            import database

            with database.buka() as kon_data:
                konteks = assistant_context.ambil(
                    kon_data,
                    data["jenis"],
                    data["resource_id"],
                    pemilik=principal.pengguna,
                )
            if (
                konteks is None
                or konteks.versi != data["resource_version"]
                or konteks.kategori != data["kategori"]
            ):
                _tidak_ada(penangan)
                return True
            persetujuan = assistant_store.beri_persetujuan_konteks(
                kon,
                principal.id_akun,
                jenis=konteks.jenis,
                resource_id=konteks.resource_id,
                resource_version=konteks.versi,
                kategori=konteks.kategori,
                sekarang=kini,
            )
            chat = assistant_store.buat_chat(
                kon,
                principal.id_akun,
                data["mode"],
                sekarang=kini,
                context_kind=konteks.jenis,
                context_id=konteks.resource_id,
                context_version=persetujuan.versi,
                context_resource_version=konteks.versi,
                context_category=konteks.kategori,
            )
            _redirect(penangan, _target_chat_inline(chat).jalur)
            return True

        if jalur in (
            "/pendamping/memori/aktifkan",
            "/pendamping/memori/nonaktifkan",
            "/pendamping/memori/hapus-semua",
        ):
            try:
                kembali = _kembali_sah(kon,principal,data.get('kembali',''))
            except GalatForm:
                _tidak_ada(penangan)
                return True
            if set(data) - {'versi','kembali','persetujuan_hapus'} or not data.get('versi','').isdigit():
                _kirim_privat(penangan, assistant_pages.halaman_memori(
                    assistant_store.daftar_memori(kon, principal.id_akun),
                    aktif=assistant_store.penggunaan_memori_aktif(kon, principal.id_akun),
                    versi=assistant_store.versi_memori(kon, principal.id_akun),
                    galat="Versi memori tidak sah.", kembali=kembali,
                ), 400)
                return True
            if jalur.endswith('hapus-semua') and data.get('persetujuan_hapus') != '1':
                memori = assistant_store.daftar_memori(kon, principal.id_akun)
                if not memori:
                    _tidak_ada(penangan)
                    return True
                _kirim_privat(penangan,assistant_pages.halaman_hapus_memori(
                    memori,
                    versi=assistant_store.versi_memori(kon,principal.id_akun),semua=True,kembali=kembali),400)
                return True
            versi = int(data["versi"])
            try:
                if jalur.endswith("hapus-semua"):
                    assistant_store.hapus_semua_memori(
                        kon, principal.id_akun, versi_diharapkan=versi,
                        sekarang=kini,
                    )
                else:
                    assistant_store.atur_penggunaan_memori(
                        kon,
                        principal.id_akun,
                        jalur == "/pendamping/memori/aktifkan",
                        versi_diharapkan=versi,
                        sekarang=kini,
                    )
            except ValueError:
                _kirim_privat(penangan, assistant_pages.halaman_memori(
                    assistant_store.daftar_memori(kon, principal.id_akun),
                    aktif=assistant_store.penggunaan_memori_aktif(kon, principal.id_akun),
                    versi=assistant_store.versi_memori(kon, principal.id_akun),
                    galat="Memori berubah. Muat ulang lalu coba lagi.", kembali=kembali,
                ), 409)
                return True
            kon.commit()
            _redirect(penangan, '/pendamping/memori'+('?kembali='+kembali if kembali else ''))
            return True

        cocok_memori = _POLA_MEMORI.fullmatch(jalur)
        if cocok_memori:
            memori_id, aksi = cocok_memori.groups()
            field = {"versi", "kembali", "persetujuan_hapus"} if aksi in ("konfirmasi", "hapus") else {"versi", "isi", "kembali"}
            if set(data) - field or "versi" not in data or not data["versi"].isdigit():
                _tidak_ada(penangan)
                return True
            try:
                kembali = _kembali_sah(kon,principal,data.get('kembali',''))
            except GalatForm:
                _tidak_ada(penangan)
                return True
            item = next((m for m in assistant_store.daftar_memori(kon,principal.id_akun) if m.id==memori_id),None)
            if item is None:
                _tidak_ada(penangan)
                return True
            if aksi=='hapus' and data.get('persetujuan_hapus')!='1':
                _kirim_privat(penangan,assistant_pages.halaman_hapus_memori((item,),versi=item.versi,kembali=kembali),400)
                return True
            versi = int(data["versi"])
            if aksi == "konfirmasi":
                berhasil = assistant_store.konfirmasi_memori(
                    kon, principal.id_akun, memori_id,
                    versi_diharapkan=versi, sekarang=kini,
                )
            elif aksi == "ubah":
                berhasil = assistant_store.ubah_memori(
                    kon, principal.id_akun, memori_id, data.get("isi", ""),
                    versi_diharapkan=versi, sekarang=kini,
                )
            else:
                berhasil = assistant_store.hapus_memori(
                    kon, principal.id_akun, memori_id,
                    versi_diharapkan=versi, sekarang=kini,
                )
            if not berhasil:
                if aksi == 'ubah':
                    _kirim_privat(penangan,assistant_pages.halaman_edit_memori(
                        item,galat='Koreksi belum disimpan. Gunakan bentuk preferensi yang didukung atau muat ulang catatan.',kembali=kembali),404)
                else:
                    _tidak_ada(penangan)
                return True
            tujuan = (f'/pendamping/chat/{kembali}' if kembali and aksi == 'konfirmasi' else
                      '/pendamping/memori'+('?kembali='+kembali if kembali else ''))
            kon.commit()
            _redirect(penangan, tujuan)
            return True

        cocok_konfirmasi = _POLA_KONFIRMASI_USULAN.fullmatch(jalur)
        if cocok_konfirmasi:
            if (
                set(data) != {"versi", "hash", "request_id"}
                or not data["versi"].isdigit()
                or not re.fullmatch(r"[0-9a-f]{64}", data["hash"])
                or not re.fullmatch(r"aksi_[0-9a-f]{32}", data["request_id"])
            ):
                _tidak_ada(penangan)
                return True
            try:
                sesi_id = assistant_actions.konfirmasi_dan_buat_sesi(
                    kon,
                    principal.id_akun,
                    principal.pengguna,
                    cocok_konfirmasi[1],
                    versi=int(data["versi"]),
                    hash_diharapkan=data["hash"],
                    request_id=data["request_id"],
                    sekarang=kini,
                )
            except LookupError:
                _tidak_ada(penangan)
                return True
            except assistant_actions.GalatTindakan as galat:
                catatan = assistant_store.ambil_usulan(kon,principal.id_akun,cocok_konfirmasi[1])
                _usulan_berubah(penangan, galat, chat_id=catatan.chat_id if catatan else '',usulan_id=cocok_konfirmasi[1])
                return True
            _redirect(penangan, f"/sesi/{sesi_id}")
            return True

        cocok = _POLA_PESAN.fullmatch(jalur)
        if not cocok or set(data) != {'pesan','request_id'}:
            _tidak_ada(penangan)
            return True
        chat = assistant_store.ambil_chat(kon,principal.id_akun,cocok[1])
        if chat is None:
            _tidak_ada(penangan)
            return True
        sumber = _sumber(chat,principal.pengguna)
        if chat.context_kind is not None and sumber is None:
            _tidak_ada(penangan)
            return True
        request_id=data['request_id']
        if not re.fullmatch(r'req_[0-9A-Za-z_-]{8,80}',request_id):
            try:
                isi,kode=_chat_html(kon,principal,chat,galat='Penanda permintaan tidak sah.')
            except LookupError:
                _tidak_ada(penangan)
                return True
            _kirim_privat(penangan,isi,400 if kode==200 else kode)
            return True
        konteks=_konteks_chat(chat,principal.pengguna)
        if chat.context_kind is not None and (konteks is None or not assistant_view.hak_baca_chat(
            kon,principal.id_akun,chat,pemilik=principal.pengguna
        )):
            _kirim_privat(penangan,assistant_pages.halaman_konteks_berubah(sumber=sumber),409)
            return True
        try:
            assistant_service.kirim_pesan(
                kon,principal.id_akun,chat.id,data['pesan'],request_id=request_id,
                sekarang=kini,konteks=konteks,
                validasi_konteks=None if konteks is None else lambda: _versi_konteks_chat(chat,principal.pengguna),
            )
        except (assistant_service.GalatPendamping,ValueError) as galat:
            operasi=kon.execute('SELECT status FROM operasi WHERE request_id=? AND account_id=? AND chat_id=?',
                                (request_id,principal.id_akun,chat.id)).fetchone()
            if operasi and operasi['status']=='pending':
                _kirim_privat(penangan,assistant_pages.halaman_status_operasi('pending',chat_id=chat.id,request_id=request_id),503)
                return True
            try:
                isi,kode=_chat_html(kon,principal,chat,galat=str(galat),
                                    operasi_url='')
            except LookupError:
                _tidak_ada(penangan)
                return True
            if kode != 200:
                # Tidak render transkrip setelah izin berubah saat network.
                _usulan_berubah(penangan, galat)
            else:
                _kirim_privat(penangan,isi,503 if isinstance(galat,assistant_service.GalatPendamping) else 400)
            return True
        kon.commit()
        _redirect(penangan, _target_chat_inline(chat).jalur)
        return True
