#!/usr/bin/env python3
"""Check package metadata, runtime assets and portable paths."""
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
        errors.append('Expected Apache-2.0 for original project code')
    maintainer = package.find('maintainer')
    if (maintainer is None or not (maintainer.text or '').strip()
            or '@' not in maintainer.get('email', '')
            or 'example.com' in maintainer.get('email', '')
            or 'pending' in (maintainer.text or '').lower()):
        errors.append('A maintainer name and non-placeholder email are required')
    for required in ('README.md', 'README.en.md', 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md',
                     'docs/SUPPORT.md', 'docs/INTEGRATION.md', 'docs/TROUBLESHOOTING.md',
                     'CONTRIBUTING.md', '.github/workflows/check.yml'):
        if not (ROOT/required).is_file():
            errors.append(f'Missing {required}')
    for model in ('mid360', 'avia'):
        report = json.loads((ROOT/f'meshes/{model}/geometry_report.json').read_text())
        digest = hashlib.sha256((ROOT/f'meshes/{model}/{model}.dae').read_bytes()).hexdigest()
        if digest != report['output_sha256']:
            errors.append(f'{model} asset hash mismatch')
    for folder in ('launch', 'cmake', 'livox_lidar_simulation_gz', 'urdf'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                text = path.read_text()
                if re.search(r'/home/[^/\s]+/|/Users/[^/\s]+/|/tmp/|[A-Za-z]:[\\/]Users[\\/]', text):
                    errors.append(f'Non-portable path in {path.relative_to(ROOT)}')
    for name in ('build.sh', 'check.sh', 'run.sh', 'check_environment.sh'):
        if subprocess.run(['bash', '-n', str(ROOT/'scripts'/name)]).returncode:
            errors.append(f'Shell syntax: {name}')
    print(json.dumps({'passed': not errors, 'errors': errors,
                      'warnings': ['Avia CAD-derived assets: public redistribution terms still need confirmation',
                                   'Precompiled runtime redistribution review is not complete; see THIRD_PARTY_NOTICES.md'],
                      'scope': 'metadata/resources only; not a GPU runtime test or redistribution clearance'}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
