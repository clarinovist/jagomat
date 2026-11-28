"""Layar anak sesi Cek Kemampuan gratis: sapaan, soal, jeda, peta, keluar, Hore.

Murni render: menerima data dari ``students.soal_murid`` (tanpa kunci) dan
mengembalikan HTML. Palang murid: tidak ada kunci, benar/salah, skor, kategori,
atau label kelemahan di layar mana pun; hanya "sudah dijawab" dan "masih kosong".
Satu maskot per layar. JS hanya papan coret (``SKRIP_PAPAN``), tanpa network,
storage, atau autosave; panel dan tombolnya tersembunyi sampai skrip membukanya.
"""
from __future__ import annotations

import design_tokens as T
import pecahan
from brand import maskot
from cek_anak_komponen import (
    DOODLE_HORE, DOODLE_KEPALA, DOODLE_PETA, DOODLE_SAPAAN, IKON_JEDA, IKON_PENSIL,
    JEDA_SETELAH, TUJUAN_BERANDA_ANAK, TUJUAN_LOGIN_HASIL, TUJUAN_ORANG_TUA, Konteks, attr, esc, kepala_teal, kerangka, konfeti,
    label_topik, stiker, url,
)
from choice_pages import pertanyaan

KATA_TEMAN = (
    "Baca pelan-pelan, ya.", "Boleh pakai papan coret.", "Ragu? Lewati dulu juga boleh.",
    "Kamu hebat sudah sampai sini!", "Tarik napas, lalu baca lagi.",
)
KABAR = {
    "simpan": ("Jawaban tersimpan", True),
    "lewat": ("Dilewati dulu. Nanti bisa kembali.", False),
}
JUDUL_JEDA = {5: "Sepertiga jalan", 10: "Dua pertiga jalan"}
PESAN_BELUM_PILIH = "Pilih satu jawaban dulu, atau ketuk Lewati dulu."

SKRIP_PAPAN = """<script>
(function () {
  var tombol = document.getElementById('btn-coret');
  var papan = document.getElementById('papan');
  var kanvas = document.getElementById('kanvas');
  var hapus = document.getElementById('hapus-coret');
  if (!tombol || !papan || !kanvas || !hapus || !kanvas.getContext) { return; }
  var ctx = kanvas.getContext('2d');
  ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = kanvas.getAttribute('data-warna') || 'black';
  var turun = false;
  function titik(e) {
    var r = kanvas.getBoundingClientRect();
    return [(e.clientX - r.left) * kanvas.width / r.width, (e.clientY - r.top) * kanvas.height / r.height];
  }
  tombol.hidden = false;
  tombol.addEventListener('click', function () {
    papan.hidden = !papan.hidden;
    tombol.setAttribute('aria-expanded', String(!papan.hidden));
  });
  kanvas.addEventListener('pointerdown', function (e) {
    turun = true;
    kanvas.setPointerCapture(e.pointerId);
    var p = titik(e);
    ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(p[0] + 0.01, p[1]); ctx.stroke();
  });
  kanvas.addEventListener('pointermove', function (e) {
    if (!turun) { return; }
    var p = titik(e);
    ctx.lineTo(p[0], p[1]); ctx.stroke();
  });
  ['pointerup', 'pointercancel'].forEach(function (nama) {
    kanvas.addEventListener(nama, function () { turun = false; });
  });
  hapus.addEventListener('click', function () { ctx.clearRect(0, 0, kanvas.width, kanvas.height); });
})();
</script>"""


def sudah_dijawab(entri: dict) -> bool:
    """Sudah ada jawaban tersimpan (isi, bukan benar/salah)."""
    return bool(((entri.get("terjawab") or {}).get("jawaban") or "").strip())


def lokasi_berikut(k: Konteks, nomor: int, jumlah: int, dari_peta: bool, kabar: str) -> str:
    """Tujuan setelah menyimpan/melewati soal ``nomor`` (tanpa data jawaban).

    Dari peta selalu kembali ke peta (tanpa jeda); soal terakhir menuju peta;
    soal 5 dan 10 menuju jeda regang; selain itu soal berikutnya.
    """
    if dari_peta or nomor >= jumlah:
        return url(k, peta=1, ok=kabar)
    if nomor in JEDA_SETELAH:
        return url(k, jeda=nomor)
    return url(k, soal=nomor + 1, ok=kabar)


def layar_sapaan(k: Konteks, nama: str, jumlah: int) -> bytes:
    isi = f"""<section class="layar-cerah teal" aria-label="Sapaan">
<div class="doodle" aria-hidden="true">{DOODLE_SAPAAN}</div>
<div class="tengah">
{maskot("menyapa", 240, kelas="maskot-besar")}
<h1>Halo, {esc(nama)}!</h1>
<p class="besar">Aku si Jago. Hari ini kita main {jumlah} soal matematika bareng.</p>
<div class="cara"><div><b>1</b>Pilih jawaban</div><div><b>2</b>Ketuk Simpan</div><div><b>★</b>Kumpulkan bintang</div></div>
<p class="bantuan">Tidak ada batas waktu. Kalau bingung, boleh lewati dulu dan kembali nanti.</p>
<form method="post" action="{attr(k)}"><input type="hidden" name="aksi" value="mulai">
<button class="cta amber" type="submit">Ayo mulai!</button></form>
</div></section>"""
    return kerangka(f"Halo, {nama}", isi)


def _jejak(daftar: list, nomor: int) -> str:
    titik = []
    for entri in daftar:
        n = entri["nomor"]
        if n == nomor:
            kelas = "kini"
        elif sudah_dijawab(entri):
            kelas = "isi"
        elif n < nomor:
            kelas = "lewat"
        else:
            kelas = ""
        titik.append(f'<li class="{kelas}"></li>')
    bintang = sum(1 for e in daftar if sudah_dijawab(e))
    return (
        f'<div class="jejak"><ol aria-hidden="true">{"".join(titik)}</ol>'
        f'<div class="teks"><span>Soal <b>{nomor}</b> dari {len(daftar)}</span>'
        f'<span>{bintang} bintang</span></div></div>'
    )


def _opsi(entri: dict) -> str:
    pilihan = entri["pilihan"]
    ssid = entri["sesi_soal_id"]
    jawaban = ((entri.get("terjawab") or {}).get("jawaban") or "")
    hanya_huruf = entri["template_id"] == "jaring_jaring"  # label sudah ada di diagram
    panjang = any(len(o.teks) > 5 for o in pilihan.opsi)
    isi = []
    for o in pilihan.opsi:
        teks = "" if hanya_huruf else pecahan.render(o.teks)
        pilih = " checked" if jawaban and jawaban == o.nilai else ""
        isi.append(
            f'<label class="opsi-satu"><input type="radio" name="opsi_{ssid}" value="{esc(o.id)}"{pilih}>'
            f'<span class="kotak"><span class="huruf">{esc(o.label)}</span>{teks}</span></label>'
        )
    kelas = "opsi panjang" if panjang and not hanya_huruf else "opsi"
    return (
        f'<fieldset class="{kelas}"><legend class="sr-saja">Pilihan jawaban</legend>'
        f'{"".join(isi)}</fieldset>'
    )


def _kabar(kode: str, galat: str) -> str:
    if galat:
        return f'<p class="kabar netral" role="status">{esc(galat)}</p>'
    if kode in KABAR:
        teks, bintang = KABAR[kode]
        tanda = '<span class="bintang" aria-hidden="true">★</span>' if bintang else ""
        return f'<p class="kabar" role="status">{tanda}{esc(teks)}</p>'
    return ""


def _panel_istirahat() -> str:
    return (
        f'<details class="rehat"><summary>{IKON_JEDA}Istirahat</summary>'
        '<div class="rehat-panel"><h2>Mau istirahat dulu?</h2>'
        '<p class="bantuan">Jawaban yang sudah disimpan aman. Pilihanmu di soal ini ikut '
        'tersimpan. Minum air dulu, nanti lanjut dari soal yang sama.</p>'
        '<button class="sekunder" type="submit" form="f-soal" name="aksi" value="keluar">'
        'Simpan &amp; keluar</button></div></details>'
    )


def layar_soal(
    k: Konteks, nama: str, daftar: list, nomor: int, revisi: int,
    *, t0: int, dari_peta: bool = False, kabar: str = "", galat: str = "",
) -> bytes:
    entri = daftar[nomor - 1]
    jumlah = len(daftar)
    teks_soal = pertanyaan(
        entri["penyajian"], entri["pilihan"], entri["template_id"], namespace=str(nomor)
    )
    lewati = lokasi_berikut(k, nomor, jumlah, dari_peta, "lewat")
    dari = '<input type="hidden" name="dari" value="peta">' if dari_peta else ""
    kepala = kepala_teal(
        f'<span class="judul-kecil">Petualangan {esc(nama)}</span>{_panel_istirahat()}',
        DOODLE_KEPALA, tambahan=_jejak(daftar, nomor),
    )
    isi = f"""{kepala}
<main class="isi-anak">
{_kabar(kabar, galat)}
<form id="f-soal" method="post" action="{attr(k)}">
<button class="bawaan" type="submit" name="aksi" value="simpan" tabindex="-1" aria-hidden="true">Simpan jawaban</button>
<input type="hidden" name="soal" value="{nomor}">
<input type="hidden" name="revisi_pekerjaan" value="{int(revisi)}">
<input type="hidden" name="t0" value="{int(t0)}">
{dari}
{label_topik(entri["template_id"])}
<div class="kertas">{teks_soal}</div>
{_opsi(entri)}
<div class="alat-kecil">
<div class="teman">{maskot("berpikir", 96)}<span class="gel">{esc(KATA_TEMAN[(nomor - 1) % len(KATA_TEMAN)])}</span></div>
<button class="btn-coret" type="button" id="btn-coret" aria-expanded="false" aria-controls="papan" hidden>{IKON_PENSIL}Papan coret</button>
</div>
<div class="papan" id="papan" hidden><span class="ket">Coret-coret di sini</span>
<button class="hapus" type="button" id="hapus-coret">Hapus</button>
<canvas id="kanvas" width="680" height="320" data-warna="{T.TEKS_JUDUL}" aria-label="Papan coret, hanya untuk coret-coret"></canvas></div>
<div class="aksi-soal">
<a class="sekunder" href="{esc(lewati)}">Lewati dulu</a>
<button class="cta" type="submit" name="aksi" value="simpan">Simpan jawaban</button>
</div>
</form>
</main>"""
    return kerangka(f"Soal {nomor} dari {jumlah}", isi, skrip=SKRIP_PAPAN)


def _angka_napas() -> str:
    angka = "".join(f'<span class="n" style="--i:{i}">{5 - i}</span>' for i in range(5))
    return f'<p class="hitung-napas" aria-hidden="true">{angka}<span class="siap">Siap!</span></p>'


def layar_jeda(k: Konteks, nomor: int, jumlah: int) -> bytes:
    isi = f"""<section class="layar-cerah krem" aria-label="Jeda regang">
<div class="tengah">
{maskot("merayakan", 240, kelas="maskot-sedang")}
<p class="eyebrow">{esc(JUDUL_JEDA.get(nomor, "Tinggal sedikit lagi"))}</p>
<h1>Wah, sudah {nomor} soal!</h1>
<p class="besar">Regangkan badan dulu bareng si Jago, yuk.</p>
<div class="regang" aria-hidden="true"><span>Tarik</span><span>Putar</span><span>Goyang</span></div>
{_angka_napas()}
<p class="bantuan">Tarik napas… hembuskan… lalu lanjut kalau sudah siap.</p>
<a class="cta" href="{attr(k, soal=min(nomor + 1, jumlah))}">Lanjut ke soal berikutnya</a>
</div></section>"""
    return kerangka(f"Jeda setelah soal {nomor}", isi)


def layar_peta(
    k: Konteks, nama: str, daftar: list, revisi: int, *, kabar: str = "",
) -> bytes:
    jumlah = len(daftar)
    kosong = sum(1 for e in daftar if not sudah_dijawab(e))
    kata = (
        f"Ada {kosong} soal yang masih kosong. Mau dicoba lagi?"
        if kosong else "Semua soal sudah dijawab. Keren!"
    )
    ubin = []
    for e in daftar:
        n = e["nomor"]
        ada = sudah_dijawab(e)
        status = "sudah dijawab" if ada else "masih kosong"
        ubin.append(
            f'<li><a class="{"" if ada else "kosong"}" href="{attr(k, soal=n, dari="peta")}" '
            f'aria-label="Soal {n}, {status}">{n}<small>{"★" if ada else "kosong"}</small></a></li>'
        )
    catatan = f"{kosong} soal masih kosong. " if kosong else ""
    kepala = kepala_teal(
        '<span class="judul-kecil">Hampir selesai!</span>', DOODLE_PETA,
        tambahan="<h1>Lihat lagi soal-soalmu</h1>",
    )
    isi = f"""{kepala}
<main class="isi-anak">
{_kabar(kabar, "")}
<div class="sapa">{maskot("membaca", 96)}<p class="gelembung">{esc(kata)}</p></div>
<ul class="peta-soal" aria-label="Peta {jumlah} soal">{"".join(ubin)}</ul>
<p class="legenda"><span>★ = sudah dijawab</span><span>Kotak putus-putus = masih kosong</span></p>
<p class="bantuan">Ketuk nomornya untuk membuka lagi. Kalau memang belum tahu, tidak apa-apa dikosongkan.</p>
<details class="kumpul"><summary>Kumpulkan jawaban</summary>
<div class="kumpul-panel"><h2>Kumpulkan sekarang?</h2>
<p class="bantuan">{esc(catatan)}Setelah dikumpulkan, jawaban tidak bisa diubah lagi.</p>
<form method="post" action="{attr(k)}"><input type="hidden" name="aksi" value="kumpul">
<input type="hidden" name="revisi_pekerjaan" value="{int(revisi)}">
<button class="cta koral" type="submit">Ya, kumpulkan</button></form>
<p class="bantuan">Mau cek lagi? Ketuk nomor soalnya di atas.</p></div></details>
</main>"""
    return kerangka("Cek soal terlewat", isi)


def layar_keluar(k: Konteks) -> bytes:
    isi = f"""<section class="layar-cerah teal" aria-label="Tersimpan">
<div class="doodle" aria-hidden="true">{DOODLE_SAPAAN}</div>
<div class="tengah">
{maskot("menyapa", 240, kelas="maskot-sedang")}
<h1>Tersimpan!</h1>
<p class="besar">Jawabanmu aman. Lanjutkan nanti lewat tautan yang sama, ya.</p>
<a class="cta amber" href="{attr(k)}">Lanjut mengerjakan sekarang</a>
</div></section>"""
    return kerangka("Tersimpan", isi)


def _blok_serah(k: Konteks) -> str:
    if k.di_hp_ini:
        return (
            f'<a class="cta putih" href="{esc(TUJUAN_LOGIN_HASIL)}">'
            'Ayah/Bunda, masuk untuk lihat hasil</a>'
        )
    if k.di_akun:
        return (
            f'<a class="cta putih" href="{esc(TUJUAN_ORANG_TUA)}">Tanya Ayah/Bunda</a>'
            f'<a class="cta putih" href="{esc(TUJUAN_BERANDA_ANAK)}">Kembali ke beranda</a>'
            '<p class="serah">Ayah/Bunda membuka hasilnya lewat Halaman Ayah/Bunda.</p>'
        )
    return (
        '<p class="serah">Tunjukkan layar ini ke Ayah/Bunda. '
        'Hasilnya dibuka di HP Ayah/Bunda.</p>'
    )


def layar_hore(k: Konteks, nama: str, dijawab: int, jumlah: int) -> bytes:
    isi = f"""<section class="layar-cerah teal" aria-label="Selesai">
{konfeti()}
<div class="doodle" aria-hidden="true">{DOODLE_HORE}</div>
<div class="tengah">
{maskot("medali", 240, kelas="maskot-sedang")}
<h1>Hore, {esc(nama)} selesai!</h1>
<div class="stiker">{stiker(jumlah)}</div>
<p class="besar">Kamu dapat stiker <b>Pejuang {int(jumlah)} Soal</b>.</p>
<div class="angka-usaha"><span>{int(dijawab)} dari {int(jumlah)} soal dijawab</span><span>tanpa menyerah</span></div>
<p class="besar">Sekarang panggil Ayah atau Bunda, ya. Bagian berikutnya untuk mereka.</p>
{_blok_serah(k)}
</div></section>"""
    return kerangka(f"Hore, {nama} selesai", isi)


def layar_pesan(judul: str, teks: str, label_tautan: str, tujuan: str) -> bytes:
    """Pesan netral (mis. revisi usang): jelaskan lalu arahkan kembali."""
    isi = f"""<section class="layar-cerah krem" aria-label="{esc(judul)}">
<div class="tengah">
<h1>{esc(judul)}</h1>
<p class="kotak-galat" role="alert">{esc(teks)}</p>
<a class="cta" href="{esc(tujuan)}">{esc(label_tautan)}</a>
</div></section>"""
    return kerangka(judul, isi)
