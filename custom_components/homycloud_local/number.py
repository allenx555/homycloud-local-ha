"""Numeric settings with inventory-defined limits."""
from homeassistant.components.number import NumberEntity, NumberMode
from .entity import HomyEntity, add_platform, number


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'number', HomyNumber)


class HomyNumber(HomyEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'number')
        extra = self.spec['extra']
        self._attr_native_min_value = extra['min']
        self._attr_native_max_value = extra['max']
        self._attr_native_step = extra.get('step', 1)
        self._attr_native_unit_of_measurement = extra.get('unit_of_measurement')

    @property
    def native_value(self):
        return number(self.raw_value())

    async def async_set_native_value(self, value):
        await self.send(self.key, value)
