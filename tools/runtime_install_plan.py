"""Validate a bundled DDS wheel and report HA's persistent dependency path. No installation."""
import argparse
import email
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import sysconfig
import zipfile

VERSION='11.0.1+homycloud.2'


def inspect_wheel(path,expected_hash,compatible_tags):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_hash:
        raise ValueError('Wheel checksum mismatch')
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        for name in names:
            relative=PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name:
                raise ValueError('Unsafe archive path')
        metadata_files=[n for n in names if n.endswith('.dist-info/METADATA')]
        wheel_files=[n for n in names if n.endswith('.dist-info/WHEEL')]
        if len(metadata_files)!=1 or len(wheel_files)!=1:
            raise ValueError('Wheel metadata is ambiguous')
        metadata=email.message_from_bytes(archive.read(metadata_files[0]))
        if metadata['Name']!='cyclonedds' or metadata['Version']!=VERSION:
            raise ValueError('Unexpected runtime distribution or version')
        wheel=email.message_from_bytes(archive.read(wheel_files[0]))
        tags=set(wheel.get_all('Tag',[]))
        if not tags.intersection(compatible_tags):
            raise ValueError('Wheel is not compatible with this Python/platform')
        libraries=[name for name in names if name.startswith('cyclonedds.libs/libddsc') and '.so' in name]
        if not libraries:
            raise ValueError('Wheel does not bundle its native DDS library')
        if not any(name.startswith('cyclonedds/THIRD_PARTY_LICENSES/') for name in names):
            raise ValueError('Bundled native-library license is missing')
        if archive.testzip() is not None:
            raise ValueError('Wheel ZIP integrity check failed')
    return {'filename':path.name,'version':VERSION,'tags':sorted(tags),'sha256':expected_hash,
            'bundled_libraries':libraries}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',required=True,type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--ha-config',required=True,type=Path)
    args=parser.parse_args()
    from packaging.tags import sys_tags
    wheel=inspect_wheel(args.wheel,args.sha256,{str(tag) for tag in sys_tags()})
    if sys.prefix!=sys.base_prefix or sys.platform!='linux':
        raise ValueError('This plan supports non-venv Linux HA runtimes only')
    config=args.ha_config.resolve()
    target=Path(sysconfig.get_path('purelib',scheme='posix_user',vars={'userbase':str(config/'deps')}))
    if not target.is_relative_to(config):
        raise ValueError('Dependency path is outside the specified HA configuration directory')
    print(json.dumps({'read_only':True,'installation_performed':False,'wheel':wheel,
                      'dependency_target':str(target),'python':sys.version.split()[0]},indent=2))


if __name__=='__main__':main()
