"""Common entity metadata and non-optimistic property access."""
import math
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


class HomyEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, did, key, platform):
        super().__init__(coordinator)
        self.did, self.key = did, key
        self.device = coordinator.devices[did]
        self.spec = self.device['entities'][key]
        self._attr_unique_id = f'homycloud_{did}_{key}_{platform}'
        self._attr_name = self.spec['name']
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, did)}, name=self.device['name'],
            manufacturer='HomyCloud', model=self.device.get('model', 'Unknown'))

    @property
    def available(self):
        return self.did in self.coordinator.data['online']

    def raw_value(self, key=None):
        return self.coordinator.data['values'].get(self.did, {}).get(key or self.key)

    async def send(self, key, value):
        await self.coordinator.async_command(self.did, key, value)


def add_platform(entry, async_add_entities, platform, entity_class):
    coordinator = entry.runtime_data
    async_add_entities(entity_class(coordinator, did, key)
                       for did, device in coordinator.devices.items()
                       for key, spec in device['entities'].items()
                       if spec['component'] == platform)
