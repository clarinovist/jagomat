"""Fragmen HTML Pendamping untuk host orang tua; tidak membuka DB/provider."""

from __future__ import annotations

import html
import secrets
import urllib.parse

import assistant_policy
import assistant_view


def _esc(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _hidden(nama: str, nilai, *, form_id: str = "") -> str:
    atribut_form = f' form="{_esc(form_id)}"' if form_id else ""
    return f'<input type="hidden" name="{_esc(nama)}" value="{_esc(nilai)}"{atribut_form}>'


def _wadah_form(isi: str, action: str, *, dalam_form: bool) -> str:
    if dalam_form:
        return isi
    return f'<form method="post" action="{_esc(action)}">{isi}</form>'


def _identitas_target(target) -> str:
    return (
        _hidden("inline_host", target.jenis_host)
        + _hidden("inline_host_id", target.host_id)
        + _hidden("inline_posisi", target.posisi)
        + (_hidden("inline_nomor", target.nomor) if target.nomor is not None else "")
    )


def panel_persetujuan(target, *, sumber, dalam_form: bool = False, galat: str = "") -> str:
    isi = (
        _identitas_target(target)
        + _hidden("kebijakan", assistant_policy.VERSI_KEBIJAKAN)
        + (f'<p class="pendamping-galat" role="alert">{_esc(galat)}</p>' if galat else "")
        + '<p>Pendamping Jagomat mengirim pesan bantuan ke DeepSeek. Jangan tulis email, nomor telepon, sandi, token, atau data pribadi anak.</p>'
        + '<p>Riwayat disimpan sampai 180 hari sejak aktivitas terakhir. Penghapusan aktif segera; salinan cadangan dapat bertahan maksimal 30 hari.</p>'
        + '<p>Jawaban AI dapat keliru. Izin untuk sumber belajar ini diminta terpisah sesudahnya. '
          '<a href="/kebijakan-privasi">Baca penjelasan privasi lengkap</a>.</p>'
        + '<label class="pendamping-cek"><input type="checkbox" name="setuju" value="1">'
          '<span>Saya memahami dan setuju memakai Pendamping Jagomat.</span></label>'
        + '<button class="pendamping-tombol" type="submit" formaction="/pendamping/inline/persetujuan">Setuju dan lanjutkan</button>'
    )
    return _panel(target, "Sebelum memakai bantuan", _wadah_form(isi, "/pendamping/inline/persetujuan", dalam_form=dalam_form), sumber=sumber, dalam_form=dalam_form)


def panel_konteks(target, konteks, *, sumber, dalam_form: bool = False, galat: str = "") -> str:
    penjelasan = {
        "soal": "Teks soal resmi, kunci, dan pembahasan akan dikirim ke layanan AI eksternal untuk Pendamping Jagomat. Jawaban dan cara anak tidak ikut dikirim.",
        "sesi": "Ringkasan topik, status, level, dan jumlah soal sesi akan dikirim ke layanan AI eksternal untuk Pendamping Jagomat; bukan jawaban atau koreksi anak.",
        "anak": "Ringkasan netral tahap, level, dan tanggal ketersediaan akan dikirim ke layanan AI eksternal untuk Pendamping Jagomat; bukan seluruh catatan anak.",
    }[konteks.jenis]
    isi = (
        _identitas_target(target)
        + _hidden("resource_version", konteks.versi)
        + _hidden("kategori", konteks.kategori)
        + _hidden("request_id", "buka_" + secrets.token_hex(16))
        + (f'<p class="pendamping-galat" role="alert">{_esc(galat)}</p>' if galat else "")
        + f'<p>{_esc(penjelasan)}</p>'
        + '<label class="pendamping-cek"><input type="checkbox" name="setuju_konteks" value="1">'
          '<span>Gunakan sumber ini untuk percakapan baru.</span></label>'
        + '<div class="pendamping-aksi">'
          '<button class="pendamping-tombol" type="submit" name="mode_chat" value="aktif" formaction="/pendamping/inline/mulai">Mulai percakapan terkait</button>'
          '<button class="pendamping-tombol pendamping-sekunder" type="submit" name="mode_chat" value="tanpa_memori" formaction="/pendamping/inline/mulai">Mulai tanpa memori</button></div>'
    )
    return _panel(target, "Pilih sumber bantuan", _wadah_form(isi, "/pendamping/inline/mulai", dalam_form=dalam_form), sumber=sumber, dalam_form=dalam_form)


def _tombol_aksi(target, chat_id: str, action: str, label: str, *,
                  dalam_form: bool, field=(), kelas: str = "pendamping-tombol") -> str:
    if dalam_form:
        muatan = urllib.parse.urlencode(tuple(field))
        atribut = f' name="data_aksi" value="{_esc(muatan)}"' if muatan else ""
        return (
            f'<button class="{_esc(kelas)}" type="submit"{atribut} '
            f'formaction="{_esc(action)}">{_esc(label)}</button>'
        )
    isi = _identitas_target(target) + _hidden("chat", chat_id)
    isi += "".join(_hidden(nama, nilai) for nama, nilai in field)
    isi += f'<button class="{_esc(kelas)}" type="submit" formaction="{_esc(action)}">{_esc(label)}</button>'
    return _wadah_form(isi, action, dalam_form=False)


def _kartu_usulan_inline(target, chat, usulan, *, dalam_form: bool) -> str:
    kartu = []
    for item in usulan:
        data = assistant_view.ringkasan_usulan(item.payload_json)
        if item.sesi_id is not None:
            aksi = f'<a class="pendamping-tombol" href="/sesi/{int(item.sesi_id)}">Buka latihan #{int(item.sesi_id)}</a>'
            catatan = "Latihan bebas sudah dibuat; membuka lagi tidak membuat sesi kedua."
        else:
            aksi = _tombol_aksi(
                target, chat.id, "/pendamping/inline/tinjau", "Tinjau usulan",
                dalam_form=dalam_form, field=(("usulan", item.id),),
            )
            catatan = "Belum ada sesi. Tinjau lalu konfirmasi secara eksplisit."
        kartu.append(
            '<aside class="pendamping-usulan"><h4>Usulan latihan bebas</h4>'
            f'<p>{_esc(data["topik"])} · {_esc(data["level"])} · {_esc(data["jumlah"])} soal</p>'
            f'<p class="pendamping-catatan">{_esc(catatan)}</p>{aksi}</aside>'
        )
    return "".join(kartu)


def _draft_memori_inline(target, chat, draft, *, dalam_form: bool) -> str:
    hasil = []
    for item in draft:
        field = (("memori", item.id), ("versi_item", item.versi))
        hasil.append(
            '<aside class="pendamping-memori"><h4>Simpan preferensi ini?</h4>'
            f'<p class="pendamping-teks">{_esc(item.isi)}</p><div class="pendamping-aksi">'
            + _tombol_aksi(target, chat.id, "/pendamping/inline/konfirmasi-memori",
                           "Konfirmasi memori", dalam_form=dalam_form, field=field)
            + _tombol_aksi(target, chat.id, "/pendamping/inline/tinjau-hapus-memori",
                           "Tinjau cara mengabaikan", dalam_form=dalam_form,
                           field=field,
                           kelas="pendamping-tombol pendamping-sekunder")
            + '</div></aside>'
        )
    return "".join(hasil)


def _kontrol_memori(target, chat, memori, *, status_memori: str, versi_memori: int,
                     dalam_form: bool) -> str:
    aktif = status_memori.startswith("Memori aktif")
    aksi = "nonaktifkan-memori" if aktif else "aktifkan-memori"
    label = "Nonaktifkan memori" if aktif else "Aktifkan memori"
    tombol = _tombol_aksi(
        target, chat.id, f"/pendamping/inline/{aksi}", label,
        dalam_form=dalam_form, field=(("versi_memori", versi_memori),),
        kelas="pendamping-tombol pendamping-sekunder",
    )
    daftar_baris = []
    for item in memori:
        if not item.dikonfirmasi:
            continue
        nama_isi = f"isi_memori_{item.id}"
        if dalam_form:
            kontrol = (
                f'<label>Isi preferensi<textarea name="{_esc(nama_isi)}">{_esc(item.isi)}</textarea></label>'
                '<div class="pendamping-aksi">'
                + _tombol_aksi(target, chat.id, "/pendamping/inline/ubah-memori", "Simpan koreksi",
                               dalam_form=True, field=(("memori", item.id), ("versi_item", item.versi),
                                                        ("isi_field", nama_isi)))
                + _tombol_aksi(target, chat.id, "/pendamping/inline/tinjau-hapus-memori", "Tinjau penghapusan",
                               dalam_form=True, field=(("memori", item.id), ("versi_item", item.versi)),
                               kelas="pendamping-tombol pendamping-sekunder")
                + '</div>'
            )
        else:
            kontrol = (
                '<form method="post" action="/pendamping/inline/ubah-memori">'
                + _identitas_target(target) + _hidden("chat", chat.id)
                + _hidden("memori", item.id) + _hidden("versi_item", item.versi)
                + f'<label>Isi preferensi<textarea name="isi_memori">{_esc(item.isi)}</textarea></label>'
                '<button class="pendamping-tombol" type="submit">Simpan koreksi</button></form>'
                + _tombol_aksi(target, chat.id, "/pendamping/inline/tinjau-hapus-memori", "Tinjau penghapusan",
                               dalam_form=False, field=(("memori", item.id), ("versi_item", item.versi)),
                               kelas="pendamping-tombol pendamping-sekunder")
            )
        daftar_baris.append('<article class="pendamping-memori">' + kontrol + '</article>')
    daftar = "".join(daftar_baris)
    return (
        '<details class="pendamping-memori"><summary>Preferensi</summary>'
        f'<p>{_esc(status_memori)}</p>' + tombol + daftar + '</details>'
    )


def panel_chat(target, chat, pesan, riwayat, *, sumber, dalam_form: bool = False,
               galat: str = "", hanya_baca: bool = False, provider_aktif: bool = True,
               usulan=(), status_memori: str = "", versi_memori: int = 0,
               memori=(), draft_memori=(), operasi=None,
               halaman_riwayat: int = 1, ada_lagi: bool = False) -> str:
    identitas_form = (
        _identitas_target(target) + _hidden("chat", chat.id)
        if dalam_form else ""
    )
    transkrip = "".join(
        '<article class="pendamping-pesan ' + ("pengguna" if item.peran == "pengguna" else "asisten") + '"'
        f' data-request-id="{_esc(getattr(item, "request_id", None) or "")}">'
        f'<h3 class="pendamping-peran">{"Kamu" if item.peran == "pengguna" else "Pendamping"}</h3>'
        f'<p class="pendamping-teks">{_esc(item.teks)}</p></article>'
        for item in pesan
    )
    if dalam_form:
        daftar = "".join(
            '<button type="submit" name="pilih_chat" value="' + _esc(item.id)
            + '" formaction="/pendamping/inline/riwayat"'
            + (' aria-current="page"' if item.id == chat.id else '') + '>'
            + _esc(assistant_view.label_chat(item)) + '</button>' for item in riwayat
        )
    else:
        daftar = "".join(
            '<a href="' + _esc(_jalur_chat(target, item.id)) + '"'
            + (' aria-current="page"' if item.id == chat.id else '') + '>'
            + _esc(assistant_view.label_chat(item)) + '</a>' for item in riwayat
        )
    navigasi_halaman = ""
    tombol_halaman = []
    if halaman_riwayat > 1:
        tombol_halaman.append((halaman_riwayat - 1, "Sebelumnya"))
    if ada_lagi:
        tombol_halaman.append((halaman_riwayat + 1, "Berikutnya"))
    for nomor, label_halaman in tombol_halaman:
        navigasi_halaman += _tombol_aksi(
            target, chat.id, "/pendamping/inline/riwayat", label_halaman,
            dalam_form=dalam_form, field=(("halaman", nomor),),
            kelas="pendamping-tautan",
        )
    histori = (
        '<details class="pendamping-riwayat"><summary>Riwayat terkait</summary>'
        f'<nav aria-label="Percakapan sumber ini">{daftar}</nav>'
        f'<p class="pendamping-catatan">Halaman {halaman_riwayat}</p>{navigasi_halaman}</details>'
    )
    status = ""
    composer = ""
    if galat:
        status = f'<p class="pendamping-galat" role="alert">{_esc(galat)}</p>'
    if hanya_baca:
        status += '<p class="pendamping-info" role="status">Sumber berubah. Percakapan ini hanya dapat dibaca.</p>'
    elif operasi is not None and operasi["status"] == "pending":
        status += '<p class="pendamping-info" role="status">Jawaban masih ditunggu. Jangan kirim ulang pesan yang sama.</p>'
        status += _tombol_aksi(
            target, chat.id, "/pendamping/inline/status", "Periksa status",
            dalam_form=dalam_form, field=(("request_id", operasi["request_id"]),),
        )
    elif not provider_aktif:
        status += '<p class="pendamping-info" role="status">Pengiriman AI sedang tidak tersedia. Pekerjaan belajar tetap dapat digunakan.</p>'
    else:
        if operasi is not None and operasi["status"] == "gagal":
            status += '<p class="pendamping-galat" role="status">Jawaban sebelumnya belum tersedia. Kamu boleh menulis pesan baru.</p>'
        isi = (
            ("" if dalam_form else _identitas_target(target) + _hidden("chat", chat.id))
            + _hidden("request_id", "req_" + secrets.token_hex(16))
            + '<div class="pendamping-composer">'
              '<label class="pendamping-label" for="pesan-inline">Pesan untuk Pendamping</label>'
              '<textarea id="pesan-inline" name="pesan" rows="5" maxlength="8000"></textarea>'
              '<button class="pendamping-tombol" type="submit" formaction="/pendamping/inline/pesan">Kirim</button>'
              '</div>'
        )
        composer = _wadah_form(isi, "/pendamping/inline/pesan", dalam_form=dalam_form)
    kontrol_memori = _kontrol_memori(
        target, chat, memori, status_memori=status_memori,
        versi_memori=versi_memori, dalam_form=dalam_form,
    ) if status_memori and not hanya_baca else ""
    draft_memori_html = _draft_memori_inline(
        target, chat, draft_memori, dalam_form=dalam_form,
    ) if not hanya_baca and chat.mode_memori != "tanpa_memori" else ""
    return _panel(
        target, "Bantuan terkait", identitas_form + status + histori
        + f'<div class="pendamping-transkrip">{transkrip}</div>'
        + _kartu_usulan_inline(target, chat, usulan, dalam_form=dalam_form)
        + draft_memori_html + composer + kontrol_memori,
        sumber=sumber, dalam_form=dalam_form, chat_id=chat.id,
    )


def panel_tinjauan_hapus_memori(
    target, chat, item, *, sumber, dalam_form: bool = False, galat: str = "",
) -> str:
    """Tinjauan inline sebelum preferensi aktif maupun draft dihapus."""
    jenis = "draft preferensi" if not item.dikonfirmasi else "preferensi aktif"
    identitas = _identitas_target(target) + _hidden("chat", chat.id)
    field = (("memori", item.id), ("versi_item", item.versi))
    if dalam_form:
        identitas_kontrol = identitas
        tombol_hapus = _tombol_aksi(
            target, chat.id, "/pendamping/inline/hapus-memori", "Ya, hapus catatan",
            dalam_form=True, field=field,
            kelas="pendamping-tombol pendamping-sekunder",
        )
        tombol_batal = _tombol_aksi(
            target, chat.id, "/pendamping/inline/batal-hapus-memori", "Batal",
            dalam_form=True, kelas="pendamping-tautan",
        )
    else:
        identitas_kontrol = identitas + "".join(_hidden(nama, nilai) for nama, nilai in field)
        tombol_hapus = (
            '<button class="pendamping-tombol pendamping-sekunder" type="submit" '
            'formaction="/pendamping/inline/hapus-memori">Ya, hapus catatan</button>'
        )
        tombol_batal = (
            '<button class="pendamping-tautan" type="submit" '
            'formaction="/pendamping/inline/batal-hapus-memori" formnovalidate>Batal</button>'
        )
    isi = (
        identitas_kontrol
        + (f'<p class="pendamping-galat" role="alert">{_esc(galat)}</p>' if galat else "")
        + f'<p>Kamu akan menghapus <b>{_esc(jenis)}</b> versi {int(item.versi)}:</p>'
        + f'<blockquote class="pendamping-teks">{_esc(item.isi)}</blockquote>'
        + '<p class="pendamping-catatan">Catatan ini tidak lagi dipakai sebagai preferensi. '
          'Chat sumber tetap ada. Salinan cadangan dapat bertahan maksimal 30 hari.</p>'
        + '<label class="pendamping-cek"><input type="checkbox" name="persetujuan_hapus" value="1">'
          '<span>Saya memahami konsekuensinya dan ingin menghapus catatan ini.</span></label>'
        + f'<div class="pendamping-aksi">{tombol_hapus}{tombol_batal}</div>'
    )
    if not dalam_form:
        isi = _wadah_form(isi, "/pendamping/inline/hapus-memori", dalam_form=False)
    return _panel(
        target, "Tinjau penghapusan memori", isi,
        sumber=sumber, dalam_form=dalam_form,
    )


def arsip_percakapan_umum(chats, *, pesan=(), dipilih=None,
                          halaman: int = 1, ada_lagi: bool = False) -> str:
    """Disclosure akun untuk chat umum lama; metadata dahulu, satu transkrip dipilih."""
    if not chats:
        return ""
    daftar = "".join(
        '<li><a href="/akun?section=arsip-pendamping&amp;chat=' + _esc(chat.id) + '">'
        + _esc(assistant_view.label_chat(chat)) + '</a></li>'
        for chat in chats
    )
    navigasi = []
    if halaman > 1:
        navigasi.append(
            f'<a href="/akun?section=arsip-pendamping&amp;halaman={halaman - 1}">Sebelumnya</a>'
        )
    if ada_lagi:
        navigasi.append(
            f'<a href="/akun?section=arsip-pendamping&amp;halaman={halaman + 1}">Berikutnya</a>'
        )
    transkrip = ""
    if dipilih is not None:
        isi_pesan = "".join(
            '<article class="pendamping-pesan '
            + ("pengguna" if item.peran == "pengguna" else "asisten") + '">'
            f'<h3>{"Kamu" if item.peran == "pengguna" else "Pendamping"}</h3>'
            f'<p class="pendamping-teks">{_esc(item.teks)}</p></article>'
            for item in pesan
        )
        transkrip = (
            '<section aria-labelledby="judul-transkrip-lama">'
            '<h3 id="judul-transkrip-lama">Transkrip yang dipilih</h3>'
            f'<p>{_esc(assistant_view.label_chat(dipilih))}</p>'
            f'<div class="pendamping-transkrip">{isi_pesan}</div></section>'
        )
    return (
        '<div class="kartu pendamping-arsip"><details open>'
        '<summary>Arsip percakapan lama</summary>'
        '<p class="sub">Percakapan umum lama hanya dapat dibaca. Arsip ini tidak '
        'terhubung ke anak dan tidak dapat dipakai untuk mengirim pesan baru.</p>'
        f'<ul>{daftar}</ul><nav aria-label="Halaman arsip">{" · ".join(navigasi)}</nav>'
        f'{transkrip}</details></div>'
    )


def panel_tinjauan(target, chat, usulan, token: str, *, sumber,
                    dalam_form: bool = False, galat: str = "") -> str:
    data = assistant_view.ringkasan_usulan(usulan.payload_json)
    materi = "".join(
        f'<li>{_esc(label)} · {_esc(jumlah)} soal</li>'
        for label, jumlah, _template in data["materi"]
    )
    isi = (
        (_identitas_target(target) + _hidden("chat", chat.id) if dalam_form else "")
        + (f'<p class="pendamping-galat" role="alert">{_esc(galat)}</p>' if galat else "")
        + f'<p><b>{_esc(data["topik"])}</b> · {_esc(data["level"])} · {_esc(data["jumlah"])} soal</p>'
        + f'<ul>{materi}</ul><p class="pendamping-catatan">Ini latihan bebas dan tidak menjadi bukti atau mengubah rencana terpandu.</p>'
        + _tombol_aksi(
            target, chat.id, "/pendamping/inline/konfirmasi-usulan",
            "Konfirmasi dan buat latihan", dalam_form=dalam_form,
            field=(("usulan", usulan.id), ("versi_usulan", usulan.versi),
                   ("hash_usulan", usulan.hash_usulan), ("request_id", token)),
        )
    )
    return _panel(target, "Tinjau usulan latihan", isi, sumber=sumber, dalam_form=dalam_form)


def panel_hasil(target, chat, sesi_id: int, *, sumber, dalam_form: bool = False) -> str:
    identitas = (
        _identitas_target(target) + _hidden("chat", chat.id)
        if dalam_form else ""
    )
    return _panel(
        target, "Latihan siap", identitas
        + f'<p role="status">Latihan bebas #{int(sesi_id)} sudah dibuat.</p>'
        '<p class="pendamping-catatan">Hasil ini tidak menjadi bukti atau mengubah reducer siklus belajar.</p>'
        f'<a class="pendamping-tombol" href="/sesi/{int(sesi_id)}">Buka latihan</a>',
        sumber=sumber, dalam_form=dalam_form,
    )


def _jalur_chat(target, chat_id: str) -> str:
    from dataclasses import replace
    return replace(target, chat_id=chat_id).jalur


def tombol_buka(
    target, *, form_id: str = "", dalam_form: bool = False,
    label: str = "Bahas dengan Pendamping",
) -> str:
    """Submit native agar field form host ikut terkirim saat bantuan dibuka.

    Tombol eksternal pada form koreksi membawa target di jalur kanonik. Hidden
    form-associated per tombol akan ikut terkirim semuanya dan menjadi ambigu.
    """
    atribut_form = f' form="{_esc(form_id)}"' if form_id else ""
    if form_id:
        identitas = ""
        action = (
            f"/pendamping/inline/buka/sesi/{target.host_id}/soal/{target.nomor}"
            if target.posisi == "soal" else
            f"/pendamping/inline/buka/sesi/{target.host_id}/sesi"
        )
    else:
        identitas = _identitas_target(target)
        action = "/pendamping/inline/buka"
    isi = (
        '<span class="pendamping-buka-inline">' + identitas
        + f'<button class="st-tombol-sekunder" type="submit"{atribut_form} '
          f'formaction="{_esc(action)}">{_esc(label)}</button></span>'
    )
    return isi if (dalam_form or form_id) else f'<form method="post" action="{_esc(action)}">{isi}</form>'


def _panel(target, judul: str, isi: str, *, sumber, dalam_form: bool = False,
           chat_id: str = "") -> str:
    label = " · ".join(str(sumber[k]) for k in ("label", "level") if sumber and sumber.get(k))
    if dalam_form:
        tutup = (
            '<button class="pendamping-tautan" type="submit" '
            'formaction="/pendamping/inline/tutup">Tutup bantuan</button>'
        )
    else:
        tutup = _wadah_form(
            _identitas_target(target)
            + '<button class="pendamping-tautan" type="submit">Tutup bantuan</button>',
            "/pendamping/inline/tutup", dalam_form=False,
        )
    return (
        f'<aside class="pendamping-inline" id="{_esc(target.anchor)}" aria-labelledby="judul-{_esc(target.anchor)}"'
        + (f' data-pendamping-chat="{_esc(chat_id)}"' if chat_id else "") + '>'
        + '<details open><summary>Bantuan Pendamping</summary><div class="pendamping-inline-isi">'
        f'<h3 id="judul-{_esc(target.anchor)}">{_esc(judul)}</h3>'
        + (f'<p class="pendamping-sumber">{_esc(label)}</p>' if label else "")
        + isi + tutup + '</div></details></aside>'
    )
