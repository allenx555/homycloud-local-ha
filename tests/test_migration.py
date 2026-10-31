import unittest
from tools.plan_migration import plan_migration


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.devices=[{'id':'fixture','entities':{'switch_1':{'component':'switch','name':'First'}}}]
        self.uid='homycloud_fixture_switch_1_switch'

    def test_preserves_user_entity_id_and_metadata(self):
        registry=[{'platform':'mqtt','unique_id':self.uid,'entity_id':'switch.user_named_light',
                   'name':'User name','area_id':'fixture_area','labels':['fixture_label'],'options':{'x':True}}]
        result=plan_migration(self.devices,registry)
        item=result['entities'][0]
        self.assertEqual(result['summary']['ready'],1)
        self.assertEqual(item['old_entity_id'],'switch.user_named_light')
        self.assertEqual(item['preserve']['name'],'User name')
        self.assertEqual(item['preserve']['labels'],['fixture_label'])
        self.assertEqual(registry[0]['platform'],'mqtt')

    def test_existing_native_entity_blocks_automatic_migration(self):
        registry=[{'domain':'switch','platform':'homycloud_local','unique_id':self.uid,'entity_id':'switch.existing'}]
        result=plan_migration(self.devices,{'data':{'entities':registry}})
        self.assertEqual(result['summary']['conflict'],1)

    def test_missing_and_duplicate_sources_are_explicit(self):
        self.assertEqual(plan_migration(self.devices,[])['summary']['missing'],1)
        with self.assertRaises(ValueError):plan_migration(self.devices*2,[])
