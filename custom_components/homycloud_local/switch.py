"""Power and lighting switches."""
from homeassistant.components.switch import SwitchEntity
from .entity import HomyEntity, add_platform


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'switch', HomySwitch)


class HomySwitch(HomyEntity, SwitchEntity):
    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'switch')

    @property
    def is_on(self):
        value = self.raw_value()
        return value == 'true' if value in ('true', 'false') else None

    async def async_turn_on(self, **kwargs):
        await self.send(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.send(self.key, False)
