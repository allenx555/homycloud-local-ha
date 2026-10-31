"""Curtains using the verified percent_control and stop commands."""
from homeassistant.components.cover import CoverEntity, CoverEntityFeature, CoverDeviceClass, ATTR_POSITION
from .entity import HomyEntity, add_platform
from .protocol.cover import displayed_position, native_position


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'cover', HomyCover)


class HomyCover(HomyEntity, CoverEntity):
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE |
                                CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION)

    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'cover')
        self.inverted = bool(self.device.get('invert_position', False))
        self._direction = None

    @property
    def current_cover_position(self):
        return displayed_position(self.raw_value('percent_control'), self.inverted)

    @property
    def is_closed(self):
        position = self.current_cover_position
        return position == 0 if position is not None else None

    @property
    def is_opening(self):
        return self._motion() == 'opening' and self.current_cover_position != 100

    @property
    def is_closing(self):
        return self._motion() == 'closing' and self.current_cover_position != 0

    def _motion(self):
        control = self.raw_value('control')
        if control in ('open', 'close'):
            self._direction = 'opening' if (control == 'open') != self.inverted else 'closing'
        elif control == 'stop':
            self._direction = None
        return self._direction if control in ('open', 'close', 'continue') else None

    async def async_open_cover(self, **kwargs):
        await self.send('percent_control', native_position(100, self.inverted))

    async def async_close_cover(self, **kwargs):
        await self.send('percent_control', native_position(0, self.inverted))

    async def async_stop_cover(self, **kwargs):
        await self.send('control', 'stop')

    async def async_set_cover_position(self, **kwargs):
        await self.send('percent_control', native_position(kwargs[ATTR_POSITION], self.inverted))
