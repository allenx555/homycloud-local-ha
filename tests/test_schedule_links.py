from types import SimpleNamespace
import unittest

from custom_components.homycloud_local.schedule_links import (
    collect_schedule_links, reconcile_schedule_links,
)


class Registry:
    def __init__(self, entities):
        self.entities = entities
        self.updates = []

    def async_get(self, entity_id):
        return self.entities.get(entity_id)

    def async_update_entity(self, entity_id, **changes):
        self.updates.append((entity_id, changes))
        for key, value in changes.items():
            setattr(self.entities[entity_id], key, value)


class Devices:
    def __init__(self, owner='entry'):
        self.device = SimpleNamespace(id='target', config_entry_id=owner)

    def async_get_device_by_identifier(self, identifier, config_entry_id):
        return self.device if identifier == ('homycloud_local', 'panel') else None


def helper(**overrides):
    return SimpleNamespace(**{
        'device_id': None, 'config_entry_id': None, 'platform': 'input_datetime',
        'entity_category': None, 'name': 'User name', 'area_id': 'room',
        'hidden_by': 'user', 'disabled_by': None, **overrides,
    })


class ScheduleLinkTests(unittest.TestCase):
    def test_validates_explicit_ownership(self):
        devices = [{'id': 'panel', 'schedule_entities': ['input_datetime.start', 'script.start']}]
        self.assertEqual(collect_schedule_links(devices), {
            'input_datetime.start': 'panel', 'script.start': 'panel'})
        self.assertEqual(collect_schedule_links([{'id': 'panel'}]), {})
        for value in ('input_datetime.start', ['switch.ac'], [None]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                collect_schedule_links([{'id': 'panel', 'schedule_entities': value}])
        with self.assertRaises(ValueError):
            collect_schedule_links(devices + [{'id': 'other', 'schedule_entities': ['script.start']}])

    def test_links_and_reconciles_reload_without_changing_user_settings(self):
        entity = helper()
        registry = Registry({'input_datetime.start': entity})
        links = {'input_datetime.start': 'panel'}
        reconcile_schedule_links(registry, Devices(), 'entry', links, 'config')
        self.assertEqual(entity.device_id, 'target')
        self.assertEqual(entity.entity_category, 'config')
        self.assertEqual((entity.name, entity.area_id, entity.hidden_by, entity.disabled_by),
                         ('User name', 'room', 'user', None))
        reconcile_schedule_links(registry, Devices(), 'entry', links, 'config')
        self.assertEqual(len(registry.updates), 1)
        entity.device_id = None  # The helper integration re-registers after reload.
        entity.entity_category = None
        reconcile_schedule_links(registry, Devices(), 'entry', links, 'config')
        self.assertEqual(len(registry.updates), 2)

    def test_does_not_steal_other_devices_or_config_entries(self):
        for overrides in ({'device_id': 'other'}, {'config_entry_id': 'other'},
                          {'platform': 'template'}):
            with self.subTest(overrides=overrides):
                registry = Registry({'input_datetime.start': helper(**overrides)})
                reconcile_schedule_links(registry, Devices(), 'entry',
                                         {'input_datetime.start': 'panel'}, 'config')
                self.assertFalse(registry.updates)

    def test_missing_helpers_and_foreign_devices_are_ignored(self):
        registry = Registry({'input_datetime.start': helper()})
        reconcile_schedule_links(registry, Devices('other'), 'entry',
                                 {'input_datetime.start': 'panel'}, 'config')
        reconcile_schedule_links(registry, Devices(), 'entry',
                                 {'input_datetime.missing': 'panel'}, 'config')
        self.assertFalse(registry.updates)
