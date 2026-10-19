"""Ikon garis menu panel pengelola; SVG inline tanpa aset jaringan."""

_ATRIBUT = ('width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"')

_BENTUK = {
    "ringkasan": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    "keluarga": ('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/>'
                 '<path d="M16 4.7a3.5 3.5 0 010 6.6"/><path d="M18 14.3c2 .7 3.5 2.6 3.5 5.7"/>'),
    "siswa": '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5"/>',
    "pendaftaran": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9z"/><path d="M9 12h6M9 16h4"/>',
    "langganan": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/>',
    "kpi": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>',
    "riset": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "operasional": '<rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
    "ai": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    "riwayat": '<path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.5L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>',
}


def ikon(kode: str) -> str:
    """SVG dekoratif untuk section; kode tak dikenal tidak menampilkan apa pun."""
    bentuk = _BENTUK.get(kode)
    return '<svg %s>%s</svg>' % (_ATRIBUT, bentuk) if bentuk else ""
