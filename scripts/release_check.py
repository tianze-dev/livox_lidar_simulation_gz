#!/usr/bin/env python3
"""Check technical readiness; --release additionally enforces recorded distribution reviews."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def distribution_blockers(root):
    data = json.loads((root/'dependencies/distribution.json').read_text())
    if data.get('schema_version') != 1:
        raise ValueError('Invalid distribution review schema')
    reviews = data.get('reviews', [])
    if {item.get('asset') for item in reviews} != {'avia_cad', 'rgl_runtime'} or len(reviews) != 2:
        raise ValueError('Missing or duplicate distribution reviews')
    blockers = []
    for item in reviews:
        if not (root/item['notice']).is_file():
            raise ValueError('Missing distribution notice')
        if item['status'] != 'approved' or not item.get('evidence', '').strip():
            blockers.append(item['asset'] + ': ' + item['reason'])
    return blockers


def check(root=ROOT, install_prefix=None, release=False):
    errors = []
    blockers = []
    try:
        package = ET.parse(root/'package.xml').getroot()
        if package.findtext('license') != 'Apache-2.0':
            errors.append('Expected Apache-2.0 for original project code')
        maintainer = package.find('maintainer')
        if (maintainer is None or not (maintainer.text or '').strip()
                or '@' not in maintainer.get('email', '')
                or 'example.com' in maintainer.get('email', '')):
            errors.append('A maintainer name and non-placeholder email are required')
        required = ('README.md', 'README.en.md', 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md',
                    'docs/SUPPORT.md', 'docs/INTEGRATION.md', 'docs/TROUBLESHOOTING.md',
                    'CONTRIBUTING.md', '.github/workflows/check.yml')
        for name in required:
            if not (root/name).is_file():
                errors.append(f'Missing {name}')
        for model in ('mid360', 'avia'):
            report = json.loads((root/f'meshes/{model}/geometry_report.json').read_text())
            for extension, expected in [('dae', report['output_sha256']), ('glb', report['glb']['sha256'])]:
                path = root/f'meshes/{model}/{model}.{extension}'
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    errors.append(f'{model} {extension} asset hash mismatch')
        for folder in ('launch', 'cmake', 'livox_lidar_simulation_gz', 'urdf'):
            for path in (root/folder).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    if re.search(r'/home/[^/\s]+/|/Users/[^/\s]+/|/tmp/|[A-Za-z]:[\\/]Users[\\/]', path.read_text()):
                        errors.append(f'Non-portable path in {path.relative_to(root)}')
        for name in ('build.sh', 'check.sh', 'run.sh', 'check_environment.sh'):
            if subprocess.run(['bash', '-n', str(root/'scripts'/name)]).returncode:
                errors.append(f'Shell syntax: {name}')
        blockers = distribution_blockers(root)
        if install_prefix:
            prefix = Path(install_prefix)
            share = prefix/'share/livox_lidar_simulation_gz'
            # Compare every source runtime resource against the installed copy.
            for folder in ('launch', 'config', 'urdf', 'worlds', 'rviz', 'meshes', 'docs'):
                for source in (root/folder).rglob('*'):
                    if not source.is_file() or '__pycache__' in source.parts:
                        continue
                    target = share/source.relative_to(root)
                    if not target.is_file() or target.read_bytes() != source.read_bytes():
                        errors.append(f'Missing or stale installed resource: {source.relative_to(root)}')
            for name in ('lock.json', 'distribution.json'):
                if (share/'dependencies'/name).read_bytes() != (root/'dependencies'/name).read_bytes():
                    errors.append(f'Installed dependency metadata differs: {name}')
            for name in ('libRGLServerPluginManager.so', 'libRGLServerPluginInstance.so', 'libRobotecGPULidar.so'):
                if not (prefix/'lib/livox_lidar_simulation_gz/rgl'/name).is_file():
                    errors.append(f'Missing installed library: {name}')
            lock = json.loads((root/'dependencies/lock.json').read_text())
            for artifact in lock['artifacts']:
                if artifact['path'].startswith('patterns/'):
                    target = share/artifact['path']
                    if hashlib.sha256(target.read_bytes()).hexdigest() != artifact['sha256']:
                        errors.append('Installed pattern hash mismatch: ' + artifact['path'])
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        errors.append(f'Invalid or missing metadata/resource: {error}')
    result = dict(technical_passed=not errors, release_ready=not errors and not blockers,
                  errors=errors, distribution_blockers=blockers,
                  scope='metadata/resources and recorded reviews; runtime validation remains separate')
    return result, int(bool(errors) or (release and bool(blockers)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--install-prefix', type=Path,
                        help='Package prefix returned by ros2 pkg prefix (not the workspace root)')
    args = parser.parse_args()
    result, code = check(install_prefix=args.install_prefix, release=args.release)
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
