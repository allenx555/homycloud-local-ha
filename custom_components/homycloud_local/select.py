"""Enumerated native settings."""
from homeassistant.components.select import SelectEntity
from .entity import HomyEntity, add_platform


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'select', HomySelect)


class HomySelect(HomyEntity, SelectEntity):
    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'select')
        self._attr_options = self.spec['extra']['options']

    @property
    def current_option(self):
        raw = self.raw_value()
        mapped = {str(value): label for label, value in self.spec.get('command_values', {}).items()}
        value = mapped.get(raw, raw)
        return value if value in self.options else None

    async def async_select_option(self, option):
        await self.send(self.key, option)
