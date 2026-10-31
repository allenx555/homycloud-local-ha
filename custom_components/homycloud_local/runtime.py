"""Load private per-home settings; never bundle these in the integration."""
import json
from pathlib import Path


def load_runtime(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    for key in ('devices', 'partition', 'dds_xml'):
        if not config.get(key):
            raise ValueError('Missing inventory configuration')
    if not isinstance(config['devices'], list):
        raise ValueError('Inventory devices must be a list')
    # Drop MQTT credentials and unrelated bridge fields at the input boundary.
    return {key: config[key] for key in ('devices', 'partition', 'dds_xml')}
