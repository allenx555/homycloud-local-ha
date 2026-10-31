"""Only declared sensors, without exposing every internal property."""
from homeassistant.components.sensor import SensorEntity
from .entity import HomyEntity, add_platform, number


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'sensor', HomySensor)


class HomySensor(HomyEntity, SensorEntity):
    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'sensor')
        extra = self.spec.get('extra', {})
        self._attr_native_unit_of_measurement = extra.get('unit_of_measurement')
        self._attr_device_class = extra.get('device_class')
        self._attr_state_class = extra.get('state_class')

    @property
    def native_value(self):
        raw = self.raw_value()
        if raw is None:
            return None
        if self.native_unit_of_measurement or self.state_class:
            return number(raw)
        return self.spec.get('display_values', {}).get(raw, raw)
