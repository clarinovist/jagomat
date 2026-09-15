"""Kontrak CI rutin v4: build teruji, eligibility eksplisit dan policy VPS."""
from pathlib import Path
import re
import itertools
import pytest

AKAR = Path(__file__).resolve().parents[2]
WORKFLOW = AKAR / '.github/workflows/deploy.yml'
RECOVERY_SHA = '33e241c18024190f41ebca1986e35af26c0397fd'


def _job(teks, nama):
    cocok = re.search(r'^  '+nama+r':\n(.*?)(?=^  [a-z_]+:\n|\Z)', teks, re.M|re.S)
    assert cocok, nama
    return cocok.group(1)


def test_pasang_tertahan_sampai_deployer_dan_policy_rutin_siap():
    teks=WORKFLOW.read_text()
    pasang=_job(teks,'pasang')
    assert "if: ${{ vars.OSN_DEPLOY_RUTIN_SIAP == '1' && github.ref == 'refs/heads/main' }}" in pasang
    assert 'needs: bangun' in pasang
    assert 'deploy-rutin-v1 ' in pasang
    assert 'deploy-v2 ' not in pasang
    assert 'rollout-approval.json' not in pasang and 'routine-policy.json' not in pasang
    assert '${{ needs.bangun.outputs.digest }}' in pasang
    assert '${{ needs.bangun.outputs.recovery_digest }}' in pasang
    assert 'cancel-in-progress: false' in teks


def test_build_candidate_dan_recovery_pakai_digest_yang_sama_untuk_verifikasi():
    teks=WORKFLOW.read_text()
    uji=_job(teks,'uji');recovery=_job(teks,'uji_recovery');bangun=_job(teks,'bangun')
    assert 'needs: [uji, uji_recovery]' in bangun
    # Checkout yang diuji/dibangun dan revision manifest wajib snapshot sama.
    assert re.findall(r'^          ref: ([0-9a-f]{40})$', teks, re.M) == [RECOVERY_SHA] * 2
    assert re.findall(r'^  RECOVERY_SHA: ([0-9a-f]{40})$', teks, re.M) == [RECOVERY_SHA]
    assert RECOVERY_SHA in recovery and RECOVERY_SHA in bangun
    assert 'recovery_digest: ${{ steps.recovery.outputs.digest }}' in bangun
    assert 'digest: ${{ steps.dorong.outputs.digest }}' in bangun
    assert 'scripts/verify_release_image.py' in bangun
    assert '${{ steps.dorong.outputs.digest }}' in bangun
    assert '${{ steps.recovery.outputs.digest }}' in bangun
    assert '--revision "$GITHUB_SHA"' in bangun
    assert '--revision "$RECOVERY_SHA"' in bangun
    kandidat=_job(teks,'uji_kandidat')
    assert 'needs: uji_kandidat' in uji
    assert 'python scripts/verify_pytest_shards.py' in uji
    assert 'python scripts/pytest_shard.py' in kandidat
    assert '--rootdir . mesin/__tests__/ -q -W error' in kandidat
    assert 'VPS_DEPLOY_KEY' not in kandidat
    assert 'working-directory: recovery' in recovery
    assert '          path: recovery\n' in recovery
    assert 'python ../scripts/pytest_shard.py' in recovery
    assert '--shard "${{ matrix.shard }}" --total 4 --' in recovery
    assert 'Canary: import recovery terisolasi, schema v4' in recovery
    assert 'VPS_DEPLOY_KEY' not in uji+recovery+bangun


def test_persiapan_tidak_memutakhirkan_latest_atau_memakai_tag_berubah():
    teks=WORKFLOW.read_text()
    bangun=_job(teks,'bangun')
    assert 'value=latest' not in bangun
    assert ':latest' not in bangun
    assert 'recovery-${{ env.RECOVERY_SHA }}' in bangun
    assert 'sha-${{ github.sha }}' in bangun
    assert 'publish-prod' not in bangun
    assert '--network' not in _job(teks,'pasang')  # sandbox image ada di probe, bukan mount produksi CI


@pytest.mark.parametrize('flag,ref', tuple(itertools.product(
    ('', '0', 'false', '1 ', '1'), ('refs/heads/main', 'refs/heads/persiapan')
)))
def test_gate_job_hanya_menerima_izin_exact_dan_main(flag, ref):
    pasang=_job(WORKFLOW.read_text(),'pasang')
    expr=re.search(r'    if: \$\{\{ (.+) \}\}',pasang).group(1)
    # Evaluasi subset ekspresi yang sengaja sempit, bukan parser YAML/deploy baru.
    assert expr == "vars.OSN_DEPLOY_RUTIN_SIAP == '1' && github.ref == 'refs/heads/main'"
    bagian=expr.split(' && ')
    nilai={'vars.OSN_DEPLOY_RUTIN_SIAP':flag,'github.ref':ref}
    lolos=all(nilai[k.strip()]==v.strip().strip("'") for k,v in (b.split(' == ') for b in bagian))
    assert lolos == (flag=='1' and ref=='refs/heads/main')


def test_dependencies_gagal_tidak_dibypass_ke_build_atau_deploy():
    teks=WORKFLOW.read_text()
    for nama in ('uji_kandidat','uji','uji_recovery','bangun','pasang'):
        job=_job(teks,nama)
        assert 'continue-on-error:' not in job
        assert 'always()' not in job and '|| true' not in job
    assert teks.index('Verifikasi image berdasarkan digest') < teks.index('  pasang:')
    assert 'if:' not in _job(teks,'bangun')  # Tak ada bypass verifikasi image.
    assert 'working-directory: recovery' in _job(teks,'uji_recovery')
    assert 'shard: [1, 2, 3, 4]' in _job(teks,'uji_recovery')
    assert 'needs: [uji, uji_recovery]' in _job(teks,'bangun')


def test_healthcheck_publik_tiga_permukaan_tetap_diperiksa():
    pasang=_job(WORKFLOW.read_text(),'pasang')
    assert 'run: python scripts/smoke_public.py' in pasang
    assert 'uses: actions/checkout@v7' in pasang
    assert 'uses: actions/setup-python@v7' in pasang
    assert pasang.index('Deploy pasangan digest') < pasang.index('scripts/smoke_public.py')
