"""HomyCloud: local DDS integration, read-only unless explicitly enabled."""

async def async_setup_entry(hass, entry):
    from homeassistant.exceptions import ConfigEntryNotReady
    from .const import PLATFORMS
    from .coordinator import HomyCoordinator
    from .runtime import load_runtime
    from .schedule_links import collect_schedule_links, async_setup_schedule_links
    try:
        config = await hass.async_add_executor_job(load_runtime, hass.config.path(entry.data['inventory_path']))
        schedule_links = collect_schedule_links(config['devices'])
        coordinator = HomyCoordinator(hass, entry, config)
        await coordinator.async_start()
    except Exception as err:
        raise ConfigEntryNotReady('DDS runtime or inventory unavailable; see diagnostics') from err
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        async_setup_schedule_links(hass, entry, schedule_links)
    except BaseException:
        await coordinator.async_stop()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    from .const import PLATFORMS
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True
