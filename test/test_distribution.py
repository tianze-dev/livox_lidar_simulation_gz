"""Technical readiness must not silently imply public redistribution approval."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_check', ROOT/'scripts/release_check.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_pending_distribution_blocks_release_not_technical_check():
    technical, code = release.check()
    assert code == 0 and technical['technical_passed']
    assert not technical['release_ready']
    formal, code = release.check(release=True)
    assert code != 0 and len(formal['distribution_blockers']) == 2


def test_approval_requires_evidence(tmp_path):
    (tmp_path/'dependencies').mkdir()
    (tmp_path/'notice').write_text('test notice')
    data = json.loads((ROOT/'dependencies/distribution.json').read_text())
    for item in data['reviews']:
        item.update(status='approved', evidence='', notice='notice')
    path = tmp_path/'dependencies/distribution.json'
    path.write_text(json.dumps(data))
    assert len(release.distribution_blockers(tmp_path)) == 2
    for item in data['reviews']:
        item['evidence'] = 'test review reference'
    path.write_text(json.dumps(data))
    assert release.distribution_blockers(tmp_path) == []


def test_missing_metadata_is_structured_error(tmp_path):
    result, code = release.check(root=tmp_path)
    assert code != 0 and result['errors'] and not result['release_ready']
