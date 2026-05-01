"""Service handlers for the mirAIe integration.

Exposes set_off_timer / set_on_timer / cancel_off_timer / cancel_on_timer
/ clear_timers as Home Assistant services targeting climate entities.

Each service resolves the target climate entity to its underlying
MirAIeDevice and invokes the device-side timer methods (which publish
the timer to the AC over MQTT).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from miraie_ac import Device as MirAIeDevice, MirAIeHub

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .logger import LOGGER

SERVICE_SET_OFF_TIMER = "set_off_timer"
SERVICE_SET_ON_TIMER = "set_on_timer"
SERVICE_CANCEL_OFF_TIMER = "cancel_off_timer"
SERVICE_CANCEL_ON_TIMER = "cancel_on_timer"
SERVICE_CLEAR_TIMERS = "clear_timers"

DURATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required("duration"): cv.time_period,
    }
)

CANCEL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})


def _devices_for_call(hass: HomeAssistant, call: ServiceCall) -> list[MirAIeDevice]:
    """Resolve the call's target climate entities to MirAIeDevice objects."""
    registry = er.async_get(hass)
    devices: list[MirAIeDevice] = []
    for entity_id in call.data[ATTR_ENTITY_ID]:
        entry = registry.async_get(entity_id)
        if entry is None or entry.platform != DOMAIN:
            LOGGER.warning("Skipping non-miraie entity %s", entity_id)
            continue
        # The unique_id is the device id (set in MirAIeClimate.__init__).
        for hub in hass.data[DOMAIN].values():
            if not isinstance(hub, MirAIeHub):
                continue
            device = next((d for d in hub.home.devices if d.id == entry.unique_id), None)
            if device is not None:
                devices.append(device)
                break
    return devices


def _seconds(call: ServiceCall) -> int:
    duration: timedelta = call.data["duration"]
    return int(duration.total_seconds())


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the timer services with Home Assistant."""

    if hass.services.has_service(DOMAIN, SERVICE_SET_OFF_TIMER):
        return

    async def _set_off_timer(call: ServiceCall) -> None:
        seconds = _seconds(call)
        for d in _devices_for_call(hass, call):
            LOGGER.debug("set_off_timer device=%s seconds=%d", d.friendly_name, seconds)
            await d.set_off_timer(seconds)

    async def _set_on_timer(call: ServiceCall) -> None:
        seconds = _seconds(call)
        for d in _devices_for_call(hass, call):
            LOGGER.debug("set_on_timer device=%s seconds=%d", d.friendly_name, seconds)
            await d.set_on_timer(seconds)

    async def _cancel_off_timer(call: ServiceCall) -> None:
        for d in _devices_for_call(hass, call):
            LOGGER.debug("cancel_off_timer device=%s", d.friendly_name)
            await d.cancel_off_timer()

    async def _cancel_on_timer(call: ServiceCall) -> None:
        for d in _devices_for_call(hass, call):
            LOGGER.debug("cancel_on_timer device=%s", d.friendly_name)
            await d.cancel_on_timer()

    async def _clear_timers(call: ServiceCall) -> None:
        for d in _devices_for_call(hass, call):
            LOGGER.debug("clear_timers device=%s", d.friendly_name)
            await d.clear_timers()

    hass.services.async_register(DOMAIN, SERVICE_SET_OFF_TIMER, _set_off_timer, schema=DURATION_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_ON_TIMER, _set_on_timer, schema=DURATION_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_OFF_TIMER, _cancel_off_timer, schema=CANCEL_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_ON_TIMER, _cancel_on_timer, schema=CANCEL_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_TIMERS, _clear_timers, schema=CANCEL_SCHEMA)


async def async_unregister_services(hass: HomeAssistant) -> None:
    for service in (
        SERVICE_SET_OFF_TIMER,
        SERVICE_SET_ON_TIMER,
        SERVICE_CANCEL_OFF_TIMER,
        SERVICE_CANCEL_ON_TIMER,
        SERVICE_CLEAR_TIMERS,
    ):
        hass.services.async_remove(DOMAIN, service)
