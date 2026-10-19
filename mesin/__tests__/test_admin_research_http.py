"""Alur HTTP aplikasi interviewer memakai server dan data sintetis."""
from datetime import datetime
import re
import urllib.parse

import pytest

import auth
import research_store
from test_admin_http_c import (
    SANDI_ADMIN, SANDI_ORANG_TUA, _hidden, _login, _minta, server,
)


def _form_buat(server, token, *, kode="R02"):
    halaman = _minta(server, "/admin/riset", cookie=token)[1]
    body = re.search(r'<form method="post" action="/admin/riset/buat">(.*?)</form>', halaman, re.S).group(1)
    return {
        "csrf": _hidden(body, "csrf"),
        "tinjauan": _hidden(body, "tinjauan"),
        "kode_responden": kode,
        "sumber": "internal",
        "diwawancarai": "2026-10-14T10:30",
        "consent_wawancara": "1",
    }


def _buat(server, token, *, kode="R02"):
    respons = _minta(server, "/admin/riset/buat", cookie=token, data=_form_buat(server, token, kode=kode))
    assert respons[0] == 303
    lokasi = respons[2]["Location"]
    return urllib.parse.parse_qs(urllib.parse.urlsplit(lokasi).query)["id"][0]


def _form_jawaban(server, token, identitas, q="Q1"):
    body = _minta(server, "/admin/riset/isi?id=%s&q=%s" % (identitas, q), cookie=token)[1]
    return {
        "csrf": _hidden(body, "csrf"), "tinjauan": _hidden(body, "tinjauan"),
        "id": identitas, "q": q,
        "revisi_wawancara": _hidden(body, "revisi_wawancara"),
        "revisi_jawaban": _hidden(body, "revisi_jawaban"),
        "status_jawaban": "dijawab", "jawaban_responden": "Jawaban sintetis",
        "kutipan_responden": "Kutipan sintetis", "kutipan_terpilih": "1",
        "catatan_interviewer": "Catatan interviewer sintetis",
        "kode_utama": "konteks_osn" if q == "Q1" else "",
        "status_klarifikasi": "tidak_perlu", "lanjut": "ringkasan",
    }


def test_dashboard_privat_hanya_cookie_admin_dan_get_hilang_tidak_bootstrap(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, body, headers = _minta(server, "/admin/riset", cookie=token)
    assert kode == 200 and "Riset konsumen" in body and "Mulai wawancara" in body
    assert "Jangan masukkan nama orang tua" in body
    assert headers["Cache-Control"] == "no-store"
    anonim = _minta(server, "/admin/riset")[:2]
    guru = _minta(server, "/admin/riset", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    admin_basic = _minta(server, "/admin/riset", auth_basic=("Admin-C", SANDI_ADMIN))[:2]
    assert admin_basic[0] == 404, "cookie admin hidup wajib untuk membaca data riset"
    assert anonim == guru == admin_basic and anonim[0] == 404
    research_store.BAWAAN.unlink()
    kode, _, _ = _minta(server, "/admin/riset", cookie=token)
    assert kode == 503 and not research_store.BAWAAN.exists()


def test_buat_wawancara_memerlukan_consent_csrf_dan_tidak_duplikat(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    form = _form_buat(server, token)
    awal = research_store.BAWAAN.read_bytes()
    assert _minta(server, "/admin/riset/buat", cookie=token, data={**form, "csrf": "rusak"})[0] == 403
    assert _minta(server, "/admin/riset/buat", cookie=token, data={k:v for k,v in form.items() if k != "consent_wawancara"})[0] == 400
    assert research_store.BAWAAN.read_bytes() == awal
    identitas = _buat(server, token)
    detail = research_store.detail_wawancara(research_store.BAWAAN, identitas)
    assert detail["kode_responden"] == "R02" and detail["status"] == "draf"
    form_dua = _form_buat(server, token, kode="R02")
    assert _minta(server, "/admin/riset/buat", cookie=token, data=form_dua)[0] == 503
    assert research_store.daftar_wawancara().total == 1


def test_form_hybrid_menyimpan_lapis_terpisah_dan_tanpa_jawaban_ideal(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    identitas = _buat(server, token)
    form = _form_jawaban(server, token, identitas)
    kode, _, header = _minta(server, "/admin/riset/jawaban", cookie=token, data=form)
    assert kode == 303 and header["Location"].endswith("id=" + identitas)
    jawaban = research_store.detail_wawancara(research_store.BAWAAN, identitas)["jawaban"]["Q1"]
    assert jawaban["jawaban_responden"] == "Jawaban sintetis"
    assert jawaban["catatan_interviewer"] == "Catatan interviewer sintetis"
    assert jawaban["kode_utama"] == "konteks_osn"
    body = _minta(server, "/admin/riset/wawancara?id=" + identitas, cookie=token)[1]
    assert "1/9" not in body  # ringkasan topik, bukan skor kualitas responden
    assert "Belum diberi status" in body


def test_nonadmin_post_identik_dan_tidak_menulis(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    identitas = _buat(server, token)
    form = _form_jawaban(server, token, identitas)
    sebelum = research_store.BAWAAN.read_bytes()
    anonim = _minta(server, "/admin/riset/jawaban", data=form)[:2]
    guru = _minta(server, "/admin/riset/jawaban", auth_basic=("Ortu-C", SANDI_ORANG_TUA), data=form)[:2]
    admin_basic = _minta(server, "/admin/riset/jawaban", auth_basic=("Admin-C", SANDI_ADMIN), data=form)[:2]
    assert anonim == guru == admin_basic and anonim[0] == 404
    assert research_store.BAWAAN.read_bytes() == sebelum


def test_finalisasi_matriks_dan_ekspor_hanya_setelah_semua_status(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    identitas = _buat(server, token)
    for i in range(1, 10):
        q = "Q%d" % i
        body = _minta(server, "/admin/riset/isi?id=%s&q=%s" % (identitas,q), cookie=token)[1]
        data = {
            "csrf": _hidden(body,"csrf"), "tinjauan": _hidden(body,"tinjauan"),
            "id":identitas,"q":q,"revisi_wawancara":_hidden(body,"revisi_wawancara"),
            "revisi_jawaban":_hidden(body,"revisi_jawaban"),
            "status_jawaban":"tidak_dibahas","jawaban_responden":"","kutipan_responden":"",
            "catatan_interviewer":"","status_klarifikasi":"tidak_perlu","lanjut":"ringkasan",
        }
        assert _minta(server,"/admin/riset/jawaban",cookie=token,data=data)[0]==303
    body = _minta(server,"/admin/riset/wawancara?id="+identitas,cookie=token)[1]
    form={"csrf":_hidden(body,"csrf"),"tinjauan":_hidden(body,"tinjauan"),"id":identitas}
    assert _minta(server,"/admin/riset/finalisasi",cookie=token,data=form)[0]==303
    assert research_store.detail_wawancara(research_store.BAWAAN,identitas)["status"]=="final"
    matriks=_minta(server,"/admin/riset/matriks",cookie=token)
    assert matriks[0]==200 and "Studi eksploratif" in matriks[1] and "R02" in matriks[1]
    dash=_minta(server,"/admin/riset",cookie=token)[1]
    forms=re.findall(r'<form method="post" action="/admin/riset/ekspor">(.*?)</form>',dash,re.S)
    assert len(forms)==2
    csv_form={"csrf":_hidden(forms[0],"csrf"),"tinjauan":_hidden(forms[0],"tinjauan"),"format":"csv"}
    kode,isi,headers=_minta(server,"/admin/riset/ekspor",cookie=token,data=csv_form)
    assert kode==200 and "R02" in isi and headers["Content-Disposition"]=='attachment; filename="riset-konsumen.csv"'
    assert auth.cari_akun("Admin-C")["id_akun"] not in isi


def test_tarik_consent_perlu_reauth_dan_menghapus_teks(server):
    token=_login(server,"Admin-C",SANDI_ADMIN)
    identitas=_buat(server,token)
    assert _minta(server,"/admin/riset/jawaban",cookie=token,data=_form_jawaban(server,token,identitas))[0]==303
    body=_minta(server,"/admin/riset/wawancara?id="+identitas,cookie=token)[1]
    form_tarikh={
        "csrf":_hidden(body,"csrf"),
        "tinjauan":re.findall(r'<form method="post" action="/admin/riset/tarik".*?name="tinjauan" value="([^"]+)',body,re.S)[0],
        "id":identitas,"reauth":"salah",
    }
    sebelum=research_store.detail_wawancara(research_store.BAWAAN,identitas)
    assert _minta(server,"/admin/riset/tarik",cookie=token,data=form_tarikh)[0]==403
    assert research_store.detail_wawancara(research_store.BAWAAN,identitas)["jawaban"]==sebelum["jawaban"]
    form_tarikh["reauth"]=SANDI_ADMIN
    assert _minta(server,"/admin/riset/tarik",cookie=token,data=form_tarikh)[0]==303
    akhir=research_store.detail_wawancara(research_store.BAWAAN,identitas)
    assert akhir["status"]=="ditarik" and akhir["jawaban"]=={}
