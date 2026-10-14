"""Renderer HTML murni untuk aplikasi interviewer riset konsumen."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import html
from urllib.parse import urlencode

import research_instrument as instrumen


SUMBER_LABEL = {
    "meta_ads": "Meta Ads",
    "referensi": "Referensi",
    "komunitas": "Komunitas",
    "internal": "Internal",
    "lainnya": "Lainnya",
}
STATUS_LABEL = {
    "draf": "Draf",
    "final": "Final",
    "perlu_redaksi": "Perlu redaksi",
    "ditarik": "Consent ditarik",
}
STATUS_JAWABAN = (
    ("dijawab", "Dijawab"),
    ("tidak_dibahas", "Tidak dibahas"),
    ("tidak_tahu", "Responden tidak tahu"),
    ("menolak", "Responden tidak ingin menjawab"),
)
STATUS_KLARIFIKASI = (
    ("tidak_perlu", "Tidak perlu klarifikasi"),
    ("sudah", "Sudah diklarifikasi"),
    ("ambigu", "Masih ambigu"),
)


def e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _tanggal(timestamp) -> str:
    if timestamp is None:
        return "—"
    zona = timezone(timedelta(hours=7))
    return datetime.fromtimestamp(int(timestamp), zona).strftime("%d %b %Y, %H.%M WIB")


def _hidden(nama, nilai) -> str:
    return '<input type="hidden" name="%s" value="%s">' % (e(nama), e(nilai))


def _badge(status) -> str:
    kelas = " perhatian" if status in ("draf", "perlu_redaksi") else " batal" if status == "ditarik" else ""
    return '<span class="admin-badge%s">%s</span>' % (kelas, e(STATUS_LABEL.get(status, status)))


def dashboard(data, *, csrf: str, token_buat: str, token_ekspor: dict,
              status_filter: str = "") -> str:
    ringkas = data["ringkasan"]
    halaman = data["daftar"]
    kartu = "".join(
        '<div class="admin-stat"><h2>%s</h2><div><strong>%d</strong><span>wawancara</span></div></div>'
        % (label, ringkas[kode])
        for kode, label in (("draf", "Draf"), ("final", "Final"),
                            ("perlu_redaksi", "Perlu redaksi"), ("mendekati_retensi", "Retensi ≤7 hari"))
    )
    opsi_filter = [('','Semua status'),*[(kode,label) for kode,label in STATUS_LABEL.items()]]
    filter_form = (
        '<form class="admin-form-cari" method="get" action="/admin/riset">'
        '<label>Status<select name="status">%s</select></label>'
        '<button class="admin-tombol" type="submit">Terapkan</button></form>'
        % ''.join('<option value="%s"%s>%s</option>' % (
            e(kode), ' selected' if kode == status_filter else '', e(label)
        ) for kode, label in opsi_filter)
    )
    if halaman.item:
        rows = []
        for item in halaman.item:
            rows.append(
                '<li><a class="riset-sesi" href="/admin/riset/wawancara?id=%s">'
                '<span class="riset-sesi-kepala"><strong>%s</strong>%s</span>'
                '<span class="riset-sesi-meta">%s · %d/9 topik · %s</span></a></li>' % (
                    e(item["id"]), e(item["kode_responden"]), _badge(item["status"]),
                    e(SUMBER_LABEL[item["sumber"]]), item["terisi"], e(_tanggal(item["diperbarui"])),
                )
            )
        daftar = '<ul class="riset-daftar-sesi">%s</ul>' % ''.join(rows)
    else:
        daftar = '<p class="admin-kosong">Belum ada wawancara pada filter ini.</p>'
    pager = ""
    if halaman.total > halaman.per_halaman:
        links = []
        if halaman.halaman > 1:
            links.append('<a href="/admin/riset?%s">Sebelumnya</a>' % e(urlencode({"status":status_filter,"halaman":halaman.halaman-1})))
        if halaman.halaman * halaman.per_halaman < halaman.total:
            links.append('<a href="/admin/riset?%s">Berikutnya</a>' % e(urlencode({"status":status_filter,"halaman":halaman.halaman+1})))
        pager = '<nav class="admin-pager" aria-label="Halaman wawancara">%s</nav>' % ''.join(links)
    buat = (
        '<section class="admin-kartu riset-mulai"><h2>Mulai wawancara</h2>'
        '<p>Gunakan kode anonim. Jangan masukkan nama orang tua, nama anak, sekolah, kontak, foto, atau jawaban soal anak.</p>'
        '<form method="post" action="/admin/riset/buat">%s%s'
        '<div class="riset-grid-form"><label>Kode responden<input name="kode_responden" maxlength="32" '
        'pattern="[A-Za-z0-9][A-Za-z0-9_-]{2,31}" placeholder="Contoh: R02" required></label>'
        '<label>Sumber rekrutmen<select name="sumber">%s</select></label>'
        '<label>Waktu wawancara<input type="datetime-local" name="diwawancarai" required></label></div>'
        '<fieldset><legend>Persetujuan</legend>'
        '<label><input type="checkbox" name="consent_wawancara" value="1" required> Responden setuju mengikuti wawancara.</label>'
        '<label><input type="checkbox" name="consent_rekaman" value="1"> Responden secara terpisah setuju direkam. Berkas rekaman tidak disimpan di Jagomat.</label>'
        '</fieldset><button class="admin-tombol" type="submit">Buat draf wawancara</button></form></section>'
        % (_hidden("csrf",csrf), _hidden("tinjauan",token_buat), ''.join(
            '<option value="%s">%s</option>' % (e(k),e(v)) for k,v in SUMBER_LABEL.items()
        ))
    )
    return (
        '<div class="admin-grid-stat">%s</div>%s'
        '<nav class="riset-aksi-atas" aria-label="Aksi data riset">'
        '<a class="admin-tautan" href="/admin/riset/matriks">Buka matriks lintas responden</a>'
        '<form method="post" action="/admin/riset/ekspor">%s%s<input type="hidden" name="format" value="csv"><button class="admin-tautan" type="submit">Ekspor CSV anonim</button></form>'
        '<form method="post" action="/admin/riset/ekspor">%s%s<input type="hidden" name="format" value="json"><button class="admin-tautan" type="submit">Ekspor JSON anonim</button></form></nav>'
        '<section class="admin-kartu"><h2>Wawancara</h2>%s%s%s</section>'
        % (kartu, buat, _hidden("csrf", csrf), _hidden("tinjauan", token_ekspor["csv"]),
           _hidden("csrf", csrf), _hidden("tinjauan", token_ekspor["json"]),
           filter_form, daftar, pager)
    )


def ringkasan_wawancara(detail, *, csrf: str, token_aksi: dict) -> str:
    jawaban = detail["jawaban"]
    daftar = []
    for nomor, item in enumerate(detail["instrumen"]["pertanyaan"], 1):
        isi = jawaban.get(item["kode"])
        status = "Belum diberi status" if isi is None else dict(STATUS_JAWABAN)[isi["status_jawaban"]]
        kode = ""
        if isi:
            labels = instrumen.label_kode(detail["instrumen"])
            semua = ([isi["kode_utama"]] if isi["kode_utama"] else []) + list(isi["kode_tambahan"])
            kode = ''.join('<span class="admin-badge">%s</span>' % e(labels[k]) for k in semua)
        daftar.append(
            '<li><div><span class="riset-nomor">%d</span><div><strong>%s</strong><p>%s</p>%s</div></div>'
            '%s</li>' % (nomor, e(item["judul"]), e(status), kode,
                         '<a href="/admin/riset/isi?id=%s&amp;q=%s">%s</a>' % (
                             e(detail["id"]), e(item["kode"]), "Lihat" if detail["status"] == "final" else "Isi"
                         ))
        )
    meta = (
        '<dl class="admin-rincian"><dt>Kode responden</dt><dd>%s</dd><dt>Status</dt><dd>%s</dd>'
        '<dt>Instrumen</dt><dd>%s</dd><dt>Sumber</dt><dd>%s</dd><dt>Wawancara</dt><dd>%s</dd>'
        '<dt>Retensi hingga</dt><dd>%s</dd></dl>' % (
            e(detail["kode_responden"]), _badge(detail["status"]), e(detail["kode_versi"]),
            e(SUMBER_LABEL[detail["sumber"]]), e(_tanggal(detail["diwawancarai"])),
            e(_tanggal(detail["retensi_hingga"])),
        )
    )
    aksi = ""
    if detail["status"] in ("draf", "perlu_redaksi"):
        lengkap = len(jawaban) == len(detail["instrumen"]["pertanyaan"])
        aksi = ('<form method="post" action="/admin/riset/finalisasi">%s%s%s'
                '<button class="admin-tombol" type="submit"%s>Selesaikan wawancara</button>'
                '%s</form>' % (
                    _hidden("csrf",csrf), _hidden("tinjauan",token_aksi["finalisasi"]),
                    _hidden("id",detail["id"]), '' if lengkap else ' disabled',
                    '' if lengkap else '<p class="admin-meta">Semua pertanyaan perlu diberi status; jawaban naratif tidak wajib.</p>',
                ))
    elif detail["status"] == "final":
        aksi = ('<form method="post" action="/admin/riset/koreksi">%s%s%s'
                '<button class="admin-tombol" type="submit">Buka untuk koreksi</button></form>' % (
                    _hidden("csrf",csrf),_hidden("tinjauan",token_aksi["koreksi"]),_hidden("id",detail["id"])
                ))
    if detail["status"] not in ("ditarik", "perlu_redaksi"):
        aksi += ('<form method="post" action="/admin/riset/redaksi">%s%s%s'
                 '<button class="admin-tombol" type="submit">Tandai perlu redaksi</button></form>' % (
                    _hidden("csrf",csrf),_hidden("tinjauan",token_aksi["redaksi"]),_hidden("id",detail["id"])
                 ))
    if detail["status"] != "ditarik":
        aksi += ('<form method="post" action="/admin/riset/tarik" data-konfirmasi="Tarik consent dan hapus seluruh jawaban serta kutipan responden ini?">%s%s%s'
                 '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
                 '<button class="admin-tombol admin-bahaya" type="submit">Tarik consent dan hapus jawaban</button></form>' % (
                    _hidden("csrf",csrf),_hidden("tinjauan",token_aksi["tarik"]),_hidden("id",detail["id"])
                 ))
    return ('<p><a href="/admin/riset">← Kembali ke daftar</a></p>'
            '<section class="admin-kartu">%s</section>'
            '<section class="admin-kartu"><h2>Topik wawancara</h2><ol class="riset-daftar-pertanyaan">%s</ol></section>'
            '<section class="admin-kartu"><h2>Tindakan</h2><div class="riset-aksi-form">%s</div></section>'
            % (meta, ''.join(daftar), aksi))


def formulir_pertanyaan(detail, kode_q, *, csrf, token, readonly=False) -> str:
    item = instrumen.pertanyaan(detail["instrumen"], kode_q)
    jawaban = detail["jawaban"].get(kode_q, {})
    labels = instrumen.label_kode(detail["instrumen"])
    status = jawaban.get("status_jawaban", "dijawab")
    utama = jawaban.get("kode_utama")
    tambahan = set(jawaban.get("kode_tambahan", ()))
    isi_opsi = []
    for kelompok, pilihan in instrumen.kelompok_pilihan(item):
        isi_opsi.append('<fieldset><legend>%s</legend>' % e(kelompok))
        for opsi in pilihan:
            kode = opsi["kode"]
            isi_opsi.append(
                '<div class="riset-kode-baris"><label><input type="radio" name="kode_utama" value="%s"%s%s> Utama</label>'
                '<label><input type="checkbox" name="kode_tambahan" value="%s"%s%s> Tambahan</label><span>%s</span></div>' % (
                    e(kode), ' checked' if kode == utama else '', ' disabled' if readonly else '',
                    e(kode), ' checked' if kode in tambahan else '', ' disabled' if readonly else '', e(opsi["label"]),
                )
            )
        isi_opsi.append('</fieldset>')
    nomor = [x["kode"] for x in detail["instrumen"]["pertanyaan"]].index(kode_q) + 1
    body = (
        '<p><a href="/admin/riset/wawancara?id=%s">← Ringkasan wawancara</a></p>'
        '<section class="admin-kartu riset-pertanyaan"><p class="admin-alis">Pertanyaan %d dari %d</p>'
        '<h2>%s</h2><p class="riset-prompt">%s</p><p class="admin-meta">%s</p>'
        '<div class="admin-kartu admin-catatan"><strong>Catatan privasi</strong><p>Jangan tulis nama, sekolah, kontak, foto, atau jawaban soal anak.</p></div>'
        '<form method="post" action="/admin/riset/jawaban">%s%s%s%s%s%s'
        '<label>Status jawaban<select name="status_jawaban"%s>%s</select></label>'
        '<label>Jawaban responden<textarea name="jawaban_responden" rows="5" maxlength="6000"%s>%s</textarea></label>'
        '<p class="admin-meta">Ringkas setia pada ucapan responden. Tidak perlu membuat jawabannya lebih ideal.</p>'
        '<label>Kutipan persis, opsional<textarea name="kutipan_responden" rows="3" maxlength="2000"%s>%s</textarea></label>'
        '<label><input type="checkbox" name="kutipan_terpilih" value="1"%s%s> Kutipan ini aman dan dipilih untuk ekspor</label>'
        '<label>Catatan interviewer<textarea name="catatan_interviewer" rows="4" maxlength="4000"%s>%s</textarea></label>'
        '<p class="admin-meta">Konteks atau interpretasi interviewer—bukan ucapan responden dan bukan kesimpulan pasar.</p>'
        '<details class="riset-kode"%s><summary>Kode jawaban</summary><p class="admin-meta">Pilih setelah mendengar jawaban. Bacakan kategori hanya jika responden buntu.</p>%s</details>'
        '<label>Status klarifikasi<select name="status_klarifikasi"%s>%s</select></label>%s</form></section>' % (
            e(detail["id"]), nomor, len(detail["instrumen"]["pertanyaan"]), e(item["judul"]), e(item["pertanyaan"]), e(item["bantuan"]),
            _hidden("csrf",csrf),_hidden("tinjauan",token),_hidden("id",detail["id"]),_hidden("q",kode_q),
            _hidden("revisi_wawancara",detail["revisi"]),_hidden("revisi_jawaban",jawaban.get("revisi",0)),
            ' disabled' if readonly else '', ''.join('<option value="%s"%s>%s</option>'%(e(k),' selected' if k==status else '',e(v)) for k,v in STATUS_JAWABAN),
            ' readonly' if readonly else '', e(jawaban.get("jawaban_responden","")),
            ' readonly' if readonly else '', e(jawaban.get("kutipan_responden","")),
            ' checked' if jawaban.get("kutipan_terpilih") else '', ' disabled' if readonly else '',
            ' readonly' if readonly else '', e(jawaban.get("catatan_interviewer","")),
            ' open' if utama or tambahan else '', ''.join(isi_opsi),
            ' disabled' if readonly else '', ''.join('<option value="%s"%s>%s</option>'%(e(k),' selected' if k==jawaban.get("status_klarifikasi","tidak_perlu") else '',e(v)) for k,v in STATUS_KLARIFIKASI),
            '<div class="riset-tombol"><button class="admin-tombol" name="lanjut" value="ringkasan" type="submit">Simpan draf</button><button class="admin-tombol" name="lanjut" value="berikut" type="submit">Simpan &amp; lanjut</button></div>' if not readonly else '',
        )
    )
    return body


def matriks(data) -> str:
    if not data["wawancara"]:
        return ('<p><a href="/admin/riset">← Kembali ke riset konsumen</a></p>'
                '<section class="admin-kartu"><p class="admin-kosong">Belum ada wawancara final untuk dibandingkan.</p></section>')
    kepala = ''.join('<th>%s</th>' % e(label) for _kode,label in data["kolom"])
    rows = []
    for item in data["wawancara"]:
        cells = []
        for kode_q, _label in data["kolom"]:
            jaw = item["jawaban"].get(kode_q)
            if not jaw:
                cells.append('<td><span class="admin-meta">Tidak dibahas</span></td>')
                continue
            kode = '<br>'.join(e(x) for x in jaw.get("kode_label", ())) or e(dict(STATUS_JAWABAN)[jaw["status_jawaban"]])
            kutipan = ('<q>%s</q>' % e(jaw["kutipan_responden"])) if jaw["kutipan_terpilih"] and jaw["kutipan_responden"] else ''
            cells.append('<td><strong>%s</strong>%s</td>' % (kode, kutipan))
        rows.append('<tr><th scope="row"><a href="/admin/riset/wawancara?id=%s">%s</a></th>%s</tr>' % (e(item["id"]),e(item["kode_responden"]),''.join(cells)))
    counts = []
    for kode_q, label in data["kolom"]:
        denominator = data["denominator"].get(kode_q,0)
        pairs = sorted((kode,n) for (q,kode),n in data["hitungan"].items() if q==kode_q)
        counts.append('<section class="admin-kartu"><h3>%s</h3><p>Denominator: %d responden yang menjawab.</p><ul>%s</ul></section>' % (
            e(label), denominator, ''.join('<li>%s: <strong>%d</strong></li>'%(e(k),n) for k,n in pairs) or '<li>Belum ada kode.</li>'
        ))
    return ('<p><a href="/admin/riset">← Kembali ke riset konsumen</a></p>'
            '<section class="admin-kartu admin-catatan"><strong>Batas pembacaan</strong><p>Studi eksploratif; tidak mewakili seluruh orang tua Indonesia dan bukan bukti PMF. Hitungan memakai denominator yang menjawab tiap topik.</p></section>'
            '<div class="admin-tabel-wrap"><table class="admin-tabel riset-matriks"><thead><tr><th>Responden</th>%s</tr></thead><tbody>%s</tbody></table></div>'
            '<div class="riset-grid-ringkas">%s</div>' % (kepala,''.join(rows),''.join(counts)))
