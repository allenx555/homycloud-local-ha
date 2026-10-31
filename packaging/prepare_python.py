"""Backport exact upstream Python 3.14 patches onto the matching stable bindings."""
from pathlib import Path
import json
import shutil
import subprocess
import tarfile


def prepare_python(base):
    base=Path(base);work=base/'work';inputs=base/'inputs';temp=work/'stable-python-source'
    temp.mkdir()
    with tarfile.open(inputs/'cyclonedds-python-source.tar.gz') as archive:
        archive.extractall(temp,filter='data')
    roots=list(temp.iterdir())
    if len(roots)!=1 or not roots[0].is_dir():raise ValueError('Unexpected Python source root')
    target=work/'python';roots[0].rename(target)
    for name in ['cyclonedds-python-pr323.patch','cyclonedds-python-pr327.patch']:
        subprocess.run(['git','apply','--include=cyclonedds/*',str(inputs/name)],cwd=target,check=True)
    setup=target/'setup.py';text=setup.read_text(encoding='utf-8')
    old='__version__ = "11.0.1"'
    if text.count(old)!=1:raise ValueError('Unexpected upstream version declaration')
    text=text.replace(old,'__version__ = "11.0.1+homycloud.2"')
    text=text.replace('"*py.typed"','"*py.typed", "THIRD_PARTY_LICENSES/*"')
    setup.write_text(text,encoding='utf-8')
    licenses=target/'cyclonedds/THIRD_PARTY_LICENSES';licenses.mkdir()
    for path in (work/'cyclonedds').glob('LICENSE*'):
        if path.is_file():shutil.copy2(path,licenses/path.name)
    (base/'packaging-patches.json').write_text(json.dumps({
        'python_base':'11.0.1','backported_runtime_patches':[323,327],
        'unmodified_native_extension':True,'c_library':'11.0.1',
        'local_version':'11.0.1+homycloud.2',
        'packaging_changes':['local version','native library license files']},indent=2),encoding='utf-8')


if __name__=='__main__':prepare_python('/build')
