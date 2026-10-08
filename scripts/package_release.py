#!/usr/bin/env python3
"""Create a source-only review archive from a clean Git commit; never publish."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT/'scripts/release_check.py')], check=True, cwd=ROOT)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise SystemExit('Refusing to archive a dirty worktree; commit reviewed source first')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stem = 'livox_lidar_simulation_gz-0.1.0-' + commit[:8]
    target = directory/(stem+'.tar.gz')
    if target.exists():
        raise SystemExit(f'Refusing to overwrite {target}')
    subprocess.run(['git', 'archive', '--format=tar.gz', '--prefix='+stem+'/',
                    '--output='+str(target), commit], check=True, cwd=ROOT)
    with target.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = dict(schema_version=1, version='0.1.0', status='review candidate; not remotely published',
                    commit=commit, archive=target.name, sha256=sha,
                    contents='Git-tracked source/assets/docs only; no caches, build/install, downloaded runtime libraries or logs')
    (directory/(stem+'.manifest.json')).write_text(json.dumps(manifest, indent=2)+'\n')
    (directory/(stem+'.sha256')).write_text(sha+'  '+target.name+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
