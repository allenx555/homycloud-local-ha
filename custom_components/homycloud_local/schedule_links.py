"""Associate explicitly configured local scheduling helpers with their device.

This only changes registry grouping. Helpers, automation logic and their state
remain owned by the original integrations.
"""
import logging
import re

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_HELPER_ID = re.compile(r'(?:input_boolean|input_datetime|input_number|timer|script)\.[a-z0-9_]+')


def collect_schedule_links(devices):
    """Validate explicit links; never infer ownership from names or room order."""
    links = {}
    for device in devices:
        entity_ids = device.get('schedule_entities', [])
        if not isinstance(entity_ids, list):
            raise ValueError('schedule_entities must be a list of helper entity IDs')
        for entity_id in entity_ids:
            if not isinstance(entity_id, str) or not _HELPER_ID.fullmatch(entity_id):
                raise ValueError('Unsupported scheduling helper entity ID')
            if entity_id in links and links[entity_id] != device['id']:
                raise ValueError('Scheduling helper is assigned to multiple devices')
            links[entity_id] = device['id']
    return links


def reconcile_schedule_links(registry, device_registry, entry_id, links, category):
    """Attach existing, unowned helpers without changing IDs or user metadata."""
    for entity_id, did in links.items():
        entity = registry.async_get(entity_id)
        device = device_registry.async_get_device_by_identifier((DOMAIN, did), entry_id)
        if entity is None or device is None or entry_id != device.config_entry_id:
            continue
        # A configured name must not move another integration's device entity.
        if entity.config_entry_id is not None or entity.platform != entity_id.split('.')[0]:
            continue
        if entity.device_id not in (None, device.id):
            _LOGGER.warning('Scheduling helper %s already belongs to another device', entity_id)
            continue
        changes = {}
        if entity.device_id != device.id:
            changes['device_id'] = device.id
        if entity.entity_category != category:
            changes['entity_category'] = category
        if changes:
            registry.async_update_entity(entity_id, **changes)


def async_setup_schedule_links(hass, entry, links):
    """Reapply links when YAML helpers register after startup or are reloaded."""
    if not links:
        return
    from homeassistant.core import callback
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.helpers.entity import EntityCategory

    registry, devices = er.async_get(hass), dr.async_get(hass)

    @callback
    def reconcile(event=None):
        if event is not None:
            if event.data.get('action') == 'remove' or event.data.get('entity_id') not in links:
                return
        reconcile_schedule_links(registry, devices, entry.entry_id, links, EntityCategory.CONFIG)

    entry.async_on_unload(hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, reconcile))
    reconcile()
