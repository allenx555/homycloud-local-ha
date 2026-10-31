"""Run under HA's Python environment; uses simulated DDS, never a gateway."""
import asyncio
import importlib.util
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from custom_components.homycloud_local.protocol.state import StateStore, validate_command

HA_AVAILABLE = importlib.util.find_spec('homeassistant') is not None
if HA_AVAILABLE:
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import HomeAssistantError
    from custom_components.homycloud_local.coordinator import HomyCoordinator
    from custom_components.homycloud_local.climate import HomyClimate
    from custom_components.homycloud_local.number import HomyNumber


class FakeDds:
    instances = []

    def __init__(self, **kwargs):
        self.devices={d['id']:d for d in kwargs['devices']}
        self.store=StateStore();self.read_only=kwargs['read_only']
        self.commands=[];self.pending=[];self.stamp=1;self.feedback=True
        type(self).instances.append(self)

    def start(self):
        for key,value in {'switch':'false','temp_set':'21.0','temp_current':'24.0','level':'middle','mode':'cold','heating_temp_set_c':'26.0'}.items():
            self.store.update('fixture',key,value,self.stamp)

    def poll(self):
        while self.pending and self.feedback:
            did,key,value=self.pending.pop(0);self.stamp+=1
            raw=('true' if value else 'false') if type(value) is bool else str(value)
            self.store.update(did,key,raw,self.stamp)
        return True

    def request(self,did):pass

    def command(self,did,key,value):
        if self.read_only:raise AssertionError('Write from read-only worker')
        value=validate_command(self.devices[did],key,value)
        self.commands.append((key,value));self.pending.append((did,key,value))

    def close(self):pass


@unittest.skipUnless(HA_AVAILABLE,'Requires HA runtime; run on the isolated HA test environment')
class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeDds.instances=[]
        self.folder=tempfile.TemporaryDirectory()
        self.hass=HomeAssistant(self.folder.name)
        self.entry=SimpleNamespace(entry_id='isolated_fixture',domain='homycloud_local',
                                  options={'enable_control':True},data={},pref_disable_polling=False,
                                  async_on_unload=lambda cb:None)
        device={'id':'fixture','name':'Fixture','kind':'climate','model':'Fixture',
                'entities':{'switch':{'component':'switch','name':'Power'},'ac':{'component':'climate','name':'AC'},'heating_temp_set_c':{'component':'number','name':'Heat target','extra':{'min':16,'max':35,'step':1,'unit_of_measurement':'°C'}}},
                'hvac':{'temperature':True,'mode':True,'fan':True,
                        'modes':{'off':None,'cool':'cold','heat':'heat','auto':'auto'}}}
        self.coordinator=HomyCoordinator(self.hass,self.entry,{'devices':[device],'partition':'fixture','dds_xml':'unused'})
        self.patcher=patch('custom_components.homycloud_local.coordinator.DdsClient',FakeDds)
        self.patcher.start()
        await self.coordinator.async_start()
        for _ in range(30):
            if self.coordinator.data['online']:break
            await asyncio.sleep(.1)
        self.assertEqual(self.coordinator.data['online'],['fixture'])
        self.client=FakeDds.instances[-1]

    async def asyncTearDown(self):
        await self.coordinator.async_stop()
        self.patcher.stop()
        await self.hass.async_stop()
        self.folder.cleanup()

    async def test_climate_waits_for_power_before_mode_and_maps_fan(self):
        import time
        original_snapshot=self.client.store.snapshot
        def delayed_snapshot():
            time.sleep(.03)
            return original_snapshot()
        self.client.store.snapshot=delayed_snapshot
        entity=HomyClimate(self.coordinator,'fixture','ac');entity.hass=self.hass
        await entity.async_set_hvac_mode('heat')
        self.assertEqual(self.client.commands[:2],[('switch',True),('mode','heat')])
        await entity.async_set_fan_mode('medium')
        await entity.async_set_temperature(temperature=22)
        self.assertEqual(entity.fan_mode,'medium')
        self.assertEqual(entity.target_temperature,22)
        self.assertEqual(str(entity.hvac_mode),'heat')
        for target in [23,24,25]:
            await entity.async_set_temperature(temperature=target)
            self.assertEqual(entity.target_temperature,target)

    async def test_missing_feedback_times_out_without_replay(self):
        self.client.feedback=False
        with self.assertRaises(HomeAssistantError):
            await self.coordinator.async_command('fixture','switch',True)
        self.assertEqual(self.client.commands,[('switch',True)])

    async def test_pending_request_fails_on_unload_and_readonly_rejects(self):
        self.coordinator.read_only=True
        with self.assertRaises(HomeAssistantError):
            await self.coordinator.async_command('fixture','switch',True)
        self.assertEqual(self.client.commands,[])
        self.coordinator.read_only=False;self.client.feedback=False
        task=asyncio.create_task(self.coordinator.async_command('fixture','switch',True))
        await asyncio.sleep(.2)
        await self.coordinator.async_stop()
        with self.assertRaises(HomeAssistantError):await task
        self.assertTrue(self.coordinator._worker.done())


    async def test_number_state_is_scalar_and_does_not_shadow_value_property(self):
        entity=HomyNumber(self.coordinator,'fixture','heating_temp_set_c');entity.hass=self.hass
        self.assertEqual(entity.native_value,26.0)
        self.assertIsInstance(entity.value,(int,float))
        self.assertIsInstance(entity.state,(int,float))
        self.assertIsInstance(str(entity.state),str)
