"""The mirAIe integration."""
from __future__ import annotations

from datetime import date

from miraie_ac import MirAIeBroker, MirAIeHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_INSTALL_DATE, DOMAIN
from .sensor import async_backfill_energy_statistics, six_months_ago

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up mirAIe from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    async with MirAIeHub() as hub:
        broker = MirAIeBroker()
        await hub.init(entry.data["username"], entry.data["password"], broker)
        hass.data[DOMAIN][entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    default_start = entry.options.get(CONF_INSTALL_DATE)
    if default_start:
        start_date = date.fromisoformat(default_start)
    else:
        start_date = six_months_ago(date.today())
    for device in hub.home.devices:
        hass.async_create_task(
            async_backfill_energy_statistics(hass, hub, device, start_date)
        )

    async def nightly_backfill(now=None):
        for device in hub.home.devices:
            hass.async_create_task(
                async_backfill_energy_statistics(hass, hub, device, start_date)
            )

    async_track_time_change(hass, nightly_backfill, hour=0, minute=5, second=0)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
