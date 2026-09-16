"""Lapisan data sisi anak: ambil soal, simpan jawaban, kepemilikan akun.

Dipecah dari students.py (refactor 31 Aug 2026): halaman-halamannya pindah
ke student_pages.py; modul ini kini murni data + pembatasan akun, tanpa
HTML. Palang tetap: tidak pernah membaca kolom kunci/malrule untuk anak —
dijaga test_palang_* (monkeypatch sqlite3.Row).
"""

from __future__ import annotations

import html

import auth
import question_views
from database import isi_sesi
from templates import Soal



def _escape(t: str) -> str:
    return html.escape(str(t))

def beranda_murid(kon, siswa_id: int) -> dict:
    """Proyeksi metadata beranda tanpa membaca hasil atau alasan guru.

    Sesi terpandu memakai selector yang sama dengan reducer. Bila belum ada
    putaran aktif, satu latihan bebas level kini boleh disorot sebagai pintasan
    operasional; itu bukan keputusan materi/kelulusan. Sesi lama tetap sekunder.
    """
    from datetime import date
    import learning_cycle as siklus

    siswa = kon.execute(
        "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None:
        return {"level": "", "sesi": [], "utama_id": None, "terpandu": False}

    def tanggal(nilai):
        try:
            return date.fromisoformat(str(nilai)[:10])
        except ValueError:
            return date.min

    baris = kon.execute(
        """SELECT s.id, s.siswa_id, s.tanggal, s.dibuat, s.level, s.topik,
                  s.mode, s.format_jawaban, s.jenis, s.tujuan, s.putaran_id, s.selesai, s.direview,
                  s.dibatalkan,
                  (SELECT COUNT(*) FROM sesi_soal ss WHERE ss.sesi_id=s.id) AS jumlah,
                  (SELECT COUNT(*) FROM sesi_soal ss JOIN jawaban j ON j.sesi_soal_id=ss.id
                   WHERE ss.sesi_id=s.id AND
                     (TRIM(IFNULL(j.jawaban,'')) <> '' OR TRIM(IFNULL(j.cara,'')) <> ''
                      OR TRIM(IFNULL(j.restatement,'')) <> '' OR j.belum_pernah=1)) AS terisi
           FROM sesi s WHERE s.siswa_id = ? ORDER BY s.id DESC""",
        (siswa_id,),
    ).fetchall()
    putaran = tuple(
        siklus.PutaranSiklus(b["id"], siswa_id, b["level"], tanggal(b["dibuka"]))
        for b in kon.execute(
            "SELECT id, level, dibuka FROM putaran_fokus WHERE siswa_id=? ORDER BY id",
            (siswa_id,),
        )
    )
    kejadian = tuple(
        siklus.KejadianSiklus(b["id"], b["jenis"], tanggal(b["dibuat"]), b["putaran_id"])
        for b in kon.execute(
            """SELECT id, jenis, dibuat, putaran_id FROM kejadian_belajar
               WHERE siswa_id=? AND jenis IN
                 ('putaran_ditutup','diganti_level','override_ditutup') ORDER BY id""",
            (siswa_id,),
        )
    )
    metadata = siklus.BuktiSiklus(
        siswa_id, siswa["tingkat"],
        sesi=tuple(siklus.SesiSiklus(
            b["id"], b["siswa_id"], b["level"], b["tujuan"], tanggal(b["tanggal"]),
            dibuat=b["dibuat"], selesai=b["selesai"], putaran_id=b["putaran_id"],
            dibatalkan=b["dibatalkan"],
        ) for b in baris),
        putaran=putaran, kejadian=kejadian,
    )
    aktif = siklus._putaran_aktif(metadata)
    pilihan = siklus.sesi_berjalan(metadata)
    tersedia = [dict(b) for b in baris if b["dibatalkan"] is None]
    utama_id = pilihan.id if pilihan is not None else None
    if aktif is None:
        manual = [b for b in tersedia
                  if b["tujuan"] == "bebas" and b["selesai"] is None
                  and b["level"] == siswa["tingkat"] and b["jumlah"] > 0]
        if manual:
            utama_id = max(manual, key=lambda b: (b["terisi"] > 0, b["id"]))["id"]
    # Renderer hanya menerima kolom daftar putih; metadata putaran tidak
    # diteruskan ke template atau atribut HTML.
    kolom_aman = ("id", "tanggal", "level", "topik", "mode", "format_jawaban", "jenis", "tujuan",
                  "selesai", "direview", "jumlah", "terisi")
    return {"level": siswa["tingkat"],
            "sesi": [{k: b[k] for k in kolom_aman} for b in tersedia],
            "utama_id": utama_id, "terpandu": aktif is not None}


def sesi_murid(kon, siswa_id: int, sesi_id: int) -> dict | None:
    """Data sesi versi murid — TANPA kunci/malrule/diagnosis.

    Satu-satunya fungsi pengambil data untuk seluruh rute murid. Test palang
    mengawasi persis fungsi ini: kalau suatu hari seseorang menambah SELECT
    kunci ke dalamnya, test akan gagal sebelum sampai produksi.
    """
    baris = kon.execute(
        """SELECT s.id, s.tanggal, s.seed, s.level, s.topik,
                  s.mode, s.format_jawaban, s.tujuan, s.timer_mode, s.durasi_menit, s.timer_auto,
                  s.mulai, s.selesai, s.dibatalkan,
                  CASE WHEN s.mulai IS NULL THEN 0 ELSE MAX(0,
                    CAST(strftime('%s', datetime('now', '+7 hours')) AS INTEGER)
                    - CAST(strftime('%s', s.mulai) AS INTEGER)) END AS detik_lalu,
                  w.nama, w.id AS siswa_id
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id
           WHERE s.id = ? AND s.siswa_id = ?""",
        (sesi_id, siswa_id),
    ).fetchone()
    if not baris:
        return None  # bukan sesi milik murid ini ATAU tidak ada
    return dict(baris)

def soal_murid(kon, sesi_id: int, siswa_id: int) -> list[dict]:
    """Daftar soal versi murid: identitas + teks saja, tanpa kunci.

    Query di sini sengaja berupa daftar putih. Jalur lama memakai
    ``database.isi_sesi`` yang ikut SELECT kunci dan diagnosis meski hasilnya
    tidak dimasukkan ke HTML; capability bearer tidak boleh membaca data yang
    tidak dibutuhkan.
    """
    if not sesi_murid(kon, siswa_id, sesi_id):
        return []
    from choice_store import daftar_pilihan
    pilihan_sesi = daftar_pilihan(kon, sesi_id)
    baris_baris = kon.execute(
        """SELECT ss.id AS sesi_soal_id, ss.nomor,
                  ss.teks_soal, ss.bagian_soal, ss.tantangan_soal,
                  ss.minta_restatement, ss.penyajian_json,
                  ss.penyajian_versi, ss.renderer_versi, ss.asal_teks,
                  ss.status_visual, ss.mode_representasi,
                  ss.fingerprint_matematis, ss.fingerprint_penyajian,
                  s.id AS soal_id, s.template_id, s.parameter,
                  s.bagian, s.tantangan, s.level, s.cerita
           FROM sesi_soal ss
           JOIN soal s ON s.id = ss.soal_id
           WHERE ss.sesi_id = ?
           ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()
    keluar: list[dict] = []
    for b in baris_baris:
        penyajian = question_views.penyajian_dari_baris(b)
        jawab = kon.execute(
            """SELECT restatement, cara, jawaban, belum_pernah
               FROM jawaban j JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.sesi_id = ? AND ss.nomor = ?""",
            (sesi_id, b["nomor"]),
        ).fetchone()
        keluar.append(
            {
                "nomor": b["nomor"],
                "sesi_soal_id": b["sesi_soal_id"],
                "template_id": b["template_id"],
                "teks": penyajian.teks_soal,
                "penyajian": penyajian,
                "bagian": penyajian.bagian_soal,
                "tantangan": penyajian.tantangan_soal,
                "minta_restatement": penyajian.minta_restatement,
                "terjawab": dict(jawab) if jawab else None,
                "pilihan": pilihan_sesi.get(b['sesi_soal_id']),
            }
        )
    return keluar

def hasil_murid(kon, siswa_id: int, sesi_id: int) -> dict | None:
    """Hasil + PEMBAHASAN satu sesi untuk ANAK (poin b feedback Filia).

    Ini SATU-SATUNYA fungsi sisi anak yang boleh menyentuh kebenaran
    jawaban, dan syaratnya ketat:

      - Sesi wajib milik anak ini (lewat sesi_murid) -> None kalau bukan.
      - Sesi wajib SUDAH DIREVIEW guru (`sesi.direview` terisi) -> None
        kalau belum. Tanpa pagar ini, anak bisa membuka pembahasan (yang
        memuat jawaban akhir) sebelum pekerjaannya dinilai — itu sama
        dengan membocorkan kunci.

    Yang dikembalikan per soal: nomor, teks, jawaban anak sendiri,
    benar/salah, dan pembahasan. Yang SENGAJA TIDAK dikembalikan: kode
    diagnosis (K/H/E/N/B), malrule_id, dan alasan. Itu bahasa kerja guru;
    anak butuh tahu letak salahnya, bukan label tipe kesalahannya.

    Catatan palang: fungsi ini memang membaca kolom yang diblokir fixture
    `db_terjaga` (kunci lewat _soal_dari_baris, benar dari diagnosis),
    jadi ia TIDAK boleh dipanggil dari halaman kerja/daftar sesi. Halaman
    hasil adalah permukaan terpisah dengan gerbang direview di atas.
    """
    from teacher_pages import _soal_dari_baris  # late import: hindari siklus

    info = sesi_murid(kon, siswa_id, sesi_id)
    if not info:
        return None
    ditinjau = kon.execute(
        "SELECT direview FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()
    if not ditinjau or not ditinjau["direview"]:
        return None

    from choice_store import daftar_pilihan
    pilihan_pg = daftar_pilihan(kon, sesi_id)
    butir: list[dict] = []
    benar = 0
    for b in isi_sesi(kon, sesi_id):
        soal: Soal = _soal_dari_baris(b)
        ini_benar = bool(b["benar"])
        if ini_benar:
            benar += 1
        butir.append(
            {
                "nomor": b["nomor"],
                "teks": soal.teks,
                "penyajian": soal.penyajian,
                "jawabanku": next((o.label + ' — ' + o.teks for o in pilihan_pg[b['sesi_soal_id']].opsi if o.nilai == b['jawaban']), '') if b['sesi_soal_id'] in pilihan_pg else (b['jawaban'] or ''),
                "benar": ini_benar,
                "perlu_ditinjau": not ini_benar and b['jawaban_id'] is not None
                    and (not (b['jawaban'] or '').strip() or b['belum_pernah'] or (b['cara'] or '').startswith('[pilihan] bingung')),
                "dijawab": b["jawaban_id"] is not None,
                "pembahasan": soal.pembahasan or "",
                "template_id": b["template_id"],
            }
        )
    return {
        "sesi_id": sesi_id,
        "tanggal": info["tanggal"],
        "level": info["level"],
        "nama": info["nama"],
        "jumlah": len(butir),
        "benar": benar,
        "soal": butir,
    }


def semua_terisi(kon, siswa_id: int, sesi_id: int) -> bool:
    """True bila SEMUA soal sesi ini sudah punya isian.

    Sebuah soal dianggap terisi kalau ada baris jawaban dengan setidaknya
    satu kolom tidak kosong (jawaban, cara, restate, atau belum_pernah).
    Definisi ini KONSISTEN dengan simpan_jawaban_murid yang hanya menyimpan
    soal bila (jawaban or cara or restate or belum).

    Kalau sesi bukan milik murid → False (palang).
    """
    if not sesi_murid(kon, siswa_id, sesi_id):
        return False
    ada_kosong = kon.execute(
        """SELECT COUNT(*) FROM sesi_soal ss
           WHERE ss.sesi_id = ?
             AND NOT EXISTS (
               SELECT 1 FROM jawaban j WHERE j.sesi_soal_id = ss.id
                 AND (TRIM(IFNULL(j.jawaban,'')) <> ''
                      OR TRIM(IFNULL(j.cara,'')) <> ''
                      OR TRIM(IFNULL(j.restatement,'')) <> ''
                      OR j.belum_pernah = 1)
             )""",
        (sesi_id,),
    ).fetchone()[0]
    return ada_kosong == 0

def simpan_jawaban_murid(kon, siswa_id: int, sesi_id: int, data: dict) -> int | None:
    """Simpan jawaban dari form murid. Palang: hanya sesi miliknya sendiri.

    Mengembalikan JUMLAH soal yang tersimpan, atau None kalau sesi bukan
    milik murid ini — pemanggil harus menolak, bukan diam-diam menyimpan ke
    sesi orang lain.

    Jumlahnya dipakai halaman untuk memberi tahu anak berapa soal yang
    benar-benar masuk. "Berhasil" saja tidak cukup: anak yang mengira sudah
    mengisi 12 soal tapi ternyata 9 perlu tahu sekarang, bukan nanti.
    """
    info = sesi_murid(kon, siswa_id, sesi_id)
    if not info or info.get('selesai') or info.get('dibatalkan'):
        return None
    if info['format_jawaban'] == 'pilihan_ganda':
        import student_submissions
        from choice_store import daftar_pilihan
        student_submissions.validasi_versi(kon, sesi_id, data)
        opsi = daftar_pilihan(kon, sesi_id)
        data = dict(data)
        for nama in list(data):
            if nama.startswith('jwb_'):
                raise ValueError('Gunakan pilihan jawaban yang tersedia.')
            if nama.startswith('opsi_'):
                sid = nama[5:]
                if not sid.isascii() or not sid.isdigit() or int(sid) not in opsi:
                    raise ValueError('Butir bukan milik sesi ini.')
                data[f'jwb_{sid}'] = opsi[int(sid)].nilai_untuk(data.pop(nama))
    elif any(nama.startswith('opsi_') for nama in data):
        raise ValueError('Sesi ini memakai jawaban isian.')
    kode_sah = {k for k, _ in PILIHAN_CARA}
    jumlah = 0
    baris_soal = kon.execute(
        """SELECT ss.id AS sesi_soal_id
           FROM sesi_soal ss
           WHERE ss.sesi_id = ? ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()
    id_sah = {str(b['sesi_soal_id']) for b in baris_soal}
    awalan_field = ('jwb_', 'cara_', 'pilih_', 'restate_', 'blm_', 'hadir_blm_')
    for nama, nilai in data.items():
        if nama.startswith(awalan_field) and nama.rsplit('_', 1)[-1] not in id_sah:
            raise ValueError('Butir bukan milik sesi ini.')
        if len(nilai) > 8000:
            raise ValueError('Isian terlalu panjang.')
    for b in baris_soal:
        ssid = b["sesi_soal_id"]
        lama = kon.execute(
            "SELECT jawaban, cara, restatement, belum_pernah FROM jawaban WHERE sesi_soal_id=?",
            (ssid,),
        ).fetchone()
        lama = dict(lama) if lama else {}
        jawaban = data.get(f"jwb_{ssid}", lama.get("jawaban", "")).strip()
        cara_lama = lama.get('cara', '')
        if f'pilih_{ssid}' in data and cara_lama.startswith(AWALAN_PILIHAN):
            cara_lama = cara_lama.partition(' — ')[2]
        teks_cara = data.get(f"cara_{ssid}", cara_lama).strip()
        pilihan = data.get(f"pilih_{ssid}", "").strip()
        restate = data.get(f"restate_{ssid}", lama.get("restatement", "")).strip()
        penuh = f"jwb_{ssid}" in data or f"hadir_blm_{ssid}" in data
        belum = f"blm_{ssid}" in data if penuh else bool(lama.get("belum_pernah")) or f"blm_{ssid}" in data

        # Pilihan cepat digabung ke kolom `cara` yang sama, bukan kolom baru.
        # Alasannya: seluruh alur diagnosis (diagnosis.py) dan laporan guru
        # sudah membaca `cara`; kolom baru berarti dua tempat yang harus
        # diingat, dan yang terlupa akan gagal senyap.
        #
        # Pilihan yang tidak dikenal DIBUANG, bukan disimpan apa adanya:
        # nilainya datang dari form dan tidak boleh dipercaya.
        if pilihan and pilihan in kode_sah:
            cara = AWALAN_PILIHAN + pilihan
            if teks_cara:
                cara += " — " + teks_cara
        else:
            cara = teks_cara

        punya_field = any(
            k in data
            for k in (
                f"jwb_{ssid}", f"cara_{ssid}", f"pilih_{ssid}",
                f"restate_{ssid}", f"blm_{ssid}", f"hadir_blm_{ssid}",
            )
        )
        if not punya_field:
            continue
        if not (jawaban or cara or restate or belum):
            if punya_field:
                # Form mengirim field kosong ketika anak menghapus isian lama.
                # Hapus baris (diagnosis ikut cascade), jangan biarkan draft lama
                # diam-diam hidup dan ikut terkirim saat finalisasi.
                kon.execute(
                    "DELETE FROM jawaban WHERE sesi_soal_id = ?", (ssid,)
                )
            continue
        from database import simpan_jawaban

        simpan_jawaban(
            kon,
            ssid,
            jawaban=jawaban,
            cara=cara,
            restatement=restate,
            belum_pernah=belum,
        )
        if jawaban:
            kon.execute('DELETE FROM refleksi_jawaban WHERE sesi_soal_id=?', (ssid,))
        jumlah += 1
    return jumlah

def siswa_dari_akun(kon, pengguna: str) -> int | None:
    """ID siswa untuk akun murid ini, atau None kalau belum terhubung."""
    akun = auth.cari_akun(pengguna)
    if akun and akun.get("siswa_id") is not None:
        baris = kon.execute(
            "SELECT id FROM siswa WHERE id = ?", (int(akun["siswa_id"]),)
        ).fetchone()
        return int(baris["id"]) if baris else None
    baris = kon.execute(
        "SELECT id FROM siswa WHERE nama = ? COLLATE NOCASE", (pengguna.strip(),)
    ).fetchone()
    return int(baris["id"]) if baris else None

def akun_murid_dari_siswa(kon, siswa_id: int) -> str | None:
    """Nama login akun murid yang terikat ke siswa ini, atau None.

    Kebalikan siswa_dari_akun: siswa_id eksplisit menang, akun warisan
    tanpa siswa_id dicocokkan lewat nama siswa seperti dulu.
    """
    baris = kon.execute(
        "SELECT nama FROM siswa WHERE id = ?", (int(siswa_id),)
    ).fetchone()
    nama = baris["nama"].strip().lower() if baris else None
    warisan = None
    for a in auth.muat_akun():
        if a.get("peran") != "murid":
            continue
        if a.get("siswa_id") is not None:
            if int(a["siswa_id"]) == int(siswa_id):
                return a["pengguna"]
        elif nama and a["pengguna"].strip().lower() == nama:
            warisan = a["pengguna"]
    return warisan

PILIHAN_CARA: tuple[tuple[str, str], ...] = (
    ("hitung_satu_satu", "Aku hitung satu per satu"),
    ("lihat_pola", "Aku lihat polanya"),
    ("pakai_rumus", "Aku pakai cara cepat / rumus"),
    ("tanya_ingat", "Aku ingat dari soal yang mirip"),
    ("tebak", "Aku tebak saja"),
    ("bingung", "Aku bingung"),
)

AWALAN_PILIHAN = "[pilihan] "

AWALAN_DRILL = "[drill] "
