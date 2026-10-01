"""Workspace anak dan form latihan orang tua/guru."""
from __future__ import annotations

import html
from datetime import datetime

import database
import design_tokens as T
import learning_cycle_ui
import profile_history
import profile_workspace
import share_links
from generator import LEVEL_BAWAAN
from question_context import label_profil_parameter as label_kelas
from template_labels import nama_tipe_soal as _nama_template
from templates import LEVEL
from topics import TOPIK_BAWAAN, ambil, daftar_topik
from teacher_shell import _halaman_stitch


LABEL_KODE_REMEDIAL = {
    "K": "Salah konsep",
    "B": "Salah memahami soal",
    "H": "Salah hitung",
    "E": "Salah menyalin jawaban",
    "N": "Menebak atau belum menunjukkan cara",
}

INFO_LATIHAN_BEBAS = (
    "Latihan bebas tidak mengubah progres rencana terpandu."
)


def _form_remedial(
    sasaran,
    siswa_id: int,
    *,
    judul: str,
    penjelasan: str,
    sumber_sesi_id: int | None = None,
    draf_remedial=None,
    bantuan: str = "",
) -> str:
    """Form pilihan remedial bersama untuk profil anak dan hasil satu sesi."""
    if not sasaran:
        return ""
    pilihan = []
    sudah_dipilih = False
    dipilih_draf = set(draf_remedial.template_id) if draf_remedial else None
    for kandidat in sasaran:
        template_id = str(kandidat["template_id"])
        kode = str(kandidat["kode"] or "")
        direkomendasikan = bool(kandidat["direkomendasikan"])
        checked = (template_id in dipilih_draf if dipilih_draf is not None
                   else direkomendasikan and not sudah_dipilih)
        sudah_dipilih = sudah_dipilih or checked
        label_kode = LABEL_KODE_REMEDIAL.get(kode, "Perlu diperhatikan")
        meta = f'{html.escape(label_kode)} · {int(kandidat["kali_salah"])} kali'
        pilihan.append(
            '<label class="pilihan-remedial-st">'
            f'<input type="checkbox" name="template_id" value="{html.escape(template_id)}"'
            f'{" checked" if checked else ""}>'
            '<span class="isi-pilihan-remedial-st">'
            f'<b>{html.escape(_nama_template(template_id))}</b>'
            f'<span class="meta-remedial-st">{meta}</span>'
            '</span></label>'
        )
    if draf_remedial is not None and draf_remedial.sumber_sesi_id:
        sumber_sesi_id = int(draf_remedial.sumber_sesi_id)
    sumber = (
        f'<input type="hidden" name="sumber_sesi_id" value="{sumber_sesi_id}">'
        if sumber_sesi_id is not None else ""
    )
    return (
        f'<section class="remedial-st"><h2>{html.escape(judul)}</h2>'
        f'<p class="sub">{html.escape(penjelasan)}</p>'
        f'<form id="form-latihan-remedial-{siswa_id}" method="post" action="/sesi-remedial/{siswa_id}" class="strip-sesi">'
        '<input type="hidden" name="inline_form" value="remedial">'
        f'{sumber}<div class="daftar-remedial-st">{"".join(pilihan)}</div>'
        '<p class="batas-remedial-st">Pilih maksimal 3 tipe soal.</p>'
        '<div class="strip-kolom"><label>Jumlah Soal</label>'
        '<select name="jumlah_soal" class="st-input">'
        + ''.join(
            f'<option value="{nilai}"{" selected" if (draf_remedial.jumlah_soal if draf_remedial else "10") == nilai else ""}>{nilai} soal (± {int(nilai) * 3} mnt)</option>'
            for nilai in ("10", "15", "20")
        )
        + '</select></div>'
        '<button type="submit" class="st-tombol-coral">'
        '<span class="material-symbols-outlined" aria-hidden="true">restart_alt</span>'
        'Buat latihan ulang terarah</button>'
        f'<div class="profil-assistant-st">{bantuan}</div></form></section>'
    )

def _ambil(baris, kolom: str, bawaan):
    """Baca kolom yang mungkin belum ada di baris.

    sqlite3.Row melempar IndexError untuk kolom tak dikenal, dan sebagian
    test memberi dict biasa. Dipakai untuk kolom hasil migrasi supaya
    pemanggil lama tidak pecah.
    """
    try:
        nilai = baris[kolom]
    except (IndexError, KeyError):
        return bawaan
    return bawaan if nilai is None else nilai

def _tanggal_ringkas(nilai) -> str:
    """Tanggal Indonesia ringkas; nilai warisan tetap ditampilkan aman."""
    mentah = str(nilai or "")
    bulan = (
        "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
    )
    try:
        tanggal = datetime.strptime(mentah, "%Y-%m-%d")
    except ValueError:
        return f'<span>{html.escape(mentah or "—")}</span>'
    label = f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"
    nilai_datetime = tanggal.strftime("%Y-%m-%d")
    return f'<time datetime="{nilai_datetime}">{label}</time>'

def _nama_topik_sesi(topik_id: str) -> tuple[str, str]:
    """Judul dan rincian topik dalam bahasa orang tua, bukan ID basis data."""
    if topik_id.startswith("gabungan:"):
        ids = [nilai for nilai in topik_id.split(":", 1)[1].split(",") if nilai]
        nama = []
        for nilai in ids:
            try:
                nama.append(ambil(nilai).nama)
            except KeyError:
                nama.append(nilai.replace("-", " ").title())
        return f"Gabungan {len(nama)} topik", " &middot; ".join(
            html.escape(nilai) for nilai in nama
        )
    try:
        nama_topik = ambil(topik_id).nama
    except KeyError:
        nama_topik = topik_id.replace("-", " ").title()
    if topik_id == "campuran":
        awalan_dekoratif = "✨ "
        if nama_topik.startswith(awalan_dekoratif):
            nama_topik = nama_topik[len(awalan_dekoratif):]
        nama_topik = nama_topik.split(" (", 1)[0]
    return nama_topik, ""

def _mode_sesi(baris) -> str:
    if _ambil(baris, 'format_jawaban', 'isian') == 'pilihan_ganda':
        return 'Pilihan ganda · latihan manual'
    if _ambil(baris, "mode", "diagnostik") == "drill":
        return "Latihan Cepat"
    return "Mode Diagnosa"

def _ringkasan_angka_sesi(baris) -> str:
    """Hanya tampilkan angka yang sudah bermakna pada tahap sesi saat ini."""
    terisi = int(_ambil(baris, "terisi", 0) or 0)
    jumlah = int(_ambil(baris, "n", 0) or 0)
    if terisi == 0:
        return ""
    bagian = [f"{terisi} dari {jumlah} terisi"]
    if _ambil(baris, "selesai", None):
        benar = int(_ambil(baris, "benar", 0) or 0)
        bagian[0] = f"{benar} dari {jumlah} benar"
        durasi = _fmt_durasi(
            _ambil(baris, "mulai", None),
            _ambil(baris, "selesai", None),
            _ambil(baris, "dicatat_awal", None),
            _ambil(baris, "dicatat_akhir", None),
        )
        if durasi != "&mdash;":
            bagian.append(f"Waktu {durasi}")
    return " &middot; ".join(bagian)

def _topik_untuk_level(level: str) -> list[str]:
    """ID topik yang tersedia pada level resmi atau fallback data lama."""
    level_efektif = level if level in LEVEL else LEVEL_BAWAAN
    daftar = [
        topik_id
        for topik_id in daftar_topik()
        if level_efektif in ambil(topik_id).komposisi and topik_id != "campuran"
    ]
    if "campuran" in daftar_topik():
        daftar = ["campuran"] + daftar
    return daftar

def _badge_review_status(baris) -> str:
    """Bedakan dibuka, draf, dan konfirmasi aktif tanpa menyatakan penguasaan."""
    if _ambil(baris, "dibatalkan", None) is not None:
        return '<span class="badge-direview batal st-badge selesai">Dibatalkan</span>'
    if _ambil(baris, "selesai", None) is None:
        if _ambil(baris, "terisi", 0) > 0:
            kelas, label = "proses", "Sedang Dikerjakan"
        else:
            kelas, label = "belum", "Belum Dikerjakan"
    else:
        fingerprint_terakhir = _ambil(baris, "fingerprint_terakhir", None)
        konfirmasi_aktif = (
            _ambil(baris, "dikonfirmasi_guru", None) is not None
            and fingerprint_terakhir is not None
            and _ambil(baris, "fingerprint_konfirmasi", None) == fingerprint_terakhir
        )
        kelas = "perlu"
        if konfirmasi_aktif:
            kelas, label = "sudah", "✓ Hasil dikonfirmasi"
        elif fingerprint_terakhir is not None:
            label = "Perlu konfirmasi ulang"
        elif _ambil(baris, "ada_tinjauan", False):
            label = "Draf tinjauan tersimpan · belum dikonfirmasi"
        elif _ambil(baris, "direview", None) is not None:
            label = "Sudah dibuka · belum dikonfirmasi"
        else:
            label = "Belum ditinjau"
    return f'<span class="badge-direview {kelas}">{label}</span>'

def _fmt_durasi(mulai, selesai, dicatat_awal=None, dicatat_akhir=None) -> str:
    """Durasi pengerjaan mm:ss dari kolom mulai/selesai sesi.

    Utama: selesai − mulai, dan hanya bila keduanya tercatat. Kalau salah
    satu tidak ada (sesi kertas yang dilengkapi lewat foto) atau durasinya
    nol — versi lama mencatat mulai saat simpan pertama, jadi sesi sekali
    simpan tercatat 0 detik — jatuh ke rentang waktu tercatatnya jawaban
    (dicatat_awal → dicatat_akhir): perkiraan yang tetap jujur karena tiap
    simpan mencatat waktunya. Tanpa jejak waktu sama sekali, tampil '—';
    mengarang durasi lebih buruk daripada menampilkan kosong.
    """
    BENTUK = "%Y-%m-%d %H:%M:%S"
    for awal, akhir in ((mulai, selesai), (dicatat_awal, dicatat_akhir)):
        if not awal or not akhir:
            continue
        try:
            detik = int(
                (
                    datetime.strptime(str(akhir), BENTUK)
                    - datetime.strptime(str(awal), BENTUK)
                ).total_seconds()
            )
        except ValueError:
            continue
        if detik > 0:
            return f"{detik // 60}:{detik % 60:02d}"
    return "&mdash;"

def _kelas_sekolah_profil(kon, siswa):
    """Caller sudah mengotorisasi; profil tanpa pemilik tidak ditebak kelasnya."""
    import learning_profile
    if not siswa['pemilik']:
        return None
    return learning_profile.baca(kon, int(siswa['id']), pemilik=siswa['pemilik']).kelas_sekolah

def _kontrol_mode_sesi(draf=None) -> str:
    """Pilihan cara menjawab dan batas waktu sebagai dua keputusan terpisah."""
    mode = draf.mode if draf else "diagnostik"
    timer = draf.timer_mode if draf else False
    durasi = draf.durasi_menit if draf else "30"
    timer_auto = draf.timer_auto if draf else "0"
    return (
        '<div class="strip-kolom"><label>Mode sesi</label>'
        '<div class="mode-pilih">'
        '<label class="mode-opsi"><input type="radio" name="mode" '
        f'value="diagnostik"{" checked" if mode == "diagnostik" else ""}>'
        '<span class="mode-teks">Mode Diagnosa'
        '<span class="mode-desk">Jawaban dan cara berpikir anak ikut diperiksa.</span>'
        '</span></label>'
        f'<label class="mode-opsi"><input type="radio" name="mode" value="drill"{" checked" if mode == "drill" else ""}>'
        '<span class="mode-teks">Latihan Cepat'
        '<span class="mode-desk">Anak langsung mengisi jawaban. Cocok untuk pengulangan.</span>'
        '</span></label>'
        '</div></div>'
        '<fieldset class="pengaturan-timer">'
        '<legend>Batas waktu</legend>'
        '<label class="mode-opsi timer-toggle">'
        '<input type="hidden" name="hadir_timer_mode" value="1">'
        f'<input type="checkbox" name="timer_mode" value="sesi"{" checked" if timer else ""}>'
        '<span class="mode-teks">Gunakan batas waktu'
        '<span class="mode-desk">Hitung mundur ditampilkan selama seluruh sesi.</span>'
        '</span></label>'
        '<div class="rincian-timer">'
        '<label class="durasi-timer">Durasi sesi '
        '<span><input type="text" inputmode="numeric" '
        f'name="durasi_menit" value="{html.escape(durasi, quote=True)}"> menit</span>'
        '<small>Saran: sekitar 3 menit per soal.</small></label>'
        '<fieldset class="akibat-timer"><legend>Ketika waktu habis</legend>'
        '<label class="mode-opsi"><input type="radio" name="timer_auto" '
        f'value="0"{" checked" if timer_auto == "0" else ""}> Ingatkan anak, tetapi tetap boleh menyelesaikan</label>'
        '<label class="mode-opsi"><input type="radio" name="timer_auto" '
        f'value="1"{" checked" if timer_auto == "1" else ""}> Kirim jawaban secara otomatis</label>'
        '</fieldset></div></fieldset>'
    )

def _kontrol_profil_parameter(identitas, terpilih=None, topik_ids=None):
    """Pilih isi kontekstual; dropdown warisan hanya untuk caller lama terbatas."""
    from question_variants_ui import kontrol_variasi, pemilih_isi
    if topik_ids is not None:
        return pemilih_isi(topik_ids, identitas, terpilih)
    return kontrol_variasi(identitas, terpilih)

def halaman_anak(
    kon,
    siswa,
    peran: str = "guru",
    pengguna: str = "",
    sorot: int | None = None,
    pesan: str = "",
    bantuan_rencana: str = "",
    bantuan_latihan: str = "",
    draf_latihan=None,
    draf_gabungan=None,
    draf_remedial=None,
    privat: bool = False,
    query: str = "",
) -> bytes:
    """Ruang kerja anak: latihan, rencana, atau riwayat terbatasi.

    Caller mengotorisasi siswa terlebih dahulu. Bantuan memilih tab konteksnya
    tanpa memperluas query/resource Pendamping; draf tetap request-local.
    """
    privat = privat or bool(bantuan_rencana or bantuan_latihan) or (peran == 'guru' and bool(pengguna))
    filter_profil = profile_history.parse_filter(query)
    section = ("rencana" if bantuan_rencana else "latihan" if bantuan_latihan or draf_latihan or draf_gabungan or draf_remedial else filter_profil.section)
    total_sesi = profile_history.jumlah_sesi(kon, siswa["id"])
    if section == "riwayat":
        sesi, total_hasil, filter_profil = profile_history.halaman_riwayat(kon, siswa["id"], filter_profil)
    else:
        sesi = profile_history.tugas_terbaru(kon, siswa["id"], sorot) if section == "latihan" else []
    opsi_topik = "".join(
        f'<option value="{html.escape(t)}"'
        f'{" selected" if (draf_latihan.topik if draf_latihan else TOPIK_BAWAAN) == t else ""}>'
        f'{html.escape("Campuran semua topik" if t == "campuran" else ambil(t).nama)}</option>'
        for t in daftar_topik()
    )
    def _kelas_sorot(rid):
        return "sorot-baru" if sorot is not None and rid == sorot else ""

    def _aksi_tautan(baris):
        rid = baris["id"]
        if baris["selesai"] or baris["dibatalkan"] is not None:
            return ""
        aktif = share_links.aktif(kon, rid)
        cabut = ""
        if aktif:
            cabut = (
                f'<form method="post" action="/sesi/{rid}/cabut-tautan" style="margin:0">'
                '<button type="submit" class="tombol-ikon-st" '
                'aria-label="Cabut tautan sesi" title="Cabut tautan">'
                f'{profile_workspace.ikon("link_off")}<span>Cabut tautan</span></button></form>'
            )
        if aktif:
            return (
                '<details class="tautan-sesi-opsi"><summary>Kelola tautan anak</summary>'
                '<p class="sub">Membuat tautan baru akan menonaktifkan tautan sebelumnya. '
                'Mencabut tautan menutup akses melalui tautan itu.</p>'
                '<div class="blok-bagikan-st"><div class="aksi-bagikan-st">'
                f'<form method="post" action="/sesi/{rid}/bagikan" '
                'data-bagikan-sesi data-bagikan-aktif="1">'
                '<button type="submit"><span data-label-bagikan>Buat dan salin tautan baru</span>'
                '</button></form>' + cabut + '</div>'
                '<span class="kabar-bagikan-st" role="status" aria-live="polite"></span>'
                '</div></details>'
            )
        return (
            '<div class="blok-bagikan-st"><div class="aksi-bagikan-st">'
            f'<form method="post" action="/sesi/{rid}/bagikan" '
            'data-bagikan-sesi data-bagikan-aktif="0">'
            '<button type="submit"><span data-label-bagikan>Salin tautan sesi</span></button>'
            '</form></div><span class="kabar-bagikan-st" role="status" '
            'aria-live="polite"></span></div>'
        )

    def _kartu_sesi(r, kelas):
        topik_id = str(_ambil(r, "topik", TOPIK_BAWAAN))
        judul_topik, rincian_topik = _nama_topik_sesi(topik_id)
        rincian = (
            '<details class="rincian-topik-st"><summary>Lihat '
            f'{len(rincian_topik.split(" &middot; "))} topik</summary>'
            '<ul>' + ''.join(f'<li>{nama}</li>' for nama in rincian_topik.split(' &middot; '))
            + '</ul></details>'
            if rincian_topik
            else ""
        )
        angka = _ringkasan_angka_sesi(r)
        ringkasan = (
            f'<div class="ringkasan-sesi-st">{angka}</div>' if angka else ""
        )
        identitas_remedial = ""
        if _ambil(r, "jenis", "biasa") == "remedial":
            fokus_ids = [
                b["template_id"] for b in database.isi_sesi(kon, int(r["id"]))
            ]
            fokus_unik = list(dict.fromkeys(fokus_ids))
            fokus = " & ".join(_nama_template(t) for t in fokus_unik)
            asal = (
                f' · dari sesi #{int(r["sumber_sesi_id"])}'
                if _ambil(r, "sumber_sesi_id", None) else ""
            )
            identitas_remedial = (
                '<div class="rincian-topik-st"><span class="st-badge latihan">'
                'Remedial</span> '
                f'Fokus {html.escape(fokus)}{asal}</div>'
            )
        return (
            f'<article class="st-kartu-baris kartu-sesi-guru {kelas}">'
            '<div class="isi-kartu-sesi-st">'
            '<div class="kepala-kartu-sesi-st">'
            f'<a class="judul-sesi-st" href="/sesi/{r["id"]}">'
            f'{html.escape(judul_topik)}</a>{_badge_review_status(r)}</div>'
            '<div class="meta-sesi-st">'
            f'{_tanggal_ringkas(r["tanggal"])}<span aria-hidden="true">&middot;</span>'
            f'<span>{html.escape(label_kelas(str(_ambil(r, "level", LEVEL_BAWAAN))))}</span>'
            '<span aria-hidden="true">&middot;</span>'
            f'<span>{html.escape(_mode_sesi(r))}</span>'
            '<span aria-hidden="true">&middot;</span>'
            f'<span class="nomor-sesi-st">Sesi #{r["id"]}</span>'
            "</div>"
            f"{rincian}{identitas_remedial}{ringkasan}"
            "</div>"
            '<div class="aksi-sesi-st">'
            f'{_aksi_tautan(r)}'
            "</div>"
            "</article>"
        )

    if section == "latihan" and sesi:
        item = "".join(_kartu_sesi(r, _kelas_sorot(r["id"])) for r in sesi)
    else:
        item = '<p class="sub">Tidak ada latihan yang perlu ditindaklanjuti.</p>'

    from choice_pages import kontrol_format
    draf_aktif = (
        "gabungan" if draf_gabungan is not None else
        "remedial" if draf_remedial is not None else "manual"
    )

    def _slot_pendamping(jenis: str) -> str:
        if peran != "guru" or not pengguna:
            return ""
        target = __import__("assistant_inline").tujuan_anak(int(siswa["id"]), "latihan")
        status_akses = __import__("assistant_entitlement_runtime").status_pengguna(pengguna)
        return __import__("assistant_components").tombol_buka(
            target, dalam_form=True, status_akses=status_akses,
        )

    topik_manual = draf_latihan.topik if draf_latihan else TOPIK_BAWAAN
    strip_sesi = (
        f'<form id="form-latihan-manual-{siswa["id"]}" method="post" action="/sesi-baru/{siswa["id"]}" class="strip-sesi profil-manuel-st">'
        '<div class="profil-champs-st">'
        + f'<div class="strip-kolom"><label for="manual-topik">Topik</label>'
        f'<select id="manual-topik" name="topik" class="st-input">{opsi_topik}</select>'
        '<small class="profil-petunjuk-st">Jagomat memilih cakupan yang sesuai untuk topik ini. '
        'Angka dan model soal berganti otomatis tanpa pilihan A–D.</small></div>'
        + '<div class="strip-kolom"><label for="manual-jumlah">Jumlah soal</label>'
        '<select id="manual-jumlah" name="jumlah_soal" class="st-input" aria-describedby="manual-jumlah-petunjuk">'
        + "".join(
            f'<option value="{nilai}"'
            f'{" selected" if (draf_latihan.jumlah_soal if draf_latihan else "") == nilai else ""}>'
            f'{label}</option>'
            for nilai, label in (("", "Sesuai topik"), ("10", "10 soal (± 30 mnt)"),
                                 ("15", "15 soal (± 45 mnt)"), ("20", "20 soal (± 60 mnt)"),
                                 ("25", "25 soal (± 75 mnt)"), ("30", "30 soal (± 90 mnt)"))
        )
        + '</select><small class="profil-petunjuk-st" id="manual-jumlah-petunjuk">'
        'Estimasi ±3 menit per soal. “Sesuai topik” memakai jumlah bawaan topik.</small></div>'
        + f'{kontrol_format("manual", getattr(draf_latihan, "format_jawaban", "isian"))}{_kontrol_mode_sesi(draf_latihan)}'
        + '<button type="submit" class="st-tombol-coral">'
        f'{profile_workspace.ikon("play_arrow")}'
        "Buat sesi baru</button></div>"
        '<input type="hidden" name="inline_form" value="manual">'
        '<div class="profil-assistant-st">'
        + _slot_pendamping("manual") + "</div></form>"
    )

    # Remedial terarah dari seluruh riwayat yang sudah ditinjau. Guru melihat
    # bukti dan memilih fokus; sistem tidak lagi mencampur enam tipe diam-diam.
    sasaran = database.sasaran_remedial_anak(kon, siswa["id"]) if section == "latihan" else []
    strip_remedial = _form_remedial(
        sasaran,
        int(siswa["id"]),
        judul="Perkuat kelemahan",
        penjelasan=(
            "Pilih yang ingin dilatih. Pilihan yang dicentang adalah rekomendasi "
            "berdasarkan hasil terbaru."
        ),
        draf_remedial=draf_remedial,
        bantuan=_slot_pendamping("remedial"),
    )

    # Latihan gabungan (poin 4 tahap 2): guru memilih BEBERAPA topik saja,
    # mis. "geometri datar + pengukuran" untuk anak yang lemah di dua itu.
    # Berbeda dari topik "campuran" yang selalu memakai SEMUA topik.
    centang_topik = "".join(
        f'<label class="mode-opsi"><input type="checkbox" name="topik" '
        f'value="{html.escape(t)}"{" checked" if draf_gabungan and t in draf_gabungan.topik else ""}> {html.escape(ambil(t).nama)}</label>'
        for t in daftar_topik()
        if t != "campuran"      # campuran sudah = semua, tak perlu dicentang
    )
    topik_gabungan = tuple(draf_gabungan.topik) if draf_gabungan else ()
    strip_gabungan = (
        f'<form id="form-latihan-gabungan-{siswa["id"]}" method="post" '
        f'action="/sesi-gabungan/{siswa["id"]}" class="strip-sesi">'
        '<input type="hidden" name="inline_form" value="gabungan">'
        + '<div class="strip-kolom">'
        "<label>Latihan gabungan — pilih beberapa topik</label>"
        '<p class="sub">Centang dua topik atau lebih. Soalnya dicampur '
        "bergantian antar-topik yang kamu pilih.</p>"
        f'<div class="mode-pilih">{centang_topik}</div>'
        '<small class="profil-petunjuk-st">Jagomat memilih satu cakupan yang tersedia pada semua topik pilihan.</small></div>'
        + f'{kontrol_format("gabungan", getattr(draf_gabungan, "format_jawaban", "isian"))}'
        + '<div class="strip-kolom">'
        '<span id="gabungan-mode-label">Mode latihan</span>'
        '<div class="mode-pilih" role="radiogroup" aria-labelledby="gabungan-mode-label">'
        '<label class="mode-opsi"><input type="radio" name="mode" value="drill"' + (' checked' if not draf_gabungan or draf_gabungan.mode == 'drill' else '') + '>'
        '<span class="mode-teks">Latihan Cepat'
        '<span class="mode-desk">Anak langsung mengisi jawaban, tanpa menuliskan cara.</span>'
        '</span></label>'
        '<label class="mode-opsi"><input type="radio" name="mode" value="diagnostik"' + (' checked' if draf_gabungan and draf_gabungan.mode == 'diagnostik' else '') + '>'
        '<span class="mode-teks">Diagnostik'
        '<span class="mode-desk">Jawaban dan cara berpikir anak ikut diperiksa.</span>'
        '</span></label>'
        '</div></div>'
        '<div class="strip-kolom"><label for="gabungan-jumlah">Jumlah Soal</label>'
        '<select id="gabungan-jumlah" name="jumlah_soal" class="st-input">'
        + ''.join(
            f'<option value="{nilai}"{" selected" if (draf_gabungan.jumlah_soal if draf_gabungan else "10") == nilai else ""}>{nilai} soal (± {int(nilai) * 3} mnt)</option>'
            for nilai in ("10", "15", "20")
        )
        + "</select></div>"
        '<button type="submit" class="st-tombol-coral">'
        f'{profile_workspace.ikon("library_add")}Buat latihan gabungan</button>'
        '<div class="profil-assistant-st">' + _slot_pendamping("gabungan") + '</div>'
        "</form>"
    )

    # Fase C: tiga form di atas dibungkus SATU kartu "Buat latihan" dengan tab
    # radio. Tanpa JS (CLAUDE.md: zero-JS by default) — pemilihan tab memakai
    # :has(), teknik yang sudah dipakai .mode-opsi:has(input:checked).
    #
    # Panel disusun dinamis: strip_remedial kosong kalau anak belum punya
    # kesalahan tercatat. Menyusunnya dari daftar mencegah tab hantu yang
    # menunjuk panel kosong.
    panel = [("baru", "add_circle", "Sesi baru", strip_sesi)]
    if strip_remedial:
        panel.append(("ulang", "restart_alt", "Perkuat kelemahan", strip_remedial))
    if strip_gabungan:
        panel.append(("gabungan", "library_add", "Gabungan topik", strip_gabungan))

    panduan = (
        '<div class="profil-aide-st info-baris"><p class="sub">'
        'Pilih topik dan bentuk latihan. Jagomat mengatur cakupan soalnya secara otomatis.</p>'
        + f'<button type="button" class="info" aria-label="{html.escape(INFO_LATIHAN_BEBAS, quote=True)}">'
        f'i<span class="info-bubble" role="tooltip">{html.escape(INFO_LATIHAN_BEBAS)}</span></button></div>'
    ) if section == 'latihan' else ''
    if len(panel) > 1:
        panel_aktif = "gabungan" if draf_gabungan else "ulang" if draf_remedial else "baru"
        tab = "".join(
            f'<input type="radio" name="jenis-latihan" id="tab-{kode}" '
            f'class="tab-radio-st"{" checked" if kode == panel_aktif else ""}>'
            for kode, _, _, _ in panel
        )
        label = "".join(
            f'<label class="tab-label-st" for="tab-{kode}">'
            f'{profile_workspace.ikon(ikon)}'
            f"{html.escape(judul)}</label>"
            for kode, ikon, judul, _ in panel
        )
        isi_panel = "".join(
            f'<div class="panel-latihan-st" data-panel="{kode}">{badan}</div>'
            for kode, _, _, badan in panel
        )
        blok_buat_latihan = (
            '<section class="buat-latihan-st">'
            '<h2 class="st profil-sr-st">Buat latihan</h2>'
            f"{tab}"
            f'<div class="tab-bar-st">{label}</div>'
            f"{panduan}{isi_panel}"
            "</section>"
        )
    else:
        # Hanya satu bentuk latihan yang tersedia — tab justru menambah klik
        # tanpa memberi pilihan. Tampilkan formnya langsung.
        blok_buat_latihan = (
            '<section class="buat-latihan-st">'
            '<h2 class="st profil-sr-st">Buat latihan</h2>'
            f"{panduan}{strip_sesi}"
            "</section>"
        )

    tautan_bantuan = (
        __import__("assistant_components").tombol_buka(
            __import__("assistant_inline").tujuan_anak(int(siswa["id"]), "rencana"),
            status_akses=__import__("assistant_entitlement_runtime").status_pengguna(pengguna),
        )
        if peran == "guru" and pengguna else ""
    )
    kartu_rencana = learning_cycle_ui.kartu_rencana(
        kon, int(siswa["id"]), slot_bantuan=tautan_bantuan,
    ) if section == "rencana" else ""
    latihan_manual = (
        '<section class="profil-formulaire-st">'
        f"{blok_buat_latihan}</section>"
    )
    if section == "rencana":
        isi_profil = kartu_rencana
    elif section == "riwayat":
        isi_profil = profile_workspace.riwayat(
            int(siswa["id"]), sesi, total_hasil, filter_profil,
            judul_topik=_nama_topik_sesi, tanggal=_tanggal_ringkas,
            badge_tinjauan=_badge_review_status, aksi_bagikan=_aksi_tautan,
        )
    else:
        isi_profil = (
            learning_cycle_ui.pengingat_rencana(kon, int(siswa["id"]))
            + latihan_manual + '<section class="profil-taches-st"><h2 class="st">Perlu ditindaklanjuti</h2>'
            '<p class="sub">Hingga tiga sesi terbaru · sesi lainnya di Riwayat.</p>'
            f'<div class="daftar-anak">{item}</div></section>'
        )

    return _halaman_stitch(
        f"{siswa['nama']} — {T.NAMA_PRODUK}",
        profile_workspace.bingkai(siswa, section, total_sesi, isi_profil, peran=peran, pesan=pesan,
                                  kelas_sekolah=_kelas_sekolah_profil(kon, siswa))
        + (bantuan_rencana if section == "rencana" else "")
        + (__import__("assistant_components").hubungkan_form(
            bantuan_latihan, f'form-latihan-{draf_aktif}-{siswa["id"]}', identitas_di_host=True,
        ) if section == "latihan" and bantuan_latihan else "")
        + ((
            __import__("assistant_components").tombol_buka(
                __import__("assistant_inline").tujuan_anak(int(siswa["id"]), "rencana"),
                status_akses=__import__("assistant_entitlement_runtime").status_pengguna(pengguna),
            )
        ) if section == "riwayat" and peran == "guru" and pengguna else ""),
        ident=(pengguna if pengguna else "guru", peran),
        kelas_bungkus="lebar pendamping-editorial-st profil-editorial-st profil-workspace-st",
        privat=privat,
    )
