"""HomyCloud configuration; control defaults to disabled."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, NAME


class HomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({'inventory_path':user_input['inventory_path']})
            from .runtime import load_runtime
            try:
                await self.hass.async_add_executor_job(load_runtime, self.hass.config.path(user_input['inventory_path']))
            except (OSError, ValueError, TypeError):
                errors['base'] = 'invalid_inventory'
            else:
                return self.async_create_entry(title=NAME, data=user_input)
        return self.async_show_form(step_id='user', data_schema=vol.Schema({
            vol.Required('inventory_path', default='homycloud_local/inventory.json'):str,
            vol.Required('enable_control', default=False):bool,
        }), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HomyOptionsFlow(config_entry)


class HomyOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title='', data=user_input)
        enabled = self._entry.options.get('enable_control', self._entry.data.get('enable_control', False))
        return self.async_show_form(step_id='init', data_schema=vol.Schema({
            vol.Required('enable_control', default=enabled):bool,
        }))
