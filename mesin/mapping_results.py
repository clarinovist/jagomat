"""Ringkasan pemetaan untuk guru; status/fokus tetap milik reducer siklus."""
from __future__ import annotations

import html
from collections import Counter, defaultdict

import design_tokens as T
import learning_cycle as lc
from cycle_carry import bukti_lanjutan
from learning_journey import perjalanan_belajar
from template_labels import nama_tipe_soal


GAYA_HASIL = f"""
.hasil-pemetaan-st {{
  margin: {T.SP_5} 0; padding: {T.SP_5}; background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KARTU_BESAR};
  scroll-margin-top: {T.SP_4};
}}
.hasil-pemetaan-st h2 {{ margin: 0 0 {T.SP_3}; color: {T.TEKS_JUDUL}; }}
.hasil-pemetaan-st h3 {{ margin: {T.SP_4} 0 {T.SP_2}; }}
.hasil-pemetaan-st p {{ line-height: {T.LINE_HEIGHT}; }}
.hasil-pemetaan-st .hasil-batas-st {{ color: {T.TEKS_SUBTLE}; font-size: .9rem; }}
.hasil-angka-st {{
  display: flex; flex-wrap: wrap; gap: {T.SP_3}; padding: 0; list-style: none;
}}
.hasil-angka-st li {{
  background: {T.LATAR_KARTU_SEKUNDER}; padding: {T.SP_3} {T.SP_4};
  border-radius: {T.RADIUS_KECIL}; color: {T.TEKS_JUDUL};
}}
.hasil-pemetaan-st summary {{
  cursor: pointer; min-height: {T.TARGET_SENTUH}; padding: {T.SP_3} 0;
  font-weight: 700; color: {T.TEKS_JUDUL};
}}
.hasil-pemetaan-st summary:focus-visible {{ outline: 2px solid {T.AKSEN_TEAL_TUA}; }}
.hasil-materi-st {{ margin: 0; padding: 0; list-style: none; }}
.hasil-materi-st li {{
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: {T.SP_3}; padding: {T.SP_3} 0; border-top: 1px solid {T.BORDER_HALUS};
  overflow-wrap: anywhere;
}}
.hasil-materi-st span {{ color: {T.TEKS_SUBTLE}; }}
@media (max-width: 40rem) {{
  .hasil-pemetaan-st {{ padding: {T.SP_4}; }}
  .hasil-materi-st li {{ grid-template-columns: minmax(0, 1fr); gap: {T.SP_1}; }}
}}
"""

_LABEL = {
    "tepat": "Jawaban tepat", "K": "Tinjau konsep", "H": "Periksa hitungan",
    "B": "Baca ulang soal", "E": "Periksa penulisan jawaban",
    "N": "Tanyakan cara menjawab", "T": "Materi belum dikenalkan",
    "dilewati": "Dilewati", "belum": "Perlu ditinjau",
}


def sesi_pemetaan_aktif(bukti: lc.BuktiSiklus, sesi_id: int):
    """Batasi hasil khusus pemetaan pada sesi selesai di putaran/level aktif."""
    putaran = lc._putaran_aktif(bukti)
    if putaran is None:
        return None
    return next((sesi for sesi in bukti.sesi
                 if sesi.id == sesi_id and sesi.siswa_id == bukti.siswa_id
                 and sesi.putaran_id == putaran.id
                 and sesi.level == putaran.level == bukti.level_aktif
                 and sesi.tujuan == "pemetaan" and sesi.selesai is not None
                 and sesi.dibatalkan is None), None)


def _kategori(outcome: lc.OutcomeSiklus) -> str:
    if outcome.dilewati:
        return "dilewati"
    if outcome.benar and not outcome.kode_final:
        return "tepat"
    return outcome.kode_final if outcome.kode_final in _LABEL else "belum"


def _temuan(outcomes) -> str:
    """Hitung catatan deskriptif, bukan skor kelemahan atau kelulusan."""
    jumlah = Counter(_kategori(item) for item in outcomes)
    per_materi = defaultdict(Counter)
    for item in outcomes:
        per_materi[item.template_id][_kategori(item)] += 1
    rincian = []
    urutan = sorted(per_materi.items(), key=lambda item: (
        -sum(nilai for kode, nilai in item[1].items() if kode != "tepat"),
        nama_tipe_soal(item[0]),
    ))
    for template, catatan in urutan:
        teks = " · ".join(f"{label}: {catatan[kode]} soal"
                          for kode, label in _LABEL.items() if catatan[kode])
        rincian.append(f'<li><b>{html.escape(nama_tipe_soal(template))}</b>'
                       f'<span>{html.escape(teks)}</span></li>')
    tinjau = sum(nilai for kode, nilai in jumlah.items() if kode not in {"tepat", "dilewati"})
    return (
        '<ul class="hasil-angka-st" aria-label="Ringkasan catatan jawaban">'
        f'<li><b>{jumlah["tepat"]} tepat</b></li>'
        f'<li><b>{tinjau} perlu perhatian</b></li>'
        f'<li><b>{jumlah["dilewati"]} dilewati</b></li></ul>'
        '<h3>Catatan per materi</h3>'
        '<ul class="hasil-materi-st">' + "".join(rincian[:5]) + '</ul>'
        + ('<details><summary>Lihat materi lainnya</summary><ul class="hasil-materi-st">'
           + "".join(rincian[5:]) + '</ul></details>' if len(rincian) > 5 else '')
        + '<p class="hasil-batas-st">Jawaban tepat adalah catatan hasil, bukan klaim penguasaan. '
        'Materi belum dikenalkan bukan kelemahan; soal dilewati bukan jawaban benar.</p>'
    )


def render_sementara(outcomes, *, draf_gagal: bool = False) -> str:
    """Ringkasan tampilan saja; tidak pernah dikirim sebagai bukti ke reducer."""
    if draf_gagal:
        judul = "Ringkasan sementara belum ditampilkan"
        isi = '<p>Selesaikan tinjauan pada soal yang ditandai. Isian perubahan tetap ada di formulir.</p>'
    else:
        judul = "Ringkasan sementara sesi ini"
        isi = _temuan(outcomes)
    return (
        '<section class="hasil-pemetaan-st" id="ringkasan-sementara" aria-labelledby="judul-sementara">'
        f'<h2 id="judul-sementara">{judul}</h2>'
        '<p><b>Belum menjadi bukti pemetaan.</b> Ini ringkasan penilaian yang ditampilkan '
        'saat halaman dibuka. Perubahan isian perlu dikonfirmasi sebelum masuk hasil pemetaan.</p>'
        f'{isi}<p>Tinjau jawaban dan cara anak di bawah, lalu pilih <b>Konfirmasi hasil</b>. '
        'Sesudahnya, Jagomat menampilkan hasil pemetaan dan langkah berikutnya.</p></section>'
    )


def bukti_pemetaan(bukti: lc.BuktiSiklus):
    """Pakai filter/provenance yang sama dengan reducer, termasuk carry dan mode."""
    sumber = bukti_lanjutan(bukti)
    return lc._sesi_bukti_pemetaan(sumber, lc._putaran_aktif(sumber))


def render_hasil(bukti: lc.BuktiSiklus, sesi_id: int) -> str:
    """Gabungkan hanya snapshot pemetaan yang dipakai reducer, bukan diagnosis mutable."""
    sesi = sesi_pemetaan_aktif(bukti, sesi_id)
    if sesi is None or sesi.dikonfirmasi is None or sesi.konfirmasi_id is None:
        return ""
    perjalanan = perjalanan_belajar(bukti, bukti.siswa_id)
    terpilih = bukti_pemetaan(bukti)
    # Representasi yang terpisah tidak boleh diam-diam diklaim ikut hasil ini.
    if sesi_id not in {item.id for item in terpilih}:
        return ""
    jumlah = len(perjalanan.tanggal_pemetaan)
    batas = (
        "Gambaran awal, belum kesimpulan akhir. Pemetaan awal memerlukan tiga sesi pada tanggal berbeda."
        if jumlah < 3 else
        "Tiga tanggal pemetaan sudah terkumpul. Pola yang baru muncul sekali masih perlu diperiksa pada sesi lain."
    )
    fokus = ""
    if perjalanan.fokus:
        daftar = "".join(
            f'<li>{html.escape(nama_tipe_soal(item.kunci[0]))} — '
            f'{html.escape(_LABEL.get(item.kunci[1], "Tinjau bersama"))}</li>'
            for item in perjalanan.fokus
        )
        fokus = f'<h3>Fokus belajar yang disarankan</h3><ol>{daftar}</ol>'
    else:
        fokus = (
            '<p>Belum ada fokus belajar yang ditetapkan dari bukti saat ini. '
            'Catatan per materi masih menjadi bahan pantauan, bukan label kelemahan anak.</p>'
        )
    catatan = "".join(f'<p class="hasil-batas-st">{html.escape(teks)}</p>' for teks in perjalanan.catatan)
    return (
        '<section class="hasil-pemetaan-st" id="hasil-pemetaan" aria-labelledby="judul-hasil-pemetaan">'
        '<h2 id="judul-hasil-pemetaan">Hasil pemetaan terkonfirmasi</h2>'
        f'<p><b>Pemetaan awal: {min(jumlah, 3)} dari 3 tanggal</b><br>'
        'Target awal: tiga sesi pada tanggal berbeda.</p>'
        f'<p>{batas}</p>'
        '<p>Gabungan catatan dari sesi pemetaan terkonfirmasi yang relevan untuk rencana saat ini.</p>'
        + _temuan(tuple(outcome for item in terpilih for outcome in item.outcomes))
        + fokus + catatan + '</section>'
    )
