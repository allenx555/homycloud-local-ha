"""Verify HA's local-dependency hook in an isolated configuration directory."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


async def verify(config):
    if importlib.util.find_spec('cyclonedds') is not None:
        raise RuntimeError('DDS is already importable; cannot verify the local dependency hook')
    from homeassistant.bootstrap import async_mount_local_lib_path
    await async_mount_local_lib_path(str(config))
    import cyclonedds
    origin=Path(cyclonedds.__file__).resolve()
    if not origin.is_relative_to(config.resolve()/'deps'):
        raise RuntimeError('DDS was not imported from the specified configuration deps directory')
    from tools.verify_native_runtime import main
    main()
    print(json.dumps({'ha_dependency_hook_verified':True,'imported_from_config_deps':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ha-config',type=Path,required=True)
    asyncio.run(verify(parser.parse_args().ha_config))
