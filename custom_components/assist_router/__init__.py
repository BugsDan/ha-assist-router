"""Assist router setup. Does not edit pipelines, automations or other entries."""

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .health import HealthChecks
from .migration import migrate_v1
from .prompts import PromptManager, async_make_inspector
from .runtime import Ledger, Runtime
from .settings import Settings

PLATFORMS = [Platform.CONVERSATION]


async def async_setup_entry(hass, entry):
    settings = Settings.from_mapping({**entry.data, **entry.options})
    # Retain safety records on reload/unload, including an execution still unwinding.
    ledgers = hass.data.setdefault(DOMAIN, {})
    ledger = ledgers.setdefault(entry.entry_id, Ledger())
    entry.runtime_data = Runtime(settings, HealthChecks(async_get_clientsession(hass), settings), ledger)
    if settings.prompt.enabled:
        entry.runtime_data.prompts = PromptManager(settings, await async_make_inspector(hass))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    runtime = entry.runtime_data
    runtime.active = False
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return True
    runtime.active = True
    return False


async def async_migrate_entry(hass, entry):
    """Migrate atomically; legacy options override data exactly as in 1.0."""
    if entry.version > 3:
        return False
    if entry.version < 3:
        try:
            config = {**entry.data, **entry.options}
            if entry.version == 1:
                config = migrate_v1(config)
            config = Settings.from_mapping(config).as_dict()
        except ValueError:
            return False
        hass.config_entries.async_update_entry(entry, data={}, options=config, version=3, minor_version=1)
    return True
