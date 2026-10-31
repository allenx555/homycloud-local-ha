"""Developer-only read-only HA entity probe. Run inside a prepared HA Python environment."""
import argparse
import asyncio
from collections import Counter
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from custom_components.homycloud_local.const import PLATFORMS
from custom_components.homycloud_local.coordinator import HomyCoordinator
from custom_components.homycloud_local.runtime import load_runtime


async def probe(inventory):
    hass=HomeAssistant('/tmp/homycloud-entity-isolated-test')
    entry=SimpleNamespace(entry_id='isolated_readonly_probe',domain='homycloud_local',
                          options={},data={},pref_disable_polling=False,
                          async_on_unload=lambda callback:None)
    coordinator=HomyCoordinator(hass,entry,load_runtime(inventory))
    try:
        await coordinator.async_start()
        await asyncio.sleep(12)
        entry.runtime_data=coordinator
        entities=[]
        counts={}
        for platform in PLATFORMS:
            before=len(entities)
            module=importlib.import_module('custom_components.homycloud_local.'+platform)
            await module.async_setup_entry(hass,entry,entities.extend)
            counts[platform]=len(entities)-before
        assert sum(counts.values())==94
        assert len({e.unique_id for e in entities})==len(entities)
        for entity in entities:
            entity.hass=hass
            # Exercise HA-native state and capability properties without registering live entities.
            entity.state
            entity.capability_attributes
        switches=[e for e in entities if e.__class__.__name__=='HomySwitch']
        try:
            await switches[0].async_turn_on()
        except HomeAssistantError:
            pass
        else:
            raise AssertionError('Read-only control was not rejected')
        print(json.dumps({'name':'HomyCloud','platforms':counts,'unique_entities':len(entities),
                          'online_devices':len(coordinator.data['online']),
                          'readonly_control_rejected':True}),flush=True)
    finally:
        await coordinator.async_stop()
        print(json.dumps({'worker_stopped':coordinator._worker.done()}),flush=True)
        await hass.async_stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--inventory',required=True)
    asyncio.run(probe(parser.parse_args().inventory))
