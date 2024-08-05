"""The MirAIe climate platform."""

from __future__ import annotations
from typing import Any
from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    DisplayMode,
)

from homeassistant.components.switch import (
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
)

from .logger import LOGGER

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:

    """Set up the MirAIe Climate Hub."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]

    entities = list(map(MirAIeDisplaySwitch, hub.home.devices))

    async_add_entities(entities)


class MirAIeDisplaySwitch(SwitchEntity):
    """Representation of a MirAIe Climate."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll: bool = False
        self._attr_unique_id = device.id
        self.device = device

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return f"{self.device.friendly_name} Display"
    
    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return DOMAIN

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return "mdi:eye-outline" if self.is_on else "mdi:eye-off-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.device.id)
            },
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return True if display is on."""
        return self.device.status.display_mode == DisplayMode.ON

    async def async_turn_off(self) -> None:
        await self.device.set_display_mode(DisplayMode.OFF)

    async def async_turn_on(self) -> None:
        await self.device.set_display_mode(DisplayMode.ON)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        
        LOGGER.debug("Successfully added display switch to HA")
        
        # Sensors should also register callbacks to HA when their state changes
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        
        LOGGER.debug("Successfully removed display switch from HA")
        
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.remove_callback(self.async_write_ha_state)