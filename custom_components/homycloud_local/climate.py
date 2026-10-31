"""Triad AC capabilities, without inventing missing targets, modes or fan feedback."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .entity import HomyEntity, add_platform, number


async def async_setup_entry(hass, entry, async_add_entities):
    add_platform(entry, async_add_entities, 'climate', HomyClimate)


class HomyClimate(HomyEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, did, key):
        super().__init__(coordinator, did, key, 'climate')
        self.caps = self.device['hvac']
        self._attr_hvac_modes = [HVACMode(mode) for mode in self.caps['modes']]
        self._attr_supported_features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self.caps.get('temperature'):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if self.caps.get('fan'):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = ['auto', 'low', 'medium', 'high']

    @property
    def hvac_mode(self):
        power = self.raw_value('switch')
        if power == 'false':
            return HVACMode.OFF
        if power != 'true':
            return None
        if not self.caps.get('mode'):
            return HVACMode.AUTO
        modes = {raw: mode for mode, raw in self.caps['modes'].items() if raw is not None}
        return HVACMode(modes[self.raw_value('mode')]) if self.raw_value('mode') in modes else None

    @property
    def current_temperature(self):
        return number(self.raw_value('temp_current'))

    @property
    def target_temperature(self):
        return number(self.raw_value('temp_set')) if self.caps.get('temperature') else None

    @property
    def fan_mode(self):
        raw = self.raw_value('level')
        result = 'medium' if raw == 'middle' else raw
        return result if self.caps.get('fan') and result in self.fan_modes else None

    async def async_turn_on(self):
        await self.send('switch', True)

    async def async_turn_off(self):
        await self.send('switch', False)

    async def async_set_hvac_mode(self, hvac_mode):
        mode = str(hvac_mode)
        if mode not in self.caps['modes']:
            raise ValueError('Unsupported HVAC mode')
        if mode == 'off':
            await self.async_turn_off()
            return
        # Await real power feedback before changing mode, rather than enqueueing both blindly.
        await self.async_turn_on()
        raw = self.caps['modes'][mode]
        if raw is not None:
            await self.send('mode', raw)

    async def async_set_temperature(self, **kwargs):
        if not self.caps.get('temperature'):
            raise ValueError('Target temperature not supported')
        await self.send('temp_set', kwargs[ATTR_TEMPERATURE])

    async def async_set_fan_mode(self, fan_mode):
        if not self.caps.get('fan') or fan_mode not in self.fan_modes:
            raise ValueError('Fan mode not supported')
        await self.send('level', 'middle' if fan_mode == 'medium' else fan_mode)
