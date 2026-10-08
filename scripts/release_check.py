#!/usr/bin/env python3
"""Check first-delivery metadata/resources without publishing anything."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    package = ET.parse(ROOT/'package.xml').getroot()
    if package.findtext('license') != 'Apache-2.0':
        errors.append('Project license must be confirmed')
    maintainer = package.find('maintainer')
    if 'example.com' in maintainer.get('email', '') or 'pending' in (maintainer.text or '').lower():
        errors.append('Maintainer identity must be confirmed')
    for required in ('README.md', 'README.en.md', 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md',
                     'docs/SUPPORT.md', 'docs/RELEASE_REVIEW.md', '.github/workflows/check.yml'):
        if not (ROOT/required).is_file():
            errors.append(f'Missing {required}')
    report = json.loads((ROOT/'meshes/mid360/geometry_report.json').read_text())
    digest = hashlib.sha256((ROOT/'meshes/mid360/mid360.dae').read_bytes()).hexdigest()
    if digest != report['output_sha256']:
        errors.append('MID-360 asset hash mismatch')
    for folder in ('launch', 'cmake', 'livox_lidar_simulation_gz', 'urdf'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                text = path.read_text()
                if re.search(r'/home/[^/]+/|sentry_simulation|scut-uav', text):
                    errors.append(f'External workspace reference in {path.relative_to(ROOT)}')
    for name in ('build.sh', 'check.sh', 'run.sh', 'check_environment.sh'):
        if subprocess.run(['bash', '-n', str(ROOT/'scripts'/name)]).returncode:
            errors.append(f'Shell syntax: {name}')
    print(json.dumps({'passed': not errors, 'errors': errors,
                      'warnings': ['Maintainer currently follows Git identity; confirm before public publication'],
                      'scope': 'metadata/resources only; consult docs/RELEASE_REVIEW.md for runtime evidence'}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
