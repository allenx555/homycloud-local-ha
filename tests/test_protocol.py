import unittest
from custom_components.homycloud_local.protocol.state import StateStore, validate_command
from custom_components.homycloud_local.protocol.client import DdsClient


class ProtocolTests(unittest.TestCase):
    def test_delayed_query_cannot_restore_old_temperature(self):
        store=StateStore()
        self.assertTrue(store.update('a','temp_set','18',200))
        self.assertFalse(store.update('a','temp_set','17',100))
        self.assertEqual(store.snapshot()['a']['temp_set'],'18')
        self.assertFalse(store.update('a','temp_set','17',None))

    def test_conflicting_equal_timestamp_does_not_change_state(self):
        store=StateStore();store.update('a','control','stop',200)
        self.assertFalse(store.update('a','control','open',200))
        self.assertEqual(store.snapshot()['a']['control'],'stop')

    def test_switch_does_not_accept_numeric_or_text_booleans(self):
        device={'entities':{'switch':{'component':'switch'}}}
        self.assertIs(validate_command(device,'switch',False),False)
        for value in [0,1,'false','ON',None]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_command(device,'switch',value)

    def test_cover_command_bounds_and_stop(self):
        d={'kind':'cover','entities':{}}
        self.assertEqual(validate_command(d,'control','stop'),'stop')
        self.assertEqual(validate_command(d,'percent_control',99),99)
        for value in [-1,100,True,float('nan'),'50']:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_command(d,'percent_control',value)

    def test_read_only_client_cannot_write_even_before_start(self):
        client=DdsClient(devices=[{'id':'fake','entities':{}}],partition='fake',xml='<CycloneDDS/>')
        with self.assertRaises(PermissionError):client.command('fake','switch',True)
        self.assertIsNone(client.change)

    def test_unknown_capability_and_temperature_limits(self):
        d={'entities':{},'hvac':{'temperature':True}}
        self.assertEqual(validate_command(d,'temp_set',21),21.0)
        for value in [True,15,31,21.5,float('inf')]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_command(d,'temp_set',value)
        with self.assertRaises(ValueError):validate_command(d,'mode','heat')

    def test_snapshot_is_detached(self):
        store=StateStore();store.update('a','switch','false',1);snapshot=store.snapshot()
        snapshot['a']['switch']='true'
        self.assertEqual(store.snapshot()['a']['switch'],'false')


    def test_unrelated_query_response_does_not_consume_pending_request(self):
        from types import SimpleNamespace
        import time
        class Reader:
            def __init__(self, samples): self.samples=samples
            def take(self, count):
                samples,self.samples=self.samples,[]
                return samples
        client=DdsClient(devices=[{'id':'fake','entities':{}}],partition='fake',xml='<CycloneDDS/>')
        client.pending['request']=('fake',time.monotonic())
        client.report=Reader([])
        client.response=Reader([SimpleNamespace(messageId='request',deviceId='other',dpResultArr='{}')])
        self.assertFalse(client.poll())
        self.assertIn('request',client.pending)
        client.response=Reader([SimpleNamespace(messageId='request',deviceId='fake',dpResultArr='{"switch":{"value":"false","time":"200"}}')])
        self.assertTrue(client.poll())
        self.assertNotIn('request',client.pending)
        self.assertEqual(client.store.snapshot()['fake']['switch'],'false')

    def test_malformed_response_does_not_crash_worker(self):
        from types import SimpleNamespace
        import time
        class Reader:
            def __init__(self,samples): self.samples=samples
            def take(self,count): return self.samples
        client=DdsClient(devices=[{'id':'fake','entities':{}}],partition='fake',xml='<CycloneDDS/>')
        client.pending['request']=('fake',time.monotonic());client.report=Reader([])
        client.response=Reader([SimpleNamespace(messageId='request',deviceId='fake',dpResultArr='[]')])
        self.assertFalse(client.poll())
        self.assertEqual(client.store.snapshot(),{})


if __name__=='__main__':unittest.main()
