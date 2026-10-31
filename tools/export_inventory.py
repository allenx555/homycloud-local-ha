"""Export only required private fields, without MQTT credentials. Never overwrites files."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.homycloud_local.runtime import load_runtime


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bridge-config', required=True)
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    config=load_runtime(args.bridge_config)
    # O_EXCL prevents accidental replacement of a working configuration.
    fd=os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        json.dump(config,stream,ensure_ascii=False,indent=2)
    print('Private inventory exported; do not commit this file.')


if __name__=='__main__':main()
