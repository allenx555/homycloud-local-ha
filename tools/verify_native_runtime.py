"""Check an installed compatibility wheel without importing any private home configuration."""
import importlib.metadata
import json
from pathlib import Path
import sys


def main():
    import cyclonedds
    from cyclonedds.__library__ import library_path
    from cyclonedds.idl._typesupport.DDS.XTypes import TypeIdentifier, TypeMapping
    from cyclonedds.idl._xt_builder import XTInterpreter
    version=importlib.metadata.version('cyclonedds')
    if version!='11.0.1+homycloud.2':
        raise RuntimeError('Unexpected DDS wheel version')
    package_root=Path(cyclonedds.__file__).resolve().parent.parent
    native=Path(library_path).resolve()
    if not native.is_file() or not native.is_relative_to(package_root):
        raise RuntimeError('Native library is not bundled with the installed wheel')
    schema=Path(__file__).resolve().parents[1]/'custom_components/homycloud_local/protocol/schemas.json'
    saved=json.loads(schema.read_text(encoding='utf-8'))['types']
    count=0
    for item in saved.values():
        mapping=TypeMapping.deserialize(bytes.fromhex(item['type_map']))
        tid=TypeIdentifier.deserialize(bytes.fromhex(item['type_id']))
        XTInterpreter.xt_to_class(tid,{p.type_identifier:p.type_object for p in
                                      mapping.identifier_object_pair_complete+mapping.identifier_object_pair_minimal})
        count+=1
    print(json.dumps({'version':version,'python':sys.version.split()[0],
                      'bundled_library':native.name,'bundled_library_verified':True,
                      'types_constructed':count}))


if __name__=='__main__':main()
