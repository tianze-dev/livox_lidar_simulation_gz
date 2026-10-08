#!/usr/bin/env python3
"""Fetch only locked public artifacts; never consult another workspace."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Artifact escapes cache directory: {relative}')
    return path


def atomic_copy(stream, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            shutil.copyfileobj(stream, output)
        actual = digest(temporary)
        if actual != expected:
            raise ValueError(f'SHA256 mismatch for {target.name}: {actual}')
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare(cache, lock, offline=False):
    for artifact in lock['artifacts']:
        target = safe_path(cache, artifact['path'])
        if target.is_file() and digest(target) == artifact['sha256']:
            print(f'Verified cache: {artifact["path"]}')
            continue
        if offline:
            raise RuntimeError(f'Missing or corrupt offline artifact: {artifact["path"]}')
        print(f'Downloading: {artifact["url"]}', flush=True)
        request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'livox-gz/0.1'})
        with urllib.request.urlopen(request, timeout=60) as response:
            atomic_copy(response, target, artifact['sha256'])
    library = lock['library']
    target = safe_path(cache, library['path'])
    if not target.is_file() or digest(target) != library['sha256']:
        with zipfile.ZipFile(safe_path(cache, library['archive'])) as archive:
            members = [name for name in archive.namelist()
                       if Path(name).name == library['member_basename']]
            if len(members) != 1:
                raise ValueError('Archive must contain exactly one expected RGL library')
            with archive.open(members[0]) as stream:
                atomic_copy(stream, target, library['sha256'])
    print(f'Verified runtime: {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=ROOT / '.deps' / 'rgl')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        parser.error('The locked RGL runtime supports Linux x86_64 only')
    lock = json.loads((ROOT / 'dependencies' / 'lock.json').read_text())
    try:
        prepare(args.cache_dir.resolve(), lock, args.offline)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, urllib.error.URLError) as error:
        print(f'Dependency preparation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
