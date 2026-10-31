"""Run from the target HA-compatible Python environment. Never sends ChangeAttribute."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.homycloud_local.protocol.client import DdsClient
from custom_components.homycloud_local.runtime import load_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args()
    if not 3 <= args.seconds <= 300:
        parser.error('--seconds must be between 3 and 300')
    config = load_runtime(args.inventory)
    client = DdsClient(devices=config['devices'], partition=config['partition'], xml=config['dds_xml'])
    start = time.monotonic()
    try:
        client.start()
        assert client.change is None
        due = {did:time.monotonic()+2+i*.18 for i,did in enumerate(client.devices)}
        while time.monotonic()-start < args.seconds:
            client.poll()
            now = time.monotonic()
            for did in client.devices:
                if now >= due[did]:
                    client.request(did)
                    due[did] = now+30
            time.sleep(.1)
        count = len(client.store.values)
        print(json.dumps({'python':sys.version.split()[0], 'read_only':client.read_only,
                          'control_writer_created':client.change is not None,
                          'configured_devices':len(client.devices), 'responding_devices':count,
                          'attribute_count':sum(len(v) for v in client.store.values.values())}))
        return 0 if count == len(client.devices) else 1
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
