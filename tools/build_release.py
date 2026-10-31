"""Build a versioned integration ZIP from public source files, without native dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from packaging.version import Version

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_candidate import read_source

DOMAIN = 'homycloud_local'
TAG_PATTERN = re.compile(
    r'v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'
    r'(?:-?(?:alpha|beta|rc|dev|a|b)[.-]?\d*)?'
)


def release_version(tag, source_version):
    if tag:
        if not TAG_PATTERN.fullmatch(tag):
            raise ValueError('Expected a version tag such as v1.2.3 or v1.2.3-rc.1')
        version = Version(tag[1:])
    else:
        version = Version(source_version)
    return str(version), version.is_prerelease


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_release(root, output, *, tag=None, commit=None):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError('Release output already exists; choose a new directory')
    if commit is not None and not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Source commit must be a full SHA-1 commit ID')
    component = root / 'custom_components' / DOMAIN
    paths = set()
    for pattern in ('*.py', 'protocol/*.py', 'manifest.json', 'strings.json',
                    'protocol/schemas.json', 'translations/*.json', 'brand/*.png'):
        paths.update(component.glob(pattern))
    files = {path.relative_to(component).as_posix(): read_source(root, path.relative_to(root))
             for path in sorted(paths)}
    required = {'__init__.py', 'manifest.json', 'config_flow.py',
                'strings.json', 'protocol/schemas.json', 'brand/icon.png'}
    if required - files.keys():
        raise ValueError('Integration source is incomplete')
    manifest = json.loads(files['manifest.json'])
    if manifest['domain'] != DOMAIN:
        raise ValueError('Unexpected integration domain')
    version, prerelease = release_version(tag, manifest['version'])
    manifest['version'] = version
    files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    # All inputs are validated before creating output; existing artifacts are never overwritten.
    output.mkdir(parents=True)
    archive_path = output / f'{DOMAIN}.zip'
    with zipfile.ZipFile(archive_path, 'x') as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    archive_hash = digest(archive_path.read_bytes())
    metadata = {
        'domain': DOMAIN, 'version': version, 'tag': tag, 'source_commit': commit,
        'prerelease': prerelease, 'native_runtime_bundled': False,
        'archive': {'filename': archive_path.name, 'sha256': archive_hash,
                    'size_bytes': archive_path.stat().st_size},
        'files': {name: {'sha256': digest(data), 'size_bytes': len(data)}
                  for name, data in sorted(files.items())},
    }
    metadata_path = output / 'release-manifest.json'
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')
    (output / 'SHA256SUMS').write_text(
        f'{archive_hash}  {archive_path.name}\n'
        f'{digest(metadata_path.read_bytes())}  {metadata_path.name}\n',
        encoding='utf-8', newline='\n')
    notes = (
        f'HomyCloud {version}\n\n'
        '下载 `homycloud_local.zip`，将包内文件解压到 HA 配置目录的 '
        '`custom_components/homycloud_local/`，然后重启 HA。请先备份已有配置。\n\n'
        '此 ZIP 包含集成代码、协议结构和图标，不包含家庭私有清单或 CycloneDDS 原生依赖。'
        '新安装仍需按仓库说明准备与 HA Python、CPU 和系统匹配的 DDS 运行时；'
        '已有兼容运行时的安装可以继续使用它。\n\n'
        '`SHA256SUMS` 用于校验下载文件，`release-manifest.json` 记录版本、源码提交及包内文件摘要。\n'
    )
    (output / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8', newline='\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('dist'))
    parser.add_argument('--tag')
    parser.add_argument('--commit')
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    metadata = build_release(args.root, args.output, tag=args.tag, commit=args.commit)
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(f"version={metadata['version']}\n")
            stream.write(f"prerelease={str(metadata['prerelease']).lower()}\n")
    print(json.dumps({key: metadata[key] for key in
                     ('version', 'prerelease', 'native_runtime_bundled', 'archive')}, indent=2))


if __name__ == '__main__':
    main()
