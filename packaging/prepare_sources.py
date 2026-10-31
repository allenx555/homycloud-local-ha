"""Extract verified source inputs and apply explicit packaging-only changes."""
import json
from pathlib import Path
import shutil
import tarfile

BASE=Path('/build')
INPUT=BASE/'inputs'
WORK=BASE/'work'


def unpack(archive,target):
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive) as stream:
        members=stream.getmembers()
        roots={Path(member.name).parts[0] for member in members}
        if len(roots)!=1:
            raise ValueError('Expected one source archive root')
        stream.extractall(target,filter='data')
    source=target/next(iter(roots))
    return source


native=unpack(INPUT/'cyclonedds-source.tar.gz',WORK/'c-source')
# Every build gets an empty work directory; these rename operations never replace production data.
native.rename(WORK/'cyclonedds')
with tarfile.open(INPUT/'linux-headers-7.0.0-r1.apk',ignore_zeros=True) as archive:
    files=[m for m in archive.getmembers() if m.isfile() and m.name.startswith('usr/include/')]
    archive.extractall(BASE/'linux-headers',members=files,filter='data')
with tarfile.open(INPUT/'wheelhouse.tar') as archive:
    archive.extractall(BASE/'wheelhouse',filter='data')
from prepare_python import prepare_python
prepare_python(BASE)
