"""Build or verify an offline development bundle; never install into HA."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.runtime_install_plan import inspect_wheel


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe bundle path')


def read_source(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Bundle inputs must remain inside the source tree')
    data = path.read_bytes()
    return data if path.suffix == '.png' else data.replace(b'\r\n', b'\n')


def build_bundle(root, wheel_dir, cache, output):
    root, wheel_dir, cache, output = map(Path, (root, wheel_dir, cache, output))
    runtime = json.loads((root / 'packaging/runtime-wheels.json').read_text(encoding='utf-8'))
    item, = runtime['wheels']
    safe_name(item['filename'])
    wheel = wheel_dir / item['filename']
    inspected = inspect_wheel(wheel, item['sha256'], {item['tag']})
    lock = json.loads((root / 'packaging/inputs.lock.json').read_text(encoding='utf-8'))
    pip, = [entry for entry in lock['wheels'] if entry['filename'].startswith('pip-')]
    safe_name(pip['filename'])
    pip_data = (cache / pip['filename']).read_bytes()
    if sha256(pip_data) != pip['sha256']:
        raise ValueError('Offline pip checksum mismatch')
    # An explicit source allowlist excludes diagnostics, captures and home inventory.
    names = {
        'README.md', 'docs/OFFLINE_CANDIDATE.md', 'docs/KNOWN_ISSUES.md',
        'docs/PROTOCOL.md', 'examples/inventory.example.json',
        'packaging/runtime-wheels.json', 'packaging/inputs.lock.json',
        'tools/__init__.py', 'tools/runtime_install_plan.py', 'tools/verify_native_runtime.py',
        'tools/verify_ha_deps.py', 'tools/build_candidate.py',
        'custom_components/homycloud_local/manifest.json',
        'custom_components/homycloud_local/strings.json',
        'custom_components/homycloud_local/translations/zh-Hans.json',
        'custom_components/homycloud_local/protocol/schemas.json',
        'custom_components/homycloud_local/brand/icon.png',
    }
    component = root / 'custom_components/homycloud_local'
    for folder in (component, component / 'protocol'):
        names.update(path.relative_to(root).as_posix() for path in folder.glob('*.py'))
    files = {name: read_source(root, name) for name in sorted(names)}
    files['wheels/' + item['filename']] = wheel.read_bytes()
    files['bootstrap/' + pip['filename']] = pip_data
    manifest = {
        'format': 1, 'status': 'development_candidate_not_published',
        'integration_version': json.loads(files['custom_components/homycloud_local/manifest.json'])['version'],
        'runtime': inspected, 'installation_performed': False,
        'files': {name: {'sha256': sha256(data), 'size': len(data)} for name, data in files.items()},
    }
    files['bundle-manifest.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return verify_bundle(output)


def verify_bundle(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate bundle entries')
        for name in names:
            safe_name(name)
        manifest = json.loads(archive.read('bundle-manifest.json'))
        if manifest['format'] != 1 or manifest['installation_performed'] is not False:
            raise ValueError('Unsupported bundle manifest')
        if set(names) != set(manifest['files']) | {'bundle-manifest.json'}:
            raise ValueError('Bundle contents differ from the manifest')
        for name, entry in manifest['files'].items():
            data = archive.read(name)
            if len(data) != entry['size'] or sha256(data) != entry['sha256']:
                raise ValueError('Bundle checksum mismatch: ' + name)
    return {'filename': path.name, 'sha256': sha256(path.read_bytes()),
            'size_bytes': path.stat().st_size, 'files_verified': len(names),
            'installation_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--wheels', type=Path, default=Path('local/wheels'))
    parser.add_argument('--cache', type=Path, default=Path('local/build-cache'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify_bundle(args.verify)
    else:
        if not args.output:
            parser.error('--output is required when building a bundle')
        result = build_bundle(args.root, args.wheels, args.cache, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
