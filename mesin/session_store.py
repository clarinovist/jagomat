"""Pembuatan sesi biasa, gabungan, urutan, dan remedial."""
from __future__ import annotations

import sqlite3
from typing import Any

from generator import LEVEL_BAWAAN
from templates import Soal
from topics import TOPIK_BAWAAN


def _simpan_butir_sesi(
    kon: sqlite3.Connection,
    sesi_id: int,
    nomor: int,
    soal: Soal,
    *,
    question_views_module,
    simpan_soal_func,
    serialisasi,
) -> int:
    """Simpan relasi soal beserta snapshot penyajiannya."""
    penyajian = question_views_module.penyajian_dari_soal(soal)
    soal_id = simpan_soal_func(kon, soal)
    cur = kon.execute(
        """INSERT INTO sesi_soal (
               sesi_id, soal_id, nomor,
               teks_soal, bagian_soal, tantangan_soal, minta_restatement,
               penyajian_json, penyajian_versi, renderer_versi, asal_teks,
               status_visual, mode_representasi, fingerprint_matematis,
               fingerprint_penyajian
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sesi_id,
            soal_id,
            nomor,
            penyajian.teks_soal,
            penyajian.bagian_soal,
            int(penyajian.tantangan_soal),
            int(penyajian.minta_restatement),
            serialisasi(penyajian),
            penyajian.penyajian_versi,
            penyajian.renderer_versi,
            penyajian.asal_teks,
            penyajian.status_visual,
            penyajian.mode_representasi,
            penyajian.fingerprint_matematis,
            penyajian.fingerprint_penyajian,
        ),
    )
    butir_id = int(cur.lastrowid)
    import context_store
    context_store.simpan_butir(kon, sesi_id, butir_id, soal)
    return butir_id


# ── Sesi ────────────────────────────────────────────────────────────────


def buat_sesi(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    topik: str = TOPIK_BAWAAN,
    tanggal: str | None = None,
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    timer_mode: str = "tanpa",
    durasi_menit: int = 15,
    timer_auto: int = 0,
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
    *,
    pembuat_lembar,
    simpan_butir,
) -> int:
    """Bangkitkan lembar dari seed, simpan soalnya ke bank, rangkai jadi sesi."""
    MODE_SAH = ("diagnostik", "drill")
    TIMER_SAH = ("tanpa", "sesi", "soal")
    if mode not in MODE_SAH:
        raise ValueError(f"mode tidak dikenal: {mode!r} (sah: {', '.join(MODE_SAH)})")
    if timer_mode not in TIMER_SAH:
        raise ValueError(
            f"timer_mode tidak dikenal: {timer_mode!r} (sah: {', '.join(TIMER_SAH)})"
        )
    if mode == "diagnostik":
        timer_mode, durasi_menit, timer_auto = "tanpa", 15, 0
    if not isinstance(durasi_menit, int) or not 1 <= durasi_menit <= 180:
        raise ValueError(f"durasi_menit tidak wajar: {durasi_menit!r}")

    from choice_store import validasi_format
    validasi_format(format_jawaban)
    from choice_generation import buat_lembar_pilihan
    pembuat = buat_lembar_pilihan if format_jawaban == 'pilihan_ganda' else pembuat_lembar
    lembar = pembuat(seed, level=level, topik=topik, jumlah_soal=jumlah_soal)
    # Level yang DICATAT adalah level yang benar-benar dipakai generator,
    # bukan yang diminta. `siswa.tingkat` teks bebas, dan `_level_efektif`
    # menormalkan nilai tak dikenal ke level paket — menyimpan yang mentah
    # membuat kolom ini berbohong: halaman murid menampilkan "level kelas 4"
    # untuk lembar yang isinya P3, dan laporan guru ikut salah label.
    # Level yang sah tidak tersentuh: untuk itu lembar.level == level.
    level = lembar.level

    kon.execute("SAVEPOINT buat_sesi_snapshot")
    try:
        if tanggal:
            cur = kon.execute(
                """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                     timer_mode, durasi_menit, timer_auto, tanggal, format_jawaban)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (siswa_id, seed, topik, level, mode,
                 timer_mode, durasi_menit, timer_auto, tanggal, format_jawaban),
            )
        else:
            cur = kon.execute(
                """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                     timer_mode, durasi_menit, timer_auto, format_jawaban)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (siswa_id, seed, topik, level, mode,
                 timer_mode, durasi_menit, timer_auto, format_jawaban),
            )
        sesi_id = int(cur.lastrowid)

        for nomor, soal in enumerate(lembar.soal, start=1):
            simpan_butir(kon, sesi_id, nomor, soal)
        if format_jawaban == 'pilihan_ganda':
            import choice_store
            choice_store.lengkapi_sesi(kon, siswa_id, sesi_id, lembar)
        kon.execute("RELEASE SAVEPOINT buat_sesi_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_snapshot")
        raise


def buat_sesi_dari_urutan(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    urutan: tuple[str, ...],
    topik: str | Any = TOPIK_BAWAAN,
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    jenis: str = "biasa",
    sumber_sesi_id: int | None = None,
    *,
    soal_terpilih: tuple[Soal, ...] | None = None,
    pembuat_lembar,
    simpan_butir,
) -> int:
    """Sesi dengan komposisi soal DITENTUKAN pemanggil, bukan dari paket.

    Dipakai remedial: template diambil dari kesalahan anak, bukan dari
    komposisi bawaan level. Sengaja fungsi terpisah, bukan parameter
    tambahan di buat_sesi — pemanggil biasa tidak boleh bisa menyetel
    komposisi tanpa sadar, dan alur normalnya tetap satu jalur.

    `topik` boleh objek Topik (paket ad-hoc lintas topik): yang tersimpan
    ke kolom `sesi.topik` adalah id-nya, supaya `topics.dari_sesi` bisa
    merekonstruksi paket yang sama saat lembar dicetak ulang.
    """
    if jenis not in ("biasa", "remedial"):
        raise ValueError(f"jenis sesi tidak dikenal: {jenis!r}")
    if jenis == "biasa" and sumber_sesi_id is not None:
        raise ValueError("sesi biasa tidak boleh memiliki sumber remedial")
    if soal_terpilih is None:
        lembar = pembuat_lembar(seed, urutan=urutan, level=level, topik=topik)
    else:
        from collections import Counter
        from generator import Lembar

        if (Counter(s.template_id for s in soal_terpilih) != Counter(urutan)
                or any(s.level != level for s in soal_terpilih)):
            raise ValueError("soal terpilih tidak cocok dengan komposisi atau level")
        lembar = Lembar(seed, soal_terpilih, level)
    topik_id = getattr(topik, "id", topik)
    kon.execute("SAVEPOINT buat_sesi_urutan_snapshot")
    try:
        cur = kon.execute(
            """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                 timer_mode, durasi_menit, timer_auto,
                                 jenis, sumber_sesi_id)
               VALUES (?, ?, ?, ?, ?, 'tanpa', 15, 0, ?, ?)""",
            (siswa_id, seed, topik_id, lembar.level, mode, jenis, sumber_sesi_id),
        )
        sesi_id = int(cur.lastrowid)
        for nomor, soal in enumerate(lembar.soal, start=1):
            simpan_butir(kon, sesi_id, nomor, soal)
        kon.execute("RELEASE SAVEPOINT buat_sesi_urutan_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_urutan_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_urutan_snapshot")
        raise


def buat_sesi_gabungan(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int,
    topik_ids: list[str],
    level: str = LEVEL_BAWAAN,
    mode: str = "diagnostik",
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
    *,
    pembuat_lembar,
    simpan_butir,
    pilih_level,
) -> int:
    """Sesi lintas BEBERAPA topik pilihan guru (poin 4 tahap 2).

    Kolom `sesi.topik` menyimpan id gabungan ("gabungan:a,b") sehingga
    sesi lama tetap bisa dibaca: `topics.dari_sesi` mengurainya kembali.
    Soalnya sendiri sudah tersimpan baris-per-baris di tabel soal, jadi
    replay tidak bergantung pada paket ad-hoc ini. Default diagnostik dijaga
    untuk pemanggil internal lama; form gabungan mengirim mode secara eksplisit.
    """
    if mode not in ("diagnostik", "drill"):
        raise ValueError(f"mode tidak dikenal: {mode!r}")

    from topics import gabungan

    paket = gabungan(topik_ids)
    # Level datang dari `siswa.tingkat` (teks bebas), bukan dari pilihan
    # guru — dan tidak semua topik punya semua level (logika melompati P4,
    # kombinatorik mulai P5). Anak P4 yang memilih dua topik tanpa P4 dulu
    # membuat generator melempar ValueError dan handler mati. Level yang
    # bukan pilihan pengguna dinormalkan, bukan ditolak.
    if level not in paket.komposisi:
        level = pilih_level(level, paket.komposisi)
    from choice_store import validasi_format
    from choice_generation import buat_lembar_pilihan
    validasi_format(format_jawaban)
    pembuat = buat_lembar_pilihan if format_jawaban == 'pilihan_ganda' else pembuat_lembar
    lembar = pembuat(seed, level=level, topik=paket, jumlah_soal=jumlah_soal)
    kon.execute("SAVEPOINT buat_sesi_gabungan_snapshot")
    try:
        cur = kon.execute(
            """INSERT INTO sesi (siswa_id, seed, topik, level, mode,
                                 timer_mode, durasi_menit, timer_auto, format_jawaban)
               VALUES (?, ?, ?, ?, ?, 'tanpa', 15, 0, ?)""",
            (siswa_id, seed, paket.id, lembar.level, mode, format_jawaban),
        )
        sesi_id = int(cur.lastrowid)
        for nomor, soal in enumerate(lembar.soal, start=1):
            simpan_butir(kon, sesi_id, nomor, soal)
        if format_jawaban == 'pilihan_ganda':
            import choice_store
            choice_store.lengkapi_sesi(kon, siswa_id, sesi_id, lembar)
        kon.execute("RELEASE SAVEPOINT buat_sesi_gabungan_snapshot")
        return sesi_id
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT buat_sesi_gabungan_snapshot")
        kon.execute("RELEASE SAVEPOINT buat_sesi_gabungan_snapshot")
        raise


def _baris_sasaran_remedial(
    kon: sqlite3.Connection,
    siswa_id: int,
    sesi_id: int | None = None,
) -> list[sqlite3.Row]:
    """Bukti diagnosis sah, terbaru lebih dulu per template."""
    syarat_sesi = " AND se.id = ?" if sesi_id is not None else ""
    parameter: tuple[int, ...] = (
        (siswa_id, sesi_id) if sesi_id is not None else (siswa_id,)
    )
    return kon.execute(
        """SELECT s.template_id,
                  se.id AS sesi_id,
                  se.tanggal,
                  ss.nomor,
                  d.benar,
                  IFNULL(d.kode_final, d.kode_usulan) AS kode,
                  d.alasan
           FROM diagnosis d
           JOIN jawaban j    ON j.id = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id = ss.soal_id
           WHERE se.siswa_id = ? AND se.format_jawaban='isian'
             AND se.selesai IS NOT NULL
             AND se.direview IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM pilot_sesi ps WHERE ps.sesi_id=se.id)"""
        + syarat_sesi
        + " ORDER BY se.tanggal DESC, se.id DESC, ss.nomor DESC",
        parameter,
    ).fetchall()


def _susun_sasaran(baris: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Ringkas bukti per template; hanya kesalahan terbaru non-T yang aktif."""
    from topics import pemilik_template

    jumlah_salah: dict[str, int] = {}
    for bukti in baris:
        kode = bukti["kode"]
        if not bukti["benar"] and kode != "T":
            template_id = bukti["template_id"]
            jumlah_salah[template_id] = jumlah_salah.get(template_id, 0) + 1

    terbaru: dict[str, sqlite3.Row] = {}
    for bukti in baris:
        terbaru.setdefault(bukti["template_id"], bukti)

    hasil: list[dict[str, Any]] = []
    for template_id, bukti in terbaru.items():
        kode = bukti["kode"]
        if bukti["benar"] or kode == "T":
            continue
        hasil.append(
            {
                "template_id": template_id,
                "topik": pemilik_template(template_id),
                "kode": kode,
                "alasan": bukti["alasan"],
                "kali_salah": jumlah_salah[template_id],
                "sesi_terakhir": int(bukti["sesi_id"]),
                "tanggal_terakhir": bukti["tanggal"],
                "direkomendasikan": kode == "K",
            }
        )
    return hasil


def sasaran_remedial_anak(
    kon: sqlite3.Connection, siswa_id: int
) -> list[dict[str, Any]]:
    """Kandidat remedial aktif dari seluruh hasil yang sudah direview guru."""
    return _susun_sasaran(_baris_sasaran_remedial(kon, siswa_id))


def sasaran_remedial_sesi(
    kon: sqlite3.Connection, siswa_id: int, sesi_id: int
) -> list[dict[str, Any]]:
    """Kandidat remedial dari satu sesi sah milik anak tersebut."""
    sumber = kon.execute(
        """SELECT 1 FROM sesi
           WHERE id = ? AND siswa_id = ?
             AND selesai IS NOT NULL AND direview IS NOT NULL""",
        (sesi_id, siswa_id),
    ).fetchone()
    if sumber is None:
        return []
    return _susun_sasaran(_baris_sasaran_remedial(kon, siswa_id, sesi_id))


def sasaran_remedial(
    kon: sqlite3.Connection, siswa_id: int, batas: int = 6
) -> list[str]:
    """Template yang perlu DILATIH ULANG oleh anak ini (poin a Filia).

    Sumbernya data nyata, bukan tebakan: template yang jawabannya pernah
    salah (diagnosis.benar = 0) untuk anak ini. Diurut dari yang paling
    sering salah, lalu yang paling baru — supaya sesi remedial menyerang
    yang paling membebani lebih dulu.

    Yang TIDAK dihitung:
      - soal yang belum dijawab (tidak ada bukti anak tidak bisa);
      - kode 'T' (belum pernah diajarkan) — itu peta urutan belajar, dan
        melatih ulang materi yang belum diajarkan bukan remedial, itu
        menjatuhkan anak dua kali;
      - template yang SELALU benar.

    `batas` menjaga sesi remedial tetap masuk akal (bawaan 6 konsep).
    Kembalian [] berarti tidak ada dasar untuk remedial — pemanggil WAJIB
    menghormati itu dan tidak mengarang latihan.
    """
    baris = kon.execute(
        """SELECT s.template_id            AS template_id,
                  COUNT(*)                 AS kali_salah,
                  MAX(se.tanggal)          AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ? AND se.format_jawaban='isian'
             AND se.selesai IS NOT NULL
             AND d.benar = 0
             AND IFNULL(d.kode_final, IFNULL(d.kode_usulan, '')) <> 'T'
           GROUP BY s.template_id
           ORDER BY kali_salah DESC, terakhir DESC""",
        (siswa_id,),
    ).fetchall()
    return [b["template_id"] for b in baris[:batas]]


def _level_terdekat(level: str, tersedia) -> str:
    """Level didukung yang PALING DEKAT dengan level anak.

    Dipakai remedial: paket sasaran bisa saja tidak punya level anak
    (logika melompati P4). Memilih yang terdekat — bukan yang pertama —
    menjaga soal tetap sepadan: anak P4 dapat P3, bukan P6.
    Seri (mis. P4 antara P3 dan P5) diputus ke bawah: lebih baik sedikit
    terlalu mudah daripada terlalu sulit untuk latihan ulang.
    """
    from templates import LEVEL

    urut = [lv for lv in LEVEL if lv in tersedia]
    if not urut:
        return level
    if level not in LEVEL:
        return urut[0]
    posisi = LEVEL.index(level)
    return min(urut, key=lambda lv: (abs(LEVEL.index(lv) - posisi),
                                     LEVEL.index(lv)))


def buat_sesi_remedial(
    kon: sqlite3.Connection,
    siswa_id: int,
    seed: int | None = None,
    level: str = LEVEL_BAWAAN,
    topik: str | None = None,
    jumlah_soal: int = 10,
    template_ids: list[str] | None = None,
    sumber_sesi_id: int | None = None,
    *,
    sasaran_anak,
    sasaran_sesi,
    pilih_level,
    buat_dari_urutan,
    random_module,
) -> int | None:
    """Sesi latihan ulang berisi HANYA konsep yang pernah dijawab salah.

    Kunci desainnya: template-nya sama, SOALNYA BARU. Seed berbeda berarti
    angka/objeknya berganti — yang dilatih konsepnya, bukan hafalan jawaban
    lembar lama. Ini juga yang membuat perbandingan "sudah membaik atau
    belum" bermakna.

    `seed=None` berarti pilih seed yang BELUM pernah dipakai anak ini
    (pola sama dengan buat_sesi_seed_baru) — pemanggil web tidak perlu
    mengurus keacakan sendiri. Seed eksplisit dipakai test determinisme.

    `topik=None` (bawaan) berarti paket DITURUNKAN dari sasaran lewat
    `topics.paket_untuk_template`. Ini bukan kenyamanan, ini koreksi bug:
    sasaran remedial datang dari seluruh riwayat anak, jadi template-nya
    bisa milik topik mana pun. Versi lama memaksa paket bawaan
    (pola-bilangan) dan melempar KeyError untuk anak yang salah di topik
    lain — 502 di produksi, 3 Sep 2026.

    None kalau tidak ada sasaran (anak belum punya kesalahan tercatat) —
    lebih jujur daripada membuat sesi acak dan menyebutnya remedial.
    """
    if not isinstance(jumlah_soal, int) or not 1 <= jumlah_soal <= 50:
        raise ValueError("jumlah_soal harus antara 1 dan 50")

    if sumber_sesi_id is None:
        kandidat = sasaran_anak(kon, siswa_id)
        kandidat_ids = [b["template_id"] for b in kandidat]
    else:
        sumber = kon.execute(
            """SELECT 1 FROM sesi
               WHERE id = ? AND siswa_id = ?
                 AND selesai IS NOT NULL AND direview IS NOT NULL""",
            (sumber_sesi_id, siswa_id),
        ).fetchone()
        if sumber is None:
            raise ValueError("sumber sesi remedial tidak sah")
        kandidat_ids = [
            b["template_id"]
            for b in sasaran_sesi(kon, siswa_id, sumber_sesi_id)
        ]

    if template_ids is None:
        sasaran = kandidat_ids[:6]
    else:
        if not template_ids:
            raise ValueError("pilihan template kosong")
        if len(template_ids) != len(set(template_ids)):
            raise ValueError("pilihan template duplikat")
        if len(template_ids) > 3:
            raise ValueError("pilihan template maksimal 3")
        if jumlah_soal < len(template_ids):
            raise ValueError("jumlah soal harus memuat setiap fokus")
        bukan_kandidat = set(template_ids) - set(kandidat_ids)
        if bukan_kandidat:
            raise ValueError("template bukan kandidat remedial")
        sasaran = list(template_ids)

    if not sasaran:
        return None
    if topik is None:
        from topics import paket_untuk_template

        paket = paket_untuk_template(sasaran)
    else:
        paket = topik
    # `siswa.tingkat` adalah teks bebas dan paket sasaran belum tentu
    # mendukung level itu (mis. anak P4 yang salah di topik logika = P3/P5/P6).
    # Guru memilih topik lewat dropdown yang sudah difilter per level, jadi
    # ValueError generator masih benar DI SANA; di sini levelnya bukan
    # pilihan siapa pun, jadi dinormalkan ke level terdekat yang didukung
    # daripada mematikan fitur untuk anak yang levelnya "salah".
    komposisi = getattr(paket, "komposisi", None)
    if komposisi and level not in komposisi:
        level = pilih_level(level, komposisi)
    if seed is None:
        dipakai = {
            r["seed"]
            for r in kon.execute(
                "SELECT seed FROM sesi WHERE siswa_id = ?", (siswa_id,)
            ).fetchall()
        }
        for _ in range(500):
            calon = random_module.randint(1, 9_999_999)
            if calon not in dipakai:
                seed = calon
                break
        else:
            raise RuntimeError("gagal menemukan seed baru")
    # Ulangi sasaran round-robin sampai memenuhi jumlah_soal: tiap konsep
    # dapat porsi seimbang, dan urutannya tetap diacak per lembar oleh
    # generator (_acak_urutan) supaya posisi soal tidak menghafal.
    urutan: list[str] = []
    while len(urutan) < jumlah_soal:
        urutan.extend(sasaran)
    return buat_dari_urutan(
        kon, siswa_id, seed,
        urutan=tuple(urutan[:jumlah_soal]),
        level=level, topik=paket,
        jenis="remedial", sumber_sesi_id=sumber_sesi_id,
    )
