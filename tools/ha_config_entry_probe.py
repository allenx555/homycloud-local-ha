"""Load/reload/unload a real HA config entry with simulated DDS, in a disposable config."""
import argparse
import asyncio
from collections import Counter
from contextlib import nullcontext
import json
import logging
from pathlib import Path
import shutil
import sys
from types import MappingProxyType
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# This fixture configures no cloud services. Use botocore's optional-CRT fallback
# to isolate the local integration from the independently reproduced native SDK abort.
sys.modules['awscrt']=None
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState, SOURCE_USER
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.exceptions import HomeAssistantError
from custom_components.homycloud_local.protocol.state import StateStore
from custom_components.homycloud_local.protocol.client import DdsClient


class FakeDds:
    writes=0
    def __init__(self,**kwargs):
        self.devices=kwargs['devices'];self.store=StateStore();self.changed=True
        assert kwargs['read_only'] is True
    def start(self):
        for device in self.devices:
            for key in device.get('query_keys',list(device['entities'])):
                value=('false' if key.startswith('switch') else '21.0' if 'temp' in key else
                       '50' if key=='percent_control' else 'stop' if key=='control' else
                       'middle' if key=='level' else 'low' if key=='fan_speed_enum' else
                       'cold' if key=='mode' else 'air_conditioner' if key=='work_mode' else 'unknown')
                self.store.update(device['id'],key,value,1)
    def poll(self):
        result=self.changed;self.changed=False;return result
    def request(self,did):pass
    def command(self,*args):
        type(self).writes+=1;raise AssertionError('Read-only probe attempted device control')
    def close(self):pass


class ReadOnlyDds(DdsClient):
    writers_created=0
    command_attempts=0
    def start(self):
        if not self.read_only:raise AssertionError('Real DDS must remain read-only')
        super().start()
        if self.change is not None:
            type(self).writers_created+=1
            raise AssertionError('Control writer created during read-only probe')
    def command(self,*args):
        type(self).command_attempts+=1
        raise AssertionError('Real DDS control blocked by the probe')


async def wait_online(entry,expected):
    for _ in range(100):
        if len(entry.runtime_data.data['online'])==expected:return
        await asyncio.sleep(.2)
    raise AssertionError('Not all configured devices responded')


async def main(config,inventory,real_dds=False):
    errors=[]
    class ErrorCapture(logging.Handler):
        def emit(self,record):
            if record.levelno>=logging.ERROR:errors.append(record.name)
    handler=ErrorCapture()
    for logger in ['homeassistant.helpers.entity','homeassistant.helpers.entity_platform','homeassistant.helpers.update_coordinator']:
        logging.getLogger(logger).addHandler(handler)
    config.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parents[1]/'custom_components'
    shutil.copytree(source,config/'custom_components',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(inventory,config/'inventory.json')
    hass=HomeAssistant(str(config));loader.async_setup(hass)
    hass.config.skip_pip=True
    hass.config_entries=ConfigEntries(hass,{'http':{'server_host':'127.0.0.1','server_port':18124}})
    from homeassistant.bootstrap import async_load_base_functionality
    assert await async_load_base_functionality(hass)
    try:
        with patch('custom_components.homycloud_local.coordinator.DdsClient',ReadOnlyDds if real_dds else FakeDds):
            form=await hass.config_entries.flow.async_init('homycloud_local',context={'source':SOURCE_USER})
            assert form['type']=='form'
            created=await hass.config_entries.flow.async_configure(form['flow_id'],{
                'inventory_path':'inventory.json','enable_control':False})
            assert created['type']=='create_entry',created['type']
            entry=created['result']
            assert entry.title=='HomyCloud'
            duplicate=await hass.config_entries.flow.async_init('homycloud_local',context={'source':SOURCE_USER})
            duplicate=await hass.config_entries.flow.async_configure(duplicate['flow_id'],{
                'inventory_path':'inventory.json','enable_control':False})
            assert duplicate['type']=='abort'
            options=await hass.config_entries.options.async_init(entry.entry_id)
            assert options['type']=='form' 
            expected_devices=len(json.loads(inventory.read_text(encoding='utf-8'))['devices'])
            await wait_online(entry,expected_devices)
            await asyncio.sleep(.2)
            assert entry.state==ConfigEntryState.LOADED,entry.state
            registry=er.async_get(hass)
            registered=[e for e in registry.entities.values() if e.config_entry_id==entry.entry_id]
            assert len(registered)==94,len(registered)
            counts=dict(Counter(e.domain for e in registered))
            invalid=[]
            for registered_entity in registered:
                obj=hass.data[registered_entity.domain].get_entity(registered_entity.entity_id)
                raw=obj.state
                if raw is not None and not isinstance(raw,(str,int,float,bool)):
                    invalid.append({'platform':registered_entity.domain,'class':type(obj).__name__,
                                    'state_type':type(raw).__name__,'bound_to_self':getattr(raw,'__self__',None) is obj})
            print(json.dumps({'invalid_states':invalid}),flush=True)
            assert not invalid,'Entity returned a non-scalar state'
            assert all(hass.states.get(item.entity_id) is not None for item in registered)
            switch=next(e.entity_id for e in registered if e.domain=='switch')
            try:
                await hass.services.async_call('switch','turn_on',{'entity_id':switch},blocking=True)
            except HomeAssistantError:
                pass
            else:
                raise AssertionError('Read-only HA service was not rejected')
            old=entry.runtime_data
            assert await hass.config_entries.async_reload(entry.entry_id)
            await wait_online(entry,expected_devices)
            await asyncio.sleep(.2)
            assert old._worker.done()
            assert len([e for e in registry.entities.values() if e.config_entry_id==entry.entry_id])==94
            active=entry.runtime_data
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert active._worker.done()
            assert FakeDds.writes==0
            assert not errors,errors
            print(json.dumps({'config_entry_loaded':True,'config_flow_passed':True,'duplicate_rejected':True,'options_form_passed':True,'registered_entities':94,'platforms':counts,
                              'reload_passed':True,'unload_passed':True,'readonly_service_rejected':True,
                              'simulated_dds_writes':FakeDds.writes,'background_errors':len(errors),'optional_aws_crt_disabled_in_fixture':True,'real_dds':real_dds,'native_control_writers_created':ReadOnlyDds.writers_created,'real_control_attempts':ReadOnlyDds.command_attempts}),flush=True)
    finally:
        await hass.async_stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--real-dds',action='store_true',help='Only enables real read-only queries; control remains blocked')
    args=parser.parse_args()
    asyncio.run(main(args.config,args.inventory,args.real_dds))
