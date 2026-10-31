"""Prepare a hash-verified offline Docker build context from pinned public inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlparse


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    return value.hexdigest()


def cached_input(item,cache,*,offline=False,opener=None):
    name=item['filename']
    if Path(name).name!=name or '/' in name or '\\' in name:
        raise ValueError('Unsafe input filename')
    target=cache/name
    if target.exists():
        if digest(target)!=item['sha256']:
            raise ValueError('Cached input checksum mismatch: '+name)
        return target
    if offline:
        raise FileNotFoundError('Missing cached input: '+name)
    if urlparse(item['url']).scheme!='https':
        raise ValueError('Inputs must use HTTPS')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',prefix=name+'.',suffix='.partial',dir=cache,delete=False) as output:
            temporary=Path(output.name)
            with (opener or urllib.request.urlopen)(item['url'],timeout=60) as response:
                shutil.copyfileobj(response,output)
        if digest(temporary)!=item['sha256']:
            raise ValueError('Downloaded input checksum mismatch: '+name)
        temporary.rename(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def deterministic_tar(output,files):
    with tarfile.open(output,'w',format=tarfile.USTAR_FORMAT) as archive:
        for name,path in sorted(files):
            info=tarfile.TarInfo(name)
            info.size=Path(path).stat().st_size
            info.mode=0o644
            info.mtime=0
            with Path(path).open('rb') as stream:
                archive.addfile(info,stream)


def prepare_context(lock,cache,output,recipes,*,offline=False,opener=None):
    cache=Path(cache);output=Path(output);recipes=Path(recipes)
    if output.exists():
        raise FileExistsError('Build context already exists; choose a new output directory')
    cache.mkdir(parents=True,exist_ok=True)
    paths={}
    for item in lock['inputs']+lock['apk_packages']+lock['wheels']:
        path=cached_input(item,cache,offline=offline,opener=opener)
        if item['filename'] in paths and paths[item['filename']]!=path:
            raise ValueError('Conflicting build inputs')
        paths[item['filename']]=path
    inputs=output/'inputs';scripts=output/'scripts'
    inputs.mkdir(parents=True);scripts.mkdir()
    for item in lock['inputs']:
        shutil.copy2(paths[item['filename']],inputs/item['filename'])
    for bundle in sorted({item['bundle'] for item in lock['apk_packages']}):
        files=[('apks/'+item['filename'],paths[item['filename']])
               for item in lock['apk_packages'] if item['bundle']==bundle]
        deterministic_tar(inputs/bundle,files)
    deterministic_tar(inputs/'wheelhouse.tar',[(item['filename'],paths[item['filename']]) for item in lock['wheels']])
    for name in ['build-wheel.sh','prepare_sources.py','prepare_python.py']:
        shutil.copyfile(recipes/name,scripts/name)
    shutil.copyfile(recipes/'Dockerfile',output/'Dockerfile')
    (inputs/'SOURCE_LOCK.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8',newline='\n')
    sums=[digest(path)+'  inputs/'+path.name for path in sorted(inputs.iterdir()) if path.is_file()]
    (inputs/'SHA256SUMS').write_text('\n'.join(sums)+'\n',encoding='utf-8',newline='\n')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--proxy')
    args=parser.parse_args()
    recipes=Path(__file__).resolve().parents[1]/'packaging'
    lock=json.loads((recipes/'inputs.lock.json').read_text(encoding='utf-8'))
    opener=None
    if args.proxy:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':args.proxy})).open
    output=prepare_context(lock,args.cache,args.output,recipes,offline=args.offline,opener=opener)
    print('Verified offline build context prepared: '+str(output))


if __name__=='__main__':main()
